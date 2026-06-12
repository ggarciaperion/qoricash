"""
Finanzas Blueprint — Control Financiero Unificado V2
=====================================================
Vista única que responde las preguntas clave de la operación diaria.

Rutas HTML:
  /finanzas/              — Control Financiero (dashboard principal)
  /finanzas/auditoria/    — Auditoría, cierres, movimientos, reconciliación

APIs (todas consumen FinanceEngine — fuente única de verdad):
  GET  /finanzas/api/snapshot         — snapshot completo
  GET  /finanzas/api/posicion         — posición abierta detallada
  GET  /finanzas/api/movimientos      — movimientos bancarios con filtros
  GET  /finanzas/api/amarres          — amarres con filtros
  GET  /finanzas/api/reconciliacion   — comparación BankBalance vs ledger
  POST /finanzas/api/ledger/activar   — registrar saldos de apertura
  POST /finanzas/api/ledger/backfill  — reconstruir ledger histórico desde operaciones
  POST /finanzas/api/cierre/calcular  — calcular cierre del día
  POST /finanzas/api/cierre/validar   — guardar saldos reales
  POST /finanzas/api/cierre/confirmar — confirmar cierre
  GET  /finanzas/api/cierre/<fecha>   — obtener cierre por fecha
  GET  /finanzas/api/cierre/historial — historial de cierres
"""
import logging
from datetime import date, datetime, timedelta

from flask import Blueprint, render_template, jsonify, request, abort
from flask_login import login_required, current_user
from sqlalchemy import func

from app.extensions import db, csrf
from app.services.finance_engine import FinanceEngine
from app.utils.formatters import now_peru

_log = logging.getLogger(__name__)

finanzas_bp = Blueprint('finanzas', __name__)

ALLOWED_ROLES = ('Master', 'Presidente de Negocios')


def _require_role():
    if current_user.role not in ALLOWED_ROLES:
        abort(403)


# ── Vistas HTML ───────────────────────────────────────────────────────────────

@finanzas_bp.route('/')
@login_required
def control():
    _require_role()
    return render_template('finanzas/control.html')


@finanzas_bp.route('/auditoria/')
@login_required
def auditoria():
    _require_role()
    from flask import redirect, url_for
    return redirect(url_for('finanzas.control'))


# ── API: Snapshot ─────────────────────────────────────────────────────────────

@finanzas_bp.route('/api/snapshot')
@login_required
def api_snapshot():
    _require_role()
    try:
        data = FinanceEngine.get_full_snapshot()
        return jsonify(data)
    except Exception as exc:
        _log.exception('[Finanzas] api_snapshot')
        return jsonify({'ok': False, 'error': str(exc)}), 500


# ── API: Posición detallada ───────────────────────────────────────────────────

@finanzas_bp.route('/api/posicion')
@login_required
def api_posicion():
    _require_role()
    try:
        pos = FinanceEngine.get_open_position()
        return jsonify({'ok': True, **pos})
    except Exception as exc:
        _log.exception('[Finanzas] api_posicion')
        return jsonify({'ok': False, 'error': str(exc)}), 500


# ── API: Movimientos bancarios ────────────────────────────────────────────────

@finanzas_bp.route('/api/movimientos')
@login_required
def api_movimientos():
    _require_role()
    try:
        from app.models import BankMovement

        fecha_ini = request.args.get('fecha_ini')
        fecha_fin = request.args.get('fecha_fin')
        banco     = request.args.get('banco')
        moneda    = request.args.get('moneda')
        tipo      = request.args.get('tipo')
        page      = int(request.args.get('page', 1))
        per_page  = int(request.args.get('per_page', 50))

        q = BankMovement.query

        if fecha_ini:
            fi = datetime.combine(date.fromisoformat(fecha_ini), datetime.min.time())
            q  = q.filter(BankMovement.movement_date >= fi)
        if fecha_fin:
            ff = datetime.combine(date.fromisoformat(fecha_fin), datetime.max.time())
            q  = q.filter(BankMovement.movement_date <= ff)
        if banco:
            q = q.filter(BankMovement.bank_key == banco)
        if moneda:
            q = q.filter(BankMovement.currency == moneda)
        if tipo:
            q = q.filter(BankMovement.movement_type == tipo)

        total = q.count()
        movs  = q.order_by(BankMovement.movement_date.desc()).offset(
            (page - 1) * per_page
        ).limit(per_page).all()

        net = q.with_entities(func.sum(BankMovement.amount)).scalar() or 0

        return jsonify({
            'ok':          True,
            'total':       total,
            'page':        page,
            'per_page':    per_page,
            'pages':       (total + per_page - 1) // per_page,
            'net_amount':  round(float(net), 2),
            'movimientos': [m.to_dict() for m in movs],
        })
    except Exception as exc:
        _log.exception('[Finanzas] api_movimientos')
        return jsonify({'ok': False, 'error': str(exc)}), 500


# ── API: Amarres ──────────────────────────────────────────────────────────────

