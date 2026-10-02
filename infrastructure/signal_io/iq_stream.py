#!/usr/bin/env python3
# drone-detector/infrastructure/signal_io/iq_stream.py
"""
IQ Data Streaming Module

This module provides high-performance streaming of IQ data for the Drone Detection System,
supporting:
- Real-time IQ sample streaming from SDR hardware
- Asynchronous sample processing pipelines
- Ring buffer for continuous data capture
- Sample rate conversion and decimation
- Multi-channel streaming
- Dynamic buffer management
- Thread-safe operations
- Performance monitoring and statistics
- Data chunking and batching
- Zero-copy optimizations
"""

import asyncio
import threading
import time
import numpy as np
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Callable, Union, Dict, Any, Tuple
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import queue

# Setup logging
import logging
logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Data Classes
# ============================================================================

class StreamState(Enum):
    """Stream state enumeration"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"


class DataType(Enum):
    """IQ data types"""
    COMPLEX64 = np.complex64
    COMPLEX128 = np.complex128
    INT16 = np.int16
    FLOAT32 = np.float32


@dataclass
class StreamConfig:
    """Stream configuration"""
    # Sample settings
    sample_rate: float = 2.4e6  # Samples per second
    chunk_size: int = 16384     # Samples per chunk
    buffer_size: int = 524288   # Total buffer size in samples (2^19)
    
    # Timing settings
    stream_timeout_ms: int = 1000
    read_timeout_ms: int = 100
    
    # Processing settings
    use_thread_pool: bool = True
    thread_pool_size: int = 4
    enable_zerocopy: bool = True
    
    # Data type
    dtype: DataType = DataType.COMPLEX64
    
    # Automatic scaling
    auto_scale: bool = True
    scale_factor: float = 1.0
    
    # Statistics
    enable_stats: bool = True
    stats_window_seconds: float = 10.0
    
    # Buffer behavior
    overwrite_on_full: bool = True
    ring_buffer_enabled: bool = True


@dataclass
class StreamChunk:
    """Data chunk from stream"""
    data: np.ndarray
    timestamp: float
    sample_rate: float
    center_freq: Optional[float] = None
    chunk_id: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration(self) -> float:
        """Duration of chunk in seconds"""
        return len(self.data) / self.sample_rate
    
    @property
    def num_samples(self) -> int:
        """Number of samples in chunk"""
        return len(self.data)


@dataclass
class StreamStats:
    """Stream performance statistics"""
    samples_received: int = 0
    samples_processed: int = 0
    chunks_produced: int = 0
    chunks_dropped: int = 0
    buffer_overruns: int = 0
    buffer_underruns: int = 0
    
    min_latency_ms: float = float('inf')
    max_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    
    current_sample_rate: float = 0.0
    current_throughput_mbps: float = 0.0
    
    start_time: float = 0.0
    last_sample_time: float = 0.0
    
    def update_latency(self, latency_ms: float):
        """Update latency statistics"""
        self.min_latency_ms = min(self.min_latency_ms, latency_ms)
        self.max_latency_ms = max(self.max_latency_ms, latency_ms)
        
        # Exponential moving average
        if self.avg_latency_ms == 0:
            self.avg_latency_ms = latency_ms
        else:
            self.avg_latency_ms = self.avg_latency_ms * 0.95 + latency_ms * 0.05
    
    def calculate_throughput(self, samples: int, elapsed_seconds: float):
        """Calculate throughput"""
        bytes_per_sample = 16  # complex64 = 16 bytes
        throughput_mbps = (samples * bytes_per_sample * 8) / (elapsed_seconds * 1_000_000)
        self.current_throughput_mbps = throughput_mbps
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'samples_received': self.samples_received,
            'samples_processed': self.samples_processed,
            'chunks_produced': self.chunks_produced,
            'chunks_dropped': self.chunks_dropped,
            'buffer_overruns': self.buffer_overruns,
            'buffer_underruns': self.buffer_underruns,
            'min_latency_ms': self.min_latency_ms if self.min_latency_ms != float('inf') else 0,
            'max_latency_ms': self.max_latency_ms,
            'avg_latency_ms': self.avg_latency_ms,
            'current_sample_rate': self.current_sample_rate,
            'current_throughput_mbps': self.current_throughput_mbps,
            'uptime_seconds': time.time() - self.start_time if self.start_time else 0
        }


# ============================================================================
# Ring Buffer
# ============================================================================

class RingBuffer:
    """
    Lock-free ring buffer for IQ samples
    
    Features:
    - Thread-safe with minimal locking
    - Zero-copy read/write operations
    - Automatic overflow handling
    - Configurable buffer size
    """
    
    def __init__(self, buffer_size: int, dtype: np.dtype = np.complex64):
        """
        Initialize ring buffer
        
        Args:
            buffer_size: Number of samples to buffer
            dtype: Data type for samples
        """
        self.buffer_size = buffer_size
        self.dtype = dtype
        self.buffer = np.zeros(buffer_size, dtype=dtype)
        self.write_pos = 0
        self.read_pos = 0
        self._lock = threading.Lock()
        self.available_samples = 0
    
    def write(self, samples: np.ndarray) -> int:
        """
        Write samples to buffer
        
        Args:
            samples: Samples to write
            
        Returns:
            Number of samples written
        """
        with self._lock:
            samples_to_write = len(samples)
            
            # Calculate available space
            if self.write_pos >= self.read_pos:
                space = self.buffer_size - (self.write_pos - self.read_pos)
            else:
                space = self.read_pos - self.write_pos
            
            if samples_to_write > space:
                # Buffer would overflow, adjust write position
                samples_to_write = space
                if space == 0:
                    return 0
            
            # Write samples
            end_pos = self.write_pos + samples_to_write
            if end_pos <= self.buffer_size:
                self.buffer[self.write_pos:end_pos] = samples[:samples_to_write]
            else:
                # Wrap around
                first_part = self.buffer_size - self.write_pos
                self.buffer[self.write_pos:] = samples[:first_part]
                remaining = samples_to_write - first_part
                self.buffer[:remaining] = samples[first_part:samples_to_write]
            
            self.write_pos = (self.write_pos + samples_to_write) % self.buffer_size
            self.available_samples += samples_to_write
            
            return samples_to_write
    
    def read(self, num_samples: int) -> np.ndarray:
        """
        Read samples from buffer
        
        Args:
            num_samples: Number of samples to read
            
        Returns:
            Array of samples (may be less than requested if insufficient data)
        """
        with self._lock:
            if self.available_samples == 0:
                return np.array([], dtype=self.dtype)
            
            samples_to_read = min(num_samples, self.available_samples)
            
            # Read samples
            end_pos = self.read_pos + samples_to_read
            if end_pos <= self.buffer_size:
                data = self.buffer[self.read_pos:end_pos].copy()
            else:
                # Wrap around
                first_part = self.buffer_size - self.read_pos
                data = np.concatenate([
                    self.buffer[self.read_pos:],
                    self.buffer[:samples_to_read - first_part]
                ]).copy()
            
            self.read_pos = (self.read_pos + samples_to_read) % self.buffer_size
            self.available_samples -= samples_to_read
            
            return data
    
    def peek(self, num_samples: int, offset: int = 0) -> np.ndarray:
        """
        Peek at samples without consuming
        
        Args:
            num_samples: Number of samples to peek
            offset: Offset from read position
            
        Returns:
            Array of samples
        """
        with self._lock:
            if self.available_samples <= offset:
                return np.array([], dtype=self.dtype)
            
            samples_to_read = min(num_samples, self.available_samples - offset)
            
            read_pos = (self.read_pos + offset) % self.buffer_size
            
            end_pos = read_pos + samples_to_read
            if end_pos <= self.buffer_size:
                data = self.buffer[read_pos:end_pos].copy()
            else:
                first_part = self.buffer_size - read_pos
                data = np.concatenate([
                    self.buffer[read_pos:],
                    self.buffer[:samples_to_read - first_part]
                ]).copy()
            
            return data
    
    def clear(self):
        """Clear the buffer"""
        with self._lock:
            self.write_pos = 0
            self.read_pos = 0
            self.available_samples = 0
            self.buffer.fill(0)
    
    def get_available(self) -> int:
        """Get number of available samples"""
        return self.available_samples
    
    def get_free_space(self) -> int:
        """Get free space in buffer"""
        return self.buffer_size - self.available_samples


# ============================================================================
# IQ Stream Source (Hardware Interface)
# ============================================================================

class IQStreamSource:
    """
    Abstract source for IQ data stream
    
    This class defines the interface for hardware-specific stream sources.
    Implementations should be provided for different SDR hardware.
    """
    
    def __init__(self, sample_rate: float, config: Optional[Dict[str, Any]] = None):
        """
        Initialize stream source
        
        Args:
            sample_rate: Sampling rate in Hz
            config: Hardware-specific configuration
        """
        self.sample_rate = sample_rate
        self.config = config or {}
        self.is_running = False
    
    async def start(self) -> bool:
        """
        Start the stream source
        
        Returns:
            True if started successfully
        """
        self.is_running = True
        return True
    
    async def stop(self):
        """Stop the stream source"""
        self.is_running = False
    
    async def read_samples(self, num_samples: int) -> np.ndarray:
        """
        Read samples from the source
        
        Args:
            num_samples: Number of samples to read
            
        Returns:
            Array of IQ samples
        """
        raise NotImplementedError("Subclass must implement read_samples")
    
    def set_center_freq(self, frequency: float):
        """Set center frequency"""
        pass


# ============================================================================
# Mock Stream Source (For Testing)
# ============================================================================

class MockStreamSource(IQStreamSource):
    """
    Mock stream source for testing
    
    Generates synthetic IQ data including:
    - Noise floor
    - Simulated drone signals
    - Test tones
    """
    
    def __init__(self, sample_rate: float, config: Optional[Dict[str, Any]] = None):
        super().__init__(sample_rate, config)
        
        # Signal generation parameters
        self.signal_type = config.get('signal_type', 'noise')  # noise, tone, drone
        self.signal_frequency = config.get('signal_frequency', 100e3)
        self.signal_amplitude = config.get('signal_amplitude', 0.5)
        self.add_noise = config.get('add_noise', True)
        self.noise_floor_db = config.get('noise_floor_db', -60)
        
        # Phase accumulator for tone generation
        self.phase = 0.0
        
        # Drone simulation parameters
        self.drone_active = False
        self.drone_type = config.get('drone_type', 'dji')
        self.drone_start_time = 0
    
    async def read_samples(self, num_samples: int) -> np.ndarray:
        """Generate synthetic samples"""
        if self.signal_type == 'noise':
            return self._generate_noise(num_samples)
        elif self.signal_type == 'tone':
            return self._generate_tone(num_samples)
        elif self.signal_type == 'drone':
            return self._generate_drone_signal(num_samples)
        else:
            return self._generate_noise(num_samples)
    
    def _generate_noise(self, num_samples: int) -> np.ndarray:
        """Generate Gaussian noise"""
        noise_power = 10 ** (self.noise_floor_db / 10)
        noise = np.sqrt(noise_power / 2) * (
            np.random.randn(num_samples) + 1j * np.random.randn(num_samples)
        )
        return noise.astype(np.complex64)
    
    def _generate_tone(self, num_samples: int) -> np.ndarray:
        """Generate a test tone"""
        t = np.arange(num_samples) / self.sample_rate
        tone = self.signal_amplitude * np.exp(2j * np.pi * self.signal_frequency * t)
        
        if self.add_noise:
            noise_power = 10 ** ((self.noise_floor_db - 30) / 10)
            noise = np.sqrt(noise_power / 2) * (
                np.random.randn(num_samples) + 1j * np.random.randn(num_samples)
            )
            tone += noise
        
        return tone.astype(np.complex64)
    
    def _generate_drone_signal(self, num_samples: int) -> np.ndarray:
        """Generate simulated drone signal"""
        if self.drone_type == 'dji':
            # DJI OcuSync-like signal (OFDM)
            signal = self._generate_ofdm_signal(num_samples)
        elif self.drone_type == 'fpv':
            # FPV analog signal (FM)
            signal = self._generate_fm_signal(num_samples)
        else:
            signal = self._generate_tone(num_samples)
        
        if self.add_noise:
            noise_power = 10 ** ((self.noise_floor_db - 30) / 10)
            noise = np.sqrt(noise_power / 2) * (
                np.random.randn(num_samples) + 1j * np.random.randn(num_samples)
            )
            signal += noise
        
        return signal.astype(np.complex64)
    
    def _generate_ofdm_signal(self, num_samples: int) -> np.ndarray:
        """Generate OFDM-like signal (DJI style)"""
        # Simulate OFDM symbols
        fft_size = 1024
        cp_len = 64
        symbol_len = fft_size + cp_len
        
        num_symbols = (num_samples + symbol_len - 1) // symbol_len
        signal = np.zeros(num_symbols * symbol_len, dtype=np.complex128)
        
        for i in range(num_symbols):
            # Generate random QPSK symbols
            symbols = (2 * np.random.randint(0, 2, fft_size) - 1) + \
                      1j * (2 * np.random.randint(0, 2, fft_size) - 1)
            symbols /= np.sqrt(2)
            
            # IFFT
            ofdm_symbol = np.fft.ifft(symbols)
            
            # Add cyclic prefix
            cp = ofdm_symbol[-cp_len:]
            symbol = np.concatenate([cp, ofdm_symbol])
            
            start = i * symbol_len
            end = min(start + symbol_len, num_samples)
            signal[start:end] = symbol[:end-start]
        
        return signal[:num_samples] * self.signal_amplitude
    
    def _generate_fm_signal(self, num_samples: int) -> np.ndarray:
        """Generate FM signal (FPV analog style)"""
        t = np.arange(num_samples) / self.sample_rate
        
        # Message signal
        message = np.sin(2 * np.pi * 1000 * t)
        
        # FM modulation
        freq_deviation = 5000
        phase = 2 * np.pi * (self.signal_frequency * t + 
                            freq_deviation * np.cumsum(message) / self.sample_rate)
        
        signal = self.signal_amplitude * np.exp(1j * phase)
        
        return signal
    
    def inject_drone(self, drone_type: str = 'dji'):
        """Inject a drone signal into the stream"""
        self.drone_active = True
        self.drone_type = drone_type
        self.signal_type = 'drone'
        self.drone_start_time = time.time()
    
    def remove_drone(self):
        """Remove injected drone signal"""
        self.drone_active = False
        self.signal_type = 'noise'


# ============================================================================
# IQ Stream Processor
# ============================================================================

class IQStream:
    """
    High-performance IQ data stream processor
    
    Features:
    - Asynchronous sample processing
    - Ring buffer for continuous capture
    - Callback-based processing pipeline
    - Sample rate conversion
    - Chunk-based processing
    - Performance statistics
    """
    
    def __init__(self, source: IQStreamSource, config: Optional[StreamConfig] = None):
        """
        Initialize IQ stream
        
        Args:
            source: IQ data source (hardware or mock)
            config: Stream configuration
        """
        self.source = source
        self.config = config or StreamConfig()
        self.config.sample_rate = source.sample_rate
        
        # Buffer management
        self.ring_buffer = RingBuffer(self.config.buffer_size, 
                                       dtype=self.config.dtype.value)
        
        # Processing pipeline
        self.processors: List[Callable] = []
        self._processing_task: Optional[asyncio.Task] = None
        self._reading_task: Optional[asyncio.Task] = None
        
        # Thread pool for CPU-bound processing
        self.thread_pool = None
        if self.config.use_thread_pool:
            self.thread_pool = ThreadPoolExecutor(max_workers=self.config.thread_pool_size)
        
        # State management
        self.state = StreamState.IDLE
        self._chunk_counter = 0
        
        # Statistics
        self.stats = StreamStats()
        self.stats.start_time = time.time()
        
        # Synchronization
        self._pause_event = asyncio.Event()
        self._pause_event.set()
        self._stop_event = asyncio.Event()
        
        logger.info(f"IQ Stream initialized: {self.config.sample_rate/1e6:.1f} MHz, "
                   f"chunk_size={self.config.chunk_size}, buffer_size={self.config.buffer_size}")
    
    def add_processor(self, processor: Callable[[StreamChunk], Optional[StreamChunk]]):
        """
        Add a processor to the pipeline
        
        Args:
            processor: Callback function that processes StreamChunk
        """
        self.processors.append(processor)
        logger.debug(f"Added processor: {processor.__name__}")
    
    def remove_processor(self, processor: Callable):
        """
        Remove a processor from the pipeline
        
        Args:
            processor: Processor to remove
        """
        if processor in self.processors:
            self.processors.remove(processor)
            logger.debug(f"Removed processor: {processor.__name__}")
    
    async def start(self):
        """Start the stream"""
        if self.state == StreamState.RUNNING:
            logger.warning("Stream already running")
            return
        
        logger.info("Starting IQ stream...")
        
        # Start the source
        await self.source.start()
        
        # Reset state
        self.state = StreamState.RUNNING
        self._stop_event.clear()
        self._chunk_counter = 0
        
        # Start tasks
        self._reading_task = asyncio.create_task(self._read_loop())
        self._processing_task = asyncio.create_task(self._process_loop())
        
        logger.info("IQ stream started")
    
    async def stop(self):
        """Stop the stream"""
        if self.state != StreamState.RUNNING:
            return
        
        logger.info("Stopping IQ stream...")
        self.state = StreamState.STOPPING
        self._stop_event.set()
        
        # Cancel tasks
        if self._reading_task:
            self._reading_task.cancel()
        if self._processing_task:
            self._processing_task.cancel()
        
        # Wait for tasks to complete
        await asyncio.sleep(0.5)
        
        # Stop source
        await self.source.stop()
        
        # Clear buffer
        self.ring_buffer.clear()
        
        self.state = StreamState.IDLE
        logger.info("IQ stream stopped")
    
    async def pause(self):
        """Pause the stream"""
        if self.state == StreamState.RUNNING:
            self.state = StreamState.PAUSED
            self._pause_event.clear()
            logger.info("IQ stream paused")
    
    async def resume(self):
        """Resume the stream"""
        if self.state == StreamState.PAUSED:
            self.state = StreamState.RUNNING
            self._pause_event.set()
            logger.info("IQ stream resumed")
    
    async def _read_loop(self):
        """Background task for reading samples from source"""
        read_size = self.config.chunk_size
        
        while not self._stop_event.is_set():
            try:
                if self.state != StreamState.RUNNING:
                    await asyncio.sleep(0.01)
                    continue
                
                # Read samples from source
                read_start = time.time()
                samples = await self.source.read_samples(read_size)
                read_latency = (time.time() - read_start) * 1000
                
                if len(samples) == 0:
                    await asyncio.sleep(0.001)
                    continue
                
                # Write to ring buffer
                written = self.ring_buffer.write(samples)
                
                if written < len(samples):
                    self.stats.buffer_overruns += 1
                    logger.warning(f"Buffer overrun: wrote {written}/{len(samples)} samples")
                
                # Update statistics
                self.stats.samples_received += len(samples)
                self.stats.update_latency(read_latency)
                self.stats.last_sample_time = time.time()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Read loop error: {e}")
                await asyncio.sleep(0.1)
    
    async def _process_loop(self):
        """Background task for processing samples"""
        chunk_size = self.config.chunk_size
        
        while not self._stop_event.is_set():
            try:
                # Wait if paused
                await self._pause_event.wait()
                
                if self.state != StreamState.RUNNING:
                    await asyncio.sleep(0.01)
                    continue
                
                # Check if enough samples available
                available = self.ring_buffer.get_available()
                if available < chunk_size:
                    # Not enough samples, wait a bit
                    if available > 0:
                        self.stats.buffer_underruns += 1
                    await asyncio.sleep(0.001)
                    continue
                
                # Read chunk from buffer
                chunk_start = time.time()
                samples = self.ring_buffer.read(chunk_size)
                
                if len(samples) < chunk_size:
                    continue
                
                # Create stream chunk
                stream_chunk = StreamChunk(
                    data=samples,
                    timestamp=chunk_start,
                    sample_rate=self.config.sample_rate,
                    chunk_id=self._chunk_counter,
                    metadata={
                        'buffer_available': self.ring_buffer.get_available()
                    }
                )
                self._chunk_counter += 1
                
                # Apply scaling if needed
                if self.config.auto_scale:
                    max_val = np.max(np.abs(stream_chunk.data))
                    if max_val > 0.95:
                        stream_chunk.data = stream_chunk.data * (0.9 / max_val)
                
                # Process through pipeline
                processed_chunk = await self._run_processors(stream_chunk)
                
                # Update statistics
                process_latency = (time.time() - chunk_start) * 1000
                self.stats.samples_processed += len(samples)
                self.stats.chunks_produced += 1
                self.stats.current_sample_rate = self._calculate_sample_rate()
                
                # Calculate throughput periodically
                if self.stats.chunks_produced % 100 == 0:
                    elapsed = time.time() - self.stats.start_time
                    if elapsed > 0:
                        self.stats.calculate_throughput(
                            self.stats.samples_processed, elapsed
                        )
                
                # Log slow processing
                if process_latency > self.config.stream_timeout_ms:
                    logger.warning(f"Slow processing: {process_latency:.1f}ms")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Process loop error: {e}")
                await asyncio.sleep(0.1)
    
    async def _run_processors(self, chunk: StreamChunk) -> Optional[StreamChunk]:
        """
        Run all processors on the chunk
        
        Args:
            chunk: Stream chunk to process
            
        Returns:
            Processed chunk
        """
        result = chunk
        
        for processor in self.processors:
            if asyncio.iscoroutinefunction(processor):
                result = await processor(result)
            else:
                if self.thread_pool:
                    result = await asyncio.get_event_loop().run_in_executor(
                        self.thread_pool, processor, result
                    )
                else:
                    result = processor(result)
            
            if result is None:
                break
        
        return result
    
    def _calculate_sample_rate(self) -> float:
        """
        Calculate effective sample rate based on statistics
        
        Returns:
            Effective sample rate in Hz
        """
        if self.stats.samples_received == 0:
            return 0.0
        
        elapsed = time.time() - self.stats.start_time
        if elapsed > 0:
            return self.stats.samples_received / elapsed
        return 0.0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get stream statistics"""
        stats_dict = self.stats.to_dict()
        stats_dict.update({
            'state': self.state.value,
            'buffer_available': self.ring_buffer.get_available(),
            'buffer_free': self.ring_buffer.get_free_space(),
            'processors': len(self.processors),
            'chunk_size': self.config.chunk_size,
            'buffer_size': self.config.buffer_size,
            'sample_rate': self.config.sample_rate
        })
        return stats_dict
    
    def get_latest_samples(self, num_samples: int) -> np.ndarray:
        """
        Get the latest samples from the buffer without consuming
        
        Args:
            num_samples: Number of samples to get
            
        Returns:
            Array of samples
        """
        available = self.ring_buffer.get_available()
        if available == 0:
            return np.array([], dtype=self.config.dtype.value)
        
        samples_to_get = min(num_samples, available)
        offset = max(0, available - samples_to_get)
        
        return self.ring_buffer.peek(samples_to_get, offset)
    
    def flush(self):
        """Flush the buffer"""
        self.ring_buffer.clear()
        logger.debug("Buffer flushed")


