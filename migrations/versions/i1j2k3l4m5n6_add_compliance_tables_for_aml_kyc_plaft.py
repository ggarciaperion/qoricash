"""Add compliance tables for AML/KYC/PLAFT

Revision ID: i1j2k3l4m5n6
Revises: h6f0b2bd0dd0
Create Date: 2025-12-01 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'i1j2k3l4m5n6'
down_revision = 'h6f0b2bd0dd0'
branch_labels = None
depends_on = None


def upgrade():
    # Create risk_levels table
    op.create_table('risk_levels',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('color', sa.String(length=20), nullable=True),
        sa.Column('score_min', sa.Integer(), nullable=True),
        sa.Column('score_max', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # Create client_risk_profiles table
    op.create_table('client_risk_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('risk_level_id', sa.Integer(), nullable=True),
        sa.Column('risk_score', sa.Integer(), nullable=True),
        sa.Column('is_pep', sa.Boolean(), nullable=True),
        sa.Column('has_legal_issues', sa.Boolean(), nullable=True),
        sa.Column('in_restrictive_lists', sa.Boolean(), nullable=True),
        sa.Column('high_volume_operations', sa.Boolean(), nullable=True),
        sa.Column('kyc_status', sa.String(length=50), nullable=True),
        sa.Column('kyc_verified_at', sa.DateTime(), nullable=True),
        sa.Column('kyc_verified_by', sa.Integer(), nullable=True),
        sa.Column('kyc_notes', sa.Text(), nullable=True),
        sa.Column('dd_level', sa.String(length=50), nullable=True),
        sa.Column('dd_last_review', sa.DateTime(), nullable=True),
        sa.Column('dd_next_review', sa.DateTime(), nullable=True),
        sa.Column('scoring_details', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ),
        sa.ForeignKeyConstraint(['kyc_verified_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['risk_level_id'], ['risk_levels.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('client_id')
    )

    # Create compliance_rules table
    op.create_table('compliance_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('rule_type', sa.String(length=50), nullable=False),
        sa.Column('rule_config', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('severity', sa.String(length=20), nullable=True),
        sa.Column('auto_flag', sa.Boolean(), nullable=True),
        sa.Column('auto_block', sa.Boolean(), nullable=True),
        sa.Column('requires_review', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create compliance_alerts table
    op.create_table('compliance_alerts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('alert_type', sa.String(length=50), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=True),
        sa.Column('operation_id', sa.Integer(), nullable=True),
        sa.Column('rule_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('reviewed_by', sa.Integer(), nullable=True),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('resolution', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ),
        sa.ForeignKeyConstraint(['operation_id'], ['operations.id'], ),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['rule_id'], ['compliance_rules.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create restrictive_list_checks table
    op.create_table('restrictive_list_checks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('list_type', sa.String(length=50), nullable=False),
        sa.Column('provider', sa.String(length=100), nullable=True),
        sa.Column('result', sa.String(length=50), nullable=False),
        sa.Column('match_score', sa.Integer(), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('checked_at', sa.DateTime(), nullable=True),
        sa.Column('checked_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['checked_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create transaction_monitoring table
    op.create_table('transaction_monitoring',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('operation_id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('risk_score', sa.Integer(), nullable=True),
        sa.Column('flags', sa.Text(), nullable=True),
        sa.Column('unusual_amount', sa.Boolean(), nullable=True),
        sa.Column('unusual_frequency', sa.Boolean(), nullable=True),
        sa.Column('structuring', sa.Boolean(), nullable=True),
        sa.Column('rapid_movement', sa.Boolean(), nullable=True),
        sa.Column('client_avg_amount', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('deviation_percentage', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('analyzed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ),
        sa.ForeignKeyConstraint(['operation_id'], ['operations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create compliance_documents table
    op.create_table('compliance_documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_type', sa.String(length=100), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=True),
        sa.Column('operation_id', sa.Integer(), nullable=True),
        sa.Column('alert_id', sa.Integer(), nullable=True),
        sa.Column('file_url', sa.String(length=500), nullable=True),
        sa.Column('file_name', sa.String(length=255), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('sent_to_uif', sa.Boolean(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['alert_id'], ['compliance_alerts.id'], ),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['operation_id'], ['operations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create compliance_audit table
    op.create_table('compliance_audit',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('action_type', sa.String(length=100), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=True),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('changes', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(length=50), nullable=True),
        sa.Column('user_agent', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Insert initial risk levels
    op.execute("""
        INSERT INTO risk_levels (name, description, color, score_min, score_max, created_at)
        VALUES
            ('Bajo', 'Riesgo bajo - Cliente regular sin flags de alerta', 'green', 0, 25, NOW()),
            ('Medio', 'Riesgo medio - Requiere monitoreo regular', 'yellow', 26, 50, NOW()),
            ('Alto', 'Riesgo alto - Requiere due diligence reforzada', 'orange', 51, 75, NOW()),
            ('Crítico', 'Riesgo crítico - Requiere aprobación de compliance', 'red', 76, 100, NOW())
    """)


def downgrade():
    op.drop_table('compliance_audit')
    op.drop_table('compliance_documents')
    op.drop_table('transaction_monitoring')
    op.drop_table('restrictive_list_checks')
    op.drop_table('compliance_alerts')
    op.drop_table('compliance_rules')
    op.drop_table('client_risk_profiles')
    op.drop_table('risk_levels')
