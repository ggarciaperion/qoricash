"""
Rutas de API para Plataforma Móvil (QoriCashApp)

Este blueprint maneja todos los endpoints necesarios para la aplicación móvil:
- Autenticación de clientes
- Auto-registro de clientes
- Gestión de operaciones desde el app
- Subida de comprobantes

Autenticación: Los clientes se autentican con DNI + contraseña
"""
from flask import Blueprint, request, jsonify
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db, csrf
from app.models.client import Client
from app.models.user import User
from app.models.operation import Operation
from app.services.client_service import ClientService
from app.services.operation_service import OperationService
from app.services.file_service import FileService
from app.services.email_service import EmailService
from app.services.notification_service import NotificationService
from app.socketio_events import emit_operation_event
from app.utils.validators import validate_dni, validate_email
from app.utils.formatters import now_peru
from app.utils.referral import generate_referral_code, is_valid_referral_code_format
import logging
import json
import secrets
import string

logger = logging.getLogger(__name__)

# Blueprint sin prefijo (se registrará con /api/client y /api/platform)
platform_bp = Blueprint('platform', __name__)

# Deshabilitar CSRF para endpoints de API móvil (usa tokens en headers)
csrf.exempt(platform_bp)


# ============================================
# AUTENTICACIÓN DE CLIENTES
# ============================================

# Login endpoint removed - now handled by client_auth_bp in client_auth.py
# This avoids route conflicts and uses the correct Client.check_password() method


@platform_bp.route('/api/client/me', methods=['POST'])
def get_client_me():
    """
    Obtener datos del cliente autenticado actual

    Body (JSON):
        - dni: DNI del cliente (para validar)

    Returns:
        - success: bool
        - client: dict
    """
    try:
        data = request.get_json() or {}
        dni = data.get('dni', '').strip()

        if not dni:
            return jsonify({
                'success': False,
                'message': 'DNI es requerido'
            }), 400

        # Buscar cliente
        client = ClientService.get_client_by_dni(dni)

        if not client:
            return jsonify({
                'success': False,
                'message': 'Cliente no encontrado'
            }), 404

        # Obtener datos del cliente (incluye has_complete_documents del modelo)
        client_data = client.to_dict(include_stats=True)
        # has_complete_documents ya viene desde to_dict() del modelo

        return jsonify({
            'success': True,
            'client': client_data
        }), 200

    except Exception as e:
        logger.error(f'Error en get_client_me: {str(e)}', exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Error al obtener datos del cliente: {str(e)}'
        }), 500


# ============================================
# REGISTRO DE CLIENTES
# ============================================

