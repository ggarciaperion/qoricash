"""
Rutas de Compliance para Middle Office - QoriCash Trading V2
"""
import json
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
from app.extensions import db, csrf
from app.models.compliance import (
    ClientRiskProfile, ComplianceRule, ComplianceAlert,
    RestrictiveListCheck, TransactionMonitoring, RiskLevel, ComplianceAudit
)
from app.models.client import Client
from app.models.operation import Operation
from app.services.compliance_service import ComplianceService
from app.utils.formatters import now_peru

compliance_bp = Blueprint('compliance', __name__)


def middle_office_required(f):
    """Decorator para requerir rol Middle Office o Master"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({
                'success': False,
                'error': 'No autenticado'
            }), 401

        # Permitir Master y Middle Office
        if current_user.role not in ['Master', 'Middle Office']:
            return jsonify({
                'success': False,
                'error': 'Acceso denegado. Solo Master y Middle Office pueden acceder.'
            }), 403
        return f(*args, **kwargs)
    return decorated_function


# ==================== ALERTAS ====================

@compliance_bp.route('/alerts')
@login_required
@middle_office_required
def alerts():
    """Página de alertas de compliance"""
    return render_template('compliance/alerts.html')


@compliance_bp.route('/api/alerts')
@login_required
@middle_office_required
def api_alerts():
    """API: Lista de alertas con filtros para DataTables"""
    try:
        # Parámetros de DataTables
        draw = request.args.get('draw', type=int, default=1)
        start = request.args.get('start', type=int, default=0)
        length = request.args.get('length', type=int, default=10)

        # Filtros
        severity = request.args.get('severity')
        status = request.args.get('status')
        alert_type = request.args.get('alert_type')

        # Query base
        query = ComplianceAlert.query

        # Aplicar filtros
        if severity:
            query = query.filter_by(severity=severity)
        if status:
            query = query.filter_by(status=status)
        if alert_type:
            query = query.filter_by(alert_type=alert_type)

        # Total de registros
        total_records = query.count()

        # Paginación
        alerts = query.order_by(ComplianceAlert.created_at.desc()) \
                     .limit(length) \
                     .offset(start) \
                     .all()

        # Formatear datos
        data = []
        for alert in alerts:
            data.append({
                'id': alert.id,
                'alert_type': alert.alert_type,
                'severity': alert.severity,
                'title': alert.title,
                'description': alert.description,
                'client_id': alert.client_id,
                'client_name': alert.client.full_name if alert.client else 'N/A',
                'operation_id': alert.operation_id,
                'status': alert.status,
                'created_at': alert.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'reviewed_by': alert.reviewer.username if alert.reviewer else None,
                'reviewed_at': alert.reviewed_at.strftime('%Y-%m-%d %H:%M:%S') if alert.reviewed_at else None
            })

        return jsonify({
            'draw': draw,
            'recordsTotal': total_records,
            'recordsFiltered': total_records,
            'data': data
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@compliance_bp.route('/alerts/<int:alert_id>')
@login_required
@middle_office_required
def alert_detail(alert_id):
    """Detalle de una alerta"""
    alert = ComplianceAlert.query.get_or_404(alert_id)
    return render_template('compliance/alert_detail.html', alert=alert)


@compliance_bp.route('/api/alerts/<int:alert_id>/resolve', methods=['POST'])
@login_required
@middle_office_required
@csrf.exempt
def resolve_alert(alert_id):
    """API: Resolver una alerta"""
    try:
        data = request.get_json()
        resolution = data.get('resolution')
        notes = data.get('notes', '')

        if not resolution:
            return jsonify({
                'success': False,
                'error': 'Debe especificar una resolución'
            }), 400

        success, message = ComplianceService.resolve_alert(
            alert_id,
            current_user.id,
            resolution,
            notes
        )

        if success:
            # Registrar en auditoría
            audit = ComplianceAudit(
                user_id=current_user.id,
                action_type='Alert_Resolution',
                entity_type='Alert',
                entity_id=alert_id,
                description=f'Alerta resuelta: {resolution}',
                changes=json.dumps({
                    'resolution': resolution,
                    'notes': notes
                }),
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent')
            )
            db.session.add(audit)
            db.session.commit()

        return jsonify({
            'success': success,
            'message': message
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== PERFILES DE RIESGO ====================

@compliance_bp.route('/risk-profiles')
@login_required
@middle_office_required
def risk_profiles():
    """Página de perfiles de riesgo"""
    return render_template('compliance/risk_profiles.html')


@compliance_bp.route('/api/risk-profiles')
@login_required
@middle_office_required
def api_risk_profiles():
    """API: Lista TODOS los clientes con sus perfiles de riesgo"""
    try:
        import logging
        logger = logging.getLogger(__name__)

        logger.info("=== INICIO api_risk_profiles (versión simplificada) ===")

        # 1. Obtener TODOS los clientes
        all_clients = Client.query.all()
        logger.info(f"Total clientes en BD: {len(all_clients)}")

        # 2. Generar perfiles faltantes automáticamente
        generated_count = 0
        for client in all_clients:
            existing_profile = ClientRiskProfile.query.filter_by(client_id=client.id).first()
            if not existing_profile:
                try:
                    logger.info(f"Generando perfil para cliente {client.id} - {client.full_name}")
                    success, score, level = ComplianceService.update_client_risk_profile(client.id, current_user.id)
                    if success:
                        generated_count += 1
                        logger.info(f"  -> Perfil creado: Score={score}, Level={level}")
                except Exception as e:
                    logger.error(f"  -> Error al generar perfil: {str(e)}")

        if generated_count > 0:
            db.session.commit()
            logger.info(f"COMMIT: Generados {generated_count} perfiles nuevos")

        # 3. Obtener TODOS los perfiles con sus clientes (INNER JOIN)
        profiles = db.session.query(ClientRiskProfile, Client).join(
            Client, ClientRiskProfile.client_id == Client.id
        ).all()

        logger.info(f"Total perfiles recuperados: {len(profiles)}")

        # 4. Construir respuesta simple
        data = []
        for profile, client in profiles:
            data.append({
                'id': profile.id,
                'client_id': client.id,
                'client_name': client.full_name,
                'client_dni': client.dni,
                'risk_score': profile.risk_score,
                'risk_level': ComplianceService.assign_risk_level(profile.risk_score),
                'is_pep': profile.is_pep,
                'kyc_status': profile.kyc_status,
                'dd_level': profile.dd_level if profile.dd_level else '-',
                'in_restrictive_lists': profile.in_restrictive_lists,
                'has_legal_issues': profile.has_legal_issues,
                'updated_at': profile.updated_at.strftime('%Y-%m-%d %H:%M') if profile.updated_at else '-'
            })

        logger.info(f"Retornando {len(data)} perfiles al frontend")
        logger.info("=== FIN api_risk_profiles ===")

        return jsonify({
            'success': True,
            'data': data
        })

    except Exception as e:
        import traceback
        logger = logging.getLogger(__name__)
        logger.error(f"ERROR en api_risk_profiles: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@compliance_bp.route('/risk-profiles/<int:client_id>')
@login_required
@middle_office_required
def risk_profile_detail(client_id):
    """Detalle de perfil de riesgo de un cliente"""
    from app.models.operation import Operation

    client = Client.query.get_or_404(client_id)
    profile = ClientRiskProfile.query.filter_by(client_id=client_id).first()

    # Cargar operaciones manualmente (client.operations es dynamic y no soporta joinedload)
    # Convertir la query a lista para pasarla al template
    operations = client.operations.order_by(Operation.created_at.desc()).all()

    return render_template('compliance/risk_profile_detail.html',
                         client=client,
                         profile=profile,
                         operations=operations)


@compliance_bp.route('/api/risk-profiles/<int:client_id>/recalculate', methods=['POST'])
@login_required
@middle_office_required
@csrf.exempt
def recalculate_risk_profile(client_id):
    """API: Recalcular perfil de riesgo de un cliente"""
    try:
        # Recalcular riesgo - auto_commit=False para hacer un solo commit con la auditoría
        success, score, level = ComplianceService.update_client_risk_profile(
            client_id,
            current_user.id,
            auto_commit=False
        )

        if success:
            # Registrar en auditoría
            audit = ComplianceAudit(
                user_id=current_user.id,
                action_type='Risk_Recalculation',
                entity_type='Client',
                entity_id=client_id,
                description=f'Perfil de riesgo recalculado: {level} ({score} puntos)',
                changes=json.dumps({
                    'score': score,
                    'level': level
                }),
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent')
            )
            db.session.add(audit)
            db.session.commit()

            return jsonify({
                'success': True,
                'message': 'Perfil recalculado correctamente',
                'data': {
                    'score': score,
                    'level': level
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Error al recalcular perfil'
            }), 500

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== KYC ====================

@compliance_bp.route('/kyc')
@login_required
@middle_office_required
def kyc():
    """Página de revisión KYC"""
    return render_template('compliance/kyc.html')


@compliance_bp.route('/api/kyc/pending')
@login_required
@middle_office_required
def api_kyc_pending():
    """API: Lista de clientes para revisión KYC"""
    try:
        import logging
        logger = logging.getLogger(__name__)

        logger.info("KYC API: Iniciando consulta de clientes...")

        # Obtener TODOS los clientes
        all_clients = Client.query.order_by(Client.created_at.desc()).all()

        logger.info(f"KYC API: Total de clientes en BD: {len(all_clients)}")

        data = []
        for client in all_clients:
            # Obtener nombre completo
            if client.document_type == 'RUC':
                client_name = client.razon_social or '-'
            else:
                parts = []
                if client.apellido_paterno:
                    parts.append(client.apellido_paterno)
                if client.apellido_materno:
                    parts.append(client.apellido_materno)
                if client.nombres:
                    parts.append(client.nombres)
                client_name = ' '.join(parts) if parts else '-'

            # Buscar perfil de riesgo
            profile = ClientRiskProfile.query.filter_by(client_id=client.id).first()

            # Determinar KYC status
            if profile and profile.kyc_status:
                kyc_status = profile.kyc_status
                # Solo mostrar si está Pendiente o En Proceso
                if kyc_status not in ['Pendiente', 'En Proceso']:
                    continue
            else:
                # Sin perfil = Pendiente
                kyc_status = 'Pendiente'

            data.append({
                'client_id': client.id,
                'client_name': client_name,
                'client_dni': client.dni,
                'client_email': client.email,
                'client_status': client.status,
                'document_type': client.document_type,
                'kyc_status': kyc_status,
                'created_at': client.created_at.strftime('%d/%m/%Y %H:%M') if client.created_at else '-'
            })

        logger.info(f"KYC API: Clientes para revisión: {len(data)}")

        return jsonify({
            'success': True,
            'data': data
        })

    except Exception as e:
        import logging
        import traceback
        logger = logging.getLogger(__name__)
        logger.error(f"KYC API ERROR: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@compliance_bp.route('/api/kyc/<int:client_id>/approve', methods=['POST'])
@login_required
@middle_office_required
@csrf.exempt
def approve_kyc(client_id):
    """API: Aprobar KYC de un cliente y ACTIVARLO para operar"""
    try:
        data = request.get_json()
        notes = data.get('notes', '')

        # Obtener cliente
        client = Client.query.get_or_404(client_id)

        # Guardar estado anterior para saber si estaba inactivo
        was_inactive = (client.status == 'Inactivo')

        # VALIDACIÓN CRÍTICA: Verificar documentos antes de aprobar
        is_valid, missing_docs = ComplianceService.validate_client_documents(client)
        if not is_valid:
            return jsonify({
                'success': False,
                'error': 'No se puede aprobar KYC. Faltan documentos requeridos',
                'missing_documents': missing_docs
            }), 400

        # Obtener o crear perfil de riesgo
        profile = ClientRiskProfile.query.filter_by(client_id=client_id).first()
        if not profile:
            profile = ClientRiskProfile(client_id=client_id)
            db.session.add(profile)

        profile.kyc_status = 'Aprobado'
        profile.kyc_verified_at = now_peru()
        profile.kyc_verified_by = current_user.id
        profile.kyc_notes = notes

        # IMPORTANTE: ACTIVAR CLIENTE - Solo Middle Office puede hacerlo
        client.status = 'Activo'
        client.updated_at = now_peru()

        # MARCAR DOCUMENTOS COMO COMPLETOS para que desaparezca el banner en la app móvil
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f'📋 [KYC APPROVE] Aprobando documentos para cliente {client.dni} - {client.full_name}')
        client.complete_documents_and_reset()
        logger.info(f'✅ [KYC APPROVE] has_complete_documents establecido a: {client.has_complete_documents}')

        # Recalcular riesgo (KYC aprobado reduce 10 puntos) - auto_commit=False para hacer un solo commit
        ComplianceService.update_client_risk_profile(client_id, current_user.id, auto_commit=False)

        # Auditoría
        audit = ComplianceAudit(
            user_id=current_user.id,
            action_type='KYC_Approval',
            entity_type='Client',
            entity_id=client_id,
            description=f'KYC aprobado - Cliente ACTIVADO para operar',
            changes=json.dumps({
                'kyc_status': 'Aprobado',
                'client_status': 'Activo',
                'has_complete_documents': True,
                'notes': notes
            }),
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        db.session.add(audit)
        db.session.commit()
        logger.info(f'💾 [KYC APPROVE] Cambios guardados en BD para cliente {client.dni}')

        # Enviar correo de activación con contraseña temporal si el cliente estaba inactivo
        try:
            from app.services.email_service import EmailService
            from app.utils.password_generator import generate_simple_password

            # Generar contraseña temporal SOLO si el cliente estaba inactivo
            temporary_password = None
            if was_inactive:
                # Generar contraseña temporal
                temporary_password = generate_simple_password(length=10)

                # Establecer contraseña en el cliente
                client.set_password(temporary_password)
                client.requires_password_change = True
                db.session.commit()

                logger.info(f'✅ [KYC APPROVE] Contraseña temporal generada para cliente {client.dni} al aprobar KYC')

            # Enviar correo con el trader que creó al cliente
            trader = client.creator if hasattr(client, 'creator') and client.creator else current_user
            EmailService.send_client_activation_email(client, trader, temporary_password)
        except Exception as e:
            # No bloquear por errores de email
            logger.warning(f'Error al enviar email de cliente activado desde KYC: {str(e)}')

        # ENVIAR NOTIFICACIÓN SOCKET.IO AL CLIENTE MÓVIL
        logger.info(f'📡 [KYC APPROVE] Enviando notificación Socket.IO a cliente {client.dni}...')
        try:
            from app.services.notification_service import NotificationService
            NotificationService.notify_client_documents_approved(client)
            logger.info(f'✅ [KYC APPROVE] Notificación Socket.IO enviada correctamente al room client_{client.dni}')
        except Exception as e:
            logger.error(f'❌ [KYC APPROVE] Error al enviar notificación Socket.IO al cliente: {str(e)}')
            logger.exception(e)

        return jsonify({
            'success': True,
            'message': 'KYC aprobado - Cliente ACTIVADO para operar'
        })

    except Exception as e:
        db.session.rollback()
        import logging
        logging.error(f"Error aprobando KYC: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@compliance_bp.route('/api/kyc/<int:client_id>/reject', methods=['POST'])
@login_required
@middle_office_required
@csrf.exempt
def reject_kyc(client_id):
    """API: Rechazar KYC de un cliente y mantenerlo INACTIVO"""
    try:
        data = request.get_json()
        notes = data.get('notes', '')

        if not notes:
            return jsonify({
                'success': False,
                'error': 'Debe especificar el motivo del rechazo'
            }), 400

        # Obtener cliente
        client = Client.query.get_or_404(client_id)

        # Obtener o crear perfil de riesgo
        profile = ClientRiskProfile.query.filter_by(client_id=client_id).first()
        if not profile:
            profile = ClientRiskProfile(client_id=client_id)
            db.session.add(profile)

        profile.kyc_status = 'Rechazado'
        profile.kyc_verified_at = now_peru()
        profile.kyc_verified_by = current_user.id
        profile.kyc_notes = notes

        # IMPORTANTE: MANTENER INACTIVO - Cliente no puede operar
        client.status = 'Inactivo'
        client.updated_at = now_peru()

        # Auditoría
        audit = ComplianceAudit(
            user_id=current_user.id,
            action_type='KYC_Rejection',
            entity_type='Client',
            entity_id=client_id,
            description=f'KYC rechazado - Cliente permanece INACTIVO',
            changes=json.dumps({
                'kyc_status': 'Rechazado',
                'client_status': 'Inactivo',
                'notes': notes
            }),
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        db.session.add(audit)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'KYC rechazado - Cliente permanece INACTIVO'
        })

    except Exception as e:
        db.session.rollback()
        import logging
        logging.error(f"Error rechazando KYC: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@compliance_bp.route('/api/kyc/<int:client_id>/reset', methods=['POST'])
@login_required
@middle_office_required
@csrf.exempt
def reset_kyc(client_id):
    """API: Reiniciar KYC rechazado para nueva revisión"""
    try:
        # Obtener cliente
        client = Client.query.get_or_404(client_id)

        # Obtener perfil de riesgo
        profile = ClientRiskProfile.query.filter_by(client_id=client_id).first()
        if not profile:
            return jsonify({
                'success': False,
                'error': 'El cliente no tiene perfil de riesgo'
            }), 404

        # Solo se puede reiniciar si está Rechazado
        if profile.kyc_status != 'Rechazado':
            return jsonify({
                'success': False,
                'error': f'El KYC está en estado "{profile.kyc_status}". Solo se puede reiniciar si está Rechazado.'
            }), 400

        # Cambiar estado a "En Proceso" para nueva revisión
        profile.kyc_status = 'En Proceso'
        profile.kyc_notes = (profile.kyc_notes or '') + f'\n\n[{now_peru().strftime("%d/%m/%Y %H:%M")}] KYC reiniciado por {current_user.username} para nueva revisión.'

        # Auditoría
        audit = ComplianceAudit(
            user_id=current_user.id,
            action_type='KYC_Reset',
            entity_type='Client',
            entity_id=client_id,
            description='KYC reiniciado para nueva revisión después de rechazo',
            changes=json.dumps({
                'old_status': 'Rechazado',
                'new_status': 'En Proceso'
            }),
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        db.session.add(audit)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'KYC reiniciado. El cliente volverá a aparecer en el menú de revisión KYC.'
        })

    except Exception as e:
        db.session.rollback()
        import logging
        logging.error(f"Error reiniciando KYC: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@compliance_bp.route('/api/clients/<int:client_id>/change-status', methods=['POST'])
@login_required
@middle_office_required
@csrf.exempt
def change_client_status(client_id):
    """API: Cambiar estado de un cliente (Activo/Inactivo) - Solo Middle Office"""
    try:
        data = request.get_json()
        new_status = data.get('status')
        reason = data.get('reason', '')

        if not new_status or new_status not in ['Activo', 'Inactivo']:
            return jsonify({
                'success': False,
                'error': 'Estado inválido. Debe ser "Activo" o "Inactivo"'
            }), 400

        # Obtener cliente
        client = Client.query.get_or_404(client_id)
        old_status = client.status

        # Cambiar estado
        client.status = new_status
        client.updated_at = now_peru()

        # Obtener perfil de riesgo
        profile = ClientRiskProfile.query.filter_by(client_id=client_id).first()

        # Si se activa, verificar que tenga KYC aprobado
        if new_status == 'Activo':
            if not profile or profile.kyc_status != 'Aprobado':
                db.session.rollback()
                return jsonify({
                    'success': False,
                    'error': 'No se puede activar un cliente sin KYC aprobado. Debe aprobar el KYC primero.'
                }), 400

        # Auditoría
        audit = ComplianceAudit(
            user_id=current_user.id,
            action_type='Client_Status_Change',
            entity_type='Client',
            entity_id=client_id,
            description=f'Estado cambiado de {old_status} a {new_status}',
            changes=json.dumps({
                'old_status': old_status,
                'new_status': new_status,
                'reason': reason
            }),
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        db.session.add(audit)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Cliente {new_status.lower()} correctamente'
        })

    except Exception as e:
        db.session.rollback()
        import logging
        logging.error(f"Error cambiando estado de cliente: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== REGLAS ====================

@compliance_bp.route('/rules')
@login_required
@middle_office_required
def rules():
    """Página de gestión de reglas"""
    return render_template('compliance/rules.html')


@compliance_bp.route('/api/rules')
@login_required
@middle_office_required
def api_rules():
    """API: Lista de reglas de compliance"""
    try:
        all_rules = ComplianceRule.query.order_by(ComplianceRule.created_at.desc()).all()

        data = []
        for rule in all_rules:
            data.append({
                'id': rule.id,
                'name': rule.name,
                'description': rule.description,
                'rule_type': rule.rule_type,
                'severity': rule.severity,
                'is_active': rule.is_active,
                'auto_block': rule.auto_block,
                'created_at': rule.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'created_by': rule.creator.username if rule.creator else 'Sistema'
            })

        return jsonify({
            'success': True,
            'data': data
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== LISTAS RESTRICTIVAS ====================

@compliance_bp.route('/restrictive-lists')
@login_required
@middle_office_required
def restrictive_lists():
    """Página de listas restrictivas"""
    return render_template('compliance/restrictive_lists.html')


@compliance_bp.route('/api/pep/<int:client_id>', methods=['POST'])
@login_required
@middle_office_required
@csrf.exempt
def update_pep_status(client_id):
    """API: Actualizar estado PEP de un cliente - SOLO Master y Middle Office"""
    try:
        data = request.get_json()

        # Obtener cliente
        client = Client.query.get_or_404(client_id)

        # Obtener o crear perfil de riesgo
        profile = ClientRiskProfile.query.filter_by(client_id=client_id).first()
        if not profile:
            profile = ClientRiskProfile(client_id=client_id)
            db.session.add(profile)

        # Actualizar status PEP
        is_pep = data.get('is_pep', False)
        profile.is_pep = is_pep

        if is_pep:
            # Si es PEP, validar campos requeridos
            pep_type = data.get('pep_type', '').strip()
            pep_position = data.get('pep_position', '').strip()
            pep_entity = data.get('pep_entity', '').strip()

            if not pep_type:
                return jsonify({
                    'success': False,
                    'error': 'Debe especificar el tipo de PEP (Directo/Familiar/Asociado Cercano)'
                }), 400

            if not pep_position:
                return jsonify({
                    'success': False,
                    'error': 'Debe especificar el cargo/posición del PEP'
                }), 400

            if not pep_entity:
                return jsonify({
                    'success': False,
                    'error': 'Debe especificar la entidad/institución del PEP'
                }), 400

            # Actualizar campos PEP
            profile.pep_type = pep_type
            profile.pep_position = pep_position
            profile.pep_entity = pep_entity
            profile.pep_notes = data.get('pep_notes', '').strip()

            # Fechas
            from datetime import datetime
            if data.get('pep_designation_date'):
                try:
                    profile.pep_designation_date = datetime.strptime(data.get('pep_designation_date'), '%Y-%m-%d').date()
                except:
                    pass

            if data.get('pep_end_date'):
                try:
                    profile.pep_end_date = datetime.strptime(data.get('pep_end_date'), '%Y-%m-%d').date()
                except:
                    pass
        else:
            # Si NO es PEP, limpiar campos
            profile.pep_type = None
            profile.pep_position = None
            profile.pep_entity = None
            profile.pep_designation_date = None
            profile.pep_end_date = None
            profile.pep_notes = None

        # Recalcular riesgo automáticamente - auto_commit=False para hacer un solo commit
        ComplianceService.update_client_risk_profile(client_id, current_user.id, auto_commit=False)

        # Auditoría
        audit = ComplianceAudit(
            user_id=current_user.id,
            action_type='PEP_Update',
            entity_type='Client',
            entity_id=client_id,
            description=f'Estado PEP actualizado a: {"Sí" if is_pep else "No"}',
            changes=json.dumps({
                'is_pep': is_pep,
                'pep_type': profile.pep_type,
                'pep_position': profile.pep_position,
                'pep_entity': profile.pep_entity
            }),
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        db.session.add(audit)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Estado PEP actualizado correctamente. Perfil de riesgo recalculado.',
            'is_pep': is_pep,
            'new_risk_score': profile.risk_score
        })

    except Exception as e:
        db.session.rollback()
        import logging
        import traceback
        logging.error(f"Error actualizando PEP: {str(e)}")
        logging.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@compliance_bp.route('/api/restrictive-lists/clients')
@login_required
@middle_office_required
def api_restrictive_lists_clients():
    """API: Lista de clientes para verificación de listas restrictivas"""
    try:
        import logging
        logger = logging.getLogger(__name__)

        # Obtener todos los clientes
        all_clients = Client.query.order_by(Client.created_at.desc()).all()
        logger.info(f"Listas Restrictivas: Total de clientes en BD: {len(all_clients)}")

        data = []
        for client in all_clients:
            try:
                # Obtener nombre completo
                if client.document_type == 'RUC':
                    client_name = client.razon_social or '-'
                else:
                    parts = []
                    if hasattr(client, 'apellido_paterno') and client.apellido_paterno:
                        parts.append(client.apellido_paterno)
                    if hasattr(client, 'apellido_materno') and client.apellido_materno:
                        parts.append(client.apellido_materno)
                    if hasattr(client, 'nombres') and client.nombres:
                        parts.append(client.nombres)
                    client_name = ' '.join(parts) if parts else '-'

                # Buscar última verificación
                last_check = None
                last_check_date = None
                last_check_result = None

                try:
                    last_check = RestrictiveListCheck.query.filter_by(
                        client_id=client.id
                    ).order_by(RestrictiveListCheck.checked_at.desc()).first()

                    if last_check:
                        last_check_date = last_check.checked_at.strftime('%d/%m/%Y %H:%M')
                        last_check_result = last_check.result
                except Exception as check_error:
                    # Hacer rollback para limpiar la transacción abortada
                    db.session.rollback()
                    logger.warning(f"Error obteniendo última verificación para cliente {client.id}: {str(check_error)}")

                data.append({
                    'client_id': client.id,
                    'client_name': client_name,
                    'client_dni': client.dni,
                    'client_email': client.email if hasattr(client, 'email') else '-',
                    'document_type': client.document_type if hasattr(client, 'document_type') else 'DNI',
                    'last_check': last_check_date,
                    'last_result': last_check_result
                })
            except Exception as client_error:
                logger.error(f"Error procesando cliente {client.id}: {str(client_error)}")
                continue

        logger.info(f"Listas Restrictivas: Retornando {len(data)} clientes")

        return jsonify({
            'success': True,
            'data': data
        })

    except Exception as e:
        import logging
        import traceback
        logger = logging.getLogger(__name__)
        logger.error(f"Listas Restrictivas API ERROR: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@compliance_bp.route('/api/restrictive-lists/check', methods=['POST'])
@login_required
@middle_office_required
@csrf.exempt
def check_restrictive_lists():
    """API: Guardar verificación manual de listas restrictivas"""
    import logging
    import traceback
    from werkzeug.utils import secure_filename
    import cloudinary
    import cloudinary.uploader

    logger = logging.getLogger(__name__)

    try:
        client_id = request.form.get('client_id')
        if not client_id:
            return jsonify({
                'success': False,
                'error': 'client_id es requerido'
            }), 400

        client = Client.query.get_or_404(int(client_id))

        # Determinar resultado general
        has_match = False
        list_types = ['ofac', 'onu', 'uif', 'interpol', 'denuncias', 'otras_listas']

        for list_type in list_types:
            if request.form.get(f'{list_type}_checked'):
                result = request.form.get(f'{list_type}_result', 'Clean')
                if result == 'Match':
                    has_match = True
                    break

        overall_result = 'Match' if has_match else 'Clean'

        # Subir archivos a Cloudinary si existen
        attachment_urls = []
        if 'attachments' in request.files:
            files = request.files.getlist('attachments')
            for file in files:
                if file and file.filename:
                    try:
                        # Subir a Cloudinary
                        upload_result = cloudinary.uploader.upload(
                            file,
                            folder=f'qoricash/restrictive_lists/client_{client_id}',
                            resource_type='auto'
                        )
                        attachment_urls.append(upload_result['secure_url'])
                        logger.info(f"Archivo subido a Cloudinary: {upload_result['secure_url']}")
                    except Exception as e:
                        logger.error(f"Error subiendo archivo a Cloudinary: {str(e)}")

        # Crear registro de verificación
        check = RestrictiveListCheck(
            client_id=int(client_id),
            list_type='Manual_Comprehensive',
            provider='Manual',
            result=overall_result,
            is_manual=True,
            observations=request.form.get('observations', ''),
            attachments=','.join(attachment_urls) if attachment_urls else None,
            checked_by=current_user.id
        )

        # Guardar datos de cada lista verificada
        for list_type in list_types:
            if request.form.get(f'{list_type}_checked'):
                setattr(check, f'{list_type}_checked', True)
                setattr(check, f'{list_type}_result', request.form.get(f'{list_type}_result', 'Clean'))
                setattr(check, f'{list_type}_details', request.form.get(f'{list_type}_details', ''))

        db.session.add(check)

        # Actualizar perfil de riesgo del cliente
        profile = ClientRiskProfile.query.filter_by(client_id=int(client_id)).first()
        if not profile:
            profile = ClientRiskProfile(client_id=int(client_id))
            db.session.add(profile)

        # Actualizar flag de listas restrictivas en el perfil
        if has_match:
            profile.in_restrictive_lists = True
        else:
            profile.in_restrictive_lists = False

        # Recalcular perfil de riesgo automáticamente - auto_commit=False para hacer un solo commit
        ComplianceService.update_client_risk_profile(int(client_id), current_user.id, auto_commit=False)

        # Auditoría
        audit = ComplianceAudit(
            user_id=current_user.id,
            action_type='Restrictive_List_Manual_Check',
            entity_type='Client',
            entity_id=int(client_id),
            description=f'Verificación manual de listas restrictivas: {overall_result}',
            changes=json.dumps({
                'result': overall_result,
                'provider': 'Manual',
                'has_attachments': len(attachment_urls) > 0
            }),
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        db.session.add(audit)

        # Commit de toda la transacción
        db.session.commit()

        logger.info(f"Verificación manual guardada para cliente {client_id}: {overall_result}")

        return jsonify({
            'success': True,
            'message': 'Verificación guardada correctamente',
            'data': {
                'result': overall_result,
                'checked_at': check.checked_at.strftime('%Y-%m-%d %H:%M:%S')
            }
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error guardando verificación de listas restrictivas: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@compliance_bp.route('/api/restrictive-lists/last-check/<int:client_id>')
@login_required
@middle_office_required
def get_last_restrictive_check(client_id):
    """API: Obtener la última verificación de un cliente para pre-cargar el modal"""
    try:
        import logging
        logger = logging.getLogger(__name__)

        client = Client.query.get_or_404(client_id)

        # Buscar última verificación manual
        last_check = RestrictiveListCheck.query.filter_by(
            client_id=client_id,
            is_manual=True
        ).order_by(RestrictiveListCheck.checked_at.desc()).first()

        if not last_check:
            return jsonify({
                'success': True,
                'has_previous': False,
                'data': None
            })

        # Retornar datos de la última verificación
        data = {
            'ofac_checked': last_check.ofac_checked,
            'ofac_result': last_check.ofac_result,
            'ofac_details': last_check.ofac_details,
            'onu_checked': last_check.onu_checked,
            'onu_result': last_check.onu_result,
            'onu_details': last_check.onu_details,
            'uif_checked': last_check.uif_checked,
            'uif_result': last_check.uif_result,
            'uif_details': last_check.uif_details,
            'interpol_checked': last_check.interpol_checked,
            'interpol_result': last_check.interpol_result,
            'interpol_details': last_check.interpol_details,
            'denuncias_checked': last_check.denuncias_checked,
            'denuncias_result': last_check.denuncias_result,
            'denuncias_details': last_check.denuncias_details,
            'otras_listas_checked': last_check.otras_listas_checked,
            'otras_listas_result': last_check.otras_listas_result,
            'otras_listas_details': last_check.otras_listas_details,
            'observations': last_check.observations,
            'checked_at': last_check.checked_at.strftime('%d/%m/%Y %H:%M'),
            'checked_by': last_check.checker.username if last_check.checker else 'Sistema'
        }

        return jsonify({
            'success': True,
            'has_previous': True,
            'data': data
        })

    except Exception as e:
        import logging
        import traceback
        logger = logging.getLogger(__name__)
        logger.error(f"Error obteniendo última verificación: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@compliance_bp.route('/api/restrictive-lists/history/<int:client_id>')
@login_required
@middle_office_required
def restrictive_lists_history(client_id):
    """API: Historial de verificaciones de listas restrictivas de un cliente"""
    try:
        client = Client.query.get_or_404(client_id)

        checks = RestrictiveListCheck.query.filter_by(
            client_id=client_id
        ).order_by(RestrictiveListCheck.checked_at.desc()).all()

        data = []
        for check in checks:
            checker_name = check.checker.username if check.checker else 'Sistema'

            data.append({
                'id': check.id,
                'result': check.result,
                'checked_at': check.checked_at.strftime('%d/%m/%Y %H:%M'),
                'checked_by': checker_name,
                'ofac_checked': check.ofac_checked,
                'ofac_result': check.ofac_result,
                'ofac_details': check.ofac_details,
                'onu_checked': check.onu_checked,
                'onu_result': check.onu_result,
                'onu_details': check.onu_details,
                'uif_checked': check.uif_checked,
                'uif_result': check.uif_result,
                'uif_details': check.uif_details,
                'interpol_checked': check.interpol_checked,
                'interpol_result': check.interpol_result,
                'interpol_details': check.interpol_details,
                'denuncias_checked': check.denuncias_checked,
                'denuncias_result': check.denuncias_result,
                'denuncias_details': check.denuncias_details,
                'otras_listas_checked': check.otras_listas_checked,
                'otras_listas_result': check.otras_listas_result,
                'otras_listas_details': check.otras_listas_details,
                'observations': check.observations,
                'attachments': check.attachments
            })

        return jsonify({
            'success': True,
            'data': data
        })

    except Exception as e:
        import logging
        import traceback
        logger = logging.getLogger(__name__)
        logger.error(f"Error obteniendo historial de listas restrictivas: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== AUDITORÍA ====================

@compliance_bp.route('/audit')
@login_required
@middle_office_required
def audit():
    """Página de auditoría"""
    return render_template('compliance/audit.html')


@compliance_bp.route('/api/audit')
@login_required
@middle_office_required
def api_audit():
    """API: Log de auditoría"""
    try:
        draw = request.args.get('draw', type=int, default=1)
        start = request.args.get('start', type=int, default=0)
        length = request.args.get('length', type=int, default=10)

        query = ComplianceAudit.query
        total_records = query.count()

        audits = query.order_by(ComplianceAudit.created_at.desc()) \
                     .limit(length) \
                     .offset(start) \
                     .all()

        data = []
        for audit_log in audits:
            data.append({
                'id': audit_log.id,
                'user': audit_log.user.username,
                'action_type': audit_log.action_type,
                'entity_type': audit_log.entity_type,
                'entity_id': audit_log.entity_id,
                'description': audit_log.description,
                'ip_address': audit_log.ip_address,
                'created_at': audit_log.created_at.strftime('%Y-%m-%d %H:%M:%S')
            })

        return jsonify({
            'draw': draw,
            'recordsTotal': total_records,
            'recordsFiltered': total_records,
            'data': data
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
