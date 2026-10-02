#!/usr/bin/env python3
# drone-detector/infrastructure/monitoring/health_check.py
"""
Health Check Module

This module provides comprehensive health checking capabilities for the Drone Detection System,
enabling:
- Service health monitoring and reporting
- Dependency health validation (database, hardware, external services)
- Liveness and readiness probes for container orchestration
- Health metrics collection and aggregation
- Configurable health check intervals
- Multi-level health status (healthy, degraded, unhealthy)
- Detailed health status reporting
- Health check history and trending
- Automatic recovery detection
- Custom health check registration
- Health check endpoints for load balancers (Kubernetes, Docker)
"""

import asyncio
import platform
import time
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, Optional, List, Callable, Union, Tuple
from collections import deque

# Setup logging
import logging
logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Data Classes
# ============================================================================

class HealthStatus(Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class HealthCheckType(Enum):
    """Types of health checks"""
    LIVENESS = "liveness"           # Is the service alive?
    READINESS = "readiness"         # Is the service ready to accept traffic?
    STARTUP = "startup"              # Is the service still starting up?
    DEPENDENCY = "dependency"       # Are dependencies healthy?
    CUSTOM = "custom"               # Custom health check


@dataclass
class HealthCheckResult:
    """Individual health check result"""
    name: str
    status: HealthStatus
    message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    response_time_ms: float = 0.0
    check_type: HealthCheckType = HealthCheckType.CUSTOM
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'name': self.name,
            'status': self.status.value,
            'message': self.message,
            'details': self.details,
            'timestamp': self.timestamp.isoformat(),
            'response_time_ms': self.response_time_ms,
            'type': self.check_type.value
        }


@dataclass
class OverallHealth:
    """Overall system health status"""
    status: HealthStatus
    timestamp: datetime
    checks: List[HealthCheckResult]
    uptime_seconds: float
    version: str = "2.0.0"
    hostname: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'status': self.status.value,
            'timestamp': self.timestamp.isoformat(),
            'uptime_seconds': self.uptime_seconds,
            'version': self.version,
            'hostname': self.hostname,
            'checks': [c.to_dict() for c in self.checks],
            'summary': self._get_summary()
        }
    
    def _get_summary(self) -> Dict[str, Any]:
        """Get health summary"""
        summary = {
            'total_checks': len(self.checks),
            'healthy': 0,
            'degraded': 0,
            'unhealthy': 0
        }
        
        for check in self.checks:
            if check.status == HealthStatus.HEALTHY:
                summary['healthy'] += 1
            elif check.status == HealthStatus.DEGRADED:
                summary['degraded'] += 1
            elif check.status == HealthStatus.UNHEALTHY:
                summary['unhealthy'] += 1
        
        return summary


# ============================================================================
# Base Health Check
# ============================================================================

class BaseHealthCheck:
    """Base class for individual health checks"""
    
    def __init__(self, name: str, check_type: HealthCheckType = HealthCheckType.CUSTOM):
        """
        Initialize health check
        
        Args:
            name: Health check name
            check_type: Type of health check
        """
        self.name = name
        self.check_type = check_type
    
    async def run(self) -> HealthCheckResult:
        """
        Run health check
        
        Returns:
            HealthCheckResult
        """
        start_time = time.time()
        
        try:
            status, message, details = await self._check()
            response_time = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                name=self.name,
                status=status,
                message=message,
                details=details,
                response_time_ms=response_time,
                check_type=self.check_type
            )
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check failed: {str(e)}",
                details={'error': str(e)},
                response_time_ms=response_time,
                check_type=self.check_type
            )
    
    async def _check(self) -> Tuple[HealthStatus, Optional[str], Dict[str, Any]]:
        """
        Perform the actual health check (override in subclass)
        
        Returns:
            Tuple of (status, message, details)
        """
        return HealthStatus.HEALTHY, None, {}


# ============================================================================
# Built-in Health Checks
# ============================================================================

