"""
MarketService — orquesta ciclos de fetch, persistencia y análisis.
"""
import logging
from datetime import datetime, timezone, timedelta
from app.utils.formatters import now_peru

from app.extensions import db
from app.models.market import MarketSnapshot, MarketSignal, MarketNews, MacroIndicator, EconomicEvent, DailyAnalysis
from .price_fetcher import fetch_all_prices
from .news_fetcher import fetch_all_news
from .macro_fetcher import fetch_macro_data
from .analysis_engine import generate_signal
from .daily_analysis_service import DailyAnalysisService

logger = logging.getLogger(__name__)

_LIMA_TZ = timezone(timedelta(hours=-5))


def _to_lima(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc).astimezone(_LIMA_TZ)


class MarketService:

    @staticmethod
    def run_price_cycle() -> dict:
        """Fetch de precios + señal (se ejecuta cada 5 min)."""
        try:
            prices = fetch_all_prices()

            snap = MarketSnapshot(
                captured_at        = prices.fetched_at,
                usdpen             = prices.usdpen.price,
                usdpen_prev        = prices.usdpen.prev,
                usdpen_chg_pct     = prices.usdpen.chg_pct,
                gold               = prices.gold.price,
                gold_prev          = prices.gold.prev,
                gold_chg_pct       = prices.gold.chg_pct,
                oil                = prices.oil.price,
                oil_prev           = prices.oil.prev,
                oil_chg_pct        = prices.oil.chg_pct,
                sp500              = prices.sp500.price,
                sp500_prev         = prices.sp500.prev,
                sp500_chg_pct      = prices.sp500.chg_pct,
                nasdaq             = prices.nasdaq.price,
                nasdaq_prev        = prices.nasdaq.prev,
                nasdaq_chg_pct     = prices.nasdaq.chg_pct,
                dxy                = prices.dxy.price,
                dxy_prev           = prices.dxy.prev,
                dxy_chg_pct        = prices.dxy.chg_pct,
                # Fase 3
                vix                = prices.vix.price,
                vix_prev           = prices.vix.prev,
                vix_chg_pct        = prices.vix.chg_pct,
                copper             = prices.copper.price,
                copper_prev        = prices.copper.prev,
                copper_chg_pct     = prices.copper.chg_pct,
                treasury_10y       = prices.treasury_10y.price,
                treasury_10y_prev  = prices.treasury_10y.prev,
                treasury_10y_chg   = prices.treasury_10y.chg_pct,
                eurusd             = prices.eurusd.price,
                eurusd_prev        = prices.eurusd.prev,
                eurusd_chg_pct     = prices.eurusd.chg_pct,
                eem                = prices.eem.price,
                eem_prev           = prices.eem.prev,
                eem_chg_pct        = prices.eem.chg_pct,
                epu                = prices.epu.price,
                epu_prev           = prices.epu.prev,
                epu_chg_pct        = prices.epu.chg_pct,
                usdjpy             = prices.usdjpy.price,
                usdjpy_prev        = prices.usdjpy.prev,
                usdjpy_chg_pct     = prices.usdjpy.chg_pct,
                btc                = prices.btc.price,
                btc_prev           = prices.btc.prev,
                btc_chg_pct        = prices.btc.chg_pct,
            )
            db.session.add(snap)

            # Noticias de las últimas 4h para enriquecer la señal
            recent_since = now_peru() - timedelta(hours=4)
            recent_news = [
                n.to_dict() for n in
                MarketNews.query
                .filter(MarketNews.fetched_at >= recent_since)
                .filter(MarketNews.direction != 'neutral')
                .order_by(MarketNews.impact_level.desc(), MarketNews.fetched_at.desc())
                .limit(20)
                .all()
            ]

            sig_data = generate_signal(prices, news=recent_news)
            db.session.add(MarketSignal(**sig_data))
            db.session.commit()

            logger.info(f"[Mercado] Precios OK — USD/PEN {prices.usdpen.price} | señal: {sig_data['signal_type']} ({sig_data['confidence']}%)")
            return {'ok': True, 'signal': sig_data['signal_type']}

        except Exception as e:
            db.session.rollback()
            logger.error(f"[Mercado] Error en ciclo de precios: {e}", exc_info=True)
            return {'ok': False, 'error': str(e)}

    @staticmethod
    def run_news_cycle() -> dict:
        """Fetch de noticias + deduplicación (se ejecuta cada 15 min)."""
        try:
            articles = fetch_all_news()
            new_count = 0
            for art in articles:
                # Deduplicar por url_hash
                exists = MarketNews.query.filter_by(url_hash=art['url_hash']).first()
                if not exists:
                    db.session.add(MarketNews(
                        fetched_at      = now_peru(),
                        source          = art['source'],
                        source_country  = art['source_country'],
                        title           = art['title'],
                        summary         = art['summary'],
                        url             = art['url'],
                        url_hash        = art['url_hash'],
                        published_at    = art['published_at'],
                        impact_level    = art['impact_level'],
                        direction       = art['direction'],
                        sentiment_score = art['sentiment_score'],
                    ))
                    new_count += 1
            db.session.commit()
            logger.info(f"[Noticias] {new_count} nuevas noticias guardadas (de {len(articles)} scrapeadas)")
            return {'ok': True, 'new': new_count, 'total': len(articles)}

        except Exception as e:
            db.session.rollback()
            logger.error(f"[Mercado] Error en ciclo de noticias: {e}", exc_info=True)
            return {'ok': False, 'error': str(e)}

    @staticmethod
    def run_macro_cycle() -> dict:
        """Fetch de indicadores macro (BLS, BCRP, FRED). Se ejecuta diariamente."""
        try:
            indicators = fetch_macro_data()
            updated = 0
            for ind in indicators:
                existing = MacroIndicator.query.filter_by(key=ind['key']).first()
                if existing:
                    existing.value      = ind['value']
                    existing.prev_value = ind['prev_value']
                    existing.unit       = ind['unit']
                    existing.period     = ind['period']
                    existing.source     = ind['source']
                    existing.direction  = ind['direction']
                    existing.notes      = ind['notes']
                    existing.updated_at = now_peru()
                else:
                    db.session.add(MacroIndicator(**ind, updated_at=now_peru()))
                updated += 1
            db.session.commit()
            logger.info(f"[Macro] {updated} indicadores actualizados")
            return {'ok': True, 'updated': updated}
        except Exception as e:
            db.session.rollback()
            logger.error(f"[Macro] Error: {e}", exc_info=True)
            return {'ok': False, 'error': str(e)}

    @staticmethod
    def run_calendar_cycle() -> dict:
        """Fetch del calendario económico semanal (ForexFactory). Se ejecuta diariamente."""
        try:
            from .calendar_fetcher import fetch_calendar
            events = fetch_calendar()
            upserted = 0
            for ev in events:
                existing = EconomicEvent.query.filter_by(event_key=ev['event_key']).first()
                if existing:
                    existing.actual   = ev['actual']
                    existing.forecast = ev['forecast']
                    existing.previous = ev['previous']
                    existing.fetched_at = now_peru()
                else:
                    db.session.add(EconomicEvent(
                        event_key  = ev['event_key'],
                        event_date = ev['event_date'],
                        country    = ev['country'],
                        flag       = ev['flag'],
                        event_name = ev['event_name'],
                        impact     = ev['impact'],
                        actual     = ev['actual'],
                        forecast   = ev['forecast'],
                        previous   = ev['previous'],
                        source     = ev['source'],
                        fetched_at = now_peru(),
                    ))
                upserted += 1
            db.session.commit()
            logger.info(f"[Calendario] {upserted} eventos actualizados")
            return {'ok': True, 'events': upserted}
        except Exception as e:
            db.session.rollback()
            logger.error(f"[Calendario] Error: {e}", exc_info=True)
            return {'ok': False, 'error': str(e)}

    @staticmethod
    def run_daily_analysis_cycle() -> dict:
        """Genera el análisis base de las 8:30 AM Lima."""
        return DailyAnalysisService.generate_daily_analysis()

    @staticmethod
    def run_intraday_update() -> dict:
        """Actualización intradía manual: incorpora noticias alto impacto desde 8:30 AM."""
        return DailyAnalysisService.update_intraday_analysis()

    @staticmethod
    def get_daily_analysis() -> dict:
        """Devuelve el análisis diario activo del día."""
        return DailyAnalysisService.get_today_analysis()

    # Botón "Actualizar" del dashboard — ejecuta los 3 ciclos
    @staticmethod
    def run_cycle() -> dict:
        r_news     = MarketService.run_news_cycle()
        r_prices   = MarketService.run_price_cycle()
        r_calendar = MarketService.run_calendar_cycle()
        return {'ok': r_prices['ok'], 'prices': r_prices, 'news': r_news, 'calendar': r_calendar}

    @staticmethod
    def get_history_range(range_key: str) -> list:
        """Historial de precios agrupado por rango. Devuelve puntos para el gráfico."""
        from sqlalchemy import text
        ranges = {
            '1w': ("datetime('now', '-7 days')",  '%Y-%m-%d %H:00'),
            '1m': ("datetime('now', '-30 days')", '%Y-%m-%d %H:00'),
            '6m': ("datetime('now', '-180 days')",'%Y-%m-%d'),
            '1y': ("datetime('now', '-365 days')",'%Y-%m-%d'),
        }
        since_expr, fmt = ranges.get(range_key, ranges['1w'])
        sql = text(f"""
            SELECT
                strftime(:fmt, captured_at)       AS t,
                ROUND(AVG(usdpen), 4)             AS usdpen,
                ROUND(AVG(gold),   2)             AS gold,
                ROUND(AVG(vix),    2)             AS vix
            FROM market_snapshots
            WHERE captured_at >= {since_expr}
              AND usdpen IS NOT NULL
            GROUP BY strftime(:fmt, captured_at)
            ORDER BY t
        """)
        rows = db.session.execute(sql, {'fmt': fmt}).fetchall()
        return [{'time': r[0], 'usdpen': r[1], 'gold': r[2], 'vix': r[3]} for r in rows]

    @staticmethod
    def get_dashboard_data() -> dict:
        """Datos para el dashboard: snapshot + señal + noticias + histórico."""
        snap   = MarketSnapshot.query.order_by(MarketSnapshot.captured_at.desc()).first()
        signal = MarketSignal.query.order_by(MarketSignal.generated_at.desc()).first()

        # Noticias: last 48h, ordenadas por más reciente primero
        since_news = now_peru() - timedelta(hours=48)
        news_rows = (
            MarketNews.query
            .filter(MarketNews.fetched_at >= since_news)
            .order_by(MarketNews.fetched_at.desc())
            .limit(50)
            .all()
        )

        # Histórico USD/PEN últimas 24h
        since_hist = now_peru() - timedelta(hours=24)
        history = (
            MarketSnapshot.query
            .filter(MarketSnapshot.captured_at >= since_hist)
            .filter(MarketSnapshot.usdpen.isnot(None))
            .order_by(MarketSnapshot.captured_at.asc())
            .all()
        )

        def _f(v): return float(v) if v is not None else None

        history_data = [
            {
                'time':   _to_lima(r.captured_at).strftime('%H:%M'),
                'usdpen': _f(r.usdpen),
                'gold':   _f(r.gold),
                'vix':    _f(r.vix),
            }
            for r in history
        ]

        last_update = _to_lima(snap.captured_at).strftime('%H:%M') if snap else None

        # Indicadores macro
        macro_rows = MacroIndicator.query.order_by(MacroIndicator.key).all()
        macro_data = {m.key: m.to_dict() for m in macro_rows}

        # Calendario económico — eventos de la semana actual
        from datetime import timezone as tz
        _LIMA = timezone(timedelta(hours=-5))
        now_lima = datetime.now(_LIMA)
        # Start of current week (Monday) and end (Sunday)
        week_start = (now_lima - timedelta(days=now_lima.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        week_end   = week_start + timedelta(days=7)
        # Convert to UTC for DB query
        week_start_utc = week_start.astimezone(timezone.utc).replace(tzinfo=None)
        week_end_utc   = week_end.astimezone(timezone.utc).replace(tzinfo=None)

        cal_rows = (
            EconomicEvent.query
            .filter(EconomicEvent.event_date >= week_start_utc)
            .filter(EconomicEvent.event_date < week_end_utc)
            .order_by(EconomicEvent.event_date.asc())
            .all()
        )
        calendar_data = [e.to_dict() for e in cal_rows]

        daily_analysis = DailyAnalysisService.get_today_analysis()

        return {
            'snapshot':       snap.to_dict()           if snap    else None,
            'signal':         signal.to_dict()          if signal  else None,
            'news':           [n.to_dict() for n in news_rows],
            'history':        history_data,
            'last_update':    last_update,
            'macro':          macro_data,
            'calendar':       calendar_data,
            'daily_analysis': daily_analysis,
        }

    @staticmethod
    def empty_dashboard_data() -> dict:
        """Datos vacíos para mostrar dashboard sin error cuando las tablas no existen aún."""
        return {
            'snapshot':       None,
            'signal':         None,
            'news':           [],
            'history':        [],
            'last_update':    None,
            'macro':          {},
            'calendar':       [],
            'daily_analysis': None,
        }
