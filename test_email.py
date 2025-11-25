"""
Script de prueba para verificar el envío de emails
Ejecuta este script para probar la configuración de Gmail
"""
import os
from dotenv import load_dotenv
from flask import Flask
from flask_mail import Mail, Message

# Cargar variables de entorno
load_dotenv()

# Crear aplicación Flask temporal
app = Flask(__name__)

# Configurar Flask-Mail
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True') == 'True'
app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL', 'False') == 'True'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

mail = Mail(app)

print("=" * 60)
print("TEST DE CONFIGURACION DE EMAIL - QoriCash Trading V2")
print("=" * 60)
print()
print(f"[SMTP] Servidor SMTP: {app.config['MAIL_SERVER']}")
print(f"[PORT] Puerto: {app.config['MAIL_PORT']}")
print(f"[TLS] TLS: {app.config['MAIL_USE_TLS']}")
print(f"[EMAIL] Email configurado: {app.config['MAIL_USERNAME']}")
print(f"[PASS] Contrasena configurada: {'Si' if app.config['MAIL_PASSWORD'] else 'No'}")
print()
print("-" * 60)

# Solicitar email de prueba
destinatario = input("Ingresa tu email personal para enviar un correo de prueba: ").strip()

if not destinatario or '@' not in destinatario:
    print("[ERROR] Email invalido. Abortando...")
    exit(1)

print()
print("[ENVIANDO] Intentando enviar email de prueba...")
print()

try:
    with app.app_context():
        # Crear mensaje de prueba
        msg = Message(
            subject="Test de Email - QoriCash Trading V2",
            recipients=[destinatario],
            html="""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body { font-family: Arial, sans-serif; line-height: 1.6; }
                    .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                    .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }
                    .content { background: white; padding: 30px; border: 1px solid #e5e7eb; border-radius: 0 0 8px 8px; }
                    .success { background: #d1fae5; border-left: 4px solid #10b981; padding: 15px; margin: 20px 0; }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>Test Exitoso</h1>
                        <p>QoriCash Trading V2</p>
                    </div>
                    <div class="content">
                        <div class="success">
                            <h2>Configuracion de Email Exitosa!</h2>
                            <p>Si estas leyendo este mensaje, significa que el sistema de envio de correos electronicos esta funcionando correctamente.</p>
                        </div>

                        <h3>Configuracion Verificada:</h3>
                        <ul>
                            <li>Servidor SMTP: smtp.gmail.com</li>
                            <li>Puerto: 587</li>
                            <li>TLS: Habilitado</li>
                            <li>Email remitente: info@qoricash.pe</li>
                        </ul>

                        <p><strong>Proximos pasos:</strong></p>
                        <ol>
                            <li>El sistema enviara automaticamente emails cuando se cree una nueva operacion</li>
                            <li>Tambien se enviara un email cuando una operacion se complete</li>
                            <li>Asegurate de que los clientes tengan su email configurado en el sistema</li>
                        </ol>

                        <p style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb; color: #6b7280; font-size: 13px;">
                            Este es un correo de prueba del sistema QoriCash Trading V2
                        </p>
                    </div>
                </div>
            </body>
            </html>
            """
        )

        # Enviar
        mail.send(msg)

        print("=" * 60)
        print("[EXITO] EMAIL ENVIADO EXITOSAMENTE!")
        print("=" * 60)
        print()
        print(f"[INFO] Revisa tu bandeja de entrada en: {destinatario}")
        print("[INFO] Si no lo ves, revisa tu carpeta de SPAM")
        print()
        print("[OK] La configuracion de Gmail esta funcionando correctamente.")
        print("     Ya puedes usar el sistema para enviar emails automaticamente.")
        print()

except Exception as e:
    print("=" * 60)
    print("[ERROR] ERROR AL ENVIAR EMAIL")
    print("=" * 60)
    print()
    print(f"Error: {str(e)}")
    print()
    print("[DEBUG] Posibles causas:")
    print()
    print("1. La contrasena no es una 'Contrasena de Aplicacion' de Google")
    print("   - Solucion: Ve a https://myaccount.google.com/ > Seguridad > Contrasenas de aplicaciones")
    print()
    print("2. La verificacion en dos pasos no esta habilitada")
    print("   - Solucion: Habilita la verificacion en dos pasos primero")
    print()
    print("3. Email o contrasena incorrectos")
    print("   - Solucion: Verifica el archivo .env")
    print()
    print("4. Problema de conexion a internet")
    print("   - Solucion: Verifica tu conexion")
    print()
