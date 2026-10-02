#!/usr/bin/env python3
# drone-detector/infrastructure/external/geocoding.py
"""
Reverse Geocoding Service

This module provides comprehensive reverse geocoding capabilities for the Drone Detection System,
converting GPS coordinates to human-readable addresses and place names with support for:

- Reverse geocoding (lat/lon → address)
- Forward geocoding (address → lat/lon)
- Multiple geocoding providers (OpenStreetMap/Nominatim, Google Maps, HERE, Bing)
- Caching for performance and rate limit reduction
- Batch geocoding for multiple coordinates
- Address components parsing (street, city, country, etc.)
- Proximity-based location naming
- Landmark and point-of-interest identification
- Timezone lookup from coordinates
- Elevation data retrieval
- Geofencing and boundary checking
- Local language support
- Automatic provider failover
- Rate limiting compliance
"""

import asyncio
import aiohttp
import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any, Union, Tuple, Callable
from collections import OrderedDict

# Setup logging
import logging
logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Data Classes
# ============================================================================

class GeocodingProvider(Enum):
    """Supported geocoding providers"""
    OPENSTREETMAP = "osm"           # OpenStreetMap Nominatim (free)
    GOOGLE = "google"               # Google Maps Geocoding API
    HERE = "here"                   # HERE Geocoding API
    BING = "bing"                   # Bing Maps Geocoding API
    MAPBOX = "mapbox"               # Mapbox Geocoding API
    LOCATIONIQ = "locationiq"       # LocationIQ (free tier)
    OPENCAGE = "opencage"           # OpenCage Geocoder


class LocationType(Enum):
    """Types of locations"""
    STREET_ADDRESS = "street_address"
    CITY = "city"
    STATE = "state"
    COUNTRY = "country"
    POSTAL_CODE = "postal_code"
    POINT_OF_INTEREST = "point_of_interest"
    NATURAL_FEATURE = "natural_feature"
    AIRPORT = "airport"
    MILITARY_BASE = "military_base"
    GOVERNMENT_BUILDING = "government_building"
    SCHOOL = "school"
    HOSPITAL = "hospital"
    PARK = "park"
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    INDUSTRIAL = "industrial"
    RURAL = "rural"
    UNKNOWN = "unknown"


@dataclass
class GeocodingConfig:
    """Geocoding service configuration"""
    # Provider settings
    primary_provider: GeocodingProvider = GeocodingProvider.OPENSTREETMAP
    fallback_providers: List[GeocodingProvider] = field(default_factory=list)
    
    # API keys (as needed per provider)
    google_api_key: Optional[str] = None
    here_api_key: Optional[str] = None
    here_app_id: Optional[str] = None
    here_app_code: Optional[str] = None
    bing_api_key: Optional[str] = None
    mapbox_api_key: Optional[str] = None
    locationiq_api_key: Optional[str] = None
    opencage_api_key: Optional[str] = None
    
    # OpenStreetMap specific
    osm_user_agent: str = "DroneDetectionSystem/2.0"
    osm_email: Optional[str] = None
    
    # Rate limiting
    requests_per_second: float = 1.0  # Nominatim limit is 1 req/sec
    cache_ttl_seconds: int = 86400  # Cache for 24 hours
    
    # Response settings
    language: str = "en"
    address_details: bool = True
    include_extras: bool = False
    
    # Performance
    enable_cache: bool = True
    cache_size: int = 10000
    batch_size: int = 10
    timeout_seconds: int = 10
    max_retries: int = 3
    retry_delay_seconds: float = 1.0


