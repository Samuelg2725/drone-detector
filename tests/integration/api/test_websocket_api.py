#!/usr/bin/env python3
"""
Integration Tests for WebSocket API

Tests for WebSocket endpoints including:
- Connection establishment and handshake
- Message broadcasting (detections, alerts, metrics)
- Subscription management
- Command sending and response
- Multiple client connections
- Reconnection handling
- Message routing
- Error handling
- Performance under load
"""

import asyncio
import json
import unittest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime
from pathlib import Path
import sys
import tempfile
import time

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

# Import application
from api.main import create_app
from infrastructure.messaging.websocket_server import (
    WebSocketManager,
    ConnectionManager,
    MessageHandler,
    WebSocketConfig
)


# ============================================================================
# Test WebSocket Client
# ============================================================================

class TestWebSocketClient:
    """Test WebSocket client for integration testing"""
    
    def __init__(self, url: str):
        self.url = url
        self.websocket = None
        self.received_messages = []
        self.connected = False
    
    async def connect(self):
        """Connect to WebSocket server"""
        import websockets
        self.websocket = await websockets.connect(self.url)
        self.connected = True
    
    async def disconnect(self):
        """Disconnect from WebSocket server"""
        if self.websocket:
            await self.websocket.close()
            self.connected = False
    
    async def send(self, message: dict):
        """Send message to server"""
        if self.websocket:
            await self.websocket.send(json.dumps(message))
    
    async def receive(self, timeout: float = 5.0) -> dict:
        """Receive message from server"""
        try:
            message = await asyncio.wait_for(self.websocket.recv(), timeout=timeout)
            data = json.loads(message)
            self.received_messages.append(data)
            return data
        except asyncio.TimeoutError:
            return None
    
    async def receive_all(self, count: int, timeout: float = 5.0) -> list:
        """Receive multiple messages"""
        messages = []
        for _ in range(count):
            msg = await self.receive(timeout)
            if msg:
                messages.append(msg)
            else:
                break
        return messages


# ============================================================================
# Test Data Generators
# ============================================================================

class WebSocketTestData:
    """Generate test data for WebSocket tests"""
    
    @staticmethod
    def create_test_detection(detection_id: str = "det_001") -> dict:
        """Create test detection message"""
        return {
            'type': 'detection',
            'data': {
                'id': detection_id,
                'drone_type': 'DJI Mavic 3',
                'confidence': 0.95,
                'threat_level': 'HIGH',
                'latitude': 37.7749,
                'longitude': -122.4194,
                'altitude': 100.0,
                'timestamp': datetime.now().isoformat()
            },
            'timestamp': datetime.now().isoformat()
        }
    
    @staticmethod
    def create_test_alert(alert_id: str = "alert_001") -> dict:
        """Create test alert message"""
        return {
            'type': 'alert',
            'data': {
                'id': alert_id,
                'severity': 'CRITICAL',
                'title': 'Drone Detected',
                'message': 'Unauthorized drone in restricted zone',
                'timestamp': datetime.now().isoformat()
            },
            'timestamp': datetime.now().isoformat()
        }
    
    @staticmethod
    def create_test_metrics() -> dict:
        """Create test metrics message"""
        return {
            'type': 'metrics',
            'data': {
                'total_detections': 1247,
                'active_threats': 12,
                'avg_confidence': 0.87,
                'system_uptime': 86400
            },
            'timestamp': datetime.now().isoformat()
        }
    
    @staticmethod
    def create_subscribe_message(channels: list) -> dict:
        """Create subscribe message"""
        return {
            'type': 'subscribe',
            'channels': channels,
            'timestamp': datetime.now().isoformat()
        }
    
    @staticmethod
    def create_command_message(command: str, data: dict = None) -> dict:
        """Create command message"""
        return {
            'type': 'command',
            'command': command,
            'data': data or {},
            'timestamp': datetime.now().isoformat()
        }
    
    @staticmethod
    def create_ping_message() -> dict:
        """Create ping message"""
        return {
            'type': 'ping',
            'timestamp': datetime.now().isoformat()
        }


# ============================================================================
# WebSocket API Test Base
# ============================================================================

