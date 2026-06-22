"""
Agente 7: Executive Intelligence Agent
Genera KPIs, reportes y tendencias ejecutivas de toda la operación de prospección.
"""
import logging
from datetime import timedelta, date
from .base import BaseAgent

_log = logging.getLogger(__name__)


class ExecutiveAgent(BaseAgent):
    agent_id     = 'executive'
    name         = 'Executive Intelligence Agent'
    description  = 'Genera KPIs, reportes y métricas ejecutivas de la operación'
    icon         = 'bi-graph-up-arrow'
    color        = 'navy'
    run_interval = 3600  # cada hora

    def _execute(self, app) -> dict:
        from app.models.prospecto import Prospecto
        from app.models.inteligencia import Oportunidad, EmailEvento
        from app.models.agent import AgentMetric
        from app.extensions import db, socketio
        from sqlalchemy import func

        with app.app_context():
            today = date.today()
            week_ago = today - timedelta(days=7)

            # ── KPIs de prospección ────────────────────────────────────────
            total_prospectos = Prospecto.query.count()
            nuevos_semana = Prospecto.query.filter(
                func.date(Prospecto.creado_en) >= week_ago
            ).count()
            contactados = Prospecto.query.filter(
                Prospecto.num_contactos > 0
            ).count()
            clientes = Prospecto.query.filter(
                Prospecto.estado_comercial.in_(['cliente', 'P4'])
            ).count()
            rebotes = Prospecto.query.filter(
                Prospecto.estado_email == 'REBOTE'
            ).count()

            # ── Emails de la semana ────────────────────────────────────────
            emails_semana = EmailEvento.query.filter(
                func.date(EmailEvento.procesado_en) >= week_ago
            ).count()
            oportunidades_semana = Oportunidad.query.filter(
                func.date(Oportunidad.detectado_en) >= week_ago
            ).count()

            # ── Métricas de agentes del día ───────────────────────────────
            emails_sent_hoy = (db.session.query(func.sum(AgentMetric.emails_sent))
                               .filter(AgentMetric.date == today)
                               .scalar() or 0)

            kpis = {
                'total_prospectos':    total_prospectos,
                'nuevos_semana':       nuevos_semana,
                'contactados':         contactados,
                'clientes':            clientes,
                'rebotes':             rebotes,
                'pendientes':          total_prospectos - contactados,
                'emails_semana':       emails_semana,
                'oportunidades_semana':oportunidades_semana,
                'emails_sent_hoy':     emails_sent_hoy,
                'tasa_conversion':     round(clientes / total_prospectos * 100, 2) if total_prospectos else 0,
            }

            # Emitir KPIs en tiempo real
            try:
                socketio.emit('executive_kpis', kpis, room='authenticated')
            except Exception:
                pass

            msg = (f'KPIs: {total_prospectos} prospectos · '
                   f'{clientes} clientes · {oportunidades_semana} oportunidades esta semana')
            return {
                'tasks':   1,
                'message': msg,
                'detail':  str(kpis),
            }

    @classmethod
    def get_kpis(cls) -> dict:
        """Obtener KPIs actuales (llamado desde rutas API)."""
        from app.models.prospecto import Prospecto
        from app.models.inteligencia import Oportunidad, EmailEvento
        from app.models.agent import AgentMetric
        from app.extensions import db
        from sqlalchemy import func
        import datetime

        today = datetime.date.today()
        week_ago = today - timedelta(days=7)

        try:
            total = Prospecto.query.count()
            nuevos = Prospecto.query.filter(func.date(Prospecto.creado_en) >= week_ago).count()
            contactados = Prospecto.query.filter(Prospecto.num_contactos > 0).count()
            clientes = Prospecto.query.filter(Prospecto.estado_comercial.in_(['cliente', 'P4'])).count()
            rebotes = Prospecto.query.filter(Prospecto.estado_email == 'REBOTE').count()
            opps = Oportunidad.query.filter(func.date(Oportunidad.detectado_en) >= week_ago).count()
            emails_hoy = (db.session.query(func.sum(AgentMetric.emails_sent))
                          .filter(AgentMetric.date == today).scalar() or 0)
            return {
                'total_prospectos': total,
                'nuevos_semana': nuevos,
                'contactados': contactados,
                'clientes': clientes,
                'rebotes': rebotes,
                'pendientes': total - contactados,
                'oportunidades_semana': opps,
                'emails_sent_hoy': emails_hoy,
                'tasa_conversion': round(clientes / total * 100, 2) if total else 0,
            }
        except Exception as e:
            _log.error(f'[Executive] get_kpis error: {e}')
            return {}
