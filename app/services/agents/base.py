"""
Clase base para todos los agentes IA de QoriCash.
Gestiona: estado, logging, métricas, SocketIO y manejo de errores.
"""
import logging
import traceback
from datetime import datetime, timedelta, timezone
from typing import Optional

_log = logging.getLogger(__name__)
_LIMA = timezone(timedelta(hours=-5))


def _now():
    return datetime.now(_LIMA).replace(tzinfo=None)


class BaseAgent:
    """
    Clase base de todos los agentes.

    Cada agente concreto debe implementar:
        def _execute(self, app_context) -> dict
            Retorna dict con claves opcionales:
              tasks (int), message (str), detail (str), metrics (dict)
    """

    agent_id: str = 'base_agent'
    name: str = 'Base Agent'
    description: str = ''
    icon: str = 'bi-robot'
    color: str = 'blue'
    run_interval: int = 900  # segundos

    # ── Ciclo de vida ─────────────────────────────────────────────────────────

    def run(self, app) -> dict:
        """Ejecutar un ciclo del agente. Gestiona estado, logging y SocketIO."""
        from app.models.agent import AgentStatus, AgentLog
        from app.extensions import db, socketio

        result = {'tasks': 0, 'message': '', 'detail': '', 'metrics': {}}

        with app.app_context():
            # 1. Marcar como RUNNING
            status = self._get_or_create_status(db)
            status.status = 'running'
            status.last_run = _now()
            db.session.commit()
            self._emit_status(socketio, status)

            try:
                # 2. Ejecutar lógica del agente
                result = self._execute(app) or result

                # 3. Actualizar estado OK
                tasks = result.get('tasks', 0)
                status.status = 'idle'
                status.tasks_today = (status.tasks_today or 0) + tasks
                status.total_tasks = (status.total_tasks or 0) + tasks
                status.last_result = result.get('message', '')
                status.last_error = None
                status.next_run = _now() + timedelta(seconds=self.run_interval)

                # Calcular performance
                total = (status.total_tasks or 0) + (status.total_errors or 0)
                if total > 0:
                    status.performance = 100.0 * (status.total_tasks or 0) / total

                # 4. Log de éxito
                msg = result.get('message', f'{self.name} completó {tasks} tareas')
                log = AgentLog(agent_id=self.agent_id, level='SUCCESS', message=msg,
                               detail=result.get('detail', ''))
                db.session.add(log)

                # 5. Métricas del día
                self._update_metrics(db, result.get('metrics', {}), tasks)

                db.session.commit()
                self._emit_status(socketio, status)
                self._emit_log(socketio, 'SUCCESS', msg, result.get('detail', ''))

            except Exception as e:
                tb = traceback.format_exc()
                _log.error(f'[{self.agent_id}] ❌ {e}\n{tb}')

                status.status = 'error'
                status.errors_today = (status.errors_today or 0) + 1
                status.total_errors = (status.total_errors or 0) + 1
                status.last_error = str(e)[:500]
                status.next_run = _now() + timedelta(seconds=self.run_interval)

                err_msg = f'Error: {str(e)[:200]}'
                log = AgentLog(agent_id=self.agent_id, level='ERROR', message=err_msg, detail=tb[:1000])
                db.session.add(log)
                db.session.commit()

                self._emit_status(socketio, status)
                self._emit_log(socketio, 'ERROR', err_msg)

                result['error'] = str(e)

        return result

    def log_info(self, app, message: str, detail: str = ''):
        """Emitir log INFO en tiempo real (sin bloquear el ciclo principal)."""
        from app.models.agent import AgentLog
        from app.extensions import db, socketio
        with app.app_context():
            log = AgentLog(agent_id=self.agent_id, level='INFO', message=message, detail=detail)
            db.session.add(log)
            db.session.commit()
            self._emit_log(socketio, 'INFO', message, detail)

    def _execute(self, app) -> dict:
        """Implementar en cada agente concreto."""
        raise NotImplementedError

    # ── Helpers internos ─────────────────────────────────────────────────────

    def _get_or_create_status(self, db) -> 'AgentStatus':
        from app.models.agent import AgentStatus
        status = AgentStatus.query.filter_by(agent_id=self.agent_id).first()
        if not status:
            status = AgentStatus(
                agent_id=self.agent_id,
                name=self.name,
                description=self.description,
                icon=self.icon,
                color=self.color,
                run_interval=self.run_interval,
                status='idle',
                enabled=True,
                performance=100.0,
            )
            db.session.add(status)
            db.session.flush()
        return status

    def _update_metrics(self, db, metrics: dict, tasks: int):
        from app.models.agent import AgentMetric
        import datetime as dt
        today = _now().date()
        m = AgentMetric.query.filter_by(agent_id=self.agent_id, date=today).first()
        if not m:
            m = AgentMetric(agent_id=self.agent_id, date=today)
            db.session.add(m)
        m.runs = (m.runs or 0) + 1
        m.tasks_completed = (m.tasks_completed or 0) + tasks
        for key, val in metrics.items():
            if hasattr(m, key):
                setattr(m, key, (getattr(m, key) or 0) + int(val or 0))

    def _emit_status(self, socketio, status):
        try:
            socketio.emit('agent_status_update', status.to_dict(), room='authenticated')
        except Exception:
            pass

    def _emit_log(self, socketio, level: str, message: str, detail: str = ''):
        try:
            socketio.emit('agent_log', {
                'agent_id': self.agent_id,
                'level':    level,
                'message':  message,
                'detail':   detail,
                'time':     _now().strftime('%H:%M:%S'),
            }, room='authenticated')
        except Exception:
            pass

    @classmethod
    def ensure_registered(cls, app):
        """Asegura que el agente tenga fila en agent_status al arrancar."""
        from app.extensions import db
        from app.models.agent import AgentStatus
        with app.app_context():
            if not AgentStatus.query.filter_by(agent_id=cls.agent_id).first():
                s = AgentStatus(
                    agent_id=cls.agent_id, name=cls.name,
                    description=cls.description, icon=cls.icon,
                    color=cls.color, run_interval=cls.run_interval,
                    status='idle', enabled=True, performance=100.0,
                )
                db.session.add(s)
                db.session.commit()
