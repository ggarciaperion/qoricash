"""
Scraper para TKambio — tkambio.com
Fuente: cuantoestaeldolar.pe (ced_path="tkambio")
(verificado 2026-05)
"""
from .cuantoestaeldolar import CedBaseScraper


class TKambioScraper(CedBaseScraper):
    slug     = "tkambio"
    url      = "https://tkambio.com"
    ced_path = "tkambio"
