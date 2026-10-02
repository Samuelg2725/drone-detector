#!/usr/bin/env python3
# drone-detector/infrastructure/messaging/redis_pubsub.py
"""
Redis Pub/Sub Integration

This module provides Redis Publish/Subscribe functionality for the Drone Detection System,
enabling:
- Real-time message distribution across multiple system instances
- Channel-based communication for different message types
- Pattern-based subscription for flexible routing
- Message queuing and persistence (Streams)
- Distributed state management
- Inter-service communication for microservices architecture
- High-performance message throughput
- Automatic reconnection handling
- Message retention and replay capabilities
"""

import asyncio
import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional, Callable, Union, Set
from collections import deque

import redis.asyncio as redis
import redis.exceptions

# Setup logging
import logging
logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Constants
# ============================================================================

class RedisChannel(Enum):
    """Predefined Redis channels for different message types"""
    # Detection channels
    DETECTION = "drone:detection"
    DETECTION_BULK = "drone:detection:bulk"
    
    # Alert channels
    ALERT = "drone:alert"
    ALERT_CRITICAL = "drone:alert:critical"
    ALERT_ESCALATED = "drone:alert:escalated"
    
    # System channels
    SYSTEM_STATUS = "system:status"
    SYSTEM_METRICS = "system:metrics"
    SYSTEM_HEALTH = "system:health"
    
    # Hardware channels
    HARDWARE_STATE = "hardware:state"
    HARDWARE_COMMAND = "hardware:command"
    
    # Spectrum channels
    SPECTRUM_FFT = "spectrum:fft"
    SPECTRUM_PSD = "spectrum:psd"
    SPECTRUM_WATERFALL = "spectrum:waterfall"
    
    # Position/Tracking channels
    POSITION_UPDATE = "tracking:position"
    TRACKING_COMMAND = "tracking:command"
    
    # Drone-specific channels
    DRONE_DETECTED = "drone:detected"
    DRONE_LOST = "drone:lost"
    DRONE_TRACKING = "drone:tracking"
    
    # Remote ID channels
    REMOTE_ID = "remoteid:data"
    REMOTE_ID_SUMMARY = "remoteid:summary"
    
    # Command and control
    COMMAND = "system:command"
    COMMAND_RESPONSE = "system:command:response"
    
    # Configuration
    CONFIG_UPDATE = "config:update"
    CONFIG_REQUEST = "config:request"


