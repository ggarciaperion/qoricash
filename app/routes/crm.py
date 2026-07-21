"""
CRM WhatsApp — QoriCash Trading V2
Webhook + Panel de conversaciones para Master
"""
import os, json, logging, requests as http_req
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, jsonify, abort
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
CRM_API_KEY       = os.environ.get('CRM_API_KEY',        'qoricash_crm_2026')



# ── Panel CRM WhatsApp ───────────────────────────────────────────
@crm_bp.route('/whatsapp')
@login_required
@require_role('Master')
def whatsapp_panel():
    return render_template('crm/whatsapp.html')


# ── API — lista de conversaciones ────────────────────────────────
@crm_bp.route('/api/conversaciones')
@login_required
@require_role('Master')
def api_conversaciones():
    """Devuelve la última conversación por número, ordenada por reciente."""
    from sqlalchemy import func
    try:
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
        no_leidos = (
            db.session.query(WaMessage.numero, func.count(WaMessage.id))
            .filter(WaMessage.leido == False, WaMessage.direccion == 'entrante')
            .group_by(WaMessage.numero)
            .all()
        )
        no_leidos_map = {r[0]: r[1] for r in no_leidos}

        # Números que tienen al menos 1 mensaje entrante (respondieron)
        respondio_set = {
            r[0] for r in
            db.session.query(WaMessage.numero)
            .filter(WaMessage.direccion == 'entrante')
            .distinct()
            .all()
        }
        # Números que solo tienen mensajes salientes (contactado, sin respuesta)
        saliente_set = {
            r[0] for r in
            db.session.query(WaMessage.numero)
            .filter(WaMessage.direccion == 'saliente')
            .distinct()
            .all()
        }

        result = []
        for m in rows:
            num = m.numero
            if num in respondio_set:
                estado = 'respondio'
            elif num in saliente_set:
                estado = 'contactado'
            else:
                estado = 'nuevo'
            result.append({
                'numero':    num,
                'nombre':    m.nombre or num,
                'empresa':   m.empresa,
                'ultimo':    m.mensaje[:60] + ('...' if len(m.mensaje) > 60 else ''),
                'hora':      m.created_at.strftime('%H:%M') if m.created_at else '',
                'direccion': m.direccion,
                'no_leidos': no_leidos_map.get(num, 0),
                'estado':    estado,
            })

        # Ordenar: 1º no leídos, 2º respondieron (leídos), 3º solo salientes
        result.sort(key=lambda x: (
            0 if x['no_leidos'] > 0 else
            1 if x['estado'] == 'respondio' else
            2
        ))
        return jsonify(result)
    except Exception as e:
        log.error(f'[CRM] api_conversaciones error: {e}')
        return jsonify({'error': str(e)}), 500


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


# ── API — registro desde campana externa (script local) ──────────
@crm_bp.route('/api/registro-campana', methods=['POST'])
@csrf.exempt
def api_registro_campana():
    """Recibe los mensajes enviados por campana_wa_lfc.py y los guarda como salientes."""
    api_key = request.headers.get('X-API-Key', '')
    if api_key != CRM_API_KEY:
        return jsonify({'ok': False, 'error': 'Unauthorized'}), 401

    data    = request.get_json(silent=True) or {}
    numero  = data.get('numero', '').strip()
    nombre  = data.get('nombre', '').strip()
    empresa = data.get('empresa', '').strip()
    mensaje = data.get('mensaje', '').strip()

    if not numero or not mensaje:
        return jsonify({'ok': False, 'error': 'Faltan datos'}), 400

    # Actualizar nombre/empresa en mensajes previos si estaban vacíos
    if nombre or empresa:
        WaMessage.query.filter_by(numero=numero, nombre='').update({'nombre': nombre})
        WaMessage.query.filter_by(numero=numero, empresa='').update({'empresa': empresa})

    db.session.add(WaMessage(
        numero    = numero,
        nombre    = nombre,
        empresa   = empresa,
        mensaje   = mensaje,
        direccion = 'saliente',
        leido     = True,
    ))

    # Vincular al prospecto si hay coincidencia por teléfono
    try:
        from app.models.prospecto import Prospecto, ActividadProspecto
        from app.models.user import User
        from sqlalchemy import or_ as _or
        from app.utils.formatters import now_peru as _now
        import re as _re
        digits = _re.sub(r'\D', '', numero)
        if digits.startswith('51') and len(digits) == 11:
            digits = digits[2:]
        if digits:
            p = (Prospecto.query
                 .filter(_or(
                     Prospecto.telefono     == digits,
                     Prospecto.telefono_alt == digits,
                     Prospecto.telefono_3   == digits,
                     Prospecto.telefono_4   == digits,
                     Prospecto.contacto_wa  == digits,
                 )).first())
            if p:
                sys_user = User.query.filter_by(role='Master').order_by(User.id).first()
                uid = sys_user.id if sys_user else 1
                act = ActividadProspecto(
                    prospecto_id=p.id,
                    user_id=uid,
                    tipo='whatsapp',
                    canal='whatsapp',
                    descripcion=f'WhatsApp enviado (campaña): {mensaje[:120]}',
                    resultado='Enviado',
                )
                db.session.add(act)
                Prospecto.query.filter_by(id=p.id).update({
                    'fecha_ultimo_contacto': _now().strftime('%Y-%m-%d %H:%M'),
                    'estado_comercial': 'contactado',
                }, synchronize_session=False)
    except Exception as _e:
        log.warning(f'[CRM Campaña] No se pudo vincular WA a prospecto: {_e}')

    db.session.commit()
    log.info(f'[CRM Campaña] Registrado envío → {numero} ({nombre})')
    return jsonify({'ok': True})


