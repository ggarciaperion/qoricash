"""add invoices table for electronic invoicing

Revision ID: 20251216_invoices
Revises: 20251212_add_partial_docs_control_fields
Create Date: 2025-12-16 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251216_invoices'
down_revision = '20251212_add_partial_docs_control_fields'
branch_labels = None
depends_on = None


def upgrade():
    # Crear tabla invoices
    op.create_table('invoices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('operation_id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('invoice_type', sa.String(length=20), nullable=False),
        sa.Column('serie', sa.String(length=10), nullable=True),
        sa.Column('numero', sa.String(length=20), nullable=True),
        sa.Column('invoice_number', sa.String(length=50), nullable=True),
        sa.Column('emisor_ruc', sa.String(length=11), nullable=False),
        sa.Column('emisor_razon_social', sa.String(length=200), nullable=False),
        sa.Column('emisor_direccion', sa.String(length=300), nullable=True),
        sa.Column('cliente_tipo_documento', sa.String(length=10), nullable=True),
        sa.Column('cliente_numero_documento', sa.String(length=20), nullable=False),
        sa.Column('cliente_denominacion', sa.String(length=200), nullable=False),
        sa.Column('cliente_direccion', sa.String(length=300), nullable=True),
        sa.Column('cliente_email', sa.String(length=120), nullable=True),
        sa.Column('descripcion', sa.Text(), nullable=True),
        sa.Column('monto_total', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('moneda', sa.String(length=10), nullable=True, server_default='PEN'),
        sa.Column('gravada', sa.Numeric(precision=15, scale=2), nullable=True, server_default='0'),
        sa.Column('exonerada', sa.Numeric(precision=15, scale=2), nullable=True, server_default='0'),
        sa.Column('igv', sa.Numeric(precision=15, scale=2), nullable=True, server_default='0'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='Pendiente'),
        sa.Column('nubefact_response', sa.Text(), nullable=True),
        sa.Column('nubefact_enlace_pdf', sa.String(length=500), nullable=True),
        sa.Column('nubefact_enlace_xml', sa.String(length=500), nullable=True),
        sa.Column('nubefact_aceptada_por_sunat', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('nubefact_sunat_description', sa.Text(), nullable=True),
        sa.Column('nubefact_sunat_note', sa.Text(), nullable=True),
        sa.Column('nubefact_codigo_hash', sa.String(length=200), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('accepted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['operation_id'], ['operations.id'], ),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Crear índices
    op.create_index(op.f('ix_invoices_operation_id'), 'invoices', ['operation_id'], unique=False)
    op.create_index(op.f('ix_invoices_client_id'), 'invoices', ['client_id'], unique=False)
    op.create_index(op.f('ix_invoices_invoice_number'), 'invoices', ['invoice_number'], unique=False)
    op.create_index(op.f('ix_invoices_status'), 'invoices', ['status'], unique=False)
    op.create_index(op.f('ix_invoices_created_at'), 'invoices', ['created_at'], unique=False)


def downgrade():
    # Eliminar índices
    op.drop_index(op.f('ix_invoices_created_at'), table_name='invoices')
    op.drop_index(op.f('ix_invoices_status'), table_name='invoices')
    op.drop_index(op.f('ix_invoices_invoice_number'), table_name='invoices')
    op.drop_index(op.f('ix_invoices_client_id'), table_name='invoices')
    op.drop_index(op.f('ix_invoices_operation_id'), table_name='invoices')

    # Eliminar tabla
    op.drop_table('invoices')
