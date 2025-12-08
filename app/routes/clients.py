"""
Rutas de Clientes para QoriCash Trading V2
"""
from flask import Blueprint, render_template, request, jsonify, send_file
from flask_login import login_required, current_user
from app.services.client_service import ClientService
from app.services.file_service import FileService
from app.services.notification_service import NotificationService
from app.utils.decorators import require_role
from app.utils.formatters import now_peru
from app.extensions import csrf
import io
import csv
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

clients_bp = Blueprint('clients', __name__, url_prefix='/clients')


@clients_bp.route('/')
@clients_bp.route('/list')
@login_required
@require_role('Master', 'Trader', 'Operador', 'Middle Office', 'Plataforma')
def list_clients():
    """
    Página de listado de clientes

    Roles permitidos: Master, Trader, Operador, Middle Office, Plataforma

    Filtrado:
    - Plataforma: Solo ve sus propios clientes (created_by = user_id)
    - Trader: Solo ve sus propios clientes (created_by = user_id)
    - Otros roles: Ven todos los clientes
    """
    from app.models.client import Client

    if current_user.role in ['Trader', 'Plataforma']:
        # Trader y Plataforma solo ven sus propios clientes
        clients = Client.query.filter_by(created_by=current_user.id).order_by(Client.created_at.desc()).all()
    else:
        # Otros roles ven todos los clientes
        clients = ClientService.get_all_clients()

    return render_template('clients/list.html',
                           user=current_user,
                           clients=clients)


@clients_bp.route('/api/list')
@login_required
@require_role('Master', 'Trader', 'Operador', 'Middle Office', 'Plataforma')
def api_list():
    """
    API: Listar clientes (JSON)

    Filtrado:
    - Plataforma/Trader: Solo sus propios clientes
    - Otros roles: Todos los clientes
    """
    from app.models.client import Client

    if current_user.role in ['Trader', 'Plataforma']:
        clients = Client.query.filter_by(created_by=current_user.id).order_by(Client.created_at.desc()).all()
    else:
        clients = ClientService.get_all_clients()

    return jsonify({
        'success': True,
        'clients': [client.to_dict() for client in clients]
    })


@clients_bp.route('/api/create', methods=['POST'])
@login_required
@require_role('Master', 'Trader', 'Plataforma')
def create_client():
    """
    API/Endpoint para crear nuevo cliente.
    Acepta JSON (application/json) o form-data multipart (desde modal), con archivos en request.files
    """
    files = request.files or {}
    # Si es JSON, request.get_json() devolverá dict; si viene form-data, usar request.form
    if request.is_json:
        data = request.get_json() or {}
    else:
        # request.form es ImmutableMultiDict; convertir a dict simple
        data = request.form.to_dict(flat=True)

    # Normalizar claves a strings y strip
    for k, v in list(data.items()):
        if isinstance(v, str):
            data[k] = v.strip()

    file_service = FileService()
    uploaded = {}

    # Subida de archivos desde el modal (si vienen): mapear a nombres de campo esperados en el servicio
    try:
        # DNI/CE
        if 'dni_front' in files:
            ok, msg, url = file_service.upload_file(files['dni_front'], 'dni', f"{data.get('dni')}_front")
            if not ok:
                return jsonify({'success': False, 'message': msg}), 400
            uploaded['dni_front_url'] = url
        if 'dni_back' in files:
            ok, msg, url = file_service.upload_file(files['dni_back'], 'dni', f"{data.get('dni')}_back")
            if not ok:
                return jsonify({'success': False, 'message': msg}), 400
            uploaded['dni_back_url'] = url

        # RUC / representante
        if 'dni_representante_front' in files:
            ok, msg, url = file_service.upload_file(files['dni_representante_front'], 'dni', f"{data.get('dni')}_rep_front")
            if not ok:
                return jsonify({'success': False, 'message': msg}), 400
            uploaded['dni_representante_front_url'] = url
        if 'dni_representante_back' in files:
            ok, msg, url = file_service.upload_file(files['dni_representante_back'], 'dni', f"{data.get('dni')}_rep_back")
            if not ok:
                return jsonify({'success': False, 'message': msg}), 400
            uploaded['dni_representante_back_url'] = url
        if 'ficha_ruc' in files:
            ok, msg, url = file_service.upload_file(files['ficha_ruc'], 'ruc', f"{data.get('dni')}_ruc")
            if not ok:
                return jsonify({'success': False, 'message': msg}), 400
            uploaded['ficha_ruc_url'] = url
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error en subida de archivos: {str(e)}'}), 500

    # Incorporar URLs subidas al payload
    data.update(uploaded)

    # Bank accounts: primer preferencia campo 'bank_accounts' (ya implementado en JS),
    # si no viene, recoger legacy indexed fields: bank_name1, bank_account_number1, etc.
    bank_accounts_raw = data.get('bank_accounts')
    if bank_accounts_raw:
        if isinstance(bank_accounts_raw, str):
            try:
                data['bank_accounts'] = json.loads(bank_accounts_raw)
            except Exception:
                return jsonify({'success': False, 'message': 'Formato inválido para bank_accounts'}), 400
    # Si request included legacy fields (bank_name1, bank_account_number1, etc.), el servicio los detectará

    success, message, client = ClientService.create_client(current_user=current_user, data=data, files=files)
    if success:
        try:
            NotificationService.notify_new_client(client, current_user)
        except Exception:
            # No bloquear por errores de notificación
            pass
        # Enviar correo electrónico de nuevo cliente
        try:
            from app.services.email_service import EmailService
            EmailService.send_new_client_registration_email(client, current_user)
        except Exception as e:
            # No bloquear por errores de email
            logger.warning(f'Error al enviar email de nuevo cliente: {str(e)}')
        return jsonify({'success': True, 'message': message, 'client': client.to_dict()}), 201
    else:
        return jsonify({'success': False, 'message': message}), 400


