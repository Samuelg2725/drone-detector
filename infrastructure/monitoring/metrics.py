#!/usr/bin/env python3
# drone-detector/infrastructure/monitoring/metrics.py
"""
Prometheus Metrics Collection

This module provides comprehensive Prometheus metrics for the Drone Detection System,
enabling:
- Real-time system monitoring and observability
- Performance tracking and bottleneck identification
- Alerting based on metric thresholds
- Historical trend analysis
- Capacity planning
- SLA/SLO monitoring
- Drone detection statistics
- Hardware performance metrics
- API endpoint monitoring
- Background job tracking
- Custom business metrics
"""

import asyncio
import time
import threading
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable, Union, Tuple
from functools import wraps

# Try to import prometheus_client
try:
    from prometheus_client import (
        Counter, Gauge, Histogram, Summary, Info, Enum,
        generate_latest, CONTENT_TYPE_LATEST, REGISTRY,
        CollectorRegistry, push_to_gateway, start_http_server
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    # Create dummy classes for when prometheus is not available
    class Counter:
        def __init__(self, *args, **kwargs): pass
        def inc(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self
    
    class Gauge:
        def __init__(self, *args, **kwargs): pass
        def set(self, *args, **kwargs): pass
        def inc(self, *args, **kwargs): pass
        def dec(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self
    
    class Histogram:
        def __init__(self, *args, **kwargs): pass
        def observe(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self
    
    class Summary:
        def __init__(self, *args, **kwargs): pass
        def observe(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self
    
    class Info:
        def __init__(self, *args, **kwargs): pass
        def info(self, *args, **kwargs): pass

# Setup logging
import logging
logger = logging.getLogger(__name__)


# ============================================================================
# Metric Definitions
# ============================================================================

class Metrics:
    """Central registry for all Prometheus metrics"""
    
    # Singleton instance
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize all metrics"""
        if not PROMETHEUS_AVAILABLE:
            logger.warning("Prometheus client not available. Metrics disabled.")
            self._enabled = False
            return
        
        self._enabled = True
        
        # ====================================================================
        # System Metrics
        # ====================================================================
        
        self.system_uptime = Gauge(
            'drone_system_uptime_seconds',
            'System uptime in seconds'
        )
        
        self.system_memory_usage = Gauge(
            'drone_system_memory_usage_bytes',
            'System memory usage in bytes',
            ['type']  # rss, vms, shared, text, lib, data, dirty
        )
        
        self.system_cpu_usage = Gauge(
            'drone_system_cpu_usage_percent',
            'System CPU usage percentage',
            ['core']
        )
        
        self.system_disk_usage = Gauge(
            'drone_system_disk_usage_bytes',
            'System disk usage in bytes',
            ['path', 'type']  # used, free, total
        )
        
        # ====================================================================
        # Detection Metrics
        # ====================================================================
        
        self.detections_total = Counter(
            'drone_detections_total',
            'Total number of drone detections',
            ['drone_type', 'threat_level', 'source']
        )
        
        self.detections_active = Gauge(
            'drone_detections_active',
            'Number of currently active detections',
            ['threat_level']
        )
        
        self.detection_confidence = Histogram(
            'drone_detection_confidence',
            'Detection confidence distribution',
            buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        )
        
        self.detection_processing_time = Histogram(
            'drone_detection_processing_seconds',
            'Time taken to process a detection',
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
        )
        
        self.false_positive_rate = Gauge(
            'drone_false_positive_rate',
            'False positive rate for detections'
        )
        
        # ====================================================================
        # Alert Metrics
        # ====================================================================
        
        self.alerts_total = Counter(
            'drone_alerts_total',
            'Total number of alerts generated',
            ['severity', 'category']
        )
        
        self.alerts_active = Gauge(
            'drone_alerts_active',
            'Number of currently active alerts',
            ['severity']
        )
        
        self.alert_escalations = Counter(
            'drone_alert_escalations_total',
            'Number of alerts that required escalation',
            ['severity']
        )
        
        self.alert_response_time = Histogram(
            'drone_alert_response_seconds',
            'Time to acknowledge/resolve alerts',
            buckets=[1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600]
        )
        
        # ====================================================================
        # Hardware Metrics
        # ====================================================================
        
        self.sdr_sample_rate = Gauge(
            'drone_sdr_sample_rate_hz',
            'Current SDR sample rate in Hz',
            ['device']
        )
        
        self.sdr_center_freq = Gauge(
            'drone_sdr_center_frequency_hz',
            'Current SDR center frequency in Hz',
            ['device']
        )
        
        self.sdr_gain = Gauge(
            'drone_sdr_gain_db',
            'Current SDR gain in dB',
            ['device', 'stage']  # lna, vga, amp
        )
        
        self.sdr_temperature = Gauge(
            'drone_sdr_temperature_celsius',
            'SDR device temperature in Celsius',
            ['device']
        )
        
        self.sdr_errors = Counter(
            'drone_sdr_errors_total',
            'Number of SDR errors',
            ['device', 'error_type']
        )
        
        self.antenna_switches = Counter(
            'drone_antenna_switches_total',
            'Number of antenna switch operations',
            ['antenna']
        )
        
        self.antenna_signal_strength = Gauge(
            'drone_antenna_signal_strength_dbm',
            'Signal strength by antenna',
            ['antenna']
        )
        
        # ====================================================================
        # Signal Processing Metrics
        # ====================================================================
        
        self.signal_fft_time = Histogram(
            'drone_signal_fft_seconds',
            'Time to compute FFT',
            buckets=[0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1]
        )
        
        self.signal_psd_time = Histogram(
            'drone_signal_psd_seconds',
            'Time to compute PSD',
            buckets=[0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1]
        )
        
        self.signal_peak_detection_time = Histogram(
            'drone_signal_peak_detection_seconds',
            'Time for peak detection',
            buckets=[0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1]
        )
        
        self.signal_snr = Gauge(
            'drone_signal_snr_db',
            'Signal-to-noise ratio in dB',
            ['frequency_band']
        )
        
        self.signal_noise_floor = Gauge(
            'drone_signal_noise_floor_dbm',
            'Noise floor in dBm',
            ['frequency_band']
        )
        
        self.signal_band_occupancy = Gauge(
            'drone_signal_band_occupancy_percent',
            'Frequency band occupancy percentage',
            ['band']
        )
        
        # ====================================================================
        # ML Model Metrics
        # ====================================================================
        
        self.ml_inference_time = Histogram(
            'drone_ml_inference_seconds',
            'ML model inference time',
            ['model_name']
        )
        
        self.ml_confidence = Gauge(
            'drone_ml_confidence',
            'ML model confidence score',
            ['model_name', 'drone_type']
        )
        
        self.ml_accuracy = Gauge(
            'drone_ml_accuracy',
            'ML model accuracy',
            ['model_name']
        )
        
        self.ml_predictions_total = Counter(
            'drone_ml_predictions_total',
            'Total ML predictions made',
            ['model_name', 'result']  # correct, incorrect
        )
        
        self.ml_training_time = Histogram(
            'drone_ml_training_seconds',
            'ML model training time',
            ['model_name']
        )
        
        self.ml_training_samples = Gauge(
            'drone_ml_training_samples',
            'Number of training samples',
            ['model_name']
        )
        
        # ====================================================================
        # Remote ID Metrics
        # ====================================================================
        
        self.remote_id_messages = Counter(
            'drone_remote_id_messages_total',
            'Remote ID messages received',
            ['status']  # valid, invalid, corrupted
        )
        
        self.remote_id_drones = Gauge(
            'drone_remote_id_drones_active',
            'Number of drones broadcasting Remote ID'
        )
        
        self.remote_id_position_age = Histogram(
            'drone_remote_id_position_age_seconds',
            'Age of Remote ID position data',
            buckets=[1, 2, 5, 10, 15, 30, 60]
        )
        
        # ====================================================================
        # TDOA Metrics
        # ====================================================================
        
        self.tdoa_position_errors = Histogram(
            'drone_tdoa_position_error_meters',
            'TDOA position estimation error',
            buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000]
        )
        
        self.tdoa_gdop = Gauge(
            'drone_tdoa_gdop',
            'Geometric Dilution of Precision',
            ['receiver_count']
        )
        
        self.tdoa_receivers = Gauge(
            'drone_tdoa_receivers_active',
            'Number of active TDOA receivers'
        )
        
        self.tdoa_sync_error = Gauge(
            'drone_tdoa_sync_error_ns',
            'TDOA receiver synchronization error in nanoseconds',
            ['receiver_pair']
        )
        
        # ====================================================================
        # API Metrics
        # ====================================================================
        
        self.api_requests_total = Counter(
            'drone_api_requests_total',
            'Total API requests',
            ['method', 'endpoint', 'status_code']
        )
        
        self.api_request_duration = Histogram(
            'drone_api_request_duration_seconds',
            'API request duration',
            ['method', 'endpoint'],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
        )
        
        self.api_active_connections = Gauge(
            'drone_api_active_connections',
            'Active WebSocket/API connections',
            ['type']
        )
        
        self.api_errors = Counter(
            'drone_api_errors_total',
            'Total API errors',
            ['method', 'endpoint', 'error_type']
        )
        
        # ====================================================================
        # Recording Metrics
        # ====================================================================
        
        self.recording_size = Gauge(
            'drone_recording_size_bytes',
            'Size of IQ recordings',
            ['format']
        )
        
        self.recording_duration = Histogram(
            'drone_recording_duration_seconds',
            'Duration of IQ recordings',
            ['format'],
            buckets=[1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600]
        )
        
        self.recording_buffer_usage = Gauge(
            'drone_recording_buffer_usage_percent',
            'Recording buffer usage percentage',
            ['type']  # pre_trigger, post_trigger
        )
        
        self.recording_compression_ratio = Gauge(
            'drone_recording_compression_ratio',
            'IQ data compression ratio',
            ['format']
        )
        
        # ====================================================================
        # Playback Metrics
        # ====================================================================
        
        self.playback_speed = Gauge(
            'drone_playback_speed',
            'Current playback speed multiplier'
        )
        
        self.playback_position = Gauge(
            'drone_playback_position_seconds',
            'Current playback position in seconds',
            ['file']
        )
        
        self.playback_buffer_underruns = Counter(
            'drone_playback_buffer_underruns_total',
            'Number of playback buffer underruns',
            ['file']
        )
        
        # ====================================================================
        # Database Metrics
        # ====================================================================
        
        self.db_connections_active = Gauge(
            'drone_db_connections_active',
            'Active database connections',
            ['database']
        )
        
        self.db_query_duration = Histogram(
            'drone_db_query_duration_seconds',
            'Database query duration',
            ['query_type'],
            buckets=[0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1]
        )
        
        self.db_query_total = Counter(
            'drone_db_queries_total',
            'Total database queries',
            ['query_type', 'status']
        )
        
        self.db_size = Gauge(
            'drone_db_size_bytes',
            'Database file size in bytes',
            ['database']
        )
        
        self.db_pool_usage = Gauge(
            'drone_db_pool_usage_percent',
            'Database connection pool usage percentage'
        )
        
        # ====================================================================
        # MQTT Metrics
        # ====================================================================
        
        self.mqtt_messages_published = Counter(
            'drone_mqtt_messages_published_total',
            'MQTT messages published',
            ['topic', 'qos']
        )
        
        self.mqtt_messages_received = Counter(
            'drone_mqtt_messages_received_total',
            'MQTT messages received',
            ['topic']
        )
        
        self.mqtt_connection_state = Gauge(
            'drone_mqtt_connection_state',
            'MQTT connection state (0=disconnected, 1=connected)'
        )
        
        self.mqtt_reconnects = Counter(
            'drone_mqtt_reconnects_total',
            'MQTT reconnection attempts'
        )
        
        # ====================================================================
        # WebSocket Metrics
        # ====================================================================
        
        self.websocket_messages_sent = Counter(
            'drone_websocket_messages_sent_total',
            'WebSocket messages sent',
            ['type']
        )
        
        self.websocket_messages_received = Counter(
            'drone_websocket_messages_received_total',
            'WebSocket messages received',
            ['type']
        )
        
        self.websocket_clients = Gauge(
            'drone_websocket_clients',
            'Number of connected WebSocket clients'
        )
        
        # ====================================================================
        # Geofence Metrics
        # ====================================================================
        
        self.geofence_violations = Counter(
            'drone_geofence_violations_total',
            'Geofence violations',
            ['zone_id', 'zone_type']
        )
        
        self.geofence_active_zones = Gauge(
            'drone_geofence_active_zones',
            'Number of active geofence zones',
            ['zone_type']
        )
        
        self.geofence_check_time = Histogram(
            'drone_geofence_check_seconds',
            'Time to check geofence violation',
            buckets=[0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1]
        )
        
        # ====================================================================
        # Notification Metrics
        # ====================================================================
        
        self.notifications_sent = Counter(
            'drone_notifications_sent_total',
            'Notifications sent',
            ['channel', 'type', 'status']
        )
        
        self.notification_latency = Histogram(
            'drone_notification_latency_seconds',
            'Notification delivery latency',
            ['channel'],
            buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60]
        )
        
        self.notification_queue_size = Gauge(
            'drone_notification_queue_size',
            'Size of notification queue',
            ['channel']
        )
        
        # ====================================================================
        # Business Metrics
        # ====================================================================
        
        self.detections_per_minute = Gauge(
            'drone_detections_per_minute',
            'Number of detections per minute',
            ['drone_type']
        )
        
        self.threats_by_location = Gauge(
            'drone_threats_by_location',
            'Number of threats by geographic area',
            ['location', 'threat_level']
        )
        
        self.response_effectiveness = Gauge(
            'drone_response_effectiveness',
            'Effectiveness of responses (0-100)',
            ['action_type']
        )
        
        self.system_readiness = Gauge(
            'drone_system_readiness',
            'System readiness score (0-100)'
        )
        
        # ====================================================================
        # Custom Metrics Registry
        # ====================================================================
        
        self._custom_metrics: Dict[str, Union[Counter, Gauge, Histogram]] = {}
        
        logger.info("Prometheus metrics initialized")
    
    def create_counter(self, name: str, description: str, labels: List[str] = None) -> Counter:
        """Create a custom counter metric"""
        if not self._enabled:
            return Counter(name, description)
        
        if labels:
            metric = Counter(name, description, labels)
        else:
            metric = Counter(name, description)
        
        self._custom_metrics[name] = metric
        return metric
    
    def create_gauge(self, name: str, description: str, labels: List[str] = None) -> Gauge:
        """Create a custom gauge metric"""
        if not self._enabled:
            return Gauge(name, description)
        
        if labels:
            metric = Gauge(name, description, labels)
        else:
            metric = Gauge(name, description)
        
        self._custom_metrics[name] = metric
        return metric
    
    def create_histogram(self, name: str, description: str, buckets: List[float] = None,
                         labels: List[str] = None) -> Histogram:
        """Create a custom histogram metric"""
        if not self._enabled:
            return Histogram(name, description)
        
        kwargs = {}
        if buckets:
            kwargs['buckets'] = buckets
        if labels:
            metric = Histogram(name, description, labels, **kwargs)
        else:
            metric = Histogram(name, description, **kwargs)
        
        self._custom_metrics[name] = metric
        return metric
    
    def is_enabled(self) -> bool:
        """Check if Prometheus metrics are enabled"""
        return self._enabled


# ============================================================================
# Metric Decorators and Context Managers
# ============================================================================

class MetricsDecorators:
    """Decorators for automatic metric collection"""
    
    @staticmethod
    def track_time(metric: Histogram, labels: Dict[str, str] = None):
        """Decorator to track function execution time"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                start = time.time()
                try:
                    result = func(*args, **kwargs)
                    duration = time.time() - start
                    if labels:
                        metric.labels(**labels).observe(duration)
                    else:
                        metric.observe(duration)
                    return result
                except Exception as e:
                    duration = time.time() - start
                    if labels:
                        metric.labels(**labels).observe(duration)
                    raise e
            
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                start = time.time()
                try:
                    result = await func(*args, **kwargs)
                    duration = time.time() - start
                    if labels:
                        metric.labels(**labels).observe(duration)
                    else:
                        metric.observe(duration)
                    return result
                except Exception as e:
                    duration = time.time() - start
                    if labels:
                        metric.labels(**labels).observe(duration)
                    raise e
            
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            return wrapper
        return decorator
    
    @staticmethod
    def track_count(metric: Counter, labels: Dict[str, str] = None):
        """Decorator to count function calls"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                result = func(*args, **kwargs)
                if labels:
                    metric.labels(**labels).inc()
                else:
                    metric.inc()
                return result
            
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                result = await func(*args, **kwargs)
                if labels:
                    metric.labels(**labels).inc()
                else:
                    metric.inc()
                return result
            
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            return wrapper
        return decorator
    
    @staticmethod
    def track_errors(metric: Counter, error_label: str = "error_type"):
        """Decorator to track function errors"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error_type = type(e).__name__
                    metric.labels(**{error_label: error_type}).inc()
                    raise e
            
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    error_type = type(e).__name__
                    metric.labels(**{error_label: error_type}).inc()
                    raise e
            
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            return wrapper
        return decorator


@contextmanager
def measure_duration(metric: Histogram, labels: Dict[str, str] = None):
    """Context manager to measure duration of a code block"""
    start = time.time()
    try:
        yield
    finally:
        duration = time.time() - start
        if labels:
            metric.labels(**labels).observe(duration)
        else:
            metric.observe(duration)


# ============================================================================
# Metrics Collector
# ============================================================================

class MetricsCollector:
    """
    Background metrics collector for system metrics
    
    Collects and updates system-level metrics regularly:
    - CPU usage
    - Memory usage
    - Disk usage
    - System uptime
    """
    
    def __init__(self, metrics: Metrics, interval_seconds: int = 10):
        """
        Initialize metrics collector
        
        Args:
            metrics: Metrics instance
            interval_seconds: Collection interval
        """
        self.metrics = metrics
        self.interval = interval_seconds
        self._task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start(self):
        """Start background collection"""
        if not self.metrics.is_enabled():
            logger.info("Metrics collector disabled (Prometheus not available)")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._collect_loop())
        logger.info(f"Metrics collector started (interval: {self.interval}s)")
    
    async def stop(self):
        """Stop background collection"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Metrics collector stopped")
    
    async def _collect_loop(self):
        """Main collection loop"""
        while self._running:
            try:
                await self._collect_system_metrics()
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Metrics collection error: {e}")
                await asyncio.sleep(self.interval)
    
    async def _collect_system_metrics(self):
        """Collect system metrics"""
        try:
            import psutil
            import platform
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.5, percpu=True)
            for i, usage in enumerate(cpu_percent):
                self.metrics.system_cpu_usage.labels(core=str(i)).set(usage)
            
            # Memory usage
            mem = psutil.virtual_memory()
            self.metrics.system_memory_usage.labels(type='total').set(mem.total)
            self.metrics.system_memory_usage.labels(type='available').set(mem.available)
            self.metrics.system_memory_usage.labels(type='used').set(mem.used)
            self.metrics.system_memory_usage.labels(type='free').set(mem.free)
            
            # Disk usage
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    self.metrics.system_disk_usage.labels(
                        path=partition.mountpoint, type='used'
                    ).set(usage.used)
                    self.metrics.system_disk_usage.labels(
                        path=partition.mountpoint, type='free'
                    ).set(usage.free)
                    self.metrics.system_disk_usage.labels(
                        path=partition.mountpoint, type='total'
                    ).set(usage.total)
                except PermissionError:
                    pass
            
        except ImportError:
            # psutil not available, skip
            pass
    
    def update_uptime(self, start_time: float):
        """Update system uptime metric"""
        uptime = time.time() - start_time
        self.metrics.system_uptime.set(uptime)


# ============================================================================
# Metrics Server
# ============================================================================

class MetricsServer:
    """
    Prometheus metrics HTTP server
    
    Exposes metrics at /metrics endpoint for Prometheus scraping
    """
    
    def __init__(self, port: int = 8001, registry: CollectorRegistry = None):
        """
        Initialize metrics server
        
        Args:
            port: HTTP server port
            registry: Custom registry (uses default if None)
        """
        self.port = port
        self.registry = registry or REGISTRY
        self._server = None
    
    def start(self):
        """Start HTTP server in a background thread"""
        if not PROMETHEUS_AVAILABLE:
            logger.warning("Prometheus not available, metrics server not started")
            return
        
        def _run_server():
            start_http_server(self.port, addr='0.0.0.0', registry=self.registry)
        
        thread = threading.Thread(target=_run_server, daemon=True)
        thread.start()
        logger.info(f"Prometheus metrics server started on port {self.port}")
    
    def get_metrics(self) -> bytes:
        """Get current metrics data"""
        if not PROMETHEUS_AVAILABLE:
            return b""
        return generate_latest(self.registry)


# ============================================================================
# Prometheus Push Gateway
# ============================================================================

class PushGatewayClient:
    """
    Client for pushing metrics to Prometheus Push Gateway
    
    Useful for batch jobs or short-lived processes
    """
    
    def __init__(self, gateway_url: str, job_name: str = "drone_detector"):
        """
        Initialize push gateway client
        
        Args:
            gateway_url: Push gateway URL (e.g., 'http://localhost:9091')
            job_name: Job name for grouping metrics
        """
        self.gateway_url = gateway_url
        self.job_name = job_name
        self.registry = CollectorRegistry()
    
    def push(self, instance: Optional[str] = None):
        """Push metrics to gateway"""
        if not PROMETHEUS_AVAILABLE:
            return
        
        grouping_key = {'instance': instance} if instance else {}
        push_to_gateway(
            self.gateway_url,
            job=self.job_name,
            registry=self.registry,
            grouping_key=grouping_key
        )
    
    def push_add(self, instance: Optional[str] = None):
        """Push metrics to gateway (additive)"""
        if not PROMETHEUS_AVAILABLE:
            return
        
        grouping_key = {'instance': instance} if instance else {}
        push_to_gateway(
            self.gateway_url,
            job=self.job_name,
            registry=self.registry,
            grouping_key=grouping_key,
            handler='push/add'
        )
    
    def delete(self, instance: Optional[str] = None):
        """Delete metrics from gateway"""
        if not PROMETHEUS_AVAILABLE:
            return
        
        grouping_key = {'instance': instance} if instance else {}
        push_to_gateway(
            self.gateway_url,
            job=self.job_name,
            registry=self.registry,
            grouping_key=grouping_key,
            handler='delete'
        )


# ============================================================================
# Factory Functions
# ============================================================================

def get_metrics() -> Metrics:
    """Get the global metrics instance"""
    return Metrics()


def start_metrics_server(port: int = 8001) -> MetricsServer:
    """
    Start the Prometheus metrics server
    
    Args:
        port: HTTP server port
        
    Returns:
        MetricsServer instance
    """
    server = MetricsServer(port=port)
    server.start()
    return server


def create_metrics_collector(interval_seconds: int = 10) -> MetricsCollector:
    """
    Create a metrics collector
    
    Args:
        interval_seconds: Collection interval
        
    Returns:
        MetricsCollector instance
    """
    metrics = get_metrics()
    collector = MetricsCollector(metrics, interval_seconds)
    return collector


# ============================================================================
# Example Usage
# ============================================================================

async def example_usage():
    """Example usage of metrics module"""
    
    print("Prometheus Metrics Example")
    print("=" * 50)
    
    # Check if prometheus is available
    metrics = get_metrics()
    print(f"\n1. Prometheus available: {PROMETHEUS_AVAILABLE}")
    print(f"   Metrics enabled: {metrics.is_enabled()}")
    
    if not metrics.is_enabled():
        print("\n   Install prometheus_client: pip install prometheus-client")
        return
    
    # Start metrics server
    print("\n2. Starting metrics server on port 8001...")
    server = start_metrics_server(8001)
    print("   Metrics available at http://localhost:8001/metrics")
    
    # Create metrics collector
    print("\n3. Starting metrics collector...")
    collector = create_metrics_collector(interval_seconds=5)
    await collector.start()
    
    # Record some metrics
    print("\n4. Recording sample metrics...")
    
    # Increment counters
    metrics.detections_total.labels(
        drone_type="DJI Mavic 3",
        threat_level="HIGH",
        source="sdr"
    ).inc()
    
    metrics.detections_total.labels(
        drone_type="FPV",
        threat_level="MEDIUM",
        source="sdr"
    ).inc()
    
    # Set gauges
    metrics.detections_active.labels(threat_level="HIGH").set(3)
    metrics.detections_active.labels(threat_level="MEDIUM").set(5)
    metrics.detections_active.labels(threat_level="LOW").set(2)
    
    # Observe histograms
    metrics.detection_confidence.observe(0.95)
    metrics.detection_confidence.observe(0.87)
    metrics.detection_confidence.observe(0.76)
    
    metrics.detection_processing_time.observe(0.023)
    metrics.detection_processing_time.observe(0.045)
    
    # Record alerts
    metrics.alerts_total.labels(severity="CRITICAL", category="DRONE_DETECTED").inc()
    metrics.alerts_total.labels(severity="HIGH", category="GEO_FENCE_VIOLATION").inc()
    
    metrics.alerts_active.labels(severity="CRITICAL").set(1)
    metrics.alerts_active.labels(severity="HIGH").set(2)
    
    # Hardware metrics
    metrics.sdr_sample_rate.labels(device="hackrf_1").set(10e6)
    metrics.sdr_center_freq.labels(device="hackrf_1").set(2.44e9)
    metrics.sdr_gain.labels(device="hackrf_1", stage="lna").set(16)
    metrics.sdr_gain.labels(device="hackrf_1", stage="vga").set(20)
    
    # Update uptime
    collector.update_uptime(time.time() - 3600)  # 1 hour uptime
    
    # Custom metrics
    custom_counter = metrics.create_counter(
        "drone_custom_detections",
        "Custom detection counter",
        ["type"]
    )
    custom_counter.labels(type="custom").inc(5)
    
    print("   Metrics recorded successfully")
    
    # Demonstrate decorators
    print("\n5. Testing metric decorators...")
    
    @MetricsDecorators.track_time(metrics.api_request_duration, 
                                   {'method': 'GET', 'endpoint': '/api/detections'})
    def simulated_api_call():
        import random
        time.sleep(random.uniform(0.01, 0.05))
        return {"status": "ok"}
    
    for _ in range(5):
        simulated_api_call()
    print("   API call timing recorded")
    
    # Run for a few seconds to let collector run
    print("\n6. Running collector for 5 seconds...")
    await asyncio.sleep(5)
    
    # Get statistics
    print("\n7. Statistics:")
    print(f"   Detections total: {metrics.detections_total._value._value if hasattr(metrics.detections_total, '_value') else '?'}")
    print(f"   Active alerts: {metrics.alerts_active._value._value if hasattr(metrics.alerts_active, '_value') else '?'}")
    
    # Stop collector
    print("\n8. Stopping collector...")
    await collector.stop()
    
    print("\n" + "=" * 50)
    print("Metrics test complete!")
    print("Access metrics at: http://localhost:8001/metrics")
    
    # Keep server running for manual inspection
    print("\nPress Ctrl+C to exit...")
    try:
        await asyncio.Future()  # run forever
    except KeyboardInterrupt:
        pass


async def main():
    """Main function"""
    await example_usage()


if __name__ == "__main__":
    asyncio.run(main())