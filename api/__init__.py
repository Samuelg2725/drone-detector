#!/usr/bin/env python3
"""
API Layer for Drone Detector System

This module provides the interface layer for external communication including:
- REST API endpoints (FastAPI)
- WebSocket connections for real-time data
- Request/response models (Pydantic schemas)
- Authentication and authorization
- Middleware (CORS, rate limiting, logging)

The API layer handles all external requests and translates them to
application layer use cases.
"""

from typing import Dict, Any, Optional

# Version information
__version__ = '1.0.0'

# ============================================================================
# Exports - Main Application
# ============================================================================

from api.main import app, create_application

# ============================================================================
# Exports - Routes
# ============================================================================

from api.routes import (
    spectrum,
    detection,
    hardware,
    system,
    map,
    analytics,
    config,
    auth
)

# ============================================================================
# Exports - Schemas
# ============================================================================

from api.schemas import (
    spectrum as spectrum_schemas,
    detection as detection_schemas,
    config as config_schemas,
    map as map_schemas,
    common as common_schemas
)

# ============================================================================
# Exports - Dependencies
# ============================================================================

from api.dependencies import (
    get_current_user,
    get_current_active_user,
    get_current_admin_user,
    get_database,
    get_redis,
    get_hardware,
    get_event_bus,
    get_detection_service,
    get_alert_service
)

# ============================================================================
# Exports - Middleware
# ============================================================================

from api.middleware import (
    RateLimitMiddleware,
    LoggingMiddleware,
    SecurityMiddleware,
    CORSMiddleware,
    RequestIDMiddleware
)

# ============================================================================
# Module Configuration
# ============================================================================

__all__ = [
    # Main application
    'app',
    'create_application',
    
    # Routes
    'spectrum',
    'detection', 
    'hardware',
    'system',
    'map',
    'analytics',
    'config',
    'auth',
    
    # Schemas
    'spectrum_schemas',
    'detection_schemas',
    'config_schemas',
    'map_schemas',
    'common_schemas',
    
    # Dependencies
    'get_current_user',
    'get_current_active_user',
    'get_current_admin_user',
    'get_database',
    'get_redis',
    'get_hardware',
    'get_event_bus',
    'get_detection_service',
    'get_alert_service',
    
    # Middleware
    'RateLimitMiddleware',
    'LoggingMiddleware',
    'SecurityMiddleware',
    'CORSMiddleware',
    'RequestIDMiddleware',
]

# ============================================================================
# API Configuration
# ============================================================================

DEFAULT_API_CONFIG = {
    'title': 'Drone Detector API',
    'description': 'Advanced Drone Detection System API',
    'version': __version__,
    'docs_url': '/docs',
    'redoc_url': '/redoc',
    'openapi_url': '/openapi.json',
    'host': '0.0.0.0',
    'port': 8888,
    'reload': False,
    'workers': 4,
    'cors': {
        'allowed_origins': ['*'],
        'allowed_methods': ['*'],
        'allowed_headers': ['*']
    },
    'rate_limits': {
        'default': '100/minute',
        'authenticated': '1000/minute',
        'admin': '5000/minute'
    },
    'ws': {
        'path': '/ws',
        'max_queue_size': 100,
        'ping_interval': 20,
        'ping_timeout': 20
    }
}

# ============================================================================
# API Status Codes
# ============================================================================

class StatusCode:
    """HTTP status codes used by the API"""
    
    # Success
    OK = 200
    CREATED = 201
    ACCEPTED = 202
    NO_CONTENT = 204
    
    # Client Error
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    METHOD_NOT_ALLOWED = 405
    CONFLICT = 409
    UNPROCESSABLE_ENTITY = 422
    TOO_MANY_REQUESTS = 429
    
    # Server Error
    INTERNAL_SERVER_ERROR = 500
    NOT_IMPLEMENTED = 501
    BAD_GATEWAY = 502
    SERVICE_UNAVAILABLE = 503
    GATEWAY_TIMEOUT = 504


# ============================================================================
# API Event Types
# ============================================================================

class APIEventType:
    """WebSocket event types"""
    
    # Connection events
    CONNECT = 'connect'
    DISCONNECT = 'disconnect'
    AUTHENTICATE = 'authenticate'
    
    # Subscription events
    SUBSCRIBE = 'subscribe'
    UNSUBSCRIBE = 'unsubscribe'
    
    # Data events
    DETECTION = 'detection'
    ALERT = 'alert'
    SPECTRUM = 'spectrum'
    SYSTEM_STATUS = 'system_status'
    HARDWARE_STATUS = 'hardware_status'
    
    # Command events
    COMMAND = 'command'
    COMMAND_RESPONSE = 'command_response'
    
    # Control events
    HEARTBEAT = 'heartbeat'
    ERROR = 'error'
    PONG = 'pong'


# ============================================================================
# API Error Responses
# ============================================================================

