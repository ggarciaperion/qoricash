"""Corrective schema migration: align ec_lotes/ec_lote_items with T1 canonical schema

Revision ID: ec04_lotes_schema_fix
Revises: ec03_lotes_test_seed
Create Date: 2026-11-09

PROPÓSITO
---------
ec02_lotes fue creado con un schema incompatible con el schema canónico T1
(ecosistema_db.py). Esta migración lo corrige PRESERVANDO todos los registros,
IDs e historial existente.

No usa DROP TABLE ni DROP COLUMN. Agrega columnas nuevas, mapea datos de
columnas existentes, actualiza valores de estado y reemplaza CHECK constraints.

ESTRATEGIA
----------
Cada ALTER se envuelve en DO $$ ... EXCEPTION WHEN duplicate_column ... END $$
para ser idempotente. Se puede aplicar múltiples veces sin riesgo.

Los valores de estado se migran ANTES de reemplazar los CHECK constraints.

VERIFICACIÓN PRE-MIGRACIÓN (ejecutar antes de aplicar)
------------------------------------------------------
  SELECT version_num FROM alembic_version;
  SELECT estado, dry_run, COUNT(*) FROM ec_lotes GROUP BY estado, dry_run;
  SELECT estado_envio, COUNT(*) FROM ec_lote_items GROUP BY estado_envio;

VERIFICACIÓN POST-MIGRACIÓN
---------------------------
  SELECT estado, COUNT(*) FROM ec_lotes GROUP BY estado;
  SELECT estado_envio, COUNT(*) FROM ec_lote_items GROUP BY estado_envio;
  SELECT COUNT(*) FROM ec_lote_items WHERE bandeja_asignada IS NOT NULL;
  SELECT COUNT(*) FROM ec_lote_items WHERE estado_validacion != 'sin_validar';

COORDINACIÓN T1
---------------
Después de esta migración, T1 debe:
  1. Escribir en ec_lotes via PostgreSQL (no solo SQLite local)
  2. Poblar lote_id con formato 'YYYY-MM-DD-X' (ej. '2026-11-09-A')
  3. Setear dry_run=TRUE para simulaciones, dry_run=FALSE para lotes reales
  4. Escribir en agent_heartbeat en PostgreSQL para que el panel detecte
     que el worker Mac está activo (actualmente solo Render puede actualizarlo)

HEARTBEAT
---------
El panel muestra 'Sin conexión' si agent_heartbeat[agent='orchestrator']
tiene last_seen > 5 min o no existe. El worker Mac debe escribir a PG.
Mientras no esté conectado, el panel siempre mostrará 'Sin conexión'.
"""
from alembic import op


revision      = 'ec04_lotes_schema_fix'
down_revision = 'ec03_lotes_test_seed'
branch_labels = None
depends_on    = None


