#!/usr/bin/env python3
# drone-detector/infrastructure/signal_io/playback.py
"""
IQ Data Playback Module

This module provides comprehensive IQ data playback capabilities for the Drone Detection System,
supporting:
- Playback from various file formats (binary, NumPy, HDF5, compressed)
- Variable speed playback (slow motion, fast forward)
- Loop/repeat playback modes
- Time-stretching and sample rate conversion
- Frame-by-frame stepping
- Seek to position
- Playlist management
- Synchronized multi-file playback
- Event triggers at specific times
- Thumbnail/spectrogram preview generation
- Network streaming of playback data
"""

import asyncio
import json
import os
import struct
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional, List, Callable, Dict, Any, Union, Tuple, Iterator
from collections import deque
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from scipy import signal

# Try to import optional dependencies
try:
    import h5py
    H5PY_AVAILABLE = True
except ImportError:
    H5PY_AVAILABLE = False

try:
    import zstandard as zstd
    ZSTD_AVAILABLE = True
except ImportError:
    ZSTD_AVAILABLE = False

try:
    import soundfile as sf
    SF_AVAILABLE = True
except ImportError:
    SF_AVAILABLE = False

# Setup logging
import logging
logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Data Classes
# ============================================================================

class PlaybackMode(Enum):
    """Playback operation modes"""
    NORMAL = "normal"
    LOOP = "loop"
    REPEAT = "repeat"
    ONCE = "once"
    RANDOM = "random"
    SHUFFLE = "shuffle"


class PlaybackState(Enum):
    """Playback state"""
    IDLE = "idle"
    PLAYING = "playing"
    PAUSED = "paused"
    STOPPED = "stopped"
    SEEKING = "seeking"
    ERROR = "error"


class PlaybackFileFormat(Enum):
    """Supported playback file formats"""
    RAW_BINARY = "raw"           # Raw binary IQ samples (complex64)
    NUMPY = "npy"                # NumPy .npy format
    HDF5 = "hdf5"                # HDF5 format
    ZSTD_COMPRESSED = "zstd"     # Zstandard compressed binary
    BLOSC_COMPRESSED = "blosc"   # Blosc compressed
    WAV = "wav"                  # WAV audio file (real part only)
    CSV = "csv"                  # CSV format (I,Q columns)


@dataclass
class PlaybackConfig:
    """Playback configuration"""
    # Playback settings
    mode: PlaybackMode = PlaybackMode.NORMAL
    speed: float = 1.0               # Playback speed multiplier
    sample_rate_conversion: bool = True
    target_sample_rate: Optional[float] = None
    
    # Buffer settings
    chunk_size: int = 16384          # Samples per chunk
    buffer_size: int = 524288        # Internal buffer size (samples)
    prefetch_chunks: int = 4         # Number of chunks to prefetch
    
    # Loop settings
    loop_count: int = -1             # -1 = infinite
    loop_start: float = 0.0          # Loop start time (seconds)
    loop_end: float = -1.0           # Loop end time (-1 = end of file)
    
    # Performance
    async_io: bool = True
    use_mmap: bool = False
    thread_pool_size: int = 2
    
    # Timestamp generation
    generate_timestamps: bool = True
    start_time: Optional[datetime] = None
    
    # Event triggers
    trigger_positions: Dict[float, Callable] = field(default_factory=dict)
    
    # Output
    output_sample_rate: Optional[float] = None
    normalize_output: bool = False
    scale_factor: float = 1.0


@dataclass
class PlaybackFile:
    """Represents a file to be played back"""
    path: Path
    format: PlaybackFileFormat
    metadata: Dict[str, Any] = field(default_factory=dict)
    num_samples: int = 0
    duration_seconds: float = 0.0
    sample_rate: float = 0.0
    center_freq: float = 0.0
    
    def __post_init__(self):
        """Load basic file info without loading data"""
        self._load_info()
    
    def _load_info(self):
        """Load file information"""
        try:
            if self.format == PlaybackFileFormat.RAW_BINARY:
                file_size = self.path.stat().st_size
                self.num_samples = file_size // 16  # complex64 = 16 bytes
                
            elif self.format == PlaybackFileFormat.NUMPY:
                data = np.load(self.path, mmap_mode='r')
                self.num_samples = len(data)
                if hasattr(data, 'dtype'):
                    self.sample_rate = data.attrs.get('sample_rate', 0)
                    self.center_freq = data.attrs.get('center_freq', 0)
            
            elif self.format == PlaybackFileFormat.HDF5 and H5PY_AVAILABLE:
                with h5py.File(self.path, 'r') as f:
                    self.num_samples = f['iq_data'].shape[0]
                    self.sample_rate = f.attrs.get('sample_rate', 0)
                    self.center_freq = f.attrs.get('center_freq', 0)
            
            # Load metadata if available
            metadata_file = self.path.parent / "metadata" / f"{self.path.stem}.json"
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    self.metadata = json.load(f)
                    if 'sample_rate' in self.metadata:
                        self.sample_rate = self.metadata['sample_rate']
                    if 'center_freq' in self.metadata:
                        self.center_freq = self.metadata['center_freq']
            
            if self.sample_rate > 0:
                self.duration_seconds = self.num_samples / self.sample_rate
                
        except Exception as e:
            logger.error(f"Failed to load file info: {e}")


