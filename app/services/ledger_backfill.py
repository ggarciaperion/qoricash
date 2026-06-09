"""
LedgerBackfill — Reconstrucción histórica del ledger BankMovement
=================================================================
Genera registros BankMovement para todas las operaciones completadas
que aún no tienen entradas en el ledger.

Seguridad:
  - Idempotente: salta operaciones que ya tienen BankMovements.
  - Modo dry_run: reporta qué haría sin escribir nada.
  - No modifica BankBalance (los saldos ya están correctos).
  - Recalcula balance_after en todo el ledger al finalizar.

Uso CLI:
  flask backfill-ledger           # dry-run por defecto
  flask backfill-ledger --apply   # ejecuta el backfill real

Uso API:
  POST /finanzas/api/ledger/backfill        body: {"dry_run": true}
  POST /finanzas/api/ledger/backfill        body: {"dry_run": false, "recalc_balance_after": true}
"""
import logging
from datetime import datetime

_log = logging.getLogger(__name__)

# Mapa alias nombre banco → clave canónica
_ALIASES = {
    'BCP':      'BCP', 'CREDITO': 'BCP', 'CRÉDITO': 'BCP',
    'INTERBANK':'INTERBANK', 'IBK': 'INTERBANK',
    'BANBIF':   'BANBIF', 'BIF':   'BANBIF',
}


def _normalize_banco(name: str) -> str:
    """'Banco de Crédito BCP …' → 'BCP'.  Retorna '' si no reconoce."""
    if not (name or '').strip():
        return ''
    u = name.upper()
    for alias, banco in _ALIASES.items():
        if alias in u:
            return banco
    return 'INTERBANK'  # fallback igual que apply_operation


def _banco_acct_name(banco_key: str, currency: str) -> str:
    """Retorna el bank_name canónico, p.ej. 'BCP USD (1917357790119)'."""
    try:
        from app.config.bank_accounts import QORICASH_ACCOUNTS
        numero = QORICASH_ACCOUNTS.get(banco_key, {}).get(currency, {}).get('numero', '')
        if numero:
            return f"{banco_key} {currency} ({numero})"
    except Exception:
        pass
    return f"{banco_key} {currency}"


