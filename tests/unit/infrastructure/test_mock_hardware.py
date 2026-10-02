#!/usr/bin/env python3
"""
Unit Tests for Mock Hardware Module

Tests for mock SDR hardware implementation, signal generation,
scenario management, and hardware simulation capabilities.
"""

import asyncio
import numpy as np
import unittest
from unittest.mock import Mock, patch, AsyncMock, MagicMock, call
from datetime import datetime
import tempfile
import json
from pathlib import Path

# Import modules to test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from infrastructure.hardware.mock_hardware import (
    MockSDR,
    MockScenario,
    MockSignalGenerator
)
from infrastructure.hardware.hardware_factory import (
    HardwareFactory,
    HardwareType
)
from infrastructure.hardware.sdr_base import SDRBase


# ============================================================================
# Test Data Generators
# ============================================================================

class TestDataGenerator:
    """Generate test data for mock hardware tests"""
    
    @staticmethod
    def generate_test_config() -> dict:
        """Generate test configuration"""
        return {
            'sample_rate': 10e6,
            'center_freq': 2.44e9,
            'gains': {
                'lna_gain': 16,
                'vga_gain': 20,
                'amp_enable': False
            },
            'mock': {
                'synthetic_mode': True,
                'simulate_latency_ms': 5,
                'simulate_errors': False,
                'auto_inject': True,
                'inject_probability': 0.3
            }
        }
    
    @staticmethod
    def generate_test_scenario() -> MockScenario:
        """Generate test scenario"""
        return MockScenario(
            name="test_drone",
            drone_type="DJI Mavic 3",
            center_freq=2.44e9,
            bandwidth=20e6,
            snr_db=15,
            duration=30.0
        )


# ============================================================================
# Mock Scenario Tests
# ============================================================================

class TestMockScenario(unittest.TestCase):
    """Test mock scenario data class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.scenario = TestDataGenerator.generate_test_scenario()
    
    def test_scenario_creation(self):
        """Test scenario creation"""
        self.assertEqual(self.scenario.name, "test_drone")
        self.assertEqual(self.scenario.drone_type, "DJI Mavic 3")
        self.assertEqual(self.scenario.center_freq, 2.44e9)
        self.assertEqual(self.scenario.bandwidth, 20e6)
        self.assertEqual(self.scenario.snr_db, 15)
        self.assertEqual(self.scenario.duration, 30.0)
    
    def test_scenario_with_file_path(self):
        """Test scenario with file path"""
        scenario = MockScenario(
            name="playback",
            drone_type="DJI Mavic 3",
            center_freq=2.44e9,
            bandwidth=20e6,
            snr_db=15,
            duration=30.0,
            file_path=Path("/path/to/test.iq")
        )
        
        self.assertIsNotNone(scenario.file_path)
        self.assertEqual(scenario.file_path, Path("/path/to/test.iq"))


# ============================================================================
# Mock Signal Generator Tests
# ============================================================================

class TestMockSignalGenerator(unittest.TestCase):
    """Test mock signal generator"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.generator = MockSignalGenerator()
    
    def test_generate_noise(self):
        """Test noise generation"""
        samples = self.generator.generate_noise(1024, -100)
        
        self.assertEqual(len(samples), 1024)
        self.assertEqual(samples.dtype, np.complex64)
        
        # Check power is roughly correct
        power = np.mean(np.abs(samples)**2)
        expected_power = 10 ** (-100 / 10)
        self.assertAlmostEqual(power, expected_power, delta=expected_power * 0.5)
    
    def test_generate_tone(self):
        """Test tone generation"""
        samples = self.generator.generate_tone(1024, 10e6, 2.44e9, 10e6)
        
        self.assertEqual(len(samples), 1024)
        self.assertEqual(samples.dtype, np.complex64)
        
        # Check that signal has expected frequency characteristics
        fft_data = np.fft.fft(samples)
        peak_idx = np.argmax(np.abs(fft_data))
        
        # Signal should have a peak
        self.assertGreater(np.max(np.abs(fft_data)), 0)
    
    def test_generate_ofdm_signal(self):
        """Test OFDM signal generation"""
        samples = self.generator.generate_ofdm_signal(10240, 20e6, 2.44e9)
        
        self.assertEqual(len(samples), 10240)
        self.assertEqual(samples.dtype, np.complex64)
        
        # Check that OFDM signal has PAPR > 1
        papr = np.max(np.abs(samples)**2) / np.mean(np.abs(samples)**2)
        self.assertGreater(papr, 1.0)
    
    def test_generate_fm_signal(self):
        """Test FM signal generation"""
        samples = self.generator.generate_fm_signal(10240, 10e6, 2.44e9)
        
        self.assertEqual(len(samples), 10240)
        self.assertEqual(samples.dtype, np.complex64)
        
        # FM signal should have constant envelope
        envelope_variance = np.var(np.abs(samples))
        self.assertLess(envelope_variance, 0.1)
    
    def test_generate_drone_signal_dji(self):
        """Test DJI drone signal generation"""
        samples = self.generator.generate_drone_signal(10240, 10e6, "dji")
        
        self.assertEqual(len(samples), 10240)
        self.assertGreater(np.max(np.abs(samples)), 0)
    
    def test_generate_drone_signal_fpv(self):
        """Test FPV drone signal generation"""
        samples = self.generator.generate_drone_signal(10240, 10e6, "fpv")
        
        self.assertEqual(len(samples), 10240)
        self.assertGreater(np.max(np.abs(samples)), 0)
    
    def test_generate_interference_wifi(self):
        """Test WiFi interference generation"""
        samples = self.generator.generate_interference_wifi(10240, 10e6)
        
        self.assertEqual(len(samples), 10240)
        self.assertGreater(np.max(np.abs(samples)), 0)
    
    def test_apply_doppler_shift(self):
        """Test Doppler shift application"""
        samples = np.ones(1024, dtype=np.complex64)
        shifted = self.generator.apply_doppler_shift(samples, 10e6, 50)
        
        self.assertEqual(len(shifted), 1024)
        # Phase should vary across samples
        self.assertNotEqual(np.angle(shifted[0]), np.angle(shifted[-1]))


