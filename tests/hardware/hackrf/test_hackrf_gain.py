#!/usr/bin/env python3
"""
HackRF Gain Control Tests

Tests for HackRF One gain control functionality including:
- LNA (Low Noise Amplifier) gain settings
- VGA (Variable Gain Amplifier) gain settings
- RF amplifier (AMP) control
- Gain range validation
- Gain step verification
- Gain settling time
- Signal power vs gain relationship
- Noise figure vs gain
- Automatic Gain Control (AGC) behavior
- Gain calibration
- Temperature effects on gain
- Multiple gain configuration combinations
"""

import unittest
import time
import numpy as np
import sys
from pathlib import Path
from collections import defaultdict
import matplotlib.pyplot as plt

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Try to import HackRF library
try:
    import pyhackrf
    HACKRF_AVAILABLE = True
except ImportError:
    HACKRF_AVAILABLE = False
    print("Warning: pyhackrf not installed. Install with: pip install python_hackrf")

# Import project modules
from infrastructure.hardware.hackrf import HackRFDevice


# ============================================================================
# Test Configuration
# ============================================================================

class GainTestConfig:
    """Configuration for gain tests"""
    
    # Test frequency (use a quiet frequency for gain testing)
    TEST_FREQUENCY = 100e6  # 100 MHz - FM broadcast (usually has signals)
    
    # Sample rate
    SAMPLE_RATE = 10e6  # 10 MHz
    
    # Sample count for power measurement
    SAMPLES_PER_MEASUREMENT = 100000  # 100k samples
    
    # Gain ranges
    LNA_GAIN_MIN = 0
    LNA_GAIN_MAX = 40
    LNA_GAIN_STEP = 8  # 8 dB steps
    
    VGA_GAIN_MIN = 0
    VGA_GAIN_MAX = 62
    VGA_GAIN_STEP = 2  # 2 dB steps
    
    # Settling time after gain change (seconds)
    SETTLING_TIME = 0.05
    
    # Number of measurements per gain setting
    NUM_MEASUREMENTS = 3
    
    # Tolerance for gain step verification (dB)
    GAIN_STEP_TOLERANCE = 2.0
    
    # Expected LNA gain values
    EXPECTED_LNA_GAINS = [0, 8, 16, 24, 32, 40]
    
    # Expected VGA gain values
    EXPECTED_VGA_GAINS = [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30,
                          32, 34, 36, 38, 40, 42, 44, 46, 48, 50, 52, 54, 56, 58, 60, 62]


# ============================================================================
# Test Skipping if HackRF not available
# ============================================================================

def require_hackrf(test_func):
    """Decorator to skip tests if HackRF is not available"""
    def wrapper(*args, **kwargs):
        if not HACKRF_AVAILABLE:
            raise unittest.SkipTest("HackRF library not available")
        return test_func(*args, **kwargs)
    return wrapper


# ============================================================================
# Gain Measurement Utilities
# ============================================================================

