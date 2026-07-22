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

# 1 pip = 0.0001 (estándar forex para pares con PEN)
SPREAD_TC = 0.0020   # 20 pips: spread que aplica el bot sobre el TC oficial

COTIZ_VALIDEZ_MIN = 15   # minutos de validez de la cotización

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

    mejora = _mejora_tc(importe)

    if op == 'compra':
        # Cliente compra dólares → empresa le vende → usa TC venta + spread
        tc_base  = round(venta + SPREAD_TC, 4)
        tc_final = round(tc_base - mejora, 4)
        soles    = round(importe * tc_final, 2)
        resumen  = (
            f'💵 *Cotización — Usted compra dólares*\n\n'
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
            f'💵 *Cotización — Usted vende dólares*\n\n'
            f'  Envías:         *USD {importe:,.2f}*\n'
            f'  Tipo de cambio: *S/ {tc_final:.4f}*\n'
            f'  Recibes:        *S/ {soles:,.2f}*'
        )

    if mejora > 0:
        resumen += f'\n\n  ✨ _TC preferencial por monto especial_'

    resumen += f'\n\n  ⏱ _Válido por {COTIZ_VALIDEZ_MIN} minutos_'

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


def _flujo_cotiz_aceptada(numero, session):
    """Cliente aceptó el precio — verificar si tiene cuenta."""
    log.info(f'[WaBot] {numero} aceptó cotización: {session.cotiz_op} USD {session.cotiz_importe} a S/ {session.cotiz_tc}')
    send_buttons(numero,
        '✅ *¡Precio aceptado!*\n\n¿Ya tienes una cuenta registrada en Qoricash?',
        [
            {'id': 'btn_tengo_cuenta', 'title': '✅ Sí, tengo cuenta'},
            {'id': 'btn_registrarme',  'title': '📝 No, quiero registrarme'},
        ]
    )


def _flujo_pedir_doc_verificacion(numero):
    send_text(numero,
        '🔎 Ingresa tu *DNI* (8 dígitos) o *RUC* (11 dígitos) para verificar tu cuenta:'
    )


def _es_dni(t):
    return bool(re.match(r'^\d{8}$', t.strip()))


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

    op_type  = 'Compra' if session.cotiz_op == 'compra' else 'Venta'
    amount_u = session.cotiz_importe
    tc       = session.cotiz_tc
    amount_p = round(amount_u * tc, 2)

    sys_user = User.query.filter_by(role='Master').order_by(User.id).first()
    uid = sys_user.id if sys_user else 1

    op = Operation(
        operation_id   = Operation.generate_operation_id(),
        client_id      = client.id,
        user_id        = uid,
        operation_type = op_type,
        origen         = 'app',
        amount_usd     = amount_u,
        exchange_rate  = tc,
        amount_pen     = amount_p,
        status         = 'Pendiente',
        notes          = 'Operación generada vía WhatsApp bot',
    )
    db.session.add(op)
    db.session.flush()
    return op


def _flujo_op_creada(numero, op, session):
    """Envía confirmación de operación creada con datos de transferencia."""
    moneda_enviar = 'PEN' if session.cotiz_op == 'compra' else 'USD'
    simbolo       = 'S/' if moneda_enviar == 'PEN' else 'USD'
    monto_enviar  = float(op.amount_pen) if moneda_enviar == 'PEN' else float(op.amount_usd)

    cuentas = _texto_cuentas_qoricash(moneda_enviar)

    msg = (
        f'✅ *Operación creada exitosamente*\n'
        f'📋 *Nro:* {op.operation_id}\n\n'
        f'Tienes *15 minutos* para realizar la transferencia, de lo contrario se cancelará automáticamente.\n\n'
        f'*Transfiere {simbolo} {monto_enviar:,.2f} a:*\n\n'
        f'{cuentas}\n\n'
        f'_Una vez realizada la transferencia, un asesor procesará tu operación._'
    )
    send_text(numero, msg)


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
        send_text(numero, '🪪 Ingresa tu número de *DNI* (8 dígitos):')
    else:
        send_text(numero, '🏢 Ingresa el *RUC* de tu empresa (11 dígitos):')


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


def _flujo_pedir_email(numero):
    send_text(numero, '📧 Por último, ingresa tu *correo electrónico*:')


def _flujo_confirmar_registro(numero, session):
    if session.tipo == 'natural':
        msg = (
            '✅ *¡Solicitud de registro recibida!*\n\n'
            'Nuestro equipo verificará tu DNI y activará tu cuenta en un máximo de *24 horas*.\n\n'
            'Te notificaremos por este mismo WhatsApp cuando esté lista para operar.'
        )
    else:
        msg = (
            '✅ *¡Solicitud de registro de empresa recibida!*\n\n'
            'Nuestro equipo verificará la ficha RUC y activará la cuenta corporativa en máximo *24 horas*.\n\n'
            'Te notificaremos por WhatsApp cuando esté habilitada.'
        )
    send_buttons(numero, msg, [
        {'id': 'btn_cotizar', 'title': '💱 Cotizar'},
        {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
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

        # ── Verificar expiración de cotización ────────────────────
        if estado == 'viendo_cotizacion' and _cotiz_expirada(session):
            _flujo_cotiz_expirada(numero)
            session.estado = 'inicio'
            db.session.commit()
            return

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
                session.estado = 'decidiendo_registro'

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

            elif estado == 'esperando_doc':
                # Verificar DNI/RUC de cliente existente
                doc = texto.strip()
                if _es_dni(doc) or _es_ruc(doc):
                    session.cotiz_doc = doc
                    client = _buscar_cliente(doc)
                    if client:
                        kyc = (client.kyc_status or '').lower()
                        if kyc in ('completo', 'aprobado'):
                            try:
                                op = _crear_operacion(session, client)
                                _flujo_op_creada(numero, op, session)
                                session.estado = 'inicio'
                            except Exception as _oe:
                                log.error(f'[WaBot] Error creando op: {_oe}')
                                send_text(numero,
                                    'Ocurrió un error al crear la operación. '
                                    'Por favor contacta a un asesor: *+51 910 624 404*'
                                )
                                session.estado = 'inicio'
                        else:
                            _flujo_sin_kyc(numero, kyc)
                            session.estado = 'inicio'
                    else:
                        _flujo_no_encontrado(numero)
                        session.estado = 'inicio'
                else:
                    send_text(numero,
                        'Ingresa un *DNI* válido (8 dígitos) o *RUC* válido (11 dígitos).'
                    )

            elif estado == 'esperando_numero_doc':
                # DNI/RUC durante el proceso de registro
                doc = texto.strip()
                esperado = 'DNI (8 dígitos)' if session.tipo == 'natural' else 'RUC (11 dígitos)'
                valido = _es_dni(doc) if session.tipo == 'natural' else _es_ruc(doc)
                if valido:
                    session.cotiz_doc = doc
                    if session.tipo == 'natural':
                        _flujo_pedir_dni_front(numero)
                        session.estado = 'esperando_dni_front'
                    else:
                        _flujo_pedir_ruc(numero)
                        session.estado = 'esperando_ruc'
                else:
                    send_text(numero, f'Ingresa un *{esperado}* válido.')

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
                # Si ya fue bienvenido antes, mostrar solo el menú
                if session.nombre or session.created_at != session.updated_at:
                    _menu_rapido(numero)
                else:
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
