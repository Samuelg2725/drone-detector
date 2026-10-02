#!/usr/bin/env python3
"""
Unit Tests for Processing Pipelines Module

Tests for end-to-end processing pipelines, including detection pipeline,
spectrum analysis pipeline, and data processing workflows.
"""

import asyncio
import json
import unittest
from unittest.mock import Mock, patch, AsyncMock, MagicMock, call
from datetime import datetime
import numpy as np
import tempfile
from pathlib import Path

# Import modules to test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.pipelines import (
    DetectionPipeline,
    SpectrumPipeline,
    RecordingPipeline,
    PlaybackPipeline,
    PipelineContext,
    PipelineStage,
    PipelineResult,
    PipelineStatus,
    create_detection_pipeline,
    create_spectrum_pipeline
)


# ============================================================================
# Test Data Generators
# ============================================================================

class TestDataGenerator:
    """Generate test data for pipeline tests"""
    
    @staticmethod
    def generate_iq_samples(num_samples: int = 16384, sample_rate: float = 10e6) -> np.ndarray:
        """Generate test IQ samples"""
        t = np.arange(num_samples) / sample_rate
        # Generate a complex signal with multiple frequency components
        signal = np.exp(1j * 2 * np.pi * 100e3 * t)
        signal += 0.5 * np.exp(1j * 2 * np.pi * 200e3 * t)
        signal += 0.3 * np.exp(1j * 2 * np.pi * 300e3 * t)
        noise = 0.1 * (np.random.randn(num_samples) + 1j * np.random.randn(num_samples))
        return (signal + noise).astype(np.complex64)
    
    @staticmethod
    def generate_detection_data() -> dict:
        """Generate test detection data"""
        return {
            'id': 'det_001',
            'timestamp': datetime.now().isoformat(),
            'drone_type': 'DJI Mavic 3',
            'confidence': 0.95,
            'threat_level': 'HIGH',
            'frequency': 2.44e9,
            'signal_strength': -45.2,
            'latitude': 37.7749,
            'longitude': -122.4194,
            'altitude': 100.0,
            'snr': 28.5,
            'bandwidth': 20e6,
            'modulation': 'OFDM'
        }
    
    @staticmethod
    def generate_spectrum_data() -> dict:
        """Generate test spectrum data"""
        frequencies = np.linspace(2.4e9, 2.5e9, 1024)
        psd = -80 + 20 * np.random.randn(1024)
        # Add a peak at 2.44 GHz
        peak_idx = np.argmin(np.abs(frequencies - 2.44e9))
        psd[peak_idx] = -45
        return {
            'frequencies': frequencies.tolist(),
            'psd': psd.tolist(),
            'sample_rate': 10e6,
            'center_freq': 2.44e9,
            'timestamp': datetime.now().isoformat()
        }

    @staticmethod
    def generate_recording_metadata() -> dict:
        """Generate test recording metadata"""
        return {
            'session_id': 'session_001',
            'recording_id': 'rec_001',
            'file_path': '/tmp/test_recording.iq',
            'duration': 30.0,
            'sample_rate': 10e6,
            'center_freq': 2.44e9,
            'num_samples': 300000000
        }


# ============================================================================
# Mock Pipeline Stages
# ============================================================================

class MockPipelineStage(PipelineStage):
    """Mock pipeline stage for testing"""
    
    def __init__(self, name: str = "mock_stage", should_fail: bool = False):
        super().__init__(name)
        self.should_fail = should_fail
        self.process_called = False
        self.process_count = 0
    
    async def process(self, context: PipelineContext) -> PipelineContext:
        self.process_called = True
        self.process_count += 1
        
        if self.should_fail:
            raise RuntimeError(f"Stage {self.name} failed")
        
        context.metadata[f"{self.name}_processed"] = True
        context.metadata[f"{self.name}_count"] = self.process_count
        return context


# ============================================================================
# Pipeline Context Tests
# ============================================================================

