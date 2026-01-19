"""
Script para agregar columnas KYC (Know Your Customer) directamente a la base de datos
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


def add_kyc_columns():
    """Agregar columnas KYC directamente con SQL"""

    app = create_app()

    with app.app_context():
        try:
            logger.info('🚀 Iniciando agregado de columnas KYC...')

            # Agregar columna kyc_status
            try:
                db.session.execute(db.text(
                    "ALTER TABLE clients ADD COLUMN kyc_status VARCHAR(20) NOT NULL DEFAULT 'Pendiente';"
                ))
                logger.info('✅ Columna kyc_status agregada')
            except Exception as e:
                if 'already exists' in str(e).lower() or 'duplicate column' in str(e).lower():
                    logger.info('ℹ️  Columna kyc_status ya existe')
                else:
                    raise

            # Agregar columna kyc_submitted_at
            try:
                db.session.execute(db.text('ALTER TABLE clients ADD COLUMN kyc_submitted_at TIMESTAMP;'))
                logger.info('✅ Columna kyc_submitted_at agregada')
            except Exception as e:
                if 'already exists' in str(e).lower() or 'duplicate column' in str(e).lower():
                    logger.info('ℹ️  Columna kyc_submitted_at ya existe')
                else:
                    raise

            # Agregar columna kyc_approved_at
            try:
                db.session.execute(db.text('ALTER TABLE clients ADD COLUMN kyc_approved_at TIMESTAMP;'))
                logger.info('✅ Columna kyc_approved_at agregada')
            except Exception as e:
                if 'already exists' in str(e).lower() or 'duplicate column' in str(e).lower():
                    logger.info('ℹ️  Columna kyc_approved_at ya existe')
                else:
                    raise

            # Agregar columna kyc_approved_by
            try:
                db.session.execute(db.text('ALTER TABLE clients ADD COLUMN kyc_approved_by INTEGER;'))
                logger.info('✅ Columna kyc_approved_by agregada')
            except Exception as e:
                if 'already exists' in str(e).lower() or 'duplicate column' in str(e).lower():
                    logger.info('ℹ️  Columna kyc_approved_by ya existe')
                else:
                    raise

            # Agregar columna kyc_rejection_reason
            try:
                db.session.execute(db.text('ALTER TABLE clients ADD COLUMN kyc_rejection_reason VARCHAR(500);'))
                logger.info('✅ Columna kyc_rejection_reason agregada')
            except Exception as e:
                if 'already exists' in str(e).lower() or 'duplicate column' in str(e).lower():
                    logger.info('ℹ️  Columna kyc_rejection_reason ya existe')
                else:
                    raise

            # Crear foreign key constraint para kyc_approved_by
            try:
                db.session.execute(db.text(
                    'ALTER TABLE clients ADD CONSTRAINT fk_clients_kyc_approved_by FOREIGN KEY (kyc_approved_by) REFERENCES users(id);'
                ))
                logger.info('✅ Foreign key fk_clients_kyc_approved_by creada')
            except Exception as e:
                if 'already exists' in str(e).lower():
                    logger.info('ℹ️  Foreign key fk_clients_kyc_approved_by ya existe')
                else:
                    raise

            # Commit todos los cambios
            db.session.commit()

            logger.info('')
            logger.info('=' * 60)
            logger.info('✅ ÉXITO: Columnas KYC agregadas correctamente')
            logger.info('=' * 60)

        except Exception as e:
            db.session.rollback()
            logger.error(f'❌ Error agregando columnas KYC: {str(e)}')
            raise


if __name__ == '__main__':
    logger.info('🔧 Ejecutando script de agregado de columnas KYC...')
    add_kyc_columns()
    logger.info('🎉 Proceso completado')
