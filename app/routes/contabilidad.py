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


@contabilidad_bp.route('/diario/nuevo', methods=['POST'])
@login_required
@require_role('Master')
def nuevo_asiento():
    """Crear un asiento manual con N líneas de debe/haber."""
    from app.services.accounting.journal_service import JournalService

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Sin datos'}), 400

    try:
        entry_date = date.fromisoformat(data.get('entry_date', str(date.today())))
        description = data.get('description', '').strip()
        raw_lines   = data.get('lines', [])

        if not description:
            return jsonify({'success': False, 'error': 'La glosa es obligatoria'}), 400
        if len(raw_lines) < 2:
            return jsonify({'success': False, 'error': 'Se requieren al menos 2 líneas'}), 400

        lines = []
        total_debe = Decimal('0')
        total_haber = Decimal('0')
        for l in raw_lines:
            debe  = Decimal(str(l.get('debe',  0) or 0))
            haber = Decimal(str(l.get('haber', 0) or 0))
            if not l.get('account_code'):
                return jsonify({'success': False, 'error': 'Todas las líneas requieren código de cuenta'}), 400
            lines.append({
                'account_code': l['account_code'].strip(),
                'description':  l.get('description', '').strip() or None,
                'debe':         debe,
                'haber':        haber,
                'currency':     l.get('currency', 'PEN'),
            })
            total_debe  += debe
            total_haber += haber

        diff = abs(total_debe - total_haber)
        if diff > Decimal('0.01'):
            return jsonify({
                'success': False,
                'error': f'El asiento no cuadra: DEBE {total_debe:.2f} ≠ HABER {total_haber:.2f}'
            }), 400

        entry = JournalService.create_entry(
            entry_type='manual',
            description=description,
            lines=lines,
            source_type='manual',
            source_id=None,
            entry_date=entry_date,
            created_by=current_user.id,
        )

        if entry:
            return jsonify({'success': True, 'entry_number': entry.entry_number})
        else:
            return jsonify({'success': False, 'error': 'Error al guardar el asiento. Revisa los logs.'}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@contabilidad_bp.route('/diario/<int:entry_id>/anular', methods=['POST'])
@login_required
@require_role('Master')
def anular_asiento(entry_id):
    """Anular un asiento: cambia status a 'anulado' y crea asiento inverso."""
    from app.models.journal_entry import JournalEntry
    from app.services.accounting.journal_service import JournalService

    data = request.get_json() or {}
    motivo = data.get('motivo', '').strip()
    if not motivo:
        return jsonify({'success': False, 'error': 'Se requiere motivo de anulación'}), 400

    entry = JournalEntry.query.get_or_404(entry_id)

    if entry.status == 'anulado':
        return jsonify({'success': False, 'error': 'El asiento ya está anulado'}), 400

    try:
        # Marcar original como anulado
        entry.status        = 'anulado'
        entry.annulled_at   = datetime.utcnow()
        entry.annulled_by   = current_user.id
        entry.annulled_reason = motivo
        db.session.flush()

        # Crear asiento inverso (contrapartida)
        lines = entry.lines.all() if hasattr(entry.lines, 'all') else list(entry.lines)
        inverse_lines = [{
            'account_code': l.account_code,
            'description':  f'Reversión: {l.description or entry.description}',
            'debe':         l.haber,   # invertir
            'haber':        l.debe,
            'currency':     l.currency or 'PEN',
        } for l in lines]

        JournalService.create_entry(
            entry_type='manual',
            description=f'ANULACIÓN: {entry.entry_number} — {motivo}',
            lines=inverse_lines,
            source_type='anulacion',
            source_id=entry.id,
            entry_date=date.today(),
            created_by=current_user.id,
        )

        # create_entry ya hace commit; si falla vuelve None pero el flag ya se guardó
        db.session.commit()
        return jsonify({'success': True, 'message': f'Asiento {entry.entry_number} anulado'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


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


# ── Libro Caja y Bancos ────────────────────────────────────────────────────────

# Mapa código PCGE → etiqueta legible
_ACCOUNT_LABELS = {
    '1011': ('Caja MN',        'PEN', 'efectivo'),
    '1012': ('Caja ME',        'USD', 'efectivo'),
    '1041': ('BCP PEN',        'PEN', 'banco'),
    '1042': ('BBVA PEN',       'PEN', 'banco'),
    '1043': ('Scotiabank PEN', 'PEN', 'banco'),
    '1044': ('BCP USD',        'USD', 'banco'),
    '1045': ('BBVA USD',       'USD', 'banco'),
    '1046': ('Scotiabank USD', 'USD', 'banco'),
}

# Cómo relacionar PCGE code → bank_name para conciliación
_CODE_TO_BANK = {
    '1041': 'BCP',  '1044': 'BCP',
    '1042': 'BBVA', '1045': 'BBVA',
    '1043': 'SCOTIABANK', '1046': 'SCOTIABANK',
}


def _caja_movimientos(year: int, month: int, account_code: str):
    """
    Retorna lista de movimientos de una cuenta en el período, ordenados por fecha.
    Cada item: {date, entry_number, description, debe, haber, saldo_acum}
    También retorna saldo_anterior (suma hasta fin del mes previo).
    """
    from app.models.journal_entry import JournalEntry
    from app.models.journal_entry_line import JournalEntryLine
    from sqlalchemy import func, extract
    import calendar

    # Saldo anterior = todo lo contabilizado antes del período actual
    first_day = date(year, month, 1)
    prev = db.session.query(
        func.sum(JournalEntryLine.debe).label('d'),
        func.sum(JournalEntryLine.haber).label('h'),
    ).join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id
    ).filter(
        JournalEntryLine.account_code == account_code,
        JournalEntry.entry_date < first_day,
        JournalEntry.status == 'activo',
    ).first()

    saldo_ant = Decimal(str(prev.d or 0)) - Decimal(str(prev.h or 0))

    # Movimientos del período
    rows = db.session.query(
        JournalEntry.entry_date,
        JournalEntry.entry_number,
        JournalEntry.description.label('entry_desc'),
        JournalEntryLine.description.label('line_desc'),
        JournalEntryLine.debe,
        JournalEntryLine.haber,
    ).join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id
    ).filter(
        JournalEntryLine.account_code == account_code,
        extract('year',  JournalEntry.entry_date) == year,
        extract('month', JournalEntry.entry_date) == month,
        JournalEntry.status == 'activo',
    ).order_by(
        JournalEntry.entry_date.asc(), JournalEntry.id.asc()
    ).all()

    movs = []
    saldo = saldo_ant
    for r in rows:
        debe  = Decimal(str(r.debe  or 0))
        haber = Decimal(str(r.haber or 0))
        saldo += debe - haber
        movs.append({
            'date':         r.entry_date,
            'entry_number': r.entry_number,
            'description':  r.line_desc or r.entry_desc,
            'debe':         debe,
            'haber':        haber,
            'saldo':        saldo,
        })

    total_debe  = sum(m['debe']  for m in movs)
    total_haber = sum(m['haber'] for m in movs)

    return {
        'code':        account_code,
        'label':       _ACCOUNT_LABELS.get(account_code, (f'Cta. {account_code}', 'PEN', 'otro'))[0],
        'currency':    _ACCOUNT_LABELS.get(account_code, ('', 'PEN', ''))[1],
        'kind':        _ACCOUNT_LABELS.get(account_code, ('', '', 'otro'))[2],
        'saldo_ant':   saldo_ant,
        'movimientos': movs,
        'total_debe':  total_debe,
        'total_haber': total_haber,
        'saldo_final': saldo_ant + total_debe - total_haber,
    }


@contabilidad_bp.route('/caja')
@login_required
@require_role('Master')
def caja():
    from app.models.bank_balance import BankBalance
    from app.models.accounting_period import AccountingPeriod
    from app.models.journal_entry_line import JournalEntryLine
    from app.models.journal_entry import JournalEntry
    from sqlalchemy import func, extract

    year  = request.args.get('year',  type=int, default=date.today().year)
    month = request.args.get('month', type=int, default=date.today().month)

    # Determinar qué cuentas tienen movimiento en el período o saldo anterior
    used_codes = {r[0] for r in db.session.query(JournalEntryLine.account_code).join(
        JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id
    ).filter(
        JournalEntry.status == 'activo',
    ).distinct().all()} & set(_ACCOUNT_LABELS.keys())

    # Si no hay nada en la DB, mostrar todas de todas formas
    codes_to_show = sorted(used_codes) if used_codes else sorted(_ACCOUNT_LABELS.keys())

    accounts = [_caja_movimientos(year, month, code) for code in codes_to_show]
    # Solo mostrar cuentas con saldo anterior != 0 o con movimientos en el período
    accounts = [a for a in accounts if a['movimientos'] or a['saldo_ant'] != 0]

    # Saldos reales del módulo de posición (para conciliación)
    bank_balances = {b.bank_name.upper(): b for b in BankBalance.query.all()}

    periods = AccountingPeriod.query.order_by(
        AccountingPeriod.year.desc(), AccountingPeriod.month.desc()
    ).all()

    return render_template(
        'contabilidad/caja.html',
        accounts=accounts,
        bank_balances=bank_balances,
        CODE_TO_BANK=_CODE_TO_BANK,
        periods=periods,
        selected_year=year,
        selected_month=month,
        user=current_user,
    )


@contabilidad_bp.route('/caja/export')
@login_required
@require_role('Master')
def export_caja():
    from app.models.bank_balance import BankBalance
    from app.models.journal_entry_line import JournalEntryLine
    from app.models.journal_entry import JournalEntry

    year  = request.args.get('year',  type=int, default=date.today().year)
    month = request.args.get('month', type=int, default=date.today().month)

    used_codes = {r[0] for r in db.session.query(JournalEntryLine.account_code).join(
        JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id
    ).filter(JournalEntry.status == 'activo').distinct().all()} & set(_ACCOUNT_LABELS.keys())

    codes = sorted(used_codes) if used_codes else sorted(_ACCOUNT_LABELS.keys())
    accounts = [_caja_movimientos(year, month, c) for c in codes]
    accounts = [a for a in accounts if a['movimientos'] or a['saldo_ant'] != 0]

    wb = openpyxl.Workbook()
    wb.remove(wb.active)  # quitamos hoja vacía default

    hfill  = PatternFill(start_color='1B3A6B', end_color='1B3A6B', fill_type='solid')
    sfill  = PatternFill(start_color='D6E4F0', end_color='D6E4F0', fill_type='solid')
    tfill  = PatternFill(start_color='E8F5E9', end_color='E8F5E9', fill_type='solid')
    thin   = Side(style='thin')
    bdr    = Border(left=thin, right=thin, top=thin, bottom=thin)

    for acc in accounts:
        ws = wb.create_sheet(f"{acc['code']} {acc['label']}"[:31])

        # Título
        ws.merge_cells('A1:F1')
        ws['A1'] = 'QORICASH TRADING S.A.C.'
        ws['A1'].font = Font(bold=True, size=12)
        ws['A1'].alignment = Alignment(horizontal='center')
        ws.merge_cells('A2:F2')
        ws['A2'] = (f"LIBRO CAJA Y BANCOS — {acc['code']} {acc['label']} "
                    f"({acc['currency']}) — {_month_name(month)} {year}")
        ws['A2'].font = Font(bold=True)
        ws['A2'].alignment = Alignment(horizontal='center')

        # Saldo anterior
        ws.merge_cells('A4:D4')
        ws['A4'] = 'SALDO ANTERIOR (al inicio del período)'
        ws['A4'].font = Font(bold=True)
        ws['A4'].fill = sfill
        ws['E4'] = float(max(acc['saldo_ant'], Decimal('0')))
        ws['F4'] = float(max(-acc['saldo_ant'], Decimal('0')))
        for c in 'ABCDEF':
            ws[f'{c}4'].border = bdr

        # Headers
        hdrs = ['N°', 'Fecha', 'N° Asiento', 'Descripción', 'DEBE', 'HABER', 'SALDO']
        for col, h in enumerate(hdrs, 1):
            cell = ws.cell(row=5, column=col, value=h)
            cell.fill = hfill
            cell.font = Font(bold=True, color='FFFFFF')
            cell.alignment = Alignment(horizontal='center')
            cell.border = bdr

        row = 6
        for n, m in enumerate(acc['movimientos'], 1):
            ws.cell(row=row, column=1, value=n).border = bdr
            ws.cell(row=row, column=2, value=m['date'].strftime('%d/%m/%Y')).border = bdr
            ws.cell(row=row, column=3, value=m['entry_number']).border = bdr
            ws.cell(row=row, column=4, value=m['description']).border = bdr
            ws.cell(row=row, column=5, value=float(m['debe'])).border = bdr
            ws.cell(row=row, column=6, value=float(m['haber'])).border = bdr
            ws.cell(row=row, column=7, value=float(m['saldo'])).border = bdr
            row += 1

        # Totales
        ws.cell(row=row, column=4, value='TOTAL DEL PERÍODO').font = Font(bold=True)
        ws.cell(row=row, column=5, value=float(acc['total_debe'])).font  = Font(bold=True)
        ws.cell(row=row, column=6, value=float(acc['total_haber'])).font = Font(bold=True)
        for c in range(1, 8):
            ws.cell(row=row, column=c).fill   = tfill
            ws.cell(row=row, column=c).border = bdr
        row += 1

        ws.cell(row=row, column=4, value='SALDO FINAL').font = Font(bold=True)
        ws.cell(row=row, column=7, value=float(acc['saldo_final'])).font = Font(bold=True)
        for c in range(1, 8):
            ws.cell(row=row, column=c).border = bdr

        widths = [5, 12, 16, 54, 14, 14, 14]
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

    if not wb.worksheets:
        ws = wb.create_sheet('Sin movimientos')
        ws['A1'] = 'No hay movimientos en cuentas de caja/bancos para el período seleccionado.'

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True,
                     download_name=f'libro_caja_bancos_{year}{month:02d}.xlsx')


