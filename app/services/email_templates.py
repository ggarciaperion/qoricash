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


def _send_email(msg: Message) -> bool:
    """Envía un correo via Gmail/Google Workspace (Flask-Mail). Agrega plain-text automáticamente."""
    from app.services.email_service import EmailService
    if not msg.body and msg.html:
        msg.body = EmailService._html_to_text(msg.html)
    try:
        mail.send(msg)
        logger.info(f'[EMAIL] OK to={msg.recipients}')
        return True
    except Exception as e:
        logger.error(f'[EMAIL] Error: {str(e)}')
        return False

# ============================================
# CONSTANTES DE MARCA
# ============================================
_LOGO_URL  = 'https://app.qoricash.pe/static/images/logo-email.png'
_GREEN     = '#5CB85C'
_DARK      = '#0D1B2A'
_SBS_TAG   = 'Regulada por la SBS &nbsp;&middot;&nbsp; Res. N.&ordm; 00313-2026'

# ============================================
# TEMA POR TIPO DE CLIENTE
# ============================================
_THEMES = {
    'persona': {
        'accent':   '#22C55E',
        'bg':       '#F0FDF4',
        'info_bg':  '#F0FDF4',
        'info_txt': '#14532d',
        'banner':   'https://app.qoricash.pe/static/images/encabezado_personal.jpg',
    },
    'empresa': {
        'accent':   '#1A3D58',
        'bg':       '#EEF2F8',
        'info_bg':  '#EEF4FF',
        'info_txt': '#1e3a5f',
        'banner':   'https://app.qoricash.pe/static/images/encabezado_corporativo.jpg',
    },
}

def _get_theme(doc_type: str) -> str:
    return 'empresa' if doc_type == 'RUC' else 'persona'

def _apply_theme_colors(html: str, theme: str) -> str:
    t = _THEMES[theme]
    return (html
        .replace(_GREEN,    t['accent'])
        .replace('#F0FDF4', t['info_bg'])
        .replace('#14532d', t['info_txt'])
    )

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


def _wrap_email_themed(body_html: str, theme: str = 'persona') -> str:
    """Wrapper temático: banner persona (verde) o empresa (navy) según tipo de cliente."""
    t = _THEMES[theme]
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>{_EMAIL_CSS}</style>
</head>
<body style="margin:0;padding:0;background:#f5f7fa;font-family:Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f7fa;padding:28px 16px;">
  <tr><td align="center">
    <table width="560" cellpadding="0" cellspacing="0"
           style="max-width:560px;width:100%;background:#ffffff;border-radius:12px;
                  overflow:hidden;box-shadow:0 2px 16px rgba(13,27,42,0.08);">
      <tr>
        <td style="padding:0;line-height:0;">
          <img src="{t['banner']}" alt="QoriCash" width="560" style="display:block;width:100%;max-width:560px;">
        </td>
      </tr>
      <tr>
        <td style="padding:8px 36px;border-bottom:1px solid #E2E8F0;text-align:right;background:#ffffff;">
          <span style="font-size:10px;color:#64748B;">{_SBS_TAG}</span>
        </td>
      </tr>
      <tr>
        <td style="height:3px;background:{t['accent']};padding:0;line-height:0;font-size:0;">&nbsp;</td>
      </tr>
      {{body_html}}
      {_FOOTER_BLOCK}
    </table>
  </td></tr>
