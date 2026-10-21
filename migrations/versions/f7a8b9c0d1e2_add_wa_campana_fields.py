"""Add wa campana fields to wa_bot_sessions

Revision ID: f7a8b9c0d1e2
Revises: n1e2w3t4a5b6
Create Date: 2026-10-10

Agrega 4 columnas para gestionar la secuencia de campaña de reactivación WA:
  - opt_out_wa          : contacto pidió no recibir más mensajes de campaña
  - campana_secuencia   : cuántos mensajes de la secuencia se han enviado (0-4)
  - campana_ultimo_envio: timestamp del último envío de campaña
  - campana_pausada     : pausa manual para este contacto específico
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


# revision identifiers, used by Alembic.
revision = 'f7a8b9c0d1e2'
down_revision = 'n1e2w3t4a5b6'
branch_labels = None
depends_on = None


def _col_exists(conn, table, column):
    cols = [c['name'] for c in inspect(conn).get_columns(table)]
    return column in cols


def upgrade():
    conn = op.get_bind()

    new_cols = [
        ('opt_out_wa',           sa.Boolean(),  False),
        ('campana_secuencia',    sa.Integer(),  0),
        ('campana_ultimo_envio', sa.DateTime(), None),
        ('campana_pausada',      sa.Boolean(),  False),
    ]

    for col_name, col_type, default in new_cols:
        if not _col_exists(conn, 'wa_bot_sessions', col_name):
            op.add_column(
                'wa_bot_sessions',
                sa.Column(col_name, col_type, nullable=True),
            )
            # Establecer valor por defecto para filas existentes
            if default is not None:
                conn.execute(
                    text(f"UPDATE wa_bot_sessions SET {col_name} = :val WHERE {col_name} IS NULL"),
                    {'val': default},
                )


def downgrade():
    for col_name in ('campana_pausada', 'campana_ultimo_envio', 'campana_secuencia', 'opt_out_wa'):
        op.drop_column('wa_bot_sessions', col_name)
