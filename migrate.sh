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

# ── Upgrade ───────────────────────────────────────────────────────────────────
echo "🚀 Ejecutando flask db upgrade..."
echo ""

flask db upgrade

echo ""
echo "✅ MIGRACIONES COMPLETADAS"
echo "=========================================="
