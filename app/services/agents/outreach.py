"""
Agente 5: Outreach Agent
Gestiona la prospección de nuevos leads: envía secuencias automáticas,
programa seguimientos y actualiza estado comercial.
"""
import logging
from datetime import timedelta, timezone
from .base import BaseAgent

_log = logging.getLogger(__name__)


class OutreachAgent(BaseAgent):
    agent_id     = 'outreach'
    name         = 'Outreach Agent'
    description  = 'Secuencias automáticas para leads nuevos y seguimientos programados'
    icon         = 'bi-megaphone'
    color        = 'teal'
    run_interval = 3600  # cada hora

    def _execute(self, app) -> dict:
        from app.models.prospecto import Prospecto, SeguimientoProspecto, ActividadProspecto
        from app.extensions import db
        from app.utils.formatters import now_peru

        with app.app_context():
            now = now_peru()
            scheduled = 0
            reminded = 0

            # 1. Programar seguimiento automático para prospectos presentados sin próximo contacto
            sin_seguimiento = (Prospecto.query
                               .filter(
                                   Prospecto.estado_comercial == 'presentado',
                                   Prospecto.fecha_proximo_contacto.is_(None),
                                   Prospecto.num_contactos >= 1,
                               )
                               .limit(100).all())

            from app.models.user import User
            bot_user = User.query.filter_by(role='Master').first()

            for p in sin_seguimiento:
                if not bot_user:
                    break
                prox = now + timedelta(days=5)
                seg = SeguimientoProspecto(
                    prospecto_id=p.id,
                    user_id=bot_user.id,
                    tipo='email',
                    descripcion='Seguimiento automático programado por Outreach Agent',
                    fecha_programada=prox,
                    completado=False,
                )
                db.session.add(seg)
                p.fecha_proximo_contacto = prox.strftime('%Y-%m-%d')
                scheduled += 1

            # 2. Detectar seguimientos vencidos y generar alerta
            vencidos = (SeguimientoProspecto.query
                        .filter(
                            SeguimientoProspecto.completado == False,
                            SeguimientoProspecto.fecha_programada < now,
                        )
                        .limit(20).all())

            if len(vencidos) > 0:
                from app.models.agent import AgentAlert
                alerta = AgentAlert(
                    agent_id=self.agent_id,
                    severity='warning',
                    title=f'{len(vencidos)} seguimientos vencidos',
                    message=f'Hay {len(vencidos)} seguimientos programados no completados.',
                )
                db.session.add(alerta)
                reminded = len(vencidos)

            db.session.commit()

            msg = f'Outreach: {scheduled} seguimientos programados · {reminded} alertas por vencidos'
            return {
                'tasks':   scheduled + reminded,
                'message': msg,
                'metrics': {'followups_scheduled': scheduled},
            }
