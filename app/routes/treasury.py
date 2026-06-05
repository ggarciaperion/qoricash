"""
Treasury Blueprint — Control Financiero y Tesorería
====================================================
Módulo de reingeniería financiera para QoriCash.

Proporciona:
  /treasury/                  — Dashboard ejecutivo de tesorería
  /treasury/movimientos/      — Libro ledger de movimientos bancarios
  /treasury/cierre/           — Proceso de cierre diario
  /treasury/libros/           — Libros contables (caja, bancos, utilidades, amarres)

  /treasury/api/dashboard     — Snapshot financiero completo (JSON)
  /treasury/api/posicion      — Posición por banco/moneda (JSON)
  /treasury/api/movimientos   — Lista de movimientos con filtros (JSON)
  /treasury/api/cierre/calcular   — Calcula datos de cierre para una fecha (JSON)
  /treasury/api/cierre/validar    — Guarda saldos reales ingresados (JSON)
  /treasury/api/cierre/confirmar  — Confirma y finaliza el cierre (JSON)
  /treasury/api/cierre/<date>     — Obtiene cierre de una fecha (JSON)
  /treasury/api/ajuste            — Crea movimiento de ajuste manual (JSON)
  /treasury/api/reconciliacion    — Verifica coherencia saldos vs movimientos (JSON)
"""
import logging
from datetime import date, datetime, timedelta

from flask import Blueprint, render_template, jsonify, request, abort
from flask_login import login_required, current_user
from sqlalchemy import func, and_

from app.extensions import db
from app.models import (
    BankBalance, Operation, AccountingMatch, AccountingBatch,
    BankMovement, DailyClosure, JournalEntry, ExpenseRecord,
)
from app.utils.formatters import now_peru

_log = logging.getLogger(__name__)

treasury_bp = Blueprint('treasury', __name__, template_folder='../templates/treasury')

ALLOWED_ROLES = ('Master', 'Presidente de Negocios')

# ── Helpers internos ──────────────────────────────────────────────────────────

def _require_master():
    if current_user.role not in ALLOWED_ROLES:
        abort(403)

BANKS    = ['BCP', 'INTERBANK', 'BANBIF']
CURRENCIES = ['USD', 'PEN']

def _bank_account_name(bank_key: str, currency: str) -> str:
    """Retorna el nombre canónico de cuenta, ej. 'BCP USD (1917357790119)'."""
    try:
        from app.config.bank_accounts import QORICASH_ACCOUNTS
        numero = QORICASH_ACCOUNTS.get(bank_key, {}).get(currency, {}).get('numero', '')
        if numero:
            return f"{bank_key} {currency} ({numero})"
    except Exception:
        pass
    return f"{bank_key} {currency}"


def _get_system_balances() -> dict:
    """
    Retorna los saldos actuales del sistema por banco y moneda.
    Estructura: {BCP: {USD: x, PEN: y}, INTERBANK: {...}, BANBIF: {...}}
    """
    balances = {b: {c: 0.0 for c in CURRENCIES} for b in BANKS}
    all_bb = BankBalance.query.all()
    for bb in all_bb:
        name = bb.bank_name  # ej. "BCP USD (191...)"
        for bk in BANKS:
            if name.startswith(bk):
                for cur in CURRENCIES:
                    if cur in name:
                        if cur == 'USD':
                            balances[bk]['USD'] += float(bb.balance_usd or 0)
                        else:
                            balances[bk]['PEN'] += float(bb.balance_pen or 0)
    return balances


def _get_open_position() -> dict:
    """
    Calcula la posición abierta: USD completado sin amarrar.
    Open = total completado por tipo − total amarrado en esa pierna.
    """
    # Total USD completado por tipo
    compras_total = db.session.query(func.sum(Operation.amount_usd)).filter(
        Operation.status == 'Completada',
        Operation.operation_type == 'Compra',
    ).scalar() or 0

    ventas_total = db.session.query(func.sum(Operation.amount_usd)).filter(
        Operation.status == 'Completada',
        Operation.operation_type == 'Venta',
    ).scalar() or 0

    # Total USD amarrado (cada match tiene una pierna compra y una venta por matched_amount_usd)
    matched_total = db.session.query(func.sum(AccountingMatch.matched_amount_usd)).filter(
        AccountingMatch.status == 'Activo',
    ).scalar() or 0

    compras_open = max(0.0, float(compras_total) - float(matched_total))
    ventas_open  = max(0.0, float(ventas_total)  - float(matched_total))
    neto         = compras_open - ventas_open

    return {
        'compras_usd': round(compras_open, 2),
        'ventas_usd':  round(ventas_open,  2),
        'neto_usd':    round(neto, 2),
        'ops_count':   0,
    }


