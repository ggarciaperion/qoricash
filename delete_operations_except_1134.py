#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para eliminar todas las operaciones excepto EXP-1134
"""
import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Obtener URL de la base de datos
DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    print("❌ ERROR: No se encontró DATABASE_URL en el archivo .env")
    sys.exit(1)

print("🔗 Conectando a la base de datos...")
engine = create_engine(DATABASE_URL)

try:
    with engine.connect() as conn:
        # Primero, ver cuántas operaciones hay
        result = conn.execute(text("SELECT COUNT(*) FROM operations"))
        total = result.scalar()
        print(f"📊 Total de operaciones antes de eliminar: {total}")

        # Ver las operaciones que se eliminarán
        result = conn.execute(text("""
            SELECT operation_id, status, created_at
            FROM operations
            WHERE operation_id != 'EXP-1134'
            ORDER BY created_at DESC
        """))
        operations_to_delete = result.fetchall()

        print(f"\n🗑️  Se eliminarán {len(operations_to_delete)} operaciones:")
        for op in operations_to_delete:
            print(f"   - {op[0]} (Estado: {op[1]}, Creada: {op[2]})")

        # Confirmar
        print(f"\n⚠️  ADVERTENCIA: Se mantendrá SOLO la operación EXP-1134")
        confirm = input("¿Deseas continuar? (escribe 'SI' para confirmar): ")

        if confirm.upper() != 'SI':
            print("❌ Operación cancelada")
            sys.exit(0)

        # Eliminar operaciones excepto EXP-1134
        print("\n🗑️  Eliminando operaciones...")
        result = conn.execute(text("""
            DELETE FROM operations
            WHERE operation_id != 'EXP-1134'
        """))
        conn.commit()

        deleted_count = result.rowcount
        print(f"✅ Se eliminaron {deleted_count} operaciones exitosamente")

        # Verificar operaciones restantes
        result = conn.execute(text("SELECT COUNT(*) FROM operations"))
        remaining = result.scalar()
        print(f"📊 Operaciones restantes: {remaining}")

        # Mostrar la operación que quedó
        result = conn.execute(text("""
            SELECT operation_id, status, amount_usd, exchange_rate, created_at
            FROM operations
            WHERE operation_id = 'EXP-1134'
        """))
        remaining_op = result.fetchone()

        if remaining_op:
            print(f"\n✅ Operación conservada:")
            print(f"   ID: {remaining_op[0]}")
            print(f"   Estado: {remaining_op[1]}")
            print(f"   Monto USD: ${remaining_op[2]}")
            print(f"   Tipo de cambio: {remaining_op[3]}")
            print(f"   Creada: {remaining_op[4]}")
        else:
            print("\n⚠️  ADVERTENCIA: No se encontró la operación EXP-1134")

        print("\n✅ Proceso completado")

except Exception as e:
    print(f"❌ ERROR: {str(e)}")
    sys.exit(1)