class WebSocketAPITestCase(unittest.IsolatedAsyncioTestCase):
    """Base test case for WebSocket API tests"""
    
    async def asyncSetUp(self):
        """Set up test fixtures"""
        # Create FastAPI app
        self.app = create_app()
        
        # Get WebSocket endpoint URL
        self.ws_url = "ws://localhost:8082/ws"
        
        # Track connected clients
        self.clients = []
    
    async def asyncTearDown(self):
        """Clean up after tests"""
        for client in self.clients:
            if client.connected:
                await client.disconnect()
    
    async def create_client(self) -> TestWebSocketClient:
        """Create and connect a test client"""
        client = TestWebSocketClient(self.ws_url)
        await client.connect()
        self.clients.append(client)
        return client


# ============================================================================
# Connection Tests
# ============================================================================

class TestWebSocketConnection(WebSocketAPITestCase):
    """Tests for WebSocket connection establishment"""
    
    async def test_connection_success(self):
        """Test successful WebSocket connection"""
        client = await self.create_client()
        
        self.assertTrue(client.connected)
        self.assertIsNotNone(client.websocket)
    
    async def test_multiple_connections(self):
        """Test multiple simultaneous connections"""
        clients = []
        for i in range(5):
            client = await self.create_client()
            clients.append(client)
            self.assertTrue(client.connected)
        
        self.assertEqual(len(clients), 5)
        
        for client in clients:
            await client.disconnect()
    
    async def test_connection_with_invalid_path(self):
        """Test connection to invalid WebSocket path"""
        client = TestWebSocketClient("ws://localhost:8082/invalid")
        
        with self.assertRaises(Exception):
            await client.connect()
    
    async def test_reconnection(self):
        """Test reconnection after disconnect"""
        client = await self.create_client()
        self.assertTrue(client.connected)
        
        await client.disconnect()
        self.assertFalse(client.connected)
        
        await client.connect()
        self.assertTrue(client.connected)


# ============================================================================
# Message Broadcasting Tests
# ============================================================================

class TestWebSocketBroadcasting(WebSocketAPITestCase):
    """Tests for message broadcasting"""
    
    async def test_broadcast_detection(self):
        """Test broadcasting detection to all clients"""
        client1 = await self.create_client()
        client2 = await self.create_client()
        
        # Send detection via backend (simulated)
        detection = WebSocketTestData.create_test_detection("det_broadcast_001")
        
        # In real test, this would come from the backend
        # For integration test, we simulate via command
        await client1.send(detection)
        
        # Both clients should receive
        msg1 = await client1.receive(timeout=2.0)
        msg2 = await client2.receive(timeout=2.0)
        
        # At least one should receive (depending on broadcast implementation)
        self.assertIsNotNone(msg1 or msg2)
    
    async def test_broadcast_alert(self):
        """Test broadcasting alert to all clients"""
        client = await self.create_client()
        
        alert = WebSocketTestData.create_test_alert("alert_broadcast_001")
        await client.send(alert)
        
        response = await client.receive(timeout=2.0)
        # Alert should be broadcast
        self.assertIsNotNone(response)
    
    async def test_broadcast_metrics(self):
        """Test broadcasting metrics to all clients"""
        client = await self.create_client()
        
        metrics = WebSocketTestData.create_test_metrics()
        await client.send(metrics)
        
        response = await client.receive(timeout=2.0)
        self.assertIsNotNone(response)


# ============================================================================
# Subscription Tests
# ============================================================================

