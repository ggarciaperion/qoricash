"""
Scraper para Kambista — kambista.com
Los tipos de cambio están en la página /tc con elementos id="valcompra" y id="valventa"
(verificado con inspección real del HTML, 2026-03)
"""
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from .base import BaseScraper, RateResult


class KambistaScraper(BaseScraper):
    slug = "kambista"
    url  = "https://kambista.com/tc"

    def fetch(self) -> RateResult:
        t0   = time.monotonic()
        sess = requests.Session()
        resp = sess.get(self.url, headers=self.get_headers(), timeout=12, verify=False)
        ms   = int((time.monotonic() - t0) * 1000)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")

        buy_el  = soup.find(id="valcompra")
        sell_el = soup.find(id="valventa")

        if not buy_el or not sell_el:
            raise ValueError("No se encontraron #valcompra / #valventa en kambista.com/tc")

        buy  = self._parse_rate(buy_el.get_text(strip=True))
        sell = self._parse_rate(sell_el.get_text(strip=True))

        return RateResult(slug=self.slug, buy_rate=buy, sell_rate=sell,
                          scraped_at=datetime.utcnow(), response_ms=ms)
