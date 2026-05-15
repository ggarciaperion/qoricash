"""
eliminar_demo_trader.py
Elimina PERMANENTEMENTE el usuario demo_trader y todos sus datos de prueba:
  - Sus operaciones
  - Sus clientes exclusivos (que no tienen operaciones de otros traders)
  - Sus prospectos, metas, ganancias diarias, notificaciones, audit_logs
  - El usuario en sí

Uso:
    # Ver qué se va a borrar (sin tocar la BD):
    DATABASE_URL="postgresql://..." python3 scripts/eliminar_demo_trader.py

    # Ejecutar la eliminación real:
    DATABASE_URL="postgresql://..." python3 scripts/eliminar_demo_trader.py --confirmar
"""
import sys
import os
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ.get("DATABASE_URL", "").replace("postgres://", "postgresql://", 1)
DRY_RUN = "--confirmar" not in sys.argv


def main():
    if not DATABASE_URL or DATABASE_URL.startswith("sqlite"):
        print("❌  Configura DATABASE_URL con la URL de producción de Render.")
        print("    Ejemplo:")
        print("    DATABASE_URL='postgresql://user:pass@host/db' python3 scripts/eliminar_demo_trader.py")
        sys.exit(1)

    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=RealDictCursor)

    sep = "=" * 65
    print(sep)
    print("  ELIMINAR DEMO_TRADER Y DATOS DE PRUEBA — QoriCash")
    print(sep)
    print(f"  Modo: {'DRY-RUN (solo lectura — nada se borra)' if DRY_RUN else '⚠️   ELIMINACIÓN REAL'}")
    print()

    # ── 1. Encontrar usuario demo_trader ───────────────────────────────
    cur.execute("""
        SELECT id, username, email, role, created_at
        FROM users
        WHERE LOWER(username) = 'demo_trader'
           OR LOWER(email) LIKE '%demo%'
        ORDER BY id
    """)
    users = cur.fetchall()

    if not users:
        print("  ❌  No se encontró ningún usuario con username='demo_trader' o email con 'demo'.")
        conn.close()
        return

    print(f"  Usuario(s) encontrado(s):")
    for u in users:
        print(f"    ID={u['id']}  |  {u['username']}  |  {u['email']}  |  rol={u['role']}  |  creado={u['created_at']}")
    print()

    user_ids = [u['id'] for u in users]

    # ── 2. Operaciones del demo_trader ─────────────────────────────────
    cur.execute("SELECT id, client_id FROM operations WHERE user_id = ANY(%s)", (user_ids,))
    ops = cur.fetchall()
    op_ids = [o['id'] for o in ops]
    client_ids_from_ops = list({o['client_id'] for o in ops})

    print(f"  Operaciones de demo_trader: {len(op_ids)}")

    # ── 3. Clientes EXCLUSIVOS (solo tienen ops de demo_trader) ────────
    exclusive_client_ids = []
    shared_client_ids = []

    if client_ids_from_ops:
        cur.execute("""
            SELECT client_id
            FROM operations
            WHERE client_id = ANY(%s)
              AND (user_id IS NULL OR user_id != ALL(%s))
            GROUP BY client_id
        """, (client_ids_from_ops, user_ids))
        shared_ids = {r['client_id'] for r in cur.fetchall()}

        for cid in client_ids_from_ops:
            if cid in shared_ids:
                shared_client_ids.append(cid)
            else:
                exclusive_client_ids.append(cid)

    print(f"  Clientes exclusivos (se borrarán): {len(exclusive_client_ids)}")
    if exclusive_client_ids:
        cur.execute("""
            SELECT id, full_name, dni, email FROM clients WHERE id = ANY(%s) ORDER BY id
        """, (exclusive_client_ids,))
        for c in cur.fetchall():
            print(f"    → ID={c['id']}  {c['full_name'] or '—'}  DNI:{c['dni']}  {c['email'] or ''}")

    if shared_client_ids:
        print(f"  Clientes compartidos (solo se borran sus ops de demo_trader, NO el cliente): {len(shared_client_ids)}")
        cur.execute("SELECT id, full_name FROM clients WHERE id = ANY(%s)", (shared_client_ids,))
        for c in cur.fetchall():
            print(f"    ⚠️   ID={c['id']}  {c['full_name']}")
    print()

    # ── 4. Conteo de registros relacionados ────────────────────────────
    def cnt(sql, params):
        cur.execute(sql, params)
        return cur.fetchone()['n']

    print("  Registros que se eliminarán:")

    items = {}

    # Por operaciones
    if op_ids:
        items["accounting_matches (ops)"] = cnt(
            "SELECT COUNT(*) AS n FROM accounting_matches WHERE buy_operation_id = ANY(%s) OR sell_operation_id = ANY(%s)",
            (op_ids, op_ids)
        )

    # Por clientes exclusivos
    if exclusive_client_ids:
        for table in ["compliance_documents", "transaction_monitoring",
                      "restrictive_list_checks", "compliance_alerts",
                      "client_risk_profiles", "reward_codes", "invoices", "complaints"]:
            try:
                items[table] = cnt(
                    f"SELECT COUNT(*) AS n FROM {table} WHERE client_id = ANY(%s)",
                    (exclusive_client_ids,)
                )
            except psycopg2.Error:
                conn.rollback()  # reset transaction after error
                items[table] = "tabla no existe"

    # Por usuario
    for table, col in [
        ("trader_daily_profits", "user_id"),
        ("trader_goals", "user_id"),
        ("notifications", "user_id"),
        ("prospectos", "user_id"),
    ]:
        try:
            items[f"{table} (usuario)"] = cnt(
                f"SELECT COUNT(*) AS n FROM {table} WHERE {col} = ANY(%s)",
                (user_ids,)
            )
        except psycopg2.Error:
            conn.rollback()
            items[f"{table} (usuario)"] = "tabla no existe"

    items["audit_logs (usuario)"] = cnt(
        "SELECT COUNT(*) AS n FROM audit_logs WHERE user_id = ANY(%s)", (user_ids,)
    )
    items[f"operations ({len(op_ids)})"] = len(op_ids)
    if exclusive_client_ids:
        items[f"clients exclusivos ({len(exclusive_client_ids)})"] = len(exclusive_client_ids)
    items[f"users (demo_trader)"] = len(user_ids)

    for label, n in items.items():
        marca = "✅" if n == 0 or n == "tabla no existe" else "🗑️ "
        print(f"    {marca} {label:<45}: {n}")
    print()

    if DRY_RUN:
        print("  ℹ️   DRY-RUN completado — nada fue eliminado.")
        print()
        print("  Para ejecutar la eliminación real:")
        print("  DATABASE_URL='...' python3 scripts/eliminar_demo_trader.py --confirmar")
        conn.close()
        return

    # ── 5. CONFIRMACIÓN ────────────────────────────────────────────────
    print("  ⚠️   ¿Confirmar eliminación permanente? [escribir 'SI' para continuar]: ", end="")
    respuesta = input().strip().upper()
    if respuesta != "SI":
        print("  Cancelado.")
        conn.close()
        return

    print()
    print("  Eliminando...")

    try:
        # Accounting matches referenciando las ops del demo_trader
        if op_ids:
            cur.execute("DELETE FROM accounting_matches WHERE buy_operation_id = ANY(%s) OR sell_operation_id = ANY(%s)", (op_ids, op_ids))
            print(f"    ✅ accounting_matches          : {cur.rowcount} fila(s)")

        # Tablas de clientes exclusivos
        if exclusive_client_ids:
            for table in ["compliance_documents", "transaction_monitoring",
                          "restrictive_list_checks", "compliance_alerts",
                          "client_risk_profiles", "reward_codes", "invoices", "complaints"]:
                try:
                    cur.execute(f"DELETE FROM {table} WHERE client_id = ANY(%s)", (exclusive_client_ids,))
                    print(f"    ✅ {table:<30}: {cur.rowcount} fila(s)")
                except psycopg2.Error as e:
                    conn.rollback()
                    print(f"    ⚠️   {table}: omitido ({e})")

            cur.execute("DELETE FROM audit_logs WHERE entity='Client' AND entity_id = ANY(%s)", (exclusive_client_ids,))
            print(f"    ✅ audit_logs (clientes)        : {cur.rowcount} fila(s)")

        # Operaciones (todas las del demo_trader, incluyendo clientes compartidos)
        cur.execute("DELETE FROM operations WHERE user_id = ANY(%s)", (user_ids,))
        print(f"    ✅ operations                  : {cur.rowcount} fila(s)")

        # Clientes exclusivos (sin operaciones ya)
        if exclusive_client_ids:
            cur.execute("DELETE FROM clients WHERE id = ANY(%s)", (exclusive_client_ids,))
            print(f"    ✅ clients (exclusivos)        : {cur.rowcount} fila(s)")

        # Tablas del usuario
        for table, col in [
            ("trader_daily_profits", "user_id"),
            ("trader_goals", "user_id"),
            ("notifications", "user_id"),
            ("prospectos", "user_id"),
        ]:
            try:
                cur.execute(f"DELETE FROM {table} WHERE {col} = ANY(%s)", (user_ids,))
                print(f"    ✅ {table:<30}: {cur.rowcount} fila(s)")
            except psycopg2.Error as e:
                conn.rollback()
                print(f"    ⚠️   {table}: omitido ({e})")

        cur.execute("DELETE FROM audit_logs WHERE user_id = ANY(%s)", (user_ids,))
        print(f"    ✅ audit_logs (usuario)        : {cur.rowcount} fila(s)")

        # Finalmente el usuario
        cur.execute("DELETE FROM users WHERE id = ANY(%s)", (user_ids,))
        print(f"    ✅ users                       : {cur.rowcount} fila(s)")

        conn.commit()
        print()
        print("  ✅  ELIMINACIÓN COMPLETADA Y CONFIRMADA EN BD.")

    except Exception as e:
        conn.rollback()
        print(f"\n  ❌  ERROR — rollback ejecutado: {e}")

    finally:
        conn.close()

    print(sep)


if __name__ == "__main__":
    main()
