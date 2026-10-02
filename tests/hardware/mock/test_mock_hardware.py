#!/usr/bin/env python3
"""
Mock Hardware Tests

Tests for mock hardware implementation including:
- Signal generation (noise, tone, OFDM, FM, drone signals)
- Scenario management
- Frequency tuning and gain control
- Sample reading and streaming
- Error simulation
- Performance benchmarking
- Multi-device support
- Configuration validation
- Statistics collection
"""

import unittest
import numpy as np
import time
import sys
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from collections import defaultdict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Import mock hardware modules
from infrastructure.hardware.mock_hardware import (
    MockSDR,
    MockScenario,
    MockSignalGenerator
)
from infrastructure.hardware.hardware_factory import HardwareFactory, HardwareType


# ============================================================================
# Test Configuration
# ============================================================================

class MockTestConfig:
    """Configuration for mock hardware tests"""
    
    # Test parameters
    SAMPLE_RATE = 10e6  # 10 MHz
    CENTER_FREQ = 2.44e9  # 2.44 GHz
    NUM_SAMPLES_SMALL = 1024
    NUM_SAMPLES_MEDIUM = 16384
    NUM_SAMPLES_LARGE = 100000
    
    # Test durations (seconds)
    SHORT_DURATION = 0.5
    MEDIUM_DURATION = 2
    LONG_DURATION = 5
    
    # Performance thresholds
    MIN_GENERATION_RATE_MSPS = 50  # Minimum 50 MS/s
    MAX_LATENCY_MS = 10  # Maximum 10ms latency
    
    # Error simulation
    ERROR_RATE = 0.01  # 1% error rate
    SIMULATE_LATENCY_MS = 5
    
    # Scenario names
    SCENARIOS = [
        'dji_mavic_2.4g_active',
        'dji_mavic_5.8g_active',
        'fpv_analog_5.8g',
        'noise_only',
        'interference_wifi'
    ]


# ============================================================================
# Test Helpers
# ============================================================================

def measure_generation_rate(mock_sdr: MockSDR, num_reads: int = 10) -> float:
    """Measure sample generation rate in MS/s"""
    total_samples = 0
    start_time = time.time()
    
    for _ in range(num_reads):
        samples = mock_sdr.read_samples(MockTestConfig.NUM_SAMPLES_MEDIUM)
        total_samples += len(samples)
    
    elapsed = time.time() - start_time
    rate = total_samples / elapsed / 1e6
    return rate


# ============================================================================
# Mock Signal Generator Tests
# ============================================================================

class TestMockSignalGenerator(unittest.TestCase):
    """Test mock signal generator functionality"""
    
    def setUp(self):
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
        
        # Peak should be present (not at DC)
        self.assertGreater(peak_idx, 0)
        self.assertLess(peak_idx, len(fft_data) - 1)
    
    def test_generate_ofdm_signal(self):
        """Test OFDM signal generation"""
        samples = self.generator.generate_ofdm_signal(10240, 20e6, 2.44e9)
        
        self.assertEqual(len(samples), 10240)
        self.assertEqual(samples.dtype, np.complex64)
        
        # OFDM should have PAPR > 1
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
    
    def test_generate_interference_bluetooth(self):
        """Test Bluetooth interference generation"""
        samples = self.generator.generate_interference_bluetooth(10240, 10e6)
        
        self.assertEqual(len(samples), 10240)
        self.assertGreater(np.max(np.abs(samples)), 0)
    
    def test_apply_doppler_shift(self):
        """Test Doppler shift application"""
        samples = np.ones(1024, dtype=np.complex64)
        shifted = self.generator.apply_doppler_shift(samples, 10e6, 50)
        
        self.assertEqual(len(shifted), 1024)
        # Phase should vary across samples
        self.assertNotEqual(np.angle(shifted[0]), np.angle(shifted[-1]))
    
    def test_apply_multipath(self):
        """Test multipath fading application"""
        samples = np.ones(1024, dtype=np.complex64)
        faded = self.generator.apply_multipath(samples, 10e6)
        
        self.assertEqual(len(faded), 1024)
        # Faded signal should have variations
        self.assertNotEqual(np.std(np.abs(faded)), 0)


