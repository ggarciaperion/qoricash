"""add assigned_operator_id to operations

Revision ID: add_assigned_operator
Revises: in_process_since_001
Create Date: 2025-11-27

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_assigned_operator'
down_revision = 'in_process_since_001'
branch_labels = None
depends_on = None


def upgrade():
    """Agregar campo assigned_operator_id a la tabla operations"""
    op.add_column('operations', sa.Column('assigned_operator_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_operations_assigned_operator', 'operations', 'users', ['assigned_operator_id'], ['id'])


def downgrade():
    """Revertir cambios - eliminar campo assigned_operator_id"""
    op.drop_constraint('fk_operations_assigned_operator', 'operations', type_='foreignkey')
    op.drop_column('operations', 'assigned_operator_id')
