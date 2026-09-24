"""
Scraper para Okane — okane.pe

CED dejó de actualizar Okane (dato con 174d+ de antigüedad al 2026-06-25).
Implementación directa: API propia + HTML parsing como fallback.

Estrategia:
  1. Endpoints API conocidos de fintechs peruanas similares
  2. __NEXT_DATA__ en HTML (Next.js SSR — expone estado inicial en JSON)
  3. Patrones en script tags
  4. Patrones de texto en HTML visible
"""
import json
import re
import time
import requests
from bs4 import BeautifulSoup
from app.utils.formatters import now_peru
from .base import BaseScraper, RateResult

_SITE_URL = "https://okane.pe"

_API_CANDIDATES = [
    "/api/exchange-rate",
    "/api/tipo-cambio",
    "/api/rates",
    "/api/v1/exchange-rate",
    "/api/v1/tipo-cambio",
    "/api/tc",
    "/v1/rates",
    "/exchange-rates",
]

_RATE_MIN = 2.5
_RATE_MAX = 6.0


class OkaneScraper(BaseScraper):
    slug = "okane"
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
                    timeout=5,   # reducido: 8 endpoints × 5s = 40s máx (vs 64s antes)
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

        # 2. Homepage: __NEXT_DATA__ (Next.js) + script tags + HTML text
        try:
            resp = sess.get(_SITE_URL, headers=self.get_headers(), timeout=12, verify=False)
            ms   = int((time.monotonic() - t0) * 1000)
            soup = BeautifulSoup(resp.text, "lxml")

            # 2a. __NEXT_DATA__
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

            # 2c. Texto visible de la página (rates en elementos HTML)
            buy, sell = self._search_in_text(resp.text)
            if self._valid(buy, sell):
                return RateResult(slug=self.slug, buy_rate=buy, sell_rate=sell,
                                  scraped_at=now_peru(), response_ms=ms)
        except Exception:
            pass

        raise ConnectionError(
            "Okane: no se pudo obtener tasas. "
            "CED dejó de actualizarlos; revisar API de okane.pe manualmente."
        )

    def _parse_json_response(self, data):
        """Extrae (buy, sell) de formatos JSON comunes."""
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
        """Busca patrones buy/sell o compra/venta en texto libre o JSON."""
        buy_m  = re.search(
            r'"(?:buy|compra|buyRate|buy_rate|tipoCambioCompra|purchasePrice)"'
            r'\s*:\s*"?([\d.]+)"?', text)
        sell_m = re.search(
            r'"(?:sell|venta|sellRate|sell_rate|tipoCambioVenta|salePrice)"'
            r'\s*:\s*"?([\d.]+)"?', text)
        try:
            if buy_m and sell_m:
                buy  = self._parse_rate(buy_m.group(1))
                sell = self._parse_rate(sell_m.group(1))
                return buy, sell
        except Exception:
            pass
        return None, None

    def _valid(self, buy, sell):
        return (buy and sell
                and _RATE_MIN < buy < _RATE_MAX
                and _RATE_MIN < sell < _RATE_MAX
                and buy < sell)
