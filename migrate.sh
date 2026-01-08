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

echo "✅ Variables de entorno verificadas"
echo "   DATABASE_URL: ${DATABASE_URL:0:30}..." # Mostrar solo inicio por seguridad
echo ""

# Mostrar historial de revisiones disponibles
echo "📚 Revisiones disponibles en migrations/versions:"
ls -lh migrations/versions/*.py 2>/dev/null || echo "   (No se encontraron archivos de migración)"
echo ""

echo "🚀 Ejecutando migración manual con SQL directo..."
echo "   (Evitando conflictos con eventlet)"
echo ""

# Cambiar al directorio del script
cd "$(dirname "$0")" || exit 1

# Ejecutar script SQL directamente (más seguro que flask db upgrade con eventlet)
if command -v psql &> /dev/null; then
    echo "📡 Conectando a PostgreSQL..."
    psql "$DATABASE_URL" < manual_migration.sql

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
        echo "❌ ERROR AL EJECUTAR MIGRACIÓN SQL"
        exit 1
    fi
else
    echo "⚠️  psql no disponible, intentando con Python..."
    echo ""

    # Alternativa: usar psycopg2 directamente
    python3 << 'PYTHON_SCRIPT'
import os
import psycopg2

DATABASE_URL = os.environ.get('DATABASE_URL')

print("📡 Conectando a PostgreSQL con psycopg2...")

try:
    # Leer script SQL
    with open('manual_migration.sql', 'r') as f:
        sql_script = f.read()

    # Conectar y ejecutar
    conn = psycopg2.connect(DATABASE_URL)
    conn.set_session(autocommit=False)
    cur = conn.cursor()

    # Ejecutar script
    cur.execute(sql_script)
    conn.commit()

    print("\n✅ MIGRACIÓN EJECUTADA CON ÉXITO\n")
    print("=" * 50)
    print("   MIGRACIONES COMPLETADAS")
    print("=" * 50)

    cur.close()
    conn.close()
    exit(0)

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
PYTHON_SCRIPT

    exit $?
fi
