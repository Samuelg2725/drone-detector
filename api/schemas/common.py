#!/usr/bin/env python3
# drone-detector/api/schemas/common.py
"""
Shared Response Models

This module provides common/shared response models for the Drone Detection System API,
including:
- Standardized success/error responses
- Pagination models
- Timestamps and metadata
- Health check responses
- Version information
- Rate limit responses
- WebSocket message formats
- Event notification schemas
- Filter and query parameters
- Batch operation responses
"""

from typing import Generic, TypeVar, List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator
from pydantic.generics import GenericModel

# ============================================================================
# Type Variables for Generic Responses
# ============================================================================

T = TypeVar('T')


# ============================================================================
# Enums
# ============================================================================

class SortOrder(str, Enum):
    """Sort order options"""
    ASC = "asc"
    DESC = "desc"


class SortField(str, Enum):
    """Common sort fields"""
    TIMESTAMP = "timestamp"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    NAME = "name"
    ID = "id"


class TimeRangePreset(str, Enum):
    """Time range presets"""
    LAST_HOUR = "last_hour"
    LAST_24_HOURS = "last_24_hours"
    LAST_7_DAYS = "last_7_days"
    LAST_30_DAYS = "last_30_days"
    THIS_WEEK = "this_week"
    THIS_MONTH = "this_month"
    CUSTOM = "custom"


# ============================================================================
# Base Response Models
# ============================================================================

class SuccessResponse(BaseModel):
    """Standard success response"""
    success: bool = Field(True, description="Indicates success")
    message: str = Field("Operation completed successfully", description="Response message")
    data: Optional[Any] = Field(None, description="Response data")
    timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "message": "Operation completed successfully",
                "data": {"id": "123", "name": "example"},
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }


