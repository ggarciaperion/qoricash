"""
Plantillas de imagen para el módulo de contenido de QoriCash.

Usa Pillow (PIL) con la identidad visual real:
  - Primary:  #00DEA8  (teal)
  - Dark:     #0D1B2A  (navy)
  - White:    #FFFFFF
  - Accent:   #00C997

Tres plantillas:
  - linkedin_card   1200×628  (horizontal, fondo navy)
  - instagram_post  1080×1080 (cuadrado, gradiente)
  - story_reel      1080×1920 (vertical, fondo navy)

Todas producidas localmente con Pillow, sin suscripción adicional.
"""

import os
import io
import textwrap
import logging
from pathlib import Path

log = logging.getLogger(__name__)

# ── Paleta oficial ────────────────────────────────────────────────────────────
C_TEAL   = (0,   222, 168)   # #00DEA8
C_NAVY   = (13,  27,  42)    # #0D1B2A
C_NAVY2  = (26,  47,  63)    # #1A2F3F
C_WHITE  = (255, 255, 255)
C_LGRAY  = (200, 210, 220)
C_TEAL_A = (0,   201, 151)   # #00C997

# ── Fuentes disponibles (orden de preferencia) ───────────────────────────────
_FONT_CANDIDATES = [
    '/System/Library/Fonts/HelveticaNeue.ttc',
    '/System/Library/Fonts/Helvetica.ttc',
    '/System/Library/Fonts/ArialHB.ttc',
    '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
]

def _load_font(size: int, bold: bool = False):
    from PIL import ImageFont
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                if path.endswith('.ttc'):
                    idx = 1 if bold else 0
                    return ImageFont.truetype(path, size, index=idx)
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _load_logo(size_px: int = 80):
    """Carga el logo real de QoriCash redimensionado."""
    from PIL import Image
    candidates = [
        'app/static/images/logo-principal.png',
        'app/static/images/logo.png',
        'app/static/images/Logofinal.png',
    ]
    # Buscar desde la raíz del proyecto
    root = Path(__file__).parents[3]
    for rel in candidates:
        p = root / rel
        if p.exists():
            try:
                img = Image.open(p).convert('RGBA')
                ratio = size_px / max(img.width, img.height)
                new_w = int(img.width * ratio)
                new_h = int(img.height * ratio)
                return img.resize((new_w, new_h), Image.LANCZOS)
            except Exception as e:
                log.warning(f'Logo no cargado desde {p}: {e}')
    return None


def _draw_rounded_rect(draw, xy, fill, radius=16):
    """Dibuja un rectángulo con bordes redondeados."""
    from PIL import ImageDraw
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill)


def _wrap_text(text: str, font, max_width: int, draw) -> list[str]:
    """Envuelve texto respetando el ancho máximo en píxeles."""
    words = text.split()
    lines, current = [], ''
    for word in words:
        test = (current + ' ' + word).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] > max_width and current:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)
    return lines


# ── Plantilla 1: LinkedIn Card (1200×628) ─────────────────────────────────────

