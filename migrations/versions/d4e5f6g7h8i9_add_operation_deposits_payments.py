"""Add client deposits, payments and operator proofs to operations

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2025-11-20
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'd4e5f6g7h8i9'
down_revision = 'c3d4e5f6g7h8'
branch_labels = None
depends_on = None


def upgrade():
    # Agregar nuevas columnas a la tabla operations
    with op.batch_alter_table('operations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('client_deposits_json', sa.Text(), nullable=True, server_default='[]'))
        batch_op.add_column(sa.Column('client_payments_json', sa.Text(), nullable=True, server_default='[]'))
        batch_op.add_column(sa.Column('operator_proofs_json', sa.Text(), nullable=True, server_default='[]'))
        batch_op.add_column(sa.Column('modification_logs_json', sa.Text(), nullable=True, server_default='[]'))
        batch_op.add_column(sa.Column('operator_comments', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('operations', schema=None) as batch_op:
        batch_op.drop_column('operator_comments')
        batch_op.drop_column('modification_logs_json')
        batch_op.drop_column('operator_proofs_json')
        batch_op.drop_column('client_payments_json')
        batch_op.drop_column('client_deposits_json')
