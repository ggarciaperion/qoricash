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

# ============================================
# CSS BASE COMPARTIDO POR TODAS LAS PLANTILLAS
# ============================================
_EMAIL_CSS = """
    body, table, td, p, h1, h2, h3, h4 { margin: 0; padding: 0; }
    img { border: 0; display: block; }
    body { background-color: #f0f4f8; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; -webkit-text-size-adjust: 100%; }
    .email-wrapper { padding: 28px 16px; }
    .email-card { max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 24px rgba(13,27,42,0.09); }
    .email-header { background-color: #0D1B2A; padding: 30px 40px 26px; text-align: center; }
    .logo-wrap { display: inline-block; border: 1.5px solid rgba(0,222,168,0.35); border-radius: 8px; padding: 7px 22px; margin-bottom: 10px; }
    .logo-text { color: #00DEA8; font-size: 21px; font-weight: 700; letter-spacing: 1.5px; }
    .tagline { color: rgba(255,255,255,0.40); font-size: 11px; letter-spacing: 0.6px; margin-top: 6px; }
    .accent-bar { height: 3px; background-color: #00DEA8; }
    .email-body { padding: 36px 40px; color: #334155; font-size: 15px; line-height: 1.65; }
    .status-box { border-radius: 10px; padding: 22px 24px; text-align: center; margin: 22px 0; }
    .status-box.success { background-color: #f0fdf4; border: 1.5px solid #86efac; }
    .status-box.info { background-color: #eff6ff; border: 1.5px solid #93c5fd; }
    .status-box.warning { background-color: #fffbeb; border: 1.5px solid #fcd34d; }
    .status-box h2 { font-size: 17px; font-weight: 700; margin-bottom: 6px; }
    .status-box.success h2 { color: #15803d; }
    .status-box.info h2 { color: #1d4ed8; }
    .status-box.warning h2 { color: #92400e; }
    .status-box p { font-size: 14px; margin-top: 4px; }
    .status-box.success p { color: #166534; }
    .status-box.info p { color: #1e40af; }
    .status-box.warning p { color: #78350f; }
    .section-label { font-size: 11px; font-weight: 700; color: #00DEA8; text-transform: uppercase; letter-spacing: 1.2px; margin: 24px 0 10px 0; }
    .data-box { background: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0; overflow: hidden; margin: 0 0 20px 0; }
    .data-row { padding: 10px 18px; border-bottom: 1px solid #f1f5f9; font-size: 14px; }
    .data-row:last-child { border-bottom: none; }
    .data-label { color: #64748b; font-weight: 600; display: inline-block; min-width: 150px; }
    .data-value { color: #1e293b; font-weight: 500; }
    .alert { border-radius: 8px; padding: 13px 16px; margin: 14px 0; font-size: 13.5px; line-height: 1.65; }
    .alert.warning { background: #fffbeb; border-left: 3px solid #f59e0b; color: #78350f; }
    .alert.danger { background: #fef2f2; border-left: 3px solid #ef4444; color: #7f1d1d; }
    .alert.info { background: #f0f9ff; border-left: 3px solid #0ea5e9; color: #0c4a6e; }
    .alert.success { background: #f0fdf4; border-left: 3px solid #22c55e; color: #14532d; }
    .password-box { background-color: #0D1B2A; border-radius: 10px; padding: 22px 24px; text-align: center; margin: 16px 0; }
    .password-label { color: rgba(255,255,255,0.50); font-size: 11px; letter-spacing: 0.8px; text-transform: uppercase; margin-bottom: 10px; }
    .password-code { color: #00DEA8; font-size: 28px; font-family: 'Courier New', Courier, monospace; font-weight: 700; letter-spacing: 4px; }
    .password-hint { color: rgba(255,255,255,0.35); font-size: 11px; margin-top: 10px; }
    .steps-box { background: #f8fafc; border-radius: 8px; padding: 14px 18px 14px 14px; margin: 14px 0; }
    .steps-box ol { margin: 0; padding-left: 22px; }
    .steps-box li { padding: 5px 0; font-size: 14px; color: #334155; }
    .cta-wrap { text-align: center; margin: 28px 0 20px 0; }
    .cta-btn { display: inline-block; background-color: #00DEA8; color: #0D1B2A; font-weight: 700; font-size: 15px; padding: 13px 36px; border-radius: 8px; text-decoration: none; letter-spacing: 0.3px; }
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
        .email-footer { padding: 20px !important; }
        .data-label { display: block !important; min-width: unset !important; margin-bottom: 2px; }
    }
"""


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

        template = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>""" + _EMAIL_CSS + """</style>
