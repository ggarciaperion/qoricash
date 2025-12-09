"""
Modelo de Saldos Bancarios para QoriCash Trading V2
"""
from datetime import datetime
from app.extensions import db
from app.utils.formatters import now_peru


class BankBalance(db.Model):
    """Modelo de Saldo Bancario"""

    __tablename__ = 'bank_balances'

    # Primary Key
    id = db.Column(db.Integer, primary_key=True)

    # Nombre del banco
    bank_name = db.Column(db.String(100), nullable=False, index=True)

    # Saldos actuales
    balance_usd = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    balance_pen = db.Column(db.Numeric(15, 2), nullable=False, default=0)

    # Saldos iniciales
    initial_balance_usd = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    initial_balance_pen = db.Column(db.Numeric(15, 2), nullable=False, default=0)

    # Timestamps
    created_at = db.Column(db.DateTime, default=now_peru, nullable=False)
    updated_at = db.Column(db.DateTime, default=now_peru, onupdate=now_peru)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Relaciones
    updater = db.relationship('User', foreign_keys=[updated_by])

    # Constraints: un banco solo puede tener un registro
    __table_args__ = (
        db.UniqueConstraint('bank_name', name='uq_bank_name'),
        db.CheckConstraint('balance_usd >= 0', name='check_balance_usd_positive'),
        db.CheckConstraint('balance_pen >= 0', name='check_balance_pen_positive'),
    )

    def to_dict(self):
        """
        Convertir a diccionario

        Returns:
            dict: Representación del saldo bancario
        """
        # Obtener nombre del usuario que actualizó (con protección)
        updated_by_name = None
        try:
            if self.updated_by:
                updated_by_name = self.updater.username if self.updater else None
        except:
            updated_by_name = None

        return {
            'id': self.id,
            'bank_name': self.bank_name,
            'balance_usd': float(self.balance_usd),
            'balance_pen': float(self.balance_pen),
            'initial_balance_usd': float(self.initial_balance_usd),
            'initial_balance_pen': float(self.initial_balance_pen),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'updated_by': updated_by_name
        }

    @staticmethod
    def get_or_create_balance(bank_name, balance_usd=0, balance_pen=0):
        """
        Obtener o crear saldo para un banco

        Args:
            bank_name: Nombre del banco
            balance_usd: Saldo inicial en USD
            balance_pen: Saldo inicial en PEN

        Returns:
            BankBalance: Saldo encontrado o creado
        """
        balance = BankBalance.query.filter_by(bank_name=bank_name).first()

        if not balance:
            balance = BankBalance(
                bank_name=bank_name,
                balance_usd=balance_usd,
                balance_pen=balance_pen
            )
            db.session.add(balance)
            db.session.commit()

        return balance

    def __repr__(self):
        return f'<BankBalance {self.bank_name} - USD: {self.balance_usd} PEN: {self.balance_pen}>'