# ============================================================================
# Mock SDR Basic Tests
# ============================================================================

class TestMockSDRBasic(unittest.TestCase):
    """Basic mock SDR functionality tests"""
    
    def setUp(self):
        self.mock_sdr = MockSDR()
    
    def test_initialization(self):
        """Test mock SDR initialization"""
        self.assertIsNotNone(self.mock_sdr)
        self.assertFalse(self.mock_sdr.is_streaming)
        self.assertEqual(self.mock_sdr.sample_rate, 10e6)
        self.assertEqual(self.mock_sdr.center_freq, 2.4e9)
    
    def test_initialize_with_config(self):
        """Test initialization with configuration"""
        config = {
            'sample_rate': 20e6,
            'center_freq': 2.45e9,
            'gains': {'lna_gain': 24, 'vga_gain': 30, 'amp_enable': True},
            'mock': {'synthetic_mode': True, 'simulate_latency_ms': 10}
        }
        
        success = self.mock_sdr.initialize(config)
        
        self.assertTrue(success)
        self.assertEqual(self.mock_sdr.sample_rate, 20e6)
        self.assertEqual(self.mock_sdr.center_freq, 2.45e9)
        self.assertEqual(self.mock_sdr.lna_gain, 24)
        self.assertEqual(self.mock_sdr.vga_gain, 30)
        self.assertTrue(self.mock_sdr.amp_enable)
        self.assertTrue(self.mock_sdr.synthetic_mode)
        self.assertEqual(self.mock_sdr.simulate_latency_ms, 10)
    
    def test_tune_frequency(self):
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
        samples = self.mock_sdr.read_samples(1024)
        
        self.assertEqual(len(samples), 1024)
        self.assertEqual(samples.dtype, np.complex64)
    
    def test_read_samples_with_latency(self):
        """Test reading samples with simulated latency"""
        self.mock_sdr.simulate_latency_ms = 10
        
        start = time.time()
        samples = self.mock_sdr.read_samples(1024)
        elapsed = (time.time() - start) * 1000
        
        self.assertGreaterEqual(elapsed, 9)  # Allow small tolerance
        self.assertEqual(len(samples), 1024)
    
    def test_start_stop_streaming(self):
        """Test starting and stopping streaming"""
        self.mock_sdr.start_streaming()
        self.assertTrue(self.mock_sdr.is_streaming)
        
        self.mock_sdr.stop_streaming()
        self.assertFalse(self.mock_sdr.is_streaming)
    
    def test_get_stream_samples(self):
        """Test getting samples from stream"""
        self.mock_sdr.start_streaming()
        
        samples = self.mock_sdr.get_stream_samples(1024)
        
        self.assertEqual(len(samples), 1024)
        
        self.mock_sdr.stop_streaming()


# ============================================================================
# Mock SDR Scenario Tests
# ============================================================================

class TestMockSDRScenarios(unittest.TestCase):
    """Mock SDR scenario management tests"""
    
    def setUp(self):
        self.mock_sdr = MockSDR()
        self.mock_sdr.initialize({})
    
    def test_list_scenarios(self):
        """Test listing available scenarios"""
        scenarios = self.mock_sdr.list_scenarios()
        
        self.assertIsInstance(scenarios, list)
        self.assertGreater(len(scenarios), 0)
        
        for scenario in MockTestConfig.SCENARIOS:
            self.assertIn(scenario, scenarios)
    
    def test_set_scenario(self):
        """Test setting scenario"""
        test_scenario = MockTestConfig.SCENARIOS[0]
        success = self.mock_sdr.set_scenario(test_scenario)
        
        self.assertTrue(success)
        self.assertEqual(self.mock_sdr.current_scenario.name, test_scenario)
    
    def test_set_invalid_scenario(self):
        """Test setting invalid scenario"""
        success = self.mock_sdr.set_scenario("invalid_scenario")
        
        self.assertFalse(success)
    
    def test_scenario_signal_generation(self):
        """Test that different scenarios produce different signals"""
        signals = {}
        
        for scenario in MockTestConfig.SCENARIOS[:3]:
            self.mock_sdr.set_scenario(scenario)
            samples = self.mock_sdr.read_samples(4096)
            signals[scenario] = samples
        
        # Noise scenario should have lower power
        noise_power = np.mean(np.abs(signals['noise_only'])**2)
        drone_power = np.mean(np.abs(signals['dji_mavic_2.4g_active'])**2)
        
        self.assertLess(noise_power, drone_power)
    
    def test_inject_drone(self):
        """Test injecting drone signal"""
        self.mock_sdr.inject_drone("DJI Mavic 3", 2.44e9)
        
        self.assertEqual(self.mock_sdr.current_scenario.drone_type, "DJI Mavic 3")
        self.assertEqual(self.mock_sdr.center_freq, 2.44e9)
    
    def test_auto_select_scenario(self):
        """Test automatic scenario selection based on frequency"""
        # Tune to 2.4 GHz band
        self.mock_sdr.tune(2.44e9)
        self.assertIn(self.mock_sdr.current_scenario.name, 
                     ['dji_mavic_2.4g_active', 'noise_only'])
        
        # Tune to 5.8 GHz band
        self.mock_sdr.tune(5.8e9)
        self.assertIn(self.mock_sdr.current_scenario.name,
                     ['dji_mavic_5.8g_active', 'fpv_analog_5.8g', 'noise_only'])


