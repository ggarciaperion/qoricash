"""
Servicio de Operaciones para QoriCash Trading V2

Core del negocio - Maneja todas las operaciones de cambio de divisas.
"""
from datetime import datetime, date
from sqlalchemy import func, and_
from app.extensions import db
from app.models.operation import Operation
from app.models.client import Client
from app.models.audit_log import AuditLog
from app.utils.validators import validate_amount, validate_exchange_rate
from app.utils.formatters import now_peru
import logging

logger = logging.getLogger(__name__)


class OperationService:
    """Servicio de gestión de operaciones"""
    
    @staticmethod
    def get_all_operations(include_relations=True):
        """
        Obtener todas las operaciones
        
        Args:
            include_relations: Si incluir datos de cliente y usuario
        
        Returns:
            list: Lista de operaciones
        """
        operations = Operation.query.order_by(Operation.created_at.desc()).all()
        
        if include_relations:
            return [op.to_dict(include_relations=True) for op in operations]
        
        return operations
    
    @staticmethod
    def get_operation_by_id(operation_id):
        """
        Obtener operación por ID numérico
        
        Args:
            operation_id: ID numérico
        
        Returns:
            Operation: Operación o None
        """
        return Operation.query.get(operation_id)
    
    @staticmethod
    def get_operation_by_operation_id(operation_id_str):
        """
        Obtener operación por operation_id (EXP-1001)
        
        Args:
            operation_id_str: ID de operación (EXP-XXXX)
        
        Returns:
            Operation: Operación o None
        """
        return Operation.query.filter_by(operation_id=operation_id_str).first()
    
    @staticmethod
    def get_operations_by_status(status):
        """
        Obtener operaciones por estado
        
        Args:
            status: Estado ('Pendiente', 'En proceso', 'Completada', 'Cancelado')
        
        Returns:
            list: Lista de operaciones
        """
        return Operation.query.filter_by(status=status).order_by(Operation.created_at.desc()).all()
    
    @staticmethod
    def get_operations_by_client(client_id):
        """
        Obtener operaciones de un cliente
        
        Args:
            client_id: ID del cliente
        
        Returns:
            list: Lista de operaciones
        """
        return Operation.query.filter_by(client_id=client_id).order_by(Operation.created_at.desc()).all()
    
    @staticmethod
    def get_today_operations():
        """
        Obtener operaciones de hoy (según zona horaria de Perú)
        Ordenadas con "En proceso" primero, luego por fecha descendente

        Returns:
            list: Lista de operaciones de hoy ordenadas por prioridad
        """
        from datetime import datetime, timedelta
        from sqlalchemy import case

        # Obtener inicio y fin del día en Perú
        now = now_peru()
        start_of_day = datetime(now.year, now.month, now.day, 0, 0, 0)
        end_of_day = datetime(now.year, now.month, now.day, 23, 59, 59)

        # Ordenar con "En proceso" primero usando CASE
        # 0 para "En proceso", 1 para el resto
        priority_order = case(
            (Operation.status == 'En proceso', 0),
            else_=1
        )

        return Operation.query.filter(
            Operation.created_at >= start_of_day,
            Operation.created_at <= end_of_day
        ).order_by(
            priority_order,  # Primero por prioridad (En proceso = 0)
            Operation.created_at.desc()  # Luego por fecha descendente
        ).all()
    
    @staticmethod
    def create_operation(current_user, client_id, operation_type, amount_usd, exchange_rate,
                        source_account=None, destination_account=None, notes=None, origen='sistema'):
        """
        Crear nueva operación

        Args:
            current_user: Usuario que crea
            client_id: ID del cliente
            operation_type: 'Compra' o 'Venta'
            amount_usd: Monto en dólares
            exchange_rate: Tipo de cambio
            source_account: Cuenta de origen (opcional)
            destination_account: Cuenta de destino (opcional)
            notes: Notas (opcional)
            origen: Origen de la operación - 'sistema' o 'plataforma' (opcional, default='sistema')

        Returns:
            tuple: (success: bool, message: str, operation: Operation|None)
        """
        # Validar permisos
        if not current_user or current_user.role not in ['Master', 'Trader', 'Plataforma', 'App']:
            return False, 'No tienes permiso para crear operaciones', None
        
        # Validar cliente
        client = Client.query.get(client_id)
        if not client:
            return False, 'Cliente no encontrado', None

        if client.status != 'Activo':
            # Si está inactivo por documentos, mostrar razón específica
            if client.inactive_reason and 'documentos' in client.inactive_reason.lower():
                return False, f'El cliente está inactivo: {client.inactive_reason}. Debe completar documentación pendiente.', None
            return False, 'El cliente no está activo', None

        # Validar límites de operaciones sin documentos completos
        can_operate, error_message = client.can_create_operation(float(amount_usd))
        if not can_operate:
            return False, error_message, None

        # Validar que Trader, Plataforma y App solo puedan crear operaciones para sus propios clientes
        if current_user.role in ['Trader', 'Plataforma', 'App']:
            if client.created_by != current_user.id:
                return False, 'Solo puedes crear operaciones para tus propios clientes', None

        # Validar tipo de operación
        if operation_type not in ['Compra', 'Venta']:
            return False, 'Tipo de operación inválido', None
        
        # Validar montos
        is_valid, error = validate_amount(amount_usd)
        if not is_valid:
            return False, f'Monto USD inválido: {error}', None
        
        is_valid, error = validate_exchange_rate(exchange_rate)
        if not is_valid:
            return False, f'Tipo de cambio inválido: {error}', None
        
        # Calcular monto en soles
        amount_pen = float(amount_usd) * float(exchange_rate)
        
        # Generar operation_id
        operation_id = Operation.generate_operation_id()
        
        # Validar origen
        if origen not in ['sistema', 'plataforma', 'app']:
            origen = 'sistema'  # Default a 'sistema' si el valor es inválido

        # Crear operación
        operation = Operation(
            operation_id=operation_id,
            client_id=client_id,
            user_id=current_user.id,
            operation_type=operation_type,
            amount_usd=amount_usd,
            exchange_rate=exchange_rate,
            amount_pen=amount_pen,
            source_account=source_account,
            destination_account=destination_account,
            notes=notes,
            origen=origen,
            status='Pendiente',
            created_at=now_peru()
        )
        
        db.session.add(operation)
        db.session.flush()  # Flush para obtener el ID de la operación

        # Registrar en auditoría
        AuditLog.log_action(
            user_id=current_user.id,
            action='CREATE_OPERATION',
            entity='Operation',
            entity_id=operation.id,
            details=f'Operación {operation_id} creada: {operation_type} ${amount_usd} para {client.full_name}'
        )

        # Commit único para operation y audit_log juntos
        db.session.commit()

        # --- Sistema de control de documentos parciales ---
        try:
            # Incrementar contador si el cliente no tiene documentos completos
            if not client.has_complete_documents:
                reached_limit = client.increment_operations_without_docs()

                if reached_limit:
                    # Cliente alcanzó el límite: inhabilitar automáticamente
                    client.disable_for_missing_documents()
                    db.session.commit()

                    logger.warning(f'Cliente {client.id} deshabilitado automáticamente por alcanzar límite de operaciones sin documentos')

                    # Enviar alertas por email a roles relevantes
                    try:
                        from app.services.email_service import EmailService
                        EmailService.send_client_disabled_for_documents_alert(
                            client=client,
                            operation=operation,
                            trader=current_user
                        )
                    except Exception as email_err:
                        logger.error(f'Error al enviar alerta de deshabilitación: {str(email_err)}')
                else:
                    # Aún puede operar pero actualizar contador
                    db.session.commit()
                    logger.info(f'Cliente {client.id} operación #{client.operations_without_docs_count} sin docs completos '
                              f'(límite: {client.operations_without_docs_limit})')
        except Exception as partial_docs_err:
            logger.error(f'Error en sistema de documentos parciales: {str(partial_docs_err)}')
            # No bloquear la operación si falla el sistema de límites

        # Enviar email de notificación (sin bloquear si falla)
        try:
            from app.services.email_service import EmailService
            logger.info(f'📧 Intentando enviar email de nueva operación {operation_id} a {client.email}...')
            EmailService.send_new_operation_email(operation)
            logger.info(f'✅ Email de nueva operación {operation_id} enviado exitosamente a {client.email}')
        except Exception as e:
            # Log el error pero no falla la operación
            logger.error(f'❌ Error al enviar email para operación {operation_id}: {str(e)}')
            import traceback
            logger.error(traceback.format_exc())

        return True, f'Operación {operation_id} creada exitosamente', operation
    
    @staticmethod
    def update_operation_status(current_user, operation_id, new_status, notes=None):
        """
        Actualizar estado de operación
        
        Args:
            current_user: Usuario que actualiza
            operation_id: ID numérico de la operación
            new_status: Nuevo estado
            notes: Notas adicionales (opcional)
        
        Returns:
            tuple: (success: bool, message: str, operation: Operation|None)
        """
        # Obtener operación
        operation = Operation.query.get(operation_id)
        if not operation:
            return False, 'Operación no encontrada', None
        
        # Validar nuevo estado
        if new_status not in ['Pendiente', 'En proceso', 'Completada', 'Cancelado']:
            return False, 'Estado inválido', None
        
        # Validar transición de estado
        valid_transitions = {
            'Pendiente': ['En proceso', 'Cancelado'],
            'En proceso': ['Completada', 'Cancelado'],
            'Completada': [],
            'Cancelado': []
        }
        
        if new_status not in valid_transitions.get(operation.status, []):
            return False, f'No se puede cambiar de {operation.status} a {new_status}', None
        
        # Guardar estado anterior
        old_status = operation.status
        
        # Actualizar estado
        operation.status = new_status
        operation.updated_at = now_peru()
        
        # Si se completa, registrar fecha
        if new_status == 'Completada':
            operation.completed_at = now_peru()
        
        # Actualizar notas si se proporcionan
        if notes:
            if operation.notes:
                operation.notes += f"\n\n[{now_peru().strftime('%Y-%m-%d %H:%M')}] {notes}"
            else:
                operation.notes = notes
        
        # Registrar en auditoría
        AuditLog.log_action(
            user_id=current_user.id,
            action='UPDATE_OPERATION_STATUS',
            entity='Operation',
            entity_id=operation.id,
            details=f'Operación {operation.operation_id}: {old_status} → {new_status}',
            notes=notes
        )

        # Commit único para operation y audit_log juntos
        db.session.commit()

        # Enviar email si la operación se completó
        if new_status == 'Completada':
            # Generar factura electrónica
            invoice_generated = False
            try:
                from app.services.invoice_service import InvoiceService
                import logging
                logger = logging.getLogger(__name__)

                logger.info(f'[OPERATION-{operation.operation_id}] ========== INICIANDO PROCESO DE FACTURACIÓN ==========')

                if InvoiceService.is_enabled():
                    logger.info(f'[OPERATION-{operation.operation_id}] ✅ Facturación electrónica HABILITADA')
                    logger.info(f'[OPERATION-{operation.operation_id}] Generando factura electrónica...')

                    success, message, invoice = InvoiceService.generate_invoice_for_operation(operation.id)

                    if success and invoice:
                        logger.info(f'[OPERATION-{operation.operation_id}] ✅ ÉXITO: Factura generada: {invoice.invoice_number}')
                        logger.info(f'[OPERATION-{operation.operation_id}] PDF URL: {invoice.nubefact_enlace_pdf}')
                        invoice_generated = True
                    else:
                        logger.error(f'[OPERATION-{operation.operation_id}] ❌ ERROR al generar factura: {message}')
                else:
                    logger.warning(f'[OPERATION-{operation.operation_id}] ⚠️ Facturación electrónica DESHABILITADA en configuración')
                    logger.warning(f'[OPERATION-{operation.operation_id}] Verifica NUBEFACT_ENABLED en variables de entorno')

                logger.info(f'[OPERATION-{operation.operation_id}] ========== FIN PROCESO DE FACTURACIÓN ==========')

            except Exception as e:
                # Log el error pero no falla la operación
                import logging
                logging.error(f'[OPERATION-{operation.operation_id}] ❌ EXCEPCIÓN al generar factura: {str(e)}')
                logging.exception(e)

            # Enviar email con comprobante (y factura si se generó)
            try:
                from app.services.email_service import EmailService
                EmailService.send_completed_operation_email(operation)
            except Exception as e:
                # Log el error pero no falla la actualización
                import logging
                logging.error(f'Error al enviar email de operación completada {operation.operation_id}: {str(e)}')

            # COMPLIANCE: Análisis automático de la operación
            try:
                from app.services.compliance_service import ComplianceService
                import logging
                logger = logging.getLogger(__name__)

                # Analizar operación para detectar patrones sospechosos
                alerts, risk_score = ComplianceService.analyze_operation(operation.id)

                logger.info(f'Compliance analysis for {operation.operation_id}: {len(alerts)} alerts, risk_score={risk_score}')

                # Actualizar perfil de riesgo del cliente
                ComplianceService.update_client_risk_profile(operation.client_id, current_user.id)

                # Log para Middle Office si hay alertas críticas
                critical_alerts = [a for a in alerts if a.severity == 'Crítica']
                if critical_alerts:
                    logger.warning(f'ALERTA CRÍTICA: Operación {operation.operation_id} generó {len(critical_alerts)} alerta(s) crítica(s)')

            except Exception as e:
                # Log el error pero no falla la operación
                import logging
                logging.error(f'Error en análisis de compliance para {operation.operation_id}: {str(e)}')

        return True, f'Estado actualizado a {new_status}', operation
    
    @staticmethod
    def update_operation_proofs(current_user, operation_id, payment_proof_url=None, operator_proof_url=None):
        """
        Actualizar comprobantes de operación
        
        Args:
            current_user: Usuario que actualiza
            operation_id: ID de la operación
            payment_proof_url: URL de comprobante de pago
            operator_proof_url: URL de comprobante del operador
        
        Returns:
            tuple: (success: bool, message: str, operation: Operation|None)
        """
        # Obtener operación
        operation = Operation.query.get(operation_id)
        if not operation:
            return False, 'Operación no encontrada', None
        
        # Actualizar URLs
        if payment_proof_url:
            operation.payment_proof_url = payment_proof_url
        
        if operator_proof_url:
            operation.operator_proof_url = operator_proof_url
        
        operation.updated_at = now_peru()

        # Registrar en auditoría
        AuditLog.log_action(
            user_id=current_user.id,
            action='UPDATE_OPERATION_PROOFS',
            entity='Operation',
            entity_id=operation.id,
            details=f'Comprobantes actualizados para operación {operation.operation_id}'
        )

        # Commit único para operation y audit_log juntos
        db.session.commit()

        return True, 'Comprobantes actualizados exitosamente', operation
    
    @staticmethod
    def cancel_operation(current_user, operation_id, reason):
        """
        Cancelar operación
        
        Args:
            current_user: Usuario que cancela
            operation_id: ID de la operación
            reason: Razón de cancelación
        
        Returns:
            tuple: (success: bool, message: str, operation: Operation|None)
        """
        # Obtener operación
        operation = Operation.query.get(operation_id)
        if not operation:
            return False, 'Operación no encontrada', None
        
        # Validar que se puede cancelar
        if not operation.can_be_canceled():
            return False, f'No se puede cancelar una operación en estado {operation.status}', None
        
        # Cancelar
        old_status = operation.status
        operation.status = 'Cancelado'
        operation.updated_at = now_peru()
        
        # Agregar razón a notas
        if operation.notes:
            operation.notes += f"\n\n[CANCELADO] {reason}"
        else:
            operation.notes = f"[CANCELADO] {reason}"
        
        # Registrar en auditoría
        AuditLog.log_action(
            user_id=current_user.id,
            action='CANCEL_OPERATION',
            entity='Operation',
            entity_id=operation.id,
            details=f'Operación {operation.operation_id} cancelada',
            notes=reason
        )

        # Commit único para operation y audit_log juntos
        db.session.commit()

        return True, 'Operación cancelada exitosamente', operation
    
    @staticmethod
    def get_dashboard_stats(month=None, year=None):
        """
        Obtener estadísticas para dashboard
        
        Args:
            month: Mes (1-12) opcional
            year: Año opcional
        
        Returns:
            dict: Estadísticas
        """
        # Si no se especifica mes/año, usar actual
        if not month or not year:
            now = now_peru()
            month = now.month
            year = now.year
        
        # Rango de fechas del mes
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
        
        # Operaciones del mes
        operations_month = Operation.query.filter(
            and_(
                Operation.created_at >= start_date,
                Operation.created_at < end_date
            )
        ).all()
        
        # Operaciones de hoy
        today = date.today()
        operations_today = Operation.query.filter(
            func.date(Operation.created_at) == today
        ).all()
        
        # Calcular estadísticas del mes
        completed_month = [op for op in operations_month if op.status == 'Completada']
        total_usd_month = sum(op.amount_usd for op in completed_month)
        total_pen_month = sum(op.amount_pen for op in completed_month)
        
        # Clientes únicos del mes
        unique_clients_month = len(set(op.client_id for op in operations_month))
        
        # Clientes activos (con al menos una operación completada)
        active_clients_month = len(set(op.client_id for op in completed_month))
        
        # Calcular estadísticas de hoy
        completed_today = [op for op in operations_today if op.status == 'Completada']
        total_usd_today = sum(op.amount_usd for op in completed_today)
        total_pen_today = sum(op.amount_pen for op in completed_today)
        unique_clients_today = len(set(op.client_id for op in operations_today))
        
        return {
            # Estadísticas del día
            'clients_today': unique_clients_today,
            'operations_today': len(operations_today),
            'usd_today': float(total_usd_today),
            'pen_today': float(total_pen_today),
            
            # Estadísticas del mes
            'clients_month': unique_clients_month,
            'active_clients_month': active_clients_month,
            'operations_month': len(operations_month),
            'usd_month': float(total_usd_month),
            'pen_month': float(total_pen_month),
            
            # Por estado
            'pending_count': sum(1 for op in operations_month if op.status == 'Pendiente'),
            'in_process_count': sum(1 for op in operations_month if op.status == 'En proceso'),
            'completed_count': len(completed_month),
            'canceled_count': sum(1 for op in operations_month if op.status == 'Cancelado')
        }
    
    @staticmethod
    def get_operations_for_operator():
        """
        Obtener operaciones relevantes para operador
        (Pendientes y En proceso)

        Returns:
            list: Lista de operaciones
        """
        return Operation.query.filter(
            Operation.status.in_(['Pendiente', 'En proceso'])
        ).order_by(Operation.created_at.desc()).all()

    @staticmethod
    def assign_operator_balanced():
        """
        Asignar un operador de forma balanceada

        Algoritmo:
        1. Obtener todos los usuarios con rol "Operador" activos
        2. Contar cuántas operaciones "En proceso" tiene cada uno asignadas
        3. Asignar al operador con menos operaciones asignadas

        Returns:
            int: ID del operador asignado, o None si no hay operadores disponibles
        """
        import logging
        logger = logging.getLogger(__name__)

        from app.models.user import User

        logger.info("🔍 Buscando operadores activos...")

        # Obtener todos los operadores activos
        operators = User.query.filter(
            and_(
                User.role == 'Operador',
                User.status == 'Activo'
            )
        ).all()

        logger.info(f"📊 Operadores encontrados: {len(operators)}")

        if not operators:
            logger.warning("⚠️ ADVERTENCIA: No hay operadores activos disponibles para asignar")
            return None

        # Log de operadores encontrados
        for op in operators:
            logger.info(f"  👤 Operador ID={op.id}, Usuario={op.username}, Email={op.email}")

        # Contar operaciones en proceso asignadas a cada operador
        operator_loads = {}
        for operator in operators:
            count = Operation.query.filter(
                and_(
                    Operation.assigned_operator_id == operator.id,
                    Operation.status == 'En proceso'
                )
            ).count()
            operator_loads[operator.id] = count
            logger.info(f"  📈 Operador ID={operator.id} ({operator.username}): {count} operaciones en proceso")

        # Encontrar el operador con menos carga
        min_load_operator_id = min(operator_loads, key=operator_loads.get)
        min_load = operator_loads[min_load_operator_id]

        logger.info(f"✅ Asignando operador: ID={min_load_operator_id}, Carga actual={min_load} operaciones")

        return min_load_operator_id
