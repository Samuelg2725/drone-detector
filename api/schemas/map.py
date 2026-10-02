#!/usr/bin/env python3
# drone-detector/api/schemas/map.py
"""
GeoJSON Models for Map and Geolocation

This module provides GeoJSON-compliant Pydantic models for geographic data,
enabling:
- Drone position tracking
- Geofence zone definitions
- Flight path visualization
- Heat map generation
- Proximity alerts
- Real-time position updates
- Historical track playback
- Area of interest management
- No-fly zone visualization
- Coverage area mapping
"""

from typing import List, Optional, Dict, Any, Union, Tuple
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator, root_validator
from geojson import Point, LineString, Polygon, MultiPoint, MultiLineString, MultiPolygon


# ============================================================================
# Enums
# ============================================================================

class GeometryType(str, Enum):
    """GeoJSON geometry types"""
    POINT = "Point"
    LINE_STRING = "LineString"
    POLYGON = "Polygon"
    MULTI_POINT = "MultiPoint"
    MULTI_LINE_STRING = "MultiLineString"
    MULTI_POLYGON = "MultiPolygon"
    GEOMETRY_COLLECTION = "GeometryCollection"


class FeatureType(str, Enum):
    """GeoJSON feature types"""
    FEATURE = "Feature"
    FEATURE_COLLECTION = "FeatureCollection"


class DroneStatus(str, Enum):
    """Drone operational status"""
    IDLE = "idle"
    TAKEOFF = "takeoff"
    FLYING = "flying"
    LANDING = "landing"
    LANDED = "landed"
    EMERGENCY = "emergency"
    UNKNOWN = "unknown"


class ThreatZoneType(str, Enum):
    """Geofence zone types"""
    NO_FLY = "no_fly"
    RESTRICTED = "restricted"
    WARNING = "warning"
    AUTHORIZED = "authorized"
    MONITORED = "monitored"
    CUSTOM = "custom"


# ============================================================================
# Base GeoJSON Models
# ============================================================================

class Position(BaseModel):
    """Position coordinates (longitude, latitude, altitude)"""
    longitude: float = Field(..., ge=-180, le=180, description="Longitude in degrees")
    latitude: float = Field(..., ge=-90, le=90, description="Latitude in degrees")
    altitude: Optional[float] = Field(None, ge=-500, le=10000, description="Altitude in meters")
    
    @property
    def coordinates(self) -> Tuple[float, float]:
        """Return as (longitude, latitude) tuple"""
        return (self.longitude, self.latitude)
    
    @property
    def coordinates_3d(self) -> Tuple[float, float, float]:
        """Return as (longitude, latitude, altitude) tuple"""
        if self.altitude is not None:
            return (self.longitude, self.latitude, self.altitude)
        return (self.longitude, self.latitude, 0.0)
    
    class Config:
        schema_extra = {
            "example": {
                "longitude": -122.4194,
                "latitude": 37.7749,
                "altitude": 100.0
            }
        }


class BoundingBox(BaseModel):
    """GeoJSON bounding box"""
    min_longitude: float = Field(..., ge=-180, le=180)
    min_latitude: float = Field(..., ge=-90, le=90)
    max_longitude: float = Field(..., ge=-180, le=180)
    max_latitude: float = Field(..., ge=-90, le=90)
    
    @validator('max_longitude')
    def validate_max_longitude(cls, v, values):
        if 'min_longitude' in values and v <= values['min_longitude']:
            raise ValueError('max_longitude must be greater than min_longitude')
        return v
    
    @validator('max_latitude')
    def validate_max_latitude(cls, v, values):
        if 'min_latitude' in values and v <= values['min_latitude']:
            raise ValueError('max_latitude must be greater than min_latitude')
        return v
    
    @property
    def as_list(self) -> List[float]:
        """Return as [min_lon, min_lat, max_lon, max_lat]"""
        return [self.min_longitude, self.min_latitude, self.max_longitude, self.max_latitude]
    
    @property
    def center(self) -> Tuple[float, float]:
        """Return center point"""
        return (
            (self.min_longitude + self.max_longitude) / 2,
            (self.min_latitude + self.max_latitude) / 2
        )


# ============================================================================
# Geometry Models
# ============================================================================

