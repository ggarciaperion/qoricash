"""
Estudio Creativo — Modelos de pipeline, etapas, fuentes y configuración de marca.
"""
import json
from datetime import date as _date
from app.extensions import db
from app.utils.formatters import now_peru


# ── ContentPipeline ───────────────────────────────────────────────────────────

class ContentPipeline(db.Model):
    """
    Flujo de trabajo coordinado entre agentes.
    Tipos:
      actualidad  → Investigador → Analista → Editor → Productor → Revisor → Usuario
      comercial   → Creativo → Editor → Productor → Revisor → Usuario
    """
    __tablename__ = 'content_pipelines'

    id          = db.Column(db.Integer, primary_key=True)
    created_at  = db.Column(db.DateTime, default=now_peru)
    updated_at  = db.Column(db.DateTime, default=now_peru, onupdate=now_peru)
    created_by  = db.Column(db.Integer, db.ForeignKey('users.id'))

    type        = db.Column(db.String(20), nullable=False)   # actualidad | comercial
    title       = db.Column(db.String(200))
    status      = db.Column(db.String(30), default='running')
    # pending | running | waiting_user | done | error | cancelled

    current_stage_seq = db.Column(db.Integer, default=1)
    notes       = db.Column(db.Text)
    error_msg   = db.Column(db.Text)

    # Relaciones
    stages   = db.relationship('PipelineStage', back_populates='pipeline',
                               cascade='all, delete-orphan',
                               order_by='PipelineStage.seq')
    sources  = db.relationship('ContentSource', back_populates='pipeline',
                               cascade='all, delete-orphan')
    creator  = db.relationship('User', foreign_keys=[created_by])

    @property
    def current_stage(self):
        for s in self.stages:
            if s.seq == self.current_stage_seq:
                return s
        return None

    @property
    def status_badge(self):
        return {
            'pending':       ('secondary', 'Pendiente'),
            'running':       ('primary',   'En proceso'),
            'waiting_user':  ('warning',   'Esperando aprobación'),
            'done':          ('success',   'Completado'),
            'error':         ('danger',    'Error'),
            'cancelled':     ('secondary', 'Cancelado'),
        }.get(self.status, ('secondary', self.status))

    @property
    def total_stages(self):
        return len(self.stages)

    @property
    def progress_pct(self):
        if not self.stages:
            return 0
        done = sum(1 for s in self.stages if s.status == 'done')
        return int(done / len(self.stages) * 100)


# ── PipelineStage ─────────────────────────────────────────────────────────────

class PipelineStage(db.Model):
    """
    Una etapa dentro del pipeline, ejecutada por un agente específico.
    Guarda entrada, salida, versión, estado y fechas.
    """
    __tablename__ = 'pipeline_stages'

    id          = db.Column(db.Integer, primary_key=True)
    pipeline_id = db.Column(db.Integer, db.ForeignKey('content_pipelines.id'), nullable=False)
    seq         = db.Column(db.Integer, nullable=False)         # orden 1, 2, 3…
    agent_role  = db.Column(db.String(40), nullable=False)      # investigador|analista|creativo|editor|productor|revisor
    status      = db.Column(db.String(30), default='pending')
    # pending | running | waiting_input | done | error | needs_review | skipped

    input_data  = db.Column(db.Text)      # JSON — entrada entregada al agente
    output_data = db.Column(db.Text)      # JSON — salida del agente
    version     = db.Column(db.Integer, default=1)

    started_at   = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)

    error_msg    = db.Column(db.Text)
    user_instruction = db.Column(db.Text)  # instrucción adicional del usuario
    review_notes = db.Column(db.Text)      # observaciones del revisor o usuario
    approved_by  = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_at  = db.Column(db.DateTime)

    pipeline = db.relationship('ContentPipeline', back_populates='stages')

    @property
    def input_dict(self):
        if self.input_data:
            try:
                return json.loads(self.input_data)
            except Exception:
                return {}
        return {}

    @property
    def output_dict(self):
        if self.output_data:
            try:
                return json.loads(self.output_data)
            except Exception:
                return {}
        return {}

    @property
    def agent_label(self):
        return {
            'investigador': 'Investigador de actualidad',
            'analista':     'Analista económico',
            'creativo':     'Creativo comercial',
            'editor':       'Editor de redes',
            'productor':    'Productor visual',
            'revisor':      'Revisor y coordinador',
        }.get(self.agent_role, self.agent_role)

    @property
    def agent_icon(self):
        return {
            'investigador': 'bi-search',
            'analista':     'bi-graph-up',
            'creativo':     'bi-lightbulb',
            'editor':       'bi-pen',
            'productor':    'bi-camera',
            'revisor':      'bi-shield-check',
        }.get(self.agent_role, 'bi-robot')

    @property
    def status_badge(self):
        return {
            'pending':       ('secondary', 'Pendiente'),
            'running':       ('primary',   'Ejecutando'),
            'waiting_input': ('warning',   'Esperando entrada'),
            'done':          ('success',   'Listo'),
            'error':         ('danger',    'Error'),
            'needs_review':  ('info',      'Requiere revisión'),
            'skipped':       ('secondary', 'Omitido'),
        }.get(self.status, ('secondary', self.status))


# ── ContentSource ─────────────────────────────────────────────────────────────

