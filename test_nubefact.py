"""
Script para probar la conexión y generación de facturas con NubeFact
"""
import os
import sys
import requests
from datetime import datetime

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app
from app.models.operation import Operation
from app.services.invoice_service import InvoiceService

def test_nubefact_connection():
    """Probar conexión con NubeFact API"""
    app = create_app()

    with app.app_context():
        print("=" * 80)
        print("PRUEBA DE CONEXIÓN CON NUBEFACT")
        print("=" * 80)
        print()

        # Verificar configuración
        api_url = app.config.get('NUBEFACT_API_URL')
        api_token = app.config.get('NUBEFACT_TOKEN')
        nubefact_enabled = app.config.get('NUBEFACT_ENABLED')
        ruc = app.config.get('NUBEFACT_RUC')

        print("📋 CONFIGURACIÓN:")
        print("-" * 80)
        print(f"NUBEFACT_ENABLED: {nubefact_enabled}")
        print(f"NUBEFACT_API_URL: {api_url}")
        print(f"NUBEFACT_TOKEN: {api_token[:10]}...{api_token[-10:] if api_token else 'NO CONFIGURADO'}")
        print(f"NUBEFACT_RUC: {ruc}")
        print()

        if not nubefact_enabled:
            print("❌ NUBEFACT_ENABLED está en False")
            print("   Cambia la variable de entorno a True")
            return

        if not api_token:
            print("❌ NUBEFACT_TOKEN no está configurado")
            return

        # Preparar datos de prueba
        print("🧪 PROBANDO CONEXIÓN CON NUBEFACT...")
        print("-" * 80)

        # Datos mínimos de prueba
        test_data = {
            "operacion": "generar_comprobante",
            "tipo_de_comprobante": "03",  # Boleta
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
                "tipo_de_igv": 9,  # Exonerado
                "igv": 0,
                "total": 100.00,
                "anticipo_regularizacion": False
            }]
        }

        headers = {
            'Authorization': f'Token token="{api_token}"',
            'Content-Type': 'application/json'
        }

        print(f"Enviando solicitud a: {api_url}/documento/generar")
        print()

        try:
            response = requests.post(
                f'{api_url}/documento/generar',
                json=test_data,
                headers=headers,
                timeout=30
            )

            print(f"📡 RESPUESTA DE NUBEFACT:")
            print("-" * 80)
            print(f"Status Code: {response.status_code}")
            print()

            try:
                response_data = response.json()
                print("Respuesta JSON:")
                import json
                print(json.dumps(response_data, indent=2, ensure_ascii=False))
                print()

                if response.status_code in [200, 201]:
                    print("✅ CONEXIÓN EXITOSA CON NUBEFACT")
                    print()

                    if response_data.get('aceptada_por_sunat'):
                        print("✅ COMPROBANTE ACEPTADO POR SUNAT (modo demo)")
                        print(f"   Serie-Número: {response_data.get('serie')}-{response_data.get('numero')}")
                        print(f"   PDF: {response_data.get('enlace_del_pdf')}")
                        print(f"   XML: {response_data.get('enlace_del_xml')}")
                    else:
                        print("⚠️  COMPROBANTE RECHAZADO POR SUNAT")
                        print(f"   Razón: {response_data.get('sunat_description')}")
                else:
                    print("❌ ERROR EN LA RESPUESTA DE NUBEFACT")
                    if 'errors' in response_data:
                        print(f"   Error: {response_data['errors']}")

            except Exception as e:
                print(f"❌ Error al parsear respuesta JSON: {e}")
                print(f"Respuesta cruda: {response.text}")

        except requests.exceptions.Timeout:
            print("❌ TIMEOUT: No se pudo conectar con NubeFact (30 segundos)")
        except requests.exceptions.ConnectionError:
            print("❌ ERROR DE CONEXIÓN: No se pudo alcanzar el servidor de NubeFact")
        except Exception as e:
            print(f"❌ ERROR INESPERADO: {e}")

        print()
        print("=" * 80)


def test_generate_invoice_for_operation():
    """Probar generar factura para una operación real"""
    app = create_app()

    with app.app_context():
        print()
        print("=" * 80)
        print("PRUEBA DE GENERACIÓN DE FACTURA PARA OPERACIÓN REAL")
        print("=" * 80)
        print()

        # Buscar una operación completada
        completed_op = Operation.query.filter_by(status='Completada').order_by(Operation.completed_at.desc()).first()

        if not completed_op:
            print("⚠️  NO HAY OPERACIONES COMPLETADAS PARA PROBAR")
            return

        print(f"📝 OPERACIÓN SELECCIONADA:")
        print("-" * 80)
        print(f"ID: {completed_op.operation_id}")
        print(f"Cliente: {completed_op.client.full_name if completed_op.client else 'N/A'}")
        print(f"Monto USD: {completed_op.amount_usd}")
        print(f"Monto PEN: {completed_op.amount_pen}")
        print(f"Tipo: {completed_op.operation_type}")
        print()

        # Verificar si ya tiene factura
        from app.models.invoice import Invoice
        existing_invoice = Invoice.query.filter_by(operation_id=completed_op.id).first()

        if existing_invoice:
            print(f"⚠️  ESTA OPERACIÓN YA TIENE UNA FACTURA:")
            print(f"   Número: {existing_invoice.invoice_number}")
            print(f"   Estado: {existing_invoice.status}")
            print(f"   Fecha: {existing_invoice.created_at}")
            print()
            print("💡 Para probar, selecciona una operación sin factura o elimina la factura existente")
            return

        # Intentar generar factura
        print("🧪 GENERANDO FACTURA...")
        print("-" * 80)

        success, message, invoice = InvoiceService.generate_invoice_for_operation(completed_op.id)

        if success and invoice:
            print("✅ FACTURA GENERADA EXITOSAMENTE")
            print()
            print(f"📄 DATOS DE LA FACTURA:")
            print(f"   Número: {invoice.invoice_number}")
            print(f"   Tipo: {invoice.invoice_type}")
            print(f"   Cliente: {invoice.cliente_denominacion}")
            print(f"   Monto: {invoice.moneda} {float(invoice.monto_total):.2f}")
            print(f"   Estado: {invoice.status}")
            print()
            if invoice.nubefact_enlace_pdf:
                print(f"   📥 PDF: {invoice.nubefact_enlace_pdf}")
            if invoice.nubefact_enlace_xml:
                print(f"   📥 XML: {invoice.nubefact_enlace_xml}")
        else:
            print(f"❌ ERROR AL GENERAR FACTURA:")
            print(f"   {message}")

        print()
        print("=" * 80)


if __name__ == '__main__':
    import sys

    print()
    print("🔧 HERRAMIENTA DE DIAGNÓSTICO DE NUBEFACT")
    print()

    # Prueba 1: Conexión con NubeFact
    test_nubefact_connection()

    print()
    print()

    # Preguntar si desea probar con una operación real
    if len(sys.argv) > 1 and sys.argv[1] == '--test-operation':
        test_generate_invoice_for_operation()
    else:
        print("💡 Para probar con una operación real, ejecuta:")
        print("   python test_nubefact.py --test-operation")
        print()