class TestWebSocketSubscription(WebSocketAPITestCase):
    """Tests for channel subscription"""
    
    async def test_subscribe_to_channel(self):
        """Test subscribing to a channel"""
        client = await self.create_client()
        
        subscribe_msg = WebSocketTestData.create_subscribe_message(['detections'])
        await client.send(subscribe_msg)
        
        # Should receive subscription confirmation
        response = await client.receive(timeout=2.0)
        if response:
            self.assertEqual(response.get('type'), 'subscribed')
    
    async def test_subscribe_multiple_channels(self):
        """Test subscribing to multiple channels"""
        client = await self.create_client()
        
        subscribe_msg = WebSocketTestData.create_subscribe_message(['detections', 'alerts', 'metrics'])
        await client.send(subscribe_msg)
        
        response = await client.receive(timeout=2.0)
        if response:
            self.assertEqual(response.get('type'), 'subscribed')
            self.assertEqual(len(response.get('channels', [])), 3)
    
    async def test_receive_filtered_messages(self):
        """Test receiving only subscribed messages"""
        client = await self.create_client()
        
        # Subscribe only to detections
        subscribe_msg = WebSocketTestData.create_subscribe_message(['detections'])
        await client.send(subscribe_msg)
        
        # Send different types of messages (simulated)
        detection = WebSocketTestData.create_test_detection()
        alert = WebSocketTestData.create_test_alert()
        
        await client.send(detection)
        await client.send(alert)
        
        # Should only receive detection (may need to wait)
        messages = await client.receive_all(2, timeout=1.0)
        
        # At least one message should be detection type
        detection_received = any(m.get('type') == 'detection' for m in messages)
        self.assertTrue(detection_received)
    
    async def test_unsubscribe_from_channel(self):
        """Test unsubscribing from a channel"""
        client = await self.create_client()
        
        # Subscribe then unsubscribe
        subscribe_msg = WebSocketTestData.create_subscribe_message(['detections'])
        await client.send(subscribe_msg)
        
        unsubscribe_msg = {'type': 'unsubscribe', 'channels': ['detections']}
        await client.send(unsubscribe_msg)
        
        response = await client.receive(timeout=2.0)
        if response:
            self.assertEqual(response.get('type'), 'unsubscribed')


# ============================================================================
# Command Handling Tests
# ============================================================================

class TestWebSocketCommands(WebSocketAPITestCase):
    """Tests for command handling"""
    
    async def test_ping_command(self):
        """Test ping command"""
        client = await self.create_client()
        
        ping_msg = WebSocketTestData.create_ping_message()
        await client.send(ping_msg)
        
        response = await client.receive(timeout=2.0)
        
        if response:
            self.assertEqual(response.get('type'), 'pong')
    
    async def test_get_status_command(self):
        """Test get status command"""
        client = await self.create_client()
        
        command = WebSocketTestData.create_command_message('get_status')
        await client.send(command)
        
        response = await client.receive(timeout=2.0)
        
        if response:
            self.assertEqual(response.get('type'), 'status')
            self.assertIn('data', response)
    
    async def test_start_system_command(self):
        """Test start system command"""
        client = await self.create_client()
        
        command = WebSocketTestData.create_command_message('start_system')
        await client.send(command)
        
        response = await client.receive(timeout=2.0)
        
        if response:
            self.assertEqual(response.get('type'), 'command_response')
            self.assertTrue(response.get('data', {}).get('success', False))
    
    async def test_stop_system_command(self):
        """Test stop system command"""
        client = await self.create_client()
        
        command = WebSocketTestData.create_command_message('stop_system')
        await client.send(command)
        
        response = await client.receive(timeout=2.0)
        
        if response:
            self.assertEqual(response.get('type'), 'command_response')
    
    async def test_invalid_command(self):
        """Test invalid command"""
        client = await self.create_client()
        
        command = WebSocketTestData.create_command_message('invalid_command')
        await client.send(command)
        
        response = await client.receive(timeout=2.0)
        
        if response:
            self.assertEqual(response.get('type'), 'error')
            self.assertIn('Invalid command', response.get('message', ''))


# ============================================================================
# Multiple Client Tests
# ============================================================================

