"""Add performance indexes for query optimization

Revision ID: 007_add_performance_indexes
Revises: 006_add_recording_management
Create Date: 2024-01-07 00:00:00.000000

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = '007_add_performance_indexes'
down_revision = '006_add_recording_management'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Composite indexes for common query patterns
    op.create_index('idx_detections_composite_1', 'detections', 
                    ['timestamp', 'threat_level', 'confidence'])
    op.create_index('idx_detections_composite_2', 'detections', 
                    ['drone_type', 'timestamp'])
    op.create_index('idx_alerts_composite', 'alerts', 
                    ['severity', 'acknowledged', 'timestamp'])
    op.create_index('idx_remote_id_composite', 'remote_id_messages', 
                    ['uas_id', 'timestamp'])
    
    # Partial indexes for active records
    op.execute("""
        CREATE INDEX idx_detections_active ON detections(timestamp) 
        WHERE is_active = 1
    """)
    
    op.execute("""
        CREATE INDEX idx_alerts_pending ON alerts(timestamp) 
        WHERE acknowledged = 0 AND resolved = 0
    """)
    
    # Index for text search (SQLite FTS)
    op.execute("""
        CREATE VIRTUAL TABLE detections_fts USING fts5(
            id, drone_type, threat_level, remote_id,
            content=detections,
            content_rowid=rowid
        )
    """)
    
    # Sync FTS with main table
    op.execute("""
        INSERT INTO detections_fts(detections_fts, rowid, id, drone_type, threat_level, remote_id)
        SELECT rowid, rowid, id, drone_type, threat_level, remote_id FROM detections
    """)
    
    # Create triggers to keep FTS in sync
    op.execute("""
        CREATE TRIGGER detections_ai AFTER INSERT ON detections BEGIN
            INSERT INTO detections_fts(rowid, id, drone_type, threat_level, remote_id)
            VALUES (new.rowid, new.id, new.drone_type, new.threat_level, new.remote_id);
        END
    """)
    
    op.execute("""
        CREATE TRIGGER detections_ad AFTER DELETE ON detections BEGIN
            INSERT INTO detections_fts(detections_fts, rowid, id, drone_type, threat_level, remote_id)
            VALUES ('delete', old.rowid, old.id, old.drone_type, old.threat_level, old.remote_id);
        END
    """)
    
    op.execute("""
        CREATE TRIGGER detections_au AFTER UPDATE ON detections BEGIN
            INSERT INTO detections_fts(detections_fts, rowid, id, drone_type, threat_level, remote_id)
            VALUES ('delete', old.rowid, old.id, old.drone_type, old.threat_level, old.remote_id);
            INSERT INTO detections_fts(rowid, id, drone_type, threat_level, remote_id)
            VALUES (new.rowid, new.id, new.drone_type, new.threat_level, new.remote_id);
        END
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS detections_au")
    op.execute("DROP TRIGGER IF EXISTS detections_ad")
    op.execute("DROP TRIGGER IF EXISTS detections_ai")
    op.execute("DROP TABLE IF EXISTS detections_fts")
    op.drop_index('idx_alerts_pending')
    op.drop_index('idx_detections_active')
    op.drop_index('idx_remote_id_composite')
    op.drop_index('idx_alerts_composite')
    op.drop_index('idx_detections_composite_2')
    op.drop_index('idx_detections_composite_1')