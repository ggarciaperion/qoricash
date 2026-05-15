"""
Scraper para Rextie — www.rextie.com
(Nota: el dominio anterior rexti.com era incorrecto — el correcto es rextie.com)
La página es Angular con SSR — las tasas se renderizan en el HTML estático.
Estructura: <div class="text-xs text-gray-200">Compra:</div>
             <div class="font-semibold text-xs"> s/ 3.4535 <!-- --></div>
(verificado con inspección real del HTML, 2026-03)
"""
import re
import time
import requests
from bs4 import BeautifulSoup
from app.utils.formatters import now_peru
from .base import BaseScraper, RateResult


class RextiScraper(BaseScraper):
    slug = "rextie"
    url  = "https://www.rextie.com"

    def fetch(self) -> RateResult:
        t0   = time.monotonic()
        resp = requests.get(self.url, headers=self.get_headers(), timeout=12, verify=False)
        ms   = int((time.monotonic() - t0) * 1000)
        resp.raise_for_status()

        # Angular SSR — decode as UTF-8 (page declares ISO-8859-1 but is actually UTF-8)
        html = resp.content.decode("utf-8", errors="replace")
        soup = BeautifulSoup(html, "lxml")

        buy  = None
        sell = None

        # Find label divs "Compra:" / "Venta:" and read the following sibling div
        for label_el in soup.find_all("div", class_=lambda c: c and "text-gray-200" in c):
            label = label_el.get_text(strip=True)
            sibling = label_el.find_next_sibling("div")
            if not sibling:
                continue
            raw = sibling.get_text(strip=True)
            # Strip "s/" prefix and any Angular comments
            m = re.search(r'[\d]+\.[\d]+', raw)
            if not m:
                continue
            rate = self._parse_rate(m.group())
            if "Compra" in label:
                buy = rate
            elif "Venta" in label:
                sell = rate

        if buy and sell:
            return RateResult(slug=self.slug, buy_rate=buy, sell_rate=sell,
                              scraped_at=now_peru(), response_ms=ms)

        raise ValueError("Rextie: no se encontraron tasas Compra/Venta en el HTML")
