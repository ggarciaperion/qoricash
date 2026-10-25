"""
enrich_camp_prospectos.py — Enriquece camp_prospecto desde PROSPECTOS_MASTER (Google Sheets).

Vincula por email exacto (case-insensitive). No une por nombre ni empresa.
Cuando hay múltiples filas con el mismo email en Sheets, usa la que tenga
Fecha Ultimo Contacto más reciente (o la primera si no hay fechas).

Uso:
    python3 enrich_camp_prospectos.py [--limit N]

Requiere token.json con acceso a la hoja PROSPECTOS_MASTER.
Se puede relanzar en cualquier momento — es idempotente (INSERT OR REPLACE).
"""

import os
import sys
import sqlite3
import argparse
import time

# ── Config ────────────────────────────────────────────────────────────────────
SHEET_ID   = '1Dn0YmyPK3417MKIin1xMUm9cbMxqvgysGePO9d9pxUw'
SHEET_TAB  = 'PROSPECTOS_MASTER'
TOKEN_PATH = os.path.expanduser('~/Desktop/Prospeccion/token.json')
SCOPES     = ['https://www.googleapis.com/auth/spreadsheets']
BATCH_SIZE = 5000  # rows per Sheets API call
DB_PATH    = os.path.join(os.path.dirname(__file__),
             '..', 'Qoricash', 'Sistema', 'qoricash', 'instance', 'qoricash_local.db')
# ─────────────────────────────────────────────────────────────────────────────


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


def upsert_to_db(db_path, records_by_email, ambiguous_emails, camp_emails):
    """
    INSERT OR REPLACE en camp_prospecto solo para emails en camp_emails.
    Retorna (insertados, omitidos_sin_match).
    """
    conn = sqlite3.connect(db_path)
    now  = time.strftime('%Y-%m-%d %H:%M:%S')

    insertados = 0
    omitidos   = 0

    sql = """
        INSERT OR REPLACE INTO camp_prospecto
            (email, ruc, razon_social, nombre_contacto, cargo,
             telefono, rubro, provincia, fuente, actualizado_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """

    for email, r in records_by_email.items():
        if email not in camp_emails:
            omitidos += 1
            continue
        fuente = 'sheets_ambiguo' if email in ambiguous_emails else 'sheets_master'
        conn.execute(sql, (
            email, r['ruc'], r['razon_social'], r['nombre_contacto'],
            r['cargo'], r['telefono'], r['rubro'], r['provincia'],
            fuente, now,
        ))
        insertados += 1

    conn.commit()
    conn.close()
    return insertados, omitidos


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=None,
                        help='Leer solo N filas de Sheets (para pruebas)')
    parser.add_argument('--db', default=DB_PATH,
                        help='Ruta al archivo SQLite')
    args = parser.parse_args()

    db_path = os.path.abspath(args.db)
    if not os.path.exists(db_path):
        # Try alternate locations
        alts = [
            os.path.join(os.path.dirname(__file__), '..', '..', 'instance', 'qoricash_local.db'),
            os.path.join(os.path.dirname(__file__), '..', '..', 'qoricash', 'instance', 'qoricash_local.db'),
        ]
        for alt in alts:
            if os.path.exists(os.path.abspath(alt)):
                db_path = os.path.abspath(alt)
                break
        else:
            print(f"ERROR: No se encontró la base de datos en {db_path}")
            print("Pasa --db /ruta/a/qoricash_local.db")
            sys.exit(1)

    print(f"DB: {db_path}")

    # Load camp_envio emails for matching
    conn = sqlite3.connect(db_path)
    camp_emails = set(
        r[0] for r in conn.execute("SELECT DISTINCT email FROM camp_envio").fetchall()
    )
    conn.close()
    print(f"Emails en camp_envio: {len(camp_emails):,}")

    # Read Sheets
    svc = get_sheets_service()
    rows = read_master_rows(svc, limit=args.limit)

    # Dedup
    records_by_email, ambiguous = dedup_by_email(rows)
    print(f"Emails únicos en Sheets: {len(records_by_email):,}")
    print(f"Intersección (matches): {sum(1 for e in records_by_email if e in camp_emails):,}")

    # Upsert
    insertados, omitidos = upsert_to_db(db_path, records_by_email, ambiguous, camp_emails)

    print(f"\n=== RESULTADO ===")
    print(f"Insertados en camp_prospecto: {insertados:,}")
    print(f"Sin envío en historial (omitidos): {omitidos:,}")
    print(f"Fuente: PROSPECTOS_MASTER (Google Sheets)")

    # Quick coverage check
    conn = sqlite3.connect(db_path)
    con_datos = conn.execute("""
        SELECT COUNT(DISTINCT ce.email)
        FROM camp_envio ce
        INNER JOIN camp_prospecto cp ON cp.email = ce.email
        WHERE cp.nombre_contacto IS NOT NULL
    """).scalar()
    print(f"Contactos con nombre registrado: {con_datos:,} de {len(camp_emails):,} "
          f"({100*con_datos//len(camp_emails) if camp_emails else 0}%)")
    conn.close()


if __name__ == '__main__':
    main()
