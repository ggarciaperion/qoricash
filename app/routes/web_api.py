"""
Rutas API para la Página Web QoriCash
Este módulo proporciona endpoints específicos para la página web pública
Actualizado: 2026-01-12 - Force redeploy para activar servicio en Render
"""
from flask import Blueprint, request, jsonify
from app.models.client import Client
from app.models.user import User
from app.models.operation import Operation
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
        direccion = data.get('direccion', '').strip().upper()
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
            nombres = data.get('nombres', '').strip().upper()
            apellido_paterno = data.get('apellido_paterno', '').strip().upper()
            apellido_materno = data.get('apellido_materno', '').strip().upper()

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
            razon_social = data.get('razon_social', '').strip().upper()
            persona_contacto = data.get('persona_contacto', '').strip().upper()

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
        # IMPORTANTE: Todos los clientes se crean con status='Inactivo'
        # Solo después de que Middle Office valide KYC se cambia a 'Activo'
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
                status='Inactivo',  # Cambio: Inicia inactivo hasta validación KYC
                has_complete_documents=False,  # Sin documentos al registrarse
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
                status='Inactivo',  # Cambio: Inicia inactivo hasta validación KYC
                has_complete_documents=False,  # Sin documentos al registrarse
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

        # Enviar email de bienvenida diferenciado (registro desde WEB)
        try:
            from app.services.email_templates import EmailTemplates

            # Usar template específico para registro desde web
            EmailTemplates.send_welcome_email_from_web(new_client)
            logger.info(f'✉️ Email de bienvenida web enviado a {new_client.dni}')

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


@web_api_bp.route('/my-operations', methods=['OPTIONS', 'POST'])
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
    # Manejar preflight OPTIONS request
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

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


@web_api_bp.route('/stats', methods=['OPTIONS', 'POST'])
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
    # Manejar preflight OPTIONS request
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

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


@web_api_bp.route('/my-accounts', methods=['OPTIONS', 'POST'])
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
    # Manejar preflight OPTIONS request
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

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


