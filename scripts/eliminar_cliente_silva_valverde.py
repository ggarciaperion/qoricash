"""
eliminar_cliente_silva_valverde.py
Elimina PERMANENTEMENTE de la BD a la cliente de prueba
"SILVA VALVERDE MARIA ELENA" y todas sus registros asociados.

Uso:
    # Ver qué se va a borrar (sin tocar la BD):
    DATABASE_URL="postgresql://..." python3 scripts/eliminar_cliente_silva_valverde.py

    # Ejecutar la eliminación real:
    DATABASE_URL="postgresql://..." python3 scripts/eliminar_cliente_silva_valverde.py --confirmar
"""
import sys
import os
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ.get("DATABASE_URL", "").replace("postgres://", "postgresql://", 1)
NOMBRE_BUSCAR = "silva valverde"
DRY_RUN = "--confirmar" not in sys.argv


def main():
    if not DATABASE_URL or DATABASE_URL.startswith("sqlite"):
        print("❌ Configura DATABASE_URL con la URL de producción de Render.")
        print("   Ejemplo:")
        print("   DATABASE_URL='postgresql://user:pass@host/db' python3 scripts/eliminar_cliente_silva_valverde.py")
        sys.exit(1)

    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=RealDictCursor)

    print("=" * 65)
    print("  ELIMINAR CLIENTE DE PRUEBA — QoriCash")
    print("=" * 65)
    print(f"  Modo: {'DRY-RUN (solo lectura — nada se borra)' if DRY_RUN else '⚠️  ELIMINACIÓN REAL'}")
    print()

    # ── Buscar cliente ─────────────────────────────────────────────────
    cur.execute("""
        SELECT id, nombres, apellidos, dni, email, created_at
        FROM clients
        WHERE LOWER(COALESCE(nombres,'') || ' ' || COALESCE(apellidos,'')) LIKE %s
           OR LOWER(COALESCE(apellidos,'') || ' ' || COALESCE(nombres,'')) LIKE %s
        ORDER BY id
    """, (f"%{NOMBRE_BUSCAR}%", f"%{NOMBRE_BUSCAR}%"))
    rows = cur.fetchall()

    if not rows:
        print(f"  ❌ No se encontró ningún cliente con '{NOMBRE_BUSCAR}'")
        conn.close()
        return

    print(f"  Cliente(s) encontrado(s): {len(rows)}")
    for r in rows:
        print(f"    ID={r['id']}  |  {r['apellidos']} {r['nombres']}  |  DNI:{r['dni']}  |  {r['email']}  |  {r['created_at']}")

    client_ids = [r['id'] for r in rows]
    ids_tuple = tuple(client_ids)
    print()

    # ── Contar registros relacionados ──────────────────────────────────
    def count(table, col="client_id"):
        cur.execute(f"SELECT COUNT(*) AS n FROM {table} WHERE {col} = ANY(%s)", (client_ids,))
        return cur.fetchone()['n']

    def count_custom(sql, params):
        cur.execute(sql, params)
        return cur.fetchone()['n']

    print("  Registros que se eliminarán:")
    counts = {
        "operations"             : count("operations"),
        "invoices"               : count("invoices"),
        "client_risk_profiles"   : count("client_risk_profiles"),
        "compliance_alerts"      : count("compliance_alerts"),
        "transaction_monitoring" : count("transaction_monitoring"),
        "restrictive_list_checks": count("restrictive_list_checks"),
        "compliance_documents"   : count("compliance_documents"),
        "reward_codes"           : count("reward_codes"),
        "complaints"             : count("complaints"),
        "audit_logs (Client)"    : count_custom(
            "SELECT COUNT(*) AS n FROM audit_logs WHERE entity='Client' AND entity_id = ANY(%s)",
            (client_ids,)
        ),
        "clients"                : len(client_ids),
    }
    for tabla, n in counts.items():
        marca = "✅" if n == 0 else "🗑️ "
        print(f"    {marca} {tabla:<30}: {n}")
    print()

    if DRY_RUN:
        print("  ℹ️  DRY-RUN completado — nada fue eliminado.")
        print()
        print("  Para ejecutar la eliminación real:")
        print(f"  DATABASE_URL='...' python3 scripts/eliminar_cliente_silva_valverde.py --confirmar")
        conn.close()
        return

    # ── CONFIRMACIÓN EXTRA ─────────────────────────────────────────────
    print("  ⚠️  ¿Confirmar eliminación permanente? [escribir 'SI' para continuar]: ", end="")
    respuesta = input().strip().upper()
    if respuesta != "SI":
        print("  Cancelado.")
        conn.close()
        return

    # ── ELIMINACIÓN EN ORDEN (respetar FK constraints) ─────────────────
    print()
    print("  Eliminando...")

    steps = [
        ("audit_logs (Client)",     "DELETE FROM audit_logs WHERE entity='Client' AND entity_id = ANY(%s)"),
        ("compliance_documents",    "DELETE FROM compliance_documents WHERE client_id = ANY(%s)"),
        ("transaction_monitoring",  "DELETE FROM transaction_monitoring WHERE client_id = ANY(%s)"),
        ("restrictive_list_checks", "DELETE FROM restrictive_list_checks WHERE client_id = ANY(%s)"),
        ("compliance_alerts",       "DELETE FROM compliance_alerts WHERE client_id = ANY(%s)"),
        ("client_risk_profiles",    "DELETE FROM client_risk_profiles WHERE client_id = ANY(%s)"),
        ("reward_codes",            "DELETE FROM reward_codes WHERE client_id = ANY(%s)"),
        ("invoices",                "DELETE FROM invoices WHERE client_id = ANY(%s)"),
        ("complaints",              "DELETE FROM complaints WHERE client_id = ANY(%s)"),
        ("operations",              "DELETE FROM operations WHERE client_id = ANY(%s)"),
        ("clients",                 "DELETE FROM clients WHERE id = ANY(%s)"),
    ]

    try:
        for label, sql in steps:
            cur.execute(sql, (client_ids,))
            print(f"    ✅ {label:<30}: {cur.rowcount} fila(s) eliminada(s)")

        conn.commit()
        print()
        print("  ✅ ELIMINACIÓN COMPLETADA Y CONFIRMADA EN BD.")

    except Exception as e:
        conn.rollback()
        print(f"\n  ❌ ERROR — rollback ejecutado: {e}")

    finally:
        conn.close()

    print("=" * 65)


if __name__ == "__main__":
    main()
