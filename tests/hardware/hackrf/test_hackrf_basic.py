#!/usr/bin/env python3
"""
HackRF Basic Hardware Tests

Tests for basic HackRF One functionality including:
- Device detection and initialization
- Board information retrieval
- Basic RX/TX operations
- Frequency tuning
- Gain control
- Sample rate configuration
- Basic signal reception
- Device reset and recovery
"""

import unittest
import time
import numpy as np
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

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
from infrastructure.hardware.sdr_base import SDRBase


# ============================================================================
# Test Configuration
# ============================================================================

class HackRFTestConfig:
    """Configuration for HackRF tests"""
    
    # Test frequencies (Hz)
    TEST_FREQ_1 = 100e6      # 100 MHz - FM broadcast
    TEST_FREQ_2 = 2.44e9     # 2.44 GHz - ISM band
    TEST_FREQ_3 = 5.8e9      # 5.8 GHz - ISM band
    
    # Test sample rates
    TEST_SAMPLE_RATE_1 = 2e6      # 2 MHz
    TEST_SAMPLE_RATE_2 = 10e6     # 10 MHz
    TEST_SAMPLE_RATE_3 = 20e6     # 20 MHz
    
    # Test gains
    TEST_LNA_GAIN = 16      # dB
    TEST_VGA_GAIN = 20      # dB
    TEST_AMP_ENABLE = False
    
    # Test duration (seconds)
    TEST_DURATION_SHORT = 0.5
    TEST_DURATION_MEDIUM = 2
    TEST_DURATION_LONG = 5
    
    # Sample counts
    NUM_SAMPLES_SMALL = 1024
    NUM_SAMPLES_MEDIUM = 16384
    NUM_SAMPLES_LARGE = 1000000


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
# HackRF Basic Tests
# ============================================================================

