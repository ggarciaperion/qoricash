"""
Scraper para Instakash — instakash.net
Intenta varios endpoints API conocidos, luego HTML.
Nota: su SSL (TLS 1.3) es incompatible con LibreSSL de macOS pero funciona en
producción (Linux / OpenSSL).
"""
import re
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from .base import BaseScraper, RateResult

# Endpoints conocidos para intentar en orden
_API_CANDIDATES = [
    "https://instakash.net/api/exchange-rates",
    "https://instakash.net/api/rates",
    "https://api.instakash.net/rates",
    "https://instakash.net/api/tc",
]

# Claves JSON que pueden contener la compra/venta
_BUY_KEYS  = ("buy", "compra", "purchase", "buy_rate",  "tipo_compra")
_SELL_KEYS = ("sell", "venta", "sale",     "sell_rate", "tipo_venta")


class InstakashScraper(BaseScraper):
    slug = "instakash"
    url  = "https://instakash.net"

    def fetch(self) -> RateResult:
        t0 = time.monotonic()

        # 1. Intentar endpoints JSON
        for api_url in _API_CANDIDATES:
            try:
                resp = requests.get(api_url, headers=self.get_json_headers(), timeout=8, verify=False)
                if resp.status_code == 200:
                    data = resp.json()
                    buy  = self._pick(data, _BUY_KEYS)
                    sell = self._pick(data, _SELL_KEYS)
                    if buy and sell:
                        ms = int((time.monotonic() - t0) * 1000)
                        return RateResult(slug=self.slug, buy_rate=buy, sell_rate=sell,
                                          scraped_at=datetime.utcnow(), response_ms=ms)
            except Exception:
                continue

        # 2. Fallback: scraping HTML
        resp = requests.get(self.url, headers=self.get_headers(), timeout=14, verify=False)
        ms   = int((time.monotonic() - t0) * 1000)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        buy  = self._find_by_label(soup, ["compra", "buy"])
        sell = self._find_by_label(soup, ["venta", "sell"])

        if not buy or not sell:
            # Último recurso: extraer primeros dos números PEN/USD del DOM
            nums = self._extract_rate_numbers(soup)
            buy  = nums[0] if len(nums) > 0 else 0.0
            sell = nums[1] if len(nums) > 1 else 0.0

        return RateResult(slug=self.slug, buy_rate=buy, sell_rate=sell,
                          scraped_at=datetime.utcnow(), response_ms=ms)

    # ── helpers ──────────────────────────────────────────────────────────
    def _pick(self, data, keys):
        if isinstance(data, dict):
            for k in keys:
                if k in data and data[k]:
                    try: return self._parse_rate(data[k])
                    except Exception: pass
            # Buscar en objetos anidados (hasta 1 nivel)
            for v in data.values():
                if isinstance(v, dict):
                    result = self._pick(v, keys)
                    if result: return result
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    result = self._pick(v[0], keys)
                    if result: return result
        return None

    def _find_by_label(self, soup, keywords):
        for kw in keywords:
            el = (soup.find(id=re.compile(kw, re.I)) or
                  soup.find(class_=lambda c: c and kw in " ".join(c).lower()) or
                  soup.find(attrs={"data-type": re.compile(kw, re.I)}))
            if el:
                try: return self._parse_rate(el.get_text(strip=True))
                except Exception: pass
        return None

    def _extract_rate_numbers(self, soup):
        rates = []
        for el in soup.find_all(["span", "strong", "b", "div", "p"]):
            if el.find(): continue  # solo hojas
            txt = el.get_text(strip=True)
            try:
                v = self._parse_rate(txt)
                if 3.0 < v < 5.0:
                    rates.append(v)
            except Exception:
                continue
        return sorted(set(rates))
