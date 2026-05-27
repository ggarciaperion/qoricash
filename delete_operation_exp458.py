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

    def safe_exec(sql, params=None):
        """Ejecuta SQL usando savepoint — ignora tablas que no existen."""
        try:
            db.session.execute(text("SAVEPOINT sp"))
            r = db.session.execute(text(sql), params or {})
            db.session.execute(text("RELEASE SAVEPOINT sp"))
            return r.rowcount
        except Exception as e:
            db.session.execute(text("ROLLBACK TO SAVEPOINT sp"))
            if 'does not exist' in str(e):
                return -1  # tabla no existe, ok
            raise

    print(f"\nEliminando registros hijos...")

    tables = [
        ("compliance_sar",          "DELETE FROM compliance_sar WHERE operation_id = :id"),
        ("compliance_review_queue", "DELETE FROM compliance_review_queue WHERE operation_id = :id"),
        ("compliance_alerts",       "DELETE FROM compliance_alerts WHERE operation_id = :id"),
        ("invoices",                "DELETE FROM invoices WHERE operation_id = :id"),
    ]
    for name, sql in tables:
        n = safe_exec(sql, {'id': op_id})
        print(f"  {name:<28}: {'(tabla no existe)' if n == -1 else str(n) + ' fila(s)'}")

    n = safe_exec(
        "DELETE FROM accounting_matches WHERE buy_operation_id = :id OR sell_operation_id = :id",
        {'id': op_id}
    )
    print(f"  {'accounting_matches':<28}: {'(tabla no existe)' if n == -1 else str(n) + ' fila(s)'}")

    n = safe_exec(
        "UPDATE reward_codes SET used_in_operation_id = NULL WHERE used_in_operation_id = :id",
        {'id': op_id}
    )
    print(f"  {'reward_codes (clear FK)':<28}: {'(tabla no existe)' if n == -1 else str(n) + ' fila(s)'}")

    # La operación (debe ir al final)
    n = safe_exec("DELETE FROM operations WHERE id = :id", {'id': op_id})
    print(f"  {'operations':<28}: {n} fila(s)")

    db.session.commit()
    print(f"\n✓ Operacion {TARGET_OP} eliminada correctamente.")
