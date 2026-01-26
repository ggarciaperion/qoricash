"""
Rutas de Reclamos para QoriCash Trading V2
"""
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models.complaint import Complaint
from app.extensions import db
from app.utils.decorators import role_required
from app.utils.formatters import now_peru
from sqlalchemy import extract, func
import logging

logger = logging.getLogger(__name__)

complaints_bp = Blueprint('complaints', __name__, url_prefix='/complaints')


@complaints_bp.route('/')
@login_required
@role_required(['Master', 'Middle Office'])
def list_complaints():
    """
    Página de listado de reclamos

    Roles permitidos: Master, Middle Office

    Muestra:
    - Estadísticas del mes actual
    - Lista de todos los reclamos
    """
    # Obtener mes y año actual (timezone Peru)
    current_date = now_peru()
    current_month = current_date.month
    current_year = current_date.year

    # Estadísticas del mes actual
    total_month = Complaint.query.filter(
        extract('month', Complaint.created_at) == current_month,
        extract('year', Complaint.created_at) == current_year
    ).count()

    pending_count = Complaint.query.filter_by(status='Pendiente').count()
    in_review_count = Complaint.query.filter_by(status='En Revisión').count()

    resolved_month = Complaint.query.filter(
        Complaint.status == 'Resuelto',
        extract('month', Complaint.resolved_at) == current_month,
        extract('year', Complaint.resolved_at) == current_year
    ).count()

    # Obtener todos los reclamos ordenados por fecha (más reciente primero)
    # Filtrar por estado si se proporciona
    status_filter = request.args.get('status', 'all')

    if status_filter == 'all':
        complaints = Complaint.query.order_by(Complaint.created_at.desc()).all()
    else:
        complaints = Complaint.query.filter_by(status=status_filter).order_by(Complaint.created_at.desc()).all()

    return render_template(
        'complaints/list.html',
        user=current_user,
        complaints=complaints,
        total_month=total_month,
        pending_count=pending_count,
        in_review_count=in_review_count,
        resolved_month=resolved_month,
        status_filter=status_filter
    )


@complaints_bp.route('/<int:id>')
@login_required
@role_required(['Master', 'Middle Office'])
def detail_complaint(id):
    """
    Ver detalle de un reclamo específico

    Roles permitidos: Master, Middle Office
    """
    complaint = Complaint.query.get_or_404(id)

    return render_template(
        'complaints/detail.html',
        user=current_user,
        complaint=complaint
    )


@complaints_bp.route('/<int:id>/update-status', methods=['POST'])
@login_required
@role_required(['Master', 'Middle Office'])
def update_complaint_status(id):
    """
    Actualizar estado y respuesta de un reclamo

    Roles permitidos: Master, Middle Office

    POST data:
        status: Nuevo estado (Pendiente, En Revisión, Resuelto)
        response: Respuesta del equipo
    """
    try:
        complaint = Complaint.query.get_or_404(id)

        # Obtener datos del formulario
        new_status = request.form.get('status', '').strip()
        response_text = request.form.get('response', '').strip()

        # Validar estado
        valid_statuses = ['Pendiente', 'En Revisión', 'Resuelto']
        if new_status not in valid_statuses:
            flash('Estado inválido', 'danger')
            return redirect(url_for('complaints.detail_complaint', id=id))

        # Actualizar datos
        complaint.status = new_status
        complaint.response = response_text if response_text else None
        complaint.updated_at = now_peru()

        # Si se marca como resuelto, guardar fecha y usuario
        if new_status == 'Resuelto':
            if not complaint.resolved_at:  # Solo si no estaba resuelto antes
                complaint.resolved_at = now_peru()
                complaint.resolved_by = current_user.id
        else:
            # Si se cambia de Resuelto a otro estado, limpiar campos de resolución
            complaint.resolved_at = None
            complaint.resolved_by = None

        db.session.commit()

        logger.info(f"✅ Reclamo {complaint.complaint_number} actualizado a estado '{new_status}' por {current_user.username}")

        flash(f'Reclamo {complaint.complaint_number} actualizado exitosamente', 'success')
        return redirect(url_for('complaints.list_complaints'))

    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Error al actualizar reclamo {id}: {str(e)}")
        flash(f'Error al actualizar reclamo: {str(e)}', 'danger')
        return redirect(url_for('complaints.detail_complaint', id=id))


@complaints_bp.route('/api/stats')
@login_required
@role_required(['Master', 'Middle Office'])
def api_stats():
    """
    API: Obtener estadísticas de reclamos (JSON)

    Returns:
        JSON con estadísticas del mes y totales
    """
    try:
        # Obtener mes y año actual (timezone Peru)
        current_date = now_peru()
        current_month = current_date.month
        current_year = current_date.year

        # Estadísticas
        total_month = Complaint.query.filter(
            extract('month', Complaint.created_at) == current_month,
            extract('year', Complaint.created_at) == current_year
        ).count()

        pending_count = Complaint.query.filter_by(status='Pendiente').count()
        in_review_count = Complaint.query.filter_by(status='En Revisión').count()

        resolved_month = Complaint.query.filter(
            Complaint.status == 'Resuelto',
            extract('month', Complaint.resolved_at) == current_month,
            extract('year', Complaint.resolved_at) == current_year
        ).count()

        total_complaints = Complaint.query.count()

        return jsonify({
            'success': True,
            'data': {
                'total_month': total_month,
                'pending_count': pending_count,
                'in_review_count': in_review_count,
                'resolved_month': resolved_month,
                'total_complaints': total_complaints
            }
        })

    except Exception as e:
        logger.error(f"❌ Error al obtener estadísticas de reclamos: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error al obtener estadísticas: {str(e)}'
        }), 500
