"""
Módulo Alertas TC — QoriCash Trading V2
Vista admin de alertas de tipo de cambio creadas en qoricash.pe
Visible para: Master
"""
import os
import requests
from flask import Blueprint, render_template, jsonify, request, current_app
from flask_login import login_required, current_user
from app.utils.decorators import require_role

alertas_tc_bp = Blueprint('alertas_tc', __name__, url_prefix='/alertas-tc')


def _fetch_alertas():
    """Obtiene todas las alertas desde el endpoint admin de qoricashweb (Next.js)."""
    web_url = os.environ.get('QORICASH_WEB_URL', 'https://www.qoricash.pe')
    secret  = os.environ.get('CRON_SECRET', '')
    try:
        resp = requests.get(
            f'{web_url}/api/alertas/admin',
            params={'secret': secret},
            timeout=8,
        )
        if resp.status_code == 200:
            return resp.json(), None
        return [], f'Error {resp.status_code} desde qoricashweb'
    except Exception as e:
        return [], str(e)


@alertas_tc_bp.route('/')
@login_required
@require_role('Master')
def index():
    alertas, error = _fetch_alertas()

    # Contadores para las pestañas
    total       = len(alertas)
    prospectos  = sum(1 for a in alertas if a.get('esProspecto'))
    clientes    = total - prospectos
    activas     = sum(1 for a in alertas if a.get('activa'))
    disparadas  = sum(1 for a in alertas if a.get('notificada'))

    return render_template(
        'alertas_tc/index.html',
        alertas=alertas,
        error=error,
        total=total,
        cnt_prospectos=prospectos,
        cnt_clientes=clientes,
        cnt_activas=activas,
        cnt_disparadas=disparadas,
    )


@alertas_tc_bp.route('/api/data')
@login_required
@require_role('Master')
def api_data():
    """Endpoint AJAX para refrescar la tabla sin recargar la página."""
    alertas, error = _fetch_alertas()
    if error:
        return jsonify({'success': False, 'error': error}), 502
    return jsonify({'success': True, 'alertas': alertas})
