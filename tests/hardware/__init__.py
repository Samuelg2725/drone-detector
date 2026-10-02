#!/usr/bin/env python3
# drone-detector/tests/hardware/__init__.py
"""
Hardware Tests Package

This package contains hardware test suites for the Drone Detection System,
including tests for SDR devices (HackRF, RTL-SDR, Pluto), antenna controllers,
and other hardware components.

Test Organization:
- hackrf/: Tests for HackRF One SDR device
- rtl_sdr/: Tests for RTL-SDR dongles
- pluto/: Tests for ADALM-PLUTO
- mock/: Tests for mock hardware simulator
- utils/: Hardware testing utilities and helpers
"""

import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import hardware detection utilities
try:
    from infrastructure.hardware.hackrf import HackRFDevice
    HACKRF_AVAILABLE = True
except ImportError:
    HACKRF_AVAILABLE = False

try:
    from infrastructure.hardware.rtl_sdr import RTL_SDRDevice
    RTL_SDR_AVAILABLE = True
except ImportError:
    RTL_SDR_AVAILABLE = False

try:
    from infrastructure.hardware.pluto import PlutoDevice
    PLUTO_AVAILABLE = True
except ImportError:
    PLUTO_AVAILABLE = False


# ============================================================================
# Test Configuration
# ============================================================================

class HardwareTestConfig:
    """Configuration for hardware tests"""
    
    # Test settings
    SKIP_MISSING_HARDWARE: bool = True
    VERBOSE: bool = True
    TIMEOUT_SECONDS: int = 30
    
    # Test frequencies (Hz)
    TEST_FREQUENCIES_2G: List[float] = [2.400e9, 2.412e9, 2.442e9, 2.472e9, 2.4835e9]
    TEST_FREQUENCIES_5G: List[float] = [5.150e9, 5.180e9, 5.320e9, 5.725e9, 5.825e9, 5.875e9]
    TEST_FREQUENCIES_VHF: List[float] = [88e6, 100e6, 108e6, 144e6, 440e6]
    
    # Test sample rates (Hz)
    TEST_SAMPLE_RATES: List[float] = [1e6, 2.4e6, 5e6, 8e6, 10e6, 20e6]
    
    # Gain settings
    TEST_LNA_GAINS: List[int] = [0, 8, 16, 24, 32, 40]
    TEST_VGA_GAINS: List[int] = [0, 10, 20, 30, 40, 50, 62]
    
    # Performance thresholds
    MIN_SAMPLE_RATE_MSPS: float = 8.0
    MAX_TUNING_TIME_MS: float = 100.0
    MIN_DETECTION_SNR_DB: float = 10.0
    MAX_NOISE_FLOOR_DBM: float = -85.0
    
    # Paths
    TEST_DATA_DIR: Path = Path(__file__).parent / "data"
    LOG_DIR: Path = Path(__file__).parent / "logs"
    
    def __post_init__(self):
        self.TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.LOG_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# Hardware Detection
# ============================================================================

def detect_available_hardware() -> Dict[str, bool]:
    """
    Detect which hardware devices are available for testing
    
    Returns:
        Dictionary with hardware availability status
    """
    available = {
        'hackrf': False,
        'rtl_sdr': False,
        'pluto': False,
        'mock': True  # Mock is always available
    }
    
    # Check HackRF
    if HACKRF_AVAILABLE:
        try:
            # Try to initialize to check connection
            hackrf = HackRFDevice()
            hackrf.initialize({'sample_rate': 2.4e6})
            hackrf.close()
            available['hackrf'] = True
        except Exception:
            pass
    
    # Check RTL-SDR
    if RTL_SDR_AVAILABLE:
        try:
            rtl = RTL_SDRDevice()
            rtl.initialize({'sample_rate': 2.4e6})
            rtl.close()
            available['rtl_sdr'] = True
        except Exception:
            pass
    
    # Check Pluto
    if PLUTO_AVAILABLE:
        try:
            pluto = PlutoDevice()
            pluto.initialize({'sample_rate': 2.4e6})
            pluto.close()
            available['pluto'] = True
        except Exception:
            pass
    
    return available


def get_available_hardware_list() -> List[str]:
    """
    Get list of available hardware device names
    
    Returns:
        List of available device names
    """
    available = detect_available_hardware()
    return [name for name, avail in available.items() if avail]


def require_hardware(hardware_type: str):
    """
    Decorator to skip tests if required hardware is not available
    
    Args:
        hardware_type: Type of hardware required ('hackrf', 'rtl_sdr', 'pluto')
    """
    def decorator(test_func):
        def wrapper(*args, **kwargs):
            available = detect_available_hardware()
            if not available.get(hardware_type, False):
                raise unittest.SkipTest(f"{hardware_type.upper()} hardware not available")
            return test_func(*args, **kwargs)
        return wrapper
    return decorator


# ============================================================================
# Test Helpers
# ============================================================================

