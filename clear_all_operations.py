#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para eliminar TODAS las operaciones de la base de datos
Incluye EXP-1134 y cualquier otra operación
"""
import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    print("ERROR: No se encontro DATABASE_URL")
    sys.exit(1)

print("=" * 60)
print("ELIMINAR TODAS LAS OPERACIONES - INICIO DESDE CERO")
print("=" * 60)

engine = create_engine(DATABASE_URL)

try:
    with engine.connect() as conn:
        # Mostrar operaciones actuales
        result = conn.execute(text("SELECT COUNT(*) FROM operations"))
        total = result.scalar()
        print(f"\nTotal de operaciones actuales: {total}")

        if total == 0:
            print("No hay operaciones para eliminar")
            sys.exit(0)

        # Listar todas las operaciones
        result = conn.execute(text("""
            SELECT operation_id, status, operation_type, created_at
            FROM operations
            ORDER BY created_at DESC
        """))
        ops = result.fetchall()

        print(f"\nOperaciones a eliminar:")
        for op in ops:
            print(f"   - {op[0]} | {op[1]} | {op[2]} | {op[3]}")

        # Confirmación
        print(f"\nADVERTENCIA: Se eliminarán TODAS las {total} operaciones")
        print("ADVERTENCIA: Esto incluye EXP-1134 y cualquier otra operación")
        print("ADVERTENCIA: Esta acción NO SE PUEDE DESHACER")

        confirm = input("\nContinuar? (escribe 'ELIMINAR TODO' para confirmar): ")

        if confirm != 'ELIMINAR TODO':
            print("Cancelado por el usuario")
            sys.exit(0)

        # Eliminar todas las operaciones
        print("\nEliminando todas las operaciones...")
        result = conn.execute(text("DELETE FROM operations"))
        conn.commit()

        deleted_count = result.rowcount
        print(f"Eliminadas: {deleted_count} operaciones")

        # Verificar que la tabla esté vacía
        result = conn.execute(text("SELECT COUNT(*) FROM operations"))
        remaining = result.scalar()
        print(f"Operaciones restantes: {remaining}")

        if remaining == 0:
            print("\nBase de datos limpia! Lista para pruebas desde cero")
        else:
            print(f"\nAdvertencia: Aún quedan {remaining} operaciones")

        print("\n" + "=" * 60)
        print("COMPLETADO")
        print("=" * 60)

except Exception as e:
    print(f"\nERROR: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
