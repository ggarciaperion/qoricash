"""
Prueba de template SOLO PRECIOS (follow-up) → ggarcia@qoricash.pe
Sin texto de presentación. TC directo, limpio, accionable.
"""
import os, sys, base64, io
from datetime import date
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText
from email.mime.image     import MIMEImage
from email.utils          import formatdate, make_msgid

BASE        = Path(__file__).parent
PROSPECCION = Path('/Users/gianpierre/Desktop/Prospeccion')
IMAGES      = BASE / 'app' / 'static' / 'images'

IMG_ENCABEZADO = IMAGES / 'encabezado_prospeccion.jpg'
IMG_BCP        = IMAGES / 'bcp_logo.png'
IMG_INTERBANK  = IMAGES / 'interbank_logo.png'
IMG_BANBIF     = IMAGES / 'banbif_logo.png'

SENDER = 'ggarcia@qoricash.pe'
DEST   = 'ggarcia@qoricash.pe'


def get_tc():
    db_url = os.environ.get('DATABASE_URL', '')
    if db_url:
        try:
            import psycopg2
            conn = psycopg2.connect(db_url, connect_timeout=5)
            cur  = conn.cursor()
            cur.execute("SELECT buy_rate, sell_rate FROM exchange_rates ORDER BY created_at DESC LIMIT 1")
            row = cur.fetchone()
            conn.close()
            if row:
                return f'{float(row[0]):.3f}', f'{float(row[1]):.3f}'
        except Exception as e:
            print(f'  (DB no accesible: {e} — usando fallback)')
    return '3.740', '3.810'


