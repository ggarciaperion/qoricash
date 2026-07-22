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


def wa_notify_cuenta_activa(client):
    """Envía WA de cuenta activada con botón de asesor. Uso externo (clients.py)."""
    if not client:
        return
    phone_raw = (getattr(client, 'phone', None) or '').split(';')[0].strip()
    phone_digits = ''.join(c for c in phone_raw if c.isdigit())
    if not phone_digits:
        return
    if not phone_digits.startswith('51'):
        phone_digits = '51' + phone_digits
    nombre = getattr(client, 'full_name', None) or getattr(client, 'razon_social', None) or 'Cliente'
    msg = (
        f'✅ *¡Tu cuenta en Qoricash está activa!*\n\n'
        f'Hola *{nombre}*, ya puedes realizar cambio de dólares con nosotros.\n\n'
        f'Escríbenos aquí mismo cuando desees cotizar. 💱'
    )
    send_buttons(phone_digits, msg, [
        {'id': 'btn_cotizar', 'title': '💱 Cotizar'},
        {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
    ])


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
        f'_Una vez hayas transferido, presiona el botón para registrar el número de la transferencia bancaria._'
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
    send_buttons(numero, msg, [
        {'id': 'btn_cotizar', 'title': '💱 Cotizar'},
        {'id': 'btn_asesor',  'title': '💬 Hablar con asesor'},
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

    # ── WhatsApp: mensaje directo a 51926011920 ──────────────────────
    try:
        wa_msg = (
            f'🔔 *Nuevo registro pendiente — {tipo_desc}*\n\n'
            f'Nombre:   {nombre}\n'
            f'DNI/RUC:  {doc}\n'
            f'Email:    {email_cl}\n'
            f'WA:       {numero}\n\n'
            f'⏱ Tiempo máximo de activación: *15 minutos*\n'
            f'Revisa el panel de KYC para activar la cuenta.'
        )
        send_text('51926011920', wa_msg)
        log.info(f'[WaBot] Notificación WA de registro enviada a admin para {numero}')
    except Exception as e:
        log.warning(f'[WaBot] No se pudo enviar WA de registro a admin: {e}')


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
                    '🔢 Ingresa el *número de operación* de tu comprobante bancario:'
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
                partes = texto.strip().split(None, 1)
                if len(partes) >= 2:
                    banco, num = partes[0].upper(), partes[1].strip()
                    session.cotiz_cuenta = f'{banco}|{num}'
                    client = _buscar_cliente(session.cotiz_doc)
                    if client:
                        _crear_op_y_confirmar(numero, session, client)
                    else:
                        send_text(numero, '⚠️ Error de sesión. Contacta a un asesor: *+51 910 624 404*')
                        session.estado = 'inicio'
                else:
                    send_text(numero,
                        'Formato incorrecto. Escribe el banco seguido del número de cuenta.\n\n'
                        'Ejemplo: *BCP 1234567890*'
                    )

            elif estado == 'esperando_numero_doc':
                # DNI/RUC durante el proceso de registro
                doc = texto.strip()
                esperado = 'DNI/CE (8-9 dígitos)' if session.tipo == 'natural' else 'RUC (11 dígitos)'
                valido = _es_dni(doc) if session.tipo == 'natural' else _es_ruc(doc)
                if valido:
                    session.cotiz_doc = doc
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
                else:
                    _bienvenida(numero, session.nombre)

            elif estado in ('esperando_dni_front', 'esperando_dni_back', 'esperando_ruc', 'esperando_email'):
                _flujo_recordatorio_registro(numero, estado)

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
