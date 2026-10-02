#!/usr/bin/env python3
# drone-detector/infrastructure/external/adsb_client.py
"""
ADS-B Exchange API Client

This module provides integration with ADS-B Exchange (adsbexchange.com) API,
enabling the Drone Detection System to receive real-time aircraft position data
to differentiate between drones and manned aircraft, detect airspace conflicts,
and provide comprehensive airspace awareness.

Features:
- Real-time aircraft position tracking
- Historical flight data retrieval
- Airport and flight information
- JSON and protobuf data formats
- Rate limiting and automatic retries
- Multi-source aggregation
- Geofence-based filtering
- Aircraft type classification
- Real-time WebSocket feed support
- Data caching for performance
"""

import asyncio
import aiohttp
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any, Union, Callable, Set
from collections import deque
import hashlib
import time
from pathlib import Path

# Try to import optional dependencies
try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

# Setup logging
import logging
logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Data Classes
# ============================================================================

class ADSBDataSource(Enum):
    """ADS-B data sources"""
    ADS_B_EXCHANGE = "adsb_exchange"
    OPENSKY = "opensky"
    FLIGHT_RADAR = "flight_radar"
    RADARBOX = "radarbox"
    AIRNAV = "airnav"
    LOCAL_SDR = "local_sdr"


class AircraftCategory(Enum):
    """Aircraft categories"""
    UNKNOWN = 0
    GLIDER = 1
    LIGHT = 2
    SMALL = 3
    LARGE = 4
    HEAVY = 5
    HELICOPTER = 6
    MILITARY = 7
    BALLOON = 8
    DRONE = 9  # For drones that incorrectly broadcast ADS-B


class EmergencyStatus(Enum):
    """Emergency status codes"""
    NONE = 0
    GENERAL = 1
    LIFEGUARD = 2
    MINIMUM_FUEL = 3
    NO_COMMS = 4
    UNLAWFUL_INTERFERENCE = 5
    DOWNED_AIRCRAFT = 6


@dataclass
class ADSBConfig:
    """ADS-B client configuration"""
    # API settings
    base_url: str = "https://adsbexchange.com/api/read"
    api_key: Optional[str] = None
    timeout_seconds: int = 30
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    
    # WebSocket settings
    ws_url: str = "wss://ws.adsbexchange.com/adsb/ws"
    ws_reconnect_seconds: int = 5
    
    # Rate limiting
    requests_per_minute: int = 60
    cache_ttl_seconds: int = 30
    
    # Data filtering
    min_altitude_ft: Optional[int] = None
    max_altitude_ft: Optional[int] = None
    latitude_range: Optional[Tuple[float, float]] = None
    longitude_range: Optional[Tuple[float, float]] = None
    aircraft_types: Optional[List[str]] = None
    
    # Features
    include_airport_info: bool = True
    include_route_info: bool = True
    include_squawk: bool = True
    
    # Caching
    enable_cache: bool = True
    cache_size: int = 10000
    
    # Data source
    data_source: ADSBDataSource = ADSBDataSource.ADS_B_EXCHANGE


@dataclass
class AircraftPosition:
    """Aircraft position data"""
    icao24: str  # ICAO 24-bit address
    callsign: Optional[str] = None
    latitude: float = 0.0
    longitude: float = 0.0
    altitude_ft: Optional[float] = None
    altitude_geom_ft: Optional[float] = None
    ground_speed_kt: Optional[float] = None
    track_deg: Optional[float] = None
    vertical_rate_fpm: Optional[float] = None
    on_ground: bool = False
    category: AircraftCategory = AircraftCategory.UNKNOWN
    emergency: EmergencyStatus = EmergencyStatus.NONE
    squawk: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    source: ADSBDataSource = ADSBDataSource.ADS_B_EXCHANGE
    
    @property
    def position_key(self) -> str:
        """Unique key for position"""
        return f"{self.icao24}:{self.timestamp.timestamp()}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'icao24': self.icao24,
            'callsign': self.callsign,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'altitude_ft': self.altitude_ft,
            'altitude_geom_ft': self.altitude_geom_ft,
            'ground_speed_kt': self.ground_speed_kt,
            'track_deg': self.track_deg,
            'vertical_rate_fpm': self.vertical_rate_fpm,
            'on_ground': self.on_ground,
            'category': self.category.value,
            'emergency': self.emergency.value,
            'squawk': self.squawk,
            'timestamp': self.timestamp.isoformat(),
            'source': self.source.value
        }


