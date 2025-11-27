"""
Rutas de Autenticación para QoriCash Trading V2
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user, logout_user
from app.services.auth_service import AuthService
from app.extensions import limiter

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/')
def index():
    """
    Ruta raíz - Redirige al login o dashboard
    """
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    return redirect(url_for('auth.login'))


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    """
    Página de login
    
    GET: Mostrar formulario
    POST: Procesar login
    """
    # Si ya está autenticado, redirigir al dashboard
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False) == 'on'
        
        # Validar campos
        if not username or not password:
            flash('Por favor completa todos los campos', 'warning')
            return render_template('auth/login.html')
        
        # Autenticar
        success, message, user = AuthService.authenticate_user(username, password, remember)
        
        if success:
            flash(f'Bienvenido {user.username}!', 'success')
            
            # Redirigir según rol
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            else:
                return redirect(url_for('dashboard.index'))
        else:
            flash(message, 'danger')
            return render_template('auth/login.html')
    
    # GET: Mostrar formulario
    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """Cerrar sesión"""
    AuthService.logout_user_session(current_user)
    flash('Sesión cerrada exitosamente', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/change_password', methods=['POST'])
@login_required
def change_password():
    """
    Cambiar contraseña del usuario actual
    
    POST JSON:
        old_password: Contraseña actual
        new_password: Nueva contraseña
    """
    data = request.get_json()
    
    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')
    
    if not old_password or not new_password:
        return jsonify({'success': False, 'message': 'Todos los campos son requeridos'}), 400
    
    # Cambiar contraseña
    success, message = AuthService.change_password(current_user, old_password, new_password)
    
    if success:
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'success': False, 'message': message}), 400


@auth_bp.route('/reset_password/<int:user_id>', methods=['POST'])
@login_required
def reset_user_password(user_id):
    """
    Restablecer contraseña de otro usuario (solo Master)
    
    POST JSON:
        new_password: Nueva contraseña
    """
    from app.models.user import User
    
    data = request.get_json()
    new_password = data.get('new_password', '')
    
    if not new_password:
        return jsonify({'success': False, 'message': 'La contraseña es requerida'}), 400
    
    # Obtener usuario objetivo
    target_user = User.query.get(user_id)
    if not target_user:
        return jsonify({'success': False, 'message': 'Usuario no encontrado'}), 404
    
    # Restablecer contraseña
    success, message = AuthService.reset_user_password(current_user, target_user, new_password)
    
    if success:
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'success': False, 'message': message}), 403