@finanzas_bp.route('/api/amarres')
@login_required
def api_amarres():
    _require_role()
    try:
        from app.models import AccountingMatch

        fecha_ini = request.args.get('fecha_ini')
        fecha_fin = request.args.get('fecha_fin')
        status    = request.args.get('status', 'Activo')
        page      = int(request.args.get('page', 1))
        per_page  = int(request.args.get('per_page', 50))

        q = AccountingMatch.query
        if status:
            q = q.filter(AccountingMatch.status == status)
        if fecha_ini:
            fi = datetime.combine(date.fromisoformat(fecha_ini), datetime.min.time())
            q  = q.filter(AccountingMatch.created_at >= fi)
        if fecha_fin:
            ff = datetime.combine(date.fromisoformat(fecha_fin), datetime.max.time())
            q  = q.filter(AccountingMatch.created_at <= ff)

        total   = q.count()
        matches = q.order_by(AccountingMatch.created_at.desc()).offset(
            (page - 1) * per_page
        ).limit(per_page).all()

        totales = q.with_entities(
            func.sum(AccountingMatch.profit_pen),
            func.sum(AccountingMatch.house_profit_pen),
            func.sum(AccountingMatch.matched_amount_usd),
        ).one()

        items = []
        for m in matches:
            buy_op  = m.buy_operation
            sell_op = m.sell_operation
            items.append({
                'id':               m.id,
                'created_at':       m.created_at.isoformat() if m.created_at else None,
                'status':           m.status,
                'match_type':       m.match_type,
                'matched_usd':      float(m.matched_amount_usd or 0),
                'buy_op_id':        buy_op.operation_id  if buy_op  else None,
                'sell_op_id':       sell_op.operation_id if sell_op else None,
                'buy_client':       buy_op.client.full_name  if buy_op  and buy_op.client  else '—',
                'sell_client':      sell_op.client.full_name if sell_op and sell_op.client else '—',
                'buy_tc':           float(m.buy_exchange_rate  or 0),
                'sell_tc':          float(m.sell_exchange_rate or 0),
                'profit_pen':       float(m.profit_pen         or 0),
                'house_pen':        float(m.house_profit_pen   or 0),
                'trader_buy_pen':   float(m.trader_buy_profit_pen  or 0),
                'trader_sell_pen':  float(m.trader_sell_profit_pen or 0),
            })

        return jsonify({
            'ok':       True,
            'total':    total,
            'page':     page,
            'per_page': per_page,
            'pages':    (total + per_page - 1) // per_page,
            'totales': {
                'profit_pen':   round(float(totales[0] or 0), 2),
                'house_pen':    round(float(totales[1] or 0), 2),
                'matched_usd':  round(float(totales[2] or 0), 2),
            },
            'items': items,
        })
    except Exception as exc:
        _log.exception('[Finanzas] api_amarres')
        return jsonify({'ok': False, 'error': str(exc)}), 500


# ── API: Reconciliación ───────────────────────────────────────────────────────

@finanzas_bp.route('/api/reconciliacion')
@login_required
def api_reconciliacion():
    _require_role()
    try:
        resultados    = FinanceEngine.get_reconciliation()
        incoherentes  = [r for r in resultados if not r['coherent']]
        sin_ledger    = [r for r in resultados if r['ledger_empty']]
        return jsonify({
            'ok':             True,
            'resultados':     resultados,
            'incoherentes':   incoherentes,
            'sin_ledger':     sin_ledger,
            'todo_coherente': len(incoherentes) == 0,
            'ledger_activo':  len(sin_ledger)   == 0,
        })
    except Exception as exc:
        _log.exception('[Finanzas] api_reconciliacion')
        return jsonify({'ok': False, 'error': str(exc)}), 500


# ── API: Activar ledger ───────────────────────────────────────────────────────

@finanzas_bp.route('/api/ledger/activar', methods=['POST'])
@csrf.exempt
@login_required
def api_ledger_activar():
    _require_role()
    try:
        result = FinanceEngine.activar_ledger(current_user.id)
        return jsonify({'ok': True, **result})
    except Exception as exc:
        _log.exception('[Finanzas] api_ledger_activar')
        return jsonify({'ok': False, 'error': str(exc)}), 500


# ── API: Backfill histórico del ledger ────────────────────────────────────────

@finanzas_bp.route('/api/ledger/backfill', methods=['POST'])
@csrf.exempt
@login_required
def api_ledger_backfill():
    """
    Reconstruye el ledger BankMovement a partir de operaciones históricas.

    Body JSON:
      dry_run   (bool, default true)  — si true, sólo reporta sin escribir
      recalc    (bool, default true)  — recalcula balance_after al finalizar
    """
    _require_role()
    try:
        from app.services.ledger_backfill import run_backfill
        data    = request.get_json() or {}
        dry_run = data.get('dry_run', True)
        recalc  = data.get('recalc', True)
        result  = run_backfill(dry_run=dry_run, recalc=recalc,
                               user_id=current_user.id)
        return jsonify({'ok': True, **result})
    except Exception as exc:
        _log.exception('[Finanzas] api_ledger_backfill')
        return jsonify({'ok': False, 'error': str(exc)}), 500


# ── API: Cierre — Calcular ────────────────────────────────────────────────────

@finanzas_bp.route('/api/cierre/calcular', methods=['POST'])
@csrf.exempt
@login_required
def api_cierre_calcular():
    _require_role()
    try:
        from app.models import DailyClosure, Operation, AccountingMatch, AccountingBatch

        data      = request.get_json() or {}
        fecha_str = data.get('fecha', date.today().isoformat())
        fecha     = date.fromisoformat(fecha_str)
        start     = datetime.combine(fecha, datetime.min.time())
        end       = start + timedelta(days=1)

        # Datos del día usando FinanceEngine
        ops_day    = FinanceEngine.get_daily_ops(fecha)
        profit_day = FinanceEngine.get_profit(fecha, fecha)
        position   = FinanceEngine.get_open_position()
        balances   = FinanceEngine.get_balances()

        pending_count = Operation.query.filter(
            Operation.status.in_(['Pendiente', 'En proceso'])
        ).count()

        open_matches = AccountingMatch.query.filter(
            AccountingMatch.status == 'Activo',
        ).outerjoin(
            AccountingBatch, AccountingMatch.batch_id == AccountingBatch.id, isouter=True
        ).filter(
            db.or_(AccountingMatch.batch_id.is_(None), AccountingBatch.status != 'Cerrado')
        ).count()

        # Obtener o crear cierre
        closure = DailyClosure.query.filter_by(closure_date=fecha).first()
        if not closure:
            closure = DailyClosure(
                closure_date=fecha,
                status=DailyClosure.STATUS_BORRADOR,
                created_by=current_user.id,
            )
            db.session.add(closure)

        closure.system_balances         = balances['by_bank']
        closure.operations_completed    = ops_day['total_ops']
        closure.total_volume_usd        = ops_day['volume_usd']
        closure.total_bought_usd        = ops_day['buy_usd']
        closure.total_sold_usd          = ops_day['sell_usd']
        closure.avg_buy_rate            = ops_day['avg_buy_rate']
        closure.avg_sell_rate           = ops_day['avg_sell_rate']
        closure.gross_spread_pen        = profit_day['total_pen']
        closure.net_profit_pen          = profit_day['total_pen']
        closure.pending_operations      = pending_count
        closure.unmatched_completed_usd = abs(position['neto_usd'])
        closure.open_matches            = open_matches
        db.session.commit()

        return jsonify({'ok': True, 'cierre': closure.to_dict()})

    except Exception as exc:
        db.session.rollback()
        _log.exception('[Finanzas] api_cierre_calcular')
        return jsonify({'ok': False, 'error': str(exc)}), 500


