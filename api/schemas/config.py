"""
drone-detector/api/schemas/config.py
Config Schemas

Schema konfigurasi untuk API layer.
Digunakan oleh:
- GET /config
- POST /config/update

Prinsip:
- Read-first
- Write terbatas (whitelist)
- Tidak menyentuh hardware langsung
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------
# Hardware Config (READ)
# ---------------------------------------------------------------------

class HardwareConfig(BaseModel):
    type: Optional[str] = Field(None, description="SDR type (hackrf, rtl_sdr, pluto)")
    center_frequency: Optional[float] = Field(None, description="Center frequency (Hz)")
    sample_rate: Optional[float] = Field(None, description="Sample rate (Hz)")

    # Gain options (device-dependent)
    lna_gain: Optional[int] = Field(None, description="LNA gain (HackRF)")
    vga_gain: Optional[int] = Field(None, description="VGA gain (HackRF)")
    rx_gain: Optional[float] = Field(None, description="RX gain (Pluto)")
    gain: Optional[Any] = Field(None, description="Gain (RTL-SDR or generic)")

    class Config:
        extra = "ignore"


# ---------------------------------------------------------------------
# System Config (READ)
# ---------------------------------------------------------------------

class SystemConfig(BaseModel):
    name: Optional[str] = Field(None, description="System name")
    mode: Optional[str] = Field(None, description="Operating mode (LIVE / REPLAY)")
    log_level: Optional[str] = Field(None, description="Logging level")

    class Config:
        extra = "ignore"


# ---------------------------------------------------------------------
# Frequency Bands (READ)
# ---------------------------------------------------------------------

class FrequencyBandsConfig(BaseModel):
    bands: Dict[str, Any] = Field(
        default_factory=dict,
        description="Frequency bands definition",
    )

    class Config:
        extra = "allow"


# ---------------------------------------------------------------------
# READ RESPONSE
# ---------------------------------------------------------------------

class ConfigResponse(BaseModel):
    available: bool = Field(..., description="Config availability")
    hardware: Optional[HardwareConfig] = None
    system: Optional[SystemConfig] = None
    frequency_bands: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------
# UPDATE PAYLOAD (WRITE - LIMITED)
# ---------------------------------------------------------------------

class HardwareConfigUpdate(BaseModel):
    """
    Konfigurasi hardware yang BOLEH diubah saat runtime.
    """
    center_frequency: Optional[float] = Field(None, description="Center frequency (Hz)")
    sample_rate: Optional[float] = Field(None, description="Sample rate (Hz)")

    lna_gain: Optional[int] = Field(None, description="LNA gain (HackRF)")
    vga_gain: Optional[int] = Field(None, description="VGA gain (HackRF)")
    rx_gain: Optional[float] = Field(None, description="RX gain (Pluto)")
    gain: Optional[Any] = Field(None, description="Gain (RTL-SDR)")

    class Config:
        extra = "forbid"


class ConfigUpdateRequest(BaseModel):
    """
    Payload update konfigurasi (partial & safe).
    """
    hardware: Optional[HardwareConfigUpdate] = None