@platform_bp.route('/api/platform/register-client', methods=['POST'])
def register_client():
    """
    Auto-registro de cliente desde app móvil

    Form Data:
        - document_type: DNI | CE | RUC
        - dni: Número de documento
        - nombres, apellido_paterno, apellido_materno (para DNI/CE)
        - razon_social (para RUC)
        - email
        - phone
        - direccion, distrito, provincia, departamento (opcional)
        - bank_accounts: JSON string con cuentas bancarias
        - dni_front: File (opcional)
        - dni_back: File (opcional)

    Returns:
        - success: bool
        - message: str
        - client: dict
    """
    try:
        # Obtener datos del formulario
        data = request.form.to_dict()
        files = request.files

        logger.info(f'📱 [PLATFORM API] Registro de cliente desde app móvil')
        logger.info(f'Data recibida: {data.keys()}')
        logger.info(f'Files recibidos: {files.keys()}')

        # Validar campos requeridos
        required_fields = ['document_type', 'dni', 'email', 'phone']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'message': f'El campo {field} es requerido'
                }), 400

        dni = data.get('dni').strip()
        email = data.get('email').strip()
        document_type = data.get('document_type').strip()

        # Validar DNI
        if not validate_dni(dni, document_type):
            return jsonify({
                'success': False,
                'message': 'DNI inválido'
            }), 400

        # Validar email
        if not validate_email(email):
            return jsonify({
                'success': False,
                'message': 'Email inválido'
            }), 400

        # Verificar si ya existe DNI en clientes
        existing_client = ClientService.get_client_by_dni(dni)
        if existing_client:
            return jsonify({
                'success': False,
                'message': 'Ya existe un cliente con este DNI'
            }), 400

        # Subir archivos si vienen
        file_service = FileService()
        document_urls = {}

        if 'dni_front' in files:
            ok, msg, url = file_service.upload_dni_front(files['dni_front'], dni)
            if ok:
                document_urls['dni_front_url'] = url
            else:
                return jsonify({'success': False, 'message': f'Error al subir DNI frontal: {msg}'}), 400

        if 'dni_back' in files:
            ok, msg, url = file_service.upload_dni_back(files['dni_back'], dni)
            if ok:
                document_urls['dni_back_url'] = url
            else:
                return jsonify({'success': False, 'message': f'Error al subir DNI reverso: {msg}'}), 400

        # Parsear bank_accounts si viene como string JSON
        bank_accounts_raw = data.get('bank_accounts')
        if bank_accounts_raw:
            try:
                bank_accounts = json.loads(bank_accounts_raw)
            except (json.JSONDecodeError, TypeError, ValueError):
                return jsonify({
                    'success': False,
                    'message': 'Formato inválido para bank_accounts'
                }), 400
        else:
            bank_accounts = []

        # Crear cliente
        new_client = Client(
            document_type=document_type,
            dni=dni,
            email=email,
            phone=data.get('phone', ''),
            status='Inactivo',  # Por defecto inactivo hasta validación
            created_at=now_peru()
        )

        # Campos según tipo de documento
        if document_type == 'RUC':
            new_client.razon_social = data.get('razon_social', '')
            new_client.persona_contacto = data.get('persona_contacto', '')
        else:
            new_client.nombres = data.get('nombres', '')
            new_client.apellido_paterno = data.get('apellido_paterno', '')
            new_client.apellido_materno = data.get('apellido_materno', '')

        # Dirección
        new_client.direccion = data.get('direccion', '')
        new_client.distrito = data.get('distrito', '')
        new_client.provincia = data.get('provincia', '')
        new_client.departamento = data.get('departamento', '')

        # Documentos
        new_client.dni_front_url = document_urls.get('dni_front_url')
        new_client.dni_back_url = document_urls.get('dni_back_url')

        # Cuentas bancarias
        if bank_accounts:
            new_client.set_bank_accounts(bank_accounts)

        # Usuario "plataforma" como creador por defecto (solo para tracking interno)
        platform_user = User.query.filter_by(username='plataforma').first()
        if platform_user:
            new_client.created_by = platform_user.id

        # Configurar password del cliente (CRÍTICO para login en app móvil)
        # Los clientes se autentican contra la tabla clients, NO users
        # Contraseña inicial = DNI
        new_client.set_password(dni)

        # Guardar cliente (NO se crea registro en users - solo en clients)
        db.session.add(new_client)
        db.session.commit()

        logger.info(f'✅ Cliente registrado exitosamente: {dni} - {new_client.full_name}')

        # Enviar email de bienvenida
        try:
            EmailService.send_new_client_registration_email(new_client, platform_user)
        except Exception as e:
            logger.warning(f'No se pudo enviar email de bienvenida: {str(e)}')

        return jsonify({
            'success': True,
            'message': 'Registro exitoso. Tu cuenta será activada después de validar tus documentos.',
            'client': new_client.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        logger.error(f'❌ Error en register_client: {str(e)}', exc_info=True)
        return jsonify({
            'success': False,
            'message': 'Error al registrar cliente. Por favor intenta nuevamente.'
        }), 500


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

            # Verificar DNI duplicado en clientes
            existing_client = ClientService.get_client_by_dni(dni)
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

            # Verificar RUC duplicado en clientes
            existing_client = ClientService.get_client_by_dni(ruc)
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

        # Sistema de referidos: Generar código único para el nuevo cliente
        max_attempts = 10
        for _ in range(max_attempts):
            referral_code = generate_referral_code()
            existing_code = Client.query.filter_by(referral_code=referral_code).first()
            if not existing_code:
                new_client.referral_code = referral_code
                logger.info(f'✨ Código de referido generado: {referral_code}')
                break

        # Validar y aplicar código de referido si fue proporcionado
        used_code = data.get('referral_code', '').strip().upper()
        if used_code:
            if not is_valid_referral_code_format(used_code):
                return jsonify({
                    'success': False,
                    'message': 'Formato de código de referido inválido'
                }), 400

            # Buscar el cliente que tiene este código
            referrer = Client.query.filter_by(referral_code=used_code).first()
            if not referrer:
                return jsonify({
                    'success': False,
                    'message': 'Código de referido no existe'
                }), 400

            # Guardar el código usado y la referencia
            new_client.used_referral_code = used_code
            new_client.referred_by = referrer.id
            logger.info(f'🎁 Cliente usa código de referido: {used_code} (Referido por: {referrer.full_name})')

        # Usuario "plataforma" como creador (solo para tracking interno)
        platform_user = User.query.filter_by(username='plataforma').first()
        if platform_user:
            new_client.created_by = platform_user.id

        # Configurar password del cliente (CRÍTICO para login en app móvil)
        # Los clientes se autentican contra la tabla clients, NO users
        new_client.set_password(password)

        # Guardar cliente (NO se crea registro en users - solo en clients)
        db.session.add(new_client)
        db.session.commit()

        logger.info(f'✅ Cliente registrado desde app: {dni} - {new_client.full_name}')

        # Enviar email de bienvenida
        try:
            EmailService.send_new_client_registration_email(new_client, platform_user)
        except Exception as e:
            logger.warning(f'No se pudo enviar email de bienvenida: {str(e)}')

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


@platform_bp.route('/api/platform/get-client/<string:dni>', methods=['GET'])
@login_required
def get_client_by_dni(dni):
    """
    Obtener cliente por DNI (para verificar existencia)

    Returns:
        - success: bool
        - client: dict
    """
    try:
        client = ClientService.get_client_by_dni(dni)

        if not client:
            return jsonify({
                'success': False,
                'message': 'Cliente no encontrado'
            }), 404

        return jsonify({
            'success': True,
            'client': client.to_dict(include_stats=True)
        }), 200

    except Exception as e:
        logger.error(f'Error en get_client_by_dni: {str(e)}')
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# ============================================
# OPERACIONES
# ============================================

@platform_bp.route('/api/client/create-operation', methods=['POST'])
def create_operation():
    """
    Crear operación desde app móvil

    Body (JSON):
        - client_dni: DNI del cliente
        - operation_type: Compra | Venta
        - amount_usd: float
        - exchange_rate: float
        - source_account: str (número de cuenta origen)
        - destination_account: str (número de cuenta destino)
        - notes: str (opcional)

    Returns:
        - success: bool
        - message: str
        - operation: dict
    """
    try:
        data = request.get_json() or {}
        logger.info(f'📱 [CREATE OPERATION] Request data: {data}')

        client_dni = data.get('client_dni', '').strip()
        operation_type = data.get('operation_type', '').strip()
        amount_usd = data.get('amount_usd')
        exchange_rate = data.get('exchange_rate')
        source_account = data.get('source_account', '').strip()
        destination_account = data.get('destination_account', '').strip()
        notes = data.get('notes', '').strip()

        logger.info(f'📱 [CREATE OPERATION] Creando operación para cliente: {client_dni}')
        logger.info(f'📱 [CREATE OPERATION] Tipo: {operation_type}, Monto USD: {amount_usd}, TC: {exchange_rate}')

        # Validar campos requeridos
        if not all([client_dni, operation_type, amount_usd, exchange_rate, source_account, destination_account]):
            return jsonify({
                'success': False,
                'message': 'Todos los campos son requeridos'
            }), 400

        # Buscar cliente
        client = ClientService.get_client_by_dni(client_dni)
        if not client:
            return jsonify({
                'success': False,
                'message': 'Cliente no encontrado'
            }), 404

        # Verificar que el cliente esté activo
        if client.status != 'Activo':
            return jsonify({
                'success': False,
                'message': 'Tu cuenta debe estar activa para realizar operaciones. Contacta al administrador.'
            }), 403

        # Convertir a float
        try:
            amount_usd = float(amount_usd)
            exchange_rate = float(exchange_rate)
        except (ValueError, TypeError):
            return jsonify({
                'success': False,
                'message': 'Monto y tipo de cambio deben ser números válidos'
            }), 400

        # Validar montos
        if amount_usd <= 0:
            return jsonify({
                'success': False,
                'message': 'El monto debe ser mayor a 0'
            }), 400

        if exchange_rate <= 0:
            return jsonify({
                'success': False,
                'message': 'El tipo de cambio debe ser mayor a 0'
            }), 400

        # Validar tipo de operación
        if operation_type not in ['Compra', 'Venta']:
            return jsonify({
                'success': False,
                'message': 'Tipo de operación inválido'
            }), 400

        # Calcular amount_pen
        amount_pen = round(amount_usd * exchange_rate, 2)

        # Generar operation_id
        operation_id = Operation.generate_operation_id()

        # Crear operación
        # IMPORTANTE: user_id=None para operaciones del app móvil (clientes no tienen usuarios internos)
        # origen='app' identifica que la operación viene del aplicativo móvil
        new_operation = Operation(
            operation_id=operation_id,
            client_id=client.id,
            user_id=None,  # NULL para app móvil - solo operaciones manuales tienen user_id
            operation_type=operation_type,
            amount_usd=amount_usd,
            exchange_rate=exchange_rate,
            amount_pen=amount_pen,
            source_account=source_account,
            destination_account=destination_account,
            notes=notes,
            origen='app',  # Identificar origen: app móvil
            status='Pendiente',
            created_at=now_peru()
        )

        db.session.add(new_operation)
        logger.info(f'📝 [CREATE OPERATION] Operación agregada a sesión, haciendo commit...')
        db.session.commit()
        logger.info(f'✅ [CREATE OPERATION] Operación creada en BD: {operation_id} - {operation_type} ${amount_usd}')

        # Serializar operación
        logger.info(f'📦 [CREATE OPERATION] Serializando operación con include_relations=True...')
        try:
            operation_dict = new_operation.to_dict(include_relations=True)
            logger.info(f'✅ [CREATE OPERATION] Operación serializada correctamente')
        except Exception as e:
            logger.error(f'❌ [CREATE OPERATION] Error en to_dict: {str(e)}', exc_info=True)
            raise

        # Emitir evento Socket.IO
        logger.info(f'📡 [CREATE OPERATION] Emitiendo evento Socket.IO...')
        emit_operation_event('created', operation_dict)

        # Enviar email
        logger.info(f'📧 [CREATE OPERATION] Enviando email de notificación...')
        try:
            EmailService.send_new_operation_email(new_operation)
            logger.info(f'✅ [CREATE OPERATION] Email enviado correctamente')
        except Exception as e:
            logger.warning(f'⚠️ [CREATE OPERATION] No se pudo enviar email: {str(e)}')

        logger.info(f'🎉 [CREATE OPERATION] Preparando respuesta exitosa...')
        return jsonify({
            'success': True,
            'message': 'Operación creada exitosamente',
            'operation': operation_dict
        }), 201

    except Exception as e:
        db.session.rollback()
        logger.error(f'❌ [CREATE OPERATION] ERROR CRÍTICO: {str(e)}', exc_info=True)
        logger.error(f'❌ [CREATE OPERATION] Tipo de error: {type(e).__name__}')
        return jsonify({
            'success': False,
            'message': 'Error al crear operación. Por favor intenta nuevamente.'
        }), 500


@platform_bp.route('/api/client/my-operations/<string:dni>', methods=['GET'])
def get_my_operations(dni):
    """
    Obtener operaciones del cliente por DNI

    Returns:
        - success: bool
        - operations: list
    """
    try:
        logger.info(f'📋 [MY OPERATIONS] Obteniendo operaciones para DNI: {dni}')

        # Buscar cliente
        client = ClientService.get_client_by_dni(dni)

        if not client:
            logger.warning(f'⚠️ [MY OPERATIONS] Cliente no encontrado: {dni}')
            return jsonify({
                'success': False,
                'message': 'Cliente no encontrado'
            }), 404

        logger.info(f'✅ [MY OPERATIONS] Cliente encontrado: {client.id}')

        # Obtener operaciones
        operations = OperationService.get_operations_by_client(client.id)
        logger.info(f'📦 [MY OPERATIONS] Operaciones encontradas: {len(operations)}')

        # Convertir a dict
        operations_data = [op.to_dict(include_relations=True) for op in operations]
        logger.info(f'✅ [MY OPERATIONS] Retornando {len(operations_data)} operaciones')

        return jsonify({
            'success': True,
            'operations': operations_data
        }), 200

    except Exception as e:
        logger.error(f'Error en get_my_operations: {str(e)}', exc_info=True)
        return jsonify({
            'success': False,
            'message': 'Error al obtener operaciones.'
        }), 500


@platform_bp.route('/api/client/operation/<int:operation_id>', methods=['GET'])
def get_operation_detail(operation_id):
    """
    Obtener detalle de operación por ID

    Returns:
        - success: bool
        - operation: dict
    """
    try:
        operation = OperationService.get_operation_by_id(operation_id)

        if not operation:
            return jsonify({
                'success': False,
                'message': 'Operación no encontrada'
            }), 404

        return jsonify({
            'success': True,
            'operation': operation.to_dict(include_relations=True)
        }), 200

    except Exception as e:
        logger.error(f'Error en get_operation_detail: {str(e)}')
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@platform_bp.route('/api/client/upload-deposit-proof/<int:operation_id>', methods=['POST'])
def upload_deposit_proof(operation_id):
    """
    Subir comprobante de depósito del cliente

    Form Data:
        - deposit_index: int (índice del depósito, desde 0)
        - file: File (comprobante)
        - importe: float (monto del depósito)
        - codigo_operacion: str (código de operación bancaria)
        - cuenta_cargo: str (cuenta desde la que se hizo el depósito)

    Returns:
        - success: bool
        - message: str
    """
    try:
        # Obtener operación
        operation = OperationService.get_operation_by_id(operation_id)

        if not operation:
            return jsonify({
                'success': False,
                'message': 'Operación no encontrada'
            }), 404

        # Validar que la operación permita subir comprobantes
        if operation.status not in ['Pendiente', 'En proceso']:
            return jsonify({
                'success': False,
                'message': 'No se puede subir comprobante para esta operación'
            }), 400

        # Obtener archivo
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'message': 'No se envió ningún archivo'
            }), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'success': False,
                'message': 'No se seleccionó ningún archivo'
            }), 400

        # Obtener datos del depósito
        deposit_index = request.form.get('deposit_index', 0)
        importe = request.form.get('importe')
        codigo_operacion = request.form.get('codigo_operacion', '')
        # Si no viene cuenta_cargo (desde app móvil), usar la cuenta de origen de la operación
        cuenta_cargo = request.form.get('cuenta_cargo', '') or operation.source_account or ''

        try:
            deposit_index = int(deposit_index)
            importe = float(importe)
        except (ValueError, TypeError):
            return jsonify({
                'success': False,
                'message': 'Índice y monto deben ser números válidos'
            }), 400

        # Subir archivo
        file_service = FileService()
        ok, msg, url = file_service.upload_file(
            file,
            'comprobantes',
            f"{operation.operation_id}_deposit_{deposit_index}"
        )

        if not ok:
            return jsonify({
                'success': False,
                'message': f'Error al subir comprobante: {msg}'
            }), 400

        # Actualizar operación con comprobante
        deposits = operation.client_deposits or []

        # Actualizar o agregar depósito
        if deposit_index < len(deposits):
            deposits[deposit_index]['comprobante_url'] = url
            deposits[deposit_index]['importe'] = importe
            deposits[deposit_index]['codigo_operacion'] = codigo_operacion
            deposits[deposit_index]['cuenta_cargo'] = cuenta_cargo
        else:
            deposits.append({
                'importe': importe,
                'codigo_operacion': codigo_operacion,
                'cuenta_cargo': cuenta_cargo,
                'comprobante_url': url
            })

        operation.client_deposits = deposits

        # CRÍTICO: Cambiar estado a "En proceso" cuando se sube el primer comprobante
        # Este es el flujo principal desde el app móvil
        old_status = operation.status
        if operation.status == 'Pendiente':
            from app.utils.formatters import now_peru
            operation.status = 'En proceso'
            operation.in_process_since = now_peru()
            logger.info(f"✅ Estado cambiado de '{old_status}' a 'En proceso' para operación {operation.operation_id}")

        # Commit inmediato para persistir cambios (comprobante + estado)
        db.session.commit()

        # Auto-asignar operador si está "En proceso" y NO tiene operador
        if operation.status == 'En proceso' and not operation.assigned_operator_id:
            try:
                operator_id = OperationService.assign_operator_balanced()
                if operator_id:
                    operation.assigned_operator_id = operator_id
                    db.session.commit()
                    logger.info(f"✅ Operador {operator_id} auto-asignado a {operation.operation_id}")
            except Exception as e:
                logger.error(f"Error auto-asignando operador: {e}")

        # Auto-crear pago al cliente si no existe (para operaciones desde app móvil)
        if operation.origen == 'plataforma' and not operation.client_payments:
            from sqlalchemy.orm.attributes import flag_modified
            if operation.operation_type == 'Compra':
                total_pago = float(operation.amount_usd or 0) * float(operation.exchange_rate or 0)
            else:
                total_pago = float(operation.amount_usd or 0)

            operation.client_payments = [{'importe': total_pago, 'cuenta_destino': operation.destination_account}]
            flag_modified(operation, 'client_payments_json')
            db.session.commit()
            logger.info(f"✅ Pago auto-creado para operación {operation.operation_id}")

        logger.info(f'✅ Comprobante subido para operación {operation.operation_id}')

        # Emitir evento Socket.IO con el nuevo estado
        emit_operation_event('updated', operation.to_dict(include_relations=True))

        return jsonify({
            'success': True,
            'message': 'Comprobante subido exitosamente',
            'comprobante_url': url
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f'❌ Error en upload_deposit_proof: {str(e)}', exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Error al subir comprobante: {str(e)}'
        }), 500


