"""add password fields to clients

Revision ID: k3l4m5n6o7p8
Revises: j2k3l4m5n6o7
Create Date: 2026-01-20 03:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'k3l4m5n6o7p8'
down_revision = 'j2k3l4m5n6o7'
branch_labels = None
depends_on = None


def upgrade():
    # Add password and requires_password_change columns to clients table
    op.add_column('clients', sa.Column('password', sa.String(length=255), nullable=True))
    op.add_column('clients', sa.Column('requires_password_change', sa.Boolean(), nullable=True, server_default='false'))


def downgrade():
    # Remove password and requires_password_change columns from clients table
    op.drop_column('clients', 'requires_password_change')
    op.drop_column('clients', 'password')
