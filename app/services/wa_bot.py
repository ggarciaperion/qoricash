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

# Importe mínimo para mejora de TC (en USD)
MONTO_ESPECIAL  = 5000
# Mejora en pips (0.001 por pip)
PIPS_MEJORA     = 15
MEJORA_TC       = PIPS_MEJORA * 0.001   # = 0.015


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
    try:
        from app.models.exchange_rate import ExchangeRate
        rates  = ExchangeRate.get_current_rates()
        compra = rates.get('compra', 0)
        venta  = rates.get('venta', 0)
        return compra, venta
    except Exception:
        return 0, 0


def _parse_monto(texto):
    """Extrae un número de un texto libre. Ej: '5000', '5,000', '$5000', '5 mil' → 5000.0"""
    t = texto.lower().strip()
    # "5 mil" o "5mil"
    m = re.match(r'^(\d+(?:[.,]\d+)?)\s*mil$', t)
    if m:
        return float(m.group(1).replace(',', '.')) * 1000
    # Número normal (quita símbolos y comas de miles)
    limpio = re.sub(r'[^\d.]', '', t.replace(',', '.'))
    # Si hay más de un punto, quitar todos menos el último
    partes = limpio.split('.')
    if len(partes) > 2:
        limpio = ''.join(partes[:-1]) + '.' + partes[-1]
    try:
        return float(limpio)
    except ValueError:
        return None


# ── Flujos del bot ─────────────────────────────────────────────────

def _bienvenida(numero, nombre):
    saludo = f'Hola {nombre} 👋' if nombre else 'Hola 👋'
    compra, venta = _get_tc()
    tc_texto = (
        f'💱 *Tipo de cambio ahora:*\n'
        f'  • Compra: S/ {compra:.3f}\n'
        f'  • Venta:  S/ {venta:.3f}'
    ) if compra else ''

    msg = (
        f'{saludo} Bienvenido a *Qoricash* 🏦\n'
        'Fintech de cambio de divisas, segura y regulada por la SBS.\n\n'
        f'{tc_texto}\n\n'
        '¿En qué te podemos ayudar?'
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
        'Escribe el monto en USD. Ejemplo: *1000*'
    )


def _flujo_mostrar_cotizacion(numero, session):
    """Muestra el TC final (con mejora si aplica) y botones de aceptar/volver."""
    compra, venta = _get_tc()
    op      = session.cotiz_op
    importe = session.cotiz_importe

    if op == 'compra':
        # Cliente compra dólares → empresa vende → TC de venta
        # Mejora: TC de venta más bajo (mejor para el cliente)
        tc_base  = venta
        tc_final = round(tc_base - MEJORA_TC, 3) if importe >= MONTO_ESPECIAL else tc_base
        soles    = round(importe * tc_final, 2)
        resumen  = (
            f'💵 *Cotización — Usted compra dólares*\n\n'
            f'  Envías:         *S/ {soles:,.2f}*\n'
            f'  Tipo de cambio: *S/ {tc_final:.3f}*\n'
            f'  Recibes:        *USD {importe:,.2f}*'
        )
        if importe >= MONTO_ESPECIAL:
            resumen += f'\n\n  ✨ _TC preferencial por monto especial_'
    else:
        # Cliente vende dólares → empresa compra → TC de compra
        # Mejora: TC de compra más alto (mejor para el cliente)
        tc_base  = compra
        tc_final = round(tc_base + MEJORA_TC, 3) if importe >= MONTO_ESPECIAL else tc_base
        soles    = round(importe * tc_final, 2)
        resumen  = (
            f'💵 *Cotización — Usted vende dólares*\n\n'
            f'  Envías:         *USD {importe:,.2f}*\n'
            f'  Tipo de cambio: *S/ {tc_final:.3f}*\n'
            f'  Recibes:        *S/ {soles:,.2f}*'
        )
        if importe >= MONTO_ESPECIAL:
            resumen += f'\n\n  ✨ _TC preferencial por monto especial_'

    session.cotiz_tc = tc_final

    send_buttons(numero, resumen, [
        {'id': 'btn_aceptar_cotiz',  'title': '✅ Aceptar'},
        {'id': 'btn_volver_cotizar', 'title': '🔄 Volver a cotizar'},
        {'id': 'btn_asesor',         'title': '💬 Hablar con asesor'},
    ])


def _flujo_cotiz_aceptada(numero, session):
    """Cliente aceptó el precio. Confirmar y redirigir."""
    op      = 'compra' if session.cotiz_op == 'compra' else 'venta'
    importe = session.cotiz_importe
    tc      = session.cotiz_tc

    msg = (
        f'✅ *¡Perfecto! Tu cotización ha sido registrada.*\n\n'
        f'  Operación:     {"Compra" if op == "compra" else "Venta"} de USD {importe:,.2f}\n'
        f'  Tipo de cambio: S/ {tc:.3f}\n\n'
        'Un asesor te contactará en breve para coordinar la operación.\n\n'
        '📞 O escríbenos directamente: *+51 910 624 404*'
    )
    send_buttons(numero, msg, [
        {'id': 'btn_cotizar',  'title': '💱 Nueva cotización'},
        {'id': 'btn_registro', 'title': '📝 Registrarme'},
    ])
    log.info(f'[WaBot] {numero} ACEPTÓ cotización: {op} USD {importe} a S/ {tc}')


