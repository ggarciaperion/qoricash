"""
Módulo Comercial — QoriCash Trading V2
Cartera de clientes por trader con acciones de contacto rápido.
Visible para: Master, Trader
"""
import base64
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from sqlalchemy import func, distinct, case as sa_case

import eventlet
from app.extensions import db, csrf
from app.models.client import Client
from app.models.operation import Operation
from app.models.exchange_rate import ExchangeRate
from app.models.user import User
from app.models.comercial_envio import ComercialEnvio
from app.utils.decorators import require_role
from app.utils.formatters import now_peru

# ── Importar utilidades de email desde prospeccion ───────────────────────────
from app.routes.prospeccion import (
    _send_via_gmail_api,
    _get_trader_info,
    _get_firma_gmail,
    _build_ticker,
    CUERPO_PRECIO,
    HEADER_HTML,
    BANCOS_HTML,
    PIE,
    FIRMA_HTML,
    LOGO_URL,
)

import os
import re

# ── WhatsApp por trader ───────────────────────────────────────────────────────
# Formato: email → (número_wa sin "+", texto_display)
# Agrega aquí cada nuevo trader con su número personal.
_TRADER_WHATSAPP: dict[str, tuple[str, str]] = {
    "ggarcia@qoricash.pe":  ("51926011920", "+51 926 011 920"),
    "gerencia@qoricash.pe": ("51926011920", "+51 926 011 920"),
    "luacosta@qoricash.pe": ("51905566165", "+51 905 566 165"),
}
_WA_DEFAULT = ("51926011920", "+51 926 011 920")  # fallback para nuevos traders sin configurar

# ── Logo en base64 (cacheado) para el preview ─────────────────────────────────
_logo_b64_cache: str = ""

def _get_logo_data_uri() -> str:
    """Devuelve el logo como data:image URI para el preview del iframe."""
    global _logo_b64_cache
    if _logo_b64_cache:
        return _logo_b64_cache
    # Intentar desde static local
    candidates = [
        os.path.join(os.path.dirname(__file__), '..', 'static', 'images', 'logo-email.png'),
        os.path.join(os.path.dirname(__file__), '..', 'static', 'images', 'Logofinal.png'),
    ]
    for path in candidates:
        path = os.path.normpath(path)
        if os.path.exists(path):
            with open(path, 'rb') as f:
                _logo_b64_cache = "data:image/png;base64," + base64.b64encode(f.read()).decode()
            return _logo_b64_cache
    # Fallback: usar la URL pública tal cual
    return LOGO_URL


def _html_para_preview(html: str) -> str:
    """
    Prepara el HTML para mostrarse en el iframe del preview:
    - Reemplaza la URL del logo por base64 inline para que cargue sin depender de internet.
    - Elimina referencias cid: de Gmail (que solo funcionan en clientes de correo).
    """
    logo_uri = _get_logo_data_uri()
    # Reemplazar URL del logo por base64
    html = html.replace(LOGO_URL, logo_uri)
    # Eliminar src con cid: (imágenes de Gmail embebidas que no se pueden resolver)
    html = re.sub(r'src="cid:[^"]*"', 'src=""', html)
    html = re.sub(r"src='cid:[^']*'", "src=''", html)
    return html

comercial_bp = Blueprint("comercial", __name__, url_prefix="/comercial")

LIMITE_LOTE   = 10   # máx. por envío masivo
LIMITE_DIARIO = 50   # máx. por usuario por día


def _count_hoy(user_id: int) -> int:
    """Emails de TC enviados hoy desde Comercial por este usuario."""
    from sqlalchemy import func
    hoy = now_peru().date()
    return (
        db.session.query(func.count(ComercialEnvio.id))
        .filter(
            ComercialEnvio.user_id == user_id,
            func.date(ComercialEnvio.sent_at) == hoy,
        )
        .scalar() or 0
    )


