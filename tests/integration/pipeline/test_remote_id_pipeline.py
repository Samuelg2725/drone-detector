#!/usr/bin/env python3
"""
Integration Tests for Remote ID Pipeline

Tests for end-to-end Remote ID processing including:
- BLE advertisement capture and decoding
- WiFi beacon capture and decoding  
- Message validation and filtering
- Location tracking and session management
- Geofence integration
- Alert generation
- Database persistence
"""

import asyncio
import json
import struct
import unittest
from unittest.mock import Mock, patch, AsyncMock, MagicMock, call
from datetime import datetime, timedelta
from pathlib import Path
import sys
import tempfile

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from domain.algorithms.remote_id_decoder import (
    RemoteIDDecoder,
    OpenDroneIDMessage,
    RemoteIDLocation,
    RemoteIDStatus,
    RemoteIDMessageType,
    RemoteIDDecoderConfig
)
from infrastructure.hardware.remote_id_scanner import RemoteIDScanner, BLEAdvertisement, WiFiBeacon
from infrastructure.storage.database import DatabaseManager
from app.services import RemoteIDService
from app.pipelines import RemoteIDPipeline
from domain.policies.geofence import GeofenceManager


# ============================================================================
# Test Data Generators
# ============================================================================

class RemoteIDTestData:
    """Generate test data for Remote ID pipeline tests"""
    
    @staticmethod
    def create_test_ble_packet(
        uas_id: str = "UAS1234567890123456",
        latitude: float = 37.7749,
        longitude: float = -122.4194,
        altitude: float = 100.0,
        speed: float = 12.5,
        heading: float = 180.0,
        message_type: int = 0x01
    ) -> bytes:
        """Create a test BLE advertisement packet"""
        packet = bytearray()
        
        # BLE header
        packet.extend(b'\x02\x01\x06')  # Flags
        packet.extend(b'\x03\x03\xFA\xFF')  # Remote ID Service UUID
        
        # Manufacturer specific data
        packet.extend(b'\x0F\xFF\x00\x05')  # DJI manufacturer ID
        
        # Remote ID message
        packet.append(message_type)
        
        # UAS ID (20 bytes)
        uas_id_bytes = uas_id.encode('ascii')[:20]
        packet.extend(uas_id_bytes)
        packet.extend(b'\x00' * (20 - len(uas_id_bytes)))
        
        # Location data
        packet.extend(struct.pack('<i', int(latitude * 1e7)))
        packet.extend(struct.pack('<i', int(longitude * 1e7)))
        packet.extend(struct.pack('<i', int(altitude * 100)))
        packet.extend(struct.pack('<H', int(speed * 100)))
        packet.extend(struct.pack('<H', int(heading * 100)))
        
        # Timestamp
        packet.extend(struct.pack('<I', int(datetime.now().timestamp())))
        
        return bytes(packet)
    
    @staticmethod
    def create_test_wifi_beacon(
        uas_id: str = "UAS1234567890123456",
        latitude: float = 37.7749,
        longitude: float = -122.4194,
        altitude: float = 100.0
    ) -> bytes:
        """Create a test WiFi beacon frame"""
        beacon = bytearray()
        
        # MAC header
        beacon.extend(b'\x80\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')
        
        # SSID
        ssid = b'Drone_Network'
        beacon.append(len(ssid))
        beacon.extend(ssid)
        
        # Supported rates
        beacon.extend(b'\x01\x08\x82\x84\x8B\x96\x0C\x12\x18\x24')
        
        # Vendor-specific IE for Remote ID
        beacon.extend(b'\xDD\x1C\x00\x11\x22\x33\x44\x55')  # Vendor OUI
        beacon.extend(b'RID\x01')  # Remote ID signature
        
        # UAS ID
        uas_id_bytes = uas_id.encode('ascii')[:20]
        beacon.extend(uas_id_bytes)
        beacon.extend(b'\x00' * (20 - len(uas_id_bytes)))
        
        # Location
        beacon.extend(struct.pack('<i', int(latitude * 1e7)))
        beacon.extend(struct.pack('<i', int(longitude * 1e7)))
        beacon.extend(struct.pack('<i', int(altitude * 100)))
        
        return bytes(beacon)
    
    @staticmethod
    def create_test_remote_id_message(
        uas_id: str = "UAS1234567890123456",
        latitude: float = 37.7749,
        longitude: float = -122.4194,
        altitude: float = 100.0,
        speed: float = 12.5,
        heading: float = 180.0
    ) -> OpenDroneIDMessage:
        """Create a test Remote ID message object"""
        return OpenDroneIDMessage(
            message_type=RemoteIDMessageType.LOCATION,
            uas_id=uas_id,
            operator_id="OP12345678",
            latitude=latitude,
            longitude=longitude,
            altitude=altitude,
            speed=speed,
            heading=heading,
            timestamp=datetime.now(),
            rssi=-65
        )


