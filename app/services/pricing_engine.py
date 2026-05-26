"""
PricingEngine — Motor de estimación de precio live USD/PEN para QoriCash.

Arquitectura:
  - Recibe DATATEC manual como ancla (source of truth)
  - Analiza snapshots de mercado (Yahoo Finance) para calcular drift
  - Aplica modelo multi-señal: DXY + interbank USD/PEN + cobre
  - Genera estimación con score de confianza, tendencia y volatilidad

Señales usadas:
  DXY  (Índice dólar)       β = +0.60  → DXY up → PEN se deprecia
  USDPEN Yahoo (interbanco) β = +0.40  → interbank lidera al retail ~3-5 min
  Cobre                      β = -0.20  → cobre up → PEN se aprecia (Perú exportador)

Estas betas son calibraciones conservadoras basadas en comportamiento histórico
del mercado cambiario peruano. Son ajustables vía config sin romper el motor.
"""
from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional

from app.utils.formatters import now_peru

logger = logging.getLogger(__name__)

# ── Configuración del motor (ajustable sin tocar lógica) ──────────────────────
class EngineConfig:
    # Betas de correlación (fracción, no porcentaje)
    DXY_BETA     =  0.60   # DXY 1% up → USD/PEN ~+0.60%
    YAHOO_BETA   =  0.40   # Yahoo interbank 1% drift → retail ~+0.40%
    COPPER_BETA  = -0.20   # Cobre 1% up → USD/PEN ~-0.20% (PEN se aprecia)
    RETAIL_BETA  =  0.25   # Retail Peru 1% up → ajuste +0.25% (confirma movimiento interbancario)

    # Freshness y confianza
    FULL_CONF_WINDOW_S  =  60    # segundos antes de empezar a penalizar confianza
    CONF_DECAY_PER_MIN  =   3    # puntos de confianza perdidos por minuto después del umbral
    CONF_MIN            =  20    # confianza mínima posible
    CONF_MAX            =  95    # confianza máxima posible
    STALE_THRESHOLD_S   = 180    # segundos → "posiblemente desactualizado"

    # Volatilidad (stddev USD/PEN entre snapshots)
    VOL_LOW_MAX   = 0.00080    # < este valor → volatilidad baja
    VOL_MED_MAX   = 0.00200    # < este valor → volatilidad media (sino: alta)

    # Tendencia (slope por snapshot de 5 min)
    TREND_STRONG  = 0.00030    # abs(slope) > este → "moderado"
    TREND_LIGHT   = 0.00010    # abs(slope) > este → "leve" (sino lateral)

    # Ventana de snapshots para análisis
    TREND_WINDOW  = 12    # últimos 12 snapshots (~60 min)
    SIGNAL_WINDOW = 6     # últimos 6 snapshots (~30 min) para drift inmediato


# ── Data Transfer Objects ─────────────────────────────────────────────────────

@dataclass
class TrendResult:
    key:   str    # lateral | alcista_leve | alcista_moderado | bajista_leve | bajista_moderado
    label: str    # etiqueta human-readable
    icon:  str    # bootstrap-icons class
    color: str    # CSS color

    @classmethod
    def build(cls, slope: float) -> 'TrendResult':
        cfg = EngineConfig
        if slope > cfg.TREND_STRONG:
            return cls('alcista_moderado', 'Alcista moderado', 'bi-graph-up-arrow', '#10b981')
        if slope > cfg.TREND_LIGHT:
            return cls('alcista_leve',     'Alcista leve',     'bi-arrow-up-right', '#34d399')
        if slope < -cfg.TREND_STRONG:
            return cls('bajista_moderado', 'Bajista moderado', 'bi-graph-down-arrow','#ef4444')
        if slope < -cfg.TREND_LIGHT:
            return cls('bajista_leve',     'Bajista leve',     'bi-arrow-down-right','#f87171')
        return cls('lateral', 'Lateral', 'bi-arrow-right', '#94a3b8')


@dataclass
class VolatilityResult:
    key:   str
    label: str
    color: str

    @classmethod
    def build(cls, stddev: float) -> 'VolatilityResult':
        cfg = EngineConfig
        if stddev < cfg.VOL_LOW_MAX:
            return cls('baja',  'Baja',  '#10b981')
        if stddev < cfg.VOL_MED_MAX:
            return cls('media', 'Media', '#f59e0b')
        return cls('alta',  'Alta',  '#ef4444')


