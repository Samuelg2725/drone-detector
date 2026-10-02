#!/usr/bin/env python3
# drone-detector/api/routes/analytics.py
"""
Analytics and Statistics Routes

This module provides REST API endpoints for analytics and statistics:
- Detection statistics (counts, trends, patterns)
- Threat level analytics
- Drone type distribution
- Temporal patterns (hourly, daily, weekly, monthly)
- Geographic heatmaps
- Performance metrics
- Alert statistics
- System health analytics
- Custom report generation
- Data export (CSV, JSON, Excel)
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body, status
from fastapi.responses import JSONResponse, StreamingResponse
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
from pydantic import BaseModel, Field, validator
import io
import csv
import json

# Local imports
from api.dependencies import (
    get_current_user,
    get_storage,
    get_detection_service,
    require_permission,
    DateRangeParams,
    PaginationParams
)
from infrastructure.storage import get_storage_manager
from infrastructure.monitoring import get_logger

# Setup router
router = APIRouter()
logger = get_logger("api.routes.analytics")


# ============================================================================
# Enums and Models
# ============================================================================

class TimeGranularity(str, Enum):
    """Time aggregation granularity"""
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"


class ExportFormat(str, Enum):
    """Export file formats"""
    CSV = "csv"
    JSON = "json"
    EXCEL = "excel"
    HTML = "html"


class ReportType(str, Enum):
    """Report types"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


class DetectionStatisticsResponse(BaseModel):
    """Detection statistics response"""
    total_detections: int
    unique_drones: int
    avg_confidence: float
    high_threat_count: int
    medium_threat_count: int
    low_threat_count: int
    top_drone_types: List[Dict[str, Any]]
    detections_by_hour: Dict[int, int]
    detections_by_day: Dict[str, int]
    period_start: datetime
    period_end: datetime
    
    class Config:
        schema_extra = {
            "example": {
                "total_detections": 1247,
                "unique_drones": 89,
                "avg_confidence": 0.87,
                "high_threat_count": 342,
                "medium_threat_count": 567,
                "low_threat_count": 338,
                "top_drone_types": [
                    {"drone_type": "DJI Mavic 3", "count": 456},
                    {"drone_type": "FPV", "count": 234},
                    {"drone_type": "DJI Mini 3", "count": 189}
                ],
                "detections_by_hour": {
                    0: 12, 1: 8, 2: 5, 3: 3, 4: 2, 5: 4,
                    6: 15, 7: 45, 8: 89, 9: 120, 10: 145,
                    11: 156, 12: 167, 13: 178, 14: 189,
                    15: 201, 16: 234, 17: 256, 18: 234,
                    19: 198, 20: 167, 21: 134, 22: 98, 23: 45
                },
                "detections_by_day": {
                    "2024-01-01": 45,
                    "2024-01-02": 52,
                    "2024-01-03": 48
                },
                "period_start": "2024-01-01T00:00:00",
                "period_end": "2024-01-31T23:59:59"
            }
        }


class ThreatTrendResponse(BaseModel):
    """Threat trend response"""
    timestamp: List[str]
    high_threat: List[int]
    medium_threat: List[int]
    low_threat: List[int]
    total: List[int]
    granularity: str


class DroneTypeDistribution(BaseModel):
    """Drone type distribution"""
    drone_type: str
    count: int
    percentage: float
    avg_confidence: float
    threat_distribution: Dict[str, int]


class AlertStatisticsResponse(BaseModel):
    """Alert statistics response"""
    total_alerts: int
    active_alerts: int
    resolved_alerts: int
    acknowledged_alerts: int
    by_severity: Dict[str, int]
    by_category: Dict[str, int]
    avg_response_time_minutes: float
    escalation_rate: float
    top_alert_sources: List[Dict[str, Any]]


class PerformanceMetricsResponse(BaseModel):
    """Performance metrics response"""
    avg_detection_latency_ms: float
    p50_detection_latency_ms: float
    p95_detection_latency_ms: float
    p99_detection_latency_ms: float
    detections_per_minute: float
    false_positive_rate: float
    system_uptime_percent: float
    api_requests_per_minute: float
    api_error_rate: float
    timestamp: datetime


