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
# CONSTANTES DE MARCA
# ============================================
_LOGO_URL  = 'https://app.qoricash.pe/static/images/logo-email.png'
_GREEN     = '#5CB85C'
_DARK      = '#0D1B2A'
_SBS_TAG   = 'Regulada por la SBS &nbsp;&middot;&nbsp; Res. N.&ordm; 00313-2026'

# ============================================
# CSS BASE: solo @media queries (estilos inline en las plantillas)
# ============================================
_EMAIL_CSS = """
    @media only screen and (max-width: 620px) {
        .email-body-cell { padding: 24px 20px !important; }
        .email-footer-cell { padding: 20px !important; }
    }
"""

# ============================================
# BLOQUES COMPARTIDOS
# ============================================
_HEADER_BLOCK = f"""
      <!-- HEADER: isotipo + SBS -->
      <tr>
        <td style="padding:20px 36px 18px;border-bottom:1px solid #E2E8F0;">
          <table width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr>
              <td style="vertical-align:middle;">
                <table cellpadding="0" cellspacing="0" border="0">
                  <tr>
                    <td style="vertical-align:middle;padding-right:12px;">
                      <img src="{_LOGO_URL}" alt="QoriCash" style="height:44px;width:auto;display:block;">
                    </td>
                    <td style="vertical-align:middle;">
                      <span style="font-size:22px;font-weight:800;color:{_DARK};letter-spacing:2px;font-family:Arial,sans-serif;">QORICASH</span>
                    </td>
                  </tr>
                </table>
              </td>
              <td style="text-align:right;vertical-align:middle;">
                <span style="font-size:10px;color:#64748B;line-height:1.5;">{_SBS_TAG}</span>
              </td>
            </tr>
          </table>
        </td>
      </tr>
"""

_FOOTER_BLOCK = f"""
      <!-- FOOTER -->
      <tr>
        <td class="email-footer-cell"
            style="background-color:#F8FAFC;border-top:1px solid #E2E8F0;
                   padding:20px 36px;text-align:center;">
          <p style="margin:0 0 3px;color:{_DARK};font-size:13px;font-weight:700;">QoriCash</p>
          <p style="margin:0 0 3px;color:#94a3b8;font-size:11px;">
            RUC: 20615113698 &nbsp;&middot;&nbsp;
            <a href="mailto:info@qoricash.pe" style="color:#94a3b8;text-decoration:none;">info@qoricash.pe</a>
            &nbsp;&middot;&nbsp;
            <a href="https://www.qoricash.pe" style="color:#94a3b8;text-decoration:none;">www.qoricash.pe</a>
          </p>
          <p style="margin:0 0 3px;color:#94a3b8;font-size:11px;">
            Av. Brasil 2790, int. 504 &nbsp;&middot;&nbsp; Pueblo Libre, Lima
          </p>
          <p style="margin:0;color:#CBD5E1;font-size:10px;">&copy; 2026 QoriCash. Todos los derechos reservados.</p>
        </td>
      </tr>
"""

def _build_shared_email_block(shared_clients: list) -> str:
    """
    Genera el bloque HTML de aviso cuando el mismo correo ya está asociado
    a otros registros existentes. Retorna string vacío si no hay otros clientes.
    """
    if not shared_clients:
        return ''

    rows = ''.join(
        f'<tr><td style="padding:4px 0;font-size:12px;color:#78350F;line-height:1.5;">'
        f'&bull;&nbsp;<strong>{c["display_name"]}</strong>'
        f'&nbsp;&mdash;&nbsp;{c["doc_type"]}: {c["dni"]}'
        f'</td></tr>'
        for c in shared_clients
    )

    return (
        f'<div style="border-radius:6px;padding:13px 16px;margin:0 0 24px 0;font-size:13px;'
        f'line-height:1.65;background:#FEF3C7;border-left:3px solid #F59E0B;">'
        f'<p style="margin:0 0 6px 0;font-weight:700;font-size:11px;text-transform:uppercase;'
        f'letter-spacing:0.8px;color:#92400E;">&#9888; Este correo ya está vinculado a otros registros</p>'
        f'<p style="margin:0 0 8px 0;font-size:12px;color:#78350F;">'
        f'Se está creando un nuevo acceso con este correo. Los registros existentes son:</p>'
        f'<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">'
        f'{rows}'
        f'</table>'
        f'</div>'
    )


