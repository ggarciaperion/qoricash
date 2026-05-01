"""Add IGV fields to expense_records and create fixed_assets table

Revision ID: f1x2e3d4a5b6
Revises: p7q8r9s0
Create Date: 2026-05-01

Cambios:
  - expense_records: agrega base_pen, igv_pen, credito_fiscal, expense_type
  - Crea tabla fixed_assets (control de activos fijos y depreciación)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = 'f1x2e3d4a5b6'
down_revision = 'r1e2g3i4s5t6'
branch_labels = None
depends_on = None


def _table_exists(conn, table_name):
    return table_name in inspect(conn).get_table_names()


def _col_exists(conn, table_name, col_name):
    cols = [c['name'] for c in inspect(conn).get_columns(table_name)]
    return col_name in cols


def upgrade():
    conn = op.get_bind()

    # ── expense_records: nuevas columnas ──────────────────────────────────────
    if _table_exists(conn, 'expense_records'):
        if not _col_exists(conn, 'expense_records', 'base_pen'):
            op.add_column('expense_records',
                sa.Column('base_pen', sa.Numeric(18, 2), nullable=True))
        if not _col_exists(conn, 'expense_records', 'igv_pen'):
            op.add_column('expense_records',
                sa.Column('igv_pen', sa.Numeric(18, 2), nullable=True))
        if not _col_exists(conn, 'expense_records', 'credito_fiscal'):
            op.add_column('expense_records',
                sa.Column('credito_fiscal', sa.Boolean(), nullable=True,
                          server_default=sa.text('false')))
        if not _col_exists(conn, 'expense_records', 'expense_type'):
            op.add_column('expense_records',
                sa.Column('expense_type', sa.String(20), nullable=True,
                          server_default=sa.text("'servicio'")))

    # ── fixed_assets ──────────────────────────────────────────────────────────
    if not _table_exists(conn, 'fixed_assets'):
        op.create_table(
            'fixed_assets',
            sa.Column('id',                     sa.Integer(),      primary_key=True),
            sa.Column('asset_code',              sa.String(20),     nullable=False),
            sa.Column('name',                    sa.String(200),    nullable=False),
            sa.Column('category',                sa.String(30),     nullable=False),
            sa.Column('account_code',            sa.String(10),     nullable=False),
            sa.Column('deprec_account',          sa.String(10),     nullable=False),
            sa.Column('acquisition_date',        sa.Date(),         nullable=False),
            sa.Column('cost_pen',                sa.Numeric(18, 2), nullable=False),
            sa.Column('residual_value',          sa.Numeric(18, 2), nullable=True,
                      server_default=sa.text('0')),
            sa.Column('useful_life_months',      sa.Integer(),      nullable=False),
            sa.Column('monthly_depreciation',    sa.Numeric(18, 4), nullable=False),
            sa.Column('months_depreciated',      sa.Integer(),      nullable=True,
                      server_default=sa.text('0')),
            sa.Column('accumulated_depreciation',sa.Numeric(18, 2), nullable=True,
                      server_default=sa.text('0')),
            sa.Column('status',                  sa.String(20),     nullable=True,
                      server_default=sa.text("'activo'")),
            sa.Column('baja_date',               sa.Date(),         nullable=True),
            sa.Column('baja_notes',              sa.Text(),         nullable=True),
            sa.Column('expense_record_id',       sa.Integer(),      nullable=True),
            sa.Column('created_by',              sa.Integer(),      nullable=True),
            sa.Column('created_at',              sa.DateTime(),     nullable=True),
            sa.ForeignKeyConstraint(['expense_record_id'], ['expense_records.id'], ),
            sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
            sa.UniqueConstraint('asset_code'),
        )
        op.create_index('ix_fixed_assets_asset_code', 'fixed_assets', ['asset_code'])


def downgrade():
    conn = op.get_bind()
    if _table_exists(conn, 'fixed_assets'):
        op.drop_table('fixed_assets')
    # No revertimos columnas de expense_records para evitar pérdida de datos