class PointGeometry(BaseModel):
    """GeoJSON Point geometry"""
    type: GeometryType = GeometryType.POINT
    coordinates: List[float] = Field(..., description="[longitude, latitude, altitude?]")
    
    @validator('coordinates')
    def validate_coordinates(cls, v):
        if len(v) < 2 or len(v) > 3:
            raise ValueError('Coordinates must be [lon, lat] or [lon, lat, alt]')
        if not (-180 <= v[0] <= 180):
            raise ValueError('Longitude must be between -180 and 180')
        if not (-90 <= v[1] <= 90):
            raise ValueError('Latitude must be between -90 and 90')
        if len(v) == 3 and not (-500 <= v[2] <= 10000):
            raise ValueError('Altitude must be between -500 and 10000')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "type": "Point",
                "coordinates": [-122.4194, 37.7749, 100.0]
            }
        }


class LineStringGeometry(BaseModel):
    """GeoJSON LineString geometry"""
    type: GeometryType = GeometryType.LINE_STRING
    coordinates: List[List[float]] = Field(..., description="List of [lon, lat, alt?] points")
    
    @validator('coordinates')
    def validate_coordinates(cls, v):
        if len(v) < 2:
            raise ValueError('LineString must have at least 2 points')
        for coord in v:
            if len(coord) < 2 or len(coord) > 3:
                raise ValueError('Each point must be [lon, lat] or [lon, lat, alt]')
        return v


class PolygonGeometry(BaseModel):
    """GeoJSON Polygon geometry"""
    type: GeometryType = GeometryType.POLYGON
    coordinates: List[List[List[float]]] = Field(..., description="List of rings (linear rings)")
    
    @validator('coordinates')
    def validate_coordinates(cls, v):
        if not v:
            raise ValueError('Polygon must have at least one ring')
        for ring in v:
            if len(ring) < 4:
                raise ValueError('Each ring must have at least 4 points')
            # Check if ring is closed
            if ring[0] != ring[-1]:
                raise ValueError('Ring must be closed (first and last point must match)')
        return v


class MultiPointGeometry(BaseModel):
    """GeoJSON MultiPoint geometry"""
    type: GeometryType = GeometryType.MULTI_POINT
    coordinates: List[List[float]] = Field(..., description="List of points")
    
    @validator('coordinates')
    def validate_coordinates(cls, v):
        if len(v) < 1:
            raise ValueError('MultiPoint must have at least one point')
        return v


class MultiLineStringGeometry(BaseModel):
    """GeoJSON MultiLineString geometry"""
    type: GeometryType = GeometryType.MULTI_LINE_STRING
    coordinates: List[List[List[float]]] = Field(..., description="List of line strings")


class MultiPolygonGeometry(BaseModel):
    """GeoJSON MultiPolygon geometry"""
    type: GeometryType = GeometryType.MULTI_POLYGON
    coordinates: List[List[List[List[float]]]] = Field(..., description="List of polygons")


class GeometryCollection(BaseModel):
    """GeoJSON GeometryCollection"""
    type: GeometryType = GeometryType.GEOMETRY_COLLECTION
    geometries: List[Union[
        PointGeometry,
        LineStringGeometry,
        PolygonGeometry,
        MultiPointGeometry,
        MultiLineStringGeometry,
        MultiPolygonGeometry
    ]] = Field(..., description="List of geometries")


# ============================================================================
# Properties Models
# ============================================================================

class DroneProperties(BaseModel):
    """Drone feature properties"""
    drone_id: str = Field(..., description="Unique drone identifier")
    drone_type: str = Field(..., description="Drone model/type")
    status: DroneStatus = Field(DroneStatus.UNKNOWN, description="Drone status")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="Detection confidence")
    threat_level: str = Field("LOW", description="Threat level (LOW, MEDIUM, HIGH, CRITICAL)")
    speed: Optional[float] = Field(None, ge=0, description="Speed in m/s")
    heading: Optional[float] = Field(None, ge=0, le=360, description="Heading in degrees")
    altitude: Optional[float] = Field(None, description="Altitude in meters")
    battery: Optional[float] = Field(None, ge=0, le=100, description="Battery percentage")
    operator: Optional[str] = Field(None, description="Operator ID")
    remote_id: Optional[str] = Field(None, description="Remote ID")
    color: Optional[str] = Field(None, description="Display color for map")
    icon: Optional[str] = Field(None, description="Icon name for marker")
    last_update: datetime = Field(default_factory=datetime.now, description="Last update timestamp")
    
    class Config:
        schema_extra = {
            "example": {
                "drone_id": "drone_001",
                "drone_type": "DJI Mavic 3",
                "status": "flying",
                "confidence": 0.95,
                "threat_level": "HIGH",
                "speed": 15.5,
                "heading": 180.0,
                "altitude": 100.0,
                "battery": 75,
                "operator": "unknown",
                "remote_id": "ABC123",
                "color": "#ff0000",
                "icon": "drone",
                "last_update": "2024-01-15T10:30:00Z"
            }
        }


