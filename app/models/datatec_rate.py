"""
Modelo para tasas de referencia DATATEC (precio interbancario spot USD/PEN).
Siempre hay un único registro activo — se actualiza in-place.
Campos:
  compra / venta       → precio de cierre
  compra_tarde / venta_tarde → precios tarde (indicativos)

PrecioBaseAccess: tabla simple que registra qué traders pueden ver
el widget de Precio Base (gestionado por Master desde el dashboard).
"""
from app.extensions import db
from app.utils.formatters import now_peru


class DatatecRate(db.Model):
    __tablename__ = 'datatec_rates'

    id           = db.Column(db.Integer, primary_key=True)
    compra       = db.Column(db.Numeric(10, 4), nullable=False, default=0)
    venta        = db.Column(db.Numeric(10, 4), nullable=False, default=0)
    compra_tarde = db.Column(db.Numeric(10, 4), nullable=True, default=None)
    venta_tarde  = db.Column(db.Numeric(10, 4), nullable=True, default=None)
    updated_by   = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    updated_at   = db.Column(db.DateTime, nullable=False, default=now_peru, onupdate=now_peru)

    updater = db.relationship('User', foreign_keys=[updated_by])

    def to_dict(self):
        return {
            'compra':       float(self.compra),
            'venta':        float(self.venta),
            'compra_tarde': float(self.compra_tarde) if self.compra_tarde is not None else None,
            'venta_tarde':  float(self.venta_tarde)  if self.venta_tarde  is not None else None,
            'updated_by':   self.updater.username if self.updater else None,
            'updated_at':   self.updated_at.isoformat() if self.updated_at else None,
        }

    @staticmethod
    def get():
        """Retorna el registro único o lo crea con valores 0."""
        row = DatatecRate.query.first()
        if not row:
            row = DatatecRate(compra=0, venta=0)
            db.session.add(row)
            db.session.commit()
        return row

    @staticmethod
    def update(compra, venta, compra_tarde, venta_tarde, user_id):
        row = DatatecRate.get()
        row.compra       = compra
        row.venta        = venta
        row.compra_tarde = compra_tarde
        row.venta_tarde  = venta_tarde
        row.updated_by   = user_id
        row.updated_at   = now_peru()
        db.session.commit()
        return row


class PrecioBaseAccess(db.Model):
    """Traders autorizados a ver el widget Precio Base (tabla nueva, no toca users)."""
    __tablename__ = 'precio_base_access'

    id      = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False, index=True)

    user = db.relationship('User', foreign_keys=[user_id])

    @staticmethod
    def has_access(user_id):
        return PrecioBaseAccess.query.filter_by(user_id=user_id).first() is not None

    @staticmethod
    def set_access(user_id, enabled):
        existing = PrecioBaseAccess.query.filter_by(user_id=user_id).first()
        if enabled and not existing:
            db.session.add(PrecioBaseAccess(user_id=user_id))
            db.session.commit()
        elif not enabled and existing:
            db.session.delete(existing)
            db.session.commit()
