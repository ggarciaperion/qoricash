"""
send_test_transaccional.py
Prueba visual de TODOS los correos transaccionales del sistema → ggarcia@qoricash.pe
Usa Flask mínimo para render_template_string + Gmail API para enviar.
Ejecutar desde: /Users/gianpierre/Desktop/Qoricash/Sistema/qoricash/
  python3 send_test_transaccional.py
"""
import sys, os, base64
from pathlib import Path
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

HERE        = Path(__file__).parent
PROSPECCION = Path('/Users/gianpierre/Desktop/Prospeccion')
STATIC      = HERE / 'app' / 'static' / 'images'
DEST        = 'ggarcia@qoricash.pe'
SENDER      = 'ggarcia@qoricash.pe'

sys.path.insert(0, str(HERE))

# ── Embeber banners como base64 para que el test no dependa del servidor ──
import base64 as _b64

def _img_data_uri(path):
    data = _b64.b64encode(Path(path).read_bytes()).decode()
    return f'data:image/jpeg;base64,{data}'

BANNER_CORP  = _img_data_uri(STATIC / 'encabezado_corporativo.jpg')
BANNER_PERS  = _img_data_uri(STATIC / 'encabezado_personal.jpg')

# ── Flask mínimo (solo para render_template_string) ─────────────────────
from flask import Flask
mini_app = Flask(__name__)
mini_app.config['SECRET_KEY'] = 'test'

# ── Gmail API ──────────────────────────────────────────────────────────────
def get_gmail():
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

def send_gmail(service, subject, html):
    msg = MIMEMultipart('alternative')
    msg['From']    = SENDER
    msg['To']      = DEST
    msg['Subject'] = subject
    msg.attach(MIMEText('(Ver versión HTML)', 'plain'))
    msg.attach(MIMEText(html, 'html'))
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId='me', body={'raw': raw}).execute()

# ── Mocks ──────────────────────────────────────────────────────────────────
class MockClient:
    id = 9999; dni = '12345678'; document_type = 'DNI'; document_number = '12345678'
    email = DEST; phone = '987654321'; full_name = 'Gianpierre Garcia'; razon_social = None

class MockClientRUC:
    id = 9998; dni = '20612345678'; document_type = 'RUC'; document_number = '20612345678'
    email = DEST; phone = '01-4567890'; full_name = None; razon_social = 'DEMO EMPRESA S.A.C.'
    bank_accounts = []

class MockTrader:
    id = 1; username = 'ggarcia'; email = DEST; role = 'Trader'

class MockProof:
    comprobante_url = 'https://www.qoricash.pe'; comentario = 'Transferencia procesada'

class MockInvoice:
    invoice_number = 'B001-00000123'; nubefact_enlace_pdf = None

class MockClientOp:
    id = 9999; dni = '12345678'; document_type = 'DNI'; document_number = '12345678'
    email = DEST; phone = '987654321'; full_name = 'Gianpierre Garcia'; razon_social = None
    bank_accounts_json = None
    @property
    def bank_accounts(self):
        return [{'bank_name':'BCP','currency':'PEN','account_number':'191-12345678-0-12'}]

class MockOperation:
    operation_id     = 'EXP-TEST-001'
    operation_type   = 'Compra'
    amount_usd       = 5000.00
    exchange_rate    = 3.4620
    amount_pen       = 17310.00
    status           = 'Pendiente'
    notes            = 'Operación de prueba'
    source_bank_name = 'BCP'
    source_account   = '191-12345678-0-12'
    destination_account = '191-99999999-0-99'
    operator_proofs  = [MockProof()]
    invoices         = [MockInvoice()]
    new_operation_email_sent = False
    user             = MockTrader()
    created_at       = datetime(2026, 8, 27, 9, 30)
    completed_at     = datetime(2026, 8, 27, 10, 15)
    client           = MockClientOp()

COMPLAINT = {
    'complaint_number': 'REC-2026-001',
    'tipo_solicitud':   'Reclamo',
    'tipo_documento':   'DNI',
    'numero_documento': '12345678',
    'nombres':          'Gianpierre',
    'apellidos':        'Garcia',
    'email':            DEST,
    'telefono':         '987654321',
    'direccion':        'Av. Brasil 2790, Pueblo Libre',
    'detalle':          'Este es un reclamo de prueba para validar el diseño del correo.',
}

