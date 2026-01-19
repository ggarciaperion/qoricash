"""
Plantillas de correos diferenciados por canal de registro
Según especificaciones de correos transaccionales de QoriCash
"""
import logging
from flask import render_template_string
from flask_mail import Message
from app.extensions import mail
from app.models.user import User

logger = logging.getLogger(__name__)


class EmailTemplates:
    """Plantillas de correo diferenciadas por origen"""

    @staticmethod
    def send_welcome_email_from_mobile(client):
        """
        Correo de bienvenida para clientes registrados desde app móvil
        - NO incluye contraseña (definida por el usuario)
        - Menciona acceso a página web

        Args:
            client: Objeto Client

        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            logger.info(f'📧 [EMAIL-MOBILE] Enviando bienvenida desde móvil a {client.dni}')

            to = [client.email] if client.email else []
            if not to:
                return False, 'Cliente sin email'

            subject = '¡Bienvenido a QoriCash!'

            html_body = EmailTemplates._render_mobile_welcome_template(client)

            msg = Message(
                subject=subject,
                recipients=to,
                html=html_body
            )

            mail.send(msg)
            logger.info(f'✅ [EMAIL-MOBILE] Email enviado a {client.dni}')
            return True, 'Email enviado'

        except Exception as e:
            logger.error(f'❌ [EMAIL-MOBILE] Error: {str(e)}')
            return False, str(e)

    @staticmethod
    def send_welcome_email_from_web(client):
        """
        Correo de bienvenida para clientes registrados desde página web
        - NO incluye contraseña (definida por el usuario)
        - Menciona acceso a app móvil

        Args:
            client: Objeto Client

        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            logger.info(f'📧 [EMAIL-WEB] Enviando bienvenida desde web a {client.dni}')

            to = [client.email] if client.email else []
            if not to:
                return False, 'Cliente sin email'

            subject = '¡Bienvenido a QoriCash!'

            html_body = EmailTemplates._render_web_welcome_template(client)

            msg = Message(
                subject=subject,
                recipients=to,
                html=html_body
            )

            mail.send(msg)
            logger.info(f'✅ [EMAIL-WEB] Email enviado a {client.dni}')
            return True, 'Email enviado'

        except Exception as e:
            logger.error(f'❌ [EMAIL-WEB] Error: {str(e)}')
            return False, str(e)

    @staticmethod
    def send_activation_with_temp_password(client, trader, temporary_password):
        """
        Correo de activación con contraseña temporal
        Solo para clientes creados por Traders
        - SÍ incluye contraseña temporal
        - Menciona acceso a web y app móvil

        Args:
            client: Objeto Client
            trader: Usuario Trader que creó al cliente
            temporary_password: Contraseña temporal generada

        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            logger.info(f'📧 [EMAIL-TRADER] Enviando activación con contraseña a {client.dni}')

            to = [client.email] if client.email else []
            if not to:
                return False, 'Cliente sin email'

            subject = 'Cuenta Activada - Contraseña Temporal | QoriCash'

            html_body = EmailTemplates._render_trader_activation_template(client, trader, temporary_password)

            msg = Message(
                subject=subject,
                recipients=to,
                html=html_body
            )

            mail.send(msg)
            logger.info(f'✅ [EMAIL-TRADER] Email enviado a {client.dni}')
            return True, 'Email enviado'

        except Exception as e:
            logger.error(f'❌ [EMAIL-TRADER] Error: {str(e)}')
            return False, str(e)

    @staticmethod
    def send_activation_without_password(client):
        """
        Correo de activación SIN contraseña temporal
        Para clientes auto-registrados (web o móvil)
        - NO incluye contraseña
        - Menciona acceso multiplataforma

        Args:
            client: Objeto Client

        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            logger.info(f'📧 [EMAIL-ACTIVATION] Enviando activación sin contraseña a {client.dni}')

            to = [client.email] if client.email else []
            if not to:
                return False, 'Cliente sin email'

            subject = '✅ Cuenta Activada - ¡Ya puedes operar! | QoriCash'

            html_body = EmailTemplates._render_auto_activation_template(client)

            msg = Message(
                subject=subject,
                recipients=to,
                html=html_body
            )

            mail.send(msg)
            logger.info(f'✅ [EMAIL-ACTIVATION] Email enviado a {client.dni}')
            return True, 'Email enviado'

        except Exception as e:
            logger.error(f'❌ [EMAIL-ACTIVATION] Error: {str(e)}')
            return False, str(e)

    # ============================================
    # PLANTILLAS HTML
    # ============================================

    @staticmethod
    def _render_mobile_welcome_template(client):
        """Plantilla para registro desde móvil"""
        client_name = client.full_name or client.razon_social or 'Cliente'

        template = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; background: #f4f4f4; margin: 0; padding: 20px; }
        .container { max-width: 600px; margin: 0 auto; background: #fff; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .header { background: linear-gradient(135deg, #0D1B2A 0%, #1a2942 100%); padding: 30px 20px; text-align: center; }
        .header h1 { margin: 0; color: #fff; font-size: 28px; }
        .content { padding: 30px; }
        .welcome { background: #e8f5f1; padding: 20px; border-radius: 8px; margin: 20px 0; text-align: center; }
        .welcome h2 { color: #00a887; margin: 0 0 10px 0; }
        .info-box { background: #f8f9fa; border-left: 4px solid #00a887; padding: 15px; margin: 20px 0; }
        .note { background: #fff3cd; border: 1px solid #ffc107; padding: 15px; border-radius: 5px; margin: 20px 0; }
        .access-info { background: #d1ecf1; border: 1px solid #17a2b8; padding: 20px; border-radius: 8px; margin: 25px 0; }
        .access-info h3 { color: #00a887; margin: 0 0 15px 0; }
        .footer { background: #f8f9fa; padding: 20px; text-align: center; color: #666; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>¡Bienvenido a QoriCash!</h1>
        </div>

        <div class="content">
            <p>Hola <strong>{{ client_name }}</strong>,</p>

            <div class="welcome">
                <h2>✅ Tu registro fue exitoso</h2>
                <p>Te damos la bienvenida a QoriCash, tu casa de cambio de confianza.</p>
            </div>

            <div class="info-box">
                <h3 style="color: #00a887;">Información de tu cuenta:</h3>
                <p><strong>Documento:</strong> {{ client_dni }}</p>
                <p><strong>Email:</strong> {{ client_email }}</p>
                <p><strong>Estado:</strong> Cuenta creada - Pendiente de validación KYC</p>
            </div>

            <div class="note">
                <h3 style="color: #856404; margin: 0 0 10px 0;">📋 Próximos pasos:</h3>
                <p style="margin: 5px 0;">Para poder realizar tu primera operación, necesitamos validar tu identidad. Por favor, sube tu documento de identidad desde la aplicación móvil.</p>
                <p style="margin: 5px 0;">Una vez aprobados tus documentos, recibirás una notificación y podrás comenzar a operar.</p>
            </div>

            <div class="access-info">
                <h3>🌐 Acceso Multiplataforma</h3>
                <p style="margin: 10px 0; color: #333;">Recuerda que también puedes acceder a tu cuenta desde nuestra página web <strong>www.qoricash.pe</strong> utilizando tu número de documento y la misma contraseña que registraste en el aplicativo móvil.</p>
            </div>

            <p style="margin-top: 30px;">Si tienes alguna consulta, no dudes en contactarnos a <a href="mailto:info@qoricash.pe" style="color: #00a887;">info@qoricash.pe</a></p>
        </div>

        <div class="footer">
            <p><strong>QoriCash</strong></p>
            <p>RUC: 20615113698</p>
            <p>© 2025 QoriCash. Todos los derechos reservados.</p>
        </div>
    </div>
</body>
</html>
"""
        return render_template_string(template,
                                     client_name=client_name,
                                     client_dni=client.dni,
                                     client_email=client.email)

    @staticmethod
    def _render_web_welcome_template(client):
        """Plantilla para registro desde web"""
        client_name = client.full_name or client.razon_social or 'Cliente'

        template = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; background: #f4f4f4; margin: 0; padding: 20px; }
        .container { max-width: 600px; margin: 0 auto; background: #fff; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .header { background: linear-gradient(135deg, #0D1B2A 0%, #1a2942 100%); padding: 30px 20px; text-align: center; }
        .header h1 { margin: 0; color: #fff; font-size: 28px; }
        .content { padding: 30px; }
        .welcome { background: #e8f5f1; padding: 20px; border-radius: 8px; margin: 20px 0; text-align: center; }
        .welcome h2 { color: #00a887; margin: 0 0 10px 0; }
        .info-box { background: #f8f9fa; border-left: 4px solid #00a887; padding: 15px; margin: 20px 0; }
        .note { background: #fff3cd; border: 1px solid #ffc107; padding: 15px; border-radius: 5px; margin: 20px 0; }
        .access-info { background: #d1ecf1; border: 1px solid #17a2b8; padding: 20px; border-radius: 8px; margin: 25px 0; }
        .access-info h3 { color: #00a887; margin: 0 0 15px 0; }
        .footer { background: #f8f9fa; padding: 20px; text-align: center; color: #666; font-size: 12px; }
        .app-links { text-align: center; margin: 15px 0; }
        .app-links a { display: inline-block; margin: 0 10px; padding: 10px 20px; background: #00a887; color: white; text-decoration: none; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>¡Bienvenido a QoriCash!</h1>
        </div>

        <div class="content">
            <p>Hola <strong>{{ client_name }}</strong>,</p>

            <div class="welcome">
                <h2>✅ Tu registro fue exitoso</h2>
                <p>Te damos la bienvenida a QoriCash, tu casa de cambio de confianza.</p>
            </div>

            <div class="info-box">
                <h3 style="color: #00a887;">Información de tu cuenta:</h3>
                <p><strong>Documento:</strong> {{ client_dni }}</p>
                <p><strong>Email:</strong> {{ client_email }}</p>
                <p><strong>Estado:</strong> Cuenta creada - Pendiente de validación KYC</p>
            </div>

            <div class="note">
                <h3 style="color: #856404; margin: 0 0 10px 0;">📋 Próximos pasos:</h3>
                <p style="margin: 5px 0;">Para poder realizar tu primera operación, necesitamos validar tu identidad. Al intentar crear tu primera operación, se te solicitará subir tu documento de identidad.</p>
                <p style="margin: 5px 0;">Una vez aprobados tus documentos, recibirás una notificación y podrás comenzar a operar.</p>
            </div>

            <div class="access-info">
                <h3>📱 Acceso desde App Móvil</h3>
                <p style="margin: 10px 0; color: #333;">Recuerda que también puedes acceder a tu cuenta desde nuestro aplicativo móvil. Descárgalo en Android o iOS e inicia sesión con tu número de documento y la contraseña que registraste en la web.</p>
                <div class="app-links">
                    <a href="#" style="background: #34a853;">📥 Android (Play Store)</a>
                    <a href="#" style="background: #000;">📥 iOS (App Store)</a>
                </div>
            </div>

            <p style="margin-top: 30px;">Si tienes alguna consulta, no dudes en contactarnos a <a href="mailto:info@qoricash.pe" style="color: #00a887;">info@qoricash.pe</a></p>
        </div>

        <div class="footer">
            <p><strong>QoriCash</strong></p>
            <p>RUC: 20615113698</p>
            <p>© 2025 QoriCash. Todos los derechos reservados.</p>
        </div>
    </div>
</body>
</html>
"""
        return render_template_string(template,
                                     client_name=client_name,
                                     client_dni=client.dni,
                                     client_email=client.email)

    @staticmethod
    def _render_trader_activation_template(client, trader, temporary_password):
        """Plantilla para activación con contraseña temporal (cliente creado por Trader)"""
        client_name = client.full_name or client.razon_social or 'Cliente'
        trader_name = trader.username if trader else 'QoriCash'

        template = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; background: #f4f4f4; margin: 0; padding: 20px; }
        .container { max-width: 600px; margin: 0 auto; background: #fff; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .header { background: linear-gradient(135deg, #0D1B2A 0%, #1a2942 100%); padding: 30px 20px; text-align: center; }
        .header h1 { margin: 0; color: #fff; font-size: 28px; }
        .content { padding: 30px; }
        .success-box { background: #d4edda; border: 2px solid #28a745; padding: 20px; border-radius: 8px; margin: 20px 0; text-align: center; }
        .success-box h2 { color: #155724; margin: 0 0 10px 0; }
        .password-box { background: #fff3cd; border: 2px solid #ffc107; padding: 20px; border-radius: 8px; margin: 20px 0; text-align: center; }
        .password-box h3 { color: #856404; margin: 0 0 15px 0; }
        .password { font-size: 24px; font-weight: bold; color: #d63384; background: white; padding: 15px; border-radius: 5px; letter-spacing: 2px; }
        .warning { background: #f8d7da; border: 1px solid #f5c6cb; padding: 15px; border-radius: 5px; margin: 20px 0; }
        .access-info { background: #d1ecf1; border: 1px solid #17a2b8; padding: 20px; border-radius: 8px; margin: 25px 0; }
        .access-info h3 { color: #00a887; margin: 0 0 15px 0; }
        .steps { background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; }
        .steps li { margin: 10px 0; }
        .footer { background: #f8f9fa; padding: 20px; text-align: center; color: #666; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Cuenta Activada - QoriCash</h1>
        </div>

        <div class="content">
            <p>Hola <strong>{{ client_name }}</strong>,</p>

            <div class="success-box">
                <h2>✅ ¡Tu cuenta ha sido activada!</h2>
                <p>Tu asesor <strong>{{ trader_name }}</strong> ha creado tu cuenta en QoriCash.</p>
            </div>

            <div class="password-box">
                <h3>🔐 Contraseña Temporal</h3>
                <div class="password">{{ temporary_password }}</div>
                <p style="margin-top: 15px; font-size: 14px; color: #856404;">Esta es una contraseña temporal que deberás cambiar en tu primer inicio de sesión.</p>
            </div>

            <div class="warning">
                <p style="margin: 0; color: #721c24;"><strong>⚠️ Importante:</strong> Por seguridad, deberás cambiar esta contraseña temporal la primera vez que inicies sesión.</p>
            </div>

            <div class="steps">
                <h3 style="color: #00a887;">📋 Próximos pasos:</h3>
                <ol>
                    <li>Inicia sesión con tu número de documento y la contraseña temporal proporcionada</li>
                    <li>El sistema te solicitará crear una nueva contraseña segura</li>
                    <li>¡Comienza a realizar tus operaciones cambiarias!</li>
                </ol>
            </div>

            <div class="access-info">
                <h3>🌐 Acceso Multiplataforma</h3>
                <p style="margin: 10px 0; color: #333;">Con esta contraseña temporal puedes acceder a tu cuenta desde:</p>
                <ul style="margin: 10px 0; padding-left: 20px;">
                    <li><strong>Página web:</strong> www.qoricash.pe</li>
                    <li><strong>Aplicativo móvil:</strong> Disponible en Android e iOS</li>
                </ul>
                <p style="margin: 10px 0; color: #333;">Utiliza tu número de documento y la contraseña temporal asignada. Por seguridad, deberás cambiarla en tu primer inicio de sesión.</p>
            </div>

            <p style="margin-top: 30px;">Si tienes alguna consulta, puedes contactar a tu asesor <strong>{{ trader_name }}</strong> o escribirnos a <a href="mailto:info@qoricash.pe" style="color: #00a887;">info@qoricash.pe</a></p>
        </div>

        <div class="footer">
            <p><strong>QoriCash</strong></p>
            <p>RUC: 20615113698</p>
            <p>© 2025 QoriCash. Todos los derechos reservados.</p>
        </div>
    </div>
</body>
</html>
"""
        return render_template_string(template,
                                     client_name=client_name,
                                     client_dni=client.dni,
                                     trader_name=trader_name,
                                     temporary_password=temporary_password)

    @staticmethod
    def _render_auto_activation_template(client):
        """Plantilla para activación sin contraseña (cliente auto-registrado)"""
        client_name = client.full_name or client.razon_social or 'Cliente'

        template = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; background: #f4f4f4; margin: 0; padding: 20px; }
        .container { max-width: 600px; margin: 0 auto; background: #fff; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .header { background: linear-gradient(135deg, #0D1B2A 0%, #1a2942 100%); padding: 30px 20px; text-align: center; }
        .header h1 { margin: 0; color: #fff; font-size: 28px; }
        .content { padding: 30px; }
        .success-box { background: #d4edda; border: 2px solid #28a745; padding: 25px; border-radius: 8px; margin: 20px 0; text-align: center; }
        .success-box h2 { color: #155724; margin: 0 0 10px 0; font-size: 24px; }
        .success-box p { color: #155724; font-size: 16px; }
        .info-box { background: #f8f9fa; border-left: 4px solid #00a887; padding: 20px; margin: 20px 0; }
        .access-info { background: #d1ecf1; border: 1px solid #17a2b8; padding: 20px; border-radius: 8px; margin: 25px 0; }
        .access-info h3 { color: #00a887; margin: 0 0 15px 0; }
        .cta-button { background: #00a887; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 20px 0; font-weight: bold; }
        .footer { background: #f8f9fa; padding: 20px; text-align: center; color: #666; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>¡Cuenta Activada!</h1>
        </div>

        <div class="content">
            <p>Hola <strong>{{ client_name }}</strong>,</p>

            <div class="success-box">
                <h2>✅ Tu cuenta ha sido activada exitosamente</h2>
                <p>Tus documentos han sido verificados y aprobados.</p>
                <p><strong>¡Ya puedes comenzar a realizar operaciones cambiarias!</strong></p>
            </div>

            <div class="info-box">
                <h3 style="color: #00a887;">¿Qué significa esto?</h3>
                <p style="margin: 10px 0;">✓ Tu identidad ha sido verificada</p>
                <p style="margin: 10px 0;">✓ Puedes crear operaciones de compra y venta</p>
                <p style="margin: 10px 0;">✓ Acceso completo a todas las funcionalidades</p>
            </div>

            <div style="text-align: center;">
                <a href="https://www.qoricash.pe" class="cta-button">Iniciar Sesión Ahora</a>
            </div>

            <div class="access-info">
                <h3>🌐 Accede desde cualquier plataforma</h3>
                <p style="margin: 10px 0; color: #333;">Recuerda que puedes acceder a tu cuenta desde:</p>
                <ul style="margin: 10px 0; padding-left: 20px; color: #333;">
                    <li><strong>Página web:</strong> www.qoricash.pe</li>
                    <li><strong>Aplicativo móvil:</strong> Android e iOS</li>
                </ul>
                <p style="margin: 15px 0; color: #333; font-weight: 500;">Utiliza tu número de documento y la contraseña que definiste al registrarte.</p>
            </div>

            <p style="margin-top: 30px;">Si tienes alguna consulta, no dudes en contactarnos a <a href="mailto:info@qoricash.pe" style="color: #00a887;">info@qoricash.pe</a></p>
        </div>

        <div class="footer">
            <p><strong>QoriCash</strong></p>
            <p>RUC: 20615113698</p>
            <p>© 2025 QoriCash. Todos los derechos reservados.</p>
        </div>
    </div>
</body>
</html>
"""
        return render_template_string(template,
                                     client_name=client_name,
                                     client_dni=client.dni)
