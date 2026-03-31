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
    'BCP':        '1041',
    'BBVA':       '1042',
    'SCOTIABANK': '1043',
    'INTERBANK':  '1041',   # fallback genérico si no tiene cuenta propia
    'BANBIF':     '1041',
}
_USD_ACCOUNTS = {
    'BCP':        '1044',
    'BBVA':       '1045',
    'SCOTIABANK': '1046',
    'INTERBANK':  '1044',
    'BANBIF':     '1044',
}


def _map_bank(bank_str: str, currency: str) -> str:
    """
    Convierte un nombre de banco (libre) al código de cuenta PCGE.
    Ejemplo: 'BCP PEN' → '1041', 'BBVA USD' → '1045'
    Fallback: '1041' (PEN) o '1044' (USD)
    """
    if not bank_str:
        return '1041' if currency == 'PEN' else '1044'
    s = bank_str.upper()
    mapping = _PEN_ACCOUNTS if currency == 'PEN' else _USD_ACCOUNTS
    for key, code in mapping.items():
        if key in s:
            return code
    return '1041' if currency == 'PEN' else '1044'


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
        """Genera el próximo número de asiento: AS-YYYY-NNNN (secuencial por año)."""
        from app.models.journal_entry import JournalEntry
        from sqlalchemy import func, extract

        count = db.session.query(func.count(JournalEntry.id)).filter(
            extract('year', JournalEntry.entry_date) == year
        ).scalar() or 0

        return f'AS-{year}-{(count + 1):04d}'

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

        COMPRA (cliente compra USD):
          Empresa RECIBE soles → ENTREGA dólares
          DEBE  104x Bancos PEN (banco donde ingresaron los soles)
          HABER 104x Bancos USD (banco de donde salieron los dólares, valorizado en PEN)

        VENTA (cliente vende USD):
          Empresa RECIBE dólares → ENTREGA soles
          DEBE  104x Bancos USD (banco donde ingresaron los dólares, valorizado en PEN)
          HABER 104x Bancos PEN (banco de donde salieron los soles)

        La GANANCIA (diferencial cambiario) se reconoce en el CALCE (netting),
        NO en este asiento — este asiento solo mueve los saldos bancarios.

        Retorna: JournalEntry | None
        Este método NUNCA lanza excepciones — cualquier error queda en el log.
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

            # Nombre del cliente para la glosa
            client = operation.client
            if client:
                client_name = client.full_name or client.razon_social or client.dni
            else:
                client_name = 'Cliente'

            op_type = operation.operation_type  # 'Compra' o 'Venta'

            # ── Determinar cuentas bancarias ────────────────────────────────
            if op_type == 'Compra':
                # source_account = banco donde el cliente depositó PEN
                # destination_account = banco de donde salieron los USD
                pen_account = _map_bank(operation.source_account, 'PEN')
                usd_account = _map_bank(operation.destination_account, 'USD')
                description = f'Compra USD – {operation.operation_id} – {client_name}'
                lines = [
                    {
                        'account_code': pen_account,
                        'description':  f'Ingreso PEN cliente – {operation.operation_id}',
                        'debe':         amount_pen,
                        'haber':        Decimal('0'),
                        'currency':     'PEN',
                    },
                    {
                        'account_code': usd_account,
                        'description':  f'Egreso USD cliente – {operation.operation_id}',
                        'debe':         Decimal('0'),
                        'haber':        amount_pen,   # valorizado en PEN
                        'currency':     'USD',
                        'amount_usd':   amount_usd,
                        'exchange_rate': tc,
                    },
                ]
            else:
                # VENTA
                # source_account = banco donde el cliente depositó USD
                # destination_account = banco de donde salieron los PEN
                usd_account = _map_bank(operation.source_account, 'USD')
                pen_account = _map_bank(operation.destination_account, 'PEN')
                description = f'Venta USD – {operation.operation_id} – {client_name}'
                lines = [
                    {
                        'account_code': usd_account,
                        'description':  f'Ingreso USD cliente – {operation.operation_id}',
                        'debe':         amount_pen,   # valorizado en PEN
                        'haber':        Decimal('0'),
                        'currency':     'USD',
                        'amount_usd':   amount_usd,
                        'exchange_rate': tc,
                    },
                    {
                        'account_code': pen_account,
                        'description':  f'Egreso PEN cliente – {operation.operation_id}',
                        'debe':         Decimal('0'),
                        'haber':        amount_pen,
                        'currency':     'PEN',
                    },
                ]

            # Usar la fecha de completado de la operación (no la fecha actual)
            entry_date = (
                operation.completed_at.date()
                if operation.completed_at
                else date_type.today()
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
            # Captura total — NUNCA debe propagar al caller
            logger.error(
                f'[Accounting] ❌ Error inesperado en '
                f'create_entry_for_completed_operation '
                f'(op={getattr(operation, "operation_id", "?")}): {exc}'
            )
            return None
