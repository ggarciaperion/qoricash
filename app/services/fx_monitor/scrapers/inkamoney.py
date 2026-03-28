"""
Scraper para InkaMoney — inkamoney.com
Las tasas están en un web-component Vue renderizado en el servidor:
  <inka-conversor-home :sale-price="3.464" :buy-price="3.446">
  :buy-price  = compra (QoriCash compra USD al cliente)
  :sale-price = venta  (QoriCash vende USD al cliente)
(verificado con inspección real del HTML, 2026-03)
"""
import re
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from .base import BaseScraper, RateResult


class InkaMoneyPeru(BaseScraper):
    slug = "inkamoney"
    url  = "https://inkamoney.com"

    def fetch(self) -> RateResult:
        t0   = time.monotonic()
        sess = requests.Session()
        resp = sess.get(self.url, headers=self.get_headers(), timeout=12, verify=False)
        ms   = int((time.monotonic() - t0) * 1000)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.content.decode("utf-8", errors="replace"), "lxml")

        el = soup.find("inka-conversor-home")
        if el:
            buy  = self._parse_rate(el.get(":buy-price",  ""))
            sell = self._parse_rate(el.get(":sale-price", ""))
            if buy and sell:
                return RateResult(slug=self.slug, buy_rate=buy, sell_rate=sell,
                                  scraped_at=datetime.utcnow(), response_ms=ms)

        # Fallback: regex sobre atributos
        m_buy  = re.search(r':buy-price=["\']([0-9.]+)["\']',  resp.text)
        m_sell = re.search(r':sale-price=["\']([0-9.]+)["\']', resp.text)
        if m_buy and m_sell:
            return RateResult(slug=self.slug,
                              buy_rate=self._parse_rate(m_buy.group(1)),
                              sell_rate=self._parse_rate(m_sell.group(1)),
                              scraped_at=datetime.utcnow(), response_ms=ms)

        raise ValueError("InkaMoney: no se encontró inka-conversor-home con :buy-price/:sale-price")
