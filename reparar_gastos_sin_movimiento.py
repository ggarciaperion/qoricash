"""
Repara gastos (ExpenseRecord con bank_account_code) que no tienen BankMovement.
Casos típicos: ITF en soles registrados antes del fix fcfa49b8 (Jun 11 18:40).

Uso:
  python3 reparar_gastos_sin_movimiento.py           -> DRY RUN
  python3 reparar_gastos_sin_movimiento.py --apply   -> aplica
"""
import os
import sys

DRY_RUN = '--apply' not in sys.argv
os.environ.setdefault('FLASK_ENV', 'production')

from app import create_app
app = create_app()

with app.app_context():
    from decimal import Decimal
    from app.extensions import db
    from app.models.expense_record import ExpenseRecord
    from app.models.bank_movement import BankMovement
    from app.models.bank_balance import BankBalance
    from app.models.exchange_rate import ExchangeRate
    from app.utils.formatters import now_peru

    # Mismos mapeos que contabilidad.py
    _ACCOUNT_LABELS = {
        '1011': ('Caja MN',       'PEN', 'efectivo'),
        '1012': ('Caja ME',       'USD', 'efectivo'),
        '1041': ('BCP PEN',       'PEN', 'banco'),
        '1044': ('BCP USD',       'USD', 'banco'),
        '1047': ('Interbank USD', 'USD', 'banco'),
        '1048': ('Interbank PEN', 'PEN', 'banco'),
        '1049': ('BanBif PEN',    'PEN', 'banco'),
        '1050': ('BanBif USD',    'USD', 'banco'),
        '1051': ('Pichincha PEN', 'PEN', 'banco'),
        '1052': ('Pichincha USD', 'USD', 'banco'),
    }
    _CODE_TO_BANK = {
        '1041': 'BCP',       '1044': 'BCP',
        '1047': 'INTERBANK', '1048': 'INTERBANK',
        '1049': 'BANBIF',    '1050': 'BANBIF',
        '1051': 'PICHINCHA', '1052': 'PICHINCHA',
    }

    # Gastos con cuenta bancaria pero sin BankMovement de tipo 'gasto'
    gastos = ExpenseRecord.query.filter(
        ExpenseRecord.bank_account_code.isnot(None)
    ).all()

    pendientes = []
    for g in gastos:
        count = BankMovement.query.filter_by(
            source_type='expense',
            source_id=g.id
        ).count()
        if count == 0:
            pendientes.append(g)

    prefix = '[DRY RUN] ' if DRY_RUN else ''
    print(f"{prefix}Gastos con cuenta bancaria sin BankMovement: {len(pendientes)}\n")

    for g in pendientes:
        print(f"  ID={g.id}  {g.expense_date}  {g.description}  "
              f"S/{g.amount_pen}  cuenta={g.bank_account_code}")

    if DRY_RUN:
        print("\nModo DRY RUN — usa --apply para crear los movimientos.")
        sys.exit(0)

    print("\nCreando BankMovements...\n")
    ok = 0
    fail = 0

    for g in pendientes:
        try:
            account_code = g.bank_account_code
            currency = _ACCOUNT_LABELS.get(account_code, ('', 'PEN', ''))[1]
            bank_key = _CODE_TO_BANK.get(account_code)
            if not bank_key:
                print(f"  ? ID={g.id}: cuenta {account_code} no reconocida — OMITIDO")
                fail += 1
                continue

            amount_pen = float(g.amount_pen or 0)

            if currency == 'PEN':
                amount_cur = amount_pen
            else:
                er = ExchangeRate.query.order_by(ExchangeRate.updated_at.desc()).first()
                tc = float(er.sell_rate) if er and er.sell_rate else 3.75
                amount_cur = round(amount_pen / tc, 2)

            bb = BankBalance.query.filter(
                BankBalance.bank_name.ilike(f'%{bank_key}%{currency}%')
            ).first()

            bank_name_mv = bb.bank_name if bb else f'{bank_key} {currency}'
            mv_date = g.expense_date if g.expense_date else now_peru()

            # Actualizar BankBalance si existe
            bal_after = None
            if bb is not None:
                if currency == 'PEN':
                    bb.balance_pen = round(max(float(bb.balance_pen) - amount_cur, 0.0), 2)
                    bal_after = float(bb.balance_pen)
                else:
                    bb.balance_usd = round(max(float(bb.balance_usd) - amount_cur, 0.0), 2)
                    bal_after = float(bb.balance_usd)
                bb.updated_at = now_peru()

            mv = BankMovement(
                movement_date  = mv_date,
                bank_name      = bank_name_mv,
                bank_key       = bank_key,
                currency       = currency,
                amount         = round(-amount_cur, 2),
                movement_type  = BankMovement.TYPE_GASTO,
                source_type    = 'expense',
                source_id      = g.id,
                description    = g.description or f'Gasto {bank_key} {currency}',
                reference_code = str(g.id),
                balance_after  = round(bal_after, 2) if bal_after is not None else None,
                closure_date   = mv_date if hasattr(mv_date, 'date') else mv_date,
                created_by     = g.created_by,
            )
            db.session.add(mv)
            db.session.commit()
            print(f"  + ID={g.id}: BankMovement creado ({bank_key} {currency} -{amount_cur})")
            ok += 1

        except Exception as e:
            fail += 1
            print(f"  x ID={g.id}: {e}")
            try:
                db.session.rollback()
            except Exception:
                pass

    print(f"\nResultado: {ok} reparados, {fail} con error")
