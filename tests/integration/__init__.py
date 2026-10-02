#!/usr/bin/env python3
# drone-detector/tests/integration/__init__.py
"""
Integration Tests Package

This package contains all integration tests for the Drone Detection System.
Integration tests verify that different components work together correctly,
testing real interactions between modules, databases, APIs, and external services.

Test Categories:
- pipeline/: End-to-end processing pipeline tests
- api/: API endpoint integration tests  
- storage/: Database integration tests
- messaging/: Message queue and WebSocket tests
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from contextlib import contextmanager

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import test utilities
from tests.unit import TestDataGenerator as UnitTestDataGenerator

# ============================================================================
# Test Configuration
# ============================================================================

# Integration test configuration
INTEGRATION_TEST_CONFIG = {
    'debug': False,
    'timeout': 60,  # Longer timeout for integration tests
    'retry_count': 3,
    'retry_delay': 1,
    'use_test_database': True,
    'use_mock_services': False,  # Integration tests use real services
    'cleanup_on_teardown': True
}

# Test directories
INTEGRATION_TEST_DIR = Path(__file__).parent
TEST_DATA_DIR = INTEGRATION_TEST_DIR / "data"
TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Test database paths
TEST_DB_PATH = TEST_DATA_DIR / "test_integration.db"
TEST_POSTGRES_DB = "drone_test_integration"

# Test server configuration
TEST_API_HOST = "localhost"
TEST_API_PORT = 8888
TEST_WS_PORT = 8889

# Service health check endpoints
HEALTH_ENDPOINTS = {
    'api': f"http://{TEST_API_HOST}:{TEST_API_PORT}/health",
    'websocket': f"ws://{TEST_API_HOST}:{TEST_WS_PORT}"
}


# ============================================================================
# Test Helpers
# ============================================================================

def setup_integration_tests():
    """Set up integration test environment"""
    # Disable logging during tests (optional)
    if not INTEGRATION_TEST_CONFIG['debug']:
        logging.disable(logging.CRITICAL)
    
    # Create test directories
    TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Set environment variables for testing
    os.environ['TESTING'] = 'true'
    os.environ['INTEGRATION_TEST'] = 'true'
    os.environ['TEST_DB_PATH'] = str(TEST_DB_PATH)
    
    print("=" * 60)
    print("Integration Test Environment Initialized")
    print(f"Test data directory: {TEST_DATA_DIR}")
    print(f"Test database: {TEST_DB_PATH}")
    print("=" * 60)


def teardown_integration_tests():
    """Clean up integration test environment"""
    # Clean up test database
    if INTEGRATION_TEST_CONFIG['cleanup_on_teardown']:
        if TEST_DB_PATH.exists():
            TEST_DB_PATH.unlink()
    
    # Clean up test data directory
    for file in TEST_DATA_DIR.iterdir():
        if file.is_file() and file.suffix != '.gitkeep':
            file.unlink()
    
    # Reset environment variables
    os.environ.pop('TESTING', None)
    os.environ.pop('INTEGRATION_TEST', None)
    
    # Re-enable logging
    if not INTEGRATION_TEST_CONFIG['debug']:
        logging.disable(logging.NOTSET)
    
    print("\nIntegration test environment cleaned up")


@contextmanager
def integration_test_context():
    """Context manager for integration tests"""
    setup_integration_tests()
    try:
        yield
    finally:
        teardown_integration_tests()


# ============================================================================
# Test Data Generators
# ============================================================================

class IntegrationTestDataGenerator:
    """Generate test data for integration tests"""
    
    @staticmethod
    def create_test_detection_batch(count: int = 10) -> List[Dict[str, Any]]:
        """Create a batch of test detections"""
        detections = []
        for i in range(count):
            detection = UnitTestDataGenerator.generate_test_detection(f"int_det_{i:04d}")
            detection['timestamp'] = f"2024-01-15T{(i % 24):02d}:{(i % 60):02d}:00Z"
            detections.append(detection)
        return detections
    
    @staticmethod
    def create_test_alert_batch(count: int = 10) -> List[Dict[str, Any]]:
        """Create a batch of test alerts"""
        alerts = []
        severities = ['INFO', 'WARNING', 'ALERT', 'CRITICAL']
        for i in range(count):
            alert = UnitTestDataGenerator.generate_test_alert(f"int_alert_{i:04d}")
            alert['severity'] = severities[i % len(severities)]
            alert['timestamp'] = f"2024-01-15T{(i % 24):02d}:{(i % 60):02d}:00Z"
            alerts.append(alert)
        return alerts
    
    @staticmethod
    def create_test_remote_id_batch(count: int = 10) -> List[Dict[str, Any]]:
        """Create a batch of test Remote ID messages"""
        messages = []
        for i in range(count):
            message = {
                'id': f"rid_int_{i:04d}",
                'uas_id': f"UAS_INT_{i:04d}",
                'latitude': 37.7749 + i * 0.0001,
                'longitude': -122.4194 + i * 0.0001,
                'altitude': 100.0 + i * 10,
                'speed': 10.0 + i,
                'heading': (i * 36) % 360,
                'timestamp': f"2024-01-15T{(i % 24):02d}:{(i % 60):02d}:00Z",
                'rssi': -60 - i,
                'operator_id': f"OP_INT_{i:04d}"
            }
            messages.append(message)
        return messages
    
    @staticmethod
    def create_test_geofence_zone(zone_id: str = "test_zone") -> Dict[str, Any]:
        """Create a test geofence zone"""
        return {
            'id': zone_id,
            'name': 'Test Restricted Zone',
            'zone_type': 'restricted',
            'description': 'Integration test zone',
            'coordinates': [
                [-122.4300, 37.7700],
                [-122.4300, 37.7800],
                [-122.4100, 37.7800],
                [-122.4100, 37.7700]
            ],
            'active': True,
            'warning_threshold': 100,
            'alert_threshold': 50
        }


# ============================================================================
# Base Integration Test Class
# ============================================================================

class IntegrationTestCase:
    """Base class for integration tests"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test class"""
        setup_integration_tests()
    
    @classmethod
    def tearDownClass(cls):
        """Tear down test class"""
        teardown_integration_tests()
    
    def setUp(self):
        """Set up test method"""
        self.test_data = IntegrationTestDataGenerator()
        self.start_time = asyncio.get_event_loop().time() if hasattr(asyncio, 'get_event_loop') else 0
    
    def tearDown(self):
        """Tear down test method"""
        pass
    
    def assertResponseOk(self, response):
        """Assert that API response is OK"""
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 200)
    
    def assertResponseCreated(self, response):
        """Assert that resource was created"""
        self.assertIsNotNone(response)
        self.assertIn(response.status_code, [200, 201])
    
    def assertResponseError(self, response, expected_status: int = 400):
        """Assert that API response is an error"""
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, expected_status)


