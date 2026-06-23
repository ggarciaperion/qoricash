"""
Scraper para Cambio Mundial — cambiomundial.com
SPA Angular con backend propio en cambiomundial.com/backend.

Endpoint directo: GET /backend/tasaCambio/daily
Respuesta: [{"buy":3.406,"sell":3.414,"tipoTasa":"REGULAR","fecha":"..."}, ...]
Se filtra tipoTasa == "REGULAR" como tasa pública estándar.

Fuente anterior (CED) descartada: su data estaba desactualizada desde 2026-05-25.
"""
import time
import requests
from app.utils.formatters import now_peru
from .base import BaseScraper, RateResult

_API_URL = "https://www.cambiomundial.com/backend/tasaCambio/daily"
_SITE_URL = "https://www.cambiomundial.com"


class CambioMundialScraper(BaseScraper):
    slug = "cambiomundial"
    url  = _SITE_URL

    def fetch(self) -> RateResult:
        t0 = time.monotonic()

        headers = self.get_json_headers()
        headers.update({
            "Referer": _SITE_URL + "/",
            "Origin":  _SITE_URL,
        })

        resp = requests.get(_API_URL, headers=headers, timeout=10, verify=False)
        ms   = int((time.monotonic() - t0) * 1000)
        resp.raise_for_status()

        data = resp.json()
        if not isinstance(data, list) or not data:
            raise ValueError(f"CambioMundial: respuesta inesperada — {str(data)[:200]}")

        # Preferir tipoTasa == "REGULAR"; si no existe, tomar el primer entry
        entry = next((r for r in data if str(r.get("tipoTasa", "")).upper() == "REGULAR"), data[0])

        buy  = self._parse_rate(entry["buy"])
        sell = self._parse_rate(entry["sell"])

        return RateResult(slug=self.slug, buy_rate=buy, sell_rate=sell,
                          scraped_at=now_peru(), response_ms=ms)
