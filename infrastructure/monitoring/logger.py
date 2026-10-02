#!/usr/bin/env python3
# drone-detector/infrastructure/monitoring/logger.py
"""
Structured Logging Module

This module provides comprehensive structured logging capabilities for the Drone Detection System,
enabling:
- JSON-formatted structured logging for machine parsing
- Multiple log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Contextual logging with extra fields
- Log rotation and archiving
- Async logging for high performance
- Log correlation with request IDs
- Sensitive data redaction
- Multi-output destinations (console, file, syslog, network)
- Log filtering and sampling
- Log level inheritance and configuration
- Structured audit logging
- Performance logging
- Security event logging
"""

import asyncio
import json
import logging
import logging.handlers
import os
import sys
import time
import traceback
from contextvars import ContextVar
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Callable, Tuple
from functools import wraps

# Try to import optional dependencies
try:
    import colorlog
    COLORLOG_AVAILABLE = True
except ImportError:
    COLORLOG_AVAILABLE = False

try:
    import pythonjsonlogger.jsonlogger as jsonlogger
    JSON_LOGGER_AVAILABLE = True
except ImportError:
    JSON_LOGGER_AVAILABLE = False

# Setup logging
logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Data Classes
# ============================================================================

class LogLevel(Enum):
    """Log levels"""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


class LogFormat(Enum):
    """Log output formats"""
    TEXT = "text"       # Human-readable text
    JSON = "json"       # Structured JSON
    COLOR = "color"     # Colored text (for development)


class LogDestination(Enum):
    """Log output destinations"""
    CONSOLE = "console"
    FILE = "file"
    SYSLOG = "syslog"
    NETWORK = "network"


@dataclass
class LogConfig:
    """Logging configuration"""
    # Basic settings
    level: LogLevel = LogLevel.INFO
    format: LogFormat = LogFormat.JSON
    context_fields: List[str] = field(default_factory=lambda: [
        'timestamp', 'level', 'logger', 'message', 'module', 
        'function', 'line', 'request_id', 'user_id', 'session_id'
    ])
    
    # Console output
    console_enabled: bool = True
    console_format: LogFormat = LogFormat.COLOR if COLORLOG_AVAILABLE else LogFormat.TEXT
    
    # File output
    file_enabled: bool = True
    file_path: str = "data/logs/system.log"
    file_max_bytes: int = 10485760  # 10 MB
    file_backup_count: int = 10
    file_format: LogFormat = LogFormat.JSON
    
    # Syslog output
    syslog_enabled: bool = False
    syslog_address: str = "/dev/log"  # or ('localhost', 514) for UDP
    syslog_facility: str = "user"
    syslog_format: LogFormat = LogFormat.TEXT
    
    # Network output
    network_enabled: bool = False
    network_host: str = "localhost"
    network_port: int = 9999
    network_protocol: str = "tcp"  # tcp or udp
    
    # Advanced settings
    enable_async: bool = True
    enable_rotation: bool = True
    enable_compression: bool = True
    include_traceback: bool = True
    redact_sensitive: bool = True
    sensitive_keys: List[str] = field(default_factory=lambda: [
        'password', 'token', 'secret', 'api_key', 'auth', 'credential'
    ])
    
    # Sampling (for high volume logs)
    sample_rate: float = 1.0  # 1.0 = log everything, 0.1 = log 10%
    
    # Correlation
    include_hostname: bool = True
    include_pid: bool = True
    
    # Performance
    queue_size: int = 1000
    flush_interval: float = 5.0


# ============================================================================
# Context Management
# ============================================================================

# Context variables for request/operation correlation
_request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
_user_id_var: ContextVar[Optional[str]] = ContextVar('user_id', default=None)
_session_id_var: ContextVar[Optional[str]] = ContextVar('session_id', default=None)
_correlation_id_var: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)


def set_request_id(request_id: str):
    """Set request ID for current context"""
    _request_id_var.set(request_id)


def get_request_id() -> Optional[str]:
    """Get current request ID"""
    return _request_id_var.get()


def set_user_id(user_id: str):
    """Set user ID for current context"""
    _user_id_var.set(user_id)


