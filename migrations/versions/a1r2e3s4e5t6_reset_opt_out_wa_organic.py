"""Reset opt_out_wa para sesiones bloqueadas por conversaciones orgánicas.

El flag opt_out_wa fue usado incorrectamente para silenciar el bot ante
cualquier mensaje entrante. La corrección (wa_bot.py) lo elimina: el bot
ahora siempre responde mensajes entrantes, opt_out_wa solo aplica a campañas
salientes. Esta migración resetea a FALSE todos los registros que tengan
opt_out_wa = TRUE para restaurar el acceso al bot a usuarios activos.

Revision ID: a1r2e3s4e5t6
Revises: z9merge_all_heads
Create Date: 2026-11-20
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1r2e3s4e5t6'
down_revision = 'z9merge_all_heads'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "UPDATE wa_bot_sessions SET opt_out_wa = FALSE WHERE opt_out_wa = TRUE"
    )


def downgrade():
    # No reversible: no sabemos cuáles eran True por campaña vs por bug.
    pass