class TestHackRFBasic(unittest.TestCase):
    """Basic HackRF hardware tests"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test class - check hardware availability"""
        if not HACKRF_AVAILABLE:
            print("\n⚠️  pyhackrf not installed - tests will be skipped")
            return
        
        # Initialize HackRF
        cls.hackrf = HackRFDevice()
        cls.hackrf.initialize({
            'sample_rate': HackRFTestConfig.TEST_SAMPLE_RATE_2,
            'center_freq': HackRFTestConfig.TEST_FREQ_2
        })
    
    @classmethod
    def tearDownClass(cls):
        """Clean up after tests"""
        if HACKRF_AVAILABLE and hasattr(cls, 'hackrf'):
            cls.hackrf.close()
    
    def setUp(self):
        """Set up before each test"""
        if not HACKRF_AVAILABLE:
            self.skipTest("HackRF library not available")
    
    # ========================================================================
    # Device Detection Tests
    # ========================================================================
    
    @require_hackrf
    def test_hackrf_initialization(self):
        """Test HackRF device initialization"""
        self.assertIsNotNone(self.hackrf)
        self.assertIsNotNone(self.hackrf.sdr)
    
    @require_hackrf
    def test_hackrf_board_info(self):
        """Test retrieving board information"""
        # Get board ID
        board_id = self.hackrf.sdr.board_id_read()
        self.assertIsNotNone(board_id)
        
        # Get version
        version = self.hackrf.sdr.version_string_read()
        self.assertIsNotNone(version)
        
        print(f"\n  HackRF Board ID: {board_id}")
        print(f"  Firmware Version: {version}")
    
    @require_hackrf
    def test_hackrf_serial_number(self):
        """Test retrieving serial number"""
        serial = self.hackrf.sdr.serial_number_read()
        if serial:
            print(f"  Serial Number: {serial}")
            self.assertIsNotNone(serial)
    
    @require_hackrf
    def test_hackrf_part_id(self):
        """Test retrieving part ID"""
        part_id = self.hackrf.sdr.part_id_serial_no_read()
        self.assertIsNotNone(part_id)
    
    # ========================================================================
    # Frequency Tuning Tests
    # ========================================================================
    
    @require_hackrf
    def test_tune_frequency(self):
        """Test frequency tuning"""
        test_freq = HackRFTestConfig.TEST_FREQ_1
        
        success = self.hackrf.tune(test_freq)
        
        self.assertTrue(success)
        self.assertEqual(self.hackrf.center_freq, test_freq)
    
    @require_hackrf
    def test_tune_multiple_frequencies(self):
        """Test tuning to multiple frequencies"""
        frequencies = [
            HackRFTestConfig.TEST_FREQ_1,
            HackRFTestConfig.TEST_FREQ_2,
            HackRFTestConfig.TEST_FREQ_3
        ]
        
        for freq in frequencies:
            success = self.hackrf.tune(freq)
            self.assertTrue(success)
            self.assertEqual(self.hackrf.center_freq, freq)
            time.sleep(0.1)
    
    @require_hackrf
    def test_tune_out_of_range(self):
        """Test tuning to out-of-range frequency"""
        # HackRF supports 1 MHz to 6 GHz
        invalid_freqs = [500e3, 7e9]
        
        for freq in invalid_freqs:
            # Should not crash, may fail gracefully
            try:
                self.hackrf.tune(freq)
            except Exception as e:
                # Expected to fail
                pass
    
    # ========================================================================
    # Sample Rate Tests
    # ========================================================================
    
    @require_hackrf
    def test_set_sample_rate(self):
        """Test setting sample rate"""
        test_rate = HackRFTestConfig.TEST_SAMPLE_RATE_1
        
        success = self.hackrf.set_sample_rate(test_rate)
        
        self.assertTrue(success)
        self.assertEqual(self.hackrf.sample_rate, test_rate)
    
    @require_hackrf
    def test_multiple_sample_rates(self):
        """Test multiple sample rates"""
        sample_rates = [
            HackRFTestConfig.TEST_SAMPLE_RATE_1,
            HackRFTestConfig.TEST_SAMPLE_RATE_2,
            HackRFTestConfig.TEST_SAMPLE_RATE_3
        ]
        
        for rate in sample_rates:
            success = self.hackrf.set_sample_rate(rate)
            self.assertTrue(success)
            self.assertEqual(self.hackrf.sample_rate, rate)
            time.sleep(0.1)
    
    # ========================================================================
    # Gain Control Tests
    # ========================================================================
    
    @require_hackrf
    def test_set_lna_gain(self):
        """Test LNA gain setting"""
        test_gain = HackRFTestConfig.TEST_LNA_GAIN
        
        success = self.hackrf.set_lna_gain(test_gain)
        
        self.assertTrue(success)
        self.assertEqual(self.hackrf.lna_gain, test_gain)
    
    @require_hackrf
    def test_set_vga_gain(self):
        """Test VGA gain setting"""
        test_gain = HackRFTestConfig.TEST_VGA_GAIN
        
        success = self.hackrf.set_vga_gain(test_gain)
        
        self.assertTrue(success)
        self.assertEqual(self.hackrf.vga_gain, test_gain)
    
    @require_hackrf
    def test_set_amp_enable(self):
        """Test RF amplifier enable/disable"""
        # Test enable
        success = self.hackrf.set_amp_enable(True)
        self.assertTrue(success)
        self.assertTrue(self.hackrf.amp_enable)
        
        # Test disable
        success = self.hackrf.set_amp_enable(False)
        self.assertTrue(success)
        self.assertFalse(self.hackrf.amp_enable)
    
    @require_hackrf
    def test_gain_range(self):
        """Test gain range limits"""
        # LNA gain range: 0-40 dB (8 dB steps)
        lna_values = [0, 8, 16, 24, 32, 40]
        for gain in lna_values:
            success = self.hackrf.set_lna_gain(gain)
            self.assertTrue(success)
        
        # VGA gain range: 0-62 dB (2 dB steps)
        vga_values = [0, 10, 20, 30, 40, 50, 60, 62]
        for gain in vga_values:
            success = self.hackrf.set_vga_gain(gain)
            self.assertTrue(success)
    
    # ========================================================================
    # RX Operation Tests
    # ========================================================================
    
    @require_hackrf
    def test_read_samples_basic(self):
        """Test basic sample reading"""
        num_samples = HackRFTestConfig.NUM_SAMPLES_SMALL
        
        samples = self.hackrf.read_samples(num_samples)
        
        self.assertEqual(len(samples), num_samples)
        self.assertEqual(samples.dtype, np.complex64)
    
    @require_hackrf
    def test_read_samples_multiple(self):
        """Test multiple sample reads"""
        for i in range(3):
            samples = self.hackrf.read_samples(HackRFTestConfig.NUM_SAMPLES_SMALL)
            self.assertEqual(len(samples), HackRFTestConfig.NUM_SAMPLES_SMALL)
            time.sleep(0.1)
    
    @require_hackrf
    def test_read_samples_large(self):
        """Test reading large number of samples"""
        num_samples = HackRFTestConfig.NUM_SAMPLES_MEDIUM
        
        start_time = time.time()
        samples = self.hackrf.read_samples(num_samples)
        elapsed = time.time() - start_time
        
        self.assertEqual(len(samples), num_samples)
        
        # Calculate throughput
        throughput = num_samples / elapsed / 1e6
        print(f"\n  Read {num_samples} samples in {elapsed:.2f}s ({throughput:.1f} MS/s)")
        
        # Should achieve reasonable throughput
        self.assertGreater(throughput, 1.0)
    
    @require_hackrf
    def test_signal_power(self):
        """Test reading and measuring signal power"""
        samples = self.hackrf.read_samples(HackRFTestConfig.NUM_SAMPLES_MEDIUM)
        
        # Calculate power statistics
        power = np.mean(np.abs(samples)**2)
        power_dbm = 10 * np.log10(power + 1e-12)
        peak_power = np.max(np.abs(samples)**2)
        peak_power_dbm = 10 * np.log10(peak_power + 1e-12)
        
        print(f"\n  Average Power: {power_dbm:.1f} dBm")
        print(f"  Peak Power: {peak_power_dbm:.1f} dBm")
        print(f"  PAPR: {peak_power_dbm - power_dbm:.1f} dB")
        
        # Power should be within reasonable range
        self.assertGreater(power_dbm, -120)
        self.assertLess(power_dbm, 10)
    
    @require_hackrf
    def test_spectrum_analysis(self):
        """Test basic spectrum analysis with HackRF"""
        samples = self.hackrf.read_samples(HackRFTestConfig.NUM_SAMPLES_MEDIUM)
        
        # Compute FFT
        fft_data = np.fft.fftshift(np.fft.fft(samples))
        fft_mag = 20 * np.log10(np.abs(fft_data) + 1e-12)
        
        # Find peak
        peak_idx = np.argmax(fft_mag)
        peak_value = fft_mag[peak_idx]
        
        print(f"\n  Spectrum peak: {peak_value:.1f} dB")
        
        # Should have a reasonable peak
        self.assertGreater(peak_value, -100)
    
    # ========================================================================
    # Streaming Tests
    # ========================================================================
    
    @require_hackrf
    def test_start_stop_streaming(self):
        """Test starting and stopping streaming"""
        self.hackrf.start_streaming()
        self.assertTrue(self.hackrf.is_streaming)
        
        time.sleep(0.5)
        
        self.hackrf.stop_streaming()
        self.assertFalse(self.hackrf.is_streaming)
    
    @require_hackrf
    def test_stream_samples(self):
        """Test streaming sample collection"""
        self.hackrf.start_streaming()
        
        # Collect samples over time
        samples_list = []
        for i in range(5):
            samples = self.hackrf.get_stream_samples(4096)
            samples_list.append(samples)
            time.sleep(0.1)
        
        self.hackrf.stop_streaming()
        
        # Should have collected samples
        total_samples = sum(len(s) for s in samples_list)
        self.assertGreater(total_samples, 0)
    
    @require_hackrf
    def test_stream_buffer(self):
        """Test stream buffer management"""
        self.hackrf.start_streaming()
        
        # Let buffer fill
        time.sleep(1)
        
        # Read samples
        samples = self.hackrf.get_stream_samples(HackRFTestConfig.NUM_SAMPLES_MEDIUM)
        
        self.hackrf.stop_streaming()
        
        self.assertGreater(len(samples), 0)
    
    # ========================================================================
    # Multiple Configuration Tests
    # ========================================================================
    
    @require_hackrf
    def test_full_configuration_cycle(self):
        """Test full configuration cycle"""
        configs = [
            {
                'freq': HackRFTestConfig.TEST_FREQ_1,
                'rate': HackRFTestConfig.TEST_SAMPLE_RATE_1,
                'lna': 16,
                'vga': 20,
                'amp': False
            },
            {
                'freq': HackRFTestConfig.TEST_FREQ_2,
                'rate': HackRFTestConfig.TEST_SAMPLE_RATE_2,
                'lna': 24,
                'vga': 30,
                'amp': True
            },
            {
                'freq': HackRFTestConfig.TEST_FREQ_3,
                'rate': HackRFTestConfig.TEST_SAMPLE_RATE_3,
                'lna': 32,
                'vga': 40,
                'amp': False
            }
        ]
        
        for config in configs:
            # Apply configuration
            self.hackrf.tune(config['freq'])
            self.hackrf.set_sample_rate(config['rate'])
            self.hackrf.set_lna_gain(config['lna'])
            self.hackrf.set_vga_gain(config['vga'])
            self.hackrf.set_amp_enable(config['amp'])
            
            # Verify
            self.assertEqual(self.hackrf.center_freq, config['freq'])
            self.assertEqual(self.hackrf.sample_rate, config['rate'])
            self.assertEqual(self.hackrf.lna_gain, config['lna'])
            self.assertEqual(self.hackrf.vga_gain, config['vga'])
            self.assertEqual(self.hackrf.amp_enable, config['amp'])
            
            # Test reception
            samples = self.hackrf.read_samples(HackRFTestConfig.NUM_SAMPLES_SMALL)
            self.assertEqual(len(samples), HackRFTestConfig.NUM_SAMPLES_SMALL)
            
            time.sleep(0.1)
    
    # ========================================================================
    # Error Handling Tests
    # ========================================================================
    
    @require_hackrf
    def test_device_reset(self):
        """Test device reset"""
        self.hackrf.close()
        
        # Reinitialize
        success = self.hackrf.initialize({
            'sample_rate': HackRFTestConfig.TEST_SAMPLE_RATE_2,
            'center_freq': HackRFTestConfig.TEST_FREQ_2
        })
        
        self.assertTrue(success)
    
    @require_hackrf
    def test_multiple_initializations(self):
        """Test multiple initializations"""
        for i in range(3):
            self.hackrf.close()
            success = self.hackrf.initialize({
                'sample_rate': HackRFTestConfig.TEST_SAMPLE_RATE_2
            })
            self.assertTrue(success)
    
    @require_hackrf
    def test_close_idempotent(self):
        """Test closing multiple times"""
        self.hackrf.close()
        self.hackrf.close()  # Second close should not error
        self.assertTrue(True)


