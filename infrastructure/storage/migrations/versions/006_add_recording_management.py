"""Add recording management tables

Revision ID: 006_add_recording_management
Revises: 005_add_spectrum_analysis
Create Date: 2024-01-06 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '006_add_recording_management'
down_revision = '005_add_spectrum_analysis'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create recordings table
    op.create_table(
        'recordings',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('session_id', sa.String(64)),
        sa.Column('file_path', sa.String(512), nullable=False),
        sa.Column('file_format', sa.String(32)),
        sa.Column('duration_seconds', sa.Float),
        sa.Column('sample_rate', sa.Float),
        sa.Column('center_frequency', sa.Float),
        sa.Column('num_samples', sa.Integer),
        sa.Column('file_size_bytes', sa.Integer),
        sa.Column('compression_ratio', sa.Float),
        sa.Column('start_time', sa.DateTime, nullable=False),
        sa.Column('end_time', sa.DateTime),
        sa.Column('trigger_source', sa.String(64)),
        sa.Column('metadata', sa.JSON),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now())
    )
    
    # Create recording_sessions table
    op.create_table(
        'recording_sessions',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('name', sa.String(256)),
        sa.Column('description', sa.Text),
        sa.Column('start_time', sa.DateTime, nullable=False),
        sa.Column('end_time', sa.DateTime),
        sa.Column('total_duration', sa.Float),
        sa.Column('total_size_bytes', sa.Integer),
        sa.Column('num_files', sa.Integer),
        sa.Column('tags', sa.JSON),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now())
    )
    
    # Create recording_events table for tracking recording events
    op.create_table(
        'recording_events',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('recording_id', sa.String(64)),
        sa.Column('event_type', sa.String(64), nullable=False),
        sa.Column('event_data', sa.JSON),
        sa.Column('timestamp', sa.DateTime, nullable=False),
        sa.ForeignKeyConstraint(['recording_id'], ['recordings.id'], ondelete='CASCADE')
    )
    
    # Create indexes
    op.create_index('idx_recordings_session', 'recordings', ['session_id'])
    op.create_index('idx_recordings_start', 'recordings', ['start_time'])
    op.create_index('idx_recordings_format', 'recordings', ['file_format'])
    op.create_index('idx_sessions_name', 'recording_sessions', ['name'])
    op.create_index('idx_sessions_start', 'recording_sessions', ['start_time'])
    op.create_index('idx_recording_events_recording', 'recording_events', ['recording_id'])
    op.create_index('idx_recording_events_timestamp', 'recording_events', ['timestamp'])


def downgrade() -> None:
    op.drop_index('idx_recording_events_timestamp')
    op.drop_index('idx_recording_events_recording')
    op.drop_index('idx_sessions_start')
    op.drop_index('idx_sessions_name')
    op.drop_index('idx_recordings_format')
    op.drop_index('idx_recordings_start')
    op.drop_index('idx_recordings_session')
    op.drop_table('recording_events')
    op.drop_table('recording_sessions')
    op.drop_table('recordings')