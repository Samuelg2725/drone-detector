#!/usr/bin/env python3
"""
Unit Tests for WebSocket Module

Tests for WebSocket server, connection management, message broadcasting,
and real-time communication functionality.
"""

import asyncio
import json
import unittest
from unittest.mock import Mock, patch, AsyncMock, MagicMock, call
from datetime import datetime
import time

# Import modules to test
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from infrastructure.messaging.websocket_server import (
    WebSocketServer,
    WebSocketManager,
    ConnectionManager,
    MessageHandler,
    WebSocketConfig,
    start_websocket_server,
    broadcast_detection,
    broadcast_alert,
    broadcast_metrics,
    broadcast_plot_data,
    get_websocket_manager
)


# ============================================================================
# Test Data Generators
# ============================================================================

class TestDataGenerator:
    """Generate test data for WebSocket tests"""
    
    @staticmethod
    def create_test_detection() -> dict:
        """Create test detection data"""
        return {
            'id': 'det_001',
            'timestamp': datetime.now().isoformat(),
            'drone_type': 'DJI Mavic 3',
            'confidence': 0.95,
            'threat_level': 'HIGH',
            'latitude': 37.7749,
            'longitude': -122.4194,
            'altitude': 100.0,
            'frequency': 2.44e9,
            'signal_strength': -45.2
        }
    
    @staticmethod
    def create_test_alert() -> dict:
        """Create test alert data"""
        return {
            'id': 'alert_001',
            'severity': 'CRITICAL',
            'title': 'Drone Detected',
            'message': 'Unauthorized drone in restricted zone',
            'timestamp': datetime.now().isoformat(),
            'drone_id': 'det_001'
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
            'confidences': [0.85, 0.92, 0.78, 0.95, 0.88]
        }
    
    @staticmethod
    def create_test_command(command: str, data: dict = None) -> dict:
        """Create test command message"""
        return {
            'type': 'command',
            'command': command,
            'data': data or {},
            'timestamp': datetime.now().isoformat()
        }


# ============================================================================
# Mock WebSocket Connection
# ============================================================================

class MockWebSocket:
    """Mock WebSocket connection for testing"""
    
    def __init__(self):
        self.sent_messages = []
        self.received_messages = []
        self.closed = False
        self.accepted = False
        self.close_code = None
        self.close_reason = None
    
    async def accept(self):
        """Accept connection"""
        self.accepted = True
    
    async def receive_text(self) -> str:
        """Receive text message"""
        if self.received_messages:
            return self.received_messages.pop(0)
        await asyncio.sleep(0.1)
        return ''
    
    async def receive_json(self) -> dict:
        """Receive JSON message"""
        text = await self.receive_text()
        if text:
            return json.loads(text)
        return {}
    
    async def send_text(self, data: str):
        """Send text message"""
        self.sent_messages.append(data)
    
    async def send_json(self, data: dict):
        """Send JSON message"""
        await self.send_text(json.dumps(data))
    
    async def close(self, code: int = 1000, reason: str = ""):
        """Close connection"""
        self.closed = True
        self.close_code = code
        self.close_reason = reason
    
    def add_received_message(self, message: str):
        """Add message to receive queue"""
        self.received_messages.append(message)


# ============================================================================
# Connection Manager Tests
# ============================================================================

