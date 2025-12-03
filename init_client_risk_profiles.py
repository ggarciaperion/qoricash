"""
Script de Inicialización de Perfiles de Riesgo
==============================================

Este script crea perfiles de riesgo para clientes existentes que no tienen uno.
Se ejecuta una sola vez después de implementar el sistema de compliance.

Uso:
    python init_client_risk_profiles.py
"""
import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app, db
from app.models.client import Client
from app.models.compliance import ClientRiskProfile, RiskLevel
from app.services.compliance_service import ComplianceService
from sqlalchemy import text
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def init_risk_profiles():
    """
    Inicializar perfiles de riesgo para todos los clientes que no tienen uno
    """
    app = create_app()

    with app.app_context():
        logger.info("=" * 60)
        logger.info("INICIANDO CREACIÓN DE PERFILES DE RIESGO")
        logger.info("=" * 60)

        # Obtener nivel de riesgo "Bajo" por defecto
        default_risk_level = RiskLevel.query.filter_by(name='Bajo').first()
        if not default_risk_level:
            logger.error("No se encontró el nivel de riesgo 'Bajo'. Ejecuta las migraciones primero.")
            return

        # Obtener todos los clientes
        all_clients = Client.query.all()
        logger.info(f"Total de clientes en sistema: {len(all_clients)}")

        # Filtrar clientes sin perfil de riesgo
        clients_without_profile = []
        for client in all_clients:
            if not ClientRiskProfile.query.filter_by(client_id=client.id).first():
                clients_without_profile.append(client)

        logger.info(f"Clientes sin perfil de riesgo: {len(clients_without_profile)}")

        if not clients_without_profile:
            logger.info("✓ Todos los clientes ya tienen perfil de riesgo")
            return

        # Crear perfiles para cada cliente
        created_count = 0
        error_count = 0

        for client in clients_without_profile:
            try:
                logger.info(f"\nProcesando cliente: {client.company_name} (DNI/RUC: {client.dni_ruc})")

                # Calcular score de riesgo basado en operaciones históricas
                risk_score = ComplianceService.calculate_client_risk_score(client.id)
                logger.info(f"  - Score calculado: {risk_score}")

                # Determinar nivel de riesgo según el score
                risk_level = RiskLevel.query.filter(
                    RiskLevel.score_min <= risk_score,
                    RiskLevel.score_max >= risk_score
                ).first()

                if not risk_level:
                    risk_level = default_risk_level

                logger.info(f"  - Nivel asignado: {risk_level.name}")

                # Determinar nivel de debida diligencia
                if risk_score >= 76:
                    due_diligence_level = 'Reforzada'
                elif risk_score >= 51:
                    due_diligence_level = 'Ampliada'
                else:
                    due_diligence_level = 'Simplificada'

                logger.info(f"  - Due diligence: {due_diligence_level}")

                # Crear perfil de riesgo
                profile = ClientRiskProfile(
                    client_id=client.id,
                    risk_level_id=risk_level.id,
                    risk_score=risk_score,
                    due_diligence_level=due_diligence_level,
                    pep_status=client.is_pep if hasattr(client, 'is_pep') else False,
                    in_restrictive_lists=client.in_restrictive_lists if hasattr(client, 'in_restrictive_lists') else False,
                    has_legal_issues=client.has_legal_issues if hasattr(client, 'has_legal_issues') else False,
                    kyc_status='Pendiente',
                    kyc_valid_until=None,
                    notes=f'Perfil creado automáticamente por script de inicialización. Score: {risk_score}'
                )

                db.session.add(profile)
                db.session.flush()

                logger.info(f"  ✓ Perfil creado exitosamente (ID: {profile.id})")
                created_count += 1

            except Exception as e:
                logger.error(f"  ✗ Error procesando cliente {client.id}: {str(e)}")
                error_count += 1
                db.session.rollback()
                continue

        # Commit final
        try:
            db.session.commit()
            logger.info("\n" + "=" * 60)
            logger.info("RESUMEN DE EJECUCIÓN")
            logger.info("=" * 60)
            logger.info(f"✓ Perfiles creados: {created_count}")
            if error_count > 0:
                logger.warning(f"✗ Errores: {error_count}")
            logger.info("✓ Script completado exitosamente")

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error al hacer commit: {str(e)}")


def verify_risk_levels():
    """
    Verificar que existan los niveles de riesgo necesarios
    """
    app = create_app()

    with app.app_context():
        logger.info("\nVerificando niveles de riesgo en base de datos...")

        risk_levels = RiskLevel.query.all()

        if not risk_levels:
            logger.error("✗ No hay niveles de riesgo en la base de datos")
            logger.error("  Ejecuta primero: flask db upgrade")
            return False

        logger.info(f"✓ Niveles de riesgo encontrados: {len(risk_levels)}")
        for level in risk_levels:
            logger.info(f"  - {level.name}: {level.score_min}-{level.score_max} ({level.color})")

        return True


if __name__ == '__main__':
    logger.info("Script de Inicialización de Perfiles de Riesgo")
    logger.info("=" * 60)

    # Verificar niveles de riesgo
    if not verify_risk_levels():
        sys.exit(1)

    # Inicializar perfiles
    init_risk_profiles()
