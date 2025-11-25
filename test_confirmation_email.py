"""
Script para probar el envio de email desde la cuenta de confirmacion
"""
import os
from dotenv import load_dotenv
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Cargar variables de entorno
load_dotenv()

# Configuracion
smtp_server = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
smtp_port = int(os.getenv('MAIL_PORT', 587))
username = os.getenv('MAIL_CONFIRMATION_USERNAME')
password = os.getenv('MAIL_CONFIRMATION_PASSWORD')
sender = os.getenv('MAIL_CONFIRMATION_SENDER')

print("=" * 60)
print("TEST EMAIL CONFIRMACION - mr.gpgv@gmail.com")
print("=" * 60)
print()
print(f"[SMTP] Servidor: {smtp_server}")
print(f"[PORT] Puerto: {smtp_port}")
print(f"[USER] Usuario: {username}")
print(f"[PASS] Password configurada: {'Si' if password else 'No'}")
print(f"[FROM] Remitente: {sender}")
print()
print("-" * 60)

# Solicitar destinatario
destinatario = input("Ingresa email de prueba: ").strip()

if not destinatario or '@' not in destinatario:
    print("[ERROR] Email invalido")
    exit(1)

print()
print("[ENVIANDO] Intentando enviar email...")
print()

try:
    # Crear mensaje
    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'Test Email Confirmacion - QoriCash'
    msg['From'] = sender
    msg['To'] = destinatario

    html = """
    <html>
    <body style="font-family: Arial, sans-serif; padding: 20px;">
        <h2 style="color: #10b981;">Test Exitoso</h2>
        <p>Este email fue enviado desde: <strong>{}</strong></p>
        <p>Si estas leyendo esto, la configuracion funciona correctamente.</p>
    </body>
    </html>
    """.format(sender)

    html_part = MIMEText(html, 'html')
    msg.attach(html_part)

    # Conectar y enviar
    print(f"[1] Conectando a {smtp_server}:{smtp_port}...")
    server = smtplib.SMTP(smtp_server, smtp_port)

    print("[2] Iniciando TLS...")
    server.starttls()

    print(f"[3] Autenticando como {username}...")
    server.login(username, password)

    print(f"[4] Enviando email a {destinatario}...")
    server.sendmail(sender, [destinatario], msg.as_string())

    print("[5] Cerrando conexion...")
    server.quit()

    print()
    print("=" * 60)
    print("[EXITO] EMAIL ENVIADO CORRECTAMENTE")
    print("=" * 60)
    print()
    print(f"[INFO] Revisa tu bandeja: {destinatario}")
    print("[INFO] Si no lo ves, revisa SPAM")
    print()

except smtplib.SMTPAuthenticationError as e:
    print()
    print("=" * 60)
    print("[ERROR] AUTENTICACION FALLIDA")
    print("=" * 60)
    print()
    print(f"Error: {str(e)}")
    print()
    print("Posibles causas:")
    print("1. La contrasena de aplicacion es incorrecta")
    print("2. La verificacion en dos pasos no esta habilitada")
    print("3. Necesitas generar una nueva contrasena de aplicacion")
    print()
    print("Pasos para crear contrasena de aplicacion en Gmail:")
    print("1. Ve a https://myaccount.google.com/")
    print("2. Seguridad > Verificacion en dos pasos")
    print("3. Habilita verificacion en dos pasos si no esta activa")
    print("4. Busca 'Contrasenas de aplicaciones'")
    print("5. Genera una nueva para 'Correo'")
    print()

except smtplib.SMTPException as e:
    print()
    print("=" * 60)
    print("[ERROR] ERROR SMTP")
    print("=" * 60)
    print()
    print(f"Error: {str(e)}")
    print()
    print("Esto puede deberse a:")
    print("1. Gmail bloquea el acceso por seguridad")
    print("2. Configuracion de 'Acceso de aplicaciones menos seguras'")
    print("3. Restricciones de la cuenta de Gmail")
    print()

except Exception as e:
    print()
    print("=" * 60)
    print("[ERROR] ERROR GENERAL")
    print("=" * 60)
    print()
    print(f"Error: {str(e)}")
    print()
