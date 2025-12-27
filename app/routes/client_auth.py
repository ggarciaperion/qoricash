"""
Rutas de Autenticación para Clientes (Mobile App)
TEMPORAL - Solo DNI sin contraseña para pruebas
"""
from flask import Blueprint, request, jsonify
from app.models.client import Client
from app.extensions import db, csrf
import logging

logger = logging.getLogger(__name__)

client_auth_bp = Blueprint('client_auth', __name__, url_prefix='/api/client')


@client_auth_bp.route('/login', methods=['POST'])
@csrf.exempt  # Eximir de CSRF para app móvil
def client_login():
    """
    Login de clientes con DNI y contraseña

    Request JSON:
    {
        "dni": "12345678",
        "password": "MiContraseña123!"  # Opcional: Si no se proporciona, usa login temporal (solo DNI)
    }

    Returns:
        JSON: {
            "success": true,
            "client": {...},
            "requires_password_change": true/false,
            "message": "Login exitoso"
        }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'message': 'No se recibieron datos'
            }), 400

        dni = data.get('dni', '').strip()
        password = data.get('password', '').strip()

        if not dni:
            return jsonify({
                'success': False,
                'message': 'DNI es requerido'
            }), 400

        # Buscar cliente por DNI
        client = Client.query.filter_by(dni=dni).first()

        if not client:
            return jsonify({
                'success': False,
                'message': 'Cliente no encontrado. Verifica el DNI.'
            }), 404

        # Verificar que el cliente esté activo
        if client.status != 'Activo':
            return jsonify({
                'success': False,
                'message': 'Cliente inactivo. Contacta al administrador.'
            }), 403

        # Si el cliente tiene contraseña configurada, validarla
        if client.password_hash:
            if not password:
                return jsonify({
                    'success': False,
                    'message': 'Contraseña es requerida'
                }), 400

            if not client.check_password(password):
                return jsonify({
                    'success': False,
                    'message': 'Contraseña incorrecta'
                }), 401

        logger.info(f"Login exitoso de cliente: {client.dni}")

        return jsonify({
            'success': True,
            'message': 'Login exitoso',
            'client': client.to_dict(),
            'requires_password_change': client.requires_password_change or False
        }), 200

    except Exception as e:
        logger.error(f"Error en login de cliente: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error al iniciar sesión: {str(e)}'
        }), 500


@client_auth_bp.route('/change-password', methods=['POST'])
@csrf.exempt
def change_password():
    """
    Cambiar contraseña del cliente (especialmente en primer login)

    Request JSON:
    {
        "dni": "12345678",
        "current_password": "temporal123",  # Opcional si requires_password_change=True
        "new_password": "MiNuevaContraseña123!"
    }

    Returns:
        JSON: {
            "success": true,
            "message": "Contraseña actualizada exitosamente"
        }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'message': 'No se recibieron datos'
            }), 400

        dni = data.get('dni', '').strip()
        current_password = data.get('current_password', '').strip()
        new_password = data.get('new_password', '').strip()

        # Validaciones básicas
        if not dni or not new_password:
            return jsonify({
                'success': False,
                'message': 'DNI y nueva contraseña son requeridos'
            }), 400

        # Validar fortaleza de nueva contraseña
        if len(new_password) < 8:
            return jsonify({
                'success': False,
                'message': 'La contraseña debe tener al menos 8 caracteres'
            }), 400

        # Buscar cliente
        client = Client.query.filter_by(dni=dni).first()

        if not client:
            return jsonify({
                'success': False,
                'message': 'Cliente no encontrado'
            }), 404

        # Si NO es primer login, validar contraseña actual
        if not client.requires_password_change:
            if not current_password:
                return jsonify({
                    'success': False,
                    'message': 'Contraseña actual es requerida'
                }), 400

            if not client.check_password(current_password):
                return jsonify({
                    'success': False,
                    'message': 'Contraseña actual incorrecta'
                }), 401
        else:
            # En primer login, validar contraseña temporal
            if current_password and not client.check_password(current_password):
                return jsonify({
                    'success': False,
                    'message': 'Contraseña temporal incorrecta'
                }), 401

        # Actualizar contraseña
        client.set_password(new_password)
        client.requires_password_change = False

        db.session.commit()

        logger.info(f"Contraseña actualizada exitosamente para cliente: {client.dni}")

        return jsonify({
            'success': True,
            'message': 'Contraseña actualizada exitosamente',
            'client': client.to_dict()
        }), 200

    except Exception as e:
        logger.error(f"Error al cambiar contraseña: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error al cambiar contraseña: {str(e)}'
        }), 500


