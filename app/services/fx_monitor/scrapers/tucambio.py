"""
Scraper para TuCambio — tucambio.pe / cambiafx.pe
El backend real está en https://cambiafx.pe/api/tc
Respuesta: {"status":200,"data":[{"tc_compra":3.446,"tc_venta":3.47,...}]}
(verificado con inspección real del HTML + API, 2026-03)
"""
import time
import requests
from app.utils.formatters import now_peru
from .base import BaseScraper, RateResult


class TuCambioScraper(BaseScraper):
    slug    = "tucambio"
    url     = "https://www.tucambio.pe"
    api_url = "https://cambiafx.pe/api/tc"

    def fetch(self) -> RateResult:
        t0 = time.monotonic()

        resp = requests.get(
            self.api_url,
            headers={**self.get_json_headers(), "Referer": "https://www.tucambio.pe/"},
            timeout=10,
            verify=False,
        )
        ms = int((time.monotonic() - t0) * 1000)
        resp.raise_for_status()

        data = resp.json()
        # Estructura: {"status":200,"data":[{"tc_compra":3.446,"tc_venta":3.47,...}]}
        items = data.get("data") or []
        if not items:
            raise ValueError("cambiafx.pe/api/tc devolvió data vacía")

        row  = items[0]
        buy  = self._parse_rate(row.get("tc_compra") or row.get("compra") or row.get("buy"))
        sell = self._parse_rate(row.get("tc_venta")  or row.get("venta")  or row.get("sell"))

        return RateResult(slug=self.slug, buy_rate=buy, sell_rate=sell,
                          scraped_at=now_peru(), response_ms=ms)
