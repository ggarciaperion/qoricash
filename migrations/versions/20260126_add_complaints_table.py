"""add complaints table for libro de reclamaciones

Revision ID: 20260126_complaints
Revises: j2k3l4m5n6o7
Create Date: 2026-01-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260126_complaints'
down_revision = 'ref_benefits_001'
branch_labels = None
depends_on = None


def upgrade():
    # Crear tabla complaints
    op.create_table('complaints',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('complaint_number', sa.String(length=20), nullable=False),
        sa.Column('document_type', sa.String(length=10), nullable=False),
        sa.Column('document_number', sa.String(length=20), nullable=False),
        sa.Column('full_name', sa.String(length=300), nullable=True),
        sa.Column('company_name', sa.String(length=300), nullable=True),
        sa.Column('contact_person', sa.String(length=300), nullable=True),
        sa.Column('email', sa.String(length=120), nullable=False),
        sa.Column('phone', sa.String(length=100), nullable=False),
        sa.Column('address', sa.String(length=500), nullable=True),
        sa.Column('complaint_type', sa.String(length=20), nullable=False, server_default='Reclamo'),
        sa.Column('detail', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='Pendiente'),
        sa.Column('response', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['resolved_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("document_type IN ('DNI', 'CE', 'RUC')", name='check_complaint_document_type'),
        sa.CheckConstraint("complaint_type IN ('Reclamo', 'Queja')", name='check_complaint_type'),
        sa.CheckConstraint("status IN ('Pendiente', 'En Revisión', 'Resuelto')", name='check_complaint_status')
    )

    # Crear índices
    op.create_index(op.f('ix_complaints_complaint_number'), 'complaints', ['complaint_number'], unique=True)
    op.create_index(op.f('ix_complaints_document_number'), 'complaints', ['document_number'], unique=False)
    op.create_index(op.f('ix_complaints_status'), 'complaints', ['status'], unique=False)
    op.create_index(op.f('ix_complaints_created_at'), 'complaints', ['created_at'], unique=False)


def downgrade():
    # Eliminar índices
    op.drop_index(op.f('ix_complaints_created_at'), table_name='complaints')
    op.drop_index(op.f('ix_complaints_status'), table_name='complaints')
    op.drop_index(op.f('ix_complaints_document_number'), table_name='complaints')
    op.drop_index(op.f('ix_complaints_complaint_number'), table_name='complaints')

    # Eliminar tabla
    op.drop_table('complaints')
