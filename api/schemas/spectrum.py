"""
drone-detector/api/schemas/spectrum.py
Spectrum Schemas

Schema untuk representasi data spectrum di API layer.
Digunakan oleh:
- REST endpoint (/spectrum/latest)
- WebSocket payload ("spectrum")

Tidak mengandung:
- FFT / DSP logic
- Hardware detail
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class SpectrumPayload(BaseModel):
    """
    Payload spectrum untuk WebSocket & REST.
    """
    timestamp: float = Field(..., description="Unix timestamp (seconds)")
    center_frequency: float = Field(..., description="Center frequency (Hz)")
    frequencies: List[float] = Field(
        ..., description="Frequency axis (Hz)"
    )
    magnitude: List[float] = Field(
        ..., description="Magnitude (dB or linear, sesuai konfigurasi)"
    )


class SpectrumResponse(BaseModel):
    """
    REST response wrapper untuk snapshot spectrum.
    """
    available: bool = Field(..., description="Apakah spectrum tersedia")
    spectrum: Optional[SpectrumPayload] = Field(
        None, description="Spectrum data terbaru"
    )
