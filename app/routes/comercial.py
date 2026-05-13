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
)

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


# ── API: enviar email de precios a un cliente ─────────────────────────────────

@comercial_bp.route("/enviar-precio/<int:client_id>", methods=["POST"])
@login_required
@require_role("Master", "Trader")
@csrf.exempt
def enviar_precio(client_id):
    c = Client.query.get_or_404(client_id)

    compra = request.json.get("compra", "").strip()
    venta  = request.json.get("venta", "").strip()

    if not compra or not venta:
        return jsonify({"ok": False, "msg": "Ingresa compra y venta"}), 400

    if not c.email:
        return jsonify({"ok": False, "msg": "El cliente no tiene email registrado"}), 400

    sender_email = current_user.email
    nombre_completo, cargo = _get_trader_info(sender_email, current_user.role)

    try:
        firma_gmail = _get_firma_gmail(sender_email)
        if firma_gmail:
            firma = f'<div style="margin-top:16px">{firma_gmail}</div>'
        else:
            firma = FIRMA_HTML.replace("{trader_nombre}", nombre_completo)

        nombre_saludo = (c.full_name or c.razon_social or "estimado cliente").split()[0].capitalize()
        ticker = _build_ticker(compra, venta)

        html = CUERPO_PRECIO.format(
            header=HEADER_HTML,
            nombre=nombre_saludo,
            ticker=ticker,
            bancos=BANCOS_HTML,
            firma=firma,
            pie=PIE,
        )

        _send_via_gmail_api(sender_email, c.email, "QoriCash - Tipo de cambio del día", html)

        return jsonify({"ok": True, "msg": f"Email enviado a {c.email}"})

    except Exception as e:
        current_app.logger.error(f"[Comercial] Error enviando email a {c.email}: {e}")
        return jsonify({"ok": False, "msg": str(e)}), 500
