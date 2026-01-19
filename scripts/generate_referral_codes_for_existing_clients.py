"""
Script de migración: Generar códigos de referido para clientes existentes

Este script genera códigos de referido únicos para todos los clientes
que no tienen uno asignado (clientes registrados antes de la implementación
del sistema de referidos).

Uso:
    python scripts/generate_referral_codes_for_existing_clients.py
"""
import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.extensions import db
from app.models.client import Client
from app.utils.referral import generate_referral_code
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def generate_codes_for_existing_clients():
    """Generar códigos de referido para clientes sin código"""

    app = create_app()

    with app.app_context():
        try:
            # Obtener clientes sin código de referido
            clients_without_code = Client.query.filter(
                (Client.referral_code == None) | (Client.referral_code == '')
            ).all()

            total_clients = len(clients_without_code)
            logger.info(f'📊 Encontrados {total_clients} clientes sin código de referido')

            if total_clients == 0:
                logger.info('✅ Todos los clientes ya tienen código de referido')
                return

            updated_count = 0
            failed_count = 0

            for client in clients_without_code:
                try:
                    # Generar código único
                    max_attempts = 20
                    code_generated = False

                    for attempt in range(max_attempts):
                        new_code = generate_referral_code()

                        # Verificar que sea único
                        existing = Client.query.filter_by(referral_code=new_code).first()

                        if not existing:
                            client.referral_code = new_code
                            code_generated = True
                            logger.info(f'✨ Cliente {client.dni} - {client.full_name}: {new_code}')
                            break

                    if not code_generated:
                        logger.error(f'❌ No se pudo generar código único para cliente {client.dni} después de {max_attempts} intentos')
                        failed_count += 1
                        continue

                    updated_count += 1

                    # Commit cada 50 clientes
                    if updated_count % 50 == 0:
                        db.session.commit()
                        logger.info(f'💾 Guardados {updated_count}/{total_clients} clientes')

                except Exception as e:
                    logger.error(f'❌ Error procesando cliente {client.dni}: {str(e)}')
                    failed_count += 1
                    continue

            # Commit final
            db.session.commit()

            logger.info('')
            logger.info('=' * 60)
            logger.info(f'✅ Migración completada:')
            logger.info(f'   - Total clientes procesados: {total_clients}')
            logger.info(f'   - Códigos generados exitosamente: {updated_count}')
            logger.info(f'   - Fallos: {failed_count}')
            logger.info('=' * 60)

        except Exception as e:
            db.session.rollback()
            logger.error(f'❌ Error en la migración: {str(e)}', exc_info=True)
            raise


if __name__ == '__main__':
    logger.info('🚀 Iniciando generación de códigos de referido para clientes existentes...')
    generate_codes_for_existing_clients()
    logger.info('🎉 Proceso finalizado')
