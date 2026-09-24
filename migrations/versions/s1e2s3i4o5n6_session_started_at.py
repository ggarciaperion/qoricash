"""wa_bot_session: add session_started_at for cycle tracking

Distingue sesiones nuevas de conversaciones post-expiración.
El campo se establece por el scheduler (o el handler in-band) cada vez
que una sesión se cierra por inactividad.  NULL = sesión activa/nueva.

Revision ID: s1e2s3i4o5n6
Revises: w1a2b3o4t5s6
Create Date: 2026-09-23
"""
from alembic import op
import sqlalchemy as sa

revision = 's1e2s3i4o5n6'
down_revision = 'w1a2b3o4t5s6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('wa_bot_sessions') as batch_op:
        batch_op.add_column(
            sa.Column('session_started_at', sa.DateTime(), nullable=True)
        )


def downgrade():
    with op.batch_alter_table('wa_bot_sessions') as batch_op:
        batch_op.drop_column('session_started_at')