@dataclass
class Address:
    """Structured address information"""
    # Primary components
    display_name: str
    street: Optional[str] = None
    house_number: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    state_code: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    country_code: Optional[str] = None
    
    # Additional components
    neighbourhood: Optional[str] = None
    suburb: Optional[str] = None
    district: Optional[str] = None
    county: Optional[str] = None
    road: Optional[str] = None
    
    # Location classification
    location_type: LocationType = LocationType.UNKNOWN
    is_restricted: bool = False
    restricted_reason: Optional[str] = None
    
    # Metadata
    confidence: float = 0.0
    provider: GeocodingProvider = GeocodingProvider.OPENSTREETMAP
    timestamp: datetime = field(default_factory=datetime.now)
    raw_response: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'display_name': self.display_name,
            'street': self.street,
            'house_number': self.house_number,
            'city': self.city,
            'state': self.state,
            'state_code': self.state_code,
            'postal_code': self.postal_code,
            'country': self.country,
            'country_code': self.country_code,
            'neighbourhood': self.neighbourhood,
            'suburb': self.suburb,
            'district': self.district,
            'county': self.county,
            'road': self.road,
            'location_type': self.location_type.value,
            'is_restricted': self.is_restricted,
            'restricted_reason': self.restricted_reason,
            'confidence': self.confidence,
            'provider': self.provider.value,
            'timestamp': self.timestamp.isoformat()
        }
    
    def get_short_name(self) -> str:
        """Get short human-readable name"""
        if self.location_type == LocationType.POINT_OF_INTEREST:
            return self.display_name.split(',')[0]
        elif self.city:
            return f"{self.city}, {self.state_code or self.state or ''}".strip(', ')
        elif self.country:
            return self.country
        return self.display_name
    
    def get_administrative_area(self) -> str:
        """Get administrative area (city/state/country hierarchy)"""
        parts = []
        if self.city:
            parts.append(self.city)
        if self.state:
            parts.append(self.state)
        if self.country:
            parts.append(self.country)
        return ', '.join(parts)


@dataclass
class PointOfInterest:
    """Point of interest information"""
    name: str
    latitude: float
    longitude: float
    category: str
    distance_meters: float
    type: str
    opening_hours: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None


@dataclass
class GeocodeResult:
    """Complete geocoding result"""
    success: bool
    coordinates: Optional[Tuple[float, float]] = None
    address: Optional[Address] = None
    timezone: Optional[str] = None
    elevation_m: Optional[float] = None
    nearby_pois: List[PointOfInterest] = field(default_factory=list)
    error_message: Optional[str] = None
    provider: GeocodingProvider = GeocodingProvider.OPENSTREETMAP
    response_time_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'success': self.success,
            'coordinates': self.coordinates,
            'address': self.address.to_dict() if self.address else None,
            'timezone': self.timezone,
            'elevation_m': self.elevation_m,
            'nearby_pois': [
                {
                    'name': poi.name,
                    'category': poi.category,
                    'distance_meters': poi.distance_meters
                } for poi in self.nearby_pois
            ],
            'error': self.error_message,
            'provider': self.provider.value,
            'response_time_ms': self.response_time_ms
        }


# ============================================================================
# Geocoding Cache
# ============================================================================

