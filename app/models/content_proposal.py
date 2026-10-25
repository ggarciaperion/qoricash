"""
Módulo de Contenido — Modelo de propuestas y lotes.
"""
from app.extensions import db
from app.utils.formatters import now_peru
import json


class ContentBatch(db.Model):
    """Lote de propuestas generadas. Evita re-generar si ya existe uno reciente."""
    __tablename__ = 'content_batches'

    id          = db.Column(db.Integer, primary_key=True)
    created_at  = db.Column(db.DateTime, default=now_peru)
    created_by  = db.Column(db.Integer, db.ForeignKey('users.id'))
    count       = db.Column(db.Integer, default=0)
    model_used  = db.Column(db.String(80))
    input_tokens  = db.Column(db.Integer, default=0)
    output_tokens = db.Column(db.Integer, default=0)
    notes       = db.Column(db.Text)

    proposals   = db.relationship('ContentProposal', back_populates='batch',
                                  cascade='all, delete-orphan')
    creator     = db.relationship('User', foreign_keys=[created_by])


class ContentProposal(db.Model):
    """Una pieza de contenido propuesta por el agente creativo."""
    __tablename__ = 'content_proposals'

    id           = db.Column(db.Integer, primary_key=True)
    batch_id     = db.Column(db.Integer, db.ForeignKey('content_batches.id'))
    created_at   = db.Column(db.DateTime, default=now_peru)
    updated_at   = db.Column(db.DateTime, default=now_peru, onupdate=now_peru)

    # Clasificación
    network      = db.Column(db.String(30), nullable=False)   # linkedin|instagram|facebook|reel
    topic        = db.Column(db.String(200))
    objective    = db.Column(db.String(200))
    audience     = db.Column(db.String(200))

    # Clasificación visual
    tag          = db.Column(db.String(60))    # etiqueta corta para el visual (ej: "Educación")

    # Contenido
    text_body    = db.Column(db.Text)      # texto listo para publicar
    visual_idea  = db.Column(db.Text)      # descripción visual / prompt imagen
    cta          = db.Column(db.String(300))
    hashtags     = db.Column(db.String(500))
    sources      = db.Column(db.Text)      # JSON: [{url, title, date}]

    # Video / Reels
    script_scenes = db.Column(db.Text)    # JSON: [{scene, duration, text_screen, voice}]
    flow_prompt   = db.Column(db.Text)    # Prompt listo para Google Flow/Gemini

    # Imagen generada
    image_path   = db.Column(db.String(500))   # ruta relativa a static/
    image_format = db.Column(db.String(20))    # png|jpg|carousel_json

    # Estado
    # borrador → aprobado / rechazado → programado → publicado
    status       = db.Column(db.String(30), default='borrador')
    rejection_reason = db.Column(db.Text)
    scheduled_at = db.Column(db.DateTime)      # fecha planificada
    platform_id  = db.Column(db.String(200))   # ID en plataforma externa (futuro)
    published_url = db.Column(db.String(500))  # URL publicada (futuro)
    published_at  = db.Column(db.DateTime)

    # Ajustes del usuario
    user_edits   = db.Column(db.Text)     # JSON: [{timestamp, field, old, new}]
    adjustment_request = db.Column(db.Text)    # última solicitud de ajuste al agente
    adjustment_result  = db.Column(db.Text)    # respuesta del agente al ajuste

    # Error si la generación falló
    error_msg    = db.Column(db.Text)

    # Demo flag
    is_demo      = db.Column(db.Boolean, default=False)

    # Entrega diaria
    pipeline_id      = db.Column(db.Integer, db.ForeignKey('content_pipelines.id'))
    delivery_type    = db.Column(db.String(20))   # noticia | comercial
    noticia_category = db.Column(db.String(30))   # nacional | internacional | mercados
    resource_status  = db.Column(db.String(30), default='prompt_listo')
    # prompt_listo | recurso_pendiente | recurso_cargado | pendiente_aprobacion | aprobado | planificado
    revisor_notas    = db.Column(db.Text)
    correcciones     = db.Column(db.Text)   # JSON list of correction strings
    retry_count      = db.Column(db.Integer, default=0)

    batch        = db.relationship('ContentBatch', back_populates='proposals')

    # ── Helpers ──────────────────────────────────────────────────────────────

    @property
    def sources_list(self):
        if self.sources:
            try:
                return json.loads(self.sources)
            except Exception:
                return []
        return []

    @property
    def scenes_list(self):
        if self.script_scenes:
            try:
                return json.loads(self.script_scenes)
            except Exception:
                return []
        return []

    @property
    def edits_list(self):
        if self.user_edits:
            try:
                return json.loads(self.user_edits)
            except Exception:
                return []
        return []

    @property
    def correcciones_list(self):
        if self.correcciones:
            try:
                return json.loads(self.correcciones)
            except Exception:
                return []
        return []

    @property
    def resource_status_badge(self):
        return {
            'prompt_listo':       ('info',      'Prompt listo'),
            'recurso_pendiente':  ('warning',   'Recurso pendiente'),
            'recurso_cargado':    ('primary',   'Recurso cargado'),
            'pendiente_aprobacion': ('warning', 'Pendiente aprobación'),
            'aprobado':           ('success',   'Aprobado'),
            'planificado':        ('info',      'Planificado'),
        }.get(self.resource_status or 'prompt_listo', ('secondary', self.resource_status or ''))

    @property
    def network_icon(self):
        return {
            'linkedin':  'bi-linkedin',
            'instagram': 'bi-instagram',
            'facebook':  'bi-facebook',
            'reel':      'bi-camera-video',
        }.get(self.network, 'bi-megaphone')

    @property
    def status_badge(self):
        return {
            'borrador':   ('secondary', 'Borrador'),
            'aprobado':   ('success',   'Aprobado'),
            'rechazado':  ('danger',    'Rechazado'),
            'programado': ('info',      'Planificado — publicación manual'),
            'publicado':  ('primary',   'Publicado manualmente'),
            'error':      ('warning',   'Error'),
        }.get(self.status, ('secondary', self.status))