def upgrade():
    # ═══════════════════════════════════════════════════════════════════════
    # PARTE 1: ec_lotes — agregar columnas del schema canónico T1
    # ═══════════════════════════════════════════════════════════════════════

    # lote_id TEXT — identificador semántico ('2026-11-09-A')
    # Se genera desde fecha+slot_index para lotes existentes.
    # T1 sobrescribirá con el formato canónico al crear nuevos lotes.
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lotes ADD COLUMN lote_id TEXT;
        EXCEPTION WHEN duplicate_column THEN NULL; END $$
    """)
    op.execute("""
        UPDATE ec_lotes
        SET lote_id = fecha::text || '-SLOT' || slot_index::text
        WHERE lote_id IS NULL
    """)
    # Intentar UNIQUE — puede fallar si ya existe, ignorar
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lotes ADD CONSTRAINT ec_lotes_lote_id_unique UNIQUE (lote_id);
        EXCEPTION WHEN duplicate_table THEN NULL;
                 WHEN duplicate_object THEN NULL; END $$
    """)

    # fuente_sheet_id — poblado desde la columna 'fuente' original
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lotes ADD COLUMN fuente_sheet_id TEXT;
        EXCEPTION WHEN duplicate_column THEN NULL; END $$
    """)
    op.execute("""
        UPDATE ec_lotes SET fuente_sheet_id = fuente
        WHERE fuente_sheet_id IS NULL AND fuente IS NOT NULL
    """)

    # fuente_tab — información no disponible en datos existentes
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lotes ADD COLUMN fuente_tab TEXT;
        EXCEPTION WHEN duplicate_column THEN NULL; END $$
    """)

    # fecha_creacion — poblada desde creado_at existente
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lotes ADD COLUMN fecha_creacion TIMESTAMPTZ;
        EXCEPTION WHEN duplicate_column THEN NULL; END $$
    """)
    op.execute("""
        UPDATE ec_lotes SET fecha_creacion = creado_at
        WHERE fecha_creacion IS NULL AND creado_at IS NOT NULL
    """)
    op.execute("""
        UPDATE ec_lotes SET fecha_creacion = NOW()
        WHERE fecha_creacion IS NULL
    """)

    # creado_por — nueva columna
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lotes ADD COLUMN creado_por TEXT;
        EXCEPTION WHEN duplicate_column THEN NULL; END $$
    """)

    # cupo_elegibles
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lotes ADD COLUMN cupo_elegibles INTEGER NOT NULL DEFAULT 300;
        EXCEPTION WHEN duplicate_column THEN NULL; END $$
    """)

    # total_candidatos — poblado desde total_items original
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lotes ADD COLUMN total_candidatos INTEGER NOT NULL DEFAULT 0;
        EXCEPTION WHEN duplicate_column THEN NULL; END $$
    """)
    op.execute("""
        UPDATE ec_lotes SET total_candidatos = total_items
        WHERE total_candidatos = 0 AND total_items > 0
    """)

    # total_elegibles, total_excluidos
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lotes ADD COLUMN total_elegibles INTEGER NOT NULL DEFAULT 0;
        EXCEPTION WHEN duplicate_column THEN NULL; END $$
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lotes ADD COLUMN total_excluidos INTEGER NOT NULL DEFAULT 0;
        EXCEPTION WHEN duplicate_column THEN NULL; END $$
    """)

    # total_enviados — poblado desde items_aceptados original
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lotes ADD COLUMN total_enviados INTEGER NOT NULL DEFAULT 0;
        EXCEPTION WHEN duplicate_column THEN NULL; END $$
    """)
    op.execute("""
        UPDATE ec_lotes SET total_enviados = items_aceptados
        WHERE total_enviados = 0 AND items_aceptados > 0
    """)

    # dry_run — puede que ya exista en schema original
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lotes ADD COLUMN dry_run BOOLEAN NOT NULL DEFAULT TRUE;
        EXCEPTION WHEN duplicate_column THEN NULL; END $$
    """)

    # Migración de valores de estado ec_lotes
    # Mapa: preparando → pendiente, listo → pendiente,
    #        enviando → en_progreso, completo → completado
    # 'cancelado' no cambia.
    op.execute("UPDATE ec_lotes SET estado = 'pendiente'   WHERE estado IN ('preparando','listo')")
    op.execute("UPDATE ec_lotes SET estado = 'en_progreso' WHERE estado = 'enviando'")
    op.execute("UPDATE ec_lotes SET estado = 'completado'  WHERE estado = 'completo'")

    # Reemplazar CHECK constraint de estado
    op.execute("""
        ALTER TABLE ec_lotes
        DROP CONSTRAINT IF EXISTS ec_lotes_estado_check
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lotes ADD CONSTRAINT ec_lotes_estado_check
            CHECK (estado IN ('pendiente','en_progreso','completado','cancelado'));
        EXCEPTION WHEN duplicate_object THEN NULL; END $$
    """)

    # Índice en fecha_creacion por timezone Lima
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_ec_lotes_fecha_lima
        ON ec_lotes (DATE(fecha_creacion AT TIME ZONE 'America/Lima'))
    """)

    # ═══════════════════════════════════════════════════════════════════════
    # PARTE 2: ec_lote_items — agregar columnas del schema canónico T1
    # ═══════════════════════════════════════════════════════════════════════

    # bandeja_asignada — copia permanente de 'bandeja' (bandeja original se conserva)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lote_items ADD COLUMN bandeja_asignada TEXT;
        EXCEPTION WHEN duplicate_column THEN NULL; END $$
    """)
    op.execute("""
        UPDATE ec_lote_items SET bandeja_asignada = bandeja
        WHERE bandeja_asignada IS NULL AND bandeja IS NOT NULL
    """)

    # estado_validacion — copia de estado_email original
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lote_items ADD COLUMN estado_validacion TEXT NOT NULL DEFAULT 'sin_validar';
        EXCEPTION WHEN duplicate_column THEN NULL; END $$
    """)
    op.execute("""
        UPDATE ec_lote_items SET estado_validacion = estado_email
        WHERE estado_validacion = 'sin_validar' AND estado_email IS NOT NULL
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lote_items ADD CONSTRAINT ec_lote_items_estado_validacion_check
            CHECK (estado_validacion IN ('valido','invalido','riesgo','no_verificado','sin_validar'));
        EXCEPTION WHEN duplicate_object THEN NULL; END $$
    """)

    # detalle_validacion
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lote_items ADD COLUMN detalle_validacion TEXT;
        EXCEPTION WHEN duplicate_column THEN NULL; END $$
    """)

    # estado_seleccion — nueva columna (datos existentes → 'candidato')
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lote_items ADD COLUMN estado_seleccion TEXT NOT NULL DEFAULT 'candidato';
        EXCEPTION WHEN duplicate_column THEN NULL; END $$
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lote_items ADD CONSTRAINT ec_lote_items_estado_seleccion_check
            CHECK (estado_seleccion IN ('candidato','elegible','excluido'));
        EXCEPTION WHEN duplicate_object THEN NULL; END $$
    """)

    # motivo_seleccion, motivo_exclusion
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lote_items ADD COLUMN motivo_seleccion TEXT;
        EXCEPTION WHEN duplicate_column THEN NULL; END $$
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lote_items ADD COLUMN motivo_exclusion TEXT;
        EXCEPTION WHEN duplicate_column THEN NULL; END $$
    """)

    # sector
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lote_items ADD COLUMN sector TEXT;
        EXCEPTION WHEN duplicate_column THEN NULL; END $$
    """)

    # Locks temporales
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lote_items ADD COLUMN bloqueado_por TEXT;
        EXCEPTION WHEN duplicate_column THEN NULL; END $$
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lote_items ADD COLUMN bloqueado_en TIMESTAMPTZ;
        EXCEPTION WHEN duplicate_column THEN NULL; END $$
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lote_items ADD COLUMN intento_enviado_en TIMESTAMPTZ;
        EXCEPTION WHEN duplicate_column THEN NULL; END $$
    """)

    # fecha_seleccion — copia de agregado_at original
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lote_items ADD COLUMN fecha_seleccion TIMESTAMPTZ;
        EXCEPTION WHEN duplicate_column THEN NULL; END $$
    """)
    op.execute("""
        UPDATE ec_lote_items SET fecha_seleccion = agregado_at
        WHERE fecha_seleccion IS NULL AND agregado_at IS NOT NULL
    """)
    op.execute("""
        UPDATE ec_lote_items SET fecha_seleccion = NOW()
        WHERE fecha_seleccion IS NULL
    """)

    # fecha_envio — copia de enviado_at original
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lote_items ADD COLUMN fecha_envio TIMESTAMPTZ;
        EXCEPTION WHEN duplicate_column THEN NULL; END $$
    """)
    op.execute("""
        UPDATE ec_lote_items SET fecha_envio = enviado_at
        WHERE fecha_envio IS NULL AND enviado_at IS NOT NULL
    """)

    # skip_reason
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lote_items ADD COLUMN skip_reason TEXT;
        EXCEPTION WHEN duplicate_column THEN NULL; END $$
    """)

    # fuente_sheet_id, fuente_tab, fuente_clave — nuevas columnas
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lote_items ADD COLUMN fuente_sheet_id TEXT;
        EXCEPTION WHEN duplicate_column THEN NULL; END $$
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lote_items ADD COLUMN fuente_tab TEXT;
        EXCEPTION WHEN duplicate_column THEN NULL; END $$
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lote_items ADD COLUMN fuente_clave TEXT;
        EXCEPTION WHEN duplicate_column THEN NULL; END $$
    """)

    # rebote_motivo — copia de rebote_tipo original; rebote_tipo se conserva
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lote_items ADD COLUMN rebote_motivo TEXT;
        EXCEPTION WHEN duplicate_column THEN NULL; END $$
    """)
    op.execute("""
        UPDATE ec_lote_items SET rebote_motivo = rebote_tipo
        WHERE rebote_motivo IS NULL AND rebote_tipo IS NOT NULL
    """)

    # Migración de valores de estado_envio
    # IMPORTANTE: ejecutar ANTES de reemplazar el CHECK constraint.
    # Mapa:
    #   en_lote      → pendiente
    #   reservado    → en_proceso
    #   aceptado     → enviado     (historial conservado; dry_run en lote padre)
    #   fallido      → error
    #   reintentable → error       (conservador: marcar como definitivo)
    #   incierto     → conciliacion
    op.execute("UPDATE ec_lote_items SET estado_envio = 'pendiente'    WHERE estado_envio = 'en_lote'")
    op.execute("UPDATE ec_lote_items SET estado_envio = 'en_proceso'   WHERE estado_envio = 'reservado'")
    op.execute("UPDATE ec_lote_items SET estado_envio = 'enviado'      WHERE estado_envio = 'aceptado'")
    op.execute("UPDATE ec_lote_items SET estado_envio = 'error'        WHERE estado_envio IN ('fallido','reintentable')")
    op.execute("UPDATE ec_lote_items SET estado_envio = 'conciliacion' WHERE estado_envio = 'incierto'")

    # Reemplazar CHECK constraint de estado_envio
    op.execute("""
        ALTER TABLE ec_lote_items
        DROP CONSTRAINT IF EXISTS ec_lote_items_estado_envio_check
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE ec_lote_items ADD CONSTRAINT ec_lote_items_estado_envio_check
            CHECK (estado_envio IN
              ('pendiente','en_proceso','en_envio','enviado','aceptado',
               'conciliacion','omitido','rebotado','error'));
        EXCEPTION WHEN duplicate_object THEN NULL; END $$
    """)

    # Propagar fuente_sheet_id desde ec_lotes hacia ec_lote_items
    op.execute("""
        UPDATE ec_lote_items li
        SET fuente_sheet_id = l.fuente_sheet_id
        FROM ec_lotes l
        WHERE li.lote_id = l.id
          AND li.fuente_sheet_id IS NULL
          AND l.fuente_sheet_id IS NOT NULL
    """)

    # Índices adicionales
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_lote_items_lote_sel
        ON ec_lote_items (lote_id, estado_seleccion, estado_envio)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_lote_items_bandeja
        ON ec_lote_items (bandeja_asignada, estado_seleccion, estado_envio)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_lote_items_lock
        ON ec_lote_items (bloqueado_por, bloqueado_en)
        WHERE bloqueado_por IS NOT NULL
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_lote_items_rebote
        ON ec_lote_items (rebote_motivo)
        WHERE rebote_motivo IS NOT NULL
    """)


def downgrade():
    # Esta migración solo agrega columnas y migra datos.
    # El downgrade deja las columnas pero restaura los valores de estado.
    op.execute("UPDATE ec_lotes SET estado = 'preparando' WHERE estado = 'pendiente'")
    op.execute("UPDATE ec_lotes SET estado = 'enviando'   WHERE estado = 'en_progreso'")
    op.execute("UPDATE ec_lotes SET estado = 'completo'   WHERE estado = 'completado'")

    op.execute("UPDATE ec_lote_items SET estado_envio = 'en_lote'  WHERE estado_envio = 'pendiente'")
    op.execute("UPDATE ec_lote_items SET estado_envio = 'reservado' WHERE estado_envio = 'en_proceso'")
    op.execute("UPDATE ec_lote_items SET estado_envio = 'aceptado'  WHERE estado_envio = 'enviado'")
    op.execute("UPDATE ec_lote_items SET estado_envio = 'fallido'   WHERE estado_envio = 'error'")
    op.execute("UPDATE ec_lote_items SET estado_envio = 'incierto'  WHERE estado_envio = 'conciliacion'")
