"""Add canonical sync columns from CONTRATO_LOTES.md

Revision ID: ec05_sync_columns
Revises: ec04_lotes_schema_fix
Create Date: 2026-11-09

PROPÓSITO
---------
Agrega las columnas del contrato canónico T1/T3 que faltaban en ec02/ec04:

  ec_lotes:
    es_prueba              INTEGER  — 1 = lote de simulación, excluir de métricas reales
    seleccion_completada_en TEXT    — NULL = etapa no completada
    validacion_completada_en TEXT   — NULL = etapa no completada
    asignacion_completada_en TEXT   — NULL = gate no aprobado → reservar_para_envio bloqueado
    aceptados_pendientes    INTEGER — Gmail aceptó pero aún no confirmado en DB
    supresion_json          TEXT    — JSON: {"email": N, "dominio": N, ...}
    sync_emitido_en         TIMESTAMPTZ — emitido_en del último payload recibido
    ultima_sync_en          TIMESTAMPTZ — cuándo T3 almacenó el último sync

  ec_lote_items:
    sync_item_id    INTEGER — id del item en SQLite (referencia; no es PK en PG)
    sync_emitido_en TIMESTAMPTZ — emitido_en del payload que creó/actualizó este item

  Constraint único para upsert idempotente:
    ec_lote_items UNIQUE(lote_id, email)

Poblado de es_prueba desde dry_run para registros existentes:
  dry_run=TRUE  → es_prueba=1
  dry_run=FALSE → es_prueba=0

VERIFICACIÓN
------------
  SELECT column_name FROM information_schema.columns
  WHERE table_name = 'ec_lotes' AND column_name = 'es_prueba';

  SELECT COUNT(*) FROM ec_lotes WHERE es_prueba = 1;
"""
from alembic import op


revision      = 'ec05_sync_columns'
down_revision = 'ec04_lotes_schema_fix'
branch_labels = None
depends_on    = None


def upgrade():
    # ═══════════════════════════════════════════════════════════════════════
    # ec_lotes — columnas del contrato
    # ═══════════════════════════════════════════════════════════════════════

    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lotes ADD COLUMN es_prueba INTEGER NOT NULL DEFAULT 0;
        EXCEPTION WHEN duplicate_column THEN NULL; END $$
    """)
    # Poblar desde dry_run para registros existentes
    op.execute("""
        UPDATE ec_lotes
        SET es_prueba = CASE WHEN dry_run = TRUE THEN 1 ELSE 0 END
        WHERE es_prueba = 0 AND dry_run IS NOT NULL
    """)

    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lotes ADD COLUMN seleccion_completada_en TEXT;
        EXCEPTION WHEN duplicate_column THEN NULL; END $$
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lotes ADD COLUMN validacion_completada_en TEXT;
        EXCEPTION WHEN duplicate_column THEN NULL; END $$
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lotes ADD COLUMN asignacion_completada_en TEXT;
        EXCEPTION WHEN duplicate_column THEN NULL; END $$
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lotes ADD COLUMN aceptados_pendientes INTEGER NOT NULL DEFAULT 0;
        EXCEPTION WHEN duplicate_column THEN NULL; END $$
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lotes ADD COLUMN supresion_json TEXT;
        EXCEPTION WHEN duplicate_column THEN NULL; END $$
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lotes ADD COLUMN sync_emitido_en TIMESTAMPTZ;
        EXCEPTION WHEN duplicate_column THEN NULL; END $$
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lotes ADD COLUMN ultima_sync_en TIMESTAMPTZ;
        EXCEPTION WHEN duplicate_column THEN NULL; END $$
    """)

    op.execute("CREATE INDEX IF NOT EXISTS ix_ec_lotes_es_prueba ON ec_lotes (es_prueba)")

    # ═══════════════════════════════════════════════════════════════════════
    # ec_lote_items — sync tracking + unique constraint para upsert
    # ═══════════════════════════════════════════════════════════════════════

    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lote_items ADD COLUMN sync_item_id INTEGER;
        EXCEPTION WHEN duplicate_column THEN NULL; END $$
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lote_items ADD COLUMN sync_emitido_en TIMESTAMPTZ;
        EXCEPTION WHEN duplicate_column THEN NULL; END $$
    """)

    # Unique constraint para ON CONFLICT (lote_id, email) en upsert
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lote_items
            ADD CONSTRAINT ec_lote_items_lote_email_unique UNIQUE (lote_id, email);
        EXCEPTION WHEN duplicate_table THEN NULL;
                 WHEN duplicate_object THEN NULL; END $$
    """)


def downgrade():
    # Solo remueve lo que agregó esta migración; no borra ec02/ec04 columns
    op.execute("DROP INDEX IF EXISTS ix_ec_lotes_es_prueba")
    op.execute("""
        ALTER TABLE ec_lote_items
        DROP CONSTRAINT IF EXISTS ec_lote_items_lote_email_unique
    """)
