#!/usr/bin/env python
"""
Script para verificar si la tabla invoices existe en la base de datos
Ejecutar: python check_invoices_table.py
"""
from run import app
from app.extensions import db
from sqlalchemy import inspect

def check_invoices_table():
    """Verificar si la tabla invoices existe"""
    with app.app_context():
        try:
            print("=" * 60)
            print("VERIFICANDO TABLA INVOICES EN BASE DE DATOS")
            print("=" * 60)

            # Obtener inspector de la base de datos
            inspector = inspect(db.engine)

            # Obtener lista de todas las tablas
            tables = inspector.get_table_names()

            # Verificar si invoices existe
            invoices_exists = 'invoices' in tables

            print(f"\n✓ Total de tablas en la BD: {len(tables)}")
            print(f"\n✓ Tabla 'invoices' existe: {invoices_exists}")

            if invoices_exists:
                print("\n✅ LA TABLA INVOICES EXISTE CORRECTAMENTE")

                # Mostrar columnas de la tabla invoices
                columns = inspector.get_columns('invoices')
                print(f"\n✓ Columnas en tabla invoices: {len(columns)}")
                for col in columns[:5]:  # Mostrar primeras 5 columnas
                    print(f"  - {col['name']}: {col['type']}")
                if len(columns) > 5:
                    print(f"  ... y {len(columns) - 5} columnas más")
            else:
                print("\n❌ LA TABLA INVOICES NO EXISTE")
                print("\nTablas disponibles:")
                for table in sorted(tables):
                    print(f"  - {table}")

            print("\n" + "=" * 60)
            return invoices_exists

        except Exception as e:
            print(f"\n❌ Error al verificar tabla: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    check_invoices_table()
