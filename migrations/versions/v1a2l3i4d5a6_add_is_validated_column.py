"""Add is_validated column to bank_movements (definitive fix)

Revision ID: v1a2l3i4d5a6
Revises: p1a2t3c4h5b6
Create Date: 2026-06-08

Root cause: migration a1u2d3i4t5o6 ran in production but the Python
SQLAlchemy inspector returned a false positive for is_validated (reported
the column as existing when it did not), so only closure_date was added.
Migration p1a2t3c4h5b6 also targets the same column but may not have
run in all environments.

This migration is the definitive single-purpose fix:
  - One statement only: ADD COLUMN IF NOT EXISTS is_validated
  - 100% idempotent — safe to run even if the column already exists
  - No other side effects
"""
from alembic import op
from sqlalchemy import text

revision    = 'v1a2l3i4d5a6'
down_revision = 'p1a2t3c4h5b6'
branch_labels = None
depends_on    = None


def upgrade():
    conn = op.get_bind()
    conn.execute(text(
        "ALTER TABLE bank_movements "
        "ADD COLUMN IF NOT EXISTS is_validated BOOLEAN NOT NULL DEFAULT false"
    ))


def downgrade():
    # Intentionally a no-op: never drop data columns on downgrade
    pass
