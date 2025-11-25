"""
Servicio de Cliente para QoriCash Trading V2

Maneja toda la lógica de negocio relacionada con clientes.
"""
from flask import current_app
from sqlalchemy import or_
from app.extensions import db, socketio
from app.models.client import Client
from app.models.audit_log import AuditLog
from app.utils.validators import validate_dni, validate_email, validate_phone
from app.utils.formatters import now_peru
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


class ClientService:
    """Servicio de gestión de clientes"""

    @staticmethod
    def get_all_clients():
        """
        Obtener todos los clientes

        ACTUALIZADO: Incluye eager loading de la relación 'creator' para mostrar
        el usuario que registró al cliente

        Returns:
            list: Lista de clientes ordenados por fecha de creación
        """
        from sqlalchemy.orm import joinedload
        return Client.query.options(joinedload(Client.creator)).order_by(Client.created_at.desc()).all()

    @staticmethod
    def get_active_clients():
        """
        Obtener solo clientes activos

        Returns:
            list: Lista de clientes activos
        """
        return Client.query.filter_by(status='Activo').order_by(Client.created_at.desc()).all()

    @staticmethod
    def get_client_by_id(client_id):
        """
        Obtener cliente por ID

        Args:
            client_id: ID del cliente

        Returns:
            Client: Cliente encontrado o None
        """
        return Client.query.get(client_id)

    @staticmethod
    def get_client_by_dni(dni):
        """
        Obtener cliente por DNI

        Args:
            dni: DNI del cliente

        Returns:
            Client: Cliente encontrado o None
        """
        return Client.query.filter_by(dni=dni).first()

    @staticmethod
    def get_client_by_email(email):
        """
        Obtener cliente por email

        Args:
            email: Email del cliente

        Returns:
            Client: Cliente encontrado o None
        """
        return Client.query.filter_by(email=email).first()

    @staticmethod
    def _build_bank_accounts_from_legacy(data):
        """
        Construye una lista de cuentas bancarias a partir de campos legacy
        (bank_name1, bank_account_number1, origin1, currency1, account_type1, ...)
        Soporta hasta 4 cuentas legacy; idempotente.
        """
        legacy_accounts = []
        for i in (1, 2, 3, 4):
            bank = data.get(f'bank_name{i}') or data.get(f'bank{i}') or None
            acc = data.get(f'bank_account_number{i}') or data.get(f'bank_account{i}') or data.get(f'bank_account_{i}') or None
            if bank or acc:
                legacy_accounts.append({
                    'origen': data.get(f'origen{i}') or data.get('origen') or data.get('bank_origin') or '',
                    'bank_name': (bank or '').strip(),
                    'account_type': (data.get(f'account_type{i}') or data.get('account_type') or '').strip(),
                    'currency': (data.get(f'currency{i}') or data.get('currency') or '').strip(),
                    'account_number': (acc or '').strip()
                })
        return legacy_accounts

    @staticmethod
    def create_client(current_user, data, files=None):
        """
        Crear nuevo cliente

        Args:
            current_user: Usuario que crea el cliente
            data: Diccionario con datos del cliente (puede venir de form o JSON)
            files: Diccionario con archivos subidos (opcional)

        Returns:
            tuple: (success: bool, message: str, client: Client|None)
        """
        # Inicializar client para evitar errores de scope
        client = None

        try:
            # --- Permisos básicos ---
            if not current_user:
                return False, 'Usuario no autenticado', None
            # Validar tipo de documento
            document_type = (data.get('document_type') or '').strip()
            if document_type not in ['DNI', 'CE', 'RUC']:
                return False, 'Tipo de documento inválido', None

            # Número de documento (campo 'dni' usado de forma genérica para DNI/CE/RUC)
            dni = (data.get('dni') or '').strip()
            if not dni:
                return False, 'El número de documento es obligatorio', None

            # Validar longitud según tipo
            if document_type == 'DNI' and len(dni) != 8:
                return False, 'El DNI debe tener 8 dígitos', None
            if document_type == 'CE' and (len(dni) < 9 or len(dni) > 12):
                return False, 'El CE debe tener entre 9 y 12 caracteres', None
            if document_type == 'RUC' and len(dni) != 11:
                return False, 'El RUC debe tener 11 dígitos', None

            # Verificar duplicados por documento
            existing_client = ClientService.get_client_by_dni(dni)
            if existing_client:
                return False, f'Ya existe un cliente con el {document_type} {dni}', None

            # Email
            email = (data.get('email') or '').strip()
            if not email:
                return False, 'El email es obligatorio', None
            if not validate_email(email):
                return False, 'Email inválido', None
            if ClientService.get_client_by_email(email):
                return False, 'Ya existe un cliente con este email', None

            # Teléfono (opcional)
            phone = (data.get('phone') or '').strip()
            if phone and not validate_phone(phone):
                return False, 'Teléfono inválido', None

            # --- BANK ACCOUNTS: intentar obtener de varias fuentes ---
            bank_accounts = data.get('bank_accounts')
            # Si viene como string JSON (desde formulario), parsear
            if isinstance(bank_accounts, str) and bank_accounts.strip():
                try:
                    bank_accounts = json.loads(bank_accounts)
                except Exception:
                    return False, 'Formato JSON inválido para bank_accounts', None

            # Si no vino bank_accounts, intentar construir desde campos legacy
            if not bank_accounts:
                legacy_accounts = ClientService._build_bank_accounts_from_legacy(data)
                if legacy_accounts:
                    bank_accounts = legacy_accounts

            # Requerir mínimo 2 cuentas
            if not bank_accounts or not isinstance(bank_accounts, (list, tuple)) or len(bank_accounts) < 2:
                return False, 'Debes registrar al menos 2 cuentas bancarias', None

            # Validar cuentas usando el método del modelo (ahora estático)
            is_valid, message = Client.validate_bank_accounts(bank_accounts)
            if not is_valid:
                return False, message, None

            # --- Construcción del objeto cliente (no persistir todavía hasta validaciones completadas) ---
            client = Client()
            client.document_type = document_type
            client.dni = dni
            client.email = email.lower()
            client.phone = phone if phone else None

            # Campos por tipo
            if document_type == 'RUC':
                razon_social = (data.get('razon_social') or '').strip()
                if not razon_social:
                    return False, 'La razón social es obligatoria', None
                client.razon_social = razon_social
                client.persona_contacto = (data.get('persona_contacto') or '').strip() or None
                # documentos RUC (si se pasaron como URLs o si se subieron y rutas están en data)
                client.dni_representante_front_url = data.get('dni_representante_front_url') or data.get('rep_dni_front_url')
                client.dni_representante_back_url = data.get('dni_representante_back_url') or data.get('rep_dni_back_url')
                client.ficha_ruc_url = data.get('ficha_ruc_url') or data.get('ruc_file_url')
            else:
                # Persona natural
                apellido_paterno = (data.get('apellido_paterno') or '').strip()
                apellido_materno = (data.get('apellido_materno') or '').strip()
                nombres = (data.get('nombres') or '').strip()
                if not apellido_paterno or not apellido_materno or not nombres:
                    return False, 'Apellidos y nombres son obligatorios', None
                client.apellido_paterno = apellido_paterno
                client.apellido_materno = apellido_materno
                client.nombres = nombres
                client.dni_front_url = data.get('dni_front_url')
                client.dni_back_url = data.get('dni_back_url')

            # Dirección
            client.direccion = (data.get('direccion') or '').strip() or None
            client.distrito = (data.get('distrito') or '').strip() or None
            client.provincia = (data.get('provincia') or '').strip() or None
            client.departamento = (data.get('departamento') or '').strip() or None

            # Campos bancarios legacy (se mantienen para compatibilidad)
            client.origen = (data.get('origen') or data.get('bank_origin') or '').strip() or None
            client.bank_name = (data.get('bank_name') or '').strip() or None
            client.account_type = (data.get('account_type') or '').strip() or None
            client.currency = (data.get('currency') or '').strip() or None
            client.bank_account_number = (data.get('bank_account_number') or '').strip() or None

            # Estado: Trader -> Inactivo siempre; Master/Operador -> permite 'Activo' por defecto
            try:
                role = getattr(current_user, 'role', None)
            except Exception:
                role = None

            if role == 'Trader':
                client.status = 'Inactivo'
            else:
                # si se pasó un estado válido en data, respetarlo; si no, default 'Activo'
                client.status = data.get('status') if data.get('status') in ['Activo', 'Inactivo'] else 'Activo'

            # created_by si existe
            client.created_by = getattr(current_user, 'id', None)
            client.created_at = now_peru()

            # --- Persistir en DB ---
            try:
                db.session.add(client)
                # set_bank_accounts actualiza bank_accounts_json y campos legacy a partir de la primera cuenta
                client.set_bank_accounts(bank_accounts)
                db.session.commit()
            except Exception as db_exc:
                db.session.rollback()
                logger.exception("Error al persistir cliente")
                return False, f'Error al guardar cliente en la base de datos: {str(db_exc)}', None

            # Auditoría: intentar registrar sin romper el flujo principal
            try:
                AuditLog.log_action(
                    user_id=getattr(current_user, 'id', None),
                    action='CREATE_CLIENT',
                    entity='Client',
                    entity_id=client.id,
                    details=f'Cliente creado: {client.full_name or client.razon_social or client.dni} ({client.document_type}: {client.dni})'
                )
            except Exception:
                logger.exception("Fallo al registrar auditoría de creación de cliente")

            # Emitir evento WebSocket para actualización en tiempo real
            try:
                socketio.emit('client_created', {
                    'client_id': client.id,
                    'client': client.to_dict(include_stats=True),
                    'created_by': getattr(current_user, 'username', 'Unknown')
                }, broadcast=True)
                logger.info(f'WebSocket event emitted: client_created for ID {client.id}')
            except Exception as ws_exc:
                logger.warning(f'Failed to emit WebSocket event for client creation: {ws_exc}')

            return True, 'Cliente creado exitosamente', client

        except Exception as e:
            # Rollback defensivo y mensaje controlado
            try:
                db.session.rollback()
            except Exception:
                pass
            logger.exception("Unexpected error creating client")
            return False, f'Error al crear cliente: {str(e)}', None

    @staticmethod
    def update_client(current_user, client_id, data):
        """
        Actualizar cliente existente

        ACTUALIZADO: Ahora los Traders pueden editar más información del cliente,
        no solo las cuentas bancarias.

        Args:
            current_user: Usuario que actualiza
            client_id: ID del cliente
            data: Diccionario con datos actualizados

        Returns:
            tuple: (success: bool, message: str, client: Client|None)
        """
        try:
            client = ClientService.get_client_by_id(client_id)
            if not client:
                return False, 'Cliente no encontrado', None

            # VALIDACIÓN DE ROL: TRADER solo puede editar cuentas bancarias
            user_role = getattr(current_user, 'role', None)
            if user_role == 'Trader':
                # Verificar que solo se estén editando cuentas bancarias
                allowed_fields = {'bank_accounts', 'origen', 'bank_name', 'account_type',
                                 'currency', 'bank_account_number', 'bank_accounts_json'}

                # Si hay campos que no son de cuentas bancarias, rechazar
                forbidden_fields = set(data.keys()) - allowed_fields
                if forbidden_fields:
                    logger.warning(f"Trader {current_user.username} intentó modificar campos prohibidos: {forbidden_fields}")
                    return False, 'No tienes permisos para modificar estos campos. Solo puedes editar cuentas bancarias.', None

            # Guardar valores anteriores para auditoría
            old_values = client.to_dict()

            # Validar email si cambió
            new_email = (data.get('email') or '').strip()
            if new_email and new_email != client.email:
                if not validate_email(new_email):
                    return False, 'Email inválido', None

                existing = ClientService.get_client_by_email(new_email)
                if existing and existing.id != client_id:
                    return False, 'Ya existe un cliente con este email', None

                client.email = new_email.lower()

            # Validar teléfono
            phone = (data.get('phone') or '').strip()
            if phone and not validate_phone(phone):
                return False, 'Teléfono inválido', None
            client.phone = phone if phone else None

            # Actualizar campos según tipo de documento
            if client.document_type == 'RUC':
                razon_social = (data.get('razon_social') or '').strip()
                if razon_social:
                    client.razon_social = razon_social

                client.persona_contacto = (data.get('persona_contacto') or '').strip() or None

                # URLs de documentos (si se proporcionan nuevas)
                if data.get('dni_representante_front_url'):
                    client.dni_representante_front_url = data.get('dni_representante_front_url')
                if data.get('dni_representante_back_url'):
                    client.dni_representante_back_url = data.get('dni_representante_back_url')
                if data.get('ficha_ruc_url'):
                    client.ficha_ruc_url = data.get('ficha_ruc_url')
            else:
                # DNI o CE
                apellido_paterno = (data.get('apellido_paterno') or '').strip()
                apellido_materno = (data.get('apellido_materno') or '').strip()
                nombres = (data.get('nombres') or '').strip()

                if apellido_paterno:
                    client.apellido_paterno = apellido_paterno
                if apellido_materno:
                    client.apellido_materno = apellido_materno
                if nombres:
                    client.nombres = nombres

                # URLs de documentos (si se proporcionan nuevas)
                if data.get('dni_front_url'):
                    client.dni_front_url = data.get('dni_front_url')
                if data.get('dni_back_url'):
                    client.dni_back_url = data.get('dni_back_url')

            # Dirección
            if 'direccion' in data:
                client.direccion = (data.get('direccion') or '').strip() or None
            if 'distrito' in data:
                client.distrito = (data.get('distrito') or '').strip() or None
            if 'provincia' in data:
                client.provincia = (data.get('provincia') or '').strip() or None
            if 'departamento' in data:
                client.departamento = (data.get('departamento') or '').strip() or None

            # Información bancaria: si vienen bank_accounts, validarlas y setearlas
            bank_accounts = data.get('bank_accounts')
            if isinstance(bank_accounts, str) and bank_accounts.strip():
                try:
                    bank_accounts = json.loads(bank_accounts)
                except Exception:
                    return False, 'Formato JSON inválido para bank_accounts', None

            if bank_accounts:
                # validar con helper del modelo
                is_valid, message = Client.validate_bank_accounts(bank_accounts)
                if not is_valid:
                    return False, message, None
                client.set_bank_accounts(bank_accounts)

            # Campos legacy
            if 'origen' in data:
                client.origen = (data.get('origen') or '').strip() or None
            if 'bank_name' in data:
                client.bank_name = (data.get('bank_name') or '').strip() or None
            if 'account_type' in data:
                client.account_type = (data.get('account_type') or '').strip() or None
            if 'currency' in data:
                client.currency = (data.get('currency') or '').strip() or None
            if 'bank_account_number' in data:
                client.bank_account_number = (data.get('bank_account_number') or '').strip() or None

            db.session.commit()

            # Auditoría
            try:
                AuditLog.log_action(
                    user_id=getattr(current_user, 'id', None),
                    action='UPDATE_CLIENT',
                    entity='Client',
                    entity_id=client.id,
                    details=f'Cliente actualizado: {client.full_name or client.razon_social or client.dni}'
                )
            except Exception:
                logger.exception("Fallo al registrar auditoría de actualización")

            # Emitir evento WebSocket para actualización en tiempo real
            try:
                socketio.emit('client_updated', {
                    'client_id': client.id,
                    'client': client.to_dict(include_stats=True),
                    'updated_by': getattr(current_user, 'username', 'Unknown')
                }, broadcast=True)
                logger.info(f'WebSocket event emitted: client_updated for ID {client.id}')
            except Exception as ws_exc:
                logger.warning(f'Failed to emit WebSocket event for client update: {ws_exc}')

            return True, 'Cliente actualizado exitosamente', client

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error al actualizar cliente: {str(e)}')
            return False, f'Error al actualizar cliente: {str(e)}', None

    @staticmethod
    def change_client_status(current_user, client_id, new_status):
        """
        Cambiar estado del cliente
        """
        try:
            if new_status not in ['Activo', 'Inactivo']:
                return False, 'Estado inválido', None

            client = ClientService.get_client_by_id(client_id)
            if not client:
                return False, 'Cliente no encontrado', None

            old_status = client.status
            client.status = new_status

            db.session.commit()

            # Auditoría
            try:
                AuditLog.log_action(
                    user_id=getattr(current_user, 'id', None),
                    action='UPDATE_CLIENT',
                    entity='Client',
                    entity_id=client.id,
                    details=f'Estado cambiado de {old_status} a {new_status} para cliente {client.full_name or client.razon_social or client.dni}'
                )
            except Exception:
                logger.exception("Fallo al registrar auditoría de cambio de estado")

            # Emitir evento WebSocket para actualización de estado
            try:
                socketio.emit('client_status_changed', {
                    'client_id': client.id,
                    'client': client.to_dict(include_stats=True),
                    'old_status': old_status,
                    'new_status': new_status,
                    'changed_by': getattr(current_user, 'username', 'Unknown')
                }, broadcast=True)
                logger.info(f'WebSocket event emitted: client_status_changed for ID {client.id}')
            except Exception as ws_exc:
                logger.warning(f'Failed to emit WebSocket event for status change: {ws_exc}')

            return True, f'Cliente {new_status.lower()} exitosamente', client

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error al cambiar estado: {str(e)}')
            return False, f'Error al cambiar estado: {str(e)}', None

    @staticmethod
    def delete_client(current_user, client_id):
        """
        Eliminar cliente
        """
        try:
            client = ClientService.get_client_by_id(client_id)
            if not client:
                return False, 'Cliente no encontrado'

            # Verificar si tiene operaciones
            if hasattr(client, 'operations') and client.operations.count() > 0:
                return False, 'No se puede eliminar un cliente con operaciones registradas'

            client_name = client.full_name or client.razon_social or client.dni

            # Auditoría antes de eliminar
            try:
                AuditLog.log_action(
                    user_id=getattr(current_user, 'id', None),
                    action='DELETE_CLIENT',
                    entity='Client',
                    entity_id=client.id,
                    details=f'Cliente eliminado: {client_name}'
                )
            except Exception:
                logger.exception("Fallo al registrar auditoría de eliminación")

            # Guardar ID antes de eliminar para el evento WebSocket
            deleted_client_id = client.id

            db.session.delete(client)
            db.session.commit()

            # Emitir evento WebSocket para eliminación
            try:
                socketio.emit('client_deleted', {
                    'client_id': deleted_client_id,
                    'client_name': client_name,
                    'deleted_by': getattr(current_user, 'username', 'Unknown')
                }, broadcast=True)
                logger.info(f'WebSocket event emitted: client_deleted for ID {deleted_client_id}')
            except Exception as ws_exc:
                logger.warning(f'Failed to emit WebSocket event for client deletion: {ws_exc}')

            return True, 'Cliente eliminado exitosamente'

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error al eliminar cliente: {str(e)}')
            return False, f'Error al eliminar cliente: {str(e)}'

    @staticmethod
    def update_client_documents(current_user, client_id, document_urls):
        """
        Actualizar URLs de documentos del cliente
        """
        try:
            client = ClientService.get_client_by_id(client_id)
            if not client:
                return False, 'Cliente no encontrado', None

            # Actualizar según tipo de documento
            if client.document_type == 'RUC':
                if 'dni_representante_front_url' in document_urls:
                    client.dni_representante_front_url = document_urls['dni_representante_front_url']
                if 'dni_representante_back_url' in document_urls:
                    client.dni_representante_back_url = document_urls['dni_representante_back_url']
                if 'ficha_ruc_url' in document_urls:
                    client.ficha_ruc_url = document_urls['ficha_ruc_url']
            else:
                if 'dni_front_url' in document_urls:
                    client.dni_front_url = document_urls['dni_front_url']
                if 'dni_back_url' in document_urls:
                    client.dni_back_url = document_urls['dni_back_url']

            db.session.commit()

            # Auditoría
            try:
                AuditLog.log_action(
                    user_id=getattr(current_user, 'id', None),
                    action='UPDATE_CLIENT',
                    entity='Client',
                    entity_id=client.id,
                    details=f'Documentos actualizados para cliente {client.full_name or client.dni}'
                )
            except Exception:
                logger.exception("Fallo al registrar auditoría de actualización documentos")

            return True, 'Documentos actualizados exitosamente', client

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error al actualizar documentos: {str(e)}')
            return False, f'Error al actualizar documentos: {str(e)}', None

    @staticmethod
    def get_client_stats(client_id):
        """
        Obtener estadísticas de un cliente
        """
        client = ClientService.get_client_by_id(client_id)
        if not client:
            return None

        operations = client.operations.all() if hasattr(client, 'operations') else []
        completed_operations = [op for op in operations if op.status == 'Completada']

        total_usd = sum(getattr(op, 'amount_usd', 0) for op in completed_operations)
        total_pen = sum(getattr(op, 'amount_pen', 0) for op in completed_operations)

        return {
            'total_operations': len(operations),
            'completed_operations': len(completed_operations),
            'pending_operations': len([op for op in operations if op.status == 'Pendiente']),
            'in_process_operations': len([op for op in operations if op.status == 'En proceso']),
            'total_usd_traded': float(total_usd),
            'total_pen_traded': float(total_pen),
            'last_operation': operations[0].created_at if operations else None
        }

    @staticmethod
    def search_clients(query):
        """
        Buscar clientes por nombre, DNI o email
        """
        search = f"%{query}%"
        return Client.query.filter(
            or_(
                Client.dni.ilike(search),
                Client.email.ilike(search),
                Client.apellido_paterno.ilike(search),
                Client.apellido_materno.ilike(search),
                Client.nombres.ilike(search),
                Client.razon_social.ilike(search)
            )
        ).all()

    @staticmethod
    def export_clients_to_dict():
        """
        Exportar todos los clientes a diccionario (para Excel/CSV)

        ACTUALIZADO: Ahora incluye el usuario que registró al cliente
        """
        clients = ClientService.get_all_clients()

        export_data = []
        for client in clients:
            data = {
                'ID': client.id,
                'Tipo Documento': client.document_type,
                'Número Documento': client.dni,
                'Nombre Completo': client.full_name or '',
                'Email': client.email,
                'Teléfono': client.phone or '',
                'Dirección Completa': client.full_address or '',
                'Origen': client.origen or '',
                # ACTUALIZADO: Reemplazar 'Banco' por 'Usuario' para Master/Operador
                'Usuario Registro': client.creator.username if client.creator else 'N/A',
                'Tipo Cuenta': client.account_type or '',
                'Moneda': client.currency or '',
                'Número Cuenta': client.bank_account_number or '',
                'Estado': client.status,
                'Total Operaciones': client.get_total_operations(),
                'Operaciones Completadas': client.get_completed_operations(),
                'Fecha Registro': client.created_at.strftime('%d/%m/%Y %H:%M') if client.created_at else ''
            }

            # Agregar campos específicos según tipo
            if client.document_type == 'RUC':
                data['Persona Contacto'] = client.persona_contacto or ''
            else:
                data['Apellido Paterno'] = client.apellido_paterno or ''
                data['Apellido Materno'] = client.apellido_materno or ''
                data['Nombres'] = client.nombres or ''

            export_data.append(data)

        return export_data