class DatabaseHealthCheck(BaseHealthCheck):
    """Database connectivity health check"""
    
    def __init__(self, db_manager):
        super().__init__("database", HealthCheckType.DEPENDENCY)
        self.db_manager = db_manager
    
    async def _check(self) -> Tuple[HealthStatus, Optional[str], Dict[str, Any]]:
        try:
            start = time.time()
            is_healthy = await self.db_manager.health_check()
            response_time = (time.time() - start) * 1000
            
            stats = self.db_manager.get_stats()
            
            if is_healthy:
                return (
                    HealthStatus.HEALTHY,
                    f"Database is healthy (response time: {response_time:.1f}ms)",
                    {
                        'response_time_ms': response_time,
                        'connections': stats.active_connections,
                        'pool_size': stats.total_connections,
                        'queries': stats.total_queries
                    }
                )
            else:
                return (
                    HealthStatus.UNHEALTHY,
                    "Database health check failed",
                    {'error': stats.last_error}
                )
                
        except Exception as e:
            return (
                HealthStatus.UNHEALTHY,
                f"Database connection error: {str(e)}",
                {'error': str(e)}
            )


class HardwareHealthCheck(BaseHealthCheck):
    """Hardware device health check"""
    
    def __init__(self, hardware_manager):
        super().__init__("hardware", HealthCheckType.LIVENESS)
        self.hardware_manager = hardware_manager
    
    async def _check(self) -> Tuple[HealthStatus, Optional[str], Dict[str, Any]]:
        try:
            status = self.hardware_manager.get_status() if hasattr(self.hardware_manager, 'get_status') else {}
            
            # Check connection
            is_connected = status.get('connected', False)
            
            if is_connected:
                return (
                    HealthStatus.HEALTHY,
                    "Hardware is connected and operational",
                    {
                        'device_type': status.get('type', 'unknown'),
                        'sample_rate': status.get('sample_rate', 0),
                        'temperature': status.get('temperature'),
                        'uptime': status.get('uptime')
                    }
                )
            else:
                return (
                    HealthStatus.DEGRADED,
                    "Hardware is not connected",
                    {'error': status.get('error', 'No connection')}
                )
                
        except Exception as e:
            return (
                HealthStatus.UNHEALTHY,
                f"Hardware check failed: {str(e)}",
                {'error': str(e)}
            )


class SDRHealthCheck(BaseHealthCheck):
    """SDR device health check"""
    
    def __init__(self, sdr_device):
        super().__init__("sdr", HealthCheckType.LIVENESS)
        self.sdr_device = sdr_device
    
    async def _check(self) -> Tuple[HealthStatus, Optional[str], Dict[str, Any]]:
        try:
            # Try to get device status
            if hasattr(self.sdr_device, 'get_stats'):
                stats = self.sdr_device.get_stats()
                return (
                    HealthStatus.HEALTHY,
                    "SDR is operational",
                    {
                        'sample_rate': stats.get('sample_rate', 0),
                        'state': stats.get('state', 'unknown'),
                        'buffer_usage': stats.get('buffer_available', 0)
                    }
                )
            else:
                return (
                    HealthStatus.HEALTHY,
                    "SDR is available",
                    {'status': 'connected'}
                )
                
        except Exception as e:
            return (
                HealthStatus.UNHEALTHY,
                f"SDR error: {str(e)}",
                {'error': str(e)}
            )