class APIError:
    """Standardized error response format"""
    
    def __init__(self, code: str, message: str, details: Optional[Dict] = None):
        self.code = code
        self.message = message
        self.details = details or {}
    
    def to_dict(self) -> Dict:
        """Convert error to dictionary"""
        return {
            'status': 'error',
            'error': {
                'code': self.code,
                'message': self.message,
                'details': self.details
            }
        }


class APIErrors:
    """Common API error instances"""
    
    # Authentication errors
    INVALID_CREDENTIALS = APIError(
        'AUTH_001',
        'Invalid username or password'
    )
    TOKEN_EXPIRED = APIError(
        'AUTH_002',
        'Authentication token has expired'
    )
    INSUFFICIENT_PERMISSIONS = APIError(
        'AUTH_003',
        'Insufficient permissions for this operation'
    )
    INVALID_API_KEY = APIError(
        'AUTH_004',
        'Invalid API key'
    )
    
    # Validation errors
    MISSING_FIELD = APIError(
        'VALID_001',
        'Required field is missing'
    )
    INVALID_TYPE = APIError(
        'VALID_002',
        'Field has invalid type'
    )
    VALUE_OUT_OF_RANGE = APIError(
        'VALID_003',
        'Value is outside allowed range'
    )
    
    # Resource errors
    NOT_FOUND = APIError(
        'RES_001',
        'Requested resource not found'
    )
    ALREADY_EXISTS = APIError(
        'RES_002',
        'Resource already exists'
    )
    CONFLICT = APIError(
        'RES_003',
        'Resource conflict'
    )
    
    # Hardware errors
    HARDWARE_NOT_CONNECTED = APIError(
        'HW_001',
        'Hardware device not connected'
    )
    HARDWARE_BUSY = APIError(
        'HW_002',
        'Hardware device is busy'
    )
    HARDWARE_NOT_SUPPORTED = APIError(
        'HW_003',
        'Hardware device not supported'
    )
    
    # Rate limiting
    RATE_LIMIT_EXCEEDED = APIError(
        'RATE_001',
        'Rate limit exceeded. Please try again later.'
    )
    
    # Server errors
    INTERNAL_ERROR = APIError(
        'API_001',
        'Internal server error'
    )
    SERVICE_UNAVAILABLE = APIError(
        'API_002',
        'Service temporarily unavailable'
    )


# ============================================================================
# API Response Helpers
# ============================================================================

def success_response(data: Any, meta: Optional[Dict] = None) -> Dict:
    """
    Create a standardized success response.
    
    Args:
        data: Response data
        meta: Optional metadata (pagination, timestamps, etc.)
    
    Returns:
        Standardized success response dictionary
        
    Example:
        >>> response = success_response({'detection_id': '123'}, {'timestamp': '2024-01-01T00:00:00Z'})
        >>> print(response)
        {
            'status': 'success',
            'data': {'detection_id': '123'},
            'meta': {'timestamp': '2024-01-01T00:00:00Z'}
        }
    """
    from datetime import datetime
    
    response = {
        'status': 'success',
        'data': data
    }
    
    if meta is None:
        meta = {}
    
    # Add timestamp if not provided
    if 'timestamp' not in meta:
        meta['timestamp'] = datetime.utcnow().isoformat()
    
    if meta:
        response['meta'] = meta
    
    return response


def paginated_response(items: list, total: int, page: int, per_page: int) -> Dict:
    """
    Create a paginated success response.
    
    Args:
        items: List of items for current page
        total: Total number of items
        page: Current page number
        per_page: Items per page
    
    Returns:
        Paginated response dictionary
    """
    pages = (total + per_page - 1) // per_page if per_page > 0 else 1
    
    meta = {
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total,
            'pages': pages,
            'has_next': page < pages,
            'has_prev': page > 1
        }
    }
    
    return success_response(items, meta)


def error_response(error: APIError, status_code: int = 400) -> Dict:
    """
    Create a standardized error response.
    
    Args:
        error: APIError instance
        status_code: HTTP status code (default: 400)
    
    Returns:
        Standardized error response dictionary
    """
    from datetime import datetime
    
    response = error.to_dict()
    response['meta'] = {
        'timestamp': datetime.utcnow().isoformat(),
        'status_code': status_code
    }
    
    return response


# ============================================================================
# API Module Logger
# ============================================================================

import logging

logger = logging.getLogger(__name__)

def setup_module():
    """Setup API module logging and configuration."""
    logger.info("API module loaded (version %s)", __version__)
    
    # Check for optional dependencies
    try:
        from fastapi import FastAPI
        logger.debug("FastAPI available for API endpoints")
    except ImportError:
        logger.warning("FastAPI not available - API endpoints disabled")
    
    try:
        from websockets import connect
        logger.debug("WebSocket support available")
    except ImportError:
        logger.warning("WebSocket not available - real-time features limited")

# Run module setup on import
setup_module()