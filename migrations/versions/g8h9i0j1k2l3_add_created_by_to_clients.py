"""add created_by to clients

Revision ID: g8h9i0j1k2l3
Revises: f7g8h9i0j1k2
Create Date: 2025-11-28 01:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'g8h9i0j1k2l3'
down_revision = 'f7g8h9i0j1k2'
branch_labels = None
depends_on = None


def upgrade():
    # Agregar columna created_by a la tabla clients
    op.add_column('clients', sa.Column('created_by', sa.Integer(), nullable=True))

    # Agregar foreign key
    op.create_foreign_key(
        'fk_clients_created_by_users',
        'clients', 'users',
        ['created_by'], ['id']
    )


def downgrade():
    # Remover foreign key
    op.drop_constraint('fk_clients_created_by_users', 'clients', type_='foreignkey')

    # Remover columna
    op.drop_column('clients', 'created_by')
