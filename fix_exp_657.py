#!/usr/bin/env python3
"""
FIX: Contabilizar EXP-657 (BBVA→BBVA) — fecha 2026-07-10.

Problema: BankBalance.apply_operation() y JournalService no se ejecutaron
correctamente porque BBVA no estaba en _ALIASES → _normalize('BBVA') = '' →
_update() silenciosamente ignoró los movimientos.

Fix aplicado en bank_balance.py: BBVA → INTERBANK en _ALIASES.
Este script retriggeriza ambos procesos para EXP-657.
"""
from datetime import datetime, date

FECHA_HOY     = date(2026, 7, 10)
DATETIME_HOY  = datetime(2026, 7, 10, 17, 0, 0)
OP_CODE       = 'EXP-657'


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
        print(f"FIX: {OP_CODE} — contabilizar BBVA→BBVA como INTERBANK")
        print("=" * 60)

        master = User.query.filter_by(role='Master').first()
        master_id = master.id if master else None

        op = Operation.query.filter_by(operation_id=OP_CODE).first()
        if not op:
            print(f"  ✗ Operación {OP_CODE} no encontrada.")
            return

        print(f"\n  Status       : {op.status}")
        print(f"  Tipo         : {op.operation_type}")
        print(f"  PEN          : {op.amount_pen}")
        print(f"  USD          : {op.amount_usd}")
        print(f"  TC           : {op.exchange_rate}")
        print(f"  source_acct  : {op.source_account}")
        print(f"  dest_acct    : {op.destination_account}")
        print(f"  source_bank  : {getattr(op, 'source_bank_name', 'n/a')}")
        print(f"  dest_bank    : {getattr(op, 'destination_bank_name', 'n/a')}")
        print(f"  completed_at : {op.completed_at}")

        if op.client_deposits:
            print(f"\n  Depositos cliente:")
            for d in op.client_deposits:
                print(f"    qc_bank={d.get('qc_bank','?')}  importe={d.get('importe','?')}  cuenta_cargo={d.get('cuenta_cargo','?')}")
        if op.client_payments:
            print(f"  Pagos a cliente:")
            for p in op.client_payments:
                print(f"    qc_bank={p.get('qc_bank','?')}  importe={p.get('importe','?')}  cuenta_destino={p.get('cuenta_destino','?')}")

        # ── Asiento contable ─────────────────────────────────────────────
        print(f"\n{'─'*50}")
        existing_entry = JournalEntry.query.filter_by(
            source_type='operation', source_id=op.id
        ).first()

        if existing_entry:
            print(f"  ✓ Asiento ya existe: id={existing_entry.id} fecha={existing_entry.entry_date}")
            for line in (existing_entry.lines or []):
                print(f"    [{line.get('account_code')}] DEBE={line.get('debe',0):.2f} HABER={line.get('haber',0):.2f} {line.get('description','')}")
        else:
            # Asegurar completed_at para que JournalService use la fecha correcta
            if not op.completed_at or op.completed_at.date() != FECHA_HOY:
                op.completed_at = DATETIME_HOY
                db.session.commit()
                print(f"  → completed_at corregido a {DATETIME_HOY}")

            try:
                entry = JournalService.create_entry_for_completed_operation(
                    op, created_by_id=master_id
                )
                if entry:
                    print(f"  ✓ Asiento contable creado: id={entry.id} fecha={entry.entry_date}")
                    for line in (entry.lines or []):
                        print(f"    [{line.get('account_code')}] DEBE={line.get('debe',0):.2f} HABER={line.get('haber',0):.2f} {line.get('description','')}")
                else:
                    print(f"  ✗ JournalService retornó None (ver logs del servidor).")
            except Exception as e:
                print(f"  ✗ Error en asiento: {e}")
                try:
                    db.session.rollback()
                except Exception:
                    pass

        # ── Movimientos bancarios ────────────────────────────────────────
        print(f"\n{'─'*50}")
        existing_mv = BankMovement.query.filter_by(
            source_type='operation', operation_id=op.id
        ).all()

        if existing_mv:
            print(f"  → {len(existing_mv)} movimiento(s) ya existen:")
            updated = 0
            for mv in existing_mv:
                print(f"    {mv.bank_name} {mv.currency} {mv.amount:+.2f} → {mv.movement_date.date()}")
                if mv.movement_date.date() != FECHA_HOY or mv.closure_date != FECHA_HOY:
                    mv.movement_date = DATETIME_HOY
                    mv.closure_date  = FECHA_HOY
                    updated += 1
            if updated:
                db.session.commit()
                print(f"  ✓ {updated} fecha(s) corregida(s) a {FECHA_HOY}.")
            else:
                print(f"  ✓ Fechas ya correctas.")
        else:
            print(f"  → Sin movimientos bancarios — ejecutando BankBalance.apply_operation()")
            try:
                BankBalance.apply_operation(op)
                db.session.commit()
                nuevos = BankMovement.query.filter_by(
                    source_type='operation', operation_id=op.id
                ).all()
                for mv in nuevos:
                    mv.movement_date = DATETIME_HOY
                    mv.closure_date  = FECHA_HOY
                    print(f"    {mv.bank_name} {mv.currency} {mv.amount:+.2f} → {FECHA_HOY}")
                db.session.commit()
                print(f"  ✓ {len(nuevos)} movimiento(s) creado(s) y fechados a {FECHA_HOY}.")
            except Exception as e:
                print(f"  ✗ Error en movimientos: {e}")
                import traceback
                traceback.print_exc()
                try:
                    db.session.rollback()
                except Exception:
                    pass

        # ── Resultado final ──────────────────────────────────────────────
        print(f"\n{'='*60}")
        db.session.refresh(op)
        entry_ok = JournalEntry.query.filter_by(source_type='operation', source_id=op.id).first()
        mvs_ok   = BankMovement.query.filter_by(source_type='operation', operation_id=op.id).count()
        print(f"  RESULTADO {OP_CODE}:")
        print(f"    Status       : {op.status}")
        print(f"    completed_at : {op.completed_at}")
        print(f"    Asiento      : {'✓ id=' + str(entry_ok.id) + ' fecha=' + str(entry_ok.entry_date) if entry_ok else '✗ SIN ASIENTO'}")
        print(f"    Movimientos  : {mvs_ok}")
        print(f"{'='*60}")


if __name__ == '__main__':
    run()