# ============================================================================
# Mock SDR Tests
# ============================================================================

class TestMockSDR(unittest.TestCase):
    """Test Mock SDR hardware implementation"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_sdr = MockSDR()
        self.config = TestDataGenerator.generate_test_config()
    
    def test_initialization(self):
        """Test mock SDR initialization"""
        self.assertIsNotNone(self.mock_sdr)
        self.assertFalse(self.mock_sdr.is_streaming)
        self.assertEqual(self.mock_sdr.sample_rate, 10e6)
        self.assertEqual(self.mock_sdr.center_freq, 2.4e9)
    
    def test_initialize_with_config(self):
        """Test initialization with configuration"""
        success = self.mock_sdr.initialize(self.config)
        
        self.assertTrue(success)
        self.assertEqual(self.mock_sdr.sample_rate, 10e6)
        self.assertEqual(self.mock_sdr.center_freq, 2.44e9)
        self.assertEqual(self.mock_sdr.lna_gain, 16)
        self.assertEqual(self.mock_sdr.vga_gain, 20)
    
    def test_tune(self):
        """Test frequency tuning"""
        test_freq = 2.45e9
        self.mock_sdr.tune(test_freq)
        
        self.assertEqual(self.mock_sdr.center_freq, test_freq)
    
    def test_set_gain(self):
        """Test gain setting"""
        self.mock_sdr.set_gain('lna', 32)
        self.assertEqual(self.mock_sdr.lna_gain, 32)
        
        self.mock_sdr.set_gain('vga', 40)
        self.assertEqual(self.mock_sdr.vga_gain, 40)
        
        self.mock_sdr.set_gain('amp', True)
        self.assertTrue(self.mock_sdr.amp_enable)
    
    def test_read_samples(self):
        """Test reading samples"""
        num_samples = 1024
        samples = self.mock_sdr.read_samples(num_samples)
        
        self.assertEqual(len(samples), num_samples)
        self.assertEqual(samples.dtype, np.complex64)
    
    def test_read_samples_with_latency(self):
        """Test reading samples with simulated latency"""
        import time
        
        self.mock_sdr.simulate_latency_ms = 10
        
        start = time.time()
        samples = self.mock_sdr.read_samples(1024)
        elapsed = (time.time() - start) * 1000
        
        self.assertGreaterEqual(elapsed, 9)  # Allow small误差
        self.assertEqual(len(samples), 1024)
    
    def test_read_samples_with_error(self):
        """Test reading samples with simulated errors"""
        self.mock_sdr.simulate_errors = True
        self.mock_sdr.error_rate = 1.0  # Always fail
        
        with self.assertRaises(RuntimeError):
            self.mock_sdr.read_samples(1024)
    
    def test_start_stop_streaming(self):
        """Test starting and stopping streaming mode"""
        self.mock_sdr.start_streaming()
        self.assertTrue(self.mock_sdr.is_streaming)
        
        self.mock_sdr.stop_streaming()
        self.assertFalse(self.mock_sdr.is_streaming)
    
    def test_get_stream_samples(self):
        """Test getting samples from streaming buffer"""
        self.mock_sdr.start_streaming()
        
        samples = self.mock_sdr.get_stream_samples(1024)
        
        self.assertEqual(len(samples), 1024)
        
        self.mock_sdr.stop_streaming()
    
    def test_set_scenario(self):
        """Test setting scenario"""
        # List available scenarios
        scenarios = self.mock_sdr.list_scenarios()
        self.assertGreater(len(scenarios), 0)
        
        # Set a valid scenario
        test_scenario = scenarios[0]
        success = self.mock_sdr.set_scenario(test_scenario)
        
        self.assertTrue(success)
        self.assertEqual(self.mock_sdr.current_scenario.name, test_scenario)
    
    def test_set_invalid_scenario(self):
        """Test setting invalid scenario"""
        success = self.mock_sdr.set_scenario("invalid_scenario")
        
        self.assertFalse(success)
    
    def test_inject_drone(self):
        """Test injecting drone signal"""
        self.mock_sdr.inject_drone("DJI Mavic 3", 2.44e9)
        
        self.assertEqual(self.mock_sdr.current_scenario.drone_type, "DJI Mavic 3")
        self.assertEqual(self.mock_sdr.center_freq, 2.44e9)
    
    def test_auto_select_scenario(self):
        """Test automatic scenario selection"""
        # Tune to 2.4 GHz band (should select DJI or noise)
        self.mock_sdr.tune(2.44e9)
        self.assertIn(self.mock_sdr.current_scenario.name, 
                     ['dji_mavic_2.4g_active', 'noise_only'])
        
        # Tune to 5.8 GHz band
        self.mock_sdr.tune(5.8e9)
        self.assertIn(self.mock_sdr.current_scenario.name,
                     ['dji_mavic_5.8g_active', 'fpv_analog_5.8g', 'noise_only'])
    
    def test_close(self):
        """Test closing mock SDR"""
        self.mock_sdr.start_streaming()
        self.mock_sdr.close()
        
        self.assertFalse(self.mock_sdr.is_streaming)
        self.assertIsNone(self.mock_sdr.loaded_samples)


# ============================================================================
# Hardware Factory Tests
# ============================================================================

class TestHardwareFactory(unittest.TestCase):
    """Test hardware factory pattern"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = TestDataGenerator.generate_test_config()
    
    def test_create_mock_hardware(self):
        """Test creating mock hardware directly"""
        hardware = HardwareFactory.create_hardware(
            hardware_type=HardwareType.MOCK,
            config=self.config
        )
        
        self.assertIsInstance(hardware, MockSDR)
    
    def test_create_hardware_with_force_mock(self):
        """Test forcing mock hardware"""
        hardware = HardwareFactory.create_hardware(
            force_mock=True,
            config=self.config
        )
        
        self.assertIsInstance(hardware, MockSDR)
    
    def test_create_hardware_auto_fallback(self):
        """Test automatic fallback to mock"""
        hardware = HardwareFactory.create_hardware(
            hardware_type=HardwareType.AUTO,
            config=self.config
        )
        
        # Should fall back to mock since real hardware likely not present
        self.assertIsInstance(hardware, MockSDR)
    
    def test_is_mock_hardware(self):
        """Test mock hardware detection"""
        hardware = MockSDR()
        
        self.assertTrue(HardwareFactory.is_mock_hardware(hardware))
        
        # Create a real hardware stub (would be False)
        from infrastructure.hardware.sdr_base import SDRBase
        class RealHardware(SDRBase):
            pass
        
        real_hardware = RealHardware()
        self.assertFalse(HardwareFactory.is_mock_hardware(real_hardware))


