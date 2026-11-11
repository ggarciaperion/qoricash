"""Add ec_lotes and ec_lote_items tables — outreach batch tracking

Revision ID: ec02_lotes
Revises: ec01_worker_tables
Create Date: 2026-11-09

Contrato de integración T1/T3
==============================

Este archivo usa CREATE TABLE IF NOT EXISTS para ser seguro en re-ejecución.
Si las tablas ya existen con el schema original (pre-ec04), no hace nada:
  la migración correctiva vive en ec04_lotes_schema_fix.py.

Schema canónico alineado con ecosistema_db.py (T1):
  ec_lotes.lote_id    TEXT UNIQUE — identificador semántico ('2026-11-09-A')
  ec_lotes.dry_run    BOOLEAN     — TRUE si el lote fue simulación (no envió correos)
  ec_lotes.estado     IN ('pendiente','en_progreso','completado','cancelado')

  ec_lote_items.lote_id          BIGINT FK → ec_lotes.id
  ec_lote_items.bandeja_asignada TEXT  (asignación permanente de bandeja)
  ec_lote_items.estado_validacion TEXT (snapshot de validación email al armar el lote)
  ec_lote_items.estado_seleccion  TEXT (candidato/elegible/excluido)
  ec_lote_items.estado_envio      IN ('pendiente','en_proceso','en_envio',
                                      'enviado','conciliacion','omitido','rebotado','error')
  ec_lote_items.rebote_motivo     TEXT (rebote posterior — no borra historial de envío)

dry_run = TRUE:
  El lote se ejecutó en modo simulación. ningún correo fue enviado al proveedor.
  El panel debe marcarlo visualmente y excluirlo de métricas de envíos reales.
  T1 debe setear dry_run=FALSE explícitamente al crear lotes de producción.

Semántica de estado_envio:
  pendiente    → seleccionado en el lote, aún no intentado
  en_proceso   → lock tomado, Gmail API no llamada
  en_envio     → Gmail API en curso (in-flight)
  enviado      → Gmail API confirmó 2xx (proveedor) — no confirma entrega a inbox
  conciliacion → resultado desconocido — NUNCA reintento automático
  omitido      → saltado (rate limit, dry_run, exclusión tardía); ver skip_reason
  rebotado     → rebote confirmado (5xx SMTP)
  error        → fallo definitivo, no reintentable

rebote_motivo IS NOT NULL → rebote detectado en response_log posterior al envío;
  estado_envio se conserva (historial no se borra).
"""
from alembic import op


revision      = 'ec02_lotes'
down_revision = 'ec01_worker_tables'
branch_labels = None
depends_on    = None


def upgrade():
    # ── ec_lotes — cabecera del lote ──────────────────────────────────────────
    # IF NOT EXISTS: si la tabla ya existe (schema original), no hace nada.
    # La migración ec04_lotes_schema_fix.py aplica las correcciones sobre
    # el schema original si las tablas ya estaban creadas.
    op.execute("""
        CREATE TABLE IF NOT EXISTS ec_lotes (
            id               BIGSERIAL PRIMARY KEY,
            lote_id          TEXT UNIQUE,
            fuente_sheet_id  TEXT,
            fuente_tab       TEXT,
            fecha_creacion   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            creado_por       TEXT,
            cupo_elegibles   INTEGER NOT NULL DEFAULT 300,
            total_candidatos INTEGER NOT NULL DEFAULT 0,
            total_elegibles  INTEGER NOT NULL DEFAULT 0,
            total_excluidos  INTEGER NOT NULL DEFAULT 0,
            total_enviados   INTEGER NOT NULL DEFAULT 0,
            estado           TEXT NOT NULL DEFAULT 'pendiente'
                             CHECK (estado IN
                               ('pendiente','en_progreso','completado','cancelado')),
            dry_run          BOOLEAN NOT NULL DEFAULT TRUE
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_ec_lotes_estado ON ec_lotes (estado)")

    # ── ec_lote_items — un registro por prospecto en el lote ──────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS ec_lote_items (
            id                  BIGSERIAL PRIMARY KEY,
            lote_id             BIGINT NOT NULL REFERENCES ec_lotes(id) ON DELETE CASCADE,
            email               TEXT NOT NULL,
            ruc                 TEXT,
            razon_social        TEXT,
            fuente_sheet_id     TEXT,
            fuente_tab          TEXT,
            fuente_clave        TEXT,
            rubro               TEXT,
            sector              TEXT,
            motivo_seleccion    TEXT,

            -- Validación técnica de la dirección de correo (snapshot del momento del lote)
            estado_validacion   TEXT NOT NULL DEFAULT 'sin_validar'
                                CHECK (estado_validacion IN
                                  ('valido','invalido','riesgo','no_verificado','sin_validar')),
            detalle_validacion  TEXT,

            -- Estado de selección dentro del lote (permanente — no se revierte)
            estado_seleccion    TEXT NOT NULL DEFAULT 'candidato'
                                CHECK (estado_seleccion IN ('candidato','elegible','excluido')),
            motivo_exclusion    TEXT,

            -- Asignación permanente de bandeja (sobrevive al envío confirmado)
            bandeja_asignada    TEXT,

            -- Lock temporal de envío (run_id del worker que tomó el item)
            bloqueado_por       TEXT,
            bloqueado_en        TIMESTAMPTZ,

            -- Momento en que se inició la llamada a Gmail API
            intento_enviado_en  TIMESTAMPTZ,

            -- Estado operativo de envío
            -- 'aceptado': Gmail aceptó (2xx) pero aún no confirmado en DB (ver CONTRATO_LOTES.md)
            estado_envio        TEXT NOT NULL DEFAULT 'pendiente'
                                CHECK (estado_envio IN
                                  ('pendiente','en_proceso','en_envio','enviado','aceptado',
                                   'conciliacion','omitido','rebotado','error')),

            fecha_seleccion     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            fecha_envio         TIMESTAMPTZ,
            gmail_message_id    TEXT,
            skip_reason         TEXT,

            -- Rebote detectado posteriormente (no borra historial de envío)
            rebote_motivo       TEXT
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_lote_items_lote    ON ec_lote_items (lote_id, estado_seleccion, estado_envio)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_lote_items_bandeja  ON ec_lote_items (bandeja_asignada, estado_seleccion, estado_envio)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_lote_items_lock     ON ec_lote_items (bloqueado_por, bloqueado_en) WHERE bloqueado_por IS NOT NULL")
    op.execute("CREATE INDEX IF NOT EXISTS ix_lote_items_msg_id   ON ec_lote_items (gmail_message_id) WHERE gmail_message_id IS NOT NULL")
    op.execute("CREATE INDEX IF NOT EXISTS ix_lote_items_rebote   ON ec_lote_items (rebote_motivo) WHERE rebote_motivo IS NOT NULL")


def downgrade():
    op.execute("DROP TABLE IF EXISTS ec_lote_items")
    op.execute("DROP TABLE IF EXISTS ec_lotes")