# ── API: Cierre — Validar (saldos reales) ────────────────────────────────────

@finanzas_bp.route('/api/cierre/validar', methods=['POST'])
@csrf.exempt
@login_required
def api_cierre_validar():
    _require_role()
    try:
        from app.models import DailyClosure

        data          = request.get_json() or {}
        fecha         = date.fromisoformat(data.get('fecha', date.today().isoformat()))
        real_balances = data.get('saldos_reales', {})
        notes         = data.get('notas', '')

        closure = DailyClosure.query.filter_by(closure_date=fecha).first()
        if not closure:
            return jsonify({'ok': False, 'error': 'Primero calcule el cierre del día'}), 400

        closure.validated_balances = real_balances
        closure.notes              = notes
        closure.compute_differences()
        db.session.commit()

        return jsonify({
            'ok':                True,
            'has_discrepancies': closure.has_discrepancies,
            'differences':       closure.differences,
            'cierre':            closure.to_dict(),
        })
    except Exception as exc:
        db.session.rollback()
        _log.exception('[Finanzas] api_cierre_validar')
        return jsonify({'ok': False, 'error': str(exc)}), 500


# ── API: Cierre — Confirmar ───────────────────────────────────────────────────

@finanzas_bp.route('/api/cierre/confirmar', methods=['POST'])
@csrf.exempt
@login_required
def api_cierre_confirmar():
    _require_role()
    try:
        from app.models import DailyClosure, BankMovement

        data   = request.get_json() or {}
        fecha  = date.fromisoformat(data.get('fecha', date.today().isoformat()))
        motivo = data.get('motivo_discrepancia', '')

        closure = DailyClosure.query.filter_by(closure_date=fecha).first()
        if not closure:
            return jsonify({'ok': False, 'error': 'Cierre no encontrado'}), 404
        if closure.is_validated:
            return jsonify({'ok': False, 'error': 'Cierre ya confirmado'}), 400
        if not closure.validated_balances:
            return jsonify({'ok': False, 'error': 'Ingrese saldos reales antes de confirmar'}), 400
        if closure.has_discrepancies and not motivo:
            return jsonify({'ok': False, 'error': 'Hay diferencias — ingrese el motivo'}), 400

        closure.status             = DailyClosure.STATUS_VALIDADO
        closure.discrepancy_reason = motivo
        closure.validated_by       = current_user.id
        closure.validated_at       = now_peru()

        BankMovement.query.filter_by(closure_date=fecha).update({'is_validated': True})
        db.session.commit()

        return jsonify({
            'ok':      True,
            'message': f'Cierre del {fecha.strftime("%d/%m/%Y")} confirmado.',
            'cierre':  closure.to_dict(),
        })
    except Exception as exc:
        db.session.rollback()
        _log.exception('[Finanzas] api_cierre_confirmar')
        return jsonify({'ok': False, 'error': str(exc)}), 500


# ── API: Cierre — Historial ───────────────────────────────────────────────────

@finanzas_bp.route('/api/cierre/historial')
@login_required
def api_cierre_historial():
    _require_role()
    try:
        from app.models import DailyClosure

        page     = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 30))
        cierres  = DailyClosure.query.order_by(
            DailyClosure.closure_date.desc()
        ).offset((page - 1) * per_page).limit(per_page).all()
        total = DailyClosure.query.count()

        return jsonify({
            'ok':      True,
            'total':   total,
            'page':    page,
            'cierres': [c.to_dict() for c in cierres],
        })
    except Exception as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 500


# ── API: Cierre — Por fecha ───────────────────────────────────────────────────

@finanzas_bp.route('/api/cierre/<fecha_str>')
@login_required
def api_cierre_get(fecha_str):
    _require_role()
    try:
        from app.models import DailyClosure

        fecha   = date.fromisoformat(fecha_str)
        closure = DailyClosure.query.filter_by(closure_date=fecha).first()
        if not closure:
            return jsonify({'ok': True, 'found': False}), 200
        return jsonify({'ok': True, 'found': True, 'cierre': closure.to_dict()})
    except Exception as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 500