# ── Libro de Ingresos y Gastos (LIG) ─────────────────────────────────────────

_INGRESO_LABELS = {
    '70': 'Ventas',
    '71': 'Variación de inventarios',
    '72': 'Producción de activo inmovilizado',
    '73': 'Descuentos, rebajas y bonificaciones obtenidas',
    '74': 'Descuentos, rebajas y bonificaciones concedidas',
    '75': 'Otros ingresos de gestión',
    '76': 'Ingresos excepcionales',
    '77': 'Diferencial cambiario',
    '78': 'Cargas cubiertas por provisiones',
    '79': 'Cargas imputables a cuentas de costos y gastos',
}


@contabilidad_bp.route('/lig')
@login_required
@require_role('Master')
def lig():
    """
    Libro de Ingresos y Gastos — formato SUNAT (RS 234-2006).
    Ingresos: líneas de asientos con cuentas 7xxx (ingresos PCGE).
    Gastos:   expense_records del período.
    """
    from app.models.journal_entry import JournalEntry
    from app.models.journal_entry_line import JournalEntryLine
    from app.models.expense_record import ExpenseRecord
    from app.models.accounting_period import AccountingPeriod
    from sqlalchemy import extract, func

    year  = request.args.get('year',  type=int, default=date.today().year)
    month = request.args.get('month', type=int, default=date.today().month)

    # Ingresos: líneas de cuentas 7xxx activas en el período
    rows = db.session.query(
        JournalEntry.entry_date,
        JournalEntry.entry_number,
        JournalEntry.description.label('entry_desc'),
        JournalEntry.entry_type,
        JournalEntryLine.account_code,
        JournalEntryLine.description.label('line_desc'),
        JournalEntryLine.haber,
    ).join(
        JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id
    ).filter(
        JournalEntryLine.account_code.like('7%'),
        JournalEntryLine.haber > 0,
        extract('year',  JournalEntry.entry_date) == year,
        extract('month', JournalEntry.entry_date) == month,
        JournalEntry.status == 'activo',
    ).order_by(
        JournalEntry.entry_date.asc(), JournalEntry.id.asc()
    ).all()

    ingresos = [{
        'fecha':        r.entry_date,
        'entry_number': r.entry_number,
        'entry_type':   r.entry_type,
        'account_code': r.account_code,
        'tipo_ingreso': _INGRESO_LABELS.get(r.account_code[:2], r.account_code),
        'description':  r.line_desc or r.entry_desc,
        'importe':      Decimal(str(r.haber or 0)),
    } for r in rows]

    # Gastos: expense_records del período
    gastos = ExpenseRecord.query.filter(
        extract('year',  ExpenseRecord.expense_date) == year,
        extract('month', ExpenseRecord.expense_date) == month,
    ).order_by(ExpenseRecord.expense_date.asc()).all()

    total_ingresos = sum(float(i['importe']) for i in ingresos)
    total_gastos   = sum(float(g.amount_pen or 0) for g in gastos)

    periods = AccountingPeriod.query.order_by(
        AccountingPeriod.year.desc(), AccountingPeriod.month.desc()
    ).all()

    return render_template(
        'contabilidad/lig.html',
        ingresos=ingresos,
        gastos=gastos,
        total_ingresos=total_ingresos,
        total_gastos=total_gastos,
        periods=periods,
        selected_year=year,
        selected_month=month,
        user=current_user,
    )


