"""Add is_validated + closure_date to bank_movements; create daily_closures table

Revision ID: a1u2d3i4t5o6
Revises: z9merge_all_heads
Create Date: 2026-06-08

Agrega las columnas que el módulo de Auditoría & Cierre Diario necesita:
  - bank_movements.is_validated  (Boolean, default False)
  - bank_movements.closure_date  (Date, nullable, indexed)
  - Tabla daily_closures completa (si no existe)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision = 'a1u2d3i4t5o6'
down_revision = 'z9merge_all_heads'
branch_labels = None
depends_on = None


def _column_exists(conn, table, column):
    return column in [c['name'] for c in inspect(conn).get_columns(table)]


def _table_exists(conn, table):
    return inspect(conn).has_table(table)


def _index_exists(conn, table, index_name):
    return any(ix['name'] == index_name for ix in inspect(conn).get_indexes(table))


def upgrade():
    conn = op.get_bind()

    # ── bank_movements: is_validated ──────────────────────────────────────
    if not _column_exists(conn, 'bank_movements', 'is_validated'):
        op.add_column('bank_movements', sa.Column(
            'is_validated',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('false'),
        ))

    # ── bank_movements: closure_date ──────────────────────────────────────
    if not _column_exists(conn, 'bank_movements', 'closure_date'):
        op.add_column('bank_movements', sa.Column(
            'closure_date',
            sa.Date(),
            nullable=True,
        ))
        if not _index_exists(conn, 'bank_movements', 'ix_bm_closure_date'):
            op.create_index('ix_bm_closure_date', 'bank_movements', ['closure_date'])

    # ── daily_closures: crear tabla completa si no existe ─────────────────
    if not _table_exists(conn, 'daily_closures'):
        op.create_table(
            'daily_closures',
            sa.Column('id',           sa.Integer(),    primary_key=True),
            sa.Column('closure_date', sa.Date(),       nullable=False),
            sa.Column('status',       sa.String(20),   nullable=False, server_default='borrador'),

            # saldos JSON
            sa.Column('system_balances_json',    sa.Text(), server_default='{}'),
            sa.Column('validated_balances_json', sa.Text(), server_default='{}'),
            sa.Column('differences_json',        sa.Text(), server_default='{}'),

            # resumen operativo
            sa.Column('operations_completed',  sa.Integer(),       server_default='0'),
            sa.Column('total_volume_usd',      sa.Numeric(15, 2),  server_default='0'),
            sa.Column('total_bought_usd',      sa.Numeric(15, 2),  server_default='0'),
            sa.Column('total_sold_usd',        sa.Numeric(15, 2),  server_default='0'),
            sa.Column('avg_buy_rate',          sa.Numeric(10, 4),  server_default='0'),
            sa.Column('avg_sell_rate',         sa.Numeric(10, 4),  server_default='0'),

            # P&L
            sa.Column('gross_spread_pen',  sa.Numeric(15, 2), server_default='0'),
            sa.Column('expenses_pen',      sa.Numeric(15, 2), server_default='0'),
            sa.Column('net_profit_pen',    sa.Numeric(15, 2), server_default='0'),

            # posición pendiente
            sa.Column('pending_operations',      sa.Integer(),      server_default='0'),
            sa.Column('unmatched_completed_usd', sa.Numeric(15, 2), server_default='0'),
            sa.Column('open_matches',            sa.Integer(),      server_default='0'),

            # discrepancias
            sa.Column('has_discrepancies',   sa.Boolean(),      server_default=sa.text('false')),
            sa.Column('max_discrepancy_usd', sa.Numeric(15, 2), server_default='0'),
            sa.Column('max_discrepancy_pen', sa.Numeric(15, 2), server_default='0'),
            sa.Column('discrepancy_reason',  sa.Text()),

            # notas
            sa.Column('notes', sa.Text()),

            # validación
            sa.Column('validated_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('validated_at', sa.DateTime(), nullable=True),

            # metadata
            sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id')),
            sa.Column('created_at', sa.DateTime()),
            sa.Column('updated_at', sa.DateTime()),

            sa.UniqueConstraint('closure_date', name='uq_daily_closures_date'),
        )
        op.create_index('ix_daily_closures_closure_date', 'daily_closures', ['closure_date'])


def downgrade():
    conn = op.get_bind()

    if _table_exists(conn, 'daily_closures'):
        op.drop_table('daily_closures')

    if _column_exists(conn, 'bank_movements', 'closure_date'):
        if _index_exists(conn, 'bank_movements', 'ix_bm_closure_date'):
            op.drop_index('ix_bm_closure_date', table_name='bank_movements')
        op.drop_column('bank_movements', 'closure_date')

    if _column_exists(conn, 'bank_movements', 'is_validated'):
        op.drop_column('bank_movements', 'is_validated')
