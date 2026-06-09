"""Merge all divergent migration heads

Revision ID: c1m2e3r4g5e6
Revises: pb1r2e3c4i5o, b1a2n3k4b5a6, p1e2r3i4o5d6, k1y2c3d4e5f6, b1c2a3j4a5d6
Create Date: 2026-06-08 08:00:00.000000

This is a no-op merge migration. It resolves the 5 divergent heads so that
flask db upgrade can proceed linearly from any starting point.

Heads merged:
  - pb1r2e3c4i5o  add_ver_precio_base_to_users
  - b1a2n3k4b5a6  drop_bank_balance_positive_constraints
  - p1e2r3i4o5d6  add_period_audit_fields
  - k1y2c3d4e5f6  add_kyc_status_to_clients
  - b1c2a3j4a5d6  add_daily_cash_control (includes audit/closure columns)
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c1m2e3r4g5e6'
down_revision = ('pb1r2e3c4i5o', 'b1a2n3k4b5a6', 'p1e2r3i4o5d6', 'k1y2c3d4e5f6', 'b1c2a3j4a5d6')
branch_labels = None
depends_on = None


def upgrade():
    # No-op: this migration only resolves divergent heads.
    pass


def downgrade():
    # No-op
    pass
