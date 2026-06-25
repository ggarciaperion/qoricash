"""
Scraper para CambiaFX — cambiafx.pe
API directa: GET https://cambiafx.pe/api/tc
Respuesta: {"status":200,"data":[{"tc_compra":3.399,"tc_venta":3.416,...}]}

Nota: CambiaFX y TuCambio comparten el mismo backend.
(Reemplaza CED — el dato de CED estaba 21 días desactualizado a 2026-06-25)
"""
import time
import requests
from app.utils.formatters import now_peru
from .base import BaseScraper, RateResult

_API_URL = "https://cambiafx.pe/api/tc"


class CambiaFXScraper(BaseScraper):
    slug = "cambiafx"
    url  = "https://cambiafx.pe"

    def fetch(self) -> RateResult:
        t0 = time.monotonic()
        resp = requests.get(
            _API_URL,
            headers={**self.get_json_headers(), "Referer": self.url + "/"},
            timeout=10,
            verify=False,
        )
        ms = int((time.monotonic() - t0) * 1000)
        resp.raise_for_status()

        data  = resp.json()
        items = data.get("data") or []
        if not items:
            raise ValueError("CambiaFX API: data vacía")

        row  = items[0]
        buy  = self._parse_rate(row.get("tc_compra") or row.get("compra") or row.get("buy"))
        sell = self._parse_rate(row.get("tc_venta")  or row.get("venta")  or row.get("sell"))

        return RateResult(slug=self.slug, buy_rate=buy, sell_rate=sell,
                          scraped_at=now_peru(), response_ms=ms)
