#!/bin/bash
# Script para ejecutar migraciones manualmente en Render
# Uso: bash migrate.sh

set -e  # Salir inmediatamente si un comando falla

echo "=========================================="
echo "   INICIANDO MIGRACIONES DE BASE DE DATOS"
echo "=========================================="
echo ""

# Verificar variables de entorno críticas
if [ -z "$DATABASE_URL" ]; then
    echo "❌ ERROR: DATABASE_URL no está configurada"
    exit 1
fi

if [ -z "$FLASK_APP" ]; then
    echo "⚠️  ADVERTENCIA: FLASK_APP no está configurada, usando valor por defecto"
    export FLASK_APP=run.py
fi

echo "✅ Variables de entorno verificadas"
echo "   FLASK_APP: $FLASK_APP"
echo "   DATABASE_URL: ${DATABASE_URL:0:30}..." # Mostrar solo inicio por seguridad
echo ""

# Mostrar revisión actual de la base de datos
echo "📋 Revisión actual de la base de datos:"
python -m flask db current || echo "   (No se pudo obtener la revisión actual)"
echo ""

# Mostrar historial de revisiones disponibles
echo "📚 Revisiones disponibles en migrations/versions:"
ls -lh migrations/versions/*.py 2>/dev/null || echo "   (No se encontraron archivos de migración)"
echo ""

# Ejecutar migraciones
echo "🚀 Ejecutando migraciones..."
python -m flask db upgrade

# Verificar resultado
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ MIGRACIONES EJECUTADAS CON ÉXITO"
    echo ""
    echo "📋 Revisión actual después de la migración:"
    python -m flask db current
    echo ""
    echo "=========================================="
    echo "   MIGRACIONES COMPLETADAS"
    echo "=========================================="
else
    echo ""
    echo "❌ ERROR AL EJECUTAR MIGRACIONES"
    echo "   Revise los logs anteriores para identificar el problema"
    exit 1
fi
