"""
Recolector de precios via yfinance.
Fase 1: USD/PEN, Oro, Petróleo, S&P500, Nasdaq, DXY
Fase 3: + VIX, Cobre, Bono 10Y, EUR/USD, ETF Emergentes (EEM), ETF Perú (EPU)
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

TICKERS = {
    # Fase 1
    'usdpen':       'USDPEN=X',
    'gold':         'GC=F',
    'oil':          'CL=F',
    'sp500':        '^GSPC',
    'nasdaq':       '^IXIC',
    'dxy':          'DX-Y.NYB',
    # Fase 3 — macro
    'vix':          '^VIX',
    'copper':       'HG=F',
    'treasury_10y': '^TNX',
    'eurusd':       'EURUSD=X',
    'eem':          'EEM',
    'epu':          'EPU',
    # Fase 4 — riesgo global
    'usdjpy': 'JPY=X',   # USD/JPY — risk-off indicator
    'btc':    'BTC-USD', # Bitcoin — risk sentiment
}


@dataclass
class AssetPrice:
    key:     str
    price:   Optional[float] = None
    prev:    Optional[float] = None
    chg_pct: Optional[float] = None
    ok:      bool = True
    error:   Optional[str] = None


@dataclass
class MarketPrices:
    fetched_at:   datetime = field(default_factory=datetime.utcnow)
    usdpen:       AssetPrice = field(default_factory=lambda: AssetPrice('usdpen'))
    gold:         AssetPrice = field(default_factory=lambda: AssetPrice('gold'))
    oil:          AssetPrice = field(default_factory=lambda: AssetPrice('oil'))
    sp500:        AssetPrice = field(default_factory=lambda: AssetPrice('sp500'))
    nasdaq:       AssetPrice = field(default_factory=lambda: AssetPrice('nasdaq'))
    dxy:          AssetPrice = field(default_factory=lambda: AssetPrice('dxy'))
    vix:          AssetPrice = field(default_factory=lambda: AssetPrice('vix'))
    copper:       AssetPrice = field(default_factory=lambda: AssetPrice('copper'))
    treasury_10y: AssetPrice = field(default_factory=lambda: AssetPrice('treasury_10y'))
    eurusd:       AssetPrice = field(default_factory=lambda: AssetPrice('eurusd'))
    eem:          AssetPrice = field(default_factory=lambda: AssetPrice('eem'))
    epu:          AssetPrice = field(default_factory=lambda: AssetPrice('epu'))
    usdjpy:       AssetPrice = field(default_factory=lambda: AssetPrice('usdjpy'))
    btc:          AssetPrice = field(default_factory=lambda: AssetPrice('btc'))


def _fetch_single(key: str, sym: str) -> AssetPrice:
    try:
        import yfinance as yf
        t    = yf.Ticker(sym)
        info = t.fast_info
        price = info.last_price
        prev  = info.previous_close
        if price is None or price == 0:
            return AssetPrice(key, ok=False, error="Sin precio")
        chg = round((price - prev) / prev * 100, 3) if prev and prev != 0 else None
        return AssetPrice(key, price=round(float(price), 4),
                          prev=round(float(prev), 4) if prev else None,
                          chg_pct=chg, ok=True)
    except Exception as e:
        logger.warning(f"[Mercado] Error {sym}: {e}")
        return AssetPrice(key, ok=False, error=str(e)[:120])


def fetch_all_prices() -> MarketPrices:
    result = MarketPrices()
    for key, sym in TICKERS.items():
        ap = _fetch_single(key, sym)
        setattr(result, key, ap)
        if ap.ok:
            logger.debug(f"[Mercado] ✅ {key}: {ap.price} ({ap.chg_pct:+.2f}%)")
        else:
            logger.debug(f"[Mercado] ❌ {key}: {ap.error}")
    return result
