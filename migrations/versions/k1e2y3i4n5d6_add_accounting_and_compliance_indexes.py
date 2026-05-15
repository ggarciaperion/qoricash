"""Add indexes on accounting and compliance FK/filter columns

Revision ID: k1e2y3i4n5d6
Revises: j1o2u3r4n5a6
Create Date: 2026-05-14

Indexes added:
  - journal_entries(period_id)        — every accounting report filters by period (CRITICAL)
  - journal_entries(entry_type)       — type filtering in many accounting views
  - journal_entries(created_by)       — audit queries
  - expense_records(period_id)        — expense queries always filter by period
  - expense_records(journal_entry_id) — lookup linked journal entry
  - compliance_alerts(client_id)      — per-client compliance views
  - compliance_alerts(operation_id)   — per-operation compliance lookup
  - reward_codes(client_id)           — per-client reward code lookup
"""
from alembic import op
from sqlalchemy import text


revision = 'k1e2y3i4n5d6'
down_revision = 'j1o2u3r4n5a6'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    conn.execute(text(
        'CREATE INDEX IF NOT EXISTS idx_je_period_id '
        'ON journal_entries(period_id)'
    ))
    conn.execute(text(
        'CREATE INDEX IF NOT EXISTS idx_je_entry_type '
        'ON journal_entries(entry_type)'
    ))
    conn.execute(text(
        'CREATE INDEX IF NOT EXISTS idx_je_created_by '
        'ON journal_entries(created_by)'
    ))
    conn.execute(text(
        'CREATE INDEX IF NOT EXISTS idx_er_period_id '
        'ON expense_records(period_id)'
    ))
    conn.execute(text(
        'CREATE INDEX IF NOT EXISTS idx_er_journal_entry_id '
        'ON expense_records(journal_entry_id)'
    ))
    conn.execute(text(
        'CREATE INDEX IF NOT EXISTS idx_ca_client_id '
        'ON compliance_alerts(client_id)'
    ))
    conn.execute(text(
        'CREATE INDEX IF NOT EXISTS idx_ca_operation_id '
        'ON compliance_alerts(operation_id)'
    ))
    conn.execute(text(
        'CREATE INDEX IF NOT EXISTS idx_rc_client_id '
        'ON reward_codes(client_id)'
    ))


def downgrade():
    conn = op.get_bind()
    conn.execute(text('DROP INDEX IF EXISTS idx_je_period_id'))
    conn.execute(text('DROP INDEX IF EXISTS idx_je_entry_type'))
    conn.execute(text('DROP INDEX IF EXISTS idx_je_created_by'))
    conn.execute(text('DROP INDEX IF EXISTS idx_er_period_id'))
    conn.execute(text('DROP INDEX IF EXISTS idx_er_journal_entry_id'))
    conn.execute(text('DROP INDEX IF EXISTS idx_ca_client_id'))
    conn.execute(text('DROP INDEX IF EXISTS idx_ca_operation_id'))
    conn.execute(text('DROP INDEX IF EXISTS idx_rc_client_id'))
