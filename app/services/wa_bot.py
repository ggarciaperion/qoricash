"""
WaBot — Chatbot de WhatsApp para Qoricash
Flujo: Bienvenida → Cotizar / Registrarme / Hablar con asesor
"""
import os, re, logging, requests
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


def send_template(numero, template_name, lang_code, params):
    """
    Envía una plantilla aprobada por Meta.
    params: lista de strings con los valores de cada variable {{1}}, {{2}}...
    Funciona aunque el cliente nunca haya escrito al bot (sin ventana de 24h).
    """
    payload = {
        'messaging_product': 'whatsapp',
        'to': numero.lstrip('+'),
        'type': 'template',
        'template': {
            'name': template_name,
            'language': {'code': lang_code},
            'components': [{
                'type': 'body',
                'parameters': [{'type': 'text', 'text': str(p)} for p in params]
            }]
        }
    }
    try:
        r = requests.post(WA_API_URL, json=payload, headers=_headers(), timeout=10)
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
        return
    phone_raw = (getattr(client, 'phone', None) or '').split(';')[0].strip()
    phone_digits = ''.join(c for c in phone_raw if c.isdigit())
    if not phone_digits:
        return
    if not phone_digits.startswith('51'):
        phone_digits = '51' + phone_digits
    send_template(phone_digits, 'qoricash_operacion_completada', 'es', [op_id, titular, email_txt])


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
    except Exception as e:
        log.error(f'[WaBot] Error send_text a {numero}: {e}')


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
    except Exception as e:
        log.error(f'[WaBot] Error send_buttons a {numero}: {e}')


