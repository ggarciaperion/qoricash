#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Verificar operaciones de un cliente específico
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
print(f"VERIFICANDO OPERACIONES DEL CLIENTE {CLIENT_DNI}")
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
            print(f"\nCliente {CLIENT_DNI} no encontrado en la base de datos")
            sys.exit(0)

        print(f"\nCliente encontrado:")
        print(f"  ID: {client[0]}")
        print(f"  DNI: {client[1]}")
        print(f"  Nombre: {client[2] or client[3] or 'N/A'}")

        # Buscar operaciones del cliente
        result = conn.execute(text("""
            SELECT id, operation_id, status, operation_type, created_at
            FROM operations
            WHERE client_id = :client_id
            ORDER BY created_at DESC
        """), {'client_id': client[0]})

        operations = result.fetchall()

        print(f"\nTotal de operaciones: {len(operations)}")

        if operations:
            print("\nOperaciones encontradas:")
            for op in operations:
                print(f"  - ID: {op[0]} | {op[1]} | {op[2]} | {op[3]} | {op[4]}")

            print(f"\nPara eliminar estas operaciones, ejecuta:")
            print(f"python delete_client_operations.py")
        else:
            print("\nEl cliente NO tiene operaciones en el servidor")

except Exception as e:
    print(f"\nERROR: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
