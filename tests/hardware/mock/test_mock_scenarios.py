#!/usr/bin/env python3
"""
Mock Scenarios Tests

Tests for mock hardware scenario management including:
- Scenario creation and registration
- Scenario switching and activation
- Scenario signal characteristics validation
- Scenario transitions and smoothness
- Scenario parameter customization
- Scenario performance benchmarking
- Scenario persistence and serialization
- Multi-scenario orchestration
- Scenario stress testing
"""

import unittest
import numpy as np
import time
import json
import tempfile
from pathlib import Path
from collections import defaultdict
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from infrastructure.hardware.mock_hardware import (
    MockSDR,
    MockScenario,
    MockSignalGenerator
)


# ============================================================================
# Test Configuration
# ============================================================================

class ScenarioTestConfig:
    """Configuration for scenario tests"""
    
    # Test parameters
    SAMPLE_RATE = 10e6  # 10 MHz
    NUM_SAMPLES = 16384
    NUM_MEASUREMENTS = 10
    
    # Scenario names
    DRONE_SCENARIOS = [
        'dji_mavic_2.4g_active',
        'dji_mavic_5.8g_active',
        'fpv_analog_5.8g',
        'autel_evo_2.4g',
        'skydio_2_2.4g'
    ]
    
    NOISE_SCENARIOS = [
        'noise_only',
        'interference_wifi',
        'interference_ble'
    ]
    
    # Performance thresholds
    MAX_SCENARIO_SWITCH_MS = 50
    MIN_SIGNAL_POWER = 1e-6
    MAX_NOISE_POWER = 1e-4
    
    # Statistical tolerances
    POWER_TOLERANCE = 0.3  # 30% tolerance for power measurements


# ============================================================================
# Signal Analysis Utilities
# ============================================================================

class SignalAnalyzer:
    """Utility for analyzing signal characteristics"""
    
    @staticmethod
    def compute_power(samples: np.ndarray) -> float:
        """Compute average signal power"""
        return np.mean(np.abs(samples)**2)
    
    @staticmethod
    def compute_peak_power(samples: np.ndarray) -> float:
        """Compute peak signal power"""
        return np.max(np.abs(samples)**2)
    
    @staticmethod
    def compute_papr(samples: np.ndarray) -> float:
        """Compute Peak-to-Average Power Ratio"""
        peak = SignalAnalyzer.compute_peak_power(samples)
        avg = SignalAnalyzer.compute_power(samples)
        return peak / avg if avg > 0 else 0
    
    @staticmethod
    def compute_bandwidth(samples: np.ndarray, sample_rate: float) -> float:
        """Estimate signal bandwidth"""
        fft_data = np.fft.fftshift(np.fft.fft(samples))
        psd = np.abs(fft_data)**2
        threshold = np.max(psd) * 0.5  # 3dB bandwidth
        
        above_threshold = np.where(psd > threshold)[0]
        if len(above_threshold) > 1:
            freqs = np.fft.fftfreq(len(samples), 1/sample_rate)
            freqs = np.fft.fftshift(freqs)
            bandwidth = freqs[above_threshold[-1]] - freqs[above_threshold[0]]
            return abs(bandwidth)
        return 0
    
    @staticmethod
    def compute_spectral_flatness(samples: np.ndarray) -> float:
        """Compute spectral flatness (Wiener entropy)"""
        fft_data = np.fft.fft(samples)
        psd = np.abs(fft_data)**2
        geometric_mean = np.exp(np.mean(np.log(psd + 1e-12)))
        arithmetic_mean = np.mean(psd)
        return geometric_mean / arithmetic_mean if arithmetic_mean > 0 else 0
    
    @staticmethod
    def compute_envelope_variance(samples: np.ndarray) -> float:
        """Compute variance of signal envelope"""
        envelope = np.abs(samples)
        return np.var(envelope)
    
    @staticmethod
    def compute_phase_variance(samples: np.ndarray) -> float:
        """Compute variance of signal phase"""
        phase = np.unwrap(np.angle(samples))
        return np.var(phase)


