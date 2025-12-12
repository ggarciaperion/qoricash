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
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #2c3e50; background-color: #f4f6f9; margin: 0; padding: 20px; }
        .container { max-width: 600px; margin: 0 auto; background: #FFFFFF; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); border: 1px solid #e1e8ed; }
        .header { background: linear-gradient(135deg, #0D1B2A 0%, #1a2942 100%); padding: 25px 20px; text-align: center; border-bottom: none; }
        .logo { max-width: 180px; height: auto; margin-bottom: 15px; }
        .header h1 { margin: 15px 0 5px 0; font-size: 26px; color: #FFFFFF; font-weight: 700; }
        .header p { margin: 5px 0 0 0; font-size: 14px; color: white; font-weight: 600; }
        .content { padding: 30px 25px; color: #2c3e50; }
        .greeting { font-size: 16px; margin-bottom: 20px; }
        .greeting strong { color: #00a887; }
        .client-info { font-size: 13px; color: #6c757d; margin: -10px 0 20px 0; }
        .intro-text { margin-bottom: 25px; line-height: 1.8; }
        .highlight-box { background: #f8fafb; border: 2px solid #d0ebe6; border-radius: 8px; padding: 20px; margin: 25px 0; }
        .info-row { display: flex; justify-content: space-between; padding: 14px 0; border-bottom: 1px solid #e1e8ed; }
        .info-row:last-child { border-bottom: none; }
        .info-label { font-weight: 600; color: #6c757d; font-size: 14px; }
        .info-value { color: #2c3e50; font-weight: 600; font-size: 14px; text-align: right; }
        .badge { display: inline-block; padding: 6px 16px; border-radius: 20px; font-size: 12px; font-weight: bold; margin: 0; }
        .badge-compra { background: linear-gradient(135deg, #d0ebe6, #e8f5f1); color: #00a887; border: 1px solid #00a887; }
        .badge-venta { background: linear-gradient(135deg, #d0ebe6, #e8f5f1); color: #00a887; border: 1px solid #00a887; }
        .amount-usd { font-size: 20px; color: #00a887; font-weight: 700; }
        .amount-pen { font-size: 20px; color: #00a887; font-weight: 700; }
        .bank-section { margin: 30px 0; padding: 25px; background: #f8fafb; border-radius: 8px; border: 2px solid #d0ebe6; }
        .bank-section h3 { margin: 0 0 12px 0; color: #00a887; font-size: 18px; font-weight: 700; }
        .bank-section p { color: #495057; font-size: 14px; margin: 8px 0; line-height: 1.6; }
        .bank-section .company-name { color: #00a887; font-weight: 700; }
        .bank-table { width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 15px; }
        .bank-table thead tr { background: #e8f5f1; }
        .bank-table th { padding: 12px 10px; text-align: left; border-bottom: 2px solid #d0ebe6; color: #00a887; font-weight: 700; font-size: 12px; }
        .bank-table td { padding: 12px 10px; border-bottom: 1px solid #e1e8ed; color: #2c3e50; }
        .bank-table tbody tr:nth-child(even) { background: #f8fafb; }
        .bank-table tbody tr:last-child td { border-bottom: none; }
        .bank-table .bank-name { font-weight: 700; color: #00a887; }
        .bank-table .account-number { font-family: 'Courier New', monospace; font-weight: 600; }
        .note-box { margin-top: 30px; padding: 18px; background: #f8fafb; border-left: 4px solid #00a887; border-radius: 4px; }
        .note-box p { margin: 0; color: #495057; font-size: 13px; line-height: 1.6; }
        .note-box strong { color: #00a887; }
        .warning-box { margin-top: 20px; padding: 15px; background: #fff3cd; border-left: 3px solid #FFB020; border-radius: 4px; }
        .warning-box p { margin: 0; color: #856404; font-size: 12px; }
        .footer { background: #f8fafb; padding: 25px 20px; text-align: center; font-size: 12px; color: #6c757d; border-top: 2px solid #d0ebe6; }
        .footer p { margin: 8px 0; }
        .footer strong { color: #00a887; }
        .divider { height: 1px; background: linear-gradient(90deg, transparent, #d0ebe6, transparent); margin: 25px 0; }
        @media only screen and (max-width: 600px) {
            body { padding: 10px; }
            .content { padding: 25px 15px; }
            .info-row { flex-direction: column; }
            .info-value { text-align: left; margin-top: 5px; }
            .bank-table { font-size: 11px; }
            .bank-table th, .bank-table td { padding: 8px 5px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <img src="https://cdn.jsdelivr.net/gh/ggarciaperion/qoricash@main/app/static/images/logo-email.png" alt="QoriCash Logo" class="logo" style="max-width: 200px; height: auto;">
            <h1>Nueva Operación Registrada</h1>
            <p>QoriCash Trading</p>
        </div>

        <div class="content">
            <p class="greeting">Estimado(a) <strong>{{ operation.client.full_name or operation.client.razon_social }}</strong>,</p>
            <p class="client-info">
                <strong>{{ operation.client.document_type or 'Documento' }}:</strong> {{ operation.client.dni }}
            </p>

            <p class="intro-text">Se ha registrado exitosamente una nueva operación de cambio de divisas con los siguientes detalles:</p>

            <div class="highlight-box">
                <div class="info-row">
                    <span class="info-label">Código de Operación:</span>
                    <span class="info-value"><strong>{{ operation.operation_id }}</strong></span>
                </div>
                <div class="info-row">
                    <span class="info-label">Tipo de Operación:</span>
                    <span class="info-value">
                        {% if operation.operation_type == 'Compra' %}
                            <span class="badge badge-compra">COMPRA USD</span>
                        {% else %}
                            <span class="badge badge-venta">VENTA USD</span>
                        {% endif %}
                    </span>
                </div>
                <div class="info-row">
                    <span class="info-label">Monto en Dólares:</span>
                    <span class="info-value amount-usd">$ {{ "{:,.2f}".format(operation.amount_usd) }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Tipo de Cambio:</span>
                    <span class="info-value">S/ {{ "%.4f"|format(operation.exchange_rate) }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Monto en Soles:</span>
                    <span class="info-value amount-pen">S/ {{ "{:,.2f}".format(operation.amount_pen) }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Estado:</span>
                    <span class="info-value">
                        {% if operation.status == 'Pendiente' %}
                            <strong style="color: #f59e0b;">{{ operation.status }}</strong>
                        {% elif operation.status == 'Completada' %}
                            <strong style="color: #10b981;">{{ operation.status }}</strong>
                        {% elif operation.status == 'Cancelada' %}
                            <strong style="color: #ef4444;">{{ operation.status }}</strong>
                        {% else %}
                            <strong style="color: #00a887;">{{ operation.status }}</strong>
                        {% endif %}
                    </span>
                </div>
                <div class="info-row">
                    <span class="info-label">Fecha de Registro:</span>
                    <span class="info-value">{{ operation.created_at.strftime('%d/%m/%Y %H:%M') }}</span>
                </div>
            </div>

            <!-- Cuentas bancarias para transferencia -->
            {% if operation.operation_type == 'Compra' %}
            <div class="bank-section">
                <h3>💵 Cuentas para Transferencia en DÓLARES (USD)</h3>
                <p>Por favor, realice su transferencia a cualquiera de las siguientes cuentas bancarias:</p>
                <p class="company-name">A nombre de: QORICASH SAC | RUC: 20615113698</p>
                <table class="bank-table">
                    <thead>
                        <tr>
                            <th>Banco</th>
                            <th>Tipo</th>
                            <th>Moneda</th>
                            <th>N° Cuenta</th>
                            <th>CCI</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td class="bank-name">BCP</td>
                            <td>Cta. Corriente</td>
                            <td>USD</td>
                            <td class="account-number">654321</td>
                            <td class="account-number">00265432100000000001</td>
                        </tr>
                        <tr>
                            <td class="bank-name">INTERBANK</td>
                            <td>Cta. Corriente</td>
                            <td>USD</td>
                            <td class="account-number">456789</td>
                            <td class="account-number">00345678900000000002</td>
                        </tr>
                        <tr>
                            <td class="bank-name">BANBIF</td>
                            <td>Cta. Corriente</td>
                            <td>USD</td>
                            <td class="account-number">369852</td>
                            <td class="account-number">03836985200000000003</td>
                        </tr>
                        <tr>
                            <td class="bank-name">PICHINCHA</td>
                            <td>Cta. Corriente</td>
                            <td>USD</td>
                            <td class="account-number">159796</td>
                            <td class="account-number">04815979600000000004</td>
                        </tr>
                    </tbody>
                </table>
            </div>
            {% elif operation.operation_type == 'Venta' %}
            <div class="bank-section">
                <h3>💰 Cuentas para Transferencia en SOLES (PEN)</h3>
                <p>Por favor, realice su transferencia a cualquiera de las siguientes cuentas bancarias:</p>
                <p class="company-name">A nombre de: QORICASH SAC | RUC: 20615113698</p>
                <table class="bank-table">
                    <thead>
                        <tr>
                            <th>Banco</th>
                            <th>Tipo</th>
                            <th>Moneda</th>
                            <th>N° Cuenta</th>
                            <th>CCI</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td class="bank-name">BCP</td>
                            <td>Cta. Corriente</td>
                            <td>PEN</td>
                            <td class="account-number">123456</td>
                            <td class="account-number">00212345600000000005</td>
                        </tr>
                        <tr>
                            <td class="bank-name">INTERBANK</td>
                            <td>Cta. Corriente</td>
                            <td>PEN</td>
                            <td class="account-number">987654</td>
                            <td class="account-number">00398765400000000006</td>
                        </tr>
                        <tr>
                            <td class="bank-name">BANBIF</td>
                            <td>Cta. Corriente</td>
                            <td>PEN</td>
                            <td class="account-number">741852</td>
                            <td class="account-number">03874185200000000007</td>
                        </tr>
                        <tr>
                            <td class="bank-name">PICHINCHA</td>
                            <td>Cta. Corriente</td>
                            <td>PEN</td>
                            <td class="account-number">753951</td>
                            <td class="account-number">04875395100000000008</td>
                        </tr>
                    </tbody>
                </table>
            </div>
            {% endif %}

            <div class="divider"></div>

            <p style="margin-top: 25px; line-height: 1.8;">Nuestro equipo procesará su operación a la brevedad posible. Le mantendremos informado sobre el progreso en cada etapa del proceso.</p>

            <div class="note-box">
                <p><strong>Importante:</strong> Este es un correo automático generado por nuestro sistema. Si tiene alguna consulta o necesita asistencia, por favor responda a este correo o contacte directamente a su asesor comercial.</p>
            </div>

            {% if is_shared_email %}
            <div class="warning-box">
                <p><strong>ℹ️ Aviso:</strong> Este correo electrónico está registrado para múltiples empresas/clientes en nuestro sistema. Las notificaciones que reciba pueden corresponder a diferentes operaciones.</p>
            </div>
            {% endif %}
        </div>

        <div class="footer">
            <p><strong>QoriCash Trading</strong></p>
            <p>Sistema de Gestión de Operaciones Cambiarias</p>
            <p style="margin-top: 12px;">© 2025 QoriCash Trading. Todos los derechos reservados.</p>
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
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #2c3e50; background-color: #f4f6f9; margin: 0; padding: 20px; }
        .container { max-width: 600px; margin: 0 auto; background: #FFFFFF; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); border: 1px solid #e1e8ed; }
        .header { background: linear-gradient(135deg, #0D1B2A 0%, #1a2942 100%); padding: 25px 20px; text-align: center; border-bottom: none; }
        .logo { max-width: 180px; height: auto; margin-bottom: 15px; }
        .header h1 { margin: 15px 0 5px 0; font-size: 26px; color: #FFFFFF; font-weight: 700; }
        .header p { margin: 5px 0 0 0; font-size: 14px; color: white; font-weight: 600; }
        .content { padding: 30px 25px; color: #2c3e50; }
        .greeting { font-size: 16px; margin-bottom: 20px; }
        .greeting strong { color: #00a887; }
        .client-info { font-size: 13px; color: #6c757d; margin: -10px 0 20px 0; }
        .success-box { background: linear-gradient(135deg, #e8f5f1, #d0ebe6); padding: 25px; margin: 25px 0; border-radius: 8px; text-align: center; box-shadow: 0 2px 8px rgba(0,168,135,0.1); }
        .success-box h2 { margin: 0; color: #00a887; font-size: 22px; font-weight: 700; }
        .success-box p { margin: 10px 0 0 0; color: #00a887; font-weight: 600; }
        .success-icon { font-size: 48px; margin-bottom: 10px; }
        .intro-text { margin-bottom: 25px; line-height: 1.8; }
        .highlight-box { background: #f8fafb; border: 2px solid #d0ebe6; border-radius: 8px; padding: 20px; margin: 25px 0; }
        .info-row { display: flex; justify-content: space-between; padding: 14px 0; border-bottom: 1px solid #e1e8ed; }
        .info-row:last-child { border-bottom: none; }
        .info-label { font-weight: 600; color: #6c757d; font-size: 14px; }
        .info-value { color: #2c3e50; font-weight: 600; font-size: 14px; text-align: right; }
        .amount-usd { font-size: 20px; color: #00a887; font-weight: 700; }
        .amount-pen { font-size: 20px; color: #00a887; font-weight: 700; }
        .proof-section { margin: 30px 0; padding: 25px; background: #f8fafb; border-radius: 8px; border: 2px solid #d0ebe6; }
        .proof-section h3 { margin: 0 0 12px 0; color: #00a887; font-size: 18px; font-weight: 700; }
        .proof-section p { color: #495057; font-size: 14px; margin: 8px 0; line-height: 1.6; }
        .btn-proof { display: inline-block; padding: 14px 28px; background: linear-gradient(135deg, #d0ebe6, #e8f5f1); color: #00a887; text-decoration: none; border-radius: 6px; font-weight: 700; margin: 10px 0; transition: transform 0.2s; border: 1px solid #00a887; }
        .btn-proof:hover { transform: translateY(-2px); }
        .proof-comment { font-size: 13px; color: #6c757d; font-style: italic; margin: 8px 0; }
        .note-box { margin-top: 30px; padding: 18px; background: #f8fafb; border-left: 4px solid #00a887; border-radius: 4px; }
        .note-box p { margin: 0; color: #495057; font-size: 13px; line-height: 1.6; }
        .note-box strong { color: #00a887; }
        .footer { background: #f8fafb; padding: 25px 20px; text-align: center; font-size: 12px; color: #6c757d; border-top: 2px solid #d0ebe6; }
        .footer p { margin: 8px 0; }
        .footer strong { color: #00a887; }
        .divider { height: 1px; background: linear-gradient(90deg, transparent, #d0ebe6, transparent); margin: 25px 0; }
        @media only screen and (max-width: 600px) {
            body { padding: 10px; }
            .content { padding: 25px 15px; }
            .info-row { flex-direction: column; }
            .info-value { text-align: left; margin-top: 5px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <img src="https://cdn.jsdelivr.net/gh/ggarciaperion/qoricash@main/app/static/images/logo-email.png" alt="QoriCash Logo" class="logo" style="max-width: 200px; height: auto;">
            <h1>Operación Completada</h1>
            <p>QoriCash Trading</p>
        </div>

        <div class="content">
            <p class="greeting">Estimado(a) <strong>{{ operation.client.full_name or operation.client.razon_social }}</strong>,</p>
            <p class="client-info">
                <strong>{{ operation.client.document_type or 'Documento' }}:</strong> {{ operation.client.dni }}
            </p>

            <div class="success-box">
                <div class="success-icon">✓</div>
                <h2>¡Operación Exitosa!</h2>
                <p>Su operación ha sido completada satisfactoriamente</p>
            </div>

            <p class="intro-text">Los detalles de la operación completada son los siguientes:</p>

            <div class="highlight-box">
                <div class="info-row">
                    <span class="info-label">Código de Operación:</span>
                    <span class="info-value"><strong>{{ operation.operation_id }}</strong></span>
                </div>
                <div class="info-row">
                    <span class="info-label">Tipo de Operación:</span>
                    <span class="info-value">{{ operation.operation_type }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Monto en Dólares:</span>
                    <span class="info-value amount-usd">$ {{ "{:,.2f}".format(operation.amount_usd) }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Tipo de Cambio:</span>
                    <span class="info-value">S/ {{ "%.4f"|format(operation.exchange_rate) }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Monto en Soles:</span>
                    <span class="info-value amount-pen">S/ {{ "{:,.2f}".format(operation.amount_pen) }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Fecha de Creación:</span>
                    <span class="info-value">{{ operation.created_at.strftime('%d/%m/%Y %H:%M') }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Fecha de Completado:</span>
                    <span class="info-value"><strong style="color: #00FFAA;">{{ operation.completed_at.strftime('%d/%m/%Y %H:%M') if operation.completed_at else '-' }}</strong></span>
                </div>
            </div>

            {% if operation.operator_proofs and operation.operator_proofs|length > 0 %}
            <div class="proof-section">
                <h3>📄 Comprobante(s) de Operación</h3>
                <p>Adjuntamos el(los) comprobante(s) de su operación completada:</p>
                {% for proof in operation.operator_proofs %}
                <div style="margin: 15px 0;">
                    <a href="{{ proof.comprobante_url if proof.comprobante_url else proof }}"
                       target="_blank"
                       class="btn-proof">
                        📥 Ver Comprobante {% if operation.operator_proofs|length > 1 %}{{ loop.index }}{% endif %}
                    </a>
                    {% if proof.comentario %}
                    <p class="proof-comment">{{ proof.comentario }}</p>
                    {% endif %}
                </div>
                {% endfor %}
            </div>
            {% endif %}

            <div class="divider"></div>

            <p style="margin-top: 25px; text-align: center; font-size: 16px; line-height: 1.8;">
                Gracias por confiar en <strong style="color: #00FFAA;">QoriCash Trading</strong> para sus operaciones de cambio de divisas.
            </p>

            <div class="note-box">
                <p><strong>Nota:</strong> Para cualquier consulta sobre esta operación, puede responder a este correo o contactar directamente a su asesor comercial.</p>
            </div>
        </div>

        <div class="footer">
            <p><strong>QoriCash Trading</strong></p>
            <p>Sistema de Gestión de Operaciones Cambiarias</p>
            <p style="margin-top: 12px;">© 2025 QoriCash Trading. Todos los derechos reservados.</p>
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
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #2c3e50; background-color: #f4f6f9; margin: 0; padding: 20px; }
        .container { max-width: 600px; margin: 0 auto; background: #FFFFFF; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); border: 1px solid #e1e8ed; }
        .header { background: linear-gradient(135deg, #0D1B2A 0%, #1a2942 100%); padding: 25px 20px; text-align: center; border-bottom: none; }
        .logo { max-width: 180px; height: auto; margin-bottom: 15px; }
        .header h1 { margin: 15px 0 5px 0; font-size: 26px; color: #FFFFFF; font-weight: 700; }
        .header p { margin: 5px 0 0 0; font-size: 14px; color: white; font-weight: 600; }
        .content { padding: 30px 25px; color: #2c3e50; }
        .greeting { font-size: 16px; margin-bottom: 20px; }
        .intro-text { margin-bottom: 25px; line-height: 1.8; }
        .intro-text strong { color: #00a887; }
        .info-box { background: #fff3cd; border-left: 4px solid #FFB020; padding: 18px; margin: 25px 0; border-radius: 4px; }
        .info-box p { margin: 0; color: #856404; font-size: 14px; line-height: 1.6; }
        .info-box .warning-icon { color: #FFB020; font-weight: 700; }
        .client-box { background: #f8fafb; border: 2px solid #d0ebe6; padding: 20px; margin: 25px 0; border-radius: 8px; }
        .client-box .title { margin: 0 0 15px 0; font-weight: 700; color: #00a887; font-size: 16px; }
        .client-box p { margin: 8px 0; color: #6c757d; font-size: 14px; }
        .client-box strong { color: #2c3e50; }
        .existing-clients { margin-top: 25px; padding: 18px; background: #f8fafb; border-radius: 6px; }
        .existing-clients p { color: #6c757d; font-size: 14px; margin-bottom: 10px; }
        .existing-clients ul { margin: 10px 0; padding-left: 20px; color: #2c3e50; }
        .existing-clients li { margin: 5px 0; font-size: 14px; }
        .contact-box { margin-top: 30px; padding: 18px; background: #f8fafb; border-left: 4px solid #00a887; border-radius: 4px; }
        .contact-box p { margin: 0; color: #495057; font-size: 13px; line-height: 1.6; }
        .contact-box strong { color: #00a887; }
        .footer { background: #f8fafb; padding: 25px 20px; text-align: center; font-size: 12px; color: #6c757d; border-top: 2px solid #d0ebe6; }
        .footer p { margin: 8px 0; }
        .footer strong { color: #00a887; }
        @media only screen and (max-width: 600px) {
            body { padding: 10px; }
            .content { padding: 25px 15px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <img src="https://cdn.jsdelivr.net/gh/ggarciaperion/qoricash@main/app/static/images/logo-email.png" alt="QoriCash Logo" class="logo" style="max-width: 200px; height: auto;">
            <h1>Notificación Informativa</h1>
            <p>QoriCash Trading</p>
        </div>

        <div class="content">
            <p class="greeting">Estimado(a) usuario,</p>

            <p class="intro-text">Le informamos que su correo electrónico <strong>{{ new_client.email }}</strong> ha sido utilizado para registrar un nuevo cliente en QoriCash Trading.</p>

            <div class="info-box">
                <p><span class="warning-icon">⚠️ Esta es una notificación informativa</span></p>
                <p style="margin-top: 10px;">Si usted autorizó este registro, no necesita realizar ninguna acción. Si NO reconoce este registro, por favor contacte inmediatamente con nosotros.</p>
            </div>

            <div class="client-box">
                <p class="title">📋 Información del Nuevo Cliente Registrado:</p>
                <p><strong>Tipo de Documento:</strong> {{ new_client.document_type }}</p>
                <p><strong>Número de Documento:</strong> {{ new_client.dni }}</p>
                <p><strong>Nombre:</strong> {{ new_client.full_name or new_client.razon_social }}</p>
                {% if new_client.phone %}
                <p><strong>Teléfono:</strong> {{ new_client.phone }}</p>
                {% endif %}
                <p><strong>Email:</strong> {{ new_client.email }}</p>
                <p><strong>Estado:</strong> {{ new_client.status }}</p>
                <p><strong>Registrado por:</strong> {{ trader.username if trader else 'Sistema' }}</p>
            </div>

            {% if existing_clients and existing_clients|length > 0 %}
            <div class="existing-clients">
                <p><strong>Nota:</strong> Este correo ya está asociado a {{ existing_clients|length }} cliente(s) adicional(es):</p>
                <ul>
                    {% for client in existing_clients %}
                    <li>{{ client.document_type }} {{ client.dni }} - {{ client.full_name or client.razon_social }}</li>
                    {% endfor %}
                </ul>
            </div>
            {% endif %}

            <div class="contact-box">
                <p><strong>¿No reconoce este registro?</strong></p>
                <p style="margin-top: 8px;">Si no autorizó este registro, por favor contacte con nosotros inmediatamente respondiendo a este correo o llamando a su ejecutivo asignado.</p>
            </div>
        </div>

        <div class="footer">
            <p><strong>QoriCash Trading</strong></p>
            <p>Sistema de Gestión de Operaciones Cambiarias</p>
            <p style="margin-top: 12px;">© 2025 QoriCash Trading. Todos los derechos reservados.</p>
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
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #2c3e50; background-color: #f4f6f9; margin: 0; padding: 20px; }
        .container { max-width: 600px; margin: 0 auto; background: #FFFFFF; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); border: 1px solid #e1e8ed; }
        .header { background: linear-gradient(135deg, #0D1B2A 0%, #1a2942 100%); padding: 25px 20px; text-align: center; border-bottom: none; }
        .logo { max-width: 180px; height: auto; margin-bottom: 15px; }
        .header h1 { margin: 15px 0 5px 0; font-size: 26px; color: #FFFFFF; font-weight: 700; }
        .header p { margin: 5px 0 0 0; font-size: 14px; color: white; font-weight: 600; }
        .content { padding: 30px 25px; color: #2c3e50; }
        .greeting { font-size: 16px; margin-bottom: 20px; }
        .greeting strong { color: #00a887; }
        .intro-text { margin-bottom: 25px; line-height: 1.8; }
        .info-box { background: #f8fafb; border: 2px solid #d0ebe6; border-radius: 8px; padding: 20px; margin: 25px 0; }
        .info-box h3 { margin: 0 0 15px 0; color: #00a887; font-size: 18px; font-weight: 700; }
        .info-box p { margin: 10px 0; color: #2c3e50; font-size: 14px; }
        .info-box p strong { color: #6c757d; }
        .welcome-box { background: linear-gradient(135deg, #e8f5f1, #d0ebe6); padding: 25px; margin: 25px 0; border-radius: 8px; text-align: center; box-shadow: 0 2px 8px rgba(0,168,135,0.1); }
        .welcome-box h2 { margin: 0; color: #00a887; font-size: 22px; font-weight: 700; }
        .welcome-box p { margin: 10px 0 0 0; color: #00a887; font-weight: 600; }
        .note-box { margin-top: 30px; padding: 18px; background: #f8fafb; border-left: 4px solid #00a887; border-radius: 4px; }
        .note-box p { margin: 0; color: #495057; font-size: 13px; line-height: 1.6; }
        .note-box strong { color: #00a887; }
        .footer { background: #f8fafb; padding: 25px 20px; text-align: center; font-size: 12px; color: #6c757d; border-top: 2px solid #d0ebe6; }
        .footer p { margin: 8px 0; }
        .footer strong { color: #00a887; }
        .divider { height: 1px; background: linear-gradient(90deg, transparent, #d0ebe6, transparent); margin: 25px 0; }
        @media only screen and (max-width: 600px) {
            body { padding: 10px; }
            .content { padding: 25px 15px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <img src="https://cdn.jsdelivr.net/gh/ggarciaperion/qoricash@main/app/static/images/logo-email.png" alt="QoriCash Logo" class="logo" style="max-width: 200px; height: auto;">
            <h1>Bienvenido a QoriCash</h1>
            <p>Sistema de Gestión de Operaciones Cambiarias</p>
        </div>

        <div class="content">
            <p class="greeting">Estimado(a) <strong>{{ client.full_name or client.razon_social }}</strong>,</p>

            <div class="welcome-box">
                <h2>¡Registro Recibido!</h2>
                <p>Su solicitud está en proceso de validación</p>
            </div>

            <p class="intro-text">Hemos recibido su solicitud de registro por parte de su ejecutivo comercial <strong style="color: #00a887;">{{ trader.username }}</strong>. Nuestro equipo está validando su información y en breve le informaremos sobre la activación de su cuenta.</p>

            <div class="info-box">
                <h3>Datos de Registro</h3>
                <p><strong>Cliente:</strong> {{ client.full_name or client.razon_social }}</p>
                {% if client.document_type %}
                <p><strong>Tipo Documento:</strong> {{ client.document_type }}</p>
                {% endif %}
                {% if client.dni %}
                <p><strong>Número Documento:</strong> {{ client.dni }}</p>
                {% endif %}
                {% if client.phone %}
                <p><strong>Teléfono:</strong> {{ client.phone }}</p>
                {% endif %}
                <p><strong>Cuentas Bancarias:</strong> {{ bank_accounts_text }}</p>
                <p><strong>Ejecutivo Asignado:</strong> {{ trader.username }}</p>
            </div>

            <div class="divider"></div>

            <p style="margin-top: 25px; line-height: 1.8;">Para consultas, contacte a <strong style="color: #00a887;">{{ trader.username }}</strong>{% if trader.email %} al correo <strong style="color: #00a887;">{{ trader.email }}</strong>{% endif %}.</p>

            <div class="note-box">
                <p><strong>Importante:</strong> Este es un correo automático generado por nuestro sistema. Una vez validada su información, recibirá un correo de confirmación de activación de cuenta.</p>
            </div>
        </div>

        <div class="footer">
            <p><strong>QoriCash Trading</strong></p>
            <p>RUC: 20615113698</p>
            <p>Sistema de Gestión de Operaciones Cambiarias</p>
            <p style="margin-top: 12px;">© 2025 QoriCash Trading. Todos los derechos reservados.</p>
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
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #2c3e50; background-color: #f4f6f9; margin: 0; padding: 20px; }
        .container { max-width: 600px; margin: 0 auto; background: #FFFFFF; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); border: 1px solid #e1e8ed; }
        .header { background: linear-gradient(135deg, #0D1B2A 0%, #1a2942 100%); padding: 25px 20px; text-align: center; border-bottom: none; }
        .logo { max-width: 180px; height: auto; margin-bottom: 15px; }
        .header h1 { margin: 15px 0 5px 0; font-size: 26px; color: #FFFFFF; font-weight: 700; }
        .header p { margin: 5px 0 0 0; font-size: 14px; color: white; font-weight: 600; }
        .content { padding: 30px 25px; color: #2c3e50; }
        .greeting { font-size: 16px; margin-bottom: 20px; }
        .greeting strong { color: #00a887; }
        .success-box { background: linear-gradient(135deg, #e8f5f1, #d0ebe6); padding: 25px; margin: 25px 0; border-radius: 8px; text-align: center; box-shadow: 0 2px 8px rgba(0,168,135,0.1); }
        .success-box h2 { margin: 0; color: #00a887; font-size: 22px; font-weight: 700; }
        .success-box p { margin: 10px 0 0 0; color: #00a887; font-weight: 600; }
        .success-icon { font-size: 48px; margin-bottom: 10px; }
        .intro-text { margin-bottom: 25px; line-height: 1.8; }
        .info-box { background: #f8fafb; border: 2px solid #d0ebe6; border-radius: 8px; padding: 20px; margin: 25px 0; }
        .info-box h3 { margin: 0 0 15px 0; color: #00a887; font-size: 18px; font-weight: 700; }
        .info-box p { margin: 10px 0; color: #2c3e50; font-size: 14px; }
        .info-box p strong { color: #6c757d; }
        .info-box .status-active { color: #00a887; font-weight: bold; }
        .benefits-box { background: #f8fafb; border-radius: 8px; padding: 20px; margin: 25px 0; border: 1px solid #e1e8ed; }
        .benefits-box h3 { margin: 0 0 15px 0; color: #00a887; font-size: 18px; font-weight: 700; }
        .benefits-box ul { margin: 10px 0; padding-left: 20px; color: #6c757d; line-height: 2; }
        .benefits-box li { margin: 8px 0; }
        .note-box { margin-top: 30px; padding: 18px; background: #f8fafb; border-left: 4px solid #00a887; border-radius: 4px; }
        .note-box p { margin: 0; color: #495057; font-size: 13px; line-height: 1.6; }
        .note-box strong { color: #00a887; }
        .footer { background: #f8fafb; padding: 25px 20px; text-align: center; font-size: 12px; color: #6c757d; border-top: 2px solid #d0ebe6; }
        .footer p { margin: 8px 0; }
        .footer strong { color: #00a887; }
        .divider { height: 1px; background: linear-gradient(90deg, transparent, #d0ebe6, transparent); margin: 25px 0; }
        @media only screen and (max-width: 600px) {
            body { padding: 10px; }
            .content { padding: 25px 15px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <img src="https://cdn.jsdelivr.net/gh/ggarciaperion/qoricash@main/app/static/images/logo-email.png" alt="QoriCash Logo" class="logo" style="max-width: 200px; height: auto;">
            <h1>¡Cuenta Activada Exitosamente!</h1>
            <p>QoriCash Trading</p>
        </div>

        <div class="content">
            <p class="greeting">Estimado(a) <strong>{{ client.full_name or client.razon_social }}</strong>,</p>

            <div class="success-box">
                <div class="success-icon">✓</div>
                <h2>¡Bienvenido a QoriCash!</h2>
                <p>Su cuenta ha sido activada correctamente</p>
            </div>

            <p class="intro-text">Nos complace informarle que su registro ha sido validado exitosamente y su cuenta ya se encuentra <strong style="color: #00a887;">ACTIVA</strong> en nuestro sistema.</p>

            <p class="intro-text">A partir de este momento, puede comenzar a realizar operaciones de cambio de divisas con nosotros. Nuestro equipo está listo para atenderle y brindarle el mejor servicio.</p>

            <div class="info-box">
                <h3>Información de su Cuenta</h3>
                <p><strong>Cliente:</strong> {{ client.full_name or client.razon_social }}</p>
                {% if client.document_number or client.dni %}
                <p><strong>Número de documento:</strong> {{ client.document_number or client.dni }}</p>
                {% endif %}
                {% if client.phone %}
                <p><strong>Número de teléfono registrado:</strong> {{ client.phone }}</p>
                {% endif %}
                <p><strong>Estado:</strong> <span class="status-active">ACTIVO</span></p>
                <p><strong>Ejecutivo Asignado:</strong> {{ trader.username }}</p>
            </div>

            <div class="benefits-box">
                <h3>¿Qué puede hacer ahora?</h3>
                <ul>
                    <li>Realizar operaciones de compra y venta de dólares</li>
                    <li>Obtener tipos de cambio competitivos</li>
                    <li>Recibir atención personalizada de su ejecutivo</li>
                    <li>Acceder a transferencias rápidas y seguras</li>
                </ul>
            </div>

            <div class="divider"></div>

            <p style="margin-top: 25px; line-height: 1.8;">Para realizar su primera operación o si tiene alguna consulta, puede contactar directamente a su ejecutivo comercial <strong style="color: #00a887;">{{ trader.username }}</strong>{% if trader.email %} al correo <strong style="color: #00a887;">{{ trader.email }}</strong>{% endif %}.</p>

            <div class="note-box">
                <p><strong>Gracias por confiar en QoriCash Trading para sus operaciones cambiarias.</strong></p>
            </div>
        </div>

        <div class="footer">
            <p><strong>QoriCash Trading</strong></p>
            <p>RUC: 20615113698</p>
            <p>Sistema de Gestión de Operaciones Cambiarias</p>
            <p style="margin-top: 12px;">© 2025 QoriCash Trading. Todos los derechos reservados.</p>
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
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #2c3e50; background-color: #f4f6f9; margin: 0; padding: 20px; }
        .container { max-width: 600px; margin: 0 auto; background: #FFFFFF; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); border: 1px solid #e1e8ed; }
        .header { background: linear-gradient(135deg, #0D1B2A 0%, #1a2942 100%); padding: 25px 20px; text-align: center; border-bottom: none; }
        .logo { max-width: 180px; height: auto; margin-bottom: 15px; }
        .header h1 { margin: 15px 0 5px 0; font-size: 26px; color: #FFFFFF; font-weight: 700; }
        .header p { margin: 5px 0 0 0; font-size: 14px; color: white; font-weight: 600; }
        .content { padding: 30px 25px; color: #2c3e50; }
        .greeting { font-size: 16px; margin-bottom: 20px; }
        .greeting strong { color: #00a887; }
        .client-info { font-size: 13px; color: #6c757d; margin: -10px 0 20px 0; }
        .warning-box { background: linear-gradient(135deg, #fff3cd, #ffe69c); padding: 25px; margin: 25px 0; border-radius: 8px; text-align: center; box-shadow: 0 2px 8px rgba(255,193,7,0.15); }
        .warning-box h2 { margin: 0; color: #856404; font-size: 22px; font-weight: 700; }
        .warning-box p { margin: 10px 0 0 0; color: #856404; font-weight: 600; }
        .warning-icon { font-size: 48px; margin-bottom: 10px; }
        .intro-text { margin-bottom: 25px; line-height: 1.8; }
        .reason-box { background: #fff3cd; border: 2px solid #FFB020; border-radius: 8px; padding: 20px; margin: 25px 0; }
        .reason-box h3 { margin: 0 0 12px 0; color: #856404; font-size: 18px; font-weight: 700; }
        .reason-box p { margin: 0; color: #856404; font-size: 14px; font-style: italic; line-height: 1.6; }
        .highlight-box { background: #f8fafb; border: 2px solid #d0ebe6; border-radius: 8px; padding: 20px; margin: 25px 0; }
        .highlight-box h3 { margin: 0 0 15px 0; color: #00a887; font-size: 18px; font-weight: 700; }
        .info-row { display: flex; justify-content: space-between; padding: 14px 0; border-bottom: 1px solid #e1e8ed; }
        .info-row:last-child { border-bottom: none; }
        .info-label { font-weight: 600; color: #6c757d; font-size: 14px; }
        .info-value { color: #2c3e50; font-weight: 600; font-size: 14px; text-align: right; }
        .amount-usd { font-size: 20px; color: #00a887; font-weight: 700; }
        .amount-pen { font-size: 20px; color: #00a887; font-weight: 700; }
        .badge-canceled { display: inline-block; padding: 6px 16px; border-radius: 20px; font-size: 13px; font-weight: bold; background: #FFB020; color: #856404; }
        .note-box { margin-top: 30px; padding: 18px; background: #f8fafb; border-left: 4px solid #00a887; border-radius: 4px; }
        .note-box p { margin: 0; color: #495057; font-size: 13px; line-height: 1.6; }
        .note-box strong { color: #00a887; }
        .footer { background: #f8fafb; padding: 25px 20px; text-align: center; font-size: 12px; color: #6c757d; border-top: 2px solid #d0ebe6; }
        .footer p { margin: 8px 0; }
        .footer strong { color: #00a887; }
        .divider { height: 1px; background: linear-gradient(90deg, transparent, #d0ebe6, transparent); margin: 25px 0; }
        @media only screen and (max-width: 600px) {
            body { padding: 10px; }
            .content { padding: 25px 15px; }
            .info-row { flex-direction: column; }
            .info-value { text-align: left; margin-top: 5px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <img src="https://cdn.jsdelivr.net/gh/ggarciaperion/qoricash@main/app/static/images/logo-email.png" alt="QoriCash Logo" class="logo" style="max-width: 200px; height: auto;">
            <h1>Operación Cancelada</h1>
            <p>QoriCash Trading</p>
        </div>

        <div class="content">
            <p class="greeting">Estimado(a) <strong>{{ operation.client.full_name or operation.client.razon_social }}</strong>,</p>
            <p class="client-info">
                <strong>{{ operation.client.document_type or 'Documento' }}:</strong> {{ operation.client.dni }}
            </p>

            <div class="warning-box">
                <div class="warning-icon">⚠</div>
                <h2>Operación Cancelada</h2>
                <p>Su operación ha sido cancelada</p>
            </div>

            <p class="intro-text">Lamentamos informarle que la operación con código <strong style="color: #856404;">{{ operation.operation_id }}</strong> ha sido <strong style="color: #856404;">CANCELADA</strong>.</p>

            <div class="reason-box">
                <h3>Motivo de Cancelación</h3>
                <p>{{ reason }}</p>
            </div>

            <div class="highlight-box">
                <h3>Detalles de la Operación Cancelada</h3>
                <div class="info-row">
                    <span class="info-label">Código de Operación:</span>
                    <span class="info-value"><strong>{{ operation.operation_id }}</strong></span>
                </div>
                <div class="info-row">
                    <span class="info-label">Tipo de Operación:</span>
                    <span class="info-value">{{ operation.operation_type }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Monto en Dólares:</span>
                    <span class="info-value amount-usd">$ {{ "{:,.2f}".format(operation.amount_usd) }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Tipo de Cambio:</span>
                    <span class="info-value">S/ {{ "%.4f"|format(operation.exchange_rate) }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Monto en Soles:</span>
                    <span class="info-value amount-pen">S/ {{ "{:,.2f}".format(operation.amount_pen) }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Fecha de Creación:</span>
                    <span class="info-value">{{ operation.created_at.strftime('%d/%m/%Y %H:%M') }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Estado:</span>
                    <span class="info-value"><span class="badge-canceled">CANCELADA</span></span>
                </div>
            </div>

            <div class="divider"></div>

            <p style="margin-top: 25px; line-height: 1.8;">Si tiene alguna consulta sobre esta cancelación, por favor contacte a su ejecutivo comercial.</p>

            <div class="note-box">
                <p><strong>Nota:</strong> Para cualquier consulta sobre esta operación, puede responder a este correo o contactar directamente a su asesor comercial.</p>
            </div>
        </div>

        <div class="footer">
            <p><strong>QoriCash Trading</strong></p>
            <p>Sistema de Gestión de Operaciones Cambiarias</p>
            <p style="margin-top: 12px;">© 2025 QoriCash Trading. Todos los derechos reservados.</p>
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
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #2c3e50; background-color: #f4f6f9; margin: 0; padding: 20px; }
        .container { max-width: 600px; margin: 0 auto; background: #FFFFFF; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); border: 1px solid #e1e8ed; }
        .header { background: linear-gradient(135deg, #0D1B2A 0%, #1a2942 100%); padding: 25px 20px; text-align: center; border-bottom: none; }
        .logo { max-width: 180px; height: auto; margin-bottom: 15px; }
        .header h1 { margin: 15px 0 5px 0; font-size: 26px; color: #FFFFFF; font-weight: 700; }
        .header p { margin: 5px 0 0 0; font-size: 14px; color: white; font-weight: 600; }
        .content { padding: 30px 25px; color: #2c3e50; }
        .greeting { font-size: 16px; margin-bottom: 20px; }
        .greeting strong { color: #00a887; }
        .client-info { font-size: 13px; color: #6c757d; margin: -10px 0 20px 0; }
        .modified-box { background: linear-gradient(135deg, #e8f5f1, #d0ebe6); padding: 25px; margin: 25px 0; border-radius: 8px; text-align: center; box-shadow: 0 2px 8px rgba(0,168,135,0.1); }
        .modified-box h2 { margin: 0; color: #00a887; font-size: 22px; font-weight: 700; }
        .modified-box p { margin: 10px 0 0 0; color: #00a887; font-weight: 600; }
        .modified-icon { font-size: 48px; margin-bottom: 10px; }
        .intro-text { margin-bottom: 25px; line-height: 1.8; }
        .operation-box { background: #f8fafb; border: 2px solid #d0ebe6; border-radius: 8px; padding: 18px; margin: 20px 0; text-align: center; }
        .operation-box p { margin: 0 0 8px 0; color: #6c757d; font-size: 14px; font-weight: 600; }
        .operation-box .operation-id { margin: 0; color: #00a887; font-size: 20px; font-weight: 700; }
        .comparison-box { background: #f8fafb; border: 2px solid #d0ebe6; border-radius: 8px; padding: 25px; margin: 25px 0; }
        .comparison-box h3 { margin: 0 0 20px 0; color: #00a887; font-size: 18px; font-weight: 700; text-align: center; }
        .comparison-item { margin: 20px 0; }
        .comparison-item p { margin: 0 0 10px 0; color: #6c757d; font-size: 14px; font-weight: 600; }
        .comparison-values { display: flex; align-items: center; justify-content: center; flex-wrap: wrap; gap: 15px; }
        .old-value { color: #dc3545; text-decoration: line-through; font-size: 18px; font-weight: 600; }
        .new-value { color: #00a887; font-weight: 700; font-size: 20px; }
        .arrow { color: #00a887; font-size: 24px; }
        .highlight-box { background: #f8fafb; border: 2px solid #d0ebe6; border-radius: 8px; padding: 20px; margin: 25px 0; }
        .highlight-box h3 { margin: 0 0 15px 0; color: #00a887; font-size: 18px; font-weight: 700; }
        .info-row { display: flex; justify-content: space-between; padding: 14px 0; border-bottom: 1px solid #e1e8ed; }
        .info-row:last-child { border-bottom: none; }
        .info-label { font-weight: 600; color: #6c757d; font-size: 14px; }
        .info-value { color: #2c3e50; font-weight: 600; font-size: 14px; text-align: right; }
        .amount-usd { font-size: 20px; color: #00a887; font-weight: 700; }
        .amount-pen { font-size: 20px; color: #00a887; font-weight: 700; }
        .badge { display: inline-block; padding: 6px 16px; border-radius: 20px; font-size: 13px; font-weight: bold; }
        .badge-compra { background: linear-gradient(135deg, #d0ebe6, #e8f5f1); color: #00a887; border: 1px solid #00a887; }
        .badge-venta { background: linear-gradient(135deg, #d0ebe6, #e8f5f1); color: #00a887; border: 1px solid #00a887; }
        .bank-section { background: #f8fafb; border: 2px solid #d0ebe6; border-radius: 8px; padding: 25px; margin: 25px 0; }
        .bank-section h3 { margin: 0 0 15px 0; color: #00a887; font-size: 18px; font-weight: 700; }
        .bank-section p { margin: 10px 0; color: #495057; font-size: 14px; line-height: 1.6; }
        .company-name { color: #00a887 !important; font-weight: 700 !important; }
        .bank-table { width: 100%; border-collapse: collapse; margin: 15px 0; font-size: 13px; }
        .bank-table thead { background: #e8f5f1; }
        .bank-table th { padding: 12px 10px; text-align: left; border-bottom: 2px solid #d0ebe6; color: #00a887; font-weight: 700; }
        .bank-table td { padding: 12px 10px; border-bottom: 1px solid #e1e8ed; color: #2c3e50; }
        .bank-table tbody tr { background: #FFFFFF; }
        .bank-table tbody tr:nth-child(even) { background: #f8fafb; }
        .bank-name { color: #00a887; font-weight: 600; }
        .account-number { font-family: monospace; font-weight: 600; color: #00a887; }
        .note-box { margin-top: 30px; padding: 18px; background: #f8fafb; border-left: 4px solid #00a887; border-radius: 4px; }
        .note-box p { margin: 0; color: #495057; font-size: 13px; line-height: 1.6; }
        .note-box strong { color: #00a887; }
        .footer { background: #f8fafb; padding: 25px 20px; text-align: center; font-size: 12px; color: #6c757d; border-top: 2px solid #d0ebe6; }
        .footer p { margin: 8px 0; }
        .footer strong { color: #00a887; }
        .divider { height: 1px; background: linear-gradient(90deg, transparent, #d0ebe6, transparent); margin: 25px 0; }
        @media only screen and (max-width: 600px) {
            body { padding: 10px; }
            .content { padding: 25px 15px; }
            .info-row { flex-direction: column; }
            .info-value { text-align: left; margin-top: 5px; }
            .comparison-values { flex-direction: column; gap: 8px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <img src="https://cdn.jsdelivr.net/gh/ggarciaperion/qoricash@main/app/static/images/logo-email.png" alt="QoriCash Logo" class="logo" style="max-width: 200px; height: auto;">
            <h1>Monto Modificado</h1>
            <p>QoriCash Trading</p>
        </div>

        <div class="content">
            <p class="greeting">Estimado(a) <strong>{{ operation.client.full_name or operation.client.razon_social }}</strong>,</p>
            <p class="client-info">
                <strong>{{ operation.client.document_type or 'Documento' }}:</strong> {{ operation.client.dni }}
            </p>

            <div class="modified-box">
                <div class="modified-icon">✎</div>
                <h2>Monto Modificado</h2>
                <p>El monto de su operación ha sido actualizado</p>
            </div>

            <p class="intro-text">Le informamos que el <strong style="color: #00a887;">monto de su operación</strong> ha sido modificado. A continuación los detalles:</p>

            <div class="operation-box">
                <p>Operación:</p>
                <p class="operation-id">{{ operation.operation_id }}</p>
            </div>

            <div class="comparison-box">
                <h3>Cambios Realizados</h3>

                <div class="comparison-item">
                    <p>Monto en Dólares (USD):</p>
                    <div class="comparison-values">
                        <span class="old-value">$ {{ "{:,.2f}".format(old_amount_usd) }}</span>
                        <span class="arrow">→</span>
                        <span class="new-value">$ {{ "{:,.2f}".format(operation.amount_usd) }}</span>
                    </div>
                </div>

                <div class="comparison-item">
                    <p>Monto en Soles (PEN):</p>
                    <div class="comparison-values">
                        <span class="old-value">S/ {{ "{:,.2f}".format(old_amount_pen) }}</span>
                        <span class="arrow">→</span>
                        <span class="new-value">S/ {{ "{:,.2f}".format(operation.amount_pen) }}</span>
                    </div>
                </div>
            </div>

            <div class="highlight-box">
                <h3>Detalles Actuales de la Operación</h3>
                <div class="info-row">
                    <span class="info-label">Código de Operación:</span>
                    <span class="info-value"><strong>{{ operation.operation_id }}</strong></span>
                </div>
                <div class="info-row">
                    <span class="info-label">Tipo de Operación:</span>
                    <span class="info-value">
                        {% if operation.operation_type == 'Compra' %}
                            <span class="badge badge-compra">COMPRA USD</span>
                        {% else %}
                            <span class="badge badge-venta">VENTA USD</span>
                        {% endif %}
                    </span>
                </div>
                <div class="info-row">
                    <span class="info-label">Monto en Dólares:</span>
                    <span class="info-value amount-usd">$ {{ "{:,.2f}".format(operation.amount_usd) }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Tipo de Cambio:</span>
                    <span class="info-value">S/ {{ "%.4f"|format(operation.exchange_rate) }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Monto en Soles:</span>
                    <span class="info-value amount-pen">S/ {{ "{:,.2f}".format(operation.amount_pen) }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Estado:</span>
                    <span class="info-value">
                        {% if operation.status == 'Pendiente' %}
                            <strong style="color: #f59e0b;">{{ operation.status }}</strong>
                        {% elif operation.status == 'Completada' %}
                            <strong style="color: #10b981;">{{ operation.status }}</strong>
                        {% elif operation.status == 'Cancelada' %}
                            <strong style="color: #ef4444;">{{ operation.status }}</strong>
                        {% else %}
                            <strong style="color: #00a887;">{{ operation.status }}</strong>
                        {% endif %}
                    </span>
                </div>
                <div class="info-row">
                    <span class="info-label">Fecha de Creación:</span>
                    <span class="info-value">{{ operation.created_at.strftime('%d/%m/%Y %H:%M') }}</span>
                </div>
            </div>

            <!-- Cuentas bancarias para transferencia (solo si está Pendiente) -->
            {% if operation.status == 'Pendiente' %}
                {% if operation.operation_type == 'Compra' %}
            <div class="bank-section">
                <h3>Cuentas para Transferencia en DÓLARES (USD)</h3>
                <p>Por favor, realice su transferencia a cualquiera de las siguientes cuentas bancarias:</p>
                <p class="company-name">A nombre de: QORICASH SAC | RUC: 20615113698</p>
                <table class="bank-table">
                    <thead>
                        <tr>
                            <th>Banco</th>
                            <th>Tipo</th>
                            <th>Moneda</th>
                            <th>N° Cuenta</th>
                            <th>CCI</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td class="bank-name">BCP</td>
                            <td>Cta. Corriente</td>
                            <td>USD</td>
                            <td class="account-number">654321</td>
                            <td class="account-number">00265432100000000001</td>
                        </tr>
                        <tr>
                            <td class="bank-name">INTERBANK</td>
                            <td>Cta. Corriente</td>
                            <td>USD</td>
                            <td class="account-number">456789</td>
                            <td class="account-number">00345678900000000002</td>
                        </tr>
                        <tr>
                            <td class="bank-name">BANBIF</td>
                            <td>Cta. Corriente</td>
                            <td>USD</td>
                            <td class="account-number">369852</td>
                            <td class="account-number">03836985200000000003</td>
                        </tr>
                        <tr>
                            <td class="bank-name">PICHINCHA</td>
                            <td>Cta. Corriente</td>
                            <td>USD</td>
                            <td class="account-number">159796</td>
                            <td class="account-number">04815979600000000004</td>
                        </tr>
                    </tbody>
                </table>
            </div>
            {% elif operation.operation_type == 'Venta' %}
            <div class="bank-section">
                <h3>Cuentas para Transferencia en SOLES (PEN)</h3>
                <p>Por favor, realice su transferencia a cualquiera de las siguientes cuentas bancarias:</p>
                <p class="company-name">A nombre de: QORICASH SAC | RUC: 20615113698</p>
                <table class="bank-table">
                    <thead>
                        <tr>
                            <th>Banco</th>
                            <th>Tipo</th>
                            <th>Moneda</th>
                            <th>N° Cuenta</th>
                            <th>CCI</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td class="bank-name">BCP</td>
                            <td>Cta. Corriente</td>
                            <td>PEN</td>
                            <td class="account-number">123456</td>
                            <td class="account-number">00212345600000000005</td>
                        </tr>
                        <tr>
                            <td class="bank-name">INTERBANK</td>
                            <td>Cta. Corriente</td>
                            <td>PEN</td>
                            <td class="account-number">987654</td>
                            <td class="account-number">00398765400000000006</td>
                        </tr>
                        <tr>
                            <td class="bank-name">BANBIF</td>
                            <td>Cta. Corriente</td>
                            <td>PEN</td>
                            <td class="account-number">741852</td>
                            <td class="account-number">03874185200000000007</td>
                        </tr>
                        <tr>
                            <td class="bank-name">PICHINCHA</td>
                            <td>Cta. Corriente</td>
                            <td>PEN</td>
                            <td class="account-number">753951</td>
                            <td class="account-number">04875395100000000008</td>
                        </tr>
                    </tbody>
                </table>
            </div>
            {% endif %}
            {% endif %}

            <div class="divider"></div>

            <p style="margin-top: 25px; line-height: 1.8;">Nuestro equipo procesará su operación con el nuevo monto. Le mantendremos informado sobre el progreso en cada etapa del proceso.</p>

            <div class="note-box">
                <p><strong>Importante:</strong> Este es un correo automático generado por nuestro sistema. Si tiene alguna consulta, por favor responda a este correo o contacte directamente a su asesor comercial.</p>
            </div>
        </div>

        <div class="footer">
            <p><strong>QoriCash Trading</strong></p>
            <p>Sistema de Gestión de Operaciones Cambiarias</p>
            <p style="margin-top: 12px;">© 2025 QoriCash Trading. Todos los derechos reservados.</p>
        </div>
    </div>
</body>
</html>
"""
        return render_template_string(template, operation=operation, old_amount_usd=old_amount_usd, old_amount_pen=old_amount_pen)
