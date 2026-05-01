"""Add profit split fields to accounting_matches

Revision ID: m1a2t3c4h5p6
Revises: f1x2e3d4a5b6
Create Date: 2026-05-01

Cambios:
  - accounting_matches: agrega buy_base_rate, sell_base_rate,
    trader_buy_profit_pen, trader_sell_profit_pen, house_profit_pen, match_type
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = 'm1a2t3c4h5p6'
down_revision = 'f1x2e3d4a5b6'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [c['name'] for c in inspector.get_columns('accounting_matches')]

    with op.batch_alter_table('accounting_matches') as batch_op:
        if 'buy_base_rate' not in columns:
            batch_op.add_column(sa.Column('buy_base_rate', sa.Numeric(10, 4), nullable=True))
        if 'sell_base_rate' not in columns:
            batch_op.add_column(sa.Column('sell_base_rate', sa.Numeric(10, 4), nullable=True))
        if 'trader_buy_profit_pen' not in columns:
            batch_op.add_column(sa.Column('trader_buy_profit_pen', sa.Numeric(15, 2), nullable=True))
        if 'trader_sell_profit_pen' not in columns:
            batch_op.add_column(sa.Column('trader_sell_profit_pen', sa.Numeric(15, 2), nullable=True))
        if 'house_profit_pen' not in columns:
            batch_op.add_column(sa.Column('house_profit_pen', sa.Numeric(15, 2), nullable=True))
        if 'match_type' not in columns:
            batch_op.add_column(sa.Column('match_type', sa.String(20), nullable=True, server_default='client_to_client'))


def downgrade():
    with op.batch_alter_table('accounting_matches') as batch_op:
        for col in ['buy_base_rate', 'sell_base_rate', 'trader_buy_profit_pen',
                    'trader_sell_profit_pen', 'house_profit_pen', 'match_type']:
            batch_op.drop_column(col)