</table>
</body></html>""".replace('{body_html}', body_html)

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

            subject = 'Bienvenido a QoriCash'

            shared_clients = EmailTemplates._get_shared_email_clients(client)
            html_body = EmailTemplates._render_mobile_welcome_template(client, shared_clients)

            msg = Message(
                subject=subject,
                recipients=to,
                html=html_body
            )

            ok = _send_email(msg)
            logger.info(f'[EMAIL-MOBILE] Resultado={ok} para {client.dni}')
            return ok, 'Email enviado' if ok else 'Error al enviar'

        except Exception as e:
            logger.error(f'❌ [EMAIL-MOBILE] Error: {str(e)}')
            return False, str(e)

    @staticmethod
    def send_welcome_email_from_web(client):
        """
        Correo de bienvenida para clientes registrados desde página web.
        - NO incluye contraseña (definida por el usuario)
        - CC a gerencia@qoricash.pe en todos los registros web

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

            # CC a gerencia en todos los registros web (DNI y RUC)
            cc = ['gerencia@qoricash.pe']
            logger.info(f'📧 [EMAIL-WEB] CC a gerencia — registro web: {client.dni}')

            subject = 'Bienvenido a QoriCash'

            shared_clients = EmailTemplates._get_shared_email_clients(client)
            html_body = EmailTemplates._render_web_welcome_template(client, shared_clients)

            msg = Message(
                subject=subject,
                recipients=to,
                cc=cc,
                html=html_body
            )

            ok = _send_email(msg)
            logger.info(f'[EMAIL-WEB] Resultado={ok} para {client.dni} + gerencia')
            return ok, 'Email enviado' if ok else 'Error al enviar'

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

            subject = 'Cuenta Activada - Ya puedes operar | QoriCash'

            # Email 1: al cliente CON contraseña temporal
            html_cliente = EmailTemplates._render_trader_activation_template(client, trader, temporary_password)
            msg_cliente = Message(
                subject=subject,
                recipients=to,
                html=html_cliente
            )
            ok1 = _send_email(msg_cliente)
            logger.info(f'[EMAIL-TRADER] Resultado={ok1} cliente {client.dni}')

            # Email 2: al trader y gerencia SIN contraseña
            ok2 = True
            if cc:
                html_cc = EmailTemplates._render_auto_activation_template(client)
                msg_cc = Message(
                    subject=subject,
                    recipients=cc,
                    html=html_cc
                )
                ok2 = _send_email(msg_cc)
                logger.info(f'[EMAIL-TRADER] Resultado={ok2} trader/gerencia: {cc}')

            ok = ok1 and ok2
            return ok, 'Email enviado' if ok else 'Error parcial al enviar'

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

            subject = 'Cuenta Activada - Ya puedes operar | QoriCash'

            html_body = EmailTemplates._render_auto_activation_template(client)

            msg = Message(
                subject=subject,
                recipients=to,
                cc=['gerencia@qoricash.pe'],
                html=html_body
            )

            ok = _send_email(msg)
            logger.info(f'[EMAIL-ACTIVATION] Resultado={ok} para {client.dni}')
            return ok, 'Email enviado' if ok else 'Error al enviar'

        except Exception as e:
            logger.error(f'❌ [EMAIL-ACTIVATION] Error: {str(e)}')
            return False, str(e)

    # ============================================
    # PLANTILLAS HTML
    # ============================================

    @staticmethod
    def _render_mobile_welcome_template(client, shared_clients=None, canal='movil'):
        """Plantilla unificada de bienvenida — móvil y web comparten el mismo HTML."""
        client_name     = client.full_name or client.razon_social or 'Cliente'
        shared_block    = _build_shared_email_block(shared_clients or [])
        doc_type        = getattr(client, 'document_type', 'DNI')
        theme           = _get_theme(doc_type)
        client_phone    = getattr(client, 'phone', None)
        client_contacto = getattr(client, 'full_name', None) if doc_type == 'RUC' else None

        body = """
      <tr>
        <td class="email-body-cell" style="padding:32px 36px;color:#334155;font-size:14px;line-height:1.65;">

          <div style="margin:0 0 20px 0;">
            <span style="display:inline-block;background:#ffffff;color:""" + _GREEN + """;font-size:10px;font-weight:700;
                         text-transform:uppercase;letter-spacing:1.4px;padding:5px 14px;border-radius:20px;
                         border:1.5px solid """ + _GREEN + """;box-shadow:0 2px 8px rgba(0,0,0,0.07);">
              Registro recibido con éxito
            </span>
          </div>

          <p style="margin:0 0 24px 0;color:#64748b;font-size:14px;">
            Hola <strong style="color:#1e293b;">{{ client_name }}</strong>, te damos la bienvenida a QoriCash.
          </p>

          <table width="100%" cellspacing="0" cellpadding="0"
                 style="border-collapse:collapse;border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;margin:0 0 24px 0;">
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:11px 18px;width:160px;color:#94a3b8;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:middle;">Documento</td>
              <td style="padding:11px 18px;color:#1e293b;font-size:13px;font-weight:500;vertical-align:middle;">{{ client_dni }}</td>
            </tr>
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:11px 18px;color:#94a3b8;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:middle;">Correo electrónico</td>
              <td style="padding:11px 18px;color:#1e293b;font-size:13px;font-weight:500;vertical-align:middle;">{{ client_email }}</td>
            </tr>
            {% if client_phone %}
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:11px 18px;color:#94a3b8;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:middle;">Teléfono</td>
              <td style="padding:11px 18px;color:#1e293b;font-size:13px;font-weight:500;vertical-align:middle;">{{ client_phone }}</td>
            </tr>
            {% endif %}
            {% if client_contacto %}
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:11px 18px;color:#94a3b8;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:middle;">Persona de contacto</td>
              <td style="padding:11px 18px;color:#1e293b;font-size:13px;font-weight:500;vertical-align:middle;">{{ client_contacto }}</td>
            </tr>
            {% endif %}
            <tr>
              <td style="padding:11px 18px;color:#94a3b8;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:middle;">Estado</td>
              <td style="padding:11px 18px;vertical-align:middle;">
                <span style="display:inline-block;background:#ffffff;border:1px solid #E2E8F0;border-radius:8px;
                             padding:4px 14px;font-size:13px;font-weight:600;color:#1e293b;
                             box-shadow:0 2px 8px rgba(0,0,0,0.05);">
                  Pendiente de verificación
                </span>
              </td>
            </tr>
          </table>

          <p style="margin:0 0 10px 0;font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:1.2px;padding-left:10px;border-left:3px solid #5CB85C;">Próximos pasos</p>

          {% if doc_type == 'RUC' %}
          <div style="border-radius:6px;padding:13px 16px;margin:0 0 12px 0;font-size:13px;line-height:1.65;
                      background:#F0FDF4;border-left:3px solid """ + _GREEN + """;color:#14532d;">
            Para realizar su primera operación, necesitamos validar su información. Envíe su ficha RUC
            desde la app, la web o respondiendo a este correo. La validación se completará en un plazo
            máximo de 10 minutos y le notificaremos cuando haya sido aprobada.
          </div>
          {% else %}
          <div style="border-radius:6px;padding:13px 16px;margin:0 0 12px 0;font-size:13px;line-height:1.65;
                      background:#F0FDF4;border-left:3px solid """ + _GREEN + """;color:#14532d;">
            Para realizar tu primera operación debemos validar tu identidad. Por favor sube tu documento de identidad
            desde la aplicación móvil. Recibirás una notificación cuando sea aprobado.
          </div>
          {% endif %}

          {% if canal == 'movil' %}
          <div style="border-radius:6px;padding:13px 16px;margin:0 0 24px 0;font-size:13px;line-height:1.65;
                      background:#F0FDF4;border-left:3px solid """ + _GREEN + """;color:#14532d;">
            <strong>Acceso web:</strong> También puedes ingresar desde <strong>www.qoricash.pe</strong>
            usando tu número de documento y la contraseña que registraste en la app.
          </div>
          {% else %}
          <div style="border-radius:6px;padding:13px 16px;margin:0 0 24px 0;font-size:13px;line-height:1.65;
                      background:#F0FDF4;border-left:3px solid """ + _GREEN + """;color:#14532d;">
            Próximamente publicaremos nuestra app para <strong>iOS</strong> y <strong>Android</strong>.
            Te notificaremos cuando esté disponible para descargar.
          </div>
          {% endif %}

          {{ shared_block }}
          <div style="height:1px;background-color:#F1F5F9;margin:20px 0;"></div>
          <p style="margin:0;font-size:12px;color:#94a3b8;">
            ¿Tienes alguna consulta? Escríbenos a
            <a href="mailto:info@qoricash.pe" style="color:""" + _GREEN + """;">info@qoricash.pe</a>
          </p>
        </td>
      </tr>"""

        html = render_template_string(
            _wrap_email_themed(body, theme),
            client_name=client_name,
            client_dni=client.dni,
            client_email=client.email,
            client_phone=client_phone,
            client_contacto=client_contacto,
            doc_type=doc_type,
            canal=canal,
            shared_block=shared_block
        )
        return _apply_theme_colors(html, theme)

    @staticmethod
    def _render_web_welcome_template(client, shared_clients=None):
        """Delegado al template unificado de bienvenida (canal web)."""
        return EmailTemplates._render_mobile_welcome_template(client, shared_clients, canal='web')

    @staticmethod
    def _render_trader_activation_template(client, trader, temporary_password=None):
        """Plantilla unificada de activación de cuenta (con o sin contraseña temporal)."""
        client_name  = client.full_name or client.razon_social or 'Cliente'
        trader_name  = trader.username if trader else 'QoriCash'
        trader_email = getattr(trader, 'email', '') or ''
        doc_number   = getattr(client, 'document_number', None) or getattr(client, 'dni', '')
        doc_type     = getattr(client, 'document_type', 'DNI')
        theme        = _get_theme(doc_type)

        body = """
      <tr>
        <td class="email-body-cell" style="padding:32px 36px;color:#334155;font-size:14px;line-height:1.65;">

          <div style="margin:0 0 20px 0;">
            {% if doc_type == 'RUC' %}
            <span style="display:inline-block;background:linear-gradient(135deg,#1A6EAD 0%,#1A3D58 100%);color:#ffffff;
                         font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.4px;
                         padding:7px 18px;border-radius:20px;box-shadow:0 4px 14px rgba(26,61,88,0.35);">
              ✓ Cuenta Activada
            </span>
            {% else %}
            <span style="display:inline-block;background:linear-gradient(135deg,#22C55E 0%,#16a34a 100%);color:#ffffff;
                         font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.4px;
                         padding:7px 18px;border-radius:20px;box-shadow:0 4px 14px rgba(34,197,94,0.35);">
              ✓ Cuenta Activada
            </span>
            {% endif %}
          </div>

          <h1 style="margin:0 0 6px 0;font-size:21px;font-weight:700;color:""" + _DARK + """;line-height:1.3;">¡Ya puedes comenzar a operar!</h1>
          <p style="margin:0 0 24px 0;color:#64748b;font-size:14px;">
            Hola <strong style="color:#1e293b;">{{ client_name }}</strong>,
            tu identidad ha sido verificada y aprobada. Tu cuenta está activa.
          </p>

          {% if doc_type == 'RUC' %}
          <table width="100%" cellspacing="0" cellpadding="0"
                 style="border-collapse:collapse;border:1px solid rgba(26,110,173,0.20);border-radius:8px;overflow:hidden;margin:0 0 24px 0;">
            <!-- Estado -->
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:11px 18px;width:160px;color:#94a3b8;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:middle;">Estado</td>
              <td style="padding:11px 18px;vertical-align:middle;">
                <span style="display:inline-block;background:linear-gradient(135deg,#1A6EAD 0%,#1A3D58 100%);border-radius:20px;padding:5px 16px;font-size:12px;font-weight:700;color:#ffffff;box-shadow:0 3px 10px rgba(26,61,88,0.3);">Activo</span>
              </td>
            </tr>
            <!-- Ejecutivo -->
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:11px 18px;color:#94a3b8;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:middle;">Ejecutivo</td>
              <td style="padding:11px 18px;color:#1e293b;font-size:13px;font-weight:600;vertical-align:middle;">{{ trader_name }}</td>
            </tr>
            {% if temporary_password %}
            <!-- Separador sección clave -->
            <tr>
              <td colspan="2" style="padding:10px 18px 6px 18px;background:rgba(26,110,173,0.05);border-top:1px solid rgba(26,110,173,0.12);">
                <p style="margin:0 0 1px 0;font-size:10px;font-weight:700;color:#1A3D58;text-transform:uppercase;letter-spacing:1.1px;">Clave de acceso corporativo</p>
                <p style="margin:0;font-size:11px;color:#94a3b8;">Para ingresar a la página web y la app móvil de QoriCash</p>
              </td>
            </tr>
            <!-- Contraseña -->
            <tr style="border-top:1px solid rgba(26,110,173,0.08);">
              <td style="padding:11px 18px;color:#1A3D58;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:middle;background:rgba(26,110,173,0.04);">Contraseña temporal</td>
              <td style="padding:11px 18px;vertical-align:middle;background:rgba(26,110,173,0.04);">
                <span style="font-family:'Courier New',Courier,monospace;font-size:15px;font-weight:700;letter-spacing:2px;color:#1A3D58;">{{ temporary_password }}</span>
              </td>
            </tr>
            <!-- Pie -->
            <tr>
              <td colspan="2" style="padding:8px 18px;background:rgba(26,110,173,0.04);border-top:1px solid rgba(26,110,173,0.08);">
                <span style="font-size:11px;color:#94a3b8;">Cópiala exactamente · Deberás cambiarla en tu primer acceso · No la compartas con nadie</span>
              </td>
            </tr>
            {% endif %}
          </table>
          {% else %}
          <table width="100%" cellspacing="0" cellpadding="0"
                 style="border-collapse:collapse;border:1px solid rgba(34,197,94,0.20);border-radius:8px;overflow:hidden;margin:0 0 24px 0;">
            <!-- Estado -->
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:11px 18px;width:160px;color:#94a3b8;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:middle;">Estado</td>
              <td style="padding:11px 18px;vertical-align:middle;">
                <span style="display:inline-block;background:linear-gradient(135deg,#22C55E 0%,#16a34a 100%);border-radius:20px;padding:5px 16px;font-size:12px;font-weight:700;color:#ffffff;box-shadow:0 3px 10px rgba(34,197,94,0.3);">Activo</span>
              </td>
            </tr>
            <!-- Ejecutivo -->
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:11px 18px;color:#94a3b8;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:middle;">Ejecutivo</td>
              <td style="padding:11px 18px;color:#1e293b;font-size:13px;font-weight:600;vertical-align:middle;">{{ trader_name }}</td>
            </tr>
            {% if temporary_password %}
            <!-- Separador sección clave -->
            <tr>
              <td colspan="2" style="padding:10px 18px 6px 18px;background:rgba(34,197,94,0.05);border-top:1px solid rgba(34,197,94,0.12);">
                <p style="margin:0 0 1px 0;font-size:10px;font-weight:700;color:#14532d;text-transform:uppercase;letter-spacing:1.1px;">Tu clave de acceso temporal</p>
                <p style="margin:0;font-size:11px;color:#94a3b8;">Para ingresar a la página web y la app móvil de QoriCash</p>
              </td>
            </tr>
            <!-- Contraseña -->
            <tr style="border-top:1px solid rgba(34,197,94,0.08);">
              <td style="padding:11px 18px;color:#14532d;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:middle;background:rgba(34,197,94,0.04);">Contraseña temporal</td>
              <td style="padding:11px 18px;vertical-align:middle;background:rgba(34,197,94,0.04);">
                <span style="font-family:'Courier New',Courier,monospace;font-size:15px;font-weight:700;letter-spacing:2px;color:#14532d;">{{ temporary_password }}</span>
              </td>
            </tr>
            <!-- Pie -->
            <tr>
              <td colspan="2" style="padding:8px 18px;background:rgba(34,197,94,0.04);border-top:1px solid rgba(34,197,94,0.08);">
                <span style="font-size:11px;color:#94a3b8;">Cópiala exactamente · Deberás cambiarla en tu primer acceso · No la compartas con nadie</span>
              </td>
            </tr>
            {% endif %}
          </table>
          {% endif %}

          <p style="margin:0 0 10px 0;font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:1.2px;padding-left:10px;border-left:3px solid #5CB85C;">¿Qué puedes hacer ahora?</p>
          <table width="100%" cellspacing="0" cellpadding="0"
                 style="border-collapse:collapse;border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;margin:0 0 24px 0;">
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:10px 18px;font-size:13px;color:#1e293b;vertical-align:top;">
                <span style="color:""" + _GREEN + """;font-weight:700;margin-right:10px;">&#10003;</span>Realizar operaciones de compra y venta de dólares
              </td>
            </tr>
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:10px 18px;font-size:13px;color:#1e293b;vertical-align:top;">
                <span style="color:""" + _GREEN + """;font-weight:700;margin-right:10px;">&#10003;</span>Acceder a tipos de cambio competitivos en tiempo real
              </td>
            </tr>
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:10px 18px;font-size:13px;color:#1e293b;vertical-align:top;">
                <span style="color:""" + _GREEN + """;font-weight:700;margin-right:10px;">&#10003;</span>Recibir atención personalizada de tu ejecutivo
              </td>
            </tr>
            <tr>
              <td style="padding:10px 18px;font-size:13px;color:#1e293b;vertical-align:top;">
                <span style="color:""" + _GREEN + """;font-weight:700;margin-right:10px;">&#10003;</span>Transferencias rápidas y seguras a tu cuenta bancaria
              </td>
            </tr>
          </table>

          <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;margin:0 0 24px 0;">
            <tr>
              <td align="center">
                {% if doc_type == 'RUC' %}
                <a href="https://qoricash.pe/empresa"
                   style="display:inline-block;background-color:""" + _GREEN + """;color:#ffffff;font-weight:700;
                          font-size:14px;padding:13px 36px;border-radius:8px;text-decoration:none;letter-spacing:0.3px;">
                  Ingresar a QoriCash
                </a>
                {% else %}
                <a href="https://qoricash.pe"
                   style="display:inline-block;background-color:""" + _GREEN + """;color:#ffffff;font-weight:700;
                          font-size:14px;padding:13px 36px;border-radius:8px;text-decoration:none;letter-spacing:0.3px;">
                  Ingresar a QoriCash
                </a>
                {% endif %}
              </td>
            </tr>
          </table>

          <div style="height:1px;background-color:#F1F5F9;margin:0 0 20px 0;"></div>
          <p style="margin:0;font-size:12px;color:#94a3b8;">
            Para tu primera operación contacta a <strong style="color:#1e293b;">{{ trader_name }}</strong>
            {% if trader_email %} en <a href="mailto:{{ trader_email }}" style="color:""" + _GREEN + """;">{{ trader_email }}</a>{% endif %}
            o escríbenos a <a href="mailto:info@qoricash.pe" style="color:""" + _GREEN + """;">info@qoricash.pe</a>.
          </p>
        </td>
      </tr>"""

        html = render_template_string(
            _wrap_email_themed(body, theme),
            client_name=client_name,
            doc_number=doc_number,
            client_email=client.email,
            trader_name=trader_name,
            trader_email=trader_email,
            temporary_password=temporary_password,
            doc_type=doc_type
        )
        return _apply_theme_colors(html, theme)

    @staticmethod
    def _render_auto_activation_template(client):
        """Plantilla para activación sin contraseña (cliente auto-registrado)"""
        client_name = client.full_name or client.razon_social or 'Cliente'
        doc_type    = getattr(client, 'document_type', 'DNI')
        theme       = _get_theme(doc_type)

        body = """
      <tr>
        <td class="email-body-cell" style="padding:32px 36px;color:#334155;font-size:14px;line-height:1.65;">

          <div style="margin:0 0 20px 0;">
            {% if doc_type == 'RUC' %}
            <span style="display:inline-block;background:linear-gradient(135deg,#1A6EAD 0%,#1A3D58 100%);color:#ffffff;
                         font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.4px;
                         padding:7px 18px;border-radius:20px;box-shadow:0 4px 14px rgba(26,61,88,0.35);">
              ✓ Cuenta Activada
            </span>
            {% else %}
            <span style="display:inline-block;background:linear-gradient(135deg,#22C55E 0%,#16a34a 100%);color:#ffffff;
                         font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.4px;
                         padding:7px 18px;border-radius:20px;box-shadow:0 4px 14px rgba(34,197,94,0.35);">
              ✓ Cuenta Activada
            </span>
            {% endif %}
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
                {% if doc_type == 'RUC' %}
                <a href="https://qoricash.pe/empresa"
                   style="display:inline-block;background-color:""" + _GREEN + """;color:#ffffff;font-weight:700;
                          font-size:14px;padding:13px 36px;border-radius:8px;text-decoration:none;letter-spacing:0.3px;">
                  Ingresar a QoriCash
                </a>
                {% else %}
                <a href="https://qoricash.pe"
                   style="display:inline-block;background-color:""" + _GREEN + """;color:#ffffff;font-weight:700;
                          font-size:14px;padding:13px 36px;border-radius:8px;text-decoration:none;letter-spacing:0.3px;">
                  Ingresar a QoriCash
                </a>
                {% endif %}
              </td>
            </tr>
          </table>

          <div style="border-radius:6px;padding:13px 16px;margin:0 0 24px 0;font-size:13px;line-height:1.65;
                      background:#F0FDF4;border-left:3px solid """ + _GREEN + """;color:#14532d;">
            {% if doc_type == 'RUC' %}
            Ingresa desde <strong>www.qoricash.pe/empresa</strong> usando tu RUC y la contraseña que definiste al registrarte.
            {% else %}
            Ingresa desde <strong>www.qoricash.pe</strong> o nuestra app móvil usando tu número de documento
            y la contraseña que definiste al registrarte.
            {% endif %}
          </div>

          <div style="height:1px;background-color:#F1F5F9;margin:20px 0;"></div>
          <p style="margin:0;font-size:12px;color:#94a3b8;">
            ¿Tienes alguna consulta? Escríbenos a
            <a href="mailto:info@qoricash.pe" style="color:""" + _GREEN + """;">info@qoricash.pe</a>
          </p>
        </td>
      </tr>"""

        html = render_template_string(
            _wrap_email_themed(body, theme),
            client_name=client_name,
            client_dni=client.dni,
            doc_type=doc_type
        )
        return _apply_theme_colors(html, theme)
