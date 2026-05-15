"""
Scraper para JetPerú — jetperu.com.pe
Autenticación en 2 pasos:
  1. POST wp-admin/admin-ajax.php?action=tc_token → JWT
  2. GET  apitc.jetperu.com.pe:5002/api/WebTipoCambio?monedaOrigenId=PEN
        con Authorization: Bearer <token>
        → filtrar monedaDestinoId == 'USDO' para USD online
(verificado con inspección real del JS + API, 2026-03)
"""
import time
import requests
from app.utils.formatters import now_peru
from .base import BaseScraper, RateResult

_TOKEN_URL = "https://jetperu.com.pe/wp-admin/admin-ajax.php"
_RATES_URL = "https://apitc.jetperu.com.pe:5002/api/WebTipoCambio"


class JetperuScraper(BaseScraper):
    slug = "jetperu"
    url  = "https://www.jetperu.com.pe"

    def fetch(self) -> RateResult:
        t0 = time.monotonic()

        # Paso 1: Obtener JWT
        r_token = requests.post(
            _TOKEN_URL,
            data={"action": "tc_token"},
            headers={
                **self.get_headers(),
                "Referer": "https://www.jetperu.com.pe/",
                "X-Requested-With": "XMLHttpRequest",
            },
            timeout=10,
            verify=False,
        )
        r_token.raise_for_status()
        token_data = r_token.json()
        token = token_data.get("data") or ""
        if not token:
            raise ValueError("JetPerú: no se obtuvo token JWT")

        # Paso 2: Llamar a la API con el token
        r_rates = requests.get(
            _RATES_URL,
            params={"monedaOrigenId": "PEN"},
            headers={
                **self.get_json_headers(),
                "Authorization": f"Bearer {token}",
                "Origin": "https://www.jetperu.com.pe",
            },
            timeout=10,
            verify=False,
        )
        ms = int((time.monotonic() - t0) * 1000)
        r_rates.raise_for_status()

        data = r_rates.json()
        # Estructura: {"exito":true, "dato":[{"monedaDestinoId":"USDO","tipoCompra":3.457,"tipoVenta":3.461,...}]}
        for item in (data.get("dato") or []):
            if item.get("monedaDestinoId") == "USDO":
                buy  = self._parse_rate(item["tipoCompra"])
                sell = self._parse_rate(item["tipoVenta"])
                return RateResult(slug=self.slug, buy_rate=buy, sell_rate=sell,
                                  scraped_at=now_peru(), response_ms=ms)

        # Si no está USDO, intentar con USD genérico
        for item in (data.get("dato") or []):
            if item.get("monedaDestinoId") == "USD":
                buy  = self._parse_rate(item["tipoCompra"])
                sell = self._parse_rate(item["tipoVenta"])
                return RateResult(slug=self.slug, buy_rate=buy, sell_rate=sell,
                                  scraped_at=now_peru(), response_ms=ms)

        raise ValueError(f"JetPerú: no se encontró monedaDestinoId USD/USDO en {list(i.get('monedaDestinoId') for i in data.get('dato',[]))}")
