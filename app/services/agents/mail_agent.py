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
import io
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
_DIAS_HABIL_ESPERA    = 5
_CALENDAR_DAYS_APPROX = 7     # 5 días hábiles ≈ 7 calendario — filtro SQL previo
_DAILY_LIMIT          = 1500  # límite diario por bandeja (Google Workspace: 2,000/día)

# Horario y modos de envío
_HORA_INICIO      = 9.0    # 09:00 Lima
_HORA_CORTE       = 13.5   # 13:30 — fin modo precios, inicio modo prospección
_HORA_FIN_TARDE   = 18.0   # 18:00 — fin modo prospección

# Batch sizes por modo (el cap _DAILY_LIMIT actúa de tope duro)
_BATCH_MAÑANA     = 100    # agresivo: maximizar envíos en ventana de precios
_BATCH_TARDE      = 50     # moderado: prospección de tarde

# Re-fetch de TC: cada N emails enviados (para capturar actualizaciones del widget)
_TC_REFRESH_CADA  = 30

# Rutas de imágenes embebidas (relativas al módulo)
_STATIC_IMAGES = os.path.join(
    os.path.dirname(__file__), '..', '..', 'static', 'images'
)
_IMG_ENCABEZADO = os.path.join(_STATIC_IMAGES, 'encabezado_prospeccion.jpg')
_IMG_BCP        = os.path.join(_STATIC_IMAGES, 'bcp_logo.png')
_IMG_INTERBANK  = os.path.join(_STATIC_IMAGES, 'interbank_logo.png')
_IMG_BANBIF     = os.path.join(_STATIC_IMAGES, 'banbif_logo.png')
_IMG_LOGO       = os.path.join(_STATIC_IMAGES, 'logo-email.png')

LOGO = 'https://www.qoricash.pe/logofirma.png'

# ─────────────────────────────────────────────────────────────────
# Plantilla HTML oficial unificada (empresa + persona natural)
# ─────────────────────────────────────────────────────────────────