# ============================================================================
# Service Fixtures
# ============================================================================

class ServiceFixture:
    """Base class for service fixtures"""
    
    def __init__(self):
        self._started = False
    
    async def start(self):
        """Start the service"""
        self._started = True
    
    async def stop(self):
        """Stop the service"""
        self._started = False
    
    async def health_check(self) -> bool:
        """Check service health"""
        return self._started
    
    @property
    def is_running(self) -> bool:
        """Check if service is running"""
        return self._started


class DatabaseFixture(ServiceFixture):
    """Database fixture for integration tests"""
    
    def __init__(self, db_path: Path = TEST_DB_PATH):
        super().__init__()
        self.db_path = db_path
        self.engine = None
    
    async def start(self):
        """Start database service"""
        from infrastructure.storage.database import DatabaseManager, DatabaseConfig, DatabaseType
        
        config = DatabaseConfig(
            db_type=DatabaseType.SQLITE,
            sqlite_path=str(self.db_path)
        )
        self.db_manager = DatabaseManager(config)
        await self.db_manager.initialize()
        await self.db_manager.create_tables()
        self._started = True
    
    async def stop(self):
        """Stop database service"""
        if hasattr(self, 'db_manager'):
            await self.db_manager.close()
        self._started = False
    
    async def clear(self):
        """Clear all data from database"""
        if hasattr(self, 'db_manager'):
            await self.db_manager.execute("DELETE FROM detections")
            await self.db_manager.execute("DELETE FROM alerts")
            await self.db_manager.execute("DELETE FROM remote_id_messages")
    
    async def health_check(self) -> bool:
        """Check database health"""
        if not self._started:
            return False
        try:
            result = await self.db_manager.fetch_val("SELECT 1")
            return result == 1
        except:
            return False


class APIFixture(ServiceFixture):
    """API server fixture for integration tests"""
    
    def __init__(self, host: str = TEST_API_HOST, port: int = TEST_API_PORT):
        super().__init__()
        self.host = host
        self.port = port
        self.server = None
        self._task = None
    
    async def start(self):
        """Start API server"""
        from api.main import create_app
        import uvicorn
        
        self.app = create_app()
        config = uvicorn.Config(self.app, host=self.host, port=self.port, log_level="error")
        self.server = uvicorn.Server(config)
        self._task = asyncio.create_task(self.server.serve())
        await asyncio.sleep(1)  # Give server time to start
        self._started = True
    
    async def stop(self):
        """Stop API server"""
        if self.server:
            self.server.should_exit = True
            await self._task
        self._started = False
    
    @property
    def base_url(self) -> str:
        """Get base URL for API"""
        return f"http://{self.host}:{self.port}"
    
    async def health_check(self) -> bool:
        """Check API health"""
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/health") as resp:
                    return resp.status == 200
        except:
            return False


