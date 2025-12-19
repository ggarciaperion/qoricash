"""
Script para validar credenciales de NubeFact
"""
import os
import sys
import requests

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app

def validate_credentials():
    """Validar credenciales de NubeFact"""
    app = create_app()

    with app.app_context():
        print("=" * 80)
        print("VALIDACIÓN DE CREDENCIALES DE NUBEFACT")
        print("=" * 80)
        print()

        # Obtener configuración
        api_url = app.config.get('NUBEFACT_API_URL')
        api_token = app.config.get('NUBEFACT_TOKEN')
        nubefact_enabled = app.config.get('NUBEFACT_ENABLED')

        print("📋 CONFIGURACIÓN ACTUAL:")
        print("-" * 80)
        print(f"NUBEFACT_ENABLED: {nubefact_enabled}")
        print(f"NUBEFACT_API_URL: {api_url}")
        print(f"NUBEFACT_TOKEN: {api_token[:20]}...{api_token[-20:] if api_token and len(api_token) > 40 else 'CORTO'}")
        print()

        # Validar configuración básica
        if not nubefact_enabled:
            print("❌ NUBEFACT_ENABLED está en False")
            print("   Solución: Cambia la variable de entorno a True")
            return

        if not api_url:
            print("❌ NUBEFACT_API_URL no está configurado")
            return

        if not api_token:
            print("❌ NUBEFACT_TOKEN no está configurado")
            return

        print("✅ Configuración básica OK")
        print()

        # Intentar diferentes métodos de autenticación
        print("🔐 PROBANDO AUTENTICACIÓN...")
        print("-" * 80)

        # Método 1: Token en header (formato actual)
        print("Método 1: Authorization: Token token=\"...\"")
        headers1 = {
            'Authorization': f'Token token="{api_token}"',
            'Content-Type': 'application/json'
        }
        test_auth_method(api_url, headers1, "Método 1")

        # Método 2: Token simple
        print("\nMétodo 2: Authorization: Bearer ...")
        headers2 = {
            'Authorization': f'Bearer {api_token}',
            'Content-Type': 'application/json'
        }
        test_auth_method(api_url, headers2, "Método 2")

        # Método 3: Solo token
        print("\nMétodo 3: Authorization: Token ...")
        headers3 = {
            'Authorization': f'Token {api_token}',
            'Content-Type': 'application/json'
        }
        test_auth_method(api_url, headers3, "Método 3")

        print()
        print("=" * 80)
        print("RECOMENDACIONES:")
        print("=" * 80)
        print()
        print("1. Accede a https://app.nubefact.com y verifica:")
        print("   - Tu cuenta esté activa")
        print("   - La RUTA/URL del API")
        print("   - El TOKEN de autenticación")
        print()
        print("2. Si la URL o TOKEN cambiaron, actualiza las variables en Render")
        print()
        print("3. Contacta a soporte@nubefact.com si sigues teniendo problemas")
        print()


def test_auth_method(api_url, headers, method_name):
    """Probar un método de autenticación"""
    test_data = {
        "operacion": "generar_comprobante",
        "tipo_de_comprobante": "03",
        "serie": "B001",
        "numero": "-",
        "sunat_transaction": 1,
        "cliente_tipo_de_documento": "1",
        "cliente_numero_de_documento": "12345678",
        "cliente_denominacion": "CLIENTE DE PRUEBA",
        "cliente_direccion": "AV. PRUEBA 123",
        "fecha_de_emision": "2025-01-01",
        "moneda": 1,
        "total_exonerada": 100.00,
        "total": 100.00,
        "items": [{
            "unidad_de_medida": "ZZ",
            "codigo": "001",
            "descripcion": "PRUEBA",
            "cantidad": 1,
            "valor_unitario": 100.00,
            "precio_unitario": 100.00,
            "subtotal": 100.00,
            "tipo_de_igv": 9,
            "igv": 0,
            "total": 100.00
        }]
    }

    try:
        response = requests.post(
            f'{api_url}/documento/generar',
            json=test_data,
            headers=headers,
            timeout=10
        )

        print(f"  Status: {response.status_code}", end=" - ")

        if response.status_code == 200 or response.status_code == 201:
            print("✅ AUTENTICACIÓN EXITOSA!")
            try:
                data = response.json()
                print(f"  Respuesta: {data}")
            except:
                print(f"  Respuesta: {response.text[:100]}")
            return True
        elif response.status_code == 401:
            print("❌ No autorizado (credenciales incorrectas)")
            try:
                data = response.json()
                print(f"  Error: {data}")
            except:
                print(f"  Respuesta: {response.text[:100]}")
        elif response.status_code == 404:
            print("❌ Endpoint no encontrado (URL incorrecta)")
        elif response.status_code == 400:
            print("⚠️  Bad Request (credenciales OK, datos incorrectos)")
            try:
                data = response.json()
                print(f"  Error: {data}")
            except:
                print(f"  Respuesta: {response.text[:100]}")
        else:
            print(f"⚠️  Código {response.status_code}")
            print(f"  Respuesta: {response.text[:100]}")

    except requests.exceptions.Timeout:
        print("❌ Timeout")
    except requests.exceptions.ConnectionError:
        print("❌ Error de conexión")
    except Exception as e:
        print(f"❌ Error: {e}")

    return False


if __name__ == '__main__':
    validate_credentials()
