"""
CRM WhatsApp — QoriCash Trading V2
Webhook + Panel de conversaciones para Master
"""
import os, json, logging, requests as http_req
from datetime import datetime
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
