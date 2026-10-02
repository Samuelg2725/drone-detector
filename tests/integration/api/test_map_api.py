#!/usr/bin/env python3
"""
Integration Tests for Map API

Tests for map-related endpoints including:
- GeoJSON data retrieval
- Drone position tracking
- Geofence management
- Heatmap data
- Track history
- Proximity alerts
- Area coverage
"""

import asyncio
import json
import unittest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timedelta
from pathlib import Path
import sys
import tempfile

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from fastapi.testclient import TestClient
from fastapi import FastAPI

# Import application and dependencies
from api.main import create_app
from api.routes.map import router
from api.schemas.map import (
    Position,
    BoundingBox,
    PointGeometry,
    PolygonGeometry,
    GeoJSONFeature,
    GeoJSONFeatureCollection,
    DroneProperties,
    GeofenceProperties,
    ThreatZoneType,
    DroneStatus
)
from infrastructure.storage.database import DatabaseManager
from domain.entities.detection import DetectionEvent, ThreatLevel
from app.services import MapService, GeofenceService


# ============================================================================
# Test Data Generators
# ============================================================================

class MapTestData:
    """Generate test data for map API tests"""
    
    @staticmethod
    def create_test_drone_position(
        drone_id: str = "drone_001",
        latitude: float = 37.7749,
        longitude: float = -122.4194,
        altitude: float = 100.0,
        threat_level: str = "LOW"
    ) -> dict:
        """Create test drone position data"""
        return {
            'drone_id': drone_id,
            'drone_type': 'DJI Mavic 3',
            'latitude': latitude,
            'longitude': longitude,
            'altitude': altitude,
            'speed': 12.5,
            'heading': 180.0,
            'threat_level': threat_level,
            'confidence': 0.95,
            'timestamp': datetime.now().isoformat(),
            'status': 'flying'
        }
    
    @staticmethod
    def create_test_geofence_zone(
        zone_id: str = "zone_001",
        name: str = "Test Zone",
        zone_type: str = "restricted",
        coordinates: list = None
    ) -> dict:
        """Create test geofence zone data"""
        if coordinates is None:
            coordinates = [
                (-122.4300, 37.7700),
                (-122.4300, 37.7800),
                (-122.4100, 37.7800),
                (-122.4100, 37.7700)
            ]
        
        return {
            'id': zone_id,
            'name': name,
            'zone_type': zone_type,
            'description': 'Test geofence zone',
            'geometry': {
                'type': 'Polygon',
                'coordinates': [[list(coord) for coord in coordinates]]
            },
            'active': True,
            'warning_threshold': 100,
            'alert_threshold': 50
        }
    
    @staticmethod
    def create_test_track(
        track_id: str = "track_001",
        drone_id: str = "drone_001",
        points: list = None
    ) -> dict:
        """Create test track data"""
        if points is None:
            points = [
                (37.7749, -122.4194, 100.0),
                (37.7750, -122.4185, 105.0),
                (37.7751, -122.4176, 110.0),
                (37.7750, -122.4167, 108.0)
            ]
        
        return {
            'track_id': track_id,
            'drone_id': drone_id,
            'drone_type': 'DJI Mavic 3',
            'points': [
                {'latitude': lat, 'longitude': lon, 'altitude': alt, 'timestamp': datetime.now().isoformat()}
                for lat, lon, alt in points
            ],
            'start_time': datetime.now().isoformat(),
            'duration_seconds': 30.0,
            'total_distance_meters': 500.0
        }
    
    @staticmethod
    def create_test_heatmap_data(points: list = None) -> dict:
        """Create test heatmap data"""
        if points is None:
            points = [
                {'lat': 37.7749, 'lon': -122.4194, 'intensity': 0.9},
                {'lat': 37.7750, 'lon': -122.4185, 'intensity': 0.7},
                {'lat': 37.7751, 'lon': -122.4176, 'intensity': 0.5},
                {'lat': 37.7748, 'lon': -122.4167, 'intensity': 0.3}
            ]
        
        return {
            'points': points,
            'bounds': {
                'min_lat': 37.7740,
                'max_lat': 37.7760,
                'min_lon': -122.4210,
                'max_lon': -122.4160
            },
            'total_points': len(points)
        }


# ============================================================================
# Mock Services
# ============================================================================

