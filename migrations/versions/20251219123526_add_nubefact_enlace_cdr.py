"""add nubefact_enlace_cdr

Revision ID: 20251219123526
Revises:
Create Date: 2025-12-19 12:35:26

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251219123526'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Agregar columna nubefact_enlace_cdr a la tabla invoices
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.add_column(sa.Column('nubefact_enlace_cdr', sa.String(length=500), nullable=True))


def downgrade():
    # Eliminar columna nubefact_enlace_cdr de la tabla invoices
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.drop_column('nubefact_enlace_cdr')