def _resolve_movements(operation) -> list:
    """
    Determina qué BankMovement crear para una operación completada.

    Replica la lógica de BankBalance.apply_operation() pero sólo
    devuelve una lista de specs — no escribe nada.

    Cada spec: {
        'acct_name':  str,   # 'BCP USD (…)'
        'bank_key':   str,   # 'BCP'
        'currency':   str,   # 'USD'
        'delta':      float, # positivo=entrada, negativo=salida
    }
    """
    specs = []
    usd   = float(operation.amount_usd or 0)
    pen   = float(operation.amount_pen or 0)

    _payments = operation.client_payments or []
    _deposits = operation.client_deposits or []
    _has_pay_banks = any(p.get('qc_bank') for p in _payments)
    _has_dep_banks = any(d.get('qc_bank') for d in _deposits)

    def _fallback_banco():
        """Banco desde la cuenta origen del cliente."""
        try:
            if operation.source_account and operation.client:
                for acct in (operation.client.bank_accounts or []):
                    if acct.get('account_number') == operation.source_account:
                        return _normalize_banco(acct.get('bank_name', ''))
        except Exception:
            pass
        return _normalize_banco(getattr(operation, 'source_bank_name', '') or '')

    def _fallback_banco_dest():
        """Banco desde la cuenta destino del cliente."""
        try:
            if operation.destination_account and operation.client:
                for acct in (operation.client.bank_accounts or []):
                    if acct.get('account_number') == operation.destination_account:
                        return _normalize_banco(acct.get('bank_name', ''))
        except Exception:
            pass
        b = _normalize_banco(getattr(operation, 'destination_bank_name', '') or '')
        return b or _fallback_banco()

    def _add(banco_key, currency, delta):
        if not banco_key or not delta:
            return
        specs.append({
            'acct_name': _banco_acct_name(banco_key, currency),
            'bank_key':  banco_key,
            'currency':  currency,
            'delta':     round(delta, 2),
        })

    if operation.operation_type == 'Compra':
        # USD entra a QoriCash (depósitos del cliente)
        if _has_dep_banks:
            _ua = 0.0
            for dep in _deposits:
                _b = (_normalize_banco(dep.get('qc_bank', ''))
                      or _normalize_banco(dep.get('cuenta_cargo', '')))
                _amt = float(dep.get('importe', 0))
                if _b and _amt > 0:
                    _add(_b, 'USD', +_amt)
                    _ua += _amt
            if _ua == 0 and usd > 0:
                _add(_fallback_banco(), 'USD', +usd)
        else:
            _add(_fallback_banco(), 'USD', +usd)

        # PEN sale de QoriCash (pagos al cliente)
        if _has_pay_banks:
            _pa = 0.0
            for pay in _payments:
                _b = (_normalize_banco(pay.get('qc_bank', ''))
                      or _normalize_banco(pay.get('cuenta_destino', '')))
                _amt = float(pay.get('importe', 0))
                if _b and _amt > 0:
                    _add(_b, 'PEN', -_amt)
                    _pa += _amt
            if _pa == 0 and pen > 0:
                _add(_fallback_banco_dest(), 'PEN', -pen)
        else:
            _add(_fallback_banco_dest(), 'PEN', -pen)

    else:  # Venta
        # PEN entra a QoriCash (depósitos del cliente)
        if _has_dep_banks:
            _pa = 0.0
            for dep in _deposits:
                _b = (_normalize_banco(dep.get('qc_bank', ''))
                      or _normalize_banco(dep.get('cuenta_cargo', '')))
                _amt = float(dep.get('importe', 0))
                if _b and _amt > 0:
                    _add(_b, 'PEN', +_amt)
                    _pa += _amt
            if _pa == 0 and pen > 0:
                _add(_fallback_banco(), 'PEN', +pen)
        else:
            _add(_fallback_banco(), 'PEN', +pen)

        # USD sale de QoriCash (pagos al cliente)
        if _has_pay_banks:
            _ua = 0.0
            for pay in _payments:
                _b = (_normalize_banco(pay.get('qc_bank', ''))
                      or _normalize_banco(pay.get('cuenta_destino', '')))
                _amt = float(pay.get('importe', 0))
                if _b and _amt > 0:
                    _add(_b, 'USD', -_amt)
                    _ua += _amt
            if _ua == 0 and usd > 0:
                _add(_fallback_banco_dest(), 'USD', -usd)
        else:
            _add(_fallback_banco_dest(), 'USD', -usd)

    return specs


def recalc_balance_after() -> dict:
    """
    Recalcula balance_after para TODOS los BankMovement en orden cronológico,
    por cada par (bank_key, currency).

    Retorna: {updated: int, pairs: int}
    """
    from app.extensions import db
    from app.models.bank_movement import BankMovement

    pairs = db.session.query(
        BankMovement.bank_key, BankMovement.currency
    ).distinct().all()

    total_updated = 0

    for bank_key, currency in pairs:
        rows = BankMovement.query.filter_by(
            bank_key=bank_key, currency=currency
        ).order_by(
            BankMovement.movement_date.asc(), BankMovement.id.asc()
        ).all()

        running = 0.0
        for mv in rows:
            running = round(running + float(mv.amount), 2)
            mv.balance_after = running
            total_updated += 1

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        _log.error(f'[LedgerBackfill] recalc_balance_after commit error: {exc}')
        raise

    return {'updated': total_updated, 'pairs': len(pairs)}


