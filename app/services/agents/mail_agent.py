"""
Agente 3: Prospecting Mail Agent — QoriCash
Ejecuta campañas de email automáticas desde las 3 bandejas de QoriCash.
Usa la plantilla oficial con imagen de encabezado y logos de bancos embebidos (CID).

Límites:
  - 490 emails / bandeja / día (margen bajo el límite Gmail de 500)
  - 15 emails / bandeja / ciclo de 30 min
  - Horario: lunes a viernes, 09:00–13:30 Lima
"""
import logging
import os
import base64
from datetime import timedelta, timezone, date
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText
from email.mime.image     import MIMEImage
from email.utils          import formatdate, make_msgid
from .base import BaseAgent

_log = logging.getLogger(__name__)
_LIMA = timezone(timedelta(hours=-5))

_BANDEJAS = {
    'ggarcia@qoricash.pe':  'GMAIL_REFRESH_TOKEN_GGARCIA',
    'gerencia@qoricash.pe': 'GMAIL_REFRESH_TOKEN_GERENCIA',
    'info@qoricash.pe':     'GMAIL_REFRESH_TOKEN_INFO',
}

_BANDEJA_NOMBRE = {
    'ggarcia@qoricash.pe':  'Gian Pierre García',
    'gerencia@qoricash.pe': 'QoriCash',
    'info@qoricash.pe':     'QoriCash',
}

_BANDEJA_CARGO = {
    'ggarcia@qoricash.pe':  'Presidente de Negocios',
    'gerencia@qoricash.pe': 'Equipo Comercial',
    'info@qoricash.pe':     'Equipo Comercial',
}

_EXCLUDE_ESTADOS   = {'NO CONTACTAR', 'REBOTE', 'INVALIDO', 'cliente', 'P4', 'negociando', 'negociacion', 'P3'}
_EXCLUDE_EMAIL_EST = {'REBOTE', 'INVALIDO', 'NO CONTACTAR'}
_DIAS_HABIL_ESPERA = 5
_CALENDAR_DAYS_APPROX = 7   # 5 días hábiles ≈ 7 calendario — filtro SQL previo
_DAILY_LIMIT       = 490
_BATCH_PER_CYCLE   = 15

# Rutas de imágenes embebidas (relativas al módulo)
_STATIC_IMAGES = os.path.join(
    os.path.dirname(__file__), '..', '..', 'static', 'images'
)
_IMG_ENCABEZADO = os.path.join(_STATIC_IMAGES, 'encabezado_prospeccion.jpg')
_IMG_BCP        = os.path.join(_STATIC_IMAGES, 'bcp_logo.png')
_IMG_INTERBANK  = os.path.join(_STATIC_IMAGES, 'interbank_logo.png')
_IMG_BANBIF     = os.path.join(_STATIC_IMAGES, 'banbif_logo.png')

LOGO = 'https://www.qoricash.pe/logofirma.png'

# ─────────────────────────────────────────────────────────────────
# Plantilla HTML oficial unificada (empresa + persona natural)
# ─────────────────────────────────────────────────────────────────

