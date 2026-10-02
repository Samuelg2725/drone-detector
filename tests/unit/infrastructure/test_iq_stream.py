#!/usr/bin/env python3
"""
Unit Tests for IQ Stream Module

Tests for IQ data streaming, ring buffer operations, sample processing,
and stream management functionality.
"""

import asyncio
import numpy as np
import unittest
from unittest.mock import Mock, patch, AsyncMock, MagicMock, call
from datetime import datetime
import time

# Import modules to test
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from infrastructure.signal_io.iq_stream import (
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
# Test Data Generators
# ============================================================================

class TestDataGenerator:
    """Generate test data for IQ stream tests"""
    
    @staticmethod
    def generate_test_signal(num_samples: int = 16384, sample_rate: float = 10e6) -> np.ndarray:
        """Generate a test IQ signal"""
        t = np.arange(num_samples) / sample_rate
        # Generate a complex sine wave with noise
        signal = np.exp(1j * 2 * np.pi * 100e3 * t)
        noise = 0.1 * (np.random.randn(num_samples) + 1j * np.random.randn(num_samples))
        return (signal + noise).astype(np.complex64)
    
    @staticmethod
    def generate_noise(num_samples: int) -> np.ndarray:
        """Generate white noise"""
        return (np.random.randn(num_samples) + 1j * np.random.randn(num_samples)).astype(np.complex64)


# ============================================================================
# Mock Stream Source
# ============================================================================

class MockStreamSourceForTest(IQStreamSource):
    """Mock stream source for testing"""
    
    def __init__(self, sample_rate: float = 10e6, config: dict = None):
        super().__init__(sample_rate, config)
        self.sample_data = TestDataGenerator.generate_test_signal(16384, sample_rate)
        self.call_count = 0
        self.delay_ms = 0
        self.should_fail = False
    
    async def read_samples(self, num_samples: int) -> np.ndarray:
        """Mock read samples"""
        if self.should_fail:
            raise RuntimeError("Mock read failure")
        
        if self.delay_ms > 0:
            await asyncio.sleep(self.delay_ms / 1000)
        
        self.call_count += 1
        samples = self.sample_data[:num_samples]
        return samples


# ============================================================================
# Ring Buffer Tests
# ============================================================================

class TestRingBuffer(unittest.TestCase):
    """Test ring buffer functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.buffer_size = 1024
        self.ring_buffer = RingBuffer(self.buffer_size, dtype=np.complex64)
    
    def test_initialization(self):
        """Test ring buffer initialization"""
        self.assertEqual(self.ring_buffer.buffer_size, self.buffer_size)
        self.assertEqual(self.ring_buffer.available_samples, 0)
        self.assertEqual(self.ring_buffer.write_pos, 0)
        self.assertEqual(self.ring_buffer.read_pos, 0)
    
    def test_write_samples(self):
        """Test writing samples to buffer"""
        samples = np.ones(100, dtype=np.complex64)
        written = self.ring_buffer.write(samples)
        
        self.assertEqual(written, 100)
        self.assertEqual(self.ring_buffer.available_samples, 100)
    
    def test_read_samples(self):
        """Test reading samples from buffer"""
        samples = np.ones(100, dtype=np.complex64)
        self.ring_buffer.write(samples)
        
        read_samples = self.ring_buffer.read(50)
        
        self.assertEqual(len(read_samples), 50)
        self.assertEqual(self.ring_buffer.available_samples, 50)
    
    def test_read_all_samples(self):
        """Test reading all available samples"""
        samples = np.ones(100, dtype=np.complex64)
        self.ring_buffer.write(samples)
        
        read_samples = self.ring_buffer.read(200)
        
        self.assertEqual(len(read_samples), 100)
        self.assertEqual(self.ring_buffer.available_samples, 0)
    
    def test_buffer_overflow(self):
        """Test buffer overflow handling"""
        # Fill buffer
        samples = np.ones(self.buffer_size, dtype=np.complex64)
        written = self.ring_buffer.write(samples)
        
        self.assertEqual(written, self.buffer_size)
        self.assertEqual(self.ring_buffer.available_samples, self.buffer_size)
        
        # Try to write more (should be dropped)
        extra_samples = np.ones(100, dtype=np.complex64)
        written = self.ring_buffer.write(extra_samples)
        
        self.assertEqual(written, 0)  # No space
        self.assertEqual(self.ring_buffer.available_samples, self.buffer_size)
    
    def test_buffer_underflow(self):
        """Test reading from empty buffer"""
        read_samples = self.ring_buffer.read(100)
        
        self.assertEqual(len(read_samples), 0)
        self.assertEqual(self.ring_buffer.available_samples, 0)
    
    def test_peek_samples(self):
        """Test peeking at samples without consuming"""
        samples = np.arange(100, dtype=np.complex64)
        self.ring_buffer.write(samples)
        
        peeked = self.ring_buffer.peek(50)
        
        self.assertEqual(len(peeked), 50)
        self.assertEqual(self.ring_buffer.available_samples, 100)  # Still available
    
    def test_peek_with_offset(self):
        """Test peeking with offset"""
        samples = np.arange(100, dtype=np.complex64)
        self.ring_buffer.write(samples)
        
        peeked = self.ring_buffer.peek(50, offset=25)
        
        self.assertEqual(len(peeked), 50)
        np.testing.assert_array_equal(peeked, samples[25:75])
    
    def test_clear_buffer(self):
        """Test clearing the buffer"""
        samples = np.ones(100, dtype=np.complex64)
        self.ring_buffer.write(samples)
        
        self.ring_buffer.clear()
        
        self.assertEqual(self.ring_buffer.available_samples, 0)
        self.assertEqual(self.ring_buffer.write_pos, 0)
        self.assertEqual(self.ring_buffer.read_pos, 0)
    
    def test_wrap_around_write(self):
        """Test writing that wraps around buffer end"""
        # Write to near the end
        samples1 = np.ones(self.buffer_size - 50, dtype=np.complex64)
        self.ring_buffer.write(samples1)
        
        # Read some to create space
        self.ring_buffer.read(30)
        
        # Write more that should wrap
        samples2 = np.ones(100, dtype=np.complex64)
        written = self.ring_buffer.write(samples2)
        
        self.assertEqual(written, 100)
    
    def test_concurrent_read_write(self):
        """Test concurrent read/write operations"""
        import threading
        
        def writer():
            for i in range(100):
                samples = np.ones(10, dtype=np.complex64) * i
                self.ring_buffer.write(samples)
                time.sleep(0.001)
        
        def reader():
            total_read = 0
            while total_read < 1000:
                samples = self.ring_buffer.read(10)
                total_read += len(samples)
                time.sleep(0.001)
        
        writer_thread = threading.Thread(target=writer)
        reader_thread = threading.Thread(target=reader)
        
        writer_thread.start()
        reader_thread.start()
        
        writer_thread.join(timeout=2)
        reader_thread.join(timeout=2)


# ============================================================================
# Mock Stream Source Tests
# ============================================================================

class TestMockStreamSource(unittest.TestCase):
    """Test mock stream source"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.source = MockStreamSource(sample_rate=10e6)
    
    def test_initialization(self):
        """Test mock source initialization"""
        self.assertEqual(self.source.sample_rate, 10e6)
        self.assertFalse(self.source.is_running)
    
    async def test_start_stop(self):
        """Test starting and stopping the source"""
        await self.source.start()
        self.assertTrue(self.source.is_running)
        
        await self.source.stop()
        self.assertFalse(self.source.is_running)
    
    async def test_read_samples(self):
        """Test reading samples from mock source"""
        await self.source.start()
        
        samples = await self.source.read_samples(1024)
        
        self.assertEqual(len(samples), 1024)
        self.assertEqual(samples.dtype, np.complex64)
    
    async def test_read_noise_samples(self):
        """Test reading noise samples"""
        self.source.signal_type = 'noise'
        await self.source.start()
        
        samples = await self.source.read_samples(1024)
        
        self.assertEqual(len(samples), 1024)
    
    async def test_read_tone_samples(self):
        """Test reading tone samples"""
        self.source.signal_type = 'tone'
        await self.source.start()
        
        samples = await self.source.read_samples(1024)
        
        self.assertEqual(len(samples), 1024)
    
    async def test_inject_drone(self):
        """Test injecting drone signal"""
        self.source.inject_drone('dji')
        
        self.assertTrue(self.source.drone_active)
        self.assertEqual(self.source.drone_type, 'dji')
    
    async def test_remove_drone(self):
        """Test removing drone signal"""
        self.source.inject_drone('dji')
        self.source.remove_drone()
        
        self.assertFalse(self.source.drone_active)
        self.assertEqual(self.source.signal_type, 'noise')


# ============================================================================
# IQ Stream Tests
# ============================================================================

class TestIQStream(unittest.TestCase):
    """Test IQ stream functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.source = MockStreamSourceForTest(sample_rate=10e6)
        self.config = StreamConfig(
            sample_rate=10e6,
            chunk_size=1024,
            buffer_size=8192,
            enable_stats=True
        )
        self.stream = IQStream(self.source, self.config)
    
    def test_initialization(self):
        """Test stream initialization"""
        self.assertEqual(self.stream.state, StreamState.IDLE)
        self.assertEqual(self.stream.config.sample_rate, 10e6)
        self.assertEqual(self.stream.config.chunk_size, 1024)
    
    async def test_start_stream(self):
        """Test starting the stream"""
        await self.stream.start()
        
        self.assertEqual(self.stream.state, StreamState.RUNNING)
        self.assertIsNotNone(self.stream._reading_task)
        self.assertIsNotNone(self.stream._processing_task)
    
    async def test_stop_stream(self):
        """Test stopping the stream"""
        await self.stream.start()
        await self.stream.stop()
        
        self.assertEqual(self.stream.state, StreamState.IDLE)
    
    async def test_pause_resume(self):
        """Test pausing and resuming the stream"""
        await self.stream.start()
        await self.stream.pause()
        
        self.assertEqual(self.stream.state, StreamState.PAUSED)
        
        await self.stream.resume()
        self.assertEqual(self.stream.state, StreamState.RUNNING)
    
    async def test_add_processor(self):
        """Test adding a processor to the pipeline"""
        def test_processor(chunk):
            return chunk
        
        self.stream.add_processor(test_processor)
        
        self.assertIn(test_processor, self.stream.processors)
    
    async def test_remove_processor(self):
        """Test removing a processor from the pipeline"""
        def test_processor(chunk):
            return chunk
        
        self.stream.add_processor(test_processor)
        self.stream.remove_processor(test_processor)
        
        self.assertNotIn(test_processor, self.stream.processors)
    
    async def test_get_latest_samples(self):
        """Test getting latest samples from buffer"""
        await self.stream.start()
        
        # Wait for some samples
        await asyncio.sleep(0.1)
        
        samples = self.stream.get_latest_samples(512)
        
        self.assertLessEqual(len(samples), 512)
    
    async def test_flush_buffer(self):
        """Test flushing the buffer"""
        await self.stream.start()
        
        # Write some samples
        samples = TestDataGenerator.generate_test_signal(1024)
        self.stream.ring_buffer.write(samples)
        
        self.assertGreater(self.stream.ring_buffer.available_samples, 0)
        
        self.stream.flush()
        
        self.assertEqual(self.stream.ring_buffer.available_samples, 0)
    
    async def test_stream_stats(self):
        """Test stream statistics collection"""
        await self.stream.start()
        
        # Let stream run for a bit
        await asyncio.sleep(0.5)
        
        stats = self.stream.get_stats()
        
        self.assertIsNotNone(stats)
        self.assertIn('samples_received', stats)
        self.assertIn('chunks_produced', stats)
    
    async def test_buffer_overflow_handling(self):
        """Test buffer overflow handling"""
        # Use small buffer to force overflow
        small_config = StreamConfig(
            sample_rate=10e6,
            chunk_size=1024,
            buffer_size=2048,
            overwrite_on_full=True
        )
        small_stream = IQStream(self.source, small_config)
        
        await small_stream.start()
        
        # Let stream run (may cause overflows)
        await asyncio.sleep(0.5)
        
        stats = small_stream.get_stats()
        
        # Buffer overruns may have occurred, but stream should still be running
        self.assertEqual(small_stream.state, StreamState.RUNNING)
    
    async def test_source_failure_handling(self):
        """Test handling of source read failures"""
        self.source.should_fail = True
        
        await self.stream.start()
        
        # Let stream run (should handle errors)
        await asyncio.sleep(0.5)
        
        # Stream should still be running (error recovery)
        self.assertEqual(self.stream.state, StreamState.RUNNING)
    
    async def test_multiple_processors(self):
        """Test multiple processors in pipeline"""
        processor_calls = []
        
        def processor1(chunk):
            processor_calls.append('processor1')
            return chunk
        
        def processor2(chunk):
            processor_calls.append('processor2')
            return chunk
        
        self.stream.add_processor(processor1)
        self.stream.add_processor(processor2)
        
        await self.stream.start()
        
        # Let stream process
        await asyncio.sleep(0.5)
        
        # Both processors should have been called
        self.assertIn('processor1', processor_calls)
        self.assertIn('processor2', processor_calls)


# ============================================================================
# IQ Stream Builder Tests
# ============================================================================

class TestIQStreamBuilder(unittest.TestCase):
    """Test IQ stream builder pattern"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.source = MockStreamSourceForTest(sample_rate=10e6)
        self.builder = IQStreamBuilder()
    
    def test_builder_initialization(self):
        """Test builder initialization"""
        self.assertIsNone(self.builder.source)
        self.assertIsInstance(self.builder.config, StreamConfig)
    
    def test_with_source(self):
        """Test setting stream source"""
        self.builder.with_source(self.source)
        
        self.assertEqual(self.builder.source, self.source)
    
    def test_with_sample_rate(self):
        """Test setting sample rate"""
        self.builder.with_sample_rate(20e6)
        
        self.assertEqual(self.builder.config.sample_rate, 20e6)
    
    def test_with_chunk_size(self):
        """Test setting chunk size"""
        self.builder.with_chunk_size(4096)
        
        self.assertEqual(self.builder.config.chunk_size, 4096)
    
    def test_with_buffer_size(self):
        """Test setting buffer size"""
        self.builder.with_buffer_size(65536)
        
        self.assertEqual(self.builder.config.buffer_size, 65536)
    
    def test_with_dtype(self):
        """Test setting data type"""
        self.builder.with_dtype(DataType.COMPLEX128)
        
        self.assertEqual(self.builder.config.dtype, DataType.COMPLEX128)
    
    def test_with_processor(self):
        """Test adding processor"""
        def test_processor(chunk):
            return chunk
        
        self.builder.with_processor(test_processor)
        
        self.assertIn(test_processor, self.builder.processors)
    
    def test_build(self):
        """Test building the stream"""
        self.builder.with_source(self.source)
        self.builder.with_chunk_size(2048)
        
        stream = self.builder.build()
        
        self.assertIsInstance(stream, IQStream)
        self.assertEqual(stream.config.chunk_size, 2048)
    
    def test_build_without_source(self):
        """Test building without source (should raise error)"""
        with self.assertRaises(ValueError):
            self.builder.build()


# ============================================================================
# Processor Function Tests
# ============================================================================

class TestProcessors(unittest.TestCase):
    """Test processor functions"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.samples = TestDataGenerator.generate_test_signal(16384)
        self.chunk = StreamChunk(
            data=self.samples,
            timestamp=time.time(),
            sample_rate=10e6,
            chunk_id=0
        )
    
    def test_fft_processor(self):
        """Test FFT processor"""
        result = fft_processor(self.chunk)
        
        self.assertIsNotNone(result)
        self.assertIn('fft', result.metadata)
        self.assertIn('fft_frequencies', result.metadata)
    
    def test_power_processor(self):
        """Test power processor"""
        result = power_processor(self.chunk)
        
        self.assertIsNotNone(result)
        self.assertIn('avg_power', result.metadata)
        self.assertIn('avg_power_dbm', result.metadata)


# ============================================================================
# Factory Function Tests
# ============================================================================

class TestFactoryFunctions(unittest.TestCase):
    """Test factory functions"""
    
    def test_create_mock_stream(self):
        """Test creating mock stream"""
        stream = create_mock_stream(sample_rate=5e6, signal_type='drone')
        
        self.assertIsInstance(stream, IQStream)
        self.assertEqual(stream.config.sample_rate, 5e6)
    
    def test_create_stream_from_hardware(self):
        """Test creating stream from hardware"""
        # This would normally create a hardware stream, but for test it creates mock
        stream = create_stream_from_hardware(sample_rate=10e6, hardware_type='hackrf')
        
        self.assertIsInstance(stream, IQStream)


# ============================================================================
# Stress Tests
# ============================================================================

class TestIQStreamStress(unittest.TestCase):
    """Stress tests for IQ stream"""
    
    async def test_high_throughput(self):
        """Test high throughput streaming"""
        source = MockStreamSourceForTest(sample_rate=20e6)
        config = StreamConfig(
            sample_rate=20e6,
            chunk_size=32768,
            buffer_size=262144,
            use_thread_pool=True,
            thread_pool_size=4
        )
        stream = IQStream(source, config)
        
        await stream.start()
        
        # Run for 2 seconds
        await asyncio.sleep(2)
        
        stats = stream.get_stats()
        
        # Should have processed many samples
        self.assertGreater(stats['samples_processed'], 0)
        
        await stream.stop()
    
    async def test_long_running_stream(self):
        """Test long-running stream stability"""
        source = MockStreamSourceForTest(sample_rate=10e6)
        stream = IQStream(source)
        
        await stream.start()
        
        # Run for 5 seconds
        for i in range(5):
            await asyncio.sleep(1)
            stats = stream.get_stats()
            self.assertIsNotNone(stats)
        
        await stream.stop()
        self.assertEqual(stream.state, StreamState.IDLE)


# ============================================================================
# Performance Tests
# ============================================================================

class TestIQStreamPerformance(unittest.TestCase):
    """Performance tests for IQ stream"""
    
    async def test_processing_latency(self):
        """Test processing latency"""
        import time
        
        source = MockStreamSourceForTest(sample_rate=10e6)
        stream = IQStream(source)
        
        latencies = []
        
        def latency_processor(chunk):
            if 'receive_time' in chunk.metadata:
                latency = time.time() - chunk.metadata['receive_time']
                latencies.append(latency)
            return chunk
        
        stream.add_processor(latency_processor)
        
        await stream.start()
        
        # Measure latency
        await asyncio.sleep(1)
        
        await stream.stop()
        
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            # Average latency should be under 100ms
            self.assertLess(avg_latency, 0.1)
    
    async def test_memory_usage(self):
        """Test memory usage stability"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024
        
        source = MockStreamSourceForTest(sample_rate=10e6)
        stream = IQStream(source)
        
        await stream.start()
        
        # Run for 3 seconds
        await asyncio.sleep(3)
        
        await stream.stop()
        
        final_memory = process.memory_info().rss / 1024 / 1024
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (< 100 MB)
        self.assertLess(memory_increase, 100)


# ============================================================================
# Integration Tests
# ============================================================================

class TestIQStreamIntegration(unittest.TestCase):
    """Integration tests for IQ stream with real components"""
    
    async def test_stream_with_recorder(self):
        """Test stream integration with recorder"""
        from infrastructure.signal_io.recorder import IQRecorder, RecordingConfig
        
        source = MockStreamSourceForTest(sample_rate=10e6)
        stream = IQStream(source)
        
        recorder = IQRecorder(RecordingConfig(
            output_dir="data/test",
            format="raw"
        ))
        
        # Start recording
        await recorder.start_recording("test_session")
        
        # Start stream
        await stream.start()
        
        # Process chunks
        async for chunk in stream._playback_loop():
            await recorder.write_samples(chunk.data)
            break  # Just one chunk for test
        
        await stream.stop()
        metadata = await recorder.stop_recording()
        
        self.assertIsNotNone(metadata)
    
    async def test_stream_with_playback(self):
        """Test stream integration with playback"""
        from infrastructure.signal_io.playback import IQPlaybackEngine
        
        # First record some data
        source = MockStreamSourceForTest(sample_rate=10e6)
        stream = IQStream(source)
        
        # Process would normally go here
        # This is a simplified integration test
        
        self.assertIsNotNone(stream)


# ============================================================================
# Run Tests
# ============================================================================

async def run_async_tests():
    """Run async test methods"""
    # Create test instance and run async methods
    test_instance = TestIQStream()
    
    await test_instance.test_start_stream()
    await test_instance.test_stop_stream()
    await test_instance.test_pause_resume()
    await test_instance.test_add_processor()
    await test_instance.test_remove_processor()
    await test_instance.test_get_latest_samples()
    await test_instance.test_flush_buffer()
    await test_instance.test_stream_stats()
    await test_instance.test_buffer_overflow_handling()
    await test_instance.test_source_failure_handling()
    await test_instance.test_multiple_processors()


if __name__ == '__main__':
    # Run async tests
    import asyncio
    asyncio.run(run_async_tests())
    
    # Run regular unittest suite
    unittest.main(verbosity=2)