class MockMapService:
    """Mock map service for testing"""
    
    def __init__(self):
        self.positions = {}
        self.tracks = {}
        self.heatmap_data = None
        self.nearby_drones = []
    
    async def get_drone_positions(self, bounds=None, drone_ids=None):
        """Get drone positions"""
        positions = list(self.positions.values())
        if bounds:
            positions = [
                p for p in positions
                if bounds['min_lat'] <= p['latitude'] <= bounds['max_lat']
                and bounds['min_lon'] <= p['longitude'] <= bounds['max_lon']
            ]
        return positions
    
    async def get_drone_position(self, drone_id):
        """Get single drone position"""
        return self.positions.get(drone_id)
    
    async def update_drone_position(self, position):
        """Update drone position"""
        self.positions[position['drone_id']] = position
        return position
    
    async def get_drone_track(self, drone_id, start_time=None, end_time=None):
        """Get drone track"""
        return self.tracks.get(drone_id, [])
    
    async def get_heatmap_data(self, bounds, time_range):
        """Get heatmap data"""
        return self.heatmap_data or MapTestData.create_test_heatmap_data()
    
    async def get_drones_near_location(self, latitude, longitude, radius_km):
        """Get drones near location"""
        return self.nearby_drones


class MockGeofenceService:
    """Mock geofence service for testing"""
    
    def __init__(self):
        self.zones = {}
        self.violations = []
    
    async def get_zones(self, zone_type=None, active_only=True):
        """Get geofence zones"""
        zones = list(self.zones.values())
        if zone_type:
            zones = [z for z in zones if z['zone_type'] == zone_type]
        if active_only:
            zones = [z for z in zones if z.get('active', True)]
        return zones
    
    async def get_zone(self, zone_id):
        """Get single zone"""
        return self.zones.get(zone_id)
    
    async def create_zone(self, zone_data):
        """Create geofence zone"""
        zone_id = zone_data.get('id', f"zone_{len(self.zones) + 1:03d}")
        self.zones[zone_id] = {**zone_data, 'id': zone_id}
        return zone_id
    
    async def update_zone(self, zone_id, zone_data):
        """Update geofence zone"""
        if zone_id in self.zones:
            self.zones[zone_id].update(zone_data)
            return True
        return False
    
    async def delete_zone(self, zone_id):
        """Delete geofence zone"""
        if zone_id in self.zones:
            del self.zones[zone_id]
            return True
        return False
    
    async def check_violation(self, latitude, longitude, altitude=0):
        """Check geofence violation"""
        for zone in self.zones.values():
            # Simplified boundary check
            if self._point_in_polygon(latitude, longitude, zone.get('coordinates', [])):
                return {
                    'violation': True,
                    'zone_id': zone['id'],
                    'zone_name': zone['name'],
                    'zone_type': zone['zone_type'],
                    'distance': 0
                }
        return {'violation': False}
    
    def _point_in_polygon(self, lat, lon, polygon):
        """Check if point is inside polygon"""
        # Simplified for testing
        return False


# ============================================================================
# Test Client Setup
# ============================================================================

class MapAPITestCase(unittest.IsolatedAsyncioTestCase):
    """Base test case for Map API tests"""
    
    async def asyncSetUp(self):
        """Set up test fixtures"""
        # Create test database
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        
        # Create mock services
        self.map_service = MockMapService()
        self.geofence_service = MockGeofenceService()
        
        # Create FastAPI app with overridden dependencies
        self.app = create_app()
        
        # Override dependencies
        async def get_map_service_override():
            return self.map_service
        
        async def get_geofence_service_override():
            return self.geofence_service
        
        self.app.dependency_overrides[get_map_service] = get_map_service_override
        self.app.dependency_overrides[get_geofence_service] = get_geofence_service_override
        
        self.client = TestClient(self.app)
    
    async def asyncTearDown(self):
        """Clean up after tests"""
        import os
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)


# ============================================================================
# Drone Position API Tests
# ============================================================================

