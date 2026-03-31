"""
Rutas del módulo contable QoriCash — Libro Diario, Gastos, Períodos.
Solo accesible por rol Master.
"""
from flask import Blueprint, render_template, request, jsonify, send_file
from flask_login import login_required, current_user
from app.extensions import db
from app.utils.decorators import require_role
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

contabilidad_bp = Blueprint('contabilidad', __name__)


def _current_period_defaults():
    """Retorna year y month del período activo (hoy)."""
    today = date.today()
    return today.year, today.month


# ── Dashboard contable ─────────────────────────────────────────────────────────

@contabilidad_bp.route('/')
@contabilidad_bp.route('/dashboard')
@login_required
@require_role('Master')
def dashboard():
    from app.models.accounting_period import AccountingPeriod
    from app.models.journal_entry import JournalEntry
    from app.models.expense_record import ExpenseRecord
    from sqlalchemy import func, extract

    year, month = _current_period_defaults()

    # Período actual
    current_period = AccountingPeriod.query.filter_by(year=year, month=month).first()

    # Asientos del mes actual
    entries_this_month = JournalEntry.query.filter(
        extract('year', JournalEntry.entry_date) == year,
        extract('month', JournalEntry.entry_date) == month,
        JournalEntry.status == 'activo',
    ).order_by(JournalEntry.entry_date.desc()).limit(10).all()

    # Totales del mes
    totals = db.session.query(
        func.sum(JournalEntry.total_debe).label('debe'),
        func.sum(JournalEntry.total_haber).label('haber'),
        func.count(JournalEntry.id).label('count'),
    ).filter(
        extract('year', JournalEntry.entry_date) == year,
        extract('month', JournalEntry.entry_date) == month,
        JournalEntry.status == 'activo',
    ).first()

    # Gastos del mes
    gastos_total = db.session.query(
        func.sum(ExpenseRecord.amount_pen)
    ).filter(
        extract('year', ExpenseRecord.expense_date) == year,
        extract('month', ExpenseRecord.expense_date) == month,
    ).scalar() or Decimal('0')

    # Todos los períodos para el selector
    periods = AccountingPeriod.query.order_by(
        AccountingPeriod.year.desc(), AccountingPeriod.month.desc()
    ).all()

    return render_template(
        'contabilidad/dashboard.html',
        current_period=current_period,
        entries_this_month=entries_this_month,
        total_debe=totals.debe or Decimal('0'),
        total_haber=totals.haber or Decimal('0'),
        entries_count=totals.count or 0,
        gastos_total=gastos_total,
        periods=periods,
        selected_year=year,
        selected_month=month,
        user=current_user,
    )


# ── Libro Diario ───────────────────────────────────────────────────────────────

@contabilidad_bp.route('/diario')
@login_required
@require_role('Master')
def diario():
    from app.models.journal_entry import JournalEntry
    from app.models.accounting_period import AccountingPeriod

    year  = request.args.get('year',  type=int, default=date.today().year)
    month = request.args.get('month', type=int, default=date.today().month)
    status_filter = request.args.get('status', 'activo')

    q = JournalEntry.query.filter_by(status=status_filter)

    if year and month:
        from sqlalchemy import extract
        q = q.filter(
            extract('year',  JournalEntry.entry_date) == year,
            extract('month', JournalEntry.entry_date) == month,
        )
    elif year:
        from sqlalchemy import extract
        q = q.filter(extract('year', JournalEntry.entry_date) == year)

    entries = q.order_by(JournalEntry.entry_date.asc(), JournalEntry.id.asc()).all()

    periods = AccountingPeriod.query.order_by(
        AccountingPeriod.year.desc(), AccountingPeriod.month.desc()
    ).all()

    return render_template(
        'contabilidad/diario.html',
        entries=entries,
        periods=periods,
        selected_year=year,
        selected_month=month,
        status_filter=status_filter,
        user=current_user,
    )


