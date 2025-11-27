"""Add notes_read_by_json to operations

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2025-11-22 23:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3d4e5f6g7h8'
down_revision = 'b2c3d4e5f6g7'
branch_labels = None
depends_on = None


def upgrade():
    # Agregar columna notes_read_by_json a la tabla operations
    op.add_column('operations', sa.Column('notes_read_by_json', sa.Text(), nullable=True))

    # Inicializar con array vacío para operaciones existentes
    op.execute("UPDATE operations SET notes_read_by_json = '[]' WHERE notes_read_by_json IS NULL")


def downgrade():
    # Eliminar columna notes_read_by_json
    op.drop_column('operations', 'notes_read_by_json')
