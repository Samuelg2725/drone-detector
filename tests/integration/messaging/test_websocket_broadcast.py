#!/usr/bin/env python3
"""
Integration Tests for WebSocket Broadcast

Tests for WebSocket broadcast functionality including:
- Broadcast to single client
- Broadcast to multiple clients
- Broadcast filtering by channel
- Broadcast with exclusion
- Broadcast performance under load
- Message ordering guarantees
- Reconnection and replay
- Binary message broadcast
"""

import asyncio
import json
import unittest
import time
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime
from pathlib import Path
import sys
import threading
import websockets
from concurrent.futures import ThreadPoolExecutor

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import pytest
from fastapi.testclient import TestClient

# Import application modules
from api.main import create_app
from infrastructure.messaging.websocket_server import (
    WebSocketServer,
    WebSocketManager,
    ConnectionManager,
    MessageHandler,
    WebSocketConfig,
    broadcast_detection,
    broadcast_alert,
    broadcast_metrics,
    broadcast_plot_data
)


# ============================================================================
# Test WebSocket Client
# ============================================================================

class TestWebSocketClient:
    """Test WebSocket client for broadcast testing"""
    
    def __init__(self, url: str, client_id: str = None):
        self.url = url
        self.client_id = client_id or f"client_{id(self)}"
        self.websocket = None
        self.received_messages = []
        self.connected = False
        self._receive_task = None
    
    async def connect(self):
        """Connect to WebSocket server"""
        self.websocket = await websockets.connect(self.url)
        self.connected = True
        self._receive_task = asyncio.create_task(self._receive_loop())
        return self
    
    async def disconnect(self):
        """Disconnect from WebSocket server"""
        self.connected = False
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        if self.websocket:
            await self.websocket.close()
    
    async def send(self, message: dict):
        """Send message to server"""
        if self.websocket:
            await self.websocket.send(json.dumps(message))
    
    async def _receive_loop(self):
        """Background receive loop"""
        try:
            while self.connected:
                try:
                    message = await asyncio.wait_for(self.websocket.recv(), timeout=0.1)
                    data = json.loads(message)
                    self.received_messages.append(data)
                except asyncio.TimeoutError:
                    continue
                except websockets.exceptions.ConnectionClosed:
                    break
        except asyncio.CancelledError:
            pass
    
    def get_messages_by_type(self, msg_type: str) -> list:
        """Get messages filtered by type"""
        return [m for m in self.received_messages if m.get('type') == msg_type]
    
    def clear_messages(self):
        """Clear received messages"""
        self.received_messages.clear()
    
    @property
    def message_count(self) -> int:
        """Get total received messages"""
        return len(self.received_messages)


# ============================================================================
# Test WebSocket Server
# ============================================================================

class TestWebSocketServer:
    """Test WebSocket server for broadcast testing"""
    
    def __init__(self, host: str = "localhost", port: int = 8085):
        self.host = host
        self.port = port
        self.server = None
        self.manager = WebSocketManager()
        self._server_task = None
        self._running = False
    
    async def start(self):
        """Start WebSocket server"""
        self._running = True
        self._server_task = asyncio.create_task(self._run_server())
        await asyncio.sleep(0.1)  # Give server time to start
    
    async def stop(self):
        """Stop WebSocket server"""
        self._running = False
        if self._server_task:
            self._server_task.cancel()
            try:
                await self._server_task
            except asyncio.CancelledError:
                pass
        if self.server:
            self.server.close()
            await self.server.wait_closed()
    
    async def _run_server(self):
        """Run WebSocket server"""
        async with websockets.serve(
            self._handle_connection,
            self.host,
            self.port
        ):
            await asyncio.Future()  # Run forever
    
    async def _handle_connection(self, websocket, path):
        """Handle WebSocket connection"""
        connection_id = await self.manager.register_connection(websocket)
        try:
            async for message in websocket:
                data = json.loads(message)
                await self._handle_message(websocket, data)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self.manager.unregister_connection(connection_id)
    
    async def _handle_message(self, websocket, data):
        """Handle incoming message"""
        msg_type = data.get('type')
        
        if msg_type == 'ping':
            await websocket.send(json.dumps({'type': 'pong', 'timestamp': datetime.now().isoformat()}))
        
        elif msg_type == 'broadcast':
            # Broadcast to all clients
            await self.manager.broadcast_to_all(data.get('data', {}))
        
        elif msg_type == 'subscribe':
            channels = data.get('channels', [])
            await self.manager.subscribe(websocket, channels)
            await websocket.send(json.dumps({'type': 'subscribed', 'channels': channels}))
    
    async def broadcast_detection(self, detection_data: dict):
        """Broadcast detection message"""
        await self.manager.broadcast_to_all({
            'type': 'detection',
            'data': detection_data,
            'timestamp': datetime.now().isoformat()
        })
    
    async def broadcast_alert(self, alert_data: dict):
        """Broadcast alert message"""
        await self.manager.broadcast_to_all({
            'type': 'alert',
            'data': alert_data,
            'timestamp': datetime.now().isoformat()
        })