# ── API interna — exportar documentos de clientes ────────────────
@crm_bp.route('/api/clientes-docs', methods=['GET'])
@csrf.exempt
def api_clientes_docs():
    """Devuelve lista de DNI/RUC de todos los clientes registrados. Protegido por API key."""
    api_key = request.headers.get('X-API-Key', '')
    if api_key != CRM_API_KEY:
        return jsonify({'ok': False}), 401
    try:
        from app.models.client import Client
        clientes = db.session.query(Client.dni, Client.document_type, Client.razon_social, Client.nombres, Client.apellido_paterno, Client.email).all()
        result = [{'dni': c.dni, 'tipo': c.document_type, 'razon_social': c.razon_social or '', 'nombre': f"{c.nombres or ''} {c.apellido_paterno or ''}".strip(), 'email': c.email} for c in clientes]
        return jsonify({'ok': True, 'total': len(result), 'clientes': result})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


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

            media_id_val   = ''
            media_tipo_val = ''
            if tipo == 'text':
                texto = msg['text']['body']
            elif tipo == 'image':
                media_id_val   = msg.get('image', {}).get('id', '')
                media_tipo_val = 'image'
                caption        = msg.get('image', {}).get('caption', '')
                texto          = caption or '[Imagen]'
            elif tipo == 'sticker':
                media_id_val   = msg.get('sticker', {}).get('id', '')
                media_tipo_val = 'sticker'
                texto          = '[Sticker]'
            elif tipo == 'audio':
                media_id_val   = msg.get('audio', {}).get('id', '')
                media_tipo_val = 'audio'
                texto          = '[Audio de voz]'
            elif tipo == 'video':
                media_id_val   = msg.get('video', {}).get('id', '')
                media_tipo_val = 'video'
                caption        = msg.get('video', {}).get('caption', '')
                texto          = caption or '[Video]'
            elif tipo == 'document':
                media_id_val   = msg.get('document', {}).get('id', '')
                media_tipo_val = 'document'
                filename       = msg.get('document', {}).get('filename', 'Documento')
                texto          = filename
            elif tipo == 'contacts':
                import json as _json
                contact_list = msg.get('contacts', [])
                if contact_list:
                    c0     = contact_list[0]
                    cname  = c0.get('name', {}).get('formatted_name', 'Contacto')
                    phones = [p.get('phone', '') for p in c0.get('phones', []) if p.get('phone')]
                    emails = [e.get('email', '') for e in c0.get('emails', []) if e.get('email')]
                    texto  = '[CONTACTO:' + _json.dumps(
                        {'name': cname, 'phones': phones, 'emails': emails},
                        ensure_ascii=False
                    ) + ']'
                else:
                    texto = '[Contacto]'
            elif tipo == 'interactive':
                interactive = msg.get('interactive', {})
                i_type = interactive.get('type', '')
                if i_type == 'button_reply':
                    texto = interactive.get('button_reply', {}).get('id', '')
                elif i_type == 'list_reply':
                    texto = interactive.get('list_reply', {}).get('id', '')
                else:
                    texto = f'[interactive:{i_type}]'
            else:
                texto = f'[{tipo}]'

            contacto = next((c for c in contacts if c.get('wa_id') == msg.get('from')), {})
            nombre   = contacto.get('profile', {}).get('name', '')

            # Buscar empresa desde mensajes anteriores
            prev = WaMessage.query.filter_by(numero=numero).first()
            empresa = prev.empresa if prev else ''

            wa_msg = WaMessage(
                numero     = numero,
                nombre     = nombre,
                empresa    = empresa,
                mensaje    = texto,
                direccion  = 'entrante',
                wa_id      = wa_id,
                leido      = False,
                media_id   = media_id_val,
                media_tipo = media_tipo_val,
            )
            db.session.add(wa_msg)

            # Vincular respuesta WA al prospecto
            try:
                from app.models.prospecto import Prospecto, ActividadProspecto
                import re as _re
                from sqlalchemy import or_ as _or
                from app.utils.formatters import now_peru as _now
                digits = _re.sub(r'\D', '', numero)
                if digits.startswith('51') and len(digits) == 11:
                    digits = digits[2:]
                if digits:
                    p = (Prospecto.query
                         .filter(_or(
                             Prospecto.telefono     == digits,
                             Prospecto.telefono_alt == digits,
                             Prospecto.telefono_3   == digits,
                             Prospecto.telefono_4   == digits,
                             Prospecto.contacto_wa  == digits,
                         )).first())
                    if p:
                        from app.models.user import User
                        sys_user = User.query.filter_by(role='Master').order_by(User.id).first()
                        uid = sys_user.id if sys_user else 1
                        act_in = ActividadProspecto(
                            prospecto_id=p.id,
                            user_id=uid,
                            tipo='whatsapp',
                            canal='whatsapp',
                            descripcion=f'WhatsApp recibido: {texto[:120]}',
                            resultado='Respondió',
                        )
                        db.session.add(act_in)
                        # Si estaba sin contactar o contactado, avanzar a interesado
                        if p.estado_comercial in (None, '', 'sin_contactar', 'contactado'):
                            p.estado_comercial = 'interesado'
                        Prospecto.query.filter_by(id=p.id).update({
                            'fecha_ultimo_contacto': _now().strftime('%Y-%m-%d %H:%M')
                        }, synchronize_session=False)
            except Exception as _e:
                log.warning(f'[CRM Webhook] No se pudo vincular WA entrante a prospecto: {_e}')

        db.session.commit()
        log.info(f'[CRM Webhook] {len(messages)} mensaje(s) recibido(s)')

        # ── Bot automático ────────────────────────────────────────
        try:
            from app.services.wa_bot import handle_message as _bot
            for msg in messages:
                numero_b = f"+{msg.get('from', '')}"
                tipo_b   = msg.get('type', '')
                if tipo_b == 'text':
                    texto_b   = msg['text']['body']
                    media_b   = ''
                elif tipo_b == 'interactive':
                    interactive_b = msg.get('interactive', {})
                    i_type_b = interactive_b.get('type', '')
                    if i_type_b == 'button_reply':
                        texto_b = interactive_b.get('button_reply', {}).get('id', '')
                    elif i_type_b == 'list_reply':
                        texto_b = interactive_b.get('list_reply', {}).get('id', '')
                    else:
                        texto_b = ''
                    media_b = ''
                elif tipo_b == 'image':
                    texto_b = msg.get('image', {}).get('caption', '')
                    media_b = msg.get('image', {}).get('id', '')
                elif tipo_b == 'document':
                    texto_b = msg.get('document', {}).get('filename', '')
                    media_b = msg.get('document', {}).get('id', '')
                else:
                    texto_b = ''
                    media_b = ''
                contacto_b = next((c for c in contacts if c.get('wa_id') == msg.get('from')), {})
                nombre_b   = contacto_b.get('profile', {}).get('name', '')
                _bot(numero_b, nombre_b, tipo_b, texto_b, media_b)
        except Exception as _eb:
            log.warning(f'[CRM Webhook] Bot error: {_eb}')

        # Emitir evento real-time para cada mensaje entrante nuevo
        if messages:
            try:
                from app.extensions import socketio as _sio
                unread = WaMessage.query.filter_by(leido=False, direccion='entrante').count()
                for msg in messages:
                    numero_ev = f"+{msg.get('from', '')}"
                    contacto_ev = next((c for c in contacts if c.get('wa_id') == msg.get('from')), {})
                    nombre_ev = contacto_ev.get('profile', {}).get('name', numero_ev)
                    tipo_ev = msg.get('type', '')
                    if tipo_ev == 'text':
                        preview = msg['text']['body'][:60]
                    else:
                        preview = f'[{tipo_ev}]'
                    _sio.emit('wa_message', {
                        'numero': numero_ev,
                        'nombre': nombre_ev,
                        'preview': preview,
                        'unread': unread,
                    }, namespace='/', room='role_Master')
            except Exception as _es:
                log.warning(f'[CRM Webhook] Socket emit error: {_es}')

    except Exception as e:
        log.error(f'[CRM Webhook] Error: {e}')

    return jsonify({'status': 'ok'})