@contabilidad_bp.route('/lig/export')
@login_required
@require_role('Master')
def export_lig():
    """Exporta el LIG en Excel con dos hojas: Ingresos y Gastos."""
    from app.models.journal_entry import JournalEntry
    from app.models.journal_entry_line import JournalEntryLine
    from app.models.expense_record import ExpenseRecord
    from sqlalchemy import extract as sa_extract

    year  = request.args.get('year',  type=int, default=date.today().year)
    month = request.args.get('month', type=int, default=date.today().month)

    rows = db.session.query(
        JournalEntry.entry_date,
        JournalEntry.entry_number,
        JournalEntry.description.label('entry_desc'),
        JournalEntryLine.account_code,
        JournalEntryLine.description.label('line_desc'),
        JournalEntryLine.haber,
    ).join(
        JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id
    ).filter(
        JournalEntryLine.account_code.like('7%'),
        JournalEntryLine.haber > 0,
        sa_extract('year',  JournalEntry.entry_date) == year,
        sa_extract('month', JournalEntry.entry_date) == month,
        JournalEntry.status == 'activo',
    ).order_by(JournalEntry.entry_date.asc(), JournalEntry.id.asc()).all()

    ingresos = [{
        'fecha':        r.entry_date,
        'entry_number': r.entry_number,
        'account_code': r.account_code,
        'tipo_ingreso': _INGRESO_LABELS.get(r.account_code[:2], r.account_code),
        'description':  r.line_desc or r.entry_desc,
        'importe':      float(r.haber or 0),
    } for r in rows]

    gastos = ExpenseRecord.query.filter(
        sa_extract('year',  ExpenseRecord.expense_date) == year,
        sa_extract('month', ExpenseRecord.expense_date) == month,
    ).order_by(ExpenseRecord.expense_date.asc()).all()

    wb = openpyxl.Workbook()

    header_fill = PatternFill(start_color='1B3A6B', end_color='1B3A6B', fill_type='solid')
    hfont = Font(bold=True, color='FFFFFF')
    center = Alignment(horizontal='center')
    thin  = Side(style='thin')
    bdr   = Border(left=thin, right=thin, top=thin, bottom=thin)

    def title_rows(ws, titulo, ncols):
        col_letter = openpyxl.utils.get_column_letter(ncols)
        ws.merge_cells(f'A1:{col_letter}1')
        ws['A1'] = 'QORICASH TRADING S.A.C.'
        ws['A1'].font = Font(bold=True, size=12)
        ws['A1'].alignment = center
        ws.merge_cells(f'A2:{col_letter}2')
        ws['A2'] = titulo
        ws['A2'].font = Font(bold=True)
        ws['A2'].alignment = center
        ws.merge_cells(f'A3:{col_letter}3')
        ws['A3'] = f'Período: {_month_name(month)} {year}  —  R.M. MYPE Tributario'
        ws['A3'].alignment = center

    # ── Hoja 1: INGRESOS ──────────────────────────────────────────────────────
    ws1 = wb.active
    ws1.title = 'Ingresos'
    title_rows(ws1, f'LIBRO DE INGRESOS — {_month_name(month).upper()} {year}', 6)

    hdrs = ['N°', 'Fecha', 'N° Asiento', 'Tipo de Ingreso', 'Cuenta PCGE', 'Descripción', 'Importe S/']
    for c, h in enumerate(hdrs, 1):
        cell = ws1.cell(row=5, column=c, value=h)
        cell.fill = header_fill
        cell.font = hfont
        cell.alignment = center
        cell.border = bdr

    row = 6
    for n, ing in enumerate(ingresos, 1):
        ws1.cell(row=row, column=1, value=n).border = bdr
        ws1.cell(row=row, column=2, value=ing['fecha'].strftime('%d/%m/%Y')).border = bdr
        ws1.cell(row=row, column=3, value=ing['entry_number']).border = bdr
        ws1.cell(row=row, column=4, value=ing['tipo_ingreso']).border = bdr
        ws1.cell(row=row, column=5, value=ing['account_code']).border = bdr
        ws1.cell(row=row, column=6, value=ing['description']).border = bdr
        ws1.cell(row=row, column=7, value=ing['importe']).border = bdr
        row += 1

    # Fila de total
    ws1.cell(row=row, column=6, value='TOTAL').font = Font(bold=True)
    total_i = sum(i['importe'] for i in ingresos)
    ws1.cell(row=row, column=7, value=total_i).font = Font(bold=True)
    ws1.cell(row=row, column=7).fill = PatternFill(start_color='D4EDDA', end_color='D4EDDA', fill_type='solid')

    widths1 = [5, 12, 16, 28, 12, 54, 14]
    for i, w in enumerate(widths1, 1):
        ws1.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

    # ── Hoja 2: GASTOS ────────────────────────────────────────────────────────
    ws2 = wb.create_sheet('Gastos')
    title_rows(ws2, f'LIBRO DE GASTOS — {_month_name(month).upper()} {year}')

    hdrs2 = ['N°', 'Fecha', 'Proveedor', 'RUC', 'Tipo Comprobante',
             'N° Comprobante', 'Cta. PCGE', 'Importe S/', 'Descripción']
    for c, h in enumerate(hdrs2, 1):
        cell = ws2.cell(row=5, column=c, value=h)
        cell.fill = header_fill
        cell.font = hfont
        cell.alignment = center
        cell.border = bdr

    row2 = 6
    for n, g in enumerate(gastos, 1):
        ws2.cell(row=row2, column=1, value=n).border = bdr
        ws2.cell(row=row2, column=2, value=g.expense_date.strftime('%d/%m/%Y')).border = bdr
        ws2.cell(row=row2, column=3, value=g.supplier_name or '—').border = bdr
        ws2.cell(row=row2, column=4, value=g.supplier_ruc  or '—').border = bdr
        ws2.cell(row=row2, column=5, value=g.voucher_type  or '—').border = bdr
        ws2.cell(row=row2, column=6, value=g.voucher_number or '—').border = bdr
        ws2.cell(row=row2, column=7, value=g.category).border = bdr
        ws2.cell(row=row2, column=8, value=float(g.amount_pen)).border = bdr
        ws2.cell(row=row2, column=9, value=g.description).border = bdr
        row2 += 1

    ws2.cell(row=row2, column=7, value='TOTAL').font = Font(bold=True)
    total_g = sum(float(g.amount_pen) for g in gastos)
    ws2.cell(row=row2, column=8, value=total_g).font = Font(bold=True)
    ws2.cell(row=row2, column=8).fill = PatternFill(start_color='F8D7DA', end_color='F8D7DA', fill_type='solid')

    widths2 = [5, 12, 36, 14, 18, 16, 10, 14, 48]
    for i, w in enumerate(widths2, 1):
        ws2.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True,
                     download_name=f'LIG_qoricash_{year}{month:02d}.xlsx')


