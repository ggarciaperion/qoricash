"""
Blueprint: Agentes de IA — /agentes
Módulo completo de monitoreo y control del ecosistema de agentes autónomos.

Rutas HTML:
  GET  /agentes/                        — Redirect → Mission Control
  GET  /agentes/mission-control         — Centro de Comando principal
  GET  /agentes/dashboard               — Dashboard ejecutivo
  GET  /agentes/activos                 — Lista de agentes activos
  GET  /agentes/actividad               — Consola de actividad en tiempo real
  GET  /agentes/prospeccion             — Métricas de prospección
  GET  /agentes/correos                 — Análisis de correos
  GET  /agentes/base-datos              — Estado de la base de datos
  GET  /agentes/auditoria               — Auditoría del sistema
  GET  /agentes/alertas                 — Centro de alertas
  GET  /agentes/configuracion           — Configuración de agentes

APIs:
  GET  /agentes/api/status              — Estado de todos los agentes (JSON)
  GET  /agentes/api/logs                — Últimos logs (JSON)
  GET  /agentes/api/kpis                — KPIs ejecutivos (JSON)
  GET  /agentes/api/alerts              — Alertas activas (JSON)
  POST /agentes/api/trigger/<agent_id>  — Ejecutar agente manualmente
  POST /agentes/api/pause/<agent_id>    — Pausar agente
  POST /agentes/api/resume/<agent_id>   — Reanudar agente
  POST /agentes/api/reset/<agent_id>    — Reiniciar contadores
  POST /agentes/api/alerts/<id>/resolve — Resolver alerta
"""
import logging
from functools import wraps
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, current_app
from flask_login import login_required, current_user
from app.extensions import db, csrf

_log = logging.getLogger(__name__)

agentes_bp = Blueprint('agentes', __name__, url_prefix='/agentes')

_ALLOWED = {'Master', 'Presidente de Negocios'}


