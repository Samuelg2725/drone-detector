#!/usr/bin/env python3
# drone-detector/api/schemas/__init__.py
"""
API Schemas Module

This module exports all Pydantic models (request/response schemas) for the Drone Detection System API,
organized by domain:
- Common schemas (shared across endpoints)
- Detection schemas
- Spectrum schemas
- Hardware schemas
- Map/GeoJSON schemas
- Configuration schemas
- Authentication schemas

All schemas include validation, serialization, and OpenAPI documentation.
"""

from typing import Dict, Any, List, Optional, Union

# ============================================================================
# Common Schemas
# ============================================================================

from .common import (
    # Base responses
    SuccessResponse,
    ErrorResponse,
    ValidationErrorResponse,
    
    # Pagination
    PaginationParams,
    PaginatedResponse,
    CursorParams,
    CursorResponse,
    
    # Common models
    TimestampMixin,
    Metadata,
    HealthStatus,
    RateLimitInfo,
    VersionInfo,
    
    # Query parameters
    TimeRangeParams,
    FilterParams,
    SortOrder,
    SortField,
    TimeRangePreset,
    
    # Batch operations
    BatchOperationRequest,
    BatchOperationResponse,
    
    # Import/Export
    ImportResult,
    ExportOptions,
    
    # WebSocket
    WebSocketMessage,
    WebSocketMessageType,
    DetectionMessage,
    AlertMessage,
    PositionMessage,
    HeartbeatMessage,
    
    # Events
    EventType,
    SystemEvent,
    
    # Utilities
    create_success_response,
    create_error_response,
    create_paginated_response
)

# ============================================================================
# Detection Schemas
# ============================================================================

from .detection import (
    # Detection models
    DetectionBase,
    DetectionCreate,
    DetectionUpdate,
    DetectionResponse,
    DetectionDetailResponse,
    
    # Detection filters
    DetectionFilterParams,
    
    # Threat assessment
    ThreatLevel,
    ThreatAssessmentRequest,
    ThreatAssessmentResponse,
    
    # Remote ID
    RemoteIDData,
    RemoteIDMessageResponse,
    RemoteIDSessionResponse,
    
    # Detection events
    DetectionEventType,
    DetectionEventResponse,
    
    # Batch detection
    BatchDetectionRequest,
    BatchDetectionResponse
)

# ============================================================================
# Spectrum Schemas
# ============================================================================

from .spectrum import (
    # Spectrum models
    SpectrumRequest,
    SpectrumResponse,
    SpectrumDataPoint,
    SpectrumMetadata,
    
    # FFT/PSD
    FFTRequest,
    FFTResponse,
    PSDRequest,
    PSDResponse,
    
    # Waterfall
    WaterfallRequest,
    WaterfallResponse,
    WaterfallDataPoint,
    
    # Peak detection
    PeakDetectionRequest,
    PeakDetectionResponse,
    PeakInfo,
    
    # Signal analysis
    SignalAnalysisRequest,
    SignalAnalysisResponse,
    ModulationInfo,
    InterferenceInfo,
    
    # Spectrum filters
    SpectrumFilterParams
)

# ============================================================================
# Hardware Schemas
# ============================================================================

from .hardware import (
    # Device models
    DeviceInfo,
    DeviceStatus,
    DeviceCapabilities,
    
    # Control requests
    TuneRequest,
    GainRequest,
    SampleRateRequest,
    ScanRequest,
    
    # Antenna models
    AntennaInfo,
    AntennaConfig,
    AntennaStatus,
    AntennaSwitchRequest,
    
    # Recording
    RecordingRequest,
    RecordingResponse,
    RecordingMetadata,
    
    # Calibration
    CalibrationRequest,
    CalibrationResponse,
    
    # Hardware status
    HardwareStatusResponse,
    HardwareMetricsResponse
)

# ============================================================================
# Map Schemas (GeoJSON)
# ============================================================================

from .map import (
    # GeoJSON base types
    Position,
    BoundingBox,
    
    # Geometry types
    PointGeometry,
    LineStringGeometry,
    PolygonGeometry,
    MultiPointGeometry,
    MultiLineStringGeometry,
    MultiPolygonGeometry,
    GeometryCollection,
    
    # Feature models
    GeoJSONFeature,
    GeoJSONFeatureCollection,
    
    # Properties
    DroneProperties,
    GeofenceProperties,
    TrackProperties,
    HeatmapProperties,
    
    # Specialized responses
    DronePositionResponse,
    DroneTracksResponse,
    GeofenceZonesResponse,
    DetectionHeatmapResponse,
    LiveTrackResponse,
    ProximityAlert,
    AreaCoverageResponse,
    
    # Request models
    GeofenceCreateRequest,
    GeofenceUpdateRequest,
    TrackQueryParams,
    HeatmapQueryParams,
    
    # Zone types
    ThreatZoneType,
    DroneStatus,
    
    # Utilities
    create_point_feature,
    create_line_feature,
    create_polygon_feature,
    create_feature_collection
)

