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

            def _fallback_banco():
                """Banco fallback cuando no hay qc_bank: usa source_account → client.bank_accounts."""
                try:
                    if operation.source_account and operation.client:
                        for acct in (operation.client.bank_accounts or []):
                            if acct.get('account_number') == operation.source_account:
                                return _normalize(acct.get('bank_name', ''))
                    if getattr(operation, 'source_bank_name', None):
                        return _normalize(operation.source_bank_name)
                except Exception:
                    pass
                return None

            usd = float(operation.amount_usd)
            pen = float(operation.amount_pen)

            _payments = operation.client_payments or []
            _deposits = operation.client_deposits or []
            _has_pay_banks = any(p.get('qc_bank') for p in _payments)
            _has_dep_banks = any(d.get('qc_bank') for d in _deposits)

            def _update(acct_name, usd_delta, pen_delta):
                if not acct_name:
                    return
                bb = BankBalance.query.filter_by(bank_name=acct_name).first()
                if bb is None:
                    _log.debug(f'[BankBalance] {acct_name} no registrada, omitiendo.')
                    return
                if usd_delta:
                    new_usd = float(bb.balance_usd) + usd_delta
                    bb.balance_usd = max(new_usd, 0.0)
                if pen_delta:
                    new_pen = float(bb.balance_pen) + pen_delta
                    bb.balance_pen = max(new_pen, 0.0)
                bb.updated_at = now_peru()

            if operation.operation_type == 'Compra':
                # Depósitos: cliente → QoriCash en USD (inflows)
                if _has_dep_banks:
                    for dep in _deposits:
                        _b = _normalize(dep.get('qc_bank', ''))
                        _amt = float(dep.get('importe', 0))
                        if _b and _amt > 0:
                            _update(_banco_accts.get(_b, {}).get('USD'), +_amt, 0.0)
                else:
                    _b = _fallback_banco()
                    if _b:
                        _update(_banco_accts.get(_b, {}).get('USD'), +usd, 0.0)

                # Pagos: QoriCash → cliente en PEN (outflows)
                if _has_pay_banks:
                    for pay in _payments:
                        _b = _normalize(pay.get('qc_bank', ''))
                        _amt = float(pay.get('importe', 0))
                        if _b and _amt > 0:
                            _update(_banco_accts.get(_b, {}).get('PEN'), 0.0, -_amt)
                else:
                    _b = _fallback_banco()
                    if _b:
                        _update(_banco_accts.get(_b, {}).get('PEN'), 0.0, -pen)

            else:  # Venta
                # Depósitos: cliente → QoriCash en PEN (inflows)
                if _has_dep_banks:
                    for dep in _deposits:
                        _b = _normalize(dep.get('qc_bank', ''))
                        _amt = float(dep.get('importe', 0))
                        if _b and _amt > 0:
                            _update(_banco_accts.get(_b, {}).get('PEN'), 0.0, +_amt)
                else:
                    _b = _fallback_banco()
                    if _b:
                        _update(_banco_accts.get(_b, {}).get('PEN'), 0.0, +pen)

                # Pagos: QoriCash → cliente en USD (outflows)
                if _has_pay_banks:
                    for pay in _payments:
                        _b = _normalize(pay.get('qc_bank', ''))
                        _amt = float(pay.get('importe', 0))
                        if _b and _amt > 0:
                            _update(_banco_accts.get(_b, {}).get('USD'), -_amt, 0.0)
                else:
                    _b = _fallback_banco()
                    if _b:
                        _update(_banco_accts.get(_b, {}).get('USD'), -usd, 0.0)

            db.session.commit()
            _log.info(f'[BankBalance] Op {operation.operation_id} ({operation.operation_type}) '
                      f'aplicada (qc_bank multibank={_has_pay_banks or _has_dep_banks}): '
                      f'USD{usd:+.2f} / PEN{pen:+.2f}')

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