def _flujo_asesor(numero):
    send_text(numero,
        '✅ Perfecto, en un momento un asesor te atenderá.\n\n'
        '📞 También puedes escribirnos directamente:\n'
        '*+51 910 624 404*'
    )
    log.info(f'[WaBot] {numero} solicitó hablar con asesor.')


def _flujo_tipo_cliente(numero):
    send_buttons(numero,
        '¿Cómo quieres registrarte?',
        [
            {'id': 'btn_natural', 'title': '👤 Persona natural'},
            {'id': 'btn_empresa', 'title': '🏢 Empresa'},
        ]
    )


def _flujo_pedir_dni_front(numero):
    send_text(numero,
        '📷 Por favor envíanos una *foto del frente de tu DNI*.\n\n'
        'Asegúrate de que sea legible y que los 4 bordes sean visibles.'
    )


def _flujo_pedir_dni_back(numero):
    send_text(numero, '📷 Ahora envíanos una *foto del reverso de tu DNI*.')


def _flujo_pedir_ruc(numero):
    send_text(numero,
        '📄 Por favor envíanos la *Ficha RUC de tu empresa*.\n\n'
        'Puedes descargarla desde sunat.gob.pe → Consulta RUC.'
    )


def _flujo_confirmar_registro(numero, session):
    if session.tipo == 'natural':
        msg = (
            '✅ *¡Documentos recibidos!*\n\n'
            'Hemos registrado tu solicitud. Un asesor verificará tus datos '
            'y te confirmará la activación de tu cuenta en breve.\n\n'
            '¿Tienes alguna otra consulta?'
        )
    else:
        msg = (
            '✅ *¡Ficha RUC recibida!*\n\n'
            'Hemos registrado tu empresa. Un asesor verificará los datos '
            'y te activará la cuenta corporativa en breve.\n\n'
            '¿Tienes alguna otra consulta?'
        )
    send_buttons(numero, msg, [
        {'id': 'btn_cotizar',  'title': '💱 Cotizar'},
        {'id': 'btn_asesor',   'title': '💬 Hablar con asesor'},
    ])
    _registrar_lead(numero, session)


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
                estado_comercial = 'interesado',
                canal_captacion  = 'whatsapp_bot',
                notas            = f'Registro vía bot WhatsApp — {tipo_desc}',
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

        # ── Botones interactivos ───────────────────────────────────
        if tipo_msg == 'interactive':
            btn_id = texto

            if btn_id == 'btn_cotizar':
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
                _flujo_cotiz_aceptada(numero, session)
                session.estado = 'inicio'

            elif btn_id == 'btn_volver_cotizar':
                _flujo_cotizar_inicio(numero)
                session.estado = 'eligiendo_operacion'

            elif btn_id == 'btn_registro':
                _flujo_tipo_cliente(numero)
                session.estado = 'eligiendo_tipo'

            elif btn_id == 'btn_asesor':
                _flujo_asesor(numero)
                session.estado = 'inicio'

            elif btn_id == 'btn_natural':
                session.tipo = 'natural'
                _flujo_pedir_dni_front(numero)
                session.estado = 'esperando_dni_front'

            elif btn_id == 'btn_empresa':
                session.tipo = 'empresa'
                _flujo_pedir_ruc(numero)
                session.estado = 'esperando_ruc'

            else:
                _bienvenida(numero, session.nombre)
                session.estado = 'inicio'

        # ── Texto libre ───────────────────────────────────────────
        elif tipo_msg == 'text':

            if estado == 'esperando_importe':
                monto = _parse_monto(texto)
                if monto and monto > 0:
                    session.cotiz_importe = monto
                    _flujo_mostrar_cotizacion(numero, session)
                    session.estado = 'viendo_cotizacion'
                else:
                    send_text(numero,
                        'No entendí el monto. Por favor escribe solo el número. Ejemplo: *1000*'
                    )

            elif estado == 'inicio':
                _bienvenida(numero, session.nombre)

            else:
                send_text(numero,
                    'Por favor usa los botones para continuar. 😊\n\n'
                    'Si necesitas ayuda escríbenos al *+51 910 624 404*'
                )

        # ── Imágenes / documentos ─────────────────────────────────
        elif tipo_msg in ('image', 'document'):
            if estado == 'esperando_dni_front' and media_id:
                session.dni_front = media_id
                _flujo_pedir_dni_back(numero)
                session.estado = 'esperando_dni_back'

            elif estado == 'esperando_dni_back' and media_id:
                session.dni_back = media_id
                _flujo_confirmar_registro(numero, session)
                session.estado = 'completado'

            elif estado == 'esperando_ruc' and media_id:
                session.ruc_doc = media_id
                _flujo_confirmar_registro(numero, session)
                session.estado = 'completado'

            elif estado == 'completado':
                _bienvenida(numero, session.nombre)
                session.estado = 'inicio'

            else:
                send_text(numero, 'Gracias por enviar el archivo. Un asesor lo revisará pronto.')

        # ── Cualquier otro tipo ───────────────────────────────────
        else:
            if estado == 'inicio':
                _bienvenida(numero, session.nombre)

        db.session.commit()

    except Exception as e:
        log.error(f'[WaBot] Error en handle_message {numero}: {e}')
        try:
            db.session.rollback()
        except Exception:
            pass
