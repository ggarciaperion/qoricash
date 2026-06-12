"""
Script de reparación: inserta BankMovements para operaciones Completadas
que no tienen movimientos en la tabla bank_movements.

NO toca BankBalance (evita violaciones de constraint check_balance_usd_positive).
Solo inserta registros en bank_movements para que aparezcan en Tesorería.

Uso:
  python3 reparar_bank_movements.py              → modo DRY RUN (solo reporta)
  python3 reparar_bank_movements.py --apply      → aplica los cambios
  python3 reparar_bank_movements.py --apply --id EXP-551,EXP-549  → solo estas ops
"""

import os
import sys

DRY_RUN = '--apply' not in sys.argv

# IDs específicos opcionales: --id EXP-551,EXP-549
FILTER_IDS = []
if '--id' in sys.argv:
    idx = sys.argv.index('--id')
    if idx + 1 < len(sys.argv):
        FILTER_IDS = [x.strip() for x in sys.argv[idx + 1].split(',')]

os.environ.setdefault('FLASK_ENV', 'production')

from app import create_app
app = create_app()

with app.app_context():
    from app.extensions import db
    from app.models.operation import Operation
    from app.models.bank_movement import BankMovement
    from app.config.bank_accounts import QORICASH_ACCOUNTS
    from app.utils.formatters import now_peru

    # ── Tablas de lookup (igual que apply_operation) ───────────────────────
    _banco_accts = {}
    for _b, _monedas in QORICASH_ACCOUNTS.items():
        _banco_accts[_b] = {}
        for _m, _d in _monedas.items():
            _banco_accts[_b][_m] = f"{_b} {_m} ({_d['numero']})"

    _ALIASES = {
        'BCP': 'BCP', 'CREDITO': 'BCP', 'CRÉDITO': 'BCP',
        'INTERBANK': 'INTERBANK', 'IBK': 'INTERBANK',
        'BANBIF': 'BANBIF', 'BIF': 'BANBIF',
    }

    def _normalize(name):
        if not (name or '').strip():
            return ''
        u = name.upper()
        for alias, banco in _ALIASES.items():
            if alias in u:
                return banco
        return 'INTERBANK'

    # ── Crear BankMovement sin tocar BankBalance ───────────────────────────
    def _insert_movement(op, acct_name, usd_delta, pen_delta):
        """Inserta un BankMovement. No modifica BankBalance."""
        if not acct_name:
            return False
        parts = acct_name.split()
        if len(parts) < 2:
            return False
        bk  = parts[0]   # BCP | INTERBANK | BANBIF
        cur = parts[1]   # USD | PEN
        delta = usd_delta if cur == 'USD' else pen_delta
        if not delta:
            return False

        mv_type = (BankMovement.TYPE_OP_ENTRADA
                   if delta > 0 else BankMovement.TYPE_OP_SALIDA)
        try:
            client_name = (op.client.full_name or '—') if op.client else '—'
        except Exception:
            client_name = '—'

        mv_date = op.completed_at or now_peru()

        mv = BankMovement(
            movement_date  = mv_date,
            bank_name      = acct_name,
            bank_key       = bk,
            currency       = cur,
            amount         = round(delta, 2),
            movement_type  = mv_type,
            source_type    = 'operation',
            source_id      = op.id,
            operation_id   = op.id,
            description    = (f'{op.operation_type} — {op.operation_id}'
                              f' — {client_name}'),
            reference_code = op.operation_id,
            counterpart    = client_name,
            balance_after  = None,   # no calculamos saldo (BankBalance intacto)
            closure_date   = mv_date.date() if hasattr(mv_date, 'date') else mv_date,
        )
        db.session.add(mv)
        return True

    # ── Determinar banco para una operación ───────────────────────────────
    def _banco_para_op(op):
        """Devuelve (banco_origen, banco_destino) para la op."""
        payments = op.client_payments or []
        deposits = op.client_deposits or []

        def _from_deposits():
            for dep in deposits:
                for key in ('qc_bank', 'cuenta_cargo', 'banco'):
                    b = _normalize(dep.get(key, ''))
                    if b:
                        return b
            if op.source_account and op.client:
                for acct in (op.client.bank_accounts or []):
                    if acct.get('account_number') == op.source_account:
                        b = _normalize(acct.get('bank_name', ''))
                        if b:
                            return b
            if getattr(op, 'source_bank_name', None):
                b = _normalize(op.source_bank_name)
                if b:
                    return b
            return None

        def _from_payments():
            for pay in payments:
                for key in ('qc_bank', 'cuenta_destino', 'banco'):
                    b = _normalize(pay.get(key, ''))
                    if b:
                        return b
            if op.destination_account and op.client:
                for acct in (op.client.bank_accounts or []):
                    if acct.get('account_number') == op.destination_account:
                        b = _normalize(acct.get('bank_name', ''))
                        if b:
                            return b
            if getattr(op, 'destination_bank_name', None):
                b = _normalize(op.destination_bank_name)
                if b:
                    return b
            return _from_deposits()

        return _from_deposits(), _from_payments()

    # ── Buscar operaciones Completadas sin BankMovement ───────────────────
    query = Operation.query.filter_by(status='Completada')
    if FILTER_IDS:
        query = query.filter(Operation.operation_id.in_(FILTER_IDS))
    all_completed = query.all()

    ops_sin_movimiento = []
    for op in all_completed:
        count = BankMovement.query.filter_by(
            source_type='operation',
            operation_id=op.id
        ).count()
        if count == 0:
            ops_sin_movimiento.append(op)

    prefix = '[DRY RUN] ' if DRY_RUN else ''
    print(f"{prefix}Operaciones Completadas sin BankMovement: {len(ops_sin_movimiento)}")
    print()

    for op in ops_sin_movimiento:
        deposits = op.client_deposits or []
        payments = op.client_payments or []
        print(f"  {op.operation_id} — {op.operation_type} "
              f"USD {op.amount_usd} / PEN {op.amount_pen} — {op.completed_at}")
        for d in deposits:
            print(f"    dep:  qc_bank={d.get('qc_bank')!r}  "
                  f"cuenta_cargo={d.get('cuenta_cargo')!r}  importe={d.get('importe')}")
        for p in payments:
            print(f"    pago: qc_bank={p.get('qc_bank')!r}  "
                  f"cuenta_destino={p.get('cuenta_destino')!r}  importe={p.get('importe')}")

    if DRY_RUN:
        print()
        print("Modo DRY RUN — usa --apply para insertar los movimientos.")
        sys.exit(0)

    # ── Aplicar ────────────────────────────────────────────────────────────
    print()
    print("Insertando BankMovements (sin tocar BankBalance)...")
    ok = 0
    fail = 0

    for op in ops_sin_movimiento:
        try:
            usd = float(op.amount_usd)
            pen = float(op.amount_pen)
            deposits  = op.client_payments or []   # para normalizar
            _payments = op.client_payments or []
            _deposits = op.client_deposits or []
            _has_dep_banks = any(d.get('qc_bank') for d in _deposits)
            _has_pay_banks = any(p.get('qc_bank') for p in _payments)

            banco_orig, banco_dest = _banco_para_op(op)
            inserted = 0

            if op.operation_type == 'Compra':
                # USD entra: por depósito(s) del cliente
                if _has_dep_banks:
                    for dep in _deposits:
                        b = _normalize(dep.get('qc_bank', '')) or _normalize(dep.get('cuenta_cargo', ''))
                        amt = float(dep.get('importe', 0))
                        if b and amt > 0:
                            acct = _banco_accts.get(b, {}).get('USD')
                            if _insert_movement(op, acct, +amt, 0.0):
                                inserted += 1
                else:
                    if banco_orig:
                        acct = _banco_accts.get(banco_orig, {}).get('USD')
                        if _insert_movement(op, acct, +usd, 0.0):
                            inserted += 1

                # PEN sale: por pago(s) a cliente
                if _has_pay_banks:
                    for pay in _payments:
                        b = _normalize(pay.get('qc_bank', '')) or _normalize(pay.get('cuenta_destino', ''))
                        amt = float(pay.get('importe', 0))
                        if b and amt > 0:
                            acct = _banco_accts.get(b, {}).get('PEN')
                            if _insert_movement(op, acct, 0.0, -amt):
                                inserted += 1
                else:
                    if banco_dest:
                        acct = _banco_accts.get(banco_dest, {}).get('PEN')
                        if _insert_movement(op, acct, 0.0, -pen):
                            inserted += 1

            else:  # Venta
                # PEN entra: por depósito(s) del cliente
                if _has_dep_banks:
                    for dep in _deposits:
                        b = _normalize(dep.get('qc_bank', '')) or _normalize(dep.get('cuenta_cargo', ''))
                        amt = float(dep.get('importe', 0))
                        if b and amt > 0:
                            acct = _banco_accts.get(b, {}).get('PEN')
                            if _insert_movement(op, acct, 0.0, +amt):
                                inserted += 1
                else:
                    if banco_orig:
                        acct = _banco_accts.get(banco_orig, {}).get('PEN')
                        if _insert_movement(op, acct, 0.0, +pen):
                            inserted += 1

                # USD sale: por pago(s) a cliente
                if _has_pay_banks:
                    for pay in _payments:
                        b = _normalize(pay.get('qc_bank', '')) or _normalize(pay.get('cuenta_destino', ''))
                        amt = float(pay.get('importe', 0))
                        if b and amt > 0:
                            acct = _banco_accts.get(b, {}).get('USD')
                            if _insert_movement(op, acct, -amt, 0.0):
                                inserted += 1
                else:
                    if banco_dest:
                        acct = _banco_accts.get(banco_dest, {}).get('USD')
                        if _insert_movement(op, acct, -usd, 0.0):
                            inserted += 1

            if inserted == 0:
                print(f"  ? {op.operation_id}: no se pudo determinar banco "
                      f"(banco_orig={banco_orig!r} banco_dest={banco_dest!r})")
                fail += 1
                continue

            db.session.commit()
            print(f"  + {op.operation_id}: {inserted} movimiento(s) insertado(s)")
            ok += 1

        except Exception as e:
            fail += 1
            print(f"  x {op.operation_id}: {e}")
            try:
                db.session.rollback()
            except Exception:
                pass

    print()
    print(f"Resultado: {ok} operaciones reparadas, {fail} con error o banco no determinado")
