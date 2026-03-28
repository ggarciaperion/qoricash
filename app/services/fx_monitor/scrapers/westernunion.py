"""
Scraper para Western Union FX — westernunionperu.pe
Su web es una SPA totalmente JS-rendered. Las tasas se obtienen desde
cuantoestaeldolar.pe (path="western-union") que las actualiza en tiempo real.
"""
from .cuantoestaeldolar import CedBaseScraper


class WesternUnionScraper(CedBaseScraper):
    slug     = "westernunion"
    url      = "https://westernunionperu.pe/cambiodemoneda"
    ced_path = "western-union"