def _get_today_operations(fecha: date = None) -> dict:
    """Resumen de operaciones completadas en la fecha dada (default: hoy)."""
    if fecha is None:
        fecha = date.today()
    start = datetime.combine(fecha, datetime.min.time())
    end   = start + timedelta(days=1)

    ops = Operation.query.filter(
        Operation.status == 'Completada',
        Operation.completed_at >= start,
        Operation.completed_at <  end,
    ).all()

    compras   = [o for o in ops if o.operation_type == 'Compra']
    ventas    = [o for o in ops if o.operation_type == 'Venta']
    vol_usd   = sum(float(o.amount_usd or 0) for o in ops)
    buy_usd   = sum(float(o.amount_usd or 0) for o in compras)
    sell_usd  = sum(float(o.amount_usd or 0) for o in ventas)
    avg_buy   = (sum(float(o.exchange_rate or 0) * float(o.amount_usd or 0) for o in compras) / buy_usd
                 if buy_usd > 0 else 0)
    avg_sell  = (sum(float(o.exchange_rate or 0) * float(o.amount_usd or 0) for o in ventas) / sell_usd
                 if sell_usd > 0 else 0)

    return {
        'date':         fecha.isoformat(),
        'total_ops':    len(ops),
        'compras_count': len(compras),
        'ventas_count':  len(ventas),
        'volume_usd':   round(vol_usd,  2),
        'buy_usd':      round(buy_usd,  2),
        'sell_usd':     round(sell_usd, 2),
        'avg_buy_rate': round(avg_buy,  4),
        'avg_sell_rate':round(avg_sell, 4),
    }


def _get_pending_operations() -> dict:
    """Operaciones pendientes/en proceso."""
    ops = Operation.query.filter(
        Operation.status.in_(['Pendiente', 'En proceso'])
    ).all()
    criticas = []
    now = now_peru()
    for op in ops:
        ref = op.created_at or now
        horas = (now - ref).total_seconds() / 3600
        if horas > 4:
            criticas.append({
                'id':            op.id,
                'operation_id':  op.operation_id,
                'status':        op.status,
                'type':          op.operation_type,
                'amount_usd':    float(op.amount_usd or 0),
                'horas':         round(horas, 1),
                'client':        op.client.full_name if op.client else '—',
            })

    return {
        'total':    len(ops),
        'criticas': sorted(criticas, key=lambda x: x['horas'], reverse=True)[:10],
    }


def _get_realized_profit(fecha_ini=None, fecha_fin=None) -> dict:
    """
    Utilidad realizada desde amarres (AccountingMatch).
    Si no se pasan fechas, devuelve el acumulado total.
    """
    q = AccountingMatch.query.filter(AccountingMatch.status == 'Activo')
    if fecha_ini:
        q = q.filter(AccountingMatch.created_at >= fecha_ini)
    if fecha_fin:
        end_dt = datetime.combine(fecha_fin, datetime.max.time())
        q = q.filter(AccountingMatch.created_at <= end_dt)

    totals = q.with_entities(
        func.sum(AccountingMatch.profit_pen),
        func.sum(AccountingMatch.house_profit_pen),
        func.sum(AccountingMatch.trader_buy_profit_pen),
        func.sum(AccountingMatch.trader_sell_profit_pen),
        func.count(AccountingMatch.id),
    ).one()

    total_profit   = float(totals[0] or 0)
    house_profit   = float(totals[1] or 0)
    trader_buy     = float(totals[2] or 0)
    trader_sell    = float(totals[3] or 0)
    match_count    = int(totals[4] or 0)
    trader_profit  = trader_buy + trader_sell

    return {
        'total_profit_pen':  round(total_profit,  2),
        'house_profit_pen':  round(house_profit,  2),
        'trader_profit_pen': round(trader_profit, 2),
        'match_count':       match_count,
    }


