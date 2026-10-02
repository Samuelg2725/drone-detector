import struct
import time
from dataclasses import dataclass
from typing import Optional

@dataclass
class RemoteIDMessage:
    """Decoded Remote ID telemetry"""
    uas_id: str           # Drone serial/ID
    latitude: float
    longitude: float
    altitude: float       # meters
    speed: float          # m/s
    heading: float        # degrees
    timestamp: float
    rssi: int

class OpenDroneIDDecoder:
    """Decode ASTM F3411 Remote ID broadcasts from 2.4 GHz"""
    
    # BLE advertising channel frequencies (MHz)
    BLE_CHANNELS = [2402, 2426, 2480]
    
    def decode_ble_frame(self, raw_bytes: bytes) -> Optional[RemoteIDMessage]:
        """Parse BLE advertising packet containing Remote ID"""
        # Check for OpenDroneID service UUID
        # Actual implementation would parse the message structure per ASTM F3411
        # This is a simplified example
        
        if len(raw_bytes) < 30:
            return None
        
        # Extract latitude (4 bytes, signed int, scale 1e-7)
        lat_raw = struct.unpack('<i', raw_bytes[10:14])[0]
        lon_raw = struct.unpack('<i', raw_bytes[14:18])[0]
        
        return RemoteIDMessage(
            uas_id=raw_bytes[20:40].decode('ascii', errors='ignore'),
            latitude=lat_raw * 1e-7,
            longitude=lon_raw * 1e-7,
            altitude=struct.unpack('<H', raw_bytes[18:20])[0],
            speed=0.0,
            heading=0.0,
            timestamp=time.time(),
            rssi=0
        )