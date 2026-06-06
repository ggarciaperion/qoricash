"""
FinanceEngine V2 — Motor Financiero Unificado de QoriCash
=========================================================
FUENTE ÚNICA DE VERDAD para todos los cálculos financieros del sistema.

Regla: ningún route ni template calcula datos financieros directamente.
       Todos consumen este servicio.

Fuentes de datos por concepto:
  Saldos bancarios   → BankBalance (caché actualizado por apply_operation)
  Posición abierta   → Operation JOIN AccountingMatch (cálculo derivado SQL)
  Utilidad realizada → AccountingMatch.profit_pen (única fuente)
  Cierre diario      → DailyClosure
  Reconciliación     → BankBalance vs SUM(BankMovement)

Nota sobre el ledger histórico:
  BankMovement es nuevo. Operaciones anteriores a su activación no tienen
  registros en el ledger → reconciliación mostrará diferencias hasta que
  se registren los saldos de apertura (ver activar_ledger()).
"""
import logging
from datetime import date, datetime, timedelta

from sqlalchemy import func

from app.extensions import db
from app.utils.formatters import now_peru

_log = logging.getLogger(__name__)

BANKS      = ['BCP', 'INTERBANK', 'BANBIF']
CURRENCIES = ['USD', 'PEN']


# ── Helpers internos ──────────────────────────────────────────────────────────

def _safe(fn, default, label):
    """Ejecuta fn(); si falla retorna default y loggea el error."""
    try:
        return fn()
    except Exception as exc:
        _log.error(f'[FinanceEngine] {label}: {exc}')
        return default


# ── Motor principal ───────────────────────────────────────────────────────────