def _get_today_expenses(fecha: date = None) -> float:
    """Gastos del día desde JournalEntry (cuentas 6xxx)."""
    if fecha is None:
        fecha = date.today()
    try:
        from app.models import JournalEntryLine
        result = db.session.query(func.sum(JournalEntryLine.debe)).join(
            JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id
        ).filter(
            JournalEntry.entry_date == fecha,
            JournalEntry.status == 'activo',
            JournalEntryLine.account_code.like('6%'),
        ).scalar()
        return float(result or 0)
    except Exception:
        return 0.0


def _get_closure_status() -> dict:
    """Estado del cierre más reciente y si hay cierre pendiente hoy."""
    today = date.today()
    yesterday = today - timedelta(days=1)

    last_closure = DailyClosure.query.order_by(DailyClosure.closure_date.desc()).first()
    today_closure = DailyClosure.query.filter_by(closure_date=today).first()

    missing_days = 0
    if last_closure:
        delta = (today - last_closure.closure_date).days
        if last_closure.is_validated:
            missing_days = max(0, delta - 1)
        else:
            missing_days = delta
    else:
        missing_days = 0  # primer día, sin historial

    return {
        'today_closure':    today_closure.to_dict() if today_closure else None,
        'last_validated':   last_closure.closure_date.isoformat() if last_closure and last_closure.is_validated else None,
        'missing_days':     missing_days,
        'requires_closure': missing_days > 0,
        'today_date':       today.isoformat(),
    }


# ── Vistas HTML ───────────────────────────────────────────────────────────────

@treasury_bp.route('/')
@login_required
def dashboard():
    _require_master()
    return render_template('treasury/dashboard.html')


@treasury_bp.route('/movimientos/')
@login_required
def movimientos():
    _require_master()
    return render_template('treasury/movimientos.html')


@treasury_bp.route('/cierre/')
@login_required
def cierre():
    _require_master()
    return render_template('treasury/cierre.html')


@treasury_bp.route('/libros/')
@login_required
def libros():
    _require_master()
    return render_template('treasury/libros.html')


# ── API: Dashboard snapshot ───────────────────────────────────────────────────

