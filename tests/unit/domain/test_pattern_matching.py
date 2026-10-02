from domain.algorithms.pattern_matching import match_signature
from domain.entities.drone import DroneSignature


def test_signature_match_simple():
    sig = DroneSignature(
        id="TEST",
        center_frequency=2450e6,
        bandwidth=20e6,
        confidence_threshold=0.7,
    )

    result = match_signature(
        peaks=[2451e6],
        signature=sig,
    )

    assert result is True
