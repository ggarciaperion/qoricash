"""
Elimina la operación de prueba EXP-409 y todos sus registros relacionados.

Uso (en Render Shell):
    python3 delete_exp409.py
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

OPERATION_ID = 'EXP-409'

with engine.begin() as conn:

    # 1. Verificar que existe
    row = conn.execute(text(
        "SELECT id, operation_id, status, amount_usd, amount_pen FROM operations WHERE operation_id = :oid"
    ), {'oid': OPERATION_ID}).fetchone()

    if not row:
        print(f"ERROR: No se encontró la operación {OPERATION_ID}")
        sys.exit(1)

    op_db_id = row[0]
    print(f"Operación encontrada → id={op_db_id}  código={row[1]}  estado={row[2]}  USD={row[3]}  PEN={row[4]}")
    print()

    # 2. Eliminar registros dependientes en orden correcto

    deleted = conn.execute(text(
        "DELETE FROM compliance_alerts WHERE operation_id = :id"
    ), {'id': op_db_id}).rowcount
    print(f"  compliance_alerts eliminados:       {deleted}")

    deleted = conn.execute(text(
        "DELETE FROM transaction_monitoring WHERE operation_id = :id"
    ), {'id': op_db_id}).rowcount
    print(f"  transaction_monitoring eliminados:  {deleted}")

    deleted = conn.execute(text(
        "DELETE FROM compliance_documents WHERE operation_id = :id"
    ), {'id': op_db_id}).rowcount
    print(f"  compliance_documents eliminados:    {deleted}")

    deleted = conn.execute(text(
        "DELETE FROM invoices WHERE operation_id = :id"
    ), {'id': op_db_id}).rowcount
    print(f"  invoices eliminados:                {deleted}")

    deleted = conn.execute(text(
        "DELETE FROM accounting_matches WHERE buy_operation_id = :id OR sell_operation_id = :id"
    ), {'id': op_db_id}).rowcount
    print(f"  accounting_matches eliminados:      {deleted}")

    deleted = conn.execute(text(
        "DELETE FROM reward_codes WHERE used_in_operation_id = :id"
    ), {'id': op_db_id}).rowcount
    print(f"  reward_codes limpiados:             {deleted}")

    # 3. Eliminar la operación
    deleted = conn.execute(text(
        "DELETE FROM operations WHERE id = :id"
    ), {'id': op_db_id}).rowcount
    print(f"\n  Operación {OPERATION_ID} eliminada:  {deleted} fila(s)")

print("\nListo. EXP-409 eliminada correctamente.")
