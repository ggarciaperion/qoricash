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
# CSS BASE: solo @media queries (estilos inline en las plantillas)
# ============================================
_EMAIL_CSS = """
    @media only screen and (max-width: 620px) {
        .email-body-cell { padding: 24px 20px !important; }
        .email-footer-cell { padding: 20px !important; }
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
<body style="margin:0;padding:0;background-color:#f5f7fa;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f5f7fa;padding:28px 16px;">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 16px rgba(13,27,42,0.08);">

      <!-- BANNER -->
      <tr>
        <td style="padding:0;background:#0D1B2A;line-height:0;font-size:0;">
          <img src="https://res.cloudinary.com/dbks8vqoh/image/upload/v1773788552/qoricash/banneremail.png" alt="QoriCash" width="600" style="width:100%;max-width:600px;display:block;border:0;">
        </td>
      </tr>

      <!-- ACCENT LINE: indigo -->
      <tr><td style="padding:0;height:3px;background-color:#6366f1;font-size:0;line-height:0;">&nbsp;</td></tr>

      <!-- BODY -->
      <tr>
        <td class="email-body-cell" style="padding:36px 40px;color:#334155;font-size:15px;line-height:1.65;">

          <!-- Event label -->
          <div style="margin:0 0 16px 0;">
            <span style="display:inline-block;background:#eef2ff;color:#6366f1;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.4px;padding:4px 10px;border-radius:4px;">Bienvenido a QoriCash</span>
          </div>

          <!-- Title -->
          <h1 style="margin:0 0 6px 0;font-size:22px;font-weight:700;color:#0D1B2A;line-height:1.3;">Tu cuenta ha sido creada</h1>
          <p style="margin:0 0 24px 0;color:#64748b;font-size:14px;">Hola <strong style="color:#1e293b;">{{ client_name }}</strong>, te damos la bienvenida a QoriCash.</p>

          <!-- Data table -->
          <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;border:1px solid #e8ecf0;border-radius:8px;overflow:hidden;margin:0 0 24px 0;">
            <tr style="border-bottom:1px solid #eef0f3;">
              <td style="padding:11px 18px;width:160px;color:#94a3b8;font-size:13px;font-weight:600;white-space:nowrap;vertical-align:top;">Documento</td>
              <td style="padding:11px 18px;color:#1e293b;font-size:14px;font-weight:500;vertical-align:top;">{{ client_dni }}</td>
            </tr>
            <tr style="border-bottom:1px solid #eef0f3;">
              <td style="padding:11px 18px;width:160px;color:#94a3b8;font-size:13px;font-weight:600;white-space:nowrap;vertical-align:top;">Correo electrónico</td>
              <td style="padding:11px 18px;color:#1e293b;font-size:14px;font-weight:500;vertical-align:top;">{{ client_email }}</td>
            </tr>
            <tr>
              <td style="padding:11px 18px;width:160px;color:#94a3b8;font-size:13px;font-weight:600;white-space:nowrap;vertical-align:top;">Estado</td>
              <td style="padding:11px 18px;color:#d97706;font-size:14px;font-weight:600;vertical-align:top;">Pendiente de verificación</td>
            </tr>
          </table>

          <!-- Next steps -->
          <p style="margin:0 0 10px 0;font-size:11px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1.2px;">Próximos pasos</p>
          <div style="border-radius:8px;padding:13px 16px;margin:0 0 16px 0;font-size:13px;line-height:1.65;background:#fffbeb;border-left:3px solid #f59e0b;color:#78350f;">
            Para realizar tu primera operación debemos validar tu identidad. Por favor sube tu documento de identidad desde la aplicación móvil. Recibirás una notificación cuando sea aprobado.
          </div>
          <div style="border-radius:8px;padding:13px 16px;margin:0 0 20px 0;font-size:13px;line-height:1.65;background:#f0f9ff;border-left:3px solid #0ea5e9;color:#0c4a6e;">
            <strong>Acceso web:</strong> También puedes ingresar desde <strong>www.qoricash.pe</strong> usando tu número de documento y la contraseña que registraste en la app.
          </div>

          <!-- Closing -->
          <div style="height:1px;background-color:#f1f5f9;margin:24px 0;"></div>
          <p style="margin:0;font-size:13px;color:#94a3b8;">¿Tienes alguna consulta? Escríbenos a <a href="mailto:info@qoricash.pe" style="color:#94a3b8;">info@qoricash.pe</a></p>

        </td>
      </tr>

      <!-- FOOTER -->
      <tr>
        <td class="email-footer-cell" style="background-color:#f8fafc;border-top:1px solid #e8ecf0;padding:20px 40px;text-align:center;">
          <p style="margin:0 0 4px 0;color:#0D1B2A;font-size:13px;font-weight:700;">QoriCash</p>
          <p style="margin:0 0 4px 0;color:#94a3b8;font-size:12px;">RUC: 20615113698 &nbsp;&middot;&nbsp; <a href="mailto:info@qoricash.pe" style="color:#94a3b8;text-decoration:none;">info@qoricash.pe</a></p>
          <p style="margin:0;color:#cbd5e1;font-size:11px;">© 2025 QoriCash. Todos los derechos reservados.</p>
        </td>
      </tr>

    </table>
  </td></tr>
</table>
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
    <style>""" + _EMAIL_CSS + """</style>
</head>
<body style="margin:0;padding:0;background-color:#f5f7fa;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f5f7fa;padding:28px 16px;">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 16px rgba(13,27,42,0.08);">

      <!-- BANNER -->
      <tr>
        <td style="padding:0;background:#0D1B2A;line-height:0;font-size:0;">
          <img src="https://res.cloudinary.com/dbks8vqoh/image/upload/v1773788552/qoricash/banneremail.png" alt="QoriCash" width="600" style="width:100%;max-width:600px;display:block;border:0;">
        </td>
      </tr>

      <!-- ACCENT LINE: indigo -->
      <tr><td style="padding:0;height:3px;background-color:#6366f1;font-size:0;line-height:0;">&nbsp;</td></tr>

      <!-- BODY -->
      <tr>
        <td class="email-body-cell" style="padding:36px 40px;color:#334155;font-size:15px;line-height:1.65;">

          <!-- Event label -->
          <div style="margin:0 0 16px 0;">
            <span style="display:inline-block;background:#eef2ff;color:#6366f1;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.4px;padding:4px 10px;border-radius:4px;">Bienvenido a QoriCash</span>
          </div>

          <!-- Title -->
          <h1 style="margin:0 0 6px 0;font-size:22px;font-weight:700;color:#0D1B2A;line-height:1.3;">Tu cuenta ha sido creada</h1>
          <p style="margin:0 0 24px 0;color:#64748b;font-size:14px;">Hola <strong style="color:#1e293b;">{{ client_name }}</strong>, te damos la bienvenida a la plataforma web de QoriCash.</p>

          <!-- Data table -->
          <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;border:1px solid #e8ecf0;border-radius:8px;overflow:hidden;margin:0 0 24px 0;">
            <tr style="border-bottom:1px solid #eef0f3;">
              <td style="padding:11px 18px;width:160px;color:#94a3b8;font-size:13px;font-weight:600;white-space:nowrap;vertical-align:top;">Documento</td>
              <td style="padding:11px 18px;color:#1e293b;font-size:14px;font-weight:500;vertical-align:top;">{{ client_dni }}</td>
            </tr>
            <tr style="border-bottom:1px solid #eef0f3;">
              <td style="padding:11px 18px;width:160px;color:#94a3b8;font-size:13px;font-weight:600;white-space:nowrap;vertical-align:top;">Correo electrónico</td>
              <td style="padding:11px 18px;color:#1e293b;font-size:14px;font-weight:500;vertical-align:top;">{{ client_email }}</td>
            </tr>
            <tr>
              <td style="padding:11px 18px;width:160px;color:#94a3b8;font-size:13px;font-weight:600;white-space:nowrap;vertical-align:top;">Estado</td>
              <td style="padding:11px 18px;color:#d97706;font-size:14px;font-weight:600;vertical-align:top;">Pendiente de verificación</td>
            </tr>
          </table>

          <!-- Next steps -->
          <p style="margin:0 0 10px 0;font-size:11px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1.2px;">Próximos pasos</p>
          <div style="border-radius:8px;padding:13px 16px;margin:0 0 16px 0;font-size:13px;line-height:1.65;background:#fffbeb;border-left:3px solid #f59e0b;color:#78350f;">
            Para realizar tu primera operación desde la plataforma web debemos validar tu identidad. Al crear tu primera operación, se te solicitará subir tu documento de identidad. Recibirás una notificación cuando sea aprobado.
          </div>
          <div style="border-radius:8px;padding:13px 16px;margin:0 0 20px 0;font-size:13px;line-height:1.65;background:#f0f9ff;border-left:3px solid #0ea5e9;color:#0c4a6e;">
            Próximamente publicaremos nuestra app para <strong>iOS</strong> y <strong>Android</strong>. Te notificaremos cuando esté disponible para descargar.
          </div>

          <!-- Closing -->
          <div style="height:1px;background-color:#f1f5f9;margin:24px 0;"></div>
          <p style="margin:0;font-size:13px;color:#94a3b8;">¿Tienes alguna consulta? Escríbenos a <a href="mailto:info@qoricash.pe" style="color:#94a3b8;">info@qoricash.pe</a></p>

        </td>
      </tr>

      <!-- FOOTER -->
      <tr>
        <td class="email-footer-cell" style="background-color:#f8fafc;border-top:1px solid #e8ecf0;padding:20px 40px;text-align:center;">
          <p style="margin:0 0 4px 0;color:#0D1B2A;font-size:13px;font-weight:700;">QoriCash</p>
          <p style="margin:0 0 4px 0;color:#94a3b8;font-size:12px;">RUC: 20615113698 &nbsp;&middot;&nbsp; <a href="mailto:info@qoricash.pe" style="color:#94a3b8;text-decoration:none;">info@qoricash.pe</a></p>
          <p style="margin:0;color:#cbd5e1;font-size:11px;">© 2025 QoriCash. Todos los derechos reservados.</p>
        </td>
      </tr>

    </table>
  </td></tr>
</table>
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
<body style="margin:0;padding:0;background-color:#f5f7fa;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f5f7fa;padding:28px 16px;">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 16px rgba(13,27,42,0.08);">

      <!-- BANNER -->
      <tr>
        <td style="padding:0;background:#0D1B2A;line-height:0;font-size:0;">
          <img src="https://res.cloudinary.com/dbks8vqoh/image/upload/v1773788552/qoricash/banneremail.png" alt="QoriCash" width="600" style="width:100%;max-width:600px;display:block;border:0;">
        </td>
      </tr>

      <!-- ACCENT LINE: green -->
      <tr><td style="padding:0;height:3px;background-color:#10b981;font-size:0;line-height:0;">&nbsp;</td></tr>

      <!-- BODY -->
      <tr>
        <td class="email-body-cell" style="padding:36px 40px;color:#334155;font-size:15px;line-height:1.65;">

          <!-- Event label -->
          <div style="margin:0 0 16px 0;">
            <span style="display:inline-block;background:#f0fdf4;color:#10b981;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.4px;padding:4px 10px;border-radius:4px;">Cuenta Activada</span>
          </div>

          <!-- Title -->
          <h1 style="margin:0 0 6px 0;font-size:22px;font-weight:700;color:#0D1B2A;line-height:1.3;">Tu identidad ha sido verificada — cuenta activa</h1>
          <p style="margin:0 0 24px 0;color:#64748b;font-size:14px;">Hola <strong style="color:#1e293b;">{{ client_name }}</strong>, tu identidad ha sido verificada y aprobada. Tu asesor <strong style="color:#0D1B2A;">{{ trader_name }}</strong> habilitó tu cuenta para que puedas comenzar a operar.</p>

          <!-- Password box -->
          <p style="margin:0 0 10px 0;font-size:11px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1.2px;">Tu contraseña temporal</p>
          <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;margin:0 0 20px 0;">
            <tr>
              <td style="background-color:#0D1B2A;border-radius:10px;padding:22px 24px;text-align:center;">
                <p style="margin:0 0 10px 0;color:rgba(255,255,255,0.50);font-size:11px;letter-spacing:0.8px;text-transform:uppercase;">Tu contraseña de acceso es</p>
                <p style="margin:0 0 10px 0;color:#00DEA8;font-size:28px;font-family:'Courier New',Courier,monospace;font-weight:700;letter-spacing:4px;">{{ temporary_password }}</p>
                <p style="margin:0;color:rgba(255,255,255,0.35);font-size:11px;">Cópiala exactamente como aparece</p>
              </td>
            </tr>
          </table>

          <!-- Security alert -->
          <div style="border-radius:8px;padding:13px 16px;margin:0 0 20px 0;font-size:13px;line-height:1.65;background:#fef2f2;border-left:3px solid #ef4444;color:#7f1d1d;">
            <strong>Importante:</strong> Por seguridad, deberás cambiar esta contraseña temporal la primera vez que inicies sesión.
          </div>

          <!-- Steps -->
          <p style="margin:0 0 10px 0;font-size:11px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1.2px;">Próximos pasos</p>
          <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;border:1px solid #e8ecf0;border-radius:8px;overflow:hidden;margin:0 0 20px 0;">
            <tr style="border-bottom:1px solid #eef0f3;">
              <td style="padding:11px 18px;color:#334155;font-size:13px;vertical-align:top;">
                <span style="color:#6366f1;font-weight:700;margin-right:8px;">1.</span>Inicia sesión con tu número de documento y la contraseña temporal
              </td>
            </tr>
            <tr style="border-bottom:1px solid #eef0f3;">
              <td style="padding:11px 18px;color:#334155;font-size:13px;vertical-align:top;">
                <span style="color:#6366f1;font-weight:700;margin-right:8px;">2.</span>El sistema te pedirá crear una nueva contraseña segura
              </td>
            </tr>
            <tr>
              <td style="padding:11px 18px;color:#334155;font-size:13px;vertical-align:top;">
                <span style="color:#6366f1;font-weight:700;margin-right:8px;">3.</span>¡Comienza a realizar tus operaciones cambiarias!
              </td>
            </tr>
          </table>

          <!-- CTA button -->
          <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;margin:0 0 20px 0;">
            <tr>
              <td align="center">
                <a href="https://www.qoricash.pe"
                   style="display:inline-block;background-color:#00DEA8;color:#0D1B2A;font-weight:700;font-size:15px;padding:13px 36px;border-radius:8px;text-decoration:none;letter-spacing:0.3px;">
                  Ingresar a QoriCash
                </a>
              </td>
            </tr>
          </table>

          <!-- Access info -->
          <div style="border-radius:8px;padding:13px 16px;margin:0 0 20px 0;font-size:13px;line-height:1.65;background:#f0f9ff;border-left:3px solid #0ea5e9;color:#0c4a6e;">
            Ingresa desde <strong>www.qoricash.pe</strong> o nuestra app móvil usando tu número de documento y la contraseña temporal indicada arriba.
          </div>

          <!-- Closing -->
          <div style="height:1px;background-color:#f1f5f9;margin:24px 0;"></div>
          <p style="margin:0;font-size:13px;color:#94a3b8;">¿Tienes alguna consulta? Contacta a tu asesor <strong style="color:#1e293b;">{{ trader_name }}</strong> o escríbenos a <a href="mailto:info@qoricash.pe" style="color:#94a3b8;">info@qoricash.pe</a></p>

        </td>
      </tr>

      <!-- FOOTER -->
      <tr>
        <td class="email-footer-cell" style="background-color:#f8fafc;border-top:1px solid #e8ecf0;padding:20px 40px;text-align:center;">
          <p style="margin:0 0 4px 0;color:#0D1B2A;font-size:13px;font-weight:700;">QoriCash</p>
          <p style="margin:0 0 4px 0;color:#94a3b8;font-size:12px;">RUC: 20615113698 &nbsp;&middot;&nbsp; <a href="mailto:info@qoricash.pe" style="color:#94a3b8;text-decoration:none;">info@qoricash.pe</a></p>
          <p style="margin:0;color:#cbd5e1;font-size:11px;">© 2026 QoriCash. Todos los derechos reservados.</p>
        </td>
      </tr>

    </table>
  </td></tr>
</table>
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
<body style="margin:0;padding:0;background-color:#f5f7fa;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f5f7fa;padding:28px 16px;">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 16px rgba(13,27,42,0.08);">

      <!-- BANNER -->
      <tr>
        <td style="padding:0;background:#0D1B2A;line-height:0;font-size:0;">
          <img src="https://res.cloudinary.com/dbks8vqoh/image/upload/v1773788552/qoricash/banneremail.png" alt="QoriCash" width="600" style="width:100%;max-width:600px;display:block;border:0;">
        </td>
      </tr>

      <!-- ACCENT LINE: green -->
      <tr><td style="padding:0;height:3px;background-color:#10b981;font-size:0;line-height:0;">&nbsp;</td></tr>

      <!-- BODY -->
      <tr>
        <td class="email-body-cell" style="padding:36px 40px;color:#334155;font-size:15px;line-height:1.65;">

          <!-- Event label -->
          <div style="margin:0 0 16px 0;">
            <span style="display:inline-block;background:#f0fdf4;color:#10b981;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.4px;padding:4px 10px;border-radius:4px;">Cuenta Activada</span>
          </div>

          <!-- Title -->
          <h1 style="margin:0 0 6px 0;font-size:22px;font-weight:700;color:#0D1B2A;line-height:1.3;">¡Ya puedes comenzar a operar!</h1>
          <p style="margin:0 0 24px 0;color:#64748b;font-size:14px;">Hola <strong style="color:#1e293b;">{{ client_name }}</strong>, tus documentos han sido verificados y aprobados. Tu cuenta está activa.</p>

          <!-- Checklist -->
          <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;border:1px solid #e8ecf0;border-radius:8px;overflow:hidden;margin:0 0 28px 0;">
            <tr style="border-bottom:1px solid #eef0f3;">
              <td style="padding:13px 18px;font-size:14px;color:#1e293b;vertical-align:top;">
                <span style="color:#10b981;font-weight:700;margin-right:10px;">&#10003;</span>Tu identidad ha sido verificada
              </td>
            </tr>
            <tr style="border-bottom:1px solid #eef0f3;">
              <td style="padding:13px 18px;font-size:14px;color:#1e293b;vertical-align:top;">
                <span style="color:#10b981;font-weight:700;margin-right:10px;">&#10003;</span>Puedes crear operaciones de compra y venta de dólares
              </td>
            </tr>
            <tr>
              <td style="padding:13px 18px;font-size:14px;color:#1e293b;vertical-align:top;">
                <span style="color:#10b981;font-weight:700;margin-right:10px;">&#10003;</span>Acceso completo a todas las funcionalidades
              </td>
            </tr>
          </table>

          <!-- CTA button -->
          <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;margin:0 0 24px 0;">
            <tr>
              <td align="center">
                <a href="https://www.qoricash.pe"
                   style="display:inline-block;background-color:#00DEA8;color:#0D1B2A;font-weight:700;font-size:15px;padding:13px 36px;border-radius:8px;text-decoration:none;letter-spacing:0.3px;">
                  Ingresar a QoriCash
                </a>
              </td>
            </tr>
          </table>

          <!-- Access info -->
          <div style="border-radius:8px;padding:13px 16px;margin:0 0 20px 0;font-size:13px;line-height:1.65;background:#f0f9ff;border-left:3px solid #0ea5e9;color:#0c4a6e;">
            Ingresa desde <strong>www.qoricash.pe</strong> o nuestra app móvil usando tu número de documento y la contraseña que definiste al registrarte.
          </div>

          <!-- Closing -->
          <div style="height:1px;background-color:#f1f5f9;margin:24px 0;"></div>
          <p style="margin:0;font-size:13px;color:#94a3b8;">¿Tienes alguna consulta? Escríbenos a <a href="mailto:info@qoricash.pe" style="color:#94a3b8;">info@qoricash.pe</a></p>

        </td>
      </tr>

      <!-- FOOTER -->
      <tr>
        <td class="email-footer-cell" style="background-color:#f8fafc;border-top:1px solid #e8ecf0;padding:20px 40px;text-align:center;">
          <p style="margin:0 0 4px 0;color:#0D1B2A;font-size:13px;font-weight:700;">QoriCash</p>
          <p style="margin:0 0 4px 0;color:#94a3b8;font-size:12px;">RUC: 20615113698 &nbsp;&middot;&nbsp; <a href="mailto:info@qoricash.pe" style="color:#94a3b8;text-decoration:none;">info@qoricash.pe</a></p>
          <p style="margin:0;color:#cbd5e1;font-size:11px;">© 2025 QoriCash. Todos los derechos reservados.</p>
        </td>
      </tr>

    </table>
  </td></tr>
</table>
</body>
</html>"""
        return render_template_string(template,
                                     client_name=client_name,
                                     client_dni=client.dni)

    @staticmethod
    def send_trader_kyc_approved_notification(client, trader):
        """
        Notificación al Trader cuando el KYC de su cliente es aprobado.
        Se envía al email del trader, informando que la cuenta ya está activa.

        Args:
            client: Objeto Client cuyo KYC fue aprobado
            trader: Usuario Trader que registró al cliente

        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            trader_email = getattr(trader, 'email', None)
            if not trader_email:
                return False, 'Trader sin email registrado'

            client_name = client.full_name or client.razon_social or 'Cliente'
            trader_name = trader.username if trader else 'Asesor'

            logger.info(f'📧 [EMAIL-TRADER-KYC] Notificando a trader {trader_name} sobre activación de {client.dni}')

            subject = f'✅ Cuenta activa: {client_name} ya puede operar | QoriCash'

            html_body = EmailTemplates._render_trader_kyc_approved_template(client, client_name, trader_name)

            msg = Message(
                subject=subject,
                recipients=[trader_email],
                html=html_body
            )

            mail.send(msg)
            logger.info(f'✅ [EMAIL-TRADER-KYC] Notificación enviada a {trader_email}')
            return True, 'Notificación enviada al trader'

        except Exception as e:
            logger.error(f'❌ [EMAIL-TRADER-KYC] Error: {str(e)}')
            return False, str(e)

    @staticmethod
    def _render_trader_kyc_approved_template(client, client_name, trader_name):
        """Plantilla de notificación al Trader: KYC aprobado, cuenta activa"""
        template = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>""" + _EMAIL_CSS + """</style>
</head>
<body style="margin:0;padding:0;background-color:#f5f7fa;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f5f7fa;padding:28px 16px;">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 16px rgba(13,27,42,0.08);">

      <!-- BANNER -->
      <tr>
        <td style="padding:0;background:#0D1B2A;line-height:0;font-size:0;">
          <img src="https://res.cloudinary.com/dbks8vqoh/image/upload/v1773788552/qoricash/banneremail.png" alt="QoriCash" width="600" style="width:100%;max-width:600px;display:block;border:0;">
        </td>
      </tr>

      <!-- ACCENT LINE: green -->
      <tr><td style="padding:0;height:3px;background-color:#10b981;font-size:0;line-height:0;">&nbsp;</td></tr>

      <!-- BODY -->
      <tr>
        <td class="email-body-cell" style="padding:36px 40px;color:#334155;font-size:15px;line-height:1.65;">

          <!-- Event label -->
          <div style="margin:0 0 16px 0;">
            <span style="display:inline-block;background:#f0fdf4;color:#10b981;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.4px;padding:4px 10px;border-radius:4px;">KYC Aprobado</span>
          </div>

          <!-- Title -->
          <h1 style="margin:0 0 6px 0;font-size:22px;font-weight:700;color:#0D1B2A;line-height:1.3;">Cuenta de cliente activada</h1>
          <p style="margin:0 0 24px 0;color:#64748b;font-size:14px;">Hola <strong style="color:#1e293b;">{{ trader_name }}</strong>, te informamos que el KYC de uno de tus clientes fue aprobado por el equipo de Middle Office y su cuenta ya está activa.</p>

          <!-- Client info box -->
          <p style="margin:0 0 10px 0;font-size:11px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1.2px;">Datos del cliente</p>
          <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;border:1px solid #e8ecf0;border-radius:8px;overflow:hidden;margin:0 0 24px 0;">
            <tr style="border-bottom:1px solid #eef0f3;">
              <td style="padding:12px 18px;font-size:13px;color:#64748b;width:40%;vertical-align:top;">Nombre</td>
              <td style="padding:12px 18px;font-size:13px;color:#1e293b;font-weight:600;vertical-align:top;">{{ client_name }}</td>
            </tr>
            <tr>
              <td style="padding:12px 18px;font-size:13px;color:#64748b;vertical-align:top;">N° Documento</td>
              <td style="padding:12px 18px;font-size:13px;color:#1e293b;font-weight:600;vertical-align:top;">{{ client_dni }}</td>
            </tr>
          </table>

          <!-- Status badge -->
          <div style="border-radius:8px;padding:13px 18px;margin:0 0 24px 0;font-size:13px;line-height:1.65;background:#f0fdf4;border-left:3px solid #10b981;color:#064e3b;">
            <strong>Estado:</strong> Cuenta <strong>Activa</strong> — el cliente ya puede crear operaciones de compra y venta de dólares.
          </div>

          <!-- Closing -->
          <div style="height:1px;background-color:#f1f5f9;margin:24px 0;"></div>
          <p style="margin:0;font-size:13px;color:#94a3b8;">Este es un mensaje automático del sistema QoriCash. Para más información, ingresa a <a href="https://app.qoricash.pe" style="color:#94a3b8;">app.qoricash.pe</a>.</p>

        </td>
      </tr>

      <!-- FOOTER -->
      <tr>
        <td class="email-footer-cell" style="background-color:#f8fafc;border-top:1px solid #e8ecf0;padding:20px 40px;text-align:center;">
          <p style="margin:0 0 4px 0;color:#0D1B2A;font-size:13px;font-weight:700;">QoriCash</p>
          <p style="margin:0 0 4px 0;color:#94a3b8;font-size:12px;">RUC: 20615113698 &nbsp;&middot;&nbsp; <a href="mailto:info@qoricash.pe" style="color:#94a3b8;text-decoration:none;">info@qoricash.pe</a></p>
          <p style="margin:0;color:#cbd5e1;font-size:11px;">© 2025 QoriCash. Todos los derechos reservados.</p>
        </td>
      </tr>

    </table>
  </td></tr>
</table>
</body>
</html>"""
        return render_template_string(template,
                                     client_name=client_name,
                                     client_dni=client.dni,
                                     trader_name=trader_name)
