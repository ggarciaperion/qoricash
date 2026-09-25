"""
Scraper para Cambio Mundial — cambiomundial.com
SPA Angular protegida por Cloudflare.

Estado observado (2026-09-24 desde IP cloud de Render):
  GET /backend/tasaCambio/daily → HTTP 403, Content-Type text/html,
  página "Just a moment…" (desafío Cloudflare antibot).
  La petición directa sin warm-up también recibió 403; el warm-up previo
  no era la causa del problema.
  No se identificó en ese momento una alternativa pública accesible.

  Comportamiento actual: scrape_ok=False, last_attempt_at actualizado.
  Último precio almacenado conservado como referencia vencida y excluido
  del ranking activo mientras el scrape siga fallando.
  Si el endpoint vuelve a responder con JSON válido, se recupera normalmente.

Fuente CED: path="cambiomundial", updated_at=2026-08-24 (31d > 4h límite) → rechazada.
"""
import re
import time
import requests
from bs4 import BeautifulSoup
from app.utils.formatters import now_peru
from .base import BaseScraper, RateResult

_SITE_URL = "https://www.cambiomundial.com"

_API_CANDIDATES = [
    "/backend/tasaCambio/daily",   # confirmado: devuelve JSON en <500ms
    "/backend/tasaCambio/today",
    "/backend/tasaCambio",
    "/backend/api/tasaCambio/daily",
    "/api/tasaCambio/daily",
    "/api/tipo-cambio",
    "/api/exchange-rate",
]


class CambioMundialScraper(BaseScraper):
    slug = "cambiomundial"
    url  = _SITE_URL

    def fetch(self) -> RateResult:
        t0 = time.monotonic()

        headers_json = self.get_json_headers()
        headers_json.update({
            "Referer": _SITE_URL + "/",
            "Origin":  _SITE_URL,
        })

        sess = requests.Session()
        for path in _API_CANDIDATES:
            try:
                resp = sess.get(
                    _SITE_URL + path,
                    headers=headers_json,
                    timeout=8,
                    verify=False,
                )
                if resp.status_code == 403:
                    raise ConnectionError(
                        "CambioMundial: HTTP 403 — acceso bloqueado por Cloudflare antibot "
                        "desde IP cloud. Último precio conservado como referencia vencida."
                    )
                if resp.status_code != 200:
                    continue
                data = resp.json()
                buy, sell = self._extract_from_json(data)
                if buy and sell and buy < sell:
                    ms = int((time.monotonic() - t0) * 1000)
                    return RateResult(slug=self.slug, buy_rate=buy, sell_rate=sell,
                                      scraped_at=now_peru(), response_ms=ms)
            except ConnectionError:
                raise
            except Exception:
                continue

        # Fallback: buscar tasas en el HTML (script tags / JSON embebido)
        try:
            resp = sess.get(_SITE_URL, headers=self.get_headers(), timeout=12, verify=False)
            if resp.status_code == 403:
                raise ConnectionError(
                    "CambioMundial: HTTP 403 — acceso bloqueado por Cloudflare antibot "
                    "desde IP cloud. Último precio conservado como referencia vencida."
                )
            ms   = int((time.monotonic() - t0) * 1000)
            soup = BeautifulSoup(resp.text, "lxml")
            for script in soup.find_all("script"):
                text = script.string or ""
                buy, sell = self._extract_from_script(text)
                if buy and sell and buy < sell:
                    return RateResult(slug=self.slug, buy_rate=buy, sell_rate=sell,
                                      scraped_at=now_peru(), response_ms=ms)
        except ConnectionError:
            raise
        except Exception:
            pass

        raise ConnectionError(
            "CambioMundial: todos los endpoints fallaron. "
            "Sin alternativa pública accesible desde IP cloud."
        )

    def _extract_from_json(self, data):
        """Extrae (buy, sell) de los formatos JSON conocidos de CambioMundial."""
        try:
            if isinstance(data, list) and data:
                entry = next(
                    (r for r in data if str(r.get("tipoTasa", "")).upper() == "REGULAR"),
                    data[0]
                )
                buy  = self._safe_parse(entry, ("buy", "compra", "buyRate", "tipoCambioCompra"))
                sell = self._safe_parse(entry, ("sell", "venta",  "sellRate", "tipoCambioVenta"))
                return buy, sell
            if isinstance(data, dict):
                buy  = self._safe_parse(data, ("buy", "compra", "buyRate", "tipoCambioCompra"))
                sell = self._safe_parse(data, ("sell", "venta",  "sellRate", "tipoCambioVenta"))
                return buy, sell
        except Exception:
            pass
        return None, None

    def _safe_parse(self, obj, keys):
        for k in keys:
            if k in obj and obj[k]:
                try:
                    return self._parse_rate(obj[k])
                except Exception:
                    pass
        return None

    def _extract_from_script(self, text):
        """Busca patrones buy/sell o compra/venta en texto de script."""
        buy_m  = re.search(
            r'"(?:buy|compra|buyRate|tipoCambioCompra)"\s*:\s*"?([\d.]+)"?', text)
        sell_m = re.search(
            r'"(?:sell|venta|sellRate|tipoCambioVenta)"\s*:\s*"?([\d.]+)"?', text)
        try:
            if buy_m and sell_m:
                return self._parse_rate(buy_m.group(1)), self._parse_rate(sell_m.group(1))
        except Exception:
            pass
        return None, None
