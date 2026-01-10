"""Fix user DNI length and add Plataforma role

Revision ID: fix_user_dni_role
Revises:
Create Date: 2026-01-09

PROBLEMA IDENTIFICADO:
1. Campo dni en tabla users solo permite 8 caracteres, pero RUC tiene 11 dígitos
2. Constraint check_user_role solo permite ['Master', 'Trader', 'Operador'],
   pero la app móvil necesita role 'Plataforma'

SOLUCIÓN:
- Aumentar longitud de dni a 20 caracteres (igual que en tabla clients)
- Actualizar constraint para permitir role 'Plataforma' y 'Cliente'
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fix_user_dni_role'
down_revision = None  # Will be set automatically by Alembic
branch_labels = None
depends_on = None


def upgrade():
    """Aplicar cambios para soportar clientes móviles"""

    # 1. Eliminar constraint de role antiguo
    op.drop_constraint('check_user_role', 'users', type_='check')

    # 2. Modificar columna dni para soportar RUC (11 dígitos)
    op.alter_column('users', 'dni',
                    existing_type=sa.String(8),
                    type_=sa.String(20),
                    existing_nullable=False)

    # 3. Crear nuevo constraint de role que incluye 'Plataforma' y 'Cliente'
    op.create_check_constraint(
        'check_user_role',
        'users',
        "role IN ('Master', 'Trader', 'Operador', 'Plataforma', 'Cliente')"
    )


def downgrade():
    """Revertir cambios"""

    # 1. Eliminar nuevo constraint
    op.drop_constraint('check_user_role', 'users', type_='check')

    # 2. Revertir columna dni a 8 caracteres
    # ADVERTENCIA: Esto fallará si hay DNIs con más de 8 caracteres
    op.alter_column('users', 'dni',
                    existing_type=sa.String(20),
                    type_=sa.String(8),
                    existing_nullable=False)

    # 3. Restaurar constraint antiguo
    op.create_check_constraint(
        'check_user_role',
        'users',
        "role IN ('Master', 'Trader', 'Operador')"
    )