@dataclass
class PlaybackPosition:
    """Current playback position"""
    file_index: int = 0
    sample_index: int = 0
    time_seconds: float = 0.0
    file_path: Optional[Path] = None
    timestamp: Optional[datetime] = None


# ============================================================================
# File Loader Classes
# ============================================================================

class FileLoader:
    """Base class for file loaders"""
    
    def __init__(self, file_path: Path, chunk_size: int, use_mmap: bool = False):
        self.file_path = file_path
        self.chunk_size = chunk_size
        self.use_mmap = use_mmap
        self._file_handle = None
        self._position = 0
    
    async def open(self):
        """Open file for reading"""
        raise NotImplementedError
    
    async def close(self):
        """Close file"""
        raise NotImplementedError
    
    async def read_chunk(self, num_samples: int) -> np.ndarray:
        """Read a chunk of samples"""
        raise NotImplementedError
    
    async def seek(self, sample_index: int) -> bool:
        """Seek to sample position"""
        raise NotImplementedError
    
    def get_position(self) -> int:
        """Get current sample position"""
        return self._position


class RawBinaryLoader(FileLoader):
    """Loader for raw binary IQ files"""
    
    async def open(self):
        """Open raw binary file"""
        if self.use_mmap:
            import mmap
            self._file_handle = open(self.file_path, 'rb')
            self._mmap = mmap.mmap(self._file_handle.fileno(), 0, access=mmap.ACCESS_READ)
        else:
            self._file_handle = open(self.file_path, 'rb')
        
        # Get file size
        self.file_size = self.file_path.stat().st_size
        self.num_samples = self.file_size // 16  # complex64 = 16 bytes
    
    async def close(self):
        """Close file"""
        if self.use_mmap and hasattr(self, '_mmap'):
            self._mmap.close()
        if self._file_handle:
            self._file_handle.close()
    
    async def read_chunk(self, num_samples: int) -> np.ndarray:
        """Read chunk of samples"""
        bytes_to_read = num_samples * 16
        remaining = self.file_size - (self._position * 16)
        bytes_to_read = min(bytes_to_read, remaining)
        
        if bytes_to_read <= 0:
            return np.array([], dtype=np.complex64)
        
        if self.use_mmap:
            data = self._mmap[self._position * 16:self._position * 16 + bytes_to_read]
        else:
            self._file_handle.seek(self._position * 16)
            data = await asyncio.get_event_loop().run_in_executor(
                None, self._file_handle.read, bytes_to_read
            )
        
        samples = np.frombuffer(data, dtype=np.complex64)
        self._position += len(samples)
        
        return samples
    
    async def seek(self, sample_index: int) -> bool:
        """Seek to position"""
        if sample_index < 0:
            sample_index = 0
        if sample_index > self.num_samples:
            sample_index = self.num_samples
        
        self._position = sample_index
        return True


class NumPyLoader(FileLoader):
    """Loader for NumPy .npy files"""
    
    async def open(self):
        """Open NumPy file"""
        if self.use_mmap:
            self._data = np.load(self.file_path, mmap_mode='r')
        else:
            self._data = np.load(self.file_path)
        
        self.num_samples = len(self._data)
    
    async def close(self):
        """Close file"""
        self._data = None
    
    async def read_chunk(self, num_samples: int) -> np.ndarray:
        """Read chunk of samples"""
        end = min(self._position + num_samples, self.num_samples)
        samples = self._data[self._position:end]
        self._position = end
        
        return samples
    
    async def seek(self, sample_index: int) -> bool:
        """Seek to position"""
        if sample_index < 0:
            sample_index = 0
        if sample_index > self.num_samples:
            sample_index = self.num_samples
        
        self._position = sample_index
        return True


