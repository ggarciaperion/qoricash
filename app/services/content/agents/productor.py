"""
Agente 5: Productor visual y audiovisual.

Reutiliza las plantillas gráficas existentes para generar imágenes y carruseles
descargables. Prepara paquetes para herramientas externas (Flow, Gemini, Canva).

ACLARACIONES HONESTAS:
- Las imágenes son PNG generados con Pillow (no Canva, no IA generativa de imágenes).
- Los prompts de Flow/Gemini son para que el usuario los use externamente.
- Un carrusel = ZIP de varios PNG, no un archivo nativo de ninguna plataforma.
- El Productor NO genera videos; prepara el guion técnico y el prompt.
"""
import json
import logging
import os
import io
import zipfile
from pathlib import Path

log = logging.getLogger(__name__)

# Sistema de dirección visual compartido entre _run_diario y el comando CLI de relleno.
SYSTEM_DV = """Eres el Director Visual de Qoricash, casa de cambio digital peruana.

OBJETIVO: Cada pieza debe transmitir una acción financiera concreta relacionada con
Qoricash: cotizar soles y dólares, cambiar por WhatsApp, pagar proveedores en divisas
o preparar el cambio de moneda para un viaje. Una persona feliz o un negocio atractivo
no es suficiente si no se entiende qué servicio ofrece Qoricash.

═══ PIEZAS COMERCIALES ═══

TECNOLOGÍA CON PROPÓSITO:
- El teléfono es protagonista visual cuando el servicio se hace por WhatsApp.
  Si no aporta al mensaje, no lo incluyas.
- Pantallas: nunca inventes tasas, saldos ni importes. Si se necesita una interfaz
  legible, escribe: «Pantalla reservada — adjuntar captura aprobada en Canva».
- Prohibido: hologramas, neón, diagramas, tarjetas flotantes, dashboards inventados,
  íconos conectados, monedas/billetes flotantes, fondos circuit-board.

VARIEDAD — nunca la misma escena entre las tres piezas del día:
- WhatsApp/cotización: primer plano del teléfono con conversación en curso; persona
  y entorno aportan contexto pero no son el sujeto principal.
- Empresas/proveedores: emprendedor en su local con el producto visible; teléfono
  como herramienta de trabajo, no como protagonista.
- Viajes: composición con teléfono, pasaporte y equipaje que transmita preparación
  del cambio de moneda.
- Otras: composición conceptual, macro de detalle u escena cotidiana distinta.

COMPOSICIÓN — describir SIEMPRE estos nueve elementos:
1. Protagonista: qué objeto/persona es el centro visual y qué está haciendo.
2. Posición y proporción: «teléfono ocupa tercio central, inclinado 15°» /
   «persona izquierda 55%, espacio negativo derecha 45%».
3. Titular: texto exacto en español, sans serif limpia (Qoricash oficial si disponible),
   tamaño relativo, posición (ej. esquina superior derecha, centro inferior), color.
4. Jerarquía: titular principal > apoyo opcional > hashtag/CTA > logo.
5. Logo Qoricash: marca de agua, esquina inferior derecha; adjuntar archivo oficial.
6. Márgenes seguros: 40 px en todos los bordes para que nada quede cortado.
7. Contraste: fondo/texto con relación ≥ 4.5:1 para lectura en móvil.
8. Instrucción Canva: si el generador de IA no renderiza bien texto o logo, añadir:
   «Generar base sin texto; añadir titular y logo en Canva».
9. Color de marca: #196BFE en un elemento concreto (prenda, mueble, pantalla, detalle).
   Nunca tiñas toda la imagen. Materiales naturales y tonos neutros en el resto.

═══ NOTICIAS — DIRECCIÓN EDITORIAL ═══

- La imagen representa el ACONTECIMIENTO ESPECÍFICO, no un símbolo genérico.
- Elemento central directamente relacionado con la noticia (objeto, lugar, persona).
- Titular breve y factual; fuente y fecha previstas en diseño o copy.
- Solo relaciona con dólar o tipo de cambio cuando exista fundamento real.
- No inventes cifras, gráficas documentales ni fotografías de hechos reales.
  Escenas sintéticas → ilustración conceptual, nunca fotografía documental.

═══ ESTRUCTURA OBLIGATORIA DE CADA flow_prompt (≥120 palabras) ═══
Debe ser autónomo para copiar en Gemini Imagen o Google Flow:

1. Mensaje al espectador: qué debe entender en 3 segundos.
2. Concepto y escena: acción, protagonista, entorno específico en Perú.
3. Composición: posiciones, proporciones, plano fotográfico.
4. Iluminación y materiales: fuente, temperatura, texturas.
5. Colores y marca: dónde y cómo aparece #196BFE.
6. Texto exacto: titular, apoyo, tipografía, ubicación y color.
7. Logo y recursos: posición, instrucción Canva si aplica.
8. Formato: dimensiones px, márgenes de seguridad.
9. Exclusiones específicas para esta pieza en particular.

PROHIBIDO en cualquier pieza: adjetivos vacíos sin traducción visual concreta
("premium", "moderno", "tecnológico", "innovador")."""