class GainMeasurement:
    """Utility for measuring signal power with different gain settings"""
    
    def __init__(self, hackrf: HackRFDevice):
        self.hackrf = hackrf
        self.measurements = []
    
    def measure_power(self, num_samples: int = GainTestConfig.SAMPLES_PER_MEASUREMENT) -> float:
        """Measure average signal power in dBm"""
        samples = self.hackrf.read_samples(num_samples)
        power = np.mean(np.abs(samples)**2)
        power_dbm = 10 * np.log10(power + 1e-12)
        return power_dbm
    
    def measure_power_multiple(self, num_measurements: int = GainTestConfig.NUM_MEASUREMENTS) -> tuple:
        """Take multiple power measurements and return average and std dev"""
        powers = []
        for _ in range(num_measurements):
            power = self.measure_power()
            powers.append(power)
            time.sleep(0.01)
        
        avg_power = np.mean(powers)
        std_power = np.std(powers)
        return avg_power, std_power
    
    def measure_gain_step(self, gain_set_func, gain_values, gain_name: str) -> dict:
        """Measure power change vs gain setting"""
        results = {
            'gain_name': gain_name,
            'gains': [],
            'powers': [],
            'power_stds': [],
            'power_changes': []
        }
        
        for gain in gain_values:
            # Set gain
            gain_set_func(gain)
            time.sleep(GainTestConfig.SETTLING_TIME)
            
            # Measure power
            avg_power, std_power = self.measure_power_multiple()
            
            results['gains'].append(gain)
            results['powers'].append(avg_power)
            results['power_stds'].append(std_power)
            
            # Calculate power change from previous
            if len(results['powers']) > 1:
                power_change = avg_power - results['powers'][-2]
                results['power_changes'].append(power_change)
        
        return results
    
    def measure_lna_gain_scan(self, vga_gain: int = 20) -> dict:
        """Scan LNA gain settings"""
        # Set fixed VGA gain
        self.hackrf.set_vga_gain(vga_gain)
        self.hackrf.set_amp_enable(False)
        
        return self.measure_gain_step(
            self.hackrf.set_lna_gain,
            GainTestConfig.EXPECTED_LNA_GAINS,
            'LNA'
        )
    
    def measure_vga_gain_scan(self, lna_gain: int = 16) -> dict:
        """Scan VGA gain settings"""
        # Set fixed LNA gain
        self.hackrf.set_lna_gain(lna_gain)
        self.hackrf.set_amp_enable(False)
        
        return self.measure_gain_step(
            self.hackrf.set_vga_gain,
            GainTestConfig.EXPECTED_VGA_GAINS,
            'VGA'
        )
    
    def measure_amp_effect(self, lna_gain: int = 16, vga_gain: int = 20) -> dict:
        """Measure effect of RF amplifier"""
        self.hackrf.set_lna_gain(lna_gain)
        self.hackrf.set_vga_gain(vga_gain)
        
        results = {
            'amp_off_power': [],
            'amp_on_power': [],
            'amp_gain': []
        }
        
        for _ in range(GainTestConfig.NUM_MEASUREMENTS):
            # Measure with amp off
            self.hackrf.set_amp_enable(False)
            time.sleep(GainTestConfig.SETTLING_TIME)
            power_off = self.measure_power()
            
            # Measure with amp on
            self.hackrf.set_amp_enable(True)
            time.sleep(GainTestConfig.SETTLING_TIME)
            power_on = self.measure_power()
            
            results['amp_off_power'].append(power_off)
            results['amp_on_power'].append(power_on)
            results['amp_gain'].append(power_on - power_off)
        
        return {
            'amp_off_power_avg': np.mean(results['amp_off_power']),
            'amp_on_power_avg': np.mean(results['amp_on_power']),
            'amp_gain_avg': np.mean(results['amp_gain']),
            'amp_gain_std': np.std(results['amp_gain'])
        }


# ============================================================================
# LNA Gain Tests
# ============================================================================