# ── Main ───────────────────────────────────────────────────────────────────
def main():
    print(f'\n=== TEST CORREOS TRANSACCIONALES → {DEST} ===\n')

    try:
        svc = get_gmail()
        print('Gmail API: OK\n')
    except Exception as e:
        print(f'ERROR Gmail API: {e}')
        sys.exit(1)

    # Importar dentro del app context
    with mini_app.app_context():
        from app.services.email_templates import EmailTemplates
        from app.services.email_service   import EmailService

        results = []

        def try_send(label, subject, render_fn):
            try:
                html = render_fn()
                # Reemplazar URLs del servidor por data URIs locales
                html = html.replace(
                    'https://app.qoricash.pe/static/images/encabezado_corporativo.jpg', BANNER_CORP
                ).replace(
                    'https://app.qoricash.pe/static/images/encabezado_personal.jpg', BANNER_PERS
                )
                send_gmail(svc, subject, html)
                print(f'  [OK]  {label}')
                results.append((label, True))
            except Exception as e:
                print(f'  [FAIL]  {label} — {e}')
                results.append((label, False))

        # ── email_templates.py ─────────────────────────────────────────────
        try_send('Bienvenida DNI (móvil)',
                 '[TEST 1] Bienvenida — QoriCash',
                 lambda: EmailTemplates._render_mobile_welcome_template(MockClient(), canal='movil'))

        try_send('Bienvenida RUC (web)',
                 '[TEST 2] Bienvenida Empresa — QoriCash',
                 lambda: EmailTemplates._render_mobile_welcome_template(MockClientRUC(), canal='web'))

        try_send('Activación + clave (DNI)',
                 '[TEST 3] Cuenta Activada + Clave — QoriCash',
                 lambda: EmailTemplates._render_trader_activation_template(MockClient(), MockTrader(), 'Qori2026!'))

        try_send('Activación + clave (RUC)',
                 '[TEST 4] Cuenta Activada + Clave Empresa — QoriCash',
                 lambda: EmailTemplates._render_trader_activation_template(MockClientRUC(), MockTrader(), 'Corp#2026'))

        try_send('Activación auto (sin clave)',
                 '[TEST 5] Cuenta Activada — QoriCash',
                 lambda: EmailTemplates._render_auto_activation_template(MockClient()))

        # ── email_service.py ───────────────────────────────────────────────
        try_send('Nueva Operación',
                 '[TEST 6] Nueva Operación #EXP-TEST-001 — QoriCash',
                 lambda: EmailService._render_new_operation_template(MockOperation()))

        try_send('Operación Completada',
                 '[TEST 7] Operación Completada #EXP-TEST-001 — QoriCash',
                 lambda: EmailService._render_completed_operation_template(MockOperation()))

        try_send('Operación Cancelada',
                 '[TEST 8] Operación Cancelada #EXP-TEST-001 — QoriCash',
                 lambda: EmailService._render_canceled_operation_template(MockOperation(), 'Plazo de pago vencido'))

        try_send('Modificación de Importe',
                 '[TEST 9] Actualización de Importe #EXP-TEST-001 — QoriCash',
                 lambda: EmailService._render_amount_modified_template(MockOperation(), 4800.00, 16617.60))

        try_send('Nuevo Cliente (trader)',
                 '[TEST 10] Registro Iniciado — QoriCash',
                 lambda: EmailService._render_new_client_template(MockClientRUC(), MockTrader()))

        try_send('Activación cliente (trader)',
                 '[TEST 11] Cuenta Activada — QoriCash',
                 lambda: EmailService._render_client_activation_template(MockClient(), MockTrader()))

        try_send('Contraseña temporal',
                 '[TEST 12] Tu nueva contraseña — QoriCash',
                 lambda: EmailService._render_temporary_password_template('Gianpierre Garcia', 'Temp#2026'))

        try_send('Reclamo',
                 '[TEST 13] Reclamo REC-2026-001 — QoriCash',
                 lambda: EmailService._render_complaint_template(COMPLAINT))

        ok = sum(1 for _, s in results if s)
        print(f'\n{ok}/{len(results)} correos enviados OK')
        print(f'Revisa {DEST}\n')

if __name__ == '__main__':
    main()
