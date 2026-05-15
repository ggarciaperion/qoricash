"""
Scraper para TuCambista — tucambista.pe
Los tipos de cambio están en <output> tags del HTML de la homepage.
output[0] = compra, output[1] = venta  (para USD/PEN)
(verificado con inspección real del HTML, 2026-03)
"""
import time
import requests
from bs4 import BeautifulSoup
from app.utils.formatters import now_peru
from .base import BaseScraper, RateResult


class TuCambistaScraper(BaseScraper):
    slug = "tucambista"
    url  = "https://www.tucambista.pe"

    def fetch(self) -> RateResult:
        t0   = time.monotonic()
        resp = requests.get(self.url, headers=self.get_headers(), timeout=12, verify=False)
        ms   = int((time.monotonic() - t0) * 1000)
        resp.raise_for_status()

        soup    = BeautifulSoup(resp.text, "lxml")
        outputs = soup.find_all("output")

        if len(outputs) < 2:
            raise ValueError(f"Se esperaban ≥2 <output>, se encontraron {len(outputs)}")

        buy  = self._parse_rate(outputs[0].get_text(strip=True))
        sell = self._parse_rate(outputs[1].get_text(strip=True))

        return RateResult(slug=self.slug, buy_rate=buy, sell_rate=sell,
                          scraped_at=now_peru(), response_ms=ms)
