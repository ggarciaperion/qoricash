"""
Rutas del módulo Mercado — /mercado
"""
import logging
from flask import Blueprint, render_template, jsonify
from flask_login import login_required
from app.utils.decorators import require_role as role_required
from app.services.market.market_service import MarketService

logger = logging.getLogger(__name__)

market_bp = Blueprint('market', __name__, url_prefix='/mercado')

_ALL = ('Master', 'Trader', 'Operador', 'Middle Office')
_WRITE = ('Master', 'Trader')


@market_bp.route('/')
@login_required
@role_required(*_ALL)
def dashboard():
    try:
        data = MarketService.get_dashboard_data()
    except Exception as e:
        logger.error(f'[Market] Error en get_dashboard_data: {e}', exc_info=True)
        data = MarketService.empty_dashboard_data()
    return render_template('market/dashboard.html', **data)


@market_bp.route('/api/current')
@login_required
@role_required(*_ALL)
def api_current():
    data = MarketService.get_dashboard_data()
    return jsonify({'success': True, 'data': data})


@market_bp.route('/api/refresh', methods=['POST'])
@login_required
@role_required(*_WRITE)
def api_refresh():
    result = MarketService.run_cycle()
    return jsonify({'success': result['ok'], 'result': result})


@market_bp.route('/api/history')
@login_required
@role_required(*_ALL)
def api_history():
    from flask import request
    range_key = request.args.get('range', '1w')
    data = MarketService.get_history_range(range_key)
    return jsonify({'success': True, 'data': data})


@market_bp.route('/api/macro/refresh', methods=['POST'])
@login_required
@role_required('Master')
def api_macro_refresh():
    result = MarketService.run_macro_cycle()
    return jsonify({'success': result['ok'], 'result': result})


@market_bp.route('/api/calendar/refresh', methods=['POST'])
@login_required
@role_required(*_WRITE)
def api_calendar_refresh():
    result = MarketService.run_calendar_cycle()
    return jsonify({'success': result['ok'], 'result': result})


@market_bp.route('/api/daily-analysis')
@login_required
@role_required(*_ALL)
def api_daily_analysis():
    """Devuelve el análisis diario activo del día."""
    data = MarketService.get_daily_analysis()
    return jsonify({'success': True, 'data': data})


@market_bp.route('/api/daily-analysis/update', methods=['POST'])
@login_required
@role_required(*_ALL)
def api_daily_analysis_update():
    """Actualización intradía manual: incorpora noticias alto impacto desde 8:30 AM."""
    result = MarketService.run_intraday_update()
    return jsonify({'success': result['ok'], 'result': result})


@market_bp.route('/api/macro/update', methods=['POST'])
@login_required
@role_required('Master')
def api_macro_update():
    """Permite a Master actualizar un indicador macro manualmente."""
    from flask import request
    from app.extensions import db
    from app.models.market import MacroIndicator
    from datetime import datetime
    data = request.get_json()
    key = data.get('key')
    if not key:
        return jsonify({'success': False, 'error': 'key requerido'})
    ind = MacroIndicator.query.filter_by(key=key).first()
    if not ind:
        return jsonify({'success': False, 'error': 'Indicador no encontrado'})
    if 'value' in data:
        ind.prev_value = ind.value
        ind.value      = data['value']
        ind.direction  = 'up' if data['value'] > float(ind.prev_value or 0) else 'down'
    if 'notes' in data:
        ind.notes = data['notes']
    ind.source     = 'manual'
    ind.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'success': True, 'indicator': ind.to_dict()})