def _build_html(nombre_dest: str, nombre_firma: str, cargo: str,
                compra: str, venta: str, hoy: str, es_personal: bool) -> str:
    if es_personal:
        intro = (
            f'Mi nombre es <strong>{nombre_firma}</strong>, Presidente de Negocios de '
            '<strong>QoriCash SAC</strong>, fintech de cambio de divisas digital inscrita en el '
            'Registro de Casas de Cambio de la SBS.<br><br>'
            'Ayudamos a empresas y personas a obtener mejores tasas de cambio que la '
            'banca tradicional, con operaciones r&aacute;pidas, seguras y sin comisiones '
            'adicionales.<br><br>'
            'Le compartimos nuestras tasas referenciales del momento y quedamos atentos '
            'a cualquier consulta o cotizaci&oacute;n que requiera.'
        )
    else:
        intro = (
            'Somos <strong>QoriCash SAC</strong>, fintech de cambio de divisas digital inscrita en el '
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
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  .card-bank {{ border:1px solid #E9EEF4;border-radius:10px;background:#FFFFFF;text-align:center;cursor:default; }}
  .card-bank:hover {{ background:#F0FDF4 !important;border-color:#86efac !important;box-shadow:0 4px 16px rgba(22,163,74,0.12) !important; }}
  .card-bank:hover .acct-row {{ display:table-row !important; }}
</style>
</head>
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

  <!-- BANCOS: 3 CARDS HORIZONTALES -->
  <tr>
    <td style="padding:16px 36px 24px;">
      <p style="margin:0 0 14px;font-size:11px;font-weight:700;color:#94A3B8;
                text-transform:uppercase;letter-spacing:1px;">
        Operamos con los bancos m&aacute;s importantes del Per&uacute;</p>
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td width="32%" style="vertical-align:top;">
            <table width="100%" cellpadding="0" cellspacing="0" border="0" class="card-bank"
                   style="border:1px solid #E9EEF4;border-radius:10px;background:#FFFFFF;text-align:center;">
              <tr><td style="padding:12px 8px 10px;height:64px;vertical-align:middle;">
                <img src="cid:logo_bcp" alt="BCP" height="44"
                     style="display:inline-block;height:44px;max-width:90%;">
              </td></tr>
              <tr class="acct-row" style="display:none;"><td
                   style="padding:10px 12px 16px;border-top:1px solid #F1F5F9;">
                <p style="margin:0;font-size:8px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px;">Soles</p>
                <p style="margin:3px 0 8px;font-size:11px;font-weight:600;color:#0D1B2A;">1937353150041</p>
                <p style="margin:0;font-size:8px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px;">D&oacute;lares</p>
                <p style="margin:3px 0 0;font-size:11px;font-weight:600;color:#0D1B2A;">1917357790119</p>
              </td></tr>
            </table>
          </td>
          <td width="2%"></td>
          <td width="32%" style="vertical-align:top;">
            <table width="100%" cellpadding="0" cellspacing="0" border="0" class="card-bank"
                   style="border:1px solid #E9EEF4;border-radius:10px;background:#FFFFFF;text-align:center;">
              <tr><td style="padding:12px 8px 10px;height:64px;vertical-align:middle;">
                <img src="cid:logo_interbank" alt="Interbank" height="44"
                     style="display:inline-block;height:44px;max-width:90%;">
              </td></tr>
              <tr class="acct-row" style="display:none;"><td
                   style="padding:10px 12px 16px;border-top:1px solid #F1F5F9;">
                <p style="margin:0;font-size:8px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px;">Soles</p>
                <p style="margin:3px 0 8px;font-size:11px;font-weight:600;color:#0D1B2A;">200-3007757571</p>
                <p style="margin:0;font-size:8px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px;">D&oacute;lares</p>
                <p style="margin:3px 0 0;font-size:11px;font-weight:600;color:#0D1B2A;">200-3007757589</p>
              </td></tr>
            </table>
          </td>
          <td width="2%"></td>
          <td width="32%" style="vertical-align:top;">
            <table width="100%" cellpadding="0" cellspacing="0" border="0" class="card-bank"
                   style="border:1px solid #E9EEF4;border-radius:10px;background:#FFFFFF;text-align:center;">
              <tr><td style="padding:12px 8px 10px;height:64px;vertical-align:middle;">
                <img src="cid:logo_banbif" alt="BanBif" height="44"
                     style="display:inline-block;height:44px;max-width:90%;">
              </td></tr>
              <tr class="acct-row" style="display:none;"><td
                   style="padding:10px 12px 16px;border-top:1px solid #F1F5F9;">
                <p style="margin:0;font-size:8px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px;">Soles</p>
                <p style="margin:3px 0 8px;font-size:11px;font-weight:600;color:#0D1B2A;">007000845805</p>
                <p style="margin:0;font-size:8px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px;">D&oacute;lares</p>
                <p style="margin:3px 0 0;font-size:11px;font-weight:600;color:#0D1B2A;">007000845813</p>
              </td></tr>
            </table>
          </td>
        </tr>
      </table>
      <p style="margin:14px 0 0;font-size:10px;color:#94A3B8;text-align:center;line-height:1.6;">
        Para operaciones con BBVA, Scotiabank, Pichincha, Banco GNB y otros bancos,
        realizamos transferencias v&iacute;a <strong style="color:#64748B;">CCI</strong>
        en un plazo de <strong style="color:#64748B;">2 a 24 horas</strong>.
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


def _build_html_prospeccion(nombre_dest: str, nombre_firma: str, cargo: str,
                             compra: str, venta: str, hoy: str, es_personal: bool) -> str:
    """Plantilla de prospección para la tarde (13:31–18:00).
    Foco en presentación institucional; TC como referencia sutil (mercado cerrando)."""
    if es_personal:
        intro = (
            f'Mi nombre es <strong>{nombre_firma}</strong>, Presidente de Negocios de '
            '<strong>QoriCash SAC</strong>, fintech de cambio de divisas digital inscrita en el '
            'Registro de Casas de Cambio de la SBS.<br><br>'
            'Ayudamos a empresas y personas que regularmente compran y venden d&oacute;lares, '
            'ofreciendo tasas superiores a las de la banca tradicional con procesos '
            '&aacute;giles, seguros y sin comisiones adicionales.<br><br>'
            'Me pongo en contacto para presentarle nuestra propuesta de valor y que '
            'conozca de cerca la rentabilidad que ganan sus operaciones al operar con nosotros.'
        )
    else:
        intro = (
            'Somos <strong>QoriCash SAC</strong>, fintech de cambio de divisas digital inscrita en el '
            'Registro de Casas de Cambio de la SBS.<br><br>'
            'Ayudamos a empresas y personas que regularmente compran y venden d&oacute;lares, '
            'ofreciendo tasas superiores a las de la banca tradicional con procesos '
            '&aacute;giles, seguros y sin comisiones adicionales.<br><br>'
            'Nos ponemos en contacto con usted para presentarle nuestra propuesta de valor '
            'y que conozca de cerca la rentabilidad que ganan sus operaciones al operar con nosotros.'
        )

    return f"""\
<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  .card-bank {{ border:1px solid #E9EEF4;border-radius:10px;background:#FFFFFF;text-align:center;cursor:default; }}
  .card-bank:hover {{ background:#F0FDF4 !important;border-color:#86efac !important;box-shadow:0 4px 16px rgba(22,163,74,0.12) !important; }}
  .card-bank:hover .acct-row {{ display:table-row !important; }}
</style>
</head>
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
    <td style="padding:28px 36px 0;">
      <p style="margin:0 0 14px;font-size:13px;color:#1E293B;line-height:1.65;">
        Estimado(a) <strong>{nombre_dest}</strong>,</p>
      <p style="margin:0;font-size:13px;color:#475569;line-height:1.8;text-align:justify;">
        {intro}
      </p>
    </td>
  </tr>

  <!-- TC DE REFERENCIA (sutil, borde izquierdo verde) -->
  <tr>
    <td style="padding:20px 36px;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0"
             style="border-left:3px solid #16a34a;background:#F8FAFC;border-radius:0 6px 6px 0;">
        <tr>
          <td style="padding:14px 18px;">
            <p style="margin:0 0 6px;font-size:10px;font-weight:700;color:#94A3B8;
                      text-transform:uppercase;letter-spacing:1.2px;">
              Tipo de cambio de referencia &mdash; {hoy}</p>
            <table cellpadding="0" cellspacing="0" border="0"><tr>
              <td style="padding-right:24px;">
                <span style="font-size:10px;color:#64748B;text-transform:uppercase;
                             letter-spacing:0.8px;">Compramos&nbsp;</span>
                <span style="font-size:16px;font-weight:700;color:#0D1B2A;">
                  S/.&thinsp;{compra}</span>
              </td>
              <td>
                <span style="font-size:10px;color:#64748B;text-transform:uppercase;
                             letter-spacing:0.8px;">Vendemos&nbsp;</span>
                <span style="font-size:16px;font-weight:700;color:#16a34a;">
                  S/.&thinsp;{venta}</span>
              </td>
            </tr></table>
            <p style="margin:6px 0 0;font-size:10px;color:#94A3B8;">
              Tasas de referencia &middot; Sujeto a variaci&oacute;n de mercado</p>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- CUENTAS BANCARIAS: 3 CARDS HORIZONTALES -->
  <tr>
    <td style="padding:0 36px 24px;">
      <p style="margin:0 0 14px;font-size:11px;font-weight:700;color:#94A3B8;
                text-transform:uppercase;letter-spacing:1px;">
        Operamos con los bancos m&aacute;s importantes del Per&uacute;</p>
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td width="32%" style="vertical-align:top;">
            <table width="100%" cellpadding="0" cellspacing="0" border="0" class="card-bank"
                   style="border:1px solid #E9EEF4;border-radius:10px;background:#FFFFFF;text-align:center;">
              <tr><td style="padding:12px 8px 10px;height:64px;vertical-align:middle;">
                <img src="cid:logo_bcp" alt="BCP" height="44"
                     style="display:inline-block;height:44px;max-width:90%;">
              </td></tr>
              <tr class="acct-row" style="display:none;"><td
                   style="padding:10px 12px 16px;border-top:1px solid #F1F5F9;">
                <p style="margin:0;font-size:8px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px;">Soles</p>
                <p style="margin:3px 0 8px;font-size:11px;font-weight:600;color:#0D1B2A;">1937353150041</p>
                <p style="margin:0;font-size:8px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px;">D&oacute;lares</p>
                <p style="margin:3px 0 0;font-size:11px;font-weight:600;color:#0D1B2A;">1917357790119</p>
              </td></tr>
            </table>
          </td>
          <td width="2%"></td>
          <td width="32%" style="vertical-align:top;">
            <table width="100%" cellpadding="0" cellspacing="0" border="0" class="card-bank"
                   style="border:1px solid #E9EEF4;border-radius:10px;background:#FFFFFF;text-align:center;">
              <tr><td style="padding:12px 8px 10px;height:64px;vertical-align:middle;">
                <img src="cid:logo_interbank" alt="Interbank" height="44"
                     style="display:inline-block;height:44px;max-width:90%;">
              </td></tr>
              <tr class="acct-row" style="display:none;"><td
                   style="padding:10px 12px 16px;border-top:1px solid #F1F5F9;">
                <p style="margin:0;font-size:8px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px;">Soles</p>
                <p style="margin:3px 0 8px;font-size:11px;font-weight:600;color:#0D1B2A;">200-3007757571</p>
                <p style="margin:0;font-size:8px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px;">D&oacute;lares</p>
                <p style="margin:3px 0 0;font-size:11px;font-weight:600;color:#0D1B2A;">200-3007757589</p>
              </td></tr>
            </table>
          </td>
          <td width="2%"></td>
          <td width="32%" style="vertical-align:top;">
            <table width="100%" cellpadding="0" cellspacing="0" border="0" class="card-bank"
                   style="border:1px solid #E9EEF4;border-radius:10px;background:#FFFFFF;text-align:center;">
              <tr><td style="padding:12px 8px 10px;height:64px;vertical-align:middle;">
                <img src="cid:logo_banbif" alt="BanBif" height="44"
                     style="display:inline-block;height:44px;max-width:90%;">
              </td></tr>
              <tr class="acct-row" style="display:none;"><td
                   style="padding:10px 12px 16px;border-top:1px solid #F1F5F9;">
                <p style="margin:0;font-size:8px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px;">Soles</p>
                <p style="margin:3px 0 8px;font-size:11px;font-weight:600;color:#0D1B2A;">007000845805</p>
                <p style="margin:0;font-size:8px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px;">D&oacute;lares</p>
                <p style="margin:3px 0 0;font-size:11px;font-weight:600;color:#0D1B2A;">007000845813</p>
              </td></tr>
            </table>
          </td>
        </tr>
      </table>
      <p style="margin:14px 0 0;font-size:10px;color:#94A3B8;text-align:center;line-height:1.6;">
        Para operaciones con BBVA, Scotiabank, Pichincha, Banco GNB y otros bancos,
        realizamos transferencias v&iacute;a <strong style="color:#64748B;">CCI</strong>
        en un plazo de <strong style="color:#64748B;">2 a 24 horas</strong>.
      </p>
    </td>
  </tr>

  <!-- BOTONES -->
  <tr>
    <td style="padding:20px 36px 28px;">
      <table cellpadding="0" cellspacing="0" border="0"><tr>
        <td style="border-radius:5px;background:#0D1B2A;padding-right:10px;">
          <a href="https://qoricash.pe/presentacion.pdf"
             style="display:inline-block;padding:12px 28px;color:#FFFFFF;
                    text-decoration:none;font-size:12px;font-weight:600;
                    letter-spacing:0.5px;" target="_blank">
            Ver presentaci&oacute;n institucional &rarr;</a>
        </td>
        <td style="border-radius:5px;background:#F1F5F9;border:1px solid #E2E8F0;">
          <a href="https://wa.me/51926011920"
             style="display:inline-block;padding:12px 28px;color:#475569;
                    text-decoration:none;font-size:12px;font-weight:600;
                    letter-spacing:0.5px;">Cotizar ahora &rarr;</a>
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


def _build_html_solo_precios(nombre_dest: str, nombre_firma: str, cargo: str,
                              compra: str, venta: str, hoy: str) -> str:
    """Follow-up para prospectos ya contactados (num_contactos >= 1).
    Sin texto de presentación. TC directo, header limpio con logo CID."""
    return f"""\
<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  .card-bank {{ border:1px solid #E9EEF4;border-radius:10px;background:#FFFFFF;text-align:center;cursor:default; }}
  .card-bank:hover {{ background:#F0FDF4 !important;border-color:#86efac !important;box-shadow:0 4px 16px rgba(22,163,74,0.12) !important; }}
  .card-bank:hover .acct-row {{ display:table-row !important; }}
</style>
</head>
<body style="margin:0;padding:0;background:#F1F5F9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#F1F5F9;padding:28px 0;">
<tr><td align="center">
<table width="560" cellpadding="0" cellspacing="0" border="0"
  style="max-width:560px;width:100%;background:#FFFFFF;border-radius:8px;overflow:hidden;
         box-shadow:0 4px 24px rgba(0,0,0,.07);">

  <!-- ENCABEZADO BLANCO CON LOGO CID -->
  <tr>
    <td style="background:#FFFFFF;border-top:4px solid #16a34a;padding:24px 36px 20px;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
        <td style="vertical-align:middle;">
          <table cellpadding="0" cellspacing="0" border="0"><tr>
            <td style="vertical-align:middle;">
              <img src="cid:logo_qori" alt="QoriCash" width="44" height="44"
                   style="display:block;border-radius:7px;box-shadow:0 2px 8px rgba(0,0,0,0.10);">
            </td>
            <td style="vertical-align:middle;padding-left:12px;">
              <p style="margin:0;font-size:20px;font-weight:800;color:#0D1B2A;
                        letter-spacing:3px;text-transform:uppercase;line-height:1;">QORICASH</p>
              <table cellpadding="0" cellspacing="0" border="0">
                <tr><td style="text-align:center;">
                  <p style="margin:3px 0 0;font-size:7px;font-weight:600;color:#94A3B8;
                            letter-spacing:3.8px;text-transform:uppercase;">CAMBIO DE DIVISAS</p>
                </td></tr>
              </table>
            </td>
          </tr></table>
        </td>
        <td align="right" style="vertical-align:middle;">
          <p style="margin:0;font-size:9px;color:#CBD5E1;text-align:right;line-height:1.5;">
            Res. SBS<br>N.&ordm;&nbsp;00313-2026</p>
        </td>
      </tr></table>
    </td>
  </tr>

  <!-- SEPARADOR -->
  <tr><td style="padding:0 36px;">
    <div style="height:1px;background:#E9EEF4;"></div>
  </td></tr>

  <!-- SALUDO -->
  <tr>
    <td style="padding:20px 36px 0;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td style="border-left:3px solid #16a34a;background:#F8FAFC;
                     padding:12px 16px;border-radius:0 6px 6px 0;">
            <p style="margin:0;font-size:13px;color:#1E293B;line-height:1.6;">
              Estimado(a) <strong>{nombre_dest}</strong>, le compartimos
              nuestro tipo de cambio actualizado para el d&iacute;a de hoy.</p>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- LABEL TC + BADGE EN VIVO -->
  <tr>
    <td style="padding:20px 36px 8px;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
        <td style="vertical-align:middle;">
          <p style="margin:0;font-size:11px;font-weight:700;color:#94A3B8;
                    text-transform:uppercase;letter-spacing:1.2px;display:inline;">
            Tipo de cambio en estos momentos</p>
          &nbsp;
          <span style="display:inline-block;background:#dcfce7;color:#16a34a;
                       font-size:9px;font-weight:700;padding:2px 8px;
                       border-radius:20px;letter-spacing:0.8px;
                       text-transform:uppercase;vertical-align:middle;">
            &#9679;&nbsp;En vivo</span>
        </td>
        <td align="right" style="white-space:nowrap;vertical-align:middle;">
          <span style="font-size:10px;color:#94A3B8;">{hoy}</span>
        </td>
      </tr></table>
    </td>
  </tr>

  <!-- BLOQUE TC -->
  <tr>
    <td style="padding:0 36px 20px;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0"
             style="border:1px solid #E9EEF4;border-radius:8px;overflow:hidden;">
        <tr>
          <td width="50%" style="padding:28px 20px;text-align:center;border-right:1px solid #E9EEF4;">
            <p style="margin:0 0 8px;font-size:9px;font-weight:700;color:#94A3B8;
                      text-transform:uppercase;letter-spacing:2px;">Compramos</p>
            <p style="margin:0;font-size:40px;font-weight:800;color:#0D1B2A;
                      letter-spacing:-1px;line-height:1;white-space:nowrap;">
              S/.&thinsp;{compra}</p>
            <p style="margin:8px 0 0;font-size:10px;color:#94A3B8;">por d&oacute;lar &middot; USD</p>
          </td>
          <td width="50%" style="padding:28px 20px;text-align:center;">
            <p style="margin:0 0 8px;font-size:9px;font-weight:700;color:#94A3B8;
                      text-transform:uppercase;letter-spacing:2px;">Vendemos</p>
            <p style="margin:0;font-size:40px;font-weight:800;color:#16a34a;
                      letter-spacing:-1px;line-height:1;white-space:nowrap;">
              S/.&thinsp;{venta}</p>
            <p style="margin:8px 0 0;font-size:10px;color:#94A3B8;">por d&oacute;lar &middot; USD</p>
          </td>
        </tr>
        <tr>
          <td colspan="2" style="padding:12px 16px;border-top:1px solid #E9EEF4;background:#F8FAFC;">
            <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
              <td align="center">
                <span style="display:inline-block;background:#FFFFFF;border:1px solid #E2E8F0;
                             border-radius:20px;padding:4px 12px;margin:0 3px;
                             font-size:10px;color:#475569;white-space:nowrap;">
                  <span style="color:#16a34a;font-weight:700;">&#10003;</span>
                  &nbsp;Operaci&oacute;n en minutos</span>
                <span style="display:inline-block;background:#FFFFFF;border:1px solid #E2E8F0;
                             border-radius:20px;padding:4px 12px;margin:0 3px;
                             font-size:10px;color:#475569;white-space:nowrap;">
                  <span style="color:#16a34a;font-weight:700;">&#10003;</span>
                  &nbsp;Sin costo de transferencia</span>
                <span style="display:inline-block;background:#FFFFFF;border:1px solid #E2E8F0;
                             border-radius:20px;padding:4px 12px;margin:0 3px;
                             font-size:10px;color:#94A3B8;white-space:nowrap;">
                  Sujeto a variaci&oacute;n de mercado</span>
              </td>
            </tr></table>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- BOTÓN WHATSAPP -->
  <tr>
    <td style="padding:0 36px 28px;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td style="border-radius:6px;background:#0D1B2A;text-align:center;">
            <a href="https://wa.me/51926011920"
               style="display:block;padding:14px 28px;color:#FFFFFF;
                      text-decoration:none;font-size:13px;font-weight:700;letter-spacing:0.5px;">
              &#128172;&nbsp;&nbsp;Cotizar ahora por WhatsApp &rarr;</a>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <tr><td style="padding:0 36px;">
    <div style="height:1px;background:#F1F5F9;"></div>
  </td></tr>

  <!-- BANCOS: 3 CARDS -->
  <tr>
    <td style="padding:16px 36px 24px;">
      <p style="margin:0 0 14px;font-size:11px;font-weight:700;color:#94A3B8;
                text-transform:uppercase;letter-spacing:1px;">
        Operamos con los bancos m&aacute;s importantes del Per&uacute;</p>
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td width="32%" style="vertical-align:top;">
            <table width="100%" cellpadding="0" cellspacing="0" border="0" class="card-bank"
                   style="border:1px solid #E9EEF4;border-radius:10px;background:#FFFFFF;text-align:center;">
              <tr><td style="padding:12px 8px 10px;height:64px;vertical-align:middle;">
                <img src="cid:logo_bcp" alt="BCP" height="44"
                     style="display:inline-block;height:44px;max-width:90%;">
              </td></tr>
              <tr class="acct-row" style="display:none;"><td
                   style="padding:10px 12px 16px;border-top:1px solid #F1F5F9;">
                <p style="margin:0;font-size:8px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px;">Soles</p>
                <p style="margin:3px 0 8px;font-size:11px;font-weight:600;color:#0D1B2A;">1937353150041</p>
                <p style="margin:0;font-size:8px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px;">D&oacute;lares</p>
                <p style="margin:3px 0 0;font-size:11px;font-weight:600;color:#0D1B2A;">1917357790119</p>
              </td></tr>
            </table>
          </td>
          <td width="2%"></td>
          <td width="32%" style="vertical-align:top;">
            <table width="100%" cellpadding="0" cellspacing="0" border="0" class="card-bank"
                   style="border:1px solid #E9EEF4;border-radius:10px;background:#FFFFFF;text-align:center;">
              <tr><td style="padding:12px 8px 10px;height:64px;vertical-align:middle;">
                <img src="cid:logo_interbank" alt="Interbank" height="44"
                     style="display:inline-block;height:44px;max-width:90%;">
              </td></tr>
              <tr class="acct-row" style="display:none;"><td
                   style="padding:10px 12px 16px;border-top:1px solid #F1F5F9;">
                <p style="margin:0;font-size:8px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px;">Soles</p>
                <p style="margin:3px 0 8px;font-size:11px;font-weight:600;color:#0D1B2A;">200-3007757571</p>
                <p style="margin:0;font-size:8px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px;">D&oacute;lares</p>
                <p style="margin:3px 0 0;font-size:11px;font-weight:600;color:#0D1B2A;">200-3007757589</p>
              </td></tr>
            </table>
          </td>
          <td width="2%"></td>
          <td width="32%" style="vertical-align:top;">
            <table width="100%" cellpadding="0" cellspacing="0" border="0" class="card-bank"
                   style="border:1px solid #E9EEF4;border-radius:10px;background:#FFFFFF;text-align:center;">
              <tr><td style="padding:12px 8px 10px;height:64px;vertical-align:middle;">
                <img src="cid:logo_banbif" alt="BanBif" height="44"
                     style="display:inline-block;height:44px;max-width:90%;">
              </td></tr>
              <tr class="acct-row" style="display:none;"><td
                   style="padding:10px 12px 16px;border-top:1px solid #F1F5F9;">
                <p style="margin:0;font-size:8px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px;">Soles</p>
                <p style="margin:3px 0 8px;font-size:11px;font-weight:600;color:#0D1B2A;">007000845805</p>
                <p style="margin:0;font-size:8px;color:#94A3B8;text-transform:uppercase;letter-spacing:1px;">D&oacute;lares</p>
                <p style="margin:3px 0 0;font-size:11px;font-weight:600;color:#0D1B2A;">007000845813</p>
              </td></tr>
            </table>
          </td>
        </tr>
      </table>
      <p style="margin:14px 0 0;font-size:10px;color:#94A3B8;text-align:center;line-height:1.6;">
        Para operaciones con BBVA, Scotiabank, Pichincha, Banco GNB y otros bancos,
        realizamos transferencias v&iacute;a <strong style="color:#64748B;">CCI</strong>
        en un plazo de <strong style="color:#64748B;">2 a 24 horas</strong>.
      </p>
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
          <img src="cid:logo_qori" width="44" height="44" alt="QoriCash"
               style="display:block;border-radius:6px;">
        </td>
        <td style="vertical-align:middle;border-left:2px solid #E2E8F0;padding-left:16px;">
          <p style="margin:0;font-size:13px;font-weight:700;color:#0D1B2A;">{nombre_firma}</p>
          <p style="margin:3px 0 0;font-size:11px;color:#64748B;">
            {cargo} &nbsp;&middot;&nbsp;
            <a href="https://wa.me/51926011920" style="color:#64748B;text-decoration:none;">+51 926 011 920</a>
          </p>
          <p style="margin:2px 0 0;font-size:11px;">
            <a href="https://www.qoricash.pe"
               style="color:#16a34a;text-decoration:none;font-weight:600;">www.qoricash.pe</a>
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
        <br>Para no recibir m&aacute;s comunicaciones responda con el asunto <em>NO CONTACTAR</em>.
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
        import eventlet
        from app.models.prospecto import Prospecto
        from app.models.exchange_rate import ExchangeRate
        from app.extensions import db
        from app.utils.formatters import now_peru
        from collections import defaultdict

        # ── Fase 1: setup y query en contexto principal ────────────────────────
        with app.app_context():
            now_dt    = now_peru()
            hour_frac = now_dt.hour + now_dt.minute / 60

            if now_dt.weekday() >= 5:
                return {'tasks': 0, 'message': 'Fuera de horario (fin de semana)'}

            if _HORA_INICIO <= hour_frac < _HORA_CORTE:
                modo       = 'precios'
                batch_size = _BATCH_MAÑANA
            elif _HORA_CORTE <= hour_frac < _HORA_FIN_TARDE:
                modo       = 'prospeccion'
                batch_size = _BATCH_TARDE
            else:
                return {'tasks': 0, 'message': (
                    f'Fuera de horario ({now_dt.strftime("%H:%M")} Lima — '
                    f'activo 09:00–18:00 días hábiles)'
                )}

            compra_ref, venta_ref = self._fetch_tc(ExchangeRate)
            today    = now_dt.date()
            hoy_str  = today.strftime('%Y-%m-%d')
            hoy_full = today.strftime('%d/%m/%Y')

            cutoff = (today - timedelta(days=_CALENDAR_DAYS_APPROX)).strftime('%Y-%m-%d')

            # Pool ampliado para cubrir las 3 bandejas en paralelo
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
                              db.or_(
                                  Prospecto.fecha_proximo_contacto.is_(None),
                                  Prospecto.fecha_proximo_contacto <= hoy_str,
                              ),
                          )
                          .order_by(Prospecto.fecha_ultimo_contacto.asc().nullsfirst())
                          .limit(900)
                          .all())

            eligible_raw = [p for p in prospectos
                            if _business_days_since(p.fecha_ultimo_contacto) >= _DIAS_HABIL_ESPERA]

            _seen_emails: dict = {}
            for p in eligible_raw:
                key = (p.email or '').strip().lower()
                if key not in _seen_emails or p.id > _seen_emails[key].id:
                    _seen_emails[key] = p
            eligible = list(_seen_emails.values())

            por_bandeja = defaultdict(list)
            for p in eligible:
                por_bandeja[self._pick_bandeja(p)].append(p)

            # Pasar solo IDs entre contextos (objetos SQLAlchemy no son seguros entre sesiones)
            ids_por_bandeja = {b: [p.id for p in por_bandeja.get(b, [])] for b in _BANDEJAS}

        # Cargar imágenes una vez, compartidas entre las 3 greenlets (solo lectura)
        img_cache = self._load_image_cache()

        # ── Fase 2: worker por bandeja ─────────────────────────────────────────
        worker_results = []

        def _bandeja_worker(bandeja, prospect_ids):
            """Greenlet independiente por bandeja — sesión DB propia."""
            from app.models.prospecto import Prospecto, ActividadProspecto
            from app.models.exchange_rate import ExchangeRate
            from app.models.user import User
            from app.extensions import db
            from app.utils.formatters import now_peru

            with app.app_context():
                if not prospect_ids:
                    worker_results.append({'bandeja': bandeja, 'sent': 0, 'skipped': 0})
                    return

                today_w    = now_peru().date()
                hoy_str_w  = today_w.strftime('%Y-%m-%d')
                hoy_full_w = today_w.strftime('%d/%m/%Y')

                sent_today = self._daily_sent_count(db, bandeja, today_w)
                remaining  = _DAILY_LIMIT - sent_today
                if remaining <= 0:
                    _log.info(f'[MailAgent] {bandeja}: límite diario alcanzado ({sent_today})')
                    worker_results.append({'bandeja': bandeja, 'sent': 0, 'skipped': 0})
                    return

                batch_ids   = prospect_ids[:min(batch_size, remaining)]
                bot_nombre  = _BANDEJA_NOMBRE.get(bandeja, 'QoriCash')
                bot_cargo   = _BANDEJA_CARGO.get(bandeja, 'Equipo Comercial')
                es_personal = (bandeja == 'ggarcia@qoricash.pe')
                bot_user_w  = User.query.filter_by(role='Master').first()

                gmail_service, gmail_creds = self._build_service(bandeja)
                if not gmail_service:
                    _log.warning(f'[MailAgent] Sin servicio Gmail para {bandeja}')
                    worker_results.append({'bandeja': bandeja, 'sent': 0, 'skipped': len(batch_ids)})
                    return

                local_compra, local_venta = self._fetch_tc(ExchangeRate)
                tc_counter = 0
                sent = skipped = 0

                for pid in batch_ids:
                    try:
                        if tc_counter >= _TC_REFRESH_CADA:
                            local_compra, local_venta = self._fetch_tc(ExchangeRate)
                            tc_counter = 0

                        p = db.session.get(Prospecto, pid)
                        if not p or not p.email:
                            skipped += 1
                            continue

                        nombre_dest = (
                            (p.nombre_contacto or p.razon_social or 'equipo')
                            .split()[0].capitalize()
                        )

                        if modo == 'precios' and (p.num_contactos or 0) >= 1:
                            html        = _build_html_solo_precios(
                                nombre_dest=nombre_dest, nombre_firma=bot_nombre,
                                cargo=bot_cargo, compra=local_compra, venta=local_venta,
                                hoy=hoy_full_w,
                            )
                            subject     = 'QoriCash \u2014 Tipo de cambio actualizado'
                            tipo_envio  = 'solo_precios'
                            descripcion = f'Follow-up precios enviado [TC {local_compra}/{local_venta}]'
                        elif modo == 'precios':
                            html        = _build_html(
                                nombre_dest=nombre_dest, nombre_firma=bot_nombre,
                                cargo=bot_cargo, compra=local_compra, venta=local_venta,
                                hoy=hoy_full_w, es_personal=es_personal,
                            )
                            subject     = 'QoriCash \u2014 Tipo de cambio preferencial'
                            tipo_envio  = 'precios'
                            descripcion = f'Email de precios enviado [TC {local_compra}/{local_venta}]'
                        else:
                            html        = _build_html_prospeccion(
                                nombre_dest=nombre_dest, nombre_firma=bot_nombre,
                                cargo=bot_cargo, compra=local_compra, venta=local_venta,
                                hoy=hoy_full_w, es_personal=es_personal,
                            )
                            subject     = 'QoriCash \u2014 Casa de cambio digital \u00b7 SBS'
                            tipo_envio  = 'presentacion'
                            descripcion = 'Email de presentación institucional enviado'

                        ok = self._send_with_service(
                            gmail_service, gmail_creds, bandeja,
                            p.email, subject, html, img_cache,
                        )
                        if not ok:
                            skipped += 1
                            continue

                        next_date = self._next_business_day(5)
                        p.fecha_primer_contacto  = p.fecha_primer_contacto or hoy_str_w
                        p.fecha_ultimo_contacto  = hoy_str_w
                        p.fecha_proximo_contacto = next_date
                        p.num_contactos          = (p.num_contactos or 0) + 1
                        p.estado_comercial       = p.estado_comercial or 'presentado'
                        p.remitente              = bandeja
                        p.tipo_ultimo_envio      = tipo_envio

                        if bot_user_w:
                            db.session.add(ActividadProspecto(
                                prospecto_id=p.id,
                                user_id=bot_user_w.id,
                                tipo='email',
                                canal='email',
                                bandeja=bandeja,
                                descripcion=descripcion,
                                resultado='enviado',
                                nuevo_estado=p.estado_comercial,
                            ))

                        db.session.flush()
                        sent += 1
                        tc_counter += 1

                        # Pausa entre envíos para evitar ráfagas (filtros anti-spam)
                        eventlet.sleep(5)

                    except Exception as e:
                        _log.warning(f'[MailAgent] Error enviando pid={pid} via {bandeja}: {e}')
                        skipped += 1

                db.session.commit()
                worker_results.append({'bandeja': bandeja, 'sent': sent, 'skipped': skipped})

        # ── Fase 3: lanzar las 3 bandejas en paralelo y esperar ───────────────
        greenlets = [
            eventlet.spawn(_bandeja_worker, bandeja, ids_por_bandeja.get(bandeja, []))
            for bandeja in _BANDEJAS
        ]
        for gt in greenlets:
            gt.wait()

        sent_total  = sum(r['sent']    for r in worker_results)
        skipped_tot = sum(r['skipped'] for r in worker_results)

        msg = (f'[{modo.upper()}] {sent_total} emails enviados · '
               f'{skipped_tot} omitidos · TC {compra_ref}/{venta_ref}')
        return {
            'tasks':   sent_total,
            'message': msg,
            'metrics': {'emails_sent': sent_total},
        }

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _fetch_tc(self, ExchangeRate) -> tuple:
        """Obtiene compra/venta actuales desde la misma fuente que el widget del sitio."""
        try:
            tc = ExchangeRate.get_current_rates()
            return f'{float(tc["compra"]):.3f}', f'{float(tc["venta"]):.3f}'
        except Exception:
            return '—', '—'

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

    # Cache de imágenes a nivel de clase — PIL corre UNA sola vez en toda la vida del proceso
    _img_cache_built: dict = {}

    def _load_image_cache(self) -> dict:
        """Retorna el cache de imágenes CID. Lo construye solo la primera vez."""
        if MailAgent._img_cache_built:
            return MailAgent._img_cache_built

        cache: dict = {}

        def _load(path: str, cid: str, fname: str, tipo: str):
            if os.path.exists(path):
                with open(path, 'rb') as f:
                    cache[cid] = (f.read(), fname, tipo)

        _load(_IMG_ENCABEZADO, 'encabezado',    'encabezado.jpg', 'jpeg')
        _load(_IMG_BCP,        'logo_bcp',      'bcp.png',        'png')
        _load(_IMG_INTERBANK,  'logo_interbank','interbank.png',  'png')
        _load(_IMG_BANBIF,     'logo_banbif',   'banbif.png',     'png')

        if os.path.exists(_IMG_LOGO):
            try:
                from PIL import Image
                img = Image.open(_IMG_LOGO).convert('RGBA').resize((104, 104), Image.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format='PNG', optimize=True)
                cache['logo_qori'] = (buf.getvalue(), 'logo.png', 'png')
            except Exception:
                with open(_IMG_LOGO, 'rb') as f:
                    cache['logo_qori'] = (f.read(), 'logo.png', 'png')

        MailAgent._img_cache_built = cache
        _log.info(f'[MailAgent] Image cache construido: {len(cache)} imágenes')
        return MailAgent._img_cache_built

    def _build_service(self, sender: str):
        """Construye el servicio Gmail API una vez por bandeja/ciclo.
        Retorna (service, creds) o (None, None) si faltan credenciales."""
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        env_key       = _BANDEJAS.get(sender)
        refresh_token = os.environ.get(env_key or '', '').strip()
        client_id     = os.environ.get('GMAIL_CLIENT_ID', '')
        client_secret = os.environ.get('GMAIL_CLIENT_SECRET', '')

        if not all([env_key, refresh_token, client_id, client_secret]):
            _log.warning(f'[MailAgent] Credenciales Gmail faltantes para {sender} (var: {env_key})')
            return None, None

        try:
            creds = Credentials(
                token=None, refresh_token=refresh_token,
                token_uri='https://oauth2.googleapis.com/token',
                client_id=client_id, client_secret=client_secret,
                scopes=['https://mail.google.com/'],
            )
            creds.refresh(Request())
            service = build('gmail', 'v1', credentials=creds)
            _log.info(f'[MailAgent] Servicio Gmail listo para {sender}')
            return service, creds
        except Exception as e:
            _log.error(f'[MailAgent] Error construyendo servicio Gmail para {sender}: {e}')
            return None, None

    def _send_with_service(self, service, creds, sender: str, to: str,
                           subject: str, html: str, img_cache: dict) -> bool:
        """Envía un email usando el servicio Gmail pre-construido del ciclo.
        Refresca el token solo si expiró (ciclos > 1h)."""
        from google.auth.transport.requests import Request

        try:
            if creds.expired:
                creds.refresh(Request())

            msg_related = MIMEMultipart('related')
            msg_related['From']       = sender
            msg_related['To']         = to
            msg_related['Subject']    = subject
            msg_related['Date']       = formatdate(localtime=True)
            msg_related['Message-ID'] = make_msgid(domain='qoricash.pe')

            msg_alt = MIMEMultipart('alternative')
            msg_alt.attach(MIMEText(html, 'html'))
            msg_related.attach(msg_alt)

            for cid, (data, fname, tipo) in img_cache.items():
                part = MIMEImage(data, tipo)
                part.add_header('Content-ID', f'<{cid}>')
                part.add_header('Content-Disposition', 'inline', filename=fname)
                msg_related.attach(part)

            raw = base64.urlsafe_b64encode(msg_related.as_bytes()).decode()
            service.users().messages().send(userId='me', body={'raw': raw}).execute()
            return True

        except Exception as e:
            _log.error(f'[MailAgent] Gmail send error ({sender} → {to}): {e}')
            return False

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

            # Logo QoriCash redimensionado (solo precios follow-up)
            if os.path.exists(_IMG_LOGO):
                try:
                    from PIL import Image
                    img = Image.open(_IMG_LOGO).convert('RGBA').resize((104, 104), Image.LANCZOS)
                    buf = io.BytesIO()
                    img.save(buf, format='PNG', optimize=True)
                    logo_bytes = buf.getvalue()
                except Exception:
                    with open(_IMG_LOGO, 'rb') as f:
                        logo_bytes = f.read()
                part = MIMEImage(logo_bytes, 'png')
                part.add_header('Content-ID', '<logo_qori>')
                part.add_header('Content-Disposition', 'inline', filename='logo.png')
                msg_related.attach(part)

            raw = base64.urlsafe_b64encode(msg_related.as_bytes()).decode()
            service.users().messages().send(userId='me', body={'raw': raw}).execute()
            return True

        except Exception as e:
            _log.error(f'[MailAgent] Gmail send error ({sender} → {to}): {e}')
            return False