# ============================================================================
# Configuration Schemas
# ============================================================================

from .config import (
    # System config
    SystemConfig,
    SystemConfigUpdate,
    SystemConfigResponse,
    
    # Frequency bands
    FrequencyBand,
    FrequencyBandCreate,
    FrequencyBandUpdate,
    FrequencyBandResponse,
    
    # Alert rules
    AlertRule,
    AlertRuleCreate,
    AlertRuleUpdate,
    AlertRuleResponse,
    
    # Drone signatures
    DroneSignature,
    DroneSignatureCreate,
    DroneSignatureUpdate,
    DroneSignatureResponse,
    
    # User preferences
    UserPreferences,
    UserPreferencesUpdate,
    
    # Notification settings
    NotificationSettings,
    NotificationSettingsUpdate,
    
    # Integration settings
    IntegrationSettings,
    IntegrationSettingsUpdate
)

# ============================================================================
# Authentication Schemas
# ============================================================================

from .auth import (
    # User models
    UserRegistration,
    UserLogin,
    UserResponse,
    UserUpdate,
    UserProfile,
    
    # Token models
    TokenResponse,
    TokenRefresh,
    
    # Password management
    PasswordResetRequest,
    PasswordResetConfirm,
    ChangePassword,
    
    # Email verification
    EmailVerificationRequest,
    EmailVerificationResponse,
    
    # Two-factor authentication
    TwoFactorSetupResponse,
    TwoFactorVerifyRequest,
    TwoFactorEnableRequest,
    TwoFactorDisableRequest,
    
    # API keys
    ApiKeyCreate,
    ApiKeyResponse,
    ApiKeyListResponse,
    
    # Role/permission models
    UserRole,
    UserStatus,
    Permission,
    
    # Admin operations
    UserRoleUpdate,
    UserStatusUpdate,
    UserListResponse
)

# ============================================================================
# Version and Metadata
# ============================================================================

__version__ = "2.0.0"
__author__ = "Drone Detection System Team"

# ============================================================================
# Public API - Explicit Exports
# ============================================================================

