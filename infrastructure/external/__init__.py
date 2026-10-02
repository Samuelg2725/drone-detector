#!/usr/bin/env python3
# drone-detector/infrastructure/external/__init__.py
"""
Infrastructure External Services Module

This module provides integration with external services and APIs for the Drone Detection System,
including:
- ADS-B Exchange aircraft tracking
- FlightRadar24 commercial flight data
- Email and SMS notifications
- Reverse geocoding services
- Weather data integration
- NOTAM (Notice to Airmen) feeds
- Aviation weather services
- Map tile services
- Alert aggregation services

The external services layer enables the system to:
- Differentiate between drones and manned aircraft
- Provide context-aware alerts with location names
- Notify security personnel via multiple channels
- Integrate with existing aviation monitoring systems
"""

from typing import Dict, Any, Optional, List, Union, Tuple
from datetime import datetime

# ============================================================================
# ADS-B Exchange Client
# ============================================================================

from .adsb_client import (
    ADSBExchangeClient,
    ADSBConfig,
    AircraftPosition,
    AircraftInfo,
    FlightRoute,
    AirportInfo,
    ADSBDataSource,
    AircraftCategory,
    EmergencyStatus,
    create_adsb_client
)

# ============================================================================
# FlightRadar24 Client
# ============================================================================

from .flightradar_client import (
    FlightRadar24Client,
    FR24Config,
    FlightPosition,
    FlightDetails,
    AirportBoard,
    FlightStatus,
    FlightType,
    AircraftAge,
    create_flightradar_client
)

# ============================================================================
# Notification Service
# ============================================================================

from .notification_service import (
    NotificationService,
    EmailConfig,
    SMSConfig,
    EmailProvider,
    SMSProvider,
    NotificationMessage,
    NotificationPriority,
    NotificationType,
    NotificationStatus,
    NotificationTemplate,
    create_gmail_notification_service,
    create_twilio_notification_service,
    create_custom_smtp_service
)

# ============================================================================
# Geocoding Service
# ============================================================================

from .geocoding import (
    GeocodingService,
    GeocodingConfig,
    GeocodingProvider,
    Address,
    LocationType,
    PointOfInterest,
    GeocodeResult,
    create_osm_geocoding_service,
    create_google_geocoding_service
)

# ============================================================================
# Version and Metadata
# ============================================================================

__version__ = "2.0.0"
__author__ = "Drone Detection System Team"
__copyright__ = "Copyright 2024-2025, Drone Detection System"
__license__ = "MIT"

# ============================================================================
# Public API - Explicit Exports
# ============================================================================

__all__ = [
    # ADS-B Exchange
    "ADSBExchangeClient",
    "ADSBConfig",
    "AircraftPosition",
    "AircraftInfo",
    "FlightRoute",
    "AirportInfo",
    "ADSBDataSource",
    "AircraftCategory",
    "EmergencyStatus",
    "create_adsb_client",
    
    # FlightRadar24
    "FlightRadar24Client",
    "FR24Config",
    "FlightPosition",
    "FlightDetails",
    "AirportBoard",
    "FlightStatus",
    "FlightType",
    "AircraftAge",
    "create_flightradar_client",
    
    # Notification Service
    "NotificationService",
    "EmailConfig",
    "SMSConfig",
    "EmailProvider",
    "SMSProvider",
    "NotificationMessage",
    "NotificationPriority",
    "NotificationType",
    "NotificationStatus",
    "NotificationTemplate",
    "create_gmail_notification_service",
    "create_twilio_notification_service",
    "create_custom_smtp_service",
    
    # Geocoding Service
    "GeocodingService",
    "GeocodingConfig",
    "GeocodingProvider",
    "Address",
    "LocationType",
    "PointOfInterest",
    "GeocodeResult",
    "create_osm_geocoding_service",
    "create_google_geocoding_service",
]


# ============================================================================
# Unified External Services Manager
# ============================================================================

