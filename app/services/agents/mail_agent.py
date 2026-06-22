"""
Agente 1: Prospecting Mail Agent
Ejecuta campañas de email automáticas desde las 3 bandejas de QoriCash.
Lee prospectos pendientes, envía correos de presentación/seguimiento y actualiza el CRM.
"""
import logging
import os
import base64
from datetime import datetime, timedelta, timezone
from .base import BaseAgent

_log = logging.getLogger(__name__)
_LIMA = timezone(timedelta(hours=-5))

# Bandejas y sus refresh token env vars
_BANDEJAS = {
    'ggarcia@qoricash.pe':  'GMAIL_REFRESH_TOKEN_GGARCIA',
    'gerencia@qoricash.pe': 'GMAIL_REFRESH_TOKEN_GERENCIA',
    'info@qoricash.pe':     'GMAIL_REFRESH_TOKEN_INFO',
}

_EXCLUDE_ESTADOS = {'NO CONTACTAR', 'REBOTE', 'INVALIDO', 'cliente', 'P4'}
_DIAS_HABIL_ESPERA = 5


def _business_days_since(date_str: str) -> int:
    """Días hábiles desde la fecha dada hasta hoy."""
    if not date_str:
        return 999
    try:
        from app.utils.formatters import now_peru
        last = datetime.strptime(date_str[:10], '%Y-%m-%d').date()
        today = now_peru().date()
        count = 0
        d = last + timedelta(days=1)
        while d <= today:
            if d.weekday() < 5:
                count += 1
            d += timedelta(days=1)
        return count
    except Exception:
        return 999


class MailAgent(BaseAgent):
    agent_id     = 'mail_agent'
    name         = 'Prospecting Mail Agent'
    description  = 'Envía campañas de presentación y seguimiento desde las 3 bandejas'
    icon         = 'bi-envelope-paper'
    color        = 'green'
    run_interval = 1800  # cada 30 min

    def _execute(self, app) -> dict:
        from app.models.prospecto import Prospecto, ActividadProspecto
        from app.extensions import db
        from app.utils.formatters import now_peru

        with app.app_context():
            sent_total = 0
            skipped = 0

            # Obtener tipo de cambio actual para incluir en email
            tc = self._get_tc()

            # Prospectos elegibles: sin contacto O +5 días hábiles desde último envío
            # Excluir estados no contactar, rebote, etc.
            prospectos = (Prospecto.query
                          .filter(
                              ~Prospecto.estado_comercial.in_(_EXCLUDE_ESTADOS),
                              ~Prospecto.estado_email.in_({'REBOTE', 'INVALIDO', 'NO CONTACTAR'}),
                              Prospecto.email.isnot(None),
                              Prospecto.email != '',
                          )
                          .order_by(Prospecto.fecha_ultimo_contacto.asc().nullsfirst())
                          .limit(150)
                          .all())

            eligible = []
            for p in prospectos:
                if _business_days_since(p.fecha_ultimo_contacto) >= _DIAS_HABIL_ESPERA:
                    eligible.append(p)

            # Limitar a 50 por ciclo para no saturar Gmail
            eligible = eligible[:50]

            for p in eligible:
                try:
                    bandeja = self._pick_bandeja(p)
                    if not bandeja:
                        skipped += 1
                        continue

                    html = self._build_email(p, bandeja, tc)
                    subject = f'Qoricash — Cambio de dólares para {p.razon_social or p.nombre_contacto or "su empresa"}'

                    ok = self._send_via_gmail(bandeja, p.email, subject, html)
                    if not ok:
                        skipped += 1
                        continue

                    # Actualizar prospecto
                    hoy = now_peru().strftime('%Y-%m-%d')
                    next_date = self._next_business_day(5)
                    p.fecha_primer_contacto = p.fecha_primer_contacto or hoy
                    p.fecha_ultimo_contacto = hoy
                    p.fecha_proximo_contacto = next_date
                    p.num_contactos = (p.num_contactos or 0) + 1
                    p.estado_comercial = p.estado_comercial or 'presentado'
                    p.remitente = bandeja
                    p.tipo_ultimo_envio = 'presentacion'

                    # Registrar actividad
                    from app.models.user import User
                    bot_user = User.query.filter_by(role='Master').first()
                    if bot_user:
                        act = ActividadProspecto(
                            prospecto_id=p.id,
                            user_id=bot_user.id,
                            tipo='email',
                            canal='email',
                            bandeja=bandeja,
                            descripcion=f'Email de presentación enviado por Mail Agent',
                            resultado='enviado',
                            nuevo_estado=p.estado_comercial,
                        )
                        db.session.add(act)

                    db.session.flush()
                    sent_total += 1

                except Exception as e:
                    _log.warning(f'[MailAgent] Error enviando a {p.email}: {e}')
                    skipped += 1

            db.session.commit()
            msg = f'Campaña: {sent_total} emails enviados · {skipped} omitidos'
            return {
                'tasks':   sent_total,
                'message': msg,
                'metrics': {'emails_sent': sent_total},
            }

    def _get_tc(self) -> dict:
        try:
            from app.models.exchange_rate import ExchangeRate
            tc = ExchangeRate.query.order_by(ExchangeRate.updated_at.desc()).first()
            if tc:
                return {'compra': float(tc.compra), 'venta': float(tc.venta)}
        except Exception:
            pass
        return {'compra': 3.38, 'venta': 3.42}

    def _pick_bandeja(self, prospecto) -> str:
        """Elegir bandeja según balance: rotación round-robin simplificada."""
        bandejas = list(_BANDEJAS.keys())
        import hashlib
        idx = int(hashlib.md5((prospecto.email or '').encode()).hexdigest(), 16) % len(bandejas)
        return bandejas[idx]

    def _next_business_day(self, days: int) -> str:
        from app.utils.formatters import now_peru
        d = now_peru().date()
        added = 0
        while added < days:
            d += timedelta(days=1)
            if d.weekday() < 5:
                added += 1
        return d.strftime('%Y-%m-%d')

    def _build_email(self, p, bandeja: str, tc: dict) -> str:
        nombre = p.razon_social or p.nombre_contacto or 'Estimado'
        compra = f"S/ {tc['compra']:.3f}"
        venta  = f"S/ {tc['venta']:.3f}"
        return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head><body style="margin:0;padding:0;background:#F1F5F9;">
