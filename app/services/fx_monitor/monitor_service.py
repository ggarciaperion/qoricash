"""
FX Monitor Service — orquesta un ciclo completo de scraping, persistencia y alertas
"""
import logging
import threading
import time as _time_module
from datetime import datetime, timezone, timedelta
from app.utils.formatters import now_peru

# Zona horaria de Lima/Perú (UTC-5, sin cambio de horario de verano)
_LIMA_TZ = timezone(timedelta(hours=-5))


def _to_lima(dt: datetime) -> datetime:
    """Convierte un datetime UTC naïve a hora Lima (UTC-5)."""
    return dt.replace(tzinfo=timezone.utc).astimezone(_LIMA_TZ)

from app.extensions import db
from app.models.competitor_rate import (
    Competitor, CompetitorRateHistory,
    CompetitorRateCurrent, CompetitorRateChangeEvent
)
from .scrapers.manager import scrape_all_gen
from .detector import detect_change

logger = logging.getLogger(__name__)

# ── Ciclo concurrente ────────────────────────────────────────────────────────
# Previene que el trigger manual y el loop automático ejecuten ciclos simultáneos.
_cycle_lock = threading.Lock()

# ── Grupos de cotización compartida ──────────────────────────────────────────
# alias_slug → canonical_slug.
# Criterio de inclusión: mismo endpoint HTTP, misma estructura de respuesta,
# mismo identificador en la respuesta (id=33). No implica identidad legal de marcas.
# El alias conserva sus registros históricos pero no participa en promedios,
# rankings competitivos, conteos activos ni alertas de competencia.
SAME_SOURCE_ALIASES: dict = {
    # tucambio tenía el mismo endpoint que cambiafx (cambiafx.pe/api/tc),
    # pero ahora usa su propio scraper independiente y debe rankear por separado.
}

# ── Muestreo temporal del historial ──────────────────────────────────────────
# Para cada slug, registra cuándo se insertó la última entrada en fx_rate_history.
# Garantiza que movimientos pequeños pero acumulados se graben,
# y que incluso sin cambios haya una muestra periódica (continuidad).
_last_history_ts: dict = {}   # slug → monotonic timestamp (float)
_HISTORY_INTERVAL = 900       # 15 minutos entre muestras forzadas

# Datos iniciales de competidores
COMPETITORS_SEED = [
    {"slug": "kambista",     "name": "Kambista",     "website": "https://kambista.com"},
    {"slug": "cambioseguro", "name": "Cambio Seguro","website": "https://cambioseguro.com"},
    {"slug": "tucambio",     "name": "TuCambio",     "website": "https://tucambio.pe"},
    {"slug": "tucambista",   "name": "TuCambista",   "website": "https://tucambista.pe"},
    {"slug": "rextie",       "name": "Rextie",       "website": "https://www.rextie.com"},
    {"slug": "dollarhouse",  "name": "Dollar House", "website": "https://dollarhouse.pe"},
    {"slug": "moneyhouse",   "name": "Moneyhouse",   "website": "https://moneyhouse.pe"},
    {"slug": "jetperu",       "name": "Jetperu",        "website": "https://jetperu.com.pe"},
    {"slug": "inkamoney",     "name": "InkaMoney",      "website": "https://inkamoney.com"},
    {"slug": "dichikash",     "name": "Dichikash",      "website": "https://dichikash.com"},
    {"slug": "westernunion",  "name": "Western Union",  "website": "https://westernunionperu.pe/cambiodemoneda"},
    {"slug": "cambiafx",      "name": "CambiaFX",       "website": "https://cambiafx.pe"},
    {"slug": "cambiomundial", "name": "Cambio Mundial", "website": "https://www.cambiomundial.com"},
    {"slug": "tkambio",       "name": "TKambio",        "website": "https://tkambio.com"},
    {"slug": "cambiosol",     "name": "Cambiosol",      "website": "https://cambiosol.pe"},
    {"slug": "okane",         "name": "Okane",          "website": "https://okanecambiodigital.com"},
]


