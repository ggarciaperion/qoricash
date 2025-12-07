"""Add Plataforma role and origen field to operations

Revision ID: k3l4m5n6o7p8
Revises: j2k3l4m5n6o7
Create Date: 2025-12-07 18:17:52.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'k3l4m5n6o7p8'
down_revision = 'j2k3l4m5n6o7'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Actualizar constraint de roles para incluir 'Plataforma'
    op.drop_constraint('check_user_role', 'users', type_='check')
    op.create_check_constraint(
        'check_user_role',
        'users',
        "role IN ('Master', 'Trader', 'Operador', 'Middle Office', 'Plataforma')"
    )

    # 2. Agregar campo 'origen' a la tabla operations
    op.add_column(
        'operations',
        sa.Column('origen', sa.String(20), nullable=False, server_default='sistema')
    )

    # 3. Crear índice para el campo origen (para búsquedas rápidas)
    op.create_index('ix_operations_origen', 'operations', ['origen'])

    # 4. Crear constraint para validar valores de origen
    op.create_check_constraint(
        'check_operation_origen',
        'operations',
        "origen IN ('plataforma', 'sistema')"
    )


def downgrade():
    # Revertir en orden inverso

    # 1. Eliminar constraint de origen
    op.drop_constraint('check_operation_origen', 'operations', type_='check')

    # 2. Eliminar índice de origen
    op.drop_index('ix_operations_origen', 'operations')

    # 3. Eliminar columna origen
    op.drop_column('operations', 'origen')

    # 4. Revertir constraint de roles
    op.drop_constraint('check_user_role', 'users', type_='check')
    op.create_check_constraint(
        'check_user_role',
        'users',
        "role IN ('Master', 'Trader', 'Operador', 'Middle Office')"
    )