@dataclass
class AircraftInfo:
    """Aircraft information (static)"""
    icao24: str
    registration: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    type_code: Optional[str] = None
    serial_number: Optional[str] = None
    operator: Optional[str] = None
    operator_callsign: Optional[str] = None
    year_built: Optional[int] = None
    owner: Optional[str] = None
    engine_type: Optional[str] = None
    wake_turbulence_category: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'icao24': self.icao24,
            'registration': self.registration,
            'manufacturer': self.manufacturer,
            'model': self.model,
            'type_code': self.type_code,
            'serial_number': self.serial_number,
            'operator': self.operator,
            'operator_callsign': self.operator_callsign,
            'year_built': self.year_built,
            'owner': self.owner,
            'engine_type': self.engine_type,
            'wake_turbulence_category': self.wake_turbulence_category
        }


@dataclass
class FlightRoute:
    """Flight route information"""
    icao24: str
    origin: Optional[str] = None
    destination: Optional[str] = None
    origin_name: Optional[str] = None
    destination_name: Optional[str] = None
    route: Optional[str] = None
    departure_time: Optional[datetime] = None
    arrival_time: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'icao24': self.icao24,
            'origin': self.origin,
            'destination': self.destination,
            'origin_name': self.origin_name,
            'destination_name': self.destination_name,
            'route': self.route,
            'departure_time': self.departure_time.isoformat() if self.departure_time else None,
            'arrival_time': self.arrival_time.isoformat() if self.arrival_time else None
        }


@dataclass
class AirportInfo:
    """Airport information"""
    icao: str
    name: str
    latitude: float
    longitude: float
    altitude_ft: float
    iata: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    timezone: Optional[str] = None
    type: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'icao': self.icao,
            'iata': self.iata,
            'name': self.name,
            'city': self.city,
            'country': self.country,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'altitude_ft': self.altitude_ft,
            'type': self.type
        }


# ============================================================================
# ADS-B Exchange API Client
# ============================================================================