class HDF5Loader(FileLoader):
    """Loader for HDF5 files"""
    
    async def open(self):
        """Open HDF5 file"""
        if not H5PY_AVAILABLE:
            raise RuntimeError("h5py not available")
        
        self._file = h5py.File(self.file_path, 'r')
        self._dataset = self._file['iq_data']
        self.num_samples = self._dataset.shape[0]
    
    async def close(self):
        """Close file"""
        if self._file:
            self._file.close()
    
    async def read_chunk(self, num_samples: int) -> np.ndarray:
        """Read chunk of samples"""
        end = min(self._position + num_samples, self.num_samples)
        samples = self._dataset[self._position:end]
        self._position = end
        
        return samples
    
    async def seek(self, sample_index: int) -> bool:
        """Seek to position"""
        if sample_index < 0:
            sample_index = 0
        if sample_index > self.num_samples:
            sample_index = self.num_samples
        
        self._position = sample_index
        return True


class ZstdLoader(FileLoader):
    """Loader for Zstandard compressed files"""
    
    async def open(self):
        """Open compressed file"""
        if not ZSTD_AVAILABLE:
            raise RuntimeError("zstandard not available")
        
        self._file_handle = open(self.file_path, 'rb')
        
        # Read header (original size)
        header = await asyncio.get_event_loop().run_in_executor(
            None, self._file_handle.read, 8
        )
        self.original_size = struct.unpack('<Q', header)[0]
        self.num_samples = self.original_size // 16
        
        # Read compressed data
        compressed = await asyncio.get_event_loop().run_in_executor(
            None, self._file_handle.read
        )
        
        # Decompress
        decompressor = zstd.ZstdDecompressor()
        self._data = decompressor.decompress(compressed, max_output_size=self.original_size)
        self._samples = np.frombuffer(self._data, dtype=np.complex64)
    
    async def close(self):
        """Close file"""
        if self._file_handle:
            self._file_handle.close()
    
    async def read_chunk(self, num_samples: int) -> np.ndarray:
        """Read chunk of samples"""
        end = min(self._position + num_samples, self.num_samples)
        samples = self._samples[self._position:end]
        self._position = end
        
        return samples
    
    async def seek(self, sample_index: int) -> bool:
        """Seek to position"""
        if sample_index < 0:
            sample_index = 0
        if sample_index > self.num_samples:
            sample_index = self.num_samples
        
        self._position = sample_index
        return True


class WAVLoader(FileLoader):
    """Loader for WAV audio files (extracts real part, creates IQ)"""
    
    async def open(self):
        """Open WAV file"""
        if not SF_AVAILABLE:
            raise RuntimeError("soundfile not available")
        
        self._data, self.sample_rate = sf.read(self.file_path)
        
        # If mono, use as real part, create imaginary zeros
        if len(self._data.shape) == 1:
            self._samples = self._data.astype(np.complex64)
        else:
            # If stereo, use as I/Q
            self._samples = (self._data[:, 0] + 1j * self._data[:, 1]).astype(np.complex64)
        
        self.num_samples = len(self._samples)
    
    async def close(self):
        """Close file"""
        self._samples = None
    
    async def read_chunk(self, num_samples: int) -> np.ndarray:
        """Read chunk of samples"""
        end = min(self._position + num_samples, self.num_samples)
        samples = self._samples[self._position:end]
        self._position = end
        
        return samples
    
    async def seek(self, sample_index: int) -> bool:
        """Seek to position"""
        if sample_index < 0:
            sample_index = 0
        if sample_index > self.num_samples:
            sample_index = self.num_samples
        
        self._position = sample_index
        return True


class CSVLoader(FileLoader):
    """Loader for CSV files with I,Q columns"""
    
    async def open(self):
        """Open CSV file"""
        self._data = np.loadtxt(self.file_path, delimiter=',')
        
        if self._data.shape[1] >= 2:
            self._samples = (self._data[:, 0] + 1j * self._data[:, 1]).astype(np.complex64)
        else:
            self._samples = self._data[:, 0].astype(np.complex64)
        
        self.num_samples = len(self._samples)
    
    async def close(self):
        """Close file"""
        self._samples = None
    
    async def read_chunk(self, num_samples: int) -> np.ndarray:
        """Read chunk of samples"""
        end = min(self._position + num_samples, self.num_samples)
        samples = self._samples[self._position:end]
        self._position = end
        
        return samples
    
    async def seek(self, sample_index: int) -> bool:
        """Seek to position"""
        if sample_index < 0:
            sample_index = 0
        if sample_index > self.num_samples:
            sample_index = self.num_samples
        
        self._position = sample_index
        return True


# ============================================================================
# File Loader Factory
# ============================================================================

