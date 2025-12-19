"""
Script para probar diferentes formatos de URL de NubeFact
"""
import os
import sys
import requests
from datetime import datetime

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app

def test_different_url_formats():
    """Probar diferentes formatos de URL para NubeFact"""
    app = create_app()

    with app.app_context():
        api_token = app.config.get('NUBEFACT_TOKEN')
        uuid = "931258a7-ab41-488d-aedf-b8a2a502a224"

        # Diferentes formatos de URL a probar
        url_formats = [
            f"https://api.nubefact.com/api/v1/{uuid}/documento/generar",
            f"https://api.nubefact.com/{uuid}/documento/generar",
            f"https://api.nubefact.com/api/{uuid}/documento/generar",
            "https://api.nubefact.com/documento/generar",
            "https://api.nubefact.com/api/v1/documento/generar",
        ]

        # Datos mínimos de prueba
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
            "enviar_automaticamente_a_la_sunat": True,
            "enviar_automaticamente_al_cliente": False,
            "items": [{
                "unidad_de_medida": "ZZ",
                "codigo": "001",
                "descripcion": "SERVICIO DE PRUEBA - NO VÁLIDO",
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

        print("=" * 80)
        print("PROBANDO DIFERENTES FORMATOS DE URL DE NUBEFACT")
        print("=" * 80)
        print()

        for i, url in enumerate(url_formats, 1):
            print(f"📡 PRUEBA {i}/{len(url_formats)}: {url}")
            print("-" * 80)

            try:
                response = requests.post(
                    url,
                    json=test_data,
                    headers=headers,
                    timeout=10
                )

                print(f"Status Code: {response.status_code}")

                if response.status_code == 404:
                    print("❌ 404 - Endpoint no encontrado")
                elif response.status_code in [200, 201]:
                    print("✅ ÉXITO - Endpoint correcto!")
                    try:
                        response_data = response.json()
                        print(f"Respuesta: {response_data}")

                        # Guardar la URL correcta
                        print()
                        print("=" * 80)
                        print(f"🎯 URL CORRECTA ENCONTRADA: {url}")
                        print("=" * 80)
                        return url
                    except:
                        print(f"Respuesta: {response.text[:200]}")
                elif response.status_code == 401:
                    print("⚠️  401 - Problema de autenticación (pero el endpoint existe!)")
                    print(f"    Esta podría ser la URL correcta: {url}")
                    try:
                        response_data = response.json()
                        print(f"    Respuesta: {response_data}")
                    except:
                        print(f"    Respuesta: {response.text[:200]}")
                elif response.status_code == 400:
                    print("⚠️  400 - Bad Request (el endpoint existe pero hay error en los datos)")
                    print(f"    Esta podría ser la URL correcta: {url}")
                    try:
                        response_data = response.json()
                        print(f"    Respuesta: {response_data}")
                    except:
                        print(f"    Respuesta: {response.text[:200]}")
                else:
                    print(f"⚠️  Status {response.status_code}")
                    print(f"Respuesta: {response.text[:200]}")

            except requests.exceptions.Timeout:
                print("❌ Timeout")
            except requests.exceptions.ConnectionError:
                print("❌ Error de conexión")
            except Exception as e:
                print(f"❌ Error: {e}")

            print()

        print("=" * 80)
        print("❌ NINGUNA URL FUNCIONÓ")
        print("=" * 80)
        print()
        print("💡 Recomendaciones:")
        print("1. Verifica que tu cuenta de NubeFact esté activa")
        print("2. Verifica que el TOKEN sea correcto")
        print("3. Contacta a soporte@nubefact.com para confirmar la URL correcta")
        print("4. Revisa la documentación en https://ayuda.nubefact.com")

        return None


if __name__ == '__main__':
    test_different_url_formats()
