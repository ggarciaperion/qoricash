#!/usr/bin/env python3
"""
FX Monitor — Diagnóstico real por scraper.
Prueba cada scraper con conexión HTTP real; no requiere Flask ni DB.
Uso: python3 scripts/fx_diagnose.py [--slug kambista] [--timeout 20]
"""
import sys, os, time, warnings, types, argparse
from datetime import datetime, timezone, timedelta

warnings.filterwarnings('ignore')
try:
    import urllib3; urllib3.disable_warnings()
except ImportError:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# ── Stubs de paquetes para importar scrapers sin disparar app/__init__.py ──────
# Creamos stubs con __path__ correcto: Python encuentra los módulos reales en disco
# pero NO ejecuta los __init__.py de los paquetes padre.

def _now_peru():
    return datetime.now(timezone(timedelta(hours=-5)))

def _make_pkg_stub(pkg_name: str):
    mod = types.ModuleType(pkg_name)
    parts = pkg_name.split('.')
    mod.__path__    = [os.path.join(ROOT, *parts)]
    mod.__package__ = pkg_name
    mod.__spec__    = None
    return mod

for _pkg in ['app', 'app.utils', 'app.services',
             'app.services.fx_monitor', 'app.services.fx_monitor.scrapers']:
    if _pkg not in sys.modules:
        sys.modules[_pkg] = _make_pkg_stub(_pkg)

# Módulo concreto: app.utils.formatters
_fmt = types.ModuleType('app.utils.formatters')
_fmt.now_peru = _now_peru
sys.modules['app.utils.formatters'] = _fmt

# ── Importar scrapers ─────────────────────────────────────────────────────────
from app.services.fx_monitor.scrapers.base         import BaseScraper, RateResult
from app.services.fx_monitor.scrapers.kambista      import KambistaScraper
from app.services.fx_monitor.scrapers.cambix        import CambixScraper
from app.services.fx_monitor.scrapers.cambioseguro  import CambioSeguroScraper
from app.services.fx_monitor.scrapers.tucambio      import TuCambioScraper
from app.services.fx_monitor.scrapers.tucambista    import TuCambistaScraper
from app.services.fx_monitor.scrapers.rexti         import RextiScraper
from app.services.fx_monitor.scrapers.dollarhouse   import DollarHouseScraper
from app.services.fx_monitor.scrapers.moneyhouse    import MoneyhouseScraper
from app.services.fx_monitor.scrapers.jetperu       import JetperuScraper
from app.services.fx_monitor.scrapers.inkamoney     import InkaMoneyPeru
from app.services.fx_monitor.scrapers.dichikash     import DichikashScraper
from app.services.fx_monitor.scrapers.westernunion  import WesternUnionScraper
from app.services.fx_monitor.scrapers.cambiafx      import CambiaFXScraper
from app.services.fx_monitor.scrapers.cambiomundial import CambioMundialScraper
from app.services.fx_monitor.scrapers.tkambio       import TKambioScraper
from app.services.fx_monitor.scrapers.cambiosol     import CambiosolScraper
from app.services.fx_monitor.scrapers.okane         import OkaneScraper

ALL_SCRAPERS = [
    KambistaScraper(),    CambixScraper(),       CambioSeguroScraper(),
    TuCambioScraper(),    TuCambistaScraper(),   RextiScraper(),
    DollarHouseScraper(), MoneyhouseScraper(),   JetperuScraper(),
    InkaMoneyPeru(),      DichikashScraper(),    WesternUnionScraper(),
    CambiaFXScraper(),    CambioMundialScraper(), TKambioScraper(),
    CambiosolScraper(),   OkaneScraper(),
]
SLUG_MAP = {s.slug: s for s in ALL_SCRAPERS}


