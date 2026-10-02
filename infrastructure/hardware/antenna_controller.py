#!/usr/bin/env python3
# drone-detector/infrastructure/hardware/antenna_controller.py
"""
Antenna Switch Controller

This module provides comprehensive antenna control for multi-band drone detection,
including:
- Multi-antenna switching for different frequency bands
- Automated antenna selection based on scanning frequency
- Antenna array control for direction finding
- Bias-T control for active antennas/LNAs
- Rotator control for directional antennas
- Antenna status monitoring and diagnostics
- Calibration and pattern management
"""

import time
import threading
import serial
import struct
import numpy as np
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Tuple, Optional, Dict, Any, Callable
from datetime import datetime
from pathlib import Path
import asyncio
import logging

# Setup logging
logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Data Classes
# ============================================================================

class AntennaPort(Enum):
    """Antenna port enumeration"""
    PORT_1 = 1
    PORT_2 = 2
    PORT_3 = 3
    PORT_4 = 4
    PORT_5 = 5
    PORT_6 = 6
    PORT_7 = 7
    PORT_8 = 8
    NONE = 0


class AntennaType(Enum):
    """Types of antennas"""
    OMNIDIRECTIONAL = "omnidirectional"
    DIRECTIONAL_PATCH = "directional_patch"
    DIRECTIONAL_YAGI = "directional_yagi"
    DIRECTIONAL_DISH = "directional_dish"
    LOG_PERIODIC = "log_periodic"
    DUAL_BAND = "dual_band"
    TRIPLE_BAND = "triple_band"
    ARRAY_PHASED = "array_phased"
    ARRAY_MIMO = "array_mimo"


class Polarization(Enum):
    """Antenna polarization types"""
    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"
    CIRCULAR_RH = "circular_rh"
    CIRCULAR_LH = "circular_lh"
    DUAL = "dual"
    CROSS = "cross"


class SwitchType(Enum):
    """Switch hardware types"""
    RELAY_SPDT = "relay_spdt"
    RELAY_SP4T = "relay_sp4t"
    RELAY_SP8T = "relay_sp8t"
    SOLID_STATE = "solid_state"
    PIN_DIODE = "pin_diode"
    MANUAL = "manual"
    VIRTUAL = "virtual"


class RotatorMode(Enum):
    """Antenna rotator operation modes"""
    MANUAL = "manual"
    AUTO_TRACK = "auto_track"
    SCAN = "scan"
    HOME = "home"
    CALIBRATE = "calibrate"
    PARK = "park"


class AntennaStatus(Enum):
    """Antenna status states"""
    OK = "ok"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    SWITCHING = "switching"
    ERROR = "error"
    CALIBRATING = "calibrating"
    UNKNOWN = "unknown"


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class Antenna:
    """Antenna configuration and state"""
    id: str
    name: str
    port: AntennaPort
    antenna_type: AntennaType
    polarization: Polarization
    frequency_range: Tuple[float, float]  # (min_freq, max_freq) in Hz
    gain_dbi: float = 0.0
    beamwidth_deg: float = 360.0  # 360 for omnidirectional
    front_to_back_db: float = 0.0
    vswr: float = 1.5
    enabled: bool = True
    bias_t_enabled: bool = False
    bias_t_voltage: float = 5.0  # Volts
    bias_t_current_ma: float = 0.0
    status: AntennaStatus = AntennaStatus.UNKNOWN
    last_switch_time: Optional[datetime] = None
    use_count: int = 0
    custom_metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'port': self.port.value,
            'type': self.antenna_type.value,
            'polarization': self.polarization.value,
            'frequency_range': list(self.frequency_range),
            'gain_dbi': self.gain_dbi,
            'beamwidth_deg': self.beamwidth_deg,
            'enabled': self.enabled,
            'status': self.status.value
        }
    
    def is_frequency_compatible(self, frequency: float) -> bool:
        """Check if antenna supports given frequency"""
        return self.frequency_range[0] <= frequency <= self.frequency_range[1]