def _wrap_email(body_html: str) -> str:
    """Envuelve contenido HTML en el wrapper base de email QoriCash."""
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>{_EMAIL_CSS}</style>
</head>
<body style="margin:0;padding:0;background-color:#f5f7fa;font-family:Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f5f7fa;padding:28px 16px;">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0"
           style="max-width:600px;width:100%;background:#ffffff;border-radius:12px;
                  overflow:hidden;box-shadow:0 2px 16px rgba(13,27,42,0.08);border-top:4px solid #5CB85C;">
      {_HEADER_BLOCK}
      {body_html}
      {_FOOTER_BLOCK}
    </table>
  </td></tr>
</table>
</body>
</html>"""


class EmailTemplates:
    """Plantillas de correo diferenciadas por origen"""

    @staticmethod
    def _get_shared_email_clients(client) -> list:
        """
        Retorna lista de dicts con los demás clientes que comparten el mismo email.
        Se excluye al propio cliente recién registrado.
        """
        try:
            from app.models.client import Client
            others = Client.query.filter(
                Client.email == client.email,
                Client.id != client.id
            ).all()
            return [
                {
                    'display_name': c.full_name or c.razon_social or 'Sin nombre',
                    'doc_type': c.document_type,
                    'dni': c.dni,
                }
                for c in others
            ]
        except Exception:
            return []

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

            shared_clients = EmailTemplates._get_shared_email_clients(client)
            html_body = EmailTemplates._render_mobile_welcome_template(client, shared_clients)

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
        - Para Persona Jurídica (RUC): CC a gerencia@qoricash.pe

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

            # CC a gerencia para Persona Jurídica (requiere revisión KYC especial)
            cc = []
            if getattr(client, 'document_type', None) == 'RUC':
                cc.append('gerencia@qoricash.pe')
                logger.info(f'📧 [EMAIL-WEB] CC a gerencia por registro Jurídica: {client.dni}')

            subject = '¡Bienvenido a QoriCash!'

            shared_clients = EmailTemplates._get_shared_email_clients(client)
            html_body = EmailTemplates._render_web_welcome_template(client, shared_clients)

            msg = Message(
                subject=subject,
                recipients=to,
                cc=cc if cc else None,
                html=html_body
            )

            mail.send(msg)
            logger.info(f'✅ [EMAIL-WEB] Email enviado a {client.dni}' + (' + gerencia' if cc else ''))
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

            # CC: trader que creó al cliente + gerencia
            seen = set(to)
            cc = []
            if trader and getattr(trader, 'email', None) and trader.email not in seen:
                cc.append(trader.email)
                seen.add(trader.email)
            if 'gerencia@qoricash.pe' not in seen:
                cc.append('gerencia@qoricash.pe')

            subject = '✅ Cuenta Activada — ¡Ya puedes operar! | QoriCash'

            # Email 1: al cliente CON contraseña temporal
            html_cliente = EmailTemplates._render_trader_activation_template(client, trader, temporary_password)
            msg_cliente = Message(
                subject=subject,
                recipients=to,
                html=html_cliente
            )
            mail.send(msg_cliente)
            logger.info(f'✅ [EMAIL-TRADER] Email con contraseña enviado al cliente {client.dni}')

            # Email 2: al trader y gerencia SIN contraseña
            if cc:
                html_cc = EmailTemplates._render_auto_activation_template(client)
                msg_cc = Message(
                    subject=subject,
                    recipients=cc,
                    html=html_cc
                )
                mail.send(msg_cc)
                logger.info(f'✅ [EMAIL-TRADER] Email sin contraseña enviado a CC: {cc}')

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
    def _render_mobile_welcome_template(client, shared_clients=None):
        """Plantilla para registro desde móvil"""
        client_name = client.full_name or client.razon_social or 'Cliente'
        shared_block = _build_shared_email_block(shared_clients or [])

        body = """
      <!-- BODY -->
      <tr>
        <td class="email-body-cell" style="padding:32px 36px;color:#334155;font-size:14px;line-height:1.65;">

          <div style="margin:0 0 16px 0;">
            <span style="display:inline-block;background:#F0FDF4;color:""" + _GREEN + """;font-size:10px;font-weight:700;
                         text-transform:uppercase;letter-spacing:1.4px;padding:4px 10px;border-radius:4px;">
              Registro recibido
            </span>
          </div>

          <h1 style="margin:0 0 6px 0;font-size:21px;font-weight:700;color:""" + _DARK + """;line-height:1.3;">Tu cuenta ha sido creada</h1>
          <p style="margin:0 0 24px 0;color:#64748b;font-size:14px;">
            Hola <strong style="color:#1e293b;">{{ client_name }}</strong>, te damos la bienvenida a QoriCash.
          </p>

          <table width="100%" cellspacing="0" cellpadding="0"
                 style="border-collapse:collapse;border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;margin:0 0 24px 0;">
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:11px 18px;width:160px;color:#94a3b8;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:top;">Documento</td>
              <td style="padding:11px 18px;color:#1e293b;font-size:13px;font-weight:500;vertical-align:top;">{{ client_dni }}</td>
            </tr>
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:11px 18px;color:#94a3b8;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:top;">Correo electrónico</td>
              <td style="padding:11px 18px;color:#1e293b;font-size:13px;font-weight:500;vertical-align:top;">{{ client_email }}</td>
            </tr>
            <tr>
              <td style="padding:11px 18px;color:#94a3b8;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:top;">Estado</td>
              <td style="padding:11px 18px;color:#d97706;font-size:13px;font-weight:600;vertical-align:top;">Pendiente de verificación</td>
            </tr>
          </table>

          <p style="margin:0 0 10px 0;font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1.2px;">Próximos pasos</p>
          <div style="border-radius:6px;padding:13px 16px;margin:0 0 12px 0;font-size:13px;line-height:1.65;
                      background:#FFFBEB;border-left:3px solid #F59E0B;color:#78350f;">
            Para realizar tu primera operación debemos validar tu identidad. Por favor sube tu documento de identidad
            desde la aplicación móvil. Recibirás una notificación cuando sea aprobado.
          </div>
          <div style="border-radius:6px;padding:13px 16px;margin:0 0 24px 0;font-size:13px;line-height:1.65;
                      background:#F0FDF4;border-left:3px solid """ + _GREEN + """;color:#14532d;">
            <strong>Acceso web:</strong> También puedes ingresar desde <strong>www.qoricash.pe</strong>
            usando tu número de documento y la contraseña que registraste en la app.
          </div>

          {{ shared_block }}
          <div style="height:1px;background-color:#F1F5F9;margin:20px 0;"></div>
          <p style="margin:0;font-size:12px;color:#94a3b8;">
            ¿Tienes alguna consulta? Escríbenos a
            <a href="mailto:info@qoricash.pe" style="color:""" + _GREEN + """;">info@qoricash.pe</a>
          </p>
        </td>
      </tr>"""

        return render_template_string(
            _wrap_email(body),
            client_name=client_name,
            client_dni=client.dni,
            client_email=client.email,
            shared_block=shared_block
        )

    @staticmethod
    def _render_web_welcome_template(client, shared_clients=None):
        """Plantilla para registro desde web"""
        client_name = client.full_name or client.razon_social or 'Cliente'
        shared_block = _build_shared_email_block(shared_clients or [])

        body = """
      <tr>
        <td class="email-body-cell" style="padding:32px 36px;color:#334155;font-size:14px;line-height:1.65;">

          <div style="margin:0 0 16px 0;">
            <span style="display:inline-block;background:#F0FDF4;color:""" + _GREEN + """;font-size:10px;font-weight:700;
                         text-transform:uppercase;letter-spacing:1.4px;padding:4px 10px;border-radius:4px;">
              Registro recibido
            </span>
          </div>

          <h1 style="margin:0 0 6px 0;font-size:21px;font-weight:700;color:""" + _DARK + """;line-height:1.3;">Tu cuenta ha sido creada</h1>
          <p style="margin:0 0 24px 0;color:#64748b;font-size:14px;">
            Hola <strong style="color:#1e293b;">{{ client_name }}</strong>,
            te damos la bienvenida a la plataforma web de QoriCash.
          </p>

          <table width="100%" cellspacing="0" cellpadding="0"
                 style="border-collapse:collapse;border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;margin:0 0 24px 0;">
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:11px 18px;width:160px;color:#94a3b8;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:top;">Documento</td>
              <td style="padding:11px 18px;color:#1e293b;font-size:13px;font-weight:500;vertical-align:top;">{{ client_dni }}</td>
            </tr>
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:11px 18px;color:#94a3b8;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:top;">Correo electrónico</td>
              <td style="padding:11px 18px;color:#1e293b;font-size:13px;font-weight:500;vertical-align:top;">{{ client_email }}</td>
            </tr>
            <tr>
              <td style="padding:11px 18px;color:#94a3b8;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:top;">Estado</td>
              <td style="padding:11px 18px;color:#d97706;font-size:13px;font-weight:600;vertical-align:top;">Pendiente de verificación</td>
            </tr>
          </table>

          <p style="margin:0 0 10px 0;font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1.2px;">Próximos pasos</p>
          <div style="border-radius:6px;padding:13px 16px;margin:0 0 12px 0;font-size:13px;line-height:1.65;
                      background:#FFFBEB;border-left:3px solid #F59E0B;color:#78350f;">
            Para realizar tu primera operación debemos validar tu identidad. Al crear tu primera operación
            se te solicitará subir tu documento de identidad. Recibirás una notificación cuando sea aprobado.
          </div>
          <div style="border-radius:6px;padding:13px 16px;margin:0 0 24px 0;font-size:13px;line-height:1.65;
                      background:#F0FDF4;border-left:3px solid """ + _GREEN + """;color:#14532d;">
            Próximamente publicaremos nuestra app para <strong>iOS</strong> y <strong>Android</strong>.
            Te notificaremos cuando esté disponible para descargar.
          </div>

          {{ shared_block }}
          <div style="height:1px;background-color:#F1F5F9;margin:20px 0;"></div>
          <p style="margin:0;font-size:12px;color:#94a3b8;">
            ¿Tienes alguna consulta? Escríbenos a
            <a href="mailto:info@qoricash.pe" style="color:""" + _GREEN + """;">info@qoricash.pe</a>
          </p>
        </td>
      </tr>"""

        return render_template_string(
            _wrap_email(body),
            client_name=client_name,
            client_dni=client.dni,
            client_email=client.email,
            shared_block=shared_block
        )

    @staticmethod
    def _render_trader_activation_template(client, trader, temporary_password):
        """Plantilla para activación con contraseña temporal (cliente creado por Trader)"""
        client_name = client.full_name or client.razon_social or 'Cliente'
        trader_name = trader.username if trader else 'QoriCash'

        body = """
      <tr>
        <td class="email-body-cell" style="padding:32px 36px;color:#334155;font-size:14px;line-height:1.65;">

          <div style="margin:0 0 16px 0;">
            <span style="display:inline-block;background:#F0FDF4;color:""" + _GREEN + """;font-size:10px;font-weight:700;
                         text-transform:uppercase;letter-spacing:1.4px;padding:4px 10px;border-radius:4px;">
              ✓ Cuenta Activada
            </span>
          </div>

          <h1 style="margin:0 0 6px 0;font-size:21px;font-weight:700;color:""" + _DARK + """;line-height:1.3;">¡Ya puedes comenzar a operar!</h1>
          <p style="margin:0 0 24px 0;color:#64748b;font-size:14px;">
            Hola <strong style="color:#1e293b;">{{ client_name }}</strong>,
            tu identidad ha sido verificada y aprobada. Tu cuenta está activa y lista para operar.
          </p>

          <table width="100%" cellspacing="0" cellpadding="0"
                 style="border-collapse:collapse;border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;margin:0 0 24px 0;">
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:12px 18px;font-size:13px;color:#1e293b;vertical-align:top;">
                <span style="color:""" + _GREEN + """;font-weight:700;margin-right:10px;">&#10003;</span>Tu identidad ha sido verificada
              </td>
            </tr>
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:12px 18px;font-size:13px;color:#1e293b;vertical-align:top;">
                <span style="color:""" + _GREEN + """;font-weight:700;margin-right:10px;">&#10003;</span>Puedes crear operaciones de compra y venta de dólares
              </td>
            </tr>
            <tr>
              <td style="padding:12px 18px;font-size:13px;color:#1e293b;vertical-align:top;">
                <span style="color:""" + _GREEN + """;font-weight:700;margin-right:10px;">&#10003;</span>Acceso completo a todas las funcionalidades
              </td>
            </tr>
          </table>

          <p style="margin:0 0 10px 0;font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1.2px;">Tu contraseña temporal</p>
          <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;margin:0 0 12px 0;">
            <tr>
              <td style="background-color:""" + _DARK + """;border-radius:10px;padding:22px 24px;text-align:center;">
                <p style="margin:0 0 10px 0;color:rgba(255,255,255,0.50);font-size:10px;letter-spacing:0.8px;text-transform:uppercase;">Contraseña de acceso</p>
                <p style="margin:0 0 10px 0;color:""" + _GREEN + """;font-size:28px;font-family:'Courier New',Courier,monospace;font-weight:700;letter-spacing:4px;">{{ temporary_password }}</p>
                <p style="margin:0;color:rgba(255,255,255,0.35);font-size:11px;">Cópiala exactamente como aparece</p>
              </td>
            </tr>
          </table>
          <div style="border-radius:6px;padding:13px 16px;margin:0 0 12px 0;font-size:13px;line-height:1.65;
                      background:#F0FDF4;border-left:3px solid """ + _GREEN + """;color:#14532d;">
            Usa esta contraseña para iniciar sesión en <strong>www.qoricash.pe</strong>.
            El sistema te pedirá crear una nueva contraseña en tu primer acceso.
          </div>
          <div style="border-radius:6px;padding:13px 16px;margin:0 0 24px 0;font-size:13px;line-height:1.65;
                      background:#FEF2F2;border-left:3px solid #EF4444;color:#7f1d1d;">
            <strong>Importante:</strong> Por seguridad, deberás cambiar esta contraseña temporal la primera vez que inicies sesión.
          </div>

          <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;margin:0 0 24px 0;">
            <tr>
              <td align="center">
                <a href="https://www.qoricash.pe"
                   style="display:inline-block;background-color:""" + _GREEN + """;color:#ffffff;font-weight:700;
                          font-size:14px;padding:13px 36px;border-radius:8px;text-decoration:none;letter-spacing:0.3px;">
                  Ingresar a QoriCash
                </a>
              </td>
            </tr>
          </table>

          <div style="height:1px;background-color:#F1F5F9;margin:20px 0;"></div>
          <p style="margin:0;font-size:12px;color:#94a3b8;">
            ¿Tienes alguna consulta? Contacta a tu asesor
            <strong style="color:#1e293b;">{{ trader_name }}</strong> o escríbenos a
            <a href="mailto:info@qoricash.pe" style="color:""" + _GREEN + """;">info@qoricash.pe</a>
          </p>
        </td>
      </tr>"""

        return render_template_string(
            _wrap_email(body),
            client_name=client_name,
            client_dni=client.dni,
            trader_name=trader_name,
            temporary_password=temporary_password
        )

    @staticmethod
    def _render_auto_activation_template(client):
        """Plantilla para activación sin contraseña (cliente auto-registrado)"""
        client_name = client.full_name or client.razon_social or 'Cliente'

        body = """
      <tr>
        <td class="email-body-cell" style="padding:32px 36px;color:#334155;font-size:14px;line-height:1.65;">

          <div style="margin:0 0 16px 0;">
            <span style="display:inline-block;background:#F0FDF4;color:""" + _GREEN + """;font-size:10px;font-weight:700;
                         text-transform:uppercase;letter-spacing:1.4px;padding:4px 10px;border-radius:4px;">
              ✓ Cuenta Activada
            </span>
          </div>

          <h1 style="margin:0 0 6px 0;font-size:21px;font-weight:700;color:""" + _DARK + """;line-height:1.3;">¡Ya puedes comenzar a operar!</h1>
          <p style="margin:0 0 24px 0;color:#64748b;font-size:14px;">
            Hola <strong style="color:#1e293b;">{{ client_name }}</strong>,
            tus documentos han sido verificados y aprobados. Tu cuenta está activa.
          </p>

          <table width="100%" cellspacing="0" cellpadding="0"
                 style="border-collapse:collapse;border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;margin:0 0 24px 0;">
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:12px 18px;font-size:13px;color:#1e293b;vertical-align:top;">
                <span style="color:""" + _GREEN + """;font-weight:700;margin-right:10px;">&#10003;</span>Tu identidad ha sido verificada
              </td>
            </tr>
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:12px 18px;font-size:13px;color:#1e293b;vertical-align:top;">
                <span style="color:""" + _GREEN + """;font-weight:700;margin-right:10px;">&#10003;</span>Puedes crear operaciones de compra y venta de dólares
              </td>
            </tr>
            <tr>
              <td style="padding:12px 18px;font-size:13px;color:#1e293b;vertical-align:top;">
                <span style="color:""" + _GREEN + """;font-weight:700;margin-right:10px;">&#10003;</span>Acceso completo a todas las funcionalidades
              </td>
            </tr>
          </table>

          <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;margin:0 0 16px 0;">
            <tr>
              <td align="center">
                <a href="https://www.qoricash.pe"
                   style="display:inline-block;background-color:""" + _GREEN + """;color:#ffffff;font-weight:700;
                          font-size:14px;padding:13px 36px;border-radius:8px;text-decoration:none;letter-spacing:0.3px;">
                  Ingresar a QoriCash
                </a>
              </td>
            </tr>
          </table>

          <div style="border-radius:6px;padding:13px 16px;margin:0 0 24px 0;font-size:13px;line-height:1.65;
                      background:#F0FDF4;border-left:3px solid """ + _GREEN + """;color:#14532d;">
            Ingresa desde <strong>www.qoricash.pe</strong> o nuestra app móvil usando tu número de documento
            y la contraseña que definiste al registrarte.
          </div>

          <div style="height:1px;background-color:#F1F5F9;margin:20px 0;"></div>
          <p style="margin:0;font-size:12px;color:#94a3b8;">
            ¿Tienes alguna consulta? Escríbenos a
            <a href="mailto:info@qoricash.pe" style="color:""" + _GREEN + """;">info@qoricash.pe</a>
          </p>
        </td>
      </tr>"""

        return render_template_string(
            _wrap_email(body),
            client_name=client_name,
            client_dni=client.dni
        )