@client_auth_bp.route('/register', methods=['POST'])
@csrf.exempt
def register_client():
    """
    Auto-registro de cliente - ULTRA SIMPLIFICADO
    """
    try:
        data = request.get_json()

        # Obtener datos
        dni = data.get('dni', '').strip()
        email = data.get('email', '').strip()
        nombres = data.get('nombres', '').strip()
        apellido_paterno = data.get('apellido_paterno', '').strip()
        apellido_materno = data.get('apellido_materno', '').strip()
        telefono = data.get('telefono', '').strip()

        # Validar
        if not all([dni, email, nombres, apellido_paterno, telefono]):
            return jsonify({'success': False, 'message': 'Faltan campos obligatorios'}), 400

        # Ver si ya existe
        if Client.query.filter_by(dni=dni).first():
            return jsonify({'success': False, 'message': 'DNI ya registrado'}), 400

        # Generar contraseña simple
        import secrets
        import string
        temp_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(10))

        # Crear cliente directo en SQL
        from sqlalchemy import text
        sql = text("""
            INSERT INTO clients
            (dni, document_type, email, nombres, apellido_paterno, apellido_materno, phone,
             status, password_hash, requires_password_change, created_at)
            VALUES
            (:dni, 'DNI', :email, :nombres, :apellido_paterno, :apellido_materno, :phone,
             'Activo', :password_hash, true, NOW())
            RETURNING id
        """)

        # Hash de contraseña
        from werkzeug.security import generate_password_hash
        pwd_hash = generate_password_hash(temp_password)

        # Ejecutar
        result = db.session.execute(sql, {
            'dni': dni,
            'email': email,
            'nombres': nombres,
            'apellido_paterno': apellido_paterno,
            'apellido_materno': apellido_materno,
            'phone': telefono,
            'password_hash': pwd_hash
        })

        client_id = result.fetchone()[0]
        db.session.commit()

        logger.info(f"Cliente registrado: {dni} (ID: {client_id})")

        return jsonify({
            'success': True,
            'message': f'¡Registro exitoso!\n\nTu contraseña temporal es:\n{temp_password}\n\nGuárdala para hacer login.',
            'password': temp_password,
            'client': {'dni': dni, 'email': email}
        }), 201

    except Exception as e:
        logger.error(f"Error registro: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@client_auth_bp.route('/verify/<dni>', methods=['GET'])
@csrf.exempt
def verify_client(dni):
    """
    Verificar si un cliente existe y está activo

    Args:
        dni: Número de documento del cliente

    Returns:
        JSON: {"success": true, "exists": true, "active": true}
    """
    try:
        client = Client.query.filter_by(dni=dni).first()

        if not client:
            return jsonify({
                'success': True,
                'exists': False,
                'active': False
            }), 200

        return jsonify({
            'success': True,
            'exists': True,
            'active': client.status == 'Activo',
            'client_name': client.get_full_name() if hasattr(client, 'get_full_name') else client.nombres or client.razon_social
        }), 200

    except Exception as e:
        logger.error(f"Error al verificar cliente: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error al verificar cliente: {str(e)}'
        }), 500


@client_auth_bp.route('/exchange-rates', methods=['GET'])
@csrf.exempt
def get_exchange_rates():
    """
    Obtener tipos de cambio actuales

    Returns:
        JSON: {
            "success": true,
            "rates": {
                "compra": 3.75,
                "venta": 3.77
            }
        }
    """
    try:
        from app.models.exchange_rate import ExchangeRate

        # Obtener tipos de cambio desde la base de datos
        rates = ExchangeRate.get_current_rates()

        return jsonify({
            'success': True,
            'rates': rates
        }), 200

    except Exception as e:
        logger.error(f"Error al obtener tipos de cambio: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error al obtener tipos de cambio: {str(e)}'
        }), 500


