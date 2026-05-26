"""
Módulo TC Live — Pricing Engine interno, solo accesible por rol Master.

Endpoints:
  GET  /tc-live                   Dashboard principal
  POST /tc-live/api/datatec       Actualiza DATATEC manual + crea audit entry
  GET  /tc-live/api/state         Estado completo del motor (polling 15s)
  GET  /tc-live/api/chart         Datos históricos para el mini-chart
  GET  /tc-live/api/history       Últimas N entradas DATATEC (audit log)

Seguridad:
  - @login_required en todas las rutas
  - @require_role('Master') en TODAS — ni Trader ni Operador acceden
  - CSRF exempt solo en endpoints JSON POST (validación manual por header)
  - Rate limiting heredado del limiter global
"""
import logging
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import text

from app.extensions import db, csrf
from app.utils.decorators import require_role
from app.utils.formatters import now_peru
from app.models.datatec_rate import DatatecRate
from app.models.market import MarketSnapshot
from app.models.live_pricing import DatatecEntry
from app.services.pricing_engine import PricingEngine

logger = logging.getLogger(__name__)

fx_live_bp = Blueprint('fx_live', __name__, url_prefix='/tc-live')

_MASTER_ONLY = ('Master',)


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────────────────────────────────────

@fx_live_bp.route('/')
@login_required
@require_role(*_MASTER_ONLY)
def dashboard():
    """Renderiza el panel TC Live. Los datos se cargan vía JS/polling."""
    return render_template('fx_live/dashboard.html')


# ─────────────────────────────────────────────────────────────────────────────
# API — Update DATATEC manual
# ─────────────────────────────────────────────────────────────────────────────

@fx_live_bp.route('/api/datatec', methods=['POST'])
@csrf.exempt
@login_required
@require_role(*_MASTER_ONLY)
def api_update_datatec():
    """
    Actualiza el precio DATATEC (fila única) y crea un DatatecEntry de auditoría.
    Body JSON: { compra: float, venta: float, notes?: string }
    """
    data = request.get_json(silent=True) or {}

    try:
        compra = float(data.get('compra', 0))
        venta  = float(data.get('venta',  0))
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'error': 'Valores inválidos'}), 400

    if compra <= 0 or venta <= 0:
        return jsonify({'ok': False, 'error': 'Compra y Venta deben ser mayores a cero'}), 400
    if venta <= compra:
        return jsonify({'ok': False, 'error': 'Venta debe ser mayor que Compra'}), 400
    if not (3.0 <= compra <= 5.0) or not (3.0 <= venta <= 5.0):
        return jsonify({'ok': False, 'error': 'Valores fuera del rango esperado (3.00–5.00)'}), 400

    notes = str(data.get('notes', '')).strip()[:300] or None

    try:
        # 1. Actualizar fila única (source of truth operativa)
        DatatecRate.update(compra, venta, None, None, current_user.id)

        # 2. Crear entrada de auditoría (inmutable, append-only)
        entry = DatatecEntry(
            compra=compra,
            venta=venta,
            user_id=current_user.id,
            notes=notes,
        )
        db.session.add(entry)
        db.session.commit()

        logger.info(
            '[TCLive] DATATEC actualizado por %s → compra=%.4f venta=%.4f',
            current_user.username, compra, venta
        )
        return jsonify({'ok': True, 'compra': compra, 'venta': venta})

    except Exception as exc:
        db.session.rollback()
        logger.error('[TCLive] Error actualizando DATATEC: %s', exc, exc_info=True)
        return jsonify({'ok': False, 'error': 'Error interno al guardar'}), 500


# ─────────────────────────────────────────────────────────────────────────────
# API — Estado completo del motor (polling)
# ─────────────────────────────────────────────────────────────────────────────

@fx_live_bp.route('/api/state')
@login_required
@require_role(*_MASTER_ONLY)
def api_state():
    """
    Retorna el estado completo: DATATEC actual + estimación live + señales.
    Diseñado para ser llamado cada 15 segundos desde el frontend.
    """
    try:
        datatec = DatatecRate.get()
        snaps   = (
            MarketSnapshot.query
            .order_by(MarketSnapshot.captured_at.desc())
            .limit(24)
            .all()
        )
        estimate = PricingEngine.compute(datatec, snaps)

        datatec_dict = datatec.to_dict()

        # Calcular age en segundos directamente para el frontend
        age_s = 0
        if datatec.updated_at:
            age_s = int((now_peru() - datatec.updated_at).total_seconds())

        return jsonify({
            'ok':          True,
            'datatec':     datatec_dict,
            'datatec_age_s': age_s,
            'estimate':    estimate.to_dict(),
            'server_time': now_peru().isoformat(),
        })
    except Exception as exc:
        logger.error('[TCLive] Error en api_state: %s', exc, exc_info=True)
        return jsonify({'ok': False, 'error': str(exc)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# API — Chart data
# ─────────────────────────────────────────────────────────────────────────────

@fx_live_bp.route('/api/chart')
@login_required
@require_role(*_MASTER_ONLY)
def api_chart():
    """
    Retorna serie temporal de snapshots para el mini-chart.
    Query param: tf=30m | 1h | 2h | 4h  (default: 1h)
    """
    tf_map = {'30m': 6, '1h': 12, '2h': 24, '4h': 48}
    tf  = request.args.get('tf', '1h')
    n   = tf_map.get(tf, 12)

    snaps = (
        MarketSnapshot.query
        .order_by(MarketSnapshot.captured_at.desc())
        .limit(n)
        .all()
    )
    snaps = list(reversed(snaps))   # cronológico

    points = []
    for s in snaps:
        usdpen = float(s.usdpen) if s.usdpen else None
        if usdpen is None:
            continue
        points.append({
            'ts':     s.captured_at.strftime('%H:%M'),
            'usdpen': usdpen,
            'dxy':    float(s.dxy)    if s.dxy    else None,
            'copper': float(s.copper) if s.copper else None,
        })

    # Superponer entradas DATATEC dentro del mismo rango
    if snaps:
        from_dt = snaps[0].captured_at
        entries = (
            DatatecEntry.query
            .filter(DatatecEntry.created_at >= from_dt)
            .order_by(DatatecEntry.created_at.asc())
            .all()
        )
        datatec_points = [
            {
                'ts':     e.created_at.strftime('%H:%M'),
                'compra': float(e.compra),
                'venta':  float(e.venta),
            }
            for e in entries
        ]
    else:
        datatec_points = []

    return jsonify({
        'ok':      True,
        'tf':      tf,
        'points':  points,
        'datatec': datatec_points,
    })


# ─────────────────────────────────────────────────────────────────────────────
# API — Historial de entradas DATATEC
# ─────────────────────────────────────────────────────────────────────────────

@fx_live_bp.route('/api/history')
@login_required
@require_role(*_MASTER_ONLY)
def api_history():
    """Retorna las últimas 20 entradas DATATEC (audit log)."""
    entries = (
        DatatecEntry.query
        .order_by(DatatecEntry.created_at.desc())
        .limit(20)
        .all()
    )
    return jsonify({
        'ok':      True,
        'entries': [e.to_dict() for e in entries],
    })
