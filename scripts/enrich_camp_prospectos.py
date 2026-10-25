"""
enrich_camp_prospectos.py — Enriquece camp_prospecto desde PROSPECTOS_MASTER (Google Sheets).

Vincula por email exacto (case-insensitive). No une por nombre ni empresa.
Cuando hay múltiples filas con el mismo email en Sheets, usa la que tenga
Fecha Ultimo Contacto más reciente (o la primera si no hay fechas).

Envía los registros al endpoint /api/prospeccion/sync-enrich del servidor Flask
(compatible con localhost y Render). Las credenciales de Sheets quedan en la Mac;
el servidor solo recibe JSON limpio vía HTTP autenticado.

Uso:
    python3 enrich_camp_prospectos.py [--limit N] [--url URL] [--dry-run]

  --url URL    Endpoint Flask (por defecto: localhost:5002).
               Para Render: --url https://tu-app.onrender.com/agentes/api/prospeccion/sync-enrich
  --dry-run    Lee Sheets y deduplica, pero no envía al servidor.

Requiere:
  - token.json con acceso a PROSPECTOS_MASTER.
  - SYNC_API_KEY en entorno o ~/.config/qoricash/sync_key (misma clave que el servidor).
Se puede relanzar en cualquier momento — es idempotente (COALESCE upsert en el servidor).
"""

import os
import sys
import argparse
import json
import time
import urllib.request
import urllib.error

# ── Config ────────────────────────────────────────────────────────────────────
SHEET_ID    = '1Dn0YmyPK3417MKIin1xMUm9cbMxqvgysGePO9d9pxUw'
SHEET_TAB   = 'PROSPECTOS_MASTER'
TOKEN_PATH  = os.path.expanduser('~/Desktop/Prospeccion/token.json')
SCOPES      = ['https://www.googleapis.com/auth/spreadsheets']
BATCH_SIZE  = 5000  # rows per Sheets API call
DEFAULT_URL = 'http://localhost:5002/agentes/api/prospeccion/sync-enrich'
_KEY_FILE   = os.path.expanduser('~/.config/qoricash/sync_key')
API_BATCH   = 500   # records per POST to /sync-enrich
# ─────────────────────────────────────────────────────────────────────────────


def _load_api_key() -> str:
    """Lee la clave de API desde SYNC_API_KEY o ~/.config/qoricash/sync_key."""
    k = os.environ.get('SYNC_API_KEY', '').strip()
    if k:
        return k
    if os.path.exists(_KEY_FILE):
        try:
            v = open(_KEY_FILE).read().strip()
            if v:
                return v
        except OSError:
            pass
    print('[ERROR] Clave de sincronización no configurada.')
    print(f'  Configura SYNC_API_KEY como variable de entorno')
    print(f'  o crea {_KEY_FILE} con el valor de la clave.')
    sys.exit(2)


def get_sheets_service():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    return build('sheets', 'v4', credentials=creds)


def read_master_rows(svc, limit=None):
    """
    Lee PROSPECTOS_MASTER en batches. Retorna lista de dicts con:
    ruc, razon_social, nombre_contacto, cargo, email, telefono, provincia, rubro.
    """
    # Cols: A=RUC B=Razon Social C=Nombre Contacto D=Cargo E=Email
    #       F=Telefono G=Provincia H=Rubro I=Estado Email J=Estado Comercial K=Fecha Ultimo
    rows_out = []
    start = 2  # skip header

    print(f"Leyendo {SHEET_TAB}…", end='', flush=True)
    while True:
        end = start + BATCH_SIZE - 1
        range_ = f'{SHEET_TAB}!A{start}:K{end}'
        try:
            result = svc.spreadsheets().values().get(
                spreadsheetId=SHEET_ID, range=range_).execute()
        except Exception as exc:
            # HTTP 400 = requested range exceeds grid bounds → hoja terminó
            code = getattr(exc, 'status_code', None) or getattr(getattr(exc, 'resp', None), 'status', None)
            if str(code) == '400' or '400' in str(exc):
                break
            raise
        values = result.get('values', [])
        if not values:
            break

        for row in values:
            def col(i):
                return row[i].strip() if i < len(row) else ''

            email = col(4).lower()
            if not email or '@' not in email:
                continue

            rows_out.append({
                'ruc':             col(0) or None,
                'razon_social':    col(1) or None,
                'nombre_contacto': col(2) or None,
                'cargo':           col(3) or None,
                'email':           email,
                'telefono':        col(5) or None,
                'provincia':       col(6) or None,
                'rubro':           col(7) or None,
                'fecha_ultimo':    col(10) or None,
            })

        print('.', end='', flush=True)
        start += BATCH_SIZE

        if limit and len(rows_out) >= limit:
            rows_out = rows_out[:limit]
            break

    print(f' {len(rows_out):,} filas leídas.')
    return rows_out


def dedup_by_email(rows):
    """
    Si hay múltiples filas con el mismo email, retiene la de fecha más reciente.
    NO fusiona registros de empresas distintas.
    """
    best = {}
    ambiguous = {}  # email → set of razon_social when same email → different companies

    for r in rows:
        email = r['email']
        if email not in best:
            best[email] = r
        else:
            prev = best[email]
            # Track if different companies share the email
            if r.get('razon_social') and prev.get('razon_social'):
                if r['razon_social'] != prev['razon_social']:
                    if email not in ambiguous:
                        ambiguous[email] = {prev['razon_social']}
                    ambiguous[email].add(r['razon_social'])
            # Keep the row with more recent fecha_ultimo
            cur_fecha  = r.get('fecha_ultimo') or ''
            prev_fecha = prev.get('fecha_ultimo') or ''
            if cur_fecha > prev_fecha:
                best[email] = r

    if ambiguous:
        print(f"  Aviso: {len(ambiguous)} emails compartidos por múltiples empresas "
              f"(se conserva el más reciente; marcado como ambiguo).")

    return best, ambiguous


