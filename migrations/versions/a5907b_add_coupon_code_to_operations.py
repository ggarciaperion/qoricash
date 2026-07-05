"""add coupon_code to operations

Revision ID: a5907b
Revises: i1a2i3n4t5e6
Create Date: 2026-06-23

Agrega columna coupon_code a la tabla operations para registrar qué cupón
fue aplicado en cada operación. El código se marca como utilizado únicamente
cuando la operación alcanza el estado "Completada".
"""
from alembic import op
import sqlalchemy as sa

revision = 'a5907b'
down_revision = 'i1a2i3n4t5e6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('operations', sa.Column('coupon_code', sa.String(20), nullable=True))


def downgrade():
    op.drop_column('operations', 'coupon_code')
