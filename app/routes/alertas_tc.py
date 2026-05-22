"""
Módulo Alertas TC — QoriCash Trading V2
Vista admin de alertas de tipo de cambio creadas en qoricash.pe
Visible para: Master
"""
import os
import requests
import logging
from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required
from app.utils.decorators import require_role

alertas_tc_bp = Blueprint('alertas_tc', __name__, url_prefix='/alertas-tc')
logger = logging.getLogger(__name__)

_WEB_URL    = lambda: os.environ.get('QORICASH_WEB_URL', 'https://www.qoricash.pe')
_SECRET     = lambda: os.environ.get('CRON_SECRET', '')


def _fetch_admin_data():
    """Obtiene alertas + lastCheck desde el endpoint admin de qoricashweb."""
    try:
        resp = requests.get(
            f'{_WEB_URL()}/api/alertas/admin',
            params={'secret': _SECRET()},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            # Support both old format (list) and new format ({alertas, lastCheck})
            if isinstance(data, list):
                return data, None, None
            return data.get('alertas', []), data.get('lastCheck'), None
        return [], None, f'Error {resp.status_code} desde qoricashweb'
    except Exception as e:
        return [], None, str(e)


@alertas_tc_bp.route('/')
@login_required
@require_role('Master')
def index():
    alertas, last_check, error = _fetch_admin_data()

    # Obtener TC actual para mostrar en el dashboard
    try:
        from app.models.exchange_rate import ExchangeRate
        rates   = ExchangeRate.get_current_rates()
        tc_compra = rates.get('compra')
        tc_venta  = rates.get('venta')
    except Exception:
        tc_compra = tc_venta = None

    total      = len(alertas)
    prospectos = sum(1 for a in alertas if a.get('esProspecto'))
    clientes   = total - prospectos
    activas    = sum(1 for a in alertas if a.get('activa'))
    disparadas = sum(1 for a in alertas if a.get('notificada'))

    return render_template(
        'alertas_tc/index.html',
        alertas=alertas,
        error=error,
        total=total,
        cnt_prospectos=prospectos,
        cnt_clientes=clientes,
        cnt_activas=activas,
        cnt_disparadas=disparadas,
        last_check=last_check,
        tc_compra=tc_compra,
        tc_venta=tc_venta,
    )


@alertas_tc_bp.route('/api/data')
@login_required
@require_role('Master')
def api_data():
    """Endpoint AJAX para refrescar la tabla sin recargar la página."""
    alertas, last_check, error = _fetch_admin_data()
    if error:
        return jsonify({'success': False, 'error': error}), 502
    return jsonify({'success': True, 'alertas': alertas, 'lastCheck': last_check})


@alertas_tc_bp.route('/api/trigger', methods=['POST'])
@login_required
@require_role('Master')
def api_trigger():
    """Dispara manualmente la verificación de alertas TC en qoricashweb."""
    try:
        from app.models.exchange_rate import ExchangeRate
        from app.extensions import csrf
        rates  = ExchangeRate.get_current_rates()
        compra = float(rates.get('compra') or 0)
        venta  = float(rates.get('venta')  or 0)
        if not compra or not venta:
            return jsonify({'success': False, 'error': 'TC no disponible'}), 400

        resp = requests.post(
            f'{_WEB_URL()}/api/alertas/check',
            json={'compra': compra, 'venta': venta},
            timeout=20,
        )
        if resp.status_code == 200:
            result = resp.json()
            logger.info(f'[AlertasTC] Trigger manual: {result}')
            return jsonify({'success': True, 'result': result, 'tc': {'compra': compra, 'venta': venta}})
        return jsonify({'success': False, 'error': f'HTTP {resp.status_code}'}), 502
    except Exception as e:
        logger.error(f'[AlertasTC] Error en trigger: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500
