"""add_prospeccion_module

Revision ID: p1r2o3s4p5e6
Revises:
Create Date: 2026-05-08

"""
from alembic import op
import sqlalchemy as sa

revision = 'p1r2o3s4p5e6'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Tabla prospectos
    op.create_table(
        'prospectos',
        sa.Column('id',                     sa.Integer(),     nullable=False),
        sa.Column('razon_social',           sa.String(300),   nullable=True),
        sa.Column('ruc',                    sa.String(20),    nullable=True),
        sa.Column('tipo',                   sa.String(50),    nullable=True),
        sa.Column('rubro',                  sa.String(150),   nullable=True),
        sa.Column('departamento',           sa.String(100),   nullable=True),
        sa.Column('provincia',              sa.String(100),   nullable=True),
        sa.Column('nombre_contacto',        sa.String(200),   nullable=True),
        sa.Column('cargo',                  sa.String(150),   nullable=True),
        sa.Column('email',                  sa.String(200),   nullable=True),
        sa.Column('email_alt',              sa.String(200),   nullable=True),
        sa.Column('telefono',               sa.String(50),    nullable=True),
        sa.Column('cliente_lfc',            sa.String(50),    nullable=True),
        sa.Column('score',                  sa.Integer(),     nullable=True),
        sa.Column('clasificacion',          sa.String(80),    nullable=True),
        sa.Column('canal',                  sa.String(80),    nullable=True),
        sa.Column('fuente',                 sa.String(80),    nullable=True),
        sa.Column('remitente',              sa.String(100),   nullable=True),
        sa.Column('tipo_ultimo_envio',      sa.String(80),    nullable=True),
        sa.Column('fecha_primer_contacto',  sa.String(30),    nullable=True),
        sa.Column('fecha_ultimo_contacto',  sa.String(30),    nullable=True),
        sa.Column('fecha_proximo_contacto', sa.String(30),    nullable=True),
        sa.Column('num_contactos',          sa.Integer(),     nullable=True),
        sa.Column('estado_email',           sa.String(80),    nullable=True),
        sa.Column('estado_comercial',       sa.String(80),    nullable=True),
        sa.Column('nivel_interes',          sa.String(80),    nullable=True),
        sa.Column('grupo',                  sa.String(80),    nullable=True),
        sa.Column('notas',                  sa.Text(),        nullable=True),
        sa.Column('creado_en',              sa.DateTime(),    nullable=True),
        sa.Column('actualizado_en',         sa.DateTime(),    nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_prospectos_email', 'prospectos', ['email'])
    op.create_index('ix_prospectos_ruc',   'prospectos', ['ruc'])

    # Tabla asignaciones_prospecto
    op.create_table(
        'asignaciones_prospecto',
        sa.Column('id',           sa.Integer(),  nullable=False),
        sa.Column('prospecto_id', sa.Integer(),  nullable=False),
        sa.Column('trader_id',    sa.Integer(),  nullable=False),
        sa.Column('activo',       sa.Boolean(),  nullable=True),
        sa.Column('asignado_por', sa.Integer(),  nullable=True),
        sa.Column('asignado_en',  sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['prospecto_id'], ['prospectos.id']),
        sa.ForeignKeyConstraint(['trader_id'],    ['users.id']),
        sa.ForeignKeyConstraint(['asignado_por'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('prospecto_id', 'trader_id', name='uq_asignacion'),
    )
    op.create_index('ix_asignaciones_prospecto_id', 'asignaciones_prospecto', ['prospecto_id'])
    op.create_index('ix_asignaciones_trader_id',    'asignaciones_prospecto', ['trader_id'])

    # Tabla actividades_prospecto
    op.create_table(
        'actividades_prospecto',
        sa.Column('id',           sa.Integer(),  nullable=False),
        sa.Column('prospecto_id', sa.Integer(),  nullable=False),
        sa.Column('user_id',      sa.Integer(),  nullable=False),
        sa.Column('tipo',         sa.String(50), nullable=True),
        sa.Column('descripcion',  sa.Text(),     nullable=True),
        sa.Column('resultado',    sa.String(200),nullable=True),
        sa.Column('nuevo_estado', sa.String(80), nullable=True),
        sa.Column('creado_en',    sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['prospecto_id'], ['prospectos.id']),
        sa.ForeignKeyConstraint(['user_id'],      ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_actividades_prospecto_id', 'actividades_prospecto', ['prospecto_id'])


def downgrade():
    op.drop_table('actividades_prospecto')
    op.drop_table('asignaciones_prospecto')
    op.drop_table('prospectos')
