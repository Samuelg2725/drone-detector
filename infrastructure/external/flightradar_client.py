#!/usr/bin/env python3
# drone-detector/infrastructure/external/flightradar_client.py
"""
FlightRadar24 Integration Client

This module provides integration with FlightRadar24 API,
enabling the Drone Detection System to receive real-time commercial flight data
for comprehensive airspace awareness and drone vs. aircraft differentiation.

Features:
- Real-time flight tracking
- Live flight feeds
- Airport departure/arrival boards
- Flight route information
- Aircraft details and photos
- Zone-based flight filtering
- Historical flight data
- Live map overlay data
- Weather integration
- NOTAM (Notice to Airmen) information
"""

import asyncio
import aiohttp
import json
import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any, Union, Callable, Tuple
from collections import deque

# Setup logging
import logging
logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Data Classes
# ============================================================================

class FlightStatus(Enum):
    """Flight status codes"""
    UNKNOWN = "unknown"
    SCHEDULED = "scheduled"
    DEPARTED = "departed"
    AIRBORNE = "airborne"
    LANDED = "landed"
    DIVERTED = "diverted"
    CANCELLED = "cancelled"
    DELAYED = "delayed"


class FlightType(Enum):
    """Flight type classification"""
    PASSENGER = "passenger"
    CARGO = "cargo"
    CHARTER = "charter"
    PRIVATE = "private"
    MILITARY = "military"
    GENERAL_AVIATION = "general_aviation"
    HELICOPTER = "helicopter"


class AircraftAge(Enum):
    """Aircraft age categories"""
    NEW = "new"        # < 5 years
    MODERN = "modern"  # 5-15 years
    MID_AGE = "mid"    # 15-25 years
    OLD = "old"        # > 25 years


@dataclass
class FR24Config:
    """FlightRadar24 client configuration"""
    # API settings
    base_url: str = "https://api.flightradar24.com/common/v1"
    api_key: Optional[str] = None
    timeout_seconds: int = 30
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    
    # Rate limiting
    requests_per_minute: int = 30
    cache_ttl_seconds: int = 30
    
    # Live feed settings
    live_feed_interval_seconds: float = 5.0
    live_zone_size_km: float = 100.0
    
    # Data filtering
    min_altitude_ft: Optional[int] = None
    max_altitude_ft: Optional[int] = None
    include_ground_flights: bool = True
    include_airborne: bool = True
    
    # Features
    include_aircraft_details: bool = True
    include_route_details: bool = True
    include_photos: bool = False
    
    # Caching
    enable_cache: bool = True
    cache_size: int = 5000


@dataclass
class FlightPosition:
    """Real-time flight position"""
    flight_id: str
    callsign: str
    latitude: float
    longitude: float
    altitude_ft: float
    ground_speed_kt: float
    track_deg: float
    vertical_rate_fpm: float
    squawk: Optional[str] = None
    registration: Optional[str] = None
    aircraft_type: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    status: FlightStatus = FlightStatus.UNKNOWN
    timestamp: datetime = field(default_factory=datetime.now)
    on_ground: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'flight_id': self.flight_id,
            'callsign': self.callsign,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'altitude_ft': self.altitude_ft,
            'ground_speed_kt': self.ground_speed_kt,
            'track_deg': self.track_deg,
            'vertical_rate_fpm': self.vertical_rate_fpm,
            'squawk': self.squawk,
            'registration': self.registration,
            'aircraft_type': self.aircraft_type,
            'origin': self.origin,
            'destination': self.destination,
            'status': self.status.value,
            'timestamp': self.timestamp.isoformat(),
            'on_ground': self.on_ground
        }


