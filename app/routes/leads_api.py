"""
leads_api.py — POST /api/leads
Endpoint para que el sistema de prospección registre leads positivos en Qoricash.

Cuando el sistema de prospección detecta una respuesta positiva de un prospecto
(solicita_cotizacion, solicita_llamada, interesado, etc.), el agente CRM Bridge
invoca este endpoint para promover al prospecto al pipeline comercial interno.

Flujo:
    ProspectosMaster (Sheets)
    → agentes prospección
    → respuesta positiva
    → agente_crm_bridge.py
    → POST /api/leads   ← este endpoint
    → Oportunidad (oportunidades_comerciales)
    → Notification.create_for_roles(comerciales)
    → /comercial/pipeline

Autenticación: Bearer token (env var QORI_CRM_TOKEN)
Rate limit: 200 requests/hora
Idempotencia: garantizada por gmail_message_id como clave primaria del evento.
  Si la misma empresa genera una nueva conversación legítima en otra fecha,
  tiene un gmail_message_id diferente y genera una oportunidad nueva.
  NO se deduplicar por email puro, solo por evento (gmail_message_id).
"""
import logging
import os
from datetime import datetime

from flask import Blueprint, request, jsonify
from app.extensions import db, csrf, limiter
from app.utils.formatters import now_peru

log = logging.getLogger(__name__)

leads_api_bp = Blueprint('leads_api', __name__, url_prefix='/api/leads')

# Token de autenticación — NUNCA hardcoded
_QORI_CRM_TOKEN = lambda: os.environ.get('QORI_CRM_TOKEN', '')


def _authenticate(req) -> tuple[bool, str]:
    """
    Verifica el Bearer token del request.
    Retorna (ok, error_msg).
    """
    token_env = _QORI_CRM_TOKEN()
    if not token_env:
        log.error("[leads_api] QORI_CRM_TOKEN no configurado en env vars")
        return False, 'token_not_configured'

    auth_header = req.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return False, 'missing_bearer'

    provided = auth_header[len('Bearer '):]
    if provided != token_env:
        log.warning(f"[leads_api] Token inválido — intento de acceso no autorizado (IP={req.remote_addr})")
        return False, 'invalid_token'

    return True, ''


