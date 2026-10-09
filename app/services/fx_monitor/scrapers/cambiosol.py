"""
Scraper para Cambiosol — cambiosol.pe
Los tipos de cambio están embebidos en un <script> inline del HTML:
  const rates = { buy: 3.438, sell: 3.465 };
Scrape directo — reemplaza la fuente CED que estaba desactualizada.
(actualizado 2026-10-09)
"""
import re
import time
import requests
from .base import BaseScraper, RateResult
from app.utils.formatters import now_peru


class CambiosolScraper(BaseScraper):
    slug = "cambiosol"
    url  = "https://cambiosol.pe"

    def fetch(self) -> RateResult:
        t0   = time.monotonic()
        resp = self.get_session().get(self.url, headers=self.get_headers(), timeout=12, verify=False)
        ms   = int((time.monotonic() - t0) * 1000)
        resp.raise_for_status()

        # const rates = { buy: 3.438, sell: 3.465 };
        buy_m  = re.search(r'buy\s*:\s*([\d.]+)', resp.text)
        sell_m = re.search(r'sell\s*:\s*([\d.]+)', resp.text)

        if not buy_m or not sell_m:
            raise ValueError("Cambiosol: no se encontró 'buy'/'sell' en el script inline del HTML")

        buy  = self._parse_rate(buy_m.group(1))
        sell = self._parse_rate(sell_m.group(1))

        return RateResult(slug=self.slug, buy_rate=buy, sell_rate=sell,
                          scraped_at=now_peru(), response_ms=ms)
