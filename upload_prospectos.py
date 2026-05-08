"""
Sube los 11K prospectos al servidor via HTTP.
Uso: python3 upload_prospectos.py
"""
import os, sys, json, openpyxl
import urllib.request, urllib.error

APP_URL  = "https://app.qoricash.pe"
API_KEY  = "qc-import-prospectos-2026"
EXCEL    = os.path.join(os.path.expanduser("~"), "Desktop", "QoriCash_BASE_MAESTRA_2026.xlsx")
ENDPOINT = f"{APP_URL}/prospeccion/api/import-batch"

HOJAS_SKIP = {"📊 RESUMEN"}
HOJA_GRUPO = {
    "🎯 PIPELINE ACTIVO":      "PIPELINE ACTIVO",
    "✅ CLIENTES LFC":          "CLIENTES LFC",
    "🔥 PRIORITARIOS":          "PRIORITARIOS",
    "⭐ CALIFICADOS":           "CALIFICADOS",
    "📬 POR CONTACTAR":        "POR CONTACTAR",
    "📋 UNIVERSO CONTACTADOS":  "UNIVERSO CONTACTADOS",
    "🔄 SOFT BOUNCE":           "SOFT BOUNCE",
    "🚫 NO CONTACTAR":          "NO CONTACTAR",
}
COL_MAP = {
    1:"razon_social", 2:"ruc", 3:"tipo", 4:"rubro", 5:"departamento",
    6:"provincia", 7:"nombre_contacto", 8:"cargo", 9:"email", 10:"email_alt",
    11:"telefono", 12:"cliente_lfc", 13:"score", 14:"clasificacion",
    15:"canal", 16:"remitente", 17:"tipo_ultimo_envio",
    18:"fecha_primer_contacto", 19:"fecha_ultimo_contacto",
    20:"fecha_proximo_contacto", 21:"num_contactos", 22:"estado_email",
    23:"estado_comercial", 24:"nivel_interes", 25:"fuente", 26:"notas",
}
INT_FIELDS = {"score", "num_contactos"}


def post(payload):
    body = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(
        ENDPOINT, data=body,
        headers={"Content-Type": "application/json", "X-Import-Key": API_KEY},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def run():
    # Verificar URL
    print(f"Conectando a {APP_URL} ...")
    resp = post({"action": "count"})
    existentes = resp.get("total", 0)
    print(f"  Registros actuales en servidor: {existentes}")

    if existentes > 0:
        r = input("Ya hay datos. Sobreescribir? (s/N): ")
        if r.lower() != "s":
            print("Cancelado.")
            return
        post({"action": "truncate"})
        print("  Tabla limpiada.")

    print(f"Leyendo {EXCEL} ...")
    wb = openpyxl.load_workbook(EXCEL, read_only=True, data_only=True)

    emails_vistos = set()
    total = 0

    for hoja_name in wb.sheetnames:
        if hoja_name in HOJAS_SKIP:
            continue
        ws    = wb[hoja_name]
        grupo = HOJA_GRUPO.get(hoja_name, hoja_name)
        rows  = list(ws.iter_rows(min_row=2))
        print(f"  [{hoja_name}] {len(rows)} filas...", end=" ", flush=True)

        lote = []
        for row in rows:
            if len(row) <= 9 or not row[9].value:
                continue
            email = str(row[9].value).strip().lower()
            if not email or "@" not in email or email in emails_vistos:
                continue
            emails_vistos.add(email)

            rec = {"grupo": grupo}
            for ci, field in COL_MAP.items():
                if ci < len(row):
                    v = row[ci].value
                    v = str(v).strip() if v is not None else None
                    if field in INT_FIELDS:
                        try: rec[field] = int(float(v)) if v else 0
                        except: rec[field] = 0
                    else:
                        rec[field] = v or None
            lote.append(rec)

            if len(lote) >= 200:
                r = post({"action": "insert", "registros": lote})
                total += r.get("insertados", 0)
                lote = []

        if lote:
            r = post({"action": "insert", "registros": lote})
            total += r.get("insertados", 0)

        print(f"OK")

    wb.close()
    final = post({"action": "count"}).get("total", "?")
    print(f"\nListo: {total} subidos — Total en servidor: {final}")


if __name__ == "__main__":
    run()
