"""
Agente 4: Editor de redes.

Adapta el análisis (Analista) o las propuestas (Creativo) al formato exacto
de cada red social: LinkedIn, Instagram, Facebook, Reel/TikTok.

Entrega textos completos, titulares y llamadas a la acción listos para usar.
No genera imágenes — eso es responsabilidad del Productor.
"""
import json
import logging

log = logging.getLogger(__name__)

SYSTEM = """Eres el Editor de redes de Qoricash, una casa de cambio digital peruana.

Recibes análisis económico o ideas de campaña y las adaptas al formato exacto
de cada red social con textos completos, titulares y CTAs listos para publicar.

FORMATOS:
- LinkedIn (1200×628): texto formal 150-300 palabras, 3-5 hashtags profesionales.
- Instagram (1080×1080): texto breve 80-150 palabras, 8-12 hashtags variados, emojis moderados.
- Facebook (1200×628): texto conversacional 100-200 palabras, 3-5 hashtags.
- Reel/TikTok (1080×1920): guion por escenas de 30-60 segundos.

REGLAS:
- Español peruano natural. Máximo 2 emojis estratégicos.
- Siempre distingue tasa BCRP (referencial) de tasa Qoricash (comercial).
- No inventas datos que no están en la entrada.
- El texto debe estar listo para publicar, sin placeholders.
"""


def run(stage, pipeline, input_type='analista'):
    """
    Ejecuta el Editor.

    input_type: 'analista'     — lee output del Analista
                'creativo'     — lee output del Creativo
                'investigador' — modo diario: 3 posts LinkedIn 80-140 palabras
    """
    if input_type == 'investigador':
        return _run_diario(stage, pipeline)

    from app.models.content_pipeline import PipelineStage
    from app.services.ai.client import ask_json, SONNET

    # Leer output de la etapa anterior
    prev_stage = PipelineStage.query.filter_by(
        pipeline_id=pipeline.id,
        agent_role=input_type,
    ).first()

    if not prev_stage or not prev_stage.output_data:
        return {
            'ok':    False,
            'reason': f'No hay output del agente {input_type} para esta etapa.',
            'piezas': [],
        }

    prev_output = prev_stage.output_dict

    if input_type == 'analista':
        entrada_ctx = _build_analista_context(prev_output)
        tipo_contenido = 'análisis económico de actualidad'
    else:
        entrada_ctx = _build_creativo_context(prev_output)
        tipo_contenido = 'propuesta comercial de Qoricash'

    prompt = f"""Tienes el siguiente {tipo_contenido}:

{entrada_ctx}

Adapta este contenido a CUATRO formatos de redes sociales para Qoricash.
Devuelve un JSON con esta estructura:
{{
  "linkedin": {{
    "topic": "título de la publicación",
    "tag": "categoría en 1-2 palabras",
    "text_body": "texto completo listo para publicar (saltos de línea reales con \\n)",
    "cta": "llamada a la acción (máx 40 chars)",
    "hashtags": "#qoricash #tipodecambio ...",
    "audience": "a quién va dirigido",
    "objective": "objetivo de la pieza"
  }},
  "instagram": {{ ... mismo esquema ... }},
  "facebook": {{ ... mismo esquema ... }},
  "reel": {{
    "topic": "título del reel",
    "tag": "REEL",
    "text_body": "descripción para caption de Instagram/TikTok",
    "cta": "llamada a la acción",
    "hashtags": "#qoricash ...",
    "audience": "a quién va dirigido",
    "objective": "objetivo",
    "script_scenes": [
      {{"scene": 1, "duration": "0-5s", "text_screen": "texto en pantalla", "voice": "locución"}}
    ],
    "flow_prompt": "prompt completo para Google Flow/Gemini Veo describiendo el video en detalle"
  }}
}}
Solo JSON sin texto adicional."""

    try:
        result = ask_json(prompt, system=SYSTEM, model=SONNET, max_tokens=4000)
        if not isinstance(result, dict):
            raise ValueError(f'Resultado inesperado: {type(result)}')

        # Normalizar: asegurar que cada red tiene sus campos
        piezas = []
        for red in ('linkedin', 'instagram', 'facebook', 'reel'):
            if red in result:
                piece = result[red]
                piece['network'] = red
                piezas.append(piece)

        return {
            'ok':       True,
            'piezas':   piezas,
            'input_type': input_type,
            'raw':      result,
        }
    except Exception as e:
        log.error(f'[Editor] Claude error: {e}', exc_info=True)
        return {
            'ok':    False,
            'reason': f'Error del agente editor: {str(e)}',
            'piezas': [],
        }