@client_auth_bp.route('/create-operation', methods=['POST'])
@csrf.exempt
def create_operation():
    """
    API: Crear operación desde app móvil (cliente)

    Request JSON:
    {
        "client_dni": "12345678",
        "operation_type": "Compra|Venta",
        "amount_usd": 1000.00,
        "exchange_rate": 3.75,
        "source_account": "19123456789012345678",
        "destination_account": "19187654321098765432",
        "notes": "Operación desde app móvil"
    }

    Returns:
        JSON: {"success": true, "operation": {...}}
    """
    try:
        from app.models.client import Client
        from app.models.user import User
        from app.services.operation_service import OperationService
        from app.services.notification_service import NotificationService

        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'message': 'No se recibieron datos'
            }), 400

        # Validar campos requeridos
        required_fields = ['client_dni', 'operation_type', 'amount_usd', 'exchange_rate']
        missing_fields = [field for field in required_fields if not data.get(field)]

        if missing_fields:
            return jsonify({
                'success': False,
                'message': f'Campos requeridos faltantes: {", ".join(missing_fields)}'
            }), 400

        # Buscar cliente por DNI
        client = Client.query.filter_by(dni=data['client_dni']).first()
        if not client:
            return jsonify({
                'success': False,
                'message': f'No existe un cliente con el documento {data["client_dni"]}'
            }), 404

        if client.status != 'Activo':
            return jsonify({
                'success': False,
                'message': 'Cliente inactivo. Contacta al administrador.'
            }), 403

        # Obtener el usuario que creó el cliente (puede ser Master, Trader, etc.)
        creator_user = User.query.get(client.created_by)
        if not creator_user:
            return jsonify({
                'success': False,
                'message': 'Error: No se encontró el usuario asociado al cliente'
            }), 500

        # Crear operación usando el servicio con el usuario creador del cliente
        success, message, operation = OperationService.create_operation(
            current_user=creator_user,
            client_id=client.id,
            operation_type=data['operation_type'],
            amount_usd=data['amount_usd'],
            exchange_rate=data['exchange_rate'],
            source_account=data.get('source_account'),
            destination_account=data.get('destination_account'),
            notes=data.get('notes', 'Operación desde app móvil'),
            origen='plataforma'
        )

        if not success:
            return jsonify({
                'success': False,
                'message': message
            }), 400

        # Enviar notificación en tiempo real
        try:
            NotificationService.notify_new_operation(operation)
            logger.info(f"📡 Notificación de nueva operación enviada: {operation.operation_id}")
        except Exception as e:
            logger.warning(f"Error enviando notificación: {str(e)}")

        logger.info(f"Operación creada desde app móvil: {operation.operation_id} para cliente {client.dni}")

        return jsonify({
            'success': True,
            'message': 'Operación creada exitosamente',
            'operation': operation.to_dict(include_relations=True)
        }), 201

    except Exception as e:
        logger.error(f"Error al crear operación desde app móvil: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'message': f'Error al crear operación: {str(e)}'
        }), 500


@client_auth_bp.route('/my-operations/<dni>', methods=['GET'])
@csrf.exempt
def get_client_operations(dni):
    """
    Obtener operaciones del cliente por DNI

    Query params:
        - status: filtrar por estado (Pendiente, En proceso, etc.)
        - limit: limitar resultados

    Returns:
        JSON: {"success": true, "operations": [...]}
    """
    try:
        from app.models.client import Client
        from app.models.operation import Operation

        # Buscar cliente
        client = Client.query.filter_by(dni=dni).first()
        if not client:
            return jsonify({
                'success': False,
                'message': 'Cliente no encontrado'
            }), 404

        # Obtener parámetros de filtro
        status_filter = request.args.get('status')
        limit = request.args.get('limit', type=int)

        # Query base
        query = Operation.query.filter_by(client_id=client.id).order_by(Operation.created_at.desc())

        # Aplicar filtros
        if status_filter:
            query = query.filter_by(status=status_filter)

        if limit:
            query = query.limit(limit)

        operations = query.all()

        return jsonify({
            'success': True,
            'operations': [op.to_dict(include_relations=True) for op in operations]
        }), 200

    except Exception as e:
        logger.error(f"Error al obtener operaciones del cliente: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error al obtener operaciones: {str(e)}'
        }), 500


@client_auth_bp.route('/operation/<int:operation_id>', methods=['GET'])
@csrf.exempt
def get_operation_detail(operation_id):
    """
    Obtener detalle de una operación por ID

    Args:
        operation_id: ID de la operación

    Returns:
        JSON: {"success": true, "operation": {...}}
    """
    try:
        from app.models.operation import Operation

        operation = Operation.query.get(operation_id)
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
        logger.error(f"Error al obtener detalle de operación: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error al obtener operación: {str(e)}'
        }), 500


