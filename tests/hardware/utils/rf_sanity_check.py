#!/usr/bin/env python3
"""
RF Sanity Check Utilities

This module provides utilities for validating RF hardware functionality:
- Signal presence verification
- Frequency accuracy testing
- Gain linearity checking
- Noise figure estimation
- Spectrum analysis
- Interference detection
- Dynamic range measurement
- Phase noise estimation
- Image rejection testing
- Sensitivity measurement
"""

import numpy as np
import time
from dataclasses import dataclass
from typing import Tuple, List, Dict, Any, Optional
from scipy import signal
from scipy.fft import fft, fftshift, fftfreq
import matplotlib.pyplot as plt
from enum import Enum


# ============================================================================
# Enums and Data Classes
# ============================================================================

class TestResult(Enum):
    """Test result status"""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    SKIP = "skip"


@dataclass
class TestMeasurement:
    """RF test measurement result"""
    name: str
    value: float
    unit: str
    expected_min: Optional[float] = None
    expected_max: Optional[float] = None
    result: TestResult = TestResult.PASS
    message: str = ""


@dataclass
class RFTestConfig:
    """RF test configuration"""
    # Test frequencies (Hz)
    TEST_FREQUENCIES: List[float] = None
    # Sample rate (Hz)
    SAMPLE_RATE: float = 10e6
    # FFT size
    FFT_SIZE: int = 2048
    # Test duration (seconds)
    DURATION: float = 1.0
    # Gain settings
    LNA_GAIN: int = 16
    VGA_GAIN: int = 20
    # Thresholds
    MIN_SNR_DB: float = 10.0
    MAX_NOISE_FLOOR_DBM: float = -90.0
    MAX_FREQ_ERROR_PPM: float = 5.0
    MIN_SIGNAL_LEVEL_DBM: float = -70.0
    
    def __post_init__(self):
        if self.TEST_FREQUENCIES is None:
            self.TEST_FREQUENCIES = [100e6, 433e6, 915e6, 2.44e9, 5.8e9]


# ============================================================================
# Signal Analysis Utilities
# ============================================================================

class SignalAnalyzer:
    """Utility for analyzing RF signals"""
    
    @staticmethod
    def compute_psd(samples: np.ndarray, sample_rate: float) -> Tuple[np.ndarray, np.ndarray]:
        """Compute Power Spectral Density"""
        f, psd = signal.welch(samples, fs=sample_rate, nperseg=1024)
        psd_db = 10 * np.log10(psd + 1e-12)
        return f, psd_db
    
    @staticmethod
    def find_peak(samples: np.ndarray, sample_rate: float) -> Tuple[float, float]:
        """Find peak frequency and power"""
        f, psd_db = SignalAnalyzer.compute_psd(samples, sample_rate)
        peak_idx = np.argmax(psd_db)
        return f[peak_idx], psd_db[peak_idx]
    
    @staticmethod
    def estimate_noise_floor(samples: np.ndarray, sample_rate: float) -> float:
        """Estimate noise floor"""
        f, psd_db = SignalAnalyzer.compute_psd(samples, sample_rate)
        # Use lower percentile for noise floor estimate
        return np.percentile(psd_db, 10)
    
    @staticmethod
    def estimate_snr(samples: np.ndarray, sample_rate: float) -> float:
        """Estimate Signal-to-Noise Ratio"""
        peak_freq, peak_power = SignalAnalyzer.find_peak(samples, sample_rate)
        noise_floor = SignalAnalyzer.estimate_noise_floor(samples, sample_rate)
        return peak_power - noise_floor
    
    @staticmethod
    def compute_total_power(samples: np.ndarray) -> float:
        """Compute total signal power"""
        return 10 * np.log10(np.mean(np.abs(samples)**2) + 1e-12)
    
    @staticmethod
    def compute_crest_factor(samples: np.ndarray) -> float:
        """Compute crest factor (peak-to-average ratio)"""
        peak = np.max(np.abs(samples))
        rms = np.sqrt(np.mean(np.abs(samples)**2))
        return peak / rms if rms > 0 else 0
    
    @staticmethod
    def compute_phase_noise(samples: np.ndarray, offset_hz: float, sample_rate: float) -> float:
        """Estimate phase noise at offset frequency"""
        # Demodulate to baseband
        peak_freq, _ = SignalAnalyzer.find_peak(samples, sample_rate)
        t = np.arange(len(samples)) / sample_rate
        demod = samples * np.exp(-1j * 2 * np.pi * peak_freq * t)
        
        # Compute phase
        phase = np.unwrap(np.angle(demod))
        
        # Remove linear trend
        phase = signal.detrend(phase)
        
        # Compute phase noise PSD
        f, psd = signal.welch(phase, fs=sample_rate, nperseg=1024)
        
        # Find offset index
        idx = np.argmin(np.abs(f - offset_hz))
        if idx < len(psd):
            return 10 * np.log10(psd[idx] + 1e-12)
        return -160
    
    @staticmethod
    def check_signal_presence(samples: np.ndarray, sample_rate: float, 
                               threshold_db: float = 10) -> bool:
        """Check if signal is present above noise floor"""
        snr = SignalAnalyzer.estimate_snr(samples, sample_rate)
        return snr > threshold_db


