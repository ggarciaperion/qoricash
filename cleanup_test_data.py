"""
cleanup_test_data.py — Limpieza completa de datos de prueba
===========================================================
Elimina en orden correcto todos los datos generados por:
  - seed_abril.py
  - seed_ops_test.py
  - set_test_risk.py

Ejecutar en Render shell:
    python3 cleanup_test_data.py
"""
import os, sys
from datetime import datetime

DATABASE_URL = os.environ.get('DATABASE_URL', '')
if not DATABASE_URL:
    # Intentar cargar .env local
    try:
        from dotenv import load_dotenv
        load_dotenv()
        DATABASE_URL = os.environ.get('DATABASE_URL', '')
    except ImportError:
        pass

if not DATABASE_URL:
    print('ERROR: DATABASE_URL no encontrada')
    sys.exit(1)

if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

engine = sa.create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

def run(sql, params=None):
    r = session.execute(sa.text(sql), params or {})
    session.flush()
    return r.rowcount

try:
    print('=== LIMPIEZA DE DATOS DE PRUEBA ===\n')

    # ── 1. Amarres vinculados a operaciones TEST ──────────────────────────
    n = run("""
        DELETE FROM accounting_matches
        WHERE buy_operation_id IN (
            SELECT id FROM operations WHERE operation_id LIKE 'TSOP-%' OR operation_id LIKE '%-SEED-%'
        )
        OR sell_operation_id IN (
            SELECT id FROM operations WHERE operation_id LIKE 'TSOP-%' OR operation_id LIKE '%-SEED-%'
        )
    """)
    print(f'  Amarres eliminados:          {n}')

    # ── 2. Lotes vacíos (sin matches) ────────────────────────────────────
    n = run("""
        DELETE FROM accounting_batches
        WHERE id NOT IN (SELECT DISTINCT batch_id FROM accounting_matches WHERE batch_id IS NOT NULL)
        AND description LIKE '%TEST%'
    """)
    print(f'  Lotes de prueba eliminados:  {n}')

    # ── 3. Journal entry lines de operaciones TEST ────────────────────────
    n = run("""
        DELETE FROM journal_entry_lines
        WHERE journal_entry_id IN (
            SELECT journal_entry_id FROM operations
            WHERE operation_id LIKE 'TSOP-%' OR operation_id LIKE '%-SEED-%'
            AND journal_entry_id IS NOT NULL
        )
    """)
    print(f'  Líneas de asiento (ops):     {n}')

    # ── 4. Journal entries de operaciones TEST ────────────────────────────
    n = run("""
        DELETE FROM journal_entries
        WHERE id IN (
            SELECT journal_entry_id FROM operations
            WHERE (operation_id LIKE 'TSOP-%' OR operation_id LIKE '%-SEED-%')
            AND journal_entry_id IS NOT NULL
        )
    """)
    print(f'  Asientos (ops):              {n}')

    # ── 5. Operaciones TEST ───────────────────────────────────────────────
    n = run("""
        DELETE FROM operations
        WHERE operation_id LIKE 'TSOP-%' OR operation_id LIKE '%-SEED-%'
    """)
    print(f'  Operaciones eliminadas:      {n}')

    # ── 6. Journal entry lines de gastos TEST ────────────────────────────
    n = run("""
        DELETE FROM journal_entry_lines
        WHERE journal_entry_id IN (
            SELECT journal_entry_id FROM expense_records
            WHERE description LIKE '[TEST-ABR]%'
            AND journal_entry_id IS NOT NULL
        )
    """)
    print(f'  Líneas de asiento (gastos):  {n}')

    # ── 7. Journal entries de gastos TEST ────────────────────────────────
    n = run("""
        DELETE FROM journal_entries
        WHERE id IN (
            SELECT journal_entry_id FROM expense_records
            WHERE description LIKE '[TEST-ABR]%'
            AND journal_entry_id IS NOT NULL
        )
    """)
    print(f'  Asientos (gastos):           {n}')

    # ── 8. Gastos TEST ────────────────────────────────────────────────────
    n = run("DELETE FROM expense_records WHERE description LIKE '[TEST-ABR]%'")
    print(f'  Gastos eliminados:           {n}')

    # ── 9. TraderDailyProfit de abril 2026 ───────────────────────────────
    n = run("""
        DELETE FROM trader_daily_profits
        WHERE EXTRACT(year FROM profit_date) = 2026
        AND EXTRACT(month FROM profit_date) = 4
    """)
    print(f'  TraderDailyProfit (abr26):   {n}')

    # ── 10. Compliance alerts de clientes TEST ────────────────────────────
    n = run("""
        DELETE FROM compliance_alerts
        WHERE client_id IN (
            SELECT id FROM clients WHERE email LIKE '%@test-qoricash.pe'
        )
        OR (status = 'Pendiente' AND client_id IN (
            SELECT id FROM clients WHERE dni = '73085751'
        ))
    """)
    print(f'  Alertas compliance:          {n}')

    # ── 11. Risk profiles de clientes TEST ───────────────────────────────
    n = run("""
        UPDATE client_risk_profiles
        SET risk_score = 10, is_pep = FALSE, has_legal_issues = FALSE,
            in_restrictive_lists = FALSE, high_volume_operations = FALSE,
            dd_level = 'Básica', kyc_status = 'Aprobado'
        WHERE client_id IN (
            SELECT id FROM clients WHERE dni = '73085751'
        )
    """)
    print(f'  Perfiles KYC revertidos:     {n}')

    n = run("""
        DELETE FROM client_risk_profiles
        WHERE client_id IN (
            SELECT id FROM clients WHERE email LIKE '%@test-qoricash.pe'
        )
    """)
    print(f'  Risk profiles TEST:          {n}')

    # ── 12. Usuarios TEST ────────────────────────────────────────────────
    n = run("DELETE FROM users WHERE username LIKE 'test_%'")
    print(f'  Usuarios TEST eliminados:    {n}')

    # ── 13. Clientes TEST ────────────────────────────────────────────────
    n = run("DELETE FROM clients WHERE email LIKE '%@test-qoricash.pe'")
    print(f'  Clientes TEST eliminados:    {n}')

    # ── 14. Período Abril 2026 (si fue creado por seed) ──────────────────
    # Solo borrar si no tiene journal_entries reales asociados
    real_entries = session.execute(sa.text("""
        SELECT COUNT(*) FROM journal_entries
        WHERE EXTRACT(year FROM entry_date) = 2026
        AND EXTRACT(month FROM entry_date) = 4
    """)).scalar()

    if real_entries == 0:
        n = run("DELETE FROM accounting_periods WHERE year = 2026 AND month = 4")
        print(f'  Período Abr 2026:            {n} (sin asientos reales, eliminado)')
    else:
        print(f'  Período Abr 2026:            conservado ({real_entries} asientos reales)')

    session.commit()
    print('\n✅ Limpieza completada. Sistema libre de datos de prueba.')

except Exception as e:
    session.rollback()
    print(f'\nERROR: {e}')
    import traceback; traceback.print_exc()
    sys.exit(1)
finally:
    session.close()
