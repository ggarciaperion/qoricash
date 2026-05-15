"""
Rutas de Compliance para Middle Office - QoriCash Trading V2
"""
import json
from flask import Blueprint, render_template, request, jsonify, redirect, url_for
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

@compliance_bp.route('/')
@compliance_bp.route('')
@login_required
@middle_office_required
def compliance_index():
    """Ruta raíz de compliance — redirige al dashboard principal"""
    return redirect(url_for('dashboard.index'))


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
    alert = db.get_or_404(ComplianceAlert, alert_id)
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

        # 1. Obtener TODOS los clientes (excluir demo_trader)
        from app.models.user import User
        _demo_id = User.get_demo_user_id()
        _cq = Client.query.filter(Client.created_by != _demo_id) if _demo_id else Client.query
        all_clients = _cq.all()
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

        # 3. Obtener TODOS los perfiles con sus clientes (INNER JOIN, excluir demo_trader)
        profiles_q = db.session.query(ClientRiskProfile, Client).join(
            Client, ClientRiskProfile.client_id == Client.id
        )
        if _demo_id:
            profiles_q = profiles_q.filter(Client.created_by != _demo_id)
        profiles = profiles_q.all()

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

    client = db.get_or_404(Client, client_id)
    profile = ClientRiskProfile.query.filter_by(client_id=client_id).first()

    operations = Operation.query.filter_by(client_id=client.id).order_by(Operation.created_at.desc()).all()

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

        # Obtener TODOS los clientes (excluir demo_trader)
        from app.models.user import User
        _demo_id = User.get_demo_user_id()
        _cq = Client.query.filter(Client.created_by != _demo_id) if _demo_id else Client.query
        all_clients = _cq.order_by(Client.created_at.desc()).all()

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
        client = db.get_or_404(Client, client_id)

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

        # Enviar correo de activación con contraseña temporal SOLO si fue creado por un Trader
        try:
            from app.services.email_service import EmailService
            from app.utils.password_generator import generate_simple_password

            # LÓGICA CORREGIDA: Solo generar contraseña temporal si fue creado manualmente por un Trader
            # Clientes auto-registrados (Web, Plataforma/Móvil) ya tienen su propia contraseña
            temporary_password = None

            # Verificar si el cliente fue creado por un Trader (creación manual desde sistema web)
            should_generate_password = False
            if client.creator:
                creator_role = client.creator.role if hasattr(client.creator, 'role') else None
                should_generate_password = (creator_role == 'Trader')
                logger.info(f'🔍 [KYC APPROVE] Cliente {client.dni} creado por: {client.creator.username} (rol: {creator_role})')

            if was_inactive and should_generate_password:
                # Solo generar contraseña temporal para clientes creados manualmente por Traders
                temporary_password = generate_simple_password(length=10)

                # Establecer contraseña en el cliente
                client.set_password(temporary_password)
                client.requires_password_change = True
                db.session.commit()

                logger.info(f'✅ [KYC APPROVE] Contraseña temporal generada para cliente {client.dni} (creado por Trader)')
            elif was_inactive and not should_generate_password:
                logger.info(f'ℹ️ [KYC APPROVE] Cliente {client.dni} auto-registrado - NO se genera contraseña temporal (mantiene su contraseña original)')

            # Enviar correo diferenciado según tipo de activación
            from app.services.email_templates import EmailTemplates

            trader = client.creator if hasattr(client, 'creator') and client.creator else current_user

            if should_generate_password:
                # Cliente creado por Trader - enviar con contraseña temporal
                EmailTemplates.send_activation_with_temp_password(client, trader, temporary_password)
                logger.info(f'✉️ [KYC APPROVE] Email de activación CON contraseña enviado a {client.dni}')
            else:
                # Cliente auto-registrado - enviar sin contraseña
                EmailTemplates.send_activation_without_password(client)
                logger.info(f'✉️ [KYC APPROVE] Email de activación SIN contraseña enviado a {client.dni}')

            # El trader ya queda en CC del correo de activación enviado al cliente
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
        client = db.get_or_404(Client, client_id)

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
        client = db.get_or_404(Client, client_id)

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
        client = db.get_or_404(Client, client_id)
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
        client = db.get_or_404(Client, client_id)

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

        # Obtener todos los clientes (excluir demo_trader)
        from app.models.user import User
        _demo_id = User.get_demo_user_id()
        _cq = Client.query.filter(Client.created_by != _demo_id) if _demo_id else Client.query
        all_clients = _cq.order_by(Client.created_at.desc()).all()
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

        client = db.get_or_404(Client, int(client_id))

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

        client = db.get_or_404(Client, client_id)

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
        client = db.get_or_404(Client, client_id)

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