# ============================================================================
# Error Simulation Tests
# ============================================================================

class TestMockSDRErrors(unittest.TestCase):
    """Mock SDR error simulation tests"""
    
    def setUp(self):
        self.mock_sdr = MockSDR()
        self.mock_sdr.initialize({
            'mock': {
                'simulate_errors': True,
                'error_rate': MockTestConfig.ERROR_RATE
            }
        })
    
    def test_error_simulation_enabled(self):
        """Test error simulation enablement"""
        self.assertTrue(self.mock_sdr.simulate_errors)
        self.assertEqual(self.mock_sdr.error_rate, MockTestConfig.ERROR_RATE)
    
    def test_read_with_errors(self):
        """Test reading samples with simulated errors"""
        errors = 0
        attempts = 50
        
        for _ in range(attempts):
            try:
                samples = self.mock_sdr.read_samples(1024)
                self.assertEqual(len(samples), 1024)
            except RuntimeError:
                errors += 1
        
        error_rate = errors / attempts
        print(f"\n  Error rate: {error_rate:.2%} (expected {MockTestConfig.ERROR_RATE:.2%})")
        
        # Error rate should be roughly as configured
        self.assertGreater(error_rate, 0)
        self.assertLess(error_rate, MockTestConfig.ERROR_RATE * 3)
    
    def test_streaming_with_errors(self):
        """Test streaming with simulated errors"""
        self.mock_sdr.start_streaming()
        
        errors = 0
        for _ in range(20):
            try:
                samples = self.mock_sdr.get_stream_samples(1024)
                self.assertEqual(len(samples), 1024)
            except RuntimeError:
                errors += 1
        
        self.mock_sdr.stop_streaming()
        
        # Should have some errors but not all
        self.assertGreater(errors, 0)
        self.assertLess(errors, 20)


# ============================================================================
# Performance Tests
# ============================================================================

class TestMockSDRPerformance(unittest.TestCase):
    """Mock SDR performance tests"""
    
    def setUp(self):
        self.mock_sdr = MockSDR()
        self.mock_sdr.initialize({})
    
    def test_generation_rate(self):
        """Test sample generation rate"""
        rate = measure_generation_rate(self.mock_sdr, 20)
        
        print(f"\n  Generation rate: {rate:.1f} MS/s")
        
        # Should achieve high generation rate
        self.assertGreater(rate, MockTestConfig.MIN_GENERATION_RATE_MSPS)
    
    def test_read_latency(self):
        """Test read operation latency"""
        latencies = []
        
        for _ in range(50):
            start = time.time()
            samples = self.mock_sdr.read_samples(MockTestConfig.NUM_SAMPLES_MEDIUM)
            latency = (time.time() - start) * 1000
            latencies.append(latency)
        
        avg_latency = np.mean(latencies)
        max_latency = np.max(latencies)
        
        print(f"\n  Average latency: {avg_latency:.2f} ms")
        print(f"  Max latency: {max_latency:.2f} ms")
        
        self.assertLess(avg_latency, MockTestConfig.MAX_LATENCY_MS)
    
    def test_continuous_generation(self):
        """Test continuous generation over time"""
        sample_counts = []
        
        for i in range(100):
            samples = self.mock_sdr.read_samples(MockTestConfig.NUM_SAMPLES_MEDIUM)
            sample_counts.append(len(samples))
            time.sleep(0.01)
        
        consistency = np.std(sample_counts) / np.mean(sample_counts)
        
        print(f"\n  Consistency: {(1 - consistency)*100:.1f}%")
        
        # Should be very consistent
        self.assertLess(consistency, 0.05)