@treasury_bp.route('/api/dashboard')
@login_required
def api_dashboard():
    _require_master()
    errors = []

    def safe(fn, default, label):
        try:
            return fn()
        except Exception as exc:
            _log.exception(f'[Treasury] dashboard section "{label}" falló')
            errors.append(f'{label}: {exc}')
            return default

    today       = date.today()
    today_start = datetime.combine(today, datetime.min.time())

    system_balances = safe(_get_system_balances,  {b: {'USD': 0.0, 'PEN': 0.0} for b in BANKS}, 'saldos')
    total_usd = sum(v['USD'] for v in system_balances.values())
    total_pen = sum(v['PEN'] for v in system_balances.values())

    today_ops   = safe(lambda: _get_today_operations(today),  {'date': today.isoformat(), 'total_ops': 0, 'compras_count': 0, 'ventas_count': 0, 'volume_usd': 0, 'buy_usd': 0, 'sell_usd': 0, 'avg_buy_rate': 0, 'avg_sell_rate': 0}, 'ops_hoy')
    pending_ops = safe(_get_pending_operations, {'total': 0, 'criticas': []}, 'pendientes')
    open_pos    = safe(_get_open_position,      {'compras_usd': 0, 'ventas_usd': 0, 'neto_usd': 0, 'ops_count': 0}, 'posicion')

    _profit_default = {'total_profit_pen': 0, 'house_profit_pen': 0, 'trader_profit_pen': 0, 'match_count': 0}
    profit_all   = safe(_get_realized_profit, _profit_default, 'profit_total')
    profit_today = safe(lambda: _get_realized_profit(today_start, today), _profit_default, 'profit_hoy')
    expenses_today = safe(lambda: _get_today_expenses(today), 0.0, 'gastos')
    closure_status = safe(_get_closure_status, {'today_closure': None, 'last_validated': None, 'missing_days': 0, 'requires_closure': False, 'today_date': today.isoformat()}, 'cierre')

    recent_movements = safe(
        lambda: BankMovement.query.order_by(BankMovement.movement_date.desc()).limit(20).all(),
        [], 'movimientos'
    )

    alerts = []
    if errors:
        alerts.append({'level': 'danger', 'icon': 'bi-bug-fill',
                       'message': 'Error interno en dashboard: ' + ' | '.join(errors)})
    if closure_status['requires_closure']:
        days = closure_status['missing_days']
        alerts.append({'level': 'danger', 'icon': 'bi-exclamation-octagon-fill',
                       'message': f'Cierre diario pendiente — {days} día(s) sin validar'})
    if pending_ops['total'] > 0 and len(pending_ops['criticas']) > 0:
        alerts.append({'level': 'warning', 'icon': 'bi-clock-history',
                       'message': f"{len(pending_ops['criticas'])} operación(es) crítica(s) (>4h)"})
    if open_pos['neto_usd'] != 0:
        alerts.append({'level': 'info', 'icon': 'bi-currency-exchange',
                       'message': (f"Posición neta USD: {'Compra' if open_pos['neto_usd'] > 0 else 'Venta'} "
                                   f"${abs(open_pos['neto_usd']):,.2f} sin amarrar")})

    net_today = round(profit_today['total_profit_pen'] - expenses_today, 2)

    return jsonify({
        'success':   True,
        'errors':    errors,
        'timestamp': now_peru().isoformat(),
        'assets': {
            'system_balances': system_balances,
            'total_usd':       round(total_usd, 2),
            'total_pen':       round(total_pen, 2),
        },
        'today_operations':   today_ops,
        'pending_operations': pending_ops,
        'open_position':      open_pos,
        'profit': {
            'all_time':       profit_all,
            'today':          profit_today,
            'expenses_today': round(expenses_today, 2),
            'net_today':      net_today,
        },
        'closure':          closure_status,
        'recent_movements': [m.to_dict() for m in recent_movements],
        'alerts':           alerts,
    })


# ── API: Posición ─────────────────────────────────────────────────────────────

@treasury_bp.route('/api/posicion')
@login_required
def api_posicion():
    _require_master()
    try:
        fecha_str = request.args.get('fecha')
        fecha = date.fromisoformat(fecha_str) if fecha_str else date.today()

        system_balances = _get_system_balances()

        # Movimientos del día para cada banco
        posicion = []
        for bk in BANKS:
            for cur in CURRENCIES:
                mvs = BankMovement.get_movements_for_day(fecha, bank_key=bk, currency=cur)
                inflows  = sum(float(m.amount) for m in mvs if float(m.amount) > 0)
                outflows = sum(float(m.amount) for m in mvs if float(m.amount) < 0)
                posicion.append({
                    'bank_key':   bk,
                    'currency':   cur,
                    'inflows':    round(inflows,          2),
                    'outflows':   round(abs(outflows),    2),
                    'net':        round(inflows + outflows, 2),
                    'current_balance': system_balances.get(bk, {}).get(cur, 0),
                    'movements_count': len(mvs),
                })

        # Totales
        total_usd_in  = sum(p['inflows']  for p in posicion if p['currency'] == 'USD')
        total_usd_out = sum(p['outflows'] for p in posicion if p['currency'] == 'USD')
        total_pen_in  = sum(p['inflows']  for p in posicion if p['currency'] == 'PEN')
        total_pen_out = sum(p['outflows'] for p in posicion if p['currency'] == 'PEN')

        # Operaciones del día
        today_ops = _get_today_operations(fecha)

        return jsonify({
            'success':       True,
            'fecha':         fecha.isoformat(),
            'posicion':      posicion,
            'today_ops':     today_ops,
            'totales': {
                'usd_entradas': round(total_usd_in,  2),
                'usd_salidas':  round(total_usd_out, 2),
                'pen_entradas': round(total_pen_in,  2),
                'pen_salidas':  round(total_pen_out, 2),
            },
        })
    except Exception as e:
        _log.exception('[Treasury] Error en api_posicion')
        return jsonify({'success': False, 'error': str(e)}), 500