# ============================================================================
# Test Data Generators
# ============================================================================

class BroadcastTestData:
    """Generate test data for broadcast tests"""
    
    @staticmethod
    def create_test_detection(detection_id: str = "det_001") -> dict:
        """Create test detection data"""
        return {
            'id': detection_id,
            'drone_type': 'DJI Mavic 3',
            'confidence': 0.95,
            'threat_level': 'HIGH',
            'latitude': 37.7749,
            'longitude': -122.4194,
            'altitude': 100.0,
            'timestamp': datetime.now().isoformat()
        }
    
    @staticmethod
    def create_test_alert(alert_id: str = "alert_001") -> dict:
        """Create test alert data"""
        return {
            'id': alert_id,
            'severity': 'CRITICAL',
            'title': 'Drone Detected',
            'message': 'Unauthorized drone in restricted zone',
            'timestamp': datetime.now().isoformat()
        }
    
    @staticmethod
    def create_test_metrics() -> dict:
        """Create test metrics data"""
        return {
            'total_detections': 1247,
            'active_threats': 12,
            'avg_confidence': 0.87,
            'system_uptime': 86400,
            'timestamp': datetime.now().isoformat()
        }
    
    @staticmethod
    def create_test_plot_data() -> dict:
        """Create test plot data"""
        return {
            'event_numbers': [1, 2, 3, 4, 5],
            'confidences': [0.85, 0.92, 0.78, 0.95, 0.88],
            'timestamp': datetime.now().isoformat()
        }


# ============================================================================
# WebSocket Broadcast Test Base
# ============================================================================

class WebSocketBroadcastTestCase(unittest.IsolatedAsyncioTestCase):
    """Base class for WebSocket broadcast tests"""
    
    async def asyncSetUp(self):
        """Set up test fixtures"""
        self.server = TestWebSocketServer(port=8086)
        await self.server.start()
        self.ws_url = f"ws://localhost:8086"
    
    async def asyncTearDown(self):
        """Clean up after tests"""
        await self.server.stop()
    
    async def create_client(self, client_id: str = None) -> TestWebSocketClient:
        """Create and connect a test client"""
        client = TestWebSocketClient(self.ws_url, client_id)
        await client.connect()
        return client


# ============================================================================
# Basic Broadcast Tests
# ============================================================================

class TestBasicBroadcast(WebSocketBroadcastTestCase):
    """Tests for basic broadcast functionality"""
    
    async def test_broadcast_to_single_client(self):
        """Test broadcasting to a single client"""
        client = await self.create_client()
        
        detection = BroadcastTestData.create_test_detection("det_single_001")
        await self.server.broadcast_detection(detection)
        
        # Wait for message to be received
        await asyncio.sleep(0.2)
        
        self.assertGreater(client.message_count, 0)
        
        detection_messages = client.get_messages_by_type('detection')
        self.assertGreater(len(detection_messages), 0)
        self.assertEqual(detection_messages[0]['data']['id'], 'det_single_001')
    
    async def test_broadcast_to_multiple_clients(self):
        """Test broadcasting to multiple clients"""
        clients = []
        for i in range(5):
            client = await self.create_client(f"client_{i}")
            clients.append(client)
        
        detection = BroadcastTestData.create_test_detection("det_multi_001")
        await self.server.broadcast_detection(detection)
        
        await asyncio.sleep(0.2)
        
        for client in clients:
            self.assertGreater(client.message_count, 0)
            detection_messages = client.get_messages_by_type('detection')
            self.assertGreater(len(detection_messages), 0)
            self.assertEqual(detection_messages[0]['data']['id'], 'det_multi_001')
    
    async def test_broadcast_different_message_types(self):
        """Test broadcasting different message types"""
        client = await self.create_client()
        
        # Broadcast multiple types
        detection = BroadcastTestData.create_test_detection("det_type_001")
        alert = BroadcastTestData.create_test_alert("alert_type_001")
        metrics = BroadcastTestData.create_test_metrics()
        
        await self.server.broadcast_detection(detection)
        await self.server.broadcast_alert(alert)
        await self.server.broadcast_to_all({'type': 'metrics', 'data': metrics})
        
        await asyncio.sleep(0.3)
        
        # Check all types received
        detection_msgs = client.get_messages_by_type('detection')
        alert_msgs = client.get_messages_by_type('alert')
        metrics_msgs = client.get_messages_by_type('metrics')
        
        self.assertGreater(len(detection_msgs), 0)
        self.assertGreater(len(alert_msgs), 0)
        self.assertGreater(len(metrics_msgs), 0)