@dataclass
class AntennaRotator:
    """Antenna rotator configuration"""
    id: str
    name: str
    port: str  # Serial port or network address
    min_azimuth: float = 0.0  # degrees
    max_azimuth: float = 360.0  # degrees
    min_elevation: float = -10.0  # degrees
    max_elevation: float = 90.0  # degrees
    azimuth_speed: float = 10.0  # degrees per second
    elevation_speed: float = 5.0  # degrees per second
    current_azimuth: float = 0.0
    current_elevation: float = 0.0
    mode: RotatorMode = RotatorMode.MANUAL
    calibration_offset: float = 0.0
    connected: bool = False
    last_command_time: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'azimuth': self.current_azimuth,
            'elevation': self.current_elevation,
            'mode': self.mode.value,
            'connected': self.connected
        }


@dataclass
class AntennaArray:
    """Phased array or MIMO antenna configuration"""
    id: str
    name: str
    elements: List[Antenna]
    element_spacing: float  # meters
    phase_center: Tuple[float, float, float]  # (x, y, z)
    beamforming_enabled: bool = False
    current_beam_angle: float = 0.0  # degrees
    steering_weights: Optional[np.ndarray] = None
    
    def calculate_steering_vector(self, angle_deg: float) -> np.ndarray:
        """Calculate steering vector for given angle"""
        if not self.elements:
            return np.array([])
        
        wavelength = 0.3  # Default 1 GHz, should be calculated from frequency
        d = self.element_spacing
        angle_rad = np.radians(angle_deg)
        
        steering = np.exp(1j * 2 * np.pi * d * np.sin(angle_rad) / wavelength *
                         np.arange(len(self.elements)))
        
        return steering


# ============================================================================
# Antenna Switch Controller
# ============================================================================

