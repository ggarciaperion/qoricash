"""
Scraper para Cambio Mundial — cambiomundial.com
SPA Angular con backend propio. Se prueban varios endpoints en orden hasta
obtener tasas válidas. Fallback final: parsing del HTML principal.

Endpoints conocidos (más reciente primero):
  /backend/tasaCambio/daily  — formato [{buy, sell, tipoTasa, fecha}]
  /backend/tasaCambio/today  — mismo formato, posible alias
  /backend/tasaCambio        — sin sufijo
  /api/tasaCambio/daily      — variante con prefijo /api
  /api/tipo-cambio           — formato genérico

Fuente CED descartada: data congelada desde 2026-05-25.
"""
import re
import time
import requests
from bs4 import BeautifulSoup
from app.utils.formatters import now_peru
from .base import BaseScraper, RateResult

_SITE_URL = "https://www.cambiomundial.com"

_API_CANDIDATES = [
    "/backend/tasaCambio/daily",
    "/backend/tasaCambio/today",
    "/backend/tasaCambio",
    "/backend/api/tasaCambio/daily",
    "/api/tasaCambio/daily",
    "/api/tipo-cambio",
    "/api/exchange-rate",
]


class CambioMundialScraper(BaseScraper):
    slug = "cambiomundial"
    url  = _SITE_URL

    def fetch(self) -> RateResult:
        t0   = time.monotonic()
        sess = requests.Session()

        # Warm-up: obtener cookies de sesión y parecer navegador real
        try:
            sess.get(_SITE_URL, headers=self.get_headers(), timeout=8, verify=False)
        except Exception:
            pass

        headers_json = self.get_json_headers()
        headers_json.update({
            "Referer": _SITE_URL + "/",
            "Origin":  _SITE_URL,
        })

        # 1. Intentar endpoints API conocidos
        for path in _API_CANDIDATES:
            try:
                resp = sess.get(
                    _SITE_URL + path,
                    headers=headers_json,
                    timeout=10,
                    verify=False,
                )
                if resp.status_code != 200:
                    continue
                data = resp.json()
                buy, sell = self._extract_from_json(data)
                if buy and sell and buy < sell:
                    ms = int((time.monotonic() - t0) * 1000)
                    return RateResult(slug=self.slug, buy_rate=buy, sell_rate=sell,
                                      scraped_at=now_peru(), response_ms=ms)
            except Exception:
                continue

        # 2. Fallback: buscar tasas en el HTML (script tags / JSON embebido)
        try:
            resp = sess.get(_SITE_URL, headers=self.get_headers(), timeout=12, verify=False)
            ms   = int((time.monotonic() - t0) * 1000)
            soup = BeautifulSoup(resp.text, "lxml")
            for script in soup.find_all("script"):
                text = script.string or ""
                buy, sell = self._extract_from_script(text)
                if buy and sell and buy < sell:
                    return RateResult(slug=self.slug, buy_rate=buy, sell_rate=sell,
                                      scraped_at=now_peru(), response_ms=ms)
        except Exception:
            pass

        raise ConnectionError(
            "CambioMundial: todos los endpoints fallaron. "
            "Verificar si /backend/tasaCambio/daily cambió de path o requiere auth."
        )

    def _extract_from_json(self, data):
        """Extrae (buy, sell) de los formatos JSON conocidos de CambioMundial."""
        try:
            if isinstance(data, list) and data:
                entry = next(
                    (r for r in data if str(r.get("tipoTasa", "")).upper() == "REGULAR"),
                    data[0]
                )
                buy  = self._safe_parse(entry, ("buy", "compra", "buyRate", "tipoCambioCompra"))
                sell = self._safe_parse(entry, ("sell", "venta",  "sellRate", "tipoCambioVenta"))
                return buy, sell
            if isinstance(data, dict):
                buy  = self._safe_parse(data, ("buy", "compra", "buyRate", "tipoCambioCompra"))
                sell = self._safe_parse(data, ("sell", "venta",  "sellRate", "tipoCambioVenta"))
                return buy, sell
        except Exception:
            pass
        return None, None

    def _safe_parse(self, obj, keys):
        for k in keys:
            if k in obj and obj[k]:
                try:
                    return self._parse_rate(obj[k])
                except Exception:
                    pass
        return None

    def _extract_from_script(self, text):
        """Busca patrones buy/sell o compra/venta en texto de script."""
        buy_m  = re.search(
            r'"(?:buy|compra|buyRate|tipoCambioCompra)"\s*:\s*"?([\d.]+)"?', text)
        sell_m = re.search(
            r'"(?:sell|venta|sellRate|tipoCambioVenta)"\s*:\s*"?([\d.]+)"?', text)
        try:
            if buy_m and sell_m:
                return self._parse_rate(buy_m.group(1)), self._parse_rate(sell_m.group(1))
        except Exception:
            pass
        return None, None