class ExternalServicesManager:
    """
    Unified manager for all external service integrations
    
    This class provides a single interface for all third-party services:
    - Aircraft tracking (ADS-B, FlightRadar24)
    - Notifications (Email, SMS)
    - Location services (Geocoding)
    
    Usage:
        manager = ExternalServicesManager()
        await manager.initialize()
        
        # Check for aircraft near drone
        aircraft = await manager.get_aircraft_near_drone(lat, lon, alt)
        
        # Send alert with location context
        await manager.send_drone_alert(detection_data, recipients)
        
        # Get location name
        location = await manager.reverse_geocode(lat, lon)
    """
    
    def __init__(self):
        """Initialize external services manager"""
        self.adsb_client: Optional[ADSBExchangeClient] = None
        self.flightradar_client: Optional[FlightRadar24Client] = None
        self.notification_service: Optional[NotificationService] = None
        self.geocoding_service: Optional[GeocodingService] = None
        
        self._initialized = False
        
        # Configuration
        self._config = {
            'enable_adsb': True,
            'enable_flightradar': False,  # Requires API key
            'enable_notifications': True,
            'enable_geocoding': True
        }
        
        self.stats = {
            'aircraft_checks': 0,
            'notifications_sent': 0,
            'geocode_requests': 0,
            'active_alerts': 0
        }
    
    async def initialize(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize external services
        
        Args:
            config: Configuration dictionary for services
        """
        if self._initialized:
            logger.warning("External services already initialized")
            return
        
        if config:
            self._config.update(config)
        
        # Initialize ADS-B client
        if self._config.get('enable_adsb'):
            adsb_config = self._config.get('adsb', {})
            self.adsb_client = create_adsb_client(
                api_key=adsb_config.get('api_key'),
                data_source=adsb_config.get('data_source', 'adsb_exchange')
            )
            logger.info("ADS-B client initialized")
        
        # Initialize FlightRadar24 client
        if self._config.get('enable_flightradar'):
            fr24_config = self._config.get('flightradar', {})
            self.flightradar_client = create_flightradar_client(
                api_key=fr24_config.get('api_key')
            )
            logger.info("FlightRadar24 client initialized")
        
        # Initialize notification service
        if self._config.get('enable_notifications'):
            notification_config = self._config.get('notifications', {})
            
            # Configure email if provided
            email_config = None
            if notification_config.get('email'):
                email_config = EmailConfig(
                    provider=EmailProvider(notification_config['email'].get('provider', 'gmail')),
                    username=notification_config['email'].get('username'),
                    password=notification_config['email'].get('password'),
                    from_email=notification_config['email'].get('from_email'),
                    from_name=notification_config['email'].get('from_name', 'Drone Detection System')
                )
            
            # Configure SMS if provided
            sms_config = None
            if notification_config.get('sms'):
                sms_config = SMSConfig(
                    provider=SMSProvider(notification_config['sms'].get('provider', 'twilio')),
                    twilio_account_sid=notification_config['sms'].get('twilio_account_sid'),
                    twilio_auth_token=notification_config['sms'].get('twilio_auth_token'),
                    twilio_phone_number=notification_config['sms'].get('twilio_phone_number')
                )
            
            self.notification_service = NotificationService(
                email_config=email_config,
                sms_config=sms_config
            )
            logger.info("Notification service initialized")
        
        # Initialize geocoding service
        if self._config.get('enable_geocoding'):
            geocoding_config = self._config.get('geocoding', {})
            provider = geocoding_config.get('provider', 'osm')
            
            if provider == 'google':
                self.geocoding_service = create_google_geocoding_service(
                    geocoding_config.get('api_key', '')
                )
            else:
                self.geocoding_service = create_osm_geocoding_service(
                    user_agent=geocoding_config.get('user_agent', 'DroneDetectionSystem/2.0'),
                    email=geocoding_config.get('email')
                )
            logger.info(f"Geocoding service initialized with provider: {provider}")
        
        self._initialized = True
        logger.info("External services manager initialized")
    
    async def close(self) -> None:
        """Close all external service connections"""
        if self.adsb_client:
            await self.adsb_client.close()
        
        if self.flightradar_client:
            await self.flightradar_client.close()
        
        if self.notification_service:
            await self.notification_service.shutdown()
        
        if self.geocoding_service:
            await self.geocoding_service.close()
        
        self._initialized = False
        logger.info("External services manager closed")
    
    # ========================================================================
    # Aircraft Tracking Methods
    # ========================================================================
    
    async def get_aircraft_near_drone(self, latitude: float, longitude: float,
                                       altitude_ft: float, radius_km: float = 5.0) -> List[Dict[str, Any]]:
        """
        Get aircraft near drone position
        
        Args:
            latitude: Drone latitude
            longitude: Drone longitude
            altitude_ft: Drone altitude in feet
            radius_km: Search radius in kilometers
            
        Returns:
            List of nearby aircraft
        """
        self.stats['aircraft_checks'] += 1
        conflicting = []
        
        # Check ADS-B data
        if self.adsb_client:
            # Get bounds for radius
            lat_range = radius_km / 111.0
            lon_range = radius_km / (111.0 * abs(latitude))
            bounds = {
                'lat_min': latitude - lat_range,
                'lat_max': latitude + lat_range,
                'lon_min': longitude - lon_range,
                'lon_max': longitude + lon_range
            }
            
            aircraft_list = await self.adsb_client.get_all_aircraft(bounds)
            
            # Filter by altitude
            for aircraft in aircraft_list:
                if aircraft.altitude_ft:
                    altitude_diff = abs(aircraft.altitude_ft - altitude_ft)
                    if altitude_diff < 500:  # Within 500 feet
                        distance = self._haversine_distance(
                            latitude, longitude,
                            aircraft.latitude, aircraft.longitude
                        )
                        if distance <= radius_km:
                            conflicting.append(aircraft.to_dict())
        
        # Check FlightRadar24 data
        if self.flightradar_client:
            flights = await self.flightradar_client.check_aircraft_near_drone(
                latitude, longitude, altitude_ft, radius_km
            )
            for flight in flights:
                conflicting.append(flight.to_dict())
        
        return conflicting
    
    def _haversine_distance(self, lat1: float, lon1: float,
                            lat2: float, lon2: float) -> float:
        """Calculate distance in kilometers"""
        import math
        R = 6371
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = math.sin(delta_lat/2) ** 2 + \
            math.cos(lat1_rad) * math.cos(lat2_rad) * \
            math.sin(delta_lon/2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    # ========================================================================
    # Notification Methods
    # ========================================================================
    
    async def send_drone_alert(self, detection_data: Dict[str, Any],
                                recipients: List[str]) -> List[NotificationMessage]:
        """
        Send drone detection alert
        
        Args:
            detection_data: Detection information
            recipients: List of recipient emails/phone numbers
            
        Returns:
            List of sent messages
        """
        if not self.notification_service:
            logger.error("Notification service not configured")
            return []
        
        # Add location context if available
        if self.geocoding_service and 'latitude' in detection_data and 'longitude' in detection_data:
            context = await self.geocoding_service.get_location_context(
                detection_data['latitude'],
                detection_data['longitude']
            )
            if context.get('short_name'):
                detection_data['location_name'] = context['short_name']
            if context.get('administrative_area'):
                detection_data['area'] = context['administrative_area']
        
        messages = await self.notification_service.send_drone_alert(
            detection_data=detection_data,
            recipients=recipients,
            notification_types=[NotificationType.EMAIL, NotificationType.SMS]
        )
        
        self.stats['notifications_sent'] += len(messages)
        
        return messages
    
    async def send_alert_escalation(self, alert_data: Dict[str, Any],
                                     recipient: str) -> bool:
        """
        Send alert escalation notification
        
        Args:
            alert_data: Alert information
            recipient: Recipient email
            
        Returns:
            True if sent
        """
        if not self.notification_service:
            logger.error("Notification service not configured")
            return False
        
        success = await self.notification_service.send_alert_escalation(alert_data, recipient)
        
        if success:
            self.stats['notifications_sent'] += 1
        
        return success
    
    async def send_daily_summary(self, summary_data: Dict[str, Any],
                                  recipients: List[str]) -> List[NotificationMessage]:
        """
        Send daily summary report
        
        Args:
            summary_data: Summary statistics
            recipients: List of recipient emails
            
        Returns:
            List of sent messages
        """
        if not self.notification_service:
            logger.error("Notification service not configured")
            return []
        
        messages = await self.notification_service.send_daily_summary(summary_data, recipients)
        self.stats['notifications_sent'] += len(messages)
        
        return messages
    
    # ========================================================================
    # Geocoding Methods
    # ========================================================================
    
    async def reverse_geocode(self, latitude: float, longitude: float) -> Optional[Address]:
        """
        Reverse geocode coordinates to address
        
        Args:
            latitude: Latitude in degrees
            longitude: Longitude in degrees
            
        Returns:
            Address object or None
        """
        if not self.geocoding_service:
            logger.error("Geocoding service not configured")
            return None
        
        self.stats['geocode_requests'] += 1
        
        result = await self.geocoding_service.reverse_geocode(latitude, longitude)
        
        if result.success:
            return result.address
        
        return None
    
    async def get_location_context(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """
        Get rich location context
        
        Args:
            latitude: Latitude in degrees
            longitude: Longitude in degrees
            
        Returns:
            Location context dictionary
        """
        if not self.geocoding_service:
            return {'coordinates': {'lat': latitude, 'lon': longitude}}
        
        return await self.geocoding_service.get_location_context(latitude, longitude)
    
    async def check_restricted_area(self, latitude: float, longitude: float) -> Tuple[bool, Optional[str]]:
        """
        Check if coordinates are in restricted area
        
        Args:
            latitude: Latitude in degrees
            longitude: Longitude in degrees
            
        Returns:
            Tuple of (is_restricted, restriction_reason)
        """
        if not self.geocoding_service:
            return False, None
        
        return await self.geocoding_service.check_restricted_area(latitude, longitude)
    
    # ========================================================================
    # Utility Methods
    # ========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics"""
        stats = {
            **self.stats,
            'initialized': self._initialized,
            'services': {
                'adsb': self.adsb_client is not None,
                'flightradar': self.flightradar_client is not None,
                'notifications': self.notification_service is not None,
                'geocoding': self.geocoding_service is not None
            }
        }
        
        # Add individual service stats
        if self.adsb_client:
            stats['adsb_stats'] = self.adsb_client.get_stats()
        
        if self.flightradar_client:
            stats['flightradar_stats'] = self.flightradar_client.get_stats()
        
        if self.notification_service:
            stats['notification_stats'] = self.notification_service.get_stats()
        
        if self.geocoding_service:
            stats['geocoding_stats'] = self.geocoding_service.get_stats()
        
        return stats
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check health of all external services
        
        Returns:
            Dictionary with health status of each service
        """
        health = {}
        
        # Check ADS-B
        if self.adsb_client:
            try:
                # Try to get a small amount of data
                aircraft = await self.adsb_client.get_all_aircraft()
                health['adsb'] = 'healthy' if aircraft is not None else 'degraded'
            except Exception as e:
                health['adsb'] = f'unhealthy: {e}'
        
        # Check geocoding
        if self.geocoding_service:
            try:
                result = await self.geocoding_service.reverse_geocode(37.7749, -122.4194, use_cache=False)
                health['geocoding'] = 'healthy' if result.success else 'degraded'
            except Exception as e:
                health['geocoding'] = f'unhealthy: {e}'
        
        # Check notification service
        if self.notification_service:
            health['notifications'] = 'configured'
        
        return health


# ============================================================================
# Convenience Functions
# ============================================================================

def get_external_services_info() -> Dict[str, Any]:
    """
    Get information about available external services
    
    Returns:
        Dictionary with service information
    """
    return {
        "version": __version__,
        "services": {
            "adsb_exchange": {
                "description": "Real-time aircraft tracking via ADS-B",
                "features": ["live_tracking", "aircraft_info", "flight_routes", "websocket_feed"],
                "requires_api_key": False
            },
            "flightradar24": {
                "description": "Commercial flight tracking",
                "features": ["live_flights", "airport_boards", "flight_details", "aircraft_photos"],
                "requires_api_key": True
            },
            "notifications": {
                "description": "Email and SMS alert delivery",
                "features": ["email", "sms", "templates", "rate_limiting", "retries"],
                "providers": ["gmail", "twilio", "aws_ses", "custom_smtp"]
            },
            "geocoding": {
                "description": "Reverse geocoding and location services",
                "features": ["address_lookup", "timezone", "elevation", "poi_discovery"],
                "providers": ["osm", "google"]
            }
        }
    }


# ============================================================================
# Singleton Manager
# ============================================================================

_default_external_manager: Optional[ExternalServicesManager] = None


async def get_external_services_manager(config: Optional[Dict[str, Any]] = None) -> ExternalServicesManager:
    """
    Get or create the default external services manager singleton
    
    Args:
        config: Optional configuration for initialization
        
    Returns:
        ExternalServicesManager instance
    """
    global _default_external_manager
    
    if _default_external_manager is None:
        _default_external_manager = ExternalServicesManager()
        await _default_external_manager.initialize(config)
    
    return _default_external_manager


async def reset_external_services_manager() -> None:
    """Reset the default external services manager"""
    global _default_external_manager
    
    if _default_external_manager:
        await _default_external_manager.close()
        _default_external_manager = None


# ============================================================================
# Module Documentation
# ============================================================================

__doc__ = """
Infrastructure External Services Package
========================================

This package provides integration with external services and APIs for the Drone Detection System.

Components:
-----------
1. **ADS-B Exchange Client** - Real-time aircraft tracking (free)
2. **FlightRadar24 Client** - Commercial flight data (requires API key)
3. **Notification Service** - Email and SMS alerts
4. **Geocoding Service** - Reverse geocoding and location context

Quick Start:
-----------
```python
from infrastructure.external import (
    ExternalServicesManager,
    get_external_services_manager
)

# Method 1: Use unified manager
manager = await get_external_services_manager({
    'enable_adsb': True,
    'enable_notifications': True,
    'enable_geocoding': True,
    'notifications': {
        'email': {
            'provider': 'gmail',
            'username': 'your@gmail.com',
            'password': 'app_password',
            'from_email': 'alerts@drone-detector.com'
        }
    }
})

# Check for aircraft near drone
aircraft = await manager.get_aircraft_near_drone(
    latitude=37.7749,
    longitude=-122.4194,
    altitude_ft=400,
    radius_km=3.0
)

if aircraft:
    await manager.send_drone_alert(detection_data, ["security@example.com"])

# Get location context
context = await manager.get_location_context(37.7749, -122.4194)
print(f"Drone over {context.get('short_name')}")

# Method 2: Use individual services
from infrastructure.external import create_adsb_client, create_osm_geocoding_service

adsb = create_adsb_client()
geocoder = create_osm_geocoding_service("MyApp/1.0")