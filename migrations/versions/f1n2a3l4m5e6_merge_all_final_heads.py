"""Merge all heads after PostgreSQL worker layer deployment

Revision ID: f1n2a3l4m5e6
Revises: a5907b, d1c2a3j4a5d6, w1a2b3o4t5s6
Create Date: 2026-09-16

Context:
  Three Flask app migrations existed as separate unmerged heads:
    - a5907b:       operations.coupon_code column
    - d1c2a3j4a5d6: daily_closures saldo_inicial + apertura/cierre columns
    - w1a2b3o4t5s6: wa_bot_sessions cotiz_* columns

  These three migrations were already applied to the Render PostgreSQL DB
  (they existed as historical alembic versions before this merge).
  This merge migration declares them as a unified linear head so that
  future 'flask db upgrade' operations work correctly.

  NOTE: ec01_worker_tables was removed from this merge's parents.
  It was retroactively added but creates a graph cycle because e1s2t3u4d5i6
  (downstream of this merge) is now ec01's down_revision. The ec01-ec07
  branch runs linearly AFTER e1s2t3u4d5i6; including ec01 here would cause
  Alembic to treat it as already applied and skip its DDL entirely.

No schema changes in this migration.
"""
from alembic import op

revision = 'f1n2a3l4m5e6'
down_revision = ('a5907b', 'd1c2a3j4a5d6', 'w1a2b3o4t5s6')
branch_labels = None
depends_on = None


def upgrade():
    pass  # No-op: all schema changes already applied in parent revisions


def downgrade():
    pass  # No-op: downgrade handled by parent revisions individually
