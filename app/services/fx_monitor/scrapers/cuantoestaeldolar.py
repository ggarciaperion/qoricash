"""
Scraper base para empresas cuyas webs son SPAs no scrapeables.
Fuente: cuantoestaeldolar.pe — agrega tasas en tiempo real de +30 casas de cambio
peruanas. Los datos viven en el payload __next_f (Next.js App Router).

Uso: subclasear CedBaseScraper y definir `ced_path` con el slug de la empresa
en cuantoestaeldolar.pe (atributo "path" en el JSON).
"""
import re
import time
import requests
from datetime import datetime
from .base import BaseScraper, RateResult

_CED_URL = "https://cuantoestaeldolar.pe"


def _fetch_ced_rates(session, headers, ced_path: str, timeout: int = 12):
    """
    Descarga cuantoestaeldolar.pe y extrae compra/venta para `ced_path`.
    Retorna (buy_float, sell_float) o lanza ValueError.
    """
    resp = session.get(_CED_URL, headers=headers, timeout=timeout, verify=False)
    resp.raise_for_status()

    # Next.js App Router serializa los datos en fragmentos self.__next_f.push([1,"..."])
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.+?)"\]\)', resp.text, re.DOTALL)
    text = ""
    for chunk in chunks:
        try:
            text += chunk.encode().decode("unicode_escape")
        except Exception:
            text += chunk

    # Localizar el bloque del path solicitado y extraer buy/sale
    idx = text.find(f'"path":"{ced_path}"')
    if idx < 0:
        # intento alternativo: buscar sin comillas exactas (encoding)
        idx = text.find(ced_path)

    if idx < 0:
        raise ValueError(f"CED: path '{ced_path}' no encontrado en el payload")

    # Tomar ventana de 600 chars después del path y buscar tasas
    window = text[idx: idx + 600]
    buy_m  = re.search(r'"buy"\s*:\s*\{[^}]*"cost"\s*:\s*"([\d.]+)"',  window)
    sell_m = re.search(r'"sale"\s*:\s*\{[^}]*"cost"\s*:\s*"([\d.]+)"', window)

    if not buy_m or not sell_m:
        raise ValueError(f"CED: tasas no encontradas en el bloque de '{ced_path}'")

    buy  = float(buy_m.group(1))
    sell = float(sell_m.group(1))

    if buy <= 0 or sell <= 0:
        raise ValueError(f"CED: tasas inválidas para '{ced_path}' buy={buy} sell={sell}")

    return buy, sell


class CedBaseScraper(BaseScraper):
    """
    Scraper genérico que obtiene tasas desde cuantoestaeldolar.pe.
    Subclases deben definir: slug, url, ced_path.
    """
    ced_path: str = ""

    def fetch(self) -> RateResult:
        t0   = time.monotonic()
        sess = requests.Session()
        buy, sell = _fetch_ced_rates(sess, self.get_headers(), self.ced_path)
        ms   = int((time.monotonic() - t0) * 1000)
        return RateResult(slug=self.slug, buy_rate=buy, sell_rate=sell,
                          scraped_at=datetime.utcnow(), response_ms=ms)
