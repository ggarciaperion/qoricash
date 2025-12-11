"""
Rutas de Posición para QoriCash Trading V2
"""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app.models import BankBalance, Operation
from app.extensions import db
from app.utils.decorators import require_role
from datetime import datetime

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
    return render_template('position/view.html', user=current_user)


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

        all_ops_today = Operation.query.filter(
            Operation.status != 'Cancelado',
            Operation.created_at >= inicio_dia,
            Operation.created_at <= fin_dia
        ).all()

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
                else:
                    ventas_pendientes_usd += float(op.amount_usd)

        # Calcular diferencia y utilidad
        diferencia_usd = total_ventas_usd - total_compras_usd
        utilidad_pen = contravalor_ventas_pen - contravalor_compras_pen

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
                'ventas_pendientes_usd': round(ventas_pendientes_usd, 2)
            },
            'compras': compras_list,
            'ventas': ventas_list
        })

    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print("=" * 80)
        print("ERROR EN /api/bank_balances:")
        print("=" * 80)
        print(error_trace)
        print("=" * 80)
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

        # Obtener SOLO operaciones COMPLETADAS del día
        completed_ops = Operation.query.filter(
            Operation.status == 'Completada',
            Operation.created_at >= inicio_dia,
            Operation.created_at <= fin_dia
        ).all()

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

        # Calcular saldos esperados totales (inicial + movimientos UNA SOLA VEZ)
        expected_total_usd = total_initial_usd + net_usd_movement
        expected_total_pen = total_initial_pen + net_pen_movement

        # Calcular diferencias totales (UNA SOLA VEZ, no multiplicado por número de bancos)
        total_difference_usd = total_actual_usd - expected_total_usd
        total_difference_pen = total_actual_pen - expected_total_pen

        # Preparar datos de reconciliación por banco
        banks_data = []

        for bank in all_banks:
            # Obtener saldos individuales del banco
            initial_usd = float(bank.initial_balance_usd or 0)
            initial_pen = float(bank.initial_balance_pen or 0)
            actual_usd = float(bank.balance_usd or 0)
            actual_pen = float(bank.balance_pen or 0)

            # Para cada banco, mostramos los movimientos globales como referencia
            # pero NO los sumamos para calcular diferencias individuales
            # ya que los movimientos afectan a todos los bancos en conjunto
            expected_usd = initial_usd  # Sin sumar movimientos
            expected_pen = initial_pen  # Sin sumar movimientos

            # Diferencias individuales (solo para referencia por banco)
            diff_usd = actual_usd - initial_usd
            diff_pen = actual_pen - initial_pen

            # Obtener nombre del usuario que actualizó (con try-except por si hay error en la relación)
            updated_by_name = None
            try:
                if bank.updated_by:
                    from app.models.user import User
                    updater = User.query.get(bank.updated_by)
                    updated_by_name = updater.username if updater else None
            except:
                updated_by_name = None

            banks_data.append({
                'id': bank.id,
                'bank_name': bank.bank_name,
                'usd': {
                    'initial': initial_usd,
                    'movements': round(net_usd_movement, 2),
                    'expected': round(expected_usd, 2),
                    'actual': actual_usd,
                    'difference': round(diff_usd, 2)
                },
                'pen': {
                    'initial': initial_pen,
                    'movements': round(net_pen_movement, 2),
                    'expected': round(expected_pen, 2),
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

        return jsonify({
            'success': True,
            'fecha': fecha_consulta.isoformat(),
            'banks': banks_data,
            'movements_summary': movements_summary,
            'total_differences': {
                'usd': round(total_difference_usd, 2),
                'pen': round(total_difference_pen, 2)
            },
            'has_critical_discrepancy': has_critical_discrepancy
        })

    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print("=" * 80)
        print("ERROR EN /api/bank_reconciliation:")
        print("=" * 80)
        print(error_trace)
        print("=" * 80)
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e),
            'details': error_trace
        }), 500
