"""
Rutas de API para Plataforma Móvil (QoriCashApp)

Endpoint de registro de clientes desde app móvil
"""
from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash
from app.extensions import db, csrf
from app.models.client import Client
from app.models.user import User
from app.utils.validators import validate_email
from app.utils.formatters import now_peru
import logging

logger = logging.getLogger(__name__)

# Blueprint sin prefijo (se registrará con /api/client)
platform_bp = Blueprint('platform', __name__)

# Deshabilitar CSRF para endpoints de API móvil
csrf.exempt(platform_bp)


@platform_bp.route('/api/client/register', methods=['POST'])
def client_register():
    """
    Registro de cliente desde app móvil (sin requerir cuentas bancarias)

    Body (JSON):
        - tipo_persona: 'Natural' | 'Jurídica'
        - document_type / tipo_documento: 'DNI' | 'CE' (para Natural)
        - dni: Número de documento (o ruc para Jurídica)
        - ruc: RUC para Jurídica
        - email: Email del cliente
        - telefono: Teléfono del cliente
        - nombres, apellido_paterno, apellido_materno: Para Natural
        - razon_social, persona_contacto: Para Jurídica
        - direccion: Dirección completa
        - departamento, provincia, distrito: Ubicación
        - password: Contraseña para la cuenta

    Returns:
        - success: bool
        - message: str
        - client: dict (opcional)
    """
    try:
        data = request.get_json() or {}

        logger.info(f'📱 [PLATFORM API] Registro de cliente desde app móvil')
        logger.info(f'Data recibida: {list(data.keys())}')

        # Validar campos requeridos básicos
        required_fields = ['email', 'telefono', 'direccion', 'departamento',
                          'provincia', 'distrito', 'password']

        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'message': f'El campo {field} es requerido'
                }), 400

        tipo_persona = data.get('tipo_persona', 'Natural')
        email = data.get('email', '').strip()
        telefono = data.get('telefono', '').strip()
        password = data.get('password', '').strip()

        # Validar email
        if not validate_email(email):
            return jsonify({
                'success': False,
                'message': 'Email inválido'
            }), 400

        # Verificar email duplicado
        existing_email = Client.query.filter_by(email=email).first()
        if existing_email:
            return jsonify({
                'success': False,
                'message': 'Ya existe un cliente con este email'
            }), 400

        # Validar según tipo de persona
        if tipo_persona == 'Natural':
            document_type = data.get('tipo_documento') or data.get('document_type', 'DNI')
            dni = data.get('dni', '').strip()
            nombres = data.get('nombres', '').strip()
            apellido_paterno = data.get('apellido_paterno', '').strip()
            apellido_materno = data.get('apellido_materno', '').strip()

            if not dni or not nombres or not apellido_paterno:
                return jsonify({
                    'success': False,
                    'message': 'DNI, nombres y apellido paterno son requeridos'
                }), 400

            # Validar longitud DNI/CE
            if document_type == 'DNI' and len(dni) != 8:
                return jsonify({
                    'success': False,
                    'message': 'El DNI debe tener 8 dígitos'
                }), 400
            elif document_type == 'CE' and len(dni) != 9:
                return jsonify({
                    'success': False,
                    'message': 'El CE debe tener 9 dígitos'
                }), 400

            # Verificar DNI duplicado
            existing_client = Client.query.filter_by(dni=dni).first()
            if existing_client:
                return jsonify({
                    'success': False,
                    'message': f'Ya existe un cliente con el {document_type} {dni}'
                }), 400

        else:  # Jurídica
            document_type = 'RUC'
            ruc = data.get('ruc', '').strip()
            dni = ruc  # Usar RUC como DNI para consistencia
            razon_social = data.get('razon_social', '').strip()
            persona_contacto = data.get('persona_contacto', '').strip()

            if not ruc or not razon_social or not persona_contacto:
                return jsonify({
                    'success': False,
                    'message': 'RUC, razón social y persona de contacto son requeridos'
                }), 400

            # Validar longitud RUC
            if len(ruc) != 11:
                return jsonify({
                    'success': False,
                    'message': 'El RUC debe tener 11 dígitos'
                }), 400

            # Verificar RUC duplicado
            existing_client = Client.query.filter_by(dni=ruc).first()
            if existing_client:
                return jsonify({
                    'success': False,
                    'message': f'Ya existe un cliente con el RUC {ruc}'
                }), 400

        # Crear cliente
        new_client = Client(
            document_type=document_type,
            dni=dni,
            email=email.lower(),
            phone=telefono,
            direccion=data.get('direccion', '').strip(),
            departamento=data.get('departamento', '').strip(),
            provincia=data.get('provincia', '').strip(),
            distrito=data.get('distrito', '').strip(),
            status='Activo',  # Activo desde app móvil
            created_at=now_peru(),
            origen='App'  # Marcar como origen App
        )

        # Campos según tipo de persona
        if tipo_persona == 'Natural':
            new_client.nombres = nombres
            new_client.apellido_paterno = apellido_paterno
            new_client.apellido_materno = apellido_materno or ''
        else:
            new_client.razon_social = razon_social
            new_client.persona_contacto = persona_contacto

        # Usuario "plataforma" como creador
        platform_user = User.query.filter_by(username='plataforma').first()
        if platform_user:
            new_client.created_by = platform_user.id

        # Guardar cliente
        db.session.add(new_client)

        # Crear usuario asociado para login
        new_user = User(
            username=dni,
            email=email.lower(),
            dni=dni,
            role='Plataforma',  # Rol para clientes de app móvil
            status='Activo',
            created_at=now_peru()
        )
        new_user.set_password(password)

        db.session.add(new_user)
        db.session.commit()

        logger.info(f'✅ Cliente registrado desde app: {dni} - {new_client.full_name}')

        return jsonify({
            'success': True,
            'message': 'Registro exitoso. Ya puedes iniciar sesión con tu DNI y contraseña.',
            'client': new_client.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        logger.error(f'❌ Error en client_register: {str(e)}', exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Error al registrar: {str(e)}'
        }), 500
