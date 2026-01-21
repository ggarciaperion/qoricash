"""
Servicio para gestionar beneficios del sistema de referidos

Este servicio maneja:
- Otorgamiento de beneficios cuando una operación se completa
- Cálculo de pips ganados
- Actualización de estadísticas del propietario del código
"""
import logging
from app.extensions import db
from app.models.client import Client
from app.models.operation import Operation
from app.utils.formatters import now_peru

logger = logging.getLogger(__name__)

# Constante: Beneficio por cada operación completada con código de referido
PIPS_PER_REFERRAL = 0.0015  # 15 pips = 0.0015 (actualizado según nuevas reglas)

# Constante: Pips necesarios para canjear por código de recompensa
PIPS_REQUIRED_FOR_REWARD = 0.0030  # 30 pips = 0.003


class ReferralService:
    """Servicio para gestionar el sistema de beneficios por referidos"""

    @staticmethod
    def _get_first_operation_status(client: Client) -> str:
        """
        Obtener el estado de la primera operación de un cliente referido.

        Esta función busca la primera operación creada por el cliente después de usar
        el código de referido y devuelve su estado actual.
        """
        try:
            # Buscar la primera operación del cliente, ordenada por fecha de creación
            first_operation = Operation.query.filter_by(
                client_id=client.id
            ).order_by(Operation.created_at.asc()).first()

            if first_operation:
                logger.debug(f"Cliente {client.dni}: Operación {first_operation.operation_id} - Estado: {first_operation.status}")
                return first_operation.status
            else:
                logger.debug(f"Cliente {client.dni}: No tiene operaciones")
                return 'Sin operación'

        except Exception as e:
            logger.error(f"Error al obtener estado de operación para cliente {client.dni}: {str(e)}", exc_info=True)
            return 'Desconocido'

    @staticmethod
    def _get_first_operation_date(client: Client) -> str:
        """
        Obtener la fecha de la primera operación de un cliente referido.

        Esta es la fecha en que el cliente usó el código de referido (fecha de creación de su primera operación).
        """
        try:
            # Buscar la primera operación del cliente
            first_operation = Operation.query.filter_by(
                client_id=client.id
            ).order_by(Operation.created_at.asc()).first()

            if first_operation and first_operation.created_at:
                logger.debug(f"Cliente {client.dni}: Primera operación creada el {first_operation.created_at}")
                return first_operation.created_at.isoformat()
            else:
                logger.debug(f"Cliente {client.dni}: No tiene operaciones con fecha")
                return None

        except Exception as e:
            logger.error(f"Error al obtener fecha de operación para cliente {client.dni}: {str(e)}", exc_info=True)
            return None

    @staticmethod
    def count_referral_use(client: Client) -> bool:
        """
        Contabilizar el uso de un código de referido cuando un cliente crea una operación

        Este método se llama al CREAR la operación, no al completarla.
        Incrementa el contador total_uses del propietario del código.

        Args:
            client: Cliente que usó el código de referido

        Returns:
            bool: True si se contabilizó correctamente, False si no aplica

        Reglas:
            - Se contabiliza al crear la primera operación con el código
            - No importa si la operación se completa, cancela o anula
            - Solo se cuenta una vez por cliente (no por cada operación)
        """
        try:
            # Verificar si el cliente usó un código de referido
            if not client.used_referral_code or not client.referred_by:
                logger.debug(f"Cliente {client.dni} no usó código de referido")
                return False

            # Obtener el propietario del código (referidor)
            referrer = Client.query.get(client.referred_by)
            if not referrer:
                logger.error(f"Propietario del código no encontrado (ID: {client.referred_by})")
                return False

            # Verificar si ya se contabilizó este cliente
            # (esto evita contar múltiples veces al mismo cliente si crea varias operaciones)
            if hasattr(client, '_referral_counted') and client._referral_counted:
                logger.debug(f"Cliente {client.dni} ya fue contabilizado previamente")
                return False

            # Incrementar el contador total de usos
            if referrer.referral_total_uses is None:
                referrer.referral_total_uses = 0
            referrer.referral_total_uses += 1

            # Marcar que se contabilizó (en memoria, no en DB)
            client._referral_counted = True

            # Guardar cambios
            db.session.commit()

            logger.info(
                f"✅ Uso contabilizado: Cliente {client.dni} usó código {client.used_referral_code} "
                f"de {referrer.dni}. Total usos: {referrer.referral_total_uses}"
            )

            return True

        except Exception as e:
            logger.error(f"❌ Error al contabilizar uso de referido: {str(e)}", exc_info=True)
            db.session.rollback()
            return False

    @staticmethod
    def grant_referral_benefit(operation: Operation) -> bool:
        """
        Otorgar beneficio al propietario del código cuando una operación se completa

        Args:
            operation: Operación que cambió a estado "Completado"

        Returns:
            bool: True si se otorgó el beneficio, False si no aplica

        Reglas:
            - Solo se otorga si la operación tiene estado "Completado"
            - Solo si el cliente usó un código de referido
            - Solo si el propietario del código existe
            - El beneficio es de 15 pips (0.0015) por operación
        """
        try:
            # Verificar que la operación esté completada
            if operation.status != 'Completada':
                logger.debug(f"Operación {operation.operation_id} no está completada, no se otorga beneficio")
                return False

            # Obtener el cliente de la operación
            client = Client.query.get(operation.client_id)
            if not client:
                logger.error(f"Cliente no encontrado para operación {operation.operation_id}")
                return False

            # Verificar si el cliente usó un código de referido
            if not client.used_referral_code or not client.referred_by:
                logger.debug(f"Cliente {client.dni} no usó código de referido, no se otorga beneficio")
                return False

            # Obtener el propietario del código (referidor)
            referrer = Client.query.get(client.referred_by)
            if not referrer:
                logger.error(f"Propietario del código no encontrado (ID: {client.referred_by})")
                return False

            # Verificar si ya se otorgó beneficio por esta operación
            # (para evitar otorgar múltiples veces si la operación se actualiza)
            if hasattr(operation, '_referral_benefit_granted'):
                logger.debug(f"Beneficio ya otorgado para operación {operation.operation_id}")
                return False

            # Otorgar beneficio al propietario del código
            referrer.referral_pips_earned += PIPS_PER_REFERRAL
            referrer.referral_pips_available += PIPS_PER_REFERRAL
            referrer.referral_completed_uses += 1

            # Marcar que se otorgó el beneficio (en memoria, no en DB)
            operation._referral_benefit_granted = True

            # Guardar cambios
            db.session.commit()

            logger.info(
                f"✅ Beneficio otorgado: {PIPS_PER_REFERRAL} pips al cliente {referrer.dni} "
                f"por operación {operation.operation_id} de {client.dni}. "
                f"Total acumulado: {referrer.referral_pips_earned} pips"
            )

            return True

        except Exception as e:
            logger.error(f"❌ Error al otorgar beneficio de referido: {str(e)}", exc_info=True)
            db.session.rollback()
            return False

    @staticmethod
    def get_referral_stats(client: Client) -> dict:
        """
        Obtener estadísticas de referidos para un cliente

        Args:
            client: Cliente propietario del código

        Returns:
            dict: Estadísticas completas de referidos
        """
        try:
            # Obtener clientes referidos
            referred_clients = Client.query.filter_by(referred_by=client.id).all()

            # Obtener operaciones completadas de clientes referidos
            completed_operations = []
            for referred_client in referred_clients:
                ops = Operation.query.filter_by(
                    client_id=referred_client.id,
                    status='Completada'
                ).all()
                completed_operations.extend(ops)

            # Construir historial de usos
            referral_history = []
            for op in completed_operations:
                referred_client = Client.query.get(op.client_id)
                referral_history.append({
                    'operation_id': op.operation_id,
                    'client_name': referred_client.full_name,
                    'client_dni': referred_client.dni,
                    'operation_date': op.created_at.isoformat() if op.created_at else None,
                    'status': op.status,
                    'pips_earned': PIPS_PER_REFERRAL,
                    'operation_type': op.operation_type,
                    'amount_usd': float(op.amount_usd),
                    'amount_pen': float(op.amount_pen)
                })

            return {
                'referral_code': client.referral_code,
                'total_referred_clients': len(referred_clients),
                'total_uses': client.referral_total_uses or 0,  # Total de clientes que usaron el código
                'total_completed_operations': len(completed_operations),
                'total_pips_earned': float(client.referral_pips_earned or 0),
                'pips_available': float(client.referral_pips_available or 0),
                'completed_uses': client.referral_completed_uses or 0,
                'referral_history': sorted(
                    referral_history,
                    key=lambda x: x['operation_date'] or '',
                    reverse=True
                ),
                'referred_clients': [
                    {
                        'name': ref.full_name,
                        'dni': ref.dni,
                        'document_type': ref.document_type,
                        'created_at': ref.created_at.isoformat() if ref.created_at else None,
                        'status': ref.status,
                        'operation_status': ReferralService._get_first_operation_status(ref),
                        'operation_date': ReferralService._get_first_operation_date(ref)
                    }
                    for ref in referred_clients
                ]
            }

        except Exception as e:
            logger.error(f"❌ Error al obtener estadísticas de referidos: {str(e)}", exc_info=True)
            return {
                'referral_code': client.referral_code,
                'total_referred_clients': 0,
                'total_completed_operations': 0,
                'total_pips_earned': 0.0,
                'pips_available': 0.0,
                'completed_uses': 0,
                'referral_history': [],
                'referred_clients': []
            }

    @staticmethod
    def use_referral_pips(client: Client, pips_to_use: float) -> bool:
        """
        Usar pips de referido para obtener beneficio en tipo de cambio

        Args:
            client: Cliente que usa sus pips
            pips_to_use: Cantidad de pips a usar

        Returns:
            bool: True si se usaron correctamente, False si no hay suficientes
        """
        try:
            if pips_to_use <= 0:
                logger.warning(f"Cantidad de pips inválida: {pips_to_use}")
                return False

            if client.referral_pips_available < pips_to_use:
                logger.warning(
                    f"Cliente {client.dni} no tiene suficientes pips. "
                    f"Disponible: {client.referral_pips_available}, Solicitado: {pips_to_use}"
                )
                return False

            # Descontar pips disponibles
            client.referral_pips_available -= pips_to_use
            db.session.commit()

            logger.info(
                f"✅ Cliente {client.dni} usó {pips_to_use} pips. "
                f"Quedan disponibles: {client.referral_pips_available} pips"
            )

            return True

        except Exception as e:
            logger.error(f"❌ Error al usar pips de referido: {str(e)}", exc_info=True)
            db.session.rollback()
            return False

    @staticmethod
    def generate_reward_code(client: Client) -> tuple:
        """
        Generar un código de recompensa canjeando 30 pips

        Args:
            client: Cliente que canjea sus pips

        Returns:
            tuple: (success: bool, message: str, reward_code: RewardCode|None)

        Reglas:
            - Requiere mínimo 30 pips disponibles
            - Genera un código único de 6 caracteres
            - Descuenta 30 pips del saldo disponible
            - El código es de un solo uso y no transferible
        """
        try:
            from app.models.reward_code import RewardCode

            # Verificar que tenga suficientes pips
            if client.referral_pips_available < PIPS_REQUIRED_FOR_REWARD:
                return False, f'Necesitas al menos 30 pips. Tienes: {int(client.referral_pips_available * 10000)} pips', None

            # Generar código único
            code = RewardCode.generate_unique_code()

            # Crear el código de recompensa
            reward_code = RewardCode(
                code=code,
                client_id=client.id,
                pips_redeemed=PIPS_REQUIRED_FOR_REWARD,
                created_at=now_peru()
            )

            # Descontar pips
            client.referral_pips_available -= PIPS_REQUIRED_FOR_REWARD

            db.session.add(reward_code)
            db.session.commit()

            logger.info(
                f"✅ Código de recompensa generado: {code} para cliente {client.dni}. "
                f"Pips restantes: {client.referral_pips_available}"
            )

            return True, 'Código de recompensa generado exitosamente', reward_code

        except Exception as e:
            logger.error(f"❌ Error al generar código de recompensa: {str(e)}", exc_info=True)
            db.session.rollback()
            return False, f'Error al generar código: {str(e)}', None

    @staticmethod
    def get_client_reward_codes(client: Client) -> list:
        """
        Obtener todos los códigos de recompensa de un cliente

        Args:
            client: Cliente propietario

        Returns:
            list: Lista de códigos de recompensa
        """
        try:
            from app.models.reward_code import RewardCode

            codes = RewardCode.query.filter_by(client_id=client.id).order_by(
                RewardCode.created_at.desc()
            ).all()

            return [code.to_dict() for code in codes]

        except Exception as e:
            logger.error(f"❌ Error al obtener códigos de recompensa: {str(e)}", exc_info=True)
            return []


# Instancia global del servicio
referral_service = ReferralService()