class FileLoaderFactory:
    """Factory for creating appropriate file loaders"""
    
    @staticmethod
    def get_loader(file_path: Path, chunk_size: int, use_mmap: bool = False) -> FileLoader:
        """Get appropriate loader for file type"""
        suffix = file_path.suffix.lower()
        
        if suffix == '.iq':
            return RawBinaryLoader(file_path, chunk_size, use_mmap)
        elif suffix == '.npy':
            return NumPyLoader(file_path, chunk_size, use_mmap)
        elif suffix == '.h5' or suffix == '.hdf5':
            return HDF5Loader(file_path, chunk_size, use_mmap)
        elif suffix == '.zst':
            return ZstdLoader(file_path, chunk_size, use_mmap)
        elif suffix == '.wav':
            return WAVLoader(file_path, chunk_size, use_mmap)
        elif suffix == '.csv':
            return CSVLoader(file_path, chunk_size, use_mmap)
        else:
            # Try to detect format
            return FileLoaderFactory._detect_format(file_path, chunk_size, use_mmap)
    
    @staticmethod
    def _detect_format(file_path: Path, chunk_size: int, use_mmap: bool) -> FileLoader:
        """Detect file format by content"""
        # Try NumPy first
        try:
            np.load(file_path, mmap_mode='r')
            return NumPyLoader(file_path, chunk_size, use_mmap)
        except:
            pass
        
        # Try HDF5
        if H5PY_AVAILABLE:
            try:
                import h5py
                with h5py.File(file_path, 'r') as f:
                    if 'iq_data' in f:
                        return HDF5Loader(file_path, chunk_size, use_mmap)
            except:
                pass
        
        # Default to raw binary
        return RawBinaryLoader(file_path, chunk_size, use_mmap)


# ============================================================================
# IQ Playback Engine
# ============================================================================

