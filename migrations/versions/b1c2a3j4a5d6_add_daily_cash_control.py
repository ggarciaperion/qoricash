"""Add opening/closing balance fields and result to daily_closures (Caja Diaria)

Revision ID: b1c2a3j4a5d6
Revises: a1u2d3i4t5o6
Create Date: 2026-06-08

Agrega control de caja diaria a daily_closures:
  - opening_balance_json / opening_total_usd / opening_total_pen
  - opening_registered_at / opening_registered_by
  - closing_balance_json / closing_total_usd / closing_total_pen
  - closing_registered_at / closing_registered_by
  - result_usd / result_pen / result_label
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision = 'b1c2a3j4a5d6'
down_revision = 'a1u2d3i4t5o6'
branch_labels = None
depends_on = None


def _col(conn, table, col):
    return col in [c['name'] for c in inspect(conn).get_columns(table)]


def upgrade():
    conn = op.get_bind()
    t = 'daily_closures'

    # Saldo Inicial
    if not _col(conn, t, 'opening_balance_json'):
        op.add_column(t, sa.Column('opening_balance_json', sa.Text(), server_default='{}'))
    if not _col(conn, t, 'opening_total_usd'):
        op.add_column(t, sa.Column('opening_total_usd', sa.Numeric(15, 2), server_default='0'))
    if not _col(conn, t, 'opening_total_pen'):
        op.add_column(t, sa.Column('opening_total_pen', sa.Numeric(15, 2), server_default='0'))
    if not _col(conn, t, 'opening_registered_at'):
        op.add_column(t, sa.Column('opening_registered_at', sa.DateTime(), nullable=True))
    if not _col(conn, t, 'opening_registered_by'):
        op.add_column(t, sa.Column('opening_registered_by', sa.Integer(),
                                   sa.ForeignKey('users.id'), nullable=True))

    # Saldo Final
    if not _col(conn, t, 'closing_balance_json'):
        op.add_column(t, sa.Column('closing_balance_json', sa.Text(), server_default='{}'))
    if not _col(conn, t, 'closing_total_usd'):
        op.add_column(t, sa.Column('closing_total_usd', sa.Numeric(15, 2), server_default='0'))
    if not _col(conn, t, 'closing_total_pen'):
        op.add_column(t, sa.Column('closing_total_pen', sa.Numeric(15, 2), server_default='0'))
    if not _col(conn, t, 'closing_registered_at'):
        op.add_column(t, sa.Column('closing_registered_at', sa.DateTime(), nullable=True))
    if not _col(conn, t, 'closing_registered_by'):
        op.add_column(t, sa.Column('closing_registered_by', sa.Integer(),
                                   sa.ForeignKey('users.id'), nullable=True))

    # Resultado
    if not _col(conn, t, 'result_usd'):
        op.add_column(t, sa.Column('result_usd', sa.Numeric(15, 2), nullable=True))
    if not _col(conn, t, 'result_pen'):
        op.add_column(t, sa.Column('result_pen', sa.Numeric(15, 2), nullable=True))
    if not _col(conn, t, 'result_label'):
        op.add_column(t, sa.Column('result_label', sa.String(20), nullable=True))


def downgrade():
    conn = op.get_bind()
    t = 'daily_closures'
    for col in ['result_label', 'result_pen', 'result_usd',
                'closing_registered_by', 'closing_registered_at',
                'closing_total_pen', 'closing_total_usd', 'closing_balance_json',
                'opening_registered_by', 'opening_registered_at',
                'opening_total_pen', 'opening_total_usd', 'opening_balance_json']:
        if _col(conn, t, col):
            op.drop_column(t, col)
