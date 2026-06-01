"""Add audit fields to accounting_periods

Revision ID: p1e2r3i4o5d6
Revises: m1a2t3c4h5p6
Create Date: 2026-06-01

Cambios:
  - accounting_periods: agrega tc_sbs_cierre, reopened_at, reopened_by, reopen_reason
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = 'p1e2r3i4o5d6'
down_revision = 'm1a2t3c4h5p6'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [c['name'] for c in inspector.get_columns('accounting_periods')]

    with op.batch_alter_table('accounting_periods') as batch_op:
        if 'tc_sbs_cierre' not in columns:
            batch_op.add_column(sa.Column('tc_sbs_cierre', sa.Numeric(10, 4), nullable=True))
        if 'reopened_at' not in columns:
            batch_op.add_column(sa.Column('reopened_at', sa.DateTime, nullable=True))
        if 'reopened_by' not in columns:
            batch_op.add_column(sa.Column('reopened_by', sa.Integer,
                                          sa.ForeignKey('users.id'), nullable=True))
        if 'reopen_reason' not in columns:
            batch_op.add_column(sa.Column('reopen_reason', sa.String(500), nullable=True))


def downgrade():
    with op.batch_alter_table('accounting_periods') as batch_op:
        for col in ['tc_sbs_cierre', 'reopened_at', 'reopened_by', 'reopen_reason']:
            batch_op.drop_column(col)
