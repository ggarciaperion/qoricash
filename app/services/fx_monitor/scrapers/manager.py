"""
Orquestador de todos los scrapers — ejecución paralela con ThreadPoolExecutor.
Circuit breaker por scraper: pausas automáticas ante fallas consecutivas.
Health tracking por scraper: métricas acumuladas de éxito/fallo/latencia.
"""
import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeout

from .kambista      import KambistaScraper
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
from .tkambio       import TKambioScraper
from .cambiosol     import CambiosolScraper
from .okane         import OkaneScraper

logger = logging.getLogger(__name__)

# ── Circuit breaker ────────────────────────────────────────────────────────────
# Evita que scrapers fallidos consuman tiempo del ciclo indefinidamente.
# _cb[slug] = {"fails": int, "open_until": float}
_cb: dict = {}

def _cb_open(slug: str) -> bool:
    """True = scraper en cooldown, saltar este ciclo."""
    entry = _cb.get(slug)
    return bool(entry and entry["open_until"] > time.monotonic())

def _cb_record(slug: str, success: bool):
    """Actualizar estado del circuit breaker y health tracking tras cada resultado."""
    if success:
        _cb.pop(slug, None)          # reset en éxito
        return
    entry = _cb.setdefault(slug, {"fails": 0, "open_until": 0.0})
    entry["fails"] += 1
    fails = entry["fails"]
    # Backoff progresivo: 5 fallas → 30s · 10 fallas → 2min · 20 fallas → 5min (máx)
    if   fails >= 20: cooldown = 300
    elif fails >= 10: cooldown = 120
    elif fails >= 5:  cooldown = 30
    else:             cooldown = 0
    if cooldown:
        entry["open_until"] = time.monotonic() + cooldown
        logger.warning(f"[CB] {slug}: {fails} fallas → cooldown {cooldown}s")


# ── Health tracking ───────────────────────────────────────────────────────────
# Métricas por scraper: consecutivos OK/fail, último error, último tiempo de respuesta.
# Acumulado en memoria desde el arranque del proceso; se resetea con cada deploy.
_health_lock = threading.Lock()
_health: dict = {}   # slug → {ok: int, fail: int, last_ms: int, last_error: str|None}

def _health_record(slug: str, success: bool, ms: int, error: str = None):
    with _health_lock:
        h = _health.setdefault(slug, {"ok": 0, "fail": 0, "last_ms": 0, "last_error": None})
        if success:
            h["ok"]         += 1
            h["last_ms"]     = ms
            h["last_error"]  = None
        else:
            h["fail"]       += 1
            h["last_error"]  = error

def get_scraper_health() -> dict:
    """Retorna snapshot de health metrics por slug. Seguro para leer desde cualquier thread."""
    with _health_lock:
        return {slug: dict(v) for slug, v in _health.items()}


ALL_SCRAPERS = [
    KambistaScraper(),
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
    TKambioScraper(),
    CambiosolScraper(),
    OkaneScraper(),
]

# ── In-flight tracking ─────────────────────────────────────────────────────────
# Evita arrancar un scraper cuando su hilo del ciclo anterior aún corre
# (ocurre si el ciclo anterior superó CYCLE_TIMEOUT y fue circuit-breaked).
_inflight_lock = threading.Lock()
_inflight: set = set()   # slugs cuyo thread OS aún está corriendo


# Mapa de slug → ced_path en cuantoestaeldolar.pe
# Usado como fallback cuando el scraper directo falla (ej. Cloudflare en cloud IPs)
_CED_FALLBACK = {
    "cambioseguro":"cambio-seguro",
    "tucambista":  "tu-cambista",
    "dollarhouse": "dollar-house",
    "moneyhouse":  "moneyhouse",
    "inkamoney":   "inkamoney",
    "dichikash":   "dichikash",
    "rextie":      "rextie",
    "kambista":    "kambista",
    "tkambio":     "tkambio",
    "cambiosol":   "cambiosol",
    "cambiafx":    "cambia-fx",
    # "cambiomundial": CED desactualizado desde 2026-05 — usa API directa ahora
    "westernunion":"western-union",
    "okane":       "okane",
}


