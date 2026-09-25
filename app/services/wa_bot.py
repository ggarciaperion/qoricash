"""
WaBot — Chatbot de WhatsApp para Qoricash
Flujo: Bienvenida → Cotizar / Registrarme / Hablar con asesor
"""
import os, re, logging, requests, uuid
from app.extensions import db
from app.models.wa_bot_session import WaBotSession
from app.models.wa_message import WaMessage

log = logging.getLogger(__name__)

WA_ACCESS_TOKEN = os.environ.get('WA_ACCESS_TOKEN', '')
WA_PHONE_ID     = os.environ.get('WA_PHONE_NUMBER_ID', '1118979324636599')
WA_API_URL      = f'https://graph.facebook.com/v19.0/{WA_PHONE_ID}/messages'

ASESOR_NUMERO   = os.environ.get('WA_ASESOR_NUMERO', '51910624404')

# Números de administración que reciben alertas del bot (registro, asesor, nueva op)
ADMIN_WA_NUMEROS = ['51926011920', '51906237356']

# Email de los operadores para notificaciones de respaldo (siempre llega)
ADMIN_EMAILS = ['gerencia@qoricash.pe', 'ggarcia@qoricash.pe']

# Nombre de la plantilla aprobada por Meta para alertas a operadores.
# Debe tener exactamente 1 variable {{1}} en el cuerpo.
# Si la plantilla no existe aún en Meta, la función cae al fallback de email.
ADMIN_ALERT_TEMPLATE = 'qoricash_alerta_operador'


def _notificar_admins_email(asunto, cuerpo_texto):
    """Envía email a los operadores. Siempre llega, no depende de ventana WA."""
    try:
        from flask_mail import Message as MailMessage
        from app.extensions import mail
        from flask import current_app
        import eventlet as _ev

        def _send():
            with current_app.app_context():
                try:
                    msg = MailMessage(
                        subject=asunto,
                        sender=current_app.config.get('MAIL_DEFAULT_SENDER', 'info@qoricash.pe'),
                        recipients=ADMIN_EMAILS,
                        body=cuerpo_texto,
                    )
                    mail.send(msg)
                    log.info(f'[WaBot] Email de alerta enviado a {ADMIN_EMAILS}')
                except Exception as e_mail:
                    log.warning(f'[WaBot] Error enviando email de alerta: {e_mail}')

        _ev.spawn_n(_send)
    except Exception as e:
        log.warning(f'[WaBot] No se pudo preparar email de alerta: {e}')


def _download_wa_media_to_cloudinary(media_id, client_id):
    """
    Descarga un archivo media de Meta y lo sube a Cloudinary (llamada síncrona).

    Flujo:
      1. GET https://graph.facebook.com/v19.0/{media_id}  → obtener URL de descarga
      2. GET dl_url                                         → descargar bytes
      3. cloudinary.uploader.upload(bytes, resource_type='auto', type='authenticated')
      4. Construye URL firmada permanente con el resource_type REAL del proveedor.
         'url'        → campos *_url del cliente (URL firmada, sin firma de tiempo → permanente).
         'media_path' → JSON con public_id + resource_type + delivery_type, para el proxy CRM.
                        El proxy usa resource_type real al generar la URL firmada de entrega.

    Returns:
        dict: {'url', 'public_id', 'resource_type', 'media_path'} si todos los pasos tienen éxito.
        None: si cualquier paso falla (se registra un warning).
    """
    try:
        import cloudinary.uploader

        # Paso 1: URL de descarga de Meta
        _meta_r = requests.get(
            f'https://graph.facebook.com/v19.0/{media_id}',
            headers={'Authorization': f'Bearer {WA_ACCESS_TOKEN}'},
            timeout=10,
        )
        if not _meta_r.ok:
            log.warning(f'[KYC] Meta media no disponible: {media_id} ({_meta_r.status_code})')
            return None
        _dl_url = _meta_r.json().get('url', '')
        if not _dl_url:
            return None

        # Paso 2: Descargar bytes del archivo
        _media_r = requests.get(
            _dl_url,
            headers={'Authorization': f'Bearer {WA_ACCESS_TOKEN}'},
            timeout=30,
        )
        if not _media_r.ok:
            log.warning(f'[KYC] Error descargando media {media_id}: {_media_r.status_code}')
            return None

        # Paso 3: Subir con resource_type='auto' (detección automática) y
        # type='authenticated' (entrega restringida). El proveedor devuelve el
        # resource_type real en la respuesta ('image', 'video', 'raw', …).
        _public_id = f'kyc_wa/{client_id}/{media_id}'
        _upload = cloudinary.uploader.upload(
            _media_r.content,
            public_id=_public_id,
            resource_type='auto',
            overwrite=False,
            type='authenticated',
        )
        _cld_pub_id  = _upload.get('public_id', '')
        _cld_res_typ = _upload.get('resource_type', 'image')   # tipo real del proveedor
        _cld_url     = _upload.get('secure_url') or _upload.get('url', '')
        if not _cld_pub_id:
            log.warning(f'[KYC] Cloudinary no devolvió public_id para {media_id}')
            return None

        # Paso 4: URL firmada permanente (sin expires_at) para la ficha del cliente.
        # Requiere que api_key/api_secret estén configurados en CLOUDINARY_URL.
        # Si faltan credenciales, se usa secure_url (será 401 sin firma; entorno dev).
        import json as _json_cld
        import cloudinary.utils as _cld_utils
        try:
            _signed_url, _ = _cld_utils.cloudinary_url(
                _cld_pub_id,
                resource_type=_cld_res_typ,
                type='authenticated',
                sign_url=True,
                secure=True,
            )
        except Exception as _sign_err:
            log.warning(f'[KYC] No se pudo firmar URL Cloudinary: {_sign_err}')
            _signed_url = _cld_url

        # Metadatos para el proxy del chat (crm.py): resource_type real, no 'auto'.
        _media_path = _json_cld.dumps({
            'public_id':     _cld_pub_id,
            'resource_type': _cld_res_typ,
            'delivery_type': 'authenticated',
        })

        log.info(
            f'[KYC] media_id={media_id} persistido en Cloudinary '
            f'client={client_id} resource_type={_cld_res_typ}'
        )
        return {
            'url':           _signed_url or _cld_url,  # URL firmada para ficha cliente
            'public_id':     _cld_pub_id,
            'resource_type': _cld_res_typ,
            'media_path':    _media_path,               # JSON para proxy firmado del chat
        }

    except Exception as _e_cld:
        log.warning(f'[KYC] Error en _download_wa_media_to_cloudinary {media_id}: {_e_cld}')
        return None


def _notificar_admins_wa(mensaje):
    """
    Envía alerta WA a todos los números de administración.

    Estrategia de dos capas:
    1. Template aprobado (ADMIN_ALERT_TEMPLATE) — funciona SIN ventana de 24h.
       Si la plantilla no existe o Meta la rechaza, cae al paso 2.
    2. Texto libre — solo funciona si el número tiene ventana de 24h activa.
       (ocurre cuando el operador interactuó con el bot recientemente)

    El email (_notificar_admins_email) se llama por separado en cada punto
    de alerta para garantizar entrega independientemente del estado WA.
    """
    for num in ADMIN_WA_NUMEROS:
        enviado = False
        # ── Intento 1: plantilla aprobada (sin restricción 24h) ─────────
        try:
            payload_tmpl = {
                'messaging_product': 'whatsapp',
                'to': num,
                'type': 'template',
                'template': {
                    'name': ADMIN_ALERT_TEMPLATE,
                    'language': {'code': 'es'},
                    'components': [{
                        'type': 'body',
                        'parameters': [{'type': 'text', 'text': mensaje}]
                    }]
                }
            }
            r = requests.post(WA_API_URL, json=payload_tmpl, headers=_headers(), timeout=10)
            if r.ok:
                log.info(f'[WaBot] Alerta admin (template) enviada a {num}')
                enviado = True
            else:
                log.warning(f'[WaBot] Template admin rechazado por Meta ({num}): {r.status_code} — {r.text[:200]}')
        except Exception as e:
            log.warning(f'[WaBot] Error template admin {num}: {e}')

        if enviado:
            continue

        # ── Intento 2: texto libre (requiere ventana 24h activa) ────────
        try:
            payload_txt = {
                'messaging_product': 'whatsapp',
                'to': num,
                'type': 'text',
                'text': {'body': mensaje},
            }
            r2 = requests.post(WA_API_URL, json=payload_txt, headers=_headers(), timeout=10)
            if r2.ok:
                log.info(f'[WaBot] Alerta admin (texto) enviada a {num}')
            else:
                log.warning(f'[WaBot] Texto admin rechazado por Meta ({num}): {r2.status_code} — ventana 24h cerrada')
        except Exception as e2:
            log.warning(f'[WaBot] Error texto admin {num}: {e2}')

# 1 pip = 0.0001 (estándar forex para pares con PEN)
SPREAD_TC = 0.0020   # 20 pips: spread que aplica el bot sobre el TC oficial

COTIZ_VALIDEZ_MIN      = 15   # minutos de validez de la cotización
SESSION_INACTIVIDAD_MIN = 15  # minutos de inactividad para expirar sesión
MONTO_MINIMO_USD       = 50   # mínimo de operación en USD

def _lookup_dni(dni):
    """
    Consulta RENIEC vía decolecta.com (primario) o apis.net.pe (fallback).
    Retorna nombre completo en formato 'Nombres Apellidos' o None si no encuentra.
    """
    import json as _json
    token = (os.environ.get('APIS_NET_PE_TOKEN') or '').strip()
    try:
        if token:
            url  = f'https://api.decolecta.com/v1/reniec/dni?numero={dni}'
            hdrs = {'Accept': 'application/json', 'User-Agent': 'QoriCash/2.0',
                    'Authorization': f'Bearer {token}'}
        else:
            url  = f'https://api.apis.net.pe/v1/dni?numero={dni}'
            hdrs = {'Accept': 'application/json', 'User-Agent': 'QoriCash/2.0'}

        r = requests.get(url, headers=hdrs, timeout=5)
        if r.status_code != 200:
            return None
        data    = r.json()
        nombres = (data.get('nombres') or data.get('nombre') or '').strip().title()
        ap_pat  = (data.get('apellidoPaterno') or data.get('apellido_paterno') or '').strip().title()
        ap_mat  = (data.get('apellidoMaterno') or data.get('apellido_materno') or '').strip().title()
        if not nombres and not ap_pat:
            return None
        return f'{nombres} {ap_pat} {ap_mat}'.strip()
    except Exception as e:
        log.warning(f'[WaBot] _lookup_dni error: {e}')
        return None


def _lookup_ruc(ruc):
    """
    Consulta SUNAT vía decolecta.com (primario) o apis.net.pe (fallback).
    Retorna razón social en título o None si no encuentra.
    """
    import json as _json
    token = (os.environ.get('APIS_NET_PE_TOKEN') or '').strip()
    try:
        if token:
            url  = f'https://api.decolecta.com/v1/sunat/ruc?numero={ruc}'
            hdrs = {'Accept': 'application/json', 'User-Agent': 'QoriCash/2.0',
                    'Authorization': f'Bearer {token}'}
        else:
            url  = f'https://api.apis.net.pe/v1/ruc?numero={ruc}'
            hdrs = {'Accept': 'application/json', 'User-Agent': 'QoriCash/2.0'}

        r = requests.get(url, headers=hdrs, timeout=5)
        if r.status_code != 200:
            return None
        data = r.json()
        razon = (data.get('razon_social') or data.get('nombre') or data.get('razonSocial') or '').strip().title()
        return razon or None
    except Exception as e:
        log.warning(f'[WaBot] _lookup_ruc error: {e}')
        return None


def _mejora_tc(importe):
    """Retorna la mejora de TC (en valor absoluto) según el importe en USD."""
    if importe >= 10000:
        return 0.0020   # 20 pips
    elif importe >= 5000:
        return 0.0015   # 15 pips
    elif importe >= 3000:
        return 0.0010   # 10 pips
    else:
        return 0.0000   # sin mejora


# ── Envío de mensajes ──────────────────────────────────────────────

def _headers():
    return {
        'Authorization': f'Bearer {WA_ACCESS_TOKEN}',
        'Content-Type': 'application/json',
    }


def _save_outgoing(numero, texto):
    # Normalizar formato: siempre con + para coincidir con mensajes entrantes
    if numero and not numero.startswith('+'):
        numero = '+' + numero
    try:
        db.session.add(WaMessage(
            numero=numero, mensaje=texto, direccion='saliente', leido=True
        ))
        db.session.commit()
    except Exception as e:
        log.warning(f'[WaBot] No se pudo guardar saliente: {e}')


def wa_notify_client(client, mensaje):
    """Envía un mensaje WA al cliente si tiene teléfono registrado. Uso externo."""
    if not client:
        return
    phone_raw = (getattr(client, 'phone', None) or '').split(';')[0].strip()
    phone_digits = ''.join(c for c in phone_raw if c.isdigit())
    if not phone_digits:
        return
    if not phone_digits.startswith('51'):
        phone_digits = '51' + phone_digits
    send_text(phone_digits, mensaje)


def wa_notify_client_buttons(client, mensaje, buttons):
    """Envía un mensaje WA con botones interactivos al cliente. Uso externo."""
    if not client:
        return
    phone_raw = (getattr(client, 'phone', None) or '').split(';')[0].strip()
    phone_digits = ''.join(c for c in phone_raw if c.isdigit())
    if not phone_digits:
        return
    if not phone_digits.startswith('51'):
        phone_digits = '51' + phone_digits
    send_buttons(phone_digits, mensaje, buttons)