# ============================================================================
# Statistical Property Tests
# ============================================================================

class TestMockSDRStatistics(unittest.TestCase):
    """Statistical property tests for mock signals"""
    
    def setUp(self):
        self.mock_sdr = MockSDR()
        self.mock_sdr.initialize({})
    
    def test_noise_statistics(self):
        """Test noise statistical properties"""
        self.mock_sdr.set_scenario("noise_only")
        samples = self.mock_sdr.read_samples(100000)
        
        real = np.real(samples)
        imag = np.imag(samples)
        
        # Mean should be near zero
        self.assertAlmostEqual(np.mean(real), 0, delta=0.01)
        self.assertAlmostEqual(np.mean(imag), 0, delta=0.01)
        
        # Variance should be consistent
        real_var = np.var(real)
        imag_var = np.var(imag)
        self.assertAlmostEqual(real_var, imag_var, delta=real_var * 0.1)
        
        # Distribution should be approximately Gaussian
        from scipy import stats
        _, p_value_real = stats.normaltest(real[:5000])
        _, p_value_imag = stats.normaltest(imag[:5000])
        
        # p-value > 0.01 indicates normal distribution
        self.assertGreater(p_value_real, 0.01)
        self.assertGreater(p_value_imag, 0.01)
    
    def test_tone_statistics(self):
        """Test tone signal statistical properties"""
        # Set up a scenario that produces a tone
        # For testing, we can manually generate
        from infrastructure.hardware.mock_hardware import MockSignalGenerator
        generator = MockSignalGenerator()
        samples = generator.generate_tone(10000, 1e6, 2.44e9, 10e6)
        
        # Check mean power
        power = np.mean(np.abs(samples)**2)
        self.assertGreater(power, 0)
        
        # Check PAPR (should be low for tone)
        papr = np.max(np.abs(samples)**2) / power
        self.assertLess(papr, 3)
    
    def test_ofdm_statistics(self):
        """Test OFDM signal statistical properties"""
        from infrastructure.hardware.mock_hardware import MockSignalGenerator
        generator = MockSignalGenerator()
        samples = generator.generate_ofdm_signal(50000, 20e6, 2.44e9)
        
        # OFDM should have high PAPR
        papr = np.max(np.abs(samples)**2) / np.mean(np.abs(samples)**2)
        self.assertGreater(papr, 5)
        
        # Amplitude distribution should be Rayleigh-like
        amplitude = np.abs(samples)
        mean_amp = np.mean(amplitude)
        std_amp = np.std(amplitude)
        
        # For Rayleigh, mean/std ≈ 1.91
        ratio = mean_amp / std_amp
        self.assertGreater(ratio, 1.5)
        self.assertLess(ratio, 2.5)


# ============================================================================
# Hardware Factory Tests
# ============================================================================

class TestMockHardwareFactory(unittest.TestCase):
    """Hardware factory mock creation tests"""
    
    def test_create_mock_direct(self):
        """Test creating mock hardware directly"""
        hardware = HardwareFactory.create_hardware(HardwareType.MOCK)
        
        self.assertIsInstance(hardware, MockSDR)
    
    def test_create_mock_with_force(self):
        """Test forcing mock hardware creation"""
        hardware = HardwareFactory.create_hardware(force_mock=True)
        
        self.assertIsInstance(hardware, MockSDR)
    
    def test_create_mock_with_config(self):
        """Test creating mock with configuration"""
        config = {
            'sample_rate': 20e6,
            'center_freq': 2.45e9,
            'mock': {'synthetic_mode': True}
        }
        
        hardware = HardwareFactory.create_hardware(HardwareType.MOCK, config)
        
        self.assertIsInstance(hardware, MockSDR)
        self.assertEqual(hardware.sample_rate, 20e6)
        self.assertEqual(hardware.center_freq, 2.45e9)
    
    def test_is_mock_hardware(self):
        """Test mock hardware detection"""
        mock_hw = MockSDR()
        
        self.assertTrue(HardwareFactory.is_mock_hardware(mock_hw))
        
        # Real hardware would return False
        from infrastructure.hardware.sdr_base import SDRBase
        class RealHardware(SDRBase):
            pass
        
        real_hw = RealHardware()
        self.assertFalse(HardwareFactory.is_mock_hardware(real_hw))