# ============================================================================
# Scenario Signal Characteristic Tests
# ============================================================================

class TestScenarioSignalCharacteristics(unittest.TestCase):
    """Test signal characteristics for different scenarios"""
    
    def setUp(self):
        self.mock_sdr = MockSDR()
        self.mock_sdr.initialize({
            'sample_rate': ScenarioTestConfig.SAMPLE_RATE
        })
        self.analyzer = SignalAnalyzer()
    
    def test_drone_scenario_power(self):
        """Test that drone scenarios have reasonable power levels"""
        for scenario in ScenarioTestConfig.DRONE_SCENARIOS:
            self.mock_sdr.set_scenario(scenario)
            samples = self.mock_sdr.read_samples(ScenarioTestConfig.NUM_SAMPLES)
            power = self.analyzer.compute_power(samples)
            
            print(f"\n  {scenario}: Power = {power:.6f}")
            
            # Drone signals should have measurable power
            self.assertGreater(power, ScenarioTestConfig.MIN_SIGNAL_POWER)
    
    def test_noise_scenario_power(self):
        """Test that noise scenarios have appropriate power levels"""
        for scenario in ScenarioTestConfig.NOISE_SCENARIOS:
            self.mock_sdr.set_scenario(scenario)
            samples = self.mock_sdr.read_samples(ScenarioTestConfig.NUM_SAMPLES)
            power = self.analyzer.compute_power(samples)
            
            print(f"\n  {scenario}: Power = {power:.6f}")
            
            # Noise should be present but not overpowering
            self.assertGreater(power, 0)
            self.assertLess(power, ScenarioTestConfig.MAX_NOISE_POWER)
    
    def test_drone_papr_characteristics(self):
        """Test PAPR characteristics for drone scenarios"""
        papr_values = {}
        
        for scenario in ScenarioTestConfig.DRONE_SCENARIOS:
            self.mock_sdr.set_scenario(scenario)
            samples = self.mock_sdr.read_samples(ScenarioTestConfig.NUM_SAMPLES)
            papr = self.analyzer.compute_papr(samples)
            papr_values[scenario] = papr
            
            print(f"\n  {scenario}: PAPR = {papr:.2f}")
            
            # PAPR should be > 1 for modulated signals
            self.assertGreater(papr, 1.0)
    
    def test_spectral_flatness(self):
        """Test spectral flatness for different scenario types"""
        flatness_values = {}
        
        for scenario in ScenarioTestConfig.DRONE_SCENARIOS[:2]:
            self.mock_sdr.set_scenario(scenario)
            samples = self.mock_sdr.read_samples(ScenarioTestConfig.NUM_SAMPLES)
            flatness = self.analyzer.compute_spectral_flatness(samples)
            flatness_values[scenario] = flatness
            
            print(f"\n  {scenario}: Spectral Flatness = {flatness:.4f}")
        
        # Noise scenario for comparison
        self.mock_sdr.set_scenario('noise_only')
        noise_samples = self.mock_sdr.read_samples(ScenarioTestConfig.NUM_SAMPLES)
        noise_flatness = self.analyzer.compute_spectral_flatness(noise_samples)
        print(f"\n  noise_only: Spectral Flatness = {noise_flatness:.4f}")
        
        # Noise should have higher spectral flatness (more uniform spectrum)
        for flatness in flatness_values.values():
            self.assertLess(flatness, noise_flatness)
    
    def test_envelope_characteristics(self):
        """Test envelope characteristics for different modulations"""
        envelope_stats = {}
        
        for scenario in ScenarioTestConfig.DRONE_SCENARIOS[:2]:
            self.mock_sdr.set_scenario(scenario)
            samples = self.mock_sdr.read_samples(ScenarioTestConfig.NUM_SAMPLES)
            envelope_var = self.analyzer.compute_envelope_variance(samples)
            envelope_stats[scenario] = envelope_var
            
            print(f"\n  {scenario}: Envelope Variance = {envelope_var:.6f}")
        
        # Add analog FPV for comparison
        self.mock_sdr.set_scenario('fpv_analog_5.8g')
        fpv_samples = self.mock_sdr.read_samples(ScenarioTestConfig.NUM_SAMPLES)
        fpv_var = self.analyzer.compute_envelope_variance(fpv_samples)
        print(f"\n  fpv_analog_5.8g: Envelope Variance = {fpv_var:.6f}")
        
        # FM signals should have lower envelope variance
        self.assertLess(fpv_var, envelope_stats.get('dji_mavic_2.4g_active', 1.0))


