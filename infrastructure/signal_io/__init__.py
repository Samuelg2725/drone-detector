#!/usr/bin/env python3
# drone-detector/infrastructure/signal_io/__init__.py
"""
Infrastructure Signal I/O Module

This module provides comprehensive signal input/output capabilities for the Drone Detection System,
including:
- Real-time IQ streaming from SDR hardware
- IQ data recording to various formats
- IQ playback from recorded files
- File reading for multiple IQ formats
- Session management for recordings
- Performance monitoring and statistics
- Asynchronous I/O operations
- Memory-mapped file access
- Chunked processing for large files
- Format conversion utilities

Supported Operations:
- Stream: Real-time IQ data from hardware
- Record: Save IQ data to disk
- Playback: Replay recorded IQ data
- Read: Load IQ data from various file formats
"""

from typing import Dict, Any, Optional, List, Union, Tuple
from datetime import datetime

# ============================================================================
# IQ Stream
# ============================================================================

from .iq_stream import (
    IQStream,
    IQStreamSource,
    MockStreamSource,
    StreamConfig,
    StreamState,
    StreamChunk,
    StreamStats,
    DataType,
    RingBuffer,
    IQStreamBuilder,
    create_mock_stream,
    create_stream_from_hardware,
    fft_processor,
    power_processor
)

# ============================================================================
# IQ Recorder
# ============================================================================

from .recorder import (
    IQRecorder,
    RecordingConfig,
    RecordingFormat,
    RecordingMode,
    RecorderState,
    RecordingMetadata,
    RecordingSession,
    create_recorder,
    create_continuous_recorder
)

# ============================================================================
# IQ Playback
# ============================================================================

from .playback import (
    IQPlaybackEngine,
    PlaybackConfig,
    PlaybackMode,
    PlaybackState,
    PlaybackFile,
    PlaybackFileFormat,
    PlaybackPosition,
    IQPlaybackIterator,
    FileLoader,
    FileLoaderFactory,
    create_playback_engine,
    create_looping_playback
)

# ============================================================================
# File Reader
# ============================================================================

from .file_reader import (
    IQFileReader,
    IQFileReaderFactory,
    IQFileFormat,
    SampleType,
    IQFileInfo,
    ReadConfig,
    RawBinaryReader,
    NumPyReader,
    HDF5Reader,
    CompressedReader,
    SigMFReader,
    CSVReader,
    WAVReader,
    GNURadioReader,
    UHDReader,
    BatchIQReader,
    read_iq_file,
    get_file_info,
    convert_iq_format
)

# ============================================================================
# Version and Metadata
# ============================================================================

__version__ = "2.0.0"
__author__ = "Drone Detection System Team"
__copyright__ = "Copyright 2024-2025, Drone Detection System"
__license__ = "MIT"

# ============================================================================
# Public API - Explicit Exports
# ============================================================================

__all__ = [
    # IQ Stream
    "IQStream",
    "IQStreamSource",
    "MockStreamSource",
    "StreamConfig",
    "StreamState",
    "StreamChunk",
    "StreamStats",
    "DataType",
    "RingBuffer",
    "IQStreamBuilder",
    "create_mock_stream",
    "create_stream_from_hardware",
    "fft_processor",
    "power_processor",
    
    # IQ Recorder
    "IQRecorder",
    "RecordingConfig",
    "RecordingFormat",
    "RecordingMode",
    "RecorderState",
    "RecordingMetadata",
    "RecordingSession",
    "create_recorder",
    "create_continuous_recorder",
    
    # IQ Playback
    "IQPlaybackEngine",
    "PlaybackConfig",
    "PlaybackMode",
    "PlaybackState",
    "PlaybackFile",
    "PlaybackFileFormat",
    "PlaybackPosition",
    "IQPlaybackIterator",
    "FileLoader",
    "FileLoaderFactory",
    "create_playback_engine",
    "create_looping_playback",
    
    # File Reader
    "IQFileReader",
    "IQFileReaderFactory",
    "IQFileFormat",
    "SampleType",
    "IQFileInfo",
    "ReadConfig",
    "RawBinaryReader",
    "NumPyReader",
    "HDF5Reader",
    "CompressedReader",
    "SigMFReader",
    "CSVReader",
    "WAVReader",
    "GNURadioReader",
    "UHDReader",
    "BatchIQReader",
    "read_iq_file",
    "get_file_info",
    "convert_iq_format",
]