class TestPipelineContext(unittest.TestCase):
    """Test pipeline context functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.context = PipelineContext(
            input_data={'test': 'data'},
            config={'param': 'value'},
            metadata={'stage': 'test'}
        )
    
    def test_context_initialization(self):
        """Test context initialization"""
        self.assertEqual(self.context.input_data['test'], 'data')
        self.assertEqual(self.context.config['param'], 'value')
        self.assertEqual(self.context.metadata['stage'], 'test')
        self.assertIsNone(self.context.result)
        self.assertEqual(self.context.status, PipelineStatus.PENDING)
    
    def test_update_metadata(self):
        """Test updating metadata"""
        self.context.update_metadata({'new_key': 'new_value'})
        
        self.assertEqual(self.context.metadata['stage'], 'test')
        self.assertEqual(self.context.metadata['new_key'], 'new_value')
    
    def test_set_result(self):
        """Test setting result"""
        result_data = {'detection_id': 'det_001', 'confidence': 0.95}
        self.context.set_result(result_data)
        
        self.assertEqual(self.context.result, result_data)
        self.assertEqual(self.context.status, PipelineStatus.COMPLETED)
    
    def test_set_error(self):
        """Test setting error"""
        error_msg = "Processing failed"
        self.context.set_error(error_msg)
        
        self.assertEqual(self.context.error, error_msg)
        self.assertEqual(self.context.status, PipelineStatus.FAILED)
    
    def test_to_dict(self):
        """Test context to dictionary conversion"""
        context_dict = self.context.to_dict()
        
        self.assertIn('input_data', context_dict)
        self.assertIn('config', context_dict)
        self.assertIn('metadata', context_dict)
        self.assertIn('status', context_dict)
        self.assertIn('created_at', context_dict)


# ============================================================================
# Pipeline Stage Tests
# ============================================================================

class TestPipelineStage(unittest.TestCase):
    """Test pipeline stage functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.stage = MockPipelineStage("test_stage")
    
    async def test_stage_initialization(self):
        """Test stage initialization"""
        self.assertEqual(self.stage.name, "test_stage")
        self.assertFalse(self.stage.process_called)
    
    async def test_stage_process(self):
        """Test stage processing"""
        context = PipelineContext(input_data={})
        
        result = await self.stage.process(context)
        
        self.assertTrue(self.stage.process_called)
        self.assertEqual(self.stage.process_count, 1)
        self.assertTrue(result.metadata['test_stage_processed'])
    
    async def test_stage_multiple_processes(self):
        """Test multiple stage processes"""
        context = PipelineContext(input_data={})
        
        for i in range(3):
            await self.stage.process(context)
        
        self.assertEqual(self.stage.process_count, 3)
        self.assertEqual(context.metadata['test_stage_count'], 3)
    
    async def test_stage_failure(self):
        """Test stage failure handling"""
        failing_stage = MockPipelineStage("failing_stage", should_fail=True)
        context = PipelineContext(input_data={})
        
        with self.assertRaises(RuntimeError):
            await failing_stage.process(context)


# ============================================================================
# Detection Pipeline Tests
# ============================================================================