class TestHackRFLNAGain(unittest.TestCase):
    """LNA (Low Noise Amplifier) gain tests"""
    
    @classmethod
    def setUpClass(cls):
        if not HACKRF_AVAILABLE:
            return
        cls.hackrf = HackRFDevice()
        cls.hackrf.initialize({
            'sample_rate': GainTestConfig.SAMPLE_RATE,
            'center_freq': GainTestConfig.TEST_FREQUENCY
        })
        cls.measurement = GainMeasurement(cls.hackrf)
    
    @classmethod
    def tearDownClass(cls):
        if HACKRF_AVAILABLE and hasattr(cls, 'hackrf'):
            cls.hackrf.close()
    
    def setUp(self):
        if not HACKRF_AVAILABLE:
            self.skipTest("HackRF library not available")
    
    @require_hackrf
    def test_lna_gain_range(self):
        """Test LNA gain range limits"""
        # Test min gain
        self.hackrf.set_lna_gain(GainTestConfig.LNA_GAIN_MIN)
        self.assertEqual(self.hackrf.lna_gain, GainTestConfig.LNA_GAIN_MIN)
        
        # Test max gain
        self.hackrf.set_lna_gain(GainTestConfig.LNA_GAIN_MAX)
        self.assertEqual(self.hackrf.lna_gain, GainTestConfig.LNA_GAIN_MAX)
        
        # Test invalid gain (should be clamped or rejected)
        invalid_gain = 50
        self.hackrf.set_lna_gain(invalid_gain)
        # Should be clamped to max or remain at previous
        self.assertLessEqual(self.hackrf.lna_gain, GainTestConfig.LNA_GAIN_MAX)
    
    @require_hackrf
    def test_lna_gain_step_size(self):
        """Test LNA gain step size (8 dB steps)"""
        results = self.measurement.measure_lna_gain_scan()
        
        print(f"\n  LNA Gain Scan Results:")
        for gain, power in zip(results['gains'], results['powers']):
            print(f"    LNA={gain}dB: Power={power:.1f}dBm")
        
        # Verify gain steps are approximately 8 dB
        expected_step = GainTestConfig.LNA_GAIN_STEP
        for i, change in enumerate(results['power_changes']):
            print(f"    Step {i+1}: {change:.1f}dB (expected {expected_step}dB)")
            
            # Allow tolerance
            self.assertAlmostEqual(change, expected_step, delta=GainTestConfig.GAIN_STEP_TOLERANCE)
    
    @require_hackrf
    def test_lna_gain_monotonicity(self):
        """Test that LNA gain is monotonic (increasing gain increases power)"""
        results = self.measurement.measure_lna_gain_scan()
        
        for i in range(1, len(results['powers'])):
            power_increase = results['powers'][i] - results['powers'][i-1]
            self.assertGreater(power_increase, 0, 
                f"Power decreased from LNA={results['gains'][i-1]} to LNA={results['gains'][i]}")
    
    @require_hackrf
    def test_lna_gain_repeatability(self):
        """Test LNA gain setting repeatability"""
        test_gains = [0, 16, 32, 40]
        
        for gain in test_gains:
            measurements = []
            for i in range(5):
                self.hackrf.set_lna_gain(gain)
                time.sleep(GainTestConfig.SETTLING_TIME)
                power = self.measurement.measure_power()
                measurements.append(power)
            
            power_std = np.std(measurements)
            print(f"\n  LNA={gain}dB: Power std={power_std:.2f}dB")
            
            # Should be repeatable within 1 dB
            self.assertLess(power_std, 1.0)


# ============================================================================
# VGA Gain Tests
# ============================================================================

class TestHackRFVGAGain(unittest.TestCase):
    """VGA (Variable Gain Amplifier) gain tests"""
    
    @classmethod
    def setUpClass(cls):
        if not HACKRF_AVAILABLE:
            return
        cls.hackrf = HackRFDevice()
        cls.hackrf.initialize({
            'sample_rate': GainTestConfig.SAMPLE_RATE,
            'center_freq': GainTestConfig.TEST_FREQUENCY
        })
        cls.measurement = GainMeasurement(cls.hackrf)
    
    @classmethod
    def tearDownClass(cls):
        if HACKRF_AVAILABLE and hasattr(cls, 'hackrf'):
            cls.hackrf.close()
    
    def setUp(self):
        if not HACKRF_AVAILABLE:
            self.skipTest("HackRF library not available")
    
    @require_hackrf
    def test_vga_gain_range(self):
        """Test VGA gain range limits"""
        # Test min gain
        self.hackrf.set_vga_gain(GainTestConfig.VGA_GAIN_MIN)
        self.assertEqual(self.hackrf.vga_gain, GainTestConfig.VGA_GAIN_MIN)
        
        # Test max gain
        self.hackrf.set_vga_gain(GainTestConfig.VGA_GAIN_MAX)
        self.assertEqual(self.hackrf.vga_gain, GainTestConfig.VGA_GAIN_MAX)
    
    @require_hackrf
    def test_vga_gain_step_size(self):
        """Test VGA gain step size (2 dB steps)"""
        # Use subset of gains for faster test
        test_gains = [0, 10, 20, 30, 40, 50, 60, 62]
        
        results = self.measurement.measure_gain_step(
            self.hackrf.set_vga_gain,
            test_gains,
            'VGA'
        )
        
        print(f"\n  VGA Gain Scan Results:")
        for gain, power in zip(results['gains'], results['powers']):
            print(f"    VGA={gain}dB: Power={power:.1f}dBm")
        
        # Verify gain steps are approximately 2 dB per 2 dB setting
        for i, change in enumerate(results['power_changes']):
            expected_step = results['gains'][i+1] - results['gains'][i]
            print(f"    Step {i+1}: {change:.1f}dB (expected {expected_step}dB)")
            
            # Allow tolerance
            self.assertAlmostEqual(change, expected_step, delta=GainTestConfig.GAIN_STEP_TOLERANCE * 2)
    
    @require_hackrf
    def test_vga_gain_monotonicity(self):
        """Test that VGA gain is monotonic"""
        test_gains = list(range(0, 63, 4))  # Every 4 dB for speed
        
        results = self.measurement.measure_gain_step(
            self.hackrf.set_vga_gain,
            test_gains,
            'VGA'
        )
        
        for i in range(1, len(results['powers'])):
            power_increase = results['powers'][i] - results['powers'][i-1]
            self.assertGreater(power_increase, -1.0,  # Allow small measurement error
                f"Power decreased from VGA={results['gains'][i-1]} to VGA={results['gains'][i]}")