def _noticia_fallback_prompt(cat: str, topic: str, text_preview: str) -> str:
    """
    Prompt visual mínimo para noticias cuando el agente de prompts falla.
    Sigue la misma estructura de 9 puntos que SYSTEM_DV.
    Garantiza que flow_prompt nunca quede vacío en propuestas de noticias.
    """
    concepto = {
        'nacional':      ('Ilustración conceptual editorial: espacio de trabajo contemporáneo '
                          'en Lima, persona adulta leyendo documento o pantalla relacionada '
                          'con economía o finanzas peruanas, expresión concentrada'),
        'internacional': ('Ilustración conceptual editorial: persona frente a pantalla con '
                          'mapa o indicadores internacionales, entorno neutro de oficina, '
                          'no construir foto documental de ningún hecho real'),
        'mercados':      ('Ilustración conceptual editorial: persona revisando gráfica '
                          'de tipo de cambio en pantalla o tablet, espacio de trabajo '
                          'financiero en Lima, luz de mañana'),
    }.get(cat, 'Ilustración conceptual editorial de actualidad económica, Lima')
    titular_sugerido = topic[:60] if topic else 'Actualidad económica'
    return (
        f'Mensaje al espectador: informarse sobre "{titular_sugerido}" en 3 segundos. '
        f'Concepto y escena: {concepto}. '
        f'Composición: protagonista centrado o en tercio izquierdo (60%), '
        f'espacio derecho (40%) disponible para titular; plano medio o americano. '
        f'Iluminación: luz natural lateral, temperatura cálida-neutra 4000 K, '
        f'sombras suaves, fondo desenfocado con bokeh sutil. '
        f'Color de marca: #196BFE aparece en un detalle menor — carpeta, taza, '
        f'indicador de pantalla — nunca tiñas toda la imagen; '
        f'colores naturales, pieles reales, materiales neutros en el resto. '
        f'Texto en imagen: titular breve "{titular_sugerido}" en sans serif limpia, '
        f'blanco sobre zona oscura o con sombra difusa, esquina inferior izquierda; '
        f'fuente en texto pequeño debajo. Generar base sin texto si la IA deforma letras; '
        f'añadir titular en Canva. '
        f'Logo Qoricash: marca de agua discreta, esquina inferior derecha; '
        f'adjuntar archivo oficial al generador. '
        f'Formato: 1200×628 px horizontal (LinkedIn), márgenes seguros 40 px. '
        f'Exclusiones: sin monedas flotantes, sin íconos conectados, sin dashboards, '
        f'sin texto en inglés, sin fotografías documentales de personas o eventos reales, '
        f'sin fondo neón o circuit-board.'
    )