class TestDetectionPipeline(unittest.TestCase):
    """Test detection pipeline functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.pipeline = DetectionPipeline()
    
    async def test_pipeline_initialization(self):
        """Test pipeline initialization"""
        self.assertEqual(len(self.pipeline.stages), 0)
        self.assertEqual(self.pipeline.name, "detection_pipeline")
    
    async def test_add_stage(self):
        """Test adding stage to pipeline"""
        stage = MockPipelineStage("stage1")
        self.pipeline.add_stage(stage)
        
        self.assertIn(stage, self.pipeline.stages)
        self.assertEqual(len(self.pipeline.stages), 1)
    
    async def test_remove_stage(self):
        """Test removing stage from pipeline"""
        stage1 = MockPipelineStage("stage1")
        stage2 = MockPipelineStage("stage2")
        
        self.pipeline.add_stage(stage1)
        self.pipeline.add_stage(stage2)
        
        self.pipeline.remove_stage("stage1")
        
        self.assertNotIn(stage1, self.pipeline.stages)
        self.assertIn(stage2, self.pipeline.stages)
        self.assertEqual(len(self.pipeline.stages), 1)
    
    async def test_run_pipeline_success(self):
        """Test successful pipeline execution"""
        stage1 = MockPipelineStage("stage1")
        stage2 = MockPipelineStage("stage2")
        
        self.pipeline.add_stage(stage1)
        self.pipeline.add_stage(stage2)
        
        iq_samples = TestDataGenerator.generate_iq_samples()
        result = await self.pipeline.run(iq_samples)
        
        self.assertIsNotNone(result)
        self.assertTrue(stage1.process_called)
        self.assertTrue(stage2.process_called)
    
    async def test_run_pipeline_with_config(self):
        """Test pipeline execution with configuration"""
        stage = MockPipelineStage("stage1")
        self.pipeline.add_stage(stage)
        
        iq_samples = TestDataGenerator.generate_iq_samples()
        config = {'threshold': 0.8, 'algorithm': 'ml'}
        
        result = await self.pipeline.run(iq_samples, config=config)
        
        self.assertIsNotNone(result)
    
    async def test_run_pipeline_failure(self):
        """Test pipeline execution with failure"""
        stage1 = MockPipelineStage("stage1")
        stage2 = MockPipelineStage("stage2", should_fail=True)
        
        self.pipeline.add_stage(stage1)
        self.pipeline.add_stage(stage2)
        
        iq_samples = TestDataGenerator.generate_iq_samples()
        result = await self.pipeline.run(iq_samples)
        
        # First stage should have run, second failed
        self.assertTrue(stage1.process_called)
        self.assertIsNotNone(result)
        self.assertEqual(result.status, PipelineStatus.FAILED)
    
    async def test_get_pipeline_status(self):
        """Test getting pipeline status"""
        stage1 = MockPipelineStage("stage1")
        stage2 = MockPipelineStage("stage2")
        
        self.pipeline.add_stage(stage1)
        self.pipeline.add_stage(stage2)
        
        status = self.pipeline.get_status()
        
        self.assertIn('name', status)
        self.assertIn('stages', status)
        self.assertEqual(len(status['stages']), 2)
    
    async def test_reset_pipeline(self):
        """Test resetting pipeline"""
        stage = MockPipelineStage("stage1")
        self.pipeline.add_stage(stage)
        
        iq_samples = TestDataGenerator.generate_iq_samples()
        await self.pipeline.run(iq_samples)
        
        self.pipeline.reset()
        
        # Context should be cleared
        self.assertIsNone(self.pipeline._current_context)


# ============================================================================
# Spectrum Pipeline Tests
# ============================================================================

class TestSpectrumPipeline(unittest.TestCase):
    """Test spectrum pipeline functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.pipeline = SpectrumPipeline()
    
    async def test_initialization(self):
        """Test pipeline initialization"""
        self.assertEqual(self.pipeline.name, "spectrum_pipeline")
        self.assertGreater(len(self.pipeline.stages), 0)
    
    async def test_run_spectrum_analysis(self):
        """Test spectrum analysis pipeline"""
        iq_samples = TestDataGenerator.generate_iq_samples()
        
        result = await self.pipeline.run(iq_samples)
        
        self.assertIsNotNone(result)
        self.assertIn('frequencies', result)
        self.assertIn('psd', result)
        self.assertIn('peaks', result)
    
    async def test_run_with_config(self):
        """Test spectrum analysis with custom config"""
        iq_samples = TestDataGenerator.generate_iq_samples()
        config = {
            'fft_size': 4096,
            'overlap': 0.75,
            'window': 'blackman'
        }
        
        result = await self.pipeline.run(iq_samples, config=config)
        
        self.assertIsNotNone(result)
    
    async def test_extract_peaks(self):
        """Test peak extraction"""
        iq_samples = TestDataGenerator.generate_iq_samples()
        
        result = await self.pipeline.run(iq_samples)
        
        self.assertIn('peaks', result)
        self.assertIsInstance(result['peaks'], list)


# ============================================================================
# Recording Pipeline Tests
# ============================================================================