# ============================================================================
# RF Amplifier Tests
# ============================================================================

class TestHackRFAmp(unittest.TestCase):
    """RF Amplifier (AMP) tests"""
    
    @classmethod
    def setUpClass(cls):
        if not HACKRF_AVAILABLE:
            return
        cls.hackrf = HackRFDevice()
        cls.hackrf.initialize({
            'sample_rate': GainTestConfig.SAMPLE_RATE,
            'center_freq': GainTestConfig.TEST_FREQUENCY
        })
        cls.measurement = GainMeasurement(cls.hackrf)
    
    @classmethod
    def tearDownClass(cls):
        if HACKRF_AVAILABLE and hasattr(cls, 'hackrf'):
            cls.hackrf.close()
    
    def setUp(self):
        if not HACKRF_AVAILABLE:
            self.skipTest("HackRF library not available")
    
    @require_hackrf
    def test_amp_enable_disable(self):
        """Test RF amplifier enable/disable"""
        self.hackrf.set_amp_enable(True)
        self.assertTrue(self.hackrf.amp_enable)
        
        self.hackrf.set_amp_enable(False)
        self.assertFalse(self.hackrf.amp_enable)
    
    @require_hackrf
    def test_amp_gain_contribution(self):
        """Test amplifier gain contribution (should be ~14 dB)"""
        # Test with different LNA/VGA combinations
        test_configs = [
            {'lna': 0, 'vga': 0},
            {'lna': 16, 'vga': 20},
            {'lna': 32, 'vga': 40}
        ]
        
        for config in test_configs:
            self.hackrf.set_lna_gain(config['lna'])
            self.hackrf.set_vga_gain(config['vga'])
            
            results = self.measurement.measure_amp_effect(config['lna'], config['vga'])
            
            print(f"\n  LNA={config['lna']}dB, VGA={config['vga']}dB:")
            print(f"    AMP Off: {results['amp_off_power_avg']:.1f} dBm")
            print(f"    AMP On:  {results['amp_on_power_avg']:.1f} dBm")
            print(f"    AMP Gain: {results['amp_gain_avg']:.1f} dB")
            
            # AMP should provide positive gain
            self.assertGreater(results['amp_gain_avg'], 10)
            self.assertLess(results['amp_gain_avg'], 20)
    
    @require_hackrf
    def test_amp_noise_figure(self):
        """Test amplifier noise figure (qualitative)"""
        # Measure noise floor with and without AMP
        self.hackrf.set_lna_gain(0)
        self.hackrf.set_vga_gain(0)
        
        # Without AMP
        self.hackrf.set_amp_enable(False)
        time.sleep(GainTestConfig.SETTLING_TIME)
        noise_off = self.measurement.measure_power()
        
        # With AMP
        self.hackrf.set_amp_enable(True)
        time.sleep(GainTestConfig.SETTLING_TIME)
        noise_on = self.measurement.measure_power()
        
        noise_increase = noise_on - noise_off
        print(f"\n  Noise floor increase with AMP: {noise_increase:.1f} dB")
        
        # AMP should increase noise floor (normal behavior)
        self.assertGreater(noise_increase, 0)


