"""Add exchange_rates table

Revision ID: k5l6m7n8o9p0
Revises: k4l5m6n7o8p9
Create Date: 2025-12-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'k5l6m7n8o9p0'
down_revision = 'k4l5m6n7o8p9'
branch_labels = None
depends_on = None


def upgrade():
    # Create exchange_rates table
    op.create_table('exchange_rates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('buy_rate', sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column('sell_rate', sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column('updated_by', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    # Drop exchange_rates table
    op.drop_table('exchange_rates')
