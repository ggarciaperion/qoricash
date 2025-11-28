#!/usr/bin/env python
"""
Script para ejecutar migraciones de base de datos en producción
Ejecutar en Render Shell: python migrate_db.py
"""
import os
import sys

# Agregar el directorio actual al path
sys.path.insert(0, os.path.dirname(__file__))

# Monkey patch de eventlet PRIMERO
import eventlet
eventlet.monkey_patch()

# Configurar psycopg2 para eventlet
try:
    from psycogreen.eventlet import patch_psycopg
    patch_psycopg()
    print("[MIGRATE] psycopg2 patched con psycogreen")
except ImportError:
    print("[MIGRATE] WARNING: psycogreen no disponible")

from app import create_app
from app.extensions import db
from flask_migrate import upgrade

def run_migrations():
    """Ejecutar migraciones pendientes"""
    app = create_app()

    with app.app_context():
        print("=" * 80)
        print("EJECUTAR MIGRACIONES - QoriCash Trading")
        print("=" * 80)

        print("\n📋 Base de datos actual:")
        print(f"   URI: {app.config['SQLALCHEMY_DATABASE_URI'][:50]}...")

        print("\n🔄 Ejecutando migraciones...")

        try:
            # Ejecutar migraciones
            upgrade()
            print("\n✅ Migraciones ejecutadas exitosamente!")

            # Verificar tablas
            print("\n📊 Verificando estructura de base de datos...")
            from sqlalchemy import inspect
            inspector = inspect(db.engine)

            tables = inspector.get_table_names()
            print(f"\n✅ Tablas encontradas ({len(tables)}):")
            for table in sorted(tables):
                columns = inspector.get_columns(table)
                print(f"   - {table} ({len(columns)} columnas)")

            # Verificar columna específica de operations
            if 'operations' in tables:
                print("\n🔍 Columnas de la tabla 'operations':")
                operations_columns = inspector.get_columns('operations')
                for col in operations_columns:
                    print(f"   - {col['name']}: {col['type']}")

                # Verificar si existe assigned_operator_id
                has_assigned_operator = any(col['name'] == 'assigned_operator_id' for col in operations_columns)
                if has_assigned_operator:
                    print("\n✅ Columna 'assigned_operator_id' existe!")
                else:
                    print("\n⚠️  Columna 'assigned_operator_id' NO existe - puede requerir migración adicional")

        except Exception as e:
            print(f"\n❌ Error al ejecutar migraciones: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

        print("\n" + "=" * 80)
        return True

if __name__ == '__main__':
    success = run_migrations()
    sys.exit(0 if success else 1)
