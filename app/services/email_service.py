"""
Servicio de envío de correos electrónicos para QoriCash Trading V2
"""
import re
import time
import logging
import eventlet
from flask import render_template_string
from flask_mail import Message
from app.extensions import mail
from app.models import User

logger = logging.getLogger(__name__)


# ============================================
# CONSTANTES DE MARCA
# ============================================
_LOGO_URL = 'https://app.qoricash.pe/static/images/logo-email.png'
_GREEN    = '#5CB85C'
_DARK     = '#0D1B2A'
_SBS_TAG  = 'Regulada por la SBS &nbsp;&middot;&nbsp; Res. N.&ordm; 00313-2026'

# ── TEMA POR TIPO DE CLIENTE ──────────────────────────────────────
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

_HEADER_BLOCK = f"""
      <tr>
        <td style="padding:20px 36px 18px;border-bottom:1px solid #E2E8F0;">
          <table width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr>
              <td style="vertical-align:middle;">
                <table cellpadding="0" cellspacing="0" border="0">
                  <tr>
                    <td style="vertical-align:middle;padding-right:12px;">
                      <img src="{_LOGO_URL}" alt="QoriCash" class="email-logo" style="height:44px;width:auto;display:block;">
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

_EMAIL_CSS = """
    @media only screen and (max-width: 620px) {
        .email-outer-wrap { padding: 8px 0 !important; }
        .email-body-cell  { padding: 22px 16px !important; }
        .email-footer-cell{ padding: 16px !important; }
        /* Cajas de métricas: reducir padding en móvil pero mantener horizontal */
        .metric-cell   { padding: 10px 4px !important; }
        /* Tabla de cuentas bancarias: reducir texto, ocultar columnas secundarias */
        .bank-td   { font-size:10px !important; padding:6px 6px !important; }
        .hide-mob  { display:none !important; }
        /* Filas detalle (Código/Tipo/Estado/Fecha): ajustar ancho de etiqueta */
        .ops-label { width:38% !important; font-size:11px !important; }
        /* Encabezado email: reducir logo */
        .email-logo { height:32px !important; }
    }
