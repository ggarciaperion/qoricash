"""Ensure bank_movements table exists with all required columns

Revision ID: p1a2t3c4h5b6
Revises: c1m2e3r4g5e6
Create Date: 2026-06-08

Patch de emergencia: garantiza que bank_movements tenga el esquema completo
requerido por el modelo BankMovement, independientemente de cómo se creó la tabla.

Usa SQL nativo con IF NOT EXISTS para ser 100% idempotente:
  - Crea la tabla si no existe (con todos los campos actuales)
  - Agrega columnas faltantes si la tabla ya existe
  - No falla nunca en un segundo run

Columnas críticas que deben existir:
  bank_key, source_type, source_id, operation_id, description,
  reference_code, counterpart, balance_after, created_by, created_at,
  is_validated, closure_date
"""
from alembic import op
from sqlalchemy import text

revision = 'p1a2t3c4h5b6'
down_revision = 'c1m2e3r4g5e6'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # ── 1. Crear tabla si no existe ───────────────────────────────────────────
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS bank_movements (
            id              SERIAL PRIMARY KEY,
            movement_date   TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
            bank_name       VARCHAR(100) NOT NULL DEFAULT '',
            bank_key        VARCHAR(20)  NOT NULL DEFAULT '',
            currency        VARCHAR(3)   NOT NULL DEFAULT 'USD',
            amount          NUMERIC(15, 2) NOT NULL DEFAULT 0,
            movement_type   VARCHAR(50)  NOT NULL DEFAULT '',
            source_type     VARCHAR(50),
            source_id       INTEGER,
            operation_id    INTEGER,
            description     VARCHAR(500),
            reference_code  VARCHAR(100),
            counterpart     VARCHAR(200),
            balance_after   NUMERIC(15, 2),
            created_by      INTEGER,
            created_at      TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
            is_validated    BOOLEAN NOT NULL DEFAULT false,
            closure_date    DATE
        )
    """))

    # ── 2. Agregar columnas faltantes (idempotente con IF NOT EXISTS) ─────────
    # Columnas que podrían faltar si la tabla fue creada con un modelo antiguo

    conn.execute(text(
        "ALTER TABLE bank_movements ADD COLUMN IF NOT EXISTS "
        "bank_key VARCHAR(20) NOT NULL DEFAULT ''"
    ))
    conn.execute(text(
        "ALTER TABLE bank_movements ADD COLUMN IF NOT EXISTS "
        "source_type VARCHAR(50)"
    ))
    conn.execute(text(
        "ALTER TABLE bank_movements ADD COLUMN IF NOT EXISTS "
        "source_id INTEGER"
    ))
    conn.execute(text(
        "ALTER TABLE bank_movements ADD COLUMN IF NOT EXISTS "
        "operation_id INTEGER"
    ))
    conn.execute(text(
        "ALTER TABLE bank_movements ADD COLUMN IF NOT EXISTS "
        "description VARCHAR(500)"
    ))
    conn.execute(text(
        "ALTER TABLE bank_movements ADD COLUMN IF NOT EXISTS "
        "reference_code VARCHAR(100)"
    ))
    conn.execute(text(
        "ALTER TABLE bank_movements ADD COLUMN IF NOT EXISTS "
        "counterpart VARCHAR(200)"
    ))
    conn.execute(text(
        "ALTER TABLE bank_movements ADD COLUMN IF NOT EXISTS "
        "balance_after NUMERIC(15, 2)"
    ))
    conn.execute(text(
        "ALTER TABLE bank_movements ADD COLUMN IF NOT EXISTS "
        "created_by INTEGER"
    ))
    conn.execute(text(
        "ALTER TABLE bank_movements ADD COLUMN IF NOT EXISTS "
        "created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()"
    ))

    # ── CRÍTICOS: los que causan el error actual ──────────────────────────────
    conn.execute(text(
        "ALTER TABLE bank_movements ADD COLUMN IF NOT EXISTS "
        "is_validated BOOLEAN NOT NULL DEFAULT false"
    ))
    conn.execute(text(
        "ALTER TABLE bank_movements ADD COLUMN IF NOT EXISTS "
        "closure_date DATE"
    ))

    # ── 3. Indexes ────────────────────────────────────────────────────────────
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_bank_movements_movement_date
        ON bank_movements (movement_date)
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_bank_movements_bank_name
        ON bank_movements (bank_name)
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_bank_movements_bank_key
        ON bank_movements (bank_key)
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_bank_movements_operation_id
        ON bank_movements (operation_id)
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_bm_closure_date
        ON bank_movements (closure_date)
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_bm_bank_currency_date
        ON bank_movements (bank_key, currency, movement_date)
    """))


def downgrade():
    # No-op: no eliminamos columnas en downgrade para no perder datos
    pass
