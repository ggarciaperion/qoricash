"""Add performance indexes on operations and clients

Revision ID: p7q8r9s0
Revises: n1e2w3t4a5b6
Create Date: 2026-03-28

Indexes added:
  - operations(status, created_at)    — compliance scoring, dashboard queries
  - operations(client_id, status)     — per-client operation history
  - clients(status)                   — active client filters
  - clients(created_at)               — registration date sorting/filtering
"""
from alembic import op
from sqlalchemy import text


revision = 'p7q8r9s0'
down_revision = 'n1e2w3t4a5b6'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    conn.execute(text(
        'CREATE INDEX IF NOT EXISTS idx_op_status_date '
        'ON operations(status, created_at)'
    ))
    conn.execute(text(
        'CREATE INDEX IF NOT EXISTS idx_op_client_status '
        'ON operations(client_id, status)'
    ))
    conn.execute(text(
        'CREATE INDEX IF NOT EXISTS idx_client_status '
        'ON clients(status)'
    ))
    conn.execute(text(
        'CREATE INDEX IF NOT EXISTS idx_client_created '
        'ON clients(created_at)'
    ))


def downgrade():
    conn = op.get_bind()
    conn.execute(text('DROP INDEX IF EXISTS idx_op_status_date'))
    conn.execute(text('DROP INDEX IF EXISTS idx_op_client_status'))
    conn.execute(text('DROP INDEX IF EXISTS idx_client_status'))
    conn.execute(text('DROP INDEX IF EXISTS idx_client_created'))
