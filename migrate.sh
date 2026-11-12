#!/bin/bash
# Script para ejecutar migraciones en Render
# Maneja tanto DBs nuevas como producción existente con historial antiguo.

set -e

# FLASK_CLI_ONLY suprime eventlet.monkey_patch(), los schedulers de expiración
# y el scheduler de Estudio Creativo durante la migración.
# Solo afecta a este proceso (preDeployCommand). gunicorn arranca en proceso
# separado sin heredar esta variable, por lo que los schedulers funcionan
# normalmente en producción.
export FLASK_CLI_ONLY=true

echo "=========================================="
echo "   INICIANDO MIGRACIONES DE BASE DE DATOS"
echo "=========================================="
echo ""

if [ -z "$DATABASE_URL" ]; then
    echo "❌ ERROR: DATABASE_URL no está configurada"
    exit 1
fi

echo "✅ DATABASE_URL configurada"
echo "   ${DATABASE_URL:0:30}..."
echo ""

echo "📚 Revisiones disponibles:"
ls -1 migrations/versions/*.py 2>/dev/null | xargs -I{} basename {} || echo "(ninguna)"
echo ""

cd "$(dirname "$0")" || exit 1

# ── Verificación de revisión Alembic ─────────────────────────────────────────
# PRIMERA comprobación: ocurre antes de cualquier parche o escritura.
# Regla de seguridad:
#   - DB sin versión (nueva instalación): continuar.
#   - DB con revisión CONOCIDA en el historial: continuar.
#   - DB con revisión DESCONOCIDA: ABORTAR con exit 1. No hacer stamp automático.
#     Una revisión desconocida indica una DB de otra rama, una restauración
#     incorrecta o un historial manipulado. Continuar silenciosamente podría
#     ejecutar migraciones sobre un schema incompatible y corromper datos.
#     Acción requerida: diagnosticar manualmente y, si es seguro, ejecutar
#     "flask db stamp <revision_conocida>" antes del deploy.

echo "🔍 Verificando revisión Alembic antes de cualquier cambio..."

CURRENT=$(flask db current 2>&1 | grep -E '^[a-f0-9]' | head -1 || true)

if [ -n "$CURRENT" ]; then
    echo "   Revisión actual en DB: $CURRENT"

    KNOWN=$(flask db history 2>&1 | grep "$CURRENT" || true)

    if [ -z "$KNOWN" ]; then
        echo ""
        echo "=========================================="
        echo "   ERROR: REVISIÓN ALEMBIC DESCONOCIDA"
        echo "=========================================="
        echo ""
        echo "   La DB reporta revisión: '$CURRENT'"
        echo "   Esta revisión NO existe en el historial de migraciones del"
        echo "   código que se está desplegando."
        echo ""
        echo "   DEPLOY DETENIDO. No se realizó ningún cambio a la DB."
        echo ""
        echo "   Causas posibles:"
        echo "     - La DB fue migrada con una rama de código diferente."
        echo "     - Se restauró un backup con un historial de migraciones distinto."
        echo "     - La tabla alembic_version fue modificada manualmente."
        echo ""
        echo "   Acción requerida (ejecutar manualmente antes de reintentar):"
        echo "     1. Identificar a qué revisión conocida corresponde el schema actual."
        echo "     2. flask db stamp <revision_conocida>"
        echo "     3. Reintentar el deploy."
        echo ""
        echo "   Revisiones conocidas (cabezas de rama):"
        flask db heads 2>&1 | grep -v "^$" | head -20 || true
        echo ""
        exit 1
    else
        echo "   ✅ Revisión reconocida — ningún cambio hasta aquí. Continuando con parches."
        echo ""
    fi
else
    echo "   DB nueva o sin versión — upgrade creará el schema desde cero."
    echo ""
fi

# ── Patch directo: is_validated en bank_movements ────────────────────────────
# Ejecuta SQL puro con psycopg2 ANTES de Alembic.
# Totalmente idempotente (IF NOT EXISTS). No depende del historial de migraciones.
echo "⚡ Garantizando columna is_validated en bank_movements..."
python3 - <<'PYEOF'
import os, sys
try:
    import psycopg2
except ImportError:
    print("   psycopg2 no disponible — saltando patch directo")
    sys.exit(0)

url = os.environ.get('DATABASE_URL', '')
if not url:
    print("   DATABASE_URL no definida — saltando patch directo")
    sys.exit(0)

try:
    conn = psycopg2.connect(url)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(
        "ALTER TABLE bank_movements "
        "ADD COLUMN IF NOT EXISTS is_validated BOOLEAN NOT NULL DEFAULT false"
    )
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='bank_movements' AND column_name='is_validated'"
    )
    exists = cur.fetchone()
    conn.close()
    if exists:
        print("   ✅ is_validated: confirmada en PostgreSQL")
    else:
        print("   ❌ is_validated: NO se pudo crear la columna")
        sys.exit(1)
except psycopg2.errors.UndefinedTable:
    print("   ⏭  bank_movements aún no existe — se creará en upgrade")
except Exception as e:
    print(f"   ⚠️  Error en patch directo: {e}")
    # No abortar — dejar que Alembic intente igualmente
PYEOF
echo ""

# ── Patch directo: bot_pausado en wa_bot_sessions ─────────────────────────────
echo "⚡ Garantizando columna bot_pausado en wa_bot_sessions..."
python3 - <<'PYEOF'
import os, sys
try:
    import psycopg2
except ImportError:
    print("   psycopg2 no disponible — saltando patch directo")
    sys.exit(0)

url = os.environ.get('DATABASE_URL', '')
if not url:
    print("   DATABASE_URL no definida — saltando patch directo")
    sys.exit(0)

try:
    conn = psycopg2.connect(url)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("""
        ALTER TABLE wa_bot_sessions
        ADD COLUMN IF NOT EXISTS bot_pausado BOOLEAN NOT NULL DEFAULT FALSE;
    """)
    print("   ✅ bot_pausado: OK")
    cur.close()
    conn.close()
except Exception as e:
    print(f"   ⚠️  Error en patch bot_pausado: {e}")
PYEOF
echo ""

# ── Patch directo: columnas apertura/cierre/resultado en daily_closures ──────
# Ejecuta SQL puro con psycopg2 ANTES de Alembic.
# Totalmente idempotente (IF NOT EXISTS). Soluciona el caso donde migrate.sh
# stampeó b1c2a3j4a5d6 sin ejecutar su upgrade() → columnas nunca creadas.
echo "⚡ Garantizando columnas apertura/cierre/resultado en daily_closures..."
python3 - <<'PYEOF'
import os, sys
try:
    import psycopg2
except ImportError:
    print("   psycopg2 no disponible — saltando patch directo")
    sys.exit(0)

url = os.environ.get('DATABASE_URL', '')
if not url:
    print("   DATABASE_URL no definida — saltando patch directo")
    sys.exit(0)

COLS = [
    ("opening_balance_json",     "TEXT NOT NULL DEFAULT '{}'"),
    ("opening_total_usd",        "NUMERIC(15,2) NOT NULL DEFAULT 0"),
    ("opening_total_pen",        "NUMERIC(15,2) NOT NULL DEFAULT 0"),
    ("opening_registered_at",    "TIMESTAMP WITHOUT TIME ZONE"),
    ("opening_registered_by",    "INTEGER REFERENCES users(id)"),
    ("closing_balance_json",     "TEXT NOT NULL DEFAULT '{}'"),
    ("closing_total_usd",        "NUMERIC(15,2) NOT NULL DEFAULT 0"),
    ("closing_total_pen",        "NUMERIC(15,2) NOT NULL DEFAULT 0"),
    ("closing_registered_at",    "TIMESTAMP WITHOUT TIME ZONE"),
    ("closing_registered_by",    "INTEGER REFERENCES users(id)"),
    ("result_usd",               "NUMERIC(15,2)"),
    ("result_pen",               "NUMERIC(15,2)"),
    ("result_label",             "VARCHAR(20)"),
]

try:
    conn = psycopg2.connect(url)
    conn.autocommit = True
    cur = conn.cursor()
    # Check if daily_closures table exists first
    cur.execute(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_name='daily_closures'"
    )
    if not cur.fetchone():
        print("   ⏭  daily_closures aún no existe — se creará en upgrade")
        conn.close()
        sys.exit(0)

    added = []
    for col, col_def in COLS:
        cur.execute(
            f"ALTER TABLE daily_closures ADD COLUMN IF NOT EXISTS {col} {col_def}"
        )
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='daily_closures' AND column_name=%s",
            (col,)
        )
        if cur.fetchone():
            added.append(col)
        else:
            print(f"   ❌ {col}: NO se pudo crear la columna")
            conn.close()
            sys.exit(1)
    conn.close()
    print(f"   ✅ {len(added)}/13 columnas confirmadas en daily_closures")
except psycopg2.errors.UndefinedTable:
    print("   ⏭  daily_closures aún no existe — se creará en upgrade")
except Exception as e:
    print(f"   ⚠️  Error en patch directo daily_closures: {e}")
    # No abortar — dejar que Alembic intente igualmente
PYEOF
echo ""

# ── Patch directo: columna sin_whatsapp en prospectos ────────────────────────
echo "⚡ Garantizando columna sin_whatsapp en prospectos..."
python3 - <<'PYEOF'
import os, sys
try:
    import psycopg2
except ImportError:
    print("   psycopg2 no disponible — saltando patch directo")
    sys.exit(0)
url = os.environ.get('DATABASE_URL', '')
if not url:
    print("   DATABASE_URL no definida — saltando patch directo")
    sys.exit(0)
try:
    conn = psycopg2.connect(url)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("ALTER TABLE prospectos ADD COLUMN IF NOT EXISTS sin_whatsapp BOOLEAN NOT NULL DEFAULT false")
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='prospectos' AND column_name='sin_whatsapp'")
    exists = cur.fetchone()
    conn.close()
    if exists:
        print("   ✅ sin_whatsapp: confirmada en PostgreSQL")
    else:
        print("   ❌ sin_whatsapp: NO se pudo crear")
        sys.exit(1)
except Exception as e:
    print(f"   ⚠️  Error en patch directo sin_whatsapp: {e}")
PYEOF
echo ""

# ── Patch directo: columna coupon_code en operations ─────────────────────────
# La migración a5907b pudo no ejecutarse si Alembic encontró conflicto de heads.
# Patch 100% idempotente (ADD COLUMN IF NOT EXISTS). Sin riesgo de pérdida de datos.
echo "⚡ Garantizando columna coupon_code en operations..."
python3 - <<'PYEOF'
import os, sys
try:
    import psycopg2
except ImportError:
    print("   psycopg2 no disponible — saltando patch directo")
    sys.exit(0)
url = os.environ.get('DATABASE_URL', '')
if not url:
    print("   DATABASE_URL no definida — saltando patch directo")
    sys.exit(0)
try:
    conn = psycopg2.connect(url)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("ALTER TABLE operations ADD COLUMN IF NOT EXISTS coupon_code VARCHAR(20)")
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='operations' AND column_name='coupon_code'")
    exists = cur.fetchone()
    conn.close()
    if exists:
        print("   ✅ coupon_code: confirmada en operations")
    else:
        print("   ❌ coupon_code: NO se pudo crear")
        sys.exit(1)
except psycopg2.errors.UndefinedTable:
    print("   ⏭  operations aún no existe — se creará en upgrade")
except Exception as e:
    print(f"   ⚠️  Error en patch directo coupon_code: {e}")
PYEOF
echo ""

# ── Patch directo: eliminar constraints positivos de bank_balances ─────────────
# La migración b1a2n3k4b5a6 fue stampeada sin ejecutarse en producción.
# Este patch idempotente garantiza que el DROP ocurra en cada deploy.
echo "⚡ Eliminando constraints positivos de bank_balances (idempotente)..."
python3 - <<'PYEOF'
import os, sys
try:
    import psycopg2
except ImportError:
    print("   psycopg2 no disponible — saltando patch directo")
    sys.exit(0)

url = os.environ.get('DATABASE_URL', '')
if not url:
    print("   DATABASE_URL no definida — saltando patch directo")
    sys.exit(0)

try:
    conn = psycopg2.connect(url)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("ALTER TABLE bank_balances DROP CONSTRAINT IF EXISTS check_balance_usd_positive")
    cur.execute("ALTER TABLE bank_balances DROP CONSTRAINT IF EXISTS check_balance_pen_positive")
    # Verificar que no quedan
    cur.execute(
        "SELECT constraint_name FROM information_schema.table_constraints "
        "WHERE table_name='bank_balances' AND constraint_type='CHECK' "
        "AND constraint_name IN ('check_balance_usd_positive','check_balance_pen_positive')"
    )
    remaining = cur.fetchall()
    conn.close()
    if remaining:
        print(f"   ❌ Constraints aún presentes: {remaining}")
        sys.exit(1)
    else:
        print("   ✅ Constraints positivos eliminados de bank_balances")
except psycopg2.errors.UndefinedTable:
    print("   ⏭  bank_balances aún no existe — se creará en upgrade")
except Exception as e:
    print(f"   ⚠️  Error en patch directo bank_balances constraints: {e}")
PYEOF
echo ""

# ── Patch directo: rebote_detectado_en en ec_lote_items ──────────────────────
# Columna añadida por la migración Alembic ec07_rebote_detectado_en.
# Este patch es una red de seguridad: si Alembic ec07 no puede correr
# (p.ej. la DB está en el stamp-path y z9merge aún no fue aplicado),
# la columna se garantiza aquí de forma totalmente idempotente.
# En el flujo normal, ec07 ya habrá creado la columna y el ADD COLUMN IF NOT
# EXISTS simplemente no hace nada.
echo "⚡ Garantizando columna rebote_detectado_en en ec_lote_items..."
python3 - <<'PYEOF'
import os, sys
try:
    import psycopg2
except ImportError:
    print("   psycopg2 no disponible — saltando patch directo")
    sys.exit(0)
url = os.environ.get('DATABASE_URL', '')
if not url:
    print("   DATABASE_URL no definida — saltando patch directo")
    sys.exit(0)
try:
    conn = psycopg2.connect(url)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name='ec_lote_items'")
    if not cur.fetchone():
        print("   ⏭  ec_lote_items aún no existe — se creará en upgrade ec02")
        conn.close()
        sys.exit(0)
    cur.execute(
        "ALTER TABLE ec_lote_items "
        "ADD COLUMN IF NOT EXISTS rebote_detectado_en TIMESTAMP WITH TIME ZONE"
    )
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='ec_lote_items' AND column_name='rebote_detectado_en'"
    )
    exists = cur.fetchone()
    conn.close()
    if exists:
        print("   ✅ rebote_detectado_en: confirmada en ec_lote_items")
    else:
        print("   ❌ rebote_detectado_en: NO se pudo crear")
        sys.exit(1)
except Exception as e:
    print(f"   ⚠️  Error en patch rebote_detectado_en: {e}")
PYEOF
echo ""

# ── Patch directo: rebote_tipo en ec_lote_items ──────────────────────────────
# Columna añadida por ec08_rebote_tipo. Idempotente: ADD COLUMN IF NOT EXISTS.
echo "⚡ Garantizando columna rebote_tipo en ec_lote_items..."
python3 - <<'PYEOF'
import os, sys
try:
    import psycopg2
except ImportError:
    print("   psycopg2 no disponible — saltando patch directo")
    sys.exit(0)
url = os.environ.get('DATABASE_URL', '')
if not url:
    print("   DATABASE_URL no definida — saltando patch directo")
    sys.exit(0)
try:
    conn = psycopg2.connect(url)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name='ec_lote_items'")
    if not cur.fetchone():
        print("   ⏭  ec_lote_items aún no existe — se creará en upgrade ec02")
        conn.close()
        sys.exit(0)
    cur.execute(
        "ALTER TABLE ec_lote_items "
        "ADD COLUMN IF NOT EXISTS rebote_tipo TEXT"
    )
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='ec_lote_items' AND column_name='rebote_tipo'"
    )
    exists = cur.fetchone()
    conn.close()
    if exists:
        print("   ✅ rebote_tipo: confirmada en ec_lote_items")
    else:
        print("   ❌ rebote_tipo: NO se pudo crear")
        sys.exit(1)
except Exception as e:
    print(f"   ⚠️  Error en patch rebote_tipo: {e}")
PYEOF
echo ""

# ── Upgrade ───────────────────────────────────────────────────────────────────
# Usar "heads" (plural) para correr TODAS las ramas pendientes independientemente.
# Esto es necesario porque el grafo tiene múltiples heads sin merge.
echo "🚀 Ejecutando flask db upgrade heads..."
echo ""

flask db upgrade heads

echo ""
echo "✅ MIGRACIONES COMPLETADAS"
echo "=========================================="

# ── Patch directo: tablas del ecosistema worker ec01 ──────────────────────────
# Alembic puede omitir ec01_worker_tables cuando su down_revision ya está aplicada
# vía otra rama del grafo. Este patch idempotente garantiza que todas las tablas
# de ec01 existan, independientemente del comportamiento de Alembic.
echo "⚡ Garantizando tablas del ecosistema worker (ec01)..."
python3 - <<'PYEOF'
import os, sys
try:
    import psycopg2
except ImportError:
    print("   psycopg2 no disponible — saltando")
    sys.exit(0)
url = os.environ.get('DATABASE_URL', '')
if not url:
    sys.exit(0)
try:
    conn = psycopg2.connect(url)
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("""
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
    cur.execute("CREATE INDEX IF NOT EXISTS ix_ec_prosp_email ON ec_prospectos(email)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_ec_prosp_prio  ON ec_prospectos(prioridad, estado_email)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_ec_prosp_dirty ON ec_prospectos(sheets_dirty) WHERE sheets_dirty = 1")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS outreach_attempt (
            id               BIGSERIAL PRIMARY KEY,
            idempotency_key  TEXT UNIQUE NOT NULL,
            prospecto_id     BIGINT,
            email            TEXT NOT NULL,
            bandeja          TEXT,
            stage            TEXT,
            status           TEXT NOT NULL DEFAULT 'reserved'
                             CHECK (status IN ('reserved','sent','failed','retryable','unknown')),
            gmail_message_id TEXT,
            reserved_at      TIMESTAMPTZ DEFAULT NOW(),
            sent_at          TIMESTAMPTZ,
            error_msg        TEXT,
            agent_run_id     BIGINT
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS ix_attempt_email  ON outreach_attempt(email, stage)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_attempt_status ON outreach_attempt(status, reserved_at)")

    cur.execute("""
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
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_outreach_gmail ON outreach_log(gmail_message_id) WHERE gmail_message_id IS NOT NULL")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_outreach_email ON outreach_log(email)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_outreach_sent  ON outreach_log(sent_at)")

    cur.execute("""
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
    cur.execute("CREATE INDEX IF NOT EXISTS ix_response_email     ON response_log(email)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_response_procesado ON response_log(procesado) WHERE procesado = 0")

    cur.execute("""
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

    cur.execute("""
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
    cur.execute("CREATE INDEX IF NOT EXISTS ix_agent_runs_agent  ON agent_runs(agent, started_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_agent_runs_status ON agent_runs(status)")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS agent_heartbeat (
            agent          TEXT PRIMARY KEY,
            last_seen      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            status         TEXT NOT NULL DEFAULT 'offline',
            current_run_id BIGINT,
            pid            INTEGER,
            hostname       TEXT,
            dry_run        INTEGER DEFAULT NULL,
            updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS prospect_locks (
            prospecto_id BIGINT PRIMARY KEY,
            locked_by    TEXT NOT NULL,
            locked_at    TIMESTAMPTZ NOT NULL,
            expires_at   TIMESTAMPTZ NOT NULL
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS ix_locks_expires ON prospect_locks(expires_at)")

    cur.execute("""
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
    cur.execute("CREATE INDEX IF NOT EXISTS ix_state_log ON prospect_state_log(prospecto_id, created_at)")

    cur.execute("""
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
    cur.execute("CREATE INDEX IF NOT EXISTS ix_lead_pipeline_email  ON lead_pipeline(email)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_lead_pipeline_notif  ON lead_pipeline(notificado) WHERE notificado = 0")

    cur.execute("""
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

    cur.execute("""
        CREATE TABLE IF NOT EXISTS bandeja_estado (
            bandeja           TEXT PRIMARY KEY,
            enviados_hoy      INTEGER DEFAULT 0,
            bounce_count_24h  INTEGER DEFAULT 0,
            total_24h         INTEGER DEFAULT 0,
            pausada_hasta     TIMESTAMPTZ,
            ultimo_update     TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    cur.execute("INSERT INTO bandeja_estado(bandeja) VALUES ('ggarcia'), ('gerencia'), ('info') ON CONFLICT (bandeja) DO NOTHING")

    cur.execute("""
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
    cur.execute("CREATE INDEX IF NOT EXISTS ix_alerts_level ON alerts_log(level, created_at)")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS runtime_config (
            key        TEXT PRIMARY KEY,
            value      TEXT,
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            updated_by TEXT DEFAULT 'system'
        )
    """)
    cur.execute("INSERT INTO runtime_config(key, value, updated_by) VALUES ('dry_run', 'true', 'migration') ON CONFLICT (key) DO NOTHING")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sync_state (
            key        TEXT PRIMARY KEY,
            value      TEXT NOT NULL,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    conn.close()
    print("   ✅ Tablas ec01 (worker ecosystem) confirmadas en PostgreSQL")
except Exception as e:
    print(f"   ⚠️  Error en patch tablas ec01: {e}")
PYEOF
echo ""

# ── Patch directo: tablas del Centro de Inteligencia Comercial IA ─────────────
echo "⚡ Garantizando tablas de Inteligencia Comercial IA..."
python3 - <<'PYEOF'
import os, sys
try:
    import psycopg2
except ImportError:
    print("   psycopg2 no disponible — saltando patch directo")
    sys.exit(0)
url = os.environ.get('DATABASE_URL', '')
if not url:
    print("   DATABASE_URL no definida — saltando patch directo")
    sys.exit(0)
try:
    conn = psycopg2.connect(url)
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS email_eventos (
            id SERIAL PRIMARY KEY,
            cuenta VARCHAR(100) NOT NULL,
            mensaje_id VARCHAR(400) UNIQUE,
            remitente VARCHAR(300),
            asunto VARCHAR(500),
            tipo VARCHAR(50),
            confianza FLOAT DEFAULT 1.0,
            ia_usada BOOLEAN DEFAULT false,
            ia_tokens INTEGER DEFAULT 0,
            accion VARCHAR(300),
            email_afectado VARCHAR(200),
            email_nuevo VARCHAR(200),
            sheets_tab VARCHAR(50),
            crm_updated BOOLEAN DEFAULT false,
            sheets_updated BOOLEAN DEFAULT false,
            procesado_en TIMESTAMP WITHOUT TIME ZONE
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS oportunidades_comerciales (
            id SERIAL PRIMARY KEY,
            empresa VARCHAR(300),
            contacto VARCHAR(200),
            cargo VARCHAR(150),
            email VARCHAR(200),
            telefono VARCHAR(100),
            sector VARCHAR(100),
            prioridad VARCHAR(20),
            score INTEGER DEFAULT 0,
            volumen_usd_est INTEGER DEFAULT 0,
            necesidad TEXT,
            recomendacion TEXT,
            cuerpo_email TEXT,
            estado VARCHAR(50) DEFAULT 'nuevo',
            cuenta_origen VARCHAR(100),
            mensaje_id VARCHAR(400),
            prospecto_creado_id INTEGER REFERENCES prospectos(id),
            wa_alerta_enviada BOOLEAN DEFAULT false,
            detectado_en TIMESTAMP WITHOUT TIME ZONE,
            actualizado_en TIMESTAMP WITHOUT TIME ZONE
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ejecuciones_motor (
            id SERIAL PRIMARY KEY,
            motor VARCHAR(50),
            inicio TIMESTAMP WITHOUT TIME ZONE,
            fin TIMESTAMP WITHOUT TIME ZONE,
            duracion_seg FLOAT,
            correos_analizados INTEGER DEFAULT 0,
            rebotes INTEGER DEFAULT 0,
            oportunidades INTEGER DEFAULT 0,
            actualizaciones INTEGER DEFAULT 0,
            no_contactar INTEGER DEFAULT 0,
            ia_tokens INTEGER DEFAULT 0,
            ia_costo_usd FLOAT DEFAULT 0.0,
            errores INTEGER DEFAULT 0,
            estado VARCHAR(20) DEFAULT 'ok',
            resumen TEXT
        )
    """)

    # Crear índices si no existen
    for idx_sql in [
        "CREATE INDEX IF NOT EXISTS ix_email_eventos_cuenta ON email_eventos(cuenta)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_email_eventos_mensaje_id ON email_eventos(mensaje_id)",
        "CREATE INDEX IF NOT EXISTS ix_email_eventos_tipo ON email_eventos(tipo)",
        "CREATE INDEX IF NOT EXISTS ix_email_eventos_procesado_en ON email_eventos(procesado_en)",
        "CREATE INDEX IF NOT EXISTS ix_oportunidades_comerciales_email ON oportunidades_comerciales(email)",
        "CREATE INDEX IF NOT EXISTS ix_oportunidades_comerciales_prioridad ON oportunidades_comerciales(prioridad)",
        "CREATE INDEX IF NOT EXISTS ix_oportunidades_comerciales_estado ON oportunidades_comerciales(estado)",
        "CREATE INDEX IF NOT EXISTS ix_oportunidades_comerciales_detectado_en ON oportunidades_comerciales(detectado_en)",
        "CREATE INDEX IF NOT EXISTS ix_ejecuciones_motor_motor ON ejecuciones_motor(motor)",
    ]:
        cur.execute(idx_sql)

    conn.close()
    print("   ✅ Tablas de Inteligencia Comercial IA confirmadas en PostgreSQL")
except Exception as e:
    print(f"   ⚠️  Error en patch Inteligencia: {e}")
PYEOF
echo ""

# ── Patch directo: tablas del Ecosistema de Agentes IA ───────────────────────
echo "⚡ Garantizando tablas de Agentes IA..."
python3 - <<'PYEOF'
import os, sys
try:
    import psycopg2
except ImportError:
    print("   psycopg2 no disponible — saltando patch directo")
    sys.exit(0)
url = os.environ.get('DATABASE_URL', '')
if not url:
    print("   DATABASE_URL no definida — saltando patch directo")
    sys.exit(0)
try:
    conn = psycopg2.connect(url)
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS agent_status (
            id SERIAL PRIMARY KEY,
            agent_id VARCHAR(50) UNIQUE NOT NULL,
            name VARCHAR(100) NOT NULL,
            description VARCHAR(300),
            icon VARCHAR(50),
            color VARCHAR(20),
            status VARCHAR(20) NOT NULL DEFAULT 'idle',
            last_run TIMESTAMP WITHOUT TIME ZONE,
            next_run TIMESTAMP WITHOUT TIME ZONE,
            run_interval INTEGER DEFAULT 900,
            tasks_today INTEGER DEFAULT 0,
            errors_today INTEGER DEFAULT 0,
            total_tasks INTEGER DEFAULT 0,
            total_errors INTEGER DEFAULT 0,
            last_result TEXT,
            last_error TEXT,
            enabled BOOLEAN NOT NULL DEFAULT true,
            paused_by INTEGER REFERENCES users(id),
            paused_at TIMESTAMP WITHOUT TIME ZONE,
            performance FLOAT DEFAULT 100.0,
            created_at TIMESTAMP WITHOUT TIME ZONE,
            updated_at TIMESTAMP WITHOUT TIME ZONE
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS agent_logs (
            id SERIAL PRIMARY KEY,
            agent_id VARCHAR(50) NOT NULL REFERENCES agent_status(agent_id),
            level VARCHAR(10) DEFAULT 'INFO',
            message TEXT NOT NULL,
            detail TEXT,
            created_at TIMESTAMP WITHOUT TIME ZONE
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS agent_alerts (
            id SERIAL PRIMARY KEY,
            agent_id VARCHAR(50) REFERENCES agent_status(agent_id),
            severity VARCHAR(20) DEFAULT 'warning',
            title VARCHAR(200) NOT NULL,
            message TEXT NOT NULL,
            resolved BOOLEAN DEFAULT false,
            resolved_by INTEGER REFERENCES users(id),
            resolved_at TIMESTAMP WITHOUT TIME ZONE,
            created_at TIMESTAMP WITHOUT TIME ZONE
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS agent_metrics (
            id SERIAL PRIMARY KEY,
            agent_id VARCHAR(50) NOT NULL,
            date DATE NOT NULL,
            runs INTEGER DEFAULT 0,
            tasks_completed INTEGER DEFAULT 0,
            errors INTEGER DEFAULT 0,
            prospects_found INTEGER DEFAULT 0,
            prospects_validated INTEGER DEFAULT 0,
            emails_sent INTEGER DEFAULT 0,
            emails_analyzed INTEGER DEFAULT 0,
            bounces_detected INTEGER DEFAULT 0,
            opportunities INTEGER DEFAULT 0,
            duplicates_removed INTEGER DEFAULT 0,
            followups_scheduled INTEGER DEFAULT 0,
            created_at TIMESTAMP WITHOUT TIME ZONE,
            CONSTRAINT uq_agent_metric_day UNIQUE (agent_id, date)
        )
    """)

    for idx_sql in [
        "CREATE INDEX IF NOT EXISTS ix_agent_status_agent_id ON agent_status(agent_id)",
        "CREATE INDEX IF NOT EXISTS ix_agent_status_status ON agent_status(status)",
        "CREATE INDEX IF NOT EXISTS ix_agent_logs_agent_id ON agent_logs(agent_id)",
        "CREATE INDEX IF NOT EXISTS ix_agent_logs_level ON agent_logs(level)",
        "CREATE INDEX IF NOT EXISTS ix_agent_logs_created_at ON agent_logs(created_at)",
        "CREATE INDEX IF NOT EXISTS ix_agent_alerts_agent_id ON agent_alerts(agent_id)",
        "CREATE INDEX IF NOT EXISTS ix_agent_alerts_severity ON agent_alerts(severity)",
        "CREATE INDEX IF NOT EXISTS ix_agent_alerts_resolved ON agent_alerts(resolved)",
        "CREATE INDEX IF NOT EXISTS ix_agent_alerts_created_at ON agent_alerts(created_at)",
        "CREATE INDEX IF NOT EXISTS ix_agent_metrics_agent_id ON agent_metrics(agent_id)",
        "CREATE INDEX IF NOT EXISTS ix_agent_metrics_date ON agent_metrics(date)",
    ]:
        cur.execute(idx_sql)

    conn.close()
    print("   ✅ Tablas de Agentes IA confirmadas en PostgreSQL")
except Exception as e:
    print(f"   ⚠️  Error en patch Agentes IA: {e}")
PYEOF
echo ""

# ── Patch directo: columnas cotiz_* en wa_bot_sessions ───────────────────────
# La migración w1a2b3o4t5s6 puede no haberse ejecutado en producción,
# causando que el bot no responda (SQLAlchemy falla al acceder session.cotiz_op).
echo "⚡ Garantizando columnas cotiz_* en wa_bot_sessions..."
python3 - <<'PYEOF'
import os, sys
try:
    import psycopg2
except ImportError:
    print("   psycopg2 no disponible — saltando patch directo")
    sys.exit(0)
url = os.environ.get('DATABASE_URL', '')
if not url:
    print("   DATABASE_URL no definida — saltando patch directo")
    sys.exit(0)
try:
    conn = psycopg2.connect(url)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name='wa_bot_sessions'")
    if not cur.fetchone():
        print("   ⏭  wa_bot_sessions aún no existe — se creará en upgrade")
        conn.close()
        sys.exit(0)
    cur.execute("ALTER TABLE wa_bot_sessions ADD COLUMN IF NOT EXISTS cotiz_op VARCHAR(10) DEFAULT ''")
    cur.execute("ALTER TABLE wa_bot_sessions ADD COLUMN IF NOT EXISTS cotiz_importe FLOAT DEFAULT 0")
    cur.execute("ALTER TABLE wa_bot_sessions ADD COLUMN IF NOT EXISTS cotiz_tc FLOAT DEFAULT 0")
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='wa_bot_sessions' AND column_name IN ('cotiz_op','cotiz_importe','cotiz_tc')"
    )
    found = [r[0] for r in cur.fetchall()]
    conn.close()
    cur.execute("ALTER TABLE wa_bot_sessions ADD COLUMN IF NOT EXISTS cotiz_doc VARCHAR(20) DEFAULT ''")
    cur.execute("ALTER TABLE wa_bot_sessions ADD COLUMN IF NOT EXISTS cotiz_email VARCHAR(120) DEFAULT ''")
    cur.execute("ALTER TABLE wa_bot_sessions ADD COLUMN IF NOT EXISTS cotiz_op_id VARCHAR(20) DEFAULT ''")
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='wa_bot_sessions' AND column_name IN ('cotiz_op','cotiz_importe','cotiz_tc','cotiz_doc','cotiz_email','cotiz_op_id')"
    )
    found = [r[0] for r in cur.fetchall()]
    conn.close()
    if len(found) == 6:
        print("   ✅ cotiz_* (6 cols) confirmadas en wa_bot_sessions")
    else:
        print(f"   ❌ Solo se encontraron: {found}")
        sys.exit(1)
except Exception as e:
    print(f"   ⚠️  Error en patch cotiz_* wa_bot_sessions: {e}")
PYEOF
echo ""

# ── Patch directo: columnas de calidad de datos en fx_rate_current ─────────────
# Agrega last_attempt_at, data_source, last_error para diagnóstico del FX Monitor.
# Totalmente idempotente (ADD COLUMN IF NOT EXISTS).
echo "⚡ Garantizando columnas de calidad en fx_rate_current..."
python3 - <<'PYEOF'
import os, sys
try:
    import psycopg2
except ImportError:
    print("   psycopg2 no disponible — saltando patch directo")
    sys.exit(0)
url = os.environ.get('DATABASE_URL', '')
if not url:
    print("   DATABASE_URL no definida — saltando patch directo")
    sys.exit(0)
try:
    conn = psycopg2.connect(url)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name='fx_rate_current'")
    if not cur.fetchone():
        print("   ⏭  fx_rate_current aún no existe — se creará en upgrade")
        conn.close()
        sys.exit(0)
    cur.execute("ALTER TABLE fx_rate_current ADD COLUMN IF NOT EXISTS last_attempt_at TIMESTAMP WITHOUT TIME ZONE")
    cur.execute("ALTER TABLE fx_rate_current ADD COLUMN IF NOT EXISTS last_valid_at TIMESTAMP WITHOUT TIME ZONE")
    cur.execute("ALTER TABLE fx_rate_current ADD COLUMN IF NOT EXISTS data_source VARCHAR(20)")
    cur.execute("ALTER TABLE fx_rate_current ADD COLUMN IF NOT EXISTS last_error VARCHAR(255)")
    cur.execute("ALTER TABLE fx_rate_current ADD COLUMN IF NOT EXISTS source_updated_at TIMESTAMP WITHOUT TIME ZONE")
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='fx_rate_current' AND column_name IN "
        "('last_attempt_at','last_valid_at','data_source','last_error','source_updated_at')"
    )
    found = [r[0] for r in cur.fetchall()]
    conn.close()
    if len(found) == 5:
        print("   ✅ last_attempt_at, last_valid_at, data_source, last_error, source_updated_at confirmadas en fx_rate_current")
    else:
        print(f"   ❌ Solo encontradas: {found}")
        sys.exit(1)
except Exception as e:
    print(f"   ⚠️  Error en patch fx_rate_current: {e}")
PYEOF
echo ""

# ── Patch directo: columnas campaña WA en wa_bot_sessions ────────────────────
echo "⚡ Garantizando columnas de campaña WA en wa_bot_sessions..."
python3 - <<'PYEOF'
import os, sys
try:
    import psycopg2
except ImportError:
    print("   psycopg2 no disponible — saltando patch directo")
    sys.exit(0)
url = os.environ.get('DATABASE_URL', '')
if not url:
    print("   DATABASE_URL no definida — saltando patch directo")
    sys.exit(0)
try:
    conn = psycopg2.connect(url)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name='wa_bot_sessions'")
    if not cur.fetchone():
        print("   ⏭  wa_bot_sessions aún no existe — se creará en upgrade")
        conn.close()
        sys.exit(0)
    cur.execute("ALTER TABLE wa_bot_sessions ADD COLUMN IF NOT EXISTS opt_out_wa          BOOLEAN DEFAULT FALSE")
    cur.execute("ALTER TABLE wa_bot_sessions ADD COLUMN IF NOT EXISTS campana_secuencia    INTEGER DEFAULT 0")
    cur.execute("ALTER TABLE wa_bot_sessions ADD COLUMN IF NOT EXISTS campana_ultimo_envio TIMESTAMP WITHOUT TIME ZONE")
    cur.execute("ALTER TABLE wa_bot_sessions ADD COLUMN IF NOT EXISTS campana_pausada      BOOLEAN DEFAULT FALSE")
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='wa_bot_sessions' AND column_name IN "
        "('opt_out_wa','campana_secuencia','campana_ultimo_envio','campana_pausada')"
    )
    found = [r[0] for r in cur.fetchall()]
    conn.close()
    if len(found) == 4:
        print("   ✅ opt_out_wa, campana_secuencia, campana_ultimo_envio, campana_pausada confirmadas en wa_bot_sessions")
    else:
        print(f"   ❌ Solo se encontraron: {found}")
        sys.exit(1)
except Exception as e:
    print(f"   ⚠️  Error en patch columnas campaña WA: {e}")
PYEOF
echo ""

# ── Patch directo: cotiz_mod_token y cotiz_nuevo_importe en wa_bot_sessions ───
echo "⚡ Garantizando cotiz_mod_token y cotiz_nuevo_importe en wa_bot_sessions..."
python3 - <<'PYEOF'
import os, sys
try:
    import psycopg2
except ImportError:
    print("   psycopg2 no disponible — saltando patch directo")
    sys.exit(0)
url = os.environ.get('DATABASE_URL', '')
if not url:
    print("   DATABASE_URL no definida — saltando patch directo")
    sys.exit(0)
try:
    conn = psycopg2.connect(url)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name='wa_bot_sessions'")
    if not cur.fetchone():
        print("   ⏭  wa_bot_sessions aún no existe — se creará en upgrade")
        conn.close()
        sys.exit(0)
    cur.execute("ALTER TABLE wa_bot_sessions ADD COLUMN IF NOT EXISTS cotiz_mod_token     VARCHAR(36)")
    cur.execute("ALTER TABLE wa_bot_sessions ADD COLUMN IF NOT EXISTS cotiz_nuevo_importe FLOAT DEFAULT 0")
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='wa_bot_sessions' AND column_name IN "
        "('cotiz_mod_token','cotiz_nuevo_importe')"
    )
    found = [r[0] for r in cur.fetchall()]
    conn.close()
    if len(found) == 2:
        print("   ✅ cotiz_mod_token, cotiz_nuevo_importe confirmadas en wa_bot_sessions")
    else:
        print(f"   ❌ Solo se encontraron: {found}")
        sys.exit(1)
except Exception as e:
    print(f"   ⚠️  Error en patch cotiz_mod_token/cotiz_nuevo_importe: {e}")
PYEOF
echo ""

# ── Patch directo: columnas faltantes en wa_messages ─────────────────────────
echo "⚡ Garantizando columnas wa_id, tipo, origen, media_id, media_tipo en wa_messages..."
python3 - <<'PYEOF'
import os, sys
try:
    import psycopg2
except ImportError:
    print("   psycopg2 no disponible — saltando patch directo")
    sys.exit(0)
url = os.environ.get('DATABASE_URL', '')
if not url:
    print("   DATABASE_URL no definida — saltando patch directo")
    sys.exit(0)
try:
    conn = psycopg2.connect(url)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name='wa_messages'")
    if not cur.fetchone():
        print("   ⏭  wa_messages aún no existe — se creará en upgrade")
        conn.close()
        sys.exit(0)
    cur.execute("ALTER TABLE wa_messages ADD COLUMN IF NOT EXISTS wa_id      VARCHAR(120) DEFAULT ''")
    cur.execute("ALTER TABLE wa_messages ADD COLUMN IF NOT EXISTS media_id   VARCHAR(120) DEFAULT ''")
    cur.execute("ALTER TABLE wa_messages ADD COLUMN IF NOT EXISTS media_tipo VARCHAR(20)  DEFAULT ''")
    cur.execute("ALTER TABLE wa_messages ADD COLUMN IF NOT EXISTS tipo       VARCHAR(20)  DEFAULT 'mensaje'")
    cur.execute("ALTER TABLE wa_messages ADD COLUMN IF NOT EXISTS origen     VARCHAR(20)  DEFAULT 'bot'")
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='wa_messages' AND column_name IN "
        "('wa_id','media_id','media_tipo','tipo','origen')"
    )
    found = [r[0] for r in cur.fetchall()]
    conn.close()
    if len(found) == 5:
        print("   ✅ wa_id, media_id, media_tipo, tipo, origen confirmadas en wa_messages")
    else:
        print(f"   ❌ Solo se encontraron: {found}")
        sys.exit(1)
except Exception as e:
    print(f"   ⚠️  Error en patch wa_messages columnas: {e}")
PYEOF
echo ""

# ── Patch directo: índice compuesto (numero, id DESC) en wa_messages ──────────
# Acelera la carga del historial: la query de los últimos 150 mensajes pasa de
# index scan + filesort a un index-only scan sobre (numero, id).
echo "⚡ Garantizando índice de rendimiento en wa_messages(numero, id)..."
python3 - <<'PYEOF'
import os, sys
try:
    import psycopg2
except ImportError:
    print("   psycopg2 no disponible — saltando")
    sys.exit(0)
url = os.environ.get('DATABASE_URL', '')
if not url:
    sys.exit(0)
try:
    conn = psycopg2.connect(url)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(
        "CREATE INDEX IF NOT EXISTS ix_wa_messages_numero_id "
        "ON wa_messages (numero, id DESC)"
    )
    conn.close()
    print("   ✅ ix_wa_messages_numero_id OK")
except Exception as e:
    print(f"   ⚠️  Error en patch índice wa_messages: {e}")
PYEOF
echo ""
# ── Patch directo: tablas del Estudio Creativo (pipeline + brand) ─────────────
# Seguridad adicional: si flask db upgrade heads falla antes de e1s2t3u4d5i6,
# estas tablas se crean de todas formas. Totalmente idempotente (IF NOT EXISTS).
echo "⚡ Garantizando tablas del Estudio Creativo (content_pipelines, pipeline_stages, content_sources, brand_configs)..."
python3 - <<'PYEOF'
import os, sys
try:
    import psycopg2
except ImportError:
    print("   psycopg2 no disponible — saltando patch directo Estudio Creativo")
    sys.exit(0)
url = os.environ.get('DATABASE_URL', '')
if not url:
    print("   DATABASE_URL no definida — saltando patch directo Estudio Creativo")
    sys.exit(0)
try:
    conn = psycopg2.connect(url)
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS content_pipelines (
            id                SERIAL PRIMARY KEY,
            created_at        TIMESTAMP WITHOUT TIME ZONE,
            updated_at        TIMESTAMP WITHOUT TIME ZONE,
            created_by        INTEGER REFERENCES users(id),
            type              VARCHAR(20) NOT NULL,
            title             VARCHAR(200),
            status            VARCHAR(30) DEFAULT 'running',
            current_stage_seq INTEGER DEFAULT 1,
            notes             TEXT,
            error_msg         TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_stages (
            id               SERIAL PRIMARY KEY,
            pipeline_id      INTEGER NOT NULL REFERENCES content_pipelines(id),
            seq              INTEGER NOT NULL,
            agent_role       VARCHAR(40) NOT NULL,
            status           VARCHAR(30) DEFAULT 'pending',
            input_data       TEXT,
            output_data      TEXT,
            version          INTEGER DEFAULT 1,
            started_at       TIMESTAMP WITHOUT TIME ZONE,
            completed_at     TIMESTAMP WITHOUT TIME ZONE,
            error_msg        TEXT,
            user_instruction TEXT,
            review_notes     TEXT,
            approved_by      INTEGER REFERENCES users(id),
            approved_at      TIMESTAMP WITHOUT TIME ZONE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS content_sources (
            id               SERIAL PRIMARY KEY,
            pipeline_id      INTEGER REFERENCES content_pipelines(id),
            stage_id         INTEGER REFERENCES pipeline_stages(id),
            fetched_at       TIMESTAMP WITHOUT TIME ZONE,
            url              VARCHAR(2000),
            title            VARCHAR(500),
            excerpt          TEXT,
            published_at     VARCHAR(30),
            source_name      VARCHAR(200),
            source_type      VARCHAR(30),
            is_verified      BOOLEAN DEFAULT false,
            used_in_analysis BOOLEAN DEFAULT false
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS brand_configs (
            id                SERIAL PRIMARY KEY,
            updated_at        TIMESTAMP WITHOUT TIME ZONE,
            updated_by        INTEGER REFERENCES users(id),
            verified_benefits TEXT DEFAULT '[]',
            prohibited_claims TEXT DEFAULT '[]',
            tone_guide        TEXT DEFAULT '',
            hashtag_sets      TEXT DEFAULT '{}',
            approved_channels VARCHAR(200) DEFAULT 'linkedin,instagram,facebook,reel',
            enabled_sources   VARCHAR(500) DEFAULT 'bcrp,sbs,el_comercio,gestion,peru21'
        )
    """)

    conn.close()
    print("   ✅ Tablas Estudio Creativo confirmadas en PostgreSQL")
except Exception as e:
    print(f"   ⚠️  Error en patch Estudio Creativo: {e}")
PYEOF
echo ""