# ============================================================================
# Unified Signal I/O Manager
# ============================================================================

class SignalIOManager:
    """
    Unified Signal I/O Manager
    
    This class provides a single interface for all signal I/O operations:
    - Streaming real-time IQ data
    - Recording to disk
    - Playback from files
    - File reading and conversion
    
    Usage:
        manager = SignalIOManager()
        
        # Start streaming from hardware
        await manager.start_stream(sample_rate=2.4e6)
        
        # Record to file
        await manager.start_recording("detection_001")
        
        # Stop and save
        metadata = await manager.stop_recording()
        
        # Playback recorded file
        await manager.playback("detection_001.iq")
    """
    
    def __init__(self):
        """Initialize Signal I/O Manager"""
        self.stream: Optional[IQStream] = None
        self.recorder: Optional[IQRecorder] = None
        self.playback_engine: Optional[IQPlaybackEngine] = None
        
        self._stream_task: Optional[asyncio.Task] = None
        self._processing_callbacks: List[Callable] = []
        
        self.stats = {
            'streaming': False,
            'recording': False,
            'playback': False,
            'total_samples_streamed': 0,
            'total_samples_recorded': 0,
            'total_samples_played': 0
        }
        
        logger.info("Signal I/O Manager initialized")
    
    # ========================================================================
    # Stream Management
    # ========================================================================
    
    async def start_stream(self, sample_rate: float = 2.4e6,
                          hardware_type: str = 'mock',
                          center_freq: float = 2.44e9,
                          callbacks: Optional[List[Callable]] = None) -> bool:
        """
        Start IQ data stream
        
        Args:
            sample_rate: Sample rate in Hz
            hardware_type: Type of hardware ('mock', 'hackrf', 'rtlsdr')
            center_freq: Center frequency in Hz
            callbacks: List of callback functions for stream chunks
            
        Returns:
            True if stream started successfully
        """
        if self.stream:
            await self.stop_stream()
        
        # Create stream
        if hardware_type == 'mock':
            self.stream = create_mock_stream(sample_rate, signal_type='drone')
        else:
            self.stream = create_stream_from_hardware(sample_rate, hardware_type)
        
        # Set center frequency if supported
        if hasattr(self.stream.source, 'set_center_freq'):
            self.stream.source.set_center_freq(center_freq)
        
        # Add processors
        for callback in (callbacks or []):
            self.stream.add_processor(callback)
        
        # Start stream
        await self.stream.start()
        
        # Start processing task
        self._stream_task = asyncio.create_task(self._process_stream_loop())
        
        self.stats['streaming'] = True
        logger.info(f"Stream started: {sample_rate/1e6:.1f} MHz at {center_freq/1e9:.2f} GHz")
        return True
    
    async def stop_stream(self) -> None:
        """Stop IQ data stream"""
        if self.stream:
            await self.stream.stop()
            self.stream = None
        
        if self._stream_task:
            self._stream_task.cancel()
            self._stream_task = None
        
        self.stats['streaming'] = False
        logger.info("Stream stopped")
    
    async def _process_stream_loop(self):
        """Background task for processing stream chunks"""
        if not self.stream:
            return
        
        async for chunk in self.stream._playback_loop():
            # Update statistics
            self.stats['total_samples_streamed'] += len(chunk)
            
            # Forward to recorder if active
            if self.recorder and self.stats['recording']:
                await self.recorder.write_samples(chunk)
            
            # Call processing callbacks
            for callback in self._processing_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(chunk)
                    else:
                        callback(chunk)
                except Exception as e:
                    logger.error(f"Callback error: {e}")
    
    # ========================================================================
    # Recording Management
    # ========================================================================
    
    async def start_recording(self, session_name: Optional[str] = None,
                            metadata: Optional[Dict[str, Any]] = None,
                            format: RecordingFormat = RecordingFormat.RAW_BINARY) -> str:
        """
        Start recording IQ data
        
        Args:
            session_name: Name for the recording session
            metadata: Additional metadata to include
            format: Recording format
            
        Returns:
            Recording ID
        """
        if not self.recorder:
            self.recorder = create_recorder(format=format)
        
        recording_id = await self.recorder.start_recording(session_name, metadata)
        self.stats['recording'] = True
        self.stats['total_samples_recorded'] = 0
        
        logger.info(f"Recording started: {recording_id}")
        return recording_id
    
    async def stop_recording(self) -> Optional[RecordingMetadata]:
        """Stop current recording"""
        if not self.recorder:
            return None
        
        metadata = await self.recorder.stop_recording()
        self.stats['recording'] = False
        
        if metadata:
            logger.info(f"Recording stopped: {metadata.recording_id}, "
                       f"{metadata.duration_seconds:.2f}s, {metadata.file_size_bytes/1024/1024:.2f}MB")
        
        return metadata
    
    # ========================================================================
    # Playback Management
    # ========================================================================
    
    async def playback_file(self, file_path: Union[str, Path],
                           speed: float = 1.0,
                           loop: bool = False) -> bool:
        """
        Playback a recorded IQ file
        
        Args:
            file_path: Path to IQ file
            speed: Playback speed multiplier
            loop: Whether to loop playback
            
        Returns:
            True if playback started
        """
        if self.playback_engine:
            await self.stop_playback()
        
        if loop:
            self.playback_engine = create_looping_playback()
        else:
            self.playback_engine = create_playback_engine()
        
        self.playback_engine.add_file(file_path)
        await self.playback_engine.set_speed(speed)
        
        # Start playback task
        asyncio.create_task(self._playback_loop())
        
        self.stats['playback'] = True
        logger.info(f"Playback started: {file_path}")
        return True
    
    async def stop_playback(self) -> None:
        """Stop playback"""
        if self.playback_engine:
            await self.playback_engine.stop()
            self.playback_engine = None
        
        self.stats['playback'] = False
        logger.info("Playback stopped")
    
    async def _playback_loop(self):
        """Background task for playback"""
        if not self.playback_engine:
            return
        
        async for chunk in IQPlaybackIterator(self.playback_engine):
            self.stats['total_samples_played'] += len(chunk)
            
            # Forward to processing callbacks
            for callback in self._processing_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(chunk)
                    else:
                        callback(chunk)
                except Exception as e:
                    logger.error(f"Playback callback error: {e}")
    
    # ========================================================================
    # File Operations
    # ========================================================================
    
    async def read_file(self, file_path: Union[str, Path],
                       sample_limit: int = 0) -> Tuple[np.ndarray, IQFileInfo]:
        """
        Read IQ file
        
        Args:
            file_path: Path to IQ file
            sample_limit: Maximum samples to read (0 = all)
            
        Returns:
            Tuple of (samples, file_info)
        """
        return await read_iq_file(file_path, sample_limit=sample_limit)
    
    async def convert_file(self, input_path: Union[str, Path],
                          output_path: Union[str, Path],
                          output_format: IQFileFormat) -> bool:
        """
        Convert IQ file to another format
        
        Args:
            input_path: Source file path
            output_path: Destination file path
            output_format: Target format
            
        Returns:
            True if conversion successful
        """
        return await convert_iq_format(input_path, output_path, output_format)
    
    def get_file_info(self, file_path: Union[str, Path]) -> IQFileInfo:
        """
        Get file information without reading data
        
        Args:
            file_path: Path to file
            
        Returns:
            File information
        """
        return get_file_info(file_path)
    
    # ========================================================================
    # Callback Management
    # ========================================================================
    
    def add_callback(self, callback: Callable) -> None:
        """
        Add a callback for stream/playback data
        
        Args:
            callback: Function that accepts a stream chunk
        """
        self._processing_callbacks.append(callback)
        logger.debug(f"Added callback: {callback.__name__}")
    
    def remove_callback(self, callback: Callable) -> None:
        """Remove a callback"""
        if callback in self._processing_callbacks:
            self._processing_callbacks.remove(callback)
            logger.debug(f"Removed callback: {callback.__name__}")
    
    def clear_callbacks(self) -> None:
        """Clear all callbacks"""
        self._processing_callbacks.clear()
        logger.debug("All callbacks cleared")
    
    # ========================================================================
    # Utility Methods
    # ========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get manager statistics"""
        stats = {**self.stats}
        
        if self.stream:
            stats['stream_stats'] = self.stream.get_stats()
        
        if self.recorder:
            stats['recorder_stats'] = self.recorder.get_stats()
        
        if self.playback_engine:
            stats['playback_stats'] = self.playback_engine.get_stats()
        
        return stats
    
    async def shutdown(self):
        """Shutdown all I/O operations"""
        await self.stop_stream()
        await self.stop_recording()
        await self.stop_playback()
        
        if self.recorder:
            await self.recorder.shutdown()
        
        logger.info("Signal I/O Manager shutdown complete")