class GeoHeatmapData(BaseModel):
    """Geographic heatmap data"""
    points: List[Dict[str, Any]]
    bounds: Dict[str, float]
    total_points: int
    timestamp: datetime


# ============================================================================
# Detection Statistics Routes
# ============================================================================

@router.get("/detections/statistics", response_model=DetectionStatisticsResponse)
async def get_detection_statistics(
    date_range: DateRangeParams = Depends(),
    granularity: TimeGranularity = Query(TimeGranularity.DAY, description="Time granularity"),
    storage = Depends(get_storage),
    current_user = Depends(get_current_user)
):
    """
    Get detection statistics for a time period
    
    Returns comprehensive statistics about drone detections including:
    - Total counts and trends
    - Threat level distribution
    - Top drone types
    - Temporal patterns
    """
    start_date = date_range.start_datetime
    end_date = date_range.end_datetime
    
    # Get detections from storage
    detections = await storage.get_detections(
        start_time=start_date,
        end_time=end_date,
        limit=10000
    )
    
    if not detections:
        return DetectionStatisticsResponse(
            total_detections=0,
            unique_drones=0,
            avg_confidence=0.0,
            high_threat_count=0,
            medium_threat_count=0,
            low_threat_count=0,
            top_drone_types=[],
            detections_by_hour={},
            detections_by_day={},
            period_start=start_date,
            period_end=end_date
        )
    
    # Calculate statistics
    total = len(detections)
    
    # Unique drones (by remote_id or signature)
    unique_drones = len(set(
        d.get('remote_id') or d.get('signature_hash', '')
        for d in detections
        if d.get('remote_id') or d.get('signature_hash')
    ))
    
    # Average confidence
    avg_confidence = sum(d.get('confidence', 0) for d in detections) / total
    
    # Threat level counts
    high_threat = sum(1 for d in detections if d.get('threat_level') == 'HIGH')
    medium_threat = sum(1 for d in detections if d.get('threat_level') == 'MEDIUM')
    low_threat = sum(1 for d in detections if d.get('threat_level') == 'LOW')
    
    # Top drone types
    drone_type_counts = {}
    for d in detections:
        drone_type = d.get('drone_type', 'unknown')
        drone_type_counts[drone_type] = drone_type_counts.get(drone_type, 0) + 1
    
    top_drone_types = [
        {"drone_type": dt, "count": count}
        for dt, count in sorted(drone_type_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    ]
    
    # Detections by hour
    detections_by_hour = {h: 0 for h in range(24)}
    for d in detections:
        hour = d.get('timestamp', datetime.now()).hour
        detections_by_hour[hour] += 1
    
    # Detections by day
    detections_by_day = {}
    for d in detections:
        day = d.get('timestamp', datetime.now()).strftime("%Y-%m-%d")
        detections_by_day[day] = detections_by_day.get(day, 0) + 1
    
    return DetectionStatisticsResponse(
        total_detections=total,
        unique_drones=unique_drones,
        avg_confidence=avg_confidence,
        high_threat_count=high_threat,
        medium_threat_count=medium_threat,
        low_threat_count=low_threat,
        top_drone_types=top_drone_types,
        detections_by_hour=detections_by_hour,
        detections_by_day=detections_by_day,
        period_start=start_date,
        period_end=end_date
    )


@router.get("/detections/trends", response_model=ThreatTrendResponse)
async def get_detection_trends(
    date_range: DateRangeParams = Depends(),
    granularity: TimeGranularity = Query(TimeGranularity.DAY, description="Time granularity"),
    storage = Depends(get_storage),
    current_user = Depends(get_current_user)
):
    """
    Get detection trends over time
    
    Returns time-series data for threat levels and total detections
    """
    start_date = date_range.start_datetime
    end_date = date_range.end_datetime
    
    # Determine interval based on granularity
    if granularity == TimeGranularity.HOUR:
        delta = timedelta(hours=1)
        format_str = "%Y-%m-%d %H:00"
    elif granularity == TimeGranularity.DAY:
        delta = timedelta(days=1)
        format_str = "%Y-%m-%d"
    elif granularity == TimeGranularity.WEEK:
        delta = timedelta(days=7)
        format_str = "%Y-%m-%d"
    elif granularity == TimeGranularity.MONTH:
        delta = timedelta(days=30)
        format_str = "%Y-%m"
    else:
        delta = timedelta(days=1)
        format_str = "%Y-%m-%d"
    
    # Get detections
    detections = await storage.get_detections(
        start_time=start_date,
        end_time=end_date,
        limit=50000
    )
    
    # Initialize time buckets
    timestamps = []
    current = start_date
    while current <= end_date:
        timestamps.append(current.strftime(format_str))
        current += delta
    
    # Initialize data arrays
    high_threat = [0] * len(timestamps)
    medium_threat = [0] * len(timestamps)
    low_threat = [0] * len(timestamps)
    total = [0] * len(timestamps)
    
    # Fill data
    for d in detections:
        # Find bucket index
        det_time = d.get('timestamp', datetime.now())
        for i, ts_str in enumerate(timestamps):
            if granularity == TimeGranularity.HOUR:
                bucket_start = datetime.strptime(ts_str, format_str)
                bucket_end = bucket_start + delta
                if bucket_start <= det_time < bucket_end:
                    threat = d.get('threat_level', 'LOW')
                    if threat == 'HIGH':
                        high_threat[i] += 1
                    elif threat == 'MEDIUM':
                        medium_threat[i] += 1
                    else:
                        low_threat[i] += 1
                    total[i] += 1
                    break
            else:
                if det_time.strftime(format_str) == ts_str:
                    threat = d.get('threat_level', 'LOW')
                    if threat == 'HIGH':
                        high_threat[i] += 1
                    elif threat == 'MEDIUM':
                        medium_threat[i] += 1
                    else:
                        low_threat[i] += 1
                    total[i] += 1
                    break
    
    return ThreatTrendResponse(
        timestamp=timestamps,
        high_threat=high_threat,
        medium_threat=medium_threat,
        low_threat=low_threat,
        total=total,
        granularity=granularity.value
    )


@router.get("/detections/types", response_model=List[DroneTypeDistribution])
async def get_drone_type_distribution(
    date_range: DateRangeParams = Depends(),
    storage = Depends(get_storage),
    current_user = Depends(get_current_user)
):
    """
    Get distribution of detected drone types
    
    Returns detailed breakdown by drone type including counts, percentages, and threat distribution
    """
    start_date = date_range.start_datetime
    end_date = date_range.end_datetime
    
    detections = await storage.get_detections(
        start_time=start_date,
        end_time=end_date,
        limit=50000
    )
    
    # Group by drone type
    type_stats = {}
    for d in detections:
        drone_type = d.get('drone_type', 'unknown')
        if drone_type not in type_stats:
            type_stats[drone_type] = {
                'count': 0,
                'confidence_sum': 0,
                'high': 0,
                'medium': 0,
                'low': 0
            }
        
        type_stats[drone_type]['count'] += 1
        type_stats[drone_type]['confidence_sum'] += d.get('confidence', 0)
        
        threat = d.get('threat_level', 'LOW')
        if threat == 'HIGH':
            type_stats[drone_type]['high'] += 1
        elif threat == 'MEDIUM':
            type_stats[drone_type]['medium'] += 1
        else:
            type_stats[drone_type]['low'] += 1
    
    total = len(detections)
    
    result = []
    for drone_type, stats in sorted(type_stats.items(), key=lambda x: x[1]['count'], reverse=True):
        result.append(DroneTypeDistribution(
            drone_type=drone_type,
            count=stats['count'],
            percentage=(stats['count'] / total * 100) if total > 0 else 0,
            avg_confidence=stats['confidence_sum'] / stats['count'] if stats['count'] > 0 else 0,
            threat_distribution={
                'HIGH': stats['high'],
                'MEDIUM': stats['medium'],
                'LOW': stats['low']
            }
        ))
    
    return result


# ============================================================================
# Alert Statistics Routes
# ============================================================================

@router.get("/alerts/statistics", response_model=AlertStatisticsResponse)
async def get_alert_statistics(
    date_range: DateRangeParams = Depends(),
    storage = Depends(get_storage),
    current_user = Depends(get_current_user)
):
    """
    Get alert statistics for a time period
    
    Returns comprehensive statistics about alerts including:
    - Counts by severity and category
    - Response times
    - Escalation rates
    """
    start_date = date_range.start_datetime
    end_date = date_range.end_datetime
    
    alerts = await storage.get_alerts(
        start_time=start_date,
        end_time=end_date,
        limit=10000
    )
    
    if not alerts:
        return AlertStatisticsResponse(
            total_alerts=0,
            active_alerts=0,
            resolved_alerts=0,
            acknowledged_alerts=0,
            by_severity={},
            by_category={},
            avg_response_time_minutes=0.0,
            escalation_rate=0.0,
            top_alert_sources=[]
        )
    
    total = len(alerts)
    
    # Status counts
    active = sum(1 for a in alerts if not a.get('resolved', False))
    resolved = sum(1 for a in alerts if a.get('resolved', False))
    acknowledged = sum(1 for a in alerts if a.get('acknowledged', False))
    
    # Severity distribution
    by_severity = {}
    for a in alerts:
        severity = a.get('severity', 'UNKNOWN')
        by_severity[severity] = by_severity.get(severity, 0) + 1
    
    # Category distribution
    by_category = {}
    for a in alerts:
        category = a.get('category', 'UNKNOWN')
        by_category[category] = by_category.get(category, 0) + 1
    
    # Response times
    response_times = []
    for a in alerts:
        created = a.get('timestamp')
        resolved_at = a.get('resolved_at')
        if created and resolved_at:
            response_time = (resolved_at - created).total_seconds() / 60
            response_times.append(response_time)
    
    avg_response_time = sum(response_times) / len(response_times) if response_times else 0
    
    # Escalation rate
    escalated = sum(1 for a in alerts if a.get('escalation_level', 0) > 0)
    escalation_rate = (escalated / total * 100) if total > 0 else 0
    
    # Top alert sources
    source_counts = {}
    for a in alerts:
        source = a.get('source', 'unknown')
        source_counts[source] = source_counts.get(source, 0) + 1
    
    top_sources = [
        {"source": src, "count": count}
        for src, count in sorted(source_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    ]
    
    return AlertStatisticsResponse(
        total_alerts=total,
        active_alerts=active,
        resolved_alerts=resolved,
        acknowledged_alerts=acknowledged,
        by_severity=by_severity,
        by_category=by_category,
        avg_response_time_minutes=avg_response_time,
        escalation_rate=escalation_rate,
        top_alert_sources=top_sources
    )


# ============================================================================
# Performance Metrics Routes
# ============================================================================

@router.get("/performance", response_model=PerformanceMetricsResponse)
async def get_performance_metrics(
    date_range: DateRangeParams = Depends(),
    detection_service = Depends(get_detection_service),
    current_user = Depends(get_current_user)
):
    """
    Get system performance metrics
    
    Returns performance metrics including latency, throughput, and error rates
    """
    start_date = date_range.start_datetime
    end_date = date_range.end_datetime
    
    # Get metrics from monitoring system
    metrics = await detection_service.get_performance_metrics(start_date, end_date)
    
    # Calculate percentiles
    latencies = metrics.get('detection_latencies_ms', [])
    if latencies:
        sorted_latencies = sorted(latencies)
        p50 = sorted_latencies[int(len(sorted_latencies) * 0.5)]
        p95 = sorted_latencies[int(len(sorted_latencies) * 0.95)]
        p99 = sorted_latencies[int(len(sorted_latencies) * 0.99)]
        avg = sum(latencies) / len(latencies)
    else:
        avg = p50 = p95 = p99 = 0
    
    # Calculate detection rate
    detection_count = metrics.get('detection_count', 0)
    duration_hours = (end_date - start_date).total_seconds() / 3600
    detections_per_minute = detection_count / (duration_hours * 60) if duration_hours > 0 else 0
    
    # False positive rate
    false_positives = metrics.get('false_positives', 0)
    true_positives = metrics.get('true_positives', 1)
    false_positive_rate = false_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
    
    # API metrics
    api_requests = metrics.get('api_requests', 0)
    api_errors = metrics.get('api_errors', 0)
    api_requests_per_minute = api_requests / (duration_hours * 60) if duration_hours > 0 else 0
    api_error_rate = (api_errors / api_requests * 100) if api_requests > 0 else 0
    
    # System uptime
    system_uptime = metrics.get('system_uptime_seconds', 0)
    total_time = (end_date - start_date).total_seconds()
    uptime_percent = (system_uptime / total_time * 100) if total_time > 0 else 100
    
    return PerformanceMetricsResponse(
        avg_detection_latency_ms=avg,
        p50_detection_latency_ms=p50,
        p95_detection_latency_ms=p95,
        p99_detection_latency_ms=p99,
        detections_per_minute=detections_per_minute,
        false_positive_rate=false_positive_rate,
        system_uptime_percent=uptime_percent,
        api_requests_per_minute=api_requests_per_minute,
        api_error_rate=api_error_rate,
        timestamp=datetime.now()
    )


# ============================================================================
# Geographic Analytics Routes
# ============================================================================

@router.get("/heatmap", response_model=GeoHeatmapData)
async def get_detection_heatmap(
    date_range: DateRangeParams = Depends(),
    min_confidence: float = Query(0.5, ge=0, le=1, description="Minimum confidence"),
    bounds: Optional[str] = Query(None, description="Bounds: min_lat,max_lat,min_lon,max_lon"),
    storage = Depends(get_storage),
    current_user = Depends(get_current_user)
):
    """
    Get geographic heatmap data for detections
    
    Returns points for heatmap visualization with bounds
    """
    start_date = date_range.start_datetime
    end_date = date_range.end_datetime
    
    # Parse bounds
    bounds_dict = None
    if bounds:
        parts = bounds.split(',')
        if len(parts) == 4:
            bounds_dict = {
                'min_lat': float(parts[0]),
                'max_lat': float(parts[1]),
                'min_lon': float(parts[2]),
                'max_lon': float(parts[3])
            }
    
    detections = await storage.get_detections(
        start_time=start_date,
        end_time=end_date,
        min_confidence=min_confidence,
        bounds=bounds_dict,
        limit=10000
    )
    
    # Extract points with coordinates
    points = []
    for d in detections:
        lat = d.get('latitude')
        lon = d.get('longitude')
        if lat is not None and lon is not None:
            points.append({
                'lat': lat,
                'lon': lon,
                'confidence': d.get('confidence', 0),
                'threat_level': d.get('threat_level', 'LOW'),
                'drone_type': d.get('drone_type', 'unknown'),
                'timestamp': d.get('timestamp', datetime.now()).isoformat()
            })
    
    # Calculate bounds from points if not provided
    if bounds_dict is None and points:
        bounds_dict = {
            'min_lat': min(p['lat'] for p in points),
            'max_lat': max(p['lat'] for p in points),
            'min_lon': min(p['lon'] for p in points),
            'max_lon': max(p['lon'] for p in points)
        }
    else:
        bounds_dict = {'min_lat': 0, 'max_lat': 0, 'min_lon': 0, 'max_lon': 0}
    
    return GeoHeatmapData(
        points=points,
        bounds=bounds_dict,
        total_points=len(points),
        timestamp=datetime.now()
    )


@router.get("/hotspots")
async def get_detection_hotspots(
    date_range: DateRangeParams = Depends(),
    min_detections: int = Query(10, ge=1, description="Minimum detections to consider a hotspot"),
    radius_km: float = Query(0.5, ge=0.1, description="Hotspot radius in km"),
    storage = Depends(get_storage),
    current_user = Depends(get_current_user)
):
    """
    Identify geographic hotspots (clusters of detections)
    
    Returns clustered hotspots with coordinates and statistics
    """
    start_date = date_range.start_datetime
    end_date = date_range.end_datetime
    
    detections = await storage.get_detections(
        start_time=start_date,
        end_time=end_date,
        limit=50000
    )
    
    # Extract coordinates
    coords = []
    for d in detections:
        lat = d.get('latitude')
        lon = d.get('longitude')
        if lat is not None and lon is not None:
            coords.append((lat, lon))
    
    if not coords:
        return {"hotspots": []}
    
    # Simple grid-based clustering
    # In production, use DBSCAN or similar algorithm
    grid_size_deg = radius_km / 111.0  # Convert km to degrees (approx)
    
    grid = {}
    for lat, lon in coords:
        grid_x = int(lat / grid_size_deg)
        grid_y = int(lon / grid_size_deg)
        key = (grid_x, grid_y)
        if key not in grid:
            grid[key] = {'count': 0, 'lats': [], 'lons': []}
        grid[key]['count'] += 1
        grid[key]['lats'].append(lat)
        grid[key]['lons'].append(lon)
    
    hotspots = []
    for (grid_x, grid_y), data in grid.items():
        if data['count'] >= min_detections:
            hotspot = {
                'center_lat': sum(data['lats']) / len(data['lats']),
                'center_lon': sum(data['lons']) / len(data['lons']),
                'detection_count': data['count'],
                'grid_cell': (grid_x, grid_y)
            }
            hotspots.append(hotspot)
    
    # Sort by detection count
    hotspots.sort(key=lambda x: x['detection_count'], reverse=True)
    
    return {
        "hotspots": hotspots[:20],
        "total_hotspots": len(hotspots),
        "radius_km": radius_km,
        "period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat()
        }
    }


# ============================================================================
# Report Generation Routes
# ============================================================================

@router.post("/reports/generate")
async def generate_report(
    report_type: ReportType = Body(..., embed=True),
    start_date: datetime = Body(..., embed=True),
    end_date: datetime = Body(..., embed=True),
    format: ExportFormat = Body(ExportFormat.JSON, embed=True),
    detection_service = Depends(get_detection_service),
    current_user = Depends(get_current_user),
    _ = Depends(require_permission("analytics:reports"))
):
    """
    Generate a custom analytics report
    
    Creates a report with configurable date range and format
    """
    report = await detection_service.generate_report(
        report_type=report_type.value,
        start_date=start_date,
        end_date=end_date,
        format=format.value
    )
    
    return {
        "success": True,
        "message": f"Report generated - {report_type.value}",
        "report_id": report.get('id'),
        "format": format.value,
        "file_url": report.get('url'),
        "generated_at": datetime.now()
    }


@router.get("/reports/{report_id}")
async def download_report(
    report_id: str = Path(..., description="Report ID"),
    detection_service = Depends(get_detection_service),
    current_user = Depends(get_current_user),
    _ = Depends(require_permission("analytics:reports"))
):
    """
    Download a generated report
    """
    report = await detection_service.get_report(report_id)
    
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report {report_id} not found"
        )
    
    # Stream file response
    return StreamingResponse(
        io.BytesIO(report['content']),
        media_type=report['content_type'],
        headers={
            "Content-Disposition": f"attachment; filename={report['filename']}"
        }
    )


