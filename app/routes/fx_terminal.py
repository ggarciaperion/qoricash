"""
FX Terminal — Centro de inteligencia de mercado USD/PEN.
Solo accesible por rol Master.

Endpoints:
  GET  /fx-terminal/              Dashboard principal
  GET  /fx-terminal/api/snap      Snapshot consolidado (Yahoo + Fintechs + DATATEC)
  POST /fx-terminal/api/datatec   Actualiza DATATEC manual
  GET  /fx-terminal/api/history   Últimas 20 entradas DATATEC
"""
import logging
import statistics
from datetime import timedelta, time as dt_time

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from app.extensions import db, csrf, socketio
from app.utils.decorators import require_role
from app.utils.formatters import now_peru
from app.models.datatec_rate import DatatecRate
from app.models.market import MarketSnapshot
from app.models.live_pricing import DatatecEntry
from app.models.competitor_rate import CompetitorRateCurrent, Competitor

logger = logging.getLogger(__name__)

fx_terminal_bp = Blueprint('fx_terminal', __name__, url_prefix='/fx-terminal')
_MASTER_ONLY = ('Master',)

_MARKET_OPEN  = dt_time(9,  0)
_MARKET_CLOSE = dt_time(13, 30)
_FINTECH_STALE_MIN = 45   # ignorar fintechs sin actualizar en más de N minutos


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _f(v):
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _market_status() -> dict:
    now  = now_peru()
    t    = now.time()
    wday = now.weekday()   # 0=lun … 6=dom
    is_open = (wday < 5) and (_MARKET_OPEN <= t < _MARKET_CLOSE)

    if is_open:
        close_dt = now.replace(hour=13, minute=30, second=0, microsecond=0)
        mins = max(0, int((close_dt - now).total_seconds() / 60))
        return {'open': is_open, 'mins_to_event': mins,
                'next_event': 'cierre', 'next_event_hm': '13:30', 'weekday': wday}
    else:
        if wday < 5 and t < _MARKET_OPEN:
            open_dt = now.replace(hour=9, minute=0, second=0, microsecond=0)
        else:
            days_ahead = 1 if wday < 4 else (7 - wday)
            open_dt = (now + timedelta(days=days_ahead)).replace(
                hour=9, minute=0, second=0, microsecond=0)
        mins = max(0, int((open_dt - now).total_seconds() / 60))
        return {'open': is_open, 'mins_to_event': mins,
                'next_event': 'apertura', 'next_event_hm': '09:00', 'weekday': wday}


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────────────────────────────────────

@fx_terminal_bp.route('/')
@login_required
@require_role(*_MASTER_ONLY)
def dashboard():
    return render_template('fx_terminal/dashboard.html')


# ─────────────────────────────────────────────────────────────────────────────
# API — Snapshot consolidado
# ─────────────────────────────────────────────────────────────────────────────

