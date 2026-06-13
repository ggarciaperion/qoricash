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

        return jsonify({
            'success': True,
            'report':  report.to_dict(),
            'message': (
                f'Auditoría {month:02d}/{year} completada. '
                f'Estado: {report.estado}. '
                f'{report.total_hallazgos} hallazgo(s).'
            ),
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
