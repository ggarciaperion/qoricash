"""
Modelos para el módulo de Mercado — análisis macro y tipo de cambio
"""
from datetime import datetime, date
from app.extensions import db


class MarketSnapshot(db.Model):
    """Snapshot de precios de activos financieros clave cada 5 minutos"""
    __tablename__ = 'market_snapshots'

    id              = db.Column(db.Integer, primary_key=True)
    captured_at     = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Tipo de cambio
    usdpen          = db.Column(db.Numeric(8, 4))
    usdpen_prev     = db.Column(db.Numeric(8, 4))
    usdpen_chg_pct  = db.Column(db.Numeric(6, 3))

    # Oro (USD/oz)
    gold            = db.Column(db.Numeric(10, 2))
    gold_prev       = db.Column(db.Numeric(10, 2))
    gold_chg_pct    = db.Column(db.Numeric(6, 3))

    # Petróleo WTI (USD/barril)
    oil             = db.Column(db.Numeric(8, 2))
    oil_prev        = db.Column(db.Numeric(8, 2))
    oil_chg_pct     = db.Column(db.Numeric(6, 3))

    # S&P 500
    sp500           = db.Column(db.Numeric(10, 2))
    sp500_prev      = db.Column(db.Numeric(10, 2))
    sp500_chg_pct   = db.Column(db.Numeric(6, 3))

    # Nasdaq Composite
    nasdaq          = db.Column(db.Numeric(10, 2))
    nasdaq_prev     = db.Column(db.Numeric(10, 2))
    nasdaq_chg_pct  = db.Column(db.Numeric(6, 3))

    # Índice del dólar (DXY)
    dxy             = db.Column(db.Numeric(8, 3))
    dxy_prev        = db.Column(db.Numeric(8, 3))
    dxy_chg_pct     = db.Column(db.Numeric(6, 3))

    # ── Indicadores macro (Phase 3) ──────────────────────────────────────────
    # VIX — índice de miedo (CBOE Volatility Index)
    vix             = db.Column(db.Numeric(8, 2))
    vix_prev        = db.Column(db.Numeric(8, 2))
    vix_chg_pct     = db.Column(db.Numeric(6, 3))

    # Cobre (USD/lb) — correlación con PEN (Perú exportador)
    copper          = db.Column(db.Numeric(8, 4))
    copper_prev     = db.Column(db.Numeric(8, 4))
    copper_chg_pct  = db.Column(db.Numeric(6, 3))

    # Bono del Tesoro EE.UU. 10 años (rendimiento %)
    treasury_10y    = db.Column(db.Numeric(6, 3))
    treasury_10y_prev   = db.Column(db.Numeric(6, 3))
    treasury_10y_chg    = db.Column(db.Numeric(6, 3))   # cambio absoluto en bps

    # EUR/USD — proxy inverso del DXY
    eurusd          = db.Column(db.Numeric(8, 4))
    eurusd_prev     = db.Column(db.Numeric(8, 4))
    eurusd_chg_pct  = db.Column(db.Numeric(6, 3))

    # ETF de mercados emergentes (EEM)
    eem             = db.Column(db.Numeric(8, 2))
    eem_prev        = db.Column(db.Numeric(8, 2))
    eem_chg_pct     = db.Column(db.Numeric(6, 3))

    # ETF Perú (EPU — iShares MSCI Peru)
    epu             = db.Column(db.Numeric(8, 2))
    epu_prev        = db.Column(db.Numeric(8, 2))
    epu_chg_pct     = db.Column(db.Numeric(6, 3))

    # USD/JPY — indicador de riesgo (JPY es activo refugio)
    usdjpy          = db.Column(db.Numeric(8, 3))
    usdjpy_prev     = db.Column(db.Numeric(8, 3))
    usdjpy_chg_pct  = db.Column(db.Numeric(6, 3))

    # Bitcoin — sentimiento de riesgo global
    btc             = db.Column(db.Numeric(12, 2))
    btc_prev        = db.Column(db.Numeric(12, 2))
    btc_chg_pct     = db.Column(db.Numeric(6, 3))

    __table_args__ = (
        db.Index('idx_market_snap_time', 'captured_at'),
    )

    def to_dict(self):
        def f(v): return float(v) if v is not None else None
        return {
            'captured_at':      self.captured_at.isoformat(),
            'usdpen':           f(self.usdpen),
            'usdpen_chg':       f(self.usdpen_chg_pct),
            'gold':             f(self.gold),
            'gold_chg':         f(self.gold_chg_pct),
            'oil':              f(self.oil),
            'oil_chg':          f(self.oil_chg_pct),
            'sp500':            f(self.sp500),
            'sp500_chg':        f(self.sp500_chg_pct),
            'nasdaq':           f(self.nasdaq),
            'nasdaq_chg':       f(self.nasdaq_chg_pct),
            'dxy':              f(self.dxy),
            'dxy_chg':          f(self.dxy_chg_pct),
            'vix':              f(self.vix),
            'vix_chg':          f(self.vix_chg_pct),
            'copper':           f(self.copper),
            'copper_chg':       f(self.copper_chg_pct),
            'treasury_10y':     f(self.treasury_10y),
            'treasury_10y_chg': f(self.treasury_10y_chg),
            'eurusd':           f(self.eurusd),
            'eurusd_chg':       f(self.eurusd_chg_pct),
            'eem':              f(self.eem),
            'eem_chg':          f(self.eem_chg_pct),
            'epu':              f(self.epu),
            'epu_chg':          f(self.epu_chg_pct),
            'usdjpy':           f(self.usdjpy),
            'usdjpy_chg':       f(self.usdjpy_chg_pct),
            'btc':              f(self.btc),
            'btc_chg':          f(self.btc_chg_pct),
        }


