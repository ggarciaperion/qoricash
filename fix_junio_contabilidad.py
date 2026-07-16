"""
Fix contabilidad junio 2026 — QoriCash
Corrige: RUC en SystemConfig + anula gasto incorrecto S/ 4,021.38 del 15/06
Ejecutar en Render shell: python fix_junio_contabilidad.py
"""
from app import create_app
from app.extensions import db
from app.models.system_config import SystemConfig
from app.models.journal_entry import JournalEntry
from app.models.journal_entry_line import JournalEntryLine
from sqlalchemy import extract, func
from decimal import Decimal

app = create_app()

with app.app_context():

    # ── 1. Corregir RUC ──────────────────────────────────────────
    ruc_actual = SystemConfig.get('RUC', 'NO EXISTE')
    print(f"\n[RUC] Valor actual: {ruc_actual}")
    SystemConfig.set('RUC', '20615113698', description='RUC QoriCash SAC')
    db.session.commit()
    print("[RUC] ✅ Corregido a: 20615113698")

    # ── 2. Anular gasto incorrecto 15/06 ~S/ 4,021.38 ────────────
    print("\n[GASTO] Buscando asiento incorrecto del 15/06/2026...")

    candidatos = db.session.query(
        JournalEntry.id,
        JournalEntry.entry_number,
        JournalEntry.entry_date,
        JournalEntry.description,
        func.sum(JournalEntryLine.debe).label('td'),
    ).join(JournalEntryLine, JournalEntryLine.journal_entry_id == JournalEntry.id
    ).filter(
        extract('year',  JournalEntry.entry_date) == 2026,
        extract('month', JournalEntry.entry_date) == 6,
        JournalEntry.entry_date.between('2026-06-14', '2026-06-16'),
        JournalEntry.status == 'activo',
        JournalEntryLine.account_code.like('6%'),
    ).group_by(
        JournalEntry.id, JournalEntry.entry_number,
        JournalEntry.entry_date, JournalEntry.description,
    ).all()

    print(f"  Candidatos encontrados: {len(candidatos)}")
    target = None
    for c in candidatos:
        print(f"  ID={c.id} | {c.entry_number} | {c.entry_date} | "
              f"S/ {float(c.td or 0):.2f} | {(c.description or '')[:60]}")
        if abs(Decimal(str(c.td or 0)) - Decimal('4021.38')) < Decimal('1.00'):
            target = c

    if target:
        entry = db.session.get(JournalEntry, target.id)
        entry.status = 'anulado'
        db.session.commit()
        print(f"[GASTO] ✅ Asiento {target.entry_number} (ID={target.id}) ANULADO")
    else:
        print("[GASTO] ⚠️  No se encontró asiento exacto. Revisa los candidatos arriba.")

    # ── 3. Verificar ingresos junio post-corrección ───────────────
    print("\n[INGRESOS] Verificando total junio 2026...")

    total_ing = db.session.query(
        func.sum(JournalEntryLine.haber)
    ).join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id
    ).filter(
        extract('year',  JournalEntry.entry_date) == 2026,
        extract('month', JournalEntry.entry_date) == 6,
        JournalEntry.status == 'activo',
        JournalEntryLine.account_code.like('7%'),
        JournalEntryLine.haber > 0,
    ).scalar() or 0

    diff = float(total_ing) - 3824.38
    print(f"  Total ingresos en libros: S/ {float(total_ing):.2f}")
    print(f"  Declarado en 621:         S/ 3,824.38")
    print(f"  Diferencia:               S/ {diff:.2f}")

    if abs(diff) > 1:
        print("\n[INGRESOS] ⚠️  Diferencia detectada. Listado de asientos 7xxx activos:")
        lines_7 = db.session.query(
            JournalEntry.entry_date,
            JournalEntry.entry_number,
            JournalEntry.description,
            JournalEntryLine.account_code,
            JournalEntryLine.haber,
        ).join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id
        ).filter(
            extract('year',  JournalEntry.entry_date) == 2026,
            extract('month', JournalEntry.entry_date) == 6,
            JournalEntry.status == 'activo',
            JournalEntryLine.account_code.like('7%'),
            JournalEntryLine.haber > 0,
        ).order_by(JournalEntry.entry_date, JournalEntry.id).all()

        for l in lines_7:
            print(f"  {l.entry_date} | {l.entry_number} | {l.account_code} | "
                  f"S/ {float(l.haber):.2f} | {(l.description or '')[:50]}")
    else:
        print("[INGRESOS] ✅ Cuadra correctamente con lo declarado.")

    print("\n✅ Script finalizado.")
