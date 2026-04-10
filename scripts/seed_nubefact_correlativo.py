"""
Script para sincronizar el correlativo de NubeFact con la BD de QoriCash.

Uso:
    python scripts/seed_nubefact_correlativo.py

Descripción:
    NubeFact ya tiene documentos emitidos (ej: B002-1 a B002-32) que no están
    registrados en la BD de QoriCash porque los intentos anteriores fallaron
    sin guardar serie/numero. Este script inserta un registro placeholder para
    que _get_next_correlative() devuelva el número correcto.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from run import app
from app.extensions import db
from app.models.invoice import Invoice
from app.models.operation import Operation

# ─────────────────────────────────────────────
# CONFIGURA AQUÍ el último número que tiene NubeFact para cada serie
# Revisa tu panel NubeFact → Comprobantes y anota el número más alto
# ─────────────────────────────────────────────
ULTIMO_NUMERO_POR_SERIE = {
    'B002': 32,   # Última boleta en NubeFact: B002-32
    # 'F001': 0,  # Descomenta si también hay facturas en NubeFact
}
# ─────────────────────────────────────────────

with app.app_context():
    # Necesitamos una operación real para cumplir el NOT NULL de operation_id
    any_operation = Operation.query.order_by(Operation.id).first()
    if not any_operation:
        print("❌ No hay operaciones en la BD. Crea al menos una operación primero.")
        sys.exit(1)

    any_client = any_operation.client

    for serie, ultimo_numero in ULTIMO_NUMERO_POR_SERIE.items():
        if ultimo_numero <= 0:
            print(f"[SKIP] {serie}: ultimo_numero={ultimo_numero}, nada que sembrar")
            continue

        # Verificar si ya existe un registro con este número o mayor
        existing = Invoice.query.filter_by(serie=serie).all()
        numeros_existentes = []
        for inv in existing:
            try:
                numeros_existentes.append(int(inv.numero))
            except (ValueError, TypeError):
                pass

        max_existente = max(numeros_existentes) if numeros_existentes else 0

        if max_existente >= ultimo_numero:
            print(f"[OK] {serie}: BD ya tiene hasta número {max_existente}, no se necesita seed")
            continue

        # Insertar placeholder con el último número conocido de NubeFact
        print(f"[SEED] {serie}: insertando placeholder numero={ultimo_numero} (BD tenía max={max_existente})")
        placeholder = Invoice(
            operation_id=any_operation.id,
            client_id=any_client.id if any_client else any_operation.client_id,
            serie=serie,
            numero=str(ultimo_numero),
            invoice_number=f"{serie}-{ultimo_numero}",
            invoice_type='Boleta' if serie.startswith('B') else 'Factura',
            emisor_ruc=os.environ.get('COMPANY_RUC', '20615113698'),
            emisor_razon_social=os.environ.get('COMPANY_NAME', 'QORICASH SAC'),
            emisor_direccion='',
            cliente_tipo_documento='DNI',
            cliente_numero_documento='00000000',
            cliente_denominacion='PLACEHOLDER - CORRELATIVO NUBEFACT',
            cliente_direccion='',
            cliente_email='',
            descripcion=f'Placeholder para sincronizar correlativo con NubeFact. Último número emitido: {serie}-{ultimo_numero}',
            monto_total=0,
            moneda='PEN',
            status='Error',
            error_message=f'Placeholder: NubeFact ya tiene hasta {serie}-{ultimo_numero}. Registro creado para sincronizar correlativo.'
        )
        db.session.add(placeholder)

    db.session.commit()
    print("\n✅ Seed completado. Próximo correlativo:")
    for serie in ULTIMO_NUMERO_POR_SERIE:
        invs = Invoice.query.filter_by(serie=serie).all()
        nums = [int(i.numero) for i in invs if i.numero and i.numero.isdigit()]
        siguiente = max(nums) + 1 if nums else 1
        print(f"   {serie} → próximo número: {siguiente}")