class TestDronePositionsAPI(MapAPITestCase):
    """Tests for drone position endpoints"""
    
    async def test_get_drone_positions_empty(self):
        """Test getting drone positions when none exist"""
        response = self.client.get("/api/map/positions")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('features', data)
        self.assertEqual(len(data['features']), 0)
    
    async def test_get_drone_positions(self):
        """Test getting drone positions"""
        # Add test positions
        test_positions = [
            MapTestData.create_test_drone_position("drone_001", 37.7749, -122.4194, 100.0, "HIGH"),
            MapTestData.create_test_drone_position("drone_002", 37.7750, -122.4185, 120.0, "MEDIUM"),
            MapTestData.create_test_drone_position("drone_003", 37.7751, -122.4176, 80.0, "LOW")
        ]
        
        for pos in test_positions:
            await self.map_service.update_drone_position(pos)
        
        response = self.client.get("/api/map/positions")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['type'], 'FeatureCollection')
        self.assertEqual(len(data['features']), 3)
        
        # Verify GeoJSON structure
        feature = data['features'][0]
        self.assertEqual(feature['type'], 'Feature')
        self.assertEqual(feature['geometry']['type'], 'Point')
        self.assertIn('properties', feature)
    
    async def test_get_drone_positions_with_bounds(self):
        """Test getting drone positions with bounds filtering"""
        # Add positions
        positions = [
            MapTestData.create_test_drone_position("drone_001", 37.7749, -122.4194),
            MapTestData.create_test_drone_position("drone_002", 38.0000, -122.5000)  # Outside bounds
        ]
        
        for pos in positions:
            await self.map_service.update_drone_position(pos)
        
        bounds = "37.77,37.78,-122.43,-122.41"
        response = self.client.get(f"/api/map/positions?bounds={bounds}")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['features']), 1)
    
    async def test_get_drone_position_by_id(self):
        """Test getting specific drone position"""
        test_position = MapTestData.create_test_drone_position("drone_unique", 37.7749, -122.4194)
        await self.map_service.update_drone_position(test_position)
        
        response = self.client.get("/api/map/positions/drone_unique")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['type'], 'Feature')
        self.assertEqual(data['properties']['drone_id'], 'drone_unique')
    
    async def test_get_nonexistent_drone(self):
        """Test getting nonexistent drone position"""
        response = self.client.get("/api/map/positions/nonexistent")
        
        self.assertEqual(response.status_code, 404)
    
    async def test_update_drone_position(self):
        """Test updating drone position"""
        position_data = MapTestData.create_test_drone_position("drone_update", 37.7749, -122.4194)
        
        response = self.client.post(
            "/api/map/positions",
            json=position_data
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        
        # Verify position was stored
        stored = await self.map_service.get_drone_position("drone_update")
        self.assertIsNotNone(stored)
        self.assertEqual(stored['latitude'], 37.7749)


# ============================================================================
# Drone Track API Tests
# ============================================================================

class TestDroneTracksAPI(MapAPITestCase):
    """Tests for drone track endpoints"""
    
    async def test_get_drone_track(self):
        """Test getting drone track"""
        track_data = MapTestData.create_test_track("track_001", "drone_track_001")
        await self.map_service.tracks.__setitem__("drone_track_001", track_data['points'])
        
        response = self.client.get("/api/map/tracks/drone_track_001")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['type'], 'FeatureCollection')
        self.assertGreater(len(data['features']), 0)
    
    async def test_get_drone_track_with_date_range(self):
        """Test getting drone track with date range"""
        track_data = MapTestData.create_test_track("track_002", "drone_track_002")
        await self.map_service.tracks.__setitem__("drone_track_002", track_data['points'])
        
        start_date = (datetime.now() - timedelta(hours=1)).isoformat()
        end_date = datetime.now().isoformat()
        
        response = self.client.get(
            f"/api/map/tracks/drone_track_002",
            params={'start_time': start_date, 'end_time': end_date}
        )
        
        self.assertEqual(response.status_code, 200)
    
    async def test_get_nonexistent_track(self):
        """Test getting nonexistent track"""
        response = self.client.get("/api/map/tracks/nonexistent")
        
        self.assertEqual(response.status_code, 404)


# ============================================================================
# Geofence API Tests
# ============================================================================