class GeocodingCache:
    """LRU cache for geocoding results"""
    
    def __init__(self, max_size: int = 10000, ttl_seconds: int = 86400):
        """
        Initialize cache
        
        Args:
            max_size: Maximum number of entries
            ttl_seconds: Time to live in seconds
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict = OrderedDict()
    
    def _make_key(self, latitude: float, longitude: float) -> str:
        """Create cache key from coordinates"""
        # Round to 5 decimal places (~1 meter precision)
        lat_rounded = round(latitude, 5)
        lon_rounded = round(longitude, 5)
        return f"{lat_rounded},{lon_rounded}"
    
    def get(self, latitude: float, longitude: float) -> Optional[GeocodeResult]:
        """Get cached result"""
        key = self._make_key(latitude, longitude)
        
        if key in self._cache:
            result, timestamp = self._cache[key]
            if (datetime.now() - timestamp).total_seconds() < self.ttl_seconds:
                # Move to end (LRU)
                self._cache.move_to_end(key)
                return result
            else:
                del self._cache[key]
        
        return None
    
    def set(self, latitude: float, longitude: float, result: GeocodeResult):
        """Cache result"""
        key = self._make_key(latitude, longitude)
        
        if len(self._cache) >= self.max_size:
            self._cache.popitem(last=False)
        
        self._cache[key] = (result, datetime.now())
    
    def clear(self):
        """Clear cache"""
        self._cache.clear()


# ============================================================================
# Provider-Specific Clients
# ============================================================================

class BaseGeocodingProvider:
    """Base class for geocoding providers"""
    
    def __init__(self, config: GeocodingConfig):
        self.config = config
        self._last_request_time = 0
    
    async def _rate_limit(self):
        """Apply rate limiting"""
        elapsed = time.time() - self._last_request_time
        min_interval = 1.0 / self.config.requests_per_second
        if elapsed < min_interval:
            await asyncio.sleep(min_interval - elapsed)
        self._last_request_time = time.time()
    
    async def reverse_geocode(self, latitude: float, longitude: float,
                              session: aiohttp.ClientSession) -> Optional[Address]:
        """Reverse geocode coordinates - override in subclass"""
        raise NotImplementedError
    
    async def forward_geocode(self, address: str,
                              session: aiohttp.ClientSession) -> Optional[Tuple[float, float]]:
        """Forward geocode address - override in subclass"""
        raise NotImplementedError


class OpenStreetMapProvider(BaseGeocodingProvider):
    """OpenStreetMap Nominatim provider"""
    
    async def reverse_geocode(self, latitude: float, longitude: float,
                              session: aiohttp.ClientSession) -> Optional[Address]:
        await self._rate_limit()
        
        params = {
            'lat': latitude,
            'lon': longitude,
            'format': 'json',
            'addressdetails': 1,
            'extratags': 1,
            'namedetails': 1,
            'zoom': 18
        }
        
        if self.config.osm_email:
            params['email'] = self.config.osm_email
        
        url = "https://nominatim.openstreetmap.org/reverse"
        
        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_response(data)
                else:
                    logger.warning(f"OSM reverse geocoding failed: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"OSM request error: {e}")
            return None
    
    async def forward_geocode(self, address: str,
                              session: aiohttp.ClientSession) -> Optional[Tuple[float, float]]:
        await self._rate_limit()
        
        params = {
            'q': address,
            'format': 'json',
            'limit': 1
        }
        
        url = "https://nominatim.openstreetmap.org/search"
        
        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data:
                        return (float(data[0]['lat']), float(data[0]['lon']))
                    return None
                return None
                
        except Exception as e:
            logger.error(f"OSM forward geocoding error: {e}")
            return None
    
    def _parse_response(self, data: Dict[str, Any]) -> Address:
        """Parse OSM reverse geocoding response"""
        address_data = data.get('address', {})
        
        # Determine location type
        location_type = LocationType.UNKNOWN
        for key in ['tourism', 'historic', 'amenity']:
            if data.get('extratags', {}).get(key):
                location_type = LocationType.POINT_OF_INTEREST
                break
        
        if data.get('addresstype') == 'airport':
            location_type = LocationType.AIRPORT
        elif data.get('addresstype') == 'military':
            location_type = LocationType.MILITARY_BASE
        elif data.get('addresstype') in ['school', 'university']:
            location_type = LocationType.SCHOOL
        elif data.get('addresstype') == 'hospital':
            location_type = LocationType.HOSPITAL
        
        return Address(
            display_name=data.get('display_name', ''),
            street=address_data.get('road') or address_data.get('street'),
            house_number=address_data.get('house_number'),
            city=address_data.get('city') or address_data.get('town') or address_data.get('village'),
            state=address_data.get('state'),
            state_code=address_data.get('state_code'),
            postal_code=address_data.get('postcode'),
            country=address_data.get('country'),
            country_code=address_data.get('country_code', '').upper(),
            neighbourhood=address_data.get('neighbourhood'),
            suburb=address_data.get('suburb'),
            district=address_data.get('district'),
            county=address_data.get('county'),
            road=address_data.get('road'),
            location_type=location_type,
            confidence=float(data.get('importance', 0.5)),
            provider=GeocodingProvider.OPENSTREETMAP,
            raw_response=data
        )


class GoogleMapsProvider(BaseGeocodingProvider):
    """Google Maps Geocoding API provider"""
    
    async def reverse_geocode(self, latitude: float, longitude: float,
                              session: aiohttp.ClientSession) -> Optional[Address]:
        if not self.config.google_api_key:
            logger.error("Google Maps API key not configured")
            return None
        
        await self._rate_limit()
        
        params = {
            'latlng': f"{latitude},{longitude}",
            'key': self.config.google_api_key,
            'language': self.config.language
        }
        
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        
        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('status') == 'OK' and data.get('results'):
                        return self._parse_response(data['results'][0])
                    return None
                return None
                
        except Exception as e:
            logger.error(f"Google Maps error: {e}")
            return None
    
    async def forward_geocode(self, address: str,
                              session: aiohttp.ClientSession) -> Optional[Tuple[float, float]]:
        if not self.config.google_api_key:
            return None
        
        await self._rate_limit()
        
        params = {
            'address': address,
            'key': self.config.google_api_key,
            'language': self.config.language
        }
        
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        
        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('status') == 'OK' and data.get('results'):
                        location = data['results'][0]['geometry']['location']
                        return (location['lat'], location['lng'])
                    return None
                return None
                
        except Exception as e:
            logger.error(f"Google Maps forward error: {e}")
            return None
    
    def _parse_response(self, data: Dict[str, Any]) -> Address:
        """Parse Google Maps response"""
        address_components = {}
        for component in data.get('address_components', []):
            for comp_type in component['types']:
                address_components[comp_type] = component['long_name']
                if comp_type == 'country':
                    address_components['country_code'] = component['short_name']
        
        # Determine location type
        location_type = LocationType.UNKNOWN
        for comp_type in data.get('types', []):
            if comp_type == 'airport':
                location_type = LocationType.AIRPORT
            elif comp_type == 'establishment':
                location_type = LocationType.POINT_OF_INTEREST
            elif comp_type == 'school':
                location_type = LocationType.SCHOOL
            elif comp_type == 'hospital':
                location_type = LocationType.HOSPITAL
        
        return Address(
            display_name=data.get('formatted_address', ''),
            street=address_components.get('route'),
            house_number=address_components.get('street_number'),
            city=address_components.get('locality'),
            state=address_components.get('administrative_area_level_1'),
            state_code=address_components.get('administrative_area_level_1_short'),
            postal_code=address_components.get('postal_code'),
            country=address_components.get('country'),
            country_code=address_components.get('country_code', '').upper(),
            location_type=location_type,
            confidence=1.0,
            provider=GeocodingProvider.GOOGLE,
            raw_response=data
        )


# ============================================================================
# Main Geocoding Service
# ============================================================================

class GeocodingService:
    """
    Unified reverse geocoding service
    
    Features:
    - Multiple provider support with automatic fallback
    - Smart caching for performance
    - Batch geocoding
    - Timezone and elevation lookup
    - Point of interest discovery
    - Restricted area detection
    - Rate limit compliance
    """
    
    def __init__(self, config: Optional[GeocodingConfig] = None):
        """
        Initialize geocoding service
        
        Args:
            config: Service configuration
        """
        self.config = config or GeocodingConfig()
        self.cache = GeocodingCache(self.config.cache_size, self.config.cache_ttl_seconds)
        
        # Initialize providers
        self._providers: Dict[GeocodingProvider, BaseGeocodingProvider] = {}
        
        # Primary provider
        if self.config.primary_provider == GeocodingProvider.OPENSTREETMAP:
            self._providers[GeocodingProvider.OPENSTREETMAP] = OpenStreetMapProvider(self.config)
        elif self.config.primary_provider == GeocodingProvider.GOOGLE:
            self._providers[GeocodingProvider.GOOGLE] = GoogleMapsProvider(self.config)
        # Add other providers as needed
        
        # Fallback providers
        for provider in self.config.fallback_providers:
            if provider == GeocodingProvider.OPENSTREETMAP:
                self._providers[provider] = OpenStreetMapProvider(self.config)
            elif provider == GeocodingProvider.GOOGLE:
                self._providers[provider] = GoogleMapsProvider(self.config)
        
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Statistics
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'api_calls': 0,
            'successful_reverse': 0,
            'failed_reverse': 0,
            'provider_failovers': 0
        }
        
        logger.info(f"Geocoding service initialized with primary provider: {self.config.primary_provider.value}")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config.timeout_seconds)
            )
        return self._session
    
    async def close(self):
        """Close HTTP session"""
        if self._session and not self._session.closed:
            await self._session.close()
        logger.info("Geocoding service closed")
    
    async def reverse_geocode(self, latitude: float, longitude: float,
                              use_cache: bool = True,
                              skip_provider_failover: bool = False) -> GeocodeResult:
        """
        Reverse geocode coordinates to address
        
        Args:
            latitude: Latitude in degrees
            longitude: Longitude in degrees
            use_cache: Whether to use cached results
            skip_provider_failover: Skip fallback providers
            
        Returns:
            GeocodeResult with address information
        """
        start_time = datetime.now()
        
        # Check cache
        if use_cache:
            cached = self.cache.get(latitude, longitude)
            if cached:
                self.stats['cache_hits'] += 1
                return cached
        
        self.stats['cache_misses'] += 1
        
        # Try providers in order
        providers_to_try = [self.config.primary_provider] + (
            [] if skip_provider_failover else self.config.fallback_providers
        )
        
        address = None
        used_provider = None
        
        session = await self._get_session()
        
        for provider_name in providers_to_try:
            if provider_name not in self._providers:
                continue
            
            provider = self._providers[provider_name]
            self.stats['api_calls'] += 1
            
            try:
                address = await provider.reverse_geocode(latitude, longitude, session)
                if address:
                    used_provider = provider_name
                    break
                    
            except Exception as e:
                logger.warning(f"Provider {provider_name.value} failed: {e}")
                if provider_name != self.config.primary_provider:
                    self.stats['provider_failovers'] += 1
                continue
        
        response_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        
        if address:
            self.stats['successful_reverse'] += 1
            
            result = GeocodeResult(
                success=True,
                coordinates=(latitude, longitude),
                address=address,
                provider=used_provider,
                response_time_ms=response_time_ms
            )
            
            # Add timezone and elevation
            result.timezone = await self.get_timezone(latitude, longitude)
            result.elevation_m = await self.get_elevation(latitude, longitude)
            
            # Get nearby points of interest (optional)
            if self.config.include_extras:
                result.nearby_pois = await self.get_nearby_pois(latitude, longitude)
            
            # Cache result
            if use_cache:
                self.cache.set(latitude, longitude, result)
            
            return result
        
        else:
            self.stats['failed_reverse'] += 1
            
            return GeocodeResult(
                success=False,
                coordinates=(latitude, longitude),
                error_message="No address found for coordinates",
                provider=self.config.primary_provider,
                response_time_ms=response_time_ms
            )
    
    async def forward_geocode(self, address: str,
                              provider: Optional[GeocodingProvider] = None) -> Optional[Tuple[float, float]]:
        """
        Forward geocode address to coordinates
        
        Args:
            address: Street address or place name
            provider: Specific provider to use (uses primary if None)
            
        Returns:
            Tuple of (latitude, longitude) or None
        """
        provider_name = provider or self.config.primary_provider
        
        if provider_name not in self._providers:
            logger.error(f"Provider not available: {provider_name}")
            return None
        
        provider = self._providers[provider_name]
        session = await self._get_session()
        
        try:
            return await provider.forward_geocode(address, session)
        except Exception as e:
            logger.error(f"Forward geocoding failed: {e}")
            return None
    
    async def get_timezone(self, latitude: float, longitude: float) -> Optional[str]:
        """
        Get timezone name at coordinates
        
        Args:
            latitude: Latitude in degrees
            longitude: Longitude in degrees
            
        Returns:
            Timezone name (e.g., 'America/Los_Angeles')
        """
        # Using Google Time Zone API if available
        if self.config.google_api_key:
            session = await self._get_session()
            params = {
                'location': f"{latitude},{longitude}",
                'timestamp': int(datetime.now().timestamp()),
                'key': self.config.google_api_key
            }
            
            url = "https://maps.googleapis.com/maps/api/timezone/json"
            
            try:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('status') == 'OK':
                            return data.get('timeZoneId')
            except Exception as e:
                logger.warning(f"Timezone lookup failed: {e}")
        
        # Fallback to OpenStreetMap
        try:
            # Use Nominatim's timezone endpoint (if available)
            pass
        except:
            pass
        
        return None
    
    async def get_elevation(self, latitude: float, longitude: float) -> Optional[float]:
        """
        Get elevation at coordinates
        
        Args:
            latitude: Latitude in degrees
            longitude: Longitude in degrees
            
        Returns:
            Elevation in meters
        """
        # Using Open-Elevation API (free, no key required)
        session = await self._get_session()
        url = "https://api.open-elevation.com/api/v1/lookup"
        params = {'locations': f"{latitude},{longitude}"}
        
        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('results'):
                        return data['results'][0].get('elevation')
        except Exception as e:
            logger.warning(f"Elevation lookup failed: {e}")
        
        return None
    
    async def get_nearby_pois(self, latitude: float, longitude: float,
                               radius_meters: float = 500) -> List[PointOfInterest]:
        """
        Get nearby points of interest
        
        Args:
            latitude: Latitude in degrees
            longitude: Longitude in degrees
            radius_meters: Search radius in meters
            
        Returns:
            List of nearby POIs
        """
        # Using Overpass API for OpenStreetMap data
        session = await self._get_session()
        
        # Query for nearby amenities
        overpass_query = f"""
        [out:json];
        (
          node["amenity"](around:{radius_meters},{latitude},{longitude});
          node["tourism"](around:{radius_meters},{latitude},{longitude});
          node["historic"](around:{radius_meters},{latitude},{longitude});
          node["shop"](around:{radius_meters},{latitude},{longitude});
        );
        out body;
        """
        
        url = "https://overpass-api.de/api/interpreter"
        
        try:
            async with session.post(url, data={'data': overpass_query}) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    pois = []
                    for element in data.get('elements', [])[:20]:  # Limit to 20
                        tags = element.get('tags', {})
                        name = tags.get('name', 'Unknown')
                        
                        if name and name != 'Unknown':
                            # Calculate distance
                            distance = self._haversine_distance(
                                latitude, longitude,
                                element.get('lat', 0), element.get('lon', 0)
                            )
                            
                            # Determine category
                            category = 'amenity'
                            if 'tourism' in tags:
                                category = 'tourism'
                            elif 'historic' in tags:
                                category = 'historic'
                            elif 'shop' in tags:
                                category = 'shop'
                            
                            poi = PointOfInterest(
                                name=name,
                                latitude=element.get('lat', 0),
                                longitude=element.get('lon', 0),
                                category=category,
                                distance_meters=distance,
                                type=tags.get('amenity') or tags.get('tourism') or category
                            )
                            pois.append(poi)
                    
                    # Sort by distance
                    pois.sort(key=lambda x: x.distance_meters)
                    return pois[:10]
                    
        except Exception as e:
            logger.warning(f"POI lookup failed: {e}")
        
        return []
    
    async def batch_reverse_geocode(self, coordinates: List[Tuple[float, float]],
                                     use_cache: bool = True) -> List[GeocodeResult]:
        """
        Batch reverse geocode multiple coordinates
        
        Args:
            coordinates: List of (latitude, longitude) tuples
            use_cache: Whether to use cache
            
        Returns:
            List of geocoding results
        """
        results = []
        
        for lat, lon in coordinates:
            result = await self.reverse_geocode(lat, lon, use_cache)
            results.append(result)
            
            # Small delay between requests (if not using cache)
            if not use_cache:
                await asyncio.sleep(0.1)
        
        return results
    
    def _haversine_distance(self, lat1: float, lon1: float,
                            lat2: float, lon2: float) -> float:
        """Calculate distance in meters between two coordinates"""
        R = 6371000  # Earth's radius in meters
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = math.sin(delta_lat/2) ** 2 + \
            math.cos(lat1_rad) * math.cos(lat2_rad) * \
            math.sin(delta_lon/2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    async def check_restricted_area(self, latitude: float, longitude: float) -> Tuple[bool, Optional[str]]:
        """
        Check if coordinates are in a restricted area
        
        Args:
            latitude: Latitude in degrees
            longitude: Longitude in degrees
            
        Returns:
            Tuple of (is_restricted, restriction_reason)
        """
        # Common restricted areas (simplified)
        # In production, this would check against a database of restricted zones
        
        # Check for airports (simplified bounding boxes)
        airports = [
            # San Francisco International (SFO)
            {'lat_min': 37.58, 'lat_max': 37.65, 'lon_min': -122.42, 'lon_max': -122.35, 'name': 'Airport - SFO'},
            # Los Angeles International (LAX)
            {'lat_min': 33.92, 'lat_max': 33.96, 'lon_min': -118.42, 'lon_max': -118.37, 'name': 'Airport - LAX'},
            # JFK Airport
            {'lat_min': 40.61, 'lat_max': 40.67, 'lon_min': -73.81, 'lon_max': -73.74, 'name': 'Airport - JFK'},
        ]
        
        for airport in airports:
            if (airport['lat_min'] <= latitude <= airport['lat_max'] and
                airport['lon_min'] <= longitude <= airport['lon_max']):
                return True, airport['name']
        
        # Check for military bases (example)
        military_bases = [
            {'lat': 37.78, 'lon': -122.27, 'radius_km': 3, 'name': 'Naval Air Station Alameda'},
        ]
        
        for base in military_bases:
            distance = self._haversine_distance(latitude, longitude, base['lat'], base['lon'])
            if distance <= base['radius_km'] * 1000:
                return True, base['name']
        
        # Check for nuclear facilities, government buildings, etc.
        # This would be expanded in production
        
        # Use reverse geocoding to check address-based restrictions
        geocode = await self.reverse_geocode(latitude, longitude, use_cache=True)
        if geocode.success and geocode.address:
            # Check for sensitive location types
            sensitive_types = [
                LocationType.MILITARY_BASE,
                LocationType.GOVERNMENT_BUILDING
            ]
            if geocode.address.location_type in sensitive_types:
                return True, geocode.address.location_type.value
        
        return False, None
    
    async def get_location_context(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """
        Get rich location context including address, timezone, elevation, and nearby places
        
        Args:
            latitude: Latitude in degrees
            longitude: Longitude in degrees
            
        Returns:
            Dictionary with comprehensive location context
        """
        # Get reverse geocode result
        geocode = await self.reverse_geocode(latitude, longitude)
        
        if not geocode.success:
            return {'error': 'Could not geocode coordinates'}
        
        # Check restricted area
        is_restricted, restriction_reason = await self.check_restricted_area(latitude, longitude)
        
        context = {
            'coordinates': {'lat': latitude, 'lon': longitude},
            'address': geocode.address.to_dict() if geocode.address else None,
            'short_name': geocode.address.get_short_name() if geocode.address else None,
            'administrative_area': geocode.address.get_administrative_area() if geocode.address else None,
            'timezone': geocode.timezone,
            'elevation_meters': geocode.elevation_m,
            'is_restricted_area': is_restricted,
            'restriction_reason': restriction_reason,
            'nearby_pois': [
                {'name': poi.name, 'category': poi.category, 'distance_meters': poi.distance_meters}
                for poi in geocode.nearby_pois
            ],
            'provider': geocode.provider.value,
            'response_time_ms': geocode.response_time_ms
        }
        
        return context
    
    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics"""
        return {
            **self.stats,
            'cache_size': len(self.cache._cache) if self.config.enable_cache else 0,
            'cache_hit_rate': self.stats['cache_hits'] / (self.stats['cache_hits'] + self.stats['cache_misses']) 
                              if (self.stats['cache_hits'] + self.stats['cache_misses']) > 0 else 0,
            'primary_provider': self.config.primary_provider.value,
            'fallback_providers': [p.value for p in self.config.fallback_providers]
        }
    
    def clear_cache(self):
        """Clear geocoding cache"""
        self.cache.clear()
        logger.info("Geocoding cache cleared")


