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

    SYSTEM_DV = """Eres el Director Visual de Qoricash.
Tu tarea es escribir prompts detallados para generar imágenes con Gemini Imagen o Google Flow.
Paleta de marca: Teal #00DEA8, Navy #0D1B2A, blanco.
Logotipo: "Qoricash" en tipografía moderna, color teal sobre fondo navy.
Estilo: limpio, profesional, fintech latinoamericano, sin elementos genéricos de banco.
Cada prompt debe tener 80-120 palabras: composición, colores, elementos, atmósfera, texto en imagen si aplica."""

    piezas_json = json.dumps(piezas_para_prompt, ensure_ascii=False)
    prompt_dv = f"""Genera prompts visuales para estas {len(piezas_para_prompt)} piezas de Qoricash:

{piezas_json}

Para cada pieza devuelve:
{{
  "tipo": "noticia|comercial",
  "idx": numero,
  "flow_prompt": "prompt completo 80-120 palabras para Gemini Imagen/Flow",
  "formato": "1200x628 LinkedIn" o "1080x1080 cuadrado"
}}

Devuelve un array JSON de {len(piezas_para_prompt)} objetos. Solo JSON."""

    try:
        prompts_result = ask_json(prompt_dv, system=SYSTEM_DV, model=SONNET, max_tokens=3000)
        if isinstance(prompts_result, dict):
            prompts_result = list(prompts_result.values())[0] if prompts_result else []
        prompts_map = {(p.get('tipo'), p.get('idx')): p for p in (prompts_result or [])}
    except Exception as e:
        log.warning(f'[DirectorVisual] Claude prompts falló: {e} — usando prompts base')
        prompts_map = {}

    # ── Crear ContentProposal records ─────────────────────────────────────────
    batch = ContentBatch(
        created_by = pipeline.created_by,
        count      = len(posts) + len(propuestas),
        model_used = 'pipeline-diario',
        notes      = f'Pipeline diario #{pipeline.id}',
    )
    db.session.add(batch)
    db.session.flush()

    proposals_created = []
    sources = _collect_pipeline_sources(pipeline)

    # Noticias → ContentProposal (delivery_type=noticia)
    for i, post in enumerate(posts):
        pm = prompts_map.get(('noticia', i), {})
        cat_label = {
            'nacional': 'Economía Perú', 'internacional': 'Internacional',
            'mercados': 'Mercados/TC',
        }.get(post.get('categoria', ''), 'Actualidad')

        p = ContentProposal(
            batch_id         = batch.id,
            pipeline_id      = pipeline.id,
            network          = 'linkedin',
            delivery_type    = 'noticia',
            noticia_category = post.get('categoria', 'internacional'),
            topic            = post.get('topic', ''),
            tag              = cat_label,
            objective        = 'Posicionamiento editorial — actualidad económica',
            audience         = 'Empresas y profesionales en LinkedIn',
            text_body        = post.get('text_body', ''),
            cta              = post.get('cta', ''),
            hashtags         = post.get('hashtags', '#qoricash #tipodecambio'),
            visual_idea      = f'Imagen informativa para post de {cat_label}',
            flow_prompt      = pm.get('flow_prompt', ''),
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
    for i, prop in enumerate(propuestas):
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
