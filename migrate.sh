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
    else
        echo "   ✅ Revisión reconocida."
        echo ""
    fi
else
    echo "   DB nueva o sin versión — ejecutando migración completa."
    echo ""
fi

# ── Asegurar todos los heads de ramas independientes ──────────────────────────
# Si la DB tiene solo algunos de los 5 heads, el merge migration z9merge_all_heads
# no puede aplicarse. Stampeamos cada uno de forma idempotente (si ya existe, no falla).
echo "🔧 Registrando heads de ramas independientes (idempotente)..."
for HEAD_REV in a1b2c3d4e5f6 d2a3t4e5c6r7 l1s2o3u4r5c6 p1r2o3s4p5e6 t1e2m3p4l5a6 z9merge_all_heads w1p2r3o4s5p6; do
    flask db stamp "$HEAD_REV" 2>/dev/null || true
done
echo "   ✅ Heads registrados."
echo ""

# ── Upgrade ───────────────────────────────────────────────────────────────────
echo "🚀 Ejecutando flask db upgrade..."
echo ""

flask db upgrade

echo ""
echo "✅ MIGRACIONES COMPLETADAS"
echo "=========================================="
