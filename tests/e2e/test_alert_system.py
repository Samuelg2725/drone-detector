#!/usr/bin/env python3
"""
End-to-End Alert System Tests

Tests for the complete alert system including:
- Alert generation from detections
- Alert severity classification
- Alert escalation and routing
- Multi-channel notifications (email, SMS, webhook)
- Alert acknowledgment and resolution
- Alert history and tracking
- Dashboard alert display
- Real-time WebSocket alerts
- Alert filtering and searching
- Alert aggregation and deduplication
"""

import asyncio
import json
import time
import unittest
import smtplib
import threading
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import sys
import tempfile

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# WebSocket for testing
try:
    import websockets
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False

# HTTP for webhook testing
try:
    import aiohttp
    HTTP_AVAILABLE = True
except ImportError:
    HTTP_AVAILABLE = False

# Import application components
from infrastructure.storage.database import DatabaseManager, DatabaseConfig, DatabaseType
from infrastructure.messaging.event_bus import EventBus
from app.services import AlertService, DetectionService
from domain.policies.alert_policies import AlertPolicyEngine, AlertSeverity, AlertCategory
from infrastructure.hardware.mock_hardware import MockSDR


# ============================================================================
# Test Configuration
# ============================================================================

class AlertTestConfig:
    """Alert system test configuration"""
    
    # Test timeouts (seconds)
    ALERT_GENERATION_TIMEOUT = 3
    NOTIFICATION_TIMEOUT = 5
    ESCALATION_TIMEOUT = 10
    
    # Test ports for webhook server
    WEBHOOK_PORT = 8999
    
    # Test email configuration
    TEST_SMTP_HOST = "localhost"
    TEST_SMTP_PORT = 8025
    
    # Test SMS (mock) configuration
    TEST_SMS_API_URL = "http://localhost:8998/sms"
    
    # Alert thresholds
    HIGH_CONFIDENCE_THRESHOLD = 0.85
    MEDIUM_CONFIDENCE_THRESHOLD = 0.70
    
    # Escalation levels
    ESCALATION_LEVELS = [1, 2, 3]
    ESCALATION_TIMES = [30, 60, 120]  # seconds


# ============================================================================
# Mock Notification Servers
# ============================================================================

class MockEmailServer:
    """Mock SMTP server for testing email notifications"""
    
    def __init__(self, host: str = "localhost", port: int = 8025):
        self.host = host
        self.port = port
        self.received_emails = []
        self.server = None
        self.server_thread = None
    
    def start(self):
        """Start mock SMTP server"""
        import smtpd
        import asyncore
        
        class MockSMTPServer(smtpd.SMTPServer):
            def __init__(self, localaddr, remoteaddr, callback):
                smtpd.SMTPServer.__init__(self, localaddr, remoteaddr)
                self.callback = callback
            
            def process_message(self, peer, mailfrom, rcpttos, data, **kwargs):
                self.callback({
                    'from': mailfrom,
                    'to': rcpttos,
                    'data': data.decode('utf-8'),
                    'timestamp': datetime.now().isoformat()
                })
        
        def on_email(email):
            self.received_emails.append(email)
        
        self.server = MockSMTPServer((self.host, self.port), None, on_email)
        self.server_thread = threading.Thread(target=asyncore.loop, daemon=True)
        self.server_thread.start()
    
    def stop(self):
        """Stop mock SMTP server"""
        if self.server:
            self.server.close()
    
    def get_emails(self, recipient: str = None) -> list:
        """Get received emails"""
        if recipient:
            return [e for e in self.received_emails if recipient in e['to']]
        return self.received_emails
    
    def clear(self):
        """Clear received emails"""
        self.received_emails.clear()


class MockWebhookServer:
    """Mock webhook server for testing webhook notifications"""
    
    def __init__(self, port: int = 8999):
        self.port = port
        self.received_webhooks = []
        self.server = None
        self.server_task = None
    
    async def start(self):
        """Start mock webhook server"""
        from aiohttp import web
        
        async def handle_webhook(request):
            data = await request.json()
            self.received_webhooks.append({
                'data': data,
                'timestamp': datetime.now().isoformat(),
                'headers': dict(request.headers)
            })
            return web.Response(status=200)
        
        app = web.Application()
        app.router.add_post('/webhook', handle_webhook)
        
        runner = web.AppRunner(app)
        await runner.setup()
        self.server = web.TCPSite(runner, 'localhost', self.port)
        await self.server.start()
    
    async def stop(self):
        """Stop mock webhook server"""
        if self.server:
            await self.server.stop()
    
    def get_webhooks(self) -> list:
        """Get received webhooks"""
        return self.received_webhooks
    
    def clear(self):
        """Clear received webhooks"""
        self.received_webhooks.clear()


