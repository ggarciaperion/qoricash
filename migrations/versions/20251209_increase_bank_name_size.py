"""Increase bank_name field size to 100 characters

Revision ID: k4l5m6n7o8p9
Revises: k3l4m5n6o7p8
Create Date: 2025-12-09 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'k4l5m6n7o8p9'
down_revision = 'k3l4m5n6o7p8'
branch_labels = None
depends_on = None


def upgrade():
    # Increase bank_name field size from 50 to 100 characters
    op.alter_column('bank_balances', 'bank_name',
                    existing_type=sa.String(50),
                    type_=sa.String(100),
                    existing_nullable=False)


def downgrade():
    # Revert bank_name field size back to 50 characters
    op.alter_column('bank_balances', 'bank_name',
                    existing_type=sa.String(100),
                    type_=sa.String(50),
                    existing_nullable=False)
