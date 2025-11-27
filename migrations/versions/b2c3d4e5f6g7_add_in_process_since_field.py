"""add in_process_since field to operations

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2025-11-23

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6g7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    """Agregar campo in_process_since a la tabla operations"""
    # Agregar columna in_process_since (nullable porque las operaciones existentes no tendrán este valor)
    op.add_column('operations', sa.Column('in_process_since', sa.DateTime(), nullable=True))

    print("✅ Campo 'in_process_since' agregado a la tabla 'operations'")


def downgrade():
    """Revertir cambios - eliminar campo in_process_since"""
    op.drop_column('operations', 'in_process_since')

    print("❌ Campo 'in_process_since' eliminado de la tabla 'operations'")
