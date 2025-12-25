#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Encontrar clientes SIN operaciones activas (Pendiente o En proceso)
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

print("=" * 80)
print("BUSCANDO CLIENTES DISPONIBLES (sin operaciones Pendiente/En proceso)")
print("=" * 80)

engine = create_engine(DATABASE_URL)

try:
    with engine.connect() as conn:
        # Obtener TODOS los clientes activos
        result = conn.execute(text("""
            SELECT id, dni, nombres, apellido_paterno, apellido_materno, razon_social, status
            FROM clients
            WHERE status = 'Activo'
            ORDER BY created_at DESC
        """))

        all_clients = result.fetchall()
        print(f"\nTotal de clientes activos: {len(all_clients)}")

        # Para cada cliente, verificar si tiene operaciones activas
        available_clients = []

        for client in all_clients:
            client_id = client[0]
            dni = client[1]

            # Construir nombre
            if client[5]:  # razon_social
                name = client[5]
            elif client[2]:  # nombres
                name = f"{client[2]} {client[3] or ''} {client[4] or ''}".strip()
            else:
                name = 'N/A'

            # Verificar operaciones activas (Pendiente o En proceso)
            result_ops = conn.execute(text("""
                SELECT COUNT(*)
                FROM operations
                WHERE client_id = :client_id
                AND status IN ('Pendiente', 'En proceso')
            """), {'client_id': client_id})

            active_ops_count = result_ops.scalar()

            if active_ops_count == 0:
                # Obtener la última operación del cliente
                result_last = conn.execute(text("""
                    SELECT operation_id, status, created_at
                    FROM operations
                    WHERE client_id = :client_id
                    ORDER BY created_at DESC
                    LIMIT 1
                """), {'client_id': client_id})

                last_op = result_last.fetchone()

                available_clients.append({
                    'dni': dni,
                    'name': name,
                    'last_operation': last_op[0] if last_op else 'Nunca',
                    'last_status': last_op[1] if last_op else 'N/A',
                    'last_date': str(last_op[2]) if last_op else 'N/A'
                })

        print(f"\n{'=' * 80}")
        print(f"CLIENTES DISPONIBLES: {len(available_clients)}")
        print(f"{'=' * 80}\n")

        if available_clients:
            print("DNI           | NOMBRE                           | ULTIMA OPERACION | ESTADO")
            print("-" * 80)
            for client in available_clients:
                print(f"{client['dni']:<13} | {client['name']:<32} | {client['last_operation']:<16} | {client['last_status']}")

            print(f"\n{'=' * 80}")
            print("PUEDES USAR CUALQUIERA DE ESTOS DNI PARA HACER LOGIN")
            print(f"{'=' * 80}\n")

            # Mostrar los 3 primeros como sugerencia
            print("SUGERENCIAS (primeros 3):")
            for i, client in enumerate(available_clients[:3], 1):
                print(f"  {i}. DNI: {client['dni']} - {client['name']}")
        else:
            print("\nNO HAY CLIENTES DISPONIBLES")
            print("Todos los clientes tienen operaciones activas (Pendiente o En proceso)")

            # Mostrar clientes con operaciones activas
            print(f"\n{'=' * 80}")
            print("CLIENTES CON OPERACIONES ACTIVAS:")
            print(f"{'=' * 80}\n")

            for client in all_clients:
                client_id = client[0]
                dni = client[1]

                if client[5]:
                    name = client[5]
                elif client[2]:
                    name = f"{client[2]} {client[3] or ''} {client[4] or ''}".strip()
                else:
                    name = 'N/A'

                result_ops = conn.execute(text("""
                    SELECT operation_id, status, created_at
                    FROM operations
                    WHERE client_id = :client_id
                    AND status IN ('Pendiente', 'En proceso')
                    ORDER BY created_at DESC
                """), {'client_id': client_id})

                active_ops = result_ops.fetchall()

                if active_ops:
                    print(f"\nDNI: {dni} - {name}")
                    for op in active_ops:
                        print(f"  - {op[0]} | {op[1]} | {op[2]}")

except Exception as e:
    print(f"\nERROR: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
