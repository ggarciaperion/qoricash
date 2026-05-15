"""prospeccion_crm_upgrade

Revision ID: s1p2r3o4s5p6
Revises: r1e2g3i4s5t6
Create Date: 2026-05-15

Agrega campos CRM avanzados a prospectos y tabla prospecto_emails.
"""
from alembic import op
import sqlalchemy as sa

revision = 's1p2r3o4s5p6'
down_revision = 'r1e2g3i4s5t6'
branch_labels = None
depends_on = None


def upgrade():
    # Nuevos campos en prospectos
    with op.batch_alter_table('prospectos', schema=None) as batch_op:
        batch_op.add_column(sa.Column('telefono_alt', sa.String(50), nullable=True))
        batch_op.add_column(sa.Column('tamano_empresa', sa.String(30), nullable=True))
        batch_op.add_column(sa.Column('volumen_estimado_usd', sa.Numeric(15, 2), nullable=True))
        batch_op.add_column(sa.Column('prioridad', sa.String(20), nullable=True))

    # Nueva tabla para múltiples emails por prospecto
    op.create_table(
        'prospecto_emails',
        sa.Column('id',           sa.Integer(),      nullable=False),
        sa.Column('prospecto_id', sa.Integer(),      nullable=False),
        sa.Column('email',        sa.String(200),    nullable=False),
        sa.Column('activo',       sa.Boolean(),      nullable=True, server_default=sa.true()),
        sa.Column('creado_en',    sa.DateTime(),     nullable=True),
        sa.ForeignKeyConstraint(['prospecto_id'], ['prospectos.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_prospecto_email_pid', 'prospecto_emails', ['prospecto_id'])


def downgrade():
    op.drop_index('idx_prospecto_email_pid', table_name='prospecto_emails')
    op.drop_table('prospecto_emails')
    with op.batch_alter_table('prospectos', schema=None) as batch_op:
        batch_op.drop_column('prioridad')
        batch_op.drop_column('volumen_estimado_usd')
        batch_op.drop_column('tamano_empresa')
        batch_op.drop_column('telefono_alt')
