from domain.policies.threat_assessment import assess_threat


def test_high_threat_on_signature_match():
    threat = assess_threat(
        signature_matched=True,
        ml_detected=False,
        peak_count=20,
    )

    assert threat.name == "HIGH"
