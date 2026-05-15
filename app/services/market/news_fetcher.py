"""
Recolector de noticias financieras via RSS.
Fuentes: BBC Business, CNBC Economy, Bloomberg, Investing.com, MarketWatch, Gestión (PE).
"""
import hashlib
import logging
from datetime import datetime, timezone
from app.utils.formatters import now_peru
from email.utils import parsedate_to_datetime
from typing import Optional

import feedparser
import requests

from .news_classifier import classify

# ── Traducción al español ─────────────────────────────────────────────────────
try:
    from deep_translator import GoogleTranslator
    _translator = GoogleTranslator(source='auto', target='es')
    _TRANSLATION_ENABLED = True
except ImportError:
    _TRANSLATION_ENABLED = False

# Palabras comunes en inglés para detectar si un texto necesita traducción
_EN_MARKERS = {
    'the','a','is','are','was','were','has','have','had','will','would',
    'could','should','of','in','on','at','to','for','with','by','from',
    'into','as','it','its','be','been','do','does','did','not','but',
    'or','and','that','this','which','who','what','how','when','where',
    'over','after','through','since','than','new','says','said','report',
    'market','rate','bank','growth','data','stock','trade','deal','up','down',
}

def _needs_translation(text: str) -> bool:
    """Detecta si el texto está en inglés basándose en palabras clave."""
    if not text:
        return False
    words = set(text.lower().split())
    return len(words & _EN_MARKERS) >= 2

def _translate(text: str, max_chars: int = 500) -> str:
    """Traduce al español si el texto parece inglés. Fallback: texto original."""
    if not _TRANSLATION_ENABLED or not text or not _needs_translation(text):
        return text
    try:
        chunk = text[:max_chars]
        return _translator.translate(chunk) or text
    except Exception:
        return text

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

# ── Catálogo de fuentes RSS ───────────────────────────────────────────────────
RSS_SOURCES = [
    # ── Internacional en Español (mercados globales / EE.UU.) ────────────────
    {
        "name":    "Reuters Español",
        "country": "US",
        "url":     "https://feeds.reuters.com/reuters/espanol/businessNews",
        "limit":   20,
    },
    {
        "name":    "Reuters ES — Mundo",
        "country": "US",
        "url":     "https://feeds.reuters.com/reuters/espanol/topNews",
        "limit":   15,
    },
    {
        "name":    "Investing.com ES — Mercados",
        "country": "US",
        "url":     "https://es.investing.com/rss/news.rss",
        "limit":   20,
    },
    {
        "name":    "Investing.com ES — FX",
        "country": "US",
        "url":     "https://es.investing.com/rss/news_1.rss",
        "limit":   10,
    },
    {
        "name":    "Investing.com ES — Economía",
        "country": "US",
        "url":     "https://es.investing.com/rss/news_14.rss",
        "limit":   10,
    },
    {
        "name":    "CNN Español",
        "country": "US",
        "url":     "https://cnnespanol.cnn.com/tag/economia/feed/",
        "limit":   10,
    },
    {
        "name":    "El País Economía",
        "country": "US",
        "url":     "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/economia/portada",
        "limit":   10,
    },
    # ── Latinoamérica ─────────────────────────────────────────────────────────
    {
        "name":    "Expansión MX",
        "country": "MX",
        "url":     "https://expansion.mx/rss",
        "limit":   10,
    },
    {
        "name":    "El Economista MX",
        "country": "MX",
        "url":     "https://www.eleconomista.com.mx/rss/",
        "limit":   10,
    },
    {
        "name":    "Infobae Economía",
        "country": "US",
        "url":     "https://www.infobae.com/feeds/rss/economia/",
        "limit":   10,
    },
    # ── Perú ─────────────────────────────────────────────────────────────────
    {
        "name":    "Gestión",
        "country": "PE",
        "url":     "https://gestion.pe/arc/outboundfeeds/rss/?outputType=xml",
        "limit":   20,
    },
    {
        "name":    "El Comercio Economía",
        "country": "PE",
        "url":     "https://elcomercio.pe/arc/outboundfeeds/rss/category/economia/?outputType=xml",
        "limit":   15,
    },
    {
        "name":    "RPP Economía",
        "country": "PE",
        "url":     "https://rpp.pe/rss/economia.xml",
        "limit":   10,
    },
    {
        "name":    "Semana Económica",
        "country": "PE",
        "url":     "https://semanaeconomica.com/feed",
        "limit":   10,
    },
]


def _parse_date(entry) -> Optional[datetime]:
    """Extrae la fecha de publicación y la convierte a UTC naive (para almacenar en DB)."""
    for attr in ("published", "updated"):
        raw = getattr(entry, attr, None)
        if raw:
            try:
                dt = parsedate_to_datetime(raw)
                # Convertir a UTC antes de quitar el timezone
                dt_utc = dt.astimezone(timezone.utc)
                return dt_utc.replace(tzinfo=None)
            except Exception:
                pass
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            # published_parsed ya viene en UTC (time.gmtime)
            return datetime(*entry.published_parsed[:6])
        except Exception:
            pass
    return now_peru()


def _url_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


def _fetch_source(source: dict) -> list[dict]:
    """Obtiene y parsea un feed RSS. Retorna lista de artículos normalizados."""
    try:
        resp = requests.get(source["url"], headers=_HEADERS, timeout=10)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
        articles = []
        for entry in feed.entries[: source["limit"]]:
            url  = getattr(entry, "link", "") or ""
            if not url:
                continue
            title   = getattr(entry, "title",   "") or ""
            summary = getattr(entry, "summary", "") or ""
            # Limpiar HTML básico del summary
            import re
            summary = re.sub(r"<[^>]+>", " ", summary).strip()[:400]

            # Traducir al español si el texto está en inglés
            title   = _translate(title,   max_chars=290)
            summary = _translate(summary, max_chars=400)

            impact, direction, sentiment = classify(title, summary)

            articles.append({
                "source":         source["name"],
                "source_country": source["country"],
                "title":          title[:290],
                "summary":        summary,
                "url":            url[:490],
                "url_hash":       _url_hash(url),
                "published_at":   _parse_date(entry),
                "impact_level":   impact,
                "direction":      direction,
                "sentiment_score": sentiment,
            })
        logger.debug(f"[Noticias] {source['name']}: {len(articles)} artículos")
        return articles
    except Exception as e:
        logger.warning(f"[Noticias] Error en {source['name']}: {e}")
        return []


def fetch_all_news() -> list[dict]:
    """
    Obtiene noticias de todas las fuentes configuradas.
    Retorna lista de artículos normalizados y clasificados.
    """
    all_articles = []
    for source in RSS_SOURCES:
        all_articles.extend(_fetch_source(source))

    # Deduplicar por url_hash (pueden venir de varias fuentes)
    seen = set()
    unique = []
    for art in all_articles:
        h = art["url_hash"]
        if h not in seen:
            seen.add(h)
            unique.append(art)

    logger.info(f"[Noticias] Total recolectadas: {len(unique)} (de {len(all_articles)} brutas)")
    return unique