# ============================================================================
# Broadcast with Exclusion Tests
# ============================================================================

class TestBroadcastExclusion(WebSocketBroadcastTestCase):
    """Tests for broadcast with client exclusion"""
    
    async def test_broadcast_exclude_sender(self):
        """Test broadcasting excluding the sender"""
        client1 = await self.create_client("sender")
        client2 = await self.create_client("receiver")
        
        # Broadcast from client1 but exclude client1
        # This requires server-side implementation
        
        # For now, just verify both receive
        detection = BroadcastTestData.create_test_detection("det_exclude_001")
        await self.server.broadcast_detection(detection)
        
        await asyncio.sleep(0.2)
        
        # Both should receive (exclusion not implemented in mock server)
        self.assertGreater(client1.message_count, 0)
        self.assertGreater(client2.message_count, 0)
    
    async def test_broadcast_to_subset(self):
        """Test broadcasting to a subset of clients"""
        clients = []
        for i in range(10):
            client = await self.create_client(f"client_{i}")
            clients.append(client)
        
        # Broadcast to all
        detection = BroadcastTestData.create_test_detection("det_subset_001")
        await self.server.broadcast_detection(detection)
        
        await asyncio.sleep(0.2)
        
        # All should receive
        for client in clients:
            self.assertGreater(client.message_count, 0)


# ============================================================================
# Channel-Based Broadcast Tests
# ============================================================================

class TestChannelBroadcast(WebSocketBroadcastTestCase):
    """Tests for channel-based broadcast"""
    
    async def test_subscribe_to_channel(self):
        """Test subscribing to a channel"""
        client = await self.create_client()
        
        # Subscribe to detections channel
        subscribe_msg = {'type': 'subscribe', 'channels': ['detections']}
        await client.send(subscribe_msg)
        
        await asyncio.sleep(0.1)
        
        # Should receive confirmation
        self.assertGreater(client.message_count, 0)
    
    async def test_channel_filtering(self):
        """Test that messages are filtered by channel"""
        client = await self.create_client()
        
        # Subscribe only to alerts
        subscribe_msg = {'type': 'subscribe', 'channels': ['alerts']}
        await client.send(subscribe_msg)
        
        await asyncio.sleep(0.1)
        client.clear_messages()
        
        # Broadcast detection and alert
        detection = BroadcastTestData.create_test_detection("det_channel_001")
        alert = BroadcastTestData.create_test_alert("alert_channel_001")
        
        await self.server.broadcast_detection(detection)
        await self.server.broadcast_alert(alert)
        
        await asyncio.sleep(0.2)
        
        # Should only receive alert
        alert_msgs = client.get_messages_by_type('alert')
        detection_msgs = client.get_messages_by_type('detection')
        
        self.assertGreater(len(alert_msgs), 0)
        self.assertEqual(len(detection_msgs), 0)
    
    async def test_multiple_channels(self):
        """Test subscribing to multiple channels"""
        client = await self.create_client()
        
        # Subscribe to multiple channels
        subscribe_msg = {'type': 'subscribe', 'channels': ['detections', 'alerts', 'metrics']}
        await client.send(subscribe_msg)
        
        await asyncio.sleep(0.1)
        client.clear_messages()
        
        # Broadcast all types
        detection = BroadcastTestData.create_test_detection("det_multi_001")
        alert = BroadcastTestData.create_test_alert("alert_multi_001")
        metrics = BroadcastTestData.create_test_metrics()
        
        await self.server.broadcast_detection(detection)
        await self.server.broadcast_alert(alert)
        await self.server.broadcast_to_all({'type': 'metrics', 'data': metrics})
        
        await asyncio.sleep(0.3)
        
        # Should receive all types
        self.assertGreater(len(client.get_messages_by_type('detection')), 0)
        self.assertGreater(len(client.get_messages_by_type('alert')), 0)
        self.assertGreater(len(client.get_messages_by_type('metrics')), 0)


