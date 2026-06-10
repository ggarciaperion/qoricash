"""
Modelos del modulo de Prospeccion para QoriCash Trading V2
"""
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
    distrito               = db.Column(db.String(100))
    web                    = db.Column(db.String(300))

    # Contacto
    nombre_contacto        = db.Column(db.Text)
    cargo                  = db.Column(db.String(150))
    email                  = db.Column(db.String(200), index=True)
    email_alt              = db.Column(db.String(200))
    telefono               = db.Column(db.String(200))

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

    # CRM avanzado
    telefono_alt           = db.Column(db.String(200))
    tamano_empresa         = db.Column(db.String(30))   # MYPE | Pequeña | Mediana | Grande
    volumen_estimado_usd   = db.Column(db.Numeric(15, 2))
    prioridad              = db.Column(db.String(20))   # alta | media | baja

    # Campos extendidos MASTER v2
    direccion              = db.Column(db.String(300))
    subsector              = db.Column(db.String(150))
    telefono_3             = db.Column(db.String(50))
    telefono_4             = db.Column(db.String(50))
    email_3                = db.Column(db.String(200))
    email_4                = db.Column(db.String(200))
    facebook               = db.Column(db.String(300))
    instagram              = db.Column(db.String(300))
    linkedin               = db.Column(db.String(300))
    apellido_paterno       = db.Column(db.String(100))
    apellido_materno       = db.Column(db.String(100))
    contacto_wa            = db.Column(db.String(50))
    ultimo_precio          = db.Column(db.String(50))
    respuesta_campana      = db.Column(db.String(200))
    bandeja                = db.Column(db.String(80))

    creado_en              = db.Column(db.DateTime, default=now_peru)
    actualizado_en         = db.Column(db.DateTime, default=now_peru, onupdate=now_peru)

    # Relaciones
    asignaciones  = db.relationship("AsignacionProspecto", backref="prospecto",
                                    lazy="select", cascade="all, delete-orphan")
    actividades   = db.relationship("ActividadProspecto", backref="prospecto",
                                    lazy="select", cascade="all, delete-orphan",
                                    order_by="ActividadProspecto.creado_en.desc()")
    emails_extra  = db.relationship("ProspectoEmail", backref="prospecto",
                                    lazy="select", cascade="all, delete-orphan")

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

    @property
    def estado_fase(self):
        """Categoria canonica del estado para filtros y logica de negocio."""
        ec = self.estado_comercial or ""
        if ec in ("cliente", "P4"):
            return "cliente"
        if ec in ("negociando", "negociacion", "P3"):
            return "negociando"
        if ec in ("precio_enviado", "P2"):
            return "precio_enviado"
        if ec in ("presentado", "seguimiento", "P1"):
            return "presentado"
        return "sin_contactar"

    @property
    def estado_badge(self):
        """Retorna (bg_class, label) para mostrar el badge de estado."""
        mapa = {
            "presentado":    ("primary",   "Presentado"),
            "precio_enviado":("info",      "Precio enviado"),
            "negociando":    ("warning",   "Negociando"),
            "cliente":       ("success",   "Cliente"),
            # legacy
            "seguimiento":   ("primary",   "Presentado"),
            "negociacion":   ("warning",   "Negociando"),
            "P1":            ("primary",   "Presentado"),
            "P2":            ("info",      "Precio enviado"),
            "P3":            ("warning",   "Negociando"),
            "P4":            ("success",   "Cliente"),
        }
        return mapa.get(self.estado_comercial or "", ("secondary", "Sin contactar"))

    @property
    def trader_asignado(self):
        """Retorna el primer trader activo asignado, o None."""
        asig = next((a for a in self.asignaciones if a.activo), None)
        return asig.trader if asig else None

    def __repr__(self):
        return f"<Prospecto {self.email}>"


class AsignacionProspecto(db.Model):
    """Asignacion de un prospecto a un trader."""
    __tablename__ = "asignaciones_prospecto"

    id                   = db.Column(db.Integer, primary_key=True)
    prospecto_id         = db.Column(db.Integer, db.ForeignKey("prospectos.id"), nullable=False, index=True)
    trader_id            = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    activo               = db.Column(db.Boolean, default=True)
    asignado_por         = db.Column(db.Integer, db.ForeignKey("users.id"))
    asignado_en          = db.Column(db.DateTime, default=now_peru)
    dias_extra           = db.Column(db.Integer, default=0)       # días adicionales aprobados
    extension_solicitada = db.Column(db.Boolean, default=False)   # pendiente de aprobación

    trader     = db.relationship("User", foreign_keys=[trader_id], backref="prospectos_asignados")
    asignador  = db.relationship("User", foreign_keys=[asignado_por])

    __table_args__ = (
        db.UniqueConstraint("prospecto_id", "trader_id", name="uq_asignacion"),
    )


