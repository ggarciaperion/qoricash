"""
Agente Creativo QoriCash — Genera propuestas de contenido para redes sociales.

Fuentes de información:
  1. Datos verificados de Qoricash (servicios, canales, SBS)
  2. Datos del módulo de mercado (TC actual, análisis diario)
  3. Noticias financieras disponibles en news_fetcher

Reglas de contenido:
  - No inventar cotizaciones ni cifras de clientes
  - Distinguir tasa referencial (BCRP) vs tasa Qoricash
  - Si faltan datos recientes: contenido educativo sin cifras actuales
  - Marcar datos de demostración con is_demo=True
"""

import json
import logging
import os
from datetime import datetime

log = logging.getLogger(__name__)

# ── Información verificada de Qoricash ───────────────────────────────────────
QORI_CONTEXT = """
SOBRE QORICASH
--------------
Qoricash es una casa de cambio digital peruana, registrada en el padrón de casas de
cambio de la SBS (Superintendencia de Banca, Seguros y AFP).

IMPORTANTE: No mencionar códigos de registro ni afirmaciones regulatorias específicas
sin que estén verificadas en el contexto de la pieza. "Registrada en la SBS" es
suficiente y verificable. No usar "Código 4801" en contenido de redes.

Servicios:
- Cambio de dólares (USD/PEN y PEN/USD) con tasa preferencial
- Operaciones para personas naturales y empresas
- Plataforma web (qoricash.pe) y atención vía WhatsApp (+51 910 624 404)
- Sin comisiones adicionales; el beneficio está en el tipo de cambio
- Tipo de cambio corporativo para empresas (spread menor, RUC verificado)

Diferencial frente a la banca:
- Tipo de cambio generalmente más competitivo que bancos locales
- Proceso 100% digital y seguro
- Registrada en el padrón SBS
- Disponible de lunes a sábado, horario extendido

Canales confirmados:
- qoricash.pe (web)
- WhatsApp: +51 910 624 404
- Instagram: @qoricash (verificar handle actual)
- LinkedIn: Qoricash

Lo que NO se debe afirmar sin datos actuales:
- Volumen de operaciones o número de clientes
- Premios o rankings
- Cotizaciones concretas sin verificar (usar "tasa del día" en su lugar)
"""

# ── Redes y sus formatos ──────────────────────────────────────────────────────
NETWORKS = {
    'linkedin':  {'label': 'LinkedIn',  'format': 'Publicación 1200×628'},
    'instagram': {'label': 'Instagram', 'format': 'Post cuadrado 1080×1080'},
    'facebook':  {'label': 'Facebook',  'format': 'Post horizontal 1200×628'},
    'reel':      {'label': 'Reel/TikTok', 'format': 'Guion 60s'},
}

# ── Temas de contenido para proponer automáticamente ─────────────────────────
TOPIC_IDEAS = [
    {'theme': 'educativo', 'tags': ['TC', 'finanzas', 'ahorro'],
     'angle': 'Por qué el tipo de cambio varía entre bancos y casas de cambio'},
    {'theme': 'educativo', 'tags': ['empresas', 'divisas'],
     'angle': 'Cómo las empresas optimizan sus cambios de moneda'},
    {'theme': 'educativo', 'tags': ['SBS', 'seguridad'],
     'angle': 'Qué significa estar regulado por la SBS'},
    {'theme': 'producto',  'tags': ['digital', 'proceso'],
     'angle': 'Cómo funciona Qoricash paso a paso'},
    {'theme': 'mercado',   'tags': ['USD', 'PEN', 'análisis'],
     'angle': 'Factores que mueven el dólar en Perú'},
    {'theme': 'producto',  'tags': ['corporativo', 'RUC'],
     'angle': 'Ventajas del tipo de cambio corporativo para empresas'},
    {'theme': 'educativo', 'tags': ['planificación', 'tesorería'],
     'angle': 'Cuándo es mejor momento para cambiar divisas'},
    {'theme': 'cultura',   'tags': ['fintech', 'Peru'],
     'angle': 'La transformación digital en los servicios financieros peruanos'},
]


def _get_market_context() -> dict:
    """Obtiene datos del módulo de mercado sin lanzar si falla."""
    try:
        from app.services.market.market_service import MarketService
        data = MarketService.get_dashboard_data()
        snap = data.get('snapshot') or {}
        analysis = data.get('daily_analysis') or {}
        return {
            'usdpen':    snap.get('usdpen'),
            'usdpen_chg': snap.get('usdpen_chg_pct'),
            'analysis_summary': analysis.get('summary', ''),
            'analysis_date':    analysis.get('generated_at', ''),
            'available': True,
        }
    except Exception as e:
        log.warning(f'[Content] market context no disponible: {e}')
        return {'available': False}


def _get_news_context(limit: int = 5) -> list[dict]:
    """Obtiene noticias recientes del fetcher."""
    try:
        from app.services.market.news_fetcher import fetch_all_news
        items = fetch_all_news()
        relevant = [
            n for n in items
            if n.get('impact_level') in ('high', 'medium')
        ][:limit]
        return [{'title': n['title'], 'source': n.get('source_name', ''),
                 'date': str(n.get('published_at', '')[:10] if n.get('published_at') else '')}
                for n in relevant]
    except Exception as e:
        log.warning(f'[Content] news context no disponible: {e}')
        return []