"""


def _wrap_email_themed_svc(body_html: str, theme: str = 'persona') -> str:
    """Wrapper temático con banner persona o empresa según tipo de cliente."""
    t = _THEMES[theme]
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>{_EMAIL_CSS}</style>
</head>
<body style="margin:0;padding:0;background:#f5f7fa;font-family:Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" class="email-outer-wrap" style="background:#f5f7fa;padding:28px 16px;">
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

def _wrap_email_svc(body_html: str) -> str:
    """Wrapper base de email QoriCash para email_service."""
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>{_EMAIL_CSS}</style>
</head>
<body style="margin:0;padding:0;background-color:#f5f7fa;font-family:Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" class="email-outer-wrap" style="background-color:#f5f7fa;padding:28px 16px;">
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


class EmailService:
    """Servicio para envío de correos electrónicos"""

    @staticmethod
    def _parse_client_emails(email_str):
        """
        Parsea un campo de email que puede contener múltiples direcciones
        separadas por ';' y retorna una lista limpia de emails válidos.
        Ej: "a@x.com; b@x.com" → ["a@x.com", "b@x.com"]
        """
        if not email_str:
            return []
        return [e.strip() for e in email_str.split(';') if e.strip() and '@' in e]

    @staticmethod
    def build_email_html(title: str, body_html: str, subtitle: str = '') -> str:
        """
        Template base corporativo para todos los correos de QoriCash.

        Args:
            title:     Título principal del correo
            body_html: Contenido HTML del cuerpo del correo
            subtitle:  Texto secundario opcional (ej: número de operación/reclamo)
        """
        subtitle_block = (
            f'<p style="margin:4px 0 20px;font-size:13px;color:#64748b;">{subtitle}</p>'
        ) if subtitle else '<div style="margin-bottom:20px;"></div>'

        body = f"""
      <tr>
        <td class="email-body-cell" style="padding:32px 36px;color:#334155;font-size:14px;line-height:1.65;">
          <h2 style="margin:0 0 0;font-size:20px;font-weight:700;color:{_DARK};">{title}</h2>
          {subtitle_block}
          {body_html}
        </td>
      </tr>"""
        return _wrap_email_svc(body)

    @staticmethod
    def _html_to_text(html: str) -> str:
        """Genera plain-text desde HTML para el fallback multipart del correo."""
        text = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
        text = re.sub(r'</p>', '\n\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</tr>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', text)
        for ent, rep in [('&nbsp;', ' '), ('&mdash;', '—'), ('&middot;', '·'),
                         ('&copy;', '©'), ('&ordm;', 'º'), ('&amp;', '&'),
                         ('&lt;', '<'), ('&gt;', '>')]:
            text = text.replace(ent, rep)
        text = re.sub(r'&[a-z]+;', '', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    @staticmethod
    def _send_async(msg, timeout=15, max_retries=2):
        """
        Envía un email de forma asíncrona via Gmail/Google Workspace (Flask-Mail).
        Reintenta hasta max_retries veces con backoff exponencial.
        Agrega plain-text automáticamente si no se proporcionó.
        """
        from flask import current_app
        app = current_app._get_current_object()

        if not msg.body and msg.html:
            msg.body = EmailService._html_to_text(msg.html)

        def _send():
            with app.app_context():
                for attempt in range(1, max_retries + 2):
                    try:
                        with eventlet.Timeout(timeout):
                            mail.send(msg)
                        logger.info(f'[EMAIL] Enviado OK to={msg.recipients}')
                        return
                    except eventlet.Timeout:
                        logger.warning(f'[EMAIL] Timeout ({timeout}s) intento {attempt} to={msg.recipients}')
                    except Exception as e:
                        logger.error(f'[EMAIL] Error intento {attempt}: {str(e)}')

                    if attempt <= max_retries:
                        wait = 2 ** attempt
                        logger.warning(f'[EMAIL] Reintento {attempt}/{max_retries} en {wait}s')
                        time.sleep(wait)
                    else:
                        logger.error(f'[EMAIL] Todos los intentos fallaron to={msg.recipients}')

        eventlet.spawn_n(_send)

    @staticmethod
    def get_recipients_for_new_operation(operation):
        """
        Obtener lista de destinatarios para una nueva operación

        Returns:
            tuple: (to, cc, bcc) donde:
                - to: Cliente (destinatario principal)
                - cc: trader que creó la operación + gerencia@qoricash.pe
                - bcc: vacío
        """
        to = EmailService._parse_client_emails(operation.client.email) if operation.client else []
        seen = set(to)
        cc = []
        trader_email = operation.user.email if operation.user and getattr(operation.user, 'email', None) else None
        if trader_email and trader_email not in seen:
            cc.append(trader_email)
            seen.add(trader_email)
        if 'gerencia@qoricash.pe' not in seen:
            cc.append('gerencia@qoricash.pe')
        bcc = []
        return to, cc, bcc

    @staticmethod
    def get_recipients_for_completed_operation(operation):
        """
        Obtener lista de destinatarios para operación completada

        Returns:
            tuple: (to, cc, bcc) donde:
                - to: Cliente
                - cc: trader que creó la operación + gerencia@qoricash.pe
                - bcc: vacío
        """
        to = EmailService._parse_client_emails(operation.client.email) if operation.client else []
        seen = set(to)
        cc = []
        trader_email = operation.user.email if operation.user and getattr(operation.user, 'email', None) else None
        if trader_email and trader_email not in seen:
            cc.append(trader_email)
            seen.add(trader_email)
        if 'gerencia@qoricash.pe' not in seen:
            cc.append('gerencia@qoricash.pe')
        bcc = []
        return to, cc, bcc

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
            # Idempotencia: evitar envío duplicado si ya se envió para esta operación
            if getattr(operation, 'new_operation_email_sent', False):
                logger.warning(f'Email de nueva operación ya enviado para {operation.operation_id}, ignorando duplicado')
                return False, 'Email ya enviado anteriormente'

            to, cc, bcc = EmailService.get_recipients_for_new_operation(operation)

            # Validar que haya al menos un destinatario
            if not to and not cc and not bcc:
                logger.warning(f'No hay destinatarios para la operación {operation.operation_id}')
                return False, 'No hay destinatarios configurados'

            # Asunto
            subject = f'Nueva Operación #{operation.operation_id} - QoriCash Trading'

            # Contenido HTML
            html_body = EmailService._render_new_operation_template(operation)

            # Reply-To: trader dueño de la operación (para que el cliente pueda responder directamente al trader)
            trader_email = operation.user.email if operation.user and operation.user.email else None

            # Crear mensaje — sender usa MAIL_DEFAULT_SENDER para no romper autenticación SMTP
            msg = Message(
                subject=subject,
                recipients=to,
                cc=cc,
                bcc=bcc,
                html=html_body
            )
            if trader_email:
                msg.reply_to = trader_email

            # Marcar como enviado ANTES del spawn para evitar race condition
            try:
                from app.extensions import db
                operation.new_operation_email_sent = True
                db.session.commit()
            except Exception:
                pass  # No bloquear el envío si falla el flag

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
            logger.info(f'[EMAIL] Iniciando envio de email completado para operacion {operation.operation_id}')

            to, cc, bcc = EmailService.get_recipients_for_completed_operation(operation)

            logger.info(f'[EMAIL] Destinatarios - TO: {to}, CC: {cc}')

            if not to and not cc:
                logger.warning(f'No hay destinatarios para la operación completada {operation.operation_id}')
                return False, 'No hay destinatarios configurados'

            # Reply-To: trader dueño de la operación
            trader_email = operation.user.email if operation.user and operation.user.email else None

            subject = f'Operación Completada #{operation.operation_id} - QoriCash Trading'

            logger.info(f'[EMAIL] Generando plantilla HTML')
            html_body = EmailService._render_completed_operation_template(operation)

            logger.info(f'[EMAIL] Creando mensaje Flask-Mail')
            msg = Message(
                subject=subject,
                recipients=to,
                cc=cc if cc else None,
                html=html_body
            )
            if trader_email:
                msg.reply_to = trader_email

            # Adjuntar comprobante electrónico si existe
            if operation.invoices and len(operation.invoices) > 0:
                invoice = operation.invoices[0]
                if invoice.nubefact_enlace_pdf:
                    try:
                        logger.info(f'[EMAIL] Descargando comprobante PDF desde: {invoice.nubefact_enlace_pdf}')
                        import requests
                        pdf_response = requests.get(invoice.nubefact_enlace_pdf, timeout=10)
                        if pdf_response.status_code == 200:
                            filename = f'{invoice.invoice_number}.pdf' if invoice.invoice_number else 'comprobante.pdf'
                            msg.attach(filename, 'application/pdf', pdf_response.content, 'attachment')
                            logger.info(f'[EMAIL] Comprobante PDF adjuntado: {filename}')
                        else:
                            logger.warning(f'[EMAIL] Error al descargar PDF: HTTP {pdf_response.status_code}')
                    except Exception as e:
                        logger.error(f'[EMAIL] Error al adjuntar comprobante: {str(e)}')
                else:
                    logger.info(f'[EMAIL] Invoice existe pero no tiene enlace PDF')
            else:
                logger.info(f'[EMAIL] Operación sin comprobante electrónico')

            logger.info(f'[EMAIL] Programando envío desde {trader_email} a TO: {to}, CC: {cc}')
            EmailService._send_async(msg, timeout=15)

            logger.info(f'[EMAIL] Email de operacion completada programado: {operation.operation_id}')
            return True, 'Email programado para envío'

        except Exception as e:
            logger.error(f'[EMAIL] ERROR al enviar email de operacion completada {operation.operation_id}: {str(e)}')
            logger.exception(e)
            return False, f'Error al enviar email: {str(e)}'

    @staticmethod
    def _render_new_operation_template(operation):
        """Plantilla HTML para nueva operación — rediseño completo."""
        import json as _json
        _client = getattr(operation, 'client', None)
        _doc    = getattr(_client, 'document_type', 'DNI')
        _theme  = _get_theme(_doc)
        is_ruc  = (_doc == 'RUC')

        # Cuentas bancarias del cliente (para sección "¿Dónde recibirás tu pago?")
        client_accounts = []
        if _client and hasattr(_client, 'bank_accounts') and _client.bank_accounts:
            try:
                ba = _client.bank_accounts
                ba = _json.loads(ba) if isinstance(ba, str) else ba
                client_accounts = ba if isinstance(ba, list) else []
            except Exception:
                pass

        from app.config.bank_accounts import get_accounts_for_currency, QORICASH_TITULAR, QORICASH_RUC
        usd_accounts = get_accounts_for_currency('USD')
        pen_accounts = get_accounts_for_currency('PEN')

        body = """
      <tr>
        <td class="email-body-cell" style="padding:32px 36px;color:#334155;font-size:14px;line-height:1.65;">

          <!-- ── BADGE + TIPO ─────────────────────────────── -->
          <div style="margin:0 0 20px 0;">
            {% if is_ruc %}
            <span style="display:inline-block;background:linear-gradient(135deg,#1A6EAD 0%,#1A3D58 100%);color:#ffffff;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.4px;padding:6px 16px;border-radius:20px;box-shadow:0 4px 12px rgba(26,61,88,0.30);">Nueva Operación</span>
            {% else %}
            <span style="display:inline-block;background:linear-gradient(135deg,#22C55E 0%,#16a34a 100%);color:#ffffff;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.4px;padding:6px 16px;border-radius:20px;box-shadow:0 4px 12px rgba(34,197,94,0.30);">Nueva Operación</span>
            {% endif %}
            </div>

          <!-- ── TÍTULO ────────────────────────────────────── -->
          <h1 style="margin:0 0 6px 0;font-size:22px;font-weight:700;color:#0D1B2A;line-height:1.3;">
            {% if is_ruc %}Su operación ha sido registrada{% else %}Tu operación ha sido registrada{% endif %}
          </h1>
          <p style="margin:0 0 24px 0;color:#64748b;font-size:14px;">
            {% if is_ruc %}Estimado(a){% else %}Hola{% endif %}
            <strong style="color:#1e293b;">{{ operation.client.full_name or operation.client.razon_social }}</strong>,
            {% if is_ruc %}le confirmamos que hemos generado una nueva operación:{% else %}te confirmamos que hemos generado una nueva operación:{% endif %}
          </p>

          <!-- ── CARD PRINCIPAL: Estado + Importe ───────────── -->
          <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;border:1px solid #E2E8F0;border-radius:12px;overflow:hidden;margin:0 0 8px 0;">
            <!-- Fila Estado + Fecha -->
            <tr>
              <td style="padding:11px 16px;background:#F8FAFC;border-bottom:1px solid #E2E8F0;">
                <table width="100%" cellspacing="0" cellpadding="0">
                  <tr>
                    <td style="font-size:11px;color:#64748b;">
                      Estado &nbsp;
                      <span style="display:inline-block;background:#FEF3C7;color:#92400E;font-size:10px;font-weight:700;padding:3px 10px;border-radius:20px;letter-spacing:0.3px;">{{ operation.status }}</span>
                    </td>
                    <td style="font-size:11px;color:#64748b;text-align:right;">
                      Fecha &nbsp;<strong style="color:#1e293b;">{{ operation.created_at.strftime('%d/%m/%Y %H:%M') }}</strong>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <!-- Inner themed card: Código + Tipo + importes -->
            <tr>
              <td style="padding:14px 16px;">
                {% if is_ruc %}
                <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;background:#F0FDF4;border:1px solid rgba(26,61,88,0.18);border-radius:8px;overflow:hidden;">
                {% else %}
                <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;background:#F0FDF4;border:1px solid rgba(34,197,94,0.28);border-radius:8px;overflow:hidden;">
                {% endif %}
                  <!-- Código + Tipo -->
                  <tr>
                    <td style="padding:10px 14px;">
                      <table width="100%" cellspacing="0" cellpadding="0">
                        <tr>
                          <td style="text-align:left;padding:0 6px;font-size:11px;color:#64748b;">
                            Código &nbsp;<strong style="color:#1e293b;font-family:'Courier New',monospace;letter-spacing:0.5px;">{{ operation.operation_id }}</strong>
                          </td>
                          <td width="80" style="padding:0 4px;"></td>
                          <td style="text-align:right;padding:0 6px;font-size:11px;color:#64748b;">
                            Tipo &nbsp;
                            {% if operation.operation_type == 'Compra' %}
                            <strong style="color:#15803D;">COMPRA USD</strong>
                            {% else %}
                            <strong style="color:#1D4ED8;">VENTA USD</strong>
                            {% endif %}
                          </td>
                        </tr>
                      </table>
                    </td>
                  </tr>
                  <!-- Separador sutil -->
                  <tr>
                    <td>
                      {% if is_ruc %}
                      <div style="height:1px;background:rgba(26,61,88,0.12);margin:0 14px;"></div>
                      {% else %}
                      <div style="height:1px;background:rgba(34,197,94,0.20);margin:0 14px;"></div>
                      {% endif %}
                    </td>
                  </tr>
                  <!-- Importes: Monto USD | Tipo de Cambio | Monto PEN -->
                  <tr>
                    <td style="padding:14px 14px 16px 14px;">
                      <table width="100%" cellspacing="0" cellpadding="0">
                        <tr>
                          <td style="text-align:center;vertical-align:top;padding:0 6px;">
                            <p style="margin:0 0 5px 0;font-size:9px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:1px;">Monto USD</p>
                            <p style="margin:0;font-size:20px;font-weight:800;color:#0D1B2A;white-space:nowrap;">$ {{ "{:,.2f}".format(operation.amount_usd) }}</p>
                          </td>
                          <td width="80" style="text-align:center;vertical-align:middle;padding:0 4px;">
                            <p style="margin:0 0 5px 0;font-size:9px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:1px;">T.C.</p>
                            <p style="margin:0;font-size:15px;font-weight:700;color:#5CB85C;white-space:nowrap;">{{ "%.4f"|format(operation.exchange_rate) }}</p>
                          </td>
                          <td style="text-align:center;vertical-align:top;padding:0 6px;">
                            <p style="margin:0 0 5px 0;font-size:9px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:1px;">Monto PEN</p>
                            <p style="margin:0;font-size:20px;font-weight:800;color:#0D1B2A;white-space:nowrap;">S/ {{ "{:,.2f}".format(operation.amount_pen) }}</p>
                          </td>
                        </tr>
                      </table>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
          </table>
          <!-- ── CUENTAS QORICASH (donde el cliente transfiere) ── -->
          <p style="margin:0 0 3px 0;font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:1.2px;padding-left:10px;border-left:3px solid #5CB85C;">
            {% if operation.operation_type == 'Compra' %}¿A dónde transfiero mis dólares?{% else %}¿A dónde transfiero mis soles?{% endif %}
          </p>
          <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;margin:0 0 24px 0;">
            <tr style="background:#F8FAFC;border-bottom:1px solid #E2E8F0;">
              <td colspan="4" style="padding:9px 14px;font-size:11px;color:#64748b;text-align:justify;">
                Titular: <strong style="color:#1e293b;">{{ qoricash_titular }}</strong> &nbsp;&bull;&nbsp; RUC {{ qoricash_ruc }} &nbsp;&bull;&nbsp;
                {% if operation.operation_type == 'Compra' %}Transfiera en <strong style="color:#1e293b;">USD</strong>{% else %}Transfiera en <strong style="color:#1e293b;">PEN</strong>{% endif %}
              </td>
            </tr>
            <tr style="background:#0D1B2A;">
              <td style="padding:7px 12px;color:#94a3b8;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;">Banco</td>
              <td style="padding:7px 12px;color:#94a3b8;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;">Tipo de cuenta</td>
              <td style="padding:7px 12px;color:#94a3b8;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;">N° Cuenta</td>
              <td style="padding:7px 12px;color:#94a3b8;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;">CCI</td>
            </tr>
            {% if operation.operation_type == 'Compra' %}
            {% for acc in usd_accounts %}
            <tr style="border-top:1px solid #F1F5F9;">
              <td style="padding:9px 12px;font-size:12px;font-weight:700;color:#1e293b;white-space:nowrap;">{{ acc.banco }}</td>
              <td style="padding:9px 12px;font-size:12px;color:#64748b;">{{ acc.tipo }}</td>
              <td style="padding:9px 12px;font-family:'Courier New',monospace;font-size:11px;font-weight:600;color:#0D1B2A;">{{ acc.numero }}</td>
              <td style="padding:9px 12px;font-family:'Courier New',monospace;font-size:11px;color:#64748b;">{{ acc.cci }}</td>
            </tr>
            {% endfor %}
            {% else %}
            {% for acc in pen_accounts %}
            <tr style="border-top:1px solid #F1F5F9;">
              <td style="padding:9px 12px;font-size:12px;font-weight:700;color:#1e293b;white-space:nowrap;">{{ acc.banco }}</td>
              <td style="padding:9px 12px;font-size:12px;color:#64748b;">{{ acc.tipo }}</td>
              <td style="padding:9px 12px;font-family:'Courier New',monospace;font-size:11px;font-weight:600;color:#0D1B2A;">{{ acc.numero }}</td>
              <td style="padding:9px 12px;font-family:'Courier New',monospace;font-size:11px;color:#64748b;">{{ acc.cci }}</td>
            </tr>
            {% endfor %}
            {% endif %}
          </table>

          <!-- ── CUENTAS DEL CLIENTE (donde recibirá el pago) ── -->
          <p style="margin:0 0 3px 0;font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:1.2px;padding-left:10px;border-left:3px solid #5CB85C;">
            {% if is_ruc %}¿Dónde recibirá su pago?{% else %}¿Dónde recibirás tu pago?{% endif %}
          </p>
          <p style="margin:0 0 10px 0;font-size:11px;color:#94a3b8;padding-left:13px;">
            Qoricash acreditará en la siguiente cuenta
          </p>
          {% if client_accounts %}
          <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;margin:0 0 24px 0;">
            <tr style="background:#0D1B2A;">
              <td style="padding:7px 14px;color:#94a3b8;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;">Banco</td>
              <td style="padding:7px 14px;color:#94a3b8;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;">Tipo de cuenta</td>
              <td style="padding:7px 14px;color:#94a3b8;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;">Titular</td>
              <td style="padding:7px 14px;color:#94a3b8;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;">N° Cuenta</td>
              <td style="padding:7px 14px;color:#94a3b8;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;">Moneda</td>
            </tr>
            {% for acc in client_accounts %}
            {% if (operation.operation_type == 'Compra' and acc.get('currency') == 'PEN') or (operation.operation_type != 'Compra' and acc.get('currency') == 'USD') %}
            <tr style="border-top:1px solid #F1F5F9;">
              <td style="padding:10px 14px;font-size:12px;font-weight:700;color:#1e293b;white-space:nowrap;">{{ acc.bank_name }}</td>
              <td style="padding:10px 14px;font-size:12px;color:#64748b;">{{ acc.get('account_type', 'Cuenta Bancaria') }}</td>
              <td style="padding:10px 14px;font-size:12px;color:#1e293b;">{{ operation.client.full_name or operation.client.razon_social }}</td>
              <td style="padding:10px 14px;font-family:'Courier New',monospace;font-size:11px;font-weight:600;color:#0D1B2A;">{{ acc.account_number }}</td>
              <td style="padding:10px 14px;font-size:12px;color:#64748b;">{{ acc.get('currency', '') }}</td>
            </tr>
            {% endif %}
            {% endfor %}
          </table>
          {% else %}
          <div style="border-radius:6px;padding:12px 16px;margin:0 0 24px 0;background:#F8FAFC;border:1px solid #E2E8F0;font-size:12px;color:#94a3b8;text-align:center;">
            {% if is_ruc %}No tiene cuentas bancarias registradas. Su ejecutivo le contactará para coordinar el pago.{% else %}No tienes cuentas bancarias registradas. Tu ejecutivo te contactará para coordinar el pago.{% endif %}
          </div>
          {% endif %}

          <!-- ── OBSERVACIONES ──────────────────────────────── -->
          {% if operation.notes %}
          <p style="margin:0 0 6px 0;font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:1.2px;padding-left:10px;border-left:3px solid #5CB85C;">Observaciones</p>
          <div style="border-radius:6px;padding:12px 16px;margin:0 0 24px 0;background:#FFFBEB;border:1px solid #FDE68A;font-size:13px;color:#78350f;line-height:1.6;">
            {{ operation.notes }}
          </div>
          {% endif %}

          <!-- ── FOOTER ─────────────────────────────────────── -->
          <div style="height:1px;background-color:#F1F5F9;margin:0 0 16px 0;"></div>
          <p style="margin:0 0 4px 0;font-size:12px;color:#64748b;">
            {% if is_ruc %}Nuestro equipo procesará su operación a la brevedad. Ante cualquier consulta, responda este correo o contacte a su ejecutivo.{% else %}Nuestro equipo procesará tu operación a la brevedad. Ante cualquier consulta, responde este correo o contacta a tu ejecutivo.{% endif %}
          </p>
          <p style="margin:0;font-size:11px;color:#94a3b8;">Este es un correo automático generado por Qoricash.</p>

        </td>
      </tr>"""

        html = render_template_string(
            _wrap_email_themed_svc(body, _theme),
            operation=operation,
            is_ruc=is_ruc,
            usd_accounts=usd_accounts,
            pen_accounts=pen_accounts,
            qoricash_titular=QORICASH_TITULAR,
            qoricash_ruc=QORICASH_RUC,
            client_accounts=client_accounts,
        )
        return _apply_theme_colors(html, _theme)

    @staticmethod
    def _render_completed_operation_template(operation):
        """Renderizar plantilla HTML para operación completada"""
        _doc = getattr(getattr(operation, 'client', None), 'document_type', 'DNI')
        _theme = _get_theme(_doc)
        body = """
      <tr>
        <td class="email-body-cell" style="padding:32px 36px;color:#334155;font-size:14px;line-height:1.65;">

          <div style="margin:0 0 16px 0;">
            {% if operation.client.document_type == 'RUC' %}
            <span style="display:inline-block;background:linear-gradient(135deg,#1A6EAD 0%,#1A3D58 100%);color:#ffffff;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.4px;padding:6px 16px;border-radius:20px;box-shadow:0 4px 14px rgba(26,61,88,0.35);">✓ Operación Completada</span>
            {% else %}
            <span style="display:inline-block;background:linear-gradient(135deg,#22C55E 0%,#16a34a 100%);color:#ffffff;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.4px;padding:6px 16px;border-radius:20px;box-shadow:0 4px 14px rgba(34,197,94,0.35);">✓ Operación Completada</span>
            {% endif %}
          </div>

          <h1 style="margin:0 0 6px 0;font-size:21px;font-weight:700;color:#0D1B2A;line-height:1.3;">Su operación fue procesada con éxito</h1>
          <p style="margin:0 0 24px 0;color:#64748b;font-size:14px;">Estimado(a) <strong style="color:#1e293b;">{{ operation.client.full_name or operation.client.razon_social }}</strong>, a continuación el detalle de su operación completada.</p>

          <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;margin:0 0 24px 0;">
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td class="ops-label" style="padding:11px 14px;width:70px;color:#94a3b8;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:middle;">Código</td>
              <td style="padding:11px 14px;color:#0D1B2A;font-size:14px;font-weight:700;vertical-align:middle;border-right:1px solid #F1F5F9;">{{ operation.operation_id }}</td>
              <td class="ops-label" style="padding:11px 14px;width:50px;color:#94a3b8;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:middle;">Tipo</td>
              <td style="padding:11px 14px;vertical-align:middle;">
                {% if operation.operation_type == 'Compra' %}
                  <span style="display:inline-block;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700;background:#DCFCE7;color:#15803D;letter-spacing:0.3px;white-space:nowrap;">COMPRA USD</span>
                {% else %}
                  <span style="display:inline-block;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700;background:#DBEAFE;color:#1D4ED8;letter-spacing:0.3px;white-space:nowrap;">VENTA USD</span>
                {% endif %}
              </td>
            </tr>
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td colspan="4" style="padding:12px 14px;">
                <table width="100%" cellspacing="0" cellpadding="0">
                  <tr>
                    <td class="metric-cell" style="text-align:center;padding:13px 8px;background:#F8FAFC;border:1px solid #E2E8F0;border-radius:6px;border-top:3px solid #5CB85C;">
                      <div style="font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Monto USD</div>
                      <div style="font-size:17px;font-weight:800;color:#5CB85C;">$ {{ "{:,.2f}".format(operation.amount_usd) }}</div>
                    </td>
                    <td class="metric-spacer" width="8">&nbsp;</td>
                    <td class="metric-cell" style="text-align:center;padding:13px 8px;background:#F8FAFC;border:1px solid #E2E8F0;border-radius:6px;border-top:3px solid #5CB85C;">
                      <div style="font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Tipo de Cambio</div>
                      <div style="font-size:15px;font-weight:700;color:#1e293b;">{{ "%.4f"|format(operation.exchange_rate) }}</div>
                    </td>
                    <td class="metric-spacer" width="8">&nbsp;</td>
                    <td class="metric-cell" style="text-align:center;padding:13px 8px;background:#F8FAFC;border:1px solid #E2E8F0;border-radius:6px;border-top:3px solid #5CB85C;">
                      <div style="font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Monto PEN</div>
                      <div style="font-size:17px;font-weight:800;color:#5CB85C;">S/ {{ "{:,.2f}".format(operation.amount_pen) }}</div>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td class="ops-label" style="padding:11px 14px;width:70px;color:#94a3b8;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:middle;">Creación</td>
              <td style="padding:11px 14px;color:#1e293b;font-size:13px;font-weight:500;vertical-align:middle;border-right:1px solid #F1F5F9;">{{ operation.created_at.strftime('%d/%m/%Y %H:%M') }}</td>
              <td class="ops-label" style="padding:11px 14px;width:70px;color:#94a3b8;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:middle;">Completado</td>
              <td style="padding:11px 14px;color:#1e293b;font-size:13px;font-weight:600;vertical-align:middle;">{{ operation.completed_at.strftime('%d/%m/%Y %H:%M') if operation.completed_at else '-' }}</td>
            </tr>
          </table>

          {% if operation.operator_proofs and operation.operator_proofs|length > 0 %}
          <p style="margin:0 0 10px 0;font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:1.2px;padding-left:10px;border-left:3px solid #5CB85C;">Comprobante(s)</p>
          <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;margin:0 0 24px 0;">
            {% for proof in operation.operator_proofs %}
            <tr style="{% if not loop.last %}border-bottom:1px solid #F1F5F9;{% endif %}">
              <td style="padding:12px 18px;vertical-align:middle;">
                <a href="{{ proof.comprobante_url if proof.comprobante_url else proof }}"
                   target="_blank"
                   style="display:inline-block;background:#0D1B2A;color:#5CB85C;border:1.5px solid #5CB85C;padding:8px 20px;border-radius:6px;text-decoration:none;font-size:13px;font-weight:600;">
                  Ver comprobante{% if operation.operator_proofs|length > 1 %} {{ loop.index }}{% endif %}
                </a>
                {% if proof.comentario %}
                <p style="margin:6px 0 0 0;font-size:13px;color:#64748b;font-style:italic;">{{ proof.comentario }}</p>
                {% endif %}
              </td>
            </tr>
            {% endfor %}
          </table>
          {% endif %}

          {% if operation.invoices and operation.invoices|length > 0 %}
          {% set invoice = operation.invoices[0] %}
          {% if invoice.nubefact_enlace_pdf or invoice.invoice_number %}
          <div style="border-radius:6px;padding:13px 16px;margin:0 0 20px 0;font-size:13px;line-height:1.65;background:#F0FDF4;border-left:3px solid #5CB85C;color:#14532d;">
            <strong>Comprobante electrónico adjunto:</strong>
            {% if invoice.invoice_number %}{{ invoice.invoice_number }}{% endif %}
            {% if invoice.nubefact_enlace_pdf %}
            &nbsp;&mdash;&nbsp;
            <a href="{{ invoice.nubefact_enlace_pdf }}" target="_blank" style="color:#5CB85C;text-decoration:none;font-weight:600;">Descargar PDF</a>
            {% endif %}
          </div>
          {% endif %}
          {% endif %}

          <div style="height:1px;background-color:#F1F5F9;margin:20px 0;"></div>
          <p style="margin:0 0 8px 0;font-size:13px;color:#334155;">Gracias por confiar en <strong>QoriCash</strong> para sus operaciones cambiarias.</p>
          <p style="margin:0;font-size:12px;color:#94a3b8;">¿Consultas? Responda este correo o contacte a su asesor comercial.</p>

        </td>
      </tr>"""
        html = render_template_string(_wrap_email_themed_svc(body, _theme), operation=operation)
        return _apply_theme_colors(html, _theme)

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
            to = EmailService._parse_client_emails(operation.client.email) if operation.client else []
            seen = set(to)
            cc = []
            trader_email = operation.user.email if operation.user and getattr(operation.user, 'email', None) else None
            if trader_email and trader_email not in seen:
                cc.append(trader_email)
                seen.add(trader_email)
            if 'gerencia@qoricash.pe' not in seen:
                cc.append('gerencia@qoricash.pe')

            if not to:
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
            if trader_email:
                msg.reply_to = trader_email

            EmailService._send_async(msg, timeout=15)
            logger.info(f'Email de cancelación programado para operación {operation.operation_id}')
            return True, 'Email programado para envío'

        except Exception as e:
            logger.error(f'Error al enviar email de cancelación {operation.operation_id}: {str(e)}')
            return False, f'Error al enviar email: {str(e)}'

    @staticmethod
    def send_amount_modified_operation_email(operation, old_amount_usd, old_amount_pen):
        """
        Enviar correo de notificación cuando el importe de una operación es modificado.

        Args:
            operation: Objeto Operation con los nuevos montos
            old_amount_usd: Monto USD anterior (float)
            old_amount_pen: Monto PEN anterior (float)

        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            to = EmailService._parse_client_emails(operation.client.email) if operation.client else []
            seen = set(to)
            cc = []
            trader_email = operation.user.email if operation.user and getattr(operation.user, 'email', None) else None
            if trader_email and trader_email not in seen:
                cc.append(trader_email)
                seen.add(trader_email)
            if 'gerencia@qoricash.pe' not in seen:
                cc.append('gerencia@qoricash.pe')

            if not to:
                logger.warning(f'No hay destinatarios para correo de modificación de monto {operation.operation_id}')
                return False, 'No hay destinatarios configurados'

            subject = f'Actualización de Importe — Operación {operation.operation_id} | QoriCash'
            html_body = EmailService._render_amount_modified_template(operation, old_amount_usd, old_amount_pen)

            msg = Message(
                subject=subject,
                recipients=to,
                cc=cc,
                html=html_body
            )
            if trader_email:
                msg.reply_to = trader_email

            EmailService._send_async(msg, timeout=15)
            logger.info(f'Email de modificación de monto programado para operación {operation.operation_id}')
            return True, 'Email programado para envío'

        except Exception as e:
            logger.error(f'Error al enviar email de modificación de monto {operation.operation_id}: {str(e)}')
            return False, f'Error al enviar email: {str(e)}'

    @staticmethod
    def _render_amount_modified_template(operation, old_amount_usd, old_amount_pen):
        """Renderizar plantilla HTML para notificación de modificación de importe"""
        import json as _json
        _client = getattr(operation, 'client', None)
        _doc    = getattr(_client, 'document_type', 'DNI')
        _theme  = _get_theme(_doc)
        is_ruc  = (_doc == 'RUC')
        client_accounts = []
        if _client and hasattr(_client, 'bank_accounts') and _client.bank_accounts:
            try:
                ba = _client.bank_accounts
                ba = _json.loads(ba) if isinstance(ba, str) else ba
                client_accounts = ba if isinstance(ba, list) else []
            except Exception:
                pass
        body = """
      <tr>
        <td class="email-body-cell" style="padding:32px 36px;color:#334155;font-size:14px;line-height:1.65;">

          <div style="margin:0 0 16px 0;">
            <span style="display:inline-block;background:#FFFBEB;color:#F59E0B;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.4px;padding:4px 10px;border-radius:4px;">Actualización de Importe</span>
          </div>

          <h1 style="margin:0 0 6px 0;font-size:21px;font-weight:700;color:#0D1B2A;line-height:1.3;">Se actualizó el importe de su operación</h1>
          <p style="margin:0 0 24px 0;color:#64748b;font-size:14px;">Estimado(a) <strong style="color:#1e293b;">{{ operation.client.full_name or operation.client.razon_social }}</strong>, el importe de su operación <strong style="color:#0D1B2A;">{{ operation.operation_id }}</strong> ha sido actualizado por nuestro equipo.</p>

          <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;margin:0 0 16px 0;">
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:11px 14px;width:70px;color:#94a3b8;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:middle;">Código</td>
              <td style="padding:11px 14px;color:#0D1B2A;font-size:14px;font-weight:700;vertical-align:middle;border-right:1px solid #F1F5F9;">{{ operation.operation_id }}</td>
              <td style="padding:11px 14px;width:80px;color:#94a3b8;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:middle;">Tipo de cambio</td>
              <td style="padding:11px 14px;color:#1e293b;font-size:13px;font-weight:500;vertical-align:middle;">{{ "%.4f"|format(operation.exchange_rate) }}</td>
            </tr>
          </table>

          <p style="margin:0 0 10px 0;font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:1.2px;padding-left:10px;border-left:3px solid #5CB85C;">Detalle del cambio</p>
          <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;margin:0 0 24px 0;">
            <tr style="background-color:#0D1B2A;">
              <td style="padding:9px 18px;color:#94a3b8;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;width:120px;">Concepto</td>
              <td style="padding:9px 18px;color:#94a3b8;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Importe anterior</td>
              <td style="padding:9px 6px;color:#94a3b8;font-size:11px;font-weight:600;text-align:center;width:30px;"></td>
              <td style="padding:9px 18px;color:#94a3b8;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Importe nuevo</td>
            </tr>
            <tr style="border-top:1px solid #F1F5F9;">
              <td style="padding:12px 18px;color:#94a3b8;font-size:12px;font-weight:600;vertical-align:middle;">Monto USD</td>
              <td style="padding:12px 18px;vertical-align:middle;">
                <span style="color:#94a3b8;text-decoration:line-through;font-size:13px;">$ {{ "{:,.2f}".format(old_amount_usd) }}</span>
              </td>
              <td style="padding:12px 6px;text-align:center;vertical-align:middle;">
                <span style="color:#F59E0B;font-weight:700;font-size:14px;">&rarr;</span>
              </td>
              <td style="padding:12px 18px;vertical-align:middle;">
                <span style="color:#5CB85C;font-weight:700;font-size:15px;">$ {{ "{:,.2f}".format(operation.amount_usd) }}</span>
              </td>
            </tr>
            <tr style="border-top:1px solid #F1F5F9;">
              <td style="padding:12px 18px;color:#94a3b8;font-size:12px;font-weight:600;vertical-align:middle;">Monto PEN</td>
              <td style="padding:12px 18px;vertical-align:middle;">
                <span style="color:#94a3b8;text-decoration:line-through;font-size:13px;">S/ {{ "{:,.2f}".format(old_amount_pen) }}</span>
              </td>
              <td style="padding:12px 6px;text-align:center;vertical-align:middle;">
                <span style="color:#F59E0B;font-weight:700;font-size:14px;">&rarr;</span>
              </td>
              <td style="padding:12px 18px;vertical-align:middle;">
                <span style="color:#5CB85C;font-weight:700;font-size:15px;">S/ {{ "{:,.2f}".format(operation.amount_pen) }}</span>
              </td>
            </tr>
          </table>

          <!-- ── CUENTAS QORICASH (donde el cliente transfiere) ── -->
          <p style="margin:0 0 3px 0;font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:1.2px;padding-left:10px;border-left:3px solid #5CB85C;">
            {% if operation.operation_type == 'Compra' %}¿A dónde transfiero mis dólares?{% else %}¿A dónde transfiero mis soles?{% endif %}
          </p>
          <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;margin:0 0 24px 0;">
            <tr style="background:#F8FAFC;border-bottom:1px solid #E2E8F0;">
              <td colspan="4" style="padding:9px 14px;font-size:11px;color:#64748b;text-align:justify;">
                Titular: <strong style="color:#1e293b;">{{ qoricash_titular }}</strong> &nbsp;&bull;&nbsp; RUC {{ qoricash_ruc }} &nbsp;&bull;&nbsp;
                {% if operation.operation_type == 'Compra' %}Transfiera en <strong style="color:#1e293b;">USD</strong>{% else %}Transfiera en <strong style="color:#1e293b;">PEN</strong>{% endif %}
              </td>
            </tr>
            <tr style="background:#0D1B2A;">
              <td style="padding:7px 12px;color:#94a3b8;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;">Banco</td>
              <td style="padding:7px 12px;color:#94a3b8;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;">Tipo de cuenta</td>
              <td style="padding:7px 12px;color:#94a3b8;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;">N° Cuenta</td>
              <td style="padding:7px 12px;color:#94a3b8;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;">CCI</td>
            </tr>
            {% if operation.operation_type == 'Compra' %}
            {% for acc in usd_accounts %}
            <tr style="border-top:1px solid #F1F5F9;">
              <td style="padding:9px 12px;font-size:12px;font-weight:700;color:#1e293b;white-space:nowrap;">{{ acc.banco }}</td>
              <td style="padding:9px 12px;font-size:12px;color:#64748b;">{{ acc.tipo }}</td>
              <td style="padding:9px 12px;font-family:'Courier New',monospace;font-size:11px;font-weight:600;color:#0D1B2A;">{{ acc.numero }}</td>
              <td style="padding:9px 12px;font-family:'Courier New',monospace;font-size:11px;color:#64748b;">{{ acc.cci }}</td>
            </tr>
            {% endfor %}
            {% else %}
            {% for acc in pen_accounts %}
            <tr style="border-top:1px solid #F1F5F9;">
              <td style="padding:9px 12px;font-size:12px;font-weight:700;color:#1e293b;white-space:nowrap;">{{ acc.banco }}</td>
              <td style="padding:9px 12px;font-size:12px;color:#64748b;">{{ acc.tipo }}</td>
              <td style="padding:9px 12px;font-family:'Courier New',monospace;font-size:11px;font-weight:600;color:#0D1B2A;">{{ acc.numero }}</td>
              <td style="padding:9px 12px;font-family:'Courier New',monospace;font-size:11px;color:#64748b;">{{ acc.cci }}</td>
            </tr>
            {% endfor %}
            {% endif %}
          </table>

          <!-- ── CUENTAS DEL CLIENTE (donde recibirá el pago) ── -->
          <p style="margin:0 0 3px 0;font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:1.2px;padding-left:10px;border-left:3px solid #5CB85C;">
            {% if is_ruc %}¿Dónde recibirá su pago?{% else %}¿Dónde recibirás tu pago?{% endif %}
          </p>
          <p style="margin:0 0 10px 0;font-size:11px;color:#94a3b8;padding-left:13px;">
            Qoricash acreditará en la siguiente cuenta
          </p>
          {% if client_accounts %}
          <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;margin:0 0 24px 0;">
            <tr style="background:#0D1B2A;">
              <td style="padding:7px 14px;color:#94a3b8;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;">Banco</td>
              <td style="padding:7px 14px;color:#94a3b8;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;">Tipo de cuenta</td>
              <td style="padding:7px 14px;color:#94a3b8;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;">Titular</td>
              <td style="padding:7px 14px;color:#94a3b8;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;">N° Cuenta</td>
              <td style="padding:7px 14px;color:#94a3b8;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;">Moneda</td>
            </tr>
            {% for acc in client_accounts %}
            {% if (operation.operation_type == 'Compra' and acc.get('currency') == 'PEN') or (operation.operation_type != 'Compra' and acc.get('currency') == 'USD') %}
            <tr style="border-top:1px solid #F1F5F9;">
              <td style="padding:10px 14px;font-size:12px;font-weight:700;color:#1e293b;white-space:nowrap;">{{ acc.bank_name }}</td>
              <td style="padding:10px 14px;font-size:12px;color:#64748b;">{{ acc.get('account_type', 'Cuenta Bancaria') }}</td>
              <td style="padding:10px 14px;font-size:12px;color:#1e293b;">{{ operation.client.full_name or operation.client.razon_social }}</td>
              <td style="padding:10px 14px;font-family:'Courier New',monospace;font-size:11px;font-weight:600;color:#0D1B2A;">{{ acc.account_number }}</td>
              <td style="padding:10px 14px;font-size:12px;color:#64748b;">{{ acc.get('currency', '') }}</td>
            </tr>
            {% endif %}
            {% endfor %}
          </table>
          {% else %}
          <div style="border-radius:6px;padding:12px 16px;margin:0 0 24px 0;background:#F8FAFC;border:1px solid #E2E8F0;font-size:12px;color:#94a3b8;text-align:center;">
            {% if is_ruc %}No tiene cuentas bancarias registradas. Su ejecutivo le contactará para coordinar el pago.{% else %}No tienes cuentas bancarias registradas. Tu ejecutivo te contactará para coordinar el pago.{% endif %}
          </div>
          {% endif %}

          <div style="border-radius:6px;padding:13px 16px;margin:0 0 20px 0;font-size:13px;line-height:1.65;background:#F0FDF4;border-left:3px solid #5CB85C;color:#14532d;">
            Si tiene alguna consulta sobre este cambio, responda este correo o contáctese directamente con su asesor.
          </div>

          <div style="height:1px;background-color:#F1F5F9;margin:20px 0;"></div>
          <p style="margin:0;font-size:12px;color:#94a3b8;">Este es un correo automático generado por el sistema QoriCash.</p>

        </td>
      </tr>"""
        from app.config.bank_accounts import get_accounts_for_currency, QORICASH_TITULAR, QORICASH_RUC
        html = render_template_string(
            _wrap_email_themed_svc(body, _theme),
            operation=operation,
            old_amount_usd=old_amount_usd,
            old_amount_pen=old_amount_pen,
            is_ruc=is_ruc,
            usd_accounts=get_accounts_for_currency('USD'),
            pen_accounts=get_accounts_for_currency('PEN'),
            qoricash_titular=QORICASH_TITULAR,
            qoricash_ruc=QORICASH_RUC,
            client_accounts=client_accounts,
        )
        return _apply_theme_colors(html, _theme)

    @staticmethod
    def _render_canceled_operation_template(operation, reason=None):
        """Renderizar plantilla HTML para operación cancelada"""
        _doc = getattr(getattr(operation, 'client', None), 'document_type', 'DNI')
        _theme = _get_theme(_doc)
        body = """
      <tr>
        <td class="email-body-cell" style="padding:32px 36px;color:#334155;font-size:14px;line-height:1.65;">

          <div style="margin:0 0 16px 0;">
            <span style="display:inline-block;background:#FEF2F2;color:#EF4444;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.4px;padding:4px 10px;border-radius:4px;">Operación Cancelada</span>
          </div>

          <h1 style="margin:0 0 6px 0;font-size:21px;font-weight:700;color:#0D1B2A;line-height:1.3;">Su operación ha sido cancelada</h1>
          <p style="margin:0 0 24px 0;color:#64748b;font-size:14px;">Estimado(a) <strong style="color:#1e293b;">{{ operation.client.full_name or operation.client.razon_social }}</strong>, la siguiente operación ha sido cancelada en nuestro sistema.</p>

          <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;margin:0 0 24px 0;">
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td class="ops-label" style="padding:11px 14px;width:70px;color:#94a3b8;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:middle;">Código</td>
              <td style="padding:11px 14px;color:#0D1B2A;font-size:14px;font-weight:700;vertical-align:middle;border-right:1px solid #F1F5F9;">{{ operation.operation_id }}</td>
              <td class="ops-label" style="padding:11px 14px;width:50px;color:#94a3b8;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:middle;">Tipo</td>
              <td style="padding:11px 14px;vertical-align:middle;">
                {% if operation.operation_type == 'Compra' %}
                  <span style="display:inline-block;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700;background:#DCFCE7;color:#15803D;letter-spacing:0.3px;white-space:nowrap;">COMPRA USD</span>
                {% else %}
                  <span style="display:inline-block;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700;background:#DBEAFE;color:#1D4ED8;letter-spacing:0.3px;white-space:nowrap;">VENTA USD</span>
                {% endif %}
              </td>
            </tr>
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td colspan="4" style="padding:12px 14px;">
                <table width="100%" cellspacing="0" cellpadding="0">
                  <tr>
                    <td class="metric-cell" style="text-align:center;padding:13px 8px;background:#F8FAFC;border:1px solid #E2E8F0;border-radius:6px;border-top:3px solid #5CB85C;">
                      <div style="font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Monto USD</div>
                      <div style="font-size:17px;font-weight:800;color:#5CB85C;">$ {{ "{:,.2f}".format(operation.amount_usd) }}</div>
                    </td>
                    <td class="metric-spacer" width="8">&nbsp;</td>
                    <td class="metric-cell" style="text-align:center;padding:13px 8px;background:#F8FAFC;border:1px solid #E2E8F0;border-radius:6px;border-top:3px solid #5CB85C;">
                      <div style="font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Tipo de Cambio</div>
                      <div style="font-size:15px;font-weight:700;color:#1e293b;">{{ "%.4f"|format(operation.exchange_rate) }}</div>
                    </td>
                    <td class="metric-spacer" width="8">&nbsp;</td>
                    <td class="metric-cell" style="text-align:center;padding:13px 8px;background:#F8FAFC;border:1px solid #E2E8F0;border-radius:6px;border-top:3px solid #5CB85C;">
                      <div style="font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Monto PEN</div>
                      <div style="font-size:17px;font-weight:800;color:#5CB85C;">S/ {{ "{:,.2f}".format(operation.amount_pen) }}</div>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td class="ops-label" style="padding:11px 14px;width:50px;color:#94a3b8;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:middle;">Fecha</td>
              <td style="padding:11px 14px;color:#1e293b;font-size:13px;font-weight:500;vertical-align:middle;border-right:1px solid #F1F5F9;">{{ operation.created_at.strftime('%d/%m/%Y %H:%M') }}</td>
              <td class="ops-label" style="padding:11px 14px;width:50px;color:#94a3b8;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:middle;">Estado</td>
              <td style="padding:11px 14px;vertical-align:middle;">
                <span style="display:inline-block;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700;background:#FEE2E2;color:#991B1B;letter-spacing:0.3px;">CANCELADO</span>
              </td>
            </tr>
          </table>

          {% if reason %}
          <div style="border-radius:6px;padding:13px 16px;margin:0 0 16px 0;font-size:13px;line-height:1.65;background:#FEF2F2;border-left:3px solid #EF4444;color:#991B1B;">
            <strong>Motivo de cancelación:</strong> {{ reason }}
          </div>
          {% endif %}

          <div style="border-radius:6px;padding:13px 16px;margin:0 0 24px 0;font-size:13px;line-height:1.65;background:#F0FDF4;border-left:3px solid #5CB85C;color:#14532d;">
            Si desea realizar una nueva operación, puede ingresar a <strong>www.qoricash.pe</strong> o contactar a su asesor comercial.
          </div>

          <div style="height:1px;background-color:#F1F5F9;margin:20px 0;"></div>
          <p style="margin:0;font-size:12px;color:#94a3b8;">¿Consultas? Responda este correo o escríbanos a <a href="mailto:info@qoricash.pe" style="color:#5CB85C;">info@qoricash.pe</a></p>

        </td>
      </tr>"""
        html = render_template_string(_wrap_email_themed_svc(body, _theme), operation=operation, reason=reason)
        return _apply_theme_colors(html, _theme)

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
            # Destinatario principal: Cliente (soporta múltiples emails separados por ";")
            to = EmailService._parse_client_emails(client.email)

            # CC: Trader que registró al cliente + gerencia
            seen = set(to)
            cc = []
            if trader and trader.email and trader.email not in seen:
                cc.append(trader.email)
                seen.add(trader.email)
            if 'gerencia@qoricash.pe' not in seen:
                cc.append('gerencia@qoricash.pe')

            # Validar que haya al menos un destinatario
            if not to and not cc:
                logger.warning(f'No hay destinatarios para el cliente {client.id}')
                return False, 'No hay destinatarios configurados'

            # Asunto
            subject = f'Bienvenido a QoriCash - Registro en Proceso'

            # Contenido HTML
            from app.services.email_templates import EmailTemplates
            shared_clients = EmailTemplates._get_shared_email_clients(client)
            html_body = EmailService._render_new_client_template(client, trader, shared_clients)

            # Crear mensaje
            msg = Message(
                subject=subject,
                recipients=to,
                cc=cc,
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
    def send_client_activation_email(client, trader, temporary_password=None):
        """
        Enviar correo de notificación de cliente activado.

        Envía DOS correos separados:
          1. Al cliente (TO): incluye la contraseña temporal si se proporciona.
          2. Al trader + gerencia (TO/BCC): sin contraseña, solo notificación de activación.

        Args:
            client: Objeto Client
            trader: Objeto User (trader que registró al cliente)
            temporary_password: Contraseña temporal generada (solo visible para el cliente)

        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            from flask import current_app
            from flask_mail import Message, Mail

            logger.info(f'[EMAIL] Iniciando envio de email de cliente activado {client.id}')

            if not client.email:
                logger.warning(f'Cliente {client.id} no tiene email registrado')
                return False, 'El cliente no tiene email registrado'

            # Obtener credenciales del email de confirmación
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
                from app.extensions import mail
                mail.init_app(current_app)

                subject = 'Cuenta Activada - Bienvenido a QoriCash'

                # ── EMAIL 1: al cliente, CON contraseña temporal ──────────────
                logger.info(f'[EMAIL] Enviando correo al cliente {client.email} (con contraseña)')
                html_cliente = EmailService._render_client_activation_template(client, trader, temporary_password=temporary_password)
                client_emails = EmailService._parse_client_emails(client.email)
                msg_cliente = Message(
                    subject=subject,
                    sender=confirmation_sender,
                    recipients=client_emails,
                    html=html_cliente
                )
                EmailService._send_async(msg_cliente, timeout=15)
                logger.info(f'[EMAIL] Correo al cliente programado: {client_emails}')

                # ── EMAIL 2: al trader + masters, SIN contraseña temporal ─────
                internal_to = []
                internal_bcc = []
                seen = set(client_emails)

                if trader and trader.email and trader.email not in seen:
                    internal_to.append(trader.email)
                    seen.add(trader.email)

                masters = User.query.filter(
                    User.role in ('Master', 'Presidente de Negocios'),
                    User.status == 'Activo',
                    User.email.isnot(None)
                ).all()
                for master in masters:
                    if master.email and master.email not in seen:
                        internal_bcc.append(master.email)
                        seen.add(master.email)

                if internal_to or internal_bcc:
                    logger.info(f'[EMAIL] Enviando correo interno a TO: {internal_to}, BCC: {internal_bcc} (sin contraseña)')
                    html_interno = EmailService._render_client_activation_template(client, trader, temporary_password=None)
                    msg_interno = Message(
                        subject=subject,
                        sender=confirmation_sender,
                        recipients=internal_to if internal_to else internal_bcc[:1],
                        bcc=internal_bcc if internal_to else internal_bcc[1:],
                        html=html_interno
                    )
                    EmailService._send_async(msg_interno, timeout=15)
                    logger.info(f'[EMAIL] Correo interno programado para trader/gerencia')

                logger.info(f'[EMAIL] Emails de activación programados para cliente {client.id}')
                return True, 'Email programado para envío'

            finally:
                # Restaurar configuración original
                current_app.config['MAIL_USERNAME'] = original_username
                current_app.config['MAIL_PASSWORD'] = original_password
                current_app.config['MAIL_DEFAULT_SENDER'] = original_sender
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
        body = """
      <tr>
        <td class="email-body-cell" style="padding:32px 36px;color:#334155;font-size:14px;line-height:1.65;">

          <div style="margin:0 0 16px 0;">
            <span style="display:inline-block;background:#F0FDF4;color:#5CB85C;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.4px;padding:5px 14px;border-radius:20px;border:1.5px solid #5CB85C;">Acceso Seguro</span>
          </div>

          <h1 style="margin:0 0 6px 0;font-size:21px;font-weight:700;color:#0D1B2A;line-height:1.3;">Contraseña temporal de acceso</h1>
          <p style="margin:0 0 24px 0;color:#64748b;font-size:14px;">
            Hola <strong style="color:#1e293b;">{{ client_name }}</strong>,
            a continuación tu contraseña temporal para ingresar a QoriCash.
          </p>

          <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;background:#0D1B2A;border-radius:10px;overflow:hidden;margin:0 0 16px 0;">
            <tr>
              <td style="padding:22px 24px;text-align:center;">
                <p style="margin:0 0 10px 0;color:rgba(255,255,255,0.50);font-size:10px;letter-spacing:0.8px;text-transform:uppercase;">Contraseña de acceso</p>
                <p style="margin:0 0 10px 0;color:#5CB85C;font-size:28px;font-family:'Courier New',Courier,monospace;font-weight:700;letter-spacing:4px;">{{ temp_password }}</p>
                <p style="margin:0;color:rgba(255,255,255,0.35);font-size:11px;">Cópiala exactamente como aparece</p>
              </td>
            </tr>
          </table>

          <div style="border-radius:6px;padding:13px 16px;margin:0 0 16px 0;font-size:13px;line-height:1.65;background:#FEF2F2;border-left:3px solid #EF4444;color:#7f1d1d;">
            <strong>Seguridad:</strong> Deberás cambiar esta contraseña al iniciar sesión. No la compartas con nadie.
          </div>

          <p style="margin:0 0 10px 0;font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:1.2px;padding-left:10px;border-left:3px solid #5CB85C;">Pasos a seguir</p>
          <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;margin:0 0 16px 0;">
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:10px 14px;color:#94a3b8;font-size:12px;font-weight:700;width:28px;text-align:center;vertical-align:top;">1</td>
              <td style="padding:10px 16px;color:#334155;font-size:13px;">Ingresa a QoriCash con tu número de documento y esta contraseña</td>
            </tr>
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:10px 14px;color:#94a3b8;font-size:12px;font-weight:700;text-align:center;vertical-align:top;">2</td>
              <td style="padding:10px 16px;color:#334155;font-size:13px;">El sistema te pedirá establecer una nueva contraseña segura</td>
            </tr>
            <tr>
              <td style="padding:10px 14px;color:#94a3b8;font-size:12px;font-weight:700;text-align:center;vertical-align:top;">3</td>
              <td style="padding:10px 16px;color:#334155;font-size:13px;">¡Listo! Ya puedes operar con normalidad</td>
            </tr>
          </table>

          <div style="border-radius:6px;padding:13px 16px;margin:0 0 24px 0;font-size:13px;line-height:1.65;background:#F0FDF4;border-left:3px solid #5CB85C;color:#14532d;">
            <strong>¿No solicitaste este cambio?</strong> Contacta a nuestro equipo inmediatamente en
            <a href="mailto:info@qoricash.pe" style="color:#5CB85C;">info@qoricash.pe</a>
          </div>

          <div style="height:1px;background-color:#F1F5F9;margin:20px 0;"></div>
          <p style="margin:0;font-size:12px;color:#94a3b8;">Este correo fue generado automáticamente. Por favor no respondas a este mensaje.</p>
        </td>
      </tr>"""
        html = render_template_string(_wrap_email_themed_svc(body, 'persona'), client_name=client_name, temp_password=temp_password)
        return _apply_theme_colors(html, 'persona')

    @staticmethod
    def _render_new_client_template(client, trader, shared_clients=None):
        _theme = _get_theme(getattr(client, 'document_type', 'DNI'))
        """Renderizar plantilla HTML para nuevo cliente registrado"""
        from app.services.email_templates import _build_shared_email_block
        shared_block = _build_shared_email_block(shared_clients or [])
        bank_accounts_text = "No registrado"
        if hasattr(client, 'bank_accounts') and client.bank_accounts:
            try:
                import json
                accounts = json.loads(client.bank_accounts) if isinstance(client.bank_accounts, str) else client.bank_accounts
                if accounts and isinstance(accounts, list):
                    bank_list = [
                        f"{a.get('bank_name','')} | {a.get('currency','')} | {a.get('account_number','')}"
                        for a in accounts if a.get('bank_name') and a.get('account_number')
                    ]
                    bank_accounts_text = ", ".join(bank_list) if bank_list else "No registrado"
            except Exception:
                pass

        body = """
      <tr>
        <td class="email-body-cell" style="padding:32px 36px;color:#334155;font-size:14px;line-height:1.65;">

          <div style="margin:0 0 20px 0;">
            {% if client.document_type == 'RUC' %}
            <span style="display:inline-block;background:linear-gradient(135deg,#1A6EAD 0%,#1A3D58 100%);color:#ffffff;
                         font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.4px;
                         padding:7px 18px;border-radius:20px;box-shadow:0 4px 14px rgba(26,61,88,0.35);">
              Registro recibido con éxito
            </span>
            {% else %}
            <span style="display:inline-block;background:linear-gradient(135deg,#22C55E 0%,#16a34a 100%);color:#ffffff;
                         font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.4px;
                         padding:7px 18px;border-radius:20px;box-shadow:0 4px 14px rgba(34,197,94,0.35);">
              Registro recibido con éxito
            </span>
            {% endif %}
          </div>

          <h1 style="margin:0 0 6px 0;font-size:21px;font-weight:700;color:#0D1B2A;line-height:1.3;">Su registro está siendo procesado</h1>
          <p style="margin:0 0 24px 0;color:#64748b;font-size:14px;">Estimado(a) <strong style="color:#1e293b;">{{ client.full_name or client.razon_social }}</strong>, hemos recibido su solicitud de registro a través de su ejecutivo <strong>{{ trader.username }}</strong>. Pronto le notificaremos la activación.</p>

          <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;margin:0 0 24px 0;">
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:11px 18px;width:160px;color:#94a3b8;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:top;">Cliente</td>
              <td style="padding:11px 18px;color:#0D1B2A;font-size:13px;font-weight:600;vertical-align:top;">{{ client.full_name or client.razon_social }}</td>
            </tr>
            {% if client.document_type %}
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:11px 18px;color:#94a3b8;font-size:12px;font-weight:600;vertical-align:top;">Tipo de documento</td>
              <td style="padding:11px 18px;color:#1e293b;font-size:13px;vertical-align:top;">{{ client.document_type }}</td>
            </tr>
            {% endif %}
            {% if client.document_number %}
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:11px 18px;color:#94a3b8;font-size:12px;font-weight:600;vertical-align:top;">N° de documento</td>
              <td style="padding:11px 18px;color:#1e293b;font-size:13px;vertical-align:top;">{{ client.document_number }}</td>
            </tr>
            {% endif %}
            {% if client.phone %}
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:11px 18px;color:#94a3b8;font-size:12px;font-weight:600;vertical-align:top;">Teléfono</td>
              <td style="padding:11px 18px;color:#1e293b;font-size:13px;vertical-align:top;">{{ client.phone }}</td>
            </tr>
            {% endif %}
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:11px 18px;color:#94a3b8;font-size:12px;font-weight:600;vertical-align:top;">Cuentas bancarias</td>
              <td style="padding:11px 18px;color:#1e293b;font-size:13px;vertical-align:top;">{{ bank_accounts_text }}</td>
            </tr>
            <tr>
              <td style="padding:11px 18px;color:#94a3b8;font-size:12px;font-weight:600;vertical-align:top;">Ejecutivo asignado</td>
              <td style="padding:11px 18px;color:#5CB85C;font-size:13px;font-weight:600;vertical-align:top;">{{ trader.username }}</td>
            </tr>
          </table>

          {{ shared_block }}
          <div style="height:1px;background-color:#F1F5F9;margin:20px 0;"></div>
          <p style="margin:0 0 6px 0;font-size:13px;color:#334155;">Para cualquier consulta, contacte a su ejecutivo <strong>{{ trader.username }}</strong>{% if trader.email %} en <a href="mailto:{{ trader.email }}" style="color:#5CB85C;">{{ trader.email }}</a>{% endif %}.</p>
          <p style="margin:0;font-size:12px;color:#94a3b8;">Este es un correo automático.</p>
        </td>
      </tr>"""
        html = render_template_string(_wrap_email_themed_svc(body, _theme), client=client, trader=trader, bank_accounts_text=bank_accounts_text, shared_block=shared_block)
        return _apply_theme_colors(html, _theme)

    @staticmethod
    def _render_client_activation_template(client, trader, temporary_password=None):
        """Delegado al template unificado de activación."""
        from app.services.email_templates import EmailTemplates
        return EmailTemplates._render_trader_activation_template(client, trader, temporary_password)

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
        _theme = _get_theme(complaint_data.get('tipo_documento', 'DNI'))
        body = """
      <tr>
        <td class="email-body-cell" style="padding:32px 36px;color:#334155;font-size:14px;line-height:1.65;">

          <div style="margin:0 0 16px 0;">
            <span style="display:inline-block;background:#FEF2F2;color:#EF4444;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.4px;padding:4px 10px;border-radius:4px;">Libro de Reclamaciones</span>
          </div>

          <h1 style="margin:0 0 6px 0;font-size:21px;font-weight:700;color:#0D1B2A;line-height:1.3;">{{ complaint_data.get('tipo_solicitud', 'Reclamo') }} recibido</h1>
          <p style="margin:0 0 24px 0;color:#64748b;font-size:14px;">N° <strong style="color:#1e293b;">{{ complaint_number }}</strong> &nbsp;&middot;&nbsp; {{ fecha_actual }}</p>

          <p style="margin:0 0 10px 0;font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:1.2px;padding-left:10px;border-left:3px solid #5CB85C;">Datos del reclamante</p>
          <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;margin:0 0 24px 0;">
            {% if complaint_data.get('tipo_documento') == 'RUC' %}
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:10px 18px;width:160px;color:#94a3b8;font-size:12px;font-weight:600;vertical-align:top;">Tipo de documento</td>
              <td style="padding:10px 18px;color:#1e293b;font-size:13px;vertical-align:top;">RUC</td>
            </tr>
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:10px 18px;color:#94a3b8;font-size:12px;font-weight:600;vertical-align:top;">N° de RUC</td>
              <td style="padding:10px 18px;color:#1e293b;font-size:13px;vertical-align:top;">{{ complaint_data.get('numero_documento', '—') }}</td>
            </tr>
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:10px 18px;color:#94a3b8;font-size:12px;font-weight:600;vertical-align:top;">Razón social</td>
              <td style="padding:10px 18px;color:#1e293b;font-size:13px;vertical-align:top;">{{ complaint_data.get('razon_social', '—') }}</td>
            </tr>
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:10px 18px;color:#94a3b8;font-size:12px;font-weight:600;vertical-align:top;">Persona de contacto</td>
              <td style="padding:10px 18px;color:#1e293b;font-size:13px;vertical-align:top;">{{ complaint_data.get('persona_contacto', '—') }}</td>
            </tr>
            {% else %}
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:10px 18px;width:160px;color:#94a3b8;font-size:12px;font-weight:600;vertical-align:top;">Tipo de documento</td>
              <td style="padding:10px 18px;color:#1e293b;font-size:13px;vertical-align:top;">{{ complaint_data.get('tipo_documento', 'DNI') }}</td>
            </tr>
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:10px 18px;color:#94a3b8;font-size:12px;font-weight:600;vertical-align:top;">N° de documento</td>
              <td style="padding:10px 18px;color:#1e293b;font-size:13px;vertical-align:top;">{{ complaint_data.get('numero_documento', '—') }}</td>
            </tr>
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:10px 18px;color:#94a3b8;font-size:12px;font-weight:600;vertical-align:top;">Nombres</td>
              <td style="padding:10px 18px;color:#1e293b;font-size:13px;vertical-align:top;">{{ complaint_data.get('nombres', '—') }} {{ complaint_data.get('apellidos', '') }}</td>
            </tr>
            {% endif %}
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:10px 18px;color:#94a3b8;font-size:12px;font-weight:600;vertical-align:top;">Email</td>
              <td style="padding:10px 18px;color:#1e293b;font-size:13px;vertical-align:top;">{{ complaint_data.get('email', '—') }}</td>
            </tr>
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:10px 18px;color:#94a3b8;font-size:12px;font-weight:600;vertical-align:top;">Teléfono</td>
              <td style="padding:10px 18px;color:#1e293b;font-size:13px;vertical-align:top;">{{ complaint_data.get('telefono', '—') }}</td>
            </tr>
            <tr>
              <td style="padding:10px 18px;color:#94a3b8;font-size:12px;font-weight:600;vertical-align:top;">Dirección</td>
              <td style="padding:10px 18px;color:#1e293b;font-size:13px;vertical-align:top;">{{ complaint_data.get('direccion', '—') }}</td>
            </tr>
          </table>

          <p style="margin:0 0 10px 0;font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:1.2px;padding-left:10px;border-left:3px solid #5CB85C;">Detalle del {{ complaint_data.get('tipo_solicitud', 'reclamo') }}</p>
          <div style="border-radius:6px;padding:16px 18px;margin:0 0 24px 0;font-size:13px;color:#78350f;white-space:pre-wrap;line-height:1.7;background:#FFFBEB;border:1px solid #FDE68A;">{{ complaint_data.get('detalle', 'No se proporcionó detalle.') }}</div>

          <div style="border-radius:6px;padding:13px 16px;margin:0 0 24px 0;font-size:13px;line-height:1.65;background:#F0FDF4;border-left:3px solid #5CB85C;color:#14532d;">
            <strong>Plazo de respuesta:</strong> Este {{ complaint_data.get('tipo_solicitud', 'reclamo').lower() }} debe ser atendido dentro de las próximas 24–48 horas hábiles.
          </div>

          <div style="height:1px;background-color:#F1F5F9;margin:20px 0;"></div>
          <p style="margin:0;font-size:12px;color:#94a3b8;">Correo generado automáticamente desde el Libro de Reclamaciones de QoriCash.</p>
        </td>
      </tr>"""
        from datetime import datetime
        import pytz

        tz_peru = pytz.timezone('America/Lima')
        fecha_actual = datetime.now(tz_peru).strftime('%d/%m/%Y %H:%M:%S')
        complaint_number = complaint_data.get('complaint_number', 'N/A')
        html = render_template_string(
            _wrap_email_themed_svc(body, _theme),
            complaint_data=complaint_data,
            fecha_actual=fecha_actual,
            complaint_number=complaint_number
        )
        return _apply_theme_colors(html, _theme)

    @staticmethod
    def send_fx_alert_email(competitor_name: str, change: dict, recipients: list):
        """
        Envía alerta de cambio de precio de competidor a usuarios Master.

        Args:
            competitor_name: Nombre del competidor que cambió sus tasas.
            change: Dict con old_buy, new_buy, old_sell, new_sell, buy_delta, sell_delta,
                    buy_delta_pct, sell_delta_pct, field.
            recipients: Lista de emails de usuarios Master.
        """
        try:
            import pytz
            from datetime import datetime as _dt
            tz_lima = pytz.timezone('America/Lima')
            hora = _dt.now(tz_lima).strftime('%d/%m/%Y %H:%M')

            field = change.get('field', 'both')
            old_buy  = change.get('old_buy')
            new_buy  = change.get('new_buy')
            old_sell = change.get('old_sell')
            new_sell = change.get('new_sell')
            buy_pct  = change.get('buy_delta_pct', 0) or 0
            sell_pct = change.get('sell_delta_pct', 0) or 0

            def _row(label, old, new, pct):
                if old is None or new is None:
                    return ''
                arrow = '▲' if new > old else '▼'
                color = '#dc3545' if new > old else '#198754'
                sign  = '+' if pct >= 0 else ''
                return f"""
                <tr>
                  <td style="padding:8px 12px;border-bottom:1px solid #eee;">{label}</td>
                  <td style="padding:8px 12px;border-bottom:1px solid #eee;">S/ {old:.4f}</td>
                  <td style="padding:8px 12px;border-bottom:1px solid #eee;color:{color};font-weight:bold;">
                    {arrow} S/ {new:.4f}
                  </td>
                  <td style="padding:8px 12px;border-bottom:1px solid #eee;color:{color};">
                    {sign}{pct:.3f}%
                  </td>
                </tr>"""

            rows_html = ''
            if field in ('buy', 'both'):
                rows_html += _row('Compra', old_buy, new_buy, buy_pct)
            if field in ('sell', 'both'):
                rows_html += _row('Venta', old_sell, new_sell, sell_pct)

            body_html = f"""
            <p style="margin:0 0 16px;font-size:15px;color:#333;">
              Se detectó un cambio de precios en
              <strong style="color:#0D1B2A;">{competitor_name}</strong>
              a las {hora} (hora Lima).
            </p>
            <table style="width:100%;border-collapse:collapse;font-size:14px;">
              <thead>
                <tr style="background:#f0f4f8;">
                  <th style="padding:8px 12px;text-align:left;">Campo</th>
                  <th style="padding:8px 12px;text-align:left;">Anterior</th>
                  <th style="padding:8px 12px;text-align:left;">Nuevo</th>
                  <th style="padding:8px 12px;text-align:left;">Variación</th>
                </tr>
              </thead>
              <tbody>{rows_html}</tbody>
            </table>
            <p style="margin:16px 0 0;font-size:12px;color:#888;">
              Revisa el <a href="/monitor/" style="color:#0d6efd;">panel de monitoreo</a>
              para ver el comparativo completo con todos los competidores.
            </p>"""

            html_content = EmailService.build_email_html(
                title=f'Cambio de precio — {competitor_name}',
                body_html=body_html,
                subtitle=f'Monitor de Competencia · {hora}',
            )

            msg = Message(
                subject=f'[QoriCash Monitor] {competitor_name} cambio su precio',
                recipients=recipients,
                html=html_content,
            )
            EmailService._send_async(msg, timeout=15)
            logger.info(f'[EMAIL] Alerta FX programada para {recipients} — {competitor_name}')

        except Exception as e:
            logger.warning(f'[EMAIL] No se pudo enviar alerta FX: {e}')
