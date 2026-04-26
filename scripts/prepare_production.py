"""
Script de Preparación para Producción — QoriCash
=================================================
Flujo:
  1. DRY-RUN: muestra resumen de todo lo que se eliminará (sin tocar nada)
  2. BACKUP:  genera volcado SQL completo de la base de datos (pg_dump)
  3. LIMPIEZA: elimina datos de prueba respetando FK constraints
  4. VERIFICACIÓN: confirma estado final del sistema

Ejecutar en Render Shell:
    python scripts/prepare_production.py

El script pide confirmación explícita ("SI") antes de eliminar.
"""

import os
import sys
import subprocess
from datetime import datetime

# ── Requiere entorno de producción ──────────────────────────────────────────
FLASK_ENV = os.environ.get("FLASK_ENV", "development")
DATABASE_URL = os.environ.get("DATABASE_URL", "")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL no está configurada.")
    sys.exit(1)

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    os.environ["DATABASE_URL"] = DATABASE_URL

# ── Bootstrap Flask app ──────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import create_app
from app.extensions import db

app = create_app()

# ────────────────────────────────────────────────────────────────────────────
# HELPERS
# ────────────────────────────────────────────────────────────────────────────

def sep(char="─", width=72):
    print(char * width)

def count(table):
    """Devuelve el número de filas de una tabla (0 si no existe)."""
    try:
        result = db.session.execute(db.text(f"SELECT COUNT(*) FROM {table}"))
        return result.scalar()
    except Exception:
        db.session.rollback()
        return None   # tabla no existe

def safe_delete(table, label, idx):
    """Elimina todos los registros de una tabla con SAVEPOINT."""
    try:
        db.session.execute(db.text(f"SAVEPOINT sp_{table}"))
        result = db.session.execute(db.text(f"DELETE FROM {table}"))
        db.session.execute(db.text(f"RELEASE SAVEPOINT sp_{table}"))
        n = result.rowcount
        print(f"  [{idx:02d}] {label:<40} {n:>6} eliminados")
        return n
    except Exception as e:
        db.session.execute(db.text(f"ROLLBACK TO SAVEPOINT sp_{table}"))
        if "does not exist" in str(e).lower():
            print(f"  [{idx:02d}] {label:<40}   N/A  (tabla no existe)")
            return 0
        print(f"  [{idx:02d}] {label:<40} ERROR: {e}")
        raise

# ────────────────────────────────────────────────────────────────────────────
# TABLAS EN ORDEN DE ELIMINACIÓN SEGURA (respeta FK)
# ────────────────────────────────────────────────────────────────────────────
TABLES = [
    # compliance
    ("compliance_documents",        "Compliance — documentos"),
    ("compliance_alerts",           "Compliance — alertas"),
    ("transaction_monitoring",      "Compliance — monitoreo transacciones"),
    ("restrictive_list_checks",     "Compliance — listas restrictivas"),
    ("client_risk_profiles",        "Perfiles de riesgo"),
    # contabilidad
    ("accounting_matches",          "Contabilidad — matches"),
    ("accounting_batches",          "Contabilidad — lotes"),
    ("journal_entry_lines",         "Contabilidad — líneas asiento"),
    ("journal_entries",             "Contabilidad — asientos"),
    # operaciones relacionadas
    ("invoices",                    "Facturas / boletas"),
    ("trader_daily_profits",        "Ganancias diarias trader"),
    ("audit_logs",                  "Audit logs"),
    ("reward_codes",                "Códigos de recompensa"),
    ("complaints",                  "Reclamos"),
    ("sanctions",                   "Sanciones"),
    # núcleo
    ("operations",                  "Operaciones de cambio"),
    ("clients",                     "Clientes"),
]

# Tablas que NO se tocan
PRESERVED = [
    "users", "bank_balances", "exchange_rates", "exchange_rate_history",
    "competitor_rates", "markets", "trader_goals", "system_config",
    "accounting_periods", "accounting_accounts", "journal_sequences",
    "risk_levels", "compliance_rules",
]

# ────────────────────────────────────────────────────────────────────────────
# PASO 1 — DRY-RUN
# ────────────────────────────────────────────────────────────────────────────

