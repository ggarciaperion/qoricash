"""
Scraper para Dichikash — dichikash.com
Las tasas están como inputs hidden en la calculadora:
  <input type="hidden" id="numero2" name="numero2" value="3.441" />  → compra
  <input type="hidden" id="numero3" name="numero3" value="3.471" />  → venta
(verificado con inspección real del HTML, 2026-03)
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
        sess = requests.Session()
        resp = sess.get(self.url, headers=self.get_headers(), timeout=12, verify=False)
        ms   = int((time.monotonic() - t0) * 1000)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.content.decode("utf-8", errors="replace"), "lxml")

        buy_el  = soup.find("input", attrs={"id": "numero2"})
        sell_el = soup.find("input", attrs={"id": "numero3"})

        if not buy_el or not sell_el:
            raise ValueError("Dichikash: no se encontraron inputs #numero2 / #numero3")

        buy  = self._parse_rate(buy_el.get("value", ""))
        sell = self._parse_rate(sell_el.get("value", ""))

        return RateResult(slug=self.slug, buy_rate=buy, sell_rate=sell,
                          scraped_at=now_peru(), response_ms=ms)