class RedisMessagePriority(Enum):
    """Message priority levels"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class RedisConfig:
    """Redis connection configuration"""
    host: str = "localhost"
    port: int = 6379
    password: Optional[str] = None
    db: int = 0
    ssl: bool = False
    ssl_cert_reqs: str = "required"
    
    # Connection pool settings
    max_connections: int = 50
    socket_timeout: float = 5.0
    socket_connect_timeout: float = 5.0
    retry_on_timeout: bool = True
    
    # Pub/Sub specific
    subscribe_patterns: List[str] = field(default_factory=list)
    channel_prefix: str = "drone"
    
    # Stream settings
    stream_max_len: int = 10000
    stream_approximate: bool = True
    
    # Reconnection settings
    reconnect_attempts: int = 10
    reconnect_backoff_base: float = 1.0
    reconnect_backoff_max: float = 30.0
    
    # Performance
    decode_responses: bool = True
    health_check_interval: int = 30


@dataclass
class RedisMessage:
    """Redis message wrapper"""
    channel: str
    data: Any
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    priority: RedisMessagePriority = RedisMessagePriority.NORMAL
    source: Optional[str] = None
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        payload = {
            'message_id': self.message_id,
            'timestamp': self.timestamp.isoformat(),
            'priority': self.priority.value,
            'data': self.data
        }
        if self.source:
            payload['source'] = self.source
        return json.dumps(payload)
    
    @classmethod
    def from_json(cls, channel: str, json_str: str) -> 'RedisMessage':
        """Create from JSON string"""
        data = json.loads(json_str)
        return cls(
            channel=channel,
            data=data.get('data'),
            message_id=data.get('message_id', str(uuid.uuid4())),
            timestamp=datetime.fromisoformat(data['timestamp']) if 'timestamp' in data else datetime.now(),
            priority=RedisMessagePriority(data.get('priority', 1)),
            source=data.get('source')
        )


# ============================================================================
# Redis Pub/Sub Manager
# ============================================================================

class RedisPubSubManager:
    """
    Redis Publish/Subscribe Manager
    
    Features:
    - Async Pub/Sub with automatic reconnection
    - Pattern-based subscriptions
    - Message queuing during disconnection
    - Channel-based and pattern-based handlers
    - Streams for message persistence
    - Rate limiting per channel
    - Message deduplication
    - Health monitoring
    """
    
    def __init__(self, config: RedisConfig):
        """
        Initialize Redis Pub/Sub manager
        
        Args:
            config: Redis configuration
        """
        self.config = config
        self._redis_client: Optional[redis.Redis] = None
        self._pubsub: Optional[redis.client.PubSub] = None
        self._running = False
        self._message_queue: deque = deque(maxlen=10000)
        self._handlers: Dict[str, List[Callable]] = {}
        self._pattern_handlers: Dict[str, List[Callable]] = {}
        self._stream_handlers: Dict[str, Callable] = {}
        self._subscriptions: Set[str] = set()
        self._pattern_subscriptions: Set[str] = set()
        self._listen_task: Optional[asyncio.Task] = None
        self._health_task: Optional[asyncio.Task] = None
        self._process_queue_task: Optional[asyncio.Task] = None
        
        # Rate limiting
        self._rate_limits: Dict[str, Dict[str, Any]] = {}
        
        # Deduplication
        self._recent_messages: deque = deque(maxlen=1000)
        self._dedup_window_seconds: float = 5.0
        
        # Statistics
        self.stats = {
            'messages_published': 0,
            'messages_received': 0,
            'messages_queued': 0,
            'messages_dropped': 0,
            'connection_attempts': 0,
            'connection_errors': 0,
            'reconnections': 0,
            'last_message_time': None,
            'last_connection_time': None
        }
        
        logger.info(f"Redis Pub/Sub manager initialized for {config.host}:{config.port}")
    
    async def connect(self) -> bool:
        """
        Connect to Redis and start pub/sub
        
        Returns:
            True if connection successful
        """
        self._running = True
        
        # Create connection pool
        try:
            self._redis_client = await redis.Redis(
                host=self.config.host,
                port=self.config.port,
                password=self.config.password,
                db=self.config.db,
                ssl=self.config.ssl,
                decode_responses=self.config.decode_responses,
                max_connections=self.config.max_connections,
                socket_timeout=self.config.socket_timeout,
                socket_connect_timeout=self.config.socket_connect_timeout,
                retry_on_timeout=self.config.retry_on_timeout,
                health_check_interval=self.config.health_check_interval
            )
            
            # Test connection
            await self._redis_client.ping()
            
            # Create pubsub client
            self._pubsub = self._redis_client.pubsub()
            
            # Start listening
            self._listen_task = asyncio.create_task(self._listen_loop())
            self._health_task = asyncio.create_task(self._health_check_loop())
            self._process_queue_task = asyncio.create_task(self._process_message_queue())
            
            self.stats['last_connection_time'] = datetime.now()
            logger.info(f"Connected to Redis at {self.config.host}:{self.config.port}")
            
            # Resubscribe to previous channels
            await self._resubscribe()
            
            return True
            
        except Exception as e:
            self.stats['connection_errors'] += 1
            logger.error(f"Failed to connect to Redis: {e}")
            return False
    
    async def _resubscribe(self):
        """Resubscribe to previous channels after reconnection"""
        if self._subscriptions:
            await self._pubsub.subscribe(*self._subscriptions)
            logger.info(f"Resubscribed to {len(self._subscriptions)} channels")
        
        if self._pattern_subscriptions:
            await self._pubsub.psubscribe(*self._pattern_subscriptions)
            logger.info(f"Resubscribed to {len(self._pattern_subscriptions)} patterns")
    
    async def _listen_loop(self):
        """Main listen loop for pub/sub messages"""
        backoff = 1.0
        
        while self._running:
            try:
                # Get message with timeout
                message = await self._pubsub.get_message(
                    timeout=1.0,
                    ignore_subscribe_messages=True
                )
                
                if message:
                    self.stats['messages_received'] += 1
                    self.stats['last_message_time'] = datetime.now()
                    
                    # Process message
                    await self._process_message(message)
                
                # Reset backoff on successful receive
                backoff = 1.0
                
            except redis.exceptions.ConnectionError as e:
                logger.warning(f"Redis connection lost: {e}")
                self.stats['connection_errors'] += 1
                
                # Attempt reconnection
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
                
                try:
                    await self.reconnect()
                except Exception as reconnect_error:
                    logger.error(f"Reconnection failed: {reconnect_error}")
                    
            except Exception as e:
                logger.error(f"Listen loop error: {e}")
                await asyncio.sleep(0.1)
    
    async def _process_message(self, message: Dict[str, Any]):
        """Process incoming Redis message"""
        channel = message.get('channel')
        data = message.get('data')
        
        if not channel or not data:
            return
        
        # Convert channel from bytes if needed
        if isinstance(channel, bytes):
            channel = channel.decode('utf-8')
        if isinstance(data, bytes):
            data = data.decode('utf-8')
        
        # Try to parse as JSON
        try:
            redis_msg = RedisMessage.from_json(channel, data)
        except (json.JSONDecodeError, KeyError):
            # Raw message
            redis_msg = RedisMessage(channel=channel, data=data)
        
        # Check rate limit
        if not self._check_rate_limit(channel):
            self.stats['messages_dropped'] += 1
            logger.warning(f"Rate limit exceeded for channel: {channel}")
            return
        
        # Check for duplicate
        if self._is_duplicate(redis_msg.message_id, redis_msg.data):
            logger.debug(f"Duplicate message dropped: {redis_msg.message_id}")
            return
        
        # Store for deduplication
        self._add_to_dedup_cache(redis_msg.message_id, redis_msg.data)
        
        # Call exact channel handlers
        if channel in self._handlers:
            for handler in self._handlers[channel]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(channel, redis_msg.data)
                    else:
                        handler(channel, redis_msg.data)
                except Exception as e:
                    logger.error(f"Handler error for channel {channel}: {e}")
        
        # Call pattern handlers
        for pattern, handlers in self._pattern_handlers.items():
            if self._matches_pattern(channel, pattern):
                for handler in handlers:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(channel, redis_msg.data)
                        else:
                            handler(channel, redis_msg.data)
                    except Exception as e:
                        logger.error(f"Pattern handler error for {pattern}: {e}")
    
    async def _process_message_queue(self):
        """Process queued messages when disconnected"""
        while self._running:
            if self._message_queue and self._pubsub and self._pubsub.connection:
                msg = self._message_queue.popleft()
                self.stats['messages_queued'] -= 1
                try:
                    await self._pubsub.publish(msg['channel'], msg['data'])
                    self.stats['messages_published'] += 1
                except Exception as e:
                    logger.error(f"Failed to publish queued message: {e}")
                    # Re-queue
                    self._message_queue.appendleft(msg)
                    self.stats['messages_queued'] += 1
            
            await asyncio.sleep(0.1)
    
    async def _health_check_loop(self):
        """Periodic health check"""
        while self._running:
            await asyncio.sleep(self.config.health_check_interval)
            
            try:
                if self._redis_client:
                    await self._redis_client.ping()
                    logger.debug("Redis health check passed")
            except Exception as e:
                logger.warning(f"Redis health check failed: {e}")
                await self.reconnect()
    
    def _check_rate_limit(self, channel: str) -> bool:
        """Check if channel is rate limited"""
        if channel not in self._rate_limits:
            return True
        
        limit_config = self._rate_limits[channel]
        now = time.time()
        
        # Clean old entries
        limit_config['timestamps'] = [
            ts for ts in limit_config['timestamps']
            if now - ts < limit_config['window']
        ]
        
        if len(limit_config['timestamps']) >= limit_config['max_messages']:
            return False
        
        limit_config['timestamps'].append(now)
        return True
    
    def _is_duplicate(self, message_id: str, data: Any) -> bool:
        """Check if message is a duplicate"""
        for msg_id, msg_data, ts in self._recent_messages:
            if msg_id == message_id:
                return True
            # Check content-based dedup
            if msg_data == data and (datetime.now() - ts).total_seconds() < self._dedup_window_seconds:
                return True
        return False
    
    def _add_to_dedup_cache(self, message_id: str, data: Any):
        """Add message to deduplication cache"""
        self._recent_messages.append((message_id, data, datetime.now()))
    
    def _matches_pattern(self, channel: str, pattern: str) -> bool:
        """Check if channel matches pattern (supports *)"""
        if pattern.endswith('*'):
            return channel.startswith(pattern[:-1])
        return pattern == channel
    
    async def publish(self, channel: Union[RedisChannel, str], 
                     data: Any,
                     priority: RedisMessagePriority = RedisMessagePriority.NORMAL,
                     source: Optional[str] = None) -> bool:
        """
        Publish message to channel
        
        Args:
            channel: Redis channel
            data: Message data
            priority: Message priority
            source: Source identifier
            
        Returns:
            True if published successfully
        """
        channel_str = channel.value if isinstance(channel, RedisChannel) else channel
        
        redis_msg = RedisMessage(
            channel=channel_str,
            data=data,
            priority=priority,
            source=source
        )
        
        json_data = redis_msg.to_json()
        
        try:
            if self._redis_client:
                # Publish with high priority for critical messages
                if priority == RedisMessagePriority.CRITICAL:
                    # Use immediate publish
                    result = await self._redis_client.publish(channel_str, json_data)
                else:
                    # Queue or publish based on connection status
                    if self._pubsub and self._pubsub.connection:
                        result = await self._pubsub.publish(channel_str, json_data)
                    else:
                        # Queue for later
                        self._message_queue.append({
                            'channel': channel_str,
                            'data': json_data
                        })
                        self.stats['messages_queued'] += 1
                        logger.debug(f"Message queued (queue size: {len(self._message_queue)})")
                        return True
                
                self.stats['messages_published'] += 1
                logger.debug(f"Published to {channel_str}: {str(data)[:100]}...")
                return True
                
        except Exception as e:
            logger.error(f"Publish error: {e}")
            # Queue for retry
            self._message_queue.append({
                'channel': channel_str,
                'data': json_data
            })
            self.stats['messages_queued'] += 1
            return False
        
        return False
    
    async def subscribe(self, channel: Union[RedisChannel, str], 
                       handler: Callable) -> None:
        """
        Subscribe to a channel
        
        Args:
            channel: Channel to subscribe to
            handler: Callback function for messages
        """
        channel_str = channel.value if isinstance(channel, RedisChannel) else channel
        
        if channel_str not in self._handlers:
            self._handlers[channel_str] = []
            self._subscriptions.add(channel_str)
            
            if self._pubsub:
                await self._pubsub.subscribe(channel_str)
                logger.info(f"Subscribed to channel: {channel_str}")
        
        self._handlers[channel_str].append(handler)
        logger.debug(f"Added handler for channel: {channel_str}")
    
    async def unsubscribe(self, channel: Union[RedisChannel, str]) -> None:
        """
        Unsubscribe from a channel
        
        Args:
            channel: Channel to unsubscribe from
        """
        channel_str = channel.value if isinstance(channel, RedisChannel) else channel
        
        if channel_str in self._handlers:
            del self._handlers[channel_str]
            self._subscriptions.discard(channel_str)
            
            if self._pubsub:
                await self._pubsub.unsubscribe(channel_str)
                logger.info(f"Unsubscribed from channel: {channel_str}")
    
    async def psubscribe(self, pattern: str, handler: Callable) -> None:
        """
        Subscribe to a pattern
        
        Args:
            pattern: Pattern to subscribe to (supports * wildcard)
            handler: Callback function for messages
        """
        if pattern not in self._pattern_handlers:
            self._pattern_handlers[pattern] = []
            self._pattern_subscriptions.add(pattern)
            
            if self._pubsub:
                await self._pubsub.psubscribe(pattern)
                logger.info(f"Subscribed to pattern: {pattern}")
        
        self._pattern_handlers[pattern].append(handler)
        logger.debug(f"Added handler for pattern: {pattern}")
    
    async def punsubscribe(self, pattern: str) -> None:
        """
        Unsubscribe from a pattern
        
        Args:
            pattern: Pattern to unsubscribe from
        """
        if pattern in self._pattern_handlers:
            del self._pattern_handlers[pattern]
            self._pattern_subscriptions.discard(pattern)
            
            if self._pubsub:
                await self._pubsub.punsubscribe(pattern)
                logger.info(f"Unsubscribed from pattern: {pattern}")
    
    async def add_rate_limit(self, channel: str, max_messages: int, 
                            window_seconds: float) -> None:
        """
        Add rate limit for a channel
        
        Args:
            channel: Channel to rate limit
            max_messages: Maximum messages per window
            window_seconds: Time window in seconds
        """
        self._rate_limits[channel] = {
            'max_messages': max_messages,
            'window': window_seconds,
            'timestamps': []
        }
        logger.info(f"Added rate limit for {channel}: {max_messages}/{window_seconds}s")
    
    async def stream_add(self, stream_key: str, data: Dict[str, Any],
                        max_len: Optional[int] = None) -> Optional[str]:
        """
        Add message to Redis Stream
        
        Args:
            stream_key: Stream key name
            data: Message data
            max_len: Maximum stream length
            
        Returns:
            Message ID or None if failed
        """
        if not self._redis_client:
            return None
        
        try:
            max_len = max_len or self.config.stream_max_len
            
            message_id = await self._redis_client.xadd(
                stream_key,
                data,
                maxlen=max_len,
                approximate=self.config.stream_approximate
            )
            
            logger.debug(f"Added to stream {stream_key}: {message_id}")
            return message_id
            
        except Exception as e:
            logger.error(f"Stream add error: {e}")
            return None
    
    async def stream_read(self, stream_key: str, last_id: str = '0',
                         count: int = 100) -> List[Dict[str, Any]]:
        """
        Read messages from Redis Stream
        
        Args:
            stream_key: Stream key name
            last_id: Last read message ID
            count: Maximum messages to read
            
        Returns:
            List of messages
        """
        if not self._redis_client:
            return []
        
        try:
            result = await self._redis_client.xread(
                {stream_key: last_id},
                count=count,
                block=0
            )
            
            messages = []
            for stream, entries in result:
                for msg_id, data in entries:
                    messages.append({
                        'id': msg_id,
                        'data': data,
                        'stream': stream
                    })
            
            return messages
            
        except Exception as e:
            logger.error(f"Stream read error: {e}")
            return []
    
    async def stream_consumer_group(self, group_name: str, stream_key: str,
                                    consumer_name: str) -> bool:
        """
        Create or join consumer group
        
        Args:
            group_name: Consumer group name
            stream_key: Stream key name
            consumer_name: Consumer name
            
        Returns:
            True if successful
        """
        if not self._redis_client:
            return False
        
        try:
            # Try to create group (ignores if already exists)
            await self._redis_client.xgroup_create(
                stream_key, group_name, id='0', mkstream=True
            )
            logger.info(f"Created consumer group: {group_name}")
        except redis.exceptions.ResponseError as e:
            if 'BUSYGROUP' not in str(e):
                logger.error(f"Consumer group error: {e}")
                return False
        
        # Register consumer
        logger.info(f"Consumer {consumer_name} joined group {group_name}")
        return True
    
    async def stream_claim_pending(self, group_name: str, consumer_name: str,
                                   stream_key: str, min_idle_ms: int = 60000,
                                   count: int = 10) -> List[Dict[str, Any]]:
        """
        Claim pending messages for a consumer
        
        Args:
            group_name: Consumer group name
            consumer_name: Consumer name
            stream_key: Stream key name
            min_idle_ms: Minimum idle time in milliseconds
            count: Maximum messages to claim
            
        Returns:
            List of claimed messages
        """
        if not self._redis_client:
            return []
        
        try:
            result = await self._redis_client.xautoclaim(
                stream_key, group_name, consumer_name,
                min_idle_ms=min_idle_ms, count=count
            )
            
            messages = []
            for msg_id, data in result[1]:
                messages.append({
                    'id': msg_id,
                    'data': data,
                    'stream': stream_key
                })
            
            return messages
            
        except Exception as e:
            logger.error(f"Stream claim error: {e}")
            return []
    
    async def stream_ack(self, stream_key: str, group_name: str, 
                        message_id: str) -> bool:
        """
        Acknowledge message in stream
        
        Args:
            stream_key: Stream key name
            group_name: Consumer group name
            message_id: Message ID to acknowledge
            
        Returns:
            True if successful
        """
        if not self._redis_client:
            return False
        
        try:
            await self._redis_client.xack(stream_key, group_name, message_id)
            logger.debug(f"Acknowledged message {message_id} in {stream_key}")
            return True
        except Exception as e:
            logger.error(f"Stream ack error: {e}")
            return False
    
    async def reconnect(self) -> bool:
        """
        Reconnect to Redis
        
        Returns:
            True if reconnection successful
        """
        self.stats['reconnections'] += 1
        logger.info("Attempting to reconnect to Redis...")
        
        # Close existing connections
        await self._close()
        
        # Attempt to reconnect
        for attempt in range(self.config.reconnect_attempts):
            try:
                self._redis_client = await redis.Redis(
                    host=self.config.host,
                    port=self.config.port,
                    password=self.config.password,
                    db=self.config.db,
                    ssl=self.config.ssl,
                    decode_responses=self.config.decode_responses,
                    max_connections=self.config.max_connections
                )
                
                await self._redis_client.ping()
                
                self._pubsub = self._redis_client.pubsub()
                
                # Resubscribe
                await self._resubscribe()
                
                logger.info("Reconnected to Redis successfully")
                return True
                
            except Exception as e:
                wait = min(
                    self.config.reconnect_backoff_base * (2 ** attempt),
                    self.config.reconnect_backoff_max
                )
                logger.warning(f"Reconnect attempt {attempt + 1} failed: {e}, waiting {wait}s")
                await asyncio.sleep(wait)
        
        logger.error("Failed to reconnect to Redis after all attempts")
        return False
    
    async def _close(self):
        """Close Redis connections"""
        if self._pubsub:
            await self._pubsub.close()
        
        if self._redis_client:
            await self._redis_client.close()
    
    async def disconnect(self):
        """Disconnect from Redis"""
        self._running = False
        
        # Cancel tasks
        if self._listen_task:
            self._listen_task.cancel()
        if self._health_task:
            self._health_task.cancel()
        if self._process_queue_task:
            self._process_queue_task.cancel()
        
        await self._close()
        
        logger.info("Disconnected from Redis")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get manager statistics"""
        return {
            **self.stats,
            'connected': self._redis_client is not None,
            'subscriptions': len(self._subscriptions),
            'pattern_subscriptions': len(self._pattern_subscriptions),
            'handlers': sum(len(h) for h in self._handlers.values()),
            'pattern_handlers': sum(len(h) for h in self._pattern_handlers.values()),
            'queued_messages': len(self._message_queue),
            'rate_limits': len(self._rate_limits),
            'redis_info': {
                'host': self.config.host,
                'port': self.config.port,
                'db': self.config.db
            }
        }


