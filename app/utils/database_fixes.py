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


def apply_all_fixes(db):
    """
    Aplicar todas las correcciones de base de datos necesarias
    """
    logger.info("=== Iniciando verificación y corrección de esquema de BD ===")

    # Aplicar corrección de restrictive_list_checks
    fix_restrictive_list_checks_schema(db)

    logger.info("=== Verificación de esquema completada ===")
