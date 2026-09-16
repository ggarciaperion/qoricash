"""Add worker operational tables for prospeccion ecosystem (PostgreSQL shared layer)

Revision ID: ec01_worker_tables
Revises: z9merge_all_heads
Create Date: 2026-09-16

Tables added (worker namespace):
  ec_prospectos      — sync cache of PROSPECTOS_MASTER
                       (renamed: 'prospectos' already used by Flask CRM model)
  outreach_attempt   — idempotency guard for all outbound sends
  outreach_log       — complete history of outbound sends
  response_log       — incoming responses / bounces classified by Response agent
  suppression        — permanent never-contact list
  agent_runs         — execution history per agent
  agent_heartbeat    — current liveness status per agent (separate from history)
  prospect_locks     — mutex to prevent concurrent processing of same prospect
  prospect_state_log — audit trail of state transitions
  lead_pipeline      — commercial signal queue (Response -> CRM Bridge)
  metrics            — daily aggregated operational metrics
  bandeja_estado     — per-inbox rate-limiting and pause state
  alerts_log         — CRITICAL/WARNING/INFO alerts from worker
  runtime_config     — operational config: DRY_RUN, TC, timestamps
  sync_state         — Sheets sync metadata

Identity notes:
  ec_prospectos.sheet_row  — sync key only (NOT business identity)
  ec_prospectos.email      — logical contact identity (enforced at consolidation layer,
                             NOT by DB UNIQUE — safe during partial sync windows)
  ec_prospectos.ruc        — company identity (NOT unique: one RUC -> many contacts)

State authority (Sheets-owned vs PG-owned):
  Sheets -> PG (sync):   ruc, email, razon_social, nombre_contacto, cargo,
                         telefono, provincia, rubro, sector, fuente, score, prioridad
  PG -> Sheets (dirty):  estado_email, estado_com, fecha_ult_contacto
  Protected in PG:       estado_email when in {correo_rebotado, invalido, sin_email}
                         estado_com when in {no_contactar, correo_rebotado, cliente,
                           interesado, solicita_*, no_interesado, persona_incorrecta}

DRY_RUN seeded as 'true' — requires explicit DB UPDATE to enable outreach.
"""
from alembic import op

revision = 'ec01_worker_tables'
down_revision = 'z9merge_all_heads'
branch_labels = None
depends_on = None


