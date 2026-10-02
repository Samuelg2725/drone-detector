#!/usr/bin/env python3
"""
Pytest Configuration and Shared Fixtures

This module provides shared fixtures and configuration for all tests in the drone-detector project.
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, Any, Generator, AsyncGenerator
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import application components (these will be available once the structure is populated)
from api.main import app
from infrastructure.storage.database import DatabaseManager, DatabaseConfig, DatabaseType
from infrastructure.hardware.mock_hardware import MockSDR
from infrastructure.hardware.hardware_factory import HardwareFactory
from infrastructure.messaging.event_bus import EventBus
from domain.entities.signal import IQSignal
from domain.entities.detection import DetectionEvent, ThreatLevel


# ============================================================================
# Pytest Configuration
# ============================================================================

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers",
        "unit: Mark test as unit test (fast, isolated)"
    )
    config.addinivalue_line(
        "markers",
        "integration: Mark test as integration test (requires services)"
    )
    config.addinivalue_line(
        "markers",
        "hardware: Mark test as hardware test (requires SDR hardware)"
    )
    config.addinivalue_line(
        "markers",
        "slow: Mark test as slow (long running)"
    )
    config.addinivalue_line(
        "markers",
        "performance: Mark test as performance test"
    )
    config.addinivalue_line(
        "markers",
        "e2e: Mark test as end-to-end test"
    )


# ============================================================================
# Basic Fixtures
# ============================================================================

@pytest.fixture
def sample_iq_data() -> bytes:
    """Generate sample IQ data for testing."""
    import struct
    import math
    
    # Generate 1024 samples of IQ data (2 bytes each for I and Q = 4 bytes per sample)
    samples = []
    for i in range(1024):
        # Simple sine wave for I and Q
        phase = 2 * math.pi * i / 128
        i_val = int(32767 * math.sin(phase))
        q_val = int(32767 * math.cos(phase))
        samples.extend(struct.pack('<hh', i_val, q_val))
    
    return b''.join(samples)


@pytest.fixture
def sample_spectrum_data() -> Dict[str, Any]:
    """Generate sample spectrum data for testing."""
    import numpy as np
    
    frequencies = np.linspace(2.4e9, 2.5e9, 1024)
    magnitudes = np.random.exponential(scale=10, size=1024)
    
    # Add a peak at 2.44 GHz (typical drone frequency)
    peak_idx = np.argmin(np.abs(frequencies - 2.44e9))
    magnitudes[peak_idx] = 100
    
    return {
        'frequencies': frequencies.tolist(),
        'magnitudes': magnitudes.tolist(),
        'sample_rate': 10e6,
        'center_frequency': 2.45e9,
        'timestamp': '2024-01-01T00:00:00Z'
    }


@pytest.fixture
def sample_detection_event() -> DetectionEvent:
    """Create a sample detection event for testing."""
    return DetectionEvent(
        id="test_detection_001",
        timestamp=1234567890.0,
        drone_id="test_drone_001",
        frequency=2.44e9,
        confidence=0.95,
        threat_level=ThreatLevel.MEDIUM,
        signal_power=-45.5,
        signal_to_noise=28.3,
        position=None,
        drone_type="DJI Mavic",
        remote_id_data=None
    )


# ============================================================================
# Hardware Fixtures
# ============================================================================

@pytest.fixture
def mock_hardware() -> MockSDR:
    """Create a mock SDR hardware instance for testing."""
    hardware = MockSDR()
    hardware.initialize({
        'sample_rate': 2e6,
        'center_frequency': 2.45e9,
        'gain': 20
    })
    return hardware


@pytest.fixture
def hardware_factory(mock_hardware: MockSDR) -> HardwareFactory:
    """Create a hardware factory configured to use mock hardware."""
    factory = HardwareFactory()
    with patch('infrastructure.hardware.hardware_factory.HackRF', return_value=mock_hardware):
        with patch('infrastructure.hardware.hardware_factory.RTL_SDR', return_value=mock_hardware):
            yield factory


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture
def temp_db_path() -> Generator[str, None, None]:
    """Create a temporary database file for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        tmp_path = tmp.name
    
    yield tmp_path
    
    # Cleanup
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)
    if os.path.exists(tmp_path + '-wal'):
        os.unlink(tmp_path + '-wal')
    if os.path.exists(tmp_path + '-shm'):
        os.unlink(tmp_path + '-shm')


@pytest.fixture
async def database_manager(temp_db_path: str) -> AsyncGenerator[DatabaseManager, None]:
    """Create a database manager with an in-memory database for testing."""
    config = DatabaseConfig(
        db_type=DatabaseType.SQLITE,
        sqlite_path=temp_db_path,
        pool_min_size=1,
        pool_max_size=5
    )
    
    db_manager = DatabaseManager(config)
    await db_manager.initialize()
    await db_manager.create_tables()
    
    yield db_manager
    
    await db_manager.close()


@pytest.fixture
def sqlalchemy_session() -> Generator[Session, None, None]:
    """Create a SQLAlchemy session for ORM testing."""
    # Create in-memory SQLite engine for testing
    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool
    )
    
    # Create tables (import models here to avoid circular imports)
    from infrastructure.storage.models import Base
    Base.metadata.create_all(bind=engine)
    
    # Create session
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        yield db
    finally:
        db.close()


# ============================================================================
# API Fixtures
# ============================================================================

@pytest.fixture
def test_client() -> Generator[TestClient, None, None]:
    """Create a FastAPI test client."""
    with TestClient(app) as client:
        yield client