# ============================================================================
# Convenience Functions for Common Operations
# ============================================================================

async def publish_detection(redis_manager: RedisPubSubManager,
                           detection_data: Dict[str, Any],
                           bulk: bool = False) -> bool:
    """
    Publish drone detection
    
    Args:
        redis_manager: RedisPubSubManager instance
        detection_data: Detection data
        bulk: Whether this is a bulk detection
        
    Returns:
        True if published successfully
    """
    channel = RedisChannel.DETECTION_BULK if bulk else RedisChannel.DETECTION
    return await redis_manager.publish(
        channel,
        {
            'type': 'detection',
            'data': detection_data,
            'timestamp': datetime.now().isoformat()
        },
        priority=RedisMessagePriority.HIGH if detection_data.get('confidence', 0) > 0.8 else RedisMessagePriority.NORMAL
    )


async def publish_alert(redis_manager: RedisPubSubManager,
                       alert_data: Dict[str, Any]) -> bool:
    """
    Publish alert
    
    Args:
        redis_manager: RedisPubSubManager instance
        alert_data: Alert data
        
    Returns:
        True if published successfully
    """
    severity = alert_data.get('severity', 'warning')
    channel = RedisChannel.ALERT_CRITICAL if severity == 'critical' else RedisChannel.ALERT
    
    priority = RedisMessagePriority.CRITICAL if severity == 'critical' else RedisMessagePriority.HIGH
    
    return await redis_manager.publish(
        channel,
        {
            'type': 'alert',
            'data': alert_data,
            'timestamp': datetime.now().isoformat()
        },
        priority=priority
    )


