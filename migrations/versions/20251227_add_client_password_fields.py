"""Add password authentication fields to clients

Revision ID: k6l7m8n9o0p1
Revises: k5l6m7n8o9p0
Create Date: 2025-12-27 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'k6l7m8n9o0p1'
down_revision = 'k5l6m7n8o9p0'
branch_labels = None
depends_on = None


def upgrade():
    # Add password_hash column to clients table
    op.add_column('clients', sa.Column('password_hash', sa.String(length=200), nullable=True))

    # Add requires_password_change column to clients table
    # Default to True for new clients, NULL for existing clients (they don't have passwords yet)
    op.add_column('clients', sa.Column('requires_password_change', sa.Boolean(), nullable=True, server_default='true'))


def downgrade():
    # Remove the columns in reverse order
    op.drop_column('clients', 'requires_password_change')
    op.drop_column('clients', 'password_hash')