def _ultimo_tc_map(client_ids: list, user_id: int) -> dict:
    """Devuelve {client_id: datetime} con el último envío de TC por cliente."""
    if not client_ids:
        return {}
    from sqlalchemy import func
    rows = (
        db.session.query(
            ComercialEnvio.client_id,
            func.max(ComercialEnvio.sent_at).label('ultimo'),
        )
        .filter(ComercialEnvio.client_id.in_(client_ids))
        .group_by(ComercialEnvio.client_id)
        .all()
    )
    return {r.client_id: r.ultimo for r in rows}


def _clasificar_cliente(ops_completadas):
    """Devuelve 'Compra', 'Venta' o 'Mixto' según los tipos de operaciones completadas."""
    tipos = {op.operation_type for op in ops_completadas}
    if 'Compra' in tipos and 'Venta' in tipos:
        return 'Mixto'
    elif 'Compra' in tipos:
        return 'Compra'
    elif 'Venta' in tipos:
        return 'Venta'
    return 'Mixto'


def _get_cartera(trader_id=None, tipo_filtro=None):
    """
    Devuelve lista de clientes con operaciones completadas.
    - trader_id=None → Master ve todos.
    - tipo_filtro: 'Compra' | 'Venta' | 'Mixto' | None (todos)

    Optimizado: 3 queries fijas en lugar de N+1 (1 por cliente).
    Query 1: agregación de stats por cliente (GROUP BY)
    Query 2: batch load de objetos Client (IN)
    Query 3: batch load de último envío de TC (IN)
    """
    op_filters = [Operation.status == 'Completada']
    if trader_id:
        op_filters.append(Operation.user_id == trader_id)

    # Expresión para pips: usa pips si existe, si no calcula de exchange_rate y base_rate
    pips_expr = sa_case(
        (Operation.pips.isnot(None), Operation.pips),
        else_=sa_case(
            (
                (Operation.exchange_rate.isnot(None)) & (Operation.base_rate.isnot(None)),
                func.abs(Operation.exchange_rate - Operation.base_rate) * 1000
            ),
            else_=None
        )
    )

    # Query 1: una sola pasada con GROUP BY — stats + tipo en SQL
    agg = db.session.query(
        Operation.client_id,
        func.count(Operation.id).label('total_ops'),
        func.sum(Operation.amount_usd).label('total_usd'),
        func.max(Operation.created_at).label('ultima_op'),
        func.avg(pips_expr).label('avg_spread'),
        func.bool_or(Operation.operation_type == 'Compra').label('has_compra'),
        func.bool_or(Operation.operation_type == 'Venta').label('has_venta'),
    ).filter(*op_filters).group_by(Operation.client_id).all()

    if not agg:
        return []

    # Clasificar tipo en Python (evita subconsulta adicional)
    def _tipo(row):
        if row.has_compra and row.has_venta:
            return 'Mixto'
        if row.has_compra:
            return 'Compra'
        if row.has_venta:
            return 'Venta'
        return 'Mixto'

    # Aplicar filtro de tipo antes de cargar clientes
    if tipo_filtro and tipo_filtro != 'Todos':
        agg = [r for r in agg if _tipo(r) == tipo_filtro]

    if not agg:
        return []

    # Query 2: batch load de todos los clientes necesarios
    client_ids = [r.client_id for r in agg]
    clients_map = {c.id: c for c in Client.query.filter(Client.id.in_(client_ids)).all()}

    # Query 3: batch load de último envío de TC
    tc_rows = (
        db.session.query(
            ComercialEnvio.client_id,
            func.max(ComercialEnvio.sent_at).label('ultimo'),
        )
        .filter(ComercialEnvio.client_id.in_(client_ids))
        .group_by(ComercialEnvio.client_id)
        .all()
    )
    tc_map = {r.client_id: r.ultimo for r in tc_rows}

    resultado = []
    for r in agg:
        c = clients_map.get(r.client_id)
        if not c:
            continue

        tipo = _tipo(r)

        # Teléfonos: puede haber múltiples separados por ;
        phones = [p.strip() for p in (c.phone or '').split(';') if p.strip()]
        wa_number = ''
        if phones:
            digits = ''.join(filter(str.isdigit, phones[0]))
            if digits and not digits.startswith('51'):
                digits = '51' + digits
            wa_number = digits

        avg_spread = round(float(r.avg_spread)) if r.avg_spread is not None else None

        resultado.append({
            'id': c.id,
            'full_name': c.full_name or c.razon_social or c.dni,
            'document_type': c.document_type,
            'dni': c.dni,
            'email': c.email,
            'phone': phones[0] if phones else '',
            'phones': phones,
            'wa_number': wa_number,
            'tipo': tipo,
            'total_ops': int(r.total_ops),
            'total_usd': float(r.total_usd or 0),
            'ultima_op': r.ultima_op,
            'avg_spread': avg_spread,
            'ultimo_tc': tc_map.get(c.id),
        })

    # Ordenar: más reciente primero
    resultado.sort(key=lambda x: x['ultima_op'], reverse=True)
    return resultado