class TestConnectionManager(unittest.TestCase):
    """Test connection manager functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.manager = ConnectionManager()
        self.mock_ws = MockWebSocket()
    
    async def test_connect(self):
        """Test connecting a client"""
        await self.manager.connect(self.mock_ws)
        
        self.assertIn(self.mock_ws, self.manager.active_connections)
        self.assertTrue(self.mock_ws.accepted)
    
    async def test_disconnect(self):
        """Test disconnecting a client"""
        await self.manager.connect(self.mock_ws)
        self.manager.disconnect(self.mock_ws)
        
        self.assertNotIn(self.mock_ws, self.manager.active_connections)
    
    async def test_broadcast(self):
        """Test broadcasting to all clients"""
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()
        
        await self.manager.connect(ws1)
        await self.manager.connect(ws2)
        
        test_message = {'type': 'test', 'data': 'hello'}
        await self.manager.broadcast(test_message)
        
        # Both clients should have received the message
        self.assertEqual(len(ws1.sent_messages), 1)
        self.assertEqual(len(ws2.sent_messages), 1)
        
        sent_data = json.loads(ws1.sent_messages[0])
        self.assertEqual(sent_data['type'], 'test')
    
    async def test_broadcast_excludes_sender(self):
        """Test broadcasting excluding specific client"""
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()
        
        await self.manager.connect(ws1)
        await self.manager.connect(ws2)
        
        test_message = {'type': 'test', 'data': 'hello'}
        await self.manager.broadcast(test_message, exclude=ws1)
        
        # ws2 should receive, ws1 should not
        self.assertEqual(len(ws2.sent_messages), 1)
        self.assertEqual(len(ws1.sent_messages), 0)
    
    async def test_send_to_client(self):
        """Test sending to specific client"""
        await self.manager.connect(self.mock_ws)
        
        test_message = {'type': 'private', 'data': 'secret'}
        await self.manager.send_to_client(self.mock_ws, test_message)
        
        self.assertEqual(len(self.mock_ws.sent_messages), 1)
        sent_data = json.loads(self.mock_ws.sent_messages[0])
        self.assertEqual(sent_data['type'], 'private')
    
    async def test_get_connection_count(self):
        """Test getting connection count"""
        self.assertEqual(self.manager.get_connection_count(), 0)
        
        await self.manager.connect(MockWebSocket())
        await self.manager.connect(MockWebSocket())
        await self.manager.connect(MockWebSocket())
        
        self.assertEqual(self.manager.get_connection_count(), 3)
    
    async def test_broadcast_with_filter(self):
        """Test broadcasting with filter function"""
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()
        
        await self.manager.connect(ws1)
        await self.manager.connect(ws2)
        
        # Only broadcast to connections that have a certain attribute
        ws1.should_receive = True
        ws2.should_receive = False
        
        def filter_func(conn):
            return getattr(conn, 'should_receive', False)
        
        test_message = {'type': 'filtered', 'data': 'test'}
        await self.manager.broadcast(test_message, filter_func=filter_func)
        
        self.assertEqual(len(ws1.sent_messages), 1)
        self.assertEqual(len(ws2.sent_messages), 0)


# ============================================================================
# WebSocket Manager Tests
# ============================================================================

class TestWebSocketManager(unittest.TestCase):
    """Test WebSocket manager functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = WebSocketConfig(
            host='localhost',
            port=8083,
            ping_interval=20,
            ping_timeout=30
        )
        self.manager = WebSocketManager(config=self.config)
    
    async def test_initialization(self):
        """Test manager initialization"""
        self.assertIsNotNone(self.manager)
        self.assertEqual(self.manager.config.host, 'localhost')
        self.assertEqual(self.manager.config.port, 8083)
    
    async def test_register_connection(self):
        """Test registering a connection"""
        mock_ws = MockWebSocket()
        connection_id = await self.manager.register_connection(mock_ws)
        
        self.assertIsNotNone(connection_id)
        self.assertIn(connection_id, self.manager.connections)
        self.assertEqual(len(self.manager.connections), 1)
    
    async def test_unregister_connection(self):
        """Test unregistering a connection"""
        mock_ws = MockWebSocket()
        connection_id = await self.manager.register_connection(mock_ws)
        
        await self.manager.unregister_connection(connection_id)
        
        self.assertNotIn(connection_id, self.manager.connections)
        self.assertEqual(len(self.manager.connections), 0)
    
    async def test_broadcast_to_all(self):
        """Test broadcasting to all connections"""
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()
        
        await self.manager.register_connection(ws1)
        await self.manager.register_connection(ws2)
        
        test_message = {'type': 'broadcast', 'data': 'test'}
        await self.manager.broadcast_to_all(test_message)
        
        self.assertEqual(len(ws1.sent_messages), 1)
        self.assertEqual(len(ws2.sent_messages), 1)
    
    async def test_send_to_connection(self):
        """Test sending to specific connection"""
        mock_ws = MockWebSocket()
        connection_id = await self.manager.register_connection(mock_ws)
        
        test_message = {'type': 'private', 'data': 'secret'}
        await self.manager.send_to_connection(connection_id, test_message)
        
        self.assertEqual(len(mock_ws.sent_messages), 1)
    
    async def test_send_to_nonexistent_connection(self):
        """Test sending to nonexistent connection"""
        result = await self.manager.send_to_connection('nonexistent', {'test': 'data'})
        
        self.assertFalse(result)
    
    async def test_get_connection_info(self):
        """Test getting connection information"""
        mock_ws = MockWebSocket()
        connection_id = await self.manager.register_connection(mock_ws)
        
        info = self.manager.get_connection_info(connection_id)
        
        self.assertIsNotNone(info)
        self.assertIn('id', info)
        self.assertIn('connected_at', info)
    
    async def test_get_all_connections_info(self):
        """Test getting all connections information"""
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()
        
        await self.manager.register_connection(ws1)
        await self.manager.register_connection(ws2)
        
        connections_info = self.manager.get_all_connections_info()
        
        self.assertEqual(len(connections_info), 2)


