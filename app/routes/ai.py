"""
Agentes IA — QoriCash
=====================
Blueprint unificado para todos los agentes de inteligencia artificial.

Rutas HTML:
  GET  /ai/                          — Dashboard de agentes IA

APIs:
  POST /ai/api/pricing               — Agente de Pricing Dinámico
  POST /ai/api/prospecting/score     — Lead scoring (batch)
  POST /ai/api/prospecting/email/<id>— Email personalizado para un prospecto
  POST /ai/api/market/classify       — Clasificar noticia financiera
  POST /ai/api/market/analysis       — Análisis diario del mercado
  POST /ai/api/compliance/<id>       — Reporte KYC de un cliente
  GET  /ai/api/compliance/alerts     — Alertas batch de compliance
  POST /ai/api/treasury/position     — Análisis de posición tesorera
  POST /ai/api/treasury/distribution — Sugerencia distribución bancaria
  GET  /ai/api/retention             — Análisis de retención/churn
  POST /ai/api/retention/message/<id>— Mensaje de reactivación para un cliente
  POST /ai/api/chat                  — Chatbot web (endpoint público)
"""
import logging
from functools import wraps

from flask import Blueprint, render_template, request, jsonify, abort
from flask_login import login_required, current_user

from app.extensions import csrf

_log = logging.getLogger(__name__)

ai_bp = Blueprint('ai', __name__, url_prefix='/ai')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ALLOWED_ROLES = {'Master', 'Presidente de Negocios', 'Middle Office', 'Trader'}


