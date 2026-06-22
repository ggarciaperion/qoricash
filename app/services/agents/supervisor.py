"""
Agente 6: Supervisor & Audit Agent
Audita todos los agentes: detecta procesos caídos, errores de sincronización,
APIs caídas y genera alertas automáticas. Se auto-corrige cuando es posible.
"""
import logging
from datetime import timedelta, timezone, datetime
from .base import BaseAgent

_log = logging.getLogger(__name__)
_LIMA = timezone(timedelta(hours=-5))

# Máximo tiempo sin ejecutar para cada agente (segundos)
_MAX_IDLE = {
    'lead_discovery':    7200,   # 2h
    'data_quality':      9000,   # 2.5h
    'mail_agent':        3600,   # 1h
    'email_intelligence':1800,   # 30 min
    'outreach':          7200,   # 2h
    'executive':        86400,   # 24h
}


class SupervisorAgent(BaseAgent):
    agent_id     = 'supervisor'
    name         = 'Supervisor & Audit Agent'
    description  = 'Audita todos los agentes, detecta fallos y genera alertas automáticas'
    icon         = 'bi-eye'
    color        = 'red'
    run_interval = 600  # cada 10 min

    def _execute(self, app) -> dict:
        from app.models.agent import AgentStatus, AgentAlert, AgentLog
        from app.extensions import db

        with app.app_context():
            alerts_created = 0
            agents_ok = 0

            now = datetime.now(_LIMA).replace(tzinfo=None)
            all_agents = AgentStatus.query.filter(
                AgentStatus.agent_id != self.agent_id
            ).all()

            for agent in all_agents:
                if not agent.enabled:
                    continue

                issues = []

                # 1. ¿Está en estado error?
                if agent.status == 'error':
                    issues.append(f'Estado ERROR desde última ejecución: {agent.last_error or "—"}')

                # 2. ¿Hace demasiado tiempo sin ejecutar?
                max_idle = _MAX_IDLE.get(agent.agent_id, 14400)
                if agent.last_run:
                    elapsed = (now - agent.last_run).total_seconds()
                    if elapsed > max_idle:
                        hours = elapsed / 3600
                        issues.append(f'Sin ejecutar hace {hours:.1f}h (límite {max_idle//3600}h)')

                # 3. Tasa de errores alta (>30%)
                total = (agent.total_tasks or 0) + (agent.total_errors or 0)
                if total > 10:
                    err_rate = (agent.total_errors or 0) / total
                    if err_rate > 0.30:
                        issues.append(f'Tasa de errores alta: {err_rate*100:.0f}%')

                if issues:
                    # Evitar duplicar alertas activas del mismo agente
                    existing = AgentAlert.query.filter_by(
                        agent_id=agent.agent_id, resolved=False
                    ).count()
                    if existing < 3:
                        for issue in issues:
                            alert = AgentAlert(
                                agent_id=agent.agent_id,
                                severity='error' if agent.status == 'error' else 'warning',
                                title=f'{agent.name}: Anomalía detectada',
                                message=issue,
                            )
                            db.session.add(alert)
                            alerts_created += 1
                else:
                    agents_ok += 1

            # 4. Verificar prospectos duplicados masivos
            from app.models.prospecto import Prospecto
            from sqlalchemy import func
            dup_count = (db.session.query(func.count())
                         .select_from(Prospecto)
                         .filter(Prospecto.notas.like('%DUPLICADO%'))
                         .scalar() or 0)
            if dup_count > 100:
                dup_alert = AgentAlert(
                    severity='warning',
                    title='Duplicados masivos detectados',
                    message=f'{dup_count} prospectos marcados como duplicados — revisar base.',
                )
                db.session.add(dup_alert)
                alerts_created += 1

            # 5. Resolver alertas antiguas si el agente ya está OK
            for agent in all_agents:
                if agent.status == 'idle' or agent.status == 'running':
                    (AgentAlert.query
                     .filter_by(agent_id=agent.agent_id, resolved=False)
                     .filter(AgentAlert.severity.in_(['warning', 'info']))
                     .update({'resolved': True, 'resolved_at': now},
                             synchronize_session=False))

            db.session.commit()

            msg = f'Auditoría: {agents_ok} agentes OK · {alerts_created} alertas nuevas'
            return {
                'tasks':   alerts_created + agents_ok,
                'message': msg,
            }