</head>
<body>
<div class="email-wrapper">
    <div class="email-card">

        <div class="email-header" style="padding:0;background:#0D1B2A;">
            <img src="https://res.cloudinary.com/dbks8vqoh/image/upload/v1773788552/qoricash/banneremail.png" alt="QoriCash" width="600" style="width:100%;max-width:600px;display:block;">
        </div>
        <div class="accent-bar"></div>

        <div class="email-body">
            <p>Hola <strong>{{ client_name }}</strong>,</p>

            <div class="status-box success">
                <h2>Registro exitoso</h2>
                <p>Te damos la bienvenida a QoriCash.</p>
            </div>

            <p class="section-label">Información de tu cuenta</p>
            <div class="data-box">
                <div class="data-row">
                    <span class="data-label">Documento</span>
                    <span class="data-value">{{ client_dni }}</span>
                </div>
                <div class="data-row">
                    <span class="data-label">Correo electrónico</span>
                    <span class="data-value">{{ client_email }}</span>
                </div>
                <div class="data-row">
                    <span class="data-label">Estado</span>
                    <span class="data-value" style="color:#d97706;font-weight:700;">Pendiente de validación KYC</span>
                </div>
            </div>

            <div class="alert warning">
                <strong>Próximos pasos:</strong> Para realizar tu primera operación debemos validar tu identidad. Por favor sube tu documento desde la aplicación móvil. Recibirás una notificación cuando sea aprobado.
            </div>

            <div class="alert info">
                <strong>Acceso web:</strong> También puedes ingresar desde <strong>www.qoricash.pe</strong> usando tu número de documento y la contraseña que registraste en la app.
            </div>

            <div class="divider"></div>
            <p class="note-text">¿Tienes alguna consulta? Escríbenos a <a href="mailto:info@qoricash.pe" class="footer-link">info@qoricash.pe</a></p>
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
        return render_template_string(template,
                                     client_name=client_name,
                                     client_dni=client.dni,
                                     client_email=client.email)

    @staticmethod
    def _render_web_welcome_template(client):
        """Plantilla para registro desde web"""
        client_name = client.full_name or client.razon_social or 'Cliente'

        template = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>""" + _EMAIL_CSS + """
        .app-btn { display: inline-block; padding: 9px 20px; border-radius: 6px; text-decoration: none; font-size: 13px; font-weight: 600; margin: 4px 6px; }
        .app-btn.android { background-color: #14532d; color: #ffffff; }
        .app-btn.ios { background-color: #1e293b; color: #ffffff; }
    </style>
</head>
<body>
<div class="email-wrapper">
    <div class="email-card">

        <div class="email-header" style="padding:0;background:#0D1B2A;">
            <img src="https://res.cloudinary.com/dbks8vqoh/image/upload/v1773788552/qoricash/banneremail.png" alt="QoriCash" width="600" style="width:100%;max-width:600px;display:block;">
        </div>
        <div class="accent-bar"></div>

        <div class="email-body">
            <p>Hola <strong>{{ client_name }}</strong>,</p>

            <div class="status-box success">
                <h2>Registro exitoso</h2>
                <p>Te damos la bienvenida a QoriCash.</p>
            </div>

            <p class="section-label">Información de tu cuenta</p>
            <div class="data-box">
                <div class="data-row">
                    <span class="data-label">Documento</span>
                    <span class="data-value">{{ client_dni }}</span>
                </div>
                <div class="data-row">
                    <span class="data-label">Correo electrónico</span>
                    <span class="data-value">{{ client_email }}</span>
                </div>
                <div class="data-row">
                    <span class="data-label">Estado</span>
                    <span class="data-value" style="color:#d97706;font-weight:700;">Pendiente de validación KYC</span>
                </div>
            </div>

            <div class="alert warning">
                <strong>Próximos pasos:</strong> Para realizar tu primera operación debemos validar tu identidad. Al intentar crear tu primera operación, se te solicitará subir tu documento. Recibirás una notificación cuando sea aprobado.
            </div>

            <div class="alert info">
                📱 <strong>Próximamente</strong> publicaremos nuestra app para <strong>iOS</strong> y <strong>Android</strong>. Te notificaremos cuando esté disponible para descargar.
            </div>

            <div class="divider"></div>
            <p class="note-text">¿Tienes alguna consulta? Escríbenos a <a href="mailto:info@qoricash.pe" class="footer-link">info@qoricash.pe</a></p>
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
        return render_template_string(template,
                                     client_name=client_name,
                                     client_dni=client.dni,
                                     client_email=client.email)

    @staticmethod
    def _render_trader_activation_template(client, trader, temporary_password):
        """Plantilla para activación con contraseña temporal (cliente creado por Trader)"""
        client_name = client.full_name or client.razon_social or 'Cliente'
        trader_name = trader.username if trader else 'QoriCash'

        template = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>""" + _EMAIL_CSS + """</style>
</head>
<body>
<div class="email-wrapper">
    <div class="email-card">

        <div class="email-header" style="padding:0;background:#0D1B2A;">
            <img src="https://res.cloudinary.com/dbks8vqoh/image/upload/v1773788552/qoricash/banneremail.png" alt="QoriCash" width="600" style="width:100%;max-width:600px;display:block;">
        </div>
        <div class="accent-bar"></div>

        <div class="email-body">
            <p>Hola <strong>{{ client_name }}</strong>,</p>

            <div class="status-box success">
                <h2>¡Tu cuenta ha sido activada!</h2>
                <p>Tu asesor <strong>{{ trader_name }}</strong> ha creado tu cuenta en QoriCash.</p>
            </div>

            <p class="section-label">Contraseña temporal</p>
            <div class="password-box">
                <p class="password-label">Tu contraseña de acceso es</p>
                <p class="password-code">{{ temporary_password }}</p>
                <p class="password-hint">Cópiala exactamente como aparece</p>
            </div>

            <div class="alert danger">
                <strong>Importante:</strong> Por seguridad, deberás cambiar esta contraseña temporal la primera vez que inicies sesión.
            </div>

            <p class="section-label">Próximos pasos</p>
            <div class="steps-box">
                <ol>
                    <li>Inicia sesión con tu número de documento y la contraseña temporal</li>
                    <li>El sistema te pedirá crear una nueva contraseña segura</li>
                    <li>¡Comienza a realizar tus operaciones cambiarias!</li>
                </ol>
            </div>

            <div class="alert info">
                <strong>Acceso multiplataforma:</strong> Puedes ingresar desde <strong>www.qoricash.pe</strong> o desde nuestra app móvil disponible en Android e iOS.
            </div>

            <div class="divider"></div>
            <p class="note-text">¿Tienes alguna consulta? Contacta a tu asesor <strong>{{ trader_name }}</strong> o escríbenos a <a href="mailto:info@qoricash.pe" class="footer-link">info@qoricash.pe</a></p>
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
        return render_template_string(template,
                                     client_name=client_name,
                                     client_dni=client.dni,
                                     trader_name=trader_name,
                                     temporary_password=temporary_password)

    @staticmethod
    def _render_auto_activation_template(client):
        """Plantilla para activación sin contraseña (cliente auto-registrado)"""
        client_name = client.full_name or client.razon_social or 'Cliente'

        template = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>""" + _EMAIL_CSS + """</style>
</head>
<body>
<div class="email-wrapper">
    <div class="email-card">

        <div class="email-header" style="padding:0;background:#0D1B2A;">
            <img src="https://res.cloudinary.com/dbks8vqoh/image/upload/v1773788552/qoricash/banneremail.png" alt="QoriCash" width="600" style="width:100%;max-width:600px;display:block;">
        </div>
        <div class="accent-bar"></div>

        <div class="email-body">
            <p>Hola <strong>{{ client_name }}</strong>,</p>

            <div class="status-box success">
                <h2>¡Cuenta activada exitosamente!</h2>
                <p>Tus documentos han sido verificados y aprobados.<br>Ya puedes comenzar a operar.</p>
            </div>

            <p class="section-label">¿Qué significa esto?</p>
            <div class="data-box">
                <div class="data-row">
                    <span class="data-value" style="color:#059669;">✓ &nbsp;Tu identidad ha sido verificada</span>
                </div>
                <div class="data-row">
                    <span class="data-value" style="color:#059669;">✓ &nbsp;Puedes crear operaciones de compra y venta</span>
                </div>
                <div class="data-row">
                    <span class="data-value" style="color:#059669;">✓ &nbsp;Acceso completo a todas las funcionalidades</span>
                </div>
            </div>

            <div class="cta-wrap">
                <a href="https://www.qoricash.pe" class="cta-btn">Iniciar sesión ahora</a>
            </div>

            <div class="alert info">
                <strong>Acceso multiplataforma:</strong> Ingresa desde <strong>www.qoricash.pe</strong> o nuestra app móvil usando tu número de documento y la contraseña que definiste al registrarte.
            </div>

            <div class="divider"></div>
            <p class="note-text">¿Tienes alguna consulta? Escríbenos a <a href="mailto:info@qoricash.pe" class="footer-link">info@qoricash.pe</a></p>
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
        return render_template_string(template,
                                     client_name=client_name,
                                     client_dni=client.dni)
