"""
Orquestador del Ecosistema de Agentes IA — QoriCash
Gestiona el ciclo de vida de todos los agentes, arranca los greenlets
de eventlet y proporciona APIs de control.
"""
import logging
import eventlet
from datetime import timedelta, timezone, datetime

from .lead_discovery     import LeadDiscoveryAgent
from .data_quality       import DataQualityAgent
from .mail_agent         import MailAgent
from .email_intelligence import EmailIntelligenceAgent
from .outreach           import OutreachAgent
from .supervisor         import SupervisorAgent
from .executive          import ExecutiveAgent
from .accounting_audit   import AccountingAuditAgent

_log = logging.getLogger(__name__)
_LIMA = timezone(timedelta(hours=-5))

# Registro global de todos los agentes (orden = flujo del pipeline)
# LeadDiscoveryAgent deshabilitado: la base de prospectos se carga manualmente
ALL_AGENTS = [
    DataQualityAgent(),
    MailAgent(),
    EmailIntelligenceAgent(),
    OutreachAgent(),
    SupervisorAgent(),
    ExecutiveAgent(),
    AccountingAuditAgent(),
]

_agent_map = {a.agent_id: a for a in ALL_AGENTS}
_greenlets = {}  # agent_id → greenlet


def _now():
    return datetime.now(_LIMA).replace(tzinfo=None)


def start_all_agents(app):
    """
    Inicializar todos los agentes como greenlets de eventlet.
    Llamar desde app/__init__.py al arrancar la aplicación.
    """
    # Primero, asegurar que todas las filas existen en agent_status
    for agent in ALL_AGENTS:
        try:
            agent.ensure_registered(app)
        except Exception as e:
            _log.error(f'[Orchestrator] Error registrando {agent.agent_id}: {e}')

    # Luego arrancar cada agente como loop independiente
    for agent in ALL_AGENTS:
        _spawn_agent(app, agent)

    _log.info(f'[Orchestrator] ✅ {len(ALL_AGENTS)} agentes inicializados')


def _spawn_agent(app, agent):
    """Lanza el loop de un agente como greenlet con watchdog."""
    def _loop():
        # Delay inicial escalonado para no saturar el arranque
        delay = {'lead_discovery': 60, 'data_quality': 90, 'mail_agent': 120,
                 'email_intelligence': 30, 'outreach': 150, 'supervisor': 45,
                 'executive': 180, 'accounting_audit': 120}.get(agent.agent_id, 60)
        eventlet.sleep(delay)

        _log.info(f'[Agent] 🟢 {agent.name} iniciado (cada {agent.run_interval}s)')

        while True:
            try:
                # Verificar si el agente está habilitado
                with app.app_context():
                    from app.models.agent import AgentStatus
                    status = AgentStatus.query.filter_by(agent_id=agent.agent_id).first()
                    if status and not status.enabled:
                        _log.info(f'[Agent] ⏸ {agent.name} pausado — esperando...')
                        eventlet.sleep(60)
                        continue

                agent.run(app)
                eventlet.sleep(agent.run_interval)

            except Exception as e:
                import traceback
                _log.error(f'[Agent] ❌ {agent.name} loop error: {e}\n{traceback.format_exc()}')
                eventlet.sleep(60)

    def _watchdog():
        gt = eventlet.spawn(_loop)
        _greenlets[agent.agent_id] = gt
        while True:
            eventlet.sleep(30)
            if gt.dead:
                _log.critical(f'[Watchdog] 🚨 {agent.name} murió — respawneando')
                gt = eventlet.spawn(_loop)
                _greenlets[agent.agent_id] = gt

    eventlet.spawn(_watchdog)


# ── Control manual desde la UI ────────────────────────────────────────────────

def trigger_agent(agent_id: str, app) -> dict:
    """Ejecutar un agente inmediatamente (llamado desde UI)."""
    agent = _agent_map.get(agent_id)
    if not agent:
        return {'error': f'Agente {agent_id} no encontrado'}
    try:
        # Algunos agentes tienen restricciones horarias (ej. accounting_audit).
        # Activar el flag de ejecución forzada si el agente lo soporta.
        if hasattr(agent, '_force_run'):
            agent._force_run = True
        result = agent.run(app)
        return result
    except Exception as e:
        return {'error': str(e)}


def pause_agent(agent_id: str, user_id: int, app) -> bool:
    """Pausar un agente."""
    with app.app_context():
        from app.models.agent import AgentStatus
        from app.extensions import db
        s = AgentStatus.query.filter_by(agent_id=agent_id).first()
        if not s:
            return False
        s.enabled = False
        s.status = 'stopped'
        s.paused_by = user_id
        s.paused_at = _now()
        db.session.commit()
    return True


def resume_agent(agent_id: str, app) -> bool:
    """Reanudar un agente pausado."""
    with app.app_context():
        from app.models.agent import AgentStatus
        from app.extensions import db
        s = AgentStatus.query.filter_by(agent_id=agent_id).first()
        if not s:
            return False
        s.enabled = True
        s.status = 'idle'
        s.paused_by = None
        s.paused_at = None
        db.session.commit()
    return True


def reset_agent_stats(agent_id: str, app) -> bool:
    """Reiniciar contadores del día."""
    with app.app_context():
        from app.models.agent import AgentStatus
        from app.extensions import db
        s = AgentStatus.query.filter_by(agent_id=agent_id).first()
        if not s:
            return False
        s.tasks_today = 0
        s.errors_today = 0
        s.last_error = None
        s.status = 'idle'
        db.session.commit()
    return True


def get_all_statuses(app) -> list:
    """Obtener el estado actual de todos los agentes."""
    with app.app_context():
        from app.models.agent import AgentStatus
        rows = AgentStatus.query.order_by(AgentStatus.id).all()
        return [r.to_dict() for r in rows]