@platform_bp.route('/api/client/cancel-expired-operation/<int:operation_id>', methods=['POST'])
def cancel_expired_operation(operation_id):
    """
    API: Cancelar operación expirada desde el cliente

    Cuando el timer local del cliente detecta expiración, llama a este endpoint
    para cancelar inmediatamente la operación, sin esperar al scheduler del backend.

    Args:
        operation_id: ID de la operación a cancelar
    """
    try:
        logger.info(f"⏱️ [CLIENT] Solicitud de cancelación por expiración: operación {operation_id}")

        # Buscar la operación
        operation = Operation.query.get(operation_id)

        if not operation:
            logger.warning(f"⚠️ [CLIENT] Operación {operation_id} no encontrada")
            return jsonify({
                'success': False,
                'message': 'Operación no encontrada'
            }), 404

        # Verificar que la operación esté en estado que permita cancelación
        if operation.status not in ['Pendiente', 'En proceso']:
            logger.info(f"ℹ️ [CLIENT] Operación {operation_id} ya está en estado {operation.status}")
            return jsonify({
                'success': True,
                'message': f'La operación ya está en estado {operation.status}',
                'operation': operation.to_dict(include_relations=True)
            })

        # Cancelar la operación
        reason = f"[Cliente - Expiración Local] Operación cancelada automáticamente por tiempo límite desde la aplicación móvil. Timestamp: {now_peru().strftime('%Y-%m-%d %H:%M:%S')}"

        operation.status = 'Cancelado'
        operation.notes = (operation.notes or '') + f"\n{reason}"
        operation.updated_at = now_peru()

        db.session.commit()

        logger.info(f"✅ [CLIENT] Operación {operation.operation_id} cancelada por expiración local")

        # Notificar cancelación via Socket.IO
        try:
            NotificationService.notify_operation_expired(operation)
            logger.info(f"📡 [CLIENT] Notificación Socket.IO enviada para operación {operation.operation_id}")
        except Exception as e:
            logger.error(f"⚠️ [CLIENT] Error enviando notificación Socket.IO: {e}")

        # Emitir evento de actualización
        emit_operation_event('canceled', operation.to_dict(include_relations=True))

        return jsonify({
            'success': True,
            'message': 'Operación cancelada exitosamente por expiración',
            'operation': operation.to_dict(include_relations=True)
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ [CLIENT] Error cancelando operación expirada {operation_id}: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Error al cancelar operación: {str(e)}'
        }), 500


