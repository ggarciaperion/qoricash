"""Remove unique constraint from client email to allow multiple clients with same email

Revision ID: k3l4m5n6o7p8
Revises: j2k3l4m5n6o7
Create Date: 2024-12-05 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'k3l4m5n6o7p8'
down_revision = 'j2k3l4m5n6o7'
branch_labels = None
depends_on = None


def upgrade():
    # Obtener conexión
    conn = op.get_bind()
    inspector = inspect(conn)

    # Buscar el nombre real de la constraint UNIQUE en el campo email
    unique_constraints = inspector.get_unique_constraints('clients')

    constraint_name = None
    for constraint in unique_constraints:
        if 'email' in constraint['column_names']:
            constraint_name = constraint['name']
            break

    # Si se encontró la constraint, eliminarla
    if constraint_name:
        with op.batch_alter_table('clients', schema=None) as batch_op:
            batch_op.drop_constraint(constraint_name, type_='unique')

    # También intentar eliminar el índice único si existe
    try:
        indexes = inspector.get_indexes('clients')
        for index in indexes:
            if 'email' in index['column_names'] and index.get('unique', False):
                op.drop_index(index['name'], table_name='clients')
    except:
        pass  # Si no existe, continuar


def downgrade():
    # Restaurar índice UNIQUE del campo email en la tabla clients
    with op.batch_alter_table('clients', schema=None) as batch_op:
        batch_op.create_unique_constraint('clients_email_key', ['email'])