async def publish_position_update(redis_manager: RedisPubSubManager,
                                 drone_id: str,
                                 position: Dict[str, float]) -> bool:
    """
    Publish drone position update
    
    Args:
        redis_manager: RedisPubSubManager instance
        drone_id: Drone identifier
        position: Position data (lat, lon, alt)
        
    Returns:
        True if published successfully
    """
    return await redis_manager.publish(
        RedisChannel.POSITION_UPDATE,
        {
            'drone_id': drone_id,
            'position': position,
            'timestamp': datetime.now().isoformat()
        },
        priority=RedisMessagePriority.HIGH
    )


async def publish_system_metrics(redis_manager: RedisPubSubManager,
                                metrics: Dict[str, Any]) -> bool:
    """
    Publish system metrics
    
    Args:
        redis_manager: RedisPubSubManager instance
        metrics: System metrics
        
    Returns:
        True if published successfully
    """
    return await redis_manager.publish(
        RedisChannel.SYSTEM_METRICS,
        {
            'type': 'metrics',
            'data': metrics,
            'timestamp': datetime.now().isoformat()
        },
        priority=RedisMessagePriority.LOW
    )


# ============================================================================
# Factory Functions
# ============================================================================

async def create_redis_manager(config: Optional[RedisConfig] = None) -> RedisPubSubManager:
    """
    Create and connect Redis Pub/Sub manager
    
    Args:
        config: Redis configuration (uses defaults if None)
        
    Returns:
        Connected RedisPubSubManager instance
    """
    if config is None:
        config = RedisConfig()
    
    manager = RedisPubSubManager(config)
    
    # Add default rate limits
    await manager.add_rate_limit(RedisChannel.DETECTION.value, 100, 60)
    await manager.add_rate_limit(RedisChannel.ALERT.value, 30, 60)
    await manager.add_rate_limit(RedisChannel.SYSTEM_METRICS.value, 60, 60)
    
    # Connect
    if await manager.connect():
        return manager
    else:
        raise ConnectionError(f"Failed to connect to Redis at {config.host}:{config.port}")


