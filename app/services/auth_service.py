"""
Servicio de Autenticación para QoriCash Trading V2

Maneja login, logout, verificación de credenciales y sesiones.
"""
from flask_login import login_user, logout_user
from app.extensions import db
from app.models.user import User
from app.models.audit_log import AuditLog
from app.utils.formatters import now_peru


class AuthService:
    """Servicio de autenticación"""
    
    @staticmethod
    def authenticate_user(username, password, remember=False):
        """
        Autenticar usuario con credenciales

        Args:
            username: DNI del usuario
            password: Contraseña en texto plano
            remember: Si mantener sesión activa

        Returns:
            tuple: (success: bool, message: str, user: User|None)
        """
        # Buscar usuario por DNI
        user = User.query.filter(User.dni == username).first()

        # Validar que existe
        if not user:
            return False, 'DNI o contraseña incorrectos', None

        # Validar que está activo
        if user.status != 'Activo':
            return False, 'Usuario inactivo. Contacte al administrador', None

        # Validar contraseña
        if not user.check_password(password):
            return False, 'DNI o contraseña incorrectos', None

        # Login exitoso
        # IMPORTANTE: remember=False siempre para seguridad
        # La sesión se cerrará automáticamente al cerrar el navegador
        login_user(user, remember=False)

        # Actualizar last_login
        user.last_login = now_peru()

        # Registrar en auditoría
        AuditLog.log_action(
            user_id=user.id,
            action='LOGIN',
            entity='User',
            entity_id=user.id,
            details=f'Login exitoso de {user.username}'
        )

        # Commit único para last_login y audit_log juntos
        db.session.commit()

        return True, 'Login exitoso', user
    
    @staticmethod
    def logout_user_session(user):
        """
        Cerrar sesión de usuario
        
        Args:
            user: Usuario actual
        
        Returns:
            tuple: (success: bool, message: str)
        """
        if not user or not user.is_authenticated:
            return False, 'No hay sesión activa'
        
        # Actualizar last_logout
        user.last_logout = now_peru()

        # Registrar en auditoría
        AuditLog.log_action(
            user_id=user.id,
            action='LOGOUT',
            entity='User',
            entity_id=user.id,
            details=f'Logout de {user.username}'
        )

        # Commit único para last_logout y audit_log juntos
        db.session.commit()

        # Logout
        logout_user()

        return True, 'Sesión cerrada exitosamente'
    
    @staticmethod
    def verify_user_status(user):
        """
        Verificar que el usuario puede usar el sistema
        
        Args:
            user: Usuario a verificar
        
        Returns:
            tuple: (is_valid: bool, message: str)
        """
        if not user:
            return False, 'Usuario no encontrado'
        
        if user.status != 'Activo':
            return False, 'Usuario inactivo'
        
        return True, 'Usuario válido'
    
    @staticmethod
    def change_password(user, old_password, new_password):
        """
        Cambiar contraseña de usuario
        
        Args:
            user: Usuario
            old_password: Contraseña actual
            new_password: Nueva contraseña
        
        Returns:
            tuple: (success: bool, message: str)
        """
        # Validar contraseña actual
        if not user.check_password(old_password):
            return False, 'Contraseña actual incorrecta'
        
        # Validar nueva contraseña
        if len(new_password) < 8:
            return False, 'La nueva contraseña debe tener al menos 8 caracteres'
        
        if not any(c.isdigit() for c in new_password):
            return False, 'La nueva contraseña debe contener al menos un número'
        
        # Cambiar contraseña
        user.set_password(new_password)

        # Registrar en auditoría
        AuditLog.log_action(
            user_id=user.id,
            action='CHANGE_PASSWORD',
            entity='User',
            entity_id=user.id,
            details='Contraseña cambiada exitosamente'
        )

        # Commit único para password y audit_log juntos
        db.session.commit()

        return True, 'Contraseña actualizada exitosamente'
    
    @staticmethod
    def reset_user_password(admin_user, target_user, new_password):
        """
        Restablecer contraseña de otro usuario (solo Master)
        
        Args:
            admin_user: Usuario administrador
            target_user: Usuario objetivo
            new_password: Nueva contraseña
        
        Returns:
            tuple: (success: bool, message: str)
        """
        # Validar que el admin es Master
        if not admin_user or admin_user.role != 'Master':
            return False, 'Solo el Master puede restablecer contraseñas'
        
        # Validar nueva contraseña
        if len(new_password) < 8:
            return False, 'La contraseña debe tener al menos 8 caracteres'
        
        if not any(c.isdigit() for c in new_password):
            return False, 'La contraseña debe contener al menos un número'
        
        # Cambiar contraseña
        target_user.set_password(new_password)

        # Registrar en auditoría
        AuditLog.log_action(
            user_id=admin_user.id,
            action='RESET_PASSWORD',
            entity='User',
            entity_id=target_user.id,
            details=f'Contraseña restablecida para {target_user.username}'
        )

        # Commit único para password y audit_log juntos
        db.session.commit()

        return True, f'Contraseña de {target_user.username} restablecida exitosamente'