def _build_html(nombre_dest: str, nombre_firma: str, cargo: str,
                compra: str, venta: str, hoy: str, es_personal: bool) -> str:
    if es_personal:
        intro = (
            f'Mi nombre es <strong>{nombre_firma}</strong>, Presidente de Negocios de '
            '<strong>QoriCash SAC</strong>, casa de cambio digital inscrita en el '
            'Registro de Casas de Cambio de la SBS.<br><br>'
            'Ayudamos a empresas y personas a obtener mejores tasas de cambio que la '
            'banca tradicional, con operaciones r&aacute;pidas, seguras y sin comisiones '
            'adicionales.<br><br>'
            'Le compartimos nuestras tasas referenciales del momento y quedamos atentos '
            'a cualquier consulta o cotizaci&oacute;n que requiera.'
        )
    else:
        intro = (
            'Somos <strong>QoriCash SAC</strong>, casa de cambio digital inscrita en el '
            'Registro de Casas de Cambio de la SBS.<br><br>'
            'Ayudamos a empresas y personas a obtener mejores tasas de cambio que la '
            'banca tradicional, con operaciones r&aacute;pidas, seguras y sin comisiones '
            'adicionales.<br><br>'
            'Le compartimos nuestras tasas referenciales del momento y quedamos atentos '
            'a cualquier consulta o cotizaci&oacute;n que requiera.'
        )

    return f"""\
<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#F1F5F9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#F1F5F9;padding:28px 0;">
<tr><td align="center">
<table width="560" cellpadding="0" cellspacing="0" border="0"
  style="max-width:560px;width:100%;background:#FFFFFF;border-radius:8px;overflow:hidden;
         box-shadow:0 4px 24px rgba(0,0,0,.07);">

  <!-- ENCABEZADO IMAGEN -->
  <tr>
    <td style="padding:0;line-height:0;background:#08121E;">
      <img src="cid:encabezado" alt="QoriCash" width="560"
           style="display:block;width:100%;max-width:560px;">
    </td>
  </tr>

  <!-- INTRO -->
  <tr>
    <td style="padding:24px 36px 0;">
      <p style="margin:0 0 14px;font-size:13px;color:#1E293B;line-height:1.65;">
        Estimado(a) <strong>{nombre_dest}</strong>,</p>
      <p style="margin:0;font-size:13px;color:#475569;line-height:1.8;text-align:justify;">
        {intro}
      </p>
    </td>
  </tr>

  <!-- LABEL TC -->
  <tr>
    <td style="padding:20px 36px 6px;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
        <td>
          <p style="margin:0;font-size:11px;font-weight:700;color:#94A3B8;
                    text-transform:uppercase;letter-spacing:1.2px;">
            Tipo de cambio en estos momentos</p>
          <p style="margin:4px 0 0;font-size:13px;color:#475569;">
            Tasas actualizadas &mdash; opere con la mejor tasa del mercado.</p>
        </td>
        <td align="right" style="white-space:nowrap;vertical-align:top;">
          <span style="font-size:10px;color:#94A3B8;">{hoy}</span>
        </td>
      </tr></table>
    </td>
  </tr>

  <!-- BLOQUE TC -->
  <tr>
    <td style="padding:16px 36px 28px;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0"
             style="border:1px solid #E9EEF4;border-radius:8px;overflow:hidden;">
        <tr>
          <td width="50%" style="padding:24px 20px;text-align:center;border-right:1px solid #E9EEF4;">
            <p style="margin:0 0 8px;font-size:9px;font-weight:700;color:#94A3B8;
                      text-transform:uppercase;letter-spacing:2px;">Compramos</p>
            <p style="margin:0;font-size:36px;font-weight:800;color:#0D1B2A;
                      letter-spacing:-1px;line-height:1;white-space:nowrap;">
              S/.&thinsp;{compra}</p>
            <p style="margin:8px 0 0;font-size:10px;color:#94A3B8;">
              por d&oacute;lar &middot; USD</p>
          </td>
          <td width="50%" style="padding:24px 20px;text-align:center;">
            <p style="margin:0 0 8px;font-size:9px;font-weight:700;color:#94A3B8;
                      text-transform:uppercase;letter-spacing:2px;">Vendemos</p>
            <p style="margin:0;font-size:36px;font-weight:800;color:#16a34a;
                      letter-spacing:-1px;line-height:1;white-space:nowrap;">
              S/.&thinsp;{venta}</p>
            <p style="margin:8px 0 0;font-size:10px;color:#94A3B8;">
              por d&oacute;lar &middot; USD</p>
          </td>
        </tr>
        <tr>
          <td colspan="2" style="padding:10px 20px;border-top:1px solid #E9EEF4;
                                  background:#F8FAFC;text-align:center;">
            <span style="font-size:10px;color:#64748B;">
              Operaci&oacute;n en minutos &nbsp;&middot;&nbsp; Sin costo de transferencia
              &nbsp;&middot;&nbsp; <em>Sujeto a variaci&oacute;n de mercado</em>
            </span>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <tr><td style="padding:0 36px;">
    <div style="height:1px;background:#F1F5F9;"></div>
  </td></tr>

  <!-- BANCOS -->
  <tr>
    <td style="padding:24px 36px 8px;">
      <p style="margin:0 0 4px;font-size:11px;font-weight:700;color:#94A3B8;
                text-transform:uppercase;letter-spacing:1px;">Cuentas bancarias</p>
      <p style="margin:0 0 16px;font-size:13px;color:#475569;">
        QORICASH S.A.C. &nbsp;&middot;&nbsp; RUC 20615113698
        &nbsp;&middot;&nbsp; Regulada por la SBS</p>
      <table width="100%" cellpadding="0" cellspacing="0" border="0"
             style="border:1px solid #E9EEF4;border-radius:8px;overflow:hidden;">
        <tr style="border-bottom:1px solid #F1F5F9;">
          <td style="padding:12px 8px 12px 16px;vertical-align:middle;width:100px;">
            <img src="cid:logo_bcp" alt="BCP" height="52"
                 style="display:block;height:52px;"></td>
          <td style="padding:12px 10px;vertical-align:middle;border-left:1px solid #F1F5F9;">
            <p style="margin:0;font-size:8px;color:#94A3B8;text-transform:uppercase;
                      letter-spacing:1px;">Soles</p>
            <p style="margin:3px 0 0;font-size:12px;font-weight:600;
                      color:#0D1B2A;">1937353150041</p></td>
          <td style="padding:12px 16px 12px 10px;vertical-align:middle;
                     border-left:1px solid #F1F5F9;">
            <p style="margin:0;font-size:8px;color:#94A3B8;text-transform:uppercase;
                      letter-spacing:1px;">D&oacute;lares</p>
            <p style="margin:3px 0 0;font-size:12px;font-weight:600;
                      color:#0D1B2A;">1917357790119</p></td>
        </tr>
        <tr style="border-bottom:1px solid #F1F5F9;">
          <td style="padding:12px 8px 12px 16px;vertical-align:middle;">
            <img src="cid:logo_interbank" alt="Interbank" height="40"
                 style="display:block;height:40px;"></td>
          <td style="padding:12px 10px;vertical-align:middle;border-left:1px solid #F1F5F9;">
            <p style="margin:0;font-size:8px;color:#94A3B8;text-transform:uppercase;
                      letter-spacing:1px;">Soles</p>
            <p style="margin:3px 0 0;font-size:12px;font-weight:600;
                      color:#0D1B2A;">200-3007757571</p></td>
          <td style="padding:12px 16px 12px 10px;vertical-align:middle;
                     border-left:1px solid #F1F5F9;">
            <p style="margin:0;font-size:8px;color:#94A3B8;text-transform:uppercase;
                      letter-spacing:1px;">D&oacute;lares</p>
            <p style="margin:3px 0 0;font-size:12px;font-weight:600;
                      color:#0D1B2A;">200-3007757589</p></td>
        </tr>
        <tr>
          <td style="padding:12px 8px 12px 16px;vertical-align:middle;">
            <img src="cid:logo_banbif" alt="BanBif" height="40"
                 style="display:block;height:40px;"></td>
          <td style="padding:12px 10px;vertical-align:middle;border-left:1px solid #F1F5F9;">
            <p style="margin:0;font-size:8px;color:#94A3B8;text-transform:uppercase;
                      letter-spacing:1px;">Soles</p>
            <p style="margin:3px 0 0;font-size:12px;font-weight:600;
                      color:#0D1B2A;">007000845805</p></td>
          <td style="padding:12px 16px 12px 10px;vertical-align:middle;
                     border-left:1px solid #F1F5F9;">
            <p style="margin:0;font-size:8px;color:#94A3B8;text-transform:uppercase;
                      letter-spacing:1px;">D&oacute;lares</p>
            <p style="margin:3px 0 0;font-size:12px;font-weight:600;
                      color:#0D1B2A;">007000845813</p></td>
        </tr>
      </table>
      <p style="margin:10px 0 0;font-size:10px;color:#94A3B8;line-height:1.6;">
        Transferencia interbancaria (CCI) disponible desde BBVA, Scotiabank,
        Pichincha y cualquier banco del Per&uacute;.
      </p>
    </td>
  </tr>

  <!-- BOTONES -->
  <tr>
    <td style="padding:20px 36px 28px;">
      <table cellpadding="0" cellspacing="0" border="0"><tr>
        <td style="border-radius:5px;background:#0D1B2A;padding-right:10px;">
          <a href="https://wa.me/51926011920"
             style="display:inline-block;padding:12px 28px;color:#FFFFFF;
                    text-decoration:none;font-size:12px;font-weight:600;
                    letter-spacing:0.5px;">Cotizar ahora &rarr;</a>
        </td>
        <td style="border-radius:5px;background:#F1F5F9;border:1px solid #E2E8F0;">
          <a href="https://qoricash.pe/presentacion.pdf"
             style="display:inline-block;padding:12px 28px;color:#475569;
                    text-decoration:none;font-size:12px;font-weight:600;
                    letter-spacing:0.5px;" target="_blank">
            Ver presentaci&oacute;n &rarr;</a>
        </td>
      </tr></table>
    </td>
  </tr>

  <tr><td style="padding:0 36px;">
    <div style="height:1px;background:#F1F5F9;"></div>
  </td></tr>

  <!-- FIRMA -->
  <tr>
    <td style="padding:20px 36px;">
      <table cellpadding="0" cellspacing="0" border="0"><tr>
        <td style="vertical-align:middle;padding-right:16px;width:44px;">
          <img src="{LOGO}" width="44" height="44" alt="QoriCash"
               style="display:block;border-radius:6px;">
        </td>
        <td style="vertical-align:middle;border-left:2px solid #E2E8F0;padding-left:16px;">
          <p style="margin:0;font-size:13px;font-weight:700;color:#0D1B2A;">
            {nombre_firma}</p>
          <p style="margin:3px 0 0;font-size:11px;color:#64748B;">
            {cargo} &nbsp;&middot;&nbsp;
            <a href="https://wa.me/51926011920"
               style="color:#64748B;text-decoration:none;">+51 926 011 920</a>
          </p>
          <p style="margin:2px 0 0;font-size:11px;">
            <a href="https://www.qoricash.pe"
               style="color:#16a34a;text-decoration:none;font-weight:600;">
              www.qoricash.pe</a>
            <span style="color:#CBD5E1;">&nbsp;&middot;&nbsp;Pueblo Libre, Lima</span>
          </p>
        </td>
      </tr></table>
    </td>
  </tr>

  <!-- PIE -->
  <tr>
    <td style="padding:14px 36px;background:#F8FAFC;border-top:1px solid #F1F5F9;">
      <p style="margin:0;font-size:10px;color:#94A3B8;text-align:center;line-height:1.6;">
        QORICASH S.A.C. &nbsp;&middot;&nbsp; RUC 20615113698 &nbsp;&middot;&nbsp;
        Regulada por la SBS &nbsp;&middot;&nbsp; Res. N.&ordm; 00313-2026
        <br>Para no recibir m&aacute;s comunicaciones responda con el asunto
        <em>NO CONTACTAR</em>.
      </p>
    </td>
  </tr>

</table>
</td></tr></table>
</body></html>"""