class GeofenceProperties(BaseModel):
    """Geofence feature properties"""
    zone_id: str = Field(..., description="Unique zone identifier")
    name: str = Field(..., description="Zone name")
    zone_type: ThreatZoneType = Field(..., description="Zone type")
    description: Optional[str] = Field(None, description="Zone description")
    restricted: bool = Field(False, description="Is this a restricted zone?")
    warning_threshold: Optional[float] = Field(None, description="Warning distance in meters")
    alert_threshold: Optional[float] = Field(None, description="Alert distance in meters")
    active: bool = Field(True, description="Is zone active?")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    
    @property
    def fill_color(self) -> str:
        """Get fill color based on zone type"""
        colors = {
            ThreatZoneType.NO_FLY: "#ff0000",
            ThreatZoneType.RESTRICTED: "#ff6600", 
            ThreatZoneType.WARNING: "#ffcc00",
            ThreatZoneType.AUTHORIZED: "#00ff00",
            ThreatZoneType.MONITORED: "#00ccff"
        }
        return colors.get(self.zone_type, "#888888")
    
    @property
    def stroke_color(self) -> str:
        """Get stroke color based on zone type"""
        return self.fill_color
    
    class Config:
        schema_extra = {
            "example": {
                "zone_id": "zone_001",
                "name": "Airport No-Fly Zone",
                "zone_type": "no_fly",
                "description": "5km radius around airport",
                "restricted": True,
                "warning_threshold": 1000,
                "alert_threshold": 500,
                "active": True,
                "created_at": "2024-01-15T10:00:00Z"
            }
        }


class TrackProperties(BaseModel):
    """Flight track properties"""
    track_id: str = Field(..., description="Unique track identifier")
    drone_id: str = Field(..., description="Drone identifier")
    drone_type: str = Field(..., description="Drone type")
    start_time: datetime = Field(..., description="Track start time")
    end_time: Optional[datetime] = Field(None, description="Track end time")
    duration_seconds: Optional[float] = Field(None, description="Track duration")
    total_distance_meters: Optional[float] = Field(None, description="Total track distance")
    max_speed_ms: Optional[float] = Field(None, description="Maximum speed")
    avg_speed_ms: Optional[float] = Field(None, description="Average speed")
    max_altitude_m: Optional[float] = Field(None, description="Maximum altitude")
    color: str = Field("#00ff00", description="Track color")
    opacity: float = Field(0.7, ge=0, le=1, description="Track opacity")
    width: int = Field(2, ge=1, le=10, description="Line width in pixels")
    
    class Config:
        schema_extra = {
            "example": {
                "track_id": "track_001",
                "drone_id": "drone_001",
                "drone_type": "DJI Mavic 3",
                "start_time": "2024-01-15T10:00:00Z",
                "end_time": "2024-01-15T10:30:00Z",
                "duration_seconds": 1800,
                "total_distance_meters": 5000,
                "max_speed_ms": 20.5,
                "avg_speed_ms": 2.78,
                "max_altitude_m": 120,
                "color": "#00ff00",
                "opacity": 0.7,
                "width": 2
            }
        }


class HeatmapProperties(BaseModel):
    """Heatmap properties"""
    intensity: float = Field(..., ge=0, le=1, description="Detection intensity")
    detection_count: int = Field(0, description="Number of detections at location")
    threat_level: Optional[str] = Field(None, description="Aggregated threat level")
    time_window: Optional[str] = Field(None, description="Time window for aggregation")
    
    class Config:
        schema_extra = {
            "example": {
                "intensity": 0.85,
                "detection_count": 25,
                "threat_level": "HIGH",
                "time_window": "24h"
            }
        }


# ============================================================================
# GeoJSON Feature Models
# ============================================================================

class GeoJSONFeature(BaseModel):
    """GeoJSON Feature"""
    type: FeatureType = FeatureType.FEATURE
    geometry: Union[
        PointGeometry,
        LineStringGeometry,
        PolygonGeometry,
        MultiPointGeometry,
        MultiLineStringGeometry,
        MultiPolygonGeometry,
        GeometryCollection
    ] = Field(..., description="Feature geometry")
    properties: Union[DroneProperties, GeofenceProperties, TrackProperties, HeatmapProperties, Dict[str, Any]] = Field(
        default_factory=dict, description="Feature properties"
    )
    id: Optional[str] = Field(None, description="Feature identifier")
    bbox: Optional[BoundingBox] = Field(None, description="Feature bounding box")