@dataclass
class FlightDetails:
    """Detailed flight information"""
    flight_id: str
    callsign: str
    airline: Optional[str] = None
    flight_number: Optional[str] = None
    aircraft_type: Optional[str] = None
    registration: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    age_years: Optional[float] = None
    age_category: Optional[AircraftAge] = None
    origin_icao: Optional[str] = None
    origin_name: Optional[str] = None
    origin_city: Optional[str] = None
    origin_country: Optional[str] = None
    origin_time: Optional[datetime] = None
    destination_icao: Optional[str] = None
    destination_name: Optional[str] = None
    destination_city: Optional[str] = None
    destination_country: Optional[str] = None
    destination_time: Optional[datetime] = None
    scheduled_departure: Optional[datetime] = None
    scheduled_arrival: Optional[datetime] = None
    actual_departure: Optional[datetime] = None
    actual_arrival: Optional[datetime] = None
    status: FlightStatus = FlightStatus.UNKNOWN
    delay_minutes: int = 0
    distance_km: float = 0.0
    duration_minutes: int = 0
    photo_url: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'flight_id': self.flight_id,
            'callsign': self.callsign,
            'airline': self.airline,
            'flight_number': self.flight_number,
            'aircraft_type': self.aircraft_type,
            'registration': self.registration,
            'manufacturer': self.manufacturer,
            'model': self.model,
            'age_years': self.age_years,
            'age_category': self.age_category.value if self.age_category else None,
            'origin_icao': self.origin_icao,
            'origin_name': self.origin_name,
            'origin_city': self.origin_city,
            'origin_country': self.origin_country,
            'origin_time': self.origin_time.isoformat() if self.origin_time else None,
            'destination_icao': self.destination_icao,
            'destination_name': self.destination_name,
            'destination_city': self.destination_city,
            'destination_country': self.destination_country,
            'destination_time': self.destination_time.isoformat() if self.destination_time else None,
            'scheduled_departure': self.scheduled_departure.isoformat() if self.scheduled_departure else None,
            'scheduled_arrival': self.scheduled_arrival.isoformat() if self.scheduled_arrival else None,
            'actual_departure': self.actual_departure.isoformat() if self.actual_departure else None,
            'actual_arrival': self.actual_arrival.isoformat() if self.actual_arrival else None,
            'status': self.status.value,
            'delay_minutes': self.delay_minutes,
            'distance_km': self.distance_km,
            'duration_minutes': self.duration_minutes,
            'photo_url': self.photo_url
        }


@dataclass
class AirportBoard:
    """Airport arrival/departure board"""
    airport_icao: str
    airport_name: str
    board_type: str  # 'arrivals' or 'departures'
    flights: List[FlightDetails]
    last_update: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'airport_icao': self.airport_icao,
            'airport_name': self.airport_name,
            'board_type': self.board_type,
            'flights': [f.to_dict() for f in self.flights],
            'last_update': self.last_update.isoformat()
        }


# ============================================================================
# FlightRadar24 API Client
# ============================================================================

