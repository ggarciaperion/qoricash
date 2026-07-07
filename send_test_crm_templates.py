"""
Test 3 plantillas CRM oficiales → ggarcia@qoricash.pe
Standalone: no requiere Flask ni Python 3.10+
Usa token.json de Desktop/Prospeccion/
"""
import os, sys, base64
from pathlib import Path
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

PROSPECCION = Path('/Users/gianpierre/Desktop/Prospeccion')
DEST        = 'ggarcia@qoricash.pe'
SENDER      = 'ggarcia@qoricash.pe'
COMPRA      = '3.720'
VENTA       = '3.730'
NOMBRE      = 'Gian Pierre'
EMPRESA     = 'QoriCash SAC'
TRADER      = 'Gian Pierre García'
CARGO       = 'Presidente de Negocios'
LOGO_URL    = 'https://www.qoricash.pe/logofirma.png'

def now_peru():
    return datetime.now(timezone(timedelta(hours=-5)))

HOY = now_peru().strftime('%d/%m/%Y')

# ── Gmail ──────────────────────────────────────────────────────────────────
def get_service():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    creds = Credentials.from_authorized_user_file(
        str(PROSPECCION / 'token.json'),
        scopes=['https://mail.google.com/']
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build('gmail', 'v1', credentials=creds)

def send(service, subject, html):
    msg = MIMEMultipart('alternative')
    msg['From']    = SENDER
    msg['To']      = DEST
    msg['Subject'] = subject
    msg.attach(MIMEText(html, 'html'))
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId='me', body={'raw': raw}).execute()

# ── Componentes comunes ────────────────────────────────────────────────────
HEADER = f"""\
<tr>
  <td style="background:#0D1B2A;padding:18px 28px;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
      <td><img src="{LOGO_URL}" alt="QoriCash" height="32" style="display:block;height:32px;"></td>
      <td style="padding-left:6px;vertical-align:middle;">
        <span style="font-size:14px;font-weight:800;color:#FFFFFF;letter-spacing:2px;">QORICASH</span>
      </td>
      <td align="right">
        <span style="font-size:10px;font-weight:700;color:#5CB85C;text-transform:uppercase;
                     letter-spacing:1.5px;background:rgba(92,184,92,.12);
                     padding:4px 10px;border-radius:20px;border:1px solid rgba(92,184,92,.3);">
          {HOY}
        </span>
      </td>
    </tr></table>
  </td>
</tr>
<tr>
  <td style="background:#F8FAFC;padding:20px 28px;border-bottom:1px solid #E9EEF4;">
    <p style="margin:0;font-size:13px;color:#475569;line-height:1.7;">
      Estimado(a) <strong>{NOMBRE}</strong>, a continuaci&oacute;n las tasas del tipo de cambio en estos momentos.
    </p>
  </td>
</tr>"""

FIRMA = f"""\
<tr>
  <td style="padding:16px 28px;border-top:1px solid #F1F5F9;background:#FAFAFA;">
    <table cellpadding="0" cellspacing="0" border="0"><tr>
      <td style="padding-right:12px;vertical-align:middle;">
        <img src="{LOGO_URL}" width="32" height="32" alt="QoriCash" style="display:block;border-radius:4px;">
      </td>
      <td style="vertical-align:middle;padding-right:24px;">
        <p style="margin:0;font-size:12px;font-weight:700;color:#0D1B2A;">{TRADER}</p>
        <p style="margin:1px 0 0;font-size:10px;color:#5CB85C;font-weight:600;">{CARGO}</p>
      </td>
      <td style="width:1px;background:#E2E8F0;padding:0;"></td>
      <td style="width:24px;"></td>
      <td style="vertical-align:middle;">
        <p style="margin:0;font-size:10px;color:#64748B;">
          <a href="https://wa.me/51910624404" style="color:#64748B;text-decoration:none;">+51 910 624 404</a>
          &nbsp;&middot;&nbsp;
          <a href="https://www.qoricash.pe" style="color:#5CB85C;text-decoration:none;font-weight:600;">www.qoricash.pe</a>
        </p>
        <p style="margin:2px 0 0;font-size:9px;color:#94A3B8;">Av. Brasil 2790, int. 504 &mdash; Pueblo Libre</p>
      </td>
    </tr></table>
  </td>
</tr>"""

