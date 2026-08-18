#!/usr/bin/env python3
"""
FIX EXP-796: Cambiar estado de Cancelado a Completada con fecha backdated 2026-08-14.
Crea asientos contables y movimientos bancarios con fecha 14 de agosto.
"""
from datetime import datetime, date

FECHA_OP    = date(2026, 8, 14)
DATETIME_OP = datetime(2026, 8, 14, 17, 0, 0)
OP_CODE     = 'EXP-796'

def run():
    from app import create_app
    from app.extensions import db
    from app.models.operation import Operation
    from app.models.bank_movement import BankMovement
    from app.models.bank_balance import BankBalance
    from app.models.journal_entry import JournalEntry
    from app.services.accounting.journal_service import JournalService
    from app.models.user import User

    app = create_app()
    with app.app_context():
        print("=" * 60)
        print(f"FIX EXP-796 → Completada backdated {FECHA_OP}")
        print("=" * 60)

        op = Operation.query.filter_by(operation_id=OP_CODE).first()
        if not op:
            print(f"✗ No se encontró la operación {OP_CODE}")
            return

        print(f"\n  Estado actual : {op.status}")
        print(f"  Tipo          : {op.operation_type}")
        print(f"  PEN           : {op.amount_pen}")
        print(f"  USD           : {op.amount_usd}")
        print(f"  TC            : {op.exchange_rate}")
        print(f"  Cliente       : {op.client.full_name if op.client else 'N/A'}")
        print(f"  created_at    : {op.created_at}")

        # ── 1. Cambiar estado a Completada (bypass validación de transición) ────
        if op.status != 'Completada':
            op.status       = 'Completada'
            op.completed_at = DATETIME_OP
            op.updated_at   = DATETIME_OP
            if not op.assigned_operator_id:
                master = User.query.filter_by(role='Master').first()
                if master:
                    op.assigned_operator_id = master.id
            db.session.commit()
            print(f"\n  ✓ Status → Completada (completed_at={DATETIME_OP})")
        else:
            print(f"\n  ✓ Ya estaba en Completada")
            if not op.completed_at or op.completed_at.date() != FECHA_OP:
                op.completed_at = DATETIME_OP
                op.updated_at   = DATETIME_OP
                db.session.commit()
                print(f"  ✓ completed_at ajustado a {DATETIME_OP}")

        master = User.query.filter_by(role='Master').first()
        master_id = master.id if master else None

        # ── 2. Asiento contable ─────────────────────────────────────────────────
        existing_entry = JournalEntry.query.filter_by(
            source_type='operation', source_id=op.id
        ).first()

        if existing_entry:
            print(f"\n  ✓ Asiento ya existe: id={existing_entry.id} fecha={existing_entry.entry_date}")
            # Asegurar que la fecha del asiento sea 14 de agosto
            if existing_entry.entry_date != FECHA_OP:
                existing_entry.entry_date = FECHA_OP
                db.session.commit()
                print(f"  ✓ Fecha del asiento corregida a {FECHA_OP}")
        else:
            try:
                entry = JournalService.create_entry_for_completed_operation(
                    op, created_by_id=master_id
                )
                if entry:
                    # Asegurar fecha correcta
                    if entry.entry_date != FECHA_OP:
                        entry.entry_date = FECHA_OP
                        db.session.commit()
                    print(f"\n  ✓ Asiento contable creado: id={entry.id} fecha={entry.entry_date}")
                else:
                    print(f"\n  ✗ JournalService retornó None — revisar logs del servidor.")
            except Exception as e:
                print(f"\n  ✗ Error en asiento: {e}")
                try:
                    db.session.rollback()
                except:
                    pass

        # ── 3. Movimientos bancarios ────────────────────────────────────────────
        existing_mv = BankMovement.query.filter_by(
            source_type='operation', operation_id=op.id
        ).all()

        if existing_mv:
            print(f"\n  → {len(existing_mv)} movimiento(s) ya existen — backdateando si es necesario.")
            updated = 0
            for mv in existing_mv:
                if mv.movement_date.date() != FECHA_OP or mv.closure_date != FECHA_OP:
                    mv.movement_date = DATETIME_OP
                    mv.closure_date  = FECHA_OP
                    updated += 1
                print(f"    {mv.bank_name} {mv.currency} {mv.amount:+.2f} → {mv.movement_date.date()}")
            if updated:
                db.session.commit()
                print(f"  ✓ {updated} fecha(s) actualizada(s).")
            else:
                print(f"  ✓ Fechas ya correctas.")
        else:
            # Crear movimientos bancarios
            try:
                BankBalance.apply_operation(op)
                db.session.commit()
                nuevos = BankMovement.query.filter_by(
                    source_type='operation', operation_id=op.id
                ).all()
                for mv in nuevos:
                    mv.movement_date = DATETIME_OP
                    mv.closure_date  = FECHA_OP
                    print(f"    {mv.bank_name} {mv.currency} {mv.amount:+.2f} → {FECHA_OP}")
                db.session.commit()
                print(f"\n  ✓ {len(nuevos)} movimiento(s) creados y backdateados a {FECHA_OP}.")
            except Exception as e:
                print(f"\n  ✗ Error en movimientos bancarios: {e}")
                try:
                    db.session.rollback()
                except:
                    pass

        # ── 4. Resumen final ────────────────────────────────────────────────────
        db.session.refresh(op)
        entry_ok = JournalEntry.query.filter_by(source_type='operation', source_id=op.id).first()
        mvs_ok   = BankMovement.query.filter_by(source_type='operation', operation_id=op.id).count()

        print(f"\n{'=' * 60}")
        print(f"  RESULTADO {OP_CODE}:")
        print(f"    Status       : {op.status}")
        print(f"    completed_at : {op.completed_at}")
        print(f"    Asiento      : {'✓ id=' + str(entry_ok.id) + ' fecha=' + str(entry_ok.entry_date) if entry_ok else '✗ SIN ASIENTO'}")
        print(f"    Movimientos  : {mvs_ok}")
        print(f"{'=' * 60}")

if __name__ == '__main__':
    run()