class ProspectoEmail(db.Model):
    """Emails adicionales por prospecto (inmutables, solo se desactivan)."""
    __tablename__ = "prospecto_emails"

    id           = db.Column(db.Integer, primary_key=True)
    prospecto_id = db.Column(db.Integer, db.ForeignKey("prospectos.id"), nullable=False, index=True)
    email        = db.Column(db.String(200), nullable=False)
    activo       = db.Column(db.Boolean, default=True)
    creado_en    = db.Column(db.DateTime, default=now_peru)

    def __repr__(self):
        return f"<ProspectoEmail {self.email} activo={self.activo}>"


class ActividadProspecto(db.Model):
    """Registro de actividades / seguimiento por prospecto — timeline unificado."""
    __tablename__ = "actividades_prospecto"

    id           = db.Column(db.Integer, primary_key=True)
    prospecto_id = db.Column(db.Integer, db.ForeignKey("prospectos.id"), nullable=False, index=True)
    user_id      = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    tipo         = db.Column(db.String(50))    # email / whatsapp / llamada / reunion / nota / estado / bounce / sistema
    canal        = db.Column(db.String(30))    # email / whatsapp / llamada / reunion / sistema / manual
    bandeja      = db.Column(db.String(100))   # ggarcia@qoricash.pe / gerencia@qoricash.pe
    descripcion  = db.Column(db.Text)
    resultado    = db.Column(db.String(200))
    nuevo_estado = db.Column(db.String(80))
    creado_en    = db.Column(db.DateTime, default=now_peru)

    usuario = db.relationship("User", foreign_keys=[user_id])

    def to_dict(self):
        return {
            "id":           self.id,
            "tipo":         self.tipo or "",
            "canal":        self.canal or "",
            "bandeja":      self.bandeja or "",
            "descripcion":  self.descripcion or "",
            "resultado":    self.resultado or "",
            "nuevo_estado": self.nuevo_estado or "",
            "usuario":      self.usuario.username if self.usuario else "",
            "creado_en":    self.creado_en.strftime("%d/%m/%Y %H:%M") if self.creado_en else "",
            "creado_iso":   self.creado_en.isoformat() if self.creado_en else "",
        }


class SeguimientoProspecto(db.Model):
    """Recordatorio / tarea programada para un prospecto."""
    __tablename__ = "seguimientos_prospecto"

    id               = db.Column(db.Integer, primary_key=True)
    prospecto_id     = db.Column(db.Integer, db.ForeignKey("prospectos.id"), nullable=False, index=True)
    user_id          = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    tipo             = db.Column(db.String(50))   # llamada / email / whatsapp / reunion / otro
    descripcion      = db.Column(db.Text)
    fecha_programada = db.Column(db.DateTime, nullable=False, index=True)
    completado       = db.Column(db.Boolean, default=False, nullable=False)
    completado_en    = db.Column(db.DateTime)
    creado_en        = db.Column(db.DateTime, default=now_peru)

    usuario   = db.relationship("User", foreign_keys=[user_id])
    prospecto = db.relationship("Prospecto", foreign_keys=[prospecto_id],
                                backref=db.backref("seguimientos", lazy="select",
                                                   cascade="all, delete-orphan",
                                                   order_by="SeguimientoProspecto.fecha_programada"))

    def to_dict(self):
        return {
            "id":               self.id,
            "tipo":             self.tipo or "",
            "descripcion":      self.descripcion or "",
            "fecha_programada": self.fecha_programada.strftime("%d/%m/%Y %H:%M") if self.fecha_programada else "",
            "fecha_iso":        self.fecha_programada.isoformat() if self.fecha_programada else "",
            "completado":       self.completado,
            "completado_en":    self.completado_en.strftime("%d/%m/%Y %H:%M") if self.completado_en else "",
            "usuario":          self.usuario.username if self.usuario else "",
            "vencido":          (not self.completado and self.fecha_programada < now_peru()) if self.fecha_programada else False,
        }
