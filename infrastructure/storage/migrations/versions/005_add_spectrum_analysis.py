"""Add spectrum analysis tables

Revision ID: 005_add_spectrum_analysis
Revises: 004_add_alert_escalation
Create Date: 2024-01-05 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '005_add_spectrum_analysis'
down_revision = '004_add_alert_escalation'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create spectrum_measurements table
    op.create_table(
        'spectrum_measurements',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('timestamp', sa.DateTime, nullable=False),
        sa.Column('center_frequency', sa.Float, nullable=False),
        sa.Column('sample_rate', sa.Float, nullable=False),
        sa.Column('fft_size', sa.Integer),
        sa.Column('psd_data', sa.JSON),
        sa.Column('peak_frequencies', sa.JSON),
        sa.Column('peak_powers', sa.JSON),
        sa.Column('noise_floor', sa.Float),
        sa.Column('snr', sa.Float),
        sa.Column('occupied_bandwidth', sa.Float),
        sa.Column('detection_id', sa.String(64)),
        sa.ForeignKeyConstraint(['detection_id'], ['detections.id'])
    )
    
    # Create interference_measurements table
    op.create_table(
        'interference_measurements',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('timestamp', sa.DateTime, nullable=False),
        sa.Column('frequency', sa.Float, nullable=False),
        sa.Column('bandwidth', sa.Float),
        sa.Column('power', sa.Float),
        sa.Column('type', sa.String(64)),
        sa.Column('severity', sa.Float),
        sa.Column('duration', sa.Float),
        sa.Column('periodic', sa.Boolean, default=False),
        sa.Column('period', sa.Float),
        sa.Column('detection_id', sa.String(64)),
        sa.ForeignKeyConstraint(['detection_id'], ['detections.id'])
    )
    
    # Create modulation_analysis table
    op.create_table(
        'modulation_analysis',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('timestamp', sa.DateTime, nullable=False),
        sa.Column('detection_id', sa.String(64)),
        sa.Column('modulation_type', sa.String(64)),
        sa.Column('confidence', sa.Float),
        sa.Column('symbol_rate', sa.Float),
        sa.Column('carrier_offset', sa.Float),
        sa.Column('evm', sa.Float),
        sa.Column('phase_noise', sa.Float),
        sa.Column('constellation_points', sa.JSON),
        sa.Column('spectral_features', sa.JSON),
        sa.ForeignKeyConstraint(['detection_id'], ['detections.id'])
    )
    
    # Create indexes
    op.create_index('idx_spectrum_timestamp', 'spectrum_measurements', ['timestamp'])
    op.create_index('idx_spectrum_frequency', 'spectrum_measurements', ['center_frequency'])
    op.create_index('idx_interference_timestamp', 'interference_measurements', ['timestamp'])
    op.create_index('idx_interference_frequency', 'interference_measurements', ['frequency'])
    op.create_index('idx_interference_type', 'interference_measurements', ['type'])
    op.create_index('idx_modulation_detection', 'modulation_analysis', ['detection_id'])
    op.create_index('idx_modulation_type', 'modulation_analysis', ['modulation_type'])


def downgrade() -> None:
    op.drop_index('idx_modulation_type')
    op.drop_index('idx_modulation_detection')
    op.drop_index('idx_interference_type')
    op.drop_index('idx_interference_frequency')
    op.drop_index('idx_interference_timestamp')
    op.drop_index('idx_spectrum_frequency')
    op.drop_index('idx_spectrum_timestamp')
    op.drop_table('modulation_analysis')
    op.drop_table('interference_measurements')
    op.drop_table('spectrum_measurements')