@pytest.fixture
async def authenticated_client() -> AsyncGenerator[TestClient, None]:
    """Create an authenticated test client."""
    from api.dependencies import get_current_user
    
    # Mock authentication
    async def mock_get_current_user():
        return {"username": "test_user", "role": "admin"}
    
    app.dependency_overrides[get_current_user] = mock_get_current_user
    
    with TestClient(app) as client:
        yield client
    
    app.dependency_overrides.clear()


# ============================================================================
# Event Bus Fixtures
# ============================================================================

@pytest.fixture
def event_bus() -> EventBus:
    """Create an event bus for testing."""
    return EventBus()


@pytest.fixture
async def event_bus_with_listeners() -> AsyncGenerator[EventBus, None]:
    """Create an event bus with registered test listeners."""
    bus = EventBus()
    
    # Create mock listeners
    mock_listener = AsyncMock()
    
    bus.subscribe("test_event", mock_listener)
    
    yield bus
    
    await bus.close()


# ============================================================================
# Configuration Fixtures
# ============================================================================

@pytest.fixture
def test_config() -> Dict[str, Any]:
    """Create test configuration."""
    return {
        'system': {
            'name': 'Drone Detector Test',
            'mode': 'mock',
            'log_level': 'DEBUG'
        },
        'hardware': {
            'type': 'mock',
            'sample_rate': 2e6,
            'center_frequency': 2.45e9,
            'gain': 20
        },
        'detection': {
            'peak_threshold': 10.0,
            'min_confidence': 0.7,
            'update_interval': 0.1
        },
        'api': {
            'host': '127.0.0.1',
            'port': 8888,
            'debug': True
        }
    }


@pytest.fixture
def config_file(temp_db_path: str) -> Generator[str, None, None]:
    """Create a temporary configuration file."""
    config = {
        'system': {
            'mode': 'mock',
            'log_level': 'DEBUG'
        },
        'database': {
            'type': 'sqlite',
            'path': temp_db_path
        },
        'hardware': {
            'type': 'mock',
            'sample_rate': 2e6
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp:
        import yaml
        yaml.dump(config, tmp)
        tmp_path = tmp.name
    
    yield tmp_path
    
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)


# ============================================================================
# Signal Processing Fixtures
# ============================================================================

@pytest.fixture
def iq_signal(sample_iq_data: bytes) -> IQSignal:
    """Create an IQ signal object for testing."""
    return IQSignal(
        data=sample_iq_data,
        sample_rate=2e6,
        center_frequency=2.45e9,
        timestamp=1234567890.0
    )


@pytest.fixture
def drone_iq_signature() -> Dict[str, Any]:
    """Create a drone IQ signature for pattern matching tests."""
    return {
        'drone_type': 'DJI Mavic 3',
        'frequency_band': 2.4e9,
        'bandwidth': 20e6,
        'modulation': 'OFDM',
        'signature_features': {
            'peak_frequencies': [2.440e9, 2.442e9, 2.445e9],
            'peak_widths': [1e6, 0.5e6, 0.8e6],
            'relative_powers': [0, -3, -5]
        }
    }


# ============================================================================
# Async Fixture Helpers
# ============================================================================

@pytest.fixture
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


# ============================================================================
# Mock Services
# ============================================================================

@pytest.fixture
def mock_websocket_server():
    """Create a mock WebSocket server for testing."""
    from unittest.mock import MagicMock, AsyncMock
    
    mock = AsyncMock()
    mock.send = AsyncMock()
    mock.receive = AsyncMock()
    mock.close = AsyncMock()
    
    return mock


@pytest.fixture
def mock_notification_service():
    """Create a mock notification service for testing."""
    from unittest.mock import MagicMock, AsyncMock
    
    service = MagicMock()
    service.send_email = AsyncMock()
    service.send_sms = AsyncMock()
    service.send_webhook = AsyncMock()
    
    return service


# ============================================================================
# Data Fixtures
# ============================================================================

@pytest.fixture
def drone_signatures_json() -> Dict[str, Any]:
    """Load drone signature data for testing."""
    return {
        "signatures": [
            {
                "drone_type": "DJI Mavic",
                "frequencies": [2.4e9, 5.8e9],
                "signal_patterns": ["OFDM", "SDR"],
                "signature_power": -50.0
            },
            {
                "drone_type": "FPV Analog",
                "frequencies": [5.8e9],
                "signal_patterns": ["FM", "Analog"],
                "signature_power": -45.0
            },
            {
                "drone_type": "Custom Build",
                "frequencies": [2.4e9, 5.2e9, 5.8e9],
                "signal_patterns": ["Unknown"],
                "signature_power": -55.0
            }
        ]
    }


# ============================================================================
# Performance Test Helpers
# ============================================================================

@pytest.fixture
def performance_metrics():
    """Provide a metrics collector for performance tests."""
    import time
    from collections import defaultdict
    
    class PerformanceMetrics:
        def __init__(self):
            self.start_time = None
            self.end_time = None
            self.metrics = defaultdict(list)
        
        def start(self):
            self.start_time = time.perf_counter()
        
        def stop(self):
            self.end_time = time.perf_counter()
        
        def record(self, name: str, value: float):
            self.metrics[name].append(value)
        
        @property
        def duration(self):
            if self.start_time and self.end_time:
                return self.end_time - self.start_time
            return 0
        
        def get_stats(self, name: str):
            values = self.metrics.get(name, [])
            if not values:
                return {}
            return {
                'count': len(values),
                'min': min(values),
                'max': max(values),
                'mean': sum(values) / len(values)
            }
    
    return PerformanceMetrics()


# ============================================================================
# Cleanup Fixtures
# ============================================================================

@pytest.fixture(autouse=True)
def cleanup_mocks():
    """Automatically cleanup mocks after each test."""
    yield
    patch.stopall()