# ==================== SCREENING AUTOMÁTICO ====================

@compliance_bp.route('/api/screening/auto/<int:client_id>', methods=['POST'])
@login_required
@middle_office_required
@csrf.exempt
def auto_screen_client(client_id):
    """
    API: Screening automático contra listas OFAC + ONU.
    Descarga las listas si no están en caché (o tienen más de 7 días),
    ejecuta fuzzy matching y guarda el resultado en RestrictiveListCheck.
    """
    try:
        from app.models.client import Client
        from app.models.compliance import RestrictiveListCheck, ClientRiskProfile
        from app.models.audit_log import AuditLog
        from app.services import sanctions_screening_service as sss

        client = db.session.get(Client, client_id)
        if not client:
            return jsonify({'success': False, 'error': 'Cliente no encontrado'}), 404

        # Ejecutar screening
        result = sss.screen_client(client_id)

        if 'error' in result:
            return jsonify({'success': False, 'error': result['error']}), 400

        overall     = result['overall']
        ofac_result = result['ofac_result']
        un_result   = result['un_result']

        def _details_json(matches):
            return json.dumps(matches, ensure_ascii=False) if matches else None

        # Guardar en RestrictiveListCheck (is_manual=False)
        check = RestrictiveListCheck(
            client_id    = client_id,
            list_type    = 'AUTO_COMPREHENSIVE',
            provider     = 'QoriCash_AutoScreen',
            result       = overall,
            match_score  = result['max_score'],
            details      = json.dumps({
                'names_searched': result['names_searched'],
                'all_matches':    result['all_matches'],
                'data_sources':   result['data_sources'],
            }, ensure_ascii=False),
            is_manual    = False,
            # OFAC
            ofac_checked = True,
            ofac_result  = ofac_result,
            ofac_details = _details_json(result['ofac_matches']),
            # ONU
            onu_checked  = True,
            onu_result   = un_result,
            onu_details  = _details_json(result['un_matches']),
            # PEP, UIF, Interpol — pendiente manual
            pep_checked  = False,
            uif_checked  = False,
            interpol_checked = False,
            denuncias_checked = False,
            otras_listas_checked = False,
            checked_by   = current_user.id,
        )
        db.session.add(check)

        # Actualizar perfil de riesgo
        profile = ClientRiskProfile.query.filter_by(client_id=client_id).first()
        if profile:
            profile.in_restrictive_lists = (overall == 'Match')
            db.session.add(profile)

        # Auditoría
        AuditLog.log_action(
            user_id   = current_user.id,
            action    = 'AUTO_SCREEN',
            entity    = 'Client',
            entity_id = client_id,
            details   = f'Screening automático: {overall} (score máx: {result["max_score"]})',
        )

        db.session.commit()

        return jsonify({
            'success':       True,
            'overall':       overall,
            'max_score':     result['max_score'],
            'ofac_result':   ofac_result,
            'ofac_matches':  result['ofac_matches'],
            'un_result':     un_result,
            'un_matches':    result['un_matches'],
            'names_searched': result['names_searched'],
            'data_sources':  result['data_sources'],
            'check_id':      check.id,
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f'[AutoScreen] Error: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@compliance_bp.route('/api/screening/status/<int:client_id>')
@login_required
@middle_office_required
def screening_status(client_id):
    """API: Último resultado de screening automático para un cliente."""
    try:
        from app.models.compliance import RestrictiveListCheck
        last = RestrictiveListCheck.query.filter_by(
            client_id=client_id, is_manual=False, list_type='AUTO_COMPREHENSIVE'
        ).order_by(RestrictiveListCheck.checked_at.desc()).first()

        if not last:
            return jsonify({'success': True, 'screened': False})

        details = {}
        if last.details:
            try:
                details = json.loads(last.details)
            except Exception:
                pass

        return jsonify({
            'success':       True,
            'screened':      True,
            'overall':       last.result,
            'max_score':     last.match_score,
            'ofac_result':   last.ofac_result,
            'ofac_matches':  json.loads(last.ofac_details) if last.ofac_details else [],
            'un_result':     last.onu_result,
            'un_matches':    json.loads(last.onu_details) if last.onu_details else [],
            'names_searched': details.get('names_searched', []),
            'data_sources':  details.get('data_sources', {}),
            'checked_at':    last.checked_at.strftime('%d/%m/%Y %H:%M') if last.checked_at else None,
            'checked_by':    getattr(last.checker, 'username', None),
        })

    except Exception as e:
        logger.error(f'[ScreeningStatus] Error: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== DECISIONES DE SCREENING ====================

@compliance_bp.route('/api/screening/decision/<int:check_id>', methods=['POST'])
@login_required
@middle_office_required
@csrf.exempt
def save_screening_decisions(check_id):
    """
    API: Guarda las decisiones del analista sobre las coincidencias detectadas.
    Payload JSON:
      {
        decisions: [{ match_idx, match_name, source, score, result_type,
                      decision: 'confirm'|'discard', reason }],
        analyst_notes: str
      }
    """
    import traceback, logging as _log
    try:
        from app.models.compliance import (
            RestrictiveListCheck, ClientRiskProfile,
            ComplianceAlert, ComplianceAudit
        )
        from app.services.compliance_service import ComplianceService

        payload       = request.get_json() or {}
        decisions     = payload.get('decisions', [])
        analyst_notes = payload.get('analyst_notes', '').strip()

        check = db.get_or_404(RestrictiveListCheck, check_id)

        # Parsear detalles existentes
        details = {}
        if check.details:
            try:
                details = json.loads(check.details)
            except Exception:
                pass

        now = now_peru()
        now_str = now.strftime('%d/%m/%Y %H:%M')

        # Enriquecer cada decisión con metadatos del analista
        enriched = []
        for d in decisions:
            enriched.append({
                **d,
                'decided_by': current_user.username,
                'decided_at': now_str,
            })

        details['decisions']     = enriched
        details['analyst_notes'] = analyst_notes
        details['verdict_by']    = current_user.username
        details['verdict_at']    = now_str

        # ── Calcular veredicto final ───────────────────────────────────────
        confirmed           = [d for d in enriched if d.get('decision') == 'confirm']
        confirmed_matches   = [d for d in confirmed if d.get('result_type') == 'Match']
        confirmed_potential = [d for d in confirmed if d.get('result_type') == 'Potential_Match']

        if confirmed_matches:
            final_verdict = 'Match'
        elif confirmed_potential:
            final_verdict = 'Potential_Match'
        else:
            final_verdict = 'Clean'

        details['final_verdict'] = final_verdict

        check.details      = json.dumps(details, ensure_ascii=False)
        check.result       = final_verdict
        check.observations = analyst_notes

        # ── Actualizar perfil de riesgo ───────────────────────────────────
        profile = ClientRiskProfile.query.filter_by(client_id=check.client_id).first()
        if not profile:
            profile = ClientRiskProfile(client_id=check.client_id)
            db.session.add(profile)

        if final_verdict == 'Match':
            profile.in_restrictive_lists = True
            profile.risk_score = min(100, (profile.risk_score or 0) + 40)
            if profile.kyc_status not in ['Rechazado']:
                profile.kyc_status = 'Rechazado'
                profile.kyc_notes  = (profile.kyc_notes or '') + (
                    f'\n[{now_str}] Coincidencia confirmada en listas restrictivas '
                    f'por {current_user.username}.'
                )
            # Crear alerta Alta
            names_str = ', '.join(d.get('match_name', '') for d in confirmed_matches[:3])
            alert = ComplianceAlert(
                alert_type  = 'KYC',
                severity    = 'Alta',
                client_id   = check.client_id,
                title       = f'Coincidencia CONFIRMADA en listas restrictivas: {names_str}',
                description = (
                    f'El analista {current_user.username} confirmó coincidencia '
                    f'en listas OFAC/ONU. KYC rechazado automáticamente.'
                ),
                details     = json.dumps({'check_id': check_id, 'decisions': enriched},
                                         ensure_ascii=False),
                status      = 'Pendiente',
            )
            db.session.add(alert)

        elif final_verdict == 'Potential_Match':
            profile.in_restrictive_lists = True
            profile.risk_score = min(100, (profile.risk_score or 0) + 15)
            alert = ComplianceAlert(
                alert_type  = 'KYC',
                severity    = 'Media',
                client_id   = check.client_id,
                title       = 'Coincidencia parcial confirmada en listas restrictivas',
                description = (
                    f'El analista {current_user.username} confirmó coincidencia '
                    f'parcial (Potential_Match). Requiere revisión adicional.'
                ),
                details     = json.dumps({'check_id': check_id, 'decisions': enriched},
                                         ensure_ascii=False),
                status      = 'Pendiente',
            )
            db.session.add(alert)

        else:  # Clean — todas descartadas
            profile.in_restrictive_lists = False
            ComplianceService.update_client_risk_profile(
                check.client_id, current_user.id, auto_commit=False
            )

        # ── Auditoría ─────────────────────────────────────────────────────
        discarded = len(decisions) - len(confirmed)
        audit = ComplianceAudit(
            user_id     = current_user.id,
            action_type = 'Screening_Decision',
            entity_type = 'Client',
            entity_id   = check.client_id,
            description = (
                f'Decisiones de screening guardadas: {final_verdict} '
                f'({len(confirmed)} confirmadas, {discarded} descartadas)'
            ),
            changes     = json.dumps({
                'check_id':        check_id,
                'final_verdict':   final_verdict,
                'confirmed_count': len(confirmed),
                'discarded_count': discarded,
            }),
            ip_address  = request.remote_addr,
            user_agent  = request.headers.get('User-Agent'),
        )
        db.session.add(audit)
        db.session.commit()

        return jsonify({
            'success':       True,
            'final_verdict': final_verdict,
            'message':       f'Decisiones guardadas. Veredicto final: {final_verdict}',
        })

    except Exception as e:
        db.session.rollback()
        _log.error(f'[ScreeningDecision] {e}')
        _log.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@compliance_bp.route('/api/screening/history/<int:client_id>')
@login_required
@middle_office_required
def screening_history(client_id):
    """API: Historial de búsquedas automáticas en listas restrictivas para un cliente."""
    try:
        from app.models.compliance import RestrictiveListCheck

        checks = RestrictiveListCheck.query.filter_by(
            client_id=client_id,
            is_manual=False,
            list_type='AUTO_COMPREHENSIVE',
        ).order_by(RestrictiveListCheck.checked_at.desc()).all()

        data = []
        for c in checks:
            details = {}
            if c.details:
                try:
                    details = json.loads(c.details)
                except Exception:
                    pass

            final_verdict   = details.get('final_verdict') or c.result
            verdict_by      = details.get('verdict_by')
            verdict_at      = details.get('verdict_at')
            decisions_count = len(details.get('decisions', []))
            confirmed_count = sum(1 for d in details.get('decisions', []) if d.get('decision') == 'confirm')

            data.append({
                'id':              c.id,
                'checked_at':      c.checked_at.strftime('%d/%m/%Y %H:%M') if c.checked_at else '-',
                'initial_result':  c.result,
                'final_verdict':   final_verdict,
                'max_score':       c.match_score or 0,
                'ofac_result':     c.ofac_result or 'Clean',
                'un_result':       c.onu_result or 'Clean',
                'checked_by':      c.checker.username if c.checker else 'Sistema',
                'verdict_by':      verdict_by,
                'verdict_at':      verdict_at,
                'decisions_count': decisions_count,
                'confirmed_count': confirmed_count,
                'has_decisions':   decisions_count > 0,
            })

        return jsonify({'success': True, 'data': data})

    except Exception as e:
        import logging, traceback
        logging.error(f'[ScreeningHistory] {e}')
        logging.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@compliance_bp.route('/api/screening/history/<int:check_id>/delete', methods=['DELETE'])
@login_required
@middle_office_required
@csrf.exempt
def delete_screening_history(check_id):
    """API: Eliminar una entrada del historial de búsquedas en listas restrictivas."""
    try:
        from app.models.compliance import RestrictiveListCheck
        check = db.get_or_404(RestrictiveListCheck, check_id)
        db.session.delete(check)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Entrada eliminada correctamente'})
    except Exception as e:
        db.session.rollback()
        logger.error(f'[DeleteScreeningHistory] {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@compliance_bp.route('/api/screening/report/<int:check_id>')
@login_required
@middle_office_required
def screening_report(check_id):
    """Página HTML imprimible con el reporte de screening. Abre en nueva pestaña."""
    from app.models.compliance import RestrictiveListCheck
    from app.models.client import Client

    check  = db.get_or_404(RestrictiveListCheck, check_id)
    client = db.get_or_404(Client, check.client_id)

    details   = {}
    if check.details:
        try:
            details = json.loads(check.details)
        except Exception:
            pass

    ofac_matches = []
    un_matches   = []
    if check.ofac_details:
        try:
            ofac_matches = json.loads(check.ofac_details)
        except Exception:
            pass
    if check.onu_details:
        try:
            un_matches = json.loads(check.onu_details)
        except Exception:
            pass

    return render_template(
        'compliance/screening_report.html',
        client       = client,
        check        = check,
        details      = details,
        ofac_matches = ofac_matches,
        un_matches   = un_matches,
        analyst      = current_user,
    )


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