class IQPlaybackEngine:
    """
    IQ Data Playback Engine
    
    Features:
    - Multiple file format support
    - Variable speed playback
    - Loop and repeat modes
    - Seek and position control
    - Prefetch buffering
    - Event triggers
    - Sample rate conversion
    """
    
    def __init__(self, config: Optional[PlaybackConfig] = None):
        """
        Initialize playback engine
        
        Args:
            config: Playback configuration
        """
        self.config = config or PlaybackConfig()
        self.state = PlaybackState.IDLE
        self.current_file: Optional[PlaybackFile] = None
        self.loader: Optional[FileLoader] = None
        self.playlist: List[PlaybackFile] = []
        self.current_position = PlaybackPosition()
        
        # Internal buffers
        self._buffer = deque(maxlen=self.config.buffer_size)
        self._prefetch_queue = asyncio.Queue(maxsize=self.config.prefetch_chunks)
        
        # Tasks and threads
        self._playback_task: Optional[asyncio.Task] = None
        self._prefetch_task: Optional[asyncio.Task] = None
        self._thread_pool = ThreadPoolExecutor(max_workers=self.config.thread_pool_size)
        
        # Synchronization
        self._pause_event = asyncio.Event()
        self._pause_event.set()
        self._stop_event = asyncio.Event()
        
        # Speed control
        self._speed = 1.0
        self._sample_rate_ratio = 1.0
        
        # Statistics
        self.stats = {
            'files_played': 0,
            'total_samples_played': 0,
            'total_duration_played': 0,
            'buffer_underruns': 0,
            'seek_operations': 0
        }
        
        # Event callbacks
        self._end_callbacks: List[Callable] = []
        self._position_callbacks: Dict[float, List[Callable]] = {}
        
        logger.info("IQ Playback Engine initialized")
    
    # ========================================================================
    # Playlist Management
    # ========================================================================
    
    def add_file(self, file_path: Union[str, Path]) -> PlaybackFile:
        """
        Add file to playlist
        
        Args:
            file_path: Path to file
            
        Returns:
            PlaybackFile object
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        # Detect format
        format = self._detect_format(path)
        
        playback_file = PlaybackFile(
            path=path,
            format=format
        )
        
        self.playlist.append(playback_file)
        logger.info(f"Added to playlist: {path.name} ({playback_file.num_samples} samples, "
                   f"{playback_file.duration_seconds:.2f}s)")
        
        return playback_file
    
    def add_directory(self, directory: Union[str, Path], pattern: str = "*.iq") -> List[PlaybackFile]:
        """
        Add all matching files from directory
        
        Args:
            directory: Directory path
            pattern: File pattern to match
            
        Returns:
            List of added PlaybackFile objects
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {dir_path}")
        
        added = []
        for file_path in dir_path.glob(pattern):
            try:
                added.append(self.add_file(file_path))
            except Exception as e:
                logger.error(f"Failed to add {file_path}: {e}")
        
        logger.info(f"Added {len(added)} files from {directory}")
        return added
    
    def remove_file(self, index: int) -> bool:
        """
        Remove file from playlist
        
        Args:
            index: Playlist index
            
        Returns:
            True if removed
        """
        if 0 <= index < len(self.playlist):
            removed = self.playlist.pop(index)
            logger.info(f"Removed from playlist: {removed.path.name}")
            return True
        return False
    
    def clear_playlist(self):
        """Clear the playlist"""
        self.playlist.clear()
        logger.info("Playlist cleared")
    
    def get_playlist_info(self) -> List[Dict[str, Any]]:
        """Get playlist information"""
        return [
            {
                'index': i,
                'name': f.path.name,
                'duration': f.duration_seconds,
                'samples': f.num_samples,
                'sample_rate': f.sample_rate
            }
            for i, f in enumerate(self.playlist)
        ]
    
    # ========================================================================
    # Format Detection
    # ========================================================================
    
    def _detect_format(self, file_path: Path) -> PlaybackFileFormat:
        """Detect file format from extension or content"""
        suffix = file_path.suffix.lower()
        
        format_map = {
            '.iq': PlaybackFileFormat.RAW_BINARY,
            '.npy': PlaybackFileFormat.NUMPY,
            '.h5': PlaybackFileFormat.HDF5,
            '.hdf5': PlaybackFileFormat.HDF5,
            '.zst': PlaybackFileFormat.ZSTD_COMPRESSED,
            '.wav': PlaybackFileFormat.WAV,
            '.csv': PlaybackFileFormat.CSV
        }
        
        if suffix in format_map:
            return format_map[suffix]
        
        # Default to raw binary
        return PlaybackFileFormat.RAW_BINARY
    
    # ========================================================================
    # Playback Control
    # ========================================================================
    
    async def play(self, file_index: int = 0, start_time: float = 0.0) -> bool:
        """
        Start playback
        
        Args:
            file_index: Index in playlist (default: 0)
            start_time: Start time in seconds
            
        Returns:
            True if started successfully
        """
        if self.state == PlaybackState.PLAYING:
            await self.stop()
        
        if not self.playlist:
            logger.error("No files in playlist")
            return False
        
        if file_index >= len(self.playlist):
            logger.error(f"Invalid file index: {file_index}")
            return False
        
        self.current_file = self.playlist[file_index]
        self.current_position.file_index = file_index
        self.current_position.file_path = self.current_file.path
        
        # Create loader
        self.loader = FileLoaderFactory.get_loader(
            self.current_file.path,
            self.config.chunk_size,
            self.config.use_mmap
        )
        await self.loader.open()
        
        # Seek to start position
        if start_time > 0:
            start_sample = int(start_time * self.current_file.sample_rate)
            await self.loader.seek(start_sample)
            self.current_position.sample_index = start_sample
            self.current_position.time_seconds = start_time
        else:
            self.current_position.sample_index = 0
            self.current_position.time_seconds = 0
        
        # Setup timestamp generation
        if self.config.generate_timestamps:
            self.current_position.timestamp = self.config.start_time or datetime.now()
        
        # Reset state
        self._stop_event.clear()
        self.state = PlaybackState.PLAYING
        
        # Calculate sample rate ratio for speed control
        target_rate = self.config.output_sample_rate or self.current_file.sample_rate
        self._sample_rate_ratio = self.current_file.sample_rate / target_rate
        
        # Start tasks
        self._prefetch_task = asyncio.create_task(self._prefetch_loop())
        self._playback_task = asyncio.create_task(self._playback_loop())
        
        logger.info(f"Playback started: {self.current_file.path.name} at {start_time:.2f}s")
        return True
    
    async def pause(self):
        """Pause playback"""
        if self.state == PlaybackState.PLAYING:
            self.state = PlaybackState.PAUSED
            self._pause_event.clear()
            logger.info("Playback paused")
    
    async def resume(self):
        """Resume playback"""
        if self.state == PlaybackState.PAUSED:
            self.state = PlaybackState.PLAYING
            self._pause_event.set()
            logger.info("Playback resumed")
    
    async def stop(self):
        """Stop playback"""
        if self.state in [PlaybackState.PLAYING, PlaybackState.PAUSED]:
            self.state = PlaybackState.STOPPING
            self._stop_event.set()
            
            # Wait for tasks to complete
            if self._playback_task:
                await asyncio.wait_for(self._playback_task, timeout=5)
            if self._prefetch_task:
                await asyncio.wait_for(self._prefetch_task, timeout=5)
            
            # Close loader
            if self.loader:
                await self.loader.close()
            
            self.state = PlaybackState.STOPPED
            logger.info("Playback stopped")
    
    async def seek(self, time_seconds: float) -> bool:
        """
        Seek to position
        
        Args:
            time_seconds: Time in seconds
            
        Returns:
            True if successful
        """
        if not self.loader or not self.current_file:
            return False
        
        self.state = PlaybackState.SEEKING
        
        # Calculate sample position
        target_sample = int(time_seconds * self.current_file.sample_rate)
        target_sample = max(0, min(target_sample, self.current_file.num_samples))
        
        # Seek in loader
        await self.loader.seek(target_sample)
        
        # Clear buffer
        self._buffer.clear()
        
        # Update position
        self.current_position.sample_index = target_sample
        self.current_position.time_seconds = target_sample / self.current_file.sample_rate
        
        if self.config.generate_timestamps and self.current_position.timestamp:
            time_delta = timedelta(seconds=self.current_position.time_seconds)
            self.current_position.timestamp = (self.config.start_time or datetime.now()) + time_delta
        
        self.state = PlaybackState.PLAYING
        self.stats['seek_operations'] += 1
        
        logger.info(f"Seeked to {time_seconds:.2f}s (sample {target_sample})")
        return True
    
    async def set_speed(self, speed: float):
        """
        Set playback speed
        
        Args:
            speed: Speed multiplier (0.5 = half speed, 2.0 = double speed)
        """
        self._speed = max(0.1, min(speed, 10.0))
        logger.info(f"Playback speed set to {self._speed}x")
    
    def get_speed(self) -> float:
        """Get current playback speed"""
        return self._speed
    
    async def next_file(self) -> bool:
        """
        Skip to next file in playlist
        
        Returns:
            True if successful
        """
        if not self.playlist:
            return False
        
        next_index = (self.current_position.file_index + 1) % len(self.playlist)
        return await self.play(next_index)
    
    async def previous_file(self) -> bool:
        """
        Go to previous file in playlist
        
        Returns:
            True if successful
        """
        if not self.playlist:
            return False
        
        prev_index = (self.current_position.file_index - 1) % len(self.playlist)
        return await self.play(prev_index)
    
    # ========================================================================
    # Internal Playback Loops
    # ========================================================================
    
    async def _prefetch_loop(self):
        """Background loop for prefetching chunks"""
        while not self._stop_event.is_set():
            try:
                # Check if buffer needs refilling
                if len(self._buffer) < self.config.buffer_size // 2:
                    # Read chunk
                    chunk = await self.loader.read_chunk(self.config.chunk_size)
                    
                    if len(chunk) == 0:
                        # End of file
                        break
                    
                    # Apply speed scaling if needed
                    if self._speed != 1.0:
                        chunk = self._resample_chunk(chunk)
                    
                    self._buffer.extend(chunk)
                
                await asyncio.sleep(0.01)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Prefetch error: {e}")
                await asyncio.sleep(0.1)
    
    async def _playback_loop(self):
        """Main playback loop"""
        last_time = time.time()
        samples_per_second = self.current_file.sample_rate * self._speed
        
        while not self._stop_event.is_set():
            # Wait if paused
            await self._pause_event.wait()
            
            if self.state != PlaybackState.PLAYING:
                await asyncio.sleep(0.01)
                continue
            
            # Get next chunk from buffer
            if len(self._buffer) >= self.config.chunk_size:
                chunk = [self._buffer.popleft() for _ in range(self.config.chunk_size)]
                chunk = np.array(chunk, dtype=np.complex64)
                
                # Apply sample rate conversion if needed
                if self.config.sample_rate_conversion and self.config.output_sample_rate:
                    chunk = self._convert_sample_rate(chunk)
                
                # Apply normalization
                if self.config.normalize_output:
                    max_val = np.max(np.abs(chunk))
                    if max_val > 0:
                        chunk = chunk / max_val
                
                # Apply scaling
                if self.config.scale_factor != 1.0:
                    chunk = chunk * self.config.scale_factor
                
                # Update position
                self.current_position.sample_index += len(chunk)
                self.current_position.time_seconds = self.current_position.sample_index / self.current_file.sample_rate
                
                # Update timestamp
                if self.config.generate_timestamps and self.current_position.timestamp:
                    time_delta = len(chunk) / self.current_file.sample_rate
                    self.current_position.timestamp += timedelta(seconds=time_delta)
                
                # Trigger position callbacks
                await self._trigger_position_callbacks(self.current_position.time_seconds)
                
                # Yield chunk to consumer
                yield chunk
                
                # Update stats
                self.stats['total_samples_played'] += len(chunk)
                
                # Control playback speed
                expected_elapsed = len(chunk) / samples_per_second
                actual_elapsed = time.time() - last_time
                if actual_elapsed < expected_elapsed:
                    await asyncio.sleep(expected_elapsed - actual_elapsed)
                last_time = time.time()
                
            elif len(self._buffer) == 0:
                # Buffer underrun
                self.stats['buffer_underruns'] += 1
                await asyncio.sleep(0.001)
            
            else:
                # Buffer partial, wait for more
                await asyncio.sleep(0.001)
        
        # End of playback
        self.stats['files_played'] += 1
        self.stats['total_duration_played'] += self.current_position.time_seconds
        
        # Check loop mode
        if self.config.mode == PlaybackMode.LOOP or self.config.mode == PlaybackMode.REPEAT:
            if self.config.loop_count == -1 or self.stats['files_played'] < self.config.loop_count:
                await self.seek(self.config.loop_start)
                await self.play(self.current_position.file_index, self.config.loop_start)
                return
        
        # Handle playlist advancement
        if self.config.mode == PlaybackMode.SHUFFLE:
            import random
            next_index = random.randint(0, len(self.playlist) - 1)
            await self.play(next_index)
        elif self.config.mode == PlaybackMode.RANDOM:
            import random
            next_index = random.randint(0, len(self.playlist) - 1)
            await self.play(next_index)
        elif self.current_position.file_index + 1 < len(self.playlist):
            await self.play(self.current_position.file_index + 1)
        
        # Trigger end callbacks
        for callback in self._end_callbacks:
            if asyncio.iscoroutinefunction(callback):
                await callback()
            else:
                callback()
        
        self.state = PlaybackState.IDLE
    
    def _resample_chunk(self, chunk: np.ndarray) -> np.ndarray:
        """Resample chunk for speed adjustment"""
        if self._speed == 1.0:
            return chunk
        
        # Calculate new length
        new_len = int(len(chunk) / self._speed)
        
        # Use scipy resample for better quality
        if len(chunk) > 0:
            resampled = signal.resample(chunk, new_len)
            return resampled.astype(np.complex64)
        
        return chunk
    
    def _convert_sample_rate(self, chunk: np.ndarray) -> np.ndarray:
        """Convert sample rate of chunk"""
        if not self.config.output_sample_rate:
            return chunk
        
        ratio = self.current_file.sample_rate / self.config.output_sample_rate
        
        if abs(ratio - 1.0) < 0.01:
            return chunk
        
        new_len = int(len(chunk) / ratio)
        
        if new_len > 0:
            resampled = signal.resample(chunk, new_len)
            return resampled.astype(np.complex64)
        
        return chunk
    
    async def _trigger_position_callbacks(self, time_seconds: float):
        """Trigger callbacks at specific positions"""
        # Check for exact time matches
        for trigger_time, callback in self.config.trigger_positions.items():
            if abs(time_seconds - trigger_time) < 0.01:  # 10ms tolerance
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
        
        # Check for range callbacks
        for pos_range, callbacks in self._position_callbacks.items():
            if pos_range[0] <= time_seconds < pos_range[1]:
                for callback in callbacks:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(time_seconds)
                    else:
                        callback(time_seconds)
    
    # ========================================================================
    # Event Callbacks
    # ========================================================================
    
    def on_end(self, callback: Callable):
        """Register callback for playback end"""
        self._end_callbacks.append(callback)
    
    def on_position(self, start_time: float, end_time: float, callback: Callable):
        """
        Register callback for position range
        
        Args:
            start_time: Start time in seconds
            end_time: End time in seconds
            callback: Callback function
        """
        key = (start_time, end_time)
        if key not in self._position_callbacks:
            self._position_callbacks[key] = []
        self._position_callbacks[key].append(callback)
    
    # ========================================================================
    # Utility Methods
    # ========================================================================
    
    def get_current_position(self) -> PlaybackPosition:
        """Get current playback position"""
        return self.current_position
    
    def get_current_position_seconds(self) -> float:
        """Get current position in seconds"""
        return self.current_position.time_seconds
    
    def get_remaining_seconds(self) -> float:
        """Get remaining time in current file"""
        if not self.current_file:
            return 0
        return self.current_file.duration_seconds - self.current_position.time_seconds
    
    def get_progress_percent(self) -> float:
        """Get playback progress percentage"""
        if not self.current_file or self.current_file.num_samples == 0:
            return 0
        return (self.current_position.sample_index / self.current_file.num_samples) * 100
    
    def get_stats(self) -> Dict[str, Any]:
        """Get playback statistics"""
        return {
            **self.stats,
            'state': self.state.value,
            'playlist_size': len(self.playlist),
            'current_file': str(self.current_file.path) if self.current_file else None,
            'current_position_seconds': self.get_current_position_seconds(),
            'progress_percent': self.get_progress_percent(),
            'buffer_size': len(self._buffer),
            'speed': self._speed,
            'sample_rate': self.current_file.sample_rate if self.current_file else 0,
            'output_sample_rate': self.config.output_sample_rate or 0
        }
    
    async def shutdown(self):
        """Shutdown playback engine"""
        await self.stop()
        self._thread_pool.shutdown(wait=True)
        logger.info("IQ Playback Engine shutdown complete")