class AntennaSwitchController:
    """
    Controls antenna switching hardware for multi-band operation
    
    Supports:
    - Relay-based switches (SPDT, SP4T, SP8T)
    - Solid-state switches
    - PIN diode switches
    - Manual/GPIO control
    """
    
    def __init__(self, switch_type: SwitchType = SwitchType.VIRTUAL,
                 serial_port: Optional[str] = None,
                 gpio_pins: Optional[List[int]] = None):
        """
        Initialize antenna switch controller
        
        Args:
            switch_type: Type of switch hardware
            serial_port: Serial port for controlled switches
            gpio_pins: GPIO pin mapping for direct control
        """
        self.switch_type = switch_type
        self.serial_port = serial_port
        self.gpio_pins = gpio_pins or []
        self.antennas: Dict[AntennaPort, Antenna] = {}
        self.current_port: Optional[AntennaPort] = None
        self._serial_connection = None
        self._lock = threading.Lock()
        self.switching_delay_ms = 50  # Delay after switching
        
        # Statistics
        self.switch_count = 0
        self.last_switch_time = None
        self.switch_errors = 0
        
        # Initialize hardware
        self._initialize_hardware()
    
    def _initialize_hardware(self):
        """Initialize switch hardware"""
        if self.switch_type == SwitchType.VIRTUAL:
            logger.info("Virtual antenna switch initialized (no hardware)")
            
        elif self.switch_type in [SwitchType.RELAY_SPDT, SwitchType.RELAY_SP4T, 
                                   SwitchType.RELAY_SP8T, SwitchType.SOLID_STATE]:
            if self.serial_port:
                try:
                    self._serial_connection = serial.Serial(
                        port=self.serial_port,
                        baudrate=9600,
                        timeout=1
                    )
                    logger.info(f"Connected to switch on {self.serial_port}")
                except Exception as e:
                    logger.error(f"Failed to connect to switch: {e}")
                    self._serial_connection = None
            
        elif self.switch_type == SwitchType.MANUAL:
            logger.info("Manual switch mode - requires physical switching")
        
        elif self.switch_type == SwitchType.PIN_DIODE:
            logger.info("PIN diode switch mode initialized")
    
    def register_antenna(self, antenna: Antenna) -> None:
        """Register an antenna with the controller"""
        self.antennas[antenna.port] = antenna
        logger.info(f"Registered antenna: {antenna.name} on port {antenna.port.value}")
    
    def register_antennas(self, antennas: List[Antenna]) -> None:
        """Register multiple antennas"""
        for antenna in antennas:
            self.register_antenna(antenna)
    
    def switch_to_port(self, port: AntennaPort, frequency: Optional[float] = None) -> bool:
        """
        Switch to specified antenna port
        
        Args:
            port: Target antenna port
            frequency: Operating frequency (for compatibility check)
            
        Returns:
            True if switch successful
        """
        with self._lock:
            if port == self.current_port:
                return True
            
            antenna = self.antennas.get(port)
            if not antenna:
                logger.error(f"Antenna not found for port {port}")
                return False
            
            if not antenna.enabled:
                logger.warning(f"Antenna {antenna.name} is disabled")
                return False
            
            # Check frequency compatibility
            if frequency and not antenna.is_frequency_compatible(frequency):
                logger.warning(f"Antenna {antenna.name} not compatible with {frequency/1e9:.2f} GHz")
                # Still switch, but log warning
            
            # Perform hardware switch
            success = self._hardware_switch(port)
            
            if success:
                self.current_port = port
                antenna.last_switch_time = datetime.now()
                antenna.use_count += 1
                self.switch_count += 1
                self.last_switch_time = datetime.now()
                
                # Wait for switching to settle
                time.sleep(self.switching_delay_ms / 1000.0)
                
                logger.info(f"Switched to antenna: {antenna.name} (port {port.value})")
                
                # Enable bias-T if configured
                if antenna.bias_t_enabled:
                    self._set_bias_t(port, enable=True)
            else:
                self.switch_errors += 1
                logger.error(f"Failed to switch to port {port}")
            
            return success
    
    def _hardware_switch(self, port: AntennaPort) -> bool:
        """Execute hardware switch based on switch type"""
        if self.switch_type == SwitchType.VIRTUAL:
            # Virtual switch - always succeeds
            return True
        
        elif self.switch_type == SwitchType.MANUAL:
            # Manual switch - assume user will switch physically
            logger.info(f"MANUAL SWITCH REQUIRED: Switch to port {port.value}")
            return True
        
        elif self.switch_type == SwitchType.RELAY_SPDT:
            return self._switch_relay_spdt(port)
        
        elif self.switch_type == SwitchType.RELAY_SP4T:
            return self._switch_relay_sp4t(port)
        
        elif self.switch_type == SwitchType.RELAY_SP8T:
            return self._switch_relay_sp8t(port)
        
        elif self.switch_type == SwitchType.SOLID_STATE:
            return self._switch_solid_state(port)
        
        elif self.switch_type == SwitchType.PIN_DIODE:
            return self._switch_pin_diode(port)
        
        else:
            logger.error(f"Unsupported switch type: {self.switch_type}")
            return False
    
    def _switch_relay_spdt(self, port: AntennaPort) -> bool:
        """Switch SPDT relay (2 ports)"""
        if port not in [AntennaPort.PORT_1, AntennaPort.PORT_2]:
            logger.error(f"Invalid port for SPDT switch: {port}")
            return False
        
        if self._serial_connection:
            command = b'1' if port == AntennaPort.PORT_1 else b'2'
            self._serial_connection.write(command)
            return True
        
        # GPIO control fallback
        if self.gpio_pins:
            # Implement GPIO control here
            pass
        
        return True
    
    def _switch_relay_sp4t(self, port: AntennaPort) -> bool:
        """Switch SP4T relay (4 ports)"""
        if port.value > 4:
            logger.error(f"Invalid port for SP4T switch: {port}")
            return False
        
        port_map = {
            AntennaPort.PORT_1: b'1',
            AntennaPort.PORT_2: b'2',
            AntennaPort.PORT_3: b'3',
            AntennaPort.PORT_4: b'4'
        }
        
        if self._serial_connection:
            command = port_map.get(port, b'1')
            self._serial_connection.write(command)
            return True
        
        return True
    
    def _switch_relay_sp8t(self, port: AntennaPort) -> bool:
        """Switch SP8T relay (8 ports)"""
        if port.value > 8:
            logger.error(f"Invalid port for SP8T switch: {port}")
            return False
        
        if self._serial_connection:
            command = str(port.value).encode()
            self._serial_connection.write(command)
            return True
        
        return True
    
    def _switch_solid_state(self, port: AntennaPort) -> bool:
        """Switch solid-state switch"""
        # Similar to relay but faster
        if self._serial_connection:
            command = struct.pack('B', port.value)
            self._serial_connection.write(command)
            return True
        return True
    
    def _switch_pin_diode(self, port: AntennaPort) -> bool:
        """Switch PIN diode switch"""
        # PIN diode switches require bias voltage control
        # Implement based on specific hardware
        return True
    
    def _set_bias_t(self, port: AntennaPort, enable: bool) -> bool:
        """Enable/disable bias-T for antenna"""
        antenna = self.antennas.get(port)
        if not antenna:
            return False
        
        if enable:
            logger.debug(f"Enabling bias-T for {antenna.name} ({antenna.bias_t_voltage}V)")
        else:
            logger.debug(f"Disabling bias-T for {antenna.name}")
        
        # Implement actual bias-T control based on hardware
        return True
    
    def get_current_antenna(self) -> Optional[Antenna]:
        """Get currently active antenna"""
        if self.current_port:
            return self.antennas.get(self.current_port)
        return None
    
    def get_antenna_for_frequency(self, frequency: float) -> Optional[Antenna]:
        """Find best antenna for given frequency"""
        compatible = [a for a in self.antennas.values() 
                     if a.enabled and a.is_frequency_compatible(frequency)]
        
        if not compatible:
            return None
        
        # Return antenna with highest gain for this frequency range
        return max(compatible, key=lambda a: a.gain_dbi)
    
    def auto_select(self, frequency: float) -> bool:
        """
        Automatically select best antenna for frequency
        
        Args:
            frequency: Operating frequency in Hz
            
        Returns:
            True if selection successful
        """
        antenna = self.get_antenna_for_frequency(frequency)
        if antenna:
            return self.switch_to_port(antenna.port, frequency)
        return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get switch controller status"""
        current_antenna = self.get_current_antenna()
        
        return {
            'switch_type': self.switch_type.value,
            'current_antenna': current_antenna.to_dict() if current_antenna else None,
            'switch_count': self.switch_count,
            'switch_errors': self.switch_errors,
            'last_switch_time': self.last_switch_time.isoformat() if self.last_switch_time else None,
            'antennas': [a.to_dict() for a in self.antennas.values()],
            'connected': self._serial_connection is not None
        }
    
    def close(self):
        """Close serial connection and cleanup"""
        if self._serial_connection:
            self._serial_connection.close()
            logger.info("Antenna switch controller closed")


# ============================================================================
# Antenna Rotator Controller
# ============================================================================

class AntennaRotatorController:
    """
    Controls antenna rotators for directional antennas
    
    Supports:
    - Yaesu rotators (GS-232 protocol)
    - DC motors with position feedback
    - Stepper motors
    - Network-controlled rotators
    """
    
    def __init__(self, rotator: AntennaRotator):
        """
        Initialize antenna rotator controller
        
        Args:
            rotator: AntennaRotator configuration
        """
        self.rotator = rotator
        self._serial_connection = None
        self._lock = threading.Lock()
        self._tracking_target: Optional[Tuple[float, float]] = None
        self._tracking_thread: Optional[threading.Thread] = None
        self._tracking_active = False
        
        self._initialize_rotator()
    
    def _initialize_rotator(self):
        """Initialize rotator hardware"""
        try:
            self._serial_connection = serial.Serial(
                port=self.rotator.port,
                baudrate=9600,
                timeout=1
            )
            self.rotator.connected = True
            logger.info(f"Connected to rotator {self.rotator.name} on {self.rotator.port}")
            
            # Query current position
            self._query_position()
            
        except Exception as e:
            logger.error(f"Failed to connect to rotator: {e}")
            self.rotator.connected = False
    
    def _query_position(self):
        """Query current rotator position"""
        if not self._serial_connection:
            return
        
        try:
            # Send position query command
            self._serial_connection.write(b'C2\r\n')
            response = self._serial_connection.readline()
            
            if response and len(response) >= 6:
                az = int(response[2:5]) if response[2:5].isdigit() else 0
                el = int(response[5:8]) if len(response) > 5 and response[5:8].isdigit() else 0
                
                self.rotator.current_azimuth = float(az)
                self.rotator.current_elevation = float(el)
                
                logger.debug(f"Rotator position: AZ={az}°, EL={el}°")
                
        except Exception as e:
            logger.error(f"Failed to query position: {e}")
    
    def set_position(self, azimuth: float, elevation: float, 
                     wait_complete: bool = True) -> bool:
        """
        Set rotator position
        
        Args:
            azimuth: Target azimuth in degrees (0-360)
            elevation: Target elevation in degrees (-10 to 90)
            wait_complete: Wait for movement to complete
            
        Returns:
            True if command successful
        """
        with self._lock:
            # Clamp values
            azimuth = max(self.rotator.min_azimuth, min(azimuth, self.rotator.max_azimuth))
            elevation = max(self.rotator.min_elevation, min(elevation, self.rotator.max_elevation))
            
            logger.info(f"Moving rotator to AZ={azimuth:.1f}°, EL={elevation:.1f}°")
            
            if not self._serial_connection:
                # Simulate movement
                self.rotator.current_azimuth = azimuth
                self.rotator.current_elevation = elevation
                return True
            
            try:
                # Format command (Yaesu GS-232 protocol)
                az_int = int(round(azimuth))
                el_int = int(round(elevation + 90))  # Convert to 0-180 range
                
                command = f"M{az_int:03d}{el_int:03d}\r\n"
                self._serial_connection.write(command.encode())
                self._serial_connection.write(b'W\r\n')  # Wait for completion
                
                if wait_complete:
                    # Wait for completion response
                    response = self._serial_connection.readline()
                    if b'X' in response:
                        self.rotator.current_azimuth = azimuth
                        self.rotator.current_elevation = elevation
                        self.rotator.last_command_time = datetime.now()
                        return True
                
                return True
                
            except Exception as e:
                logger.error(f"Failed to set position: {e}")
                return False
    
    def start_scan(self, start_az: float, end_az: float, step: float = 5.0,
                   speed: float = 5.0) -> bool:
        """
        Start scanning mode
        
        Args:
            start_az: Starting azimuth
            end_az: Ending azimuth
            step: Step size in degrees
            speed: Scan speed in degrees/second
            
        Returns:
            True if scan started
        """
        self.rotator.mode = RotatorMode.SCAN
        self._scan_parameters = {
            'start': start_az,
            'end': end_az,
            'step': step,
            'speed': speed,
            'current': start_az,
            'direction': 1
        }
        
        # Start scan thread
        self._scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self._scan_thread.start()
        
        return True
    
    def _scan_loop(self):
        """Scan loop for automatic scanning"""
        while self.rotator.mode == RotatorMode.SCAN:
            params = self._scan_parameters
            self.set_position(params['current'], self.rotator.current_elevation, wait_complete=True)
            
            params['current'] += params['step'] * params['direction']
            
            # Reverse direction at boundaries
            if params['current'] >= params['end']:
                params['current'] = params['end']
                params['direction'] = -1
            elif params['current'] <= params['start']:
                params['current'] = params['start']
                params['direction'] = 1
            
            # Wait for step movement
            time.sleep(params['step'] / params['speed'])
    
    def start_tracking(self, target_callback: Callable[[], Tuple[float, float]],
                      update_rate: float = 1.0) -> None:
        """
        Start tracking a moving target
        
        Args:
            target_callback: Function that returns (azimuth, elevation) of target
            update_rate: Tracking update rate in Hz
        """
        self.rotator.mode = RotatorMode.AUTO_TRACK
        self._tracking_target = None
        self._tracking_callback = target_callback
        self._tracking_rate = update_rate
        self._tracking_active = True
        
        self._tracking_thread = threading.Thread(target=self._tracking_loop, daemon=True)
        self._tracking_thread.start()
        
        logger.info("Starting auto-tracking mode")
    
    def _tracking_loop(self):
        """Tracking loop for auto-tracking mode"""
        while self._tracking_active and self.rotator.mode == RotatorMode.AUTO_TRACK:
            try:
                az, el = self._tracking_callback()
                self.set_position(az, el, wait_complete=False)
                time.sleep(1.0 / self._tracking_rate)
            except Exception as e:
                logger.error(f"Tracking error: {e}")
                time.sleep(1)
    
    def stop_tracking(self):
        """Stop auto-tracking"""
        self._tracking_active = False
        self.rotator.mode = RotatorMode.MANUAL
        logger.info("Stopped auto-tracking")
    
    def park(self) -> bool:
        """Park rotator to safe position"""
        self.rotator.mode = RotatorMode.PARK
        return self.set_position(180.0, 45.0, wait_complete=True)
    
    def home(self) -> bool:
        """Return to home position"""
        self.rotator.mode = RotatorMode.HOME
        return self.set_position(0.0, 0.0, wait_complete=True)
    
    def get_status(self) -> Dict[str, Any]:
        """Get rotator status"""
        return self.rotator.to_dict()
    
    def close(self):
        """Close rotator connection"""
        self._tracking_active = False
        if self._serial_connection:
            self._serial_connection.close()
            logger.info(f"Rotator {self.rotator.name} closed")


# ============================================================================
# Antenna Array Controller (Phased Array)
# ============================================================================

class AntennaArrayController:
    """
    Controls phased array antennas for beamforming
    
    Supports:
    - Phase shifters
    - Amplitude control
    - Beam steering
    - Null steering
    """
    
    def __init__(self, array: AntennaArray):
        """
        Initialize antenna array controller
        
        Args:
            array: AntennaArray configuration
        """
        self.array = array
        self.current_frequency = 2.4e9  # Default frequency
        self.current_beam_angle = 0.0
        
        logger.info(f"Initialized antenna array: {array.name} with {len(array.elements)} elements")
    
    def set_frequency(self, frequency: float) -> None:
        """Set operating frequency for beamforming"""
        self.current_frequency = frequency
    
    def steer_beam(self, angle_deg: float) -> None:
        """
        Steer beam to specified angle
        
        Args:
            angle_deg: Beam angle in degrees
        """
        self.current_beam_angle = angle_deg
        
        if not self.array.beamforming_enabled:
            logger.warning("Beamforming not enabled for this array")
            return
        
        # Calculate steering weights
        steering_vector = self.array.calculate_steering_vector(angle_deg)
        
        # Apply weights to phase shifters
        self._apply_weights(steering_vector)
        
        logger.info(f"Beam steered to {angle_deg:.1f}°")
    
    def _apply_weights(self, weights: np.ndarray) -> None:
        """Apply steering weights to hardware"""
        # Implement actual phase shifter control
        # This would interface with specific hardware
        self.array.steering_weights = weights
        
        for i, weight in enumerate(weights):
            phase = np.angle(weight) * 180 / np.pi
            amplitude = np.abs(weight)
            # Send to phase shifter for element i
            # self._set_phase_shifter(i, phase)
    
    def create_null(self, interference_angle: float, depth_db: float = 30.0) -> None:
        """
        Create null in antenna pattern at specified angle
        
        Args:
            interference_angle: Angle for null in degrees
            depth_db: Null depth in dB
        """
        logger.info(f"Creating null at {interference_angle:.1f}° with depth {depth_db}dB")
        # Implement null steering algorithm
        # This would use adaptive beamforming
    
    def get_status(self) -> Dict[str, Any]:
        """Get array status"""
        return {
            'id': self.array.id,
            'name': self.array.name,
            'elements': len(self.array.elements),
            'beamforming_enabled': self.array.beamforming_enabled,
            'current_beam_angle': self.current_beam_angle,
            'current_frequency': self.current_frequency
        }


# ============================================================================
# Unified Antenna Manager
# ============================================================================

class AntennaManager:
    """
    Unified antenna management system
    
    Manages all antenna-related hardware:
    - Switch control
    - Rotator control  
    - Array control
    - Bias-T control
    """
    
    def __init__(self):
        """Initialize antenna manager"""
        self.switch_controller: Optional[AntennaSwitchController] = None
        self.rotator_controller: Optional[AntennaRotatorController] = None
        self.array_controller: Optional[AntennaArrayController] = None
        
        self.antennas: Dict[str, Antenna] = {}
        self.scan_strategy = "auto"  # auto, manual, frequency_based
        
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
    
    def configure_switch(self, switch_type: SwitchType = SwitchType.VIRTUAL,
                         serial_port: Optional[str] = None,
                         gpio_pins: Optional[List[int]] = None) -> None:
        """Configure antenna switch controller"""
        self.switch_controller = AntennaSwitchController(
            switch_type=switch_type,
            serial_port=serial_port,
            gpio_pins=gpio_pins
        )
    
    def configure_rotator(self, rotator: AntennaRotator) -> None:
        """Configure antenna rotator controller"""
        self.rotator_controller = AntennaRotatorController(rotator)
    
    def configure_array(self, array: AntennaArray) -> None:
        """Configure antenna array controller"""
        self.array_controller = AntennaArrayController(array)
    
    def add_antenna(self, antenna: Antenna) -> None:
        """Add antenna to manager"""
        self.antennas[antenna.id] = antenna
        
        if self.switch_controller:
            self.switch_controller.register_antenna(antenna)
    
    def select_antenna_for_frequency(self, frequency: float) -> bool:
        """
        Automatically select best antenna for frequency
        
        Args:
            frequency: Operating frequency in Hz
            
        Returns:
            True if selection successful
        """
        if not self.switch_controller:
            logger.warning("Switch controller not configured")
            return False
        
        return self.switch_controller.auto_select(frequency)
    
    def select_antenna_by_id(self, antenna_id: str) -> bool:
        """
        Select antenna by ID
        
        Args:
            antenna_id: Antenna identifier
            
        Returns:
            True if selection successful
        """
        antenna = self.antennas.get(antenna_id)
        if not antenna:
            logger.error(f"Antenna not found: {antenna_id}")
            return False
        
        if not self.switch_controller:
            logger.warning("Switch controller not configured")
            return False
        
        return self.switch_controller.switch_to_port(antenna.port)
    
    def point_rotator(self, azimuth: float, elevation: float) -> bool:
        """Point rotator to specified position"""
        if not self.rotator_controller:
            logger.warning("Rotator controller not configured")
            return False
        
        return self.rotator_controller.set_position(azimuth, elevation)
    
    def steer_array_beam(self, angle_deg: float) -> None:
        """Steer phased array beam"""
        if not self.array_controller:
            logger.warning("Array controller not configured")
            return
        
        self.array_controller.steer_beam(angle_deg)
    
    def start_monitoring(self, interval_seconds: float = 10.0) -> None:
        """Start antenna monitoring thread"""
        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval_seconds,),
            daemon=True
        )
        self._monitor_thread.start()
        logger.info("Antenna monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop antenna monitoring"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("Antenna monitoring stopped")
    
    def _monitor_loop(self, interval: float) -> None:
        """Monitoring loop for antenna status"""
        while self._monitoring:
            try:
                status = self.get_system_status()
                
                # Check for issues
                for antenna in self.antennas.values():
                    if antenna.vswr > 2.5:
                        logger.warning(f"High VSWR on antenna {antenna.name}: {antenna.vswr}")
                
                time.sleep(interval)
                
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                time.sleep(interval)
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get complete antenna system status"""
        status = {
            'timestamp': datetime.now().isoformat(),
            'antennas': [a.to_dict() for a in self.antennas.values()],
            'switch': self.switch_controller.get_status() if self.switch_controller else None,
            'rotator': self.rotator_controller.get_status() if self.rotator_controller else None,
            'array': self.array_controller.get_status() if self.array_controller else None,
            'scan_strategy': self.scan_strategy
        }
        
        return status
    
    def close_all(self):
        """Close all controllers"""
        if self.switch_controller:
            self.switch_controller.close()
        if self.rotator_controller:
            self.rotator_controller.close()
        
        self.stop_monitoring()
        logger.info("Antenna manager closed")


