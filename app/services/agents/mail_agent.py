"""
Agente 3: Prospecting Mail Agent — QoriCash
Ejecuta campañas de email automáticas desde las 3 bandejas de QoriCash.
Usa la plantilla oficial de prospección con imagen de marca.

Límites:
  - 490 emails / bandeja / día (margen bajo el límite Gmail de 500)
  - 15 emails / bandeja / ciclo de 30 min
"""
import logging
import os
import base64
from datetime import timedelta, timezone
from .base import BaseAgent

_log = logging.getLogger(__name__)
_LIMA = timezone(timedelta(hours=-5))

_BANDEJAS = {
    'ggarcia@qoricash.pe':  'GMAIL_REFRESH_TOKEN_GGARCIA',
    'gerencia@qoricash.pe': 'GMAIL_REFRESH_TOKEN_GERENCIA',
    'info@qoricash.pe':     'GMAIL_REFRESH_TOKEN_INFO',
}

# Nombre del remitente por bandeja (para el cuerpo del email)
_BANDEJA_NOMBRE = {
    'ggarcia@qoricash.pe':  'Giancarlo García',
    'gerencia@qoricash.pe': 'Gerencia QoriCash',
    'info@qoricash.pe':     'Equipo QoriCash',
}

_EXCLUDE_ESTADOS   = {'NO CONTACTAR', 'REBOTE', 'INVALIDO', 'cliente', 'P4'}
_DIAS_HABIL_ESPERA = 5
_DAILY_LIMIT       = 490   # margen de seguridad bajo el límite Gmail de 500
_BATCH_PER_CYCLE   = 15    # máx por bandeja por ciclo (3 × 15 = 45 / ciclo)

# ─────────────────────────────────────────────────────────────────
# Templates oficiales QoriCash (idénticos a prospeccion.py)
# Usamos marcadores __XXXXX__ para evitar conflictos con .format()
# ─────────────────────────────────────────────────────────────────
_LOGO = "https://www.qoricash.pe/logofirma.png"

_HEADER = (
    '<tr>'
    '  <td style="background:#0D1B2A;padding:18px 28px;">'
    '    <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
    '      <td><img src="' + _LOGO + '" alt="QoriCash" height="32" style="display:block;height:32px;"></td>'
    '      <td style="padding-left:6px;vertical-align:middle;">'
    '        <span style="font-size:14px;font-weight:800;color:#FFFFFF;letter-spacing:2px;">QORICASH</span>'
    '      </td>'
    '      <td align="right">'
    '        <span style="font-size:10px;font-weight:700;color:#5CB85C;text-transform:uppercase;'
    '                     letter-spacing:1.5px;background:rgba(92,184,92,.12);'
    '                     padding:4px 10px;border-radius:20px;border:1px solid rgba(92,184,92,.3);">'
    '          __FECHA__'
    '        </span>'
    '      </td>'
    '    </tr></table>'
    '  </td>'
    '</tr>'
)