@client_auth_bp.route('/upload-deposit-proof/<int:operation_id>', methods=['POST'])
@csrf.exempt
def upload_deposit_proof(operation_id):
    """
    Subir comprobante de abono desde app móvil - VERSIÓN SIMPLIFICADA
    """
    try:
        from app.models.operation import Operation
        from app.services.file_service import FileService
        from sqlalchemy.orm.attributes import flag_modified
        from app.extensions import socketio

        operation = Operation.query.get(operation_id)
        if not operation:
            return jsonify({'success': False, 'message': 'Operación no encontrada'}), 404

        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'No se envió ningún archivo'}), 400

        # Obtener datos del formulario
        file = request.files['file']
        deposit_index = request.form.get('deposit_index', 0, type=int)
        importe = request.form.get('importe', type=float)
        codigo_operacion = request.form.get('codigo_operacion', type=str)

        # Subir archivo
        file_service = FileService()
        success, message, url = file_service.upload_file(
            file, 'deposits', f"{operation.operation_id}_deposit_{deposit_index}"
        )

        if not success:
            return jsonify({'success': False, 'message': message}), 400

        # Actualizar depósitos
        deposits = operation.client_deposits or []
        while len(deposits) <= deposit_index:
            deposits.append({})

        deposits[deposit_index]['comprobante_url'] = url
        if importe is not None:
            deposits[deposit_index]['importe'] = float(importe)
        if codigo_operacion:
            deposits[deposit_index]['codigo_operacion'] = str(codigo_operacion)
        if operation.source_account:
            deposits[deposit_index]['cuenta_cargo'] = operation.source_account

        operation.client_deposits = deposits
        flag_modified(operation, 'client_deposits_json')

        # Cambiar estado a "En proceso"
        old_status = operation.status
        if operation.status == 'Pendiente':
            operation.status = 'En proceso'

        # Auto-asignar operador si está "En proceso" y NO tiene operador
        if operation.status == 'En proceso' and not operation.assigned_operator_id:
            try:
                from app.services.operation_service import OperationService
                from app.models.user import User

                operator_id = OperationService.assign_operator_balanced()
                if operator_id:
                    operation.assigned_operator_id = operator_id
                    logger.info(f"✅ Operador {operator_id} auto-asignado a {operation.operation_id}")

                    # Notificar al operador específicamente
                    try:
                        operator_user = User.query.get(operator_id)
                        if operator_user:
                            from app.services.notification_service import NotificationService
                            NotificationService.notify_operation_assigned(operation, operator_user)
                            logger.info(f"📡 Notificación enviada a operador {operator_user.username}")
                    except Exception as notify_error:
                        logger.error(f"Error notificando al operador: {notify_error}")
            except Exception as e:
                logger.error(f"Error auto-asignando operador: {e}")

        # Auto-crear pago si no existe
        if operation.origen == 'plataforma' and not operation.client_payments:
            if operation.operation_type == 'Compra':
                total_pago = float(operation.amount_usd or 0) * float(operation.exchange_rate or 0)
            else:
                total_pago = float(operation.amount_usd or 0)

            operation.client_payments = [{'importe': total_pago, 'cuenta_destino': operation.destination_account}]
            flag_modified(operation, 'client_payments_json')

        # Guardar cambios
        db.session.commit()

        # Emitir Socket.IO con datos completos usando NotificationService
        try:
            from app.services.notification_service import NotificationService
            NotificationService.notify_operation_updated(operation, old_status)
            logger.info(f"📡 NotificationService.notify_operation_updated llamado para {operation.operation_id}")
        except Exception as e:
            logger.warning(f"⚠️ Error en NotificationService: {e}")

        return jsonify({
            'success': True,
            'message': 'Comprobante subido exitosamente',
            'url': url
        }), 200

    except Exception as e:
        logger.error(f"Error al subir comprobante: {str(e)}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


@client_auth_bp.route('/cancel-operation/<int:operation_id>', methods=['POST'])
@csrf.exempt
def cancel_operation(operation_id):
    """
    Cancelar operación desde el cliente con motivo

    Request JSON:
    {
        "cancellation_reason": "Motivo de la cancelación"
    }
    """
    try:
        from app.models.operation import Operation
        from app.services.notification_service import NotificationService
        from datetime import datetime

        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'message': 'No se recibieron datos'
            }), 400

        cancellation_reason = data.get('cancellation_reason', '').strip()

        if not cancellation_reason:
            return jsonify({
                'success': False,
                'message': 'El motivo de cancelación es requerido'
            }), 400

        # Buscar la operación
        operation = Operation.query.get(operation_id)

        if not operation:
            return jsonify({
                'success': False,
                'message': 'Operación no encontrada'
            }), 404

        # Validar que la operación no esté en proceso o completada
        if operation.status == 'En proceso':
            return jsonify({
                'success': False,
                'message': 'No se puede cancelar una operación que está siendo procesada'
            }), 400

        if operation.status in ['Completada', 'Cancelado', 'Expirada']:
            return jsonify({
                'success': False,
                'message': f'No se puede cancelar una operación {operation.status.lower()}'
            }), 400

        # Cancelar la operación
        operation.status = 'Cancelado'
        operation.cancellation_reason = cancellation_reason
        operation.updated_at = datetime.utcnow()

        db.session.commit()

        logger.info(f"Operación {operation.operation_id} cancelada por el cliente. Motivo: {cancellation_reason}")

        # Notificar via Socket.IO
        NotificationService.notify_operation_canceled(operation, cancellation_reason)

        return jsonify({
            'success': True,
            'message': 'Operación cancelada exitosamente',
            'operation': operation.to_dict()
        }), 200

    except Exception as e:
        logger.error(f"Error al cancelar operación: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error al cancelar operación: {str(e)}'
        }), 500


