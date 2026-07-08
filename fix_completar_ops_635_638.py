#!/usr/bin/env python3
"""
FIX v2: Completar EXP-635 y EXP-638 con fecha backdated a 2026-07-07.
Corrige: nombre de módulo JournalEntry → app.models.journal_entry
"""
from datetime import datetime, date

FECHA_AYER   = date(2026, 7, 7)
DATETIME_AYER = datetime(2026, 7, 7, 17, 0, 0)
OPS = ['EXP-635', 'EXP-638']

def run():
    from app import create_app
    from app.extensions import db
    from app.models.operation import Operation
    from app.models.bank_movement import BankMovement
    from app.models.bank_balance import BankBalance
    from app.models.journal_entry import JournalEntry          # ← nombre correcto
    from app.services.accounting.journal_service import JournalService
    from app.models.user import User

    app = create_app()
    with app.app_context():
        print("=" * 60)
        print("FIX v2: EXP-635 y EXP-638 backdated 2026-07-07")
        print("=" * 60)

        master = User.query.filter_by(role='Master').first()
        master_id = master.id if master else None

        for code in OPS:
            print(f"\n── {code} ──────────────────────────────────────")
            op = Operation.query.filter_by(operation_id=code).first()
            if not op:
                print(f"  ✗ No encontrada.")
                continue

            print(f"  Status: {op.status} | Tipo: {op.operation_type} | "
                  f"PEN={op.amount_pen} USD={op.amount_usd} TC={op.exchange_rate}")

            # ── Asiento contable ─────────────────────────────────────────────
            existing_entry = JournalEntry.query.filter_by(
                source_type='operation', source_id=op.id
            ).first()

            if existing_entry:
                print(f"  ✓ Asiento ya existe: id={existing_entry.id} fecha={existing_entry.entry_date}")
            else:
                # Aseguramos que completed_at esté bien para que JournalService use fecha correcta
                if not op.completed_at or op.completed_at.date() != FECHA_AYER:
                    op.completed_at = DATETIME_AYER
                    db.session.commit()

                try:
                    entry = JournalService.create_entry_for_completed_operation(
                        op, created_by_id=master_id
                    )
                    if entry:
                        print(f"  ✓ Asiento contable creado: id={entry.id} fecha={entry.entry_date}")
                    else:
                        print(f"  ✗ JournalService retornó None (ver logs del servidor).")
                except Exception as e:
                    print(f"  ✗ Error en asiento: {e}")
                    try: db.session.rollback()
                    except: pass

            # ── Movimientos bancarios ────────────────────────────────────────
            existing_mv = BankMovement.query.filter_by(
                source_type='operation', operation_id=op.id
            ).all()

            if existing_mv:
                print(f"  → {len(existing_mv)} movimientos ya existen — solo backdateando si es necesario.")
                updated = 0
                for mv in existing_mv:
                    if mv.movement_date.date() != FECHA_AYER or mv.closure_date != FECHA_AYER:
                        mv.movement_date = DATETIME_AYER
                        mv.closure_date  = FECHA_AYER
                        updated += 1
                    print(f"    {mv.bank_name} {mv.currency} {mv.amount:+.2f} → {mv.movement_date.date()}")
                if updated:
                    db.session.commit()
                    print(f"  ✓ {updated} fecha(s) actualizada(s).")
                else:
                    print(f"  ✓ Fechas ya correctas.")
            else:
                # Solo aplicar si no existen
                if op.status != 'Completada':
                    op.status       = 'Completada'
                    op.completed_at = DATETIME_AYER
                    if not op.assigned_operator_id:
                        op.assigned_operator_id = master_id
                    db.session.commit()
                    print(f"  ✓ Status → Completada")

                try:
                    BankBalance.apply_operation(op)
                    db.session.commit()
                    nuevos = BankMovement.query.filter_by(
                        source_type='operation', operation_id=op.id
                    ).all()
                    for mv in nuevos:
                        mv.movement_date = DATETIME_AYER
                        mv.closure_date  = FECHA_AYER
                        print(f"    {mv.bank_name} {mv.currency} {mv.amount:+.2f} → {FECHA_AYER}")
                    db.session.commit()
                    print(f"  ✓ {len(nuevos)} movimiento(s) creados y backdateados.")
                except Exception as e:
                    print(f"  ✗ Error en movimientos: {e}")
                    try: db.session.rollback()
                    except: pass

            # ── Status final ─────────────────────────────────────────────────
            db.session.refresh(op)
            entry_ok = JournalEntry.query.filter_by(source_type='operation', source_id=op.id).first()
            mvs_ok   = BankMovement.query.filter_by(source_type='operation', operation_id=op.id).count()
            print(f"\n  RESULTADO {code}:")
            print(f"    Status       : {op.status}")
            print(f"    completed_at : {op.completed_at}")
            print(f"    Asiento      : {'✓ id=' + str(entry_ok.id) + ' fecha=' + str(entry_ok.entry_date) if entry_ok else '✗ SIN ASIENTO'}")
            print(f"    Movimientos  : {mvs_ok}")

        print("\n" + "=" * 60)
        print("FIX v2 completado.")
        print("=" * 60)

if __name__ == '__main__':
    run()
