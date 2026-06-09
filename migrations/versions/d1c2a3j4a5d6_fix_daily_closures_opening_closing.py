"""Fix daily_closures: add opening/closing/result columns (definitive fix)

Revision ID: d1c2a3j4a5d6
Revises: v1a2l3i4d5a6
Create Date: 2026-06-09

Root cause: migration b1c2a3j4a5d6 was stamped in production (not executed)
because migrate.sh stamps it for DBs with old migration history. This means
the 13 columns it defines were never added to the physical table in PostgreSQL.

This migration is the definitive fix:
  - Uses ADD COLUMN IF NOT EXISTS (100% idempotent, safe to run multiple times)
  - Covers all 13 columns needed for Apertura/Cierre de Día
  - No side effects, no data loss risk
"""
from alembic import op
from sqlalchemy import text

revision    = 'd1c2a3j4a5d6'
down_revision = 'v1a2l3i4d5a6'
branch_labels = None
depends_on    = None

_T = 'daily_closures'


def upgrade():
    conn = op.get_bind()

    # ── Saldo Inicial (Apertura) ──────────────────────────────────────────
    conn.execute(text(
        f"ALTER TABLE {_T} ADD COLUMN IF NOT EXISTS "
        "opening_balance_json TEXT NOT NULL DEFAULT '{}'"
    ))
    conn.execute(text(
        f"ALTER TABLE {_T} ADD COLUMN IF NOT EXISTS "
        "opening_total_usd NUMERIC(15,2) NOT NULL DEFAULT 0"
    ))
    conn.execute(text(
        f"ALTER TABLE {_T} ADD COLUMN IF NOT EXISTS "
        "opening_total_pen NUMERIC(15,2) NOT NULL DEFAULT 0"
    ))
    conn.execute(text(
        f"ALTER TABLE {_T} ADD COLUMN IF NOT EXISTS "
        "opening_registered_at TIMESTAMP WITHOUT TIME ZONE"
    ))
    conn.execute(text(
        f"ALTER TABLE {_T} ADD COLUMN IF NOT EXISTS "
        "opening_registered_by INTEGER REFERENCES users(id)"
    ))

    # ── Saldo Final (Cierre de caja) ──────────────────────────────────────
    conn.execute(text(
        f"ALTER TABLE {_T} ADD COLUMN IF NOT EXISTS "
        "closing_balance_json TEXT NOT NULL DEFAULT '{}'"
    ))
    conn.execute(text(
        f"ALTER TABLE {_T} ADD COLUMN IF NOT EXISTS "
        "closing_total_usd NUMERIC(15,2) NOT NULL DEFAULT 0"
    ))
    conn.execute(text(
        f"ALTER TABLE {_T} ADD COLUMN IF NOT EXISTS "
        "closing_total_pen NUMERIC(15,2) NOT NULL DEFAULT 0"
    ))
    conn.execute(text(
        f"ALTER TABLE {_T} ADD COLUMN IF NOT EXISTS "
        "closing_registered_at TIMESTAMP WITHOUT TIME ZONE"
    ))
    conn.execute(text(
        f"ALTER TABLE {_T} ADD COLUMN IF NOT EXISTS "
        "closing_registered_by INTEGER REFERENCES users(id)"
    ))

    # ── Resultado del día ─────────────────────────────────────────────────
    conn.execute(text(
        f"ALTER TABLE {_T} ADD COLUMN IF NOT EXISTS "
        "result_usd NUMERIC(15,2)"
    ))
    conn.execute(text(
        f"ALTER TABLE {_T} ADD COLUMN IF NOT EXISTS "
        "result_pen NUMERIC(15,2)"
    ))
    conn.execute(text(
        f"ALTER TABLE {_T} ADD COLUMN IF NOT EXISTS "
        "result_label VARCHAR(20)"
    ))


def downgrade():
    # Intentionally a no-op: never drop data columns on downgrade
    pass