@clients_bp.route('/api/update/<int:client_id>', methods=['PUT', 'PATCH'])
@login_required
@require_role('Master', 'Trader', 'Operador')
def update_client(client_id):
    """
    API: Actualizar cliente existente
    """
    data = request.get_json() or {}
    success, message, client = ClientService.update_client(current_user=current_user, client_id=client_id, data=data)
    if success:
        return jsonify({'success': True, 'message': message, 'client': client.to_dict()})
    else:
        return jsonify({'success': False, 'message': message}), 400


@clients_bp.route('/api/change_status/<int:client_id>', methods=['PATCH'])
@login_required
@require_role('Master', 'Middle Office')
def change_status(client_id):
    """
    API: Cambiar estado del cliente (Activo/Inactivo)
    SOLO Master y Middle Office - Operador YA NO tiene este permiso
    """
    data = request.get_json() or {}
    new_status = data.get('status')

    if not new_status:
        return jsonify({'success': False, 'message': 'El estado es requerido'}), 400

    # Obtener estado anterior antes de cambiarlo
    client_before = ClientService.get_client_by_id(client_id)
    old_status = client_before.status if client_before else None

    success, message, client = ClientService.change_client_status(current_user=current_user, client_id=client_id, new_status=new_status)
    if success:
        # Si el cliente fue activado (de Inactivo a Activo), enviar email
        if old_status == 'Inactivo' and new_status == 'Activo':
            try:
                from app.services.email_service import EmailService
                # Enviar correo con el trader que creó al cliente
                trader = client.creator if hasattr(client, 'creator') and client.creator else current_user
                EmailService.send_client_activation_email(client, trader)
            except Exception as e:
                # No bloquear por errores de email
                logger.warning(f'Error al enviar email de cliente activado: {str(e)}')
        return jsonify({'success': True, 'message': message, 'client': client.to_dict()})
    else:
        return jsonify({'success': False, 'message': message}), 400


@clients_bp.route('/api/delete/<int:client_id>', methods=['DELETE'])
@login_required
@require_role('Master')
def delete_client(client_id):
    """
    API: Eliminar cliente
    """
    success, message = ClientService.delete_client(current_user=current_user, client_id=client_id)
    if success:
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'success': False, 'message': message}), 400