def upgrade():
    # ── ec_prospectos ──────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS ec_prospectos (
            id                  BIGSERIAL PRIMARY KEY,
            sheet_row           INTEGER UNIQUE NOT NULL,
            ruc                 VARCHAR(20),
            email               TEXT,
            razon_social        TEXT,
            nombre_contacto     TEXT,
            cargo               TEXT,
            telefono            TEXT,
            provincia           TEXT,
            rubro               TEXT,
            sector              TEXT,
            estado_email        TEXT NOT NULL DEFAULT 'sin_validar',
            estado_com          TEXT NOT NULL DEFAULT 'nuevo',
            score               SMALLINT DEFAULT 0,
            prioridad           TEXT DEFAULT 'BAJA',
            fuente              TEXT,
            fecha_ult_contacto  TEXT,
            social_score        SMALLINT DEFAULT 0,
            synced_at           TIMESTAMPTZ,
            sheets_dirty        SMALLINT DEFAULT 0,
            row_hash            TEXT
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_ec_prosp_email ON ec_prospectos(email)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ec_prosp_prio ON ec_prospectos(prioridad, estado_email)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ec_prosp_dirty ON ec_prospectos(sheets_dirty) WHERE sheets_dirty = 1")

    # ── outreach_attempt ───────────────────────────────────────────────────────
    # UNKNOWN is terminal for auto-retry. Must be manually reconciled.
    op.execute("""
        CREATE TABLE IF NOT EXISTS outreach_attempt (
            id                  BIGSERIAL PRIMARY KEY,
            idempotency_key     TEXT UNIQUE NOT NULL,
            prospecto_id        BIGINT,
            email               TEXT NOT NULL,
            bandeja             TEXT,
            stage               TEXT,
            status              TEXT NOT NULL DEFAULT 'reserved'
                                    CHECK (status IN ('reserved','sent','failed','retryable','unknown')),
            gmail_message_id    TEXT,
            reserved_at         TIMESTAMPTZ DEFAULT NOW(),
            sent_at             TIMESTAMPTZ,
            error_msg           TEXT,
            agent_run_id        BIGINT
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_attempt_email ON outreach_attempt(email, stage)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_attempt_status ON outreach_attempt(status, reserved_at)")

    # ── outreach_log ───────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS outreach_log (
            id               BIGSERIAL PRIMARY KEY,
            prospecto_id     BIGINT REFERENCES ec_prospectos(id) ON DELETE SET NULL,
            email            TEXT NOT NULL,
            bandeja          TEXT NOT NULL,
            stage            TEXT NOT NULL,
            template_sector  TEXT,
            subject          TEXT,
            gmail_message_id TEXT,
            sent_at          TIMESTAMPTZ DEFAULT NOW(),
            status           TEXT DEFAULT 'enviado',
            skip_reason      TEXT,
            tc_compra        TEXT,
            tc_venta         TEXT,
            agent_run_id     BIGINT
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ix_outreach_gmail
        ON outreach_log(gmail_message_id)
        WHERE gmail_message_id IS NOT NULL
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_outreach_email ON outreach_log(email)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_outreach_sent  ON outreach_log(sent_at)")

    # ── response_log ──────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS response_log (
            id                BIGSERIAL PRIMARY KEY,
            email             TEXT,
            bandeja_receptora TEXT,
            gmail_msg_id      TEXT UNIQUE,
            clasificacion     TEXT,
            bounce_type       TEXT,
            subject_original  TEXT,
            snippet           TEXT,
            recibido_at       TIMESTAMPTZ DEFAULT NOW(),
            procesado         SMALLINT DEFAULT 0,
            crm_conv_id       BIGINT,
            agent_run_id      BIGINT
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_response_email ON response_log(email)")
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_response_procesado
        ON response_log(procesado) WHERE procesado = 0
    """)

    # ── suppression ───────────────────────────────────────────────────────────
    # Shared between Flask and Worker. Suppression always wins.
    op.execute("""
        CREATE TABLE IF NOT EXISTS suppression (
            id           BIGSERIAL PRIMARY KEY,
            tipo         TEXT NOT NULL CHECK (tipo IN ('email','dominio','telefono','ruc')),
            valor        TEXT NOT NULL,
            motivo       TEXT NOT NULL,
            fuente       TEXT,
            agregado_at  TIMESTAMPTZ DEFAULT NOW(),
            agent_run_id BIGINT,
            notas        TEXT,
            UNIQUE (tipo, valor)
        )
    """)

    # ── agent_runs ────────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS agent_runs (
            id              BIGSERIAL PRIMARY KEY,
            agent           TEXT NOT NULL,
            execution_uuid  TEXT UNIQUE NOT NULL,
            started_at      TIMESTAMPTZ DEFAULT NOW(),
            finished_at     TIMESTAMPTZ,
            status          TEXT DEFAULT 'running',
            records_in      INTEGER DEFAULT 0,
            records_out     INTEGER DEFAULT 0,
            actions_taken   INTEGER DEFAULT 0,
            actions_skipped INTEGER DEFAULT 0,
            error_msg       TEXT,
            summary_json    JSONB,
            triggered_by    TEXT DEFAULT 'schedule'
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_agent_runs_agent ON agent_runs(agent, started_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agent_runs_status ON agent_runs(status)")

    # ── agent_heartbeat ───────────────────────────────────────────────────────
    # Liveness per agent. Mission Control detects OFFLINE if last_seen > threshold.
    # Distinct from agent_runs which records individual execution history.
    # status values: running | idle | paused | error | offline
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

    # ── prospect_locks ────────────────────────────────────────────────────────
    # PK is prospecto_id. Lock acquisition uses:
    #   INSERT ON CONFLICT DO UPDATE WHERE expires_at < NOW() RETURNING prospecto_id
    # This is atomic: inserts if no lock, updates if existing lock expired, no-ops if held.
    op.execute("""
        CREATE TABLE IF NOT EXISTS prospect_locks (
            prospecto_id BIGINT PRIMARY KEY,
            locked_by    TEXT NOT NULL,
            locked_at    TIMESTAMPTZ NOT NULL,
            expires_at   TIMESTAMPTZ NOT NULL
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_locks_expires ON prospect_locks(expires_at)")

    # ── prospect_state_log ────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS prospect_state_log (
            id              BIGSERIAL PRIMARY KEY,
            prospecto_id    BIGINT REFERENCES ec_prospectos(id) ON DELETE CASCADE,
            estado_anterior TEXT,
            estado_nuevo    TEXT NOT NULL,
            motivo          TEXT,
            agente          TEXT,
            agent_run_id    BIGINT,
            created_at      TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_state_log ON prospect_state_log(prospecto_id, created_at)")

    # ── lead_pipeline ─────────────────────────────────────────────────────────
    # Commercial signal queue, NOT a CRM. Idempotency by gmail_msg_id.
    op.execute("""
        CREATE TABLE IF NOT EXISTS lead_pipeline (
            id                BIGSERIAL PRIMARY KEY,
            email             TEXT NOT NULL,
            prospecto_id      BIGINT REFERENCES ec_prospectos(id) ON DELETE SET NULL,
            tipo              TEXT NOT NULL,
            subject           TEXT,
            bandeja_receptora TEXT,
            gmail_msg_id      TEXT UNIQUE,
            contexto_json     JSONB,
            notificado        SMALLINT DEFAULT 0,
            webhook_ok        SMALLINT DEFAULT 0,
            notas             TEXT,
            created_at        TIMESTAMPTZ DEFAULT NOW(),
            updated_at        TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_lead_pipeline_email ON lead_pipeline(email)")
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_lead_pipeline_notif
        ON lead_pipeline(notificado) WHERE notificado = 0
    """)

    # ── metrics ───────────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            id          BIGSERIAL PRIMARY KEY,
            fecha       DATE NOT NULL,
            metric_key  TEXT NOT NULL,
            value_num   DOUBLE PRECISION,
            value_text  TEXT,
            dimension   TEXT DEFAULT '',
            UNIQUE (fecha, metric_key, dimension)
        )
    """)

    # ── bandeja_estado ────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS bandeja_estado (
            bandeja           TEXT PRIMARY KEY,
            enviados_hoy      INTEGER DEFAULT 0,
            bounce_count_24h  INTEGER DEFAULT 0,
            total_24h         INTEGER DEFAULT 0,
            pausada_hasta     TIMESTAMPTZ,
            ultimo_update     TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("""
        INSERT INTO bandeja_estado(bandeja)
        VALUES ('ggarcia'), ('gerencia'), ('info')
        ON CONFLICT (bandeja) DO NOTHING
    """)

    # ── alerts_log ────────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS alerts_log (
            id           BIGSERIAL PRIMARY KEY,
            level        TEXT NOT NULL CHECK (level IN ('CRITICAL','WARNING','INFO')),
            component    TEXT NOT NULL,
            message      TEXT NOT NULL,
            detail       TEXT,
            agent_run_id BIGINT,
            created_at   TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_alerts_level ON alerts_log(level, created_at)")

    # ── runtime_config ────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS runtime_config (
            key        TEXT PRIMARY KEY,
            value      TEXT,
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            updated_by TEXT DEFAULT 'system'
        )
    """)
    op.execute("""
        INSERT INTO runtime_config(key, value, updated_by)
        VALUES ('dry_run', 'true', 'migration')
        ON CONFLICT (key) DO NOTHING
    """)

    # ── sync_state ────────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS sync_state (
            key        TEXT PRIMARY KEY,
            value      TEXT NOT NULL,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)


def downgrade():
    # Drop in reverse dependency order (FKs first)
    op.execute("DROP TABLE IF EXISTS sync_state")
    op.execute("DROP TABLE IF EXISTS runtime_config")
    op.execute("DROP TABLE IF EXISTS alerts_log")
    op.execute("DROP TABLE IF EXISTS bandeja_estado")
    op.execute("DROP TABLE IF EXISTS metrics")
    op.execute("DROP TABLE IF EXISTS lead_pipeline")
    op.execute("DROP TABLE IF EXISTS prospect_state_log")
    op.execute("DROP TABLE IF EXISTS prospect_locks")
    op.execute("DROP TABLE IF EXISTS agent_heartbeat")
    op.execute("DROP TABLE IF EXISTS agent_runs")
    op.execute("DROP TABLE IF EXISTS suppression")
    op.execute("DROP TABLE IF EXISTS response_log")
    op.execute("DROP TABLE IF EXISTS outreach_log")
    op.execute("DROP TABLE IF EXISTS outreach_attempt")
    op.execute("DROP TABLE IF EXISTS ec_prospectos")
