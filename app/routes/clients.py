"""
Rutas de Clientes para QoriCash Trading V2
"""
from flask import Blueprint, render_template, request, jsonify, send_file
from flask_login import login_required, current_user
from app.services.client_service import ClientService
from app.services.file_service import FileService
from app.services.notification_service import NotificationService
from app.utils.decorators import require_role
import io
import csv
from datetime import datetime
import json

clients_bp = Blueprint('clients', __name__, url_prefix='/clients')


@clients_bp.route('/')
@clients_bp.route('/list')
@login_required
@require_role('Master', 'Trader', 'Operador')
def list_clients():
    """
    Página de listado de clientes

    Roles permitidos: Master, Trader, Operador
    """
    clients = ClientService.get_all_clients()
    return render_template('clients/list.html',
                           user=current_user,
                           clients=clients)


@clients_bp.route('/api/list')
@login_required
@require_role('Master', 'Trader', 'Operador')
def api_list():
    """
    API: Listar clientes (JSON)
    """
    clients = ClientService.get_all_clients()
    return jsonify({
        'success': True,
        'clients': [client.to_dict() for client in clients]
    })


@clients_bp.route('/api/create', methods=['POST'])
@login_required
@require_role('Master', 'Trader')
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
@require_role('Master', 'Operador')
def change_status(client_id):
    """
    API: Cambiar estado del cliente (Activo/Inactivo)
    """
    data = request.get_json() or {}
    new_status = data.get('status')

    if not new_status:
        return jsonify({'success': False, 'message': 'El estado es requerido'}), 400

    success, message, client = ClientService.change_client_status(current_user=current_user, client_id=client_id, new_status=new_status)
    if success:
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
@require_role('Master', 'Trader')
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
@require_role('Master', 'Trader', 'Operador')
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
@require_role('Master', 'Trader', 'Operador')
def search():
    """
    API: Buscar clientes
    """
    query = request.args.get('q', '').strip()

    if not query or len(query) < 3:
        return jsonify({'success': False, 'message': 'La búsqueda debe tener al menos 3 caracteres'}), 400

    clients = ClientService.search_clients(query)

    return jsonify({'success': True, 'clients': [client.to_dict() for client in clients]})


@clients_bp.route('/api/export/csv')
@login_required
@require_role('Master')
def export_csv():
    """
    API: Exportar clientes a CSV
    """
    try:
        clients_data = ClientService.export_clients_to_dict()

        if not clients_data:
            return jsonify({'success': False, 'message': 'No hay clientes para exportar'}), 404

        # Crear CSV en memoria
        output = io.StringIO()

        # Obtener headers del primer cliente
        headers = list(clients_data[0].keys())

        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        writer.writerows(clients_data)

        # Convertir a bytes
        output.seek(0)
        csv_bytes = io.BytesIO(output.getvalue().encode('utf-8-sig'))  # UTF-8 con BOM para Excel

        # Nombre del archivo con fecha
        filename = f"clientes_qoricash_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        return send_file(
            csv_bytes,
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error al exportar: {str(e)}'}), 500


@clients_bp.route('/api/<int:client_id>')
@login_required
@require_role('Master', 'Trader', 'Operador')
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
@require_role('Master', 'Trader', 'Operador')
def get_active():
    """
    API: Obtener solo clientes activos
    """
    clients = ClientService.get_active_clients()
    return jsonify({'success': True, 'clients': [client.to_dict() for client in clients]})