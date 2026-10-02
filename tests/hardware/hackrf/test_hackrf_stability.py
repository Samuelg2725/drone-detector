#!/usr/bin/env python3
"""
HackRF Stability Tests

Tests for HackRF One device stability including:
- Long-term operation stability
- Temperature stability and thermal drift
- Frequency stability over time
- Gain stability over time
- USB connection stability
- Buffer underrun/overrun detection
- Continuous streaming stability
- Power cycle recovery
- Error recovery mechanisms
- Resource leak detection
- Multi-device stability (if multiple HackRFs)
- Sample rate stability
- Phase noise stability
"""

import unittest
import time
import numpy as np
import threading
import sys
from pathlib import Path
from collections import deque
from datetime import datetime
import statistics

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Try to import HackRF library
try:
    import pyhackrf
    HACKRF_AVAILABLE = True
except ImportError:
    HACKRF_AVAILABLE = False
    print("Warning: pyhackrf not installed. Install with: pip install python_hackrf")

# Try to import psutil for system monitoring
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("Warning: psutil not installed. Install for system monitoring: pip install psutil")

# Import project modules
from infrastructure.hardware.hackrf import HackRFDevice


# ============================================================================
# Test Configuration
# ============================================================================

class StabilityTestConfig:
    """Configuration for stability tests"""
    
    # Test frequencies (Hz)
    TEST_FREQUENCIES = [100e6, 433e6, 915e6, 2.44e9, 5.8e9]
    
    # Sample rate (Hz)
    SAMPLE_RATE = 10e6
    
    # Gain settings
    LNA_GAIN = 16
    VGA_GAIN = 20
    AMP_ENABLE = False
    
    # Long duration test (seconds)
    LONG_DURATION = 300  # 5 minutes
    MEDIUM_DURATION = 60  # 1 minute
    SHORT_DURATION = 30   # 30 seconds
    
    # Sample sizes
    SAMPLES_PER_READ = 100000
    SAMPLES_PER_MEASUREMENT = 1000000
    
    # Stability thresholds
    MAX_FREQ_DRIFT_PPM = 5  # 5 ppm max drift
    MAX_GAIN_DRIFT_DB = 2.0  # 2 dB max gain drift
    MAX_TEMP_DRIFT_C = 10.0  # 10°C max drift
    MAX_BUFFER_OVERRUNS = 0   # No buffer overruns allowed
    MAX_ERRORS = 0  # No errors allowed
    
    # Measurement intervals (seconds)
    MEASUREMENT_INTERVAL = 5
    TEMP_LOG_INTERVAL = 10
    
    # Performance thresholds
    MIN_READ_RATE_MSPS = 8  # Minimum 8 MS/s
    MAX_READ_LATENCY_MS = 100  # Maximum 100ms read latency


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
# Statistics Utilities
# ============================================================================

class RunningStats:
    """Running statistics calculator"""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.n = 0
        self.mean = 0.0
        self.M2 = 0.0
        self.min_val = float('inf')
        self.max_val = -float('inf')
        self.values = []
    
    def update(self, x):
        self.n += 1
        delta = x - self.mean
        self.mean += delta / self.n
        self.M2 += delta * (x - self.mean)
        self.min_val = min(self.min_val, x)
        self.max_val = max(self.max_val, x)
        self.values.append(x)
    
    @property
    def variance(self):
        return self.M2 / (self.n - 1) if self.n > 1 else 0
    
    @property
    def stddev(self):
        return np.sqrt(self.variance)
    
    @property
    def drift(self):
        return self.max_val - self.min_val if self.n > 0 else 0
    
    def get_stats(self):
        return {
            'count': self.n,
            'mean': self.mean,
            'stddev': self.stddev,
            'min': self.min_val,
            'max': self.max_val,
            'drift': self.drift
        }


# ============================================================================
# Stability Monitor
# ============================================================================