# ============================================================================
# Asynchronous Tests
# ============================================================================

class TestMockSDRAsync(unittest.IsolatedAsyncioTestCase):
    """Async mock hardware tests"""
    
    async def asyncSetUp(self):
        self.mock_sdr = MockSDR()
        self.mock_sdr.initialize({})
    
    async def test_async_read_samples(self):
        """Test async sample reading"""
        samples = await asyncio.get_event_loop().run_in_executor(
            None, self.mock_sdr.read_samples, 1024
        )
        
        self.assertEqual(len(samples), 1024)
    
    async def test_concurrent_reads(self):
        """Test concurrent reads from multiple coroutines"""
        async def read_samples():
            return await asyncio.get_event_loop().run_in_executor(
                None, self.mock_sdr.read_samples, 1024
            )
        
        results = await asyncio.gather(*[read_samples() for _ in range(10)])
        
        self.assertEqual(len(results), 10)
        for samples in results:
            self.assertEqual(len(samples), 1024)
    
    async def test_streaming_with_async(self):
        """Test streaming with async operations"""
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


# ============================================================================
# Integration Tests
# ============================================================================

class TestMockHardwareIntegration(unittest.TestCase):
    """Integration tests for mock hardware"""
    
    def setUp(self):
        self.mock_sdr = MockSDR()
        self.mock_sdr.initialize({})
    
    def test_signal_chain(self):
        """Test complete signal chain"""
        # Configure for drone detection
        self.mock_sdr.inject_drone("DJI Mavic 3", 2.44e9)
        
        # Read samples
        samples = self.mock_sdr.read_samples(16384)
        
        # Verify signal has power
        power = np.mean(np.abs(samples)**2)
        self.assertGreater(power, 0)
        
        # Check for spectral peaks
        fft_data = np.fft.fftshift(np.fft.fft(samples))
        peak_power = np.max(np.abs(fft_data)**2)
        avg_power = np.mean(np.abs(fft_data)**2)
        papr = peak_power / avg_power
        
        # Signal should have some peaks
        self.assertGreater(papr, 1.0)
    
    def test_scenario_transition_smoothness(self):
        """Test smooth scenario transitions"""
        # Noise scenario
        self.mock_sdr.set_scenario("noise_only")
        noise_samples = self.mock_sdr.read_samples(1024)
        noise_power = np.mean(np.abs(noise_samples)**2)
        
        # Drone scenario
        self.mock_sdr.set_scenario("dji_mavic_2.4g_active")
        drone_samples = self.mock_sdr.read_samples(1024)
        drone_power = np.mean(np.abs(drone_samples)**2)
        
        # Drone should have higher power
        self.assertGreater(drone_power, noise_power)


# ============================================================================
# Run Tests
# ============================================================================

def run_tests():
    """Run the test suite"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestMockSignalGenerator))
    suite.addTests(loader.loadTestsFromTestCase(TestMockSDRBasic))
    suite.addTests(loader.loadTestsFromTestCase(TestMockSDRScenarios))
    suite.addTests(loader.loadTestsFromTestCase(TestMockSDRErrors))
    suite.addTests(loader.loadTestsFromTestCase(TestMockSDRPerformance))
    suite.addTests(loader.loadTestsFromTestCase(TestMockSDRStatistics))
    suite.addTests(loader.loadTestsFromTestCase(TestMockHardwareFactory))
    suite.addTests(loader.loadTestsFromTestCase(TestMockHardwareIntegration))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    import asyncio
    success = run_tests()
    sys.exit(0 if success else 1)