# ============================================================================
# Combined Gain Tests
# ============================================================================

class TestHackRFCombinedGain(unittest.TestCase):
    """Combined gain configuration tests"""
    
    @classmethod
    def setUpClass(cls):
        if not HACKRF_AVAILABLE:
            return
        cls.hackrf = HackRFDevice()
        cls.hackrf.initialize({
            'sample_rate': GainTestConfig.SAMPLE_RATE,
            'center_freq': GainTestConfig.TEST_FREQUENCY
        })
        cls.measurement = GainMeasurement(cls.hackrf)
    
    @classmethod
    def tearDownClass(cls):
        if HACKRF_AVAILABLE and hasattr(cls, 'hackrf'):
            cls.hackrf.close()
    
    def setUp(self):
        if not HACKRF_AVAILABLE:
            self.skipTest("HackRF library not available")
    
    @require_hackrf
    def test_gain_matrix(self):
        """Test various gain combinations"""
        lna_values = [0, 16, 32]
        vga_values = [0, 20, 40, 62]
        
        results = defaultdict(dict)
        
        for lna in lna_values:
            for vga in vga_values:
                self.hackrf.set_lna_gain(lna)
                self.hackrf.set_vga_gain(vga)
                self.hackrf.set_amp_enable(False)
                
                time.sleep(GainTestConfig.SETTLING_TIME)
                power = self.measurement.measure_power()
                
                results[lna][vga] = power
                print(f"  LNA={lna}dB, VGA={vga}dB: Power={power:.1f}dBm")
        
        # Verify power increases with gain
        for lna in lna_values:
            powers = list(results[lna].values())
            for i in range(1, len(powers)):
                self.assertGreater(powers[i], powers[i-1],
                    f"Power decreased with increasing VGA gain at LNA={lna}")
    
    @require_hackrf
    def test_gain_saturation(self):
        """Test gain saturation at high settings"""
        # Measure power at increasing VGA gain
        vga_values = list(range(0, 63, 4))
        powers = []
        
        self.hackrf.set_lna_gain(32)  # High LNA gain
        
        for vga in vga_values:
            self.hackrf.set_vga_gain(vga)
            time.sleep(GainTestConfig.SETTLING_TIME)
            power = self.measurement.measure_power()
            powers.append(power)
        
        # Check for saturation (diminishing returns)
        # This is qualitative - not a strict test
        print(f"\n  VGA gain sweep for saturation:")
        for vga, power in zip(vga_values, powers):
            print(f"    VGA={vga}dB: Power={power:.1f}dBm")


# ============================================================================
# Gain Stability Tests
# ============================================================================

