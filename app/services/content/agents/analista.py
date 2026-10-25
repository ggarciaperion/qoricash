"""
Agente 2: Analista económico.

Recibe las fuentes del Investigador y elabora un análisis que:
- Separa hechos de interpretación.
- Evalúa el posible impacto en tipo de cambio, empresas y personas.
- NO garantiza movimientos del dólar.
- NO inventa cifras ni fuerza relaciones causales.

La interpretación es del agente; los hechos deben estar en las fuentes.
"""
import json
import logging

log = logging.getLogger(__name__)

SYSTEM = """Eres el Analista económico de Qoricash, una casa de cambio digital peruana.

Tu trabajo es analizar fuentes de información financiera y económica para:
1. Identificar hechos verificables.
2. Interpretar su posible impacto en el tipo de cambio USD/PEN, en empresas y en personas naturales.

REGLAS ESTRICTAS:
- Separa claramente HECHOS (lo que dicen las fuentes) de INTERPRETACIÓN (tu análisis).
- Nunca garantices movimientos del dólar. Usa "podría", "sugiere", "es posible que".
- Cita siempre la fuente de cada dato concreto que menciones.
- Si los datos son insuficientes, dilo explícitamente.
- No inventes cifras, no extrapoles sin datos.
- Distingue tasa referencial del BCRP de tasa comercial de mercado.
"""


def run(stage, pipeline):
    """
    Ejecuta el Analista.
    Lee las ContentSource del pipeline y produce un análisis estructurado.
    """
    from app.models.content_pipeline import ContentSource
    from app.services.ai.client import ask_json, SONNET

    # Recuperar fuentes del Investigador (stage anterior)
    sources = ContentSource.query.filter_by(
        pipeline_id=pipeline.id,
        used_in_analysis=True
    ).all()

    if not sources:
        return {
            'ok':      False,
            'reason':  'Sin fuentes disponibles. El Investigador debe completarse primero.',
            'analisis': None,
        }

    # Construir contexto con las fuentes
    ctx_parts = []
    for i, s in enumerate(sources[:10], 1):
        ctx_parts.append(
            f'[Fuente {i}] {s.source_name} ({s.published_at or "fecha n/d"})\n'
            f'Título: {s.title}\n'
            f'Contenido: {(s.excerpt or "")[:400]}\n'
            + (f'URL: {s.url}' if s.url else '')
        )
    context = '\n---\n'.join(ctx_parts)

    prompt = f"""Analiza las siguientes fuentes de información financiera:

{context}

Devuelve un objeto JSON con esta estructura exacta:
{{
  "resumen_ejecutivo": "2-3 oraciones que resumen la situación actual",
  "hechos": [
    {{"hecho": "descripción del hecho", "fuente": "nombre de la fuente", "fecha": "YYYY-MM-DD"}}
  ],
  "interpretacion": [
    {{"punto": "interpretación o implicación", "certeza": "alta|media|baja", "nota": "limitación o advertencia"}}
  ],
  "impacto_tc": "análisis del posible efecto en USD/PEN, con 'podría/sugiere/es posible'",
  "impacto_empresas": "relevancia para empresas que cambian divisas",
  "impacto_personas": "relevancia para personas naturales",
  "temas_para_contenido": ["tema 1", "tema 2", "tema 3"],
  "datos_sin_verificar": ["dato o afirmación que necesita verificación adicional"],
  "advertencia": "si los datos son insuficientes o hay limitaciones importantes"
}}
Solo JSON, sin texto adicional."""

    try:
        result = ask_json(prompt, system=SYSTEM, model=SONNET, max_tokens=2500)
        # Si Claude devuelve una lista, tomar el primer elemento dict
        if isinstance(result, list):
            result = next((item for item in result if isinstance(item, dict)), {})
        if not isinstance(result, dict):
            raise ValueError(f'Respuesta no es dict: {type(result)}')
        result.setdefault('ok', True)
        result['source_count'] = len(sources)
        result['sources_used'] = [{'title': s.title, 'url': s.url, 'source': s.source_name}
                                   for s in sources[:10]]
        return result
    except Exception as e:
        log.error(f'[Analista] Claude error: {e}', exc_info=True)
        return {
            'ok':    False,
            'reason': f'Error del agente analista: {str(e)}',
            'analisis': None,
        }