class TestGeofenceAPI(MapAPITestCase):
    """Tests for geofence endpoints"""
    
    async def test_get_geofence_zones_empty(self):
        """Test getting geofence zones when none exist"""
        response = self.client.get("/api/map/geofence")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['type'], 'FeatureCollection')
        self.assertEqual(len(data['features']), 0)
    
    async def test_create_geofence_zone(self):
        """Test creating geofence zone"""
        zone_data = MapTestData.create_test_geofence_zone(
            name="Test Restricted Zone",
            zone_type="restricted"
        )
        
        response = self.client.post("/api/map/geofence", json=zone_data)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('zone_id', data)
    
    async def test_get_geofence_zones(self):
        """Test getting geofence zones"""
        # Create test zones
        zones = [
            MapTestData.create_test_geofence_zone("zone_001", "No Fly Zone", "no_fly"),
            MapTestData.create_test_geofence_zone("zone_002", "Warning Zone", "warning"),
            MapTestData.create_test_geofence_zone("zone_003", "Restricted Zone", "restricted")
        ]
        
        for zone in zones:
            await self.geofence_service.create_zone(zone)
        
        response = self.client.get("/api/map/geofence")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['features']), 3)
    
    async def test_get_geofence_zones_by_type(self):
        """Test getting geofence zones filtered by type"""
        zones = [
            MapTestData.create_test_geofence_zone("zone_001", "No Fly Zone", "no_fly"),
            MapTestData.create_test_geofence_zone("zone_002", "Warning Zone", "warning")
        ]
        
        for zone in zones:
            await self.geofence_service.create_zone(zone)
        
        response = self.client.get("/api/map/geofence?zone_type=no_fly")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        for feature in data['features']:
            self.assertEqual(feature['properties']['zone_type'], 'no_fly')
    
    async def test_get_geofence_zone_by_id(self):
        """Test getting specific geofence zone"""
        zone_data = MapTestData.create_test_geofence_zone("zone_specific", "Specific Zone", "restricted")
        await self.geofence_service.create_zone(zone_data)
        
        response = self.client.get("/api/map/geofence/zone_specific")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['properties']['name'], 'Specific Zone')
    
    async def test_update_geofence_zone(self):
        """Test updating geofence zone"""
        zone_data = MapTestData.create_test_geofence_zone("zone_update", "Original Name", "warning")
        await self.geofence_service.create_zone(zone_data)
        
        update_data = {'name': 'Updated Name', 'active': False}
        response = self.client.put("/api/map/geofence/zone_update", json=update_data)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        
        # Verify update
        zone = await self.geofence_service.get_zone("zone_update")
        self.assertEqual(zone['name'], 'Updated Name')
        self.assertFalse(zone['active'])
    
    async def test_delete_geofence_zone(self):
        """Test deleting geofence zone"""
        zone_data = MapTestData.create_test_geofence_zone("zone_delete", "To Delete", "restricted")
        await self.geofence_service.create_zone(zone_data)
        
        response = self.client.delete("/api/map/geofence/zone_delete")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        
        # Verify deletion
        zone = await self.geofence_service.get_zone("zone_delete")
        self.assertIsNone(zone)


# ============================================================================
# Heatmap API Tests
# ============================================================================

class TestHeatmapAPI(MapAPITestCase):
    """Tests for heatmap endpoints"""
    
    async def test_get_heatmap(self):
        """Test getting heatmap data"""
        # Setup test heatmap data
        self.map_service.heatmap_data = MapTestData.create_test_heatmap_data()
        
        response = self.client.get(
            "/api/map/heatmap",
            params={
                'start_time': (datetime.now() - timedelta(hours=1)).isoformat(),
                'end_time': datetime.now().isoformat(),
                'latitude': 37.7749,
                'longitude': -122.4194,
                'radius_km': 5
            }
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('points', data)
        self.assertIn('bounds', data)
        self.assertIn('total_points', data)
    
    async def test_get_heatmap_no_data(self):
        """Test getting heatmap with no data"""
        self.map_service.heatmap_data = None
        
        response = self.client.get("/api/map/heatmap")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['points']), 0)


# ============================================================================
# Proximity API Tests
# ============================================================================