@router.get("/reports/list")
async def list_reports(
    pagination: PaginationParams = Depends(),
    detection_service = Depends(get_detection_service),
    current_user = Depends(get_current_user),
    _ = Depends(require_permission("analytics:reports"))
):
    """
    List available reports
    """
    reports = await detection_service.list_reports(
        limit=pagination.limit,
        offset=pagination.offset
    )
    
    return {
        "reports": reports,
        "pagination": {
            "page": pagination.page,
            "page_size": pagination.page_size,
            "total": len(reports)
        }
    }


# ============================================================================
# Data Export Routes
# ============================================================================

@router.post("/export/detections")
async def export_detections(
    date_range: DateRangeParams = Depends(),
    format: ExportFormat = Query(ExportFormat.JSON, description="Export format"),
    storage = Depends(get_storage),
    current_user = Depends(get_current_user),
    _ = Depends(require_permission("analytics:export"))
):
    """
    Export detection data to file
    
    Exports detections in CSV, JSON, or Excel format
    """
    start_date = date_range.start_datetime
    end_date = date_range.end_datetime
    
    detections = await storage.get_detections(
        start_time=start_date,
        end_time=end_date,
        limit=100000
    )
    
    if format == ExportFormat.CSV:
        # Generate CSV
        output = io.StringIO()
        if detections:
            fieldnames = list(detections[0].keys())
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(detections)
        
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode()),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=detections_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.csv"
            }
        )
    
    elif format == ExportFormat.JSON:
        # Generate JSON
        content = json.dumps({
            "export_date": datetime.now().isoformat(),
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "count": len(detections),
            "data": detections
        }, indent=2, default=str)
        
        return StreamingResponse(
            io.BytesIO(content.encode()),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=detections_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.json"
            }
        )
    
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Export format {format.value} not implemented yet"
        )


