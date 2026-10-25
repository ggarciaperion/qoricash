"""
Agente 3: Creativo comercial.

Propone campañas e ideas usando ÚNICAMENTE los beneficios verificados
en la ficha de marca (BrandConfig).

REGLAS ESTRICTAS:
- Solo usa beneficios de BrandConfig.benefits_list.
- Nunca inventa cifras de clientes, testimonios, comparaciones sin datos o
  funcionalidades inexistentes.
- Marca como prohibido cualquier afirmación en BrandConfig.claims_list.
- Indica explícitamente qué beneficio verificado sustenta cada propuesta.
"""
import json
import logging

log = logging.getLogger(__name__)

SYSTEM_BASE = """Eres el Creativo comercial de Qoricash, una casa de cambio digital peruana.

Tu trabajo es proponer ideas de campaña para redes sociales usando ÚNICAMENTE
los beneficios verificados de la marca que se te proporcionan.

REGLAS ABSOLUTAS:
1. Solo comunicas beneficios que aparecen en la lista de beneficios verificados.
2. No inventas cifras de clientes, volúmenes, premios ni testimonios.
3. No haces comparaciones directas con bancos o competidores sin datos del día.
4. No garantizas ningún tipo de cambio ni rentabilidad.
5. Si un ángulo requeriría una afirmación no verificada, dilo y propón uno alternativo.
6. Distingue siempre entre tasa referencial del BCRP y tasa comercial de Qoricash.
"""


def run(stage, pipeline):
    """
    Ejecuta el Creativo comercial.
    En modo 'diario': 3 propuestas independientes con audiencia rotativa y prompt visual.
    En modo estándar: 4 ideas de campaña para distintas redes.
    """
    if pipeline.type == 'diario':
        return _run_diario(stage, pipeline)

    from app.models.content_pipeline import BrandConfig
    from app.services.ai.client import ask_json, SONNET

    brand = BrandConfig.get_current()

    benefits = brand.benefits_list
    prohibited = brand.claims_list
    tone = brand.tone_guide or 'Natural, profesional, español peruano.'

    if not benefits:
        return {
            'ok':    False,
            'reason': 'La ficha de marca no tiene beneficios verificados. '
                      'Configure la ficha en Configuración antes de usar el Creativo.',
            'ideas': [],
        }

    system = SYSTEM_BASE + f'\n\nTONO: {tone}'

    prompt = f"""BENEFICIOS VERIFICADOS DE QORICASH (puedes usar estos y solo estos):
{json.dumps(benefits, ensure_ascii=False, indent=2)}

AFIRMACIONES PROHIBIDAS (no uses estas bajo ninguna circunstancia):
{json.dumps(prohibited, ensure_ascii=False, indent=2)}

TAREA: Propón 4 ideas de campaña para redes sociales de Qoricash.
Varía las redes: LinkedIn (empresas), Instagram (personas), Facebook (general), Reel/TikTok (jóvenes).

Para cada idea devuelve JSON:
{{
  "red": "linkedin|instagram|facebook|reel",
  "angulo": "enfoque principal de la pieza",
  "beneficio_utilizado": "el beneficio verificado exacto que justifica esta propuesta",
  "titular": "titular de la publicación (máx 80 chars)",
  "gancho": "primera línea o apertura (máx 100 chars)",
  "cta": "llamada a la acción (máx 40 chars)",
  "publico_objetivo": "a quién va dirigido",
  "tono": "formal|cercano|educativo|inspiracional",
  "advertencia": "si hay alguna limitación en esta propuesta (o null)"
}}

Responde con un array JSON de 4 objetos. Sin texto adicional."""

    try:
        raw = ask_json(prompt, system=system, model=SONNET, max_tokens=2500)
        if isinstance(raw, dict):
            ideas = raw.get('ideas') or list(raw.values())[0] if raw else []
        else:
            ideas = raw if isinstance(raw, list) else []

        return {
            'ok':    True,
            'ideas': ideas[:4],
            'brand_version': brand.id,
            'benefits_used': benefits,
        }
    except Exception as e:
        log.error(f'[Creativo] Claude error: {e}', exc_info=True)
        return {
            'ok':    False,
            'reason': f'Error del agente creativo: {str(e)}',
            'ideas': [],
        }