@contabilidad_bp.route('/diario/<int:entry_id>/lines')
@login_required
@require_role('Master')
def entry_lines(entry_id):
    """API: líneas de un asiento (para el acordeón del diario)."""
    from app.models.journal_entry import JournalEntry

    entry = JournalEntry.query.get_or_404(entry_id)
    lines = entry.lines.all() if hasattr(entry.lines, 'all') else list(entry.lines)

    return jsonify([{
        'account_code': l.account_code,
        'description':  l.description or '',
        'debe':         float(l.debe or 0),
        'haber':        float(l.haber or 0),
        'currency':     l.currency or 'PEN',
        'amount_usd':   float(l.amount_usd) if l.amount_usd else None,
        'exchange_rate': float(l.exchange_rate) if l.exchange_rate else None,
    } for l in lines])


@contabilidad_bp.route('/diario/export')
@login_required
@require_role('Master')
def export_diario():
    """Exportar Libro Diario en Excel."""
    from app.models.journal_entry import JournalEntry
    from sqlalchemy import extract

    year  = request.args.get('year',  type=int, default=date.today().year)
    month = request.args.get('month', type=int, default=date.today().month)

    entries = JournalEntry.query.filter(
        extract('year',  JournalEntry.entry_date) == year,
        extract('month', JournalEntry.entry_date) == month,
        JournalEntry.status == 'activo',
    ).order_by(JournalEntry.entry_date.asc(), JournalEntry.id.asc()).all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Libro Diario'

    # Encabezado empresa
    ws.merge_cells('A1:H1')
    ws['A1'] = 'QORICASH TRADING S.A.C.'
    ws['A1'].font = Font(bold=True, size=12)
    ws['A1'].alignment = Alignment(horizontal='center')

    ws.merge_cells('A2:H2')
    ws['A2'] = f'LIBRO DIARIO — {_month_name(month)} {year}'
    ws['A2'].font = Font(bold=True)
    ws['A2'].alignment = Alignment(horizontal='center')

    ws.merge_cells('A3:H3')
    ws['A3'] = 'Régimen MYPE Tributario — PCGE'
    ws['A3'].alignment = Alignment(horizontal='center')

    # Headers tabla
    header_fill = PatternFill(start_color='1B3A6B', end_color='1B3A6B', fill_type='solid')
    header_font = Font(bold=True, color='FFFFFF')
    headers = ['N° Asiento', 'Fecha', 'Tipo', 'Descripción', 'Cta.', 'Glosa línea', 'DEBE (S/)', 'HABER (S/)']
    for col, h in enumerate(headers, 1):
        c = ws.cell(row=5, column=col, value=h)
        c.fill = header_fill
        c.font = header_font
        c.alignment = Alignment(horizontal='center')

    row = 6
    thin = Side(style='thin')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for entry in entries:
        lines = entry.lines.all() if hasattr(entry.lines, 'all') else list(entry.lines)
        first_line = True
        for line in lines:
            ws.cell(row=row, column=1, value=entry.entry_number if first_line else '').border = border
            ws.cell(row=row, column=2, value=entry.entry_date.strftime('%d/%m/%Y') if first_line else '').border = border
            ws.cell(row=row, column=3, value=entry.entry_type if first_line else '').border = border
            ws.cell(row=row, column=4, value=entry.description if first_line else '').border = border
            ws.cell(row=row, column=5, value=line.account_code).border = border
            ws.cell(row=row, column=6, value=line.description or '').border = border
            ws.cell(row=row, column=7, value=float(line.debe or 0)).border = border
            ws.cell(row=row, column=8, value=float(line.haber or 0)).border = border
            first_line = False
            row += 1
        # Fila de totales del asiento
        ws.cell(row=row, column=5, value='TOTAL ASIENTO').font = Font(bold=True)
        ws.cell(row=row, column=7, value=float(entry.total_debe)).font = Font(bold=True)
        ws.cell(row=row, column=8, value=float(entry.total_haber)).font = Font(bold=True)
        row += 1

    # Ajuste anchos
    widths = [16, 12, 22, 48, 8, 40, 14, 14]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    filename = f'libro_diario_qoricash_{year}{month:02d}.xlsx'
    return send_file(output,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True,
                     download_name=filename)


