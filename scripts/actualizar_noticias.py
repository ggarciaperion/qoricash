"""
Genera 15 noticias financieras diarias con Groq (Llama 3.3 70B)
y las publica en Upstash Redis para qoricash.pe.

Uso:
    python scripts/actualizar_noticias.py

Variables de entorno requeridas:
    GROQ_API_KEY
    UPSTASH_REDIS_REST_URL
    UPSTASH_REDIS_REST_TOKEN
"""

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone


# ── Config ────────────────────────────────────────────────────────────────────

LLM_API_KEY     = os.environ["OPENROUTER_API_KEY"]
UPSTASH_URL     = os.environ["UPSTASH_REDIS_REST_URL"]
UPSTASH_TOKEN   = os.environ["UPSTASH_REDIS_REST_TOKEN"]
REDIS_KEY       = "qoricash:noticias"
LLM_MODEL       = "meta-llama/llama-3.3-70b-instruct:free"
LLM_ENDPOINT    = "https://openrouter.ai/api/v1/chat/completions"

UNSPLASH_POOL = [
    "photo-1611974789855-9c2a0a7236a3",
    "photo-1554224155-6726b3ff858f",
    "photo-1621981386829-9b458080ee07",
    "photo-1578575437130-527eed3abbec",
    "photo-1570129477492-45c003edd2be",
    "photo-1547981609-4b6bfe67ca0b",
    "photo-1611273426858-450d8e3c9fce",
    "photo-1580519542036-c47de6196ba5",
    "photo-1518546305927-5a555bb7020d",
    "photo-1486325212027-8081e485255e",
    "photo-1526628953301-3cd9ea6a7b0e",
    "photo-1535320903710-d993d3d77d29",
    "photo-1559526324-593bc073d938",
    "photo-1604594849809-dfedbc827105",
    "photo-1521791136064-7986c2920216",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def http_post(url, headers, body):
    data = json.dumps(body).encode("utf-8")
    req  = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def build_prompt(iso_date, fecha_texto):
    images = ", ".join(UNSPLASH_POOL)
    return f"""Genera exactamente 15 noticias financieras del día {fecha_texto} para QoriCash, casa de cambio online peruana especializada en PEN/USD.

Distribución EXACTA:
- Las 2 primeras: destacada true — temas macro que impactan el tipo de cambio PEN/USD
- 4 de fuente "Gestión", categoría "Nacional" — BCRP, exportaciones, MEF, sector productivo
- 3 de fuente "Bloomberg", categoría "Internacional" — Fed, China, commodities, mercados globales
- 3 de fuente "TradingView", categoría "Nacional" o "Internacional" — PEN/USD, DXY, petróleo, metales, BTC
- 3 de fuente "Infobae", categoría "Internacional" — Argentina, Colombia, Chile o Brasil

Reglas:
- Cifras realistas para 2026 (tipo de cambio S/ 3.60–3.80, Fed entre 4%–5%)
- "contenido": mínimo 3 párrafos con nombres, cifras concretas y contexto
- "analisis": 2 párrafos — (1) impacto en PEN/USD y (2) recomendación para empresas con exposición cambiaria
- "fecha": exactamente "{iso_date}" para todas
- IDs: gen_001 a gen_015
- Imágenes (no repetir más de 3 veces la misma): {images}
  Formato: "https://images.unsplash.com/{{photo_id}}?w=1200&q=80"

Estructura de cada objeto JSON:
{{
  "id": "gen_001",
  "titulo": "Título informativo con datos numéricos",
  "descripcion": "Resumen de 2-3 oraciones",
  "contenido": "3-4 párrafos con detalles y cifras",
  "analisis": "2 párrafos: impacto PEN/USD y recomendación",
  "categoria": "Nacional" o "Internacional",
  "fuente": "Gestión" | "Bloomberg" | "TradingView" | "Infobae",
  "fecha": "{iso_date}",
  "destacada": false,
  "imagen": "https://images.unsplash.com/photo-XXXXX?w=1200&q=80"
}}

Devuelve ÚNICAMENTE el array JSON puro. Sin texto adicional. Sin bloques de código markdown. Empieza con [ y termina con ]."""


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    now = datetime.now(timezone.utc)
    iso_date    = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    weekdays    = ["lunes","martes","miércoles","jueves","viernes","sábado","domingo"]
    months      = ["enero","febrero","marzo","abril","mayo","junio",
                   "julio","agosto","septiembre","octubre","noviembre","diciembre"]
    fecha_texto = f"{weekdays[now.weekday()]} {now.day} de {months[now.month-1]} de {now.year}"

    print(f"[noticias] Generando para {fecha_texto}...")

    # 1. Llamar a Groq
    prompt = build_prompt(iso_date, fecha_texto)
    llm_body = {
        "model": LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.8,
        "max_tokens": 12000,
    }
    llm_headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://qoricash.pe",
        "X-Title": "QoriCash Noticias",
    }

    try:
        result = http_post(LLM_ENDPOINT, llm_headers, llm_body)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"[noticias] LLM HTTP {e.code}: {body}", file=sys.stderr)
        raise
    raw = result["choices"][0]["message"]["content"].strip()

    # Limpiar fences de markdown si Llama los incluye
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        raw = raw.rsplit("```", 1)[0].strip()

    noticias = json.loads(raw)
    assert isinstance(noticias, list) and len(noticias) > 0, "Array vacío o inválido"
    print(f"[noticias] Groq generó {len(noticias)} artículos.")

    # 2. Guardar en Upstash Redis
    redis_headers = {
        "Authorization": f"Bearer {UPSTASH_TOKEN}",
        "Content-Type": "application/json",
    }
    redis_body = ["SET", REDIS_KEY, json.dumps(noticias, ensure_ascii=False)]
    redis_result = http_post(UPSTASH_URL, redis_headers, redis_body)
    print(f"[noticias] Redis: {redis_result}")
    print(f"[noticias] ✓ {len(noticias)} noticias publicadas en qoricash.pe")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[noticias] ERROR: {e}", file=sys.stderr)
        sys.exit(1)
