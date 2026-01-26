#!/bin/bash
# Script para ejecutar migraciones en Render
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

echo "✅ Variables de entorno verificadas"
echo "   DATABASE_URL: ${DATABASE_URL:0:30}..." # Mostrar solo inicio por seguridad
echo ""

# Mostrar historial de revisiones disponibles
echo "📚 Revisiones disponibles en migrations/versions:"
ls -lh migrations/versions/*.py 2>/dev/null || echo "   (No se encontraron archivos de migración)"
echo ""

# Cambiar al directorio del script
cd "$(dirname "$0")" || exit 1

echo "🚀 Ejecutando migraciones con Flask-Migrate..."
echo ""

# Ejecutar migraciones
flask db upgrade

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ MIGRACIÓN EJECUTADA CON ÉXITO"
    echo ""
    echo "=========================================="
    echo "   MIGRACIONES COMPLETADAS"
    echo "=========================================="
    exit 0
else
    echo ""
    echo "❌ ERROR AL EJECUTAR MIGRACIÓN"
    exit 1
fi