@client_auth_bp.route('/add-bank-account/<string:client_dni>', methods=['POST'])
@csrf.exempt
def add_bank_account(client_dni):
    """
    Agregar cuenta bancaria a un cliente desde el app

    Request JSON:
    {
        "origen": "Lima" | "Provincia",
        "bank_name": "BCP" | "INTERBANK" | "PICHINCHA" | "BANBIF" | otro,
        "account_type": "Ahorro" | "Corriente",
        "currency": "S/" | "$",
        "account_number": "número de cuenta",
        "cci": "número CCI de 20 dígitos" (solo si no es BCP, INTERBANK, PICHINCHA, BANBIF)
    }
    """
    try:
        from app.models.client import Client
        from sqlalchemy.orm.attributes import flag_modified

        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'message': 'No se recibieron datos'
            }), 400

        # Validar campos requeridos
        origen = data.get('origen', '').strip()
        bank_name = data.get('bank_name', '').strip()
        account_type = data.get('account_type', '').strip()
        currency = data.get('currency', '').strip()
        account_number = data.get('account_number', '').strip()
        cci = data.get('cci', '').strip() if data.get('cci') else ''

        if not all([origen, bank_name, account_type, currency, account_number]):
            return jsonify({
                'success': False,
                'message': 'Todos los campos son requeridos'
            }), 400

        # Validaciones específicas
        if origen not in ['Lima', 'Provincia']:
            return jsonify({
                'success': False,
                'message': 'Origen debe ser Lima o Provincia'
            }), 400

        if account_type not in ['Ahorro', 'Corriente']:
            return jsonify({
                'success': False,
                'message': 'Tipo de cuenta debe ser Ahorro o Corriente'
            }), 400

        if currency not in ['S/', '$']:
            return jsonify({
                'success': False,
                'message': 'Moneda debe ser S/ o $'
            }), 400

        # Validar provincia solo BCP o INTERBANK
        if origen == 'Provincia' and bank_name not in ['BCP', 'INTERBANK']:
            return jsonify({
                'success': False,
                'message': 'Para cuentas de provincia solo operamos con BCP e INTERBANK'
            }), 400

        # Validar CCI para bancos que no sean los principales
        main_banks = ['BCP', 'INTERBANK', 'PICHINCHA', 'BANBIF']
        if bank_name not in main_banks:
            if not cci or len(cci) != 20:
                return jsonify({
                    'success': False,
                    'message': 'Para este banco debe ingresar el CCI de 20 dígitos'
                }), 400
            # Guardar el CCI como número de cuenta
            account_number = cci

        # Buscar cliente
        client = Client.query.filter_by(dni=client_dni).first()

        if not client:
            return jsonify({
                'success': False,
                'message': 'Cliente no encontrado'
            }), 404

        # Obtener cuentas existentes
        current_accounts = client.bank_accounts or []

        # Verificar que no sea duplicado
        for acc in current_accounts:
            if (acc.get('bank_name') == bank_name and
                acc.get('account_type') == account_type and
                acc.get('account_number') == account_number and
                acc.get('currency') == currency):
                return jsonify({
                    'success': False,
                    'message': 'Esta cuenta bancaria ya está registrada'
                }), 400

        # Verificar límite de 6 cuentas
        if len(current_accounts) >= 6:
            return jsonify({
                'success': False,
                'message': 'Máximo 6 cuentas bancarias permitidas'
            }), 400

        # Agregar nueva cuenta
        new_account = {
            'origen': origen,
            'bank_name': bank_name,
            'account_type': account_type,
            'currency': currency,
            'account_number': account_number
        }

        current_accounts.append(new_account)

        # Actualizar cliente
        client.set_bank_accounts(current_accounts)
        flag_modified(client, 'bank_accounts_json')

        db.session.commit()

        logger.info(f"Cuenta bancaria agregada para cliente {client_dni}: {bank_name} - {account_number}")

        return jsonify({
            'success': True,
            'message': 'Cuenta bancaria agregada exitosamente',
            'client': client.to_dict()
        }), 200

    except Exception as e:
        logger.error(f"Error al agregar cuenta bancaria: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error al agregar cuenta bancaria: {str(e)}'
        }), 500


