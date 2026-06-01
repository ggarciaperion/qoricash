"""
Historial de saldos bancarios por día para QoriCash.

Cada vez que el operador actualiza un saldo en el módulo Posición,
se graba (o actualiza) un snapshot para la fecha del día.  Esto permite
que el Libro Caja y Bancos pueda reconstruir el saldo anterior de
cualquier período aunque no existan asientos contables previos.
"""
from app.extensions import db
from app.utils.formatters import now_peru


class BankBalanceHistory(db.Model):
    """Snapshot diario del saldo de cada cuenta bancaria."""

    __tablename__ = 'bank_balance_history'

    id            = db.Column(db.Integer, primary_key=True)

    # Fecha del snapshot (YYYY-MM-DD)
    snapshot_date = db.Column(db.Date, nullable=False, index=True)

    # Nombre completo de la cuenta, igual que BankBalance.bank_name
    # Ejemplo: "BCP PEN (191-12345678-0-01)"
    bank_name     = db.Column(db.String(100), nullable=False, index=True)

    # Saldo ACTUAL al momento de guardar
    balance_usd   = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    balance_pen   = db.Column(db.Numeric(15, 2), nullable=False, default=0)

    # Saldo INICIAL (apertura del día / período)
    initial_balance_usd = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    initial_balance_pen = db.Column(db.Numeric(15, 2), nullable=False, default=0)

    # Auditoría
    updated_by  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    updated_at  = db.Column(db.DateTime, default=now_peru, onupdate=now_peru)

    __table_args__ = (
        db.UniqueConstraint('snapshot_date', 'bank_name', name='uq_bbh_date_bank'),
    )

    def __repr__(self):
        return (f'<BankBalanceHistory {self.snapshot_date} {self.bank_name} '
                f'PEN={self.balance_pen} USD={self.balance_usd}>')
