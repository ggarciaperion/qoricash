#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Limpiar TODAS las operaciones del cliente 12366666
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
print(f"LIMPIANDO CLIENTE {CLIENT_DNI}")
print("=" * 60)

engine = create_engine(DATABASE_URL)

try:
    with engine.connect() as conn:
        # Buscar cliente
        result = conn.execute(text("""
            SELECT id, dni, nombres, apellido_paterno, apellido_materno, razon_social
            FROM clients
            WHERE dni = :dni
        """), {'dni': CLIENT_DNI})

        client = result.fetchone()

        if not client:
            print(f"\nCliente {CLIENT_DNI} NO encontrado en la base de datos")
            print("No hay nada que limpiar")
            sys.exit(0)

        client_id = client[0]

        # Construir nombre
        if client[5]:  # razon_social
            client_name = client[5]
        elif client[2]:  # nombres
            client_name = f"{client[2]} {client[3] or ''} {client[4] or ''}".strip()
        else:
            client_name = 'N/A'

        print(f"\nCliente encontrado:")
        print(f"  ID: {client_id}")
        print(f"  DNI: {CLIENT_DNI}")
        print(f"  Nombre: {client_name}")

        # Contar operaciones
        result = conn.execute(text("""
            SELECT COUNT(*) FROM operations WHERE client_id = :client_id
        """), {'client_id': client_id})

        count = result.scalar()

        print(f"\nTotal de operaciones: {count}")

        if count == 0:
            print("\nEl cliente NO tiene operaciones en el servidor")
            print("Solo necesitas limpiar el cache de la app")
            sys.exit(0)

        # Listar operaciones
        result = conn.execute(text("""
            SELECT id, operation_id, status, operation_type, created_at
            FROM operations
            WHERE client_id = :client_id
            ORDER BY created_at DESC
        """), {'client_id': client_id})

        operations = result.fetchall()

        print("\nOperaciones a eliminar:")
        for op in operations:
            print(f"  - {op[1]} | {op[2]} | {op[3]} | {op[4]}")

        # Confirmación
        print(f"\nADVERTENCIA: Se eliminaran {count} operaciones")
        confirm = input("\nContinuar? (escribe 'SI' para confirmar): ")

        if confirm != 'SI':
            print("Cancelado")
            sys.exit(0)

        # Eliminar operaciones
        print("\nEliminando operaciones del servidor...")
        result = conn.execute(text("""
            DELETE FROM operations WHERE client_id = :client_id
        """), {'client_id': client_id})
        conn.commit()

        deleted = result.rowcount
        print(f"Eliminadas: {deleted} operaciones del servidor")

        # Verificar
        result = conn.execute(text("""
            SELECT COUNT(*) FROM operations WHERE client_id = :client_id
        """), {'client_id': client_id})

        remaining = result.scalar()

        if remaining == 0:
            print(f"\nSERVIDOR LIMPIO: Cliente {CLIENT_DNI} sin operaciones")
            print("\nAhora limpia el cache de la app:")
            print("1. Cierra la app completamente")
            print("2. En el dispositivo: Configuracion > Apps > QoriCash > Borrar datos")
            print("3. O desinstala y reinstala la app")
        else:
            print(f"\nAdvertencia: Aun quedan {remaining} operaciones")

        print("\n" + "=" * 60)
        print("COMPLETADO - SERVIDOR LIMPIO")
        print("=" * 60)

except Exception as e:
    print(f"\nERROR: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
