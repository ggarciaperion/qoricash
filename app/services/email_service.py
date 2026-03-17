"""
Servicio de envío de correos electrónicos para QoriCash Trading V2
"""
from flask import render_template_string
from flask_mail import Message
from app.extensions import mail
from app.models import User
import logging
import eventlet

logger = logging.getLogger(__name__)


class EmailService:
    """Servicio para envío de correos electrónicos"""

    @staticmethod
    def _send_async(msg, timeout=10):
        """
        Enviar email de forma asíncrona con timeout

        Args:
            msg: Flask-Mail Message object
            timeout: Timeout en segundos (default 10s)
        """
        from flask import current_app

        # Capturar el contexto de la aplicación antes de spawning
        app = current_app._get_current_object()

        def _send():
            try:
                # Usar el contexto de la aplicación en el hilo asíncrono
                with app.app_context():
                    with eventlet.Timeout(timeout):
                        mail.send(msg)
                        logger.info(f'Email enviado exitosamente (async)')
            except eventlet.Timeout:
                logger.warning(f'Timeout al enviar email después de {timeout}s')
            except Exception as e:
                logger.error(f'Error al enviar email (async): {str(e)}')

        # Spawn en background (fire and forget)
        eventlet.spawn_n(_send)

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
        # Destinatario principal: Cliente
        to = [operation.client.email] if operation.client and operation.client.email else []

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
        # Destinatario principal: Cliente
        to = [operation.client.email] if operation.client and operation.client.email else []

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
            to, cc, bcc = EmailService.get_recipients_for_new_operation(operation)

            # Validar que haya al menos un destinatario
            if not to and not cc and not bcc:
                logger.warning(f'No hay destinatarios para la operación {operation.operation_id}')
                return False, 'No hay destinatarios configurados'

            # Asunto
            subject = f'Nueva Operación #{operation.operation_id} - QoriCash Trading'

            # Contenido HTML
            html_body = EmailService._render_new_operation_template(operation)

            # Crear mensaje
            msg = Message(
                subject=subject,
                recipients=to,
                cc=cc,
                bcc=bcc,
                html=html_body
            )

            # Enviar ASÍNCRONO para no bloquear el worker
            EmailService._send_async(msg, timeout=15)

            logger.info(f'Email de nueva operación programado para envío: {operation.operation_id}')
            return True, 'Email programado para envío'

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
            # Si no están configuradas, usar las credenciales regulares como fallback
            confirmation_username = current_app.config.get('MAIL_CONFIRMATION_USERNAME') or current_app.config.get('MAIL_USERNAME')
            confirmation_password = current_app.config.get('MAIL_CONFIRMATION_PASSWORD') or current_app.config.get('MAIL_PASSWORD')
            confirmation_sender = current_app.config.get('MAIL_CONFIRMATION_SENDER') or current_app.config.get('MAIL_DEFAULT_SENDER')

            logger.info(f'[EMAIL] Credenciales - Usuario: {confirmation_username}, Remitente: {confirmation_sender}')

            if not confirmation_username or not confirmation_password:
                logger.error('[EMAIL] Credenciales de email no configuradas')
                return False, 'Email no configurado'

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

                # Adjuntar comprobante electrónico si existe
                if operation.invoices and len(operation.invoices) > 0:
                    invoice = operation.invoices[0]  # Tomar el primer invoice
                    if invoice.nubefact_enlace_pdf:
                        try:
                            logger.info(f'[EMAIL] Descargando comprobante PDF desde: {invoice.nubefact_enlace_pdf}')
                            import requests
                            pdf_response = requests.get(invoice.nubefact_enlace_pdf, timeout=10)

                            if pdf_response.status_code == 200:
                                # Nombre del archivo adjunto
                                filename = f'{invoice.invoice_number}.pdf' if invoice.invoice_number else 'comprobante.pdf'

                                # Adjuntar PDF al mensaje
                                msg.attach(
                                    filename,
                                    'application/pdf',
                                    pdf_response.content,
                                    'attachment'
                                )
                                logger.info(f'[EMAIL] Comprobante PDF adjuntado: {filename}')
                            else:
                                logger.warning(f'[EMAIL] Error al descargar PDF: HTTP {pdf_response.status_code}')
                        except Exception as e:
                            logger.error(f'[EMAIL] Error al adjuntar comprobante: {str(e)}')
                    else:
                        logger.info(f'[EMAIL] Invoice existe pero no tiene enlace PDF')
                else:
                    logger.info(f'[EMAIL] Operación sin comprobante electrónico')

                # Enviar ASÍNCRONO para no bloquear el worker
                logger.info(f'[EMAIL] Programando envío de email a TO: {to}, CC: {cc}')
                EmailService._send_async(msg, timeout=15)

                logger.info(f'[EMAIL] Email de operacion completada programado para envío desde {confirmation_sender}: {operation.operation_id}')
                return True, 'Email programado para envío'

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
    def _render_new_operation_template(operation):
        """Renderizar plantilla HTML para nueva operación"""
        template = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body, table, td, p, h1, h2, h3 { margin: 0; padding: 0; }
        body { background-color: #f0f4f8; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; }
        .email-wrapper { padding: 28px 16px; }
        .email-card { max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 24px rgba(13,27,42,0.09); }
        .email-header { background-color: #0D1B2A; padding: 30px 40px 26px; text-align: center; }
        .logo-wrap { display: inline-block; border: 1.5px solid rgba(0,222,168,0.35); border-radius: 8px; padding: 7px 22px; margin-bottom: 10px; }
        .logo-text { color: #00DEA8; font-size: 21px; font-weight: 700; letter-spacing: 1.5px; }
        .tagline { color: rgba(255,255,255,0.40); font-size: 11px; letter-spacing: 0.6px; margin-top: 6px; }
        .accent-bar { height: 3px; background-color: #00DEA8; }
        .email-body { padding: 36px 40px; color: #334155; font-size: 15px; line-height: 1.65; }
        .section-label { font-size: 11px; font-weight: 700; color: #00DEA8; text-transform: uppercase; letter-spacing: 1.2px; margin: 24px 0 10px 0; }
        .data-box { background: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0; overflow: hidden; margin: 0 0 20px 0; }
        .data-row { padding: 10px 18px; border-bottom: 1px solid #f1f5f9; font-size: 14px; }
        .data-row:last-child { border-bottom: none; }
        .data-label { color: #64748b; font-weight: 600; display: inline-block; min-width: 150px; }
        .data-value { color: #1e293b; font-weight: 500; }
        .op-badge { display: inline-block; padding: 3px 12px; border-radius: 20px; font-size: 12px; font-weight: 700; letter-spacing: 0.3px; }
        .op-badge.buy { background-color: #dcfce7; color: #15803d; }
        .op-badge.sell { background-color: #dbeafe; color: #1d4ed8; }
        .bank-section { border-radius: 8px; overflow: hidden; border: 1px solid #e2e8f0; margin: 16px 0; }
        .bank-header { padding: 12px 16px; font-size: 13px; font-weight: 700; }
        .bank-header.buy { background-color: #f0fdf4; color: #15803d; border-bottom: 1px solid #bbf7d0; }
        .bank-header.sell { background-color: #fef2f2; color: #991b1b; border-bottom: 1px solid #fecaca; }
        .bank-subtext { font-size: 12px; font-weight: 400; margin-top: 3px; opacity: 0.8; }
        .bank-table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
        .bank-table th { background-color: #0D1B2A; color: #94a3b8; font-weight: 600; padding: 9px 12px; text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; }
        .bank-table td { padding: 9px 12px; border-bottom: 1px solid #f1f5f9; color: #334155; }
        .bank-table tr:last-child td { border-bottom: none; }
        .bank-table tr:nth-child(even) td { background-color: #f8fafc; }
        .bank-name { font-weight: 700; color: #1e293b; }
        .account-num { font-family: 'Courier New', monospace; color: #0D1B2A; font-weight: 600; }
        .alert { border-radius: 8px; padding: 13px 16px; margin: 14px 0; font-size: 13.5px; line-height: 1.65; }
        .alert.warning { background: #fffbeb; border-left: 3px solid #f59e0b; color: #78350f; }
        .divider { height: 1px; background-color: #f1f5f9; margin: 24px 0; }
        .note-text { font-size: 13px; color: #94a3b8; line-height: 1.6; }
        .email-footer { background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 22px 40px; text-align: center; }
        .footer-brand { color: #0D1B2A; font-size: 14px; font-weight: 700; margin-bottom: 4px; }
        .footer-meta { color: #94a3b8; font-size: 12px; }
        .footer-link { color: #00DEA8; text-decoration: none; }
        .footer-copy { color: #cbd5e1; font-size: 11px; margin-top: 8px; }
        @media only screen and (max-width: 620px) {
            .email-body { padding: 24px 20px !important; }
            .email-header { padding: 24px 20px !important; }
            .data-label { display: block !important; min-width: unset !important; margin-bottom: 2px; }
        }
    </style>
</head>
<body>
<div class="email-wrapper">
    <div class="email-card">

        <div class="email-header">
            <div class="logo-wrap"><span class="logo-text">QoriCash</span></div>
            <p class="tagline">Nueva operación registrada</p>
        </div>
        <div class="accent-bar"></div>

        <div class="email-body">
            <p>Estimado(a) <strong>{{ operation.client.full_name or operation.client.razon_social }}</strong>,</p>
            <p style="margin-top:10px;color:#64748b;font-size:14px;">Se ha registrado una nueva operación con los siguientes detalles:</p>

            <p class="section-label">Resumen de la operación</p>
            <table width="100%" cellspacing="0" cellpadding="0" style="background:#f8fafc;border-radius:8px;border:1px solid #e2e8f0;border-collapse:collapse;font-size:14px;margin:0 0 20px 0;">
                <tr style="border-bottom:1px solid #f1f5f9;">
                    <td style="padding:10px 18px;color:#64748b;font-weight:600;width:160px;vertical-align:middle;white-space:nowrap;">Código</td>
                    <td style="padding:10px 18px;color:#0D1B2A;font-weight:700;vertical-align:middle;">{{ operation.operation_id }}</td>
                </tr>
                <tr style="border-bottom:1px solid #f1f5f9;">
                    <td style="padding:10px 18px;color:#64748b;font-weight:600;white-space:nowrap;vertical-align:middle;">Tipo</td>
                    <td style="padding:10px 18px;vertical-align:middle;">
                        {% if operation.operation_type == 'Compra' %}
                            <span style="display:inline-block;padding:3px 12px;border-radius:20px;font-size:12px;font-weight:700;background:#dcfce7;color:#15803d;">COMPRA USD</span>
                        {% else %}
                            <span style="display:inline-block;padding:3px 12px;border-radius:20px;font-size:12px;font-weight:700;background:#dbeafe;color:#1d4ed8;">VENTA USD</span>
                        {% endif %}
                    </td>
                </tr>
                <tr style="border-bottom:1px solid #f1f5f9;">
                    <td style="padding:10px 18px;color:#64748b;font-weight:600;white-space:nowrap;vertical-align:middle;">Monto USD</td>
                    <td style="padding:10px 18px;color:#059669;font-weight:700;font-size:16px;vertical-align:middle;">$ {{ "{:,.2f}".format(operation.amount_usd) }}</td>
                </tr>
                <tr style="border-bottom:1px solid #f1f5f9;">
                    <td style="padding:10px 18px;color:#64748b;font-weight:600;white-space:nowrap;vertical-align:middle;">Tipo de cambio</td>
                    <td style="padding:10px 18px;color:#1e293b;font-weight:500;vertical-align:middle;">{{ "%.4f"|format(operation.exchange_rate) }}</td>
                </tr>
                <tr style="border-bottom:1px solid #f1f5f9;">
                    <td style="padding:10px 18px;color:#64748b;font-weight:600;white-space:nowrap;vertical-align:middle;">Monto PEN</td>
                    <td style="padding:10px 18px;color:#dc2626;font-weight:700;font-size:16px;vertical-align:middle;">S/ {{ "{:,.2f}".format(operation.amount_pen) }}</td>
                </tr>
                <tr style="border-bottom:1px solid #f1f5f9;">
                    <td style="padding:10px 18px;color:#64748b;font-weight:600;white-space:nowrap;vertical-align:middle;">Estado</td>
                    <td style="padding:10px 18px;color:#d97706;font-weight:600;vertical-align:middle;">{{ operation.status }}</td>
                </tr>
                <tr>
                    <td style="padding:10px 18px;color:#64748b;font-weight:600;white-space:nowrap;vertical-align:middle;">Fecha</td>
                    <td style="padding:10px 18px;color:#1e293b;font-weight:500;vertical-align:middle;">{{ operation.created_at.strftime('%d/%m/%Y %H:%M') }}</td>
                </tr>
            </table>

            {% if operation.operation_type == 'Compra' %}
            <p class="section-label">Cuentas para transferencia (USD)</p>
            <div class="bank-section">
                <div class="bank-header buy">
                    Transfiera en DÓLARES a cualquiera de estas cuentas
                    <div class="bank-subtext">A nombre de QORICASH SAC — RUC 20615113698</div>
                </div>
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
                        <tr><td class="bank-name">BCP</td><td>Cta. Corriente</td><td>USD</td><td class="account-num">1917357790119</td><td class="account-num">00219100735779011959</td></tr>
                        <tr><td class="bank-name">INTERBANK</td><td>Cta. Corriente</td><td>USD</td><td class="account-num">200-3007757589</td><td class="account-num">00320000300775758939</td></tr>
                    </tbody>
                </table>
            </div>
            {% elif operation.operation_type == 'Venta' %}
            <p class="section-label">Cuentas para transferencia (PEN)</p>
            <div class="bank-section">
                <div class="bank-header sell">
                    Transfiera en SOLES a cualquiera de estas cuentas
                    <div class="bank-subtext">A nombre de QORICASH SAC — RUC 20615113698</div>
                </div>
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
                        <tr><td class="bank-name">BCP</td><td>Cta. Corriente</td><td>PEN</td><td class="account-num">1937353150041</td><td class="account-num">00219300735315004118</td></tr>
                        <tr><td class="bank-name">INTERBANK</td><td>Cta. Corriente</td><td>PEN</td><td class="account-num">200-3007757571</td><td class="account-num">00320000300775757137</td></tr>
                    </tbody>
                </table>
            </div>
            {% endif %}

            {% if operation.notes %}
            <div class="alert warning">
                <strong>Notas:</strong> {{ operation.notes }}
            </div>
            {% endif %}

            <div class="divider"></div>
            <p style="font-size:14px;color:#334155;">Nuestro equipo procesará su operación a la brevedad posible y le mantendremos informado.</p>
            <p class="note-text" style="margin-top:12px;">¿Consultas? Responda este correo o contacte a su asesor.</p>
        </div>

        <div class="email-footer">
            <p class="footer-brand">QoriCash</p>
            <p class="footer-meta">RUC: 20615113698 &nbsp;·&nbsp; <a href="mailto:info@qoricash.pe" class="footer-link">info@qoricash.pe</a></p>
            <p class="footer-copy">© 2025 QoriCash. Todos los derechos reservados.</p>
        </div>

    </div>
</div>
</body>
</html>"""
        return render_template_string(template, operation=operation)

    @staticmethod
    def _render_completed_operation_template(operation):
        """Renderizar plantilla HTML para operación completada"""
        template = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body, table, td, p, h1, h2, h3 { margin: 0; padding: 0; }
        body { background-color: #f0f4f8; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; }
        .email-wrapper { padding: 28px 16px; }
        .email-card { max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 24px rgba(13,27,42,0.09); }
        .email-header { background-color: #0D1B2A; padding: 30px 40px 26px; text-align: center; }
        .logo-wrap { display: inline-block; border: 1.5px solid rgba(0,222,168,0.35); border-radius: 8px; padding: 7px 22px; margin-bottom: 10px; }
        .logo-text { color: #00DEA8; font-size: 21px; font-weight: 700; letter-spacing: 1.5px; }
        .tagline { color: rgba(255,255,255,0.40); font-size: 11px; letter-spacing: 0.6px; margin-top: 6px; }
        .accent-bar { height: 3px; background-color: #00DEA8; }
        .email-body { padding: 36px 40px; color: #334155; font-size: 15px; line-height: 1.65; }
        .success-banner { background-color: #f0fdf4; border: 1.5px solid #86efac; border-radius: 10px; padding: 20px 24px; text-align: center; margin: 20px 0; }
        .success-banner h2 { color: #15803d; font-size: 17px; font-weight: 700; margin-bottom: 6px; }
        .success-banner p { color: #166534; font-size: 14px; }
        .section-label { font-size: 11px; font-weight: 700; color: #00DEA8; text-transform: uppercase; letter-spacing: 1.2px; margin: 24px 0 10px 0; }
        .data-box { background: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0; overflow: hidden; margin: 0 0 20px 0; }
        .data-row { padding: 10px 18px; border-bottom: 1px solid #f1f5f9; font-size: 14px; }
        .data-row:last-child { border-bottom: none; }
        .data-label { color: #64748b; font-weight: 600; display: inline-block; min-width: 150px; }
        .data-value { color: #1e293b; font-weight: 500; }
        .proof-btn { display: inline-block; background-color: #0D1B2A; color: #00DEA8; border: 1.5px solid #00DEA8; padding: 10px 22px; border-radius: 6px; text-decoration: none; font-size: 13px; font-weight: 600; margin: 4px 0; }
        .divider { height: 1px; background-color: #f1f5f9; margin: 24px 0; }
        .note-text { font-size: 13px; color: #94a3b8; line-height: 1.6; }
        .email-footer { background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 22px 40px; text-align: center; }
        .footer-brand { color: #0D1B2A; font-size: 14px; font-weight: 700; margin-bottom: 4px; }
        .footer-meta { color: #94a3b8; font-size: 12px; }
        .footer-link { color: #00DEA8; text-decoration: none; }
        .footer-copy { color: #cbd5e1; font-size: 11px; margin-top: 8px; }
        @media only screen and (max-width: 620px) {
            .email-body { padding: 24px 20px !important; }
            .email-header { padding: 24px 20px !important; }
            .data-label { display: block !important; min-width: unset !important; margin-bottom: 2px; }
        }
    </style>
</head>
<body>
<div class="email-wrapper">
    <div class="email-card">

        <div class="email-header">
            <div class="logo-wrap"><span class="logo-text">QoriCash</span></div>
            <p class="tagline">Operación completada</p>
        </div>
        <div class="accent-bar"></div>

        <div class="email-body">
            <p>Estimado(a) <strong>{{ operation.client.full_name or operation.client.razon_social }}</strong>,</p>

            <div class="success-banner">
                <h2>¡Operación completada!</h2>
                <p>Su operación ha sido procesada satisfactoriamente.</p>
            </div>

            <p class="section-label">Detalle de la operación</p>
            <div class="data-box">
                <div class="data-row">
                    <span class="data-label">Código</span>
                    <span class="data-value" style="font-weight:700;color:#0D1B2A;">{{ operation.operation_id }}</span>
                </div>
                <div class="data-row">
                    <span class="data-label">Tipo</span>
                    <span class="data-value">{{ operation.operation_type }}</span>
                </div>
                <div class="data-row">
                    <span class="data-label">Monto USD</span>
                    <span class="data-value" style="color:#059669;font-weight:700;font-size:16px;">$ {{ "{:,.2f}".format(operation.amount_usd) }}</span>
                </div>
                <div class="data-row">
                    <span class="data-label">Tipo de cambio</span>
                    <span class="data-value">{{ "%.4f"|format(operation.exchange_rate) }}</span>
                </div>
                <div class="data-row">
                    <span class="data-label">Monto PEN</span>
                    <span class="data-value" style="color:#dc2626;font-weight:700;font-size:16px;">S/ {{ "{:,.2f}".format(operation.amount_pen) }}</span>
                </div>
                <div class="data-row">
                    <span class="data-label">Fecha de creación</span>
                    <span class="data-value">{{ operation.created_at.strftime('%d/%m/%Y %H:%M') }}</span>
                </div>
                <div class="data-row">
                    <span class="data-label">Fecha de completado</span>
                    <span class="data-value" style="color:#059669;font-weight:600;">{{ operation.completed_at.strftime('%d/%m/%Y %H:%M') if operation.completed_at else '-' }}</span>
                </div>
            </div>

            {% if operation.operator_proofs and operation.operator_proofs|length > 0 %}
            <p class="section-label">Comprobante(s)</p>
            <div class="data-box" style="padding:14px 18px;">
                {% for proof in operation.operator_proofs %}
                <div style="margin:6px 0;">
                    <a href="{{ proof.comprobante_url if proof.comprobante_url else proof }}"
                       target="_blank" class="proof-btn">
                        Ver comprobante{% if operation.operator_proofs|length > 1 %} {{ loop.index }}{% endif %}
                    </a>
                    {% if proof.comentario %}
                    <p style="margin:5px 0 0 0;font-size:13px;color:#64748b;font-style:italic;">{{ proof.comentario }}</p>
                    {% endif %}
                </div>
                {% endfor %}
            </div>
            {% endif %}

            <div class="divider"></div>
            <p style="font-size:14px;color:#334155;">Gracias por confiar en <strong>QoriCash</strong> para sus operaciones cambiarias.</p>
            <p class="note-text" style="margin-top:10px;">¿Consultas? Responda este correo o contacte a su asesor comercial.</p>
        </div>

        <div class="email-footer">
            <p class="footer-brand">QoriCash</p>
            <p class="footer-meta">RUC: 20615113698 &nbsp;·&nbsp; <a href="mailto:info@qoricash.pe" class="footer-link">info@qoricash.pe</a></p>
            <p class="footer-copy">© 2025 QoriCash. Todos los derechos reservados.</p>
        </div>

    </div>
</div>
</body>
</html>"""
        return render_template_string(template, operation=operation)

    @staticmethod
    def send_canceled_operation_email(operation, reason=None):
        """
        Enviar correo de notificación de operación cancelada

        Args:
            operation: Objeto Operation
            reason: Motivo de cancelación (opcional)

        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            to = [operation.client.email] if operation.client and operation.client.email else []

            cc = []
            if operation.user and operation.user.email:
                cc.append(operation.user.email)

            if not to and not cc:
                logger.warning(f'No hay destinatarios para correo de cancelación de operación {operation.operation_id}')
                return False, 'No hay destinatarios configurados'

            subject = f'Operación Cancelada — {operation.operation_id} | QoriCash'
            html_body = EmailService._render_canceled_operation_template(operation, reason)

            msg = Message(
                subject=subject,
                recipients=to,
                cc=cc,
                html=html_body
            )

            EmailService._send_async(msg, timeout=15)
            logger.info(f'Email de cancelación programado para operación {operation.operation_id}')
            return True, 'Email programado para envío'

        except Exception as e:
            logger.error(f'Error al enviar email de cancelación {operation.operation_id}: {str(e)}')
            return False, f'Error al enviar email: {str(e)}'

    @staticmethod
    def _render_canceled_operation_template(operation, reason=None):
        """Renderizar plantilla HTML para operación cancelada"""
        template = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body, table, td, p, h1, h2, h3 { margin: 0; padding: 0; }
        body { background-color: #f0f4f8; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; }
        .email-wrapper { padding: 28px 16px; }
        .email-card { max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 24px rgba(13,27,42,0.09); }
        .email-header { background-color: #0D1B2A; padding: 30px 40px 26px; text-align: center; }
        .logo-wrap { display: inline-block; border: 1.5px solid rgba(0,222,168,0.35); border-radius: 8px; padding: 7px 22px; margin-bottom: 10px; }
        .logo-text { color: #00DEA8; font-size: 21px; font-weight: 700; letter-spacing: 1.5px; }
        .tagline { color: rgba(255,255,255,0.40); font-size: 11px; letter-spacing: 0.6px; margin-top: 6px; }
        .accent-bar { height: 3px; background-color: #ef4444; }
        .email-body { padding: 36px 40px; color: #334155; font-size: 15px; line-height: 1.65; }
        .cancel-banner { background-color: #fef2f2; border: 1.5px solid #fecaca; border-radius: 10px; padding: 20px 24px; text-align: center; margin: 20px 0; }
        .cancel-banner h2 { color: #991b1b; font-size: 17px; font-weight: 700; margin-bottom: 6px; }
        .cancel-banner p { color: #7f1d1d; font-size: 14px; }
        .section-label { font-size: 11px; font-weight: 700; color: #00DEA8; text-transform: uppercase; letter-spacing: 1.2px; margin: 24px 0 10px 0; }
        .alert { border-radius: 8px; padding: 13px 16px; margin: 14px 0; font-size: 13.5px; line-height: 1.65; }
        .alert.warning { background: #fffbeb; border-left: 3px solid #f59e0b; color: #78350f; }
        .alert.info { background: #f0f9ff; border-left: 3px solid #0ea5e9; color: #0c4a6e; }
        .divider { height: 1px; background-color: #f1f5f9; margin: 24px 0; }
        .note-text { font-size: 13px; color: #94a3b8; line-height: 1.6; }
        .email-footer { background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 22px 40px; text-align: center; }
        .footer-brand { color: #0D1B2A; font-size: 14px; font-weight: 700; margin-bottom: 4px; }
        .footer-meta { color: #94a3b8; font-size: 12px; }
        .footer-link { color: #00DEA8; text-decoration: none; }
        .footer-copy { color: #cbd5e1; font-size: 11px; margin-top: 8px; }
        @media only screen and (max-width: 620px) {
            .email-body { padding: 24px 20px !important; }
            .email-header { padding: 24px 20px !important; }
        }
    </style>
</head>
<body>
<div class="email-wrapper">
    <div class="email-card">

        <div class="email-header">
            <div class="logo-wrap"><span class="logo-text">QoriCash</span></div>
            <p class="tagline">Operación cancelada</p>
        </div>
        <div class="accent-bar"></div>

        <div class="email-body">
            <p>Estimado(a) <strong>{{ operation.client.full_name or operation.client.razon_social }}</strong>,</p>

            <div class="cancel-banner">
                <h2>Operación cancelada</h2>
                <p>La siguiente operación ha sido cancelada en nuestro sistema.</p>
            </div>

            <p class="section-label">Detalle de la operación</p>
            <table width="100%" cellspacing="0" cellpadding="0" style="background:#f8fafc;border-radius:8px;border:1px solid #e2e8f0;border-collapse:collapse;font-size:14px;margin:0 0 20px 0;">
                <tr style="border-bottom:1px solid #f1f5f9;">
                    <td style="padding:10px 18px;color:#64748b;font-weight:600;width:160px;vertical-align:middle;white-space:nowrap;">Código</td>
                    <td style="padding:10px 18px;color:#0D1B2A;font-weight:700;vertical-align:middle;">{{ operation.operation_id }}</td>
                </tr>
                <tr style="border-bottom:1px solid #f1f5f9;">
                    <td style="padding:10px 18px;color:#64748b;font-weight:600;white-space:nowrap;vertical-align:middle;">Tipo</td>
                    <td style="padding:10px 18px;color:#1e293b;font-weight:500;vertical-align:middle;">{{ operation.operation_type }}</td>
                </tr>
                <tr style="border-bottom:1px solid #f1f5f9;">
                    <td style="padding:10px 18px;color:#64748b;font-weight:600;white-space:nowrap;vertical-align:middle;">Monto USD</td>
                    <td style="padding:10px 18px;color:#1e293b;font-weight:700;font-size:16px;vertical-align:middle;">$ {{ "{:,.2f}".format(operation.amount_usd) }}</td>
                </tr>
                <tr style="border-bottom:1px solid #f1f5f9;">
                    <td style="padding:10px 18px;color:#64748b;font-weight:600;white-space:nowrap;vertical-align:middle;">Tipo de cambio</td>
                    <td style="padding:10px 18px;color:#1e293b;font-weight:500;vertical-align:middle;">{{ "%.4f"|format(operation.exchange_rate) }}</td>
                </tr>
                <tr style="border-bottom:1px solid #f1f5f9;">
                    <td style="padding:10px 18px;color:#64748b;font-weight:600;white-space:nowrap;vertical-align:middle;">Monto PEN</td>
                    <td style="padding:10px 18px;color:#1e293b;font-weight:700;font-size:16px;vertical-align:middle;">S/ {{ "{:,.2f}".format(operation.amount_pen) }}</td>
                </tr>
                <tr style="border-bottom:1px solid #f1f5f9;">
                    <td style="padding:10px 18px;color:#64748b;font-weight:600;white-space:nowrap;vertical-align:middle;">Fecha</td>
                    <td style="padding:10px 18px;color:#1e293b;font-weight:500;vertical-align:middle;">{{ operation.created_at.strftime('%d/%m/%Y %H:%M') }}</td>
                </tr>
                <tr>
                    <td style="padding:10px 18px;color:#64748b;font-weight:600;white-space:nowrap;vertical-align:middle;">Estado</td>
                    <td style="padding:10px 18px;vertical-align:middle;">
                        <span style="display:inline-block;padding:3px 12px;border-radius:20px;font-size:12px;font-weight:700;background:#fee2e2;color:#991b1b;">CANCELADO</span>
                    </td>
                </tr>
            </table>

            {% if reason %}
            <div class="alert warning">
                <strong>Motivo de cancelación:</strong> {{ reason }}
            </div>
            {% endif %}

            <div class="alert info">
                Si desea realizar una nueva operación, puede ingresar a <strong>www.qoricash.pe</strong> o contactar a su asesor comercial.
            </div>

            <div class="divider"></div>
            <p class="note-text">¿Consultas? Responda este correo o escríbanos a <a href="mailto:info@qoricash.pe" class="footer-link">info@qoricash.pe</a></p>
        </div>

        <div class="email-footer">
            <p class="footer-brand">QoriCash</p>
            <p class="footer-meta">RUC: 20615113698 &nbsp;·&nbsp; <a href="mailto:info@qoricash.pe" class="footer-link">info@qoricash.pe</a></p>
            <p class="footer-copy">© 2025 QoriCash. Todos los derechos reservados.</p>
        </div>

    </div>
</div>
</body>
</html>"""
        return render_template_string(template, operation=operation, reason=reason)

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
            # Destinatario principal: Cliente
            to = [client.email] if client.email else []

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

            # Enviar ASÍNCRONO para no bloquear el worker
            EmailService._send_async(msg, timeout=15)

            logger.info(f'Email de nuevo cliente programado para envío: {client.id}')
            return True, 'Email programado para envío'

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
            from flask import current_app
            from flask_mail import Message, Mail

            logger.info(f'[EMAIL] Iniciando envio de email de cliente activado {client.id}')

            # Destinatario principal: Cliente
            to = [client.email] if client.email else []

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
            # Si no están configuradas, usar las credenciales regulares como fallback
            confirmation_username = current_app.config.get('MAIL_CONFIRMATION_USERNAME') or current_app.config.get('MAIL_USERNAME')
            confirmation_password = current_app.config.get('MAIL_CONFIRMATION_PASSWORD') or current_app.config.get('MAIL_PASSWORD')
            confirmation_sender = current_app.config.get('MAIL_CONFIRMATION_SENDER') or current_app.config.get('MAIL_DEFAULT_SENDER')

            logger.info(f'[EMAIL] Credenciales - Usuario: {confirmation_username}, Remitente: {confirmation_sender}')

            if not confirmation_username or not confirmation_password:
                logger.error('[EMAIL] Credenciales de email no configuradas')
                return False, 'Email no configurado'

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

                # Enviar ASÍNCRONO para no bloquear el worker
                logger.info(f'[EMAIL] Programando envío de email a TO: {to}, CC: {cc}')
                EmailService._send_async(msg, timeout=15)

                logger.info(f'[EMAIL] Email de cliente activado programado para envío desde {confirmation_sender}: {client.id}')
                return True, 'Email programado para envío'

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
    def send_temporary_password_email(client_email, client_name, temp_password):
        """
        Enviar correo con contraseña temporal al cliente

        Args:
            client_email: Email del cliente
            client_name: Nombre del cliente
            temp_password: Contraseña temporal generada

        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            from flask_mail import Message

            logger.info(f'[EMAIL] Iniciando envío de contraseña temporal a {client_email}')

            # Destinatario
            to = [client_email]

            # Asunto
            subject = 'Recuperación de Contraseña - QoriCash'

            # Contenido HTML
            html_body = EmailService._render_temporary_password_template(client_name, temp_password)

            # Crear mensaje
            msg = Message(
                subject=subject,
                recipients=to,
                html=html_body
            )

            # Enviar ASÍNCRONO
            EmailService._send_async(msg, timeout=15)

            logger.info(f'[EMAIL] Email de contraseña temporal programado para envío a {client_email}')
            return True, 'Email programado para envío'

        except Exception as e:
            logger.error(f'[EMAIL] ERROR al enviar email de contraseña temporal: {str(e)}')
            logger.exception(e)
            return False, f'Error al enviar email: {str(e)}'

    @staticmethod
    def _render_temporary_password_template(client_name, temp_password):
        """Renderizar plantilla HTML para contraseña temporal"""
        template = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body, table, td, p, h1, h2, h3 { margin: 0; padding: 0; }
        body { background-color: #f0f4f8; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; }
        .email-wrapper { padding: 28px 16px; }
        .email-card { max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 24px rgba(13,27,42,0.09); }
        .email-header { background-color: #0D1B2A; padding: 30px 40px 26px; text-align: center; }
        .logo-wrap { display: inline-block; border: 1.5px solid rgba(0,222,168,0.35); border-radius: 8px; padding: 7px 22px; margin-bottom: 10px; }
        .logo-text { color: #00DEA8; font-size: 21px; font-weight: 700; letter-spacing: 1.5px; }
        .tagline { color: rgba(255,255,255,0.40); font-size: 11px; letter-spacing: 0.6px; margin-top: 6px; }
        .accent-bar { height: 3px; background-color: #00DEA8; }
        .email-body { padding: 36px 40px; color: #334155; font-size: 15px; line-height: 1.65; }
        .section-label { font-size: 11px; font-weight: 700; color: #00DEA8; text-transform: uppercase; letter-spacing: 1.2px; margin: 24px 0 10px 0; }
        .password-box { background-color: #0D1B2A; border-radius: 10px; padding: 22px 24px; text-align: center; margin: 16px 0; }
        .password-label { color: rgba(255,255,255,0.50); font-size: 11px; letter-spacing: 0.8px; text-transform: uppercase; margin-bottom: 10px; }
        .password-code { color: #00DEA8; font-size: 28px; font-family: 'Courier New', Courier, monospace; font-weight: 700; letter-spacing: 4px; }
        .password-hint { color: rgba(255,255,255,0.35); font-size: 11px; margin-top: 10px; }
        .alert { border-radius: 8px; padding: 13px 16px; margin: 14px 0; font-size: 13.5px; line-height: 1.65; }
        .alert.danger { background: #fef2f2; border-left: 3px solid #ef4444; color: #7f1d1d; }
        .alert.info { background: #f0f9ff; border-left: 3px solid #0ea5e9; color: #0c4a6e; }
        .steps-box { background: #f8fafc; border-radius: 8px; padding: 14px 18px 14px 14px; margin: 14px 0; }
        .steps-box ol { margin: 0; padding-left: 22px; }
        .steps-box li { padding: 5px 0; font-size: 14px; color: #334155; }
        .data-box { background: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0; overflow: hidden; margin: 0 0 20px 0; }
        .data-row { padding: 9px 18px; border-bottom: 1px solid #f1f5f9; font-size: 14px; }
        .data-row:last-child { border-bottom: none; }
        .divider { height: 1px; background-color: #f1f5f9; margin: 24px 0; }
        .note-text { font-size: 13px; color: #94a3b8; line-height: 1.6; }
        .email-footer { background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 22px 40px; text-align: center; }
        .footer-brand { color: #0D1B2A; font-size: 14px; font-weight: 700; margin-bottom: 4px; }
        .footer-meta { color: #94a3b8; font-size: 12px; }
        .footer-link { color: #00DEA8; text-decoration: none; }
        .footer-copy { color: #cbd5e1; font-size: 11px; margin-top: 8px; }
        @media only screen and (max-width: 620px) {
            .email-body { padding: 24px 20px !important; }
            .email-header { padding: 24px 20px !important; }
        }
    </style>
</head>
<body>
<div class="email-wrapper">
    <div class="email-card">

        <div class="email-header">
            <div class="logo-wrap"><span class="logo-text">QoriCash</span></div>
            <p class="tagline">Recuperación de contraseña</p>
        </div>
        <div class="accent-bar"></div>

        <div class="email-body">
            <p>Hola <strong>{{ client_name }}</strong>,</p>
            <p style="margin-top:10px;color:#64748b;font-size:14px;">Hemos recibido tu solicitud. A continuación tu contraseña temporal de acceso:</p>

            <p class="section-label">Tu contraseña temporal</p>
            <div class="password-box">
                <p class="password-label">Contraseña de acceso</p>
                <p class="password-code">{{ temp_password }}</p>
                <p class="password-hint">Cópiala exactamente como aparece</p>
            </div>

            <div class="alert danger">
                <strong>Seguridad:</strong> Deberás cambiar esta contraseña al iniciar sesión. No la compartas con nadie.
            </div>

            <p class="section-label">Pasos a seguir</p>
            <div class="steps-box">
                <ol>
                    <li>Ingresa a QoriCash con tu número de documento y esta contraseña</li>
                    <li>El sistema te pedirá establecer una nueva contraseña segura</li>
                    <li>¡Listo! Ya puedes operar con normalidad</li>
                </ol>
            </div>

            <p class="section-label">Requisitos para tu nueva contraseña</p>
            <div class="data-box">
                <div class="data-row" style="color:#334155;">Mínimo 8 caracteres</div>
                <div class="data-row" style="color:#334155;">Al menos una letra mayúscula</div>
                <div class="data-row" style="color:#334155;">Al menos una letra minúscula</div>
                <div class="data-row" style="color:#334155;">Al menos un número</div>
            </div>

            <div class="alert info">
                <strong>¿No solicitaste este cambio?</strong> Contacta a nuestro equipo de soporte inmediatamente en <a href="mailto:info@qoricash.pe" style="color:#0c4a6e;">info@qoricash.pe</a>
            </div>

            <div class="divider"></div>
            <p class="note-text">Este correo fue generado automáticamente. Por favor no respondas a este mensaje.</p>
        </div>

        <div class="email-footer">
            <p class="footer-brand">QoriCash</p>
            <p class="footer-meta">RUC: 20615113698 &nbsp;·&nbsp; <a href="mailto:info@qoricash.pe" class="footer-link">info@qoricash.pe</a></p>
            <p class="footer-copy">© 2025 QoriCash. Todos los derechos reservados.</p>
        </div>

    </div>
</div>
</body>
</html>"""
        return render_template_string(template, client_name=client_name, temp_password=temp_password)

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

        template = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body, table, td, p, h1, h2, h3 { margin: 0; padding: 0; }
        body { background-color: #f0f4f8; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; }
        .email-wrapper { padding: 28px 16px; }
        .email-card { max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 24px rgba(13,27,42,0.09); }
        .email-header { background-color: #0D1B2A; padding: 30px 40px 26px; text-align: center; }
        .logo-wrap { display: inline-block; border: 1.5px solid rgba(0,222,168,0.35); border-radius: 8px; padding: 7px 22px; margin-bottom: 10px; }
        .logo-text { color: #00DEA8; font-size: 21px; font-weight: 700; letter-spacing: 1.5px; }
        .tagline { color: rgba(255,255,255,0.40); font-size: 11px; letter-spacing: 0.6px; margin-top: 6px; }
        .accent-bar { height: 3px; background-color: #00DEA8; }
        .email-body { padding: 36px 40px; color: #334155; font-size: 15px; line-height: 1.65; }
        .status-box { border-radius: 10px; padding: 20px 24px; text-align: center; margin: 20px 0; background-color: #fffbeb; border: 1.5px solid #fcd34d; }
        .status-box h2 { font-size: 17px; font-weight: 700; color: #92400e; margin-bottom: 6px; }
        .status-box p { font-size: 14px; color: #78350f; }
        .section-label { font-size: 11px; font-weight: 700; color: #00DEA8; text-transform: uppercase; letter-spacing: 1.2px; margin: 24px 0 10px 0; }
        .data-box { background: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0; overflow: hidden; margin: 0 0 20px 0; }
        .data-row { padding: 10px 18px; border-bottom: 1px solid #f1f5f9; font-size: 14px; }
        .data-row:last-child { border-bottom: none; }
        .data-label { color: #64748b; font-weight: 600; display: inline-block; min-width: 150px; }
        .data-value { color: #1e293b; font-weight: 500; }
        .divider { height: 1px; background-color: #f1f5f9; margin: 24px 0; }
        .note-text { font-size: 13px; color: #94a3b8; line-height: 1.6; }
        .email-footer { background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 22px 40px; text-align: center; }
        .footer-brand { color: #0D1B2A; font-size: 14px; font-weight: 700; margin-bottom: 4px; }
        .footer-meta { color: #94a3b8; font-size: 12px; }
        .footer-link { color: #00DEA8; text-decoration: none; }
        .footer-copy { color: #cbd5e1; font-size: 11px; margin-top: 8px; }
        @media only screen and (max-width: 620px) {
            .email-body { padding: 24px 20px !important; }
            .email-header { padding: 24px 20px !important; }
            .data-label { display: block !important; min-width: unset !important; margin-bottom: 2px; }
        }
    </style>
</head>
<body>
<div class="email-wrapper">
    <div class="email-card">

        <div class="email-header">
            <div class="logo-wrap"><span class="logo-text">QoriCash</span></div>
            <p class="tagline">Registro en proceso</p>
        </div>
        <div class="accent-bar"></div>

        <div class="email-body">
            <p>Estimado(a) <strong>{{ client.full_name or client.razon_social }}</strong>,</p>
            <p style="margin-top:10px;color:#64748b;font-size:14px;">Hemos recibido su solicitud de registro a través de su ejecutivo comercial <strong>{{ trader.username }}</strong>. Estamos validando su información y pronto le notificaremos la activación de su cuenta.</p>

            <p class="section-label">Datos de registro</p>
            <div class="data-box">
                <div class="data-row">
                    <span class="data-label">Cliente</span>
                    <span class="data-value">{{ client.full_name or client.razon_social }}</span>
                </div>
                {% if client.document_type %}
                <div class="data-row">
                    <span class="data-label">Tipo de documento</span>
                    <span class="data-value">{{ client.document_type }}</span>
                </div>
                {% endif %}
                {% if client.document_number %}
                <div class="data-row">
                    <span class="data-label">Número de documento</span>
                    <span class="data-value">{{ client.document_number }}</span>
                </div>
                {% endif %}
                {% if client.phone %}
                <div class="data-row">
                    <span class="data-label">Teléfono</span>
                    <span class="data-value">{{ client.phone }}</span>
                </div>
                {% endif %}
                <div class="data-row">
                    <span class="data-label">Cuentas bancarias</span>
                    <span class="data-value">{{ bank_accounts_text }}</span>
                </div>
                <div class="data-row">
                    <span class="data-label">Ejecutivo asignado</span>
                    <span class="data-value" style="color:#00a87a;font-weight:600;">{{ trader.username }}</span>
                </div>
            </div>

            <div class="divider"></div>
            <p style="font-size:14px;color:#334155;">Para cualquier consulta, contacte a su ejecutivo <strong>{{ trader.username }}</strong>{% if trader.email %} en <a href="mailto:{{ trader.email }}" class="footer-link">{{ trader.email }}</a>{% endif %}.</p>
            <p class="note-text" style="margin-top:10px;">Este es un correo automático.</p>
        </div>

        <div class="email-footer">
            <p class="footer-brand">QoriCash</p>
            <p class="footer-meta">RUC: 20615113698 &nbsp;·&nbsp; <a href="mailto:info@qoricash.pe" class="footer-link">info@qoricash.pe</a></p>
            <p class="footer-copy">© 2025 QoriCash. Todos los derechos reservados.</p>
        </div>

    </div>
</div>
</body>
</html>"""
        return render_template_string(template, client=client, trader=trader, bank_accounts_text=bank_accounts_text)

    @staticmethod
    def _render_client_activation_template(client, trader):
        """Renderizar plantilla HTML para cliente activado"""
        template = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body, table, td, p, h1, h2, h3 { margin: 0; padding: 0; }
        body { background-color: #f0f4f8; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; }
        .email-wrapper { padding: 28px 16px; }
        .email-card { max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 24px rgba(13,27,42,0.09); }
        .email-header { background-color: #0D1B2A; padding: 30px 40px 26px; text-align: center; }
        .logo-wrap { display: inline-block; border: 1.5px solid rgba(0,222,168,0.35); border-radius: 8px; padding: 7px 22px; margin-bottom: 10px; }
        .logo-text { color: #00DEA8; font-size: 21px; font-weight: 700; letter-spacing: 1.5px; }
        .tagline { color: rgba(255,255,255,0.40); font-size: 11px; letter-spacing: 0.6px; margin-top: 6px; }
        .accent-bar { height: 3px; background-color: #00DEA8; }
        .email-body { padding: 36px 40px; color: #334155; font-size: 15px; line-height: 1.65; }
        .success-banner { background-color: #f0fdf4; border: 1.5px solid #86efac; border-radius: 10px; padding: 20px 24px; text-align: center; margin: 20px 0; }
        .success-banner h2 { color: #15803d; font-size: 17px; font-weight: 700; margin-bottom: 6px; }
        .success-banner p { color: #166534; font-size: 14px; }
        .section-label { font-size: 11px; font-weight: 700; color: #00DEA8; text-transform: uppercase; letter-spacing: 1.2px; margin: 24px 0 10px 0; }
        .data-box { background: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0; overflow: hidden; margin: 0 0 20px 0; }
        .data-row { padding: 10px 18px; border-bottom: 1px solid #f1f5f9; font-size: 14px; }
        .data-row:last-child { border-bottom: none; }
        .data-label { color: #64748b; font-weight: 600; display: inline-block; min-width: 150px; }
        .data-value { color: #1e293b; font-weight: 500; }
        .cta-wrap { text-align: center; margin: 28px 0 20px 0; }
        .cta-btn { display: inline-block; background-color: #00DEA8; color: #0D1B2A; font-weight: 700; font-size: 15px; padding: 13px 36px; border-radius: 8px; text-decoration: none; }
        .divider { height: 1px; background-color: #f1f5f9; margin: 24px 0; }
        .note-text { font-size: 13px; color: #94a3b8; line-height: 1.6; }
        .email-footer { background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 22px 40px; text-align: center; }
        .footer-brand { color: #0D1B2A; font-size: 14px; font-weight: 700; margin-bottom: 4px; }
        .footer-meta { color: #94a3b8; font-size: 12px; }
        .footer-link { color: #00DEA8; text-decoration: none; }
        .footer-copy { color: #cbd5e1; font-size: 11px; margin-top: 8px; }
        @media only screen and (max-width: 620px) {
            .email-body { padding: 24px 20px !important; }
            .email-header { padding: 24px 20px !important; }
            .data-label { display: block !important; min-width: unset !important; margin-bottom: 2px; }
        }
    </style>
</head>
<body>
<div class="email-wrapper">
    <div class="email-card">

        <div class="email-header">
            <div class="logo-wrap"><span class="logo-text">QoriCash</span></div>
            <p class="tagline">Cuenta activada</p>
        </div>
        <div class="accent-bar"></div>

        <div class="email-body">
            <p>Estimado(a) <strong>{{ client.full_name or client.razon_social }}</strong>,</p>

            <div class="success-banner">
                <h2>¡Bienvenido a QoriCash!</h2>
                <p>Su cuenta ha sido activada correctamente. Ya puede comenzar a operar.</p>
            </div>

            <p class="section-label">Información de su cuenta</p>
            <div class="data-box">
                <div class="data-row">
                    <span class="data-label">Cliente</span>
                    <span class="data-value">{{ client.full_name or client.razon_social }}</span>
                </div>
                {% if client.document_number %}
                <div class="data-row">
                    <span class="data-label">Documento</span>
                    <span class="data-value">{{ client.document_number }}</span>
                </div>
                {% endif %}
                <div class="data-row">
                    <span class="data-label">Correo electrónico</span>
                    <span class="data-value">{{ client.email }}</span>
                </div>
                <div class="data-row">
                    <span class="data-label">Estado</span>
                    <span class="data-value" style="color:#059669;font-weight:700;">ACTIVO</span>
                </div>
                <div class="data-row">
                    <span class="data-label">Ejecutivo asignado</span>
                    <span class="data-value" style="color:#00a87a;font-weight:600;">{{ trader.username }}</span>
                </div>
            </div>

            <p class="section-label">¿Qué puede hacer ahora?</p>
            <div class="data-box">
                <div class="data-row" style="color:#059669;">✓ &nbsp;Realizar operaciones de compra y venta de dólares</div>
                <div class="data-row" style="color:#059669;">✓ &nbsp;Acceder a tipos de cambio competitivos</div>
                <div class="data-row" style="color:#059669;">✓ &nbsp;Recibir atención personalizada de su ejecutivo</div>
                <div class="data-row" style="color:#059669;">✓ &nbsp;Transferencias rápidas y seguras</div>
            </div>

            <div class="cta-wrap">
                <a href="https://www.qoricash.pe" class="cta-btn">Iniciar sesión ahora</a>
            </div>

            <div class="divider"></div>
            <p class="note-text">Para su primera operación o cualquier consulta, contacte a <strong>{{ trader.username }}</strong>{% if trader.email %} en <a href="mailto:{{ trader.email }}" class="footer-link">{{ trader.email }}</a>{% endif %}. Gracias por confiar en QoriCash.</p>
        </div>

        <div class="email-footer">
            <p class="footer-brand">QoriCash</p>
            <p class="footer-meta">RUC: 20615113698 &nbsp;·&nbsp; <a href="mailto:info@qoricash.pe" class="footer-link">info@qoricash.pe</a></p>
            <p class="footer-copy">© 2025 QoriCash. Todos los derechos reservados.</p>
        </div>

    </div>
</div>
</body>
</html>"""
        return render_template_string(template, client=client, trader=trader)

    @staticmethod
    def send_complaint_email(complaint_data):
        """
        Enviar correo de reclamo/queja del libro de reclamaciones

        Args:
            complaint_data: dict con los datos del reclamo
                - tipo_documento: str
                - numero_documento: str
                - nombres: str (opcional)
                - apellidos: str (opcional)
                - razon_social: str (opcional)
                - persona_contacto: str (opcional)
                - email: str
                - telefono: str
                - direccion: str
                - tipo_solicitud: str ('Reclamo' o 'Queja')
                - detalle: str

        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            logger.info(f'[EMAIL] Iniciando envío de email de {complaint_data.get("tipo_solicitud", "Reclamo")}')

            # Destinatario principal: info@qoricash.pe
            to = ['info@qoricash.pe']

            # Copia: email del cliente
            cc = []
            if complaint_data.get('email'):
                cc.append(complaint_data['email'])

            logger.info(f'[EMAIL] Destinatarios - TO: {to}, CC: {cc}')

            # Determinar el nombre del cliente según tipo de documento
            if complaint_data.get('tipo_documento') == 'RUC':
                client_name = complaint_data.get('razon_social', 'Cliente')
            else:
                nombres = complaint_data.get('nombres', '')
                apellidos = complaint_data.get('apellidos', '')
                client_name = f"{nombres} {apellidos}".strip() or 'Cliente'

            # Asunto
            tipo_solicitud = complaint_data.get('tipo_solicitud', 'Reclamo')
            subject = f'[{tipo_solicitud}] Libro de Reclamaciones - {client_name}'

            # Contenido HTML
            html_body = EmailService._render_complaint_template(complaint_data)

            # Crear mensaje
            msg = Message(
                subject=subject,
                recipients=to,
                cc=cc if cc else None,
                html=html_body
            )

            # Enviar ASÍNCRONO para no bloquear
            EmailService._send_async(msg, timeout=15)

            logger.info(f'[EMAIL] Email de {tipo_solicitud} programado para envío')
            return True, 'Email programado para envío'

        except Exception as e:
            logger.error(f'[EMAIL] ERROR al enviar email de reclamo: {str(e)}')
            logger.exception(e)
            return False, f'Error al enviar email: {str(e)}'

    @staticmethod
    def _render_complaint_template(complaint_data):
        """Renderizar plantilla HTML para reclamo/queja del libro de reclamaciones"""
        template = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body, table, td, p, h1, h2, h3 { margin: 0; padding: 0; }
        body { background-color: #f0f4f8; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; }
        .email-wrapper { padding: 28px 16px; }
        .email-card { max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 24px rgba(13,27,42,0.09); }
        .email-header { background-color: #0D1B2A; padding: 30px 40px 26px; text-align: center; }
        .logo-wrap { display: inline-block; border: 1.5px solid rgba(0,222,168,0.35); border-radius: 8px; padding: 7px 22px; margin-bottom: 10px; }
        .logo-text { color: #00DEA8; font-size: 21px; font-weight: 700; letter-spacing: 1.5px; }
        .complaint-num { color: #ffffff; font-size: 17px; font-weight: 700; margin-top: 8px; letter-spacing: 0.5px; }
        .tagline { color: rgba(255,255,255,0.40); font-size: 11px; letter-spacing: 0.6px; margin-top: 6px; }
        .accent-bar { height: 3px; background-color: #f59e0b; }
        .email-body { padding: 36px 40px; color: #334155; font-size: 15px; line-height: 1.65; }
        .meta-row { font-size: 12.5px; color: #94a3b8; margin-bottom: 20px; }
        .section-label { font-size: 11px; font-weight: 700; color: #00DEA8; text-transform: uppercase; letter-spacing: 1.2px; margin: 24px 0 10px 0; }
        .data-box { background: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0; overflow: hidden; margin: 0 0 20px 0; }
        .data-row { padding: 10px 18px; border-bottom: 1px solid #f1f5f9; font-size: 14px; }
        .data-row:last-child { border-bottom: none; }
        .data-label { color: #64748b; font-weight: 600; display: inline-block; min-width: 160px; }
        .data-value { color: #1e293b; font-weight: 500; }
        .detail-box { background: #fffbeb; border: 1px solid #fcd34d; border-radius: 8px; padding: 16px 18px; margin: 0 0 20px 0; font-size: 14px; color: #78350f; white-space: pre-wrap; line-height: 1.7; }
        .alert { border-radius: 8px; padding: 13px 16px; margin: 14px 0; font-size: 13.5px; line-height: 1.65; }
        .alert.info { background: #f0f9ff; border-left: 3px solid #0ea5e9; color: #0c4a6e; }
        .divider { height: 1px; background-color: #f1f5f9; margin: 24px 0; }
        .note-text { font-size: 13px; color: #94a3b8; line-height: 1.6; }
        .email-footer { background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 22px 40px; text-align: center; }
        .footer-brand { color: #0D1B2A; font-size: 14px; font-weight: 700; margin-bottom: 4px; }
        .footer-meta { color: #94a3b8; font-size: 12px; }
        .footer-link { color: #00DEA8; text-decoration: none; }
        .footer-copy { color: #cbd5e1; font-size: 11px; margin-top: 8px; }
        @media only screen and (max-width: 620px) {
            .email-body { padding: 24px 20px !important; }
            .email-header { padding: 24px 20px !important; }
            .data-label { display: block !important; min-width: unset !important; margin-bottom: 2px; }
        }
    </style>
</head>
<body>
<div class="email-wrapper">
    <div class="email-card">

        <div class="email-header">
            <div class="logo-wrap"><span class="logo-text">QoriCash</span></div>
            <p class="complaint-num">{{ complaint_number }}</p>
            <p class="tagline">Libro de Reclamaciones</p>
        </div>
        <div class="accent-bar"></div>

        <div class="email-body">
            <p class="meta-row">Fecha de registro: {{ fecha_actual }}</p>

            <p class="section-label">Datos del reclamante</p>
            <div class="data-box">
                {% if complaint_data.get('tipo_documento') == 'RUC' %}
                <div class="data-row">
                    <span class="data-label">Tipo de documento</span>
                    <span class="data-value">RUC</span>
                </div>
                <div class="data-row">
                    <span class="data-label">Número de RUC</span>
                    <span class="data-value">{{ complaint_data.get('numero_documento', '—') }}</span>
                </div>
                <div class="data-row">
                    <span class="data-label">Razón social</span>
                    <span class="data-value">{{ complaint_data.get('razon_social', '—') }}</span>
                </div>
                <div class="data-row">
                    <span class="data-label">Persona de contacto</span>
                    <span class="data-value">{{ complaint_data.get('persona_contacto', '—') }}</span>
                </div>
                {% else %}
                <div class="data-row">
                    <span class="data-label">Tipo de documento</span>
                    <span class="data-value">{{ complaint_data.get('tipo_documento', 'DNI') }}</span>
                </div>
                <div class="data-row">
                    <span class="data-label">Número de documento</span>
                    <span class="data-value">{{ complaint_data.get('numero_documento', '—') }}</span>
                </div>
                <div class="data-row">
                    <span class="data-label">Nombres</span>
                    <span class="data-value">{{ complaint_data.get('nombres', '—') }}</span>
                </div>
                <div class="data-row">
                    <span class="data-label">Apellidos</span>
                    <span class="data-value">{{ complaint_data.get('apellidos', '—') }}</span>
                </div>
                {% endif %}
                <div class="data-row">
                    <span class="data-label">Correo electrónico</span>
                    <span class="data-value">{{ complaint_data.get('email', '—') }}</span>
                </div>
                <div class="data-row">
                    <span class="data-label">Teléfono</span>
                    <span class="data-value">{{ complaint_data.get('telefono', '—') }}</span>
                </div>
                <div class="data-row">
                    <span class="data-label">Dirección</span>
                    <span class="data-value">{{ complaint_data.get('direccion', '—') }}</span>
                </div>
            </div>

            <p class="section-label">Detalle del {{ complaint_data.get('tipo_solicitud', 'reclamo') }}</p>
            <div class="detail-box">{{ complaint_data.get('detalle', 'No se proporcionó detalle.') }}</div>

            <div class="alert info">
                <strong>Plazo de respuesta:</strong> Este {{ complaint_data.get('tipo_solicitud', 'reclamo').lower() }} debe ser atendido dentro de las próximas 24–48 horas hábiles.
            </div>

            <div class="divider"></div>
            <p class="note-text">Correo generado automáticamente desde el Libro de Reclamaciones de QoriCash.</p>
        </div>

        <div class="email-footer">
            <p class="footer-brand">QoriCash</p>
            <p class="footer-meta">RUC: 20615113698 &nbsp;·&nbsp; <a href="mailto:info@qoricash.pe" class="footer-link">info@qoricash.pe</a></p>
            <p class="footer-copy">© 2025 QoriCash. Todos los derechos reservados.</p>
        </div>

    </div>
</div>
</body>
</html>"""
        from datetime import datetime
        import pytz

        # Obtener fecha actual en zona horaria de Perú
        tz_peru = pytz.timezone('America/Lima')
        fecha_actual = datetime.now(tz_peru).strftime('%d/%m/%Y %H:%M:%S')

        complaint_number = complaint_data.get('complaint_number', 'N/A')
        return render_template_string(template, complaint_data=complaint_data, fecha_actual=fecha_actual, complaint_number=complaint_number)
