"""
Rutas de Dashboard para QoriCash Trading V2
"""
from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from app.services.operation_service import OperationService
from app.utils.formatters import now_peru
from app.utils.decorators import require_role
from app.extensions import db
from app.models.trader_goal import TraderGoal
from app.models.trader_daily_profit import TraderDailyProfit
from app.models.user import User
from app.models.operation import Operation
from datetime import datetime, timedelta, date
from sqlalchemy import and_, func

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@login_required
def index():
    """
    Dashboard principal
    
    Redirige al dashboard según el rol del usuario
    """
    # Verificar rol y mostrar dashboard correspondiente
    if current_user.role == 'Master':
        return render_template('dashboard/master.html', user=current_user)
    elif current_user.role == 'Trader':
        return render_template('dashboard/trader.html', user=current_user)
    elif current_user.role == 'Operador':
        # Los operadores ven dashboard completo sin Sistema ni Gestionar Usuarios
        return render_template('dashboard/operator.html', user=current_user)
    else:
        return render_template('dashboard/trader.html', user=current_user)


@dashboard_bp.route('/api/dashboard_data')
@login_required
def get_dashboard_data():
    """
    API: Obtener datos del dashboard

    Query params:
        month: Mes (1-12) opcional
        year: Año opcional

    Returns:
        JSON con estadísticas
    """
    # Obtener parámetros
    month = request.args.get('month', type=int)
    year = request.args.get('year', type=int)

    # Obtener estadísticas
    stats = OperationService.get_dashboard_stats(month, year)

    # Agregar datos adicionales según rol
    if current_user.role == 'Master':
        # Master ve todo
        from app.models.user import User
        from app.models.client import Client

        stats['total_users'] = User.query.count()
        stats['active_users'] = User.query.filter_by(status='Activo').count()
        stats['total_clients'] = Client.query.count()
        stats['active_clients'] = Client.query.filter_by(status='Activo').count()

    return jsonify(stats)


