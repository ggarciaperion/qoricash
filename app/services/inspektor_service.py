"""
Servicio de Integración con Inspektor (PREPARADO - NO ACTIVO)
==============================================================

Este servicio está configurado pero NO ACTIVADO hasta que se complete
el contrato con Inspektor.

Para activar:
1. Contratar servicio en https://inspektor.pe
2. Obtener API_KEY
3. Configurar variable de entorno INSPEKTOR_API_KEY en Render
4. Descomentar la llamada en app/services/client_service.py

API de Inspektor:
- Endpoint: https://api.inspektor.pe/v1
- Documentación: https://docs.inspektor.pe
- Costo aproximado: $0.45 por consulta

Funcionalidades:
- Verificación DNI en RENIEC
- Verificación RUC en SUNAT
- Validación de datos personales
- Detección PEP (Personas Expuestas Políticamente)
- Consulta listas restrictivas
"""
import os
import requests
import logging
from typing import Dict, Tuple, Optional

logger = logging.getLogger(__name__)


class InspektorService:
    """Servicio de verificación RENIEC/SUNAT vía Inspektor API"""

    # API Configuration (obtener de variables de entorno)
    API_KEY = os.getenv('INSPEKTOR_API_KEY', '')  # Configurar en Render
    BASE_URL = 'https://api.inspektor.pe/v1'
    TIMEOUT = 30  # segundos

    @staticmethod
    def is_configured() -> bool:
        """
        Verificar si el servicio está configurado

        Returns:
            bool: True si API_KEY está configurado
        """
        return bool(InspektorService.API_KEY)

    @staticmethod
    def verify_dni(dni: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        Verificar DNI en RENIEC vía Inspektor

        Args:
            dni: DNI a verificar (8 dígitos)

        Returns:
            tuple: (success: bool, message: str, data: dict|None)

        Ejemplo de respuesta exitosa:
        {
            'dni': '12345678',
            'nombres': 'JUAN',
            'apellido_paterno': 'PEREZ',
            'apellido_materno': 'GARCIA',
            'nombre_completo': 'PEREZ GARCIA JUAN',
            'fecha_nacimiento': '1990-05-15',
            'sexo': 'M',
            'estado_civil': 'SOLTERO',
            'ubigeo_reniec': '150101',
            'ubigeo_sunat': '150101',
            'direccion': 'AV EJEMPLO 123',
            'departamento': 'LIMA',
            'provincia': 'LIMA',
            'distrito': 'LIMA',
            'is_pep': False,  # Persona Expuesta Políticamente
            'in_lists': []    # Listas restrictivas
        }
        """
        # Verificar que el servicio está configurado
        if not InspektorService.is_configured():
            logger.warning("Inspektor no configurado - Retornando validación manual")
            return False, 'Servicio Inspektor no configurado. Verificación manual requerida.', None

        try:
            # Validar formato DNI
            if not dni or len(dni) != 8 or not dni.isdigit():
                return False, 'DNI debe tener 8 dígitos', None

            # Realizar petición a Inspektor
            headers = {
                'Authorization': f'Bearer {InspektorService.API_KEY}',
                'Content-Type': 'application/json'
            }

            url = f'{InspektorService.BASE_URL}/reniec/dni/{dni}'

            logger.info(f"Consultando DNI {dni} en RENIEC vía Inspektor...")

            response = requests.get(
                url,
                headers=headers,
                timeout=InspektorService.TIMEOUT
            )

            # Procesar respuesta
            if response.status_code == 200:
                data = response.json()

                if data.get('success'):
                    logger.info(f"✓ DNI {dni} verificado: {data.get('nombre_completo')}")
                    return True, 'DNI verificado exitosamente', data.get('data')
                else:
                    error_msg = data.get('message', 'DNI no encontrado en RENIEC')
                    logger.warning(f"DNI {dni} no encontrado: {error_msg}")
                    return False, error_msg, None

            elif response.status_code == 404:
                return False, 'DNI no encontrado en RENIEC', None

            elif response.status_code == 401:
                logger.error("API Key de Inspektor inválida")
                return False, 'Error de autenticación con Inspektor', None

            elif response.status_code == 429:
                logger.error("Límite de consultas excedido en Inspektor")
                return False, 'Límite de consultas excedido. Intente más tarde.', None

            else:
                logger.error(f"Error HTTP {response.status_code}: {response.text}")
                return False, f'Error al consultar RENIEC: {response.status_code}', None

        except requests.Timeout:
            logger.error(f"Timeout consultando DNI {dni}")
            return False, 'Tiempo de espera agotado. Intente nuevamente.', None

        except requests.RequestException as e:
            logger.error(f"Error de conexión con Inspektor: {str(e)}")
            return False, 'Error de conexión con servicio de verificación', None

        except Exception as e:
            logger.error(f"Error inesperado verificando DNI {dni}: {str(e)}")
            return False, f'Error interno: {str(e)}', None

    @staticmethod
    def verify_ruc(ruc: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        Verificar RUC en SUNAT vía Inspektor

        Args:
            ruc: RUC a verificar (11 dígitos)

        Returns:
            tuple: (success: bool, message: str, data: dict|None)

        Ejemplo de respuesta exitosa:
        {
            'ruc': '20123456789',
            'razon_social': 'EMPRESA EJEMPLO S.A.C.',
            'nombre_comercial': 'EJEMPLO',
            'tipo_contribuyente': 'SOCIEDAD ANONIMA CERRADA',
            'fecha_inscripcion': '2015-03-20',
            'estado': 'ACTIVO',
            'condicion': 'HABIDO',
            'direccion': 'AV EJEMPLO 456',
            'departamento': 'LIMA',
            'provincia': 'LIMA',
            'distrito': 'MIRAFLORES',
            'ubigeo': '150122',
            'actividad_economica': 'COMERCIO AL POR MAYOR',
            'ciiu': '4690',
            'representante_legal': 'JUAN PEREZ GARCIA',
            'sistema_emision': 'MANUAL',
            'sistema_contabilidad': 'COMPUTARIZADO',
            'is_good_taxpayer': False,  # Buenos contribuyentes
            'in_lists': []  # Listas restrictivas
        }
        """
        # Verificar que el servicio está configurado
        if not InspektorService.is_configured():
            logger.warning("Inspektor no configurado - Retornando validación manual")
            return False, 'Servicio Inspektor no configurado. Verificación manual requerida.', None

        try:
            # Validar formato RUC
            if not ruc or len(ruc) != 11 or not ruc.isdigit():
                return False, 'RUC debe tener 11 dígitos', None

            # Realizar petición a Inspektor
            headers = {
                'Authorization': f'Bearer {InspektorService.API_KEY}',
                'Content-Type': 'application/json'
            }

            url = f'{InspektorService.BASE_URL}/sunat/ruc/{ruc}'

            logger.info(f"Consultando RUC {ruc} en SUNAT vía Inspektor...")

            response = requests.get(
                url,
                headers=headers,
                timeout=InspektorService.TIMEOUT
            )

            # Procesar respuesta
            if response.status_code == 200:
                data = response.json()

                if data.get('success'):
                    logger.info(f"✓ RUC {ruc} verificado: {data.get('razon_social')}")
                    return True, 'RUC verificado exitosamente', data.get('data')
                else:
                    error_msg = data.get('message', 'RUC no encontrado en SUNAT')
                    logger.warning(f"RUC {ruc} no encontrado: {error_msg}")
                    return False, error_msg, None

            elif response.status_code == 404:
                return False, 'RUC no encontrado en SUNAT', None

            elif response.status_code == 401:
                logger.error("API Key de Inspektor inválida")
                return False, 'Error de autenticación con Inspektor', None

            elif response.status_code == 429:
                logger.error("Límite de consultas excedido en Inspektor")
                return False, 'Límite de consultas excedido. Intente más tarde.', None

            else:
                logger.error(f"Error HTTP {response.status_code}: {response.text}")
                return False, f'Error al consultar SUNAT: {response.status_code}', None

        except requests.Timeout:
            logger.error(f"Timeout consultando RUC {ruc}")
            return False, 'Tiempo de espera agotado. Intente nuevamente.', None

        except requests.RequestException as e:
            logger.error(f"Error de conexión con Inspektor: {str(e)}")
            return False, 'Error de conexión con servicio de verificación', None

        except Exception as e:
            logger.error(f"Error inesperado verificando RUC {ruc}: {str(e)}")
            return False, f'Error interno: {str(e)}', None

    @staticmethod
    def verify_client(dni_ruc: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        Verificar cliente (DNI o RUC) automáticamente

        Args:
            dni_ruc: DNI (8 dígitos) o RUC (11 dígitos)

        Returns:
            tuple: (success: bool, message: str, data: dict|None)
        """
        if not dni_ruc:
            return False, 'DNI/RUC requerido', None

        dni_ruc = dni_ruc.strip()

        # Determinar si es DNI o RUC por longitud
        if len(dni_ruc) == 8:
            return InspektorService.verify_dni(dni_ruc)
        elif len(dni_ruc) == 11:
            return InspektorService.verify_ruc(dni_ruc)
        else:
            return False, 'DNI debe tener 8 dígitos o RUC 11 dígitos', None


# =============================================================================
# FUNCIONES DE INTEGRACIÓN (DESCOMENTAR CUANDO SE ACTIVE INSPEKTOR)
# =============================================================================

def auto_verify_on_client_creation(client_data: Dict) -> Dict:
    """
    Verificar automáticamente datos del cliente al crearlo

    Esta función se debe llamar desde ClientService.create_client()

    Args:
        client_data: Datos del cliente a crear

    Returns:
        dict: Datos actualizados con información de RENIEC/SUNAT

    Ejemplo de uso en client_service.py:

    # DESCOMENTAR CUANDO SE ACTIVE INSPEKTOR
    # from app.services.inspektor_service import auto_verify_on_client_creation
    #
    # # Verificar automáticamente
    # if InspektorService.is_configured():
    #     client_data = auto_verify_on_client_creation(client_data)
    """
    dni_ruc = client_data.get('dni_ruc', '')

    if not InspektorService.is_configured():
        logger.info("Inspektor no configurado - Saltando verificación automática")
        return client_data

    success, message, data = InspektorService.verify_client(dni_ruc)

    if success and data:
        logger.info(f"✓ Datos verificados automáticamente para {dni_ruc}")

        # Actualizar datos del cliente con información verificada
        if len(dni_ruc) == 8:  # DNI
            client_data['verified_name'] = data.get('nombre_completo')
            client_data['is_pep'] = data.get('is_pep', False)
            client_data['address'] = data.get('direccion', client_data.get('address', ''))

        elif len(dni_ruc) == 11:  # RUC
            client_data['company_name'] = data.get('razon_social')
            client_data['legal_representative'] = data.get('representante_legal', '')
            client_data['address'] = data.get('direccion', client_data.get('address', ''))
            client_data['economic_activity'] = data.get('actividad_economica', '')

        # Verificar listas restrictivas
        in_lists = data.get('in_lists', [])
        if in_lists:
            client_data['in_restrictive_lists'] = True
            client_data['restrictive_lists_details'] = ', '.join(in_lists)
        else:
            client_data['in_restrictive_lists'] = False

        client_data['verification_status'] = 'Verificado'
        client_data['verification_date'] = data.get('verification_date')

    else:
        logger.warning(f"No se pudo verificar {dni_ruc}: {message}")
        client_data['verification_status'] = 'Pendiente'

    return client_data