# ── API: Movimientos ──────────────────────────────────────────────────────────

@treasury_bp.route('/api/movimientos')
@login_required
def api_movimientos():
    _require_master()
    try:
        fecha_ini_str = request.args.get('fecha_ini')
        fecha_fin_str = request.args.get('fecha_fin')
        bank_key      = request.args.get('banco')
        currency      = request.args.get('moneda')
        mv_type       = request.args.get('tipo')
        page          = int(request.args.get('page', 1))
        per_page      = int(request.args.get('per_page', 50))

        q = BankMovement.query

        if fecha_ini_str:
            fi = datetime.combine(date.fromisoformat(fecha_ini_str), datetime.min.time())
            q = q.filter(BankMovement.movement_date >= fi)
        if fecha_fin_str:
            ff = datetime.combine(date.fromisoformat(fecha_fin_str), datetime.max.time())
            q = q.filter(BankMovement.movement_date <= ff)
        if bank_key:
            q = q.filter(BankMovement.bank_key == bank_key)
        if currency:
            q = q.filter(BankMovement.currency == currency)
        if mv_type:
            q = q.filter(BankMovement.movement_type == mv_type)

        total = q.count()
        movs  = q.order_by(BankMovement.movement_date.desc()).offset(
            (page - 1) * per_page
        ).limit(per_page).all()

        # Totales del filtro
        totales = q.with_entities(
            func.sum(BankMovement.amount)
        ).scalar()

        return jsonify({
            'success':   True,
            'total':     total,
            'page':      page,
            'per_page':  per_page,
            'pages':     (total + per_page - 1) // per_page,
            'net_amount': round(float(totales or 0), 2),
            'movimientos': [m.to_dict() for m in movs],
        })
    except Exception as e:
        _log.exception('[Treasury] Error en api_movimientos')
        return jsonify({'success': False, 'error': str(e)}), 500


# ── API: Ajuste manual ────────────────────────────────────────────────────────

@treasury_bp.route('/api/ajuste', methods=['POST'])
@login_required
def api_ajuste():
    _require_master()
    try:
        data       = request.get_json() or {}
        bank_key   = data.get('banco')
        currency   = data.get('moneda')
        amount_raw = float(data.get('monto', 0))
        tipo       = data.get('tipo', 'ajuste_entrada')   # ajuste_entrada | ajuste_salida | transfer_entrada | transfer_salida
        desc       = data.get('descripcion', '')
        ref        = data.get('referencia', '')

        if not bank_key or bank_key not in BANKS:
            return jsonify({'success': False, 'error': 'Banco inválido'}), 400
        if not currency or currency not in CURRENCIES:
            return jsonify({'success': False, 'error': 'Moneda inválida'}), 400
        if amount_raw <= 0:
            return jsonify({'success': False, 'error': 'Monto debe ser positivo'}), 400
        if tipo not in BankMovement.LABELS:
            return jsonify({'success': False, 'error': 'Tipo de movimiento inválido'}), 400

        # Determinar signo
        positive_types = {'ajuste_entrada', 'transfer_entrada', 'saldo_inicial'}
        amount = amount_raw if tipo in positive_types else -amount_raw

        acct_name = _bank_account_name(bank_key, currency)
        bb = BankBalance.query.filter_by(bank_name=acct_name).first()
        if not bb:
            return jsonify({'success': False, 'error': f'Cuenta {acct_name} no encontrada'}), 404

        # Actualizar BankBalance
        if currency == 'USD':
            bb.balance_usd = max(float(bb.balance_usd) + amount, 0.0)
            bal_after = float(bb.balance_usd)
        else:
            bb.balance_pen = max(float(bb.balance_pen) + amount, 0.0)
            bal_after = float(bb.balance_pen)
        bb.updated_at = now_peru()
        bb.updated_by = current_user.id

        # Crear BankMovement
        mv = BankMovement(
            movement_date  = now_peru(),
            bank_name      = acct_name,
            bank_key       = bank_key,
            currency       = currency,
            amount         = round(amount, 2),
            movement_type  = tipo,
            source_type    = 'adjustment',
            description    = desc or f'Ajuste manual — {BankMovement.LABELS.get(tipo, tipo)}',
            reference_code = ref,
            balance_after  = bal_after,
            created_by     = current_user.id,
            closure_date   = date.today(),
        )
        db.session.add(mv)
        db.session.commit()

        return jsonify({
            'success':  True,
            'message':  f'Ajuste registrado: {currency} {amount:+.2f} en {acct_name}',
            'movement': mv.to_dict(),
        })
    except Exception as e:
        db.session.rollback()
        _log.exception('[Treasury] Error en api_ajuste')
        return jsonify({'success': False, 'error': str(e)}), 500