class FlightRadar24Client:
    """
    FlightRadar24 API Client
    
    Provides methods to fetch real-time commercial flight data,
    airport information, and flight tracking.
    """
    
    def __init__(self, config: Optional[FR24Config] = None):
        """
        Initialize FlightRadar24 client
        
        Args:
            config: Client configuration
        """
        self.config = config or FR24Config()
        self.session: Optional[aiohttp.ClientSession] = None
        self._last_request_time = 0
        self._request_count = 0
        self._request_window_start = time.time()
        
        # Cache
        self._flight_cache: Dict[str, tuple] = {}
        self._airport_cache: Dict[str, tuple] = {}
        self._aircraft_cache: Dict[str, tuple] = {}
        
        # Live feed
        self._live_feed_task: Optional[asyncio.Task] = None
        self._live_listeners: List[Callable] = []
        
        logger.info("FlightRadar24 client initialized")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config.timeout_seconds),
                headers={
                    'User-Agent': 'DroneDetectionSystem/2.0',
                    'Accept': 'application/json'
                }
            )
        return self.session
    
    async def close(self):
        """Close client session"""
        if self.session and not self.session.closed:
            await self.session.close()
        
        if self._live_feed_task:
            self._live_feed_task.cancel()
        
        logger.info("FlightRadar24 client closed")
    
    async def _rate_limit(self):
        """Apply rate limiting"""
        now = time.time()
        
        if now - self._request_window_start >= 60:
            self._request_window_start = now
            self._request_count = 0
        
        if self._request_count >= self.config.requests_per_minute:
            wait_time = 60 - (now - self._request_window_start)
            if wait_time > 0:
                logger.debug(f"Rate limit reached, waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
                self._request_window_start = time.time()
                self._request_count = 0
        
        self._request_count += 1
        self._last_request_time = now
    
    def _get_cache_key(self, endpoint: str, params: Dict[str, Any]) -> str:
        """Generate cache key"""
        key_data = f"{endpoint}:{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    async def _request(self, endpoint: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Make API request"""
        await self._rate_limit()
        
        session = await self._get_session()
        url = f"{self.config.base_url}/{endpoint}"
        
        # Add API key if available
        if self.config.api_key:
            params['api_key'] = self.config.api_key
        
        for attempt in range(self.config.max_retries):
            try:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data
                    elif response.status == 429:
                        logger.warning("Rate limited, waiting...")
                        await asyncio.sleep(2 ** attempt)
                    else:
                        logger.error(f"API error {response.status}")
                        return None
                        
            except asyncio.TimeoutError:
                logger.warning(f"Request timeout (attempt {attempt + 1})")
                await asyncio.sleep(self.config.retry_delay_seconds)
            except Exception as e:
                logger.error(f"Request error: {e}")
                await asyncio.sleep(self.config.retry_delay_seconds)
        
        return None
    
    async def _get_cached_or_fetch(self, endpoint: str, params: Dict[str, Any],
                                    ttl: int = None) -> Optional[Dict[str, Any]]:
        """Get from cache or fetch"""
        if not self.config.enable_cache:
            return await self._request(endpoint, params)
        
        ttl = ttl or self.config.cache_ttl_seconds
        cache_key = self._get_cache_key(endpoint, params)
        
        if cache_key in self._flight_cache:
            timestamp, data = self._flight_cache[cache_key]
            if (time.time() - timestamp) <= ttl:
                return data
        
        data = await self._request(endpoint, params)
        
        if data:
            self._flight_cache[cache_key] = (time.time(), data)
            
            if len(self._flight_cache) > self.config.cache_size:
                oldest = min(self._flight_cache.items(), key=lambda x: x[1][0])
                del self._flight_cache[oldest[0]]
        
        return data
    
    # ========================================================================
    # Live Flight Feed
    # ========================================================================
    
    async def start_live_feed(self, bounds: Optional[Dict[str, float]] = None,
                              callback: Callable[[List[FlightPosition]], None] = None):
        """
        Start live flight feed
        
        Args:
            bounds: Geographic bounds dictionary with 'lat_min', 'lat_max', 'lon_min', 'lon_max'
            callback: Async callback for flight updates
        """
        self._live_listeners.append(callback) if callback else None
        
        if self._live_feed_task is None:
            self._live_feed_task = asyncio.create_task(
                self._live_feed_loop(bounds)
            )
            logger.info("Live flight feed started")
    
    async def _live_feed_loop(self, bounds: Optional[Dict[str, float]] = None):
        """Background task for live flight updates"""
        while True:
            try:
                flights = await self.get_live_flights(bounds)
                
                for callback in self._live_listeners:
                    if callback:
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(flights)
                            else:
                                callback(flights)
                        except Exception as e:
                            logger.error(f"Live feed callback error: {e}")
                
                await asyncio.sleep(self.config.live_feed_interval_seconds)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Live feed error: {e}")
                await asyncio.sleep(5)
    
    async def stop_live_feed(self):
        """Stop live flight feed"""
        if self._live_feed_task:
            self._live_feed_task.cancel()
            self._live_feed_task = None
        
        self._live_listeners.clear()
        logger.info("Live flight feed stopped")
    
    # ========================================================================
    # Real-time Flight Data
    # ========================================================================
    
    async def get_live_flights(self, bounds: Optional[Dict[str, float]] = None) -> List[FlightPosition]:
        """
        Get live flights in specified bounds
        
        Args:
            bounds: Geographic bounds (optional)
            
        Returns:
            List of flight positions
        """
        params = {}
        
        if bounds:
            params.update({
                'lat_min': bounds.get('lat_min', -90),
                'lat_max': bounds.get('lat_max', 90),
                'lon_min': bounds.get('lon_min', -180),
                'lon_max': bounds.get('lon_max', 180)
            })
        
        data = await self._get_cached_or_fetch("live-flights.json", params, ttl=5)
        
        if not data:
            return []
        
        flights = []
        for flight_data in data.get('result', {}).get('response', {}).get('data', []):
            flight = self._parse_flight_position(flight_data)
            
            # Apply filters
            if self.config.min_altitude_ft and flight.altitude_ft < self.config.min_altitude_ft:
                continue
            if self.config.max_altitude_ft and flight.altitude_ft > self.config.max_altitude_ft:
                continue
            if not self.config.include_ground_flights and flight.on_ground:
                continue
            if not self.config.include_airborne and not flight.on_ground:
                continue
            
            flights.append(flight)
        
        return flights
    
    def _parse_flight_position(self, data: Dict[str, Any]) -> FlightPosition:
        """Parse flight position from API response"""
        return FlightPosition(
            flight_id=data.get('id', ''),
            callsign=data.get('identification', {}).get('callsign', ''),
            latitude=float(data.get('latitude', 0)),
            longitude=float(data.get('longitude', 0)),
            altitude_ft=float(data.get('altitude', {}).get('feet', 0)),
            ground_speed_kt=float(data.get('speed', {}).get('speed', 0)),
            track_deg=float(data.get('heading', 0)),
            vertical_rate_fpm=float(data.get('vertical_rate', 0)),
            squawk=data.get('squawk'),
            registration=data.get('registration', {}).get('id'),
            aircraft_type=data.get('aircraft', {}).get('model'),
            origin=data.get('airport', {}).get('origin', {}).get('code', {}).get('icao'),
            destination=data.get('airport', {}).get('destination', {}).get('code', {}).get('icao'),
            status=FlightStatus(data.get('status', 'unknown')),
            on_ground=data.get('on_ground', False)
        )
    
    async def get_flight_by_id(self, flight_id: str) -> Optional[FlightPosition]:
        """
        Get flight by ID
        
        Args:
            flight_id: FlightRadar24 flight ID
            
        Returns:
            Flight position or None
        """
        all_flights = await self.get_live_flights()
        for flight in all_flights:
            if flight.flight_id == flight_id:
                return flight
        return None
    
    async def get_flight_by_callsign(self, callsign: str) -> Optional[FlightPosition]:
        """
        Get flight by callsign
        
        Args:
            callsign: Flight callsign (e.g., 'UAL123')
            
        Returns:
            Flight position or None
        """
        all_flights = await self.get_live_flights()
        for flight in all_flights:
            if flight.callsign.upper() == callsign.upper():
                return flight
        return None
    
    # ========================================================================
    # Flight Details
    # ========================================================================
    
    async def get_flight_details(self, flight_id: str) -> Optional[FlightDetails]:
        """
        Get detailed flight information
        
        Args:
            flight_id: FlightRadar24 flight ID
            
        Returns:
            Flight details or None
        """
        params = {'flight_id': flight_id}
        
        if self.config.include_aircraft_details:
            params['aircraft_details'] = 'true'
        if self.config.include_route_details:
            params['route_details'] = 'true'
        
        data = await self._get_cached_or_fetch("flight-details.json", params, ttl=300)
        
        if not data:
            return None
        
        flight_data = data.get('result', {}).get('response', {}).get('data', {})
        
        return FlightDetails(
            flight_id=flight_id,
            callsign=flight_data.get('identification', {}).get('callsign', ''),
            airline=flight_data.get('airline', {}).get('name'),
            flight_number=flight_data.get('identification', {}).get('number', {}).get('default'),
            aircraft_type=flight_data.get('aircraft', {}).get('model', {}).get('code'),
            registration=flight_data.get('aircraft', {}).get('registration'),
            manufacturer=flight_data.get('aircraft', {}).get('model', {}).get('manufacturer'),
            model=flight_data.get('aircraft', {}).get('model', {}).get('text'),
            age_years=flight_data.get('aircraft', {}).get('age'),
            origin_icao=flight_data.get('airport', {}).get('origin', {}).get('code', {}).get('icao'),
            origin_name=flight_data.get('airport', {}).get('origin', {}).get('name'),
            origin_city=flight_data.get('airport', {}).get('origin', {}).get('city'),
            origin_country=flight_data.get('airport', {}).get('origin', {}).get('country'),
            destination_icao=flight_data.get('airport', {}).get('destination', {}).get('code', {}).get('icao'),
            destination_name=flight_data.get('airport', {}).get('destination', {}).get('name'),
            destination_city=flight_data.get('airport', {}).get('destination', {}).get('city'),
            destination_country=flight_data.get('airport', {}).get('destination', {}).get('country'),
            status=FlightStatus(flight_data.get('status', 'unknown')),
            distance_km=flight_data.get('route', {}).get('distance', 0),
            duration_minutes=flight_data.get('route', {}).get('duration', 0),
            photo_url=flight_data.get('aircraft', {}).get('images', {}).get('thumbnails', [{}])[0].get('src') if self.config.include_photos else None
        )
    
    # ========================================================================
    # Airport Information
    # ========================================================================
    
    async def get_airport_board(self, icao: str, board_type: str = 'departures') -> Optional[AirportBoard]:
        """
        Get airport arrival/departure board
        
        Args:
            icao: Airport ICAO code (e.g., 'KJFK')
            board_type: 'departures' or 'arrivals'
            
        Returns:
            Airport board with flight list
        """
        params = {
            'airport_code': icao,
            'type': board_type
        }
        
        data = await self._get_cached_or_fetch("airport-board.json", params, ttl=120)
        
        if not data:
            return None
        
        flights = []
        for flight_data in data.get('result', {}).get('response', {}).get('data', []):
            flight = FlightDetails(
                flight_id=flight_data.get('flight_id', ''),
                callsign=flight_data.get('callsign', ''),
                airline=flight_data.get('airline', {}).get('name'),
                flight_number=flight_data.get('flight_number'),
                aircraft_type=flight_data.get('aircraft_type'),
                origin_icao=flight_data.get('origin', {}).get('code'),
                destination_icao=flight_data.get('destination', {}).get('code'),
                scheduled_departure=datetime.fromisoformat(flight_data['scheduled_departure']) if flight_data.get('scheduled_departure') else None,
                scheduled_arrival=datetime.fromisoformat(flight_data['scheduled_arrival']) if flight_data.get('scheduled_arrival') else None,
                status=FlightStatus(flight_data.get('status', 'unknown')),
                delay_minutes=flight_data.get('delay', 0)
            )
            flights.append(flight)
        
        return AirportBoard(
            airport_icao=icao,
            airport_name=data.get('result', {}).get('response', {}).get('airport', {}).get('name', ''),
            board_type=board_type,
            flights=flights
        )
    
    async def get_airport_info(self, icao: str) -> Optional[Dict[str, Any]]:
        """
        Get airport information
        
        Args:
            icao: Airport ICAO code
            
        Returns:
            Airport information dictionary
        """
        params = {'airport_code': icao}
        
        data = await self._get_cached_or_fetch("airport-info.json", params, ttl=3600)
        
        if not data:
            return None
        
        return {
            'icao': icao,
            'name': data.get('result', {}).get('response', {}).get('airport', {}).get('name'),
            'city': data.get('result', {}).get('response', {}).get('airport', {}).get('city'),
            'country': data.get('result', {}).get('response', {}).get('airport', {}).get('country'),
            'timezone': data.get('result', {}).get('response', {}).get('airport', {}).get('timezone')
        }
    
    # ========================================================================
    # Aircraft Information
    # ========================================================================
    
    async def get_aircraft_info(self, registration: str) -> Optional[Dict[str, Any]]:
        """
        Get aircraft information by registration
        
        Args:
            registration: Aircraft registration (e.g., 'N12345')
            
        Returns:
            Aircraft information dictionary
        """
        # Check cache
        if registration in self._aircraft_cache:
            timestamp, info = self._aircraft_cache[registration]
            if (time.time() - timestamp) <= 86400:  # 24 hour TTL
                return info
        
        params = {'registration': registration}
        
        data = await self._get_cached_or_fetch("aircraft-info.json", params, ttl=86400)
        
        if not data:
            return None
        
        info = {
            'registration': registration,
            'manufacturer': data.get('result', {}).get('response', {}).get('aircraft', {}).get('manufacturer'),
            'model': data.get('result', {}).get('response', {}).get('aircraft', {}).get('model'),
            'serial_number': data.get('result', {}).get('response', {}).get('aircraft', {}).get('serial'),
            'age_years': data.get('result', {}).get('response', {}).get('aircraft', {}).get('age'),
            'owner': data.get('result', {}).get('response', {}).get('aircraft', {}).get('owner'),
            'operator': data.get('result', {}).get('response', {}).get('aircraft', {}).get('operator')
        }
        
        self._aircraft_cache[registration] = (time.time(), info)
        
        return info
    
    # ========================================================================
    # Zone-based Queries
    # ========================================================================
    
    async def get_flights_in_zone(self, center_lat: float, center_lon: float,
                                   radius_km: float = 10.0) -> List[FlightPosition]:
        """
        Get flights within a radius of a point
        
        Args:
            center_lat: Center latitude
            center_lon: Center longitude
            radius_km: Search radius in kilometers
            
        Returns:
            List of flights in the zone
        """
        # Convert radius to degrees (approximate)
        lat_range = radius_km / 111.0
        lon_range = radius_km / (111.0 * abs(center_lat))
        
        bounds = {
            'lat_min': center_lat - lat_range,
            'lat_max': center_lat + lat_range,
            'lon_min': center_lon - lon_range,
            'lon_max': center_lon + lon_range
        }
        
        all_flights = await self.get_live_flights(bounds)
        
        # Filter by exact distance
        flights_in_zone = []
        for flight in all_flights:
            distance = self._haversine_distance(
                center_lat, center_lon,
                flight.latitude, flight.longitude
            )
            if distance <= radius_km:
                flights_in_zone.append(flight)
        
        return flights_in_zone
    
    def _haversine_distance(self, lat1: float, lon1: float,
                            lat2: float, lon2: float) -> float:
        """Calculate Haversine distance in kilometers"""
        from math import radians, sin, cos, sqrt, asin
        
        R = 6371  # Earth's radius
        
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        
        return R * c
    
    # ========================================================================
    # Alert Methods for Drone Detection
    # ========================================================================
    
    async def check_aircraft_near_drone(self, drone_lat: float, drone_lon: float,
                                         drone_alt_ft: float, radius_km: float = 5.0,
                                         altitude_diff_ft: float = 500) -> List[FlightPosition]:
        """
        Check for aircraft near a drone position
        
        Args:
            drone_lat: Drone latitude
            drone_lon: Drone longitude
            drone_alt_ft: Drone altitude in feet
            radius_km: Search radius in kilometers
            altitude_diff_ft: Maximum altitude difference to consider
            
        Returns:
            List of nearby aircraft that might conflict with drone
        """
        nearby_flights = await self.get_flights_in_zone(drone_lat, drone_lon, radius_km)
        
        # Filter by altitude proximity
        conflicting = []
        for flight in nearby_flights:
            if not flight.on_ground:  # Only airborne aircraft
                altitude_diff = abs(flight.altitude_ft - drone_alt_ft)
                if altitude_diff <= altitude_diff_ft:
                    conflicting.append(flight)
        
        return conflicting
    
    # ========================================================================
    # Utility Methods
    # ========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics"""
        return {
            'cache_size': len(self._flight_cache),
            'aircraft_cache': len(self._aircraft_cache),
            'airport_cache': len(self._airport_cache),
            'live_feed_running': self._live_feed_task is not None,
            'listeners': len(self._live_listeners),
            'request_count': self._request_count,
            'rate_limit_remaining': self.config.requests_per_minute - self._request_count
        }
    
    async def clear_cache(self):
        """Clear all caches"""
        self._flight_cache.clear()
        self._aircraft_cache.clear()
        self._airport_cache.clear()
        logger.info("Cache cleared")


# ============================================================================
# Factory Functions
# ============================================================================

def create_flightradar_client(api_key: Optional[str] = None,
                              max_flights: int = 100) -> FlightRadar24Client:
    """
    Create FlightRadar24 client
    
    Args:
        api_key: Optional API key
        max_flights: Maximum number of flights to track
        
    Returns:
        Configured FlightRadar24Client
    """
    config = FR24Config(
        api_key=api_key,
        cache_size=max_flights * 10
    )
    return FlightRadar24Client(config)


# ============================================================================
# Example Usage
# ============================================================================

async def example_usage():
    """Example usage of FlightRadar24 client"""
    
    print("FlightRadar24 Client Example")
    print("=" * 50)
    
    # Create client
    client = create_flightradar_client()
    
    # Get live flights
    print("\n1. Fetching live flights near San Francisco...")
    bounds = {
        'lat_min': 37.5,
        'lat_max': 38.0,
        'lon_min': -122.5,
        'lon_max': -122.0
    }
    
    flights = await client.get_live_flights(bounds)
    print(f"   Found {len(flights)} flights")
    
    # Display first few
    for flight in flights[:5]:
        print(f"   {flight.callsign}: {flight.altitude_ft:.0f}ft, "
              f"speed: {flight.ground_speed_kt:.0f}kt, "
              f"{flight.origin} -> {flight.destination}")
    
    # Get flight details
    if flights:
        print(f"\n2. Getting details for {flights[0].callsign}...")
        details = await client.get_flight_details(flights[0].flight_id)
        if details:
            print(f"   Airline: {details.airline}")
            print(f"   Aircraft: {details.manufacturer} {details.model}")
            print(f"   Age: {details.age_years:.1f} years")
    
    # Check flights near a drone
    print("\n3. Checking for aircraft near simulated drone...")
    drone_lat = 37.7749
    drone_lon = -122.4194
    drone_alt = 400  # 400 feet AGL
    
    conflicts = await client.check_aircraft_near_drone(
        drone_lat, drone_lon, drone_alt, radius_km=3.0, altitude_diff_ft=500
    )
    
    if conflicts:
        print(f"   WARNING: {len(conflicts)} aircraft near drone!")
        for conflict in conflicts:
            print(f"   - {conflict.callsign} at {conflict.altitude_ft:.0f}ft, "
                  f"distance: {self._haversine_distance(drone_lat, drone_lon, conflict.latitude, conflict.longitude):.1f}km")
    else:
        print("   No aircraft conflicts detected")
    
    # Get airport board
    print("\n4. Getting SFO departures...")
    board = await client.get_airport_board('KSFO', 'departures')
    if board:
        print(f"   {board.airport_name}: {len(board.flights)} departing flights")
        for flight in board.flights[:3]:
            print(f"   - {flight.callsign} to {flight.destination_icao}, "
                  f"status: {flight.status.value}")
    
    # Statistics
    print("\n5. Client statistics:")
    stats = client.get_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    # Cleanup
    await client.close()
    
    print("\n" + "=" * 50)
    print("FlightRadar24 client example complete")


async def main():
    """Main function"""
    await example_usage()


if __name__ == "__main__":
    asyncio.run(main())