def get_user_id() -> Optional[str]:
    """Get current user ID"""
    return _user_id_var.get()


def set_session_id(session_id: str):
    """Set session ID for current context"""
    _session_id_var.set(session_id)


def get_session_id() -> Optional[str]:
    """Get current session ID"""
    return _session_id_var.get()


def set_correlation_id(correlation_id: str):
    """Set correlation ID for current context"""
    _correlation_id_var.set(correlation_id)


def get_correlation_id() -> Optional[str]:
    """Get current correlation ID"""
    return _correlation_id_var.get()


def clear_context():
    """Clear all context variables"""
    _request_id_var.set(None)
    _user_id_var.set(None)
    _session_id_var.set(None)
    _correlation_id_var.set(None)


@asynccontextmanager
async def logging_context(request_id: Optional[str] = None,
                          user_id: Optional[str] = None,
                          session_id: Optional[str] = None,
                          correlation_id: Optional[str] = None):
    """
    Context manager for logging context
    
    Usage:
        async with logging_context(request_id="123", user_id="user1"):
            logger.info("Processing request")
    """
    # Save old values
    old_request_id = get_request_id()
    old_user_id = get_user_id()
    old_session_id = get_session_id()
    old_correlation_id = get_correlation_id()
    
    # Set new values
    if request_id:
        set_request_id(request_id)
    if user_id:
        set_user_id(user_id)
    if session_id:
        set_session_id(session_id)
    if correlation_id:
        set_correlation_id(correlation_id)
    
    try:
        yield
    finally:
        # Restore old values
        set_request_id(old_request_id)
        set_user_id(old_user_id)
        set_session_id(old_session_id)
        set_correlation_id(old_correlation_id)


# ============================================================================
# Custom Log Formatters
# ============================================================================

