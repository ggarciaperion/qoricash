"""
CRM WhatsApp — QoriCash Trading V2
Webhook + Panel de conversaciones para Master
"""
import os, json, logging, requests as http_req
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from app.extensions import db, csrf
from app.models.wa_message import WaMessage
from app.utils.decorators import require_role
from app.utils.formatters import now_peru

crm_bp = Blueprint('crm', __name__, url_prefix='/crm')
log    = logging.getLogger(__name__)

WA_VERIFY_TOKEN   = os.environ.get('WA_VERIFY_TOKEN',    'qoricash_wa_verify_2026')
WA_ACCESS_TOKEN   = os.environ.get('WA_ACCESS_TOKEN',    '')
WA_PHONE_ID       = os.environ.get('WA_PHONE_NUMBER_ID', '1197587863432080')
WA_TEMPLATE_NAME  = os.environ.get('WA_TEMPLATE_NAME',   'qoricash_precios_ok')
WA_HEADER_IMAGE   = os.environ.get('WA_HEADER_IMAGE',    'https://www.qoricash.pe/banerwsp.png')
WA_API_URL        = f'https://graph.facebook.com/v19.0/{WA_PHONE_ID}/messages'


# ── PANEL PRINCIPAL ───────────────────────────────────────────────
@crm_bp.route('/whatsapp')
@login_required
@require_role('Master')
def whatsapp():
    return render_template('crm/whatsapp.html')


# ── API — lista de conversaciones ────────────────────────────────
@crm_bp.route('/api/conversaciones')
@login_required
@require_role('Master')
def api_conversaciones():
    """Devuelve la última conversación por número, ordenada por reciente."""
    from sqlalchemy import func

    # Último mensaje por número
    sub = (
        db.session.query(
            WaMessage.numero,
            func.max(WaMessage.id).label('last_id')
        )
        .group_by(WaMessage.numero)
        .subquery()
    )
    rows = (
        db.session.query(WaMessage)
        .join(sub, WaMessage.id == sub.c.last_id)
        .order_by(WaMessage.created_at.desc())
        .all()
    )

    # No leídos por número
    no_leidos = (
        db.session.query(WaMessage.numero, func.count(WaMessage.id))
        .filter(WaMessage.leido == False, WaMessage.direccion == 'entrante')
        .group_by(WaMessage.numero)
        .all()
    )
    no_leidos_map = {r[0]: r[1] for r in no_leidos}

    result = []
    for m in rows:
        result.append({
            'numero':    m.numero,
            'nombre':    m.nombre or m.numero,
            'empresa':   m.empresa,
            'ultimo':    m.mensaje[:60] + ('...' if len(m.mensaje) > 60 else ''),
            'hora':      m.created_at.strftime('%H:%M') if m.created_at else '',
            'direccion': m.direccion,
            'no_leidos': no_leidos_map.get(m.numero, 0),
        })

    return jsonify(result)


# ── API — mensajes de una conversación ───────────────────────────
@crm_bp.route('/api/mensajes/<path:numero>')
@login_required
@require_role('Master')
def api_mensajes(numero):
    """Devuelve todos los mensajes de un número y los marca como leídos."""
    mensajes = (
        WaMessage.query
        .filter_by(numero=numero)
        .order_by(WaMessage.created_at.asc())
        .all()
    )
    # Marcar como leídos
    WaMessage.query.filter_by(numero=numero, leido=False, direccion='entrante').update({'leido': True})
    db.session.commit()

    return jsonify([m.to_dict() for m in mensajes])


# ── API — enviar mensaje de texto libre ──────────────────────────
@crm_bp.route('/api/enviar', methods=['POST'])
@login_required
@require_role('Master')
def api_enviar():
    data   = request.get_json()
    numero = data.get('numero', '').strip()
    texto  = data.get('mensaje', '').strip()

    if not numero or not texto:
        return jsonify({'ok': False, 'error': 'Faltan datos'}), 400

    # Asegurar formato E.164
    digits = ''.join(c for c in numero if c.isdigit())
    if not digits.startswith('51'):
        digits = f'51{digits}'
    destino = f'+{digits}'

    headers = {'Authorization': f'Bearer {WA_ACCESS_TOKEN}', 'Content-Type': 'application/json'}
    payload = {
        'messaging_product': 'whatsapp',
        'to': destino,
        'type': 'text',
        'text': {'body': texto},
    }
    resp = http_req.post(WA_API_URL, headers=headers, json=payload, timeout=10)

    if resp.status_code == 200:
        msg = WaMessage(
            numero    = destino,
            mensaje   = texto,
            direccion = 'saliente',
            leido     = True,
        )
        db.session.add(msg)
        db.session.commit()
        return jsonify({'ok': True})
    else:
        log.error(f'[CRM] Error enviando a {destino}: {resp.text}')
        return jsonify({'ok': False, 'error': resp.json().get('error', {}).get('message', 'Error API')}), 400


# ── WEBHOOK — verificación (GET) ─────────────────────────────────
@crm_bp.route('/webhook', methods=['GET'])
@csrf.exempt
def webhook_verify():
    mode      = request.args.get('hub.mode')
    token     = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    if mode == 'subscribe' and token == WA_VERIFY_TOKEN:
        log.info('[CRM Webhook] Verificación OK')
        return challenge, 200
    return 'Forbidden', 403


# ── WEBHOOK — mensajes entrantes (POST) ──────────────────────────
@crm_bp.route('/webhook', methods=['POST'])
@csrf.exempt
def webhook_receive():
    try:
        body     = request.get_json(silent=True) or {}
        entry    = body.get('entry', [{}])[0]
        changes  = entry.get('changes', [{}])[0]
        value    = changes.get('value', {})
        messages = value.get('messages', [])
        contacts = value.get('contacts', [])

        if not messages:
            return jsonify({'status': 'ok'})

        for msg in messages:
            numero    = f"+{msg.get('from', '')}"
            wa_id     = msg.get('id', '')
            tipo      = msg.get('type', '')

            if tipo == 'text':
                texto = msg['text']['body']
            elif tipo == 'image':
                texto = '[Imagen]'
            elif tipo == 'audio':
                texto = '[Audio de voz]'
            elif tipo == 'video':
                texto = '[Video]'
            elif tipo == 'document':
                texto = '[Documento]'
            else:
                texto = f'[{tipo}]'

            contacto = next((c for c in contacts if c.get('wa_id') == msg.get('from')), {})
            nombre   = contacto.get('profile', {}).get('name', '')

            # Buscar empresa desde mensajes anteriores
            prev = WaMessage.query.filter_by(numero=numero).first()
            empresa = prev.empresa if prev else ''

            wa_msg = WaMessage(
                numero    = numero,
                nombre    = nombre,
                empresa   = empresa,
                mensaje   = texto,
                direccion = 'entrante',
                wa_id     = wa_id,
                leido     = False,
            )
            db.session.add(wa_msg)

        db.session.commit()
        log.info(f'[CRM Webhook] {len(messages)} mensaje(s) recibido(s)')

    except Exception as e:
        log.error(f'[CRM Webhook] Error: {e}')

    return jsonify({'status': 'ok'})
