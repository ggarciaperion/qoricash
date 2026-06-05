"""
Rutas de Posición para QoriCash Trading V2
"""
import logging
import traceback
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app.models import BankBalance, BankBalanceHistory, Operation, User
from app.extensions import db
from app.utils.decorators import require_role
from app.config.bank_accounts import QORICASH_ACCOUNTS
from datetime import datetime

logger = logging.getLogger(__name__)

position_bp = Blueprint('position', __name__)


@position_bp.route('/')
@position_bp.route('/view')
@login_required
@require_role('Master', 'Operador')
def position_view():
    """
    Página de Posición

    Solo accesible para Master y Operador
    Muestra saldos bancarios y control de operaciones
    """
    usd_accounts = [
        (banco, data)
        for banco, monedas in QORICASH_ACCOUNTS.items()
        for moneda, data in monedas.items()
        if moneda == 'USD'
    ]
    pen_accounts = [
        (banco, data)
        for banco, monedas in QORICASH_ACCOUNTS.items()
        for moneda, data in monedas.items()
        if moneda == 'PEN'
    ]
    return render_template(
        'position/view.html',
        user=current_user,
        usd_accounts=usd_accounts,
        pen_accounts=pen_accounts,
    )


@position_bp.route('/api/bank_balances')
@login_required
@require_role('Master', 'Operador')
def get_bank_balances():
    """
    API: Obtener datos de posición del día

    Query params:
        fecha: Fecha en formato YYYY-MM-DD (opcional, por defecto hoy)

    Returns:
        JSON con resumen de posición y listas de operaciones
    """
    try:
        from sqlalchemy import func
        from app.utils.formatters import now_peru
        from datetime import datetime as dt

        # Obtener fecha del query param o usar fecha actual
        fecha_param = request.args.get('fecha')
        if fecha_param:
            try:
                fecha_consulta = dt.strptime(fecha_param, '%Y-%m-%d').date()
            except ValueError:
                fecha_consulta = now_peru().date()
        else:
            fecha_consulta = now_peru().date()

        # Obtener TODAS las operaciones del día (excepto Cancelado)
        # Importante: created_at está almacenado como hora de Peru (sin timezone)
        # Por lo tanto, podemos comparar directamente con la fecha solicitada
        from datetime import datetime as dt, timedelta, time

        # Crear inicio y fin del día en Peru (horario de Perú)
        # Usamos fecha_consulta que ya viene de now_peru().date() cuando no hay parámetro
        inicio_dia = dt.combine(fecha_consulta, time.min)  # 00:00:00
        fin_dia = dt.combine(fecha_consulta, time.max)      # 23:59:59.999999

        demo_id = User.get_demo_user_id()
        ops_query = Operation.query.filter(
            Operation.status != 'Cancelado',
            Operation.created_at >= inicio_dia,
            Operation.created_at <= fin_dia
        )
        if demo_id:
            ops_query = ops_query.filter(Operation.user_id != demo_id)
        all_ops_today = ops_query.all()

        # Inicializar totales
        total_compras_usd = 0.0
        contravalor_compras_pen = 0.0
        total_ventas_usd = 0.0
        contravalor_ventas_pen = 0.0

        # Preparar listas de operaciones para las tablas
        compras_list = []
        ventas_list = []

        # Contadores para métricas adicionales
        total_tc_compras = 0.0
        count_compras = 0
        total_tc_ventas = 0.0
        count_ventas = 0

        # Subtotales por estado
        compras_completadas_usd = 0.0
        compras_pendientes_usd = 0.0
        ventas_completadas_usd = 0.0
        ventas_pendientes_usd = 0.0
        compras_completadas_pen = 0.0
        ventas_completadas_pen = 0.0

        for op in all_ops_today:
            # Calcular tiempo transcurrido desde creación
            tiempo_transcurrido = (now_peru() - op.created_at).total_seconds() / 3600  # en horas

            # Determinar si es operación crítica
            es_critica = False
            razon_critica = []

            # Crítica por antigüedad (más de 24 horas pendiente)
            if op.status in ['Pendiente', 'En proceso'] and tiempo_transcurrido > 24:
                es_critica = True
                razon_critica.append(f'{int(tiempo_transcurrido)}h pendiente')

            # Crítica por monto alto (más de $10,000)
            if float(op.amount_usd) >= 10000:
                es_critica = True
                razon_critica.append(f'Monto alto: ${float(op.amount_usd):,.2f}')

            # Construir datos de la operación
            op_data = {
                'id': op.id,  # ID numérico para el modal
                'operation_id': op.operation_id,  # Código de operación
                'client_name': op.client.full_name if op.client and op.client.full_name else
                              (op.client.razon_social if op.client and op.client.razon_social else 'N/A'),
                'amount_usd': float(op.amount_usd),
                'exchange_rate': float(op.exchange_rate),
                'amount_pen': float(op.amount_pen),
                'status': op.status,
                'created_at': op.created_at.isoformat(),
                'completed_at': op.completed_at.isoformat() if op.completed_at else None,
                'horas_transcurridas': round(tiempo_transcurrido, 1),
                'es_critica': es_critica,
                'razon_critica': ', '.join(razon_critica) if razon_critica else None
            }

            # Clasificar por tipo y sumar totales
            if op.operation_type == 'Compra':
                compras_list.append(op_data)
                total_compras_usd += float(op.amount_usd)
                contravalor_compras_pen += float(op.amount_pen)
                total_tc_compras += float(op.exchange_rate)
                count_compras += 1

                # Subtotales por estado
                if op.status == 'Completada':
                    compras_completadas_usd += float(op.amount_usd)
                    compras_completadas_pen += float(op.amount_pen)
                else:
                    compras_pendientes_usd += float(op.amount_usd)

            else:  # Venta
                ventas_list.append(op_data)
                total_ventas_usd += float(op.amount_usd)
                contravalor_ventas_pen += float(op.amount_pen)
                total_tc_ventas += float(op.exchange_rate)
                count_ventas += 1

                # Subtotales por estado
                if op.status == 'Completada':
                    ventas_completadas_usd += float(op.amount_usd)
                    ventas_completadas_pen += float(op.amount_pen)
                else:
                    ventas_pendientes_usd += float(op.amount_usd)

        # Calcular diferencia y utilidad
        diferencia_usd = total_ventas_usd - total_compras_usd
        utilidad_pen = contravalor_ventas_pen - contravalor_compras_pen
        utilidad_completadas_pen = ventas_completadas_pen - compras_completadas_pen

        # Determinar etiqueta dinámica
        if diferencia_usd > 0:
            etiqueta_diferencia = "VENDIDOS EN"
        elif diferencia_usd < 0:
            etiqueta_diferencia = "COMPRADOS EN"
        else:
            etiqueta_diferencia = "NETEADOS"

        # Calcular TC promedio
        tc_promedio_compras = round(total_tc_compras / count_compras, 4) if count_compras > 0 else 0
        tc_promedio_ventas = round(total_tc_ventas / count_ventas, 4) if count_ventas > 0 else 0

        # Determinar si hay desbalance crítico (>$5000)
        desbalance_critico = abs(diferencia_usd) > 5000

        return jsonify({
            'success': True,
            'fecha': fecha_consulta.isoformat(),
            'posicion': {
                'total_compras_usd': round(total_compras_usd, 2),
                'contravalor_compras_pen': round(contravalor_compras_pen, 2),
                'total_ventas_usd': round(total_ventas_usd, 2),
                'contravalor_ventas_pen': round(contravalor_ventas_pen, 2),
                'diferencia_usd': round(diferencia_usd, 2),
                'etiqueta_diferencia': etiqueta_diferencia,
                'utilidad_pen': round(utilidad_pen, 2),
                'desbalance_critico': desbalance_critico,
                # Métricas adicionales
                'total_operaciones': count_compras + count_ventas,
                'cantidad_compras': count_compras,
                'cantidad_ventas': count_ventas,
                'tc_promedio_compras': tc_promedio_compras,
                'tc_promedio_ventas': tc_promedio_ventas,
                # Subtotales por estado
                'compras_completadas_usd': round(compras_completadas_usd, 2),
                'compras_pendientes_usd': round(compras_pendientes_usd, 2),
                'ventas_completadas_usd': round(ventas_completadas_usd, 2),
                'ventas_pendientes_usd': round(ventas_pendientes_usd, 2),
                'compras_completadas_pen': round(compras_completadas_pen, 2),
                'ventas_completadas_pen': round(ventas_completadas_pen, 2),
                'utilidad_completadas_pen': round(utilidad_completadas_pen, 2)
            },
            'compras': compras_list,
            'ventas': ventas_list
        })

    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f'ERROR EN /api/bank_balances:\n{error_trace}')
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e),
            'details': error_trace
        }), 500


