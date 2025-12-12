"""Add partial docs control fields to clients

Revision ID: m5n6o7p8q9r0
Revises: l4m5n6o7p8q9
Create Date: 2025-12-12 22:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'm5n6o7p8q9r0'
down_revision = 'l4m5n6o7p8q9'
branch_labels = None
depends_on = None


def upgrade():
    # Agregar campos para control de operaciones sin documentos completos
    op.add_column('clients', sa.Column('operations_without_docs_count', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('clients', sa.Column('operations_without_docs_limit', sa.Integer(), nullable=True))
    op.add_column('clients', sa.Column('max_amount_without_docs', sa.Numeric(precision=15, scale=2), nullable=True))
    op.add_column('clients', sa.Column('has_complete_documents', sa.Boolean(), nullable=True, server_default='0'))
    op.add_column('clients', sa.Column('inactive_reason', sa.String(length=200), nullable=True))
    op.add_column('clients', sa.Column('documents_pending_since', sa.DateTime(), nullable=True))


def downgrade():
    # Eliminar las columnas agregadas
    op.drop_column('clients', 'documents_pending_since')
    op.drop_column('clients', 'inactive_reason')
    op.drop_column('clients', 'has_complete_documents')
    op.drop_column('clients', 'max_amount_without_docs')
    op.drop_column('clients', 'operations_without_docs_limit')
    op.drop_column('clients', 'operations_without_docs_count')
