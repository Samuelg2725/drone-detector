#!/usr/bin/env python3
# drone-detector/tests/e2e/__init__.py
"""
End-to-End Tests Package

This package contains end-to-end tests for the Drone Detection System.
End-to-end tests verify complete user workflows and system integration,
testing the system as a whole from the user's perspective.

Test Categories:
- test_full_detection_cycle.py: Complete detection workflow
- test_dashboard_ui.py: Web dashboard user interface
- test_alert_system.py: Alert generation and notification system
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
from tests.integration import IntegrationTestDataGenerator
from tests.unit import BaseTestCase


# ============================================================================
# Test Configuration
# ============================================================================

class E2ETestConfig:
    """End-to-end test configuration"""
    
    # Server settings
    API_HOST: str = os.environ.get('E2E_API_HOST', 'localhost')
    API_PORT: int = int(os.environ.get('E2E_API_PORT', 8888))
    WS_PORT: int = int(os.environ.get('E2E_WS_PORT', 8889))
    
    # Test timeouts (seconds)
    STARTUP_TIMEOUT: int = 30
    SHUTDOWN_TIMEOUT: int = 10
    TEST_TIMEOUT: int = 60
    
    # Browser settings (for UI tests)
    HEADLESS: bool = os.environ.get('E2E_HEADLESS', 'true').lower() == 'true'
    SLOW_MO: int = int(os.environ.get('E2E_SLOW_MO', 0))
    
    # Test data
    TEST_USER: str = "e2e_test_user"
    TEST_PASSWORD: str = "e2e_test_password"
    TEST_EMAIL: str = "e2e@test.com"
    
    # Paths
    SCREENSHOT_DIR: Path = PROJECT_ROOT / "test_screenshots" / "e2e"
    LOG_DIR: Path = PROJECT_ROOT / "test_logs" / "e2e"
    
    @classmethod
    def ensure_dirs(cls):
        """Ensure test directories exist"""
        cls.SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOG_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# Test Helpers
# ============================================================================

def setup_e2e_environment():
    """Set up end-to-end test environment"""
    E2ETestConfig.ensure_dirs()
    
    # Set environment variables for testing
    os.environ['E2E_TESTING'] = 'true'
    os.environ['TESTING'] = 'true'
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(E2ETestConfig.LOG_DIR / "e2e_tests.log"),
            logging.StreamHandler()
        ]
    )
    
    print("\n" + "="*60)
    print("E2E Test Environment Initialized")
    print(f"API: http://{E2ETestConfig.API_HOST}:{E2ETestConfig.API_PORT}")
    print(f"WebSocket: ws://{E2ETestConfig.API_HOST}:{E2ETestConfig.WS_PORT}")
    print(f"Screenshot Dir: {E2ETestConfig.SCREENSHOT_DIR}")
    print("="*60)


def teardown_e2e_environment():
    """Clean up end-to-end test environment"""
    os.environ.pop('E2E_TESTING', None)
    print("\nE2E test environment cleaned up")


@contextmanager
def e2e_test_context():
    """Context manager for end-to-end tests"""
    setup_e2e_environment()
    try:
        yield
    finally:
        teardown_e2e_environment()


# ============================================================================
# E2E Test Data Generators
# ============================================================================

class E2ETestDataGenerator:
    """Generate test data for end-to-end tests"""
    
    @staticmethod
    def create_test_detection_batch(count: int = 10) -> List[Dict[str, Any]]:
        """Create a batch of test detections"""
        import time
        from datetime import datetime
        
        detections = []
        base_time = datetime.now()
        
        for i in range(count):
            detection = {
                'id': f"e2e_det_{int(time.time())}_{i:04d}",
                'timestamp': (base_time - timedelta(seconds=i*10)).isoformat(),
                'drone_type': ['DJI Mavic 3', 'FPV Analog', 'Autel EVO II'][i % 3],
                'manufacturer': ['DJI', 'Generic', 'Autel'][i % 3],
                'confidence': 0.7 + (i % 3) * 0.1,
                'threat_level': ['LOW', 'MEDIUM', 'HIGH'][i % 3],
                'frequency': 2.44e9 if i % 2 == 0 else 5.8e9,
                'signal_strength': -50 - (i % 30),
                'latitude': 37.7749 + (i * 0.001),
                'longitude': -122.4194 + (i * 0.001),
                'altitude': 50 + i * 10,
                'speed': 5 + i * 2,
                'heading': (i * 36) % 360
            }
            detections.append(detection)
        
        return detections
    
    @staticmethod
    def create_test_alert_batch(count: int = 10) -> List[Dict[str, Any]]:
        """Create a batch of test alerts"""
        import time
        from datetime import datetime
        
        alerts = []
        severities = ['INFO', 'WARNING', 'ALERT', 'CRITICAL']
        categories = ['DRONE_DETECTED', 'GEO_FENCE_VIOLATION', 'INTERFERENCE', 'SYSTEM_ERROR']
        
        for i in range(count):
            alert = {
                'id': f"e2e_alert_{int(time.time())}_{i:04d}",
                'timestamp': datetime.now().isoformat(),
                'severity': severities[i % len(severities)],
                'category': categories[i % len(categories)],
                'title': f"Test Alert {i}",
                'message': f"This is test alert number {i}",
                'source': 'e2e_test',
                'acknowledged': False,
                'resolved': False
            }
            alerts.append(alert)
        
        return alerts
    
    @staticmethod
    def create_test_user() -> Dict[str, Any]:
        """Create test user data"""
        import secrets
        
        return {
            'username': E2ETestConfig.TEST_USER,
            'email': E2ETestConfig.TEST_EMAIL,
            'password': E2ETestConfig.TEST_PASSWORD,
            'full_name': 'E2E Test User',
            'role': 'operator'
        }


# ============================================================================
# E2E Test Fixtures
# ============================================================================

class E2EFixtureManager:
    """Manager for end-to-end test fixtures"""
    
    def __init__(self):
        self.fixtures = {}
        self._initialized = False
    
    def register(self, name: str, fixture):
        """Register a fixture"""
        self.fixtures[name] = fixture
    
    async def initialize_all(self):
        """Initialize all fixtures"""
        for name, fixture in self.fixtures.items():
            if hasattr(fixture, 'initialize'):
                await fixture.initialize()
                print(f"  Initialized fixture: {name}")
        self._initialized = True
    
    async def cleanup_all(self):
        """Clean up all fixtures"""
        for name, fixture in self.fixtures.items():
            if hasattr(fixture, 'cleanup'):
                await fixture.cleanup()
                print(f"  Cleaned up fixture: {name}")
        self._initialized = False
    
    def get(self, name: str):
        """Get a fixture by name"""
        return self.fixtures.get(name)


class APIFixture:
    """API server fixture for E2E tests"""
    
    def __init__(self, host: str = E2ETestConfig.API_HOST, port: int = E2ETestConfig.API_PORT):
        self.host = host
        self.port = port
        self.server = None
        self._task = None
    
    async def initialize(self):
        """Start API server"""
        import uvicorn
        from api.main import create_app
        
        self.app = create_app()
        config = uvicorn.Config(
            self.app, 
            host=self.host, 
            port=self.port, 
            log_level="error"
        )
        self.server = uvicorn.Server(config)
        self._task = asyncio.create_task(self.server.serve())
        
        # Wait for server to start
        await asyncio.sleep(2)
    
    async def cleanup(self):
        """Stop API server"""
        if self.server:
            self.server.should_exit = True
            if self._task:
                await self._task
    
    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"
    
    @property
    def ws_url(self) -> str:
        return f"ws://{self.host}:{E2ETestConfig.WS_PORT}"


class DatabaseFixture:
    """Database fixture for E2E tests"""
    
    def __init__(self, in_memory: bool = True):
        self.in_memory = in_memory
        self.db = None
        self.db_path = None
    
    async def initialize(self):
        """Initialize database"""
        from infrastructure.storage.database import DatabaseManager, DatabaseConfig, DatabaseType
        
        config = DatabaseConfig(
            db_type=DatabaseType.SQLITE,
            sqlite_path=":memory:" if self.in_memory else "data/e2e_test.db"
        )
        
        self.db = DatabaseManager(config)
        await self.db.initialize()
        await self.db.create_tables()
        
        if not self.in_memory:
            self.db_path = config.sqlite_path
    
    async def cleanup(self):
        """Clean up database"""
        if self.db:
            await self.db.close()
        
        if self.db_path and Path(self.db_path).exists():
            Path(self.db_path).unlink()
    
    async def clear(self):
        """Clear all data"""
        if self.db:
            await self.db.execute("DELETE FROM detections")
            await self.db.execute("DELETE FROM alerts")
            await self.db.execute("DELETE FROM remote_id_messages")


class WebSocketFixture:
    """WebSocket fixture for E2E tests"""
    
    def __init__(self, port: int = E2ETestConfig.WS_PORT):
        self.port = port
        self.server = None
        self._task = None
        self.connections = []
    
    async def initialize(self):
        """Start WebSocket server"""
        from infrastructure.messaging.websocket_server import start_websocket_server
        
        self._task = asyncio.create_task(
            start_websocket_server(host='0.0.0.0', port=self.port)
        )
        await asyncio.sleep(1)
    
    async def cleanup(self):
        """Stop WebSocket server"""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


# ============================================================================
# Base E2E Test Class
# ============================================================================

class E2ETestCase:
    """Base class for end-to-end tests"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test class"""
        setup_e2e_environment()
        cls.fixtures = E2EFixtureManager()
    
    @classmethod
    def tearDownClass(cls):
        """Tear down test class"""
        teardown_e2e_environment()
    
    def setUp(self):
        """Set up test method"""
        self.start_time = asyncio.get_event_loop().time()
        self.test_data = E2ETestDataGenerator()
    
    def tearDown(self):
        """Tear down test method"""
        pass
    
    async def take_screenshot(self, page, name: str):
        """Take screenshot for debugging"""
        screenshot_path = E2ETestConfig.SCREENSHOT_DIR / f"{name}.png"
        await page.screenshot(path=str(screenshot_path))
        print(f"  Screenshot saved: {screenshot_path}")
    
    def assertResponseOk(self, response):
        """Assert API response is OK"""
        self.assertIsNotNone(response)
        self.assertEqual(response.status, 200)
    
    def assertResponseCreated(self, response):
        """Assert resource was created"""
        self.assertIsNotNone(response)
        self.assertIn(response.status, [200, 201, 202])
    
    def assertAlertReceived(self, alerts, expected_count: int = 1):
        """Assert alerts were received"""
        self.assertIsNotNone(alerts)
        self.assertGreaterEqual(len(alerts), expected_count)