<table width="100%" cellpadding="0" cellspacing="0">
<tr><td align="center" style="padding:24px 16px;">
<table width="600" style="background:#fff;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.07);">
<tr><td style="padding:28px 36px 8px;">
<p style="font-family:Arial,sans-serif;font-size:15px;color:#1e293b;">
Estimado equipo de <strong>{nombre}</strong>,</p>
<p style="font-family:Arial,sans-serif;font-size:14px;color:#475569;line-height:1.7;">
Somos <strong>QoriCash</strong>, casa de cambio digital autorizada por la SBS, especializada en
operaciones de cambio de divisas para empresas. Ofrecemos tipos de cambio superiores al bancario,
sin comisiones, con atención personalizada y transferencias inmediatas.</p>
<table style="margin:20px 0;padding:16px 20px;background:#f8fafc;border-left:4px solid #16a34a;
              border-radius:4px;width:100%;box-sizing:border-box;">
<tr>
  <td style="font-family:Arial,sans-serif;font-size:12px;color:#64748b;
             text-transform:uppercase;letter-spacing:.06em;">TIPO DE CAMBIO HOY</td>
</tr>
<tr>
  <td>
    <span style="font-size:22px;font-weight:800;color:#0D1B2A;">
      Compramos: {compra}</span>&nbsp;&nbsp;
    <span style="font-size:22px;font-weight:800;color:#16a34a;">
      Vendemos: {venta}</span>
  </td>
</tr>
</table>
<p style="font-family:Arial,sans-serif;font-size:14px;color:#475569;line-height:1.7;">
¿Le gustaría recibir una cotización para sus próximas operaciones de cambio?
Con gusto coordinamos una reunión o enviamos nuestra presentación institucional.</p>
<p style="margin-top:20px;">
<a href="https://qoricash.pe" style="background:#0D1B2A;color:#fff;padding:10px 22px;
   border-radius:5px;text-decoration:none;font-family:Arial,sans-serif;
   font-size:13px;font-weight:700;">Ver presentación →</a></p>
</td></tr>
<tr><td style="padding:12px 36px 24px;font-family:Arial,sans-serif;font-size:12px;color:#94a3b8;">
RUC 20607547139 · Autorizado SBS · <a href="mailto:info@qoricash.pe"
style="color:#94a3b8;">info@qoricash.pe</a>
</td></tr>
</table></td></tr></table></body></html>"""

    def _send_via_gmail(self, sender: str, to: str, subject: str, html: str) -> bool:
        try:
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build

            env_key = _BANDEJAS.get(sender)
            if not env_key:
                return False
            refresh_token = os.environ.get(env_key, '').strip()
            client_id     = os.environ.get('GMAIL_CLIENT_ID', '')
            client_secret = os.environ.get('GMAIL_CLIENT_SECRET', '')
            if not all([refresh_token, client_id, client_secret]):
                _log.warning(f'[MailAgent] Credenciales Gmail faltantes para {sender}')
                return False

            creds = Credentials(
                token=None, refresh_token=refresh_token,
                token_uri='https://oauth2.googleapis.com/token',
                client_id=client_id, client_secret=client_secret,
                scopes=['https://mail.google.com/'],
            )
            creds.refresh(Request())
            service = build('gmail', 'v1', credentials=creds)

            msg = MIMEMultipart('alternative')
            msg['From']    = sender
            msg['To']      = to
            msg['Subject'] = subject
            msg.attach(MIMEText(html, 'html'))

            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            service.users().messages().send(userId='me', body={'raw': raw}).execute()
            return True

        except Exception as e:
            _log.error(f'[MailAgent] Gmail send error ({sender} → {to}): {e}')
            return False
