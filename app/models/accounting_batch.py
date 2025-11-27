"""
Modelo de Lote Contable (Batch) para QoriCash Trading V2

Este modelo representa un conjunto de amarres contables agrupados (neteo)
"""
from app.extensions import db
from app.utils.formatters import now_peru
import json


class AccountingBatch(db.Model):
    """Modelo de lote de neteo contable"""

    __tablename__ = 'accounting_batches'

    # Primary Key
    id = db.Column(db.Integer, primary_key=True)

    # Identificador único del batch
    batch_code = db.Column(db.String(50), unique=True, nullable=False, index=True)

    # Descripción
    description = db.Column(db.String(500))

    # Fecha del neteo (puede ser diferente a la fecha de creación)
    netting_date = db.Column(db.Date, nullable=False, index=True)

    # Totales del batch
    total_buys_usd = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    total_buys_pen = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    total_sells_usd = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    total_sells_pen = db.Column(db.Numeric(15, 2), nullable=False, default=0)

    # Diferencia y utilidad
    difference_usd = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    total_profit_pen = db.Column(db.Numeric(15, 2), nullable=False, default=0)

    # Tipos de cambio promedio
    avg_buy_rate = db.Column(db.Numeric(10, 4), nullable=True)
    avg_sell_rate = db.Column(db.Numeric(10, 4), nullable=True)

    # Número de operaciones y matches
    num_matches = db.Column(db.Integer, nullable=False, default=0)
    num_buy_operations = db.Column(db.Integer, nullable=False, default=0)
    num_sell_operations = db.Column(db.Integer, nullable=False, default=0)

    # Asiento contable (JSON)
    # [{cuenta, debe, haber, glosa}, ...]
    accounting_entry_json = db.Column(db.Text, default='[]')

    # Estado
    status = db.Column(
        db.String(20),
        nullable=False,
        default='Abierto',
        index=True
    )  # Abierto, Cerrado, Anulado

    # Metadatos
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=now_peru, nullable=False)
    updated_at = db.Column(db.DateTime, default=now_peru, onupdate=now_peru)
    closed_at = db.Column(db.DateTime, nullable=True)

    # Relaciones
    matches = db.relationship('AccountingMatch', back_populates='batch', cascade='all, delete-orphan')
    creator = db.relationship('User', foreign_keys=[created_by])

    # Constraints
    __table_args__ = (
        db.CheckConstraint(
            status.in_(['Abierto', 'Cerrado', 'Anulado']),
            name='check_batch_status'
        ),
    )

    @property
    def accounting_entry(self):
        """Obtener asiento contable como lista"""
        try:
            return json.loads(self.accounting_entry_json or '[]')
        except:
            return []

    @accounting_entry.setter
    def accounting_entry(self, value):
        """Guardar asiento contable"""
        self.accounting_entry_json = json.dumps(value or [])

    def calculate_totals(self):
        """Calcular totales del batch basado en sus matches"""
        if not self.matches:
            return

        buy_ops = set()
        sell_ops = set()
        total_profit = 0
        total_buy_tc = 0
        total_sell_tc = 0
        count_buys = 0
        count_sells = 0

        for match in self.matches:
            if match.status == 'Activo':
                buy_ops.add(match.buy_operation_id)
                sell_ops.add(match.sell_operation_id)
                total_profit += float(match.profit_pen)
                total_buy_tc += float(match.buy_exchange_rate)
                total_sell_tc += float(match.sell_exchange_rate)
                count_buys += 1
                count_sells += 1

        # Calcular totales de operaciones únicas
        from app.models.operation import Operation
        buy_operations = Operation.query.filter(Operation.id.in_(buy_ops)).all()
        sell_operations = Operation.query.filter(Operation.id.in_(sell_ops)).all()

        self.total_buys_usd = sum(float(op.amount_usd) for op in buy_operations)
        self.total_buys_pen = sum(float(op.amount_pen) for op in buy_operations)
        self.total_sells_usd = sum(float(op.amount_usd) for op in sell_operations)
        self.total_sells_pen = sum(float(op.amount_pen) for op in sell_operations)

        self.difference_usd = self.total_sells_usd - self.total_buys_usd
        self.total_profit_pen = total_profit

        self.num_matches = len([m for m in self.matches if m.status == 'Activo'])
        self.num_buy_operations = len(buy_ops)
        self.num_sell_operations = len(sell_ops)

        self.avg_buy_rate = round(total_buy_tc / count_buys, 4) if count_buys > 0 else 0
        self.avg_sell_rate = round(total_sell_tc / count_sells, 4) if count_sells > 0 else 0

    def to_dict(self, include_matches=False):
        """Convertir a diccionario"""
        data = {
            'id': self.id,
            'batch_code': self.batch_code,
            'description': self.description,
            'netting_date': self.netting_date.isoformat() if self.netting_date else None,
            'total_buys_usd': float(self.total_buys_usd),
            'total_buys_pen': float(self.total_buys_pen),
            'total_sells_usd': float(self.total_sells_usd),
            'total_sells_pen': float(self.total_sells_pen),
            'difference_usd': float(self.difference_usd),
            'total_profit_pen': float(self.total_profit_pen),
            'avg_buy_rate': float(self.avg_buy_rate) if self.avg_buy_rate else None,
            'avg_sell_rate': float(self.avg_sell_rate) if self.avg_sell_rate else None,
            'num_matches': self.num_matches,
            'num_buy_operations': self.num_buy_operations,
            'num_sell_operations': self.num_sell_operations,
            'accounting_entry': self.accounting_entry,
            'status': self.status,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'closed_at': self.closed_at.isoformat() if self.closed_at else None,
            'created_by_name': self.creator.username if self.creator else None,
        }

        if include_matches:
            data['matches'] = [m.to_dict() for m in self.matches if m.status == 'Activo']

        return data

    @staticmethod
    def generate_batch_code():
        """Generar código de batch secuencial"""
        from app.utils.formatters import now_peru
        last_batch = AccountingBatch.query.order_by(AccountingBatch.id.desc()).first()

        if last_batch and last_batch.batch_code:
            try:
                last_num = int(last_batch.batch_code.split('-')[1])
                new_num = last_num + 1
            except (IndexError, ValueError):
                new_num = 1001
        else:
            new_num = 1001

        fecha = now_peru().strftime('%Y%m%d')
        return f'BATCH-{new_num:04d}-{fecha}'

    def __repr__(self):
        return f'<AccountingBatch {self.batch_code}>'