def _persist_one(result, comp, prev, slug_to_current, changes_so_far):
    """
    Procesa un RateResult y actualiza DB (sin commit).
    Retorna (rate_ok: bool, change_detected: bool).

    Reglas de vigencia:
    - last_attempt_at: siempre actualizado (éxito o fallo).
    - last_valid_at / updated_at / data_source: SOLO en éxito.
    - Un fallo no sobreescribe el precio bueno anterior.

    Historia (muestreo):
    - Primera entrada: siempre insertar.
    - Cualquier cambio (delta > 0): insertar.
    - Sin cambio pero han pasado ≥15 min desde la última entrada: insertar muestra.
    """
    from decimal import Decimal

    _valid_range = 2.5 < result.buy_rate < 6.0 and 2.5 < result.sell_rate < 6.0
    _valid_order = result.buy_rate < result.sell_rate
    _rate_ok = result.success and result.buy_rate > 0 and _valid_range and _valid_order

    # ── Fallo ────────────────────────────────────────────────────────────────
    if not _rate_ok:
        if result.success and result.buy_rate > 0:
            logger.warning(
                f"[FX] {result.slug}: dato rechazado — "
                f"buy={result.buy_rate} sell={result.sell_rate} "
                f"(rango_ok={_valid_range} order_ok={_valid_order})"
            )
        if prev:
            was_ok = bool(prev.scrape_ok)
            prev.last_attempt_at = result.scraped_at
            prev.scrape_ok       = False
            prev.last_error      = result.error or "Dato inválido"
            # updated_at / last_valid_at / data_source: NO tocar — preservar último precio bueno
            if was_ok:
                # Primera transición ok→error: registrar en histórico
                db.session.add(CompetitorRateHistory(
                    competitor_id=comp.id,
                    buy_rate=0, sell_rate=0,
                    scraped_at=result.scraped_at,
                    response_ms=result.response_ms,
                    error=result.error,
                ))
        else:
            placeholder = CompetitorRateCurrent(
                competitor_id=comp.id,
                buy_rate=0, sell_rate=0,
                updated_at=result.scraped_at,
                last_attempt_at=result.scraped_at,
                scrape_ok=False,
                last_error=result.error or "Dato inválido",
            )
            db.session.add(placeholder)
            db.session.add(CompetitorRateHistory(
                competitor_id=comp.id,
                buy_rate=0, sell_rate=0,
                scraped_at=result.scraped_at,
                response_ms=result.response_ms,
                error=result.error,
            ))
            slug_to_current[result.slug] = placeholder
        return False, False

    # ── Éxito ────────────────────────────────────────────────────────────────
    prev_buy  = float(prev.buy_rate)  if prev else None
    prev_sell = float(prev.sell_rate) if prev else None

    # Historia: primer registro o cualquier cambio o ≥15 min sin muestra
    _is_first = not prev or not prev.scrape_ok or prev_buy is None
    _any_change = False
    if prev and prev.scrape_ok and prev_buy is not None:
        _bd = abs(Decimal(str(result.buy_rate))  - Decimal(str(prev_buy)))
        _sd = abs(Decimal(str(result.sell_rate)) - Decimal(str(prev_sell)))
        _any_change = (_bd > Decimal('0') or _sd > Decimal('0'))

    _mono_now  = _time_module.monotonic()
    _last_hist = _last_history_ts.get(result.slug, 0)
    _time_ok   = (_mono_now - _last_hist) >= _HISTORY_INTERVAL
    _should_hist = _is_first or _any_change or _time_ok

    if _should_hist:
        _last_history_ts[result.slug] = _mono_now
        db.session.add(CompetitorRateHistory(
            competitor_id=comp.id,
            buy_rate=result.buy_rate,
            sell_rate=result.sell_rate,
            scraped_at=result.scraped_at,
            response_ms=result.response_ms,
            error=result.error,
        ))

    # Detectar cambio para eventos
    change = detect_change(result.buy_rate, result.sell_rate, prev_buy, prev_sell)
    if change:
        db.session.add(CompetitorRateChangeEvent(competitor_id=comp.id, **change))
        logger.info(
            f"[FX] Cambio en {comp.name}: "
            f"compra {change['old_buy']} → {change['new_buy']} | "
            f"venta {change['old_sell']} → {change['new_sell']}"
        )

    # Actualizar current — solo los campos de éxito
    src = getattr(result, 'source', 'direct')
    src_updated_at = getattr(result, 'source_updated_at', None)

    # ── Protección: no sobreescribir precio directo reciente con dato CED más antiguo ──
    # Un respaldo CED tiene una antigüedad real (src_updated_at) que puede ser anterior
    # al último precio directo que tenemos. Si ese es el caso, descartar silenciosamente.
    if src in ('ced_batch', 'ced_direct') and prev and prev.data_source == 'direct':
        _prev_ts = prev.last_valid_at
        if _prev_ts and src_updated_at:
            _prev_aware = _prev_ts if _prev_ts.tzinfo else _prev_ts.replace(tzinfo=_LIMA_TZ)
            # src_updated_at ya es UTC aware (viene de CED)
            _ced_aware  = src_updated_at
            if _prev_aware > _ced_aware:
                logger.info(
                    f"[FX] {result.slug}: CED descartado — "
                    f"source_updated_at={src_updated_at} es anterior al "
                    f"direct last_valid_at={_prev_ts}"
                )
                prev.last_attempt_at = result.scraped_at
                return False, False

    if prev:
        prev.prev_buy_rate  = prev.buy_rate
        prev.prev_sell_rate = prev.sell_rate
        prev.buy_rate       = result.buy_rate
        prev.sell_rate      = result.sell_rate
        prev.updated_at       = result.scraped_at
        prev.last_valid_at    = result.scraped_at
        prev.last_attempt_at  = result.scraped_at
        prev.scrape_ok        = True
        prev.data_source      = src
        prev.last_error       = None
        prev.source_updated_at = src_updated_at   # None para scrapers directos; datetime UTC para CED
    else:
        new_current = CompetitorRateCurrent(
            competitor_id=comp.id,
            buy_rate=result.buy_rate,
            sell_rate=result.sell_rate,
            updated_at=result.scraped_at,
            last_valid_at=result.scraped_at,
            last_attempt_at=result.scraped_at,
            scrape_ok=True,
            data_source=src,
            source_updated_at=src_updated_at,
        )
        db.session.add(new_current)
        slug_to_current[result.slug] = new_current

    return True, bool(change)


