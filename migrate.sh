#!/bin/bash
# Script para ejecutar migraciones en Render
# Maneja tanto DBs nuevas como producción existente con historial antiguo.

set -e

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

# ── Detección de estado actual de la DB ──────────────────────────────────────
# Si la versión en alembic_version NO existe en nuestro historial,
# es una DB con migraciones antiguas → stampeamos al baseline sin borrar datos.

echo "🔍 Verificando estado de la base de datos..."

CURRENT=$(flask db current 2>&1 | grep -E '^[a-f0-9]' | head -1 || true)

if [ -n "$CURRENT" ]; then
    echo "   Revisión actual en DB: $CURRENT"

    KNOWN=$(flask db history 2>&1 | grep "$CURRENT" || true)

    if [ -z "$KNOWN" ]; then
        echo ""
        echo "⚠️  Revisión '$CURRENT' no pertenece al historial actual."
        echo "   DB existente con migraciones antiguas — aplicando baseline seguro..."
        echo "   (NINGUNA tabla será eliminada ni modificada)"
        echo ""

        flask db stamp --purge
        flask db stamp 85a767945dcc

        echo "✅ DB stampeada a baseline 85a767945dcc"
        echo "   (todas las migraciones hasta p1a2t3c4h5b6 serán marcadas como ya ejecutadas)"
        echo "   (solo v1a2l3i4d5a6 correrá — agrega is_validated si falta)"
        echo ""

        # Registrar todas las ramas conocidas para que flask db upgrade heads
        # pueda arrancar desde el estado correcto en DBs con historial antiguo.
        echo "🔧 Registrando heads de ramas conocidas (solo para DB con historial antiguo)..."
        # Nota: b1a2n3k4b5a6 OMITIDO — manejado por patch directo psycopg2 arriba
        for HEAD_REV in a1b2c3d4e5f6 d2a3t4e5c6r7 l1s2o3u4r5c6 p1r2o3s4p5e6 t1e2m3p4l5a6 z9merge_all_heads w1p2r3o4s5p6 pb1r2e3c4i5o k1y2c3d4e5f6 p1e2r3i4o5d6 a1u2d3i4t5o6 b1c2a3j4a5d6 c1m2e3r4g5e6 p1a2t3c4h5b6 v1a2l3i4d5a6 d1c2a3j4a5d6 aa1s2i3n4w5a6 i1a2i3n4t5e6 a5907b w1a2b3o4t5s6; do
            flask db stamp "$HEAD_REV" 2>/dev/null || true
        done
        echo "   ✅ Heads registrados."
        echo ""
    else
        echo "   ✅ Revisión reconocida — sin stamp (evitar downgrade)."
        echo ""
    fi
else
    echo "   DB nueva o sin versión — ejecutando migración completa."
    echo ""
fi

# ── Upgrade ───────────────────────────────────────────────────────────────────
# Usar "heads" (plural) para correr TODAS las ramas pendientes independientemente.
# Esto es necesario porque el grafo tiene múltiples heads sin merge.
echo "🚀 Ejecutando flask db upgrade heads..."
echo ""

flask db upgrade heads

echo ""
echo "✅ MIGRACIONES COMPLETADAS"
echo "=========================================="

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
    if len(found) == 3:
        print("   ✅ cotiz_op, cotiz_importe, cotiz_tc confirmadas en wa_bot_sessions")
    else:
        print(f"   ❌ Solo se encontraron: {found}")
        sys.exit(1)
except Exception as e:
    print(f"   ⚠️  Error en patch cotiz_* wa_bot_sessions: {e}")
PYEOF
echo ""
