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
            from app.models.bank_movement import BankMovement

            _banco_accts = {}
            for _b, _monedas in QORICASH_ACCOUNTS.items():
                _banco_accts[_b] = {}
                for _m, _d in _monedas.items():
                    _banco_accts[_b][_m] = f"{_b} {_m} ({_d['numero']})"

            _ALIASES = {
                'BCP': 'BCP', 'CREDITO': 'BCP', 'CRÉDITO': 'BCP',
                'INTERBANK': 'INTERBANK', 'IBK': 'INTERBANK',
                'BANBIF': 'BANBIF', 'BIF': 'BANBIF',
                # Bancos externos → QoriCash opera vía transferencia interbancaria
                # desde sus cuentas INTERBANK (misma lógica que _map_bank en journal_service)
                'BBVA': 'INTERBANK', 'CONTINENTAL': 'INTERBANK',
                'SCOTIABANK': 'INTERBANK', 'SCOTIA': 'INTERBANK',
                'PICHINCHA': 'INTERBANK', 'NACION': 'INTERBANK',
                'NACIÓN': 'INTERBANK', 'GNB': 'INTERBANK',
                'RIPLEY': 'INTERBANK', 'FALABELLA': 'INTERBANK',
                'ALFIN': 'INTERBANK', 'MIBANCO': 'INTERBANK',
            }

            def _normalize(name):
                if not (name or '').strip():
                    return ''  # empty → banco indeterminado
                u = name.upper()
                for alias, banco in _ALIASES.items():
                    if alias in u:
                        return banco
                return 'INTERBANK'  # fallback: cualquier banco no reconocido opera vía interbancario INTERBANK

            def _fallback_banco_from_account(account_str):
                """Deriva banco de QoriCash desde el string de cuenta del cliente."""
                if not account_str:
                    return None
                return _normalize(account_str) or None

            def _fallback_banco():
                """Banco origen: Compra-USD / Venta-PEN (source_account del cliente)."""
                try:
                    if operation.source_account and operation.client:
                        for acct in (operation.client.bank_accounts or []):
                            if acct.get('account_number') == operation.source_account:
                                b = _normalize(acct.get('bank_name', ''))
                                if b:
                                    return b
                    if getattr(operation, 'source_bank_name', None):
                        b = _normalize(operation.source_bank_name)
                        if b:
                            return b
                    # Último recurso: derivar banco desde cuenta_cargo de los depósitos
                    for dep in (_deposits or []):
                        for key in ('cuenta_cargo', 'qc_bank', 'banco'):
                            b = _normalize(dep.get(key, ''))
                            if b:
                                return b
                except Exception:
                    pass
                return None

            def _fallback_banco_dest():
                """Banco destino: Compra-PEN / Venta-USD (destination_account del cliente)."""
                try:
                    if operation.destination_account and operation.client:
                        for acct in (operation.client.bank_accounts or []):
                            if acct.get('account_number') == operation.destination_account:
                                b = _normalize(acct.get('bank_name', ''))
                                if b:
                                    return b
                    if getattr(operation, 'destination_bank_name', None):
                        b = _normalize(operation.destination_bank_name)
                        if b:
                            return b
                    # Último recurso: derivar banco desde cuenta_destino de los pagos
                    for pay in (_payments or []):
                        for key in ('cuenta_destino', 'qc_bank', 'banco'):
                            b = _normalize(pay.get(key, ''))
                            if b:
                                return b
                except Exception:
                    pass
                return _fallback_banco()

            usd = float(operation.amount_usd)
            pen = float(operation.amount_pen)

            _payments = operation.client_payments or []
            _deposits = operation.client_deposits or []
            _has_pay_banks = any(p.get('qc_bank') for p in _payments)
            _has_dep_banks = any(d.get('qc_bank') for d in _deposits)

            def _update(acct_name, usd_delta, pen_delta, ref_code=None, counterpart=None):
                if not acct_name:
                    return
                _parts = acct_name.split()
                _bk    = _parts[0]   # BCP | INTERBANK | BANBIF
                _cur   = _parts[1]   # USD | PEN
                _delta = usd_delta if _cur == 'USD' else pen_delta
                if not _delta:
                    return

                # ── Actualizar BankBalance si existe (no bloquea la creación del ledger) ──
                bb = BankBalance.query.filter_by(bank_name=acct_name).first()
                _bal_after = None
                if bb is not None:
                    if usd_delta:
                        bb.balance_usd = round(float(bb.balance_usd) + usd_delta, 2)
                    if pen_delta:
                        bb.balance_pen = round(float(bb.balance_pen) + pen_delta, 2)
                    bb.updated_at = now_peru()
                    _bal_after = float(bb.balance_usd if _cur == 'USD' else bb.balance_pen)
                else:
                    _log.debug(f'[BankBalance] {acct_name} no registrada — solo ledger')

                # ── Crear BankMovement SIEMPRE (ledger inmutable — fuente de verdad) ──
                _mv_type = (BankMovement.TYPE_OP_ENTRADA
                            if _delta > 0 else BankMovement.TYPE_OP_SALIDA)
                _client_name = '—'
                try:
                    _client_name = (operation.client.full_name or '—') if operation.client else '—'
                except Exception:
                    pass
                mv = BankMovement(
                    movement_date  = now_peru(),
                    bank_name      = acct_name,
                    bank_key       = _bk,
                    currency       = _cur,
                    amount         = round(_delta, 2),
                    movement_type  = _mv_type,
                    source_type    = 'operation',
                    source_id      = operation.id,
                    operation_id   = operation.id,
                    description    = (f'{operation.operation_type} — {operation.operation_id}'
                                      f' — {_client_name}'),
                    reference_code = ref_code or operation.operation_id,
                    counterpart    = counterpart or _client_name,
                    balance_after  = round(_bal_after, 2) if _bal_after is not None else None,
                    closure_date   = now_peru().date(),
                )
                db.session.add(mv)

            if operation.operation_type == 'Compra':
                # Depósitos: cliente → QoriCash en USD (inflows)
                if _has_dep_banks:
                    _ua = 0.0
                    for dep in _deposits:
                        _b = _normalize(dep.get('qc_bank', '')) or _normalize(dep.get('cuenta_cargo', ''))
                        _amt = float(dep.get('importe', 0))
                        if _b and _amt > 0:
                            _update(_banco_accts.get(_b, {}).get('USD'), +_amt, 0.0)
                            _ua += _amt
                    if _ua == 0 and usd > 0:
                        _b = _fallback_banco()
                        if _b:
                            _update(_banco_accts.get(_b, {}).get('USD'), +usd, 0.0)
                else:
                    _b = _fallback_banco()
                    if _b:
                        _update(_banco_accts.get(_b, {}).get('USD'), +usd, 0.0)

                # Pagos PEN: QoriCash → cliente  (banco = cuenta DESTINO del cliente)
                if _has_pay_banks:
                    _pa = 0.0
                    for pay in _payments:
                        _b = _normalize(pay.get('qc_bank', '')) or _normalize(pay.get('cuenta_destino', ''))
                        _amt = float(pay.get('importe', 0))
                        if _b and _amt > 0:
                            _update(_banco_accts.get(_b, {}).get('PEN'), 0.0, -_amt)
                            _pa += _amt
                    if _pa == 0 and pen > 0:
                        _b = _fallback_banco_dest()
                        if _b:
                            _update(_banco_accts.get(_b, {}).get('PEN'), 0.0, -pen)
                else:
                    _b = _fallback_banco_dest()
                    if _b:
                        _update(_banco_accts.get(_b, {}).get('PEN'), 0.0, -pen)

            else:  # Venta
                # Depósitos PEN: cliente → QoriCash  (banco = cuenta ORIGEN del cliente)
                if _has_dep_banks:
                    _pa = 0.0
                    for dep in _deposits:
                        _b = _normalize(dep.get('qc_bank', '')) or _normalize(dep.get('cuenta_cargo', ''))
                        _amt = float(dep.get('importe', 0))
                        if _b and _amt > 0:
                            _update(_banco_accts.get(_b, {}).get('PEN'), 0.0, +_amt)
                            _pa += _amt
                    if _pa == 0 and pen > 0:
                        _b = _fallback_banco()
                        if _b:
                            _update(_banco_accts.get(_b, {}).get('PEN'), 0.0, +pen)
                else:
                    _b = _fallback_banco()
                    if _b:
                        _update(_banco_accts.get(_b, {}).get('PEN'), 0.0, +pen)

                # Pagos USD: QoriCash → cliente  (banco = cuenta DESTINO del cliente)
                if _has_pay_banks:
                    _ua = 0.0
                    for pay in _payments:
                        _b = _normalize(pay.get('qc_bank', '')) or _normalize(pay.get('cuenta_destino', ''))
                        _amt = float(pay.get('importe', 0))
                        if _b and _amt > 0:
                            _update(_banco_accts.get(_b, {}).get('USD'), -_amt, 0.0)
                            _ua += _amt
                    if _ua == 0 and usd > 0:
                        _b = _fallback_banco_dest()
                        if _b:
                            _update(_banco_accts.get(_b, {}).get('USD'), -usd, 0.0)
                else:
                    _b = _fallback_banco_dest()
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