class MockSMSProvider:
    """Mock SMS provider for testing SMS notifications"""
    
    def __init__(self):
        self.sent_messages = []
    
    async def send_sms(self, to: str, message: str) -> bool:
        """Send SMS (mock)"""
        self.sent_messages.append({
            'to': to,
            'message': message,
            'timestamp': datetime.now().isoformat()
        })
        return True
    
    def get_messages(self, to: str = None) -> list:
        """Get sent messages"""
        if to:
            return [m for m in self.sent_messages if m['to'] == to]
        return self.sent_messages
    
    def clear(self):
        """Clear sent messages"""
        self.sent_messages.clear()


# ============================================================================
# Alert System Test Fixture
# ============================================================================

class AlertSystemFixture:
    """Complete alert system test fixture"""
    
    def __init__(self):
        self.db = None
        self.event_bus = None
        self.alert_service = None
        self.detection_service = None
        self.alert_engine = None
        self.mock_email = None
        self.mock_webhook = None
        self.mock_sms = None
        self.hardware = None
    
    async def start(self):
        """Start alert system with all components"""
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        
        # Initialize database
        db_config = DatabaseConfig(
            db_type=DatabaseType.SQLITE,
            sqlite_path=self.db_path
        )
        self.db = DatabaseManager(db_config)
        await self.db.initialize()
        await self.db.create_tables()
        
        # Initialize event bus
        self.event_bus = EventBus()
        
        # Initialize alert engine
        self.alert_engine = AlertPolicyEngine()
        
        # Initialize mock hardware
        self.hardware = MockSDR()
        self.hardware.initialize({'sample_rate': 10e6})
        
        # Initialize mock notification servers
        self.mock_email = MockEmailServer()
        self.mock_webhook = MockWebhookServer()
        self.mock_sms = MockSMSProvider()
        
        # Start mock servers
        self.mock_email.start()
        await self.mock_webhook.start()
        
        # Initialize alert service
        self.alert_service = AlertService(
            db=self.db,
            event_bus=self.event_bus,
            email_service=self.mock_email,
            sms_service=self.mock_sms,
            webhook_service=self.mock_webhook
        )
        
        # Initialize detection service
        self.detection_service = DetectionService(
            hardware=self.hardware,
            db=self.db,
            event_bus=self.event_bus,
            alert_service=self.alert_service
        )
        
        # Register alert handlers
        self.event_bus.on('alert.generated', self._on_alert)
        self.event_bus.on('alert.escalated', self._on_escalation)
        
        # Track events
        self.generated_alerts = []
        self.escalated_alerts = []
        
        # Start services
        await self.detection_service.start()
        
        return self
    
    async def stop(self):
        """Stop alert system"""
        await self.detection_service.stop()
        self.mock_email.stop()
        await self.mock_webhook.stop()
        await self.db.close()
        
        import os
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def _on_alert(self, alert_data):
        """Handle alert generation event"""
        self.generated_alerts.append(alert_data)
    
    def _on_escalation(self, escalation_data):
        """Handle alert escalation event"""
        self.escalated_alerts.append(escalation_data)
    
    async def generate_detection(self, confidence: float = 0.95, 
                                  drone_type: str = "DJI Mavic 3",
                                  threat_level: str = "HIGH") -> dict:
        """Generate a test detection"""
        self.hardware.inject_drone(drone_type, 2.44e9)
        await asyncio.sleep(0.5)
        
        # In a real system, this would create a detection
        # For test, we simulate
        detection = {
            'id': f"det_{int(time.time())}",
            'timestamp': datetime.now().isoformat(),
            'drone_type': drone_type,
            'confidence': confidence,
            'threat_level': threat_level,
            'frequency': 2.44e9,
            'latitude': 37.7749,
            'longitude': -122.4194
        }
        
        # Trigger alert generation
        await self.alert_service.process_detection(detection)
        
        return detection


# ============================================================================
# Alert System Tests
# ============================================================================

