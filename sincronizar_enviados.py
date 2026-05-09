"""
Marca como "En Seguimiento" todos los prospectos a quienes ya se les envio correo
por las campanas anteriores (enviados_campana2.json y enviados_precios.json).

Uso: python3 sincronizar_enviados.py
"""
import os, json
import urllib.request, urllib.error

APP_URL  = "https://app.qoricash.pe"
API_KEY  = "qc-import-prospectos-2026"
BASE_DIR = os.path.join(os.path.expanduser("~"), "Desktop", "Prospeccion")

ARCHIVOS = [
    os.path.join(BASE_DIR, "enviados_campana2.json"),
    os.path.join(BASE_DIR, "enviados_precios.json"),
    os.path.join(BASE_DIR, "enviados.json"),
]

def post(endpoint, payload):
    body = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(
        f"{APP_URL}{endpoint}", data=body,
        headers={"Content-Type": "application/json", "X-Import-Key": API_KEY},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def run():
    emails = set()
    for archivo in ARCHIVOS:
        if not os.path.exists(archivo):
            print(f"  [omitido] {os.path.basename(archivo)} no encontrado")
            continue
        with open(archivo) as f:
            data = json.load(f)
            if isinstance(data, list):
                for e in data:
                    if isinstance(e, str) and "@" in e:
                        emails.add(e.strip().lower())
            elif isinstance(data, dict):
                for e in data.keys():
                    if "@" in e:
                        emails.add(e.strip().lower())
        print(f"  {os.path.basename(archivo)}: {len(emails)} emails acumulados")

    emails = list(emails)
    print(f"\nTotal emails a sincronizar: {len(emails)}")
    if not emails:
        print("Nada que sincronizar.")
        return

    LOTE = 300
    total_act = total_nf = 0
    for i in range(0, len(emails), LOTE):
        lote = emails[i:i+LOTE]
        resp = post("/prospeccion/api/sincronizar-enviados", {"emails": lote})
        total_act += resp.get("actualizados", 0)
        total_nf  += resp.get("no_encontrados", 0)
        print(f"  Lote {i//LOTE+1}: {resp.get('actualizados',0)} actualizados", flush=True)

    print(f"\nResultado final:")
    print(f"  Actualizados  : {total_act}")
    print(f"  No encontrados: {total_nf}")

if __name__ == "__main__":
    run()