def send_list(numero, body, sections):
    payload = {
        'messaging_product': 'whatsapp',
        'to': numero.lstrip('+'),
        'type': 'interactive',
        'interactive': {
            'type': 'list',
            'body': {'text': body},
            'action': {
                'button': 'Ver opciones',
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


# ── Flujos del bot ─────────────────────────────────────────────────

def _bienvenida(numero, nombre):
    primer_nombre = nombre.split()[0] if nombre else ''
    saludo = f'Hola {primer_nombre} 👋' if primer_nombre else 'Hola 👋'
    base_compra, base_venta = _get_tc()
    # Aplicar spread igual que en la cotización:
    # compra (bot compra USD del cliente) = base_compra - SPREAD_TC
    # venta  (bot vende USD al cliente)   = base_venta  + SPREAD_TC
    compra = round(base_compra - SPREAD_TC, 3) if base_compra else 0
    venta  = round(base_venta  + SPREAD_TC, 3) if base_venta  else 0
    tc_texto = (
        f'💱 *Tipo de cambio ahora:*\n'
        f'  • Compra: S/ {compra:.3f}\n'
        f'  • Venta:  S/ {venta:.3f}'
    ) if compra else ''

    msg = (
        f'{saludo} Bienvenido a *Qoricash* 🏦\n'
        'Casa de cambio digital — rápida, segura y regulada por la SBS.\n\n'
        f'{tc_texto}\n\n'
        '⭐ _Tasa preferencial para importes mayores a $3,000 USD_'
    ).strip()

    send_buttons(numero, msg, [
        {'id': 'btn_cotizar',  'title': '💱 Cotizar'},
        {'id': 'btn_registro', 'title': '📝 Registrarme'},
        {'id': 'btn_asesor',   'title': '💬 Hablar con asesor'},
    ])


def _flujo_cotizar_inicio(numero):
    """Pregunta si el cliente desea comprar o vender dólares."""
    send_buttons(numero,
        '¿Qué operación deseas realizar?',
        [
            {'id': 'btn_comprar', 'title': '🟢 Comprar dólares'},
            {'id': 'btn_vender',  'title': '🔵 Vender dólares'},
        ]
    )


def _flujo_pedir_importe(numero, operacion):
    """Solicita el importe en USD."""
    op_texto = 'comprar' if operacion == 'compra' else 'vender'
    send_text(numero,
        f'¿Cuántos dólares deseas {op_texto}?\n\n'
        f'Escribe el monto en USD. Ejemplo: *1000*\n'
        f'_(Mínimo: USD {MONTO_MINIMO_USD:,.0f})_'
    )


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
            f'💵 *Cotización — Compra de dólares*\n\n'
            f'  Envías:         *S/ {soles:,.2f}*\n'
            f'  Tipo de cambio: *S/ {tc_final:.4f}*\n'
            f'  Recibes:        *USD {importe:,.2f}*'
        )
    else:
        # Cliente vende dólares → empresa le compra → usa TC compra - spread
        tc_base  = round(compra - SPREAD_TC, 4)
        tc_final = round(tc_base + mejora, 4)
        soles    = round(importe * tc_final, 2)
        resumen  = (
            f'💵 *Cotización — Venta de dólares*\n\n'
            f'  Envías:         *USD {importe:,.2f}*\n'
            f'  Tipo de cambio: *S/ {tc_final:.4f}*\n'
            f'  Recibes:        *S/ {soles:,.2f}*'
        )

    if mejora > 0:
        resumen += f'\n\n  ✨ _TC preferencial por monto especial_'

    resumen += f'\n\n  ⏱ _Válido hasta las {expira_hora}_'

    session.cotiz_tc = tc_final

    send_buttons(numero, resumen, [
        {'id': 'btn_aceptar_cotiz',  'title': '✅ Aceptar'},
        {'id': 'btn_volver_cotizar', 'title': '🔄 Volver a cotizar'},
        {'id': 'btn_asesor',         'title': '💬 Hablar con asesor'},
    ])


def _menu_rapido(numero):
    """Menú de opciones sin el saludo de bienvenida (para clientes que ya fueron bienvenidos)."""
    send_buttons(numero,
        '¿En qué te podemos ayudar?',
        [
            {'id': 'btn_cotizar',  'title': '💱 Cotizar'},
            {'id': 'btn_registro', 'title': '📝 Registrarme'},
            {'id': 'btn_asesor',   'title': '💬 Hablar con asesor'},
        ]
    )


def _flujo_como_funciona(numero):
    """Explica el proceso de cambio y destaca seguridad / regulación SBS."""
    msg = (
        '🏦 *¿Cómo funciona Qoricash?*\n\n'
        '1️⃣ *Cotiza* — Ingresa el monto y obtén el tipo de cambio en tiempo real, sin compromisos.\n\n'
        '2️⃣ *Transfiere* — Realiza la transferencia bancaria a nuestra cuenta y compártenos el código de operación.\n\n'
        '3️⃣ *Recibe* — Verificamos tu pago y depositamos los fondos en tu cuenta en minutos.\n\n'
        '🛡️ *Tu seguridad es nuestra prioridad #1.*\n'
        'Somos una fintech 100% regulada y supervisada por la *Superintendencia de Banca, Seguros y AFP (SBS)*.\n'
        '📋 Res. N.° 00313-2026\n\n'
        '🕐 Atención: lunes a viernes de 9:00 AM a 6:00 PM.\n\n'
        '¿Deseas comenzar ahora?'
    )
    send_buttons(numero, msg, [
        {'id': 'btn_cotizar',  'title': '💱 Cotizar ahora'},
        {'id': 'btn_registro', 'title': '📝 Registrarme'},
        {'id': 'btn_asesor',   'title': '💬 Hablar con asesor'},
    ])


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
    send_buttons(numero,
        '⏰ Tu sesión ha expirado por inactividad.\n\n'
        'Cuando desees volver a operar, escríbenos y comenzamos de nuevo.',
        [{'id': 'btn_asesor', 'title': '💬 Hablar con asesor'}]
    )


def _reset_sesion(session):
    """Limpia todos los datos de la sesión y la devuelve a inicio."""
    session.estado        = 'inicio'
    session.cotiz_op      = ''
    session.cotiz_importe = 0.0
    session.cotiz_tc      = 0.0
    session.cotiz_doc     = ''
    session.cotiz_email   = ''
    session.cotiz_op_id   = ''
    session.cotiz_cuenta  = ''
    session.tipo          = ''


def _sesion_inactiva(session):
    """Retorna True si la sesión lleva más de SESSION_INACTIVIDAD_MIN sin actividad."""
    from datetime import timedelta
    from app.utils.formatters import now_peru
    if not session.updated_at:
        return False
    return (now_peru() - session.updated_at) > timedelta(minutes=SESSION_INACTIVIDAD_MIN)


def _flujo_cotiz_aceptada(numero, session):
    """Cliente aceptó el precio — verificar si tiene cuenta."""
    log.info(f'[WaBot] {numero} aceptó cotización: {session.cotiz_op} USD {session.cotiz_importe} a S/ {session.cotiz_tc}')
    send_buttons(numero,
        '✅ *¡Precio aceptado!*\n\n¿Ya eres cliente en Qoricash?',
        [
            {'id': 'btn_tengo_cuenta', 'title': '✅ Sí, soy cliente'},
            {'id': 'btn_registrarme',  'title': '📝 No, quiero registrarme'},
        ]
    )


def _flujo_pedir_doc_verificacion(numero):
    send_text(numero,
        '🔎 Ingresa tu *DNI/CE* (8-9 dígitos) o *RUC* (11 dígitos) para verificar tu cuenta:'
    )


def _es_dni(t):
    """DNI peruano (8 dígitos) o Carnet de Extranjería (9 dígitos)."""
    return bool(re.match(r'^\d{8,9}$', t.strip()))


def _es_ruc(t):
    return bool(re.match(r'^\d{11}$', t.strip()))


def _es_email(t):
    return bool(re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', t.strip()))


def _buscar_cliente(doc):
    """Busca un cliente por DNI o RUC."""
    try:
        from app.models.client import Client
        doc = doc.strip()
        return Client.query.filter_by(dni=doc).first()
    except Exception as e:
        log.warning(f'[WaBot] Error buscando cliente {doc}: {e}')
        return None


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


def _flujo_elegir_cliente_telefono(numero, clientes):
    """
    Cuando un número de WA tiene múltiples cuentas aprobadas (ej: personal + empresa),
    muestra botones para que el usuario elija con cuál operar.
    """
    botones = []
    for c in clientes[:2]:
        nombre = (c.full_name or c.razon_social or c.dni or 'Cliente').strip()
        titulo = nombre[:20]
        botones.append({'id': f'btn_cliente_{c.dni}', 'title': titulo})
    botones.append({'id': 'btn_tengo_cuenta', 'title': '🔎 Ingresar DNI/RUC'})
    send_buttons(numero,
        '¿Con cuál de tus cuentas deseas realizar la operación?',
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

    # Enviar email de confirmación igual que las operaciones creadas por otros canales
    try:
        from app.services.email_service import EmailService
        EmailService.send_new_operation_email(op)
    except Exception as _email_err:
        log.warning(f'[WaBot] No se pudo enviar email nueva op {op.operation_id}: {_email_err}')

    return op


def _flujo_op_creada(numero, op, session, client):
    """Envía confirmación de operación creada con datos de transferencia y solicita código."""
    moneda_enviar = 'PEN' if session.cotiz_op == 'compra' else 'USD'
    simbolo       = 'S/' if moneda_enviar == 'PEN' else 'USD'
    monto_enviar  = float(op.amount_pen) if moneda_enviar == 'PEN' else float(op.amount_usd)
    titular       = (client.full_name or '').title() if client else ''

    cuentas = _texto_cuentas_qoricash(moneda_enviar)

    msg = (
        f'✅ *Operación creada exitosamente*\n'
        f'📋 *Nro:* {op.operation_id}\n'
        + (f'👤 *Titular:* {titular}\n' if titular else '')
        + f'\n'
        f'Tienes *15 minutos* para realizar la transferencia, de lo contrario se cancelará automáticamente.\n\n'
        f'*Transfiere {simbolo} {monto_enviar:,.2f} a:*\n\n'
        f'{cuentas}\n\n'
        f'_Una vez transferido, presiona el botón y te pediremos el código de tu voucher (número de 8 a 12 dígitos que aparece en tu constancia bancaria)._'
    )
    send_buttons(numero, msg, [
        {'id': 'btn_ya_transferi', 'title': '✅ Ya transferí'},
    ])


def _flujo_registrar_codigo_op(numero, codigo, session):
    """Registra el código de operación bancaria del cliente y pasa la op a En proceso."""
    try:
        from app.models.operation import Operation
        op = Operation.query.filter_by(operation_id=session.cotiz_op_id).first()
        if not op:
            send_text(numero, '⚠️ No encontramos tu operación. Contacta a un asesor: *+51 910 624 404*')
            return

        if op.status not in ('Pendiente', 'En proceso'):
            send_text(numero, f'ℹ️ Tu operación *{op.operation_id}* ya fue procesada o cancelada.')
            session.estado = 'inicio'
            return

        # Agregar abono con el código de operación
        deposits = op.client_deposits or []
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

        send_buttons(numero,
            f'✅ *¡Código registrado!*\n\n'
            f'📋 *Operación:* {op.operation_id}\n'
            f'🔢 *Código bancario:* {codigo}\n\n'
            f'Tu operación pasó a *En proceso*. Un asesor verificará tu transferencia y completará el cambio en breve.\n\n'
            f'¿Tienes alguna consulta?',
            [
                {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
                {'id': 'btn_cotizar', 'title': '💱 Nueva cotización'},
            ]
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
    """Pide al cliente su número de cuenta cuando no tiene ninguna registrada."""
    simbolo = 'USD' if moneda == 'USD' else 'soles (PEN)'
    send_text(numero,
        f'No tenemos una cuenta {simbolo} registrada a tu nombre.\n\n'
        f'Por favor ingresa tu *número de cuenta {simbolo}* donde deseas recibir el dinero:'
    )


def _crear_op_y_confirmar(numero, session, client):
    """Crea la operación y envía confirmación. Centraliza la lógica de creación."""
    try:
        op = _crear_operacion(session, client)
        session.cotiz_op_id = op.operation_id
        _flujo_op_creada(numero, op, session, client)
        session.estado = 'op_pendiente_pago'
        # Notificar al sistema en tiempo real para que aparezca sin recargar
        try:
            from app.services.notification_service import NotificationService
            NotificationService.notify_new_operation(op)
            NotificationService.notify_dashboard_update()
        except Exception as _notif_err:
            log.warning(f'[WaBot] Error notificando nueva op al sistema: {_notif_err}')
        # Notificar a admins por WA + email
        try:
            titular = client.full_name or client.razon_social or numero
            tipo_op = 'Compra USD' if op.operation_type == 'Compra' else 'Venta USD'
            _msg_op = (
                f'💱 Nueva operación desde el bot\n\n'
                f'Op:      {op.operation_id}\n'
                f'Cliente: {titular}\n'
                f'Tipo:    {tipo_op}\n'
                f'Monto:   USD {session.cotiz_importe:,.2f}\n'
                f'TC:      S/ {session.cotiz_tc:.4f}\n\n'
                f'Esperando transferencia del cliente.'
            )
            _notificar_admins_wa(_msg_op)
            _notificar_admins_email(
                f'💱 Nueva operación bot — {op.operation_id}',
                _msg_op
            )
        except Exception as _wa_err:
            log.warning(f'[WaBot] Error notificando nueva op a admins: {_wa_err}')
    except Exception as _oe:
        log.error(f'[WaBot] Error creando op: {_oe}')
        send_text(numero,
            'Ocurrió un error al crear la operación. '
            'Por favor contacta a un asesor: *+51 910 624 404*'
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
        'En breve un asesor se pondrá en contacto contigo por este mismo chat para brindarte el soporte que necesitas.'
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


def _flujo_fuera_horario(numero):
    """Notifica al cliente que estamos fuera de horario de operación."""
    send_buttons(numero,
        '🕐 *Fuera de horario de operación*\n\n'
        'Para ejecutar operaciones, registrarte o hablar con un asesor, '
        'necesitamos estar en horario:\n'
        '• Lunes a Viernes: *9:00 AM – 6:00 PM*\n'
        '• Sábados: *9:00 AM – 2:00 PM*\n\n'
        'Puedes cotizar el tipo de cambio ahora de forma indicativa. 😊',
        [{'id': 'btn_cotizar', 'title': '💱 Ver tipo de cambio'}]
    )


# ── Handler principal ──────────────────────────────────────────────

def _nombre_valido(nombre):
    """Retorna el nombre solo si contiene al menos una letra del alfabeto."""
    if not nombre:
        return ''
    return nombre if re.search(r'[a-zA-ZáéíóúüñÁÉÍÓÚÜÑ]', nombre) else ''


def handle_message(numero, nombre, tipo_msg, texto, media_id=''):
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
        if estado != 'inicio' and _sesion_inactiva(session):
            log.info(f'[WaBot] {numero} — sesión inactiva ({estado}), reiniciando.')
            _reset_sesion(session)
            db.session.commit()
            estado = 'inicio'

        # ── Verificar expiración de cotización ────────────────────
        if estado == 'viendo_cotizacion' and _cotiz_expirada(session):
            _flujo_cotiz_expirada(numero)
            session.estado = 'inicio'
            db.session.commit()
            return

        # ── Botones interactivos ───────────────────────────────────
        if tipo_msg == 'interactive':
            btn_id = texto

            # Botones que requieren horario de atención (ejecutar operación / registrarse / asesor)
            # Cotizar es permitido fuera de horario de forma indicativa
            _BTNS_CON_HORARIO = {
                'btn_aceptar_cotiz', 'btn_registro', 'btn_registrarme', 'btn_asesor',
            }
            if btn_id in _BTNS_CON_HORARIO and not _is_horario_atencion():
                _flujo_fuera_horario(numero)

            elif btn_id == 'btn_cotizar':
                _flujo_cotizar_inicio(numero)
                session.estado = 'eligiendo_operacion'

            elif btn_id == 'btn_comprar':
                session.cotiz_op = 'compra'
                _flujo_pedir_importe(numero, 'compra')
                session.estado = 'esperando_importe'

            elif btn_id == 'btn_vender':
                session.cotiz_op = 'venta'
                _flujo_pedir_importe(numero, 'venta')
                session.estado = 'esperando_importe'

            elif btn_id == 'btn_aceptar_cotiz':
                # P2 — Buscar cliente por número de teléfono antes de preguntar DNI
                clientes_tel = _buscar_clientes_por_telefono(numero)
                if len(clientes_tel) == 1:
                    # Un único cliente aprobado → saltar verificación de DNI
                    client_tel = clientes_tel[0]
                    session.cotiz_doc = client_tel.dni
                    moneda_recibe_tel = 'USD' if session.cotiz_op == 'compra' else 'PEN'
                    cuentas_tel = _cuentas_cliente_por_moneda(client_tel, moneda_recibe_tel)
                    if len(cuentas_tel) == 1:
                        session.cotiz_cuenta = cuentas_tel[0].get('account_number', '')
                        _crear_op_y_confirmar(numero, session, client_tel)
                    elif len(cuentas_tel) > 1:
                        _flujo_elegir_cuenta(numero, cuentas_tel, moneda_recibe_tel)
                        session.estado = 'eligiendo_cuenta_destino'
                    else:
                        _flujo_pedir_cuenta_destino(numero, moneda_recibe_tel)
                        session.estado = 'esperando_cuenta_destino'
                elif len(clientes_tel) > 1:
                    # Múltiples cuentas (ej. personal + empresa) → elegir
                    _flujo_elegir_cliente_telefono(numero, clientes_tel)
                    session.estado = 'eligiendo_cliente_telefono'
                else:
                    # No encontrado → flujo estándar con DNI
                    _flujo_cotiz_aceptada(numero, session)
                    session.estado = 'decidiendo_registro'

            elif btn_id.startswith('btn_cliente_') and estado == 'eligiendo_cliente_telefono':
                # P2 — Cliente eligió con qué cuenta operar (múltiples cuentas en mismo teléfono)
                doc_sel = btn_id[len('btn_cliente_'):]
                session.cotiz_doc = doc_sel
                client_sel = _buscar_cliente(doc_sel)
                if client_sel and (client_sel.kyc_status or '').lower() in ('completo', 'aprobado'):
                    moneda_sel = 'USD' if session.cotiz_op == 'compra' else 'PEN'
                    cuentas_sel = _cuentas_cliente_por_moneda(client_sel, moneda_sel)
                    if len(cuentas_sel) == 1:
                        session.cotiz_cuenta = cuentas_sel[0].get('account_number', '')
                        _crear_op_y_confirmar(numero, session, client_sel)
                    elif len(cuentas_sel) > 1:
                        _flujo_elegir_cuenta(numero, cuentas_sel, moneda_sel)
                        session.estado = 'eligiendo_cuenta_destino'
                    else:
                        _flujo_pedir_cuenta_destino(numero, moneda_sel)
                        session.estado = 'esperando_cuenta_destino'
                else:
                    send_text(numero, '⚠️ No encontramos esa cuenta activa. Ingresa tu documento manualmente.')
                    _flujo_pedir_doc_verificacion(numero)
                    session.estado = 'esperando_doc'

            elif btn_id.startswith('btn_cuenta_') and estado == 'eligiendo_cuenta_destino':
                session.cotiz_cuenta = btn_id[len('btn_cuenta_'):]
                client = _buscar_cliente(session.cotiz_doc)
                if client:
                    _crear_op_y_confirmar(numero, session, client)
                else:
                    send_text(numero, '⚠️ Error de sesión. Contacta a un asesor: *+51 910 624 404*')
                    session.estado = 'inicio'

            elif btn_id == 'btn_otra_cuenta':
                moneda_recibe = 'USD' if session.cotiz_op == 'compra' else 'PEN'
                simbolo = 'USD ($)' if moneda_recibe == 'USD' else 'soles (S/)'
                send_text(numero,
                    f'🏦 Ingresa el *nombre del banco* y tu *número de cuenta {simbolo}*.\n\n'
                    f'Ejemplo: *BCP 1234567890*'
                )
                session.estado = 'esperando_cuenta_nueva'

            elif btn_id == 'btn_ya_transferi':
                send_text(numero,
                    '🔢 Ingresa el *código de tu transferencia*.\n\n'
                    'Es el número de 8 a 12 dígitos que aparece en tu voucher o constancia bancaria '
                    '(puede llamarse "número de operación", "referencia" o "código de transacción").\n\n'
                    'Ejemplo: *12345678*'
                )
                session.estado = 'esperando_codigo_op'

            elif btn_id == 'btn_tengo_cuenta':
                _flujo_pedir_doc_verificacion(numero)
                session.estado = 'esperando_doc'

            elif btn_id == 'btn_volver_cotizar':
                _flujo_cotizar_inicio(numero)
                session.estado = 'eligiendo_operacion'

            elif btn_id in ('btn_registro', 'btn_registrarme'):
                _flujo_tipo_cliente(numero)
                session.estado = 'eligiendo_tipo'

            elif btn_id == 'btn_asesor':
                _flujo_asesor(numero)
                session.estado = 'inicio'

            elif btn_id == 'btn_como_funciona':
                _flujo_como_funciona(numero)
                session.estado = 'inicio'

            elif btn_id == 'btn_volver_inicio':
                session.estado      = 'inicio'
                session.tipo        = ''
                session.cotiz_doc   = ''
                session.cotiz_email = ''
                session.dni_front   = ''
                session.dni_back    = ''
                session.ruc_doc     = ''
                _bienvenida(numero, session.nombre)

            elif btn_id == 'btn_natural':
                session.tipo = 'natural'
                _flujo_pedir_numero_doc(numero, 'natural')
                session.estado = 'esperando_numero_doc'

            elif btn_id == 'btn_empresa':
                session.tipo = 'empresa'
                _flujo_pedir_numero_doc(numero, 'empresa')
                session.estado = 'esperando_numero_doc'

            else:
                _menu_rapido(numero)
                session.estado = 'inicio'

        # ── Texto libre ───────────────────────────────────────────
        elif tipo_msg == 'text':

            # Solo el registro requiere horario en texto (cotizar y cuenta destino se permiten siempre)
            _ESTADOS_CON_HORARIO = {
                'eligiendo_tipo', 'esperando_numero_doc',
            }
            if estado in _ESTADOS_CON_HORARIO and not _is_horario_atencion():
                _flujo_fuera_horario(numero)

            elif estado == 'esperando_importe':
                monto = _parse_monto(texto)
                if monto and monto > 0:
                    if monto < MONTO_MINIMO_USD:
                        send_text(numero,
                            f'El monto mínimo de operación es *USD {MONTO_MINIMO_USD:,.0f}*.\n\n'
                            f'¿Cuántos dólares deseas cambiar?'
                        )
                    elif monto > 20000:
                        send_buttons(numero,
                            '💼 Para operaciones superiores a *USD 20,000* te atendemos de forma personalizada con condiciones especiales.\n\n'
                            'Un asesor te contactará para brindarte el mejor tipo de cambio.',
                            [{'id': 'btn_asesor', 'title': '💬 Hablar con asesor'}]
                        )
                        session.estado = 'inicio'
                    else:
                        session.cotiz_importe = monto
                        _flujo_mostrar_cotizacion(numero, session)
                        session.estado = 'viendo_cotizacion'
                else:
                    send_text(numero,
                        'No entendí el monto. Por favor escribe solo el número en USD. Ejemplo: *1000*'
                    )

            elif estado == 'esperando_doc':
                # Verificar DNI/RUC de cliente existente
                doc = texto.strip()
                if _es_dni(doc) or _es_ruc(doc):
                    session.cotiz_doc = doc
                    client = _buscar_cliente(doc)
                    if client:
                        kyc = (client.kyc_status or '').lower()
                        if kyc in ('completo', 'aprobado'):
                            # Determinar moneda que recibirá el cliente
                            moneda_recibe = 'USD' if session.cotiz_op == 'compra' else 'PEN'
                            cuentas = _cuentas_cliente_por_moneda(client, moneda_recibe)
                            if len(cuentas) == 1:
                                # Una sola cuenta: auto-seleccionar
                                session.cotiz_cuenta = cuentas[0].get('account_number', '')
                                _crear_op_y_confirmar(numero, session, client)
                            elif len(cuentas) > 1:
                                # Múltiples cuentas: elegir
                                _flujo_elegir_cuenta(numero, cuentas, moneda_recibe)
                                session.estado = 'eligiendo_cuenta_destino'
                            else:
                                # Sin cuenta de esa moneda: pedir
                                session.cotiz_cuenta = ''
                                _flujo_pedir_cuenta_destino(numero, moneda_recibe)
                                session.estado = 'esperando_cuenta_destino'
                        else:
                            _flujo_sin_kyc(numero, kyc)
                            session.estado = 'inicio'
                    else:
                        _flujo_no_encontrado(numero)
                        session.estado = 'inicio'
                else:
                    send_text(numero,
                        'Ingresa un *DNI/CE* válido (8-9 dígitos) o *RUC* válido (11 dígitos).'
                    )

            elif estado == 'esperando_cuenta_destino':
                # Cliente sin cuentas registradas ingresa número de cuenta manualmente
                session.cotiz_cuenta = texto.strip()
                client = _buscar_cliente(session.cotiz_doc)
                if client:
                    _crear_op_y_confirmar(numero, session, client)
                else:
                    send_text(numero, '⚠️ Error de sesión. Contacta a un asesor: *+51 910 624 404*')
                    session.estado = 'inicio'

            elif estado == 'esperando_cuenta_nueva':
                # Cliente ingresa "BANCO NUMERO" para una nueva cuenta
                # P8 — Normalizar: eliminar "Banco"/"Bank" prefijo antes de parsear
                raw_cuenta = texto.strip()
                raw_upper = raw_cuenta.upper()
                if raw_upper.startswith('BANCO ') or raw_upper.startswith('BANK '):
                    raw_cuenta = raw_cuenta.split(None, 1)[1].strip()
                partes = raw_cuenta.split(None, 1)
                if len(partes) >= 2:
                    banco, num = partes[0].upper(), partes[1].strip()
                    # Validar que num contiene dígitos
                    num_digits = re.sub(r'\D', '', num)
                    if len(num_digits) >= 6:
                        session.cotiz_cuenta = f'{banco}|{num_digits}'
                        client = _buscar_cliente(session.cotiz_doc)
                        if client:
                            _crear_op_y_confirmar(numero, session, client)
                        else:
                            send_text(numero, '⚠️ Error de sesión. Contacta a un asesor: *+51 910 624 404*')
                            session.estado = 'inicio'
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
                    send_text(numero, f'Ingresa un *{esperado}* válido.')

            elif estado == 'esperando_codigo_op':
                codigo = texto.strip()
                if codigo:
                    _flujo_registrar_codigo_op(numero, codigo, session)
                else:
                    send_text(numero, 'Ingresa el código de operación de tu comprobante bancario.')

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
                if any(k in txt_lower for k in ('como funciona', 'cómo funciona', 'como opera', 'es seguro', 'es confiable')):
                    _flujo_como_funciona(numero)
                elif any(k in txt_lower for k in ('horario', 'hora', 'atienden', 'trabajan', 'abren', 'cierran')):
                    _flujo_como_funciona(numero)  # incluye horario en el texto
                elif any(k in txt_lower for k in ('cancelar', 'salir', 'exit', 'stop', 'no gracias')):
                    send_text(numero,
                        'No hay ningún proceso activo. Cuando quieras operar, estamos aquí. 😊'
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
                            '⏳ Tu solicitud de registro está siendo revisada por nuestro equipo.\n\n'
                            'Te notificaremos por aquí mismo cuando tu cuenta esté activa.',
                            [{'id': 'btn_asesor', 'title': '💬 Hablar con asesor'}]
                        )
                    else:
                        send_buttons(numero,
                            '¿Deseas registrarte en Qoricash?',
                            [
                                {'id': 'btn_registro', 'title': '📝 Registrarme'},
                                {'id': 'btn_asesor',   'title': '💬 Hablar con asesor'},
                            ]
                        )
                else:
                    _bienvenida(numero, session.nombre)

            elif estado in ('esperando_dni_front', 'esperando_dni_back', 'esperando_ruc', 'esperando_email'):
                _flujo_recordatorio_registro(numero, estado)

            else:
                # P1 — Re-enviar el paso donde quedó el cliente según su estado
                if estado == 'eligiendo_operacion':
                    _flujo_cotizar_inicio(numero)

                elif estado == 'esperando_importe':
                    _flujo_pedir_importe(numero, session.cotiz_op or 'compra')

                elif estado == 'eligiendo_tipo':
                    _flujo_tipo_cliente(numero)

                elif estado in ('eligiendo_cuenta_destino', 'esperando_cuenta_destino', 'esperando_cuenta_nueva'):
                    moneda = 'USD' if session.cotiz_op == 'compra' else 'PEN'
                    _flujo_pedir_cuenta_destino(numero, moneda)
                    session.estado = 'esperando_cuenta_destino'

                elif estado == 'viendo_cotizacion':
                    # P1 — Cliente escribió texto en lugar de usar los botones de cotización
                    _flujo_mostrar_cotizacion(numero, session)

                elif estado == 'decidiendo_registro':
                    # P1 — Cliente escribió texto en lugar de usar los botones "¿Ya eres cliente?"
                    _flujo_cotiz_aceptada(numero, session)

                elif estado == 'op_pendiente_pago':
                    # P1 — Cliente escribió en lugar de presionar "Ya transferí"
                    from app.models.operation import Operation as _Op2
                    op_act = _Op2.query.filter_by(operation_id=session.cotiz_op_id).first() if session.cotiz_op_id else None
                    if op_act and op_act.status == 'Pendiente':
                        moneda_e = 'PEN' if session.cotiz_op == 'compra' else 'USD'
                        simbolo_e = 'S/' if moneda_e == 'PEN' else 'USD'
                        monto_e = float(op_act.amount_pen) if moneda_e == 'PEN' else float(op_act.amount_usd)
                        send_buttons(numero,
                            f'📋 Tu operación *{op_act.operation_id}* sigue pendiente de pago.\n\n'
                            f'Transfiere *{simbolo_e} {monto_e:,.2f}* y luego presiona el botón.',
                            [{'id': 'btn_ya_transferi', 'title': '✅ Ya transferí'}]
                        )
                    else:
                        _bienvenida(numero, session.nombre)
                        session.estado = 'inicio'

                elif estado == 'eligiendo_cliente_telefono':
                    # Re-enviar selección de cuenta
                    clientes_re = _buscar_clientes_por_telefono(numero)
                    if clientes_re:
                        _flujo_elegir_cliente_telefono(numero, clientes_re)
                    else:
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
                    _bienvenida(numero, session.nombre)

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
                _bienvenida(numero, session.nombre)
                session.estado = 'inicio'

            else:
                send_text(numero, 'Gracias por enviar el archivo. Un asesor lo revisará pronto.')

        # ── Cualquier otro tipo (audio, video, ubicación, sticker, etc.) ─────
        else:
            # P13 — En estados activos, avisar que solo se aceptan texto y fotos
            if estado != 'inicio':
                send_text(numero,
                    'Solo puedo procesar texto y fotos por ahora 😊\n'
                    'Por favor usa las opciones del menú o escribe tu respuesta.'
                )
            else:
                _bienvenida(numero, session.nombre)

        db.session.commit()

    except Exception as e:
        log.error(f'[WaBot] Error en handle_message {numero}: {e}')
        try:
            db.session.rollback()
        except Exception:
            pass