class MacroIndicator(db.Model):
    """Indicadores macroeconómicos clave — se actualizan diariamente."""
    __tablename__ = 'macro_indicators'

    id            = db.Column(db.Integer, primary_key=True)
    key           = db.Column(db.String(50), unique=True, nullable=False)
    label         = db.Column(db.String(100))          # "Tasa FED"
    value         = db.Column(db.Numeric(12, 4))
    prev_value    = db.Column(db.Numeric(12, 4))
    unit          = db.Column(db.String(20))            # "%", "K jobs", "USD"
    period        = db.Column(db.String(30))            # "Mar 2026", "Feb 2026"
    source        = db.Column(db.String(50))            # "FRED", "BLS", "BCRP", "manual"
    direction     = db.Column(db.String(10))            # "up", "down", "flat"
    updated_at    = db.Column(db.DateTime, default=datetime.utcnow)
    notes         = db.Column(db.String(200))           # contexto adicional

    def to_dict(self):
        return {
            'key':        self.key,
            'label':      self.label,
            'value':      float(self.value)      if self.value      else None,
            'prev_value': float(self.prev_value) if self.prev_value else None,
            'unit':       self.unit,
            'period':     self.period,
            'source':     self.source,
            'direction':  self.direction,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'notes':      self.notes,
        }


class MarketNews(db.Model):
    """Noticias financieras recolectadas y clasificadas automáticamente"""
    __tablename__ = 'market_news'

    id              = db.Column(db.Integer, primary_key=True)
    fetched_at      = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    source          = db.Column(db.String(80))                        # 'BBC Business', 'Gestión'
    source_country  = db.Column(db.String(2))                         # 'PE', 'US', 'GB'
    title           = db.Column(db.String(300), nullable=False)
    summary         = db.Column(db.Text)
    url             = db.Column(db.String(500))
    published_at    = db.Column(db.DateTime)

    impact_level    = db.Column(db.String(10), default='low')         # high | medium | low
    direction       = db.Column(db.String(20), default='neutral')     # bullish_usd | bearish_usd | neutral
    sentiment_score = db.Column(db.Numeric(4, 2), default=0)          # -1.0 a +1.0
    url_hash        = db.Column(db.String(32), unique=True)            # MD5 de URL para deduplicar

    __table_args__ = (
        db.Index('idx_news_fetched', 'fetched_at'),
        db.Index('idx_news_impact',  'impact_level'),
    )

    def to_dict(self):
        from datetime import timezone, timedelta
        _LIMA = timezone(timedelta(hours=-5))

        def _fmt_lima(dt):
            """Convierte datetime UTC (naive) a string legible en hora Lima."""
            if not dt:
                return None
            dt_utc  = dt.replace(tzinfo=timezone.utc)
            dt_lima = dt_utc.astimezone(_LIMA)
            # Formato: "25 mar 20:20"
            meses = ['', 'ene', 'feb', 'mar', 'abr', 'may', 'jun',
                     'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
            return f"{dt_lima.day} {meses[dt_lima.month]} {dt_lima.strftime('%H:%M')}"

        return {
            'id':             self.id,
            'source':         self.source,
            'source_country': self.source_country,
            'title':          self.title,
            'summary':        self.summary,
            'url':            self.url,
            'published_lima': _fmt_lima(self.published_at),
            'fetched_lima':   _fmt_lima(self.fetched_at),
            'impact_level':   self.impact_level,
            'direction':      self.direction,
            'sentiment':      float(self.sentiment_score) if self.sentiment_score else 0,
        }


class MarketSignal(db.Model):
    """Señales de mercado generadas por el motor de análisis"""
    __tablename__ = 'market_signals'

    id              = db.Column(db.Integer, primary_key=True)
    generated_at    = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    signal_type     = db.Column(db.String(20), nullable=False)   # bullish | bearish | volatile | lateral
    confidence      = db.Column(db.Integer, default=0)           # 0-100
    title           = db.Column(db.String(200))
    reasoning       = db.Column(db.Text)
    triggered_by    = db.Column(db.Text)                          # JSON list de factores

    def to_dict(self):
        import json
        return {
            'generated_at': self.generated_at.isoformat(),
            'signal_type':  self.signal_type,
            'confidence':   self.confidence,
            'title':        self.title,
            'reasoning':    self.reasoning,
            'triggered_by': json.loads(self.triggered_by) if self.triggered_by else [],
        }


class EconomicEvent(db.Model):
    """Eventos del calendario económico semanal (ForexFactory)"""
    __tablename__ = 'economic_events'

    id          = db.Column(db.Integer, primary_key=True)
    event_key   = db.Column(db.String(32), unique=True, nullable=False)
    event_date  = db.Column(db.DateTime, nullable=False)   # UTC
    country     = db.Column(db.String(10))
    flag        = db.Column(db.String(10))
    event_name  = db.Column(db.String(250))
    impact      = db.Column(db.String(10))                 # high/medium/low
    actual      = db.Column(db.String(30))
    forecast    = db.Column(db.String(30))
    previous    = db.Column(db.String(30))
    source      = db.Column(db.String(50), default='ForexFactory')
    fetched_at  = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.Index('idx_events_date', 'event_date'),
    )

    def to_dict(self):
        from datetime import timezone, timedelta
        _LIMA_TZ = timezone(timedelta(hours=-5))
        _DAYS_ES = {0: 'Lun', 1: 'Mar', 2: 'Mié', 3: 'Jue', 4: 'Vie', 5: 'Sáb', 6: 'Dom'}
        dt_utc  = self.event_date.replace(tzinfo=timezone.utc)
        dt_lima = dt_utc.astimezone(_LIMA_TZ)
        now_lima = datetime.now(_LIMA_TZ)
        return {
            'event_key':  self.event_key,
            'date_lima':  dt_lima.strftime('%Y-%m-%d'),
            'time_lima':  dt_lima.strftime('%H:%M'),
            'day_es':     _DAYS_ES[dt_lima.weekday()],
            'country':    self.country,
            'flag':       self.flag,
            'event_name': self.event_name,
            'impact':     self.impact,
            'actual':     self.actual,
            'forecast':   self.forecast,
            'previous':   self.previous,
            'is_today':   dt_lima.date() == now_lima.date(),
            'is_past':    dt_lima < now_lima,
        }


