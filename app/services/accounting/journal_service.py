"""
JournalService — Servicio central de contabilidad QoriCash.

Responsabilidades:
  - Crear asientos en el Libro Diario (partida doble)
  - Gestionar períodos contables (abrir/cerrar)
  - Generar asiento automático al completar una operación

Principio de aislamiento:
  - NUNCA lanza excepciones al caller de operaciones
  - Todos los métodos públicos capturan sus propios errores
  - Un fallo contable NO afecta el flujo de la operación
"""
import logging
from datetime import datetime, date as date_type
from decimal import Decimal

from app.extensions import db

logger = logging.getLogger(__name__)

# ── Mapeo banco → código PCGE ─────────────────────────────────────────────────
_PEN_ACCOUNTS = {
    'BCP':       '1041',
    'INTERBANK': '1048',
    'BANBIF':    '1049',    # en proceso de apertura
    'PICHINCHA': '1051',    # en proceso de apertura
}
_USD_ACCOUNTS = {
    'BCP':       '1044',
    'INTERBANK': '1047',
    'BANBIF':    '1050',    # en proceso de apertura
    'PICHINCHA': '1052',    # en proceso de apertura
}


def _map_bank(bank_str: str, currency: str) -> str:
    """
    Convierte un nombre de banco al código de cuenta PCGE.
    Acepta nombre directo ('BCP', 'BBVA', ...) o cualquier string con el nombre embebido.
    Fallback: '1041' (PEN) o '1044' (USD).
    """
    if not bank_str:
        return '1041' if currency == 'PEN' else '1044'
    s = bank_str.upper()
    mapping = _PEN_ACCOUNTS if currency == 'PEN' else _USD_ACCOUNTS
    for key, code in mapping.items():
        if key in s:
            return code
    return '1041' if currency == 'PEN' else '1044'


def _bank_from_client_accounts(client, account_number: str) -> str | None:
    """
    Busca el nombre del banco dado un número de cuenta en client.bank_accounts.
    Retorna el bank_name o None si no encuentra coincidencia.
    """
    if not client or not account_number:
        return None
    try:
        for acc in (client.bank_accounts or []):
            if str(acc.get('account_number', '')).strip() == str(account_number).strip():
                return acc.get('bank_name') or None
    except Exception:
        pass
    return None


def _distribute_pen(items: list, total_pen: Decimal, key: str = 'importe') -> list:
    """
    Distribuye total_pen entre los ítems proporcionalmente al campo `key`.
    El último ítem absorbe la diferencia de redondeo.
    Si todos los pesos son 0 reparte en partes iguales.
    Retorna lista de Decimal con len == len(items).
    """
    if not items:
        return []
    weights = [_safe_decimal(item.get(key, 0)) for item in items]
    total_w = sum(weights)
    result = []
    allocated = Decimal('0')
    for i, w in enumerate(weights):
        if i == len(weights) - 1:
            result.append(total_pen - allocated)
        else:
            if total_w > 0:
                amt = (w / total_w * total_pen).quantize(Decimal('0.01'))
            else:
                amt = (total_pen / len(weights)).quantize(Decimal('0.01'))
            result.append(amt)
            allocated += amt
    return result


def _safe_decimal(value, default=Decimal('0')) -> Decimal:
    try:
        return Decimal(str(value)) if value is not None else default
    except Exception:
        return default


