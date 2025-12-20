"""Add en_observacion field to operations

Revision ID: n6o7p8q9r0s1
Revises: m5n6o7p8q9r0
Create Date: 2025-12-19 23:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'n6o7p8q9r0s1'
down_revision = 'm5n6o7p8q9r0'
branch_labels = None
depends_on = None


def upgrade():
    # Agregar campo en_observacion a tabla operations
    op.add_column('operations', sa.Column('en_observacion', sa.Boolean(), nullable=False, server_default='0'))


def downgrade():
    # Eliminar campo en_observacion
    op.drop_column('operations', 'en_observacion')
