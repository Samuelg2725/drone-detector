#!/usr/bin/env python3
# drone-detector/infrastructure/signal_io/file_reader.py
"""
IQ File Reader Module

This module provides comprehensive file reading capabilities for various IQ file formats,
supporting:
- Multiple file format detection and reading
- Format conversion utilities
- Metadata extraction
- Chunked reading for large files
- Memory-mapped file access
- Format validation and error handling
- Batch file processing
- Format auto-detection
- Streaming reads for real-time processing

Supported formats:
- RAW Binary (.iq, .bin, .raw, .cfile)
- NumPy (.npy)
- HDF5 (.h5, .hdf5)
- Compressed formats (.zst, .gz, .bz2, .lz4)
- SigMF (.sigmf)
- GNURadio (.cfile)
- UHD (.dat)
- CSV/Text (.csv, .txt)
- WAV (.wav)
- RF64 (.rf64)
- SCP (.scp)
"""

import asyncio
import gzip
import bz2
import struct
import json
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, List, Callable, Dict, Any, Union, Tuple, BinaryIO, Iterator
from collections import defaultdict

import numpy as np

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
    import lz4.frame
    LZ4_AVAILABLE = True
except ImportError:
    LZ4_AVAILABLE = False

try:
    import soundfile as sf
    SF_AVAILABLE = True
except ImportError:
    SF_AVAILABLE = False

try:
    import sigmf
    SIGMF_AVAILABLE = True
except ImportError:
    SIGMF_AVAILABLE = False

# Setup logging
import logging
logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Data Classes
# ============================================================================

class IQFileFormat(Enum):
    """Supported IQ file formats"""
    RAW_BINARY = "raw_binary"
    NUMPY = "numpy"
    HDF5 = "hdf5"
    ZSTD = "zstd"
    GZIP = "gzip"
    BZIP2 = "bzip2"
    LZ4 = "lz4"
    SIGMF = "sigmf"
    GNU_RADIO = "gnu_radio"
    UHD = "uhd"
    CSV = "csv"
    WAV = "wav"
    RF64 = "rf64"
    SCP = "scp"
    UNKNOWN = "unknown"


class SampleType(Enum):
    """IQ sample data types"""
    COMPLEX64 = np.complex64
    COMPLEX128 = np.complex128
    INT16 = np.int16
    INT32 = np.int32
    FLOAT32 = np.float32
    FLOAT64 = np.float64


@dataclass
class IQFileInfo:
    """Information about an IQ file"""
    file_path: Path
    format: IQFileFormat
    sample_rate: float = 0.0
    center_freq: float = 0.0
    num_samples: int = 0
    duration_seconds: float = 0.0
    data_type: SampleType = SampleType.COMPLEX64
    sample_size_bytes: int = 16
    compressed: bool = False
    compression_ratio: float = 1.0
    has_metadata: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.num_samples > 0 and self.sample_rate > 0:
            self.duration_seconds = self.num_samples / self.sample_rate
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'file_path': str(self.file_path),
            'format': self.format.value,
            'sample_rate': self.sample_rate,
            'center_freq': self.center_freq,
            'num_samples': self.num_samples,
            'duration_seconds': self.duration_seconds,
            'data_type': str(self.data_type.value),
            'sample_size_bytes': self.sample_size_bytes,
            'compressed': self.compressed,
            'has_metadata': self.has_metadata
        }


@dataclass
class ReadConfig:
    """Configuration for file reading"""
    chunk_size: int = 16384  # Samples per chunk
    use_mmap: bool = False   # Use memory mapping for large files
    validate_checksum: bool = True
    load_metadata: bool = True
    max_file_size_mb: int = 4096  # Maximum file size to load (0 = unlimited)
    sample_offset: int = 0  # Starting sample offset
    sample_limit: int = 0   # Maximum samples to read (0 = all)


# ============================================================================
# Base Reader Class
# ============================================================================

