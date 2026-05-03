"""
clean_test_gastos.py — Eliminar gastos de prueba [TEST-ABR]
============================================================
Elimina los expense_records con descripción [TEST-ABR] y sus
asientos contables asociados (journal_entries + journal_entry_lines).

Ejecutar en Render shell:
    python3 clean_test_gastos.py
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

try:
    print('=== LIMPIEZA DE GASTOS TEST [TEST-ABR] ===\n')

    # 1. Obtener IDs de los expense_records de prueba
    rows = session.execute(sa.text(
        "SELECT id, expense_date, description, journal_entry_id "
        "FROM expense_records WHERE description LIKE '%TEST-ABR%'"
    )).fetchall()

    if not rows:
        print('No se encontraron registros [TEST-ABR]. Nada que eliminar.')
        sys.exit(0)

    expense_ids   = [r[0] for r in rows]
    journal_ids   = [r[3] for r in rows if r[3] is not None]

    print(f'Gastos TEST encontrados: {len(expense_ids)}')
    for r in rows:
        print(f'  ID {r[0]} | {r[1]} | {r[2][:60]}')

    print()

    # 2. Borrar líneas de asiento
    if journal_ids:
        n = run(
            "DELETE FROM journal_entry_lines WHERE journal_entry_id = ANY(:ids)",
            {'ids': journal_ids}
        )
        print(f'Líneas de asiento eliminadas: {n}')

    # 3. Borrar los expense_records
    n = run(
        "DELETE FROM expense_records WHERE id = ANY(:ids)",
        {'ids': expense_ids}
    )
    print(f'Gastos eliminados: {n}')

    # 4. Borrar los journal_entries (después del expense_record para evitar FK)
    if journal_ids:
        n = run(
            "DELETE FROM journal_entries WHERE id = ANY(:ids)",
            {'ids': journal_ids}
        )
        print(f'Asientos contables eliminados: {n}')

    session.commit()
    print('\n✅ Limpieza completada.')

except Exception as e:
    session.rollback()
    print(f'\nERROR FATAL: {e}')
    import traceback; traceback.print_exc()
    sys.exit(1)
finally:
    session.close()