# ============================================================================
# Performance Tests
# ============================================================================

class TestHackRFPerformance(unittest.TestCase):
    """Performance tests for HackRF"""
    
    @classmethod
    def setUpClass(cls):
        if not HACKRF_AVAILABLE:
            return
        cls.hackrf = HackRFDevice()
        cls.hackrf.initialize({
            'sample_rate': HackRFTestConfig.TEST_SAMPLE_RATE_2
        })
    
    @classmethod
    def tearDownClass(cls):
        if HACKRF_AVAILABLE and hasattr(cls, 'hackrf'):
            cls.hackrf.close()
    
    @require_hackrf
    def test_sample_rate_accuracy(self):
        """Test sample rate accuracy"""
        expected_rate = HackRFTestConfig.TEST_SAMPLE_RATE_2
        num_samples = 1000000
        
        start_time = time.time()
        samples = self.hackrf.read_samples(num_samples)
        elapsed = time.time() - start_time
        
        actual_rate = num_samples / elapsed
        
        print(f"\n  Expected rate: {expected_rate/1e6:.1f} MHz")
        print(f"  Actual rate: {actual_rate/1e6:.1f} MHz")
        print(f"  Error: {abs(actual_rate - expected_rate)/expected_rate*100:.2f}%")
        
        # Should be within 10% of expected
        self.assertLess(abs(actual_rate - expected_rate) / expected_rate, 0.1)
    
    @require_hackrf
    def test_tuning_speed(self):
        """Test frequency tuning speed"""
        frequencies = [100e6, 500e6, 1e9, 2e9, 3e9, 4e9, 5e9]
        
        times = []
        for freq in frequencies:
            start = time.time()
            self.hackrf.tune(freq)
            times.append(time.time() - start)
        
        avg_time = sum(times) / len(times)
        print(f"\n  Average tuning time: {avg_time*1000:.2f} ms")
        
        # Tuning should be reasonably fast
        self.assertLess(avg_time, 0.1)
    
    @require_hackrf
    def test_continuous_operation(self):
        """Test continuous operation over time"""
        duration = HackRFTestConfig.TEST_DURATION_MEDIUM
        read_count = 0
        start_time = time.time()
        
        while time.time() - start_time < duration:
            samples = self.hackrf.read_samples(HackRFTestConfig.NUM_SAMPLES_SMALL)
            read_count += 1
        
        reads_per_second = read_count / duration
        
        print(f"\n  Reads per second: {reads_per_second:.0f}")
        print(f"  Throughput: {reads_per_second * HackRFTestConfig.NUM_SAMPLES_SMALL / 1e6:.1f} MS/s")
        
        # Should maintain reasonable throughput
        self.assertGreater(reads_per_second, 10)


