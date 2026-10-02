# Drone Detector System - Remote ID Integration Guide

## Overview

Remote ID (RID) is a system that allows drones to broadcast identification and location information. The Drone Detector system integrates with both Bluetooth (BT) and Wi-Fi (WiFi) based Remote ID protocols, enabling identification of compliant drones even when conventional RF detection is challenging.

## Remote ID Standards

### Supported Protocols

| Standard | Frequency | Range | Data Rate | Status |
|----------|-----------|-------|-----------|--------|
| ASTM F3411-22 (Standard) | 2.4 GHz (BLE) | 100-500m | 1 Mbps | ✅ Full Support |
| EU Drone Regulation | 2.4 GHz (BLE) | 100-500m | 1 Mbps | ✅ Full Support |
| Wi-Fi Beacon (802.11) | 2.4/5 GHz | 50-200m | 11-54 Mbps | ✅ Full Support |
| Bluetooth 4.0+ (LE) | 2.4 GHz | 100-500m | 1 Mbps | ✅ Full Support |
| Bluetooth 5.0+ (Long Range) | 2.4 GHz | 200-800m | 0.5 Mbps | ✅ Full Support |
| LTE-based RID | Cellular | Global | Variable | ⚠️ Beta Support |

### Remote ID Message Types

```yaml
Basic ID:
  - ID Type: Serial number, CAA registration, etc.
  - UAS ID: Unique identifier
  - ID Type: Specific format indicator

Location/Vector:
  - Latitude/Longitude (WGS84)
  - Altitude (barometric/GNSS)
  - Speed (horizontal/vertical)
  - Heading (true north)
  - Timestamp (UTC)

Auth/Status:
  - Authentication data
  - Operational status
  - Emergency status

System Info:
  - Manufacturer
  - Model name
  - Serial number
  - Operator ID
  - Category (1-4)
  - Class (0-6)

Operator Info:
  - Operator ID/registration
  - Operator location
  - Contact info (if allowed)
Architecture
text
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Remote ID Integration Architecture                  │
│                                                                              │
│  ┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐ │
│  │   Bluetooth LE   │      │    Wi-Fi 2.4GHz  │      │   SDR Spectrum   │ │
│  │    Scanner       │      │    Scanner       │      │    Analyzer      │ │
│  └────────┬─────────┘      └────────┬─────────┘      └────────┬─────────┘ │
│           │                         │                         │            │
│           ▼                         ▼                         ▼            │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │                     Remote ID Processor                          │      │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────┐  │      │
│  │  │  BLE Frame │  │ Wi-Fi Frame│  │  Signature │  │  Fusion  │  │      │
│  │  │  Decoder   │  │  Decoder   │  │  Matching  │  │  Engine  │  │      │
│  │  └────────────┘  └────────────┘  └────────────┘  └──────────┘  │      │
│  └──────────────────────────────────────────────────────────────────┘      │
│                                      │                                      │
│                                      ▼                                      │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │                     Remote ID Database                            │      │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────┐  │      │
│  │  │  Drone ID  │  │  Position  │  │  Operator  │  │  History │  │      │
│  │  │   Index    │  │   Store    │  │   Info     │  │   Store  │  │      │
│  │  └────────────┘  └────────────┘  └────────────┘  └──────────┘  │      │
│  └──────────────────────────────────────────────────────────────────┘      │
│                                      │                                      │
│                                      ▼                                      │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │                     Integration Layers                            │      │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────┐  │      │
│  │  │ Detection  │  │  Tracking  │  │  Alerting  │  │  Export  │  │      │
│  │  │  Pipeline  │  │   Engine   │  │  System    │  │  Module  │  │      │
│  │  └────────────┘  └────────────┘  └────────────┘  └──────────┘  │      │
│  └──────────────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────────────┘
Hardware Setup for Remote ID
Bluetooth LE Scanner
yaml
Recommended Hardware for BLE Scanning:
  Primary: "Nordic nRF52840 Dongle"
    Interface: USB 2.0
    Range: 400m (with antenna)
    Channels: 37, 38, 39
    Scanning Rate: 100% duty cycle
    
  Alternative: "ESP32 Development Board"
    Interface: USB/UART
    Range: 200m
    Cost: $10-15
    
  Professional: "Ubertooth One"
    Interface: USB 2.0
    Range: 500m
    Features: Full Bluetooth monitoring

  Network-based: "Raspberry Pi with BLE"
    Multiple nodes for triangulation
    Ethernet/WiFi backhaul
Wi-Fi Scanner Setup
yaml
Wi-Fi Hardware Options:
  Professional: "Kismet-compatible adapter"
    - Chipset: Atheros AR9271
    - Monitor mode support
    - Dual-band 2.4/5 GHz
    
  Cost-effective: "RTL8812AU adapter"
    - Monitor mode capable
    - 2.4/5 GHz support
    - $20-30
    
  Integrated: "On-board Wi-Fi (Raspberry Pi 4/5)"
    - Good for basic scanning
    - Limited to 2.4 GHz
    - Range: 100m
Installation Script
bash
#!/bin/bash
# install_remote_id_hardware.sh

# Install Bluetooth tools
sudo apt update
sudo apt install -y \
    bluez \
    bluez-hcidump \
    bluetooth \
    rfkill \
    libbluetooth-dev \
    python3-bluez

# Install Wi-Fi tools
sudo apt install -y \
    aircrack-ng \
    kismet \
    tcpdump \
    wireshark

# Configure Bluetooth
sudo systemctl enable bluetooth
sudo systemctl start bluetooth

# Set Bluetooth scanning permissions
sudo setcap cap_net_raw,cap_net_admin+eip $(which hcitool)
sudo setcap cap_net_raw,cap_net_admin+eip $(which hcidump)

# Configure Wi-Fi for monitor mode
sudo iwconfig wlan0 mode monitor
sudo ip link set wlan0 up

# Install Python libraries
pip install \
    bleak \
    bluepy \
    pybluez \
    scapy \
    'scapy[complete]'
Configuration
Remote ID Configuration File
yaml
# config/remote_id.yaml
remote_id:
  # General settings
  enabled: true
  scan_interval: 1  # seconds
  scan_duration: 1  # seconds per channel
  
  # BLE Scanner
  bluetooth:
    enabled: true
    adapter: "hci0"  # Bluetooth adapter
    scan_mode: "active"  # active or passive
    scan_parameters:
      interval_ms: 30   # Scan interval
      window_ms: 30     # Scan window
      passive_timeout: 5  # seconds
      
    filters:
      min_rssi: -80  # dBm, ignore weaker signals
      max_age: 10    # seconds, cache timeout
      
    channels:
      - 37  # Advertising channel 37 (2402 MHz)
      - 38  # Advertising channel 38 (2426 MHz)
      - 39  # Advertising channel 39 (2480 MHz)
      
    # Duplicate filtering
    duplicate_filtering:
      enabled: true
      window_seconds: 10
      
  # Wi-Fi Scanner
  wifi:
    enabled: true
    interface: "wlan0"
    channels: [1, 6, 11]  # 2.4 GHz channels
    # channels: [36, 40, 44, 48]  # 5 GHz channels
    hop_interval: 0.2  # seconds per channel
    monitor_mode: true
    
    filters:
      min_rssi: -85
      beacon_only: false  # Include probe responses
      
  # SDR-based RID (experimental)
  sdr:
    enabled: false
    frequency: 2.402e9  # BLE channel 37
    bandwidth: 2e6
    modulation: "gfsk"
    
  # Data storage
  storage:
    retention_days: 90
    archive_raw: false
    compress: true
    
  # Integration with detection
  integration:
    correlate_with_rf: true
    correlation_window_ms: 500
    override_rf_detection: false  # Use RID if available
    confidence_boost: 0.3  # Confidence increase when RID matches
    
  # Alerting
  alerts:
    no_remote_id: true  # Alert when drone lacks RID
    suspicious_id: true
    operator_not_authorized: true
    location_outside_zone: true
Multi-Scanner Configuration
yaml
# config/remote_id_nodes.yaml
nodes:
  - name: "scanner_01"
    location:
      latitude: 37.7749
      longitude: -122.4194
      altitude: 10.0
    hardware:
      bluetooth: "hci0"
      wifi: "wlan0"
    address: "192.168.1.101"
    
  - name: "scanner_02"
    location:
      latitude: 37.7750
      longitude: -122.4185
      altitude: 12.0
    hardware:
      bluetooth: "hci0"
      wifi: "wlan0"
    address: "192.168.1.102"
    
  - name: "scanner_03"
    location:
      latitude: 37.7745
      longitude: -122.4200
      altitude: 11.0
    hardware:
      bluetooth: "hci0"
      wifi: "wlan0"
    address: "192.168.1.103"
Remote ID Processing Pipeline
BLE Frame Decoding
python
# infrastructure/remote_id/ble_decoder.py
"""Bluetooth LE Remote ID decoder"""

import asyncio
from bleak import BleakScanner
from construct import Struct, Int8ul, Int16ul, Int32ul, Bytes, String

# ASTM F3411-22 message structures
BasicIDMessage = Struct(
    "msg_type" / Int8ul,
    "id_type" / Int8ul,
    "ua_type" / Int8ul,
    "uas_id" / Bytes(20)
)

LocationMessage = Struct(
    "msg_type" / Int8ul,
    "status" / Int8ul,
    "direction" / Int8ul,
    "latitude" / Int32ul,
    "longitude" / Int32ul,
    "altitude_baro" / Int16ul,
    "altitude_geo" / Int16ul,
    "heading" / Int16ul,
    "speed_horiz" / Int16ul,
    "speed_vert" / Int16ul,
    "timestamp" / Int16ul
)

class BLERemoteIDDecoder:
    """BLE Remote ID message decoder"""
    
    def __init__(self, config):
        self.config = config
        self.scanner = None
        self.known_drones = {}
        
    async def start_scanning(self):
        """Start BLE scanning for Remote ID"""
        self.scanner = BleakScanner(
            detection_callback=self._on_device_detected,
            scanning_mode=self.config['scan_mode']
        )
        
        await self.scanner.start()
        
    async def stop_scanning(self):
        """Stop BLE scanning"""
        if self.scanner:
            await self.scanner.stop()
            
    def _on_device_detected(self, device, advertisement_data):
        """Process detected BLE device"""
        # Check if device is advertising Remote ID
        if self._is_remote_id_advertisement(advertisement_data):
            rid_data = self._decode_remote_id(advertisement_data)
            if rid_data:
                self._process_remote_id(device.address, rid_data, device.rssi)
                
    def _is_remote_id_advertisement(self, adv_data):
        """Check if advertisement contains Remote ID data"""
        # ASTM F3411-22 UUID: 0xFFFA
        for uuid, data in adv_data.service_data.items():
            if uuid == "0000fffa-0000-1000-8000-00805f9b34fb":
                return True
        return False
        
    def _decode_remote_id(self, adv_data):
        """Decode Remote ID message from advertisement"""
        for uuid, data in adv_data.service_data.items():
            if uuid == "0000fffa-0000-1000-8000-00805f9b34fb":
                return self._parse_f3411_messages(data)
        return None
        
    def _parse_f3411_messages(self, data):
        """Parse ASTM F3411-22 messages"""
        messages = []
        offset = 0
        
        while offset < len(data):
            msg_type = data[offset]
            
            if msg_type == 0x00:  # Basic ID
                msg = BasicIDMessage.parse(data[offset:offset+25])
                messages.append(("basic_id", msg))
                offset += 25
                
            elif msg_type == 0x01:  # Location
                msg = LocationMessage.parse(data[offset:offset+19])
                messages.append(("location", msg))
                offset += 19
                
            elif msg_type == 0x02:  # Auth
                # Authentication message
                offset += len(data) - offset
                
            elif msg_type == 0x03:  # Self ID
                # System information
                offset += 24
                
            elif msg_type == 0x04:  # System
                offset += 28
                
            else:
                break
                
        return messages
Wi-Fi Beacon Decoding
python
# infrastructure/remote_id/wifi_decoder.py
"""Wi-Fi Remote ID beacon decoder"""

import asyncio
from scapy.all import *
from scapy.layers.dot11 import Dot11, Dot11Beacon, Dot11ProbeResp

class WiFiRemoteIDDecoder:
    """Wi-Fi Remote ID beacon decoder"""
    
    def __init__(self, interface="wlan0"):
        self.interface = interface
        self.known_drones = {}
        
    async def start_scanning(self):
        """Start Wi-Fi monitor mode scanning"""
        # Set interface to monitor mode
        os.system(f"sudo ip link set {self.interface} down")
        os.system(f"sudo iw dev {self.interface} set type monitor")
        os.system(f"sudo ip link set {self.interface} up")
        
        # Start packet capture
        self.sniffer = AsyncSniffer(
            iface=self.interface,
            prn=self._packet_handler,
            store=False
        )
        self.sniffer.start()
        
    def _packet_handler(self, packet):
        """Process captured Wi-Fi packet"""
        if packet.haslayer(Dot11):
            # Check for Remote ID vendor-specific IE
            if self._has_remote_id_ie(packet):
                rid_data = self._extract_remote_id(packet)
                if rid_data:
                    bssid = packet.addr2
                    rssi = packet.dBm_AntSignal if hasattr(packet, 'dBm_AntSignal') else -60
                    self._process_remote_id(bssid, rid_data, rssi)
                    
    def _has_remote_id_ie(self, packet):
        """Check for Remote ID Information Element"""
        if packet.haslayer(Dot11Beacon) or packet.haslayer(Dot11ProbeResp):
            # Look for vendor-specific IE with Remote ID OUI
            # OUI: 0x8C, 0xDE, 0xF6 (AUVSI)
            for ie in packet[Dot11].info:
                if len(ie) > 4 and ie[0] == 0xDD:  # Vendor specific
                    oui = ie[1:4]
                    if oui == b'\x8C\xDE\xF6':  # AUVSI OUI
                        return True
        return False
        
    def _extract_remote_id(self, packet):
        """Extract Remote ID data from beacon"""
        rid_data = {}
        
        # Check for RID in beacon frame
        if packet.haslayer(Dot11Beacon):
            beacon = packet[Dot11Beacon]
            
            # Parse IE data
            for ie in beacon.info:
                if ie[0] == 0xDD and len(ie) > 4:  # Vendor specific
                    oui = ie[1:4]
                    if oui == b'\x8C\xDE\xF6':  # AUVSI OUI
                        # Parse Remote ID data
                        rid_type = ie[4]
                        payload = ie[5:]
                        
                        if rid_type == 0x01:  # Basic ID
                            rid_data['basic_id'] = self._parse_basic_id(payload)
                        elif rid_type == 0x02:  # Location
                            rid_data['location'] = self._parse_location(payload)
                        elif rid_type == 0x03:  # Auth
                            rid_data['auth'] = payload
                            
        return rid_data
Remote ID Processing
python
# infrastructure/remote_id/processor.py
"""Remote ID message processor"""

class RemoteIDProcessor:
    """Main Remote ID processing engine"""
    
    def __init__(self, config):
        self.config = config
        self.ble_decoder = BLERemoteIDDecoder(config['bluetooth'])
        self.wifi_decoder = WiFiRemoteIDDecoder(config['wifi']['interface'])
        self.database = RemoteIDDatabase()
        self.fusion_engine = DataFusionEngine()
        
    async def start(self):
        """Start all RID scanners"""
        tasks = []
        
        if self.config['bluetooth']['enabled']:
            tasks.append(self.ble_decoder.start_scanning())
            
        if self.config['wifi']['enabled']:
            tasks.append(self.wifi_decoder.start_scanning())
            
        await asyncio.gather(*tasks)
        
    async def process_remote_id(self, device_id, rid_messages, rssi, scanner_id):
        """Process incoming Remote ID data"""
        
        # Parse messages
        drone_info = self._parse_remote_id_messages(rid_messages)
        drone_info['device_id'] = device_id
        drone_info['rssi'] = rssi
        drone_info['scanner_id'] = scanner_id
        drone_info['timestamp'] = datetime.utcnow()
        
        # Add position estimate from RSSI
        if 'location' in drone_info:
            drone_info['position'] = self._estimate_position(
                drone_info['location'], rssi, scanner_id
            )
            
        # Store in database
        await self.database.store_remote_id(drone_info)
        
        # Correlate with RF detection
        if self.config['integration']['correlate_with_rf']:
            await self._correlate_with_rf_detection(drone_info)
            
        # Check alerts
        await self._check_alerts(drone_info)
        
        return drone_info
        
    def _estimate_position(self, location_data, rssi, scanner_id):
        """Estimate drone position from RSSI and scanner location"""
        scanner_pos = self._get_scanner_location(scanner_id)
        
        # Estimate distance from RSSI (simplified)
        # distance = 10^((tx_power - rssi) / (10 * n))
        tx_power = -45  # Typical BLE TX power
        n = 2.0  # Path loss exponent (free space)
        
        distance = 10 ** ((tx_power - rssi) / (10 * n))
        
        # Apply trilateration if multiple scanners
        positions = self._get_multilateration(device_id)
        
        return {
            'latitude': location_data.get('latitude', scanner_pos['latitude']),
            'longitude': location_data.get('longitude', scanner_pos['longitude']),
            'altitude': location_data.get('altitude', 0),
            'accuracy': distance,
            'source': 'remote_id'
        }
Remote ID Database
Database Schema
sql
-- Remote ID database tables
CREATE TABLE remote_id_drones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    uas_id VARCHAR(20) UNIQUE NOT NULL,
    serial_number VARCHAR(50),
    operator_id VARCHAR(50),
    manufacturer VARCHAR(100),
    model VARCHAR(100),
    category INTEGER,
    class INTEGER,
    first_seen TIMESTAMP WITH TIME ZONE,
    last_seen TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE remote_id_positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    drone_id UUID REFERENCES remote_id_drones(id),
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    altitude_baro DOUBLE PRECISION,
    altitude_geo DOUBLE PRECISION,
    heading DOUBLE PRECISION,
    speed_horizontal DOUBLE PRECISION,
    speed_vertical DOUBLE PRECISION,
    accuracy INTEGER,
    rssi INTEGER,
    scanner_id VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE remote_id_operators (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100),
    registration_number VARCHAR(50),
    contact_email VARCHAR(100),
    contact_phone VARCHAR(20),
    authorized_zones JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE remote_id_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    drone_id UUID REFERENCES remote_id_drones(id),
    alert_type VARCHAR(50),
    severity VARCHAR(20),
    message TEXT,
    acknowledged BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_rid_drones_uas_id ON remote_id_drones(uas_id);
CREATE INDEX idx_rid_positions_drone_time ON remote_id_positions(drone_id, timestamp);
CREATE INDEX idx_rid_positions_time ON remote_id_positions(timestamp);
CREATE INDEX idx_rid_alerts_drone ON remote_id_alerts(drone_id);
ORM Models
python
# infrastructure/storage/remote_id_models.py
from sqlalchemy import Column, String, Integer, Float, DateTime, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

class RemoteIDDrone(Base):
    __tablename__ = 'remote_id_drones'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    uas_id = Column(String(20), unique=True, nullable=False)
    serial_number = Column(String(50))
    operator_id = Column(String(50))
    manufacturer = Column(String(100))
    model = Column(String(100))
    category = Column(Integer)
    class_type = Column(Integer)
    first_seen = Column(DateTime(timezone=True))
    last_seen = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    positions = relationship("RemoteIDPosition", back_populates="drone")
    alerts = relationship("RemoteIDAlert", back_populates="drone")
    
class RemoteIDPosition(Base):
    __tablename__ = 'remote_id_positions'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    drone_id = Column(UUID(as_uuid=True), ForeignKey('remote_id_drones.id'))
    timestamp = Column(DateTime(timezone=True), nullable=False)
    latitude = Column(Float)
    longitude = Column(Float)
    altitude_baro = Column(Float)
    altitude_geo = Column(Float)
    heading = Column(Float)
    speed_horizontal = Column(Float)
    speed_vertical = Column(Float)
    accuracy = Column(Integer)
    rssi = Column(Integer)
    scanner_id = Column(String(50))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    drone = relationship("RemoteIDDrone", back_populates="positions")
Integration with Detection System
RF and RID Correlation
python
# domain/services/rid_integration.py
"""Integration between RF detection and Remote ID"""

class RIDCorrelationEngine:
    """Correlates RF detections with Remote ID"""
    
    def __init__(self, correlation_window_ms=500):
        self.correlation_window = correlation_window_ms / 1000
        self.rf_detections = []
        self.rid_messages = []
        
    async def correlate(self, rf_detection):
        """Correlate RF detection with recent RID messages"""
        matches = []
        
        # Find RID messages within time window
        for rid in self.rid_messages:
            time_diff = abs(rf_detection.timestamp - rid.timestamp)
            
            if time_diff < self.correlation_window:
                # Check frequency correlation
                freq_match = self._check_frequency_match(rf_detection, rid)
                
                # Check position correlation
                pos_match = self._check_position_match(rf_detection, rid)
                
                correlation_score = (freq_match + pos_match) / 2
                
                if correlation_score > 0.7:
                    matches.append({
                        'rid': rid,
                        'score': correlation_score
                    })
                    
        # Best match
        if matches:
            best_match = max(matches, key=lambda x: x['score'])
            return self._merge_detections(rf_detection, best_match['rid'])
            
        return rf_detection
        
    def _check_frequency_match(self, rf_detection, rid):
        """Check if frequency matches known RID bands"""
        rid_bands = {
            'ble': 2.402e9,
            'ble_38': 2.426e9,
            'ble_39': 2.480e9,
            'wifi_24': 2.412e9,
            'wifi_5': 5.180e9
        }
        
        min_diff = min(abs(rf_detection.frequency - band) 
                      for band in rid_bands.values())
        
        return 1.0 if min_diff < 10e6 else 0.0
        
    def _check_position_match(self, rf_detection, rid):
        """Check if positions match within tolerance"""
        if not rid.position or not rf_detection.position:
            return 0.5
            
        # Calculate great-circle distance
        distance = haversine_distance(
            rf_detection.position.latitude,
            rf_detection.position.longitude,
            rid.position.latitude,
            rid.position.longitude
        )
        
        # Convert to similarity score
        max_distance = 1000  # meters
        score = max(0, 1 - (distance / max_distance))
        
        return score
Enhanced Detection with RID
python
class EnhancedDetectionService:
    """Detection service enhanced with Remote ID"""
    
    async def process_detection(self, rf_detection):
        """Process detection with Remote ID enrichment"""
        
        # Check for related Remote ID
        rid_match = await self.rid_correlation.correlate(rf_detection)
        
        if rid_match:
            # Enhance detection with RID data
            detection = DetectionEvent(
                drone_type=rid_match.drone_type or rf_detection.drone_type,
                confidence=min(1.0, rf_detection.confidence + 0.2),
                position=rid_match.position or rf_detection.position,
                remote_id_data=rid_match.remote_id_data,
                threat_level=self._assess_threat_with_rid(rid_match),
                operator_info=rid_match.operator_info
            )
        else:
            # No RID, use RF detection only
            detection = rf_detection
            
            # Alert if drone lacks Remote ID (if configured)
            if self.config['alerts']['no_remote_id']:
                await self.alert_system.send_alert(
                    type="no_remote_id",
                    detection=detection,
                    severity="medium"
                )
                
        return detection
API Endpoints
Remote ID API
bash
# Get Remote ID information for a drone
curl http://localhost:8888/api/v1/remote-id/drone/DJI-123456

# Response
{
  "uas_id": "DJI-123456",
  "serial_number": "1A2B3C4D5E6F",
  "operator_id": "OP-78901",
  "manufacturer": "DJI",
  "model": "Mavic 3",
  "category": 2,
  "class": 3,
  "last_position": {
    "latitude": 37.7749,
    "longitude": -122.4194,
    "altitude": 120.5,
    "timestamp": "2024-01-01T00:00:00Z"
  },
  "history": []
}

# Query Remote ID drones by operator
curl "http://localhost:8888/api/v1/remote-id/operator/OP-78901"

# Get Remote ID statistics
curl http://localhost:8888/api/v1/remote-id/stats

# Response
{
  "total_drones_seen": 124,
  "drones_with_rid": 95,
  "drones_without_rid": 29,
  "rid_coverage_percent": 76.6,
  "top_manufacturers": {
    "DJI": 67,
    "Autel": 12,
    "Skydio": 8,
    "Other": 8
  },
  "last_hour_detections": 12
}

# Export Remote ID data
curl -X POST http://localhost:8888/api/v1/remote-id/export \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2024-01-01T00:00:00Z",
    "end_date": "2024-01-31T23:59:59Z",
    "format": "csv",
    "include_positions": true
  }'
Alert Rules
Remote ID Alert Configuration
yaml
# config/remote_id_alerts.yaml
alerts:
  # No Remote ID detected
  no_remote_id:
    enabled: true
    severity: "medium"
    message: "Drone detected without Remote ID at {location}"
    cooldown: 300  # seconds
    
  # Unauthorized operator
  unauthorized_operator:
    enabled: true
    severity: "high"
    message: "Unauthorized operator {operator_id} operating drone {uas_id}"
    authorized_operators_db: "postgres"
    
  # Suspicious ID format
  suspicious_id:
    enabled: true
    severity: "high"
    message: "Suspicious Remote ID format {uas_id}"
    pattern_matching: true
    
  # Location outside authorized zone
  location_violation:
    enabled: true
    severity: "critical"
    message: "Drone {uas_id} operating outside authorized zone"
    geofencing_enabled: true
    
  # Spoofing detection
  spoofing_detected:
    enabled: true
    severity: "critical"
    message: "Possible Remote ID spoofing detected"
    detection_method: "multi_scanner_correlation"
    
  # Operator not registered
  operator_not_registered:
    enabled: true
    severity: "high"
    message: "Operator {operator_id} not in registered database"
    check_registration: true
Privacy and Compliance
Data Retention Policies
python
class RemoteIDPrivacyManager:
    """Manage Remote ID data privacy and compliance"""
    
    def __init__(self):
        self.retention_policies = {
            'positions': 90,  # days
            'identifiable_data': 30,  # days
            'operator_info': 365,  # days
            'alerts': 730  # days
        }
        
    async def apply_retention_policies(self):
        """Apply data retention policies"""
        for data_type, days in self.retention_policies.items():
            cutoff = datetime.utcnow() - timedelta(days=days)
            
            if data_type == 'positions':
                await self.database.delete_old_positions(cutoff)
            elif data_type == 'identifiable_data':
                await self.anonymize_old_data(cutoff)
                
    async def anonymize_data(self, drone_id):
        """Anonymize Remote ID data"""
        await self.database.update_drone(
            drone_id,
            serial_number=None,
            operator_id=None,
            anonymized=True
        )
        
    def check_compliance(self, region):
        """Check compliance with regional regulations"""
        # GDPR (Europe)
        if region == 'EU':
            return {
                'requires_consent': True,
                'retention_max_days': 30,
                'right_to_be_forgotten': True
            }
        # FAA (USA)
        elif region == 'US':
            return {
                'requires_consent': False,
                'retention_max_days': 365,
                'right_to_be_forgotten': False
            }
        # Add other regions...
Testing Remote ID
Mock Remote ID Generator
python
# tests/mock_remote_id.py
class MockRemoteIDGenerator:
    """Generate test Remote ID data"""
    
    def generate_basic_id(self):
        """Generate mock Basic ID message"""
        return {
            'msg_type': 0x00,
            'id_type': 0x00,  # Serial number
            'ua_type': 0x01,  # Drone
            'uas_id': f"DRONE_{random.randint(10000, 99999)}"
        }
        
    def generate_location(self, lat, lon, alt):
        """Generate mock location message"""
        return {
            'msg_type': 0x01,
            'status': 0x00,  # Airborne
            'direction': 0x00,
            'latitude': int(lat * 1e7),
            'longitude': int(lon * 1e7),
            'altitude_baro': int(alt),
            'altitude_geo': int(alt),
            'heading': random.randint(0, 360),
            'speed_horiz': random.randint(0, 1000),
            'speed_vert': random.randint(-100, 100),
            'timestamp': int(datetime.utcnow().timestamp())
        }
Integration Tests
python
# tests/integration/test_remote_id.py
import pytest
from infrastructure.remote_id.processor import RemoteIDProcessor

@pytest.mark.asyncio
async def test_remote_id_decoding():
    """Test Remote ID message decoding"""
    
    # Create mock BLE advertisement
    mock_adv = create_mock_rid_advertisement()
    
    # Process with decoder
    decoder = BLERemoteIDDecoder(config)
    result = decoder._decode_remote_id(mock_adv)
    
    # Assertions
    assert result is not None
    assert len(result) > 0
    assert result[0][0] == "basic_id"
    
@pytest.mark.asyncio
async def test_rf_rid_correlation():
    """Test correlation between RF and RID"""
    
    # Create RF detection
    rf_detection = create_mock_rf_detection(
        frequency=2.45e9,
        position={"lat": 37.7749, "lon": -122.4194}
    )
    
    # Create RID message
    rid_message = create_mock_rid_message(
        uas_id="TEST-123",
        position={"lat": 37.7749, "lon": -122.4194},
        timestamp=rf_detection.timestamp + 0.1
    )
    
    # Correlate
    correlation_engine = RIDCorrelationEngine()
    result = await correlation_engine.correlate(rf_detection)
    
    assert result.remote_id_data is not None
    assert result.remote_id_data['uas_id'] == "TEST-123"
    assert result.confidence > 0.8
Troubleshooting
Common Issues
bash
# Issue: Bluetooth adapter not found
hciconfig -a
sudo hciconfig hci0 up
rfkill unblock bluetooth

# Issue: Permission denied for Bluetooth
sudo adduser $USER bluetooth
sudo usermod -a -G bluetooth $USER

# Issue: Wi-Fi monitor mode fails
sudo airmon-ng check kill
sudo iwconfig wlan0 mode monitor
sudo ip link set wlan0 up

# Issue: No Remote ID messages received
# Check signal strength
hcitool cc  # BLE scan test
sudo airodump-ng wlan0  # Wi-Fi scan test

# Issue: Database connection
sudo systemctl status postgresql
psql -U drone_user -d drone_detector -c "SELECT 1"

# Issue: Correlations not working
# Check time synchronization between scanners
ntpq -p
timedatectl status
Diagnostic Tools
bash
# Remote ID diagnostic script
python scripts/diagnose_remote_id.py

# Output:
# ✓ Bluetooth adapter: hci0 (UP)
# ✓ Wi-Fi interface: wlan0 (MONITOR mode)
# ✓ Remote ID database: Connected
# ✓ Scanners: 3 active
#   - scanner_01: 127 detections (last 5min)
#   - scanner_02: 98 detections (last 5min)
#   - scanner_03: 112 detections (last 5min)
# ✗ Correlation engine: Delayed (287ms avg)
#   - Suggestion: Reduce correlation_window_ms

# View Remote ID statistics
python scripts/rid_stats.py --days 7
Performance Metrics
Monitoring Remote ID Performance
python
# Prometheus metrics for Remote ID
from prometheus_client import Counter, Histogram, Gauge

rid_detections_total = Counter(
    'rid_detections_total',
    'Total Remote ID detections',
    ['scanner', 'protocol']
)

rid_processing_latency = Histogram(
    'rid_processing_latency_seconds',
    'Remote ID processing latency',
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0]
)

rid_active_drones = Gauge(
    'rid_active_drones',
    'Currently active Remote ID drones'
)

rid_correlation_matches = Counter(
    'rid_correlation_matches_total',
    'Successful RF-RID correlations'
)
Future Enhancements
Planned Features
yaml
# Future Remote ID capabilities
roadmap:
  Q1_2025:
    - LTE-based Remote ID support
    - Improved multilateration for position
    - Blockchain-based authentication
    
  Q2_2025:
    - Real-time operator verification
    - Automated compliance reporting
    - Integration with FAA/CAAC databases
    
  Q3_2025:
    - Encrypted Remote ID decryption
    - AI-based spoofing detection
    - Historical pattern analysis
    
  Q4_2025:
    - Networked RID aggregation
    - Cross-jurisdiction handoff
    - Virtual geofencing based on RID
This Remote ID integration guide provides comprehensive documentation for incorporating Remote ID capabilities into the Drone Detector system, enabling identification and tracking of compliant drones through both Bluetooth and Wi-Fi protocols.