# ============================================================================
# Dashboard Summary Route
# ============================================================================

@router.get("/dashboard/summary")
async def get_dashboard_summary(
    detection_service = Depends(get_detection_service),
    storage = Depends(get_storage),
    current_user = Depends(get_current_user)
):
    """
    Get dashboard summary data (last 24 hours)
    
    Returns a comprehensive summary for the main dashboard
    """
    now = datetime.now()
    last_24h = now - timedelta(hours=24)
    
    # Get recent detections
    detections = await storage.get_detections(
        start_time=last_24h,
        end_time=now,
        limit=1000
    )
    
    # Get active alerts
    alerts = await storage.get_active_alerts()
    
    # Get recent detections count by hour
    detections_by_hour = {h: 0 for h in range(24)}
    for d in detections:
        hour = d.get('timestamp', now).hour
        detections_by_hour[hour] += 1
    
    # Get threat level breakdown
    threat_breakdown = {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
    for d in detections:
        threat = d.get('threat_level', 'LOW')
        if threat in threat_breakdown:
            threat_breakdown[threat] += 1
    
    # Get top drone types
    drone_type_counts = {}
    for d in detections[:100]:  # Limit for performance
        drone_type = d.get('drone_type', 'unknown')
        drone_type_counts[drone_type] = drone_type_counts.get(drone_type, 0) + 1
    
    top_drone_types = sorted(
        [{"type": k, "count": v} for k, v in drone_type_counts.items()],
        key=lambda x: x['count'], reverse=True
    )[:5]
    
    # Get system metrics
    performance_metrics = await detection_service.get_performance_metrics(last_24h, now)
    
    return {
        "period": {
            "start": last_24h.isoformat(),
            "end": now.isoformat(),
            "duration_hours": 24
        },
        "overview": {
            "total_detections": len(detections),
            "active_alerts": len(alerts),
            "unique_drone_types": len(drone_type_counts),
            "high_threat_percentage": (threat_breakdown['HIGH'] / len(detections) * 100) if detections else 0
        },
        "detections_by_hour": detections_by_hour,
        "threat_breakdown": threat_breakdown,
        "top_drone_types": top_drone_types,
        "performance": {
            "avg_latency_ms": performance_metrics.get('avg_latency_ms', 0),
            "detections_per_minute": len(detections) / 24 / 60,
            "false_positive_rate": performance_metrics.get('false_positive_rate', 0)
        },
        "timestamp": now.isoformat()
    }


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    print("Analytics Routes Module")
    print("=" * 50)
    
    print("\nAvailable Endpoints:")
    print("  GET  /detections/statistics  - Detection statistics")
    print("  GET  /detections/trends      - Detection trends over time")
    print("  GET  /detections/types       - Drone type distribution")
    print("  GET  /alerts/statistics      - Alert statistics")
    print("  GET  /performance            - Performance metrics")
    print("  GET  /heatmap                - Geographic heatmap data")
    print("  GET  /hotspots               - Detection hotspots")
    print("  POST /reports/generate       - Generate report")
    print("  GET  /reports/{id}           - Download report")
    print("  GET  /reports/list           - List reports")
    print("  POST /export/detections      - Export detection data")
    print("  GET  /dashboard/summary      - Dashboard summary")
    
    print("\n" + "=" * 50)