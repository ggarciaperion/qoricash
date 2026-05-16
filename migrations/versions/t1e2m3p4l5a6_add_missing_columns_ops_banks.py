"""Add missing columns: operations (base_rate, pips, email_sent) and bank_balances (initial_balance)

Revision ID: t1e2m3p4l5a6
Revises: s1p2r3o4s5p6
Create Date: 2026-05-16

Agrega columnas que estaban en los modelos pero nunca entraron al historial
de migraciones Alembic (solo existían como scripts manuales):
  - operations.base_rate
  - operations.pips
  - operations.new_operation_email_sent
  - bank_balances.initial_balance_usd
  - bank_balances.initial_balance_pen

Usa inspector para verificar existencia previa — es seguro en producción
donde los scripts manuales ya se hayan ejecutado.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


revision = 't1e2m3p4l5a6'
down_revision = 's1p2r3o4s5p6'
branch_labels = None
depends_on = None


def _column_exists(conn, table, column):
    return column in [c['name'] for c in inspect(conn).get_columns(table)]


def upgrade():
    conn = op.get_bind()

    # ── operations ────────────────────────────────────────────────────────────
    if not _column_exists(conn, 'operations', 'base_rate'):
        op.add_column('operations', sa.Column('base_rate', sa.Numeric(10, 4), nullable=True))

    if not _column_exists(conn, 'operations', 'pips'):
        op.add_column('operations', sa.Column('pips', sa.Numeric(8, 1), nullable=True))

    if not _column_exists(conn, 'operations', 'new_operation_email_sent'):
        op.add_column('operations', sa.Column(
            'new_operation_email_sent',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('false'),
        ))

    # ── bank_balances ─────────────────────────────────────────────────────────
    if not _column_exists(conn, 'bank_balances', 'initial_balance_usd'):
        op.add_column('bank_balances', sa.Column(
            'initial_balance_usd',
            sa.Numeric(15, 2),
            nullable=False,
            server_default=sa.text('0'),
        ))

    if not _column_exists(conn, 'bank_balances', 'initial_balance_pen'):
        op.add_column('bank_balances', sa.Column(
            'initial_balance_pen',
            sa.Numeric(15, 2),
            nullable=False,
            server_default=sa.text('0'),
        ))


def downgrade():
    conn = op.get_bind()

    if _column_exists(conn, 'bank_balances', 'initial_balance_pen'):
        op.drop_column('bank_balances', 'initial_balance_pen')
    if _column_exists(conn, 'bank_balances', 'initial_balance_usd'):
        op.drop_column('bank_balances', 'initial_balance_usd')
    if _column_exists(conn, 'operations', 'new_operation_email_sent'):
        op.drop_column('operations', 'new_operation_email_sent')
    if _column_exists(conn, 'operations', 'pips'):
        op.drop_column('operations', 'pips')
    if _column_exists(conn, 'operations', 'base_rate'):
        op.drop_column('operations', 'base_rate')
