"""Remove en_observacion field from operations

Revision ID: o7p8q9r0s1t2
Revises: n6o7p8q9r0s1
Create Date: 2025-12-19 23:30:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'o7p8q9r0s1t2'
down_revision = 'n6o7p8q9r0s1'
branch_labels = None
depends_on = None


def upgrade():
    # Eliminar campo en_observacion de tabla operations
    op.drop_column('operations', 'en_observacion')


def downgrade():
    # Recrear campo en_observacion si se necesita revertir
    op.add_column('operations', sa.Column('en_observacion', sa.Boolean(), nullable=False, server_default='0'))