# ── Gastos ─────────────────────────────────────────────────────────────────────

@contabilidad_bp.route('/gastos')
@login_required
@require_role('Master')
def gastos():
    from app.models.expense_record import ExpenseRecord
    from app.models.accounting_period import AccountingPeriod
    from sqlalchemy import extract

    year  = request.args.get('year',  type=int, default=date.today().year)
    month = request.args.get('month', type=int, default=date.today().month)

    records = ExpenseRecord.query.filter(
        extract('year',  ExpenseRecord.expense_date) == year,
        extract('month', ExpenseRecord.expense_date) == month,
    ).order_by(ExpenseRecord.expense_date.desc()).all()

    periods = AccountingPeriod.query.order_by(
        AccountingPeriod.year.desc(), AccountingPeriod.month.desc()
    ).all()

    return render_template(
        'contabilidad/gastos.html',
        records=records,
        periods=periods,
        selected_year=year,
        selected_month=month,
        user=current_user,
    )


@contabilidad_bp.route('/gastos/nuevo', methods=['POST'])
@login_required
@require_role('Master')
def nuevo_gasto():
    """Registrar un gasto manualmente y crear su asiento contable."""
    from app.models.expense_record import ExpenseRecord
    from app.services.accounting.journal_service import JournalService

    data = request.get_json() or request.form

    try:
        expense_date = date.fromisoformat(data.get('expense_date', str(date.today())))
        amount_pen   = Decimal(str(data.get('amount_pen', 0)))

        record = ExpenseRecord(
            expense_date=expense_date,
            category=data.get('category', '6391'),
            description=data.get('description', ''),
            amount_pen=amount_pen,
            voucher_type=data.get('voucher_type') or None,
            voucher_number=data.get('voucher_number') or None,
            supplier_ruc=data.get('supplier_ruc') or None,
            supplier_name=data.get('supplier_name') or None,
            created_by=current_user.id,
        )

        # Obtener/crear período
        period = JournalService.get_or_create_period(expense_date)
        record.period_id = period.id
        db.session.add(record)
        db.session.flush()

        # Crear asiento contable del gasto
        account_code = data.get('category', '6391')
        entry = JournalService.create_entry(
            entry_type='gasto',
            description=f"Gasto: {record.description}",
            lines=[
                {
                    'account_code': account_code,
                    'description':  record.description,
                    'debe':         amount_pen,
                    'haber':        Decimal('0'),
                    'currency':     'PEN',
                },
                {
                    'account_code': '4699',   # Otras cuentas por pagar
                    'description':  f'Por pagar: {record.description}',
                    'debe':         Decimal('0'),
                    'haber':        amount_pen,
                    'currency':     'PEN',
                },
            ],
            source_type='expense',
            source_id=record.id,
            entry_date=expense_date,
            created_by=current_user.id,
        )
        if entry:
            record.journal_entry_id = entry.id

        db.session.commit()
        return jsonify({'success': True, 'message': 'Gasto registrado correctamente'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400


# ── Períodos ───────────────────────────────────────────────────────────────────

@contabilidad_bp.route('/periodos')
@login_required
@require_role('Master')
def periodos():
    from app.models.accounting_period import AccountingPeriod
    periods = AccountingPeriod.query.order_by(
        AccountingPeriod.year.desc(), AccountingPeriod.month.desc()
    ).all()
    return render_template(
        'contabilidad/periodos.html',
        periods=periods,
        user=current_user,
    )


@contabilidad_bp.route('/periodos/cerrar', methods=['POST'])
@login_required
@require_role('Master')
def cerrar_periodo():
    from app.services.accounting.journal_service import JournalService
    data = request.get_json() or request.form
    year  = int(data.get('year'))
    month = int(data.get('month'))
    success, message = JournalService.close_period(year, month, current_user.id)
    return jsonify({'success': success, 'message': message})


# ── Helper ─────────────────────────────────────────────────────────────────────

def _month_name(m: int) -> str:
    names = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']
    return names[m - 1] if 1 <= m <= 12 else str(m)
