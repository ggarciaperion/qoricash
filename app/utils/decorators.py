"""
Decoradores personalizados para QoriCash Trading V2
"""
from functools import wraps
from flask import flash, redirect, url_for, jsonify, request
from flask_login import current_user


def require_role(*roles):
    """
    Decorador para requerir roles específicos

    Args:
        *roles: Roles permitidos ('Master', 'Trader', 'Operador')

    Usage:
        @require_role('Master')
        @require_role('Master', 'Trader')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                if request.is_json:
                    return jsonify({'error': 'No autenticado'}), 401
                flash('Por favor inicia sesión para acceder', 'warning')
                return redirect(url_for('auth.login'))

            if current_user.role not in roles:
                if request.is_json:
                    return jsonify({'error': 'No autorizado'}), 403
                flash('No tienes permiso para acceder a esta página', 'danger')
                return redirect(url_for('dashboard.index'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator


# Alias para compatibilidad (algunos archivos usan role_required)
role_required = require_role


def api_key_required(f):
    """
    Decorador para requerir API key en requests
    
    Usage:
        @api_key_required
        def my_api_endpoint():
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        
        if not api_key:
            return jsonify({'error': 'API key requerida'}), 401
        
        # Aquí podrías validar el API key contra la base de datos
        # Por ahora, acepta cualquier key no vacía
        
        return f(*args, **kwargs)
    return decorated_function


def ajax_required(f):
    """
    Decorador para requerir que la petición sea AJAX
    
    Usage:
        @ajax_required
        def my_ajax_endpoint():
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not request.is_json and not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Se requiere petición AJAX'}), 400
        return f(*args, **kwargs)
    return decorated_function