@position_bp.route('/api/update_balance', methods=['POST'])
@login_required
@require_role('Master', 'Operador')
def update_balance():
    """
    API: Actualizar saldo bancario

    POST JSON:
        bank_name: Nombre del banco
        currency: 'USD' o 'PEN'
        amount: Nuevo saldo
    """
    data = request.get_json()

    bank_name = data.get('bank_name')
    currency = data.get('currency')
    amount = data.get('amount', 0)

    if not bank_name or not currency:
        return jsonify({'error': 'Faltan datos requeridos'}), 400

    if currency not in ['USD', 'PEN']:
        return jsonify({'error': 'Moneda inválida'}), 400

    try:
        amount = float(amount)
        if amount < 0:
            return jsonify({'error': 'El saldo no puede ser negativo'}), 400
    except (ValueError, TypeError):
        return jsonify({'error': 'Monto inválido'}), 400

    try:
        from app.utils.formatters import now_peru
        import logging
        logger = logging.getLogger(__name__)

        logger.info(f"Actualizando saldo actual: bank_name={bank_name}, currency={currency}, amount={amount}")

        balance = BankBalance.get_or_create_balance(bank_name)

        if currency == 'USD':
            balance.balance_usd = amount
        else:
            balance.balance_pen = amount

        balance.updated_by = current_user.id
        balance.updated_at = now_peru()

        # Grabar snapshot diario para Libro Caja y Bancos
        today = now_peru().date()
        hist = BankBalanceHistory.query.filter_by(
            snapshot_date=today, bank_name=balance.bank_name
        ).first()
        if not hist:
            hist = BankBalanceHistory(
                snapshot_date=today,
                bank_name=balance.bank_name,
                initial_balance_usd=float(balance.initial_balance_usd or 0),
                initial_balance_pen=float(balance.initial_balance_pen or 0),
                balance_usd=float(balance.balance_usd or 0),
                balance_pen=float(balance.balance_pen or 0),
            )
            db.session.add(hist)
        if currency == 'USD':
            hist.balance_usd = amount
        else:
            hist.balance_pen = amount
        hist.updated_by = current_user.id
        hist.updated_at = now_peru()

        db.session.commit()

        logger.info(f"Saldo actual actualizado exitosamente para {bank_name}")

        return jsonify({
            'success': True,
            'message': f'Saldo actualizado exitosamente',
            'balance': {
                'id': balance.id,
                'bank_name': balance.bank_name,
                'balance_usd': float(balance.balance_usd or 0),
                'balance_pen': float(balance.balance_pen or 0),
                'initial_balance_usd': float(balance.initial_balance_usd or 0),
                'initial_balance_pen': float(balance.initial_balance_pen or 0)
            }
        })

    except Exception as e:
        import traceback
        logger = logging.getLogger(__name__)
        logger.error(f"Error actualizando saldo actual: {str(e)}")
        logger.error(traceback.format_exc())
        db.session.rollback()
        return jsonify({'error': str(e), 'details': traceback.format_exc()}), 500


@position_bp.route('/api/update_initial_balance', methods=['POST'])
@login_required
@require_role('Master', 'Operador')
def update_initial_balance():
    """
    API: Actualizar saldo inicial bancario

    POST JSON:
        bank_name: Nombre del banco
        currency: 'USD' o 'PEN'
        amount: Nuevo saldo inicial
    """
    data = request.get_json()

    bank_name = data.get('bank_name')
    currency = data.get('currency')
    amount = data.get('amount', 0)

    if not bank_name or not currency:
        return jsonify({'error': 'Faltan datos requeridos'}), 400

    if currency not in ['USD', 'PEN']:
        return jsonify({'error': 'Moneda inválida'}), 400

    try:
        amount = float(amount)
        if amount < 0:
            return jsonify({'error': 'El saldo inicial no puede ser negativo'}), 400
    except (ValueError, TypeError):
        return jsonify({'error': 'Monto inválido'}), 400

    try:
        from app.utils.formatters import now_peru
        import logging
        logger = logging.getLogger(__name__)

        logger.info(f"Actualizando saldo inicial: bank_name={bank_name}, currency={currency}, amount={amount}")

        balance = BankBalance.get_or_create_balance(bank_name)

        if currency == 'USD':
            balance.initial_balance_usd = amount
        else:
            balance.initial_balance_pen = amount

        balance.updated_by = current_user.id
        balance.updated_at = now_peru()

        # Grabar snapshot diario para Libro Caja y Bancos
        today = now_peru().date()
        hist = BankBalanceHistory.query.filter_by(
            snapshot_date=today, bank_name=balance.bank_name
        ).first()
        if not hist:
            hist = BankBalanceHistory(
                snapshot_date=today,
                bank_name=balance.bank_name,
                balance_usd=float(balance.balance_usd or 0),
                balance_pen=float(balance.balance_pen or 0),
                initial_balance_usd=float(balance.initial_balance_usd or 0),
                initial_balance_pen=float(balance.initial_balance_pen or 0),
            )
            db.session.add(hist)
        if currency == 'USD':
            hist.initial_balance_usd = amount
        else:
            hist.initial_balance_pen = amount
        hist.updated_by = current_user.id
        hist.updated_at = now_peru()

        db.session.commit()

        logger.info(f"Saldo inicial actualizado exitosamente para {bank_name}")

        return jsonify({
            'success': True,
            'message': f'Saldo inicial actualizado exitosamente',
            'balance': {
                'id': balance.id,
                'bank_name': balance.bank_name,
                'balance_usd': float(balance.balance_usd or 0),
                'balance_pen': float(balance.balance_pen or 0),
                'initial_balance_usd': float(balance.initial_balance_usd or 0),
                'initial_balance_pen': float(balance.initial_balance_pen or 0)
            }
        })

    except Exception as e:
        import traceback
        logger = logging.getLogger(__name__)
        logger.error(f"Error actualizando saldo inicial: {str(e)}")
        logger.error(traceback.format_exc())
        db.session.rollback()
        return jsonify({'error': str(e), 'details': traceback.format_exc()}), 500