@platform_bp.route('/api/web/add-bank-account', methods=['POST'])
def add_bank_account():
    """
    Agregar cuenta bancaria a cliente existente desde web

    Body (JSON):
        - dni: DNI del cliente
        - bank_name: Nombre del banco
        - account_number: Número de cuenta o CCI
        - account_type: 'Ahorro' | 'Corriente'
        - currency: 'S/' | '$'
        - origen: 'Lima' | 'Provincia' (opcional)

    Returns:
        - success: bool
        - message: str
        - bank_accounts: list (opcional)
    """
    try:
        data = request.get_json() or {}

        logger.info(f'🏦 [WEB API] Agregar cuenta bancaria')
        logger.info(f'Data recibida: {list(data.keys())}')

        # Validar campos requeridos
        required_fields = ['dni', 'bank_name', 'account_number', 'account_type', 'currency', 'origen']

        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'message': f'El campo {field} es requerido'
                }), 400

        dni = data.get('dni', '').strip()
        bank_name = data.get('bank_name', '').strip()
        account_number = data.get('account_number', '').strip()
        account_type = data.get('account_type', '').strip()
        currency = data.get('currency', '').strip()
        origen = data.get('origen', '').strip()

        # Buscar cliente
        client = Client.query.filter_by(dni=dni).first()
        if not client:
            return jsonify({
                'success': False,
                'message': 'Cliente no encontrado'
            }), 404

        # Validar tipo de cuenta
        if account_type not in ['Ahorro', 'Corriente']:
            return jsonify({
                'success': False,
                'message': 'Tipo de cuenta inválido (debe ser Ahorro o Corriente)'
            }), 400

        # Validar moneda
        if currency not in ['S/', '$']:
            return jsonify({
                'success': False,
                'message': 'Moneda inválida (debe ser S/ o $)'
            }), 400

        # Validar origen
        if origen not in ['Lima', 'Provincia']:
            return jsonify({
                'success': False,
                'message': 'Origen inválido (debe ser Lima o Provincia)'
            }), 400

        # Validar CCI para bancos que lo requieren
        if bank_name in ['BBVA', 'SCOTIABANK', 'OTROS']:
            if len(account_number) != 20:
                return jsonify({
                    'success': False,
                    'message': f'Para {bank_name} debes ingresar un CCI de exactamente 20 dígitos'
                }), 400
        else:
            # Validar número de cuenta normal (13-20 dígitos)
            if not account_number.isdigit() or len(account_number) < 13 or len(account_number) > 20:
                return jsonify({
                    'success': False,
                    'message': 'El número de cuenta debe tener entre 13 y 20 dígitos'
                }), 400

        # Obtener cuentas existentes
        existing_accounts = client.bank_accounts or []

        # Validar máximo de cuentas
        if len(existing_accounts) >= 6:
            return jsonify({
                'success': False,
                'message': 'Has alcanzado el máximo de 6 cuentas bancarias permitidas'
            }), 400

        # Validar cuenta duplicada
        account_key = f"{bank_name}_{account_type}_{account_number}_{currency}"
        for acc in existing_accounts:
            existing_key = f"{acc.get('bank_name')}_{acc.get('account_type')}_{acc.get('account_number')}_{acc.get('currency')}"
            if account_key == existing_key:
                return jsonify({
                    'success': False,
                    'message': 'Ya tienes registrada esta cuenta bancaria'
                }), 400

        # Agregar nueva cuenta
        new_account = {
            'origen': origen,
            'bank_name': bank_name,
            'account_type': account_type,
            'currency': currency,
            'account_number': account_number
        }

        existing_accounts.append(new_account)

        # Actualizar cliente
        client.set_bank_accounts(existing_accounts)
        db.session.commit()

        logger.info(f'✅ Cuenta bancaria agregada: {dni} - {bank_name} {currency}')

        return jsonify({
            'success': True,
            'message': 'Cuenta bancaria agregada exitosamente',
            'bank_accounts': client.bank_accounts
        }), 201

    except Exception as e:
        db.session.rollback()
        logger.error(f'❌ Error en add_bank_account: {str(e)}', exc_info=True)
        return jsonify({
            'success': False,
            'message': 'Error al agregar cuenta bancaria. Por favor intenta nuevamente.'
        }), 500