@finanzas_bp.route('/api/saldo/corregir', methods=['POST'])
@csrf.exempt
@login_required
def api_saldo_corregir():
    """Corrección manual de saldo bancario — fuente única reemplaza position.update_balance."""
    _require_role()
    try:
        from app.models.bank_balance import BankBalance
        from app.models.bank_movement import BankMovement

        data      = request.get_json() or {}
        bank_name = data.get('bank_name', '').strip()
        currency  = data.get('currency', '').upper()
        amount    = data.get('amount')
        motivo    = data.get('motivo', 'Corrección manual').strip()

        if not bank_name or currency not in ('USD', 'PEN'):
            return jsonify({'ok': False, 'error': 'Faltan datos o moneda inválida'}), 400
        try:
            amount = float(amount)
            if amount < 0:
                return jsonify({'ok': False, 'error': 'El saldo no puede ser negativo'}), 400
        except (TypeError, ValueError):
            return jsonify({'ok': False, 'error': 'Monto inválido'}), 400

        balance = BankBalance.get_or_create_balance(bank_name)
        anterior = float(balance.balance_usd if currency == 'USD' else balance.balance_pen)
        diferencia = amount - anterior

        if currency == 'USD':
            balance.balance_usd         = amount
            balance.initial_balance_usd = amount  # base para sync_balances
        else:
            balance.balance_pen         = amount
            balance.initial_balance_pen = amount  # base para sync_balances
        balance.updated_by = current_user.id
        balance.updated_at = now_peru()

        db.session.commit()
        return jsonify({
            'ok': True,
            'message': f'Saldo {bank_name} {currency} corregido a {amount:.2f}',
            'anterior': anterior,
            'nuevo': amount,
            'diferencia': diferencia,
        })
    except Exception as exc:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(exc)}), 500




# ── API: Apertura / Cierre simplificado (2 inputs: USD total + PEN total) ─────

@finanzas_bp.route('/api/dia/apertura', methods=['POST'])
@csrf.exempt
@login_required
def api_dia_apertura():
    """
    Registra el saldo inicial del día con sólo dos valores: USD total y PEN total.
    Distribuye proporcionalmente entre bancos usando los saldos actuales de BankBalance.
    Body: { usd: float, pen: float, fecha: 'YYYY-MM-DD' (opcional) }
    """
    _require_role()
    try:
        from app.models import DailyClosure, BankBalance
        from app.config.bank_accounts import QORICASH_ACCOUNTS

        data   = request.get_json() or {}
        fecha  = date.fromisoformat(data.get('fecha', date.today().isoformat()))
        usd_in = float(data.get('usd', 0))
        pen_in = float(data.get('pen', 0))

        if usd_in < 0 or pen_in < 0:
            return jsonify({'ok': False, 'error': 'Los saldos no pueden ser negativos'}), 400

        # Construir dict per-bank distribuyendo proporcionalmente desde BankBalance actual
        BANKS = ['BCP', 'INTERBANK', 'BANBIF']
        cur_usd = {bk: 0.0 for bk in BANKS}
        cur_pen = {bk: 0.0 for bk in BANKS}
        for bk in BANKS:
            for cur in ('USD', 'PEN'):
                numero  = QORICASH_ACCOUNTS.get(bk, {}).get(cur, {}).get('numero', '')
                acct    = f"{bk} {cur} ({numero})"
                bb      = BankBalance.query.filter_by(bank_name=acct).first()
                if bb:
                    if cur == 'USD':
                        cur_usd[bk] = float(bb.balance_usd or 0)
                    else:
                        cur_pen[bk] = float(bb.balance_pen or 0)

        total_sys_usd = sum(cur_usd.values()) or 1.0
        total_sys_pen = sum(cur_pen.values()) or 1.0

        bals = {}
        for bk in BANKS:
            bals[bk] = {
                'USD': round(usd_in * (cur_usd[bk] / total_sys_usd), 2),
                'PEN': round(pen_in * (cur_pen[bk] / total_sys_pen), 2),
            }
        # Fix rounding residuals: assign remainder to BCP
        bals['BCP']['USD'] = round(bals['BCP']['USD'] + usd_in - sum(v['USD'] for v in bals.values()), 2)
        bals['BCP']['PEN'] = round(bals['BCP']['PEN'] + pen_in - sum(v['PEN'] for v in bals.values()), 2)

        closure = DailyClosure.query.filter_by(closure_date=fecha).first()
        if not closure:
            closure = DailyClosure(
                closure_date=fecha,
                status=DailyClosure.STATUS_BORRADOR,
                created_by=current_user.id,
            )
            db.session.add(closure)

        if closure.opening_balance_json and closure.opening_balance_json != '{}':
            if current_user.role != 'Master':
                return jsonify({'ok': False, 'error': 'Apertura ya registrada. Solo un Master puede modificarla.'}), 409

        closure.opening_balance       = bals
        closure.opening_total_usd     = round(usd_in, 2)
        closure.opening_total_pen     = round(pen_in, 2)
        closure.opening_registered_at = now_peru()
        closure.opening_registered_by = current_user.id

        if closure.closing_balance_json and closure.closing_balance_json != '{}':
            closure.compute_result()

        db.session.commit()
        return jsonify({'ok': True, 'message': f'Apertura del {fecha.strftime("%d/%m/%Y")} registrada.',
                        'cierre': closure.to_dict()})
    except Exception as exc:
        db.session.rollback()
        _log.exception('[Finanzas] api_dia_apertura')
        return jsonify({'ok': False, 'error': str(exc)}), 500