class TestRecordingPipeline(unittest.TestCase):
    """Test recording pipeline functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.pipeline = RecordingPipeline()
        self.temp_dir = tempfile.mkdtemp()
    
    async def test_initialization(self):
        """Test pipeline initialization"""
        self.assertEqual(self.pipeline.name, "recording_pipeline")
    
    async def test_start_recording(self):
        """Test starting recording"""
        config = {
            'output_dir': self.temp_dir,
            'duration': 5,
            'sample_rate': 10e6
        }
        
        result = await self.pipeline.start_recording(config)
        
        self.assertIsNotNone(result)
        self.assertIn('recording_id', result)
    
    async def test_stop_recording(self):
        """Test stopping recording"""
        config = {
            'output_dir': self.temp_dir,
            'duration': 5,
            'sample_rate': 10e6
        }
        
        await self.pipeline.start_recording(config)
        result = await self.pipeline.stop_recording()
        
        self.assertIsNotNone(result)
        self.assertIn('duration', result)


# ============================================================================
# Playback Pipeline Tests
# ============================================================================

class TestPlaybackPipeline(unittest.TestCase):
    """Test playback pipeline functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.pipeline = PlaybackPipeline()
        self.test_file = Path(tempfile.mktemp(suffix='.iq'))
        
        # Create test file
        iq_data = TestDataGenerator.generate_iq_samples()
        iq_data.tofile(self.test_file)
    
    def tearDown(self):
        """Clean up test files"""
        if self.test_file.exists():
            self.test_file.unlink()
    
    async def test_initialization(self):
        """Test pipeline initialization"""
        self.assertEqual(self.pipeline.name, "playback_pipeline")
    
    async def test_load_file(self):
        """Test loading file for playback"""
        result = await self.pipeline.load_file(str(self.test_file))
        
        self.assertTrue(result)
        self.assertEqual(self.pipeline.current_file, str(self.test_file))
    
    async def test_play(self):
        """Test playback"""
        await self.pipeline.load_file(str(self.test_file))
        
        result = await self.pipeline.play()
        
        self.assertTrue(result)
    
    async def test_pause_resume(self):
        """Test pause and resume"""
        await self.pipeline.load_file(str(self.test_file))
        await self.pipeline.play()
        
        await self.pipeline.pause()
        self.assertTrue(self.pipeline.is_paused)
        
        await self.pipeline.resume()
        self.assertFalse(self.pipeline.is_paused)
    
    async def test_stop(self):
        """Test stop playback"""
        await self.pipeline.load_file(str(self.test_file))
        await self.pipeline.play()
        
        await self.pipeline.stop()
        
        self.assertFalse(self.pipeline.is_playing)
    
    async def test_seek(self):
        """Test seeking in playback"""
        await self.pipeline.load_file(str(self.test_file))
        
        position = await self.pipeline.seek(5.0)
        
        self.assertIsNotNone(position)


# ============================================================================
# Pipeline Factory Tests
# ============================================================================

class TestPipelineFactory(unittest.TestCase):
    """Test pipeline factory functions"""
    
    async def test_create_detection_pipeline(self):
        """Test creating detection pipeline"""
        pipeline = create_detection_pipeline()
        
        self.assertIsInstance(pipeline, DetectionPipeline)
        self.assertEqual(pipeline.name, "detection_pipeline")
    
    async def test_create_detection_pipeline_with_config(self):
        """Test creating detection pipeline with configuration"""
        config = {
            'ml_enabled': True,
            'remote_id_enabled': True,
            'confidence_threshold': 0.7
        }
        
        pipeline = create_detection_pipeline(config=config)
        
        self.assertIsInstance(pipeline, DetectionPipeline)
    
    async def test_create_spectrum_pipeline(self):
        """Test creating spectrum pipeline"""
        pipeline = create_spectrum_pipeline()
        
        self.assertIsInstance(pipeline, SpectrumPipeline)
        self.assertEqual(pipeline.name, "spectrum_pipeline")
    
    async def test_create_spectrum_pipeline_with_config(self):
        """Test creating spectrum pipeline with configuration"""
        config = {
            'fft_size': 4096,
            'overlap': 0.75,
            'peak_threshold': 0.8
        }
        
        pipeline = create_spectrum_pipeline(config=config)
        
        self.assertIsInstance(pipeline, SpectrumPipeline)


# ============================================================================
# End-to-End Pipeline Tests
# ============================================================================

