from infrastructure.storage.repositories import DetectionRepository


def test_sqlite_storage_roundtrip(temp_db):
    repo = DetectionRepository(temp_db)

    repo.save({
        "timestamp": 1.23,
        "center_frequency": 2450e6,
        "peaks": [2451e6],
        "signature": "TEST",
        "classification": "drone",
        "threat_level": "HIGH",
        "metadata": {},
    })

    items = repo.get_latest(limit=1)
    assert items[0]["threat_level"] == "HIGH"
