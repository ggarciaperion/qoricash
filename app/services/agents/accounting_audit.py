"""
Agente de Auditoría Contable — QoriCash
========================================
Ejecuta la auditoría contable diaria a las 23:00 hora Lima (L-V).
Migrado desde el cron job externo en Render ('auditoria-contable-diaria').

Estrategia:
  - run_interval = 3600s (loop cada hora)
  - _execute() comprueba la hora Lima: solo actúa entre 23:00 y 23:59
  - Guarda la fecha de la última ejecución para no duplicar dentro de la misma noche
  - Solo días hábiles (lunes–viernes)
"""
import logging
from datetime import datetime, timedelta, timezone, date

from .base import BaseAgent

_log = logging.getLogger(__name__)
_LIMA = timezone(timedelta(hours=-5))


def _now_lima() -> datetime:
    return datetime.now(_LIMA).replace(tzinfo=None)


class AccountingAuditAgent(BaseAgent):

    agent_id     = 'accounting_audit'
    name         = 'Auditoría Contable'
    description  = 'Auditoría contable diaria: partida doble, conciliación, depreciación automática y Estado de Resultados.'
    icon         = 'bi-shield-check'
    color        = 'purple'
    run_interval = 3600   # revisa cada hora; solo ejecuta dentro de la ventana 23:xx L-V

    # Fecha de la última auditoría completa (en memoria — suficiente, el AgentStatus
    # persiste last_run en DB para visibilidad en el dashboard).
    _last_audit_date: date = None

    def _execute(self, app) -> dict:
        now = _now_lima()

        # 1. Solo lunes–viernes (0=lunes … 6=domingo)
        if now.weekday() >= 5:
            _log.info('[AccountingAudit] Fin de semana — omitiendo.')
            return {'tasks': 0, 'message': 'Fin de semana — sin auditoría.'}

        # 2. Solo ventana 23:00–23:59
        if now.hour != 23:
            _log.debug(f'[AccountingAudit] Fuera de ventana ({now.hour}:xx) — esperando las 23:00.')
            return {'tasks': 0, 'message': f'Esperando ventana 23:00 (hora actual: {now.strftime("%H:%M")}).'}

        # 3. No duplicar si ya corrió hoy
        today = now.date()
        if self._last_audit_date == today:
            _log.info('[AccountingAudit] Auditoría ya ejecutada hoy — omitiendo duplicado.')
            return {'tasks': 0, 'message': f'Auditoría ya ejecutada el {today}.'}

        # 4. Ejecutar auditoría
        from app.services.audit.audit_engine import AuditEngine

        year  = today.year
        month = today.month

        _log.info(f'[AccountingAudit] Iniciando auditoría {month:02d}/{year} ...')
        engine = AuditEngine(
            year=year,
            month=month,
            audit_date=today,
            trigger='agent',
            executed_by_id=None,
            auto_depreciate=True,
        )
        report = engine.run()

        # 5. Marcar como ejecutado
        AccountingAuditAgent._last_audit_date = today

        # 6. Construir resumen
        criticos = report.hallazgos_criticos or 0
        total    = report.total_hallazgos    or 0
        estado   = report.estado             or 'desconocido'
        elapsed  = report.execution_seconds  or 0

        msg = (
            f'Auditoría {month:02d}/{year} completada en {elapsed:.1f}s — '
            f'Estado: {estado} — {total} hallazgo(s) ({criticos} crítico(s)).'
        )

        detail_parts = []
        if report.ops_sin_asiento:
            detail_parts.append(f'{report.ops_sin_asiento} ops sin asiento')
        if report.asientos_descuadrados:
            detail_parts.append(f'{report.asientos_descuadrados} asientos descuadrados')
        if report.diferencias_banco:
            detail_parts.append(f'{report.diferencias_banco} dif. bancarias')
        if report.gastos_sin_comprobante:
            detail_parts.append(f'{report.gastos_sin_comprobante} gastos sin comprobante')
        detail = ' | '.join(detail_parts) if detail_parts else 'Sin hallazgos relevantes.'

        return {
            'tasks':   1,
            'message': msg,
            'detail':  detail,
            'metrics': {
                'hallazgos_criticos': criticos,
                'total_hallazgos':    total,
            },
        }
