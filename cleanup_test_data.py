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

DATABASE_URL = os.environ.get('DATABASE_URL', '')
if not DATABASE_URL:
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
    try:
        r = session.execute(sa.text(sql), params or {})
        session.flush()
        return r.rowcount
    except Exception as e:
        print(f'  [WARN] {e}')
        session.rollback()
        return 0

def section(title):
    print(f'\n--- {title} ---')

try:
    print('=== LIMPIEZA DE DATOS DE PRUEBA ===')

    # ── Obtener IDs de clientes TEST ──────────────────────────────────────
    rows = session.execute(sa.text(
        "SELECT id, email FROM clients WHERE email LIKE '%@test-qoricash.pe'"
    )).fetchall()

    if not rows:
        print('\nNo se encontraron clientes de prueba (@test-qoricash.pe).')
    else:
        client_ids = [r[0] for r in rows]
        print(f'\nClientes TEST encontrados: {len(client_ids)} → IDs {client_ids}')

        # Obtener operaciones de esos clientes
        op_rows = session.execute(sa.text(
            "SELECT id FROM operations WHERE client_id = ANY(:ids)"
        ), {'ids': client_ids}).fetchall()
        op_ids = [r[0] for r in op_rows]

        # Journal entries vinculados via source_id
        je_rows = session.execute(sa.text(
            "SELECT id FROM journal_entries WHERE source_id = ANY(:ids) AND source_type = 'operation'"
        ), {'ids': op_ids}).fetchall() if op_ids else []
        je_ids = [r[0] for r in je_rows]
        print(f'  Operaciones vinculadas:  {len(op_ids)}')

        section('1. Amarres de esas operaciones')
        if op_ids:
            n = run(
                "DELETE FROM accounting_matches "
                "WHERE buy_operation_id = ANY(:ids) OR sell_operation_id = ANY(:ids)",
                {'ids': op_ids}
            )
            print(f'  Amarres eliminados: {n}')

        section('2. Journal entry lines de operaciones')
        if je_ids:
            n = run("DELETE FROM journal_entry_lines WHERE journal_entry_id = ANY(:ids)", {'ids': je_ids})
            print(f'  Líneas eliminadas: {n}')

        section('3. Facturas (invoices) de operaciones')
        if op_ids:
            n = run("DELETE FROM invoices WHERE operation_id = ANY(:ids)", {'ids': op_ids})
            print(f'  Facturas eliminadas: {n}')

        section('4. Operaciones')
        if op_ids:
            n = run("DELETE FROM operations WHERE id = ANY(:ids)", {'ids': op_ids})
            print(f'  Operaciones eliminadas: {n}')

        section('5. Journal entries huérfanos')
        if je_ids:
            n = run("DELETE FROM journal_entries WHERE id = ANY(:ids)", {'ids': je_ids})
            print(f'  Asientos eliminados: {n}')

        section('6. Compliance — todas las tablas')
        for table in ['compliance_alerts', 'compliance_documents',
                      'restrictive_list_checks', 'transaction_monitoring',
                      'compliance_audit']:
            n = run(f"DELETE FROM {table} WHERE client_id = ANY(:ids)", {'ids': client_ids})
            print(f'  {table}: {n}')

        section('7. Risk profiles')
        n = run("DELETE FROM client_risk_profiles WHERE client_id = ANY(:ids)", {'ids': client_ids})
        print(f'  Perfiles eliminados: {n}')

        section('8. Reward codes')
        n = run("DELETE FROM reward_codes WHERE client_id = ANY(:ids)", {'ids': client_ids})
        print(f'  Reward codes eliminados: {n}')

        section('9. Auto-referencia referred_by')
        n = run("UPDATE clients SET referred_by = NULL WHERE referred_by = ANY(:ids)", {'ids': client_ids})
        print(f'  Refs eliminadas: {n}')

        section('10. CLIENTES TEST')
        n = run("DELETE FROM clients WHERE id = ANY(:ids)", {'ids': client_ids})
        print(f'  Clientes eliminados: {n}')

    # ── Operaciones TSOP/SEED huérfanas (sin cliente TEST) ────────────────
    section('11. Operaciones TSOP-*/SEED residuales')
    orphan_ops = session.execute(sa.text(
        "SELECT id FROM operations "
        "WHERE operation_id LIKE 'TSOP-%' OR operation_id LIKE '%-SEED-%'"
    )).fetchall()
    if orphan_ops:
        oids = [r[0] for r in orphan_ops]
        jeids_rows = session.execute(sa.text(
            "SELECT id FROM journal_entries WHERE source_id = ANY(:ids) AND source_type = 'operation'"
        ), {'ids': oids}).fetchall()
        jeids = [r[0] for r in jeids_rows]
        run("DELETE FROM accounting_matches WHERE buy_operation_id = ANY(:ids) OR sell_operation_id = ANY(:ids)", {'ids': oids})
        if jeids:
            run("DELETE FROM journal_entry_lines WHERE journal_entry_id = ANY(:ids)", {'ids': jeids})
            run("DELETE FROM journal_entries WHERE id = ANY(:ids)", {'ids': jeids})
        n = run("DELETE FROM operations WHERE id = ANY(:ids)", {'ids': oids})
        print(f'  Operaciones residuales eliminadas: {n}')
    else:
        print('  Ninguna')

    # ── Usuarios TEST ─────────────────────────────────────────────────────
    section('12. Usuarios test_*')
    n = run("DELETE FROM users WHERE username LIKE 'test_%'")
    print(f'  Usuarios eliminados: {n}')

    # ── KYC revert DNI 73085751 ───────────────────────────────────────────
    section('13. KYC revert DNI 73085751')
    n = run("""
        UPDATE client_risk_profiles SET
            risk_score = 10, is_pep = FALSE, has_legal_issues = FALSE,
            in_restrictive_lists = FALSE, high_volume_operations = FALSE,
            dd_level = 'Básica', kyc_status = 'Aprobado'
        WHERE client_id = (SELECT id FROM clients WHERE dni = '73085751' LIMIT 1)
    """)
    run("""
        DELETE FROM compliance_alerts
        WHERE status = 'Pendiente'
        AND client_id = (SELECT id FROM clients WHERE dni = '73085751' LIMIT 1)
    """)
    print(f'  Perfil revertido: {n}')

    # ── DIAMANTA S.A.C. — set_test_risk lo tocó por fallback ─────────────
    # El script set_test_risk usa LIMIT 1 como fallback y pudo haber
    # seteado kyc_status='Aprobado' en DIAMANTA. Resetear a 'Pendiente'.
    section('14. Restaurar KYC de DIAMANTA S.A.C. (RUC 20494899940)')
    n = run("""
        UPDATE client_risk_profiles SET
            kyc_status = 'Pendiente',
            is_pep = FALSE, has_legal_issues = FALSE,
            in_restrictive_lists = FALSE, high_volume_operations = FALSE,
            risk_score = 10, dd_level = 'Básica'
        WHERE client_id = (SELECT id FROM clients WHERE dni = '20494899940' LIMIT 1)
    """)
    if n == 0:
        # No tiene perfil aún — crear uno Pendiente
        run("""
            INSERT INTO client_risk_profiles
                (client_id, risk_score, is_pep, has_legal_issues, in_restrictive_lists,
                 high_volume_operations, dd_level, kyc_status, created_at, updated_at)
            SELECT id, 10, FALSE, FALSE, FALSE, FALSE, 'Básica', 'Pendiente', NOW(), NOW()
            FROM clients WHERE dni = '20494899940' LIMIT 1
        """)
        print('  Perfil KYC creado como Pendiente')
    else:
        print(f'  KYC restaurado a Pendiente: {n} registro(s)')
    run("""
        DELETE FROM compliance_alerts
        WHERE status = 'Pendiente'
        AND description LIKE '%DIAMANTA%'
    """)

    session.commit()
    print('\n✅ Limpieza completada.')

except Exception as e:
    session.rollback()
    print(f'\nERROR FATAL: {e}')
    import traceback; traceback.print_exc()
    sys.exit(1)
finally:
    session.close()