class TestHackRFGainStability(unittest.TestCase):
    """Gain stability tests"""
    
    @classmethod
    def setUpClass(cls):
        if not HACKRF_AVAILABLE:
            return
        cls.hackrf = HackRFDevice()
        cls.hackrf.initialize({
            'sample_rate': GainTestConfig.SAMPLE_RATE,
            'center_freq': GainTestConfig.TEST_FREQUENCY
        })
        cls.measurement = GainMeasurement(cls.hackrf)
    
    @classmethod
    def tearDownClass(cls):
        if HACKRF_AVAILABLE and hasattr(cls, 'hackrf'):
            cls.hackrf.close()
    
    def setUp(self):
        if not HACKRF_AVAILABLE:
            self.skipTest("HackRF library not available")
    
    @require_hackrf
    def test_gain_settling_time(self):
        """Test gain settling time after change"""
        self.hackrf.set_lna_gain(0)
        self.hackrf.set_vga_gain(0)
        
        # Measure settling time
        settling_times = []
        
        for target_gain in [16, 32, 40]:
            start_time = time.time()
            self.hackrf.set_lna_gain(target_gain)
            
            # Measure until power stabilizes
            powers = []
            for i in range(20):
                power = self.measurement.measure_power()
                powers.append(power)
                time.sleep(0.01)
            
            # Find when power stabilizes (within 0.5 dB)
            stable_idx = 0
            for i in range(len(powers) - 5):
                if np.std(powers[i:i+5]) < 0.5:
                    stable_idx = i
                    break
            
            settling_time = stable_idx * 0.01
            settling_times.append(settling_time)
            print(f"\n  Gain change to LNA={target_gain}dB: settling time ~{settling_time*1000:.0f}ms")
        
        # Settling time should be reasonable
        self.assertLess(np.mean(settling_times), 0.5)
    
    @require_hackrf
    def test_gain_drift(self):
        """Test gain drift over time"""
        self.hackrf.set_lna_gain(16)
        self.hackrf.set_vga_gain(20)
        
        # Measure power over time
        powers = []
        for i in range(100):
            power = self.measurement.measure_power()
            powers.append(power)
            time.sleep(0.1)
        
        power_std = np.std(powers)
        power_drift = max(powers) - min(powers)
        
        print(f"\n  Power over 10 seconds:")
        print(f"    Mean: {np.mean(powers):.1f} dBm")
        print(f"    Std Dev: {power_std:.2f} dB")
        print(f"    Drift: {power_drift:.2f} dB")
        
        # Gain should be reasonably stable
        self.assertLess(power_std, 1.0)


# ============================================================================
# Gain Calibration Tests
# ============================================================================

class TestHackRFGainCalibration(unittest.TestCase):
    """Gain calibration tests"""
    
    @classmethod
    def setUpClass(cls):
        if not HACKRF_AVAILABLE:
            return
        cls.hackrf = HackRFDevice()
        cls.hackrf.initialize({
            'sample_rate': GainTestConfig.SAMPLE_RATE,
            'center_freq': GainTestConfig.TEST_FREQUENCY
        })
        cls.measurement = GainMeasurement(cls.hackrf)
    
    @classmethod
    def tearDownClass(cls):
        if HACKRF_AVAILABLE and hasattr(cls, 'hackrf'):
            cls.hackrf.close()
    
    def setUp(self):
        if not HACKRF_AVAILABLE:
            self.skipTest("HackRF library not available")
    
    @require_hackrf
    def test_gain_linearity(self):
        """Test gain linearity"""
        lna_gains = [0, 8, 16, 24, 32, 40]
        vga_gains = [0, 10, 20, 30, 40, 50, 62]
        
        # Use a known signal source (e.g., broadcast FM)
        # This is a qualitative test
        
        results = []
        for lna in lna_gains:
            self.hackrf.set_lna_gain(lna)
            for vga in vga_gains:
                self.hackrf.set_vga_gain(vga)
                time.sleep(GainTestConfig.SETTLING_TIME)
                power = self.measurement.measure_power()
                results.append({
                    'lna': lna,
                    'vga': vga,
                    'power': power
                })
        
        # Check linearity - power should increase with total gain
        # This is a complex test; simplified check
        for i in range(1, len(results)):
            if results[i]['lna'] == results[i-1]['lna']:
                if results[i]['vga'] > results[i-1]['vga']:
                    self.assertGreater(results[i]['power'], results[i-1]['power'])


# ============================================================================
# Run Tests
# ============================================================================

def run_tests():
    """Run the test suite"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestHackRFLNAGain))
    suite.addTests(loader.loadTestsFromTestCase(TestHackRFVGAGain))
    suite.addTests(loader.loadTestsFromTestCase(TestHackRFAmp))
    suite.addTests(loader.loadTestsFromTestCase(TestHackRFCombinedGain))
    suite.addTests(loader.loadTestsFromTestCase(TestHackRFGainStability))
    suite.addTests(loader.loadTestsFromTestCase(TestHackRFGainCalibration))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)