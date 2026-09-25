"""
Rutas del módulo FX Monitor — /monitor
"""
import logging
from datetime import datetime, timezone, timedelta
import os
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

# ── Política de vigencia CED (fuente única para todo el módulo) ──────────────
# Umbral de elegibilidad para rankings, mejores precios, promedios y alertas.
# Configurable vía env var FX_CED_ELIGIBLE_HOURS (ver app/config/__init__.py).
#
# Consumidores de esta política:
#   - api_live()  : ranking, best_buy/best_sell, market_avg_buy/sell, market_spread
#   - El dashboard (dashboard.html) muestra TODOS los competidores para diagnóstico,
#     incluyendo los CED vencidos como referencia. No realiza cálculos de ranking
#     ni promedios — solo lista datos con scrape_ok/stale_min visible al operador.
#   - api_current(): endpoint de datos crudos para herramientas internas; no filtra.
#
# Distinto del umbral de aceptación del scraper (4h en cuantoestaeldolar.py):
#   ese se aplica al guardar. Este se aplica al calcular en cada request.
#
# Nota sobre source_updated_at de CED:
#   El campo "updated_at" de cuantoestaeldolar.pe tiene semántica exacta desconocida
#   (podría ser el último cambio de precio, la última sincronización de CED u otro evento).
#   Se describe como "fecha informada por la fuente", no como confirmación de actividad.
#   Si source_updated_at es None (ausente/inválido/futuro): vigencia no acreditada → referencia.
_CED_ELIGIBLE_HOURS: float = float(os.environ.get('FX_CED_ELIGIBLE_HOURS', '2.0'))


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


