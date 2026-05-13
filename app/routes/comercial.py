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
from sqlalchemy import func, distinct

from app.extensions import db, csrf
from app.models.client import Client
from app.models.operation import Operation
from app.models.exchange_rate import ExchangeRate
from app.models.user import User
from app.utils.decorators import require_role

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
    """
    # Subconsulta: clientes con al menos 1 operación completada (del trader si aplica)
    q = (
        db.session.query(Client)
        .join(Operation, Operation.client_id == Client.id)
        .filter(Operation.status == 'Completada')
    )
    if trader_id:
        q = q.filter(Operation.user_id == trader_id)

    clientes = q.distinct().all()

    resultado = []
    for c in clientes:
        ops_q = c.operations.filter_by(status='Completada')
        if trader_id:
            ops_q = ops_q.filter_by(user_id=trader_id)
        ops = ops_q.all()

        if not ops:
            continue

        tipo = _clasificar_cliente(ops)

        if tipo_filtro and tipo_filtro != 'Todos' and tipo != tipo_filtro:
            continue

        ultima_op = max(ops, key=lambda o: o.created_at)
        total_usd = sum(float(o.amount_usd or 0) for o in ops)

        # Teléfonos: puede haber múltiples separados por ;
        phones = [p.strip() for p in (c.phone or '').split(';') if p.strip()]
        # Limpiar a solo dígitos para wa.me (primer número)
        wa_number = ''
        if phones:
            digits = ''.join(filter(str.isdigit, phones[0]))
            if digits and not digits.startswith('51'):
                digits = '51' + digits
            wa_number = digits

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
            'total_ops': len(ops),
            'total_usd': total_usd,
            'ultima_op': ultima_op.created_at,
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

    clientes = _get_cartera(trader_id=trader_id, tipo_filtro=tipo_filtro)

    # Conteos para las pestañas
    todos = _get_cartera(trader_id=trader_id)
    cnt = {
        "Todos": len(todos),
        "Compra": sum(1 for c in todos if c["tipo"] == "Compra"),
        "Venta":  sum(1 for c in todos if c["tipo"] == "Venta"),
        "Mixto":  sum(1 for c in todos if c["tipo"] == "Mixto"),
    }

    # Tipo de cambio actual
    rate = ExchangeRate.query.order_by(ExchangeRate.updated_at.desc()).first()

    return render_template(
        "comercial/index.html",
        clientes=clientes,
        tipo_filtro=tipo_filtro,
        cnt=cnt,
        rate=rate,
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

    return CUERPO_PRECIO.format(
        header=header,
        mensaje=mensaje,
        ticker=ticker,
        bancos=BANCOS_HTML,
        firma=firma,
        pie=PIE,
    )


# ── API: preview del email de precios ────────────────────────────────────────

@comercial_bp.route("/preview-precio/<int:client_id>")
@login_required
@require_role("Master", "Trader")
def preview_precio(client_id):
    c = Client.query.get_or_404(client_id)

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
    c = Client.query.get_or_404(client_id)

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

        return jsonify({"ok": True, "msg": f"Email enviado a {c.email}"})

    except Exception as e:
        current_app.logger.error(f"[Comercial] Error enviando email a {c.email}: {e}")
        return jsonify({"ok": False, "msg": str(e)}), 500
