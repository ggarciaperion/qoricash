"""
Modelo de Saldos Bancarios para QoriCash Trading V2
"""
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
    def apply_operation(operation):
        """
        Actualiza balance_usd / balance_pen automáticamente al completar una operación.

        Compra:  QoriCash recibe USD del cliente  → banco_usd.balance_usd += amount_usd
                 QoriCash entrega PEN al cliente  → banco_pen.balance_pen -= amount_pen

        Venta:   QoriCash recibe PEN del cliente  → banco_pen.balance_pen += amount_pen
                 QoriCash entrega USD al cliente  → banco_usd.balance_usd -= amount_usd

        El banco se determina por source_account → client.bank_accounts (misma lógica
        que get_bank_reconciliation).  Si no hay registro BankBalance para ese banco,
        se omite silenciosamente (el operador debe agregarlo primero desde el UI).
        """
        import logging
        _log = logging.getLogger(__name__)

        try:
            from app.config.bank_accounts import QORICASH_ACCOUNTS

            _banco_accts = {}
            for _b, _monedas in QORICASH_ACCOUNTS.items():
                _banco_accts[_b] = {}
                for _m, _d in _monedas.items():
                    _banco_accts[_b][_m] = f"{_b} {_m} ({_d['numero']})"

            _ALIASES = {
                'BCP': 'BCP', 'CREDITO': 'BCP', 'CRÉDITO': 'BCP',
                'INTERBANK': 'INTERBANK', 'IBK': 'INTERBANK',
                'BANBIF': 'BANBIF', 'BIF': 'BANBIF',
            }

            def _normalize(name):
                u = (name or '').upper()
                for alias, banco in _ALIASES.items():
                    if alias in u:
                        return banco
                return 'INTERBANK'

            # Determinar banco por cuenta origen del cliente
            banco = None
            try:
                if operation.source_account and operation.client:
                    for acct in (operation.client.bank_accounts or []):
                        if acct.get('account_number') == operation.source_account:
                            banco = _normalize(acct.get('bank_name', ''))
                            break
            except Exception:
                pass

            if banco is None:
                _log.debug(f'[BankBalance] Op {operation.operation_id}: banco no determinado, omitiendo auto-update.')
                return

            usd_acct = _banco_accts.get(banco, {}).get('USD')
            pen_acct = _banco_accts.get(banco, {}).get('PEN')
            usd = float(operation.amount_usd)
            pen = float(operation.amount_pen)

            def _update(acct_name, usd_delta, pen_delta):
                if not acct_name:
                    return
                bb = BankBalance.query.filter_by(bank_name=acct_name).first()
                if bb is None:
                    _log.debug(f'[BankBalance] {acct_name} no registrada, omitiendo.')
                    return
                if usd_delta:
                    bb.balance_usd = max(float(bb.balance_usd) + usd_delta, 0.0)
                if pen_delta:
                    bb.balance_pen = max(float(bb.balance_pen) + pen_delta, 0.0)
                bb.updated_at = now_peru()

            if operation.operation_type == 'Compra':
                _update(usd_acct, +usd, 0.0)
                _update(pen_acct, 0.0, -pen)
            else:  # Venta
                _update(pen_acct, 0.0, +pen)
                _update(usd_acct, -usd, 0.0)

            db.session.commit()
            _log.info(f'[BankBalance] Op {operation.operation_id} ({operation.operation_type}) '
                      f'aplicada a {banco}: USD{usd:+.2f} / PEN{pen:+.2f}')

        except Exception as exc:
            _log.error(f'[BankBalance] Error en apply_operation para {getattr(operation, "operation_id", "?")} : {exc}')
            try:
                db.session.rollback()
            except Exception:
                pass

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