@fx_monitor_bp.route("/api/debug")
@login_required
@role_required("Master")
def api_debug():
    """Diagnóstico del estado interno del monitor FX (solo Master)."""
    from app.services.fx_monitor import live_cache
    from app.services.fx_monitor.scrapers.manager import _cb, get_scraper_health
    from app.models.competitor_rate import Competitor, CompetitorRateCurrent
    import time as _time

    try:
        competitors_total = Competitor.query.count()
        competitors_active = Competitor.query.filter_by(is_active=True).count()
        current_rows = CompetitorRateCurrent.query.count()
        current_ok = CompetitorRateCurrent.query.filter_by(scrape_ok=True).count()
        current_with_prices = db.session.query(CompetitorRateCurrent).filter(
            CompetitorRateCurrent.buy_rate > 0
        ).count()

        # Detalles por competidor
        rows = (
            db.session.query(CompetitorRateCurrent, Competitor)
            .join(Competitor, CompetitorRateCurrent.competitor_id == Competitor.id)
            .all()
        )
        health = get_scraper_health()
        details = []
        for curr, comp in rows:
            h = health.get(comp.slug, {})
            details.append({
                "slug":             comp.slug,
                "buy":              float(curr.buy_rate),
                "sell":             float(curr.sell_rate),
                "scrape_ok":        curr.scrape_ok,
                "updated_at":       curr.updated_at.isoformat() if curr.updated_at else None,
                "last_attempt_at":  curr.last_attempt_at.isoformat() if curr.last_attempt_at else None,
                "data_source":      curr.data_source,
                "last_error":       curr.last_error,
                "health_ok":        h.get("ok", 0),
                "health_fail":      h.get("fail", 0),
                "health_last_ms":   h.get("last_ms", 0),
            })

        cb_state = {slug: {"fails": v["fails"], "cooldown_secs": max(0, round(v["open_until"] - _time.monotonic()))}
                    for slug, v in _cb.items()}

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({
        "competitors_total":     competitors_total,
        "competitors_active":    competitors_active,
        "current_rows":          current_rows,
        "current_scrape_ok":     current_ok,
        "current_with_prices":   current_with_prices,
        "cache_version":         live_cache.get_version(),
        "circuit_breaker":       cb_state,
        "scraper_health":        get_scraper_health(),
        "details":               details,
    })


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

    # updated_epoch ya viene calculado por get_dashboard_data() usando last_valid_at.
    # No sobreescribir — el servicio ya aplica el fallback correcto para registros antiguos.

    # Rankings — solo entidades con AMBOS precios válidos y frescos
    # Stale threshold: durante horario de mercado (9:00-13:30) = 3 min
    # Fuera de horario el scraper duerme 30 min — no aplicar stale check
    now_lima    = datetime.now(_LIMA)
    server_now  = int(now_lima.timestamp())
    from datetime import time as _dtime
    _in_market  = _dtime(9, 0) <= now_lima.time() < _dtime(13, 30)
    STALE_SECS  = 3 * 60 if _in_market else None    # None = sin límite fuera de horario

    valid   = []
    invalid = []
    for c in competitors:
        src = c.get("data_source") or "direct"
        has_prices = c.get("buy", 0) > 0 and c.get("sell", 0) > 0
        if not has_prices:
            c["is_valid"] = False
            invalid.append(c)
            continue
        if not c.get("scrape_ok"):
            # Scraper falló pero conserva precios → incluir en ranking como referencia vencida.
            # Solo se excluye del ranking si no tiene precio (ya manejado antes de este bloque).
            c["is_valid"] = True
            c["is_stale"] = True
            valid.append(c)
            continue

        if src in ('ced_direct', 'ced_batch'):
            # Para datos CED: la vigencia se juzga por source_updated_at (timestamp del proveedor),
            # NO por updated_epoch (= hora en que nosotros descargamos, que siempre es reciente).
            # Una descarga reciente no oculta que el precio del proveedor es antiguo.
            src_upd_epoch = c.get("source_updated_epoch")
            if src_upd_epoch is None:
                # Vigencia no acreditada: timestamp ausente/inválido/futuro → referencia vencida.
                c["is_valid"] = True
                c["is_stale"] = True
                c["is_ced_unknown_ts"] = True
                valid.append(c)
                continue
            ced_age_secs = server_now - src_upd_epoch
            if ced_age_secs > _CED_ELIGIBLE_HOURS * 3600:
                c["is_valid"] = True
                c["is_stale"] = True
                valid.append(c)
            else:
                c["is_valid"] = True
                valid.append(c)
        else:
            # Scrapers directos: lógica de STALE_SECS (3 min en horario de mercado)
            ep = c.get("updated_epoch", 0)
            is_stale = STALE_SECS and ep > 0 and (server_now - ep) > STALE_SECS
            if is_stale:
                c["is_valid"] = True
                c["is_stale"] = True
                valid.append(c)
            else:
                c["is_valid"] = True
                valid.append(c)

    # ── Dedup: eliminar doble ponderación de aliases ──────────────────────────
    # Debe ejecutarse ANTES del filtro de outliers para que el alias no influya
    # en el cálculo de medianas del conjunto válido.
    #
    # Regla de representación del grupo:
    #   - Canónico válido + alias válido → retirar alias; canónico representa al grupo.
    #   - Canónico NO válido + alias válido → alias queda como único representante
    #     elegible del grupo (no se descarta la cotización por falla del canónico).
    #   - Canónico válido + alias NO válido → alias ya está en invalid; sin cambio.
    #   - Ambos NO válidos → sin cambio.
    #
    # Los aliases retirados van a 'aliases' (categoría neutral), NO a 'invalid'
    # (que agrupa errores de captura). Siguen siendo visibles con su etiqueta ALIAS.
    aliases = []
    _valid_slugs = {c["slug"] for c in valid}
    for c in list(valid):
        if c.get("is_alias"):
            if c.get("canonical_slug") in _valid_slugs:
                # Canónico disponible como representante → retirar alias de cálculos
                c["is_valid"] = False
                valid.remove(c)
                aliases.append(c)
            # Si el canónico no está en valid, el alias permanece como representante

    # ── Filtro de outliers ────────────────────────────────────────────────────
    # Excluye tasas que se desvíen >6% de la mediana del grupo válido.
    # Se calcula solo sobre entradas frescas (no vencidas) para que las medianas
    # no estén sesgadas por precios antiguos. Las entradas vencidas quedan en el
    # ranking pero no participan en el cálculo de la mediana ni en los promedios.
    def _median(values):
        s = sorted(values)
        n = len(s)
        return (s[n // 2] + s[n // 2 - 1]) / 2 if n % 2 == 0 else s[n // 2]

    OUTLIER_PCT = 0.06   # 6 % de tolerancia

    fresh = [c for c in valid if not c.get("is_stale")]
    if fresh:
        med_buy  = _median([c["buy"]  for c in fresh])
        med_sell = _median([c["sell"] for c in fresh])
        for c in fresh[:]:
            buy_ok  = abs(c["buy"]  - med_buy)  / med_buy  <= OUTLIER_PCT
            sell_ok = abs(c["sell"] - med_sell) / med_sell <= OUTLIER_PCT
            if not (buy_ok and sell_ok):
                logger.warning(
                    f'[FXMonitor] Outlier excluido del ranking: {c["name"]} '
                    f'buy={c["buy"]} sell={c["sell"]} '
                    f'(mediana buy={med_buy:.4f} sell={med_sell:.4f})'
                )
                c["is_outlier"] = True
                c["is_valid"]   = False
                valid.remove(c)
                invalid.append(c)
        fresh = [c for c in valid if not c.get("is_stale")]   # recalcular tras outliers

    stale_ranked = [c for c in valid if c.get("is_stale")]
    errors = invalid
    # Ranking: frescos primero (ordenados por precio), luego vencidos, luego sin precio, luego aliases.
    buy_ranked  = sorted(fresh,        key=lambda c: c["buy"],  reverse=True) + \
                  sorted(stale_ranked, key=lambda c: c["buy"],  reverse=True) + \
                  sorted(errors,       key=lambda c: c["buy"],  reverse=True) + \
                  sorted(aliases,      key=lambda c: c["buy"],  reverse=True)
    sell_ranked = sorted(fresh,        key=lambda c: c["sell"]) + \
                  sorted(stale_ranked, key=lambda c: c["sell"]) + \
                  sorted(errors,       key=lambda c: c["sell"]) + \
                  sorted(aliases,      key=lambda c: c["sell"])

    # best_buy / best_sell: mejor entre frescos y válidos; fallback a stale (ya ordenado)
    def _best(ranked, key):
        fresh = [c for c in ranked if c.get("is_valid")]
        if fresh:
            return fresh[0]
        stale = [c for c in ranked if c.get(key, 0) > 0]
        return stale[0] if stale else None

    best_buy  = _best(buy_ranked,  "buy")
    best_sell = _best(sell_ranked, "sell")

    # Market stats: solo entradas frescas; fallback a vencidas si no hay ninguna fresca
    stats_pool = fresh or [c for c in stale_ranked if c.get("buy", 0) > 0]
    avg_buy  = round(sum(c["buy"]  for c in stats_pool) / len(stats_pool), 4) if stats_pool else 0
    avg_sell = round(sum(c["sell"] for c in stats_pool) / len(stats_pool), 4) if stats_pool else 0

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
        "total_active":      len(fresh),
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