# ============================================================================
# Asynchronous Tests
# ============================================================================

class TestMockSDRAsync(unittest.IsolatedAsyncioTestCase):
    """Async tests for mock SDR"""
    
    async def asyncSetUp(self):
        """Set up async test fixtures"""
        self.mock_sdr = MockSDR()
        self.config = TestDataGenerator.generate_test_config()
        self.mock_sdr.initialize(self.config)
    
    async def test_async_read_samples(self):
        """Test async reading of samples"""
        samples = await asyncio.get_event_loop().run_in_executor(
            None, self.mock_sdr.read_samples, 2048
        )
        
        self.assertEqual(len(samples), 2048)
    
    async def test_continuous_streaming(self):
        """Test continuous streaming over time"""
        self.mock_sdr.start_streaming()
        
        samples_list = []
        for i in range(5):
            samples = await asyncio.get_event_loop().run_in_executor(
                None, self.mock_sdr.get_stream_samples, 1024
            )
            samples_list.append(samples)
            await asyncio.sleep(0.01)
        
        self.mock_sdr.stop_streaming()
        
        self.assertEqual(len(samples_list), 5)
        for samples in samples_list:
            self.assertEqual(len(samples), 1024)
    
    async def test_concurrent_reads(self):
        """Test concurrent reads from multiple coroutines"""
        async def read_samples(num):
            return await asyncio.get_event_loop().run_in_executor(
                None, self.mock_sdr.read_samples, 1024
            )
        
        # Run multiple concurrent reads
        results = await asyncio.gather(*[read_samples(i) for i in range(10)])
        
        self.assertEqual(len(results), 10)
        for samples in results:
            self.assertEqual(len(samples), 1024)