@client_auth_bp.route('/delete-bank-account/<string:client_dni>/<int:account_index>', methods=['DELETE'])
@csrf.exempt
def delete_bank_account(client_dni, account_index):
    """
    Eliminar cuenta bancaria de un cliente desde el app

    Parameters:
    - client_dni: DNI del cliente
    - account_index: Índice de la cuenta bancaria a eliminar (0-based)
    """
    try:
        from app.models.client import Client
        from sqlalchemy.orm.attributes import flag_modified

        logger.info(f"[DELETE BANK ACCOUNT] Inicio - DNI: {client_dni}, Index: {account_index}")

        # Buscar cliente
        client = Client.query.filter_by(dni=client_dni).first()

        if not client:
            logger.warning(f"[DELETE BANK ACCOUNT] Cliente no encontrado: {client_dni}")
            return jsonify({
                'success': False,
                'message': 'Cliente no encontrado'
            }), 404

        # Obtener cuentas existentes
        current_accounts = client.bank_accounts or []
        logger.info(f"[DELETE BANK ACCOUNT] Cuentas actuales: {len(current_accounts)}")

        if not current_accounts:
            logger.warning(f"[DELETE BANK ACCOUNT] No hay cuentas bancarias registradas")
            return jsonify({
                'success': False,
                'message': 'No hay cuentas bancarias registradas'
            }), 404

        # Verificar que el índice sea válido
        if account_index < 0 or account_index >= len(current_accounts):
            logger.warning(f"[DELETE BANK ACCOUNT] Índice inválido: {account_index} (total: {len(current_accounts)})")
            return jsonify({
                'success': False,
                'message': f'Índice de cuenta inválido: {account_index}'
            }), 404

        logger.info(f"[DELETE BANK ACCOUNT] Eliminando cuenta en índice {account_index}")

        # Eliminar la cuenta por índice
        deleted_account = current_accounts.pop(account_index)
        logger.info(f"[DELETE BANK ACCOUNT] Cuenta eliminada: {deleted_account}")

        # Actualizar cliente
        client.set_bank_accounts(current_accounts)
        flag_modified(client, 'bank_accounts_json')

        db.session.commit()
        logger.info(f"[DELETE BANK ACCOUNT] Base de datos actualizada exitosamente")

        logger.info(f"Cuenta bancaria eliminada para cliente {client_dni}: {deleted_account.get('bank_name')} - {deleted_account.get('account_number')}")

        return jsonify({
            'success': True,
            'message': 'Cuenta bancaria eliminada exitosamente',
            'client': client.to_dict()
        }), 200

    except Exception as e:
        logger.error(f"[DELETE BANK ACCOUNT] Error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error al eliminar cuenta bancaria: {str(e)}'
        }), 500


@client_auth_bp.route('/health', methods=['GET'])
def health():
    """Health check para cliente auth"""
    return jsonify({
        'status': 'ok',
        'service': 'QoriCash Client Auth API',
        'version': '1.0.0-temporal'
    }), 200
