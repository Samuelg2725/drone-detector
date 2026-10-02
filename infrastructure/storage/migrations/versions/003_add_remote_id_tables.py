"""Add Remote ID tables

Revision ID: 003_add_remote_id_tables
Revises: 002_add_drone_signatures
Create Date: 2024-01-03 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003_add_remote_id_tables'
down_revision = '002_add_drone_signatures'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create remote_id_messages table
    op.create_table(
        'remote_id_messages',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('uas_id', sa.String(128), nullable=False),
        sa.Column('latitude', sa.Float, nullable=False),
        sa.Column('longitude', sa.Float, nullable=False),
        sa.Column('altitude', sa.Float),
        sa.Column('speed', sa.Float),
        sa.Column('heading', sa.Float),
        sa.Column('horizontal_accuracy', sa.Float),
        sa.Column('vertical_accuracy', sa.Float),
        sa.Column('timestamp', sa.DateTime, nullable=False),
        sa.Column('rssi', sa.Integer),
        sa.Column('frequency', sa.Float),
        sa.Column('raw_data', sa.LargeBinary),
        sa.Column('status', sa.String(32)),
        sa.Column('operator_id', sa.String(128)),
        sa.Column('operator_latitude', sa.Float),
        sa.Column('operator_longitude', sa.Float),
        sa.Column('operator_altitude', sa.Float),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now())
    )
    
    # Create remote_id_sessions table
    op.create_table(
        'remote_id_sessions',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('uas_id', sa.String(128), nullable=False),
        sa.Column('start_time', sa.DateTime, nullable=False),
        sa.Column('end_time', sa.DateTime),
        sa.Column('first_latitude', sa.Float),
        sa.Column('first_longitude', sa.Float),
        sa.Column('last_latitude', sa.Float),
        sa.Column('last_longitude', sa.Float),
        sa.Column('max_speed', sa.Float),
        sa.Column('avg_altitude', sa.Float),
        sa.Column('max_altitude', sa.Float),
        sa.Column('track_length', sa.Float),
        sa.Column('operator_id', sa.String(128))
    )
    
    # Create remote_id_tracks table for storing track points
    op.create_table(
        'remote_id_tracks',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('session_id', sa.String(64), nullable=False),
        sa.Column('timestamp', sa.DateTime, nullable=False),
        sa.Column('latitude', sa.Float, nullable=False),
        sa.Column('longitude', sa.Float, nullable=False),
        sa.Column('altitude', sa.Float),
        sa.Column('speed', sa.Float),
        sa.Column('heading', sa.Float),
        sa.ForeignKeyConstraint(['session_id'], ['remote_id_sessions.id'], ondelete='CASCADE')
    )
    
    # Create indexes
    op.create_index('idx_remote_id_uas', 'remote_id_messages', ['uas_id'])
    op.create_index('idx_remote_id_timestamp', 'remote_id_messages', ['timestamp'])
    op.create_index('idx_remote_id_session_uas', 'remote_id_sessions', ['uas_id'])
    op.create_index('idx_remote_id_session_time', 'remote_id_sessions', ['start_time'])
    op.create_index('idx_remote_id_tracks_session', 'remote_id_tracks', ['session_id'])
    op.create_index('idx_remote_id_tracks_time', 'remote_id_tracks', ['timestamp'])
    
    # Create spatial index for PostgreSQL (if using PostgreSQL)
    # This is commented out as it's PostgreSQL-specific
    # op.execute("CREATE INDEX idx_remote_id_location ON remote_id_messages USING GIST (ll_to_earth(latitude, longitude))")


def downgrade() -> None:
    op.drop_index('idx_remote_id_tracks_time')
    op.drop_index('idx_remote_id_tracks_session')
    op.drop_index('idx_remote_id_session_time')
    op.drop_index('idx_remote_id_session_uas')
    op.drop_index('idx_remote_id_timestamp')
    op.drop_index('idx_remote_id_uas')
    op.drop_table('remote_id_tracks')
    op.drop_table('remote_id_sessions')
    op.drop_table('remote_id_messages')