# ============================================================================
# Integration Tests
# ============================================================================

class TestMockHardwareIntegration(unittest.TestCase):
    """Integration tests for mock hardware"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_sdr = MockSDR()
        self.mock_sdr.initialize(TestDataGenerator.generate_test_config())
    
    def test_signal_chain(self):
        """Test complete signal chain"""
        # Configure mock for drone detection
        self.mock_sdr.inject_drone("DJI Mavic 3", 2.44e9)
        
        # Read samples
        samples = self.mock_sdr.read_samples(16384)
        
        # Verify samples have expected characteristics
        power = np.mean(np.abs(samples)**2)
        self.assertGreater(power, 0)
        
        # Check for signal peaks
        fft_data = np.fft.fftshift(np.fft.fft(samples))
        peak_power = np.max(np.abs(fft_data)**2)
        avg_power = np.mean(np.abs(fft_data)**2)
        papr = peak_power / avg_power
        
        # Signal should have some peaks (PAPR > 1)
        self.assertGreater(papr, 1.0)
    
    def test_frequency_hopping_simulation(self):
        """Test frequency hopping simulation"""
        self.mock_sdr.frequency_hop = True
        
        # Read samples over time to see frequency changes
        samples = []
        for i in range(10):
            chunk = self.mock_sdr.read_samples(8192)
            samples.append(chunk)
            self.mock_sdr.tune(2.44e9 + i * 1e6)
        
        self.assertEqual(len(samples), 10)
    
    def test_scenario_transition(self):
        """Test smooth scenario transitions"""
        # Start with noise
        self.mock_sdr.set_scenario("noise_only")
        noise_samples = self.mock_sdr.read_samples(1024)
        
        # Switch to drone
        self.mock_sdr.set_scenario("dji_mavic_2.4g_active")
        drone_samples = self.mock_sdr.read_samples(1024)
        
        # Drone should have higher power than noise
        noise_power = np.mean(np.abs(noise_samples)**2)
        drone_power = np.mean(np.abs(drone_samples)**2)
        
        self.assertGreater(drone_power, noise_power)


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================

class TestMockHardwareEdgeCases(unittest.TestCase):
    """Test edge cases and error handling"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_sdr = MockSDR()
    
    def test_initialize_without_config(self):
        """Test initialization without config"""
        success = self.mock_sdr.initialize({})
        
        self.assertTrue(success)
        self.assertEqual(self.mock_sdr.sample_rate, 10e6)
    
    def test_read_zero_samples(self):
        """Test reading zero samples"""
        samples = self.mock_sdr.read_samples(0)
        
        self.assertEqual(len(samples), 0)
    
    def test_read_negative_samples(self):
        """Test reading negative samples"""
        samples = self.mock_sdr.read_samples(-100)
        
        self.assertEqual(len(samples), 0)
    
    def test_set_scenario_nonexistent(self):
        """Test setting nonexistent scenario"""
        success = self.mock_sdr.set_scenario("nonexistent_scenario")
        
        self.assertFalse(success)
    
    def test_inject_drone_invalid_type(self):
        """Test injecting drone with invalid type"""
        # Should not crash, use default behavior
        self.mock_sdr.inject_drone("Invalid Type", 2.44e9)
        
        self.assertEqual(self.mock_sdr.current_scenario.drone_type, "Invalid Type")
    
    def test_get_stream_samples_when_not_streaming(self):
        """Test getting stream samples when not streaming"""
        samples = self.mock_sdr.get_stream_samples(1024)
        
        self.assertEqual(len(samples), 0)
    
    def test_close_when_already_closed(self):
        """Test closing already closed device"""
        self.mock_sdr.close()
        self.mock_sdr.close()  # Should not raise exception