# ── API — proxy de media WhatsApp ────────────────────────────────
@crm_bp.route('/api/media/<media_id>')
@login_required
@require_role('Master')
def api_media_proxy(media_id):
    """Descarga el media de Meta y lo sirve al browser (proxy en vivo)."""
    from flask import Response, stream_with_context
    if not WA_ACCESS_TOKEN:
        return 'No access token', 503
    try:
        # Paso 1: obtener URL de descarga
        meta_r = http_req.get(
            f'https://graph.facebook.com/v19.0/{media_id}',
            headers={'Authorization': f'Bearer {WA_ACCESS_TOKEN}'},
            timeout=10,
        )
        if not meta_r.ok:
            return 'Media no disponible', 404
        dl_url = meta_r.json().get('url', '')
        if not dl_url:
            return 'URL no encontrada', 404

        # Paso 2: descargar el archivo
        media_r = http_req.get(
            dl_url,
            headers={'Authorization': f'Bearer {WA_ACCESS_TOKEN}'},
            stream=True,
            timeout=20,
        )
        if not media_r.ok:
            return 'Error descargando media', 502

        content_type = media_r.headers.get('Content-Type', 'application/octet-stream')
        return Response(
            stream_with_context(media_r.iter_content(chunk_size=8192)),
            content_type=content_type,
            headers={'Cache-Control': 'private, max-age=86400'},
        )
    except Exception as e:
        log.error(f'[CRM] media_proxy error: {e}')
        return 'Error interno', 500


# ── API — contador de mensajes WA no leídos ───────────────────────
@crm_bp.route('/api/wa-novedades')
@login_required
@require_role('Master')
def api_wa_novedades():
    """Devuelve el conteo de mensajes entrantes no leídos."""
    try:
        count = WaMessage.query.filter_by(leido=False, direccion='entrante').count()
        return jsonify({'ok': True, 'unread': count})
    except Exception as e:
        log.error(f'[CRM] wa-novedades error: {e}')
        return jsonify({'ok': True, 'unread': 0})


