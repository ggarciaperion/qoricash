"""
Scraper para Moneyhouse — moneyhouse.pe
(Nota: el dominio anterior moneyhouse.com.pe tiene falla de DNS)
Las tasas están en:
  div.views-field-field-t-c-compra → span.cantant  (compra)
  div.views-field-field-t-c-venta  → span.cantant  (venta)
(verificado con inspección real del HTML, 2026-03)
"""
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from .base import BaseScraper, RateResult


class MoneyhouseScraper(BaseScraper):
    slug = "moneyhouse"
    url  = "https://moneyhouse.pe"

    def fetch(self) -> RateResult:
        t0   = time.monotonic()
        sess = requests.Session()
        resp = sess.get(self.url, headers=self.get_headers(), timeout=12, verify=False)
        ms   = int((time.monotonic() - t0) * 1000)
        resp.raise_for_status()

        soup    = BeautifulSoup(resp.text, "lxml")
        buy_div  = soup.find("div", class_="views-field-field-t-c-compra")
        sell_div = soup.find("div", class_="views-field-field-t-c-venta")

        if buy_div and sell_div:
            buy_span  = buy_div.find("span", class_="cantant")
            sell_span = sell_div.find("span", class_="cantant")
            if buy_span and sell_span:
                buy  = self._parse_rate(buy_span.get_text(strip=True))
                sell = self._parse_rate(sell_span.get_text(strip=True))
                return RateResult(slug=self.slug, buy_rate=buy, sell_rate=sell,
                                  scraped_at=datetime.utcnow(), response_ms=ms)

        raise ValueError("Moneyhouse: no se encontraron div.views-field-field-t-c-compra/venta")
