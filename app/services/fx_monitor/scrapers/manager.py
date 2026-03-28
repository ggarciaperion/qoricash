"""
Orquestador de todos los scrapers — ejecución paralela con ThreadPoolExecutor
"""
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

logger = logging.getLogger(__name__)

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
]


def scrape_all(active_slugs=None, max_workers=6):
    """
    Ejecuta todos los scrapers activos en paralelo.

    Args:
        active_slugs: lista de slugs activos (None = todos)
        max_workers:  hilos paralelos

    Returns:
        list[RateResult]
    """
    scrapers = ALL_SCRAPERS
    if active_slugs is not None:
        scrapers = [s for s in ALL_SCRAPERS if s.slug in active_slugs]

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(s.safe_fetch): s.slug for s in scrapers}
        for future in as_completed(futures):
            slug = futures[future]
            try:
                result = future.result()
                results.append(result)
                status = "✅" if result.success else "❌"
                logger.info(f"[FX] {status} {slug}: compra={result.buy_rate} venta={result.sell_rate} ({result.response_ms}ms)")
            except Exception as e:
                logger.error(f"[FX] 💥 {slug}: {e}")

    return results