@finanzas_bp.route('/api/dia/cierre', methods=['POST'])
@csrf.exempt
@login_required
def api_dia_cierre():
    """
    Registra el saldo final del día con sólo dos valores: USD total y PEN total.
    Body: { usd: float, pen: float, fecha: 'YYYY-MM-DD' (opcional), notas: str }
    """
    _require_role()
    try:
        from app.models import DailyClosure, BankBalance
        from app.config.bank_accounts import QORICASH_ACCOUNTS

        data   = request.get_json() or {}
        fecha  = date.fromisoformat(data.get('fecha', date.today().isoformat()))
        usd_in = float(data.get('usd', 0))
        pen_in = float(data.get('pen', 0))
        notas  = data.get('notas', '').strip()

        if usd_in < 0 or pen_in < 0:
            return jsonify({'ok': False, 'error': 'Los saldos no pueden ser negativos'}), 400

        closure = DailyClosure.query.filter_by(closure_date=fecha).first()
        if not closure or not closure.opening_balance_json or closure.opening_balance_json == '{}':
            return jsonify({'ok': False, 'error': 'Registre primero la apertura del día'}), 400

        if closure.is_validated and current_user.role != 'Master':
            return jsonify({'ok': False, 'error': 'El cierre ya fue validado. Solo un Master puede modificarlo.'}), 409

        # Distribute closing balance proportionally (same logic as apertura)
        BANKS = ['BCP', 'INTERBANK', 'BANBIF']
        cur_usd = {bk: 0.0 for bk in BANKS}
        cur_pen = {bk: 0.0 for bk in BANKS}
        from app.config.bank_accounts import QORICASH_ACCOUNTS
        for bk in BANKS:
            for cur in ('USD', 'PEN'):
                numero = QORICASH_ACCOUNTS.get(bk, {}).get(cur, {}).get('numero', '')
                acct   = f"{bk} {cur} ({numero})"
                bb     = BankBalance.query.filter_by(bank_name=acct).first()
                if bb:
                    if cur == 'USD':
                        cur_usd[bk] = float(bb.balance_usd or 0)
                    else:
                        cur_pen[bk] = float(bb.balance_pen or 0)

        total_sys_usd = sum(cur_usd.values()) or 1.0
        total_sys_pen = sum(cur_pen.values()) or 1.0

        bals = {}
        for bk in BANKS:
            bals[bk] = {
                'USD': round(usd_in * (cur_usd[bk] / total_sys_usd), 2),
                'PEN': round(pen_in * (cur_pen[bk] / total_sys_pen), 2),
            }
        bals['BCP']['USD'] = round(bals['BCP']['USD'] + usd_in - sum(v['USD'] for v in bals.values()), 2)
        bals['BCP']['PEN'] = round(bals['BCP']['PEN'] + pen_in - sum(v['PEN'] for v in bals.values()), 2)

        closure.closing_balance       = bals
        closure.closing_total_usd     = round(usd_in, 2)
        closure.closing_total_pen     = round(pen_in, 2)
        closure.closing_registered_at = now_peru()
        closure.closing_registered_by = current_user.id
        if notas:
            closure.notes = notas

        result = closure.compute_result()
        db.session.commit()
        return jsonify({'ok': True, 'message': f'Cierre del {fecha.strftime("%d/%m/%Y")} registrado.',
                        'result': result, 'cierre': closure.to_dict()})
    except Exception as exc:
        db.session.rollback()
        _log.exception('[Finanzas] api_dia_cierre')
        return jsonify({'ok': False, 'error': str(exc)}), 500


# ── API: Caja Diaria — Registrar Apertura ─────────────────────────────────────

@finanzas_bp.route('/api/caja/apertura', methods=['POST'])
@csrf.exempt
@login_required
def api_caja_apertura():
    """
    Registra el saldo inicial del día.
    Solo se puede registrar una vez por fecha (a menos que sea Master).
    Body: { fecha, balances: {BCP:{USD,PEN}, INTERBANK:{USD,PEN}, BANBIF:{USD,PEN}}, notas }
    """
    _require_role()
    try:
        from app.models import DailyClosure

        data   = request.get_json() or {}
        fecha  = date.fromisoformat(data.get('fecha', date.today().isoformat()))
        bals   = data.get('balances', {})

        # Validar que sea dict con bancos/monedas
        if not isinstance(bals, dict):
            return jsonify({'ok': False, 'error': 'Formato de saldos inválido'}), 400

        # Validar numéricos
        total_usd = 0.0
        total_pen = 0.0
        for banco, monedas in bals.items():
            for cur, amt in monedas.items():
                try:
                    v = float(amt)
                    if v < 0:
                        return jsonify({'ok': False, 'error': f'Monto negativo en {banco}/{cur}'}), 400
                    if cur == 'USD':
                        total_usd += v
                    elif cur == 'PEN':
                        total_pen += v
                except (TypeError, ValueError):
                    return jsonify({'ok': False, 'error': f'Monto inválido en {banco}/{cur}'}), 400

        # Obtener o crear cierre del día
        closure = DailyClosure.query.filter_by(closure_date=fecha).first()
        if not closure:
            closure = DailyClosure(
                closure_date=fecha,
                status=DailyClosure.STATUS_BORRADOR,
                created_by=current_user.id,
            )
            db.session.add(closure)

        # Validar: no sobreescribir apertura existente (salvo Master)
        if closure.opening_balance_json and closure.opening_balance_json != '{}':
            if current_user.role != 'Master':
                return jsonify({
                    'ok': False,
                    'error': 'El saldo inicial ya fue registrado para esta fecha. Solo un Master puede modificarlo.',
                }), 409

        closure.opening_balance      = bals
        closure.opening_total_usd    = round(total_usd, 2)
        closure.opening_total_pen    = round(total_pen, 2)
        closure.opening_registered_at = now_peru()
        closure.opening_registered_by = current_user.id

        # Si ya existe cierre, recalcular resultado
        if closure.closing_balance_json and closure.closing_balance_json != '{}':
            closure.compute_result()

        db.session.commit()
        return jsonify({
            'ok':      True,
            'message': f'Saldo inicial del {fecha.strftime("%d/%m/%Y")} registrado.',
            'cierre':  closure.to_dict(),
        })
    except Exception as exc:
        db.session.rollback()
        _log.exception('[Finanzas] api_caja_apertura')
        return jsonify({'ok': False, 'error': str(exc)}), 500


# ── API: Caja Diaria — Registrar Cierre ──────────────────────────────────────

