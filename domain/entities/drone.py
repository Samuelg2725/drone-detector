"""
domain/entities/drone.py

Also never included in the purchased package. pattern_matching.py
imports DroneSignature from here and calls exactly two methods on it -
.matches_bandwidth(bandwidth) and .is_confident(confidence) - which is
the full interface implemented below, inferred directly from that
usage.
"""
from dataclasses import dataclass


@dataclass
class DroneSignature:
    """A known drone RF signature to match candidate signals against.

    This is a real, usable structure - but note that having the
    structure doesn't mean there's any actual validated signature data
    behind it. Populating a real signatures list with real measured
    bandwidth ranges from real drones is a separate, substantial task
    this package never did (see ml_classifier.py and
    spectrum_analyzer.py's own arbitrary "DJI"/"FPV" thresholds, which
    have the same gap - real-looking code, unvalidated numbers).
    """
    id: str
    name: str
    min_bandwidth_hz: float
    max_bandwidth_hz: float
    min_confidence: float = 0.6

    def matches_bandwidth(self, bandwidth_hz: float) -> bool:
        return self.min_bandwidth_hz <= bandwidth_hz <= self.max_bandwidth_hz

    def is_confident(self, confidence: float) -> bool:
        return confidence >= self.min_confidence
