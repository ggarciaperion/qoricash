"""
Genera las claves VAPID para Web Push Notifications.
Ejecutar UNA sola vez y copiar los valores en las variables de entorno de Render.

Uso:
    python3 generate_vapid_keys.py

Luego agregar en Render → Environment:
    VAPID_PUBLIC_KEY  = <valor de la línea "Public Key">
    VAPID_PRIVATE_KEY = <el bloque PEM completo, con saltos de línea>
    VAPID_CLAIMS_SUB  = mailto:gerencia@qoricash.pe
"""
import base64
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization


def generate():
    private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())

    # PEM de la clave privada (para VAPID_PRIVATE_KEY en Render)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    # Clave pública como base64url sin padding (para VAPID_PUBLIC_KEY y el frontend)
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    public_b64 = base64.urlsafe_b64encode(public_bytes).rstrip(b'=').decode()

    print('=' * 60)
    print('VAPID Keys generadas — copiar en Render > Environment')
    print('=' * 60)
    print()
    print(f'VAPID_PUBLIC_KEY={public_b64}')
    print()
    print('VAPID_PRIVATE_KEY=')
    print(private_pem)
    print('VAPID_CLAIMS_SUB=mailto:gerencia@qoricash.pe')
    print()
    print('IMPORTANTE: Guardar en un lugar seguro.')
    print('No regenerar sin eliminar las suscripciones existentes en la BD.')


if __name__ == '__main__':
    generate()