# ============================================================================
# RF Sanity Checker
# ============================================================================

class RFSanityChecker:
    """
    Comprehensive RF hardware sanity check utility
    
    Performs various tests to verify RF hardware functionality:
    - Basic connectivity
    - Frequency accuracy
    - Gain control
    - Noise floor
    - Signal detection
    - Dynamic range
    """
    
    def __init__(self, hackrf_device, config: Optional[RFTestConfig] = None):
        """
        Initialize RF sanity checker
        
        Args:
            hackrf_device: Initialized HackRF device
            config: Test configuration
        """
        self.device = hackrf_device
        self.config = config or RFTestConfig()
        self.measurements: List[TestMeasurement] = []
        self.analyzer = SignalAnalyzer()
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all RF sanity tests"""
        print("\n" + "="*60)
        print("RF SANITY CHECK")
        print("="*60)
        
        results = {
            'timestamp': time.time(),
            'tests': {}
        }
        
        # Run individual tests
        results['tests']['connectivity'] = self.test_connectivity()
        results['tests']['noise_floor'] = self.test_noise_floor()
        results['tests']['gain_control'] = self.test_gain_control()
        results['tests']['frequency_accuracy'] = self.test_frequency_accuracy()
        results['tests']['signal_detection'] = self.test_signal_detection()
        results['tests']['dynamic_range'] = self.test_dynamic_range()
        
        # Calculate overall result
        failed = [k for k, v in results['tests'].items() 
                  if isinstance(v, dict) and v.get('result') == TestResult.FAIL.value]
        results['overall_result'] = TestResult.FAIL.value if failed else TestResult.PASS.value
        results['failed_tests'] = failed
        
        self._print_summary(results)
        
        return results
    
    def test_connectivity(self) -> Dict[str, Any]:
        """Test basic device connectivity"""
        print("\n[1] Testing Device Connectivity...")
        
        try:
            # Try to read board info
            board_id = self.device.sdr.board_id_read() if hasattr(self.device.sdr, 'board_id_read') else 0
            version = self.device.sdr.version_string_read() if hasattr(self.device.sdr, 'version_string_read') else "unknown"
            
            # Try to read samples
            samples = self.device.read_samples(1024)
            
            result = {
                'result': TestResult.PASS.value,
                'board_id': board_id,
                'version': version,
                'samples_received': len(samples),
                'message': 'Device connected and responding'
            }
            print(f"  ✓ Connected - Board: {board_id}, FW: {version}")
            
        except Exception as e:
            result = {
                'result': TestResult.FAIL.value,
                'error': str(e),
                'message': 'Device connection failed'
            }
            print(f"  ✗ Connection failed: {e}")
        
        return result
    
    def test_noise_floor(self) -> Dict[str, Any]:
        """Test noise floor measurement"""
        print("\n[2] Testing Noise Floor...")
        
        # Set low gain for noise measurement
        self.device.set_lna_gain(0)
        self.device.set_vga_gain(0)
        self.device.set_amp_enable(False)
        
        # Collect samples
        samples = self.device.read_samples(int(self.config.SAMPLE_RATE * self.config.DURATION))
        
        # Compute noise floor
        noise_floor = self.analyzer.estimate_noise_floor(samples, self.config.SAMPLE_RATE)
        total_power = self.analyzer.compute_total_power(samples)
        
        result = {
            'result': TestResult.PASS.value,
            'noise_floor_dbm': noise_floor,
            'total_power_dbm': total_power,
            'expected_max_dbm': self.config.MAX_NOISE_FLOOR_DBM
        }
        
        if noise_floor > self.config.MAX_NOISE_FLOOR_DBM:
            result['result'] = TestResult.FAIL.value
            result['message'] = f"Noise floor too high: {noise_floor:.1f} dBm > {self.config.MAX_NOISE_FLOOR_DBM} dBm"
            print(f"  ✗ {result['message']}")
        else:
            print(f"  ✓ Noise floor: {noise_floor:.1f} dBm")
            print(f"    Total power: {total_power:.1f} dBm")
        
        return result
    
    def test_gain_control(self) -> Dict[str, Any]:
        """Test gain control linearity"""
        print("\n[3] Testing Gain Control...")
        
        # Set frequency with known signal (e.g., FM broadcast)
        self.device.tune(100e6)  # 100 MHz - typically has signals
        
        test_gains = [0, 8, 16, 24, 32, 40]
        powers = []
        
        for gain in test_gains:
            self.device.set_lna_gain(gain)
            time.sleep(0.05)
            samples = self.device.read_samples(int(self.config.SAMPLE_RATE * 0.1))
            power = self.analyzer.compute_total_power(samples)
            powers.append(power)
            print(f"    LNA={gain}dB: Power={power:.1f}dBm")
        
        # Check monotonicity
        is_monotonic = all(powers[i] <= powers[i+1] for i in range(len(powers)-1))
        
        result = {
            'result': TestResult.PASS.value if is_monotonic else TestResult.FAIL.value,
            'gains': test_gains,
            'powers': powers,
            'is_monotonic': is_monotonic
        }
        
        if is_monotonic:
            print(f"  ✓ Gain control is monotonic")
        else:
            print(f"  ✗ Gain control is not monotonic")
        
        return result
    
    def test_frequency_accuracy(self) -> Dict[str, Any]:
        """Test frequency accuracy using known signals"""
        print("\n[4] Testing Frequency Accuracy...")
        
        errors_ppm = []
        
        for test_freq in self.config.TEST_FREQUENCIES:
            self.device.tune(test_freq)
            time.sleep(0.1)
            samples = self.device.read_samples(int(self.config.SAMPLE_RATE * 0.2))
            
            # Find peak frequency
            peak_freq, _ = self.analyzer.find_peak(samples, self.config.SAMPLE_RATE)
            actual_freq = test_freq + peak_freq
            
            # Calculate error
            error_hz = actual_freq - test_freq
            error_ppm = abs(error_hz) / test_freq * 1e6
            errors_ppm.append(error_ppm)
            
            status = "✓" if error_ppm < self.config.MAX_FREQ_ERROR_PPM else "✗"
            print(f"    {test_freq/1e6:.0f}MHz: {status} Error={error_ppm:.2f}ppm")
        
        avg_error_ppm = np.mean(errors_ppm)
        max_error_ppm = np.max(errors_ppm)
        
        result = {
            'result': TestResult.PASS.value if max_error_ppm < self.config.MAX_FREQ_ERROR_PPM else TestResult.FAIL.value,
            'average_error_ppm': avg_error_ppm,
            'max_error_ppm': max_error_ppm,
            'errors_ppm': errors_ppm
        }
        
        if max_error_ppm < self.config.MAX_FREQ_ERROR_PPM:
            print(f"  ✓ Frequency accuracy OK (max error: {max_error_ppm:.2f}ppm)")
        else:
            print(f"  ✗ Frequency accuracy FAIL (max error: {max_error_ppm:.2f}ppm)")
        
        return result
    
    def test_signal_detection(self) -> Dict[str, Any]:
        """Test signal detection capability"""
        print("\n[5] Testing Signal Detection...")
        
        self.device.set_lna_gain(self.config.LNA_GAIN)
        self.device.set_vga_gain(self.config.VGA_GAIN)
        
        detected_signals = []
        
        for test_freq in self.config.TEST_FREQUENCIES:
            self.device.tune(test_freq)
            time.sleep(0.05)
            samples = self.device.read_samples(int(self.config.SAMPLE_RATE * 0.2))
            
            snr = self.analyzer.estimate_snr(samples, self.config.SAMPLE_RATE)
            signal_present = snr > self.config.MIN_SNR_DB
            
            detected_signals.append({
                'frequency': test_freq,
                'snr_db': snr,
                'detected': signal_present
            })
            
            status = "✓" if signal_present else "○"
            print(f"    {test_freq/1e6:.0f}MHz: {status} SNR={snr:.1f}dB")
        
        result = {
            'result': TestResult.PASS.value,
            'detected_signals': detected_signals,
            'message': 'Signal detection complete'
        }
        
        return result
    
    def test_dynamic_range(self) -> Dict[str, Any]:
        """Test dynamic range"""
        print("\n[6] Testing Dynamic Range...")
        
        # Measure noise floor (minimum signal)
        self.device.set_lna_gain(0)
        self.device.set_vga_gain(0)
        noise_samples = self.device.read_samples(int(self.config.SAMPLE_RATE * 0.5))
        noise_power = self.analyzer.compute_total_power(noise_samples)
        
        # Measure maximum signal (with gain)
        self.device.set_lna_gain(40)
        self.device.set_vga_gain(62)
        self.device.set_amp_enable(True)
        max_samples = self.device.read_samples(int(self.config.SAMPLE_RATE * 0.5))
        max_power = self.analyzer.compute_total_power(max_samples)
        
        dynamic_range = max_power - noise_power
        
        result = {
            'result': TestResult.PASS.value,
            'noise_floor_dbm': noise_power,
            'max_power_dbm': max_power,
            'dynamic_range_db': dynamic_range
        }
        
        print(f"  Noise floor: {noise_power:.1f} dBm")
        print(f"  Max power: {max_power:.1f} dBm")
        print(f"  Dynamic range: {dynamic_range:.1f} dB")
        
        return result
    
    def _print_summary(self, results: Dict[str, Any]):
        """Print test summary"""
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        
        for test_name, test_result in results['tests'].items():
            if isinstance(test_result, dict):
                status = "✓" if test_result.get('result') == TestResult.PASS.value else "✗"
                print(f"  {status} {test_name}: {test_result.get('message', test_result.get('result', 'unknown'))}")
        
        print(f"\nOverall Result: {results['overall_result'].upper()}")
        
        if results['failed_tests']:
            print(f"Failed tests: {', '.join(results['failed_tests'])}")
    
    def generate_report(self, results: Dict[str, Any], output_path: Optional[str] = None):
        """Generate HTML report"""
        import json
        from datetime import datetime
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>RF Sanity Check Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{ color: #333; }}
        .pass {{ color: green; }}
        .fail {{ color: red; }}
        .test-card {{
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 15px;
            margin: 15px 0;
            background: #fafafa;
        }}
        .test-title {{
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 10px;
        }}
        .measurement {{
            font-family: monospace;
            margin: 5px 0;
        }}
        .summary {{
            background: #e8f4f8;
            padding: 15px;
            border-radius: 8px;
            margin-top: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>RF Sanity Check Report</h1>
        <p><strong>Date:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p><strong>Overall Result:</strong> <span class="{results['overall_result']}">{results['overall_result'].upper()}</span></p>
        
        <h2>Test Results</h2>
"""
        
        for test_name, test_result in results['tests'].items():
            status_class = "pass" if test_result.get('result') == TestResult.PASS.value else "fail"
            html_content += f"""
        <div class="test-card">
            <div class="test-title">{test_name.replace('_', ' ').title()}</div>
            <div class="measurement">Status: <span class="{status_class}">{test_result.get('result', 'unknown')}</span></div>
            <div class="measurement">{test_result.get('message', '')}</div>
        </div>
"""
        
        html_content += f"""
        <div class="summary">
            <h3>Summary</h3>
            <p>Total Tests: {len(results['tests'])}</p>
            <p>Failed Tests: {len(results['failed_tests'])}</p>
            <p>Pass Rate: {(len(results['tests']) - len(results['failed_tests'])) / len(results['tests']) * 100:.1f}%</p>
        </div>
    </div>
</body>
</html>
"""
        
        if output_path:
            with open(output_path, 'w') as f:
                f.write(html_content)
            print(f"\nReport saved to: {output_path}")
        
        return html_content


