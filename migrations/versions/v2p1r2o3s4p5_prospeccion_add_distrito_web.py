"""prospeccion_add_distrito_web

Revision ID: v2p1r2o3s4p5
Revises: s1p2r3o4s5p6
Create Date: 2026-05-25

Agrega columnas distrito y web a la tabla prospectos.
"""
from alembic import op
import sqlalchemy as sa

revision = 'v2p1r2o3s4p5'
down_revision = 's1p2r3o4s5p6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('prospectos', schema=None) as batch_op:
        batch_op.add_column(sa.Column('distrito', sa.String(100), nullable=True))
        batch_op.add_column(sa.Column('web',      sa.String(300), nullable=True))


def downgrade():
    with op.batch_alter_table('prospectos', schema=None) as batch_op:
        batch_op.drop_column('web')
        batch_op.drop_column('distrito')
