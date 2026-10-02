"""Add geospatial support for location queries

Revision ID: 008_add_geospatial_support
Revises: 007_add_performance_indexes
Create Date: 2024-01-08 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '008_add_geospatial_support'
down_revision = '007_add_performance_indexes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add geofence_zones table
    op.create_table(
        'geofence_zones',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('name', sa.String(256), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('zone_type', sa.String(32)),  # restricted, warning, no_fly, etc.
        sa.Column('polygon_coordinates', sa.JSON, nullable=False),
        sa.Column('center_latitude', sa.Float),
        sa.Column('center_longitude', sa.Float),
        sa.Column('radius_meters', sa.Float),
        sa.Column('altitude_min', sa.Float),
        sa.Column('altitude_max', sa.Float),
        sa.Column('active', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, onupdate=sa.func.now())
    )
    
    # Create geofence_violations table
    op.create_table(
        'geofence_violations',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('detection_id', sa.String(64)),
        sa.Column('zone_id', sa.String(64)),
        sa.Column('latitude', sa.Float, nullable=False),
        sa.Column('longitude', sa.Float, nullable=False),
        sa.Column('altitude', sa.Float),
        sa.Column('distance_to_zone', sa.Float),
        sa.Column('timestamp', sa.DateTime, nullable=False),
        sa.Column('resolved', sa.Boolean, default=False),
        sa.Column('resolved_at', sa.DateTime),
        sa.ForeignKeyConstraint(['detection_id'], ['detections.id']),
        sa.ForeignKeyConstraint(['zone_id'], ['geofence_zones.id'])
    )
    
    # Create geolocation_history table for drone tracking
    op.create_table(
        'geolocation_history',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('drone_id', sa.String(128)),
        sa.Column('detection_id', sa.String(64)),
        sa.Column('latitude', sa.Float, nullable=False),
        sa.Column('longitude', sa.Float, nullable=False),
        sa.Column('altitude', sa.Float),
        sa.Column('speed', sa.Float),
        sa.Column('heading', sa.Float),
        sa.Column('timestamp', sa.DateTime, nullable=False),
        sa.Column('source', sa.String(64)),  # remote_id, tdoa, radar, etc.
        sa.ForeignKeyConstraint(['detection_id'], ['detections.id'])
    )
    
    # Create indexes for geospatial queries
    op.create_index('idx_geofence_zones', 'geofence_zones', ['name', 'active'])
    op.create_index('idx_geofence_violations_zone', 'geofence_violations', ['zone_id'])
    op.create_index('idx_geofence_violations_time', 'geofence_violations', ['timestamp'])
    op.create_index('idx_geolocation_drone', 'geolocation_history', ['drone_id', 'timestamp'])
    op.create_index('idx_geolocation_detection', 'geolocation_history', ['detection_id'])
    
    # Insert default geofence zones
    op.execute("""
        INSERT INTO geofence_zones (id, name, description, zone_type, polygon_coordinates, active)
        VALUES 
        ('zone_airport_1', 'Airport Restricted Zone', '5km radius around airport', 'restricted',
         '{"type": "circle", "center": [-122.4194, 37.7749], "radius": 5000}', true),
        ('zone_military_1', 'Military Base', 'Military installation no-fly zone', 'no_fly',
         '{"type": "polygon", "coordinates": [[-122.42, 37.77], [-122.42, 37.78], [-122.41, 37.78], [-122.41, 37.77]]}', true),
        ('zone_warning_1', 'Helicopter Corridor', 'Low-flying aircraft corridor', 'warning',
         '{"type": "polygon", "coordinates": [[-122.43, 37.76], [-122.43, 37.79], [-122.40, 37.79], [-122.40, 37.76]]}', true)
    """)


def downgrade() -> None:
    op.drop_index('idx_geolocation_detection')
    op.drop_index('idx_geolocation_drone')
    op.drop_index('idx_geofence_violations_time')
    op.drop_index('idx_geofence_violations_zone')
    op.drop_index('idx_geofence_zones')
    op.drop_table('geolocation_history')
    op.drop_table('geofence_violations')
    op.drop_table('geofence_zones')