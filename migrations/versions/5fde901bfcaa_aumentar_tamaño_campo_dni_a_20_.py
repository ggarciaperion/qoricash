"""Aumentar tamaño campo dni a 20 caracteres

Revision ID: 5fde901bfcaa
Revises: c851829de964
Create Date: 2025-11-20 10:21:52.937477
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '5fde901bfcaa'
down_revision = 'c851829de964'
branch_labels = None
depends_on = None


def upgrade():
    # Aumentar el tamaño del campo dni de VARCHAR(8) a VARCHAR(20)
    # para soportar DNI (8), CE (9-12), y RUC (11)
    op.alter_column('clients', 'dni',
                    existing_type=sa.String(8),
                    type_=sa.String(20),
                    existing_nullable=False)


def downgrade():
    # Revertir el cambio (solo si todos los DNIs tienen 8 caracteres o menos)
    op.alter_column('clients', 'dni',
                    existing_type=sa.String(20),
                    type_=sa.String(8),
                    existing_nullable=False)