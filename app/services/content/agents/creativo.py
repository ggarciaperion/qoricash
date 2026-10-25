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

DIRECCIÓN VISUAL — LEE ESTO ANTES DE ESCRIBIR flow_prompt:
Cada pieza debe ser fotografía publicitaria real o composición conceptual fotorrealista, NO ilustración
corporativa ni infografía. La escena debe tener un protagonista claro y representar el beneficio de
forma concreta. Las tres piezas deben tener escenarios y composiciones DIFERENTES entre sí.

ESTRUCTURA OBLIGATORIA de cada flow_prompt (mín 100 palabras, listo para copiar en Gemini Imagen):
1. Tipo de pieza: "Fotografía publicitaria." o "Composición conceptual fotorrealista."
2. Sujeto y acción: persona real, edad aproximada, qué está haciendo, expresión natural.
3. Entorno: lugar concreto en Perú (barrio, ciudad, tipo de local), elementos del espacio.
4. Encuadre: plano y distribución (ej. "plano medio, sujeto izquierda 60%, espacio derecha 40%").
5. Luz: fuente, temperatura, atmósfera (ej. "luz natural lateral, mañana, sombras suaves").
6. Color de marca: cómo aparece #196BFE (Azul Qoricash) — en un objeto, prenda, detalle del entorno.
   NO tiñas toda la imagen. Permite colores naturales, pieles reales, materiales neutros.
7. Logo: "El logo Qoricash aparece como marca de agua discreta en esquina inferior derecha.
   El usuario debe proporcionar el archivo oficial al generador."
8. Formato: "1200×628 px horizontal (LinkedIn)."
9. Texto en imagen: solo si aporta valor — una frase breve en español. Si no aplica, omitir.
10. Exclusiones específicas: qué NO debe aparecer en esta pieza en particular.

PROHIBIDO en flow_prompt:
- Diagramas de flujo, íconos conectados, dashboards, tarjetas flotantes.
- Monedas, billetes o símbolos de dólar como decoración.
- Fondos tecnológicos (circuit-board, neón, hologramas).
- Piel plástica, sonrisas forzadas, fotografía corporativa genérica.
- Texto en inglés.
- Frases vagas como "estilo premium, moderno, innovador" sin describir la escena.

VARIEDAD: las 3 propuestas deben mostrar situaciones claramente distintas.
Alterna entre: persona en negocio / persona con teléfono en escena cotidiana /
viajero o importador / composición conceptual con materiales reales.

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
      "visual_idea": "descripción en 2-3 oraciones de la escena y el beneficio representado",
      "flow_prompt": "prompt autónomo ≥100 palabras siguiendo la estructura indicada, listo para copiar en Gemini Imagen",
      "advertencia": "limitación o null"
    }}
  ]
}}
Exactamente 3 propuestas. Solo JSON."""

    # Liberar la conexión DB antes de la llamada IA (puede tardar varios minutos).
    # benefits, prohibited y tone ya están en variables locales; brand.id se captura aquí.
    _brand_id = brand.id
    from app.extensions import db
    db.session.close()

    try:
        raw = ask_json(prompt, system=system, model=SONNET, max_tokens=4000)
        if isinstance(raw, list):
            propuestas = raw
        else:
            propuestas = raw.get('propuestas', [])
        return {
            'ok':         True,
            'propuestas': propuestas[:3],
            'brand_version': _brand_id,
            'mode':       'diario',
        }
    except Exception as e:
        log.error(f'[Creativo-diario] Claude error: {e}', exc_info=True)
        return {'ok': False, 'reason': f'Error del Creativo diario: {str(e)}', 'propuestas': []}
