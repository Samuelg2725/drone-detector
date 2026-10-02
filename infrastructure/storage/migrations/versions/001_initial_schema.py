"""Initial schema for drone detection system

Revision ID: 001_initial_schema
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite, postgresql, mysql

# revision identifiers, used by Alembic.
revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create detections table
    op.create_table(
        'detections',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('timestamp', sa.DateTime, nullable=False),
        sa.Column('drone_type', sa.String(128)),
        sa.Column('confidence', sa.Float),
        sa.Column('threat_level', sa.String(32)),
        sa.Column('frequency', sa.Float),
        sa.Column('signal_strength', sa.Float),
        sa.Column('latitude', sa.Float),
        sa.Column('longitude', sa.Float),
        sa.Column('altitude', sa.Float),
        sa.Column('remote_id', sa.String(128)),
        sa.Column('metadata', sa.JSON),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, onupdate=sa.func.now()),
        sa.Column('is_active', sa.Boolean, default=True)
    )
    
    # Create detection_events table
    op.create_table(
        'detection_events',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('detection_id', sa.String(64), nullable=False),
        sa.Column('event_type', sa.String(64), nullable=False),
        sa.Column('event_data', sa.JSON),
        sa.Column('timestamp', sa.DateTime, nullable=False),
        sa.ForeignKeyConstraint(['detection_id'], ['detections.id'], ondelete='CASCADE')
    )
    
    # Create alerts table
    op.create_table(
        'alerts',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('detection_id', sa.String(64)),
        sa.Column('severity', sa.String(32), nullable=False),
        sa.Column('title', sa.String(256)),
        sa.Column('message', sa.Text),
        sa.Column('acknowledged', sa.Boolean, default=False),
        sa.Column('acknowledged_by', sa.String(128)),
        sa.Column('resolved', sa.Boolean, default=False),
        sa.Column('timestamp', sa.DateTime, nullable=False),
        sa.Column('resolved_at', sa.DateTime),
        sa.Column('escalation_level', sa.Integer, default=0),
        sa.ForeignKeyConstraint(['detection_id'], ['detections.id'])
    )
    
    # Create system_metrics table
    op.create_table(
        'system_metrics',
        sa.Column('id', sa.Integer, autoincrement=True),
        sa.Column('timestamp', sa.DateTime, nullable=False),
        sa.Column('metric_name', sa.String(128), nullable=False),
        sa.Column('metric_value', sa.Float),
        sa.Column('metadata', sa.JSON),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('idx_detections_timestamp', 'detections', ['timestamp'])
    op.create_index('idx_detections_threat_level', 'detections', ['threat_level'])
    op.create_index('idx_detections_drone_type', 'detections', ['drone_type'])
    op.create_index('idx_detections_confidence', 'detections', ['confidence'])
    op.create_index('idx_alerts_severity', 'alerts', ['severity'])
    op.create_index('idx_alerts_timestamp', 'alerts', ['timestamp'])
    op.create_index('idx_alerts_acknowledged', 'alerts', ['acknowledged'])
    op.create_index('idx_metrics_timestamp', 'system_metrics', ['timestamp'])
    op.create_index('idx_metrics_name', 'system_metrics', ['metric_name'])
    op.create_index('idx_events_detection', 'detection_events', ['detection_id'])
    op.create_index('idx_events_timestamp', 'detection_events', ['timestamp'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_events_timestamp')
    op.drop_index('idx_events_detection')
    op.drop_index('idx_metrics_name')
    op.drop_index('idx_metrics_timestamp')
    op.drop_index('idx_alerts_acknowledged')
    op.drop_index('idx_alerts_timestamp')
    op.drop_index('idx_alerts_severity')
    op.drop_index('idx_detections_confidence')
    op.drop_index('idx_detections_drone_type')
    op.drop_index('idx_detections_threat_level')
    op.drop_index('idx_detections_timestamp')
    
    # Drop tables
    op.drop_table('system_metrics')
    op.drop_table('alerts')
    op.drop_table('detection_events')
    op.drop_table('detections')