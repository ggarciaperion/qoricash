"""
Script para agregar columnas de referidos directamente a la base de datos
Este script se ejecuta independientemente de las migraciones de Alembic
"""
import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.extensions import db
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def add_referral_columns():
    """Agregar columnas de referidos directamente con SQL"""

    app = create_app()

    with app.app_context():
        try:
            logger.info('🚀 Iniciando agregado de columnas de referidos...')

            # Agregar columna referral_code
            try:
                db.session.execute(db.text('ALTER TABLE clients ADD COLUMN referral_code VARCHAR(6);'))
                logger.info('✅ Columna referral_code agregada')
            except Exception as e:
                if 'already exists' in str(e).lower() or 'duplicate column' in str(e).lower():
                    logger.info('ℹ️  Columna referral_code ya existe')
                else:
                    raise

            # Agregar columna used_referral_code
            try:
                db.session.execute(db.text('ALTER TABLE clients ADD COLUMN used_referral_code VARCHAR(6);'))
                logger.info('✅ Columna used_referral_code agregada')
            except Exception as e:
                if 'already exists' in str(e).lower() or 'duplicate column' in str(e).lower():
                    logger.info('ℹ️  Columna used_referral_code ya existe')
                else:
                    raise

            # Agregar columna referred_by
            try:
                db.session.execute(db.text('ALTER TABLE clients ADD COLUMN referred_by INTEGER;'))
                logger.info('✅ Columna referred_by agregada')
            except Exception as e:
                if 'already exists' in str(e).lower() or 'duplicate column' in str(e).lower():
                    logger.info('ℹ️  Columna referred_by ya existe')
                else:
                    raise

            # Crear índice único en referral_code
            try:
                db.session.execute(db.text('CREATE UNIQUE INDEX ix_clients_referral_code ON clients (referral_code);'))
                logger.info('✅ Índice único ix_clients_referral_code creado')
            except Exception as e:
                if 'already exists' in str(e).lower():
                    logger.info('ℹ️  Índice ix_clients_referral_code ya existe')
                else:
                    raise

            # Crear foreign key constraint
            try:
                db.session.execute(db.text('ALTER TABLE clients ADD CONSTRAINT fk_clients_referred_by FOREIGN KEY (referred_by) REFERENCES clients(id);'))
                logger.info('✅ Foreign key fk_clients_referred_by creada')
            except Exception as e:
                if 'already exists' in str(e).lower():
                    logger.info('ℹ️  Foreign key fk_clients_referred_by ya existe')
                else:
                    raise

            # Commit todos los cambios
            db.session.commit()

            logger.info('')
            logger.info('=' * 60)
            logger.info('✅ ÉXITO: Columnas de referidos agregadas correctamente')
            logger.info('=' * 60)

        except Exception as e:
            db.session.rollback()
            logger.error(f'❌ Error agregando columnas: {str(e)}')
            raise


if __name__ == '__main__':
    logger.info('🔧 Ejecutando script de corrección de columnas de referidos...')
    add_referral_columns()
    logger.info('🎉 Proceso completado')
