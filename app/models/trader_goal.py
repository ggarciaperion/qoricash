"""
Modelo de Metas Mensuales de Traders para QoriCash Trading V2
"""
from datetime import datetime
from app.extensions import db
from app.utils.formatters import now_peru


class TraderGoal(db.Model):
    """Modelo de Meta Mensual de Trader"""

    __tablename__ = 'trader_goals'

    # Primary Key
    id = db.Column(db.Integer, primary_key=True)

    # Foreign Key
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    # Periodo
    month = db.Column(db.Integer, nullable=False)  # 1-12
    year = db.Column(db.Integer, nullable=False)  # 2024, 2025, etc.

    # Meta comercial mensual en soles
    goal_amount_pen = db.Column(db.Numeric(15, 2), nullable=False, default=0)

    # Timestamps
    created_at = db.Column(db.DateTime, default=now_peru, nullable=False)
    updated_at = db.Column(db.DateTime, default=now_peru, onupdate=now_peru)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Relaciones
    trader = db.relationship('User', foreign_keys=[user_id], backref='goals')
    creator = db.relationship('User', foreign_keys=[created_by])

    # Constraints: un trader solo puede tener una meta por mes/año
    __table_args__ = (
        db.UniqueConstraint('user_id', 'month', 'year', name='uq_trader_month_year'),
        db.CheckConstraint('month >= 1 AND month <= 12', name='check_month_valid'),
        db.CheckConstraint('goal_amount_pen >= 0', name='check_goal_positive'),
    )

    def to_dict(self):
        """
        Convertir a diccionario

        Returns:
            dict: Representación de la meta
        """
        return {
            'id': self.id,
            'user_id': self.user_id,
            'trader_name': self.trader.username if self.trader else None,
            'trader_email': self.trader.email if self.trader else None,
            'month': self.month,
            'year': self.year,
            'goal_amount_pen': float(self.goal_amount_pen),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    @staticmethod
    def get_or_create_goal(user_id, month, year, goal_amount_pen=0, created_by_id=None):
        """
        Obtener o crear meta para un trader en un mes/año específico

        Args:
            user_id: ID del trader
            month: Mes (1-12)
            year: Año
            goal_amount_pen: Meta en soles
            created_by_id: ID del usuario que crea la meta

        Returns:
            TraderGoal: Meta encontrada o creada
        """
        goal = TraderGoal.query.filter_by(
            user_id=user_id,
            month=month,
            year=year
        ).first()

        if not goal:
            goal = TraderGoal(
                user_id=user_id,
                month=month,
                year=year,
                goal_amount_pen=goal_amount_pen,
                created_by=created_by_id
            )
            db.session.add(goal)
            db.session.commit()

        return goal

    def __repr__(self):
        return f'<TraderGoal {self.trader.username if self.trader else "Unknown"} {self.month}/{self.year} - S/ {self.goal_amount_pen}>'