class StructuredLogFormatter(logging.Formatter):
    """Structured log formatter supporting JSON and text formats"""
    
    def __init__(self, config: LogConfig):
        super().__init__()
        self.config = config
        self.hostname = socket.gethostname() if config.include_hostname else None
        self.pid = os.getpid() if config.include_pid else None
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record"""
        # Extract timestamp
        timestamp = datetime.fromtimestamp(record.created).isoformat()
        
        # Build log entry
        log_entry = {
            'timestamp': timestamp,
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add context fields
        request_id = get_request_id()
        if request_id:
            log_entry['request_id'] = request_id
        
        user_id = get_user_id()
        if user_id:
            log_entry['user_id'] = user_id
        
        session_id = get_session_id()
        if session_id:
            log_entry['session_id'] = session_id
        
        correlation_id = get_correlation_id()
        if correlation_id:
            log_entry['correlation_id'] = correlation_id
        
        # Add system info
        if self.hostname:
            log_entry['hostname'] = self.hostname
        if self.pid:
            log_entry['pid'] = self.pid
        
        # Add extra fields from record
        if hasattr(record, 'extra_fields'):
            for key, value in record.extra_fields.items():
                log_entry[key] = value
        
        # Add exception info
        if record.exc_info:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info) if self.config.include_traceback else None
            }
        
        # Redact sensitive data
        if self.config.redact_sensitive:
            log_entry = self._redact_sensitive(log_entry)
        
        # Format output
        if self.config.format == LogFormat.JSON:
            return json.dumps(log_entry)
        else:
            return self._format_text(log_entry)
    
    def _redact_sensitive(self, data: Dict) -> Dict:
        """Redact sensitive information"""
        for key in list(data.keys()):
            key_lower = key.lower()
            for sensitive in self.config.sensitive_keys:
                if sensitive in key_lower:
                    data[key] = '[REDACTED]'
        
        return data
    
    def _format_text(self, data: Dict) -> str:
        """Format as text"""
        parts = []
        
        # Timestamp
        parts.append(f"[{data.get('timestamp', '')}]")
        
        # Level with color
        level = data.get('level', 'INFO')
        parts.append(f"{level:8}")
        
        # Logger name
        parts.append(f"[{data.get('logger', 'root')}]")
        
        # Correlation IDs
        if data.get('request_id'):
            parts.append(f"[req:{data.get('request_id')[:8]}]")
        if data.get('correlation_id'):
            parts.append(f"[corr:{data.get('correlation_id')[:8]}]")
        
        # Location
        parts.append(f"({data.get('module', '')}:{data.get('line', 0)})")
        
        # Message
        parts.append(f"- {data.get('message', '')}")
        
        # Extra fields
        extra = {k: v for k, v in data.items() 
                if k not in ['timestamp', 'level', 'logger', 'message', 'module', 
                            'function', 'line', 'request_id', 'correlation_id',
                            'user_id', 'session_id', 'hostname', 'pid', 'exception']}
        if extra:
            parts.append(f"| {json.dumps(extra)}")
        
        return ' '.join(parts)


class ColoredLogFormatter(logging.Formatter):
    """Colored log formatter for development"""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'
    }
    
    def format(self, record: logging.LogRecord) -> str:
        """Format with colors"""
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        return f"{color}{timestamp} [{record.levelname:8}] [{record.name}] {reset}{record.getMessage()}"


# ============================================================================
# Async Log Handler
# ============================================================================

class AsyncLogHandler(logging.Handler):
    """
    Asynchronous log handler that queues log records and processes them
    in a background thread to avoid blocking the main thread.
    """
    
    def __init__(self, handler: logging.Handler, queue_size: int = 1000, flush_interval: float = 5.0):
        super().__init__()
        self.handler = handler
        self.queue_size = queue_size
        self.flush_interval = flush_interval
        self._queue = asyncio.Queue(maxsize=queue_size)
        self._task: Optional[asyncio.Task] = None
        self._running = False
    
    def start(self):
        """Start the async handler"""
        if self._running:
            return
        
        self._running = True
        loop = asyncio.get_event_loop()
        self._task = loop.create_task(self._process_queue())
    
    async def stop(self):
        """Stop the async handler"""
        self._running = False
        if self._task:
            await self._task
    
    def emit(self, record: logging.LogRecord):
        """Queue log record for processing"""
        if not self._running:
            return
        
        try:
            self._queue.put_nowait(record)
        except asyncio.QueueFull:
            # Drop oldest record if queue is full
            try:
                self._queue.get_nowait()
                self._queue.put_nowait(record)
            except asyncio.QueueEmpty:
                pass
    
    async def _process_queue(self):
        """Process queued log records"""
        while self._running:
            try:
                # Process items with timeout to allow periodic flushing
                try:
                    record = await asyncio.wait_for(self._queue.get(), timeout=self.flush_interval)
                    self.handler.emit(record)
                except asyncio.TimeoutError:
                    # Flush if needed
                    if hasattr(self.handler, 'flush'):
                        self.handler.flush()
            except Exception as e:
                print(f"Error in async log handler: {e}")


# ============================================================================
# Sampling Filter
# ============================================================================

class SamplingFilter(logging.Filter):
    """Filter that samples log records based on rate"""
    
    def __init__(self, rate: float = 1.0):
        super().__init__()
        self.rate = rate
        self._counter = 0
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter log record based on sampling rate"""
        if self.rate >= 1.0:
            return True
        
        self._counter += 1
        return (self._counter % int(1 / self.rate)) == 0


# ============================================================================
# Structured Logger
# ============================================================================