def run_backfill(dry_run: bool = True,
                 recalc: bool = True,
                 user_id: int = None) -> dict:
    """
    Backfill principal.

    Args:
        dry_run:  Si True, no escribe nada — sólo reporta.
        recalc:   Si True (y dry_run=False), recalcula balance_after al final.
        user_id:  ID del usuario que lanza el backfill (para created_by).

    Returns: {
        dry_run, ops_total, ops_skipped, ops_processed, ops_no_bank,
        movements_created, recalc_result, errors
    }
    """
    from app.extensions import db
    from app.models.operation import Operation
    from app.models.bank_movement import BankMovement
    from app.utils.formatters import now_peru

    ops_all      = Operation.query.filter_by(status='Completada').order_by(
        Operation.completed_at.asc()
    ).all()

    # Operaciones que YA tienen BankMovements en el ledger
    existing_op_ids = set(
        row[0] for row in db.session.query(BankMovement.operation_id).filter(
            BankMovement.operation_id.isnot(None)
        ).distinct().all()
    )

    ops_skipped   = 0
    ops_processed = 0
    ops_no_bank   = 0
    movements_created = 0
    errors        = []
    dry_run_preview = []  # para dry_run

    for op in ops_all:
        if op.id in existing_op_ids:
            ops_skipped += 1
            continue

        try:
            specs = _resolve_movements(op)
        except Exception as exc:
            errors.append(f'op {op.operation_id}: resolve error — {exc}')
            continue

        if not specs:
            ops_no_bank += 1
            _log.warning(f'[LedgerBackfill] op {op.operation_id}: sin banco determinable, omitida')
            continue

        # Preparar client_name
        client_name = '—'
        try:
            client_name = (op.client.full_name or '—') if op.client else '—'
        except Exception:
            pass

        movement_dt = op.completed_at or now_peru()
        closure_dt  = movement_dt.date() if isinstance(movement_dt, datetime) else movement_dt

        if dry_run:
            for s in specs:
                dry_run_preview.append({
                    'op':         op.operation_id,
                    'client':     client_name,
                    'fecha':      movement_dt.isoformat() if movement_dt else None,
                    'acct_name':  s['acct_name'],
                    'currency':   s['currency'],
                    'delta':      s['delta'],
                    'mv_type':    'op_entrada' if s['delta'] > 0 else 'op_salida',
                })
            ops_processed += 1
            movements_created += len(specs)
            continue

        # Escribir
        try:
            for s in specs:
                mv_type = (BankMovement.TYPE_OP_ENTRADA
                           if s['delta'] > 0 else BankMovement.TYPE_OP_SALIDA)
                mv = BankMovement(
                    movement_date  = movement_dt,
                    bank_name      = s['acct_name'],
                    bank_key       = s['bank_key'],
                    currency       = s['currency'],
                    amount         = s['delta'],
                    movement_type  = mv_type,
                    source_type    = 'operation',
                    source_id      = op.id,
                    operation_id   = op.id,
                    description    = (f'{op.operation_type} — {op.operation_id}'
                                      f' — {client_name} [backfill]'),
                    reference_code = op.operation_id,
                    counterpart    = client_name,
                    balance_after  = None,  # recalculado al final
                    closure_date   = closure_dt,
                    created_by     = user_id,
                    is_validated   = True,  # histórico = ya ocurrió
                )
                db.session.add(mv)
                movements_created += 1

            ops_processed += 1

        except Exception as exc:
            db.session.rollback()
            errors.append(f'op {op.operation_id}: write error — {exc}')
            continue

    if not dry_run:
        try:
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            errors.append(f'commit final: {exc}')

    recalc_result = None
    if not dry_run and recalc and not errors:
        try:
            recalc_result = recalc_balance_after()
        except Exception as exc:
            errors.append(f'recalc_balance_after: {exc}')

    result = {
        'dry_run':          dry_run,
        'ops_total':        len(ops_all),
        'ops_skipped':      ops_skipped,
        'ops_processed':    ops_processed,
        'ops_no_bank':      ops_no_bank,
        'movements_created':movements_created,
        'recalc_result':    recalc_result,
        'errors':           errors,
    }

    if dry_run:
        result['preview'] = dry_run_preview

    _log.info(f'[LedgerBackfill] dry_run={dry_run} processed={ops_processed} '
              f'created={movements_created} skipped={ops_skipped} errors={len(errors)}')

    return result
