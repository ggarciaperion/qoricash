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
from app.utils.referral import generate_referral_code, is_valid_referral_code_format
import logging

logger = logging.getLogger(__name__)

# Blueprint sin prefijo (se registrará con /api/client)
platform_bp = Blueprint('platform', __name__)

# Deshabilitar CSRF para endpoints de API móvil
csrf.exempt(platform_bp)


# Agregar headers CORS a todas las respuestas del blueprint
@platform_bp.after_request
def after_request(response):
    """Agregar headers CORS a todas las respuestas"""
    origin = request.headers.get('Origin')
    if origin:
        response.headers.add('Access-Control-Allow-Origin', origin)
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS')
        response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response


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


@platform_bp.route('/api/web/add-bank-account', methods=['POST', 'OPTIONS'])
def add_bank_account():
    # Manejar preflight OPTIONS request
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', request.headers.get('Origin', '*'))
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'POST,OPTIONS')
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        return response, 200
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
            'message': f'Error al agregar cuenta: {str(e)}'
        }), 500


@platform_bp.route('/api/client/my-operations/<string:dni>', methods=['GET'])
@login_required
def get_my_operations(dni):
    """
    Obtener operaciones del cliente por DNI

    Returns:
        - success: bool
        - operations: list
    """
    try:
        # Buscar cliente
        client = ClientService.get_client_by_dni(dni)

        if not client:
            return jsonify({
                'success': False,
                'message': 'Cliente no encontrado'
            }), 404

        # Obtener operaciones
        operations = OperationService.get_operations_by_client(client.id)

        # Convertir a dict
        operations_data = [op.to_dict(include_relations=True) for op in operations]

        return jsonify({
            'success': True,
            'operations': operations_data
        }), 200

    except Exception as e:
        logger.error(f'Error en get_my_operations: {str(e)}')
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@platform_bp.route('/api/client/operation/<int:operation_id>', methods=['GET'])
@login_required
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
@login_required
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
        cuenta_cargo = request.form.get('cuenta_cargo', '')

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
        db.session.commit()

        logger.info(f'✅ Comprobante subido para operación {operation.operation_id}')

        # Emitir evento Socket.IO
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