def _build_analista_context(data: dict) -> str:
    parts = []
    if data.get('resumen_ejecutivo'):
        parts.append(f'RESUMEN: {data["resumen_ejecutivo"]}')
    if data.get('hechos'):
        hechos = '\n'.join(f'- {h.get("hecho","")} ({h.get("fuente","")}, {h.get("fecha","")})'
                           for h in data['hechos'][:5])
        parts.append(f'HECHOS VERIFICADOS:\n{hechos}')
    if data.get('impacto_tc'):
        parts.append(f'IMPACTO EN TIPO DE CAMBIO: {data["impacto_tc"]}')
    if data.get('impacto_empresas'):
        parts.append(f'IMPACTO EN EMPRESAS: {data["impacto_empresas"]}')
    if data.get('impacto_personas'):
        parts.append(f'IMPACTO EN PERSONAS: {data["impacto_personas"]}')
    if data.get('temas_para_contenido'):
        parts.append(f'TEMAS SUGERIDOS: {", ".join(data["temas_para_contenido"][:3])}')
    return '\n\n'.join(parts)


def _run_diario(stage, pipeline):
    """
    Editor en modo diario.
    Lee las noticias categorizadas del Investigador (1 por categoría) y escribe
    un post LinkedIn de 80-140 palabras por cada una.
    Itera sobre `categorized` (dict cat→noticia), NO sobre `sources` list,
    para garantizar exactamente una noticia por categoría sin repetición.
    """
    from app.models.content_pipeline import PipelineStage
    from app.services.ai.client import ask_json, SONNET

    inv_stage = PipelineStage.query.filter_by(
        pipeline_id=pipeline.id,
        agent_role='investigador',
    ).first()
    if not inv_stage or not inv_stage.output_data:
        return {'ok': False, 'reason': 'No hay output del Investigador.', 'posts': []}

    inv_out = inv_stage.output_dict
    # `categorized` es el dict definitivo {categoria: noticia_dict} generado por el Investigador.
    # Cada clave aparece UNA SOLA VEZ. No usar sources[:3] (puede repetir categorías).
    categorized = inv_out.get('categorized', {})

    if not categorized:
        return {'ok': False, 'reason': 'El Investigador no produjo noticias categorizadas.', 'posts': []}

    CAT_LABEL = {
        'nacional':      'Economía nacional (Perú)',
        'internacional': 'Internacional',
        'mercados':      'Mercados y tipo de cambio',
    }
    ORDEN = ['nacional', 'internacional', 'mercados']

    # Construir contexto estrictamente por categoría, en orden definido
    noticias_ctx = []
    cats_disponibles = []
    for cat in ORDEN:
        if cat not in categorized:
            continue
        noticia = categorized[cat]
        cats_disponibles.append(cat)
        label = CAT_LABEL.get(cat, cat.title())
        fecha = noticia.get('fecha', noticia.get('published', ''))
        fuente = noticia.get('source', noticia.get('fuente_nombre', ''))
        url = noticia.get('url', noticia.get('fuente_url', ''))
        titulo = noticia.get('title', noticia.get('titulo', ''))
        resumen = noticia.get('summary', noticia.get('resumen', titulo))[:500]
        nota_tc = ''
        if cat == 'mercados':
            nota_tc = '\nNOTA: Este dato corresponde al ÚLTIMO CIERRE de la sesión bursátil. No es un precio en tiempo real.'
        noticias_ctx.append(
            f'CATEGORÍA: {cat} — {label}\n'
            f'Título: {titulo}\n'
            f'Resumen: {resumen}{nota_tc}\n'
            f'Fuente: {fuente}  |  Fecha: {fecha}  |  URL: {url}'
        )

    if not noticias_ctx:
        return {'ok': False, 'reason': 'Categorized vacío: sin noticias para procesar.', 'posts': []}

    context = '\n\n---\n\n'.join(noticias_ctx)
    n_posts = len(noticias_ctx)

    SYSTEM_DIARIO = """Eres el Editor LinkedIn de Qoricash, una casa de cambio digital peruana.

Tu tarea es transformar noticias económicas en posts de LinkedIn de 80 a 140 palabras.

REGLAS CRÍTICAS — SEGUIR AL PIE DE LA LETRA:
- Escribe ÚNICAMENTE sobre la noticia que se te da en cada bloque CATEGORÍA.
- PROHIBIDO introducir temas, eventos, criptomonedas, índices o datos que NO estén en el bloque.
- Si la noticia menciona USD/PEN, usa el valor exacto proporcionado y aclara que es el último cierre.
- NO predices movimientos del dólar. Usas "podría", "sugiere", "se observó".
- Exactamente 80-140 palabras por post (cuenta las palabras).
- Párrafos cortos, lenguaje profesional pero accesible. Español peruano natural.
- Máximo 1 emoji por post.
- Termina con una pregunta o reflexión breve que invite al diálogo.
- NO incluyas hashtags dentro del text_body.
"""

    cats_str = ', '.join(cats_disponibles)
    prompt = f"""Transforma estas {n_posts} noticias en posts LinkedIn para Qoricash.
Categorías disponibles: {cats_str}

{context}

Devuelve un JSON con este formato exacto:
{{
  "posts": [
    {{
      "categoria": "{cats_disponibles[0] if cats_disponibles else 'nacional'}",
      "topic": "titular en máx 80 chars",
      "text_body": "post completo 80-140 palabras (saltos reales con \\n)",
      "cta": "pregunta o reflexión final (máx 60 chars)",
      "hashtags": "#qoricash #tipodecambio ...",
      "fuente_nombre": "nombre del medio tal como aparece en Fuente",
      "fuente_url": "URL de la noticia tal como aparece en URL",
      "fecha_publicacion": "fecha tal como aparece en Fecha"
    }}
  ]
}}
Un post por categoría, en el mismo orden que los bloques: {cats_str}.
Solo JSON, sin texto adicional."""

    try:
        result = ask_json(prompt, system=SYSTEM_DIARIO, model=SONNET, max_tokens=3000)
        if isinstance(result, list):
            posts = result
        else:
            posts = result.get('posts', [])

        # Forzar categoria correcta por posición (por si el modelo la cambia)
        for i, post in enumerate(posts):
            if i < len(cats_disponibles):
                post['categoria'] = cats_disponibles[i]
                # Rellenar atribución desde categorized si el modelo lo omitió
                noticia = categorized[cats_disponibles[i]]
                if not post.get('fuente_nombre'):
                    post['fuente_nombre'] = noticia.get('source', noticia.get('fuente_nombre', ''))
                if not post.get('fuente_url'):
                    post['fuente_url'] = noticia.get('url', noticia.get('fuente_url', ''))
                if not post.get('fecha_publicacion'):
                    post['fecha_publicacion'] = noticia.get('fecha', noticia.get('published', ''))

        return {
            'ok':               True,
            'posts':            posts[:n_posts],
            'cats_disponibles': cats_disponibles,
            'mode':             'diario',
        }
    except Exception as e:
        log.error(f'[Editor-diario] Claude error: {e}', exc_info=True)
        return {'ok': False, 'reason': f'Error del Editor diario: {str(e)}', 'posts': []}


def _build_creativo_context(data: dict) -> str:
    parts = []
    ideas = data.get('ideas', [])
    if ideas:
        parts.append('IDEAS DE CAMPAÑA APROBADAS:')
        for i, idea in enumerate(ideas[:4], 1):
            parts.append(
                f'{i}. [{idea.get("red","").upper()}] {idea.get("angulo","")}\n'
                f'   Beneficio: {idea.get("beneficio_utilizado","")}\n'
                f'   Titular: {idea.get("titular","")}\n'
                f'   Gancho: {idea.get("gancho","")}\n'
                f'   CTA: {idea.get("cta","")}'
            )
    return '\n'.join(parts)
