import asyncio
import json
import time
from typing import Dict, List, Any
from datetime import datetime
import websockets
from websockets.server import WebSocketServerProtocol

class WebSocketManager:
    def __init__(self):
        self.connections: List[WebSocketServerProtocol] = []
        self.system_state = {
            'state': 'paused',
            'total_detections': 0,
            'true_positives': 0,
            'false_positives': 0,
            'avg_processing_time': 0.0,
            'system_uptime': 0,
            'sensor_uptime': [0, 0, 0, 0]
        }
        self.start_time = time.time()
    
    async def register(self, websocket: WebSocketServerProtocol):
        self.connections.append(websocket)
        print(f"Client connected. Total: {len(self.connections)}")
        
        # Send initial status
        await self.send_metrics(websocket)
    
    async def unregister(self, websocket: WebSocketServerProtocol):
        self.connections.remove(websocket)
        print(f"Client disconnected. Total: {len(self.connections)}")
    
    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast message to all connected clients"""
        if not self.connections:
            return
        
        message_json = json.dumps(message)
        disconnected = []
        
        for websocket in self.connections:
            try:
                await websocket.send(message_json)
            except websockets.exceptions.ConnectionClosed:
                disconnected.append(websocket)
        
        # Clean up disconnected clients
        for websocket in disconnected:
            await self.unregister(websocket)
    
    async def send_metrics(self, websocket: WebSocketServerProtocol = None):
        """Send system metrics to client(s)"""
        message = {
            'type': 'metrics',
            'data': {
                'total_detections': self.system_state['total_detections'],
                'true_positives': self.system_state['true_positives'],
                'false_positives': self.system_state['false_positives'],
                'avg_processing_time': self.system_state['avg_processing_time'],
                'system_uptime': time.time() - self.start_time,
                'sensor_uptime': self.system_state['sensor_uptime']
            },
            'timestamp': datetime.now().isoformat()
        }
        
        if websocket:
            await websocket.send(json.dumps(message))
        else:
            await self.broadcast(message)
    
    async def send_detection(self, detection: Dict[str, Any]):
        """Send new detection to clients"""
        message = {
            'type': 'detection',
            'data': detection,
            'timestamp': datetime.now().isoformat()
        }
        await self.broadcast(message)
        
        # Update metrics
        self.system_state['total_detections'] += 1
        if detection.get('true_positive', True):
            self.system_state['true_positives'] += 1
        else:
            self.system_state['false_positives'] += 1
    
    async def send_alert(self, message: str, level: str = 'warning'):
        """Send alert to clients"""
        alert_msg = {
            'type': 'alert',
            'data': {
                'message': message,
                'level': level,
                'timestamp': datetime.now().isoformat()
            }
        }
        await self.broadcast(alert_msg)
    
    async def send_plot_data(self, event_number: int, confidence: float):
        """Send plot data point to clients"""
        message = {
            'type': 'plot_data',
            'data': {
                'event_numbers': [event_number],
                'confidences': [confidence]
            }
        }
        await self.broadcast(message)
    
    async def handle_command(self, command: str):
        """Handle client commands"""
        if command == 'start':
            self.system_state['state'] = 'running'
            await self.send_alert('System started', 'info')
        elif command == 'stop':
            self.system_state['state'] = 'paused'
            await self.send_alert('System paused', 'info')
        elif command == 'clear_detections':
            self.system_state['total_detections'] = 0
            self.system_state['true_positives'] = 0
            self.system_state['false_positives'] = 0
            await self.send_alert('Detections cleared', 'info')
        
        # Broadcast updated state
        status_msg = {
            'type': 'status',
            'data': {'state': self.system_state['state']}
        }
        await self.broadcast(status_msg)
        await self.send_metrics()

# WebSocket server handler
async def websocket_handler(websocket: WebSocketServerProtocol, path: str):
    manager = WebSocketManager()  # In practice, use a singleton
    
    await manager.register(websocket)
    
    try:
        async for message in websocket:
            # Handle incoming commands
            command = message.strip()
            await manager.handle_command(command)
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        await manager.unregister(websocket)

# Run server
async def start_websocket_server(host='localhost', port=8082):
    async with websockets.serve(websocket_handler, host, port):
        print(f"WebSocket server running on ws://{host}:{port}")
        await asyncio.Future()  # Run forever