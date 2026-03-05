"""Remove rol Plataforma del sistema

Revision ID: k3l4m5n6o7p8
Revises: j2k3l4m5n6o7
Create Date: 2025-12-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'k3l4m5n6o7p8'
down_revision = 'j2k3l4m5n6o7'
branch_labels = None
depends_on = None


def upgrade():
    # Reasignar usuarios con rol 'Plataforma' a rol 'Web' antes de cambiar el constraint
    op.execute("UPDATE users SET role = 'Web' WHERE role = 'Plataforma'")

    # Eliminar constraint antiguo y recrear sin 'Plataforma'
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_constraint('check_user_role', type_='check')
        batch_op.create_check_constraint(
            'check_user_role',
            "role IN ('Master', 'Trader', 'Operador', 'Middle Office', 'App', 'Web')"
        )


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_constraint('check_user_role', type_='check')
        batch_op.create_check_constraint(
            'check_user_role',
            "role IN ('Master', 'Trader', 'Operador', 'Middle Office', 'Plataforma', 'App', 'Web')"
        )