# ── Vista principal ───────────────────────────────────────────────────────────

@comercial_bp.route("/")
@login_required
@require_role("Master", "Trader")
def index():
    tipo_filtro = request.args.get("tipo", "Todos")
    if tipo_filtro not in ("Todos", "Compra", "Venta", "Mixto"):
        tipo_filtro = "Todos"

    trader_id = None if current_user.role == "Master" else current_user.id

    # Una sola llamada: filtramos en Python para evitar la segunda query completa
    todos = _get_cartera(trader_id=trader_id)
    cnt = {
        "Todos": len(todos),
        "Compra": sum(1 for c in todos if c["tipo"] == "Compra"),
        "Venta":  sum(1 for c in todos if c["tipo"] == "Venta"),
        "Mixto":  sum(1 for c in todos if c["tipo"] == "Mixto"),
    }
    if tipo_filtro != "Todos":
        clientes = [c for c in todos if c["tipo"] == tipo_filtro]
    else:
        clientes = todos

    # Tipo de cambio actual
    rate = ExchangeRate.query.order_by(ExchangeRate.updated_at.desc()).first()

    envios_hoy = _count_hoy(current_user.id)

    return render_template(
        "comercial/index.html",
        clientes=clientes,
        tipo_filtro=tipo_filtro,
        cnt=cnt,
        rate=rate,
        envios_hoy=envios_hoy,
        limite_diario=LIMITE_DIARIO,
        limite_lote=LIMITE_LOTE,
    )


# ── Helpers compartidos ───────────────────────────────────────────────────────