@finanzas_bp.route('/api/caja/cierre', methods=['POST'])
@csrf.exempt
@login_required
def api_caja_cierre():
    """
    Registra el saldo final del día y calcula resultado.
    Body: { fecha, balances: {BCP:{USD,PEN}, ...}, notas }
    """
    _require_role()
    try:
        from app.models import DailyClosure

        data   = request.get_json() or {}
        fecha  = date.fromisoformat(data.get('fecha', now_peru().date().isoformat()))
        bals   = data.get('balances', {})
        notas  = data.get('notas', '').strip()

        if not isinstance(bals, dict):
            return jsonify({'ok': False, 'error': 'Formato de saldos inválido'}), 400

        total_usd = 0.0
        total_pen = 0.0
        for banco, monedas in bals.items():
            for cur, amt in monedas.items():
                try:
                    v = float(amt)
                    if v < 0:
                        return jsonify({'ok': False, 'error': f'Monto negativo en {banco}/{cur}'}), 400
                    if cur == 'USD':
                        total_usd += v
                    elif cur == 'PEN':
                        total_pen += v
                except (TypeError, ValueError):
                    return jsonify({'ok': False, 'error': f'Monto inválido en {banco}/{cur}'}), 400

        closure = DailyClosure.query.filter_by(closure_date=fecha).first()
        if not closure:
            return jsonify({'ok': False, 'error': 'Registre primero el saldo inicial del día'}), 400

        # Validar: no reemplazar cierre confirmado (salvo Master)
        if closure.is_validated and current_user.role != 'Master':
            return jsonify({'ok': False, 'error': 'El cierre ya fue validado. Solo un Master puede modificarlo.'}), 409

        closure.closing_balance      = bals
        closure.closing_total_usd    = round(total_usd, 2)
        closure.closing_total_pen    = round(total_pen, 2)
        closure.closing_registered_at = now_peru()
        closure.closing_registered_by = current_user.id
        if notas:
            closure.notes = notas

        result = closure.compute_result()
        db.session.commit()

        return jsonify({
            'ok':      True,
            'message': f'Saldo final del {fecha.strftime("%d/%m/%Y")} registrado.',
            'result':  result,
            'cierre':  closure.to_dict(),
        })
    except Exception as exc:
        db.session.rollback()
        _log.exception('[Finanzas] api_caja_cierre')
        return jsonify({'ok': False, 'error': str(exc)}), 500


# ── API: Caja Diaria — Reabrir (eliminar cierre del día) ─────────────────────

@finanzas_bp.route('/api/caja/reabrir', methods=['POST'])
@csrf.exempt
@login_required
def api_caja_reabrir():
    """Elimina el saldo final registrado del día, reabriendo el cierre."""
    _require_role()
    try:
        from app.models import DailyClosure

        data  = request.get_json() or {}
        fecha = date.fromisoformat(data.get('fecha', now_peru().date().isoformat()))

        closure = DailyClosure.query.filter_by(closure_date=fecha).first()
        if not closure:
            return jsonify({'ok': False, 'error': 'No existe registro para esa fecha'}), 404

        has_closing = bool(closure.closing_balance_json and closure.closing_balance_json != '{}')
        if not has_closing:
            return jsonify({'ok': False, 'error': 'El día ya está abierto'}), 400

        closure.closing_balance_json      = '{}'
        closure.closing_total_usd         = 0.0
        closure.closing_total_pen         = 0.0
        closure.closing_registered_at     = None
        closure.closing_registered_by     = None

        db.session.commit()
        _log.info(f'[Finanzas] Cierre {fecha} reabierto por user {current_user.id}')

        return jsonify({'ok': True, 'message': f'Día {fecha.strftime("%d/%m/%Y")} reabierto correctamente.'})
    except Exception as exc:
        db.session.rollback()
        _log.exception('[Finanzas] api_caja_reabrir')
        return jsonify({'ok': False, 'error': str(exc)}), 500


# ── API: Caja Diaria — Estado del día ────────────────────────────────────────

@finanzas_bp.route('/api/caja/hoy')
@login_required
def api_caja_hoy():
    """Estado actual de caja para la fecha indicada (default: hoy)."""
    _require_role()
    try:
        from app.models import DailyClosure
        fecha_str = request.args.get('fecha', date.today().isoformat())
        fecha = date.fromisoformat(fecha_str)
        closure = DailyClosure.query.filter_by(closure_date=fecha).first()
        if not closure:
            # Devolver saldos actuales del sistema como referencia
            balances = FinanceEngine.get_balances()
            return jsonify({
                'ok':       True,
                'found':    False,
                'fecha':    fecha.isoformat(),
                'balances_actuales': balances['by_bank'],
                'total_usd_actual':  balances['total_usd'],
                'total_pen_actual':  balances['total_pen'],
            })
        return jsonify({'ok': True, 'found': True, 'cierre': closure.to_dict()})
    except Exception as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 500


# ── API: Caja Diaria — Historial ─────────────────────────────────────────────