@clients_bp.route('/api/upload_documents/<int:client_id>', methods=['POST'])
@login_required
@require_role('Master', 'Trader', 'Plataforma')
def upload_documents(client_id):
    """
    API: Subir documentos del cliente
    """
    client = ClientService.get_client_by_id(client_id)
    if not client:
        return jsonify({'success': False, 'message': 'Cliente no encontrado'}), 404

    file_service = FileService()
    document_urls = {}

    try:
        if client.document_type == 'RUC':
            # Subir documentos RUC
            if 'dni_representante_front' in request.files:
                file = request.files['dni_representante_front']
                ok, msg, url = file_service.upload_file(file, 'dni', f"REP_{client.dni}")
                if ok:
                    document_urls['dni_representante_front_url'] = url
                else:
                    return jsonify({'success': False, 'message': f'Error DNI representante frontal: {msg}'}), 400

            if 'dni_representante_back' in request.files:
                file = request.files['dni_representante_back']
                ok, msg, url = file_service.upload_file(file, 'dni', f"REP_{client.dni}")
                if ok:
                    document_urls['dni_representante_back_url'] = url
                else:
                    return jsonify({'success': False, 'message': f'Error DNI representante reverso: {msg}'}), 400

            if 'ficha_ruc' in request.files:
                file = request.files['ficha_ruc']
                ok, msg, url = file_service.upload_file(file, 'ruc', f"RUC_{client.dni}")
                if ok:
                    document_urls['ficha_ruc_url'] = url
                else:
                    return jsonify({'success': False, 'message': f'Error Ficha RUC: {msg}'}), 400

        else:
            # Subir documentos DNI/CE
            if 'dni_front' in request.files:
                file = request.files['dni_front']
                ok, msg, url = file_service.upload_dni_front(file, client.dni)
                if ok:
                    document_urls['dni_front_url'] = url
                else:
                    return jsonify({'success': False, 'message': f'Error documento frontal: {msg}'}), 400

            if 'dni_back' in request.files:
                file = request.files['dni_back']
                ok, msg, url = file_service.upload_dni_back(file, client.dni)
                if ok:
                    document_urls['dni_back_url'] = url
                else:
                    return jsonify({'success': False, 'message': f'Error documento reverso: {msg}'}), 400

        # Actualizar cliente con URLs
        if document_urls:
            success, message, client = ClientService.update_client_documents(current_user=current_user, client_id=client_id, document_urls=document_urls)
            if success:
                return jsonify({'success': True, 'message': message, 'client': client.to_dict()})
            else:
                return jsonify({'success': False, 'message': message}), 400

        return jsonify({'success': False, 'message': 'No se seleccionó ningún archivo'}), 400

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error al subir documentos: {str(e)}'}), 500


@clients_bp.route('/api/<int:client_id>/stats')
@login_required
@require_role('Master', 'Trader', 'Operador', 'Middle Office')
def get_stats(client_id):
    """
    API: Obtener estadísticas de un cliente
    """
    stats = ClientService.get_client_stats(client_id)

    if stats:
        return jsonify({'success': True, 'stats': stats})
    else:
        return jsonify({'success': False, 'message': 'Cliente no encontrado'}), 404


@clients_bp.route('/api/search')
@login_required
@require_role('Master', 'Trader', 'Operador', 'Middle Office', 'Plataforma')
def search():
    """
    API: Buscar clientes

    Filtrado:
    - Plataforma/Trader: Solo sus propios clientes
    - Otros roles: Todos los clientes
    """
    from app.models.client import Client
    from sqlalchemy import or_

    query = request.args.get('q', '').strip()

    if not query or len(query) < 3:
        return jsonify({'success': False, 'message': 'La búsqueda debe tener al menos 3 caracteres'}), 400

    if current_user.role in ['Trader', 'Plataforma']:
        # Buscar solo en sus propios clientes
        search = f"%{query}%"
        clients = Client.query.filter(
            Client.created_by == current_user.id,
            or_(
                Client.dni.ilike(search),
                Client.email.ilike(search),
                Client.apellido_paterno.ilike(search),
                Client.apellido_materno.ilike(search),
                Client.nombres.ilike(search),
                Client.razon_social.ilike(search)
            )
        ).all()
    else:
        # Buscar en todos los clientes
        clients = ClientService.search_clients(query)

    return jsonify({'success': True, 'clients': [client.to_dict() for client in clients]})


