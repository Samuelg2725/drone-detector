#!/usr/bin/env python3
# drone-detector/infrastructure/monitoring/__init__.py
"""
Infrastructure Monitoring Module

This module provides comprehensive monitoring capabilities for the Drone Detection System,
including:
- Prometheus metrics collection and exposition
- Health check endpoints (liveness, readiness, startup)
- Structured logging with JSON support
- System performance monitoring
- Resource usage tracking (CPU, memory, disk)
- Service dependency health checks
- Metric aggregation and reporting
- Log rotation and archiving
- Distributed tracing support
- Alert integration with Prometheus Alertmanager

The monitoring layer enables:
- Real-time system observability
- Performance bottleneck identification
- Proactive issue detection
- Capacity planning
- SLA/SLO monitoring
- Audit trail generation
"""

from typing import Dict, Any, Optional, List, Union
from datetime import datetime

# ============================================================================
# Metrics
# ============================================================================

from .metrics import (
    Metrics,
    MetricsCollector,
    MetricsServer,
    PushGatewayClient,
    MetricsDecorators,
    measure_duration,
    get_metrics,
    start_metrics_server,
    create_metrics_collector
)

# ============================================================================
# Health Check
# ============================================================================

from .health_check import (
    HealthCheckManager,
    HealthCheckRegistry,
    BaseHealthCheck,
    HealthStatus,
    HealthCheckType,
    HealthCheckResult,
    OverallHealth,
    DatabaseHealthCheck,
    HardwareHealthCheck,
    SDRHealthCheck,
    DiskSpaceHealthCheck,
    MemoryHealthCheck,
    ExternalServicesHealthCheck,
    APIHealthCheck,
    WebSocketHealthCheck,
    DetectionEngineHealthCheck,
    create_health_check_manager,
    setup_default_health_checks,
    create_health_routes
)

# ============================================================================
# Logger
# ============================================================================

from .logger import (
    StructuredLogger,
    LogConfig,
    LogLevel,
    LogFormat,
    LogDestination,
    LoggerFactory,
    logging_context,
    set_request_id,
    get_request_id,
    set_user_id,
    get_user_id,
    set_session_id,
    get_session_id,
    set_correlation_id,
    get_correlation_id,
    log_function_call,
    log_performance,
    setup_logging,
    get_logger,
    shutdown_logging
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
    # Metrics
    "Metrics",
    "MetricsCollector",
    "MetricsServer",
    "PushGatewayClient",
    "MetricsDecorators",
    "measure_duration",
    "get_metrics",
    "start_metrics_server",
    "create_metrics_collector",
    
    # Health Check
    "HealthCheckManager",
    "HealthCheckRegistry",
    "BaseHealthCheck",
    "HealthStatus",
    "HealthCheckType",
    "HealthCheckResult",
    "OverallHealth",
    "DatabaseHealthCheck",
    "HardwareHealthCheck",
    "SDRHealthCheck",
    "DiskSpaceHealthCheck",
    "MemoryHealthCheck",
    "ExternalServicesHealthCheck",
    "APIHealthCheck",
    "WebSocketHealthCheck",
    "DetectionEngineHealthCheck",
    "create_health_check_manager",
    "setup_default_health_checks",
    "create_health_routes",
    
    # Logger
    "StructuredLogger",
    "LogConfig",
    "LogLevel",
    "LogFormat",
    "LogDestination",
    "LoggerFactory",
    "logging_context",
    "set_request_id",
    "get_request_id",
    "set_user_id",
    "get_user_id",
    "set_session_id",
    "get_session_id",
    "set_correlation_id",
    "get_correlation_id",
    "log_function_call",
    "log_performance",
    "setup_logging",
    "get_logger",
    "shutdown_logging",
]


# ============================================================================
# Unified Monitoring Manager
# ============================================================================

