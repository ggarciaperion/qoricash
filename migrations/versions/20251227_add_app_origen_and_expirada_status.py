"""Add app origin and Expirada status to operations

Revision ID: m6n7o8p9q1r2
Revises: k3l4m5n6o7p8
Create Date: 2025-12-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'm6n7o8p9q1r2'
down_revision = 'k3l4m5n6o7p8'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Actualizar constraint de origen para incluir 'app'
    op.drop_constraint('check_operation_origen', 'operations', type_='check')
    op.create_check_constraint(
        'check_operation_origen',
        'operations',
        "origen IN ('sistema', 'plataforma', 'app')"
    )

    # 2. Actualizar constraint de status para incluir 'Expirada'
    op.drop_constraint('check_operation_status', 'operations', type_='check')
    op.create_check_constraint(
        'check_operation_status',
        'operations',
        "status IN ('Pendiente', 'En proceso', 'Completada', 'Cancelado', 'Expirada')"
    )


def downgrade():
    # Revertir en orden inverso

    # 1. Revertir constraint de status (eliminar 'Expirada')
    op.drop_constraint('check_operation_status', 'operations', type_='check')
    op.create_check_constraint(
        'check_operation_status',
        'operations',
        "status IN ('Pendiente', 'En proceso', 'Completada', 'Cancelado')"
    )

    # 2. Revertir constraint de origen (eliminar 'app')
    op.drop_constraint('check_operation_origen', 'operations', type_='check')
    op.create_check_constraint(
        'check_operation_origen',
        'operations',
        "origen IN ('plataforma', 'sistema')"
    )
