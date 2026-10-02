# infrastructure/hardware/hardware_factory.py
"""Factory for creating SDR hardware instances (real or mock)"""

import os
from typing import Dict, Any, Optional
from .sdr_base import SDRBase
from .hackrf import HackRFDevice
from .mock_hardware import MockSDR

class HardwareType:
    """Hardware type constants"""
    HACKRF = "hackrf"
    RTL_SDR = "rtl_sdr"
    PLUTO = "pluto"
    MOCK = "mock"
    AUTO = "auto"

class HardwareFactory:
    """Factory for creating SDR hardware with mock support"""
    
    @staticmethod
    def create_hardware(
        hardware_type: str = HardwareType.AUTO,
        config: Optional[Dict[str, Any]] = None,
        force_mock: bool = False
    ) -> SDRBase:
        """
        Create hardware instance.
        
        Args:
            hardware_type: Type of hardware (hackrf, mock, auto)
            config: Configuration dictionary
            force_mock: Force mock mode even if real hardware is available
        
        Returns:
            SDRBase instance
        """
        
        config = config or {}
        mock_enabled = config.get('mock', {}).get('enabled', False)
        
        # Determine if we should use mock
        use_mock = force_mock or mock_enabled
        
        if use_mock:
            print("[Factory] Creating MOCK hardware (no physical device required)")
            device = MockSDR()
            device.initialize(config)
            return device
        
        # Try real hardware
        if hardware_type == HardwareType.HACKRF or hardware_type == HardwareType.AUTO:
            try:
                # Try to detect HackRF
                from .hackrf import HackRFDevice
                device = HackRFDevice()
                if device.initialize(config):
                    print("[Factory] HackRF One detected and initialized")
                    return device
            except Exception as e:
                print(f"[Factory] HackRF not available: {e}")
        
        if hardware_type == HardwareType.MOCK:
            print("[Factory] Creating MOCK hardware as requested")
            device = MockSDR()
            device.initialize(config)
            return device
        
        # Fallback to mock if auto and no hardware found
        if hardware_type == HardwareType.AUTO:
            print("[Factory] No real hardware detected, falling back to MOCK")
            device = MockSDR()
            device.initialize(config)
            return device
        
        raise ValueError(f"No valid hardware implementation found for type: {hardware_type}")
    
    @staticmethod
    def is_mock_hardware(device: SDRBase) -> bool:
        """Check if device is a mock implementation"""
        return isinstance(device, MockSDR)