def _ced_batch_fallback(failed_slugs: list) -> dict:
    """
    Descarga cuantoestaeldolar.pe UNA VEZ y extrae tasas para todos los slugs fallidos.
    Retorna dict slug → (buy, sell, source_updated_at) donde source_updated_at puede ser None.
    """
    from .cuantoestaeldolar import _fetch_ced_rates
    import re
    import requests

    slugs_with_path = {s: _CED_FALLBACK[s] for s in failed_slugs if s in _CED_FALLBACK}
    if not slugs_with_path:
        return {}

    # Descargar CED una sola vez para todos
    try:
        sess = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept":     "text/html,application/xhtml+xml,*/*;q=0.9",
            "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        }
        resp = sess.get("https://cuantoestaeldolar.pe", headers=headers, timeout=15, verify=False)
        resp.raise_for_status()

        chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.+?)"\]\)', resp.text, re.DOTALL)
        text = ""
        for chunk in chunks:
            try:
                text += chunk.encode().decode("unicode_escape")
            except Exception:
                text += chunk

        recovered: dict = {}
        for slug, ced_path in slugs_with_path.items():
            try:
                idx = text.find(f'"path":"{ced_path}"')
                if idx < 0:
                    idx = text.find(ced_path)
                if idx < 0:
                    continue
                window = text[idx: idx + 600]

                # Validar antigüedad y conservar timestamp del proveedor
                from datetime import datetime, timezone
                src_upd = None
                upd_m = re.search(r'"updated_at"\s*:\s*"([^"]+)"', window)
                if upd_m:
                    try:
                        upd_dt  = datetime.fromisoformat(upd_m.group(1).replace("Z", "+00:00"))
                        now_utc = datetime.now(timezone.utc)
                        stale_h = (now_utc - upd_dt).total_seconds() / 3600
                        if stale_h > 4.0:
                            logger.warning(f"[CED-BATCH] {slug}: dato CED tiene {stale_h:.1f}h — ignorando")
                            continue
                        if upd_dt <= now_utc:   # descartar timestamps futuros
                            src_upd = upd_dt
                    except Exception:
                        pass   # src_upd permanece None — vigencia no acreditada

                buy_m  = re.search(r'"buy"\s*:\s*\{[^}]*"cost"\s*:\s*"([\d.]+)"',  window)
                sell_m = re.search(r'"sale"\s*:\s*\{[^}]*"cost"\s*:\s*"([\d.]+)"', window)
                if buy_m and sell_m:
                    buy  = float(buy_m.group(1))
                    sell = float(sell_m.group(1))
                    if buy > 0 and sell > 0:
                        recovered[slug] = (buy, sell, src_upd)
            except Exception:
                continue

        logger.info(f"[CED-BATCH] Recuperados via CED: {list(recovered.keys())}")
        return recovered

    except Exception as e:
        logger.warning(f"[CED-BATCH] Error descargando cuantoestaeldolar.pe: {e}")
        return {}


_RATE_MIN = 2.5
_RATE_MAX = 6.0

# Tiempo máximo que se espera por todos los scrapers en paralelo.
# Si algún scraper no termina en este tiempo se registra como error y se circuit-breaka.
# Suficiente para scrapers lentos multi-estrategia (~35-40s con timeouts reducidos).
CYCLE_TIMEOUT = 40


def _is_valid_rate(buy: float, sell: float) -> bool:
    """Verifica que las tasas estén en rango razonable para PEN/USD."""
    return (_RATE_MIN < buy < _RATE_MAX and _RATE_MIN < sell < _RATE_MAX and buy < sell)


def scrape_all_gen(active_slugs=None, max_workers=18):
    """
    Generador: emite RateResult conforme llegan los scrapers.

    Fase 1 — scrapers directos: cada future se emite al terminar, sin esperar al resto.
    Fase 2 — CED batch: tras completar la fase 1, emite los resultados de fallback.

    El ejecutor usa pool.shutdown(wait=False): as_completed(timeout=CYCLE_TIMEOUT)
    actúa realmente como límite de tiempo — el contexto manager no lo anula.

    Scrapers cuyo hilo OS aún corre del ciclo anterior (_inflight) se saltan para
    evitar duplicados en vuelo.
    """
    from .base import RateResult
    from app.utils.formatters import now_peru

    scrapers = ALL_SCRAPERS
    if active_slugs is not None:
        scrapers = [s for s in ALL_SCRAPERS if s.slug in active_slugs]

    ready   = [s for s in scrapers if not _cb_open(s.slug)]
    skipped = [s.slug for s in scrapers if _cb_open(s.slug)]
    if skipped:
        logger.warning(f"[CB] {len(skipped)} scrapers en cooldown: {skipped} — CED fallback")

    # Excluir scrapers cuyo hilo OS del ciclo anterior aún está corriendo
    with _inflight_lock:
        still_running = [s.slug for s in ready if s.slug in _inflight]
        if still_running:
            logger.warning(f"[FX] Scrapers aún en vuelo del ciclo anterior: {still_running} — saltando")
        ready = [s for s in ready if s.slug not in _inflight]
        for s in ready:
            _inflight.add(s.slug)

    failed_slugs = list(still_running)   # tratar stuck scrapers como fallidos
    t_cycle = time.monotonic()
    pool = ThreadPoolExecutor(max_workers=max_workers)

    def _wrap(scraper):
        """Ejecuta safe_fetch y retira el slug de _inflight al terminar."""
        try:
            return scraper.safe_fetch()
        finally:
            with _inflight_lock:
                _inflight.discard(scraper.slug)

    try:
        futures = {pool.submit(_wrap, s): s.slug for s in ready}
        try:
            for future in as_completed(futures, timeout=CYCLE_TIMEOUT):
                slug = futures[future]
                try:
                    result = future.result()
                    if result.success and result.buy_rate > 0:
                        if not _is_valid_rate(result.buy_rate, result.sell_rate):
                            logger.warning(
                                f"[FX] ⚠️  {slug}: tasas fuera de rango "
                                f"buy={result.buy_rate} sell={result.sell_rate} — descartando"
                            )
                            result = RateResult(
                                slug=slug, buy_rate=0.0, sell_rate=0.0,
                                scraped_at=result.scraped_at,
                                response_ms=result.response_ms, success=False,
                                error=f"Fuera de rango: {result.buy_rate}/{result.sell_rate}")
                    _cb_record(slug, result.success)
                    _health_record(slug, result.success, result.response_ms, result.error)
                    status = "✅" if result.success else "❌"
                    logger.info(f"[FX] {status} {slug}: compra={result.buy_rate} venta={result.sell_rate} ({result.response_ms}ms)")
                    if not result.success or result.buy_rate == 0:
                        failed_slugs.append(slug)
                    yield result
                except Exception as e:
                    _cb_record(slug, False)
                    _health_record(slug, False, 0, str(e)[:255])
                    logger.error(f"[FX] 💥 {slug}: {e}")
                    failed_slugs.append(slug)
                    yield RateResult(slug=slug, buy_rate=0.0, sell_rate=0.0,
                                     scraped_at=now_peru(), response_ms=0,
                                     success=False, error=str(e)[:255])

        except FuturesTimeout:
            elapsed = int((time.monotonic() - t_cycle) * 1000)
            for future, slug in futures.items():
                if not future.done():
                    # Hilo sigue corriendo — NO retirar de _inflight (lo hará él mismo)
                    logger.error(f"[FX] ⏰ {slug}: timeout después de {elapsed}ms — circuit-breaking")
                    _cb_record(slug, False)
                    _health_record(slug, False, elapsed, f"Cycle timeout >{CYCLE_TIMEOUT}s")
                    failed_slugs.append(slug)
                    yield RateResult(
                        slug=slug, buy_rate=0.0, sell_rate=0.0,
                        scraped_at=now_peru(), response_ms=elapsed,
                        success=False, error=f"Cycle timeout >{CYCLE_TIMEOUT}s",
                    )
    finally:
        # shutdown(wait=False): el generador no bloquea esperando hilos timeout.
        # Los hilos vivos limpian _inflight solos al terminar vía _wrap/finally.
        pool.shutdown(wait=False)

    # ── Fase 2: CED batch ──────────────────────────────────────────────────────
    # Scrapers cooldown (skipped) + scrapers directos fallidos + stuck scrapers
    all_fallback = list(set(failed_slugs + skipped))
    if all_fallback:
        t0 = time.monotonic()
        recovered = _ced_batch_fallback(all_fallback)
        ms = int((time.monotonic() - t0) * 1000)
        for slug, (buy, sell, src_upd) in recovered.items():
            if not _is_valid_rate(buy, sell):
                logger.warning(f"[CED-BATCH] ⚠️  {slug}: fuera de rango {buy}/{sell} — ignorando")
                continue
            _cb_record(slug, True)
            _health_record(slug, True, ms)
            logger.info(f"[CED-BATCH] ✅ {slug} recuperado: compra={buy} venta={sell}")
            yield RateResult(
                slug=slug, buy_rate=buy, sell_rate=sell,
                scraped_at=now_peru(), response_ms=ms, success=True,
                source='ced_batch', source_updated_at=src_upd,
            )


def scrape_all(active_slugs=None, max_workers=18):
    """
    Wrapper síncrono sobre scrape_all_gen: retorna lista completa (fase 1 + fase 2).
    Último resultado por slug prevalece (CED batch sobreescribe fallo directo).
    """
    results_by_slug = {}
    for r in scrape_all_gen(active_slugs=active_slugs, max_workers=max_workers):
        results_by_slug[r.slug] = r
    return list(results_by_slug.values())