# ============================================================================
# Convenience Functions
# ============================================================================

def get_signal_io_info() -> Dict[str, Any]:
    """
    Get information about available signal I/O components
    
    Returns:
        Dictionary with component information
    """
    return {
        "version": __version__,
        "components": {
            "stream": {
                "description": "Real-time IQ streaming from SDR hardware",
                "sources": ["mock", "hackrf", "rtlsdr", "pluto"],
                "features": ["real-time", "ring_buffer", "callbacks"]
            },
            "recorder": {
                "description": "IQ data recording to disk",
                "formats": ["raw", "npy", "hdf5", "zstd", "blosc"],
                "features": ["trigger", "scheduled", "continuous", "rotation"]
            },
            "playback": {
                "description": "IQ file playback",
                "formats": ["raw", "npy", "hdf5", "zstd", "wav", "csv"],
                "features": ["speed_control", "loop", "seek", "playlist"]
            },
            "file_reader": {
                "description": "IQ file reading and conversion",
                "formats": ["raw", "npy", "hdf5", "zstd", "gz", "bz2", "lz4", "sigmf", "wav", "csv"],
                "features": ["auto_detect", "batch", "convert", "metadata"]
            }
        }
    }


# ============================================================================
# Singleton Manager
# ============================================================================

_default_signal_io_manager: Optional[SignalIOManager] = None