# ── IMPORT desde Google Sheets (uso único) ────────────────────────
@crm_bp.route('/import-sheets')
@login_required
@require_role('Master')
def import_sheets():
    """Lee WA_Respuestas del Sheets master e importa a la BD. Idempotente por wa_id."""
    try:
        import gspread
        from google.oauth2.credentials import Credentials as GCreds
        from google.auth.transport.requests import Request as GRequest

        SCOPES = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive.file',
        ]
        SHEETS_ID = os.environ.get('WA_SHEETS_ID', '1JERPeGFzZPkgB9of22gFGf6_ckJjAOnnR0bxDA55c-A')

        creds_data = {
            'client_id':     os.environ.get('GOOGLE_CLIENT_ID', ''),
            'client_secret': os.environ.get('GOOGLE_CLIENT_SECRET', ''),
            'refresh_token': os.environ.get('GOOGLE_REFRESH_TOKEN', ''),
            'token_uri':     'https://oauth2.googleapis.com/token',
        }
        creds = GCreds.from_authorized_user_info(creds_data, SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(GRequest())

        gc = gspread.Client(auth=creds)
        sh = gc.open_by_key(SHEETS_ID)
        ws = sh.worksheet('WA_Respuestas')
        filas = ws.get_all_values()

        if len(filas) <= 1:
            return jsonify({'ok': True, 'importados': 0, 'msg': 'Hoja vacía'})

        headers = [h.strip() for h in filas[0]]
        idx = {h: i for i, h in enumerate(headers)}

        importados = omitidos = 0
        for row in filas[1:]:
            def g(col): return row[idx[col]].strip() if col in idx and idx[col] < len(row) else ''

            wa_id   = g('WA_ID')
            numero  = g('NÚMERO')
            nombre  = g('NOMBRE')
            empresa = g('EMPRESA')
            mensaje = g('MENSAJE')
            fecha_s = g('FECHA')

            if not numero or not mensaje:
                continue

            if wa_id and WaMessage.query.filter_by(wa_id=wa_id).first():
                omitidos += 1
                continue

            created = now_peru()
            for fmt in ('%d/%m/%Y %H:%M', '%Y-%m-%d %H:%M', '%d/%m/%Y'):
                try:
                    created = datetime.strptime(fecha_s[:16], fmt[:len(fecha_s[:16])])
                    break
                except Exception:
                    pass

            db.session.add(WaMessage(
                numero     = numero,
                nombre     = nombre,
                empresa    = empresa,
                mensaje    = mensaje,
                direccion  = 'entrante',
                wa_id      = wa_id,
                leido      = False,
                created_at = created,
            ))
            importados += 1

        db.session.commit()
        log.info(f'[CRM] Import Sheets: {importados} importados, {omitidos} omitidos')
        return jsonify({'ok': True, 'importados': importados, 'omitidos': omitidos})

    except Exception as e:
        log.error(f'[CRM] import_sheets error: {e}')
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── API interna — importar prospectos en lote ─────────────────────
@crm_bp.route('/api/import-prospectos', methods=['POST'])
@csrf.exempt
def api_import_prospectos():
    """Inserta lotes de prospectos. Protegido por CRM_API_KEY."""
    api_key = request.headers.get('X-API-Key', '')
    if api_key != CRM_API_KEY:
        return jsonify({'ok': False, 'error': 'Unauthorized'}), 401

    from app.models.prospecto import Prospecto

    data   = request.get_json(silent=True) or {}
    action = data.get('action', 'insert')

    if action == 'truncate':
        from sqlalchemy import text
        db.session.execute(text("TRUNCATE TABLE prospectos CASCADE"))
        db.session.commit()
        return jsonify({'ok': True, 'msg': 'Tabla limpiada'})

    if action == 'count':
        return jsonify({'ok': True, 'total': Prospecto.query.count()})

    if action == 'lfc_emails':
        rows = Prospecto.query.filter(
            Prospecto.cliente_lfc.isnot(None), Prospecto.cliente_lfc != '',
            Prospecto.email.isnot(None), Prospecto.email != ''
        ).with_entities(
            Prospecto.id, Prospecto.razon_social, Prospecto.email,
            Prospecto.estado_comercial, Prospecto.estado_email,
            Prospecto.fecha_ultimo_contacto
        ).all()
        return jsonify({
            'ok': True,
            'total': len(rows),
            'emails': [{
                'id':                   r.id,
                'razon_social':         r.razon_social or '',
                'email':                r.email,
                'estado':               r.estado_comercial or '',
                'estado_email':         r.estado_email or '',
                'fecha_ultimo_contacto': r.fecha_ultimo_contacto or '',
            } for r in rows],
        })

    if action == 'restore_lfc_batch':
        emails_list = data.get('emails', [])
        if not emails_list:
            return jsonify({'ok': False, 'error': 'emails requerido'}), 400
        emails_lower = {e.lower().strip() for e in emails_list}
        updated = 0
        not_found = []
        for email in emails_lower:
            p = Prospecto.query.filter(
                db.func.lower(Prospecto.email) == email
            ).first()
            if p:
                p.cliente_lfc = 'LFC'
                updated += 1
            else:
                not_found.append(email)
        db.session.commit()
        return jsonify({'ok': True, 'updated': updated, 'not_found': len(not_found)})

    if action == 'update_contacto_batch':
        from app.models.prospecto import ActividadProspecto
        from app.models.user import User
        ids     = data.get('ids', [])
        ts      = now_peru()
        ts_str  = ts.strftime("%Y-%m-%d %H:%M")
        # Usar el primer usuario admin disponible para actividades automáticas
        sistema_user = User.query.order_by(User.id.asc()).first()
        sistema_uid  = sistema_user.id if sistema_user else None
        updated = 0
        for pid in ids:
            p = db.session.get(Prospecto, pid)
            if not p:
                continue
            p.fecha_ultimo_contacto  = ts_str
            p.fecha_proximo_contacto = (ts + timedelta(days=3)).strftime("%Y-%m-%d %H:%M")
            if not p.fecha_primer_contacto:
                p.fecha_primer_contacto = ts_str
            p.num_contactos = (p.num_contactos or 0) + 1
            if sistema_uid:
                act = ActividadProspecto(
                    prospecto_id=p.id, user_id=sistema_uid,
                    tipo='email', canal='email',
                    bandeja='ggarcia@qoricash.pe',
                    descripcion='Correo de precios LFC enviado (campaña automática)',
                    resultado='Enviado',
                )
                db.session.add(act)
            updated += 1
        db.session.commit()
        return jsonify({'ok': True, 'updated': updated})

    if action == 'lfc_stats':
        from sqlalchemy import func
        total_lfc = Prospecto.query.filter(
            Prospecto.cliente_lfc.isnot(None), Prospecto.cliente_lfc != ''
        ).count()
        con_email = Prospecto.query.filter(
            Prospecto.cliente_lfc.isnot(None), Prospecto.cliente_lfc != '',
            Prospecto.email.isnot(None), Prospecto.email != ''
        ).count()
        valores = db.session.query(Prospecto.cliente_lfc, func.count()).filter(
            Prospecto.cliente_lfc.isnot(None), Prospecto.cliente_lfc != ''
        ).group_by(Prospecto.cliente_lfc).order_by(func.count().desc()).all()
        return jsonify({
            'ok': True,
            'total_lfc': total_lfc,
            'con_email': con_email,
            'sin_email': total_lfc - con_email,
            'valores': [{'valor': v, 'cantidad': c} for v, c in valores],
        })

    if action == 'update_email_prospecto':
        # Actualiza el email de un prospecto y agrega nota de cambio
        from app.models.prospecto import ActividadProspecto
        from app.models.user import User
        email_viejo = (data.get('email_viejo') or '').strip().lower()
        email_nuevo = (data.get('email_nuevo') or '').strip().lower()
        if not email_viejo or not email_nuevo:
            return jsonify({'ok': False, 'error': 'email_viejo y email_nuevo requeridos'}), 400
        p = Prospecto.query.filter(db.func.lower(Prospecto.email) == email_viejo).first()
        if not p:
            return jsonify({'ok': False, 'error': f'Prospecto no encontrado: {email_viejo}'}), 404
        sistema_user = User.query.order_by(User.id.asc()).first()
        sistema_uid  = sistema_user.id if sistema_user else None
        p.email = email_nuevo
        if sistema_uid:
            act = ActividadProspecto(
                prospecto_id=p.id,
                user_id=sistema_uid,
                tipo='sistema',
                canal='email',
                bandeja='ggarcia@qoricash.pe',
                descripcion=f'Email actualizado automáticamente: {email_viejo} → {email_nuevo} (notificación de cambio de dirección recibida)',
                resultado='Email actualizado',
            )
            db.session.add(act)
        db.session.commit()
        return jsonify({'ok': True, 'razon_social': p.razon_social, 'email_nuevo': email_nuevo})

    if action == 'marcar_bounces':
        # Marca emails rebotados en prospectos y agrega nota en ActividadProspecto
        from app.models.prospecto import ActividadProspecto
        from app.models.user import User
        emails_list = data.get('emails', [])  # [{"email": "...", "razon": "..."}]
        bandeja     = data.get('bandeja', 'ggarcia@qoricash.pe')
        sistema_user = User.query.order_by(User.id.asc()).first()
        sistema_uid  = sistema_user.id if sistema_user else None
        marcados = 0
        no_encontrados = []
        for item in emails_list:
            email  = (item.get('email') or '').strip().lower().rstrip('.')
            razon  = (item.get('razon') or 'Email rebotado — dirección inválida')[:200]
            if not email or '@' not in email:
                continue
            p = Prospecto.query.filter(
                db.func.lower(Prospecto.email) == email
            ).first()
            if not p:
                no_encontrados.append(email)
                continue
            # Marcar estado_email como rebote (NO nullificar email, conservar para referencia)
            p.estado_email = 'rebote'
            # Agregar actividad/nota en timeline
            if sistema_uid:
                act = ActividadProspecto(
                    prospecto_id=p.id,
                    user_id=sistema_uid,
                    tipo='bounce',
                    canal='email',
                    bandeja=bandeja,
                    descripcion=f'Email inválido / rebote detectado automáticamente. Razón: {razon}',
                    resultado='Rebote',
                    nuevo_estado='rebote',
                )
                db.session.add(act)
            marcados += 1
        db.session.commit()
        return jsonify({
            'ok': True,
            'marcados': marcados,
            'no_encontrados': len(no_encontrados),
            'emails_no_encontrados': no_encontrados[:20],
        })

    if action == 'prospeccion_emails':
        # Prospectos NO-LFC con email válido, para campaña de precios
        rows = Prospecto.query.filter(
            db.or_(Prospecto.cliente_lfc.is_(None), Prospecto.cliente_lfc == ''),
            Prospecto.email.isnot(None), Prospecto.email != '',
            db.or_(
                Prospecto.estado_comercial.is_(None),
                ~Prospecto.estado_comercial.in_(['no_contactar', 'no contactar']),
            ),
            db.or_(
                Prospecto.estado_email.is_(None),
                ~Prospecto.estado_email.in_(['rebote', 'bounce', 'no_contactar', 'no contactar', 'rechazado']),
            ),
        ).with_entities(
            Prospecto.id, Prospecto.razon_social, Prospecto.email,
            Prospecto.estado_comercial, Prospecto.estado_email,
            Prospecto.fecha_ultimo_contacto
        ).all()
        return jsonify({
            'ok': True,
            'total': len(rows),
            'emails': [{
                'id':                    r.id,
                'razon_social':          r.razon_social or '',
                'email':                 r.email,
                'estado':                r.estado_comercial or '',
                'estado_email':          r.estado_email or '',
                'fecha_ultimo_contacto': r.fecha_ultimo_contacto or '',
            } for r in rows],
        })

    if action == 'update_prospeccion_batch':
        from app.models.prospecto import ActividadProspecto
        from app.models.user import User
        ids     = data.get('ids', [])
        bandeja = data.get('bandeja', 'ggarcia@qoricash.pe')
        ts      = now_peru()
        ts_str  = ts.strftime("%Y-%m-%d %H:%M")
        sistema_user = User.query.order_by(User.id.asc()).first()
        sistema_uid  = sistema_user.id if sistema_user else None
        updated = 0
        for pid in ids:
            p = db.session.get(Prospecto, pid)
            if not p:
                continue
            p.fecha_ultimo_contacto  = ts_str
            p.fecha_proximo_contacto = (ts + timedelta(days=3)).strftime("%Y-%m-%d %H:%M")
            if not p.fecha_primer_contacto:
                p.fecha_primer_contacto = ts_str
            p.num_contactos = (p.num_contactos or 0) + 1
            if sistema_uid:
                act = ActividadProspecto(
                    prospecto_id=p.id, user_id=sistema_uid,
                    tipo='email', canal='email',
                    bandeja=bandeja,
                    descripcion='Correo de precios enviado (campaña automática)',
                    resultado='Enviado',
                )
                db.session.add(act)
            updated += 1
        db.session.commit()
        return jsonify({'ok': True, 'updated': updated})

    if action == 'export_all':
        # Exporta TODOS los prospectos con campos completos (incluyendo LFC)
        from app.models.prospecto import Prospecto as P, AsignacionProspecto, ActividadProspecto, ProspectoEmail
        from sqlalchemy import func as _func
        prosp_all = P.query.order_by(P.id.asc()).all()
        ids_all   = [p.id for p in prosp_all]
        # Trader map
        asigs_all = AsignacionProspecto.query.filter(
            AsignacionProspecto.prospecto_id.in_(ids_all),
            AsignacionProspecto.activo == True
        ).all() if ids_all else []
        tmap_all = {}
        for a in asigs_all:
            if a.prospecto_id not in tmap_all and a.trader:
                tmap_all[a.prospecto_id] = a.trader.username
        # Emails extra
        extras_all = ProspectoEmail.query.filter(
            ProspectoEmail.prospecto_id.in_(ids_all),
            ProspectoEmail.activo == True,
        ).all() if ids_all else []
        emap_all = {}
        for e in extras_all:
            emap_all.setdefault(e.prospecto_id, []).append(e.email)
        # Última actividad
        lat_subq = (
            db.session.query(
                ActividadProspecto.prospecto_id,
                _func.max(ActividadProspecto.creado_en).label('max_ts'),
            ).group_by(ActividadProspecto.prospecto_id).subquery()
        )
        act_rows_all = (
            db.session.query(ActividadProspecto)
            .join(lat_subq, (ActividadProspecto.prospecto_id == lat_subq.c.prospecto_id) &
                  (ActividadProspecto.creado_en == lat_subq.c.max_ts))
            .all()
        )
        amap_all = {a.prospecto_id: a for a in act_rows_all}
        result = []
        for p in prosp_all:
            extra_emails = emap_all.get(p.id, [])
            ult = amap_all.get(p.id)
            result.append({
                'id':                     p.id,
                'razon_social':           p.razon_social or '',
                'ruc':                    p.ruc or '',
                'tipo':                   p.tipo or '',
                'rubro':                  p.rubro or '',
                'departamento':           p.departamento or '',
                'provincia':              p.provincia or '',
                'distrito':               getattr(p, 'distrito', '') or '',
                'web':                    getattr(p, 'web', '') or '',
                'nombre_contacto':        p.nombre_contacto or '',
                'cargo':                  p.cargo or '',
                'email':                  p.email or '',
                'email_alt':              p.email_alt or '',
                'emails_extra':           extra_emails,
                'telefono':               p.telefono or '',
                'telefono_alt':           getattr(p, 'telefono_alt', '') or '',
                'telefono_3':             getattr(p, 'telefono_3', '') or '',
                'telefono_4':             getattr(p, 'telefono_4', '') or '',
                'tamano_empresa':         getattr(p, 'tamano_empresa', '') or '',
                'volumen_estimado_usd':   float(getattr(p, 'volumen_estimado_usd', None) or 0) or None,
                'prioridad':              getattr(p, 'prioridad', '') or '',
                'cliente_lfc':            p.cliente_lfc or '',
                'score':                  p.score or 0,
                'clasificacion':          p.clasificacion or '',
                'canal':                  p.canal or '',
                'fuente':                 p.fuente or '',
                'remitente':              p.remitente or '',
                'tipo_ultimo_envio':      p.tipo_ultimo_envio or '',
                'estado_email':           p.estado_email or '',
                'estado_comercial':       p.estado_comercial or '',
                'nivel_interes':          p.nivel_interes or '',
                'grupo':                  p.grupo or '',
                'notas':                  p.notas or '',
                'sin_whatsapp':           getattr(p, 'sin_whatsapp', False) or False,
                'fecha_primer_contacto':  p.fecha_primer_contacto or '',
                'fecha_ultimo_contacto':  p.fecha_ultimo_contacto or '',
                'fecha_proximo_contacto': p.fecha_proximo_contacto or '',
                'num_contactos':          p.num_contactos or 0,
                'trader':                 tmap_all.get(p.id, ''),
                'ult_actividad_tipo':     ult.tipo if ult else '',
                'ult_actividad_fecha':    ult.creado_en.strftime('%Y-%m-%d %H:%M') if ult and ult.creado_en else '',
                'ult_actividad_desc':     (ult.descripcion or '')[:200] if ult else '',
                'creado_en':              p.creado_en.strftime('%Y-%m-%d %H:%M') if p.creado_en else '',
                'actualizado_en':         p.actualizado_en.strftime('%Y-%m-%d %H:%M') if p.actualizado_en else '',
            })
        return jsonify({'ok': True, 'total': len(result), 'prospectos': result})

    if action == 'list_identifiers':
        # Devuelve RUC + razon_social de todos los prospectos
        from app.models.client import Client
        prosp = Prospecto.query.with_entities(
            Prospecto.ruc, Prospecto.razon_social, Prospecto.email
        ).all()
        clientes = Client.query.with_entities(
            Client.dni, Client.razon_social, Client.email,
            Client.document_type
        ).all()
        return jsonify({
            'ok': True,
            'prospectos': [
                {'ruc': r.ruc, 'razon_social': r.razon_social, 'email': r.email}
                for r in prosp
            ],
            'clientes': [
                {
                    'ruc': c.dni if c.document_type == 'RUC' else None,
                    'razon_social': c.razon_social,
                    'email': c.email,
                    'document_type': c.document_type
                }
                for c in clientes
            ],
        })

    if action == 'delete_prospecto':
        from app.models.prospecto import AsignacionProspecto, ActividadProspecto, ProspectoEmail, SeguimientoProspecto
        email = (data.get('email') or '').strip().lower()
        if not email:
            return jsonify({'ok': False, 'error': 'email requerido'}), 400
        p = Prospecto.query.filter(db.func.lower(Prospecto.email) == email).first()
        if not p:
            return jsonify({'ok': False, 'error': f'No encontrado: {email}'}), 404
        pid = p.id
        razon = p.razon_social
        AsignacionProspecto.query.filter_by(prospecto_id=pid).delete()
        ActividadProspecto.query.filter_by(prospecto_id=pid).delete()
        ProspectoEmail.query.filter_by(prospecto_id=pid).delete()
        SeguimientoProspecto.query.filter_by(prospecto_id=pid).delete()
        db.session.delete(p)
        db.session.commit()
        return jsonify({'ok': True, 'eliminado': {'id': pid, 'razon_social': razon, 'email': email}})

    if action == 'delete_por_nombre':
        from app.models.prospecto import AsignacionProspecto, ActividadProspecto, ProspectoEmail, SeguimientoProspecto
        nombre = (data.get("nombre") or "").strip()
        if not nombre or len(nombre) < 3:
            return jsonify({"ok": False, "error": "nombre requerido (min 3 chars)"}), 400
        matches = Prospecto.query.filter(Prospecto.razon_social.ilike(f"%{nombre}%")).all()
        if not matches:
            return jsonify({"ok": True, "deleted": 0, "eliminados": [], "mensaje": "Ningun prospecto encontrado"})
        eliminados = []
        for p in matches:
            pid = p.id
            eliminados.append({"id": pid, "razon_social": p.razon_social, "email": p.email})
            AsignacionProspecto.query.filter_by(prospecto_id=pid).delete()
            ActividadProspecto.query.filter_by(prospecto_id=pid).delete()
            ProspectoEmail.query.filter_by(prospecto_id=pid).delete()
            SeguimientoProspecto.query.filter_by(prospecto_id=pid).delete()
            db.session.delete(p)
        db.session.commit()
        return jsonify({"ok": True, "deleted": len(eliminados), "eliminados": eliminados})


    if action == 'delete_bulk_email':
        # Elimina prospectos por lista de emails (hasta 300 por llamada)
        from app.models.prospecto import ActividadProspecto, AsignacionProspecto, ProspectoEmail, SeguimientoProspecto
        emails_input = [e.strip().lower() for e in data.get('emails', []) if e and e.strip()]
        if not emails_input:
            return jsonify({'ok': True, 'eliminados': 0})
        ids_raw = Prospecto.query.filter(
            db.func.lower(Prospecto.email).in_(emails_input)
        ).with_entities(Prospecto.id).all()
        id_list = [r[0] for r in ids_raw]
        if not id_list:
            return jsonify({'ok': True, 'eliminados': 0, 'encontrados': 0})
        SeguimientoProspecto.query.filter(SeguimientoProspecto.prospecto_id.in_(id_list)).delete(synchronize_session=False)
        ActividadProspecto.query.filter(ActividadProspecto.prospecto_id.in_(id_list)).delete(synchronize_session=False)
        AsignacionProspecto.query.filter(AsignacionProspecto.prospecto_id.in_(id_list)).delete(synchronize_session=False)
        ProspectoEmail.query.filter(ProspectoEmail.prospecto_id.in_(id_list)).delete(synchronize_session=False)
        Prospecto.query.filter(Prospecto.id.in_(id_list)).delete(synchronize_session=False)
        db.session.commit()
        return jsonify({'ok': True, 'eliminados': len(id_list)})

    if action == 'purge_sector_publico':
        from app.models.prospecto import ActividadProspecto, AsignacionProspecto, ProspectoEmail, SeguimientoProspecto
        from sqlalchemy import or_, func as _func

        PATRONES_RS = [
            '%ministerio%', '%municipalidad%', '%gobierno regional%', '%gobierno local%',
            '%gobierno distrit%', '%gobierno provinc%',
            '%essalud%', '%sunat%', '%sunarp%', '%sunass%', '%susalud%',
            '%indecopi%', '%osinergmin%', '%osiptel%', '%ositran%', '%oefa%', '%osce%',
            '%poder judicial%', '%ministerio publico%', '%ministerio público%',
            '%fiscalia%', '%fiscalía%', '%defensoria%', '%defensoría%',
            '%banco de la nacion%', '%banco de la nación%', '%banco central de reserva%',
            '%contraloria%', '%contraloría%',
            '%congreso de la republica%', '%congreso de la república%',
            '%provias%', '%cofopri%', '%proinversion%', '%proinversión%',
            '%devida%', '%concytec%', '%sineace%',
            '%ugel%', '%dirección regional%', '%direccion regional%',
            '%gerencia regional%', '%gerencia sub regional%',
            '%sedapal%', '%emapa%', '%eps %',
            '%proyecto especial%', '%autoridad nacional%', '%autoridad para%',
            '%tribunal%constitucional%', '%jurado nacional%',
            '%cuerpo general de bomberos%', '%compañia de bomberos%',
            '%policia nacional%', '%policía nacional%',
            '%ejercito del peru%', '%ejército del perú%',
            '%marina de guerra%', '%fuerza aerea%', '%fuerza aérea%',
            '%inpe%', '%migraciones%', '%senamhi%',
            '%foncodes%', '%pronied%', '%agrorural%',
            '%conadis%', '%seguro integral de salud%',
            '%promperu%', '%promperú%', '%sierra y selva exportadora%',
            '%senasa%', '%sernanp%', '%inia%', '%ana %', '% ana%',
            '%servicio nacional%', '%servicio de agua%',
            '%electro%oriente%', '%electro%centro%', '%electro%sur%', '%electro%norte%',
            '%electro%ucayali%', '%electro%puno%',
            '%luz del sur%sociedad%', '%hidrandina%', '%enosa%', '%electroperu%',
            '%petroperu%', '%perupetro%',
            '%enapu%', '%corpac%', '%aeropuerto%peru%',
            '%instituto peruano%', '%instituto nacional%',
            '%agencia peruana%', '%agencia de promocion%',
            '%autoridad portuaria%', '%autoridad de transporte%',
            '%programa nacional%', '%programa de desarrollo%',
            '%unidad ejecutora%', '%sede administrativa%',
            '%red de salud%', '%red asistencial%',
            '%hospital nacional%', '%hospital regional%',
            '%hospital de apoyo%', '%instituto especializado%',
            '%centro de salud%', '% puesto de salud%',
            '%universidad nacional%',
            '%superintendencia%',
        ]

        # Condiciones por email .gob.pe
        cond_email = or_(
            Prospecto.email.ilike('%.gob.pe'),
            Prospecto.email_alt.ilike('%.gob.pe'),
            Prospecto.email_3.ilike('%.gob.pe'),
            Prospecto.email_4.ilike('%.gob.pe'),
        )

        # Condiciones por razón social
        cond_rs = or_(*[Prospecto.razon_social.ilike(p) for p in PATRONES_RS])

        condicion_total = or_(cond_email, cond_rs)

        # Obtener IDs
        ids_raw = Prospecto.query.filter(condicion_total).with_entities(Prospecto.id).all()
        id_list = [r[0] for r in ids_raw]

        if not id_list:
            return jsonify({'ok': True, 'eliminados': 0, 'msg': 'No se encontraron registros públicos'})

        # Eliminar en lotes de 1000 para evitar timeout
        CHUNK = 1000
        eliminados = 0
        for i in range(0, len(id_list), CHUNK):
            chunk = id_list[i:i+CHUNK]
            SeguimientoProspecto.query.filter(SeguimientoProspecto.prospecto_id.in_(chunk)).delete(synchronize_session=False)
            ActividadProspecto.query.filter(ActividadProspecto.prospecto_id.in_(chunk)).delete(synchronize_session=False)
            AsignacionProspecto.query.filter(AsignacionProspecto.prospecto_id.in_(chunk)).delete(synchronize_session=False)
            ProspectoEmail.query.filter(ProspectoEmail.prospecto_id.in_(chunk)).delete(synchronize_session=False)
            Prospecto.query.filter(Prospecto.id.in_(chunk)).delete(synchronize_session=False)
            db.session.commit()
            eliminados += len(chunk)

        total_restante = Prospecto.query.count()
        return jsonify({'ok': True, 'eliminados': eliminados, 'total_restante': total_restante})

    registros = data.get('registros', [])
    if not registros:
        return jsonify({'ok': True, 'insertados': 0})

    objs = [Prospecto(**r) for r in registros]
    db.session.bulk_save_objects(objs)
    db.session.commit()
    return jsonify({'ok': True, 'insertados': len(objs)})


# ── API interna — validar y limpiar teléfonos de prospectos ───────
@crm_bp.route('/api/limpiar-telefonos', methods=['POST'])
@csrf.exempt
def api_limpiar_telefonos():
    """Valida los teléfonos de todos los prospectos.
    Conserva sólo celulares peruanos válidos (9 dígitos, comienzan con 9).
    Elimina fijos, internacionales y formatos inválidos.
    Protegido por CRM_API_KEY.
    """
    import re as _re

    api_key = request.headers.get('X-API-Key', '')
    if api_key != CRM_API_KEY:
        return jsonify({'ok': False, 'error': 'Unauthorized'}), 401

    from app.models.prospecto import Prospecto

    def _normalizar(raw):
        """Retorna 9 dígitos si es celular peruano válido, sino None."""
        if not raw:
            return None
        digits = _re.sub(r'\D', '', str(raw).strip())
        # Quitar código de país Perú si está presente
        if len(digits) == 12 and digits.startswith('519'):
            digits = digits[3:]
        elif len(digits) == 11 and digits.startswith('51'):
            digits = digits[2:]
        # Celular peruano: 9 dígitos comenzando con 9
        if len(digits) == 9 and digits.startswith('9'):
            return digits
        return None

    PHONE_FIELDS = ['telefono', 'telefono_alt', 'telefono_3', 'telefono_4', 'contacto_wa']
    stats = {f: {'revisados': 0, 'validos': 0, 'eliminados': 0} for f in PHONE_FIELDS}
    modificados = 0
    ejemplos_eliminados = []

    try:
        prospectos = Prospecto.query.all()
        total = len(prospectos)

        for p in prospectos:
            cambio = False
            for campo in PHONE_FIELDS:
                val = getattr(p, campo, None)
                if val:
                    stats[campo]['revisados'] += 1
                    cleaned = _normalizar(val)
                    if cleaned:
                        stats[campo]['validos'] += 1
                        if str(val).strip() != cleaned:
                            setattr(p, campo, cleaned)
                            cambio = True
                    else:
                        stats[campo]['eliminados'] += 1
                        if len(ejemplos_eliminados) < 20:
                            ejemplos_eliminados.append({
                                'id': p.id,
                                'campo': campo,
                                'valor': str(val).strip(),
                                'razon_social': p.razon_social or '',
                            })
                        setattr(p, campo, None)
                        cambio = True
            if cambio:
                modificados += 1

        db.session.commit()
        log.info(f'[CRM] limpiar-telefonos: {modificados} prospectos modificados de {total}')

        total_eliminados = sum(s['eliminados'] for s in stats.values())
        total_validos    = sum(s['validos']    for s in stats.values())
        total_revisados  = sum(s['revisados']  for s in stats.values())

        return jsonify({
            'ok': True,
            'total_prospectos': total,
            'prospectos_modificados': modificados,
            'telefonos_revisados': total_revisados,
            'telefonos_validos': total_validos,
            'telefonos_eliminados': total_eliminados,
            'detalle_por_campo': stats,
            'ejemplos_eliminados': ejemplos_eliminados,
        })

    except Exception as e:
        db.session.rollback()
        log.error(f'[CRM] limpiar-telefonos error: {e}')
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── Limpieza historial WA anterior a julio 2026 ───────────────────
@crm_bp.route('/api/limpiar-wa-historial', methods=['POST'])
@login_required
@require_role('Master')
def api_limpiar_wa_historial():
    from datetime import date
    from app.models.wa_bot_session import WaBotSession
    cutoff = datetime(2026, 7, 1)
    msgs_del = WaMessage.query.filter(WaMessage.created_at < cutoff).delete()
    # Eliminar sesiones cuyos números no tengan mensajes después del cutoff
    numeros_activos = {r[0] for r in db.session.query(WaMessage.numero).distinct().all()}
    sesiones_del = WaBotSession.query.filter(
        ~WaBotSession.numero.in_(numeros_activos)
    ).delete(synchronize_session='fetch')
    db.session.commit()
    log.info(f'[CRM] Limpieza WA: {msgs_del} mensajes, {sesiones_del} sesiones eliminadas')
    return jsonify({'ok': True, 'mensajes_eliminados': msgs_del, 'sesiones_eliminadas': sesiones_del})