_BANCOS = (
    '<tr><td style="padding:20px 28px 8px;">'
    '<p style="margin:0 0 12px;font-size:10px;font-weight:900;color:#94A3B8;text-transform:uppercase;letter-spacing:1.4px;">'
    '<strong>Operamos con los principales bancos del Per&uacute;</strong></p>'
    '<table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:12px;">'
    '<tr><td style="border-left:3px solid #5CB85C;padding-left:10px;">'
    '<p style="margin:0;font-size:10px;font-weight:700;color:#0D1B2A;">QORICASH S.A.C.</p>'
    '<p style="margin:2px 0 0;font-size:9px;color:#94A3B8;">RUC 20615113698 &nbsp;&middot;&nbsp; Regulada por la SBS</p>'
    '</td></tr></table>'
    '<table width="100%" cellpadding="0" cellspacing="0" border="0"'
    '       style="border:1px solid #E9EEF4;border-radius:10px;overflow:hidden;margin-bottom:16px;">'
    '<tr style="border-bottom:1px solid #F1F5F9;">'
    '<td style="width:90px;padding:12px 8px 12px 18px;vertical-align:middle;">'
    '<span style="font-size:15px;font-weight:800;color:#F97316;">BCP</span></td>'
    '<td style="padding:14px 12px;vertical-align:middle;border-left:1px solid #F1F5F9;">'
    '<p style="margin:0;font-size:9px;color:#94A3B8;text-transform:uppercase;">Soles</p>'
    '<p style="margin:2px 0 0;font-size:12px;font-weight:700;color:#1E293B;">1937353150041</p></td>'
    '<td style="padding:14px 18px 14px 12px;vertical-align:middle;border-left:1px solid #F1F5F9;">'
    '<p style="margin:0;font-size:9px;color:#94A3B8;text-transform:uppercase;">D&oacute;lares</p>'
    '<p style="margin:2px 0 0;font-size:12px;font-weight:700;color:#1E293B;">1917357790119</p></td>'
    '</tr>'
    '<tr style="border-bottom:1px solid #F1F5F9;background:#FAFBFC;">'
    '<td style="width:90px;padding:12px 8px 12px 18px;vertical-align:middle;">'
    '<span style="font-size:15px;font-weight:800;color:#00A859;">Interbank</span></td>'
    '<td style="padding:14px 12px;vertical-align:middle;border-left:1px solid #F1F5F9;">'
    '<p style="margin:0;font-size:9px;color:#94A3B8;text-transform:uppercase;">Soles</p>'
    '<p style="margin:2px 0 0;font-size:12px;font-weight:700;color:#1E293B;">200-3007757571</p></td>'
    '<td style="padding:14px 18px 14px 12px;vertical-align:middle;border-left:1px solid #F1F5F9;">'
    '<p style="margin:0;font-size:9px;color:#94A3B8;text-transform:uppercase;">D&oacute;lares</p>'
    '<p style="margin:2px 0 0;font-size:12px;font-weight:700;color:#1E293B;">200-3007757589</p></td>'
    '</tr>'
    '<tr>'
    '<td style="width:90px;padding:12px 8px 12px 18px;vertical-align:middle;">'
    '<span style="font-size:15px;font-weight:800;color:#004B9D;">BanBif</span></td>'
    '<td style="padding:14px 12px;vertical-align:middle;border-left:1px solid #F1F5F9;">'
    '<p style="margin:0;font-size:9px;color:#94A3B8;text-transform:uppercase;">Soles</p>'
    '<p style="margin:2px 0 0;font-size:12px;font-weight:700;color:#1E293B;">007000845805</p></td>'
    '<td style="padding:14px 18px 14px 12px;vertical-align:middle;border-left:1px solid #F1F5F9;">'
    '<p style="margin:0;font-size:9px;color:#94A3B8;text-transform:uppercase;">D&oacute;lares</p>'
    '<p style="margin:2px 0 0;font-size:12px;font-weight:700;color:#1E293B;">007000845813</p></td>'
    '</tr>'
    '</table>'
    '<p style="margin:0 0 20px;font-size:10px;color:#64748B;line-height:1.6;">'
    '<strong>Transferencia interbancaria (CCI) disponible desde BBVA, Scotiabank, Pichincha'
    ' y cualquier banco del Per&uacute;.</strong></p>'
    '<table cellpadding="0" cellspacing="0" border="0" style="margin-bottom:24px;">'
    '<tr><td style="border-radius:7px;background:#0D1B2A;box-shadow:0 4px 14px rgba(13,27,42,.25);">'
    '<a href="https://wa.me/51926011920"'
    '   style="display:inline-block;padding:13px 30px;color:#FFFFFF;text-decoration:none;'
    '          font-size:12px;font-weight:700;letter-spacing:0.8px;">'
    'Cotizar en l&iacute;nea &nbsp;&rarr;</a>'
    '</td></tr></table>'
    '</td></tr>'
)

