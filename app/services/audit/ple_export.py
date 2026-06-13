"""
Exportador PLE (Programa de Libros Electrónicos) — SUNAT
==========================================================
Genera archivos .txt en el formato exacto exigido por SUNAT para el
envío de Libros Electrónicos vía PLE o SLE-PLE.

Libros implementados:
  LE0301  — Libro Diario (Formato Simplificado — MYPE hasta 300 UIT)
  LE0801  — Registro de Ventas e Ingresos  (si aplica)
  LE0801  — Registro de Compras            (si aplica)

Para QoriCash (casa de cambio exonerada de IGV):
  - Registro de Ventas = vacío (actividad exonerada)
  - Registro de Compras = gastos con factura
  - Libro Diario Formato Simplificado = obligatorio

Estructura Libro Diario Formato Simplificado (LE030100):
  Campos: Periodo|CUO|Glosa|FechaAsiento|CodMoneda|CodCuentaContable|
          DenominacionCuenta|MontoDebe|MontoHaber|Indicador
  - Periodo    : YYYYMM
  - CUO        : Código Único de Operación (entry_number sin guiones)
  - Indicador  : 1=Activo 2=Anulado 8=Informativo
"""
import io
from datetime import date
from decimal import Decimal

from app.extensions import db

# Código de libro SUNAT para Diario Simplificado
LIBRO_DIARIO_SIMP = 'LE030100'


def _periodo_str(year: int, month: int) -> str:
    return f'{year}{month:02d}00'


def _cuo(entry_number: str) -> str:
    """AS-2026-0001 → AS20260001"""
    return entry_number.replace('-', '')


def _fmt_decimal(val) -> str:
    """Formatea Decimal a string con 2 decimales, sin separador de miles."""
    return f'{float(val or 0):.2f}'


def _nombre_cuenta(code: str, catalog: dict) -> str:
    acc = catalog.get(code)
    return acc.name if acc else f'Cuenta {code}'


def export_libro_diario_simplificado(year: int, month: int) -> bytes:
    """
    Genera el archivo .txt del Libro Diario Formato Simplificado
    en el formato PLE de SUNAT.

    Retorna los bytes del archivo listo para descarga.

    Formato por línea (pipe-delimited):
    Periodo|CUO|CorrelativoAsiento|FechaAsiento|CodMoneda|
    CodCuentaContable|DenominacionCuenta|MontoDebe|MontoHaber|
    AjusteIndicador|EstadoOperacion
    """
    from app.models.journal_entry import JournalEntry
    from app.models.journal_entry_line import JournalEntryLine
    from app.models.accounting_account import AccountingAccount
    from sqlalchemy import extract
    from sqlalchemy.orm import joinedload

    periodo = _periodo_str(year, month)

    catalog = {a.code: a for a in AccountingAccount.query.all()}

    entries = (
        JournalEntry.query
        .options(joinedload(JournalEntry.lines))
        .filter(
            extract('year',  JournalEntry.entry_date) == year,
            extract('month', JournalEntry.entry_date) == month,
        )
        .order_by(JournalEntry.entry_date.asc(), JournalEntry.id.asc())
        .all()
    )

    buf = io.StringIO()

    for entry in entries:
        estado = '1' if entry.status == 'activo' else '2'
        cuo    = _cuo(entry.entry_number)
        fecha  = entry.entry_date.strftime('%d/%m/%Y')
        glosa  = entry.description[:200].replace('|', ' ').replace('\n', ' ')

        for line in entry.lines:
            nombre = _nombre_cuenta(line.account_code, catalog).replace('|', ' ')
            row = (
                f'{periodo}|{cuo}|M001|{fecha}|PEN|'
                f'{line.account_code}|{nombre}|'
                f'{_fmt_decimal(line.debe)}|{_fmt_decimal(line.haber)}|'
                f'0|{estado}\r\n'
            )
            buf.write(row)

    content = buf.getvalue()
    buf.close()
    return content.encode('latin-1', errors='replace')


def export_registro_compras(year: int, month: int) -> bytes:
    """
    Genera el Registro de Compras (LE080100) para QoriCash.
    Solo incluye facturas de proveedores (voucher_type='factura').

    Campos SUNAT LE080100:
    Periodo|CUO|CorrelativoAsiento|FechaEmision|FechaVencimiento|
    TipoComprobante|SerieComprobante|NumeroComprobante|TipoDocProveedor|
    NumDocProveedor|NombreProveedor|MontoBI|MontoIGV|MontoTotal|
    MontoISC|MontoOtrosTributos|TotalCP|TipoMoneda|EstadoAnotacion
    """
    from app.models.expense_record import ExpenseRecord
    from sqlalchemy import extract

    periodo = _periodo_str(year, month)

    gastos = ExpenseRecord.query.filter(
        extract('year',  ExpenseRecord.expense_date) == year,
        extract('month', ExpenseRecord.expense_date) == month,
    ).order_by(ExpenseRecord.expense_date.asc()).all()

    buf = io.StringIO()

    for i, g in enumerate(gastos, 1):
        es_factura = (g.voucher_type or '').lower() in ('factura',)
        tipo_cp = '01' if es_factura else '03'  # 01=Factura, 03=Boleta

        ruc_tipo = '6' if (g.supplier_ruc and len(g.supplier_ruc) == 11) else '0'
        base    = _fmt_decimal(g.base_pen or g.amount_pen)
        igv     = _fmt_decimal(g.igv_pen or 0)
        total   = _fmt_decimal(g.amount_pen)
        fecha   = g.expense_date.strftime('%d/%m/%Y')
        voucher = (g.voucher_number or '').replace('|', ' ')
        serie   = voucher[:4] if len(voucher) >= 4 else ''
        numero  = voucher[4:] if len(voucher) > 4 else voucher
        proveedor = (g.supplier_name or 'SIN PROVEEDOR')[:100].replace('|', ' ')

        row = (
            f'{periodo}|M{i:06d}|1|{fecha}|-|'
            f'{tipo_cp}|{serie}|{numero}|'
            f'{ruc_tipo}|{g.supplier_ruc or ""}|{proveedor}|'
            f'{base}|{igv}|{total}|0.00|0.00|{total}|PEN|1\r\n'
        )
        buf.write(row)

    content = buf.getvalue()
    buf.close()
    return content.encode('latin-1', errors='replace')


def get_filename(libro: str, year: int, month: int, ruc: str = '20615113698') -> str:
    """
    Genera el nombre de archivo según la convención SUNAT:
    LE{RUC}{PERIODO}{LIBRO}{MONEDA}{ESTADO}.txt
    """
    periodo = f'{year}{month:02d}00'
    if libro == 'diario':
        codigo = '030100'
    elif libro == 'compras':
        codigo = '080100'
    else:
        codigo = '000000'
    return f'LE{ruc}{periodo}{codigo}00011.txt'
