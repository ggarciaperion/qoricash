#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Eliminar TODAS las operaciones de un cliente específico
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

CLIENT_DNI = '12366666'

print("=" * 60)
print(f"ELIMINAR OPERACIONES DEL CLIENTE {CLIENT_DNI}")
print("=" * 60)

engine = create_engine(DATABASE_URL)

try:
    with engine.connect() as conn:
        # Buscar cliente
        result = conn.execute(text("""
            SELECT id, dni, full_name, razon_social
            FROM clients
            WHERE dni = :dni
        """), {'dni': CLIENT_DNI})

        client = result.fetchone()

        if not client:
            print(f"\nCliente {CLIENT_DNI} no encontrado")
            sys.exit(0)

        client_id = client[0]
        client_name = client[2] or client[3] or 'N/A'

        print(f"\nCliente: {client_name} (DNI: {CLIENT_DNI})")

        # Contar operaciones
        result = conn.execute(text("""
            SELECT COUNT(*) FROM operations WHERE client_id = :client_id
        """), {'client_id': client_id})

        count = result.scalar()

        if count == 0:
            print("\nEl cliente NO tiene operaciones para eliminar")
            sys.exit(0)

        # Listar operaciones
        result = conn.execute(text("""
            SELECT id, operation_id, status, operation_type, created_at
            FROM operations
            WHERE client_id = :client_id
            ORDER BY created_at DESC
        """), {'client_id': client_id})

        operations = result.fetchall()

        print(f"\nOperaciones a eliminar ({count}):")
        for op in operations:
            print(f"  - {op[1]} | {op[2]} | {op[3]} | {op[4]}")

        # Confirmación
        print(f"\nADVERTENCIA: Se eliminaran {count} operaciones del cliente {client_name}")
        confirm = input("\nContinuar? (escribe 'SI' para confirmar): ")

        if confirm != 'SI':
            print("Cancelado")
            sys.exit(0)

        # Eliminar operaciones
        print("\nEliminando operaciones...")
        result = conn.execute(text("""
            DELETE FROM operations WHERE client_id = :client_id
        """), {'client_id': client_id})
        conn.commit()

        deleted = result.rowcount
        print(f"Eliminadas: {deleted} operaciones")

        # Verificar
        result = conn.execute(text("""
            SELECT COUNT(*) FROM operations WHERE client_id = :client_id
        """), {'client_id': client_id})

        remaining = result.scalar()

        if remaining == 0:
            print(f"\nCliente {CLIENT_DNI} limpio! Sin operaciones en el servidor")
        else:
            print(f"\nAdvertencia: Aun quedan {remaining} operaciones")

        print("\n" + "=" * 60)
        print("COMPLETADO")
        print("=" * 60)

except Exception as e:
    print(f"\nERROR: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