@dashboard_bp.route('/api/dashboard/all')
@login_required
def get_all_dashboard_data():
    """
    API: Obtener TODAS las estadísticas del dashboard en una sola petición

    Query params:
        trader_id: ID del trader para filtrar (opcional)
        month: Mes específico (opcional)
        year: Año específico (opcional)

    Returns:
        JSON con todas las estadísticas combinadas
    """
    trader_id = request.args.get('trader_id', type=int)
    month = request.args.get('month', type=int)
    year = request.args.get('year', type=int)

    now = now_peru()

    # Usar mes/año actual si no se especifica
    if not month:
        month = now.month
    if not year:
        year = now.year

    # ========================================
    # ESTADÍSTICAS DE HOY
    # ========================================
    from sqlalchemy.orm import joinedload

    start_of_day = datetime(now.year, now.month, now.day, 0, 0, 0)
    end_of_day = datetime(now.year, now.month, now.day, 23, 59, 59)
    today_date = now.date()

    # OPTIMIZACIÓN: Usar joinedload para evitar N+1 queries
    query_today = Operation.query.filter(
        Operation.created_at >= start_of_day,
        Operation.created_at <= end_of_day
    ).limit(500)  # EMERGENCY FIX: Limitar registros para evitar timeout

    if trader_id:
        query_today = query_today.filter(Operation.user_id == trader_id)

    all_operations_today = query_today.all()
    completed_today = [op for op in all_operations_today if op.status == 'Completada']

    # Calcular utilidad del día
    profit_today = 0
    if trader_id:
        daily_profit = TraderDailyProfit.query.filter_by(
            user_id=trader_id,
            profit_date=today_date
        ).first()
        if daily_profit:
            profit_today = float(daily_profit.profit_amount_pen)
    else:
        ventas_pen = sum(float(op.amount_pen) for op in completed_today if op.operation_type == 'Venta')
        compras_pen = sum(float(op.amount_pen) for op in completed_today if op.operation_type == 'Compra')
        profit_today = ventas_pen - compras_pen

    stats_today = {
        'operations_count': len(completed_today),
        'completed_count': len(completed_today),
        'pending_count': sum(1 for op in all_operations_today if op.status == 'Pendiente'),
        'in_process_count': sum(1 for op in all_operations_today if op.status == 'En proceso'),
        'canceled_count': sum(1 for op in all_operations_today if op.status == 'Cancelado'),
        'total_usd': float(sum(op.amount_usd for op in completed_today)),
        'total_pen': float(sum(op.amount_pen for op in completed_today)),
        'unique_clients': len(set(op.client_id for op in completed_today)),
        'profit_today': round(profit_today, 2)
    }

    # ========================================
    # ESTADÍSTICAS DEL MES
    # ========================================
    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1)
    else:
        end_date = datetime(year, month + 1, 1)

    # OPTIMIZACIÓN: Usar joinedload para evitar N+1 queries
    query_month = Operation.query.filter(
        and_(
            Operation.created_at >= start_date,
            Operation.created_at < end_date
        )
    )

    if trader_id:
        query_month = query_month.filter(Operation.user_id == trader_id)

    operations_month = query_month.all()
    completed_month = [op for op in operations_month if op.status == 'Completada']

    # Calcular utilidad acumulada del mes
    profit_month = 0
    if trader_id:
        daily_profits = TraderDailyProfit.query.filter(
            TraderDailyProfit.user_id == trader_id,
            TraderDailyProfit.profit_date >= start_date.date(),
            TraderDailyProfit.profit_date < end_date.date()
        ).all()
        profit_month = sum(float(dp.profit_amount_pen) for dp in daily_profits)
    else:
        from collections import defaultdict
        daily_operations = defaultdict(lambda: {'ventas': 0, 'compras': 0})

        for op in completed_month:
            op_date = op.created_at.date()
            if op.operation_type == 'Venta':
                daily_operations[op_date]['ventas'] += float(op.amount_pen)
            elif op.operation_type == 'Compra':
                daily_operations[op_date]['compras'] += float(op.amount_pen)

        for date_data in daily_operations.values():
            profit_month += (date_data['ventas'] - date_data['compras'])

    # Obtener meta mensual
    goal_amount = 0
    if trader_id:
        goal = TraderGoal.query.filter_by(
            user_id=trader_id,
            month=month,
            year=year
        ).first()
        if goal:
            goal_amount = float(goal.goal_amount_pen)
    else:
        all_goals = TraderGoal.query.filter_by(
            month=month,
            year=year
        ).all()
        goal_amount = sum(float(g.goal_amount_pen) for g in all_goals)

    # Clientes activos
    from app.models.client import Client
    active_clients = Client.query.filter_by(status='Activo').count()

    stats_month = {
        'operations_count': len(completed_month),
        'completed_count': len(completed_month),
        'pending_count': sum(1 for op in all_operations_today if op.status == 'Pendiente'),  # SOLO del día
        'in_process_count': sum(1 for op in all_operations_today if op.status == 'En proceso'),  # SOLO del día
        'canceled_count': sum(1 for op in all_operations_today if op.status == 'Cancelado'),  # SOLO del día
        'completed_count_today': sum(1 for op in all_operations_today if op.status == 'Completada'),  # SOLO del día
        'total_usd': float(sum(op.amount_usd for op in completed_month)),
        'total_pen': float(sum(op.amount_pen for op in completed_month)),
        'unique_clients': len(set(op.client_id for op in completed_month)),
        'active_clients': active_clients,
        'profit_month': round(profit_month, 2),
        'goal_amount': round(goal_amount, 2)
    }

    # ========================================
    # DATOS DEL SISTEMA (solo Master)
    # ========================================
    stats_system = {}
    if current_user.role == 'Master':
        stats_system['total_users'] = User.query.count()
        stats_system['active_users'] = User.query.filter_by(status='Activo').count()

    # Combinar todas las estadísticas
    return jsonify({
        'today': stats_today,
        'month': stats_month,
        'system': stats_system
    })


