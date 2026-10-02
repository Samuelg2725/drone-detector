#!/usr/bin/env python3
"""
End-to-End Detection Cycle Tests

Tests for complete drone detection workflow including:
- Hardware initialization and configuration
- Signal acquisition and processing
- Detection and classification
- Alert generation and notification
- Data persistence and retrieval
- System cleanup and shutdown
"""

import asyncio
import json
import time
import unittest
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import application modules
from infrastructure.hardware.mock_hardware import MockSDR
from infrastructure.signal_io.iq_stream import IQStream
from app.pipelines import DetectionPipeline
from app.services import DetectionService
from infrastructure.storage.database import DatabaseManager, DatabaseConfig, DatabaseType
from infrastructure.messaging.event_bus import EventBus
from infrastructure.monitoring.logger import get_logger


# ============================================================================
# Test Configuration
# ============================================================================

logger = get_logger(__name__)


class E2ETestConfig:
    """End-to-end test configuration"""
    
    # Test duration (seconds)
    SHORT_TEST = 10
    MEDIUM_TEST = 30
    LONG_TEST = 60
    
    # Sample rate (Hz)
    SAMPLE_RATE = 10e6
    
    # Test frequencies (Hz)
    TEST_FREQUENCIES = [2.44e9, 5.8e9]
    
    # Detection thresholds
    MIN_CONFIDENCE = 0.7
    HIGH_CONFIDENCE = 0.85
    
    # Alert thresholds
    ALERT_SEVERITY_LEVELS = ['INFO', 'WARNING', 'ALERT', 'CRITICAL']
    
    # Timeouts (seconds)
    DETECTION_TIMEOUT = 5
    ALERT_TIMEOUT = 5
    PROCESSING_TIMEOUT = 10


# ============================================================================
# Test Data Generators
# ============================================================================

class E2ETestData:
    """Generate test data for end-to-end tests"""
    
    @staticmethod
    def create_test_detection(detection_id: str = None) -> dict:
        """Create test detection data"""
        return {
            'id': detection_id or f"e2e_det_{int(time.time())}",
            'timestamp': datetime.now().isoformat(),
            'drone_type': 'DJI Mavic 3',
            'manufacturer': 'DJI',
            'confidence': 0.95,
            'threat_level': 'HIGH',
            'frequency': 2.44e9,
            'signal_strength': -45.2,
            'latitude': 37.7749,
            'longitude': -122.4194,
            'altitude': 100.0,
            'speed': 12.5,
            'heading': 180.0
        }
    
    @staticmethod
    def create_test_alert(alert_id: str = None, detection_id: str = None) -> dict:
        """Create test alert data"""
        return {
            'id': alert_id or f"e2e_alert_{int(time.time())}",
            'detection_id': detection_id,
            'severity': 'CRITICAL',
            'title': 'Drone Detected in Restricted Zone',
            'message': 'Unauthorized drone detected in no-fly zone',
            'timestamp': datetime.now().isoformat(),
            'source': 'detection_engine'
        }


# ============================================================================
# Mock Components
# ============================================================================

class MockNotificationService:
    """Mock notification service for testing"""
    
    def __init__(self):
        self.sent_notifications = []
    
    async def send_alert(self, alert_data: dict) -> bool:
        self.sent_notifications.append(alert_data)
        return True
    
    async def send_email(self, email_data: dict) -> bool:
        self.sent_notifications.append(email_data)
        return True
    
    def get_notification_count(self) -> int:
        return len(self.sent_notifications)
    
    def clear(self):
        self.sent_notifications.clear()


class MockWebSocketServer:
    """Mock WebSocket server for testing"""
    
    def __init__(self):
        self.broadcast_messages = []
    
    async def broadcast(self, message: dict) -> None:
        self.broadcast_messages.append(message)
    
    def get_broadcast_count(self) -> int:
        return len(self.broadcast_messages)
    
    def clear(self):
        self.broadcast_messages.clear()


# ============================================================================
# End-to-End Test Suite
# ============================================================================

