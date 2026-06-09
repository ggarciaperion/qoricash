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
        echo ""

        # Registrar todas las ramas conocidas para que flask db upgrade heads
        # pueda arrancar desde el estado correcto en DBs con historial antiguo.
        echo "🔧 Registrando heads de ramas conocidas (solo para DB con historial antiguo)..."
        for HEAD_REV in a1b2c3d4e5f6 d2a3t4e5c6r7 l1s2o3u4r5c6 p1r2o3s4p5e6 t1e2m3p4l5a6 z9merge_all_heads w1p2r3o4s5p6 pb1r2e3c4i5o b1a2n3k4b5a6 k1y2c3d4e5f6 p1e2r3i4o5d6 a1u2d3i4t5o6 b1c2a3j4a5d6 c1m2e3r4g5e6; do
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