@finanzas_bp.route('/api/caja/historial')
@login_required
def api_caja_historial():
    """
    Historial de cierres con saldo inicial/final y resultado.
    Params: fecha_ini, fecha_fin, page, per_page
    """
    _require_role()
    try:
        from app.models import DailyClosure
        from sqlalchemy import and_

        page     = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 30))
        fecha_ini = request.args.get('fecha_ini')
        fecha_fin = request.args.get('fecha_fin')

        q = DailyClosure.query
        if fecha_ini:
            q = q.filter(DailyClosure.closure_date >= date.fromisoformat(fecha_ini))
        if fecha_fin:
            q = q.filter(DailyClosure.closure_date <= date.fromisoformat(fecha_fin))

        total   = q.count()
        cierres = q.order_by(DailyClosure.closure_date.desc()).offset(
            (page - 1) * per_page
        ).limit(per_page).all()

        # Calcular acumulados
        total_utilidad_pen = sum(
            float(c.result_pen or 0) for c in cierres
            if c.result_label in ('utilidad', 'perdida', 'cuadre') and c.result_pen is not None
        )
        dias_utilidad = sum(1 for c in cierres if c.result_label == 'utilidad')
        dias_perdida  = sum(1 for c in cierres if c.result_label == 'perdida')
        dias_cuadre   = sum(1 for c in cierres if c.result_label == 'cuadre')

        return jsonify({
            'ok':       True,
            'total':    total,
            'page':     page,
            'per_page': per_page,
            'pages':    (total + per_page - 1) // per_page,
            'resumen': {
                'total_result_pen': round(total_utilidad_pen, 2),
                'dias_utilidad':    dias_utilidad,
                'dias_perdida':     dias_perdida,
                'dias_cuadre':      dias_cuadre,
            },
            'cierres': [c.to_dict() for c in cierres],
        })
    except Exception as exc:
        _log.exception('[Finanzas] api_caja_historial')
        return jsonify({'ok': False, 'error': str(exc)}), 500

# ── API: Caja — Cuadre automático ─────────────────────────────────────────────

@finanzas_bp.route('/api/caja/cuadre')
@login_required
def api_caja_cuadre():
    """
    Cuadre de caja del día:
      saldo_inicial + ingresos − egresos = saldo_teórico vs saldo_final
    Params: fecha (YYYY-MM-DD, default: hoy)
    """
    _require_role()
    try:
        fecha_str = request.args.get('fecha', date.today().isoformat())
        fecha = date.fromisoformat(fecha_str)
        result = FinanceEngine.get_daily_cashflow(fecha)
        return jsonify({'ok': True, **result})
    except Exception as exc:
        _log.exception('[Finanzas] api_caja_cuadre')
        return jsonify({'ok': False, 'error': str(exc)}), 500


# ── DIAGNÓSTICO TEMPORAL ───────────────────────────────────────────────────────
@finanzas_bp.route('/api/diagnostico/saldos')
@login_required
def api_diagnostico_saldos():
    """Diagnóstico: BankBalance records + operaciones completadas hoy con sus movimientos."""
    _require_role()
    from app.models.bank_balance import BankBalance
    from app.models import Operation
    from app.config.bank_accounts import QORICASH_ACCOUNTS, ALLOWED_BANK_NAMES
    from datetime import datetime as dt, time, timedelta

    # 1. Todos los registros BankBalance
    all_bb = []
    for bb in BankBalance.query.order_by(BankBalance.bank_name).all():
        all_bb.append({
            'bank_name':           bb.bank_name,
            'balance_usd':         float(bb.balance_usd),
            'balance_pen':         float(bb.balance_pen),
            'initial_balance_usd': float(bb.initial_balance_usd),
            'initial_balance_pen': float(bb.initial_balance_pen),
            'in_allowed':          bb.bank_name in ALLOWED_BANK_NAMES,
            'updated_at':          bb.updated_at.isoformat() if bb.updated_at else None,
        })

    # 2. Operaciones completadas hoy → bank detection + deltas
    today = now_peru().date()
    ops_today = Operation.query.filter(
        Operation.status == 'Completada',
        Operation.completed_at >= dt.combine(today, time.min),
        Operation.completed_at <= dt.combine(today, time.max),
    ).order_by(Operation.completed_at.desc()).all()

    _ALIASES = {'BCP':'BCP','CREDITO':'BCP','CRÉDITO':'BCP','INTERBANK':'INTERBANK','IBK':'INTERBANK','BANBIF':'BANBIF','BIF':'BANBIF'}
    _banco_accts = {b: {m: f"{b} {m} ({d['numero']})" for m, d in ms.items()} for b, ms in QORICASH_ACCOUNTS.items()}

    def _norm(name):
        if not (name or '').strip(): return ''
        u = name.upper()
        for alias, banco in _ALIASES.items():
            if alias in u: return banco
        return 'INTERBANK'

    ops_info = []
    for op in ops_today:
        _pays = op.client_payments or []
        _deps = op.client_deposits or []
        _hp = any(p.get('qc_bank') for p in _pays)
        _hd = any(d.get('qc_bank') for d in _deps)

        # Detectar banco origen (USD para Compra / PEN para Venta)
        src_bank = ''
        try:
            if op.source_account and op.client:
                for a in (op.client.bank_accounts or []):
                    if a.get('account_number') == op.source_account:
                        src_bank = _norm(a.get('bank_name', ''))
            if not src_bank and getattr(op, 'source_bank_name', None):
                src_bank = _norm(op.source_bank_name)
        except Exception: pass

        dst_bank = ''
        try:
            if op.destination_account and op.client:
                for a in (op.client.bank_accounts or []):
                    if a.get('account_number') == op.destination_account:
                        dst_bank = _norm(a.get('bank_name', ''))
            if not dst_bank and getattr(op, 'destination_bank_name', None):
                dst_bank = _norm(op.destination_bank_name)
        except Exception: pass
        if not dst_bank: dst_bank = src_bank or 'INTERBANK'

        # Calcular deltas esperados
        usd = float(op.amount_usd or 0)
        pen = float(op.amount_pen or 0)
        movements = []
        if op.operation_type == 'Compra':
            usd_bank = src_bank or 'INTERBANK'
            pen_bank = dst_bank
            if _hd:
                for d in _deps:
                    b = _norm(d.get('qc_bank','')) or _norm(d.get('cuenta_cargo',''))
                    a = float(d.get('importe', 0))
                    if b and a > 0:
                        movements.append({'acct': _banco_accts.get(b,{}).get('USD','?'), 'delta_usd': +a, 'delta_pen': 0})
            else:
                movements.append({'acct': _banco_accts.get(usd_bank,{}).get('USD','?'), 'delta_usd': +usd, 'delta_pen': 0})
            if _hp:
                for p in _pays:
                    b = _norm(p.get('qc_bank','')) or _norm(p.get('cuenta_destino',''))
                    a = float(p.get('importe', 0))
                    if b and a > 0:
                        movements.append({'acct': _banco_accts.get(b,{}).get('PEN','?'), 'delta_usd': 0, 'delta_pen': -a})
            else:
                movements.append({'acct': _banco_accts.get(pen_bank,{}).get('PEN','?'), 'delta_usd': 0, 'delta_pen': -pen})
        else:  # Venta
            pen_bank = src_bank or 'INTERBANK'
            usd_bank = dst_bank
            if _hd:
                for d in _deps:
                    b = _norm(d.get('qc_bank','')) or _norm(d.get('cuenta_cargo',''))
                    a = float(d.get('importe', 0))
                    if b and a > 0:
                        movements.append({'acct': _banco_accts.get(b,{}).get('PEN','?'), 'delta_usd': 0, 'delta_pen': +a})
            else:
                movements.append({'acct': _banco_accts.get(pen_bank,{}).get('PEN','?'), 'delta_usd': 0, 'delta_pen': +pen})
            if _hp:
                for p in _pays:
                    b = _norm(p.get('qc_bank','')) or _norm(p.get('cuenta_destino',''))
                    a = float(p.get('importe', 0))
                    if b and a > 0:
                        movements.append({'acct': _banco_accts.get(b,{}).get('USD','?'), 'delta_usd': -a, 'delta_pen': 0})
            else:
                movements.append({'acct': _banco_accts.get(usd_bank,{}).get('USD','?'), 'delta_usd': -usd, 'delta_pen': 0})

        ops_info.append({
            'op_id':      op.operation_id,
            'type':       op.operation_type,
            'amount_usd': usd,
            'amount_pen': pen,
            'completed_at': op.completed_at.isoformat() if op.completed_at else None,
            'src_bank':   src_bank,
            'dst_bank':   dst_bank,
            'has_qc_deposits': _hd,
            'has_qc_payments': _hp,
            'deposits':   _deps,
            'payments':   _pays,
            'movements':  movements,
        })

    return jsonify({'ok': True, 'bank_balances': all_bb, 'ops_today': ops_info})


