"""Add missing performance indexes

Revision ID: i1n2d3e4x5e6
Revises: m1a2t3c4h5p6
Create Date: 2026-05-14

Indexes added:
  - clients(created_by)           — trader-filtered client views (20+ query sites)
  - operations(operation_type)    — accounting / type filtering
  - operations(completed_at)      — accounting date-range queries on completed ops
"""
from alembic import op
from sqlalchemy import text


revision = 'i1n2d3e4x5e6'
down_revision = 'm1a2t3c4h5p6'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    conn.execute(text(
        'CREATE INDEX IF NOT EXISTS idx_client_created_by '
        'ON clients(created_by)'
    ))
    conn.execute(text(
        'CREATE INDEX IF NOT EXISTS idx_op_type '
        'ON operations(operation_type)'
    ))
    conn.execute(text(
        'CREATE INDEX IF NOT EXISTS idx_op_completed_at '
        'ON operations(completed_at)'
    ))


def downgrade():
    conn = op.get_bind()
    conn.execute(text('DROP INDEX IF EXISTS idx_client_created_by'))
    conn.execute(text('DROP INDEX IF EXISTS idx_op_type'))
    conn.execute(text('DROP INDEX IF EXISTS idx_op_completed_at'))