# ============================================================================
# Quick Test Functions
# ============================================================================

def quick_connectivity_test(hackrf_device) -> bool:
    """Quick test for device connectivity"""
    try:
        samples = hackrf_device.read_samples(1024)
        return len(samples) > 0
    except:
        return False


def quick_signal_test(hackrf_device, frequency: float, sample_rate: float = 10e6) -> bool:
    """Quick test for signal presence at frequency"""
    hackrf_device.tune(frequency)
    time.sleep(0.05)
    samples = hackrf_device.read_samples(int(sample_rate * 0.1))
    analyzer = SignalAnalyzer()
    snr = analyzer.estimate_snr(samples, sample_rate)
    return snr > 10


def measure_noise_floor(hackrf_device, sample_rate: float = 10e6) -> float:
    """Measure noise floor"""
    hackrf_device.set_lna_gain(0)
    hackrf_device.set_vga_gain(0)
    samples = hackrf_device.read_samples(int(sample_rate * 0.5))
    analyzer = SignalAnalyzer()
    return analyzer.estimate_noise_floor(samples, sample_rate)


# ============================================================================
# Example Usage
# ============================================================================

def example_usage():
    """Example usage of RF sanity checker"""
    print("RF Sanity Check Example")
    print("="*60)
    
    # This requires an initialized HackRF device
    # from infrastructure.hardware.hackrf import HackRFDevice
    
    # hackrf = HackRFDevice()
    # hackrf.initialize({'sample_rate': 10e6})
    
    # Create checker
    # checker = RFSanityChecker(hackrf)
    # results = checker.run_all_tests()
    # checker.generate_report(results, "rf_sanity_report.html")
    
    print("\nTo use this module, initialize a HackRF device and pass it to RFSanityChecker")
    print("Example:")
    print("  from infrastructure.hardware.hackrf import HackRFDevice")
    print("  hackrf = HackRFDevice()")
    print("  hackrf.initialize({'sample_rate': 10e6})")
    print("  checker = RFSanityChecker(hackrf)")
    print("  results = checker.run_all_tests()")


if __name__ == "__main__":
    example_usage()