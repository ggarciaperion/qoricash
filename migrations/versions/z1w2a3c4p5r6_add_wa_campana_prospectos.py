"""add wa_campana_prospectos table

Revision ID: z1w2a3c4p5r6
Revises: z9merge_all_heads
Create Date: 2026-11-22

Tabla de tracking de campañas WA enviadas a prospectos de la Fuente de Datos.
Independiente del sistema de email y del chatbot WA.
"""
from alembic import op
import sqlalchemy as sa

revision = 'z1w2a3c4p5r6'
down_revision = 'z9merge_all_heads'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'wa_campana_prospectos',
        sa.Column('id',               sa.Integer(),     primary_key=True),
        sa.Column('prospecto_id',     sa.Integer(),     sa.ForeignKey('prospectos.id'), nullable=True),
        sa.Column('numero',           sa.String(25),    nullable=False),
        sa.Column('nombre',           sa.String(150),   nullable=True,  server_default=''),
        sa.Column('empresa',          sa.String(300),   nullable=True,  server_default=''),
        sa.Column('wa_validado',      sa.String(20),    nullable=False, server_default='sin_validar'),
        sa.Column('fecha_validacion', sa.DateTime(),    nullable=True),
        sa.Column('campana',          sa.String(100),   nullable=False),
        sa.Column('plantilla',        sa.String(100),   nullable=False),
        sa.Column('compra',           sa.String(10),    nullable=True,  server_default=''),
        sa.Column('venta',            sa.String(10),    nullable=True,  server_default=''),
        sa.Column('wa_id',            sa.String(120),   nullable=True),
        sa.Column('estado',           sa.String(20),    nullable=False, server_default='pendiente'),
        sa.Column('error_msg',        sa.Text(),        nullable=True),
        sa.Column('fecha_envio',      sa.DateTime(),    nullable=True),
        sa.Column('fecha_entregado',  sa.DateTime(),    nullable=True),
        sa.Column('fecha_leido',      sa.DateTime(),    nullable=True),
        sa.Column('enviado_por',      sa.Integer(),     sa.ForeignKey('users.id'), nullable=True),
        sa.Column('creado_en',        sa.DateTime(),    nullable=False),
        sa.Column('actualizado_en',   sa.DateTime(),    nullable=False),
    )
    op.create_index('ix_wa_campana_numero',    'wa_campana_prospectos', ['numero'])
    op.create_index('ix_wa_campana_campana',   'wa_campana_prospectos', ['campana'])
    op.create_index('ix_wa_campana_estado',    'wa_campana_prospectos', ['estado'])
    op.create_index('ix_wa_campana_wa_id',     'wa_campana_prospectos', ['wa_id'])
    op.create_index('ix_wa_campana_prosp_id',  'wa_campana_prospectos', ['prospecto_id'])
    op.create_unique_constraint('uq_wa_campana_numero', 'wa_campana_prospectos', ['numero', 'campana'])


def downgrade():
    op.drop_table('wa_campana_prospectos')