def _require_agent_access(f):
    @wraps(f)
    def _wrap(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in _ALLOWED:
            from flask import abort
            abort(403)
        return f(*args, **kwargs)
    return _wrap


# ─────────────────────────────────────────────────────────────────────────────
# HTML — Páginas principales
# ─────────────────────────────────────────────────────────────────────────────

@agentes_bp.route('/')
@login_required
@_require_agent_access
def index():
    from app.models.agent import AgentStatus, AgentAlert
    from app.services.agents.executive import ExecutiveAgent
    agents   = AgentStatus.query.all()
    alerts_n = AgentAlert.query.filter_by(resolved=False).count()
    kpis     = ExecutiveAgent.get_kpis()
    running  = sum(1 for a in agents if a.status == 'running')
    return render_template('agentes/index.html',
                           agents=agents, alerts_n=alerts_n,
                           kpis=kpis, running=running)


@agentes_bp.route('/mission-control')
@login_required
@_require_agent_access
def mission_control():
    from app.models.agent import AgentStatus, AgentLog, AgentAlert
    from app.services.agents.executive import ExecutiveAgent

    agents = AgentStatus.query.order_by(AgentStatus.id).all()
    recent_logs = (AgentLog.query.order_by(AgentLog.created_at.desc()).limit(50).all())
    alerts = AgentAlert.query.filter_by(resolved=False).order_by(AgentAlert.created_at.desc()).limit(10).all()
    kpis = ExecutiveAgent.get_kpis()

    return render_template('agentes/mission_control.html',
                           agents=agents, recent_logs=recent_logs,
                           alerts=alerts, kpis=kpis)


@agentes_bp.route('/dashboard')
@login_required
@_require_agent_access
def dashboard():
    from app.models.agent import AgentStatus, AgentMetric, AgentAlert
    from app.services.agents.executive import ExecutiveAgent
    from sqlalchemy import func
    import datetime

    agents = AgentStatus.query.order_by(AgentStatus.id).all()
    kpis = ExecutiveAgent.get_kpis()

    # Métricas de los últimos 7 días
    week_metrics = (AgentMetric.query
                    .filter(AgentMetric.date >= datetime.date.today() - datetime.timedelta(days=7))
                    .order_by(AgentMetric.date.desc())
                    .all())

    alerts_count = AgentAlert.query.filter_by(resolved=False).count()

    return render_template('agentes/dashboard.html',
                           agents=agents, kpis=kpis,
                           week_metrics=week_metrics,
                           alerts_count=alerts_count)


@agentes_bp.route('/activos')
@login_required
@_require_agent_access
def activos():
    from app.models.agent import AgentStatus
    agents = AgentStatus.query.order_by(AgentStatus.id).all()
    return render_template('agentes/activos.html', agents=agents)


@agentes_bp.route('/actividad')
@login_required
@_require_agent_access
def actividad():
    from app.models.agent import AgentLog, AgentStatus
    logs = AgentLog.query.order_by(AgentLog.created_at.desc()).limit(200).all()
    agents = AgentStatus.query.order_by(AgentStatus.name).all()
    return render_template('agentes/actividad.html', logs=logs, agents=agents)


@agentes_bp.route('/prospeccion')
@login_required
@_require_agent_access
def prospeccion():
    from app.models.prospecto import Prospecto
    from app.models.agent import AgentMetric
    from sqlalchemy import func
    import datetime

    stats = {
        'total': Prospecto.query.count(),
        'contactados': Prospecto.query.filter(Prospecto.num_contactos > 0).count(),
        'sin_contacto': Prospecto.query.filter(Prospecto.num_contactos == 0).count(),
        'rebotes': Prospecto.query.filter(Prospecto.estado_email == 'REBOTE').count(),
        'no_contactar': Prospecto.query.filter(Prospecto.estado_comercial == 'NO CONTACTAR').count(),
        'clientes': Prospecto.query.filter(Prospecto.estado_comercial.in_(['cliente','P4'])).count(),
        'negociando': Prospecto.query.filter(Prospecto.estado_comercial.in_(['negociando','negociacion','P3'])).count(),
    }

    # Métricas de emails de hoy
    today = datetime.date.today()
    emails_hoy = (db.session.query(func.sum(AgentMetric.emails_sent))
                  .filter(AgentMetric.date == today).scalar() or 0)
    stats['emails_hoy'] = emails_hoy

    return render_template('agentes/prospeccion.html', stats=stats)


@agentes_bp.route('/correos')
@login_required
@_require_agent_access
def correos():
    from app.models.inteligencia import EmailEvento, Oportunidad
    import datetime

    hoy = datetime.date.today()
    semana = hoy - datetime.timedelta(days=7)

    eventos_hoy = EmailEvento.query.count()

    eventos_recientes = (EmailEvento.query
                         .order_by(EmailEvento.procesado_en.desc())
                         .limit(100).all())

    oportunidades = (Oportunidad.query
                     .filter_by(estado='nuevo')
                     .order_by(Oportunidad.detectado_en.desc())
                     .limit(20).all())

    return render_template('agentes/correos.html',
                           eventos=eventos_recientes,
                           oportunidades=oportunidades)


@agentes_bp.route('/base-datos')
@login_required
@_require_agent_access
def base_datos():
    from app.models.prospecto import Prospecto
    from sqlalchemy import func

    # Distribución por estado_comercial
    por_estado = (db.session.query(Prospecto.estado_comercial, func.count(Prospecto.id))
                  .group_by(Prospecto.estado_comercial)
                  .all())

    # Distribución por departamento
    por_depto = (db.session.query(Prospecto.departamento, func.count(Prospecto.id))
                 .filter(Prospecto.departamento.isnot(None))
                 .group_by(Prospecto.departamento)
                 .order_by(func.count(Prospecto.id).desc())
                 .limit(15).all())

    # Distribución por rubro
    por_rubro = (db.session.query(Prospecto.rubro, func.count(Prospecto.id))
                 .filter(Prospecto.rubro.isnot(None))
                 .group_by(Prospecto.rubro)
                 .order_by(func.count(Prospecto.id).desc())
                 .limit(10).all())

    total = Prospecto.query.count()
    return render_template('agentes/base_datos.html',
                           por_estado=por_estado, por_depto=por_depto,
                           por_rubro=por_rubro, total=total)


@agentes_bp.route('/auditoria')
@login_required
@_require_agent_access
def auditoria():
    from app.models.agent import AgentLog, AgentStatus, AgentAlert
    logs_error = (AgentLog.query.filter_by(level='ERROR')
                  .order_by(AgentLog.created_at.desc()).limit(50).all())
    alerts_all = (AgentAlert.query.order_by(AgentAlert.created_at.desc()).limit(50).all())
    agents = AgentStatus.query.all()
    return render_template('agentes/auditoria.html',
                           logs_error=logs_error, alerts_all=alerts_all,
                           agents=agents)


@agentes_bp.route('/alertas')
@login_required
@_require_agent_access
def alertas():
    from app.models.agent import AgentAlert
    activas = AgentAlert.query.filter_by(resolved=False).order_by(
        AgentAlert.created_at.desc()).all()
    resueltas = AgentAlert.query.filter_by(resolved=True).order_by(
        AgentAlert.created_at.desc()).limit(20).all()
    return render_template('agentes/alertas.html',
                           activas=activas, resueltas=resueltas)


@agentes_bp.route('/contabilidad')
@login_required
@_require_agent_access
def contabilidad():
    from app.models.audit_report import AuditReport
    reports = (AuditReport.query
               .order_by(AuditReport.audit_date.desc())
               .limit(6).all())
    latest = reports[0] if reports else None
    return render_template('agentes/contabilidad.html',
                           reports=reports, latest=latest)


@agentes_bp.route('/configuracion')
@login_required
@_require_agent_access
def configuracion():
    from app.models.agent import AgentStatus
    agents = AgentStatus.query.order_by(AgentStatus.id).all()
    return render_template('agentes/configuracion.html', agents=agents)


# ─────────────────────────────────────────────────────────────────────────────
# APIs JSON
# ─────────────────────────────────────────────────────────────────────────────

@agentes_bp.route('/api/status')
@login_required
@_require_agent_access
def api_status():
    from app.models.agent import AgentStatus
    agents = AgentStatus.query.order_by(AgentStatus.id).all()
    return jsonify([a.to_dict() for a in agents])


@agentes_bp.route('/api/logs')
@login_required
@_require_agent_access
def api_logs():
    from app.models.agent import AgentLog
    limit = min(int(request.args.get('limit', 100)), 500)
    agent_filter = request.args.get('agent_id')
    q = AgentLog.query
    if agent_filter:
        q = q.filter_by(agent_id=agent_filter)
    logs = q.order_by(AgentLog.created_at.desc()).limit(limit).all()
    return jsonify([l.to_dict() for l in logs])


@agentes_bp.route('/api/kpis')
@login_required
@_require_agent_access
def api_kpis():
    from app.services.agents.executive import ExecutiveAgent
    return jsonify(ExecutiveAgent.get_kpis())


@agentes_bp.route('/api/alerts')
@login_required
@_require_agent_access
def api_alerts():
    from app.models.agent import AgentAlert
    alerts = AgentAlert.query.filter_by(resolved=False).order_by(
        AgentAlert.created_at.desc()).limit(50).all()
    return jsonify([a.to_dict() for a in alerts])


@agentes_bp.route('/api/trigger/<agent_id>', methods=['POST'])
@login_required
@_require_agent_access
@csrf.exempt
def api_trigger(agent_id):
    from app.services.agents.orchestrator import _agent_map
    import eventlet
    app = current_app._get_current_object()
    agent = _agent_map.get(agent_id)
    if not agent:
        return jsonify({'error': f'Agente {agent_id} no encontrado'})
    # Ejecutar en greenlet para no bloquear el request
    eventlet.spawn(agent.run, app)
    return jsonify({'ok': True, 'message': f'{agent.name} disparado en background'})


@agentes_bp.route('/api/pause/<agent_id>', methods=['POST'])
@login_required
@_require_agent_access
@csrf.exempt
def api_pause(agent_id):
    from app.services.agents.orchestrator import pause_agent
    ok = pause_agent(agent_id, current_user.id, current_app._get_current_object())
    return jsonify({'ok': ok})


@agentes_bp.route('/api/resume/<agent_id>', methods=['POST'])
@login_required
@_require_agent_access
@csrf.exempt
def api_resume(agent_id):
    from app.services.agents.orchestrator import resume_agent
    ok = resume_agent(agent_id, current_app._get_current_object())
    return jsonify({'ok': ok})


@agentes_bp.route('/api/reset/<agent_id>', methods=['POST'])
@login_required
@_require_agent_access
@csrf.exempt
def api_reset(agent_id):
    from app.services.agents.orchestrator import reset_agent_stats
    ok = reset_agent_stats(agent_id, current_app._get_current_object())
    return jsonify({'ok': ok})


@agentes_bp.route('/api/alerts/<int:alert_id>/resolve', methods=['POST'])
@login_required
@_require_agent_access
@csrf.exempt
def api_resolve_alert(alert_id):
    from app.models.agent import AgentAlert
    from app.utils.formatters import now_peru
    alert = AgentAlert.query.get_or_404(alert_id)
    alert.resolved = True
    alert.resolved_by = current_user.id
    alert.resolved_at = now_peru()
    db.session.commit()
    return jsonify({'ok': True})


@agentes_bp.route('/api/test-gmail', methods=['GET'])
@login_required
@_require_agent_access
def api_test_gmail():
    """Diagnóstico: prueba autenticación Gmail para cada bandeja."""
    import os
    from app.services.agents.mail_agent import _BANDEJAS

    results = []
    for bandeja, env_var in _BANDEJAS.items():
        token = os.environ.get(env_var, '')
        client_id     = os.environ.get('GMAIL_CLIENT_ID', '')
        client_secret = os.environ.get('GMAIL_CLIENT_SECRET', '')

        if not token:
            results.append({'bandeja': bandeja, 'ok': False, 'error': f'Variable {env_var} no encontrada en env'})
            continue
        if not client_id or not client_secret:
            results.append({'bandeja': bandeja, 'ok': False, 'error': 'GMAIL_CLIENT_ID o GMAIL_CLIENT_SECRET faltantes'})
            continue

        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build

            creds = Credentials(
                token=None, refresh_token=token,
                token_uri='https://oauth2.googleapis.com/token',
                client_id=client_id, client_secret=client_secret,
                scopes=['https://mail.google.com/'],
            )
            creds.refresh(Request())
            build('gmail', 'v1', credentials=creds)
            results.append({'bandeja': bandeja, 'ok': True, 'error': None,
                            'token_preview': token[:10] + '…'})
        except Exception as e:
            results.append({'bandeja': bandeja, 'ok': False, 'error': str(e),
                            'token_preview': token[:10] + '…'})

    return jsonify({'results': results})
