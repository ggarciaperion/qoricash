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
from app.utils.referral import generate_referral_code
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

        # Sistema de referidos: Generar código único para el nuevo cliente
        max_attempts = 10
        for _ in range(max_attempts):
            referral_code = generate_referral_code()
            existing_code = Client.query.filter_by(referral_code=referral_code).first()
            if not existing_code:
                new_client.referral_code = referral_code
                logger.info(f'✨ Código de referido generado para cliente web: {referral_code}')
                break

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

        # Solo contar operaciones completadas en total_operations
        total_operations = len([op for op in operations if op.status == 'Completada'])
        pending_operations = len([op for op in operations if op.status in ['Pendiente', 'En proceso']])
        completed_operations = len([op for op in operations if op.status == 'Completada'])

        total_soles = sum([op.amount_pen for op in operations if op.status == 'Completada'])
        total_dolares = sum([op.amount_usd for op in operations if op.status == 'Completada'])

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

        # Determinar source_account y destination_account según tipo de operación
        # La cuenta seleccionada es donde el cliente RECIBE el pago (destination)
        destination_currency = 'S/' if tipo == 'compra' else '$'
        source_currency = '$' if tipo == 'compra' else 'S/'

        # Validar que la cuenta seleccionada sea de la moneda correcta
        if selected_account.get('currency') != destination_currency:
            return jsonify({
                'success': False,
                'message': f'La cuenta seleccionada debe ser en {destination_currency} para este tipo de operación'
            }), 400

        # destination_account es la cuenta seleccionada (donde el cliente recibirá el pago)
        destination_account = selected_account.get('account_number', '')

        # source_account: buscar otra cuenta del cliente en la moneda correcta
        # (cuenta desde donde el cliente transferirá a QoriCash)
        source_account = ''
        for account in bank_accounts:
            if account.get('currency') == source_currency:
                source_account = account.get('account_number', '')
                break

        # Crear operación con campos correctos del modelo
        from app.models.operation import Operation

        # Generar operation_id usando el método del modelo (mantiene correlativo único)
        operation_id = Operation.generate_operation_id()

        new_operation = Operation(
            operation_id=operation_id,
            client_id=client.id,
            user_id=client.created_by,  # Trader que registró al cliente
            operation_type=tipo.capitalize(),  # 'Compra' o 'Venta'
            amount_usd=float(data['monto_dolares']),
            amount_pen=float(data['monto_soles']),
            exchange_rate=exchange_rate,
            status='Pendiente',
            origen='web',  # Marcar como operación desde web
            source_account=source_account,  # Cuenta del cliente desde donde transferirá
            destination_account=destination_account,  # Cuenta del cliente donde recibirá el pago
            created_at=now_peru()
        )

        db.session.add(new_operation)
        db.session.commit()

        logger.info(f"✅ Operación {new_operation.operation_id} creada desde WEB para cliente {client.dni}")
        logger.info(f"   📊 Estado: {new_operation.status} | Origen: {new_operation.origen} | Creada: {new_operation.created_at}")

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
                    'codigo_operacion': new_operation.operation_id,
                    'tipo': new_operation.operation_type,
                    'monto_soles': float(new_operation.amount_pen),
                    'monto_dolares': float(new_operation.amount_usd),
                    'tipo_cambio': float(new_operation.exchange_rate),
                    'estado': new_operation.status,
                    'canal': new_operation.origen,
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


