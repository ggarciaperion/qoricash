"""
Modelos para el módulo TC Live — Pricing Engine interno de QoriCash.

DatatecEntry : audit log de cada actualización manual del precio DATATEC.
               A diferencia de DatatecRate (fila única), este modelo guarda
               un registro histórico completo para auditoría y análisis de drift.
"""
from app.extensions import db
from app.utils.formatters import now_peru


class DatatecEntry(db.Model):
    """
    Registro inmutable de cada actualización manual del precio DATATEC.
    Nunca se modifica — solo se inserta. Permite reconstruir historial
    y calcular drift temporal para el pricing engine.
    """
    __tablename__ = 'datatec_entries'

    id         = db.Column(db.Integer, primary_key=True)
    compra     = db.Column(db.Numeric(10, 4), nullable=False)
    venta      = db.Column(db.Numeric(10, 4), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now_peru)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    notes      = db.Column(db.String(300), nullable=True)

    user = db.relationship('User', foreign_keys=[user_id])

    __table_args__ = (
        db.Index('idx_datatec_entries_created', 'created_at'),
    )

    def to_dict(self) -> dict:
        return {
            'id':         self.id,
            'compra':     float(self.compra),
            'venta':      float(self.venta),
            'spread':     round(float(self.venta) - float(self.compra), 4),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'created_fmt': self.created_at.strftime('%d/%m %H:%M') if self.created_at else '—',
            'user':       self.user.username if self.user else 'sistema',
            'notes':      self.notes or '',
        }
