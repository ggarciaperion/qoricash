#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Eliminar todas las operaciones del cliente 12366666 via API
"""
import requests
import json

API_BASE_URL = 'https://app.qoricash.pe'
CLIENT_DNI = '12366666'

print("=" * 60)
print(f"ELIMINANDO OPERACIONES DEL CLIENTE {CLIENT_DNI} VIA API")
print("=" * 60)

# Paso 1: Obtener operaciones del cliente
print(f"\nObteniendo operaciones del cliente {CLIENT_DNI}...")
response = requests.get(f"{API_BASE_URL}/api/client/my-operations/{CLIENT_DNI}")

if response.status_code != 200:
    print(f"ERROR: No se pudieron obtener las operaciones ({response.status_code})")
    print(response.text)
    exit(1)

data = response.json()
operations = data.get('operations', [])

print(f"\nTotal de operaciones encontradas: {len(operations)}")

if len(operations) == 0:
    print("\nNo hay operaciones para eliminar")
    exit(0)

# Mostrar operaciones
print("\nOperaciones a eliminar:")
for op in operations:
    print(f"  - {op['operation_id']} | {op['status']} | {op['operation_type']} | {op['created_at']}")

# Confirmación
print(f"\nADVERTENCIA: Se eliminaran {len(operations)} operaciones")
confirm = input("\nContinuar? (escribe 'SI' para confirmar): ")

if confirm != 'SI':
    print("Cancelado")
    exit(0)

# Eliminar operaciones
print("\nEliminando operaciones...")
deleted_count = 0
error_count = 0

for op in operations:
    operation_id = op['id']
    operation_code = op['operation_id']

    try:
        # Usar endpoint de cancelación con motivo
        cancel_data = {
            'cancellation_reason': 'Limpieza de datos de prueba - Cliente 12366666'
        }

        response = requests.post(
            f"{API_BASE_URL}/api/client/cancel-operation/{operation_id}",
            json=cancel_data,
            headers={'Content-Type': 'application/json'}
        )

        if response.status_code == 200:
            print(f"  OK: {operation_code} cancelada")
            deleted_count += 1
        else:
            print(f"  ERROR: {operation_code} - {response.status_code}: {response.text[:100]}")
            error_count += 1
    except Exception as e:
        print(f"  ERROR: {operation_code} - {str(e)}")
        error_count += 1

print("\n" + "=" * 60)
print(f"RESUMEN:")
print(f"  Operaciones canceladas: {deleted_count}")
print(f"  Errores: {error_count}")
print("=" * 60)

# Verificar
print("\nVerificando operaciones restantes...")
response = requests.get(f"{API_BASE_URL}/api/client/my-operations/{CLIENT_DNI}")
if response.status_code == 200:
    data = response.json()
    remaining_ops = data.get('operations', [])
    # Contar solo operaciones no canceladas
    active_ops = [op for op in remaining_ops if op['status'] not in ['Cancelada', 'Cancelado']]
    print(f"Operaciones activas restantes: {len(active_ops)}")

    if len(active_ops) == 0:
        print("\nCLIENTE LIMPIO: Todas las operaciones han sido canceladas")
    else:
        print(f"\nAdvertencia: Aun quedan {len(active_ops)} operaciones activas")
        for op in active_ops:
            print(f"  - {op['operation_id']} | {op['status']}")
