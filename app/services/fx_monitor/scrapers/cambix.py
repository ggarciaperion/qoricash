"""
Scraper para Cambix — cambix.pe
Cambix usa Angular con Azure API Management (apibcprod01.azure-api.net/cambix/).
La API requiere autenticación JWT — las tasas no están disponibles públicamente
sin credenciales. El scraper intenta obtenerlas y falla de forma controlada si no
puede acceder.
Estado 2026-03: Requiere investigación adicional del flujo de autenticación.
"""
import time
import requests
from app.utils.formatters import now_peru
from .base import BaseScraper, RateResult

_API_BASE = "https://apibcprod01.azure-api.net/cambix/"
_SITE_URL = "https://cambix.pe"


class CambixScraper(BaseScraper):
    slug = "cambix"
    url  = _SITE_URL

    def fetch(self) -> RateResult:
        t0 = time.monotonic()

        # Intentar endpoints públicos conocidos de la API Azure
        api_headers = {
            **self.get_json_headers(),
            "Origin":  _SITE_URL,
            "Referer": _SITE_URL + "/",
        }
        for version in ("v1", "v2", "v3"):
            for path in ("tipo-cambio", "tipoCambio", "exchange-rate", "rates", "public/rates"):
                try:
                    r = requests.get(
                        f"{_API_BASE}{version}/{path}",
                        headers=api_headers,
                        timeout=6,
                        verify=False,
                    )
                    if r.status_code == 200:
                        try:
                            data = r.json()
                        except Exception:
                            continue
                        buy  = self._pick(data, ("compra", "buy", "buyRate", "tipoCambioCompra", "tc_compra"))
                        sell = self._pick(data, ("venta",  "sell", "sellRate", "tipoCambioVenta",  "tc_venta"))
                        if buy and sell:
                            ms = int((time.monotonic() - t0) * 1000)
                            return RateResult(slug=self.slug, buy_rate=buy, sell_rate=sell,
                                              scraped_at=now_peru(), response_ms=ms)
                except Exception:
                    continue

        # El fallback HTML fue eliminado: el site Angular no renderiza tasas en el HTML
        # estático, por lo que el regex capturaba números arbitrarios de la página
        # produciendo tasas incorrectas que contaminaban el ranking de mejor compra/venta.
        raise ConnectionError(
            "Cambix: API Azure requiere autenticación JWT. "
            "Las tasas no están disponibles públicamente sin credenciales."
        )

    def _pick(self, data, keys):
        if isinstance(data, dict):
            for k in keys:
                if k in data and data[k]:
                    try:
                        return self._parse_rate(data[k])
                    except Exception:
                        pass
        elif isinstance(data, list) and data:
            return self._pick(data[0], keys)
        return None
