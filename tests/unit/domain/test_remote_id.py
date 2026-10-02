#!/usr/bin/env python3
"""
Unit Tests for Remote ID Module

Tests for Remote ID message decoding, validation, and processing.
Covers ASTM F3411-22 message formats, BLE/WiFi decoding, and data extraction.
"""

import unittest
import json
import struct
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock, MagicMock

import numpy as np

# Import modules to test
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from domain.algorithms.remote_id_decoder import (
    RemoteIDDecoder,
    OpenDroneIDMessage,
    RemoteIDLocation,
    RemoteIDStatus,
    RemoteIDMessageType,
    RemoteIDDecoderConfig,
    decode_remote_id_packet,
    decode_ble_advertisement,
    decode_wifi_beacon
)


# ============================================================================
# Test Data
# ============================================================================

class RemoteIDTestData:
    """Test data for Remote ID tests"""
    
    @staticmethod
    def create_test_ble_packet(message_type=0x00):
        """Create test BLE advertisement packet"""
        # Simplified BLE packet structure for testing
        # This would be replaced with actual packet structure
        
        packet = bytearray()
        
        # Header
        packet.extend(b'\x02\x01\x06')  # Flags
        packet.extend(b'\x03\x03\xFA\xFF')  # Service UUID (0xFFFA for Remote ID)
        
        # Manufacturer specific data
        packet.extend(b'\x0F\xFF\x00\x05')  # Manufacturer ID (DJI = 0x0005)
        
        # Remote ID message (simplified)
        packet.append(message_type)  # Message type
        packet.extend([0x00] * 24)  # Placeholder for message data
        
        # UAS ID (20 bytes)
        uas_id = b'UAS1234567890123456'
        packet.extend(uas_id[:20])
        
        # Location data
        packet.extend(struct.pack('<i', int(37.7749 * 1e7)))  # Latitude
        packet.extend(struct.pack('<i', int(-122.4194 * 1e7)))  # Longitude
        packet.extend(struct.pack('<i', 10000))  # Altitude (cm)
        
        return bytes(packet)
    
    @staticmethod
    def create_test_wifi_beacon():
        """Create test WiFi beacon frame"""
        # Simplified beacon frame for testing
        beacon = bytearray()
        
        # MAC header (simplified)
        beacon.extend(b'\x80\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')
        
        # Beacon frame body
        beacon.extend(b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09')  # SSID
        
        # Vendor-specific IE for Remote ID
        beacon.extend(b'\xDD\x1C\x00\x11\x22\x33\x44\x55')  # Vendor OUI
        
        # Remote ID data
        beacon.extend(b'RID\x01')  # Remote ID signature
        uas_id = b'UAS1234567890123456'
        beacon.extend(uas_id[:20])
        
        # Location
        beacon.extend(struct.pack('<i', int(37.7749 * 1e7)))
        beacon.extend(struct.pack('<i', int(-122.4194 * 1e7)))
        beacon.extend(struct.pack('<i', 10000))
        
        return bytes(beacon)


# ============================================================================
# Remote ID Decoder Tests
# ============================================================================

class TestRemoteIDDecoder(unittest.TestCase):
    """Test Remote ID decoder functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = RemoteIDDecoderConfig(
            validate_checksum=True,
            max_age_seconds=10,
            required_fields=['uas_id', 'latitude', 'longitude']
        )
        self.decoder = RemoteIDDecoder(config=self.config)
    
    def test_decoder_initialization(self):
        """Test decoder initialization"""
        self.assertIsNotNone(self.decoder)
        self.assertEqual(self.decoder.config.validate_checksum, True)
        self.assertEqual(self.decoder.config.max_age_seconds, 10)
    
    def test_decode_valid_ble_packet(self):
        """Test decoding valid BLE advertisement"""
        packet = RemoteIDTestData.create_test_ble_packet()
        
        result = decode_ble_advertisement(packet)
        
        self.assertIsNotNone(result)
        self.assertIn('uas_id', result)
        self.assertIn('latitude', result)
        self.assertIn('longitude', result)
    
    def test_decode_invalid_ble_packet(self):
        """Test decoding invalid BLE packet"""
        packet = b'\x00\x01\x02\x03'  # Too short
        
        result = decode_ble_advertisement(packet)
        
        self.assertIsNone(result)
    
    def test_decode_valid_wifi_beacon(self):
        """Test decoding valid WiFi beacon"""
        beacon = RemoteIDTestData.create_test_wifi_beacon()
        
        result = decode_wifi_beacon(beacon)
        
        self.assertIsNotNone(result)
        self.assertIn('uas_id', result)
    
    def test_decode_invalid_wifi_beacon(self):
        """Test decoding invalid WiFi beacon"""
        beacon = b'\x00\x01\x02\x03'  # Too short
        
        result = decode_wifi_beacon(beacon)
        
        self.assertIsNone(result)
    
    @patch('domain.algorithms.remote_id_decoder.decode_ble_advertisement')
    async def test_process_ble_message(self, mock_decode):
        """Test processing BLE message"""
        mock_decode.return_value = {
            'uas_id': 'TEST123',
            'latitude': 37.7749,
            'longitude': -122.4194,
            'altitude': 100.0,
            'valid': True
        }
        
        packet = RemoteIDTestData.create_test_ble_packet()
        result = await self.decoder.process_ble_message(packet, rssi=-65)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['uas_id'], 'TEST123')
        self.assertEqual(result['rssi'], -65)
    
    def test_validate_message(self):
        """Test message validation"""
        message = {
            'uas_id': 'TEST123',
            'latitude': 37.7749,
            'longitude': -122.4194,
            'timestamp': datetime.now()
        }
        
        is_valid, errors = self.decoder.validate_message(message)
        
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
    
    def test_validate_message_missing_fields(self):
        """Test validation with missing fields"""
        message = {
            'uas_id': 'TEST123'
        }
        
        is_valid, errors = self.decoder.validate_message(message)
        
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)
    
    def test_validate_message_stale_data(self):
        """Test validation with stale data"""
        message = {
            'uas_id': 'TEST123',
            'latitude': 37.7749,
            'longitude': -122.4194,
            'timestamp': datetime.now() - timedelta(seconds=30)
        }
        
        is_valid, errors = self.decoder.validate_message(message)
        
        self.assertFalse(is_valid)
        self.assertIn('stale', str(errors).lower())
    
    def test_extract_location_data(self):
        """Test location data extraction"""
        message = {
            'latitude': 37.7749,
            'longitude': -122.4194,
            'altitude': 150.5,
            'speed': 12.3,
            'heading': 180.0
        }
        
        location = self.decoder.extract_location(message)
        
        self.assertEqual(location['latitude'], 37.7749)
        self.assertEqual(location['longitude'], -122.4194)
        self.assertEqual(location['altitude'], 150.5)
        self.assertEqual(location['speed'], 12.3)
    
    def test_extract_location_missing_data(self):
        """Test location extraction with missing data"""
        message = {
            'latitude': 37.7749,
            'longitude': -122.4194
        }
        
        location = self.decoder.extract_location(message)
        
        self.assertEqual(location['latitude'], 37.7749)
        self.assertEqual(location['longitude'], -122.4194)
        self.assertEqual(location['altitude'], 0.0)
        self.assertEqual(location['speed'], 0.0)


# ============================================================================
# OpenDroneIDMessage Tests
# ============================================================================

class TestOpenDroneIDMessage(unittest.TestCase):
    """Test OpenDroneIDMessage data class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.test_time = datetime.now()
        self.message = OpenDroneIDMessage(
            message_type=RemoteIDMessageType.BASIC_ID,
            uas_id='UAS12345678',
            operator_id='OP12345678',
            latitude=37.7749,
            longitude=-122.4194,
            altitude=100.0,
            speed=15.5,
            heading=180.0,
            timestamp=self.test_time,
            rssi=-65
        )
    
    def test_message_creation(self):
        """Test message creation"""
        self.assertEqual(self.message.uas_id, 'UAS12345678')
        self.assertEqual(self.message.latitude, 37.7749)
        self.assertEqual(self.message.longitude, -122.4194)
        self.assertEqual(self.message.rssi, -65)
    
    def test_message_is_valid(self):
        """Test message validation"""
        is_valid = self.message.is_valid()
        self.assertTrue(is_valid)
    
    def test_message_age(self):
        """Test message age calculation"""
        age = self.message.age_seconds
        self.assertGreaterEqual(age, 0)
        self.assertLess(age, 1)
    
    def test_message_to_dict(self):
        """Test message to dict conversion"""
        msg_dict = self.message.to_dict()
        
        self.assertEqual(msg_dict['uas_id'], 'UAS12345678')
        self.assertEqual(msg_dict['latitude'], 37.7749)
        self.assertEqual(msg_dict['message_type'], 'basic_id')
    
    def test_create_location_object(self):
        """Test creating location object from message"""
        location = self.message.to_location()
        
        self.assertEqual(location.latitude, 37.7749)
        self.assertEqual(location.longitude, -122.4194)
        self.assertEqual(location.altitude, 100.0)


# ============================================================================
# Remote ID Location Tests
# ============================================================================

class TestRemoteIDLocation(unittest.TestCase):
    """Test Remote ID location data class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.location = RemoteIDLocation(
            latitude=37.7749,
            longitude=-122.4194,
            altitude=100.0,
            accuracy_horizontal=5.0,
            accuracy_vertical=10.0,
            timestamp=datetime.now()
        )
    
    def test_location_creation(self):
        """Test location creation"""
        self.assertEqual(self.location.latitude, 37.7749)
        self.assertEqual(self.location.longitude, -122.4194)
        self.assertEqual(self.location.altitude, 100.0)
    
    def test_distance_to(self):
        """Test distance calculation"""
        other = RemoteIDLocation(
            latitude=37.7750,
            longitude=-122.4180,
            altitude=100.0
        )
        
        distance = self.location.distance_to(other)
        
        # Approximate distance between points
        self.assertGreater(distance, 0)
        self.assertLess(distance, 200)  # Should be less than 200 meters
    
    def test_to_dict(self):
        """Test location to dict conversion"""
        loc_dict = self.location.to_dict()
        
        self.assertEqual(loc_dict['latitude'], 37.7749)
        self.assertEqual(loc_dict['longitude'], -122.4194)
        self.assertEqual(loc_dict['altitude'], 100.0)
    
    def test_point(self):
        """Test getting point coordinates"""
        point = self.location.point
        
        self.assertEqual(point[0], -122.4194)
        self.assertEqual(point[1], 37.7749)
        self.assertEqual(point[2], 100.0)


# ============================================================================
# Remote ID Status Tests
# ============================================================================

class TestRemoteIDStatus(unittest.TestCase):
    """Test Remote ID status enumeration"""
    
    def test_status_values(self):
        """Test status enum values"""
        self.assertEqual(RemoteIDStatus.VALID.value, 'valid')
        self.assertEqual(RemoteIDStatus.INVALID.value, 'invalid')
        self.assertEqual(RemoteIDStatus.STALE.value, 'stale')
        self.assertEqual(RemoteIDStatus.SUSPICIOUS.value, 'suspicious')
    
    def test_status_from_string(self):
        """Test status from string conversion"""
        status = RemoteIDStatus('valid')
        self.assertEqual(status, RemoteIDStatus.VALID)


# ============================================================================
# Integration Tests
# ============================================================================

class TestRemoteIDIntegration(unittest.TestCase):
    """Integration tests for Remote ID components"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.decoder = RemoteIDDecoder()
    
    def test_full_decode_chain(self):
        """Test full decode chain from packet to location"""
        packet = RemoteIDTestData.create_test_ble_packet()
        
        # Decode packet
        decoded = decode_ble_advertisement(packet)
        
        self.assertIsNotNone(decoded)
        self.assertIn('uas_id', decoded)
        
        # Convert to location
        if 'latitude' in decoded and 'longitude' in decoded:
            location = RemoteIDLocation(
                latitude=decoded['latitude'],
                longitude=decoded['longitude'],
                altitude=decoded.get('altitude', 0)
            )
            
            self.assertIsInstance(location, RemoteIDLocation)
    
    def test_multiple_message_types(self):
        """Test decoding different message types"""
        message_types = [0x00, 0x01, 0x02, 0x03, 0x04, 0x05]
        
        for msg_type in message_types:
            packet = RemoteIDTestData.create_test_ble_packet(msg_type)
            decoded = decode_ble_advertisement(packet)
            
            # Should still decode even if message type not fully supported
            self.assertIsNotNone(decoded)


# ============================================================================
# Performance Tests
# ============================================================================

class TestRemoteIDPerformance(unittest.TestCase):
    """Performance tests for Remote ID processing"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.decoder = RemoteIDDecoder()
        self.test_packets = [
            RemoteIDTestData.create_test_ble_packet()
            for _ in range(100)
        ]
    
    def test_batch_decode_performance(self):
        """Test batch decode performance"""
        import time
        
        start_time = time.time()
        
        for packet in self.test_packets:
            result = decode_ble_advertisement(packet)
            self.assertIsNotNone(result)
        
        elapsed = time.time() - start_time
        
        # Should process 100 packets in under 1 second
        self.assertLess(elapsed, 1.0)
    
    @patch('domain.algorithms.remote_id_decoder.decode_ble_advertisement')
    async def test_concurrent_processing(self, mock_decode):
        """Test concurrent message processing"""
        import asyncio
        
        mock_decode.return_value = {'uas_id': 'TEST', 'valid': True}
        
        tasks = [
            self.decoder.process_ble_message(packet)
            for packet in self.test_packets[:10]
        ]
        
        results = await asyncio.gather(*tasks)
        
        self.assertEqual(len(results), 10)
        for result in results:
            self.assertIsNotNone(result)


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================

class TestRemoteIDEdgeCases(unittest.TestCase):
    """Test edge cases and error handling"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.decoder = RemoteIDDecoder()
    
    def test_empty_packet(self):
        """Test decoding empty packet"""
        result = decode_ble_advertisement(b'')
        self.assertIsNone(result)
    
    def test_malformed_packet(self):
        """Test decoding malformed packet"""
        packet = b'\xFF\xFF\xFF\xFF' * 100
        result = decode_ble_advertisement(packet)
        self.assertIsNone(result)
    
    def test_invalid_coordinates(self):
        """Test handling of invalid coordinates"""
        message = {
            'uas_id': 'TEST',
            'latitude': 200.0,  # Invalid latitude (> 90)
            'longitude': -200.0,  # Invalid longitude (> 180)
            'timestamp': datetime.now()
        }
        
        is_valid, errors = self.decoder.validate_message(message)
        
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)
    
    def test_null_remote_id(self):
        """Test handling of null Remote ID"""
        message = {
            'latitude': 37.7749,
            'longitude': -122.4194,
            'timestamp': datetime.now()
        }
        
        is_valid, errors = self.decoder.validate_message(message)
        
        self.assertFalse(is_valid)
        self.assertIn('uas_id', str(errors).lower())
    
    def test_negative_altitude(self):
        """Test handling of negative altitude"""
        message = {
            'uas_id': 'TEST',
            'latitude': 37.7749,
            'longitude': -122.4194,
            'altitude': -100,
            'timestamp': datetime.now()
        }
        
        is_valid, errors = self.decoder.validate_message(message)
        
        # Negative altitude should be acceptable (below ground)
        self.assertTrue(is_valid)