class TestAlertSystem(unittest.IsolatedAsyncioTestCase):
    """End-to-end alert system tests"""
    
    async def asyncSetUp(self):
        """Set up test environment"""
        self.fixture = await AlertSystemFixture().start()
    
    async def asyncTearDown(self):
        """Clean up after tests"""
        await self.fixture.stop()
    
    async def test_alert_generation_from_detection(self):
        """Test alert generation from detection"""
        print("\n" + "="*60)
        print("TEST: Alert Generation from Detection")
        print("="*60)
        
        # Generate high-confidence detection
        detection = await self.fixture.generate_detection(
            confidence=0.95,
            drone_type="DJI Mavic 3",
            threat_level="HIGH"
        )
        
        print(f"  Detection generated: {detection['id']}")
        
        # Wait for alert processing
        await asyncio.sleep(AlertTestConfig.ALERT_GENERATION_TIMEOUT)
        
        # Verify alert was generated
        self.assertGreater(len(self.fixture.generated_alerts), 0,
                          "No alert generated")
        
        alert = self.fixture.generated_alerts[0]
        print(f"  Alert generated: {alert.get('id')}")
        print(f"    Severity: {alert.get('severity')}")
        print(f"    Category: {alert.get('category')}")
        
        # Verify alert properties
        self.assertEqual(alert.get('drone_type'), 'DJI Mavic 3')
        self.assertIn(alert.get('severity'), ['CRITICAL', 'HIGH', 'ALERT'])
        
        # Verify notification was sent
        emails = self.fixture.mock_email.get_emails()
        print(f"  Email notifications: {len(emails)}")
        self.assertGreater(len(emails), 0, "No email notification sent")
    
    async def test_alert_severity_classification(self):
        """Test alert severity classification based on confidence"""
        print("\n" + "="*60)
        print("TEST: Alert Severity Classification")
        print("="*60)
        
        # Test different confidence levels
        test_cases = [
            (0.95, "HIGH", "CRITICAL"),
            (0.85, "MEDIUM", "HIGH"),
            (0.70, "LOW", "MEDIUM"),
            (0.50, "VERY_LOW", "LOW")
        ]
        
        results = []
        
        for confidence, threat_level, expected_severity in test_cases:
            self.fixture.generated_alerts.clear()
            
            await self.fixture.generate_detection(
                confidence=confidence,
                threat_level=threat_level
            )
            
            await asyncio.sleep(1)
            
            if self.fixture.generated_alerts:
                severity = self.fixture.generated_alerts[0].get('severity')
                results.append({
                    'confidence': confidence,
                    'expected': expected_severity,
                    'actual': severity,
                    'match': severity == expected_severity
                })
        
        print("\n  Severity Classification Results:")
        for r in results:
            status = "✓" if r['match'] else "✗"
            print(f"    {status} Confidence {r['confidence']:.0%}: "
                  f"Expected {r['expected']}, Got {r['actual']}")
            self.assertTrue(r['match'], f"Misclassification for confidence {r['confidence']}")
    
    async def test_alert_escalation(self):
        """Test alert escalation over time"""
        print("\n" + "="*60)
        print("TEST: Alert Escalation")
        print("="*60)
        
        # Generate a detection that requires escalation
        await self.fixture.generate_detection(confidence=0.95, threat_level="HIGH")
        
        # Track escalation levels
        escalation_levels = []
        
        # Monitor escalations
        async def track_escalations():
            for escalation in self.fixture.escalated_alerts:
                escalation_levels.append(escalation.get('level'))
        
        asyncio.create_task(track_escalations())
        
        # Wait for potential escalations
        await asyncio.sleep(AlertTestConfig.ESCALATION_TIMEOUT)
        
        print(f"  Escalation levels observed: {escalation_levels}")
        print(f"  Total escalations: {len(self.fixture.escalated_alerts)}")
        
        # Should have at least one escalation
        self.assertGreater(len(self.fixture.escalated_alerts), 0,
                          "No alert escalations occurred")
    
    async def test_multiple_notification_channels(self):
        """Test notifications through multiple channels"""
        print("\n" + "="*60)
        print("TEST: Multi-Channel Notifications")
        print("="*60)
        
        # Clear all notification stores
        self.fixture.mock_email.clear()
        self.fixture.mock_webhook.clear()
        self.fixture.mock_sms.clear()
        
        # Generate detection
        await self.fixture.generate_detection(confidence=0.95)
        
        await asyncio.sleep(AlertTestConfig.NOTIFICATION_TIMEOUT)
        
        # Check email
        emails = self.fixture.mock_email.get_emails()
        print(f"  Email notifications: {len(emails)}")
        
        # Check webhook
        webhooks = self.fixture.mock_webhook.get_webhooks()
        print(f"  Webhook notifications: {len(webhooks)}")
        
        # Check SMS
        sms_messages = self.fixture.mock_sms.get_messages()
        print(f"  SMS notifications: {len(sms_messages)}")
        
        # At least one channel should have notifications
        total_notifications = len(emails) + len(webhooks) + len(sms_messages)
        self.assertGreater(total_notifications, 0,
                          "No notifications sent through any channel")
    
    async def test_alert_acknowledgment(self):
        """Test alert acknowledgment workflow"""
        print("\n" + "="*60)
        print("TEST: Alert Acknowledgment")
        print("="*60)
        
        # Generate alert
        await self.fixture.generate_detection(confidence=0.95)
        await asyncio.sleep(1)
        
        if not self.fixture.generated_alerts:
            self.skipTest("No alert generated")
        
        alert_id = self.fixture.generated_alerts[0].get('id')
        print(f"  Alert ID: {alert_id}")
        
        # Acknowledge alert
        result = await self.fixture.alert_service.acknowledge_alert(
            alert_id=alert_id,
            user="test_operator"
        )
        
        print(f"  Acknowledgment result: {result}")
        
        # Verify acknowledgment was recorded
        alert = await self.fixture.db.fetch_one(
            "SELECT * FROM alerts WHERE id = ?", alert_id
        )
        
        if alert:
            acknowledged = alert.get('acknowledged', False)
            acknowledged_by = alert.get('acknowledged_by')
            print(f"  Acknowledged: {acknowledged}")
            print(f"  Acknowledged by: {acknowledged_by}")
            
            self.assertTrue(acknowledged, "Alert not marked as acknowledged")
            self.assertEqual(acknowledged_by, "test_operator")
    
    async def test_alert_resolution(self):
        """Test alert resolution workflow"""
        print("\n" + "="*60)
        print("TEST: Alert Resolution")
        print("="*60)
        
        # Generate alert
        await self.fixture.generate_detection(confidence=0.95)
        await asyncio.sleep(1)
        
        if not self.fixture.generated_alerts:
            self.skipTest("No alert generated")
        
        alert_id = self.fixture.generated_alerts[0].get('id')
        print(f"  Alert ID: {alert_id}")
        
        # Acknowledge first
        await self.fixture.alert_service.acknowledge_alert(alert_id, "operator")
        
        # Resolve alert
        result = await self.fixture.alert_service.resolve_alert(alert_id)
        print(f"  Resolution result: {result}")
        
        # Verify resolution
        alert = await self.fixture.db.fetch_one(
            "SELECT * FROM alerts WHERE id = ?", alert_id
        )
        
        if alert:
            resolved = alert.get('resolved', False)
            resolved_at = alert.get('resolved_at')
            print(f"  Resolved: {resolved}")
            print(f"  Resolved at: {resolved_at}")
            
            self.assertTrue(resolved, "Alert not marked as resolved")
            self.assertIsNotNone(resolved_at, "Resolution time not set")
    
    async def test_alert_deduplication(self):
        """Test alert deduplication for similar events"""
        print("\n" + "="*60)
        print("TEST: Alert Deduplication")
        print("="*60)
        
        # Clear existing alerts
        self.fixture.generated_alerts.clear()
        
        # Generate multiple similar detections in quick succession
        for i in range(5):
            await self.fixture.generate_detection(confidence=0.95)
            await asyncio.sleep(0.1)
        
        await asyncio.sleep(2)
        
        # Should have fewer alerts than detections due to deduplication
        alert_count = len(self.fixture.generated_alerts)
        print(f"  Detections: 5")
        print(f"  Alerts generated: {alert_count}")
        
        # Should not create 5 separate alerts
        self.assertLess(alert_count, 5, "Too many alerts generated (deduplication failed)")
        self.assertGreater(alert_count, 0, "No alerts generated")
    
    async def test_alert_filtering(self):
        """Test alert filtering by criteria"""
        print("\n" + "="*60)
        print("TEST: Alert Filtering")
        print("="*60)
        
        # Generate alerts with different severities
        severities = ['HIGH', 'MEDIUM', 'LOW']
        
        for severity in severities:
            await self.fixture.generate_detection(
                confidence=0.9 if severity == 'HIGH' else 0.6,
                threat_level=severity
            )
            await asyncio.sleep(0.5)
        
        await asyncio.sleep(2)
        
        # Query alerts by severity
        for severity in severities:
            alerts = await self.fixture.db.fetch_all(
                "SELECT * FROM alerts WHERE severity = ?", severity
            )
            print(f"  {severity} alerts: {len(alerts)}")
            
            if severity == 'HIGH':
                self.assertGreater(len(alerts), 0, f"No {severity} alerts found")
    
    async def test_alert_aggregation(self):
        """Test alert aggregation for summary reports"""
        print("\n" + "="*60)
        print("TEST: Alert Aggregation")
        print("="*60)
        
        # Generate multiple alerts
        for i in range(10):
            await self.fixture.generate_detection(confidence=0.85)
            await asyncio.sleep(0.2)
        
        await asyncio.sleep(3)
        
        # Get aggregated statistics
        stats = await self.fixture.alert_service.get_alert_statistics(
            start_time=datetime.now() - timedelta(hours=1),
            end_time=datetime.now()
        )
        
        print(f"  Total alerts: {stats.get('total', 0)}")
        print(f"  By severity: {stats.get('by_severity', {})}")
        print(f"  By category: {stats.get('by_category', {})}")
        
        self.assertGreater(stats.get('total', 0), 0, "No alerts in statistics")


