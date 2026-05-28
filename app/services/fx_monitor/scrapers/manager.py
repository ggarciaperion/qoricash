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
from .metafxperu    import MetaFXPeruScraper

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
    # Backoff progresivo: 5 fallas → 60s · 10 fallas → 5min · 20 fallas → 30min
    if   fails >= 20: cooldown = 1800
    elif fails >= 10: cooldown = 300
    elif fails >= 5:  cooldown = 60
    else:             cooldown = 0
    if cooldown:
        entry["open_until"] = time.monotonic() + cooldown
        logger.warning(f"[CB] {slug}: {fails} fallas → cooldown {cooldown}s")


ALL_SCRAPERS = [
    MetaFXPeruScraper(),
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


def scrape_all(active_slugs=None, max_workers=18):
    """
    Ejecuta todos los scrapers activos en paralelo con circuit breaker.
    Scrapers en cooldown se saltan para no ralentizar el ciclo.
    """
    scrapers = ALL_SCRAPERS
    if active_slugs is not None:
        scrapers = [s for s in ALL_SCRAPERS if s.slug in active_slugs]

    # Separar scrapers activos de los que están en cooldown
    ready   = [s for s in scrapers if not _cb_open(s.slug)]
    skipped = [s.slug for s in scrapers if _cb_open(s.slug)]
    if skipped:
        logger.debug(f"[CB] Saltando {len(skipped)} scrapers en cooldown: {skipped}")

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(s.safe_fetch): s.slug for s in ready}
        for future in as_completed(futures):
            slug = futures[future]
            try:
                result = future.result()
                _cb_record(slug, result.success)
                results.append(result)
                status = "✅" if result.success else "❌"
                logger.info(f"[FX] {status} {slug}: compra={result.buy_rate} venta={result.sell_rate} ({result.response_ms}ms)")
            except Exception as e:
                _cb_record(slug, False)
                logger.error(f"[FX] 💥 {slug}: {e}")

    return results
