"""
Correcciones automáticas de base de datos
Este módulo se ejecuta al iniciar la aplicación y verifica/corrige problemas de esquema
"""
import logging
from sqlalchemy import text

logger = logging.getLogger(__name__)


def fix_restrictive_list_checks_schema(db):
    """
    Agregar columnas faltantes a la tabla restrictive_list_checks si no existen
    Esta es una solución de emergencia para asegurar que las columnas existan
    """
    try:
        with db.engine.connect() as connection:
            # Lista de columnas a agregar
            columns_to_add = [
                ("is_manual", "BOOLEAN DEFAULT FALSE"),
                ("pep_checked", "BOOLEAN DEFAULT FALSE"),
                ("pep_result", "VARCHAR(50)"),
                ("pep_details", "TEXT"),
                ("ofac_checked", "BOOLEAN DEFAULT FALSE"),
                ("ofac_result", "VARCHAR(50)"),
                ("ofac_details", "TEXT"),
                ("onu_checked", "BOOLEAN DEFAULT FALSE"),
                ("onu_result", "VARCHAR(50)"),
                ("onu_details", "TEXT"),
                ("uif_checked", "BOOLEAN DEFAULT FALSE"),
                ("uif_result", "VARCHAR(50)"),
                ("uif_details", "TEXT"),
                ("interpol_checked", "BOOLEAN DEFAULT FALSE"),
                ("interpol_result", "VARCHAR(50)"),
                ("interpol_details", "TEXT"),
                ("denuncias_checked", "BOOLEAN DEFAULT FALSE"),
                ("denuncias_result", "VARCHAR(50)"),
                ("denuncias_details", "TEXT"),
                ("otras_listas_checked", "BOOLEAN DEFAULT FALSE"),
                ("otras_listas_result", "VARCHAR(50)"),
                ("otras_listas_details", "TEXT"),
                ("observations", "TEXT"),
                ("attachments", "TEXT"),
            ]

            for column_name, column_type in columns_to_add:
                try:
                    # Intentar agregar la columna
                    sql = f"ALTER TABLE restrictive_list_checks ADD COLUMN IF NOT EXISTS {column_name} {column_type};"
                    connection.execute(text(sql))
                    connection.commit()
                    logger.info(f"Columna {column_name} verificada/agregada exitosamente")
                except Exception as e:
                    # Si falla, la columna probablemente ya existe
                    connection.rollback()
                    logger.debug(f"Columna {column_name} ya existe o error: {str(e)}")

            logger.info("Verificación de esquema de restrictive_list_checks completada")
            return True

    except Exception as e:
        logger.error(f"Error al verificar/corregir esquema de restrictive_list_checks: {str(e)}")
        return False


def fix_clients_partial_docs_schema(db):
    """
    Agregar columnas para sistema de documentos parciales a la tabla clients
    Permite que clientes operen con documentación incompleta bajo límites controlados
    """
    try:
        with db.engine.connect() as connection:
            # Lista de columnas para control de documentos parciales
            columns_to_add = [
                ("operations_without_docs_count", "INTEGER DEFAULT 0"),
                ("operations_without_docs_limit", "INTEGER"),
                ("max_amount_without_docs", "NUMERIC(15, 2)"),
                ("has_complete_documents", "BOOLEAN DEFAULT FALSE"),
                ("inactive_reason", "VARCHAR(200)"),
                ("documents_pending_since", "TIMESTAMP"),
            ]

            for column_name, column_type in columns_to_add:
                try:
                    # Intentar agregar la columna
                    sql = f"ALTER TABLE clients ADD COLUMN IF NOT EXISTS {column_name} {column_type};"
                    connection.execute(text(sql))
                    connection.commit()
                    logger.info(f"Columna clients.{column_name} verificada/agregada exitosamente")
                except Exception as e:
                    # Si falla, la columna probablemente ya existe
                    connection.rollback()
                    logger.debug(f"Columna clients.{column_name} ya existe o error: {str(e)}")

            logger.info("Verificación de esquema de documentos parciales en clients completada")
            return True

    except Exception as e:
        logger.error(f"Error al verificar/corregir esquema de documentos parciales: {str(e)}")
        return False


def fix_clients_push_notifications_schema(db):
    """
    Agregar columna push_notification_token a la tabla clients
    Para almacenar tokens de Expo Push Notifications
    """
    try:
        with db.engine.connect() as connection:
            try:
                # Agregar columna push_notification_token
                sql = "ALTER TABLE clients ADD COLUMN IF NOT EXISTS push_notification_token VARCHAR(200);"
                connection.execute(text(sql))
                connection.commit()
                logger.info("Columna clients.push_notification_token verificada/agregada exitosamente")
            except Exception as e:
                # Si falla, la columna probablemente ya existe
                connection.rollback()
                logger.debug(f"Columna clients.push_notification_token ya existe o error: {str(e)}")

            logger.info("Verificación de esquema de push notifications en clients completada")
            return True

    except Exception as e:
        logger.error(f"Error al verificar/corregir esquema de push notifications: {str(e)}")
        return False


def apply_all_fixes(db):
    """
    Aplicar todas las correcciones de base de datos necesarias
    """
    logger.info("=== Iniciando verificación y corrección de esquema de BD ===")

    # Aplicar corrección de restrictive_list_checks
    fix_restrictive_list_checks_schema(db)

    # Aplicar corrección de sistema de documentos parciales
    fix_clients_partial_docs_schema(db)

    # Aplicar corrección de push notifications
    fix_clients_push_notifications_schema(db)

    logger.info("=== Verificación de esquema completada ===")
