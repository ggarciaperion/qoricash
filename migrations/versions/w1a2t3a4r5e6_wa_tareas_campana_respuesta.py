"""wa_tareas + campana respuesta cols

Revision ID: w1a2t3a4r5e6
Revises: r1u2c3r4e5s6
Create Date: 2026-11-24
"""
from alembic import op
import sqlalchemy as sa

revision = 'w1a2t3a4r5e6'
down_revision = 'r1u2c3r4e5s6'
branch_labels = None
depends_on = None


def upgrade():
    # Tabla wa_tareas
    op.create_table(
        'wa_tareas',
        sa.Column('id',            sa.Integer(),    primary_key=True),
        sa.Column('numero',        sa.String(25),   nullable=False),
        sa.Column('descripcion',   sa.Text(),       nullable=False),
        sa.Column('fecha_prog',    sa.Date(),       nullable=True),
        sa.Column('completado',    sa.Boolean(),    nullable=False, server_default='false'),
        sa.Column('completado_en', sa.DateTime(),   nullable=True),
        sa.Column('creado_por',    sa.Integer(),    sa.ForeignKey('users.id'), nullable=True),
        sa.Column('creado_en',     sa.DateTime(),   nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_wa_tareas_numero',     'wa_tareas', ['numero'])
    op.create_index('ix_wa_tareas_fecha_prog', 'wa_tareas', ['fecha_prog'])

    # Columnas en wa_campana_prospectos
    op.add_column('wa_campana_prospectos',
        sa.Column('respondio_en',  sa.DateTime(),    nullable=True))
    op.add_column('wa_campana_prospectos',
        sa.Column('respuesta_btn', sa.String(200),   nullable=True))


def downgrade():
    op.drop_column('wa_campana_prospectos', 'respuesta_btn')
    op.drop_column('wa_campana_prospectos', 'respondio_en')
    op.drop_index('ix_wa_tareas_fecha_prog', table_name='wa_tareas')
    op.drop_index('ix_wa_tareas_numero', table_name='wa_tareas')
    op.drop_table('wa_tareas')