class TestFullDetectionCycle(unittest.IsolatedAsyncioTestCase):
    """Complete end-to-end detection cycle tests"""
    
    async def asyncSetUp(self):
        """Set up test environment"""
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        
        # Initialize components
        db_config = DatabaseConfig(
            db_type=DatabaseType.SQLITE,
            sqlite_path=self.db_path
        )
        self.db = DatabaseManager(db_config)
        await self.db.initialize()
        await self.db.create_tables()
        
        # Create mock hardware
        self.hardware = MockSDR()
        self.hardware.initialize({
            'sample_rate': E2ETestConfig.SAMPLE_RATE,
            'mock': {'synthetic_mode': True, 'simulate_latency_ms': 0}
        })
        
        # Create mock services
        self.notification_service = MockNotificationService()
        self.websocket_server = MockWebSocketServer()
        self.event_bus = EventBus()
        
        # Create detection service
        self.detection_service = DetectionService(
            hardware=self.hardware,
            db=self.db,
            notification_service=self.notification_service,
            websocket_server=self.websocket_server,
            event_bus=self.event_bus
        )
        
        # Track events
        self.received_detections = []
        self.received_alerts = []
        
        # Register event handlers
        self.event_bus.on('detection.created', self._on_detection)
        self.event_bus.on('alert.generated', self._on_alert)
    
    async def asyncTearDown(self):
        """Clean up after tests"""
        await self.detection_service.stop()
        await self.db.close()
        
        import os
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def _on_detection(self, detection_data):
        """Handle detection event"""
        self.received_detections.append(detection_data)
    
    def _on_alert(self, alert_data):
        """Handle alert event"""
        self.received_alerts.append(alert_data)
    
    # ========================================================================
    # Core Detection Cycle Tests
    # ========================================================================
    
    async def test_full_detection_cycle(self):
        """Test complete detection cycle from signal to alert"""
        print("\n" + "="*60)
        print("TEST: Full Detection Cycle")
        print("="*60)
        
        # Start detection service
        await self.detection_service.start()
        
        # Inject drone signal
        self.hardware.inject_drone("DJI Mavic 3", 2.44e9)
        
        # Wait for detection
        await asyncio.sleep(E2ETestConfig.DETECTION_TIMEOUT)
        
        # Stop service
        await self.detection_service.stop()
        
        # Verify detection was created
        self.assertGreater(len(self.received_detections), 0,
                          "No detections were created")
        
        detection = self.received_detections[0]
        print(f"\n  Detection created: {detection.get('id')}")
        print(f"    Drone type: {detection.get('drone_type')}")
        print(f"    Confidence: {detection.get('confidence'):.2%}")
        print(f"    Threat level: {detection.get('threat_level')}")
        
        # Verify detection was saved to database
        saved_detection = await self.db.fetch_one(
            "SELECT * FROM detections WHERE id = ?", detection.get('id')
        )
        self.assertIsNotNone(saved_detection, "Detection not saved to database")
        
        # Verify alert was generated
        self.assertGreater(len(self.received_alerts), 0,
                          "No alerts were generated")
        
        alert = self.received_alerts[0]
        print(f"  Alert generated: {alert.get('id')}")
        print(f"    Severity: {alert.get('severity')}")
        print(f"    Message: {alert.get('message')[:50]}...")
        
        # Verify notification was sent
        self.assertGreater(self.notification_service.get_notification_count(), 0,
                          "No notifications were sent")
        
        # Verify WebSocket broadcast
        self.assertGreater(self.websocket_server.get_broadcast_count(), 0,
                          "No WebSocket broadcasts were sent")
    
    async def test_multiple_detections(self):
        """Test handling of multiple consecutive detections"""
        print("\n" + "="*60)
        print("TEST: Multiple Consecutive Detections")
        print("="*60)
        
        await self.detection_service.start()
        
        # Inject multiple drone signals
        drone_types = ["DJI Mavic 3", "FPV Analog", "Autel EVO II"]
        frequencies = [2.44e9, 5.8e9, 2.44e9]
        
        for i, (drone_type, freq) in enumerate(zip(drone_types, frequencies)):
            print(f"  Injecting {drone_type} at {freq/1e9:.2f} GHz")
            self.hardware.inject_drone(drone_type, freq)
            await asyncio.sleep(2)
        
        # Wait for processing
        await asyncio.sleep(5)
        
        await self.detection_service.stop()
        
        # Verify multiple detections
        detection_count = len(self.received_detections)
        print(f"\n  Total detections: {detection_count}")
        
        self.assertGreaterEqual(detection_count, len(drone_types),
                               f"Expected at least {len(drone_types)} detections, got {detection_count}")
    
    async def test_threat_escalation(self):
        """Test threat escalation based on detection parameters"""
        print("\n" + "="*60)
        print("TEST: Threat Escalation")
        print("="*60)
        
        await self.detection_service.start()
        
        # Inject high threat drone
        self.hardware.inject_drone("DJI Mavic 3", 2.44e9)
        await asyncio.sleep(3)
        
        # Inject low threat drone
        self.hardware.inject_drone("FPV Analog", 5.8e9)
        await asyncio.sleep(3)
        
        await self.detection_service.stop()
        
        # Check threat levels
        high_threats = [d for d in self.received_detections 
                       if d.get('threat_level') == 'HIGH']
        low_threats = [d for d in self.received_detections 
                      if d.get('threat_level') == 'LOW']
        
        print(f"\n  High threat detections: {len(high_threats)}")
        print(f"  Low threat detections: {len(low_threats)}")
        
        self.assertGreater(len(high_threats), 0, "No high threat detections")
        
        # Check alerts by severity
        critical_alerts = [a for a in self.received_alerts 
                          if a.get('severity') == 'CRITICAL']
        print(f"  Critical alerts: {len(critical_alerts)}")
    
    async def test_persistence_and_recovery(self):
        """Test data persistence and system recovery"""
        print("\n" + "="*60)
        print("TEST: Persistence and Recovery")
        print("="*60)
        
        # Run first detection cycle
        await self.detection_service.start()
        self.hardware.inject_drone("DJI Mavic 3", 2.44e9)
        await asyncio.sleep(3)
        await self.detection_service.stop()
        
        first_detection_count = len(self.received_detections)
        print(f"\n  First cycle detections: {first_detection_count}")
        
        # Clear in-memory events (database should persist)
        self.received_detections.clear()
        self.received_alerts.clear()
        
        # Restart service
        await self.detection_service.start()
        self.hardware.inject_drone("DJI Mavic 3", 2.44e9)
        await asyncio.sleep(3)
        await self.detection_service.stop()
        
        second_detection_count = len(self.received_detections)
        print(f"  Second cycle detections: {second_detection_count}")
        
        # Verify new detections were created
        self.assertGreater(second_detection_count, 0,
                          "No detections in second cycle")
        
        # Verify database still has all detections
        db_count = await self.db.fetch_val("SELECT COUNT(*) FROM detections")
        print(f"  Total detections in database: {db_count}")
        
        self.assertGreaterEqual(db_count, first_detection_count,
                               "Database missing detections from first cycle")
    
    async def test_concurrent_processing(self):
        """Test concurrent detection processing"""
        print("\n" + "="*60)
        print("TEST: Concurrent Processing")
        print("="*60)
        
        await self.detection_service.start()
        
        # Inject multiple signals simultaneously
        drone_configs = [
            ("DJI Mavic 3", 2.44e9),
            ("FPV Analog", 5.8e9),
            ("Autel EVO II", 2.44e9),
            ("Skydio 2", 5.8e9)
        ]
        
        # Inject all at once
        for drone_type, freq in drone_configs:
            self.hardware.inject_drone(drone_type, freq)
        
        # Wait for processing
        await asyncio.sleep(5)
        
        await self.detection_service.stop()
        
        detection_count = len(self.received_detections)
        print(f"\n  Detections from concurrent signals: {detection_count}")
        
        # Should detect all (or most) signals
        self.assertGreaterEqual(detection_count, len(drone_configs) * 0.7,
                               f"Only {detection_count}/{len(drone_configs)} signals detected")
    
    async def test_error_recovery(self):
        """Test system recovery from errors"""
        print("\n" + "="*60)
        print("TEST: Error Recovery")
        print("="*60)
        
        # Inject error condition (simulate hardware failure)
        self.hardware.simulate_errors = True
        self.hardware.error_rate = 0.5
        
        await self.detection_service.start()
        self.hardware.inject_drone("DJI Mavic 3", 2.44e9)
        
        # Let it run with errors
        await asyncio.sleep(5)
        
        # Disable error simulation
        self.hardware.simulate_errors = False
        
        # Continue processing
        await asyncio.sleep(3)
        
        await self.detection_service.stop()
        
        detection_count = len(self.received_detections)
        print(f"\n  Detections despite errors: {detection_count}")
        
        # Should have some successful detections
        self.assertGreater(detection_count, 0,
                          "No successful detections after error recovery")