# ============================================================================
# Scenario Switching Tests
# ============================================================================

class TestScenarioSwitching(unittest.TestCase):
    """Test scenario switching performance and smoothness"""
    
    def setUp(self):
        self.mock_sdr = MockSDR()
        self.mock_sdr.initialize({
            'sample_rate': ScenarioTestConfig.SAMPLE_RATE
        })
    
    def test_scenario_switch_speed(self):
        """Test scenario switching speed"""
        switch_times = []
        
        for i in range(ScenarioTestConfig.NUM_MEASUREMENTS):
            for scenario in ScenarioTestConfig.DRONE_SCENARIOS:
                start = time.time()
                self.mock_sdr.set_scenario(scenario)
                switch_times.append((time.time() - start) * 1000)
        
        avg_switch_time = np.mean(switch_times)
        max_switch_time = np.max(switch_times)
        
        print(f"\n  Average switch time: {avg_switch_time:.2f} ms")
        print(f"  Max switch time: {max_switch_time:.2f} ms")
        
        self.assertLess(max_switch_time, ScenarioTestConfig.MAX_SCENARIO_SWITCH_MS)
    
    def test_scenario_switch_consistency(self):
        """Test consistency of signal after switching"""
        self.mock_sdr.set_scenario('noise_only')
        noise_power = SignalAnalyzer.compute_power(
            self.mock_sdr.read_samples(ScenarioTestConfig.NUM_SAMPLES)
        )
        
        powers = []
        for scenario in ScenarioTestConfig.DRONE_SCENARIOS:
            self.mock_sdr.set_scenario(scenario)
            samples = self.mock_sdr.read_samples(ScenarioTestConfig.NUM_SAMPLES)
            power = SignalAnalyzer.compute_power(samples)
            powers.append(power)
            
            # Switch back to noise to verify
            self.mock_sdr.set_scenario('noise_only')
            verify_power = SignalAnalyzer.compute_power(
                self.mock_sdr.read_samples(ScenarioTestConfig.NUM_SAMPLES)
            )
            self.assertAlmostEqual(verify_power, noise_power, delta=noise_power * 0.1)
        
        print(f"\n  Drone powers: {[f'{p:.6f}' for p in powers]}")
    
    def test_scenario_switch_consecutive(self):
        """Test multiple consecutive scenario switches"""
        scenario_sequence = (
            ScenarioTestConfig.DRONE_SCENARIOS + 
            ScenarioTestConfig.NOISE_SCENARIOS
        ) * 3  # Repeat sequence
        
        powers = []
        for scenario in scenario_sequence:
            self.mock_sdr.set_scenario(scenario)
            samples = self.mock_sdr.read_samples(ScenarioTestConfig.NUM_SAMPLES // 2)
            powers.append(SignalAnalyzer.compute_power(samples))
        
        # Verify all switches completed without error
        self.assertEqual(len(powers), len(scenario_sequence))
        
        # Check that drone scenarios have higher power than noise
        for i, scenario in enumerate(scenario_sequence):
            if scenario in ScenarioTestConfig.DRONE_SCENARIOS:
                self.assertGreater(powers[i], ScenarioTestConfig.MIN_SIGNAL_POWER)
            else:
                self.assertLess(powers[i], ScenarioTestConfig.MAX_NOISE_POWER)


# ============================================================================
# Scenario Repeatability Tests
# ============================================================================

class TestScenarioRepeatability(unittest.TestCase):
    """Test scenario repeatability and consistency"""
    
    def setUp(self):
        self.mock_sdr = MockSDR()
        self.mock_sdr.initialize({
            'sample_rate': ScenarioTestConfig.SAMPLE_RATE
        })
    
    def test_scenario_repeatability(self):
        """Test that same scenario produces consistent signals"""
        scenario = ScenarioTestConfig.DRONE_SCENARIOS[0]
        
        power_measurements = []
        for i in range(ScenarioTestConfig.NUM_MEASUREMENTS):
            self.mock_sdr.set_scenario(scenario)
            samples = self.mock_sdr.read_samples(ScenarioTestConfig.NUM_SAMPLES)
            power = SignalAnalyzer.compute_power(samples)
            power_measurements.append(power)
        
        power_mean = np.mean(power_measurements)
        power_std = np.std(power_measurements)
        power_cv = power_std / power_mean  # Coefficient of variation
        
        print(f"\n  Power mean: {power_mean:.6f}")
        print(f"  Power std: {power_std:.6f}")
        print(f"  Coefficient of variation: {power_cv:.3f}")
        
        # Should be reasonably consistent
        self.assertLess(power_cv, ScenarioTestConfig.POWER_TOLERANCE)
    
    def test_scenario_reproducibility(self):
        """Test that scenario produces same signal over time"""
        scenario = ScenarioTestConfig.DRONE_SCENARIOS[0]
        
        # First measurement
        self.mock_sdr.set_scenario(scenario)
        samples1 = self.mock_sdr.read_samples(ScenarioTestConfig.NUM_SAMPLES)
        stats1 = {
            'power': SignalAnalyzer.compute_power(samples1),
            'papr': SignalAnalyzer.compute_papr(samples1),
            'bandwidth': SignalAnalyzer.compute_bandwidth(samples1, ScenarioTestConfig.SAMPLE_RATE)
        }
        
        # Wait a bit
        time.sleep(0.5)
        
        # Second measurement
        self.mock_sdr.set_scenario(scenario)
        samples2 = self.mock_sdr.read_samples(ScenarioTestConfig.NUM_SAMPLES)
        stats2 = {
            'power': SignalAnalyzer.compute_power(samples2),
            'papr': SignalAnalyzer.compute_papr(samples2),
            'bandwidth': SignalAnalyzer.compute_bandwidth(samples2, ScenarioTestConfig.SAMPLE_RATE)
        }
        
        print(f"\n  First measurement: {stats1}")
        print(f"  Second measurement: {stats2}")
        
        # Statistics should be similar
        self.assertAlmostEqual(stats1['power'], stats2['power'], 
                               delta=stats1['power'] * 0.1)
        self.assertAlmostEqual(stats1['papr'], stats2['papr'], delta=0.5)
    
    def test_scenario_determinism(self):
        """Test that scenario produces deterministic output for same seed"""
        # Note: Mock hardware may not be fully deterministic
        # This test checks basic consistency
        
        self.mock_sdr.set_scenario('noise_only')
        samples1 = self.mock_sdr.read_samples(10000)
        samples2 = self.mock_sdr.read_samples(10000)
        
        # Different reads should produce different samples
        correlation = np.corrcoef(np.abs(samples1), np.abs(samples2))[0, 1]
        
        print(f"\n  Correlation between successive reads: {correlation:.4f}")
        
        # Noise should be uncorrelated
        self.assertLess(abs(correlation), 0.1)


# ============================================================================
# Scenario Parameter Tests
# ============================================================================

class TestScenarioParameters(unittest.TestCase):
    """Test scenario parameter customization"""
    
    def setUp(self):
        self.mock_sdr = MockSDR()
        self.mock_sdr.initialize({
            'sample_rate': ScenarioTestConfig.SAMPLE_RATE
        })
    
    def test_custom_scenario_creation(self):
        """Test creating custom scenario"""
        custom_scenario = MockScenario(
            name="custom_drone",
            drone_type="Custom Drone",
            center_freq=2.5e9,
            bandwidth=25e6,
            snr_db=20,
            duration=60.0
        )
        
        # Add to available scenarios
        self.mock_sdr.scenarios.append(custom_scenario)
        self.mock_sdr.set_scenario("custom_drone")
        
        samples = self.mock_sdr.read_samples(ScenarioTestConfig.NUM_SAMPLES)
        
        self.assertIsNotNone(samples)
        self.assertEqual(len(samples), ScenarioTestConfig.NUM_SAMPLES)
    
    def test_scenario_snr_variation(self):
        """Test SNR variation affects signal quality"""
        snr_values = [5, 10, 15, 20, 25]
        powers = []
        
        for snr in snr_values:
            scenario = MockScenario(
                name=f"test_snr_{snr}",
                drone_type="Test",
                center_freq=2.44e9,
                bandwidth=20e6,
                snr_db=snr,
                duration=10.0
            )
            self.mock_sdr.scenarios.append(scenario)
            self.mock_sdr.set_scenario(f"test_snr_{snr}")
            
            samples = self.mock_sdr.read_samples(ScenarioTestConfig.NUM_SAMPLES)
            power = SignalAnalyzer.compute_power(samples)
            powers.append(power)
        
        print(f"\n  SNR vs Power: {list(zip(snr_values, powers))}")
        
        # Higher SNR should generally produce higher power
        # (may not be strictly monotonic due to noise)
        self.assertGreater(powers[-1], powers[0])
    
    def test_scenario_bandwidth_effect(self):
        """Test bandwidth parameter affects signal"""
        bandwidths = [5e6, 10e6, 20e6, 40e6]
        measured_bws = []
        
        for bw in bandwidths:
            scenario = MockScenario(
                name=f"test_bw_{bw}",
                drone_type="Test",
                center_freq=2.44e9,
                bandwidth=bw,
                snr_db=20,
                duration=10.0
            )
            self.mock_sdr.scenarios.append(scenario)
            self.mock_sdr.set_scenario(f"test_bw_{bw}")
            
            samples = self.mock_sdr.read_samples(ScenarioTestConfig.NUM_SAMPLES)
            measured_bw = SignalAnalyzer.compute_bandwidth(samples, ScenarioTestConfig.SAMPLE_RATE)
            measured_bws.append(measured_bw)
        
        print(f"\n  Bandwidths: Expected={bandwidths}, Measured={measured_bws}")
        
        # Measured bandwidth should increase with expected
        for i in range(1, len(measured_bws)):
            if measured_bws[i-1] > 0:
                self.assertGreater(measured_bws[i], measured_bws[i-1])


# ============================================================================
# Scenario Validation Tests
# ============================================================================

class TestScenarioValidation(unittest.TestCase):
    """Test scenario validation and error handling"""
    
    def setUp(self):
        self.mock_sdr = MockSDR()
        self.mock_sdr.initialize({
            'sample_rate': ScenarioTestConfig.SAMPLE_RATE
        })
    
    def test_invalid_scenario_handling(self):
        """Test handling of invalid scenario names"""
        with self.assertRaises(Exception):
            self.mock_sdr.set_scenario("nonexistent_scenario")
    
    def test_empty_scenario_list(self):
        """Test scenario list is not empty"""
        scenarios = self.mock_sdr.list_scenarios()
        self.assertGreater(len(scenarios), 0)
    
    def test_scenario_properties(self):
        """Test scenario properties are accessible"""
        for scenario in self.mock_sdr.scenarios:
            self.assertIsNotNone(scenario.name)
            self.assertIsNotNone(scenario.drone_type)
            self.assertIsNotNone(scenario.center_freq)
            self.assertIsNotNone(scenario.snr_db)
    
    def test_scenario_description(self):
        """Test scenario descriptions are meaningful"""
        for scenario in self.mock_sdr.scenarios:
            self.assertIsInstance(scenario.name, str)
            self.assertIsInstance(scenario.drone_type, (str, type(None)))
            self.assertIsInstance(scenario.center_freq, (int, float))


# ============================================================================
# Scenario Performance Tests
# ============================================================================

class TestScenarioPerformance(unittest.TestCase):
    """Performance tests for scenarios"""
    
    def setUp(self):
        self.mock_sdr = MockSDR()
        self.mock_sdr.initialize({
            'sample_rate': ScenarioTestConfig.SAMPLE_RATE
        })
    
    def test_scenario_generation_rate(self):
        """Test sample generation rate for different scenarios"""
        rates = {}
        
        for scenario in ScenarioTestConfig.DRONE_SCENARIOS[:3]:
            self.mock_sdr.set_scenario(scenario)
            
            start = time.time()
            total_samples = 0
            for _ in range(10):
                samples = self.mock_sdr.read_samples(ScenarioTestConfig.NUM_SAMPLES)
                total_samples += len(samples)
            elapsed = time.time() - start
            
            rate = total_samples / elapsed / 1e6
            rates[scenario] = rate
            
            print(f"\n  {scenario}: {rate:.1f} MS/s")
            
            # All scenarios should generate at reasonable rate
            self.assertGreater(rate, 10)
    
    def test_scenario_memory_usage(self):
        """Test memory usage across scenario switches"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024
        
        memory_samples = []
        for i in range(100):
            scenario = ScenarioTestConfig.DRONE_SCENARIOS[i % len(ScenarioTestConfig.DRONE_SCENARIOS)]
            self.mock_sdr.set_scenario(scenario)
            samples = self.mock_sdr.read_samples(ScenarioTestConfig.NUM_SAMPLES)
            
            if i % 10 == 0:
                current_memory = process.memory_info().rss / 1024 / 1024
                memory_samples.append(current_memory)
        
        memory_increase = max(memory_samples) - initial_memory if memory_samples else 0
        
        print(f"\n  Initial memory: {initial_memory:.1f} MB")
        print(f"  Max memory: {max(memory_samples):.1f} MB")
        print(f"  Memory increase: {memory_increase:.1f} MB")
        
        # Should not leak memory significantly
        self.assertLess(memory_increase, 50)


# ============================================================================
# Scenario Stress Tests
# ============================================================================

class TestScenarioStress(unittest.TestCase):
    """Stress tests for scenarios under load"""
    
    def setUp(self):
        self.mock_sdr = MockSDR()
        self.mock_sdr.initialize({
            'sample_rate': ScenarioTestConfig.SAMPLE_RATE,
            'mock': {
                'synthetic_mode': True,
                'simulate_latency_ms': 0
            }
        })
    
    def test_rapid_scenario_switching(self):
        """Test rapid scenario switching under load"""
        errors = 0
        switch_count = 500
        
        for i in range(switch_count):
            try:
                scenario = ScenarioTestConfig.DRONE_SCENARIOS[i % len(ScenarioTestConfig.DRONE_SCENARIOS)]
                self.mock_sdr.set_scenario(scenario)
                samples = self.mock_sdr.read_samples(1024)
                self.assertEqual(len(samples), 1024)
            except Exception as e:
                errors += 1
        
        print(f"\n  Rapid switches: {switch_count}, Errors: {errors}")
        self.assertEqual(errors, 0)
    
    def test_concurrent_scenario_access(self):
        """Test concurrent scenario access from multiple threads"""
        import threading
        
        results = []
        errors = []
        
        def worker(worker_id):
            try:
                for i in range(100):
                    scenario = ScenarioTestConfig.DRONE_SCENARIOS[i % len(ScenarioTestConfig.DRONE_SCENARIOS)]
                    self.mock_sdr.set_scenario(scenario)
                    samples = self.mock_sdr.read_samples(4096)
                    results.append(len(samples))
            except Exception as e:
                errors.append(str(e))
        
        threads = []
        for i in range(4):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        print(f"\n  Concurrent workers: 4, Total operations: {len(results)}")
        print(f"  Errors: {len(errors)}")
        
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(results), 400)


# ============================================================================
# Scenario Persistence Tests
# ============================================================================

class TestScenarioPersistence(unittest.TestCase):
    """Test scenario persistence and serialization"""
    
    def setUp(self):
        self.mock_sdr = MockSDR()
        self.mock_sdr.initialize({
            'sample_rate': ScenarioTestConfig.SAMPLE_RATE
        })
    
    def test_scenario_state_save(self):
        """Test saving scenario state"""
        self.mock_sdr.set_scenario(ScenarioTestConfig.DRONE_SCENARIOS[0])
        samples_before = self.mock_sdr.read_samples(ScenarioTestConfig.NUM_SAMPLES)
        
        # Save scenario state
        saved_scenario = self.mock_sdr.current_scenario
        
        # Switch to different scenario
        self.mock_sdr.set_scenario(ScenarioTestConfig.DRONE_SCENARIOS[1])
        
        # Restore saved scenario
        self.mock_sdr.current_scenario = saved_scenario
        samples_after = self.mock_sdr.read_samples(ScenarioTestConfig.NUM_SAMPLES)
        
        # Compare statistics
        power_before = SignalAnalyzer.compute_power(samples_before)
        power_after = SignalAnalyzer.compute_power(samples_after)
        
        print(f"\n  Power before: {power_before:.6f}")
        print(f"  Power after: {power_after:.6f}")
        
        self.assertAlmostEqual(power_before, power_after, delta=power_before * 0.1)
    
    def test_scenario_serialization(self):
        """Test scenario serialization to JSON"""
        scenario = MockScenario(
            name="test_serialize",
            drone_type="Test Drone",
            center_freq=2.44e9,
            bandwidth=20e6,
            snr_db=15,
            duration=30.0,
            file_path=Path("/test/path.iq")
        )
        
        # Convert to dict
        scenario_dict = {
            'name': scenario.name,
            'drone_type': scenario.drone_type,
            'center_freq': scenario.center_freq,
            'bandwidth': scenario.bandwidth,
            'snr_db': scenario.snr_db,
            'duration': scenario.duration,
            'file_path': str(scenario.file_path) if scenario.file_path else None
        }
        
        # Serialize to JSON
        json_str = json.dumps(scenario_dict)
        
        # Deserialize
        loaded_dict = json.loads(json_str)
        
        self.assertEqual(loaded_dict['name'], scenario.name)
        self.assertEqual(loaded_dict['center_freq'], scenario.center_freq)
        
        print(f"\n  Serialized scenario: {json_str[:100]}...")


# ============================================================================
# Run Tests
# ============================================================================

def run_tests():
    """Run the test suite"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestScenarioSignalCharacteristics))
    suite.addTests(loader.loadTestsFromTestCase(TestScenarioSwitching))
    suite.addTests(loader.loadTestsFromTestCase(TestScenarioRepeatability))
    suite.addTests(loader.loadTestsFromTestCase(TestScenarioParameters))
    suite.addTests(loader.loadTestsFromTestCase(TestScenarioValidation))
    suite.addTests(loader.loadTestsFromTestCase(TestScenarioPerformance))
    suite.addTests(loader.loadTestsFromTestCase(TestScenarioStress))
    suite.addTests(loader.loadTestsFromTestCase(TestScenarioPersistence))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)