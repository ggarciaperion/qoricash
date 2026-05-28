"""
Rutas del módulo FX Monitor — /monitor
"""
import logging
from datetime import datetime, timezone, timedelta
from flask import Blueprint, render_template, jsonify, request, Response
from flask_login import login_required, current_user
from app.extensions import db
from app.utils.decorators import require_role as role_required, trading_desk_required
from app.services.fx_monitor.monitor_service import FXMonitorService
from app.models.competitor_rate import Competitor, CompetitorRateCurrent

logger = logging.getLogger(__name__)

fx_monitor_bp = Blueprint("fx_monitor", __name__, url_prefix="/monitor")

_LIMA = timezone(timedelta(hours=-5))
_MON  = ("Master",)   # solo Master + Presidente de Negocios (normalizado en decorator)


@fx_monitor_bp.route("/")
@login_required
@trading_desk_required
def dashboard():
    """Panel principal de monitoreo de competencia."""
    try:
        data = FXMonitorService.get_dashboard_data()
    except Exception as e:
        logger.error(f'[FXMonitor] Error en get_dashboard_data: {e}', exc_info=True)
        data = FXMonitorService.empty_dashboard_data()
    return render_template("fx_monitor/dashboard.html", **data)


@fx_monitor_bp.route("/api/current")
@login_required
@trading_desk_required
def api_current():
    """JSON con precios actuales de todos los competidores."""
    data = FXMonitorService.get_dashboard_data()
    return jsonify({"success": True, "data": data})


@fx_monitor_bp.route("/api/history/<slug>")
@login_required
@trading_desk_required
def api_history(slug):
    """Histórico de precios de un competidor."""
    hours = request.args.get("hours", 24, type=int)
    rows  = FXMonitorService.get_history(slug, hours=hours)
    return jsonify({"success": True, "data": rows})


@fx_monitor_bp.route("/api/price-evolution")
@login_required
@trading_desk_required
def api_price_evolution():
    """Serie temporal: promedio competencia vs QoriCash."""
    hours = request.args.get("hours", 24, type=int)
    data  = FXMonitorService.get_price_evolution(hours=hours)
    return jsonify({"success": True, "data": data})


@fx_monitor_bp.route("/api/scrape-now", methods=["POST"])
@login_required
@role_required("Master")
def api_scrape_now():
    """Fuerza un ciclo de scraping inmediato (solo Master)."""
    FXMonitorService.seed_competitors()   # garantiza que todos los competidores estén activos
    result = FXMonitorService.run_scrape_cycle()
    return jsonify({"success": True, "result": result})