class GeoJSONFeatureCollection(BaseModel):
    """GeoJSON FeatureCollection"""
    type: FeatureType = FeatureType.FEATURE_COLLECTION
    features: List[GeoJSONFeature] = Field(..., description="List of features")
    bbox: Optional[BoundingBox] = Field(None, description="Collection bounding box")
    
    @property
    def feature_count(self) -> int:
        """Get number of features"""
        return len(self.features)
    
    def add_feature(self, feature: GeoJSONFeature) -> None:
        """Add a feature to the collection"""
        self.features.append(feature)


# ============================================================================
# Specialized Response Models
# ============================================================================

class DronePositionResponse(BaseModel):
    """Drone position response"""
    feature: GeoJSONFeature = Field(..., description="Drone position as GeoJSON feature")
    
    class Config:
        schema_extra = {
            "example": {
                "feature": {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [-122.4194, 37.7749, 100.0]
                    },
                    "properties": {
                        "drone_id": "drone_001",
                        "drone_type": "DJI Mavic 3",
                        "threat_level": "HIGH",
                        "confidence": 0.95
                    }
                }
            }
        }


class DroneTracksResponse(BaseModel):
    """Drone tracks response"""
    collection: GeoJSONFeatureCollection = Field(..., description="Track collection")
    total_tracks: int = Field(..., description="Total number of tracks")
    tracks_by_type: Dict[str, int] = Field(default_factory=dict, description="Track count by drone type")


class GeofenceZonesResponse(BaseModel):
    """Geofence zones response"""
    collection: GeoJSONFeatureCollection = Field(..., description="Geofence zone collection")
    active_zones: int = Field(..., description="Number of active zones")
    zones_by_type: Dict[str, int] = Field(default_factory=dict, description="Zone count by type")


class DetectionHeatmapResponse(BaseModel):
    """Detection heatmap response"""
    collection: GeoJSONFeatureCollection = Field(..., description="Heatmap point collection")
    total_points: int = Field(..., description="Total number of points")
    intensity_range: Tuple[float, float] = Field(..., description="Min/max intensity")
    time_range: Tuple[datetime, datetime] = Field(..., description="Time range of data")


class LiveTrackResponse(BaseModel):
    """Real-time drone tracking response"""
    features: List[GeoJSONFeature] = Field(..., description="Current drone positions")
    timestamp: datetime = Field(default_factory=datetime.now)
    active_drones: int = Field(0, description="Number of active drones")
    update_interval_ms: int = Field(1000, description="Update interval in milliseconds")


class ProximityAlert(BaseModel):
    """Proximity alert response"""
    alert_id: str
    drone_id: str
    drone_position: Position
    zone_id: str
    zone_name: str
    zone_type: ThreatZoneType
    distance_meters: float
    severity: str  # warning, alert, critical
    timestamp: datetime
    action_required: bool
    recommended_action: str
    
    class Config:
        schema_extra = {
            "example": {
                "alert_id": "alert_001",
                "drone_id": "drone_001",
                "drone_position": {
                    "longitude": -122.4194,
                    "latitude": 37.7749,
                    "altitude": 100.0
                },
                "zone_id": "zone_001",
                "zone_name": "Airport No-Fly Zone",
                "zone_type": "no_fly",
                "distance_meters": 450,
                "severity": "critical",
                "timestamp": "2024-01-15T10:30:00Z",
                "action_required": True,
                "recommended_action": "Immediate intervention required"
            }
        }


class AreaCoverageResponse(BaseModel):
    """Area coverage response"""
    coverage_polygon: PolygonGeometry
    coverage_percentage: float = Field(..., ge=0, le=100)
    monitored_area_sqkm: float
    blind_spots: List[PolygonGeometry]
    recommendation: str


# ============================================================================
# Request Models
# ============================================================================

class GeofenceCreateRequest(BaseModel):
    """Geofence zone creation request"""
    name: str = Field(..., min_length=1, max_length=100)
    zone_type: ThreatZoneType
    geometry: PolygonGeometry
    description: Optional[str] = None
    warning_threshold: Optional[float] = Field(None, ge=0, description="Warning threshold in meters")
    alert_threshold: Optional[float] = Field(None, ge=0, description="Alert threshold in meters")
    active: bool = True