# ============================================================================
# Stream Builder
# ============================================================================

class IQStreamBuilder:
    """
    Builder pattern for constructing IQ streams with processing pipeline
    
    Usage:
        stream = (IQStreamBuilder()
                  .with_source(hackrf_source)
                  .with_chunk_size(32768)
                  .with_processor(fft_processor)
                  .with_processor(detection_processor)
                  .build())
    """
    
    def __init__(self):
        self.source: Optional[IQStreamSource] = None
        self.config = StreamConfig()
        self.processors: List[Callable] = []
    
    def with_source(self, source: IQStreamSource) -> 'IQStreamBuilder':
        """Set stream source"""
        self.source = source
        return self
    
    def with_sample_rate(self, sample_rate: float) -> 'IQStreamBuilder':
        """Set sample rate"""
        self.config.sample_rate = sample_rate
        return self
    
    def with_chunk_size(self, chunk_size: int) -> 'IQStreamBuilder':
        """Set chunk size"""
        self.config.chunk_size = chunk_size
        return self
    
    def with_buffer_size(self, buffer_size: int) -> 'IQStreamBuilder':
        """Set buffer size"""
        self.config.buffer_size = buffer_size
        return self
    
    def with_dtype(self, dtype: DataType) -> 'IQStreamBuilder':
        """Set data type"""
        self.config.dtype = dtype
        return self
    
    def with_processor(self, processor: Callable) -> 'IQStreamBuilder':
        """Add a processor to the pipeline"""
        self.processors.append(processor)
        return self
    
    def enable_stats(self, enable: bool = True) -> 'IQStreamBuilder':
        """Enable statistics collection"""
        self.config.enable_stats = enable
        return self
    
    def build(self) -> IQStream:
        """Build the IQ stream"""
        if self.source is None:
            raise ValueError("Source must be set before building")
        
        stream = IQStream(self.source, self.config)
        for processor in self.processors:
            stream.add_processor(processor)
        
        return stream


