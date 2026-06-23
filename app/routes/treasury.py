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

from sqlalchemy import or_

from app.extensions import db
from app.models import (
    BankBalance, Operation, AccountingMatch, AccountingBatch,
    BankMovement, DailyClosure, JournalEntry, ExpenseRecord,
)
from app.models.user import User
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
    Saldos del sistema por banco y moneda — fuente: BankMovement (suma acumulada).
    Coincide con la columna 'Teórico' de Control de Apertura y Cierre.
    """
    balances = {b: {c: 0.0 for c in CURRENCIES} for b in BANKS}
    for bk in BANKS:
        for cur in CURRENCIES:
            balances[bk][cur] = round(BankMovement.compute_running_balance(bk, cur), 2)
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
        fecha = now_peru().date()
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
        fecha = now_peru().date()
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


def _dias_laborables(desde, hasta) -> int:
    """
    Cuenta días laborables entre dos fechas (excluyendo domingos).
    QoriCash opera lunes a sábado; domingo no se trabaja.
    """
    total = 0
    d = desde
    while d < hasta:
        if d.weekday() != 6:  # 6 = domingo
            total += 1
        d += timedelta(days=1)
    return total


def _get_closure_status() -> dict:
    """Estado del cierre más reciente y si hay cierre pendiente hoy.
    Los domingos nunca requieren apertura ni cierre — no se trabaja."""
    today = now_peru().date()

    # Domingo: no se opera, sin requerimiento de cierre
    if today.weekday() == 6:
        last_closure = DailyClosure.query.order_by(DailyClosure.closure_date.desc()).first()
        today_closure = DailyClosure.query.filter_by(closure_date=today).first()
        return {
            'today_closure':    today_closure.to_dict() if today_closure else None,
            'last_validated':   last_closure.closure_date.isoformat() if last_closure and last_closure.is_validated else None,
            'missing_days':     0,
            'requires_closure': False,
            'today_date':       today.isoformat(),
            'is_sunday':        True,
        }

    last_closure = DailyClosure.query.order_by(DailyClosure.closure_date.desc()).first()
    today_closure = DailyClosure.query.filter_by(closure_date=today).first()

    missing_days = 0
    if last_closure:
        if last_closure.is_validated:
            # Contar días laborables entre el último cierre y hoy (sin incluir hoy)
            missing_days = max(0, _dias_laborables(last_closure.closure_date, today) - 1)
        else:
            missing_days = _dias_laborables(last_closure.closure_date, today)
    else:
        missing_days = 0  # primer día, sin historial

    return {
        'today_closure':    today_closure.to_dict() if today_closure else None,
        'last_validated':   last_closure.closure_date.isoformat() if last_closure and last_closure.is_validated else None,
        'missing_days':     missing_days,
        'requires_closure': missing_days > 0,
        'today_date':       today.isoformat(),
        'is_sunday':        False,
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

    today       = now_peru().date()
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
        fecha = date.fromisoformat(fecha_str) if fecha_str else now_peru().date()

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
        movs  = q.order_by(BankMovement.movement_date.desc(), BankMovement.id.desc()).offset(
            (page - 1) * per_page
        ).limit(per_page).all()

        # Totales del filtro
        totales = q.with_entities(
            func.sum(BankMovement.amount)
        ).scalar()

        # ── Saldo acumulado dinámico ──────────────────────────────────────────
        # Solo calculable cuando se filtra por banco+moneda específicos,
        # de lo contrario el saldo no tiene contexto semántico.
        computed_balances = {}
        if bank_key and currency and movs:
            oldest = movs[-1]  # último elemento = más antiguo (orden DESC)
            # Suma de todos los movimientos ANTERIORES (más nuevos en el tiempo)
            # a la página actual, para ese banco+moneda
            sum_before = db.session.query(func.sum(BankMovement.amount)).filter(
                BankMovement.bank_key == bank_key,
                BankMovement.currency == currency,
                or_(
                    BankMovement.movement_date > oldest.movement_date,
                    and_(
                        BankMovement.movement_date == oldest.movement_date,
                        BankMovement.id > oldest.id,
                    )
                )
            ).scalar() or 0

            running = float(sum_before)
            for mv in reversed(movs):  # más antiguo → más nuevo
                running = round(running + float(mv.amount), 2)
                computed_balances[mv.id] = running

        # ── Trader por operación (batch, 2 queries) ────────────────────────
        op_ids = [mv.operation_id for mv in movs if mv.operation_id]
        op_map = {}
        trader_map = {}
        if op_ids:
            ops = Operation.query.filter(Operation.id.in_(op_ids)).all()
            op_map = {op.id: op for op in ops}
            user_ids = list({op.assigned_operator_id for op in ops if op.assigned_operator_id})
            if user_ids:
                users = User.query.filter(User.id.in_(user_ids)).all()
                trader_map = {u.id: u.username for u in users}

        def _enrich(mv):
            d = mv.to_dict()
            # Saldo acumulado calculado dinámicamente
            if mv.id in computed_balances:
                d['balance_after'] = computed_balances[mv.id]
            # Trader del operador asignado a la operación
            op = op_map.get(mv.operation_id)
            d['trader_name'] = (
                trader_map.get(op.assigned_operator_id)
                if op and op.assigned_operator_id else None
            )
            return d

        return jsonify({
            'success':   True,
            'total':     total,
            'page':      page,
            'per_page':  per_page,
            'pages':     (total + per_page - 1) // per_page,
            'net_amount': round(float(totales or 0), 2),
            'movimientos': [_enrich(m) for m in movs],
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
            closure_date   = now_peru().date(),
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
        fecha_str  = data.get('fecha', now_peru().date().isoformat())
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
        fecha_str     = data.get('fecha', now_peru().date().isoformat())
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
        fecha_str         = data.get('fecha', now_peru().date().isoformat())
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


# ── API: Cierre — Reabrir (solo Master) ──────────────────────────────────────

@treasury_bp.route('/api/cierre/reabrir', methods=['POST'])
@login_required
def api_cierre_reabrir():
    """Revierte un cierre validado a borrador (solo rol Master)."""
    if current_user.role not in ALLOWED_ROLES:
        return jsonify({'success': False, 'error': 'Sin permisos para reabrir un cierre'}), 403
    try:
        data      = request.get_json() or {}
        fecha_str = data.get('fecha', now_peru().date().isoformat())
        fecha     = date.fromisoformat(fecha_str)

        closure = DailyClosure.query.filter_by(closure_date=fecha).first()
        if not closure:
            return jsonify({'success': False, 'error': 'Cierre no encontrado'}), 404
        if not closure.is_validated:
            return jsonify({'success': False, 'error': 'El cierre ya está en borrador'}), 400

        closure.status       = DailyClosure.STATUS_BORRADOR
        closure.validated_by = None
        closure.validated_at = None

        BankMovement.query.filter_by(closure_date=fecha).update({'is_validated': False})

        db.session.commit()
        _log.info(f'[Treasury] Cierre {fecha} reabierto por user {current_user.id}')

        return jsonify({
            'success': True,
            'message': f'Cierre del {fecha.strftime("%d/%m/%Y")} reabierto. Puedes volver a validarlo.',
            'cierre':  closure.to_dict(),
        })
    except Exception as e:
        db.session.rollback()
        _log.exception('[Treasury] Error en api_cierre_reabrir')
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


@treasury_bp.route('/api/ops-sin-movimientos')
@login_required
def api_ops_sin_movimientos():
    """
    Monitoreo: operaciones Completadas sin BankMovements en el ledger.
    Permite detectar fallos silenciosos de apply_operation antes de que
    afecten los reportes de Tesorería.
    """
    _require_master()
    try:
        from sqlalchemy import text
        # Consulta eficiente: ops completadas cuyo id no aparece en bank_movements
        result = db.session.execute(text("""
            SELECT o.id, o.operation_id, o.operation_type,
                   o.amount_usd, o.amount_pen, o.completed_at
            FROM operations o
            WHERE o.status = 'Completada'
              AND NOT EXISTS (
                  SELECT 1 FROM bank_movements bm
                  WHERE bm.operation_id = o.id
                    AND bm.source_type = 'operation'
              )
            ORDER BY o.completed_at DESC
            LIMIT 100
        """))
        rows = result.fetchall()
        ops = [{
            'id':             r[0],
            'operation_id':   r[1],
            'operation_type': r[2],
            'amount_usd':     float(r[3]) if r[3] else 0,
            'amount_pen':     float(r[4]) if r[4] else 0,
            'completed_at':   r[5].isoformat() if r[5] else None,
        } for r in rows]
        return jsonify({
            'success': True,
            'count':   len(ops),
            'ops':     ops,
            'alerta':  len(ops) > 0,
        })
    except Exception as e:
        _log.exception('[Treasury] Error en api_ops_sin_movimientos')
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


# ══════════════════════════════════════════════════════════════════════════════
# TRASLADOS INTERNOS DE FONDOS PROPIOS
# ══════════════════════════════════════════════════════════════════════════════

from decimal import Decimal as _Dec
from app.models.internal_transfer import InternalTransfer
from app.services.accounting.journal_service import _map_bank as _jmap


def _acct_name(bank: str, currency: str) -> str:
    """Nombre canónico de cuenta: 'BCP USD (1917357790119)'."""
    return _bank_account_name(bank, currency)


def _exec_traslado(data: dict, user_id: int) -> dict:
    """
    Lógica central de traslado interno.
    Actualiza BankBalance, crea BankMovements y JournalEntry en una sola
    transacción atómica. Retorna el InternalTransfer guardado.
    """
    from app.models.bank_movement import BankMovement
    from app.services.accounting.journal_service import JournalService

    origin_bank = data['origin_bank'].upper()
    origin_cur  = data['origin_currency'].upper()
    dest_bank   = data['dest_bank'].upper()
    dest_cur    = data['dest_currency'].upper()
    amount      = _Dec(str(data['amount']))
    commission  = _Dec(str(data.get('commission', 0) or 0))
    itf_amt     = _Dec(str(data.get('itf_amount',  0) or 0))
    description = (data.get('description') or '').strip()
    ref_code    = (data.get('reference_code') or '').strip()

    if amount <= 0:
        raise ValueError('El monto debe ser mayor a cero.')
    if commission < 0 or itf_amt < 0:
        raise ValueError('Comisión e ITF no pueden ser negativos.')
    if origin_cur != dest_cur:
        raise ValueError('Solo se permiten traslados en la misma moneda. '
                         'Para conversiones entre monedas use el módulo de operaciones.')

    origin_acct = _acct_name(origin_bank, origin_cur)
    dest_acct   = _acct_name(dest_bank, dest_cur)

    if origin_acct == dest_acct:
        raise ValueError('La cuenta de origen y destino no pueden ser la misma.')

    # ── Verificar saldos ──────────────────────────────────────────────────────
    origin_bb = BankBalance.query.filter_by(bank_name=origin_acct).first()
    dest_bb   = BankBalance.query.filter_by(bank_name=dest_acct).first()

    if not origin_bb:
        raise ValueError(f'Cuenta de origen no encontrada: {origin_acct}')
    if not dest_bb:
        raise ValueError(f'Cuenta de destino no encontrada: {dest_acct}')

    total_debit = amount + commission + itf_amt
    origin_bal  = _Dec(str(origin_bb.balance_usd if origin_cur == 'USD' else origin_bb.balance_pen))
    dest_bal    = _Dec(str(dest_bb.balance_usd   if dest_cur   == 'USD' else dest_bb.balance_pen))

    if origin_bal < total_debit:
        raise ValueError(
            f'Fondos insuficientes en {origin_acct}. '
            f'Disponible: {origin_cur} {float(origin_bal):,.2f} — '
            f'Requerido: {float(total_debit):,.2f}.'
        )

    # ── Actualizar BankBalance ────────────────────────────────────────────────
    if origin_cur == 'USD':
        origin_bb.balance_usd = float(origin_bal - total_debit)
        dest_bb.balance_usd   = float(dest_bal   + amount)
    else:
        origin_bb.balance_pen = float(origin_bal - total_debit)
        dest_bb.balance_pen   = float(dest_bal   + amount)

    # ── BankMovement salida ───────────────────────────────────────────────────
    new_origin_bal = float(origin_bal - total_debit)
    mv_salida = BankMovement(
        movement_date  = now_peru(),
        bank_name      = origin_acct,
        bank_key       = origin_bank,
        currency       = origin_cur,
        amount         = float(-total_debit),
        movement_type  = BankMovement.TYPE_TRANSFER_SALIDA,
        source_type    = 'transfer',
        description    = (f'Traslado → {dest_acct}' + (f' | {description}' if description else '')),
        reference_code = ref_code or None,
        counterpart    = dest_acct,
        balance_after  = round(new_origin_bal, 2),
        created_by     = user_id,
        closure_date   = now_peru().date(),
    )

    # ── BankMovement entrada ──────────────────────────────────────────────────
    new_dest_bal = float(dest_bal + amount)
    mv_entrada = BankMovement(
        movement_date  = now_peru(),
        bank_name      = dest_acct,
        bank_key       = dest_bank,
        currency       = dest_cur,
        amount         = float(amount),
        movement_type  = BankMovement.TYPE_TRANSFER_ENTRADA,
        source_type    = 'transfer',
        description    = (f'Traslado ← {origin_acct}' + (f' | {description}' if description else '')),
        reference_code = ref_code or None,
        counterpart    = origin_acct,
        balance_after  = round(new_dest_bal, 2),
        created_by     = user_id,
        closure_date   = now_peru().date(),
    )

    db.session.add(mv_salida)
    db.session.add(mv_entrada)
    db.session.flush()   # obtener IDs

    # ── Asiento contable (partida doble) ──────────────────────────────────────
    origin_pcge = _jmap(origin_bank, origin_cur)
    dest_pcge   = _jmap(dest_bank,   dest_cur)

    journal_lines = [
        # Destino: DEBE (entra dinero)
        {'account_code': dest_pcge,   'debe': amount,  'haber': _Dec('0'), 'currency': dest_cur},
        # Origen:  HABER (sale dinero total_debit)
        {'account_code': origin_pcge, 'debe': _Dec('0'), 'haber': total_debit, 'currency': origin_cur},
    ]
    if commission > 0:
        journal_lines.append({
            'account_code': '6359',
            'debe':         commission,
            'haber':        _Dec('0'),
            'currency':     origin_cur,
        })
    if itf_amt > 0:
        journal_lines.append({
            'account_code': '6991',
            'debe':         itf_amt,
            'haber':        _Dec('0'),
            'currency':     origin_cur,
        })

    entry = JournalService.create_entry(
        entry_type  = 'traslado_interno',
        description = (f'Traslado {origin_acct} → {dest_acct}'
                       + (f' | {description}' if description else '')),
        lines       = journal_lines,
        source_type = 'transfer',
        source_id   = None,      # se actualiza tras el flush del InternalTransfer
        entry_date  = now_peru().date(),
        created_by  = user_id,
    )

    # ── Crear InternalTransfer ────────────────────────────────────────────────
    transfer = InternalTransfer(
        transfer_code       = InternalTransfer.next_code(),
        origin_bank         = origin_bank,
        origin_currency     = origin_cur,
        origin_account      = origin_acct,
        dest_bank           = dest_bank,
        dest_currency       = dest_cur,
        dest_account        = dest_acct,
        amount              = amount,
        commission          = commission,
        itf_amount          = itf_amt,
        description         = description or None,
        reference_code      = ref_code or None,
        journal_entry_id    = entry.id if entry else None,
        movement_salida_id  = mv_salida.id,
        movement_entrada_id = mv_entrada.id,
        status              = 'activo',
        created_by          = user_id,
    )
    db.session.add(transfer)
    db.session.commit()
    return transfer


# ── UI ────────────────────────────────────────────────────────────────────────

@treasury_bp.route('/traslados/')
@login_required
def traslados():
    _require_master()
    from app.config.bank_accounts import QORICASH_ACCOUNTS
    traslados_list = (InternalTransfer.query
                      .order_by(InternalTransfer.transfer_date.desc())
                      .limit(100).all())
    accounts = [
        {'bank': b, 'currency': c, 'name': _acct_name(b, c)}
        for b, currencies in QORICASH_ACCOUNTS.items()
        for c in currencies
    ]
    # Saldos actuales
    balances = {}
    for acct in accounts:
        bb = BankBalance.query.filter_by(bank_name=acct['name']).first()
        if bb:
            balances[acct['name']] = (float(bb.balance_usd)
                                      if acct['currency'] == 'USD'
                                      else float(bb.balance_pen))
        else:
            balances[acct['name']] = None
    return render_template('treasury/traslados.html',
                           traslados=traslados_list,
                           accounts=accounts,
                           balances=balances)


# ── API ───────────────────────────────────────────────────────────────────────

@treasury_bp.route('/api/traslado', methods=['POST'])
@login_required
def api_crear_traslado():
    _require_master()
    data = request.get_json() or {}
    try:
        transfer = _exec_traslado(data, current_user.id)
        return jsonify({'success': True, 'transfer': transfer.to_dict(),
                        'message': f'Traslado {transfer.transfer_code} registrado.'})
    except ValueError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 400
    except Exception as e:
        db.session.rollback()
        _log.exception('[Treasury] Error en api_crear_traslado')
        return jsonify({'success': False, 'error': str(e)}), 500


@treasury_bp.route('/api/traslados')
@login_required
def api_listar_traslados():
    _require_master()
    page     = request.args.get('page', 1, type=int)
    per_page = 20
    q        = (InternalTransfer.query
                .order_by(InternalTransfer.transfer_date.desc())
                .paginate(page=page, per_page=per_page, error_out=False))
    return jsonify({
        'success': True,
        'items':   [t.to_dict() for t in q.items],
        'total':   q.total,
        'pages':   q.pages,
        'page':    page,
    })


@treasury_bp.route('/api/traslado/<int:transfer_id>/anular', methods=['POST'])
@login_required
def api_anular_traslado(transfer_id):
    _require_master()
    data   = request.get_json() or {}
    reason = (data.get('reason') or '').strip()
    if not reason:
        return jsonify({'success': False, 'error': 'Debe indicar un motivo de anulación.'}), 400

    t = db.get_or_404(InternalTransfer, transfer_id)
    if t.status != 'activo':
        return jsonify({'success': False, 'error': 'El traslado ya está anulado.'}), 400

    try:
        # Revertir saldos en BankBalance
        origin_bb = BankBalance.query.filter_by(bank_name=t.origin_account).first()
        dest_bb   = BankBalance.query.filter_by(bank_name=t.dest_account).first()

        total_debit = float(t.amount) + float(t.commission) + float(t.itf_amount)

        if origin_bb:
            if t.origin_currency == 'USD':
                origin_bb.balance_usd = round(float(origin_bb.balance_usd) + total_debit, 2)
            else:
                origin_bb.balance_pen = round(float(origin_bb.balance_pen) + total_debit, 2)

        if dest_bb:
            if t.dest_currency == 'USD':
                dest_bb.balance_usd = round(float(dest_bb.balance_usd) - float(t.amount), 2)
            else:
                dest_bb.balance_pen = round(float(dest_bb.balance_pen) - float(t.amount), 2)

        # Anular asiento contable
        if t.journal_entry_id:
            from app.models.journal_entry import JournalEntry
            je = JournalEntry.query.get(t.journal_entry_id)
            if je:
                je.status = 'anulado'

        t.status        = 'anulado'
        t.anulado_by    = current_user.id
        t.anulado_at    = now_peru()
        t.anulado_reason= reason
        db.session.commit()

        return jsonify({'success': True, 'message': f'Traslado {t.transfer_code} anulado.'})
    except Exception as e:
        db.session.rollback()
        _log.exception('[Treasury] Error anulando traslado')
        return jsonify({'success': False, 'error': str(e)}), 500