@web_api_bp.route('/create-operation', methods=['OPTIONS', 'POST'])
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
        referral_code: string (optional) - Código de referido aplicado
    """
    # Manejar preflight OPTIONS request
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

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

        # CRÍTICO: Procesar código de referido si se proporcionó
        referral_code = data.get('referral_code', '').strip().upper()
        if referral_code:
            # Verificar que el cliente no haya usado un código anteriormente
            if client.used_referral_code:
                return jsonify({
                    'success': False,
                    'message': 'Ya has usado un código de referido en una operación anterior'
                }), 400

            # Validar que el código exista y no sea su propio código
            referrer = Client.query.filter_by(referral_code=referral_code).first()
            if not referrer:
                return jsonify({
                    'success': False,
                    'message': 'Código de referido no válido'
                }), 400

            if referrer.id == client.id:
                return jsonify({
                    'success': False,
                    'message': 'No puedes usar tu propio código de referido'
                }), 400

            # Guardar el código usado y quién lo refirió
            client.used_referral_code = referral_code
            client.referred_by = referrer.id
            logger.info(f"✅ Cliente {client.dni} usó código de referido {referral_code} de {referrer.full_name}")

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

        # Contabilizar uso del código de referido (independiente de si se completa la operación)
        if referral_code:
            try:
                from app.services.referral_service import referral_service
                referral_service.count_referral_use(client)
            except Exception as e:
                logger.warning(f"⚠️ Error al contabilizar uso de referido: {str(e)}")

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


@web_api_bp.route('/cancel-operation', methods=['OPTIONS', 'POST'])
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


@web_api_bp.route('/submit-proof', methods=['OPTIONS', 'POST'])
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
    # Manejar preflight OPTIONS request
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

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


@web_api_bp.route('/fix-referral-73733737', methods=['POST'])
@csrf.exempt
def fix_referral_code_temp():
    """
    ENDPOINT TEMPORAL: Actualizar cliente 73733737 que usó código 3NEFUG antes del fix
    Este endpoint se puede eliminar después de ejecutarlo una vez
    """
    try:
        # Buscar el cliente con DNI 73733737
        client = Client.query.filter_by(dni='73733737').first()

        if not client:
            return jsonify({
                'success': False,
                'message': 'Cliente con DNI 73733737 no encontrado'
            }), 404

        # Verificar si ya fue actualizado
        if client.used_referral_code == '3NEFUG':
            return jsonify({
                'success': True,
                'message': 'Cliente ya fue actualizado previamente',
                'already_fixed': True
            }), 200

        # Buscar el dueño del código 3NEFUG
        referrer = Client.query.filter_by(referral_code='3NEFUG').first()

        if not referrer:
            return jsonify({
                'success': False,
                'message': 'No se encontró el dueño del código 3NEFUG'
            }), 404

        # Actualizar el cliente
        client.used_referral_code = '3NEFUG'
        client.referred_by = referrer.id

        # Guardar cambios
        db.session.commit()

        logger.info(f"✅ Fix aplicado: Cliente {client.dni} marcado como que usó código {client.used_referral_code}")

        return jsonify({
            'success': True,
            'message': 'Cliente actualizado exitosamente',
            'data': {
                'client_dni': client.dni,
                'client_name': client.full_name,
                'used_referral_code': client.used_referral_code,
                'referrer_name': referrer.full_name,
                'referrer_code': referrer.referral_code
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Error al aplicar fix de referral code: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error al aplicar fix: {str(e)}'
        }), 500


@web_api_bp.route('/run-migration-reward-codes', methods=['POST'])
@csrf.exempt
def run_migration_reward_codes():
    """
    ENDPOINT TEMPORAL: Crear tabla reward_codes y agregar columna referral_total_uses
    Este endpoint se puede eliminar después de ejecutarlo una vez
    """
    try:
        # Verificar si la tabla reward_codes ya existe
        result = db.session.execute(db.text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_name = 'reward_codes'
        """))
        table_exists = result.fetchone() is not None

        # Verificar si la columna referral_total_uses ya existe
        result = db.session.execute(db.text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'clients'
            AND column_name = 'referral_total_uses'
        """))
        column_exists = result.fetchone() is not None

        if table_exists and column_exists:
            return jsonify({
                'success': True,
                'message': 'La tabla y columna ya existen. Migración no necesaria.',
                'already_migrated': True
            }), 200

        logger.info(f"📝 Ejecutando migración de reward_codes y referral_total_uses")
        changes_made = []

        # Crear tabla reward_codes si no existe
        if not table_exists:
            db.session.execute(db.text("""
                CREATE TABLE reward_codes (
                    id SERIAL PRIMARY KEY,
                    code VARCHAR(6) UNIQUE NOT NULL,
                    client_id INTEGER NOT NULL REFERENCES clients(id),
                    pips_redeemed FLOAT NOT NULL DEFAULT 0.003,
                    is_used BOOLEAN DEFAULT FALSE,
                    used_at TIMESTAMP,
                    used_in_operation_id INTEGER REFERENCES operations(id),
                    created_at TIMESTAMP NOT NULL
                )
            """))
            changes_made.append('Tabla reward_codes creada')
            logger.info("✅ Tabla reward_codes creada")

        # Agregar columna referral_total_uses si no existe
        if not column_exists:
            db.session.execute(db.text(
                "ALTER TABLE clients ADD COLUMN referral_total_uses INTEGER DEFAULT 0"
            ))
            db.session.execute(db.text("""
                UPDATE clients
                SET referral_total_uses = 0
                WHERE referral_total_uses IS NULL
            """))
            changes_made.append('Columna referral_total_uses agregada')
            logger.info("✅ Columna referral_total_uses agregada")

        # Commit cambios
        db.session.commit()

        logger.info("✅ Migración de reward_codes completada exitosamente")

        return jsonify({
            'success': True,
            'message': 'Migración completada exitosamente',
            'changes_made': changes_made
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Error al ejecutar migración: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Error al ejecutar migración: {str(e)}'
        }), 500


@web_api_bp.route('/run-migration-referral-benefits', methods=['POST'])
@csrf.exempt
def run_migration_referral_benefits():
    """
    ENDPOINT TEMPORAL: Ejecutar migración para agregar columnas de beneficios por referidos
    Este endpoint se puede eliminar después de ejecutarlo una vez
    """
    try:
        # Verificar si las columnas ya existen
        result = db.session.execute(db.text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'clients'
            AND column_name IN ('referral_pips_earned', 'referral_pips_available', 'referral_completed_uses')
        """))
        existing_columns = [row[0] for row in result]

        if len(existing_columns) == 3:
            return jsonify({
                'success': True,
                'message': 'Las columnas ya existen. Migración no necesaria.',
                'already_migrated': True,
                'existing_columns': existing_columns
            }), 200

        logger.info(f"📝 Ejecutando migración de beneficios por referidos. Columnas existentes: {existing_columns}")

        # Agregar columnas si no existen
        columns_added = []

        if 'referral_pips_earned' not in existing_columns:
            db.session.execute(db.text(
                "ALTER TABLE clients ADD COLUMN referral_pips_earned FLOAT DEFAULT 0.0"
            ))
            columns_added.append('referral_pips_earned')
            logger.info("✅ Agregada columna: referral_pips_earned")

        if 'referral_pips_available' not in existing_columns:
            db.session.execute(db.text(
                "ALTER TABLE clients ADD COLUMN referral_pips_available FLOAT DEFAULT 0.0"
            ))
            columns_added.append('referral_pips_available')
            logger.info("✅ Agregada columna: referral_pips_available")

        if 'referral_completed_uses' not in existing_columns:
            db.session.execute(db.text(
                "ALTER TABLE clients ADD COLUMN referral_completed_uses INTEGER DEFAULT 0"
            ))
            columns_added.append('referral_completed_uses')
            logger.info("✅ Agregada columna: referral_completed_uses")

        # Actualizar valores NULL a defaults
        db.session.execute(db.text("""
            UPDATE clients
            SET referral_pips_earned = 0.0
            WHERE referral_pips_earned IS NULL
        """))
        db.session.execute(db.text("""
            UPDATE clients
            SET referral_pips_available = 0.0
            WHERE referral_pips_available IS NULL
        """))
        db.session.execute(db.text("""
            UPDATE clients
            SET referral_completed_uses = 0
            WHERE referral_completed_uses IS NULL
        """))

        # Commit cambios
        db.session.commit()

        logger.info("✅ Migración de beneficios por referidos completada exitosamente")

        return jsonify({
            'success': True,
            'message': 'Migración completada exitosamente',
            'columns_added': columns_added,
            'total_columns': len(columns_added)
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Error al ejecutar migración: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Error al ejecutar migración: {str(e)}'
        }), 500