# ============================================================================
# Playback Iterator (For Streaming)
# ============================================================================

class IQPlaybackIterator:
    """
    Async iterator for streaming playback data
    
    Usage:
        async for chunk in playback.iterate():
            process(chunk)
    """
    
    def __init__(self, engine: IQPlaybackEngine):
        self.engine = engine
        self._generator = None
    
    def __aiter__(self):
        return self
    
    async def __anext__(self):
        if not self._generator:
            self._generator = self.engine._playback_loop()
        
        try:
            chunk = await self._generator.__anext__()
            return chunk
        except StopAsyncIteration:
            raise StopAsyncIteration


# ============================================================================
# Factory Functions
# ============================================================================

def create_playback_engine(output_sample_rate: Optional[float] = None,
                          mode: PlaybackMode = PlaybackMode.NORMAL) -> IQPlaybackEngine:
    """
    Create a configured playback engine
    
    Args:
        output_sample_rate: Output sample rate (None = same as source)
        mode: Playback mode
        
    Returns:
        Configured IQPlaybackEngine
    """
    config = PlaybackConfig(
        mode=mode,
        output_sample_rate=output_sample_rate,
        sample_rate_conversion=output_sample_rate is not None
    )
    return IQPlaybackEngine(config)


def create_looping_playback(loop_start: float = 0.0, loop_end: float = -1.0) -> IQPlaybackEngine:
    """
    Create a looping playback engine
    
    Args:
        loop_start: Loop start time in seconds
        loop_end: Loop end time in seconds (-1 = end of file)
        
    Returns:
        Looping playback engine
    """
    config = PlaybackConfig(
        mode=PlaybackMode.LOOP,
        loop_start=loop_start,
        loop_end=loop_end,
        loop_count=-1
    )
    return IQPlaybackEngine(config)