# ── Balance de Comprobación ────────────────────────────────────────────────────

@contabilidad_bp.route('/balance')
@login_required
@require_role('Master')
def balance():
    from app.models.journal_entry import JournalEntry
    from app.models.journal_entry_line import JournalEntryLine
    from app.models.accounting_account import AccountingAccount
    from app.models.accounting_period import AccountingPeriod
    from sqlalchemy import func, extract

    year  = request.args.get('year',  type=int, default=date.today().year)
    month = request.args.get('month', type=int, default=date.today().month)

    # Totales acumulados por cuenta en el período
    rows = db.session.query(
        JournalEntryLine.account_code,
        func.sum(JournalEntryLine.debe).label('total_debe'),
        func.sum(JournalEntryLine.haber).label('total_haber'),
    ).join(
        JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id
    ).filter(
        extract('year',  JournalEntry.entry_date) == year,
        extract('month', JournalEntry.entry_date) == month,
        JournalEntry.status == 'activo',
    ).group_by(
        JournalEntryLine.account_code
    ).order_by(
        JournalEntryLine.account_code
    ).all()

    # Catálogo para nombres y tipo
    catalog = {a.code: a for a in AccountingAccount.query.all()}

    accounts = []
    grand_debe = Decimal('0')
    grand_haber = Decimal('0')

    for r in rows:
        code = r.account_code
        acc  = catalog.get(code)
        td   = Decimal(str(r.total_debe  or 0))
        th   = Decimal(str(r.total_haber or 0))
        # Saldo según naturaleza de la cuenta
        if acc:
            if acc.nature == 'deudora':
                saldo_deudor  = max(td - th, Decimal('0'))
                saldo_acreedor = max(th - td, Decimal('0'))
            else:
                saldo_acreedor = max(th - td, Decimal('0'))
                saldo_deudor   = max(td - th, Decimal('0'))
            acc_type = acc.type
            acc_name = acc.name
        else:
            saldo_deudor   = max(td - th, Decimal('0'))
            saldo_acreedor = max(th - td, Decimal('0'))
            acc_type = _infer_type(code)
            acc_name = '(sin descripción)'

        accounts.append({
            'code':            code,
            'name':            acc_name,
            'type':            acc_type,
            'total_debe':      td,
            'total_haber':     th,
            'saldo_deudor':    saldo_deudor,
            'saldo_acreedor':  saldo_acreedor,
        })
        grand_debe  += td
        grand_haber += th

    periods = AccountingPeriod.query.order_by(
        AccountingPeriod.year.desc(), AccountingPeriod.month.desc()
    ).all()

    return render_template(
        'contabilidad/balance.html',
        accounts=accounts,
        grand_debe=grand_debe,
        grand_haber=grand_haber,
        grand_saldo_deudor=sum(a['saldo_deudor'] for a in accounts),
        grand_saldo_acreedor=sum(a['saldo_acreedor'] for a in accounts),
        periods=periods,
        selected_year=year,
        selected_month=month,
        user=current_user,
    )


