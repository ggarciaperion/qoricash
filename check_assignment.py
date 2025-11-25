"""
Script para verificar asignaciones de operadores
"""
import os
from dotenv import load_dotenv
load_dotenv()

import psycopg2

database_url = os.environ.get('DATABASE_URL')

try:
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()

    # Verificar operaciones en proceso
    cursor.execute("""
        SELECT
            o.operation_id,
            o.status,
            o.assigned_operator_id,
            u.username as assigned_to
        FROM operations o
        LEFT JOIN users u ON u.id = o.assigned_operator_id
        WHERE o.status = 'En proceso'
        ORDER BY o.created_at DESC
        LIMIT 10
    """)

    print("OPERACIONES EN PROCESO:")
    print("-" * 80)
    for row in cursor.fetchall():
        print(f"ID: {row[0]}, Estado: {row[1]}, Operador ID: {row[2]}, Asignado a: {row[3] or 'NO ASIGNADO'}")

    print("\n" + "=" * 80 + "\n")

    # Verificar operadores activos
    cursor.execute("""
        SELECT id, username, role, status
        FROM users
        WHERE role = 'Operador'
    """)

    print("OPERADORES REGISTRADOS:")
    print("-" * 80)
    for row in cursor.fetchall():
        print(f"ID: {row[0]}, Usuario: {row[1]}, Rol: {row[2]}, Estado: {row[3]}")

    cursor.close()
    conn.close()

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
