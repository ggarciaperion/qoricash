"""
Modelos del modulo de Prospeccion para QoriCash Trading V2
"""
from datetime import datetime
from app.extensions import db
from app.utils.formatters import now_peru


class Prospecto(db.Model):
    """Registro de prospecto comercial."""
    __tablename__ = "prospectos"

    id                     = db.Column(db.Integer, primary_key=True)

    # Datos empresa
    razon_social           = db.Column(db.String(300))
    ruc                    = db.Column(db.String(20), index=True)
    tipo                   = db.Column(db.String(50))          # Empresa / Persona
    rubro                  = db.Column(db.String(150))
    departamento           = db.Column(db.String(100))
    provincia              = db.Column(db.String(100))

    # Contacto
    nombre_contacto        = db.Column(db.String(200))
    cargo                  = db.Column(db.String(150))
    email                  = db.Column(db.String(200), index=True)
    email_alt              = db.Column(db.String(200))
    telefono               = db.Column(db.String(50))

    # Clasificacion
    cliente_lfc            = db.Column(db.String(50))
    score                  = db.Column(db.Integer, default=0)
    clasificacion          = db.Column(db.String(80))
    canal                  = db.Column(db.String(80))
    fuente                 = db.Column(db.String(80))

    # Historial campaña
    remitente              = db.Column(db.String(100))
    tipo_ultimo_envio      = db.Column(db.String(80))
    fecha_primer_contacto  = db.Column(db.String(30))
    fecha_ultimo_contacto  = db.Column(db.String(30))
    fecha_proximo_contacto = db.Column(db.String(30))
    num_contactos          = db.Column(db.Integer, default=0)

    # Estado
    estado_email           = db.Column(db.String(80))
    estado_comercial       = db.Column(db.String(80))
    nivel_interes          = db.Column(db.String(80))
    grupo                  = db.Column(db.String(80))

    notas                  = db.Column(db.Text)
    creado_en              = db.Column(db.DateTime, default=now_peru)
    actualizado_en         = db.Column(db.DateTime, default=now_peru, onupdate=now_peru)

    # Relaciones
    asignaciones  = db.relationship("AsignacionProspecto", backref="prospecto",
                                    lazy="dynamic", cascade="all, delete-orphan")
    actividades   = db.relationship("ActividadProspecto", backref="prospecto",
                                    lazy="dynamic", cascade="all, delete-orphan",
                                    order_by="ActividadProspecto.creado_en.desc()")

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

    @property
    def score_color(self):
        s = self.score or 0
        if s >= 70: return "#B91C1C"
        if s >= 50: return "#3B82F6"
        if s >= 30: return "#22C55E"
        return "#94A3B8"

    @property
    def estado_badge(self):
        mapa = {
            "seguimiento": ("primary",   "En Seguimiento"),
            "negociacion": ("warning",   "En Negociacion"),
            "cliente":     ("success",   "Cliente"),
            # compatibilidad con estados anteriores
            "P1": ("primary",  "En Seguimiento"),
            "P2": ("primary",  "En Seguimiento"),
            "P3": ("warning",  "En Negociacion"),
            "P4": ("success",  "Cliente"),
        }
        return mapa.get(self.estado_comercial, ("secondary", "Sin contactar"))

    @property
    def trader_asignado(self):
        """Retorna el primer trader activo asignado, o None."""
        asig = self.asignaciones.filter_by(activo=True).first()
        return asig.trader if asig else None

    def __repr__(self):
        return f"<Prospecto {self.email}>"


class AsignacionProspecto(db.Model):
    """Asignacion de un prospecto a un trader."""
    __tablename__ = "asignaciones_prospecto"

    id           = db.Column(db.Integer, primary_key=True)
    prospecto_id = db.Column(db.Integer, db.ForeignKey("prospectos.id"), nullable=False, index=True)
    trader_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    activo       = db.Column(db.Boolean, default=True)
    asignado_por = db.Column(db.Integer, db.ForeignKey("users.id"))
    asignado_en  = db.Column(db.DateTime, default=now_peru)

    trader     = db.relationship("User", foreign_keys=[trader_id], backref="prospectos_asignados")
    asignador  = db.relationship("User", foreign_keys=[asignado_por])

    __table_args__ = (
        db.UniqueConstraint("prospecto_id", "trader_id", name="uq_asignacion"),
    )


class ActividadProspecto(db.Model):
    """Registro de actividades / seguimiento por prospecto."""
    __tablename__ = "actividades_prospecto"

    id           = db.Column(db.Integer, primary_key=True)
    prospecto_id = db.Column(db.Integer, db.ForeignKey("prospectos.id"), nullable=False, index=True)
    user_id      = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    tipo         = db.Column(db.String(50))   # email / llamada / reunion / nota / estado
    descripcion  = db.Column(db.Text)
    resultado    = db.Column(db.String(200))
    nuevo_estado = db.Column(db.String(80))
    creado_en    = db.Column(db.DateTime, default=now_peru)

    usuario = db.relationship("User", foreign_keys=[user_id])