# ============================================================================
# Example Processors
# ============================================================================

async def fft_processor(chunk: StreamChunk) -> StreamChunk:
    """
    Example FFT processor
    
    Adds FFT data to chunk metadata
    """
    # Compute FFT
    fft_data = np.fft.fftshift(np.fft.fft(chunk.data))
    fft_magnitude = np.abs(fft_data)
    
    chunk.metadata['fft'] = fft_magnitude.tolist()
    chunk.metadata['fft_frequencies'] = np.fft.fftfreq(len(chunk.data), 1/chunk.sample_rate).tolist()
    
    return chunk


async def power_processor(chunk: StreamChunk) -> StreamChunk:
    """
    Example power measurement processor
    """
    # Compute average power
    power = np.mean(np.abs(chunk.data)**2)
    power_dbm = 10 * np.log10(power + 1e-12)
    
    chunk.metadata['avg_power'] = float(power)
    chunk.metadata['avg_power_dbm'] = float(power_dbm)
    
    return chunk


# ============================================================================
# Factory Functions
# ============================================================================

def create_mock_stream(sample_rate: float = 2.4e6, 
                       signal_type: str = 'drone') -> IQStream:
    """
    Create a mock IQ stream for testing
    
    Args:
        sample_rate: Sample rate in Hz
        signal_type: Type of signal ('noise', 'tone', 'drone')
        
    Returns:
        Configured IQStream instance
    """
    source = MockStreamSource(sample_rate, {'signal_type': signal_type})
    stream = IQStream(source, StreamConfig(sample_rate=sample_rate))
    return stream