# ── API: Cierre — Calcular ────────────────────────────────────────────────────

@treasury_bp.route('/api/cierre/calcular', methods=['POST'])
@login_required
def api_cierre_calcular():
    _require_master()
    try:
        data       = request.get_json() or {}
        fecha_str  = data.get('fecha', date.today().isoformat())
        fecha      = date.fromisoformat(fecha_str)

        start = datetime.combine(fecha, datetime.min.time())
        end   = start + timedelta(days=1)

        # ── Operaciones completadas en el día ──
        ops_day = Operation.query.filter(
            Operation.status == 'Completada',
            Operation.completed_at >= start,
            Operation.completed_at <  end,
        ).all()
        compras = [o for o in ops_day if o.operation_type == 'Compra']
        ventas  = [o for o in ops_day if o.operation_type == 'Venta']
        vol_usd  = sum(float(o.amount_usd or 0) for o in ops_day)
        buy_usd  = sum(float(o.amount_usd or 0) for o in compras)
        sell_usd = sum(float(o.amount_usd or 0) for o in ventas)
        avg_buy  = (sum(float(o.exchange_rate or 0) * float(o.amount_usd or 0) for o in compras) / buy_usd
                    if buy_usd > 0 else 0)
        avg_sell = (sum(float(o.exchange_rate or 0) * float(o.amount_usd or 0) for o in ventas) / sell_usd
                    if sell_usd > 0 else 0)

        # ── Amarres del día ──
        matches_day = AccountingMatch.query.filter(
            AccountingMatch.status == 'Activo',
            AccountingMatch.created_at >= start,
            AccountingMatch.created_at <  end,
        ).all()
        spread_pen = sum(float(m.profit_pen or 0) for m in matches_day)

        # ── Gastos del día ──
        expenses_pen = _get_today_expenses(fecha)

        # ── Operaciones pendientes ──
        pending_ops = Operation.query.filter(
            Operation.status.in_(['Pendiente', 'En proceso'])
        ).count()

        # ── USD sin amarrar ──
        open_pos = _get_open_position()

        # ── Amarres activos sin batch cerrado ──
        open_matches = AccountingMatch.query.filter(
            AccountingMatch.status == 'Activo',
        ).join(
            AccountingBatch, AccountingMatch.batch_id == AccountingBatch.id, isouter=True
        ).filter(
            db.or_(AccountingMatch.batch_id.is_(None), AccountingBatch.status != 'Cerrado')
        ).count()

        # ── Saldos del sistema por banco ──
        system_balances = _get_system_balances()

        # ── Obtener o crear cierre ──
        closure = DailyClosure.query.filter_by(closure_date=fecha).first()
        if not closure:
            closure = DailyClosure(
                closure_date = fecha,
                status       = DailyClosure.STATUS_BORRADOR,
                created_by   = current_user.id,
            )
            db.session.add(closure)

        closure.system_balances        = system_balances
        closure.operations_completed   = len(ops_day)
        closure.total_volume_usd       = round(vol_usd,   2)
        closure.total_bought_usd       = round(buy_usd,   2)
        closure.total_sold_usd         = round(sell_usd,  2)
        closure.avg_buy_rate           = round(avg_buy,   4)
        closure.avg_sell_rate          = round(avg_sell,  4)
        closure.gross_spread_pen       = round(spread_pen, 2)
        closure.expenses_pen           = round(expenses_pen, 2)
        closure.net_profit_pen         = round(spread_pen - expenses_pen, 2)
        closure.pending_operations     = pending_ops
        closure.unmatched_completed_usd = round(open_pos['neto_usd'], 2)
        closure.open_matches           = open_matches
        db.session.commit()

        return jsonify({'success': True, 'cierre': closure.to_dict()})
    except Exception as e:
        db.session.rollback()
        _log.exception('[Treasury] Error en api_cierre_calcular')
        return jsonify({'success': False, 'error': str(e)}), 500


