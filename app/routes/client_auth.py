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
    Login temporal para clientes - Solo DNI

    IMPORTANTE: Este es un endpoint TEMPORAL para pruebas.
    En producción debe requerir contraseña.

    Request JSON:
    {
        "dni": "12345678"
    }

    Returns:
        JSON: {
            "success": true,
            "client": {...},
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

        logger.info(f"Login exitoso de cliente: {client.dni}")

        return jsonify({
            'success': True,
            'message': 'Login exitoso',
            'client': client.to_dict()
        }), 200

    except Exception as e:
        logger.error(f"Error en login de cliente: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error al iniciar sesión: {str(e)}'
        }), 500


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
        # TEMPORAL: Tipos de cambio hardcodeados
        # TODO: Obtener de configuración o base de datos controlada por Master
        return jsonify({
            'success': True,
            'rates': {
                'compra': 3.75,  # Tipo de cambio de compra (cliente vende USD)
                'venta': 3.77    # Tipo de cambio de venta (cliente compra USD)
            }
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

        # Emitir Socket.IO básico
        try:
            socketio.emit('operacion_actualizada', {
                'id': operation.id,
                'operation_id': operation.operation_id,
                'status': operation.status,
                'old_status': old_status,
                'client_deposits': operation.client_deposits,
                'client_payments': operation.client_payments
            }, namespace='/')
        except:
            pass  # No fallar si Socket.IO tiene problemas

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


@client_auth_bp.route('/health', methods=['GET'])
def health():
    """Health check para cliente auth"""
    return jsonify({
        'status': 'ok',
        'service': 'QoriCash Client Auth API',
        'version': '1.0.0-temporal'
    }), 200
