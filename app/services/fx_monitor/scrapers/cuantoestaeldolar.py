"""
Scraper base para empresas cuyas webs son SPAs no scrapeables.
Fuente: cuantoestaeldolar.pe — agrega tasas en tiempo real de +30 casas de cambio
peruanas. Los datos viven en el payload __next_f (Next.js App Router).

Uso: subclasear CedBaseScraper y definir `ced_path` con el slug de la empresa
en cuantoestaeldolar.pe (atributo "path" en el JSON).

Optimización: caché compartida de 60s — todos los CedBaseScraper del mismo ciclo
comparten una sola descarga de CED en lugar de hacer N requests paralelas.
"""
import re
import time
import threading
import requests
from app.utils.formatters import now_peru
from .base import BaseScraper, RateResult

_CED_URL = "https://cuantoestaeldolar.pe"

# Rango válido para tasas PEN/USD (margen amplio para absorber variaciones)
_RATE_MIN = 2.5
_RATE_MAX = 6.0

# ── Caché en proceso para la página CED ──────────────────────────────────────
# Evita que los N scrapers CED hagan N requests paralelas al mismo sitio.
# TTL: 60s — suficiente para un ciclo de scraping (~5-10s de ejecución).
_ced_cache_lock = threading.Lock()
_ced_cache: dict = {"text": "", "ts": 0.0}
_CED_CACHE_TTL  = 60.0  # segundos


def _build_ced_text(raw_html: str) -> str:
    """Extrae y decodifica los fragmentos __next_f del HTML de cuantoestaeldolar.pe."""
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.+?)"\]\)', raw_html, re.DOTALL)
    text = ""
    for chunk in chunks:
        try:
            text += chunk.encode().decode("unicode_escape")
        except Exception:
            text += chunk
    return text


def _get_ced_text(session, headers, timeout: int = 15) -> str:
    """
    Descarga cuantoestaeldolar.pe y retorna el texto decodificado.
    Usa caché interna de 60s para no descargar la misma página N veces en paralelo.
    """
    now = time.monotonic()
    with _ced_cache_lock:
        if _ced_cache["text"] and (now - _ced_cache["ts"]) < _CED_CACHE_TTL:
            return _ced_cache["text"]

    # Descarga fuera del lock para no bloquear otros threads
    resp = session.get(_CED_URL, headers=headers, timeout=timeout, verify=False)
    resp.raise_for_status()
    text = _build_ced_text(resp.text)

    with _ced_cache_lock:
        _ced_cache["text"] = text
        _ced_cache["ts"]   = time.monotonic()

    return text


# Umbral máximo de antigüedad de datos CED.
# Si CED no ha actualizado el dato en más de este tiempo, se rechaza.
# Evidencia (2026-06-25): dollarhouse/cambiosol/westernunion ≈ 87 min.
# TKambio = 14d, CambiaFX = 21d, Okane = 174d, Cambix = 908d → todos rechazados.
_CED_MAX_STALE_HOURS = 4.0


def _extract_rates_from_text(text: str, ced_path: str) -> tuple:
    """
    Extrae (buy, sell) para `ced_path` desde el texto ya decodificado de CED.
    Retorna (buy_float, sell_float) o lanza ValueError.
    Valida que updated_at de CED no supere _CED_MAX_STALE_HOURS.
    """
    from datetime import datetime, timezone

    # Búsqueda exacta primero, luego fallback sin comillas (encoding alternativo)
    idx = text.find(f'"path":"{ced_path}"')
    if idx < 0:
        idx = text.find(ced_path)
    if idx < 0:
        raise ValueError(f"CED: path '{ced_path}' no encontrado en el payload")

    # Ventana de 1500 chars — más robusta ante estructuras JSON con campos adicionales
    window = text[idx: idx + 1500]

    # ── Validar antigüedad del dato CED ──────────────────────────────────────
    upd_m = re.search(r'"updated_at"\s*:\s*"([^"]+)"', window)
    if upd_m:
        try:
            upd_str = upd_m.group(1)
            upd_dt  = datetime.fromisoformat(upd_str.replace("Z", "+00:00"))
            now_utc = datetime.now(timezone.utc)
            stale_h = (now_utc - upd_dt).total_seconds() / 3600
            if stale_h > _CED_MAX_STALE_HOURS:
                raise ValueError(
                    f"CED: datos de '{ced_path}' tienen {stale_h:.1f}h de antigüedad "
                    f"(updated_at={upd_str}) — excede límite de {_CED_MAX_STALE_HOURS}h. "
                    f"CED dejó de actualizar este competidor."
                )
        except ValueError:
            raise
        except Exception:
            pass  # Si no se puede parsear el timestamp, no bloqueamos

    buy_m  = re.search(r'"buy"\s*:\s*\{[^}]*"cost"\s*:\s*"([\d.]+)"',  window)
    sell_m = re.search(r'"sale"\s*:\s*\{[^}]*"cost"\s*:\s*"([\d.]+)"', window)

    if not buy_m or not sell_m:
        # Fallback: patrones alternativos de estructura
        buy_m  = buy_m  or re.search(r'"buy_rate"\s*:\s*"?([\d.]+)"?',  window)
        sell_m = sell_m or re.search(r'"sell_rate"\s*:\s*"?([\d.]+)"?', window)

    if not buy_m or not sell_m:
        raise ValueError(f"CED: tasas no encontradas en el bloque de '{ced_path}' "
                         f"(window={window[:120]!r})")

    buy  = float(buy_m.group(1))
    sell = float(sell_m.group(1))

    if not (_RATE_MIN < buy < _RATE_MAX) or not (_RATE_MIN < sell < _RATE_MAX):
        raise ValueError(f"CED: tasas fuera de rango para '{ced_path}' buy={buy} sell={sell} "
                         f"(esperado {_RATE_MIN}–{_RATE_MAX})")
    if buy >= sell:
        raise ValueError(f"CED: buy ({buy}) >= sell ({sell}) para '{ced_path}' — dato inválido")

    return buy, sell


def _fetch_ced_rates(session, headers, ced_path: str, timeout: int = 15):
    """
    API de compatibilidad — descarga CED (con caché) y extrae tasas para `ced_path`.
    Retorna (buy_float, sell_float) o lanza ValueError.
    """
    text = _get_ced_text(session, headers, timeout=timeout)
    return _extract_rates_from_text(text, ced_path)


class CedBaseScraper(BaseScraper):
    """
    Scraper genérico que obtiene tasas desde cuantoestaeldolar.pe.
    Subclases deben definir: slug, url, ced_path.
    """
    ced_path: str = ""

    def fetch(self) -> RateResult:
        t0   = time.monotonic()
        sess = requests.Session()
        buy, sell = _fetch_ced_rates(sess, self.get_headers(), self.ced_path)
        ms   = int((time.monotonic() - t0) * 1000)
        return RateResult(slug=self.slug, buy_rate=buy, sell_rate=sell,
                          scraped_at=now_peru(), response_ms=ms)