def render_linkedin_card(topic: str, body_lines: list[str],
                         cta: str = '', tag: str = '') -> bytes:
    """
    Genera imagen horizontal para LinkedIn.
    topic:      título grande
    body_lines: 2-3 líneas de texto
    cta:        llamada a la acción
    tag:        etiqueta de categoría (p.ej. "Tipo de Cambio")
    Retorna: bytes PNG
    """
    from PIL import Image, ImageDraw

    W, H = 1200, 628
    img  = Image.new('RGB', (W, H), C_NAVY)
    draw = ImageDraw.Draw(img)

    # ── Barra de acento izquierda ────────────────────────────────────────────
    draw.rectangle([0, 0, 6, H], fill=C_TEAL)

    # ── Gradiente sutil en el fondo derecho ─────────────────────────────────
    for i in range(400):
        alpha = int(30 * (1 - i / 400))
        x = W - 400 + i
        draw.line([(x, 0), (x, H)], fill=(0, 222, 168, alpha))

    # ── Tag de categoría ────────────────────────────────────────────────────
    tag_font = _load_font(20)
    if tag:
        tag_text = tag.upper()
        bbox = draw.textbbox((0, 0), tag_text, font=tag_font)
        tw = bbox[2] - bbox[0]
        pad = 12
        _draw_rounded_rect(draw, [56, 48, 56 + tw + pad*2, 48 + 32], C_TEAL, radius=6)
        draw.text((56 + pad, 52), tag_text, font=tag_font, fill=C_NAVY)

    # ── Título ───────────────────────────────────────────────────────────────
    title_font = _load_font(52, bold=True)
    title_y    = 110 if tag else 80
    title_lines = _wrap_text(topic, title_font, W - 200, draw)
    for i, line in enumerate(title_lines[:3]):
        draw.text((56, title_y + i * 66), line, font=title_font, fill=C_WHITE)

    # ── Línea divisoria ──────────────────────────────────────────────────────
    divider_y = title_y + len(title_lines[:3]) * 66 + 20
    draw.rectangle([56, divider_y, 200, divider_y + 3], fill=C_TEAL)

    # ── Cuerpo ───────────────────────────────────────────────────────────────
    body_font = _load_font(28)
    body_y    = divider_y + 28
    for line in body_lines[:4]:
        wrapped = _wrap_text(line, body_font, W - 200, draw)
        for wl in wrapped[:2]:
            draw.text((56, body_y), wl, font=body_font, fill=C_LGRAY)
            body_y += 40

    # ── CTA ──────────────────────────────────────────────────────────────────
    if cta:
        cta_font = _load_font(26)
        cta_y    = H - 100
        draw.text((56, cta_y), f'→ {cta}', font=cta_font, fill=C_TEAL)

    # ── Logo ─────────────────────────────────────────────────────────────────
    logo = _load_logo(64)
    if logo:
        lx = W - logo.width - 48
        ly = H - logo.height - 32
        img.paste(logo, (lx, ly), logo)

    # ── Dominio ──────────────────────────────────────────────────────────────
    domain_font = _load_font(20)
    draw.text((56, H - 44), 'qoricash.pe', font=domain_font,
              fill=(100, 150, 130))

    buf = io.BytesIO()
    img.save(buf, format='PNG', optimize=True)
    return buf.getvalue()


# ── Plantilla 2: Instagram/Facebook Post (1080×1080) ─────────────────────────