@position_bp.route('/api/ping')
@login_required
def ping():
    """Diagnóstico: verifica que el blueprint position responde y puede consultar BankBalance."""
    try:
        count = BankBalance.query.count()
        return jsonify({'success': True, 'bank_count': count, 'msg': 'OK'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@position_bp.route('/api/bank_reconciliation')
@login_required
@require_role('Master', 'Operador')
def get_bank_reconciliation():
    """
    API: Obtener datos de reconciliación de saldos bancarios

    Query params:
        fecha: Fecha en formato YYYY-MM-DD (opcional, por defecto hoy)

    Returns:
        JSON con:
        - Lista de bancos con saldos iniciales, movimientos del día, saldos esperados y actuales
        - Resumen de movimientos del día (solo operaciones COMPLETADAS)
        - Diferencias/descuadres
    """
    try:
        from app.utils.formatters import now_peru
        from datetime import datetime as dt, time

        # Obtener fecha del query param o usar fecha actual
        fecha_param = request.args.get('fecha')
        if fecha_param:
            try:
                fecha_consulta = dt.strptime(fecha_param, '%Y-%m-%d').date()
            except ValueError:
                fecha_consulta = now_peru().date()
        else:
            fecha_consulta = now_peru().date()

        # Crear inicio y fin del día en Peru
        inicio_dia = dt.combine(fecha_consulta, time.min)
        fin_dia = dt.combine(fecha_consulta, time.max)

        # Obtener SOLO operaciones COMPLETADAS del día (excluir demo)
        demo_id = User.get_demo_user_id()
        rec_query = Operation.query.filter(
            Operation.status == 'Completada',
            Operation.created_at >= inicio_dia,
            Operation.created_at <= fin_dia
        )
        if demo_id:
            rec_query = rec_query.filter(Operation.user_id != demo_id)
        completed_ops = rec_query.all()

        # Obtener operaciones PENDIENTES / EN PROCESO del día
        pend_query = Operation.query.filter(
            Operation.status.in_(['Pendiente', 'En proceso']),
            Operation.created_at >= inicio_dia,
            Operation.created_at <= fin_dia
        )
        if demo_id:
            pend_query = pend_query.filter(Operation.user_id != demo_id)
        pending_ops = pend_query.all()

        logger.debug(f'Reconciliación {fecha_consulta}: {len(completed_ops)} operaciones completadas, {len(pending_ops)} pendientes')

        # Calcular movimientos del día (solo COMPLETADAS)
        total_usd_in = 0.0  # USD que entró (Ventas)
        total_usd_out = 0.0  # USD que salió (Compras)
        total_pen_in = 0.0  # PEN que entró (Compras)
        total_pen_out = 0.0  # PEN que salió (Ventas)

        for op in completed_ops:
            if op.operation_type == 'Compra':
                # Compra: Recibimos USD, Pagamos PEN
                total_usd_in += float(op.amount_usd)
                total_pen_out += float(op.amount_pen)
            else:  # Venta
                # Venta: Pagamos USD, Recibimos PEN
                total_usd_out += float(op.amount_usd)
                total_pen_in += float(op.amount_pen)

        # Movimientos netos del día
        net_usd_movement = total_usd_in - total_usd_out
        net_pen_movement = total_pen_in - total_pen_out

        # Obtener todos los bancos registrados
        all_banks = BankBalance.query.all()

        # Calcular totales globales (sumas de todos los bancos)
        total_initial_usd = sum(float(bank.initial_balance_usd or 0) for bank in all_banks)
        total_initial_pen = sum(float(bank.initial_balance_pen or 0) for bank in all_banks)
        total_actual_usd = sum(float(bank.balance_usd or 0) for bank in all_banks)
        total_actual_pen = sum(float(bank.balance_pen or 0) for bank in all_banks)

        # ── Atribuir movimientos a cada cuenta bancaria específica ────────────
        # QoriCash usa el mismo banco que el cliente (si el cliente tiene cuenta
        # INTERBANK, el depósito va a la cuenta INTERBANK de QoriCash).
        # La cuenta del cliente origen (source_account) identifica el banco usado.
        from app.config.bank_accounts import QORICASH_ACCOUNTS

        # Map: banco → { 'USD': 'INTERBANK USD (200-...)', 'PEN': 'INTERBANK PEN (200-...)' }
        _banco_accts = {}
        for _b, _monedas in QORICASH_ACCOUNTS.items():
            _banco_accts[_b] = {}
            for _m, _d in _monedas.items():
                _banco_accts[_b][_m] = f"{_b} {_m} ({_d['numero']})"

        _BANK_ALIASES = {
            'BCP': 'BCP', 'CREDITO': 'BCP', 'CRÉDITO': 'BCP',
            'INTERBANK': 'INTERBANK', 'IBK': 'INTERBANK',
            'BANBIF': 'BANBIF', 'BIF': 'BANBIF',
        }

        def _normalize_banco(name):
            # Cadena vacía → banco indeterminado (el caller elige fallback).
            if not (name or '').strip():
                return ''
            u = name.upper()
            for alias, banco in _BANK_ALIASES.items():
                if alias in u:
                    return banco
            return 'INTERBANK'  # banco externo desconocido → cobro/pago vía INTERBANK

        # acct_mvmt: { full_bank_name: { 'USD': float, 'PEN': float } }
        acct_mvmt = {}

        def _add_mvmt(full_name, usd_delta, pen_delta):
            if not full_name:
                return
            if full_name not in acct_mvmt:
                acct_mvmt[full_name] = {'USD': 0.0, 'PEN': 0.0}
            acct_mvmt[full_name]['USD'] += usd_delta
            acct_mvmt[full_name]['PEN'] += pen_delta

        def _fallback_banco(op):
            """Banco fallback para el lado ORIGEN (Compra-USD / Venta-PEN)."""
            try:
                if op.source_account and op.client:
                    for _acct in (op.client.bank_accounts or []):
                        if _acct.get('account_number') == op.source_account:
                            return _normalize_banco(_acct.get('bank_name', ''))
                if op.source_bank_name:
                    return _normalize_banco(op.source_bank_name)
            except Exception:
                pass
            return 'INTERBANK'

        def _fallback_banco_dest(op):
            """Banco fallback para el lado DESTINO (Compra-PEN / Venta-USD).
            Para Compra: QoriCash paga PEN a la cuenta destino del cliente.
            Para Venta:  QoriCash paga USD a la cuenta destino del cliente.
            La cuenta destino del cliente determina qué banco de QoriCash se usa
            (transferencia intrabancaria mismo-banco)."""
            try:
                if op.destination_account and op.client:
                    for _acct in (op.client.bank_accounts or []):
                        if _acct.get('account_number') == op.destination_account:
                            return _normalize_banco(_acct.get('bank_name', ''))
                if op.destination_bank_name:
                    return _normalize_banco(op.destination_bank_name)
            except Exception:
                pass
            return _fallback_banco(op)  # último recurso: usar banco origen

        for op in completed_ops:
            _usd = float(op.amount_usd)
            _pen = float(op.amount_pen)
            _payments = op.client_payments or []
            _deposits = op.client_deposits or []
            _has_pay_banks = any(p.get('qc_bank') for p in _payments)
            _has_dep_banks = any(d.get('qc_bank') for d in _deposits)

            if op.operation_type == 'Compra':
                # Depósitos USD: cliente → QoriCash  (banco = cuenta origen del cliente)
                if _has_dep_banks:
                    _usd_attr = 0.0
                    for dep in _deposits:
                        _b = _normalize_banco(dep.get('qc_bank', '')) or _normalize_banco(dep.get('cuenta_cargo', ''))
                        _amt = float(dep.get('importe', 0))
                        if _b and _amt > 0:
                            _add_mvmt(_banco_accts.get(_b, {}).get('USD'), +_amt, 0.0)
                            _usd_attr += _amt
                    if _usd_attr == 0 and _usd > 0:
                        _add_mvmt(_banco_accts.get(_fallback_banco(op), {}).get('USD'), +_usd, 0.0)
                else:
                    _add_mvmt(_banco_accts.get(_fallback_banco(op), {}).get('USD'), +_usd, 0.0)
                # Pagos PEN: QoriCash → cliente  (banco = cuenta DESTINO del cliente)
                if _has_pay_banks:
                    _pen_attr = 0.0
                    for pay in _payments:
                        _b = _normalize_banco(pay.get('qc_bank', '')) or _normalize_banco(pay.get('cuenta_destino', ''))
                        _amt = float(pay.get('importe', 0))
                        if _b and _amt > 0:
                            _add_mvmt(_banco_accts.get(_b, {}).get('PEN'), 0.0, -_amt)
                            _pen_attr += _amt
                    if _pen_attr == 0 and _pen > 0:
                        _add_mvmt(_banco_accts.get(_fallback_banco_dest(op), {}).get('PEN'), 0.0, -_pen)
                else:
                    _add_mvmt(_banco_accts.get(_fallback_banco_dest(op), {}).get('PEN'), 0.0, -_pen)
            else:  # Venta
                # Depósitos PEN: cliente → QoriCash  (banco = cuenta origen del cliente)
                if _has_dep_banks:
                    _pen_attr = 0.0
                    for dep in _deposits:
                        _b = _normalize_banco(dep.get('qc_bank', '')) or _normalize_banco(dep.get('cuenta_cargo', ''))
                        _amt = float(dep.get('importe', 0))
                        if _b and _amt > 0:
                            _add_mvmt(_banco_accts.get(_b, {}).get('PEN'), 0.0, +_amt)
                            _pen_attr += _amt
                    if _pen_attr == 0 and _pen > 0:
                        _add_mvmt(_banco_accts.get(_fallback_banco(op), {}).get('PEN'), 0.0, +_pen)
                else:
                    _add_mvmt(_banco_accts.get(_fallback_banco(op), {}).get('PEN'), 0.0, +_pen)
                # Pagos USD: QoriCash → cliente  (banco = cuenta DESTINO del cliente)
                if _has_pay_banks:
                    _usd_attr = 0.0
                    for pay in _payments:
                        _b = _normalize_banco(pay.get('qc_bank', '')) or _normalize_banco(pay.get('cuenta_destino', ''))
                        _amt = float(pay.get('importe', 0))
                        if _b and _amt > 0:
                            _add_mvmt(_banco_accts.get(_b, {}).get('USD'), -_amt, 0.0)
                            _usd_attr += _amt
                    if _usd_attr == 0 and _usd > 0:
                        _add_mvmt(_banco_accts.get(_fallback_banco_dest(op), {}).get('USD'), -_usd, 0.0)
                else:
                    _add_mvmt(_banco_accts.get(_fallback_banco_dest(op), {}).get('USD'), -_usd, 0.0)
        # Movimientos proyectados de operaciones pendientes / en proceso
        acct_mvmt_pend = {}

        def _add_mvmt_pend(full_name, usd_delta, pen_delta):
            if not full_name:
                return
            if full_name not in acct_mvmt_pend:
                acct_mvmt_pend[full_name] = {'USD': 0.0, 'PEN': 0.0}
            acct_mvmt_pend[full_name]['USD'] += usd_delta
            acct_mvmt_pend[full_name]['PEN'] += pen_delta

        for op in pending_ops:
            _usd = float(op.amount_usd)
            _pen = float(op.amount_pen)
            _payments = op.client_payments or []
            _deposits = op.client_deposits or []
            _has_pay_banks = any(p.get('qc_bank') for p in _payments)
            _has_dep_banks = any(d.get('qc_bank') for d in _deposits)

            if op.operation_type == 'Compra':
                if _has_dep_banks:
                    _usd_attr = 0.0
                    for dep in _deposits:
                        _b = _normalize_banco(dep.get('qc_bank', '')) or _normalize_banco(dep.get('cuenta_cargo', ''))
                        _amt = float(dep.get('importe', 0))
                        if _b and _amt > 0:
                            _add_mvmt_pend(_banco_accts.get(_b, {}).get('USD'), +_amt, 0.0)
                            _usd_attr += _amt
                    if _usd_attr == 0 and _usd > 0:
                        _add_mvmt_pend(_banco_accts.get(_fallback_banco(op), {}).get('USD'), +_usd, 0.0)
                else:
                    _add_mvmt_pend(_banco_accts.get(_fallback_banco(op), {}).get('USD'), +_usd, 0.0)
                if _has_pay_banks:
                    _pen_attr = 0.0
                    for pay in _payments:
                        _b = _normalize_banco(pay.get('qc_bank', '')) or _normalize_banco(pay.get('cuenta_destino', ''))
                        _amt = float(pay.get('importe', 0))
                        if _b and _amt > 0:
                            _add_mvmt_pend(_banco_accts.get(_b, {}).get('PEN'), 0.0, -_amt)
                            _pen_attr += _amt
                    if _pen_attr == 0 and _pen > 0:
                        _add_mvmt_pend(_banco_accts.get(_fallback_banco_dest(op), {}).get('PEN'), 0.0, -_pen)
                else:
                    _add_mvmt_pend(_banco_accts.get(_fallback_banco_dest(op), {}).get('PEN'), 0.0, -_pen)
            else:
                if _has_dep_banks:
                    _pen_attr = 0.0
                    for dep in _deposits:
                        _b = _normalize_banco(dep.get('qc_bank', '')) or _normalize_banco(dep.get('cuenta_cargo', ''))
                        _amt = float(dep.get('importe', 0))
                        if _b and _amt > 0:
                            _add_mvmt_pend(_banco_accts.get(_b, {}).get('PEN'), 0.0, +_amt)
                            _pen_attr += _amt
                    if _pen_attr == 0 and _pen > 0:
                        _add_mvmt_pend(_banco_accts.get(_fallback_banco(op), {}).get('PEN'), 0.0, +_pen)
                else:
                    _add_mvmt_pend(_banco_accts.get(_fallback_banco(op), {}).get('PEN'), 0.0, +_pen)
                if _has_pay_banks:
                    _usd_attr = 0.0
                    for pay in _payments:
                        _b = _normalize_banco(pay.get('qc_bank', '')) or _normalize_banco(pay.get('cuenta_destino', ''))
                        _amt = float(pay.get('importe', 0))
                        if _b and _amt > 0:
                            _add_mvmt_pend(_banco_accts.get(_b, {}).get('USD'), -_amt, 0.0)
                            _usd_attr += _amt
                    if _usd_attr == 0 and _usd > 0:
                        _add_mvmt_pend(_banco_accts.get(_fallback_banco_dest(op), {}).get('USD'), -_usd, 0.0)
                else:
                    _add_mvmt_pend(_banco_accts.get(_fallback_banco_dest(op), {}).get('USD'), -_usd, 0.0)
        # ─────────────────────────────────────────────────────────────────────

        # Calcular totales esperados y diferencias usando movimientos por cuenta
        expected_total_usd = sum(
            float(b.initial_balance_usd or 0) + acct_mvmt.get(b.bank_name, {}).get('USD', 0.0)
            for b in all_banks
        )
        expected_total_pen = sum(
            float(b.initial_balance_pen or 0) + acct_mvmt.get(b.bank_name, {}).get('PEN', 0.0)
            for b in all_banks
        )
        total_difference_usd = round(total_actual_usd - expected_total_usd, 2)
        total_difference_pen = round(total_actual_pen - expected_total_pen, 2)

        logger.debug(
            f'Reconciliación {fecha_consulta}: bancos={len(all_banks)}, '
            f'USD_neto={net_usd_movement}, PEN_neto={net_pen_movement}, '
            f'diff_USD={total_difference_usd}, diff_PEN={total_difference_pen}'
        )

        # Preparar datos de reconciliación por banco
        banks_data = []

        for bank in all_banks:
            initial_usd = float(bank.initial_balance_usd or 0)
            initial_pen = float(bank.initial_balance_pen or 0)
            actual_usd = float(bank.balance_usd or 0)
            actual_pen = float(bank.balance_pen or 0)

            # Movimientos atribuidos a este banco específico (Completadas)
            _mvmt = acct_mvmt.get(bank.bank_name, {'USD': 0.0, 'PEN': 0.0})
            movement_usd = _mvmt['USD']
            movement_pen = _mvmt['PEN']

            # Saldo real = inicial + movimientos completados
            expected_usd = initial_usd + movement_usd
            expected_pen = initial_pen + movement_pen

            # Diferencia = manual - esperado (completadas)
            diff_usd = actual_usd - expected_usd
            diff_pen = actual_pen - expected_pen

            # Movimientos pendientes proyectados
            _mvmt_pend = acct_mvmt_pend.get(bank.bank_name, {'USD': 0.0, 'PEN': 0.0})
            pend_movement_usd = _mvmt_pend['USD']
            pend_movement_pen = _mvmt_pend['PEN']

            # Saldo esperado total (incluye pendientes)
            saldo_esp_pend_usd = expected_usd + pend_movement_usd
            saldo_esp_pend_pen = expected_pen + pend_movement_pen

            # Obtener nombre del usuario que actualizó (con try-except por si hay error en la relación)
            updated_by_name = None
            try:
                if bank.updated_by:
                    updater = db.session.get(User, bank.updated_by)
                    updated_by_name = updater.username if updater else None
            except:
                updated_by_name = None

            banks_data.append({
                'id': bank.id,
                'bank_name': bank.bank_name,
                'usd': {
                    'initial': initial_usd,
                    'movements': round(movement_usd, 2),
                    'expected': round(expected_usd, 2),
                    'pend_movements': round(pend_movement_usd, 2),
                    'saldo_esp_pend': round(saldo_esp_pend_usd, 2),
                    'actual': actual_usd,
                    'difference': round(diff_usd, 2)
                },
                'pen': {
                    'initial': initial_pen,
                    'movements': round(movement_pen, 2),
                    'expected': round(expected_pen, 2),
                    'pend_movements': round(pend_movement_pen, 2),
                    'saldo_esp_pend': round(saldo_esp_pend_pen, 2),
                    'actual': actual_pen,
                    'difference': round(diff_pen, 2)
                },
                'updated_at': bank.updated_at.isoformat() if bank.updated_at else None,
                'updated_by': updated_by_name
            })

        # Resumen de movimientos
        movements_summary = {
            'usd': {
                'inflows': round(total_usd_in, 2),
                'outflows': round(total_usd_out, 2),
                'net': round(net_usd_movement, 2)
            },
            'pen': {
                'inflows': round(total_pen_in, 2),
                'outflows': round(total_pen_out, 2),
                'net': round(net_pen_movement, 2)
            },
            'completed_operations': len(completed_ops)
        }

        # Detectar descuadres críticos (diferencia > $100 o S/300)
        has_critical_discrepancy = abs(total_difference_usd) > 100 or abs(total_difference_pen) > 300

        # ── C-02: Comparar saldo real vs saldo contable (Libro Mayor) ─────────
        # Mapeo banco → código PCGE para cruzar con JournalEntryLine
        _BANK_PCGE = {
            'BCP':       {'PEN': '1041', 'USD': '1044'},
            'INTERBANK': {'PEN': '1048', 'USD': '1047'},
            'BANBIF':    {'PEN': '1049', 'USD': '1050'},
        }
        _LEDGER_THRESHOLD_PEN = 1.00   # S/ 1.00
        _LEDGER_THRESHOLD_USD = 0.50   # $ 0.50

        has_ledger_discrepancy = False

        try:
            from app.models.journal_entry_line import JournalEntryLine
            from app.models.journal_entry import JournalEntry as JE
            from sqlalchemy import func as sqlfunc

            def _ledger_balance_pen(pcge_code: str, entry_date) -> float:
                """
                Flujo neto contable del día para cuentas PEN.
                Suma DEBE - HABER (en PEN) de asientos activos con entry_date = fecha.
                """
                debe = db.session.query(sqlfunc.sum(JournalEntryLine.debe)).join(JE).filter(
                    JournalEntryLine.account_code == pcge_code,
                    JE.status == 'activo',
                    JE.entry_date == entry_date
                ).scalar() or 0
                haber = db.session.query(sqlfunc.sum(JournalEntryLine.haber)).join(JE).filter(
                    JournalEntryLine.account_code == pcge_code,
                    JE.status == 'activo',
                    JE.entry_date == entry_date
                ).scalar() or 0
                return round(float(debe) - float(haber), 2)

            def _ledger_balance_usd(pcge_code: str, entry_date) -> float:
                """
                Flujo neto contable del día para cuentas USD.
                Suma amount_usd (debe) - amount_usd (haber) — usa los USD reales,
                no el equivalente en PEN, para que sea comparable con 'actual' en USD.
                """
                debe_usd = db.session.query(sqlfunc.sum(JournalEntryLine.amount_usd)).join(JE).filter(
                    JournalEntryLine.account_code == pcge_code,
                    JournalEntryLine.debe > 0,
                    JournalEntryLine.amount_usd.isnot(None),
                    JE.status == 'activo',
                    JE.entry_date == entry_date
                ).scalar() or 0
                haber_usd = db.session.query(sqlfunc.sum(JournalEntryLine.amount_usd)).join(JE).filter(
                    JournalEntryLine.account_code == pcge_code,
                    JournalEntryLine.haber > 0,
                    JournalEntryLine.amount_usd.isnot(None),
                    JE.status == 'activo',
                    JE.entry_date == entry_date
                ).scalar() or 0
                return round(float(debe_usd) - float(haber_usd), 2)

            for bank_dict in banks_data:
                # bank_name = "BCP USD (xxx)" → extract first word = "BCP"
                bank_key = bank_dict['bank_name'].split()[0].upper()
                pcge_map = _BANK_PCGE.get(bank_key, {})

                ledger_pen = _ledger_balance_pen(pcge_map['PEN'], fecha_consulta) if 'PEN' in pcge_map else None
                ledger_usd = _ledger_balance_usd(pcge_map['USD'], fecha_consulta) if 'USD' in pcge_map else None

                bank_dict['ledger_pen'] = ledger_pen
                bank_dict['ledger_usd'] = ledger_usd

                # ledger_balance = flujo neto contable del día (no saldo acumulado)
                # ledger_diff = flujo contable - movimientos_completadas (debería ser ≈0 si el libro cuadra)
                if ledger_pen is not None:
                    bank_dict['pen']['ledger_balance'] = ledger_pen
                    # Compara flujo contable vs flujo operativo del día
                    diff = ledger_pen - bank_dict['pen']['movements']
                    bank_dict['pen']['ledger_diff'] = round(diff, 2)
                    if abs(diff) > _LEDGER_THRESHOLD_PEN:
                        has_ledger_discrepancy = True
                else:
                    bank_dict['pen']['ledger_balance'] = None
                    bank_dict['pen']['ledger_diff'] = None

                if ledger_usd is not None:
                    bank_dict['usd']['ledger_balance'] = ledger_usd
                    diff = ledger_usd - bank_dict['usd']['movements']
                    bank_dict['usd']['ledger_diff'] = round(diff, 2)
                    if abs(diff) > _LEDGER_THRESHOLD_USD:
                        has_ledger_discrepancy = True
                else:
                    bank_dict['usd']['ledger_balance'] = None
                    bank_dict['usd']['ledger_diff'] = None

        except Exception as exc:
            logger.warning(f'[C-02] No se pudo calcular saldo contable: {exc}')
            db.session.rollback()
            has_ledger_discrepancy = False
        # ─────────────────────────────────────────────────────────────────────

        return jsonify({
            'success': True,
            'fecha': fecha_consulta.isoformat(),
            'banks': banks_data,
            'movements_summary': movements_summary,
            'total_differences': {
                'usd': round(total_difference_usd, 2),
                'pen': round(total_difference_pen, 2)
            },
            'has_critical_discrepancy': has_critical_discrepancy,
            'has_ledger_discrepancy': has_ledger_discrepancy,
        })

    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f'ERROR EN /api/bank_reconciliation:\n{error_trace}')
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e),
            'details': error_trace
        }), 500


