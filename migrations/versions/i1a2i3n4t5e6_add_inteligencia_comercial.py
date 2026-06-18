"""add inteligencia comercial tables

Revision ID: i1a2i3n4t5e6
Revises: aa1s2i3n4w5a6
Create Date: 2026-06-18

Crea tablas para el Centro de Inteligencia Comercial IA:
  - email_eventos: log de cada email procesado por los motores automáticos
  - oportunidades_comerciales: oportunidades detectadas por IA
  - ejecuciones_motor: resumen de cada ejecución de motor
"""
from alembic import op
import sqlalchemy as sa

revision = 'i1a2i3n4t5e6'
down_revision = 'aa1s2i3n4w5a6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'email_eventos',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('cuenta', sa.String(100), nullable=False, index=True),
        sa.Column('mensaje_id', sa.String(400), unique=True, index=True, nullable=True),
        sa.Column('remitente', sa.String(300), nullable=True),
        sa.Column('asunto', sa.String(500), nullable=True),
        sa.Column('tipo', sa.String(50), index=True, nullable=True),
        sa.Column('confianza', sa.Float(), server_default='1.0', nullable=True),
        sa.Column('ia_usada', sa.Boolean(), server_default='false', nullable=True),
        sa.Column('ia_tokens', sa.Integer(), server_default='0', nullable=True),
        sa.Column('accion', sa.String(300), nullable=True),
        sa.Column('email_afectado', sa.String(200), nullable=True),
        sa.Column('email_nuevo', sa.String(200), nullable=True),
        sa.Column('sheets_tab', sa.String(50), nullable=True),
        sa.Column('crm_updated', sa.Boolean(), server_default='false', nullable=True),
        sa.Column('sheets_updated', sa.Boolean(), server_default='false', nullable=True),
        sa.Column('procesado_en', sa.DateTime(), index=True, nullable=True),
    )

    op.create_table(
        'oportunidades_comerciales',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('empresa', sa.String(300), nullable=True),
        sa.Column('contacto', sa.String(200), nullable=True),
        sa.Column('cargo', sa.String(150), nullable=True),
        sa.Column('email', sa.String(200), index=True, nullable=True),
        sa.Column('telefono', sa.String(100), nullable=True),
        sa.Column('sector', sa.String(100), nullable=True),
        sa.Column('prioridad', sa.String(20), index=True, nullable=True),
        sa.Column('score', sa.Integer(), server_default='0', nullable=True),
        sa.Column('volumen_usd_est', sa.Integer(), server_default='0', nullable=True),
        sa.Column('necesidad', sa.Text(), nullable=True),
        sa.Column('recomendacion', sa.Text(), nullable=True),
        sa.Column('cuerpo_email', sa.Text(), nullable=True),
        sa.Column('estado', sa.String(50), index=True, server_default='nuevo', nullable=True),
        sa.Column('cuenta_origen', sa.String(100), nullable=True),
        sa.Column('mensaje_id', sa.String(400), nullable=True),
        sa.Column('prospecto_creado_id', sa.Integer(), sa.ForeignKey('prospectos.id'), nullable=True),
        sa.Column('wa_alerta_enviada', sa.Boolean(), server_default='false', nullable=True),
        sa.Column('detectado_en', sa.DateTime(), index=True, nullable=True),
        sa.Column('actualizado_en', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'ejecuciones_motor',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('motor', sa.String(50), index=True, nullable=True),
        sa.Column('inicio', sa.DateTime(), nullable=True),
        sa.Column('fin', sa.DateTime(), nullable=True),
        sa.Column('duracion_seg', sa.Float(), nullable=True),
        sa.Column('correos_analizados', sa.Integer(), server_default='0', nullable=True),
        sa.Column('rebotes', sa.Integer(), server_default='0', nullable=True),
        sa.Column('oportunidades', sa.Integer(), server_default='0', nullable=True),
        sa.Column('actualizaciones', sa.Integer(), server_default='0', nullable=True),
        sa.Column('no_contactar', sa.Integer(), server_default='0', nullable=True),
        sa.Column('ia_tokens', sa.Integer(), server_default='0', nullable=True),
        sa.Column('ia_costo_usd', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('errores', sa.Integer(), server_default='0', nullable=True),
        sa.Column('estado', sa.String(20), server_default='ok', nullable=True),
        sa.Column('resumen', sa.Text(), nullable=True),
    )


def downgrade():
    op.drop_table('ejecuciones_motor')
    op.drop_table('oportunidades_comerciales')
    op.drop_table('email_eventos')