@platform_bp.route('/api/web/remove-bank-account', methods=['POST'])
def remove_bank_account():
    """
    Eliminar cuenta bancaria de cliente existente desde web

    Body (JSON):
        - dni: DNI del cliente
        - account_index: Índice de la cuenta a eliminar en el array

    Returns:
        - success: bool
        - message: str
        - bank_accounts: list (actualizada)
    """
    try:
        data = request.get_json() or {}

        logger.info(f'🗑️ [WEB API] Eliminar cuenta bancaria')
        logger.info(f'Data recibida: {list(data.keys())}')

        # Validar campos requeridos
        if not data.get('dni') or data.get('account_index') is None:
            return jsonify({
                'success': False,
                'message': 'DNI y account_index son requeridos'
            }), 400

        dni = data.get('dni', '').strip()
        account_index = data.get('account_index')

        # Validar que account_index sea un número
        try:
            account_index = int(account_index)
        except (ValueError, TypeError):
            return jsonify({
                'success': False,
                'message': 'El índice de cuenta debe ser un número válido'
            }), 400

        # Buscar cliente
        client = Client.query.filter_by(dni=dni).first()
        if not client:
            return jsonify({
                'success': False,
                'message': 'Cliente no encontrado'
            }), 404

        # Obtener cuentas existentes
        existing_accounts = client.bank_accounts or []

        # Validar que el índice exista
        if account_index < 0 or account_index >= len(existing_accounts):
            return jsonify({
                'success': False,
                'message': 'Índice de cuenta inválido'
            }), 400

        # Validar que queden al menos 2 cuentas después de eliminar
        if len(existing_accounts) <= 2:
            return jsonify({
                'success': False,
                'message': 'Debes mantener al menos 2 cuentas bancarias registradas (una en S/ y otra en $)'
            }), 400

        # Eliminar la cuenta
        removed_account = existing_accounts.pop(account_index)

        # Validar que después de eliminar aún haya al menos una cuenta en S/ y una en $
        currencies_remaining = [acc.get('currency') for acc in existing_accounts]
        if 'S/' not in currencies_remaining or '$' not in currencies_remaining:
            return jsonify({
                'success': False,
                'message': 'No puedes eliminar esta cuenta. Debes mantener al menos una cuenta en Soles (S/) y una en Dólares ($)'
            }), 400

        # Actualizar cliente
        client.set_bank_accounts(existing_accounts)
        db.session.commit()

        logger.info(f'✅ Cuenta bancaria eliminada: {dni} - {removed_account.get("bank_name")} {removed_account.get("currency")}')

        return jsonify({
            'success': True,
            'message': 'Cuenta bancaria eliminada exitosamente',
            'bank_accounts': client.bank_accounts
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f'❌ Error en remove_bank_account: {str(e)}', exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Error al eliminar cuenta: {str(e)}'
        }), 500