@contabilidad_bp.route('/balance/export')
@login_required
@require_role('Master')
def export_balance():
    from app.models.journal_entry import JournalEntry
    from app.models.journal_entry_line import JournalEntryLine
    from app.models.accounting_account import AccountingAccount
    from sqlalchemy import func, extract

    year  = request.args.get('year',  type=int, default=date.today().year)
    month = request.args.get('month', type=int, default=date.today().month)

    rows = db.session.query(
        JournalEntryLine.account_code,
        func.sum(JournalEntryLine.debe).label('total_debe'),
        func.sum(JournalEntryLine.haber).label('total_haber'),
    ).join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id
    ).filter(
        extract('year',  JournalEntry.entry_date) == year,
        extract('month', JournalEntry.entry_date) == month,
        JournalEntry.status == 'activo',
    ).group_by(JournalEntryLine.account_code
    ).order_by(JournalEntryLine.account_code).all()

    catalog = {a.code: a for a in AccountingAccount.query.all()}

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Balance Comprobación'

    # Título
    ws.merge_cells('A1:F1')
    ws['A1'] = 'QORICASH TRADING S.A.C.'
    ws['A1'].font = Font(bold=True, size=12)
    ws['A1'].alignment = Alignment(horizontal='center')
    ws.merge_cells('A2:F2')
    ws['A2'] = f'BALANCE DE COMPROBACIÓN — {_month_name(month)} {year}'
    ws['A2'].font = Font(bold=True)
    ws['A2'].alignment = Alignment(horizontal='center')

    header_fill = PatternFill(start_color='1B3A6B', end_color='1B3A6B', fill_type='solid')
    headers = ['Código', 'Cuenta', 'Tipo', 'DEBE (S/)', 'HABER (S/)', 'Saldo Deudor', 'Saldo Acreedor']
    for col, h in enumerate(headers, 1):
        c = ws.cell(row=4, column=col, value=h)
        c.fill = header_fill
        c.font = Font(bold=True, color='FFFFFF')
        c.alignment = Alignment(horizontal='center')

    row = 5
    for r in rows:
        code = r.account_code
        acc  = catalog.get(code)
        td   = float(r.total_debe  or 0)
        th   = float(r.total_haber or 0)
        if acc and acc.nature == 'deudora':
            sd, sa = max(td - th, 0), max(th - td, 0)
        else:
            sa, sd = max(th - td, 0), max(td - th, 0)

        ws.cell(row=row, column=1, value=code)
        ws.cell(row=row, column=2, value=acc.name if acc else '(sin descripción)')
        ws.cell(row=row, column=3, value=acc.type if acc else _infer_type(code))
        ws.cell(row=row, column=4, value=td)
        ws.cell(row=row, column=5, value=th)
        ws.cell(row=row, column=6, value=sd)
        ws.cell(row=row, column=7, value=sa)
        row += 1

    for i, w in enumerate([10, 42, 12, 14, 14, 14, 14], 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True,
                     download_name=f'balance_comprobacion_{year}{month:02d}.xlsx')


