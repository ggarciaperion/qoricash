"""
Modelo de cola de revisión del Lead Hunter IA.
Los leads encontrados pasan por aquí antes de entrar al CRM.
"""
from app.extensions import db
from app.utils.formatters import now_peru


class LeadHunterQueue(db.Model):
    """
    Cola de staging para leads encontrados por el agente IA.
    Estado: pendiente → aprobado (va al CRM) | rechazado (descartado)
    """
    __tablename__ = 'lead_hunter_queue'

    id                   = db.Column(db.Integer, primary_key=True)
    found_at             = db.Column(db.DateTime, default=now_peru, nullable=False)

    # Datos del lead
    razon_social         = db.Column(db.String(300))
    ruc                  = db.Column(db.String(20))
    rubro                = db.Column(db.String(150))
    departamento         = db.Column(db.String(100))
    provincia            = db.Column(db.String(100))
    distrito             = db.Column(db.String(100))
    email                = db.Column(db.String(200))
    telefono             = db.Column(db.String(200))
    web                  = db.Column(db.String(300))

    # Clasificación IA
    fuente               = db.Column(db.String(80))   # SUNAT-CIIU-4610 | PaginasAmarillas | etc
    score                = db.Column(db.Integer, default=0)   # 0-100
    potencial            = db.Column(db.String(20))   # alto | medio | bajo
    tamano_empresa       = db.Column(db.String(30))   # MYPE | Pequeña | Mediana | Grande
    volumen_estimado_usd = db.Column(db.Numeric(15, 2))
    accion_sugerida      = db.Column(db.Text)
    notas                = db.Column(db.Text)

    # Estado de revisión humana
    status               = db.Column(db.String(20), default='pendiente', nullable=False)
    # pendiente | aprobado | rechazado
    reviewed_by          = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    reviewed_at          = db.Column(db.DateTime, nullable=True)
    reject_reason        = db.Column(db.String(200))   # motivo de rechazo (opcional)

    # Si fue aprobado, ID del prospecto creado
    prospecto_id         = db.Column(db.Integer, db.ForeignKey('prospectos.id'), nullable=True)

    reviewer = db.relationship('User', foreign_keys=[reviewed_by])

    def to_dict(self):
        return {
            'id':                   self.id,
            'found_at':             self.found_at.strftime('%Y-%m-%d %H:%M') if self.found_at else '—',
            'razon_social':         self.razon_social or '—',
            'ruc':                  self.ruc or '—',
            'rubro':                self.rubro or '—',
            'departamento':         self.departamento or '—',
            'email':                self.email or '—',
            'telefono':             self.telefono or '—',
            'web':                  self.web or '—',
            'fuente':               self.fuente or '—',
            'score':                self.score or 0,
            'potencial':            self.potencial or '—',
            'tamano_empresa':       self.tamano_empresa or '—',
            'volumen_estimado_usd': float(self.volumen_estimado_usd) if self.volumen_estimado_usd else None,
            'accion_sugerida':      self.accion_sugerida or '—',
            'notas':                self.notas or '—',
            'status':               self.status,
            'reviewed_by':          self.reviewer.username if self.reviewer else None,
            'reviewed_at':          self.reviewed_at.strftime('%Y-%m-%d %H:%M') if self.reviewed_at else None,
            'prospecto_id':         self.prospecto_id,
        }