# ── API: Cierre — Validar (guardar saldos reales) ─────────────────────────────

@treasury_bp.route('/api/cierre/validar', methods=['POST'])
@login_required
def api_cierre_validar():
    _require_master()
    try:
        data          = request.get_json() or {}
        fecha_str     = data.get('fecha', date.today().isoformat())
        fecha         = date.fromisoformat(fecha_str)
        real_balances = data.get('saldos_reales', {})
        notes         = data.get('notas', '')

        closure = DailyClosure.query.filter_by(closure_date=fecha).first()
        if not closure:
            return jsonify({'success': False, 'error': 'Primero calcule el cierre del día'}), 400

        closure.validated_balances = real_balances
        closure.notes              = notes
        closure.compute_differences()
        db.session.commit()

        return jsonify({
            'success':         True,
            'has_discrepancies': closure.has_discrepancies,
            'differences':     closure.differences,
            'max_diff_usd':    float(closure.max_discrepancy_usd or 0),
            'max_diff_pen':    float(closure.max_discrepancy_pen or 0),
            'cierre':          closure.to_dict(),
        })
    except Exception as e:
        db.session.rollback()
        _log.exception('[Treasury] Error en api_cierre_validar')
        return jsonify({'success': False, 'error': str(e)}), 500


# ── API: Cierre — Confirmar ───────────────────────────────────────────────────

@treasury_bp.route('/api/cierre/confirmar', methods=['POST'])
@login_required
def api_cierre_confirmar():
    _require_master()
    try:
        data              = request.get_json() or {}
        fecha_str         = data.get('fecha', date.today().isoformat())
        fecha             = date.fromisoformat(fecha_str)
        discrepancy_reason = data.get('motivo_discrepancia', '')

        closure = DailyClosure.query.filter_by(closure_date=fecha).first()
        if not closure:
            return jsonify({'success': False, 'error': 'Cierre no encontrado'}), 404
        if closure.is_validated:
            return jsonify({'success': False, 'error': 'Cierre ya fue validado'}), 400
        if not closure.validated_balances:
            return jsonify({'success': False, 'error': 'Debe ingresar saldos reales antes de confirmar'}), 400
        if closure.has_discrepancies and not discrepancy_reason:
            return jsonify({'success': False, 'error': 'Hay discrepancias — debe ingresar el motivo'}), 400

        closure.status              = DailyClosure.STATUS_VALIDADO
        closure.discrepancy_reason  = discrepancy_reason
        closure.validated_by        = current_user.id
        closure.validated_at        = now_peru()

        # Marcar movimientos del día como validados
        BankMovement.query.filter_by(closure_date=fecha).update({'is_validated': True})

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Cierre del {fecha.strftime("%d/%m/%Y")} confirmado correctamente.',
            'cierre':  closure.to_dict(),
        })
    except Exception as e:
        db.session.rollback()
        _log.exception('[Treasury] Error en api_cierre_confirmar')
        return jsonify({'success': False, 'error': str(e)}), 500


# ── API: Cierre — Obtener por fecha ──────────────────────────────────────────

