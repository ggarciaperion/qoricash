"""
Servicio de Notificaciones para QoriCash Trading V2

Maneja notificaciones en tiempo real usando SocketIO.
"""
from app.extensions import socketio


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
            print(f"Error enviando notificación de nueva operación: {e}")
    
    @staticmethod
    def notify_operation_updated(operation, old_status=None):
        """
        Notificar operación actualizada
        
        Args:
            operation: Objeto Operation
            old_status: Estado anterior (opcional)
        """
        try:
            data = {
                'operation_id': operation.operation_id,
                'client_name': operation.client.full_name if operation.client else 'N/A',
                'status': operation.status,
                'old_status': old_status
            }
            
            socketio.emit('operacion_actualizada', data, namespace='/')
        except Exception as e:
            print(f"Error enviando notificación de operación actualizada: {e}")
    
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
            print(f"Error enviando notificación de operación completada: {e}")
    
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
            print(f"Error enviando notificación de operación cancelada: {e}")
    
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
            print(f"Error enviando notificación a rol {role}: {e}")
    
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
            print(f"Error enviando notificación a usuario {user_id}: {e}")
    
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
            print(f"Error enviando notificación broadcast: {e}")
    
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
            print(f"Error enviando notificación de nuevo cliente: {e}")
    
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
            print(f"Error enviando notificación de nuevo usuario: {e}")
    
    @staticmethod
    def notify_dashboard_update():
        """
        Notificar actualización del dashboard
        """
        try:
            socketio.emit('dashboard_update', {}, namespace='/')
        except Exception as e:
            print(f"Error enviando notificación de actualización de dashboard: {e}")

    @staticmethod
    def notify_position_update():
        """
        Notificar actualización de la posición
        """
        try:
            socketio.emit('position_update', {}, namespace='/')
        except Exception as e:
            print(f"Error enviando notificación de actualización de posición: {e}")

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

            print(f"Notificación enviada a operador {operator_user.username} (ID: {operator_user.id}) - Operación {operation.operation_id}")
        except Exception as e:
            print(f"Error enviando notificación de asignación de operación: {e}")

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

            print(f"Notificación de reasignación enviada: {operation.operation_id} -> {new_operator.username}")
        except Exception as e:
            print(f"Error enviando notificación de reasignación: {e}")
