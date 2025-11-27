"""
Socket.IO Events para QoriCash Trading V2
Maneja eventos de WebSocket para actualizaciones en tiempo real
"""
from flask_socketio import emit, join_room, leave_room
from flask_login import current_user
from app.extensions import socketio


# ============================================
# EVENTOS DE CONEXIÓN
# ============================================

@socketio.on('connect')
def handle_connect():
    """Maneja la conexión de un cliente WebSocket"""
    if current_user.is_authenticated:
        # Unir al usuario a su sala de rol
        join_room(f'role_{current_user.role}')

        # Unir al usuario a su sala personal
        join_room(f'user_{current_user.id}')

        # Sala global para todos los usuarios autenticados
        join_room('authenticated')

        print(f'Usuario {current_user.username} ({current_user.role}) conectado via WebSocket')

        # Notificar al usuario que se conectó exitosamente
        emit('connection_established', {
            'message': 'Conectado al sistema en tiempo real',
            'user': current_user.username,
            'role': current_user.role
        })


@socketio.on('disconnect')
def handle_disconnect():
    """Maneja la desconexión de un cliente WebSocket"""
    if current_user.is_authenticated:
        print(f'Usuario {current_user.username} desconectado')


# ============================================
# EVENTOS DE OPERACIONES
# ============================================

@socketio.on('operation_created')
def handle_operation_created(data):
    """Emite cuando se crea una nueva operación"""
    # No procesamos aquí, esto se llama desde las rutas
    pass


@socketio.on('operation_updated')
def handle_operation_updated(data):
    """Emite cuando se actualiza una operación"""
    # No procesamos aquí, esto se llama desde las rutas
    pass


@socketio.on('operation_deleted')
def handle_operation_deleted(data):
    """Emite cuando se elimina una operación"""
    # No procesamos aquí, esto se llama desde las rutas
    pass


# ============================================
# EVENTOS DE CLIENTES
# ============================================

@socketio.on('client_created')
def handle_client_created(data):
    """Emite cuando se crea un nuevo cliente"""
    # No procesamos aquí, esto se llama desde las rutas
    pass


@socketio.on('client_updated')
def handle_client_updated(data):
    """Emite cuando se actualiza un cliente"""
    # No procesamos aquí, esto se llama desde las rutas
    pass


@socketio.on('client_deleted')
def handle_client_deleted(data):
    """Emite cuando se elimina un cliente"""
    # No procesamos aquí, esto se llama desde las rutas
    pass


# ============================================
# EVENTOS DE USUARIOS
# ============================================

@socketio.on('user_created')
def handle_user_created(data):
    """Emite cuando se crea un nuevo usuario"""
    # No procesamos aquí, esto se llama desde las rutas
    pass


@socketio.on('user_updated')
def handle_user_updated(data):
    """Emite cuando se actualiza un usuario"""
    # No procesamos aquí, esto se llama desde las rutas
    pass


@socketio.on('user_deleted')
def handle_user_deleted(data):
    """Emite cuando se elimina un usuario"""
    # No procesamos aquí, esto se llama desde las rutas
    pass


# ============================================
# EVENTOS DE DASHBOARD
# ============================================

@socketio.on('dashboard_refresh')
def handle_dashboard_refresh(data):
    """Solicita actualización del dashboard"""
    if current_user.is_authenticated:
        emit('refresh_dashboard', {'message': 'Dashboard actualizado'}, room=f'user_{current_user.id}')


# ============================================
# FUNCIONES HELPER PARA EMITIR EVENTOS
# ============================================

def emit_operation_event(event_type, operation_data):
    """
    Emite un evento de operación a todos los usuarios relevantes

    Args:
        event_type: 'created', 'updated', 'deleted'
        operation_data: Datos de la operación
    """
    # Emitir a todos los usuarios autenticados
    socketio.emit(f'operation_{event_type}', operation_data, room='authenticated')

    # También emitir específicamente a Masters y Operadores
    socketio.emit(f'operation_{event_type}', operation_data, room='role_Master')
    socketio.emit(f'operation_{event_type}', operation_data, room='role_Operador')


def emit_client_event(event_type, client_data):
    """
    Emite un evento de cliente a todos los usuarios relevantes

    Args:
        event_type: 'created', 'updated', 'deleted'
        client_data: Datos del cliente
    """
    # Emitir a todos los usuarios autenticados
    socketio.emit(f'client_{event_type}', client_data, room='authenticated')

    # También emitir específicamente a Masters, Traders y Operadores
    socketio.emit(f'client_{event_type}', client_data, room='role_Master')
    socketio.emit(f'client_{event_type}', client_data, room='role_Trader')
    socketio.emit(f'client_{event_type}', client_data, room='role_Operador')


def emit_user_event(event_type, user_data):
    """
    Emite un evento de usuario solo a Masters

    Args:
        event_type: 'created', 'updated', 'deleted'
        user_data: Datos del usuario
    """
    # Solo emitir a Masters
    socketio.emit(f'user_{event_type}', user_data, room='role_Master')


def emit_dashboard_update():
    """Emite evento para actualizar el dashboard de todos los usuarios"""
    socketio.emit('dashboard_update', {'message': 'Actualizar dashboard'}, room='authenticated')
