#!/usr/bin/env python3
# drone-detector/infrastructure/messaging/__init__.py
"""
Infrastructure Messaging Module

This module provides messaging infrastructure for the Drone Detection System,
including WebSocket, MQTT, Redis Pub/Sub, and Event Bus capabilities.

The messaging layer handles:
- Real-time communication with web clients (WebSocket)
- IoT integration via MQTT protocol
- High-performance message distribution via Redis Pub/Sub
- Internal event bus for component communication
- Message routing, filtering, and transformation
- Connection management and reconnection handling
"""

from typing import Dict, Any, Optional, List, Callable
from datetime import datetime

# ============================================================================
# WebSocket Server
# ============================================================================

from .websocket_server import (
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
# Event Bus
# ============================================================================

from .event_bus import (
    EventBus,
    Event,
    EventListener,
    EventPriority,
    EventBusConfig,
    get_event_bus,
    create_event,
    subscribe_to_event,
    publish_event
)

# ============================================================================
# MQTT Client
# ============================================================================

from .mqtt_client import (
    MQTTClient,
    MQTTConfig,
    MQTTMessage,
    MQTTQoS,
    MQTTConnectionState,
    MQTTMessageType,
    MQTTMultiBrokerClient,
    RedisChannel as MQTTRedisChannel,  # Alias to avoid confusion
    create_default_mqtt_client,
    create_tls_mqtt_client
)

# ============================================================================
# Redis Pub/Sub
# ============================================================================

from .redis_pubsub import (
    RedisPubSubManager,
    RedisConfig,
    RedisMessage,
    RedisMessagePriority,
    RedisChannel,
    create_redis_manager,
    create_default_redis_manager,
    publish_detection,
    publish_alert,
    publish_position_update,
    publish_system_metrics
)

# ============================================================================
# Version and Metadata
# ============================================================================

__version__ = "2.0.0"
__author__ = "Drone Detection System Team"
__copyright__ = "Copyright 2024-2025, Drone Detection System"
__license__ = "MIT"

# ============================================================================
# Public API - Explicit Exports
# ============================================================================

__all__ = [
    # WebSocket
    "WebSocketServer",
    "WebSocketManager",
    "ConnectionManager",
    "MessageHandler",
    "WebSocketConfig",
    "start_websocket_server",
    "broadcast_detection",
    "broadcast_alert",
    "broadcast_metrics",
    "broadcast_plot_data",
    "get_websocket_manager",
    
    # Event Bus
    "EventBus",
    "Event",
    "EventListener",
    "EventPriority",
    "EventBusConfig",
    "get_event_bus",
    "create_event",
    "subscribe_to_event",
    "publish_event",
    
    # MQTT
    "MQTTClient",
    "MQTTConfig",
    "MQTTMessage",
    "MQTTQoS",
    "MQTTConnectionState",
    "MQTTMessageType",
    "MQTTMultiBrokerClient",
    "MQTTRedisChannel",
    "create_default_mqtt_client",
    "create_tls_mqtt_client",
    
    # Redis Pub/Sub
    "RedisPubSubManager",
    "RedisConfig",
    "RedisMessage",
    "RedisMessagePriority",
    "RedisChannel",
    "create_redis_manager",
    "create_default_redis_manager",
    "publish_detection",
    "publish_alert",
    "publish_position_update",
    "publish_system_metrics",
]


# ============================================================================
# Unified Messaging Manager
# ============================================================================

class MessagingManager:
    """
    Unified messaging manager that orchestrates all messaging components
    
    This class provides a single interface for all messaging needs:
    - WebSocket for real-time web clients
    - MQTT for IoT integration
    - Redis Pub/Sub for inter-service communication
    - Event Bus for internal component communication
    """
    
    def __init__(self):
        """Initialize messaging manager"""
        self.websocket_manager: Optional[WebSocketManager] = None
        self.event_bus: Optional[EventBus] = None
        self.mqtt_client: Optional[MQTTClient] = None
        self.redis_manager: Optional[RedisPubSubManager] = None
        
        self._initialized = False
        self._components: Dict[str, Any] = {}
    
    async def initialize(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize all messaging components
        
        Args:
            config: Configuration dictionary for messaging components
        """
        config = config or {}
        
        # Initialize Event Bus (always enabled)
        event_bus_config = config.get('event_bus', {})
        self.event_bus = EventBus(config=EventBusConfig(**event_bus_config))
        self._components['event_bus'] = self.event_bus
        
        # Initialize WebSocket if configured
        if config.get('websocket', {}).get('enabled', True):
            ws_config = config.get('websocket', {})
            from .websocket_server import WebSocketConfig as WSConfig, WebSocketManager
            self.websocket_manager = WebSocketManager(
                config=WSConfig(
                    host=ws_config.get('host', 'localhost'),
                    port=ws_config.get('port', 8082)
                )
            )
            self._components['websocket'] = self.websocket_manager
        
        # Initialize MQTT if configured
        if config.get('mqtt', {}).get('enabled', False):
            mqtt_config_dict = config.get('mqtt', {})
            mqtt_config = MQTTConfig(
                broker_host=mqtt_config_dict.get('host', 'localhost'),
                broker_port=mqtt_config_dict.get('port', 1883),
                username=mqtt_config_dict.get('username'),
                password=mqtt_config_dict.get('password'),
                use_tls=mqtt_config_dict.get('use_tls', False),
                base_topic=mqtt_config_dict.get('base_topic', 'drone-detector')
            )
            self.mqtt_client = MQTTClient(mqtt_config)
            self._components['mqtt'] = self.mqtt_client
        
        # Initialize Redis if configured
        if config.get('redis', {}).get('enabled', False):
            redis_config_dict = config.get('redis', {})
            redis_config = RedisConfig(
                host=redis_config_dict.get('host', 'localhost'),
                port=redis_config_dict.get('port', 6379),
                password=redis_config_dict.get('password'),
                db=redis_config_dict.get('db', 0)
            )
            self.redis_manager = RedisPubSubManager(redis_config)
            await self.redis_manager.connect()
            self._components['redis'] = self.redis_manager
        
        self._initialized = True
        
        # Log initialization
        component_list = ', '.join(self._components.keys())
        print(f"Messaging manager initialized with components: {component_list}")
    
    async def start(self) -> None:
        """Start all messaging components"""
        if not self._initialized:
            raise RuntimeError("Messaging manager not initialized. Call initialize() first.")
        
        # Start WebSocket server
        if self.websocket_manager:
            import asyncio
            asyncio.create_task(self.websocket_manager.start_server())
        
        # Connect MQTT
        if self.mqtt_client:
            self.mqtt_client.connect()
        
        # Event Bus is always ready
        if self.event_bus:
            self.event_bus.start()
        
        print("All messaging components started")
    
    async def stop(self) -> None:
        """Stop all messaging components"""
        # Stop WebSocket
        if self.websocket_manager:
            await self.websocket_manager.stop()
        
        # Disconnect MQTT
        if self.mqtt_client:
            self.mqtt_client.disconnect()
        
        # Disconnect Redis
        if self.redis_manager:
            await self.redis_manager.disconnect()
        
        # Stop Event Bus
        if self.event_bus:
            self.event_bus.stop()
        
        self._initialized = False
        print("All messaging components stopped")
    
    def broadcast_detection(self, detection_data: Dict[str, Any]) -> None:
        """
        Broadcast detection through all enabled channels
        
        Args:
            detection_data: Detection information
        """
        # WebSocket broadcast
        if self.websocket_manager:
            import asyncio
            asyncio.create_task(
                broadcast_detection(self.websocket_manager, detection_data)
            )
        
        # MQTT publish
        if self.mqtt_client:
            self.mqtt_client.publish_detection(detection_data)
        
        # Redis publish
        if self.redis_manager:
            import asyncio
            asyncio.create_task(
                publish_detection(self.redis_manager, detection_data)
            )
        
        # Event Bus
        if self.event_bus:
            self.event_bus.emit(create_event(
                'detection.created',
                detection_data,
                source='messaging_manager'
            ))
    
    def broadcast_alert(self, alert_data: Dict[str, Any]) -> None:
        """
        Broadcast alert through all enabled channels
        
        Args:
            alert_data: Alert information
        """
        # WebSocket broadcast
        if self.websocket_manager:
            import asyncio
            asyncio.create_task(
                broadcast_alert(self.websocket_manager, alert_data)
            )
        
        # MQTT publish
        if self.mqtt_client:
            self.mqtt_client.publish_alert(alert_data)
        
        # Redis publish
        if self.redis_manager:
            import asyncio
            asyncio.create_task(
                publish_alert(self.redis_manager, alert_data)
            )
        
        # Event Bus
        if self.event_bus:
            self.event_bus.emit(create_event(
                'alert.generated',
                alert_data,
                source='messaging_manager'
            ))
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get status of all messaging components
        
        Returns:
            Dictionary with component status
        """
        status = {
            'initialized': self._initialized,
            'components': {}
        }
        
        if self.websocket_manager:
            status['components']['websocket'] = {
                'running': self.websocket_manager._running,
                'connections': len(self.websocket_manager.connections) if hasattr(self.websocket_manager, 'connections') else 0
            }
        
        if self.mqtt_client:
            status['components']['mqtt'] = self.mqtt_client.get_stats()
        
        if self.redis_manager:
            status['components']['redis'] = self.redis_manager.get_stats()
        
        if self.event_bus:
            status['components']['event_bus'] = {
                'listeners': len(self.event_bus._listeners) if hasattr(self.event_bus, '_listeners') else 0
            }
        
        return status


# ============================================================================
# Convenience Functions
# ============================================================================

def get_messaging_info() -> Dict[str, Any]:
    """
    Get information about available messaging components
    
    Returns:
        Dictionary with messaging information
    """
    return {
        "version": __version__,
        "components": {
            "websocket": {
                "description": "WebSocket server for real-time web client communication",
                "features": ["real-time", "bidirectional", "broadcast"]
            },
            "event_bus": {
                "description": "Internal event bus for component communication",
                "features": ["async", "priority", "wildcards"]
            },
            "mqtt": {
                "description": "MQTT client for IoT integration",
                "features": ["QoS", "TLS", "auto-reconnect", "command-response"]
            },
            "redis_pubsub": {
                "description": "Redis Pub/Sub for distributed messaging",
                "features": ["async", "streams", "patterns", "rate-limiting"]
            }
        }
    }


# ============================================================================
# Singleton Manager
# ============================================================================

_default_messaging_manager: Optional[MessagingManager] = None


async def get_messaging_manager(config: Optional[Dict[str, Any]] = None) -> MessagingManager:
    """
    Get or create the default messaging manager singleton
    
    Args:
        config: Optional configuration for initialization
        
    Returns:
        MessagingManager instance
    """
    global _default_messaging_manager
    
    if _default_messaging_manager is None:
        _default_messaging_manager = MessagingManager()
        await _default_messaging_manager.initialize(config)
        await _default_messaging_manager.start()
    
    return _default_messaging_manager


async def reset_messaging_manager() -> None:
    """Reset the default messaging manager"""
    global _default_messaging_manager
    
    if _default_messaging_manager:
        await _default_messaging_manager.stop()
        _default_messaging_manager = None


# ============================================================================
# Module Documentation
# ============================================================================

__doc__ = """
Infrastructure Messaging Package
================================

This package provides messaging infrastructure for the Drone Detection System.

Components:
-----------
1. **WebSocket Server** - Real-time communication with web dashboard
2. **Event Bus** - Internal event-driven architecture
3. **MQTT Client** - IoT platform integration
4. **Redis Pub/Sub** - High-performance distributed messaging

Quick Start:
-----------
```python
from infrastructure.messaging import (
    MessagingManager,
    get_messaging_manager
)

# Method 1: Use unified manager
manager = await get_messaging_manager({
    'websocket': {'enabled': True, 'port': 8082},
    'mqtt': {'enabled': True, 'host': 'mqtt.example.com'},
    'redis': {'enabled': True, 'host': 'localhost'}
})

# Broadcast detection
manager.broadcast_detection({
    'drone_type': 'DJI Mavic 3',
    'confidence': 0.95
})

# Method 2: Use individual components
from infrastructure.messaging import (
    start_websocket_server,
    get_event_bus,
    create_default_mqtt_client
)

# Start WebSocket server
await start_websocket_server(port=8082)

# Use event bus
event_bus = get_event_bus()
event_bus.on('detection', handler_function)

# Use MQTT
mqtt = create_default_mqtt_client('localhost')
mqtt.connect()
mqtt.publish_detection(detection_data)