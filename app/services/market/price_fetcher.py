"""
Recolector de precios financieros.
Usa Yahoo Finance JSON API directamente (más confiable en producción que la librería yfinance).
Fallback para USD/PEN: ExchangeRate-API (open.er-api.com, sin key).
"""
import logging
import requests
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# ── Símbolo Yahoo Finance → nombre interno ────────────────────────────────────
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
    'usdjpy': 'JPY=X',
    'btc':    'BTC-USD',
}

_YAHOO_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/122.0.0.0 Safari/537.36'
    ),
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://finance.yahoo.com/',
    'Origin': 'https://finance.yahoo.com',
}

# Sesión compartida para reutilizar cookies entre requests
_session: Optional[requests.Session] = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update(_YAHOO_HEADERS)
        # Visitar la página principal para obtener cookies iniciales
        try:
            _session.get('https://finance.yahoo.com/', timeout=8)
        except Exception:
            pass
    return _session


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


def _fetch_yahoo_v8(key: str, sym: str) -> AssetPrice:
    """Llama directo al endpoint JSON v8 de Yahoo Finance (evita la librería yfinance)."""
    try:
        sess = _get_session()
        url  = f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}'
        resp = sess.get(url, params={'interval': '1d', 'range': '2d'}, timeout=15)
        resp.raise_for_status()
        data   = resp.json()
        result = data.get('chart', {}).get('result')
        if not result:
            err = data.get('chart', {}).get('error', {})
            return AssetPrice(key, ok=False, error=str(err)[:120])
        meta   = result[0].get('meta', {})
        price  = meta.get('regularMarketPrice') or meta.get('chartPreviousClose')
        prev   = meta.get('previousClose') or meta.get('chartPreviousClose')
        if not price:
            return AssetPrice(key, ok=False, error='Sin precio en meta')
        chg = round((price - prev) / prev * 100, 3) if prev and prev != 0 else None
        return AssetPrice(
            key, price=round(float(price), 4),
            prev=round(float(prev), 4) if prev else None,
            chg_pct=chg, ok=True
        )
    except Exception as e:
        return AssetPrice(key, ok=False, error=str(e)[:120])


def _fetch_yahoo_v10(key: str, sym: str) -> AssetPrice:
    """Fallback: endpoint v10/quoteSummary de Yahoo Finance."""
    try:
        sess = _get_session()
        url  = f'https://query2.finance.yahoo.com/v10/finance/quoteSummary/{sym}'
        resp = sess.get(url, params={'modules': 'price'}, timeout=15)
        resp.raise_for_status()
        data   = resp.json()
        price_mod = (
            data.get('quoteSummary', {})
            .get('result', [{}])[0]
            .get('price', {})
        )
        price = price_mod.get('regularMarketPrice', {}).get('raw')
        prev  = price_mod.get('regularMarketPreviousClose', {}).get('raw')
        if not price:
            return AssetPrice(key, ok=False, error='Sin precio en v10')
        chg = round((price - prev) / prev * 100, 3) if prev and prev != 0 else None
        return AssetPrice(
            key, price=round(float(price), 4),
            prev=round(float(prev), 4) if prev else None,
            chg_pct=chg, ok=True
        )
    except Exception as e:
        return AssetPrice(key, ok=False, error=str(e)[:120])


def _fetch_usdpen_fallback() -> AssetPrice:
    """
    Fallback para USD/PEN cuando Yahoo Finance falla.
    Usa open.er-api.com (libre, sin clave API).
    """
    try:
        resp = requests.get(
            'https://open.er-api.com/v6/latest/USD',
            timeout=10,
            headers={'User-Agent': 'QoriCash/1.0'}
        )
        resp.raise_for_status()
        data  = resp.json()
        rate  = data.get('rates', {}).get('PEN')
        if not rate:
            return AssetPrice('usdpen', ok=False, error='PEN no en respuesta')
        return AssetPrice('usdpen', price=round(float(rate), 4), ok=True)
    except Exception as e:
        return AssetPrice('usdpen', ok=False, error=f'Fallback: {str(e)[:80]}')


def _fetch_single(key: str, sym: str) -> AssetPrice:
    """Intenta v8, luego v10. Para usdpen agrega fallback ExchangeRate-API."""
    result = _fetch_yahoo_v8(key, sym)
    if result.ok:
        return result

    logger.debug(f"[Mercado] v8 falló para {sym}: {result.error} — intentando v10")
    result = _fetch_yahoo_v10(key, sym)
    if result.ok:
        return result

    logger.debug(f"[Mercado] v10 falló para {sym}: {result.error}")

    if key == 'usdpen':
        logger.debug('[Mercado] Usando fallback ExchangeRate-API para usdpen')
        result = _fetch_usdpen_fallback()

    if not result.ok:
        logger.warning(f'[Mercado] ❌ {key} ({sym}): {result.error}')

    return result


def fetch_all_prices() -> MarketPrices:
    result = MarketPrices()
    for key, sym in TICKERS.items():
        ap = _fetch_single(key, sym)
        setattr(result, key, ap)
        if ap.ok:
            logger.debug(f'[Mercado] ✅ {key}: {ap.price} ({ap.chg_pct:+.3f}%)')
        else:
            logger.warning(f'[Mercado] ❌ {key}: {ap.error}')
    return result