# ============================================================================
# E2E Test Runner
# ============================================================================

class E2ETestRunner:
    """Runner for end-to-end tests"""
    
    def __init__(self):
        self.fixture_manager = E2EFixtureManager()
        self.results = []
    
    async def setup(self):
        """Set up test runner"""
        # Register fixtures
        self.fixture_manager.register('api', APIFixture())
        self.fixture_manager.register('database', DatabaseFixture())
        self.fixture_manager.register('websocket', WebSocketFixture())
        
        await self.fixture_manager.initialize_all()
    
    async def teardown(self):
        """Tear down test runner"""
        await self.fixture_manager.cleanup_all()
    
    async def run_test(self, test_func, name: str) -> Dict[str, Any]:
        """Run a single test"""
        start = asyncio.get_event_loop().time()
        try:
            await test_func()
            success = True
            error = None
        except Exception as e:
            success = False
            error = str(e)
        
        duration = asyncio.get_event_loop().time() - start
        
        result = {
            'name': name,
            'success': success,
            'duration': duration,
            'error': error
        }
        self.results.append(result)
        
        return result
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*60)
        print("E2E TEST SUMMARY")
        print("="*60)
        
        passed = sum(1 for r in self.results if r['success'])
        failed = len(self.results) - passed
        total = len(self.results)
        
        print(f"\n  Total: {total}")
        print(f"  Passed: {passed}")
        print(f"  Failed: {failed}")
        print(f"  Pass Rate: {(passed/total*100):.1f}%")
        
        if failed > 0:
            print("\n  Failed Tests:")
            for r in self.results:
                if not r['success']:
                    print(f"    ✗ {r['name']}: {r['error'][:100]}")


