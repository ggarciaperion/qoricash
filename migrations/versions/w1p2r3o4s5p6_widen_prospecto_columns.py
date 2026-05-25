"""widen_prospecto_columns

Revision ID: w1p2r3o4s5p6
Revises: v2p1r2o3s4p5
Create Date: 2026-05-25

Amplía columnas de prospectos para soportar valores mergeados largos.
"""
from alembic import op
import sqlalchemy as sa

revision = 'w1p2r3o4s5p6'
down_revision = 'v2p1r2o3s4p5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('prospectos', schema=None) as batch_op:
        batch_op.alter_column('nombre_contacto',
            existing_type=sa.String(200),
            type_=sa.Text(),
            existing_nullable=True)
        batch_op.alter_column('telefono',
            existing_type=sa.String(50),
            type_=sa.String(200),
            existing_nullable=True)
        batch_op.alter_column('telefono_alt',
            existing_type=sa.String(50),
            type_=sa.String(200),
            existing_nullable=True)


def downgrade():
    with op.batch_alter_table('prospectos', schema=None) as batch_op:
        batch_op.alter_column('nombre_contacto',
            existing_type=sa.Text(),
            type_=sa.String(200),
            existing_nullable=True)
        batch_op.alter_column('telefono',
            existing_type=sa.String(200),
            type_=sa.String(50),
            existing_nullable=True)
        batch_op.alter_column('telefono_alt',
            existing_type=sa.String(200),
            type_=sa.String(50),
            existing_nullable=True)