class GeofenceUpdateRequest(BaseModel):
    """Geofence zone update request"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    zone_type: Optional[ThreatZoneType] = None
    geometry: Optional[PolygonGeometry] = None
    description: Optional[str] = None
    warning_threshold: Optional[float] = Field(None, ge=0)
    alert_threshold: Optional[float] = Field(None, ge=0)
    active: Optional[bool] = None


class TrackQueryParams(BaseModel):
    """Track query parameters"""
    drone_id: Optional[str] = None
    drone_type: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = Field(100, ge=1, le=1000)
    simplify_tolerance: Optional[float] = Field(None, ge=0, description="Track simplification tolerance in meters")


class HeatmapQueryParams(BaseModel):
    """Heatmap query parameters"""
    start_time: datetime
    end_time: datetime
    min_confidence: float = Field(0.5, ge=0, le=1)
    threat_levels: List[str] = Field(default=["LOW", "MEDIUM", "HIGH", "CRITICAL"])
    grid_size: int = Field(50, ge=10, le=500, description="Grid size in pixels")
    bounds: Optional[BoundingBox] = None


# ============================================================================
# Utility Functions
# ============================================================================

def create_point_feature(
    longitude: float,
    latitude: float,
    altitude: Optional[float],
    properties: Dict[str, Any]
) -> GeoJSONFeature:
    """Create a point GeoJSON feature"""
    coordinates = [longitude, latitude]
    if altitude is not None:
        coordinates.append(altitude)
    
    return GeoJSONFeature(
        geometry=PointGeometry(coordinates=coordinates),
        properties=properties
    )


def create_line_feature(
    coordinates: List[Tuple[float, float, Optional[float]]],
    properties: Dict[str, Any]
) -> GeoJSONFeature:
    """Create a line string GeoJSON feature"""
    coord_list = []
    for coord in coordinates:
        if len(coord) == 2:
            coord_list.append([coord[0], coord[1]])
        else:
            coord_list.append([coord[0], coord[1], coord[2]])
    
    return GeoJSONFeature(
        geometry=LineStringGeometry(coordinates=coord_list),
        properties=properties
    )


def create_polygon_feature(
    rings: List[List[Tuple[float, float]]],
    properties: Dict[str, Any]
) -> GeoJSONFeature:
    """Create a polygon GeoJSON feature"""
    coord_rings = []
    for ring in rings:
        coord_ring = [[lon, lat] for lon, lat in ring]
        # Ensure ring is closed
        if coord_ring[0] != coord_ring[-1]:
            coord_ring.append(coord_ring[0])
        coord_rings.append(coord_ring)
    
    return GeoJSONFeature(
        geometry=PolygonGeometry(coordinates=coord_rings),
        properties=properties
    )


def create_feature_collection(features: List[GeoJSONFeature]) -> GeoJSONFeatureCollection:
    """Create a feature collection from a list of features"""
    return GeoJSONFeatureCollection(features=features)


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    """Example usage of map schemas"""
    
    print("Map Schemas Module Test")
    print("=" * 50)
    
    # Create a point feature
    print("\n1. Creating Drone Position Feature:")
    drone_feature = create_point_feature(
        longitude=-122.4194,
        latitude=37.7749,
        altitude=100.0,
        properties={
            "drone_id": "drone_001",
            "drone_type": "DJI Mavic 3",
            "threat_level": "HIGH",
            "confidence": 0.95
        }
    )
    print(f"   Feature type: {drone_feature.type}")
    print(f"   Geometry: {drone_feature.geometry.type}")
    
    # Create a polygon feature (geofence)
    print("\n2. Creating Geofence Zone Feature:")
    
    # Define a square polygon
    square_ring = [
        (-122.4300, 37.7700),
        (-122.4300, 37.7800),
        (-122.4100, 37.7800),
        (-122.4100, 37.7700)
    ]
    
    geofence_feature = create_polygon_feature(
        rings=[square_ring],
        properties={
            "zone_id": "zone_001",
            "name": "Test Zone",
            "zone_type": "restricted"
        }
    )
    print(f"   Zone type: {geofence_feature.properties.get('zone_type')}")
    
    # Create a feature collection
    print("\n3. Creating Feature Collection:")
    collection = create_feature_collection([drone_feature, geofence_feature])
    print(f"   Number of features: {collection.feature_count}")
    
    # Create bounding box
    print("\n4. Creating Bounding Box:")
    bbox = BoundingBox(
        min_longitude=-122.5,
        min_latitude=37.7,
        max_longitude=-122.3,
        max_latitude=37.9
    )
    print(f"   Center: {bbox.center}")
    
    # Create position
    print("\n5. Creating Position:")
    pos = Position(longitude=-122.4194, latitude=37.7749, altitude=100.0)
    print(f"   Coordinates: {pos.coordinates}")
    print(f"   3D Coordinates: {pos.coordinates_3d}")
    
    # Validate geometry
    print("\n6. Geometry Validation:")
    try:
        valid_point = PointGeometry(coordinates=[-122.4194, 37.7749, 100.0])
        print("   Valid point geometry created")
    except Exception as e:
        print(f"   Validation error: {e}")
    
    print("\n" + "=" * 50)
    print("Map schemas test complete!")