async def get_signal_io_manager() -> SignalIOManager:
    """
    Get or create the default signal I/O manager singleton
    
    Returns:
        SignalIOManager instance
    """
    global _default_signal_io_manager
    
    if _default_signal_io_manager is None:
        _default_signal_io_manager = SignalIOManager()
    
    return _default_signal_io_manager


async def reset_signal_io_manager() -> None:
    """Reset the default signal I/O manager"""
    global _default_signal_io_manager
    
    if _default_signal_io_manager:
        await _default_signal_io_manager.shutdown()
        _default_signal_io_manager = None


# ============================================================================
# Module Documentation
# ============================================================================

__doc__ = """
Infrastructure Signal I/O Package
=================================

This package provides comprehensive signal input/output capabilities for the 
Drone Detection System.

Components:
-----------
1. **IQ Stream** - Real-time IQ data from SDR hardware
2. **IQ Recorder** - Save IQ data to disk with metadata
3. **IQ Playback** - Replay recorded IQ files
4. **File Reader** - Read various IQ file formats

Quick Start:
-----------
```python
from infrastructure.signal_io import (
    SignalIOManager,
    get_signal_io_manager,
    RecordingFormat,
    IQFileFormat
)

# Method 1: Use unified manager
manager = await get_signal_io_manager()

# Start streaming
await manager.start_stream(sample_rate=2.4e6)

# Record to file
await manager.start_recording("drone_detection", format=RecordingFormat.NUMPY)

# Stop recording
metadata = await manager.stop_recording()

# Playback recorded file
await manager.playback_file("drone_detection.npy")

# Read file directly
samples, info = await manager.read_file("recording.iq")

# Method 2: Use individual components
from infrastructure.signal_io import (
    create_mock_stream,
    create_recorder,
    create_playback_engine,
    read_iq_file
)

# Stream only
stream = create_mock_stream(2.4e6)
await stream.start()

# Record only
recorder = create_recorder()
await recorder.start_recording()
await recorder.write_samples(samples)
await recorder.stop_recording()

# Playback only
engine = create_playback_engine()
engine.add_file("recording.iq")
await engine.play()

# Read only
samples, info = await read_iq_file("recording.iq")