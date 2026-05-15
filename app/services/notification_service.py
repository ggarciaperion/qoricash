"""
Servicio de Notificaciones — QoriCash
Centraliza WebSocket (tiempo real) + DB (historial) + badge counter.

REGLAS DE ROOMS (socketio_events.py):
  - Por rol:  f'role_{role}'   → "role_Master", "role_Operador", etc.
  - Por user: f'user_{user_id}'
  - Global:   'authenticated'
"""
import logging
from app.extensions import socketio, db

logger = logging.getLogger(__name__)

# ─── Utilidades internas ───────────────────────────────────────────────────────

def _emit_to_role(event, data, role):
    """Emite a todos los usuarios de un rol. Room correcto: role_{role}."""
    try:
        socketio.emit(event, data, namespace='/', room=f'role_{role}')
    except Exception as e:
        logger.error(f'[NOTIF] emit_to_role({role}) error: {e}')


def _emit_to_user(event, data, user_id):
    try:
        socketio.emit(event, data, namespace='/', room=f'user_{user_id}')
    except Exception as e:
        logger.error(f'[NOTIF] emit_to_user({user_id}) error: {e}')


def _emit_to_roles(event, data, roles):
    for role in roles:
        _emit_to_role(event, data, role)


def _save_to_db(roles, title, message, notif_type='info', category='general', link=None):
    try:
        from app.models.notification import Notification
        Notification.create_for_roles(roles, title, message, notif_type, category, link)
        db.session.commit()
    except Exception as e:
        logger.error(f'[NOTIF] save_to_db error: {e}')
        db.session.rollback()


def _save_to_db_user(user_id, title, message, notif_type='info', category='general', link=None):
    try:
        from app.models.notification import Notification
        Notification.create_for_user(user_id, title, message, notif_type, category, link)
        db.session.commit()
    except Exception as e:
        logger.error(f'[NOTIF] save_to_db_user error: {e}')
        db.session.rollback()


def _push_unread_count(user_id):
    try:
        from app.models.notification import Notification
        count = Notification.query.filter_by(user_id=user_id, is_read=False).count()
        _emit_to_user('notification_badge', {'count': count}, user_id)
    except Exception as e:
        logger.error(f'[NOTIF] push_unread_count error: {e}')


def _emit_to_client_operation(operation, old_status=None):
    """Emite actualización de operación al room del cliente web (client_{dni})."""
    try:
        if not operation.client or not operation.client.dni:
            return
        # Mapear status de Flask a formato frontend
        status_map = {
            'Pendiente':  'pendiente',
            'En proceso': 'en_proceso',
            'Completada': 'completado',
            'Cancelada':  'cancelado',
            'Rechazada':  'rechazado',
        }
        client_data = {
            'event':        'operacion_cliente_actualizada',
            'id':           operation.id,
            'operation_id': operation.operation_id,
            'status':       operation.status,
            'status_key':   status_map.get(operation.status, 'pendiente'),
            'old_status':   old_status,
            'amount_usd':   float(operation.amount_usd or 0),
            'amount_pen':   float(operation.amount_pen or 0),
            'exchange_rate': float(operation.exchange_rate or 0),
            'updated_at':   operation.updated_at.isoformat() if operation.updated_at else None,
        }
        socketio.emit('operacion_cliente_actualizada', client_data,
                      namespace='/', room=f'client_{operation.client.dni}')
        logger.info(f'[NOTIF] operacion_cliente_actualizada → client_{operation.client.dni}: {operation.operation_id} → {operation.status}')
    except Exception as e:
        logger.error(f'[NOTIF] _emit_to_client_operation error: {e}')


def _push_unread_counts_for_roles(roles):
    try:
        from app.models.user import User
        from app.models.notification import Notification
        users = User.query.filter(User.role.in_(roles), User.status == 'Activo').all()
        for u in users:
            count = Notification.query.filter_by(user_id=u.id, is_read=False).count()
            _emit_to_user('notification_badge', {'count': count}, u.id)
    except Exception as e:
        logger.error(f'[NOTIF] push_unread_counts_for_roles error: {e}')


