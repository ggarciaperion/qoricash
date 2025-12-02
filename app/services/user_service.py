"""
Servicio de Usuarios para QoriCash Trading V2

Maneja CRUD de usuarios, cambios de rol, activación/desactivación.
"""
from app.extensions import db
from app.models.user import User
from app.models.audit_log import AuditLog
from app.utils.validators import validate_dni, validate_email, validate_password
from app.utils.formatters import now_peru


class UserService:
    """Servicio de gestión de usuarios"""
    
    @staticmethod
    def get_all_users():
        """
        Obtener todos los usuarios
        
        Returns:
            list: Lista de usuarios
        """
        return User.query.order_by(User.created_at.desc()).all()
    
    @staticmethod
    def get_user_by_id(user_id):
        """
        Obtener usuario por ID
        
        Args:
            user_id: ID del usuario
        
        Returns:
            User: Usuario o None
        """
        return User.query.get(user_id)
    
    @staticmethod
    def get_active_users():
        """
        Obtener solo usuarios activos
        
        Returns:
            list: Lista de usuarios activos
        """
        return User.query.filter_by(status='Activo').order_by(User.username).all()
    
    @staticmethod
    def get_users_by_role(role):
        """
        Obtener usuarios por rol

        Args:
            role: Rol a filtrar ('Master', 'Trader', 'Operador', 'Middle Office')

        Returns:
            list: Lista de usuarios con ese rol
        """
        return User.query.filter_by(role=role).order_by(User.username).all()
    
    @staticmethod
    def create_user(current_user, username, email, password, dni, role='Trader'):
        """
        Crear nuevo usuario

        Args:
            current_user: Usuario que crea (debe ser Master)
            username: Nombre de usuario
            email: Email
            password: Contraseña
            dni: DNI
            role: Rol ('Master', 'Trader', 'Operador', 'Middle Office')

        Returns:
            tuple: (success: bool, message: str, user: User|None)
        """
        # Validar que solo Master puede crear usuarios
        if not current_user or current_user.role != 'Master':
            return False, 'Solo el Master puede crear usuarios', None
        
        # Validar datos
        is_valid, error = validate_email(email)
        if not is_valid:
            return False, error, None
        
        is_valid, error = validate_dni(dni)
        if not is_valid:
            return False, error, None
        
        is_valid, error = validate_password(password)
        if not is_valid:
            return False, error, None
        
        # Validar rol
        if role not in ['Master', 'Trader', 'Operador', 'Middle Office']:
            return False, 'Rol inválido', None
        
        # Validar que username no existe
        if User.query.filter_by(username=username).first():
            return False, 'El nombre de usuario ya existe', None
        
        # Validar que email no existe
        if User.query.filter_by(email=email).first():
            return False, 'El email ya está registrado', None
        
        # Validar que DNI no existe
        if User.query.filter_by(dni=dni).first():
            return False, 'El DNI ya está registrado', None
        
        # Crear usuario
        user = User(
            username=username,
            email=email,
            dni=dni,
            role=role,
            status='Activo',
            created_at=now_peru()
        )
        user.set_password(password)

        db.session.add(user)
        db.session.flush()  # Flush para obtener el ID del nuevo usuario

        # Registrar en auditoría
        AuditLog.log_action(
            user_id=current_user.id,
            action='CREATE_USER',
            entity='User',
            entity_id=user.id,
            details=f'Usuario {username} creado con rol {role}'
        )

        # Commit único para user y audit_log juntos
        db.session.commit()

        return True, 'Usuario creado exitosamente', user
    
    @staticmethod
    def update_user(current_user, user_id, email=None, dni=None, role=None, status=None):
        """
        Actualizar usuario
        
        Args:
            current_user: Usuario que actualiza (debe ser Master)
            user_id: ID del usuario a actualizar
            email: Nuevo email (opcional)
            dni: Nuevo DNI (opcional)
            role: Nuevo rol (opcional)
            status: Nuevo estado (opcional)
        
        Returns:
            tuple: (success: bool, message: str, user: User|None)
        """
        # Validar que solo Master puede actualizar usuarios
        if not current_user or current_user.role != 'Master':
            return False, 'Solo el Master puede actualizar usuarios', None
        
        # Obtener usuario
        user = User.query.get(user_id)
        if not user:
            return False, 'Usuario no encontrado', None
        
        # Validar y actualizar email
        if email and email != user.email:
            is_valid, error = validate_email(email)
            if not is_valid:
                return False, error, None
            
            # Verificar que no existe
            if User.query.filter_by(email=email).first():
                return False, 'El email ya está registrado', None
            
            user.email = email
        
        # Validar y actualizar DNI
        if dni and dni != user.dni:
            is_valid, error = validate_dni(dni)
            if not is_valid:
                return False, error, None
            
            # Verificar que no existe
            if User.query.filter_by(dni=dni).first():
                return False, 'El DNI ya está registrado', None
            
            user.dni = dni
        
        # Actualizar rol
        if role and role != user.role:
            if role not in ['Master', 'Trader', 'Operador', 'Middle Office']:
                return False, 'Rol inválido', None
            user.role = role
        
        # Actualizar estado
        if status and status != user.status:
            if status not in ['Activo', 'Inactivo']:
                return False, 'Estado inválido', None
            user.status = status
        
        user.updated_at = now_peru()

        # Registrar en auditoría
        AuditLog.log_action(
            user_id=current_user.id,
            action='UPDATE_USER',
            entity='User',
            entity_id=user.id,
            details=f'Usuario {user.username} actualizado'
        )

        # Commit único para user y audit_log juntos
        db.session.commit()

        return True, 'Usuario actualizado exitosamente', user
    
    @staticmethod
    def toggle_user_status(current_user, user_id):
        """
        Activar/Desactivar usuario
        
        Args:
            current_user: Usuario que realiza la acción (debe ser Master)
            user_id: ID del usuario
        
        Returns:
            tuple: (success: bool, message: str, user: User|None)
        """
        # Validar que solo Master puede cambiar estado
        if not current_user or current_user.role != 'Master':
            return False, 'Solo el Master puede cambiar el estado de usuarios', None
        
        # Obtener usuario
        user = User.query.get(user_id)
        if not user:
            return False, 'Usuario no encontrado', None
        
        # No permitir desactivar al propio usuario
        if user.id == current_user.id:
            return False, 'No puedes desactivar tu propio usuario', None
        
        # Cambiar estado
        new_status = 'Inactivo' if user.status == 'Activo' else 'Activo'
        user.status = new_status
        user.updated_at = now_peru()

        # Registrar en auditoría
        AuditLog.log_action(
            user_id=current_user.id,
            action='TOGGLE_USER_STATUS',
            entity='User',
            entity_id=user.id,
            details=f'Usuario {user.username} {new_status.lower()}'
        )

        # Commit único para user y audit_log juntos
        db.session.commit()

        return True, f'Usuario {new_status.lower()} exitosamente', user
    
    @staticmethod
    def delete_user(current_user, user_id):
        """
        Eliminar usuario (soft delete - cambiar a Inactivo)
        
        Args:
            current_user: Usuario que elimina (debe ser Master)
            user_id: ID del usuario
        
        Returns:
            tuple: (success: bool, message: str)
        """
        # Validar que solo Master puede eliminar
        if not current_user or current_user.role != 'Master':
            return False, 'Solo el Master puede eliminar usuarios'
        
        # Obtener usuario
        user = User.query.get(user_id)
        if not user:
            return False, 'Usuario no encontrado'
        
        # No permitir eliminar al propio usuario
        if user.id == current_user.id:
            return False, 'No puedes eliminar tu propio usuario'
        
        # Soft delete (marcar como inactivo)
        user.status = 'Inactivo'
        user.updated_at = now_peru()

        # Registrar en auditoría
        AuditLog.log_action(
            user_id=current_user.id,
            action='DELETE_USER',
            entity='User',
            entity_id=user.id,
            details=f'Usuario {user.username} eliminado (soft delete)'
        )

        # Commit único para user y audit_log juntos
        db.session.commit()

        return True, 'Usuario eliminado exitosamente'
    
    @staticmethod
    def get_user_stats(user_id):
        """
        Obtener estadísticas de un usuario
        
        Args:
            user_id: ID del usuario
        
        Returns:
            dict: Estadísticas del usuario
        """
        user = User.query.get(user_id)
        if not user:
            return None
        
        return {
            'total_operations': user.operations.count(),
            'completed_operations': user.operations.filter_by(status='Completada').count(),
            'pending_operations': user.operations.filter_by(status='Pendiente').count(),
            'in_process_operations': user.operations.filter_by(status='En proceso').count(),
            'canceled_operations': user.operations.filter_by(status='Cancelado').count()
        }
