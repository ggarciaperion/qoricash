#!/usr/bin/env python3
"""
FIX: Completar EXP-635 y EXP-638 con fecha backdated a 2026-07-07.

Qué hace:
  1. Verifica el estado actual de cada operación
  2. Cambia status → Completada con completed_at = 2026-07-07 17:00 (hora Peru)
  3. Genera asiento contable (usa completed_at.date() → 2026-07-07 automáticamente)
  4. Aplica movimientos bancarios y los backdatea a 2026-07-07
  5. Imprime resumen de todo lo que se ejecutó

Ejecutar en Render Shell:
  python3 fix_completar_ops_635_638.py

IMPORTANTE: Ejecutar UNA SOLA VEZ. Tiene guards contra doble ejecución.
"""
import sys
import os
from datetime import datetime, date

# ── Fecha backdated ──────────────────────────────────────────────────────────
FECHA_AYER = date(2026, 7, 7)
DATETIME_AYER = datetime(2026, 7, 7, 17, 0, 0)  # 5pm hora Peru
OPS = ['EXP-635', 'EXP-638']

def run():
    from app import create_app
    from app.extensions import db
    from app.models.operation import Operation
    from app.models.bank_movement import BankMovement
    from app.models.audit_log import AuditLog

    app = create_app()
    with app.app_context():

        print("=" * 60)
        print("FIX: Completar EXP-635 y EXP-638 backdated 2026-07-07")
        print("=" * 60)

        for code in OPS:
            print(f"\n── {code} ──────────────────────────────────────")
            op = Operation.query.filter_by(operation_id=code).first()

            if not op:
                print(f"  ✗ Operación {code} no encontrada. Abortando esta op.")
                continue

            print(f"  Estado actual : {op.status}")
            print(f"  Tipo          : {op.operation_type}")
            print(f"  Monto PEN     : {op.amount_pen}")
            print(f"  Monto USD     : {op.amount_usd}")
            print(f"  TC            : {op.exchange_rate}")
            print(f"  completed_at  : {op.completed_at}")

            # ── Guard: no volver a procesar si ya está completada ────────────
            if op.status == 'Completada':
                # Verificar si ya tiene movimientos y asiento
                from app.models.journal import JournalEntry
                entry = JournalEntry.query.filter_by(
                    source_type='operation', source_id=op.id
                ).first()
                mvs = BankMovement.query.filter_by(
                    source_type='operation', operation_id=op.id
                ).count()
                print(f"  ⚠  Ya está Completada — asiento: {'SÍ' if entry else 'NO'}, movimientos: {mvs}")
                print(f"  Saltando (guard anti-duplicado activo).")
                continue

            if op.status not in ('pendiente', 'Pendiente', 'En proceso', 'en_proceso'):
                print(f"  ✗ Estado inesperado: {op.status}. No se procesará.")
                continue

            # ── 1. Cambiar status y backdatear completed_at ──────────────────
            print(f"  → Cambiando status a Completada con fecha {FECHA_AYER}...")
            op.status        = 'Completada'
            op.completed_at  = DATETIME_AYER
            op.in_process_since = None

            # Si no tiene operador asignado, asignar ID=1 (Master por defecto)
            if not op.assigned_operator_id:
                from app.models.user import User
                master = User.query.filter_by(role='Master').first()
                if master:
                    op.assigned_operator_id = master.id
                    print(f"  → Operador asignado: {master.username} (id={master.id})")

            db.session.commit()
            print(f"  ✓ Status actualizado.")

            # ── 2. Asiento contable ──────────────────────────────────────────
            print(f"  → Generando asiento contable (fecha: {FECHA_AYER})...")
            try:
                from app.services.accounting.journal_service import JournalService
                from app.models.journal import JournalEntry

                # Verificar que no exista ya
                existing = JournalEntry.query.filter_by(
                    source_type='operation', source_id=op.id
                ).first()
                if existing:
                    print(f"  ⚠  Asiento contable ya existe (id={existing.id}) — omitiendo.")
                else:
                    entry = JournalService.create_entry_for_completed_operation(
                        op, created_by_id=op.assigned_operator_id
                    )
                    if entry:
                        print(f"  ✓ Asiento contable creado: id={entry.id}, fecha={entry.entry_date}")
                    else:
                        print(f"  ✗ No se generó asiento contable (ver logs).")
            except Exception as e:
                print(f"  ✗ Error en asiento contable: {e}")
                try:
                    db.session.rollback()
                except Exception:
                    pass

            # ── 3. Movimientos bancarios ─────────────────────────────────────
            print(f"  → Aplicando movimientos bancarios...")
            try:
                # Verificar que no existan ya
                existing_mv = BankMovement.query.filter_by(
                    source_type='operation', operation_id=op.id
                ).count()
                if existing_mv > 0:
                    print(f"  ⚠  Ya existen {existing_mv} movimientos — omitiendo apply_operation.")
                else:
                    from app.models.bank_balance import BankBalance
                    BankBalance.apply_operation(op)
                    db.session.commit()

                    # Backdatear los movimientos creados
                    nuevos_mv = BankMovement.query.filter_by(
                        source_type='operation', operation_id=op.id
                    ).all()
                    print(f"  ✓ {len(nuevos_mv)} movimiento(s) bancario(s) creados. Backdateando...")
                    for mv in nuevos_mv:
                        mv.movement_date = DATETIME_AYER
                        mv.closure_date  = FECHA_AYER
                        print(f"    → {mv.bank_name} {mv.currency} {mv.amount:+.2f} → fecha {FECHA_AYER}")
                    db.session.commit()
                    print(f"  ✓ Fechas de movimientos actualizadas a {FECHA_AYER}.")

            except Exception as e:
                print(f"  ✗ Error en movimientos bancarios: {e}")
                import traceback; traceback.print_exc()
                try:
                    db.session.rollback()
                except Exception:
                    pass

            # ── 4. Resumen final ─────────────────────────────────────────────
            db.session.refresh(op)
            from app.models.journal import JournalEntry
            entry_final = JournalEntry.query.filter_by(
                source_type='operation', source_id=op.id
            ).first()
            mvs_final = BankMovement.query.filter_by(
                source_type='operation', operation_id=op.id
            ).all()
            print(f"\n  RESUMEN {code}:")
            print(f"    Status      : {op.status}")
            print(f"    completed_at: {op.completed_at}")
            print(f"    Asiento     : {'id=' + str(entry_final.id) + ' fecha=' + str(entry_final.entry_date) if entry_final else 'NO'}")
            print(f"    Movimientos : {len(mvs_final)}")
            for mv in mvs_final:
                print(f"      {mv.bank_name} {mv.currency} {mv.amount:+.2f} {mv.movement_date.date()}")

        print("\n" + "=" * 60)
        print("FIX completado.")
        print("=" * 60)

if __name__ == '__main__':
    run()
