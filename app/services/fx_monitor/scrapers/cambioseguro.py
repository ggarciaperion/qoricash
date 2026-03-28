"""
Scraper para Cambio Seguro — cambioseguro.com
Los tipos de cambio están en <span class="value-rate"> (primero=compra, segundo=venta)
(verificado con inspección real del HTML, 2026-03)
"""
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from .base import BaseScraper, RateResult


class CambioSeguroScraper(BaseScraper):
    slug = "cambioseguro"
    url  = "https://cambioseguro.com"

    def fetch(self) -> RateResult:
        t0   = time.monotonic()
        resp = requests.get(self.url, headers=self.get_headers(), timeout=12, verify=False)
        ms   = int((time.monotonic() - t0) * 1000)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # <span class="value-rate">3.4360</span>  (compra)
        # <span class="value-rate">3.4700</span>  (venta)
        rate_els = soup.find_all("span", class_="value-rate")

        if len(rate_els) >= 2:
            buy  = self._parse_rate(rate_els[0].get_text(strip=True))
            sell = self._parse_rate(rate_els[1].get_text(strip=True))
        else:
            raise ValueError(f"Se esperaban ≥2 span.value-rate, se encontraron {len(rate_els)}")

        return RateResult(slug=self.slug, buy_rate=buy, sell_rate=sell,
                          scraped_at=datetime.utcnow(), response_ms=ms)
