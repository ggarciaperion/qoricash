"""
Scraper para Cambix — cambix.pe

Cambix es una SPA Angular cuya API Azure (apibcprod01.azure-api.net/cambix/)
requiere autenticación JWT. CED tiene data de Cambix con 908d de antigüedad (2026-06).

Estrategia multi-capa:
  1. API pública en app.cambix.pe (subdominio de app, patrón común en fintechs)
  2. Endpoints Azure sin auth (podrían existir rutas públicas)
  3. Buscar en el bundle JS principal el endpoint real + tasas embebidas
  4. Buscar tasas en HTML del home (Angular puede pre-renderizar via SSR/TransferState)

Si todo falla: raise ConnectionError descriptivo.
"""
import re
import time
import requests
from app.utils.formatters import now_peru
from .base import BaseScraper, RateResult

_SITE_URL = "https://cambix.pe"
_APP_URL   = "https://app.cambix.pe"
_API_BASE  = "https://apibcprod01.azure-api.net/cambix/"

# Endpoints a probar en orden: app subdomain, Azure public paths, site root
_API_CANDIDATES = [
    (_APP_URL,   "/api/tipo-cambio"),
    (_APP_URL,   "/api/rates"),
    (_APP_URL,   "/api/exchange-rate"),
    (_APP_URL,   "/api/v1/rates"),
    (_SITE_URL,  "/api/tipo-cambio"),
    (_SITE_URL,  "/api/rates"),
]

_AZURE_PUBLIC_PATHS = [
    "public/rates",
    "public/tipo-cambio",
    "v1/public/rates",
    "v2/public/rates",
]

_RATE_MIN = 2.5
_RATE_MAX = 6.0


class CambixScraper(BaseScraper):
    slug = "cambix"
    url  = _SITE_URL

    def fetch(self) -> RateResult:
        t0 = time.monotonic()
        sess = requests.Session()

        headers_json = {
            **self.get_json_headers(),
            "Origin":  _SITE_URL,
            "Referer": _SITE_URL + "/",
        }

        # 1. Subdomain + sitio: endpoints API directos
        for base, path in _API_CANDIDATES:
            try:
                r = sess.get(base + path, headers=headers_json, timeout=6, verify=False)
                if r.status_code == 200:
                    buy, sell = self._pick_json(r.json())
                    if self._valid(buy, sell):
                        ms = int((time.monotonic() - t0) * 1000)
                        return RateResult(slug=self.slug, buy_rate=buy, sell_rate=sell,
                                          scraped_at=now_peru(), response_ms=ms)
            except Exception:
                continue

        # 2. Azure: solo rutas que podrían ser públicas (sin auth)
        for path in _AZURE_PUBLIC_PATHS:
            try:
                r = sess.get(_API_BASE + path, headers=headers_json, timeout=6, verify=False)
                if r.status_code == 200:
                    buy, sell = self._pick_json(r.json())
                    if self._valid(buy, sell):
                        ms = int((time.monotonic() - t0) * 1000)
                        return RateResult(slug=self.slug, buy_rate=buy, sell_rate=sell,
                                          scraped_at=now_peru(), response_ms=ms)
            except Exception:
                continue

        # 3. Buscar en el JS del bundle principal (Angular TransferState / env embebido)
        try:
            buy, sell = self._scan_js_bundle(sess, t0)
            if self._valid(buy, sell):
                ms = int((time.monotonic() - t0) * 1000)
                return RateResult(slug=self.slug, buy_rate=buy, sell_rate=sell,
                                  scraped_at=now_peru(), response_ms=ms)
        except Exception:
            pass

        raise ConnectionError(
            "Cambix: API Azure requiere JWT y no se encontraron endpoints públicos. "
            "CED tiene 908d de stale. Requiere investigación manual del bundle Angular."
        )

    def _pick_json(self, data):
        _KEYS_BUY  = ("compra", "buy", "buyRate", "tipoCambioCompra", "tc_compra", "purchase")
        _KEYS_SELL = ("venta",  "sell", "sellRate", "tipoCambioVenta",  "tc_venta",  "sale")
        if isinstance(data, list) and data:
            data = data[0]
        if isinstance(data, dict):
            buy  = self._safe_parse(data, _KEYS_BUY)
            sell = self._safe_parse(data, _KEYS_SELL)
            return buy, sell
        return None, None

    def _safe_parse(self, obj, keys):
        for k in keys:
            if k in obj and obj[k]:
                try:
                    return self._parse_rate(obj[k])
                except Exception:
                    pass
        return None

    def _scan_js_bundle(self, sess, t0):
        """
        Descarga la homepage Angular, encuentra el main bundle JS,
        y busca tasas hardcodeadas o el endpoint real de la API.
        """
        resp = sess.get(_SITE_URL, headers=self.get_headers(), timeout=12, verify=False)

        # Buscar el script principal (main.*.js o runtime.*.js)
        bundle_urls = re.findall(
            r'src="((?:https?://[^"]*)?/(?:main|runtime|app)[^"]*\.js)"',
            resp.text
        )
        for bundle_path in bundle_urls[:3]:
            try:
                url = bundle_path if bundle_path.startswith("http") else _SITE_URL + bundle_path
                js  = sess.get(url, headers=self.get_headers(), timeout=15, verify=False)
                text = js.text

                # Buscar tasas numéricas en rango PEN/USD dentro del bundle
                buy_m  = re.search(
                    r'"(?:compra|buy|tipoCambioCompra)"\s*:\s*"?(3\.[2-9]\d{3})"?', text)
                sell_m = re.search(
                    r'"(?:venta|sell|tipoCambioVenta)"\s*:\s*"?(3\.[2-9]\d{3})"?', text)
                if buy_m and sell_m:
                    buy  = self._parse_rate(buy_m.group(1))
                    sell = self._parse_rate(sell_m.group(1))
                    if self._valid(buy, sell):
                        return buy, sell
            except Exception:
                continue

        return None, None

    def _valid(self, buy, sell):
        return (buy and sell
                and _RATE_MIN < buy < _RATE_MAX
                and _RATE_MIN < sell < _RATE_MAX
                and buy < sell)