@dashboard_bp.route('/api/stats/today')
@login_required
def get_today_stats():
    """
    API: Obtener estadísticas de hoy

    Query params:
        trader_id: ID del trader para filtrar (opcional)

    Lógica de utilidad:
    - SIN FILTRO: Automática → (Total PEN Ventas) - (Total PEN Compras)
    - CON FILTRO: Manual → Valor ingresado manualmente para el trader
    """
    trader_id = request.args.get('trader_id', type=int)

    # Obtener inicio y fin del día en Perú
    from sqlalchemy.orm import joinedload

    now = now_peru()
    start_of_day = datetime(now.year, now.month, now.day, 0, 0, 0)
    end_of_day = datetime(now.year, now.month, now.day, 23, 59, 59)
    today_date = now.date()

    # Construir query con EAGER LOADING
    query = Operation.query.options(
        joinedload(Operation.client),
        joinedload(Operation.user)
    ).filter(
        Operation.created_at >= start_of_day,
        Operation.created_at <= end_of_day
    )

    # Aplicar filtro por trader si existe
    if trader_id:
        query = query.filter(Operation.user_id == trader_id)

    # Obtener todas las operaciones del día
    all_operations = query.all()

    # Filtrar solo las operaciones completadas
    completed = [op for op in all_operations if op.status == 'Completada']

    # Calcular utilidad del día según filtro
    profit_today = 0
    if trader_id:
        # CON FILTRO: Utilidad manual del trader
        daily_profit = TraderDailyProfit.query.filter_by(
            user_id=trader_id,
            profit_date=today_date
        ).first()
        if daily_profit:
            profit_today = float(daily_profit.profit_amount_pen)
    else:
        # SIN FILTRO: Automática (Ventas PEN - Compras PEN) solo de operaciones completadas
        ventas_pen = sum(float(op.amount_pen) for op in completed if op.operation_type == 'Venta')
        compras_pen = sum(float(op.amount_pen) for op in completed if op.operation_type == 'Compra')
        profit_today = ventas_pen - compras_pen

    # ESTADÍSTICAS DE HOY: Solo operaciones completadas
    return jsonify({
        'operations_count': len(completed),  # Solo completadas
        'completed_count': len(completed),
        'pending_count': sum(1 for op in all_operations if op.status == 'Pendiente'),
        'in_process_count': sum(1 for op in all_operations if op.status == 'En proceso'),
        'total_usd': float(sum(op.amount_usd for op in completed)),
        'total_pen': float(sum(op.amount_pen for op in completed)),
        'unique_clients': len(set(op.client_id for op in completed)),  # Solo completadas
        'profit_today': round(profit_today, 2)
    })


@dashboard_bp.route('/api/stats/month')
@login_required
def get_month_stats():
    """
    API: Obtener estadísticas del mes

    Query params:
        trader_id: ID del trader para filtrar (opcional)
        month: Mes específico (opcional)
        year: Año específico (opcional)

    Lógica de utilidad acumulada del mes:
    - SIN FILTRO: Automática → Suma de (Total PEN Ventas - Total PEN Compras) de cada día del mes
    - CON FILTRO: Manual → Suma de todas las utilidades diarias ingresadas manualmente para ese trader

    Lógica de meta mensual:
    - SIN FILTRO: Suma de todas las metas mensuales de todos los traders
    - CON FILTRO: Meta mensual asignada manualmente a ese trader
    """
    trader_id = request.args.get('trader_id', type=int)
    month = request.args.get('month', type=int)
    year = request.args.get('year', type=int)

    now = now_peru()

    # Usar mes/año actual si no se especifica
    if not month:
        month = now.month
    if not year:
        year = now.year

    # Calcular inicio y fin del mes
    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1)
    else:
        end_date = datetime(year, month + 1, 1)

    # Construir query
    query = Operation.query.filter(
        and_(
            Operation.created_at >= start_date,
            Operation.created_at < end_date
        )
    )

    # Aplicar filtro por trader si existe
    if trader_id:
        query = query.filter(Operation.user_id == trader_id)

    operations = query.all()
    completed = [op for op in operations if op.status == 'Completada']

    # Calcular utilidad acumulada del mes según filtro
    profit_month = 0
    if trader_id:
        # CON FILTRO: Suma de utilidades diarias manuales del trader
        daily_profits = TraderDailyProfit.query.filter(
            TraderDailyProfit.user_id == trader_id,
            TraderDailyProfit.profit_date >= start_date.date(),
            TraderDailyProfit.profit_date < end_date.date()
        ).all()
        profit_month = sum(float(dp.profit_amount_pen) for dp in daily_profits)
    else:
        # SIN FILTRO: Automática - calcular día por día (Ventas PEN - Compras PEN)
        # Agrupar operaciones por día
        from collections import defaultdict
        daily_operations = defaultdict(lambda: {'ventas': 0, 'compras': 0})

        for op in completed:
            op_date = op.created_at.date()
            if op.operation_type == 'Venta':
                daily_operations[op_date]['ventas'] += float(op.amount_pen)
            elif op.operation_type == 'Compra':
                daily_operations[op_date]['compras'] += float(op.amount_pen)

        # Sumar utilidades diarias
        for date_data in daily_operations.values():
            profit_month += (date_data['ventas'] - date_data['compras'])

    # Obtener meta mensual según filtro
    goal_amount = 0
    if trader_id:
        # CON FILTRO: Meta del trader específico
        goal = TraderGoal.query.filter_by(
            user_id=trader_id,
            month=month,
            year=year
        ).first()
        if goal:
            goal_amount = float(goal.goal_amount_pen)
    else:
        # SIN FILTRO: Suma de todas las metas mensuales de todos los traders
        all_goals = TraderGoal.query.filter_by(
            month=month,
            year=year
        ).all()
        goal_amount = sum(float(g.goal_amount_pen) for g in all_goals)

    # Contar clientes activos
    from app.models.client import Client
    active_clients = Client.query.filter_by(status='Activo').count()

    # Obtener operaciones solo del día actual para "Estado de Operaciones"
    today_start = datetime(now.year, now.month, now.day, 0, 0, 0)
    today_end = datetime(now.year, now.month, now.day, 23, 59, 59)

    query_today = Operation.query.filter(
        Operation.created_at >= today_start,
        Operation.created_at <= today_end
    )

    # Aplicar filtro por trader si existe
    if trader_id:
        query_today = query_today.filter(Operation.user_id == trader_id)

    operations_today = query_today.all()

    # ESTADÍSTICAS DEL MES: Solo operaciones completadas
    return jsonify({
        'operations_count': len(completed),  # Solo completadas del mes
        'completed_count': len(completed),
        'pending_count': sum(1 for op in operations_today if op.status == 'Pendiente'),  # Solo del día
        'in_process_count': sum(1 for op in operations_today if op.status == 'En proceso'),  # Solo del día
        'canceled_count': sum(1 for op in operations_today if op.status == 'Cancelado'),  # Solo del día
        'completed_count_today': sum(1 for op in operations_today if op.status == 'Completada'),  # Solo del día
        'total_usd': float(sum(op.amount_usd for op in completed)),
        'total_pen': float(sum(op.amount_pen for op in completed)),
        'unique_clients': len(set(op.client_id for op in completed)),  # Solo completadas
        'active_clients': active_clients,
        'profit_month': round(profit_month, 2),
        'goal_amount': round(goal_amount, 2)
    })


