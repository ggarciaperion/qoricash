"""add assigned_operator_id to operations

Revision ID: f7g8h9i0j1k2
Revises: e5f6g7h8i9j0
Create Date: 2025-11-28 01:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f7g8h9i0j1k2'
down_revision = 'e5f6g7h8i9j0'
branch_labels = None
depends_on = None


def upgrade():
    # Agregar columna assigned_operator_id a la tabla operations
    op.add_column('operations', sa.Column('assigned_operator_id', sa.Integer(), nullable=True))

    # Crear índice para mejorar performance
    op.create_index(op.f('ix_operations_assigned_operator_id'), 'operations', ['assigned_operator_id'], unique=False)

    # Agregar foreign key
    op.create_foreign_key(
        'fk_operations_assigned_operator_id_users',
        'operations', 'users',
        ['assigned_operator_id'], ['id']
    )


def downgrade():
    # Remover foreign key
    op.drop_constraint('fk_operations_assigned_operator_id_users', 'operations', type_='foreignkey')

    # Remover índice
    op.drop_index(op.f('ix_operations_assigned_operator_id'), table_name='operations')

    # Remover columna
    op.drop_column('operations', 'assigned_operator_id')