@clients_bp.route('/api/export/csv')
@login_required
@require_role('Master')
def export_csv():
    """
    API: Exportar clientes a Excel con formato de tabla
    """
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter

        # Obtener todos los clientes con eager loading
        from sqlalchemy.orm import joinedload
        from app.models.client import Client
        clients = Client.query.options(joinedload(Client.creator)).order_by(Client.created_at.desc()).all()

        if not clients:
            return jsonify({'success': False, 'message': 'No hay clientes para exportar'}), 404

        # Crear workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Clientes"

        # Definir columnas en orden específico (ahora con más detalle)
        headers = [
            'ID',
            'Tipo Documento',
            'Número Documento',
            'Nombre Completo',
            'Persona Contacto',  # Para RUC
            'Email',
            'Teléfono',
            'Dirección',
            'Distrito',
            'Provincia',
            'Departamento',
            'Usuario Registro',
            'Fecha Registro',
            'Estado',
            'Total Operaciones',
            'Operaciones Completadas',
            'Cuenta Bancaria 1',
            'Cuenta Bancaria 2',
            'Cuenta Bancaria 3',
            'Cuenta Bancaria 4',
            'Cuenta Bancaria 5',
            'Cuenta Bancaria 6'
        ]

        # Escribir encabezados con formato
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num, value=header)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            cell.alignment = Alignment(horizontal="center", vertical="center")

        # Escribir datos
        for row_num, client in enumerate(clients, 2):
            col = 1
            ws.cell(row=row_num, column=col, value=client.id); col += 1
            ws.cell(row=row_num, column=col, value=client.document_type); col += 1
            ws.cell(row=row_num, column=col, value=client.dni); col += 1
            ws.cell(row=row_num, column=col, value=client.full_name or ''); col += 1

            # Persona de contacto (solo para RUC)
            ws.cell(row=row_num, column=col, value=client.persona_contacto if client.document_type == 'RUC' else ''); col += 1

            ws.cell(row=row_num, column=col, value=client.email); col += 1
            ws.cell(row=row_num, column=col, value=client.phone or ''); col += 1

            # Dirección separada en columnas
            ws.cell(row=row_num, column=col, value=client.direccion or ''); col += 1
            ws.cell(row=row_num, column=col, value=client.distrito or ''); col += 1
            ws.cell(row=row_num, column=col, value=client.provincia or ''); col += 1
            ws.cell(row=row_num, column=col, value=client.departamento or ''); col += 1

            ws.cell(row=row_num, column=col, value=client.creator.email if client.creator else 'N/A'); col += 1
            ws.cell(row=row_num, column=col, value=client.created_at.strftime('%d/%m/%Y %H:%M') if client.created_at else ''); col += 1
            ws.cell(row=row_num, column=col, value=client.status); col += 1
            ws.cell(row=row_num, column=col, value=client.get_total_operations()); col += 1
            ws.cell(row=row_num, column=col, value=client.get_completed_operations()); col += 1

            # Cuentas bancarias (hasta 6)
            bank_accounts = client.bank_accounts or []
            for i in range(6):
                if i < len(bank_accounts):
                    account = bank_accounts[i]
                    account_str = f"{account.get('bank_name', '')} | {account.get('account_type', '')} | {account.get('currency', '')} | {account.get('account_number', '')}"
                    ws.cell(row=row_num, column=col, value=account_str)
                else:
                    ws.cell(row=row_num, column=col, value='')
                col += 1

        # Ajustar ancho de columnas
        column_widths = {
            'A': 8,   # ID
            'B': 15,  # Tipo Documento
            'C': 18,  # Número Documento
            'D': 35,  # Nombre Completo
            'E': 30,  # Persona Contacto
            'F': 30,  # Email
            'G': 15,  # Teléfono
            'H': 30,  # Dirección
            'I': 20,  # Distrito
            'J': 20,  # Provincia
            'K': 20,  # Departamento
            'L': 30,  # Usuario Registro
            'M': 18,  # Fecha Registro
            'N': 12,  # Estado
            'O': 18,  # Total Ops
            'P': 20,  # Ops Completadas
            'Q': 50,  # Cuenta 1
            'R': 50,  # Cuenta 2
            'S': 50,  # Cuenta 3
            'T': 50,  # Cuenta 4
            'U': 50,  # Cuenta 5
            'V': 50   # Cuenta 6
        }

        for col, width in column_widths.items():
            ws.column_dimensions[col].width = width

        # Guardar en memoria
        excel_file = io.BytesIO()
        wb.save(excel_file)
        excel_file.seek(0)

        # Nombre del archivo con fecha
        filename = f"clientes_qoricash_{now_peru().strftime('%Y%m%d_%H%M%S')}.xlsx"

        return send_file(
            excel_file,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Error al exportar: {str(e)}'}), 500


@clients_bp.route('/api/<int:client_id>')
@login_required
@require_role('Master', 'Trader', 'Operador', 'Middle Office')
def get_client(client_id):
    """
    API: Obtener detalles de un cliente
    """
    client = ClientService.get_client_by_id(client_id)

    if not client:
        return jsonify({'success': False, 'message': 'Cliente no encontrado'}), 404

    return jsonify({'success': True, 'client': client.to_dict(include_stats=True)})


@clients_bp.route('/api/active')
@login_required
@require_role('Master', 'Trader', 'Operador', 'Middle Office', 'Plataforma')
def get_active():
    """
    API: Obtener solo clientes activos

    Filtrado:
    - Plataforma/Trader: Solo sus propios clientes activos
    - Otros roles: Todos los clientes activos
    """
    from app.models.client import Client

    if current_user.role in ['Trader', 'Plataforma']:
        clients = Client.query.filter_by(
            created_by=current_user.id,
            status='Activo'
        ).order_by(Client.created_at.desc()).all()
    else:
        clients = ClientService.get_active_clients()

    return jsonify({'success': True, 'clients': [client.to_dict() for client in clients]})


@clients_bp.route('/api/upload_validation_oc/<int:client_id>', methods=['POST'])
@login_required
@require_role('Master', 'Operador')
def upload_validation_oc(client_id):
    """
    API: Subir documento de validación del Oficial de Cumplimiento (OC)
    Solo para roles Master y Operador
    """
    client = ClientService.get_client_by_id(client_id)
    if not client:
        return jsonify({'success': False, 'message': 'Cliente no encontrado'}), 404

    if 'validation_oc_file' not in request.files:
        return jsonify({'success': False, 'message': 'No se envió ningún archivo'}), 400

    file = request.files['validation_oc_file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No se seleccionó ningún archivo'}), 400

    try:
        file_service = FileService()

        # Subir archivo a Cloudinary con folder específico para validación OC
        ok, msg, url = file_service.upload_file(file, 'validation_oc', f"OC_{client.dni}")

        if not ok:
            return jsonify({'success': False, 'message': f'Error al subir archivo: {msg}'}), 400

        # Actualizar cliente con URL de validación OC
        client.validation_oc_url = url
        from app.extensions import db
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Documento de validación OC subido correctamente',
            'validation_oc_url': url
        })

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error al subir documento: {str(e)}'}), 500


