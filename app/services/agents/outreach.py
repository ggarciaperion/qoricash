"""
Agente 5: Outreach Agent
Monitor del pipeline de prospección. No envía correos (eso lo hace MailAgent).
Su rol es garantizar que ningún lead caliente se enfríe sin seguimiento:
  - Detecta prospectos en negociación sin actividad en 3+ días → alerta urgente
  - Detecta seguimientos vencidos (SeguimientoProspecto sin completar)
  - Detecta prospectos 'presentado' que ya superaron fecha_proximo_contacto
    pero MailAgent aún no los ha alcanzado → crea SeguimientoProspecto para revisión humana
"""
import logging
from datetime import timedelta, timezone
from .base import BaseAgent

_log = logging.getLogger(__name__)
_DIAS_SIN_ACTIVIDAD_NEGOCIANDO = 3   # días sin respuesta para considerar una oportunidad en riesgo
_DIAS_PRESENTADO_REZAGADO      = 14  # días desde primer contacto sin avance = rezagado


class OutreachAgent(BaseAgent):
    agent_id     = 'outreach'
    name         = 'Outreach Agent'
    description  = 'Monitorea el pipeline: alerta oportunidades en riesgo y seguimientos vencidos'
    icon         = 'bi-megaphone'
    color        = 'teal'
    run_interval = 3600  # cada hora

    def _execute(self, app) -> dict:
        from app.models.prospecto import Prospecto, SeguimientoProspecto, ActividadProspecto
        from app.models.agent import AgentAlert
        from app.extensions import db
        from app.utils.formatters import now_peru
        from sqlalchemy import func

        with app.app_context():
            now   = now_peru()
            today = now.date()
            alerts_created = 0
            followups      = 0

            bot_user = self._get_bot_user()

            # ── 1. Oportunidades en riesgo: 'negociando' sin actividad en 3+ días ──
            umbral_negociando = (today - timedelta(days=_DIAS_SIN_ACTIVIDAD_NEGOCIANDO)).strftime('%Y-%m-%d')

            en_riesgo = (Prospecto.query
                         .filter(
                             Prospecto.estado_comercial == 'negociando',
                             db.or_(
                                 Prospecto.fecha_ultimo_contacto.is_(None),
                                 Prospecto.fecha_ultimo_contacto <= umbral_negociando,
                             ),
                         )
                         .limit(50).all())

            for p in en_riesgo:
                # Evitar alertas duplicadas: comprobar si ya hay una alerta activa
                ya_alertado = (AgentAlert.query
                               .filter(
                                   AgentAlert.agent_id == self.agent_id,
                                   AgentAlert.title.like(f'%{p.id}%'),
                               )
                               .first())
                if ya_alertado:
                    continue

                empresa = (p.razon_social or p.nombre_contacto or f'ID {p.id}')[:60]
                db.session.add(AgentAlert(
                    agent_id=self.agent_id,
                    severity='critical',
                    title=f'[{p.id}] Oportunidad en riesgo: {empresa}',
                    message=(
                        f'El prospecto "{empresa}" está en estado negociando pero '
                        f'no registra actividad desde {p.fecha_ultimo_contacto or "nunca"}. '
                        f'Contactar por WhatsApp o llamada de inmediato.'
                    ),
                ))
                alerts_created += 1

            # ── 2. Seguimientos vencidos (SeguimientoProspecto sin completar) ──
            vencidos = (SeguimientoProspecto.query
                        .filter(
                            SeguimientoProspecto.completado == False,
                            SeguimientoProspecto.fecha_programada < now,
                        )
                        .limit(30).all())

            if vencidos:
                db.session.add(AgentAlert(
                    agent_id=self.agent_id,
                    severity='warning',
                    title=f'{len(vencidos)} seguimientos vencidos sin completar',
                    message=(
                        f'Hay {len(vencidos)} seguimientos programados que no se han marcado '
                        f'como completados. Revisar agenda de seguimiento.'
                    ),
                ))
                alerts_created += 1

            # ── 3. Presentados rezagados: contactados pero sin avance en 14+ días ──
            umbral_presentado = (today - timedelta(days=_DIAS_PRESENTADO_REZAGADO)).strftime('%Y-%m-%d')

            rezagados = (Prospecto.query
                         .filter(
                             Prospecto.estado_comercial == 'presentado',
                             Prospecto.fecha_ultimo_contacto <= umbral_presentado,
                             Prospecto.num_contactos >= 3,   # 3+ intentos sin respuesta
                         )
                         .limit(20).all())

            for p in rezagados:
                if not bot_user:
                    break
                # Verificar que no tenga ya un SeguimientoProspecto pendiente
                tiene_seg = (SeguimientoProspecto.query
                             .filter(
                                 SeguimientoProspecto.prospecto_id == p.id,
                                 SeguimientoProspecto.completado == False,
                             )
                             .first())
                if tiene_seg:
                    continue

                empresa = (p.razon_social or p.nombre_contacto or f'ID {p.id}')[:60]
                seg = SeguimientoProspecto(
                    prospecto_id=p.id,
                    user_id=bot_user.id,
                    tipo='revision',
                    descripcion=(
                        f'Prospecto con {p.num_contactos} contactos sin respuesta en '
                        f'{_DIAS_PRESENTADO_REZAGADO}+ días. Considerar cambio de canal '
                        f'(WhatsApp/llamada) o marcar como inactivo.'
                    ),
                    fecha_programada=now + timedelta(days=1),
                    completado=False,
                )
                db.session.add(seg)
                followups += 1

            db.session.commit()

            msg = (f'Pipeline: {len(en_riesgo)} oportunidades en riesgo · '
                   f'{len(vencidos)} seguimientos vencidos · '
                   f'{followups} rezagados encolados')
            return {
                'tasks':   alerts_created + followups,
                'message': msg,
                'metrics': {
                    'opportunities_at_risk': len(en_riesgo),
                    'overdue_followups':     len(vencidos),
                    'stale_prospects':       followups,
                },
            }

    def _get_bot_user(self):
        try:
            from app.models.user import User
            return User.query.filter_by(role='Master').first()
        except Exception:
            return None
