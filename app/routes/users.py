"""
Rutas de Usuarios para QoriCash Trading V2
"""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app.services.user_service import UserService
from app.services.notification_service import NotificationService
from app.utils.decorators import require_role

users_bp = Blueprint('users', __name__)


@users_bp.route('/')
@users_bp.route('/manage')
@login_required
@require_role('Master')
def manage():
    """
    Página de gestión de usuarios (solo Master)
    """
    users = UserService.get_all_users()
    return render_template('users/manage.html', user=current_user, users=users)


@users_bp.route('/api/list')
@login_required
@require_role('Master')
def list_users():
    """
    API: Listar todos los usuarios
    """
    users = UserService.get_all_users()
    return jsonify({
        'success': True,
        'users': [user.to_dict() for user in users]
    })


@users_bp.route('/api/create', methods=['POST'])
@login_required
@require_role('Master')
def create_user():
    """
    API: Crear nuevo usuario

    POST JSON:
        username: string (required)
        email: string (required)
        password: string (required)
        dni: string (required)
        role: string (required) - 'Master', 'Trader', 'Operador', 'Middle Office'
    """
    data = request.get_json()
    
    # Extraer datos
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    dni = data.get('dni', '').strip()
    role = data.get('role', 'Trader')
    
    # Validar campos requeridos
    if not all([username, email, password, dni, role]):
        return jsonify({
            'success': False,
            'message': 'Todos los campos son requeridos'
        }), 400
    
    # Crear usuario
    success, message, user = UserService.create_user(
        current_user=current_user,
        username=username,
        email=email,
        password=password,
        dni=dni,
        role=role
    )
    
    if success:
        # Notificar creación
        NotificationService.notify_new_user(user, current_user)
        
        return jsonify({
            'success': True,
            'message': message,
            'user': user.to_dict()
        }), 201
    else:
        return jsonify({
            'success': False,
            'message': message
        }), 400


@users_bp.route('/api/update/<int:user_id>', methods=['PUT'])
@login_required
@require_role('Master')
def update_user(user_id):
    """
    API: Actualizar usuario
    
    PUT JSON:
        email: string (optional)
        dni: string (optional)
        role: string (optional)
        status: string (optional)
    """
    data = request.get_json()
    
    # Actualizar usuario
    success, message, user = UserService.update_user(
        current_user=current_user,
        user_id=user_id,
        email=data.get('email'),
        dni=data.get('dni'),
        role=data.get('role'),
        status=data.get('status')
    )
    
    if success:
        return jsonify({
            'success': True,
            'message': message,
            'user': user.to_dict()
        })
    else:
        return jsonify({
            'success': False,
            'message': message
        }), 400


@users_bp.route('/api/toggle_status/<int:user_id>', methods=['POST'])
@login_required
@require_role('Master')
def toggle_status(user_id):
    """
    API: Activar/Desactivar usuario
    """
    success, message, user = UserService.toggle_user_status(current_user, user_id)
    
    if success:
        return jsonify({
            'success': True,
            'message': message,
            'user': user.to_dict()
        })
    else:
        return jsonify({
            'success': False,
            'message': message
        }), 400


@users_bp.route('/api/delete/<int:user_id>', methods=['DELETE'])
@login_required
@require_role('Master')
def delete_user(user_id):
    """
    API: Eliminar usuario (soft delete)
    """
    success, message = UserService.delete_user(current_user, user_id)
    
    if success:
        return jsonify({
            'success': True,
            'message': message
        })
    else:
        return jsonify({
            'success': False,
            'message': message
        }), 400


@users_bp.route('/api/<int:user_id>')
@login_required
@require_role('Master')
def get_user(user_id):
    """
    API: Obtener detalles de un usuario
    """
    user = UserService.get_user_by_id(user_id)
    
    if not user:
        return jsonify({
            'success': False,
            'message': 'Usuario no encontrado'
        }), 404
    
    # Incluir estadísticas
    stats = UserService.get_user_stats(user_id)
    
    return jsonify({
        'success': True,
        'user': user.to_dict(include_relations=True),
        'stats': stats
    })


@users_bp.route('/api/by_role/<role>')
@login_required
def get_users_by_role(role):
    """
    API: Obtener usuarios por rol
    """
    users = UserService.get_users_by_role(role)
    return jsonify({
        'success': True,
        'users': [user.to_dict() for user in users]
    })


@users_bp.route('/api/active')
@login_required
def get_active_users():
    """
    API: Obtener solo usuarios activos
    """
    users = UserService.get_active_users()
    return jsonify({
        'success': True,
        'users': [user.to_dict() for user in users]
    })