@dataclass
class SignalDetail:
    name:    str
    symbol:  str
    current: Optional[float]
    chg_pct: Optional[float]
    contrib_pct: float   # contribución al ajuste total (en %)


@dataclass
class LiveEstimate:
    ok: bool = False

    # Precios estimados
    live_compra: Optional[float] = None
    live_venta:  Optional[float] = None

    # Desviación vs DATATEC
    dev_compra: Optional[float] = None
    dev_venta:  Optional[float] = None
    adj_pct:    Optional[float] = None   # ajuste total aplicado en %

    # Meta
    confidence:  int = 0
    trend:       TrendResult  = field(default_factory=lambda: TrendResult('lateral','Lateral','bi-arrow-right','#94a3b8'))
    volatility:  VolatilityResult = field(default_factory=lambda: VolatilityResult('baja','Baja','#10b981'))
    datatec_age_s: int = 0
    is_stale:    bool = False

    # Señales individuales
    signals:     List[SignalDetail] = field(default_factory=list)
    insights:    List[str]          = field(default_factory=list)

    # Diagnóstico
    reason:      str = ''

    def to_dict(self) -> dict:
        return {
            'ok':          self.ok,
            'live_compra': self.live_compra,
            'live_venta':  self.live_venta,
            'dev_compra':  self.dev_compra,
            'dev_venta':   self.dev_venta,
            'adj_pct':     self.adj_pct,
            'confidence':  self.confidence,
            'trend': {
                'key':   self.trend.key,
                'label': self.trend.label,
                'icon':  self.trend.icon,
                'color': self.trend.color,
            },
            'volatility': {
                'key':   self.volatility.key,
                'label': self.volatility.label,
                'color': self.volatility.color,
            },
            'datatec_age_s': self.datatec_age_s,
            'is_stale':      self.is_stale,
            'signals': [
                {
                    'name':    s.name,
                    'symbol':  s.symbol,
                    'current': s.current,
                    'chg_pct': s.chg_pct,
                    'contrib': s.contrib_pct,
                } for s in self.signals
            ],
            'insights': self.insights,
            'reason':   self.reason,
        }


# ── Helpers de cálculo ────────────────────────────────────────────────────────

def _f(val) -> Optional[float]:
    """Convierte Decimal/None a float seguro."""
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def _linear_slope(values: List[float]) -> float:
    """
    Regresión lineal simple sobre una serie temporal equidistante.
    Retorna la pendiente (USD/PEN por período).
    """
    n = len(values)
    if n < 2:
        return 0.0
    xs = list(range(n))
    x_mean = (n - 1) / 2
    y_mean = statistics.mean(values)
    num = sum((xs[i] - x_mean) * (values[i] - y_mean) for i in range(n))
    den = sum((xs[i] - x_mean) ** 2 for i in range(n))
    return num / den if den != 0 else 0.0


def _find_baseline_snap(snaps: list, reference_dt: datetime):
    """
    Encuentra el snapshot cuyo captured_at es el más cercano a reference_dt.
    Devuelve None si la diferencia supera 30 minutos (baseline demasiado lejana).
    """
    if not snaps or not reference_dt:
        return None
    best = min(snaps, key=lambda s: abs((s.captured_at - reference_dt).total_seconds()))
    if abs((best.captured_at - reference_dt).total_seconds()) > 1800:
        return None
    return best


# ── Motor principal ───────────────────────────────────────────────────────────

