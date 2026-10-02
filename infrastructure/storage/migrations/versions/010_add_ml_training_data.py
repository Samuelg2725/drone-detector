"""Add ML training data tables

Revision ID: 010_add_ml_training_data
Revises: 009_add_audit_logging
Create Date: 2024-01-10 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '010_add_ml_training_data'
down_revision = '009_add_audit_logging'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create ml_training_samples table
    op.create_table(
        'ml_training_samples',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('sample_type', sa.String(32), nullable=False),  # iq, psd, features
        sa.Column('label', sa.String(128)),
        sa.Column('drone_type', sa.String(128)),
        sa.Column('file_path', sa.String(512)),
        sa.Column('features', sa.JSON),
        sa.Column('metadata', sa.JSON),
        sa.Column('source_recording_id', sa.String(64)),
        sa.Column('validated', sa.Boolean, default=False),
        sa.Column('validation_confidence', sa.Float),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now())
    )
    
    # Create ml_models table
    op.create_table(
        'ml_models',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('model_name', sa.String(128), nullable=False),
        sa.Column('model_version', sa.String(32)),
        sa.Column('model_type', sa.String(64)),  # random_forest, neural_network, etc.
        sa.Column('file_path', sa.String(512)),
        sa.Column('accuracy', sa.Float),
        sa.Column('precision', sa.Float),
        sa.Column('recall', sa.Float),
        sa.Column('f1_score', sa.Float),
        sa.Column('training_samples', sa.Integer),
        sa.Column('validation_samples', sa.Integer),
        sa.Column('hyperparameters', sa.JSON),
        sa.Column('feature_importance', sa.JSON),
        sa.Column('is_active', sa.Boolean, default=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('trained_at', sa.DateTime),
        sa.Column('training_duration_seconds', sa.Float)
    )
    
    # Create ml_predictions table for storing prediction results
    op.create_table(
        'ml_predictions',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('detection_id', sa.String(64)),
        sa.Column('model_id', sa.String(64)),
        sa.Column('predicted_type', sa.String(128)),
        sa.Column('confidence', sa.Float),
        sa.Column('alternative_predictions', sa.JSON),
        sa.Column('features_used', sa.JSON),
        sa.Column('inference_time_ms', sa.Float),
        sa.Column('timestamp', sa.DateTime, nullable=False),
        sa.ForeignKeyConstraint(['detection_id'], ['detections.id']),
        sa.ForeignKeyConstraint(['model_id'], ['ml_models.id'])
    )
    
    # Create ml_training_jobs table
    op.create_table(
        'ml_training_jobs',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('job_name', sa.String(128)),
        sa.Column('status', sa.String(32), default='pending'),
        sa.Column('config', sa.JSON),
        sa.Column('result_model_id', sa.String(64)),
        sa.Column('error_message', sa.Text),
        sa.Column('started_at', sa.DateTime),
        sa.Column('completed_at', sa.DateTime),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['result_model_id'], ['ml_models.id'])
    )
    
    # Create indexes
    op.create_index('idx_training_label', 'ml_training_samples', ['label'])
    op.create_index('idx_training_type', 'ml_training_samples', ['sample_type'])
    op.create_index('idx_training_validated', 'ml_training_samples', ['validated'])
    op.create_index('idx_models_name', 'ml_models', ['model_name', 'model_version'])
    op.create_index('idx_models_active', 'ml_models', ['is_active'])
    op.create_index('idx_predictions_detection', 'ml_predictions', ['detection_id'])
    op.create_index('idx_predictions_timestamp', 'ml_predictions', ['timestamp'])
    op.create_index('idx_training_jobs_status', 'ml_training_jobs', ['status'])
    op.create_index('idx_training_jobs_created', 'ml_training_jobs', ['created_at'])


def downgrade() -> None:
    op.drop_index('idx_training_jobs_created')
    op.drop_index('idx_training_jobs_status')
    op.drop_index('idx_predictions_timestamp')
    op.drop_index('idx_predictions_detection')
    op.drop_index('idx_models_active')
    op.drop_index('idx_models_name')
    op.drop_index('idx_training_validated')
    op.drop_index('idx_training_type')
    op.drop_index('idx_training_label')
    op.drop_table('ml_training_jobs')
    op.drop_table('ml_predictions')
    op.drop_table('ml_models')
    op.drop_table('ml_training_samples')