__all__ = [
    # Common
    "SuccessResponse",
    "ErrorResponse",
    "ValidationErrorResponse",
    "PaginationParams",
    "PaginatedResponse",
    "CursorParams",
    "CursorResponse",
    "TimestampMixin",
    "Metadata",
    "HealthStatus",
    "RateLimitInfo",
    "VersionInfo",
    "TimeRangeParams",
    "FilterParams",
    "SortOrder",
    "SortField",
    "TimeRangePreset",
    "BatchOperationRequest",
    "BatchOperationResponse",
    "ImportResult",
    "ExportOptions",
    "WebSocketMessage",
    "WebSocketMessageType",
    "DetectionMessage",
    "AlertMessage",
    "PositionMessage",
    "HeartbeatMessage",
    "EventType",
    "SystemEvent",
    "create_success_response",
    "create_error_response",
    "create_paginated_response",
    
    # Detection
    "DetectionBase",
    "DetectionCreate",
    "DetectionUpdate",
    "DetectionResponse",
    "DetectionDetailResponse",
    "DetectionFilterParams",
    "ThreatLevel",
    "ThreatAssessmentRequest",
    "ThreatAssessmentResponse",
    "RemoteIDData",
    "RemoteIDMessageResponse",
    "RemoteIDSessionResponse",
    "DetectionEventType",
    "DetectionEventResponse",
    "BatchDetectionRequest",
    "BatchDetectionResponse",
    
    # Spectrum
    "SpectrumRequest",
    "SpectrumResponse",
    "SpectrumDataPoint",
    "SpectrumMetadata",
    "FFTRequest",
    "FFTResponse",
    "PSDRequest",
    "PSDResponse",
    "WaterfallRequest",
    "WaterfallResponse",
    "WaterfallDataPoint",
    "PeakDetectionRequest",
    "PeakDetectionResponse",
    "PeakInfo",
    "SignalAnalysisRequest",
    "SignalAnalysisResponse",
    "ModulationInfo",
    "InterferenceInfo",
    "SpectrumFilterParams",
    
    # Hardware
    "DeviceInfo",
    "DeviceStatus",
    "DeviceCapabilities",
    "TuneRequest",
    "GainRequest",
    "SampleRateRequest",
    "ScanRequest",
    "AntennaInfo",
    "AntennaConfig",
    "AntennaStatus",
    "AntennaSwitchRequest",
    "RecordingRequest",
    "RecordingResponse",
    "RecordingMetadata",
    "CalibrationRequest",
    "CalibrationResponse",
    "HardwareStatusResponse",
    "HardwareMetricsResponse",
    
    # Map
    "Position",
    "BoundingBox",
    "PointGeometry",
    "LineStringGeometry",
    "PolygonGeometry",
    "MultiPointGeometry",
    "MultiLineStringGeometry",
    "MultiPolygonGeometry",
    "GeometryCollection",
    "GeoJSONFeature",
    "GeoJSONFeatureCollection",
    "DroneProperties",
    "GeofenceProperties",
    "TrackProperties",
    "HeatmapProperties",
    "DronePositionResponse",
    "DroneTracksResponse",
    "GeofenceZonesResponse",
    "DetectionHeatmapResponse",
    "LiveTrackResponse",
    "ProximityAlert",
    "AreaCoverageResponse",
    "GeofenceCreateRequest",
    "GeofenceUpdateRequest",
    "TrackQueryParams",
    "HeatmapQueryParams",
    "ThreatZoneType",
    "DroneStatus",
    "create_point_feature",
    "create_line_feature",
    "create_polygon_feature",
    "create_feature_collection",
    
    # Configuration
    "SystemConfig",
    "SystemConfigUpdate",
    "SystemConfigResponse",
    "FrequencyBand",
    "FrequencyBandCreate",
    "FrequencyBandUpdate",
    "FrequencyBandResponse",
    "AlertRule",
    "AlertRuleCreate",
    "AlertRuleUpdate",
    "AlertRuleResponse",
    "DroneSignature",
    "DroneSignatureCreate",
    "DroneSignatureUpdate",
    "DroneSignatureResponse",
    "UserPreferences",
    "UserPreferencesUpdate",
    "NotificationSettings",
    "NotificationSettingsUpdate",
    "IntegrationSettings",
    "IntegrationSettingsUpdate",
    
    # Authentication
    "UserRegistration",
    "UserLogin",
    "UserResponse",
    "UserUpdate",
    "UserProfile",
    "TokenResponse",
    "TokenRefresh",
    "PasswordResetRequest",
    "PasswordResetConfirm",
    "ChangePassword",
    "EmailVerificationRequest",
    "EmailVerificationResponse",
    "TwoFactorSetupResponse",
    "TwoFactorVerifyRequest",
    "TwoFactorEnableRequest",
    "TwoFactorDisableRequest",
    "ApiKeyCreate",
    "ApiKeyResponse",
    "ApiKeyListResponse",
    "UserRole",
    "UserStatus",
    "Permission",
    "UserRoleUpdate",
    "UserStatusUpdate",
    "UserListResponse"
]


# ============================================================================
# Module Documentation
# ============================================================================

__doc__ = """
API Schemas Package
===================

This package contains all Pydantic models (request/response schemas) for the Drone Detection System API.

Schema Categories:
------------------
1. **Common** - Shared schemas for all endpoints
   - Success/Error responses
   - Pagination
   - WebSocket messages
   - Health checks

2. **Detection** - Drone detection data
   - Detection CRUD
   - Threat assessment
   - Remote ID data
   - Detection events

3. **Spectrum** - Spectrum analysis data
   - FFT/PSD results
   - Waterfall data
   - Peak detection
   - Signal analysis

4. **Hardware** - Hardware control data
   - Device status
   - Antenna configuration
   - Recording control
   - Calibration

5. **Map** - GeoJSON data
   - Drone positions
   - Geofence zones
   - Flight tracks
   - Heatmap data

6. **Configuration** - System configuration
   - Frequency bands
   - Alert rules
   - Drone signatures
   - User preferences

7. **Authentication** - User management
   - User registration/login
   - Password reset
   - 2FA
   - API keys

Quick Start:
-----------
```python
from api.schemas import (
    SuccessResponse,
    DetectionResponse,
    SpectrumResponse,
    HardwareStatusResponse,
    DronePositionResponse,
    SystemConfig,
    UserResponse
)

# Use in route handlers
@router.get("/detections/{id}", response_model=DetectionResponse)
async def get_detection(id: str):
    return DetectionResponse(...)

# Use for request validation
@router.post("/detections")
async def create_detection(detection: DetectionCreate):
    return SuccessResponse(data=await create_detection(detection))

# Use for responses
@router.get("/health")
async def health():
    return HealthStatus(status="healthy", version="2.0.0")