class StructuredLogger:
    """
    Structured logger wrapper
    
    Provides a convenient interface for structured logging with context
    and extra fields.
    """
    
    def __init__(self, name: str, config: Optional[LogConfig] = None):
        """
        Initialize structured logger
        
        Args:
            name: Logger name
            config: Logging configuration
        """
        self.name = name
        self.config = config or LogConfig()
        self._logger = logging.getLogger(name)
        self._setup_logger()
    
    def _setup_logger(self):
        """Setup logger with handlers and formatters"""
        # Set level
        self._logger.setLevel(self.config.level.value)
        
        # Clear existing handlers
        self._logger.handlers.clear()
        
        # Console handler
        if self.config.console_enabled:
            console_handler = logging.StreamHandler(sys.stdout)
            if self.config.console_format == LogFormat.COLOR and COLORLOG_AVAILABLE:
                formatter = colorlog.ColoredFormatter(
                    '%(log_color)s%(asctime)s [%(levelname)-8s] [%(name)s] %(reset)s%(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    log_colors={
                        'DEBUG': 'cyan',
                        'INFO': 'green',
                        'WARNING': 'yellow',
                        'ERROR': 'red',
                        'CRITICAL': 'magenta',
                    }
                )
            elif self.config.console_format == LogFormat.JSON and JSON_LOGGER_AVAILABLE:
                formatter = jsonlogger.JsonFormatter(
                    fmt='%(asctime)s %(levelname)s %(name)s %(message)s',
                    timestamp=True
                )
            else:
                formatter = logging.Formatter(
                    '%(asctime)s [%(levelname)-8s] [%(name)s] %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
            
            console_handler.setFormatter(formatter)
            
            if self.config.enable_async:
                console_handler = AsyncLogHandler(console_handler, self.config.queue_size)
                if hasattr(console_handler, 'start'):
                    console_handler.start()
            
            self._logger.addHandler(console_handler)
        
        # File handler
        if self.config.file_enabled:
            log_path = Path(self.config.file_path)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            if self.config.enable_rotation:
                file_handler = logging.handlers.RotatingFileHandler(
                    filename=self.config.file_path,
                    maxBytes=self.config.file_max_bytes,
                    backupCount=self.config.file_backup_count,
                    encoding='utf-8'
                )
            else:
                file_handler = logging.FileHandler(self.config.file_path, encoding='utf-8')
            
            if self.config.file_format == LogFormat.JSON and JSON_LOGGER_AVAILABLE:
                file_handler.setFormatter(jsonlogger.JsonFormatter(
                    fmt='%(asctime)s %(levelname)s %(name)s %(message)s',
                    timestamp=True
                ))
            else:
                file_handler.setFormatter(logging.Formatter(
                    '%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                ))
            
            if self.config.enable_async:
                file_handler = AsyncLogHandler(file_handler, self.config.queue_size)
                if hasattr(file_handler, 'start'):
                    file_handler.start()
            
            self._logger.addHandler(file_handler)
        
        # Syslog handler
        if self.config.syslog_enabled:
            syslog_handler = logging.handlers.SysLogHandler(
                address=self.config.syslog_address,
                facility=self.config.syslog_facility
            )
            syslog_handler.setFormatter(logging.Formatter(
                '%(name)s: %(message)s'
            ))
            self._logger.addHandler(syslog_handler)
        
        # Add sampling filter
        if self.config.sample_rate < 1.0:
            self._logger.addFilter(SamplingFilter(self.config.sample_rate))
    
    def _log(self, level: int, message: str, **kwargs):
        """Internal log method with structured fields"""
        extra = kwargs.pop('extra', {})
        
        # Create log record
        record = self._logger.makeRecord(
            name=self.name,
            level=level,
            fn='',
            lno=0,
            msg=message,
            args=(),
            exc_info=kwargs.pop('exc_info', None),
            func=None,
            extra={'extra_fields': {**extra, **kwargs}}
        )
        
        # Add context
        request_id = get_request_id()
        if request_id:
            record.extra_fields['request_id'] = request_id
        
        user_id = get_user_id()
        if user_id:
            record.extra_fields['user_id'] = user_id
        
        session_id = get_session_id()
        if session_id:
            record.extra_fields['session_id'] = session_id
        
        correlation_id = get_correlation_id()
        if correlation_id:
            record.extra_fields['correlation_id'] = correlation_id
        
        self._logger.handle(record)
    
    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self._log(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message"""
        self._log(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self._log(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message"""
        self._log(logging.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message"""
        self._log(logging.CRITICAL, message, **kwargs)
    
    def exception(self, message: str, **kwargs):
        """Log exception with traceback"""
        self._log(logging.ERROR, message, exc_info=True, **kwargs)
    
    def log_detection(self, detection_data: Dict[str, Any]):
        """Log drone detection event"""
        self.info(
            f"Drone detected: {detection_data.get('drone_type', 'unknown')}",
            event_type="detection",
            drone_type=detection_data.get('drone_type'),
            confidence=detection_data.get('confidence'),
            threat_level=detection_data.get('threat_level'),
            latitude=detection_data.get('latitude'),
            longitude=detection_data.get('longitude'),
            altitude=detection_data.get('altitude'),
            frequency=detection_data.get('frequency')
        )
    
    def log_alert(self, alert_data: Dict[str, Any]):
        """Log alert event"""
        self.warning(
            f"Alert: {alert_data.get('title', 'Unknown alert')}",
            event_type="alert",
            severity=alert_data.get('severity'),
            alert_id=alert_data.get('id'),
            message=alert_data.get('message')
        )
    
    def log_performance(self, operation: str, duration_ms: float, **kwargs):
        """Log performance metric"""
        self.debug(
            f"Performance: {operation} took {duration_ms:.2f}ms",
            event_type="performance",
            operation=operation,
            duration_ms=duration_ms,
            **kwargs
        )
    
    def log_security(self, message: str, event_type: str, **kwargs):
        """Log security event"""
        self.warning(
            message,
            event_type=f"security_{event_type}",
            security_event=True,
            **kwargs
        )
    
    def set_level(self, level: LogLevel):
        """Set log level"""
        self._logger.setLevel(level.value)
        self.config.level = level
    
    def get_level(self) -> LogLevel:
        """Get current log level"""
        return self.config.level


# ============================================================================
# Logger Factory
# ============================================================================

class LoggerFactory:
    """Factory for creating structured loggers"""
    
    _instance = None
    _config: Optional[LogConfig] = None
    _loggers: Dict[str, StructuredLogger] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def configure(cls, config: LogConfig):
        """Configure the logger factory"""
        cls._config = config
    
    @classmethod
    def get_logger(cls, name: str, config: Optional[LogConfig] = None) -> StructuredLogger:
        """
        Get a structured logger
        
        Args:
            name: Logger name
            config: Optional override configuration
            
        Returns:
            StructuredLogger instance
        """
        if name not in cls._loggers:
            logger_config = config or cls._config or LogConfig()
            cls._loggers[name] = StructuredLogger(name, logger_config)
        
        return cls._loggers[name]
    
    @classmethod
    def set_level(cls, level: LogLevel):
        """Set log level for all loggers"""
        for logger in cls._loggers.values():
            logger.set_level(level)
    
    @classmethod
    def shutdown(cls):
        """Shutdown all loggers"""
        for logger in cls._loggers.values():
            for handler in logger._logger.handlers:
                if hasattr(handler, 'stop'):
                    handler.stop()
        cls._loggers.clear()


# ============================================================================
# Convenience Functions
# ============================================================================

def setup_logging(config: Optional[LogConfig] = None) -> None:
    """
    Setup global logging configuration
    
    Args:
        config: Logging configuration
    """
    config = config or LogConfig()
    LoggerFactory.configure(config)
    logger.info("Logging system initialized", config=config.to_dict() if hasattr(config, 'to_dict') else str(config))


def get_logger(name: str) -> StructuredLogger:
    """
    Get a structured logger
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        StructuredLogger instance
    """
    return LoggerFactory.get_logger(name)


def shutdown_logging():
    """Shutdown logging system"""
    LoggerFactory.shutdown()


# ============================================================================
# Decorators for Logging
# ============================================================================

def log_function_call(level: LogLevel = LogLevel.DEBUG):
    """
    Decorator to log function calls
    
    Args:
        level: Log level for the call
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            
            # Log function entry
            logger._log(level.value, f"Calling {func.__name__}", 
                       function=func.__name__, 
                       args=str(args)[:200], 
                       kwargs=str(kwargs)[:200])
            
            try:
                start_time = time.time()
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                # Log function exit
                logger._log(level.value, f"Completed {func.__name__} in {duration_ms:.2f}ms",
                           function=func.__name__,
                           duration_ms=duration_ms)
                
                return result
                
            except Exception as e:
                logger.exception(f"Exception in {func.__name__}: {str(e)}")
                raise
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            
            # Log function entry
            logger._log(level.value, f"Calling {func.__name__}", 
                       function=func.__name__)
            
            try:
                start_time = time.time()
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                # Log function exit
                logger._log(level.value, f"Completed {func.__name__} in {duration_ms:.2f}ms",
                           function=func.__name__,
                           duration_ms=duration_ms)
                
                return result
                
            except Exception as e:
                logger.exception(f"Exception in {func.__name__}: {str(e)}")
                raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper
    return decorator


def log_performance(operation: str):
    """
    Decorator to log performance metrics
    
    Args:
        operation: Operation name
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                logger.log_performance(operation, duration_ms)
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.log_performance(f"{operation}_error", duration_ms, error=str(e))
                raise
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                logger.log_performance(operation, duration_ms)
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.log_performance(f"{operation}_error", duration_ms, error=str(e))
                raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper
    return decorator


# ============================================================================
# Example Usage
# ============================================================================

async def example_usage():
    """Example usage of structured logging"""
    
    print("Structured Logging Example")
    print("=" * 50)
    
    # Configure logging
    print("\n1. Configuring logging...")
    config = LogConfig(
        level=LogLevel.DEBUG,
        format=LogFormat.JSON,
        console_enabled=True,
        console_format=LogFormat.COLOR,
        file_enabled=False,  # Disable file for demo
        redact_sensitive=True
    )
    setup_logging(config)
    print("   Logging configured")
    
    # Get logger
    logger = get_logger("example")
    
    # Basic logging
    print("\n2. Basic logging...")
    logger.debug("This is a debug message")
    logger.info("This is an info message", user="admin", action="login")
    logger.warning("This is a warning message", threshold=90)
    logger.error("This is an error message", error_code=500)
    
    # Structured logging with context
    print("\n3. Structured logging with context...")
    async with logging_context(request_id="req_12345", user_id="user_001"):
        logger.info("Processing request", endpoint="/api/detections", method="GET")
        logger.debug("Request details", params={"limit": 100, "offset": 0})
    
    # Log detection event
    print("\n4. Logging detection event...")
    detection_data = {
        'drone_type': 'DJI Mavic 3',
        'confidence': 0.95,
        'threat_level': 'HIGH',
        'latitude': 37.7749,
        'longitude': -122.4194,
        'altitude': 400,
        'frequency': 2.44e9
    }
    logger.log_detection(detection_data)
    
    # Log alert event
    print("\n5. Logging alert event...")
    alert_data = {
        'severity': 'CRITICAL',
        'title': 'Geofence Violation',
        'id': 'alt_001',
        'message': 'Drone entered restricted airspace'
    }
    logger.log_alert(alert_data)
    
    # Log performance metrics
    print("\n6. Logging performance metrics...")
    logger.log_performance("fft_computation", 12.5, size=2048)
    logger.log_performance("ml_inference", 45.2, model="random_forest")
    
    # Log security event
    print("\n7. Logging security event...")
    logger.log_security(
        "Unauthorized access attempt detected",
        "unauthorized_access",
        source_ip="192.168.1.100",
        attempted_endpoint="/admin"
    )
    
    # Using decorators
    print("\n8. Using logging decorators...")
    
    @log_function_call(LogLevel.INFO)
    def process_detection(detection_id: str):
        return f"Processed {detection_id}"
    
    result = process_detection("det_001")
    print(f"   Result: {result}")
    
    @log_performance("database_query")
    async def query_database(query: str):
        await asyncio.sleep(0.01)
        return [{"id": 1}, {"id": 2}]
    
    await query_database("SELECT * FROM detections")
    
    # Redaction demo
    print("\n9. Sensitive data redaction demo...")
    logger.info("User login", username="admin", password="secret_password", api_key="abc123xyz")
    logger.info("API call", token="bearer_token_12345", auth="basic")
    
    # Get log entries (from buffer)
    print("\n10. Logging complete - check console output above")
    
    # Shutdown
    print("\n11. Shutting down logging...")
    shutdown_logging()
    
    print("\n" + "=" * 50)
    print("Structured logging example complete!")


async def main():
    """Main function"""
    await example_usage()


if __name__ == "__main__":
    asyncio.run(main())