class WebSocketFixture(ServiceFixture):
    """WebSocket server fixture for integration tests"""
    
    def __init__(self, host: str = TEST_API_HOST, port: int = TEST_WS_PORT):
        super().__init__()
        self.host = host
        self.port = port
        self.server = None
        self._task = None
    
    async def start(self):
        """Start WebSocket server"""
        from infrastructure.messaging.websocket_server import start_websocket_server
        
        self._task = asyncio.create_task(start_websocket_server(host=self.host, port=self.port))
        await asyncio.sleep(0.5)
        self._started = True
    
    async def stop(self):
        """Stop WebSocket server"""
        if self._task:
            self._task.cancel()
        self._started = False
    
    @property
    def ws_url(self) -> str:
        """Get WebSocket URL"""
        return f"ws://{self.host}:{self.port}"
    
    async def health_check(self) -> bool:
        """Check WebSocket health"""
        import websockets
        try:
            async with websockets.connect(self.ws_url) as ws:
                await ws.send('{"type": "ping"}')
                response = await asyncio.wait_for(ws.recv(), timeout=2.0)
                return 'pong' in response.lower()
        except:
            return False


# ============================================================================
# Fixture Manager
# ============================================================================

class FixtureManager:
    """Manages service fixtures for integration tests"""
    
    def __init__(self):
        self.fixtures: Dict[str, ServiceFixture] = {}
    
    def register(self, name: str, fixture: ServiceFixture):
        """Register a fixture"""
        self.fixtures[name] = fixture
    
    async def start_all(self):
        """Start all registered fixtures"""
        for name, fixture in self.fixtures.items():
            await fixture.start()
            print(f"Started fixture: {name}")
    
    async def stop_all(self):
        """Stop all registered fixtures"""
        for name, fixture in self.fixtures.items():
            await fixture.stop()
            print(f"Stopped fixture: {name}")
    
    async def health_check_all(self) -> Dict[str, bool]:
        """Check health of all fixtures"""
        results = {}
        for name, fixture in self.fixtures.items():
            results[name] = await fixture.health_check()
        return results
    
    def get(self, name: str) -> Optional[ServiceFixture]:
        """Get a fixture by name"""
        return self.fixtures.get(name)


# ============================================================================
# Global Fixture Manager
# ============================================================================

_fixture_manager: Optional[FixtureManager] = None


async def get_fixture_manager() -> FixtureManager:
    """Get or create the global fixture manager"""
    global _fixture_manager
    if _fixture_manager is None:
        _fixture_manager = FixtureManager()
        
        # Register default fixtures
        _fixture_manager.register('database', DatabaseFixture())
        _fixture_manager.register('api', APIFixture())
        _fixture_manager.register('websocket', WebSocketFixture())
    
    return _fixture_manager


async def setup_integration_services():
    """Setup all integration services"""
    manager = await get_fixture_manager()
    await manager.start_all()
    
    # Verify health
    health = await manager.health_check_all()
    for name, healthy in health.items():
        status = "✓" if healthy else "✗"
        print(f"  {status} {name}: {'healthy' if healthy else 'unhealthy'}")
    
    return manager


async def teardown_integration_services():
    """Teardown all integration services"""
    manager = await get_fixture_manager()
    await manager.stop_all()


# ============================================================================
# Test Discovery
# ============================================================================

def discover_integration_tests():
    """Discover all integration tests"""
    import unittest
    loader = unittest.TestLoader()
    start_dir = INTEGRATION_TEST_DIR
    suite = loader.discover(str(start_dir), pattern="test_*.py")
    return suite


def run_integration_tests(verbosity: int = 2):
    """Run all integration tests"""
    import unittest
    suite = discover_integration_tests()
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    return result.wasSuccessful()


# ============================================================================
# Package Metadata
# ============================================================================

__version__ = "2.0.0"
__author__ = "Drone Detection System Team"
__all__ = [
    # Configuration
    "INTEGRATION_TEST_CONFIG",
    "TEST_DATA_DIR",
    "TEST_DB_PATH",
    "TEST_API_HOST",
    "TEST_API_PORT",
    "TEST_WS_PORT",
    
    # Helpers
    "setup_integration_tests",
    "teardown_integration_tests",
    "integration_test_context",
    
    # Data Generators
    "IntegrationTestDataGenerator",
    
    # Base Test Class
    "IntegrationTestCase",
    
    # Fixtures
    "ServiceFixture",
    "DatabaseFixture",
    "APIFixture",
    "WebSocketFixture",
    "FixtureManager",
    "get_fixture_manager",
    "setup_integration_services",
    "teardown_integration_services",
    
    # Test Discovery
    "discover_integration_tests",
    "run_integration_tests"
]

# ============================================================================
# Module Initialization
# ============================================================================

# Auto-setup when module is imported (if not in test mode)
if not os.environ.get('INTEGRATION_TEST_ACTIVE'):
    # Only setup if explicitly requested
    pass

# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    """Run all integration tests when executed directly"""
    import asyncio
    
    async def main():
        success = await run_integration_tests_async()
        sys.exit(0 if success else 1)
    
    async def run_integration_tests_async():
        """Run integration tests asynchronously"""
        try:
            # Setup services
            await setup_integration_services()
            
            # Run tests
            success = run_integration_tests()
            
            # Teardown services
            await teardown_integration_services()
            
            return success
        except Exception as e:
            print(f"Error running integration tests: {e}")
            return False
    
    asyncio.run(main())