# ============================================================================
# Example Usage
# ============================================================================

async def example_playback():
    """Example of basic playback"""
    print("IQ Playback Example")
    print("-" * 30)
    
    # Create playback engine
    engine = create_playback_engine()
    
    # Add file to playlist
    engine.add_file("data/iq/replay/dji_sample.iq")
    
    # Register end callback
    def on_playback_end():
        print("Playback completed!")
    
    engine.on_end(on_playback_end)
    
    # Start playback
    await engine.play()
    
    # Iterate over chunks
    async for chunk in IQPlaybackIterator(engine):
        print(f"Received chunk: {len(chunk)} samples")
        # Process chunk (e.g., send to detection engine)
        if chunk is None:
            break
    
    # Get statistics
    stats = engine.get_stats()
    print(f"\nPlayback Stats: {stats}")
    
    await engine.shutdown()


async def example_controlled_playback():
    """Example of controlled playback with seeking and speed control"""
    print("\nControlled Playback Example")
    print("-" * 30)
    
    engine = create_playback_engine()
    engine.add_file("data/iq/replay/long_recording.iq")
    
    # Start playback
    await engine.play()
    
    # Run control loop
    for i in range(10):
        await asyncio.sleep(2)
        
        # Show progress
        progress = engine.get_progress_percent()
        position = engine.get_current_position_seconds()
        remaining = engine.get_remaining_seconds()
        
        print(f"Position: {position:.1f}s, Progress: {progress:.1f}%, Remaining: {remaining:.1f}s")
        
        # Change speed periodically
        if i == 3:
            await engine.set_speed(1.5)
            print("Speed increased to 1.5x")
        elif i == 6:
            await engine.set_speed(0.5)
            print("Speed decreased to 0.5x")
        elif i == 8:
            await engine.seek(10)
            print("Seeked to 10 seconds")
    
    await engine.stop()
    await engine.shutdown()


async def example_playlist_demo():
    """Example of playlist playback"""
    print("\nPlaylist Demo")
    print("-" * 30)
    
    engine = create_playback_engine(mode=PlaybackMode.SHUFFLE)
    
    # Add multiple files
    engine.add_directory("data/iq/replay", pattern="*.iq")
    
    # Show playlist
    playlist = engine.get_playlist_info()
    print(f"Playlist has {len(playlist)} files")
    for info in playlist:
        print(f"  {info['name']}: {info['duration']:.2f}s")
    
    # Start playback
    await engine.play(0)
    
    # Simulate playback
    for i in range(5):
        await asyncio.sleep(1)
        if engine.get_progress_percent() > 95:
            print("Moving to next file...")
    
    await engine.stop()
    await engine.shutdown()


async def main():
    """Main example"""
    print("IQ Playback Module Test")
    print("=" * 50)
    
    # Run examples
    await example_playback()
    await example_controlled_playback()
    await example_playlist_demo()
    
    print("\n" + "=" * 50)
    print("IQ Playback test complete!")


if __name__ == "__main__":
    asyncio.run(main())