class MonitoringManager:
    """
    Unified monitoring manager that orchestrates all monitoring components
    
    This class provides a single interface for:
    - Metrics collection and exposition
    - Health check management
    - Structured logging
    - Performance monitoring
    
    Usage:
        manager = MonitoringManager()
        await manager.initialize()
        
        # Start metrics server
        await manager.start_metrics_server(port=8001)
        
        # Get overall health
        health = await manager.get_health()
        
        # Log with context
        async with manager.logging_context(request_id="123"):
            manager.logger.info("Processing request")
    """
    
    def __init__(self):
        """Initialize monitoring manager"""
        self.metrics: Optional[Metrics] = None
        self.metrics_collector: Optional[MetricsCollector] = None
        self.metrics_server: Optional[MetricsServer] = None
        self.health_manager: Optional[HealthCheckManager] = None
        self.logger: Optional[StructuredLogger] = None
        self._initialized = False
        self._start_time = datetime.now()
        
        # Statistics
        self.stats = {
            'metrics_collected': 0,
            'health_checks_performed': 0,
            'logs_generated': 0
        }
    
    async def initialize(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize monitoring manager
        
        Args:
            config: Configuration dictionary for monitoring components
        """
        if self._initialized:
            return
        
        config = config or {}
        
        # Initialize metrics
        self.metrics = get_metrics()
        
        # Initialize metrics collector
        collector_config = config.get('metrics_collector', {})
        self.metrics_collector = create_metrics_collector(
            interval_seconds=collector_config.get('interval_seconds', 10)
        )
        await self.metrics_collector.start()
        
        # Initialize health check manager
        self.health_manager = create_health_check_manager()
        await self.health_manager.initialize()
        
        # Initialize logger
        log_config_dict = config.get('logger', {})
        from .logger import LogConfig, LogLevel, setup_logging
        
        log_config = LogConfig(
            level=LogLevel(log_config_dict.get('level', 'INFO')),
            console_enabled=log_config_dict.get('console_enabled', True),
            file_enabled=log_config_dict.get('file_enabled', True),
            file_path=log_config_dict.get('file_path', 'data/logs/system.log')
        )
        setup_logging(log_config)
        self.logger = get_logger("monitoring")
        
        self._initialized = True
        
        self.logger.info("Monitoring manager initialized", config=config)
    
    async def start_metrics_server(self, port: int = 8001) -> None:
        """
        Start Prometheus metrics server
        
        Args:
            port: HTTP server port
        """
        if not self._initialized:
            raise RuntimeError("Monitoring manager not initialized")
        
        self.metrics_server = start_metrics_server(port)
        self.logger.info(f"Metrics server started on port {port}")
    
    async def stop_metrics_server(self) -> None:
        """Stop metrics server (if running)"""
        if self.metrics_server:
            # Metrics server runs in background thread, no explicit stop needed
            self.metrics_server = None
            self.logger.info("Metrics server stopped")
    
    async def register_health_checks(self, **dependencies) -> None:
        """
        Register health checks for dependencies
        
        Args:
            **dependencies: Named dependencies for health checks
                - database: Database manager
                - hardware: Hardware manager
                - sdr: SDR device
                - external: External services manager
                - detection: Detection service
                - websocket: WebSocket manager
        """
        if not self.health_manager:
            raise RuntimeError("Health manager not initialized")
        
        await setup_default_health_checks(
            manager=self.health_manager,
            db_manager=dependencies.get('database'),
            hardware_manager=dependencies.get('hardware'),
            sdr_device=dependencies.get('sdr'),
            external_manager=dependencies.get('external'),
            detection_service=dependencies.get('detection'),
            websocket_manager=dependencies.get('websocket')
        )
        
        self.logger.info("Health checks registered", 
                        dependencies=list(dependencies.keys()))
    
    async def get_health(self) -> Dict[str, Any]:
        """
        Get overall system health
        
        Returns:
            Dictionary with health information
        """
        if not self.health_manager:
            return {'status': 'unavailable', 'error': 'Health manager not initialized'}
        
        self.stats['health_checks_performed'] += 1
        health = await self.health_manager.overall_health()
        return health.to_dict()
    
    async def get_liveness(self) -> Dict[str, Any]:
        """
        Get liveness status
        
        Returns:
            Liveness status dictionary
        """
        if not self.health_manager:
            return {'status': 'unhealthy', 'error': 'Health manager not initialized'}
        
        health = await self.health_manager.liveness_probe()
        return health.to_dict()
    
    async def get_readiness(self) -> Dict[str, Any]:
        """
        Get readiness status
        
        Returns:
            Readiness status dictionary
        """
        if not self.health_manager:
            return {'status': 'unhealthy', 'error': 'Health manager not initialized'}
        
        health = await self.health_manager.readiness_probe()
        return health.to_dict()
    
    def record_metric(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """
        Record a custom metric
        
        Args:
            name: Metric name
            value: Metric value
            labels: Optional labels for the metric
        """
        if not self.metrics or not self.metrics.is_enabled():
            return
        
        # Create or get custom gauge
        gauge = self.metrics.create_gauge(
            f"drone_custom_{name}",
            f"Custom metric: {name}",
            list(labels.keys()) if labels else None
        )
        
        if labels:
            gauge.labels(**labels).set(value)
        else:
            gauge.set(value)
        
        self.stats['metrics_collected'] += 1
    
    def increment_counter(self, name: str, labels: Optional[Dict[str, str]] = None):
        """
        Increment a counter metric
        
        Args:
            name: Counter name
            labels: Optional labels
        """
        if not self.metrics or not self.metrics.is_enabled():
            return
        
        counter = self.metrics.create_counter(
            f"drone_custom_{name}_total",
            f"Custom counter: {name}",
            list(labels.keys()) if labels else None
        )
        
        if labels:
            counter.labels(**labels).inc()
        else:
            counter.inc()
        
        self.stats['metrics_collected'] += 1
    
    def update_uptime(self):
        """Update system uptime metric"""
        if not self.metrics or not self.metrics.is_enabled():
            return
        
        uptime = (datetime.now() - self._start_time).total_seconds()
        self.metrics.system_uptime.set(uptime)
    
    def logging_context(self, request_id: Optional[str] = None,
                        user_id: Optional[str] = None,
                        session_id: Optional[str] = None,
                        correlation_id: Optional[str] = None):
        """
        Get logging context manager
        
        Args:
            request_id: Request ID
            user_id: User ID
            session_id: Session ID
            correlation_id: Correlation ID
            
        Returns:
            Logging context manager
        """
        from .logger import logging_context as log_ctx
        return log_ctx(request_id, user_id, session_id, correlation_id)
    
    async def record_detection_metric(self, detection_data: Dict[str, Any]):
        """
        Record detection metrics
        
        Args:
            detection_data: Detection information
        """
        if not self.metrics or not self.metrics.is_enabled():
            return
        
        # Increment detection counter
        self.metrics.detections_total.labels(
            drone_type=detection_data.get('drone_type', 'unknown'),
            threat_level=detection_data.get('threat_level', 'UNKNOWN'),
            source=detection_data.get('source', 'unknown')
        ).inc()
        
        # Record confidence histogram
        confidence = detection_data.get('confidence', 0)
        self.metrics.detection_confidence.observe(confidence)
        
        # Update active detections gauge
        active = detection_data.get('active_detections', 0)
        self.metrics.detections_active.labels(
            threat_level=detection_data.get('threat_level', 'UNKNOWN')
        ).set(active)
        
        # Log the detection
        if self.logger:
            self.logger.log_detection(detection_data)
        
        self.stats['metrics_collected'] += 3
    
    async def record_alert_metric(self, alert_data: Dict[str, Any]):
        """
        Record alert metrics
        
        Args:
            alert_data: Alert information
        """
        if not self.metrics or not self.metrics.is_enabled():
            return
        
        # Increment alert counter
        self.metrics.alerts_total.labels(
            severity=alert_data.get('severity', 'UNKNOWN'),
            category=alert_data.get('category', 'GENERAL')
        ).inc()
        
        # Update active alerts gauge
        active = alert_data.get('active_alerts', 0)
        self.metrics.alerts_active.labels(
            severity=alert_data.get('severity', 'UNKNOWN')
        ).set(active)
        
        # Log the alert
        if self.logger:
            self.logger.log_alert(alert_data)
        
        self.stats['metrics_collected'] += 2
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get monitoring manager statistics
        
        Returns:
            Dictionary with statistics
        """
        metrics_stats = self.metrics.get_stats() if self.metrics and hasattr(self.metrics, 'get_stats') else {}
        health_stats = self.health_manager.get_status() if self.health_manager else {}
        
        return {
            **self.stats,
            'initialized': self._initialized,
            'uptime_seconds': (datetime.now() - self._start_time).total_seconds(),
            'metrics_server_running': self.metrics_server is not None,
            'metrics_collector_running': self.metrics_collector is not None,
            'health_manager': health_stats,
            'metrics': metrics_stats
        }
    
    async def shutdown(self):
        """Shutdown monitoring manager"""
        if self.metrics_collector:
            await self.metrics_collector.stop()
        
        if self.metrics_server:
            await self.stop_metrics_server()
        
        shutdown_logging()
        
        self._initialized = False
        print("Monitoring manager shutdown complete")


# ============================================================================
# Convenience Functions
# ============================================================================

def get_monitoring_info() -> Dict[str, Any]:
    """
    Get information about monitoring components
    
    Returns:
        Dictionary with component information
    """
    return {
        "version": __version__,
        "components": {
            "metrics": {
                "description": "Prometheus metrics collection and exposition",
                "features": ["counters", "gauges", "histograms", "summaries"],
                "export_format": "Prometheus text format",
                "default_port": 8001
            },
            "health_check": {
                "description": "Health check endpoints for container orchestration",
                "features": ["liveness", "readiness", "startup", "dependency checks"],
                "probe_endpoints": ["/health/live", "/health/ready", "/health/startup"]
            },
            "logger": {
                "description": "Structured logging with multiple formats",
                "formats": ["text", "json", "color"],
                "outputs": ["console", "file", "syslog", "network"],
                "features": ["context", "rotation", "redaction", "async"]
            }
        }
    }


# ============================================================================
# Singleton Manager
# ============================================================================

_default_monitoring_manager: Optional[MonitoringManager] = None


async def get_monitoring_manager(config: Optional[Dict[str, Any]] = None) -> MonitoringManager:
    """
    Get or create the default monitoring manager singleton
    
    Args:
        config: Optional configuration for initialization
        
    Returns:
        MonitoringManager instance
    """
    global _default_monitoring_manager
    
    if _default_monitoring_manager is None:
        _default_monitoring_manager = MonitoringManager()
        await _default_monitoring_manager.initialize(config)
    
    return _default_monitoring_manager


async def reset_monitoring_manager() -> None:
    """Reset the default monitoring manager"""
    global _default_monitoring_manager
    
    if _default_monitoring_manager:
        await _default_monitoring_manager.shutdown()
        _default_monitoring_manager = None


# ============================================================================
# Module Documentation
# ============================================================================

__doc__ = """
Infrastructure Monitoring Package
=================================

This package provides comprehensive monitoring capabilities for the Drone Detection System.

Components:
-----------
1. **Metrics** - Prometheus metrics collection and exposition
2. **Health Check** - Liveness, readiness, and startup probes
3. **Logger** - Structured logging with multiple formats and outputs

Quick Start:
-----------
```python
from infrastructure.monitoring import (
    MonitoringManager,
    get_monitoring_manager,
    setup_logging,
    get_logger,
    get_metrics
)

# Method 1: Use unified manager
manager = await get_monitoring_manager({
    'logger': {
        'level': 'INFO',
        'console_enabled': True,
        'file_enabled': True
    },
    'metrics_collector': {
        'interval_seconds': 10
    }
})

# Start metrics server
await manager.start_metrics_server(port=8001)

# Register health checks
await manager.register_health_checks(
    database=db_manager,
    hardware=hardware_manager
)

# Get system health
health = await manager.get_health()

# Record metrics
await manager.record_detection_metric(detection_data)

# Method 2: Use individual components
from infrastructure.monitoring import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)
logger.info("System started")

from infrastructure.monitoring import get_metrics, start_metrics_server

metrics = get_metrics()
metrics.detections_total.labels(drone_type="DJI").inc()
start_metrics_server(8001)

from infrastructure.monitoring import create_health_check_manager

health_manager = create_health_check_manager()
await health_manager.initialize()