# ============================================================================
# Performance Tests
# ============================================================================

class TestMockHardwarePerformance(unittest.TestCase):
    """Performance tests for mock hardware"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_sdr = MockSDR()
        self.mock_sdr.initialize(TestDataGenerator.generate_test_config())
    
    def test_sample_generation_rate(self):
        """Test sample generation rate"""
        import time
        
        num_samples = 10_000_000  # 10 million samples
        num_sdr_samples = 10e6
        
        start = time.time()
        samples = self.mock_sdr.read_samples(num_samples)
        elapsed = time.time() - start
        
        # Should be able to generate at least 10 MS/s
        rate = num_samples / elapsed
        self.assertGreater(rate, 5e6)  # At least 5 MS/s
    
    def test_memory_usage(self):
        """Test memory usage stability"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024
        
        # Generate many samples
        for i in range(10):
            samples = self.mock_sdr.read_samples(1_000_000)
            self.assertEqual(len(samples), 1_000_000)
        
        final_memory = process.memory_info().rss / 1024 / 1024
        memory_increase = final_memory - initial_memory
        
        # Memory should not increase significantly
        self.assertLess(memory_increase, 50)  # Less than 50 MB increase


# ============================================================================
# Configuration Tests
# ============================================================================

class TestMockHardwareConfig(unittest.TestCase):
    """Test mock hardware configuration"""
    
    def test_config_with_synthetic_mode(self):
        """Test synthetic mode configuration"""
        config = {
            'mock': {
                'synthetic_mode': True,
                'simulate_latency_ms': 0
            }
        }
        
        mock_sdr = MockSDR()
        mock_sdr.initialize(config)
        
        self.assertTrue(mock_sdr.synthetic_mode)
    
    def test_config_with_playback_mode(self):
        """Test playback mode configuration"""
        config = {
            'mock': {
                'synthetic_mode': False,
                'simulate_latency_ms': 0
            }
        }
        
        mock_sdr = MockSDR()
        mock_sdr.initialize(config)
        
        self.assertFalse(mock_sdr.synthetic_mode)
    
    def test_config_with_latency(self):
        """Test latency configuration"""
        config = {
            'mock': {
                'simulate_latency_ms': 25
            }
        }
        
        mock_sdr = MockSDR()
        mock_sdr.initialize(config)
        
        self.assertEqual(mock_sdr.simulate_latency_ms, 25)
    
    def test_config_with_errors(self):
        """Test error simulation configuration"""
        config = {
            'mock': {
                'simulate_errors': True,
                'error_rate': 0.05
            }
        }
        
        mock_sdr = MockSDR()
        mock_sdr.initialize(config)
        
        self.assertTrue(mock_sdr.simulate_errors)
        self.assertEqual(mock_sdr.error_rate, 0.05)


# ============================================================================
# Statistics and Monitoring Tests
# ============================================================================

class TestMockHardwareStats(unittest.TestCase):
    """Test mock hardware statistics"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_sdr = MockSDR()
        config = TestDataGenerator.generate_test_config()
        self.mock_sdr.initialize(config)
    
    def test_get_stats(self):
        """Test getting device statistics"""
        # Perform some operations
        self.mock_sdr.read_samples(1024)
        self.mock_sdr.tune(2.45e9)
        self.mock_sdr.set_gain('lna', 24)
        
        # In a real implementation, would have stats method
        # This is a placeholder for future implementation
        pass


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == '__main__':
    # Run with verbose output
    unittest.main(verbosity=2)