class TestEndToEndPipelines(unittest.IsolatedAsyncioTestCase):
    """End-to-end tests for pipelines"""
    
    async def asyncSetUp(self):
        """Set up test fixtures"""
        self.detection_pipeline = DetectionPipeline()
        self.spectrum_pipeline = SpectrumPipeline()
    
    async def test_full_detection_workflow(self):
        """Test complete detection workflow"""
        # Generate test IQ samples
        iq_samples = TestDataGenerator.generate_iq_samples()
        
        # Run spectrum analysis first
        spectrum_result = await self.spectrum_pipeline.run(iq_samples)
        
        self.assertIsNotNone(spectrum_result)
        self.assertIn('psd', spectrum_result)
        
        # Then run detection
        detection_result = await self.detection_pipeline.run(iq_samples)
        
        self.assertIsNotNone(detection_result)
    
    async def test_pipeline_chaining(self):
        """Test chaining multiple pipelines"""
        iq_samples = TestDataGenerator.generate_iq_samples()
        
        # Create a combined pipeline
        combined = DetectionPipeline()
        
        # Add spectrum stage first
        spectrum_stage = MockPipelineStage("spectrum")
        combined.add_stage(spectrum_stage)
        
        # Add detection stage
        detection_stage = MockPipelineStage("detection")
        combined.add_stage(detection_stage)
        
        result = await combined.run(iq_samples)
        
        self.assertTrue(spectrum_stage.process_called)
        self.assertTrue(detection_stage.process_called)
    
    async def test_error_propagation(self):
        """Test error propagation through pipeline"""
        iq_samples = TestDataGenerator.generate_iq_samples()
        
        # Create pipeline with failing stage
        pipeline = DetectionPipeline()
        pipeline.add_stage(MockPipelineStage("stage1"))
        pipeline.add_stage(MockPipelineStage("stage2", should_fail=True))
        pipeline.add_stage(MockPipelineStage("stage3"))
        
        result = await pipeline.run(iq_samples)
        
        # Stage3 should not have been called
        self.assertEqual(result.status, PipelineStatus.FAILED)


# ============================================================================
# Performance Tests
# ============================================================================

class TestPipelinePerformance(unittest.TestCase):
    """Performance tests for pipelines"""
    
    async def test_detection_speed(self):
        """Test detection pipeline speed"""
        pipeline = DetectionPipeline()
        iq_samples = TestDataGenerator.generate_iq_samples(16384)
        
        import time
        start = time.time()
        
        for _ in range(10):
            await pipeline.run(iq_samples)
        
        elapsed = time.time() - start
        avg_time = elapsed / 10
        
        # Should process in under 0.5 seconds per iteration
        self.assertLess(avg_time, 0.5)
    
    async def test_spectrum_speed(self):
        """Test spectrum pipeline speed"""
        pipeline = SpectrumPipeline()
        iq_samples = TestDataGenerator.generate_iq_samples(16384)
        
        import time
        start = time.time()
        
        for _ in range(10):
            await pipeline.run(iq_samples)
        
        elapsed = time.time() - start
        avg_time = elapsed / 10
        
        # Should process in under 0.3 seconds per iteration
        self.assertLess(avg_time, 0.3)


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestPipelineErrorHandling(unittest.TestCase):
    """Test pipeline error handling"""
    
    async def test_handle_invalid_input(self):
        """Test handling invalid input"""
        pipeline = DetectionPipeline()
        
        with self.assertRaises(ValueError):
            await pipeline.run(None)
    
    async def test_handle_empty_input(self):
        """Test handling empty input"""
        pipeline = DetectionPipeline()
        empty_samples = np.array([], dtype=np.complex64)
        
        result = await pipeline.run(empty_samples)
        
        self.assertEqual(result.status, PipelineStatus.FAILED)
        self.assertIsNotNone(result.error)
    
    async def test_handle_malformed_config(self):
        """Test handling malformed configuration"""
        pipeline = DetectionPipeline()
        iq_samples = TestDataGenerator.generate_iq_samples()
        
        # Invalid config should be handled gracefully
        result = await pipeline.run(iq_samples, config=None)
        
        self.assertIsNotNone(result)


# ============================================================================
# Run Tests
# ============================================================================

async def run_async_tests():
    """Run async test methods"""
    test_classes = [
        TestPipelineStage,
        TestDetectionPipeline,
        TestSpectrumPipeline,
        TestRecordingPipeline,
        TestPlaybackPipeline,
        TestPipelineFactory,
        TestPipelinePerformance,
        TestPipelineErrorHandling
    ]
    
    for test_class in test_classes:
        print(f"\nRunning {test_class.__name__}...")
        instance = test_class()
        
        # Run async methods
        for method_name in dir(instance):
            if method_name.startswith('test_') and asyncio.iscoroutinefunction(getattr(instance, method_name)):
                method = getattr(instance, method_name)
                await method()


if __name__ == '__main__':
    # Run async tests
    import asyncio
    asyncio.run(run_async_tests())
    
    # Run regular unittest suite
    unittest.main(verbosity=2)