drone-detector/tests/unit/README.md - Unit Tests Documentation

markdown
# Unit Tests Directory

This directory contains all unit tests for the Drone Detection System. Unit tests focus on testing individual components in isolation, using mocks and patches to avoid external dependencies.

## Directory Structure
tests/unit/
├── README.md # This file
├── init.py # Package initialization and test utilities
├── conftest.py # pytest configuration and fixtures
├── domain/ # Domain layer tests
│ ├── init.py
│ ├── test_fft.py # FFT algorithm tests
│ ├── test_psd.py # PSD calculation tests
│ ├── test_peak_detection.py # Peak detection tests
│ ├── test_pattern_matching.py # Pattern matching tests
│ ├── test_ml_classifier.py # ML classifier tests
│ ├── test_remote_id.py # Remote ID decoder tests
│ ├── test_tdoa_engine.py # TDOA engine tests
│ ├── test_spectrum_analyzer.py # Spectrum analyzer tests
│ ├── test_threat_assessment.py # Threat assessment tests
│ └── test_frequency_allocation.py # Frequency allocation tests
├── infrastructure/ # Infrastructure layer tests
│ ├── init.py
│ ├── hardware/
│ │ ├── test_hackrf.py # HackRF device tests
│ │ ├── test_mock_hardware.py # Mock hardware tests
│ │ └── test_antenna_controller.py # Antenna control tests
│ ├── signal_io/
│ │ ├── test_iq_stream.py # IQ streaming tests
│ │ ├── test_recorder.py # Recording tests
│ │ ├── test_playback.py # Playback tests
│ │ └── test_file_reader.py # File reading tests
│ ├── storage/
│ │ ├── test_database.py # Database tests
│ │ ├── test_repositories.py # Repository tests
│ │ └── test_query_builder.py # Query builder tests
│ ├── messaging/
│ │ ├── test_websocket.py # WebSocket tests
│ │ ├── test_event_bus.py # Event bus tests
│ │ ├── test_mqtt_client.py # MQTT client tests
│ │ └── test_redis_pubsub.py # Redis pub/sub tests
│ └── monitoring/
│ ├── test_metrics.py # Metrics tests
│ ├── test_health_check.py # Health check tests
│ └── test_logger.py # Logger tests
├── app/ # Application layer tests
│ ├── init.py
│ ├── test_services.py # Service tests
│ ├── test_pipelines.py # Pipeline tests
│ ├── test_workers.py # Worker tests
│ └── test_startup.py # Startup tests
├── api/ # API layer tests
│ ├── init.py
│ ├── test_routes.py # Route tests
│ ├── test_middleware.py # Middleware tests
│ ├── test_dependencies.py # Dependency tests
│ └── test_schemas.py # Schema validation tests
└── conftest.py # pytest configuration

text

## Test Categories

### Domain Layer Tests (`domain/`)

| Test File | Components Tested | Key Test Areas |
|-----------|-------------------|----------------|
| `test_fft.py` | FFT algorithms | Complex FFT, real FFT, windowing |
| `test_psd.py` | PSD calculations | Welch method, periodogram, multitaper |
| `test_peak_detection.py` | Peak detection | Threshold, prominence, multi-scale |
| `test_pattern_matching.py` | Signal matching | Cross-correlation, likelihood |
| `test_ml_classifier.py` | ML classification | Feature extraction, model prediction |
| `test_remote_id.py` | Remote ID | Packet decoding, validation |
| `test_tdoa_engine.py` | TDOA positioning | Chan method, Taylor series |
| `test_spectrum_analyzer.py` | Spectrum analysis | Modulation recognition, interference |
| `test_threat_assessment.py` | Threat evaluation | Risk scoring, escalation |
| `test_frequency_allocation.py` | Band management | Scanning strategies, priority |

### Infrastructure Layer Tests (`infrastructure/`)

#### Hardware Tests (`hardware/`)

| Test File | Components Tested |
|-----------|-------------------|
| `test_hackrf.py` | HackRF device initialization, tuning, gain control |
| `test_mock_hardware.py` | Mock SDR, signal generation, scenarios |
| `test_antenna_controller.py` | Antenna switching, rotator control |

