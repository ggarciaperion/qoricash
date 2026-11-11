"""Add dry_run to agent_heartbeat — scheduler sends envíos habilitados/deshabilitados

Revision ID: ec06_agent_heartbeat_dry_run
Revises: ec05_sync_columns
Create Date: 2026-11-10

Columna:
  agent_heartbeat.dry_run  INTEGER DEFAULT NULL
    NULL  → desconocido (agente nunca indicó su configuración)
    1     → dry_run activo  → envíos deshabilitados
    0     → dry_run inactivo → envíos habilitados

Migración idempotente: usa ADD COLUMN IF NOT EXISTS.
Es segura tanto en bases donde la columna NO existe (producción, staging)
como en bases donde ya se añadió manualmente (dev local).

No usa downgrade destructivo; el downgrade simplemente intenta eliminar la
columna con IF EXISTS para no romper bases que nunca la tuvieron.
"""
from alembic import op


revision      = 'ec06_agent_heartbeat_dry_run'
down_revision = 'ec05_sync_columns'
branch_labels = None
depends_on    = None


def upgrade():
    # Safety net: create agent_heartbeat if ec01 didn't run (e.g. graph topology edge case)
    op.execute("""
        CREATE TABLE IF NOT EXISTS agent_heartbeat (
            agent          TEXT PRIMARY KEY,
            last_seen      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            status         TEXT NOT NULL DEFAULT 'offline',
            current_run_id BIGINT,
            pid            INTEGER,
            hostname       TEXT,
            updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        ALTER TABLE agent_heartbeat
        ADD COLUMN IF NOT EXISTS dry_run INTEGER DEFAULT NULL
    """)


def downgrade():
    op.execute("""
        ALTER TABLE agent_heartbeat
        DROP COLUMN IF EXISTS dry_run
    """)