@position_bp.route('/api/sync_balances', methods=['POST'])
@login_required
@require_role('Master', 'Operador')
def sync_balances():
    """
    Sincroniza balance_pen / balance_usd de cada banco calculando:
        balance = initial_balance + movimientos_completados_del_dia

    Corrige valores desactualizados por errores históricos de apply_operation.
    """
    try:
        from app.utils.formatters import now_peru
        from datetime import datetime as dt, time

        fecha_param = request.args.get('fecha')
        if fecha_param:
            try:
                fecha_consulta = dt.strptime(fecha_param, '%Y-%m-%d').date()
            except ValueError:
                fecha_consulta = now_peru().date()
        else:
            fecha_consulta = now_peru().date()

        inicio_dia = dt.combine(fecha_consulta, time.min)
        fin_dia    = dt.combine(fecha_consulta, time.max)

        demo_id = User.get_demo_user_id()
        rec_query = Operation.query.filter(
            Operation.status == 'Completada',
            Operation.created_at >= inicio_dia,
            Operation.created_at <= fin_dia
        )
        if demo_id:
            rec_query = rec_query.filter(Operation.user_id != demo_id)
        completed_ops = rec_query.all()

        from app.config.bank_accounts import QORICASH_ACCOUNTS
        _banco_accts = {}
        for _b, _monedas in QORICASH_ACCOUNTS.items():
            _banco_accts[_b] = {}
            for _m, _d in _monedas.items():
                _banco_accts[_b][_m] = f"{_b} {_m} ({_d['numero']})"

        _BANK_ALIASES = {
            'BCP': 'BCP', 'CREDITO': 'BCP', 'CRÉDITO': 'BCP',
            'INTERBANK': 'INTERBANK', 'IBK': 'INTERBANK',
            'BANBIF': 'BANBIF', 'BIF': 'BANBIF',
        }

        def _norm(name):
            if not (name or '').strip():
                return ''
            u = name.upper()
            for alias, banco in _BANK_ALIASES.items():
                if alias in u:
                    return banco
            return 'INTERBANK'

        def _fallback(op):
            """Banco origen: Compra-USD / Venta-PEN."""
            try:
                if op.source_account and op.client:
                    for acct in (op.client.bank_accounts or []):
                        if acct.get('account_number') == op.source_account:
                            return _norm(acct.get('bank_name', ''))
                if op.source_bank_name:
                    return _norm(op.source_bank_name)
            except Exception:
                pass
            return 'INTERBANK'

        def _fallback_dest(op):
            """Banco destino: Compra-PEN / Venta-USD."""
            try:
                if op.destination_account and op.client:
                    for acct in (op.client.bank_accounts or []):
                        if acct.get('account_number') == op.destination_account:
                            return _norm(acct.get('bank_name', ''))
                if op.destination_bank_name:
                    return _norm(op.destination_bank_name)
            except Exception:
                pass
            return _fallback(op)

        acct_mvmt = {}

        def _add(full_name, usd_d, pen_d):
            if not full_name:
                return
            if full_name not in acct_mvmt:
                acct_mvmt[full_name] = {'USD': 0.0, 'PEN': 0.0}
            acct_mvmt[full_name]['USD'] += usd_d
            acct_mvmt[full_name]['PEN'] += pen_d

        for op in completed_ops:
            _usd  = float(op.amount_usd)
            _pen  = float(op.amount_pen)
            _pays = op.client_payments or []
            _deps = op.client_deposits or []
            _hp   = any(p.get('qc_bank') for p in _pays)
            _hd   = any(d.get('qc_bank') for d in _deps)
            _fb   = _fallback(op)
            _fbd  = _fallback_dest(op)

            if op.operation_type == 'Compra':
                if _hd:
                    _ua = 0.0
                    for d in _deps:
                        _b = _norm(d.get('qc_bank','')) or _norm(d.get('cuenta_cargo',''))
                        _a = float(d.get('importe', 0))
                        if _b and _a > 0:
                            _add(_banco_accts.get(_b,{}).get('USD'), +_a, 0.0)
                            _ua += _a
                    if _ua == 0 and _usd > 0:
                        _add(_banco_accts.get(_fb,{}).get('USD'), +_usd, 0.0)
                else:
                    _add(_banco_accts.get(_fb,{}).get('USD'), +_usd, 0.0)
                if _hp:
                    _pa = 0.0
                    for p in _pays:
                        _b = _norm(p.get('qc_bank','')) or _norm(p.get('cuenta_destino',''))
                        _a = float(p.get('importe', 0))
                        if _b and _a > 0:
                            _add(_banco_accts.get(_b,{}).get('PEN'), 0.0, -_a)
                            _pa += _a
                    if _pa == 0 and _pen > 0:
                        _add(_banco_accts.get(_fbd,{}).get('PEN'), 0.0, -_pen)
                else:
                    _add(_banco_accts.get(_fbd,{}).get('PEN'), 0.0, -_pen)
            else:  # Venta
                if _hd:
                    _pa = 0.0
                    for d in _deps:
                        _b = _norm(d.get('qc_bank','')) or _norm(d.get('cuenta_cargo',''))
                        _a = float(d.get('importe', 0))
                        if _b and _a > 0:
                            _add(_banco_accts.get(_b,{}).get('PEN'), 0.0, +_a)
                            _pa += _a
                    if _pa == 0 and _pen > 0:
                        _add(_banco_accts.get(_fb,{}).get('PEN'), 0.0, +_pen)
                else:
                    _add(_banco_accts.get(_fb,{}).get('PEN'), 0.0, +_pen)
                if _hp:
                    _ua = 0.0
                    for p in _pays:
                        _b = _norm(p.get('qc_bank','')) or _norm(p.get('cuenta_destino',''))
                        _a = float(p.get('importe', 0))
                        if _b and _a > 0:
                            _add(_banco_accts.get(_b,{}).get('USD'), -_a, 0.0)
                            _ua += _a
                    if _ua == 0 and _usd > 0:
                        _add(_banco_accts.get(_fbd,{}).get('USD'), -_usd, 0.0)
                else:
                    _add(_banco_accts.get(_fbd,{}).get('USD'), -_usd, 0.0)

        all_banks = BankBalance.query.all()
        updated = []
        for bank in all_banks:
            mvmt = acct_mvmt.get(bank.bank_name, {'USD': 0.0, 'PEN': 0.0})
            new_usd = max(float(bank.initial_balance_usd or 0) + mvmt['USD'], 0.0)
            new_pen = max(float(bank.initial_balance_pen or 0) + mvmt['PEN'], 0.0)
            bank.balance_usd = new_usd
            bank.balance_pen = new_pen
            bank.updated_at  = now_peru()
            updated.append({'bank_name': bank.bank_name, 'usd': round(new_usd, 2), 'pen': round(new_pen, 2)})

        db.session.commit()
        logger.info(f'[SyncBalances] {len(updated)} cuentas sincronizadas para {fecha_consulta}')
        return jsonify({'success': True, 'updated': updated, 'fecha': fecha_consulta.isoformat()})

    except Exception as e:
        db.session.rollback()
        logger.error(f'ERROR EN /api/sync_balances: {traceback.format_exc()}')
        return jsonify({'success': False, 'error': str(e)}), 500