def _build_ticker_comercial(compra, venta, tipo="Mixto"):
    """
    Ticker de precios con resaltado según el tipo de operación del cliente.
    - Compra: el cliente compra dólares → QoriCash le VENDE → resaltar celda Vendemos
    - Venta:  el cliente vende dólares  → QoriCash le COMPRA → resaltar celda Compramos
    - Mixto:  ambas celdas neutras.
    """
    # Estilos de celda destacada vs neutra
    highlight_compra = tipo == 'Compra'
    highlight_venta  = tipo == 'Venta'

    # ── Compramos ────────────────────────────────────────────────────────────
    if highlight_compra:
        td_compra = (
            'padding:20px 28px;border-right:1.5px solid #BFDBFE;text-align:center;'
            'background:#EFF6FF;'
        )
        label_compra = (
            'margin:0 0 4px;font-size:9px;font-weight:700;color:#2563EB;'
            'text-transform:uppercase;letter-spacing:1.8px;'
        )
        precio_compra = (
            'margin:0;font-size:36px;font-weight:800;color:#1D4ED8;'
            'letter-spacing:-1px;line-height:1;'
        )
        badge_compra = (
            '<br><span style="display:inline-block;margin-top:6px;font-size:9px;font-weight:700;'
            'color:#fff;background:#2563EB;border-radius:20px;padding:2px 10px;'
            'letter-spacing:.6px;">Tasa preferencial</span>'
        )
    else:
        td_compra     = 'padding:24px 28px;border-right:1.5px solid #E2E8F0;text-align:center;'
        label_compra  = 'margin:0 0 6px;font-size:9px;font-weight:700;color:#94A3B8;text-transform:uppercase;letter-spacing:1.8px;'
        precio_compra = 'margin:0;font-size:34px;font-weight:800;color:#0D1B2A;letter-spacing:-1px;line-height:1;'
        badge_compra  = ''

    # ── Vendemos ─────────────────────────────────────────────────────────────
    if highlight_venta:
        td_venta = (
            'padding:20px 28px;text-align:center;'
            'background:#F0FDF4;'
        )
        label_venta = (
            'margin:0 0 4px;font-size:9px;font-weight:700;color:#16A34A;'
            'text-transform:uppercase;letter-spacing:1.8px;'
        )
        precio_venta = (
            'margin:0;font-size:36px;font-weight:800;color:#15803D;'
            'letter-spacing:-1px;line-height:1;'
        )
        badge_venta = (
            '<br><span style="display:inline-block;margin-top:6px;font-size:9px;font-weight:700;'
            'color:#fff;background:#16A34A;border-radius:20px;padding:2px 10px;'
            'letter-spacing:.6px;">Tasa preferencial</span>'
        )
    else:
        td_venta     = 'padding:24px 28px;text-align:center;'
        label_venta  = 'margin:0 0 6px;font-size:9px;font-weight:700;color:#94A3B8;text-transform:uppercase;letter-spacing:1.8px;'
        precio_venta = 'margin:0;font-size:34px;font-weight:800;color:#16a34a;letter-spacing:-1px;line-height:1;'
        badge_venta  = ''

    return f"""\
<tr>
  <td style="padding:20px 28px;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0"
      style="border:1.5px solid #E2E8F0;border-radius:10px;overflow:hidden;">
      <tr>
        <td width="50%" style="{td_compra}">
          <p style="{label_compra}">Compramos</p>
          <p style="{precio_compra}">S/. {compra}</p>
          <p style="margin:8px 0 0;font-size:10px;color:#94A3B8;">por d&oacute;lar &middot; USD</p>
          {badge_compra}
        </td>
        <td width="50%" style="{td_venta}">
          <p style="{label_venta}">Vendemos</p>
          <p style="{precio_venta}">S/. {venta}</p>
          <p style="margin:8px 0 0;font-size:10px;color:#94A3B8;">por d&oacute;lar &middot; USD</p>
          {badge_venta}
        </td>
      </tr>
      <tr>
        <td colspan="2" style="padding:10px 28px;border-top:1.5px solid #E2E8F0;text-align:center;">
          <span style="font-size:10px;font-weight:600;color:#64748B;letter-spacing:0.3px;">
            &bull;&nbsp; Operaci&oacute;n en minutos &nbsp;&middot;&nbsp; Sin costo de transferencia
          </span><br>
          <span style="font-size:9.5px;color:#94A3B8;font-style:italic;">
            Precios del momento &mdash; sujetos a variaci&oacute;n por volatilidad del mercado.
          </span>
        </td>
      </tr>
    </table>
  </td>
</tr>"""


_SUFIJOS_LEGALES = {
    'SAC', 'SA', 'EIRL', 'SRL', 'SAS', 'SAA', 'SCRL', 'SCS',
    'S.A.C.', 'S.A.', 'E.I.R.L.', 'S.R.L.', 'S.A.S.',
}