class DiskSpaceHealthCheck(BaseHealthCheck):
    """Disk space health check"""
    
    def __init__(self, paths: List[str], threshold_gb: float = 1.0):
        super().__init__("disk_space", HealthCheckType.STARTUP)
        self.paths = paths
        self.threshold_bytes = threshold_gb * 1024 * 1024 * 1024
    
    async def _check(self) -> Tuple[HealthStatus, Optional[str], Dict[str, Any]]:
        try:
            import psutil
            results = {}
            is_healthy = True
            
            for path in self.paths:
                usage = psutil.disk_usage(path)
                free_gb = usage.free / (1024**3)
                results[path] = {
                    'free_gb': free_gb,
                    'used_gb': usage.used / (1024**3),
                    'total_gb': usage.total / (1024**3),
                    'percent': usage.percent
                }
                
                if usage.free < self.threshold_bytes:
                    is_healthy = False
            
            if is_healthy:
                return (
                    HealthStatus.HEALTHY,
                    "Sufficient disk space available",
                    results
                )
            else:
                return (
                    HealthStatus.DEGRADED,
                    "Low disk space warning",
                    results
                )
                
        except ImportError:
            return (
                HealthStatus.HEALTHY,
                "Disk space check skipped (psutil not available)",
                {}
            )
        except Exception as e:
            return (
                HealthStatus.UNHEALTHY,
                f"Disk space check failed: {str(e)}",
                {'error': str(e)}
            )


class MemoryHealthCheck(BaseHealthCheck):
    """Memory usage health check"""
    
    def __init__(self, threshold_percent: float = 90.0):
        super().__init__("memory", HealthCheckType.STARTUP)
        self.threshold_percent = threshold_percent
    
    async def _check(self) -> Tuple[HealthStatus, Optional[str], Dict[str, Any]]:
        try:
            import psutil
            mem = psutil.virtual_memory()
            
            is_healthy = mem.percent < self.threshold_percent
            
            if is_healthy:
                status = HealthStatus.HEALTHY
                message = f"Memory usage: {mem.percent:.1f}%"
            else:
                status = HealthStatus.DEGRADED
                message = f"High memory usage: {mem.percent:.1f}%"
            
            return (
                status,
                message,
                {
                    'percent': mem.percent,
                    'used_gb': mem.used / (1024**3),
                    'available_gb': mem.available / (1024**3),
                    'total_gb': mem.total / (1024**3)
                }
            )
            
        except ImportError:
            return (HealthStatus.HEALTHY, "Memory check skipped (psutil not available)", {})
        except Exception as e:
            return (HealthStatus.UNHEALTHY, f"Memory check failed: {str(e)}", {})
    
class ExternalServicesHealthCheck(BaseHealthCheck):
    """External service health check"""
    
    def __init__(self, external_manager):
        super().__init__("external_services", HealthCheckType.DEPENDENCY)
        self.external_manager = external_manager
    
    async def _check(self) -> Tuple[HealthStatus, Optional[str], Dict[str, Any]]:
        try:
            if not self.external_manager:
                return (
                    HealthStatus.HEALTHY,
                    "External services not configured",
                    {'status': 'not_configured'}
                )
            
            health = await self.external_manager.health_check()
            
            # Determine overall status
            unhealthy_count = sum(1 for s in health.values() if 'unhealthy' in str(s))
            degraded_count = sum(1 for s in health.values() if 'degraded' in str(s))
            
            if unhealthy_count > 0:
                status = HealthStatus.UNHEALTHY
                message = f"{unhealthy_count} external services unhealthy"
            elif degraded_count > 0:
                status = HealthStatus.DEGRADED
                message = f"{degraded_count} external services degraded"
            else:
                status = HealthStatus.HEALTHY
                message = "All external services healthy"
            
            return status, message, health
            
        except Exception as e:
            return (
                HealthStatus.UNHEALTHY,
                f"External services check failed: {str(e)}",
                {'error': str(e)}
            )


class APIHealthCheck(BaseHealthCheck):
    """API endpoint health check"""
    
    def __init__(self, app):
        super().__init__("api", HealthCheckType.LIVENESS)
        self.app = app
    
    async def _check(self) -> Tuple[HealthStatus, Optional[str], Dict[str, Any]]:
        try:
            # Simple check - API is running if we get here
            return (
                HealthStatus.HEALTHY,
                "API is operational",
                {'status': 'running'}
            )
        except Exception as e:
            return (
                HealthStatus.UNHEALTHY,
                f"API check failed: {str(e)}",
                {'error': str(e)}
            )


