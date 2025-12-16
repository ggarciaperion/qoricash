#!/usr/bin/env python
"""
Script para verificar la configuración de NubeFact
Ejecutar: python check_nubefact_config.py
"""
from run import app

def check_nubefact_config():
    """Verificar configuración de NubeFact"""
    with app.app_context():
        try:
            print("=" * 60)
            print("VERIFICANDO CONFIGURACIÓN DE NUBEFACT")
            print("=" * 60)

            # Importar servicio
            from app.services.invoice_service import InvoiceService

            # Verificar configuración
            enabled = InvoiceService.is_enabled()
            api_url = app.config.get('NUBEFACT_API_URL')
            token = app.config.get('NUBEFACT_TOKEN')
            company_ruc = app.config.get('COMPANY_RUC')
            company_name = app.config.get('COMPANY_NAME')

            print(f"\n✓ NUBEFACT_ENABLED: {enabled}")
            print(f"✓ NUBEFACT_API_URL: {api_url}")
            print(f"✓ NUBEFACT_TOKEN: {'Configurado' if token else 'NO CONFIGURADO'}")
            print(f"  Token (primeros 20 chars): {token[:20] if token else 'N/A'}...")
            print(f"✓ COMPANY_RUC: {company_ruc}")
            print(f"✓ COMPANY_NAME: {company_name}")

            print("\n" + "=" * 60)

            if enabled and api_url and token:
                print("✅ CONFIGURACIÓN CORRECTA - Facturación habilitada")
            else:
                print("❌ CONFIGURACIÓN INCOMPLETA")
                if not enabled:
                    print("  - NUBEFACT_ENABLED debe ser 'True' (con T mayúscula)")
                if not api_url:
                    print("  - NUBEFACT_API_URL no configurado")
                if not token:
                    print("  - NUBEFACT_TOKEN no configurado")

            print("=" * 60)
            return enabled and api_url and token

        except Exception as e:
            print(f"\n❌ Error al verificar configuración: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    check_nubefact_config()