def build_html_solo_precios(nombre_dest, nombre_firma, cargo, compra, venta, hoy):
    return f"""\
<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  .card-bank {{ border:1px solid #E9EEF4;border-radius:10px;background:#FFFFFF;
                text-align:center;cursor:default;transition:all .2s; }}
  .card-bank:hover {{ background:#F0FDF4 !important;border-color:#86efac !important;
                      box-shadow:0 4px 16px rgba(22,163,74,0.12) !important; }}
  .card-bank:hover .acct-row {{ display:table-row !important; }}
</style>
</head>
<body style="margin:0;padding:0;background:#F1F5F9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#F1F5F9;padding:28px 0;">
<tr><td align="center">
<table width="560" cellpadding="0" cellspacing="0" border="0"
  style="max-width:560px;width:100%;background:#FFFFFF;border-radius:8px;overflow:hidden;
         box-shadow:0 4px 24px rgba(0,0,0,.07);">

  <!-- ENCABEZADO DEGRADADO TENUE -->
  <tr>
    <td style="background:#FFFFFF;border-top:4px solid #16a34a;
               padding:24px 36px 20px;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
        <td style="vertical-align:middle;">
          <table cellpadding="0" cellspacing="0" border="0"><tr>
            <td style="vertical-align:middle;">
              <img src="cid:logo_qori" alt="QoriCash" width="44" height="44"
                   style="display:block;border-radius:7px;
                          box-shadow:0 2px 8px rgba(0,0,0,0.10);">
            </td>
            <td style="vertical-align:middle;padding-left:12px;">
              <p style="margin:0;font-size:20px;font-weight:800;color:#0D1B2A;
                        letter-spacing:3px;text-transform:uppercase;line-height:1;">
                QORICASH</p>
              <p style="margin:3px 0 0;font-size:7px;font-weight:600;color:#94A3B8;
                        letter-spacing:3.8px;text-transform:uppercase;text-align:center;">
                CAMBIO DE DIVISAS</p>
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

  <!-- 1. SALUDO CON BORDE IZQUIERDO VERDE -->
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

  <!-- 2. LABEL TC CON BADGE EN VIVO -->
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
            <p style="margin:8px 0 0;font-size:10px;color:#94A3B8;">
              por d&oacute;lar &middot; USD</p>
          </td>
          <td width="50%" style="padding:28px 20px;text-align:center;">
            <p style="margin:0 0 8px;font-size:9px;font-weight:700;color:#94A3B8;
                      text-transform:uppercase;letter-spacing:2px;">Vendemos</p>
            <p style="margin:0;font-size:40px;font-weight:800;color:#16a34a;
                      letter-spacing:-1px;line-height:1;white-space:nowrap;">
              S/.&thinsp;{venta}</p>
            <p style="margin:8px 0 0;font-size:10px;color:#94A3B8;">
              por d&oacute;lar &middot; USD</p>
          </td>
        </tr>

        <!-- 4. FEATURE PILLS CON CHECKMARKS -->
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

  <!-- 3. BOTÓN ANCHO CON WHATSAPP -->
  <tr>
    <td style="padding:0 36px 28px;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td style="border-radius:6px;background:#0D1B2A;text-align:center;">
            <a href="https://wa.me/51910624404"
               style="display:block;padding:14px 28px;color:#FFFFFF;
                      text-decoration:none;font-size:13px;font-weight:700;
                      letter-spacing:0.5px;">
              &#128172;&nbsp;&nbsp;Cotizar ahora por WhatsApp &rarr;</a>
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

          <!-- BCP -->
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

          <!-- INTERBANK -->
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

          <!-- BANBIF -->
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

  <tr><td style="padding:16px 36px 0;">
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
            <a href="https://wa.me/51910624404" style="color:#64748B;text-decoration:none;">+51 910 624 404</a>
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


def get_gmail_service():
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


def send_email(service, subject, html):
    msg = MIMEMultipart('related')
    msg['From']       = SENDER
    msg['To']         = DEST
    msg['Subject']    = subject
    msg['Date']       = formatdate(localtime=True)
    msg['Message-ID'] = make_msgid(domain='qoricash.pe')

    alt = MIMEMultipart('alternative')
    alt.attach(MIMEText(html, 'html'))
    msg.attach(alt)

    def attach(path, cid, fname, tipo):
        if not path.exists():
            return
        with open(path, 'rb') as f:
            part = MIMEImage(f.read(), tipo)
        part.add_header('Content-ID', f'<{cid}>')
        part.add_header('Content-Disposition', 'inline', filename=fname)
        msg.attach(part)

    def attach_logo(path, cid, display_px=52):
        """Resize logo to 2× display size before embedding — 85KB → ~4KB."""
        if not path.exists():
            return
        from PIL import Image
        size = display_px * 2  # retina 2×
        img = Image.open(path).convert('RGBA').resize((size, size), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format='PNG', optimize=True)
        part = MIMEImage(buf.getvalue(), 'png')
        part.add_header('Content-ID', f'<{cid}>')
        part.add_header('Content-Disposition', 'inline', filename='logo.png')
        msg.attach(part)

    attach_logo(IMAGES / 'logo-email.png', 'logo_qori', display_px=52)
    attach(IMG_BCP,                   'logo_bcp',      'bcp.png',        'png')
    attach(IMG_INTERBANK,             'logo_interbank','interbank.png',  'png')
    attach(IMG_BANBIF,                'logo_banbif',   'banbif.png',     'png')

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId='me', body={'raw': raw}).execute()


# ── MAIN ───────────────────────────────────────────────────────────────────
print('\n=== TEST SOLO PRECIOS (follow-up) ===')
compra, venta = get_tc()
hoy = date.today().strftime('%d/%m/%Y')
print(f'TC: compra {compra} / venta {venta}')
print(f'Destino: {DEST}')

html = build_html_solo_precios(
    nombre_dest  = 'Gian Pierre',
    nombre_firma = 'Gian Pierre García',
    cargo        = 'Presidente de Negocios',
    compra       = compra,
    venta        = venta,
    hoy          = hoy,
)

print('\nConectando Gmail...')
service = get_gmail_service()

print('Enviando...')
send_email(service,
    subject = '[PRUEBA FOLLOW-UP] QoriCash \u2014 Tipo de cambio actualizado',
    html    = html,
)
print(f'\n✅ Enviado a {DEST}')
print('Asunto: [PRUEBA FOLLOW-UP] QoriCash — Tipo de cambio actualizado')
