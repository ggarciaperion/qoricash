"""Add index on journal_entry_lines(journal_entry_id)

Revision ID: j1o2u3r4n5a6
Revises: i1n2d3e4x5e6
Create Date: 2026-05-14

Index added:
  - journal_entry_lines(journal_entry_id)  — every JournalEntryLine JOIN uses this FK
"""
from alembic import op
from sqlalchemy import text


revision = 'j1o2u3r4n5a6'
down_revision = 'i1n2d3e4x5e6'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    conn.execute(text(
        'CREATE INDEX IF NOT EXISTS idx_jel_journal_entry_id '
        'ON journal_entry_lines(journal_entry_id)'
    ))


def downgrade():
    conn = op.get_bind()
    conn.execute(text('DROP INDEX IF EXISTS idx_jel_journal_entry_id'))
