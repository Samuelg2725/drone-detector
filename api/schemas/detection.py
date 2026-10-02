"""
drone-detector/api/schemas/detection.py
Detection Schemas

Schema untuk representasi data detection event di API layer.
Digunakan oleh:
- REST history (/detection/latest)
- WebSocket payload ("detection")

Tidak mengandung:
- Logic detection
- DSP / ML
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from enum import Enum


class ThreatLevelSchema(str, Enum):
    """
    Enum threat level untuk API.
    """
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DetectionPayload(BaseModel):
    """
    Payload satu event deteksi.
    """
    timestamp: float = Field(..., description="Unix timestamp (seconds)")
    center_frequency: float = Field(..., description="Center frequency (Hz)")

    peaks: List[float] = Field(
        ..., description="Detected peak frequencies (Hz)"
    )

    signature: Optional[str] = Field(
        None, description="Matched drone signature ID"
    )
    classification: Optional[str] = Field(
        None, description="ML classification label"
    )

    threat_level: ThreatLevelSchema = Field(
        ..., description="Threat assessment result"
    )

    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (confidence, SNR, etc)",
    )


class DetectionListResponse(BaseModel):
    """
    REST response untuk list detection events.
    """
    available: bool = Field(..., description="Data availability")
    count: int = Field(..., description="Number of items")
    items: List[DetectionPayload] = Field(
        default_factory=list,
        description="Detection event list",
    )
