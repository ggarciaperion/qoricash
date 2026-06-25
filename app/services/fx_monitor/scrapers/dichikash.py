"""
Scraper para Dichikash — dichikash.com
Los tipos de cambio están en inputs ocultos en el HTML:
  <input type="hidden" id="numero2" ... value="3.402" />  ← compra
  <input type="hidden" id="numero3" ... value="3.415" />  ← venta
(Reemplaza CED — dato CED tenía 3+ días de desactualización a 2026-06-25)
"""
import time
import requests
from bs4 import BeautifulSoup
from app.utils.formatters import now_peru
from .base import BaseScraper, RateResult


class DichikashScraper(BaseScraper):
    slug = "dichikash"
    url  = "https://dichikash.com"

    def fetch(self) -> RateResult:
        t0   = time.monotonic()
        resp = requests.get(self.url, headers=self.get_headers(), timeout=12, verify=False)
        ms   = int((time.monotonic() - t0) * 1000)
        resp.raise_for_status()

        soup    = BeautifulSoup(resp.text, "lxml")
        buy_el  = soup.find(id="numero2")
        sell_el = soup.find(id="numero3")

        if buy_el and sell_el:
            buy  = self._parse_rate(buy_el.get("value", ""))
            sell = self._parse_rate(sell_el.get("value", ""))
            return RateResult(slug=self.slug, buy_rate=buy, sell_rate=sell,
                              scraped_at=now_peru(), response_ms=ms)

        raise ValueError("Dichikash: no se encontraron #numero2 / #numero3 en el HTML")
