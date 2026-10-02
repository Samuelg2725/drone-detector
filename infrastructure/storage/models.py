"""
drone-detector/infrastructure/storage/models.py
Storage Models

Berisi representasi data untuk layer storage.
Model di sini:
- BUKAN domain entity
- BUKAN ORM penuh
- Hanya struktur data persistensi

Tujuan:
- Memisahkan Domain Entity dari bentuk penyimpanan
- Memudahkan mapping & migrasi database
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from domain.entities.detection import DetectionEvent, ThreatLevel


@dataclass
class DetectionRecord:
    """
    Representasi satu record deteksi di database.
    """
    id: Optional[int]
    timestamp: float
    center_frequency: float
    peaks: List[float]
    signature: Optional[str]
    classification: Optional[str]
    threat_level: ThreatLevel
    metadata: Dict[str, Any]

    # ---------- Mapping ----------

    @classmethod
    def from_domain(cls, event: DetectionEvent) -> "DetectionRecord":
        """
        Convert DetectionEvent (domain) → DetectionRecord (storage).
        """
        return cls(
            id=None,
            timestamp=event.timestamp,
            center_frequency=event.center_frequency,
            peaks=list(event.peaks),
            signature=event.signature,
            classification=event.classification,
            threat_level=event.threat_level,
            metadata=dict(event.metadata),
        )

    def to_domain(self) -> DetectionEvent:
        """
        Convert DetectionRecord → DetectionEvent.
        """
        return DetectionEvent(
            timestamp=self.timestamp,
            center_frequency=self.center_frequency,
            peaks=self.peaks,
            signature=self.signature,
            classification=self.classification,
            threat_level=self.threat_level,
            metadata=self.metadata,
        )

    # ---------- Serialization ----------

    def peaks_as_text(self) -> str:
        """
        Serialize peaks untuk penyimpanan text.
        """
        return ",".join(map(str, self.peaks))

    @staticmethod
    def peaks_from_text(text: str) -> List[float]:
        """
        Deserialize peaks dari text database.
        """
        if not text:
            return []
        return [float(x) for x in text.split(",")]