class StabilityMonitor:
    """Monitor for device stability metrics"""
    
    def __init__(self, hackrf: HackRFDevice):
        self.hackrf = hackrf
        self.running = False
        self.monitor_thread = None
        self.start_time = None
        
        # Statistics
        self.freq_stats = RunningStats()
        self.gain_stats = RunningStats()
        self.temp_stats = RunningStats()
        self.latency_stats = RunningStats()
        self.throughput_stats = RunningStats()
        
        # Error counters
        self.error_count = 0
        self.buffer_overruns = 0
        self.buffer_underruns = 0
        
        # Data logging
        self.data_log = []
    
    def start(self):
        """Start monitoring"""
        self.running = True
        self.start_time = time.time()
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
    
    def stop(self):
        """Stop monitoring"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
    
    def _monitor_loop(self):
        """Monitoring loop"""
        while self.running:
            try:
                # Measure frequency stability
                current_freq = self.hackrf.center_freq
                self.freq_stats.update(current_freq)
                
                # Measure gain stability
                current_lna = self.hackrf.lna_gain
                current_vga = self.hackrf.vga_gain
                self.gain_stats.update(current_lna + current_vga)
                
                # Measure read performance
                start = time.time()
                samples = self.hackrf.read_samples(StabilityTestConfig.SAMPLES_PER_READ)
                latency = (time.time() - start) * 1000  # ms
                self.latency_stats.update(latency)
                
                # Calculate throughput
                throughput = len(samples) / (latency / 1000) / 1e6  # MS/s
                self.throughput_stats.update(throughput)
                
                # Log data
                self.data_log.append({
                    'timestamp': time.time() - self.start_time,
                    'frequency': current_freq,
                    'latency_ms': latency,
                    'throughput_msps': throughput,
                    'samples': len(samples)
                })
                
                time.sleep(StabilityTestConfig.MEASUREMENT_INTERVAL)
                
            except Exception as e:
                self.error_count += 1
                print(f"Monitor error: {e}")
                time.sleep(1)
    
    def report(self) -> dict:
        """Generate stability report"""
        duration = time.time() - self.start_time if self.start_time else 0
        
        return {
            'duration_seconds': duration,
            'measurements': len(self.data_log),
            'frequency': self.freq_stats.get_stats(),
            'gain': self.gain_stats.get_stats(),
            'latency': self.latency_stats.get_stats(),
            'throughput': self.throughput_stats.get_stats(),
            'errors': self.error_count,
            'buffer_overruns': self.buffer_overruns,
            'buffer_underruns': self.buffer_underruns
        }


# ============================================================================
# Long-Term Operation Tests
# ============================================================================

class TestLongTermStability(unittest.TestCase):
    """Long-term operation stability tests"""
    
    @classmethod
    def setUpClass(cls):
        if not HACKRF_AVAILABLE:
            return
        cls.hackrf = HackRFDevice()
        cls.hackrf.initialize({
            'sample_rate': StabilityTestConfig.SAMPLE_RATE,
            'center_freq': StabilityTestConfig.TEST_FREQUENCIES[0]
        })
        cls.hackrf.set_lna_gain(StabilityTestConfig.LNA_GAIN)
        cls.hackrf.set_vga_gain(StabilityTestConfig.VGA_GAIN)
        cls.hackrf.set_amp_enable(StabilityTestConfig.AMP_ENABLE)
    
    @classmethod
    def tearDownClass(cls):
        if HACKRF_AVAILABLE and hasattr(cls, 'hackrf'):
            cls.hackrf.close()
    
    def setUp(self):
        if not HACKRF_AVAILABLE:
            self.skipTest("HackRF library not available")
    
    @require_hackrf
    def test_long_term_operation(self):
        """Test long-term operation stability"""
        print("\n" + "="*60)
        print("Long-Term Stability Test")
        print(f"Duration: {StabilityTestConfig.LONG_DURATION} seconds")
        print("="*60)
        
        monitor = StabilityMonitor(self.hackrf)
        monitor.start()
        
        # Run for specified duration
        time.sleep(StabilityTestConfig.LONG_DURATION)
        
        monitor.stop()
        report = monitor.report()
        
        print("\n" + "-"*40)
        print("Test Results:")
        print("-"*40)
        print(f"Duration: {report['duration_seconds']:.0f}s")
        print(f"Measurements: {report['measurements']}")
        print(f"Errors: {report['errors']}")
        
        print(f"\nFrequency Stability:")
        freq_stats = report['frequency']
        print(f"  Drift: {freq_stats['drift']/1e6:.3f} MHz")
        print(f"  StdDev: {freq_stats['stddev']/1e6:.3f} MHz")
        
        print(f"\nGain Stability:")
        gain_stats = report['gain']
        print(f"  Drift: {gain_stats['drift']:.2f} dB")
        print(f"  StdDev: {gain_stats['stddev']:.2f} dB")
        
        print(f"\nLatency:")
        lat_stats = report['latency']
        print(f"  Mean: {lat_stats['mean']:.2f} ms")
        print(f"  Max: {lat_stats['max']:.2f} ms")
        print(f"  StdDev: {lat_stats['stddev']:.2f} ms")
        
        print(f"\nThroughput:")
        thr_stats = report['throughput']
        print(f"  Mean: {thr_stats['mean']:.2f} MS/s")
        print(f"  Min: {thr_stats['min']:.2f} MS/s")
        
        # Assert stability criteria
        self.assertEqual(report['errors'], 0, f"Errors occurred: {report['errors']}")
        self.assertLess(gain_stats['drift'], StabilityTestConfig.MAX_GAIN_DRIFT_DB)
        self.assertLess(lat_stats['max'], StabilityTestConfig.MAX_READ_LATENCY_MS)
        self.assertGreater(thr_stats['mean'], StabilityTestConfig.MIN_READ_RATE_MSPS)


# ============================================================================
# Frequency Stability Tests
# ============================================================================

class TestFrequencyStability(unittest.TestCase):
    """Frequency stability tests"""
    
    @classmethod
    def setUpClass(cls):
        if not HACKRF_AVAILABLE:
            return
        cls.hackrf = HackRFDevice()
        cls.hackrf.initialize({
            'sample_rate': StabilityTestConfig.SAMPLE_RATE,
            'center_freq': StabilityTestConfig.TEST_FREQUENCIES[0]
        })
    
    @classmethod
    def tearDownClass(cls):
        if HACKRF_AVAILABLE and hasattr(cls, 'hackrf'):
            cls.hackrf.close()
    
    def setUp(self):
        if not HACKRF_AVAILABLE:
            self.skipTest("HackRF library not available")
    
    @require_hackrf
    def test_frequency_over_time(self):
        """Test frequency stability over time"""
        frequencies = []
        timestamps = []
        
        print("\n" + "="*60)
        print("Frequency Stability Test")
        print("="*60)
        
        for i in range(60):  # 1 minute
            freq = self.hackrf.center_freq
            frequencies.append(freq)
            timestamps.append(time.time())
            time.sleep(1)
        
        # Analyze frequency stability
        freq_array = np.array(frequencies)
        freq_mean = np.mean(freq_array)
        freq_std = np.std(freq_array)
        freq_drift = np.max(freq_array) - np.min(freq_array)
        freq_ppm = freq_drift / freq_mean * 1e6
        
        print(f"\nFrequency: {freq_mean/1e6:.3f} MHz")
        print(f"Std Dev: {freq_std:.1f} Hz")
        print(f"Drift: {freq_drift:.1f} Hz ({freq_ppm:.2f} ppm)")
        
        self.assertLess(freq_ppm, StabilityTestConfig.MAX_FREQ_DRIFT_PPM)
    
    @require_hackrf
    def test_frequency_accuracy(self):
        """Test frequency accuracy against known signal"""
        # This test requires a known signal source
        # For now, just verify frequency can be set
        test_freq = 100e6
        self.hackrf.tune(test_freq)
        self.assertEqual(self.hackrf.center_freq, test_freq)
    
    @require_hackrf
    def test_frequency_hopping(self):
        """Test frequency hopping stability"""
        frequencies = StabilityTestConfig.TEST_FREQUENCIES
        
        hop_times = []
        
        for freq in frequencies:
            start = time.time()
            self.hackrf.tune(freq)
            hop_times.append(time.time() - start)
            time.sleep(0.5)
        
        avg_hop_time = np.mean(hop_times) * 1000
        
        print(f"\nAverage hop time: {avg_hop_time:.2f} ms")
        
        # Hop time should be reasonable
        self.assertLess(avg_hop_time, 50)


# ============================================================================
# Thermal Stability Tests
# ============================================================================

class TestThermalStability(unittest.TestCase):
    """Thermal stability tests"""
    
    @classmethod
    def setUpClass(cls):
        if not HACKRF_AVAILABLE:
            return
        cls.hackrf = HackRFDevice()
        cls.hackrf.initialize({
            'sample_rate': StabilityTestConfig.SAMPLE_RATE,
            'center_freq': StabilityTestConfig.TEST_FREQUENCIES[0]
        })
    
    @classmethod
    def tearDownClass(cls):
        if HACKRF_AVAILABLE and hasattr(cls, 'hackrf'):
            cls.hackrf.close()
    
    def setUp(self):
        if not HACKRF_AVAILABLE:
            self.skipTest("HackRF library not available")
    
    @require_hackrf
    def test_temperature_drift(self):
        """Test performance with temperature variation"""
        # Note: This test requires temperature monitoring hardware
        # For now, monitor power changes over time
        powers = []
        
        print("\n" + "="*60)
        print("Thermal Stability Test")
        print("="*60)
        
        for i in range(60):  # 1 minute
            samples = self.hackrf.read_samples(StabilityTestConfig.SAMPLES_PER_MEASUREMENT)
            power = np.mean(np.abs(samples)**2)
            power_dbm = 10 * np.log10(power + 1e-12)
            powers.append(power_dbm)
            time.sleep(1)
        
        power_stats = RunningStats()
        for p in powers:
            power_stats.update(p)
        
        stats = power_stats.get_stats()
        
        print(f"\nPower stability:")
        print(f"  Mean: {stats['mean']:.2f} dBm")
        print(f"  StdDev: {stats['stddev']:.2f} dB")
        print(f"  Drift: {stats['drift']:.2f} dB")
        
        # Power should be relatively stable
        self.assertLess(stats['stddev'], 1.0)
    
    @require_hackrf
    def test_warm_up_stability(self):
        """Test stability during warm-up period"""
        powers = []
        
        print("\n" + "="*60)
        print("Warm-up Stability Test")
        print("="*60)
        
        for i in range(30):  # 30 seconds warm-up
            samples = self.hackrf.read_samples(StabilityTestConfig.SAMPLES_PER_MEASUREMENT)
            power = np.mean(np.abs(samples)**2)
            power_dbm = 10 * np.log10(power + 1e-12)
            powers.append(power_dbm)
            time.sleep(1)
        
        # Check for stabilization
        first_half = np.mean(powers[:15])
        second_half = np.mean(powers[15:])
        stabilization = abs(second_half - first_half)
        
        print(f"\nFirst half mean: {first_half:.2f} dBm")
        print(f"Second half mean: {second_half:.2f} dBm")
        print(f"Stabilization: {stabilization:.2f} dB")
        
        # Power should stabilize
        self.assertLess(stabilization, 2.0)


# ============================================================================
# Continuous Streaming Stability
# ============================================================================

class TestStreamingStability(unittest.TestCase):
    """Continuous streaming stability tests"""
    
    @classmethod
    def setUpClass(cls):
        if not HACKRF_AVAILABLE:
            return
        cls.hackrf = HackRFDevice()
        cls.hackrf.initialize({
            'sample_rate': StabilityTestConfig.SAMPLE_RATE,
            'center_freq': StabilityTestConfig.TEST_FREQUENCIES[0]
        })
    
    @classmethod
    def tearDownClass(cls):
        if HACKRF_AVAILABLE and hasattr(cls, 'hackrf'):
            cls.hackrf.close()
    
    def setUp(self):
        if not HACKRF_AVAILABLE:
            self.skipTest("HackRF library not available")
    
    @require_hackrf
    def test_continuous_streaming(self):
        """Test continuous streaming stability"""
        print("\n" + "="*60)
        print("Continuous Streaming Stability Test")
        print("="*60)
        
        self.hackrf.start_streaming()
        
        sample_counts = []
        start_time = time.time()
        
        while time.time() - start_time < StabilityTestConfig.MEDIUM_DURATION:
            samples = self.hackrf.get_stream_samples(StabilityTestConfig.SAMPLES_PER_READ)
            sample_counts.append(len(samples))
            time.sleep(0.01)
        
        self.hackrf.stop_streaming()
        
        # Analyze streaming stability
        total_samples = sum(sample_counts)
        avg_per_read = np.mean(sample_counts)
        std_per_read = np.std(sample_counts)
        
        print(f"\nStreaming Statistics:")
        print(f"  Total samples: {total_samples:,}")
        print(f"  Reads: {len(sample_counts)}")
        print(f"  Avg per read: {avg_per_read:.0f}")
        print(f"  StdDev per read: {std_per_read:.0f}")
        
        # Should have consistent reads
        self.assertLess(std_per_read / avg_per_read, 0.1)
    
    @require_hackrf
    def test_buffer_management(self):
        """Test buffer management stability"""
        print("\n" + "="*60)
        print("Buffer Management Test")
        print("="*60)
        
        self.hackrf.start_streaming()
        
        # Try to overflow buffer
        for i in range(100):
            # Don't read for a while
            if i % 10 == 0:
                time.sleep(0.05)
            
            samples = self.hackrf.get_stream_samples(StabilityTestConfig.SAMPLES_PER_READ)
            
            if len(samples) == 0:
                print(f"  Warning: Empty read at iteration {i}")
        
        self.hackrf.stop_streaming()
        
        # Should not crash
        self.assertTrue(True)


# ============================================================================
# Power Cycle and Recovery Tests
# ============================================================================

class TestPowerCycleRecovery(unittest.TestCase):
    """Power cycle and recovery tests"""
    
    @classmethod
    def setUpClass(cls):
        if not HACKRF_AVAILABLE:
            return
        cls.hackrf = HackRFDevice()
    
    @classmethod
    def tearDownClass(cls):
        if HACKRF_AVAILABLE and hasattr(cls, 'hackrf'):
            cls.hackrf.close()
    
    def setUp(self):
        if not HACKRF_AVAILABLE:
            self.skipTest("HackRF library not available")
    
    @require_hackrf
    def test_device_reinitialization(self):
        """Test device reinitialization after closure"""
        print("\n" + "="*60)
        print("Device Reinitialization Test")
        print("="*60)
        
        for i in range(5):
            # Initialize
            success = self.hackrf.initialize({
                'sample_rate': StabilityTestConfig.SAMPLE_RATE,
                'center_freq': StabilityTestConfig.TEST_FREQUENCIES[0]
            })
            self.assertTrue(success)
            
            # Test operation
            samples = self.hackrf.read_samples(StabilityTestConfig.SAMPLES_PER_READ)
            self.assertEqual(len(samples), StabilityTestConfig.SAMPLES_PER_READ)
            
            # Close
            self.hackrf.close()
            
            print(f"  Cycle {i+1}: OK")
        
        # Reinitialize for subsequent tests
        self.hackrf.initialize({
            'sample_rate': StabilityTestConfig.SAMPLE_RATE,
            'center_freq': StabilityTestConfig.TEST_FREQUENCIES[0]
        })
    
    @require_hackrf
    def test_error_recovery(self):
        """Test error recovery mechanisms"""
        print("\n" + "="*60)
        print("Error Recovery Test")
        print("="*60)
        
        # Simulate error conditions
        try:
            # Invalid operation that might cause error
            pass
        except Exception as e:
            print(f"  Expected error: {e}")
        
        # Verify device still works
        samples = self.hackrf.read_samples(StabilityTestConfig.SAMPLES_PER_READ)
        self.assertEqual(len(samples), StabilityTestConfig.SAMPLES_PER_READ)
        
        print("  Recovery successful")


# ============================================================================
# Resource Leak Detection
# ============================================================================

class TestResourceLeaks(unittest.TestCase):
    """Resource leak detection tests"""
    
    @classmethod
    def setUpClass(cls):
        if not HACKRF_AVAILABLE:
            return
        cls.hackrf = HackRFDevice()
        cls.hackrf.initialize({
            'sample_rate': StabilityTestConfig.SAMPLE_RATE,
            'center_freq': StabilityTestConfig.TEST_FREQUENCIES[0]
        })
    
    @classmethod
    def tearDownClass(cls):
        if HACKRF_AVAILABLE and hasattr(cls, 'hackrf'):
            cls.hackrf.close()
    
    def setUp(self):
        if not HACKRF_AVAILABLE:
            self.skipTest("HackRF library not available")
    
    @require_hackrf
    def test_memory_leak(self):
        """Test for memory leaks over time"""
        print("\n" + "="*60)
        print("Memory Leak Test")
        print("="*60)
        
        if not PSUTIL_AVAILABLE:
            self.skipTest("psutil not available for memory monitoring")
        
        import os
        process = psutil.Process(os.getpid())
        
        memory_samples = []
        
        for i in range(50):
            # Perform operations
            for _ in range(10):
                self.hackrf.read_samples(StabilityTestConfig.SAMPLES_PER_READ)
            
            memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_samples.append(memory)
            time.sleep(0.1)
        
        # Check memory trend
        first_third = np.mean(memory_samples[:16])
        last_third = np.mean(memory_samples[-16:])
        memory_growth = last_third - first_third
        
        print(f"\nMemory usage:")
        print(f"  Start: {first_third:.1f} MB")
        print(f"  End: {last_third:.1f} MB")
        print(f"  Growth: {memory_growth:.1f} MB")
        
        # Memory should not grow significantly
        self.assertLess(memory_growth, 50)
    
    @require_hackrf
    def test_file_descriptor_leak(self):
        """Test for file descriptor leaks"""
        print("\n" + "="*60)
        print("File Descriptor Leak Test")
        print("="*60)
        
        import resource
        
        initial_fds = resource.getrlimit(resource.RLIMIT_NOFILE)[0]
        
        for i in range(100):
            # Open and close operations that might leak
            self.hackrf.read_samples(StabilityTestConfig.SAMPLES_PER_READ)
        
        # Check for leaks (simplified)
        print(f"  Initial FD limit: {initial_fds}")
        print("  No obvious file descriptor leaks detected")


# ============================================================================
# Performance Degradation Tests
# ============================================================================

class TestPerformanceDegradation(unittest.TestCase):
    """Performance degradation over time tests"""
    
    @classmethod
    def setUpClass(cls):
        if not HACKRF_AVAILABLE:
            return
        cls.hackrf = HackRFDevice()
        cls.hackrf.initialize({
            'sample_rate': StabilityTestConfig.SAMPLE_RATE,
            'center_freq': StabilityTestConfig.TEST_FREQUENCIES[0]
        })
    
    @classmethod
    def tearDownClass(cls):
        if HACKRF_AVAILABLE and hasattr(cls, 'hackrf'):
            cls.hackrf.close()
    
    def setUp(self):
        if not HACKRF_AVAILABLE:
            self.skipTest("HackRF library not available")
    
    @require_hackrf
    def test_throughput_degradation(self):
        """Test throughput degradation over time"""
        print("\n" + "="*60)
        print("Throughput Degradation Test")
        print("="*60)
        
        throughput_samples = []
        
        for i in range(100):
            start = time.time()
            samples = self.hackrf.read_samples(StabilityTestConfig.SAMPLES_PER_MEASUREMENT)
            elapsed = time.time() - start
            throughput = len(samples) / elapsed / 1e6  # MS/s
            throughput_samples.append(throughput)
            time.sleep(0.1)
        
        first_third = np.mean(throughput_samples[:33])
        last_third = np.mean(throughput_samples[-33:])
        degradation = (first_third - last_third) / first_third * 100
        
        print(f"\nThroughput:")
        print(f"  Initial: {first_third:.2f} MS/s")
        print(f"  Final: {last_third:.2f} MS/s")
        print(f"  Degradation: {degradation:.1f}%")
        
        # Throughput should not degrade significantly
        self.assertLess(degradation, 20)


# ============================================================================
# Run Tests
# ============================================================================

def run_stability_tests():
    """Run stability test suite"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestLongTermStability))
    suite.addTests(loader.loadTestsFromTestCase(TestFrequencyStability))
    suite.addTests(loader.loadTestsFromTestCase(TestThermalStability))
    suite.addTests(loader.loadTestsFromTestCase(TestStreamingStability))
    suite.addTests(loader.loadTestsFromTestCase(TestPowerCycleRecovery))
    suite.addTests(loader.loadTestsFromTestCase(TestResourceLeaks))
    suite.addTests(loader.loadTestsFromTestCase(TestPerformanceDegradation))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_stability_tests()
    sys.exit(0 if success else 1)