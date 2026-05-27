"""
Script de uso único: eliminar operación EXP-458 (VILCHEZ OSORIO POUL).
Ejecutar desde Render Shell:
    python3 delete_operation_exp458.py
"""
import os, sys
os.environ.setdefault('FLASK_ENV', 'production')

from app import create_app
from app.extensions import db
from sqlalchemy import text

app = create_app()

TARGET_OP = 'EXP-458'
TARGET_CLIENT = 'VILCHEZ OSORIO POUL'

with app.app_context():
    row = db.session.execute(
        text("SELECT o.id, o.operation_id, o.status, "
             "COALESCE(c.apellido_paterno,'') || ' ' || COALESCE(c.apellido_materno,'') || ' ' || COALESCE(c.nombres,'') AS nombre "
             "FROM operations o JOIN clients c ON c.id = o.client_id "
             "WHERE o.operation_id = :oid"),
        {'oid': TARGET_OP}
    ).fetchone()

    if not row:
        print(f"ERROR: No se encontró la operación {TARGET_OP}.")
        sys.exit(1)

    op_id, op_code, status, full_name = row
    full_name = full_name.strip()
    print(f"\nOperación encontrada:")
    print(f"  ID interno : {op_id}")
    print(f"  Código     : {op_code}")
    print(f"  Estado     : {status}")
    print(f"  Cliente    : {full_name}")

    if TARGET_CLIENT.upper() not in full_name.upper():
        print(f"\nERROR: El cliente '{full_name}' no coincide con '{TARGET_CLIENT}'. Abortando.")
        sys.exit(1)

    print(f"\nEliminando registros hijos...")

    # 1. Compliance SAR
    r = db.session.execute(text("DELETE FROM compliance_sar WHERE operation_id = :id"), {'id': op_id})
    print(f"  compliance_sar          : {r.rowcount} fila(s)")

    # 2. Compliance review queue
    r = db.session.execute(text("DELETE FROM compliance_review_queue WHERE operation_id = :id"), {'id': op_id})
    print(f"  compliance_review_queue : {r.rowcount} fila(s)")

    # 3. Compliance alerts
    r = db.session.execute(text("DELETE FROM compliance_alerts WHERE operation_id = :id"), {'id': op_id})
    print(f"  compliance_alerts       : {r.rowcount} fila(s)")

    # 4. Accounting matches (buy o sell)
    r = db.session.execute(
        text("DELETE FROM accounting_matches WHERE buy_operation_id = :id OR sell_operation_id = :id"),
        {'id': op_id}
    )
    print(f"  accounting_matches      : {r.rowcount} fila(s)")

    # 5. Reward codes que usaron esta operación (solo limpiar referencia)
    r = db.session.execute(
        text("UPDATE reward_codes SET used_in_operation_id = NULL WHERE used_in_operation_id = :id"),
        {'id': op_id}
    )
    print(f"  reward_codes (clear FK) : {r.rowcount} fila(s)")

    # 6. Invoices
    r = db.session.execute(text("DELETE FROM invoices WHERE operation_id = :id"), {'id': op_id})
    print(f"  invoices                : {r.rowcount} fila(s)")

    # 7. La operación
    r = db.session.execute(text("DELETE FROM operations WHERE id = :id"), {'id': op_id})
    print(f"  operations              : {r.rowcount} fila(s)")

    db.session.commit()
    print(f"\n✓ Operacion {TARGET_OP} eliminada correctamente.")
