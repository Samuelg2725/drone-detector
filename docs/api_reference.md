# Drone Detector API Reference

## Overview

The Drone Detector provides a comprehensive REST API for system control, data retrieval, and real-time monitoring. The API follows RESTful principles, uses JSON for requests/responses, and includes OpenAPI 3.0 documentation.

**Base URL:** `http://localhost:8888/api/v1`

**API Documentation:** `http://localhost:8888/docs` (Swagger UI) or `http://localhost:8888/redoc` (ReDoc)

## Authentication

The API uses JWT (JSON Web Token) authentication for protected endpoints.

### Authentication Flow

```bash
# 1. Obtain access token
curl -X POST http://localhost:8888/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your_password"}'

# Response
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 3600
}

# 2. Use token in subsequent requests
curl -X GET http://localhost:8888/api/v1/detections \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
API Keys
For machine-to-machine communication, API keys are supported:

bash
curl -X GET http://localhost:8888/api/v1/detections \
  -H "X-API-Key: your_api_key_here"
Response Format
All responses follow a consistent format:

Success Response
json
{
  "status": "success",
  "data": {
    // Response data here
  },
  "meta": {
    "timestamp": "2024-01-01T00:00:00Z",
    "request_id": "uuid",
    "version": "1.0.0"
  }
}
Paginated Response
json
{
  "status": "success",
  "data": {
    "items": [],
    "pagination": {
      "page": 1,
      "per_page": 50,
      "total": 1234,
      "pages": 25,
      "next": "/api/v1/detections?page=2",
      "prev": null
    }
  }
}
Error Response
json
{
  "status": "error",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request parameters",
    "details": [
      {
        "field": "frequency",
        "message": "Frequency must be between 70e6 and 6e9"
      }
    ]
  },
  "meta": {
    "timestamp": "2024-01-01T00:00:00Z",
    "request_id": "uuid"
  }
}
HTTP Status Codes
Status	Description
200	Success
201	Created
204	No Content
400	Bad Request - Invalid parameters
401	Unauthorized - Authentication required
403	Forbidden - Insufficient permissions
404	Not Found - Resource doesn't exist
409	Conflict - Resource already exists
422	Unprocessable Entity - Validation error
429	Too Many Requests - Rate limit exceeded
500	Internal Server Error
503	Service Unavailable
Rate Limiting
API endpoints have rate limits to ensure system stability:

text
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1640995200
Retry-After: 3600
Endpoint Type	Limit	Period
Public endpoints	100	per minute
Authenticated endpoints	1000	per minute
Admin endpoints	5000	per minute
Data export	50	per hour
Endpoints
System Management
GET /health
System health check endpoint.

Response:

json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2024-01-01T00:00:00Z",
  "components": {
    "database": "healthy",
    "redis": "healthy",
    "hardware": "healthy",
    "websocket": "healthy"
  },
  "uptime_seconds": 86400
}
GET /metrics
Prometheus metrics endpoint.

Response: Prometheus exposition format

text
# HELP drone_detections_total Total number of drone detections
# TYPE drone_detections_total counter
drone_detections_total{drone_type="DJI_Mavic"} 1234

# HELP drone_detection_latency_ms Detection processing latency
# TYPE drone_detection_latency_ms histogram
drone_detection_latency_ms_bucket{le="50"} 100
drone_detection_latency_ms_bucket{le="100"} 500
GET /system/info
Get system information.

Response:

json
{
  "version": "1.0.0",
  "build_date": "2024-01-01T00:00:00Z",
  "git_commit": "abc123",
  "environment": "production",
  "hardware": {
    "type": "hackrf",
    "sample_rate": 2000000,
    "center_frequency": 2450000000,
    "gain": 20
  },
  "resources": {
    "cpu_percent": 45.2,
    "memory_mb": 512,
    "disk_usage_percent": 30.5
  }
}
Authentication
POST /auth/login
Authenticate user and get access token.

Request:

json
{
  "username": "admin",
  "password": "your_password"
}
Response:

json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "uuid",
    "username": "admin",
    "role": "admin",
    "permissions": ["read", "write", "admin"]
  }
}
POST /auth/refresh
Refresh access token.

Request:

json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
Response:

json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "expires_in": 3600
}
POST /auth/logout
Logout user (invalidates token).

Request Headers:

text
Authorization: Bearer <token>
Response: 204 No Content

POST /auth/change-password
Change user password.

Request:

json
{
  "current_password": "old_password",
  "new_password": "new_password"
}
Response: 204 No Content

POST /auth/api-key
Generate new API key.

Response:

json
{
  "api_key": "dk_live_abc123def456...",
  "name": "My Integration",
  "created_at": "2024-01-01T00:00:00Z",
  "expires_at": "2025-01-01T00:00:00Z"
}
DELETE /auth/api-key/{key_id}
Revoke API key.

Response: 204 No Content

Detections
GET /detections
Get list of drone detections.

Query Parameters:

Parameter	Type	Description
start_time	datetime	Start of time range (ISO 8601)
end_time	datetime	End of time range (ISO 8601)
drone_type	string	Filter by drone type
threat_level	string	Filter by threat level (low, medium, high, critical)
min_confidence	float	Minimum confidence score (0-1)
frequency_min	float	Minimum frequency (Hz)
frequency_max	float	Maximum frequency (Hz)
limit	int	Number of results (default: 50, max: 1000)
offset	int	Pagination offset
sort	string	Sort field (timestamp, confidence)
order	string	Sort order (asc, desc)
Response:

json
{
  "items": [
    {
      "id": "uuid",
      "timestamp": "2024-01-01T00:00:00Z",
      "drone_type": "DJI Mavic 3",
      "frequency": 2445000000,
      "confidence": 0.95,
      "threat_level": "medium",
      "signal_power": -45.5,
      "snr": 28.3,
      "position": {
        "latitude": 37.7749,
        "longitude": -122.4194,
        "altitude": 100.5,
        "accuracy": 10.0
      },
      "remote_id": {
        "serial_number": "DJI_123456",
        "operator_id": "OP_789012",
        "uas_id": "UAS_345678"
      }
    }
  ],
  "pagination": {
    "total": 1234,
    "limit": 50,
    "offset": 0,
    "next_offset": 50
  }
}
GET /detections/{detection_id}
Get specific detection by ID.

Response:

json
{
  "id": "uuid",
  "timestamp": "2024-01-01T00:00:00Z",
  "drone_type": "DJI Mavic 3",
  "frequency": 2445000000,
  "confidence": 0.95,
  "threat_level": "medium",
  "signal_power": -45.5,
  "snr": 28.3,
  "bandwidth": 20000000,
  "modulation": "OFDM",
  "position": {
    "latitude": 37.7749,
    "longitude": -122.4194,
    "altitude": 100.5,
    "accuracy": 10.0
  },
  "position_history": [
    {
      "timestamp": "2024-01-01T00:00:00Z",
      "latitude": 37.7749,
      "longitude": -122.4194,
      "altitude": 100.5
    }
  ],
  "remote_id": {
    "serial_number": "DJI_123456",
    "operator_id": "OP_789012",
    "uas_id": "UAS_345678",
    "operator_location": {
      "latitude": 37.7750,
      "longitude": -122.4195
    }
  },
  "spectrum_snapshot": {
    "frequencies": [2440000000, 2441000000, ...],
    "psd": [-90, -85, -45, -88, ...],
    "waterfall": [[...], [...]]
  }
}
GET /detections/stats
Get detection statistics.

Query Parameters:

Parameter	Type	Description
start_time	datetime	Start of time range
end_time	datetime	End of time range
interval	string	Time bucket interval (hour, day, week, month)
Response:

json
{
  "total_detections": 1234,
  "unique_drones": 42,
  "threat_distribution": {
    "critical": 5,
    "high": 23,
    "medium": 456,
    "low": 750
  },
  "drone_types": {
    "DJI Mavic 3": 234,
    "DJI Mini": 456,
    "FPV Analog": 321,
    "Custom": 123
  },
  "frequency_bands": {
    "2.4GHz": 678,
    "5.8GHz": 456,
    "900MHz": 100
  },
  "detections_over_time": [
    {
      "timestamp": "2024-01-01T00:00:00Z",
      "count": 42
    }
  ],
  "avg_confidence": 0.87,
  "peak_hour": 14
}
GET /detections/export
Export detections to file.

Query Parameters:

Parameter	Type	Description
start_time	datetime	Start of time range
end_time	datetime	End of time range
format	string	Export format (csv, json, parquet)
include_raw	boolean	Include raw IQ data
Response: File download (Content-Disposition attachment)

Real-time Streaming (WebSocket)
WebSocket /ws/detections
Real-time detection stream.

Connection:

javascript
const ws = new WebSocket('ws://localhost:8888/api/v1/ws/detections?token=your_jwt');

ws.onmessage = (event) => {
  const detection = JSON.parse(event.data);
  console.log('New detection:', detection);
};
Message Types:

Detection Event

json
{
  "type": "detection",
  "data": {
    "detection_id": "uuid",
    "drone_type": "DJI Mavic 3",
    "confidence": 0.95,
    "threat_level": "medium",
    "timestamp": "2024-01-01T00:00:00Z"
  }
}
Heartbeat

json
{
  "type": "heartbeat",
  "timestamp": "2024-01-01T00:00:00Z"
}
Alert

json
{
  "type": "alert",
  "severity": "high",
  "message": "Unauthorized drone detected in restricted zone",
  "detection_id": "uuid"
}
System Status

json
{
  "type": "system_status",
  "status": "operational",
  "hardware_temp": 45.2,
  "cpu_usage": 32.5
}
Spectrum Analysis
GET /spectrum/live
Get real-time spectrum data.

Response:

json
{
  "timestamp": "2024-01-01T00:00:00Z",
  "center_frequency": 2450000000,
  "sample_rate": 2000000,
  "frequencies": [2440000000, 2441000000, ...],
  "spectrum": [-90.5, -85.2, -45.3, -88.1, ...],
  "waterfall": [
    [-90, -85, -45, -88],
    [-91, -86, -46, -89],
    ...
  ],
  "peaks": [
    {
      "frequency": 2445000000,
      "power": -45.3,
      "bandwidth": 20000000
    }
  ]
}
GET /spectrum/history
Get historical spectrum data.

Query Parameters:

Parameter	Type	Description
start_time	datetime	Start of time range
end_time	datetime	End of time range
frequency	float	Specific frequency
bandwidth	float	Frequency bandwidth
resolution	int	FFT resolution
Response:

json
{
  "frequency": 2445000000,
  "bandwidth": 20000000,
  "time_series": [
    {
      "timestamp": "2024-01-01T00:00:00Z",
      "power": -45.3,
      "snr": 28.5
    }
  ],
  "stats": {
    "min_power": -90.2,
    "max_power": -45.3,
    "avg_power": -65.4,
    "std_power": 12.3
  }
}
GET /spectrum/waterfall/{date}
Get waterfall image for specific date.

Response: PNG image

Hardware Control
GET /hardware/status
Get hardware status.

Response:

json
{
  "type": "hackrf",
  "connected": true,
  "temperature_c": 45.2,
  "sample_rate": 2000000,
  "center_frequency": 2450000000,
  "gain": 20,
  "lna_gain": 16,
  "vga_gain": 20,
  "usb_speed": "High Speed",
  "firmware_version": "2023.01.1"
}
POST /hardware/configure
Configure hardware parameters.

Request:

json
{
  "sample_rate": 10000000,
  "center_frequency": 5800000000,
  "gain": 24,
  "lna_gain": 20,
  "vga_gain": 30,
  "bandwidth": 20000000
}
Response:

json
{
  "status": "configured",
  "previous_config": {...},
  "new_config": {...}
}
POST /hardware/scan
Initiate frequency scan.

Request:

json
{
  "start_frequency": 2400000000,
  "end_frequency": 2500000000,
  "step_size": 1000000,
  "dwell_time_ms": 100
}
Response:

json
{
  "scan_id": "uuid",
  "progress_url": "/api/v1/hardware/scan/{scan_id}/status",
  "estimated_completion": "2024-01-01T00:01:00Z"
}
GET /hardware/scan/{scan_id}/status
Get scan status.

Response:

json
{
  "scan_id": "uuid",
  "status": "running",
  "progress_percent": 45,
  "current_frequency": 2445000000,
  "detections_found": 3
}
GET /hardware/calibrate
Run hardware calibration.

Response:

json
{
  "calibration_id": "uuid",
  "status": "running",
  "estimated_duration_seconds": 30
}
Drone Signatures
GET /signatures
Get drone signature database.

Response:

json
{
  "signatures": [
    {
      "drone_type": "DJI Mavic 3",
      "frequency_bands": [
        {"start": 2400000000, "end": 2480000000},
        {"start": 5725000000, "end": 5875000000}
      ],
      "modulation": "OFDM",
      "bandwidth": 20000000,
      "signature_features": {
        "peak_width": 1500000,
        "cyclic_prefix": true,
        "pilots": [2405000000, 2410000000]
      },
      "confidence_threshold": 0.75
    }
  ],
  "last_updated": "2024-01-01T00:00:00Z",
  "version": 42
}
POST /signatures
Add new drone signature.

Request:

json
{
  "drone_type": "Custom Drone",
  "frequency_bands": [
    {"start": 2400000000, "end": 2480000000}
  ],
  "modulation": "OFDM",
  "bandwidth": 20000000,
  "signature_features": {
    "peak_width": 1500000,
    "cyclic_prefix": true
  }
}
Response:

json
{
  "id": "uuid",
  "drone_type": "Custom Drone",
  "created_at": "2024-01-01T00:00:00Z"
}
PUT /signatures/{signature_id}
Update existing signature.

Response:

json
{
  "id": "uuid",
  "updated": true,
  "version": 2
}
DELETE /signatures/{signature_id}
Delete signature.

Response: 204 No Content

Alerts
GET /alerts
Get alerts.

Query Parameters:

Parameter	Type	Description
severity	string	Filter by severity (low, medium, high, critical)
acknowledged	boolean	Filter by acknowledgment status
start_time	datetime	Start of time range
end_time	datetime	End of time range
limit	int	Number of results
Response:

json
{
  "items": [
    {
      "id": "uuid",
      "timestamp": "2024-01-01T00:00:00Z",
      "severity": "high",
      "title": "Unauthorized Drone Detected",
      "message": "DJI Mavic 3 detected in restricted airspace",
      "detection_id": "uuid",
      "acknowledged": false,
      "acknowledged_by": null,
      "acknowledged_at": null,
      "actions_taken": ["notification_sent", "recording_started"]
    }
  ],
  "unacknowledged_count": 3
}
POST /alerts/{alert_id}/acknowledge
Acknowledge alert.

Request:

json
{
  "notes": "Investigating the situation"
}
Response:

json
{
  "id": "uuid",
  "acknowledged": true,
  "acknowledged_by": "admin",
  "acknowledged_at": "2024-01-01T00:00:00Z"
}
POST /alerts/config
Configure alert rules.

Request:

json
{
  "rules": [
    {
      "name": "High threat in restricted zone",
      "condition": "threat_level == 'high' and in_restricted_zone",
      "severity": "critical",
      "actions": ["email", "sms", "webhook", "record_video"],
      "cooldown_seconds": 300
    }
  ],
  "notification_channels": {
    "email": {
      "enabled": true,
      "recipients": ["security@example.com"]
    },
    "sms": {
      "enabled": true,
      "numbers": ["+1234567890"]
    },
    "webhook": {
      "enabled": false,
      "url": "https://your-webhook.com/alert"
    }
  }
}
Response:

json
{
  "status": "configured",
  "rules_active": 5,
  "channels_active": 2
}
Map & Geospatial
GET /map/detections
Get detection locations for map.

Query Parameters:

Parameter	Type	Description
bounds	string	Map bounds (min_lon,min_lat,max_lon,max_lat)
start_time	datetime	Start of time range
end_time	datetime	End of time range
threat_level	string	Filter by threat level
Response (GeoJSON):

json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [-122.4194, 37.7749]
      },
      "properties": {
        "detection_id": "uuid",
        "drone_type": "DJI Mavic 3",
        "threat_level": "high",
        "timestamp": "2024-01-01T00:00:00Z",
        "confidence": 0.95
      }
    }
  ]
}
GET /map/heatmap
Get detection heatmap data.

Response:

json
{
  "type": "HeatmapData",
  "data": [
    {"lat": 37.7749, "lon": -122.4194, "weight": 95},
    {"lat": 37.7750, "lon": -122.4195, "weight": 87}
  ],
  "bounds": {
    "min_lat": 37.7700,
    "max_lat": 37.7800,
    "min_lon": -122.4300,
    "max_lon": -122.4100
  }
}
GET /map/restricted-zones
Get restricted zone definitions.

Response (GeoJSON):

json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[-122.42, 37.77], [-122.41, 37.77], [-122.41, 37.78], [-122.42, 37.78], [-122.42, 37.77]]]
      },
      "properties": {
        "name": "Airport Restricted Zone",
        "type": "no_fly",
        "severity": "critical"
      }
    }
  ]
}
POST /map/restricted-zones
Add restricted zone.

Request (GeoJSON):

json
{
  "type": "Feature",
  "geometry": {
    "type": "Polygon",
    "coordinates": [...]
  },
  "properties": {
    "name": "New Restricted Zone",
    "type": "no_fly",
    "severity": "high"
  }
}
Response:

json
{
  "id": "uuid",
  "created": true
}
Analytics
GET /analytics/trends
Get detection trends.

Query Parameters:

Parameter	Type	Description
start_time	datetime	Start of time range
end_time	datetime	End of time range
granularity	string	Time granularity (hour, day, week, month)
metrics	string	Comma-separated metrics to include
Response:

json
{
  "detection_trend": [
    {"timestamp": "2024-01-01T00:00:00Z", "count": 42},
    {"timestamp": "2024-01-02T00:00:00Z", "count": 38}
  ],
  "threat_trend": {
    "critical": [0, 1, 2],
    "high": [5, 3, 8]
  },
  "peak_hours": {
    "0": 10, "1": 5, "2": 2, "3": 1, "4": 0, "5": 2,
    "6": 15, "7": 45, "8": 60, "9": 55, "10": 50, "11": 48,
    "12": 52, "13": 58, "14": 70, "15": 85, "16": 90, "17": 95,
    "18": 88, "19": 75, "20": 65, "21": 55, "22": 40, "23": 25
  },
  "busiest_day": "Saturday",
  "average_daily": 125.5
}
GET /analytics/predictions
Get ML predictions for future drone activity.

Response:

json
{
  "predictions": [
    {"timestamp": "2024-01-02T00:00:00Z", "predicted_count": 42, "confidence_interval": [35, 49]},
    {"timestamp": "2024-01-03T00:00:00Z", "predicted_count": 38, "confidence_interval": [31, 45]}
  ],
  "model_accuracy": 0.87,
  "features_used": ["hour_of_day", "day_of_week", "weather", "historical_trend"]
}
Recording & Playback
POST /recordings/start
Start IQ recording.

Request:

json
{
  "duration_seconds": 300,
  "frequency": 2450000000,
  "bandwidth": 20000000,
  "format": "complex_int16",
  "auto_stop": true
}
Response:

json
{
  "recording_id": "uuid",
  "status": "recording",
  "file_path": "/data/iq/live/session_20240101_000000",
  "estimated_size_mb": 500
}
POST /recordings/stop/{recording_id}
Stop recording.

Response:

json
{
  "recording_id": "uuid",
  "status": "stopped",
  "duration_seconds": 300,
  "file_size_mb": 478,
  "file_path": "/data/iq/live/session_20240101_000000"
}
GET /recordings
List recordings.

Response:

json
{
  "recordings": [
    {
      "id": "uuid",
      "timestamp": "2024-01-01T00:00:00Z",
      "duration_seconds": 300,
      "frequency": 2450000000,
      "sample_rate": 20000000,
      "file_size_mb": 478,
      "has_detections": true,
      "detection_count": 5
    }
  ]
}
GET /recordings/{recording_id}/download
Download recording file.

Response: Binary IQ data download

POST /recordings/{recording_id}/playback
Start playback of recording.

Request:

json
{
  "speed": 1.0,
  "loop": false,
  "start_offset_seconds": 0
}
Response:

json
{
  "playback_id": "uuid",
  "status": "playing",
  "websocket_url": "ws://localhost:8888/api/v1/ws/playback/{playback_id}"
}
Configuration
GET /config
Get system configuration.

Response:

json
{
  "system": {
    "name": "Drone Detector",
    "mode": "production",
    "log_level": "INFO",
    "timezone": "UTC"
  },
  "hardware": {
    "type": "hackrf",
    "sample_rate": 2000000,
    "gain": 20
  },
  "detection": {
    "threshold": 10,
    "min_confidence": 0.7,
    "update_interval_ms": 100
  },
  "alerts": {
    "enabled": true,
    "email_enabled": true,
    "sms_enabled": false
  },
  "data_retention": {
    "detections_days": 90,
    "recordings_days": 30,
    "spectrum_days": 7
  }
}
PUT /config
Update system configuration.

Request: (partial config)

Response: Updated full configuration

GET /config/schema
Get configuration schema for validation.

Response:

json
{
  "system": {
    "type": "object",
    "properties": {
      "name": {"type": "string"},
      "mode": {"enum": ["development", "production"]}
    }
  }
}
ML Model Management
GET /ml/models
List ML models.

Response:

json
{
  "models": [
    {
      "name": "classifier_v1",
      "version": "1.0.0",
      "created_at": "2024-01-01T00:00:00Z",
      "accuracy": 0.95,
      "size_mb": 45,
      "active": true
    }
  ],
  "active_model": "classifier_v1"
}
POST /ml/models/activate
Activate a model.

Request:

json
{
  "model_name": "classifier_v2",
  "version": "2.0.0"
}
Response:

json
{
  "status": "activated",
  "active_model": "classifier_v2"
}
POST /ml/models/train
Start model training.

Request:

json
{
  "dataset": "drone_signatures_2024",
  "epochs": 100,
  "learning_rate": 0.001,
  "batch_size": 32,
  "validation_split": 0.2
}
Response:

json
{
  "training_id": "uuid",
  "status": "started",
  "progress_url": "/api/v1/ml/training/{training_id}/status"
}
GET /ml/models/evaluate
Evaluate model performance.

Response:

json
{
  "accuracy": 0.95,
  "precision": 0.94,
  "recall": 0.96,
  "f1_score": 0.95,
  "confusion_matrix": [
    [85, 5, 2],
    [3, 88, 4],
    [2, 3, 90]
  ],
  "class_names": ["DJI", "FPV", "Custom"],
  "feature_importance": {
    "spectral_centroid": 0.25,
    "peak_width": 0.20,
    "rms_power": 0.15
  }
}
Export & Reporting
POST /exports/detections
Export detections to file.

Request:

json
{
  "start_time": "2024-01-01T00:00:00Z",
  "end_time": "2024-01-31T23:59:59Z",
  "format": "csv",
  "fields": ["timestamp", "drone_type", "frequency", "confidence", "threat_level"],
  "filename": "detections_january.csv"
}
Response:

json
{
  "export_id": "uuid",
  "status": "processing",
  "download_url": "/api/v1/exports/{export_id}/download",
  "estimated_completion": "2024-01-01T00:01:00Z"
}
GET /exports/{export_id}/download
Download exported file.

Response: File download

POST /reports/daily
Generate daily report.

Request:

json
{
  "date": "2024-01-01",
  "format": "pdf",
  "include_spectrum": true,
  "include_map": true
}
Response:

json
{
  "report_id": "uuid",
  "download_url": "/api/v1/reports/{report_id}/download",
  "size_bytes": 1024000
}
GET /reports
List generated reports.

Response:

json
{
  "reports": [
    {
      "id": "uuid",
      "type": "daily",
      "date": "2024-01-01",
      "generated_at": "2024-01-02T00:00:00Z",
      "size_bytes": 1024000,
      "download_url": "/api/v1/reports/{id}/download"
    }
  ]
}
WebSocket API
Connection Endpoint
text
ws://localhost:8888/api/v1/ws
Authentication
javascript
// Method 1: Query parameter
const ws = new WebSocket('ws://localhost:8888/api/v1/ws?token=your_jwt');

// Method 2: After authentication (recommended)
const ws = new WebSocket('ws://localhost:8888/api/v1/ws');
ws.onopen = () => {
  ws.send(JSON.stringify({
    type: "auth",
    token: "your_jwt"
  }));
};
Subscription Messages
javascript
// Subscribe to detections
ws.send(JSON.stringify({
  type: "subscribe",
  channel: "detections",
  filters: {
    min_confidence: 0.8,
    threat_levels: ["high", "critical"]
  }
}));

// Subscribe to spectrum
ws.send(JSON.stringify({
  type: "subscribe",
  channel: "spectrum",
  frequency: 2450000000,
  bandwidth: 20000000
}));

// Subscribe to system status
ws.send(JSON.stringify({
  type: "subscribe",
  channel: "system"
}));

// Unsubscribe
ws.send(JSON.stringify({
  type: "unsubscribe",
  channel: "detections"
}));
Control Messages
javascript
// Start scan
ws.send(JSON.stringify({
  type: "command",
  command: "start_scan",
  params: {
    start_freq: 2400000000,
    end_freq: 2500000000
  }
}));

// Start recording
ws.send(JSON.stringify({
  type: "command",
  command: "start_recording",
  params: {
    duration: 300
  }
}));

// Acknowledge alert
ws.send(JSON.stringify({
  type: "command",
  command: "acknowledge_alert",
  alert_id: "uuid"
}));
Received Messages
javascript
// Detection message
{
  "type": "detection",
  "data": {
    "detection_id": "uuid",
    "drone_type": "DJI Mavic 3",
    "confidence": 0.95,
    "timestamp": "2024-01-01T00:00:00Z"
  }
}

// Spectrum update
{
  "type": "spectrum",
  "data": {
    "timestamp": "2024-01-01T00:00:00Z",
    "frequencies": [...],
    "powers": [...]
  }
}

// Alert message
{
  "type": "alert",
  "severity": "high",
  "title": "Unauthorized Drone",
  "message": "Drone detected in restricted zone",
  "detection_id": "uuid"
}

// System status
{
  "type": "status",
  "data": {
    "hardware": "connected",
    "cpu_usage": 45.2,
    "memory_usage": 512,
    "uptime": 86400
  }
}

// Heartbeat
{
  "type": "heartbeat",
  "timestamp": "2024-01-01T00:00:00Z"
}

// Error
{
  "type": "error",
  "code": "INVALID_COMMAND",
  "message": "Unknown command: invalid_command"
}
Error Codes
Code	Description
AUTH_001	Invalid credentials
AUTH_002	Token expired
AUTH_003	Insufficient permissions
AUTH_004	Invalid API key
VALID_001	Missing required field
VALID_002	Invalid field type
VALID_003	Value out of range
RES_001	Resource not found
RES_002	Resource already exists
RES_003	Resource conflict
HW_001	Hardware not connected
HW_002	Hardware busy
HW_003	Hardware not supported
DB_001	Database connection error
DB_002	Query timeout
DB_003	Constraint violation
RATE_001	Rate limit exceeded
API_001	Internal server error
API_002	Service unavailable
API_003	Gateway timeout
SDK Examples
Python
python
from drone_detector import DroneDetectorClient

# Initialize client
client = DroneDetectorClient(
    base_url="http://localhost:8888/api/v1",
    api_key="your_api_key"
)

# Get detections
detections = client.detections.list(
    start_time="2024-01-01T00:00:00Z",
    threat_level="high",
    limit=10
)

# Real-time streaming
async def on_detection(detection):
    print(f"New detection: {detection.drone_type}")

client.stream_detections(on_detection)

# Get spectrum
spectrum = client.spectrum.get_live()
print(f"Center frequency: {spectrum.center_frequency}")

# Control hardware
client.hardware.configure(
    center_frequency=2450000000,
    gain=20
)
JavaScript
javascript
import DroneDetectorClient from 'drone-detector-sdk';

const client = new DroneDetectorClient({
  baseUrl: 'http://localhost:8888/api/v1',
  apiKey: 'your_api_key'
});

// Get detections
const detections = await client.detections.list({
  startTime: '2024-01-01T00:00:00Z',
  threatLevel: 'high',
  limit: 10
});

// WebSocket streaming
const stream = client.streamDetections();
stream.on('detection', (detection) => {
  console.log('New detection:', detection);
});

// Get spectrum
const spectrum = await client.spectrum.getLive();
console.log('Spectrum data:', spectrum);

// Control hardware
await client.hardware.configure({
  centerFrequency: 2450000000,
  gain: 20
});
cURL Examples
bash
# Login
curl -X POST http://localhost:8888/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"password"}'

# Get detections (with pagination)
curl -X GET "http://localhost:8888/api/v1/detections?limit=10&offset=0" \
  -H "Authorization: Bearer $TOKEN"

# Get live spectrum
curl -X GET http://localhost:8888/api/v1/spectrum/live \
  -H "Authorization: Bearer $TOKEN"

# Start recording
curl -X POST http://localhost:8888/api/v1/recordings/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"duration_seconds":300,"frequency":2450000000}'

# Export detections
curl -X POST http://localhost:8888/api/v1/exports/detections \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"start_time":"2024-01-01T00:00:00Z","format":"csv"}'

# Get system info
curl -X GET http://localhost:8888/api/v1/system/info \
  -H "Authorization: Bearer $TOKEN"
API Versioning
The API uses URL versioning (/api/v1/). Version changes follow semantic versioning:

Major version (v1, v2): Breaking changes

Minor version: New features, backwards compatible

Patch version: Bug fixes, no API changes

Version lifecycle:

Current stable: v1

Deprecated: v0 (removed after 6 months)

Beta: v2-beta (available for testing)

Version header: API-Version: 1.0

Rate Limit Headers
All responses include rate limit headers:

text
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1640995200
Retry-After: 3600
Exceeding limit:

json
{
  "status": "error",
  "error": {
    "code": "RATE_001",
    "message": "Rate limit exceeded. Try again in 3600 seconds."
  }
}
Pagination
Endpoints that return lists support pagination:

Request:

limit: Number of items per page (default: 50, max: 1000)

offset: Number of items to skip (for offset-based pagination)

page: Page number (for page-based pagination, used with per_page)

Response headers:

X-Total-Count: Total number of items

X-Total-Pages: Total number of pages

Example:

bash
curl "http://localhost:8888/api/v1/detections?limit=100&offset=200"
Filtering & Sorting
Filter Syntax
text
GET /api/v1/detections?field=value
GET /api/v1/detections?field__gt=value      # Greater than
GET /api/v1/detections?field__lt=value      # Less than
GET /api/v1/detections?field__gte=value     # Greater than or equal
GET /api/v1/detections?field__lte=value     # Less than or equal
GET /api/v1/detections?field__contains=value # Contains substring
GET /api/v1/detections?field__in=value1,value2 # In list
Sorting
text
GET /api/v1/detections?sort=timestamp     # Ascending
GET /api/v1/detections?sort=-timestamp    # Descending
GET /api/v1/detections?sort=timestamp,confidence # Multiple fields
OpenAPI Specification
The API is fully documented with OpenAPI 3.0:

Swagger UI: http://localhost:8888/docs

ReDoc: http://localhost:8888/redoc

OpenAPI JSON: http://localhost:8888/openapi.json

OpenAPI YAML: http://localhost:8888/openapi.yaml

Download the specification for client generation:

bash
curl http://localhost:8888/openapi.json > drone-detector-api.json
Webhook Integration
Configure webhooks for real-time notifications:

bash
curl -X POST http://localhost:8888/api/v1/alerts/config \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "webhook": {
      "url": "https://your-server.com/webhook",
      "events": ["detection", "alert"],
      "secret": "your_webhook_secret",
      "retry_count": 3,
      "timeout_ms": 5000
    }
  }'
Webhook payload:

json
{
  "event": "detection",
  "timestamp": "2024-01-01T00:00:00Z",
  "data": {
    "detection_id": "uuid",
    "drone_type": "DJI Mavic 3",
    "confidence": 0.95
  },
  "signature": "sha256=abc123..."
}
Verify signature:

python
import hmac
import hashlib

def verify_signature(payload, signature, secret):
    expected = hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected)