class IQFileReader(ABC):
    """Abstract base class for IQ file readers"""
    
    def __init__(self, file_path: Path, config: Optional[ReadConfig] = None):
        """
        Initialize file reader
        
        Args:
            file_path: Path to the file
            config: Read configuration
        """
        self.file_path = Path(file_path)
        self.config = config or ReadConfig()
        self.file_info: Optional[IQFileInfo] = None
        self._file_handle: Optional[BinaryIO] = None
        self._position: int = 0
        
        if not self.file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Check file size
        file_size_mb = self.file_path.stat().st_size / (1024 * 1024)
        if self.config.max_file_size_mb > 0 and file_size_mb > self.config.max_file_size_mb:
            raise ValueError(f"File too large: {file_size_mb:.1f}MB > {self.config.max_file_size_mb}MB")
    
    @abstractmethod
    async def open(self) -> None:
        """Open the file for reading"""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close the file"""
        pass
    
    @abstractmethod
    async def read_chunk(self, num_samples: int) -> np.ndarray:
        """Read a chunk of samples"""
        pass
    
    @abstractmethod
    async def get_info(self) -> IQFileInfo:
        """Get file information"""
        pass
    
    async def seek(self, sample_index: int) -> bool:
        """
        Seek to a sample position
        
        Args:
            sample_index: Target sample index
            
        Returns:
            True if successful
        """
        self._position = max(0, min(sample_index, self.file_info.num_samples))
        return True
    
    def get_position(self) -> int:
        """Get current sample position"""
        return self._position
    
    async def read_all(self) -> np.ndarray:
        """Read all samples from the file"""
        chunks = []
        await self.seek(self.config.sample_offset)
        
        remaining = self.file_info.num_samples - self._position
        if self.config.sample_limit > 0:
            remaining = min(remaining, self.config.sample_limit)
        
        while remaining > 0:
            chunk_size = min(self.config.chunk_size, remaining)
            chunk = await self.read_chunk(chunk_size)
            if len(chunk) == 0:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        
        if chunks:
            return np.concatenate(chunks)
        return np.array([], dtype=np.complex64)
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.open()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()


# ============================================================================
# Format-Specific Readers
# ============================================================================

class RawBinaryReader(IQFileReader):
    """Reader for raw binary IQ files"""
    
    def __init__(self, file_path: Path, config: Optional[ReadConfig] = None,
                 data_type: SampleType = SampleType.COMPLEX64,
                 sample_rate: float = 0.0, center_freq: float = 0.0):
        """
        Initialize raw binary reader
        
        Args:
            file_path: Path to file
            config: Read configuration
            data_type: Sample data type
            sample_rate: Sample rate (required for info)
            center_freq: Center frequency (optional)
        """
        super().__init__(file_path, config)
        self.data_type = data_type
        self.external_sample_rate = sample_rate
        self.external_center_freq = center_freq
        self._mmap = None
    
    async def open(self) -> None:
        """Open raw binary file"""
        if self.config.use_mmap:
            import mmap
            self._file_handle = open(self.file_path, 'rb')
            self._mmap = mmap.mmap(self._file_handle.fileno(), 0, access=mmap.ACCESS_READ)
        else:
            self._file_handle = open(self.file_path, 'rb')
        
        self.file_info = await self.get_info()
    
    async def close(self) -> None:
        """Close file"""
        if self._mmap:
            self._mmap.close()
        if self._file_handle:
            self._file_handle.close()
    
    async def read_chunk(self, num_samples: int) -> np.ndarray:
        """Read a chunk of samples"""
        sample_bytes = self._get_sample_bytes()
        bytes_to_read = num_samples * sample_bytes
        
        if self._mmap:
            start = self._position * sample_bytes
            data = self._mmap[start:start + bytes_to_read]
        else:
            self._file_handle.seek(self._position * sample_bytes)
            data = await asyncio.get_event_loop().run_in_executor(
                None, self._file_handle.read, bytes_to_read
            )
        
        if not data:
            return np.array([], dtype=np.complex64)
        
        samples = self._parse_samples(data)
        self._position += len(samples)
        
        return samples
    
    async def get_info(self) -> IQFileInfo:
        """Get file information"""
        file_size = self.file_path.stat().st_size
        sample_bytes = self._get_sample_bytes()
        num_samples = file_size // sample_bytes
        
        return IQFileInfo(
            file_path=self.file_path,
            format=IQFileFormat.RAW_BINARY,
            sample_rate=self.external_sample_rate,
            center_freq=self.external_center_freq,
            num_samples=num_samples,
            data_type=self.data_type,
            sample_size_bytes=sample_bytes
        )
    
    def _get_sample_bytes(self) -> int:
        """Get bytes per sample"""
        type_bytes = {
            SampleType.COMPLEX64: 16,
            SampleType.COMPLEX128: 32,
            SampleType.INT16: 4,  # I,Q each 2 bytes
            SampleType.INT32: 8,  # I,Q each 4 bytes
            SampleType.FLOAT32: 8,  # I,Q each 4 bytes
            SampleType.FLOAT64: 16  # I,Q each 8 bytes
        }
        return type_bytes.get(self.data_type, 16)
    
    def _parse_samples(self, data: bytes) -> np.ndarray:
        """Parse raw bytes to complex samples"""
        if self.data_type == SampleType.COMPLEX64:
            return np.frombuffer(data, dtype=np.complex64)
        
        elif self.data_type == SampleType.COMPLEX128:
            return np.frombuffer(data, dtype=np.complex128)
        
        elif self.data_type == SampleType.INT16:
            arr = np.frombuffer(data, dtype=np.int16)
            return (arr[0::2] + 1j * arr[1::2]).astype(np.complex64) / 32768.0
        
        elif self.data_type == SampleType.INT32:
            arr = np.frombuffer(data, dtype=np.int32)
            return (arr[0::2] + 1j * arr[1::2]).astype(np.complex64) / 2147483648.0
        
        elif self.data_type == SampleType.FLOAT32:
            arr = np.frombuffer(data, dtype=np.float32)
            return (arr[0::2] + 1j * arr[1::2]).astype(np.complex64)
        
        elif self.data_type == SampleType.FLOAT64:
            arr = np.frombuffer(data, dtype=np.float64)
            return (arr[0::2] + 1j * arr[1::2]).astype(np.complex128)
        
        else:
            return np.frombuffer(data, dtype=np.complex64)


class NumPyReader(IQFileReader):
    """Reader for NumPy .npy files"""
    
    async def open(self) -> None:
        """Open NumPy file"""
        if self.config.use_mmap:
            self._data = np.load(self.file_path, mmap_mode='r')
        else:
            self._data = np.load(self.file_path)
        
        self.file_info = await self.get_info()
    
    async def close(self) -> None:
        """Close file"""
        self._data = None
    
    async def read_chunk(self, num_samples: int) -> np.ndarray:
        """Read a chunk of samples"""
        end = min(self._position + num_samples, self.file_info.num_samples)
        samples = self._data[self._position:end]
        self._position = end
        return samples
    
    async def get_info(self) -> IQFileInfo:
        """Get file information"""
        # Load metadata if available
        metadata = {}
        sample_rate = 0.0
        center_freq = 0.0
        
        if self.config.load_metadata:
            if hasattr(self._data, 'attrs'):
                metadata = dict(self._data.attrs)
                sample_rate = metadata.get('sample_rate', 0.0)
                center_freq = metadata.get('center_freq', 0.0)
        
        # Determine data type
        dtype = self._data.dtype
        if dtype == np.complex64:
            sample_type = SampleType.COMPLEX64
        elif dtype == np.complex128:
            sample_type = SampleType.COMPLEX128
        else:
            sample_type = SampleType.COMPLEX64
        
        return IQFileInfo(
            file_path=self.file_path,
            format=IQFileFormat.NUMPY,
            sample_rate=sample_rate,
            center_freq=center_freq,
            num_samples=len(self._data),
            data_type=sample_type,
            sample_size_bytes=self._data.itemsize,
            has_metadata=bool(metadata),
            metadata=metadata
        )


class HDF5Reader(IQFileReader):
    """Reader for HDF5 files"""
    
    async def open(self) -> None:
        """Open HDF5 file"""
        if not H5PY_AVAILABLE:
            raise RuntimeError("h5py not available. Install with: pip install h5py")
        
        self._file = h5py.File(self.file_path, 'r')
        
        # Find IQ dataset (common names)
        iq_dataset_names = ['iq_data', 'data', 'samples', 'I/Q', 'complex']
        self._dataset = None
        
        for name in iq_dataset_names:
            if name in self._file:
                self._dataset = self._file[name]
                break
        
        if self._dataset is None:
            # Try to find any dataset
            for key in self._file.keys():
                if isinstance(self._file[key], h5py.Dataset):
                    self._dataset = self._file[key]
                    break
        
        if self._dataset is None:
            raise ValueError("No IQ dataset found in HDF5 file")
        
        self.file_info = await self.get_info()
    
    async def close(self) -> None:
        """Close HDF5 file"""
        if self._file:
            self._file.close()
    
    async def read_chunk(self, num_samples: int) -> np.ndarray:
        """Read a chunk of samples"""
        end = min(self._position + num_samples, self.file_info.num_samples)
        samples = self._dataset[self._position:end]
        self._position = end
        return samples
    
    async def get_info(self) -> IQFileInfo:
        """Get file information"""
        # Extract metadata from attributes
        metadata = dict(self._file.attrs)
        sample_rate = metadata.get('sample_rate', 0.0)
        center_freq = metadata.get('center_freq', 0.0)
        
        # Try to get from dataset attributes
        if hasattr(self._dataset, 'attrs'):
            metadata.update(dict(self._dataset.attrs))
            sample_rate = metadata.get('sample_rate', sample_rate)
            center_freq = metadata.get('center_freq', center_freq)
        
        # Determine data type
        dtype = self._dataset.dtype
        if dtype == np.complex64:
            sample_type = SampleType.COMPLEX64
        elif dtype == np.complex128:
            sample_type = SampleType.COMPLEX128
        else:
            sample_type = SampleType.COMPLEX64
        
        return IQFileInfo(
            file_path=self.file_path,
            format=IQFileFormat.HDF5,
            sample_rate=sample_rate,
            center_freq=center_freq,
            num_samples=self._dataset.shape[0],
            data_type=sample_type,
            sample_size_bytes=self._dataset.dtype.itemsize,
            has_metadata=True,
            metadata=metadata
        )


class CompressedReader(IQFileReader):
    """Reader for compressed IQ files (zstd, gzip, bz2, lz4)"""
    
    def __init__(self, file_path: Path, config: Optional[ReadConfig] = None,
                 compression_format: Optional[IQFileFormat] = None):
        """
        Initialize compressed reader
        
        Args:
            file_path: Path to compressed file
            config: Read configuration
            compression_format: Compression format (auto-detected if None)
        """
        super().__init__(file_path, config)
        self.compression_format = compression_format or self._detect_compression()
        self._data = None
        self._samples = None
    
    def _detect_compression(self) -> IQFileFormat:
        """Detect compression format from extension"""
        suffix = self.file_path.suffix.lower()
        
        format_map = {
            '.zst': IQFileFormat.ZSTD,
            '.gz': IQFileFormat.GZIP,
            '.gzip': IQFileFormat.GZIP,
            '.bz2': IQFileFormat.BZIP2,
            '.lz4': IQFileFormat.LZ4
        }
        
        return format_map.get(suffix, IQFileFormat.UNKNOWN)
    
    async def open(self) -> None:
        """Open and decompress file"""
        if self.compression_format == IQFileFormat.ZSTD:
            await self._decompress_zstd()
        elif self.compression_format == IQFileFormat.GZIP:
            await self._decompress_gzip()
        elif self.compression_format == IQFileFormat.BZIP2:
            await self._decompress_bzip2()
        elif self.compression_format == IQFileFormat.LZ4:
            await self._decompress_lz4()
        else:
            raise ValueError(f"Unsupported compression format: {self.compression_format}")
        
        self.file_info = await self.get_info()
    
    async def _decompress_zstd(self) -> None:
        """Decompress Zstandard file"""
        if not ZSTD_AVAILABLE:
            raise RuntimeError("zstandard not available. Install with: pip install zstandard")
        
        with open(self.file_path, 'rb') as f:
            # Read header (original size)
            header = await asyncio.get_event_loop().run_in_executor(None, f.read, 8)
            if len(header) == 8:
                original_size = struct.unpack('<Q', header)[0]
                compressed = await asyncio.get_event_loop().run_in_executor(None, f.read)
                
                decompressor = zstd.ZstdDecompressor()
                self._data = decompressor.decompress(compressed, max_output_size=original_size)
                self._samples = np.frombuffer(self._data, dtype=np.complex64)
    
    async def _decompress_gzip(self) -> None:
        """Decompress GZIP file"""
        with gzip.open(self.file_path, 'rb') as f:
            self._data = await asyncio.get_event_loop().run_in_executor(None, f.read)
            self._samples = np.frombuffer(self._data, dtype=np.complex64)
    
    async def _decompress_bzip2(self) -> None:
        """Decompress BZIP2 file"""
        with bz2.open(self.file_path, 'rb') as f:
            self._data = await asyncio.get_event_loop().run_in_executor(None, f.read)
            self._samples = np.frombuffer(self._data, dtype=np.complex64)
    
    async def _decompress_lz4(self) -> None:
        """Decompress LZ4 file"""
        if not LZ4_AVAILABLE:
            raise RuntimeError("lz4 not available. Install with: pip install lz4")
        
        with open(self.file_path, 'rb') as f:
            compressed = await asyncio.get_event_loop().run_in_executor(None, f.read)
            self._data = lz4.frame.decompress(compressed)
            self._samples = np.frombuffer(self._data, dtype=np.complex64)
    
    async def close(self) -> None:
        """Close file"""
        self._data = None
        self._samples = None
    
    async def read_chunk(self, num_samples: int) -> np.ndarray:
        """Read a chunk of samples"""
        if self._samples is None:
            return np.array([], dtype=np.complex64)
        
        end = min(self._position + num_samples, len(self._samples))
        samples = self._samples[self._position:end].copy()
        self._position = end
        return samples
    
    async def get_info(self) -> IQFileInfo:
        """Get file information"""
        if self._samples is None:
            return IQFileInfo(
                file_path=self.file_path,
                format=self.compression_format,
                num_samples=0
            )
        
        original_size = len(self._data) if self._data else 0
        compressed_size = self.file_path.stat().st_size
        
        return IQFileInfo(
            file_path=self.file_path,
            format=self.compression_format,
            num_samples=len(self._samples),
            data_type=SampleType.COMPLEX64,
            sample_size_bytes=16,
            compressed=True,
            compression_ratio=original_size / compressed_size if compressed_size > 0 else 1.0
        )


class SigMFReader(IQFileReader):
    """Reader for SigMF (Signal Metadata Format) files"""
    
    async def open(self) -> None:
        """Open SigMF file"""
        if not SIGMF_AVAILABLE:
            raise RuntimeError("sigmf not available. Install with: pip install sigmf")
        
        self._sigmf = sigmf.sigmffile.fromfile(str(self.file_path))
        self.file_info = await self.get_info()
    
    async def close(self) -> None:
        """Close file"""
        self._sigmf = None
    
    async def read_chunk(self, num_samples: int) -> np.ndarray:
        """Read a chunk of samples"""
        samples = self._sigmf.read_samples(
            start_index=self._position,
            length=min(num_samples, self.file_info.num_samples - self._position)
        )
        self._position += len(samples)
        return samples
    
    async def get_info(self) -> IQFileInfo:
        """Get file information"""
        annotations = self._sigmf.get_annotations()
        
        return IQFileInfo(
            file_path=self.file_path,
            format=IQFileFormat.SIGMF,
            sample_rate=self._sigmf.get_global_field('core:sample_rate'),
            center_freq=self._sigmf.get_capture_info(0).get('core:frequency', 0),
            num_samples=self._sigmf.sample_count,
            data_type=SampleType.COMPLEX64,
            sample_size_bytes=16,
            has_metadata=True,
            metadata={
                'annotations': annotations,
                'captures': self._sigmf.get_captures(),
                'global': self._sigmf.get_global_info()
            }
        )


class CSVReader(IQFileReader):
    """Reader for CSV files with I/Q columns"""
    
    async def open(self) -> None:
        """Open CSV file"""
        self._data = np.loadtxt(self.file_path, delimiter=',')
        
        if self._data.ndim == 1:
            # Single column treated as real
            self._samples = self._data.astype(np.complex64)
        elif self._data.shape[1] >= 2:
            # Two or more columns: I and Q
            self._samples = (self._data[:, 0] + 1j * self._data[:, 1]).astype(np.complex64)
        else:
            self._samples = self._data.astype(np.complex64)
        
        self.file_info = await self.get_info()
    
    async def close(self) -> None:
        """Close file"""
        self._samples = None
        self._data = None
    
    async def read_chunk(self, num_samples: int) -> np.ndarray:
        """Read a chunk of samples"""
        end = min(self._position + num_samples, self.file_info.num_samples)
        samples = self._samples[self._position:end]
        self._position = end
        return samples
    
    async def get_info(self) -> IQFileInfo:
        """Get file information"""
        # Try to parse header for metadata
        metadata = {}
        try:
            with open(self.file_path, 'r') as f:
                first_line = f.readline().strip()
                if first_line.startswith('#'):
                    # Comment line with metadata
                    metadata = json.loads(first_line[1:])
        except:
            pass
        
        sample_rate = metadata.get('sample_rate', 0.0)
        center_freq = metadata.get('center_freq', 0.0)
        
        return IQFileInfo(
            file_path=self.file_path,
            format=IQFileFormat.CSV,
            sample_rate=sample_rate,
            center_freq=center_freq,
            num_samples=len(self._samples),
            data_type=SampleType.COMPLEX64,
            sample_size_bytes=16,
            has_metadata=bool(metadata),
            metadata=metadata
        )


class WAVReader(IQFileReader):
    """Reader for WAV audio files (extracts I/Q from stereo)"""
    
    async def open(self) -> None:
        """Open WAV file"""
        if not SF_AVAILABLE:
            raise RuntimeError("soundfile not available. Install with: pip install soundfile")
        
        self._data, self._sample_rate = sf.read(self.file_path)
        
        if self._data.ndim == 1:
            # Mono - use as real part
            self._samples = self._data.astype(np.complex64)
        elif self._data.shape[1] == 2:
            # Stereo - treat as I/Q
            self._samples = (self._data[:, 0] + 1j * self._data[:, 1]).astype(np.complex64)
        else:
            # Multi-channel - use first two as I/Q
            self._samples = (self._data[:, 0] + 1j * self._data[:, 1]).astype(np.complex64)
        
        self.file_info = await self.get_info()
    
    async def close(self) -> None:
        """Close file"""
        self._samples = None
        self._data = None
    
    async def read_chunk(self, num_samples: int) -> np.ndarray:
        """Read a chunk of samples"""
        end = min(self._position + num_samples, self.file_info.num_samples)
        samples = self._samples[self._position:end]
        self._position = end
        return samples
    
    async def get_info(self) -> IQFileInfo:
        """Get file information"""
        # Try to read metadata from WAV chunk
        metadata = {}
        
        return IQFileInfo(
            file_path=self.file_path,
            format=IQFileFormat.WAV,
            sample_rate=self._sample_rate,
            num_samples=len(self._samples),
            data_type=SampleType.COMPLEX64,
            sample_size_bytes=16,
            has_metadata=bool(metadata),
            metadata=metadata
        )


class GNURadioReader(RawBinaryReader):
    """Reader for GNURadio .cfile files"""
    
    async def get_info(self) -> IQFileInfo:
        """Get file information"""
        info = await super().get_info()
        info.format = IQFileFormat.GNU_RADIO
        return info


class UHDReader(RawBinaryReader):
    """Reader for UHD .dat files"""
    
    async def get_info(self) -> IQFileInfo:
        """Get file information"""
        info = await super().get_info()
        info.format = IQFileFormat.UHD
        
        # Try to read metadata from companion file
        metadata_file = self.file_path.with_suffix('.json')
        if metadata_file.exists():
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
                info.sample_rate = metadata.get('sample_rate', info.sample_rate)
                info.center_freq = metadata.get('center_freq', info.center_freq)
                info.metadata = metadata
                info.has_metadata = True
        
        return info


# ============================================================================
# File Reader Factory
# ============================================================================

class IQFileReaderFactory:
    """Factory for creating appropriate file readers"""
    
    @staticmethod
    def get_reader(file_path: Path, config: Optional[ReadConfig] = None,
                   **kwargs) -> IQFileReader:
        """
        Get appropriate reader for file
        
        Args:
            file_path: Path to file
            config: Read configuration
            **kwargs: Additional format-specific arguments
            
        Returns:
            Appropriate IQFileReader instance
        """
        format = IQFileReaderFactory.detect_format(file_path)
        
        if format == IQFileFormat.RAW_BINARY:
            return RawBinaryReader(file_path, config, **kwargs)
        elif format == IQFileFormat.NUMPY:
            return NumPyReader(file_path, config)
        elif format == IQFileFormat.HDF5:
            return HDF5Reader(file_path, config)
        elif format in [IQFileFormat.ZSTD, IQFileFormat.GZIP, 
                        IQFileFormat.BZIP2, IQFileFormat.LZ4]:
            return CompressedReader(file_path, config, compression_format=format)
        elif format == IQFileFormat.SIGMF:
            return SigMFReader(file_path, config)
        elif format == IQFileFormat.CSV:
            return CSVReader(file_path, config)
        elif format == IQFileFormat.WAV:
            return WAVReader(file_path, config)
        elif format == IQFileFormat.GNU_RADIO:
            return GNURadioReader(file_path, config, **kwargs)
        elif format == IQFileFormat.UHD:
            return UHDReader(file_path, config, **kwargs)
        else:
            # Try raw binary as fallback
            return RawBinaryReader(file_path, config, **kwargs)
    
    @staticmethod
    def detect_format(file_path: Path) -> IQFileFormat:
        """
        Detect file format from extension and content
        
        Args:
            file_path: Path to file
            
        Returns:
            Detected format
        """
        suffix = file_path.suffix.lower()
        
        # Extension-based detection
        format_map = {
            '.iq': IQFileFormat.RAW_BINARY,
            '.bin': IQFileFormat.RAW_BINARY,
            '.raw': IQFileFormat.RAW_BINARY,
            '.cfile': IQFileFormat.GNU_RADIO,
            '.dat': IQFileFormat.UHD,
            '.npy': IQFileFormat.NUMPY,
            '.h5': IQFileFormat.HDF5,
            '.hdf5': IQFileFormat.HDF5,
            '.zst': IQFileFormat.ZSTD,
            '.gz': IQFileFormat.GZIP,
            '.bz2': IQFileFormat.BZIP2,
            '.lz4': IQFileFormat.LZ4,
            '.sigmf': IQFileFormat.SIGMF,
            '.csv': IQFileFormat.CSV,
            '.txt': IQFileFormat.CSV,
            '.wav': IQFileFormat.WAV,
            '.rf64': IQFileFormat.RF64,
            '.scp': IQFileFormat.SCP
        }
        
        if suffix in format_map:
            return format_map[suffix]
        
        # Content-based detection
        with open(file_path, 'rb') as f:
            header = f.read(20)
            
            # Check for NumPy magic number
            if header[:6] == b'\x93NUMPY':
                return IQFileFormat.NUMPY
            
            # Check for HDF5 magic
            if header[:8] == b'\x89HDF\r\n\x1a\n':
                return IQFileFormat.HDF5
            
            # Check for SigMF
            if header[:4] == b'SIGM':
                return IQFileFormat.SIGMF
            
            # Check for WAV
            if header[:4] == b'RIFF' and header[8:12] == b'WAVE':
                return IQFileFormat.WAV
        
        return IQFileFormat.UNKNOWN


# ============================================================================
# Batch File Processor
# ============================================================================

class BatchIQReader:
    """
    Batch processor for multiple IQ files
    
    Features:
    - Process multiple files sequentially
    - Automatic format detection
    - Parallel processing support
    - Progress tracking
    """
    
    def __init__(self, config: Optional[ReadConfig] = None):
        """
        Initialize batch reader
        
        Args:
            config: Read configuration
        """
        self.config = config or ReadConfig()
        self.files: List[Path] = []
        self.results: List[Dict[str, Any]] = []
    
    def add_file(self, file_path: Union[str, Path]) -> None:
        """Add a file to the batch"""
        self.files.append(Path(file_path))
    
    def add_directory(self, directory: Union[str, Path], pattern: str = "*") -> None:
        """Add all matching files from directory"""
        dir_path = Path(directory)
        for file_path in dir_path.glob(pattern):
            self.files.append(file_path)
    
    async def process_all(self, processor: Optional[Callable] = None) -> List[Dict[str, Any]]:
        """
        Process all files in batch
        
        Args:
            processor: Optional processing function for each file
            
        Returns:
            List of processing results
        """
        self.results = []
        
        for i, file_path in enumerate(self.files):
            logger.info(f"Processing file {i+1}/{len(self.files)}: {file_path.name}")
            
            try:
                reader = IQFileReaderFactory.get_reader(file_path, self.config)
                
                async with reader:
                    info = await reader.get_info()
                    
                    if processor:
                        result = await processor(reader, info)
                    else:
                        result = await reader.read_all()
                    
                    self.results.append({
                        'file': str(file_path),
                        'info': info.to_dict(),
                        'result': result
                    })
                    
            except Exception as e:
                logger.error(f"Failed to process {file_path}: {e}")
                self.results.append({
                    'file': str(file_path),
                    'error': str(e)
                })
        
        return self.results


# ============================================================================
# Utility Functions
# ============================================================================

async def read_iq_file(file_path: Union[str, Path], 
                      sample_rate: Optional[float] = None,
                      center_freq: Optional[float] = None,
                      sample_limit: int = 0) -> Tuple[np.ndarray, IQFileInfo]:
    """
    Convenience function to read an IQ file
    
    Args:
        file_path: Path to file
        sample_rate: Sample rate (for formats without metadata)
        center_freq: Center frequency (optional)
        sample_limit: Maximum samples to read (0 = all)
        
    Returns:
        Tuple of (samples, file_info)
    """
    config = ReadConfig(sample_limit=sample_limit)
    
    kwargs = {}
    if sample_rate:
        kwargs['sample_rate'] = sample_rate
    if center_freq:
        kwargs['center_freq'] = center_freq
    
    reader = IQFileReaderFactory.get_reader(Path(file_path), config, **kwargs)
    
    async with reader:
        samples = await reader.read_all()
        info = await reader.get_info()
    
    return samples, info


def get_file_info(file_path: Union[str, Path]) -> IQFileInfo:
    """
    Get file information without reading data
    
    Args:
        file_path: Path to file
        
    Returns:
        File information
    """
    path = Path(file_path)
    format = IQFileReaderFactory.detect_format(path)
    
    return IQFileInfo(
        file_path=path,
        format=format,
        num_samples=0,
        modified_at=datetime.fromtimestamp(path.stat().st_mtime),
        created_at=datetime.fromtimestamp(path.stat().st_ctime)
    )


async def convert_iq_format(input_path: Union[str, Path],
                           output_path: Union[str, Path],
                           output_format: IQFileFormat,
                           sample_rate: float = 0.0,
                           **kwargs) -> bool:
    """
    Convert IQ file to another format
    
    Args:
        input_path: Source file path
        output_path: Destination file path
        output_format: Target format
        sample_rate: Sample rate (if not in metadata)
        **kwargs: Additional format-specific arguments
        
    Returns:
        True if conversion successful
    """
    # Read source file
    samples, info = await read_iq_file(input_path, sample_rate=sample_rate)
    
    # Write to target format
    if output_format == IQFileFormat.NUMPY:
        np.save(output_path, samples)
        if hasattr(np.save, 'attrs'):
            # Add metadata if possible
            pass
    
    elif output_format == IQFileFormat.RAW_BINARY:
        samples.astype(np.complex64).tofile(output_path)
    
    elif output_format == IQFileFormat.CSV:
        iq_array = np.column_stack((samples.real, samples.imag))
        np.savetxt(output_path, iq_array, delimiter=',',
                  header=f"# {{'sample_rate': {info.sample_rate}, 'center_freq': {info.center_freq}}}")
    
    else:
        raise ValueError(f"Unsupported output format: {output_format}")
    
    logger.info(f"Converted {input_path} to {output_path} ({output_format.value})")
    return True


# ============================================================================
# Example Usage
# ============================================================================

async def example_read_raw():
    """Example of reading raw binary file"""
    print("Raw Binary File Read Example")
    print("-" * 30)
    
    # Create reader
    reader = RawBinaryReader(
        Path("data/iq/sample.iq"),
        sample_rate=2.4e6,
        center_freq=2.44e9
    )
    
    async with reader:
        info = await reader.get_info()
        print(f"File info: {info.to_dict()}")
        
        # Read all samples
        samples = await reader.read_all()
        print(f"Read {len(samples)} samples")
        
        # Or read in chunks
        await reader.seek(0)
        chunk = await reader.read_chunk(1024)
        print(f"Read chunk: {len(chunk)} samples")


async def example_auto_detect():
    """Example of auto-detecting file format"""
    print("\nAuto-Detection Example")
    print("-" * 30)
    
    # Detect format
    format = IQFileReaderFactory.detect_format(Path("data/iq/sample.npy"))
    print(f"Detected format: {format.value}")
    
    # Get appropriate reader
    reader = IQFileReaderFactory.get_reader(Path("data/iq/sample.npy"))
    
    async with reader:
        info = await reader.get_info()
        print(f"File info: {info.to_dict()}")


async def example_batch_process():
    """Example of batch processing"""
    print("\nBatch Processing Example")
    print("-" * 30)
    
    batch = BatchIQReader()
    batch.add_directory("data/iq/replay", pattern="*.iq")
    
    def process_samples(reader, info):
        return len(reader._data) if hasattr(reader, '_data') else 0
    
    results = await batch.process_all(process_samples)
    
    for result in results:
        print(f"{result['file']}: {result.get('result', 'error')}")


async def example_convert():
    """Example of format conversion"""
    print("\nFormat Conversion Example")
    print("-" * 30)
    
    # Convert from raw to NumPy
    await convert_iq_format(
        "data/iq/sample.iq",
        "data/iq/sample.npy",
        IQFileFormat.NUMPY,
        sample_rate=2.4e6
    )
    
    # Convert to CSV
    await convert_iq_format(
        "data/iq/sample.npy",
        "data/iq/sample.csv",
        IQFileFormat.CSV
    )


async def main():
    """Main example"""
    print("IQ File Reader Test")
    print("=" * 50)
    
    # Run examples
    await example_read_raw()
    await example_auto_detect()
    await example_batch_process()
    await example_convert()
    
    print("\n" + "=" * 50)
    print("IQ File Reader test complete!")


if __name__ == "__main__":
    asyncio.run(main())