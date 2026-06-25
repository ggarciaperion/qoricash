"""
Orquestador de todos los scrapers — ejecución paralela con ThreadPoolExecutor.
Circuit breaker por scraper: pausas automáticas ante fallas consecutivas.
"""
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from .kambista      import KambistaScraper
from .cambix        import CambixScraper
from .cambioseguro  import CambioSeguroScraper
from .tucambio      import TuCambioScraper
from .tucambista    import TuCambistaScraper
from .rexti         import RextiScraper
from .dollarhouse   import DollarHouseScraper
from .moneyhouse    import MoneyhouseScraper
from .jetperu       import JetperuScraper
from .inkamoney     import InkaMoneyPeru
from .dichikash     import DichikashScraper
from .westernunion  import WesternUnionScraper
from .cambiafx      import CambiaFXScraper
from .cambiomundial import CambioMundialScraper
from .tkambio       import TKambioScraper
from .cambiosol     import CambiosolScraper
from .okane         import OkaneScraper

logger = logging.getLogger(__name__)

# ── Circuit breaker ────────────────────────────────────────────────────────────
# Evita que scrapers fallidos consuman tiempo del ciclo indefinidamente.
# _cb[slug] = {"fails": int, "open_until": float}
_cb: dict = {}

def _cb_open(slug: str) -> bool:
    """True = scraper en cooldown, saltar este ciclo."""
    entry = _cb.get(slug)
    return bool(entry and entry["open_until"] > time.monotonic())

def _cb_record(slug: str, success: bool):
    """Actualizar estado del circuit breaker tras cada resultado."""
    if success:
        _cb.pop(slug, None)          # reset en éxito
        return
    entry = _cb.setdefault(slug, {"fails": 0, "open_until": 0.0})
    entry["fails"] += 1
    fails = entry["fails"]
    # Backoff progresivo: 5 fallas → 30s · 10 fallas → 2min · 20 fallas → 5min (máx)
    if   fails >= 20: cooldown = 300
    elif fails >= 10: cooldown = 120
    elif fails >= 5:  cooldown = 30
    else:             cooldown = 0
    if cooldown:
        entry["open_until"] = time.monotonic() + cooldown
        logger.warning(f"[CB] {slug}: {fails} fallas → cooldown {cooldown}s")


ALL_SCRAPERS = [
    KambistaScraper(),
    CambixScraper(),
    CambioSeguroScraper(),
    TuCambioScraper(),
    TuCambistaScraper(),
    RextiScraper(),
    DollarHouseScraper(),
    MoneyhouseScraper(),
    JetperuScraper(),
    InkaMoneyPeru(),
    DichikashScraper(),
    WesternUnionScraper(),
    CambiaFXScraper(),
    CambioMundialScraper(),
    TKambioScraper(),
    CambiosolScraper(),
    OkaneScraper(),
]


# Mapa de slug → ced_path en cuantoestaeldolar.pe
# Usado como fallback cuando el scraper directo falla (ej. Cloudflare en cloud IPs)
_CED_FALLBACK = {
    "cambix":      "cambix",
    "cambioseguro":"cambio-seguro",
    "tucambista":  "tu-cambista",
    "dollarhouse": "dollar-house",
    "moneyhouse":  "moneyhouse",
    "inkamoney":   "inkamoney",
    "dichikash":   "dichikash",
    "rextie":      "rextie",
    "kambista":    "kambista",
    "tkambio":     "tkambio",
    "cambiosol":   "cambiosol",
    "cambiafx":    "cambia-fx",
    # "cambiomundial": CED desactualizado desde 2026-05 — usa API directa ahora
    "westernunion":"western-union",
    "okane":       "okane",
}


