"""add sin_whatsapp to prospectos

Revision ID: aa1s2i3n4w5a6
Revises: w1p2r3o4s5p6
Create Date: 2026-06-10

Agrega columna sin_whatsapp (Boolean) a prospectos para marcar
numeros que no tienen WhatsApp registrado.
"""
from alembic import op
import sqlalchemy as sa

revision = 'aa1s2i3n4w5a6'
down_revision = 'y1u2s3e4r5s6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('prospectos', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sin_whatsapp', sa.Boolean(), nullable=True, server_default='false'))


def downgrade():
    with op.batch_alter_table('prospectos', schema=None) as batch_op:
        batch_op.drop_column('sin_whatsapp')
