"""Add composite source index and remaining compliance indexes

Revision ID: l1s2o3u4r5c6
Revises: k1e2y3i4n5d6
Create Date: 2026-05-14

Indexes added:
  - journal_entries(source_type, source_id)     — composite: lookup by origin (operation/expense/match)
  - restrictive_list_checks(client_id)          — per-client sanctions history
  - compliance records client_id, operation_id  — per-client/operation behaviour analysis
"""
from alembic import op
from sqlalchemy import text


revision = 'l1s2o3u4r5c6'
down_revision = 'k1e2y3i4n5d6'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    conn.execute(text(
        'CREATE INDEX IF NOT EXISTS idx_je_source '
        'ON journal_entries(source_type, source_id)'
    ))
    conn.execute(text(
        'CREATE INDEX IF NOT EXISTS idx_rlc_client_id '
        'ON restrictive_list_checks(client_id)'
    ))
    conn.execute(text(
        'CREATE INDEX IF NOT EXISTS idx_tm_operation_id '
        'ON transaction_monitoring(operation_id)'
    ))
    conn.execute(text(
        'CREATE INDEX IF NOT EXISTS idx_tm_client_id '
        'ON transaction_monitoring(client_id)'
    ))


def downgrade():
    conn = op.get_bind()
    conn.execute(text('DROP INDEX IF EXISTS idx_je_source'))
    conn.execute(text('DROP INDEX IF EXISTS idx_rlc_client_id'))
    conn.execute(text('DROP INDEX IF EXISTS idx_tm_operation_id'))
    conn.execute(text('DROP INDEX IF EXISTS idx_tm_client_id'))
