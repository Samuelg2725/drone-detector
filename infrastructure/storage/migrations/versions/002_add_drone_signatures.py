"""Add drone signatures table

Revision ID: 002_add_drone_signatures
Revises: 001_initial_schema
Create Date: 2024-01-02 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002_add_drone_signatures'
down_revision = '001_initial_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create drone_signatures table
    op.create_table(
        'drone_signatures',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('drone_type', sa.String(128), nullable=False, unique=True),
        sa.Column('manufacturer', sa.String(128)),
        sa.Column('signature_data', sa.JSON, nullable=False),
        sa.Column('frequency_bands', sa.JSON),
        sa.Column('modulation_types', sa.JSON),
        sa.Column('bandwidth', sa.Float),
        sa.Column('hop_pattern', sa.JSON),
        sa.Column('confidence', sa.Float, default=0.0),
        sa.Column('verified', sa.Boolean, default=False),
        sa.Column('source', sa.String(256)),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, onupdate=sa.func.now())
    )
    
    # Create spectrum_signatures table
    op.create_table(
        'spectrum_signatures',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('name', sa.String(256)),
        sa.Column('signature_type', sa.String(64)),
        sa.Column('spectrum_data', sa.JSON),
        sa.Column('peak_frequencies', sa.JSON),
        sa.Column('characteristics', sa.JSON),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now())
    )
    
    # Create indexes
    op.create_index('idx_signatures_drone_type', 'drone_signatures', ['drone_type'])
    op.create_index('idx_signatures_manufacturer', 'drone_signatures', ['manufacturer'])
    op.create_index('idx_signatures_verified', 'drone_signatures', ['verified'])
    op.create_index('idx_spectrum_type', 'spectrum_signatures', ['signature_type'])
    
    # Insert initial drone signatures
    op.execute("""
        INSERT INTO drone_signatures (id, drone_type, manufacturer, signature_data, frequency_bands, modulation_types, bandwidth, verified)
        VALUES 
        ('sig_dji_mavic_3', 'DJI Mavic 3', 'DJI', 
         '{"protocol": "OcuSync 4.0", "features": ["4K video", "long range"]}',
         '[[2.400e9, 2.4835e9], [5.725e9, 5.875e9]]',
         '["OFDM", "QPSK"]', 20e6, true),
        ('sig_dji_mini_3', 'DJI Mini 3', 'DJI',
         '{"protocol": "OcuSync 3.0", "features": ["4K video"]}',
         '[[2.400e9, 2.4835e9]]',
         '["OFDM"]', 10e6, true),
        ('sig_fpv_analog', 'FPV Analog', 'Generic',
         '{"protocol": "Analog FM", "features": ["low latency"]}',
         '[[5.650e9, 5.950e9]]',
         '["FM"]', 8e6, true),
        ('sig_autel_evo_ii', 'Autel EVO II', 'Autel',
         '{"protocol": "Autel Link", "features": ["8K video"]}',
         '[[2.400e9, 2.4835e9], [5.725e9, 5.875e9]]',
         '["OFDM", "QAM"]', 20e6, true),
        ('sig_skydio_2', 'Skydio 2', 'Skydio',
         '{"protocol": "Skydio Autonomy", "features": ["obstacle avoidance"]}',
         '[[2.400e9, 2.4835e9], [5.725e9, 5.875e9]]',
         '["OFDM"]', 20e6, true)
    """)


def downgrade() -> None:
    op.drop_index('idx_spectrum_type')
    op.drop_index('idx_signatures_verified')
    op.drop_index('idx_signatures_manufacturer')
    op.drop_index('idx_signatures_drone_type')
    op.drop_table('spectrum_signatures')
    op.drop_table('drone_signatures')