@leads_api_bp.route('/', methods=['POST'])
@csrf.exempt
@limiter.limit("200 per hour")
def create_lead():
    """
    POST /api/leads/

    Recibe un lead positivo del sistema de prospección y lo registra
    en Qoricash como Oportunidad + notificación in-app para el equipo.

    Request JSON:
    {
        "email":             "empresa@ejemplo.com",    (requerido)
        "gmail_message_id":  "1abc23def",              (requerido — clave de idempotencia)
        "tipo_lead":         "solicita_cotizacion",    (requerido)
        "empresa":           "Empresa SAC",
        "contacto":          "Juan García",
        "sector":            "importadores",
        "provincia":         "Lima",
        "telefono":          "987654321",
        "score":             7,
        "prioridad":         "alta",
        "fuente":            "PROSPECTOS_MASTER",
        "subject_original":  "Re: Tipo de cambio corporativo",
        "bandeja_receptora": "ggarcia@qoricash.pe",
        "prospecto_id":      123,
        "fecha_lead":        "2026-09-16T10:30:00"
    }

    Response 200:
    {"status": "created", "oportunidad_id": 42}

    Response 200 (duplicado):
    {"status": "already_exists", "oportunidad_id": 42}

    Response 401: token inválido
    Response 400: campos requeridos faltantes
    Response 429: rate limit
    """
    # Autenticación
    auth_ok, auth_error = _authenticate(request)
    if not auth_ok:
        return jsonify({'error': auth_error}), 401

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'body_required'}), 400

    # Validar campos requeridos
    email = (data.get('email') or '').strip().lower()
    gmail_msg_id = (data.get('gmail_message_id') or '').strip()
    tipo_lead = (data.get('tipo_lead') or '').strip()

    if not email:
        return jsonify({'error': 'email_required'}), 400
    if not gmail_msg_id:
        return jsonify({'error': 'gmail_message_id_required'}), 400
    if not tipo_lead:
        return jsonify({'error': 'tipo_lead_required'}), 400

    # ── Idempotencia: buscar por gmail_message_id (clave del evento) ─────────
    # Decisión de diseño: la clave de idempotencia es el ID del evento/mensaje
    # que originó la oportunidad, no el email del prospecto. Esto permite que:
    # - La misma empresa que responde en una nueva conversación (nuevo message_id)
    #   genere una oportunidad nueva sin ser bloqueada.
    # - Un mismo mensaje procesado dos veces (retry, bug, doble ejecución) NO
    #   genere oportunidades duplicadas.
    from app.models.inteligencia import Oportunidad

    existing = Oportunidad.query.filter_by(mensaje_id=gmail_msg_id).first()
    if existing:
        log.debug(f"[leads_api] Lead ya existe: gmail_msg_id={gmail_msg_id!r} → oportunidad #{existing.id}")
        return jsonify({
            'status': 'already_exists',
            'oportunidad_id': existing.id,
        }), 200

    # ── Crear Oportunidad ────────────────────────────────────────────────────
    empresa   = data.get('empresa') or ''
    contacto  = data.get('contacto') or ''
    sector    = data.get('sector') or ''
    provincia = data.get('provincia') or ''
    telefono  = data.get('telefono') or ''
    score_raw = data.get('score', 0)
    prioridad = data.get('prioridad') or _prioridad_from_tipo(tipo_lead)
    subject   = data.get('subject_original') or ''

    # Construir 'necesidad' con contexto del evento
    necesidad = _build_necesidad(tipo_lead, subject, data)

    try:
        score = int(score_raw)
    except (ValueError, TypeError):
        score = 0

    op = Oportunidad(
        empresa         = empresa[:300] if empresa else '',
        contacto        = contacto[:200] if contacto else '',
        email           = email[:200],
        telefono        = telefono[:100] if telefono else '',
        sector          = sector[:100] if sector else '',
        prioridad       = prioridad,
        score           = score,
        necesidad       = necesidad[:1000] if necesidad else '',
        recomendacion   = _recomendacion_from_tipo(tipo_lead),
        cuerpo_email    = subject[:500] if subject else '',
        estado          = 'nuevo',
        cuenta_origen   = data.get('bandeja_receptora') or '',
        mensaje_id      = gmail_msg_id,
    )

    # Vincular con Prospecto si viene el ID
    prospecto_id = data.get('prospecto_id')
    if prospecto_id:
        try:
            op.prospecto_creado_id = int(prospecto_id)
        except (ValueError, TypeError):
            pass

    db.session.add(op)
    db.session.flush()  # obtener id antes del commit
    oportunidad_id = op.id

    # ── Notificación in-app para equipo comercial ────────────────────────────
    urgente = tipo_lead in ('solicita_cotizacion', 'solicita_llamada', 'solicita_whatsapp')
    notif_title   = f"{'⚡ ' if urgente else ''}Lead: {empresa or email}"
    notif_message = _notif_message(tipo_lead, empresa, email, sector)
    notif_type    = 'danger' if urgente else 'warning'
    notif_link    = f'/comercial/pipeline?id={oportunidad_id}'

    _roles_comerciales = ['Master', 'Presidente de Negocios', 'Trader']

    try:
        from app.models.notification import Notification
        Notification.create_for_roles(
            roles     = _roles_comerciales,
            title     = notif_title,
            message   = notif_message,
            notif_type= notif_type,
            category  = 'client',
            link      = notif_link,
        )
    except Exception as e:
        # La notificación falla → loguear pero NO abortar la creación de oportunidad
        log.warning(f"[leads_api] Notificación fallida (oportunidad creada igual): {e}")

    db.session.commit()

    log.info(
        f"[leads_api] Oportunidad #{oportunidad_id} creada: {email} ({tipo_lead}) "
        f"empresa={empresa!r} prioridad={prioridad}"
    )

    return jsonify({
        'status':        'created',
        'oportunidad_id': oportunidad_id,
        'prioridad':      prioridad,
    }), 200