@web_api_bp.route('/grant-pips-to-73733737', methods=['POST'])
@csrf.exempt
def grant_pips_to_73733737():
    """
    ENDPOINT TEMPORAL: Otorgar manualmente 15 pips al cliente 73733737 (dueño del código 2A5YQH)
    por la operación completada del cliente 15979715

    Este endpoint se puede eliminar después de ejecutarlo una vez
    """
    try:
        # Buscar el cliente con DNI 73733737 (dueño del código)
        referrer = Client.query.filter_by(dni='73733737').first()

        if not referrer:
            return jsonify({
                'success': False,
                'message': 'Cliente con DNI 73733737 no encontrado'
            }), 404

        # Buscar el cliente que usó el código (15979715)
        referred_client = Client.query.filter_by(dni='15979715').first()

        if not referred_client:
            return jsonify({
                'success': False,
                'message': 'Cliente con DNI 15979715 no encontrado'
            }), 404

        # Verificar que usó el código correcto
        if referred_client.used_referral_code != '2A5YQH':
            return jsonify({
                'success': False,
                'message': f'El cliente 15979715 no usó el código 2A5YQH (usó: {referred_client.used_referral_code})'
            }), 400

        # Buscar la operación completada
        completed_op = Operation.query.filter_by(
            client_id=referred_client.id,
            status='Completada'
        ).order_by(Operation.created_at.desc()).first()

        if not completed_op:
            return jsonify({
                'success': False,
                'message': 'No se encontró operación completada para el cliente 15979715'
            }), 404

        # Otorgar 15 pips (0.0015)
        PIPS_TO_GRANT = 0.0015

        # Guardar valores anteriores
        old_pips_earned = referrer.referral_pips_earned or 0.0
        old_pips_available = referrer.referral_pips_available or 0.0
        old_completed_uses = referrer.referral_completed_uses or 0

        # Otorgar beneficio
        referrer.referral_pips_earned = old_pips_earned + PIPS_TO_GRANT
        referrer.referral_pips_available = old_pips_available + PIPS_TO_GRANT
        referrer.referral_completed_uses = old_completed_uses + 1

        # Guardar cambios
        db.session.commit()

        logger.info(f"✅ Pips otorgados manualmente: {PIPS_TO_GRANT} pips al cliente {referrer.dni} por operación {completed_op.operation_id}")

        return jsonify({
            'success': True,
            'message': 'Pips otorgados exitosamente',
            'data': {
                'referrer_dni': referrer.dni,
                'referrer_name': referrer.full_name,
                'referrer_code': referrer.referral_code,
                'referred_client_dni': referred_client.dni,
                'referred_client_name': referred_client.full_name,
                'operation_id': completed_op.operation_id,
                'pips_granted': PIPS_TO_GRANT,
                'old_values': {
                    'pips_earned': old_pips_earned,
                    'pips_available': old_pips_available,
                    'completed_uses': old_completed_uses
                },
                'new_values': {
                    'pips_earned': float(referrer.referral_pips_earned),
                    'pips_available': float(referrer.referral_pips_available),
                    'completed_uses': referrer.referral_completed_uses
                }
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Error al otorgar pips manualmente: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Error al otorgar pips: {str(e)}'
        }), 500


@web_api_bp.route('/debug-client/<string:dni>', methods=['GET'])
@csrf.exempt
def debug_client_operations(dni):
    """Endpoint temporal de diagnóstico para verificar operaciones de un cliente"""
    try:
        client = Client.query.filter_by(dni=dni).first()
        if not client:
            return jsonify({'success': False, 'message': 'Cliente no encontrado'}), 404

        operations = Operation.query.filter_by(client_id=client.id).order_by(Operation.created_at.asc()).all()

        return jsonify({
            'success': True,
            'client': {
                'id': client.id,
                'dni': client.dni,
                'name': client.full_name,
                'used_referral_code': client.used_referral_code,
                'referred_by': client.referred_by
            },
            'operations': [
                {
                    'operation_id': op.operation_id,
                    'status': op.status,
                    'created_at': op.created_at.isoformat() if op.created_at else None,
                    'operation_type': op.operation_type
                }
                for op in operations
            ],
            'total_operations': len(operations)
        }), 200

    except Exception as e:
        logger.error(f"❌ Error en debug: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500
