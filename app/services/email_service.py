"""
Servicio de envío de correos electrónicos para QoriCash Trading V2
"""
from flask import render_template_string
from flask_mail import Message
from app.extensions import mail
from app.models import User
import logging

logger = logging.getLogger(__name__)


class EmailService:
    """Servicio para envío de correos electrónicos"""

    @staticmethod
    def parse_email_addresses(email_string):
        """
        Parsear string de emails separados por ; y retornar lista limpia

        Args:
            email_string: String con emails separados por ; (ej: "email1@x.com;email2@x.com")

        Returns:
            list: Lista de emails únicos y válidos
        """
        if not email_string:
            return []

        # Dividir por ; y limpiar espacios
        emails = [email.strip() for email in email_string.split(';') if email.strip()]

        # Eliminar duplicados manteniendo el orden
        seen = set()
        unique_emails = []
        for email in emails:
            if email not in seen:
                seen.add(email)
                unique_emails.append(email)

        return unique_emails

    @staticmethod
    def check_if_email_is_shared(client_email):
        """
        Verificar si el email está siendo usado por más de un cliente

        Args:
            client_email: Email del cliente a verificar

        Returns:
            tuple: (is_shared: bool, other_clients_count: int)
        """
        from app.models.client import Client

        if not client_email:
            return False, 0

        # Contar cuántos clientes tienen este mismo email (o lo contienen si es múltiple)
        clients_with_email = Client.query.filter(
            Client.email.like(f'%{client_email}%')
        ).count()

        # Si hay más de 1, el email está compartido
        is_shared = clients_with_email > 1
        other_count = clients_with_email - 1 if is_shared else 0

        return is_shared, other_count

    @staticmethod
    def get_recipients_for_new_operation(operation):
        """
        Obtener lista de destinatarios para una nueva operación

        Returns:
            tuple: (to, cc, bcc) donde:
                - to: Cliente (destinatario principal)
                - cc: Trader que creó la operación
                - bcc: Master y Operadores
        """
        # Destinatario principal: Cliente (soporta múltiples emails separados por ;)
        to = EmailService.parse_email_addresses(operation.client.email) if operation.client and operation.client.email else []

        # Copia: Trader que creó la operación
        cc = []
        if operation.user and operation.user.email:
            cc.append(operation.user.email)

        # Copia oculta: Master y Operadores
        bcc = []
        masters_and_operators = User.query.filter(
            User.role.in_(['Master', 'Operador']),
            User.status == 'Activo',
            User.email.isnot(None)
        ).all()

        for user in masters_and_operators:
            if user.email and user.email not in cc:  # Evitar duplicados
                bcc.append(user.email)

        return to, cc, bcc

    @staticmethod
    def get_recipients_for_completed_operation(operation):
        """
        Obtener lista de destinatarios para operación completada

        Returns:
            tuple: (to, cc, bcc) donde:
                - to: Cliente
                - cc: Trader que creó la operación
                - bcc: vacío (no se envía BCC en completadas)
        """
        # Destinatario principal: Cliente (soporta múltiples emails separados por ;)
        to = EmailService.parse_email_addresses(operation.client.email) if operation.client and operation.client.email else []

        # Copia: Trader que creó la operación
        cc = []
        if operation.user and operation.user.email:
            cc.append(operation.user.email)

        return to, cc, []

    @staticmethod
    def send_new_operation_email(operation):
        """
        Enviar correo de notificación de nueva operación

        Args:
            operation: Objeto Operation

        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            # NO enviar correos si el usuario que creó la operación es Plataforma
            # La página web se encarga de enviar sus propios correos
            if operation.user and operation.user.role == 'Plataforma':
                logger.info(f'Email omitido para operación {operation.operation_id} - creada por rol Plataforma')
                return True, 'Email omitido (rol Plataforma)'

            to, cc, bcc = EmailService.get_recipients_for_new_operation(operation)

            # Validar que haya al menos un destinatario
            if not to and not cc and not bcc:
                logger.warning(f'No hay destinatarios para la operación {operation.operation_id}')
                return False, 'No hay destinatarios configurados'

            # Asunto con nombre del trader
            trader_name = operation.user.username if operation.user else 'Sistema'
            subject = f'{trader_name} - Nueva Operación #{operation.operation_id} - QoriCash Trading'

            # Verificar si el email está compartido
            is_shared, other_count = EmailService.check_if_email_is_shared(operation.client.email)

            # Contenido HTML
            html_body = EmailService._render_new_operation_template(operation, is_shared, other_count)

            # Crear mensaje
            msg = Message(
                subject=subject,
                recipients=to,
                cc=cc,
                bcc=bcc,
                html=html_body
            )

            # Enviar
            mail.send(msg)

            logger.info(f'Email de nueva operación enviado: {operation.operation_id}')
            return True, 'Email enviado correctamente'

        except Exception as e:
            logger.error(f'Error al enviar email de nueva operación {operation.operation_id}: {str(e)}')
            return False, f'Error al enviar email: {str(e)}'

    @staticmethod
    def send_completed_operation_email(operation):
        """
        Enviar correo de notificación de operación completada
        Usa credenciales separadas del email de confirmación con Flask-Mail

        Args:
            operation: Objeto Operation

        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            # NO enviar correos si el usuario que creó la operación es Plataforma
            # La página web se encarga de enviar sus propios correos
            if operation.user and operation.user.role == 'Plataforma':
                logger.info(f'Email de completado omitido para operación {operation.operation_id} - creada por rol Plataforma')
                return True, 'Email omitido (rol Plataforma)'

            from flask import current_app
            from flask_mail import Message, Mail

            logger.info(f'[EMAIL] Iniciando envio de email completado para operacion {operation.operation_id}')
            logger.info(f'[EMAIL] operator_proofs: {operation.operator_proofs}')
            logger.info(f'[EMAIL] operator_proof_url (legacy): {operation.operator_proof_url}')

            to, cc, bcc = EmailService.get_recipients_for_completed_operation(operation)

            logger.info(f'[EMAIL] Destinatarios - TO: {to}, CC: {cc}')

            # Validar que haya al menos un destinatario
            if not to and not cc:
                logger.warning(f'No hay destinatarios para la operación completada {operation.operation_id}')
                return False, 'No hay destinatarios configurados'

            # Obtener credenciales del email de confirmación
            confirmation_username = current_app.config.get('MAIL_CONFIRMATION_USERNAME')
            confirmation_password = current_app.config.get('MAIL_CONFIRMATION_PASSWORD')
            confirmation_sender = current_app.config.get('MAIL_CONFIRMATION_SENDER')

            logger.info(f'[EMAIL] Credenciales - Usuario: {confirmation_username}, Remitente: {confirmation_sender}')

            if not confirmation_username or not confirmation_password:
                logger.error('[EMAIL] Credenciales de email de confirmacion no configuradas')
                return False, 'Email de confirmación no configurado'

            # Guardar configuración original
            original_username = current_app.config.get('MAIL_USERNAME')
            original_password = current_app.config.get('MAIL_PASSWORD')
            original_sender = current_app.config.get('MAIL_DEFAULT_SENDER')

            # Sobrescribir temporalmente con credenciales de confirmación
            current_app.config['MAIL_USERNAME'] = confirmation_username
            current_app.config['MAIL_PASSWORD'] = confirmation_password
            current_app.config['MAIL_DEFAULT_SENDER'] = confirmation_sender

            try:
                # Crear un nuevo objeto Mail con la configuración actualizada
                from app.extensions import mail
                mail.init_app(current_app)

                # Asunto
                subject = f'Operación Completada #{operation.operation_id} - QoriCash Trading'

                # Contenido HTML
                logger.info(f'[EMAIL] Generando plantilla HTML')
                html_body = EmailService._render_completed_operation_template(operation)

                # Crear mensaje usando Flask-Mail
                logger.info(f'[EMAIL] Creando mensaje Flask-Mail')
                msg = Message(
                    subject=subject,
                    sender=confirmation_sender,
                    recipients=to,
                    cc=cc if cc else None,
                    html=html_body
                )

                # Enviar
                logger.info(f'[EMAIL] Enviando email a TO: {to}, CC: {cc}')
                mail.send(msg)

                logger.info(f'[EMAIL] Email de operacion completada enviado exitosamente desde {confirmation_sender}: {operation.operation_id}')
                return True, 'Email enviado correctamente'

            finally:
                # Restaurar configuración original
                current_app.config['MAIL_USERNAME'] = original_username
                current_app.config['MAIL_PASSWORD'] = original_password
                current_app.config['MAIL_DEFAULT_SENDER'] = original_sender
                # Reinicializar mail con configuración original
                mail.init_app(current_app)

        except Exception as e:
            logger.error(f'[EMAIL] ERROR al enviar email de operacion completada {operation.operation_id}: {str(e)}')
            logger.exception(e)
            return False, f'Error al enviar email: {str(e)}'

    @staticmethod
    def _render_new_operation_template(operation, is_shared_email=False, other_clients_count=0):
        """Renderizar plantilla HTML para nueva operación"""
        template = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f4f4f4; margin: 0; padding: 0; }
        .container { max-width: 600px; margin: 20px auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px 20px; text-align: center; }
        .header h1 { margin: 0; font-size: 24px; }
        .content { padding: 30px 20px; }
        .badge { display: inline-block; padding: 5px 15px; border-radius: 20px; font-size: 12px; font-weight: bold; margin: 5px 0; }
        .badge-success { background: #10b981; color: white; }
        .badge-primary { background: #3b82f6; color: white; }
        .info-row { display: flex; justify-content: space-between; padding: 12px; border-bottom: 1px solid #e5e7eb; }
        .info-row:last-child { border-bottom: none; }
        .info-label { font-weight: 600; color: #6b7280; }
        .info-value { color: #111827; font-weight: 500; }
        .highlight-box { background: #f9fafb; border-left: 4px solid #667eea; padding: 15px; margin: 20px 0; border-radius: 4px; }
        .footer { background: #f9fafb; padding: 20px; text-align: center; font-size: 12px; color: #6b7280; }
        .btn { display: inline-block; padding: 12px 24px; background: #667eea; color: white; text-decoration: none; border-radius: 6px; margin: 10px 0; }
        @media only screen and (max-width: 600px) {
            .info-row { flex-direction: column; }
            .info-label { margin-bottom: 5px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>✨ Nueva Operación Registrada</h1>
            <p style="margin: 10px 0 0 0; font-size: 14px;">QoriCash Trading</p>
        </div>

        <div class="content">
            <p>Estimado(a) <strong>{{ operation.client.full_name or operation.client.razon_social }}</strong>,</p>
            <p style="margin: -10px 0 15px 0; font-size: 14px; color: #6b7280;">
                <strong>{{ operation.client.document_type or 'Documento' }}:</strong> {{ operation.client.dni }}
            </p>

            <p>Se ha registrado una nueva operación de cambio de divisas con los siguientes detalles:</p>

            <div class="highlight-box">
                <div class="info-row">
                    <span class="info-label">Código de Operación:</span>
                    <span class="info-value"><strong>{{ operation.operation_id }}</strong></span>
                </div>
                <div class="info-row">
                    <span class="info-label">Tipo:</span>
                    <span class="info-value">
                        {% if operation.operation_type == 'Compra' %}
                            <span class="badge badge-success">COMPRA USD</span>
                        {% else %}
                            <span class="badge badge-primary">VENTA USD</span>
                        {% endif %}
                    </span>
                </div>
                <div class="info-row">
                    <span class="info-label">Monto USD:</span>
                    <span class="info-value" style="font-size: 18px; color: #059669;">$ {{ "{:,.2f}".format(operation.amount_usd) }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Tipo de Cambio:</span>
                    <span class="info-value">{{ "%.4f"|format(operation.exchange_rate) }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Monto PEN:</span>
                    <span class="info-value" style="font-size: 18px; color: #dc2626;">S/ {{ "{:,.2f}".format(operation.amount_pen) }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Estado:</span>
                    <span class="info-value"><strong>{{ operation.status }}</strong></span>
                </div>
                <div class="info-row">
                    <span class="info-label">Fecha:</span>
                    <span class="info-value">{{ operation.created_at.strftime('%d/%m/%Y %H:%M') }}</span>
                </div>
            </div>

            <!-- Cuentas bancarias para transferencia -->
            {% if operation.operation_type == 'Compra' %}
            <div style="margin: 25px 0; padding: 20px; background: #ecfdf5; border-radius: 8px; border: 2px solid #10b981;">
                <h3 style="margin: 0 0 15px 0; color: #065f46; font-size: 16px;">Cuentas para Transferencia (USD)</h3>
                <p style="margin: 0 0 10px 0; color: #374151; font-size: 14px;">Por favor, realice su transferencia en cualquiera de las siguientes cuentas en DOLARES:</p>
                <p style="margin: 0 0 15px 0; color: #065f46; font-size: 13px; font-weight: 600;">- A nombre de QORICASH SAC con número de RUC 20235842211</p>
                <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                    <thead>
                        <tr style="background: #d1fae5;">
                            <th style="padding: 10px; text-align: left; border-bottom: 2px solid #10b981; color: #065f46; font-weight: 600;">Banco</th>
                            <th style="padding: 10px; text-align: left; border-bottom: 2px solid #10b981; color: #065f46; font-weight: 600;">Tipo</th>
                            <th style="padding: 10px; text-align: left; border-bottom: 2px solid #10b981; color: #065f46; font-weight: 600;">Moneda</th>
                            <th style="padding: 10px; text-align: left; border-bottom: 2px solid #10b981; color: #065f46; font-weight: 600;">Numero de Cuenta</th>
                            <th style="padding: 10px; text-align: left; border-bottom: 2px solid #10b981; color: #065f46; font-weight: 600;">Numero de CCI</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr style="background: white;">
                            <td style="padding: 10px; border-bottom: 1px solid #d1fae5; color: #1f2937; font-weight: 500;">BCP</td>
                            <td style="padding: 10px; border-bottom: 1px solid #d1fae5; color: #4b5563;">Cta. Corriente</td>
                            <td style="padding: 10px; border-bottom: 1px solid #d1fae5; color: #4b5563;">USD</td>
                            <td style="padding: 10px; border-bottom: 1px solid #d1fae5; color: #1f2937; font-family: monospace; font-weight: 600;">654321</td>
                            <td style="padding: 10px; border-bottom: 1px solid #d1fae5; color: #1f2937; font-family: monospace; font-weight: 600;">00265432100000000001</td>
                        </tr>
                        <tr style="background: #f0fdf4;">
                            <td style="padding: 10px; border-bottom: 1px solid #d1fae5; color: #1f2937; font-weight: 500;">INTERBANK</td>
                            <td style="padding: 10px; border-bottom: 1px solid #d1fae5; color: #4b5563;">Cta. Corriente</td>
                            <td style="padding: 10px; border-bottom: 1px solid #d1fae5; color: #4b5563;">USD</td>
                            <td style="padding: 10px; border-bottom: 1px solid #d1fae5; color: #1f2937; font-family: monospace; font-weight: 600;">456789</td>
                            <td style="padding: 10px; border-bottom: 1px solid #d1fae5; color: #1f2937; font-family: monospace; font-weight: 600;">00345678900000000002</td>
                        </tr>
                        <tr style="background: white;">
                            <td style="padding: 10px; border-bottom: 1px solid #d1fae5; color: #1f2937; font-weight: 500;">BANBIF</td>
                            <td style="padding: 10px; border-bottom: 1px solid #d1fae5; color: #4b5563;">Cta. Corriente</td>
                            <td style="padding: 10px; border-bottom: 1px solid #d1fae5; color: #4b5563;">USD</td>
                            <td style="padding: 10px; border-bottom: 1px solid #d1fae5; color: #1f2937; font-family: monospace; font-weight: 600;">369852</td>
                            <td style="padding: 10px; border-bottom: 1px solid #d1fae5; color: #1f2937; font-family: monospace; font-weight: 600;">03836985200000000003</td>
                        </tr>
                        <tr style="background: #f0fdf4;">
                            <td style="padding: 10px; color: #1f2937; font-weight: 500;">PICHINCHA</td>
                            <td style="padding: 10px; color: #4b5563;">Cta. Corriente</td>
                            <td style="padding: 10px; color: #4b5563;">USD</td>
                            <td style="padding: 10px; color: #1f2937; font-family: monospace; font-weight: 600;">159796</td>
                            <td style="padding: 10px; color: #1f2937; font-family: monospace; font-weight: 600;">04815979600000000004</td>
                        </tr>
                    </tbody>
                </table>
            </div>
            {% elif operation.operation_type == 'Venta' %}
            <div style="margin: 25px 0; padding: 20px; background: #fef2f2; border-radius: 8px; border: 2px solid #ef4444;">
                <h3 style="margin: 0 0 15px 0; color: #991b1b; font-size: 16px;">Cuentas para Transferencia (PEN)</h3>
                <p style="margin: 0 0 10px 0; color: #374151; font-size: 14px;">Por favor, realice su transferencia en cualquiera de las siguientes cuentas en SOLES:</p>
                <p style="margin: 0 0 15px 0; color: #991b1b; font-size: 13px; font-weight: 600;">- A nombre de QORICASH SAC con número de RUC 20235842211</p>
                <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                    <thead>
                        <tr style="background: #fee2e2;">
                            <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ef4444; color: #991b1b; font-weight: 600;">Banco</th>
                            <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ef4444; color: #991b1b; font-weight: 600;">Tipo</th>
                            <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ef4444; color: #991b1b; font-weight: 600;">Moneda</th>
                            <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ef4444; color: #991b1b; font-weight: 600;">Numero de Cuenta</th>
                            <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ef4444; color: #991b1b; font-weight: 600;">Numero de CCI</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr style="background: white;">
                            <td style="padding: 10px; border-bottom: 1px solid #fee2e2; color: #1f2937; font-weight: 500;">BCP</td>
                            <td style="padding: 10px; border-bottom: 1px solid #fee2e2; color: #4b5563;">Cta. Corriente</td>
                            <td style="padding: 10px; border-bottom: 1px solid #fee2e2; color: #4b5563;">PEN</td>
                            <td style="padding: 10px; border-bottom: 1px solid #fee2e2; color: #1f2937; font-family: monospace; font-weight: 600;">123456</td>
                            <td style="padding: 10px; border-bottom: 1px solid #fee2e2; color: #1f2937; font-family: monospace; font-weight: 600;">00212345600000000005</td>
                        </tr>
                        <tr style="background: #fef2f2;">
                            <td style="padding: 10px; border-bottom: 1px solid #fee2e2; color: #1f2937; font-weight: 500;">INTERBANK</td>
                            <td style="padding: 10px; border-bottom: 1px solid #fee2e2; color: #4b5563;">Cta. Corriente</td>
                            <td style="padding: 10px; border-bottom: 1px solid #fee2e2; color: #4b5563;">PEN</td>
                            <td style="padding: 10px; border-bottom: 1px solid #fee2e2; color: #1f2937; font-family: monospace; font-weight: 600;">987654</td>
                            <td style="padding: 10px; border-bottom: 1px solid #fee2e2; color: #1f2937; font-family: monospace; font-weight: 600;">00398765400000000006</td>
                        </tr>
                        <tr style="background: white;">
                            <td style="padding: 10px; border-bottom: 1px solid #fee2e2; color: #1f2937; font-weight: 500;">BANBIF</td>
                            <td style="padding: 10px; border-bottom: 1px solid #fee2e2; color: #4b5563;">Cta. Corriente</td>
                            <td style="padding: 10px; border-bottom: 1px solid #fee2e2; color: #4b5563;">PEN</td>
                            <td style="padding: 10px; border-bottom: 1px solid #fee2e2; color: #1f2937; font-family: monospace; font-weight: 600;">741852</td>
                            <td style="padding: 10px; border-bottom: 1px solid #fee2e2; color: #1f2937; font-family: monospace; font-weight: 600;">03874185200000000007</td>
                        </tr>
                        <tr style="background: #fef2f2;">
                            <td style="padding: 10px; color: #1f2937; font-weight: 500;">PICHINCHA</td>
                            <td style="padding: 10px; color: #4b5563;">Cta. Corriente</td>
                            <td style="padding: 10px; color: #4b5563;">PEN</td>
                            <td style="padding: 10px; color: #1f2937; font-family: monospace; font-weight: 600;">753951</td>
                            <td style="padding: 10px; color: #1f2937; font-family: monospace; font-weight: 600;">04875395100000000008</td>
                        </tr>
                    </tbody>
                </table>
            </div>
            {% endif %}

            <p style="margin-top: 25px;">Nuestro equipo procesará su operación a la brevedad posible. Le mantendremos informado sobre el progreso.</p>

            <p style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #e5e7eb; color: #6b7280; font-size: 13px;">
                <strong>Importante:</strong> Este es un correo automático. Si tiene alguna consulta, por favor responda a este correo o contacte a su asesor.
            </p>

            {% if is_shared_email %}
            <div style="margin-top: 15px; padding: 12px; background: #fffbeb; border-left: 3px solid #f59e0b; border-radius: 4px;">
                <p style="margin: 0; color: #92400e; font-size: 12px;">
                    <strong>ℹ️ Nota:</strong> Este correo electrónico está registrado para más de una empresa/cliente en nuestro sistema. Las notificaciones que reciba pueden corresponder a diferentes operaciones.
                </p>
            </div>
            {% endif %}
        </div>

        <div class="footer">
            <p><strong>QoriCash Trading</strong></p>
            <p>Sistema de Gestión de Operaciones Cambiarias</p>
            <p style="margin-top: 10px;">© 2024 QoriCash Trading V2. Todos los derechos reservados.</p>
        </div>
    </div>
</body>
</html>
"""
        return render_template_string(template, operation=operation, is_shared_email=is_shared_email, other_clients_count=other_clients_count)

    @staticmethod
    def _render_completed_operation_template(operation):
        """Renderizar plantilla HTML para operación completada"""
        template = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f4f4f4; margin: 0; padding: 0; }
        .container { max-width: 600px; margin: 20px auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .header { background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; padding: 30px 20px; text-align: center; }
        .header h1 { margin: 0; font-size: 24px; }
        .content { padding: 30px 20px; }
        .badge { display: inline-block; padding: 5px 15px; border-radius: 20px; font-size: 12px; font-weight: bold; margin: 5px 0; }
        .badge-success { background: #10b981; color: white; }
        .info-row { display: flex; justify-content: space-between; padding: 12px; border-bottom: 1px solid #e5e7eb; }
        .info-row:last-child { border-bottom: none; }
        .info-label { font-weight: 600; color: #6b7280; }
        .info-value { color: #111827; font-weight: 500; }
        .success-box { background: #d1fae5; border-left: 4px solid #10b981; padding: 20px; margin: 20px 0; border-radius: 4px; text-align: center; }
        .footer { background: #f9fafb; padding: 20px; text-align: center; font-size: 12px; color: #6b7280; }
        @media only screen and (max-width: 600px) {
            .info-row { flex-direction: column; }
            .info-label { margin-bottom: 5px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Operacion Completada</h1>
            <p style="margin: 10px 0 0 0; font-size: 14px;">QoriCash Trading</p>
        </div>

        <div class="content">
            <p>Estimado(a) <strong>{{ operation.client.full_name or operation.client.razon_social }}</strong>,</p>
            <p style="margin: -10px 0 15px 0; font-size: 14px; color: #6b7280;">
                <strong>{{ operation.client.document_type or 'Documento' }}:</strong> {{ operation.client.dni }}
            </p>

            <div class="success-box">
                <h2 style="margin: 0; color: #065f46; font-size: 20px;">Operacion Exitosa</h2>
                <p style="margin: 10px 0 0 0; color: #047857;">Su operacion ha sido completada satisfactoriamente</p>
            </div>

            <p>Los detalles de la operación completada son:</p>

            <div style="background: #f9fafb; border-radius: 6px; padding: 15px; margin: 20px 0;">
                <div class="info-row">
                    <span class="info-label">Código de Operación:</span>
                    <span class="info-value"><strong>{{ operation.operation_id }}</strong></span>
                </div>
                <div class="info-row">
                    <span class="info-label">Tipo:</span>
                    <span class="info-value">{{ operation.operation_type }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Monto USD:</span>
                    <span class="info-value" style="font-size: 18px; color: #059669;">$ {{ "{:,.2f}".format(operation.amount_usd) }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Tipo de Cambio:</span>
                    <span class="info-value">{{ "%.4f"|format(operation.exchange_rate) }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Monto PEN:</span>
                    <span class="info-value" style="font-size: 18px; color: #dc2626;">S/ {{ "{:,.2f}".format(operation.amount_pen) }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Fecha de Creación:</span>
                    <span class="info-value">{{ operation.created_at.strftime('%d/%m/%Y %H:%M') }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Fecha de Completado:</span>
                    <span class="info-value"><strong>{{ operation.completed_at.strftime('%d/%m/%Y %H:%M') if operation.completed_at else '-' }}</strong></span>
                </div>
            </div>

            {% if operation.operator_proofs and operation.operator_proofs|length > 0 %}
            <div style="margin: 25px 0; padding: 20px; background: #f0f9ff; border-radius: 8px; border: 1px solid #0ea5e9;">
                <h3 style="margin: 0 0 15px 0; color: #0369a1; font-size: 16px;">Comprobante(s) de Operacion</h3>
                <p style="margin: 0 0 15px 0; color: #334155;">Adjuntamos el comprobante de su operacion completada:</p>
                {% for proof in operation.operator_proofs %}
                <div style="margin: 10px 0;">
                    <a href="{{ proof.comprobante_url if proof.comprobante_url else proof }}"
                       target="_blank"
                       style="display: inline-block; padding: 12px 24px; background: #0ea5e9; color: white; text-decoration: none; border-radius: 6px; font-weight: 600; margin-bottom: 5px;">
                        Ver Comprobante {% if operation.operator_proofs|length > 1 %}{{ loop.index }}{% endif %}
                    </a>
                    {% if proof.comentario %}
                    <p style="margin: 5px 0 0 0; font-size: 13px; color: #475569; font-style: italic;">
                        {{ proof.comentario }}
                    </p>
                    {% endif %}
                </div>
                {% endfor %}
            </div>
            {% endif %}

            <p style="margin-top: 25px;">Gracias por confiar en <strong>QoriCash Trading</strong> para sus operaciones de cambio de divisas.</p>

            <p style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #e5e7eb; color: #6b7280; font-size: 13px;">
                <strong>Nota:</strong> Para cualquier consulta sobre esta operación, puede responder a este correo o contactar a su asesor comercial.
            </p>
        </div>

        <div class="footer">
            <p><strong>QoriCash Trading</strong></p>
            <p>Sistema de Gestión de Operaciones Cambiarias</p>
            <p style="margin-top: 10px;">© 2024 QoriCash Trading V2. Todos los derechos reservados.</p>
        </div>
    </div>
</body>
</html>
"""
        return render_template_string(template, operation=operation)


    @staticmethod
    def send_shared_email_notification(new_client, existing_clients, trader):
        """
        Enviar correo informativo cuando un email se usa para registrar un nuevo cliente

        Args:
            new_client: Nuevo cliente que se está registrando
            existing_clients: Lista de clientes que ya tienen este email
            trader: Usuario que está registrando al nuevo cliente

        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            # NO enviar correos si el usuario que registró el cliente es Plataforma
            # La página web se encarga de enviar sus propios correos
            if trader and trader.role == 'Plataforma':
                logger.info(f'Email de shared email omitido para cliente {new_client.id} - registrado por rol Plataforma')
                return True, 'Email omitido (rol Plataforma)'

            from flask_mail import Message
            from app.extensions import mail

            # Destinatario: El email compartido
            to = EmailService.parse_email_addresses(new_client.email) if new_client.email else []

            if not to:
                return False, 'No hay destinatario para email compartido'

            # Asunto
            subject = 'Notificación: Nuevo Cliente Registrado con su Email - QoriCash'

            # Contenido HTML
            html_body = EmailService._render_shared_email_notification_template(
                new_client, existing_clients, trader
            )

            # Crear mensaje
            msg = Message(
                subject=subject,
                recipients=to,
                html=html_body
            )

            # Enviar
            mail.send(msg)

            logger.info(f'Email de notificación de email compartido enviado: {new_client.id}')
            return True, 'Email de notificación enviado correctamente'

        except Exception as e:
            logger.error(f'Error al enviar email de notificación de email compartido: {str(e)}')
            return False, f'Error al enviar email: {str(e)}'

    @staticmethod
    def _render_shared_email_notification_template(new_client, existing_clients, trader):
        """Renderizar plantilla HTML para notificación de email compartido"""
        template = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f4f4f4; margin: 0; padding: 0; }
        .container { max-width: 600px; margin: 20px auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .header { background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); color: white; padding: 30px 20px; text-align: center; }
        .header h1 { margin: 0; font-size: 24px; }
        .content { padding: 30px 20px; }
        .info-box { background: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; margin: 20px 0; border-radius: 4px; }
        .client-box { background: #f0f9ff; border: 1px solid #0ea5e9; padding: 15px; margin: 15px 0; border-radius: 6px; }
        .footer { background: #f9fafb; padding: 20px; text-align: center; font-size: 12px; color: #6b7280; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>ℹ️ Notificación Informativa</h1>
            <p style="margin: 10px 0 0 0; font-size: 14px;">QoriCash Trading</p>
        </div>

        <div class="content">
            <p>Estimado(a) usuario,</p>

            <p>Le informamos que su correo electrónico <strong>{{ new_client.email }}</strong> ha sido utilizado para registrar un nuevo cliente en QoriCash Trading.</p>

            <div class="info-box">
                <p style="margin: 0 0 10px 0; font-weight: 600; color: #d97706;">⚠️ Esta es una notificación informativa</p>
                <p style="margin: 5px 0; font-size: 14px;">Si usted autorizó este registro, no necesita realizar ninguna acción. Si NO reconoce este registro, por favor contacte inmediatamente con nosotros.</p>
            </div>

            <div class="client-box">
                <p style="margin: 0 0 10px 0; font-weight: 600; color: #0369a1;">📋 Información del Nuevo Cliente Registrado:</p>
                <p style="margin: 5px 0;"><strong>Tipo de Documento:</strong> {{ new_client.document_type }}</p>
                <p style="margin: 5px 0;"><strong>Número de Documento:</strong> {{ new_client.dni }}</p>
                <p style="margin: 5px 0;"><strong>Nombre:</strong> {{ new_client.full_name or new_client.razon_social }}</p>
                {% if new_client.phone %}
                <p style="margin: 5px 0;"><strong>Teléfono:</strong> {{ new_client.phone }}</p>
                {% endif %}
                <p style="margin: 5px 0;"><strong>Email:</strong> {{ new_client.email }}</p>
                <p style="margin: 5px 0;"><strong>Estado:</strong> {{ new_client.status }}</p>
                <p style="margin: 5px 0;"><strong>Registrado por:</strong> {{ trader.username if trader else 'Sistema' }}</p>
            </div>

            {% if existing_clients and existing_clients|length > 0 %}
            <p style="margin-top: 20px; font-size: 14px; color: #475569;">
                <strong>Nota:</strong> Este correo ya está asociado a {{ existing_clients|length }} cliente(s) adicional(es):
            </p>
            <ul style="font-size: 14px; color: #475569;">
                {% for client in existing_clients %}
                <li>{{ client.document_type }} {{ client.dni }} - {{ client.full_name or client.razon_social }}</li>
                {% endfor %}
            </ul>
            {% endif %}

            <p style="margin-top: 25px; padding-top: 20px; border-top: 1px solid #e5e7eb; color: #6b7280; font-size: 13px;">
                <strong>¿No reconoce este registro?</strong><br>
                Si no autorizó este registro, por favor contacte con nosotros inmediatamente respondiendo a este correo o llamando a su ejecutivo asignado.
            </p>
        </div>

        <div class="footer">
            <p><strong>QoriCash Trading</strong></p>
            <p>Sistema de Gestión de Operaciones Cambiarias</p>
            <p style="margin-top: 10px;">© 2024 QoriCash Trading V2. Todos los derechos reservados.</p>
        </div>
    </div>
</body>
</html>
"""
        return render_template_string(template, new_client=new_client, existing_clients=existing_clients, trader=trader)

    @staticmethod
    def send_new_client_registration_email(client, trader):
        """
        Enviar correo de notificación de nuevo cliente registrado

        Args:
            client: Objeto Client
            trader: Objeto User (trader que registró al cliente)

        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            # NO enviar correos si el usuario que registró el cliente es Plataforma
            # La página web se encarga de enviar sus propios correos
            if trader and trader.role == 'Plataforma':
                logger.info(f'Email de nuevo cliente omitido para cliente {client.id} - registrado por rol Plataforma')
                return True, 'Email omitido (rol Plataforma)'

            # Destinatario principal: Cliente (soporta múltiples emails separados por ;)
            to = EmailService.parse_email_addresses(client.email) if client.email else []

            # Copia: Trader que registró al cliente
            cc = []
            if trader and trader.email:
                cc.append(trader.email)

            # Copia oculta: info@qoricash.pe + Master(s)
            bcc = ['info@qoricash.pe']

            masters = User.query.filter(
                User.role == 'Master',
                User.status == 'Activo',
                User.email.isnot(None)
            ).all()

            for master in masters:
                if master.email and master.email not in cc and master.email not in bcc:
                    bcc.append(master.email)

            # Validar que haya al menos un destinatario
            if not to and not cc and not bcc:
                logger.warning(f'No hay destinatarios para el cliente {client.id}')
                return False, 'No hay destinatarios configurados'

            # Asunto
            subject = f'Bienvenido a QoriCash - Registro en Proceso'

            # Contenido HTML
            html_body = EmailService._render_new_client_template(client, trader)

            # Crear mensaje
            msg = Message(
                subject=subject,
                recipients=to,
                cc=cc,
                bcc=bcc,
                html=html_body
            )

            # Enviar
            mail.send(msg)

            logger.info(f'Email de nuevo cliente enviado: {client.id}')
            return True, 'Email enviado correctamente'

        except Exception as e:
            logger.error(f'Error al enviar email de nuevo cliente {client.id}: {str(e)}')
            return False, f'Error al enviar email: {str(e)}'

    @staticmethod
    def send_client_activation_email(client, trader):
        """
        Enviar correo de notificación de cliente activado
        Usa credenciales separadas del email de confirmación con Flask-Mail

        Args:
            client: Objeto Client
            trader: Objeto User (trader que registró al cliente)

        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            # NO enviar correos si el usuario que registró el cliente es Plataforma
            # La página web se encarga de enviar sus propios correos
            if trader and trader.role == 'Plataforma':
                logger.info(f'Email de cliente activado omitido para cliente {client.id} - registrado por rol Plataforma')
                return True, 'Email omitido (rol Plataforma)'

            from flask import current_app
            from flask_mail import Message, Mail

            logger.info(f'[EMAIL] Iniciando envio de email de cliente activado {client.id}')

            # Destinatario principal: Cliente (soporta múltiples emails separados por ;)
            to = EmailService.parse_email_addresses(client.email) if client.email else []

            # Copia: Trader que registró al cliente
            cc = []
            if trader and trader.email:
                cc.append(trader.email)

            # Copia oculta: Solo Master
            bcc = []
            masters = User.query.filter(
                User.role == 'Master',
                User.status == 'Activo',
                User.email.isnot(None)
            ).all()

            for master in masters:
                if master.email and master.email not in cc:
                    bcc.append(master.email)

            logger.info(f'[EMAIL] Destinatarios - TO: {to}, CC: {cc}')

            # Validar que haya al menos un destinatario
            if not to and not cc and not bcc:
                logger.warning(f'No hay destinatarios para el cliente activado {client.id}')
                return False, 'No hay destinatarios configurados'

            # Obtener credenciales del email de confirmación
            confirmation_username = current_app.config.get('MAIL_CONFIRMATION_USERNAME')
            confirmation_password = current_app.config.get('MAIL_CONFIRMATION_PASSWORD')
            confirmation_sender = current_app.config.get('MAIL_CONFIRMATION_SENDER')

            logger.info(f'[EMAIL] Credenciales - Usuario: {confirmation_username}, Remitente: {confirmation_sender}')

            if not confirmation_username or not confirmation_password:
                logger.error('[EMAIL] Credenciales de email de confirmacion no configuradas')
                return False, 'Email de confirmación no configurado'

            # Guardar configuración original
            original_username = current_app.config.get('MAIL_USERNAME')
            original_password = current_app.config.get('MAIL_PASSWORD')
            original_sender = current_app.config.get('MAIL_DEFAULT_SENDER')

            # Sobrescribir temporalmente con credenciales de confirmación
            current_app.config['MAIL_USERNAME'] = confirmation_username
            current_app.config['MAIL_PASSWORD'] = confirmation_password
            current_app.config['MAIL_DEFAULT_SENDER'] = confirmation_sender

            try:
                # Crear un nuevo objeto Mail con la configuración actualizada
                from app.extensions import mail
                mail.init_app(current_app)

                # Asunto
                subject = f'Cuenta Activada - Bienvenido a QoriCash'

                # Contenido HTML
                logger.info(f'[EMAIL] Generando plantilla HTML')
                html_body = EmailService._render_client_activation_template(client, trader)

                # Crear mensaje usando Flask-Mail
                logger.info(f'[EMAIL] Creando mensaje Flask-Mail')
                msg = Message(
                    subject=subject,
                    sender=confirmation_sender,
                    recipients=to,
                    cc=cc if cc else None,
                    bcc=bcc if bcc else None,
                    html=html_body
                )

                # Enviar
                logger.info(f'[EMAIL] Enviando email a TO: {to}, CC: {cc}')
                mail.send(msg)

                logger.info(f'[EMAIL] Email de cliente activado enviado exitosamente desde {confirmation_sender}: {client.id}')
                return True, 'Email enviado correctamente'

            finally:
                # Restaurar configuración original
                current_app.config['MAIL_USERNAME'] = original_username
                current_app.config['MAIL_PASSWORD'] = original_password
                current_app.config['MAIL_DEFAULT_SENDER'] = original_sender
                # Reinicializar mail con configuración original
                mail.init_app(current_app)

        except Exception as e:
            logger.error(f'[EMAIL] ERROR al enviar email de cliente activado {client.id}: {str(e)}')
            logger.exception(e)
            return False, f'Error al enviar email: {str(e)}'

    @staticmethod
    def _render_new_client_template(client, trader):
        """Renderizar plantilla HTML para nuevo cliente registrado"""
        # Obtener cuentas bancarias del cliente
        bank_accounts_text = "No registrado"
        if hasattr(client, 'bank_accounts') and client.bank_accounts:
            try:
                import json
                if isinstance(client.bank_accounts, str):
                    accounts = json.loads(client.bank_accounts)
                else:
                    accounts = client.bank_accounts
                if accounts and isinstance(accounts, list) and len(accounts) > 0:
                    bank_list = []
                    for acc in accounts:
                        bank_name = acc.get('bank_name', '')
                        currency = acc.get('currency', '')
                        acc_number = acc.get('account_number', '')
                        if bank_name and acc_number:
                            bank_list.append(f"{bank_name} | {currency} | {acc_number}")
                    bank_accounts_text = ", ".join(bank_list) if bank_list else "No registrado"
            except:
                bank_accounts_text = "No registrado"

        template = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f4f4f4; margin: 0; padding: 0; }
        .container { max-width: 600px; margin: 20px auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px 20px; text-align: center; }
        .header h1 { margin: 0; font-size: 24px; }
        .content { padding: 30px 20px; }
        .info-box { background: #f9fafb; border-left: 4px solid #667eea; padding: 15px; margin: 20px 0; border-radius: 4px; }
        .footer { background: #f9fafb; padding: 20px; text-align: center; font-size: 12px; color: #6b7280; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Bienvenido a QoriCash</h1>
            <p style="margin: 10px 0 0 0; font-size: 14px;">Cambio de divisas</p>
        </div>

        <div class="content">
            <p>Estimado(a) <strong>{{ client.full_name or client.razon_social }}</strong>,</p>

            <p>Hemos recibido su solicitud de registro por parte de su ejecutivo comercial <strong>{{ trader.username }}</strong>. Nuestro equipo está validando su información y en breve le informaremos sobre la activación de su cuenta.</p>

            <div class="info-box">
                <p style="margin: 0 0 10px 0; font-weight: 600; color: #667eea;">Datos de Registro:</p>
                <p style="margin: 5px 0;"><strong>Cliente:</strong> {{ client.full_name or client.razon_social }}</p>
                {% if client.document_type %}
                <p style="margin: 5px 0;"><strong>Tipo Documento:</strong> {{ client.document_type }}</p>
                {% endif %}
                {% if client.dni %}
                <p style="margin: 5px 0;"><strong>Número Documento:</strong> {{ client.dni }}</p>
                {% endif %}
                {% if client.phone %}
                <p style="margin: 5px 0;"><strong>Teléfono:</strong> {{ client.phone }}</p>
                {% endif %}
                <p style="margin: 5px 0;"><strong>Cuentas Bancarias:</strong> {{ bank_accounts_text }}</p>
                <p style="margin: 5px 0;"><strong>Ejecutivo Asignado:</strong> {{ trader.username }}</p>
            </div>

            <p>Para consultas, contacte a <strong>{{ trader.username }}</strong>{% if trader.email %} al correo {{ trader.email }}{% endif %}.</p>

            <p style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #e5e7eb; color: #6b7280; font-size: 13px;">
                <strong>Importante:</strong> Este es un correo automático.
            </p>
        </div>

        <div class="footer">
            <p><strong>QoriCash</strong></p>
            <p>RUC: 20235842211</p>
            <p>Sistema de Gestión de Operaciones Cambiarias</p>
            <p style="margin-top: 10px;">© 2024 QoriCash. Todos los derechos reservados.</p>
        </div>
    </div>
</body>
</html>
"""
        return render_template_string(template, client=client, trader=trader, bank_accounts_text=bank_accounts_text)

    @staticmethod
    def _render_client_activation_template(client, trader):
        """Renderizar plantilla HTML para cliente activado"""
        template = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f4f4f4; margin: 0; padding: 0; }
        .container { max-width: 600px; margin: 20px auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .header { background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; padding: 30px 20px; text-align: center; }
        .header h1 { margin: 0; font-size: 24px; }
        .content { padding: 30px 20px; }
        .success-box { background: #d1fae5; border-left: 4px solid #10b981; padding: 20px; margin: 20px 0; border-radius: 4px; text-align: center; }
        .info-box { background: #f0f9ff; border-left: 4px solid #3b82f6; padding: 15px; margin: 20px 0; border-radius: 4px; }
        .footer { background: #f9fafb; padding: 20px; text-align: center; font-size: 12px; color: #6b7280; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>¡Cuenta Activada Exitosamente!</h1>
            <p style="margin: 10px 0 0 0; font-size: 14px;">QoriCash</p>
        </div>

        <div class="content">
            <p>Estimado(a) <strong>{{ client.full_name or client.razon_social }}</strong>,</p>

            <div class="success-box">
                <h2 style="margin: 0; color: #065f46; font-size: 20px;">¡Bienvenido a QoriCash!</h2>
                <p style="margin: 10px 0 0 0; color: #047857;">Su cuenta ha sido activada correctamente</p>
            </div>

            <p>Nos complace informarle que su registro ha sido validado exitosamente y su cuenta ya se encuentra <strong>activa</strong> en nuestro sistema.</p>

            <p>A partir de este momento, puede comenzar a realizar operaciones de cambio de divisas con nosotros. Nuestro equipo está listo para atenderle y brindarle el mejor servicio.</p>

            <div class="info-box">
                <p style="margin: 0 0 10px 0; font-weight: 600; color: #1e40af;">Información de su Cuenta:</p>
                <p style="margin: 5px 0;"><strong>Cliente:</strong> {{ client.full_name or client.razon_social }}</p>
                {% if client.document_number or client.dni %}
                <p style="margin: 5px 0;"><strong>Número de documento:</strong> {{ client.document_number or client.dni }}</p>
                {% endif %}
                {% if client.phone %}
                <p style="margin: 5px 0;"><strong>Número de teléfono registrado:</strong> {{ client.phone }}</p>
                {% endif %}
                <p style="margin: 5px 0;"><strong>Estado:</strong> <span style="color: #059669; font-weight: bold;">ACTIVO</span></p>
                <p style="margin: 5px 0;"><strong>Ejecutivo Asignado:</strong> {{ trader.username }}</p>
            </div>

            <p><strong>¿Qué puede hacer ahora?</strong></p>
            <ul style="color: #374151; line-height: 1.8;">
                <li>Realizar operaciones de compra y venta de dólares</li>
                <li>Obtener tipos de cambio competitivos</li>
                <li>Recibir atención personalizada de su ejecutivo</li>
                <li>Acceder a transferencias rápidas y seguras</li>
            </ul>

            <p style="margin-top: 25px;">Para realizar su primera operación o si tiene alguna consulta, puede contactar directamente a su ejecutivo comercial <strong>{{ trader.username }}</strong>{% if trader.email %} al correo {{ trader.email }}{% endif %}.</p>

            <p style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #e5e7eb; color: #6b7280; font-size: 13px;">
                <strong>Gracias por confiar en QoriCash para sus operaciones cambiarias.</strong>
            </p>
        </div>

        <div class="footer">
            <p><strong>QoriCash</strong></p>
            <p>RUC: 20235842211</p>
            <p>Sistema de Gestión de Operaciones Cambiarias</p>
            <p style="margin-top: 10px;">© 2024 QoriCash. Todos los derechos reservados.</p>
        </div>
    </div>
</body>
</html>
"""
        return render_template_string(template, client=client, trader=trader)

    @staticmethod
    def send_canceled_operation_email(operation, reason):
        """
        Enviar correo de notificación de operación cancelada

        Args:
            operation: Objeto Operation
            reason: Motivo de cancelación

        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            # NO enviar correos si el usuario que creó la operación es Plataforma
            # La página web se encarga de enviar sus propios correos
            if operation.user and operation.user.role == 'Plataforma':
                logger.info(f'Email de cancelación omitido para operación {operation.operation_id} - creada por rol Plataforma')
                return True, 'Email omitido (rol Plataforma)'

            to, cc, bcc = EmailService.get_recipients_for_completed_operation(operation)

            # Validar que haya al menos un destinatario
            if not to and not cc:
                logger.warning(f'No hay destinatarios para la operación cancelada {operation.operation_id}')
                return False, 'No hay destinatarios configurados'

            # Asunto
            subject = f'Operación Cancelada #{operation.operation_id} - QoriCash Trading'

            # Contenido HTML
            html_body = EmailService._render_canceled_operation_template(operation, reason)

            # Crear mensaje
            msg = Message(
                subject=subject,
                recipients=to,
                cc=cc,
                html=html_body
            )

            # Enviar
            mail.send(msg)

            logger.info(f'Email de operación cancelada enviado: {operation.operation_id}')
            return True, 'Email enviado correctamente'

        except Exception as e:
            logger.error(f'Error al enviar email de operación cancelada {operation.operation_id}: {str(e)}')
            return False, f'Error al enviar email: {str(e)}'

    @staticmethod
    def _render_canceled_operation_template(operation, reason):
        """Renderizar plantilla HTML para operación cancelada"""
        template = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f4f4f4; margin: 0; padding: 0; }
        .container { max-width: 600px; margin: 20px auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .header { background: linear-gradient(135deg, #dc2626 0%, #991b1b 100%); color: white; padding: 30px 20px; text-align: center; }
        .header h1 { margin: 0; font-size: 24px; }
        .content { padding: 30px 20px; }
        .badge { display: inline-block; padding: 5px 15px; border-radius: 20px; font-size: 12px; font-weight: bold; margin: 5px 0; }
        .badge-canceled { background: #dc2626; color: white; }
        .info-row { display: flex; justify-content: space-between; padding: 12px; border-bottom: 1px solid #e5e7eb; }
        .info-row:last-child { border-bottom: none; }
        .info-label { font-weight: 600; color: #6b7280; }
        .info-value { color: #111827; font-weight: 500; }
        .warning-box { background: #fef2f2; border-left: 4px solid #dc2626; padding: 20px; margin: 20px 0; border-radius: 4px; }
        .reason-box { background: #fff7ed; border-left: 4px solid #f59e0b; padding: 15px; margin: 20px 0; border-radius: 4px; }
        .footer { background: #f9fafb; padding: 20px; text-align: center; font-size: 12px; color: #6b7280; }
        @media only screen and (max-width: 600px) {
            .info-row { flex-direction: column; }
            .info-label { margin-bottom: 5px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⚠️ Operación Cancelada</h1>
            <p style="margin: 10px 0 0 0; font-size: 14px;">QoriCash Trading</p>
        </div>

        <div class="content">
            <p>Estimado(a) <strong>{{ operation.client.full_name or operation.client.razon_social }}</strong>,</p>
            <p style="margin: -10px 0 15px 0; font-size: 14px; color: #6b7280;">
                <strong>{{ operation.client.document_type or 'Documento' }}:</strong> {{ operation.client.dni }}
            </p>

            <div class="warning-box">
                <h2 style="margin: 0; color: #991b1b; font-size: 20px;">Operación Cancelada</h2>
                <p style="margin: 10px 0 0 0; color: #7f1d1d;">Su operación ha sido cancelada</p>
            </div>

            <p>Lamentamos informarle que la operación con código <strong>{{ operation.operation_id }}</strong> ha sido <strong style="color: #dc2626;">CANCELADA</strong>.</p>

            <div class="reason-box">
                <p style="margin: 0 0 5px 0; font-weight: 600; color: #92400e;">Motivo de Cancelación:</p>
                <p style="margin: 0; color: #451a03; font-style: italic;">{{ reason }}</p>
            </div>

            <p><strong>Detalles de la Operación Cancelada:</strong></p>

            <div style="background: #f9fafb; border-radius: 6px; padding: 15px; margin: 20px 0;">
                <div class="info-row">
                    <span class="info-label">Código de Operación:</span>
                    <span class="info-value"><strong>{{ operation.operation_id }}</strong></span>
                </div>
                <div class="info-row">
                    <span class="info-label">Tipo:</span>
                    <span class="info-value">{{ operation.operation_type }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Monto USD:</span>
                    <span class="info-value" style="font-size: 18px; color: #059669;">$ {{ "{:,.2f}".format(operation.amount_usd) }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Tipo de Cambio:</span>
                    <span class="info-value">{{ "%.4f"|format(operation.exchange_rate) }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Monto PEN:</span>
                    <span class="info-value" style="font-size: 18px; color: #dc2626;">S/ {{ "{:,.2f}".format(operation.amount_pen) }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Fecha de Creación:</span>
                    <span class="info-value">{{ operation.created_at.strftime('%d/%m/%Y %H:%M') }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Estado:</span>
                    <span class="info-value"><span class="badge badge-canceled">CANCELADA</span></span>
                </div>
            </div>

            <p style="margin-top: 25px;">Si tiene alguna consulta sobre esta cancelación, por favor contacte a su ejecutivo comercial.</p>

            <p style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #e5e7eb; color: #6b7280; font-size: 13px;">
                <strong>Nota:</strong> Para cualquier consulta sobre esta operación, puede responder a este correo o contactar a su asesor comercial.
            </p>
        </div>

        <div class="footer">
            <p><strong>QoriCash Trading</strong></p>
            <p>Sistema de Gestión de Operaciones Cambiarias</p>
            <p style="margin-top: 10px;">© 2024 QoriCash Trading V2. Todos los derechos reservados.</p>
        </div>
    </div>
</body>
</html>
"""
        return render_template_string(template, operation=operation, reason=reason)

    @staticmethod
    def send_amount_modified_operation_email(operation, old_amount_usd, old_amount_pen):
        """
        Enviar correo de notificación de modificación de monto

        Args:
            operation: Objeto Operation (con nuevos montos)
            old_amount_usd: Monto USD anterior
            old_amount_pen: Monto PEN anterior

        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            # NO enviar correos si el usuario que creó la operación es Plataforma
            # La página web se encarga de enviar sus propios correos
            if operation.user and operation.user.role == 'Plataforma':
                logger.info(f'Email de monto modificado omitido para operación {operation.operation_id} - creada por rol Plataforma')
                return True, 'Email omitido (rol Plataforma)'

            to, cc, bcc = EmailService.get_recipients_for_new_operation(operation)

            # Validar que haya al menos un destinatario
            if not to and not cc and not bcc:
                logger.warning(f'No hay destinatarios para modificación de monto {operation.operation_id}')
                return False, 'No hay destinatarios configurados'

            # Asunto con nombre del trader
            trader_name = operation.user.username if operation.user else 'Sistema'
            subject = f'{trader_name} - Monto Modificado Operación #{operation.operation_id} - QoriCash Trading'

            # Contenido HTML
            html_body = EmailService._render_amount_modified_operation_template(
                operation, old_amount_usd, old_amount_pen
            )

            # Crear mensaje
            msg = Message(
                subject=subject,
                recipients=to,
                cc=cc,
                bcc=bcc,
                html=html_body
            )

            # Enviar
            mail.send(msg)

            logger.info(f'Email de modificación de monto enviado: {operation.operation_id}')
            return True, 'Email enviado correctamente'

        except Exception as e:
            logger.error(f'Error al enviar email de modificación de monto {operation.operation_id}: {str(e)}')
            return False, f'Error al enviar email: {str(e)}'

    @staticmethod
    def _render_amount_modified_operation_template(operation, old_amount_usd, old_amount_pen):
        """Renderizar plantilla HTML para modificación de monto"""
        template = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f4f4f4; margin: 0; padding: 0; }
        .container { max-width: 600px; margin: 20px auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .header { background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); color: white; padding: 30px 20px; text-align: center; }
        .header h1 { margin: 0; font-size: 24px; }
        .content { padding: 30px 20px; }
        .badge { display: inline-block; padding: 5px 15px; border-radius: 20px; font-size: 12px; font-weight: bold; margin: 5px 0; }
        .badge-modified { background: #f59e0b; color: white; }
        .badge-success { background: #10b981; color: white; }
        .badge-primary { background: #3b82f6; color: white; }
        .info-row { display: flex; justify-content: space-between; padding: 12px; border-bottom: 1px solid #e5e7eb; }
        .info-row:last-child { border-bottom: none; }
        .info-label { font-weight: 600; color: #6b7280; }
        .info-value { color: #111827; font-weight: 500; }
        .highlight-box { background: #fff7ed; border-left: 4px solid #f59e0b; padding: 15px; margin: 20px 0; border-radius: 4px; }
        .comparison-box { background: #f0f9ff; border: 2px solid #0ea5e9; padding: 20px; margin: 20px 0; border-radius: 6px; }
        .old-value { color: #dc2626; text-decoration: line-through; font-size: 16px; }
        .new-value { color: #059669; font-weight: bold; font-size: 18px; }
        .arrow { color: #f59e0b; font-size: 20px; margin: 0 10px; }
        .footer { background: #f9fafb; padding: 20px; text-align: center; font-size: 12px; color: #6b7280; }
        @media only screen and (max-width: 600px) {
            .info-row { flex-direction: column; }
            .info-label { margin-bottom: 5px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📝 Monto Modificado</h1>
            <p style="margin: 10px 0 0 0; font-size: 14px;">QoriCash Trading</p>
        </div>

        <div class="content">
            <p>Estimado(a) <strong>{{ operation.client.full_name or operation.client.razon_social }}</strong>,</p>
            <p style="margin: -10px 0 15px 0; font-size: 14px; color: #6b7280;">
                <strong>{{ operation.client.document_type or 'Documento' }}:</strong> {{ operation.client.dni }}
            </p>

            <p>Le informamos que el <strong>monto de su operación</strong> ha sido modificado. A continuación los detalles:</p>

            <div class="highlight-box">
                <p style="margin: 0 0 5px 0; font-weight: 600; color: #92400e;">Operación:</p>
                <p style="margin: 0; font-size: 18px;"><strong>{{ operation.operation_id }}</strong></p>
            </div>

            <div class="comparison-box">
                <h3 style="margin: 0 0 15px 0; color: #0369a1;">Cambios Realizados:</h3>

                <div style="margin: 15px 0;">
                    <p style="margin: 0 0 8px 0; font-weight: 600; color: #374151;">Monto USD:</p>
                    <div style="display: flex; align-items: center; flex-wrap: wrap;">
                        <span class="old-value">$ {{ "{:,.2f}".format(old_amount_usd) }}</span>
                        <span class="arrow">→</span>
                        <span class="new-value">$ {{ "{:,.2f}".format(operation.amount_usd) }}</span>
                    </div>
                </div>

                <div style="margin: 15px 0;">
                    <p style="margin: 0 0 8px 0; font-weight: 600; color: #374151;">Monto PEN:</p>
                    <div style="display: flex; align-items: center; flex-wrap: wrap;">
                        <span class="old-value">S/ {{ "{:,.2f}".format(old_amount_pen) }}</span>
                        <span class="arrow">→</span>
                        <span class="new-value">S/ {{ "{:,.2f}".format(operation.amount_pen) }}</span>
                    </div>
                </div>
            </div>

            <p><strong>Detalles Actuales de la Operación:</strong></p>

            <div style="background: #f9fafb; border-radius: 6px; padding: 15px; margin: 20px 0;">
                <div class="info-row">
                    <span class="info-label">Código de Operación:</span>
                    <span class="info-value"><strong>{{ operation.operation_id }}</strong></span>
                </div>
                <div class="info-row">
                    <span class="info-label">Tipo:</span>
                    <span class="info-value">
                        {% if operation.operation_type == 'Compra' %}
                            <span class="badge badge-success">COMPRA USD</span>
                        {% else %}
                            <span class="badge badge-primary">VENTA USD</span>
                        {% endif %}
                    </span>
                </div>
                <div class="info-row">
                    <span class="info-label">Monto USD:</span>
                    <span class="info-value" style="font-size: 18px; color: #059669;">$ {{ "{:,.2f}".format(operation.amount_usd) }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Tipo de Cambio:</span>
                    <span class="info-value">{{ "%.4f"|format(operation.exchange_rate) }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Monto PEN:</span>
                    <span class="info-value" style="font-size: 18px; color: #dc2626;">S/ {{ "{:,.2f}".format(operation.amount_pen) }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Estado:</span>
                    <span class="info-value"><strong>{{ operation.status }}</strong></span>
                </div>
                <div class="info-row">
                    <span class="info-label">Fecha:</span>
                    <span class="info-value">{{ operation.created_at.strftime('%d/%m/%Y %H:%M') }}</span>
                </div>
            </div>

            <!-- Cuentas bancarias para transferencia (solo si está Pendiente) -->
            {% if operation.status == 'Pendiente' %}
                {% if operation.operation_type == 'Compra' %}
                <div style="margin: 25px 0; padding: 20px; background: #ecfdf5; border-radius: 8px; border: 2px solid #10b981;">
                    <h3 style="margin: 0 0 15px 0; color: #065f46; font-size: 16px;">Cuentas para Transferencia (USD)</h3>
                    <p style="margin: 0 0 10px 0; color: #374151; font-size: 14px;">Por favor, realice su transferencia en cualquiera de las siguientes cuentas en DOLARES:</p>
                    <p style="margin: 0 0 15px 0; color: #065f46; font-size: 13px; font-weight: 600;">- A nombre de QORICASH SAC con número de RUC 20235842211</p>
                    <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                        <thead>
                            <tr style="background: #d1fae5;">
                                <th style="padding: 10px; text-align: left; border-bottom: 2px solid #10b981; color: #065f46; font-weight: 600;">Banco</th>
                                <th style="padding: 10px; text-align: left; border-bottom: 2px solid #10b981; color: #065f46; font-weight: 600;">Tipo</th>
                                <th style="padding: 10px; text-align: left; border-bottom: 2px solid #10b981; color: #065f46; font-weight: 600;">Moneda</th>
                                <th style="padding: 10px; text-align: left; border-bottom: 2px solid #10b981; color: #065f46; font-weight: 600;">Numero de Cuenta</th>
                                <th style="padding: 10px; text-align: left; border-bottom: 2px solid #10b981; color: #065f46; font-weight: 600;">Numero de CCI</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr style="background: white;">
                                <td style="padding: 10px; border-bottom: 1px solid #d1fae5; color: #1f2937; font-weight: 500;">BCP</td>
                                <td style="padding: 10px; border-bottom: 1px solid #d1fae5; color: #4b5563;">Cta. Corriente</td>
                                <td style="padding: 10px; border-bottom: 1px solid #d1fae5; color: #4b5563;">USD</td>
                                <td style="padding: 10px; border-bottom: 1px solid #d1fae5; color: #1f2937; font-family: monospace; font-weight: 600;">654321</td>
                                <td style="padding: 10px; border-bottom: 1px solid #d1fae5; color: #1f2937; font-family: monospace; font-weight: 600;">00265432100000000001</td>
                            </tr>
                            <tr style="background: #f0fdf4;">
                                <td style="padding: 10px; border-bottom: 1px solid #d1fae5; color: #1f2937; font-weight: 500;">INTERBANK</td>
                                <td style="padding: 10px; border-bottom: 1px solid #d1fae5; color: #4b5563;">Cta. Corriente</td>
                                <td style="padding: 10px; border-bottom: 1px solid #d1fae5; color: #4b5563;">USD</td>
                                <td style="padding: 10px; border-bottom: 1px solid #d1fae5; color: #1f2937; font-family: monospace; font-weight: 600;">456789</td>
                                <td style="padding: 10px; border-bottom: 1px solid #d1fae5; color: #1f2937; font-family: monospace; font-weight: 600;">00345678900000000002</td>
                            </tr>
                            <tr style="background: white;">
                                <td style="padding: 10px; border-bottom: 1px solid #d1fae5; color: #1f2937; font-weight: 500;">BANBIF</td>
                                <td style="padding: 10px; border-bottom: 1px solid #d1fae5; color: #4b5563;">Cta. Corriente</td>
                                <td style="padding: 10px; border-bottom: 1px solid #d1fae5; color: #4b5563;">USD</td>
                                <td style="padding: 10px; border-bottom: 1px solid #d1fae5; color: #1f2937; font-family: monospace; font-weight: 600;">369852</td>
                                <td style="padding: 10px; border-bottom: 1px solid #d1fae5; color: #1f2937; font-family: monospace; font-weight: 600;">03836985200000000003</td>
                            </tr>
                            <tr style="background: #f0fdf4;">
                                <td style="padding: 10px; color: #1f2937; font-weight: 500;">PICHINCHA</td>
                                <td style="padding: 10px; color: #4b5563;">Cta. Corriente</td>
                                <td style="padding: 10px; color: #4b5563;">USD</td>
                                <td style="padding: 10px; color: #1f2937; font-family: monospace; font-weight: 600;">159796</td>
                                <td style="padding: 10px; color: #1f2937; font-family: monospace; font-weight: 600;">04815979600000000004</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                {% elif operation.operation_type == 'Venta' %}
                <div style="margin: 25px 0; padding: 20px; background: #fef2f2; border-radius: 8px; border: 2px solid #ef4444;">
                    <h3 style="margin: 0 0 15px 0; color: #991b1b; font-size: 16px;">Cuentas para Transferencia (PEN)</h3>
                    <p style="margin: 0 0 10px 0; color: #374151; font-size: 14px;">Por favor, realice su transferencia en cualquiera de las siguientes cuentas en SOLES:</p>
                    <p style="margin: 0 0 15px 0; color: #991b1b; font-size: 13px; font-weight: 600;">- A nombre de QORICASH SAC con número de RUC 20235842211</p>
                    <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                        <thead>
                            <tr style="background: #fee2e2;">
                                <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ef4444; color: #991b1b; font-weight: 600;">Banco</th>
                                <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ef4444; color: #991b1b; font-weight: 600;">Tipo</th>
                                <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ef4444; color: #991b1b; font-weight: 600;">Moneda</th>
                                <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ef4444; color: #991b1b; font-weight: 600;">Numero de Cuenta</th>
                                <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ef4444; color: #991b1b; font-weight: 600;">Numero de CCI</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr style="background: white;">
                                <td style="padding: 10px; border-bottom: 1px solid #fee2e2; color: #1f2937; font-weight: 500;">BCP</td>
                                <td style="padding: 10px; border-bottom: 1px solid #fee2e2; color: #4b5563;">Cta. Corriente</td>
                                <td style="padding: 10px; border-bottom: 1px solid #fee2e2; color: #4b5563;">PEN</td>
                                <td style="padding: 10px; border-bottom: 1px solid #fee2e2; color: #1f2937; font-family: monospace; font-weight: 600;">123456</td>
                                <td style="padding: 10px; border-bottom: 1px solid #fee2e2; color: #1f2937; font-family: monospace; font-weight: 600;">00212345600000000005</td>
                            </tr>
                            <tr style="background: #fef2f2;">
                                <td style="padding: 10px; border-bottom: 1px solid #fee2e2; color: #1f2937; font-weight: 500;">INTERBANK</td>
                                <td style="padding: 10px; border-bottom: 1px solid #fee2e2; color: #4b5563;">Cta. Corriente</td>
                                <td style="padding: 10px; border-bottom: 1px solid #fee2e2; color: #4b5563;">PEN</td>
                                <td style="padding: 10px; border-bottom: 1px solid #fee2e2; color: #1f2937; font-family: monospace; font-weight: 600;">987654</td>
                                <td style="padding: 10px; border-bottom: 1px solid #fee2e2; color: #1f2937; font-family: monospace; font-weight: 600;">00398765400000000006</td>
                            </tr>
                            <tr style="background: white;">
                                <td style="padding: 10px; border-bottom: 1px solid #fee2e2; color: #1f2937; font-weight: 500;">BANBIF</td>
                                <td style="padding: 10px; border-bottom: 1px solid #fee2e2; color: #4b5563;">Cta. Corriente</td>
                                <td style="padding: 10px; border-bottom: 1px solid #fee2e2; color: #4b5563;">PEN</td>
                                <td style="padding: 10px; border-bottom: 1px solid #fee2e2; color: #1f2937; font-family: monospace; font-weight: 600;">741852</td>
                                <td style="padding: 10px; border-bottom: 1px solid #fee2e2; color: #1f2937; font-family: monospace; font-weight: 600;">03874185200000000007</td>
                            </tr>
                            <tr style="background: #fef2f2;">
                                <td style="padding: 10px; color: #1f2937; font-weight: 500;">PICHINCHA</td>
                                <td style="padding: 10px; color: #4b5563;">Cta. Corriente</td>
                                <td style="padding: 10px; color: #4b5563;">PEN</td>
                                <td style="padding: 10px; color: #1f2937; font-family: monospace; font-weight: 600;">753951</td>
                                <td style="padding: 10px; color: #1f2937; font-family: monospace; font-weight: 600;">04875395100000000008</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                {% endif %}
            {% endif %}

            <p style="margin-top: 25px;">Nuestro equipo procesará su operación con el nuevo monto. Le mantendremos informado sobre el progreso.</p>

            <p style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #e5e7eb; color: #6b7280; font-size: 13px;">
                <strong>Importante:</strong> Este es un correo automático. Si tiene alguna consulta, por favor responda a este correo o contacte a su asesor.
            </p>
        </div>

        <div class="footer">
            <p><strong>QoriCash Trading</strong></p>
            <p>Sistema de Gestión de Operaciones Cambiarias</p>
            <p style="margin-top: 10px;">© 2024 QoriCash Trading V2. Todos los derechos reservados.</p>
        </div>
    </div>
</body>
</html>
"""
        return render_template_string(template, operation=operation, old_amount_usd=old_amount_usd, old_amount_pen=old_amount_pen)