class ContentSource(db.Model):
    """
    Fuente de información recuperada por el Investigador.
    Guarda URL, título, extracto, fecha y evidencia utilizada.
    """
    __tablename__ = 'content_sources'

    id          = db.Column(db.Integer, primary_key=True)
    pipeline_id = db.Column(db.Integer, db.ForeignKey('content_pipelines.id'))
    stage_id    = db.Column(db.Integer, db.ForeignKey('pipeline_stages.id'))
    fetched_at  = db.Column(db.DateTime, default=now_peru)

    url          = db.Column(db.String(2000))
    title        = db.Column(db.String(500))
    excerpt      = db.Column(db.Text)          # extracto/resumen del contenido
    published_at = db.Column(db.String(30))    # fecha publicación original (str para flexibilidad)
    source_name  = db.Column(db.String(200))
    source_type  = db.Column(db.String(30))    # oficial|media|bcrp|sbs|user_provided|market_feed
    is_verified  = db.Column(db.Boolean, default=False)  # marcado como verificado por usuario
    used_in_analysis = db.Column(db.Boolean, default=False)

    pipeline = db.relationship('ContentPipeline', back_populates='sources')

    @property
    def short_url(self):
        if not self.url:
            return ''
        try:
            from urllib.parse import urlparse
            p = urlparse(self.url)
            return p.netloc + (p.path[:40] if p.path else '')
        except Exception:
            return self.url[:50]


# ── BrandConfig ───────────────────────────────────────────────────────────────

class BrandConfig(db.Model):
    """
    Ficha de marca editable. Define qué puede y qué no puede afirmar
    el agente Creativo al proponer contenido comercial.
    """
    __tablename__ = 'brand_configs'

    id          = db.Column(db.Integer, primary_key=True)
    updated_at  = db.Column(db.DateTime, default=now_peru, onupdate=now_peru)
    updated_by  = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Beneficios verificados (lista JSON de strings)
    verified_benefits = db.Column(db.Text, default='[]')

    # Afirmaciones prohibidas (lista JSON de strings)
    prohibited_claims = db.Column(db.Text, default='[]')

    # Guía de tono
    tone_guide  = db.Column(db.Text, default='')

    # Sets de hashtags aprobados (JSON)
    hashtag_sets = db.Column(db.Text, default='{}')

    # Canales aprobados
    approved_channels = db.Column(db.String(200),
                                  default='linkedin,instagram,facebook,reel')

    # Fuentes de mercado habilitadas
    enabled_sources = db.Column(db.String(500),
                                default='bcrp,sbs,el_comercio,gestion,peru21')

    @property
    def benefits_list(self):
        try:
            return json.loads(self.verified_benefits or '[]')
        except Exception:
            return []

    @property
    def claims_list(self):
        try:
            return json.loads(self.prohibited_claims or '[]')
        except Exception:
            return []

    @property
    def hashtags_dict(self):
        try:
            return json.loads(self.hashtag_sets or '{}')
        except Exception:
            return {}

    @property
    def hashtag_sets_list(self):
        return self.hashtags_dict

    @classmethod
    def get_current(cls):
        """Retorna la config activa, creando una por defecto si no existe."""
        cfg = cls.query.order_by(cls.id.desc()).first()
        if not cfg:
            cfg = cls(
                verified_benefits=json.dumps([
                    'Tipo de cambio competitivo respecto a la banca tradicional',
                    'Proceso 100% digital sin necesidad de ir a una sucursal',
                    'Operaciones disponibles de lunes a sábado en horario extendido',
                    'Atención vía WhatsApp (+51 910 624 404) y web (qoricash.pe)',
                    'Sin comisiones adicionales: el diferencial está en el tipo de cambio',
                    'Opción de tipo de cambio corporativo para empresas con RUC verificado',
                ], ensure_ascii=False),
                prohibited_claims=json.dumps([
                    'Mejor tipo de cambio del mercado (sin datos comparativos actualizados)',
                    'Número de clientes o volumen de operaciones (no publicar sin datos verificados)',
                    'Premios, rankings o reconocimientos (solo si están documentados)',
                    'Garantías de tasas futuras o predicciones del dólar',
                    'Comparaciones directas con bancos específicos sin datos del día',
                ], ensure_ascii=False),
                tone_guide='Natural, profesional y cercano. Español peruano. '
                           'Sin exceso de emojis (máximo 2 por publicación). '
                           'Evitar tecnicismos sin explicación. '
                           'Siempre distinguir tasa referencial BCRP de tasa comercial Qoricash.',
            )
            from app.extensions import db as _db
            _db.session.add(cfg)
            _db.session.commit()
        return cfg


# ── EntregaDiaria ──────────────────────────────────────────────────────────────

class EntregaDiaria(db.Model):
    """
    Registro de la entrega diaria del Estudio Creativo.
    Una fila por día (fecha único). Vinculada al pipeline 'diario' del día.
    """
    __tablename__ = 'entregas_diarias'

    id           = db.Column(db.Integer, primary_key=True)
    fecha        = db.Column(db.Date, nullable=False, unique=True)
    pipeline_id  = db.Column(db.Integer, db.ForeignKey('content_pipelines.id'))
    status       = db.Column(db.String(30), default='generando')
    # generando | listo | parcial | error
    noticias_ok  = db.Column(db.Integer, default=0)
    comercial_ok = db.Column(db.Integer, default=0)
    generado_at  = db.Column(db.DateTime)
    notas        = db.Column(db.Text)

    pipeline = db.relationship('ContentPipeline')

    @classmethod
    def get_today(cls):
        """Retorna la entrega de hoy, o None si no existe."""
        return cls.query.filter_by(fecha=_date.today()).first()

    @classmethod
    def get_or_create_today(cls, pipeline_id=None):
        """Retorna (entrega, created). Si no existe, crea con status='generando'."""
        entrega = cls.get_today()
        if entrega:
            return entrega, False
        entrega = cls(fecha=_date.today(), pipeline_id=pipeline_id, status='generando')
        db.session.add(entrega)
        db.session.flush()
        return entrega, True
