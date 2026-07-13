"""
WaBot — Chatbot de WhatsApp para QoriCash
Flujo: Bienvenida → TC / Registro (natural/empresa) / Asesor
"""
import os, logging, requests
from app.extensions import db
from app.models.wa_bot_session import WaBotSession
from app.models.wa_message import WaMessage

log = logging.getLogger(__name__)

WA_ACCESS_TOKEN = os.environ.get('WA_ACCESS_TOKEN', '')
WA_PHONE_ID     = os.environ.get('WA_PHONE_NUMBER_ID', '1118979324636599')
WA_API_URL      = f'https://graph.facebook.com/v19.0/{WA_PHONE_ID}/messages'

ASESOR_NUMERO   = os.environ.get('WA_ASESOR_NUMERO', '51910624404')  # número del asesor interno


# ── Envío de mensajes ─────────────────────────────────────────────

def _headers():
    return {
        'Authorization': f'Bearer {WA_ACCESS_TOKEN}',
        'Content-Type': 'application/json',
    }


def _save_outgoing(numero, texto):
    """Guarda mensaje saliente en WaMessage."""
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
    """
    buttons = [{'id': 'btn_id', 'title': 'Texto'}]  (máx 3)
    """
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
    """
    sections = [{'title': 'Sección', 'rows': [{'id': 'id', 'title': 'Título', 'description': ''}]}]
    """
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


# ── Helpers de TC ─────────────────────────────────────────────────

def _get_tc():
    try:
        from app.models.exchange_rate import ExchangeRate
        rates = ExchangeRate.get_current_rates()
        compra = rates.get('compra', 0)
        venta  = rates.get('venta', 0)
        return compra, venta
    except Exception:
        return 0, 0


# ── Flujos del bot ────────────────────────────────────────────────

def _bienvenida(numero, nombre):
    saludo = f'Hola {nombre} 👋' if nombre else 'Hola 👋'
    compra, venta = _get_tc()
    tc_texto = f'💱 *Tipo de cambio ahora:*\n  • Compra: S/ {compra:.3f}\n  • Venta:  S/ {venta:.3f}' if compra else ''

    msg = (
        f'{saludo} Bienvenido a *QoriCash* 🏦\n'
        'Casa de cambio digital, segura y regulada por la SBS.\n\n'
        f'{tc_texto}\n\n'
        '¿En qué te podemos ayudar?'
    ).strip()

    send_buttons(numero, msg, [
        {'id': 'btn_tc',       'title': '💱 Tipo de cambio'},
        {'id': 'btn_registro', 'title': '📝 Registrarme'},
        {'id': 'btn_asesor',   'title': '💬 Hablar con asesor'},
    ])


def _flujo_tc(numero):
    compra, venta = _get_tc()
    if compra:
        msg = (
            f'💱 *Tipo de cambio QoriCash*\n\n'
            f'  • Compra USD: *S/ {compra:.3f}*\n'
            f'  • Venta USD:  *S/ {venta:.3f}*\n\n'
            '¿Quieres iniciar una operación?'
        )
        send_buttons(numero, msg, [
            {'id': 'btn_registro', 'title': '📝 Registrarme'},
            {'id': 'btn_asesor',   'title': '💬 Hablar con asesor'},
        ])
    else:
        send_text(numero, 'En este momento no tenemos el tipo de cambio disponible. Por favor escríbenos directamente y te atendemos al instante.')


def _flujo_asesor(numero):
    send_text(numero,
        '✅ Perfecto, en un momento un asesor te atenderá.\n\n'
        '📞 También puedes llamarnos o escribirnos directamente:\n'
        '*+51 910 624 404*'
    )
    # Notificar internamente (log — se puede ampliar a notificación al asesor)
    log.info(f'[WaBot] {numero} solicitó hablar con asesor.')


def _flujo_tipo_cliente(numero):
    send_buttons(numero,
        '¿Cómo quieres registrarte?',
        [
            {'id': 'btn_natural',  'title': '👤 Persona natural'},
            {'id': 'btn_empresa',  'title': '🏢 Empresa'},
        ]
    )


def _flujo_pedir_dni_front(numero):
    send_text(numero,
        '📷 Por favor envíanos una *foto del frente de tu DNI*.\n\n'
        'Asegúrate de que sea legible y que los 4 bordes sean visibles.'
    )


def _flujo_pedir_dni_back(numero):
    send_text(numero,
        '📷 Ahora envíanos una *foto del reverso de tu DNI*.'
    )


def _flujo_pedir_ruc(numero):
    send_text(numero,
        '📄 Por favor envíanos la *Ficha RUC de tu empresa*.\n\n'
        'Puedes descargarla desde sunat.gob.pe → Consulta RUC.'
    )


def _flujo_confirmar_registro(numero, session):
    if session.tipo == 'natural':
        msg = (
            '✅ *¡Documentos recibidos!*\n\n'
            'Hemos registrado tu solicitud. Un asesor verificará tus datos y te confirmará la activación de tu cuenta en breve.\n\n'
            '¿Tienes alguna otra consulta?'
        )
    else:
        msg = (
            '✅ *¡Ficha RUC recibida!*\n\n'
            'Hemos registrado tu empresa. Un asesor verificará los datos y te activará la cuenta corporativa en breve.\n\n'
            '¿Tienes alguna otra consulta?'
        )
    send_buttons(numero, msg, [
        {'id': 'btn_tc',     'title': '💱 Tipo de cambio'},
        {'id': 'btn_asesor', 'title': '💬 Hablar con asesor'},
    ])
    # Guardar lead en prospecto si no existe
    _registrar_lead(numero, session)


def _registrar_lead(numero, session):
    try:
        from app.models.prospecto import Prospecto, ActividadProspecto
        from app.models.user import User
        import re
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


# ── Handler principal ─────────────────────────────────────────────

def handle_message(numero, nombre, tipo_msg, texto, media_id=''):
    """
    Punto de entrada desde webhook_receive().
    tipo_msg: 'text' | 'image' | 'document' | etc.
    texto: cuerpo del mensaje (o caption)
    media_id: id de media si hay imagen/documento
    """
    try:
        session = WaBotSession.get_or_create(numero)
        if nombre and not session.nombre:
            session.nombre = nombre

        estado = session.estado

        # ── Respuestas a botones interactivos ─────────────────────
        if tipo_msg == 'interactive':
            btn_id = texto  # pasamos el button_id como texto desde el webhook

            if btn_id == 'btn_tc':
                _flujo_tc(numero)
                session.estado = 'inicio'

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

        # ── Mensajes de texto ─────────────────────────────────────
        elif tipo_msg == 'text':
            if estado == 'inicio':
                _bienvenida(numero, session.nombre)
            else:
                # Si está en medio de un flujo y manda texto, guiar
                send_text(numero, 'Por favor usa los botones para navegar las opciones. 😊')

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
