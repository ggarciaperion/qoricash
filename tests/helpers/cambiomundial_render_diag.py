#!/usr/bin/env python3
"""
Diagnóstico de Cambio Mundial para Render Bash — solo lectura.

Copia y pega este script completo en la consola Bash de Render.
No inicializa Flask, no toca schedulers, no imprime credenciales.

Muestra:
  [DB]   last_attempt_at / last_valid_at / data_source / last_error
  [HTTP] estado / Content-Type / duración
  [RATE] compra y venta extraídas, o motivo por el que no se pueden extraer

Uso:
    python3 cambiomundial_render_diag.py
    # Lee DATABASE_URL del entorno de Render automáticamente.
"""
import os, sys, time, json, textwrap
import urllib.request, urllib.error

# ── 1. LECTURA DE BD (solo lectura, sin ORM) ─────────────────────────────────

DB_URL = os.environ.get("DATABASE_URL", "")
if not DB_URL:
    print("[DB] ERROR: DATABASE_URL no definida en el entorno.")
    sys.exit(1)

# Render usa postgres://, psycopg2 requiere postgresql://
if DB_URL.startswith("postgres://"):
    DB_URL = "postgresql://" + DB_URL[len("postgres://"):]

try:
    import psycopg2
    import psycopg2.extras

    conn = psycopg2.connect(DB_URL)
    conn.set_session(readonly=True, autocommit=True)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT
            c.slug,
            c.name,
            r.buy_rate,
            r.sell_rate,
            r.scrape_ok,
            r.last_attempt_at,
            r.last_valid_at,
            r.data_source,
            r.last_error,
            r.source_updated_at
        FROM fx_rate_current r
        JOIN fx_competitors  c ON c.id = r.competitor_id
        WHERE c.slug = 'cambiomundial'
        LIMIT 1
    """)
    row = cur.fetchone()
    cur.close()
    conn.close()

    print("\n[DB] Registro actual de Cambio Mundial")
    print("─" * 45)
    if row:
        for k, v in row.items():
            print(f"  {k:<22} {v}")
    else:
        print("  (sin registro — nunca scrapeado o fila eliminada)")

except ImportError:
    print("[DB] psycopg2 no disponible en este entorno. Instalando...")
    os.system("pip install psycopg2-binary -q")
    print("[DB] Reinicia el script tras la instalación.")
    sys.exit(1)
except Exception as exc:
    print(f"[DB] Error al conectar: {exc}")

# ── 2. PETICIÓN HTTP AL ENDPOINT PRIMARIO ────────────────────────────────────

_API_URL = "https://www.cambiomundial.com/backend/tasaCambio/daily"
_HEADERS = {
    "User-Agent":  "Mozilla/5.0 (compatible; qoricash-diag/1.0)",
    "Accept":      "application/json",
    "Referer":     "https://www.cambiomundial.com/",
    "Origin":      "https://www.cambiomundial.com",
}
_TIMEOUT = 10   # segundos — acotado

print("\n[HTTP] GET", _API_URL)
print("─" * 45)

t0 = time.monotonic()
http_ok = False
payload = None
try:
    req  = urllib.request.Request(_API_URL, headers=_HEADERS)
    resp = urllib.request.urlopen(req, timeout=_TIMEOUT)
    dur  = int((time.monotonic() - t0) * 1000)
    ct   = resp.headers.get("Content-Type", "(sin Content-Type)")
    body = resp.read(8192)   # acotado: no leer respuestas enormes

    print(f"  status           200 OK")
    print(f"  Content-Type     {ct}")
    print(f"  duración         {dur} ms")
    print(f"  bytes recibidos  {len(body)}")

    # Intentar parsear JSON
    try:
        payload = json.loads(body)
        http_ok = True
    except json.JSONDecodeError as je:
        preview = body[:200].decode("utf-8", errors="replace")
        print(f"\n[HTTP] No es JSON válido: {je}")
        print(f"  Primeros 200 bytes: {preview!r}")

except urllib.error.HTTPError as exc:
    dur = int((time.monotonic() - t0) * 1000)
    body_err = exc.read(512).decode("utf-8", errors="replace")
    print(f"  status           {exc.code} {exc.reason}")
    print(f"  duración         {dur} ms")
    print(f"  cuerpo (512B):   {body_err[:200]!r}")
except urllib.error.URLError as exc:
    dur = int((time.monotonic() - t0) * 1000)
    print(f"  ERROR de red:    {exc.reason}")
    print(f"  duración         {dur} ms")
    print("  Hipótesis: IP de Render bloqueada por Cloudflare, timeout, o DNS.")
except Exception as exc:
    print(f"  ERROR inesperado: {exc}")

# ── 3. EXTRACCIÓN DE TASAS ────────────────────────────────────────────────────

print("\n[RATE] Extracción de compra / venta")
print("─" * 45)

if not http_ok or payload is None:
    print("  No se puede extraer: petición HTTP falló (ver sección [HTTP]).")
else:
    # Lógica equivalente a CambioMundialScraper._extract_from_json
    buy = sell = None
    entry = None

    if isinstance(payload, list) and payload:
        entry = next(
            (r for r in payload if str(r.get("tipoTasa", "")).upper() == "REGULAR"),
            payload[0]
        )
    elif isinstance(payload, dict):
        entry = payload

    if entry:
        _KEYS_BUY  = ("buy", "compra", "buyRate", "tipoCambioCompra")
        _KEYS_SELL = ("sell", "venta", "sellRate", "tipoCambioVenta")

        for k in _KEYS_BUY:
            if k in entry and entry[k]:
                try:
                    buy = float(entry[k])
                    break
                except (ValueError, TypeError):
                    pass

        for k in _KEYS_SELL:
            if k in entry and entry[k]:
                try:
                    sell = float(entry[k])
                    break
                except (ValueError, TypeError):
                    pass

        if buy and sell:
            print(f"  compra  {buy}")
            print(f"  venta   {sell}")
            if buy < sell:
                print(f"  spread  {sell - buy:.4f}  ✓ válido")
            else:
                print(f"  ALERTA: buy ({buy}) >= sell ({sell}) — spread inválido")
        else:
            print("  No se encontraron campos buy/sell conocidos en la entrada.")
            print(f"  Claves disponibles: {list(entry.keys())}")
            # Mostrar el payload completo (acotado a 400 chars)
            raw = json.dumps(payload, ensure_ascii=False)
            print(f"  Payload (400c): {raw[:400]}")
    else:
        print(f"  Payload inesperado (tipo {type(payload).__name__}): {str(payload)[:200]}")

print()
