"""Add kyc_status and kyc_blocked_at to clients (Progressive KYC)

Revision ID: k1y2c3d4e5f6
Revises: r1e2g3i4s5t6
Create Date: 2026-05-31

Agrega kyc_status y kyc_blocked_at a la tabla clients para el sistema
de onboarding progresivo KYC.

kyc_status:
  'pendiente' - Sin documentos, dentro de límites operativos
  'completo'  - Documentos aprobados, operaciones ilimitadas
  'bloqueado' - Alcanzó límite sin documentación (soft block)

También actualiza max_amount_without_docs a los nuevos límites:
  DNI/CE: $10,000 USD (antes $1,000)
  RUC:    $30,000 USD (antes $1,000)
"""
from alembic import op
from sqlalchemy import text

revision = 'k1y2c3d4e5f6'
down_revision = 'z9merge_all_heads'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # Agregar columna kyc_status
    conn.execute(text(
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS kyc_status VARCHAR(20) NOT NULL DEFAULT 'pendiente'"
    ))

    # Agregar columna kyc_blocked_at
    conn.execute(text(
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS kyc_blocked_at TIMESTAMP"
    ))

    # Backfill kyc_status para clientes existentes
    # Clientes con documentos completos → kyc_status = 'completo'
    conn.execute(text("""
        UPDATE clients
        SET kyc_status = 'completo'
        WHERE has_complete_documents = TRUE
        AND kyc_status = 'pendiente'
    """))

    # Clientes inactivos por documentos → kyc_status = 'bloqueado'
    conn.execute(text("""
        UPDATE clients
        SET kyc_status = 'bloqueado'
        WHERE has_complete_documents = FALSE
        AND inactive_reason ILIKE '%document%'
        AND kyc_status = 'pendiente'
    """))

    # Actualizar max_amount_without_docs a nuevos límites para clientes sin docs
    # RUC (PJ) → $30,000
    conn.execute(text("""
        UPDATE clients
        SET max_amount_without_docs = 30000,
            operations_without_docs_limit = 2
        WHERE document_type = 'RUC'
        AND has_complete_documents = FALSE
        AND kyc_status = 'pendiente'
    """))

    # DNI/CE (PN) → $10,000
    conn.execute(text("""
        UPDATE clients
        SET max_amount_without_docs = 10000,
            operations_without_docs_limit = 2
        WHERE document_type IN ('DNI', 'CE')
        AND has_complete_documents = FALSE
        AND kyc_status = 'pendiente'
    """))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE clients DROP COLUMN IF EXISTS kyc_status"))
    conn.execute(text("ALTER TABLE clients DROP COLUMN IF EXISTS kyc_blocked_at"))