@clients_bp.route('/api/traders/active')
@login_required
@csrf.exempt
def get_active_traders():
    """
    API: Obtener lista de traders activos para reasignación
    Solo Master puede acceder
    """
    # Verificar rol manualmente
    if current_user.role != 'Master':
        return jsonify({'success': False, 'message': 'No autorizado'}), 403

    try:
        from app.models.user import User
        traders = User.query.filter_by(role='Trader', status='Activo').order_by(User.username).all()

        traders_list = [{
            'id': trader.id,
            'username': trader.username,
            'email': trader.email,
            'total_clients': len(ClientService.get_clients_by_trader(trader.id))
        } for trader in traders]

        return jsonify({
            'success': True,
            'traders': traders_list
        })
    except Exception as e:
        logger.error(f'Error al obtener traders: {str(e)}')
        return jsonify({'success': False, 'message': f'Error al obtener traders: {str(e)}'}), 500


@clients_bp.route('/api/reassign/<int:client_id>', methods=['POST'])
@login_required
@csrf.exempt
def reassign_client(client_id):
    """
    API: Reasignar un cliente individual a otro trader
    Solo Master puede reasignar
    """
    # Verificar rol manualmente
    if current_user.role != 'Master':
        return jsonify({'success': False, 'message': 'No autorizado. Solo Master puede reasignar clientes'}), 403

    try:
        data = request.get_json(force=True, silent=True)
        if not data:
            return jsonify({'success': False, 'message': 'No se recibieron datos válidos'}), 400

        new_trader_id = data.get('new_trader_id')

        if not new_trader_id:
            return jsonify({'success': False, 'message': 'El ID del nuevo trader es requerido'}), 400

        success, message, client = ClientService.reassign_client(
            current_user=current_user,
            client_id=client_id,
            new_trader_id=new_trader_id
        )

        if success:
            # Enviar notificaciones
            try:
                NotificationService.notify_client_reassignment(client, current_user, new_trader_id)
            except Exception:
                logger.warning('Error al enviar notificación de reasignación')

            return jsonify({
                'success': True,
                'message': message,
                'client': client.to_dict(include_stats=True)
            })
        else:
            return jsonify({'success': False, 'message': message}), 400

    except Exception as e:
        logger.error(f'Error en reasignación: {str(e)}')
        return jsonify({'success': False, 'message': f'Error al reasignar cliente: {str(e)}'}), 500