def _business_days_since(date_str: str) -> int:
    """Días hábiles desde date_str hasta hoy."""
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
        from app.models.exchange_rate import ExchangeRate
        from app.extensions import db
        from app.utils.formatters import now_peru
        from collections import defaultdict

        with app.app_context():
            # Horario permitido: 9:00–13:30 Lima, lunes a viernes
            now_dt = now_peru()
            if now_dt.weekday() >= 5:
                return {'tasks': 0, 'message': 'Fuera de horario (fin de semana)'}
            hour_frac = now_dt.hour + now_dt.minute / 60
            if not (9.0 <= hour_frac < 13.5):
                return {'tasks': 0, 'message': (
                    f'Fuera de horario ({now_dt.strftime("%H:%M")} Lima — activo 09:00–13:30)'
                )}

            # Tasas actuales desde ExchangeRate
            try:
                tc = ExchangeRate.get_current()
                compra = f'{float(tc["compra"]):.3f}'
                venta  = f'{float(tc["venta"]):.3f}'
            except Exception:
                compra, venta = '—', '—'

            sent_total = 0
            skipped    = 0
            today      = now_dt.date()
            hoy_str    = today.strftime('%Y-%m-%d')
            hoy_full   = today.strftime('%d/%m/%Y')

            # Usuario bot para registrar actividades
            from app.models.user import User
            bot_user = User.query.filter_by(role='Master').first()

            # FIX 5: filtro de fecha en SQL (7 días calendario ≈ 5 hábiles)
            cutoff = (today - timedelta(days=_CALENDAR_DAYS_APPROX)).strftime('%Y-%m-%d')

            prospectos = (Prospecto.query
                          .filter(
                              ~Prospecto.estado_comercial.in_(_EXCLUDE_ESTADOS),
                              ~Prospecto.estado_email.in_(_EXCLUDE_EMAIL_EST),
                              Prospecto.email.isnot(None),
                              Prospecto.email != '',
                              db.or_(
                                  Prospecto.fecha_ultimo_contacto.is_(None),
                                  Prospecto.fecha_ultimo_contacto <= cutoff,
                              ),
                          )
                          .order_by(Prospecto.fecha_ultimo_contacto.asc().nullsfirst())
                          .limit(300)
                          .all())

            # Refinamiento exacto por días hábiles (sobre conjunto ya pequeño)
            eligible = [p for p in prospectos
                        if _business_days_since(p.fecha_ultimo_contacto) >= _DIAS_HABIL_ESPERA]

            # Distribuir por bandeja (hash estable)
            por_bandeja = defaultdict(list)
            for p in eligible:
                por_bandeja[self._pick_bandeja(p)].append(p)

            for bandeja in list(_BANDEJAS.keys()):
                prospects_q = por_bandeja.get(bandeja, [])
                if not prospects_q:
                    continue

                sent_today = self._daily_sent_count(db, bandeja, today)
                remaining  = _DAILY_LIMIT - sent_today
                if remaining <= 0:
                    _log.info(f'[MailAgent] {bandeja}: límite diario alcanzado ({sent_today})')
                    continue

                batch      = prospects_q[:min(_BATCH_PER_CYCLE, remaining)]
                bot_nombre = _BANDEJA_NOMBRE.get(bandeja, 'QoriCash')
                bot_cargo  = _BANDEJA_CARGO.get(bandeja, 'Equipo Comercial')
                es_personal = (bandeja == 'ggarcia@qoricash.pe')

                for p in batch:
                    try:
                        nombre_dest = (
                            (p.nombre_contacto or p.razon_social or 'equipo')
                            .split()[0].capitalize()
                        )
                        html = _build_html(
                            nombre_dest=nombre_dest,
                            nombre_firma=bot_nombre,
                            cargo=bot_cargo,
                            compra=compra,
                            venta=venta,
                            hoy=hoy_full,
                            es_personal=es_personal,
                        )
                        subject = 'QoriCash \u2014 Tipo de cambio preferencial'
                        ok = self._send_via_gmail(bandeja, p.email, subject, html)
                        if not ok:
                            skipped += 1
                            continue

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
            msg = f'Campaña: {sent_total} emails enviados · {skipped} omitidos · TC {compra}/{venta}'
            return {
                'tasks':   sent_total,
                'message': msg,
                'metrics': {'emails_sent': sent_total},
            }

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _daily_sent_count(self, db, bandeja: str, today) -> int:
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

    def _send_via_gmail(self, sender: str, to: str, subject: str, html: str) -> bool:
        try:
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

            # MIMEMultipart/related para soportar imágenes CID embebidas
            msg_related = MIMEMultipart('related')
            msg_related['From']       = sender
            msg_related['To']         = to
            msg_related['Subject']    = subject
            msg_related['Date']       = formatdate(localtime=True)
            msg_related['Message-ID'] = make_msgid(domain='qoricash.pe')

            msg_alt = MIMEMultipart('alternative')
            msg_alt.attach(MIMEText(html, 'html'))
            msg_related.attach(msg_alt)

            # Adjuntar imágenes CID si los archivos existen
            def _adjuntar(path: str, cid: str, fname: str, tipo: str):
                if not os.path.exists(path):
                    return
                with open(path, 'rb') as f:
                    part = MIMEImage(f.read(), tipo)
                part.add_header('Content-ID', f'<{cid}>')
                part.add_header('Content-Disposition', 'inline', filename=fname)
                msg_related.attach(part)

            _adjuntar(_IMG_ENCABEZADO, 'encabezado',    'encabezado.jpg', 'jpeg')
            _adjuntar(_IMG_BCP,        'logo_bcp',      'bcp.png',        'png')
            _adjuntar(_IMG_INTERBANK,  'logo_interbank','interbank.png',  'png')
            _adjuntar(_IMG_BANBIF,     'logo_banbif',   'banbif.png',     'png')

            raw = base64.urlsafe_b64encode(msg_related.as_bytes()).decode()
            service.users().messages().send(userId='me', body={'raw': raw}).execute()
            return True

        except Exception as e:
            _log.error(f'[MailAgent] Gmail send error ({sender} → {to}): {e}')
            return False