# ─────────────────────────────────────────────────────────────────────────────
class JournalService:
    """Métodos estáticos — no requiere instancia."""

    # ── Períodos ──────────────────────────────────────────────────────────────

    @staticmethod
    def get_or_create_period(for_date: date_type):
        """
        Retorna el período contable para la fecha dada.
        Lo crea automáticamente si no existe (estado 'abierto').
        Usa flush() para obtener el ID sin hacer commit.
        """
        from app.models.accounting_period import AccountingPeriod

        period = AccountingPeriod.query.filter_by(
            year=for_date.year, month=for_date.month
        ).first()

        if not period:
            period = AccountingPeriod(
                year=for_date.year,
                month=for_date.month,
                status='abierto',
            )
            db.session.add(period)
            db.session.flush()
            logger.info(f'[Accounting] Período creado: {period.year}/{period.month:02d}')

        return period

    @staticmethod
    def close_period(year: int, month: int, user_id: int):
        """
        Cierra un período contable. Un período cerrado no acepta nuevos asientos.
        Retorna (success: bool, message: str)
        """
        from app.models.accounting_period import AccountingPeriod

        period = AccountingPeriod.query.filter_by(year=year, month=month).first()
        if not period:
            return False, 'Período no encontrado'
        if period.status == 'cerrado':
            return False, 'El período ya está cerrado'

        period.status = 'cerrado'
        period.closed_at = datetime.utcnow()
        period.closed_by = user_id
        db.session.commit()
        logger.info(f'[Accounting] Período cerrado: {year}/{month:02d} por user_id={user_id}')
        return True, f'Período {period.label} cerrado correctamente'

    # ── Numeración ────────────────────────────────────────────────────────────

    @staticmethod
    def _next_entry_number(year: int) -> str:
        """
        Genera el próximo número de asiento: AS-YYYY-NNNN.
        Usa SELECT FOR UPDATE sobre JournalSequence para garantizar
        secuencialidad sin huecos ni duplicados bajo carga concurrente (A-04).
        """
        from app.models.journal_sequence import JournalSequence

        seq = (
            db.session.query(JournalSequence)
            .filter_by(year=year)
            .with_for_update()
            .first()
        )
        if not seq:
            seq = JournalSequence(year=year, last_number=0)
            db.session.add(seq)
            db.session.flush()

        seq.last_number += 1
        db.session.flush()
        return f'AS-{year}-{seq.last_number:04d}'

    # ── Creación de asiento ───────────────────────────────────────────────────

    @staticmethod
    def create_entry(
        entry_type: str,
        description: str,
        lines: list,
        source_type: str = None,
        source_id: int = None,
        entry_date: date_type = None,
        created_by: int = None,
    ):
        """
        Crea un asiento contable completo (cabecera + líneas).

        Parámetros:
          entry_type  : 'operacion_completada' | 'calce_netting' | 'gasto' | 'manual' | ...
          description : Glosa del asiento
          lines       : Lista de dicts con claves:
                          account_code (str, obligatorio)
                          debe         (Decimal/float, default 0)
                          haber        (Decimal/float, default 0)
                          description  (str, opcional)
                          currency     (str, default 'PEN')
                          amount_usd   (Decimal, opcional)
                          exchange_rate (Decimal, opcional)
          source_type : Tipo de origen ('operation', 'match', 'manual')
          source_id   : ID del registro origen
          entry_date  : Fecha del asiento (default: hoy)
          created_by  : user.id

        Retorna: JournalEntry | None
        Nota: El CALLER debe hacer db.session.commit() o la llamada
              a create_entry ya incluye commit interno (ver _commit_entry).
        """
        from app.models.journal_entry import JournalEntry
        from app.models.journal_entry_line import JournalEntryLine

        if entry_date is None:
            entry_date = date_type.today()

        try:
            period = JournalService.get_or_create_period(entry_date)

            if period.status == 'cerrado':
                logger.warning(
                    f'[Accounting] Período {period.year}/{period.month:02d} cerrado '
                    f'— asiento tipo "{entry_type}" no registrado'
                )
                return None

            total_debe  = sum(_safe_decimal(l.get('debe',  0)) for l in lines)
            total_haber = sum(_safe_decimal(l.get('haber', 0)) for l in lines)

            entry_number = JournalService._next_entry_number(entry_date.year)

            entry = JournalEntry(
                entry_number=entry_number,
                period_id=period.id,
                entry_date=entry_date,
                description=description,
                entry_type=entry_type,
                source_type=source_type,
                source_id=source_id,
                total_debe=total_debe,
                total_haber=total_haber,
                status='activo',
                created_by=created_by,
            )
            db.session.add(entry)
            db.session.flush()   # obtener entry.id sin commit aún

            for i, line in enumerate(lines, start=1):
                jel = JournalEntryLine(
                    journal_entry_id=entry.id,
                    account_code=line['account_code'],
                    description=line.get('description'),
                    debe=_safe_decimal(line.get('debe', 0)),
                    haber=_safe_decimal(line.get('haber', 0)),
                    currency=line.get('currency', 'PEN'),
                    amount_usd=_safe_decimal(line['amount_usd']) if line.get('amount_usd') else None,
                    exchange_rate=_safe_decimal(line['exchange_rate']) if line.get('exchange_rate') else None,
                    line_order=i,
                )
                db.session.add(jel)

            db.session.commit()
            logger.info(
                f'[Accounting] ✅ Asiento {entry_number} | {entry_type} | '
                f'D:{total_debe} H:{total_haber}'
            )
            return entry

        except Exception as exc:
            db.session.rollback()
            logger.error(f'[Accounting] ❌ Error al crear asiento ({entry_type}): {exc}')
            return None

    # ── Hook automático: operación completada ─────────────────────────────────

    @staticmethod
    def create_entry_for_completed_operation(operation, created_by_id: int = None):
        """
        Genera el asiento de partida doble cuando una operación pasa a 'Completada'.

        COMPRA (cliente compra USD — QoriCash recibe PEN, entrega USD):
          DEBE  104x PEN  por cada abono del cliente (client_deposits_json)
          HABER 104x USD  por cada pago al cliente   (client_payments_json)

        VENTA (cliente vende USD — QoriCash recibe USD, entrega PEN):
          DEBE  104x USD  por cada abono del cliente (client_deposits_json)
          HABER 104x PEN  por cada pago al cliente   (client_payments_json)

        El banco exacto se determina buscando el número de cuenta en client.bank_accounts.
        Si hay múltiples abonos/pagos se crea una línea por cada uno (partición proporcional
        del total en PEN según el importe de cada movimiento).
        Si deposits/payments están vacíos usa source_account/destination_account como fallback.

        La GANANCIA (diferencial cambiario) se reconoce en el CALCE (netting),
        NO en este asiento — este asiento solo refleja movimientos bancarios.

        Retorna: JournalEntry | None  — NUNCA lanza excepciones.
        """
        try:
            amount_pen = _safe_decimal(operation.amount_pen)
            amount_usd = _safe_decimal(operation.amount_usd)
            tc         = _safe_decimal(operation.exchange_rate)

            if amount_pen <= 0:
                logger.warning(
                    f'[Accounting] Op {operation.operation_id}: amount_pen=0, asiento omitido'
                )
                return None

            client      = operation.client
            client_name = (client.full_name or client.razon_social or client.dni
                           ) if client else 'Cliente'
            op_type     = operation.operation_type   # 'Compra' | 'Venta'
            op_id       = operation.operation_id

            deposits = operation.client_deposits or []   # [{importe, cuenta_cargo, ...}]
            payments = operation.client_payments or []   # [{importe, cuenta_destino, ...}]

            lines = []

            # ── Función interna: DEBE lines ───────────────────────────────
            def _debe_lines(items, account_key, currency_in):
                """
                Crea líneas DEBE distribuyendo amount_pen entre los ítems.
                currency_in: 'PEN' o 'USD' (determina el código PCGE a usar).
                """
                pen_parts = _distribute_pen(items, amount_pen)
                result = []
                for item, pen_amt in zip(items, pen_parts):
                    if pen_amt <= 0:
                        continue
                    acct_num = item.get(account_key, '')
                    bank     = _bank_from_client_accounts(client, acct_num)
                    pcge     = _map_bank(bank or acct_num, currency_in)
                    usd_amt  = (pen_amt / tc).quantize(Decimal('0.01')) if tc > 0 else Decimal('0')
                    result.append({
                        'account_code': pcge,
                        'description':  f'Ingreso {currency_in} – {op_id}',
                        'debe':         pen_amt,
                        'haber':        Decimal('0'),
                        'currency':     currency_in,
                        **(({'amount_usd': usd_amt, 'exchange_rate': tc})
                           if currency_in == 'USD' else {}),
                    })
                return result

            # ── Función interna: HABER lines ──────────────────────────────
            def _haber_lines(items, account_key, currency_out):
                pen_parts = _distribute_pen(items, amount_pen)
                result = []
                for item, pen_amt in zip(items, pen_parts):
                    if pen_amt <= 0:
                        continue
                    acct_num = item.get(account_key, '')
                    bank     = _bank_from_client_accounts(client, acct_num)
                    pcge     = _map_bank(bank or acct_num, currency_out)
                    usd_amt  = (pen_amt / tc).quantize(Decimal('0.01')) if tc > 0 else Decimal('0')
                    result.append({
                        'account_code': pcge,
                        'description':  f'Egreso {currency_out} – {op_id}',
                        'debe':         Decimal('0'),
                        'haber':        pen_amt,
                        'currency':     currency_out,
                        **(({'amount_usd': usd_amt, 'exchange_rate': tc})
                           if currency_out == 'USD' else {}),
                    })
                return result

            if op_type == 'Compra':
                # ── DEBE: PEN que ingresaron (abonos del cliente) ─────────
                if deposits:
                    lines += _debe_lines(deposits, 'cuenta_cargo', 'PEN')
                else:
                    bank = _bank_from_client_accounts(client, operation.source_account)
                    pcge = _map_bank(bank or operation.source_account, 'PEN')
                    lines.append({'account_code': pcge,
                                  'description':  f'Ingreso PEN – {op_id}',
                                  'debe': amount_pen, 'haber': Decimal('0'),
                                  'currency': 'PEN'})

                # ── HABER: USD que salieron (pagos al cliente) ────────────
                if payments:
                    lines += _haber_lines(payments, 'cuenta_destino', 'USD')
                else:
                    bank    = _bank_from_client_accounts(client, operation.destination_account)
                    pcge    = _map_bank(bank or operation.destination_account, 'USD')
                    usd_amt = (amount_pen / tc).quantize(Decimal('0.01')) if tc > 0 else amount_usd
                    lines.append({'account_code': pcge,
                                  'description':  f'Egreso USD – {op_id}',
                                  'debe': Decimal('0'), 'haber': amount_pen,
                                  'currency': 'USD',
                                  'amount_usd': usd_amt, 'exchange_rate': tc})

                description = f'Compra USD – {op_id} – {client_name}'

            else:  # VENTA
                # ── DEBE: USD que ingresaron (abonos del cliente) ─────────
                if deposits:
                    lines += _debe_lines(deposits, 'cuenta_cargo', 'USD')
                else:
                    bank = _bank_from_client_accounts(client, operation.source_account)
                    pcge = _map_bank(bank or operation.source_account, 'USD')
                    lines.append({'account_code': pcge,
                                  'description':  f'Ingreso USD – {op_id}',
                                  'debe': amount_pen, 'haber': Decimal('0'),
                                  'currency': 'USD',
                                  'amount_usd': amount_usd, 'exchange_rate': tc})

                # ── HABER: PEN que salieron (pagos al cliente) ────────────
                if payments:
                    lines += _haber_lines(payments, 'cuenta_destino', 'PEN')
                else:
                    bank = _bank_from_client_accounts(client, operation.destination_account)
                    pcge = _map_bank(bank or operation.destination_account, 'PEN')
                    lines.append({'account_code': pcge,
                                  'description':  f'Egreso PEN – {op_id}',
                                  'debe': Decimal('0'), 'haber': amount_pen,
                                  'currency': 'PEN'})

                description = f'Venta USD – {op_id} – {client_name}'

            entry_date = (
                operation.completed_at.date()
                if operation.completed_at
                else date_type.today()
            )

            logger.info(
                f'[Accounting] Op {op_id} ({op_type}): '
                f'{len([l for l in lines if l["debe"]>0])} líneas DEBE, '
                f'{len([l for l in lines if l["haber"]>0])} líneas HABER'
            )

            return JournalService.create_entry(
                entry_type='operacion_completada',
                description=description,
                lines=lines,
                source_type='operation',
                source_id=operation.id,
                entry_date=entry_date,
                created_by=created_by_id,
            )

        except Exception as exc:
            logger.error(
                f'[Accounting] ❌ Error en create_entry_for_completed_operation '
                f'(op={getattr(operation, "operation_id", "?")}): {exc}'
            )
            return None
