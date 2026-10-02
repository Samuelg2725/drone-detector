"""Add alert escalation and notification tables

Revision ID: 004_add_alert_escalation
Revises: 003_add_remote_id_tables
Create Date: 2024-01-04 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004_add_alert_escalation'
down_revision = '003_add_remote_id_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create alert_escalations table
    op.create_table(
        'alert_escalations',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('alert_id', sa.String(64), nullable=False),
        sa.Column('escalation_level', sa.Integer, nullable=False),
        sa.Column('triggered_at', sa.DateTime, nullable=False),
        sa.Column('action_taken', sa.String(128)),
        sa.Column('notified_users', sa.JSON),
        sa.Column('response_received', sa.Boolean, default=False),
        sa.Column('response_by', sa.String(128)),
        sa.Column('response_at', sa.DateTime),
        sa.ForeignKeyConstraint(['alert_id'], ['alerts.id'], ondelete='CASCADE')
    )
    
    # Create notifications table
    op.create_table(
        'notifications',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('alert_id', sa.String(64)),
        sa.Column('channel', sa.String(64), nullable=False),
        sa.Column('recipient', sa.String(256)),
        sa.Column('subject', sa.String(512)),
        sa.Column('message', sa.Text),
        sa.Column('status', sa.String(32), default='pending'),
        sa.Column('sent_at', sa.DateTime),
        sa.Column('delivered_at', sa.DateTime),
        sa.Column('error', sa.Text),
        sa.Column('retry_count', sa.Integer, default=0),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['alert_id'], ['alerts.id'])
    )
    
    # Create alert_rules table for configurable rules
    op.create_table(
        'alert_rules',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('severity', sa.String(32)),
        sa.Column('condition', sa.JSON),
        sa.Column('action', sa.String(64)),
        sa.Column('cooldown_seconds', sa.Integer, default=60),
        sa.Column('escalation_seconds', sa.JSON),
        sa.Column('enabled', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, onupdate=sa.func.now())
    )
    
    # Create indexes
    op.create_index('idx_escalations_alert', 'alert_escalations', ['alert_id'])
    op.create_index('idx_escalations_level', 'alert_escalations', ['escalation_level'])
    op.create_index('idx_notifications_alert', 'notifications', ['alert_id'])
    op.create_index('idx_notifications_status', 'notifications', ['status'])
    op.create_index('idx_notifications_created', 'notifications', ['created_at'])
    op.create_index('idx_alert_rules_enabled', 'alert_rules', ['enabled'])
    
    # Insert default alert rules
    op.execute("""
        INSERT INTO alert_rules (id, name, description, severity, condition, action, cooldown_seconds, escalation_seconds, enabled)
        VALUES 
        ('rule_high_confidence', 'High Confidence Drone', 'Alert when detection confidence > 0.85', 'CRITICAL',
         '{"confidence": {"$gt": 0.85}}', 'notify_authorities', 30, '[60, 300]', true),
        ('rule_medium_confidence', 'Medium Confidence Drone', 'Alert when detection confidence between 0.7 and 0.85', 'ALERT',
         '{"confidence": {"$between": [0.7, 0.85]}}', 'notify', 60, '[120]', true),
        ('rule_geofence', 'Geofence Violation', 'Alert when drone enters restricted zone', 'CRITICAL',
         '{"in_restricted_zone": true}', 'call_security', 10, '[30, 120]', true),
        ('rule_jamming', 'RF Jamming Detected', 'Alert when jamming is detected', 'EMERGENCY',
         '{"jamming_detected": true}', 'deploy_jammer', 300, '[10, 30, 60]', true),
        ('rule_multiple_drones', 'Multiple Drones', 'Alert when 3+ drones detected', 'CRITICAL',
         '{"drone_count": {"$gte": 3}}', 'notify_authorities', 60, '[60]', true)
    """)


def downgrade() -> None:
    op.drop_index('idx_alert_rules_enabled')
    op.drop_index('idx_notifications_created')
    op.drop_index('idx_notifications_status')
    op.drop_index('idx_notifications_alert')
    op.drop_index('idx_escalations_level')
    op.drop_index('idx_escalations_alert')
    op.drop_table('alert_rules')
    op.drop_table('notifications')
    op.drop_table('alert_escalations')