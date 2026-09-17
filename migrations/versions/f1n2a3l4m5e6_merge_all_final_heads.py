"""Merge all heads after PostgreSQL worker layer deployment

Revision ID: f1n2a3l4m5e6
Revises: a5907b, d1c2a3j4a5d6, ec01_worker_tables, w1a2b3o4t5s6
Create Date: 2026-09-16

Context:
  After the ec01_worker_tables migration (worker PostgreSQL shared layer),
  three Flask app migrations remained as separate unmerged heads:
    - a5907b:       operations.coupon_code column
    - d1c2a3j4a5d6: daily_closures saldo_inicial + apertura/cierre columns
    - w1a2b3o4t5s6: wa_bot_sessions cotiz_* columns

  These three migrations were already applied to the Render PostgreSQL DB
  (they existed as historical alembic versions before the ec01 stamping).
  This merge migration declares them as a unified linear head so that
  future 'flask db upgrade' operations work correctly.

  WARNING: Before stamping the PG DB with this revision, verify that the
  columns above exist in the production database:
    SELECT column_name FROM information_schema.columns
    WHERE table_name IN ('operations', 'wa_bot_sessions')
    AND column_name IN ('coupon_code', 'cotiz_op', 'cotiz_importe', 'cotiz_tc');

  If all columns exist:
    flask db stamp f1n2a3l4m5e6

  Only after successful stamp, flask db upgrade is safe as a release command.

No schema changes in this migration.
"""
from alembic import op

revision = 'f1n2a3l4m5e6'
down_revision = ('a5907b', 'd1c2a3j4a5d6', 'ec01_worker_tables', 'w1a2b3o4t5s6')
branch_labels = None
depends_on = None


def upgrade():
    pass  # No-op: all schema changes already applied in parent revisions


def downgrade():
    pass  # No-op: downgrade handled by parent revisions individually
