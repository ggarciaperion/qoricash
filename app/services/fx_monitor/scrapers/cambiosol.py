"""
Scraper para Cambiosol — cambiosol.pe
Fuente: cuantoestaeldolar.pe (ced_path="cambiosol")
(verificado 2026-05)
"""
from .cuantoestaeldolar import CedBaseScraper


class CambiosolScraper(CedBaseScraper):
    slug     = "cambiosol"
    url      = "https://cambiosol.pe"
    ced_path = "cambiosol"
