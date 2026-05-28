"""
Scraper para MetaFX Peru — metafxperu.com
Utiliza la API JSON oficial del sitio: GET /obtener_tasas.php
  {"ok": true, "data": [
    {"tipo": "bid", "valor_fijo": "3.415", "modo_fijo": 1, ...},
    {"tipo": "ask", "valor_fijo": "3.427", "modo_fijo": 1, ...}
  ]}

bid  = compra  (precio al que MetaFX compra USD del cliente)
ask  = venta   (precio al que MetaFX vende USD al cliente)

modo_fijo == 1 → usar valor_fijo (precio exacto publicado)
modo_fijo == 0 → usar (valor_min + valor_max) / 2 (rango flotante)
"""
import time
import requests
from app.utils.formatters import now_peru
from .base import BaseScraper, RateResult

_API_URL = "https://metafxperu.com/obtener_tasas.php"

# Cache de último resultado exitoso — se devuelve cuando la API retorna 429
_cache: dict = {"buy": None, "sell": None, "ts": 0}


class MetaFXPeruScraper(BaseScraper):
    slug = "metafxperu"
    url  = "https://metafxperu.com"

    def fetch(self) -> RateResult:
        t0   = time.monotonic()
        sess = requests.Session()
        try:
            resp = sess.get(
                _API_URL,
                headers={
                    **self.get_json_headers(),
                    "Referer": "https://metafxperu.com/",
                    "Origin":  "https://metafxperu.com",
                },
                timeout=10,
                verify=False,
            )
            resp.raise_for_status()
        except requests.HTTPError as e:
            ms = int((time.monotonic() - t0) * 1000)
            if e.response is not None and e.response.status_code == 429 and _cache["buy"]:
                # Rate-limited — devolver último precio válido en cache
                return RateResult(
                    slug=self.slug,
                    buy_rate=_cache["buy"],
                    sell_rate=_cache["sell"],
                    scraped_at=now_peru(),
                    response_ms=ms,
                    success=True,
                )
            raise
        ms = int((time.monotonic() - t0) * 1000)
        resp.raise_for_status()  # re-raise si hubo otro error HTTP

        payload = resp.json()
        if not payload.get("ok"):
            raise ValueError("MetaFX Peru: API retornó ok=false")

        buy = sell = None
        for item in payload.get("data", []):
            tipo = item.get("tipo", "").lower()
            if item.get("modo_fijo") == 1:
                price = self._parse_rate(item.get("valor_fijo", 0))
            else:
                vmin = self._parse_rate(item.get("valor_min", 0))
                vmax = self._parse_rate(item.get("valor_max", 0))
                price = round((vmin + vmax) / 2, 4)

            if tipo == "bid":
                buy = price
            elif tipo == "ask":
                sell = price

        if not buy or not sell:
            raise ValueError(f"MetaFX Peru: tasas incompletas buy={buy} sell={sell}")

        # Actualizar cache con precios frescos
        _cache["buy"] = buy
        _cache["sell"] = sell
        _cache["ts"] = time.time()

        return RateResult(
            slug=self.slug,
            buy_rate=buy,
            sell_rate=sell,
            scraped_at=now_peru(),
            response_ms=ms,
        )