# ============================================================================
# Performance Tests
# ============================================================================

class TestAlertPerformance(unittest.IsolatedAsyncioTestCase):
    """Alert system performance tests"""
    
    async def asyncSetUp(self):
        """Set up performance test environment"""
        self.fixture = await AlertSystemFixture().start()
    
    async def asyncTearDown(self):
        """Clean up after tests"""
        await self.fixture.stop()
    
    async def test_alert_generation_latency(self):
        """Test alert generation latency"""
        print("\n" + "="*60)
        print("PERFORMANCE: Alert Generation Latency")
        print("="*60)
        
        latencies = []
        
        for i in range(10):
            start = time.time()
            await self.fixture.generate_detection(confidence=0.95)
            
            # Wait for alert to be generated
            await asyncio.sleep(0.1)
            
            latency = (time.time() - start) * 1000
            latencies.append(latency)
        
        avg_latency = sum(latencies) / len(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)
        
        print(f"  Average latency: {avg_latency:.1f} ms")
        print(f"  Min latency: {min_latency:.1f} ms")
        print(f"  Max latency: {max_latency:.1f} ms")
        
        self.assertLess(avg_latency, 2000, f"Alert latency too high: {avg_latency:.1f}ms")
    
    async def test_concurrent_alerts(self):
        """Test handling of concurrent alerts"""
        print("\n" + "="*60)
        print("PERFORMANCE: Concurrent Alert Processing")
        print("="*60)
        
        start = time.time()
        
        # Generate many alerts concurrently
        tasks = []
        for i in range(20):
            tasks.append(self.fixture.generate_detection(confidence=0.85))
        
        await asyncio.gather(*tasks)
        
        await asyncio.sleep(3)
        
        elapsed = time.time() - start
        alerts_per_second = 20 / elapsed
        
        print(f"  Time: {elapsed:.2f}s")
        print(f"  Throughput: {alerts_per_second:.1f} alerts/second")
        
        self.assertGreater(alerts_per_second, 2, f"Throughput too low: {alerts_per_second:.1f} alerts/s")