PIE = """\
<tr>
  <td style="padding:12px 28px;background:#F8FAFC;border-top:1px solid #F1F5F9;">
    <p style="margin:0;font-size:9px;color:#CBD5E1;text-align:center;">
      Regulada por la SBS &nbsp;&middot;&nbsp; Res. N.&ordm; 00313-2026 &nbsp;&middot;&nbsp;
      Precios sujetos a variaci&oacute;n &nbsp;&middot;&nbsp;
      Para no recibir m&aacute;s comunicaciones, responda con asunto <em>NO CONTACTAR</em>.
    </p>
  </td>
</tr>"""

BANCOS = """\
<tr>
  <td style="padding:24px 28px 8px;">
    <p style="margin:0 0 14px;font-size:10px;font-weight:900;color:#94A3B8;text-transform:uppercase;letter-spacing:1.4px;">
      <strong>Operamos con los principales bancos del Per&uacute;</strong>
    </p>
    <table width="100%" cellpadding="0" cellspacing="0" border="0"
      style="border:1px solid #E9EEF4;border-radius:10px;overflow:hidden;margin-bottom:16px;">
      <tr style="border-bottom:1px solid #F1F5F9;">
        <td style="width:90px;padding:12px 8px 12px 18px;vertical-align:middle;">
          <span style="font-size:15px;font-weight:800;color:#F97316;">BCP</span>
        </td>
        <td style="padding:14px 12px;vertical-align:middle;border-left:1px solid #F1F5F9;">
          <p style="margin:0;font-size:9px;color:#94A3B8;text-transform:uppercase;">Soles</p>
          <p style="margin:2px 0 0;font-size:12px;font-weight:700;color:#1E293B;">1937353150041</p>
        </td>
        <td style="padding:14px 18px 14px 12px;vertical-align:middle;border-left:1px solid #F1F5F9;">
          <p style="margin:0;font-size:9px;color:#94A3B8;text-transform:uppercase;">D&oacute;lares</p>
          <p style="margin:2px 0 0;font-size:12px;font-weight:700;color:#1E293B;">1917357790119</p>
        </td>
      </tr>
      <tr style="border-bottom:1px solid #F1F5F9;background:#FAFBFC;">
        <td style="width:90px;padding:12px 8px 12px 18px;vertical-align:middle;">
          <span style="font-size:15px;font-weight:800;color:#00A859;">Interbank</span>
        </td>
        <td style="padding:14px 12px;vertical-align:middle;border-left:1px solid #F1F5F9;">
          <p style="margin:0;font-size:9px;color:#94A3B8;text-transform:uppercase;">Soles</p>
          <p style="margin:2px 0 0;font-size:12px;font-weight:700;color:#1E293B;">200-3007757571</p>
        </td>
        <td style="padding:14px 18px 14px 12px;vertical-align:middle;border-left:1px solid #F1F5F9;">
          <p style="margin:0;font-size:9px;color:#94A3B8;text-transform:uppercase;">D&oacute;lares</p>
          <p style="margin:2px 0 0;font-size:12px;font-weight:700;color:#1E293B;">200-3007757589</p>
        </td>
      </tr>
      <tr>
        <td style="width:90px;padding:12px 8px 12px 18px;vertical-align:middle;">
          <span style="font-size:15px;font-weight:800;color:#004B9D;">BanBif</span>
        </td>
        <td style="padding:14px 12px;vertical-align:middle;border-left:1px solid #F1F5F9;">
          <p style="margin:0;font-size:9px;color:#94A3B8;text-transform:uppercase;">Soles</p>
          <p style="margin:2px 0 0;font-size:12px;font-weight:700;color:#1E293B;">007000845805</p>
        </td>
        <td style="padding:14px 18px 14px 12px;vertical-align:middle;border-left:1px solid #F1F5F9;">
          <p style="margin:0;font-size:9px;color:#94A3B8;text-transform:uppercase;">D&oacute;lares</p>
          <p style="margin:2px 0 0;font-size:12px;font-weight:700;color:#1E293B;">007000845813</p>
        </td>
      </tr>
    </table>
    <table cellpadding="0" cellspacing="0" border="0" style="margin-bottom:28px;">
      <tr><td style="border-radius:7px;background:#0D1B2A;">
        <a href="https://wa.me/51910624404"
           style="display:inline-block;padding:13px 30px;color:#FFFFFF;text-decoration:none;font-size:12px;font-weight:700;">
          Cotizar en l&iacute;nea &nbsp;&rarr;
        </a>
      </td></tr>
    </table>
  </td>
</tr>"""

