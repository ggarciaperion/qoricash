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


# ============================================
# CONSTANTES DE MARCA
# ============================================
_LOGO_URL = 'https://www.qoricash.pe/logofirma.png'
_GREEN    = '#5CB85C'
_DARK     = '#0D1B2A'
_SBS_TAG  = 'Regulada por la SBS &nbsp;&middot;&nbsp; Res. N.&ordm; 00313-2026'

_HEADER_BLOCK = f"""
      <tr>
        <td style="padding:20px 36px 18px;border-bottom:1px solid #E2E8F0;">
          <table width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr>
              <td style="vertical-align:middle;">
                <table cellpadding="0" cellspacing="0" border="0">
                  <tr>
                    <td style="vertical-align:middle;padding-right:10px;">
                      <img src="{_LOGO_URL}" alt="Q" style="height:38px;width:auto;display:block;">
                    </td>
                    <td style="width:3px;min-width:3px;background:{_GREEN};border-radius:2px;vertical-align:middle;">&nbsp;</td>
                    <td style="padding-left:10px;vertical-align:middle;">
                      <span style="font-size:20px;font-weight:800;color:{_DARK};letter-spacing:2px;font-family:Arial,sans-serif;">QORICASH</span>
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
        .email-body-cell { padding: 24px 20px !important; }
        .email-footer-cell { padding: 20px !important; }
    }
"""


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
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f5f7fa;padding:28px 16px;">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0"
           style="max-width:600px;width:100%;background:#ffffff;border-radius:12px;
                  overflow:hidden;box-shadow:0 2px 16px rgba(13,27,42,0.08);">
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
                - cc: gerencia@qoricash.pe
                - bcc: vacío
        """
        to = [operation.client.email] if operation.client and operation.client.email else []
        cc = [e for e in ['gerencia@qoricash.pe'] if e not in set(to)]
        bcc = []
        return to, cc, bcc

    @staticmethod
    def get_recipients_for_completed_operation(operation):
        """
        Obtener lista de destinatarios para operación completada

        Returns:
            tuple: (to, cc, bcc) donde:
                - to: Cliente
                - cc: gerencia@qoricash.pe
                - bcc: vacío
        """
        to = [operation.client.email] if operation.client and operation.client.email else []
        cc = [e for e in ['gerencia@qoricash.pe'] if e not in set(to)]
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

            # Sender: email del trader dueño de la operación
            trader_email = operation.user.email if operation.user and operation.user.email else None
            if not trader_email:
                logger.warning(f'Trader sin email para operación {operation.operation_id} — usando remitente por defecto')

            # Crear mensaje
            msg = Message(
                subject=subject,
                sender=trader_email,
                recipients=to,
                cc=cc,
                bcc=bcc,
                html=html_body
            )

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

            # Sender: email del trader dueño de la operación
            trader_email = operation.user.email if operation.user and operation.user.email else None

            subject = f'Operación Completada #{operation.operation_id} - QoriCash Trading'

            logger.info(f'[EMAIL] Generando plantilla HTML')
            html_body = EmailService._render_completed_operation_template(operation)

            logger.info(f'[EMAIL] Creando mensaje Flask-Mail')
            msg = Message(
                subject=subject,
                sender=trader_email,
                recipients=to,
                cc=cc if cc else None,
                html=html_body
            )

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
        """Renderizar plantilla HTML para nueva operación"""
        body = """
      <tr>
        <td class="email-body-cell" style="padding:32px 36px;color:#334155;font-size:14px;line-height:1.65;">

          <div style="margin:0 0 16px 0;">
            <span style="display:inline-block;background:#EFF6FF;color:#3B82F6;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.4px;padding:4px 10px;border-radius:4px;">Nueva Operación</span>
          </div>

          <h1 style="margin:0 0 6px 0;font-size:21px;font-weight:700;color:#0D1B2A;line-height:1.3;">Su operación ha sido registrada</h1>
          <p style="margin:0 0 24px 0;color:#64748b;font-size:14px;">Estimado(a) <strong style="color:#1e293b;">{{ operation.client.full_name or operation.client.razon_social }}</strong>, a continuación el resumen de su operación.</p>

          <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;margin:0 0 24px 0;">
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:11px 18px;width:160px;color:#94a3b8;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:top;">Código</td>
              <td style="padding:11px 18px;color:#0D1B2A;font-size:14px;font-weight:700;vertical-align:top;">{{ operation.operation_id }}</td>
            </tr>
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:11px 18px;width:160px;color:#94a3b8;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:top;">Tipo</td>
              <td style="padding:11px 18px;font-size:14px;vertical-align:top;">
                {% if operation.operation_type == 'Compra' %}
                  <span style="display:inline-block;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700;background:#DCFCE7;color:#15803D;letter-spacing:0.3px;">COMPRA USD</span>
                {% else %}
                  <span style="display:inline-block;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700;background:#DBEAFE;color:#1D4ED8;letter-spacing:0.3px;">VENTA USD</span>
                {% endif %}
              </td>
            </tr>
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td colspan="2" style="padding:12px 18px;">
                <table width="100%" cellspacing="0" cellpadding="0">
                  <tr>
                    <td style="text-align:center;padding:13px 8px;background:#F8FAFC;border:1px solid #E2E8F0;border-radius:6px;">
                      <div style="font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Monto USD</div>
                      <div style="font-size:17px;font-weight:800;color:#0D1B2A;">$ {{ "{:,.2f}".format(operation.amount_usd) }}</div>
                    </td>
                    <td width="8">&nbsp;</td>
                    <td style="text-align:center;padding:13px 8px;background:#F8FAFC;border:1px solid #E2E8F0;border-radius:6px;">
                      <div style="font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Tipo de Cambio</div>
                      <div style="font-size:15px;font-weight:700;color:#1e293b;">{{ "%.4f"|format(operation.exchange_rate) }}</div>
                    </td>
                    <td width="8">&nbsp;</td>
                    <td style="text-align:center;padding:13px 8px;background:#F8FAFC;border:1px solid #E2E8F0;border-radius:6px;">
                      <div style="font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Monto PEN</div>
                      <div style="font-size:17px;font-weight:800;color:#0D1B2A;">S/ {{ "{:,.2f}".format(operation.amount_pen) }}</div>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:11px 18px;width:160px;color:#94a3b8;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:top;">Estado</td>
              <td style="padding:11px 18px;color:#d97706;font-size:13px;font-weight:600;vertical-align:top;">{{ operation.status }}</td>
            </tr>
            <tr>
              <td style="padding:11px 18px;width:160px;color:#94a3b8;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:top;">Fecha</td>
              <td style="padding:11px 18px;color:#1e293b;font-size:13px;font-weight:500;vertical-align:top;">{{ operation.created_at.strftime('%d/%m/%Y %H:%M') }}</td>
            </tr>
          </table>

          {% if operation.operation_type == 'Compra' %}
          <p style="margin:0 0 10px 0;font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1.2px;">Cuentas para transferencia (USD)</p>
          <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;margin:0 0 24px 0;font-size:13px;">
            <tr>
              <td colspan="5" style="padding:11px 16px;background-color:#F8FAFC;border-bottom:1px solid #E2E8F0;color:#334155;font-size:13px;font-weight:600;">
                Transfiera en <strong>DÓLARES</strong> a cualquiera de estas cuentas &mdash; A nombre de {{ qoricash_titular }} &mdash; RUC {{ qoricash_ruc }}
              </td>
            </tr>
            <tr style="background-color:#0D1B2A;">
              <td style="padding:8px 12px;color:#94a3b8;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Banco</td>
              <td style="padding:8px 12px;color:#94a3b8;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Tipo</td>
              <td style="padding:8px 12px;color:#94a3b8;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Moneda</td>
              <td style="padding:8px 12px;color:#94a3b8;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">N° Cuenta</td>
              <td style="padding:8px 12px;color:#94a3b8;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">CCI</td>
            </tr>
            {% for acc in usd_accounts %}
            <tr style="border-top:1px solid #F1F5F9;">
              <td style="padding:9px 12px;color:#1e293b;font-weight:700;">{{ acc.banco }}</td>
              <td style="padding:9px 12px;color:#334155;">{{ acc.tipo }}</td>
              <td style="padding:9px 12px;color:#334155;">USD</td>
              <td style="padding:9px 12px;font-family:'Courier New',monospace;color:#0D1B2A;font-weight:600;font-size:11px;white-space:nowrap;">{{ acc.numero }}</td>
              <td style="padding:9px 12px;font-family:'Courier New',monospace;color:#0D1B2A;font-weight:600;font-size:11px;white-space:nowrap;word-break:break-all;">{{ acc.cci }}</td>
            </tr>
            {% endfor %}
          </table>
          {% elif operation.operation_type == 'Venta' %}
          <p style="margin:0 0 10px 0;font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1.2px;">Cuentas para transferencia (PEN)</p>
          <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;margin:0 0 24px 0;font-size:13px;">
            <tr>
              <td colspan="5" style="padding:11px 16px;background-color:#F8FAFC;border-bottom:1px solid #E2E8F0;color:#334155;font-size:13px;font-weight:600;">
                Transfiera en <strong>SOLES</strong> a cualquiera de estas cuentas &mdash; A nombre de {{ qoricash_titular }} &mdash; RUC {{ qoricash_ruc }}
              </td>
            </tr>
            <tr style="background-color:#0D1B2A;">
              <td style="padding:8px 12px;color:#94a3b8;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Banco</td>
              <td style="padding:8px 12px;color:#94a3b8;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Tipo</td>
              <td style="padding:8px 12px;color:#94a3b8;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Moneda</td>
              <td style="padding:8px 12px;color:#94a3b8;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">N° Cuenta</td>
              <td style="padding:8px 12px;color:#94a3b8;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">CCI</td>
            </tr>
            {% for acc in pen_accounts %}
            <tr style="border-top:1px solid #F1F5F9;">
              <td style="padding:9px 12px;color:#1e293b;font-weight:700;">{{ acc.banco }}</td>
              <td style="padding:9px 12px;color:#334155;">{{ acc.tipo }}</td>
              <td style="padding:9px 12px;color:#334155;">PEN</td>
              <td style="padding:9px 12px;font-family:'Courier New',monospace;color:#0D1B2A;font-weight:600;font-size:11px;white-space:nowrap;">{{ acc.numero }}</td>
              <td style="padding:9px 12px;font-family:'Courier New',monospace;color:#0D1B2A;font-weight:600;font-size:11px;white-space:nowrap;word-break:break-all;">{{ acc.cci }}</td>
            </tr>
            {% endfor %}
          </table>
          {% endif %}

          {% if operation.notes %}
          <div style="border-radius:6px;padding:13px 16px;margin:0 0 20px 0;font-size:13px;line-height:1.65;background:#FFFBEB;border-left:3px solid #F59E0B;color:#78350f;">
            <strong>Notas:</strong> {{ operation.notes }}
          </div>
          {% endif %}

          <div style="height:1px;background-color:#F1F5F9;margin:20px 0;"></div>
          <p style="margin:0 0 8px 0;font-size:13px;color:#334155;">Nuestro equipo procesará su operación a la brevedad posible y le mantendremos informado.</p>
          <p style="margin:0;font-size:12px;color:#94a3b8;">¿Consultas? Responda este correo o contacte a su asesor.</p>

        </td>
      </tr>"""
        from app.config.bank_accounts import get_accounts_for_currency, QORICASH_TITULAR, QORICASH_RUC
        return render_template_string(
            _wrap_email_svc(body),
            operation=operation,
            usd_accounts=get_accounts_for_currency('USD'),
            pen_accounts=get_accounts_for_currency('PEN'),
            qoricash_titular=QORICASH_TITULAR,
            qoricash_ruc=QORICASH_RUC,
        )

    @staticmethod
    def _render_completed_operation_template(operation):
        """Renderizar plantilla HTML para operación completada"""
        body = """
      <tr>
        <td class="email-body-cell" style="padding:32px 36px;color:#334155;font-size:14px;line-height:1.65;">

          <div style="margin:0 0 16px 0;">
            <span style="display:inline-block;background:#F0FDF4;color:#5CB85C;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.4px;padding:4px 10px;border-radius:4px;">✓ Operación Completada</span>
          </div>

          <h1 style="margin:0 0 6px 0;font-size:21px;font-weight:700;color:#0D1B2A;line-height:1.3;">Su operación fue procesada con éxito</h1>
          <p style="margin:0 0 24px 0;color:#64748b;font-size:14px;">Estimado(a) <strong style="color:#1e293b;">{{ operation.client.full_name or operation.client.razon_social }}</strong>, a continuación el detalle de su operación completada.</p>

          <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;margin:0 0 24px 0;">
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:11px 18px;width:160px;color:#94a3b8;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:top;">Código</td>
              <td style="padding:11px 18px;color:#0D1B2A;font-size:14px;font-weight:700;vertical-align:top;">{{ operation.operation_id }}</td>
            </tr>
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:11px 18px;width:160px;color:#94a3b8;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:top;">Tipo</td>
              <td style="padding:11px 18px;color:#1e293b;font-size:13px;font-weight:500;vertical-align:top;">{{ operation.operation_type }}</td>
            </tr>
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td colspan="2" style="padding:12px 18px;">
                <table width="100%" cellspacing="0" cellpadding="0">
                  <tr>
                    <td style="text-align:center;padding:13px 8px;background:#F8FAFC;border:1px solid #E2E8F0;border-radius:6px;">
                      <div style="font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Monto USD</div>
                      <div style="font-size:17px;font-weight:800;color:#0D1B2A;">$ {{ "{:,.2f}".format(operation.amount_usd) }}</div>
                    </td>
                    <td width="8">&nbsp;</td>
                    <td style="text-align:center;padding:13px 8px;background:#F8FAFC;border:1px solid #E2E8F0;border-radius:6px;">
                      <div style="font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Tipo de Cambio</div>
                      <div style="font-size:15px;font-weight:700;color:#1e293b;">{{ "%.4f"|format(operation.exchange_rate) }}</div>
                    </td>
                    <td width="8">&nbsp;</td>
                    <td style="text-align:center;padding:13px 8px;background:#F8FAFC;border:1px solid #E2E8F0;border-radius:6px;">
                      <div style="font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Monto PEN</div>
                      <div style="font-size:17px;font-weight:800;color:#0D1B2A;">S/ {{ "{:,.2f}".format(operation.amount_pen) }}</div>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:11px 18px;width:160px;color:#94a3b8;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:top;">Fecha de creación</td>
              <td style="padding:11px 18px;color:#1e293b;font-size:13px;font-weight:500;vertical-align:top;">{{ operation.created_at.strftime('%d/%m/%Y %H:%M') }}</td>
            </tr>
            <tr>
              <td style="padding:11px 18px;width:160px;color:#94a3b8;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:top;">Fecha de completado</td>
              <td style="padding:11px 18px;color:#1e293b;font-size:13px;font-weight:600;vertical-align:top;">{{ operation.completed_at.strftime('%d/%m/%Y %H:%M') if operation.completed_at else '-' }}</td>
            </tr>
          </table>

          {% if operation.operator_proofs and operation.operator_proofs|length > 0 %}
          <p style="margin:0 0 10px 0;font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1.2px;">Comprobante(s)</p>
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
        return render_template_string(_wrap_email_svc(body), operation=operation)

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
            cc = [e for e in ['gerencia@qoricash.pe'] if e not in set(to)]
            trader_email = operation.user.email if operation.user and operation.user.email else None

            if not to:
                logger.warning(f'No hay destinatarios para correo de cancelación de operación {operation.operation_id}')
                return False, 'No hay destinatarios configurados'

            subject = f'Operación Cancelada — {operation.operation_id} | QoriCash'
            html_body = EmailService._render_canceled_operation_template(operation, reason)

            msg = Message(
                subject=subject,
                sender=trader_email,
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
            to = [operation.client.email] if operation.client and operation.client.email else []
            cc = [e for e in ['gerencia@qoricash.pe'] if e not in set(to)]
            trader_email = operation.user.email if operation.user and operation.user.email else None

            if not to:
                logger.warning(f'No hay destinatarios para correo de modificación de monto {operation.operation_id}')
                return False, 'No hay destinatarios configurados'

            subject = f'Actualización de Importe — Operación {operation.operation_id} | QoriCash'
            html_body = EmailService._render_amount_modified_template(operation, old_amount_usd, old_amount_pen)

            msg = Message(
                subject=subject,
                sender=trader_email,
                recipients=to,
                cc=cc,
                html=html_body
            )

            EmailService._send_async(msg, timeout=15)
            logger.info(f'Email de modificación de monto programado para operación {operation.operation_id}')
            return True, 'Email programado para envío'

        except Exception as e:
            logger.error(f'Error al enviar email de modificación de monto {operation.operation_id}: {str(e)}')
            return False, f'Error al enviar email: {str(e)}'

    @staticmethod
    def _render_amount_modified_template(operation, old_amount_usd, old_amount_pen):
        """Renderizar plantilla HTML para notificación de modificación de importe"""
        body = """
      <tr>
        <td class="email-body-cell" style="padding:32px 36px;color:#334155;font-size:14px;line-height:1.65;">

          <div style="margin:0 0 16px 0;">
            <span style="display:inline-block;background:#FFFBEB;color:#F59E0B;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.4px;padding:4px 10px;border-radius:4px;">Actualización de Importe</span>
          </div>

          <h1 style="margin:0 0 6px 0;font-size:21px;font-weight:700;color:#0D1B2A;line-height:1.3;">Se actualizó el importe de su operación</h1>
          <p style="margin:0 0 24px 0;color:#64748b;font-size:14px;">Estimado(a) <strong style="color:#1e293b;">{{ operation.client.full_name or operation.client.razon_social }}</strong>, el importe de su operación <strong style="color:#0D1B2A;">{{ operation.operation_id }}</strong> ha sido actualizado por nuestro equipo.</p>

          <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;margin:0 0 16px 0;">
            <tr>
              <td style="padding:11px 18px;width:160px;color:#94a3b8;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:top;">Código</td>
              <td style="padding:11px 18px;color:#0D1B2A;font-size:14px;font-weight:700;vertical-align:top;">{{ operation.operation_id }}</td>
            </tr>
            <tr style="border-top:1px solid #F1F5F9;">
              <td style="padding:11px 18px;width:160px;color:#94a3b8;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:top;">Tipo de cambio</td>
              <td style="padding:11px 18px;color:#1e293b;font-size:13px;font-weight:500;vertical-align:top;">{{ "%.4f"|format(operation.exchange_rate) }}</td>
            </tr>
          </table>

          <p style="margin:0 0 10px 0;font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1.2px;">Detalle del cambio</p>
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
                <span style="color:#0D1B2A;font-weight:700;font-size:15px;">$ {{ "{:,.2f}".format(operation.amount_usd) }}</span>
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
                <span style="color:#0D1B2A;font-weight:700;font-size:15px;">S/ {{ "{:,.2f}".format(operation.amount_pen) }}</span>
              </td>
            </tr>
          </table>

          {% if operation.operation_type == 'Compra' %}
          <p style="margin:0 0 10px 0;font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1.2px;">Cuentas para transferencia (USD)</p>
          <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;margin:0 0 24px 0;font-size:13px;">
            <tr>
              <td colspan="5" style="padding:11px 16px;background-color:#F8FAFC;border-bottom:1px solid #E2E8F0;color:#334155;font-size:13px;font-weight:600;">
                Transfiera en <strong>DÓLARES</strong> el nuevo importe a cualquiera de estas cuentas &mdash; A nombre de {{ qoricash_titular }} &mdash; RUC {{ qoricash_ruc }}
              </td>
            </tr>
            <tr style="background-color:#0D1B2A;">
              <td style="padding:8px 12px;color:#94a3b8;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Banco</td>
              <td style="padding:8px 12px;color:#94a3b8;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Tipo</td>
              <td style="padding:8px 12px;color:#94a3b8;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Moneda</td>
              <td style="padding:8px 12px;color:#94a3b8;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">N° Cuenta</td>
              <td style="padding:8px 12px;color:#94a3b8;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">CCI</td>
            </tr>
            {% for acc in usd_accounts %}
            <tr style="border-top:1px solid #F1F5F9;">
              <td style="padding:9px 12px;color:#1e293b;font-weight:700;">{{ acc.banco }}</td>
              <td style="padding:9px 12px;color:#334155;">{{ acc.tipo }}</td>
              <td style="padding:9px 12px;color:#334155;">USD</td>
              <td style="padding:9px 12px;font-family:'Courier New',monospace;color:#0D1B2A;font-weight:600;font-size:11px;white-space:nowrap;">{{ acc.numero }}</td>
              <td style="padding:9px 12px;font-family:'Courier New',monospace;color:#0D1B2A;font-weight:600;font-size:11px;white-space:nowrap;word-break:break-all;">{{ acc.cci }}</td>
            </tr>
            {% endfor %}
          </table>
          {% elif operation.operation_type == 'Venta' %}
          <p style="margin:0 0 10px 0;font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1.2px;">Cuentas para transferencia (PEN)</p>
          <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;margin:0 0 24px 0;font-size:13px;">
            <tr>
              <td colspan="5" style="padding:11px 16px;background-color:#F8FAFC;border-bottom:1px solid #E2E8F0;color:#334155;font-size:13px;font-weight:600;">
                Transfiera en <strong>SOLES</strong> el nuevo importe a cualquiera de estas cuentas &mdash; A nombre de {{ qoricash_titular }} &mdash; RUC {{ qoricash_ruc }}
              </td>
            </tr>
            <tr style="background-color:#0D1B2A;">
              <td style="padding:8px 12px;color:#94a3b8;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Banco</td>
              <td style="padding:8px 12px;color:#94a3b8;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Tipo</td>
              <td style="padding:8px 12px;color:#94a3b8;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Moneda</td>
              <td style="padding:8px 12px;color:#94a3b8;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">N° Cuenta</td>
              <td style="padding:8px 12px;color:#94a3b8;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">CCI</td>
            </tr>
            {% for acc in pen_accounts %}
            <tr style="border-top:1px solid #F1F5F9;">
              <td style="padding:9px 12px;color:#1e293b;font-weight:700;">{{ acc.banco }}</td>
              <td style="padding:9px 12px;color:#334155;">{{ acc.tipo }}</td>
              <td style="padding:9px 12px;color:#334155;">PEN</td>
              <td style="padding:9px 12px;font-family:'Courier New',monospace;color:#0D1B2A;font-weight:600;font-size:11px;white-space:nowrap;">{{ acc.numero }}</td>
              <td style="padding:9px 12px;font-family:'Courier New',monospace;color:#0D1B2A;font-weight:600;font-size:11px;white-space:nowrap;word-break:break-all;">{{ acc.cci }}</td>
            </tr>
            {% endfor %}
          </table>
          {% endif %}

          <div style="border-radius:6px;padding:13px 16px;margin:0 0 20px 0;font-size:13px;line-height:1.65;background:#F0FDF4;border-left:3px solid #5CB85C;color:#14532d;">
            Si tiene alguna consulta sobre este cambio, responda este correo o contáctese directamente con su asesor.
          </div>

          <div style="height:1px;background-color:#F1F5F9;margin:20px 0;"></div>
          <p style="margin:0;font-size:12px;color:#94a3b8;">Este es un correo automático generado por el sistema QoriCash.</p>

        </td>
      </tr>"""
        from app.config.bank_accounts import get_accounts_for_currency, QORICASH_TITULAR, QORICASH_RUC
        return render_template_string(
            _wrap_email_svc(body),
            operation=operation,
            old_amount_usd=old_amount_usd,
            old_amount_pen=old_amount_pen,
            usd_accounts=get_accounts_for_currency('USD'),
            pen_accounts=get_accounts_for_currency('PEN'),
            qoricash_titular=QORICASH_TITULAR,
            qoricash_ruc=QORICASH_RUC,
        )

    @staticmethod
    def _render_canceled_operation_template(operation, reason=None):
        """Renderizar plantilla HTML para operación cancelada"""
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
              <td style="padding:11px 18px;width:160px;color:#94a3b8;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:top;">Código</td>
              <td style="padding:11px 18px;color:#0D1B2A;font-size:14px;font-weight:700;vertical-align:top;">{{ operation.operation_id }}</td>
            </tr>
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:11px 18px;width:160px;color:#94a3b8;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:top;">Tipo</td>
              <td style="padding:11px 18px;color:#1e293b;font-size:13px;font-weight:500;vertical-align:top;">{{ operation.operation_type }}</td>
            </tr>
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td colspan="2" style="padding:12px 18px;">
                <table width="100%" cellspacing="0" cellpadding="0">
                  <tr>
                    <td style="text-align:center;padding:13px 8px;background:#F8FAFC;border:1px solid #E2E8F0;border-radius:6px;">
                      <div style="font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Monto USD</div>
                      <div style="font-size:17px;font-weight:800;color:#0D1B2A;">$ {{ "{:,.2f}".format(operation.amount_usd) }}</div>
                    </td>
                    <td width="8">&nbsp;</td>
                    <td style="text-align:center;padding:13px 8px;background:#F8FAFC;border:1px solid #E2E8F0;border-radius:6px;">
                      <div style="font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Tipo de Cambio</div>
                      <div style="font-size:15px;font-weight:700;color:#1e293b;">{{ "%.4f"|format(operation.exchange_rate) }}</div>
                    </td>
                    <td width="8">&nbsp;</td>
                    <td style="text-align:center;padding:13px 8px;background:#F8FAFC;border:1px solid #E2E8F0;border-radius:6px;">
                      <div style="font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Monto PEN</div>
                      <div style="font-size:17px;font-weight:800;color:#0D1B2A;">S/ {{ "{:,.2f}".format(operation.amount_pen) }}</div>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:11px 18px;width:160px;color:#94a3b8;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:top;">Fecha</td>
              <td style="padding:11px 18px;color:#1e293b;font-size:13px;font-weight:500;vertical-align:top;">{{ operation.created_at.strftime('%d/%m/%Y %H:%M') }}</td>
            </tr>
            <tr>
              <td style="padding:11px 18px;width:160px;color:#94a3b8;font-size:12px;font-weight:600;white-space:nowrap;vertical-align:top;">Estado</td>
              <td style="padding:11px 18px;vertical-align:top;">
                <span style="display:inline-block;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700;background:#FEE2E2;color:#991B1B;letter-spacing:0.3px;">CANCELADO</span>
              </td>
            </tr>
          </table>

          {% if reason %}
          <div style="border-radius:6px;padding:13px 16px;margin:0 0 16px 0;font-size:13px;line-height:1.65;background:#FFFBEB;border-left:3px solid #F59E0B;color:#78350f;">
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
        return render_template_string(_wrap_email_svc(body), operation=operation, reason=reason)

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
            html_body = EmailService._render_new_client_template(client, trader)

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

            # Copia: Trader que registró al cliente (solo si es distinto al cliente)
            cc = []
            if trader and trader.email and trader.email not in to:
                cc.append(trader.email)

            # Copia oculta: Solo Master (excluir emails ya en to o cc)
            seen = set(to) | set(cc)
            bcc = []
            masters = User.query.filter(
                User.role == 'Master',
                User.status == 'Activo',
                User.email.isnot(None)
            ).all()

            for master in masters:
                if master.email and master.email not in seen:
                    bcc.append(master.email)
                    seen.add(master.email)

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
        body = """
      <tr>
        <td class="email-body-cell" style="padding:32px 36px;color:#334155;font-size:14px;line-height:1.65;">

          <div style="margin:0 0 16px 0;">
            <span style="display:inline-block;background:#F0FDF4;color:#5CB85C;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.4px;padding:4px 10px;border-radius:4px;">Acceso Seguro</span>
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

          <p style="margin:0 0 10px 0;font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1.2px;">Pasos a seguir</p>
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
        return render_template_string(_wrap_email_svc(body), client_name=client_name, temp_password=temp_password)

    @staticmethod
    def _render_new_client_template(client, trader):
        """Renderizar plantilla HTML para nuevo cliente registrado"""
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

          <div style="margin:0 0 16px 0;">
            <span style="display:inline-block;background:#FFFBEB;color:#D97706;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.4px;padding:4px 10px;border-radius:4px;">Registro Recibido</span>
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

          <div style="height:1px;background-color:#F1F5F9;margin:20px 0;"></div>
          <p style="margin:0 0 6px 0;font-size:13px;color:#334155;">Para cualquier consulta, contacte a su ejecutivo <strong>{{ trader.username }}</strong>{% if trader.email %} en <a href="mailto:{{ trader.email }}" style="color:#5CB85C;">{{ trader.email }}</a>{% endif %}.</p>
          <p style="margin:0;font-size:12px;color:#94a3b8;">Este es un correo automático.</p>
        </td>
      </tr>"""
        return render_template_string(_wrap_email_svc(body), client=client, trader=trader, bank_accounts_text=bank_accounts_text)

    @staticmethod
    def _render_client_activation_template(client, trader):
        """Renderizar plantilla HTML para cliente activado"""
        body = """
      <tr>
        <td class="email-body-cell" style="padding:32px 36px;color:#334155;font-size:14px;line-height:1.65;">

          <div style="margin:0 0 16px 0;">
            <span style="display:inline-block;background:#F0FDF4;color:#5CB85C;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.4px;padding:4px 10px;border-radius:4px;">✓ Cuenta Activada</span>
          </div>

          <h1 style="margin:0 0 6px 0;font-size:21px;font-weight:700;color:#0D1B2A;line-height:1.3;">¡Bienvenido(a) a QoriCash!</h1>
          <p style="margin:0 0 24px 0;color:#64748b;font-size:14px;">Estimado(a) <strong style="color:#1e293b;">{{ client.full_name or client.razon_social }}</strong>, su cuenta ha sido activada. Ya puede comenzar a operar.</p>

          <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;margin:0 0 24px 0;">
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:11px 18px;width:160px;color:#94a3b8;font-size:12px;font-weight:600;vertical-align:top;">Cliente</td>
              <td style="padding:11px 18px;color:#0D1B2A;font-size:13px;font-weight:600;vertical-align:top;">{{ client.full_name or client.razon_social }}</td>
            </tr>
            {% if client.document_number %}
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:11px 18px;color:#94a3b8;font-size:12px;font-weight:600;vertical-align:top;">Documento</td>
              <td style="padding:11px 18px;color:#1e293b;font-size:13px;vertical-align:top;">{{ client.document_number }}</td>
            </tr>
            {% endif %}
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:11px 18px;color:#94a3b8;font-size:12px;font-weight:600;vertical-align:top;">Email</td>
              <td style="padding:11px 18px;color:#1e293b;font-size:13px;vertical-align:top;">{{ client.email }}</td>
            </tr>
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:11px 18px;color:#94a3b8;font-size:12px;font-weight:600;vertical-align:top;">Estado</td>
              <td style="padding:11px 18px;color:#5CB85C;font-size:13px;font-weight:700;vertical-align:top;">ACTIVO</td>
            </tr>
            <tr>
              <td style="padding:11px 18px;color:#94a3b8;font-size:12px;font-weight:600;vertical-align:top;">Ejecutivo</td>
              <td style="padding:11px 18px;color:#5CB85C;font-size:13px;font-weight:600;vertical-align:top;">{{ trader.username }}</td>
            </tr>
          </table>

          <p style="margin:0 0 10px 0;font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1.2px;">¿Qué puede hacer ahora?</p>
          <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;margin:0 0 24px 0;">
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:10px 18px;color:#5CB85C;font-size:13px;">&#10003; &nbsp;Realizar operaciones de compra y venta de dólares</td>
            </tr>
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:10px 18px;color:#5CB85C;font-size:13px;">&#10003; &nbsp;Acceder a tipos de cambio competitivos</td>
            </tr>
            <tr style="border-bottom:1px solid #F1F5F9;">
              <td style="padding:10px 18px;color:#5CB85C;font-size:13px;">&#10003; &nbsp;Recibir atención personalizada de su ejecutivo</td>
            </tr>
            <tr>
              <td style="padding:10px 18px;color:#5CB85C;font-size:13px;">&#10003; &nbsp;Transferencias rápidas y seguras</td>
            </tr>
          </table>

          <table width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 24px 0;">
            <tr>
              <td align="center">
                <a href="https://www.qoricash.pe"
                   style="display:inline-block;background:#5CB85C;color:#ffffff;font-weight:700;font-size:14px;padding:13px 36px;border-radius:8px;text-decoration:none;letter-spacing:0.3px;">
                  Iniciar sesión ahora
                </a>
              </td>
            </tr>
          </table>

          <div style="height:1px;background-color:#F1F5F9;margin:0 0 20px 0;"></div>
          <p style="margin:0;font-size:12px;color:#94a3b8;">Para su primera operación, contacte a <strong>{{ trader.username }}</strong>{% if trader.email %} en <a href="mailto:{{ trader.email }}" style="color:#5CB85C;">{{ trader.email }}</a>{% endif %}. Gracias por confiar en QoriCash.</p>
        </td>
      </tr>"""
        return render_template_string(_wrap_email_svc(body), client=client, trader=trader)

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
        body = """
      <tr>
        <td class="email-body-cell" style="padding:32px 36px;color:#334155;font-size:14px;line-height:1.65;">

          <div style="margin:0 0 16px 0;">
            <span style="display:inline-block;background:#FEF2F2;color:#EF4444;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.4px;padding:4px 10px;border-radius:4px;">Libro de Reclamaciones</span>
          </div>

          <h1 style="margin:0 0 6px 0;font-size:21px;font-weight:700;color:#0D1B2A;line-height:1.3;">{{ complaint_data.get('tipo_solicitud', 'Reclamo') }} recibido</h1>
          <p style="margin:0 0 24px 0;color:#64748b;font-size:14px;">N° <strong style="color:#1e293b;">{{ complaint_number }}</strong> &nbsp;&middot;&nbsp; {{ fecha_actual }}</p>

          <p style="margin:0 0 10px 0;font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1.2px;">Datos del reclamante</p>
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

          <p style="margin:0 0 10px 0;font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1.2px;">Detalle del {{ complaint_data.get('tipo_solicitud', 'reclamo') }}</p>
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
        return render_template_string(
            _wrap_email_svc(body),
            complaint_data=complaint_data,
            fecha_actual=fecha_actual,
            complaint_number=complaint_number
        )

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
                title=f'🔔 Cambio de precio — {competitor_name}',
                body_html=body_html,
                subtitle=f'Monitor de Competencia · {hora}',
            )

            msg = Message(
                subject=f'[QoriCash Monitor] {competitor_name} cambió su precio',
                recipients=recipients,
                html=html_content,
            )
            mail.send(msg)
            logger.info(f'[EMAIL] Alerta FX enviada a {recipients} — {competitor_name}')

        except Exception as e:
            logger.warning(f'[EMAIL] No se pudo enviar alerta FX: {e}')