# ============================================================================
# Configuration Tests
# ============================================================================

class TestRemoteIDConfig(unittest.TestCase):
    """Test Remote ID configuration"""
    
    def test_default_config(self):
        """Test default configuration"""
        config = RemoteIDDecoderConfig()
        
        self.assertTrue(config.validate_checksum)
        self.assertEqual(config.max_age_seconds, 10)
        self.assertIn('uas_id', config.required_fields)
    
    def test_custom_config(self):
        """Test custom configuration"""
        config = RemoteIDDecoderConfig(
            validate_checksum=False,
            max_age_seconds=30,
            required_fields=['latitude', 'longitude']
        )
        
        self.assertFalse(config.validate_checksum)
        self.assertEqual(config.max_age_seconds, 30)
        self.assertNotIn('uas_id', config.required_fields)
    
    def test_config_from_dict(self):
        """Test config creation from dictionary"""
        config_dict = {
            'validate_checksum': True,
            'max_age_seconds': 20,
            'required_fields': ['uas_id', 'timestamp']
        }
        
        config = RemoteIDDecoderConfig(**config_dict)
        
        self.assertTrue(config.validate_checksum)
        self.assertEqual(config.max_age_seconds, 20)


# ============================================================================
# Mock Hardware Tests
# ============================================================================

class TestRemoteIDMockHardware(unittest.TestCase):
    """Test Remote ID with mock hardware"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.decoder = RemoteIDDecoder()
    
    @patch('infrastructure.hardware.remote_id_scanner.RemoteIDScanner')
    async def test_mock_scanner(self, MockScanner):
        """Test mock Remote ID scanner"""
        mock_scanner = MockScanner()
        mock_scanner.scan.return_value = [
            {'uas_id': 'TEST001', 'latitude': 37.7749, 'longitude': -122.4194}
        ]
        
        results = await mock_scanner.scan()
        
        self.assertIsNotNone(results)
        self.assertEqual(len(results), 1)


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == '__main__':
    # Run with verbose output
    unittest.main(verbosity=2)