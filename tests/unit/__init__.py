#!/usr/bin/env python3
# drone-detector/tests/unit/__init__.py
"""
Unit Tests Package

This package contains all unit tests for the Drone Detection System.
Unit tests focus on testing individual components in isolation,
using mocks and patches to avoid external dependencies.

Test Organization:
- domain/: Tests for core business logic (algorithms, entities, policies)
- infrastructure/: Tests for infrastructure components (hardware, storage, messaging)
- app/: Tests for application layer (services, pipelines, workers)
- api/: Tests for API routes and handlers
"""

import os
import sys
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Test configuration
TEST_CONFIG = {
    'debug': False,
    'timeout': 30,
    'mock_external_services': True,
    'use_test_database': True
}

# Test data directory
TEST_DATA_DIR = PROJECT_ROOT / "tests" / "data"
TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Test database path
TEST_DB_PATH = TEST_DATA_DIR / "test_detections.db"


# ============================================================================
# Test Helpers
# ============================================================================

def setup_test_environment():
    """Set up test environment before running tests"""
    import logging
    logging.disable(logging.CRITICAL)
    
    # Set environment variables for testing
    os.environ['TESTING'] = 'true'
    os.environ['MOCK_HARDWARE'] = 'true'
    
    print("Test environment initialized")


def teardown_test_environment():
    """Clean up test environment after tests"""
    # Clean up test database
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
    
    # Clean up test data directory
    for file in TEST_DATA_DIR.iterdir():
        if file.is_file():
            file.unlink()
    
    print("Test environment cleaned up")


# ============================================================================
# Common Test Fixtures
# ============================================================================

class BaseTestCase:
    """Base test case with common functionality"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test class"""
        setup_test_environment()
    
    @classmethod
    def tearDownClass(cls):
        """Tear down test class"""
        teardown_test_environment()
    
    def assertAlmostEqualList(self, list1, list2, delta=1e-6):
        """Assert two lists are almost equal"""
        self.assertEqual(len(list1), len(list2))
        for a, b in zip(list1, list2):
            self.assertAlmostEqual(a, b, delta=delta)
    
    def assertNumpyEqual(self, arr1, arr2, rtol=1e-5, atol=1e-8):
        """Assert two numpy arrays are equal"""
        import numpy as np
        np.testing.assert_allclose(arr1, arr2, rtol=rtol, atol=atol)


# ============================================================================
# Test Data Generators
# ============================================================================

class TestDataGenerator:
    """Generate test data for unit tests"""
    
    @staticmethod
    def generate_iq_samples(num_samples: int = 1024, sample_rate: float = 10e6) -> np.ndarray:
        """Generate synthetic IQ samples for testing"""
        import numpy as np
        t = np.arange(num_samples) / sample_rate
        # Generate a complex signal with multiple frequency components
        signal = np.exp(1j * 2 * np.pi * 100e3 * t)
        signal += 0.5 * np.exp(1j * 2 * np.pi * 200e3 * t)
        signal += 0.3 * np.exp(1j * 2 * np.pi * 300e3 * t)
        noise = 0.1 * (np.random.randn(num_samples) + 1j * np.random.randn(num_samples))
        return (signal + noise).astype(np.complex64)
    
    @staticmethod
    def generate_test_detection(detection_id: str = "det_001") -> dict:
        """Generate test detection data"""
        from datetime import datetime
        return {
            'id': detection_id,
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
    def generate_test_alert(alert_id: str = "alert_001") -> dict:
        """Generate test alert data"""
        from datetime import datetime
        return {
            'id': alert_id,
            'severity': 'CRITICAL',
            'title': 'Test Alert',
            'message': 'This is a test alert',
            'timestamp': datetime.now().isoformat(),
            'detection_id': 'det_001',
            'acknowledged': False,
            'resolved': False
        }
    
    @staticmethod
    def generate_test_spectrum(fft_size: int = 1024) -> dict:
        """Generate test spectrum data"""
        import numpy as np
        frequencies = np.linspace(2.4e9, 2.5e9, fft_size)
        psd = -80 + 20 * np.random.randn(fft_size)
        # Add a peak
        peak_idx = np.argmin(np.abs(frequencies - 2.44e9))
        psd[peak_idx] = -45
        return {
            'frequencies': frequencies.tolist(),
            'psd': psd.tolist(),
            'sample_rate': 10e6,
            'center_freq': 2.44e9
        }


# ============================================================================
# Mock Classes for Testing
# ============================================================================

class MockHardware:
    """Mock hardware device for testing"""
    
    def __init__(self):
        self.is_connected = True
        self.sample_rate = 10e6
        self.center_freq = 2.44e9
        self.gain = 20
    
    def initialize(self, config=None):
        """Initialize hardware"""
        return True
    
    def tune(self, frequency):
        """Tune to frequency"""
        self.center_freq = frequency
        return True
    
    def read_samples(self, num_samples):
        """Read samples"""
        return TestDataGenerator.generate_iq_samples(num_samples)
    
    def close(self):
        """Close hardware"""
        self.is_connected = False


class MockDatabase:
    """Mock database for testing"""
    
    def __init__(self):
        self.detections = []
        self.alerts = []
        self.recordings = []
    
    async def save_detection(self, detection):
        """Save detection"""
        self.detections.append(detection)
        return detection['id']
    
    async def get_detections(self, **filters):
        """Get detections"""
        return self.detections
    
    async def save_alert(self, alert):
        """Save alert"""
        self.alerts.append(alert)
        return alert['id']
    
    async def get_alerts(self, **filters):
        """Get alerts"""
        return self.alerts
    
    async def clear(self):
        """Clear all data"""
        self.detections.clear()
        self.alerts.clear()
        self.recordings.clear()


class MockWebSocket:
    """Mock WebSocket connection for testing"""
    
    def __init__(self):
        self.sent_messages = []
        self.received_messages = []
        self.closed = False
    
    async def accept(self):
        """Accept connection"""
        pass
    
    async def send_json(self, data):
        """Send JSON message"""
        self.sent_messages.append(data)
    
    async def receive_json(self):
        """Receive JSON message"""
        if self.received_messages:
            return self.received_messages.pop(0)
        return {}
    
    async def close(self):
        """Close connection"""
        self.closed = True


# ============================================================================
# Test Discovery
# ============================================================================

def discover_tests():
    """Discover all unit tests"""
    import unittest
    loader = unittest.TestLoader()
    start_dir = Path(__file__).parent
    suite = loader.discover(str(start_dir), pattern="test_*.py")
    return suite


def run_tests(verbosity: int = 2):
    """Run all unit tests"""
    import unittest
    suite = discover_tests()
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    return result.wasSuccessful()


# ============================================================================
# Package Metadata
# ============================================================================

__version__ = "2.0.0"
__author__ = "Drone Detection System Team"
__all__ = [
    # Test helpers
    "setup_test_environment",
    "teardown_test_environment",
    "BaseTestCase",
    "TestDataGenerator",
    
    # Mock classes
    "MockHardware",
    "MockDatabase",
    "MockWebSocket",
    
    # Test discovery
    "discover_tests",
    "run_tests",
    
    # Constants
    "TEST_CONFIG",
    "TEST_DATA_DIR",
    "TEST_DB_PATH"
]

# ============================================================================
# Module Initialization
# ============================================================================

# Configure test environment when module is imported
if os.environ.get('TESTING') != 'true':
    # Only auto-setup if not already in test mode
    setup_test_environment()


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    """Run all unit tests when executed directly"""
    success = run_tests()
    sys.exit(0 if success else 1)