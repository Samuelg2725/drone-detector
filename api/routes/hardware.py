#!/usr/bin/env python3
# drone-detector/api/routes/hardware.py
"""
Hardware Control Routes

This module provides REST API endpoints for hardware control and monitoring:
- SDR device management (HackRF, RTL-SDR, Pluto)
- Antenna control and switching
- Hardware status and health monitoring
- Frequency tuning and gain control
- Recording control
- Hardware calibration
- Multiple device support
- Real-time hardware metrics
- Configuration management
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body, status
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator

# Local imports
from api.dependencies import (
    get_current_user,
    get_hardware_service,
    require_permission,
    rate_limiter
)
from infrastructure.hardware import (
    HardwareType,
    AntennaPort,
    AntennaType,
    Polarization
)

# Setup router
router = APIRouter()


# ============================================================================
# Pydantic Models
# ============================================================================

class HardwareTypeEnum(str, Enum):
    """Hardware device types"""
    HACKRF = "hackrf"
    RTL_SDR = "rtl_sdr"
    PLUTO = "pluto"
    MOCK = "mock"


class AntennaPortEnum(int, Enum):
    """Antenna port numbers"""
    PORT_1 = 1
    PORT_2 = 2
    PORT_3 = 3
    PORT_4 = 4
    PORT_5 = 5
    PORT_6 = 6
    PORT_7 = 7
    PORT_8 = 8


class AntennaTypeEnum(str, Enum):
    """Antenna types"""
    OMNIDIRECTIONAL = "omnidirectional"
    DIRECTIONAL_PATCH = "directional_patch"
    DIRECTIONAL_YAGI = "directional_yagi"
    DIRECTIONAL_DISH = "directional_dish"
    LOG_PERIODIC = "log_periodic"
    DUAL_BAND = "dual_band"


class PolarizationEnum(str, Enum):
    """Antenna polarization"""
    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"
    CIRCULAR_RH = "circular_rh"
    CIRCULAR_LH = "circular_lh"
    DUAL = "dual"
    CROSS = "cross"


class TuneRequest(BaseModel):
    """Frequency tuning request"""
    frequency_hz: float = Field(..., gt=0, le=6e9, description="Target frequency in Hz")
    device_id: Optional[str] = Field(None, description="Device ID (uses default if None)")
    wait_for_lock: bool = Field(True, description="Wait for PLL lock")
    
    class Config:
        schema_extra = {
            "example": {
                "frequency_hz": 2440000000,
                "device_id": "hackrf_1",
                "wait_for_lock": True
            }
        }


class GainRequest(BaseModel):
    """Gain configuration request"""
    lna_gain: Optional[int] = Field(None, ge=0, le=40, description="LNA gain (dB)")
    vga_gain: Optional[int] = Field(None, ge=0, le=62, description="VGA gain (dB)")
    amp_enable: Optional[bool] = Field(None, description="RF amplifier enable")
    device_id: Optional[str] = Field(None, description="Device ID")
    
    class Config:
        schema_extra = {
            "example": {
                "lna_gain": 16,
                "vga_gain": 20,
                "amp_enable": False
            }
        }


class SampleRateRequest(BaseModel):
    """Sample rate configuration request"""
    sample_rate_hz: float = Field(..., gt=0, le=20e6, description="Sample rate in Hz")
    device_id: Optional[str] = Field(None, description="Device ID")
    
    class Config:
        schema_extra = {
            "example": {
                "sample_rate_hz": 10000000
            }
        }


class ScanRequest(BaseModel):
    """Frequency scanning request"""
    start_freq_hz: float = Field(..., gt=0, le=6e9)
    end_freq_hz: float = Field(..., gt=0, le=6e9)
    step_hz: float = Field(100000, gt=0, description="Frequency step size")
    dwell_time_ms: float = Field(100, gt=0, le=10000, description="Dwell time per step")
    device_id: Optional[str] = Field(None)
    
    @validator('end_freq_hz')
    def validate_range(cls, v, values):
        if 'start_freq_hz' in values and v <= values['start_freq_hz']:
            raise ValueError('end_freq_hz must be greater than start_freq_hz')
        return v


class AntennaRequest(BaseModel):
    """Antenna switch request"""
    port: AntennaPortEnum = Field(..., description="Antenna port to switch to")
    frequency_hz: Optional[float] = Field(None, description="Operating frequency for compatibility check")
    
    class Config:
        schema_extra = {
            "example": {
                "port": 1,
                "frequency_hz": 2440000000
            }
        }


class AntennaConfig(BaseModel):
    """Antenna configuration"""
    id: str = Field(..., description="Antenna ID")
    name: str = Field(..., description="Antenna name")
    port: AntennaPortEnum = Field(..., description="Physical port")
    antenna_type: AntennaTypeEnum = Field(..., description="Antenna type")
    polarization: PolarizationEnum = Field(..., description="Polarization")
    frequency_min_hz: float = Field(..., description="Minimum frequency")
    frequency_max_hz: float = Field(..., description="Maximum frequency")
    gain_dbi: float = Field(0.0, description="Antenna gain in dBi")
    beamwidth_deg: float = Field(360.0, description="Beamwidth in degrees")
    enabled: bool = Field(True, description="Antenna enabled")
    bias_t_enabled: bool = Field(False, description="Bias-T enabled")
    bias_t_voltage: float = Field(5.0, description="Bias-T voltage")
    
    class Config:
        schema_extra = {
            "example": {
                "id": "ant_2.4g_omni",
                "name": "2.4 GHz Omnidirectional",
                "port": 1,
                "antenna_type": "omnidirectional",
                "polarization": "vertical",
                "frequency_min_hz": 2400000000,
                "frequency_max_hz": 2500000000,
                "gain_dbi": 3.0,
                "beamwidth_deg": 360.0,
                "enabled": True,
                "bias_t_enabled": False,
                "bias_t_voltage": 5.0
            }
        }


class HardwareStatusResponse(BaseModel):
    """Hardware status response"""
    device_id: str
    device_type: str
    connected: bool
    sample_rate_hz: float
    center_freq_hz: float
    lna_gain_db: int
    vga_gain_db: int
    amp_enabled: bool
    temperature_celsius: Optional[float] = None
    uptime_seconds: float
    errors: int
    last_error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        schema_extra = {
            "example": {
                "device_id": "hackrf_1",
                "device_type": "hackrf",
                "connected": True,
                "sample_rate_hz": 10000000,
                "center_freq_hz": 2440000000,
                "lna_gain_db": 16,
                "vga_gain_db": 20,
                "amp_enabled": False,
                "temperature_celsius": 42.5,
                "uptime_seconds": 3600,
                "errors": 0,
                "last_error": None,
                "timestamp": "2024-01-15T10:30:00"
            }
        }


class AntennaStatusResponse(BaseModel):
    """Antenna status response"""
    current_port: int
    current_antenna: Optional[Dict[str, Any]] = None
    antennas: List[Dict[str, Any]]
    switch_count: int
    last_switch_time: Optional[datetime] = None
    
    class Config:
        schema_extra = {
            "example": {
                "current_port": 1,
                "current_antenna": {
                    "id": "ant_2.4g_omni",
                    "name": "2.4 GHz Omnidirectional",
                    "gain_dbi": 3.0
                },
                "antennas": [],
                "switch_count": 42,
                "last_switch_time": "2024-01-15T10:30:00"
            }
        }


class ScanProgressResponse(BaseModel):
    """Scan progress response"""
    scan_id: str
    status: str  # pending, running, completed, failed
    progress_percent: float
    current_freq_hz: float
    start_freq_hz: float
    end_freq_hz: float
    step_hz: float
    steps_completed: int
    steps_total: int
    estimated_time_remaining_sec: float
    results: Optional[List[Dict[str, Any]]] = None
    started_at: datetime
    completed_at: Optional[datetime] = None


# ============================================================================
# Device Management Routes
# ============================================================================

@router.get("/devices", response_model=List[Dict[str, Any]])
async def list_devices(
    hardware_service = Depends(get_hardware_service),
    current_user = Depends(get_current_user)
):
    """
    List all available hardware devices
    
    Returns list of detected SDR devices with their capabilities
    """
    devices = await hardware_service.get_devices()
    return [
        {
            "id": d.id,
            "type": d.type.value,
            "name": d.name,
            "serial": d.serial,
            "connected": d.connected,
            "capabilities": {
                "min_freq": d.min_frequency,
                "max_freq": d.max_frequency,
                "max_sample_rate": d.max_sample_rate
            }
        }
        for d in devices
    ]


@router.get("/devices/{device_id}/status", response_model=HardwareStatusResponse)
async def get_device_status(
    device_id: str = Path(..., description="Device ID"),
    hardware_service = Depends(get_hardware_service),
    current_user = Depends(get_current_user)
):
    """
    Get detailed status of a specific hardware device
    
    Returns real-time status including tuning, gains, temperature, etc.
    """
    status = await hardware_service.get_device_status(device_id)
    
    if not status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device {device_id} not found"
        )
    
    return status


@router.post("/devices/{device_id}/tune")
async def tune_frequency(
    request: TuneRequest,
    device_id: str = Path(..., description="Device ID"),
    hardware_service = Depends(get_hardware_service),
    current_user = Depends(get_current_user),
    _ = Depends(require_permission("hardware:control"))
):
    """
    Tune SDR to specified frequency
    
    Sets the center frequency of the SDR device
    """
    success = await hardware_service.tune_frequency(
        device_id=request.device_id or device_id,
        frequency=request.frequency_hz,
        wait_for_lock=request.wait_for_lock
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to tune frequency"
        )
    
    return {
        "success": True,
        "message": f"Tuned to {request.frequency_hz / 1e9:.3f} GHz",
        "device_id": request.device_id or device_id,
        "frequency_hz": request.frequency_hz
    }


@router.post("/devices/{device_id}/gain")
async def set_gain(
    request: GainRequest,
    device_id: str = Path(..., description="Device ID"),
    hardware_service = Depends(get_hardware_service),
    current_user = Depends(get_current_user),
    _ = Depends(require_permission("hardware:control"))
):
    """
    Configure device gains
    
    Sets LNA, VGA, and amplifier gains
    """
    changes = {}
    
    if request.lna_gain is not None:
        success = await hardware_service.set_lna_gain(
            device_id=request.device_id or device_id,
            gain=request.lna_gain
        )
        if success:
            changes["lna_gain_db"] = request.lna_gain
    
    if request.vga_gain is not None:
        success = await hardware_service.set_vga_gain(
            device_id=request.device_id or device_id,
            gain=request.vga_gain
        )
        if success:
            changes["vga_gain_db"] = request.vga_gain
    
    if request.amp_enable is not None:
        success = await hardware_service.set_amp_enable(
            device_id=request.device_id or device_id,
            enabled=request.amp_enable
        )
        if success:
            changes["amp_enabled"] = request.amp_enable
    
    if not changes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid gain parameters provided"
        )
    
    return {
        "success": True,
        "message": "Gain configuration updated",
        "device_id": request.device_id or device_id,
        "changes": changes
    }


@router.post("/devices/{device_id}/sample-rate")
async def set_sample_rate(
    request: SampleRateRequest,
    device_id: str = Path(..., description="Device ID"),
    hardware_service = Depends(get_hardware_service),
    current_user = Depends(get_current_user),
    _ = Depends(require_permission("hardware:control"))
):
    """
    Configure sample rate
    
    Sets the ADC/DAC sample rate for the device
    """
    success = await hardware_service.set_sample_rate(
        device_id=request.device_id or device_id,
        sample_rate=request.sample_rate_hz
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set sample rate"
        )
    
    return {
        "success": True,
        "message": f"Sample rate set to {request.sample_rate_hz / 1e6:.1f} MHz",
        "device_id": request.device_id or device_id,
        "sample_rate_hz": request.sample_rate_hz
    }


# ============================================================================
# Scanning Routes
# ============================================================================

@router.post("/scan", response_model=ScanProgressResponse)
async def start_scan(
    request: ScanRequest,
    hardware_service = Depends(get_hardware_service),
    current_user = Depends(get_current_user),
    _ = Depends(require_permission("hardware:scan"))
):
    """
    Start frequency scan
    
    Scans a frequency range and returns measured power levels
    """
    scan_id = await hardware_service.start_scan(
        start_freq=request.start_freq_hz,
        end_freq=request.end_freq_hz,
        step=request.step_hz,
        dwell_time_ms=request.dwell_time_ms,
        device_id=request.device_id
    )
    
    if not scan_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start scan"
        )
    
    return await hardware_service.get_scan_status(scan_id)


@router.get("/scan/{scan_id}", response_model=ScanProgressResponse)
async def get_scan_status(
    scan_id: str = Path(..., description="Scan ID"),
    hardware_service = Depends(get_hardware_service),
    current_user = Depends(get_current_user)
):
    """
    Get scan progress and results
    """
    status = await hardware_service.get_scan_status(scan_id)
    
    if not status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan {scan_id} not found"
        )
    
    return status


@router.delete("/scan/{scan_id}")
async def stop_scan(
    scan_id: str = Path(..., description="Scan ID"),
    hardware_service = Depends(get_hardware_service),
    current_user = Depends(get_current_user),
    _ = Depends(require_permission("hardware:control"))
):
    """
    Stop an ongoing scan
    """
    success = await hardware_service.stop_scan(scan_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan {scan_id} not found or already completed"
        )
    
    return {
        "success": True,
        "message": f"Scan {scan_id} stopped"
    }


# ============================================================================
# Antenna Control Routes
# ============================================================================

@router.get("/antenna", response_model=AntennaStatusResponse)
async def get_antenna_status(
    hardware_service = Depends(get_hardware_service),
    current_user = Depends(get_current_user)
):
    """
    Get current antenna configuration and status
    """
    return await hardware_service.get_antenna_status()


@router.post("/antenna/switch")
async def switch_antenna(
    request: AntennaRequest,
    hardware_service = Depends(get_hardware_service),
    current_user = Depends(get_current_user),
    _ = Depends(require_permission("hardware:control"))
):
    """
    Switch to specified antenna port
    """
    success = await hardware_service.switch_antenna(
        port=request.port.value,
        frequency=request.frequency_hz
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to switch to port {request.port.value}"
        )
    
    return {
        "success": True,
        "message": f"Switched to antenna port {request.port.value}",
        "port": request.port.value
    }


@router.post("/antenna/auto-select")
async def auto_select_antenna(
    frequency_hz: float = Body(..., embed=True),
    hardware_service = Depends(get_hardware_service),
    current_user = Depends(get_current_user),
    _ = Depends(require_permission("hardware:control"))
):
    """
    Automatically select best antenna for frequency
    """
    port = await hardware_service.auto_select_antenna(frequency_hz)
    
    if port is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No antenna found for frequency {frequency_hz / 1e9:.3f} GHz"
        )
    
    return {
        "success": True,
        "message": f"Auto-selected antenna port {port}",
        "frequency_hz": frequency_hz,
        "selected_port": port
    }


@router.post("/antenna/configure")
async def configure_antenna(
    config: AntennaConfig,
    hardware_service = Depends(get_hardware_service),
    current_user = Depends(get_current_user),
    _ = Depends(require_permission("hardware:configure"))
):
    """
    Configure or add an antenna
    """
    success = await hardware_service.configure_antenna(
        antenna_id=config.id,
        name=config.name,
        port=config.port.value,
        antenna_type=config.antenna_type.value,
        polarization=config.polarization.value,
        frequency_range=(config.frequency_min_hz, config.frequency_max_hz),
        gain_dbi=config.gain_dbi,
        beamwidth_deg=config.beamwidth_deg,
        enabled=config.enabled,
        bias_t_enabled=config.bias_t_enabled,
        bias_t_voltage=config.bias_t_voltage
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to configure antenna"
        )
    
    return {
        "success": True,
        "message": f"Antenna {config.id} configured",
        "antenna": config.dict()
    }


# ============================================================================
# Calibration Routes
# ============================================================================

@router.post("/calibrate/ppm")
async def calibrate_ppm(
    reference_frequency_hz: float = Body(..., embed=True),
    hardware_service = Depends(get_hardware_service),
    current_user = Depends(get_current_user),
    _ = Depends(require_permission("hardware:calibrate"))
):
    """
    Calibrate device PPM offset using reference frequency
    
    Automatically calculates and applies PPM correction
    """
    ppm = await hardware_service.calibrate_ppm(reference_frequency_hz)
    
    if ppm is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PPM calibration failed"
        )
    
    return {
        "success": True,
        "message": f"PPM calibration complete: {ppm:.1f} ppm",
        "ppm_correction": ppm
    }


@router.post("/calibrate/noise-floor")
async def calibrate_noise_floor(
    duration_seconds: float = Body(5.0, embed=True),
    hardware_service = Depends(get_hardware_service),
    current_user = Depends(get_current_user),
    _ = Depends(require_permission("hardware:calibrate"))
):
    """
    Calibrate noise floor measurement
    
    Measures noise floor for a duration and updates calibration
    """
    noise_floor = await hardware_service.calibrate_noise_floor(duration_seconds)
    
    return {
        "success": True,
        "message": f"Noise floor calibration complete",
        "noise_floor_dbm": noise_floor
    }


# ============================================================================
# Recording Control Routes
# ============================================================================

@router.post("/recording/start")
async def start_recording(
    duration_seconds: Optional[float] = Body(None, embed=True),
    file_format: str = Body("raw", embed=True),
    hardware_service = Depends(get_hardware_service),
    current_user = Depends(get_current_user),
    _ = Depends(require_permission("hardware:record"))
):
    """
    Start recording IQ data to file
    """
    recording_id = await hardware_service.start_recording(
        duration=duration_seconds,
        format=file_format
    )
    
    return {
        "success": True,
        "message": "Recording started",
        "recording_id": recording_id
    }


@router.post("/recording/stop")
async def stop_recording(
    hardware_service = Depends(get_hardware_service),
    current_user = Depends(get_current_user),
    _ = Depends(require_permission("hardware:record"))
):
    """
    Stop current recording
    """
    metadata = await hardware_service.stop_recording()
    
    return {
        "success": True,
        "message": "Recording stopped",
        "metadata": metadata
    }


# ============================================================================
# Health and Status Routes
# ============================================================================

@router.get("/health")
async def hardware_health(
    hardware_service = Depends(get_hardware_service)
):
    """
    Get hardware subsystem health
    """
    health = await hardware_service.get_health()
    
    return health


@router.get("/metrics")
async def hardware_metrics(
    hardware_service = Depends(get_hardware_service),
    current_user = Depends(get_current_user)
):
    """
    Get real-time hardware metrics
    
    Returns performance metrics for all devices
    """
    metrics = await hardware_service.get_metrics()
    
    return metrics


@router.get("/capabilities")
async def get_capabilities(
    hardware_service = Depends(get_hardware_service)
):
    """
    Get hardware capabilities
    
    Returns supported frequencies, sample rates, etc.
    """
    capabilities = await hardware_service.get_capabilities()
    
    return capabilities


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    print("Hardware Control Routes Module")
    print("=" * 50)
    
    print("\nAvailable Endpoints:")
    print("  GET    /devices                 - List hardware devices")
    print("  GET    /devices/{id}/status     - Get device status")
    print("  POST   /devices/{id}/tune       - Tune frequency")
    print("  POST   /devices/{id}/gain       - Set gains")
    print("  POST   /devices/{id}/sample-rate - Set sample rate")
    print("  POST   /scan                    - Start frequency scan")
    print("  GET    /scan/{id}               - Get scan status")
    print("  DELETE /scan/{id}               - Stop scan")
    print("  GET    /antenna                 - Get antenna status")
    print("  POST   /antenna/switch          - Switch antenna")
    print("  POST   /antenna/auto-select     - Auto-select antenna")
    print("  POST   /antenna/configure       - Configure antenna")
    print("  POST   /calibrate/ppm           - Calibrate PPM")
    print("  POST   /calibrate/noise-floor   - Calibrate noise floor")
    print("  POST   /recording/start         - Start recording")
    print("  POST   /recording/stop          - Stop recording")
    print("  GET    /health                  - Hardware health")
    print("  GET    /metrics                 - Hardware metrics")
    print("  GET    /capabilities            - Hardware capabilities")
    
    print("\n" + "=" * 50)