class FXMonitorService:

    @staticmethod
    def seed_competitors():
        """Upsert de competidores base — inserta los que faltan y activa los que están inactivos."""
        for data in COMPETITORS_SEED:
            comp = Competitor.query.filter_by(slug=data["slug"]).first()
            if not comp:
                db.session.add(Competitor(**data))
                logger.info(f"[FX] Competidor nuevo insertado: {data['slug']}")
            elif not comp.is_active:
                comp.is_active = True
                logger.info(f"[FX] Competidor reactivado: {data['slug']}")
        db.session.commit()
        logger.info("[FX] Competidores sincronizados.")

    @staticmethod
    def run_scrape_cycle():
        """
        Ciclo completo con:
        - Lock de ciclo: previene ejecuciones concurrentes (manual + automático).
        - Publicación independiente: commit tras cada resultado — un scraper rápido
          aparece en la API mientras otro sigue pendiente.
        - last_valid_at: solo se actualiza en resultados exitosos; los fallos no
          sobreescriben la vigencia ni la procedencia del último precio bueno.
        - Historia: muestreo temporal (15 min) + detección de cualquier cambio;
          movimientos pequeños consecutivos ya no se pierden.
        """
        if not _cycle_lock.acquire(blocking=False):
            logger.warning("[FX] Ciclo ya en progreso — saltando ejecución concurrente")
            return {"ok": 0, "errors": 0, "skipped": True}

        ok_count = error_count = changes_count = 0

        try:
            # 1. Competidores activos
            competitors = {c.slug: c for c in Competitor.query.filter_by(is_active=True).all()}
            if not competitors:
                logger.warning("[FX] No hay competidores activos.")
                return {"ok": 0, "errors": 0}

            # 2. Cargar precios actuales para comparación delta
            current_map = {c.competitor_id: c for c in CompetitorRateCurrent.query.all()}
            slug_to_current = {}
            for comp in competitors.values():
                if comp.id in current_map:
                    slug_to_current[comp.slug] = current_map[comp.id]

            # 3. Scraping con publicación independiente por resultado
            gen = scrape_all_gen(active_slugs=list(competitors.keys()))
            try:
                for result in gen:
                    comp = competitors.get(result.slug)
                    if not comp:
                        continue
                    prev = slug_to_current.get(result.slug)
                    try:
                        _ok, _chg = _persist_one(
                            result, comp, prev, slug_to_current, changes_count
                        )
                        if _ok:
                            ok_count += 1
                        else:
                            error_count += 1
                        if _chg:
                            changes_count += 1
                        db.session.commit()
                    except Exception as exc:
                        db.session.rollback()
                        error_count += 1
                        logger.error(f"[FX] Error persistiendo {result.slug}: {exc}", exc_info=True)
            finally:
                gen.close()

            logger.info(
                f"[FX] Ciclo completado — ✅ {ok_count} OK | "
                f"❌ {error_count} errores | 🔔 {changes_count} cambios"
            )
            return {"ok": ok_count, "errors": error_count, "changes": changes_count}

        except Exception as e:
            db.session.rollback()
            logger.error(f"[FX] Error en ciclo: {e}", exc_info=True)
            return {"ok": 0, "errors": -1, "exception": str(e)}
        finally:
            _cycle_lock.release()
            db.session.remove()

    @staticmethod
    def get_dashboard_data():
        """
        Datos para el dashboard: precios actuales + TC propio + últimos cambios.
        """
        from app.models.exchange_rate import ExchangeRate

        own = ExchangeRate.get_current_rates()
        own_buy  = own["compra"]
        own_sell = own["venta"]

        rows = (
            db.session.query(CompetitorRateCurrent, Competitor)
            .join(Competitor, CompetitorRateCurrent.competitor_id == Competitor.id)
            .filter(Competitor.is_active == True)
            .order_by(CompetitorRateCurrent.sell_rate.desc())
            .all()
        )

        from datetime import timezone as _tz
        _LIMA_TZ_OFF = _tz(timedelta(hours=-5))
        competitors = []
        for current, comp in rows:
            buy  = float(current.buy_rate)
            sell = float(current.sell_rate)

            # last_valid_at = última lectura exitosa (fallback a updated_at para registros antiguos)
            ts_valid = current.last_valid_at or current.updated_at
            if ts_valid and ts_valid.tzinfo is None:
                ts_valid = ts_valid.replace(tzinfo=_LIMA_TZ_OFF)
            valid_epoch = int(ts_valid.timestamp()) if ts_valid else 0

            # source_updated_at = timestamp del proveedor (solo CED); None para scrapers directos
            ts_src_upd = current.source_updated_at
            if ts_src_upd and ts_src_upd.tzinfo is None:
                ts_src_upd = ts_src_upd.replace(tzinfo=_LIMA_TZ_OFF)
            src_upd_epoch = int(ts_src_upd.timestamp()) if ts_src_upd else None

            # last_attempt_at para mostrar "intentado hace Xs"
            ts_att = current.last_attempt_at
            if ts_att and ts_att.tzinfo is None:
                ts_att = ts_att.replace(tzinfo=_LIMA_TZ_OFF)
            att_epoch = int(ts_att.timestamp()) if ts_att else 0

            now_epoch = int(now_peru().timestamp())
            stale_min = round((now_epoch - valid_epoch) / 60, 1) if valid_epoch else None

            competitors.append({
                "slug":              comp.slug,
                "name":              comp.name,
                "website":           comp.website,
                "buy":               buy,
                "sell":              sell,
                "spread":            round(sell - buy, 4),
                "vs_own_buy":        round(buy  - own_buy,  4),
                "vs_own_sell":       round(sell - own_sell, 4),
                "prev_buy":          float(current.prev_buy_rate)  if current.prev_buy_rate  else None,
                "prev_sell":         float(current.prev_sell_rate) if current.prev_sell_rate else None,
                "updated_at":        current.updated_at.strftime("%H:%M"),
                "updated_epoch":     valid_epoch,
                "last_valid_epoch":  valid_epoch,
                "last_attempt_epoch": att_epoch,
                "stale_min":           stale_min,
                "scrape_ok":           current.scrape_ok,
                "data_source":         current.data_source,
                "source_updated_epoch": src_upd_epoch,   # epoch UTC del proveedor (CED); None para directos
                "is_alias":          comp.slug in SAME_SOURCE_ALIASES,
                "canonical_slug":    SAME_SOURCE_ALIASES.get(comp.slug),
                "last_error":        current.last_error,
                "last_attempt_at":   current.last_attempt_at.strftime("%H:%M:%S") if current.last_attempt_at else None,
            })

        recent_changes = (
            CompetitorRateChangeEvent.query
            .order_by(CompetitorRateChangeEvent.detected_at.desc())
            .limit(20)
            .all()
        )

        return {
            "own_buy":    own_buy,
            "own_sell":   own_sell,
            "competitors": competitors,
            "changes":    [e.to_dict() for e in recent_changes],
        }

    @staticmethod
    def empty_dashboard_data() -> dict:
        """Datos vacíos para mostrar dashboard sin error cuando las tablas no existen aún."""
        return {
            "own_buy":     3.75,
            "own_sell":    3.77,
            "competitors": [],
            "changes":     [],
        }

    @staticmethod
    def get_history(slug, hours=24):
        """Histórico de precios de un competidor (últimas N horas)."""
        from datetime import timedelta
        comp = Competitor.query.filter_by(slug=slug).first_or_404()
        since = now_peru() - timedelta(hours=hours)
        rows = (
            CompetitorRateHistory.query
            .filter_by(competitor_id=comp.id)
            .filter(CompetitorRateHistory.scraped_at >= since)
            .filter(CompetitorRateHistory.buy_rate != None)
            .order_by(CompetitorRateHistory.scraped_at.asc())
            .all()
        )
        return [r.to_dict() for r in rows]

    @staticmethod
    def get_price_evolution(hours: int = 24) -> dict:
        """
        Serie temporal para el gráfico de evolución:
          - Promedio de todos los competidores activos (compra y venta)
          - QoriCash (compra y venta)
        Devuelve listas alineadas con labels de hora Lima.
        """
        from app.models.exchange_rate import ExchangeRate
        from collections import defaultdict

        since_utc = now_peru() - timedelta(hours=hours)

        # Tamaño de bucket según el rango solicitado
        if hours <= 24:
            bucket_sec = 3600        # 1 hora
        elif hours <= 72:
            bucket_sec = 7200        # 2 horas
        else:
            bucket_sec = 14400       # 4 horas

        # ── Competencia: promedio por bucket ─────────────────────────────
        active_ids = [c.id for c in Competitor.query.filter_by(is_active=True).all()]
        if not active_ids:
            return {'labels': [], 'comp_buy': [], 'comp_sell': [], 'own_buy': [], 'own_sell': []}

        hist = (
            CompetitorRateHistory.query
            .filter(CompetitorRateHistory.competitor_id.in_(active_ids))
            .filter(CompetitorRateHistory.scraped_at >= since_utc)
            .filter(CompetitorRateHistory.buy_rate > 0)
            .order_by(CompetitorRateHistory.scraped_at.asc())
            .all()
        )

        buckets: dict = defaultdict(list)
        for row in hist:
            ts = int(row.scraped_at.timestamp())
            b  = (ts // bucket_sec) * bucket_sec
            buckets[b].append((float(row.buy_rate), float(row.sell_rate)))

        # ── QoriCash: historial de cambios de TC ─────────────────────────
        own_hist = (
            ExchangeRate.query
            .filter(ExchangeRate.updated_at >= since_utc)
            .order_by(ExchangeRate.updated_at.asc())
            .all()
        )
        # Tasa activa justo antes del período (para tener valor desde el inicio)
        own_baseline = (
            ExchangeRate.query
            .filter(ExchangeRate.updated_at < since_utc)
            .order_by(ExchangeRate.updated_at.desc())
            .first()
        )

        own_points = []  # lista de (timestamp_utc, buy, sell)
        if own_baseline:
            own_points.append((
                int(own_baseline.updated_at.timestamp()),
                float(own_baseline.buy_rate),
                float(own_baseline.sell_rate),
            ))
        for row in own_hist:
            own_points.append((
                int(row.updated_at.timestamp()),
                float(row.buy_rate),
                float(row.sell_rate),
            ))

        # ── Construir series alineadas ────────────────────────────────────
        sorted_buckets = sorted(buckets.keys())
        labels    = []
        comp_buy  = []
        comp_sell = []
        q_buy     = []
        q_sell    = []

        for b in sorted_buckets:
            entries  = buckets[b]
            avg_buy  = round(sum(e[0] for e in entries) / len(entries), 4)
            avg_sell = round(sum(e[1] for e in entries) / len(entries), 4)

            dt_lima = _to_lima(datetime.utcfromtimestamp(b))
            labels.append(dt_lima.strftime('%d/%m %H:%M'))
            comp_buy.append(avg_buy)
            comp_sell.append(avg_sell)

            # Último TC de QoriCash vigente en el punto medio del bucket
            mid = b + bucket_sec // 2
            own_at = None
            for ts, ob, os in own_points:
                if ts <= mid:
                    own_at = (ob, os)
                else:
                    break
            q_buy.append(own_at[0] if own_at else None)
            q_sell.append(own_at[1] if own_at else None)

        return {
            'labels':    labels,
            'comp_buy':  comp_buy,
            'comp_sell': comp_sell,
            'own_buy':   q_buy,
            'own_sell':  q_sell,
        }
