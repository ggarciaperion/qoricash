#!/usr/bin/env python
"""
Script para sincronizar el esquema de base de datos con los modelos
ADVERTENCIA: Solo usar en desarrollo o cuando la estructura está desincronizada
Ejecutar en Render Shell: python sync_database_schema.py
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
    print("[SYNC] psycopg2 patched con psycogreen")
except ImportError:
    print("[SYNC] WARNING: psycogreen no disponible")

from app import create_app
from app.extensions import db
from sqlalchemy import inspect, text

def sync_schema():
    """Sincronizar esquema de base de datos"""
    app = create_app()

    with app.app_context():
        print("=" * 80)
        print("SINCRONIZAR ESQUEMA DE BASE DE DATOS")
        print("=" * 80)

        inspector = inspect(db.engine)

        # Obtener todas las columnas esperadas de los modelos
        from app.models.client import Client
        from app.models.operation import Operation

        models_to_check = [
            (Client, 'clients'),
            (Operation, 'operations')
        ]

        for model, table_name in models_to_check:
            print(f"\n{'='*80}")
            print(f"Verificando tabla: {table_name}")
            print('='*80)

            # Obtener columnas actuales en la BD
            try:
                actual_columns = {col['name']: col for col in inspector.get_columns(table_name)}
                print(f"\n✅ Tabla existe con {len(actual_columns)} columnas")
            except Exception as e:
                print(f"\n❌ Error: {e}")
                continue

            # Obtener columnas esperadas del modelo
            expected_columns = {}
            for column in model.__table__.columns:
                expected_columns[column.name] = column

            # Encontrar columnas faltantes
            missing_columns = set(expected_columns.keys()) - set(actual_columns.keys())

            if missing_columns:
                print(f"\n⚠️  Columnas faltantes: {len(missing_columns)}")

                for col_name in sorted(missing_columns):
                    col = expected_columns[col_name]
                    print(f"\n   Agregando: {col_name} ({col.type})")

                    try:
                        # Construir el ALTER TABLE
                        col_type = str(col.type)
                        nullable = "NULL" if col.nullable else "NOT NULL"
                        default = ""

                        # Determinar valor por defecto según el tipo
                        if not col.nullable:
                            if 'VARCHAR' in col_type or 'TEXT' in col_type:
                                default = "DEFAULT ''"
                            elif 'INTEGER' in col_type:
                                default = "DEFAULT 0"
                            elif 'BOOLEAN' in col_type:
                                default = "DEFAULT FALSE"
                            elif 'DATETIME' in col_type or 'TIMESTAMP' in col_type:
                                default = "DEFAULT CURRENT_TIMESTAMP"

                        # Para columnas nullables, no necesitamos default
                        if col.nullable:
                            default = ""
                            nullable = "NULL"

                        sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type} {default} {nullable};"

                        print(f"   SQL: {sql}")
                        db.session.execute(text(sql))
                        db.session.commit()
                        print(f"   ✅ Columna agregada!")

                    except Exception as e:
                        db.session.rollback()
                        print(f"   ❌ Error: {e}")
                        # Continuar con las demás columnas
            else:
                print(f"\n✅ Todas las columnas existen!")

            # Mostrar columnas actuales
            print(f"\n📋 Columnas actuales en {table_name}:")
            actual_columns = {col['name']: col for col in inspector.get_columns(table_name)}
            for col_name in sorted(actual_columns.keys()):
                status = "✓" if col_name in expected_columns else "?"
                print(f"   {status} {col_name}")

        print("\n" + "=" * 80)
        print("SINCRONIZACIÓN COMPLETADA")
        print("=" * 80)

if __name__ == '__main__':
    try:
        sync_schema()
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
