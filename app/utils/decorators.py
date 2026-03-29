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
                También acepta una lista de roles como primer argumento

    Usage:
        @require_role('Master')
        @require_role('Master', 'Trader')
        @require_role(['Master', 'Middle Office'])
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                # Detectar si es una petición JSON o AJAX
                if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'error': 'No autenticado'}), 401
                flash('Por favor inicia sesión para acceder', 'warning')
                return redirect(url_for('auth.login'))

            # Normalizar roles (aceptar lista o argumentos múltiples)
            allowed_roles = roles[0] if len(roles) == 1 and isinstance(roles[0], list) else roles

            if current_user.role not in allowed_roles:
                # Detectar si es una petición JSON o AJAX
                if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
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
    Decorador para requerir API key en requests.
    Valida contra la variable de entorno INTERNAL_API_KEY.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        import os, logging
        api_key = request.headers.get('X-API-Key')

        if not api_key:
            return jsonify({'error': 'API key requerida'}), 401

        expected = os.environ.get('INTERNAL_API_KEY', '')
        if not expected:
            logging.warning('[Security] INTERNAL_API_KEY no configurada — endpoint protegido rechazando acceso')
            return jsonify({'error': 'Configuración de seguridad no disponible'}), 503

        if api_key != expected:
            logging.warning(f'[Security] API key inválida desde {request.remote_addr}')
            return jsonify({'error': 'API key inválida'}), 403

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