@web_api_bp.route('/cancel-operation', methods=['POST'])
@csrf.exempt
def cancel_operation_web():
    """
    Cancelar una operación desde la página web

    Request JSON:
        {
            "operation_id": 198,
            "reason": "No puedo realizar la transferencia"
        }

    Returns:
        JSON con éxito o error
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'message': 'No se recibieron datos'
            }), 400

        # Validar campos requeridos
        operation_id = data.get('operation_id')
        reason = data.get('reason', 'Cancelado desde la página web')

        if not operation_id:
            return jsonify({
                'success': False,
                'message': 'Campo requerido: operation_id'
            }), 400

        # Obtener operación
        from app.models.operation import Operation
        operation = Operation.query.get(operation_id)

        if not operation:
            return jsonify({
                'success': False,
                'message': 'Operación no encontrada'
            }), 404

        # Verificar que la operación esté en estado Pendiente
        if operation.status != 'Pendiente':
            return jsonify({
                'success': False,
                'message': f'No se puede cancelar una operación en estado {operation.status}'
            }), 400

        # Cancelar operación
        operation.status = 'Cancelado'
        operation.updated_at = now_peru()

        # Agregar motivo a las notas
        if operation.notes:
            operation.notes += f"\n\n[{now_peru().strftime('%Y-%m-%d %H:%M')}] Cancelado desde web: {reason}"
        else:
            operation.notes = f"Cancelado desde web: {reason}"

        db.session.commit()

        logger.info(f"✅ Operación {operation.operation_id} cancelada desde WEB. Motivo: {reason}")

        return jsonify({
            'success': True,
            'message': 'Operación cancelada exitosamente'
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Error al cancelar operación desde WEB: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'message': f'Error al cancelar operación: {str(e)}'
        }), 500


@web_api_bp.route('/submit-proof', methods=['POST'])
@csrf.exempt
def submit_proof_web():
    """
    Enviar comprobantes de pago desde la página web

    Este endpoint:
    1. Recibe archivos de comprobante (hasta 4)
    2. Registra el código de voucher del cliente
    3. Actualiza el estado de la operación a "En proceso"
    4. Asigna automáticamente la operación a un Operador

    Form data:
        operation_id: int (required) - ID de la operación
        voucher_code: string (optional) - Código del comprobante de transferencia del cliente
        files: list of files (optional) - Hasta 4 archivos de comprobante

    Returns:
        JSON con resultado de la operación
    """
    try:
        # Obtener operation_id del form
        operation_id = request.form.get('operation_id', type=int)
        if not operation_id:
            return jsonify({
                'success': False,
                'message': 'operation_id es requerido'
            }), 400

        # Buscar operación
        from app.models.operation import Operation
        operation = Operation.query.get(operation_id)

        if not operation:
            return jsonify({
                'success': False,
                'message': 'Operación no encontrada'
            }), 404

        # Verificar que la operación esté en estado Pendiente
        if operation.status != 'Pendiente':
            return jsonify({
                'success': False,
                'message': f'No se puede procesar una operación en estado {operation.status}'
            }), 400

        # Obtener código de voucher (opcional)
        voucher_code = request.form.get('voucher_code', '').strip()

        # Procesar archivos de comprobante
        uploaded_urls = []
        if request.files:
            from app.services.file_service import FileService
            file_service = FileService()

            # Obtener todos los archivos del request
            files = request.files.getlist('files')

            if len(files) > 4:
                return jsonify({
                    'success': False,
                    'message': 'Máximo 4 archivos permitidos'
                }), 400

            # Subir cada archivo
            for i, file in enumerate(files):
                if file and file.filename:
                    success, message, url = file_service.upload_file(
                        file,
                        'client_proofs',
                        f"{operation.operation_id}_proof_{i}"
                    )

                    if success:
                        uploaded_urls.append(url)
                    else:
                        logger.error(f"Error subiendo archivo {i}: {message}")
                        # Continuar con los demás archivos aunque uno falle

        # Actualizar operación
        operation.status = 'En proceso'
        operation.in_process_since = now_peru()

        # Guardar código de voucher en notas si fue proporcionado
        if voucher_code:
            voucher_note = f"Código de comprobante del cliente: {voucher_code}"
            if operation.notes:
                operation.notes += f"\n{voucher_note}"
            else:
                operation.notes = voucher_note

        # Inicializar client_deposits con datos completos del abono del cliente
        # Determinar el monto y la moneda según el tipo de operación
        if operation.operation_type == 'Compra':
            # Compra: Cliente vende USD (abona dólares)
            deposit_amount = float(operation.amount_usd)
            deposit_currency = '$'
        else:
            # Venta: Cliente compra USD (abona soles)
            deposit_amount = float(operation.amount_pen)
            deposit_currency = 'S/'

        # Crear registro de abono con TODOS los campos necesarios
        deposit_entry = {
            'importe': deposit_amount,
            'codigo_operacion': voucher_code if voucher_code else '',
            'cuenta_cargo': operation.source_account or '',
            'comprobante_url': uploaded_urls[0] if uploaded_urls else '',
            'fecha': now_peru().isoformat()
        }

        operation.client_deposits = [deposit_entry]

        # Inicializar client_payments con datos de la cuenta destino
        # Determinar el monto de pago según el tipo de operación
        if operation.operation_type == 'Compra':
            # Compra: QoriCash paga soles al cliente
            payment_amount = float(operation.amount_pen)
        else:
            # Venta: QoriCash paga dólares al cliente
            payment_amount = float(operation.amount_usd)

        # Crear registro de pago con cuenta destino
        payment_entry = {
            'importe': payment_amount,
            'cuenta_destino': operation.destination_account or ''
        }

        operation.client_payments = [payment_entry]

        # Asignar operador automáticamente de forma balanceada
        from app.services.operation_service import OperationService
        assigned_operator_id = OperationService.assign_operator_balanced()

        if assigned_operator_id:
            operation.assigned_operator_id = assigned_operator_id
            logger.info(f"✅ Operación {operation.operation_id} asignada al operador ID: {assigned_operator_id}")
        else:
            logger.warning(f"⚠️ No se pudo asignar operador a {operation.operation_id}")

        # Registrar en audit log
        from app.models.audit_log import AuditLog
        AuditLog.log_action(
            user_id=operation.user_id,
            action='UPDATE_OPERATION',
            entity='Operation',
            entity_id=operation.id,
            details=f'Operación {operation.operation_id} enviada a proceso desde web. ' +
                   f'Comprobantes: {len(uploaded_urls)}. ' +
                   (f'Asignada al operador ID {assigned_operator_id}' if assigned_operator_id else 'Sin operador asignado')
        )

        db.session.commit()

        # Notificar actualización
        try:
            from app.services.notification_service import NotificationService
            NotificationService.notify_operation_updated(operation, 'Pendiente')
            NotificationService.notify_dashboard_update()

            # Notificar al operador asignado
            if assigned_operator_id:
                from app.models.user import User
                assigned_operator = User.query.get(assigned_operator_id)
                if assigned_operator:
                    NotificationService.notify_operation_assigned(operation, assigned_operator)
        except Exception as notify_error:
            logger.warning(f"⚠️ Error al notificar: {str(notify_error)}")

        logger.info(f"✅ Comprobante(s) enviado(s) desde WEB para operación {operation.operation_id}")

        return jsonify({
            'success': True,
            'message': 'Comprobante enviado exitosamente. Tu operación está en proceso.',
            'data': {
                'operation_id': operation.id,
                'codigo_operacion': operation.operation_id,
                'estado': operation.status,
                'archivos_subidos': len(uploaded_urls),
                'operador_asignado': assigned_operator_id is not None
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Error al enviar comprobante desde WEB: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'message': f'Error al enviar comprobante: {str(e)}'
        }), 500


@web_api_bp.route('/health', methods=['GET'])
def health_check():
    """Health check para web API"""
    return jsonify({
        'status': 'ok',
        'service': 'QoriCash Web API',
        'version': '1.0.0'
    }), 200