class ADSBExchangeClient:
    """
    ADS-B Exchange API Client
    
    Provides methods to fetch real-time and historical aircraft data
    from the ADS-B Exchange network.
    """
    
    def __init__(self, config: Optional[ADSBConfig] = None):
        """
        Initialize ADS-B client
        
        Args:
            config: Client configuration
        """
        self.config = config or ADSBConfig()
        self.session: Optional[aiohttp.ClientSession] = None
        self._last_request_time = 0
        self._request_count = 0
        self._request_window_start = time.time()
        
        # Cache
        self._position_cache: Dict[str, tuple] = {}
        self._aircraft_cache: Dict[str, tuple] = {}
        self._airport_cache: Dict[str, tuple] = {}
        
        # WebSocket connection
        self._ws = None
        self._ws_task: Optional[asyncio.Task] = None
        self._listeners: List[Callable] = []
        
        logger.info(f"ADS-B client initialized with source: {self.config.data_source.value}")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config.timeout_seconds)
            )
        return self.session
    
    async def close(self):
        """Close client session"""
        if self.session and not self.session.closed:
            await self.session.close()
        
        if self._ws:
            await self._ws.close()
        
        logger.info("ADS-B client closed")
    
    async def _rate_limit(self):
        """Apply rate limiting"""
        now = time.time()
        
        # Reset window if needed
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
        """Generate cache key for request"""
        key_data = f"{endpoint}:{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _is_cache_valid(self, cache_entry: tuple, ttl: int) -> bool:
        """Check if cache entry is still valid"""
        if not cache_entry:
            return False
        timestamp, _ = cache_entry
        return (time.time() - timestamp) <= ttl
    
    async def _get_cached_or_fetch(self, endpoint: str, params: Dict[str, Any],
                                    ttl: int = None) -> Optional[Dict[str, Any]]:
        """Get from cache or fetch from API"""
        if not self.config.enable_cache:
            return await self._fetch(endpoint, params)
        
        ttl = ttl or self.config.cache_ttl_seconds
        cache_key = self._get_cache_key(endpoint, params)
        
        # Check cache
        if cache_key in self._position_cache:
            timestamp, data = self._position_cache[cache_key]
            if self._is_cache_valid((timestamp, data), ttl):
                return data
        
        # Fetch from API
        data = await self._fetch(endpoint, params)
        
        if data:
            self._position_cache[cache_key] = (time.time(), data)
            
            # Trim cache if needed
            if len(self._position_cache) > self.config.cache_size:
                # Remove oldest entries
                oldest = min(self._position_cache.items(), key=lambda x: x[1][0])
                del self._position_cache[oldest[0]]
        
        return data
    
    async def _fetch(self, endpoint: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Make API request"""
        await self._rate_limit()
        
        session = await self._get_session()
        
        # Build URL
        if self.config.data_source == ADSBDataSource.ADS_B_EXCHANGE:
            url = f"{self.config.base_url}/{endpoint}"
        elif self.config.data_source == ADSBDataSource.OPENSKY:
            url = f"https://opensky-network.org/api/{endpoint}"
        else:
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
                        logger.error(f"API error {response.status}: {await response.text()}")
                        return None
                        
            except asyncio.TimeoutError:
                logger.warning(f"Request timeout (attempt {attempt + 1})")
                await asyncio.sleep(self.config.retry_delay_seconds)
            except Exception as e:
                logger.error(f"Request error: {e}")
                await asyncio.sleep(self.config.retry_delay_seconds)
        
        return None
    
    # ========================================================================
    # Aircraft Position Methods
    # ========================================================================
    
    async def get_all_aircraft(self, bounds: Optional[Dict[str, float]] = None) -> List[AircraftPosition]:
        """
        Get all aircraft in the specified bounds
        
        Args:
            bounds: Dictionary with 'lat_min', 'lat_max', 'lon_min', 'lon_max'
            
        Returns:
            List of aircraft positions
        """
        params = {}
        
        if bounds:
            params.update({
                'lat_min': bounds.get('lat_min', -90),
                'lat_max': bounds.get('lat_max', 90),
                'lon_min': bounds.get('lon_min', -180),
                'lon_max': bounds.get('lon_max', 180)
            })
        
        # Apply config filters
        if self.config.latitude_range:
            params['lat_min'] = self.config.latitude_range[0]
            params['lat_max'] = self.config.latitude_range[1]
        if self.config.longitude_range:
            params['lon_min'] = self.config.longitude_range[0]
            params['lon_max'] = self.config.longitude_range[1]
        
        data = await self._get_cached_or_fetch("json/", params, ttl=5)  # 5 second TTL for real-time
        if not data:
            return []
        
        aircraft_list = []
        for ac_data in data.get('aircraft', []):
            aircraft = self._parse_aircraft_data(ac_data)
            
            # Apply altitude filters
            if self.config.min_altitude_ft and aircraft.altitude_ft and aircraft.altitude_ft < self.config.min_altitude_ft:
                continue
            if self.config.max_altitude_ft and aircraft.altitude_ft and aircraft.altitude_ft > self.config.max_altitude_ft:
                continue
            
            # Apply aircraft type filters
            if self.config.aircraft_types and aircraft.category not in self.config.aircraft_types:
                continue
            
            aircraft_list.append(aircraft)
        
        return aircraft_list
    
    async def get_aircraft_by_icao(self, icao24: str) -> Optional[AircraftPosition]:
        """
        Get position for specific aircraft by ICAO24 address
        
        Args:
            icao24: ICAO 24-bit address (hex)
            
        Returns:
            Aircraft position or None
        """
        all_aircraft = await self.get_all_aircraft()
        for aircraft in all_aircraft:
            if aircraft.icao24.upper() == icao24.upper():
                return aircraft
        return None
    
    async def get_aircraft_by_callsign(self, callsign: str) -> List[AircraftPosition]:
        """
        Get aircraft by callsign
        
        Args:
            callsign: Flight callsign
            
        Returns:
            List of matching aircraft
        """
        all_aircraft = await self.get_all_aircraft()
        return [a for a in all_aircraft 
                if a.callsign and callsign.upper() in a.callsign.upper()]
    
    def _parse_aircraft_data(self, data: Dict[str, Any]) -> AircraftPosition:
        """Parse aircraft data from API response"""
        return AircraftPosition(
            icao24=data.get('hex', ''),
            callsign=data.get('flight', '').strip(),
            latitude=data.get('lat', 0),
            longitude=data.get('lon', 0),
            altitude_ft=data.get('altitude', None),
            altitude_geom_ft=data.get('alt_geom', None),
            ground_speed_kt=data.get('speed', None),
            track_deg=data.get('track', None),
            vertical_rate_fpm=data.get('vert_rate', None),
            on_ground=data.get('ground', False),
            category=self._parse_category(data.get('category', 0)),
            emergency=EmergencyStatus(data.get('emergency', 0)),
            squawk=data.get('squawk', None),
            timestamp=datetime.now(),
            source=self.config.data_source
        )
    
    def _parse_category(self, category_code: int) -> AircraftCategory:
        """Parse aircraft category code"""
        category_map = {
            0: AircraftCategory.UNKNOWN,
            1: AircraftCategory.GLIDER,
            2: AircraftCategory.LIGHT,
            3: AircraftCategory.SMALL,
            4: AircraftCategory.LARGE,
            5: AircraftCategory.HEAVY,
            6: AircraftCategory.HELICOPTER,
            7: AircraftCategory.MILITARY,
            8: AircraftCategory.BALLOON,
            9: AircraftCategory.DRONE
        }
        return category_map.get(category_code, AircraftCategory.UNKNOWN)
    
    # ========================================================================
    # Flight Information Methods
    # ========================================================================
    
    async def get_flight_info(self, icao24: str) -> Optional[FlightRoute]:
        """
        Get flight route information for an aircraft
        
        Args:
            icao24: ICAO 24-bit address
            
        Returns:
            Flight route information
        """
        params = {'icao': icao24}
        data = await self._get_cached_or_fetch("flightinfo/", params, ttl=300)  # 5 minute TTL
        
        if not data:
            return None
        
        return FlightRoute(
            icao24=icao24,
            origin=data.get('origin', {}).get('icao'),
            destination=data.get('destination', {}).get('icao'),
            origin_name=data.get('origin', {}).get('name'),
            destination_name=data.get('destination', {}).get('name'),
            route=data.get('route'),
            departure_time=datetime.fromisoformat(data['departure_time']) if data.get('departure_time') else None,
            arrival_time=datetime.fromisoformat(data['arrival_time']) if data.get('arrival_time') else None
        )
    
    async def get_aircraft_info(self, icao24: str) -> Optional[AircraftInfo]:
        """
        Get static aircraft information
        
        Args:
            icao24: ICAO 24-bit address
            
        Returns:
            Aircraft information
        """
        # Check cache first
        if icao24 in self._aircraft_cache:
            timestamp, info = self._aircraft_cache[icao24]
            if self._is_cache_valid((timestamp, info), 86400):  # 24 hour TTL
                return info
        
        params = {'icao': icao24}
        data = await self._get_cached_or_fetch("aircraftinfo/", params, ttl=86400)
        
        if not data:
            return None
        
        info = AircraftInfo(
            icao24=icao24,
            registration=data.get('registration'),
            manufacturer=data.get('manufacturer'),
            model=data.get('model'),
            type_code=data.get('type_code'),
            serial_number=data.get('serial_number'),
            operator=data.get('operator'),
            operator_callsign=data.get('operator_callsign'),
            year_built=data.get('year_built'),
            owner=data.get('owner'),
            engine_type=data.get('engine_type'),
            wake_turbulence_category=data.get('wake_turbulence_category')
        )
        
        # Update cache
        self._aircraft_cache[icao24] = (time.time(), info)
        
        return info
    
    # ========================================================================
    # Airport Information Methods
    # ========================================================================
    
    async def get_airport_info(self, icao: str) -> Optional[AirportInfo]:
        """
        Get airport information by ICAO code
        
        Args:
            icao: ICAO airport code (e.g., 'KJFK')
            
        Returns:
            Airport information
        """
        # Check cache
        if icao in self._airport_cache:
            timestamp, airport = self._airport_cache[icao]
            if self._is_cache_valid((timestamp, airport), 86400):
                return airport
        
        params = {'icao': icao}
        data = await self._get_cached_or_fetch("airport/", params, ttl=86400)
        
        if not data:
            return None
        
        airport = AirportInfo(
            icao=icao,
            name=data.get('name', ''),
            latitude=data.get('lat', 0),
            longitude=data.get('lon', 0),
            altitude_ft=data.get('altitude', 0),
            iata=data.get('iata'),
            city=data.get('city'),
            country=data.get('country'),
            timezone=data.get('timezone'),
            type=data.get('type')
        )
        
        self._airport_cache[icao] = (time.time(), airport)
        
        return airport
    
    async def get_airports_in_bounds(self, lat_min: float, lat_max: float,
                                     lon_min: float, lon_max: float) -> List[AirportInfo]:
        """
        Get airports within geographic bounds
        
        Args:
            lat_min, lat_max: Latitude range
            lon_min, lon_max: Longitude range
            
        Returns:
            List of airports
        """
        params = {
            'lat_min': lat_min,
            'lat_max': lat_max,
            'lon_min': lon_min,
            'lon_max': lon_max
        }
        
        data = await self._get_cached_or_fetch("airports/", params, ttl=3600)
        
        if not data:
            return []
        
        airports = []
        for airport_data in data.get('airports', []):
            airport = AirportInfo(
                icao=airport_data.get('icao'),
                name=airport_data.get('name'),
                latitude=airport_data.get('lat', 0),
                longitude=airport_data.get('lon', 0),
                altitude_ft=airport_data.get('altitude', 0),
                iata=airport_data.get('iata')
            )
            airports.append(airport)
        
        return airports
    
    # ========================================================================
    # WebSocket Real-time Feed
    # ========================================================================
    
    async def start_websocket_feed(self, callback: Callable[[AircraftPosition], None],
                                   bounds: Optional[Dict[str, float]] = None):
        """
        Start WebSocket feed for real-time aircraft positions
        
        Args:
            callback: Async callback function for each aircraft update
            bounds: Geographic bounds for filtering
        """
        if not WEBSOCKETS_AVAILABLE:
            logger.error("websockets library not available")
            return
        
        self._listeners.append(callback)
        
        if self._ws_task is None:
            self._ws_task = asyncio.create_task(self._websocket_loop(bounds))
            logger.info("WebSocket feed started")
    
    async def _websocket_loop(self, bounds: Optional[Dict[str, float]] = None):
        """WebSocket connection loop with auto-reconnect"""
        while True:
            try:
                async with websockets.connect(self.config.ws_url) as ws:
                    self._ws = ws
                    logger.info("WebSocket connected to ADS-B feed")
                    
                    async for message in ws:
                        await self._process_ws_message(message, bounds)
                        
            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket connection closed, reconnecting...")
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
            
            await asyncio.sleep(self.config.ws_reconnect_seconds)
    
    async def _process_ws_message(self, message: str, bounds: Optional[Dict[str, float]] = None):
        """Process WebSocket message"""
        try:
            data = json.loads(message)
            aircraft = self._parse_aircraft_data(data)
            
            # Apply bounds filter
            if bounds:
                if (aircraft.latitude < bounds.get('lat_min', -90) or
                    aircraft.latitude > bounds.get('lat_max', 90) or
                    aircraft.longitude < bounds.get('lon_min', -180) or
                    aircraft.longitude > bounds.get('lon_max', 180)):
                    return
            
            # Apply altitude filter
            if self.config.min_altitude_ft and aircraft.altitude_ft and aircraft.altitude_ft < self.config.min_altitude_ft:
                return
            if self.config.max_altitude_ft and aircraft.altitude_ft and aircraft.altitude_ft > self.config.max_altitude_ft:
                return
            
            # Notify listeners
            for callback in self._listeners:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(aircraft)
                    else:
                        callback(aircraft)
                except Exception as e:
                    logger.error(f"Callback error: {e}")
                    
        except json.JSONDecodeError:
            logger.error("Failed to parse WebSocket message")
    
    async def stop_websocket_feed(self):
        """Stop WebSocket feed"""
        self._listeners.clear()
        
        if self._ws_task:
            self._ws_task.cancel()
            self._ws_task = None
        
        if self._ws:
            await self._ws.close()
        
        logger.info("WebSocket feed stopped")
    
    # ========================================================================
    # Historical Data Methods
    # ========================================================================
    
    async def get_historical_track(self, icao24: str, start_time: datetime,
                                   end_time: datetime) -> List[AircraftPosition]:
        """
        Get historical track for an aircraft
        
        Args:
            icao24: ICAO 24-bit address
            start_time: Start of time range
            end_time: End of time range
            
        Returns:
            List of aircraft positions over time
        """
        params = {
            'icao': icao24,
            'start': int(start_time.timestamp()),
            'end': int(end_time.timestamp())
        }
        
        data = await self._get_cached_or_fetch("history/", params, ttl=3600)
        
        if not data:
            return []
        
        positions = []
        for pos_data in data.get('positions', []):
            aircraft = AircraftPosition(
                icao24=icao24,
                latitude=pos_data.get('lat', 0),
                longitude=pos_data.get('lon', 0),
                altitude_ft=pos_data.get('altitude'),
                ground_speed_kt=pos_data.get('speed'),
                track_deg=pos_data.get('track'),
                timestamp=datetime.fromtimestamp(pos_data.get('timestamp', 0)),
                source=self.config.data_source
            )
            positions.append(aircraft)
        
        return positions
    
    # ========================================================================
    # Utility Methods
    # ========================================================================
    
    async def check_aircraft_in_area(self, latitude: float, longitude: float,
                                      radius_km: float = 5.0) -> List[AircraftPosition]:
        """
        Check for aircraft within a radius of a point
        
        Args:
            latitude: Center latitude
            longitude: Center longitude
            radius_km: Search radius in kilometers
            
        Returns:
            List of aircraft in the area
        """
        # Convert radius to degrees (approximate)
        lat_range = radius_km / 111.0  # 1 degree ≈ 111 km
        lon_range = radius_km / (111.0 * abs(latitude))
        
        bounds = {
            'lat_min': latitude - lat_range,
            'lat_max': latitude + lat_range,
            'lon_min': longitude - lon_range,
            'lon_max': longitude + lon_range
        }
        
        all_aircraft = await self.get_all_aircraft(bounds)
        
        # Calculate exact distances
        aircraft_in_area = []
        for aircraft in all_aircraft:
            distance = self._haversine_distance(
                latitude, longitude,
                aircraft.latitude, aircraft.longitude
            )
            if distance <= radius_km:
                aircraft_in_area.append(aircraft)
        
        return aircraft_in_area
    
    def _haversine_distance(self, lat1: float, lon1: float,
                            lat2: float, lon2: float) -> float:
        """Calculate Haversine distance in kilometers"""
        from math import radians, sin, cos, sqrt, asin
        
        R = 6371  # Earth's radius in km
        
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        
        return R * c
    
    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics"""
        return {
            'source': self.config.data_source.value,
            'cache_size': len(self._position_cache),
            'aircraft_cache': len(self._aircraft_cache),
            'airport_cache': len(self._airport_cache),
            'websocket_connected': self._ws is not None and not self._ws.closed,
            'listeners': len(self._listeners),
            'request_count': self._request_count
        }


# ============================================================================
# Factory Functions
# ============================================================================

def create_adsb_client(api_key: Optional[str] = None,
                       data_source: ADSBDataSource = ADSBDataSource.ADS_B_EXCHANGE) -> ADSBExchangeClient:
    """
    Create ADS-B client with configuration
    
    Args:
        api_key: Optional API key for authenticated endpoints
        data_source: Data source to use
        
    Returns:
        Configured ADSBExchangeClient
    """
    config = ADSBConfig(
        api_key=api_key,
        data_source=data_source
    )
    return ADSBExchangeClient(config)


# ============================================================================
# Example Usage
# ============================================================================

async def example_usage():
    """Example usage of ADS-B client"""
    
    print("ADS-B Client Example")
    print("=" * 50)
    
    # Create client
    client = create_adsb_client()
    
    # Get aircraft in area
    print("\n1. Fetching aircraft in San Francisco Bay Area...")
    bounds = {
        'lat_min': 37.5,
        'lat_max': 38.0,
        'lon_min': -122.5,
        'lon_max': -122.0
    }
    
    aircraft_list = await client.get_all_aircraft(bounds)
    print(f"   Found {len(aircraft_list)} aircraft")
    
    # Display first few
    for aircraft in aircraft_list[:5]:
        print(f"   {aircraft.callsign}: {aircraft.icao24} at "
              f"({aircraft.latitude:.4f}, {aircraft.longitude:.4f}) "
              f"alt: {aircraft.altitude_ft:.0f}ft")
    
    # Check specific aircraft
    print("\n2. Checking specific aircraft...")
    aircraft = await client.get_aircraft_by_callsign("UAL")
    if aircraft:
        print(f"   Found United Airlines flight: {aircraft[0].callsign}")
    
    # Get flight info
    print("\n3. Getting flight information...")
    if aircraft:
        flight_info = await client.get_flight_info(aircraft[0].icao24)
        if flight_info:
            print(f"   Route: {flight_info.origin} -> {flight_info.destination}")
    
    # Check area for aircraft
    print("\n4. Checking area near airport...")
    nearby = await client.check_aircraft_in_area(37.6213, -122.3790, radius_km=10)
    print(f"   Found {len(nearby)} aircraft within 10km of SFO")
    
    # Real-time WebSocket example
    print("\n5. WebSocket feed would run here...")
    print("   (WebSocket feed requires websockets library)")
    
    # Statistics
    print("\n6. Client statistics:")
    stats = client.get_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    # Cleanup
    await client.close()
    
    print("\n" + "=" * 50)
    print("ADS-B client example complete")


async def main():
    """Main function"""
    await example_usage()


if __name__ == "__main__":
    asyncio.run(main())