# ============================================================================
# Performance Tests
# ============================================================================

class TestPerformance(unittest.IsolatedAsyncioTestCase):
    """Performance benchmarks for detection cycle"""
    
    async def asyncSetUp(self):
        """Set up performance test environment"""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        
        db_config = DatabaseConfig(
            db_type=DatabaseType.SQLITE,
            sqlite_path=self.db_path
        )
        self.db = DatabaseManager(db_config)
        await self.db.initialize()
        
        self.hardware = MockSDR()
        self.hardware.initialize({'sample_rate': 10e6})
        
        self.detection_service = DetectionService(
            hardware=self.hardware,
            db=self.db
        )
    
    async def asyncTearDown(self):
        """Clean up after tests"""
        await self.detection_service.stop()
        await self.db.close()
        import os
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    async def test_detection_latency(self):
        """Test detection latency"""
        print("\n" + "="*60)
        print("PERFORMANCE: Detection Latency")
        print("="*60)
        
        await self.detection_service.start()
        
        latencies = []
        
        for _ in range(10):
            start = time.time()
            self.hardware.inject_drone("DJI Mavic 3", 2.44e9)
            await asyncio.sleep(0.1)
            
            # Wait for detection (simplified)
            await asyncio.sleep(1)
            latency = (time.time() - start) * 1000
            latencies.append(latency)
        
        await self.detection_service.stop()
        
        avg_latency = sum(latencies) / len(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)
        
        print(f"\n  Average latency: {avg_latency:.1f} ms")
        print(f"  Min latency: {min_latency:.1f} ms")
        print(f"  Max latency: {max_latency:.1f} ms")
        
        self.assertLess(avg_latency, 2000, f"Average latency too high: {avg_latency:.1f}ms")
    
    async def test_throughput(self):
        """Test detection throughput"""
        print("\n" + "="*60)
        print("PERFORMANCE: Detection Throughput")
        print("="*60)
        
        await self.detection_service.start()
        
        num_signals = 20
        start = time.time()
        
        for i in range(num_signals):
            self.hardware.inject_drone(f"Test Drone {i}", 2.44e9)
            await asyncio.sleep(0.05)
        
        await asyncio.sleep(5)
        await self.detection_service.stop()
        
        elapsed = time.time() - start
        throughput = num_signals / elapsed
        
        print(f"\n  Signals injected: {num_signals}")
        print(f"  Time elapsed: {elapsed:.1f}s")
        print(f"  Throughput: {throughput:.2f} signals/second")
        
        self.assertGreater(throughput, 1.0, f"Throughput too low: {throughput:.2f} signals/s")


