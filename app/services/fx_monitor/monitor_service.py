"""
FX Monitor Service — orquesta un ciclo completo de scraping, persistencia y alertas
"""
import logging
from datetime import datetime, timezone, timedelta

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
from .scrapers.manager import scrape_all
from .detector import detect_change

logger = logging.getLogger(__name__)

# Datos iniciales de competidores
COMPETITORS_SEED = [
    {"slug": "kambista",     "name": "Kambista",     "website": "https://kambista.com"},
    {"slug": "cambix",       "name": "Cambix",       "website": "https://cambix.pe"},
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
]


class FXMonitorService:

    @staticmethod
    def seed_competitors():
        """Inserta los competidores base si no existen aún."""
        for data in COMPETITORS_SEED:
            if not Competitor.query.filter_by(slug=data["slug"]).first():
                db.session.add(Competitor(**data))
        db.session.commit()
        logger.info("[FX] Competidores inicializados.")

    @staticmethod
    def run_scrape_cycle():
        """
        Ciclo completo:
        1. Obtiene competidores activos de la DB
        2. Scraping paralelo
        3. Guarda histórico
        4. Detecta cambios y registra eventos
        5. Actualiza tabla current
        """
        try:
            # 1. Competidores activos
            competitors = {c.slug: c for c in Competitor.query.filter_by(is_active=True).all()}
            if not competitors:
                logger.warning("[FX] No hay competidores activos.")
                return {"ok": 0, "errors": 0}

            # 2. Cargar precios actuales para comparación
            current_map = {
                c.competitor_id: c
                for c in CompetitorRateCurrent.query.all()
            }
            # Reindexar por slug para fácil acceso
            slug_to_current = {}
            for comp in competitors.values():
                if comp.id in current_map:
                    slug_to_current[comp.slug] = current_map[comp.id]

            # 3. Scraping
            results = scrape_all(active_slugs=list(competitors.keys()))

            ok_count = error_count = changes_count = 0

            for result in results:
                comp = competitors.get(result.slug)
                if not comp:
                    continue

                # 4. Guardar en histórico
                history = CompetitorRateHistory(
                    competitor_id=comp.id,
                    buy_rate=result.buy_rate  if result.success else 0,
                    sell_rate=result.sell_rate if result.success else 0,
                    scraped_at=result.scraped_at,
                    response_ms=result.response_ms,
                    error=result.error,
                )
                db.session.add(history)

                if not result.success or result.buy_rate == 0:
                    error_count += 1
                    # Marcar current como error pero no pisar el último precio válido
                    prev = slug_to_current.get(result.slug)
                    if prev:
                        prev.scrape_ok = False
                    continue

                ok_count += 1

                # 5. Detectar cambio
                prev = slug_to_current.get(result.slug)
                prev_buy  = float(prev.buy_rate)  if prev else None
                prev_sell = float(prev.sell_rate) if prev else None

                change = detect_change(result.buy_rate, result.sell_rate, prev_buy, prev_sell)

                if change:
                    changes_count += 1
                    event = CompetitorRateChangeEvent(
                        competitor_id=comp.id,
                        **change,
                    )
                    db.session.add(event)
                    logger.info(
                        f"[FX] 🔔 Cambio detectado en {comp.name}: "
                        f"compra {change['old_buy']} → {change['new_buy']} | "
                        f"venta {change['old_sell']} → {change['new_sell']}"
                    )

                # 6. Actualizar current
                if prev:
                    prev.prev_buy_rate  = prev.buy_rate
                    prev.prev_sell_rate = prev.sell_rate
                    prev.buy_rate       = result.buy_rate
                    prev.sell_rate      = result.sell_rate
                    prev.updated_at     = result.scraped_at
                    prev.scrape_ok      = True
                else:
                    new_current = CompetitorRateCurrent(
                        competitor_id=comp.id,
                        buy_rate=result.buy_rate,
                        sell_rate=result.sell_rate,
                        updated_at=result.scraped_at,
                        scrape_ok=True,
                    )
                    db.session.add(new_current)
                    slug_to_current[result.slug] = new_current

            db.session.commit()
            logger.info(f"[FX] Ciclo completado — ✅ {ok_count} OK | ❌ {error_count} errores | 🔔 {changes_count} cambios")
            return {"ok": ok_count, "errors": error_count, "changes": changes_count}

        except Exception as e:
            db.session.rollback()
            logger.error(f"[FX] Error en ciclo: {e}", exc_info=True)
            return {"ok": 0, "errors": -1, "exception": str(e)}

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

        competitors = []
        for current, comp in rows:
            buy  = float(current.buy_rate)
            sell = float(current.sell_rate)
            competitors.append({
                "slug":           comp.slug,
                "name":           comp.name,
                "website":        comp.website,
                "buy":            buy,
                "sell":           sell,
                "spread":         round(sell - buy, 4),
                "vs_own_buy":     round(buy  - own_buy,  4),
                "vs_own_sell":    round(sell - own_sell, 4),
                "prev_buy":       float(current.prev_buy_rate)  if current.prev_buy_rate  else None,
                "prev_sell":      float(current.prev_sell_rate) if current.prev_sell_rate else None,
                "updated_at":     _to_lima(current.updated_at).strftime("%H:%M"),
                "scrape_ok":      current.scrape_ok,
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
        since = datetime.utcnow() - timedelta(hours=hours)
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

        since_utc = datetime.utcnow() - timedelta(hours=hours)

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