class WebSocketHealthCheck(BaseHealthCheck):
    """WebSocket server health check"""
    
    def __init__(self, websocket_manager):
        super().__init__("websocket", HealthCheckType.LIVENESS)
        self.websocket_manager = websocket_manager
    
    async def _check(self) -> Tuple[HealthStatus, Optional[str], Dict[str, Any]]:
        try:
            if hasattr(self.websocket_manager, 'get_stats'):
                stats = self.websocket_manager.get_stats()
                connections = stats.get('connections', 0)
                
                return (
                    HealthStatus.HEALTHY,
                    f"WebSocket server running ({connections} connections)",
                    {
                        'connections': connections,
                        'messages_sent': stats.get('messages_sent', 0),
                        'messages_received': stats.get('messages_received', 0)
                    }
                )
            else:
                return (
                    HealthStatus.HEALTHY,
                    "WebSocket server is operational",
                    {}
                )
                
        except Exception as e:
            return (
                HealthStatus.UNHEALTHY,
                f"WebSocket check failed: {str(e)}",
                {'error': str(e)}
            )


class DetectionEngineHealthCheck(BaseHealthCheck):
    """Detection engine health check"""
    
    def __init__(self, detection_service):
        super().__init__("detection_engine", HealthCheckType.LIVENESS)
        self.detection_service = detection_service
    
    async def _check(self) -> Tuple[HealthStatus, Optional[str], Dict[str, Any]]:
        try:
            # Check if detection service is running
            is_running = getattr(self.detection_service, 'is_running', False)
            
            if is_running:
                return (
                    HealthStatus.HEALTHY,
                    "Detection engine is running",
                    {
                        'active_detections': getattr(self.detection_service, 'active_detections', 0)
                    }
                )
            else:
                return (
                    HealthStatus.DEGRADED,
                    "Detection engine is not active",
                    {}
                )
                
        except Exception as e:
            return (
                HealthStatus.UNHEALTHY,
                f"Detection engine check failed: {str(e)}",
                {'error': str(e)}
            )


# ============================================================================
# Health Check Registry
# ============================================================================

