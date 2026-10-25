"""Add daily delivery system: entregas_diarias table + new columns on content_proposals

Revision ID: d1a2r3i4o5d6
Revises: c1o2n3t4e5n6
Create Date: 2026-10-25
"""
from alembic import op
import sqlalchemy as sa

revision = 'd1a2r3i4o5d6'
down_revision = 'c1o2n3t4e5n6'
branch_labels = None
depends_on = None


def upgrade():
    # ── New columns on content_proposals ──────────────────────────────────────
    with op.batch_alter_table('content_proposals') as batch:
        batch.add_column(sa.Column('pipeline_id',      sa.Integer(), nullable=True))
        batch.add_column(sa.Column('delivery_type',    sa.String(20), nullable=True))
        # noticia | comercial
        batch.add_column(sa.Column('noticia_category', sa.String(30), nullable=True))
        # nacional | internacional | mercados
        batch.add_column(sa.Column('resource_status',  sa.String(30), nullable=True,
                                   server_default='prompt_listo'))
        # prompt_listo | recurso_pendiente | recurso_cargado |
        # pendiente_aprobacion | aprobado | planificado
        batch.add_column(sa.Column('revisor_notas',    sa.Text(), nullable=True))
        batch.add_column(sa.Column('correcciones',     sa.Text(), nullable=True))  # JSON list
        batch.add_column(sa.Column('retry_count',      sa.Integer(), nullable=True,
                                   server_default='0'))

    # ── entregas_diarias table ─────────────────────────────────────────────────
    op.create_table(
        'entregas_diarias',
        sa.Column('id',            sa.Integer(),    nullable=False),
        sa.Column('fecha',         sa.Date(),       nullable=False),
        sa.Column('pipeline_id',   sa.Integer(),    nullable=True),
        sa.Column('status',        sa.String(30),   nullable=True, default='generando'),
        # generando | listo | parcial | error
        sa.Column('noticias_ok',   sa.Integer(),    nullable=True, default=0),
        sa.Column('comercial_ok',  sa.Integer(),    nullable=True, default=0),
        sa.Column('generado_at',   sa.DateTime(),   nullable=True),
        sa.Column('notas',         sa.Text(),       nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('fecha', name='uq_entregas_diarias_fecha'),
    )


def downgrade():
    op.drop_table('entregas_diarias')
    with op.batch_alter_table('content_proposals') as batch:
        batch.drop_column('retry_count')
        batch.drop_column('correcciones')
        batch.drop_column('revisor_notas')
        batch.drop_column('resource_status')
        batch.drop_column('noticia_category')
        batch.drop_column('delivery_type')
        batch.drop_column('pipeline_id')
