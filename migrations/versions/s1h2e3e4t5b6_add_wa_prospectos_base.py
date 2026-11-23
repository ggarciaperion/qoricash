"""add wa_prospectos_base table

Revision ID: s1h2e3e4t5b6
Revises: z1w2a3c4p5r6
Create Date: 2026-11-23

Tabla de prospectos sincronizados desde la Fuente de Datos (Google Sheet).
Contactos que ya recibieron email y tienen teléfono disponible para WA follow-up.
"""
from alembic import op
import sqlalchemy as sa

revision = 's1h2e3e4t5b6'
down_revision = 'z1w2a3c4p5r6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'wa_prospectos_base',
        sa.Column('id',            sa.Integer(),     nullable=False),
        sa.Column('numero',        sa.String(15),    nullable=False),
        sa.Column('nombre',        sa.String(200),   nullable=True),
        sa.Column('empresa',       sa.String(300),   nullable=True),
        sa.Column('rubro',         sa.String(100),   nullable=True),
        sa.Column('bandeja_email', sa.String(20),    nullable=True),
        sa.Column('fecha_email',   sa.DateTime(),    nullable=True),
        sa.Column('wa_validado',   sa.String(20),    nullable=True, server_default='sin_historial'),
        sa.Column('actualizado_en',sa.DateTime(),    nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('numero', name='uq_wa_prospectos_base_numero'),
    )
    op.create_index('ix_wa_prospectos_base_numero', 'wa_prospectos_base', ['numero'])
    op.create_index('ix_wa_prospectos_base_wa_validado', 'wa_prospectos_base', ['wa_validado'])


def downgrade():
    op.drop_index('ix_wa_prospectos_base_wa_validado', table_name='wa_prospectos_base')
    op.drop_index('ix_wa_prospectos_base_numero', table_name='wa_prospectos_base')
    op.drop_table('wa_prospectos_base')
