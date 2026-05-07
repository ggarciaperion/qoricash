"""add datatec tarde columns

Revision ID: d2a3t4e5c6r7
Revises: d1a2t3e4c5r6
Create Date: 2026-05-07
"""
from alembic import op
import sqlalchemy as sa

revision = 'd2a3t4e5c6r7'
down_revision = 'd1a2t3e4c5r6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('datatec_rates',
        sa.Column('compra_tarde', sa.Numeric(10, 4), nullable=True))
    op.add_column('datatec_rates',
        sa.Column('venta_tarde', sa.Numeric(10, 4), nullable=True))


def downgrade():
    op.drop_column('datatec_rates', 'venta_tarde')
    op.drop_column('datatec_rates', 'compra_tarde')