# ── Diagnóstico de base de datos — verificación de columnas en daily_closures ─

@finanzas_bp.route('/api/db-diagnostico')
@csrf.exempt
def api_db_diagnostico():
    """
    Endpoint de diagnóstico: verifica que las columnas de daily_closures existan en
    la base de datos real en PostgreSQL. Requiere X-Cron-Secret para acceso.
    """
    import os
    from sqlalchemy import text
    _DIAG_KEY = 'qc_diag_2026_x7k'
    given = (request.headers.get('X-Cron-Secret')
             or request.args.get('secret')
             or '')
    env_secret = os.environ.get('CRON_SECRET', '')
    if given != _DIAG_KEY and (not env_secret or given != env_secret):
        return jsonify({'ok': False, 'error': 'Unauthorized'}), 401

    result = {}
    try:
        # 1. Identificar la base de datos activa
        row = db.session.execute(text("SELECT current_database(), current_schema(), version()")).fetchone()
        result['db_info'] = {
            'current_database': row[0],
            'current_schema':   row[1],
            'version':          row[2][:80],
        }

        # 2. Todos los schemas que contienen daily_closures
        schemas = db.session.execute(text(
            "SELECT schemaname, tablename FROM pg_tables WHERE tablename='daily_closures'"
        )).fetchall()
        result['daily_closures_schemas'] = [{'schema': r[0], 'table': r[1]} for r in schemas]

        # 3. Columnas reales en daily_closures (todos los schemas)
        cols = db.session.execute(text(
            "SELECT table_schema, column_name, data_type, column_default, is_nullable "
            "FROM information_schema.columns "
            "WHERE table_name='daily_closures' "
            "ORDER BY table_schema, ordinal_position"
        )).fetchall()
        result['columns'] = [
            {'schema': r[0], 'column': r[1], 'type': r[2], 'default': r[3], 'nullable': r[4]}
            for r in cols
        ]

        # 4. Verificar las 13 columnas requeridas
        existing_cols = {r[1] for r in cols}
        required = [
            'opening_balance_json', 'opening_total_usd', 'opening_total_pen',
            'opening_registered_at', 'opening_registered_by',
            'closing_balance_json', 'closing_total_usd', 'closing_total_pen',
            'closing_registered_at', 'closing_registered_by',
            'result_usd', 'result_pen', 'result_label',
        ]
        result['required_columns_check'] = {
            col: ('OK' if col in existing_cols else 'MISSING')
            for col in required
        }
        result['all_required_present'] = all(col in existing_cols for col in required)

        # 5. Estado de alembic_version
        try:
            av = db.session.execute(text("SELECT version_num FROM alembic_version")).fetchall()
            result['alembic_version'] = [r[0] for r in av]
        except Exception as e:
            result['alembic_version'] = f'error: {e}'

        # 6. DATABASE_URL (solo host+db, sin credenciales)
        db_url = os.environ.get('DATABASE_URL', '')
        if db_url:
            try:
                from urllib.parse import urlparse
                p = urlparse(db_url)
                result['db_connection'] = f'{p.scheme}://*****@{p.hostname}:{p.port}{p.path}'
            except Exception:
                result['db_connection'] = 'parse error'
        else:
            result['db_connection'] = 'DATABASE_URL not set'

    except Exception as exc:
        result['error'] = str(exc)

    return jsonify(result)
