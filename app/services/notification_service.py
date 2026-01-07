"""
Servicio de Notificaciones para QoriCash Trading V2

Maneja notificaciones en tiempo real usando SocketIO.
"""
from app.extensions import socketio
import logging

logger = logging.getLogger(__name__)


class NotificationService:
    """Servicio de notificaciones en tiempo real"""
    
    @staticmethod
    def notify_new_operation(operation):
        """
        Notificar nueva operación creada
        
        Args:
            operation: Objeto Operation
        """
        try:
            data = {
                'operation_id': operation.operation_id,
                'client_name': operation.client.full_name if operation.client else 'N/A',
                'operation_type': operation.operation_type,
                'amount_usd': float(operation.amount_usd),
                'status': operation.status,
                'created_by': operation.user.username if operation.user else 'N/A'
            }
            
            socketio.emit('nueva_operacion', data, namespace='/')
        except Exception as e:
            logger.error(f"Error enviando notificación de nueva operación: {e}")
    
    @staticmethod
    def notify_operation_updated(operation, old_status=None):
        """
        Notificar operación actualizada

        Args:
            operation: Objeto Operation
            old_status: Estado anterior (opcional)
        """
        try:
            # Enviar datos completos de la operación para actualizar el sistema web
            data = {
                'id': operation.id,
                'operation_id': operation.operation_id,
                'client_id': operation.client_id,
                'client_name': operation.client.full_name if operation.client else 'N/A',
                'client_dni': operation.client.dni if operation.client else None,
                'status': operation.status,
                'old_status': old_status,
                'operation_type': operation.operation_type,
                'amount_usd': float(operation.amount_usd) if operation.amount_usd else 0,
                'amount_pen': float(operation.amount_pen) if operation.amount_pen else 0,
                'exchange_rate': float(operation.exchange_rate) if operation.exchange_rate else 0,
                'assigned_operator_id': operation.assigned_operator_id,
                'assigned_operator_name': operation.assigned_operator.full_name if operation.assigned_operator else None,
                'client_deposits': operation.client_deposits or [],
                'client_payments': operation.client_payments or [],
                'total_deposits': operation.total_deposits,
                'total_payments': operation.total_payments,
                'created_at': operation.created_at.isoformat() if operation.created_at else None,
                'updated_at': operation.updated_at.isoformat() if operation.updated_at else None,
            }

            socketio.emit('operacion_actualizada', data, namespace='/')
            logger.info(f"📡 Socket.IO emitido: operacion_actualizada para {operation.operation_id}")
        except Exception as e:
            logger.error(f"Error enviando notificación de operación actualizada: {e}")
    
    @staticmethod
    def notify_operation_completed(operation):
        """
        Notificar operación completada
        
        Args:
            operation: Objeto Operation
        """
        try:
            data = {
                'operation_id': operation.operation_id,
                'client_name': operation.client.full_name if operation.client else 'N/A',
                'amount_usd': float(operation.amount_usd),
                'amount_pen': float(operation.amount_pen)
            }
            
            socketio.emit('operacion_completada', data, namespace='/')
        except Exception as e:
            logger.error(f"Error enviando notificación de operación completada: {e}")
    
    @staticmethod
    def notify_operation_canceled(operation, reason=None):
        """
        Notificar operación cancelada
        
        Args:
            operation: Objeto Operation
            reason: Razón de cancelación (opcional)
        """
        try:
            data = {
                'operation_id': operation.operation_id,
                'client_name': operation.client.full_name if operation.client else 'N/A',
                'reason': reason
            }
            
            socketio.emit('operacion_cancelada', data, namespace='/')
        except Exception as e:
            logger.error(f"Error enviando notificación de operación cancelada: {e}")
    
    @staticmethod
    def notify_to_role(role, message_type, data):
        """
        Notificar a usuarios de un rol específico
        
        Args:
            role: Rol a notificar ('Master', 'Trader', 'Operador')
            message_type: Tipo de mensaje
            data: Datos del mensaje
        """
        try:
            data['target_role'] = role
            socketio.emit(message_type, data, namespace='/', room=role)
        except Exception as e:
            logger.error(f"Error enviando notificación a rol {role}: {e}")
    
    @staticmethod
    def notify_to_user(user_id, message_type, data):
        """
        Notificar a un usuario específico
        
        Args:
            user_id: ID del usuario
            message_type: Tipo de mensaje
            data: Datos del mensaje
        """
        try:
            room = f'user_{user_id}'
            socketio.emit(message_type, data, namespace='/', room=room)
        except Exception as e:
            logger.error(f"Error enviando notificación a usuario {user_id}: {e}")
    
    @staticmethod
    def broadcast_notification(title, message, notification_type='info'):
        """
        Enviar notificación broadcast a todos
        
        Args:
            title: Título de la notificación
            message: Mensaje
            notification_type: Tipo ('info', 'success', 'warning', 'error')
        """
        try:
            data = {
                'title': title,
                'message': message,
                'type': notification_type
            }
            
            socketio.emit('notification', data, namespace='/')
        except Exception as e:
            logger.error(f"Error enviando notificación broadcast: {e}")
    
    @staticmethod
    def notify_new_client(client, created_by):
        """
        Notificar nuevo cliente creado
        
        Args:
            client: Objeto Client
            created_by: Usuario que creó
        """
        try:
            data = {
                'client_name': client.full_name,
                'client_dni': client.dni,
                'created_by': created_by.username if created_by else 'N/A'
            }
            
            socketio.emit('nuevo_cliente', data, namespace='/')
        except Exception as e:
            logger.error(f"Error enviando notificación de nuevo cliente: {e}")
    
    @staticmethod
    def notify_new_user(user, created_by):
        """
        Notificar nuevo usuario creado
        
        Args:
            user: Objeto User
            created_by: Usuario que creó
        """
        try:
            data = {
                'username': user.username,
                'role': user.role,
                'created_by': created_by.username if created_by else 'N/A'
            }
            
            # Solo notificar a Masters
            NotificationService.notify_to_role('Master', 'nuevo_usuario', data)
        except Exception as e:
            logger.error(f"Error enviando notificación de nuevo usuario: {e}")
    
    @staticmethod
    def notify_dashboard_update():
        """
        Notificar actualización del dashboard
        """
        try:
            socketio.emit('dashboard_update', {}, namespace='/')
        except Exception as e:
            logger.error(f"Error enviando notificación de actualización de dashboard: {e}")

    @staticmethod
    def notify_position_update():
        """
        Notificar actualización de la posición
        """
        try:
            socketio.emit('position_update', {}, namespace='/')
        except Exception as e:
            logger.error(f"Error enviando notificación de actualización de posición: {e}")

    @staticmethod
    def notify_operation_assigned(operation, operator_user):
        """
        Notificar al operador cuando se le asigna una operación

        Args:
            operation: Objeto Operation
            operator_user: Usuario operador asignado
        """
        try:
            data = {
                'operation_id': operation.operation_id,
                'operation_db_id': operation.id,
                'client_name': operation.client.full_name if operation.client else 'N/A',
                'operation_type': operation.operation_type,
                'amount_usd': float(operation.amount_usd) if operation.amount_usd else 0,
                'status': operation.status,
                'message': f'Se te ha asignado la operación {operation.operation_id}'
            }

            # Notificar solo al operador específico
            room = f'user_{operator_user.id}'
            socketio.emit('operacion_asignada', data, namespace='/', room=room)

            logger.info(f"Notificación enviada a operador {operator_user.username} (ID: {operator_user.id}) - Operación {operation.operation_id}")
        except Exception as e:
            logger.error(f"Error enviando notificación de asignación de operación: {e}")

    @staticmethod
    def notify_operation_reassigned(operation, old_operator, new_operator, reassigned_by):
        """
        Notificar cuando una operación es reasignada por Master

        Args:
            operation: Objeto Operation
            old_operator: Usuario operador anterior (puede ser None)
            new_operator: Usuario operador nuevo
            reassigned_by: Usuario Master que reasignó
        """
        try:
            data = {
                'operation_id': operation.operation_id,
                'operation_db_id': operation.id,
                'client_name': operation.client.full_name if operation.client else 'N/A',
                'operation_type': operation.operation_type,
                'amount_usd': float(operation.amount_usd) if operation.amount_usd else 0,
                'status': operation.status,
                'old_operator_name': old_operator.username if old_operator else 'No asignado',
                'new_operator_name': new_operator.username,
                'reassigned_by': reassigned_by.username,
                'message': f'Se te ha reasignado la operación {operation.operation_id}'
            }

            # Notificar al nuevo operador
            room_new = f'user_{new_operator.id}'
            socketio.emit('operacion_asignada', data, namespace='/', room=room_new)

            # Notificar al operador anterior que ya no la tiene asignada
            if old_operator:
                data_old = data.copy()
                data_old['message'] = f'La operación {operation.operation_id} ha sido reasignada a {new_operator.username}'
                room_old = f'user_{old_operator.id}'
                socketio.emit('operacion_reasignada_removida', data_old, namespace='/', room=room_old)

            logger.info(f"Notificación de reasignación enviada: {operation.operation_id} -> {new_operator.username}")
        except Exception as e:
            logger.error(f"Error enviando notificación de reasignación: {e}")

    @staticmethod
    def notify_client_reassignment(client, reassigned_by_user, new_trader_id):
        """
        Notificar cuando un cliente es reasignado a otro trader

        Args:
            client: Objeto Client
            reassigned_by_user: Usuario Master que reasignó
            new_trader_id: ID del nuevo trader
        """
        try:
            from app.models.user import User

            new_trader = User.query.get(new_trader_id)
            if not new_trader:
                return

            old_trader = client.creator if hasattr(client, 'creator') else None

            data = {
                'client_id': client.id,
                'client_name': client.full_name or client.razon_social or client.dni,
                'client_dni': client.dni,
                'old_trader_name': old_trader.username if old_trader else 'No asignado',
                'new_trader_name': new_trader.username,
                'reassigned_by': reassigned_by_user.username,
                'message': f'Se te ha asignado el cliente {client.full_name or client.razon_social or client.dni}'
            }

            # Notificar al nuevo trader
            room_new = f'user_{new_trader.id}'
            socketio.emit('cliente_asignado', data, namespace='/', room=room_new)

            # Notificar al trader anterior que ya no tiene el cliente
            if old_trader:
                data_old = data.copy()
                data_old['message'] = f'El cliente {client.full_name or client.razon_social or client.dni} ha sido reasignado a {new_trader.username}'
                room_old = f'user_{old_trader.id}'
                socketio.emit('cliente_reasignado_removido', data_old, namespace='/', room=room_old)

            logger.info(f"Notificación de reasignación de cliente enviada: {client.dni} -> {new_trader.username}")
        except Exception as e:
            logger.error(f"Error enviando notificación de reasignación de cliente: {e}")

    @staticmethod
    def notify_bulk_client_reassignment(new_trader, reassigned_by_user, client_count):
        """
        Notificar reasignación masiva de clientes

        Args:
            new_trader: Usuario trader que recibe los clientes
            reassigned_by_user: Usuario Master que reasignó
            client_count: Cantidad de clientes reasignados
        """
        try:
            data = {
                'client_count': client_count,
                'new_trader_name': new_trader.username,
                'reassigned_by': reassigned_by_user.username,
                'message': f'Se te han asignado {client_count} cliente(s) nuevos'
            }

            # Notificar al nuevo trader
            room = f'user_{new_trader.id}'
            socketio.emit('clientes_asignados_masivo', data, namespace='/', room=room)

            logger.info(f"Notificación de reasignación masiva enviada: {client_count} clientes -> {new_trader.username}")
        except Exception as e:
            logger.error(f"Error enviando notificación de reasignación masiva: {e}")

    @staticmethod
    def notify_new_client(client, created_by_user):
        """
        Notificar cuando se crea un nuevo cliente

        Args:
            client: Objeto Client
            created_by_user: Usuario que creó el cliente
        """
        try:
            data = {
                'client_id': client.id,
                'client_name': client.full_name or client.razon_social or client.dni,
                'client_dni': client.dni,
                'created_by': created_by_user.username,
                'message': f'Nuevo cliente registrado: {client.full_name or client.razon_social or client.dni}'
            }

            # Notificar a todos los Masters y Operadores
            socketio.emit('nuevo_cliente', data, namespace='/')

            logger.info(f"Notificación de nuevo cliente enviada: {client.dni}")
        except Exception as e:
            logger.error(f"Error enviando notificación de nuevo cliente: {e}")

    @staticmethod
    def notify_client_documents_approved(client):
        """
        Notificar al cliente cuando sus documentos sean aprobados

        Args:
            client: Objeto Client
        """
        try:
            logger.info(f"🔔 [NOTIF-KYC] INICIO - Preparando notificación de documentos aprobados para cliente {client.dni}")

            data = {
                'type': 'documents_approved',
                'title': '✅ Cuenta Activada',
                'message': 'Tus documentos han sido aprobados. ¡Ya puedes realizar operaciones!',
                'client_dni': client.dni,
                'client_id': client.id,
                'client_name': client.full_name or client.razon_social,
            }

            # Notificar al cliente específico usando su DNI como room
            room = f'client_{client.dni}'
            logger.info(f"📡 [NOTIF-KYC] Enviando evento 'documents_approved' al room: {room}")
            logger.info(f"📦 [NOTIF-KYC] Datos: {data}")

            socketio.emit('documents_approved', data, namespace='/', room=room)

            logger.info(f"✅ [NOTIF-KYC] Notificación de documentos aprobados enviada exitosamente al cliente: {client.dni}")
        except Exception as e:
            logger.error(f"❌ [NOTIF-KYC] Error enviando notificación de documentos aprobados: {e}")
            logger.exception(e)

    @staticmethod
    def notify_operation_expired(operation):
        """
        Notificar al cliente cuando su operación expire por timeout

        NOTA: La notificación Socket.IO solo llega si la app está abierta y conectada.
        Para notificaciones cuando la app está cerrada, se envía correo electrónico.

        Args:
            operation: Objeto Operation
        """
        try:
            if not operation.client:
                logger.warning(f"⚠️ Operación {operation.operation_id} sin cliente asociado")
                return

            data = {
                'type': 'operation_expired',
                'operation_id': operation.operation_id,
                'title': '⏱️ Operación Expirada',
                'message': f'La operación {operation.operation_id} ha expirado por falta de transferencia. Puedes crear una nueva operación.',
                'client_dni': operation.client.dni,
                'client_id': operation.client_id,
            }

            # Notificar al cliente específico usando su DNI como room
            room = f'client_{operation.client.dni}'

            logger.info(f"📡 [SOCKET.IO] Intentando enviar notificación de operación expirada:")
            logger.info(f"   - Cliente DNI: {operation.client.dni}")
            logger.info(f"   - Room: {room}")
            logger.info(f"   - Operación: {operation.operation_id}")
            logger.info(f"   - Namespace: /")
            logger.info(f"   - Evento: operation_expired")

            # Emitir al room del cliente
            socketio.emit('operation_expired', data, namespace='/', room=room)

            logger.info(f"✅ [SOCKET.IO] Notificación emitida al room '{room}'")
            logger.info(f"   ⚠️ NOTA: Solo llegará si la app está abierta y conectada")

        except Exception as e:
            logger.error(f"❌ [SOCKET.IO] Error enviando notificación de operación expirada: {e}")
            import traceback
            logger.error(traceback.format_exc())
