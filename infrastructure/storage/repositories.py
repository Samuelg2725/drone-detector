"""
drone-detector/infrastructure/storage/repositories.py
Repositories

Repository layer bertugas:
- Menjadi adapter antara domain entity dan database
- Menyembunyikan detail SQL / storage
- Menyediakan API yang konsisten untuk application layer

Repository ≠ Database connection
"""

from typing import Iterable, Optional

from domain.entities.detection import DetectionEvent, ThreatLevel
from infrastructure.storage.database import Database
from infrastructure.storage.models import DetectionRecord


class DetectionRepository:
    """
    Repository untuk DetectionEvent.
    """

    def __init__(self, database: Database):
        self._db = database

    # ---------- Commands (Write) ----------

    def save(self, event: DetectionEvent) -> None:
        """
        Simpan DetectionEvent ke database.
        """
        record = DetectionRecord.from_domain(event)
        self._save_record(record)

    def _save_record(self, record: DetectionRecord) -> None:
        """
        Simpan DetectionRecord ke database (internal).
        """
        assert self._db._conn is not None

        cursor = self._db._conn.cursor()
        cursor.execute(
            """
            INSERT INTO detections (
                timestamp,
                center_frequency,
                peaks,
                signature,
                classification,
                threat_level,
                metadata
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.timestamp,
                record.center_frequency,
                record.peaks_as_text(),
                record.signature,
                record.classification,
                record.threat_level.name,
                str(record.metadata),
            ),
        )
        self._db._conn.commit()

    # ---------- Queries (Read) ----------

    def get_latest(
        self,
        limit: int = 100,
        min_threat: Optional[ThreatLevel] = None,
    ) -> Iterable[DetectionEvent]:
        """
        Ambil event deteksi terbaru sebagai domain entity.
        """
        assert self._db._conn is not None

        query = "SELECT * FROM detections"
        params = []

        if min_threat is not None:
            query += " WHERE threat_level >= ?"
            params.append(min_threat.name)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor = self._db._conn.cursor()
        cursor.execute(query, params)

        for row in cursor.fetchall():
            yield self._row_to_domain(row)

    # ---------- Mapping ----------

    @staticmethod
    def _row_to_domain(row) -> DetectionEvent:
        """
        Convert database row → DetectionEvent.
        """
        record = DetectionRecord(
            id=row["id"],
            timestamp=row["timestamp"],
            center_frequency=row["center_frequency"],
            peaks=DetectionRecord.peaks_from_text(row["peaks"]),
            signature=row["signature"],
            classification=row["classification"],
            threat_level=ThreatLevel[row["threat_level"]],
            metadata=eval(row["metadata"]) if row["metadata"] else {},
        )
        return record.to_domain()