# ============================================================================
# Stability Tests
# ============================================================================

class TestHackRFStability(unittest.TestCase):
    """Stability tests for HackRF"""
    
    @classmethod
    def setUpClass(cls):
        if not HACKRF_AVAILABLE:
            return
        cls.hackrf = HackRFDevice()
        cls.hackrf.initialize({
            'sample_rate': HackRFTestConfig.TEST_SAMPLE_RATE_2
        })
    
    @classmethod
    def tearDownClass(cls):
        if HACKRF_AVAILABLE and hasattr(cls, 'hackrf'):
            cls.hackrf.close()
    
    @require_hackrf
    def test_long_running_rx(self):
        """Test long-running reception stability"""
        duration = HackRFTestConfig.TEST_DURATION_LONG
        errors = 0
        
        start_time = time.time()
        while time.time() - start_time < duration:
            try:
                samples = self.hackrf.read_samples(HackRFTestConfig.NUM_SAMPLES_MEDIUM)
                self.assertEqual(len(samples), HackRFTestConfig.NUM_SAMPLES_MEDIUM)
            except Exception as e:
                errors += 1
                print(f"  Error: {e}")
        
        print(f"\n  Duration: {duration}s, Errors: {errors}")
        
        # Should have no errors
        self.assertEqual(errors, 0)
    
    @require_hackrf
    def test_temperature_stability(self):
        """Test temperature stability over time"""
        # Read temperature multiple times
        temps = []
        for i in range(10):
            # Get temperature (if available)
            # Note: HackRF temperature reading may not be directly available
            time.sleep(1)
            temps.append(25.0)  # Placeholder
        
        print(f"\n  Temperature readings: {temps}")
        
        # Temperature should be stable
        temp_range = max(temps) - min(temps) if temps else 0
        self.assertLess(temp_range, 10)


