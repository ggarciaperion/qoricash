"""Drop check constraints check_balance_usd_positive and check_balance_pen_positive from bank_balances

Revision ID: b1a2n3k4b5a6
Revises: y1u2s3e4r5s6
Create Date: 2026-06-08

Allows negative bank balances so that apply_operation can correctly track
deficit positions (e.g. paying out more than current balance in a currency).
"""
from alembic import op
import sqlalchemy as sa

revision = 'b1a2n3k4b5a6'
down_revision = 'y1u2s3e4r5s6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('bank_balances', schema=None) as batch_op:
        try:
            batch_op.drop_constraint('check_balance_usd_positive', type_='check')
        except Exception:
            pass
        try:
            batch_op.drop_constraint('check_balance_pen_positive', type_='check')
        except Exception:
            pass


def downgrade():
    with op.batch_alter_table('bank_balances', schema=None) as batch_op:
        batch_op.create_check_constraint('check_balance_pen_positive', 'balance_pen >= 0')
        batch_op.create_check_constraint('check_balance_usd_positive', 'balance_usd >= 0')
