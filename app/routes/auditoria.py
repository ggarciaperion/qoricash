"""
Módulo de Auditoría Contable IA — Rutas Flask
===============================================
Dashboard + API del Agente Contable Autónomo.

Rutas:
  GET  /contabilidad/auditoria/              — Dashboard principal
  POST /contabilidad/auditoria/ejecutar      — Ejecutar auditoría manual
  GET  /contabilidad/auditoria/historial     — Historial de reportes
  GET  /contabilidad/auditoria/<id>          — Detalle de un reporte
  GET  /contabilidad/auditoria/api/ultimo    — Último reporte (JSON)
  GET  /contabilidad/auditoria/ple/diario    — Descarga PLE Libro Diario
  GET  /contabilidad/auditoria/ple/compras   — Descarga PLE Registro Compras
  POST /contabilidad/auditoria/depreciar     — Ejecutar depreciación mensual
"""
import logging
from datetime import date, datetime

from flask import (Blueprint, render_template, jsonify, request,
                   send_file, redirect, url_for)
from flask_login import login_required, current_user
from io import BytesIO

from app.extensions import db, csrf
from app.utils.decorators import require_role
from app.utils.formatters import now_peru

_log = logging.getLogger(__name__)

auditoria_bp = Blueprint('auditoria', __name__)


# ── Dashboard principal ───────────────────────────────────────────────────────

@auditoria_bp.route('/')
@login_required
@require_role('Master')
def dashboard():
    from app.models.audit_report import AuditReport

    # Último reporte
    ultimo = AuditReport.query.order_by(
        AuditReport.audit_date.desc(),
        AuditReport.id.desc()
    ).first()

    # Historial últimos 30 días
    historial = AuditReport.query.order_by(
        AuditReport.audit_date.desc(),
        AuditReport.id.desc()
    ).limit(30).all()

    today = date.today()

    return render_template(
        'auditoria/dashboard.html',
        ultimo=ultimo,
        historial=historial,
        today=today,
        user=current_user,
    )


# ── Ejecutar auditoría manual ─────────────────────────────────────────────────

@auditoria_bp.route('/ejecutar', methods=['POST'])
@csrf.exempt
@login_required
@require_role('Master')
def ejecutar():
    from app.services.audit.audit_engine import AuditEngine

    data  = request.get_json() or {}
    year  = int(data.get('year',  date.today().year))
    month = int(data.get('month', date.today().month))
    auto_depreciate = bool(data.get('auto_depreciate', True))

    try:
        engine = AuditEngine(
            year=year,
            month=month,
            audit_date=date.today(),
            trigger='manual',
            executed_by_id=current_user.id,
            auto_depreciate=auto_depreciate,
        )
        report = engine.run()

        message = (
            f'Auditoría {month:02d}/{year} completada. '
            f'Estado: {report.estado}. '
            f'{report.total_hallazgos} hallazgo(s).'
        )

        # ── Actualizar AgentStatus para mantener métricas en sync ───────────
        try:
            from app.models.agent import AgentStatus, AgentLog
            from datetime import timedelta
            s = AgentStatus.query.filter_by(agent_id='accounting_audit').first()
            if s:
                s.tasks_today = (s.tasks_today or 0) + 1
                s.total_tasks = (s.total_tasks or 0) + 1
                s.last_run    = datetime.utcnow()
                s.next_run    = datetime.utcnow() + timedelta(hours=1)
                s.status      = 'idle'
                s.last_result = (f'Manual ({current_user.username}): '
                                 f'{report.total_hallazgos} hallazgos. {report.estado}.')
                s.last_error  = None
                db.session.add(AgentLog(
                    agent_id='accounting_audit',
                    level='SUCCESS',
                    message=f'Auditoría manual — {report.estado}',
                    detail=(f'{report.total_hallazgos} hallazgos, '
                            f'{report.hallazgos_criticos} críticos. '
                            f'Ejecutado por {current_user.username}.'),
                ))
                db.session.commit()
        except Exception as e_agent:
            _log.warning(f'[Auditoria] No se pudo actualizar AgentStatus: {e_agent}')

        return jsonify({
            'success': True,
            'report':  report.to_dict(),
            'message': message,
        })
    except Exception as exc:
        _log.exception('[Auditoria] Error al ejecutar auditoría manual')
        return jsonify({'success': False, 'error': str(exc)}), 500


