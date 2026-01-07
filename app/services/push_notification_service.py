"""
Servicio para enviar Push Notifications usando Expo Push Notifications

Expo Push Notifications permite enviar notificaciones a dispositivos móviles
incluso cuando la app está cerrada o en segundo plano.
"""
import logging
import requests
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# URL del API de Expo Push Notifications
EXPO_PUSH_API_URL = 'https://exp.host/--/api/v2/push/send'


class PushNotificationService:
    """Servicio para enviar notificaciones push vía Expo"""

    @staticmethod
    def is_valid_expo_token(token: str) -> bool:
        """
        Verificar si un token es válido de Expo

        Args:
            token: Token a verificar

        Returns:
            bool: True si es válido
        """
        if not token:
            return False

        # Los tokens de Expo comienzan con "ExponentPushToken[" o "ExpoPushToken["
        return token.startswith('ExponentPushToken[') or token.startswith('ExpoPushToken[')

    @staticmethod
    def send_push_notification(
        token: str,
        title: str,
        body: str,
        data: Dict[str, Any] = None,
        sound: str = 'default',
        priority: str = 'high'
    ) -> Dict[str, Any]:
        """
        Enviar notificación push a un dispositivo específico

        Args:
            token: Token de Expo Push del dispositivo
            title: Título de la notificación
            body: Contenido de la notificación
            data: Datos adicionales (opcional)
            sound: Sonido ('default', 'none', o nombre de archivo)
            priority: Prioridad ('default', 'normal', 'high')

        Returns:
            Dict con resultado del envío
        """
        try:
            # Validar token
            if not PushNotificationService.is_valid_expo_token(token):
                logger.warning(f"⚠️ Token inválido de Expo: {token[:20]}...")
                return {
                    'success': False,
                    'error': 'Token inválido de Expo'
                }

            # Preparar mensaje
            message = {
                'to': token,
                'sound': sound,
                'title': title,
                'body': body,
                'priority': priority,
                'data': data or {},
            }

            logger.info(f"📤 [PUSH] Enviando notificación push:")
            logger.info(f"   - Token: {token[:20]}...")
            logger.info(f"   - Título: {title}")
            logger.info(f"   - Cuerpo: {body}")

            # Enviar a API de Expo
            response = requests.post(
                EXPO_PUSH_API_URL,
                json=message,
                headers={
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                },
                timeout=10
            )

            response_data = response.json()

            logger.info(f"📥 [PUSH] Respuesta de Expo API: {response_data}")

            # Verificar respuesta
            if response.status_code == 200 and response_data.get('data'):
                ticket = response_data['data'][0]

                if ticket.get('status') == 'ok':
                    logger.info(f"✅ [PUSH] Notificación enviada exitosamente")
                    logger.info(f"   - Ticket ID: {ticket.get('id')}")
                    return {
                        'success': True,
                        'ticket_id': ticket.get('id')
                    }
                else:
                    error_message = ticket.get('message', 'Error desconocido')
                    error_details = ticket.get('details', {})
                    logger.error(f"❌ [PUSH] Error en ticket: {error_message}")
                    logger.error(f"   - Detalles: {error_details}")
                    return {
                        'success': False,
                        'error': error_message,
                        'details': error_details
                    }
            else:
                logger.error(f"❌ [PUSH] Error HTTP {response.status_code}: {response_data}")
                return {
                    'success': False,
                    'error': f'Error HTTP {response.status_code}',
                    'response': response_data
                }

        except requests.exceptions.Timeout:
            logger.error("❌ [PUSH] Timeout al conectar con Expo API")
            return {
                'success': False,
                'error': 'Timeout al conectar con Expo'
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ [PUSH] Error de conexión con Expo API: {str(e)}")
            return {
                'success': False,
                'error': f'Error de conexión: {str(e)}'
            }
        except Exception as e:
            logger.error(f"❌ [PUSH] Error inesperado: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'error': f'Error inesperado: {str(e)}'
            }

    @staticmethod
    def send_push_to_multiple(
        tokens: List[str],
        title: str,
        body: str,
        data: Dict[str, Any] = None,
        sound: str = 'default',
        priority: str = 'high'
    ) -> Dict[str, Any]:
        """
        Enviar notificación push a múltiples dispositivos

        Args:
            tokens: Lista de tokens de Expo Push
            title: Título de la notificación
            body: Contenido de la notificación
            data: Datos adicionales (opcional)
            sound: Sonido ('default', 'none', o nombre de archivo)
            priority: Prioridad ('default', 'normal', 'high')

        Returns:
            Dict con resultados del envío
        """
        try:
            # Filtrar tokens válidos
            valid_tokens = [t for t in tokens if PushNotificationService.is_valid_expo_token(t)]

            if not valid_tokens:
                logger.warning("⚠️ No hay tokens válidos para enviar")
                return {
                    'success': False,
                    'error': 'No hay tokens válidos'
                }

            # Preparar mensajes
            messages = []
            for token in valid_tokens:
                messages.append({
                    'to': token,
                    'sound': sound,
                    'title': title,
                    'body': body,
                    'priority': priority,
                    'data': data or {},
                })

            logger.info(f"📤 [PUSH] Enviando {len(messages)} notificaciones push")

            # Enviar a API de Expo
            response = requests.post(
                EXPO_PUSH_API_URL,
                json=messages,
                headers={
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                },
                timeout=10
            )

            response_data = response.json()

            logger.info(f"📥 [PUSH] Respuesta de Expo API para {len(messages)} mensajes")

            # Contar éxitos y errores
            success_count = 0
            error_count = 0

            if response.status_code == 200 and response_data.get('data'):
                for ticket in response_data['data']:
                    if ticket.get('status') == 'ok':
                        success_count += 1
                    else:
                        error_count += 1
                        logger.error(f"❌ [PUSH] Error en ticket: {ticket.get('message')}")

            logger.info(f"✅ [PUSH] Enviadas: {success_count} exitosas, {error_count} fallidas")

            return {
                'success': success_count > 0,
                'sent': success_count,
                'failed': error_count,
                'total': len(messages)
            }

        except Exception as e:
            logger.error(f"❌ [PUSH] Error al enviar notificaciones múltiples: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'error': f'Error: {str(e)}'
            }

    @staticmethod
    def send_operation_expired_push(client):
        """
        Enviar notificación push de operación expirada a un cliente

        Args:
            client: Objeto Client con push_notification_token

        Returns:
            Dict con resultado del envío
        """
        try:
            if not client.push_notification_token:
                logger.warning(f"⚠️ Cliente {client.dni} no tiene token de push")
                return {
                    'success': False,
                    'error': 'Cliente sin token de push'
                }

            # Enviar notificación
            return PushNotificationService.send_push_notification(
                token=client.push_notification_token,
                title='⏱️ Operación Expirada',
                body='Tu operación ha expirado por falta de comprobante. Puedes crear una nueva operación.',
                data={
                    'type': 'operation_expired',
                    'client_dni': client.dni,
                },
                sound='default',
                priority='high'
            )

        except Exception as e:
            logger.error(f"❌ [PUSH] Error al enviar push de operación expirada: {str(e)}")
            return {
                'success': False,
                'error': f'Error: {str(e)}'
            }
