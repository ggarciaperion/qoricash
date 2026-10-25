"""
Servicio de imágenes para el módulo de contenido.
Genera, guarda y sirve imágenes usando las plantillas de marca.
"""

import os
import logging
import hashlib
from pathlib import Path

log = logging.getLogger(__name__)

# Directorio de salida relativo al proyecto
_CONTENT_IMG_DIR = 'app/static/content/img'


def _ensure_dir():
    root = Path(__file__).parents[3]
    d = root / _CONTENT_IMG_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def render_and_save(proposal):
    """
    Renderiza la imagen de una propuesta y la guarda en static/content/img/.
    Retorna la ruta relativa a static/ (para url_for) o None si falla.
    """
    from app.services.content.brand_templates import (
        render_linkedin_card, render_instagram_post, render_story_cover,
    )
    try:
        tag       = proposal.topic.split(':')[0][:20] if proposal.topic else ''
        body_lines = []
        if proposal.text_body:
            # Primeras 3 líneas no vacías del cuerpo para el visual
            body_lines = [l.strip() for l in proposal.text_body.split('\n')
                          if l.strip()][:3]

        network = proposal.network or 'linkedin'

        if network == 'linkedin' or network == 'facebook':
            img_bytes = render_linkedin_card(
                topic=proposal.topic or '',
                body_lines=body_lines,
                cta=proposal.cta or '',
                tag=proposal.tag if hasattr(proposal, 'tag') else tag,
            )
            suffix = 'linkedin'
        elif network == 'instagram':
            img_bytes = render_instagram_post(
                topic=proposal.topic or '',
                body_lines=body_lines,
                cta=proposal.cta or '',
                tag=proposal.tag if hasattr(proposal, 'tag') else tag,
            )
            suffix = 'instagram'
        elif network == 'reel':
            img_bytes = render_story_cover(
                topic=proposal.topic or '',
                subtitle=proposal.cta or '',
                tag='REEL',
            )
            suffix = 'reel'
        else:
            return None

        d = _ensure_dir()
        fname = f'proposal_{proposal.id}_{suffix}.png'
        fpath = d / fname
        with open(fpath, 'wb') as f:
            f.write(img_bytes)

        return f'content/img/{fname}'

    except Exception as e:
        log.error(f'[Content] render_and_save proposal={proposal.id}: {e}')
        return None


def get_image_url(image_path):
    """Convierte ruta relativa a URL de Flask (static)."""
    if not image_path:
        return None
    return f'/static/{image_path}'