def _build_system_prompt() -> str:
    return f"""Eres el agente creativo de Qoricash, una fintech peruana de cambio de divisas.
Tu misión: generar propuestas de contenido para redes sociales que sean útiles, verídicas y con identidad de marca.

{QORI_CONTEXT}

REGLAS ESTRICTAS:
1. No inventes cifras de clientes, volúmenes ni rankings.
2. Diferencia explícitamente "tasa del BCRP (referencial)" de "tasa Qoricash (comercial)".
3. Si usas datos de mercado, cita la fecha y la fuente.
4. Si no hay datos recientes, produce contenido educativo sin cifras.
5. Marca con is_demo=true cualquier cifra hipotética usada como ejemplo.
6. El texto debe estar listo para publicar, en español peruano natural.
7. No uses emojis en exceso; 1-3 estratégicos si ayudan al tono.
"""


def generate_batch(n: int = 3, user_id: int = None) -> list[dict]:
    """
    Genera un lote de n propuestas usando Claude.
    Retorna lista de dicts listos para crear ContentProposal.
    """
    from app.services.ai.client import ask_json, SONNET

    market = _get_market_context()
    news   = _get_news_context()

    # Construir contexto de datos disponibles
    data_ctx = ''
    if market.get('available') and market.get('usdpen'):
        data_ctx += f'\nTIPO DE CAMBIO USD/PEN (tasa de mercado referencial): {market["usdpen"]}'
        if market.get('usdpen_chg'):
            data_ctx += f' ({market["usdpen_chg"]:+.2f}% hoy)'
        data_ctx += f'\nFecha del dato: {market.get("analysis_date", "hoy")}'
        if market.get('analysis_summary'):
            data_ctx += f'\nResumen de mercado: {market["analysis_summary"][:300]}'
    else:
        data_ctx += '\n(Sin datos de mercado en tiempo real disponibles — usar contenido educativo)'

    if news:
        data_ctx += '\n\nNOTICIAS FINANCIERAS RELEVANTES RECIENTES:'
        for item in news:
            data_ctx += f'\n- [{item["date"]}] {item["title"]} ({item["source"]})'

    today = datetime.now().strftime('%d de %B de %Y')

    prompt = f"""Fecha de hoy: {today}

DATOS DISPONIBLES:{data_ctx}

TEMAS SUGERIDOS (elige los más relevantes o propón variantes mejores):
{json.dumps([t['angle'] for t in TOPIC_IDEAS[:6]], ensure_ascii=False, indent=2)}

TAREA: Genera exactamente {n} propuestas de contenido para redes sociales de Qoricash.
Varía las redes: incluye al menos 1 LinkedIn, 1 Instagram o Facebook, 1 Reel.

Para cada propuesta responde con este JSON exacto:
{{
  "network": "linkedin|instagram|facebook|reel",
  "topic": "título de la pieza (máx 80 chars)",
  "objective": "objetivo de la publicación en una frase",
  "audience": "público objetivo (p.ej. empresas PYME, personas naturales, etc.)",
  "tag": "categoría de 1-2 palabras para el visual (p.ej. Tipo de Cambio, Educación, Fintech)",
  "text_body": "texto completo listo para publicar en esa red (con saltos de línea reales)",
  "body_lines": ["línea 1 para el visual", "línea 2 para el visual"],
  "visual_idea": "descripción de cómo debería verse la imagen o video",
  "cta": "llamada a la acción (máx 40 chars)",
  "hashtags": "#qoricash #tipodecambio ...",
  "sources": [{{"title": "fuente", "date": "YYYY-MM-DD"}}],
  "is_demo": false,
  "script_scenes": null,
  "flow_prompt": null
}}

Para propuestas de tipo "reel", reemplaza script_scenes y flow_prompt por:
"script_scenes": [
  {{"scene": 1, "duration": "0-5s", "text_screen": "texto en pantalla", "voice": "locución"}}
],
"flow_prompt": "prompt completo para Google Flow/Gemini Veo describiendo el video"

Responde con un array JSON de {n} objetos. Sin texto fuera del JSON.
"""

    system = _build_system_prompt()
    raw    = ask_json(prompt, system=system, model=SONNET, max_tokens=4096)

    # Normalizar: puede ser lista directa o dict con lista dentro
    if isinstance(raw, dict):
        proposals = raw.get('proposals') or raw.get('items') or list(raw.values())[0]
    else:
        proposals = raw

    if not isinstance(proposals, list):
        raise ValueError(f'Respuesta inesperada de Claude: {type(raw)}')

    return proposals[:n]


def adjust_proposal(proposal_id: int, adjustment: str) -> dict:
    """
    Pide al agente que ajuste una pieza existente según las instrucciones del usuario.
    Retorna dict con los campos actualizados (solo los que cambian).
    """
    from app.services.ai.client import ask_json, SONNET
    from app.models.content_proposal import ContentProposal

    p = ContentProposal.query.get_or_404(proposal_id)

    current = {
        'network':    p.network,
        'topic':      p.topic,
        'text_body':  p.text_body,
        'visual_idea': p.visual_idea,
        'cta':        p.cta,
        'hashtags':   p.hashtags,
    }
    if p.script_scenes:
        current['script_scenes'] = p.scenes_list

    prompt = f"""Propuesta original:
{json.dumps(current, ensure_ascii=False, indent=2)}

Instrucción del editor:
{adjustment}

Ajusta la propuesta según esa instrucción. Retorna SOLO los campos que cambian,
en el mismo formato JSON. No incluyas campos que no cambien.
Mantén todas las reglas de contenido (no inventar cifras, etc.)."""

    return ask_json(prompt, system=_build_system_prompt(), model=SONNET, max_tokens=2048)


def generate_single(network: str, topic_hint: str = '') -> dict:
    """Genera una sola propuesta para una red específica."""
    results = generate_batch(n=1)
    if results:
        r = results[0]
        if network:
            r['network'] = network
        return r
    return {}
