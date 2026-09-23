"""wa_bot_session: add Etapa 2/3 columns

Adds the fields required by the chatbot Etapa 2 (identity verification during
quoting) and Etapa 3 (account selection + operation confirmation):

  cotiz_doc       -- DNI/RUC ingresado durante cotizacion
  cotiz_email     -- email capturado para registro inline
  cotiz_op_id     -- operation_id creado (EXP-XXX)
  cotiz_cuenta    -- cuenta destino seleccionada (BANCO|NUMERO)
  cotiz_timestamp -- momento en que se mostro la cotizacion
  cotiz_token     -- UUID corto que identifica la version de cotizacion
  bot_pausado     -- True cuando un asesor toma control manual
  cotiz_intentos  -- contador de mensajes no entendidos consecutivos

Uses inspector for safe IF-NOT-EXISTS semantics so the migration is
idempotent in environments where columns were added manually.

Revision ID: e3t4a5p6a3b4
Revises: f1n2a3l4m5e6
Create Date: 2026-09-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


revision = 'e3t4a5p6a3b4'
down_revision = 'f1n2a3l4m5e6'
branch_labels = None
depends_on = None


def _existing_columns(table_name):
    """Return the set of column names currently in table_name."""
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    return {col['name'] for col in inspector.get_columns(table_name)}


def upgrade():
    existing = _existing_columns('wa_bot_sessions')

    with op.batch_alter_table('wa_bot_sessions') as batch_op:
        if 'cotiz_doc' not in existing:
            batch_op.add_column(sa.Column('cotiz_doc', sa.String(20),
                                          nullable=True, server_default=''))
        if 'cotiz_email' not in existing:
            batch_op.add_column(sa.Column('cotiz_email', sa.String(120),
                                          nullable=True, server_default=''))
        if 'cotiz_op_id' not in existing:
            batch_op.add_column(sa.Column('cotiz_op_id', sa.String(20),
                                          nullable=True, server_default=''))
        if 'cotiz_cuenta' not in existing:
            batch_op.add_column(sa.Column('cotiz_cuenta', sa.String(50),
                                          nullable=True, server_default=''))
        if 'cotiz_timestamp' not in existing:
            batch_op.add_column(sa.Column('cotiz_timestamp', sa.DateTime(),
                                          nullable=True))
        if 'cotiz_token' not in existing:
            batch_op.add_column(sa.Column('cotiz_token', sa.String(36),
                                          nullable=True))
        if 'bot_pausado' not in existing:
            batch_op.add_column(sa.Column('bot_pausado', sa.Boolean(),
                                          nullable=False, server_default=sa.false()))
        if 'cotiz_intentos' not in existing:
            batch_op.add_column(sa.Column('cotiz_intentos', sa.Integer(),
                                          nullable=False, server_default='0'))


def downgrade():
    # No-op: safe downgrade is not possible here.
    #
    # upgrade() uses IF-NOT-EXISTS semantics (inspector check) so it skips
    # columns that already existed before this migration ran. At downgrade time
    # there is no persistent record of which columns were newly added vs.
    # pre-existing, so dropping all eight unconditionally risks destroying data
    # that belongs to a prior migration or a manual addition.
    pass