class HardwareTestHelper:
    """Helper class for hardware tests"""
    
    @staticmethod
    def get_test_frequencies(band: str = "all") -> List[float]:
        """
        Get test frequencies for specified band
        
        Args:
            band: Frequency band ('vhf', '2g', '5g', 'all')
            
        Returns:
            List of test frequencies in Hz
        """
        config = HardwareTestConfig()
        frequencies = []
        
        if band in ['vhf', 'all']:
            frequencies.extend(config.TEST_FREQUENCIES_VHF)
        if band in ['2g', 'all']:
            frequencies.extend(config.TEST_FREQUENCIES_2G)
        if band in ['5g', 'all']:
            frequencies.extend(config.TEST_FREQUENCIES_5G)
        
        return frequencies
    
    @staticmethod
    def generate_test_signal(frequency_hz: float, sample_rate: float = 10e6,
                             duration_s: float = 0.1, snr_db: float = 20) -> np.ndarray:
        """Generate test signal for simulation"""
        import numpy as np
        
        num_samples = int(sample_rate * duration_s)
        t = np.arange(num_samples) / sample_rate
        
        # Generate carrier
        signal = np.exp(1j * 2 * np.pi * frequency_hz * t)
        
        # Add noise
        noise_power = 10 ** (-snr_db / 10)
        noise = np.sqrt(noise_power/2) * (np.random.randn(num_samples) + 1j * np.random.randn(num_samples))
        
        return signal + noise
    
    @staticmethod
    def measure_tuning_time(device, frequencies: List[float]) -> float:
        """Measure average tuning time across frequencies"""
        import time
        
        times = []
        for freq in frequencies:
            start = time.time()
            device.tune(freq)
            times.append((time.time() - start) * 1000)
        
        return np.mean(times)
    
    @staticmethod
    def create_test_directory(device_name: str) -> Path:
        """Create test directory for device logs"""
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        test_dir = HardwareTestConfig.LOG_DIR / device_name / timestamp
        test_dir.mkdir(parents=True, exist_ok=True)
        
        return test_dir


# ============================================================================
# Test Result Classes
# ============================================================================

class HardwareTestResult:
    """Container for hardware test results"""
    
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.start_time = None
        self.end_time = None
        self.success = False
        self.message = ""
        self.data: Dict[str, Any] = {}
        self.measurements: List[Dict[str, Any]] = []
    
    def start(self):
        """Start test timing"""
        import time
        self.start_time = time.time()
    
    def stop(self):
        """Stop test timing"""
        import time
        self.end_time = time.time()
    
    @property
    def duration_ms(self) -> float:
        """Get test duration in milliseconds"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary"""
        return {
            'test_name': self.test_name,
            'success': self.success,
            'message': self.message,
            'duration_ms': self.duration_ms,
            'data': self.data,
            'measurements': self.measurements
        }


# ============================================================================
# Base Test Class
# ============================================================================

class HardwareTestCase:
    """Base class for hardware test cases"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test class"""
        cls.config = HardwareTestConfig()
        cls.helper = HardwareTestHelper()
        
        # Create logger
        cls.logger = logging.getLogger(cls.__name__)
        if not cls.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            cls.logger.addHandler(handler)
        
        if cls.config.VERBOSE:
            cls.logger.setLevel(logging.INFO)
        else:
            cls.logger.setLevel(logging.WARNING)
    
    def setUp(self):
        """Set up test method"""
        self.test_result = HardwareTestResult(self._testMethodName)
        self.test_result.start()
    
    def tearDown(self):
        """Tear down test method"""
        self.test_result.stop()
        
        if self.config.VERBOSE:
            status = "PASS" if self.test_result.success else "FAIL"
            print(f"\n  {status} - {self.test_result.test_name} ({self.test_result.duration_ms:.1f}ms)")
    
    def assertTestPass(self, condition: bool, message: str = ""):
        """Assert test condition and record result"""
        self.test_result.success = condition
        self.test_result.message = message
        self.assertTrue(condition, message)
    
    def record_measurement(self, name: str, value: float, unit: str = ""):
        """Record a measurement"""
        self.test_result.measurements.append({
            'name': name,
            'value': value,
            'unit': unit
        })


# ============================================================================
# Module Exports
# ============================================================================

__version__ = "2.0.0"
__author__ = "Drone Detection System Team"

__all__ = [
    # Configuration
    "HardwareTestConfig",
    
    # Hardware detection
    "detect_available_hardware",
    "get_available_hardware_list",
    "require_hardware",
    "HACKRF_AVAILABLE",
    "RTL_SDR_AVAILABLE",
    "PLUTO_AVAILABLE",
    
    # Helpers
    "HardwareTestHelper",
    
    # Results
    "HardwareTestResult",
    
    # Base class
    "HardwareTestCase",
    
    # Constants
    "PROJECT_ROOT"
]

# ============================================================================
# Initialize Hardware Detection
# ============================================================================

# Log hardware availability
_available = detect_available_hardware()
if HardwareTestConfig.VERBOSE:
    print("\nHardware Availability:")
    for device, available in _available.items():
        status = "✓" if available else "✗"
        print(f"  {status} {device.upper()}: {'Available' if available else 'Not available'}")


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    """Print hardware availability when run directly"""
    print("Hardware Tests Package")
    print("=" * 40)
    
    available = detect_available_hardware()
    
    print("\nHardware Availability:")
    for device, avail in available.items():
        status = "✅" if avail else "❌"
        print(f"  {status} {device.upper()}")
    
    print(f"\nTest configuration:")
    print(f"  Skip missing hardware: {HardwareTestConfig.SKIP_MISSING_HARDWARE}")
    print(f"  Test data directory: {HardwareTestConfig.TEST_DATA_DIR}")
    print(f"  Log directory: {HardwareTestConfig.LOG_DIR}")
    
    print("\nTo run hardware tests:")
    print("  pytest tests/hardware/hackrf/ -v")
    print("  pytest tests/hardware/rtl_sdr/ -v")
    print("  pytest tests/hardware/pluto/ -v")
    print("  pytest tests/hardware/mock/ -v")