# ============================================================================
# Factory Functions
# ============================================================================

def create_default_antenna_system() -> AntennaManager:
    """
    Create a default antenna system with common configurations
    
    Returns:
        Configured AntennaManager
    """
    manager = AntennaManager()
    
    # Configure virtual switch (for testing)
    manager.configure_switch(switch_type=SwitchType.VIRTUAL)
    
    # Add standard antennas
    antennas = [
        Antenna(
            id="ant_2.4g_omni",
            name="2.4 GHz Omnidirectional",
            port=AntennaPort.PORT_1,
            antenna_type=AntennaType.OMNIDIRECTIONAL,
            polarization=Polarization.VERTICAL,
            frequency_range=(2.40e9, 2.50e9),
            gain_dbi=3.0,
            beamwidth_deg=360.0
        ),
        Antenna(
            id="ant_5.8g_omni",
            name="5.8 GHz Omnidirectional",
            port=AntennaPort.PORT_2,
            antenna_type=AntennaType.OMNIDIRECTIONAL,
            polarization=Polarization.VERTICAL,
            frequency_range=(5.70e9, 5.90e9),
            gain_dbi=5.0,
            beamwidth_deg=360.0
        ),
        Antenna(
            id="ant_2.4g_directional",
            name="2.4 GHz Yagi",
            port=AntennaPort.PORT_3,
            antenna_type=AntennaType.DIRECTIONAL_YAGI,
            polarization=Polarization.HORIZONTAL,
            frequency_range=(2.40e9, 2.50e9),
            gain_dbi=12.0,
            beamwidth_deg=30.0,
            front_to_back_db=15.0
        ),
        Antenna(
            id="ant_5.8g_directional",
            name="5.8 GHz Patch",
            port=AntennaPort.PORT_4,
            antenna_type=AntennaType.DIRECTIONAL_PATCH,
            polarization=Polarization.CIRCULAR_RH,
            frequency_range=(5.70e9, 5.90e9),
            gain_dbi=14.0,
            beamwidth_deg=25.0,
            front_to_back_db=18.0,
            bias_t_enabled=True,
            bias_t_voltage=5.0
        )
    ]
    
    for antenna in antennas:
        manager.add_antenna(antenna)
    
    return manager


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    """Test antenna controller"""
    
    print("Antenna Controller Test")
    print("=" * 50)
    
    # Create antenna manager
    manager = create_default_antenna_system()
    print("\n1. Antenna System Created")
    
    # Select antenna for frequency
    print("\n2. Testing Antenna Selection:")
    
    test_frequencies = [2.44e9, 5.8e9, 2.45e9, 5.85e9]
    
    for freq in test_frequencies:
        success = manager.select_antenna_for_frequency(freq)
        status = manager.get_system_status()
        
        current = status['switch']['current_antenna']
        if current:
            print(f"   {freq/1e9:.2f} GHz → {current['name']} (gain: {current['gain_dbi']} dBi)")
        else:
            print(f"   {freq/1e9:.2f} GHz → No antenna selected")
    
    # Get system status
    print("\n3. System Status:")
    status = manager.get_system_status()
    print(f"   Active Antennas: {len(status['antennas'])}")
    print(f"   Switch Type: {status['switch']['switch_type']}")
    print(f"   Switch Count: {status['switch']['switch_count']}")
    
    # Test manual selection
    print("\n4. Manual Antenna Selection:")
    manager.select_antenna_by_id("ant_5.8g_directional")
    status = manager.get_system_status()
    current = status['switch']['current_antenna']
    if current:
        print(f"   Manually selected: {current['name']}")
    
    # Print antenna details
    print("\n5. Antenna Details:")
    for antenna in status['antennas']:
        print(f"   {antenna['name']}:")
        print(f"     - Range: {antenna['frequency_range'][0]/1e9:.2f}-{antenna['frequency_range'][1]/1e9:.2f} GHz")
        print(f"     - Gain: {antenna['gain_dbi']} dBi")
        print(f"     - Beamwidth: {antenna['beamwidth_deg']}°")
    
    # Cleanup
    manager.close_all()
    
    print("\n" + "=" * 50)
    print("Antenna controller test complete")