def run(stage, pipeline):
    """
    Ejecuta el Productor / Director Visual.
    En modo 'diario': genera prompts Gemini/Flow para 6 piezas (sin Pillow).
    En modo estándar: genera imágenes Pillow + ContentProposal records.
    """
    if pipeline.type == 'diario':
        return _run_diario(stage, pipeline)

    from app.models.content_pipeline import PipelineStage
    from app.models.content_proposal import ContentProposal, ContentBatch
    from app.services.content.image_service import render_and_save
    from app.extensions import db
    from app.utils.formatters import now_peru

    editor_stage = PipelineStage.query.filter_by(
        pipeline_id=pipeline.id,
        agent_role='editor',
    ).first()

    if not editor_stage or not editor_stage.output_data:
        return {
            'ok':    False,
            'reason': 'El Editor no ha completado su etapa.',
            'proposals': [],
        }

    editor_out = editor_stage.output_dict
    piezas = editor_out.get('piezas', [])

    if not piezas:
        return {
            'ok':    False,
            'reason': 'El Editor no produjo piezas para este pipeline.',
            'proposals': [],
        }

    # Crear batch vinculado al pipeline
    batch = ContentBatch(
        created_by   = pipeline.created_by,
        count        = len(piezas),
        model_used   = 'pipeline',
        notes        = f'Pipeline #{pipeline.id} — {pipeline.title or pipeline.type}',
    )
    db.session.add(batch)
    db.session.flush()

    proposals_created = []
    packs_generated   = []

    for pieza in piezas:
        red = pieza.get('network', 'linkedin')
        try:
            p = ContentProposal(
                batch_id     = batch.id,
                network      = red,
                topic        = pieza.get('topic', ''),
                tag          = pieza.get('tag', ''),
                objective    = pieza.get('objective', ''),
                audience     = pieza.get('audience', ''),
                text_body    = pieza.get('text_body', ''),
                cta          = pieza.get('cta', ''),
                hashtags     = pieza.get('hashtags', ''),
                visual_idea  = pieza.get('visual_idea', ''),
                status       = 'borrador',
                is_demo      = False,
            )
            # Fuentes del pipeline
            sources = _collect_pipeline_sources(pipeline)
            if sources:
                p.sources = json.dumps(sources, ensure_ascii=False)

            # Script de reel
            if red == 'reel':
                scenes = pieza.get('script_scenes', [])
                if scenes:
                    p.script_scenes = json.dumps(scenes, ensure_ascii=False)
                if pieza.get('flow_prompt'):
                    p.flow_prompt = pieza['flow_prompt']

            db.session.add(p)
            db.session.flush()

            # Generar imagen
            img_path = render_and_save(p)
            if img_path:
                p.image_path   = img_path
                p.image_format = 'png'

            proposals_created.append({
                'proposal_id': p.id,
                'network':     red,
                'topic':       p.topic,
                'image':       img_path,
            })

            # Paquete para herramienta externa si es reel
            if red == 'reel' and p.flow_prompt:
                pack = _build_video_pack(p)
                packs_generated.append(pack)

        except Exception as e:
            log.warning(f'[Productor] pieza {red} fallida: {e}')
            proposals_created.append({'network': red, 'error': str(e)})

    db.session.commit()

    # Generar carrusel (ZIP de imágenes) para la sesión
    carousel_path = _make_carousel_zip(pipeline.id, proposals_created)

    return {
        'ok':           True,
        'proposals':    proposals_created,
        'batch_id':     batch.id,
        'carousel_zip': carousel_path,
        'packs':        packs_generated,
        'note':         (
            'Imágenes generadas localmente con Pillow (formato de marca). '
            'Para video, usa el paquete Flow en cada pieza Reel. '
            'Para diseño personalizado, descarga las referencias e impórtalas en Canva.'
        ),
    }


def _collect_pipeline_sources(pipeline) -> list:
    from app.models.content_pipeline import ContentSource
    srcs = ContentSource.query.filter_by(pipeline_id=pipeline.id).all()
    return [
        {'title': s.title, 'url': s.url or '', 'date': s.published_at or '',
         'source': s.source_name}
        for s in srcs[:5]
    ]


def _build_video_pack(proposal) -> dict:
    """Prepara el paquete de video para herramienta externa."""
    return {
        'proposal_id': proposal.id,
        'tool':        'Google Flow / Gemini Veo / CapCut',
        'format':      '1080×1920 px (9:16) — vertical para Reel/TikTok',
        'duration':    '30-60 segundos',
        'flow_prompt': proposal.flow_prompt,
        'instructions': (
            '1. Copia el prompt en Google Flow o Gemini Veo.\n'
            '2. Ajusta colores a: Teal #00DEA8, Navy #0D1B2A.\n'
            '3. Agrega el logo Qoricash en la última escena.\n'
            '4. Exporta en MP4 1080×1920.\n'
            '5. Sube el archivo en "Cargar resultado" para continuar a revisión.'
        ),
        'cover_image': proposal.image_path,
        'script_scenes': proposal.scenes_list,
        'upload_endpoint': f'/contenido/api/propuesta/{proposal.id}/cargar-recurso',
    }