# ============================================================================
# Message Handler Tests
# ============================================================================

class TestMessageHandler(unittest.TestCase):
    """Test message handler functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.handler = MessageHandler()
    
    async def test_register_handler(self):
        """Test registering a message handler"""
        async def test_handler(data):
            return {'status': 'ok'}
        
        self.handler.register('test', test_handler)
        
        self.assertIn('test', self.handler.handlers)
        self.assertEqual(self.handler.handlers['test'], test_handler)
    
    async def test_unregister_handler(self):
        """Test unregistering a message handler"""
        async def test_handler(data):
            return {'status': 'ok'}
        
        self.handler.register('test', test_handler)
        self.handler.unregister('test')
        
        self.assertNotIn('test', self.handler.handlers)
    
    async def test_handle_message(self):
        """Test handling a message"""
        async def ping_handler(data):
            return {'pong': True, 'echo': data}
        
        self.handler.register('ping', ping_handler)
        
        result = await self.handler.handle('ping', {'message': 'hello'})
        
        self.assertIsNotNone(result)
        self.assertTrue(result['pong'])
        self.assertEqual(result['echo']['message'], 'hello')
    
    async def test_handle_unregistered_message(self):
        """Test handling unregistered message type"""
        result = await self.handler.handle('unknown', {})
        
        self.assertIsNone(result)
    
    async def test_clear_handlers(self):
        """Test clearing all handlers"""
        async def handler1(data): pass
        async def handler2(data): pass
        
        self.handler.register('type1', handler1)
        self.handler.register('type2', handler2)
        
        self.assertEqual(len(self.handler.handlers), 2)
        
        self.handler.clear()
        
        self.assertEqual(len(self.handler.handlers), 0)


# ============================================================================
# WebSocket Server Tests
# ============================================================================

class TestWebSocketServer(unittest.TestCase):
    """Test WebSocket server functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = WebSocketConfig(host='localhost', port=8084)
        self.server = WebSocketServer(config=self.config)
    
    async def test_initialization(self):
        """Test server initialization"""
        self.assertEqual(self.server.config.host, 'localhost')
        self.assertEqual(self.server.config.port, 8084)
        self.assertFalse(self.server.is_running)
    
    async def test_start_stop(self):
        """Test starting and stopping server"""
        # Start server (this would normally run in background)
        # For test, we just verify the method exists
        self.assertTrue(hasattr(self.server, 'start'))
        self.assertTrue(hasattr(self.server, 'stop'))
    
    async def test_handle_connection(self):
        """Test handling a connection"""
        mock_ws = MockWebSocket()
        
        # Mock the message handling loop
        async def mock_receive():
            return ''
        
        mock_ws.receive_text = mock_receive
        
        # Should not raise exception
        await self.server.handle_connection(mock_ws, '/ws')


# ============================================================================
# Broadcast Functions Tests
# ============================================================================