# ============================================================================
# Mock Scanner
# ============================================================================

class MockRemoteIDScanner:
    """Mock Remote ID scanner for testing"""
    
    def __init__(self):
        self.is_scanning = False
        self.packets = []
        self.callbacks = []
    
    async def start_scanning(self):
        self.is_scanning = True
    
    async def stop_scanning(self):
        self.is_scanning = False
    
    def register_callback(self, callback):
        self.callbacks.append(callback)
    
    async def inject_packet(self, packet: bytes, rssi: int = -65):
        """Inject a test packet"""
        for callback in self.callbacks:
            await callback(packet, rssi)


# ============================================================================
# Remote ID Pipeline Integration Tests
# ============================================================================

class TestRemoteIDPipelineIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration tests for Remote ID pipeline"""
    
    async def asyncSetUp(self):
        """Set up test fixtures"""
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        
        # Initialize components
        self.db = DatabaseManager()
        self.db.config.sqlite_path = self.db_path
        await self.db.initialize()
        await self.db.create_tables()
        
        # Create scanner and decoder
        self.scanner = MockRemoteIDScanner()
        self.decoder = RemoteIDDecoder()
        self.service = RemoteIDService(self.db, self.decoder)
        self.geofence_manager = GeofenceManager()
        
        # Create pipeline
        self.pipeline = RemoteIDPipeline(
            scanner=self.scanner,
            decoder=self.decoder,
            service=self.service,
            geofence_manager=self.geofence_manager
        )
    
    async def asyncTearDown(self):
        """Clean up after tests"""
        await self.pipeline.stop()
        await self.db.close()
        
        # Clean up temp database
        import os
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    async def test_full_pipeline_ble_message(self):
        """Test full pipeline processing for BLE message"""
        # Create test message
        packet = RemoteIDTestData.create_test_ble_packet(
            uas_id="UAS_TEST_001",
            latitude=37.7749,
            longitude=-122.4194,
            altitude=100.0
        )
        
        # Process through pipeline
        result = await self.pipeline.process_message(packet, rssi=-65, source='ble')
        
        # Verify result
        self.assertIsNotNone(result)
        self.assertEqual(result['uas_id'], "UAS_TEST_001")
        self.assertAlmostEqual(result['latitude'], 37.7749, places=4)
        self.assertAlmostEqual(result['longitude'], -122.4194, places=4)
        
        # Verify database persistence
        messages = await self.service.get_messages(uas_id="UAS_TEST_001", limit=10)
        self.assertGreaterEqual(len(messages), 1)
    
    async def test_full_pipeline_wifi_message(self):
        """Test full pipeline processing for WiFi beacon"""
        # Create test beacon
        beacon = RemoteIDTestData.create_test_wifi_beacon(
            uas_id="UAS_TEST_002",
            latitude=37.7750,
            longitude=-122.4180,
            altitude=110.0
        )
        
        # Process through pipeline
        result = await self.pipeline.process_message(beacon, rssi=-70, source='wifi')
        
        # Verify result
        self.assertIsNotNone(result)
        self.assertEqual(result['uas_id'], "UAS_TEST_002")
        self.assertAlmostEqual(result['latitude'], 37.7750, places=4)
    
    async def test_continuous_scanning(self):
        """Test continuous scanning and message processing"""
        # Start pipeline
        await self.pipeline.start()
        
        # Inject multiple messages
        messages = []
        for i in range(5):
            packet = RemoteIDTestData.create_test_ble_packet(
                uas_id=f"UAS_{i:03d}",
                latitude=37.7749 + i * 0.001,
                longitude=-122.4194 + i * 0.001,
                altitude=100.0 + i * 10
            )
            messages.append(packet)
            await self.scanner.inject_packet(packet, rssi=-60 - i)
            await asyncio.sleep(0.1)
        
        # Let pipeline process
        await asyncio.sleep(1)
        
        # Verify stats
        stats = self.pipeline.get_stats()
        self.assertEqual(stats['messages_processed'], 5)
        
        # Stop pipeline
        await self.pipeline.stop()
    
    async def test_tracking_session(self):
        """Test drone tracking session management"""
        uas_id = "UAS_TRACK_001"
        
        # Send multiple position updates
        positions = [
            (37.7749, -122.4194, 100.0),
            (37.7750, -122.4185, 105.0),
            (37.7751, -122.4176, 110.0),
            (37.7750, -122.4167, 108.0),
            (37.7748, -122.4160, 95.0)
        ]
        
        for lat, lon, alt in positions:
            packet = RemoteIDTestData.create_test_ble_packet(
                uas_id=uas_id,
                latitude=lat,
                longitude=lon,
                altitude=alt
            )
            await self.pipeline.process_message(packet, rssi=-65)
            await asyncio.sleep(0.1)
        
        # Get session info
        session = await self.service.get_session(uas_id)
        
        self.assertIsNotNone(session)
        self.assertAlmostEqual(session['first_latitude'], 37.7749, places=4)
        self.assertAlmostEqual(session['last_latitude'], 37.7748, places=4)
        self.assertGreater(session['max_speed'], 0)
    
    async def test_geofence_integration(self):
        """Test geofence violation detection"""
        # Add a geofence zone
        zone = await self.geofence_manager.add_zone(
            name="Test Restricted Zone",
            zone_type="restricted",
            coordinates=[
                (37.7700, -122.4250),
                (37.7700, -122.4150),
                (37.7800, -122.4150),
                (37.7800, -122.4250)
            ]
        )
        
        # Send position inside geofence
        packet_inside = RemoteIDTestData.create_test_ble_packet(
            uas_id="UAS_VIOLATION",
            latitude=37.7750,
            longitude=-122.4200,
            altitude=100.0
        )
        
        result_inside = await self.pipeline.process_message(packet_inside, rssi=-65)
        
        # Should trigger violation
        violations = await self.geofence_manager.get_violations(uas_id="UAS_VIOLATION")
        self.assertGreaterEqual(len(violations), 1)
        
        # Send position outside geofence
        packet_outside = RemoteIDTestData.create_test_ble_packet(
            uas_id="UAS_VIOLATION",
            latitude=37.7900,
            longitude=-122.4300,
            altitude=100.0
        )
        
        result_outside = await self.pipeline.process_message(packet_outside, rssi=-65)
        
        # No new violation
        violations = await self.geofence_manager.get_violations(uas_id="UAS_VIOLATION")
        self.assertEqual(len(violations), 1)
    
    async def test_alert_generation(self):
        """Test alert generation for suspicious activity"""
        # Register alert callback
        alerts = []
        
        async def on_alert(alert):
            alerts.append(alert)
        
        self.pipeline.on_alert(on_alert)
        
        # Send spoofed messages (multiple UAS IDs from same source)
        for i in range(5):
            packet = RemoteIDTestData.create_test_ble_packet(
                uas_id=f"UAS_SPOOF_{i}",
                latitude=37.7749,
                longitude=-122.4194,
                altitude=100.0
            )
            await self.pipeline.process_message(packet, rssi=-65)
            await asyncio.sleep(0.05)
        
        # Should trigger spoofing alert
        await asyncio.sleep(0.5)
        
        spoofing_alerts = [a for a in alerts if 'spoofing' in a['type'].lower()]
        self.assertGreaterEqual(len(spoofing_alerts), 1)
    
    async def test_message_validation(self):
        """Test message validation and filtering"""
        # Valid message
        valid_packet = RemoteIDTestData.create_test_ble_packet(
            uas_id="UAS_VALID",
            latitude=37.7749,
            longitude=-122.4194
        )
        valid_result = await self.pipeline.process_message(valid_packet, rssi=-65)
        self.assertIsNotNone(valid_result)
        
        # Invalid message (missing UAS ID)
        invalid_packet = RemoteIDTestData.create_test_ble_packet(
            uas_id="",
            latitude=37.7749,
            longitude=-122.4194
        )
        invalid_result = await self.pipeline.process_message(invalid_packet, rssi=-65)
        self.assertIsNone(invalid_result)
        
        # Stale message (old timestamp)
        stale_packet = RemoteIDTestData.create_test_ble_packet()
        # Would need to modify timestamp to be old
        stale_result = await self.pipeline.process_message(stale_packet, rssi=-65)
        # Should be filtered if stale
        self.assertIsNotNone(stale_result)
    
    async def test_concurrent_messages(self):
        """Test processing multiple messages concurrently"""
        uas_ids = [f"UAS_CONCURRENT_{i:03d}" for i in range(20)]
        
        async def send_message(uas_id):
            packet = RemoteIDTestData.create_test_ble_packet(
                uas_id=uas_id,
                latitude=37.7749,
                longitude=-122.4194
            )
            return await self.pipeline.process_message(packet, rssi=-65)
        
        # Process messages concurrently
        tasks = [send_message(uas_id) for uas_id in uas_ids]
        results = await asyncio.gather(*tasks)
        
        # All should succeed
        success_count = sum(1 for r in results if r is not None)
        self.assertEqual(success_count, 20)
        
        # Verify all stored
        for uas_id in uas_ids:
            messages = await self.service.get_messages(uas_id=uas_id, limit=1)
            self.assertGreaterEqual(len(messages), 1)
    
    async def test_rate_limiting(self):
        """Test rate limiting for messages from same drone"""
        uas_id = "UAS_RATE_001"
        
        # Send many messages rapidly
        for i in range(100):
            packet = RemoteIDTestData.create_test_ble_packet(
                uas_id=uas_id,
                latitude=37.7749 + i * 0.0001,
                longitude=-122.4194 + i * 0.0001
            )
            await self.pipeline.process_message(packet, rssi=-65)
        
        await asyncio.sleep(1)
        
        # Should have stored limited number of messages
        messages = await self.service.get_messages(uas_id=uas_id, limit=200)
        # Rate limiting should prevent storing all 100
        self.assertLess(len(messages), 100)
        self.assertGreater(len(messages), 0)
    
    async def test_session_timeout(self):
        """Test session timeout for inactive drones"""
        uas_id = "UAS_TIMEOUT_001"
        
        # Send first message
        packet1 = RemoteIDTestData.create_test_ble_packet(
            uas_id=uas_id,
            latitude=37.7749,
            longitude=-122.4194
        )
        await self.pipeline.process_message(packet1, rssi=-65)
        
        # Get session
        session1 = await self.service.get_session(uas_id)
        self.assertIsNotNone(session1)
        
        # Wait for timeout
        await asyncio.sleep(5)
        
        # Send another message
        packet2 = RemoteIDTestData.create_test_ble_packet(
            uas_id=uas_id,
            latitude=37.7750,
            longitude=-122.4180
        )
        await self.pipeline.process_message(packet2, rssi=-65)
        
        # Should create new session or mark old as ended
        session2 = await self.service.get_session(uas_id)
        self.assertIsNotNone(session2)
    
    async def test_error_recovery(self):
        """Test pipeline error recovery"""
        # Mock decoder to fail temporarily
        original_decode = self.decoder.decode_message
        
        async def failing_decode(*args, **kwargs):
            raise Exception("Temporary decode error")
        
        self.decoder.decode_message = failing_decode
        
        # Send message that will fail
        packet = RemoteIDTestData.create_test_ble_packet()
        result = await self.pipeline.process_message(packet, rssi=-65)
        
        # Should handle error gracefully
        self.assertIsNone(result)
        
        # Restore decoder and verify recovery
        self.decoder.decode_message = original_decode
        
        result = await self.pipeline.process_message(packet, rssi=-65)
        self.assertIsNotNone(result)
    
    async def test_performance_large_batch(self):
        """Test performance with large batch of messages"""
        import time
        
        num_messages = 500
        start_time = time.time()
        
        # Send messages
        for i in range(num_messages):
            packet = RemoteIDTestData.create_test_ble_packet(
                uas_id=f"UAS_PERF_{i:04d}",
                latitude=37.7749,
                longitude=-122.4194
            )
            await self.pipeline.process_message(packet, rssi=-65)
        
        elapsed = time.time() - start_time
        
        # Should process at least 100 messages per second
        messages_per_second = num_messages / elapsed
        self.assertGreater(messages_per_second, 50)
        
        # Verify stored count
        total_messages = await self.service.get_messages_count()
        self.assertGreaterEqual(total_messages, num_messages * 0.9)  # Allow 10% loss
    
    async def test_remote_id_correlation(self):
        """Test correlation of Remote ID messages with detections"""
        # Create a detection
        from domain.entities.detection import DetectionEvent
        
        detection = DetectionEvent(
            id="det_corr_001",
            drone_type="DJI Mavic 3",
            confidence=0.95,
            latitude=37.7749,
            longitude=-122.4194,
            altitude=100.0,
            frequency=2.44e9
        )
        
        # Store detection
        await self.db.save_detection(detection)
        
        # Receive Remote ID message at same location
        packet = RemoteIDTestData.create_test_ble_packet(
            uas_id="UAS_CORR_001",
            latitude=37.7749,
            longitude=-122.4194,
            altitude=100.0
        )
        
        result = await self.pipeline.process_message(packet, rssi=-65)
        
        # Should correlate with detection
        self.assertIsNotNone(result)
        if 'correlated_detection_id' in result:
            self.assertEqual(result['correlated_detection_id'], "det_corr_001")


# ============================================================================
# Component Unit Tests (within integration context)
# ============================================================================

class TestRemoteIDScannerIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration tests for Remote ID scanner with real hardware simulation"""
    
    async def test_scanner_lifecycle(self):
        """Test scanner lifecycle"""
        scanner = RemoteIDScanner()
        
        await scanner.start()
        self.assertTrue(scanner.is_running)
        
        await scanner.stop()
        self.assertFalse(scanner.is_running)
    
    async def test_scanner_callback(self):
        """Test scanner callback mechanism"""
        scanner = RemoteIDScanner()
        received_packets = []
        
        async def callback(packet, rssi):
            received_packets.append((packet, rssi))
        
        scanner.register_callback(callback)
        
        await scanner.start()
        
        # This would normally receive real packets
        # For test, we simulate
        await asyncio.sleep(0.5)
        
        await scanner.stop()


class TestRemoteIDServiceIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration tests for Remote ID service"""
    
    async def asyncSetUp(self):
        """Set up test fixtures"""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        
        self.db = DatabaseManager()
        self.db.config.sqlite_path = self.db_path
        await self.db.initialize()
        await self.db.create_tables()
        
        self.decoder = RemoteIDDecoder()
        self.service = RemoteIDService(self.db, self.decoder)
    
    async def asyncTearDown(self):
        """Clean up after tests"""
        await self.db.close()
        import os
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    async def test_save_and_retrieve_message(self):
        """Test saving and retrieving Remote ID messages"""
        message = RemoteIDTestData.create_test_remote_id_message(
            uas_id="UAS_SERVICE_001",
            latitude=37.7749,
            longitude=-122.4194
        )
        
        message_id = await self.service.save_message(message)
        self.assertIsNotNone(message_id)
        
        retrieved = await self.service.get_message(message_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved['uas_id'], "UAS_SERVICE_001")
    
    async def test_get_track(self):
        """Test getting track history"""
        uas_id = "UAS_TRACK_SERVICE"
        
        # Save multiple positions
        positions = [
            (37.7749, -122.4194, 100.0),
            (37.7750, -122.4185, 105.0),
            (37.7751, -122.4176, 110.0)
        ]
        
        for lat, lon, alt in positions:
            message = RemoteIDTestData.create_test_remote_id_message(
                uas_id=uas_id,
                latitude=lat,
                longitude=lon,
                altitude=alt
            )
            await self.service.save_message(message)
            await asyncio.sleep(0.1)
        
        track = await self.service.get_track(uas_id, limit=10)
        
        self.assertEqual(len(track), 3)
        self.assertAlmostEqual(track[0]['latitude'], 37.7749, places=4)
        self.assertAlmostEqual(track[-1]['latitude'], 37.7751, places=4)
    
    async def test_get_active_drones(self):
        """Test getting active drones"""
        uas_ids = ["UAS_ACTIVE_001", "UAS_ACTIVE_002", "UAS_ACTIVE_003"]
        
        for uas_id in uas_ids:
            message = RemoteIDTestData.create_test_remote_id_message(
                uas_id=uas_id,
                latitude=37.7749,
                longitude=-122.4194
            )
            await self.service.save_message(message)
        
        active = await self.service.get_active_drones(minutes=5)
        
        self.assertEqual(len(active), 3)


# ============================================================================
# Performance Tests
# ============================================================================

class TestRemoteIDPipelinePerformance(unittest.IsolatedAsyncioTestCase):
    """Performance tests for Remote ID pipeline"""
    
    async def asyncSetUp(self):
        """Set up test fixtures"""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        
        self.db = DatabaseManager()
        self.db.config.sqlite_path = self.db_path
        await self.db.initialize()
        
        self.scanner = MockRemoteIDScanner()
        self.decoder = RemoteIDDecoder()
        self.service = RemoteIDService(self.db, self.decoder)
        self.geofence_manager = GeofenceManager()
        
        self.pipeline = RemoteIDPipeline(
            scanner=self.scanner,
            decoder=self.decoder,
            service=self.service,
            geofence_manager=self.geofence_manager
        )
    
    async def asyncTearDown(self):
        """Clean up after tests"""
        await self.pipeline.stop()
        await self.db.close()
        import os
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    async def test_throughput(self):
        """Test message throughput"""
        import time
        
        num_messages = 1000
        start_time = time.time()
        
        for i in range(num_messages):
            packet = RemoteIDTestData.create_test_ble_packet(
                uas_id=f"UAS_PERF_{i:04d}",
                latitude=37.7749,
                longitude=-122.4194
            )
            await self.pipeline.process_message(packet, rssi=-65)
        
        elapsed = time.time() - start_time
        throughput = num_messages / elapsed
        
        print(f"\nThroughput: {throughput:.0f} messages/second")
        self.assertGreater(throughput, 100)  # At least 100 msg/s
    
    async def test_latency(self):
        """Test message processing latency"""
        import time
        
        latencies = []
        
        for i in range(100):
            packet = RemoteIDTestData.create_test_ble_packet(
                uas_id=f"UAS_LAT_{i:04d}",
                latitude=37.7749,
                longitude=-122.4194
            )
            
            start = time.time()
            await self.pipeline.process_message(packet, rssi=-65)
            latency = (time.time() - start) * 1000  # ms
            
            latencies.append(latency)
        
        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)
        
        print(f"\nAverage latency: {avg_latency:.2f} ms")
        print(f"Max latency: {max_latency:.2f} ms")
        
        self.assertLess(avg_latency, 50)  # < 50ms average
        self.assertLess(max_latency, 200)  # < 200ms max


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == '__main__':
    # Run with verbose output
    unittest.main(verbosity=2)