# ─── Clase pública (mantiene compatibilidad con imports existentes) ─────────────

class NotificationService:

    # ── Operaciones ──────────────────────────────────────────────────────────

    @staticmethod
    def notify_new_operation(operation):
        """Trader/Web crea operación → Master y Operador."""
        try:
            name = operation.client.full_name if operation.client else 'N/A'
            data = {
                'event': 'nueva_operacion',
                'operation_id':   operation.operation_id,
                'client_name':    name,
                'operation_type': operation.operation_type,
                'amount_usd':     float(operation.amount_usd or 0),
                'status':         operation.status,
                'created_by':     operation.user.username if operation.user else 'N/A',
                'title':          '📋 Nueva Operación',
                'message':        f'{operation.operation_id} — {name}',
                'type':           'info',
                'sound':          True,
            }
            roles = ['Master', 'Operador']
            _emit_to_roles('nueva_operacion', data, roles)
            _save_to_db(roles, '📋 Nueva Operación',
                        f'{operation.operation_id} — {name} ({operation.operation_type})',
                        notif_type='info', category='operation',
                        link=f'/operations/{operation.id}')
            _push_unread_counts_for_roles(roles)
        except Exception as e:
            logger.error(f'[NOTIF] notify_new_operation error: {e}')

    # Alias para platform_api.py que llama emit_operation_created
    @staticmethod
    def emit_operation_created(operation):
        NotificationService.notify_new_operation(operation)
    
    @staticmethod
    def notify_operation_updated(operation, old_status=None):
        """Operación actualizada → Master, Operador y cliente web."""
        try:
            msg = f'{operation.operation_id} → {operation.status}'
            if operation.assigned_operator:
                msg += f' | {operation.assigned_operator.username}'
            data = {
                'event':                  'operacion_actualizada',
                'id':                     operation.id,
                'operation_id':           operation.operation_id,
                'client_id':              operation.client_id,
                'client_name':            operation.client.full_name if operation.client else 'N/A',
                'client_dni':             operation.client.dni if operation.client else None,
                'status':                 operation.status,
                'old_status':             old_status,
                'operation_type':         operation.operation_type,
                'amount_usd':             float(operation.amount_usd or 0),
                'amount_pen':             float(operation.amount_pen or 0),
                'exchange_rate':          float(operation.exchange_rate or 0),
                'assigned_operator_id':   operation.assigned_operator_id,
                'assigned_operator_name': operation.assigned_operator.username if operation.assigned_operator else None,
                'client_deposits':        operation.client_deposits or [],
                'client_payments':        operation.client_payments or [],
                'total_deposits':         operation.total_deposits,
                'total_payments':         operation.total_payments,
                'created_at':             operation.created_at.isoformat() if operation.created_at else None,
                'updated_at':             operation.updated_at.isoformat() if operation.updated_at else None,
                'title':                  '🔄 Operación Actualizada',
                'message':                msg,
                'type':                   'info',
                'sound':                  False,
            }
            _emit_to_roles('operacion_actualizada', data, ['Master', 'Operador'])

            # Notificar al cliente web en tiempo real
            if operation.client and operation.client.dni:
                _emit_to_client_operation(operation, old_status)

            logger.info(f'[NOTIF] operacion_actualizada: {operation.operation_id}')
        except Exception as e:
            logger.error(f'[NOTIF] notify_operation_updated error: {e}')
    
    @staticmethod
    def notify_operation_completed(operation):
        try:
            title = '✅ Operación Completada'
            name  = operation.client.full_name if operation.client else 'N/A'
            msg   = f'{operation.operation_id} — {name}'
            data  = {
                'event': 'operacion_completada', 'operation_id': operation.operation_id,
                'client_name': name, 'amount_usd': float(operation.amount_usd or 0),
                'amount_pen': float(operation.amount_pen or 0),
                'title': title, 'message': msg, 'type': 'success', 'sound': True, 'sound_file': 'completada',
            }
            roles = ['Master', 'Operador']
            _emit_to_roles('operacion_completada', data, roles)
            _save_to_db(roles, title, msg, notif_type='success', category='operation',
                        link=f'/operations/{operation.id}')
            _push_unread_counts_for_roles(roles)
            # Notificar al cliente web
            _emit_to_client_operation(operation, 'En proceso')
        except Exception as e:
            logger.error(f'[NOTIF] notify_operation_completed error: {e}')

    @staticmethod
    def notify_operation_in_process(operation):
        """Trader/Web sube comprobante → operación pasa a En proceso → Master, Operador y cliente web."""
        try:
            title = '⏳ Operación En Proceso'
            name  = operation.client.full_name if operation.client else 'N/A'
            msg   = f'{operation.operation_id} — {name} subió comprobante'
            data  = {
                'event': 'operacion_en_proceso',
                'operation_id':   operation.operation_id,
                'operation_db_id': operation.id,
                'client_name':    name,
                'status':         'En proceso',
                'title':          title,
                'message':        msg,
                'type':           'warning',
                'sound':          True,
            }
            roles = ['Master', 'Operador']
            _emit_to_roles('operacion_en_proceso', data, roles)
            _save_to_db(roles, title, msg, notif_type='warning', category='operation',
                        link=f'/operations/{operation.id}')
            _push_unread_counts_for_roles(roles)
            # Notificar al cliente web
            _emit_to_client_operation(operation, 'Pendiente')
        except Exception as e:
            logger.error(f'[NOTIF] notify_operation_in_process error: {e}')

    @staticmethod
    def notify_operation_canceled(operation, reason=None):
        try:
            title = '❌ Operación Cancelada'
            msg   = f'{operation.operation_id} — {reason or "sin razón"}'
            data  = {
                'event': 'operacion_cancelada', 'operation_id': operation.operation_id,
                'client_name': operation.client.full_name if operation.client else 'N/A',
                'reason': reason, 'title': title, 'message': msg, 'type': 'warning', 'sound': True,
            }
            roles = ['Master', 'Operador']
            _emit_to_roles('operacion_cancelada', data, roles)
            _save_to_db(roles, title, msg, notif_type='warning', category='operation',
                        link=f'/operations/{operation.id}')
            _push_unread_counts_for_roles(roles)
            # Notificar al cliente web
            _emit_to_client_operation(operation, None)
        except Exception as e:
            logger.error(f'[NOTIF] notify_operation_canceled error: {e}')

    @staticmethod
    def notify_to_role(role, message_type, data):
        """Emite a un rol. Room correcto: role_{role}."""
        try:
            data['target_role'] = role
            _emit_to_role(message_type, data, role)
        except Exception as e:
            logger.error(f'[NOTIF] notify_to_role({role}) error: {e}')

    @staticmethod
    def notify_to_user(user_id, message_type, data):
        try:
            _emit_to_user(message_type, data, user_id)
        except Exception as e:
            logger.error(f'[NOTIF] notify_to_user({user_id}) error: {e}')

    @staticmethod
    def broadcast_notification(title, message, notification_type='info'):
        try:
            socketio.emit('notification', {'title': title, 'message': message, 'type': notification_type},
                          namespace='/', room='authenticated')
        except Exception as e:
            logger.error(f'[NOTIF] broadcast_notification error: {e}')

    @staticmethod
    def notify_new_client(client, created_by_user=None):
        """Nuevo cliente → Master, Operador, Middle Office."""
        try:
            created_by = created_by_user or getattr(client, '_created_by', None)
            name  = client.full_name or getattr(client, 'razon_social', None) or client.dni
            canal = created_by.username if created_by else 'N/A'
            title = '👤 Nuevo Cliente'
            msg   = f'{name} ({client.dni}) — por {canal}'
            data  = {
                'event': 'nuevo_cliente', 'client_id': client.id, 'client_name': name,
                'client_dni': client.dni, 'created_by': canal,
                'title': title, 'message': msg, 'type': 'info', 'sound': True,
            }
            roles = ['Master', 'Operador', 'Middle Office']
            _emit_to_roles('nuevo_cliente', data, roles)
            _emit_to_roles('client_created', data, roles)
            _save_to_db(roles, title, msg, notif_type='info', category='client',
                        link=f'/clients/{client.id}')
            _push_unread_counts_for_roles(roles)
        except Exception as e:
            logger.error(f'[NOTIF] notify_new_client error: {e}')

    # Alias para platform_api.py
    @staticmethod
    def emit_client_created(client_data):
        try:
            data = client_data if isinstance(client_data, dict) else {}
            data.update({'event': 'client_created', 'sound': True, 'type': 'info'})
            _emit_to_roles('client_created', data, ['Master', 'Operador', 'Middle Office'])
        except Exception as e:
            logger.error(f'[NOTIF] emit_client_created error: {e}')

    @staticmethod
    def notify_new_user(user, created_by):
        """Nuevo usuario → solo Masters."""
        try:
            title = '🧑‍💼 Nuevo Usuario'
            msg   = f'{user.username} ({user.role}) — por {created_by.username if created_by else "N/A"}'
            data  = {
                'event': 'nuevo_usuario', 'username': user.username, 'role': user.role,
                'created_by': created_by.username if created_by else 'N/A',
                'title': title, 'message': msg, 'type': 'info', 'sound': False,
            }
            _emit_to_role('nuevo_usuario', data, 'Master')
            _save_to_db(['Master'], title, msg, notif_type='info', category='user',
                        link=f'/users/{user.id}')
            _push_unread_counts_for_roles(['Master'])
        except Exception as e:
            logger.error(f'[NOTIF] notify_new_user error: {e}')

    @staticmethod
    def notify_dashboard_update():
        try:
            socketio.emit('dashboard_update', {}, namespace='/', room='authenticated')
        except Exception as e:
            logger.error(f'[NOTIF] notify_dashboard_update error: {e}')

    @staticmethod
    def notify_position_update():
        try:
            socketio.emit('position_update', {}, namespace='/', room='authenticated')
        except Exception as e:
            logger.error(f'[NOTIF] notify_position_update error: {e}')

    @staticmethod
    def notify_operation_assigned(operation, operator_user):
        try:
            title = '📌 Operación Asignada'
            msg   = f'Se te asignó la operación {operation.operation_id}'
            data  = {
                'event': 'operacion_asignada', 'operation_id': operation.operation_id,
                'operation_db_id': operation.id,
                'client_name': operation.client.full_name if operation.client else 'N/A',
                'operation_type': operation.operation_type,
                'amount_usd': float(operation.amount_usd or 0), 'status': operation.status,
                'title': title, 'message': msg, 'type': 'info', 'sound': True,
            }
            _emit_to_user('operacion_asignada', data, operator_user.id)
            _save_to_db_user(operator_user.id, title, msg, notif_type='info', category='operation',
                             link=f'/operations/{operation.id}')
            _push_unread_count(operator_user.id)
        except Exception as e:
            logger.error(f'[NOTIF] notify_operation_assigned error: {e}')

    @staticmethod
    def notify_operation_reassigned(operation, old_operator, new_operator, reassigned_by):
        try:
            title_new = '📌 Operación Reasignada'
            msg_new   = f'Se te reasignó la operación {operation.operation_id}'
            data_new  = {
                'event': 'operacion_asignada', 'operation_id': operation.operation_id,
                'operation_db_id': operation.id,
                'client_name': operation.client.full_name if operation.client else 'N/A',
                'operation_type': operation.operation_type,
                'amount_usd': float(operation.amount_usd or 0), 'status': operation.status,
                'reassigned_by': reassigned_by.username,
                'title': title_new, 'message': msg_new, 'type': 'info', 'sound': True,
            }
            _emit_to_user('operacion_asignada', data_new, new_operator.id)
            _save_to_db_user(new_operator.id, title_new, msg_new, notif_type='info',
                             category='operation', link=f'/operations/{operation.id}')
            _push_unread_count(new_operator.id)

            if old_operator:
                title_old = '🔁 Operación Removida'
                msg_old   = f'La op. {operation.operation_id} fue reasignada a {new_operator.username}'
                data_old  = {**data_new,
                             'event': 'operacion_reasignada_removida',
                             'title': title_old, 'message': msg_old, 'sound': False}
                _emit_to_user('operacion_reasignada_removida', data_old, old_operator.id)
                _save_to_db_user(old_operator.id, title_old, msg_old, notif_type='warning',
                                 category='operation', link=f'/operations/{operation.id}')
                _push_unread_count(old_operator.id)
        except Exception as e:
            logger.error(f'[NOTIF] notify_operation_reassigned error: {e}')

    @staticmethod
    def notify_client_reassignment(client, reassigned_by_user, new_trader_id):
        try:
            from app.models.user import User
            new_trader = db.session.get(User, new_trader_id)
            if not new_trader:
                return
            old_trader = client.creator if hasattr(client, 'creator') else None
            name = client.full_name or getattr(client, 'razon_social', None) or client.dni
            title_new = '👤 Cliente Asignado'
            msg_new   = f'Se te asignó el cliente {name}'
            data_new  = {
                'event': 'cliente_asignado', 'client_id': client.id,
                'client_name': name, 'client_dni': client.dni,
                'title': title_new, 'message': msg_new, 'type': 'info', 'sound': True,
            }
            _emit_to_user('cliente_asignado', data_new, new_trader.id)
            _save_to_db_user(new_trader.id, title_new, msg_new, notif_type='info',
                             category='client', link=f'/clients/{client.id}')
            _push_unread_count(new_trader.id)

            if old_trader:
                title_old = '🔁 Cliente Reasignado'
                msg_old   = f'{name} fue reasignado a {new_trader.username}'
                data_old  = {**data_new,
                             'event': 'cliente_reasignado_removido',
                             'title': title_old, 'message': msg_old, 'sound': False}
                _emit_to_user('cliente_reasignado_removido', data_old, old_trader.id)
                _save_to_db_user(old_trader.id, title_old, msg_old, notif_type='warning',
                                 category='client', link=f'/clients/{client.id}')
                _push_unread_count(old_trader.id)
        except Exception as e:
            logger.error(f'[NOTIF] notify_client_reassignment error: {e}')

    @staticmethod
    def notify_bulk_client_reassignment(new_trader, reassigned_by_user, client_count):
        try:
            title = '👥 Clientes Asignados'
            msg   = f'Se te asignaron {client_count} cliente(s)'
            data  = {
                'event': 'clientes_asignados_masivo', 'client_count': client_count,
                'new_trader_name': new_trader.username, 'title': title,
                'message': msg, 'type': 'info', 'sound': True,
            }
            _emit_to_user('clientes_asignados_masivo', data, new_trader.id)
            _save_to_db_user(new_trader.id, title, msg, notif_type='info', category='client')
            _push_unread_count(new_trader.id)
        except Exception as e:
            logger.error(f'[NOTIF] notify_bulk_client_reassignment error: {e}')

    @staticmethod
    def notify_client_documents_approved(client):
        try:
            data = {
                'event': 'documents_approved', 'type': 'documents_approved',
                'title': '✅ Cuenta Activada',
                'message': '¡Tus documentos fueron aprobados! Ya puedes operar.',
                'client_dni': client.dni, 'client_id': client.id,
                'client_name': client.full_name or getattr(client, 'razon_social', ''),
            }
            socketio.emit('documents_approved', data, namespace='/', room=f'client_{client.dni}')
            logger.info(f'[NOTIF] documents_approved → client_{client.dni}')
        except Exception as e:
            logger.error(f'[NOTIF] notify_client_documents_approved error: {e}')

    @staticmethod
    def notify_operation_expired(operation):
        try:
            if not operation.client:
                return
            data = {
                'event': 'operation_expired', 'type': 'operation_expired',
                'operation_id': operation.operation_id,
                'title': '⏱️ Operación Expirada',
                'message': f'La operación {operation.operation_id} expiró. Puedes crear una nueva.',
                'client_dni': operation.client.dni, 'client_id': operation.client_id,
            }
            socketio.emit('operation_expired', data, namespace='/', room=f'client_{operation.client.dni}')
        except Exception as e:
            logger.error(f'[NOTIF] notify_operation_expired error: {e}')
