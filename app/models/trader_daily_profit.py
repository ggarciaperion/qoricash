"""
Modelo de Utilidades Diarias de Traders para QoriCash Trading V2
"""
from datetime import datetime
from app.extensions import db
from app.utils.formatters import now_peru


class TraderDailyProfit(db.Model):
    """Modelo de Utilidad Diaria de Trader (ingreso manual)"""

    __tablename__ = 'trader_daily_profits'

    # Primary Key
    id = db.Column(db.Integer, primary_key=True)

    # Foreign Key
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    # Fecha de la utilidad
    profit_date = db.Column(db.Date, nullable=False, index=True)

    # Utilidad del día en soles (ingresada manualmente)
    profit_amount_pen = db.Column(db.Numeric(15, 2), nullable=False, default=0)

    # Timestamps
    created_at = db.Column(db.DateTime, default=now_peru, nullable=False)
    updated_at = db.Column(db.DateTime, default=now_peru, onupdate=now_peru)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Relaciones
    trader = db.relationship('User', foreign_keys=[user_id], backref='daily_profits')
    creator = db.relationship('User', foreign_keys=[created_by])

    # Constraints: un trader solo puede tener una utilidad por día
    __table_args__ = (
        db.UniqueConstraint('user_id', 'profit_date', name='uq_trader_profit_date'),
    )

    def to_dict(self):
        """
        Convertir a diccionario

        Returns:
            dict: Representación de la utilidad diaria
        """
        return {
            'id': self.id,
            'user_id': self.user_id,
            'trader_name': self.trader.username if self.trader else None,
            'trader_email': self.trader.email if self.trader else None,
            'profit_date': self.profit_date.isoformat() if self.profit_date else None,
            'profit_amount_pen': float(self.profit_amount_pen),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    @staticmethod
    def get_or_create_profit(user_id, profit_date, profit_amount_pen=0, created_by_id=None):
        """
        Obtener o crear utilidad diaria para un trader en una fecha específica

        Args:
            user_id: ID del trader
            profit_date: Fecha de la utilidad (date object)
            profit_amount_pen: Utilidad en soles
            created_by_id: ID del usuario que crea el registro

        Returns:
            TraderDailyProfit: Utilidad encontrada o creada
        """
        profit = TraderDailyProfit.query.filter_by(
            user_id=user_id,
            profit_date=profit_date
        ).first()

        if not profit:
            profit = TraderDailyProfit(
                user_id=user_id,
                profit_date=profit_date,
                profit_amount_pen=profit_amount_pen,
                created_by=created_by_id
            )
            db.session.add(profit)
            db.session.commit()

        return profit

    def __repr__(self):
        return f'<TraderDailyProfit {self.trader.username if self.trader else "Unknown"} {self.profit_date} - S/ {self.profit_amount_pen}>'
