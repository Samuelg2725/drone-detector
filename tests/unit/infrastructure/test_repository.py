import sqlite3
from infrastructure.storage.repositories import DetectionRepository


def test_repository_insert_and_fetch(tmp_path):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)

    repo = DetectionRepository(conn)

    repo.save({
        "timestamp": 1.0,
        "center_frequency": 2450e6,
        "peaks": [],
        "signature": None,
        "classification": None,
        "threat_level": "LOW",
        "metadata": {},
    })

    items = repo.get_latest(limit=1)
    assert len(items) == 1
