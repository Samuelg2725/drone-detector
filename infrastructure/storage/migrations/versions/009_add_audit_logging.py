"""Add audit logging tables

Revision ID: 009_add_audit_logging
Revises: 008_add_geospatial_support
Create Date: 2024-01-09 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '009_add_audit_logging'
down_revision = '008_add_geospatial_support'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('user_id', sa.String(128)),
        sa.Column('username', sa.String(128)),
        sa.Column('action', sa.String(128), nullable=False),
        sa.Column('resource_type', sa.String(64)),
        sa.Column('resource_id', sa.String(64)),
        sa.Column('old_value', sa.JSON),
        sa.Column('new_value', sa.JSON),
        sa.Column('ip_address', sa.String(45)),
        sa.Column('user_agent', sa.String(512)),
        sa.Column('status', sa.String(32)),
        sa.Column('error_message', sa.Text),
        sa.Column('timestamp', sa.DateTime, nullable=False),
        sa.Column('request_id', sa.String(64))
    )
    
    # Create system_events table
    op.create_table(
        'system_events',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('event_type', sa.String(64), nullable=False),
        sa.Column('event_source', sa.String(128)),
        sa.Column('severity', sa.String(32)),
        sa.Column('message', sa.Text),
        sa.Column('details', sa.JSON),
        sa.Column('timestamp', sa.DateTime, nullable=False),
        sa.Column('acknowledged', sa.Boolean, default=False),
        sa.Column('resolved', sa.Boolean, default=False)
    )
    
    # Create user_activity table
    op.create_table(
        'user_activity',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('user_id', sa.String(128)),
        sa.Column('session_id', sa.String(64)),
        sa.Column('activity_type', sa.String(64)),
        sa.Column('activity_data', sa.JSON),
        sa.Column('duration_seconds', sa.Float),
        sa.Column('timestamp', sa.DateTime, nullable=False),
        sa.Column('ip_address', sa.String(45))
    )
    
    # Create configuration_history table
    op.create_table(
        'configuration_history',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('config_key', sa.String(256), nullable=False),
        sa.Column('config_value', sa.JSON),
        sa.Column('old_value', sa.JSON),
        sa.Column('changed_by', sa.String(128)),
        sa.Column('change_reason', sa.Text),
        sa.Column('timestamp', sa.DateTime, nullable=False),
        sa.Column('version', sa.Integer)
    )
    
    # Create indexes
    op.create_index('idx_audit_user', 'audit_logs', ['user_id', 'timestamp'])
    op.create_index('idx_audit_action', 'audit_logs', ['action', 'timestamp'])
    op.create_index('idx_audit_resource', 'audit_logs', ['resource_type', 'resource_id'])
    op.create_index('idx_audit_request', 'audit_logs', ['request_id'])
    op.create_index('idx_system_events_type', 'system_events', ['event_type', 'timestamp'])
    op.create_index('idx_system_events_severity', 'system_events', ['severity'])
    op.create_index('idx_user_activity_user', 'user_activity', ['user_id', 'timestamp'])
    op.create_index('idx_user_activity_session', 'user_activity', ['session_id'])
    op.create_index('idx_config_key', 'configuration_history', ['config_key', 'version'])
    op.create_index('idx_config_timestamp', 'configuration_history', ['timestamp'])


def downgrade() -> None:
    op.drop_index('idx_config_timestamp')
    op.drop_index('idx_config_key')
    op.drop_index('idx_user_activity_session')
    op.drop_index('idx_user_activity_user')
    op.drop_index('idx_system_events_severity')
    op.drop_index('idx_system_events_type')
    op.drop_index('idx_audit_request')
    op.drop_index('idx_audit_resource')
    op.drop_index('idx_audit_action')
    op.drop_index('idx_audit_user')
    op.drop_table('configuration_history')
    op.drop_table('user_activity')
    op.drop_table('system_events')
    op.drop_table('audit_logs')