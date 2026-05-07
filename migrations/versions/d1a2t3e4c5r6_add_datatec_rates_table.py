"""add datatec_rates table

Revision ID: d1a2t3e4c5r6
Revises: r1e2g3i4s5t6
Create Date: 2026-05-07
"""
from alembic import op
import sqlalchemy as sa

revision = 'd1a2t3e4c5r6'
down_revision = 'r1e2g3i4s5t6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'datatec_rates',
        sa.Column('id',         sa.Integer(),     nullable=False),
        sa.Column('compra',     sa.Numeric(10, 4), nullable=False, server_default='0'),
        sa.Column('venta',      sa.Numeric(10, 4), nullable=False, server_default='0'),
        sa.Column('updated_by', sa.Integer(),     sa.ForeignKey('users.id'), nullable=True),
        sa.Column('updated_at', sa.DateTime(),    nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('datatec_rates')
