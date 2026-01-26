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
    try:
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
    except Exception as e:
        logger.error(f"❌ Error al listar reclamos: {str(e)}")
        flash('Error al cargar reclamos. Es posible que la tabla aún no exista. Contacte al administrador.', 'danger')
        return redirect(url_for('dashboard.index'))


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

        # Prevenir edición si ya está resuelto
        if complaint.status == 'Resuelto':
            flash('No se puede editar un reclamo que ya está resuelto', 'warning')
            return redirect(url_for('complaints.detail_complaint', id=id))

        # Obtener datos del formulario
        new_status = request.form.get('status', '').strip()
        response_text = request.form.get('response', '').strip()

        # Validar estado
        valid_statuses = ['Pendiente', 'En Revisión', 'Resuelto']
        if new_status not in valid_statuses:
            flash('Estado inválido', 'danger')
            return redirect(url_for('complaints.detail_complaint', id=id))

        # Validar que al marcar como "Resuelto" haya respuesta O imagen
        if new_status == 'Resuelto':
            has_response = response_text and response_text.strip() != ''
            has_image = complaint.resolution_image_url and complaint.resolution_image_url.strip() != ''

            if not has_response and not has_image:
                flash('Para marcar como "Resuelto" debe proporcionar al menos una respuesta del equipo o una imagen de resolución', 'warning')
                return redirect(url_for('complaints.detail_complaint', id=id))

        # Guardar estado anterior para comparar
        old_status = complaint.status

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

        # Enviar correos automáticos cuando cambia el estado
        if old_status != new_status:
            try:
                from app.services.email_service import EmailService
                from flask_mail import Message

                # Datos del cliente
                client_name = complaint.full_name or complaint.company_name
                client_email = complaint.email

                if new_status == 'En Revisión':
                    # Correo cuando pasa a "En Revisión"
                    subject = f'Reclamo {complaint.complaint_number} - En Revisión'

                    html_content = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <meta charset="UTF-8">
                    </head>
                    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                                <h1 style="margin: 0;">Actualización de Reclamo</h1>
                                <p style="margin: 10px 0 0 0; font-size: 18px; font-weight: bold;">{complaint.complaint_number}</p>
                            </div>

                            <div style="background-color: #f8f9fa; padding: 30px; border-radius: 0 0 10px 10px;">
                                <p>Estimado/a <strong>{client_name}</strong>,</p>

                                <p>Le informamos que su reclamo <strong>{complaint.complaint_number}</strong> se encuentra actualmente <strong>en revisión</strong> por nuestro equipo.</p>

                                <p>Estamos trabajando para resolver su solicitud a la brevedad posible.</p>

                                <p style="margin-top: 30px;">Atentamente,</p>
                                <p><strong>Equipo QoriCash</strong></p>
                                <p style="color: #666; font-size: 12px; margin-top: 30px;">
                                    Este es un correo automático, por favor no responder a esta dirección.
                                </p>
                            </div>
                        </div>
                    </body>
                    </html>
                    """

                    # Crear mensaje con cliente como destinatario y copia a info
                    msg = Message(
                        subject=subject,
                        recipients=[client_email],
                        cc=['info@qoricash.pe'],
                        html=html_content
                    )

                    # Enviar asíncrono
                    EmailService._send_async(msg, timeout=15)

                    logger.info(f"✅ Correos de 'En Revisión' enviados para reclamo {complaint.complaint_number}")

                elif new_status == 'Resuelto':
                    # Correo cuando pasa a "Resuelto"
                    subject = f'Reclamo {complaint.complaint_number} - Resuelto'

                    # Construir HTML con o sin imagen
                    image_html = ''
                    if complaint.resolution_image_url:
                        image_html = f"""
                        <div style="text-align: center; margin: 20px 0;">
                            <p><strong>Imagen de Resolución:</strong></p>
                            <img src="{complaint.resolution_image_url}" alt="Resolución" style="max-width: 100%; height: auto; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                        </div>
                        """

                    html_content = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <meta charset="UTF-8">
                    </head>
                    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                            <div style="background: linear-gradient(135deg, #28a745 0%, #20c997 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                                <h1 style="margin: 0;">Reclamo Resuelto</h1>
                                <p style="margin: 10px 0 0 0; font-size: 18px; font-weight: bold;">{complaint.complaint_number}</p>
                            </div>

                            <div style="background-color: #f8f9fa; padding: 30px; border-radius: 0 0 10px 10px;">
                                <p>Estimado/a <strong>{client_name}</strong>,</p>

                                <p>Nos complace informarle que su reclamo <strong>{complaint.complaint_number}</strong> ha sido <strong>resuelto</strong>.</p>

                                {image_html}

                                <p>Si tiene alguna consulta adicional, no dude en contactarnos.</p>

                                <p style="margin-top: 30px;">Atentamente,</p>
                                <p><strong>Equipo QoriCash</strong></p>
                                <p style="color: #666; font-size: 12px; margin-top: 30px;">
                                    Este es un correo automático, por favor no responder a esta dirección.
                                </p>
                            </div>
                        </div>
                    </body>
                    </html>
                    """

                    # Crear mensaje con cliente como destinatario y copia a info
                    msg = Message(
                        subject=subject,
                        recipients=[client_email],
                        cc=['info@qoricash.pe'],
                        html=html_content
                    )

                    # Enviar asíncrono
                    EmailService._send_async(msg, timeout=15)

                    logger.info(f"✅ Correos de 'Resuelto' enviados para reclamo {complaint.complaint_number}")

            except Exception as email_error:
                logger.error(f"❌ Error al enviar correos de actualización de estado: {str(email_error)}")
                # No fallar la actualización si falla el correo
                pass

        flash(f'Reclamo {complaint.complaint_number} actualizado exitosamente', 'success')
        return redirect(url_for('complaints.list_complaints'))

    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Error al actualizar reclamo {id}: {str(e)}")
        flash(f'Error al actualizar reclamo: {str(e)}', 'danger')
        return redirect(url_for('complaints.detail_complaint', id=id))


