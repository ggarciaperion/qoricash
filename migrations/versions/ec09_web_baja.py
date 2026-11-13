"""Add ec_web_baja table for web unsubscribe requests

Revision ID: ec09_web_baja
Revises: ec08_rebote_tipo
Create Date: 2026-11-12

Tabla ec_web_baja:
  Registra solicitudes de baja recibidas desde www.qoricash.pe/baja.
  El motor las lee via GET /api/sync/baja?since=... y llama add_suppression()
  localmente en ecosistema.db.

  email     TEXT UNIQUE — destinatario que solicitó baja
  creado_en TIMESTAMPTZ — cuándo se registró (DEFAULT NOW())
  ip_origen TEXT        — IP del visitante web (para auditoría)

Migración idempotente: usa CREATE TABLE IF NOT EXISTS.
"""
from alembic import op


revision      = 'ec09_web_baja'
down_revision = 'ec08_rebote_tipo'
branch_labels = None
depends_on    = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS ec_web_baja (
            id        SERIAL PRIMARY KEY,
            email     TEXT NOT NULL,
            creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            ip_origen TEXT,
            CONSTRAINT ec_web_baja_email_uq UNIQUE (email)
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_ec_web_baja_creado_en
            ON ec_web_baja (creado_en)
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS ec_web_baja")