# ── Estado de Resultados ───────────────────────────────────────────────────────

# UIT vigente (actualizar cada año)
_UIT = Decimal('5350')   # UIT 2026
_IR_TRAMO_1_LIMITE = _UIT * 15   # S/ 80,250
_IR_TRAMO_1_TASA   = Decimal('0.10')
_IR_TRAMO_2_TASA   = Decimal('0.295')


def _ir_mype(utilidad: Decimal) -> Decimal:
    """Cálculo IR Régimen MYPE Tributario (anual estimado sobre utilidad del período)."""
    if utilidad <= 0:
        return Decimal('0')
    if utilidad <= _IR_TRAMO_1_LIMITE:
        return (utilidad * _IR_TRAMO_1_TASA).quantize(Decimal('0.01'))
    else:
        t1 = _IR_TRAMO_1_LIMITE * _IR_TRAMO_1_TASA
        t2 = (utilidad - _IR_TRAMO_1_LIMITE) * _IR_TRAMO_2_TASA
        return (t1 + t2).quantize(Decimal('0.01'))


@contabilidad_bp.route('/resultados')
@login_required
@require_role('Master')
def resultados():
    from app.models.journal_entry import JournalEntry
    from app.models.journal_entry_line import JournalEntryLine
    from app.models.accounting_account import AccountingAccount
    from app.models.accounting_period import AccountingPeriod
    from sqlalchemy import func, extract

    year  = request.args.get('year',  type=int, default=date.today().year)
    month = request.args.get('month', type=int, default=date.today().month)

    rows = db.session.query(
        JournalEntryLine.account_code,
        func.sum(JournalEntryLine.debe).label('total_debe'),
        func.sum(JournalEntryLine.haber).label('total_haber'),
    ).join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id
    ).filter(
        extract('year',  JournalEntry.entry_date) == year,
        extract('month', JournalEntry.entry_date) == month,
        JournalEntry.status == 'activo',
    ).group_by(JournalEntryLine.account_code
    ).order_by(JournalEntryLine.account_code).all()

    catalog = {a.code: a for a in AccountingAccount.query.all()}

    # Clasificar por tipo para P&L
    ingresos = []
    gastos   = []

    for r in rows:
        code = r.account_code
        acc  = catalog.get(code)
        acc_type = acc.type if acc else _infer_type(code)
        acc_name = acc.name if acc else f'Cuenta {code}'
        td = Decimal(str(r.total_debe  or 0))
        th = Decimal(str(r.total_haber or 0))

        if acc_type == 'ingreso':
            # Cuentas de ingreso: naturaleza acreedora → saldo neto = haber - debe
            neto = max(th - td, Decimal('0'))
            if neto > 0:
                ingresos.append({'code': code, 'name': acc_name, 'monto': neto})

        elif acc_type == 'gasto':
            # Cuentas de gasto: naturaleza deudora → saldo neto = debe - haber
            neto = max(td - th, Decimal('0'))
            if neto > 0:
                gastos.append({'code': code, 'name': acc_name, 'monto': neto})

    total_ingresos = sum(i['monto'] for i in ingresos)
    total_gastos   = sum(g['monto'] for g in gastos)
    utilidad_antes_ir = total_ingresos - total_gastos
    ir_estimado = _ir_mype(utilidad_antes_ir)
    utilidad_neta = utilidad_antes_ir - ir_estimado

    periods = AccountingPeriod.query.order_by(
        AccountingPeriod.year.desc(), AccountingPeriod.month.desc()
    ).all()

    return render_template(
        'contabilidad/resultados.html',
        ingresos=ingresos,
        gastos=gastos,
        total_ingresos=total_ingresos,
        total_gastos=total_gastos,
        utilidad_antes_ir=utilidad_antes_ir,
        ir_estimado=ir_estimado,
        utilidad_neta=utilidad_neta,
        periods=periods,
        selected_year=year,
        selected_month=month,
        UIT=_UIT,
        IR_LIMITE=_IR_TRAMO_1_LIMITE,
        user=current_user,
    )


