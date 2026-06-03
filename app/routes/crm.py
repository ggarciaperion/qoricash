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
        import re as _re
        digits = _re.sub(r'\D', '', numero)
        if digits.startswith('51') and len(digits) == 11:
            digits = digits[2:]
        if digits:
            p = (Prospecto.query
                 .filter(or_(
                     Prospecto.telefono     == digits,
                     Prospecto.telefono_alt == digits,
                     Prospecto.telefono_3   == digits,
                     Prospecto.telefono_4   == digits,
                     Prospecto.contacto_wa  == digits,
                 )).first())
            if p:
                from sqlalchemy import or_
                from app.utils.formatters import now_peru as _now
                # Buscar user_id de sistema (id=1) o primer Master
                from app.models.user import User
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
                    'fecha_ultimo_contacto': _now().strftime('%Y-%m-%d %H:%M')
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

    except Exception as e:
        log.error(f'[CRM Webhook] Error: {e}')

    return jsonify({'status': 'ok'})


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
