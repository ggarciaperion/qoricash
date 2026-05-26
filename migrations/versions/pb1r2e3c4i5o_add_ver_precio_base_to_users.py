"""Add ver_precio_base column to users table

Revision ID: pb1r2e3c4i5o
Revises: z9merge_all_heads
Create Date: 2026-05-26

Agrega columna booleana ver_precio_base a la tabla users.
Controlada por Master desde el dashboard para decidir qué traders
pueden ver el widget de Precio Base.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'pb1r2e3c4i5o'
down_revision = 'z9merge_all_heads'
branch_labels = None
depends_on = None


def _column_exists(conn, table, column):
    return column in [c['name'] for c in inspect(conn).get_columns(table)]


def upgrade():
    conn = op.get_bind()
    if not _column_exists(conn, 'users', 'ver_precio_base'):
        op.add_column('users', sa.Column(
            'ver_precio_base', sa.Boolean(), nullable=False, server_default='false'
        ))


def downgrade():
    conn = op.get_bind()
    if _column_exists(conn, 'users', 'ver_precio_base'):
        op.drop_column('users', 'ver_precio_base')
