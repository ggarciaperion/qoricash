"""
Clase base para todos los scrapers de competidores
"""
import time
import random
import logging
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]


@dataclass
class RateResult:
    slug:        str
    buy_rate:    float
    sell_rate:   float
    scraped_at:  datetime
    response_ms: int
    success:     bool  = True
    error:       str   = None


class BaseScraper:
    slug: str
    url:  str

    def get_headers(self):
        # NOTE: Accept-Encoding is intentionally omitted — setting it manually
        # prevents requests from auto-decompressing the response.
        return {
            "User-Agent":      random.choice(USER_AGENTS),
            "Accept":          "text/html,application/xhtml+xml,*/*;q=0.9",
            "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
            "DNT":             "1",
            "Connection":      "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    def get_json_headers(self):
        h = self.get_headers()
        h["Accept"] = "application/json, text/plain, */*"
        h["Referer"] = self.url
        return h

    def fetch(self) -> RateResult:
        raise NotImplementedError

    def safe_fetch(self) -> RateResult:
        """Wrapper con manejo de errores — nunca lanza excepción."""
        t0 = time.monotonic()
        try:
            result = self.fetch()
            return result
        except Exception as e:
            ms = int((time.monotonic() - t0) * 1000)
            logger.error(f"[{self.slug}] Error en scrape: {e}")
            return RateResult(
                slug=self.slug,
                buy_rate=0.0,
                sell_rate=0.0,
                scraped_at=datetime.utcnow(),
                response_ms=ms,
                success=False,
                error=str(e)[:255],
            )

    def _parse_rate(self, value) -> float:
        """Convierte string de precio a float de forma robusta."""
        if isinstance(value, (int, float)):
            return float(value)
        cleaned = str(value).strip().replace(",", ".").replace(" ", "")
        # Si tiene más de un punto, quitar los separadores de miles
        parts = cleaned.split(".")
        if len(parts) > 2:
            cleaned = "".join(parts[:-1]) + "." + parts[-1]
        return float(cleaned)