def _saludo_empresa(razon_social: str) -> str:
    """Devuelve un saludo apropiado para una empresa: razón social limpia o abreviada."""
    if not razon_social:
        return "estimado cliente"
    # Quitar sufijos legales al final
    partes = razon_social.strip().split()
    while partes and partes[-1].upper().rstrip('.') in {s.rstrip('.') for s in _SUFIJOS_LEGALES}:
        partes.pop()
    nombre_limpio = ' '.join(partes).title() if partes else razon_social.title()
    # Si es corto (≤ 28 chars) usarlo tal cual, si no tomar las 3 primeras palabras significativas
    if len(nombre_limpio) <= 28:
        return nombre_limpio
    palabras = nombre_limpio.split()
    return ' '.join(palabras[:3]) if len(palabras) >= 3 else nombre_limpio


def _nombre_saludo_cliente(c) -> str:
    """Primer nombre para persona natural; razón social limpia/abreviada para empresa."""
    es_empresa = (getattr(c, 'document_type', '') or '').upper() == 'RUC'
    if es_empresa:
        return _saludo_empresa(c.razon_social or c.full_name or '')
    # Persona natural → primer nombre del campo `nombres` (evita tomar el apellido)
    nombres = (getattr(c, 'nombres', None) or '').strip()
    if nombres:
        return nombres.split()[0].capitalize()
    # Fallback: si no hay campo nombres separado, descartamos apellidos conocidos
    full = (c.full_name or '').strip()
    ap_pat = (getattr(c, 'apellido_paterno', None) or '').strip().upper()
    ap_mat = (getattr(c, 'apellido_materno', None) or '').strip().upper()
    for palabra in full.split():
        if palabra.upper() not in (ap_pat, ap_mat) and palabra:
            return palabra.capitalize()
    return (full.split()[0].capitalize() if full else 'estimado cliente')


def _build_mensaje_personalizado(tipo):
    """Bloque HTML con mensaje contextual según el tipo de operación del cliente."""
    if tipo == 'Compra':
        # Cliente compra dólares → le conviene cuando el dólar baja
        return """\
<tr>
  <td style="padding:0 28px 4px;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0"
      style="background:#EFF6FF;border-left:4px solid #2563EB;border-radius:0 8px 8px 0;padding:14px 18px;">
      <tr>
        <td>
          <p style="margin:0 0 4px;font-size:10px;font-weight:800;color:#1D4ED8;
                    text-transform:uppercase;letter-spacing:1px;">
            Oportunidad para usted
          </p>
          <p style="margin:0;font-size:12px;color:#1E3A5F;line-height:1.6;">
            El tipo de cambio <strong>ha bajado</strong>, es un buen momento para adquirir
            dólares antes de que el mercado recupere y maximizar el valor de su inversión.
          </p>
        </td>
      </tr>
    </table>
  </td>
</tr>"""
    elif tipo == 'Venta':
        # Cliente vende dólares → le conviene cuando el dólar sube
        return """\
<tr>
  <td style="padding:0 28px 4px;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0"
      style="background:#F0FDF4;border-left:4px solid #16A34A;border-radius:0 8px 8px 0;padding:14px 18px;">
      <tr>
        <td>
          <p style="margin:0 0 4px;font-size:10px;font-weight:800;color:#15803D;
                    text-transform:uppercase;letter-spacing:1px;">
            Oportunidad para usted
          </p>
          <p style="margin:0;font-size:12px;color:#14532D;line-height:1.6;">
            El tipo de cambio <strong>ha subido</strong>. Es un excelente momento para vender
            sus dólares y obtener más soles por cada dólar antes de que el mercado corrija.
          </p>
        </td>
      </tr>
    </table>
  </td>
</tr>"""
    else:
        # Mixto → menciona ambas opciones
        return """\
<tr>
  <td style="padding:0 28px 4px;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0"
      style="background:#FAFAFA;border-left:4px solid #5CB85C;border-radius:0 8px 8px 0;padding:14px 18px;">
      <tr>
        <td>
          <p style="margin:0 0 4px;font-size:10px;font-weight:800;color:#5CB85C;
                    text-transform:uppercase;letter-spacing:1px;">
            Tasas vigentes del día
          </p>
          <p style="margin:0;font-size:12px;color:#1E293B;line-height:1.6;">
            Tanto para <strong>compra</strong> como para <strong>venta</strong> de dólares,
            contamos con las mejores tasas del mercado. Contáctenos para coordinar
            su operación de forma inmediata.
          </p>
        </td>
      </tr>
    </table>
  </td>
</tr>"""