def send_to_api(url, api_key, records_by_email, ambiguous_emails, camp_emails):
    """
    Envía registros al endpoint /sync-enrich en lotes de API_BATCH.
    Solo envía emails presentes en camp_emails (ya importados al servidor).
    Retorna (upserted, omitidos_sin_match, errores).
    El servidor hace upsert idempotente con COALESCE — compatible con SQLite y PostgreSQL.
    La clave nunca se registra en logs.
    """
    now = time.strftime('%Y-%m-%d %H:%M:%S')

    # Construir lista filtrada
    to_send = []
    omitidos = 0
    for email, r in records_by_email.items():
        if email not in camp_emails:
            omitidos += 1
            continue
        to_send.append({
            'email':           email,
            'ruc':             r['ruc'],
            'razon_social':    r['razon_social'],
            'nombre_contacto': r['nombre_contacto'],
            'cargo':           r['cargo'],
            'telefono':        r['telefono'],
            'rubro':           r['rubro'],
            'provincia':       r['provincia'],
            'fuente':          'sheets_ambiguo' if email in ambiguous_emails else 'sheets_master',
            'actualizado_at':  now,
        })

    upserted = 0
    errores  = 0

    headers = {
        'Content-Type': 'application/json; charset=utf-8',
        'X-Sync-Client': 'enrich_camp_prospectos/2.0',
    }
    if api_key:
        headers['X-Sync-Key'] = api_key   # nunca aparece en logs

    total = len(to_send)
    for i in range(0, total, API_BATCH):
        batch = to_send[i:i + API_BATCH]
        body  = json.dumps({'records': batch}).encode('utf-8')
        req   = urllib.request.Request(url, data=body, headers=headers, method='POST')
        lote  = f'lote {i//API_BATCH + 1}/{(total + API_BATCH - 1)//API_BATCH}'
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode('utf-8', errors='replace'))
                upserted += data.get('upserted', 0)
                print(f'  {lote}: {data.get("upserted", "?")} upserted / '
                      f'{data.get("skipped", "?")} skipped')
        except urllib.error.HTTPError as exc:
            body_err = ''
            try:
                body_err = exc.read().decode('utf-8', errors='replace')[:200]
            except Exception:
                pass
            print(f'  {lote}: HTTP {exc.code} — {body_err}')
            errores += len(batch)
        except Exception as exc:
            print(f'  {lote}: {type(exc).__name__}: {exc}')
            errores += len(batch)

    return upserted, omitidos, errores


def main():
    parser = argparse.ArgumentParser(
        description='Enriquece camp_prospecto vía API desde PROSPECTOS_MASTER (Google Sheets)')
    parser.add_argument('--limit', type=int, default=None,
                        help='Leer solo N filas de Sheets (para pruebas)')
    parser.add_argument('--url', default=DEFAULT_URL,
                        help='Endpoint Flask sync-enrich')
    parser.add_argument('--dry-run', action='store_true',
                        help='Leer y deduplicar Sheets pero no enviar al servidor')
    args = parser.parse_args()

    api_key = '' if args.dry_run else _load_api_key()

    print(f"Endpoint: {args.url}")
    if args.dry_run:
        print("  (dry-run: solo se listan, no se envían)")

    # Obtener emails ya importados (camp_envio) para filtrar antes de enviar
    # El servidor expone cuántos emails existen via el mismo endpoint con GET
    # — pero para no hacer dos trips, consultamos directamente si estamos en localhost.
    # Si el servidor está en Render, pasamos camp_emails vacío: el servidor filtrará por sí mismo.
    camp_emails: set = set()
    if not args.dry_run:
        # Intentar leer camp_envio emails desde el servidor
        try:
            req = urllib.request.Request(
                args.url.replace('/sync-enrich', '/camp-emails'),
                headers={'X-Sync-Key': api_key} if api_key else {},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                camp_emails = set(data.get('emails', []))
                print(f"Emails en camp_envio (servidor): {len(camp_emails):,}")
        except Exception:
            # Endpoint no disponible o no existe — enviar todo y dejar que el servidor filtre
            camp_emails = None  # type: ignore[assignment]
            print("  Aviso: no se pudo consultar /camp-emails; se enviarán todos los registros.")

    # Read Sheets
    svc = get_sheets_service()
    rows = read_master_rows(svc, limit=args.limit)

    # Dedup
    records_by_email, ambiguous = dedup_by_email(rows)
    print(f"Emails únicos en Sheets: {len(records_by_email):,}")

    if camp_emails is not None:
        matches = sum(1 for e in records_by_email if e in camp_emails)
        print(f"Intersección con camp_envio (matches): {matches:,}")
    else:
        # Sin filtro previo: enviar todos y dejar que el servidor upserte solo los que existen
        camp_emails = set(records_by_email.keys())

    if args.dry_run:
        filtrados = sum(1 for e in records_by_email if e in camp_emails)
        print(f"\n=== DRY-RUN ===")
        print(f"Registros que se enviarían: {filtrados:,}")
        print(f"Sin match en camp_envio (omitidos): {len(records_by_email) - filtrados:,}")
        return

    # Enviar al endpoint
    upserted, omitidos, errores = send_to_api(
        args.url, api_key, records_by_email, ambiguous, camp_emails)

    print(f"\n=== RESULTADO ===")
    print(f"Upserted en camp_prospecto: {upserted:,}")
    print(f"Sin match en camp_envio (omitidos localmente): {omitidos:,}")
    if errores:
        print(f"Errores de envío: {errores:,} registros no confirmados")
        sys.exit(1)


if __name__ == '__main__':
    main()