def wa_notify_cuenta_activa(client):
    """Envía WA de cuenta activada usando plantilla aprobada. Sin restricción de 24h."""
    if not client:
        return
    phone_raw = (getattr(client, 'phone', None) or '').split(';')[0].strip()
    phone_digits = ''.join(c for c in phone_raw if c.isdigit())
    if not phone_digits:
        return
    if not phone_digits.startswith('51'):
        phone_digits = '51' + phone_digits
    # Usar campo 'nombres' para obtener el primer nombre (no apellido)
    nombres_raw = getattr(client, 'nombres', None) or getattr(client, 'razon_social', None) or 'Cliente'
    primer_nombre = nombres_raw.strip().split()[0].title() if nombres_raw.strip() else 'Cliente'
    payload = {
        'messaging_product': 'whatsapp',
        'to': phone_digits,
        'type': 'template',
        'template': {
            'name': 'qoricash_cuenta_activa',
            'language': {'code': 'es_PE'},
            'components': [{
                'type': 'body',
                'parameters': [{'type': 'text', 'parameter_name': 'nombre', 'text': primer_nombre}]
            }]
        }
    }
    try:
        r = requests.post(WA_API_URL, json=payload, headers=_headers(), timeout=10)
        r.raise_for_status()
        _save_outgoing(phone_digits, f'[template:qoricash_cuenta_activa] nombre={primer_nombre}')
        log.info(f'[WaBot] Template cuenta_activa enviado a {phone_digits}')
    except Exception as e:
        log.error(f'[WaBot] Error enviando cuenta_activa a {phone_digits}: {e}')
        return
    # P3 — Si el cliente tenía una cotización pendiente antes de registrarse, recordarla
    try:
        from app.models.wa_bot_session import WaBotSession as _WBS
        _bot_s = _WBS.query.filter_by(numero=phone_digits).first()
        if _bot_s and _bot_s.cotiz_op and _bot_s.cotiz_importe:
            _op_txt = 'comprar' if _bot_s.cotiz_op == 'compra' else 'vender'
            cta_body = (
                f'¡Tu cuenta está activa! Recuerda que querías {_op_txt} '
                f'*USD {_bot_s.cotiz_importe:,.0f}*. ¿Cotizamos ahora?'
            )
        else:
            cta_body = '¿Qué deseas hacer?'
    except Exception:
        cta_body = '¿Qué deseas hacer?'

    # Enviar botones de acción (requiere ventana 24h — falla silenciosamente si no aplica)
    try:
        send_buttons(phone_digits, cta_body, [
            {'id': 'btn_cotizar', 'title': '💱 Cotizar'},
            {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
        ])
    except Exception:
        pass


def send_template(numero, template_name, lang_code, params, header_image_url=None):
    """
    Envía una plantilla aprobada por Meta.
    params: lista de strings con los valores de cada variable {{1}}, {{2}}...
    header_image_url: URL pública de imagen si el template tiene header tipo IMAGE.
    Funciona aunque el cliente nunca haya escrito al bot (sin ventana de 24h).
    """
    components = []
    if header_image_url:
        components.append({
            'type': 'header',
            'parameters': [{'type': 'image', 'image': {'link': header_image_url}}]
        })
    components.append({
        'type': 'body',
        'parameters': [{'type': 'text', 'text': str(p)} for p in params]
    })
    payload = {
        'messaging_product': 'whatsapp',
        'to': numero.lstrip('+'),
        'type': 'template',
        'template': {
            'name': template_name,
            'language': {'code': lang_code},
            'components': components,
        }
    }
    try:
        r = requests.post(WA_API_URL, json=payload, headers=_headers(), timeout=10)
        if not r.ok:
            log.error(f'[WaBot] Error send_template {template_name} a {numero}: HTTP {r.status_code} | {r.text[:300]}')
            return
        r.raise_for_status()
        _save_outgoing(numero, f'[template:{template_name}] ' + ' | '.join(str(p) for p in params))
        log.info(f'[WaBot] Template {template_name} enviado a {numero}')
    except Exception as e:
        log.error(f'[WaBot] Error send_template {template_name} a {numero}: {e}')


def wa_notify_operacion_completada(client, op_id, titular, email_txt):
    """
    Envía notificación de operación completada usando plantilla aprobada.
    Llega a cualquier número aunque no haya ventana de 24h activa.
    """
    if not client:
        log.warning(f'[WaBot-COMPLETE] {op_id}: client es None — no se envía WA')
        return
    phone_raw = (getattr(client, 'phone', None) or '').split(';')[0].strip()
    phone_digits = ''.join(c for c in phone_raw if c.isdigit())
    if not phone_digits:
        log.warning(f'[WaBot-COMPLETE] {op_id}: teléfono vacío (phone_raw={phone_raw!r}) — no se envía WA')
        return
    if not phone_digits.startswith('51'):
        phone_digits = '51' + phone_digits
    log.warning(f'[WaBot-COMPLETE] {op_id}: enviando template a {phone_digits} | titular={titular!r}')
    send_template(phone_digits, 'qoricash_operacion_completada', 'es', [op_id, titular, email_txt])
    log.warning(f'[WaBot-COMPLETE] {op_id}: send_template finalizado para {phone_digits}')


def wa_notify_operacion_cancelada(client, op_id, titular, reason):
    """
    Notifica al cliente que su operación fue cancelada.
    Usa send_text (válido dentro de la ventana de 24h).
    """
    if not client:
        return
    phone_raw = (getattr(client, 'phone', None) or '').split(';')[0].strip()
    phone_digits = ''.join(c for c in phone_raw if c.isdigit())
    if not phone_digits:
        return
    if not phone_digits.startswith('51'):
        phone_digits = '51' + phone_digits
    mensaje = (
        f'❌ Tu operación *{op_id}* a nombre de *{titular}* ha sido cancelada.\n\n'
        f'*Motivo:* {reason}\n\n'
        f'Si tienes alguna consulta escríbenos o llámanos al *+51 910 624 404*.'
    )
    send_text(phone_digits, mensaje)


def send_text(numero, texto):
    payload = {
        'messaging_product': 'whatsapp',
        'to': numero.lstrip('+'),
        'type': 'text',
        'text': {'body': texto},
    }
    try:
        r = requests.post(WA_API_URL, json=payload, headers=_headers(), timeout=10)
        r.raise_for_status()
        _save_outgoing(numero, texto)
        return True
    except Exception as e:
        log.error(f'[WaBot] Error send_text a {numero}: {e}')
        return False


def send_buttons(numero, body, buttons):
    """buttons = [{'id': 'btn_id', 'title': 'Texto'}]  (máx 3)"""
    payload = {
        'messaging_product': 'whatsapp',
        'to': numero.lstrip('+'),
        'type': 'interactive',
        'interactive': {
            'type': 'button',
            'body': {'text': body},
            'action': {
                'buttons': [
                    {'type': 'reply', 'reply': {'id': b['id'], 'title': b['title'][:20]}}
                    for b in buttons[:3]
                ]
            }
        }
    }
    try:
        r = requests.post(WA_API_URL, json=payload, headers=_headers(), timeout=10)
        r.raise_for_status()
        _save_outgoing(numero, body + ' [botones: ' + ', '.join(b['title'] for b in buttons) + ']')
        return True
    except Exception as e:
        log.error(f'[WaBot] Error send_buttons a {numero}: {e}')
        return False


def send_buttons_image(numero, image_url, body, buttons):
    """Mensaje interactivo con imagen en el header + hasta 3 botones.
    Si Meta rechaza la imagen, hace fallback a send_buttons normal."""
    payload = {
        'messaging_product': 'whatsapp',
        'to': numero.lstrip('+'),
        'type': 'interactive',
        'interactive': {
            'type': 'button',
            'header': {
                'type': 'image',
                'image': {'link': image_url},
            },
            'body': {'text': body},
            'action': {
                'buttons': [
                    {'type': 'reply', 'reply': {'id': b['id'], 'title': b['title'][:20]}}
                    for b in buttons[:3]
                ]
            }
        }
    }
    try:
        r = requests.post(WA_API_URL, json=payload, headers=_headers(), timeout=10)
        if not r.ok:
            log.warning(f'[WaBot] send_buttons_image falló ({r.status_code}), fallback a send_buttons')
            return send_buttons(numero, body, buttons)
        _save_outgoing(numero, '[imagen] ' + body + ' [botones: ' + ', '.join(b['title'] for b in buttons) + ']')
        return True
    except Exception as e:
        log.error(f'[WaBot] Error send_buttons_image a {numero}: {e}')
        return send_buttons(numero, body, buttons)

def send_list(numero, body, sections, button='Continuar'):
    payload = {
        'messaging_product': 'whatsapp',
        'to': numero.lstrip('+'),
        'type': 'interactive',
        'interactive': {
            'type': 'list',
            'body': {'text': body},
            'action': {
                'button': button,
                'sections': sections,
            }
        }
    }
    try:
        r = requests.post(WA_API_URL, json=payload, headers=_headers(), timeout=10)
        r.raise_for_status()
        _save_outgoing(numero, body)
    except Exception as e:
        log.error(f'[WaBot] Error send_list a {numero}: {e}')


# ── Helpers de TC ──────────────────────────────────────────────────

def _get_tc():
    """Lee el TC desde DatatecRate — la misma fuente que el gadget de precios."""
    try:
        from app.models.datatec_rate import DatatecRate
        row = DatatecRate.get()
        return float(row.compra), float(row.venta)
    except Exception:
        return 0, 0


def _flujo_tc_publico(numero):
    """
    Muestra el tipo de cambio público vigente con botones de dirección.
    No solicita identificación. Devuelve True si el TC estaba disponible.
    Usado en saludos, consultas de TC y rutas P3 donde el cliente aún no
    está identificado pero no hay razón para bloquearle la consulta.
    """
    compra, venta = _get_tc()
    if not compra or not venta:
        send_buttons(numero,
            '⚠️ El tipo de cambio no está disponible en este momento.\n\n'
            'Intenta en unos minutos o habla con un asesor.',
            [
                {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
                {'id': 'btn_cotizar', 'title': '🔄 Reintentar'},
            ]
        )
        return False
    send_buttons(numero,
        f'💵 *Tipo de cambio vigente*\n\n'
        f'› Compramos tus dólares: *S/ {compra:.4f}*\n'
        f'› Te vendemos dólares:   *S/ {venta:.4f}*\n\n'
        '¿Qué quieres hacer?',
        [
            {'id': 'btn_comprar', 'title': 'Soles a dólares'},
            {'id': 'btn_vender',  'title': 'Dólares a soles'},
            {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
        ]
    )
    return True


def _parse_monto(texto):
    """
    Extrae un número de texto libre con soporte para formatos peruanos/internacionales.
    Ejemplos:
      '5000'     → 5000.0
      '5,000'    → 5000.0   (coma como separador de miles)
      '5.000'    → 5000.0   (punto como separador de miles — formato peruano)
      '5,000.50' → 5000.5
      '5.000,50' → 5000.5   (formato europeo/peruano con decimal)
      '5 mil'    → 5000.0
      '$5000'    → 5000.0
      '1.5'      → 1.5      (punto decimal)
      '1,5'      → 1.5      (coma decimal)
    """
    t = texto.lower().strip()
    # "5 mil" o "5mil"
    m = re.match(r'^(\d+(?:[.,]\d+)?)\s*mil$', t)
    if m:
        return float(m.group(1).replace(',', '.')) * 1000

    # Quitar símbolos de moneda y espacios, conservar dígitos, puntos y comas
    limpio = re.sub(r'[^\d.,]', '', t)
    if not limpio:
        return None

    # Caso 1: solo dígitos
    if re.match(r'^\d+$', limpio):
        return float(limpio)

    # Caso 2: separador de miles puro — X.000 / X,000 / X.000.000 / X,000,000
    if re.match(r'^\d{1,3}([.,]\d{3})+$', limpio):
        return float(re.sub(r'[.,]', '', limpio))

    # Caso 3: miles + decimal — X.000,50 / X,000.50 / X.000.000,50
    m2 = re.match(r'^(\d{1,3}(?:[.,]\d{3})+)[.,](\d{1,2})$', limpio)
    if m2:
        entero = re.sub(r'[.,]', '', m2.group(1))
        return float(f'{entero}.{m2.group(2)}')

    # Caso 4: un solo separador
    if '.' in limpio and ',' not in limpio:
        partes = limpio.split('.')
        if len(partes) == 2:
            # X.YYY con exactamente 3 decimales → separador de miles
            if len(partes[1]) == 3 and partes[1].isdigit() and len(partes[0]) <= 3:
                return float(partes[0] + partes[1])
            # Resto → punto decimal normal
            return float(limpio)
    if ',' in limpio and '.' not in limpio:
        partes = limpio.split(',')
        if len(partes) == 2:
            # X,YYY con exactamente 3 decimales → separador de miles
            if len(partes[1]) == 3 and partes[1].isdigit() and len(partes[0]) <= 3:
                return float(partes[0] + partes[1])
            # Resto → coma decimal
            return float(limpio.replace(',', '.'))

    # Fallback: eliminar todo excepto dígitos y último separador
    limpio2 = limpio.replace(',', '.')
    partes2 = limpio2.split('.')
    if len(partes2) > 2:
        limpio2 = ''.join(partes2[:-1]) + '.' + partes2[-1]
    try:
        return float(limpio2)
    except ValueError:
        return None


# ── Detección de intenciones en texto libre ────────────────────────

def _detectar_intencion(texto):
    """
    Clasifica la intención del usuario cuando no escribe un monto válido.
    Usa Claude Haiku para interpretar lenguaje natural en cualquier forma.
    Retorna: 'cancelar' | 'no_tengo' | 'asesor' | None (reintento de monto)
    Fallback por keywords si la IA no está disponible.
    """
    client = _get_anthropic_client()
    if client:
        try:
            prompt = (
                'Clasifica la intención del siguiente mensaje de un usuario en un chat de '
                'casa de cambio de divisas (soles/dólares). El bot le había pedido que '
                'ingrese el monto en dólares que quiere cambiar.\n\n'
                f'Mensaje del usuario: "{texto}"\n\n'
                'Responde SOLO con una de estas palabras (sin explicación, sin puntuación):\n'
                '- cancelar   → quiere salir, cancelar, no seguir, desistir, volver al inicio\n'
                '- no_tengo   → dice que no tiene la divisa, no tiene dinero, no le alcanza, etc.\n'
                '- asesor     → quiere hablar con una persona, pide ayuda humana\n'
                '- reintento  → intentó escribir un monto pero lo escribió mal '
                '(letras, confusión de formato, idioma distinto, etc.)\n'
                '- otro       → pregunta algo diferente (tipo de cambio, horario, cómo funciona, '
                'consulta sobre el servicio, cualquier cosa que no sea un monto ni las anteriores)\n'
            )
            resp = client.messages.create(
                model='claude-haiku-4-5-20251001',
                max_tokens=10,
                messages=[{'role': 'user', 'content': prompt}],
            )
            clasificacion = resp.content[0].text.strip().lower().split()[0]
            if clasificacion in ('cancelar', 'no_tengo', 'asesor', 'reintento', 'otro'):
                log.info(f'[WaBot-IA] intencion clasificada="{clasificacion}" para texto="{texto[:40]}"')
                return None if clasificacion == 'reintento' else clasificacion
        except Exception as e:
            log.warning(f'[WaBot-IA] Error clasificando intención: {e}')

    # Fallback por keywords si la IA no responde
    t = texto.lower().strip()
    for frase in ('no tengo', 'no cuento', 'no tengo dólares', 'no tengo dolares',
                  'no tengo soles', 'no tengo plata', 'no tengo dinero'):
        if frase in t:
            return 'no_tengo'
    for frase in ('cancel', 'cancelar', 'cancela', 'salir', 'volver', 'inicio',
                  'no quiero', 'no me interesa', 'olvida', 'chau', 'adios', 'adiós'):
        if frase in t:
            return 'cancelar'
    for frase in ('asesor', 'agente', 'persona', 'humano', 'ayuda', 'hablar con'):
        if frase in t:
            return 'asesor'
    return None


# ── Etapa 2: Interpretación estructurada de solicitudes ───────────

def _interpretar_solicitud(texto, session=None):
    """
    Interprets free text to extract trade intent (deterministic first, IA fallback).

    Returns:
      tipo:           'compra' | 'venta' | None
      importe:        float | None   (USD when set)
      moneda_importe: 'USD' | 'PEN' | None
      es_hipotetico:  bool
      es_correccion:  bool
      faltante:       list[str]
      fuente:         'determinista' | 'ia' | 'fallo'

    Security: only extracts routing signals. Callers validate before updating session.
    """
    t = texto.lower().strip()

    resultado = {
        'tipo': None,
        'importe': None,
        'moneda_importe': None,
        'es_hipotetico': False,
        'es_correccion': False,
        'faltante': [],
        'fuente': 'determinista',
    }

    # ── Hipotetico ──────────────────────────────────────────────────
    _hip_kw = ('cuanto recibiria', 'cuanto me darian', 'si cambio', 'si fuera',
               'y si son', 'y si fuera', 'si tuviera', 'cuanto seria', 'y si', 'si son',
               u'cuánto recibiría', u'cuánto me darían',
               u'cuánto sería')
    if any(k in t for k in _hip_kw):
        resultado['es_hipotetico'] = True

    # ── Correccion ─────────────────────────────────────────────────
    _cor_kw = ('mejor que sean', 'mejor son', 'mejor serian', 'en realidad',
               'cambia a', 'en cambio son', 'prefiero', 'en vez', 'en lugar',
               u'mejor serían')
    if any(k in t for k in _cor_kw):
        resultado['es_correccion'] = True
    # "mejor N" solo cuando hay digito inmediato (evita "mejor precio")
    if not resultado['es_correccion'] and re.search(r'\bmejor\s+\d', t):
        resultado['es_correccion'] = True

    # ── Direccion ──────────────────────────────────────────────────
    _compra_sig = (
        'comprar dolares', 'compro dolares', 'quiero dolares', 'necesito dolares',
        'tengo soles', 'soles a dolares', 'soles por dolares', 'de soles a',
        'envio soles', 'mando soles', 'cambiar soles', 'comprar usd',
        u'comprar dólares', u'compro dólares', u'quiero dólares',
        u'necesito dólares', u'envío soles',
    )
    _venta_sig = (
        'vender dolares', 'vendo dolares', 'quiero soles', 'necesito soles',
        'tengo dolares', 'dolares a soles', 'dolares por soles', 'de dolares a',
        'envio dolares', 'mando dolares', 'cambiar dolares', 'vender usd',
        u'vender dólares', u'vendo dólares', u'tengo dólares',
        u'dólares a soles', u'dólares por soles', u'de dólares a',
        u'envío dólares', u'mando dólares', u'cambiar dólares',
    )
    es_compra = any(k in t for k in _compra_sig)
    es_venta  = any(k in t for k in _venta_sig)
    # Regex: handles "verb + amount + currency" (e.g. "comprar 1500 dolares")
    if not es_compra and re.search(r'\b(comprar?|compro)\b.{0,30}\b(d[oó]lares?|usd)\b', t):
        es_compra = True
    # "quiero/necesito + dolares" only signals compra if no explicit venta verb is present
    # AND no explicit directional phrase "dolares a soles" exists (stronger signal).
    _venta_dir_explicit = any(k in t for k in (
        'dolares a soles', 'dolares por soles', 'de dolares a',
        'usd a soles', 'usd por soles',
        'dólares a soles', 'dólares por soles', 'de dólares a',
    ))
    if (not es_compra
            and re.search(r'\b(quiero|necesito)\b.{0,30}\b(d[oó]lares?|usd)\b', t)
            and not re.search(r'\b(vender?|vendo)\b', t)
            and not _venta_dir_explicit):
        es_compra = True
    if not es_venta and re.search(r'\b(vender?|vendo)\b.{0,30}\b(d[oó]lares?|usd)\b', t):
        es_venta = True
    # "quiero/necesito + soles" only signals venta if no explicit compra verb is present
    # AND no explicit directional phrase "soles a dolares" exists (stronger signal).
    _compra_dir_explicit = any(k in t for k in (
        'soles a dolares', 'soles por dolares', 'de soles a',
        'soles a usd', 'soles por usd',
        'soles a dólares', 'soles por dólares', 'de soles a dólares',
    ))
    if (not es_venta
            and re.search(r'\b(quiero|necesito)\b.{0,30}\bsoles?\b', t)
            and not re.search(r'\b(comprar?|compro)\b', t)
            and not _compra_dir_explicit):
        es_venta = True
    # Negation: "no quiero/deseo comprar/vender ..." cancels the detected direction
    if es_compra and re.search(r'\bno\s+(?:quiero|deseo)(?:\s+comprar?)?\b', t):
        es_compra = False
    if es_venta and re.search(r'\bno\s+(?:quiero|deseo)(?:\s+vender?)?\b', t):
        es_venta = False
    if es_compra and not es_venta:
        resultado['tipo'] = 'compra'
    elif es_venta and not es_compra:
        resultado['tipo'] = 'venta'

    # ── Importe y moneda ───────────────────────────────────────────
    monto = _parse_monto(texto)
    if monto and monto > 0:
        resultado['importe'] = monto
        _pen_kw = ('soles', ' sol ', 's/ ', 's/.')
        _usd_kw = ('dolares', 'dolar', 'usd', '$ ',
                   u'dólares', u'dólar')
        if any(k in t for k in _pen_kw) and not any(k in t for k in _usd_kw):
            resultado['moneda_importe'] = 'PEN'
        else:
            resultado['moneda_importe'] = 'USD'

    # ── Si el determinista aporto algo, devolver sin IA ─────────────
    if resultado['tipo'] is not None or resultado['importe'] is not None:
        resultado['faltante'] = [f for f in ('tipo', 'importe') if not resultado[f]]
        return resultado

    # ── Sin digito no hay importe — no llamar IA ────────────────────
    if not re.search(r'\d', texto):
        resultado['faltante'] = ['tipo', 'importe']
        return resultado

    # ── Fallback IA ────────────────────────────────────────────────
    resultado['fuente'] = 'ia'
    try:
        ia_client = _get_anthropic_client()
        if not ia_client:
            resultado['fuente'] = 'fallo'
            return resultado
        prompt = (
            'Analiza el mensaje de un cliente de casa de cambio de divisas '
            '(soles/dolares peruanos). Responde SOLO con este formato:\n'
            'tipo=compra|venta|ninguno\n'
            'importe=NUMERO|ninguno\n'
            'moneda=USD|PEN|ninguno\n'
            'correccion=si|no\n'
            'hipotetico=si|no\n\n'
            'compra = cliente envia soles, recibe dolares\n'
            'venta  = cliente envia dolares, recibe soles\n'
            'correccion = corrige un dato previo (mejor, en realidad, etc.)\n'
            'hipotetico = consulta hipotetica (y si fueran, cuanto recibiria, etc.)\n\n'
            f'Mensaje: "{texto}"'
        )
        resp = ia_client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=60,
            messages=[{'role': 'user', 'content': prompt}],
        )
        for line in resp.content[0].text.strip().split('\n'):
            if '=' not in line:
                continue
            k, v = line.split('=', 1)
            k, v = k.strip(), v.strip().lower()
            if k == 'tipo' and v in ('compra', 'venta'):
                resultado['tipo'] = v
            elif k == 'importe' and v != 'ninguno':
                parsed = _parse_monto(v)
                if parsed and parsed > 0:
                    resultado['importe'] = parsed
            elif k == 'moneda' and v in ('usd', 'pen'):
                resultado['moneda_importe'] = v.upper()
            elif k == 'correccion' and v == 'si':
                resultado['es_correccion'] = True
            elif k == 'hipotetico' and v == 'si':
                resultado['es_hipotetico'] = True
    except Exception as _e:
        log.warning(f'[WaBot-IA] Error en _interpretar_solicitud: {_e}')
        resultado['fuente'] = 'fallo'

    resultado['faltante'] = [f for f in ('tipo', 'importe') if not resultado[f]]
    return resultado


def _no_tengo_handler(texto, numero, session):
    """
    Handles 'no tengo' messages with nuanced currency parsing.

    Four cases:
    1. Bank/account reference -> explain options, keep session
    2. Explicit currency = what client would send in current flow -> offer inverse, reset
    3. Explicit currency = what client would receive -> clarify, keep session
    4. Generic / no currency -> deduce from cotiz_op if set; ask if not; keep session on ambiguous
    """
    t = texto.lower()
    cotiz_op = session.cotiz_op or ''

    # Case 1: account / bank reference
    _cuenta_kw = ('cuenta', 'bcp', 'bbva', 'interbank', 'scotiabank', 'pichincha',
                  'banco', 'tarjeta', 'billetera', 'yape', 'plin')
    if any(k in t for k in _cuenta_kw):
        send_buttons(numero,
            'No hay problema \U0001f60a Para recibir tu cambio puedes indicarnos cualquier '
            'cuenta bancaria peruana. \u00bfContinuamos con la cotizaci\u00f3n?',
            [
                {'id': 'btn_cotizar', 'title': '\U0001f4b1 Continuar cotizaci\u00f3n'},
                {'id': 'btn_asesor',  'title': '\U0001f4ac Hablar con asesor'},
            ]
        )
        return  # session preserved

    _soles_kw = ('soles', ' sol ', 'pen')
    _usd_kw   = ('dolares', 'dolar', 'usd', u'd\u00f3lares', u'd\u00f3lar')
    menciona_soles = any(k in t for k in _soles_kw)
    menciona_usd   = any(k in t for k in _usd_kw)

    if menciona_soles and not menciona_usd:
        if cotiz_op == 'compra':
            # compra: sends soles -> lacking soles -> offer inverse
            _reset_sesion(session)
            send_buttons(numero,
                u'\U0001f4b1 Entendido. Si tienes *d\u00f3lares* y quieres *soles*, '
                u'puedo ayudarte con el cambio al rev\u00e9s.',
                [
                    {'id': 'btn_vender',  'title': u'2\u2192 D\u00f3lares a Soles'},
                    {'id': 'btn_asesor',  'title': u'\U0001f4ac Hablar con asesor'},
                ]
            )
        else:
            # venta or no direction: soles is received; lacking soles != can't operate
            send_buttons(numero,
                u'\u00bfQu\u00e9 necesitas exactamente? '
                u'Si quieres *obtener soles*, cu\u00e9ntame m\u00e1s para ayudarte mejor.',
                [
                    {'id': 'btn_cotizar', 'title': u'\U0001f4b1 Ver tipo de cambio'},
                    {'id': 'btn_asesor',  'title': u'\U0001f4ac Hablar con asesor'},
                ]
            )
            # session preserved

    elif menciona_usd and not menciona_soles:
        if cotiz_op == 'venta':
            # venta: sends dollars -> lacking dollars -> offer inverse
            _reset_sesion(session)
            send_buttons(numero,
                u'\U0001f4b1 Entendido. Si tienes *soles* y quieres *d\u00f3lares*, '
                u'puedo ayudarte con el cambio al rev\u00e9s.',
                [
                    {'id': 'btn_comprar', 'title': u'1\u2192 Soles a D\u00f3lares'},
                    {'id': 'btn_asesor',  'title': u'\U0001f4ac Hablar con asesor'},
                ]
            )
        else:
            # compra or no direction: dollars is received; lacking dollars != can't buy
            send_buttons(numero,
                u'Para *obtener d\u00f3lares* solo necesitas soles para enviar; '
                u'no es necesario tener d\u00f3lares de antemano. '
                u'\u00bfContinuamos con tu cotizaci\u00f3n?',
                [
                    {'id': 'btn_cotizar', 'title': u'\U0001f4b1 Continuar cotizaci\u00f3n'},
                    {'id': 'btn_asesor',  'title': u'\U0001f4ac Hablar con asesor'},
                ]
            )
            # session preserved

    else:
        # Generic / ambiguous — deduce from cotiz_op if set
        if cotiz_op:
            divisa_falta = 'soles' if cotiz_op == 'compra' else u'd\u00f3lares'
            divisa_tiene = u'd\u00f3lares' if divisa_falta == 'soles' else 'soles'
            _reset_sesion(session)
            send_buttons(numero,
                f'Sin problema. Si tienes *{divisa_tiene}* y quieres *{divisa_falta}*, '
                u'podemos hacer el cambio al rev\u00e9s. \U0001f4b1\n\n\u00bfQu\u00e9 quieres hacer?',
                [
                    {'id': 'btn_cotizar', 'title': u'\U0001f4b1 Ver tipo de cambio'},
                    {'id': 'btn_asesor',  'title': u'\U0001f4ac Hablar con asesor'},
                ]
            )
        else:
            # No direction: ask without resetting
            send_buttons(numero,
                u'\U0001f60a \u00bfQu\u00e9 moneda te falta? \u00bfSoles o d\u00f3lares?\n\n'
                u'O si prefieres, un asesor puede orientarte.',
                [
                    {'id': 'btn_asesor', 'title': u'\U0001f4ac Hablar con asesor'},
                ]
            )
            # session preserved


def _continuar_segun_sesion(numero, session):
    """Routes to next step based on what is already set in session."""
    if session.cotiz_op and (session.cotiz_importe or 0) >= MONTO_MINIMO_USD:
        _flujo_mostrar_cotizacion(numero, session)
        session.estado = 'viendo_cotizacion'
    elif session.cotiz_op:
        _flujo_pedir_importe(numero, session.cotiz_op)
        session.estado = 'esperando_importe'
    else:
        _flujo_cotizar_inicio(numero)
        session.estado = 'eligiendo_operacion'


def _identificar_y_cotizar_directo(numero, session):
    """
    Identifies the client (P1/P2/P3) and routes to the appropriate step
    based on what is already in session.cotiz_op / session.cotiz_importe.
    Unlike _intentar_identificar_y_cotizar, does not unconditionally show
    the direction-selection screen.
    """
    # P1 — doc conocido en sesion
    _client_ses = _buscar_cliente(session.cotiz_doc) if session.cotiz_doc else None
    if _client_ses and _client_ses.status == 'Activo':
        primer_nombre = (_client_ses.nombres or _client_ses.razon_social or '').split()[0].title()
        if not (session.cotiz_op and (session.cotiz_importe or 0) >= MONTO_MINIMO_USD):
            # Only greet when not about to show the quote immediately
            send_text(numero,
                f'\U0001f44b \u00a1Hola de nuevo, {primer_nombre}!\n\n'
                '_Si deseas operar con otro documento, cierra la sesi\u00f3n primero._'
            )
        _continuar_segun_sesion(numero, session)
        return

    # P2 — phone lookup
    _clientes_tel = _buscar_clientes_por_telefono(numero)
    if len(_clientes_tel) == 1 and _clientes_tel[0].status == 'Activo':
        _c = _clientes_tel[0]
        session.cotiz_doc = _c.dni
        primer_nombre = (_c.nombres or _c.razon_social or '').split()[0].title()
        send_text(numero, f'\U0001f44b \u00a1Hola de nuevo, {primer_nombre}!')
        _continuar_segun_sesion(numero, session)
        return

    # P3 — cliente desconocido.
    # Si ya tenemos op+importe, mostramos la cotización primero y pedimos identidad
    # solo al aceptar (mismo comportamiento que el flujo paso a paso / T4).
    if session.cotiz_op and (session.cotiz_importe or 0) >= MONTO_MINIMO_USD:
        _flujo_mostrar_cotizacion(numero, session)
        session.estado = 'viendo_cotizacion'
    else:
        # Cliente desconocido con dirección+importe → mostrar cotización ahora.
        # La identificación se solicitará únicamente si acepta el precio.
        _flujo_mostrar_cotizacion(numero, session)
        session.estado = 'viendo_cotizacion'


def _aplicar_interpretacion_pre_op(numero, session, interp):
    """
    Applies interpretation result to session before an operation is created.
    Validates all values; handles PEN limitation; falls back to guided flow on failure.

    Pre-condition: caller has verified no active operation exists.
    Security: only updates cotiz_op and cotiz_importe (pre-quotation fields).
    """
    if interp.get('fuente') == 'fallo':
        _intentar_identificar_y_cotizar(numero, session)
        return

    tipo    = interp.get('tipo')
    importe = interp.get('importe')
    moneda  = interp.get('moneda_importe') or 'USD'

    # PEN limitation: engine works with USD amounts only
    if moneda == 'PEN' and importe:
        verbo = 'comprar' if tipo == 'compra' else ('vender' if tipo == 'venta' else 'cambiar')
        send_text(numero,
            f'Nuestro motor cotiza en *d\u00f3lares (USD)*; no podemos calcular exactamente '
            f'cu\u00e1ntos d\u00f3lares recibir\u00edas desde soles sin conocer el TC en ese instante.\n\n'
            f'\u00bfCu\u00e1ntos d\u00f3lares quieres {verbo}? Ejemplo: *500* o *1000*'
        )
        if tipo:
            session.cotiz_op = tipo
        session.estado = 'esperando_importe' if session.cotiz_op else 'eligiendo_operacion'
        return

    # Apply direction if unambiguous
    if tipo:
        session.cotiz_op = tipo

    # Apply amount (USD, validated)
    if importe and importe > 0 and moneda == 'USD':
        if importe < MONTO_MINIMO_USD:
            verbo2 = ('comprar' if session.cotiz_op == 'compra'
                      else 'vender' if session.cotiz_op == 'venta' else 'cambiar')
            send_text(numero,
                f'El monto m\u00ednimo de operaci\u00f3n es *USD {MONTO_MINIMO_USD:,.0f}*.\n\n'
                f'\u00bfCu\u00e1ntos d\u00f3lares deseas {verbo2}?'
            )
            session.estado = 'esperando_importe' if session.cotiz_op else 'eligiendo_operacion'
            return
        session.cotiz_importe = importe

    # Route based on what is now known
    if session.cotiz_op and (session.cotiz_importe or 0) >= MONTO_MINIMO_USD:
        # Both direction and amount known → identify client then show quote
        _identificar_y_cotizar_directo(numero, session)
    elif session.cotiz_op:
        # Direction known but amount missing → ask for amount first
        _flujo_pedir_importe(numero, session.cotiz_op)
        session.estado = 'esperando_importe'
    else:
        _intentar_identificar_y_cotizar(numero, session)


# ── Flujos del bot ─────────────────────────────────────────────────

def _bienvenida(numero, session):
    """
    Saludo de bienvenida:
    - 1 persona natural (DNI/CE) vinculada al número → saludo por nombre.
    - Cualquier otro caso (0, 1 empresa/RUC, 2+) → saludo genérico Qoricash.
    Siempre muestra TC actual + 3 botones de operación. No pre-popula cotiz_doc.
    """
    BANNER_URL = 'https://qoricash.pe/213.jpg'
    clientes = _buscar_clientes_por_telefono(numero)

    saludo = '¡Hola! 👋 Bienvenido a Qoricash.'
    if len(clientes) == 1:
        c = clientes[0]
        if (c.document_type or '').upper() in ('DNI', 'CE'):
            nombre_db = (c.nombres or '').strip()
            primer_nombre = nombre_db.split()[0].title() if nombre_db else ''
            if primer_nombre:
                saludo = f'¡Hola, {primer_nombre}! 👋'

    _c, _v = _get_tc()
    if _c and _v:
        tc_text = (
            f'\n💵 Compramos tus dólares: *S/ {_c:.4f}*\n'
            f'💵 Te vendemos dólares:   *S/ {_v:.4f}*\n\n'
            '¿Qué monto quieres cambiar y a qué moneda?'
        )
    else:
        tc_text = '\nCambia dólares sin salir de tu WhatsApp, sin comisiones.'

    msg = f'{saludo} Cambia tus dólares con un excelente tipo de cambio, sin salir de WhatsApp. 💵{tc_text}'
    send_buttons_image(numero, BANNER_URL, msg, [
        {'id': 'btn_comprar',       'title': 'Soles a dólares'},
        {'id': 'btn_vender',        'title': 'Dólares a soles'},
        {'id': 'btn_como_funciona', 'title': '› ¿Cómo funciona?'},
    ])


def _flujo_cotizar_inicio(numero):
    """Pregunta si el cliente desea comprar o vender dólares."""
    send_buttons(numero,
        'Cotiza el tipo de operacion\n\n'
        '• *Tengo soles* y quiero dólares — primera opción\n'
        '• *Tengo dólares* y quiero soles — segunda opción',
        [
            {'id': 'btn_comprar', 'title': 'Soles a dólares'},
            {'id': 'btn_vender',  'title': 'Dólares a soles'},
        ]
    )


def _flujo_pedir_importe(numero, operacion):
    """Solicita el importe en USD."""
    if operacion == 'compra':
        pregunta = f'¿Cuántos dólares quieres recibir? Mínimo: USD {MONTO_MINIMO_USD:,.0f}.'
    else:
        pregunta = f'¿Cuántos dólares quieres cambiar a soles? Mínimo: USD {MONTO_MINIMO_USD:,.0f}.'
    send_buttons(numero, pregunta, [{'id': 'btn_volver_cotizar', 'title': '🔙 Volver atrás'}])


def _flujo_mostrar_cotizacion(numero, session):
    """Muestra el TC final (con mejora si aplica) y botones de aceptar/volver."""
    from datetime import timedelta
    from app.utils.formatters import now_peru

    compra, venta = _get_tc()

    # P16 — Validar que el TC esté disponible
    if not compra or not venta:
        send_buttons(numero,
            '⚠️ El tipo de cambio no está disponible en este momento.\n\n'
            'Por favor intenta en unos minutos o habla con un asesor.',
            [
                {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
                {'id': 'btn_cotizar', 'title': '🔄 Reintentar'},
            ]
        )
        session.estado = 'inicio'
        return

    op      = session.cotiz_op
    importe = session.cotiz_importe
    mejora  = _mejora_tc(importe)

    # Hora de expiración de la cotización
    expira_hora = (now_peru() + timedelta(minutes=COTIZ_VALIDEZ_MIN)).strftime('%I:%M %p').lstrip('0')

    if op == 'compra':
        # Cliente compra dólares → empresa le vende → usa TC venta + spread
        tc_base  = round(venta + SPREAD_TC, 4)
        tc_final = round(tc_base - mejora, 4)
        soles    = round(importe * tc_final, 2)
        resumen  = (
            f'💱 *Tu cotización*\n\n'
            f'› Tú envías:    *S/ {soles:,.2f}*\n'
            f'› Tú recibes:  *USD {importe:,.2f}*\n\n'
            f'Tipo de cambio: S/ {tc_final:.4f}'
        )
    else:
        # Cliente vende dólares → empresa le compra → usa TC compra - spread
        tc_base  = round(compra - SPREAD_TC, 4)
        tc_final = round(tc_base + mejora, 4)
        soles    = round(importe * tc_final, 2)
        resumen  = (
            f'💱 *Tu cotización*\n\n'
            f'› Tú envías:    *USD {importe:,.2f}*\n'
            f'› Tú recibes:  *S/ {soles:,.2f}*\n\n'
            f'Tipo de cambio: S/ {tc_final:.4f}'
        )

    # Guardia: tc_final debe ser finito y positivo antes de asignar o mostrar.
    import math as _math_mq
    if not (_math_mq.isfinite(tc_final) and tc_final > 0):
        log.warning(f'[WaBot] TC inválido ({tc_final}) al cotizar para {numero}')
        try:
            session.cotiz_token = None  # ningún token aceptable para esta cotización
        except Exception:
            pass
        send_buttons(numero,
            '⚠️ El tipo de cambio no está disponible en este momento.\n\n'
            'Inténtalo en unos minutos o habla con un asesor.',
            [
                {'id': 'btn_cotizar', 'title': '🔄 Cotizar de nuevo'},
                {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
            ]
        )
        session.estado = 'inicio'
        return

    if mejora > 0:
        resumen += f'\n> ✨ TC preferencial por monto especial'

    resumen += f'\n> ⏱ Válido hasta las {expira_hora}'

    session.cotiz_tc = tc_final
    try:
        session.cotiz_timestamp = now_peru()
    except Exception:
        pass

    # Assign a fresh UUID token that uniquely identifies this quote version.
    # Acceptance is valid only when button token == session.cotiz_token (exact equality).
    _token = str(uuid.uuid4())
    try:
        session.cotiz_token = _token
    except Exception:
        pass

    send_list(numero, resumen, [{
        'title': 'Opciones',
        'rows': [
            {'id': f'btn_aceptar_cotiz_{_token}', 'title': 'Aceptar cotización'},
            {'id': 'btn_cambiar_monto',            'title': 'Cambiar monto'},
            {'id': 'btn_cambiar_operacion',        'title': 'Cambiar tipo de operación'},
            {'id': 'btn_cancelar_cotiz',           'title': 'Cancelar cotización'},
            {'id': 'btn_asesor',                   'title': 'Hablar con asesor'},
        ]
    }])


def _menu_rapido(numero):
    """Menú de opciones sin el saludo de bienvenida (para clientes que ya fueron bienvenidos)."""
    send_buttons(numero,
        '¿En qué te podemos ayudar? 👇',
        [
            {'id': 'btn_cotizar',       'title': '💱 Cotizar'},
            {'id': 'btn_como_funciona', 'title': 'ℹ️ ¿Cómo funciona?'},
            {'id': 'btn_asesor',        'title': '💬 Hablar con asesor'},
        ]
    )


def _flujo_como_funciona(numero):
    """Explica el proceso de cambio y destaca seguridad / regulación SBS."""
    BANNER_URL = 'https://qoricash.pe/334.jpg'
    msg = (
        '1️⃣ *Cotiza* — Dinos cuánto quieres cambiar y te damos el precio al instante. Sin compromisos.\n\n'
        '2️⃣ *Transfiere* — Envías el dinero a la cuenta bancaria de Qoricash de tu elección y nos mandas el código de operación.\n\n'
        '3️⃣ *¡Listo!* — En minutos transferimos a tu cuenta y te avisamos aquí por WhatsApp.\n\n'
        '🔒 Inscritos en SBS\n'
        '🕐 Lun–Vie 9am–6pm · Sáb 9am–2pm'
    )
    send_buttons_image(numero, BANNER_URL, msg, [
        {'id': 'btn_cotizar', 'title': '💱 Ver tipo de cambio'},
        {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
    ])


def _flujo_horario(numero):
    """Responde directamente con el horario de atención."""
    send_buttons(numero,
        '🕐 *Horario de atención Qoricash*\n\n'
        '• Lunes a Viernes: *9:00 AM – 6:00 PM*\n'
        '• Sábados: *9:00 AM – 2:00 PM*\n'
        '• Domingos: cerrado\n\n'
        'Puedes cotizar el tipo de cambio en cualquier momento 😊',
        [
            {'id': 'btn_cotizar', 'title': '💱 Cotizar ahora'},
            {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
        ]
    )


def _flujo_cotiz_expirada(numero):
    """Avisa que la cotización venció y ofrece volver a cotizar."""
    send_buttons(numero,
        f'⏱ Tu cotización ha vencido (validez: {COTIZ_VALIDEZ_MIN} min).\n\n'
        '¿Deseas obtener un nuevo precio?',
        [
            {'id': 'btn_cotizar', 'title': '💱 Nueva cotización'},
            {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
        ]
    )


def _cotiz_expirada(session):
    """Retorna True si la cotización lleva más de COTIZ_VALIDEZ_MIN sin ser aceptada."""
    from datetime import timedelta
    from app.utils.formatters import now_peru
    if not session.updated_at:
        return False
    return (now_peru() - session.updated_at) > timedelta(minutes=COTIZ_VALIDEZ_MIN)


def _flujo_sesion_expirada(numero):
    """Avisa al cliente que la sesión expiró por inactividad."""
    send_text(numero,
        '⏰ Tu sesión ha expirado por inactividad.\n\n'
        'Cuando desees volver a operar, escríbenos y comenzamos de nuevo.'
    )


def _reset_sesion(session):
    """Limpia todos los datos de la sesión y la devuelve a inicio."""
    from app.utils.formatters import now_peru as _now_reset
    session.estado         = 'inicio'
    session.cotiz_op       = ''
    session.cotiz_importe  = 0.0
    session.cotiz_tc       = 0.0
    session.cotiz_doc      = ''
    session.cotiz_email    = ''
    session.cotiz_op_id    = ''
    session.cotiz_cuenta   = ''
    session.tipo           = ''
    session.bot_pausado    = False   # siempre reactivar el bot al resetear sesión
    session.updated_at     = _now_reset()  # forzar UPDATE aunque no haya otros cambios
    try:
        session.cotiz_intentos = 0
    except Exception:
        pass
    try:
        session.cotiz_token = None   # invalidar token de cotización anterior
    except Exception:
        pass


def _sesion_inactiva(session):
    """Retorna True si la sesión lleva más de SESSION_INACTIVIDAD_MIN sin actividad."""
    from datetime import timedelta
    from app.utils.formatters import now_peru
    if not session.updated_at:
        return False
    return (now_peru() - session.updated_at) > timedelta(minutes=SESSION_INACTIVIDAD_MIN)


def _ultimo_saliente_fue_op_completada(numero):
    """
    Retorna True si el último mensaje saliente para este número fue
    la plantilla qoricash_operacion_completada.
    Permite detectar que el cliente responde a la notificación de operación completada.
    """
    ultimo = (WaMessage.query
              .filter_by(numero=numero, direccion='saliente')
              .order_by(WaMessage.id.desc())
              .first())
    return ultimo is not None and '[template:qoricash_operacion_completada]' in (ultimo.mensaje or '')


def _flujo_seleccionar_titular(numero, session):
    """
    Presenta los titulares activos vinculados al número de WA para que el cliente
    confirme quién realiza el cambio. Lógica por cantidad:
      0 activos → pedir documento directamente.
      1 activo  → 2 botones: [Titular] [Usar otro documento].
      2 activos → 3 botones: [Titular 1] [Titular 2] [Usar otro documento].
      3+ activos → lista desplegable ('Elegir titular') + fila 'Usar otro documento'.
    """
    clientes = _buscar_clientes_por_telefono(numero)
    activos = [c for c in clientes if (c.status or '').lower() == 'activo']

    if len(activos) == 0:
        send_buttons(numero,
            'Para continuar, ingresa tu *DNI* (8 dígitos) o *RUC* (11 dígitos).\n\n'
            'Si tienes Carné de Extranjería, elige CE 👇',
            [
                {'id': 'btn_tengo_ce',       'title': '🌍 Tengo CE'},
                {'id': 'btn_volver_cotizar',  'title': '🔙 Volver'},
            ]
        )
        session.estado = 'esperando_id_cotizar'

    elif len(activos) == 1:
        c = activos[0]
        label = (c.full_name or c.razon_social or c.dni or '').strip()[:20]
        send_buttons(numero,
            '¿A nombre de quién realizarás este cambio?',
            [
                {'id': f'btn_titular_{c.dni}', 'title': label or 'Mi cuenta'},
                {'id': 'btn_usar_otro_doc',    'title': '🔄 Usar otro documento'},
            ]
        )
        session.estado = 'eligiendo_titular'

    elif len(activos) == 2:
        c1, c2 = activos[0], activos[1]
        label1 = (c1.full_name or c1.razon_social or c1.dni or '').strip()[:20]
        label2 = (c2.full_name or c2.razon_social or c2.dni or '').strip()[:20]
        send_buttons(numero,
            '¿A nombre de quién realizarás este cambio?',
            [
                {'id': f'btn_titular_{c1.dni}', 'title': label1 or 'Cuenta 1'},
                {'id': f'btn_titular_{c2.dni}', 'title': label2 or 'Cuenta 2'},
                {'id': 'btn_usar_otro_doc',     'title': '🔄 Usar otro documento'},
            ]
        )
        session.estado = 'eligiendo_titular'

    else:
        # 3+ titulares: lista desplegable (máx 9 filas + "Usar otro doc")
        rows = []
        for c in activos[:9]:
            label = (c.full_name or c.razon_social or c.dni or '').strip()[:24]
            rows.append({'id': f'btn_titular_LIST_{c.dni}', 'title': label or c.dni})
        rows.append({'id': 'btn_usar_otro_doc', 'title': '🔄 Usar otro documento'})
        send_list(numero,
            '¿A nombre de quién realizarás este cambio?\n\nElige un titular de la lista:',
            [{'title': 'Titulares', 'rows': rows}],
            button='Elegir titular',
        )
        session.estado = 'eligiendo_titular'


def _flujo_cotiz_aceptada(numero, session):
    """
    Flujo post-aceptación: delega la selección de titular a _flujo_seleccionar_titular.
    """
    log.info(f'[WaBot] {numero} aceptó cotización: {session.cotiz_op} USD {session.cotiz_importe} a S/ {session.cotiz_tc}')
    _flujo_seleccionar_titular(numero, session)


def _flujo_pedir_doc_verificacion(numero):
    send_text(numero,
        '🔎 Ingresa tu *DNI/CE* (8-9 dígitos) o *RUC* (11 dígitos) para verificar tu cuenta:'
    )


def _flujo_pedir_identificacion(numero):
    """Solicita DNI/RUC/CE para identificar al cliente antes de operar."""
    send_text(numero,
        '🔎 Para continuar, ingresa tu número de documento:\n\n'
        '• *DNI* — 8 dígitos (persona natural)\n'
        '• *CE* — 9 dígitos (carné de extranjería)\n'
        '• *RUC* — 11 dígitos (empresa)\n\n'
        'Lo consultaremos en RENIEC/SUNAT para verificar tu identidad.'
    )


def _flujo_pedir_id_para_cotizar(numero):
    """Solicita DNI/RUC/CE para identificar al cliente antes de mostrar el TC."""
    send_buttons(numero,
        '🔎 Para mostrarte el tipo de cambio preferente necesitamos verificar tu identidad.\n\n'
        'Ingresa tu *DNI* (8 dígitos), *CE* (9 dígitos) o *RUC* (11 dígitos):',
        [{'id': 'btn_no_ahora', 'title': '❌ Cancelar'}]
    )


def _intentar_identificar_y_cotizar(numero, session):
    """
    Identifica al cliente con 3 niveles de prioridad y arranca el flujo de cotización.

    Prioridad 1 — session.cotiz_doc ya fijado (misma sesión activa):
        Reutiliza el documento sin preguntar.  Muestra nota de cómo cambiar.
    Prioridad 2 — Phone lookup P2 (1 cliente activo por número):
        Auto-identifica y fija cotiz_doc.
    Prioridad 3 — Ninguno:
        Pide DNI/RUC → estado esperando_id_cotizar.
    """
    # P1 — sesión activa con doc ya conocido
    _client_ses = _buscar_cliente(session.cotiz_doc) if session.cotiz_doc else None
    if _client_ses and _client_ses.status == 'Activo':
        primer_nombre = (_client_ses.nombres or _client_ses.razon_social or '').split()[0].title()
        send_text(numero,
            f'👋 ¡Hola de nuevo, {primer_nombre}!\n\n'
            f'_Continuamos con tu misma sesión. Si deseas operar con otro documento, '
            f'cierra la sesión primero._'
        )
        _flujo_cotizar_inicio(numero)
        session.estado = 'eligiendo_operacion'
        return

    # P2 — phone lookup
    _clientes_tel = _buscar_clientes_por_telefono(numero)
    if len(_clientes_tel) == 1 and _clientes_tel[0].status == 'Activo':
        _c = _clientes_tel[0]
        session.cotiz_doc = _c.dni
        primer_nombre = (_c.nombres or _c.razon_social or '').split()[0].title()
        send_text(numero, f'👋 ¡Hola de nuevo, {primer_nombre}!')
        _flujo_cotizar_inicio(numero)
        session.estado = 'eligiendo_operacion'
        return

    # P3 — cliente aún no identificado.
    # Mostrar TC público y dejar que elija dirección; la ID se pedirá solo al aceptar.
    _flujo_tc_publico(numero)
    session.estado = 'eligiendo_operacion'


def _auto_crear_cliente(doc, nombre, es_empresa, phone_numero, email=None):
    """
    Crea un cliente nuevo a partir de datos de RENIEC/SUNAT.
    Status=Activo, kyc_status=pendiente — puede operar dentro de los límites legales.
    email: correo real del cliente; si None usa placeholder temporal.
    """
    import random, string
    from app.models.client import Client
    from decimal import Decimal

    digits = re.sub(r'\D', '', phone_numero)
    local  = digits[-9:] if len(digits) >= 9 else digits

    placeholder_email = email if email else f'{doc}@bot.qoricash.pe'

    _doc_norm = doc.strip()
    _es_ce = (not es_empresa and len(_doc_norm) == 9)  # CE: 9 dígitos, no empresa

    client = Client()
    client.document_type = 'RUC' if es_empresa else ('CE' if _es_ce else 'DNI')
    client.dni    = _doc_norm
    client.email  = placeholder_email
    client.phone  = local
    client.status = 'Activo'
    client.kyc_status = 'pendiente'
    # Límites operativos sin documentos (normativa SBS)
    client.operations_without_docs_limit = 10
    client.max_amount_without_docs = Decimal('50000.00') if es_empresa else Decimal('10000.00')

    if es_empresa:
        client.razon_social = nombre
    elif _es_ce:
        # CE: sin API de consulta — guardar nombre declarado íntegro.
        # Apellidos quedan NULL (campos nullable); back office normaliza.
        client.nombres = nombre
    else:
        # DNI: RENIEC devuelve "AP_PAT AP_MAT NOMBRES..."
        parts = nombre.split()
        if len(parts) >= 3:
            client.apellido_paterno = parts[0]
            client.apellido_materno = parts[1]
            client.nombres          = ' '.join(parts[2:])
        elif len(parts) == 2:
            client.apellido_paterno = parts[0]
            client.nombres          = parts[1]
        else:
            client.nombres = nombre

    # Generar código de referido único
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if not Client.query.filter_by(referral_code=code).first():
            client.referral_code = code
            break

    db.session.add(client)
    db.session.commit()
    log.info(f'[WaBot] Cliente auto-creado: {doc} | {nombre} | tel={local}')
    return client


def _es_dni(t):
    """DNI peruano (8 dígitos) o Carnet de Extranjería (9 dígitos)."""
    return bool(re.match(r'^\d{8,9}$', t.strip()))


def _es_ruc(t):
    return bool(re.match(r'^\d{11}$', t.strip()))


_DOMINIOS_DESECHABLES = {
    'yopmail.com', 'mailinator.com', 'guerrillamail.com', 'guerrillamail.net',
    'guerrillamail.org', 'tempmail.com', 'temp-mail.org', 'throwam.com',
    'trashmail.com', 'trashmail.me', 'dispostable.com', 'sharklasers.com',
    'guerrillamailblock.com', 'grr.la', 'guerrillamail.info', 'spam4.me',
    'spamgourmet.com', 'maildrop.cc', 'fakeinbox.com', 'mailnull.com',
    'spamcowboy.com', 'discard.email', 'spamhereplease.com', 'crap.email',
    'getairmail.com', 'filzmail.com', 'throwam.com', 'mail.tm',
    'mohmal.com', 'tempr.email', 'nwldx.com', 'mailtemp.net',
    'boximail.com', '10minutemail.com', '20minutemail.com', 'tempinbox.com',
    'spamgourmet.net', 'notmailinator.com', 'dispostable.com', 'binkmail.com',
}

_TLDS_INVALIDOS = {'.con', '.cmo', '.ocm', '.coom', '.comm', '.cm', '.vom', '.ocm'}

def _es_email(t: str) -> bool:
    """
    Valida formato de email, TLDs mal escritos y dominios desechables/prueba.
    Retorna True solo si el email parece real y válido.
    """
    t = t.strip().lower()
    # Formato básico
    if not re.match(r'^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$', t):
        return False
    # Debe tener exactamente un @
    parts = t.split('@')
    if len(parts) != 2:
        return False
    local, domain = parts
    if not local or not domain or '.' not in domain:
        return False
    # TLDs mal escritos comunes
    for bad_tld in _TLDS_INVALIDOS:
        if t.endswith(bad_tld):
            return False
    # Dominios desechables
    if domain in _DOMINIOS_DESECHABLES:
        return False
    return True


def _buscar_cliente(doc):
    """Busca un cliente por DNI o RUC."""
    try:
        from app.models.client import Client
        doc = doc.strip()
        return Client.query.filter_by(dni=doc).first()
    except Exception as e:
        log.warning(f'[WaBot] Error buscando cliente {doc}: {e}')
        return None


def _operacion_activa_cliente(numero):
    """
    Retorna la operación más reciente en estado Pendiente o En proceso
    del cliente asociado al número de WhatsApp, o None si no tiene ninguna.
    """
    try:
        from app.models.client import Client
        from app.models.operation import Operation
        digits = re.sub(r'\D', '', numero)
        local = digits[-9:] if len(digits) >= 9 else digits
        if not local:
            return None
        client = Client.query.filter(Client.phone.ilike(f'%{local}%')).first()
        if not client:
            return None
        return Operation.query.filter(
            Operation.client_id == client.id,
            Operation.status.in_(['Pendiente', 'En proceso'])
        ).order_by(Operation.created_at.desc()).first()
    except Exception as e:
        log.warning(f'[WaBot] Error buscando operación activa {numero}: {e}')
        return None


def _flujo_op_ya_activa(numero, op):
    """Informa al cliente que ya tiene una operación activa y no puede cotizar."""
    estado_texto = 'pendiente de pago' if op.status == 'Pendiente' else 'siendo procesada'
    botones = [{'id': 'btn_asesor', 'title': '💬 Hablar con asesor'}]
    if op.status == 'Pendiente':
        botones.append({'id': f'btn_modificar_importe_{op.operation_id}',   'title': '✏️ Modificar importe'})
        botones.append({'id': f'btn_cancelar_operacion_{op.operation_id}', 'title': '❌ Cancelar operación'})
    send_buttons(numero,
        f'⏳ Tu operación *{op.operation_id}* está {estado_texto}.\n\n'
        f'Solo puedes tener una operación activa a la vez. '
        f'En cuanto se complete podrás iniciar una nueva.\n\n'
        f'¿Tienes alguna consulta?',
        botones
    )


def _buscar_clientes_por_telefono(numero):
    """
    Busca todos los clientes con KYC aprobado cuyo campo phone contenga
    los últimos 9 dígitos del número WA (número local peruano sin código de país).
    Puede retornar más de uno si el mismo teléfono tiene cuenta personal y empresa.
    """
    try:
        from app.models.client import Client
        digits = re.sub(r'\D', '', numero)
        local = digits[-9:] if len(digits) >= 9 else digits
        if not local:
            return []
        todos = Client.query.filter(Client.phone.ilike(f'%{local}%')).all()
        return [c for c in todos if (c.kyc_status or '').lower() in ('completo', 'aprobado')]
    except Exception as e:
        log.warning(f'[WaBot] Error buscando clientes por teléfono {numero}: {e}')
        return []


def _buscar_cliente_por_tel_cualquier_kyc(numero):
    """
    Busca el cliente registrado con ese teléfono, sin filtrar por kyc_status.
    Si hay múltiples clientes con el mismo teléfono (compartido entre titular personal
    y empresa, p.ej.), retorna None para evitar asignar el documento al titular incorrecto.
    """
    try:
        from app.models.client import Client
        digits = re.sub(r'\D', '', numero)
        local = digits[-9:] if len(digits) >= 9 else digits
        if not local:
            return None
        results = Client.query.filter(Client.phone.ilike(f'%{local}%')).all()
        if len(results) == 1:
            return results[0]
        # Cero o múltiples clientes: ambigüo — no auto-asignar documento
        return None
    except Exception as e:
        log.warning(f'[WaBot] Error buscando cliente (any KYC) por tel {numero}: {e}')
        return None


def _flujo_elegir_cliente_telefono(numero, clientes):
    """
    Cuando un número de WA tiene múltiples cuentas aprobadas (ej: personal + empresa),
    muestra botones para que el usuario elija con cuál operar.
    Incluye siempre "Usar otro documento" para que pueda operar en nombre de terceros.
    """
    botones = []
    for c in clientes[:2]:
        nombre = (c.full_name or c.razon_social or c.dni or 'Cliente').strip()
        titulo = nombre[:20]
        botones.append({'id': f'btn_cliente_{c.dni}', 'title': titulo})
    botones.append({'id': 'btn_usar_otro_doc', 'title': '🔄 Usar otro documento'})
    send_buttons(numero,
        '¿A nombre de quién realizarás este cambio?',
        botones
    )


def _texto_cuentas_qoricash(moneda):
    """Devuelve texto formateado con las cuentas BCP e INTERBANK para la moneda dada."""
    from app.config.bank_accounts import QORICASH_ACCOUNTS, QORICASH_TITULAR, QORICASH_RUC
    lineas = [f'*Titular:* {QORICASH_TITULAR}', f'*RUC:* {QORICASH_RUC}', '']
    for banco in ('BCP', 'INTERBANK'):
        data = QORICASH_ACCOUNTS.get(banco, {}).get(moneda)
        if data:
            lineas.append(f'🏦 *{banco}*')
            lineas.append(f'  Cuenta: `{data["numero"]}`')
            if banco != 'BCP':
                lineas.append(f'  CCI:    `{data["cci"]}`')
            lineas.append('')
    return '\n'.join(lineas).strip()


def _crear_operacion(session, client):
    """Crea la Operation en el sistema y la retorna."""
    from app.models.operation import Operation
    from app.models.user import User
    from app.extensions import db

    # cotiz_op='compra' = cliente compra $ → QoriCash vende → Venta
    # cotiz_op='venta'  = cliente vende $ → QoriCash compra → Compra
    op_type  = 'Venta' if session.cotiz_op == 'compra' else 'Compra'
    amount_u = session.cotiz_importe
    tc       = session.cotiz_tc
    amount_p = round(amount_u * tc, 2)

    sys_user = User.query.filter_by(role='Master').order_by(User.id).first()
    uid = sys_user.id if sys_user else 1

    import json as _json

    cuenta_raw = session.cotiz_cuenta or ''
    if '|' in cuenta_raw:
        banco_dest, num_dest = cuenta_raw.split('|', 1)
    else:
        banco_dest, num_dest = None, cuenta_raw or None

    # Si solo tenemos número de cuenta (sin banco), resolver el banco desde las cuentas del cliente
    if not banco_dest and num_dest and client:
        for acct in (getattr(client, 'bank_accounts', None) or []):
            if getattr(acct, 'account_number', None) == num_dest:
                banco_dest = getattr(acct, 'bank_name', None)
                break

    # Importe a pagar al cliente: Venta → USD, Compra → PEN (convención del sistema)
    pago_importe = float(amount_u) if op_type == 'Venta' else float(amount_p)

    # Pre-poblar pago al cliente con la cuenta que eligió en el bot
    client_payments = _json.dumps([{
        'importe':        pago_importe,
        'cuenta_destino': num_dest or '',
        'qc_bank':        banco_dest or '',
        'comprobante_url': '',
    }]) if num_dest else '[]'

    op = Operation(
        operation_id          = Operation.generate_operation_id(),
        client_id             = client.id,
        user_id               = uid,
        operation_type        = op_type,
        origen                = 'app',
        amount_usd            = amount_u,
        exchange_rate         = tc,
        amount_pen            = amount_p,
        status                = 'Pendiente',
        destination_account   = num_dest,
        destination_bank_name = banco_dest,
        client_payments_json  = client_payments,
        notes                 = 'Operación generada vía WhatsApp bot',
    )
    db.session.add(op)
    db.session.flush()

    # BONUS — Si el cliente no tenía cuenta registrada en esa moneda, guardarla en su perfil
    # para que en la próxima operación el bot muestre el botón en lugar de preguntar de nuevo.
    if banco_dest and num_dest and client:
        try:
            moneda_dest = '$' if op_type == 'Venta' else 'S/'
            cuentas_actuales = list(getattr(client, 'bank_accounts', None) or [])
            ya_existe = any(
                a.get('account_number', '').replace(' ', '') == num_dest.replace(' ', '')
                for a in cuentas_actuales
            )
            if not ya_existe:
                cuentas_actuales.append({
                    'bank_name':       banco_dest.upper(),
                    'account_number':  num_dest,
                    'account_type':    'Ahorro',
                    'currency':        moneda_dest,
                    'cci':             '',
                })
                client.set_bank_accounts(cuentas_actuales)
                log.info(f'[WaBot] Cuenta {banco_dest} {num_dest} ({moneda_dest}) guardada en perfil cliente {client.id}')
        except Exception as _acct_err:
            log.warning(f'[WaBot] No se pudo guardar cuenta en perfil cliente: {_acct_err}')

    # Enviar email de confirmación igual que las operaciones creadas por otros canales
    try:
        from app.services.email_service import EmailService
        EmailService.send_new_operation_email(op)
    except Exception as _email_err:
        log.warning(f'[WaBot] No se pudo enviar email nueva op {op.operation_id}: {_email_err}')

    return op


def _flujo_op_creada(numero, op, session, client):
    """Envía instrucciones de transferencia tras crear la operación."""
    moneda_enviar = 'PEN' if session.cotiz_op == 'compra' else 'USD'
    simbolo       = 'S/' if moneda_enviar == 'PEN' else 'USD'
    monto_enviar  = float(op.amount_pen) if moneda_enviar == 'PEN' else float(op.amount_usd)
    titular       = (client.full_name or '').title() if client else ''

    cuentas = _texto_cuentas_qoricash(moneda_enviar)

    if _is_horario_atencion():
        aviso_plazo = '⏱ *Plazo:* 15 minutos para transferir.'
        aviso_horario = ''
    else:
        proximo = _next_business_day()
        aviso_plazo   = f'⏱ *Plazo:* hasta las 9:00 AM del {proximo}.'
        aviso_horario = f'> 🕐 _Fuera de horario: procesaremos el {proximo} al inicio de operaciones._\n\n'

    OP_BANNER_URL = 'https://qoricash.pe/hj.png'
    msg = (
        f'✅ *Operación registrada*\n\n'
        f'📋 *N°:* {op.operation_id}'
        + (f'\n👤 *Titular:* {titular}' if titular else '')
        + f'\n\n{aviso_plazo}\n{aviso_horario}'
        f'Transfiérenos *{simbolo} {monto_enviar:,.2f}* a:\n\n'
        f'{cuentas}\n\n'
        f'Transfiere el importe indicado a nuestra cuenta. '
        f'Luego envíanos aquí el código de tu transferencia.'
    )
    return send_buttons_image(numero, OP_BANNER_URL, msg, [
        {'id': 'btn_ya_transferi',                             'title': '✅ Ya transferí'},
        {'id': f'btn_modificar_importe_{op.operation_id}',     'title': '✏️ Cambiar monto'},
        {'id': f'btn_cancelar_operacion_{op.operation_id}',    'title': '❌ Cancelar operación'},
    ])


def _flujo_modificar_importe(numero, session):
    """Inicia el flujo para que el cliente modifique el importe de su operación pendiente."""
    from app.models.operation import Operation
    op = Operation.query.filter_by(operation_id=session.cotiz_op_id).first()

    if not op:
        send_buttons(numero,
            '⚠️ No encontramos tu operación. Contacta a un asesor o vuelve a cotizar.',
            [
                {'id': 'btn_cotizar', 'title': '💱 Cotizar'},
                {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
            ]
        )
        return

    if op.status != 'Pendiente':
        send_text(
            numero,
            f'ℹ️ Tu operación *{op.operation_id}* ya está en estado *{op.status}* '
            f'y no puede modificarse. Contacta a un asesor si necesitas ayuda.'
        )
        session.estado = 'op_pendiente_pago'
        return

    verbo = 'comprar' if session.cotiz_op == 'compra' else 'vender'
    send_text(
        numero,
        f'✏️ *Modificar importe — {op.operation_id}*\n\n'
        f'Importe actual: *USD {float(op.amount_usd):,.2f}*\n'
        f'T.C. aplicado: *{float(op.exchange_rate):.4f}*\n\n'
        f'¿Cuántos USD deseas {verbo} ahora?\n'
        f'_(Mínimo USD {MONTO_MINIMO_USD:,.0f})_'
    )
    session.estado = 'esperando_nuevo_importe'


def _flujo_registrar_codigo_op(numero, codigo, session):
    """Registra el código de operación bancaria del cliente y pasa la op a En proceso."""
    try:
        from app.models.operation import Operation
        # Bloqueo de fila: previene registro duplicado concurrente del mismo código
        op = Operation.query.filter_by(operation_id=session.cotiz_op_id).with_for_update().first()
        if not op:
            send_buttons(numero,
                '⚠️ No encontramos tu operación. Contacta a un asesor o vuelve a cotizar.',
                [
                    {'id': 'btn_cotizar', 'title': '💱 Cotizar'},
                    {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
                ]
            )
            return

        if op.status not in ('Pendiente', 'En proceso'):
            # Op cerrada: conservar código reportado en notas y notificar al equipo
            try:
                from app.utils.formatters import now_peru as _now_cc
                _nota = f'\n[WA {_now_cc().strftime("%d/%m %H:%M")}] Cliente reportó código {codigo} con op en estado {op.status}'
                op.notes = (op.notes or '') + _nota
                db.session.commit()
            except Exception:
                pass
            send_text(numero,
                f'Tu operación *{op.operation_id}* ya no está activa '
                f'(estado actual: *{op.status}*).\n\n'
                'Guardamos tu código para revisión. Un asesor se contactará contigo si hay algo pendiente.'
            )
            try:
                _notificar_admins_wa(
                    f'⚠️ Código *{codigo}* reportado vía WA\n'
                    f'Op: {op.operation_id} (estado: {op.status})\n'
                    f'Tel: {numero}'
                )
            except Exception:
                pass
            session.estado = 'inicio'
            return

        # Idempotencia: verificar si este código ya fue registrado
        deposits = op.client_deposits or []
        ya_registrado = any(d.get('codigo_operacion') == codigo for d in deposits)
        if ya_registrado:
            send_text(numero, f'El código *{codigo}* ya está registrado para tu operación *{op.operation_id}*.')
            session.estado = 'inicio'
            return

        deposits.append({
            'importe':           float(op.amount_pen) if session.cotiz_op == 'compra' else float(op.amount_usd),
            'codigo_operacion':  codigo,
            'cuenta_cargo':      '',
            'comprobante_url':   '',
        })
        op.client_deposits = deposits

        # Cambiar estado a En proceso
        from app.utils.formatters import now_peru
        op.status        = 'En proceso'
        op.in_process_since = now_peru()

        db.session.commit()
        log.info(f'[WaBot] {numero} envió código op {codigo} para {op.operation_id} → En proceso')

        if not _is_horario_atencion():
            proximo = _next_business_day()
            send_text(numero,
                f'> 🕐 _Fuera de horario: procesaremos el {proximo} al inicio de operaciones._'
            )

        send_text(numero,
            f'Recibimos tu código *{codigo}*. '
            f'Verificaremos el abono y te avisaremos cuando el cambio esté completado.'
        )
        session.cotiz_op_id = ''
        session.estado = 'inicio'

    except Exception as e:
        log.error(f'[WaBot] Error registrando código op {numero}: {e}')
        send_text(numero, '⚠️ Ocurrió un error. Contacta a un asesor: *+51 910 624 404*')


def _cuentas_cliente_por_moneda(client, moneda):
    """Retorna las cuentas del cliente filtradas por moneda ('USD' o 'PEN').
    El campo currency se almacena como '$' o 'S/' en el sistema."""
    equiv = {'USD': ('$', 'USD'), 'PEN': ('S/', 'PEN')}
    aceptadas = equiv.get(moneda.upper(), (moneda,))
    return [
        a for a in (client.bank_accounts or [])
        if a.get('currency', '').strip() in aceptadas
    ]


def _flujo_elegir_cuenta(numero, cuentas, moneda):
    """Muestra botones para que el cliente elija su cuenta de destino (máx 2 + 'Otra cuenta')."""
    simbolo = 'USD' if moneda == 'USD' else 'S/'
    cuerpo  = f'¿A qué cuenta {simbolo} deseas recibir tu dinero?'
    botones = []
    for a in cuentas[:2]:
        banco   = a.get('bank_name', 'Banco')
        numero_ = a.get('account_number', '')
        ultimos = numero_[-4:] if len(numero_) >= 4 else numero_
        botones.append({'id': f'btn_cuenta_{numero_}', 'title': f'{banco} ···{ultimos}'})
    botones.append({'id': 'btn_otra_cuenta', 'title': '🏦 Otra cuenta'})
    send_buttons(numero, cuerpo, botones)


def _flujo_pedir_cuenta_destino(numero, moneda):
    """Pide al cliente banco + número de cuenta cuando no tiene ninguna registrada en esa moneda."""
    simbolo = 'dólares (USD)' if moneda == 'USD' else 'soles (S/)'
    send_buttons(numero,
        f'¿A qué cuenta quieres recibir tus *{simbolo}*?\n\n'
        f'Selecciona tu banco 👇',
        [{'id': 'btn_elegir_banco', 'title': '🏦 Elegir banco'}]
    )


def _flujo_confirmar_cuenta(numero, banco, num_cuenta):
    """Muestra los datos de cuenta para confirmación antes de continuar."""
    send_buttons(numero,
        f'Confirma tu cuenta de destino 👇\n\n'
        f'🏦 *Banco:* {banco}\n'
        f'🔢 *N° de cuenta:* {num_cuenta}',
        [
            {'id': 'btn_confirmar_cuenta', 'title': '✅ Sí, es correcta'},
            {'id': 'btn_cambiar_cuenta',   'title': '✏️ Cambiar cuenta'},
        ]
    )


def _flujo_resumen_final(numero, session, client, regenerar_token=True):
    """
    Muestra el resumen compacto de la operación antes de crearla.
    El cliente debe pulsar 'Confirmar cambio' para que se genere la operación.

    regenerar_token=True (default): genera un nuevo UUID y lo guarda en session.cotiz_token.
    regenerar_token=False: reutiliza el token existente (re-envío sin cambios de datos).
    """
    op      = session.cotiz_op or 'compra'
    importe = float(session.cotiz_importe or 0)
    tc      = float(session.cotiz_tc or 0)
    cuenta  = session.cotiz_cuenta or ''

    # Bloquear resumen con TC invalido (0, negativo, NaN, infinito).
    import math as _math_rf
    if not (_math_rf.isfinite(tc) and tc > 0):
        log.warning(f'[WaBot] resumen bloqueado: TC invalido ({tc}) para {numero}')
        send_buttons(numero,
            '⚠️ No pude obtener el tipo de cambio. Cotiza nuevamente para continuar.',
            [
                {'id': 'btn_cotizar', 'title': '🔄 Cotizar de nuevo'},
                {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
            ]
        )
        session.estado = 'inicio'
        return

    # Parsear cuenta (formato guardado: BANCO|NUMERO)
    if '|' in cuenta:
        banco_d, num_d = cuenta.split('|', 1)
    else:
        banco_d, num_d = '', cuenta

    # Resolver banco desde el perfil si falta
    if not banco_d and num_d and client:
        for acct in (getattr(client, 'bank_accounts', None) or []):
            if acct.get('account_number') == num_d:
                banco_d = acct.get('bank_name', '')
                break

    moneda_recibe  = 'USD' if op == 'compra' else 'PEN'
    sim_recibe     = 'USD' if moneda_recibe == 'USD' else 'S/'
    sim_envia      = 'S/'  if moneda_recibe == 'USD' else 'USD'

    if op == 'compra':
        monto_envia  = round(importe * tc, 2)
        monto_recibe = importe
    else:
        monto_envia  = importe
        monto_recibe = round(importe * tc, 2)

    # Mostrar el número completo de cuenta para que el cliente pueda verificar lo ingresado
    cuenta_desc = (f'{banco_d} · {sim_recibe} · {num_d}' if banco_d
                   else f'{sim_recibe} · {num_d}')

    resumen = (
        f'💱 *Resumen de tu operación*\n\n'
        f'› Tú envías:      *{sim_envia} {monto_envia:,.2f}*\n'
        f'› Tú recibes:     *{sim_recibe} {monto_recibe:,.2f}*\n'
        f'› Tipo de cambio: *S/ {tc:.4f}*\n'
        f'› Cuenta destino: *{cuenta_desc}*'
    )
    # Generar (o reutilizar) token de resumen: identifica esta versión exacta (cotización + cuenta).
    # El botón "Confirmar cambio" lleva el token → botones viejos son rechazados automáticamente.
    if regenerar_token:
        _resumen_token = str(uuid.uuid4())
        session.cotiz_token = _resumen_token
    else:
        _resumen_token = session.cotiz_token or str(uuid.uuid4())
    send_buttons(numero, resumen, [
        {'id': f'btn_confirmar_operacion_{_resumen_token}', 'title': '✅ Confirmar cambio'},
        {'id': 'btn_cambiar_cuenta_resumen',                'title': '🔄 Cambiar cuenta'},
    ])


def _seleccionar_cuenta_y_continuar(numero, session, client, cuentas, moneda):
    """
    Enruta a la cuenta de destino según cuántas haya disponibles.
    Verifica límites KYC antes de mostrar el resumen.
    """
    # KYC check: verificar si el cliente puede crear esta operación
    try:
        _kyc_ok, _kyc_msg = client.can_create_operation(float(session.cotiz_importe or 0))
        if not _kyc_ok:
            send_buttons(numero,
                f'⚠️ *Límite operativo alcanzado*\n\n{_kyc_msg}\n\n'
                'Habla con un asesor para completar tu verificación de identidad.',
                [
                    {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
                    {'id': 'btn_cotizar', 'title': '💱 Nueva cotización'},
                ]
            )
            session.estado = 'inicio'
            return
        # Aviso preventivo: última operación permitida sin docs
        _ops_count = client.operations_without_docs_count or 0
        if not client.has_complete_documents and _ops_count == 1:
            send_text(numero,
                '⚠️ _Esta es tu última operación sin verificación de identidad. '
                'Después necesitarás subir tu documento para seguir operando._'
            )
    except Exception as _kyc_err:
        log.warning(f'[WaBot] Error en KYC check {numero}: {_kyc_err}')

    if len(cuentas) == 1:
        acct = cuentas[0]
        banco   = acct.get('bank_name', '')
        num_ctd = acct.get('account_number', '')
        session.cotiz_cuenta = f'{banco}|{num_ctd}'
        _flujo_resumen_final(numero, session, client)
        session.estado = 'confirmando_operacion'
    else:
        _flujo_elegir_cuenta(numero, cuentas, moneda)
        session.estado = 'eligiendo_cuenta_destino'


def _crear_op_y_confirmar(numero, session, client, confirm_token=None):
    """Crea la operación y envía confirmación bajo bloqueo de fila.

    confirm_token: token del botón pulsado; se valida contra session.cotiz_token bajo el lock.
    Si hay discrepancia (sesión concurrente o botón caducado) se re-muestra el resumen actual.
    El commit ocurre ANTES de las llamadas externas (WA, email) para liberar el lock de fila
    lo antes posible y garantizar que la operación persiste aunque fallen las notificaciones.
    """
    try:
        # ── Adquirir bloqueo de fila (previene creación duplicada concurrente) ──
        WaBotSession.query.filter_by(id=session.id).with_for_update().first()
        db.session.expire(session)  # forzar re-lectura de atributos bajo el lock

        # ── Re-verificar estado y token bajo el lock ──
        _estado_lock = session.estado
        _token_lock  = session.cotiz_token or ''

        if _estado_lock != 'confirmando_operacion':
            send_buttons(numero,
                '⚠️ El resumen ya no está activo. ¿Quieres cotizar de nuevo?',
                [
                    {'id': 'btn_cotizar', 'title': '💱 Nueva cotización'},
                    {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
                ]
            )
            db.session.commit()
            return

        if confirm_token and confirm_token != _token_lock:
            # Token caducado: re-mostrar resumen actual sin generar nuevo token
            _flujo_resumen_final(numero, session, client, regenerar_token=False)
            db.session.commit()
            return

        # ── Consumir token para prevenir replay ──
        session.cotiz_token = None

        # ── E1/N5 — Verificar que no haya otra operación activa ──
        _op_race = _operacion_activa_cliente(numero)
        if _op_race:
            _flujo_op_ya_activa(numero, _op_race)
            session.estado = 'inicio'
            db.session.commit()
            return

        # ── CV1 — Verificar que la cotización no haya expirado ──
        try:
            from datetime import timedelta as _td_cv
            from app.utils.formatters import now_peru as _now_cv
            _ts = getattr(session, 'cotiz_timestamp', None)
            if _ts and (_now_cv() - _ts) > _td_cv(minutes=COTIZ_VALIDEZ_MIN):
                _flujo_cotiz_expirada(numero)
                _reset_sesion(session)
                db.session.commit()
                return
        except Exception:
            pass

        # ── CV2 — Revalidar TC e importe (cubre NaN, infinito, cero) ──
        import math as _math_c
        _tc_val  = float(session.cotiz_tc or 0)
        _imp_val = float(session.cotiz_importe or 0)
        if not (_math_c.isfinite(_tc_val) and _tc_val > 0
                and _math_c.isfinite(_imp_val) and _imp_val >= MONTO_MINIMO_USD):
            log.warning(f'[WaBot] Datos inválidos al crear op: TC={_tc_val} importe={_imp_val} {numero}')
            session.cotiz_token = None
            send_buttons(numero,
                '⚠️ Los datos de la cotización no son válidos. Cotiza de nuevo — '
                'conservamos el monto y la dirección.',
                [
                    {'id': 'btn_cotizar', 'title': '🔄 Cotizar de nuevo'},
                    {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
                ]
            )
            db.session.commit()
            return

        # ── KYC3 — Re-verificar límites bajo el lock (previene race condition) ──
        # Adquirir bloqueo de fila en el cliente para serializar creaciones concurrentes
        try:
            from app.models.client import Client as _ClientLock
            _ClientLock.query.filter_by(id=client.id).with_for_update().first()
            db.session.expire(client)
        except Exception as _cl_lock_err:
            log.warning(f'[WaBot] No se pudo bloquear fila cliente {numero}: {_cl_lock_err}')
        try:
            _kyc_ok3, _kyc_msg3 = client.can_create_operation(float(session.cotiz_importe or 0))
            if not _kyc_ok3:
                send_buttons(numero,
                    f'⚠️ *Límite operativo alcanzado*\n\n{_kyc_msg3}\n\n'
                    'Habla con un asesor para completar tu verificación de identidad.',
                    [
                        {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
                        {'id': 'btn_cotizar', 'title': '💱 Nueva cotización'},
                    ]
                )
                session.estado = 'inicio'
                db.session.commit()
                return
        except Exception as _kyc3_err:
            log.warning(f'[WaBot] KYC3 check error {numero}: {_kyc3_err}')

        # ── CV3 — Revalidar cuenta de destino antes de crear la operación ──
        _cuenta_val     = session.cotiz_cuenta or ''
        _num_cuenta_val = _cuenta_val.split('|', 1)[1] if '|' in _cuenta_val else _cuenta_val
        _accts_val      = getattr(client, 'bank_accounts', None) or []
        if _num_cuenta_val and _accts_val:
            _cuenta_valida = any(
                a.get('account_number') == _num_cuenta_val
                for a in _accts_val
            )
            if not _cuenta_valida:
                log.warning(
                    f'[WaBot] CV3: cuenta {_num_cuenta_val} no en perfil '
                    f'cliente {client.id} ({numero}) — rechazando operación'
                )
                send_buttons(numero,
                    '⚠️ La cuenta de destino ya no está disponible. '
                    'Por favor elige de nuevo.',
                    [
                        {'id': 'btn_cotizar', 'title': '🔄 Cotizar de nuevo'},
                        {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
                    ]
                )
                session.cotiz_cuenta = ''
                session.estado = 'inicio'
                db.session.commit()
                return

        # ── Crear operación y actualizar sesión ──
        op = _crear_operacion(session, client)
        # Capturar datos antes del commit (SQLAlchemy los expira tras commit)
        _op_id       = op.operation_id
        _op_type     = op.operation_type
        _cotiz_imp   = float(session.cotiz_importe or 0)
        _cotiz_tc    = float(session.cotiz_tc or 0)
        session.cotiz_op_id = _op_id
        session.estado      = 'op_pendiente_pago'

        # ── Commit ANTES de llamadas externas (libera el lock de fila) ──
        db.session.commit()

        # ── Enviar instrucciones al cliente ──
        sent = _flujo_op_creada(numero, op, session, client)
        if not sent:
            log.warning(f'[WaBot] Instrucciones no enviadas para {_op_id}; '
                        f'cliente puede recuperar respondiendo en estado op_pendiente_pago.')

        # ── Notificar al sistema en tiempo real ──
        try:
            from app.services.notification_service import NotificationService
            NotificationService.notify_new_operation(op)
            NotificationService.notify_dashboard_update()
        except Exception as _notif_err:
            log.warning(f'[WaBot] Error notificando nueva op al sistema: {_notif_err}')

        # ── Notificar a admins por WA + email ──
        try:
            titular = client.full_name or client.razon_social or numero
            tipo_op = 'Compra USD' if _op_type == 'Compra' else 'Venta USD'
            _msg_op = (
                f'💱 Nueva operación desde el bot\n\n'
                f'Op:      {_op_id}\n'
                f'Cliente: {titular}\n'
                f'Tipo:    {tipo_op}\n'
                f'Monto:   USD {_cotiz_imp:,.2f}\n'
                f'TC:      S/ {_cotiz_tc:.4f}\n\n'
                f'Esperando transferencia del cliente.'
            )
            _notificar_admins_wa(_msg_op)
            _notificar_admins_email(
                f'💱 Nueva operación bot — {_op_id}',
                _msg_op
            )
        except Exception as _wa_err:
            log.warning(f'[WaBot] Error notificando nueva op a admins: {_wa_err}')
    except Exception as _oe:
        log.error(f'[WaBot] Error creando op: {_oe}')
        send_buttons(numero,
            'Ocurrió un error al crear la operación. Por favor contacta a un asesor.',
            [{'id': 'btn_asesor', 'title': '💬 Hablar con asesor'}]
        )
        session.estado = 'inicio'


def _flujo_sin_kyc(numero, kyc_status):
    if kyc_status in ('pendiente', 'en_revision'):
        msg = ('⏳ Tu cuenta está siendo revisada por nuestro equipo.\n\n'
               'Te notificaremos cuando esté aprobada para que puedas operar.\n\n'
               '¿Tienes dudas? Escríbenos: *+51 910 624 404*')
    else:
        msg = ('❌ Tu cuenta no está habilitada para operar.\n\n'
               'Contáctate con un asesor para más información.\n\n'
               '📞 *+51 910 624 404*')
    send_buttons(numero, msg, [
        {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
        {'id': 'btn_cotizar', 'title': '💱 Nueva cotización'},
    ])


def _flujo_recordatorio_registro(numero, estado):
    """Recuerda al cliente en qué paso del registro se quedó y ofrece volver al inicio."""
    mensajes = {
        'esperando_dni_front': '📋 ¡Tienes un registro en curso! Solo necesitamos la foto del frente de tu DNI para continuar. 😊',
        'esperando_dni_back':  '📋 ¡Ya casi terminas! Falta la foto del reverso de tu DNI.',
        'esperando_ruc':       '📋 ¡Tienes un registro en curso! Solo falta que nos envíes la Ficha RUC de tu empresa.',
        'esperando_email':     '📋 ¡Casi listo! Solo falta tu correo electrónico para completar el registro.',
    }
    msg = mensajes.get(estado, '📋 Tienes un registro en curso.')
    send_buttons(numero, msg, [
        {'id': 'btn_volver_inicio', 'title': '🔙 Volver al inicio'},
        {'id': 'btn_asesor',        'title': '💬 Hablar con asesor'},
    ])


def _flujo_no_encontrado(numero):
    send_buttons(numero,
        '🔍 No encontramos tu cuenta en Qoricash.\n\n'
        '¿Deseas registrarte ahora? El proceso toma solo unos minutos.',
        [
            {'id': 'btn_registrarme', 'title': '📝 Registrarme'},
            {'id': 'btn_asesor',      'title': '💬 Hablar con asesor'},
        ]
    )


def _flujo_pedir_numero_doc(numero, tipo):
    if tipo == 'natural':
        send_text(numero, '🪪 Ingresa tu número de *DNI o CE* (8-9 dígitos):')
    else:
        send_text(numero, '🏢 Ingresa el *RUC* de tu empresa (11 dígitos):')


def _flujo_asesor(numero):
    send_text(numero,
        '💬 *Conectando con un asesor...*\n\n'
        'En breve alguien de nuestro equipo te escribe por este mismo chat.\n\n'
        'Cuéntanos tu consulta mientras tanto 👇'
    )
    log.info(f'[WaBot] {numero} solicitó hablar con asesor.')
    _msg_asesor = (
        f'💬 Cliente solicita asesor\n\n'
        f'WA: {numero}\n\n'
        f'Atiéndelo en: https://app.qoricash.pe/crm/whatsapp'
    )
    _notificar_admins_wa(_msg_asesor)
    _notificar_admins_email(
        f'💬 Cliente solicita asesor — {numero}',
        _msg_asesor
    )


def _flujo_tipo_cliente(numero):
    send_buttons(numero,
        '¿Cómo quieres registrarte?',
        [
            {'id': 'btn_natural', 'title': '👤 Persona natural'},
            {'id': 'btn_empresa', 'title': '🏢 Empresa'},
        ]
    )


def _flujo_pedir_dni_front(numero, nombre=None):
    saludo = f'Hola *{nombre}* 👋 ' if nombre else ''
    send_text(numero,
        f'{saludo}📷 Por favor envíanos una *foto del frente de tu DNI*.\n\n'
        'Asegúrate de que sea legible y que los 4 bordes sean visibles.'
    )


def _flujo_pedir_dni_back(numero):
    send_text(numero, '📷 Ahora envíanos una *foto del reverso de tu DNI*.')


def _flujo_pedir_ruc(numero, razon_social=None):
    empresa = f' de *{razon_social}*' if razon_social else ''
    send_text(numero,
        f'✅ Empresa verificada{empresa}.\n\n'
        '📄 Por favor envíanos la *Ficha RUC de tu empresa*.\n\n'
        'Puedes descargarla desde sunat.gob.pe → Consulta RUC.'
    )


def _flujo_pedir_email(numero):
    send_text(numero, '📧 Por último, ingresa tu *correo electrónico*:')


def _flujo_confirmar_registro(numero, session):
    if session.tipo == 'natural':
        tipo_doc = 'CE' if len(session.cotiz_doc) == 9 else 'DNI'
        msg = (
            '✅ *¡Solicitud de registro recibida!*\n\n'
            f'Nuestro equipo verificará tu {tipo_doc} y activará tu cuenta en un máximo de *15 minutos*.\n\n'
            'Te notificaremos por este mismo WhatsApp cuando esté lista para operar.'
        )
        tipo_desc = 'Persona Natural'
    else:
        msg = (
            '✅ *¡Solicitud de registro de empresa recibida!*\n\n'
            'Nuestro equipo verificará la ficha RUC y activará la cuenta corporativa en máximo *15 minutos*.\n\n'
            'Te notificaremos por WhatsApp cuando esté habilitada.'
        )
        tipo_desc = 'Empresa'

    # P3 — Si venía de una cotización aceptada, recordarle que puede retomar
    if session.cotiz_op and session.cotiz_importe:
        op_texto = 'comprar' if session.cotiz_op == 'compra' else 'vender'
        msg += (
            f'\n\n💡 _Recuerda que querías {op_texto} USD {session.cotiz_importe:,.0f}. '
            f'Una vez activa tu cuenta, cotiza de nuevo para obtener el tipo de cambio del momento._'
        )

    send_buttons(numero, msg, [
        {'id': 'btn_asesor', 'title': '💬 Hablar con asesor'},
    ])
    _registrar_lead(numero, session)
    _notificar_admin_registro(numero, session, tipo_desc)


def _notificar_admin_registro(numero, session, tipo_desc):
    """Notifica a gerencia por email y WhatsApp cuando hay un registro pendiente desde el bot."""
    nombre   = session.nombre or numero
    doc      = session.cotiz_doc or 'no indicado'
    email_cl = session.cotiz_email or 'no indicado'

    # ── Email: info@qoricash.pe → gerencia@qoricash.pe ──────────────
    try:
        from flask_mail import Message
        from app.extensions import mail
        from flask import current_app
        app = current_app._get_current_object()

        asunto = f'[Bot WA] Nuevo registro pendiente — {tipo_desc}: {nombre}'
        cuerpo = (
            f'Se ha recibido una nueva solicitud de registro a través del bot de WhatsApp.\n\n'
            f'Tipo:     {tipo_desc}\n'
            f'Nombre:   {nombre}\n'
            f'DNI/RUC:  {doc}\n'
            f'Email:    {email_cl}\n'
            f'Número WA: {numero}\n\n'
            f'Tiempo máximo de respuesta: 15 minutos.\n\n'
            f'Revisa el panel de KYC/Clientes para activar la cuenta.'
        )
        email_msg = Message(
            subject=asunto,
            sender='info@qoricash.pe',
            recipients=['gerencia@qoricash.pe'],
            body=cuerpo,
        )

        import eventlet as _ev

        def _do_send():
            with app.app_context():
                try:
                    mail.send(email_msg)
                    log.info(f'[WaBot] Email de registro enviado a gerencia para {numero}')
                except Exception as _e:
                    log.warning(f'[WaBot] Error enviando email de registro: {_e}')

        _ev.spawn_n(_do_send)
    except Exception as e:
        log.warning(f'[WaBot] No se pudo preparar email de registro: {e}')

    # ── WhatsApp + Email: notificar a todos los admins ──────────────
    _msg_reg = (
        f'🔔 Nuevo registro pendiente — {tipo_desc}\n\n'
        f'Nombre:   {nombre}\n'
        f'DNI/RUC:  {doc}\n'
        f'Email:    {email_cl}\n'
        f'WA:       {numero}\n\n'
        f'Tiempo maximo de activacion: 15 minutos\n'
        f'Revisa el panel de KYC para activar la cuenta.'
    )
    _notificar_admins_wa(_msg_reg)
    _notificar_admins_email(
        f'🔔 Nuevo registro pendiente — {nombre}',
        _msg_reg
    )
    log.info(f'[WaBot] Notificación WA+Email de registro enviada a admins para {numero}')


def _registrar_lead(numero, session):
    try:
        from app.models.prospecto import Prospecto, ActividadProspecto
        from app.models.user import User
        digits = re.sub(r'\D', '', numero)
        if digits.startswith('51') and len(digits) == 11:
            digits = digits[2:]
        if not digits:
            return
        existing = Prospecto.query.filter(
            (Prospecto.telefono == digits) |
            (Prospecto.contacto_wa == digits)
        ).first()
        if not existing:
            tipo_desc = 'Persona Natural' if session.tipo == 'natural' else 'Empresa'
            p = Prospecto(
                nombre_comercial = session.nombre or f'Lead WA {numero}',
                telefono         = digits,
                contacto_wa      = digits,
                email            = session.cotiz_email or None,
                estado_comercial = 'interesado',
                canal_captacion  = 'whatsapp_bot',
                notas            = (
                    f'Registro vía bot WhatsApp — {tipo_desc}. '
                    f'Doc: {session.cotiz_doc or "pendiente"}. '
                    'DNI/RUC pendiente de validación.'
                ),
            )
            db.session.add(p)
            sys_user = User.query.filter_by(role='Master').order_by(User.id).first()
            uid = sys_user.id if sys_user else 1
            db.session.flush()
            act = ActividadProspecto(
                prospecto_id=p.id,
                user_id=uid,
                tipo='whatsapp',
                canal='whatsapp_bot',
                descripcion=f'Registro vía bot — {tipo_desc}. DNI/RUC pendiente de validación.',
                resultado='Lead capturado',
            )
            db.session.add(act)
            log.info(f'[WaBot] Nuevo prospecto creado desde bot: {numero} ({tipo_desc})')
    except Exception as e:
        log.warning(f'[WaBot] No se pudo registrar lead: {e}')


# ── IA conversacional (Claude) ─────────────────────────────────────

_ANTHROPIC_CLIENT = None

def _get_anthropic_client():
    """Lazy-init del cliente Anthropic. Retorna None si no hay API key."""
    global _ANTHROPIC_CLIENT
    if _ANTHROPIC_CLIENT is not None:
        return _ANTHROPIC_CLIENT
    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        log.warning('[WaBot-IA] ANTHROPIC_API_KEY no configurada — IA desactivada')
        return None
    try:
        import anthropic
        _ANTHROPIC_CLIENT = anthropic.Anthropic(api_key=api_key)
        log.info('[WaBot-IA] Cliente Anthropic inicializado OK')
        return _ANTHROPIC_CLIENT
    except Exception as e:
        log.warning(f'[WaBot-IA] No se pudo inicializar cliente Anthropic: {e}')
        return None


def _historial_ia(numero, limite=12, wa_id=None, history_since=None):
    """
    Retorna (filtered, current_in_history) donde:
    - filtered: lista de dicts {'role': 'user'|'assistant', 'content': str}
      listos para la API de Anthropic.
    - current_in_history: True si el mensaje identificado por wa_id fue encontrado
      en la ventana devuelta.

    history_since: datetime opcional. Si se proporciona, solo se incluyen mensajes
      cuyo created_at >= history_since.  Usado para acotar el contexto de IA al
      ciclo vigente de sesión y evitar que instrucciones de sesiones expiradas
      dirijan la nueva conversación.

    Los mensajes consecutivos del mismo rol se CONCATENAN (separados por '---')
    para preservar todo el contenido. Ejemplo: si el cliente envió tres mensajes
    seguidos ("Quiero comprar dólares", "Son 1500", "Al BCP"), los tres quedan
    en un único turno 'user' con el contenido completo — ninguno se descarta.

    NOTA: la concatenación de roles es un post-procesado para la alternancia de
    Anthropic. No equivale a agrupar varios webhooks en una sola respuesta —
    cada webhook se procesa de forma independiente.

    wa_id: ID de WhatsApp del mensaje que se está procesando.
           Cuando se proporciona:
           - Se usa como techo temporal: solo se incluyen mensajes hasta ese
             registro (inclusive), lo que evita el bleed-in de mensajes de
             solicitudes concurrentes llegadas casi al mismo tiempo.
           - El orden usa id como desempate para timestamps iguales (determinista).
           - current_in_history=True si ese wa_id está en la ventana devuelta.
    """
    try:
        from sqlalchemy import or_, and_

        current_db = None
        if wa_id:
            current_db = (WaMessage.query
                          .filter_by(numero=numero, wa_id=wa_id)
                          .first())

        q = WaMessage.query.filter_by(numero=numero)
        if history_since is not None:
            # Acotar al ciclo vigente: excluir mensajes de sesiones anteriores.
            # history_since = session.session_started_at, establecido al expirar.
            q = q.filter(WaMessage.created_at >= history_since)
        if current_db is not None:
            # Solo mensajes hasta el registro actual (inclusive).
            # Usa id como desempate cuando dos mensajes tienen el mismo created_at.
            q = q.filter(
                or_(
                    WaMessage.created_at < current_db.created_at,
                    and_(
                        WaMessage.created_at == current_db.created_at,
                        WaMessage.id <= current_db.id,
                    )
                )
            )

        msgs = (
            q.order_by(WaMessage.created_at.desc(), WaMessage.id.desc())
             .limit(limite)
             .all()
        )
        msgs = list(reversed(msgs))  # cronológico

        current_in_history = False
        historia = []
        for m in msgs:
            if wa_id and m.wa_id == wa_id:
                current_in_history = True
            role = 'assistant' if m.direccion == 'saliente' else 'user'
            texto = m.mensaje.strip()
            if not texto:
                continue
            # Normalizar templates de Meta en algo legible por la IA
            if texto.startswith('[template:'):
                texto = f'[Mensaje automático del sistema: {texto}]'
            historia.append({'role': role, 'content': texto})

        # Anthropic requiere alternancia user/assistant.
        # Mensajes consecutivos del mismo rol se CONCATENAN para preservar
        # todo el contenido — nunca se descartan mensajes previos.
        filtered = []
        for msg in historia:
            if filtered and filtered[-1]['role'] == msg['role']:
                filtered[-1] = {
                    'role': filtered[-1]['role'],
                    'content': filtered[-1]['content'] + '\n---\n' + msg['content'],
                }
            else:
                filtered.append({'role': msg['role'], 'content': msg['content']})
        return filtered, current_in_history
    except Exception as e:
        log.warning(f'[WaBot-IA] Error leyendo historial: {e}')
        return [], False


def _construir_contexto_sesion(numero, session):
    """
    Construye un bloque de texto estructurado con el estado actual de la sesión,
    la cotización vigente, la cuenta de destino y la operación vinculada.
    Se incluye en el system prompt de la IA para que responda con contexto real.

    IMPORTANTE:
    - No incluye DNI, RUC, cuentas completas ni credenciales.
    - Los datos desconocidos se indican explícitamente; nunca se suponen.
    - La operación se consulta desde la BD para obtener su estado real,
      sin depender de plantillas en el historial de mensajes.
    """
    from app.utils.formatters import now_peru
    from datetime import timedelta

    lineas = []

    # ── Estado conversacional ──────────────────────────────────────────────────
    estado = session.estado or 'inicio'
    DESCRIPCIONES_ESTADO = {
        'inicio':                    'sin flujo activo; esperando primer mensaje',
        'menu_mostrado':             'menú de bienvenida visible; cliente eligiendo acción',
        'eligiendo_operacion':       'eligiendo dirección del cambio (soles→dólares o dólares→soles)',
        'esperando_importe':         'el bot pidió el monto en USD; cliente debe escribirlo',
        'viendo_cotizacion':         'cotización mostrada; cliente decidiendo si acepta el precio',
        'eligiendo_cuenta_destino':  'bot mostrando cuentas guardadas del cliente para destino',
        'esperando_cuenta_destino':  'cliente debe escribir banco y número de cuenta (formato: BANCO NÚMERO)',
        'esperando_cuenta_nueva':    'cliente ingresando una cuenta diferente a las guardadas',
        'esperando_num_cuenta':      'cliente ingresando número de cuenta tras elegir banco en la lista',
        'confirmando_cuenta':        'bot pidió confirmación de la cuenta destino mostrada',
        'confirmando_operacion':     'resumen de operación mostrado; cliente debe confirmar o cambiar cuenta',
        'op_pendiente_pago':         'operación creada; cliente debe realizar la transferencia bancaria',
        'esperando_codigo_op':       'cliente debe ingresar el código de su voucher bancario',
        'esperando_referencia_yt':   'cliente debe escribir el número de operación (ej: EXP-001) para localizar su transferencia',
        'esperando_nuevo_importe':   'cliente puede modificar el importe de la operación pendiente',
        'eligiendo_tipo':            'registro: eligiendo tipo de cuenta (persona natural / empresa)',
        'esperando_numero_doc':      'registro: ingresando DNI o RUC',
        'esperando_dni_front':       'registro: enviando foto del frente del DNI',
        'esperando_dni_back':        'registro: enviando foto del reverso del DNI',
        'esperando_ruc':             'registro: enviando ficha RUC de la empresa',
        'esperando_email':           'registro: ingresando correo electrónico',
        'completado':                'registro enviado; pendiente de activación por el equipo',
        'esperando_id_cotizar':      'cliente debe ingresar DNI/CE/RUC para identificarse',
        'esperando_email_cotizar':   'cliente nuevo identificado; debe ingresar su correo',
        'esperando_email_registro':  'cliente nuevo en flujo registro; debe ingresar su correo',
        'esperando_ce_numero':       'cliente ingresando número de Carné de Extranjería',
        'esperando_nombre_ce':       'cliente ingresando nombre completo (titular CE)',
        'esperando_confirmar_ce':    'esperando confirmación de que el número es un CE',
        'esperando_identificacion':  'flujo de identificación con posible auto-creación de cuenta',
        'decidiendo_registro':       'cliente eligiendo si ya tiene cuenta o quiere registrarse',
    }
    desc_estado = DESCRIPCIONES_ESTADO.get(estado, f'flujo interno: {estado}')
    lineas.append(f'ESTADO DEL FLUJO: {desc_estado}')

    cotiz_op      = session.cotiz_op or ''
    cotiz_importe = session.cotiz_importe or 0.0
    cotiz_tc      = session.cotiz_tc or 0.0
    op_id         = session.cotiz_op_id or ''

    # ── Dirección del cambio (disponible con o sin operación creada) ───────────
    if cotiz_op and cotiz_importe:
        if cotiz_op == 'compra':
            dir_cliente = 'cliente ENVÍA soles → RECIBE dólares'
        else:
            dir_cliente = 'cliente ENVÍA dólares → RECIBE soles'
        lineas.append(f'DIRECCIÓN DEL CAMBIO: {dir_cliente}')
        lineas.append(f'MONTO EN JUEGO: USD {cotiz_importe:,.2f}')

    # ── Operación vinculada (si existe, sus importes son la referencia) ────────
    if op_id:
        try:
            from app.models.operation import Operation
            op = Operation.query.filter_by(operation_id=op_id).first()
            if op:
                # Validar que la operación pertenece al cliente identificado en la sesión
                cotiz_doc_val = session.cotiz_doc or ''
                if cotiz_doc_val:
                    from app.models.client import Client as _ClientVal
                    client_of_op = _ClientVal.query.filter_by(id=op.client_id).first()
                    doc_ok = client_of_op and cotiz_doc_val in (
                        client_of_op.dni or '', client_of_op.ruc or ''
                    )
                    if not doc_ok:
                        lineas.append(
                            f'OPERACIÓN VINCULADA: referencia {op_id} no corresponde '
                            f'al perfil identificado en esta sesión'
                        )
                        op = None  # no usar datos de esta operación

                if op:
                    if op.status == 'Completada':
                        extra = ('— operación finalizada; '
                                 'el sistema registra su resultado final')
                    elif op.status == 'En proceso':
                        extra = ('— el cliente reportó su transferencia; '
                                 'la operación está en proceso y el sistema '
                                 'todavía no registra su finalización')
                    elif op.status == 'Pendiente':
                        ahora = now_peru()
                        pago_expira = op.created_at + timedelta(minutes=15)
                        if ahora < pago_expira:
                            mins_pago = max(0, int((pago_expira - ahora).total_seconds() / 60))
                            extra = f'— esperando transferencia (~{mins_pago} min restantes para pagar)'
                        else:
                            extra = '— esperando transferencia (plazo de pago expirado)'
                    elif op.status in ('Cancelado', 'Cancelada'):
                        extra = '— cancelada'
                    else:
                        extra = f'— {op.status}'
                    lineas.append(
                        f'OPERACIÓN VINCULADA: ID {op.operation_id} | estado: {op.status} | '
                        f'USD {float(op.amount_usd):,.2f} ↔ S/ {float(op.amount_pen):,.2f} | '
                        f'TC confirmado S/ {float(op.exchange_rate):.4f} {extra}'
                    )
            else:
                lineas.append(f'OPERACIÓN VINCULADA: referencia {op_id} no encontrada en el sistema')
        except Exception as _e:
            lineas.append(f'OPERACIÓN VINCULADA: referencia {op_id} (error al consultar: {_e})')

    else:
        # Sin operación creada: mostrar cotización en curso si hay datos
        if cotiz_op and cotiz_importe and cotiz_tc:
            monto_pen = round(cotiz_importe * cotiz_tc, 2)
            if cotiz_op == 'compra':
                lineas.append(
                    f'COTIZACIÓN EN CURSO: envía S/ {monto_pen:,.2f} | recibe USD {cotiz_importe:,.2f}'
                    f' | TC cotizado S/ {cotiz_tc:.4f}'
                )
            else:
                lineas.append(
                    f'COTIZACIÓN EN CURSO: envía USD {cotiz_importe:,.2f} | recibe S/ {monto_pen:,.2f}'
                    f' | TC cotizado S/ {cotiz_tc:.4f}'
                )
            # Plazo para confirmar la cotización (distinto del plazo de pago de la operación)
            cotiz_ts = getattr(session, 'cotiz_timestamp', None)
            if cotiz_ts:
                expira = cotiz_ts + timedelta(minutes=15)
                ahora = now_peru()
                if ahora < expira:
                    mins_rest = max(0, int((expira - ahora).total_seconds() / 60))
                    lineas.append(f'PLAZO COTIZACIÓN: ~{mins_rest} min para aceptar antes de que expire')
                else:
                    lineas.append('PLAZO COTIZACIÓN: expirada')
            else:
                lineas.append('PLAZO COTIZACIÓN: no disponible')
        elif cotiz_op and cotiz_importe:
            lineas.append('COTIZACIÓN EN CURSO: TC aún no calculado')
        else:
            lineas.append('COTIZACIÓN EN CURSO: ninguna')

        # Fallback: buscar operación por teléfono solo si la asociación es inequívoca.
        # Un número con varios perfiles o varias ops activas no es suficiente.
        try:
            clientes = _buscar_clientes_por_telefono(numero)
            if len(clientes) > 1:
                lineas.append(
                    'OPERACIÓN VINCULADA: no determinada — '
                    'el número está asociado a más de un perfil registrado'
                )
            elif len(clientes) == 1:
                from app.models.operation import Operation as _OpFb
                ops_activas_fb = _OpFb.query.filter(
                    _OpFb.client_id == clientes[0].id,
                    _OpFb.status.in_(['Pendiente', 'En proceso'])
                ).all()
                if len(ops_activas_fb) == 1:
                    _o = ops_activas_fb[0]
                    lineas.append(
                        f'OPERACIÓN DETECTADA (por teléfono, sin vincular): {_o.operation_id} | '
                        f'estado: {_o.status} | USD {float(_o.amount_usd):,.2f} '
                        f'(para preguntas sobre esta operación, indicar el ID)'
                    )
                elif len(ops_activas_fb) > 1:
                    lineas.append(
                        'OPERACIÓN VINCULADA: no determinada — '
                        'el cliente tiene más de una operación activa'
                    )
                else:
                    lineas.append('OPERACIÓN VINCULADA: ninguna')
            else:
                lineas.append('OPERACIÓN VINCULADA: ninguna')
        except Exception:
            lineas.append('OPERACIÓN VINCULADA: ninguna')

    # ── Cuenta de destino (enmascarada) ────────────────────────────────────────
    cotiz_cuenta = session.cotiz_cuenta or ''
    if cotiz_cuenta and '|' in cotiz_cuenta:
        banco_dest, num_dest = cotiz_cuenta.split('|', 1)
        mascara = ('···' + num_dest[-4:]) if len(num_dest) >= 4 else '···'
        if banco_dest:
            lineas.append(f'CUENTA DESTINO CLIENTE: {banco_dest} {mascara}')
        else:
            lineas.append(f'CUENTA DESTINO CLIENTE: seleccionada ({mascara})')
    elif cotiz_cuenta:
        lineas.append('CUENTA DESTINO CLIENTE: parcialmente definida')
    else:
        lineas.append('CUENTA DESTINO CLIENTE: no definida aún')

    # ── Acción pendiente ───────────────────────────────────────────────────────
    ACCION_PENDIENTE = {
        'esperando_importe':       'cliente debe escribir el monto en USD (ejemplo: 1500)',
        'viendo_cotizacion':       'cliente debe pulsar "Aceptar cotización" o pedir más opciones',
        'eligiendo_cuenta_destino':'cliente debe elegir su cuenta de destino de los botones',
        'esperando_cuenta_destino':'cliente debe escribir: BANCO NÚMERO (ejemplo: BCP 1234567890)',
        'esperando_num_cuenta':    'cliente debe escribir su número de cuenta o CCI',
        'confirmando_cuenta':      'cliente debe confirmar o cambiar la cuenta mostrada',
        'confirmando_operacion':   'cliente debe pulsar "Confirmar cambio" o "Cambiar cuenta" en el resumen',
        'op_pendiente_pago':       'cliente debe realizar la transferencia y pulsar "Ya transferí"',
        'esperando_codigo_op':     'cliente debe ingresar el código de su voucher bancario',
        'esperando_referencia_yt': 'cliente debe escribir el número de operación (ej: EXP-001) para localizar su transferencia',
        'esperando_nuevo_importe': 'cliente puede modificar el monto escribiendo el nuevo importe en USD',
        'esperando_id_cotizar':    'cliente debe ingresar su DNI (8), CE (9) o RUC (11 dígitos)',
        'esperando_email_cotizar': 'cliente debe ingresar su correo electrónico',
        'esperando_email_registro':'cliente debe ingresar su correo electrónico',
        'esperando_numero_doc':    'cliente debe ingresar su DNI o RUC para el registro',
        'esperando_dni_front':     'cliente debe enviar foto del frente de su DNI',
        'esperando_dni_back':      'cliente debe enviar foto del reverso de su DNI',
        'esperando_ruc':           'cliente debe enviar la ficha RUC de su empresa',
        'esperando_email':         'cliente debe ingresar su correo electrónico',
        'esperando_nombre_ce':     'cliente debe ingresar su nombre completo',
    }
    accion = ACCION_PENDIENTE.get(estado, 'ninguna acción específica pendiente')
    lineas.append(f'ACCIÓN PENDIENTE: {accion}')

    return '\n'.join(lineas)


def _respuesta_ia(texto_usuario, numero, session, wa_id=''):
    """
    Genera una respuesta conversacional usando Claude Haiku.
    Incluye historial reciente y contexto estructurado de la sesión.
    Retorna str con la respuesta, o None si falla (para caer al fallback clásico).

    wa_id: ID de WhatsApp del mensaje que se está procesando.
           Se pasa a _historial_ia para acotar la ventana y verificar que el
           mensaje actual esté presente en el historial devuelto.

    El historial se construye con _historial_ia (que preserva todos los mensajes
    concatenando consecutivos del mismo rol). El contexto de sesión se inyecta
    en el system prompt mediante _construir_contexto_sesion.

    No otorga a la IA capacidad para crear, modificar ni cancelar operaciones.
    """
    client = _get_anthropic_client()
    if client is None:
        return None

    # bot_pausado se verifica en handle_message antes de llegar aquí;
    # esta comprobación es una salvaguarda adicional para llamadas directas.
    try:
        if session.bot_pausado:
            return None
    except Exception:
        pass

    try:
        compra, venta = _get_tc()
        tc_str = (
            f'Compra: S/ {compra:.3f} | Venta: S/ {venta:.3f}'
            if compra else 'no disponible en este momento'
        )

        nombre_cliente = session.nombre or 'cliente'
        registrado     = bool(session.cotiz_doc)
        en_horario     = _is_horario_atencion()
        horario_txt    = 'Lunes a viernes: 9:00 am – 6:00 pm | Sábados: 9:00 am – 2:00 pm'
        disponibilidad = (
            'en horario de atención'
            if en_horario else
            'fuera de horario (la operación se registra y se procesa al inicio del siguiente día hábil)'
        )

        # Contexto estructurado de la sesión actual (estado, cotización, op, cuenta)
        contexto_sesion = _construir_contexto_sesion(numero, session)

        system_prompt = (
            'Eres el asistente virtual de Qoricash, una casa de cambio digital peruana '
            'inscrita en la SBS. '
            'Tu función es responder preguntas y aclarar dudas. No vendes ni eres insistente.\n\n'

            'REGLAS GENERALES:\n'
            '- Responde en español, breve y amable (máximo 2-3 oraciones).\n'
            '- Texto plano sin asteriscos ni markdown. Emojis ocasionales y naturales.\n'
            '- No inventes tipos de cambio distintos a los proporcionados.\n'
            '- No afirmes haber realizado acciones que el sistema no ejecutó. '
            'No puedes crear, modificar, cancelar ni completar operaciones.\n'
            '- Si el cliente pide un cambio que el flujo actual no puede aplicar '
            '(ej: corregir cuenta ya confirmada), explícaselo y oriéntalo al asesor '
            'o al botón correspondiente — no digas que lo cambiaste.\n\n'

            'SOBRE EL ESTADO ACTUAL:\n'
            '- El CONTEXTO DE SESIÓN muestra el estado real del flujo y los datos disponibles.\n'
            '- Responde considerando el paso en que está el cliente; '
            'no repitas preguntas ya resueltas ni reinicies el proceso.\n'
            '- Distingue entre datos disponibles y pendientes; no completes valores por suposición.\n'
            '- Si la operación está "En proceso", el cliente reportó su transferencia '
            'y estamos verificando el depósito bancario — los fondos aún no fueron enviados.\n'
            '- Si la operación está "Completada", los fondos ya fueron enviados al cliente. '
            'Después de eso puede hacer nuevas preguntas o cotizar de nuevo; '
            'no fuerces una despedida solo por la presencia de esa notificación.\n\n'

            'SOBRE DESPEDIDAS Y CIERRES:\n'
            '- Si el cliente dice "gracias", "ok", "listo", "perfecto" o similar, '
            'responde con calidez breve y ofrece ayuda adicional si el flujo sigue abierto.\n'
            '- Solo te despides si el cliente indica explícitamente que no necesita más ayuda.\n\n'

            '- Si el cliente quiere cotizar, indícale que use el botón Cotizar.\n'
            '- Si la consulta está fuera de tu alcance, ofrece conectar con un asesor.\n\n'

            'DATOS ACTUALES DEL SERVICIO:\n'
            f'- Tipo de cambio hoy: {tc_str}\n'
            '- Solo operamos USD ↔ PEN (dólares americanos / soles peruanos)\n'
            f'- Horario de atención: {horario_txt}\n'
            f'- Estado del servicio ahora: {disponibilidad}\n'
            f'- Nombre del cliente: {nombre_cliente}\n'
            f'- Cliente registrado en el sistema: {"sí" if registrado else "no"}\n'
            '- Web: www.qoricash.pe | Asesor: +51 910 624 404\n\n'

            'CONTEXTO DE SESIÓN (datos reales del flujo; no suponer valores ausentes):\n'
            f'{contexto_sesion}'
        )

        # ── Construir historial ────────────────────────────────────────────────
        # _historial_ia preserva todos los mensajes (concatena consecutivos del mismo rol)
        # y devuelve un flag indicando si el mensaje actual (por wa_id) fue encontrado.
        # El wa_id se usa para acotar el techo temporal y garantizar un orden determinista.
        # session_started_at acota el historial al ciclo vigente: mensajes de sesiones
        # expiradas no deben influir en la interpretación de la nueva conversación.
        _history_since = getattr(session, 'session_started_at', None)
        historia, current_in_history = _historial_ia(numero, wa_id=wa_id, history_since=_history_since)

        # Garantizar que la secuencia empiece con 'user'
        while historia and historia[0]['role'] == 'assistant':
            historia = historia[1:]

        if not historia:
            # Historial vacío: crear turno mínimo con el mensaje actual
            historia = [{'role': 'user', 'content': texto_usuario}]
        elif not current_in_history:
            # El mensaje actual no fue hallado en la ventana devuelta (wa_id vacío,
            # mensaje fuera de la ventana de N registros, o lag de BD).
            # Se incorpora para que la IA procese siempre el mensaje actual.
            if historia[-1]['role'] == 'user':
                historia[-1] = {
                    'role': 'user',
                    'content': historia[-1]['content'] + '\n---\n' + texto_usuario,
                }
            else:
                historia.append({'role': 'user', 'content': texto_usuario})
        elif historia[-1]['role'] != 'user':
            # El mensaje está en BD pero tras la concatenación el turno final es
            # 'assistant' (borde con lag). Agregar para cerrar el turno.
            historia.append({'role': 'user', 'content': texto_usuario})
        # Si current_in_history y termina en 'user': el mensaje ya está incluido.

        response = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=200,
            system=system_prompt,
            messages=historia,
        )
        respuesta = response.content[0].text.strip()
        log.info(
            f'[WaBot-IA] {numero} → IA respondió ({len(respuesta)} chars, '
            f'ctx={len(historia)} turnos, estado={session.estado})'
        )

        # Guardia de ciclo: verificar que la sesión no fue reiniciada por el scheduler
        # mientras la IA computaba (puede tardar 2-5 s). Si session_started_at cambió
        # durante ese tiempo, la respuesta fue generada con contexto del ciclo anterior
        # y no debe enviarse al usuario.
        try:
            _fresh_ssa = WaBotSession.query.filter_by(numero=numero).with_entities(
                WaBotSession.session_started_at
            ).scalar()
            _orig_ssa = getattr(session, 'session_started_at', None)
            if _fresh_ssa != _orig_ssa:
                log.info(
                    f'[WaBot-IA] {numero} — session_started_at cambió mientras IA computaba '
                    f'({_orig_ssa} → {_fresh_ssa}); descartando respuesta del ciclo vencido.'
                )
                return None
        except Exception as _ssa_chk_err:
            log.warning(f'[WaBot-IA] No se pudo verificar drift de sesión: {_ssa_chk_err}')

        return respuesta

    except Exception as e:
        log.warning(f'[WaBot-IA] Error generando respuesta IA para {numero}: {e}')
        return None


# ── Horario de atención ────────────────────────────────────────────

def _is_horario_atencion():
    """
    Retorna True si estamos dentro del horario de atención:
      Lun–Vie  09:00 – 18:00
      Sábado   09:00 – 14:00
      Domingo  cerrado
    """
    from app.utils.formatters import now_peru
    now = now_peru()
    day  = now.weekday()   # 0=Lun … 4=Vie, 5=Sáb, 6=Dom
    hour = now.hour
    if 0 <= day <= 4:          # Lun–Vie
        return 9 <= hour < 18
    if day == 5:               # Sábado
        return 9 <= hour < 14
    return False               # Domingo


# Feriados nacionales Perú 2026 (fecha, mes)
_FERIADOS_PE = {
    (1, 1), (9, 4), (10, 4), (1, 5), (29, 6), (28, 7), (29, 7),
    (30, 8), (8, 10), (1, 11), (8, 12), (25, 12),
}


def _next_business_day():
    """
    Retorna un string con el próximo día hábil (lun–vie, no feriado)
    y la hora de apertura. Ejemplo: 'lunes 11 de agosto a las 9:00 AM'
    """
    from app.utils.formatters import now_peru
    from datetime import timedelta
    DIAS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
    MESES = ['', 'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
             'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
    candidate = now_peru().date() + timedelta(days=1)
    for _ in range(14):  # máximo 2 semanas hacia adelante
        wd = candidate.weekday()
        es_feriado = (candidate.day, candidate.month) in _FERIADOS_PE
        if wd < 5 and not es_feriado:  # lun–vie, no feriado
            nombre_dia = DIAS[wd]
            return f'{nombre_dia} {candidate.day} de {MESES[candidate.month]} a las 9:00 AM'
        candidate += timedelta(days=1)
    return 'el próximo día hábil a las 9:00 AM'


def _flujo_fuera_horario(numero):
    """Notifica al cliente que el registro manual requiere horario de atención."""
    send_buttons(numero,
        '🕐 *Fuera de horario*\n\n'
        'El proceso de registro requiere que nuestro equipo esté en línea para verificar tus datos.\n\n'
        '• Lunes a Viernes: *9:00 AM – 6:00 PM*\n'
        '• Sábados: *9:00 AM – 2:00 PM*\n\n'
        'Mientras tanto puedes ver el tipo de cambio o hablar con un asesor 😊',
        [
            {'id': 'btn_cotizar', 'title': '💱 Ver tipo de cambio'},
            {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
        ]
    )


# ── Handler principal ──────────────────────────────────────────────

def _nombre_valido(nombre):
    """Retorna el nombre solo si contiene al menos una letra del alfabeto."""
    if not nombre:
        return ''
    return nombre if re.search(r'[a-zA-ZáéíóúüñÁÉÍÓÚÜÑ]', nombre) else ''


def _typing(numero, wa_id=''):
    """
    Muestra animación de escritura (3 puntos) y marca el mensaje como leído.
    Se llama justo antes de procesar y responder un mensaje entrante.
    """
    import time
    headers = _headers()

    # Llamada combinada: read receipt + typing indicator en un solo request
    if wa_id:
        try:
            requests.post(WA_API_URL, json={
                'messaging_product': 'whatsapp',
                'status': 'read',
                'message_id': wa_id,
                'typing_indicator': {'type': 'text'},
            }, headers=headers, timeout=5)
        except Exception:
            pass
    else:
        # Sin wa_id: solo typing indicator
        try:
            requests.post(WA_API_URL, json={
                'messaging_product': 'whatsapp',
                'recipient_type': 'individual',
                'to': numero.lstrip('+'),
                'type': 'typing_indicator',
                'typing_indicator': {'type': 'text'},
            }, headers=headers, timeout=5)
        except Exception:
            pass

    time.sleep(1.2)  # pausa natural antes de responder


def handle_message(numero, nombre, tipo_msg, texto, media_id='', wa_id=''):
    """
    Punto de entrada desde webhook_receive().
    tipo_msg: 'text' | 'image' | 'document' | 'interactive' | etc.
    texto: cuerpo del mensaje o button_id si es interactive
    """
    try:
        session = WaBotSession.get_or_create(numero)
        nombre = _nombre_valido(nombre)
        if nombre and not session.nombre:
            session.nombre = nombre

        estado = session.estado

        # ── Typing indicator + read receipt ────────────────────────
        _typing(numero, wa_id)

        # ── Bot pausado: asesor atendiendo manualmente ─────────────
        try:
            _bot_pausado = session.bot_pausado
        except Exception:
            _bot_pausado = False
        if _bot_pausado:
            log.info(f'[WaBot] {numero} — bot pausado (asesor activo), mensaje ignorado.')
            db.session.commit()
            return

        # ── Sesión expirada por inactividad (cliente escribe tras 15 min) ──
        # Excepción: si el cliente tiene una operación En proceso, no expirar —
        # el operador puede tardar más de 15 min en depositar los fondos.
        if estado != 'inicio' and _sesion_inactiva(session):
            _op_ep = _operacion_activa_cliente(numero)
            if _op_ep and _op_ep.status == 'En proceso':
                log.info(f'[WaBot] {numero} — sesión inactiva pero op {_op_ep.operation_id} En proceso, no expirar.')
            else:
                log.info(f'[WaBot] {numero} — sesión inactiva ({estado}), reiniciando.')
                _reset_sesion(session)
                # Marcar inicio del nuevo ciclo: igual que el scheduler
                try:
                    from app.utils.formatters import now_peru as _now_inb
                    session.session_started_at = _now_inb()
                except Exception:
                    pass
                db.session.commit()
                estado = 'inicio'

        # ── Verificar expiración de cotización ────────────────────
        if estado == 'viendo_cotizacion' and _cotiz_expirada(session):
            _flujo_cotiz_expirada(numero)
            session.estado = 'inicio'
            db.session.commit()
            return

        # Nota: el mensaje de cierre "¡Fue un placer!" se envía proactivamente
        # por el job de expiración de sesiones (antes de resetear), no aquí.
        # Si el cliente escribe tras una sesión reseteada, recibe bienvenida.

        # ── Botones interactivos ───────────────────────────────────
        btn_id = None  # se sobreescribe en el bloque interactive; evita UnboundLocalError en text
        if tipo_msg == 'interactive':
            btn_id = texto

            # Solo el registro manual requiere horario de atención
            _BTNS_CON_HORARIO = {
                'btn_registro', 'btn_registrarme',
            }
            if btn_id in _BTNS_CON_HORARIO and not _is_horario_atencion():
                _flujo_fuera_horario(numero)

            elif btn_id == 'btn_cotizar':
                _op_activa = _operacion_activa_cliente(numero)
                if _op_activa:
                    _flujo_op_ya_activa(numero, _op_activa)
                else:
                    _flujo_tc_publico(numero)
                    session.estado = 'eligiendo_operacion'

            elif btn_id == 'btn_comprar':
                _op_activa = _operacion_activa_cliente(numero)
                if _op_activa:
                    _flujo_op_ya_activa(numero, _op_activa)
                    session.estado = 'inicio'
                else:
                    session.cotiz_op = 'compra'
                    # Preserve existing importe if already set
                    _continuar_segun_sesion(numero, session)

            elif btn_id == 'btn_vender':
                _op_activa = _operacion_activa_cliente(numero)
                if _op_activa:
                    _flujo_op_ya_activa(numero, _op_activa)
                    session.estado = 'inicio'
                else:
                    session.cotiz_op = 'venta'
                    # Preserve existing importe if already set
                    _continuar_segun_sesion(numero, session)

            elif btn_id.startswith('btn_aceptar_cotiz'):
                # Exact token identity: each quote gets a unique 8-char UUID fragment.
                # btn_id format: 'btn_aceptar_cotiz_{token}'
                _prefix = 'btn_aceptar_cotiz_'
                _token_btn = btn_id[len(_prefix):] if len(btn_id) > len(_prefix) else ''
                _token_ses = getattr(session, 'cotiz_token', None) or ''
                _cotiz_stale = not _token_btn or not _token_ses or _token_btn != _token_ses
                if _cotiz_stale:
                    # Wrong token, no token, or superseded quote — reject silently
                    send_text(numero,
                        'Esta cotización ya fue reemplazada. Acepta la más reciente para continuar.'
                    )
                # Guardia: sesión activa + datos válidos
                elif session.estado != 'viendo_cotizacion' or not (session.cotiz_importe or 0) or not (session.cotiz_tc or 0):
                    send_buttons(numero,
                        '⚠️ Tu cotización ya no está activa. ¿Quieres cotizar de nuevo?',
                        [
                            {'id': 'btn_cotizar', 'title': '💱 Nueva cotización'},
                            {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
                        ]
                    )
                # Si ya tenemos el doc del cliente en sesion, ir directo a cuenta
                elif session.cotiz_doc:
                    client_ac = _buscar_cliente(session.cotiz_doc)
                    if client_ac and client_ac.status == 'Activo':
                        moneda_recibe_ac = 'USD' if session.cotiz_op == 'compra' else 'PEN'
                        cuentas_ac = _cuentas_cliente_por_moneda(client_ac, moneda_recibe_ac)
                        if cuentas_ac:
                            _seleccionar_cuenta_y_continuar(numero, session, client_ac, cuentas_ac, moneda_recibe_ac)
                        else:
                            _flujo_pedir_cuenta_destino(numero, moneda_recibe_ac)
                            session.estado = 'esperando_cuenta_destino'
                    else:
                        send_buttons(numero,
                            '⚠️ No pudimos verificar tu cuenta. Por favor habla con un asesor.',
                            [
                                {'id': 'btn_asesor',       'title': '💬 Hablar con asesor'},
                                {'id': 'btn_volver_inicio', 'title': '🔙 Volver al inicio'},
                            ]
                        )
                        session.estado = 'inicio'
                else:
                    # Intentar identificar por teléfono (P2 phone lookup)
                    _clientes_tel = _buscar_clientes_por_telefono(numero)
                    if len(_clientes_tel) == 1 and _clientes_tel[0].status == 'Activo':
                        _c = _clientes_tel[0]
                        session.cotiz_doc = _c.dni
                        moneda_recibe_ac = 'USD' if session.cotiz_op == 'compra' else 'PEN'
                        cuentas_ac = _cuentas_cliente_por_moneda(_c, moneda_recibe_ac)
                        if cuentas_ac:
                            _seleccionar_cuenta_y_continuar(numero, session, _c, cuentas_ac, moneda_recibe_ac)
                        else:
                            _flujo_pedir_cuenta_destino(numero, moneda_recibe_ac)
                            session.estado = 'esperando_cuenta_destino'
                    elif len(_clientes_tel) > 1:
                        _flujo_elegir_cliente_telefono(numero, _clientes_tel)
                        session.estado = 'eligiendo_cliente_telefono'
                    else:
                        # Cliente desconocido: solicitar documento directamente, sin pregunta intermedia.
                        send_buttons(numero,
                            'Para continuar, ingresa tu *DNI* (8 dígitos) o *RUC* (11 dígitos).\n\n'
                            'Si tienes Carné de Extranjería, elige CE 👇',
                            [
                                {'id': 'btn_tengo_ce',      'title': '🌍 Tengo CE'},
                                {'id': 'btn_volver_cotizar', 'title': '🔙 Volver'},
                            ]
                        )
                        session.estado = 'esperando_id_cotizar'

            elif btn_id.startswith('btn_cliente_') and estado in ('eligiendo_cliente_telefono', 'eligiendo_titular'):
                # P2 — Cliente eligió con qué cuenta operar (múltiples cuentas en mismo teléfono)
                doc_sel = btn_id[len('btn_cliente_'):]
                session.cotiz_doc    = doc_sel
                session.cotiz_cuenta = ''  # limpiar cuenta del perfil anterior
                client_sel = _buscar_cliente(doc_sel)
                if client_sel and (client_sel.kyc_status or '').lower() in ('completo', 'aprobado'):
                    moneda_sel = 'USD' if session.cotiz_op == 'compra' else 'PEN'
                    cuentas_sel = _cuentas_cliente_por_moneda(client_sel, moneda_sel)
                    if cuentas_sel:
                        _seleccionar_cuenta_y_continuar(numero, session, client_sel, cuentas_sel, moneda_sel)
                    else:
                        _flujo_pedir_cuenta_destino(numero, moneda_sel)
                        session.estado = 'esperando_cuenta_destino'
                else:
                    send_text(numero, '⚠️ No encontramos esa cuenta activa. Ingresa tu documento manualmente.')
                    _flujo_pedir_doc_verificacion(numero)
                    session.estado = 'esperando_doc'

            elif btn_id.startswith('btn_titular_') and estado == 'eligiendo_titular':
                # Cliente confirma con qué perfil opera (botón directo o lista desplegable)
                _raw = btn_id[len('btn_titular_'):]
                doc_sel = _raw[len('LIST_'):] if _raw.startswith('LIST_') else _raw
                session.cotiz_doc    = doc_sel
                session.cotiz_cuenta = ''  # limpiar cuenta del perfil anterior
                client_sel = _buscar_cliente(doc_sel)
                if client_sel and client_sel.status == 'Activo':
                    moneda_sel = 'USD' if session.cotiz_op == 'compra' else 'PEN'
                    cuentas_sel = _cuentas_cliente_por_moneda(client_sel, moneda_sel)
                    if cuentas_sel:
                        _seleccionar_cuenta_y_continuar(numero, session, client_sel, cuentas_sel, moneda_sel)
                    else:
                        _flujo_pedir_cuenta_destino(numero, moneda_sel)
                        session.estado = 'esperando_cuenta_destino'
                else:
                    send_buttons(numero,
                        '⚠️ No encontramos esa cuenta activa. Ingresa tu documento manualmente.',
                        [
                            {'id': 'btn_usar_otro_doc', 'title': '🔄 Usar otro documento'},
                            {'id': 'btn_asesor',        'title': '💬 Hablar con asesor'},
                        ]
                    )
                    session.estado = 'esperando_id_cotizar'

            elif btn_id == 'btn_usar_otro_doc':
                # Cliente quiere usar un documento diferente al identificado automáticamente.
                # Limpia el perfil de sesión sin tocar datos del CRM.
                session.cotiz_doc    = ''
                session.cotiz_cuenta = ''
                session.nombre       = ''
                send_buttons(numero,
                    'Ingresa tu *DNI* (8 dígitos) o *RUC* (11 dígitos).\n\n'
                    'Si tienes Carné de Extranjería, elige CE 👇',
                    [
                        {'id': 'btn_tengo_ce',      'title': '🌍 Tengo CE'},
                        {'id': 'btn_volver_cotizar', 'title': '🔙 Volver'},
                    ]
                )
                session.estado = 'esperando_id_cotizar'

            elif btn_id.startswith('btn_cuenta_') and estado == 'eligiendo_cuenta_destino':
                num_ctd = btn_id[len('btn_cuenta_'):]
                client = _buscar_cliente(session.cotiz_doc)
                if client:
                    # Verificar que la cuenta pertenece al titular y validar moneda
                    banco_ctd  = ''
                    _acct_match = None
                    for _acct in (getattr(client, 'bank_accounts', None) or []):
                        if _acct.get('account_number') == num_ctd:
                            banco_ctd   = _acct.get('bank_name', '')
                            _acct_match = _acct
                            break
                    if not _acct_match:
                        # Cuenta no registrada a nombre del titular: botón de otro contexto
                        send_buttons(numero,
                            '⚠️ Esa cuenta no está registrada a tu nombre.\n\n'
                            '¿Quieres usar otra cuenta?',
                            [{'id': 'btn_otra_cuenta', 'title': '🏦 Otra cuenta'}]
                        )
                    else:
                        # Validar moneda: la cuenta debe aceptar la divisa de la operación
                        moneda_recibe = 'USD' if session.cotiz_op == 'compra' else 'PEN'
                        _raw_cur = (_acct_match.get('currency') or '').strip()
                        _acct_cur = _raw_cur.replace('$', 'USD').replace('S/', 'PEN').upper()
                        if _acct_cur and _acct_cur != moneda_recibe:
                            send_buttons(numero,
                                f'⚠️ Esa cuenta está en {_raw_cur or _acct_cur} '
                                f'pero necesitas recibir en {moneda_recibe}.\n\n'
                                '¿Tienes otra cuenta?',
                                [{'id': 'btn_otra_cuenta', 'title': '🏦 Otra cuenta'}]
                            )
                        else:
                            session.cotiz_cuenta = f'{banco_ctd}|{num_ctd}'
                            _flujo_resumen_final(numero, session, client)
                            session.estado = 'confirmando_operacion'
                else:
                    send_text(numero, '⚠️ Error de sesión. Contacta a un asesor: *+51 910 624 404*')
                    session.estado = 'inicio'

            elif btn_id == 'btn_otra_cuenta':
                moneda_recibe = 'USD' if session.cotiz_op == 'compra' else 'PEN'
                _flujo_pedir_cuenta_destino(numero, moneda_recibe)
                session.estado = 'esperando_cuenta_nueva'

            elif btn_id == 'btn_ya_transferi':
                from app.models.operation import Operation as _OpYT
                _op_yt          = None
                _yt_ambiguous   = False  # True → múltiples ops, no elegir ninguna
                _yt_status_info = None   # (op_id, status) cuando P1 halla op no-Pendiente

                # P1 — op referenciada en sesión actual
                if session.cotiz_op_id:
                    _op_yt = _OpYT.query.filter_by(operation_id=session.cotiz_op_id).first()
                    # Si la op existe pero ya no está Pendiente, dar respuesta útil sin reactivar
                    if _op_yt and _op_yt.status != 'Pendiente':
                        _yt_status_info = (_op_yt.operation_id, _op_yt.status)
                        _op_yt = None
                    # Verificar que pertenece al titular de la sesión (previene cross-op)
                    if _op_yt and session.cotiz_doc:
                        _client_yt_ses = _buscar_cliente(session.cotiz_doc)
                        if _client_yt_ses and _op_yt.client_id != _client_yt_ses.id:
                            log.warning(
                                f'[WaBot] btn_ya_transferi: op {session.cotiz_op_id} '
                                f'no pertenece al titular {session.cotiz_doc}'
                            )
                            _op_yt = None

                # P2 — fallback solo cuando sesión expiró y hay titular conocido
                if not _op_yt and session.cotiz_doc:
                    _client_yt_fb = _buscar_cliente(session.cotiz_doc)
                    if _client_yt_fb:
                        _fb_ops = _OpYT.query.filter(
                            _OpYT.client_id == _client_yt_fb.id,
                            _OpYT.status == 'Pendiente',
                        ).order_by(_OpYT.created_at.desc()).all()
                        if len(_fb_ops) == 1:
                            # Única op Pendiente del titular → sin ambigüedad
                            _op_yt = _fb_ops[0]
                            session.cotiz_op_id = _op_yt.operation_id
                            if not session.cotiz_op and hasattr(_op_yt, 'operation_type'):
                                session.cotiz_op = (
                                    _op_yt.operation_type.lower()
                                    if _op_yt.operation_type else 'venta'
                                )
                        elif len(_fb_ops) > 1:
                            _yt_ambiguous = True  # múltiples ops → pedir referencia

                # P3 — fallback sin titular: buscar en TODOS los clientes del teléfono
                #      Solo si hay exactamente una op Pendiente en total (sin ambigüedad)
                if not _op_yt and not _yt_ambiguous and not session.cotiz_doc:
                    try:
                        from app.models.client import Client as _ClientYT
                        _digits_yt  = re.sub(r'\D', '', numero)
                        _local_yt   = _digits_yt[-9:] if len(_digits_yt) >= 9 else _digits_yt
                        _clients_yt = (
                            _ClientYT.query.filter(
                                _ClientYT.phone.ilike(f'%{_local_yt}%')
                            ).all() if _local_yt else []
                        )
                        _all_pending_yt = []
                        for _c_yt in _clients_yt:
                            _pending_yt = _OpYT.query.filter(
                                _OpYT.client_id == _c_yt.id,
                                _OpYT.status == 'Pendiente',
                            ).all()
                            _all_pending_yt.extend(_pending_yt)
                        if len(_all_pending_yt) == 1:
                            _op_yt = _all_pending_yt[0]
                            session.cotiz_op_id = _op_yt.operation_id
                            if not session.cotiz_op and hasattr(_op_yt, 'operation_type'):
                                session.cotiz_op = (
                                    _op_yt.operation_type.lower()
                                    if _op_yt.operation_type else 'venta'
                                )
                        elif len(_all_pending_yt) > 1:
                            _yt_ambiguous = True
                    except Exception as _yt_p3_err:
                        log.warning(f'[WaBot] btn_ya_transferi P3 error {numero}: {_yt_p3_err}')

                # Responder según resultado
                if _yt_ambiguous:
                    # No elegir arbitrariamente — pedir número de operación por texto.
                    # Estado dedicado: evita que el IA procese el texto como mensaje libre
                    # y garantiza que la referencia sea validada antes de proceder.
                    send_buttons(numero,
                        '⚠️ Encontramos varias operaciones pendientes asociadas a tu número.\n\n'
                        'Para registrar tu transferencia, escríbenos el *número de operación* '
                        '(ejemplo: *EXP-001*) que aparece en tu confirmación de cotización, '
                        'o habla con un asesor.',
                        [{'id': 'btn_asesor', 'title': '💬 Hablar con asesor'}]
                    )
                    session.estado = 'esperando_referencia_yt'
                elif _op_yt:
                    _moneda_yt  = 'PEN' if session.cotiz_op == 'compra' else 'USD'
                    _simbolo_yt = 'S/' if _moneda_yt == 'PEN' else 'USD'
                    _monto_yt   = float(_op_yt.amount_pen) if _moneda_yt == 'PEN' else float(_op_yt.amount_usd)
                    _detalle_yt = f'📋 *{_op_yt.operation_id}* · {_simbolo_yt} {_monto_yt:,.2f}\n\n'
                    send_buttons(numero,
                        f'🔢 *¿Cuál es el código de tu transferencia?*\n\n'
                        f'{_detalle_yt}'
                        'Encuéntralo en tu constancia bancaria como '
                        '"N° de operación", "referencia" o "código de transacción".\n\n'
                        'Ejemplo: 12345678',
                        [{'id': f'btn_modificar_importe_{_op_yt.operation_id}', 'title': '🔙 Volver atrás'}]
                    )
                    session.estado = 'esperando_codigo_op'
                elif _yt_status_info:
                    # P1 halló la op referenciada en sesión pero ya no es Pendiente:
                    # responder según estado real sin duplicar ni reactivar la operación.
                    _yt_op_id_s, _yt_st_s = _yt_status_info
                    if _yt_st_s == 'En proceso':
                        send_text(numero,
                            f'✅ Tu operación *{_yt_op_id_s}* ya está *en proceso*.\n\n'
                            'Nuestro equipo la está atendiendo. Te avisaremos cuando esté completada.')
                    elif _yt_st_s == 'Completada':
                        send_buttons(numero,
                            f'✅ La operación *{_yt_op_id_s}* ya fue *procesada exitosamente*.\n\n'
                            '¿Deseas realizar una nueva operación?',
                            [{'id': 'btn_cotizar', 'title': '💱 Nueva cotización'}]
                        )
                    else:
                        send_buttons(numero,
                            f'ℹ️ La operación *{_yt_op_id_s}* tiene estado *{_yt_st_s}* '
                            'y ya no puede recibir pagos.\n\n¿Deseas cotizar de nuevo?',
                            [
                                {'id': 'btn_cotizar', 'title': '💱 Nueva cotización'},
                                {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
                            ]
                        )
                    session.estado = 'inicio'
                else:
                    send_buttons(numero,
                        '⚠️ No encontramos una operación pendiente de pago.\n\n'
                        'Si acabas de transferir, dinos tu código de voucher o habla con un asesor.',
                        [
                            {'id': 'btn_cotizar', 'title': '💱 Nueva cotización'},
                            {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
                        ]
                    )
                    session.estado = 'inicio'

            elif btn_id.startswith('btn_cancelar_operacion'):
                from app.models.operation import Operation as _OpCancel
                # El botón nuevo codifica el op_id: btn_cancelar_operacion_{EXP-XXX}
                # El botón viejo (sin sufijo) no lleva op_id.
                _sfx_cancel = btn_id[len('btn_cancelar_operacion'):]
                _btn_op_id  = _sfx_cancel.lstrip('_') or None  # 'EXP-XXX' o None

                # ── Caso A: botón sin op_id (formato viejo o sin contexto) ──
                if _btn_op_id is None:
                    _cur_op = None
                    if session.cotiz_op_id:
                        _cur_op = _OpCancel.query.filter_by(
                            operation_id=session.cotiz_op_id).first()
                    if _cur_op and _cur_op.status == 'Pendiente':
                        send_buttons(numero,
                            f'Para cancelar la operación *{_cur_op.operation_id}*, '
                            'pulsa el botón de cancelación del mensaje más reciente.',
                            [
                                {'id': f'btn_cancelar_operacion_{_cur_op.operation_id}',
                                 'title': '❌ Cancelar operación'},
                                {'id': 'btn_asesor', 'title': '💬 Hablar con asesor'},
                            ]
                        )
                    else:
                        send_buttons(numero,
                            'No encontramos ninguna operación activa para cancelar.\n\n'
                            '¿En qué más puedo ayudarte?',
                            [
                                {'id': 'btn_cotizar', 'title': '💱 Nueva cotización'},
                                {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
                            ]
                        )

                else:
                    # ── Caso B: botón lleva op_id ──
                    _op_cancel = _OpCancel.query.filter_by(
                        operation_id=_btn_op_id).first()

                    # Si la sesión actual apunta a una operación DISTINTA, no tocar nada.
                    _session_op_id = session.cotiz_op_id or ''
                    if (_session_op_id
                            and _btn_op_id != _session_op_id
                            and _op_cancel):
                        # Botón pertenece a una op diferente de la sesión actual.
                        _cur_op2 = _OpCancel.query.filter_by(
                            operation_id=_session_op_id).first()
                        if _cur_op2 and _cur_op2.status == 'Pendiente':
                            send_buttons(numero,
                                f'⚠️ Ese botón era de una operación anterior.\n\n'
                                f'Tu operación actual es *{_cur_op2.operation_id}*. '
                                'Pulsa el botón de cancelación de la instrucción más reciente si deseas cancelarla.',
                                [
                                    {'id': f'btn_cancelar_operacion_{_cur_op2.operation_id}',
                                     'title': '❌ Cancelar operación actual'},
                                    {'id': 'btn_asesor', 'title': '💬 Hablar con asesor'},
                                ]
                            )
                        else:
                            send_buttons(numero,
                                '⚠️ Ese botón pertenece a una operación que ya no está activa.',
                                [
                                    {'id': 'btn_cotizar', 'title': '💱 Nueva cotización'},
                                    {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
                                ]
                            )

                    elif not _op_cancel:
                        send_buttons(numero,
                            'No encontramos ninguna operación activa para cancelar.\n\n'
                            '¿En qué más puedo ayudarte?',
                            [
                                {'id': 'btn_cotizar', 'title': '💱 Nueva cotización'},
                                {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
                            ]
                        )
                    elif _op_cancel.status == 'Cancelado':
                        send_buttons(numero,
                            f'ℹ️ La operación *{_op_cancel.operation_id}* ya estaba cancelada.\n\n'
                            'No se realizó ningún cobro. ¿Deseas iniciar una nueva cotización?',
                            [
                                {'id': 'btn_cotizar', 'title': '💱 Nueva cotización'},
                                {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
                            ]
                        )
                    elif _op_cancel.status not in ('Pendiente',):
                        send_buttons(numero,
                            f'⚠️ La operación *{_op_cancel.operation_id}* está en estado '
                            f'*{_op_cancel.status}* y no puede cancelarse.\n\n'
                            'Si tienes dudas, habla con un asesor.',
                            [{'id': 'btn_asesor', 'title': '💬 Hablar con asesor'}]
                        )
                    else:
                        # Revalidar bajo lock: estado + pertenencia al cliente + sin depósito.
                        _op_lock = _OpCancel.query.filter_by(
                            id=_op_cancel.id).with_for_update().first()
                        db.session.expire(_op_lock)
                        # Verificar pertenencia al cliente bajo el lock
                        _client_for_check = _buscar_cliente(session.cotiz_doc) if session.cotiz_doc else None
                        _client_id_ok = (
                            _client_for_check is None  # sin doc → no podemos rechazar por cliente
                            or _op_lock.client_id == _client_for_check.id
                        )
                        if not _client_id_ok:
                            send_buttons(numero,
                                '⚠️ Esta operación no corresponde a tu cuenta.',
                                [{'id': 'btn_asesor', 'title': '💬 Hablar con asesor'}]
                            )
                            db.session.commit()
                        elif _op_lock.status != 'Pendiente':
                            send_buttons(numero,
                                f'⚠️ La operación *{_op_lock.operation_id}* ya no está pendiente '
                                f'(estado actual: *{_op_lock.status}*).\n\nSi necesitas ayuda, habla con un asesor.',
                                [{'id': 'btn_asesor', 'title': '💬 Hablar con asesor'}]
                            )
                            db.session.commit()
                        elif _op_lock.client_deposits:
                            send_buttons(numero,
                                f'⚠️ Ya registramos una transferencia para la operación '
                                f'*{_op_lock.operation_id}*.\n\n'
                                'No podemos cancelarla automáticamente. Habla con un asesor para resolverlo.',
                                [{'id': 'btn_asesor', 'title': '💬 Hablar con asesor'}]
                            )
                            db.session.commit()
                        else:
                            _op_lock.status = 'Cancelado'
                            _nota_c = 'Cancelado por el cliente vía WhatsApp bot'
                            _op_lock.notes = ((_op_lock.notes or '') + f'\n\n[BOT] {_nota_c}').strip()
                            db.session.commit()
                            try:
                                from app.services.notification_service import NotificationService as _NSC
                                _NSC.notify_operation_updated(_op_lock, old_status='Pendiente')
                            except Exception:
                                pass
                            send_buttons(numero,
                                f'❌ *Operación {_op_lock.operation_id} cancelada.*\n\n'
                                'No se realizó ningún cobro. Cuando quieras hacer otro cambio, aquí estaremos. 😊',
                                [
                                    {'id': 'btn_cotizar', 'title': '💱 Nueva cotización'},
                                    {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
                                ]
                            )
                            _reset_sesion(session)

            elif btn_id.startswith('btn_modificar_importe'):
                # Validar que el botón corresponde a la operación activa de esta sesión.
                # Formato nuevo: btn_modificar_importe_OPID (embed en generación).
                # Botones sin op_id embebido o con op_id diferente al de la sesión
                # son de un ciclo anterior: se rechazan sin tocar ningún estado.
                _pfx_mod = 'btn_modificar_importe_'
                _embedded_mod_op = btn_id[len(_pfx_mod):] if btn_id.startswith(_pfx_mod) else ''
                _session_op_id   = session.cotiz_op_id or ''
                if not _embedded_mod_op or _embedded_mod_op != _session_op_id:
                    send_buttons(numero,
                        '⏱️ Ese botón ya no corresponde a ninguna operación activa.\n\n'
                        '¿Qué quieres hacer?',
                        [
                            {'id': 'btn_cotizar', 'title': '💱 Cotizar'},
                            {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
                        ]
                    )
                else:
                    _flujo_modificar_importe(numero, session)

            elif btn_id == 'btn_tengo_cuenta':
                _flujo_pedir_doc_verificacion(numero)
                session.estado = 'esperando_doc'

            elif btn_id == 'btn_volver_cotizar':
                _flujo_cotizar_inicio(numero)
                session.estado = 'eligiendo_operacion'

            elif btn_id == 'btn_cambiar_monto':
                # Conservar dirección; solo pedir nuevo importe.
                try:
                    session.cotiz_token = None
                except Exception:
                    pass
                _flujo_pedir_importe(numero, session.cotiz_op or 'venta')
                session.estado = 'esperando_importe'

            elif btn_id == 'btn_mas_opciones':
                # Compatibilidad con mensajes anteriores al rediseño de lista.
                send_list(numero,
                    '¿Qué deseas hacer?',
                    [{
                        'title': 'Opciones',
                        'rows': [
                            {'id': 'btn_cambiar_monto',    'title': 'Cambiar monto'},
                            {'id': 'btn_cambiar_operacion','title': 'Cambiar operación'},
                            {'id': 'btn_cancelar_cotiz',   'title': 'Cancelar cotización'},
                            {'id': 'btn_asesor',           'title': 'Hablar con asesor'},
                        ]
                    }]
                )

            elif btn_id == 'btn_cambiar_operacion':
                # Conservar importe; solo actualizar dirección.
                try:
                    session.cotiz_token = None
                except Exception:
                    pass
                send_list(numero,
                    '¿Qué cambio quieres hacer?',
                    [{'title': 'Dirección', 'rows': [
                        {'id': 'btn_dir_compra', 'title': 'Soles a dólares'},
                        {'id': 'btn_dir_venta',  'title': 'Dólares a soles'},
                    ]}]
                )

            elif btn_id == 'btn_dir_compra':
                session.cotiz_op     = 'compra'
                session.cotiz_cuenta = ''
                try:
                    session.cotiz_token = None
                except Exception:
                    pass
                if (session.cotiz_importe or 0) >= MONTO_MINIMO_USD:
                    _flujo_mostrar_cotizacion(numero, session)
                    session.estado = 'viendo_cotizacion'
                else:
                    _flujo_pedir_importe(numero, 'compra')
                    session.estado = 'esperando_importe'

            elif btn_id == 'btn_dir_venta':
                session.cotiz_op     = 'venta'
                session.cotiz_cuenta = ''
                try:
                    session.cotiz_token = None
                except Exception:
                    pass
                if (session.cotiz_importe or 0) >= MONTO_MINIMO_USD:
                    _flujo_mostrar_cotizacion(numero, session)
                    session.estado = 'viendo_cotizacion'
                else:
                    _flujo_pedir_importe(numero, 'venta')
                    session.estado = 'esperando_importe'

            elif btn_id == 'btn_cancelar_cotiz':
                _reset_sesion(session)
                send_buttons(numero,
                    'Cotización cancelada. ¿Hay algo más en lo que pueda ayudarte?',
                    [
                        {'id': 'btn_cotizar', 'title': '💱 Nueva cotización'},
                        {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
                    ]
                )

            elif btn_id == 'btn_elegir_banco':
                moneda_b = 'USD' if session.cotiz_op == 'compra' else 'PEN'
                send_list(numero,
                    f'¿En qué banco tienes tu cuenta en {"dólares" if moneda_b == "USD" else "soles"}?',
                    [{
                        'title': 'Selecciona tu banco',
                        'rows': [
                            {'id': 'btn_banco_bcp',        'title': 'BCP'},
                            {'id': 'btn_banco_interbank',  'title': 'Interbank'},
                            {'id': 'btn_banco_banbif',     'title': 'BanBif'},
                            {'id': 'btn_banco_bbva',       'title': 'BBVA'},
                            {'id': 'btn_banco_scotiabank', 'title': 'Scotiabank'},
                            {'id': 'btn_banco_pichincha',  'title': 'Pichincha'},
                            {'id': 'btn_banco_otras',      'title': 'Otras entidades'},
                        ]
                    }]
                )

            elif btn_id in ('btn_banco_bcp', 'btn_banco_interbank', 'btn_banco_banbif'):
                _banco_map = {'btn_banco_bcp': 'BCP', 'btn_banco_interbank': 'INTERBANK', 'btn_banco_banbif': 'BANBIF'}
                _banco_sel = _banco_map[btn_id]
                session.cotiz_cuenta = f'{_banco_sel}|'
                send_buttons(numero,
                    f'Escribe tu número de cuenta *{_banco_sel}*:',
                    [{'id': 'btn_asesor', 'title': '💬 Hablar con asesor'}]
                )
                session.estado = 'esperando_num_cuenta'

            elif btn_id in ('btn_banco_bbva', 'btn_banco_scotiabank', 'btn_banco_pichincha', 'btn_banco_otras'):
                _banco_map2 = {'btn_banco_bbva': 'BBVA', 'btn_banco_scotiabank': 'SCOTIABANK',
                               'btn_banco_pichincha': 'PICHINCHA', 'btn_banco_otras': 'OTRO'}
                _banco_sel = _banco_map2[btn_id]
                session.cotiz_cuenta = f'{_banco_sel}|CCI'
                send_buttons(numero,
                    f'Para *{_banco_sel}*, ingresa tu *CCI* (20 dígitos):\n\n'
                    f'Lo encuentras en tu app del banco → Mis cuentas → Datos de cuenta.',
                    [{'id': 'btn_asesor', 'title': '💬 Hablar con asesor'}]
                )
                session.estado = 'esperando_num_cuenta'

            elif btn_id == 'btn_como_funciona':
                _flujo_como_funciona(numero)

            elif btn_id in ('btn_registro', 'btn_registrarme'):
                _flujo_tipo_cliente(numero)
                session.estado = 'eligiendo_tipo'

            elif btn_id == 'btn_asesor':
                _flujo_asesor(numero)
                try:
                    session.bot_pausado = True
                except Exception:
                    pass
                session.estado = 'inicio'

            elif btn_id == 'btn_no_ahora':
                # Cliente canceló el flujo de identificación — respuesta amigable, no bienvenida
                send_buttons(numero,
                    'No hay problema 😊 Cuando quieras cotizar o necesites cambiar divisas, '
                    'aquí estaremos.\n\n'
                    '¿Hay algo más en lo que pueda ayudarte?',
                    [
                        {'id': 'btn_cerrar_sesion', 'title': '🔒 Cerrar sesión'},
                        {'id': 'btn_cotizar',       'title': '💱 Cotizar'},
                        {'id': 'btn_asesor',        'title': '💬 Hablar con asesor'},
                    ]
                )
                session.estado = 'menu_mostrado'

            elif btn_id == 'btn_cerrar_sesion':
                _reset_sesion(session)
                send_text(numero,
                    '¡Hasta luego! 👋 Tu sesión ha sido cerrada.\n\n'
                    'Cuando regreses, escríbenos y estaremos listos para ayudarte.'
                )
                session.estado = 'inicio'

            elif btn_id == 'btn_confirmar_cuenta':
                client = _buscar_cliente(session.cotiz_doc)
                if client:
                    _flujo_resumen_final(numero, session, client)
                    session.estado = 'confirmando_operacion'
                else:
                    send_buttons(numero,
                        '⚠️ Error de sesión. Por favor contacta a un asesor.',
                        [{'id': 'btn_asesor', 'title': '💬 Hablar con asesor'}]
                    )
                    session.estado = 'inicio'

            elif btn_id == 'btn_cambiar_cuenta':
                moneda_recibe = 'USD' if session.cotiz_op == 'compra' else 'PEN'
                session.cotiz_cuenta = ''
                _flujo_pedir_cuenta_destino(numero, moneda_recibe)
                session.estado = 'esperando_cuenta_nueva'

            elif btn_id.startswith('btn_confirmar_operacion'):
                # Crea la operación solo si el resumen presentado sigue vigente.
                # El token en el btn_id (btn_confirmar_operacion_{token}) debe coincidir
                # con session.cotiz_token para garantizar que se confirma exactamente
                # el resumen que el cliente vio (cuenta + TC + importes).
                _sfx_co = btn_id[len('btn_confirmar_operacion'):]
                _co_token = _sfx_co.lstrip('_')            # '' si botón antiguo sin token
                _sesion_token = getattr(session, 'cotiz_token', None) or ''
                if estado != 'confirmando_operacion':
                    send_buttons(numero,
                        '⚠️ El resumen ya no está activo. ¿Quieres cotizar de nuevo?',
                        [
                            {'id': 'btn_cotizar', 'title': '💱 Nueva cotización'},
                            {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
                        ]
                    )
                elif not _co_token or _co_token != _sesion_token:
                    # Token vacío (botón antiguo) o no coincide (resumen reemplazado):
                    # re-mostrar el resumen actual para que el cliente confirme con el botón correcto.
                    _client_stale = _buscar_cliente(session.cotiz_doc)
                    _flujo_resumen_final(numero, session, _client_stale, regenerar_token=False)
                    # estado permanece 'confirmando_operacion'
                else:
                    client_op = _buscar_cliente(session.cotiz_doc)
                    if client_op:
                        _crear_op_y_confirmar(numero, session, client_op, confirm_token=_co_token)
                    else:
                        send_buttons(numero,
                            '⚠️ Error de sesión. Por favor contacta a un asesor.',
                            [{'id': 'btn_asesor', 'title': '💬 Hablar con asesor'}]
                        )
                        session.estado = 'inicio'

            elif btn_id == 'btn_cambiar_cuenta_resumen':
                # Desde el resumen: volver a elegir o ingresar cuenta
                moneda_recibe = 'USD' if session.cotiz_op == 'compra' else 'PEN'
                session.cotiz_cuenta = ''
                client_ccr = _buscar_cliente(session.cotiz_doc)
                if client_ccr:
                    _cuentas_ccr = _cuentas_cliente_por_moneda(client_ccr, moneda_recibe)
                    if _cuentas_ccr:
                        _flujo_elegir_cuenta(numero, _cuentas_ccr, moneda_recibe)
                        session.estado = 'eligiendo_cuenta_destino'
                    else:
                        _flujo_pedir_cuenta_destino(numero, moneda_recibe)
                        session.estado = 'esperando_cuenta_nueva'
                else:
                    _flujo_pedir_cuenta_destino(numero, moneda_recibe)
                    session.estado = 'esperando_cuenta_nueva'

            elif btn_id == 'btn_confirmar_ce':
                send_text(numero, '✍️ Ingresa tu *nombre completo*:')
                session.tipo   = 'natural'
                session.estado = 'esperando_nombre_ce'

            elif btn_id == 'btn_reintentar_doc':
                session.cotiz_doc = ''
                _flujo_pedir_id_para_cotizar(numero)
                session.estado = 'esperando_id_cotizar'

            elif btn_id == 'btn_volver_inicio':
                session.estado      = 'inicio'
                session.tipo        = ''
                session.cotiz_doc   = ''
                session.cotiz_email = ''
                session.dni_front   = ''
                session.dni_back    = ''
                session.ruc_doc     = ''
                _bienvenida(numero, session)

            elif btn_id == 'btn_natural':
                session.tipo = 'natural'
                _flujo_pedir_numero_doc(numero, 'natural')
                session.estado = 'esperando_numero_doc'

            elif btn_id == 'btn_empresa':
                session.tipo = 'empresa'
                _flujo_pedir_numero_doc(numero, 'empresa')
                session.estado = 'esperando_numero_doc'

            elif btn_id == 'btn_tengo_ce':
                send_text(numero,
                    '🌍 Envíanos los *9 dígitos de tu CE* y tus *nombres y apellidos completos* '
                    'tal como aparecen en el documento.\n\n'
                    'Puedes enviarnos ambos juntos o por separado.\n'
                    'Ejemplo: *123456789 Juan Pérez García*'
                )
                session.estado = 'esperando_ce_numero'

            else:
                _menu_rapido(numero)
                session.estado = 'inicio'

        # ── Texto libre ───────────────────────────────────────────
        elif tipo_msg == 'text':
            txt_lower = texto.lower()

            # Solo el registro requiere horario en texto (cotizar y cuenta destino se permiten siempre)
            _ESTADOS_CON_HORARIO = {
                'eligiendo_tipo', 'esperando_numero_doc',
            }

            # N0 — despedida universal: "cierra sesion", "chau", "adios", etc.
            _despedida_kw = ('cierra sesion', 'cierra sesión', 'cerrar sesion', 'cerrar sesión',
                             'chau', 'adios', 'adiós', 'bye bye', 'nos vemos',
                             'hasta mañana', 'hasta manana', 'hasta pronto')
            if any(k in txt_lower for k in _despedida_kw):
                primer_nombre = (session.nombre or '').split()[0].title() if session.nombre else ''
                _reset_sesion(session)
                send_text(numero,
                    f'¡Hasta luego{", " + primer_nombre if primer_nombre else ""}! 👋 '
                    f'Cuando necesites cambiar, aquí estaremos. ¡Que tengas un excelente día!'
                )

            # N1 — "cancelar" universal: cualquier estado activo (excepto inicio)
            elif estado != 'inicio' and any(k in txt_lower for k in ('cancelar', 'salir', 'no gracias', 'stop', 'quiero salir')):
                _reset_sesion(session)
                send_buttons(numero,
                    '✅ Proceso cancelado. ¿Hay algo más en lo que pueda ayudarte?',
                    [
                        {'id': 'btn_cotizar', 'title': '💱 Cotizar'},
                        {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
                    ]
                )

            elif estado in _ESTADOS_CON_HORARIO and not _is_horario_atencion():
                _flujo_fuera_horario(numero)

            elif estado == 'esperando_importe':
                monto = _parse_monto(texto)
                if monto and monto > 0:
                    # Monto válido → resetear contador de intentos
                    try:
                        session.cotiz_intentos = 0
                    except Exception:
                        pass
                    if monto < MONTO_MINIMO_USD:
                        send_text(numero,
                            f'El monto mínimo de operación es *USD {MONTO_MINIMO_USD:,.0f}*.\n\n'
                            f'¿Cuántos dólares deseas cambiar?'
                        )
                    else:
                        session.cotiz_importe = monto
                        # Detect direction change in rich messages (e.g. "Mejor vender 800 dólares")
                        if re.search(r'[a-záéíóúñü]', texto.lower()):
                            try:
                                _interp_imp = _interpretar_solicitud(texto, session)
                                if (_interp_imp.get('tipo')
                                        and _interp_imp['tipo'] != (session.cotiz_op or '')
                                        and _interp_imp.get('fuente') == 'determinista'):
                                    session.cotiz_op = _interp_imp['tipo']
                            except Exception:
                                pass
                        _flujo_mostrar_cotizacion(numero, session)
                        session.estado = 'viendo_cotizacion'
                else:
                    # Sin monto → detectar intención antes de pedir reintento
                    intencion = _detectar_intencion(texto)
                    if intencion == 'cancelar':
                        _reset_sesion(session)
                        send_buttons(numero,
                            'Sin problema, cancelamos la cotización. 😊\n\n'
                            '¿Hay algo más en lo que pueda ayudarte?',
                            [
                                {'id': 'btn_cotizar', 'title': '💱 Cotizar'},
                                {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
                            ]
                        )
                    elif intencion == 'no_tengo':
                        _no_tengo_handler(texto, numero, session)
                    elif intencion == 'asesor':
                        _reset_sesion(session)
                        send_buttons(numero,
                            'Con gusto te conecto con un asesor. 👋',
                            [{'id': 'btn_asesor', 'title': '💬 Hablar con asesor'}]
                        )
                    elif intencion == 'otro':
                        # Pregunta distinta durante el flujo → responder con IA y redirigir
                        respuesta_ia = _respuesta_ia(texto, numero, session, wa_id=wa_id)
                        if respuesta_ia:
                            send_text(numero, respuesta_ia)
                        send_text(numero,
                            'Cuando quieras continuar con la cotización, escribe el monto en dólares. '
                            'Ejemplo: *1000*'
                        )
                        # No reseteamos el estado — el flujo sigue esperando el monto
                    else:
                        # No se entendió el monto → incrementar contador
                        try:
                            session.cotiz_intentos = (session.cotiz_intentos or 0) + 1
                            intentos = session.cotiz_intentos
                        except Exception:
                            intentos = 1

                        if intentos >= 2:
                            send_buttons(numero,
                                '🤔 Parece que hay una dificultad con el monto.\n\n'
                                'Escribe solo el número en dólares, por ejemplo: *1000*\n\n'
                                '¿Prefieres que un asesor te ayude?',
                                [
                                    {'id': 'btn_asesor',        'title': '💬 Hablar con asesor'},
                                    {'id': 'btn_volver_inicio', 'title': '🔙 Volver al inicio'},
                                ]
                            )
                            try:
                                session.cotiz_intentos = 0
                            except Exception:
                                pass
                            session.estado = 'inicio'
                        else:
                            send_text(numero,
                                'No entendí el monto. Escribe solo el número en dólares.\n\n'
                                'Ejemplo: *1000*  o  *2500*  o  *5 mil*'
                            )

            elif estado == 'esperando_identificacion':
                # Flujo nuevo: identificar cliente por DNI/RUC con auto-creación
                doc = texto.strip()
                txt_lower_id = doc.lower()
                # Permitir salir del estado en cualquier momento
                if any(k in txt_lower_id for k in ('cancelar', 'salir', 'no quiero', 'volver', 'inicio', 'exit', 'stop', 'no', 'menu')):
                    _reset_sesion(session)
                    _menu_rapido(numero)
                elif len(re.sub(r'\D', '', doc)) == 9:
                    # 9 dígitos → posible Carné de Extranjería, confirmar con el cliente
                    session.cotiz_doc = doc
                    send_buttons(numero,
                        f'Registramos el número *{doc}* (9 dígitos).\n\n'
                        '¿Es tu *Carné de Extranjería (CE)*? Si te equivocaste puedes reintentar.',
                        [
                            {'id': 'btn_confirmar_ce',   'title': '✍️ Sí, es mi CE'},
                            {'id': 'btn_reintentar_doc', 'title': '🔄 Me equivoqué'},
                        ]
                    )
                    session.estado = 'esperando_confirmar_ce'
                elif _es_dni(doc) or _es_ruc(doc):
                    session.cotiz_doc = doc
                    es_empresa = _es_ruc(doc)
                    client = _buscar_cliente(doc)
                    if client:
                        if client.status == 'Activo':
                            primer_nombre = (client.nombres or client.razon_social or '').split()[0].title()
                            send_text(numero, f'✅ ¡Hola de nuevo, {primer_nombre}! Te identificamos correctamente.')
                            moneda_recibe = 'USD' if session.cotiz_op == 'compra' else 'PEN'
                            cuentas = _cuentas_cliente_por_moneda(client, moneda_recibe)
                            if cuentas:
                                _seleccionar_cuenta_y_continuar(numero, session, client, cuentas, moneda_recibe)
                            else:
                                _flujo_pedir_cuenta_destino(numero, moneda_recibe)
                                session.estado = 'esperando_cuenta_destino'
                        else:
                            send_buttons(numero,
                                '⏳ Encontramos tu cuenta pero aún no está activa.\n\n'
                                'Nuestro equipo la activará pronto. ¿Deseas hablar con un asesor?',
                                [
                                    {'id': 'btn_asesor',       'title': '💬 Hablar con asesor'},
                                    {'id': 'btn_volver_inicio', 'title': '🔙 Volver al inicio'},
                                ]
                            )
                            session.estado = 'inicio'
                    else:
                        # No existe → consultar RENIEC/SUNAT
                        session.cotiz_intentos = 0  # reset contador de intentos
                        send_text(numero, '🔍 Verificando tu documento...')
                        nombre_api = _lookup_ruc(doc) if es_empresa else _lookup_dni(doc)
                        if nombre_api:
                            # Guardar datos para usarlos cuando llegue el email
                            session.nombre = nombre_api
                            session.tipo   = 'empresa' if es_empresa else 'natural'
                            saludo = nombre_api.split()[0].title()
                            send_buttons(numero,
                                f'✅ Verificamos tu documento en {"SUNAT" if es_empresa else "RENIEC"}.\n\n'
                                f'Y para finalizar, coloca tu *correo electrónico*:\n\n'
                                f'Revísalo bien antes de enviarlo.',
                                [
                                    {'id': 'btn_asesor',       'title': '💬 Hablar con asesor'},
                                    {'id': 'btn_volver_inicio', 'title': '🔙 Cancelar'},
                                ]
                            )
                            session.estado = 'esperando_email_registro'
                        else:
                            _intentos = (session.cotiz_intentos or 0) + 1
                            session.cotiz_intentos = _intentos
                            if _intentos >= 3:
                                send_buttons(numero,
                                    f'Hemos intentado verificar *{doc}* varias veces y no lo encontramos en '
                                    f'{"SUNAT" if es_empresa else "RENIEC"}.\n\n'
                                    'Puede que el número tenga un error o no esté registrado. '
                                    'Un asesor puede ayudarte a continuar.',
                                    [
                                        {'id': 'btn_asesor',       'title': '💬 Hablar con asesor'},
                                        {'id': 'btn_volver_inicio', 'title': '← Volver'},
                                    ]
                                )
                            else:
                                _restantes = 3 - _intentos
                                send_buttons(numero,
                                    f'No encontramos el número *{doc}* 🤔\n\n'
                                    f'Revisa que esté bien escrito e ingrésalo de nuevo '
                                    f'({_restantes} intento{"s" if _restantes > 1 else ""} restante{"s" if _restantes > 1 else ""}).',
                                    [{'id': 'btn_volver_inicio', 'title': '← Volver'}]
                                )
                else:
                    send_buttons(numero,
                        '⚠️ Documento no válido.\n\n'
                        'Ingresa un *DNI* (8 dígitos) o *RUC* (11 dígitos).\n'
                        'Ejemplo: *12345678*  |  *20123456789*',
                        [{'id': 'btn_volver_inicio', 'title': '🔙 Cancelar'}]
                    )

            elif estado == 'esperando_email_registro':
                # Recibe email para completar auto-registro
                email_raw = texto.strip().lower()
                if any(k in email_raw for k in ('cancelar', 'salir', 'no quiero', 'volver', 'no', 'exit')):
                    _reset_sesion(session)
                    _menu_rapido(numero)
                elif _es_email(email_raw):
                    doc        = session.cotiz_doc or ''
                    nombre_reg = session.nombre    or ''
                    es_empresa = (session.tipo == 'empresa')
                    try:
                        client = _auto_crear_cliente(doc, nombre_reg, es_empresa, numero, email=email_raw)
                        saludo = (client.razon_social or client.nombres or '').split()[0].title()
                        send_text(numero,
                            f'🎉 ¡Listo, {saludo}! Tu perfil en Qoricash ha sido creado.\n\n'
                            f'Recibirás las confirmaciones de tus operaciones en *{email_raw}*.\n\n'
                            f'Continuemos con tu operación 👇'
                        )
                        _notificar_admins_wa(
                            f'🆕 Cliente auto-registrado vía bot:\n'
                            f'Doc: {doc} | {nombre_reg}\n'
                            f'Email: {email_raw} | Tel: {numero}\n'
                            f'Cotiz: {session.cotiz_op} USD {session.cotiz_importe}'
                        )
                        moneda_recibe = 'USD' if session.cotiz_op == 'compra' else 'PEN'
                        _flujo_pedir_cuenta_destino(numero, moneda_recibe)
                        session.estado = 'esperando_cuenta_destino'
                    except Exception as _e:
                        log.error(f'[WaBot] Error auto-creando cliente {doc}: {_e}')
                        send_buttons(numero,
                            '⚠️ No pudimos completar tu registro. Un asesor te ayudará.',
                            [
                                {'id': 'btn_asesor',       'title': '💬 Hablar con asesor'},
                                {'id': 'btn_volver_inicio', 'title': '🔙 Volver al inicio'},
                            ]
                        )
                        session.estado = 'inicio'
                else:
                    send_buttons(numero,
                        '⚠️ Correo no válido. Verifica que:\n'
                        '• Tenga el formato correcto (ej: *tucorreo@gmail.com*)\n'
                        '• No termine en *.con*, *.cmo* u otro dominio incorrecto\n'
                        '• No sea un correo temporal o de prueba\n\n'
                        'Intenta de nuevo 👇',
                        [{'id': 'btn_volver_inicio', 'title': '🔙 Cancelar'}]
                    )

            elif estado == 'esperando_id_cotizar':
                # Consulta pública de TC: nunca debe bloquear por falta de documento.
                # Si el cliente pregunta el TC mientras está esperando identificación,
                # se responde directamente sin cambiar de estado.
                doc = texto.strip()
                txt_lower_idc = doc.lower()
                _tc_kw_idc = (
                    'cuanto esta', 'cuánto está', 'a cuanto', 'a cuánto',
                    'tipo de cambio', ' tasa', ' tc ', 'precio del dolar',
                    'precio del dólar', 'dolar hoy', 'dólar hoy', 'cuanto cuesta',
                    'cuánto cuesta', 'cotizacion hoy', 'cotización hoy',
                )
                if any(k in txt_lower_idc for k in _tc_kw_idc):
                    _flujo_tc_publico(numero)
                    # Estado no cambia: cuando el cliente quiera continuar, aún pediremos doc
                elif any(k in txt_lower_idc for k in ('cancelar', 'salir', 'no quiero', 'volver', 'inicio', 'exit', 'stop', 'no', 'menu')):
                    _reset_sesion(session)
                    _menu_rapido(numero)
                elif _es_dni(doc) or _es_ruc(doc):
                    session.cotiz_doc = doc
                    es_empresa = _es_ruc(doc)
                    client = _buscar_cliente(doc)
                    if client:
                        if client.status == 'Activo':
                            primer_nombre = (client.nombres or client.razon_social or '').split()[0].title()
                            send_text(numero, f'✅ ¡Hola de nuevo, {primer_nombre}! Te identificamos correctamente.')
                            # Mostrar cotizacion primero; aceptarla lleva a la cuenta destino.
                            _continuar_segun_sesion(numero, session)
                        else:
                            send_buttons(numero,
                                '⏳ Encontramos tu cuenta pero aún no está activa.\n\n'
                                'Nuestro equipo la activará pronto. ¿Deseas hablar con un asesor?',
                                [
                                    {'id': 'btn_asesor',       'title': '💬 Hablar con asesor'},
                                    {'id': 'btn_volver_inicio', 'title': '🔙 Volver al inicio'},
                                ]
                            )
                            session.estado = 'inicio'
                    else:
                        # No existe → consultar RENIEC/SUNAT
                        session.cotiz_intentos = 0  # reset contador de intentos
                        send_text(numero, '🔍 Verificando tu documento...')
                        nombre_api = _lookup_ruc(doc) if es_empresa else _lookup_dni(doc)
                        if nombre_api:
                            session.nombre = nombre_api
                            session.tipo   = 'empresa' if es_empresa else 'natural'
                            send_buttons(numero,
                                f'✅ Verificamos tu documento en {"SUNAT" if es_empresa else "RENIEC"}.\n\n'
                                f'Para finalizar, coloca tu *correo electrónico*:\n\n'
                                f'Revísalo bien antes de enviarlo.',
                                [
                                    {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
                                    {'id': 'btn_no_ahora', 'title': '❌ Cancelar'},
                                ]
                            )
                            session.estado = 'esperando_email_cotizar'
                        else:
                            _intentos = (session.cotiz_intentos or 0) + 1
                            session.cotiz_intentos = _intentos
                            if _intentos >= 3:
                                send_buttons(numero,
                                    f'Hemos intentado verificar *{doc}* varias veces y no lo encontramos en '
                                    f'{"SUNAT" if es_empresa else "RENIEC"}.\n\n'
                                    'Puede que el número tenga un error o no esté registrado. '
                                    'Un asesor puede ayudarte a continuar.',
                                    [
                                        {'id': 'btn_asesor',   'title': '💬 Hablar con asesor'},
                                        {'id': 'btn_no_ahora', 'title': '← Volver'},
                                    ]
                                )
                            else:
                                _restantes = 3 - _intentos
                                send_buttons(numero,
                                    f'No encontramos el número *{doc}* 🤔\n\n'
                                    f'Revisa que esté bien escrito e ingrésalo de nuevo '
                                    f'({_restantes} intento{"s" if _restantes > 1 else ""} restante{"s" if _restantes > 1 else ""}).',
                                    [{'id': 'btn_no_ahora', 'title': '← Volver'}]
                                )
                else:
                    send_buttons(numero,
                        '⚠️ Documento no válido.\n\n'
                        'Ingresa tu *DNI* (8 dígitos), *CE* (9 dígitos) o *RUC* (11 dígitos).\n'
                        'Ejemplo: *12345678* · *123456789* · *20123456789*',
                        [{'id': 'btn_no_ahora', 'title': '❌ Cancelar'}]
                    )



            elif estado == 'esperando_confirmar_ce':
                # Cliente confirmó o rechazó que sus 9 dígitos son CE
                if btn_id == 'btn_confirmar_ce':
                    send_text(numero, '✍️ Ingresa tu *nombre completo*:')
                    session.tipo   = 'natural'
                    session.estado = 'esperando_nombre_ce'
                elif btn_id == 'btn_reintentar_doc':
                    session.cotiz_doc = ''
                    _flujo_pedir_id_para_cotizar(numero)
                    session.estado = 'esperando_id_cotizar'
                else:
                    send_buttons(numero,
                        f'Registramos el número *{session.cotiz_doc}* (9 dígitos).\n\n'
                        '¿Es tu *Carné de Extranjería (CE)*? Si te equivocaste puedes reintentar.',
                        [
                            {'id': 'btn_confirmar_ce',   'title': '✍️ Sí, es mi CE'},
                            {'id': 'btn_reintentar_doc', 'title': '🔄 Me equivoqué'},
                        ]
                    )

            elif estado == 'esperando_ce_numero':
                # Acepta CE solo, nombre solo, o ambos en un mismo mensaje (cualquier orden).
                ce_raw = re.sub(r'\D', '', texto.strip())
                # Extraer nombre: letras y espacios que quedan tras retirar los dígitos
                _nombre_ce_parte = re.sub(r'\d+', '', texto).strip()
                _nombre_ce_parte = re.sub(r'[^a-zA-ZáéíóúüñÁÉÍÓÚÜÑ\s]', '', _nombre_ce_parte).strip()
                _tiene_nombre = len(_nombre_ce_parte) >= 3

                if any(k in texto.lower() for k in ('cancelar', 'salir', 'volver', 'no')):
                    _flujo_cotizar_inicio(numero)
                    session.estado = 'eligiendo_operacion'
                elif ce_raw and len(ce_raw) != 9:
                    send_text(numero,
                        f'⚠️ El CE debe tener exactamente 9 dígitos (recibimos {len(ce_raw)}).\n'
                        'Inténtalo de nuevo:'
                    )
                elif ce_raw and len(ce_raw) == 9:
                    session.cotiz_doc = ce_raw   # preservar ceros iniciales como texto
                    session.tipo = 'natural'
                    if _tiene_nombre:
                        session.nombre = _nombre_ce_parte
                        send_text(numero,
                            f'✅ CE *{ce_raw}* y nombre *{_nombre_ce_parte.title()}* recibidos.\n\n'
                            'Para enviarte las confirmaciones, ingresa tu *correo electrónico*:'
                        )
                        session.estado = 'esperando_email_cotizar'
                    else:
                        send_text(numero, '✍️ Ahora ingresa tu *nombre completo* tal como aparece en el documento:')
                        session.estado = 'esperando_nombre_ce'
                else:
                    # Solo texto (sin dígitos): guardar nombre y pedir número de CE
                    if _tiene_nombre:
                        session.nombre = _nombre_ce_parte
                        send_text(numero,
                            f'✅ Nombre *{_nombre_ce_parte.title()}* guardado.\n\n'
                            'Ahora envíanos los *9 dígitos* de tu Carné de Extranjería:'
                        )
                    else:
                        send_text(numero,
                            '⚠️ No detectamos el número de CE.\n'
                            'Envíanos los *9 dígitos* de tu Carné de Extranjería:'
                        )

            elif estado == 'esperando_nombre_ce':
                # Recibe nombre del titular CE
                nombre_ce = texto.strip()
                if len(nombre_ce) < 3:
                    send_text(numero, '⚠️ Ingresa tu nombre completo (mínimo 3 caracteres).')
                else:
                    session.nombre = nombre_ce
                    send_text(numero,
                        f'✅ Gracias, *{nombre_ce.split()[0].title()}*.\n\n'
                        'Para enviarte las confirmaciones de tus operaciones ingresa tu *correo electrónico*:'
                    )
                    session.estado = 'esperando_email_cotizar'

            elif estado == 'esperando_email_cotizar':
                # Recibe email para nuevo cliente que quiere cotizar
                email_raw = texto.strip().lower()
                if any(k in email_raw for k in ('cancelar', 'salir', 'no quiero', 'volver', 'no', 'exit')):
                    send_buttons(numero,
                        'No hay problema 😊 Cuando quieras cotizar o necesites cambiar divisas, '
                        'aquí estaremos.\n\n'
                        '¿Hay algo más en lo que pueda ayudarte?',
                        [
                            {'id': 'btn_cerrar_sesion', 'title': '🔒 Cerrar sesión'},
                            {'id': 'btn_cotizar',       'title': '💱 Cotizar'},
                            {'id': 'btn_asesor',        'title': '💬 Hablar con asesor'},
                        ]
                    )
                    session.estado = 'menu_mostrado'
                elif _es_email(email_raw):
                    doc        = session.cotiz_doc or ''
                    nombre_reg = session.nombre    or ''
                    es_empresa = (session.tipo == 'empresa')
                    try:
                        client = _auto_crear_cliente(doc, nombre_reg, es_empresa, numero, email=email_raw)
                        saludo = (client.razon_social or client.nombres or '').split()[0].title()
                        send_text(numero,
                            f'🎉 ¡Listo, {saludo}! Tu perfil en Qoricash ha sido creado.\n\n'
                            f'Recibirás las confirmaciones de tus operaciones en *{email_raw}*.\n\n'
                            f'Continuemos con tu operación 👇'
                        )
                        _notificar_admins_wa(
                            f'🆕 Cliente auto-registrado vía bot (cotizar):\n'
                            f'Doc: {doc} | {nombre_reg}\n'
                            f'Email: {email_raw} | Tel: {numero}'
                        )
                        # Continuar directamente a cuenta destino (ya tiene op y monto elegidos)
                        moneda_recibe_ec = 'USD' if session.cotiz_op == 'compra' else 'PEN'
                        _flujo_pedir_cuenta_destino(numero, moneda_recibe_ec)
                        session.estado = 'esperando_cuenta_destino'
                    except Exception as _e:
                        log.error(f'[WaBot] Error auto-creando cliente {doc}: {_e}')
                        send_buttons(numero,
                            '⚠️ No pudimos completar tu registro. Un asesor te ayudará.',
                            [
                                {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
                                {'id': 'btn_no_ahora', 'title': '❌ Cancelar'},
                            ]
                        )
                        session.estado = 'inicio'
                else:
                    send_buttons(numero,
                        '⚠️ Correo no válido. Verifica que:\n'
                        '• Tenga el formato correcto (ej: *tucorreo@gmail.com*)\n'
                        '• No termine en *.con*, *.cmo* u otro dominio incorrecto\n'
                        '• No sea un correo temporal o de prueba\n\n'
                        'Intenta de nuevo 👇',
                        [{'id': 'btn_no_ahora', 'title': '❌ Cancelar'}]
                    )

            elif estado == 'esperando_doc':
                # Verificar DNI/RUC de cliente existente (flujo legacy por teléfono múltiple)
                doc = texto.strip()
                if _es_dni(doc) or _es_ruc(doc):
                    session.cotiz_doc = doc
                    client = _buscar_cliente(doc)
                    if client:
                        if client.status == 'Activo':
                            moneda_recibe = 'USD' if session.cotiz_op == 'compra' else 'PEN'
                            cuentas = _cuentas_cliente_por_moneda(client, moneda_recibe)
                            if cuentas:
                                _seleccionar_cuenta_y_continuar(numero, session, client, cuentas, moneda_recibe)
                            else:
                                session.cotiz_cuenta = ''
                                _flujo_pedir_cuenta_destino(numero, moneda_recibe)
                                session.estado = 'esperando_cuenta_destino'
                        else:
                            _flujo_sin_kyc(numero, (client.kyc_status or '').lower())
                            session.estado = 'inicio'
                    else:
                        # No encontrado → auto-crear igual que en esperando_identificacion
                        es_empresa = _es_ruc(doc)
                        nombre = _lookup_ruc(doc) if es_empresa else _lookup_dni(doc)
                        if nombre:
                            try:
                                client = _auto_crear_cliente(doc, nombre, es_empresa, numero)
                                saludo = (client.razon_social or client.nombres or '').split()[0].title()
                                send_text(numero,
                                    f'✅ ¡Bienvenido, {saludo}! Hemos verificado y creado tu perfil en Qoricash.'
                                )
                                moneda_recibe = 'USD' if session.cotiz_op == 'compra' else 'PEN'
                                _flujo_pedir_cuenta_destino(numero, moneda_recibe)
                                session.estado = 'esperando_cuenta_destino'
                            except Exception as _e:
                                log.error(f'[WaBot] Error auto-creando cliente {doc}: {_e}')
                                _flujo_no_encontrado(numero)
                                session.estado = 'inicio'
                        else:
                            _flujo_no_encontrado(numero)
                            session.estado = 'inicio'
                else:
                    send_text(numero,
                        '⚠️ Documento no válido.\n\n'
                        'Ingresa un *DNI/CE* (8-9 dígitos) o *RUC* (11 dígitos).\n'
                        'Ejemplo: *12345678* (DNI) | *20123456789* (RUC)'
                    )

            elif estado == 'esperando_num_cuenta':
                # Cliente ingresa número de cuenta/CCI tras seleccionar banco en la lista
                _num_raw = re.sub(r'\D', '', texto.strip())
                _stored  = session.cotiz_cuenta or '|'
                _banco_n, _flag = _stored.split('|', 1)
                _necesita_cci   = _flag == 'CCI'
                if _necesita_cci:
                    if len(_num_raw) != 20:
                        send_text(numero,
                            f'⚠️ El CCI debe tener exactamente 20 dígitos.\n'
                            f'Recibimos {len(_num_raw)} dígito{"s" if len(_num_raw) != 1 else ""}. Intenta de nuevo:'
                        )
                    else:
                        session.cotiz_cuenta = f'{_banco_n}|{_num_raw}'
                        _client_nc = _buscar_cliente(session.cotiz_doc)
                        _flujo_resumen_final(numero, session, _client_nc)
                        session.estado = 'confirmando_operacion'
                else:
                    if len(_num_raw) < 6:
                        send_text(numero,
                            f'⚠️ El número de cuenta debe tener al menos 6 dígitos. Intenta de nuevo:'
                        )
                    else:
                        session.cotiz_cuenta = f'{_banco_n}|{_num_raw}'
                        _client_nc = _buscar_cliente(session.cotiz_doc)
                        _flujo_resumen_final(numero, session, _client_nc)
                        session.estado = 'confirmando_operacion'

            elif estado == 'esperando_cuenta_destino':
                # Cliente ingresa "BANCO NUMERO" para cuenta sin registrar
                _raw_cd = texto.strip()
                _raw_cd_u = _raw_cd.upper()
                if _raw_cd_u.startswith('BANCO ') or _raw_cd_u.startswith('BANK '):
                    _raw_cd = _raw_cd.split(None, 1)[1].strip()
                _partes_cd = _raw_cd.split(None, 1)
                if len(_partes_cd) >= 2:
                    _banco_cd, _num_cd = _partes_cd[0].upper(), _partes_cd[1].strip()
                    _digits_cd = re.sub(r'\D', '', _num_cd)
                    if len(_digits_cd) >= 6:
                        session.cotiz_cuenta = f'{_banco_cd}|{_digits_cd}'
                        _client_cd = _buscar_cliente(session.cotiz_doc)
                        _flujo_resumen_final(numero, session, _client_cd)
                        session.estado = 'confirmando_operacion'
                    else:
                        send_text(numero,
                            '⚠️ El número de cuenta debe tener al menos 6 dígitos.\n\n'
                            'Ejemplo: *BCP 1234567890*'
                        )
                else:
                    send_text(numero,
                        'Escribe el *banco* seguido del *número de cuenta*.\n\n'
                        'Ejemplo: *BCP 1234567890*\n'
                        'También: *Interbank 123456789* | *Scotiabank 0123456789*'
                    )

            elif estado == 'esperando_cuenta_nueva':
                # Cliente ingresa "BANCO NUMERO" para una nueva cuenta
                raw_cuenta = texto.strip()
                raw_upper = raw_cuenta.upper()
                if raw_upper.startswith('BANCO ') or raw_upper.startswith('BANK '):
                    raw_cuenta = raw_cuenta.split(None, 1)[1].strip()
                partes = raw_cuenta.split(None, 1)
                if len(partes) >= 2:
                    banco, num = partes[0].upper(), partes[1].strip()
                    num_digits = re.sub(r'\D', '', num)
                    if len(num_digits) >= 6:
                        session.cotiz_cuenta = f'{banco}|{num_digits}'
                        _client_cn = _buscar_cliente(session.cotiz_doc)
                        _flujo_resumen_final(numero, session, _client_cn)
                        session.estado = 'confirmando_operacion'
                    else:
                        send_text(numero,
                            'El número de cuenta debe tener al menos 6 dígitos.\n\n'
                            'Ejemplo: *BCP 1234567890*'
                        )
                else:
                    send_text(numero,
                        'Escribe el banco seguido del número de cuenta.\n\n'
                        'Ejemplo: *BCP 1234567890*\n'
                        'También puedes escribir: *Interbank 123456789*'
                    )

            elif estado == 'esperando_numero_doc':
                # DNI/RUC durante el proceso de registro
                doc = texto.strip()
                esperado = 'DNI/CE (8-9 dígitos)' if session.tipo == 'natural' else 'RUC (11 dígitos)'
                valido = _es_dni(doc) if session.tipo == 'natural' else _es_ruc(doc)
                if valido:
                    session.cotiz_doc = doc
                    # P10 — Feedback inmediato antes del lookup externo (evita silencio)
                    send_text(numero, '🔍 Verificando tu documento...')
                    if session.tipo == 'natural':
                        # Consultar RENIEC solo para DNI (8 dígitos); CE no tiene lookup
                        nombre_reniec = None
                        if len(doc) == 8:
                            nombre_reniec = _lookup_dni(doc)
                            if nombre_reniec:
                                session.nombre = nombre_reniec
                        _flujo_pedir_dni_front(numero, nombre_reniec)
                        session.estado = 'esperando_dni_front'
                    else:
                        # Consultar SUNAT para RUC
                        razon_social = _lookup_ruc(doc)
                        if razon_social:
                            session.nombre = razon_social
                        _flujo_pedir_ruc(numero, razon_social)
                        session.estado = 'esperando_ruc'
                else:
                    send_text(numero,
                        f'⚠️ Documento no válido. Por favor ingresa un *{esperado}* correcto.\n\n'
                        'Ejemplo: *12345678* (DNI) | *12345678901* (RUC)'
                    )

            elif estado == 'esperando_codigo_op':
                codigo = texto.strip()
                codigo_digits = re.sub(r'\D', '', codigo)
                if codigo and len(codigo_digits) >= 4:
                    # T2 — Feedback inmediato antes del lookup
                    send_text(numero, '🔍 Verificando tu código...')
                    _flujo_registrar_codigo_op(numero, codigo, session)
                elif codigo:
                    send_text(numero,
                        '⚠️ El código parece incorrecto. Debe contener al menos 4 dígitos.\n\n'
                        'Encuéntralo en tu constancia bancaria como "N° de operación", '
                        '"referencia" o "código de transacción".\n\n'
                        'Ejemplo: *12345678*'
                    )
                else:
                    send_text(numero, '🔢 Ingresa el código de operación de tu voucher bancario.')

            elif estado == 'esperando_referencia_yt':
                # Cliente debe escribir el número de operación para el caso de múltiples ops.
                # Validar: la referencia debe existir, pertenecer a este teléfono, y ser Pendiente.
                _ref_raw = texto.strip().upper()
                if not _ref_raw:
                    send_text(numero,
                        '🔢 Escribe el *número de operación* (ejemplo: *EXP-001*) '
                        'que aparece en tu confirmación de cotización.')
                else:
                    try:
                        from app.models.operation import Operation as _OpRef
                        # Buscar por id exacto o por sufijo numérico
                        _op_ref = _OpRef.query.filter_by(operation_id=_ref_raw).first()
                        if not _op_ref:
                            _digits_only = re.sub(r'\D', '', _ref_raw)
                            if _digits_only:
                                _op_ref = _OpRef.query.filter(
                                    _OpRef.operation_id.like(f'%{_digits_only}')
                                ).first()

                        if not _op_ref:
                            send_buttons(numero,
                                f'⚠️ No encontramos la operación *{_ref_raw}*.\n\n'
                                'Verifica el número en tu confirmación de cotización '
                                'o habla con un asesor.',
                                [
                                    {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
                                    {'id': 'btn_cotizar', 'title': '💱 Nueva cotización'},
                                ]
                            )
                            session.estado = 'inicio'
                        else:
                            # Verificar que la op pertenece a un cliente de este teléfono
                            from app.models.client import Client as _ClientRef
                            _digs_ref  = re.sub(r'\D', '', numero)
                            _local_ref = _digs_ref[-9:] if len(_digs_ref) >= 9 else _digs_ref
                            _clients_phone = (
                                _ClientRef.query.filter(
                                    _ClientRef.phone.ilike(f'%{_local_ref}%')
                                ).all() if _local_ref else []
                            )
                            _authorized = any(c.id == _op_ref.client_id for c in _clients_phone)
                            # También aceptar si el doc en sesión coincide con el titular
                            if not _authorized and session.cotiz_doc:
                                _c_ses = _buscar_cliente(session.cotiz_doc)
                                if _c_ses and _c_ses.id == _op_ref.client_id:
                                    _authorized = True

                            if not _authorized:
                                # No revelar detalles de ops ajenas
                                send_buttons(numero,
                                    f'⚠️ No encontramos esa operación asociada a tu número.\n\n'
                                    'Si crees que es un error, habla con un asesor.',
                                    [{'id': 'btn_asesor', 'title': '💬 Hablar con asesor'}]
                                )
                                session.estado = 'inicio'
                            elif _op_ref.status == 'Pendiente':
                                session.cotiz_op_id = _op_ref.operation_id
                                _mon_r  = 'PEN' if session.cotiz_op == 'compra' else 'USD'
                                _sim_r  = 'S/' if _mon_r == 'PEN' else 'USD'
                                _amt_r  = float(_op_ref.amount_pen) if _mon_r == 'PEN' else float(_op_ref.amount_usd)
                                send_buttons(numero,
                                    f'🔢 *¿Cuál es el código de tu transferencia?*\n\n'
                                    f'📋 *{_op_ref.operation_id}* · {_sim_r} {_amt_r:,.2f}\n\n'
                                    'Encuéntralo en tu constancia bancaria como '
                                    '"N° de operación", "referencia" o "código de transacción".\n\n'
                                    'Ejemplo: 12345678',
                                    [{'id': f'btn_modificar_importe_{_op_ref.operation_id}', 'title': '🔙 Volver atrás'}]
                                )
                                session.estado = 'esperando_codigo_op'
                            elif _op_ref.status == 'En proceso':
                                send_text(numero,
                                    f'✅ Tu operación *{_op_ref.operation_id}* ya está *en proceso*.\n\n'
                                    'Nuestro equipo la está atendiendo. '
                                    'Te avisaremos cuando esté completada.')
                                session.estado = 'inicio'
                            elif _op_ref.status == 'Completada':
                                send_buttons(numero,
                                    f'✅ La operación *{_op_ref.operation_id}* ya fue *procesada exitosamente*.',
                                    [{'id': 'btn_cotizar', 'title': '💱 Nueva cotización'}]
                                )
                                session.estado = 'inicio'
                            else:
                                send_buttons(numero,
                                    f'ℹ️ La operación *{_op_ref.operation_id}* tiene estado '
                                    f'*{_op_ref.status}* y ya no puede recibir pagos.',
                                    [
                                        {'id': 'btn_cotizar', 'title': '💱 Nueva cotización'},
                                        {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
                                    ]
                                )
                                session.estado = 'inicio'
                    except Exception as _ref_err:
                        log.warning(f'[WaBot] esperando_referencia_yt error {numero}: {_ref_err}')
                        send_buttons(numero,
                            '⚠️ Tuvimos un problema verificando la referencia. '
                            'Habla con un asesor para continuar.',
                            [{'id': 'btn_asesor', 'title': '💬 Hablar con asesor'}]
                        )
                        session.estado = 'inicio'

            elif estado == 'esperando_doc_kyc_titular':
                # Cliente con número de teléfono ambiguo (múltiples registros) debe
                # identificarse con su DNI o RUC antes de asociar el documento enviado.
                _doc_id_raw = texto.strip().upper()
                if not _doc_id_raw:
                    send_text(numero,
                        '✏️ Por favor escribe tu número de *DNI* o *RUC* para que podamos identificarte.')
                else:
                    _c_kyc_id = _buscar_cliente(_doc_id_raw)
                    if _c_kyc_id:
                        session.cotiz_doc = _doc_id_raw
                        send_text(numero,
                            '✅ Identidad verificada. Por favor envía nuevamente el documento '
                            'para que lo asociemos a tu cuenta.')
                    else:
                        send_buttons(numero,
                            '⚠️ No encontramos ese número en nuestro sistema.\n\n'
                            'Verifica que sea correcto o habla con un asesor.',
                            [{'id': 'btn_asesor', 'title': '💬 Hablar con asesor'}]
                        )
                    session.estado = 'inicio'

            elif estado == 'esperando_nuevo_importe':
                nuevo_monto = _parse_monto(texto)
                if not nuevo_monto or nuevo_monto <= 0:
                    intencion = _detectar_intencion(texto)
                    if intencion == 'cancelar':
                        _reset_sesion(session)
                        send_buttons(numero,
                            'Sin problema, cancelamos el cambio de monto. 😊\n\n'
                            '¿Qué quieres hacer?',
                            [
                                {'id': 'btn_cotizar', 'title': '💱 Cotizar'},
                                {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
                            ]
                        )
                    elif intencion == 'asesor':
                        _reset_sesion(session)
                        send_buttons(numero,
                            'Con gusto te conecto con un asesor. 👋',
                            [{'id': 'btn_asesor', 'title': '💬 Hablar con asesor'}]
                        )
                    else:
                        send_text(numero,
                            '⚠️ No entendí el monto. Ingresa solo el número en USD.\n'
                            'Ejemplo: *1500* o *1500.50*'
                        )
                elif nuevo_monto < MONTO_MINIMO_USD:
                    send_text(numero,
                        f'⚠️ El monto mínimo es *USD {MONTO_MINIMO_USD:,.0f}*.\n'
                        f'¿Cuántos USD deseas cambiar?'
                    )
                else:
                    from app.models.operation import Operation
                    from app.services.email_service import EmailService
                    from app.services.notification_service import NotificationService

                    op = Operation.query.filter_by(operation_id=session.cotiz_op_id).first()
                    if not op:
                        send_buttons(numero,
                            '⚠️ No encontramos tu operación. Contacta a un asesor o vuelve a cotizar.',
                            [
                                {'id': 'btn_cotizar', 'title': '💱 Cotizar'},
                                {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
                            ]
                        )
                        session.estado = 'inicio'
                    elif op.status != 'Pendiente':
                        send_text(numero,
                            f'ℹ️ Tu operación *{op.operation_id}* ya está en estado *{op.status}* '
                            f'y no puede modificarse.'
                        )
                        session.estado = 'op_pendiente_pago'
                    else:
                        # Guardar importes anteriores para el email
                        old_usd = float(op.amount_usd)
                        old_pen = float(op.amount_pen)
                        tc      = float(op.exchange_rate)

                        # Calcular nuevos importes con el mismo TC
                        nuevo_usd = round(nuevo_monto, 2)
                        nuevo_pen = round(nuevo_monto * tc, 2)

                        op.amount_usd = nuevo_usd
                        op.amount_pen = nuevo_pen
                        db.session.commit()

                        log.info(
                            f'[WaBot] {numero} modificó importe {op.operation_id}: '
                            f'USD {old_usd} → {nuevo_usd} | PEN {old_pen} → {nuevo_pen}'
                        )

                        # Notificación en tiempo real al sistema web
                        try:
                            NotificationService.notify_operation_updated(op, old_status=op.status)
                        except Exception as _ne:
                            log.warning(f'[WaBot] notify_operation_updated error: {_ne}')

                        # Email automático de modificación de importe
                        try:
                            EmailService.send_amount_modified_operation_email(op, old_usd, old_pen)
                        except Exception as _ee:
                            log.warning(f'[WaBot] email modificación importe error: {_ee}')

                        # Construcción del mensaje de confirmación.
                        moneda_enviar  = 'PEN' if session.cotiz_op == 'compra' else 'USD'
                        _envia_label   = 'S/' if moneda_enviar == 'PEN' else 'USD'
                        _recibe_label  = 'USD' if moneda_enviar == 'PEN' else 'S/'
                        monto_enviar   = nuevo_pen if moneda_enviar == 'PEN' else nuevo_usd
                        _recibe_monto  = nuevo_usd if moneda_enviar == 'PEN' else nuevo_pen

                        # Plazo real desde created_at original; tolerante a naive/aware.
                        from datetime import timedelta as _td3b, timezone as _tz3b
                        from app.utils.formatters import now_peru
                        try:
                            _created = op.created_at
                            _now3b   = now_peru()
                            if _created.tzinfo is None:
                                _created = _created.replace(tzinfo=_tz3b.utc)
                            _expira3b   = _created + _td3b(minutes=15)
                            _restante3b = max(0, int((_expira3b - _now3b).total_seconds() / 60))
                            _hora_lim   = _expira3b.astimezone(_now3b.tzinfo).strftime('%I:%M %p').lstrip('0')
                        except Exception as _pe:
                            log.warning(f'[WaBot] plazo calc error ({op.operation_id}): {_pe}')
                            _restante3b = 0
                            _hora_lim   = '—'

                        _plazo_txt = (
                            f'Transfiere antes de las {_hora_lim}.'
                            if _restante3b > 0 else
                            'Procesaremos mañana al inicio de operaciones.'
                        )

                        msg = (
                            f'✅ *Importe actualizado · {op.operation_id}*\n\n'
                            f'Tú envías: *{_envia_label} {monto_enviar:,.2f}*\n'
                            f'Tú recibes: *{_recibe_label} {_recibe_monto:,.2f}*\n'
                            f'Tipo de cambio: S/ {tc:.4f}\n'
                            f'{_plazo_txt}'
                        )
                        _enviado = send_buttons(numero, msg, [
                            {'id': 'btn_ya_transferi',                          'title': '✅ Ya transferí'},
                            {'id': f'btn_modificar_importe_{op.operation_id}',  'title': '✏️ Modificar importe'},
                            {'id': f'btn_cancelar_operacion_{op.operation_id}', 'title': '❌ Cancelar'},
                        ])
                        if not _enviado:
                            log.error(
                                f'[WaBot] send_buttons falló tras actualizar {op.operation_id}; '
                                'modificación persistida, enviando texto de respaldo'
                            )
                            # Fallback: resumen completo en texto plano para que el cliente
                            # no tenga que enviar otro mensaje.
                            send_text(numero, msg)
                        session.estado = 'op_pendiente_pago'

            elif estado == 'esperando_email':
                email = texto.strip()
                if _es_email(email):
                    session.cotiz_email = email
                    _flujo_confirmar_registro(numero, session)
                    session.estado = 'completado'
                else:
                    send_text(numero,
                        'Ingresa un correo electrónico válido.\nEjemplo: *nombre@correo.com*'
                    )

            elif estado == 'inicio':
                txt_lower = texto.lower()
                if any(k in txt_lower for k in ('hola', 'buenas', 'buenos', 'hi ', 'hey', 'saludos', 'buen dia', 'buen día')):
                    _bienvenida(numero, session)
                    session.estado = 'menu_mostrado'
                elif any(k in txt_lower for k in ('como funciona', 'cómo funciona', 'como opera', 'es seguro', 'es confiable', 'información', 'informacion', 'info', 'cuéntame', 'cuentame')):
                    _flujo_como_funciona(numero)
                elif any(k in txt_lower for k in ('horario', 'hora', 'atienden', 'trabajan', 'abren', 'cierran', 'disponible', 'disponibles')):
                    _flujo_horario(numero)
                elif any(k in txt_lower for k in ('cancelar', 'salir', 'exit', 'stop', 'no gracias',
                                                    'cierra sesion', 'cierra sesión', 'cerrar sesion', 'cerrar sesión',
                                                    'chau', 'adios', 'adiós', 'bye bye', 'hasta pronto', 'nos vemos')):
                    primer_nombre = (session.nombre or '').split()[0].title() if session.nombre else ''
                    send_text(numero,
                        f'¡Hasta luego{", " + primer_nombre if primer_nombre else ""}! 👋 '
                        f'Cuando necesites cambiar, aquí estaremos. ¡Que tengas un excelente día!'
                    )
                elif any(k in txt_lower for k in ('euro', 'eur ', 'libra', 'gbp', 'yuan', 'yen', 'otra moneda')):
                    send_buttons(numero,
                        '💱 Por el momento operamos solo cambio de *USD ↔ PEN* (dólares americanos a soles).\n\n'
                        '¿Deseas cotizar el tipo de cambio dólar / sol?',
                        [
                            {'id': 'btn_cotizar', 'title': '💱 Cotizar USD'},
                            {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
                        ]
                    )
                elif any(k in txt_lower for k in ('registr', 'mi cuenta', 'activar', 'cuándo activan', 'cuando activan', 'estado de mi cuenta')):
                    if session.cotiz_doc:
                        send_buttons(numero,
                            '⏳ Tu solicitud está siendo revisada por nuestro equipo.\n\n'
                            'Te notificaremos por aquí mismo cuando tu cuenta esté activa.',
                            [{'id': 'btn_asesor', 'title': '💬 Hablar con asesor'}]
                        )
                    else:
                        send_buttons(numero,
                            '¡Buenas noticias! El registro es automático al cotizar. 🎉\n\n'
                            'Solo necesitas tu DNI o RUC y te creamos el perfil al instante.',
                            [
                                {'id': 'btn_cotizar', 'title': '💱 Cotizar ahora'},
                                {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
                            ]
                        )
                elif any(k in txt_lower for k in (
                    'cotizar', 'cotizacion', 'cotización', 'tipo de cambio', 'cambio', 'precio',
                    'comprar', 'vender', 'cambiar', 'dólar', 'dolar', 'quiero', 'necesito',
                    'cuanto', 'cuánto', 'tc', 'tasa', 'me interesa', 'saber',
                )):
                    _op_activa_txt = _operacion_activa_cliente(numero)
                    if _op_activa_txt:
                        _flujo_op_ya_activa(numero, _op_activa_txt)
                    else:
                        try:
                            _interp_i = _interpretar_solicitud(texto, session)
                        except Exception as _ei:
                            log.warning(f'[WaBot] Error interpretando solicitud: {_ei}')
                            _interp_i = {'fuente': 'fallo'}
                        _aplicar_interpretacion_pre_op(numero, session, _interp_i)
                else:
                    # Despedida en estado inicio
                    if any(k in txt_lower for k in _despedida_kw):
                        primer_nombre = (session.nombre or '').split()[0].title() if session.nombre else ''
                        send_text(numero,
                            f'¡Hasta luego{", " + primer_nombre if primer_nombre else ""}! 👋 '
                            f'Cuando necesites cambiar, aquí estaremos. ¡Que tengas un excelente día!'
                        )
                    else:
                        # Si tiene operación activa, recordarle antes de mostrar bienvenida
                        _op_activa_txt = _operacion_activa_cliente(numero)
                        if _op_activa_txt:
                            _flujo_op_ya_activa(numero, _op_activa_txt)
                        else:
                            # ── Detectar código tardío ────────────────────────────────
                            # La sesión puede haber expirado mientras la op estaba pendiente.
                            # El cliente llega a 'inicio' y escribe "ya transferí, código 001234".
                            _codigo_tardio_inicio = None
                            _m_tardi = re.search(
                                r'(?:c[oó]digo|cod\.?|referencia|ref\.?|voucher|n[uú]mero)\s*[:\-]?\s*([A-Za-z0-9]{4,20})',
                                texto
                            )
                            if _m_tardi:
                                _codigo_tardio_inicio = _m_tardi.group(1)
                            elif re.match(r'^([A-Za-z0-9]{6,20})$', texto.strip()):
                                _codigo_tardio_inicio = texto.strip()

                            if _codigo_tardio_inicio:
                                try:
                                    from app.models.client import Client as _CliT
                                    from app.models.operation import Operation as _OpTi
                                    from datetime import timedelta as _tdTi
                                    from app.utils.formatters import now_peru as _now_ti
                                    _digs_ti = re.sub(r'\D', '', numero)
                                    _local_ti = _digs_ti[-9:] if len(_digs_ti) >= 9 else _digs_ti
                                    _cli_ti = (_CliT.query
                                               .filter(_CliT.phone.ilike(f'%{_local_ti}%'))
                                               .first()) if _local_ti else None
                                    if _cli_ti:
                                        _cutoff_ti = _now_ti() - _tdTi(hours=2)
                                        _ops_ti = (_OpTi.query
                                                   .filter(
                                                       _OpTi.client_id == _cli_ti.id,
                                                       _OpTi.status.in_(['Cancelado', 'Completado']),
                                                       _OpTi.updated_at >= _cutoff_ti,
                                                   )
                                                   .order_by(_OpTi.updated_at.desc())
                                                   .all())
                                        if len(_ops_ti) == 1:
                                            _op_ti = _ops_ti[0]
                                            try:
                                                _op_ti.notes = ((_op_ti.notes or '')
                                                    + f'\n[WA tardío] Código {_codigo_tardio_inicio} reportado tras cierre de sesión')
                                                db.session.commit()
                                            except Exception:
                                                pass
                                            send_text(numero,
                                                f'Guardamos tu código *{_codigo_tardio_inicio}* relacionado con '
                                                f'la operación *{_op_ti.operation_id}*. '
                                                'Un asesor lo revisará y te confirmará a la brevedad.'
                                            )
                                            _notificar_admins_wa(
                                                f'📋 Código tardío vía WA\n'
                                                f'Cliente: {_cli_ti.full_name}\n'
                                                f'Código:  {_codigo_tardio_inicio}\n'
                                                f'Op:      {_op_ti.operation_id} ({_op_ti.status})\n'
                                                f'Tel:     {numero}'
                                            )
                                        else:
                                            # Ambiguo o sin op reciente → derivar a asesor
                                            _notificar_admins_wa(
                                                f'📋 Código tardío sin op clara\n'
                                                f'Código: {_codigo_tardio_inicio}\n'
                                                f'Tel:    {numero}'
                                            )
                                            send_buttons(numero,
                                                f'Recibimos tu código *{_codigo_tardio_inicio}*. '
                                                'No encontramos una operación reciente con la que asociarlo. '
                                                'Un asesor lo revisará y te contactará.',
                                                [{'id': 'btn_asesor', 'title': '💬 Hablar con asesor'}]
                                            )
                                    else:
                                        _bienvenida(numero, session)
                                except Exception as _et_i:
                                    log.warning(f'[WaBot] Error detectando código tardío en inicio: {_et_i}')
                                    _bienvenida(numero, session)
                            else:
                                # Candidato de importe: número suelto en 'inicio'.
                                # Válido tanto para clientes nuevos como para sesiones
                                # post-expiración.  No afirmar que la sesión expiró —
                                # simplemente confirmar el monto y preguntar dirección.
                                _texto_clean = texto.strip()
                                _es_numero_solo = bool(re.match(r'^[\d\.,\$\s]+(?:mil)?$', _texto_clean, re.IGNORECASE))
                                _monto_candidato = _parse_monto(_texto_clean) if _es_numero_solo else None
                                if _monto_candidato and _monto_candidato > 0:
                                    session.cotiz_importe = _monto_candidato
                                    send_buttons(numero,
                                        f'*{_monto_candidato:,.0f} USD* 👍\n\n¿Quieres comprarlos o venderlos?',
                                        [
                                            {'id': 'btn_comprar', 'title': '🟢 Comprar USD'},
                                            {'id': 'btn_vender',  'title': '🔴 Vender USD'},
                                        ]
                                    )
                                    session.estado = 'eligiendo_operacion'
                                else:
                                    # Texto libre: responder con IA (historial acotado al
                                    # ciclo vigente — ver _historial_ia history_since).
                                    # No enviar _menu_rapido después: genera un segundo
                                    # mensaje contradictorio con la respuesta de la IA.
                                    _ia_resp = _respuesta_ia(texto, numero, session, wa_id=wa_id)
                                    if _ia_resp:
                                        send_text(numero, _ia_resp)
                                    else:
                                        _bienvenida(numero, session)
                                    session.estado = 'menu_mostrado'
                        if session.estado not in ('eligiendo_operacion', 'eligiendo_cliente_telefono'):
                            session.estado = 'menu_mostrado'  # avanza en cualquier caso

            elif estado == 'menu_mostrado':
                # El cliente ya recibió la bienvenida. No re-enviarla; responder con inteligencia.
                txt_lower = texto.lower()
                _entendido = True  # flag para resetear contador si se entiende el mensaje

                if any(k in txt_lower for k in ('hola', 'buenas', 'buenos', 'hi ', 'hey', 'saludos', 'buen dia', 'buen día')):
                    send_buttons(numero,
                        '¡Hola! 👋 ¿En qué te puedo ayudar hoy?',
                        [
                            {'id': 'btn_cotizar',       'title': '💱 Cotizar'},
                            {'id': 'btn_como_funciona', 'title': 'ℹ️ ¿Cómo funciona?'},
                            {'id': 'btn_asesor',        'title': '💬 Hablar con asesor'},
                        ]
                    )
                elif any(k in txt_lower for k in ('ok', 'okey', 'okay', 'entendido', 'gracias', 'listo', 'perfecto', 'bien', 'dale', 'claro', 'de acuerdo')):
                    send_buttons(numero,
                        '😊 ¿Hay algo más en lo que pueda ayudarte?',
                        [
                            {'id': 'btn_cotizar', 'title': '💱 Cotizar'},
                            {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
                        ]
                    )
                elif any(k in txt_lower for k in ('como funciona', 'cómo funciona', 'como opera', 'es seguro', 'es confiable', 'información', 'informacion', 'info', 'cuéntame', 'cuentame')):
                    _flujo_como_funciona(numero)
                elif any(k in txt_lower for k in ('horario', 'hora', 'atienden', 'trabajan', 'abren', 'cierran', 'disponible', 'disponibles')):
                    _flujo_horario(numero)
                elif any(k in txt_lower for k in ('no quiero', 'no me interesa', 'no gracias', 'no tengo', 'salir', 'exit', 'stop', 'cancelar',
                                                    'cierra sesion', 'cierra sesión', 'cerrar sesion', 'cerrar sesión',
                                                    'chau', 'adios', 'adiós', 'bye bye', 'hasta pronto', 'nos vemos')):
                    primer_nombre = (session.nombre or '').split()[0].title() if session.nombre else ''
                    _reset_sesion(session)
                    send_text(numero,
                        f'¡Hasta luego{", " + primer_nombre if primer_nombre else ""}! 👋 '
                        f'Cuando necesites cambiar, aquí estaremos. ¡Que tengas un excelente día!'
                    )
                elif any(k in txt_lower for k in ('euro', 'eur ', 'libra', 'gbp', 'yuan', 'yen', 'otra moneda')):
                    send_buttons(numero,
                        '💱 Por el momento operamos solo cambio de *USD ↔ PEN* (dólares americanos a soles).\n\n'
                        '¿Deseas cotizar el tipo de cambio dólar / sol?',
                        [
                            {'id': 'btn_cotizar', 'title': '💱 Cotizar USD'},
                            {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
                        ]
                    )
                elif any(k in txt_lower for k in (
                    'cotizar', 'cotizacion', 'cotización', 'tipo de cambio', 'cambio', 'precio',
                    'comprar', 'vender', 'cambiar', 'dólar', 'dolar', 'quiero', 'necesito',
                    'cuanto', 'cuánto', 'tc', 'tasa', 'me interesa', 'saber', ' tc ', 'cuánto está', 'cuanto esta',
                )):
                    _op_activa_txt = _operacion_activa_cliente(numero)
                    if _op_activa_txt:
                        _flujo_op_ya_activa(numero, _op_activa_txt)
                    else:
                        try:
                            _interp_m = _interpretar_solicitud(texto, session)
                        except Exception as _em:
                            log.warning(f'[WaBot] Error interpretando solicitud: {_em}')
                            _interp_m = {'fuente': 'fallo'}
                        _aplicar_interpretacion_pre_op(numero, session, _interp_m)
                elif any(k in txt_lower for k in ('asesor', 'ayuda', 'ayúdame', 'ayudame', 'hablar', 'persona', 'humano', 'soporte', 'contacto')):
                    _flujo_asesor(numero)
                    try:
                        session.bot_pausado = True
                    except Exception:
                        pass
                    session.estado = 'inicio'
                elif any(k in txt_lower for k in ('registr', 'mi cuenta', 'activar', 'cuándo activan', 'cuando activan', 'estado de mi cuenta')):
                    if session.cotiz_doc:
                        send_buttons(numero,
                            '⏳ Tu solicitud está siendo revisada por nuestro equipo.\n\n'
                            'Te notificaremos por aquí mismo cuando tu cuenta esté activa.',
                            [{'id': 'btn_asesor', 'title': '💬 Hablar con asesor'}]
                        )
                    else:
                        send_buttons(numero,
                            '¡Buenas noticias! El registro es automático al cotizar. 🎉\n\n'
                            'Solo necesitas tu DNI o RUC y te creamos el perfil al instante.',
                            [
                                {'id': 'btn_cotizar', 'title': '💱 Cotizar ahora'},
                                {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
                            ]
                        )
                else:
                    _entendido = False
                    # Despedida en estado menu_mostrado
                    if any(k in txt_lower for k in _despedida_kw):
                        primer_nombre = (session.nombre or '').split()[0].title() if session.nombre else ''
                        _reset_sesion(session)
                        send_text(numero,
                            f'¡Hasta luego{", " + primer_nombre if primer_nombre else ""}! 👋 '
                            f'Cuando necesites cambiar, aquí estaremos. ¡Que tengas un excelente día!'
                        )
                        _entendido = True
                    else:
                        _op_activa_txt = _operacion_activa_cliente(numero)
                        if _op_activa_txt:
                            _flujo_op_ya_activa(numero, _op_activa_txt)
                        else:
                            # Intentar respuesta con IA primero
                            _ia_resp = _respuesta_ia(texto, numero, session, wa_id=wa_id)
                            if _ia_resp:
                                send_text(numero, _ia_resp)
                                _menu_rapido(numero)
                                _entendido = True  # IA respondió correctamente, resetear contador
                            else:
                                # Contar mensajes no entendidos consecutivamente para evitar loop
                                try:
                                    session.cotiz_intentos = (session.cotiz_intentos or 0) + 1
                                    _no_entendidos = session.cotiz_intentos
                                except Exception:
                                    _no_entendidos = 1

                                if _no_entendidos >= 2:
                                    # Tras 2 mensajes sin entender: derivar a asesor automáticamente
                                    try:
                                        session.cotiz_intentos = 0
                                    except Exception:
                                        pass
                                    send_buttons(numero,
                                        'Parece que no logro entenderte bien. 😊\n\n'
                                        'Te conecto con un asesor para que pueda ayudarte mejor.',
                                        [
                                            {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
                                            {'id': 'btn_cotizar', 'title': '💱 Cotizar'},
                                        ]
                                    )
                                else:
                                    _menu_rapido(numero)

                if _entendido:
                    try:
                        session.cotiz_intentos = 0
                    except Exception:
                        pass

            elif estado in ('esperando_dni_front', 'esperando_dni_back', 'esperando_ruc', 'esperando_email'):
                _flujo_recordatorio_registro(numero, estado)

            else:
                # P1 — Re-enviar el paso donde quedó el cliente según su estado
                if estado == 'eligiendo_operacion':
                    _cancelar_kw = ('cancelar', 'salir', 'exit', 'stop', 'no gracias', 'volver', 'inicio', 'menu')
                    _cotizar_kw  = ('comprar', 'vender', 'compra', 'venta', 'dolares', 'dólares', 'soles', 'cambiar')
                    if any(k in txt_lower for k in _despedida_kw):
                        primer_nombre = (session.nombre or '').split()[0].title() if session.nombre else ''
                        _reset_sesion(session)
                        send_text(numero,
                            f'¡Hasta luego{", " + primer_nombre if primer_nombre else ""}! 👋 '
                            f'Cuando necesites cambiar, aquí estaremos. ¡Que tengas un excelente día!'
                        )
                    elif any(k in txt_lower for k in _cancelar_kw):
                        _reset_sesion(session)
                        _menu_rapido(numero)
                    elif any(k in txt_lower for k in _cotizar_kw):
                        # Interpretation: extract direction/amount from the message
                        try:
                            _interp_e = _interpretar_solicitud(texto, session)
                        except Exception as _ee:
                            log.warning(f'[WaBot] Error interpretando solicitud: {_ee}')
                            _interp_e = {'fuente': 'fallo'}
                        if _interp_e.get('tipo'):
                            session.cotiz_op = _interp_e['tipo']
                        _aplicar_interpretacion_pre_op(numero, session, _interp_e)
                    else:
                        # Pregunta fuera del flujo → intentar IA, si falla re-mostrar botones
                        _ia_resp = _respuesta_ia(texto, numero, session, wa_id=wa_id)
                        if _ia_resp:
                            send_text(numero, _ia_resp)
                            _flujo_cotizar_inicio(numero)
                        else:
                            _flujo_cotizar_inicio(numero)

                elif estado == 'esperando_importe':
                    _flujo_pedir_importe(numero, session.cotiz_op or 'compra')

                elif estado == 'eligiendo_tipo':
                    _flujo_tipo_cliente(numero)

                elif estado == 'eligiendo_cuenta_destino':
                    # B1 — Re-mostrar los botones de selección de cuenta (no pedir cuenta nueva)
                    _moneda_re = 'USD' if session.cotiz_op == 'compra' else 'PEN'
                    _client_re = _buscar_cliente(session.cotiz_doc)
                    if _client_re:
                        _cuentas_re = _cuentas_cliente_por_moneda(_client_re, _moneda_re)
                        if _cuentas_re:
                            _flujo_elegir_cuenta(numero, _cuentas_re, _moneda_re)
                        else:
                            _flujo_pedir_cuenta_destino(numero, _moneda_re)
                            session.estado = 'esperando_cuenta_destino'
                    else:
                        _flujo_pedir_cuenta_destino(numero, _moneda_re)
                        session.estado = 'esperando_cuenta_destino'

                elif estado in ('esperando_cuenta_destino', 'esperando_cuenta_nueva'):
                    moneda = 'USD' if session.cotiz_op == 'compra' else 'PEN'
                    _flujo_pedir_cuenta_destino(numero, moneda)
                    session.estado = 'esperando_cuenta_destino'

                elif estado == 'viendo_cotizacion':
                    _dudas_kw = ('conveniente', 'precio',
                                 'como funciona', 'cómo funciona', 'garantia', 'garantía',
                                 'cuanto', 'cuánto', 'comparar', 'banco', 'diferencia',
                                 'recomend', 'mejor', 'sirve', 'vale la pena')
                    _seguridad_kw = ('es seguro', 'seguro', 'confiable', 'confianza',
                                     'riesgo', 'estafa', 'fraude')
                    _cancelar_kw = ('cancelar', 'salir', 'no gracias', 'volver', 'inicio', 'menu', 'no quiero')
                    if any(k in txt_lower for k in _despedida_kw):
                        primer_nombre = (session.nombre or '').split()[0].title() if session.nombre else ''
                        _reset_sesion(session)
                        send_text(numero,
                            f'¡Hasta luego{", " + primer_nombre if primer_nombre else ""}! 👋 '
                            f'Cuando necesites cambiar, aquí estaremos. ¡Que tengas un excelente día!'
                        )
                    elif any(k in txt_lower for k in _cancelar_kw):
                        _reset_sesion(session)
                        _menu_rapido(numero)
                    else:
                        # Try interpretation BEFORE _dudas_kw ('mejor'/'cuanto' overlap)
                        _interp_v = {'fuente': 'determinista', 'es_correccion': False, 'es_hipotetico': False}
                        try:
                            _interp_v = _interpretar_solicitud(texto, session)
                        except Exception as _ev:
                            log.warning(f'[WaBot] Error interpretando en viendo_cotizacion: {_ev}')
                        # Token for the current quote (used in all accept buttons shown here)
                        _token_v = getattr(session, 'cotiz_token', None) or ''
                        _handled_v = False
                        # [BUG-2A] Direction change: client wants opposite direction.
                        # Must run BEFORE the amount-correction block.
                        # Hypothetical questions ("¿y si cambio X?") must NOT modify the session.
                        if (not _handled_v
                                and _interp_v.get('tipo')
                                and _interp_v['tipo'] != (session.cotiz_op or '')
                                and _interp_v.get('fuente') != 'fallo'
                                and not _interp_v.get('es_hipotetico')):
                            _nuevo_tipo = _interp_v['tipo']
                            session.cotiz_op     = _nuevo_tipo
                            session.cotiz_cuenta = ''   # moneda anterior puede ser incompatible
                            try:
                                session.cotiz_token = None
                            except Exception:
                                pass
                            # Usar nuevo importe si valido; conservar actual si no se indicó.
                            if (_interp_v.get('importe')
                                    and (_interp_v.get('moneda_importe') or 'USD') == 'USD'
                                    and _interp_v['importe'] >= MONTO_MINIMO_USD):
                                session.cotiz_importe = _interp_v['importe']
                            _flujo_mostrar_cotizacion(numero, session)
                            session.estado = 'viendo_cotizacion'
                            _handled_v = True
                        # Correction: explicit amount change -> new quote (invalidates previous acceptance)
                        if (not _handled_v and _interp_v.get('es_correccion')
                                and _interp_v.get('importe')
                                and (_interp_v.get('moneda_importe') or 'USD') == 'USD'):
                            _nuevo_m = _interp_v['importe']
                            if _nuevo_m < MONTO_MINIMO_USD:
                                send_text(numero,
                                    f'El monto mínimo es *USD {MONTO_MINIMO_USD:,.0f}*. ¿Cuántos dólares deseas?'
                                )
                            else:
                                session.cotiz_importe = _nuevo_m
                                _flujo_mostrar_cotizacion(numero, session)
                            _handled_v = True
                        # Hypothetical: informational calculation without modifying session
                        elif (_interp_v.get('es_hipotetico')
                                and _interp_v.get('importe')
                                and (_interp_v.get('moneda_importe') or 'USD') == 'USD'):
                            _imp_hip = _interp_v['importe']
                            _c_h, _v_h = _get_tc()
                            if _c_h and _v_h:
                                _op_h = session.cotiz_op or 'compra'
                                _mej_h = _mejora_tc(_imp_hip)
                                if _op_h == 'compra':
                                    _tc_h  = round(_v_h + SPREAD_TC - _mej_h, 4)
                                    _sol_h = round(_imp_hip * _tc_h, 2)
                                    send_text(numero,
                                        f'💱 *Referencia informativa* (no modifica tu cotización)\n\n'
                                        f'Para USD {_imp_hip:,.2f}: enviarías S/ {_sol_h:,.2f} '
                                        f'(TC S/ {_tc_h:.4f})\n\n'
                                        f'Tu cotización vigente es USD {session.cotiz_importe:,.2f}.'
                                    )
                                else:
                                    _tc_h  = round(_c_h - SPREAD_TC + _mej_h, 4)
                                    _sol_h = round(_imp_hip * _tc_h, 2)
                                    send_text(numero,
                                        f'💱 *Referencia informativa* (no modifica tu cotización)\n\n'
                                        f'Para USD {_imp_hip:,.2f}: recibirías S/ {_sol_h:,.2f} '
                                        f'(TC S/ {_tc_h:.4f})\n\n'
                                        f'Tu cotización vigente es USD {session.cotiz_importe:,.2f}.'
                                    )
                                send_buttons(numero,
                                    '¿Continúas con tu cotización actual?',
                                    [
                                        {'id': f'btn_aceptar_cotiz_{_token_v}', 'title': '✅ Aceptar precio actual'},
                                        {'id': 'btn_volver_cotizar',         'title': '🔄 Nueva cotización'},
                                    ]
                                )
                            _handled_v = True
                        if not _handled_v and any(k in txt_lower for k in _seguridad_kw):
                            send_text(numero,
                                'Qoricash está inscrito en la SBS '
                                'y opera con cuentas propias en el sistema bancario peruano. '
                                'Transferimos únicamente a la cuenta que nos proporciones. '
                                'Puedes verificar nuestros datos en la web de la SBS.'
                            )
                            send_buttons(numero,
                                '¿Continuamos con tu cotización?',
                                [
                                    {'id': f'btn_aceptar_cotiz_{_token_v}', 'title': '✅ Aceptar cotización'},
                                    {'id': 'btn_como_funciona',              'title': 'ℹ️ ¿Cómo funciona?'},
                                ]
                            )
                            _handled_v = True

                        if not _handled_v:
                            if any(k in txt_lower for k in _dudas_kw):
                                send_buttons(numero,
                                    '¿Tienes dudas sobre el tipo de cambio o el proceso? '
                                    'Un asesor puede orientarte de inmediato 😊',
                                    [
                                        {'id': 'btn_asesor',                 'title': '💬 Hablar con asesor'},
                                        {'id': f'btn_aceptar_cotiz_{_token_v}', 'title': '✅ Aceptar precio'},
                                        {'id': 'btn_volver_cotizar',         'title': '🔄 Nueva cotización'},
                                    ]
                                )
                            else:
                                # Texto libre -> IA breve + recordatorio de opciones
                                _ia_resp = _respuesta_ia(texto, numero, session, wa_id=wa_id)
                                if _ia_resp:
                                    send_text(numero, _ia_resp)
                                send_buttons(numero,
                                    '¿Continúas con tu cotización?',
                                    [
                                        {'id': f'btn_aceptar_cotiz_{_token_v}', 'title': '✅ Aceptar precio'},
                                        {'id': 'btn_volver_cotizar',         'title': '🔄 Nueva cotización'},
                                        {'id': 'btn_asesor',                 'title': '💬 Hablar con asesor'},
                                    ]
                                )

                elif estado == 'decidiendo_registro':
                    # P1 — Cliente escribió texto en lugar de usar los botones "¿Ya eres cliente?"
                    _ia_resp = _respuesta_ia(texto, numero, session, wa_id=wa_id)
                    if _ia_resp:
                        send_text(numero, _ia_resp)
                    _flujo_cotiz_aceptada(numero, session)

                elif estado == 'op_pendiente_pago':
                    # Detectar código inline: "código 001234", "ya transferí 001234", etc.
                    _codigo_inline = None
                    _m_codigo = re.search(
                        r'(?:c[oó]digo|cod\.?|operaci[oó]n|referencia|ref\.?|voucher|n[uú]mero)\s*[:\-]?\s*([A-Za-z0-9]{4,20})',
                        txt_lower
                    )
                    if not _m_codigo:
                        # Mensaje que solo contiene un código alfanumérico
                        _m_codigo = re.match(r'^([A-Za-z0-9]{6,20})$', texto.strip())
                    if _m_codigo:
                        _codigo_inline = texto[_m_codigo.start(1):_m_codigo.start(1) + len(_m_codigo.group(1))]
                        # Preservar capitalización original buscando en texto original
                        _raw_match = re.search(
                            r'(?:c[oó]digo|cod\.?|operaci[oó]n|referencia|ref\.?|voucher|n[uú]mero)\s*[:\-]?\s*([A-Za-z0-9]{4,20})',
                            texto
                        )
                        if _raw_match:
                            _codigo_inline = _raw_match.group(1)
                        elif re.match(r'^([A-Za-z0-9]{6,20})$', texto.strip()):
                            _codigo_inline = texto.strip()

                    # Consulta de TC con operación activa: responder sin tocar la operación.
                    _tc_query_kw = (
                        'cuanto esta', 'cuánto está', 'a cuanto', 'a cuánto',
                        'tipo de cambio', 'tasa', ' tc ', 'precio del dolar',
                        'precio del dólar', 'dolar hoy', 'dólar hoy', 'cuanto cuesta',
                        'cuánto cuesta', 'cotizacion hoy', 'cotización hoy',
                    )
                    _es_consulta_tc_op = (
                        not _codigo_inline
                        and any(k in txt_lower for k in _tc_query_kw)
                    )
                    if _es_consulta_tc_op:
                        _c_op, _v_op = _get_tc()
                        if _c_op and _v_op:
                            _tc_op_ses = float(session.cotiz_tc) if session.cotiz_tc else None
                            _tc_resp = (
                                f'💵 *TC vigente*\n'
                                f'› Compramos: S/ {_c_op:.4f}\n'
                                f'› Vendemos:  S/ {_v_op:.4f}'
                            )
                            if _tc_op_ses and abs(_tc_op_ses - _c_op) > 0.0005:
                                _tc_resp += (
                                    f'\n\n_Tu operación usa el TC pactado al cotizar: '
                                    f'S/ {_tc_op_ses:.4f}_'
                                )
                            send_text(numero, _tc_resp)
                        else:
                            send_text(numero, '⚠️ El tipo de cambio no está disponible en este momento.')
                        # Estado no cambia: la operación sigue pendiente
                    elif _codigo_inline:
                        _flujo_registrar_codigo_op(numero, _codigo_inline, session)
                    else:
                        # P1 — Cliente escribió texto libre; recordar qué hacer
                        from app.models.operation import Operation as _Op2
                        op_act = _Op2.query.filter_by(operation_id=session.cotiz_op_id).first() if session.cotiz_op_id else None
                        if op_act and op_act.status == 'Pendiente':
                            moneda_e = 'PEN' if session.cotiz_op == 'compra' else 'USD'
                            simbolo_e = 'S/' if moneda_e == 'PEN' else 'USD'
                            monto_e = float(op_act.amount_pen) if moneda_e == 'PEN' else float(op_act.amount_usd)
                            _cuentas_q = _texto_cuentas_qoricash(moneda_e)
                            _ia_resp = _respuesta_ia(texto, numero, session, wa_id=wa_id)
                            if _ia_resp:
                                send_text(numero, _ia_resp)
                            send_buttons(numero,
                                f'📋 Tu operación *{op_act.operation_id}* sigue pendiente de pago.\n\n'
                                f'Transfiere *{simbolo_e} {monto_e:,.2f}* a:\n\n'
                                f'{_cuentas_q}\n\n'
                                f'Cuando hayas transferido, escríbenos el código de tu voucher o pulsa el botón.',
                                [{'id': 'btn_ya_transferi', 'title': '✅ Ya transferí'}]
                            )
                        else:
                            _bienvenida(numero, session)
                            session.estado = 'inicio'

                elif estado == 'confirmando_operacion':
                    # Cliente escribió texto mientras esperaba confirmar el resumen
                    _client_co = _buscar_cliente(session.cotiz_doc)
                    _flujo_resumen_final(numero, session, _client_co)

                elif estado == 'confirmando_cuenta':
                    # Cliente escribió texto en lugar de usar los botones de confirmación
                    if session.cotiz_cuenta and '|' in session.cotiz_cuenta:
                        _banco_c, _num_c = session.cotiz_cuenta.split('|', 1)
                        _flujo_confirmar_cuenta(numero, _banco_c, _num_c)
                    else:
                        _flujo_pedir_cuenta_destino(numero, 'USD' if session.cotiz_op == 'compra' else 'PEN')
                        session.estado = 'esperando_cuenta_destino'

                elif estado == 'eligiendo_cliente_telefono':
                    # Flujo legacy — redirigir siempre a verificación por documento
                    _flujo_pedir_doc_verificacion(numero)
                    session.estado = 'esperando_doc'

                elif estado == 'completado':
                    send_buttons(numero,
                        '⏳ Tu registro está siendo verificado por nuestro equipo.\n\n'
                        'Te avisaremos por aquí mismo cuando tu cuenta esté activa. '
                        'Si tienes dudas, habla con un asesor.',
                        [{'id': 'btn_asesor', 'title': '💬 Hablar con asesor'}]
                    )

                else:
                    _bienvenida(numero, session)
                    session.estado = 'menu_mostrado'

        # ── Imágenes / documentos ─────────────────────────────────
        elif tipo_msg in ('image', 'document'):
            if estado == 'esperando_dni_front' and media_id:
                session.dni_front = media_id
                _flujo_pedir_dni_back(numero)
                session.estado = 'esperando_dni_back'

            elif estado == 'esperando_dni_back' and media_id:
                session.dni_back = media_id
                _flujo_pedir_email(numero)
                session.estado = 'esperando_email'

            elif estado == 'esperando_ruc' and media_id:
                session.ruc_doc = media_id
                _flujo_pedir_email(numero)
                session.estado = 'esperando_email'

            elif estado == 'completado':
                # C3 — No confundir al cliente; sus docs ya fueron recibidos
                send_buttons(numero,
                    '⏳ Ya recibimos tus documentos. Nuestro equipo los está revisando.\n\n'
                    'No necesitas enviar nada más. Te avisaremos por aquí cuando tu cuenta esté activa.',
                    [{'id': 'btn_asesor', 'title': '💬 Hablar con asesor'}]
                )

            else:
                # E3 — Estado inesperado al recibir imagen/documento
                if estado == 'op_pendiente_pago':
                    send_buttons(numero,
                        '📎 Para registrar tu pago, presiona el botón *"Ya transferí"* e ingresa '
                        'el código de tu voucher bancario (N° de operación o referencia).\n\n'
                        'La foto del comprobante no es necesaria.',
                        [{'id': 'btn_ya_transferi', 'title': '✅ Ya transferí'}]
                    )
                elif estado == 'viendo_cotizacion':
                    _flujo_mostrar_cotizacion(numero, session)
                else:
                    # B7 — Verificar si es cliente registrado enviando documentos KYC
                    _client_kyc_img = None
                    if session.cotiz_doc:
                        _client_kyc_img = _buscar_cliente(session.cotiz_doc)
                    if _client_kyc_img is None:
                        _client_kyc_img = _buscar_cliente_por_tel_cualquier_kyc(numero)

                    if _client_kyc_img:
                        _kyc_img = (_client_kyc_img.kyc_status or 'pendiente').lower()
                        if _kyc_img == 'bloqueado':
                            # Bloqueo administrativo: no aceptar docs; derivar a asesor
                            send_buttons(numero,
                                '🔒 Tu cuenta tiene una restricción administrativa.\n\n'
                                'Para resolverla, comunícate directamente con nuestro equipo.',
                                [{'id': 'btn_asesor', 'title': '💬 Hablar con asesor'}]
                            )
                        elif _kyc_img in ('completo', 'aprobado'):
                            send_buttons(numero,
                                '📎 Recibimos tu archivo, pero no estamos esperando documentos en este momento.\n\n'
                                '¿En qué podemos ayudarte?',
                                [
                                    {'id': 'btn_cotizar', 'title': '💱 Cotizar'},
                                    {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
                                ]
                            )
                        elif _kyc_img == 'en_revision':
                            # Documentos ya recibidos y en revisión: no pedir reenvío
                            send_buttons(numero,
                                '⏳ Ya recibimos tus documentos y nuestro equipo los está revisando.\n\n'
                                'No necesitas enviar nada más. Te notificaremos cuando tu cuenta esté activa.',
                                [{'id': 'btn_asesor', 'title': '💬 Hablar con asesor'}]
                            )
                        else:
                            # pendiente / rechazado — aceptar documento sin auto-aprobar.
                            # El WaMessage entrante ya fue persistido por webhook_receive ANTES
                            # de llegar aquí; el admin puede verlo en el CRM vía /crm/api/media/<id>.
                            # Se descarga y sube a Cloudinary de forma SÍNCRONA para garantizar
                            # que el archivo esté almacenado antes de confirmarle al usuario.
                            if media_id:
                                _doc_marcado   = False   # documents_pending_since establecido
                                _cld_url_kyc   = None    # URL de Cloudinary tras upload exitoso
                                try:
                                    from app.utils.formatters import now_peru as _now_kyc
                                    from app.models.wa_message import WaMessage as _WaMsgKyc

                                    # Verificar si este media_id ya fue procesado (reenvío de webhook)
                                    _existing_kyc = _WaMsgKyc.query.filter_by(media_id=media_id).first()
                                    if _existing_kyc and _existing_kyc.media_local_path:
                                        log.info(f'[KYC] media_id={media_id} ya procesado — ignorando reintento')
                                        send_text(numero,
                                            '📎 Ya registramos ese archivo. Si necesitas enviar otro documento, '
                                            'por favor tómalo nuevamente desde tu cámara o galería.')
                                        return

                                    # Marcar que hay documentos pendientes de revisión en DB
                                    if not _client_kyc_img.documents_pending_since:
                                        _client_kyc_img.documents_pending_since = _now_kyc()
                                    _doc_marcado = True

                                    # Determinar qué cara corresponde al paso actual del flujo.
                                    # La heurística usa el primer campo vacío, pero sólo en
                                    # el sentido front→back: si ya hay URL en front, el siguiente
                                    # paso lógico es back (y así el back no puede repetir el front).
                                    # Si ambos están llenos, el doc es adicional (no avanza KYC).
                                    _doc_type_kyc = (getattr(_client_kyc_img, 'document_type', None) or 'DNI').upper()
                                    if _doc_type_kyc == 'RUC':
                                        _doc_face_kyc = (
                                            'ficha_ruc' if not getattr(_client_kyc_img, 'ficha_ruc_url', None)
                                            else 'additional'
                                        )
                                    else:
                                        if not getattr(_client_kyc_img, 'dni_front_url', None):
                                            _doc_face_kyc = 'front'
                                        elif not getattr(_client_kyc_img, 'dni_back_url', None):
                                            _doc_face_kyc = 'back'
                                        else:
                                            _doc_face_kyc = 'additional'

                                    # Persistencia síncrona: descarga + subida a Cloudinary
                                    _cld_result_kyc = _download_wa_media_to_cloudinary(media_id, _client_kyc_img.id)

                                    if _cld_result_kyc:
                                        _cld_url_kyc  = _cld_result_kyc['url']
                                        _cld_path_kyc = _cld_result_kyc['media_path']
                                        # Guardar URL firmada en el campo del cliente
                                        # (visible en la ficha sin proxy adicional)
                                        if _doc_face_kyc == 'front':
                                            _client_kyc_img.dni_front_url = _cld_url_kyc
                                        elif _doc_face_kyc == 'back':
                                            _client_kyc_img.dni_back_url = _cld_url_kyc
                                        elif _doc_face_kyc == 'ficha_ruc':
                                            _client_kyc_img.ficha_ruc_url = _cld_url_kyc

                                        # Almacenar JSON de metadatos en WaMessage para
                                        # que el proxy del chat genere URL firmada con
                                        # el resource_type real (no 'auto')
                                        _msg_kyc_rec = _WaMsgKyc.query.filter_by(media_id=media_id).first()
                                        if _msg_kyc_rec:
                                            _msg_kyc_rec.media_local_path = _cld_path_kyc

                                        # Flush + commit antes de confirmar al usuario.
                                        # Si commit falla: rollback, log public_id Cloudinary
                                        # para recuperación manual, sin mensaje de éxito.
                                        db.session.flush()
                                        db.session.commit()

                                except Exception as _dp_err:
                                    log.warning(f'[KYC] Error procesando documento {numero}: {_dp_err}')
                                    if _cld_result_kyc:
                                        log.error(
                                            f'[KYC] Upload exitoso pero DB falló — '
                                            f'public_id={_cld_result_kyc["public_id"]} '
                                            f'cliente_id={_client_kyc_img.id} media_id={media_id} — '
                                            f'archivo en Cloudinary disponible para recuperación manual.'
                                        )
                                        try:
                                            db.session.rollback()
                                        except Exception:
                                            pass
                                    _cld_result_kyc = None   # Garantiza que no se confirme éxito
                                    _cld_url_kyc    = None   # Impide que la guardia if _cld_url_kyc confirme

                                log.info(
                                    f'[KYC] {numero} envió doc vía WA '
                                    f'(kyc={_kyc_img} face={_doc_face_kyc if _doc_marcado else "?"} '
                                    f'media_id={media_id} persistido={bool(_cld_result_kyc)} '
                                    f'dni={getattr(_client_kyc_img, "dni", "?")})'
                                )

                                if _doc_marcado:
                                    _nombre_kyc = (
                                        getattr(_client_kyc_img, 'full_name', None)
                                        or getattr(_client_kyc_img, 'razon_social', None)
                                        or getattr(_client_kyc_img, 'dni', numero)
                                    )
                                    _notificar_admins_wa(
                                        f'📄 Documento KYC recibido vía WA\n\n'
                                        f'Cliente: {_nombre_kyc}\n'
                                        f'WA: {numero}\n'
                                        f'Estado KYC previo: {_kyc_img}\n'
                                        f'Almacenado: {"✅ Cloudinary" if _cld_url_kyc else "⚠️ solo Meta (pendiente)"}\n\n'
                                        f'Revisa el chat en el CRM para aprobar o solicitar corrección.'
                                    )
                                    if _cld_url_kyc:
                                        # Mensaje de siguiente paso según la cara guardada
                                        _sig_paso_kyc = ''
                                        if _doc_type_kyc == 'RUC':
                                            if _doc_face_kyc == 'ficha_ruc':
                                                _sig_paso_kyc = '\n\n📋 Si cuentas con el DNI del representante legal, envíalo también.'
                                        else:
                                            if _doc_face_kyc == 'front':
                                                _sig_paso_kyc = '\n\n📷 Ahora envía la *foto del reverso* de tu documento.'
                                            elif _doc_face_kyc == 'back':
                                                _sig_paso_kyc = '\n\nYa tenemos ambas caras de tu documento. Nuestro equipo lo revisará pronto.'
                                        send_buttons(numero,
                                            f'📄 Documento recibido y almacenado.{_sig_paso_kyc}\n\n'
                                            '✅ Nuestro equipo lo revisará y te avisará por este WhatsApp '
                                            'cuando tu cuenta esté habilitada.',
                                            [{'id': 'btn_asesor', 'title': '💬 Hablar con asesor'}]
                                        )
                                    else:
                                        send_buttons(numero,
                                            '📎 Recibimos tu archivo, pero ocurrió un problema al guardarlo.\n\n'
                                            'Por favor envíalo nuevamente o habla con un asesor.',
                                            [{'id': 'btn_asesor', 'title': '💬 Hablar con asesor'}]
                                        )
                                else:
                                    send_buttons(numero,
                                        '📎 Recibimos el archivo, pero tuvimos un problema al registrar tu solicitud.\n\n'
                                        'Por favor habla con un asesor para confirmar.',
                                        [{'id': 'btn_asesor', 'title': '💬 Hablar con asesor'}]
                                    )
                            else:
                                send_buttons(numero,
                                    '📎 No pudimos recibir el archivo. Por favor inténtalo de nuevo.',
                                    [{'id': 'btn_asesor', 'title': '💬 Hablar con asesor'}]
                                )
                    else:
                        # No se identificó un cliente único. Verificar si hay ambigüedad
                        # (varios clientes comparten este teléfono) para pedir aclaración.
                        _kyc_ambiguo = False
                        if not session.cotiz_doc:
                            try:
                                from app.models.client import Client as _ClientAmb
                                _digits_amb = re.sub(r'\D', '', numero)
                                _local_amb  = _digits_amb[-9:] if len(_digits_amb) >= 9 else _digits_amb
                                if _local_amb:
                                    _cnt_amb = _ClientAmb.query.filter(
                                        _ClientAmb.phone.ilike(f'%{_local_amb}%')
                                    ).count()
                                    _kyc_ambiguo = (_cnt_amb > 1)
                            except Exception:
                                pass

                        if _kyc_ambiguo:
                            send_text(numero,
                                '📎 Recibimos tu archivo, pero necesitamos verificar tu identidad.\n\n'
                                '✏️ Por favor escribe tu número de *DNI* o *RUC* para asociar el documento.'
                            )
                            session.estado = 'esperando_doc_kyc_titular'
                        else:
                            send_buttons(numero,
                                '📎 Recibimos tu archivo, pero no estamos esperando documentos en este momento.\n\n'
                                '¿En qué podemos ayudarte?',
                                [
                                    {'id': 'btn_cotizar', 'title': '💱 Cotizar'},
                                    {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
                                ]
                            )

        # ── Cualquier otro tipo (audio, video, ubicación, sticker, etc.) ─────
        else:
            # N2 — En estados de registro, recordar exactamente qué se necesita
            _recordatorios_imagen = {
                'esperando_dni_front': '📷 Necesito la *foto del frente de tu DNI* para continuar. Por favor toma una foto y envíala aquí.',
                'esperando_dni_back':  '📷 Necesito la *foto del reverso de tu DNI* para continuar.',
                'esperando_ruc':       '📄 Necesito la *Ficha RUC de tu empresa* (imagen o PDF). Descárgala en sunat.gob.pe.',
            }
            if estado in _recordatorios_imagen:
                send_text(numero, _recordatorios_imagen[estado])
            elif estado != 'inicio':
                send_text(numero,
                    'Solo puedo procesar texto, fotos y documentos por ahora 😊\n'
                    'Por favor usa las opciones del menú o escribe tu respuesta.'
                )
            else:
                _bienvenida(numero, session)

        db.session.commit()

    except Exception as e:
        log.error(f'[WaBot] Error en handle_message {numero}: {e}')
        try:
            db.session.rollback()
        except Exception:
            pass
