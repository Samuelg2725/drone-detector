#!/usr/bin/env python3
# drone-detector/infrastructure/messaging/mqtt_client.py
"""
MQTT Client Integration

This module provides MQTT (Message Queuing Telemetry Transport) integration 
for the Drone Detection System, enabling:
- Real-time detection publishing to MQTT brokers
- Remote command reception via MQTT
- Alert distribution over MQTT
- Status reporting and telemetry
- Integration with IoT platforms (Home Assistant, Node-RED, etc.)
- Multi-broker support for redundancy
- QoS management for reliable delivery
- TLS/SSL encryption support
- Last Will and Testament (LWT) for connection monitoring
"""

import asyncio
import json
import ssl
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional, Callable, Union, Tuple
from collections import deque

import paho.mqtt.client as mqtt
from paho.mqtt.properties import Properties
from paho.mqtt.packettypes import PacketTypes

# Setup logging
import logging
logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Constants
# ============================================================================

class MQTTQoS(Enum):
    """MQTT Quality of Service levels"""
    AT_MOST_ONCE = 0    # Fire and forget
    AT_LEAST_ONCE = 1   # Acknowledged delivery
    EXACTLY_ONCE = 2    # Guaranteed delivery (two-phase handshake)


class MQTTConnectionState(Enum):
    """MQTT connection states"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


class MQTTMessageType(Enum):
    """Types of messages published"""
    DETECTION = "detection"
    ALERT = "alert"
    STATUS = "status"
    METRICS = "metrics"
    TELEMETRY = "telemetry"
    SPECTRUM = "spectrum"
    COMMAND_RESPONSE = "command_response"
    CONFIG = "config"
    HEARTBEAT = "heartbeat"


@dataclass
class MQTTConfig:
    """MQTT client configuration"""
    # Connection settings
    broker_host: str = "localhost"
    broker_port: int = 1883
    client_id: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    
    # TLS settings
    use_tls: bool = False
    tls_ca_cert: Optional[str] = None
    tls_client_cert: Optional[str] = None
    tls_client_key: Optional[str] = None
    tls_insecure: bool = False
    
    # MQTT settings
    keepalive: int = 60
    clean_session: bool = True
    qos: MQTTQoS = MQTTQoS.AT_LEAST_ONCE
    retain: bool = False
    
    # Topic configuration
    base_topic: str = "drone-detector"
    detection_topic: str = "detections"
    alert_topic: str = "alerts"
    status_topic: str = "status"
    command_topic: str = "commands"
    telemetry_topic: str = "telemetry"
    spectrum_topic: str = "spectrum"
    
    # Advanced settings
    max_inflight_messages: int = 20
    max_queued_messages: int = 1000
    message_retry_seconds: int = 5
    reconnect_delay_min: int = 1
    reconnect_delay_max: int = 120
    reconnect_backoff_factor: float = 2.0
    
    # Last Will and Testament
    lwt_topic: str = "status"
    lwt_payload: str = "offline"
    lwt_qos: MQTTQoS = MQTTQoS.AT_LEAST_ONCE
    lwt_retain: bool = True
    
    # Heartbeat
    heartbeat_enabled: bool = True
    heartbeat_interval_seconds: int = 30
    heartbeat_topic: str = "heartbeat"
    
    # Remote command settings
    commands_enabled: bool = True
    command_timeout_seconds: int = 30
    
    # Buffer settings
    offline_buffer_enabled: bool = True
    offline_buffer_size: int = 1000
    
    def get_client_id(self) -> str:
        """Get or generate client ID"""
        if self.client_id:
            return self.client_id
        return f"drone-detector-{uuid.uuid4().hex[:8]}"
    
    def get_full_topic(self, topic: str) -> str:
        """Get full topic with base prefix"""
        if topic.startswith("/"):
            return f"{self.base_topic}{topic}"
        return f"{self.base_topic}/{topic}"


@dataclass
class MQTTMessage:
    """MQTT message wrapper"""
    topic: str
    payload: Any
    qos: MQTTQoS = MQTTQoS.AT_LEAST_ONCE
    retain: bool = False
    message_type: MQTTMessageType = MQTTMessageType.STATUS
    timestamp: datetime = field(default_factory=datetime.now)
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def to_json(self) -> str:
        """Convert payload to JSON string"""
        if isinstance(self.payload, (dict, list)):
            return json.dumps(self.payload)
        return str(self.payload)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'message_id': self.message_id,
            'topic': self.topic,
            'payload': self.payload if isinstance(self.payload, (dict, list)) else str(self.payload),
            'qos': self.qos.value,
            'retain': self.retain,
            'type': self.message_type.value,
            'timestamp': self.timestamp.isoformat()
        }


# ============================================================================
# MQTT Client
# ============================================================================

class MQTTClient:
    """
    MQTT client for Drone Detection System
    
    Features:
    - Automatic reconnection
    - Message queuing during disconnection
    - TLS/SSL encryption
    - Multiple QoS levels
    - Message buffering and persistence
    - Command handling
    - Heartbeat monitoring
    """
    
    def __init__(self, config: MQTTConfig):
        """
        Initialize MQTT client
        
        Args:
            config: MQTT configuration
        """
        self.config = config
        self.client = None
        self.state = MQTTConnectionState.DISCONNECTED
        self._running = False
        self._message_queue = deque(maxlen=config.offline_buffer_size)
        self._message_callbacks: Dict[str, List[Callable]] = {}
        self._command_handlers: Dict[str, Callable] = {}
        self._command_responses: Dict[str, asyncio.Future] = {}
        self._loop = None
        self._thread = None
        self._heartbeat_task = None
        self._reconnect_delay = config.reconnect_delay_min
        
        # Statistics
        self.stats = {
            'messages_sent': 0,
            'messages_received': 0,
            'messages_queued': 0,
            'connection_attempts': 0,
            'connection_errors': 0,
            'reconnections': 0,
            'last_message_time': None,
            'last_connection_time': None
        }
        
        logger.info(f"MQTT client initialized for broker: {config.broker_host}:{config.broker_port}")
    
    def connect(self) -> bool:
        """
        Connect to MQTT broker
        
        Returns:
            True if connection successful
        """
        self._running = True
        self._loop = asyncio.new_event_loop()
        
        # Start client in separate thread
        self._thread = threading.Thread(target=self._run_client, daemon=True)
        self._thread.start()
        
        # Wait for connection
        timeout = 10
        start_time = time.time()
        while self.state != MQTTConnectionState.CONNECTED and (time.time() - start_time) < timeout:
            time.sleep(0.1)
        
        return self.state == MQTTConnectionState.CONNECTED
    
    def _run_client(self):
        """Run MQTT client in thread"""
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._async_connect())
        self._loop.run_forever()
    
    async def _async_connect(self):
        """Async connection establishment"""
        self._init_client()
        
        # Connect with auto-reconnect
        while self._running:
            try:
                self.state = MQTTConnectionState.CONNECTING
                self.stats['connection_attempts'] += 1
                
                # Connect to broker
                if self.config.use_tls:
                    self.client.tls_set(
                        ca_certs=self.config.tls_ca_cert,
                        certfile=self.config.tls_client_cert,
                        keyfile=self.config.tls_client_key,
                        cert_reqs=ssl.CERT_REQUIRED
                    )
                    if self.config.tls_insecure:
                        self.client.tls_insecure_set(True)
                
                self.client.connect(
                    self.config.broker_host,
                    self.config.broker_port,
                    self.config.keepalive
                )
                
                # Start network loop
                self.client.loop_start()
                
                # Wait for connection
                await asyncio.sleep(1)
                
                if self.state == MQTTConnectionState.CONNECTED:
                    logger.info(f"Connected to MQTT broker at {self.config.broker_host}:{self.config.broker_port}")
                    self._reconnect_delay = self.config.reconnect_delay_min
                    self.stats['last_connection_time'] = datetime.now()
                    
                    # Start heartbeat
                    if self.config.heartbeat_enabled:
                        self._start_heartbeat()
                    
                    # Publish queued messages
                    await self._publish_queued_messages()
                    
                    # Wait for disconnection
                    while self.state == MQTTConnectionState.CONNECTED and self._running:
                        await asyncio.sleep(1)
                
            except Exception as e:
                self.state = MQTTConnectionState.ERROR
                self.stats['connection_errors'] += 1
                logger.error(f"MQTT connection error: {e}")
                
                # Wait before reconnecting
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(
                    self._reconnect_delay * self.config.reconnect_backoff_factor,
                    self.config.reconnect_delay_max
                )
                self.stats['reconnections'] += 1
    
    def _init_client(self):
        """Initialize Paho MQTT client"""
        properties = Properties(PacketTypes.CONNECT)
        properties.SessionExpiryInterval = 3600 if self.config.clean_session else 0xFFFFFFFF
        
        self.client = mqtt.Client(
            client_id=self.config.get_client_id(),
            clean_session=self.config.clean_session,
            protocol=mqtt.MQTTv5,
            properties=properties
        )
        
        # Set credentials
        if self.config.username and self.config.password:
            self.client.username_pw_set(self.config.username, self.config.password)
        
        # Set callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.on_publish = self._on_publish
        self.client.on_log = self._on_log
        
        # Set LWT
        self.client.will_set(
            topic=self.config.get_full_topic(self.config.lwt_topic),
            payload=self.config.lwt_payload,
            qos=self.config.lwt_qos.value,
            retain=self.config.lwt_retain
        )
        
        # Configure message handling
        self.client.max_inflight_messages_set(self.config.max_inflight_messages)
        self.client.message_retry_set(self.config.message_retry_seconds)
    
    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """MQTT connection callback"""
        if rc == 0:
            self.state = MQTTConnectionState.CONNECTED
            logger.info(f"MQTT connected successfully (rc={rc})")
            
            # Subscribe to command topic if enabled
            if self.config.commands_enabled:
                command_topic = self.config.get_full_topic(f"{self.config.command_topic}/+")
                self.client.subscribe(command_topic, qos=self.config.qos.value)
                logger.info(f"Subscribed to commands: {command_topic}")
            
            # Subscribe to status requests
            status_topic = self.config.get_full_topic(f"{self.config.status_topic}/get")
            self.client.subscribe(status_topic, qos=self.config.qos.value)
            
            # Publish online status
            self._publish_status("online")
            
        else:
            self.state = MQTTConnectionState.ERROR
            error_messages = {
                1: "Connection refused - incorrect protocol version",
                2: "Connection refused - invalid client identifier",
                3: "Connection refused - server unavailable",
                4: "Connection refused - bad username or password",
                5: "Connection refused - not authorized"
            }
            logger.error(f"MQTT connection failed: {error_messages.get(rc, f'Unknown error {rc}')}")
    
    def _on_disconnect(self, client, userdata, rc, properties=None):
        """MQTT disconnection callback"""
        self.state = MQTTConnectionState.DISCONNECTED
        logger.warning(f"MQTT disconnected (rc={rc})")
        
        # Stop heartbeat
        self._stop_heartbeat()
    
    def _on_message(self, client, userdata, msg):
        """MQTT message callback"""
        try:
            self.stats['messages_received'] += 1
            self.stats['last_message_time'] = datetime.now()
            
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            
            # Parse JSON payload
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                data = payload
            
            # Extract command from topic
            base_topic = self.config.base_topic
            if topic.startswith(base_topic):
                relative_topic = topic[len(base_topic):].strip('/')
                
                # Handle commands
                if relative_topic.startswith(self.config.command_topic):
                    command_parts = relative_topic.split('/')
                    if len(command_parts) >= 2:
                        command = command_parts[1]
                        command_id = data.get('command_id') if isinstance(data, dict) else None
                        
                        # Process command
                        if command in self._command_handlers:
                            logger.info(f"Processing command: {command}")
                            response = self._command_handlers[command](data)
                            
                            # Send response if requested
                            if command_id and response:
                                response_topic = f"{self.config.base_topic}/{self.config.command_topic}/response/{command_id}"
                                self.publish(response_topic, response, MQTTMessageType.COMMAND_RESPONSE)
                        else:
                            logger.warning(f"Unknown command: {command}")
                
                # Handle status requests
                elif relative_topic == f"{self.config.status_topic}/get":
                    self._publish_status("ok")
            
            # Trigger callbacks
            for pattern, callbacks in self._message_callbacks.items():
                if self._topic_matches(pattern, topic):
                    for callback in callbacks:
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                asyncio.create_task(callback(topic, data))
                            else:
                                callback(topic, data)
                        except Exception as e:
                            logger.error(f"Callback error: {e}")
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def _on_publish(self, client, userdata, mid):
        """MQTT publish callback"""
        self.stats['messages_sent'] += 1
        logger.debug(f"Message published (mid={mid})")
    
    def _on_log(self, client, userdata, level, buf):
        """MQTT log callback"""
        if level >= mqtt.MQTT_LOG_WARNING:
            logger.debug(f"MQTT: {buf}")
    
    def _topic_matches(self, pattern: str, topic: str) -> bool:
        """Check if topic matches pattern with wildcards"""
        pattern_parts = pattern.split('/')
        topic_parts = topic.split('/')
        
        if len(pattern_parts) != len(topic_parts) and '+' not in pattern and '#' not in pattern:
            return False
        
        for p, t in zip(pattern_parts, topic_parts):
            if p == '+':
                continue
            elif p == '#':
                return True
            elif p != t:
                return False
        
        return len(pattern_parts) == len(topic_parts)
    
    async def _publish_queued_messages(self):
        """Publish messages queued during disconnection"""
        if not self.config.offline_buffer_enabled:
            return
        
        while self._message_queue and self.state == MQTTConnectionState.CONNECTED:
            message = self._message_queue.popleft()
            self.stats['messages_queued'] -= 1
            await self._publish_async(message)
    
    async def _publish_async(self, message: MQTTMessage) -> bool:
        """Async publish message"""
        if not self.client or self.state != MQTTConnectionState.CONNECTED:
            # Queue for later
            if self.config.offline_buffer_enabled and len(self._message_queue) < self.config.offline_buffer_size:
                self._message_queue.append(message)
                self.stats['messages_queued'] += 1
                logger.debug(f"Message queued (queue size: {len(self._message_queue)})")
            return False
        
        try:
            payload = message.to_json()
            qos = message.qos.value if message.qos else self.config.qos.value
            
            result = self.client.publish(
                topic=message.topic,
                payload=payload,
                qos=qos,
                retain=message.retain
            )
            
            logger.debug(f"Published to {message.topic}: {payload[:100]}...")
            return result.rc == mqtt.MQTT_ERR_SUCCESS
            
        except Exception as e:
            logger.error(f"Publish error: {e}")
            return False
    
    def _publish_status(self, status: str):
        """Publish system status"""
        status_message = MQTTMessage(
            topic=self.config.get_full_topic(self.config.status_topic),
            payload={
                'status': status,
                'state': self.state.value,
                'client_id': self.config.get_client_id(),
                'uptime': time.time() - self.client._last_connection if hasattr(self.client, '_last_connection') else 0,
                'timestamp': datetime.now().isoformat()
            },
            qos=self.config.qos,
            retain=True,
            message_type=MQTTMessageType.STATUS
        )
        self._loop.create_task(self._publish_async(status_message))
    
    def _start_heartbeat(self):
        """Start heartbeat task"""
        async def heartbeat_loop():
            while self.state == MQTTConnectionState.CONNECTED and self._running:
                await asyncio.sleep(self.config.heartbeat_interval_seconds)
                
                heartbeat = MQTTMessage(
                    topic=self.config.get_full_topic(self.config.heartbeat_topic),
                    payload={
                        'timestamp': datetime.now().isoformat(),
                        'client_id': self.config.get_client_id()
                    },
                    qos=MQTTQoS.AT_MOST_ONCE,
                    retain=False,
                    message_type=MQTTMessageType.HEARTBEAT
                )
                await self._publish_async(heartbeat)
        
        self._heartbeat_task = asyncio.create_task(heartbeat_loop())
    
    def _stop_heartbeat(self):
        """Stop heartbeat task"""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None
    
    # ========================================================================
    # Public API
    # ========================================================================
    
    def publish_detection(self, detection_data: Dict[str, Any], 
                          drone_id: Optional[str] = None) -> bool:
        """
        Publish drone detection
        
        Args:
            detection_data: Detection information
            drone_id: Optional drone identifier
            
        Returns:
            True if published successfully
        """
        topic = self.config.get_full_topic(self.config.detection_topic)
        if drone_id:
            topic = f"{topic}/{drone_id}"
        
        message = MQTTMessage(
            topic=topic,
            payload={
                'type': 'detection',
                'data': detection_data,
                'timestamp': datetime.now().isoformat()
            },
            qos=self.config.qos,
            message_type=MQTTMessageType.DETECTION
        )
        
        return self._loop.create_task(self._publish_async(message)).result() if self._loop else False
    
    def publish_alert(self, alert_data: Dict[str, Any]) -> bool:
        """
        Publish alert
        
        Args:
            alert_data: Alert information
            
        Returns:
            True if published successfully
        """
        message = MQTTMessage(
            topic=self.config.get_full_topic(self.config.alert_topic),
            payload={
                'type': 'alert',
                'data': alert_data,
                'timestamp': datetime.now().isoformat()
            },
            qos=MQTTQoS.EXACTLY_ONCE,  # Alerts need guaranteed delivery
            message_type=MQTTMessageType.ALERT
        )
        
        return self._loop.create_task(self._publish_async(message)).result() if self._loop else False
    
    def publish_metrics(self, metrics_data: Dict[str, Any]) -> bool:
        """
        Publish system metrics
        
        Args:
            metrics_data: Metrics information
            
        Returns:
            True if published successfully
        """
        message = MQTTMessage(
            topic=self.config.get_full_topic("metrics"),
            payload={
                'type': 'metrics',
                'data': metrics_data,
                'timestamp': datetime.now().isoformat()
            },
            qos=MQTTQoS.AT_MOST_ONCE,
            message_type=MQTTMessageType.METRICS
        )
        
        return self._loop.create_task(self._publish_async(message)).result() if self._loop else False
    
    def publish_telemetry(self, telemetry_data: Dict[str, Any]) -> bool:
        """
        Publish telemetry data
        
        Args:
            telemetry_data: Telemetry information
            
        Returns:
            True if published successfully
        """
        message = MQTTMessage(
            topic=self.config.get_full_topic(self.config.telemetry_topic),
            payload={
                'type': 'telemetry',
                'data': telemetry_data,
                'timestamp': datetime.now().isoformat()
            },
            qos=MQTTQoS.AT_LEAST_ONCE,
            message_type=MQTTMessageType.TELEMETRY
        )
        
        return self._loop.create_task(self._publish_async(message)).result() if self._loop else False
    
    def publish_spectrum(self, spectrum_data: Dict[str, Any]) -> bool:
        """
        Publish spectrum data
        
        Args:
            spectrum_data: Spectrum information
            
        Returns:
            True if published successfully
        """
        message = MQTTMessage(
            topic=self.config.get_full_topic(self.config.spectrum_topic),
            payload={
                'type': 'spectrum',
                'data': spectrum_data,
                'timestamp': datetime.now().isoformat()
            },
            qos=MQTTQoS.AT_MOST_ONCE,
            message_type=MQTTMessageType.SPECTRUM
        )
        
        return self._loop.create_task(self._publish_async(message)).result() if self._loop else False
    
    def register_command_handler(self, command: str, handler: Callable) -> None:
        """
        Register a command handler
        
        Args:
            command: Command name
            handler: Handler function
        """
        self._command_handlers[command] = handler
        logger.info(f"Registered command handler: {command}")
    
    def register_message_callback(self, topic_pattern: str, callback: Callable) -> None:
        """
        Register a message callback
        
        Args:
            topic_pattern: Topic pattern (supports + and # wildcards)
            callback: Callback function
        """
        if topic_pattern not in self._message_callbacks:
            self._message_callbacks[topic_pattern] = []
        self._message_callbacks[topic_pattern].append(callback)
    
    def send_command(self, command: str, params: Dict[str, Any] = None,
                     target: str = "system", timeout: float = None) -> Optional[Dict[str, Any]]:
        """
        Send command to remote system and wait for response
        
        Args:
            command: Command name
            params: Command parameters
            target: Target system
            timeout: Response timeout (defaults to config.command_timeout_seconds)
            
        Returns:
            Response data or None if timeout
        """
        if not self._loop:
            logger.error("MQTT client not connected")
            return None
        
        command_id = str(uuid.uuid4())
        command_topic = f"{self.config.base_topic}/{self.config.command_topic}/{target}/{command}"
        
        command_data = {
            'command': command,
            'command_id': command_id,
            'params': params or {},
            'source': self.config.get_client_id(),
            'timestamp': datetime.now().isoformat()
        }
        
        # Create future for response
        loop = asyncio.new_event_loop()
        future = loop.create_future()
        self._command_responses[command_id] = future
        
        # Publish command
        message = MQTTMessage(
            topic=command_topic,
            payload=command_data,
            qos=MQTTQoS.AT_LEAST_ONCE,
            message_type=MQTTMessageType.STATUS
        )
        
        success = loop.run_until_complete(self._publish_async(message))
        
        if not success:
            return None
        
        # Wait for response
        timeout = timeout or self.config.command_timeout_seconds
        try:
            response = loop.run_until_complete(asyncio.wait_for(future, timeout))
            return response
        except asyncio.TimeoutError:
            logger.error(f"Command {command} timed out after {timeout}s")
            return None
        finally:
            if command_id in self._command_responses:
                del self._command_responses[command_id]
            loop.close()
    
    def _handle_command_response(self, response_data: Dict[str, Any]):
        """Handle command response"""
        command_id = response_data.get('command_id')
        if command_id and command_id in self._command_responses:
            self._command_responses[command_id].set_result(response_data)
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        self._running = False
        
        if self.client:
            # Publish offline status
            self._publish_status("offline")
            
            # Disconnect
            self.client.loop_stop()
            self.client.disconnect()
        
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        
        if self._thread:
            self._thread.join(timeout=5)
        
        self.state = MQTTConnectionState.DISCONNECTED
        logger.info("MQTT client disconnected")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics"""
        return {
            **self.stats,
            'state': self.state.value,
            'connected': self.state == MQTTConnectionState.CONNECTED,
            'queue_size': len(self._message_queue),
            'client_id': self.config.get_client_id(),
            'broker': f"{self.config.broker_host}:{self.config.broker_port}"
        }


# ============================================================================
# Multi-Broker Client (High Availability)
# ============================================================================

class MQTTMultiBrokerClient:
    """
    MQTT client with multiple broker support for high availability
    
    Features:
    - Automatic failover between brokers
    - Load balancing across brokers
    - Broker health monitoring
    """
    
    def __init__(self, brokers: List[MQTTConfig]):
        """
        Initialize multi-broker client
        
        Args:
            brokers: List of MQTT configurations
        """
        self.brokers = brokers
        self.current_broker_index = 0
        self.client: Optional[MQTTClient] = None
        self._running = False
        self._monitor_task = None
        
        logger.info(f"Multi-broker client initialized with {len(brokers)} brokers")
    
    def connect(self) -> bool:
        """Connect to primary broker"""
        self._running = True
        return self._connect_to_broker(0)
    
    def _connect_to_broker(self, index: int) -> bool:
        """Connect to specific broker"""
        if index >= len(self.brokers):
            logger.error("No brokers available")
            return False
        
        self.current_broker_index = index
        config = self.brokers[index]
        
        logger.info(f"Connecting to broker {index + 1}/{len(self.brokers)}: {config.broker_host}")
        
        # Close existing client
        if self.client:
            self.client.disconnect()
        
        # Create new client
        self.client = MQTTClient(config)
        
        # Start monitoring
        self._start_monitoring()
        
        return self.client.connect()
    
    def _start_monitoring(self):
        """Start broker health monitoring"""
        async def monitor_loop():
            while self._running:
                await asyncio.sleep(5)
                
                if self.client and self.client.state != MQTTConnectionState.CONNECTED:
                    logger.warning(f"Broker {self.current_broker_index + 1} disconnected")
                    # Try next broker
                    next_index = (self.current_broker_index + 1) % len(self.brokers)
                    self._connect_to_broker(next_index)
        
        asyncio.create_task(monitor_loop())
    
    def get_client(self) -> Optional[MQTTClient]:
        """Get current active MQTT client"""
        return self.client
    
    def disconnect(self):
        """Disconnect all brokers"""
        self._running = False
        if self.client:
            self.client.disconnect()


# ============================================================================
# Factory Functions
# ============================================================================

def create_default_mqtt_client(broker_host: str = "localhost",
                                broker_port: int = 1883,
                                username: Optional[str] = None,
                                password: Optional[str] = None) -> MQTTClient:
    """
    Create default MQTT client
    
    Args:
        broker_host: MQTT broker hostname
        broker_port: MQTT broker port
        username: Username (optional)
        password: Password (optional)
    
    Returns:
        Configured MQTT client
    """
    config = MQTTConfig(
        broker_host=broker_host,
        broker_port=broker_port,
        username=username,
        password=password,
        base_topic="drone-detector"
    )
    
    return MQTTClient(config)


def create_tls_mqtt_client(broker_host: str = "localhost",
                           broker_port: int = 8883,
                           ca_cert: str = "ca.crt",
                           client_cert: str = "client.crt",
                           client_key: str = "client.key") -> MQTTClient:
    """
    Create TLS-enabled MQTT client
    
    Args:
        broker_host: MQTT broker hostname
        broker_port: MQTT broker port (default 8883)
        ca_cert: CA certificate path
        client_cert: Client certificate path
        client_key: Client key path
    
    Returns:
        Configured MQTT client with TLS
    """
    config = MQTTConfig(
        broker_host=broker_host,
        broker_port=broker_port,
        use_tls=True,
        tls_ca_cert=ca_cert,
        tls_client_cert=client_cert,
        tls_client_key=client_key,
        base_topic="drone-detector"
    )
    
    return MQTTClient(config)


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    """Test MQTT client"""
    
    print("MQTT Client Test")
    print("=" * 50)
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Create MQTT client
    client = create_default_mqtt_client("localhost", 1883)
    
    # Register command handler
    def handle_status_command(data: Dict[str, Any]) -> Dict[str, Any]:
        print(f"Received status command: {data}")
        return {"status": "ok", "version": "2.0.0"}
    
    client.register_command_handler("status", handle_status_command)
    
    # Register message callback
    def on_detection(topic: str, data: Dict[str, Any]):
        print(f"Detection received: {data.get('data', {}).get('drone_type', 'Unknown')}")
    
    client.register_message_callback("drone-detector/detections/+", on_detection)
    
    # Connect to broker
    print("\n1. Connecting to MQTT broker...")
    if client.connect():
        print("   Connected successfully!")
    else:
        print("   Failed to connect!")
        exit(1)
    
    # Publish test detections
    print("\n2. Publishing test detections...")
    
    test_detection = {
        'drone_id': 'test_drone_001',
        'drone_type': 'DJI Mavic 3',
        'confidence': 0.95,
        'signal_strength': -45,
        'frequency': 2.44e9,
        'position': [37.7749, -122.4194, 100]
    }
    
    client.publish_detection(test_detection, drone_id='drone_001')
    print("   Detection published")
    
    # Publish alert
    test_alert = {
        'severity': 'critical',
        'message': 'Drone detected in restricted zone',
        'drone_id': 'drone_001'
    }
    
    client.publish_alert(test_alert)
    print("   Alert published")
    
    # Publish metrics
    test_metrics = {
        'detections_per_minute': 15,
        'average_confidence': 0.87,
        'active_threats': 2
    }
    
    client.publish_metrics(test_metrics)
    print("   Metrics published")
    
    # Send command
    print("\n3. Sending command...")
    response = client.send_command("status", {"verbose": True}, timeout=5)
    if response:
        print(f"   Response: {response}")
    
    # Get stats
    print("\n4. Client Statistics:")
    stats = client.get_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    # Disconnect
    print("\n5. Disconnecting...")
    client.disconnect()
    
    print("\n" + "=" * 50)
    print("MQTT client test complete")