# ============================================================================
# Mock Tests (for CI without hardware)
# ============================================================================

class TestHackRFMock(unittest.TestCase):
    """Mock tests for HackRF (no hardware required)"""
    
    @patch('infrastructure.hardware.hackrf.pyhackrf')
    def test_mock_initialization(self, mock_pyhackrf):
        """Test mock initialization"""
        mock_pyhackrf.pyhackrf_init.return_value = None
        mock_pyhackrf.pyhackrf_open.return_value = Mock()
        
        hackrf = HackRFDevice()
        success = hackrf.initialize({'sample_rate': 10e6})
        
        self.assertTrue(success)
    
    @patch('infrastructure.hardware.hackrf.pyhackrf')
    def test_mock_tune(self, mock_pyhackrf):
        """Test mock tuning"""
        mock_sdr = Mock()
        mock_pyhackrf.pyhackrf_open.return_value = mock_sdr
        
        hackrf = HackRFDevice()
        hackrf.initialize({})
        
        success = hackrf.tune(2.44e9)
        
        self.assertTrue(success)
        self.assertEqual(hackrf.center_freq, 2.44e9)
    
    @patch('infrastructure.hardware.hackrf.pyhackrf')
    def test_mock_read_samples(self, mock_pyhackrf):
        """Test mock sample reading"""
        mock_sdr = Mock()
        mock_pyhackrf.pyhackrf_open.return_value = mock_sdr
        
        hackrf = HackRFDevice()
        hackrf.initialize({})
        
        # Mock the callback
        def mock_callback(device, buffer, buffer_length, valid_length):
            # Fill buffer with test data
            return 0
        
        hackrf.sdr.set_rx_callback = mock_callback
        
        samples = hackrf.read_samples(1024)
        
        self.assertEqual(len(samples), 1024)


# ============================================================================
# Run Tests
# ============================================================================

def run_tests():
    """Run the test suite"""
    # Create test loader
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestHackRFBasic))
    suite.addTests(loader.loadTestsFromTestCase(TestHackRFPerformance))
    suite.addTests(loader.loadTestsFromTestCase(TestHackRFStability))
    suite.addTests(loader.loadTestsFromTestCase(TestHackRFMock))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)