class TestProximityAPI(MapAPITestCase):
    """Tests for proximity endpoints"""
    
    async def test_get_drones_near_location(self):
        """Test getting drones near a location"""
        # Setup nearby drones
        self.map_service.nearby_drones = [
            MapTestData.create_test_drone_position("drone_near_001", 37.7749, -122.4194),
            MapTestData.create_test_drone_position("drone_near_002", 37.7748, -122.4190)
        ]
        
        response = self.client.get(
            "/api/map/proximity",
            params={
                'latitude': 37.7749,
                'longitude': -122.4194,
                'radius_km': 0.5
            }
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('features', data)
        self.assertEqual(len(data['features']), 2)
    
    async def test_check_geofence_violation(self):
        """Test checking geofence violation"""
        # Create a zone
        zone_data = MapTestData.create_test_geofence_zone("zone_check", "Check Zone", "restricted")
        await self.geofence_service.create_zone(zone_data)
        
        response = self.client.get(
            "/api/map/geofence/check",
            params={
                'latitude': 37.7749,
                'longitude': -122.4194,
                'altitude': 100
            }
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('violation', data)


# ============================================================================
# Area Coverage API Tests
# ============================================================================

class TestAreaCoverageAPI(MapAPITestCase):
    """Tests for area coverage endpoints"""
    
    async def test_get_area_coverage(self):
        """Test getting area coverage data"""
        response = self.client.get(
            "/api/map/coverage",
            params={
                'latitude': 37.7749,
                'longitude': -122.4194,
                'radius_km': 5
            }
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('coverage_percentage', data)
        self.assertIn('monitored_area_sqkm', data)
        self.assertIn('recommendation', data)


# ============================================================================
# Validation Tests
# ============================================================================

class TestMapAPIValidation(MapAPITestCase):
    """Tests for request validation"""
    
    async def test_invalid_coordinates(self):
        """Test invalid coordinate values"""
        response = self.client.get(
            "/api/map/proximity",
            params={
                'latitude': 200,  # Invalid latitude
                'longitude': -122.4194,
                'radius_km': 0.5
            }
        )
        
        self.assertEqual(response.status_code, 422)  # Validation error
    
    async def test_invalid_date_range(self):
        """Test invalid date range"""
        response = self.client.get(
            "/api/map/heatmap",
            params={
                'start_time': datetime.now().isoformat(),
                'end_time': (datetime.now() - timedelta(hours=1)).isoformat()  # End before start
            }
        )
        
        self.assertEqual(response.status_code, 422)
    
    async def test_invalid_geofence_geometry(self):
        """Test invalid geofence geometry (less than 3 points)"""
        invalid_zone = {
            'name': 'Invalid Zone',
            'zone_type': 'restricted',
            'geometry': {
                'type': 'Polygon',
                'coordinates': [[[0, 0], [1, 1]]]  # Invalid polygon
            }
        }
        
        response = self.client.post("/api/map/geofence", json=invalid_zone)
        
        self.assertEqual(response.status_code, 422)


# ============================================================================
# WebSocket Tests
# ============================================================================

class TestMapWebSocket(MapAPITestCase):
    """Tests for map WebSocket endpoints"""
    
    async def test_websocket_connection(self):
        """Test WebSocket connection for live positions"""
        # This would require a WebSocket test client
        # For integration tests, we can test the endpoint exists
        response = self.client.get("/api/map/ws")
        # WebSocket upgrade should fail with regular HTTP client
        self.assertNotEqual(response.status_code, 404)


# ============================================================================
# Performance Tests
# ============================================================================

class TestMapAPIPerformance(MapAPITestCase):
    """Performance tests for map API"""
    
    async def test_large_dataset_performance(self):
        """Test performance with large number of positions"""
        import time
        
        # Add many positions
        num_positions = 1000
        for i in range(num_positions):
            position = MapTestData.create_test_drone_position(
                f"drone_{i:04d}",
                37.7749 + i * 0.0001,
                -122.4194 + i * 0.0001
            )
            await self.map_service.update_drone_position(position)
        
        start_time = time.time()
        response = self.client.get("/api/map/positions")
        elapsed = time.time() - start_time
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['features']), num_positions)
        
        # Should handle 1000 positions in under 1 second
        self.assertLess(elapsed, 1.0)
    
    async def test_geojson_size(self):
        """Test GeoJSON response size is reasonable"""
        # Add many positions
        for i in range(100):
            position = MapTestData.create_test_drone_position(f"drone_{i:04d}")
            await self.map_service.update_drone_position(position)
        
        response = self.client.get("/api/map/positions")
        
        # Check content length
        content_length = len(response.content)
        # 100 positions should be under 100KB
        self.assertLess(content_length, 100 * 1024)


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == '__main__':
    # Run with verbose output
    unittest.main(verbosity=2)