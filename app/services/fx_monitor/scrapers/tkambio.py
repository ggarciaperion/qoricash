"""
Scraper para TKambio — tkambio.com

CED dejó de actualizar TKambio (dato con 14d+ de antigüedad al 2026-06-25).
Implementación directa: API propia + HTML parsing como fallback.

Estrategia:
  1. Endpoints API conocidos de fintechs peruanas similares
  2. __NEXT_DATA__ en HTML (Next.js SSR)
  3. Patrones en script tags
  4. Patrones de texto en HTML visible
"""
import re
import time
import requests
from bs4 import BeautifulSoup
from app.utils.formatters import now_peru
from .base import BaseScraper, RateResult

_SITE_URL = "https://tkambio.com"

_API_CANDIDATES = [
    "/api/tipo-cambio",
    "/api/exchange-rate",
    "/api/rates",
    "/api/v1/tipo-cambio",
    "/api/v1/exchange-rate",
    "/api/tc",
    "/v1/tipo-cambio",
    "/exchange-rates",
    "/api/cambio",
]

_RATE_MIN = 2.5
_RATE_MAX = 6.0


class TKambioScraper(BaseScraper):
    slug = "tkambio"
    url  = _SITE_URL

    def fetch(self) -> RateResult:
        t0   = time.monotonic()
        sess = requests.Session()

        headers_json = self.get_json_headers()
        headers_json["Referer"] = _SITE_URL + "/"

        # 1. Intentar endpoints API
        for path in _API_CANDIDATES:
            try:
                resp = sess.get(
                    _SITE_URL + path,
                    headers=headers_json,
                    timeout=8,
                    verify=False,
                )
                if resp.status_code != 200:
                    continue
                buy, sell = self._parse_json_response(resp.json())
                if self._valid(buy, sell):
                    ms = int((time.monotonic() - t0) * 1000)
                    return RateResult(slug=self.slug, buy_rate=buy, sell_rate=sell,
                                      scraped_at=now_peru(), response_ms=ms)
            except Exception:
                continue

        # 2. Homepage: __NEXT_DATA__ + script tags + HTML text
        try:
            resp = sess.get(_SITE_URL, headers=self.get_headers(), timeout=12, verify=False)
            ms   = int((time.monotonic() - t0) * 1000)
            soup = BeautifulSoup(resp.text, "lxml")

            # 2a. __NEXT_DATA__ (Next.js SSR)
            nd = soup.find("script", id="__NEXT_DATA__")
            if nd and nd.string:
                buy, sell = self._search_in_text(nd.string)
                if self._valid(buy, sell):
                    return RateResult(slug=self.slug, buy_rate=buy, sell_rate=sell,
                                      scraped_at=now_peru(), response_ms=ms)

            # 2b. Todos los script tags
            for script in soup.find_all("script"):
                text = script.string or ""
                buy, sell = self._search_in_text(text)
                if self._valid(buy, sell):
                    return RateResult(slug=self.slug, buy_rate=buy, sell_rate=sell,
                                      scraped_at=now_peru(), response_ms=ms)

            # 2c. HTML completo
            buy, sell = self._search_in_text(resp.text)
            if self._valid(buy, sell):
                return RateResult(slug=self.slug, buy_rate=buy, sell_rate=sell,
                                  scraped_at=now_peru(), response_ms=ms)
        except Exception:
            pass

        raise ConnectionError(
            "TKambio: no se pudo obtener tasas. "
            "CED dejó de actualizarlos; revisar API de tkambio.com manualmente."
        )

    def _parse_json_response(self, data):
        _KEYS_BUY  = ("buy", "compra", "buyRate", "buy_rate", "tipoCambioCompra",
                      "purchase", "purchasePrice", "tc_compra")
        _KEYS_SELL = ("sell", "venta",  "sellRate", "sell_rate", "tipoCambioVenta",
                      "sale",  "salePrice",     "tc_venta")
        if isinstance(data, list) and data:
            data = data[0]
        if isinstance(data, dict):
            buy  = self._safe_parse(data, _KEYS_BUY)
            sell = self._safe_parse(data, _KEYS_SELL)
            return buy, sell
        return None, None

    def _safe_parse(self, obj, keys):
        for k in keys:
            if k in obj and obj[k]:
                try:
                    return self._parse_rate(obj[k])
                except Exception:
                    pass
        return None

    def _search_in_text(self, text):
        buy_m  = re.search(
            r'"(?:buy|compra|buyRate|buy_rate|tipoCambioCompra|purchasePrice)"'
            r'\s*:\s*"?([\d.]+)"?', text)
        sell_m = re.search(
            r'"(?:sell|venta|sellRate|sell_rate|tipoCambioVenta|salePrice)"'
            r'\s*:\s*"?([\d.]+)"?', text)
        try:
            if buy_m and sell_m:
                return self._parse_rate(buy_m.group(1)), self._parse_rate(sell_m.group(1))
        except Exception:
            pass
        return None, None

    def _valid(self, buy, sell):
        return (buy and sell
                and _RATE_MIN < buy < _RATE_MAX
                and _RATE_MIN < sell < _RATE_MAX
                and buy < sell)