def _build_email_html(c, compra, venta, sender_email, nombre_completo, cargo="Trader", tipo="Mixto"):
    """Construye el HTML del correo de precios para un cliente."""
    from datetime import datetime as _dt
    fecha = _dt.now().strftime("%d/%m/%Y")

    firma_gmail = _get_firma_gmail(sender_email)
    if firma_gmail:
        firma = f'<tr><td style="padding:16px 28px;border-top:1px solid #F1F5F9;background:#FAFAFA;">{firma_gmail}</td></tr>'
    else:
        firma = FIRMA_HTML.replace("{trader_nombre}", nombre_completo).replace("{trader_cargo}", cargo)

    nombre_saludo = _nombre_saludo_cliente(c)
    ticker  = _build_ticker_comercial(compra, venta, tipo)
    mensaje = _build_mensaje_personalizado(tipo)
    header  = HEADER_HTML.replace("{fecha}", fecha).replace("{nombre}", nombre_saludo)

    # Número de WhatsApp del trader que envía el correo
    wa_num, wa_display = _TRADER_WHATSAPP.get(sender_email.lower(), _WA_DEFAULT)

    html = CUERPO_PRECIO.format(
        header=header,
        mensaje=mensaje,
        ticker=ticker,
        bancos=BANCOS_HTML,
        firma=firma,
        pie=PIE,
    )
    # Reemplazar el número hardcodeado por el del trader correspondiente
    html = html.replace("51926011920", wa_num)
    html = html.replace("+51 926 011 920", wa_display)
    return html


# ── API: preview del email de precios ────────────────────────────────────────

@comercial_bp.route("/preview-precio/<int:client_id>")
@login_required
@require_role("Master", "Trader")
def preview_precio(client_id):
    c = db.get_or_404(Client, client_id)

    compra = request.args.get("compra", "").strip()
    venta  = request.args.get("venta", "").strip()
    tipo   = request.args.get("tipo", "Mixto").strip()
    if tipo not in ("Compra", "Venta", "Mixto"):
        tipo = "Mixto"

    if not compra or not venta:
        return jsonify({"ok": False, "msg": "Ingresa compra y venta"}), 400

    sender_email = current_user.email
    nombre_completo, cargo = _get_trader_info(sender_email, current_user.role)

    try:
        html = _build_email_html(c, compra, venta, sender_email, nombre_completo, cargo, tipo)
        return jsonify({"ok": True, "html": _html_para_preview(html)})
    except Exception as e:
        current_app.logger.error(f"[Comercial] Error generando preview para {c.email}: {e}")
        return jsonify({"ok": False, "msg": str(e)}), 500


# ── API: enviar email de precios a un cliente ─────────────────────────────────