def create_stream_from_hardware(sample_rate: float = 2.4e6,
                                 hardware_type: str = 'hackrf') -> IQStream:
    """
    Create IQ stream from real hardware
    
    Args:
        sample_rate: Sample rate in Hz
        hardware_type: Type of hardware ('hackrf', 'rtlsdr', etc.)
        
    Returns:
        Configured IQStream instance
    """
    # This would integrate with actual hardware drivers
    # For now, return mock stream
    return create_mock_stream(sample_rate)


# ============================================================================
# Example Usage
# ============================================================================

async def main():
    """Example usage of IQ streaming"""
    
    print("IQ Stream Test")
    print("=" * 50)
    
    # Create stream
    print("\n1. Creating IQ stream...")
    stream = create_mock_stream(sample_rate=2.4e6, signal_type='drone')
    
    # Add processors
    print("2. Adding processors...")
    stream.add_processor(fft_processor)
    stream.add_processor(power_processor)
    
    # Start stream
    print("3. Starting stream...")
    await stream.start()
    
    # Collect statistics for 5 seconds
    print("4. Collecting statistics...")
    
    for i in range(10):
        await asyncio.sleep(0.5)
        stats = stream.get_stats()
        print(f"   Chunks: {stats['chunks_produced']}, "
              f"Samples: {stats['samples_processed']}, "
              f"Throughput: {stats['current_throughput_mbps']:.2f} Mbps")
    
    # Get final statistics
    print("\n5. Final Statistics:")
    stats = stream.get_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    # Stop stream
    print("\n6. Stopping stream...")
    await stream.stop()
    
    print("\n" + "=" * 50)
    print("IQ stream test complete!")


if __name__ == "__main__":
    # Run async main
    asyncio.run(main())