def _ai_required(f):
    """Roles con acceso al panel IA."""
    @wraps(f)
    def _wrap(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        if current_user.role not in _ALLOWED_ROLES:
            abort(403)
        return f(*args, **kwargs)
    return _wrap


def _master_only(f):
    """Solo Master y Presidente de Negocios."""
    @wraps(f)
    def _wrap(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        if current_user.role not in ('Master', 'Presidente de Negocios'):
            abort(403)
        return f(*args, **kwargs)
    return _wrap


# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------

@ai_bp.route('/')
@login_required
@_ai_required
def dashboard():
    return render_template('ai/dashboard.html')


# ---------------------------------------------------------------------------
# Pricing Agent
# ---------------------------------------------------------------------------

@ai_bp.route('/api/pricing', methods=['POST'])
@csrf.exempt
@login_required
@_ai_required
def api_pricing():
    from app.services.ai.pricing_agent import analyze
    result = analyze()
    return jsonify(result)


# ---------------------------------------------------------------------------
# Prospecting Agent
# ---------------------------------------------------------------------------

@ai_bp.route('/api/prospecting/score', methods=['POST'])
@csrf.exempt
@login_required
@_ai_required
def api_prospecting_score():
    data  = request.get_json() or {}
    limit = int(data.get('limit', 100))
    from app.services.ai.prospecting_agent import score_batch
    result = score_batch(limit=limit)
    return jsonify(result)


@ai_bp.route('/api/prospecting/email/<int:prospecto_id>', methods=['POST'])
@csrf.exempt
@login_required
@_ai_required
def api_prospecting_email(prospecto_id):
    from app.services.ai.prospecting_agent import generate_email
    result = generate_email(prospecto_id)
    return jsonify(result)


# ---------------------------------------------------------------------------
# Market Agent
# ---------------------------------------------------------------------------

@ai_bp.route('/api/market/classify', methods=['POST'])
@csrf.exempt
@login_required
@_ai_required
def api_market_classify():
    data    = request.get_json() or {}
    title   = data.get('title', '')
    summary = data.get('summary', '')
    if not title:
        return jsonify({'ok': False, 'error': 'title requerido'}), 400
    from app.services.ai.market_agent import classify_news
    impact, direction, score = classify_news(title, summary)
    return jsonify({'ok': True, 'impact': impact, 'direction': direction, 'score': score})


@ai_bp.route('/api/market/analysis', methods=['POST'])
@csrf.exempt
@login_required
@_ai_required
def api_market_analysis():
    data        = request.get_json() or {}
    news_items  = data.get('news_items', [])
    market_data = data.get('market_data', {})
    from app.services.ai.market_agent import generate_daily_analysis
    result = generate_daily_analysis(news_items, market_data)
    return jsonify(result)


# ---------------------------------------------------------------------------
# Compliance Agent
# ---------------------------------------------------------------------------

@ai_bp.route('/api/compliance/<int:client_id>', methods=['POST'])
@csrf.exempt
@login_required
@_ai_required
def api_compliance_client(client_id):
    from app.services.ai.compliance_agent import analyze_client
    result = analyze_client(client_id)
    return jsonify(result)


@ai_bp.route('/api/compliance/alerts', methods=['GET'])
@login_required
@_ai_required
def api_compliance_alerts():
    from app.services.ai.compliance_agent import analyze_batch_alerts
    result = analyze_batch_alerts()
    return jsonify(result)


# ---------------------------------------------------------------------------
# Treasury Agent
# ---------------------------------------------------------------------------

@ai_bp.route('/api/treasury/position', methods=['POST'])
@csrf.exempt
@login_required
@_ai_required
def api_treasury_position():
    from app.services.ai.treasury_agent import analyze_daily_position
    result = analyze_daily_position()
    return jsonify(result)


@ai_bp.route('/api/treasury/distribution', methods=['POST'])
@csrf.exempt
@login_required
@_master_only
def api_treasury_distribution():
    from app.services.ai.treasury_agent import suggest_bank_distribution
    result = suggest_bank_distribution()
    return jsonify(result)


# ---------------------------------------------------------------------------
# Retention Agent
# ---------------------------------------------------------------------------

@ai_bp.route('/api/retention', methods=['GET'])
@login_required
@_ai_required
def api_retention():
    from app.services.ai.retention_agent import analyze_retention
    result = analyze_retention()
    return jsonify(result)


@ai_bp.route('/api/retention/message/<int:client_id>', methods=['POST'])
@csrf.exempt
@login_required
@_ai_required
def api_retention_message(client_id):
    from app.services.ai.retention_agent import generate_reactivation_message
    result = generate_reactivation_message(client_id)
    return jsonify(result)


# ---------------------------------------------------------------------------
# Lead Hunter Agent
# ---------------------------------------------------------------------------

@ai_bp.route('/api/leads/hunt', methods=['POST'])
@csrf.exempt
@login_required
@_master_only
def api_leads_hunt():
    """Lanza un ciclo completo de caza de prospectos."""
    data       = request.get_json() or {}
    sources    = data.get('sources')          # None = todas
    min_score  = int(data.get('min_score', 35))
    max_leads  = int(data.get('max_leads', 100))
    from app.services.ai.lead_hunter_agent import run_hunt
    result = run_hunt(sources=sources, min_score=min_score, max_new_leads=max_leads)
    return jsonify(result)


@ai_bp.route('/api/leads/search', methods=['POST'])
@csrf.exempt
@login_required
@_ai_required
def api_leads_search():
    """Búsqueda puntual de un prospecto por nombre/RUC."""
    data  = request.get_json() or {}
    query = (data.get('query') or '').strip()
    if not query:
        return jsonify({'ok': False, 'error': 'query requerido'}), 400
    from app.services.ai.lead_hunter_agent import search_prospect
    result = search_prospect(query)
    return jsonify(result)


@ai_bp.route('/api/leads/status', methods=['GET'])
@login_required
@_ai_required
def api_leads_status():
    """Estadísticas del agente de prospección automática."""
    from app.models.prospecto import Prospecto
    from app.extensions import db
    from sqlalchemy import func
    from app.utils.formatters import now_peru
    from datetime import timedelta

    today   = now_peru().date()
    week_ago = today - timedelta(days=7)

    total = Prospecto.query.filter_by(canal='IA-LeadHunter').count()
    this_week = Prospecto.query.filter(
        Prospecto.canal == 'IA-LeadHunter',
        Prospecto.creado_en >= week_ago,
    ).count()

    by_source = db.session.query(
        Prospecto.fuente, func.count(Prospecto.id)
    ).filter(
        Prospecto.canal == 'IA-LeadHunter'
    ).group_by(Prospecto.fuente).all()

    top = Prospecto.query.filter_by(
        canal='IA-LeadHunter'
    ).order_by(Prospecto.score.desc()).limit(5).all()

    return jsonify({
        'ok': True,
        'total_ia_leads': total,
        'esta_semana': this_week,
        'por_fuente': [{'fuente': f, 'count': c} for f, c in by_source],
        'top_prospects': [
            {'id': p.id, 'razon_social': p.razon_social, 'rubro': p.rubro,
             'score': p.score, 'fuente': p.fuente}
            for p in top
        ],
    })


# ---------------------------------------------------------------------------
# Chatbot Web (endpoint público — sin login requerido)
# ---------------------------------------------------------------------------

@ai_bp.route('/api/chat', methods=['POST'])
@csrf.exempt
def api_chat():
    """
    Endpoint para el chatbot de qoricash.pe.
    Recibe: {message: str, session_id: str (opcional)}
    Responde: {ok: bool, reply: str}
    """
    data    = request.get_json() or {}
    message = (data.get('message') or '').strip()
    if not message:
        return jsonify({'ok': False, 'error': 'message requerido'}), 400

    try:
        from app.services.ai.client import ask, HAIKU
        from app.models.exchange_rate import ExchangeRate

        er = ExchangeRate.query.order_by(ExchangeRate.updated_at.desc()).first()
        compra = float(er.buy_rate)  if er else 3.70
        venta  = float(er.sell_rate) if er else 3.75

        system = f"""Eres el asistente virtual de QoriCash, casa de cambio digital en Lima, Perú.
Eres amable, conciso y profesional. Respondes en español.

INFORMACIÓN ACTUAL:
  Tipo de cambio HOY: Compramos USD a {compra:.4f} soles | Vendemos USD a {venta:.4f} soles
  Servicio: cambio de dólares online, transferencia a cualquier banco del Perú.
  Horario: Lunes a Viernes 9:00 AM — 6:00 PM | Sábados 9:00 AM — 1:00 PM.
  Contacto: WhatsApp +51 999 999 999 | web: qoricash.pe

Puedes responder preguntas sobre el tipo de cambio, cómo funciona el servicio, documentos requeridos,
límites de operación, y canalizar consultas complejas al equipo humano.
Mantén respuestas cortas (máx 3 oraciones). Si no sabes algo, di que un asesor te contactará."""

        reply = ask(message, system=system, model=HAIKU, max_tokens=300)
        return jsonify({'ok': True, 'reply': reply})

    except Exception as e:
        _log.error(f'[AI Chat] Error: {e}', exc_info=True)
        return jsonify({'ok': True, 'reply': 'Disculpa, en este momento no puedo responder. Contáctanos al WhatsApp para atención inmediata.'})
