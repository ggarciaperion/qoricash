"""
Modelo de Amarre Contable (Match) para QoriCash Trading V2

Este modelo representa el emparejamiento entre operaciones de compra y venta
"""
from app.extensions import db
from app.utils.formatters import now_peru


class AccountingMatch(db.Model):
    """Modelo de amarre entre operaciones de compra y venta"""

    __tablename__ = 'accounting_matches'

    # Primary Key
    id = db.Column(db.Integer, primary_key=True)

    # Foreign Keys
    buy_operation_id = db.Column(db.Integer, db.ForeignKey('operations.id'), nullable=False, index=True)
    sell_operation_id = db.Column(db.Integer, db.ForeignKey('operations.id'), nullable=False, index=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('accounting_batches.id'), nullable=True, index=True)

    # Montos amarrados (puede ser parcial)
    matched_amount_usd = db.Column(db.Numeric(15, 2), nullable=False)  # Cuánto USD se amarró

    # Tipos de cambio
    buy_exchange_rate = db.Column(db.Numeric(10, 4), nullable=False)  # TC de compra
    sell_exchange_rate = db.Column(db.Numeric(10, 4), nullable=False)  # TC de venta

    # Utilidad
    profit_pen = db.Column(db.Numeric(15, 2), nullable=False)  # Utilidad en PEN
    profit_percentage = db.Column(db.Numeric(5, 4), nullable=True)  # % de utilidad

    # Estado
    status = db.Column(
        db.String(20),
        nullable=False,
        default='Activo'
    )  # Activo, Anulado

    # Metadatos
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=now_peru, nullable=False)
    updated_at = db.Column(db.DateTime, default=now_peru, onupdate=now_peru)

    # Relaciones
    buy_operation = db.relationship('Operation', foreign_keys=[buy_operation_id], backref='buy_matches')
    sell_operation = db.relationship('Operation', foreign_keys=[sell_operation_id], backref='sell_matches')
    batch = db.relationship('AccountingBatch', back_populates='matches')
    creator = db.relationship('User', foreign_keys=[created_by])

    def to_dict(self):
        """Convertir a diccionario"""
        return {
            'id': self.id,
            'buy_operation_id': self.buy_operation_id,
            'sell_operation_id': self.sell_operation_id,
            'batch_id': self.batch_id,
            'matched_amount_usd': float(self.matched_amount_usd),
            'buy_exchange_rate': float(self.buy_exchange_rate),
            'sell_exchange_rate': float(self.sell_exchange_rate),
            'profit_pen': float(self.profit_pen),
            'profit_percentage': float(self.profit_percentage) if self.profit_percentage else None,
            'status': self.status,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            # Información de operaciones
            'buy_operation_code': self.buy_operation.operation_id if self.buy_operation else None,
            'sell_operation_code': self.sell_operation.operation_id if self.sell_operation else None,
            'buy_client_name': self.buy_operation.client.full_name if self.buy_operation and self.buy_operation.client else None,
            'sell_client_name': self.sell_operation.client.full_name if self.sell_operation and self.sell_operation.client else None,
        }

    def __repr__(self):
        return f'<AccountingMatch {self.id}: Buy {self.buy_operation_id} <-> Sell {self.sell_operation_id}>'
