"""wa_bot_sessions: add cotiz_mod_token and cotiz_nuevo_importe for amount-change confirmation

Revision ID: m1o2d3i4m5p6
Revises: w1a2b3o4t5s6
Create Date: 2026-10-10
"""
from alembic import op
import sqlalchemy as sa

revision = 'm1o2d3i4m5p6'
down_revision = 'w1a2b3o4t5s6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('wa_bot_sessions') as batch_op:
        batch_op.add_column(sa.Column('cotiz_mod_token',     sa.String(36), nullable=True))
        batch_op.add_column(sa.Column('cotiz_nuevo_importe', sa.Float(),    nullable=True, server_default='0'))


def downgrade():
    with op.batch_alter_table('wa_bot_sessions') as batch_op:
        batch_op.drop_column('cotiz_nuevo_importe')
        batch_op.drop_column('cotiz_mod_token')
