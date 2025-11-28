"""drop name column from clients

Revision ID: h6f0b2bd0dd0
Revises: g8h9i0j1k2l3
Create Date: 2025-11-28 02:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'h6f0b2bd0dd0'
down_revision = 'g8h9i0j1k2l3'
branch_labels = None
depends_on = None


def upgrade():
    # Drop the orphaned 'name' column from clients table
    # This column is not in the Client model - the model uses 'full_name' as a @property
    op.drop_column('clients', 'name')


def downgrade():
    # Re-add the name column if needed (though it shouldn't be used)
    op.add_column('clients', sa.Column('name', sa.String(length=200), nullable=True))