@complaints_bp.route('/<int:id>/upload-resolution-image', methods=['POST'])
@login_required
@role_required(['Master', 'Middle Office'])
def upload_resolution_image(id):
    """Subir imagen de resolución"""
    try:
        complaint = Complaint.query.get_or_404(id)

        # Verificar si viene archivo o URL JSON
        if request.files and 'file' in request.files:
            # Upload de archivo desde FormData
            file = request.files['file']

            if not file or file.filename == '':
                return jsonify({
                    'success': False,
                    'message': 'No se proporcionó archivo'
                }), 400

            # Usar FileService para subir a Cloudinary
            from app.services.file_service import FileService
            file_service = FileService()

            success, message, image_url = file_service.upload_file(file, folder='complaints/resolutions')

            if not success:
                return jsonify({
                    'success': False,
                    'message': message
                }), 400

        elif request.get_json():
            # URL directa desde JSON (legacy)
            data = request.get_json()
            image_url = data.get('image_url', '').strip()

            if not image_url:
                return jsonify({
                    'success': False,
                    'message': 'URL de imagen no proporcionada'
                }), 400
        else:
            return jsonify({
                'success': False,
                'message': 'No se proporcionó archivo ni URL'
            }), 400

        complaint.resolution_image_url = image_url
        complaint.updated_at = now_peru()

        db.session.commit()

        logger.info(f"✅ Imagen de resolución subida para reclamo {complaint.complaint_number}: {image_url}")

        return jsonify({
            'success': True,
            'message': 'Imagen subida exitosamente',
            'image_url': image_url
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Error al subir imagen: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@complaints_bp.route('/<int:id>/remove-resolution-image', methods=['POST'])
@login_required
@role_required(['Master', 'Middle Office'])
def remove_resolution_image(id):
    """Eliminar imagen de resolución"""
    try:
        complaint = Complaint.query.get_or_404(id)

        complaint.resolution_image_url = None
        complaint.updated_at = now_peru()

        db.session.commit()

        logger.info(f"✅ Imagen de resolución eliminada del reclamo {complaint.complaint_number}")

        flash('Imagen eliminada exitosamente', 'success')
        return redirect(url_for('complaints.detail_complaint', id=id))

    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Error al eliminar imagen: {str(e)}")
        flash(f'Error al eliminar imagen: {str(e)}', 'danger')
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