# ── Historial ─────────────────────────────────────────────────────────────────

@auditoria_bp.route('/historial')
@login_required
@require_role('Master')
def historial():
    from app.models.audit_report import AuditReport

    page = request.args.get('page', 1, type=int)
    reportes = AuditReport.query.order_by(
        AuditReport.audit_date.desc(),
        AuditReport.id.desc()
    ).paginate(page=page, per_page=20, error_out=False)

    return jsonify({
        'success': True,
        'reportes': [r.to_dict() for r in reportes.items],
        'total':    reportes.total,
        'pages':    reportes.pages,
        'page':     page,
    })


# ── Detalle de un reporte ─────────────────────────────────────────────────────

@auditoria_bp.route('/<int:report_id>')
@login_required
@require_role('Master')
def detalle(report_id):
    from app.models.audit_report import AuditReport
    report = db.get_or_404(AuditReport, report_id)
    return jsonify({'success': True, 'report': report.to_dict()})


# ── Último reporte ────────────────────────────────────────────────────────────

@auditoria_bp.route('/api/ultimo')
@login_required
@require_role('Master')
def api_ultimo():
    from app.models.audit_report import AuditReport

    year  = request.args.get('year',  type=int, default=date.today().year)
    month = request.args.get('month', type=int, default=date.today().month)

    report = AuditReport.query.filter_by(
        # Buscar el último reporte del período
    ).order_by(AuditReport.id.desc()).first()

    # Si piden período específico
    from sqlalchemy import extract
    report = AuditReport.query.filter(
        extract('year',  AuditReport.audit_date) == year,
        extract('month', AuditReport.audit_date) == month,
    ).order_by(AuditReport.id.desc()).first()

    if not report:
        return jsonify({'success': True, 'report': None, 'message': 'Sin auditoría para este período'})

    return jsonify({'success': True, 'report': report.to_dict()})


# ── PLE Export: Libro Diario ──────────────────────────────────────────────────

@auditoria_bp.route('/ple/diario')
@login_required
@require_role('Master')
def ple_diario():
    from app.services.audit.ple_export import (
        export_libro_diario_simplificado, get_filename
    )
    from app.models.system_config import SystemConfig

    year  = request.args.get('year',  type=int, default=date.today().year)
    month = request.args.get('month', type=int, default=date.today().month)

    try:
        ruc      = SystemConfig.get('RUC', '20615113698')
        content  = export_libro_diario_simplificado(year, month)
        filename = get_filename('diario', year, month, ruc)

        output = BytesIO(content)
        output.seek(0)

        return send_file(
            output,
            mimetype='text/plain',
            as_attachment=True,
            download_name=filename,
        )
    except Exception as exc:
        _log.exception('[PLE] Error exportando Libro Diario')
        return jsonify({'success': False, 'error': str(exc)}), 500


# ── PLE Export: Registro de Compras ──────────────────────────────────────────

@auditoria_bp.route('/ple/compras')
@login_required
@require_role('Master')
def ple_compras():
    from app.services.audit.ple_export import export_registro_compras, get_filename
    from app.models.system_config import SystemConfig

    year  = request.args.get('year',  type=int, default=date.today().year)
    month = request.args.get('month', type=int, default=date.today().month)

    try:
        ruc      = SystemConfig.get('RUC', '20615113698')
        content  = export_registro_compras(year, month)
        filename = get_filename('compras', year, month, ruc)

        output = BytesIO(content)
        output.seek(0)

        return send_file(
            output,
            mimetype='text/plain',
            as_attachment=True,
            download_name=filename,
        )
    except Exception as exc:
        _log.exception('[PLE] Error exportando Registro Compras')
        return jsonify({'success': False, 'error': str(exc)}), 500


# ── Depreciación mensual manual ───────────────────────────────────────────────