def _ced_batch_fallback(failed_slugs: list) -> dict:
    """
    Descarga cuantoestaeldolar.pe UNA VEZ y extrae tasas para todos los slugs fallidos.
    Retorna dict slug → (buy, sell) para los que se encontraron.
    """
    from .cuantoestaeldolar import _fetch_ced_rates
    import re
    import requests

    slugs_with_path = {s: _CED_FALLBACK[s] for s in failed_slugs if s in _CED_FALLBACK}
    if not slugs_with_path:
        return {}

    # Descargar CED una sola vez para todos
    try:
        sess = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept":     "text/html,application/xhtml+xml,*/*;q=0.9",
            "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        }
        resp = sess.get("https://cuantoestaeldolar.pe", headers=headers, timeout=15, verify=False)
        resp.raise_for_status()

        chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.+?)"\]\)', resp.text, re.DOTALL)
        text = ""
        for chunk in chunks:
            try:
                text += chunk.encode().decode("unicode_escape")
            except Exception:
                text += chunk

        recovered = {}
        for slug, ced_path in slugs_with_path.items():
            try:
                idx = text.find(f'"path":"{ced_path}"')
                if idx < 0:
                    idx = text.find(ced_path)
                if idx < 0:
                    continue
                window = text[idx: idx + 600]

                # Validar antigüedad del dato antes de usar
                from datetime import datetime, timezone
                upd_m = re.search(r'"updated_at"\s*:\s*"([^"]+)"', window)
                if upd_m:
                    try:
                        upd_dt  = datetime.fromisoformat(upd_m.group(1).replace("Z", "+00:00"))
                        stale_h = (datetime.now(timezone.utc) - upd_dt).total_seconds() / 3600
                        if stale_h > 4.0:
                            logger.warning(f"[CED-BATCH] {slug}: dato CED tiene {stale_h:.1f}h — ignorando")
                            continue
                    except Exception:
                        pass

                buy_m  = re.search(r'"buy"\s*:\s*\{[^}]*"cost"\s*:\s*"([\d.]+)"',  window)
                sell_m = re.search(r'"sale"\s*:\s*\{[^}]*"cost"\s*:\s*"([\d.]+)"', window)
                if buy_m and sell_m:
                    buy  = float(buy_m.group(1))
                    sell = float(sell_m.group(1))
                    if buy > 0 and sell > 0:
                        recovered[slug] = (buy, sell)
            except Exception:
                continue

        logger.info(f"[CED-BATCH] Recuperados via CED: {list(recovered.keys())}")
        return recovered

    except Exception as e:
        logger.warning(f"[CED-BATCH] Error descargando cuantoestaeldolar.pe: {e}")
        return {}


_RATE_MIN = 2.5
_RATE_MAX = 6.0


def _is_valid_rate(buy: float, sell: float) -> bool:
    """Verifica que las tasas estén en rango razonable para PEN/USD."""
    return (_RATE_MIN < buy < _RATE_MAX and _RATE_MIN < sell < _RATE_MAX and buy < sell)


def scrape_all(active_slugs=None, max_workers=18):
    """
    Ejecuta todos los scrapers activos en paralelo con circuit breaker.
    Para scrapers que fallan o están en cooldown y tienen mapping en CED,
    intenta recuperar las tasas de cuantoestaeldolar.pe en una sola request.

    FIX: Los scrapers en cooldown (circuit breaker) también se intentan via CED
    para evitar que los precios queden congelados indefinidamente.
    """
    from .base import RateResult
    from app.utils.formatters import now_peru

    scrapers = ALL_SCRAPERS
    if active_slugs is not None:
        scrapers = [s for s in ALL_SCRAPERS if s.slug in active_slugs]

    # Separar scrapers activos de los que están en cooldown
    ready   = [s for s in scrapers if not _cb_open(s.slug)]
    skipped = [s.slug for s in scrapers if _cb_open(s.slug)]
    if skipped:
        logger.warning(f"[CB] {len(skipped)} scrapers en cooldown: {skipped} — se intentará CED fallback")

    results = []
    failed_slugs = []

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(s.safe_fetch): s.slug for s in ready}
        for future in as_completed(futures):
            slug = futures[future]
            try:
                result = future.result()
                # Validar rango antes de aceptar el resultado
                if result.success and result.buy_rate > 0:
                    if not _is_valid_rate(result.buy_rate, result.sell_rate):
                        logger.warning(
                            f"[FX] ⚠️  {slug}: tasas fuera de rango "
                            f"buy={result.buy_rate} sell={result.sell_rate} — descartando"
                        )
                        result = RateResult(slug=slug, buy_rate=0.0, sell_rate=0.0,
                                            scraped_at=result.scraped_at,
                                            response_ms=result.response_ms,
                                            success=False,
                                            error=f"Fuera de rango: {result.buy_rate}/{result.sell_rate}")
                _cb_record(slug, result.success)
                results.append(result)
                status = "✅" if result.success else "❌"
                logger.info(f"[FX] {status} {slug}: compra={result.buy_rate} venta={result.sell_rate} ({result.response_ms}ms)")
                if not result.success or result.buy_rate == 0:
                    failed_slugs.append(slug)
            except Exception as e:
                _cb_record(slug, False)
                logger.error(f"[FX] 💥 {slug}: {e}")
                failed_slugs.append(slug)

    # Fallback CED batch para scrapers que fallaron Y para los que estaban en cooldown.
    # FIX CRÍTICO: los scrapers en cooldown también se intentan via CED para evitar
    # que sus precios queden congelados cuando el scraper directo está parado.
    all_fallback_slugs = list(set(failed_slugs + skipped))
    if all_fallback_slugs:
        t0 = time.monotonic()
        recovered = _ced_batch_fallback(all_fallback_slugs)
        ms = int((time.monotonic() - t0) * 1000)
        for slug, (buy, sell) in recovered.items():
            if not _is_valid_rate(buy, sell):
                logger.warning(f"[CED-BATCH] ⚠️  {slug}: tasas CED fuera de rango {buy}/{sell} — ignorando")
                continue
            # Reemplazar el resultado fallido con el dato de CED
            results = [r for r in results if r.slug != slug]
            results.append(RateResult(
                slug=slug, buy_rate=buy, sell_rate=sell,
                scraped_at=now_peru(), response_ms=ms, success=True,
            ))
            _cb_record(slug, True)  # resetear circuit breaker si CED funciona
            logger.info(f"[CED-BATCH] ✅ {slug} recuperado: compra={buy} venta={sell}")

    return results