def render_instagram_post(topic: str, body_lines: list[str],
                          cta: str = '', tag: str = '') -> bytes:
    """Genera imagen cuadrada para Instagram/Facebook."""
    from PIL import Image, ImageDraw

    W = H = 1080
    img  = Image.new('RGB', (W, H), C_NAVY)
    draw = ImageDraw.Draw(img)

    # ── Bloque de color teal en la parte superior ─────────────────────────
    draw.rectangle([0, 0, W, 320], fill=C_NAVY2)
    draw.rectangle([0, 318, W, 322], fill=C_TEAL)

    # ── Esquinas decorativas ─────────────────────────────────────────────
    draw.rectangle([0, 0, 8, H], fill=C_TEAL)
    draw.rectangle([W-8, 0, W, H], fill=(0, 222, 168, 40))

    # ── Tag ───────────────────────────────────────────────────────────────
    tag_font = _load_font(22)
    if tag:
        bbox = draw.textbbox((0, 0), tag.upper(), font=tag_font)
        tw = bbox[2] - bbox[0]
        _draw_rounded_rect(draw, [48, 52, 48 + tw + 28, 52 + 36], C_TEAL, radius=8)
        draw.text((62, 56), tag.upper(), font=tag_font, fill=C_NAVY)

    # ── Título ────────────────────────────────────────────────────────────
    title_font = _load_font(54, bold=True)
    title_y    = 118
    title_lines = _wrap_text(topic, title_font, W - 120, draw)
    for i, line in enumerate(title_lines[:3]):
        draw.text((54, title_y + i * 68), line, font=title_font, fill=C_WHITE)

    # ── Cuerpo ────────────────────────────────────────────────────────────
    body_font = _load_font(30)
    body_y    = 360
    for line in body_lines[:5]:
        wrapped = _wrap_text(line, body_font, W - 120, draw)
        for wl in wrapped[:2]:
            draw.text((54, body_y), wl, font=body_font, fill=C_LGRAY)
            body_y += 44

    # ── CTA ───────────────────────────────────────────────────────────────
    if cta:
        cta_font = _load_font(30)
        cta_bbox = draw.textbbox((0, 0), cta, font=cta_font)
        cw = cta_bbox[2] - cta_bbox[0]
        pad = 24
        cta_x = (W - cw - pad*2) // 2
        _draw_rounded_rect(draw, [cta_x, H - 150, cta_x + cw + pad*2, H - 90],
                           C_TEAL, radius=12)
        draw.text((cta_x + pad, H - 142), cta, font=cta_font, fill=C_NAVY)

    # ── Logo ──────────────────────────────────────────────────────────────
    logo = _load_logo(72)
    if logo:
        lx = W - logo.width - 48
        img.paste(logo, (lx, H - logo.height - 32), logo)

    domain_font = _load_font(22)
    draw.text((54, H - 44), 'qoricash.pe', font=domain_font, fill=(100, 150, 130))

    buf = io.BytesIO()
    img.save(buf, format='PNG', optimize=True)
    return buf.getvalue()


# ── Plantilla 3: Story / Reel cover (1080×1920) ──────────────────────────────

def render_story_cover(topic: str, subtitle: str = '',
                       tag: str = 'REEL') -> bytes:
    """Genera portada vertical para Story o Reel."""
    from PIL import Image, ImageDraw

    W, H = 1080, 1920
    img  = Image.new('RGB', (W, H), C_NAVY)
    draw = ImageDraw.Draw(img)

    # Banda teal inferior
    draw.rectangle([0, H - 320, W, H], fill=C_NAVY2)
    draw.rectangle([0, H - 322, W, H - 318], fill=C_TEAL)

    # Banda izquierda
    draw.rectangle([0, 0, 10, H], fill=C_TEAL)

    # Tag
    tag_font = _load_font(30)
    bbox = draw.textbbox((0, 0), tag.upper(), font=tag_font)
    tw = bbox[2]
    _draw_rounded_rect(draw, [60, 80, 60 + tw + 36, 80 + 48], C_TEAL, radius=10)
    draw.text((78, 88), tag.upper(), font=tag_font, fill=C_NAVY)

    # Título
    title_font = _load_font(76, bold=True)
    title_lines = _wrap_text(topic, title_font, W - 140, draw)
    title_y = (H // 2) - len(title_lines) * 45
    for i, line in enumerate(title_lines[:4]):
        draw.text((60, title_y + i * 96), line, font=title_font, fill=C_WHITE)

    # Subtítulo
    if subtitle:
        sub_font = _load_font(36)
        sub_y = title_y + len(title_lines[:4]) * 96 + 30
        sub_lines = _wrap_text(subtitle, sub_font, W - 140, draw)
        for line in sub_lines[:3]:
            draw.text((60, sub_y), line, font=sub_font, fill=C_LGRAY)
            sub_y += 50

    # Logo
    logo = _load_logo(88)
    if logo:
        lx = (W - logo.width) // 2
        img.paste(logo, (lx, H - 220), logo)

    domain_font = _load_font(28)
    domain_text = 'qoricash.pe'
    d_bbox = draw.textbbox((0, 0), domain_text, font=domain_font)
    dw = d_bbox[2]
    draw.text(((W - dw) // 2, H - 80), domain_text, font=domain_font, fill=(100, 150, 130))

    buf = io.BytesIO()
    img.save(buf, format='PNG', optimize=True)
    return buf.getvalue()