@clients_bp.route('/api/reassign/bulk', methods=['POST'])
@login_required
@csrf.exempt
def reassign_clients_bulk():
    """
    API: Reasignar múltiples clientes a un nuevo trader
    Solo Master puede reasignar
    """
    # Verificar rol manualmente para mejor control
    if current_user.role != 'Master':
        return jsonify({'success': False, 'message': 'No autorizado. Solo Master puede reasignar clientes'}), 403

    try:
        data = request.get_json(force=True, silent=True)
        if not data:
            return jsonify({'success': False, 'message': 'No se recibieron datos válidos'}), 400

        client_ids = data.get('client_ids', [])
        new_trader_id = data.get('new_trader_id')

        if not new_trader_id:
            return jsonify({'success': False, 'message': 'El ID del nuevo trader es requerido'}), 400

        if not client_ids or not isinstance(client_ids, list):
            return jsonify({'success': False, 'message': 'Debe proporcionar una lista de clientes'}), 400

        success, message, results = ClientService.reassign_clients_bulk(
            current_user=current_user,
            client_ids=client_ids,
            new_trader_id=new_trader_id
        )

        if success or results:
            # Enviar notificación al nuevo trader
            try:
                from app.models.user import User
                new_trader = User.query.get(new_trader_id)
                if new_trader and results:
                    NotificationService.notify_bulk_client_reassignment(
                        new_trader,
                        current_user,
                        len(results.get('success', []))
                    )
            except Exception:
                logger.warning('Error al enviar notificación de reasignación masiva')

            return jsonify({
                'success': success,
                'message': message,
                'results': results
            })
        else:
            return jsonify({'success': False, 'message': message}), 400

    except Exception as e:
        logger.error(f'Error en reasignación masiva: {str(e)}')
        return jsonify({'success': False, 'message': f'Error al reasignar clientes: {str(e)}'}), 500


@clients_bp.route('/detail/<int:client_id>')
@login_required
@require_role('Master', 'Trader', 'Operador', 'Middle Office')
def client_detail(client_id):
    """
    Página de detalle completo del cliente
    Muestra información, documentos, operaciones, perfil de riesgo
    """
    client = ClientService.get_client_by_id(client_id)

    if not client:
        return render_template('errors/404.html', message='Cliente no encontrado'), 404

    # Obtener perfil de riesgo si existe
    from app.models.compliance import ClientRiskProfile
    from app.models.operation import Operation
    risk_profile = ClientRiskProfile.query.filter_by(client_id=client_id).first()

    # Obtener últimas operaciones (corregido para SQLAlchemy 2.x)
    recent_operations = Operation.query.filter_by(client_id=client_id).order_by(Operation.created_at.desc()).limit(10).all()

    return render_template('clients/detail.html',
                         client=client,
                         risk_profile=risk_profile,
                         recent_operations=recent_operations)


@clients_bp.route('/api/trader/<int:trader_id>/clients')
@login_required
@csrf.exempt
def get_trader_clients(trader_id):
    """
    API: Obtener todos los clientes de un trader específico
    Solo Master puede acceder
    """
    # Verificar rol manualmente
    if current_user.role != 'Master':
        return jsonify({'success': False, 'message': 'No autorizado'}), 403

    try:
        clients = ClientService.get_clients_by_trader(trader_id)

        return jsonify({
            'success': True,
            'clients': [client.to_dict(include_stats=True) for client in clients],
            'total': len(clients)
        })
    except Exception as e:
        logger.error(f'Error al obtener clientes del trader: {str(e)}')
        return jsonify({'success': False, 'message': f'Error al obtener clientes: {str(e)}'}), 500