def dry_run():
    sep("═")
    print("  DRY-RUN — RESUMEN DE DATOS QUE SERÁN ELIMINADOS")
    sep("═")

    total = 0
    with app.app_context():
        for table, label in TABLES:
            n = count(table)
            if n is None:
                print(f"  {label:<40}  —  tabla no existe")
            else:
                marker = " ◄ TIENE DATOS" if n > 0 else ""
                print(f"  {label:<40}  {n:>6} filas{marker}")
                total += n

        sep()
        print(f"  TOTAL DE REGISTROS A ELIMINAR: {total}")
        sep()

        print("\n  TABLAS QUE SE CONSERVAN:")
        for t in PRESERVED:
            n = count(t)
            if n is not None:
                print(f"    {t:<35}  {n:>6} filas  ✓")
        sep()

    return total

# ────────────────────────────────────────────────────────────────────────────
# PASO 2 — BACKUP
# ────────────────────────────────────────────────────────────────────────────

def backup():
    sep("═")
    print("  BACKUP DE BASE DE DATOS")
    sep("═")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"/tmp/qoricash_backup_{ts}.sql"

    raw_url = os.environ.get("DATABASE_URL", "")
    cmd = ["pg_dump", "--no-password", "--format=plain", "--file", backup_file, raw_url]

    print(f"  Generando: {backup_file}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        size = os.path.getsize(backup_file)
        print(f"  ✓  Backup completado — {size / 1024:.1f} KB")
        print(f"  ✓  Ubicación: {backup_file}")
    else:
        print(f"  ✗  pg_dump falló:\n{result.stderr}")
        print("  ADVERTENCIA: Continuando sin backup físico.")
        print("  Asegúrate de tener un snapshot de Render antes de continuar.")

    sep()
    return backup_file

# ────────────────────────────────────────────────────────────────────────────
# PASO 3 — LIMPIEZA
# ────────────────────────────────────────────────────────────────────────────

def clean():
    sep("═")
    print("  EJECUTANDO LIMPIEZA")
    sep("═")

    total = 0
    with app.app_context():
        for idx, (table, label) in enumerate(TABLES, start=1):
            n = safe_delete(table, label, idx)
            total += n

        db.session.commit()

    sep()
    print(f"  ✓  LIMPIEZA COMPLETADA — {total} registros eliminados")
    sep()
    return total

# ────────────────────────────────────────────────────────────────────────────
# PASO 4 — VERIFICACIÓN FINAL
# ────────────────────────────────────────────────────────────────────────────

def verify():
    sep("═")
    print("  VERIFICACIÓN FINAL")
    sep("═")

    issues = []
    with app.app_context():
        print("  Tablas que deben estar vacías:")
        for table, label in TABLES:
            n = count(table)
            if n is None:
                print(f"    {label:<40}  N/A")
            elif n == 0:
                print(f"    {label:<40}  ✓  vacía")
            else:
                print(f"    {label:<40}  ✗  AÚN TIENE {n} FILAS")
                issues.append((label, n))

        sep()
        print("  Tablas preservadas:")
        for t in PRESERVED:
            n = count(t)
            if n is not None:
                print(f"    {t:<35}  {n:>6} filas  ✓")

        sep()
        if issues:
            print("  ✗  INCONSISTENCIAS ENCONTRADAS:")
            for label, n in issues:
                print(f"     - {label}: {n} registros restantes")
        else:
            print("  ✓  Sistema limpio. Listo para producción.")
        sep("═")

# ────────────────────────────────────────────────────────────────────────────
# MAIN
# ────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print()
    sep("═")
    print("  QORICASH — PREPARACIÓN PARA PRODUCCIÓN")
    print(f"  Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Entorno: {FLASK_ENV}")
    sep("═")
    print()

    # ── PASO 1: DRY-RUN ─────────────────────────────────────────────────────
    total = dry_run()

    if total == 0:
        print("\n  No hay datos de prueba. El sistema ya está limpio.")
        sys.exit(0)

    # ── CONFIRMACIÓN ────────────────────────────────────────────────────────
    print()
    print("  ⚠️  ADVERTENCIA: Esta acción eliminará TODOS los registros listados.")
    print("  ⚠️  Esta operación es IRREVERSIBLE una vez confirmada.")
    print()
    confirm = input("  Escribe SI para continuar: ").strip()

    if confirm != "SI":
        print("\n  Operación cancelada.")
        sys.exit(0)

    # ── PASO 2: BACKUP ───────────────────────────────────────────────────────
    backup_file = backup()

    # ── PASO 3: LIMPIEZA ─────────────────────────────────────────────────────
    clean()

    # ── PASO 4: VERIFICACIÓN ─────────────────────────────────────────────────
    verify()