@dashboard_bp.route('/api/traders')
@login_required
@require_role('Master')
def get_traders():
    """
    API: Obtener lista de traders

    Solo accesible para Master
    """
    traders = User.query.filter_by(role='Trader', status='Activo').all()

    return jsonify({
        'traders': [{
            'id': trader.id,
            'username': trader.username,
            'email': trader.email
        } for trader in traders]
    })


@dashboard_bp.route('/api/goals')
@login_required
@require_role('Master')
def get_goals():
    """
    API: Obtener metas de traders para un periodo

    Query params:
        month: Mes (1-12)
        year: Año
    """
    month = request.args.get('month', type=int)
    year = request.args.get('year', type=int)

    if not month or not year:
        return jsonify({'error': 'Se requiere mes y año'}), 400

    # Obtener todos los traders
    traders = User.query.filter_by(role='Trader').order_by(User.username).all()

    traders_data = []
    for trader in traders:
        # Buscar meta existente
        goal = TraderGoal.query.filter_by(
            user_id=trader.id,
            month=month,
            year=year
        ).first()

        traders_data.append({
            'id': trader.id,
            'username': trader.username,
            'email': trader.email,
            'status': trader.status,
            'goal_amount': float(goal.goal_amount_pen) if goal else 0
        })

    return jsonify({'traders': traders_data})


