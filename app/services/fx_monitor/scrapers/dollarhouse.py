"""
Scraper para Dollar House — dollarhouse.pe
Las tasas reales están en https://app.dollarhouse.pe/calculadorav2
(iframe embebido en la homepage)
Campos: <input name="purchaseprice"> = compra, <input name="op_saleprice"> = venta
(verificado con inspección real del HTML, 2026-03)
"""
import time
import requests
from bs4 import BeautifulSoup
from app.utils.formatters import now_peru
from .base import BaseScraper, RateResult

_CALC_URL = "https://app.dollarhouse.pe/calculadorav2"


class DollarHouseScraper(BaseScraper):
    slug = "dollarhouse"
    url  = "https://dollarhouse.pe"

    def fetch(self) -> RateResult:
        t0   = time.monotonic()
        sess = requests.Session()
        # Primera request a la homepage para obtener connect.sid (sesión Express)
        try:
            sess.get(self.url, headers=self.get_headers(), timeout=8, verify=False)
        except Exception:
            pass  # Si falla la homepage igual intentamos con la calculadora
        resp = sess.get(
            _CALC_URL,
            headers={**self.get_headers(), "Referer": "https://dollarhouse.pe/"},
            timeout=12,
            verify=False,
        )
        ms   = int((time.monotonic() - t0) * 1000)
        resp.raise_for_status()

        soup    = BeautifulSoup(resp.text, "lxml")
        buy_el  = soup.find("input", attrs={"name": "purchaseprice"})
        sell_el = soup.find("input", attrs={"name": "op_saleprice"})

        if not buy_el or not sell_el:
            raise ValueError("DollarHouse: no se encontraron inputs purchaseprice/op_saleprice")

        buy  = self._parse_rate(buy_el.get("value", ""))
        sell = self._parse_rate(sell_el.get("value", ""))

        return RateResult(slug=self.slug, buy_rate=buy, sell_rate=sell,
                          scraped_at=now_peru(), response_ms=ms)