@comercial_bp.route("/enviar-precio/<int:client_id>", methods=["POST"])
@login_required
@require_role("Master", "Trader")
@csrf.exempt
def enviar_precio(client_id):
    c = db.get_or_404(Client, client_id)

    data   = request.json or {}
    compra = data.get("compra", "").strip()
    venta  = data.get("venta", "").strip()
    tipo   = data.get("tipo", "Mixto").strip()
    html   = data.get("html", "").strip()  # HTML editado desde el borrador
    if tipo not in ("Compra", "Venta", "Mixto"):
        tipo = "Mixto"

    if not c.email:
        return jsonify({"ok": False, "msg": "El cliente no tiene email registrado"}), 400

    sender_email = current_user.email
    nombre_completo, cargo = _get_trader_info(sender_email, current_user.role)

    try:
        if not html:
            if not compra or not venta:
                return jsonify({"ok": False, "msg": "Ingresa compra y venta"}), 400
            html = _build_email_html(c, compra, venta, sender_email, nombre_completo, cargo, tipo)

        _send_via_gmail_api(sender_email, c.email, "QoriCash - Tipo de cambio del día", html)

        # Registrar envío
        db.session.add(ComercialEnvio(
            client_id=c.id,
            user_id=current_user.id,
            compra=compra or None,
            venta=venta or None,
        ))
        db.session.commit()

        return jsonify({"ok": True, "msg": f"Email enviado a {c.email}"})

    except Exception as e:
        current_app.logger.error(f"[Comercial] Error enviando email a {c.email}: {e}")
        return jsonify({"ok": False, "msg": str(e)}), 500


# ── API: envío masivo de TC ───────────────────────────────────────────────────

@comercial_bp.route("/enviar-masivo", methods=["POST"])
@login_required
@require_role("Master", "Trader")
@csrf.exempt
def enviar_masivo():
    data       = request.json or {}
    client_ids = data.get("client_ids", [])
    compra     = data.get("compra", "").strip()
    venta      = data.get("venta", "").strip()

    if not compra or not venta:
        return jsonify({"ok": False, "msg": "Ingresa compra y venta"}), 400
    if not client_ids:
        return jsonify({"ok": False, "msg": "Selecciona al menos un cliente"}), 400
    if len(client_ids) > LIMITE_LOTE:
        return jsonify({"ok": False, "msg": f"Máximo {LIMITE_LOTE} por lote"}), 400

    # Verificar cuota diaria
    enviados_hoy = _count_hoy(current_user.id)
    restantes    = LIMITE_DIARIO - enviados_hoy
    if restantes <= 0:
        return jsonify({"ok": False, "msg": f"Límite diario de {LIMITE_DIARIO} emails alcanzado"}), 429
    if len(client_ids) > restantes:
        client_ids = client_ids[:restantes]

    sender_email = current_user.email
    nombre_completo, cargo = _get_trader_info(sender_email, current_user.role)

    resultados = []
    for cid in client_ids:
        c = db.session.get(Client, cid)
        if not c:
            resultados.append({"id": cid, "nombre": "—", "ok": False, "msg": "Cliente no encontrado"})
            continue
        if not c.email:
            resultados.append({"id": cid, "nombre": c.full_name or str(cid), "ok": False, "msg": "Sin email"})
            continue

        tipo = _clasificar_cliente(
            Operation.query.filter_by(client_id=c.id, status='Completada').all()
        )

        try:
            html = _build_email_html(c, compra, venta, sender_email, nombre_completo, cargo, tipo)
            _send_via_gmail_api(sender_email, c.email, "QoriCash - Tipo de cambio del día", html)
            db.session.add(ComercialEnvio(
                client_id=c.id, user_id=current_user.id, compra=compra, venta=venta
            ))
            resultados.append({"id": cid, "nombre": c.full_name or str(cid), "ok": True, "msg": c.email})
        except Exception as e:
            current_app.logger.error(f"[Comercial Masivo] Error enviando a {c.email}: {e}")
            resultados.append({"id": cid, "nombre": c.full_name or str(cid), "ok": False, "msg": str(e)})

        eventlet.sleep(1)  # pausa cooperativa — no bloquea el worker

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

    ok_count  = sum(1 for r in resultados if r["ok"])
    err_count = len(resultados) - ok_count
    return jsonify({
        "ok": True,
        "enviados": ok_count,
        "errores": err_count,
        "resultados": resultados,
        "envios_hoy": _count_hoy(current_user.id),
    })
