"""
Scraper para Cambio Mundial — cambiomundial.com
Su web es una SPA Angular totalmente JS-rendered. Las tasas se obtienen desde
cuantoestaeldolar.pe (path="cambiomundial") que las actualiza en tiempo real.
"""
from .cuantoestaeldolar import CedBaseScraper


class CambioMundialScraper(CedBaseScraper):
    slug     = "cambiomundial"
    url      = "https://www.cambiomundial.com"
    ced_path = "cambiomundial"