def run_scraper(s: BaseScraper, timeout_secs: int = 25) -> dict:
    import concurrent.futures as _cf
    t0  = time.monotonic()
    ts  = _now_peru().strftime('%H:%M:%S')
    with _cf.ThreadPoolExecutor(max_workers=1) as pool:
        f = pool.submit(s.safe_fetch)
        try:
            r = f.result(timeout=timeout_secs)
        except _cf.TimeoutError:
            ms = int((time.monotonic() - t0) * 1000)
            return dict(slug=s.slug, url=s.url, ts=ts, ok=False,
                        buy=None, sell=None, ms=ms, source="n/a",
                        error=f"Timeout local >{timeout_secs}s")
    ms = int((time.monotonic() - t0) * 1000)
    return dict(slug=r.slug, url=s.url, ts=ts, ok=r.success,
                buy=round(r.buy_rate, 4)  if r.buy_rate  else None,
                sell=round(r.sell_rate, 4) if r.sell_rate else None,
                ms=ms, source=getattr(r, 'source', 'direct'),
                error=r.error)


def test_tucambio_identity():
    """Comprueba si cambiafx.pe/api/tc identifica inequívocamente TuCambio o CambiaFX."""
    import requests, json as _j
    print("\n=== Identidad TuCambio vs CambiaFX ===\n")
    for label, referer in [("TuCambio",  "https://www.tucambio.pe/"),
                            ("CambiaFX",  "https://cambiafx.pe/")]:
        try:
            r = requests.get(
                "https://cambiafx.pe/api/tc",
                headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json",
                         "Referer": referer},
                timeout=10, verify=False)
            data = r.json()
            print(f"  {label} (Referer={referer})")
            print(f"    Status:  {r.status_code}")
            print(f"    Body:    {_j.dumps(data, ensure_ascii=False)[:300]}")
            if isinstance(data, dict) and 'data' in data:
                item = (data['data'] or [{}])[0]
                print(f"    Keys:    {list(item.keys())}")
        except Exception as e:
            print(f"  {label}: ERROR — {e}")
        print()


def run_parallel(scrapers, timeout):
    import concurrent.futures as _cf
    results = []
    with _cf.ThreadPoolExecutor(max_workers=len(scrapers)) as pool:
        futs = {pool.submit(run_scraper, s, timeout): s.slug for s in scrapers}
        for f in _cf.as_completed(futs, timeout=timeout + 10):
            results.append(f.result())
    results.sort(key=lambda r: r["slug"])
    return results


def print_table(results):
    now = _now_peru().strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n{'='*80}")
    print(f"  FX Monitor — Diagnóstico real por scraper")
    print(f"  {now} Lima  |  macOS local (resultados pueden diferir de Render/cloud)")
    print(f"{'='*80}")
    print(f"\n{'Slug':<16} {'OK':<4} {'Compra':<8} {'Venta':<8} {'ms':<6} {'Fuente':<12} Detalle")
    print(f"{'─'*80}")
    ok_n = 0
    for r in results:
        ok   = "✅" if r["ok"] else "❌"
        buy  = f"{r['buy']:.4f}"  if r["buy"]  else "——"
        sell = f"{r['sell']:.4f}" if r["sell"] else "——"
        err  = (r["error"] or "")[:45]
        print(f"{r['slug']:<16} {ok:<4} {buy:<8} {sell:<8} {r['ms']:<6} {r.get('source','?'):<12} {err}")
        if r["ok"]: ok_n += 1
    print(f"\n  Resultado: {ok_n}/{len(results)} OK  —  {_now_peru().strftime('%H:%M:%S')} Lima")
    print(f"  Nota: IPs cloud pueden ser bloqueadas por Cloudflare/ratelimit.")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug",     help="slug(s) separados por coma")
    parser.add_argument("--timeout",  type=int, default=25)
    parser.add_argument("--parallel", action="store_true")
    parser.add_argument("--identity", action="store_true")
    args = parser.parse_args()

    if args.identity:
        test_tucambio_identity()
        sys.exit(0)

    scrapers = [SLUG_MAP[s.strip()] for s in args.slug.split(",")] if args.slug \
               else ALL_SCRAPERS

    if args.parallel:
        results = run_parallel(scrapers, args.timeout)
    else:
        results = [run_scraper(s, args.timeout) for s in scrapers]

    print_table(results)