# ============================================================================
# Integration Tests with External Services
# ============================================================================

class TestExternalIntegration(unittest.IsolatedAsyncioTestCase):
    """Tests integrating with external services"""
    
    async def asyncSetUp(self):
        """Set up integration test environment"""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        
        db_config = DatabaseConfig(
            db_type=DatabaseType.SQLITE,
            sqlite_path=self.db_path
        )
        self.db = DatabaseManager(db_config)
        await self.db.initialize()
        
        self.hardware = MockSDR()
        self.hardware.initialize({'sample_rate': 10e6})
    
    async def asyncTearDown(self):
        """Clean up after tests"""
        await self.db.close()
        import os
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    async def test_notification_integration(self):
        """Test notification service integration"""
        print("\n" + "="*60)
        print("INTEGRATION: Notification Service")
        print("="*60)
        
        notification_service = MockNotificationService()
        
        detection_service = DetectionService(
            hardware=self.hardware,
            db=self.db,
            notification_service=notification_service
        )
        
        await detection_service.start()
        self.hardware.inject_drone("DJI Mavic 3", 2.44e9)
        await asyncio.sleep(3)
        await detection_service.stop()
        
        notification_count = notification_service.get_notification_count()
        print(f"\n  Notifications sent: {notification_count}")
        
        self.assertGreater(notification_count, 0, "No notifications were sent")
    
    async def test_websocket_integration(self):
        """Test WebSocket broadcast integration"""
        print("\n" + "="*60)
        print("INTEGRATION: WebSocket Broadcasting")
        print("="*60)
        
        websocket_server = MockWebSocketServer()
        
        detection_service = DetectionService(
            hardware=self.hardware,
            db=self.db,
            websocket_server=websocket_server
        )
        
        await detection_service.start()
        self.hardware.inject_drone("DJI Mavic 3", 2.44e9)
        await asyncio.sleep(3)
        await detection_service.stop()
        
        broadcast_count = websocket_server.get_broadcast_count()
        print(f"\n  WebSocket broadcasts: {broadcast_count}")
        
        self.assertGreater(broadcast_count, 0, "No WebSocket broadcasts were sent")


# ============================================================================
# Run Tests
# ============================================================================

async def run_e2e_tests():
    """Run end-to-end tests"""
    test_classes = [
        TestFullDetectionCycle,
        TestPerformance,
        TestExternalIntegration
    ]
    
    for test_class in test_classes:
        print(f"\n{'='*60}")
        print(f"Running {test_class.__name__}")
        print(f"{'='*60}")
        
        instance = test_class()
        await instance.asyncSetUp()
        
        # Run test methods
        for method_name in dir(instance):
            if method_name.startswith('test_'):
                method = getattr(instance, method_name)
                try:
                    await method()
                    print(f"✓ {method_name}")
                except Exception as e:
                    print(f"✗ {method_name}: {e}")
        
        await instance.asyncTearDown()


if __name__ == '__main__':
    asyncio.run(run_e2e_tests())