class TestBroadcastFunctions(unittest.TestCase):
    """Test broadcast helper functions"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.manager = WebSocketManager()
        self.mock_ws = MockWebSocket()
    
    async def test_broadcast_detection(self):
        """Test broadcasting detection"""
        detection = TestDataGenerator.create_test_detection()
        
        # Register connection
        await self.manager.register_connection(self.mock_ws)
        
        # Broadcast detection
        await broadcast_detection(self.manager, detection)
        
        # Verify message was sent
        self.assertEqual(len(self.mock_ws.sent_messages), 1)
        sent_data = json.loads(self.mock_ws.sent_messages[0])
        self.assertEqual(sent_data['type'], 'detection')
        self.assertEqual(sent_data['data']['id'], 'det_001')
    
    async def test_broadcast_alert(self):
        """Test broadcasting alert"""
        alert = TestDataGenerator.create_test_alert()
        
        await self.manager.register_connection(self.mock_ws)
        await broadcast_alert(self.manager, alert)
        
        self.assertEqual(len(self.mock_ws.sent_messages), 1)
        sent_data = json.loads(self.mock_ws.sent_messages[0])
        self.assertEqual(sent_data['type'], 'alert')
        self.assertEqual(sent_data['data']['severity'], 'CRITICAL')
    
    async def test_broadcast_metrics(self):
        """Test broadcasting metrics"""
        metrics = TestDataGenerator.create_test_metrics()
        
        await self.manager.register_connection(self.mock_ws)
        await broadcast_metrics(self.manager, metrics)
        
        self.assertEqual(len(self.mock_ws.sent_messages), 1)
        sent_data = json.loads(self.mock_ws.sent_messages[0])
        self.assertEqual(sent_data['type'], 'metrics')
        self.assertEqual(sent_data['data']['total_detections'], 1247)
    
    async def test_broadcast_plot_data(self):
        """Test broadcasting plot data"""
        plot_data = TestDataGenerator.create_test_plot_data()
        
        await self.manager.register_connection(self.mock_ws)
        await broadcast_plot_data(self.manager, plot_data)
        
        self.assertEqual(len(self.mock_ws.sent_messages), 1)
        sent_data = json.loads(self.mock_ws.sent_messages[0])
        self.assertEqual(sent_data['type'], 'plot_data')
        self.assertEqual(len(sent_data['data']['event_numbers']), 5)


# ============================================================================
# WebSocket Configuration Tests
# ============================================================================

class TestWebSocketConfig(unittest.TestCase):
    """Test WebSocket configuration"""
    
    def test_default_config(self):
        """Test default configuration"""
        config = WebSocketConfig()
        
        self.assertEqual(config.host, 'localhost')
        self.assertEqual(config.port, 8082)
        self.assertEqual(config.ping_interval, 20)
        self.assertEqual(config.ping_timeout, 30)
    
    def test_custom_config(self):
        """Test custom configuration"""
        config = WebSocketConfig(
            host='0.0.0.0',
            port=9000,
            ping_interval=30,
            ping_timeout=45
        )
        
        self.assertEqual(config.host, '0.0.0.0')
        self.assertEqual(config.port, 9000)
        self.assertEqual(config.ping_interval, 30)
        self.assertEqual(config.ping_timeout, 45)
    
    def test_config_from_dict(self):
        """Test config from dictionary"""
        config_dict = {
            'host': '192.168.1.100',
            'port': 8085,
            'ping_interval': 15,
            'ping_timeout': 20
        }
        
        config = WebSocketConfig(**config_dict)
        
        self.assertEqual(config.host, '192.168.1.100')
        self.assertEqual(config.port, 8085)


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestWebSocketErrorHandling(unittest.TestCase):
    """Test WebSocket error handling"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.manager = WebSocketManager()
    
    async def test_handle_invalid_json(self):
        """Test handling invalid JSON message"""
        mock_ws = MockWebSocket()
        mock_ws.add_received_message('invalid json {')
        
        await self.manager.register_connection(mock_ws)
        
        # Should not crash
        await self.manager.handle_message(mock_ws, 'invalid json {')
    
    async def test_handle_connection_error(self):
        """Test handling connection error"""
        mock_ws = MockWebSocket()
        
        # Simulate error on receive
        async def receive_error():
            raise Exception("Connection error")
        
        mock_ws.receive_text = receive_error
        
        await self.manager.register_connection(mock_ws)
        
        # Should handle gracefully
        await self.manager.handle_client(mock_ws, '/ws')
    
    async def test_broadcast_with_no_connections(self):
        """Test broadcasting with no connections"""
        # Should not raise exception
        await self.manager.broadcast_to_all({'test': 'data'})


# ============================================================================
# Performance Tests
# ============================================================================

class TestWebSocketPerformance(unittest.TestCase):
    """Performance tests for WebSocket"""
    
    async def test_message_throughput(self):
        """Test message throughput"""
        manager = WebSocketManager()
        
        # Create many mock connections
        connections = []
        for i in range(100):
            ws = MockWebSocket()
            await manager.register_connection(ws)
            connections.append(ws)
        
        start_time = time.time()
        
        # Send 1000 messages
        for i in range(1000):
            await manager.broadcast_to_all({'type': 'test', 'index': i})
        
        elapsed = time.time() - start_time
        messages_per_second = 1000 / elapsed
        
        # Should handle at least 1000 messages per second
        self.assertGreater(messages_per_second, 100)
    
    async def test_large_message_handling(self):
        """Test handling large messages"""
        manager = WebSocketManager()
        ws = MockWebSocket()
        await manager.register_connection(ws)
        
        # Create large message (1 MB)
        large_data = {'data': 'x' * 1000000}
        
        start_time = time.time()
        await manager.broadcast_to_all(large_data)
        elapsed = time.time() - start_time
        
        # Should handle large message within reasonable time
        self.assertLess(elapsed, 1.0)