# ── Plantilla 1: PRESENTACIÓN ──────────────────────────────────────────────
def build_presentacion():
    return f"""\
<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;font-size:14px;color:#1E293B;line-height:1.7;max-width:620px;margin:0 auto;padding:24px;">
  <table width="100%" cellpadding="0" cellspacing="0" border="0"
    style="background:#FFFFFF;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.07);">
    {HEADER}
    <tr><td style="padding:28px 28px 8px;">
      <p>Estimado(a) <strong>{NOMBRE}</strong>,</p>
      <p style="text-align:justify;">Mi nombre es <strong>{TRADER}</strong>, {CARGO} de
        <strong>QoriCash SAC</strong>, fintech de cambio de divisas 100% digital,
        regulada por la Superintendencia de Banca, Seguros y AFP del Per&uacute;.</p>
      <p style="text-align:justify;">Trabajamos con empresas que realizan operaciones frecuentes de compra y venta
        de d&oacute;lares, y que en muchos casos est&aacute;n dejando dinero sobre la mesa al operar con el tipo
        de cambio que les ofrece su entidad financiera actual.</p>
      <p style="text-align:justify;">Porque cada centavo cuenta, le ofrecemos <strong>tasas que superan
        consistentemente al sistema bancario tradicional</strong>, con ejecuci&oacute;n inmediata y cero costos
        ocultos.</p>
      <div style="background:#F7F9FC;border-left:4px solid #4CAF50;border-radius:4px;padding:16px 20px;margin:24px 0;">
        <p style="margin:0 0 6px;font-weight:bold;color:#0D1B2A;">Le propongo algo concreto:</p>
        <p style="margin:0;color:#4A5568;text-align:justify;">Una comparativa sin compromiso entre las tasas que
          recibe hoy de su proveedor actual y las que podemos ofrecerle en QoriCash, en tiempo real.</p>
      </div>
      <div style="margin:16px 0 24px;">
        <a href="https://qoricash.pe/presentacion.pdf"
           style="display:inline-block;padding:10px 24px;background:#5CB85C;color:#ffffff;
                  text-decoration:none;border-radius:6px;font-size:13px;font-weight:700;"
           target="_blank">Ver presentaci&oacute;n QoriCash</a>
      </div>
      <p>Contamos con cuentas corrientes en los bancos m&aacute;s importantes del Per&uacute;:</p>
    </td></tr>
    {BANCOS}
    {FIRMA}
    {PIE}
  </table>
</body></html>"""

# ── Plantilla 2: PRECIO ───────────────────────────────────────────────────
def build_precio(compra, venta):
    ticker = f"""\
<tr>
  <td style="padding:20px 28px;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0"
      style="border:1.5px solid #E2E8F0;border-radius:10px;overflow:hidden;">
      <tr>
        <td width="50%" style="padding:24px 28px;border-right:1.5px solid #E2E8F0;text-align:center;">
          <p style="margin:0 0 6px;font-size:9px;font-weight:700;color:#94A3B8;text-transform:uppercase;letter-spacing:1.8px;">Compramos</p>
          <p style="margin:0;font-size:34px;font-weight:800;color:#0D1B2A;letter-spacing:-1px;line-height:1;">S/. {compra}</p>
          <p style="margin:8px 0 0;font-size:10px;color:#94A3B8;">por d&oacute;lar &middot; USD</p>
        </td>
        <td width="50%" style="padding:24px 28px;text-align:center;">
          <p style="margin:0 0 6px;font-size:9px;font-weight:700;color:#94A3B8;text-transform:uppercase;letter-spacing:1.8px;">Vendemos</p>
          <p style="margin:0;font-size:34px;font-weight:800;color:#16a34a;letter-spacing:-1px;line-height:1;">S/. {venta}</p>
          <p style="margin:8px 0 0;font-size:10px;color:#94A3B8;">por d&oacute;lar &middot; USD</p>
        </td>
      </tr>
      <tr>
        <td colspan="2" style="padding:10px 28px;border-top:1.5px solid #E2E8F0;text-align:center;">
          <span style="font-size:10px;font-weight:600;color:#64748B;">
            &bull;&nbsp; Operaci&oacute;n en minutos &nbsp;&middot;&nbsp; Sin costo de transferencia
          </span>
        </td>
      </tr>
    </table>
  </td>
</tr>"""
    return f"""\
<!DOCTYPE html><html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#F4F6F8;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#F4F6F8;padding:32px 0;">
<tr><td align="center">
<table width="560" cellpadding="0" cellspacing="0" border="0"
  style="max-width:560px;width:100%;background:#FFFFFF;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.07);">
  {HEADER}
  {ticker}
  {BANCOS}
  {FIRMA}
  {PIE}
</table>
</td></tr>
</table>
</body></html>"""

