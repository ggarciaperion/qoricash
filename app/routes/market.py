"""
Rutas del módulo Mercado — /mercado
"""
import logging
import os
from flask import Blueprint, render_template, jsonify, request
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


@market_bp.route('/api/ticker')
def api_ticker_public():
    """
    Endpoint público para la cinta de mercado en qoricash.pe.
    Protegido por API key via header X-Ticker-Key o query param key.
    """
    expected_key = os.environ.get('TICKER_API_KEY', '')
    provided_key = request.headers.get('X-Ticker-Key') or request.args.get('key', '')
    if expected_key and provided_key != expected_key:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    try:
        data = MarketService.get_dashboard_data()
    except Exception as e:
        logger.error(f'[Ticker] Error: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

    def _fmt(val):
        if val is None:
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    # Los precios viven dentro de data['snapshot'] (dict), no en el nivel raíz
    snap = data.get('snapshot') or {}

    ticker = [
        {'key': 'usdpen',       'label': 'USD / PEN',   'value': _fmt(snap.get('usdpen')),       'chg': _fmt(snap.get('usdpen_chg_pct')),    'prefix': 'S/', 'suffix': ''},
        {'key': 'gold',         'label': 'Oro',          'value': _fmt(snap.get('gold')),          'chg': _fmt(snap.get('gold_chg_pct')),      'prefix': '$',  'suffix': '/oz'},
        {'key': 'oil',          'label': 'Petróleo WTI', 'value': _fmt(snap.get('oil')),           'chg': _fmt(snap.get('oil_chg_pct')),       'prefix': '$',  'suffix': '/bbl'},
        {'key': 'sp500',        'label': 'S&P 500',      'value': _fmt(snap.get('sp500')),         'chg': _fmt(snap.get('sp500_chg_pct')),     'prefix': '',   'suffix': ''},
        {'key': 'nasdaq',       'label': 'Nasdaq',       'value': _fmt(snap.get('nasdaq')),        'chg': _fmt(snap.get('nasdaq_chg_pct')),    'prefix': '',   'suffix': ''},
        {'key': 'eurusd',       'label': 'EUR / USD',    'value': _fmt(snap.get('eurusd')),        'chg': _fmt(snap.get('eurusd_chg_pct')),    'prefix': '$',  'suffix': ''},
        {'key': 'dxy',          'label': 'DXY',          'value': _fmt(snap.get('dxy')),           'chg': _fmt(snap.get('dxy_chg_pct')),       'prefix': '',   'suffix': ''},
        {'key': 'vix',          'label': 'VIX',          'value': _fmt(snap.get('vix')),           'chg': _fmt(snap.get('vix_chg_pct')),       'prefix': '',   'suffix': ''},
        {'key': 'copper',       'label': 'Cobre',        'value': _fmt(snap.get('copper')),        'chg': _fmt(snap.get('copper_chg_pct')),    'prefix': '$',  'suffix': '/lb'},
        {'key': 'treasury_10y', 'label': 'Bono 10Y',     'value': _fmt(snap.get('treasury_10y')), 'chg': _fmt(snap.get('treasury_10y_chg')),  'prefix': '',   'suffix': '%'},
    ]

    # Agregar macro si están disponibles
    macro = data.get('macro') or {}
    if macro.get('bcrp_rate'):
        ticker.append({'key': 'bcrp', 'label': 'Tasa BCRP', 'value': _fmt(macro['bcrp_rate'].get('value')), 'chg': None, 'prefix': '', 'suffix': '%'})
    if macro.get('tc_venta_bcrp'):
        ticker.append({'key': 'tc_bcrp', 'label': 'TC Venta BCRP', 'value': _fmt(macro['tc_venta_bcrp'].get('value')), 'chg': None, 'prefix': 'S/', 'suffix': ''})

    return jsonify({'success': True, 'items': ticker})


# ─── DATATEC Reference Rates ─────────────────────────────────────────────────

@market_bp.route('/api/datatec', methods=['GET'])
@login_required
def datatec_get():
    """GET: retorna las tasas DATATEC actuales."""
    try:
        from app.models.datatec_rate import DatatecRate
        row = DatatecRate.get()
        return jsonify({'success': True, 'data': row.to_dict()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@market_bp.route('/api/datatec', methods=['POST'])
@login_required
@role_required('Master', 'Trader')
def datatec_update():
    """POST: actualiza las tasas DATATEC."""
    try:
        from app.models.datatec_rate import DatatecRate
        from flask_login import current_user
        data = request.get_json() or {}
        compra = data.get('compra')
        venta  = data.get('venta')
        if compra is None or venta is None:
            return jsonify({'success': False, 'error': 'Faltan compra o venta'}), 400
        compra_tarde = data.get('compra_tarde')
        venta_tarde  = data.get('venta_tarde')
        row = DatatecRate.update(
            float(compra), float(venta),
            float(compra_tarde) if compra_tarde not in (None, '') else None,
            float(venta_tarde)  if venta_tarde  not in (None, '') else None,
            current_user.id
        )
        return jsonify({'success': True, 'data': row.to_dict()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