# ── Health check (sin auth) ──────────────────────────────────────────────────

@leads_api_bp.route('/health', methods=['GET'])
@csrf.exempt
def health():
    """Endpoint de health check — no requiere autenticación."""
    token_configured = bool(_QORI_CRM_TOKEN())
    return jsonify({'ok': True, 'token_configured': token_configured}), 200


# ── Helpers ──────────────────────────────────────────────────────────────────

def _prioridad_from_tipo(tipo: str) -> str:
    """Infiere prioridad según el tipo de lead cuando no se provee."""
    alta = {'solicita_cotizacion', 'solicita_llamada', 'solicita_whatsapp'}
    media = {'interesado', 'solicita_informacion', 'consulta_tc', 'respuesta_positiva'}
    if tipo in alta:
        return 'alta'
    if tipo in media:
        return 'media'
    return 'baja'


def _build_necesidad(tipo: str, subject: str, data: dict) -> str:
    """Construye el campo necesidad con contexto del evento."""
    labels = {
        'solicita_cotizacion':  'Solicita cotización de tipo de cambio',
        'solicita_llamada':     'Solicita llamada telefónica',
        'solicita_whatsapp':    'Solicita contacto por WhatsApp',
        'interesado':           'Respuesta positiva — interés general',
        'solicita_informacion': 'Solicita más información',
        'consulta_tc':          'Consulta sobre el tipo de cambio',
        'respuesta_positiva':   'Respuesta positiva a campaña de prospección',
        'referido':             'Referido por contacto de la empresa',
    }
    base = labels.get(tipo, tipo.replace('_', ' ').title())
    parts = [base]
    if subject:
        parts.append(f'Asunto original: "{subject[:200]}"')
    if data.get('fuente'):
        parts.append(f'Fuente: {data["fuente"]}')
    return ' | '.join(parts)


def _recomendacion_from_tipo(tipo: str) -> str:
    """Genera una recomendación de acción según el tipo de lead."""
    recs = {
        'solicita_cotizacion':  'Contactar inmediatamente con cotización en tiempo real.',
        'solicita_llamada':     'Llamar en menos de 2 horas hábiles.',
        'solicita_whatsapp':    'Enviar mensaje de WhatsApp con TC y presentación.',
        'interesado':           'Hacer seguimiento con propuesta de TC y casos de éxito.',
        'solicita_informacion': 'Enviar presentación corporativa y casos de uso.',
        'consulta_tc':          'Responder con TC actualizado y propuesta de servicio.',
        'respuesta_positiva':   'Agendar llamada de presentación.',
        'referido':             'Contactar al referido mencionando el punto de contacto.',
    }
    return recs.get(tipo, 'Dar seguimiento personalizado al prospecto.')


def _notif_message(tipo: str, empresa: str, email: str, sector: str) -> str:
    nombre = empresa or email
    sector_str = f' ({sector})' if sector else ''
    labels = {
        'solicita_cotizacion':  f'{nombre}{sector_str} solicita cotización TC',
        'solicita_llamada':     f'{nombre}{sector_str} solicita llamada',
        'solicita_whatsapp':    f'{nombre}{sector_str} solicita WhatsApp',
        'interesado':           f'{nombre}{sector_str} respondió positivamente',
        'solicita_informacion': f'{nombre}{sector_str} solicita más información',
        'consulta_tc':          f'{nombre}{sector_str} pregunta por el TC',
        'referido':             f'Referido desde {nombre}{sector_str}',
    }
    return labels.get(tipo, f'{nombre}{sector_str} — {tipo}')