@auditoria_bp.route('/depreciar', methods=['POST'])
@csrf.exempt
@login_required
@require_role('Master')
def depreciar():
    from app.services.audit.depreciation import run_depreciacion_mensual

    data  = request.get_json() or {}
    year  = int(data.get('year',  date.today().year))
    month = int(data.get('month', date.today().month))

    try:
        resultado = run_depreciacion_mensual(year, month, current_user.id)
        return jsonify({
            'success': True,
            'resultado': resultado,
            'message': (
                f'{resultado["generados"]} asiento(s) de depreciación generado(s) '
                f'para {month:02d}/{year}. '
                f'Total: S/ {resultado["total_depreciation"]:,.2f}.'
            ),
        })
    except Exception as exc:
        _log.exception('[Depreciation] Error al depreciar')
        return jsonify({'success': False, 'error': str(exc)}), 500


# ── Regenerar asientos desde operaciones y gastos ────────────────────────────

@auditoria_bp.route('/regenerar-asientos', methods=['POST'])
@csrf.exempt
@login_required
@require_role('Master')
def regenerar_asientos():
    """
    Re-genera asientos contables para todas las operaciones completadas
    y gastos registrados desde el 01/06/2026 que no tienen asiento vinculado.

    Usar DESPUÉS de ejecutar reset_contabilidad_junio.sql.
    """
    from datetime import date as date_type
    from decimal import Decimal
    from app.models.operation import Operation
    from app.models.expense_record import ExpenseRecord
    from app.models.journal_entry import JournalEntry
    from app.services.accounting.journal_service import JournalService

    DESDE = date_type(2026, 6, 1)

    ops_ok = 0
    ops_err = 0
    gastos_ok = 0
    gastos_err = 0
    errores = []

    # ── 1. Operaciones completadas sin asiento ──────────────────────────────
    ops = Operation.query.filter(
        Operation.status == 'Completada',
        Operation.completed_at >= DESDE,
    ).order_by(Operation.completed_at.asc()).all()

    # IDs de operaciones que ya tienen asiento
    existing_op_ids = set(
        row[0] for row in db.session.query(JournalEntry.source_id).filter(
            JournalEntry.source_type == 'operation',
            JournalEntry.status == 'activo',
        ).all() if row[0]
    )

    for op in ops:
        if op.id in existing_op_ids:
            continue
        try:
            entry = JournalService.create_entry_for_completed_operation(
                op, created_by_id=current_user.id
            )
            if entry:
                ops_ok += 1
            else:
                ops_err += 1
                errores.append(f'Op {op.operation_id}: create_entry retornó None')
        except Exception as exc:
            ops_err += 1
            errores.append(f'Op {op.operation_id}: {exc}')

    # ── 2. Gastos sin asiento ───────────────────────────────────────────────
    gastos = ExpenseRecord.query.filter(
        ExpenseRecord.expense_date >= DESDE,
        ExpenseRecord.journal_entry_id.is_(None),
    ).order_by(ExpenseRecord.expense_date.asc()).all()

    for rec in gastos:
        try:
            amount_pen = Decimal(str(rec.amount_pen))
            bank_code  = rec.bank_account_code
            category   = rec.category or '6399'

            if bank_code:
                lines = [
                    {'account_code': category,  'debe': amount_pen, 'haber': Decimal('0'), 'currency': 'PEN'},
                    {'account_code': bank_code,  'debe': Decimal('0'), 'haber': amount_pen, 'currency': 'PEN'},
                ]
            else:
                lines = [
                    {'account_code': category,  'debe': amount_pen, 'haber': Decimal('0'), 'currency': 'PEN'},
                    {'account_code': '4699',     'debe': Decimal('0'), 'haber': amount_pen, 'currency': 'PEN'},
                ]

            entry_type = 'activo_fijo' if rec.expense_type == 'activo_fijo' else 'gasto'
            entry = JournalService.create_entry(
                entry_type=entry_type,
                description=f'Gasto: {rec.description}',
                lines=lines,
                source_type='expense',
                source_id=rec.id,
                entry_date=rec.expense_date,
                created_by=current_user.id,
            )
            if entry:
                rec.journal_entry_id = entry.id
                db.session.commit()
                gastos_ok += 1
            else:
                gastos_err += 1
                errores.append(f'Gasto #{rec.id} ({rec.description[:40]}): create_entry retornó None')
        except Exception as exc:
            db.session.rollback()
            gastos_err += 1
            errores.append(f'Gasto #{rec.id}: {exc}')

    # ── 3. Batches de amarres sin asiento calce_netting ────────────────────
    batches_ok = 0
    batches_err = 0

    from app.models.accounting_batch import AccountingBatch
    from app.services.accounting_service import AccountingService

    existing_batch_ids = set(
        row[0] for row in db.session.query(JournalEntry.source_id).filter(
            JournalEntry.source_type == 'batch',
            JournalEntry.entry_type == 'calce_netting',
            JournalEntry.status == 'activo',
        ).all() if row[0]
    )

    batches = AccountingBatch.query.filter(
        AccountingBatch.netting_date >= DESDE,
        AccountingBatch.status == 'cerrado',
    ).order_by(AccountingBatch.netting_date.asc()).all()

    for batch in batches:
        if batch.id in existing_batch_ids:
            continue
        try:
            AccountingService._create_journal_entry_for_batch(batch, current_user.id)
            batches_ok += 1
        except Exception as exc:
            batches_err += 1
            errores.append(f'Batch {batch.batch_code}: {exc}')

    # ── 4. Matches individuales sin asiento calce_match ─────────────────────
    matches_ok = 0
    matches_err = 0

    from app.models.accounting_match import AccountingMatch

    existing_match_ids = set(
        row[0] for row in db.session.query(JournalEntry.source_id).filter(
            JournalEntry.source_type == 'match',
            JournalEntry.entry_type == 'calce_match',
            JournalEntry.status == 'activo',
        ).all() if row[0]
    )

    matches = AccountingMatch.query.filter(
        AccountingMatch.created_at >= DESDE,
        AccountingMatch.status == 'Activo',
    ).order_by(AccountingMatch.created_at.asc()).all()

    for match in matches:
        if match.id in existing_match_ids:
            continue
        try:
            AccountingService._create_income_entry_for_match(match, current_user.id)
            matches_ok += 1
        except Exception as exc:
            matches_err += 1
            errores.append(f'Match #{match.id}: {exc}')

    total_ok  = ops_ok + gastos_ok + batches_ok + matches_ok
    total_err = ops_err + gastos_err + batches_err + matches_err

    return jsonify({
        'success':     True,
        'ops_ok':      ops_ok,
        'ops_err':     ops_err,
        'gastos_ok':   gastos_ok,
        'gastos_err':  gastos_err,
        'batches_ok':  batches_ok,
        'batches_err': batches_err,
        'matches_ok':  matches_ok,
        'matches_err': matches_err,
        'total_ok':    total_ok,
        'total_err':   total_err,
        'errores':     errores[:30],
        'message':     (
            f'Regeneración completada. '
            f'Ops: {ops_ok} OK. Gastos: {gastos_ok} OK. '
            f'Batches: {batches_ok} OK. Matches: {matches_ok} OK. '
            f'Errores: {total_err}.'
        ),
    })


# ── API: Conciliación en tiempo real ─────────────────────────────────────────

@auditoria_bp.route('/api/conciliacion')
@login_required
@require_role('Master')
def api_conciliacion():
    from app.services.audit.reconciliation import run_conciliacion

    try:
        resultado = run_conciliacion()
        serializable = {
            code: {
                **data,
                'saldo_journal':   float(data['saldo_journal']),
                'saldo_tesoreria': float(data['saldo_tesoreria']) if data['saldo_tesoreria'] is not None else None,
                'diferencia':      float(data['diferencia']) if data['diferencia'] is not None else None,
            }
            for code, data in resultado.items()
        }
        diferencias = sum(1 for d in serializable.values() if not d['ok'])
        return jsonify({
            'success':     True,
            'conciliacion': serializable,
            'diferencias':  diferencias,
            'ok':           diferencias == 0,
        })
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500