#### Signal I/O Tests (`signal_io/`)

| Test File | Components Tested |
|-----------|-------------------|
| `test_iq_stream.py` | Ring buffer, streaming, processors |
| `test_recorder.py` | Recording, file rotation, triggers |
| `test_playback.py` | Playback, speed control, seek |
| `test_file_reader.py` | Format detection, file reading |

#### Storage Tests (`storage/`)

| Test File | Components Tested |
|-----------|-------------------|
| `test_database.py` | Connection pooling, queries, transactions |
| `test_repositories.py` | CRUD operations, filtering, pagination |
| `test_query_builder.py` | SQL construction, joins, conditions |

#### Messaging Tests (`messaging/`)

| Test File | Components Tested |
|-----------|-------------------|
| `test_websocket.py` | Connection management, broadcasting |
| `test_event_bus.py` | Event publishing, subscription |
| `test_mqtt_client.py` | MQTT connection, message publishing |
| `test_redis_pubsub.py` | Pub/sub, streams, patterns |

#### Monitoring Tests (`monitoring/`)

| Test File | Components Tested |
|-----------|-------------------|
| `test_metrics.py` | Prometheus metrics collection |
| `test_health_check.py` | Liveness, readiness probes |
| `test_logger.py` | Structured logging, rotation |

### Application Layer Tests (`app/`)

| Test File | Components Tested |
|-----------|-------------------|
| `test_services.py` | Service orchestration, business logic |
| `test_pipelines.py` | Processing pipelines, stages |
| `test_workers.py` | Background tasks, queues |
| `test_startup.py` | Application initialization, shutdown |

### API Layer Tests (`api/`)

| Test File | Components Tested |
|-----------|-------------------|
| `test_routes.py` | Endpoint handlers, responses |
| `test_middleware.py` | Request/response middleware |
| `test_dependencies.py` | Dependency injection |
| `test_schemas.py` | Request/response validation |

## Running Tests

### Basic Test Execution

