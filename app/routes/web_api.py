"""
Rutas API para la Página Web QoriCash
Este módulo proporciona endpoints específicos para la página web pública
Actualizado: 2026-01-12 - Force redeploy para activar servicio en Render
"""
from flask import Blueprint, request, jsonify
from app.models.client import Client
from app.models.user import User
from app.extensions import db, csrf
from werkzeug.security import generate_password_hash
from app.utils.formatters import now_peru
import logging

logger = logging.getLogger(__name__)

web_api_bp = Blueprint('web_api', __name__, url_prefix='/api/web')


@web_api_bp.after_request
def after_request(response):
    """Agregar headers CORS a todas las respuestas del blueprint"""
    origin = request.headers.get('Origin')

    # Lista de orígenes permitidos
    allowed_origins = [
        'http://localhost:3000',  # Página web QoriCash (desarrollo)
        'https://qoricash.pe',     # Página web QoriCash (producción)
        'https://www.qoricash.pe'  # Página web QoriCash (producción con www)
    ]

    # Si el origen está en la lista, agregarlo
    if origin in allowed_origins:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'

    return response


@web_api_bp.route('/register', methods=['OPTIONS', 'POST'])
@csrf.exempt
def register_from_web():
    """
    Registro de clientes desde la página web

    Soporta:
    - Persona Natural (DNI o CE)
    - Persona Jurídica (RUC)

    Request JSON:
    {
        "tipo_persona": "Natural" | "Jurídica",
        "tipo_documento": "DNI" | "CE" | "RUC",
        "dni": "12345678" (8 dígitos para DNI, 9 para CE, 11 para RUC),
        "nombres": "Juan" (para Natural),
        "apellido_paterno": "García" (para Natural),
        "apellido_materno": "López" (para Natural, opcional),
        "razon_social": "Empresa SAC" (para Jurídica),
        "persona_contacto": "Juan García" (para Jurídica),
        "email": "email@ejemplo.com",
        "telefono": "987654321",
        "direccion": "Av. Principal 123",
        "departamento": "Lima",
        "provincia": "Lima",
        "distrito": "Miraflores",
        "password": "contraseña segura",
        "accept_promotions": true/false
    }

    Returns:
        JSON: {
            "success": true/false,
            "message": "...",
            "client": {...} (si success=true)
        }
    """
    # Manejar preflight OPTIONS request
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'message': 'No se recibieron datos'
            }), 400

        # Obtener datos comunes
        tipo_persona = data.get('tipo_persona', 'Natural').strip()
        tipo_documento = data.get('tipo_documento', 'DNI').strip()
        dni = data.get('dni', '').strip()
        email = data.get('email', '').strip()
        telefono = data.get('telefono', '').strip()
        direccion = data.get('direccion', '').strip()
        departamento = data.get('departamento', '').strip()
        provincia = data.get('provincia', '').strip()
        distrito = data.get('distrito', '').strip()
        password = data.get('password', '').strip()
        accept_promotions = data.get('accept_promotions', False)

        # Validar campos obligatorios
        if not all([dni, email, telefono, direccion, departamento, provincia, distrito, password]):
            return jsonify({
                'success': False,
                'message': 'Faltan campos obligatorios'
            }), 400

        # Validar email
        if not email or '@' not in email:
            return jsonify({
                'success': False,
                'message': 'Email inválido'
            }), 400

        # Validar contraseña
        if len(password) < 8:
            return jsonify({
                'success': False,
                'message': 'La contraseña debe tener al menos 8 caracteres'
            }), 400

        # Validar según tipo de persona
        if tipo_persona == 'Natural':
            nombres = data.get('nombres', '').strip()
            apellido_paterno = data.get('apellido_paterno', '').strip()
            apellido_materno = data.get('apellido_materno', '').strip()

            if not all([nombres, apellido_paterno]):
                return jsonify({
                    'success': False,
                    'message': 'Nombres y apellido paterno son obligatorios'
                }), 400

            # Validar DNI o CE
            if tipo_documento == 'DNI':
                if len(dni) != 8:
                    return jsonify({
                        'success': False,
                        'message': 'DNI debe tener 8 dígitos'
                    }), 400
            elif tipo_documento == 'CE':
                if len(dni) != 9:
                    return jsonify({
                        'success': False,
                        'message': 'Carné de Extranjería debe tener 9 dígitos'
                    }), 400
            else:
                return jsonify({
                    'success': False,
                    'message': 'Tipo de documento inválido para Persona Natural'
                }), 400

        elif tipo_persona == 'Jurídica':
            razon_social = data.get('razon_social', '').strip()
            persona_contacto = data.get('persona_contacto', '').strip()

            if not all([razon_social, persona_contacto]):
                return jsonify({
                    'success': False,
                    'message': 'Razón social y persona de contacto son obligatorios'
                }), 400

            # Validar RUC
            if tipo_documento != 'RUC':
                tipo_documento = 'RUC'  # Forzar RUC para Jurídica

            if len(dni) != 11:
                return jsonify({
                    'success': False,
                    'message': 'RUC debe tener 11 dígitos'
                }), 400
        else:
            return jsonify({
                'success': False,
                'message': 'Tipo de persona inválido'
            }), 400

        # Verificar si el cliente ya existe
        existing_client = Client.query.filter_by(dni=dni).first()
        if existing_client:
            tipo_doc_msg = 'RUC' if tipo_persona == 'Jurídica' else tipo_documento
            return jsonify({
                'success': False,
                'message': f'Ya existe un cliente con el {tipo_doc_msg} {dni}'
            }), 409

        # Obtener o crear usuario "Web" para asignar como creador
        web_user = User.query.filter(
            (User.username == 'Web') | (User.email == 'web@qoricash.pe')
        ).first()

        if not web_user:
            logger.info("🌐 Usuario 'Web' no existe, creándolo...")
            import secrets
            web_user = User(
                username='Web',
                email='web@qoricash.pe',
                dni='22222222',  # DNI ficticio para usuario Web
                role='Web',
                password_hash=generate_password_hash(secrets.token_urlsafe(32)),
                status='Activo',
                created_at=now_peru()
            )
            db.session.add(web_user)
            db.session.flush()
            logger.info(f"✅ Usuario 'Web' creado con ID: {web_user.id}")

        # Crear cliente según tipo de persona
        if tipo_persona == 'Natural':
            new_client = Client(
                dni=dni,
                document_type=tipo_documento,
                email=email,
                nombres=nombres,
                apellido_paterno=apellido_paterno,
                apellido_materno=apellido_materno or '',
                phone=telefono,
                direccion=direccion,
                departamento=departamento,
                provincia=provincia,
                distrito=distrito,
                status='Activo',
                password_hash=generate_password_hash(password),
                requires_password_change=False,
                created_by=web_user.id,
                created_at=now_peru()
            )
        else:  # Jurídica
            new_client = Client(
                dni=dni,  # RUC
                document_type='RUC',
                email=email,
                razon_social=razon_social,
                persona_contacto=persona_contacto,
                phone=telefono,
                direccion=direccion,
                departamento=departamento,
                provincia=provincia,
                distrito=distrito,
                status='Activo',
                password_hash=generate_password_hash(password),
                requires_password_change=False,
                created_by=web_user.id,
                created_at=now_peru()
            )

        db.session.add(new_client)
        db.session.commit()

        logger.info(f"🌐 Cliente registrado desde web: {new_client.dni} (ID: {new_client.id})")

        # Enviar email de bienvenida
        try:
            from app.services.email_service import EmailService
            from flask_mail import Message
            from app.extensions import mail

            saludo = f"{nombres} {apellido_paterno}" if tipo_persona == 'Natural' else razon_social
            tipo_doc_email = tipo_documento

            msg = Message(
                subject='Bienvenido a QoriCash - Cuenta Creada',
                sender=('QoriCash', 'info@qoricash.pe'),
                recipients=[email]
            )

            msg.html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #0D1B2A 0%, #1a2942 100%); padding: 30px; text-align: center; color: white; }}
        .content {{ background: #f9f9f9; padding: 30px; }}
        .info-box {{ background: #e0f2fe; border-left: 4px solid #0284c7; padding: 15px; margin: 20px 0; }}
        .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>¡Bienvenido a QoriCash!</h1>
            <p>Tu Casa de Cambio Digital</p>
        </div>
        <div class="content">
            <p>Hola <strong>{saludo}</strong>,</p>
            <p>¡Tu cuenta ha sido creada exitosamente desde nuestra página web! 🎉</p>

            <div class="info-box">
                <p style="margin: 0; font-weight: bold;">📋 Tu información de acceso:</p>
                <p style="margin: 10px 0 0 0;">{tipo_doc_email}: <strong>{dni}</strong></p>
            </div>

            <p><strong>📱 Próximos pasos:</strong></p>
            <ol>
                <li>Ingresa a nuestra plataforma web con tu {tipo_doc_email} y contraseña</li>
                <li>Completa tu perfil con tus cuentas bancarias</li>
                <li>Sube la documentación requerida para validación KYC</li>
                <li>Una vez aprobado, ¡podrás realizar operaciones!</li>
            </ol>

            <p><strong>💡 Recuerda:</strong></p>
            <ul>
                <li>Mantén tu contraseña segura</li>
                <li>Nunca la compartas con nadie</li>
                <li>Para cualquier consulta, contáctanos</li>
            </ul>
        </div>
        <div class="footer">
            <p>Este es un correo automático, por favor no responder.</p>
            <p>© 2025 QoriCash - Casa de Cambio Digital</p>
        </div>
    </div>
</body>
</html>
"""

            mail.send(msg)
            logger.info(f"📧 Email de bienvenida enviado a {email}")

        except Exception as email_error:
            logger.error(f"❌ Error enviando email: {str(email_error)}")
            # No bloquear el registro si falla el email

        return jsonify({
            'success': True,
            'message': '¡Registro exitoso! Revisa tu email para más información.',
            'client': {
                'id': new_client.id,
                'dni': new_client.dni,
                'email': new_client.email,
                'tipo_persona': tipo_persona,
                'tipo_documento': tipo_documento
            }
        }), 201

    except Exception as e:
        logger.error(f"❌ Error en registro web: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error al registrar: {str(e)}'
        }), 500


@web_api_bp.route('/my-operations', methods=['POST'])
@csrf.exempt
def get_my_operations():
    """
    Obtener operaciones del cliente autenticado

    Request JSON:
    {
        "dni": "12345678"
    }

    Returns:
        JSON: {
            "success": true/false,
            "operations": [...]
        }
    """
    try:
        data = request.get_json()

        if not data or 'dni' not in data:
            return jsonify({
                'success': False,
                'message': 'DNI es requerido'
            }), 400

        dni = data.get('dni', '').strip()

        # Buscar cliente
        client = Client.query.filter_by(dni=dni).first()
        if not client:
            return jsonify({
                'success': False,
                'message': 'Cliente no encontrado'
            }), 404

        # Obtener operaciones
        from app.models.operation import Operation
        operations = Operation.query.filter_by(
            client_id=client.id
        ).order_by(Operation.created_at.desc()).limit(50).all()

        return jsonify({
            'success': True,
            'data': [op.to_dict(include_relations=True) for op in operations]
        }), 200

    except Exception as e:
        logger.error(f"❌ Error al obtener operaciones: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error al obtener operaciones: {str(e)}'
        }), 500


@web_api_bp.route('/stats', methods=['POST'])
@csrf.exempt
def get_client_stats():
    """
    Obtener estadísticas del cliente

    Request JSON:
    {
        "dni": "12345678"
    }

    Returns:
        JSON: {
            "success": true/false,
            "data": {
                "total_operations": 0,
                "pending_operations": 0,
                "completed_operations": 0,
                "total_soles": 0.0,
                "total_dolares": 0.0
            }
        }
    """
    try:
        data = request.get_json()

        if not data or 'dni' not in data:
            return jsonify({
                'success': False,
                'message': 'DNI es requerido'
            }), 400

        dni = data.get('dni', '').strip()

        # Buscar cliente
        client = Client.query.filter_by(dni=dni).first()
        if not client:
            return jsonify({
                'success': False,
                'message': 'Cliente no encontrado'
            }), 404

        # Calcular estadísticas
        from app.models.operation import Operation
        from sqlalchemy import func

        operations = Operation.query.filter_by(client_id=client.id).all()

        total_operations = len(operations)
        pending_operations = len([op for op in operations if op.status in ['Pendiente', 'En proceso']])
        completed_operations = len([op for op in operations if op.status == 'Completado'])

        total_soles = sum([op.amount_pen for op in operations if op.status == 'Completado'])
        total_dolares = sum([op.amount_usd for op in operations if op.status == 'Completado'])

        return jsonify({
            'success': True,
            'data': {
                'total_operations': total_operations,
                'pending_operations': pending_operations,
                'completed_operations': completed_operations,
                'total_soles': float(total_soles),
                'total_dolares': float(total_dolares)
            }
        }), 200

    except Exception as e:
        logger.error(f"❌ Error al obtener estadísticas: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error al obtener estadísticas: {str(e)}'
        }), 500


@web_api_bp.route('/my-accounts', methods=['POST'])
@csrf.exempt
def get_my_accounts():
    """
    Obtener cuentas bancarias del cliente

    Request JSON:
    {
        "dni": "12345678"
    }

    Returns:
        JSON: {
            "success": true/false,
            "data": [...]
        }
    """
    try:
        data = request.get_json()

        if not data or 'dni' not in data:
            return jsonify({
                'success': False,
                'message': 'DNI es requerido'
            }), 400

        dni = data.get('dni', '').strip()

        # Buscar cliente
        client = Client.query.filter_by(dni=dni).first()
        if not client:
            return jsonify({
                'success': False,
                'message': 'Cliente no encontrado'
            }), 404

        # Obtener cuentas bancarias
        bank_accounts = client.bank_accounts or []

        return jsonify({
            'success': True,
            'data': bank_accounts
        }), 200

    except Exception as e:
        logger.error(f"❌ Error al obtener cuentas bancarias: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error al obtener cuentas bancarias: {str(e)}'
        }), 500


@web_api_bp.route('/create-operation', methods=['POST'])
@csrf.exempt
def create_operation_web():
    """
    Crear operación desde la página web

    POST JSON:
        dni: string (required)
        tipo: string (required) - 'compra' o 'venta'
        monto_soles: float (required)
        monto_dolares: float (required)
        banco_cuenta_id: int (required)
    """
    try:
        data = request.get_json()
        logger.info(f"📝 Solicitud de creación de operación desde WEB: {data}")

        # Validar datos requeridos
        required_fields = ['dni', 'tipo', 'monto_soles', 'monto_dolares', 'banco_cuenta_id']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'message': f'Campo requerido: {field}'
                }), 400

        # Buscar cliente por DNI
        client = Client.query.filter_by(dni=data['dni']).first()
        if not client:
            return jsonify({
                'success': False,
                'message': 'Cliente no encontrado'
            }), 404

        # Obtener tipo de cambio actual
        from app.models.exchange_rate import ExchangeRate
        current_rates = ExchangeRate.get_current_rates()
        if not current_rates:
            return jsonify({
                'success': False,
                'message': 'No hay tipo de cambio disponible'
            }), 500

        # Determinar tipo de cambio según operación
        tipo = data['tipo'].lower()
        exchange_rate = current_rates['compra'] if tipo == 'compra' else current_rates['venta']

        # Validar cuenta bancaria del cliente (están en JSON)
        bank_accounts = client.bank_accounts  # Método property que parsea el JSON
        bank_account_index = data['banco_cuenta_id']

        if not bank_accounts or bank_account_index >= len(bank_accounts):
            return jsonify({
                'success': False,
                'message': 'Cuenta bancaria no válida'
            }), 400

        selected_account = bank_accounts[bank_account_index]

        # Crear operación
        from app.models.operation import Operation
        new_operation = Operation(
            client_id=client.id,
            tipo=tipo.capitalize(),
            monto_soles=float(data['monto_soles']),
            monto_dolares=float(data['monto_dolares']),
            tipo_cambio=exchange_rate,
            estado='Pendiente',
            canal='web',  # Marcar como operación desde web
            trader_id=client.created_by,  # Asignar al trader que registró al cliente
            banco_cuenta_id=data['banco_cuenta_id'],
            created_at=now_peru()
        )

        db.session.add(new_operation)
        db.session.commit()

        # Generar código de operación
        new_operation.codigo_operacion = f"EXP-{new_operation.id}"
        db.session.commit()

        logger.info(f"✅ Operación {new_operation.codigo_operacion} creada desde WEB para cliente {client.dni}")

        # Notificar al sistema (opcional, si el servicio de notificaciones está disponible)
        try:
            from app.services.notification_service import NotificationService
            NotificationService.notify_new_operation(new_operation)
            NotificationService.notify_dashboard_update()
        except Exception as notify_error:
            logger.warning(f"⚠️ Error al notificar operación: {str(notify_error)}")

        return jsonify({
            'success': True,
            'message': 'Operación creada exitosamente',
            'data': {
                'operation': {
                    'id': new_operation.id,
                    'codigo_operacion': new_operation.codigo_operacion,
                    'tipo': new_operation.tipo,
                    'monto_soles': new_operation.monto_soles,
                    'monto_dolares': new_operation.monto_dolares,
                    'tipo_cambio': new_operation.tipo_cambio,
                    'estado': new_operation.estado,
                    'canal': new_operation.canal,
                    'created_at': new_operation.created_at.isoformat() if new_operation.created_at else None,
                }
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Error al crear operación desde WEB: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'message': f'Error al crear operación: {str(e)}'
        }), 500


@web_api_bp.route('/health', methods=['GET'])
def health_check():
    """Health check para web API"""
    return jsonify({
        'status': 'ok',
        'service': 'QoriCash Web API',
        'version': '1.0.0'
    }), 200