def _run_diario(stage, pipeline):
    """
    Director Visual en modo diario.
    Lee outputs del Editor (3 posts) y Creativo (3 propuestas),
    genera prompts Gemini/Flow enriquecidos para cada pieza,
    y crea los 6 ContentProposal records con resource_status='prompt_listo'.
    NO genera imágenes Pillow.
    """
    from app.models.content_pipeline import PipelineStage
    from app.models.content_proposal import ContentProposal, ContentBatch
    from app.services.ai.client import ask_json, SONNET
    from app.extensions import db

    editor_stage   = PipelineStage.query.filter_by(pipeline_id=pipeline.id, agent_role='editor').first()
    creativo_stage = PipelineStage.query.filter_by(pipeline_id=pipeline.id, agent_role='creativo').first()
    inv_stage      = PipelineStage.query.filter_by(pipeline_id=pipeline.id, agent_role='investigador').first()

    if not editor_stage or not editor_stage.output_data:
        return {'ok': False, 'reason': 'El Editor no ha completado su etapa.', 'proposals': []}
    if not creativo_stage or not creativo_stage.output_data:
        return {'ok': False, 'reason': 'El Creativo no ha completado su etapa.', 'proposals': []}

    editor_out   = editor_stage.output_dict
    creativo_out = creativo_stage.output_dict
    inv_out      = inv_stage.output_dict if inv_stage and inv_stage.output_data else {}

    posts      = editor_out.get('posts', [])[:3]
    propuestas = creativo_out.get('propuestas', [])[:3]

    if not posts and not propuestas:
        return {'ok': False, 'reason': 'Editor y Creativo no produjeron contenido.', 'proposals': []}

    # ── Generar prompts visuales enriquecidos con Claude ──────────────────────
    # Para las noticias, Claude genera un prompt visual de imagen informativa
    # Para las propuestas comerciales, ya incluyen flow_prompt del Creativo,
    # pero pedimos a Claude un prompt refinado y más detallado.

    piezas_para_prompt = []
    for i, post in enumerate(posts):
        piezas_para_prompt.append({
            'tipo': 'noticia',
            'idx': i,
            'categoria': post.get('categoria', 'internacional'),
            'topic': post.get('topic', ''),
            'text_body': (post.get('text_body', ''))[:200],
        })
    for i, prop in enumerate(propuestas):
        piezas_para_prompt.append({
            'tipo': 'comercial',
            'idx': i,
            'audiencia': prop.get('audiencia', ''),
            'topic': prop.get('topic', ''),
            'visual_idea': prop.get('visual_idea', ''),
            'flow_prompt_base': prop.get('flow_prompt', ''),
        })

    piezas_json = json.dumps(piezas_para_prompt, ensure_ascii=False)
    prompt_dv = f"""Genera prompts visuales para estas {len(piezas_para_prompt)} piezas de Qoricash:

{piezas_json}

Para las piezas comerciales: fotografía publicitaria con escenas diferentes entre sí
(alterna persona en negocio, persona con teléfono, viajero, composición conceptual).
Para las noticias: imagen editorial conceptual relacionada con el tema.

Para cada pieza devuelve:
{{
  "tipo": "noticia|comercial",
  "idx": numero,
  "flow_prompt": "prompt autónomo ≥100 palabras siguiendo la estructura de Director Visual",
  "formato": "1200x628 LinkedIn" o "1080x1080 cuadrado"
}}

Devuelve un array JSON de {len(piezas_para_prompt)} objetos. Solo JSON."""

    # Guardar created_by (non-PK) antes de cerrar la sesión; pipeline.id (PK) sobrevive al detach.
    _pip_created_by = pipeline.created_by
    db.session.close()

    try:
        prompts_result = ask_json(prompt_dv, system=SYSTEM_DV, model=SONNET, max_tokens=3500)
        if isinstance(prompts_result, dict):
            prompts_result = list(prompts_result.values())[0] if prompts_result else []
        prompts_map = {(p.get('tipo'), p.get('idx')): p for p in (prompts_result or [])}
    except Exception as e:
        log.warning(f'[DirectorVisual] Claude prompts falló: {e} — usando prompts base')
        prompts_map = {}

    # ── Crear ContentProposal records ─────────────────────────────────────────
    batch = ContentBatch(
        created_by = _pip_created_by,
        count      = len(posts) + len(propuestas),
        model_used = 'pipeline-diario',
        notes      = f'Pipeline diario #{pipeline.id}',
    )
    db.session.add(batch)
    db.session.flush()

    proposals_created = []
    sources = _collect_pipeline_sources(pipeline)

    # Idempotencia: saber qué categorías de noticias y cuántas comerciales ya existen.
    existing_cats = {
        p.noticia_category
        for p in ContentProposal.query.filter_by(
            pipeline_id=pipeline.id, delivery_type='noticia'
        ).all()
        if p.noticia_category
    }
    cok_existing = ContentProposal.query.filter_by(
        pipeline_id=pipeline.id, delivery_type='comercial'
    ).count()

    # Noticias → ContentProposal (delivery_type=noticia)
    for i, post in enumerate(posts):
        cat = post.get('categoria', 'internacional')
        if cat in existing_cats:
            log.info(f'[DirectorVisual] Noticia categoría "{cat}" ya existe para pipeline #{pipeline.id} — omitiendo')
            continue
        pm = prompts_map.get(('noticia', i), {})
        cat_label = {
            'nacional': 'Economía Perú', 'internacional': 'Internacional',
            'mercados': 'Mercados/TC',
        }.get(cat, 'Actualidad')
        raw_fp = pm.get('flow_prompt', '').strip()
        noticia_fp = raw_fp or _noticia_fallback_prompt(cat, post.get('topic', ''), post.get('text_body', '')[:200])

        p = ContentProposal(
            batch_id         = batch.id,
            pipeline_id      = pipeline.id,
            network          = 'linkedin',
            delivery_type    = 'noticia',
            noticia_category = cat,
            topic            = post.get('topic', ''),
            tag              = cat_label,
            objective        = 'Posicionamiento editorial — actualidad económica',
            audience         = 'Empresas y profesionales en LinkedIn',
            text_body        = post.get('text_body', ''),
            cta              = post.get('cta', ''),
            hashtags         = post.get('hashtags', '#qoricash #tipodecambio'),
            visual_idea      = f'Imagen informativa para post de {cat_label}',
            flow_prompt      = noticia_fp,
            image_format     = pm.get('formato', '1200x628 LinkedIn'),
            resource_status  = 'prompt_listo',
            status           = 'borrador',
            is_demo          = False,
        )
        if sources:
            p.sources = json.dumps(sources, ensure_ascii=False)
        db.session.add(p)
        db.session.flush()
        proposals_created.append({
            'proposal_id':    p.id,
            'delivery_type':  'noticia',
            'categoria':      post.get('categoria'),
            'topic':          p.topic,
            'resource_status': 'prompt_listo',
        })

    # Propuestas comerciales → ContentProposal (delivery_type=comercial)
    # Idempotencia: si ya existen N comerciales, solo crear los que falten hasta 3.
    cok_created = 0
    for i, prop in enumerate(propuestas):
        if cok_existing + cok_created >= 3:
            log.info(f'[DirectorVisual] Comercial #{i} omitido: ya hay {cok_existing + cok_created} comerciales')
            break
        pm = prompts_map.get(('comercial', i), {})
        p = ContentProposal(
            batch_id         = batch.id,
            pipeline_id      = pipeline.id,
            network          = 'linkedin',
            delivery_type    = 'comercial',
            noticia_category = None,
            topic            = prop.get('topic', ''),
            tag              = 'Comercial',
            objective        = prop.get('angulo', ''),
            audience         = prop.get('audiencia', ''),
            text_body        = prop.get('text_body', ''),
            cta              = prop.get('cta', ''),
            hashtags         = prop.get('hashtags', '#qoricash'),
            visual_idea      = prop.get('visual_idea', ''),
            flow_prompt      = pm.get('flow_prompt') or prop.get('flow_prompt', ''),
            image_format     = pm.get('formato', '1200x628 LinkedIn'),
            resource_status  = 'prompt_listo',
            status           = 'borrador',
            is_demo          = False,
        )
        db.session.add(p)
        db.session.flush()
        cok_created += 1
        proposals_created.append({
            'proposal_id':    p.id,
            'delivery_type':  'comercial',
            'audiencia':      prop.get('audiencia'),
            'topic':          p.topic,
            'resource_status': 'prompt_listo',
        })

    db.session.commit()

    return {
        'ok':        True,
        'proposals': proposals_created,
        'batch_id':  batch.id,
        'note':      (
            'Prompts Gemini/Flow generados para las 6 piezas. '
            'Copia el prompt de cada pieza en Gemini Imagen o Google Flow, '
            'genera la imagen/video y cárgalo en "Adjuntar resultado".'
        ),
        'mode':      'diario',
    }


def _make_carousel_zip(pipeline_id: int, proposals: list) -> str:
    """
    Genera un ZIP con todas las imágenes del pipeline.
    Retorna la ruta relativa a static/ o None si falla.
    """
    try:
        from flask import current_app
        img_dir = Path(current_app.root_path) / 'static' / 'content' / 'img'
        zip_name = f'pipeline_{pipeline_id}_carousel.zip'
        zip_path = img_dir / zip_name

        static_dir = Path(current_app.root_path) / 'static'
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for item in proposals:
                img = item.get('image')
                if img:
                    full = static_dir / img   # static/content/img/proposal_N.png
                    if full.exists():
                        zf.write(full, arcname=Path(img).name)

        if zip_path.stat().st_size > 100:
            return f'content/img/{zip_name}'
    except Exception as e:
        log.warning(f'[Productor] carousel zip: {e}')
    return None
