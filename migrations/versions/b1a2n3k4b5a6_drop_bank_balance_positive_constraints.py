"""Drop check constraints check_balance_usd_positive and check_balance_pen_positive from bank_balances

Revision ID: b1a2n3k4b5a6
Revises: y1u2s3e4r5s6
Create Date: 2026-06-08
"""
from alembic import op

revision = 'b1a2n3k4b5a6'
down_revision = 'y1u2s3e4r5s6'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('ALTER TABLE bank_balances DROP CONSTRAINT IF EXISTS check_balance_usd_positive')
    op.execute('ALTER TABLE bank_balances DROP CONSTRAINT IF EXISTS check_balance_pen_positive')


def downgrade():
    op.execute('ALTER TABLE bank_balances ADD CONSTRAINT check_balance_usd_positive CHECK (balance_usd >= 0)')
    op.execute('ALTER TABLE bank_balances ADD CONSTRAINT check_balance_pen_positive CHECK (balance_pen >= 0)')
