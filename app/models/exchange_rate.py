"""
Modelo para tipos de cambio
"""
from datetime import datetime
from app.extensions import db
from app.utils.formatters import now_peru

class ExchangeRate(db.Model):
    """
    Modelo para almacenar tipos de cambio actuales
    Solo debe haber un registro activo a la vez
    """
    __tablename__ = 'exchange_rates'

    id = db.Column(db.Integer, primary_key=True)

    # Tipos de cambio
    buy_rate = db.Column(db.Numeric(10, 4), nullable=False)  # Tipo de cambio de compra (cliente vende USD)
    sell_rate = db.Column(db.Numeric(10, 4), nullable=False)  # Tipo de cambio de venta (cliente compra USD)

    # Metadatos
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False, default=now_peru)

    # Relaciones
    updated_by_user = db.relationship('User', backref='exchange_rate_updates')

    def __repr__(self):
        return f'<ExchangeRate Compra: {self.buy_rate}, Venta: {self.sell_rate}>'

    def to_dict(self):
        """Convertir a diccionario para JSON"""
        return {
            'id': self.id,
            'compra': float(self.buy_rate),
            'venta': float(self.sell_rate),
            'updated_by': self.updated_by_user.username if self.updated_by_user else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    @staticmethod
    def get_current_rates():
        """
        Obtener tipos de cambio actuales
        Returns dict con 'compra' y 'venta'
        """
        rate = ExchangeRate.query.order_by(ExchangeRate.updated_at.desc()).first()

        if rate:
            return {
                'compra': float(rate.buy_rate),
                'venta': float(rate.sell_rate)
            }
        else:
            # Valores por defecto si no hay registros
            return {
                'compra': 3.75,
                'venta': 3.77
            }

    @staticmethod
    def update_rates(buy_rate, sell_rate, user_id):
        """
        Actualizar tipos de cambio

        Args:
            buy_rate: Tipo de cambio de compra
            sell_rate: Tipo de cambio de venta
            user_id: ID del usuario que actualiza

        Returns:
            ExchangeRate: Nuevo registro creado
        """
        new_rate = ExchangeRate(
            buy_rate=buy_rate,
            sell_rate=sell_rate,
            updated_by=user_id,
            updated_at=now_peru()
        )

        db.session.add(new_rate)
        db.session.commit()

        return new_rate