# ── Plantilla 3: SEGUIMIENTO ──────────────────────────────────────────────
def build_seguimiento():
    header_seg = f"""\
<tr>
  <td style="background:#0D1B2A;padding:18px 28px;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
      <td><img src="{LOGO_URL}" alt="QoriCash" height="32" style="display:block;height:32px;"></td>
      <td style="padding-left:6px;vertical-align:middle;">
        <span style="font-size:14px;font-weight:800;color:#FFFFFF;letter-spacing:2px;">QORICASH</span>
      </td>
      <td align="right">
        <span style="font-size:10px;font-weight:700;color:#5CB85C;text-transform:uppercase;
                     letter-spacing:1.5px;background:rgba(92,184,92,.12);
                     padding:4px 10px;border-radius:20px;border:1px solid rgba(92,184,92,.3);">
          {HOY}
        </span>
      </td>
    </tr></table>
  </td>
</tr>"""
    cuerpo = f"""\
<tr>
  <td style="padding:28px 28px 8px;">
    <p style="margin:0 0 16px;font-size:14px;color:#1E293B;line-height:1.7;">
      Estimado(a) <strong>{NOMBRE}</strong>,
    </p>
    <p style="margin:0 0 16px;font-size:13px;color:#475569;line-height:1.7;text-align:justify;">
      Me comunico nuevamente desde QoriCash para darle seguimiento a la presentaci&oacute;n que le enviamos
      recientemente. Quiero asegurarme de que haya tenido la oportunidad de revisarla y saber si tiene
      alguna consulta sobre c&oacute;mo podemos optimizar sus operaciones de cambio de d&oacute;lares.
    </p>
    <div style="background:#F0FDF4;border-left:4px solid #5CB85C;border-radius:4px;padding:16px 20px;margin:20px 0;">
      <p style="margin:0 0 8px;font-weight:700;font-size:13px;color:#0D1B2A;">En QoriCash ofrecemos:</p>
      <p style="margin:0;font-size:13px;color:#4A5568;line-height:1.85;">
        &#10003;&nbsp; Tasas que superan consistentemente al sistema bancario<br>
        &#10003;&nbsp; Operaci&oacute;n 100% digital, en minutos y sin costos ocultos<br>
        &#10003;&nbsp; Atenci&oacute;n personalizada con su ejecutivo asignado
      </p>
    </div>
    <p style="margin:0 0 22px;font-size:13px;color:#475569;line-height:1.7;text-align:justify;">
      &iquest;Le parece si coordinamos una llamada breve esta semana para mostrarle en tiempo real
      la diferencia entre nuestras tasas y las que recibe actualmente?
    </p>
    <table cellpadding="0" cellspacing="0" border="0" style="margin-bottom:28px;">
      <tr><td style="border-radius:7px;background:#5CB85C;">
        <a href="https://wa.me/51910624404"
           style="display:inline-block;padding:12px 28px;color:#FFFFFF;text-decoration:none;font-size:13px;font-weight:700;">
          Coordinar llamada &nbsp;&rarr;
        </a>
      </td></tr>
    </table>
  </td>
</tr>"""
    return f"""\
<!DOCTYPE html><html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#F4F6F8;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#F4F6F8;padding:32px 0;">
<tr><td align="center">
<table width="560" cellpadding="0" cellspacing="0" border="0"
  style="max-width:560px;width:100%;background:#FFFFFF;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.07);">
  {header_seg}
  {cuerpo}
  {FIRMA}
  {PIE}
</table>
</td></tr>
</table>
</body></html>"""

# ── MAIN ───────────────────────────────────────────────────────────────────
print(f'\n=== TEST 3 PLANTILLAS CRM → {DEST} ===\n')

try:
    service = get_service()
    print('Gmail API OK\n')
except Exception as e:
    print(f'ERROR Gmail API: {e}')
    sys.exit(1)

correos = [
    ('[TEST 1/3] Presentación — QoriCash',          build_presentacion()),
    ('[TEST 2/3] Tipo de cambio QORICASH',          build_precio(COMPRA, VENTA)),
    ('[TEST 3/3] Seguimiento — QoriCash',           build_seguimiento()),
]

for subject, html in correos:
    try:
        send(service, subject, html)
        print(f'  ✓ {subject}')
    except Exception as e:
        print(f'  ✗ {subject} — ERROR: {e}')

print(f'\nRevisa tu bandeja {DEST}')
