"""
Servicio de Facturación Electrónica para QoriCash Trading V2
Integración con NubeFact API
"""
import requests
import logging
from datetime import datetime
from flask import current_app
from app.extensions import db
from app.models.invoice import Invoice
from app.models.operation import Operation
from app.models.client import Client
from app.utils.formatters import now_peru

logger = logging.getLogger(__name__)


class InvoiceService:
    """Servicio para generar y enviar facturas electrónicas a través de NubeFact"""

    # Mapeo de tipo de documento del cliente para NubeFact
    DOCUMENT_TYPE_MAPPING = {
        'DNI': '1',      # DNI
        'CE': '4',       # Carnet de Extranjería
        'RUC': '6'       # RUC
    }

    # Tipo de comprobante SUNAT
    INVOICE_TYPE_MAPPING = {
        'Factura': '1',     # Factura
        'Boleta': '2'       # Boleta de Venta (sin cero adelante según ejemplo NubeFact)
    }

    @staticmethod
    def is_enabled():
        """Verificar si la facturación electrónica está habilitada"""
        return current_app.config.get('NUBEFACT_ENABLED', False)

    @staticmethod
    def _get_next_correlative(serie):
        """
        Obtener el siguiente número correlativo para una serie

        Args:
            serie: Serie del comprobante (ej: 'F001', 'B001')

        Returns:
            int: Siguiente número correlativo
        """
        from sqlalchemy import func, cast, Integer
        from sqlalchemy.sql import text

        # Buscar TODAS las facturas de esta serie y encontrar el máximo número
        # Incluye errores porque NubeFact puede haberlas creado antes de rechazarlas
        all_invoices = Invoice.query.filter_by(serie=serie).all()

        max_numero = 0
        for invoice in all_invoices:
            if invoice.numero:
                try:
                    num = int(invoice.numero)
                    if num > max_numero:
                        max_numero = num
                except (ValueError, TypeError):
                    # Ignorar números que no son enteros
                    continue

        next_numero = max_numero + 1
        logger.info(f'[INVOICE] Último correlativo para {serie}: {max_numero}, siguiente: {next_numero}')
        return next_numero

    @staticmethod
    def generate_invoice_for_operation(operation_id):
        """
        Generar factura electrónica para una operación

        Args:
            operation_id: ID de la operación

        Returns:
            tuple: (success: bool, message: str, invoice: Invoice)
        """
        try:
            # Verificar si está habilitado
            if not InvoiceService.is_enabled():
                logger.info('[INVOICE] Facturación electrónica deshabilitada')
                return False, 'Facturación electrónica no habilitada', None

            # Obtener operación
            operation = Operation.query.get(operation_id)
            if not operation:
                return False, 'Operación no encontrada', None

            # Obtener cliente
            client = operation.client
            if not client:
                return False, 'Cliente no encontrado', None

            # Verificar si ya existe factura para esta operación
            existing_invoice = Invoice.query.filter_by(
                operation_id=operation.id,
                status='Aceptado'
            ).first()

            if existing_invoice:
                logger.info(f'[INVOICE] Ya existe factura aceptada para operación {operation.operation_id}')
                return True, 'Ya existe factura para esta operación', existing_invoice

            # Determinar tipo de comprobante según documento del cliente
            invoice_type_name, invoice_type_code = InvoiceService._determine_invoice_type(client)

            # Preparar datos del comprobante
            invoice_data = InvoiceService._prepare_invoice_data(operation, client, invoice_type_code)

            # Enviar a NubeFact
            success, response_data = InvoiceService._send_to_nubefact(invoice_data)

            if not success:
                error_msg = response_data.get('errors', 'Error desconocido')
                logger.error(f'[INVOICE] Error al enviar a NubeFact: {error_msg}')

                # Crear registro de factura con error
                invoice = Invoice(
                    operation_id=operation.id,
                    client_id=client.id,
                    invoice_type=invoice_type_name,
                    emisor_ruc=current_app.config.get('COMPANY_RUC'),
                    emisor_razon_social=current_app.config.get('COMPANY_NAME'),
                    emisor_direccion=InvoiceService._get_company_full_address(),
                    cliente_tipo_documento=client.document_type,
                    cliente_numero_documento=client.dni,
                    cliente_denominacion=client.full_name or 'CLIENTE',
                    cliente_direccion=client.full_address,
                    cliente_email=client.email,
                    descripcion=InvoiceService._generate_service_description(operation),
                    monto_total=operation.amount_pen,
                    moneda='PEN',
                    exonerada=operation.amount_pen,  # En BD guardamos como exonerada (inafecta para NubeFact)
                    status='Error',
                    error_message=str(error_msg)
                )
                db.session.add(invoice)
                db.session.commit()

                return False, f'Error al generar factura: {error_msg}', invoice

            # Crear registro de factura exitoso
            invoice = InvoiceService._create_invoice_from_response(
                operation, client, invoice_type_name, response_data
            )

            logger.info(f'[INVOICE] ✅ Factura generada exitosamente: {invoice.invoice_number}')
            logger.info(f'[INVOICE] PDF URL guardada: {invoice.nubefact_enlace_pdf}')
            logger.info(f'[INVOICE] XML URL guardada: {invoice.nubefact_enlace_xml}')
            return True, 'Factura generada correctamente', invoice

        except Exception as e:
            logger.error(f'[INVOICE] Error al generar factura: {str(e)}')
            logger.exception(e)
            return False, f'Error inesperado: {str(e)}', None

    @staticmethod
    def _determine_invoice_type(client):
        """
        Determinar tipo de comprobante según documento del cliente

        Returns:
            tuple: (invoice_type_name, invoice_type_code)
        """
        if client.document_type == 'RUC':
            return 'Factura', '1'
        else:  # DNI o CE
            return 'Boleta', '2'  # Sin cero adelante según ejemplo NubeFact

    @staticmethod
    def _get_company_full_address():
        """Obtener dirección completa de la empresa"""
        address = current_app.config.get('COMPANY_ADDRESS', '')
        district = current_app.config.get('COMPANY_DISTRICT', '')
        province = current_app.config.get('COMPANY_PROVINCE', '')
        department = current_app.config.get('COMPANY_DEPARTMENT', '')

        parts = [address, district, province, department]
        return ', '.join([p for p in parts if p])

    @staticmethod
    def _generate_service_description(operation):
        """
        Generar descripción del servicio según la operación

        Formato: QORICASH VENDE 100 USD CON TIPO DE CAMBIO 3.5698
                 CLIENTE ENVIA 356.98 PEN CLIENTE RECIBE 100 USD
        """
        if operation.operation_type == 'Venta':
            # QoriCash vende USD al cliente
            description = (
                f"QORICASH VENDE {float(operation.amount_usd):.2f} USD "
                f"CON TIPO DE CAMBIO {float(operation.exchange_rate):.4f} - "
                f"CLIENTE ENVIA {float(operation.amount_pen):.2f} PEN - "
                f"CLIENTE RECIBE {float(operation.amount_usd):.2f} USD"
            )
        else:  # Compra
            # QoriCash compra USD al cliente
            description = (
                f"QORICASH COMPRA {float(operation.amount_usd):.2f} USD "
                f"CON TIPO DE CAMBIO {float(operation.exchange_rate):.4f} - "
                f"CLIENTE ENVIA {float(operation.amount_usd):.2f} USD - "
                f"CLIENTE RECIBE {float(operation.amount_pen):.2f} PEN"
            )

        return description

    @staticmethod
    def _prepare_invoice_data(operation, client, invoice_type_code):
        """
        Preparar datos del comprobante para enviar a NubeFact

        Returns:
            dict: Datos del comprobante en formato NubeFact
        """
        # Obtener tipo de documento del cliente
        client_doc_type = InvoiceService.DOCUMENT_TYPE_MAPPING.get(
            client.document_type, '1'
        )

        # Datos de la empresa
        company_ruc = current_app.config.get('COMPANY_RUC')
        company_name = current_app.config.get('COMPANY_NAME')
        company_address = InvoiceService._get_company_full_address()

        # Descripción del servicio
        service_description = InvoiceService._generate_service_description(operation)

        # Monto (exonerado de IGV)
        total_amount = float(operation.amount_pen)

        # Preparar items (detalle del comprobante)
        items = [{
            "unidad_de_medida": "ZZ",  # ZZ = Servicio
            "codigo": "001",
            "descripcion": service_description,
            "cantidad": 1,
            "valor_unitario": total_amount,
            "precio_unitario": total_amount,
            "subtotal": total_amount,
            "tipo_de_igv": 9,  # 9 = Inafecto según ejemplo NubeFact
            "igv": 0,
            "total": total_amount,
            "anticipo_regularizacion": False,
            "codigo_producto_sunat": "20000000"  # Código SUNAT para servicios
        }]

        # Determinar serie y obtener siguiente correlativo
        # IMPORTANTE: Usar B002 porque B001-1 ya existe en NubeFact (anulado pero no eliminado)
        serie = "F001" if invoice_type_code == "1" else "B002"
        next_number = InvoiceService._get_next_correlative(serie)
        numero_int = int(next_number)  # Enviar como entero según ejemplo NubeFact

        logger.info(f'[INVOICE] Serie: {serie}, Número correlativo: {numero_int}')

        # Estructura del comprobante para NubeFact (siguiendo ejemplo oficial)
        invoice_data = {
            "operacion": "generar_comprobante",
            "tipo_de_comprobante": invoice_type_code,
            "serie": serie,
            "numero": numero_int,  # Enviar como entero
            "sunat_transaction": 1,
            "cliente_tipo_de_documento": int(client_doc_type),  # Enviar como entero
            "cliente_numero_de_documento": client.dni,
            "cliente_denominacion": client.full_name or "CLIENTE",
            "cliente_direccion": client.full_address or "-",
            "cliente_email": client.email.split(';')[0] if client.email else "",
            "cliente_email_1": "",
            "cliente_email_2": "",
            "fecha_de_emision": now_peru().strftime("%d-%m-%Y"),
            "fecha_de_vencimiento": "",
            "moneda": "1",  # String según ejemplo NubeFact
            "tipo_de_cambio": "",
            "porcentaje_de_igv": "18.00",  # String según ejemplo
            "descuento_global": "",
            "total_descuento": "",
            "total_anticipo": "",
            "total_gravada": "",  # String vacío en lugar de 0
            "total_inafecta": str(total_amount),  # CORREGIDO: Inafecta para operaciones de cambio
            "total_exonerada": "",  # String vacío
            "total_igv": "",  # String vacío
            "total_gratuita": "",
            "total_otros_cargos": "",
            "total": str(total_amount),  # String según ejemplo
            "percepcion_tipo": "",
            "percepcion_base_imponible": "",
            "total_percepcion": "",
            "total_incluido_percepcion": "",
            "detraccion": "false",  # String según ejemplo
            "observaciones": f"Operación #{operation.operation_id}",
            "documento_que_se_modifica_tipo": "",
            "documento_que_se_modifica_serie": "",
            "documento_que_se_modifica_numero": "",
            "tipo_de_nota_de_credito": "",
            "tipo_de_nota_de_debito": "",
            "enviar_automaticamente_a_la_sunat": "true",  # String según ejemplo
            "enviar_automaticamente_al_cliente": "false",  # String según ejemplo
            "codigo_unico": operation.operation_id,  # ID único de la operación
            "condiciones_de_pago": "",
            "medio_de_pago": "",
            "placa_vehiculo": "",
            "orden_compra_servicio": "",
            "tabla_personalizada_codigo": "",
            "formato_de_pdf": "A4",  # Formato A4 para boletas (igual que facturas)
            "items": items
        }

        return invoice_data

    @staticmethod
    def _send_to_nubefact(invoice_data):
        """
        Enviar comprobante a NubeFact API

        Returns:
            tuple: (success: bool, response_data: dict)
        """
        try:
            api_url = current_app.config.get('NUBEFACT_API_URL')
            api_token = current_app.config.get('NUBEFACT_TOKEN')

            if not api_token:
                return False, {'errors': 'Token de NubeFact no configurado'}

            headers = {
                'Authorization': f'Token token="{api_token}"',
                'Content-Type': 'application/json'
            }

            logger.info('[INVOICE] Enviando comprobante a NubeFact...')
            logger.info(f'[INVOICE] URL: {api_url}')
            logger.info(f'[INVOICE] JSON enviado: {invoice_data}')

            response = requests.post(
                api_url,
                json=invoice_data,
                headers=headers,
                timeout=30
            )

            response_data = response.json()

            logger.info(f'[INVOICE] Respuesta NubeFact: Status {response.status_code}')
            logger.info(f'[INVOICE] Respuesta completa: {response_data}')

            if response.status_code in [200, 201]:
                logger.info(f'[INVOICE] ✅ NubeFact respondió exitosamente')

                # Verificar si SUNAT aceptó el comprobante
                aceptada_sunat = response_data.get('aceptada_por_sunat', False)
                enlace_pdf = response_data.get('enlace_del_pdf', '')
                enlace_xml = response_data.get('enlace_del_xml', '')

                logger.info(f'[INVOICE] Aceptada por SUNAT: {aceptada_sunat}')
                logger.info(f'[INVOICE] Enlace PDF: {enlace_pdf}')
                logger.info(f'[INVOICE] Enlace XML: {enlace_xml}')

                # Si NubeFact generó el comprobante (tiene enlaces), es exitoso
                # En modo DEMO, aceptada_por_sunat puede ser False pero el comprobante se genera correctamente
                if enlace_pdf and enlace_xml:
                    if aceptada_sunat:
                        logger.info(f'[INVOICE] ✅ Comprobante ACEPTADO por SUNAT')
                    else:
                        logger.info(f'[INVOICE] ⚠️ Comprobante generado en modo DEMO (no enviado a SUNAT aún)')
                    return True, response_data
                else:
                    # No hay enlaces = error real
                    sunat_desc = response_data.get('sunat_description', 'Error al generar comprobante')
                    logger.error(f'[INVOICE] ❌ Error: {sunat_desc}')
                    return False, {
                        'errors': sunat_desc
                    }
            else:
                logger.error(f'[INVOICE] ❌ NubeFact respondió con error: Status {response.status_code}')
                return False, response_data

        except requests.exceptions.Timeout:
            logger.error('[INVOICE] Timeout al conectar con NubeFact')
            return False, {'errors': 'Timeout al conectar con NubeFact'}
        except requests.exceptions.RequestException as e:
            logger.error(f'[INVOICE] Error de conexión con NubeFact: {str(e)}')
            return False, {'errors': f'Error de conexión: {str(e)}'}
        except Exception as e:
            logger.error(f'[INVOICE] Error inesperado al enviar a NubeFact: {str(e)}')
            return False, {'errors': f'Error inesperado: {str(e)}'}

    @staticmethod
    def _create_invoice_from_response(operation, client, invoice_type_name, response_data):
        """
        Crear registro de factura desde respuesta de NubeFact

        Returns:
            Invoice: Objeto Invoice creado
        """
        invoice = Invoice(
            operation_id=operation.id,
            client_id=client.id,
            invoice_type=invoice_type_name,
            serie=response_data.get('serie', ''),
            numero=response_data.get('numero', ''),
            invoice_number=f"{response_data.get('serie', '')}-{response_data.get('numero', '')}",
            emisor_ruc=current_app.config.get('COMPANY_RUC'),
            emisor_razon_social=current_app.config.get('COMPANY_NAME'),
            emisor_direccion=InvoiceService._get_company_full_address(),
            cliente_tipo_documento=client.document_type,
            cliente_numero_documento=client.dni,
            cliente_denominacion=client.full_name or 'CLIENTE',
            cliente_direccion=client.full_address,
            cliente_email=client.email,
            descripcion=InvoiceService._generate_service_description(operation),
            monto_total=operation.amount_pen,
            moneda='PEN',
            exonerada=operation.amount_pen,  # En BD guardamos como exonerada (inafecta para NubeFact)
            gravada=0,
            igv=0,
            status='Aceptado',
            nubefact_response=str(response_data),
            nubefact_enlace_pdf=response_data.get('enlace_del_pdf', ''),
            nubefact_enlace_xml=response_data.get('enlace_del_xml', ''),
            # nubefact_enlace_cdr=response_data.get('enlace_del_cdr', ''),  # CDR de SUNAT - TEMPORALMENTE COMENTADO
            nubefact_aceptada_por_sunat=response_data.get('aceptada_por_sunat', False),
            nubefact_sunat_description=response_data.get('sunat_description', ''),
            nubefact_sunat_note=response_data.get('sunat_note', ''),
            nubefact_codigo_hash=response_data.get('codigo_hash', ''),
            sent_at=now_peru(),
            accepted_at=now_peru() if response_data.get('aceptada_por_sunat') else None
        )

        db.session.add(invoice)
        db.session.commit()

        return invoice

    @staticmethod
    def get_invoice_pdf_url(invoice_id):
        """
        Obtener URL del PDF de una factura

        Args:
            invoice_id: ID de la factura

        Returns:
            str: URL del PDF o None
        """
        invoice = Invoice.query.get(invoice_id)
        if invoice and invoice.nubefact_enlace_pdf:
            return invoice.nubefact_enlace_pdf
        return None

    @staticmethod
    def get_invoices_for_operation(operation_id):
        """
        Obtener todas las facturas de una operación

        Args:
            operation_id: ID de la operación

        Returns:
            list: Lista de facturas
        """
        operation = Operation.query.get(operation_id)
        if not operation:
            return []

        return Invoice.query.filter_by(operation_id=operation.id).all()
