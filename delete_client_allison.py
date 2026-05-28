"""
Elimina el cliente COOK MARQUEZ ALLISON MARIA JOSEFINA (DNI 06631846)
incluyendo todas sus operaciones y registros relacionados.

Uso (en Render Shell):
    python3 delete_client_allison.py
"""
import os, sys

DATABASE_URL = os.environ.get('DATABASE_URL', '')
if not DATABASE_URL:
    print("ERROR: Define DATABASE_URL en el entorno")
    sys.exit(1)

if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

from sqlalchemy import create_engine, text

engine = create_engine(DATABASE_URL)

TARGET_DNI = '06631846'

with engine.begin() as conn:

    # Buscar el cliente
    client = conn.execute(text(
        "SELECT id, dni, nombres, apellido_paterno, apellido_materno, email, status FROM clients WHERE dni = :dni"
    ), {'dni': TARGET_DNI}).fetchone()

    if not client:
        print(f"No se encontró cliente con DNI {TARGET_DNI}")
        sys.exit(0)

    cid = client.id
    print(f"Cliente encontrado: id={cid} | {client.apellido_paterno} {client.apellido_materno} {client.nombres} | {client.email} | {client.status}")

    # Ver operaciones
    ops = conn.execute(text(
        "SELECT id, operation_id, status, amount_usd FROM operations WHERE client_id = :cid"
    ), {'cid': cid}).fetchall()
    print(f"\nOperaciones ({len(ops)}):")
    for op in ops:
        print(f"  {op.operation_id} | {op.status} | USD {op.amount_usd}")

    # Eliminar en orden para respetar FKs
    # 1. accounting_match (referencias a operations)
    op_ids = [op.id for op in ops]
    if op_ids:
        ids_str = ','.join(str(i) for i in op_ids)
        conn.execute(text(f"DELETE FROM accounting_matches WHERE buy_operation_id IN ({ids_str}) OR sell_operation_id IN ({ids_str})"))
        print(f"\n  → accounting_matches eliminados")

        conn.execute(text(f"DELETE FROM compliance_alerts WHERE operation_id IN ({ids_str})"))
        print(f"  → compliance_alerts de operaciones eliminados")

    # 2. compliance_alerts del cliente
    conn.execute(text("DELETE FROM compliance_alerts WHERE client_id = :cid"), {'cid': cid})
    print(f"  → compliance_alerts del cliente eliminados")

    # 3. restrictive_list_checks (NOT NULL client_id)
    conn.execute(text("DELETE FROM restrictive_list_checks WHERE client_id = :cid"), {'cid': cid})
    print(f"  → restrictive_list_checks eliminados")

    # 4. client_risk_profiles
    conn.execute(text("DELETE FROM client_risk_profiles WHERE client_id = :cid"), {'cid': cid})
    print(f"  → client_risk_profiles eliminados")

    # 5. invoices de las operaciones
    if op_ids:
        conn.execute(text(f"DELETE FROM invoices WHERE operation_id IN ({ids_str})"))
        print(f"  → invoices eliminados")

    # 7. operaciones
    conn.execute(text("DELETE FROM operations WHERE client_id = :cid"), {'cid': cid})
    print(f"  → operaciones eliminadas")

    # 8. cliente
    conn.execute(text("DELETE FROM clients WHERE id = :cid"), {'cid': cid})
    print(f"\n✅ Cliente id={cid} eliminado completamente.")

print("\n✅ Listo.")
