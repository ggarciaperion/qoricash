"""Add precio_base_access table for trader widget access control

Revision ID: pb1r2e3c4i5o
Revises: z9merge_all_heads, w1p2r3o4s5p6
Create Date: 2026-05-26

Crea tabla precio_base_access para controlar qué traders pueden ver
el widget de Precio Base. No modifica ninguna tabla existente.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'pb1r2e3c4i5o'
down_revision = ('z9merge_all_heads', 'w1p2r3o4s5p6')
branch_labels = None
depends_on = None


def _table_exists(conn, table):
    return inspect(conn).has_table(table)


def upgrade():
    conn = op.get_bind()
    if not _table_exists(conn, 'precio_base_access'):
        op.create_table(
            'precio_base_access',
            sa.Column('id',      sa.Integer(), primary_key=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'),
                      unique=True, nullable=False, index=True),
        )


def downgrade():
    conn = op.get_bind()
    if _table_exists(conn, 'precio_base_access'):
        op.drop_table('precio_base_access')