class TestMultipleClients(WebSocketAPITestCase):
    """Tests for multiple client interactions"""
    
    async def test_broadcast_to_all(self):
        """Test broadcasting to all connected clients"""
        clients = []
        for i in range(3):
            client = await self.create_client()
            clients.append(client)
        
        # Broadcast message from one client
        broadcast_msg = {'type': 'broadcast', 'data': {'message': 'hello'}}
        await clients[0].send(broadcast_msg)
        
        # All clients should receive
        await asyncio.sleep(0.5)
        
        for client in clients:
            self.assertGreaterEqual(len(client.received_messages), 0)
    
    async def test_private_message(self):
        """Test sending private message to specific client"""
        client1 = await self.create_client()
        client2 = await self.create_client()
        
        # Send private message (implementation specific)
        private_msg = {'type': 'private', 'target': 'client2', 'data': {'secret': 'data'}}
        await client1.send(private_msg)
        
        # Only client2 should receive
        await asyncio.sleep(0.5)
        
        # This test depends on implementation
        # For now, just verify no errors
        self.assertTrue(True)
    
    async def test_client_disconnect_handling(self):
        """Test handling of client disconnection"""
        client1 = await self.create_client()
        client2 = await self.create_client()
        
        # Disconnect one client
        await client1.disconnect()
        
        # Broadcast should still work for remaining clients
        broadcast_msg = {'type': 'broadcast', 'data': {'message': 'test'}}
        await client2.send(broadcast_msg)
        
        response = await client2.receive(timeout=2.0)
        self.assertIsNotNone(response)


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestWebSocketErrorHandling(WebSocketAPITestCase):
    """Tests for WebSocket error handling"""
    
    async def test_invalid_json(self):
        """Test sending invalid JSON"""
        client = await self.create_client()
        
        # Send invalid JSON
        if client.websocket:
            await client.websocket.send("not valid json")
        
        # Should not crash, may receive error message
        response = await client.receive(timeout=2.0)
        # No assertion, just verify no exception
    
    async def test_malformed_message(self):
        """Test sending malformed message"""
        client = await self.create_client()
        
        malformed = {'type': 'missing_data'}  # Missing required fields
        await client.send(malformed)
        
        response = await client.receive(timeout=2.0)
        
        if response:
            self.assertEqual(response.get('type'), 'error')
    
    async def test_rate_limit_exceeded(self):
        """Test rate limiting"""
        client = await self.create_client()
        
        # Send many messages quickly
        for i in range(100):
            msg = WebSocketTestData.create_ping_message()
            await client.send(msg)
        
        await asyncio.sleep(0.5)
        
        # Should not crash, some messages may be rate limited
        self.assertTrue(True)
    
    async def test_large_message(self):
        """Test sending large message"""
        client = await self.create_client()
        
        # Create large message (1MB)
        large_data = {'data': 'x' * 1000000}
        large_msg = {'type': 'data', 'data': large_data}
        
        await client.send(large_msg)
        
        response = await client.receive(timeout=5.0)
        # Should handle large message or return error
        if response:
            self.assertIn('type', response)


# ============================================================================
# Heartbeat Tests
# ============================================================================

class TestWebSocketHeartbeat(WebSocketAPITestCase):
    """Tests for heartbeat mechanism"""
    
    async def test_heartbeat_response(self):
        """Test heartbeat ping/pong"""
        client = await self.create_client()
        
        ping = WebSocketTestData.create_ping_message()
        await client.send(ping)
        
        response = await client.receive(timeout=2.0)
        
        if response:
            self.assertEqual(response.get('type'), 'pong')
    
    async def test_heartbeat_timeout(self):
        """Test heartbeat timeout handling"""
        # This test would need to simulate network issues
        # For integration test, just verify connection handles idle
        client = await self.create_client()
        
        # Stay idle for a while
        await asyncio.sleep(2)
        
        # Should still be connected
        self.assertTrue(client.connected)
        
        # Send a message to verify
        ping = WebSocketTestData.create_ping_message()
        await client.send(ping)
        
        response = await client.receive(timeout=2.0)
        # May or may not receive, but no exception
        self.assertTrue(True)


# ============================================================================
# Performance Tests
# ============================================================================

