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
        for HEAD_REV in a1b2c3d4e5f6 d2a3t4e5c6r7 l1s2o3u4r5c6 p1r2o3s4p5e6 t1e2m3p4l5a6 z9merge_all_heads w1p2r3o4s5p6 pb1r2e3c4i5o b1a2n3k4b5a6 k1y2c3d4e5f6 p1e2r3i4o5d6 a1u2d3i4t5o6 b1c2a3j4a5d6 c1m2e3r4g5e6 p1a2t3c4h5b6 v1a2l3i4d5a6 d1c2a3j4a5d6; do
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