class FinanceEngine:

    # ── 1. Saldos bancarios ───────────────────────────────────────────────────

    @staticmethod
    def get_balances() -> dict:
        """
        Saldos actuales por banco y moneda.
        Fuente: BankBalance (caché).

        Returns:
            by_bank:    {BCP: {USD: x, PEN: y}, INTERBANK: {...}, BANBIF: {...}}
            total_usd:  suma USD todas las cuentas
            total_pen:  suma PEN todas las cuentas
            accounts:   lista plana de cuentas con detalle
        """
        from app.models import BankBalance

        by_bank  = {b: {'USD': 0.0, 'PEN': 0.0} for b in BANKS}
        accounts = []

        for bb in BankBalance.query.all():
            for bk in BANKS:
                if not bb.bank_name.startswith(bk):
                    continue
                for cur in CURRENCIES:
                    if cur not in bb.bank_name:
                        continue
                    bal = float(bb.balance_usd if cur == 'USD' else bb.balance_pen)
                    by_bank[bk][cur] += bal
                    accounts.append({
                        'bank':         bk,
                        'currency':     cur,
                        'balance':      round(bal, 2),
                        'account_name': bb.bank_name,
                        'updated_at':   bb.updated_at.isoformat() if bb.updated_at else None,
                    })

        total_usd = round(sum(v['USD'] for v in by_bank.values()), 2)
        total_pen = round(sum(v['PEN'] for v in by_bank.values()), 2)

        return {
            'by_bank':   by_bank,
            'total_usd': total_usd,
            'total_pen': total_pen,
            'accounts':  accounts,
        }

    # ── 2. Posición abierta ───────────────────────────────────────────────────

    @staticmethod
    def get_open_position() -> dict:
        """
        Posición abierta: operaciones completadas con USD sin amarrar.

        FÓRMULA (por operación):
          Si Compra: open = amount_usd − SUM(matched_amount_usd WHERE buy_op = op)
          Si Venta:  open = amount_usd − SUM(matched_amount_usd WHERE sell_op = op)

        Usa subqueries SQL — NO itera objetos Python.

        Returns:
            items:               lista de posiciones abiertas con detalle y aging
            total_compras_open:  USD compra sin amarrar
            total_ventas_open:   USD venta sin amarrar
            neto_usd:            compras_open − ventas_open
            total_items:         cantidad de operaciones con posición abierta
        """
        from app.models import Operation, AccountingMatch

        # Cuánto ya está amarrado por el lado compra
        buy_sq = db.session.query(
            AccountingMatch.buy_operation_id.label('op_id'),
            func.sum(AccountingMatch.matched_amount_usd).label('matched'),
        ).filter(AccountingMatch.status == 'Activo').group_by(
            AccountingMatch.buy_operation_id
        ).subquery()

        # Cuánto ya está amarrado por el lado venta
        sell_sq = db.session.query(
            AccountingMatch.sell_operation_id.label('op_id'),
            func.sum(AccountingMatch.matched_amount_usd).label('matched'),
        ).filter(AccountingMatch.status == 'Activo').group_by(
            AccountingMatch.sell_operation_id
        ).subquery()

        rows = db.session.query(
            Operation,
            func.coalesce(buy_sq.c.matched,  0).label('buy_matched'),
            func.coalesce(sell_sq.c.matched, 0).label('sell_matched'),
        ).outerjoin(
            buy_sq,  Operation.id == buy_sq.c.op_id
        ).outerjoin(
            sell_sq, Operation.id == sell_sq.c.op_id
        ).filter(
            Operation.status == 'Completada'
        ).order_by(
            Operation.completed_at.asc()
        ).all()

        today = now_peru().date()
        items          = []
        total_compras  = 0.0
        total_ventas   = 0.0

        for op, buy_matched, sell_matched in rows:
            matched  = float(buy_matched if op.operation_type == 'Compra' else sell_matched)
            open_usd = round(float(op.amount_usd or 0) - matched, 2)
            if open_usd < 0.01:
                continue

            completed_date = op.completed_at.date() if op.completed_at else today
            days_open      = (today - completed_date).days

            items.append({
                'id':           op.id,
                'operation_id': op.operation_id,
                'type':         op.operation_type,
                'client':       op.client.full_name if op.client else '—',
                'amount_usd':   round(float(op.amount_usd or 0), 2),
                'matched_usd':  round(matched, 2),
                'open_usd':     open_usd,
                'exchange_rate':float(op.exchange_rate or 0),
                'base_rate':    float(op.base_rate or 0) if op.base_rate else None,
                'completed_at': op.completed_at.isoformat() if op.completed_at else None,
                'days_open':    days_open,
                'is_aged':      days_open >= 5,
            })

            if op.operation_type == 'Compra':
                total_compras += open_usd
            else:
                total_ventas += open_usd

        return {
            'items':              items,
            'total_compras_open': round(total_compras, 2),
            'total_ventas_open':  round(total_ventas,  2),
            'neto_usd':           round(total_compras - total_ventas, 2),
            'total_items':        len(items),
        }

    # ── 3. Utilidad realizada ─────────────────────────────────────────────────

    @staticmethod
    def get_profit(fecha_ini=None, fecha_fin=None) -> dict:
        """
        Utilidad realizada desde AccountingMatch.

        FUENTE ÚNICA: AccountingMatch.profit_pen, house_profit_pen,
                      trader_buy_profit_pen, trader_sell_profit_pen

        Args:
            fecha_ini: date o datetime inicio del período (None = todo el historial)
            fecha_fin: date o datetime fin del período   (None = hoy inclusive)

        Returns:
            total_pen, house_pen, trader_buy_pen, trader_sell_pen,
            trader_total_pen, match_count
        """
        from app.models import AccountingMatch

        q = AccountingMatch.query.filter(AccountingMatch.status == 'Activo')

        if fecha_ini is not None:
            start = (datetime.combine(fecha_ini, datetime.min.time())
                     if isinstance(fecha_ini, date) else fecha_ini)
            q = q.filter(AccountingMatch.created_at >= start)

        if fecha_fin is not None:
            end = (datetime.combine(fecha_fin, datetime.max.time())
                   if isinstance(fecha_fin, date) else fecha_fin)
            q = q.filter(AccountingMatch.created_at <= end)

        row = q.with_entities(
            func.sum(AccountingMatch.profit_pen),
            func.sum(AccountingMatch.house_profit_pen),
            func.sum(AccountingMatch.trader_buy_profit_pen),
            func.sum(AccountingMatch.trader_sell_profit_pen),
            func.count(AccountingMatch.id),
        ).one()

        total       = float(row[0] or 0)
        house       = float(row[1] or 0)
        trader_buy  = float(row[2] or 0)
        trader_sell = float(row[3] or 0)
        count       = int(row[4]   or 0)

        return {
            'total_pen':        round(total,               2),
            'house_pen':        round(house,               2),
            'trader_buy_pen':   round(trader_buy,          2),
            'trader_sell_pen':  round(trader_sell,         2),
            'trader_total_pen': round(trader_buy + trader_sell, 2),
            'match_count':      count,
        }

    # ── 4. Operaciones del día ────────────────────────────────────────────────

    @staticmethod
    def get_daily_ops(fecha: date = None) -> dict:
        """Resumen de operaciones completadas en la fecha dada."""
        from app.models import Operation

        if fecha is None:
            fecha = now_peru().date()
        start = datetime.combine(fecha, datetime.min.time())
        end   = start + timedelta(days=1)

        ops      = Operation.query.filter(
            Operation.status == 'Completada',
            Operation.completed_at >= start,
            Operation.completed_at <  end,
        ).all()

        compras  = [o for o in ops if o.operation_type == 'Compra']
        ventas   = [o for o in ops if o.operation_type == 'Venta']
        vol_usd  = sum(float(o.amount_usd or 0) for o in ops)
        buy_usd  = sum(float(o.amount_usd or 0) for o in compras)
        sell_usd = sum(float(o.amount_usd or 0) for o in ventas)

        avg_buy  = (sum(float(o.exchange_rate or 0) * float(o.amount_usd or 0) for o in compras) / buy_usd
                    if buy_usd  > 0 else 0)
        avg_sell = (sum(float(o.exchange_rate or 0) * float(o.amount_usd or 0) for o in ventas) / sell_usd
                    if sell_usd > 0 else 0)

        return {
            'fecha':         fecha.isoformat(),
            'total_ops':     len(ops),
            'compras_count': len(compras),
            'ventas_count':  len(ventas),
            'volume_usd':    round(vol_usd,  2),
            'buy_usd':       round(buy_usd,  2),
            'sell_usd':      round(sell_usd, 2),
            'avg_buy_rate':  round(avg_buy,  4),
            'avg_sell_rate': round(avg_sell, 4),
        }

    # ── 5. Operaciones pendientes ─────────────────────────────────────────────

    @staticmethod
    def get_pending_ops() -> dict:
        """Operaciones no completadas con flag de criticidad (>4h)."""
        from app.models import Operation
        from app.utils.formatters import now_peru

        ops = Operation.query.filter(
            Operation.status.in_(['Pendiente', 'En proceso'])
        ).order_by(Operation.created_at.asc()).all()

        now   = now_peru()
        items = []
        for op in ops:
            horas = ((now - op.created_at).total_seconds() / 3600
                     if op.created_at else 0)
            items.append({
                'id':           op.id,
                'operation_id': op.operation_id,
                'status':       op.status,
                'type':         op.operation_type,
                'amount_usd':   float(op.amount_usd or 0),
                'horas':        round(horas, 1),
                'client':       op.client.full_name if op.client else '—',
                'is_critical':  horas > 4,
            })

        return {
            'total':    len(items),
            'criticas': [i for i in items if i['is_critical']],
            'items':    items[:20],
        }

    # ── 6. Estado del cierre ──────────────────────────────────────────────────

    @staticmethod
    def get_closure_status() -> dict:
        """Estado del cierre diario más reciente."""
        from app.models import DailyClosure

        today     = now_peru().date()
        last      = DailyClosure.query.order_by(DailyClosure.closure_date.desc()).first()
        today_cls = DailyClosure.query.filter_by(closure_date=today).first()

        missing = 0
        if last:
            delta   = (today - last.closure_date).days
            missing = max(0, delta - 1) if last.is_validated else delta

        return {
            'today_closure':    today_cls.to_dict() if today_cls else None,
            'last_date':        last.closure_date.isoformat() if last else None,
            'last_validated':   last.is_validated if last else False,
            'missing_days':     missing,
            'requires_closure': missing > 0,
            'today_date':       today.isoformat(),
        }

    # ── 7. Reconciliación ─────────────────────────────────────────────────────

    @staticmethod
    def get_reconciliation() -> list:
        """
        Compara BankBalance (caché) vs SUM(BankMovement) (ledger).

        Si ledger_empty=True significa que el ledger aún no tiene saldos
        de apertura para esa cuenta — usar activar_ledger() para corregir.
        """
        from app.models import BankBalance, BankMovement
        from app.config.bank_accounts import ALLOWED_BANK_NAMES

        result = []
        for acct_name in ALLOWED_BANK_NAMES:
            bb = BankBalance.query.filter_by(bank_name=acct_name).first()
            if not bb:
                continue

            parts      = acct_name.split()
            bank_key   = parts[0]
            currency   = parts[1]
            bal_cache  = float(bb.balance_usd if currency == 'USD' else bb.balance_pen)
            bal_ledger = BankMovement.compute_running_balance(bank_key, currency)
            diff       = round(bal_cache - bal_ledger, 2)

            result.append({
                'account_name':  acct_name,
                'bank':          bank_key,
                'currency':      currency,
                'balance_cache': round(bal_cache,  2),
                'balance_ledger':round(bal_ledger, 2),
                'diff':          diff,
                'coherent':      abs(diff) < 0.02,
                'ledger_empty':  bal_ledger == 0.0 and bal_cache > 0.01,
            })

        return result

    # ── 8. Snapshot completo ──────────────────────────────────────────────────

    @staticmethod
    def get_full_snapshot() -> dict:
        """
        Snapshot completo para el dashboard de Control Financiero.
        Cada sección es independiente: un error no rompe el resto.
        """
        today = now_peru().date()

        _profit_default = {
            'total_pen': 0, 'house_pen': 0,
            'trader_buy_pen': 0, 'trader_sell_pen': 0,
            'trader_total_pen': 0, 'match_count': 0,
        }
        _ops_default = {
            'fecha': today.isoformat(), 'total_ops': 0,
            'compras_count': 0, 'ventas_count': 0,
            'volume_usd': 0, 'buy_usd': 0, 'sell_usd': 0,
            'avg_buy_rate': 0, 'avg_sell_rate': 0,
        }

        balances    = _safe(FinanceEngine.get_balances,
                            {'by_bank': {}, 'total_usd': 0, 'total_pen': 0, 'accounts': []},
                            'balances')
        position    = _safe(FinanceEngine.get_open_position,
                            {'items': [], 'total_compras_open': 0, 'total_ventas_open': 0,
                             'neto_usd': 0, 'total_items': 0},
                            'position')
        profit_all  = _safe(FinanceEngine.get_profit, _profit_default, 'profit_all')
        profit_today = _safe(lambda: FinanceEngine.get_profit(today, today),
                             _profit_default, 'profit_today')
        daily_ops   = _safe(lambda: FinanceEngine.get_daily_ops(today), _ops_default, 'daily_ops')
        pending     = _safe(FinanceEngine.get_pending_ops,
                            {'total': 0, 'criticas': [], 'items': []}, 'pending')
        closure     = _safe(FinanceEngine.get_closure_status,
                            {'today_closure': None, 'last_date': None, 'last_validated': False,
                             'missing_days': 0, 'requires_closure': False,
                             'today_date': today.isoformat()},
                            'closure')

        # Alertas consolidadas
        alerts = []
        if closure['requires_closure']:
            d = closure['missing_days']
            alerts.append({
                'level': 'danger',
                'msg':   f'Cierre pendiente — {d} día(s) sin validar',
            })
        if pending['criticas']:
            n = len(pending['criticas'])
            alerts.append({
                'level': 'warning',
                'msg':   f'{n} operación(es) sin completar con más de 4 horas',
            })
        aged = [p for p in position['items'] if p['is_aged']]
        if aged:
            n = len(aged)
            alerts.append({
                'level': 'warning',
                'msg':   f'{n} posición(es) abierta(s) con 5 o más días sin amarrar',
            })

        return {
            'ok':        True,
            'timestamp': now_peru().isoformat(),
            'balances':  balances,
            'position':  position,
            'profit':    {'all_time': profit_all, 'today': profit_today},
            'daily_ops': daily_ops,
            'pending':   pending,
            'closure':   closure,
            'alerts':    alerts,
        }

    # ── 9. Activar ledger (saldo inicial) ─────────────────────────────────────

    @staticmethod
    def activar_ledger(user_id: int) -> dict:
        """
        Registra saldos de apertura en BankMovement para todas las cuentas.

        Solo actúa sobre cuentas que aún no tienen movimientos en el ledger
        (ledger_empty=True). Para cuentas con movimientos existentes, no hace nada.

        Retorna: {activated: [lista], skipped: [lista], errors: [lista]}
        """
        from app.models import BankBalance, BankMovement
        from app.config.bank_accounts import ALLOWED_BANK_NAMES
        from app.utils.formatters import now_peru

        activated = []
        skipped   = []
        errors    = []

        for acct_name in ALLOWED_BANK_NAMES:
            try:
                bb = BankBalance.query.filter_by(bank_name=acct_name).first()
                if not bb:
                    skipped.append(f'{acct_name}: sin registro BankBalance')
                    continue

                parts     = acct_name.split()
                bank_key  = parts[0]
                currency  = parts[1]
                bal_cache = float(bb.balance_usd if currency == 'USD' else bb.balance_pen)

                # Verificar si ya tiene movimientos
                existing = BankMovement.query.filter_by(
                    bank_key=bank_key, currency=currency
                ).first()
                if existing:
                    skipped.append(f'{acct_name}: ya tiene {BankMovement.query.filter_by(bank_key=bank_key, currency=currency).count()} movimiento(s)')
                    continue

                if bal_cache <= 0:
                    skipped.append(f'{acct_name}: saldo cero, sin apertura')
                    continue

                mv = BankMovement(
                    movement_date  = now_peru(),
                    bank_name      = acct_name,
                    bank_key       = bank_key,
                    currency       = currency,
                    amount         = round(bal_cache, 2),
                    movement_type  = BankMovement.TYPE_SALDO_INICIAL,
                    source_type    = 'ledger_activation',
                    description    = f'Saldo de apertura al activar el ledger — {now_peru().date().isoformat()}',
                    balance_after  = round(bal_cache, 2),
                    closure_date   = now_peru().date(),
                    created_by     = user_id,
                )
                db.session.add(mv)
                activated.append(f'{acct_name}: apertura {currency} {bal_cache:,.2f}')

            except Exception as exc:
                errors.append(f'{acct_name}: {exc}')

        try:
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            errors.append(f'commit: {exc}')

        return {'activated': activated, 'skipped': skipped, 'errors': errors}
