"""
Servicio de Compliance para AML/KYC/PLAFT - QoriCash Trading V2
"""
import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import func
from app.extensions import db
from app.models.compliance import (
    ClientRiskProfile, ComplianceRule, ComplianceAlert,
    RestrictiveListCheck, TransactionMonitoring, RiskLevel
)
from app.models.operation import Operation
from app.models.client import Client
from app.utils.formatters import now_peru

logger = logging.getLogger(__name__)


class ComplianceService:
    """Servicio principal de Compliance"""

    # Umbrales de montos (en USD)
    THRESHOLD_HIGH_AMOUNT = 10000  # Operaciones mayores a $10,000
    THRESHOLD_SUSPICIOUS_AMOUNT = 50000  # Operaciones mayores a $50,000
    THRESHOLD_CRITICAL_AMOUNT = 100000  # Operaciones mayores a $100,000

    # Umbrales de frecuencia
    THRESHOLD_DAILY_OPERATIONS = 3  # Más de 3 operaciones al día
    THRESHOLD_WEEKLY_OPERATIONS = 10  # Más de 10 operaciones a la semana
    THRESHOLD_MONTHLY_OPERATIONS = 30  # Más de 30 operaciones al mes

    @staticmethod
    def calculate_client_risk_score(client_id):
        """
        Calcular score de riesgo de un cliente (0-100)

        Factores considerados:
        - Volumen de operaciones
        - Frecuencia de operaciones
        - Montos inusuales
        - Status PEP
        - Listas restrictivas
        - Procesos judiciales
        - Antigüedad como cliente
        - Documentación KYC
        """
        from app.models.client import Client

        client = Client.query.get(client_id)
        if not client:
            return 0

        score = 0
        details = {}

        # 1. Volumen de operaciones (0-25 puntos)
        operations = Operation.query.filter_by(
            client_id=client_id,
            status='Completada'
        ).all()

        if operations:
            total_usd = sum(float(op.amount_usd) for op in operations)
            avg_amount = total_usd / len(operations)

            if avg_amount > ComplianceService.THRESHOLD_CRITICAL_AMOUNT:
                score += 25
                details['volume_risk'] = 'Crítico'
            elif avg_amount > ComplianceService.THRESHOLD_SUSPICIOUS_AMOUNT:
                score += 20
                details['volume_risk'] = 'Alto'
            elif avg_amount > ComplianceService.THRESHOLD_HIGH_AMOUNT:
                score += 10
                details['volume_risk'] = 'Medio'
            else:
                score += 5
                details['volume_risk'] = 'Bajo'
        else:
            details['volume_risk'] = 'Sin operaciones'

        # 2. Frecuencia de operaciones (0-20 puntos)
        last_30_days = now_peru() - timedelta(days=30)
        recent_ops = Operation.query.filter(
            Operation.client_id == client_id,
            Operation.created_at >= last_30_days
        ).count()

        if recent_ops > ComplianceService.THRESHOLD_MONTHLY_OPERATIONS:
            score += 20
            details['frequency_risk'] = 'Alta'
        elif recent_ops > ComplianceService.THRESHOLD_WEEKLY_OPERATIONS:
            score += 10
            details['frequency_risk'] = 'Media'
        else:
            details['frequency_risk'] = 'Baja'

        # 3. PEP (0-30 puntos)
        risk_profile = ClientRiskProfile.query.filter_by(client_id=client_id).first()
        if risk_profile and risk_profile.is_pep:
            score += 30
            details['pep_risk'] = 'Sí'
        else:
            details['pep_risk'] = 'No'

        # 4. Listas restrictivas (0-25 puntos)
        if risk_profile and risk_profile.in_restrictive_lists:
            score += 25
            details['restrictive_lists'] = 'Sí'
        else:
            last_check = RestrictiveListCheck.query.filter_by(
                client_id=client_id,
                result='Match'
            ).first()
            if last_check:
                score += 25
                details['restrictive_lists'] = 'Match encontrado'
            else:
                details['restrictive_lists'] = 'No'

        # 5. Procesos judiciales (0-15 puntos)
        if risk_profile and risk_profile.has_legal_issues:
            score += 15
            details['legal_issues'] = 'Sí'
        else:
            details['legal_issues'] = 'No'

        # 6. KYC Status (reducir puntos si está verificado) (-10 puntos)
        if risk_profile and risk_profile.kyc_status == 'Aprobado':
            score = max(0, score - 10)
            details['kyc_verified'] = 'Sí'
        else:
            details['kyc_verified'] = 'No'

        # Limitar score a 100
        score = min(100, score)

        return score, details

    @staticmethod
    def assign_risk_level(score):
        """
        Asignar nivel de riesgo según el score

        0-25: Bajo
        26-50: Medio
        51-75: Alto
        76-100: Crítico
        """
        if score <= 25:
            return 'Bajo'
        elif score <= 50:
            return 'Medio'
        elif score <= 75:
            return 'Alto'
        else:
            return 'Crítico'

    @staticmethod
    def update_client_risk_profile(client_id, user_id=None, auto_commit=True):
        """Actualizar perfil de riesgo de un cliente

        Args:
            client_id: ID del cliente
            user_id: ID del usuario que realiza la actualización (opcional)
            auto_commit: Si es True, hace commit automáticamente. Si es False, deja la transacción abierta
                        para que la función llamadora haga el commit (útil para transacciones anidadas)
        """
        try:
            # Calcular score
            score, details = ComplianceService.calculate_client_risk_score(client_id)

            # Obtener o crear perfil
            profile = ClientRiskProfile.query.filter_by(client_id=client_id).first()
            if not profile:
                profile = ClientRiskProfile(client_id=client_id)
                db.session.add(profile)

            # Actualizar score
            profile.risk_score = score
            profile.scoring_details = json.dumps(details)
            profile.updated_at = now_peru()

            # Asignar nivel de riesgo
            risk_level_name = ComplianceService.assign_risk_level(score)
            risk_level = RiskLevel.query.filter_by(name=risk_level_name).first()
            if risk_level:
                profile.risk_level_id = risk_level.id

            # Determinar nivel de Due Diligence
            if score >= 76:
                profile.dd_level = 'Reforzada'
            elif score >= 51:
                profile.dd_level = 'Básica'
            else:
                profile.dd_level = 'Simplificada'

            # Solo hacer commit si auto_commit es True
            if auto_commit:
                db.session.commit()

            logger.info(f'Risk profile updated for client {client_id}: score={score}, level={risk_level_name}')
            return True, score, risk_level_name

        except Exception as e:
            # Solo hacer rollback si auto_commit es True (si es False, la función llamadora lo manejará)
            if auto_commit:
                db.session.rollback()
            logger.error(f'Error updating risk profile for client {client_id}: {str(e)}')
            raise  # Re-lanzar la excepción para que la función llamadora la maneje

    @staticmethod
    def analyze_operation(operation_id):
        """
        Analizar operación para detectar actividades sospechosas

        Returns:
            tuple: (alerts_generated, risk_score)
        """
        operation = Operation.query.get(operation_id)
        if not operation:
            return [], 0

        alerts = []
        risk_score = 0
        flags = []

        # 1. Monto inusual
        amount_usd = float(operation.amount_usd)
        if amount_usd >= ComplianceService.THRESHOLD_CRITICAL_AMOUNT:
            risk_score += 40
            flags.append('critical_amount')
            alerts.append(ComplianceService._create_alert(
                alert_type='AML',
                severity='Crítica',
                client_id=operation.client_id,
                operation_id=operation.id,
                title=f'Monto Crítico: ${amount_usd:,.2f}',
                description=f'Operación supera el umbral crítico de ${ComplianceService.THRESHOLD_CRITICAL_AMOUNT:,}',
                details=json.dumps({'amount': amount_usd, 'threshold': ComplianceService.THRESHOLD_CRITICAL_AMOUNT})
            ))
        elif amount_usd >= ComplianceService.THRESHOLD_SUSPICIOUS_AMOUNT:
            risk_score += 25
            flags.append('high_amount')
            alerts.append(ComplianceService._create_alert(
                alert_type='AML',
                severity='Alta',
                client_id=operation.client_id,
                operation_id=operation.id,
                title=f'Monto Alto: ${amount_usd:,.2f}',
                description=f'Operación supera el umbral de monitoreo de ${ComplianceService.THRESHOLD_SUSPICIOUS_AMOUNT:,}',
                details=json.dumps({'amount': amount_usd, 'threshold': ComplianceService.THRESHOLD_SUSPICIOUS_AMOUNT})
            ))

        # 2. Frecuencia inusual
        today = now_peru().date()
        daily_ops = Operation.query.filter(
            Operation.client_id == operation.client_id,
            func.date(Operation.created_at) == today
        ).count()

        if daily_ops > ComplianceService.THRESHOLD_DAILY_OPERATIONS:
            risk_score += 20
            flags.append('high_frequency')
            alerts.append(ComplianceService._create_alert(
                alert_type='Behavioral',
                severity='Media',
                client_id=operation.client_id,
                operation_id=operation.id,
                title=f'Alta Frecuencia: {daily_ops} operaciones hoy',
                description=f'Cliente ha realizado {daily_ops} operaciones en un día',
                details=json.dumps({'daily_count': daily_ops, 'threshold': ComplianceService.THRESHOLD_DAILY_OPERATIONS})
            ))

        # 3. Desviación del promedio del cliente
        client_ops = Operation.query.filter_by(
            client_id=operation.client_id,
            status='Completada'
        ).all()

        if len(client_ops) >= 3:
            amounts = [float(op.amount_usd) for op in client_ops]
            avg_amount = sum(amounts) / len(amounts)
            deviation = ((amount_usd - avg_amount) / avg_amount) * 100 if avg_amount > 0 else 0

            if abs(deviation) > 200:  # Más de 200% de desviación
                risk_score += 15
                flags.append('unusual_deviation')
                alerts.append(ComplianceService._create_alert(
                    alert_type='Volumetric',
                    severity='Media',
                    client_id=operation.client_id,
                    operation_id=operation.id,
                    title=f'Desviación Inusual: {deviation:.1f}%',
                    description=f'Monto se desvía {deviation:.1f}% del promedio del cliente (${avg_amount:,.2f})',
                    details=json.dumps({'deviation': deviation, 'avg': avg_amount, 'current': amount_usd})
                ))

        # 4. Cliente PEP
        risk_profile = ClientRiskProfile.query.filter_by(client_id=operation.client_id).first()
        if risk_profile and risk_profile.is_pep:
            risk_score += 10
            flags.append('pep_client')
            alerts.append(ComplianceService._create_alert(
                alert_type='PEP',
                severity='Alta',
                client_id=operation.client_id,
                operation_id=operation.id,
                title='Cliente PEP',
                description='Operación realizada por Persona Expuesta Políticamente',
                details=json.dumps({'pep': True})
            ))

        # 5. Cliente en listas restrictivas
        if risk_profile and risk_profile.in_restrictive_lists:
            risk_score += 30
            flags.append('restrictive_list')
            alerts.append(ComplianceService._create_alert(
                alert_type='AML',
                severity='Crítica',
                client_id=operation.client_id,
                operation_id=operation.id,
                title='Cliente en Lista Restrictiva',
                description='Operación de cliente que aparece en listas restrictivas',
                details=json.dumps({'restrictive_list': True})
            ))

        # Guardar monitoreo de transacción
        monitoring = TransactionMonitoring(
            operation_id=operation.id,
            client_id=operation.client_id,
            risk_score=min(100, risk_score),
            flags=json.dumps(flags),
            unusual_amount=('high_amount' in flags or 'critical_amount' in flags),
            unusual_frequency=('high_frequency' in flags),
            analyzed_at=now_peru()
        )
        db.session.add(monitoring)

        try:
            db.session.commit()
            logger.info(f'Operation {operation_id} analyzed: {len(alerts)} alerts, risk_score={risk_score}')
        except Exception as e:
            db.session.rollback()
            logger.error(f'Error saving operation analysis: {str(e)}')

        return alerts, min(100, risk_score)

    @staticmethod
    def _create_alert(alert_type, severity, client_id, operation_id, title, description, details, rule_id=None):
        """Crear una alerta de compliance"""
        alert = ComplianceAlert(
            alert_type=alert_type,
            severity=severity,
            client_id=client_id,
            operation_id=operation_id,
            rule_id=rule_id,
            title=title,
            description=description,
            details=details,
            status='Pendiente'
        )
        db.session.add(alert)
        return alert

    @staticmethod
    def get_pending_alerts(severity=None, alert_type=None, limit=50):
        """Obtener alertas pendientes"""
        query = ComplianceAlert.query.filter_by(status='Pendiente')

        if severity:
            query = query.filter_by(severity=severity)
        if alert_type:
            query = query.filter_by(alert_type=alert_type)

        return query.order_by(ComplianceAlert.created_at.desc()).limit(limit).all()

    @staticmethod
    def resolve_alert(alert_id, user_id, resolution, notes):
        """Resolver una alerta"""
        try:
            alert = ComplianceAlert.query.get(alert_id)
            if not alert:
                return False, 'Alerta no encontrada'

            alert.status = 'Resuelta'
            alert.reviewed_at = now_peru()
            alert.reviewed_by = user_id
            alert.resolution = resolution
            alert.review_notes = notes

            db.session.commit()

            logger.info(f'Alert {alert_id} resolved by user {user_id}: {resolution}')
            return True, 'Alerta resuelta correctamente'

        except Exception as e:
            db.session.rollback()
            logger.error(f'Error resolving alert {alert_id}: {str(e)}')
            return False, f'Error: {str(e)}'

    @staticmethod
    def check_restrictive_lists(client_id, user_id, provider='Manual'):
        """
        Simular consulta a listas restrictivas
        En producción, esto se integraría con Inspektor u otro proveedor
        """
        # TODO: Integrar con Inspektor API
        # Por ahora, crear registro manual

        check = RestrictiveListCheck(
            client_id=client_id,
            list_type='Manual',
            provider=provider,
            result='Clean',  # Clean, Match, Potential_Match
            match_score=0,
            details=json.dumps({'note': 'Verificación manual pendiente de integración con Inspektor'}),
            checked_by=user_id
        )

        db.session.add(check)
        db.session.commit()

        return check

    @staticmethod
    def validate_client_documents(client):
        """
        Validar que el cliente tenga todos los documentos necesarios
        Retorna: (is_valid, missing_documents)
        """
        missing_documents = []

        if client.document_type == 'RUC':
            # Validar documentos para RUC
            if not client.dni_representante_front_url:
                missing_documents.append('DNI Representante Legal (Frontal)')
            if not client.dni_representante_back_url:
                missing_documents.append('DNI Representante Legal (Reverso)')
            if not client.ficha_ruc_url:
                missing_documents.append('Ficha RUC')
        else:
            # Validar documentos para DNI/CE
            if not client.dni_front_url:
                missing_documents.append(f'{client.document_type} (Frontal)')
            if not client.dni_back_url:
                missing_documents.append(f'{client.document_type} (Reverso)')

        # Validar cuentas bancarias
        if not client.bank_accounts or len(client.bank_accounts) == 0:
            missing_documents.append('Al menos una cuenta bancaria')

        is_valid = len(missing_documents) == 0
        return is_valid, missing_documents

    @staticmethod
    def get_compliance_dashboard_stats():
        """Obtener estadísticas para el dashboard de Middle Office"""
        stats = {}

        # Alertas pendientes por severidad
        stats['alerts_critical'] = ComplianceAlert.query.filter_by(
            status='Pendiente',
            severity='Crítica'
        ).count()

        stats['alerts_high'] = ComplianceAlert.query.filter_by(
            status='Pendiente',
            severity='Alta'
        ).count()

        stats['alerts_medium'] = ComplianceAlert.query.filter_by(
            status='Pendiente',
            severity='Media'
        ).count()

        stats['alerts_total'] = ComplianceAlert.query.filter_by(status='Pendiente').count()

        # Clientes por nivel de riesgo
        stats['clients_critical_risk'] = ClientRiskProfile.query.filter(
            ClientRiskProfile.risk_score >= 76
        ).count()

        stats['clients_high_risk'] = ClientRiskProfile.query.filter(
            ClientRiskProfile.risk_score >= 51,
            ClientRiskProfile.risk_score < 76
        ).count()

        stats['clients_medium_risk'] = ClientRiskProfile.query.filter(
            ClientRiskProfile.risk_score >= 26,
            ClientRiskProfile.risk_score < 51
        ).count()

        # KYC pendientes
        stats['kyc_pending'] = ClientRiskProfile.query.filter_by(kyc_status='Pendiente').count()
        stats['kyc_in_process'] = ClientRiskProfile.query.filter_by(kyc_status='En Proceso').count()

        # PEP
        stats['pep_clients'] = ClientRiskProfile.query.filter_by(is_pep=True).count()

        # Listas restrictivas
        stats['restrictive_list_matches'] = RestrictiveListCheck.query.filter_by(result='Match').count()

        return stats