class ErrorResponse(BaseModel):
    """Standard error response"""
    success: bool = Field(False, description="Indicates failure")
    error: str = Field(..., description="Error type/code")
    message: str = Field(..., description="Error message")
    status_code: int = Field(..., description="HTTP status code")
    details: Optional[Dict[str, Any]] = Field(None, description="Error details")
    request_id: Optional[str] = Field(None, description="Request ID for tracking")
    timestamp: datetime = Field(default_factory=datetime.now, description="Error timestamp")
    
    class Config:
        schema_extra = {
            "example": {
                "success": False,
                "error": "NOT_FOUND",
                "message": "Resource not found",
                "status_code": 404,
                "details": {"resource_id": "123"},
                "request_id": "req_abc123",
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }


class ValidationErrorResponse(BaseModel):
    """Validation error response"""
    success: bool = Field(False)
    error: str = Field("VALIDATION_ERROR")
    message: str = Field("Validation failed")
    status_code: int = Field(422)
    errors: List[Dict[str, Any]] = Field(..., description="Field validation errors")
    request_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        schema_extra = {
            "example": {
                "success": False,
                "error": "VALIDATION_ERROR",
                "message": "Validation failed",
                "status_code": 422,
                "errors": [
                    {"field": "email", "message": "Invalid email format"},
                    {"field": "age", "message": "Must be at least 18"}
                ],
                "request_id": "req_abc123",
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }


# ============================================================================
# Pagination Models
# ============================================================================

class PaginationParams(BaseModel):
    """Pagination query parameters"""
    page: int = Field(1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(20, ge=1, le=100, description="Items per page")
    sort_by: Optional[str] = Field(None, description="Field to sort by")
    sort_order: SortOrder = Field(SortOrder.DESC, description="Sort order")
    
    @property
    def offset(self) -> int:
        """Calculate offset for database query"""
        return (self.page - 1) * self.page_size
    
    @property
    def limit(self) -> int:
        """Get limit for database query"""
        return self.page_size


class PaginatedResponse(GenericModel, Generic[T]):
    """Generic paginated response"""
    items: List[T] = Field(..., description="List of items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")
    
    @validator('total_pages', always=True)
    def calculate_total_pages(cls, v, values):
        """Calculate total pages from total and page_size"""
        if 'total' in values and 'page_size' in values:
            total = values['total']
            page_size = values['page_size']
            return (total + page_size - 1) // page_size if page_size > 0 else 0
        return v
    
    @validator('has_next', always=True)
    def calculate_has_next(cls, v, values):
        """Calculate has_next from page and total_pages"""
        if 'page' in values and 'total_pages' in values:
            return values['page'] < values['total_pages']
        return v
    
    @validator('has_prev', always=True)
    def calculate_has_prev(cls, v, values):
        """Calculate has_prev from page"""
        if 'page' in values:
            return values['page'] > 1
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "items": [{"id": "1"}, {"id": "2"}],
                "total": 100,
                "page": 1,
                "page_size": 20,
                "total_pages": 5,
                "has_next": True,
                "has_prev": False
            }
        }


class CursorParams(BaseModel):
    """Cursor-based pagination parameters"""
    cursor: Optional[str] = Field(None, description="Pagination cursor")
    limit: int = Field(20, ge=1, le=100, description="Items per page")
    sort_by: Optional[str] = Field(None, description="Field to sort by")
    sort_order: SortOrder = Field(SortOrder.DESC, description="Sort order")


class CursorResponse(GenericModel, Generic[T]):
    """Generic cursor-based pagination response"""
    items: List[T] = Field(..., description="List of items")
    next_cursor: Optional[str] = Field(None, description="Cursor for next page")
    has_more: bool = Field(..., description="Whether there are more items")
    total: Optional[int] = Field(None, description="Total count (if available)")


# ============================================================================
# Common Data Models
# ============================================================================

class TimestampMixin(BaseModel):
    """Mixin with timestamp fields"""
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class Metadata(BaseModel):
    """Generic metadata model"""
    version: str = Field(..., description="API version")
    request_id: str = Field(..., description="Request ID")
    response_time_ms: float = Field(..., description="Response time in milliseconds")
    server_time: datetime = Field(default_factory=datetime.now, description="Server timestamp")


class HealthStatus(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Overall status (healthy, degraded, unhealthy)")
    version: str = Field(..., description="API version")
    uptime_seconds: float = Field(..., description="System uptime in seconds")
    timestamp: datetime = Field(default_factory=datetime.now, description="Health check timestamp")
    components: Dict[str, str] = Field(default_factory=dict, description="Component health status")
    details: Optional[Dict[str, Any]] = Field(None, description="Detailed health information")
    
    class Config:
        schema_extra = {
            "example": {
                "status": "healthy",
                "version": "2.0.0",
                "uptime_seconds": 86400,
                "timestamp": "2024-01-15T10:30:00Z",
                "components": {
                    "database": "healthy",
                    "hardware": "healthy",
                    "external_services": "degraded"
                }
            }
        }


class RateLimitInfo(BaseModel):
    """Rate limit information"""
    limit: int = Field(..., description="Maximum requests per window")
    remaining: int = Field(..., description="Remaining requests in window")
    reset: int = Field(..., description="Seconds until limit resets")
    retry_after: Optional[int] = Field(None, description="Seconds to wait before retry")
    
    class Config:
        schema_extra = {
            "example": {
                "limit": 100,
                "remaining": 87,
                "reset": 45,
                "retry_after": None
            }
        }


class VersionInfo(BaseModel):
    """API version information"""
    version: str = Field(..., description="API version")
    build_date: datetime = Field(..., description="Build timestamp")
    commit_hash: Optional[str] = Field(None, description="Git commit hash")
    environment: str = Field("production", description="Deployment environment")
    features: List[str] = Field(default_factory=list, description="Enabled features")
    
    class Config:
        schema_extra = {
            "example": {
                "version": "2.0.0",
                "build_date": "2024-01-15T10:00:00Z",
                "commit_hash": "abc123def456",
                "environment": "production",
                "features": ["real_time", "geofencing", "remote_id"]
            }
        }


# ============================================================================
# Query Parameter Models
# ============================================================================

class TimeRangeParams(BaseModel):
    """Time range query parameters"""
    start_time: Optional[datetime] = Field(None, description="Start time (ISO format)")
    end_time: Optional[datetime] = Field(None, description="End time (ISO format)")
    preset: Optional[TimeRangePreset] = Field(TimeRangePreset.LAST_24_HOURS, description="Time range preset")
    
    @validator('end_time')
    def validate_end_time(cls, v, values):
        """Validate end time is after start time"""
        if v and values.get('start_time') and v <= values['start_time']:
            raise ValueError('end_time must be after start_time')
        return v
    
    def get_start_time(self) -> datetime:
        """Get resolved start time"""
        if self.start_time:
            return self.start_time
        
        now = datetime.now()
        if self.preset == TimeRangePreset.LAST_HOUR:
            return now - timedelta(hours=1)
        elif self.preset == TimeRangePreset.LAST_24_HOURS:
            return now - timedelta(hours=24)
        elif self.preset == TimeRangePreset.LAST_7_DAYS:
            return now - timedelta(days=7)
        elif self.preset == TimeRangePreset.LAST_30_DAYS:
            return now - timedelta(days=30)
        elif self.preset == TimeRangePreset.THIS_WEEK:
            return now - timedelta(days=now.weekday())
        elif self.preset == TimeRangePreset.THIS_MONTH:
            return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        return now - timedelta(hours=24)
    
    def get_end_time(self) -> datetime:
        """Get resolved end time"""
        if self.end_time:
            return self.end_time
        return datetime.now()


class FilterParams(BaseModel):
    """Generic filter parameters"""
    search: Optional[str] = Field(None, description="Search query")
    ids: Optional[List[str]] = Field(None, description="Filter by IDs")
    exclude_ids: Optional[List[str]] = Field(None, description="Exclude by IDs")
    active: Optional[bool] = Field(None, description="Filter by active status")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values"""
        return {k: v for k, v in self.dict().items() if v is not None}


class BatchOperationRequest(BaseModel):
    """Batch operation request"""
    ids: List[str] = Field(..., description="List of IDs to operate on")
    operation: str = Field(..., description="Operation to perform")
    params: Dict[str, Any] = Field(default_factory=dict, description="Operation parameters")


class BatchOperationResponse(BaseModel):
    """Batch operation response"""
    total: int = Field(..., description="Total items processed")
    successful: int = Field(..., description="Number of successful operations")
    failed: int = Field(..., description="Number of failed operations")
    errors: List[Dict[str, Any]] = Field(default_factory=list, description="Error details")
    
    class Config:
        schema_extra = {
            "example": {
                "total": 10,
                "successful": 9,
                "failed": 1,
                "errors": [
                    {"id": "item_005", "error": "Resource not found"}
                ]
            }
        }


# ============================================================================
# WebSocket Message Models
# ============================================================================

class WebSocketMessageType(str, Enum):
    """WebSocket message types"""
    # Server -> Client
    DETECTION = "detection"
    ALERT = "alert"
    METRICS = "metrics"
    STATUS = "status"
    POSITION = "position"
    SPECTRUM = "spectrum"
    NOTIFICATION = "notification"
    HEARTBEAT = "heartbeat"
    ERROR = "error"
    
    # Client -> Server
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    COMMAND = "command"
    PING = "ping"


class WebSocketMessage(BaseModel):
    """Base WebSocket message"""
    type: WebSocketMessageType = Field(..., description="Message type")
    data: Any = Field(..., description="Message data")
    timestamp: datetime = Field(default_factory=datetime.now, description="Message timestamp")
    message_id: Optional[str] = Field(None, description="Unique message ID")
    
    class Config:
        schema_extra = {
            "example": {
                "type": "detection",
                "data": {"drone_id": "123", "confidence": 0.95},
                "timestamp": "2024-01-15T10:30:00Z",
                "message_id": "msg_abc123"
            }
        }


class DetectionMessage(BaseModel):
    """Detection WebSocket message"""
    type: WebSocketMessageType = WebSocketMessageType.DETECTION
    data: Dict[str, Any] = Field(..., description="Detection data")
    timestamp: datetime = Field(default_factory=datetime.now)
    message_id: str = Field(..., description="Detection ID")


class AlertMessage(BaseModel):
    """Alert WebSocket message"""
    type: WebSocketMessageType = WebSocketMessageType.ALERT
    data: Dict[str, Any] = Field(..., description="Alert data")
    timestamp: datetime = Field(default_factory=datetime.now)
    message_id: str = Field(..., description="Alert ID")


class PositionMessage(BaseModel):
    """Position update WebSocket message"""
    type: WebSocketMessageType = WebSocketMessageType.POSITION
    data: Dict[str, Any] = Field(..., description="Position data")
    timestamp: datetime = Field(default_factory=datetime.now)


class HeartbeatMessage(BaseModel):
    """Heartbeat WebSocket message"""
    type: WebSocketMessageType = WebSocketMessageType.HEARTBEAT
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)


# ============================================================================
# Event Notification Models
# ============================================================================

class EventType(str, Enum):
    """System event types"""
    # Detection events
    DETECTION_CREATED = "detection.created"
    DETECTION_UPDATED = "detection.updated"
    DETECTION_DELETED = "detection.deleted"
    
    # Alert events
    ALERT_GENERATED = "alert.generated"
    ALERT_ACKNOWLEDGED = "alert.acknowledged"
    ALERT_RESOLVED = "alert.resolved"
    ALERT_ESCALATED = "alert.escalated"
    
    # Hardware events
    HARDWARE_CONNECTED = "hardware.connected"
    HARDWARE_DISCONNECTED = "hardware.disconnected"
    HARDWARE_ERROR = "hardware.error"
    
    # System events
    SYSTEM_STARTED = "system.started"
    SYSTEM_STOPPED = "system.stopped"
    CONFIG_CHANGED = "config.changed"


class SystemEvent(BaseModel):
    """System event notification"""
    event_type: EventType = Field(..., description="Event type")
    timestamp: datetime = Field(default_factory=datetime.now)
    source: str = Field(..., description="Event source component")
    data: Dict[str, Any] = Field(default_factory=dict, description="Event data")
    severity: str = Field("info", description="Event severity (info, warning, error)")


# ============================================================================
# Import Models
# ============================================================================

class ImportResult(BaseModel):
    """Import operation result"""
    total: int = Field(..., description="Total records processed")
    imported: int = Field(..., description="Records successfully imported")
    skipped: int = Field(..., description="Records skipped")
    errors: List[Dict[str, Any]] = Field(default_factory=list, description="Import errors")
    
    class Config:
        schema_extra = {
            "example": {
                "total": 100,
                "imported": 95,
                "skipped": 5,
                "errors": [
                    {"row": 23, "error": "Invalid format"},
                    {"row": 45, "error": "Duplicate entry"}
                ]
            }
        }


class ExportOptions(BaseModel):
    """Export options"""
    format: str = Field("json", description="Export format (json, csv, excel)")
    fields: Optional[List[str]] = Field(None, description="Fields to include")
    start_time: Optional[datetime] = Field(None, description="Start time filter")
    end_time: Optional[datetime] = Field(None, description="End time filter")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Additional filters")
    compression: bool = Field(False, description="Compress output")


# ============================================================================
# Utility Functions
# ============================================================================

def create_success_response(data: Any = None, message: str = "Operation completed successfully") -> SuccessResponse:
    """Create a standardized success response"""
    return SuccessResponse(success=True, message=message, data=data)


def create_error_response(error: str, message: str, status_code: int, details: Dict[str, Any] = None, request_id: str = None) -> ErrorResponse:
    """Create a standardized error response"""
    return ErrorResponse(
        success=False,
        error=error,
        message=message,
        status_code=status_code,
        details=details,
        request_id=request_id
    )


def create_paginated_response(items: List[T], total: int, page: int, page_size: int) -> PaginatedResponse[T]:
    """Create a paginated response"""
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    """Example usage of common schemas"""
    
    print("Common Schemas Module Test")
    print("=" * 50)
    
    # Success response
    print("\n1. Success Response:")
    response = create_success_response({"id": "123", "name": "Test"}, "Created successfully")
    print(f"   Success: {response.success}")
    print(f"   Message: {response.message}")
    print(f"   Data: {response.data}")
    
    # Error response
    print("\n2. Error Response:")
    error = create_error_response(
        error="NOT_FOUND",
        message="Resource not found",
        status_code=404,
        details={"resource_id": "123"},
        request_id="req_abc"
    )
    print(f"   Error: {error.error}")
    print(f"   Status: {error.status_code}")
    
    # Paginated response
    print("\n3. Paginated Response:")
    paginated = create_paginated_response(
        items=[{"id": "1"}, {"id": "2"}],
        total=100,
        page=1,
        page_size=20
    )
    print(f"   Items: {len(paginated.items)}")
    print(f"   Total: {paginated.total}")
    print(f"   Has next: {paginated.has_next}")
    
    # Health status
    print("\n4. Health Status:")
    health = HealthStatus(
        status="healthy",
        version="2.0.0",
        uptime_seconds=86400,
        components={
            "database": "healthy",
            "hardware": "healthy"
        }
    )
    print(f"   Status: {health.status}")
    print(f"   Components: {len(health.components)}")
    
    # WebSocket message
    print("\n5. WebSocket Message:")
    ws_msg = DetectionMessage(
        data={"drone_id": "123", "confidence": 0.95},
        message_id="msg_001"
    )
    print(f"   Type: {ws_msg.type}")
    print(f"   Message ID: {ws_msg.message_id}")
    
    # Rate limit info
    print("\n6. Rate Limit Info:")
    rate_limit = RateLimitInfo(limit=100, remaining=87, reset=45)
    print(f"   Limit: {rate_limit.limit}")
    print(f"   Remaining: {rate_limit.remaining}")
    
    # Version info
    print("\n7. Version Info:")
    version = VersionInfo(
        version="2.0.0",
        build_date=datetime.now(),
        commit_hash="abc123",
        environment="development"
    )
    print(f"   Version: {version.version}")
    print(f"   Environment: {version.environment}")
    
    print("\n" + "=" * 50)
    print("Common schemas test complete!")