@treasury_bp.route('/api/cierre/<fecha_str>')
@login_required
def api_cierre_get(fecha_str):
    _require_master()
    try:
        fecha   = date.fromisoformat(fecha_str)
        closure = DailyClosure.query.filter_by(closure_date=fecha).first()
        if not closure:
            return jsonify({'success': False, 'found': False}), 200
        return jsonify({'success': True, 'found': True, 'cierre': closure.to_dict()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@treasury_bp.route('/api/cierre/historial')
@login_required
def api_cierre_historial():
    _require_master()
    try:
        page     = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 30))
        cierres  = DailyClosure.query.order_by(
            DailyClosure.closure_date.desc()
        ).offset((page - 1) * per_page).limit(per_page).all()
        total = DailyClosure.query.count()
        return jsonify({
            'success':  True,
            'total':    total,
            'page':     page,
            'cierres':  [c.to_dict() for c in cierres],
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── API: Reconciliación ───────────────────────────────────────────────────────

@treasury_bp.route('/api/reconciliacion')
@login_required
def api_reconciliacion():
    """
    Verifica coherencia entre BankBalance (saldo rápido) y la suma de
    BankMovement (fuente de verdad). Expone diferencias.
    """
    _require_master()
    try:
        resultados = []
        for bk in BANKS:
            for cur in CURRENCIES:
                acct_name = _bank_account_name(bk, cur)
                bb = BankBalance.query.filter_by(bank_name=acct_name).first()
                saldo_balance = float((bb.balance_usd if cur == 'USD' else bb.balance_pen) or 0) if bb else 0.0

                saldo_movs = BankMovement.compute_running_balance(bk, cur)
                diff = round(saldo_balance - saldo_movs, 2)

                resultados.append({
                    'banco':         bk,
                    'moneda':        cur,
                    'acct_name':     acct_name,
                    'saldo_balance': round(saldo_balance, 2),
                    'saldo_movs':    round(saldo_movs,    2),
                    'diferencia':    diff,
                    'coherente':     abs(diff) < 0.02,
                })

        incoherentes = [r for r in resultados if not r['coherente']]
        return jsonify({
            'success':      True,
            'resultados':   resultados,
            'incoherentes': incoherentes,
            'todo_coherente': len(incoherentes) == 0,
        })
    except Exception as e:
        _log.exception('[Treasury] Error en api_reconciliacion')
        return jsonify({'success': False, 'error': str(e)}), 500


# ── API: Libro de Amarres ─────────────────────────────────────────────────────

@treasury_bp.route('/api/libros/amarres')
@login_required
def api_libro_amarres():
    _require_master()
    try:
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
            q = q.filter(AccountingMatch.created_at >= fi)
        if fecha_fin:
            ff = datetime.combine(date.fromisoformat(fecha_fin), datetime.max.time())
            q = q.filter(AccountingMatch.created_at <= ff)

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
                'matched_usd':      float(m.matched_amount_usd or 0),
                'buy_op_id':        buy_op.operation_id  if buy_op  else None,
                'sell_op_id':       sell_op.operation_id if sell_op else None,
                'buy_client':       buy_op.client.full_name  if buy_op  and buy_op.client  else '—',
                'sell_client':      sell_op.client.full_name if sell_op and sell_op.client else '—',
                'buy_tc':           float(m.buy_exchange_rate  or 0),
                'sell_tc':          float(m.sell_exchange_rate or 0),
                'buy_base':         float(m.buy_base_rate  or m.buy_exchange_rate  or 0),
                'sell_base':        float(m.sell_base_rate or m.sell_exchange_rate or 0),
                'total_profit_pen': float(m.profit_pen         or 0),
                'house_profit_pen': float(m.house_profit_pen   or 0),
                'trader_buy_pen':   float(m.trader_buy_profit_pen  or 0),
                'trader_sell_pen':  float(m.trader_sell_profit_pen or 0),
                'batch_id':         m.batch_id,
                'match_type':       m.match_type,
            })

        return jsonify({
            'success':   True,
            'total':     total,
            'page':      page,
            'per_page':  per_page,
            'pages':     (total + per_page - 1) // per_page,
            'totales': {
                'profit_pen':       round(float(totales[0] or 0), 2),
                'house_profit_pen': round(float(totales[1] or 0), 2),
                'matched_usd':      round(float(totales[2] or 0), 2),
            },
            'items': items,
        })
    except Exception as e:
        _log.exception('[Treasury] Error en api_libro_amarres')
        return jsonify({'success': False, 'error': str(e)}), 500
