"""Reset bot_pausado para sesiones sin asesor activo.

bot_pausado=TRUE se establece cuando el cliente pide hablar con un asesor.
Hay sesiones que quedaron con bot_pausado=TRUE indefinidamente porque el
asesor nunca liberó el control. Esto silencia el bot permanentemente para
esos usuarios. Esta migración resetea a FALSE todas las sesiones pausadas
donde el asesor no tuvo actividad en las últimas 4 horas (igual que el
auto-expire del código), restaurando el acceso al bot.

Revision ID: b2o3t4p5a6u7
Revises: a1r2e3s4e5t6
Create Date: 2026-11-20
"""
from alembic import op
import sqlalchemy as sa

revision = 'b2o3t4p5a6u7'
down_revision = 'a1r2e3s4e5t6'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        UPDATE wa_bot_sessions
        SET bot_pausado = FALSE,
            estado_atencion = 'bot'
        WHERE bot_pausado = TRUE
          AND updated_at < NOW() - INTERVAL '4 hours'
    """)


def downgrade():
    # No reversible: no sabemos cuáles eran pausas intencionales.
    pass