@contabilidad_bp.route('/resultados/export')
@login_required
@require_role('Master')
def export_resultados():
    from app.models.journal_entry import JournalEntry
    from app.models.journal_entry_line import JournalEntryLine
    from app.models.accounting_account import AccountingAccount
    from sqlalchemy import func, extract

    year  = request.args.get('year',  type=int, default=date.today().year)
    month = request.args.get('month', type=int, default=date.today().month)

    rows = db.session.query(
        JournalEntryLine.account_code,
        func.sum(JournalEntryLine.debe).label('total_debe'),
        func.sum(JournalEntryLine.haber).label('total_haber'),
    ).join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id
    ).filter(
        extract('year',  JournalEntry.entry_date) == year,
        extract('month', JournalEntry.entry_date) == month,
        JournalEntry.status == 'activo',
    ).group_by(JournalEntryLine.account_code
    ).order_by(JournalEntryLine.account_code).all()

    catalog = {a.code: a for a in AccountingAccount.query.all()}

    ingresos, gastos = [], []
    for r in rows:
        code = r.account_code
        acc  = catalog.get(code)
        acc_type = acc.type if acc else _infer_type(code)
        acc_name = acc.name if acc else f'Cuenta {code}'
        td = float(r.total_debe or 0)
        th = float(r.total_haber or 0)
        if acc_type == 'ingreso':
            neto = max(th - td, 0)
            if neto > 0:
                ingresos.append({'code': code, 'name': acc_name, 'monto': neto})
        elif acc_type == 'gasto':
            neto = max(td - th, 0)
            if neto > 0:
                gastos.append({'code': code, 'name': acc_name, 'monto': neto})

    total_i = sum(i['monto'] for i in ingresos)
    total_g = sum(g['monto'] for g in gastos)
    util    = total_i - total_g
    ir      = float(_ir_mype(Decimal(str(util))))
    util_n  = util - ir

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Estado de Resultados'

    header_fill = PatternFill(start_color='1B3A6B', end_color='1B3A6B', fill_type='solid')
    green_fill  = PatternFill(start_color='198754', end_color='198754', fill_type='solid')
    red_fill    = PatternFill(start_color='DC3545', end_color='DC3545', fill_type='solid')

    ws.merge_cells('A1:C1')
    ws['A1'] = 'QORICASH TRADING S.A.C.'
    ws['A1'].font = Font(bold=True, size=12)
    ws['A1'].alignment = Alignment(horizontal='center')
    ws.merge_cells('A2:C2')
    ws['A2'] = f'ESTADO DE RESULTADOS — {_month_name(month)} {year}'
    ws['A2'].font = Font(bold=True)
    ws['A2'].alignment = Alignment(horizontal='center')
    ws.merge_cells('A3:C3')
    ws['A3'] = 'Régimen MYPE Tributario'
    ws['A3'].alignment = Alignment(horizontal='center')

    def hrow(r, text, fill=None):
        ws.merge_cells(f'A{r}:C{r}')
        ws[f'A{r}'] = text
        ws[f'A{r}'].font = Font(bold=True, color='FFFFFF' if fill else '000000')
        if fill:
            for c in ['A', 'B', 'C']:
                ws[f'{c}{r}'].fill = fill

    def drow(r, code, name, monto):
        ws.cell(row=r, column=1, value=code)
        ws.cell(row=r, column=2, value=name)
        ws.cell(row=r, column=3, value=monto)
        ws.cell(row=r, column=3).number_format = '#,##0.00'

    row = 5
    hrow(row, 'INGRESOS', header_fill); row += 1
    for i in ingresos:
        drow(row, i['code'], i['name'], i['monto']); row += 1
    drow(row, '', 'TOTAL INGRESOS', total_i)
    ws.cell(row=row, column=3).font = Font(bold=True)
    ws.cell(row=row, column=3).fill = green_fill
    ws.cell(row=row, column=3).font = Font(bold=True, color='FFFFFF')
    row += 2

    hrow(row, 'GASTOS', header_fill); row += 1
    for g in gastos:
        drow(row, g['code'], g['name'], g['monto']); row += 1
    drow(row, '', 'TOTAL GASTOS', total_g)
    ws.cell(row=row, column=3).font = Font(bold=True)
    row += 2

    drow(row, '', 'UTILIDAD ANTES DE IR', util)
    ws.cell(row=row, column=3).font = Font(bold=True)
    row += 1
    drow(row, '', f'(-) IR MYPE Tributario', ir); row += 1
    drow(row, '', 'UTILIDAD NETA', util_n)
    ws.cell(row=row, column=3).font = Font(bold=True)
    ws.cell(row=row, column=3).fill = green_fill if util_n >= 0 else red_fill
    ws.cell(row=row, column=3).font = Font(bold=True, color='FFFFFF')

    ws.column_dimensions['A'].width = 10
    ws.column_dimensions['B'].width = 48
    ws.column_dimensions['C'].width = 16

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True,
                     download_name=f'estado_resultados_{year}{month:02d}.xlsx')


# ── Helper ─────────────────────────────────────────────────────────────────────

def _month_name(m: int) -> str:
    names = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']
    return names[m - 1] if 1 <= m <= 12 else str(m)


def _infer_type(code: str) -> str:
    """Inferir tipo de cuenta por el código PCGE cuando no está en el catálogo."""
    if code.startswith('1') or code.startswith('3'):
        return 'activo'
    if code.startswith('4') or code.startswith('46'):
        return 'pasivo'
    if code.startswith('5'):
        return 'patrimonio'
    if code.startswith('7'):
        return 'ingreso'
    if code.startswith('6'):
        return 'gasto'
    return 'activo'