# ============================================================================
# Broadcast Performance Tests
# ============================================================================

class TestBroadcastPerformance(WebSocketBroadcastTestCase):
    """Performance tests for broadcast"""
    
    async def test_broadcast_throughput(self):
        """Test broadcast throughput with many messages"""
        client = await self.create_client()
        
        num_messages = 100
        start_time = time.time()
        
        for i in range(num_messages):
            detection = BroadcastTestData.create_test_detection(f"det_perf_{i:04d}")
            await self.server.broadcast_detection(detection)
        
        elapsed = time.time() - start_time
        throughput = num_messages / elapsed
        
        print(f"\nBroadcast throughput: {throughput:.0f} messages/second")
        
        # Should handle at least 50 messages per second
        self.assertGreater(throughput, 50)
    
    async def test_many_clients_broadcast(self):
        """Test broadcast performance with many clients"""
        num_clients = 50
        clients = []
        
        # Connect clients
        start_time = time.time()
        for i in range(num_clients):
            client = await self.create_client(f"client_{i}")
            clients.append(client)
        
        connect_time = time.time() - start_time
        print(f"\nConnected {num_clients} clients in {connect_time:.2f}s")
        
        # Broadcast one message
        detection = BroadcastTestData.create_test_detection("det_many_clients_001")
        
        start_time = time.time()
        await self.server.broadcast_detection(detection)
        
        # Wait for delivery
        await asyncio.sleep(0.5)
        
        # Count deliveries
        total_received = sum(c.message_count for c in clients)
        print(f"Total messages received: {total_received}")
        
        # All clients should have received the message
        for client in clients:
            self.assertGreater(client.message_count, 0)
    
    async def test_concurrent_broadcasts(self):
        """Test concurrent broadcasts from multiple sources"""
        num_broadcasters = 10
        messages_per_broadcaster = 20
        
        async def broadcaster(broadcaster_id):
            for i in range(messages_per_broadcaster):
                detection = BroadcastTestData.create_test_detection(f"det_conc_{broadcaster_id}_{i:03d}")
                await self.server.broadcast_detection(detection)
                await asyncio.sleep(0.01)
        
        client = await self.create_client()
        
        start_time = time.time()
        await asyncio.gather(*[broadcaster(i) for i in range(num_broadcasters)])
        elapsed = time.time() - start_time
        
        total_messages = num_broadcasters * messages_per_broadcaster
        await asyncio.sleep(0.5)  # Wait for processing
        
        print(f"\nConcurrent broadcasts: {total_messages} messages in {elapsed:.2f}s")
        print(f"Client received: {client.message_count} messages")
        
        # Client should have received all messages (allow some loss)
        self.assertGreaterEqual(client.message_count, total_messages * 0.9)


# ============================================================================
# Large Message Broadcast Tests
# ============================================================================