class DailyAnalysis(db.Model):
    """Análisis fundamental diario del USD/PEN — generado a las 8:30 am Lima de lunes a viernes."""
    __tablename__ = 'daily_analyses'

    id                   = db.Column(db.Integer, primary_key=True)
    analysis_date        = db.Column(db.Date, nullable=False)       # Fecha de la jornada (Lima)
    generated_at         = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Veredicto principal
    trend                = db.Column(db.String(10), nullable=False)  # 'alza' | 'baja' | 'estable'
    confidence           = db.Column(db.Integer, default=0)          # 0-100
    title                = db.Column(db.String(300))                 # Titular ejecutivo
    summary              = db.Column(db.Text)                        # Párrafo principal del análisis
    key_factors          = db.Column(db.Text)                        # JSON list de factores clave

    # Métricas internas de cálculo
    news_analyzed        = db.Column(db.Integer, default=0)
    bullish_signals      = db.Column(db.Integer, default=0)
    bearish_signals      = db.Column(db.Integer, default=0)
    net_score            = db.Column(db.Integer, default=0)

    # Control de actualizaciones extraordinarias
    is_extraordinary     = db.Column(db.Boolean, default=False)
    extraordinary_reason = db.Column(db.String(300))

    is_active            = db.Column(db.Boolean, default=True)

    __table_args__ = (
        db.Index('idx_daily_analysis_date', 'analysis_date'),
    )

    def to_dict(self):
        import json
        from datetime import timezone, timedelta
        _LIMA = timezone(timedelta(hours=-5))
        gen_lima = self.generated_at.replace(tzinfo=timezone.utc).astimezone(_LIMA)
        meses = ['', 'ene', 'feb', 'mar', 'abr', 'may', 'jun',
                 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
        gen_str = f"{gen_lima.day} {meses[gen_lima.month]}, {gen_lima.strftime('%H:%M')} Lima"
        return {
            'id':                   self.id,
            'analysis_date':        self.analysis_date.isoformat() if self.analysis_date else None,
            'generated_at_lima':    gen_str,
            'trend':                self.trend,
            'confidence':           self.confidence,
            'title':                self.title,
            'summary':              self.summary,
            'key_factors':          json.loads(self.key_factors) if self.key_factors else [],
            'news_analyzed':        self.news_analyzed,
            'bullish_signals':      self.bullish_signals,
            'bearish_signals':      self.bearish_signals,
            'net_score':            self.net_score,
            'is_extraordinary':     self.is_extraordinary,
            'extraordinary_reason': self.extraordinary_reason,
        }
