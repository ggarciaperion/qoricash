"""add compliance tables

Revision ID: c0m1p2l3i4a5
Revises: n1e2w3t4a5b6
Create Date: 2026-03-27 00:00:00.000000

Tablas añadidas (con IF NOT EXISTS para ser seguro en producción):
  risk_levels, client_risk_profiles, compliance_rules, compliance_alerts,
  restrictive_list_checks, transaction_monitoring, compliance_documents,
  compliance_audit
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'c0m1p2l3i4a5'
down_revision = 'n1e2w3t4a5b6'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = inspector.get_table_names()

    # ── risk_levels ────────────────────────────────────────────────────────────
    if 'risk_levels' not in existing:
        op.create_table(
            'risk_levels',
            sa.Column('id',          sa.Integer,     primary_key=True),
            sa.Column('name',        sa.String(50),  nullable=False, unique=True),
            sa.Column('description', sa.Text),
            sa.Column('color',       sa.String(20)),
            sa.Column('score_min',   sa.Integer),
            sa.Column('score_max',   sa.Integer),
            sa.Column('created_at',  sa.DateTime),
        )

    # ── client_risk_profiles ───────────────────────────────────────────────────
    if 'client_risk_profiles' not in existing:
        op.create_table(
            'client_risk_profiles',
            sa.Column('id',                 sa.Integer,      primary_key=True),
            sa.Column('client_id',          sa.Integer,      sa.ForeignKey('clients.id'),    nullable=False, unique=True),
            sa.Column('risk_level_id',      sa.Integer,      sa.ForeignKey('risk_levels.id')),
            sa.Column('risk_score',         sa.Integer,      server_default='0'),
            sa.Column('is_pep',             sa.Boolean,      server_default=sa.text('false')),
            sa.Column('has_legal_issues',   sa.Boolean,      server_default=sa.text('false')),
            sa.Column('in_restrictive_lists', sa.Boolean,    server_default=sa.text('false')),
            sa.Column('high_volume_operations', sa.Boolean,  server_default=sa.text('false')),
            sa.Column('pep_type',           sa.String(50)),
            sa.Column('pep_position',       sa.String(200)),
            sa.Column('pep_entity',         sa.String(200)),
            sa.Column('pep_designation_date', sa.Date),
            sa.Column('pep_end_date',       sa.Date),
            sa.Column('pep_notes',          sa.Text),
            sa.Column('kyc_status',         sa.String(50),   server_default='Pendiente'),
            sa.Column('kyc_verified_at',    sa.DateTime),
            sa.Column('kyc_verified_by',    sa.Integer,      sa.ForeignKey('users.id')),
            sa.Column('kyc_notes',          sa.Text),
            sa.Column('dd_level',           sa.String(50)),
            sa.Column('dd_last_review',     sa.DateTime),
            sa.Column('dd_next_review',     sa.DateTime),
            sa.Column('scoring_details',    sa.Text),
            sa.Column('created_at',         sa.DateTime),
            sa.Column('updated_at',         sa.DateTime),
        )

    # ── compliance_rules ───────────────────────────────────────────────────────
    if 'compliance_rules' not in existing:
        op.create_table(
            'compliance_rules',
            sa.Column('id',               sa.Integer,     primary_key=True),
            sa.Column('name',             sa.String(200), nullable=False),
            sa.Column('description',      sa.Text),
            sa.Column('rule_type',        sa.String(50),  nullable=False),
            sa.Column('rule_config',      sa.Text,        nullable=False),
            sa.Column('is_active',        sa.Boolean,     server_default=sa.text('true')),
            sa.Column('severity',         sa.String(20)),
            sa.Column('auto_flag',        sa.Boolean,     server_default=sa.text('true')),
            sa.Column('auto_block',       sa.Boolean,     server_default=sa.text('false')),
            sa.Column('requires_review',  sa.Boolean,     server_default=sa.text('true')),
            sa.Column('created_at',       sa.DateTime),
            sa.Column('created_by',       sa.Integer,     sa.ForeignKey('users.id')),
            sa.Column('updated_at',       sa.DateTime),
        )

    # ── compliance_alerts ─────────────────────────────────────────────────────
    if 'compliance_alerts' not in existing:
        op.create_table(
            'compliance_alerts',
            sa.Column('id',            sa.Integer,     primary_key=True),
            sa.Column('alert_type',    sa.String(50),  nullable=False),
            sa.Column('severity',      sa.String(20),  nullable=False),
            sa.Column('client_id',     sa.Integer,     sa.ForeignKey('clients.id')),
            sa.Column('operation_id',  sa.Integer,     sa.ForeignKey('operations.id')),
            sa.Column('rule_id',       sa.Integer,     sa.ForeignKey('compliance_rules.id')),
            sa.Column('title',         sa.String(200), nullable=False),
            sa.Column('description',   sa.Text),
            sa.Column('details',       sa.Text),
            sa.Column('status',        sa.String(50),  server_default='Pendiente'),
            sa.Column('reviewed_at',   sa.DateTime),
            sa.Column('reviewed_by',   sa.Integer,     sa.ForeignKey('users.id')),
            sa.Column('review_notes',  sa.Text),
            sa.Column('resolution',    sa.String(100)),
            sa.Column('created_at',    sa.DateTime),
            sa.Column('updated_at',    sa.DateTime),
        )

    # ── restrictive_list_checks ────────────────────────────────────────────────
    if 'restrictive_list_checks' not in existing:
        op.create_table(
            'restrictive_list_checks',
            sa.Column('id',                    sa.Integer,     primary_key=True),
            sa.Column('client_id',             sa.Integer,     sa.ForeignKey('clients.id'), nullable=False),
            sa.Column('list_type',             sa.String(50),  nullable=False),
            sa.Column('provider',              sa.String(100)),
            sa.Column('result',                sa.String(50),  nullable=False),
            sa.Column('match_score',           sa.Integer),
            sa.Column('details',               sa.Text),
            sa.Column('is_manual',             sa.Boolean,     server_default=sa.text('false')),
            sa.Column('pep_checked',           sa.Boolean,     server_default=sa.text('false')),
            sa.Column('pep_result',            sa.String(50)),
            sa.Column('pep_details',           sa.Text),
            sa.Column('ofac_checked',          sa.Boolean,     server_default=sa.text('false')),
            sa.Column('ofac_result',           sa.String(50)),
            sa.Column('ofac_details',          sa.Text),
            sa.Column('onu_checked',           sa.Boolean,     server_default=sa.text('false')),
            sa.Column('onu_result',            sa.String(50)),
            sa.Column('onu_details',           sa.Text),
            sa.Column('uif_checked',           sa.Boolean,     server_default=sa.text('false')),
            sa.Column('uif_result',            sa.String(50)),
            sa.Column('uif_details',           sa.Text),
            sa.Column('interpol_checked',      sa.Boolean,     server_default=sa.text('false')),
            sa.Column('interpol_result',       sa.String(50)),
            sa.Column('interpol_details',      sa.Text),
            sa.Column('denuncias_checked',     sa.Boolean,     server_default=sa.text('false')),
            sa.Column('denuncias_result',      sa.String(50)),
            sa.Column('denuncias_details',     sa.Text),
            sa.Column('otras_listas_checked',  sa.Boolean,     server_default=sa.text('false')),
            sa.Column('otras_listas_result',   sa.String(50)),
            sa.Column('otras_listas_details',  sa.Text),
            sa.Column('observations',          sa.Text),
            sa.Column('attachments',           sa.Text),
            sa.Column('checked_at',            sa.DateTime),
            sa.Column('checked_by',            sa.Integer,     sa.ForeignKey('users.id')),
        )

    # ── transaction_monitoring ────────────────────────────────────────────────
    if 'transaction_monitoring' not in existing:
        op.create_table(
            'transaction_monitoring',
            sa.Column('id',                   sa.Integer,       primary_key=True),
            sa.Column('operation_id',         sa.Integer,       sa.ForeignKey('operations.id'), nullable=False),
            sa.Column('client_id',            sa.Integer,       sa.ForeignKey('clients.id'),    nullable=False),
            sa.Column('risk_score',           sa.Integer,       server_default='0'),
            sa.Column('flags',                sa.Text),
            sa.Column('unusual_amount',       sa.Boolean,       server_default=sa.text('false')),
            sa.Column('unusual_frequency',    sa.Boolean,       server_default=sa.text('false')),
            sa.Column('structuring',          sa.Boolean,       server_default=sa.text('false')),
            sa.Column('rapid_movement',       sa.Boolean,       server_default=sa.text('false')),
            sa.Column('client_avg_amount',    sa.Numeric(15,2)),
            sa.Column('deviation_percentage', sa.Numeric(10,2)),
            sa.Column('analyzed_at',          sa.DateTime),
        )

    # ── compliance_documents ──────────────────────────────────────────────────
    if 'compliance_documents' not in existing:
        op.create_table(
            'compliance_documents',
            sa.Column('id',            sa.Integer,     primary_key=True),
            sa.Column('document_type', sa.String(100), nullable=False),
            sa.Column('title',         sa.String(200), nullable=False),
            sa.Column('client_id',     sa.Integer,     sa.ForeignKey('clients.id')),
            sa.Column('operation_id',  sa.Integer,     sa.ForeignKey('operations.id')),
            sa.Column('alert_id',      sa.Integer,     sa.ForeignKey('compliance_alerts.id')),
            sa.Column('file_url',      sa.String(500)),
            sa.Column('file_name',     sa.String(255)),
            sa.Column('content',       sa.Text),
            sa.Column('status',        sa.String(50),  server_default='Borrador'),
            sa.Column('sent_to_uif',   sa.Boolean,     server_default=sa.text('false')),
            sa.Column('sent_at',       sa.DateTime),
            sa.Column('created_at',    sa.DateTime),
            sa.Column('created_by',    sa.Integer,     sa.ForeignKey('users.id')),
        )

    # ── compliance_audit ──────────────────────────────────────────────────────
    if 'compliance_audit' not in existing:
        op.create_table(
            'compliance_audit',
            sa.Column('id',           sa.Integer,     primary_key=True),
            sa.Column('user_id',      sa.Integer,     sa.ForeignKey('users.id'), nullable=False),
            sa.Column('action_type',  sa.String(100), nullable=False),
            sa.Column('entity_type',  sa.String(50)),
            sa.Column('entity_id',    sa.Integer),
            sa.Column('description',  sa.Text),
            sa.Column('changes',      sa.Text),
            sa.Column('ip_address',   sa.String(50)),
            sa.Column('user_agent',   sa.String(255)),
            sa.Column('created_at',   sa.DateTime),
        )


def downgrade():
    op.drop_table('compliance_audit')
    op.drop_table('compliance_documents')
    op.drop_table('transaction_monitoring')
    op.drop_table('restrictive_list_checks')
    op.drop_table('compliance_alerts')
    op.drop_table('compliance_rules')
    op.drop_table('client_risk_profiles')
    op.drop_table('risk_levels')
