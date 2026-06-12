"""
Repara gastos (ExpenseRecord) que no tienen BankMovement.

Cubre tres casos:
  CASO A — bank_account_code presente en el ExpenseRecord
            (nuevo_gasto registrado antes del fix fcfa49b8).
  CASO B — bank_account_code NULL pero el JournalEntry tiene línea HABER en
            cuenta 104x (pago_cuota registrado antes del fix fcfa49b8).
  CASO C — categoría bancaria (6411 ITF, 6791) sin bank_account_code ni 104x en
            el asiento (registrado con banco vacío por error en el formulario).
            Requiere --banco-itf=XXXX para indicar la cuenta (ej. 1041 = BCP PEN).

Uso:
  python3 reparar_gastos_sin_movimiento.py                        -> DRY RUN
  python3 reparar_gastos_sin_movimiento.py --apply                -> aplica A+B
  python3 reparar_gastos_sin_movimiento.py --banco-itf=1041       -> DRY RUN + lista caso C
  python3 reparar_gastos_sin_movimiento.py --apply --banco-itf=1041 -> aplica A+B+C
"""
import os
import sys

DRY_RUN = '--apply' not in sys.argv

# Cuenta bancaria para caso C (6411/6791 sin banco): ej. --banco-itf=1041
_banco_itf_arg = next((a.split('=',1)[1] for a in sys.argv if a.startswith('--banco-itf=')), None)
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
    _BANK_ACCOUNTS = set(_CODE_TO_BANK.keys())  # cuentas 104x reconocidas

    # ── Recopilar todos los ExpenseRecord sin BankMovement ────────────────────

    # IDs de gastos que YA tienen BankMovement
    existing_ids = {
        row[0] for row in db.session.query(BankMovement.source_id).filter(
            BankMovement.source_type == 'expense',
            BankMovement.source_id.isnot(None),
        ).distinct().all()
    }

    todos_gastos = ExpenseRecord.query.all()

    # Caso A: bank_account_code presente → podemos leer la cuenta directo
    caso_a = []
    for g in todos_gastos:
        if g.id in existing_ids:
            continue
        if g.bank_account_code and g.bank_account_code in _BANK_ACCOUNTS:
            caso_a.append((g, g.bank_account_code))

    # Caso B: bank_account_code NULL → buscar línea HABER en 104x del JournalEntry
    caso_b = []
    caso_b_ids = set()
    for g in todos_gastos:
        if g.id in existing_ids:
            continue
        if g.bank_account_code:
            continue   # ya cubierto por caso A
        if not g.journal_entry_id:
            continue
        # Buscar la línea HABER en cuenta bancaria dentro del asiento
        from sqlalchemy import text
        row = db.session.execute(text("""
            SELECT account_code, haber
            FROM journal_entry_lines
            WHERE journal_entry_id = :je_id
              AND account_code = ANY(:codes)
              AND haber > 0
            ORDER BY id
            LIMIT 1
        """), {'je_id': g.journal_entry_id, 'codes': list(_BANK_ACCOUNTS)}).fetchone()
        if row:
            caso_b.append((g, row[0]))  # (ExpenseRecord, account_code)
            caso_b_ids.add(g.id)

    # Caso C: categoría bancaria (6411 ITF / 6791) sin bank_account_code ni 104x
    #         Registrado con banco vacío desde el formulario. Requiere --banco-itf=XXXX.
    _BANK_CATS = {'6411', '6791'}
    caso_c = []
    for g in todos_gastos:
        if g.id in existing_ids:
            continue
        if g.bank_account_code:
            continue
        if g.id in caso_b_ids:
            continue
        if g.category not in _BANK_CATS:
            continue
        caso_c.append(g)

    pendientes = caso_a + caso_b

    prefix = '[DRY RUN] ' if DRY_RUN else ''
    print(f"{prefix}Gastos sin BankMovement: {len(pendientes)} "
          f"(caso A={len(caso_a)}, caso B={len(caso_b)})\n")

    for g, acct in pendientes:
        tag = 'A' if g.bank_account_code else 'B'
        print(f"  [{tag}] ID={g.id}  {g.expense_date}  {g.description}  "
              f"S/{g.amount_pen}  cuenta={acct}")

    # Caso C: listar siempre, procesar solo si --banco-itf fue provisto
    if caso_c:
        print(f"\n{'[DRY RUN] ' if DRY_RUN else ''}Caso C — gastos ITF/bancarios sin banco asignado: {len(caso_c)}")
        for g in caso_c:
            print(f"  [C] ID={g.id}  {g.expense_date}  {g.description}  S/{g.amount_pen}  cat={g.category}")
        if _banco_itf_arg:
            print(f"  → Se usará cuenta={_banco_itf_arg} para reparar estos gastos")
        else:
            print("  → Para reparar estos, agrega: --banco-itf=XXXX (ej. --banco-itf=1041 para BCP PEN)")

    if _banco_itf_arg and _banco_itf_arg in _BANK_ACCOUNTS:
        for g in caso_c:
            pendientes.append((g, _banco_itf_arg))

    if DRY_RUN:
        print("\nModo DRY RUN — usa --apply para crear los movimientos.")
        sys.exit(0)

    print("\nCreando BankMovements...\n")
    ok = 0
    fail = 0

    for g, account_code in pendientes:
        try:
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

            # Actualizar BankBalance según caso:
            #   Caso A (bank_account_code presente): saldo ya fue debitado por código antiguo
            #           si bb existía. No volvemos a debitar — solo leemos bal_after.
            #   Caso B (pago_cuota pre-fix):         saldo NUNCA fue debitado. Debitar ahora.
            #   Caso C (6411/6791 sin banco):        asiento fue contra 4699, BankBalance
            #           NUNCA fue tocado. Debitar ahora.
            is_caso_b = (g.bank_account_code is None and g.id in caso_b_ids)
            is_caso_c = (g.bank_account_code is None and g.id not in caso_b_ids)
            bal_after = None
            if bb is not None:
                if is_caso_b or is_caso_c:
                    # BankBalance nunca fue debitado → debitar ahora
                    if currency == 'PEN':
                        bb.balance_pen = round(max(float(bb.balance_pen) - amount_cur, 0.0), 2)
                        bal_after = float(bb.balance_pen)
                    else:
                        bb.balance_usd = round(max(float(bb.balance_usd) - amount_cur, 0.0), 2)
                        bal_after = float(bb.balance_usd)
                    bb.updated_at = now_peru()
                else:
                    # Caso A: ya debitado, solo leer saldo actual
                    bal_after = float(bb.balance_pen if currency == 'PEN' else bb.balance_usd)

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
            if g.bank_account_code:
                tag = 'A'
            elif g.id in caso_b_ids:
                tag = 'B'
            else:
                tag = 'C'
            print(f"  + [{tag}] ID={g.id}: BankMovement creado ({bank_key} {currency} -{amount_cur})")
            ok += 1

        except Exception as e:
            fail += 1
            print(f"  x ID={g.id}: {e}")
            try:
                db.session.rollback()
            except Exception:
                pass

    print(f"\nResultado: {ok} reparados, {fail} con error")