@fx_terminal_bp.route('/api/snap')
@login_required
@require_role(*_MASTER_ONLY)
def api_snap():
    """
    Retorna snapshot consolidado:
      - Yahoo Finance (último MarketSnapshot)
      - Fintechs Peru (CompetitorRateCurrent activos y frescos)
      - DATATEC manual (DatatecRate)
      - Consenso calculado
      - Estado de mercado
    """
    try:
        # ── Yahoo Finance ─────────────────────────────────────────────────
        snap = (MarketSnapshot.query
                .order_by(MarketSnapshot.captured_at.desc())
                .first())

        yahoo = None
        if snap:
            yahoo = {
                'usdpen':          _f(snap.usdpen),
                'usdpen_chg_pct':  _f(snap.usdpen_chg_pct),
                'dxy':             _f(snap.dxy),
                'dxy_chg_pct':     _f(snap.dxy_chg_pct),
                'copper':          _f(snap.copper),
                'copper_chg_pct':  _f(snap.copper_chg_pct),
                'gold':            _f(snap.gold),
                'gold_chg_pct':    _f(snap.gold_chg_pct),
                'vix':             _f(snap.vix),
                'vix_chg_pct':     _f(snap.vix_chg_pct),
                'captured_at':     snap.captured_at.strftime('%H:%M'),
            }

        # ── Fintechs Peru ─────────────────────────────────────────────────
        stale_cutoff = now_peru() - timedelta(minutes=_FINTECH_STALE_MIN)
        currents = (
            CompetitorRateCurrent.query
            .join(Competitor)
            .filter(Competitor.is_active == True)    # noqa: E712
            .filter(CompetitorRateCurrent.scrape_ok == True)  # noqa: E712
            .filter(CompetitorRateCurrent.updated_at >= stale_cutoff)
            .all()
        )

        fintech_list = sorted([
            {
                'name':    c.competitor.name,
                'slug':    c.competitor.slug,
                'buy':     _f(c.buy_rate),
                'sell':    _f(c.sell_rate),
                'spread':  round(_f(c.sell_rate) - _f(c.buy_rate), 4)
                           if c.sell_rate and c.buy_rate else None,
                'updated': c.updated_at.strftime('%H:%M'),
            }
            for c in currents if c.sell_rate and c.buy_rate
        ], key=lambda x: x['sell'])

        fintechs = {
            'count':       len(fintech_list),
            'median_buy':  None,
            'median_sell': None,
            'min_sell':    None,
            'max_sell':    None,
            'list':        fintech_list,
        }
        if fintech_list:
            sells = [f['sell'] for f in fintech_list]
            buys  = [f['buy']  for f in fintech_list]
            fintechs['median_sell'] = round(statistics.median(sells), 4)
            fintechs['median_buy']  = round(statistics.median(buys),  4)
            fintechs['min_sell']    = round(min(sells), 4)
            fintechs['max_sell']    = round(max(sells), 4)

        # ── DATATEC ───────────────────────────────────────────────────────
        datatec_row = DatatecRate.get()
        age_s = (int((now_peru() - datatec_row.updated_at).total_seconds())
                 if datatec_row.updated_at else 0)
        datatec = {
            'compra':        _f(datatec_row.compra),
            'venta':         _f(datatec_row.venta),
            'age_s':         age_s,
            'age_min':       age_s // 60,
            'updated_by':    datatec_row.updater.username if datatec_row.updater else None,
            'is_configured': (_f(datatec_row.compra) or 0) > 0,
        }

        # ── Consenso ──────────────────────────────────────────────────────
        # Referencia de venta: preferir mediana de fintechs (mercado retail real)
        # Si no hay fintechs, usar Yahoo Finance
        ref_sell = fintechs['median_sell'] or (yahoo['usdpen'] if yahoo else None)
        ref_buy  = fintechs['median_buy']  or (yahoo['usdpen'] if yahoo else None)

        consensus = {'ref_sell': ref_sell, 'ref_buy': ref_buy}
        if ref_sell and datatec['is_configured']:
            consensus['diff_venta']  = round(ref_sell - datatec['venta'],  4)
            consensus['diff_compra'] = round(ref_buy  - datatec['compra'], 4)
            consensus['sources'] = (
                (['Yahoo'] if yahoo and yahoo['usdpen'] else []) +
                ([f'{fintechs["count"]} fintechs'] if fintechs['count'] > 0 else [])
            )

        return jsonify({
            'ok':          True,
            'yahoo':       yahoo,
            'fintechs':    fintechs,
            'datatec':     datatec,
            'consensus':   consensus,
            'market':      _market_status(),
            'server_time': now_peru().strftime('%H:%M:%S'),
        })

    except Exception as exc:
        logger.error('[FXTerminal] api_snap error: %s', exc, exc_info=True)
        return jsonify({'ok': False, 'error': str(exc)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# API — Actualizar DATATEC
# ─────────────────────────────────────────────────────────────────────────────

@fx_terminal_bp.route('/api/datatec', methods=['GET'])
@login_required
@require_role('Master', 'Trader', 'Operador')
def api_get_datatec():
    """Precio DATATEC actual — lectura para Master/Trader/Operador."""
    row = DatatecRate.get()
    return jsonify({
        'ok': True,
        'compra':     float(row.compra),
        'venta':      float(row.venta),
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
        'updated_by': row.updater.username if row.updater else None,
    })


@fx_terminal_bp.route('/api/datatec', methods=['POST'])
@csrf.exempt
@login_required
@require_role(*_MASTER_ONLY)
def api_update_datatec():
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
        return jsonify({'ok': False, 'error': 'Valores fuera de rango esperado (3.00–5.00)'}), 400

    notes = str(data.get('notes', '')).strip()[:300] or None

    try:
        DatatecRate.update(compra, venta, None, None, current_user.id)
        db.session.add(DatatecEntry(
            compra=compra, venta=venta,
            user_id=current_user.id, notes=notes,
        ))
        db.session.commit()
        logger.info('[FXTerminal] DATATEC → compra=%.4f venta=%.4f por %s',
                    compra, venta, current_user.username)
        socketio.emit('datatec_actualizado', {
            'compra':     compra,
            'venta':      venta,
            'updated_by': current_user.username,
            'updated_at': now_peru().isoformat(),
        })
        return jsonify({'ok': True, 'compra': compra, 'venta': venta})
    except Exception as exc:
        db.session.rollback()
        logger.error('[FXTerminal] Error DATATEC update: %s', exc)
        return jsonify({'ok': False, 'error': 'Error interno al guardar'}), 500


# ─────────────────────────────────────────────────────────────────────────────
# API — Historial DATATEC
# ─────────────────────────────────────────────────────────────────────────────

@fx_terminal_bp.route('/api/history')
@login_required
@require_role(*_MASTER_ONLY)
def api_history():
    entries = (DatatecEntry.query
               .order_by(DatatecEntry.created_at.desc())
               .limit(20).all())
    return jsonify({'ok': True, 'entries': [e.to_dict() for e in entries]})