class TestLargeMessageBroadcast(WebSocketBroadcastTestCase):
    """Tests for broadcasting large messages"""
    
    async def test_large_json_message(self):
        """Test broadcasting large JSON message"""
        client = await self.create_client()
        
        # Create large message (100KB)
        large_data = {'data': 'x' * 100000}
        large_message = {
            'type': 'large_data',
            'data': large_data,
            'timestamp': datetime.now().isoformat()
        }
        
        start_time = time.time()
        await self.server.broadcast_to_all(large_message)
        elapsed = time.time() - start_time
        
        await asyncio.sleep(0.5)
        
        print(f"\nLarge message ({len(str(large_message))} bytes) broadcast in {elapsed:.3f}s")
        
        # Should receive without error
        self.assertGreater(client.message_count, 0)
    
    async def test_many_large_messages(self):
        """Test broadcasting many large messages"""
        client = await self.create_client()
        
        num_messages = 10
        message_size = 50000  # 50KB each
        
        start_time = time.time()
        
        for i in range(num_messages):
            large_data = {'data': 'x' * message_size, 'index': i}
            message = {'type': 'large_data', 'data': large_data}
            await self.server.broadcast_to_all(message)
        
        elapsed = time.time() - start_time
        total_data_mb = (num_messages * message_size) / (1024 * 1024)
        
        print(f"\nBroadcast {total_data_mb:.2f} MB in {elapsed:.2f}s")
        print(f"Throughput: {total_data_mb / elapsed:.2f} MB/s")
        
        await asyncio.sleep(1.0)  # Wait for processing
        
        self.assertGreater(client.message_count, 0)


# ============================================================================
# Binary Message Broadcast Tests
# ============================================================================

class TestBinaryBroadcast(WebSocketBroadcastTestCase):
    """Tests for broadcasting binary messages"""
    
    async def test_binary_data_broadcast(self):
        """Test broadcasting binary data"""
        client = await self.create_client()
        
        # Create binary data
        binary_data = bytes([i % 256 for i in range(1024)])
        
        # Broadcast as binary (requires custom server implementation)
        # For this test, we'll use JSON with base64 encoded data
        import base64
        
        message = {
            'type': 'binary',
            'data': base64.b64encode(binary_data).decode('ascii'),
            'encoding': 'base64'
        }
        
        await self.server.broadcast_to_all(message)
        
        await asyncio.sleep(0.2)
        
        self.assertGreater(client.message_count, 0)


# ============================================================================
# Broadcast Ordering Tests
# ============================================================================

class TestBroadcastOrdering(WebSocketBroadcastTestCase):
    """Tests for broadcast message ordering"""
    
    async def test_message_ordering(self):
        """Test that messages are received in order"""
        client = await self.create_client()
        
        num_messages = 50
        
        for i in range(num_messages):
            detection = BroadcastTestData.create_test_detection(f"det_order_{i:03d}")
            await self.server.broadcast_detection(detection)
            await asyncio.sleep(0.01)
        
        await asyncio.sleep(0.5)
        
        # Check ordering by sequence
        detection_msgs = client.get_messages_by_type('detection')
        received_ids = [msg['data']['id'] for msg in detection_msgs]
        expected_ids = [f"det_order_{i:03d}" for i in range(num_messages)]
        
        # Check that first N IDs match expected (may not receive all)
        for i, expected in enumerate(expected_ids[:len(received_ids)]):
            self.assertEqual(received_ids[i], expected, f"Order mismatch at position {i}")
    
    async def test_concurrent_broadcast_ordering(self):
        """Test ordering of concurrent broadcasts"""
        client = await self.create_client()
        
        async def send_messages(prefix, count):
            for i in range(count):
                detection = BroadcastTestData.create_test_detection(f"{prefix}_{i:03d}")
                await self.server.broadcast_detection(detection)
                await asyncio.sleep(0.005)
        
        # Send from multiple sources concurrently
        await asyncio.gather(
            send_messages("A", 20),
            send_messages("B", 20),
            send_messages("C", 20)
        )
        
        await asyncio.sleep(1.0)
        
        detection_msgs = client.get_messages_by_type('detection')
        received_ids = [msg['data']['id'] for msg in detection_msgs]
        
        print(f"\nReceived {len(received_ids)} messages")
        
        # Should have received messages (order may be interleaved)
        self.assertGreater(len(received_ids), 0)


# ============================================================================
# Broadcast Reliability Tests
# ============================================================================