_FIRMA_TPL = (
    '<tr><td style="padding:16px 28px;border-top:1px solid #F1F5F9;background:#FAFAFA;">'
    '<table cellpadding="0" cellspacing="0" border="0"><tr>'
    '<td style="padding-right:12px;vertical-align:middle;">'
    '<img src="' + _LOGO + '" width="32" height="32" alt="QoriCash" style="display:block;border-radius:4px;"></td>'
    '<td style="vertical-align:middle;padding-right:24px;">'
    '<p style="margin:0;font-size:12px;font-weight:700;color:#0D1B2A;">__TRADER_NOMBRE__</p>'
    '<p style="margin:1px 0 0;font-size:10px;color:#5CB85C;font-weight:600;">__TRADER_CARGO__</p></td>'
    '<td style="width:1px;background:#E2E8F0;padding:0;"></td>'
    '<td style="width:24px;"></td>'
    '<td style="vertical-align:middle;">'
    '<p style="margin:0;font-size:10px;color:#64748B;">'
    '<a href="https://wa.me/51926011920" style="color:#64748B;text-decoration:none;">+51 926 011 920</a>'
    ' &nbsp;&middot;&nbsp; '
    '<a href="https://www.qoricash.pe" style="color:#5CB85C;text-decoration:none;font-weight:600;">www.qoricash.pe</a></p>'
    '<p style="margin:2px 0 0;font-size:9px;color:#94A3B8;">Av. Brasil 2790, int. 504 &mdash; Pueblo Libre</p>'
    '</td>'
    '</tr></table>'
    '</td></tr>'
)

_PIE = (
    '<tr><td style="padding:12px 28px;background:#F8FAFC;border-top:1px solid #F1F5F9;">'
    '<p style="margin:0;font-size:9px;color:#CBD5E1;text-align:center;">'
    'Regulada por la SBS &nbsp;&middot;&nbsp; Res. N.&ordm; 00313-2026 &nbsp;&middot;&nbsp;'
    'Precios sujetos a variaci&oacute;n &nbsp;&middot;&nbsp;'
    'Para no recibir m&aacute;s comunicaciones, responda con asunto <em>NO CONTACTAR</em>.'
    '</p>'
    '</td></tr>'
)

_BODY_TPL = (
    '<!DOCTYPE html>'
    '<html lang="es"><head><meta charset="UTF-8"></head>'
    '<body style="margin:0;padding:0;background:#F4F6F8;font-family:Arial,sans-serif;">'
    '<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#F4F6F8;padding:32px 0;">'
    '<tr><td align="center">'
    '<table width="600" cellpadding="0" cellspacing="0" border="0"'
    '  style="max-width:600px;width:100%;background:#FFFFFF;border-radius:12px;overflow:hidden;'
    '         box-shadow:0 2px 12px rgba(0,0,0,.07);">'
    '__HEADER__'
    '<tr><td style="padding:24px 28px 8px;">'
    '<p style="margin:0 0 12px;font-size:14px;color:#1E293B;">'
    'Estimado(a) <strong>__NOMBRE__</strong>,</p>'
    '<p style="margin:0 0 12px;font-size:14px;color:#475569;line-height:1.7;text-align:justify;">'
    '__PRESENTACION__</p>'
    '<p style="margin:0 0 12px;font-size:14px;color:#475569;line-height:1.7;text-align:justify;">'
    'Trabajamos con empresas que realizan operaciones frecuentes de compra y venta de d&oacute;lares,'
    ' y que en muchos casos est&aacute;n dejando dinero sobre la mesa al operar con el tipo de cambio'
    ' que les ofrece su entidad financiera actual.</p>'
    '<p style="margin:0 0 12px;font-size:14px;color:#475569;line-height:1.7;text-align:justify;">'
    'Le ofrecemos <strong>tasas que superan consistentemente al sistema bancario tradicional</strong>,'
    ' sin comisiones, con ejecuci&oacute;n inmediata y atenci&oacute;n personalizada.</p>'
    '<div style="background:#F7F9FC;border-left:4px solid #4CAF50;border-radius:4px;'
    '            padding:14px 18px;margin:20px 0;">'
    '<p style="margin:0 0 4px;font-weight:bold;color:#0D1B2A;font-size:13px;">Le propongo algo concreto:</p>'
    '<p style="margin:0;color:#4A5568;font-size:13px;text-align:justify;">'
    'Una comparativa sin compromiso entre las tasas que recibe hoy de su proveedor actual'
    ' y las que podemos ofrecerle en QoriCash, en tiempo real.</p>'
    '</div>'
    '<p style="margin:0 0 16px;font-size:14px;color:#475569;">'
    'Si desea conocer m&aacute;s, puede ver nuestra presentaci&oacute;n institucional:</p>'
    '<table cellpadding="0" cellspacing="0" border="0" style="margin-bottom:20px;">'
    '<tr><td style="border-radius:6px;background:linear-gradient(135deg,#5CB85C 0%,#4a9b4a 100%);">'
    '<a href="https://qoricash.pe/presentacion.pdf"'
    '   style="display:inline-block;padding:11px 26px;color:#FFFFFF;text-decoration:none;'
    '          font-size:13px;font-weight:700;letter-spacing:0.3px;" target="_blank">'
    'Ver presentaci&oacute;n QoriCash &rarr;</a>'
    '</td></tr></table>'
    '<p style="margin:0 0 4px;font-size:13px;color:#475569;">'
    'Contamos con cuentas en los principales bancos del Per&uacute;:</p>'
    '</td></tr>'
    '__BANCOS__'
    '__FIRMA__'
    '__PIE__'
    '</table>'
    '</td></tr>'
    '</table>'
    '</body></html>'
)