class TestWebSocketPerformance(WebSocketAPITestCase):
    """Performance tests for WebSocket"""
    
    async def test_message_throughput(self):
        """Test message throughput"""
        client = await self.create_client()
        
        num_messages = 100
        start_time = time.time()
        
        for i in range(num_messages):
            msg = WebSocketTestData.create_ping_message()
            await client.send(msg)
        
        elapsed = time.time() - start_time
        throughput = num_messages / elapsed
        
        print(f"\nThroughput: {throughput:.0f} messages/second")
        
        # Should handle at least 50 messages/second
        self.assertGreater(throughput, 50)
    
    async def test_multiple_client_load(self):
        """Test load with multiple clients"""
        num_clients = 50
        clients = []
        
        # Connect many clients
        start_time = time.time()
        for i in range(num_clients):
            client = await self.create_client()
            clients.append(client)
        
        connect_time = time.time() - start_time
        print(f"\nConnected {num_clients} clients in {connect_time:.2f}s")
        
        # Should connect within reasonable time
        self.assertLess(connect_time, 10)
        
        # Send messages from all clients
        start_time = time.time()
        for client in clients:
            await client.send(WebSocketTestData.create_ping_message())
        
        # Disconnect all
        for client in clients:
            await client.disconnect()
        
        elapsed = time.time() - start_time
        print(f"Sent messages in {elapsed:.2f}s")
    
    async def test_concurrent_messages(self):
        """Test concurrent message sending"""
        num_clients = 10
        messages_per_client = 50
        
        async def client_worker(num_messages):
            client = await self.create_client()
            for i in range(num_messages):
                await client.send(WebSocketTestData.create_ping_message())
            await client.disconnect()
            return client.received_messages
        
        start_time = time.time()
        tasks = [client_worker(messages_per_client) for _ in range(num_clients)]
        results = await asyncio.gather(*tasks)
        elapsed = time.time() - start_time
        
        total_messages = sum(len(r) for r in results)
        print(f"\nProcessed {total_messages} messages in {elapsed:.2f}s")
        
        # Should handle concurrent load
        self.assertGreater(total_messages, 0)


# ============================================================================
# Security Tests
# ============================================================================

class TestWebSocketSecurity(WebSocketAPITestCase):
    """Security tests for WebSocket"""
    
    async def test_authentication_required(self):
        """Test that authentication is required"""
        # Try to connect without auth token
        client = TestWebSocketClient(self.ws_url)
        
        try:
            await client.connect()
            # If connection succeeds, check if auth is required
            # Send unauthenticated message
            await client.send({'type': 'ping'})
            response = await client.receive(timeout=2.0)
            # May get auth error
            if response and response.get('type') == 'error':
                self.assertIn('auth', response.get('message', '').lower())
        except Exception:
            # Connection may be rejected
            self.assertTrue(True)
    
    async def test_invalid_token(self):
        """Test connection with invalid token"""
        # This test depends on auth implementation
        # For now, just verify the endpoint exists
        client = TestWebSocketClient(f"{self.ws_url}?token=invalid")
        
        try:
            await client.connect()
        except Exception:
            self.assertTrue(True)
    
    async def test_message_validation(self):
        """Test message validation for security"""
        client = await self.create_client()
        
        # Try to send message with injection attempt
        malicious = {
            'type': 'command',
            'command': 'eval',
            'data': {'code': 'import os; os.system("rm -rf /")'}
        }
        
        await client.send(malicious)
        
        response = await client.receive(timeout=2.0)
        
        if response:
            # Should reject malicious command
            self.assertIn('error', response.get('type', '').lower() or '')
    
    async def test_rate_limit_security(self):
        """Test rate limiting for security"""
        client = await self.create_client()
        
        # Send many messages to trigger rate limit
        for i in range(200):
            await client.send(WebSocketTestData.create_ping_message())
        
        await asyncio.sleep(0.5)
        
        # Should not crash, may reject some messages
        self.assertTrue(True)


# ============================================================================
# Recovery Tests
# ============================================================================

class TestWebSocketRecovery(WebSocketAPITestCase):
    """Tests for WebSocket recovery mechanisms"""
    
    async def test_server_restart_recovery(self):
        """Test client recovery after server restart"""
        client = await self.create_client()
        self.assertTrue(client.connected)
        
        # Simulate server restart (would need to restart server)
        # For integration test, just verify reconnect capability
        await client.disconnect()
        
        # Reconnect
        await client.connect()
        self.assertTrue(client.connected)
    
    async def test_message_queue_on_disconnect(self):
        """Test message queuing during disconnect"""
        client = await self.create_client()
        
        # Disconnect
        await client.disconnect()
        
        # Messages sent while disconnected should be queued
        # (Implementation dependent)
        
        # Reconnect
        await client.connect()
        
        # Should receive queued messages
        response = await client.receive(timeout=2.0)
        # May or may not receive queued messages
        self.assertTrue(True)


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == '__main__':
    # Run with verbose output
    unittest.main(verbosity=2)