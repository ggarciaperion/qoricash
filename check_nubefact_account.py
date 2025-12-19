"""
Script para verificar el estado de la cuenta de NubeFact
"""
import os
import sys
import requests

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app

def check_account():
    """Verificar cuenta de NubeFact"""
    app = create_app()

    with app.app_context():
        print("=" * 80)
        print("VERIFICACIÓN DE CUENTA DE NUBEFACT")
        print("=" * 80)
        print()

        api_token = app.config.get('NUBEFACT_TOKEN')

        # URLs conocidas de NubeFact
        possible_uuids = [
            "931258a7-ab41-488d-aedf-b8a2a502a224",  # El que tienes
        ]

        print("🔍 PROBANDO CON EL UUID ORIGINAL...")
        print("-" * 80)

        uuid = possible_uuids[0]
        url = f"https://api.nubefact.com/api/v1/{uuid}/documento/generar"

        print(f"URL: {url}")
        print()

        # Datos de prueba mínimos
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
            "fecha_de_emision": "2025-01-15",
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
            "enviar_automaticamente_a_la_sunat": False,  # No enviar a SUNAT en prueba
            "enviar_automaticamente_al_cliente": False,
            "items": [{
                "unidad_de_medida": "ZZ",
                "codigo": "001",
                "descripcion": "SERVICIO DE PRUEBA - VALIDACION DE CREDENCIALES",
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

        try:
            print("📡 Enviando solicitud...")
            response = requests.post(url, json=test_data, headers=headers, timeout=30)

            print(f"Status Code: {response.status_code}")
            print()

            if response.status_code == 404:
                print("❌ ERROR 404 - ENDPOINT NO ENCONTRADO")
                print()
                print("Posibles causas:")
                print("1. ❌ El UUID en la URL es incorrecto o expiró")
                print("2. ❌ Tu cuenta de NubeFact fue desactivada")
                print("3. ❌ NubeFact cambió la estructura de su API")
                print()
                print("🔧 SOLUCIONES:")
                print("-" * 80)
                print("1. Accede a https://app.nubefact.com/login")
                print("2. Ve a: Configuración > API > Integración")
                print("3. Copia la RUTA exacta que te muestra el panel")
                print("4. Actualiza NUBEFACT_API_URL en Render con esa RUTA")
                print()
                print("O contacta a soporte@nubefact.com con estos datos:")
                print(f"   - RUC: 20615113698")
                print(f"   - UUID actual: {uuid}")
                print(f"   - Error: 404 al intentar generar comprobante")

            elif response.status_code in [200, 201]:
                print("✅ ¡ÉXITO! LA CONEXIÓN FUNCIONA")
                print()
                try:
                    data = response.json()
                    import json
                    print("Respuesta de NubeFact:")
                    print(json.dumps(data, indent=2, ensure_ascii=False))
                    print()

                    if data.get('aceptada_por_sunat'):
                        print("✅ Comprobante aceptado por SUNAT (modo demo)")
                        print(f"   Serie-Número: {data.get('serie')}-{data.get('numero')}")
                        print(f"   PDF: {data.get('enlace_del_pdf')}")
                        print()
                        print("🎯 LA URL CORRECTA ES:")
                        print(f"   {url.replace('/documento/generar', '')}")
                    else:
                        print("⚠️  Comprobante rechazado por SUNAT")
                        print(f"   Razón: {data.get('sunat_description')}")

                except Exception as e:
                    print(f"Respuesta: {response.text}")

            elif response.status_code == 401:
                print("❌ ERROR 401 - NO AUTORIZADO")
                print()
                print("El endpoint existe pero el TOKEN es incorrecto.")
                print()
                print("🔧 SOLUCIÓN:")
                print("1. Accede a https://app.nubefact.com")
                print("2. Ve a: Configuración > API")
                print("3. Regenera el TOKEN si es necesario")
                print("4. Actualiza NUBEFACT_TOKEN en Render")

            elif response.status_code == 400:
                print("⚠️  ERROR 400 - BAD REQUEST")
                print()
                print("✅ El endpoint y credenciales son correctos!")
                print("❌ Pero hay un error en el formato de los datos enviados")
                print()
                try:
                    data = response.json()
                    import json
                    print("Error de NubeFact:")
                    print(json.dumps(data, indent=2, ensure_ascii=False))
                except:
                    print(f"Respuesta: {response.text}")

            else:
                print(f"⚠️  Status Code: {response.status_code}")
                print(f"Respuesta: {response.text[:500]}")

        except requests.exceptions.Timeout:
            print("❌ TIMEOUT - No hubo respuesta en 30 segundos")
        except requests.exceptions.ConnectionError:
            print("❌ ERROR DE CONEXIÓN")
        except Exception as e:
            print(f"❌ ERROR: {e}")

        print()
        print("=" * 80)


if __name__ == '__main__':
    check_account()
