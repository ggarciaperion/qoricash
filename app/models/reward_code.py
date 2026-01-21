"""
Modelo de Código de Recompensa

Códigos generados cuando un cliente canjea 30 pips acumulados.
Cada código es único, de un solo uso, y no transferible.
"""
from app.extensions import db
from app.utils.formatters import now_peru
import secrets
import string


class RewardCode(db.Model):
    """Modelo de Código de Recompensa"""

    __tablename__ = 'reward_codes'

    # Primary Key
    id = db.Column(db.Integer, primary_key=True)

    # Código único de recompensa (6 caracteres alfanuméricos)
    code = db.Column(db.String(6), unique=True, nullable=False, index=True)

    # Cliente propietario del código
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)

    # Pips canjeados para generar este código
    pips_redeemed = db.Column(db.Float, nullable=False, default=0.0030)  # 30 pips = 0.003

    # Estado del código
    is_used = db.Column(db.Boolean, default=False)  # True si ya fue usado
    used_at = db.Column(db.DateTime)  # Cuándo se usó
    used_in_operation_id = db.Column(db.Integer, db.ForeignKey('operations.id'))  # Operación donde se usó

    # Timestamps
    created_at = db.Column(db.DateTime, default=now_peru, nullable=False)

    # Relaciones
    owner = db.relationship('Client', foreign_keys=[client_id], backref='reward_codes')
    operation_used = db.relationship('Operation', foreign_keys=[used_in_operation_id])

    @staticmethod
    def generate_unique_code():
        """Generar código único de 6 caracteres alfanuméricos"""
        while True:
            # Generar código aleatorio de 6 caracteres (letras mayúsculas y números)
            code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))

            # Verificar que no exista en la base de datos
            if not RewardCode.query.filter_by(code=code).first():
                return code

    def to_dict(self):
        """Convertir a diccionario"""
        return {
            'id': self.id,
            'code': self.code,
            'pips_redeemed': float(self.pips_redeemed),
            'is_used': self.is_used,
            'used_at': self.used_at.isoformat() if self.used_at else None,
            'used_in_operation_id': self.used_in_operation_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
