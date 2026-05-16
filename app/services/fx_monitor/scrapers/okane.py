"""
Scraper para Okane — okane.pe
Fuente: cuantoestaeldolar.pe (ced_path="okane")
(verificado 2026-05)
"""
from .cuantoestaeldolar import CedBaseScraper


class OkaneScraper(CedBaseScraper):
    slug     = "okane"
    url      = "https://okane.pe"
    ced_path = "okane"
