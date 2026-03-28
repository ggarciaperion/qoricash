"""
Scraper para CambiaFX — cambiafx.pe
Su web es una SPA Laravel+Inertia+Vite totalmente JS-rendered. Las tasas se
obtienen desde cuantoestaeldolar.pe (path="cambia-fx") que las actualiza en
tiempo real.
"""
from .cuantoestaeldolar import CedBaseScraper


class CambiaFXScraper(CedBaseScraper):
    slug     = "cambiafx"
    url      = "https://cambiafx.pe"
    ced_path = "cambia-fx"
