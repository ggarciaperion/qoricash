"""
Modelos para el sistema de monitoreo de tipos de cambio de la competencia (FX Monitor)
"""
from app.extensions import db
from app.utils.formatters import now_peru


class Competitor(db.Model):
    """Competidores registrados para monitoreo"""
    __tablename__ = 'fx_competitors'

    id           = db.Column(db.Integer, primary_key=True)
    slug         = db.Column(db.String(50), unique=True, nullable=False)  # 'kambista'
    name         = db.Column(db.String(100), nullable=False)              # 'Kambista'
    website      = db.Column(db.String(255), nullable=False)
    scraper_type = db.Column(db.String(20), default='requests')           # 'requests' | 'playwright'
    is_active    = db.Column(db.Boolean, default=True)
    created_at   = db.Column(db.DateTime, default=now_peru)

    # Relaciones
    rates_history = db.relationship('CompetitorRateHistory', backref='competitor', lazy='select')
    current_rate  = db.relationship('CompetitorRateCurrent', backref='competitor', uselist=False)

    def __repr__(self):
        return f'<Competitor {self.slug}>'

    def to_dict(self):
        return {
            'id': self.id,
            'slug': self.slug,
            'name': self.name,
            'website': self.website,
            'is_active': self.is_active,
        }


class CompetitorRateHistory(db.Model):
    """Histórico completo de tipos de cambio por competidor"""
    __tablename__ = 'fx_rate_history'

    id            = db.Column(db.Integer, primary_key=True, autoincrement=True)
    competitor_id = db.Column(db.Integer, db.ForeignKey('fx_competitors.id'), nullable=False)
    buy_rate      = db.Column(db.Numeric(8, 4), nullable=False)
    sell_rate     = db.Column(db.Numeric(8, 4), nullable=False)
    scraped_at    = db.Column(db.DateTime, nullable=False, default=now_peru)
    response_ms   = db.Column(db.Integer)           # latencia del scrape en ms
    error         = db.Column(db.String(255))        # mensaje de error si falló

    __table_args__ = (
        db.Index('idx_fx_history_competitor_time', 'competitor_id', 'scraped_at'),
    )

    def to_dict(self):
        return {
            'buy_rate':   float(self.buy_rate),
            'sell_rate':  float(self.sell_rate),
            'scraped_at': self.scraped_at.isoformat(),
        }


class CompetitorRateCurrent(db.Model):
    """Último tipo de cambio conocido por competidor (tabla de lectura rápida)"""
    __tablename__ = 'fx_rate_current'

    competitor_id  = db.Column(db.Integer, db.ForeignKey('fx_competitors.id'), primary_key=True)
    buy_rate       = db.Column(db.Numeric(8, 4), nullable=False)
    sell_rate      = db.Column(db.Numeric(8, 4), nullable=False)
    prev_buy_rate  = db.Column(db.Numeric(8, 4))
    prev_sell_rate = db.Column(db.Numeric(8, 4))
    updated_at     = db.Column(db.DateTime, nullable=False, default=now_peru)
    scrape_ok      = db.Column(db.Boolean, default=True)   # False si el último scrape falló

    def spread(self):
        return float(self.sell_rate) - float(self.buy_rate)

    def to_dict(self):
        return {
            'buy_rate':       float(self.buy_rate),
            'sell_rate':      float(self.sell_rate),
            'prev_buy_rate':  float(self.prev_buy_rate)  if self.prev_buy_rate  else None,
            'prev_sell_rate': float(self.prev_sell_rate) if self.prev_sell_rate else None,
            'updated_at':     self.updated_at.isoformat(),
            'scrape_ok':      self.scrape_ok,
        }


class CompetitorRateChangeEvent(db.Model):
    """Registro de cada cambio de precio detectado"""
    __tablename__ = 'fx_change_events'

    id            = db.Column(db.Integer, primary_key=True, autoincrement=True)
    competitor_id = db.Column(db.Integer, db.ForeignKey('fx_competitors.id'), nullable=False)

    field         = db.Column(db.String(10), nullable=False)   # 'buy' | 'sell' | 'both'
    old_buy       = db.Column(db.Numeric(8, 4))
    new_buy       = db.Column(db.Numeric(8, 4))
    old_sell      = db.Column(db.Numeric(8, 4))
    new_sell      = db.Column(db.Numeric(8, 4))
    buy_delta     = db.Column(db.Numeric(8, 4))
    sell_delta    = db.Column(db.Numeric(8, 4))
    buy_delta_pct = db.Column(db.Numeric(6, 3))
    sell_delta_pct= db.Column(db.Numeric(6, 3))

    detected_at   = db.Column(db.DateTime, default=now_peru)
    alert_sent    = db.Column(db.Boolean, default=False)

    competitor    = db.relationship('Competitor', backref='change_events')

    def to_dict(self):
        return {
            'id':             self.id,
            'competitor':     self.competitor.name if self.competitor else None,
            'slug':           self.competitor.slug if self.competitor else None,
            'field':          self.field,
            'old_buy':        float(self.old_buy)        if self.old_buy        else None,
            'new_buy':        float(self.new_buy)        if self.new_buy        else None,
            'old_sell':       float(self.old_sell)       if self.old_sell       else None,
            'new_sell':       float(self.new_sell)       if self.new_sell       else None,
            'buy_delta':      float(self.buy_delta)      if self.buy_delta      else None,
            'sell_delta':     float(self.sell_delta)     if self.sell_delta     else None,
            'buy_delta_pct':  float(self.buy_delta_pct)  if self.buy_delta_pct  else None,
            'sell_delta_pct': float(self.sell_delta_pct) if self.sell_delta_pct else None,
            'detected_at':    self.detected_at.isoformat(),
        }