# ============================================================================
# Module Exports
# ============================================================================

__version__ = "2.0.0"
__author__ = "Drone Detection System Team"

__all__ = [
    # Configuration
    "E2ETestConfig",
    
    # Helpers
    "setup_e2e_environment",
    "teardown_e2e_environment",
    "e2e_test_context",
    
    # Data Generators
    "E2ETestDataGenerator",
    
    # Fixtures
    "E2EFixtureManager",
    "APIFixture",
    "DatabaseFixture",
    "WebSocketFixture",
    
    # Base Class
    "E2ETestCase",
    
    # Runner
    "E2ETestRunner"
]

# ============================================================================
# Module Initialization
# ============================================================================

# Ensure directories exist
E2ETestConfig.ensure_dirs()

# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    """Print test information when run directly"""
    print("End-to-End Tests Package")
    print("=" * 40)
    
    print(f"\nConfiguration:")
    print(f"  API: http://{E2ETestConfig.API_HOST}:{E2ETestConfig.API_PORT}")
    print(f"  WebSocket: ws://{E2ETestConfig.API_HOST}:{E2ETestConfig.WS_PORT}")
    print(f"  Headless: {E2ETestConfig.HEADLESS}")
    print(f"  Screenshot Dir: {E2ETestConfig.SCREENSHOT_DIR}")
    
    print("\nAvailable Test Modules:")
    print("  - test_full_detection_cycle.py: Complete detection workflow")
    print("  - test_dashboard_ui.py: Web dashboard tests")
    print("  - test_alert_system.py: Alert system tests")
    
    print("\nTo run E2E tests:")
    print("  pytest tests/e2e/ -v")
    print("  pytest tests/e2e/test_dashboard_ui.py -v")
    print("  E2E_HEADLESS=false pytest tests/e2e/test_dashboard_ui.py -v")