```bash
# Run all unit tests
python -m pytest tests/unit/ -v

# Run specific test file
python -m pytest tests/unit/domain/test_remote_id.py -v

# Run specific test class
python -m pytest tests/unit/domain/test_remote_id.py::TestRemoteIDDecoder -v

# Run specific test method
python -m pytest tests/unit/domain/test_remote_id.py::TestRemoteIDDecoder::test_decode_valid_ble_packet -v
Test Categories
bash
# Run domain tests only
python -m pytest tests/unit/domain/ -v

# Run infrastructure tests only
python -m pytest tests/unit/infrastructure/ -v

# Run app tests only
python -m pytest tests/unit/app/ -v

# Run API tests only
python -m pytest tests/unit/api/ -v
With Coverage
bash
# Run with coverage report
python -m pytest tests/unit/ --cov=. --cov-report=html

# Run specific module with coverage
python -m pytest tests/unit/domain/test_remote_id.py --cov=domain.algorithms.remote_id_decoder --cov-report=term

# Generate coverage report for all modules
python -m pytest tests/unit/ --cov=. --cov-report=html --cov-report=xml
Parallel Execution
bash
# Run tests in parallel (requires pytest-xdist)
python -m pytest tests/unit/ -n auto

# Run with specific number of workers
python -m pytest tests/unit/ -n 4
With Detailed Output
bash
# Verbose output
python -m pytest tests/unit/ -v

# Show print statements
python -m pytest tests/unit/ -s

# Show slowest tests
python -m pytest tests/unit/ --durations=10
Test Configuration (conftest.py)
python
import pytest
import asyncio
from pathlib import Path

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

@pytest.fixture
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def sample_iq_data():
    """Provide sample IQ data for tests"""
    import numpy as np
    return (np.random.randn(1024) + 1j * np.random.randn(1024)).astype(np.complex64)

@pytest.fixture
def mock_hardware():
    """Provide mock hardware for tests"""
    from tests.unit import MockHardware
    return MockHardware()

@pytest.fixture
def mock_database():
    """Provide mock database for tests"""
    from tests.unit import MockDatabase
    return MockDatabase()

# Markers for test categorization
pytest.mark.domain = pytest.mark.domain
pytest.mark.infrastructure = pytest.mark.infrastructure
pytest.mark.app = pytest.mark.app
pytest.mark.api = pytest.mark.api
pytest.mark.slow = pytest.mark.slow
pytest.mark.async_test = pytest.mark.async_test
Writing Tests
Test Structure Template
python
import unittest
import pytest
from unittest.mock import Mock, patch, AsyncMock

from module_to_test import ClassToTest

class TestClassName(unittest.TestCase):
    """Test class description"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.test_instance = ClassToTest()
        self.test_data = {...}
    
    def tearDown(self):
        """Clean up after tests"""
        pass
    
    def test_method_name_normal_case(self):
        """Test description for normal operation"""
        result = self.test_instance.method(self.test_data)
        self.assertEqual(result, expected)
    
    def test_method_name_edge_case(self):
        """Test description for edge case"""
        result = self.test_instance.method(edge_case_data)
        self.assertIsNone(result)
    
    def test_method_name_error_handling(self):
        """Test description for error handling"""
        with self.assertRaises(ValueError):
            self.test_instance.method(invalid_data)
    
    @pytest.mark.async_test
    async def test_async_method(self):
        """Test async method"""
        result = await self.test_instance.async_method()
        self.assertIsNotNone(result)
Test Naming Convention
Prefix	Meaning	Example
test_method_name_	Test a specific method	test_decode_packet_valid
test_	General test	test_initialization
test_*_error	Error handling	test_decode_invalid_packet_error
test_*_edge_case	Edge cases	test_empty_input_edge_case
Test Data
Test Data Directory
text
tests/unit/data/
├── iq_samples/
│   ├── test_signal.iq          # Sample IQ data
│   └── test_noise.iq           # Noise samples
├── config/
│   ├── test_config.yaml        # Test configuration
│   └── test_signatures.json    # Test signatures
└── expected/
    ├── expected_output.json    # Expected results
    └── expected_spectrum.npy   # Expected spectrum data
Generating Test Data
python
from tests.unit import TestDataGenerator

# Generate IQ samples
iq_data = TestDataGenerator.generate_iq_samples(4096)

# Generate test detection
detection = TestDataGenerator.generate_test_detection("test_001")

# Generate test alert
alert = TestDataGenerator.generate_test_alert("alert_001")
Continuous Integration
GitHub Actions Workflow
yaml
name: Unit Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.9, 3.10, 3.11]
    
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
    - name: Run tests
      run: |
        python -m pytest tests/unit/ -v --cov=. --cov-report=xml
    - name: Upload coverage
      uses: codecov/codecov-action@v3
Test Coverage Goals
Module	Target Coverage	Current
Domain Layer	95%	-
Infrastructure Layer	90%	-
Application Layer	85%	-
API Layer	80%	-
Overall	85%	-
Troubleshooting
Common Issues
Issue	Solution
Import errors	Check PYTHONPATH and project structure
Async test failures	Use @pytest.mark.async_test decorator
Mock not working	Verify patch target path
Database locked	Use in-memory SQLite for tests
Timeout errors	Increase timeout or optimize test
Debugging Tests
bash
# Run with debug output
python -m pytest tests/unit/ -v --capture=no

# Drop into debugger on failure
python -m pytest tests/unit/ --pdb

# Run with print statements visible
python -m pytest tests/unit/ -s
Best Practices
Isolation: Each test should be independent and not rely on other tests

Fast execution: Unit tests should run quickly (< 100ms per test)

Clear naming: Test names should describe what is being tested

Arrange-Act-Assert: Structure tests with clear sections

Mock external dependencies: Use mocks for databases, networks, hardware

Test edge cases: Include boundary conditions and error cases

Use assertions: Verify both return values and side effects

Keep tests simple: One logical assertion per test
