"""
Scraper para TKambio — tkambio.com

TKambio es un WordPress con enrutamiento SPA wildcard; no expone API REST pública.
Endpoint real: POST /wp-admin/admin-ajax.php con action=get_exchange_rate
Respuesta: {"buying_rate":3.4,"selling_rate":3.428,"text_updated_at":"2 horas","outdates_in":600,...}

Nota: text_updated_at es una cadena legible ("2 horas"), no un timestamp ISO.
source_updated_at no se puede poblar desde esta fuente.
"""
import time
import requests
from app.utils.formatters import now_peru
from .base import BaseScraper, RateResult

_AJAX_URL = "https://tkambio.com/wp-admin/admin-ajax.php"
_RATE_MIN  = 2.5
_RATE_MAX  = 6.0


class TKambioScraper(BaseScraper):
    slug = "tkambio"
    url  = "https://tkambio.com"

    def fetch(self) -> RateResult:
        t0 = time.monotonic()

        headers = self.get_headers()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        headers["Referer"]      = "https://tkambio.com/"
        headers["Origin"]       = "https://tkambio.com"

        sess = requests.Session()
        resp = sess.post(
            _AJAX_URL,
            data="action=get_exchange_rate",
            headers=headers,
            timeout=12,
            verify=False,
        )
        resp.raise_for_status()

        data = resp.json()
        buy  = float(data["buying_rate"])
        sell = float(data["selling_rate"])

        if not (_RATE_MIN < buy < _RATE_MAX and _RATE_MIN < sell < _RATE_MAX):
            raise ValueError(
                f"TKambio: tasas fuera de rango buy={buy} sell={sell} "
                f"(esperado {_RATE_MIN}–{_RATE_MAX})"
            )
        if buy >= sell:
            raise ValueError(
                f"TKambio: buy ({buy}) >= sell ({sell}) — dato inválido"
            )

        ms = int((time.monotonic() - t0) * 1000)
        return RateResult(
            slug=self.slug,
            buy_rate=buy,
            sell_rate=sell,
            scraped_at=now_peru(),
            response_ms=ms,
            source="direct",
        )
