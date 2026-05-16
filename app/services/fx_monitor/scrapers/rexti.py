"""
Scraper para Rextie — www.rextie.com
La página es Astro — los tipos de cambio se cargan vía GraphQL desde app.rextie.com.
Endpoint: POST https://app.rextie.com/api/graphql/
Query: currentFxRates(sources: [REXTIE]) { source ask bid }
  bid = compra (lo que pagan por USD), ask = venta (lo que cobran por USD)
(verificado 2026-05)
"""
import time
import requests
from app.utils.formatters import now_peru
from .base import BaseScraper, RateResult

_GQL_URL = "https://app.rextie.com/api/graphql/"
_GQL_QUERY = """
query GetFxRates($sources: [FXRateSource!]!) {
    currentFxRates(sources: $sources) { source ask bid }
}
"""


class RextiScraper(BaseScraper):
    slug = "rextie"
    url  = "https://www.rextie.com"

    def fetch(self) -> RateResult:
        t0 = time.monotonic()

        headers = self.get_json_headers()
        headers.update({
            "Content-Type":        "application/json",
            "rextie-country":      "pe",
            "rextie-language":     "es",
            "rextie-app-platform": "rextie-web",
            "rextie-app-version":  "6.0.20",
        })

        resp = requests.post(
            _GQL_URL,
            headers=headers,
            json={"query": _GQL_QUERY, "variables": {"sources": ["REXTIE"]}},
            timeout=12,
            verify=False,
        )
        ms = int((time.monotonic() - t0) * 1000)
        resp.raise_for_status()

        data = resp.json()
        rates = data.get("data", {}).get("currentFxRates", [])
        for entry in rates:
            if entry.get("source") == "REXTIE":
                buy  = self._parse_rate(entry["bid"])   # bid = compra
                sell = self._parse_rate(entry["ask"])   # ask = venta
                return RateResult(slug=self.slug, buy_rate=buy, sell_rate=sell,
                                  scraped_at=now_peru(), response_ms=ms)

        raise ValueError("Rextie: no se encontró source REXTIE en la respuesta GraphQL")
