"""
Scraper para TuCambista — tucambista.pe
La página es Next.js con Server Components — los datos se entregan en el payload RSC.
Se obtienen haciendo GET con header "RSC: 1" y parseando el JSON embebido.
Estructura: competition:[{"id":0,"entity":"tucambista","buyExchangeRate":X,"sellExchangeRate":Y,...}]
(verificado 2026-05)
"""
import re
import time
import json
import requests
from app.utils.formatters import now_peru
from .base import BaseScraper, RateResult


class TuCambistaScraper(BaseScraper):
    slug = "tucambista"
    url  = "https://www.tucambista.pe"

    def fetch(self) -> RateResult:
        t0 = time.monotonic()

        headers = self.get_headers()
        headers.update({
            "Accept": "text/x-component",
            "RSC":    "1",
            "Next-Router-State-Tree": (
                "%5B%22%22%2C%7B%22children%22%3A%5B%22__PAGE__%22%2C%7B%7D%5D%7D"
                "%2Cnull%2Cnull%2Ctrue%5D"
            ),
        })

        resp = requests.get(self.url, headers=headers, timeout=12, verify=False)
        ms   = int((time.monotonic() - t0) * 1000)
        resp.raise_for_status()

        # Extraer el bloque competition del payload RSC
        m = re.search(r'"competition"\s*:\s*(\[.*?\])', resp.text, re.DOTALL)
        if not m:
            raise ValueError("TuCambista: no se encontró 'competition' en el payload RSC")

        entries = json.loads(m.group(1))
        for entry in entries:
            if str(entry.get("entity", "")).lower() == "tucambista":
                buy  = self._parse_rate(entry["buyExchangeRate"])
                sell = self._parse_rate(entry["sellExchangeRate"])
                return RateResult(slug=self.slug, buy_rate=buy, sell_rate=sell,
                                  scraped_at=now_peru(), response_ms=ms)

        raise ValueError("TuCambista: no se encontró entry 'tucambista' en competition")
