"""
Script de inicialización para sistema de Compliance
Ejecutar después de la migración de BD
"""
import os
import sys

# Agregar el directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db
from app.models.compliance import RiskLevel
from app.utils.formatters import now_peru

def init_compliance_data():
    """Inicializar datos de compliance"""
    app = create_app()

    with app.app_context():
        print("Iniciando configuración de Compliance...")

        # Verificar si ya existen niveles de riesgo
        existing_levels = RiskLevel.query.count()

        if existing_levels > 0:
            print(f"✓ Niveles de riesgo ya inicializados ({existing_levels} registros)")
            return

        # Crear niveles de riesgo
        risk_levels = [
            RiskLevel(
                name='Bajo',
                description='Riesgo bajo - Cliente regular sin flags de alerta',
                color='green',
                score_min=0,
                score_max=25,
                created_at=now_peru()
            ),
            RiskLevel(
                name='Medio',
                description='Riesgo medio - Requiere monitoreo regular',
                color='yellow',
                score_min=26,
                score_max=50,
                created_at=now_peru()
            ),
            RiskLevel(
                name='Alto',
                description='Riesgo alto - Requiere due diligence reforzada',
                color='orange',
                score_min=51,
                score_max=75,
                created_at=now_peru()
            ),
            RiskLevel(
                name='Crítico',
                description='Riesgo crítico - Requiere aprobación de compliance',
                color='red',
                score_min=76,
                score_max=100,
                created_at=now_peru()
            )
        ]

        try:
            for level in risk_levels:
                db.session.add(level)

            db.session.commit()
            print("✓ Niveles de riesgo creados correctamente")
            print("  - Bajo (0-25)")
            print("  - Medio (26-50)")
            print("  - Alto (51-75)")
            print("  - Crítico (76-100)")

        except Exception as e:
            db.session.rollback()
            print(f"✗ Error al crear niveles de riesgo: {str(e)}")
            raise

if __name__ == '__main__':
    init_compliance_data()
    print("\n✅ Sistema de Compliance inicializado correctamente")