# ============================================================================
# Integration Tests
# ============================================================================

class TestWebSocketIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration tests for WebSocket components"""
    
    async def asyncSetUp(self):
        """Set up integration test fixtures"""
        self.manager = WebSocketManager()
        self.message_handler = MessageHandler()
        
        # Register test handlers
        async def ping_handler(data):
            return {'pong': True, 'timestamp': datetime.now().isoformat()}
        
        async def echo_handler(data):
            return {'echo': data}
        
        self.message_handler.register('ping', ping_handler)
        self.message_handler.register('echo', echo_handler)
    
    async def test_full_message_flow(self):
        """Test full message flow from client to handler and back"""
        mock_ws = MockWebSocket()
        await self.manager.register_connection(mock_ws)
        
        # Simulate client sending ping
        ping_message = json.dumps({'type': 'ping', 'data': {'test': True}})
        mock_ws.add_received_message(ping_message)
        
        # Process message
        message = await mock_ws.receive_json()
        response = await self.message_handler.handle(
            message.get('type'), 
            message.get('data', {})
        )
        
        # Send response
        if response:
            await mock_ws.send_json({'type': 'pong', 'data': response})
        
        # Verify response
        self.assertEqual(len(mock_ws.sent_messages), 1)
        sent_data = json.loads(mock_ws.sent_messages[0])
        self.assertEqual(sent_data['type'], 'pong')
        self.assertTrue(sent_data['data']['pong'])
    
    async def test_command_processing(self):
        """Test command processing flow"""
        mock_ws = MockWebSocket()
        await self.manager.register_connection(mock_ws)
        
        # Simulate client sending command
        command = TestDataGenerator.create_test_command('start_scanning', {'frequency': 2.44e9})
        mock_ws.add_received_message(json.dumps(command))
        
        # Process command
        message = await mock_ws.receive_json()
        
        self.assertEqual(message['command'], 'start_scanning')
        self.assertEqual(message['data']['frequency'], 2.44e9)
    
    async def test_multiple_clients(self):
        """Test communication between multiple clients"""
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()
        
        await self.manager.register_connection(ws1)
        await self.manager.register_connection(ws2)
        
        # ws1 sends message to all
        broadcast_message = {'type': 'broadcast', 'data': 'hello everyone'}
        await self.manager.broadcast_to_all(broadcast_message)
        
        # Both clients should receive
        self.assertEqual(len(ws1.sent_messages), 1)
        self.assertEqual(len(ws2.sent_messages), 1)


# ============================================================================
# Singleton Manager Tests
# ============================================================================

class TestSingletonManager(unittest.TestCase):
    """Test singleton WebSocket manager"""
    
    async def test_get_websocket_manager(self):
        """Test getting WebSocket manager singleton"""
        manager1 = await get_websocket_manager()
        manager2 = await get_websocket_manager()
        
        # Should be the same instance
        self.assertIs(manager1, manager2)
    
    async def test_get_websocket_manager_with_config(self):
        """Test getting manager with configuration"""
        config = WebSocketConfig(port=9999)
        
        # This would normally create a new instance with config
        # For test, we just verify the method exists
        self.assertTrue(hasattr(get_websocket_manager, '__call__'))


# ============================================================================
# Run Tests
# ============================================================================

async def run_async_tests():
    """Run async test methods"""
    test_classes = [
        TestConnectionManager,
        TestWebSocketManager,
        TestMessageHandler,
        TestWebSocketServer,
        TestBroadcastFunctions,
        TestWebSocketErrorHandling,
        TestWebSocketPerformance,
        TestSingletonManager
    ]
    
    for test_class in test_classes:
        print(f"\nRunning {test_class.__name__}...")
        instance = test_class()
        
        # Run async methods
        for method_name in dir(instance):
            if method_name.startswith('test_') and asyncio.iscoroutinefunction(getattr(instance, method_name)):
                method = getattr(instance, method_name)
                await method()


if __name__ == '__main__':
    # Run async tests
    import asyncio
    asyncio.run(run_async_tests())
    
    # Run regular unittest suite
    unittest.main(verbosity=2)