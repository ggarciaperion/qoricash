"""wa_bot_session: add cotizacion fields

Revision ID: w1a2b3o4t5s6
Revises: z9merge_all_heads
Create Date: 2026-07-21
"""
from alembic import op
import sqlalchemy as sa

revision = 'w1a2b3o4t5s6'
down_revision = 'z9merge_all_heads'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('wa_bot_sessions') as batch_op:
        batch_op.add_column(sa.Column('cotiz_op',      sa.String(10),  nullable=True, server_default=''))
        batch_op.add_column(sa.Column('cotiz_importe', sa.Float(),     nullable=True, server_default='0'))
        batch_op.add_column(sa.Column('cotiz_tc',      sa.Float(),     nullable=True, server_default='0'))


def downgrade():
    with op.batch_alter_table('wa_bot_sessions') as batch_op:
        batch_op.drop_column('cotiz_tc')
        batch_op.drop_column('cotiz_importe')
        batch_op.drop_column('cotiz_op')