def _business_days_since(date_str: str) -> int:
    """Días hábiles transcurridos desde date_str hasta hoy."""
    if not date_str:
        return 999
    try:
        from datetime import datetime
        from app.utils.formatters import now_peru
        last  = datetime.strptime(date_str[:10], '%Y-%m-%d').date()
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
    description  = 'Envía campañas de presentación desde las 3 bandejas · límite 490/bandeja/día'
    icon         = 'bi-envelope-paper'
    color        = 'green'
    run_interval = 1800  # cada 30 min

    def _execute(self, app) -> dict:
        from app.models.prospecto import Prospecto, ActividadProspecto
        from app.extensions import db
        from app.utils.formatters import now_peru
        from collections import defaultdict

        with app.app_context():
            sent_total = 0
            skipped    = 0
            today      = now_peru().date()

            # Usuario bot para registrar actividades
            from app.models.user import User
            bot_user  = User.query.filter_by(role='Master').first()
            bot_cargo = 'Ejecutivo Comercial'

            # Prospectos elegibles (más desactualizados primero)
            prospectos = (Prospecto.query
                          .filter(
                              ~Prospecto.estado_comercial.in_(_EXCLUDE_ESTADOS),
                              ~Prospecto.estado_email.in_({'REBOTE', 'INVALIDO', 'NO CONTACTAR'}),
                              Prospecto.email.isnot(None),
                              Prospecto.email != '',
                          )
                          .order_by(Prospecto.fecha_ultimo_contacto.asc().nullsfirst())
                          .limit(600)
                          .all())

            # Filtrar por días hábiles de espera
            eligible = [p for p in prospectos
                        if _business_days_since(p.fecha_ultimo_contacto) >= _DIAS_HABIL_ESPERA]

            # Agrupar por bandeja
            por_bandeja = defaultdict(list)
            for p in eligible:
                por_bandeja[self._pick_bandeja(p)].append(p)

            for bandeja in list(_BANDEJAS.keys()):
                prospects_q = por_bandeja.get(bandeja, [])
                if not prospects_q:
                    continue

                # Respetar límite diario por bandeja
                sent_today = self._daily_sent_count(db, bandeja, today)
                remaining  = _DAILY_LIMIT - sent_today
                if remaining <= 0:
                    _log.info(f'[MailAgent] {bandeja}: límite diario alcanzado ({sent_today})')
                    continue

                batch      = prospects_q[:min(_BATCH_PER_CYCLE, remaining)]
                bot_nombre = _BANDEJA_NOMBRE.get(bandeja, 'Equipo QoriCash')

                for p in batch:
                    try:
                        html    = self._build_email(p, bandeja, bot_nombre, bot_cargo)
                        subject = 'QoriCash - El mejor tipo de cambio para empresas'

                        ok = self._send_via_gmail(bandeja, p.email, subject, html)
                        if not ok:
                            skipped += 1
                            continue

                        hoy_str   = now_peru().strftime('%Y-%m-%d')
                        next_date = self._next_business_day(5)
                        p.fecha_primer_contacto  = p.fecha_primer_contacto or hoy_str
                        p.fecha_ultimo_contacto  = hoy_str
                        p.fecha_proximo_contacto = next_date
                        p.num_contactos          = (p.num_contactos or 0) + 1
                        p.estado_comercial       = p.estado_comercial or 'presentado'
                        p.remitente              = bandeja
                        p.tipo_ultimo_envio      = 'presentacion'

                        if bot_user:
                            act = ActividadProspecto(
                                prospecto_id=p.id,
                                user_id=bot_user.id,
                                tipo='email',
                                canal='email',
                                bandeja=bandeja,
                                descripcion='Email de presentación enviado por Mail Agent',
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

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _daily_sent_count(self, db, bandeja: str, today) -> int:
        """Emails enviados hoy por esta bandeja (desde ActividadProspecto)."""
        from app.models.prospecto import ActividadProspecto
        from sqlalchemy import func
        try:
            return (db.session.query(func.count(ActividadProspecto.id))
                    .filter(
                        ActividadProspecto.canal   == 'email',
                        ActividadProspecto.bandeja == bandeja,
                        func.date(ActividadProspecto.creado_en) == today,
                    ).scalar() or 0)
        except Exception:
            return 0

    def _pick_bandeja(self, prospecto) -> str:
        """Bandeja consistente por hash del email (round-robin estable)."""
        import hashlib
        bandejas = list(_BANDEJAS.keys())
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

    def _build_email(self, p, bandeja: str, bot_nombre: str, bot_cargo: str) -> str:
        """Construye el HTML con la plantilla oficial de prospección."""
        from app.utils.formatters import now_peru
        nombre = ((p.nombre_contacto or p.razon_social or 'estimado cliente')
                  .split()[0].capitalize())
        fecha  = now_peru().strftime('%d/%m/%Y')

        header = _HEADER.replace('__FECHA__', fecha)
        firma  = (_FIRMA_TPL
                  .replace('__TRADER_NOMBRE__', bot_nombre)
                  .replace('__TRADER_CARGO__',  bot_cargo))

        presentacion = (
            f'Mi nombre es <strong>{bot_nombre}</strong>, Ejecutivo Comercial de '
            '<strong>QoriCash SAC</strong>, fintech de cambio de divisas 100&#37; digital, '
            'regulada por la Superintendencia de Banca, Seguros y AFP del Per&uacute;.'
        )

        return (_BODY_TPL
                .replace('__HEADER__',       header)
                .replace('__NOMBRE__',       nombre)
                .replace('__PRESENTACION__', presentacion)
                .replace('__BANCOS__',       _BANCOS)
                .replace('__FIRMA__',        firma)
                .replace('__PIE__',          _PIE))

    def _send_via_gmail(self, sender: str, to: str, subject: str, html: str) -> bool:
        try:
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build

            env_key       = _BANDEJAS.get(sender)
            refresh_token = os.environ.get(env_key or '', '').strip()
            client_id     = os.environ.get('GMAIL_CLIENT_ID', '')
            client_secret = os.environ.get('GMAIL_CLIENT_SECRET', '')

            if not all([env_key, refresh_token, client_id, client_secret]):
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
