"""
Scraper para Okane Cambio Digital — okanecambiodigital.com

Error de dominio resuelto (2026-09-24):
  okane.pe         → sistema POS de restaurante (Angular, sin funcionalidad FX)
  okanecambiodigital.com → casa de cambio FX real (misma marca, dominio diferente)

Endpoint confirmado (público, sin auth):
  GET https://okanecambiodigital.com/backend_apigateway/v1/tipoDeCambio
  Respuesta: [{"idTipoCambio":"064427","fecha":"2026-09-24T18:04:35",
               "idMoneda":"USD","valorCompra":3.3700,"valorVenta":3.4500,
               "tipoModalidad":"01"}]
  - valorCompra → buy_rate   (Okane compra USD del cliente)
  - valorVenta  → sell_rate  (Okane vende USD al cliente)
  - fecha       → source_updated_at (último cambio de tasa en formato ISO local sin tz)
  - Filtrar por idMoneda="USD" si la respuesta incluye múltiples monedas.

URL del monitor actualizada de okane.pe a okanecambiodigital.com.
El monitor CED ("okane") también apuntaba al sitio erróneo; el path en CED
corresponde al negocio, no al dominio actual.
"""
import time
import requests
from datetime import datetime, timezone, timedelta
from app.utils.formatters import now_peru
from .base import BaseScraper, RateResult

_API_URL  = "https://okanecambiodigital.com/backend_apigateway/v1/tipoDeCambio"
_SITE_URL = "https://okanecambiodigital.com"
_RATE_MIN = 2.5
_RATE_MAX  = 6.0
# Okane está en Lima (UTC-5); la API devuelve fechas locales sin tz
_LIMA_TZ   = timezone(timedelta(hours=-5))


class OkaneScraper(BaseScraper):
    slug = "okane"
    url  = _SITE_URL

    def fetch(self) -> RateResult:
        t0 = time.monotonic()

        headers = self.get_json_headers()
        headers["Referer"] = _SITE_URL + "/"
        headers["Origin"]  = _SITE_URL

        sess = requests.Session()
        resp = sess.get(_API_URL, headers=headers, timeout=12, verify=False)
        resp.raise_for_status()

        data = resp.json()
        # Respuesta es lista; filtrar por USD si hay múltiples monedas
        if isinstance(data, list):
            entry = next(
                (r for r in data if str(r.get("idMoneda", "")).upper() == "USD"),
                data[0] if data else None,
            )
        elif isinstance(data, dict):
            entry = data
        else:
            raise ValueError(f"Okane: formato de respuesta inesperado: {type(data)}")

        if not entry:
            raise ValueError("Okane: respuesta vacía")

        buy  = float(entry["valorCompra"])
        sell = float(entry["valorVenta"])

        if not (_RATE_MIN < buy < _RATE_MAX and _RATE_MIN < sell < _RATE_MAX):
            raise ValueError(
                f"Okane: tasas fuera de rango buy={buy} sell={sell} "
                f"(esperado {_RATE_MIN}–{_RATE_MAX})"
            )
        if buy >= sell:
            raise ValueError(
                f"Okane: buy ({buy}) >= sell ({sell}) — dato inválido"
            )

        # source_updated_at: la API devuelve datetime local Lima sin offset.
        # Se trata como UTC-5 (Lima) y se convierte a UTC aware.
        src_updated_at = None
        fecha_str = entry.get("fecha")
        if fecha_str:
            try:
                dt_local = datetime.fromisoformat(fecha_str)
                if dt_local.tzinfo is None:
                    dt_local = dt_local.replace(tzinfo=_LIMA_TZ)
                src_updated_at = dt_local.astimezone(timezone.utc)
            except Exception:
                pass   # no invertir una fecha si el formato cambia

        ms = int((time.monotonic() - t0) * 1000)
        return RateResult(
            slug=self.slug,
            buy_rate=buy,
            sell_rate=sell,
            scraped_at=now_peru(),
            response_ms=ms,
            source="direct",
            source_updated_at=src_updated_at,
        )