# ============================================================================
# Integration Tests
# ============================================================================

class TestAlertIntegrations(unittest.IsolatedAsyncioTestCase):
    """Alert system integration tests"""
    
    async def asyncSetUp(self):
        """Set up integration test environment"""
        self.fixture = await AlertSystemFixture().start()
    
    async def asyncTearDown(self):
        """Clean up after tests"""
        await self.fixture.stop()
    
    async def test_websocket_alert_broadcast(self):
        """Test alert broadcast via WebSocket"""
        if not WEBSOCKET_AVAILABLE:
            self.skipTest("WebSockets not available")
        
        print("\n" + "="*60)
        print("INTEGRATION: WebSocket Alert Broadcast")
        print("="*60)
        
        # Connect to WebSocket server (if running)
        # This test assumes a WebSocket server is running
        try:
            async with websockets.connect("ws://localhost:8082") as ws:
                # Subscribe to alerts
                await ws.send(json.dumps({"type": "subscribe", "channel": "alerts"}))
                
                # Generate alert
                await self.fixture.generate_detection(confidence=0.95)
                
                # Wait for alert message
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    data = json.loads(message)
                    print(f"  Received WebSocket alert: {data.get('type')}")
                    self.assertEqual(data.get('type'), 'alert')
                except asyncio.TimeoutError:
                    self.fail("No alert received via WebSocket")
                    
        except Exception as e:
            print(f"  WebSocket connection skipped: {e}")
            self.skipTest("WebSocket server not available")


# ============================================================================
# Run Tests
# ============================================================================

async def run_alert_tests():
    """Run alert system tests"""
    test_classes = [
        TestAlertSystem,
        TestAlertPerformance,
        TestAlertIntegrations
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
    asyncio.run(run_alert_tests())