class PricingEngine:
    """
    Calcula la estimación de precio live USD/PEN a partir de:
      - DatatecRate   → ancla manual (source of truth)
      - MarketSnapshot[] → historial de señales de mercado (Yahoo Finance)

    Uso:
        snaps    = MarketSnapshot.query.order_by(...desc).limit(24).all()
        datatec  = DatatecRate.get()
        estimate = PricingEngine.compute(datatec, snaps)
    """

    @staticmethod
    def compute(datatec, snaps: list, retail: dict | None = None) -> LiveEstimate:
        """
        retail (opcional): {
            'avg_sell_now':  float  — promedio venta competidores actual,
            'avg_sell_base': float  — promedio venta competidores al momento del último update DATATEC,
            'avg_buy_now':   float,
            'count':         int    — cantidad de casas de cambio en la muestra,
        }
        """
        cfg = EngineConfig

        # ── 0. Validar datos mínimos ──────────────────────────────────────────
        if not datatec or float(datatec.compra or 0) == 0:
            return LiveEstimate(ok=False, reason='DATATEC no configurado — ingresa Compra y Venta')

        compra_anchor = _f(datatec.compra)
        venta_anchor  = _f(datatec.venta)

        # ── 1. Freshness del DATATEC ──────────────────────────────────────────
        now = now_peru()
        age_s = int((now - datatec.updated_at).total_seconds()) if datatec.updated_at else 0
        is_stale = age_s > cfg.STALE_THRESHOLD_S

        # ── 2. Baseline snapshot (el más cercano al momento del update DATATEC) ──
        # Los snapshots vienen ordenados desc (más reciente primero)
        snaps_asc = list(reversed(snaps))   # orden cronológico para análisis
        latest    = snaps[-1] if snaps else None    # más antiguo no... espera
        # snaps[0] es el MÁS RECIENTE (desc), snaps[-1] es el MÁS ANTIGUO
        latest    = snaps[0] if snaps else None
        baseline  = _find_baseline_snap(snaps, datatec.updated_at) if datatec.updated_at else None

        # ── 3. Extraer valores de señales ─────────────────────────────────────
        dxy_now     = _f(latest.dxy)     if latest else None
        ypen_now    = _f(latest.usdpen)  if latest else None
        copper_now  = _f(latest.copper)  if latest else None

        dxy_base    = _f(baseline.dxy)     if baseline else None
        ypen_base   = _f(baseline.usdpen)  if baseline else None
        copper_base = _f(baseline.copper)  if baseline else None

        # ── 4. Calcular drift por señal ───────────────────────────────────────
        adj_total   = 0.0
        signals     = []

        # --- DXY ---
        dxy_drift   = 0.0
        dxy_contrib = 0.0
        if dxy_now and dxy_base and dxy_base != 0:
            dxy_drift   = (dxy_now - dxy_base) / dxy_base
            dxy_contrib = dxy_drift * cfg.DXY_BETA
            adj_total  += dxy_contrib
        signals.append(SignalDetail(
            name='Índice Dólar (DXY)',
            symbol='DXY',
            current=dxy_now,
            chg_pct=_f(latest.dxy_chg_pct) if latest else None,
            contrib_pct=round(dxy_contrib * 100, 4),
        ))

        # --- Yahoo USD/PEN interbank ---
        ypen_drift   = 0.0
        ypen_contrib = 0.0
        if ypen_now and ypen_base and ypen_base != 0:
            ypen_drift   = (ypen_now - ypen_base) / ypen_base
            ypen_contrib = ypen_drift * cfg.YAHOO_BETA
            adj_total   += ypen_contrib
        signals.append(SignalDetail(
            name='USD/PEN Interbancario',
            symbol='USDPEN',
            current=ypen_now,
            chg_pct=_f(latest.usdpen_chg_pct) if latest else None,
            contrib_pct=round(ypen_contrib * 100, 4),
        ))

        # --- Cobre ---
        copper_drift   = 0.0
        copper_contrib = 0.0
        if copper_now and copper_base and copper_base != 0:
            copper_drift   = (copper_now - copper_base) / copper_base
            copper_contrib = copper_drift * cfg.COPPER_BETA
            adj_total     += copper_contrib
        signals.append(SignalDetail(
            name='Cobre (CMX)',
            symbol='COPPER',
            current=copper_now,
            chg_pct=_f(latest.copper_chg_pct) if latest else None,
            contrib_pct=round(copper_contrib * 100, 4),
        ))

        # --- Retail Peru (promedio casas de cambio online) ---
        retail_drift   = 0.0
        retail_contrib = 0.0
        retail_sell_now  = retail.get('avg_sell_now')  if retail else None
        retail_sell_base = retail.get('avg_sell_base') if retail else None
        retail_count     = retail.get('count', 0)      if retail else 0
        if retail_sell_now and retail_sell_base and retail_sell_base != 0:
            retail_drift   = (retail_sell_now - retail_sell_base) / retail_sell_base
            retail_contrib = retail_drift * cfg.RETAIL_BETA
            adj_total     += retail_contrib
        # chg_pct relativo al precio base (cuánto movió el retail desde baseline)
        retail_chg = round(retail_drift * 100, 3) if retail_sell_now and retail_sell_base else None
        signals.append(SignalDetail(
            name=f'Retail Peru ({retail_count} fintechs)',
            symbol='RETAIL',
            current=retail_sell_now,
            chg_pct=retail_chg,
            contrib_pct=round(retail_contrib * 100, 4),
        ))

        # ── 5. Aplicar ajuste a los precios DATATEC ───────────────────────────
        live_compra = round(compra_anchor * (1 + adj_total), 4)
        live_venta  = round(venta_anchor  * (1 + adj_total), 4)

        # Preservar el spread mínimo (no colapsar la diferencia compra/venta)
        spread_original = venta_anchor - compra_anchor
        if live_venta - live_compra < spread_original * 0.90:
            live_venta = round(live_compra + spread_original, 4)

        dev_compra = round(live_compra - compra_anchor, 4)
        dev_venta  = round(live_venta  - venta_anchor,  4)

        # ── 6. Tendencia y volatilidad ────────────────────────────────────────
        usdpen_series = [
            _f(s.usdpen) for s in snaps[:cfg.TREND_WINDOW]
            if _f(s.usdpen) is not None
        ]
        # snaps está en desc — invertir para que sea cronológico al hacer slope
        usdpen_series = list(reversed(usdpen_series))

        if len(usdpen_series) >= 2:
            slope      = _linear_slope(usdpen_series)
            trend      = TrendResult.build(slope)
            stddev     = statistics.stdev(usdpen_series) if len(usdpen_series) >= 2 else 0.0
            volatility = VolatilityResult.build(stddev)
        else:
            slope      = 0.0
            trend      = TrendResult.build(0.0)
            stddev     = 0.0
            volatility = VolatilityResult.build(0.0)

        # ── 7. Score de confianza ─────────────────────────────────────────────
        age_min    = age_s / 60
        confidence = cfg.CONF_MAX
        confidence -= max(0, age_min - cfg.FULL_CONF_WINDOW_S / 60) * cfg.CONF_DECAY_PER_MIN
        if volatility.key == 'alta':   confidence -= 12
        elif volatility.key == 'media': confidence -= 6
        if not baseline:               confidence -= 15  # sin baseline confiable
        if not ypen_now:               confidence -= 10  # Yahoo no disponible
        if not retail_sell_now:        confidence -= 5   # sin datos retail
        confidence = max(cfg.CONF_MIN, min(cfg.CONF_MAX, int(confidence)))

        # ── 8. Generar insights ───────────────────────────────────────────────
        insights: List[str] = []
        if is_stale:
            insights.append('DATATEC posiblemente rezagado — recomendable actualizar el precio')
        if volatility.key == 'alta':
            insights.append('Alta volatilidad detectada — operar con precaución')
        if abs(dxy_drift) > 0.003:
            direction = 'al alza' if dxy_drift > 0 else 'a la baja'
            insights.append(f'DXY moviéndose {direction} ({dxy_drift*100:+.2f}%) — presión sobre el sol')
        if trend.key in ('alcista_moderado', 'bajista_moderado'):
            insights.append(f'Mercado en tendencia {trend.label.lower()} sostenida')
        if retail_sell_now and retail_sell_base and abs(retail_drift) > 0.001:
            direction = 'al alza' if retail_drift > 0 else 'a la baja'
            insights.append(
                f'Mercado retail moviéndose {direction} ({retail_drift*100:+.2f}%) '
                f'— {retail_count} casas de cambio online confirman el movimiento'
            )
        if abs(adj_total) < 0.00005 and not is_stale:
            insights.append('Mercado estable — DATATEC alineado con señales actuales')

        logger.info(
            '[PricingEngine] adj=%.4f%% compra=%.4f venta=%.4f conf=%d trend=%s vol=%s stale=%s',
            adj_total * 100, live_compra, live_venta, confidence,
            trend.key, volatility.key, is_stale
        )

        return LiveEstimate(
            ok=True,
            live_compra=live_compra,
            live_venta=live_venta,
            dev_compra=dev_compra,
            dev_venta=dev_venta,
            adj_pct=round(adj_total * 100, 4),
            confidence=confidence,
            trend=trend,
            volatility=volatility,
            datatec_age_s=age_s,
            is_stale=is_stale,
            signals=signals,
            insights=insights,
        )