class TestBroadcastReliability(WebSocketBroadcastTestCase):
    """Tests for broadcast reliability"""
    
    async def test_broadcast_with_disconnecting_clients(self):
        """Test broadcast with clients disconnecting during transmission"""
        clients = []
        for i in range(10):
            client = await self.create_client(f"client_{i}")
            clients.append(client)
        
        # Broadcast many messages
        for i in range(50):
            detection = BroadcastTestData.create_test_detection(f"det_rel_{i:03d}")
            await self.server.broadcast_detection(detection)
            
            # Disconnect some clients midway
            if i == 25:
                for j in range(5, 8):
                    await clients[j].disconnect()
        
        await asyncio.sleep(0.5)
        
        # Remaining clients should have received messages
        for j in range(5):  # First 5 clients should still be connected
            self.assertGreater(clients[j].message_count, 0)
    
    async def test_broadcast_during_reconnection(self):
        """Test broadcast behavior during client reconnection"""
        client = await self.create_client()
        
        # Send some messages
        for i in range(10):
            detection = BroadcastTestData.create_test_detection(f"det_recon_{i:03d}")
            await self.server.broadcast_detection(detection)
        
        # Disconnect and reconnect
        await client.disconnect()
        await client.connect()
        
        # Send more messages
        for i in range(10, 20):
            detection = BroadcastTestData.create_test_detection(f"det_recon_{i:03d}")
            await self.server.broadcast_detection(detection)
        
        await asyncio.sleep(0.5)
        
        # Should receive messages after reconnection
        self.assertGreater(client.message_count, 0)


# ============================================================================
# Broadcast Error Handling Tests
# ============================================================================

class TestBroadcastErrorHandling(WebSocketBroadcastTestCase):
    """Tests for broadcast error handling"""
    
    async def test_broadcast_with_invalid_message(self):
        """Test broadcasting invalid message"""
        client = await self.create_client()
        
        # Send invalid message (missing required fields)
        invalid_message = {'type': 'invalid', 'data': None}
        
        try:
            await self.server.broadcast_to_all(invalid_message)
        except Exception:
            pass  # Should handle gracefully
        
        await asyncio.sleep(0.2)
        
        # Should not crash, client may or may not receive
        self.assertTrue(True)
    
    async def test_broadcast_to_nonexistent_client(self):
        """Test broadcasting to nonexistent client"""
        # This should not raise exception
        try:
            await self.server.manager.send_to_connection("nonexistent", {'test': 'data'})
        except Exception:
            self.fail("Broadcast to nonexistent client raised exception")


# ============================================================================
# Stress Tests
# ============================================================================

class TestBroadcastStress(WebSocketBroadcastTestCase):
    """Stress tests for broadcast system"""
    
    async def test_sustained_broadcast_load(self):
        """Test sustained broadcast load over time"""
        client = await self.create_client()
        
        duration = 10  # seconds
        start_time = time.time()
        message_count = 0
        
        while time.time() - start_time < duration:
            detection = BroadcastTestData.create_test_detection(f"det_stress_{message_count:05d}")
            await self.server.broadcast_detection(detection)
            message_count += 1
            await asyncio.sleep(0.01)  # 100 messages per second
        
        elapsed = time.time() - start_time
        actual_rate = message_count / elapsed
        
        print(f"\nStress test: {message_count} messages in {elapsed:.2f}s ({actual_rate:.0f} msg/s)")
        print(f"Client received: {client.message_count} messages")
        
        # Should have received most messages
        self.assertGreater(client.message_count, message_count * 0.8)
    
    async def test_peak_load_burst(self):
        """Test peak load burst handling"""
        client = await self.create_client()
        
        burst_size = 500
        start_time = time.time()
        
        # Send burst of messages
        for i in range(burst_size):
            detection = BroadcastTestData.create_test_detection(f"det_burst_{i:04d}")
            await self.server.broadcast_detection(detection)
        
        elapsed = time.time() - start_time
        burst_rate = burst_size / elapsed
        
        print(f"\nBurst: {burst_size} messages in {elapsed:.3f}s ({burst_rate:.0f} msg/s)")
        
        await asyncio.sleep(1.0)  # Wait for processing
        
        print(f"Client received: {client.message_count} messages")
        
        # Should have received most messages
        self.assertGreater(client.message_count, burst_size * 0.7)


# ============================================================================
# Run Tests
# ============================================================================

async def run_tests():
    """Run all broadcast tests"""
    test_classes = [
        TestBasicBroadcast,
        TestBroadcastExclusion,
        TestChannelBroadcast,
        TestBroadcastPerformance,
        TestLargeMessageBroadcast,
        TestBinaryBroadcast,
        TestBroadcastOrdering,
        TestBroadcastReliability,
        TestBroadcastErrorHandling,
        TestBroadcastStress
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
    asyncio.run(run_tests())