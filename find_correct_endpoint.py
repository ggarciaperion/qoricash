"""
Script para encontrar el endpoint correcto de NubeFact
"""
import os
import sys
import requests
from datetime import datetime

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app

def find_endpoint():
    """Encontrar el endpoint correcto de NubeFact"""
    app = create_app()

    with app.app_context():
        print("=" * 80)
        print("BÚSQUEDA DEL ENDPOINT CORRECTO DE NUBEFACT")
        print("=" * 80)
        print()

        api_token = "c7328e0c40924368814da869b11326d7e1bceebc603c43309047102b397b6370"
        base_url = "https://api.nubefact.com/api/v1/931258a7-ab41-488d-aedf-b8a2a502a224"

        # Posibles endpoints
        endpoints = [
            "",  # Solo la base
            "/generar",
            "/documento/generar",
            "/comprobante/generar",
            "/invoice",
            "/invoice/create",
            "/factura",
            "/factura/generar",
            "/boleta",
            "/boleta/generar",
            "/send",
            "/api/generar",
        ]

        # Datos de prueba
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
            "cliente_email": "",
            "fecha_de_emision": datetime.now().strftime("%Y-%m-%d"),
            "moneda": 1,
            "tipo_de_cambio": "",
            "porcentaje_de_igv": 18.00,
            "total_gravada": 0,
            "total_inafecta": 0,
            "total_exonerada": 100.00,
            "total_igv": 0,
            "total_gratuita": 0,
            "total_otros_cargos": 0,
            "total": 100.00,
            "enviar_automaticamente_a_la_sunat": False,
            "enviar_automaticamente_al_cliente": False,
            "items": [{
                "unidad_de_medida": "ZZ",
                "codigo": "001",
                "descripcion": "SERVICIO DE PRUEBA",
                "cantidad": 1,
                "valor_unitario": 100.00,
                "precio_unitario": 100.00,
                "subtotal": 100.00,
                "tipo_de_igv": 9,
                "igv": 0,
                "total": 100.00,
                "anticipo_regularizacion": False
            }]
        }

        headers = {
            'Authorization': f'Token token="{api_token}"',
            'Content-Type': 'application/json'
        }

        print("🔍 PROBANDO DIFERENTES ENDPOINTS...")
        print("-" * 80)
        print()

        for i, endpoint in enumerate(endpoints, 1):
            url = f"{base_url}{endpoint}" if endpoint else base_url

            print(f"[{i}/{len(endpoints)}] {url}")

            try:
                # Probar con POST
                response = requests.post(url, json=test_data, headers=headers, timeout=10)
                status = response.status_code

                print(f"    POST → Status: {status}", end=" ")

                if status == 404:
                    print("❌ No encontrado")
                elif status in [200, 201]:
                    print("✅ ¡ÉXITO!")
                    try:
                        data = response.json()
                        print(f"    Respuesta: {data}")
                        print()
                        print("=" * 80)
                        print(f"🎯 ENDPOINT CORRECTO ENCONTRADO: {url}")
                        print("=" * 80)
                        return url
                    except:
                        print(f"    Respuesta: {response.text[:100]}")
                elif status == 400:
                    print("⚠️  Bad Request (endpoint existe!)")
                    try:
                        data = response.json()
                        print(f"    Error: {data}")
                    except:
                        print(f"    Respuesta: {response.text[:100]}")
                elif status == 401:
                    print("⚠️  No autorizado (endpoint existe!)")
                elif status == 405:
                    print("⚠️  Método no permitido (prueba GET)")
                    # Probar con GET
                    try:
                        response_get = requests.get(url, headers=headers, timeout=5)
                        print(f"    GET → Status: {response_get.status_code}")
                    except:
                        pass
                else:
                    print(f"⚠️  Código {status}")

            except requests.exceptions.Timeout:
                print("    ⏱️  Timeout")
            except requests.exceptions.ConnectionError:
                print("    ❌ Error de conexión")
            except Exception as e:
                print(f"    ❌ Error: {e}")

            print()

        print("=" * 80)
        print("❌ NO SE ENCONTRÓ UN ENDPOINT QUE FUNCIONE")
        print("=" * 80)
        print()
        print("📞 SIGUIENTE PASO:")
        print("-" * 80)
        print("Contacta a soporte de NubeFact:")
        print()
        print("Email: soporte@nubefact.com")
        print()
        print("Mensaje sugerido:")
        print("-" * 40)
        print("Hola,")
        print()
        print("Estoy integrando mi sistema con su API pero obtengo error 404.")
        print()
        print("Mis credenciales son:")
        print(f"- RUTA: {base_url}")
        print(f"- TOKEN: {api_token[:20]}...{api_token[-20:]}")
        print()
        print("He probado estos endpoints sin éxito:")
        for ep in endpoints:
            print(f"  - {base_url}{ep}")
        print()
        print("¿Cuál es el endpoint correcto para generar comprobantes?")
        print("¿Tiene algún manual actualizado de integración?")
        print()
        print("Gracias,")
        print("-" * 40)


if __name__ == '__main__':
    find_endpoint()