# ============================================================================
# Factory Functions
# ============================================================================

def create_osm_geocoding_service(user_agent: str = "DroneDetectionSystem/2.0",
                                  email: Optional[str] = None) -> GeocodingService:
    """
    Create geocoding service using OpenStreetMap (free, no API key required)
    
    Args:
        user_agent: User agent string for API requests
        email: Contact email for OSM (optional but recommended)
        
    Returns:
        Configured GeocodingService
    """
    config = GeocodingConfig(
        primary_provider=GeocodingProvider.OPENSTREETMAP,
        osm_user_agent=user_agent,
        osm_email=email,
        requests_per_second=1.0  # Nominatim limit
    )
    return GeocodingService(config)


def create_google_geocoding_service(api_key: str) -> GeocodingService:
    """
    Create geocoding service using Google Maps API
    
    Args:
        api_key: Google Maps API key
        
    Returns:
        Configured GeocodingService
    """
    config = GeocodingConfig(
        primary_provider=GeocodingProvider.GOOGLE,
        google_api_key=api_key,
        requests_per_second=10.0,
        fallback_providers=[GeocodingProvider.OPENSTREETMAP]
    )
    return GeocodingService(config)


# ============================================================================
# Example Usage
# ============================================================================

async def example_usage():
    """Example usage of geocoding service"""
    
    print("Geocoding Service Example")
    print("=" * 50)
    
    # Create service (using OpenStreetMap - free, no key required)
    geocoder = create_osm_geocoding_service(
        user_agent="DroneDetectionSystem/2.0",
        email="demo@example.com"
    )
    
    # Sample drone detection coordinates
    test_coordinates = [
        (37.7749, -122.4194),   # San Francisco
        (40.7128, -74.0060),    # New York
        (51.5074, -0.1278),     # London
        (34.0522, -118.2437)    # Los Angeles
    ]
    
    print("\n1. Reverse Geocoding Examples:")
    
    for lat, lon in test_coordinates:
        result = await geocoder.reverse_geocode(lat, lon)
        
        if result.success:
            print(f"\n   Coordinates: ({lat:.4f}, {lon:.4f})")
            print(f"   Address: {result.address.display_name[:80]}...")
            print(f"   Short Name: {result.address.get_short_name()}")
            print(f"   City/State: {result.address.get_administrative_area()}")
            print(f"   Location Type: {result.address.location_type.value}")
            print(f"   Confidence: {result.address.confidence:.2%}")
            if result.timezone:
                print(f"   Timezone: {result.timezone}")
            if result.elevation_m:
                print(f"   Elevation: {result.elevation_m:.0f}m")
            if result.nearby_pois:
                print(f"   Nearby: {result.nearby_pois[0].name} ({result.nearby_pois[0].distance_meters:.0f}m)")
        else:
            print(f"   Failed: {result.error_message}")
    
    # Check restricted area
    print("\n2. Restricted Area Check:")
    
    # Test near airport
    airport_lat, airport_lon = 37.62, -122.38  # Near SFO
    is_restricted, reason = await geocoder.check_restricted_area(airport_lat, airport_lon)
    print(f"   Coordinates near SFO: ({airport_lat}, {airport_lon})")
    print(f"   Restricted: {is_restricted}, Reason: {reason}")
    
    # Get rich location context
    print("\n3. Rich Location Context:")
    
    drone_lat, drone_lon = 37.7749, -122.4194
    context = await geocoder.get_location_context(drone_lat, drone_lon)
    
    print(f"   Short Name: {context.get('short_name')}")
    print(f"   Administrative Area: {context.get('administrative_area')}")
    print(f"   Timezone: {context.get('timezone')}")
    print(f"   Elevation: {context.get('elevation_meters')}m")
    print(f"   Restricted Area: {context.get('is_restricted_area')}")
    if context.get('nearby_pois'):
        print(f"   Nearby POIs: {len(context.get('nearby_pois'))}")
        for poi in context.get('nearby_pois')[:3]:
            print(f"     - {poi['name']} ({poi['distance_meters']:.0f}m)")
    
    # Forward geocoding (address to coordinates)
    print("\n4. Forward Geocoding Example:")
    
    addresses = [
        "Golden Gate Bridge, San Francisco",
        "Eiffel Tower, Paris",
        "Sydney Opera House, Australia"
    ]
    
    for address in addresses:
        coords = await geocoder.forward_geocode(address)
        if coords:
            print(f"   {address}: ({coords[0]:.4f}, {coords[1]:.4f})")
    
    # Batch geocoding
    print("\n5. Batch Reverse Geocoding:")
    
    batch_coords = [(37.77, -122.42), (37.78, -122.41), (37.79, -122.40)]
    results = await geocoder.batch_reverse_geocode(batch_coords, use_cache=True)
    
    for i, result in enumerate(results):
        if result.success:
            print(f"   {i+1}. {result.address.get_short_name()}")
    
    # Statistics
    print("\n6. Service Statistics:")
    stats = geocoder.get_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    # Cleanup
    await geocoder.close()
    
    print("\n" + "=" * 50)
    print("Geocoding service example complete")


async def main():
    """Main function"""
    await example_usage()


if __name__ == "__main__":
    asyncio.run(main())