@fx_monitor_bp.route("/api/seed", methods=["POST"])
@login_required
@role_required("Master")
def api_seed():
    """Inserta/activa competidores faltantes y ejecuta un ciclo de scraping (solo Master)."""
    try:
        FXMonitorService.seed_competitors()
        result = FXMonitorService.run_scrape_cycle()
        return jsonify({"success": True, "seeded": True, "scrape": result})
    except Exception as e:
        logger.error(f"[FXMonitor] api_seed error: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@fx_monitor_bp.route("/api/competitors", methods=["GET"])
@login_required
def api_competitors():
    """Lista de competidores registrados."""
    comps = Competitor.query.order_by(Competitor.name).all()
    return jsonify({"success": True, "data": [c.to_dict() for c in comps]})


@fx_monitor_bp.route("/api/competitors/<int:comp_id>/toggle", methods=["POST"])
@login_required
@role_required("Master")
def api_toggle_competitor(comp_id):
    """Activa/desactiva un competidor."""
    comp = db.get_or_404(Competitor, comp_id)
    comp.is_active = not comp.is_active
    db.session.commit()
    return jsonify({"success": True, "is_active": comp.is_active})


# ─── Trading Monitor ─────────────────────────────────────────────────────────

@fx_monitor_bp.route("/trading")
@login_required
@trading_desk_required
def trading_monitor():
    """Pantalla premium de monitoreo FX para trading desk / pantalla grande."""
    try:
        data = FXMonitorService.get_dashboard_data()
    except Exception as e:
        logger.error(f'[FXMonitor] trading_monitor error: {e}', exc_info=True)
        data = FXMonitorService.empty_dashboard_data()
    return render_template("fx_monitor/trading_monitor.html", **data)


@fx_monitor_bp.route("/api/live")
@login_required
@trading_desk_required
def api_live():
    """
    JSON optimizado para el trading monitor — polled cada 12 segundos.
    Incluye:
      - Competidores con timestamp epoch para calcular 'hace X segundos'
      - best_buy / best_sell pre-calculados
      - Estadísticas de mercado
      - Histórico compacto (last 2h) para sparklines
    """
    try:
        data = FXMonitorService.get_dashboard_data()
    except Exception as e:
        logger.error(f'[FXMonitor] api_live error: {e}', exc_info=True)
        data = FXMonitorService.empty_dashboard_data()

    # Own rate update timestamp (same as widget)
    own_updated_epoch = 0
    try:
        from app.models.exchange_rate import ExchangeRate
        rate = ExchangeRate.query.order_by(ExchangeRate.updated_at.desc()).first()
        if rate and rate.updated_at:
            ts = rate.updated_at
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=_LIMA)  # DB guarda hora Lima naive
            own_updated_epoch = int(ts.timestamp())
    except Exception:
        pass

    competitors = data["competitors"]

    # Enrich with epoch timestamp for "X ago" display
    slug_epoch = {}
    try:
        rows = (
            db.session.query(CompetitorRateCurrent, Competitor)
            .join(Competitor, CompetitorRateCurrent.competitor_id == Competitor.id)
            .filter(Competitor.is_active == True)
            .all()
        )
        for curr, comp in rows:
            ts = curr.updated_at
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=_LIMA)  # DB guarda hora Lima naive
            slug_epoch[comp.slug] = int(ts.timestamp())
    except Exception:
        pass

    for c in competitors:
        c["updated_epoch"] = slug_epoch.get(c["slug"], 0)

    # Rankings — solo entidades con AMBOS precios válidos y frescos
    # Stale threshold: durante horario de mercado (9:00-13:30) = 10 min
    # Fuera de horario el scraper duerme 30 min — no aplicar stale check
    now_lima    = datetime.now(_LIMA)
    server_now  = int(now_lima.timestamp())
    from datetime import time as _dtime
    _in_market  = _dtime(9, 0) <= now_lima.time() < _dtime(13, 30)
    STALE_SECS  = 10 * 60 if _in_market else None   # None = sin límite fuera de horario

    valid   = []
    invalid = []
    for c in competitors:
        has_data = c.get("scrape_ok") and c.get("buy", 0) > 0 and c.get("sell", 0) > 0
        if not has_data:
            c["is_valid"] = False
            invalid.append(c)
            continue
        ep = slug_epoch.get(c["slug"], 0)
        is_stale = STALE_SECS and ep > 0 and (server_now - ep) > STALE_SECS
        if is_stale:
            c["is_valid"] = False
            c["is_stale"] = True
            invalid.append(c)
        else:
            c["is_valid"] = True
            valid.append(c)

    active = valid
    errors = invalid
    buy_ranked  = sorted(active, key=lambda c: c["buy"],  reverse=True) + errors
    sell_ranked = sorted(active, key=lambda c: c["sell"]) + errors

    # best_buy / best_sell SOLO de entradas válidas (nunca de errores)
    best_buy  = buy_ranked[0]  if active else None
    best_sell = sell_ranked[0] if active else None

    # Market stats
    avg_buy  = round(sum(c["buy"]  for c in active) / len(active), 4) if active else 0
    avg_sell = round(sum(c["sell"] for c in active) / len(active), 4) if active else 0

    # Server time Lima
    now_lima = datetime.now(_LIMA)

    return jsonify({
        "success":       True,
        "server_time":   now_lima.strftime("%H:%M:%S"),
        "server_epoch":  int(now_lima.timestamp()),
        "own_buy":       data["own_buy"],
        "own_sell":      data["own_sell"],
        "own_spread":    round(data["own_sell"] - data["own_buy"], 4),
        "competitors":   competitors,
        "buy_ranked":    buy_ranked,
        "sell_ranked":   sell_ranked,
        "best_buy":      {"slug": best_buy["slug"],  "name": best_buy["name"],  "price": best_buy["buy"],  "epoch": best_buy["updated_epoch"]}  if best_buy  else None,
        "best_sell":     {"slug": best_sell["slug"], "name": best_sell["name"], "price": best_sell["sell"], "epoch": best_sell["updated_epoch"]} if best_sell else None,
        "market_avg_buy":  avg_buy,
        "market_avg_sell": avg_sell,
        "market_spread":   round(avg_sell - avg_buy, 4) if avg_buy and avg_sell else 0,
        "total_active":      len(active),
        "total_errors":      len(errors),
        "own_updated_epoch": own_updated_epoch,
    })


# ─── Server-Sent Events — push inmediato al browser ──────────────────────────

@fx_monitor_bp.route("/api/stream")
@login_required
@trading_desk_required
def api_stream():
    """
    SSE: envía un evento cada vez que el scraping loop completa un ciclo.
    El cliente recibe la señal y hace fetch inmediato de /api/live.
    Latencia end-to-end: ciclo (~5-7s) + fetch (<300ms) = <8s total.
    """
    from app.services.fx_monitor import live_cache

    def generate():
        import eventlet.queue
        # Enviar versión actual inmediatamente al conectar
        yield f"data: {{\"v\":{live_cache.get_version()}}}\n\n"

        q = live_cache.subscribe()
        try:
            while True:
                try:
                    v = q.get(timeout=20)
                    yield f"data: {{\"v\":{v}}}\n\n"
                except eventlet.queue.Empty:
                    yield ": ping\n\n"  # keepalive para evitar timeout de proxy
        except GeneratorExit:
            pass
        finally:
            live_cache.unsubscribe(q)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":        "keep-alive",
        },
    )
