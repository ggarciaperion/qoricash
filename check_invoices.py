"""
Script de diagnóstico para verificar facturas generadas
"""
import os
import sys

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app
from app.models.invoice import Invoice
from app.models.operation import Operation
from app.extensions import db

def check_invoices():
    """Verificar facturas en la base de datos"""
    app = create_app()

    with app.app_context():
        print("=" * 80)
        print("DIAGNÓSTICO DE FACTURAS ELECTRÓNICAS - QORICASH")
        print("=" * 80)
        print()

        # Verificar configuración
        print("📋 CONFIGURACIÓN DE NUBEFACT:")
        print("-" * 80)
        print(f"NUBEFACT_ENABLED: {app.config.get('NUBEFACT_ENABLED')}")
        print(f"NUBEFACT_API_URL: {app.config.get('NUBEFACT_API_URL')}")
        print(f"NUBEFACT_TOKEN configurado: {bool(app.config.get('NUBEFACT_TOKEN'))}")
        print(f"NUBEFACT_RUC: {app.config.get('NUBEFACT_RUC')}")
        print(f"COMPANY_RUC: {app.config.get('COMPANY_RUC')}")
        print(f"COMPANY_NAME: {app.config.get('COMPANY_NAME')}")
        print()

        # Contar facturas
        total_invoices = Invoice.query.count()
        print(f"📊 TOTAL DE FACTURAS EN BASE DE DATOS: {total_invoices}")
        print()

        if total_invoices == 0:
            print("⚠️  NO HAY FACTURAS EN LA BASE DE DATOS")
            print()
            print("Posibles causas:")
            print("1. No se han completado operaciones desde que se habilitó la facturación")
            print("2. Hay un error al generar facturas que no se está registrando")
            print("3. La tabla de facturas no se migró correctamente")
            print()

            # Verificar operaciones completadas
            completed_ops = Operation.query.filter_by(status='Completada').count()
            print(f"📈 OPERACIONES COMPLETADAS: {completed_ops}")

            if completed_ops > 0:
                print()
                print("⚠️  HAY OPERACIONES COMPLETADAS PERO SIN FACTURAS")
                print("Esto indica que el proceso de facturación NO se está ejecutando correctamente")
                print()

                # Mostrar últimas 5 operaciones completadas
                last_completed = Operation.query.filter_by(status='Completada').order_by(Operation.completed_at.desc()).limit(5).all()
                print("📝 ÚLTIMAS 5 OPERACIONES COMPLETADAS (sin factura):")
                print("-" * 80)
                for op in last_completed:
                    print(f"  • {op.operation_id} - Cliente: {op.client.full_name if op.client else 'N/A'} - "
                          f"Completada: {op.completed_at.strftime('%Y-%m-%d %H:%M') if op.completed_at else 'N/A'}")
                print()
        else:
            # Mostrar estadísticas de facturas
            print(f"✅ SE ENCONTRARON {total_invoices} FACTURAS")
            print()

            # Por estado
            print("📊 FACTURAS POR ESTADO:")
            print("-" * 80)
            estados = db.session.query(Invoice.status, db.func.count(Invoice.id)).group_by(Invoice.status).all()
            for estado, count in estados:
                print(f"  • {estado}: {count}")
            print()

            # Por tipo
            print("📊 FACTURAS POR TIPO:")
            print("-" * 80)
            tipos = db.session.query(Invoice.invoice_type, db.func.count(Invoice.id)).group_by(Invoice.invoice_type).all()
            for tipo, count in tipos:
                print(f"  • {tipo}: {count}")
            print()

            # Últimas 10 facturas
            print("📝 ÚLTIMAS 10 FACTURAS GENERADAS:")
            print("-" * 80)
            last_invoices = Invoice.query.order_by(Invoice.created_at.desc()).limit(10).all()
            for inv in last_invoices:
                status_icon = "✅" if inv.status == "Aceptado" else "❌" if inv.status == "Error" else "⏳"
                print(f"  {status_icon} {inv.invoice_number or 'SIN NÚMERO'} - "
                      f"Cliente: {inv.cliente_denominacion} - "
                      f"Monto: {inv.moneda} {float(inv.monto_total):.2f} - "
                      f"Estado: {inv.status} - "
                      f"Fecha: {inv.created_at.strftime('%Y-%m-%d %H:%M')}")

                # Mostrar error si existe
                if inv.error_message:
                    print(f"    ⚠️  ERROR: {inv.error_message}")

                # Mostrar PDFs
                if inv.nubefact_enlace_pdf:
                    print(f"    📄 PDF: {inv.nubefact_enlace_pdf}")
                if inv.nubefact_enlace_xml:
                    print(f"    📄 XML: {inv.nubefact_enlace_xml}")
                print()

            # Facturas con error
            error_invoices = Invoice.query.filter_by(status='Error').all()
            if error_invoices:
                print()
                print(f"❌ FACTURAS CON ERROR ({len(error_invoices)}):")
                print("-" * 80)
                for inv in error_invoices:
                    print(f"  • Operación: {inv.operation.operation_id if inv.operation else 'N/A'}")
                    print(f"    Cliente: {inv.cliente_denominacion}")
                    print(f"    Error: {inv.error_message}")
                    print(f"    Fecha: {inv.created_at.strftime('%Y-%m-%d %H:%M')}")
                    print()

        # Verificar operaciones completadas sin factura
        print()
        print("🔍 VERIFICANDO OPERACIONES COMPLETADAS SIN FACTURA:")
        print("-" * 80)

        completed_ops = Operation.query.filter_by(status='Completada').all()
        ops_without_invoice = []

        for op in completed_ops:
            invoices = Invoice.query.filter_by(operation_id=op.id).all()
            if not invoices:
                ops_without_invoice.append(op)

        if ops_without_invoice:
            print(f"⚠️  ENCONTRADAS {len(ops_without_invoice)} OPERACIONES COMPLETADAS SIN FACTURA:")
            print()
            for op in ops_without_invoice[:10]:  # Mostrar máximo 10
                print(f"  • {op.operation_id} - Cliente: {op.client.full_name if op.client else 'N/A'} - "
                      f"Completada: {op.completed_at.strftime('%Y-%m-%d %H:%M') if op.completed_at else 'N/A'}")

            if len(ops_without_invoice) > 10:
                print(f"  ... y {len(ops_without_invoice) - 10} más")
            print()
            print("💡 RECOMENDACIÓN: Revisa los logs de Render cuando se completó alguna de estas operaciones")
            print("   Busca mensajes que contengan '[INVOICE]' o '[OPERATION-XXX]'")
        else:
            print("✅ TODAS LAS OPERACIONES COMPLETADAS TIENEN FACTURA")

        print()
        print("=" * 80)
        print("FIN DEL DIAGNÓSTICO")
        print("=" * 80)


if __name__ == '__main__':
    check_invoices()
