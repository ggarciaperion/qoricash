"""
Migración puntual: alinear kyc_status con has_complete_documents.

Caso: clientes con has_complete_documents=True pero kyc_status != 'completo'.
Esto ocurre cuando el aprobado de documentos actualizó el flag booleano
pero no persistió el campo kyc_status correctamente.

Ejecutar en Render shell:
    python fix_kyc_status_inconsistency.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

from run import app
from app.extensions import db
from app.models.client import Client

with app.app_context():
    # Clientes con docs completos pero kyc_status incorrecto
    inconsistentes = Client.query.filter(
        Client.has_complete_documents == True,
        Client.kyc_status != 'completo',
    ).all()

    if not inconsistentes:
        print("✅ No hay inconsistencias. Todos los clientes con docs completos tienen kyc_status='completo'.")
        sys.exit(0)

    print(f"🔧 Encontrados {len(inconsistentes)} clientes con inconsistencia:")
    for c in inconsistentes:
        nombre = c.full_name or c.razon_social or c.dni
        print(f"   {c.dni} | {nombre} | kyc_status actual: '{c.kyc_status}'")
        c.kyc_status = 'completo'

    db.session.commit()
    print(f"\n✅ Corregidos {len(inconsistentes)} clientes — kyc_status='completo'.")