class HealthCheckRegistry:
    """
    Registry for managing health checks
    
    Features:
    - Register custom health checks
    - Run all checks or specific types
    - Track check history
    - Concurrent check execution
    """
    
    def __init__(self):
        """Initialize health check registry"""
        self._checks: List[BaseHealthCheck] = []
        self._history: deque = deque(maxlen=1000)  # Keep last 1000 results
        self._check_times: Dict[str, datetime] = {}
    
    def register(self, check: BaseHealthCheck) -> None:
        """
        Register a health check
        
        Args:
            check: Health check to register
        """
        self._checks.append(check)
        logger.info(f"Registered health check: {check.name} ({check.check_type.value})")
    
    def unregister(self, name: str) -> bool:
        """
        Unregister a health check
        
        Args:
            name: Name of health check to remove
            
        Returns:
            True if removed
        """
        for i, check in enumerate(self._checks):
            if check.name == name:
                self._checks.pop(i)
                logger.info(f"Unregistered health check: {name}")
                return True
        return False
    
    async def run_checks(self, check_type: Optional[HealthCheckType] = None) -> List[HealthCheckResult]:
        """
        Run all registered health checks
        
        Args:
            check_type: Only run checks of this type (optional)
            
        Returns:
            List of health check results
        """
        checks_to_run = self._checks
        if check_type:
            checks_to_run = [c for c in self._checks if c.check_type == check_type]
        
        # Run checks concurrently
        tasks = [check.run() for check in checks_to_run]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        health_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                health_results.append(HealthCheckResult(
                    name=checks_to_run[i].name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Health check failed: {str(result)}",
                    check_type=checks_to_run[i].check_type
                ))
            else:
                health_results.append(result)
                self._check_times[result.name] = result.timestamp
        
        # Store history
        self._history.append({
            'timestamp': datetime.now(),
            'results': [r.to_dict() for r in health_results]
        })
        
        return health_results
    
    async def get_overall_health(self, uptime_seconds: float = 0) -> OverallHealth:
        """
        Get overall system health
        
        Args:
            uptime_seconds: System uptime in seconds
            
        Returns:
            OverallHealth object
        """
        results = await self.run_checks()
        
        # Determine overall status
        if any(r.status == HealthStatus.UNHEALTHY for r in results):
            status = HealthStatus.UNHEALTHY
        elif any(r.status == HealthStatus.DEGRADED for r in results):
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.HEALTHY
        
        import socket
        hostname = socket.gethostname()
        
        return OverallHealth(
            status=status,
            timestamp=datetime.now(),
            checks=results,
            uptime_seconds=uptime_seconds,
            hostname=hostname
        )
    
    def get_check_history(self, name: Optional[str] = None, 
                          hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get health check history
        
        Args:
            name: Specific check name (optional)
            hours: Hours of history to return
            
        Returns:
            List of historical results
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        
        history = []
        for entry in self._history:
            if entry['timestamp'] < cutoff:
                continue
            
            if name:
                # Filter by check name
                filtered_results = [r for r in entry['results'] if r['name'] == name]
                if filtered_results:
                    history.append({
                        'timestamp': entry['timestamp'],
                        'results': filtered_results
                    })
            else:
                history.append(entry)
        
        return history
    
    def get_checks_info(self) -> List[Dict[str, Any]]:
        """Get information about registered checks"""
        return [
            {
                'name': check.name,
                'type': check.check_type.value,
                'registered_at': self._check_times.get(check.name, None)
            }
            for check in self._checks
        ]
    
    def clear_history(self):
        """Clear health check history"""
        self._history.clear()
        logger.info("Health check history cleared")


# ============================================================================
# Health Check Manager
# ============================================================================

class HealthCheckManager:
    """
    Main health check manager
    
    This class manages all health checks and provides endpoints for
    liveness, readiness, and startup probes.
    """
    
    def __init__(self):
        """Initialize health check manager"""
        self.registry = HealthCheckRegistry()
        self._start_time = time.time()
        self._ready = False
        self._startup_complete = False
    
    async def initialize(self):
        """Initialize health check manager"""
        self._start_time = time.time()
        self._ready = True
        self._startup_complete = True
        logger.info("Health check manager initialized")
    
    def register_check(self, check: BaseHealthCheck) -> None:
        """
        Register a health check
        
        Args:
            check: Health check to register
        """
        self.registry.register(check)
    
    async def liveness_probe(self) -> OverallHealth:
        """
        Liveness probe - is the service alive?
        
        Returns:
            Overall health status
        """
        # Liveness checks only check critical components
        results = await self.registry.run_checks(HealthCheckType.LIVENESS)
        
        uptime = time.time() - self._start_time
        
        status = HealthStatus.HEALTHY
        if any(r.status == HealthStatus.UNHEALTHY for r in results):
            status = HealthStatus.UNHEALTHY
        elif any(r.status == HealthStatus.DEGRADED for r in results):
            status = HealthStatus.DEGRADED
        
        return OverallHealth(
            status=status,
            timestamp=datetime.now(),
            checks=results,
            uptime_seconds=uptime
        )
    
    async def readiness_probe(self) -> OverallHealth:
        """
        Readiness probe - is the service ready to accept traffic?
        
        Returns:
            Overall health status
        """
        if not self._ready:
            return OverallHealth(
                status=HealthStatus.UNHEALTHY,
                timestamp=datetime.now(),
                checks=[],
                uptime_seconds=time.time() - self._start_time
            )
        
        # Readiness checks include dependencies
        results = await self.registry.run_checks(HealthCheckType.READINESS)
        
        uptime = time.time() - self._start_time
        
        status = HealthStatus.HEALTHY
        if any(r.status == HealthStatus.UNHEALTHY for r in results):
            status = HealthStatus.UNHEALTHY
        elif any(r.status == HealthStatus.DEGRADED for r in results):
            status = HealthStatus.DEGRADED
        
        # Also include dependency checks
        dependency_results = await self.registry.run_checks(HealthCheckType.DEPENDENCY)
        all_results = results + dependency_results
        
        if any(r.status == HealthStatus.UNHEALTHY for r in dependency_results):
            status = HealthStatus.UNHEALTHY
        
        return OverallHealth(
            status=status,
            timestamp=datetime.now(),
            checks=all_results,
            uptime_seconds=uptime
        )
    
    async def startup_probe(self) -> OverallHealth:
        """
        Startup probe - is the service still starting up?
        
        Returns:
            Overall health status
        """
        if self._startup_complete:
            return OverallHealth(
                status=HealthStatus.HEALTHY,
                timestamp=datetime.now(),
                checks=[],
                uptime_seconds=time.time() - self._start_time
            )
        
        # Startup checks
        results = await self.registry.run_checks(HealthCheckType.STARTUP)
        
        uptime = time.time() - self._start_time
        
        # Check if all startup checks are healthy
        all_healthy = all(r.status == HealthStatus.HEALTHY for r in results)
        
        if all_healthy:
            self._startup_complete = True
            status = HealthStatus.HEALTHY
        else:
            status = HealthStatus.UNHEALTHY
        
        return OverallHealth(
            status=status,
            timestamp=datetime.now(),
            checks=results,
            uptime_seconds=uptime
        )
    
    async def overall_health(self) -> OverallHealth:
        """
        Get overall system health
        
        Returns:
            OverallHealth object
        """
        return await self.registry.get_overall_health(time.time() - self._start_time)
    
    def set_ready(self, ready: bool):
        """Set readiness status"""
        self._ready = ready
        logger.info(f"Readiness set to: {ready}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get health check manager status"""
        return {
            'uptime_seconds': time.time() - self._start_time,
            'ready': self._ready,
            'startup_complete': self._startup_complete,
            'registered_checks': len(self.registry._checks),
            'history_size': len(self.registry._history)
        }


# ============================================================================
# Factory Functions
# ============================================================================

def create_health_check_manager() -> HealthCheckManager:
    """Create a health check manager"""
    return HealthCheckManager()


async def setup_default_health_checks(manager: HealthCheckManager,
                                      db_manager = None,
                                      hardware_manager = None,
                                      external_manager = None,
                                      detection_service = None,
                                      websocket_manager = None,
                                      sdr_device = None) -> None:
    """
    Setup default health checks
    
    Args:
        manager: Health check manager
        db_manager: Database manager
        hardware_manager: Hardware manager
        external_manager: External services manager
        detection_service: Detection service
        websocket_manager: WebSocket manager
        sdr_device: SDR device
    """
    # Add system checks
    manager.register_check(MemoryHealthCheck(threshold_percent=90.0))
    manager.register_check(DiskSpaceHealthCheck(['/', '/data'], threshold_gb=1.0))
    
    # Add database check
    if db_manager:
        manager.register_check(DatabaseHealthCheck(db_manager))
    
    # Add hardware checks
    if hardware_manager:
        manager.register_check(HardwareHealthCheck(hardware_manager))
    
    if sdr_device:
        manager.register_check(SDRHealthCheck(sdr_device))
    
    # Add external services check
    if external_manager:
        manager.register_check(ExternalServicesHealthCheck(external_manager))
    
    # Add service checks
    if detection_service:
        manager.register_check(DetectionEngineHealthCheck(detection_service))
    
    if websocket_manager:
        manager.register_check(WebSocketHealthCheck(websocket_manager))
    
    logger.info("Default health checks configured")


# ============================================================================
# FastAPI Route Handlers
# ============================================================================

def create_health_routes(manager: HealthCheckManager):
    """
    Create FastAPI routes for health endpoints
    
    Args:
        manager: Health check manager
        
    Returns:
        FastAPI router
    """
    from fastapi import APIRouter, Response
    from fastapi.responses import JSONResponse
    
    router = APIRouter(tags=["health"])
    
    @router.get("/health/live")
    async def liveness():
        """Liveness probe endpoint"""
        result = await manager.liveness_probe()
        status_code = 200 if result.status == HealthStatus.HEALTHY else 503
        return JSONResponse(content=result.to_dict(), status_code=status_code)
    
    @router.get("/health/ready")
    async def readiness():
        """Readiness probe endpoint"""
        result = await manager.readiness_probe()
        status_code = 200 if result.status == HealthStatus.HEALTHY else 503
        return JSONResponse(content=result.to_dict(), status_code=status_code)
    
    @router.get("/health/startup")
    async def startup():
        """Startup probe endpoint"""
        result = await manager.startup_probe()
        status_code = 200 if result.status == HealthStatus.HEALTHY else 503
        return JSONResponse(content=result.to_dict(), status_code=status_code)
    
    @router.get("/health")
    async def health():
        """Overall health endpoint"""
        result = await manager.overall_health()
        status_code = 200 if result.status == HealthStatus.HEALTHY else 503
        return JSONResponse(content=result.to_dict(), status_code=status_code)
    
    @router.get("/health/checks")
    async def list_checks():
        """List all registered health checks"""
        return JSONResponse(content={
            'checks': manager.registry.get_checks_info(),
            'status': manager.get_status()
        })
    
    return router


# ============================================================================
# Example Usage
# ============================================================================

async def example_usage():
    """Example usage of health check module"""
    
    print("Health Check Module Example")
    print("=" * 50)
    
    # Create health check manager
    print("\n1. Creating health check manager...")
    manager = create_health_check_manager()
    await manager.initialize()
    
    # Setup default health checks (with mock dependencies)
    print("\n2. Setting up default health checks...")
    await setup_default_health_checks(manager)
    
    # Register a custom health check
    print("\n3. Registering custom health check...")
    
    class CustomHealthCheck(BaseHealthCheck):
        async def _check(self):
            # Simulate a check
            import random
            if random.random() > 0.9:
                return HealthStatus.DEGRADED, "Custom check degraded", {"random": True}
            return HealthStatus.HEALTHY, "Custom check passed", {"value": 42}
    
    manager.register_check(CustomHealthCheck("custom_check"))
    print("   Custom health check registered")
    
    # Run liveness probe
    print("\n4. Running liveness probe...")
    result = await manager.liveness_probe()
    print(f"   Status: {result.status.value}")
    print(f"   Uptime: {result.uptime_seconds:.1f}s")
    print(f"   Checks: {len(result.checks)}")
    
    # Run readiness probe
    print("\n5. Running readiness probe...")
    result = await manager.readiness_probe()
    print(f"   Status: {result.status.value}")
    
    # Run overall health
    print("\n6. Running overall health check...")
    result = await manager.overall_health()
    print(f"   Status: {result.status.value}")
    print(f"   Summary: {result._get_summary()}")
    
    # Show individual check results
    print("\n7. Individual check results:")
    for check in result.checks:
        print(f"   {check.name}: {check.status.value} ({check.response_time_ms:.1f}ms)")
        if check.message:
            print(f"     {check.message[:100]}")
    
    # Get check history
    print("\n8. Check history:")
    history = manager.registry.get_check_history(hours=1)
    print(f"   History entries: {len(history)}")
    
    # Create FastAPI routes (example)
    print("\n9. FastAPI routes created:")
    router = create_health_routes(manager)
    print(f"   Routes: /health, /health/live, /health/ready, /health/startup, /health/checks")
    
    # Get manager status
    print("\n10. Manager status:")
    status = manager.get_status()
    for key, value in status.items():
        print(f"    {key}: {value}")
    
    print("\n" + "=" * 50)
    print("Health check example complete!")


async def main():
    """Main function"""
    await example_usage()


if __name__ == "__main__":
    asyncio.run(main())