# ── Modo diario ───────────────────────────────────────────────────────────────

# Audiencias rotativas — el día del mes determina cuál toca
_AUDIENCIAS_ROTA = [
    ('empresas importadoras y exportadoras', 'linkedin'),
    ('personas naturales que cambian divisas', 'linkedin'),
    ('emprendedores y pymes con operaciones en dólares', 'linkedin'),
]


def _run_diario(stage, pipeline):
    """
    Creativo en modo diario.
    Genera exactamente 3 propuestas comerciales independientes:
    - Cada una para una audiencia diferente (rotación por día del mes)
    - Cada una incluye visual_prompt para Gemini/Flow
    - Texto listo para LinkedIn (80-140 palabras)
    """
    from app.models.content_pipeline import BrandConfig
    from app.services.ai.client import ask_json, SONNET
    from datetime import datetime

    brand    = BrandConfig.get_current()
    benefits = brand.benefits_list
    prohibited = brand.claims_list
    tone     = brand.tone_guide or 'Natural, profesional, español peruano.'

    if not benefits:
        return {'ok': False, 'reason': 'Ficha de marca sin beneficios. Configure en Configuración.',
                'propuestas': []}

    # Audiencias del día (rotación circular basada en día del mes)
    hoy = datetime.now().day
    audiencias = [_AUDIENCIAS_ROTA[(hoy + i) % 3] for i in range(3)]

    audiencias_str = '\n'.join(
        f'{i+1}. Audiencia: "{aud}" | Red principal: {red}'
        for i, (aud, red) in enumerate(audiencias)
    )

    system = SYSTEM_BASE + f'\n\nTONO: {tone}'

    prompt = f"""BENEFICIOS VERIFICADOS DE QORICASH:
{json.dumps(benefits, ensure_ascii=False, indent=2)}

AFIRMACIONES PROHIBIDAS:
{json.dumps(prohibited, ensure_ascii=False, indent=2)}

TAREA: Genera 3 propuestas comerciales INDEPENDIENTES para LinkedIn, una por audiencia:

{audiencias_str}

Para cada propuesta, incluye un prompt detallado para generar la imagen en Gemini/Imagen o Google Flow.
El prompt visual debe describir: composición, colores de marca (Teal #00DEA8, Navy #0D1B2A, blanco),
elementos gráficos, tipografía y qué debe transmitir la imagen.

Devuelve un JSON con estructura:
{{
  "propuestas": [
    {{
      "audiencia": "descripción de la audiencia",
      "angulo": "enfoque principal de esta pieza",
      "beneficio_utilizado": "el beneficio verificado exacto que sustenta esta propuesta",
      "topic": "titular en máx 80 chars",
      "text_body": "texto LinkedIn 80-140 palabras con \\n para párrafos",
      "cta": "llamada a la acción (máx 40 chars)",
      "hashtags": "#qoricash #tipodecambio ...",
      "visual_idea": "descripción en 2-3 oraciones de qué mostrar visualmente",
      "flow_prompt": "prompt completo y detallado para Gemini Imagen/Flow (mín 80 palabras): composición, colores, elementos, ambiente, texto en imagen si aplica",
      "advertencia": "limitación o null"
    }}
  ]
}}
Exactamente 3 propuestas. Solo JSON."""

    try:
        raw = ask_json(prompt, system=system, model=SONNET, max_tokens=4000)
        if isinstance(raw, list):
            propuestas = raw
        else:
            propuestas = raw.get('propuestas', [])
        return {
            'ok':         True,
            'propuestas': propuestas[:3],
            'brand_version': brand.id,
            'mode':       'diario',
        }
    except Exception as e:
        log.error(f'[Creativo-diario] Claude error: {e}', exc_info=True)
        return {'ok': False, 'reason': f'Error del Creativo diario: {str(e)}', 'propuestas': []}