@dashboard_bp.route('/api/goals/save', methods=['POST'])
@login_required
@require_role('Master')
def save_goals():
    """
    API: Guardar metas de traders

    POST JSON:
        goals: Array de objetos con trader_id, month, year, goal_amount_pen
    """
    data = request.get_json()
    goals_data = data.get('goals', [])

    if not goals_data:
        return jsonify({'error': 'No se proporcionaron metas'}), 400

    try:
        for goal_data in goals_data:
            trader_id = goal_data.get('trader_id')
            month = goal_data.get('month')
            year = goal_data.get('year')
            goal_amount = goal_data.get('goal_amount_pen', 0)

            # Validar que el trader exista y sea un Trader
            trader = User.query.get(trader_id)
            if not trader or trader.role != 'Trader':
                continue

            # Buscar meta existente
            goal = TraderGoal.query.filter_by(
                user_id=trader_id,
                month=month,
                year=year
            ).first()

            if goal:
                # Actualizar meta existente
                goal.goal_amount_pen = goal_amount
                goal.updated_at = now_peru()
            else:
                # Crear nueva meta
                goal = TraderGoal(
                    user_id=trader_id,
                    month=month,
                    year=year,
                    goal_amount_pen=goal_amount,
                    created_by=current_user.id
                )
                db.session.add(goal)

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'{len(goals_data)} metas guardadas exitosamente'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/api/profits')
@login_required
@require_role('Master')
def get_profits():
    """
    API: Obtener utilidades diarias de un trader para un periodo

    Query params:
        trader_id: ID del trader (requerido)
        month: Mes (1-12)
        year: Año
    """
    trader_id = request.args.get('trader_id', type=int)
    month = request.args.get('month', type=int)
    year = request.args.get('year', type=int)

    if not trader_id:
        return jsonify({'error': 'Se requiere trader_id'}), 400
    if not month or not year:
        return jsonify({'error': 'Se requiere mes y año'}), 400

    # Validar que el trader exista
    trader = User.query.get(trader_id)
    if not trader or trader.role != 'Trader':
        return jsonify({'error': 'Trader no encontrado'}), 404

    # Calcular rango de fechas del mes
    start_date = datetime(year, month, 1).date()
    if month == 12:
        end_date = datetime(year + 1, 1, 1).date()
    else:
        end_date = datetime(year, month + 1, 1).date()

    # Obtener todas las utilidades diarias del trader para ese mes
    daily_profits = TraderDailyProfit.query.filter(
        TraderDailyProfit.user_id == trader_id,
        TraderDailyProfit.profit_date >= start_date,
        TraderDailyProfit.profit_date < end_date
    ).all()

    # Calcular utilidad acumulada del mes
    accumulated_profit = sum(float(dp.profit_amount_pen) for dp in daily_profits)

    # Obtener utilidad del día actual (si existe)
    today_date = now_peru().date()
    today_profit = 0
    if start_date <= today_date < end_date:
        daily_profit_today = TraderDailyProfit.query.filter_by(
            user_id=trader_id,
            profit_date=today_date
        ).first()
        if daily_profit_today:
            today_profit = float(daily_profit_today.profit_amount_pen)

    return jsonify({
        'trader_id': trader_id,
        'trader_name': trader.username,
        'month': month,
        'year': year,
        'profit_today': round(today_profit, 2),
        'accumulated_profit': round(accumulated_profit, 2),
        'daily_profits': [dp.to_dict() for dp in daily_profits]
    })


@dashboard_bp.route('/api/profits/save', methods=['POST'])
@login_required
@require_role('Master')
def save_profit():
    """
    API: Guardar utilidad diaria de un trader

    POST JSON:
        trader_id: ID del trader
        profit_date: Fecha de la utilidad (formato: YYYY-MM-DD)
        profit_amount_pen: Utilidad del día en soles
    """
    data = request.get_json()

    trader_id = data.get('trader_id')
    profit_date_str = data.get('profit_date')
    profit_amount = data.get('profit_amount_pen', 0)

    if not trader_id or not profit_date_str:
        return jsonify({'error': 'Se requiere trader_id y profit_date'}), 400

    # Validar que el trader exista y sea un Trader
    trader = User.query.get(trader_id)
    if not trader or trader.role != 'Trader':
        return jsonify({'error': 'Trader no encontrado'}), 404

    try:
        # Convertir fecha
        profit_date = datetime.strptime(profit_date_str, '%Y-%m-%d').date()

        # Buscar utilidad existente
        daily_profit = TraderDailyProfit.query.filter_by(
            user_id=trader_id,
            profit_date=profit_date
        ).first()

        if daily_profit:
            # Actualizar utilidad existente
            daily_profit.profit_amount_pen = profit_amount
            daily_profit.updated_at = now_peru()
        else:
            # Crear nueva utilidad
            daily_profit = TraderDailyProfit(
                user_id=trader_id,
                profit_date=profit_date,
                profit_amount_pen=profit_amount,
                created_by=current_user.id
            )
            db.session.add(daily_profit)

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Utilidad guardada exitosamente',
            'data': daily_profit.to_dict()
        })

    except ValueError:
        return jsonify({'error': 'Formato de fecha inválido. Use YYYY-MM-DD'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