def create_default_redis_manager() -> RedisPubSubManager:
    """Create default Redis manager (requires async connect)"""
    return RedisPubSubManager(RedisConfig())


# ============================================================================
# Example Usage
# ============================================================================

async def main():
    """Example usage of Redis Pub/Sub"""
    
    print("Redis Pub/Sub Test")
    print("=" * 50)
    
    # Create manager
    config = RedisConfig(
        host="localhost",
        port=6379,
        decode_responses=True
    )
    
    manager = RedisPubSubManager(config)
    
    # Connect
    print("\n1. Connecting to Redis...")
    if await manager.connect():
        print("   Connected successfully!")
    else:
        print("   Failed to connect!")
        return
    
    # Register handlers
    print("\n2. Registering handlers...")
    
    async def on_detection(channel: str, data: Dict[str, Any]):
        print(f"   Detection received: {data.get('data', {}).get('drone_type', 'Unknown')}")
    
    async def on_alert(channel: str, data: Dict[str, Any]):
        severity = data.get('data', {}).get('severity', 'unknown')
        print(f"   ALERT [{severity}]: {data.get('data', {}).get('message', 'No message')}")
    
    async def on_position(channel: str, data: Dict[str, Any]):
        drone_id = data.get('drone_id', 'unknown')
        pos = data.get('position', {})
        print(f"   Position update: {drone_id} at ({pos.get('lat', 0):.4f}, {pos.get('lon', 0):.4f})")
    
    await manager.subscribe(RedisChannel.DETECTION, on_detection)
    await manager.subscribe(RedisChannel.ALERT, on_alert)
    await manager.subscribe(RedisChannel.POSITION_UPDATE, on_position)
    
    # Subscribe to pattern
    async def on_any_drone(channel: str, data: Dict[str, Any]):
        print(f"   Pattern match - {channel}: {str(data)[:50]}...")
    
    await manager.psubscribe("drone:*", on_any_drone)
    
    print("   Handlers registered")
    
    # Publish test messages
    print("\n3. Publishing test messages...")
    
    # Publish detection
    await publish_detection(manager, {
        'drone_id': 'test_001',
        'drone_type': 'DJI Mavic 3',
        'confidence': 0.95,
        'signal_strength': -45,
        'frequency': 2.44e9
    })
    
    # Publish alert
    await publish_alert(manager, {
        'severity': 'critical',
        'message': 'Unauthorized drone detected in restricted zone',
        'drone_id': 'test_001'
    })
    
    # Publish position
    await publish_position_update(manager, 'test_001', {
        'lat': 37.7749,
        'lon': -122.4194,
        'alt': 100.0
    })
    
    # Publish metrics
    await publish_system_metrics(manager, {
        'detections_per_minute': 15,
        'average_confidence': 0.87,
        'active_threats': 2
    })
    
    # Add to stream
    print("\n4. Testing Redis Streams...")
    stream_id = await manager.stream_add("detection:stream", {
        'drone_type': 'DJI Mavic 3',
        'confidence': 0.95,
        'timestamp': datetime.now().isoformat()
    })
    print(f"   Added to stream: {stream_id}")
    
    # Read from stream
    messages = await manager.stream_read("detection:stream", count=5)
    print(f"   Read {len(messages)} messages from stream")
    
    # Wait for messages to be processed
    print("\n5. Waiting for messages to be processed...")
    await asyncio.sleep(2)
    
    # Get statistics
    print("\n6. Statistics:")
    stats = manager.get_stats()
    print(f"   Messages published: {stats['messages_published']}")
    print(f"   Messages received: {stats['messages_received']}")
    print(f"   Messages queued: {stats['messages_queued']}")
    print(f"   Subscriptions: {stats['subscriptions']}")
    print(f"   Pattern subscriptions: {stats['pattern_subscriptions']}")
    print(f"   Connected: {stats['connected']}")
    
    # Disconnect
    print("\n7. Disconnecting...")
    await manager.disconnect()
    
    print("\n" + "=" * 50)
    print("Redis Pub/Sub test complete")


if __name__ == "__main__":
    # Run async main
    asyncio.run(main())