@position_bp.route('/api/debug_movements')
@login_required
@require_role('Master', 'Operador')
def debug_movements():
    """
    Endpoint de diagnóstico: muestra el desglose exacto de movimientos por operación
    sin modificar la base de datos. Útil para detectar atribuciones incorrectas de banco.
    """
    try:
        from app.utils.formatters import now_peru
        from datetime import datetime as dt, time

        fecha_param = request.args.get('fecha')
        if fecha_param:
            try:
                fecha_consulta = dt.strptime(fecha_param, '%Y-%m-%d').date()
            except ValueError:
                fecha_consulta = now_peru().date()
        else:
            fecha_consulta = now_peru().date()

        inicio_dia = dt.combine(fecha_consulta, time.min)
        fin_dia    = dt.combine(fecha_consulta, time.max)

        demo_id = User.get_demo_user_id()
        rec_query = Operation.query.filter(
            Operation.status == 'Completada',
            Operation.created_at >= inicio_dia,
            Operation.created_at <= fin_dia
        )
        if demo_id:
            rec_query = rec_query.filter(Operation.user_id != demo_id)
        completed_ops = rec_query.all()

        from app.config.bank_accounts import QORICASH_ACCOUNTS
        _banco_accts = {}
        for _b, _monedas in QORICASH_ACCOUNTS.items():
            _banco_accts[_b] = {}
            for _m, _d in _monedas.items():
                _banco_accts[_b][_m] = f"{_b} {_m} ({_d['numero']})"

        _BANK_ALIASES = {
            'BCP': 'BCP', 'CREDITO': 'BCP', 'CRÉDITO': 'BCP',
            'INTERBANK': 'INTERBANK', 'IBK': 'INTERBANK',
            'BANBIF': 'BANBIF', 'BIF': 'BANBIF',
        }

        def _norm(name):
            if not (name or '').strip():
                return ''
            u = name.upper()
            for alias, banco in _BANK_ALIASES.items():
                if alias in u:
                    return banco
            return 'INTERBANK'

        def _fallback(op):
            try:
                if op.source_account and op.client:
                    for acct in (op.client.bank_accounts or []):
                        if acct.get('account_number') == op.source_account:
                            return _norm(acct.get('bank_name', ''))
                if op.source_bank_name:
                    return _norm(op.source_bank_name)
            except Exception:
                pass
            return 'INTERBANK'

        def _fallback_dest(op):
            try:
                if op.destination_account and op.client:
                    for acct in (op.client.bank_accounts or []):
                        if acct.get('account_number') == op.destination_account:
                            return _norm(acct.get('bank_name', ''))
                if op.destination_bank_name:
                    return _norm(op.destination_bank_name)
            except Exception:
                pass
            return _fallback(op)

        acct_totals = {}
        ops_detail  = []

        for op in completed_ops:
            _usd  = float(op.amount_usd)
            _pen  = float(op.amount_pen)
            _pays = op.client_payments or []
            _deps = op.client_deposits or []
            _hp   = any(p.get('qc_bank') for p in _pays)
            _hd   = any(d.get('qc_bank') for d in _deps)
            _fb   = _fallback(op)
            _fbd  = _fallback_dest(op)

            movements = []

            def _record(full_name, usd_d, pen_d, reason):
                if not full_name:
                    movements.append({'cuenta': 'DESCONOCIDA', 'usd': usd_d, 'pen': pen_d, 'razon': reason})
                    return
                movements.append({'cuenta': full_name, 'usd': usd_d, 'pen': pen_d, 'razon': reason})
                if full_name not in acct_totals:
                    acct_totals[full_name] = {'USD': 0.0, 'PEN': 0.0}
                acct_totals[full_name]['USD'] += usd_d
                acct_totals[full_name]['PEN'] += pen_d

            if op.operation_type == 'Compra':
                if _hd:
                    _ua = 0.0
                    for d in _deps:
                        _b = _norm(d.get('qc_bank','')) or _norm(d.get('cuenta_cargo',''))
                        _a = float(d.get('importe', 0))
                        if _b and _a > 0:
                            _record(_banco_accts.get(_b,{}).get('USD'), +_a, 0.0,
                                    f"Compra dep qc_bank={d.get('qc_bank','')} cuenta={d.get('cuenta_cargo','')}")
                            _ua += _a
                    if _ua == 0 and _usd > 0:
                        _record(_banco_accts.get(_fb,{}).get('USD'), +_usd, 0.0,
                                f"Compra dep fallback src={op.source_account} src_bank={op.source_bank_name} fb={_fb}")
                else:
                    _record(_banco_accts.get(_fb,{}).get('USD'), +_usd, 0.0,
                            f"Compra dep (sin qc_bank) fallback src={op.source_account} src_bank={op.source_bank_name} fb={_fb}")
                if _hp:
                    _pa = 0.0
                    for p in _pays:
                        _b = _norm(p.get('qc_bank','')) or _norm(p.get('cuenta_destino',''))
                        _a = float(p.get('importe', 0))
                        if _b and _a > 0:
                            _record(_banco_accts.get(_b,{}).get('PEN'), 0.0, -_a,
                                    f"Compra pay qc_bank={p.get('qc_bank','')} cuenta={p.get('cuenta_destino','')}")
                            _pa += _a
                    if _pa == 0 and _pen > 0:
                        _record(_banco_accts.get(_fbd,{}).get('PEN'), 0.0, -_pen,
                                f"Compra pay fallback dest={op.destination_account} dest_bank={op.destination_bank_name} fbd={_fbd}")
                else:
                    _record(_banco_accts.get(_fbd,{}).get('PEN'), 0.0, -_pen,
                            f"Compra pay (sin qc_bank) fallback dest={op.destination_account} dest_bank={op.destination_bank_name} fbd={_fbd}")
            else:  # Venta
                if _hd:
                    _pa = 0.0
                    for d in _deps:
                        _b = _norm(d.get('qc_bank','')) or _norm(d.get('cuenta_cargo',''))
                        _a = float(d.get('importe', 0))
                        if _b and _a > 0:
                            _record(_banco_accts.get(_b,{}).get('PEN'), 0.0, +_a,
                                    f"Venta dep qc_bank={d.get('qc_bank','')} cuenta={d.get('cuenta_cargo','')}")
                            _pa += _a
                    if _pa == 0 and _pen > 0:
                        _record(_banco_accts.get(_fb,{}).get('PEN'), 0.0, +_pen,
                                f"Venta dep fallback src={op.source_account} src_bank={op.source_bank_name} fb={_fb}")
                else:
                    _record(_banco_accts.get(_fb,{}).get('PEN'), 0.0, +_pen,
                            f"Venta dep (sin qc_bank) fallback src={op.source_account} src_bank={op.source_bank_name} fb={_fb}")
                if _hp:
                    _ua = 0.0
                    for p in _pays:
                        _b = _norm(p.get('qc_bank','')) or _norm(p.get('cuenta_destino',''))
                        _a = float(p.get('importe', 0))
                        if _b and _a > 0:
                            _record(_banco_accts.get(_b,{}).get('USD'), -_a, 0.0,
                                    f"Venta pay qc_bank={p.get('qc_bank','')} cuenta={p.get('cuenta_destino','')}")
                            _ua += _a
                    if _ua == 0 and _usd > 0:
                        _record(_banco_accts.get(_fbd,{}).get('USD'), -_usd, 0.0,
                                f"Venta pay fallback dest={op.destination_account} dest_bank={op.destination_bank_name} fbd={_fbd}")
                else:
                    _record(_banco_accts.get(_fbd,{}).get('USD'), -_usd, 0.0,
                            f"Venta pay (sin qc_bank) fallback dest={op.destination_account} dest_bank={op.destination_bank_name} fbd={_fbd}")

            ops_detail.append({
                'op_id':   op.operation_id,
                'tipo':    op.operation_type,
                'usd':     _usd,
                'pen':     _pen,
                'fb':      _fb,
                'fbd':     _fbd,
                'hd':      _hd,
                'hp':      _hp,
                'deposits': _deps,
                'payments': _pays,
                'movimientos': movements,
            })

        return jsonify({
            'fecha':    fecha_consulta.isoformat(),
            'ops':      len(ops_detail),
            'totales':  acct_totals,
            'detalle':  ops_detail,
        })

    except Exception as e:
        logger.error(f'ERROR EN /api/debug_movements: {traceback.format_exc()}')
        return jsonify({'success': False, 'error': str(e)}), 500
