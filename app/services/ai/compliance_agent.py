"""
Agente de Compliance KYC — Screening Inteligente
-------------------------------------------------
Analiza el perfil de un cliente y genera un reporte de riesgo completo.
Va más allá del fuzzy matching: detecta patrones de comportamiento,
inconsistencias en el perfil, señales de riesgo contextual.
"""
import logging
from app.services.ai.client import ask_json, SONNET

_log = logging.getLogger(__name__)


def _get_client_context(client_id: int) -> dict:
    from app.extensions import db
    from app.models.client import Client
    from app.models.compliance import ClientCompliance
    from app.models.operation import Operation
    from sqlalchemy import func

    client = Client.query.get(client_id)
    if not client:
        raise ValueError(f'Cliente {client_id} no encontrado')

    compliance = ClientCompliance.query.filter_by(client_id=client_id).first()

    # Estadísticas de operaciones
    stats = db.session.query(
        func.count(Operation.id).label('total'),
        func.sum(Operation.amount_usd).label('vol_usd'),
        func.avg(Operation.exchange_rate).label('tc_promedio'),
        func.max(Operation.amount_usd).label('max_usd'),
    ).filter(
        Operation.client_id == client_id,
        Operation.status == 'Completada',
    ).first()

    # Operaciones recientes (últimas 5)
    recent_ops = Operation.query.filter_by(
        client_id=client_id, status='Completada'
    ).order_by(Operation.completed_at.desc()).limit(5).all()

    return {
        'id':              client.id,
        'nombre':          client.full_name,
        'doc_type':        client.document_type,
        'doc_number':      client.dni,
        'email':           client.email,
        'razon_social':    client.razon_social or '—',
        'direccion':       f"{client.distrito or ''}, {client.provincia or ''}, {client.departamento or ''}",
        'status':          client.status,
        'origen':          client.origen or '—',
        'ops_total':       int(stats.total or 0),
        'vol_usd_total':   round(float(stats.vol_usd or 0), 2),
        'tc_promedio':     round(float(stats.tc_promedio or 0), 4),
        'max_op_usd':      round(float(stats.max_usd or 0), 2),
        'kyc_status':      compliance.kyc_status if compliance else 'Pendiente',
        'risk_score':      compliance.risk_score if compliance else 0,
        'is_pep':          compliance.is_pep if compliance else False,
        'in_restrictive':  compliance.in_restrictive_lists if compliance else False,
        'dd_level':        compliance.dd_level if compliance else '—',
        'recent_ops':      [
            {
                'tipo':   op.operation_type,
                'usd':    float(op.amount_usd or 0),
                'tc':     float(op.exchange_rate or 0),
                'fecha':  op.completed_at.strftime('%Y-%m-%d') if op.completed_at else '—',
            }
            for op in recent_ops
        ],
    }


def analyze_client(client_id: int) -> dict:
    """
    Genera reporte de riesgo KYC completo para un cliente.
    """
    try:
        ctx = _get_client_context(client_id)

        ops_txt = '\n'.join(
            f"  {o['fecha']}: {o['tipo']} ${o['usd']:,.0f} @ {o['tc']:.4f}"
            for o in ctx['recent_ops']
        ) or '  (sin operaciones completadas)'

        prompt = f"""Eres el oficial de cumplimiento de QoriCash, casa de cambio regulada por la SBS de Perú.
Analiza el perfil de este cliente y genera un reporte de riesgo KYC detallado.

PERFIL DEL CLIENTE:
- Nombre/Razón Social: {ctx['nombre']} / {ctx['razon_social']}
- Documento: {ctx['doc_type']} {ctx['doc_number']}
- Origen: {ctx['origen']}
- Dirección: {ctx['direccion']}
- Estado cuenta: {ctx['status']}
- PEP: {'Sí' if ctx['is_pep'] else 'No'} | En listas restrictivas: {'Sí' if ctx['in_restrictive'] else 'No'}
- KYC status actual: {ctx['kyc_status']} | Score actual: {ctx['risk_score']}/100

HISTORIAL OPERATIVO:
- Total ops: {ctx['ops_total']} | Volumen USD total: ${ctx['vol_usd_total']:,.2f}
- TC promedio: {ctx['tc_promedio']:.4f} | Operación máxima: ${ctx['max_op_usd']:,.2f}
- Operaciones recientes:
{ops_txt}

Detecta patrones de riesgo (actividad inusual, escalada súbita de montos, inconsistencias).
Considera normativa SBS/UIF de Perú para casas de cambio.

Responde SOLO JSON:
{{
  "risk_score": <0-100>,
  "nivel_riesgo": "Bajo|Medio|Alto|Crítico",
  "nivel_dd": "Simplificada|Básica|Reforzada",
  "señales_riesgo": ["<señal1>", "<señal2>"],
  "señales_positivas": ["<positivo1>"],
  "resumen": "<análisis en 3-4 oraciones para el oficial de cumplimiento>",
  "acciones_recomendadas": ["<acción1>", "<acción2>"],
  "requiere_sar": true|false,
  "justificacion_sar": "<solo si requiere_sar es true>",
  "siguiente_revision": "<periodicidad: mensual|trimestral|anual>"
}}"""

        result = ask_json(prompt, model=SONNET, max_tokens=1200)
        result['client_id']   = client_id
        result['client_name'] = ctx['nombre']
        return {'ok': True, 'report': result, 'context': ctx}

    except Exception as e:
        _log.error(f'[ComplianceAgent] Error client {client_id}: {e}', exc_info=True)
        return {'ok': False, 'error': str(e)}


def analyze_batch_alerts() -> dict:
    """
    Analiza todos los clientes activos buscando patrones de riesgo a nivel portafolio.
    """
    try:
        from app.extensions import db
        from app.models.client import Client
        from app.models.operation import Operation
        from sqlalchemy import func
        from datetime import datetime, timedelta
        from app.utils.formatters import now_peru

        # Clientes con operaciones en los últimos 30 días
        cutoff = now_peru() - timedelta(days=30)
        active = db.session.query(
            Client.id,
            Client.nombres,
            Client.apellido_paterno,
            Client.razon_social,
            func.count(Operation.id).label('ops'),
            func.sum(Operation.amount_usd).label('vol'),
            func.max(Operation.amount_usd).label('max_op'),
        ).join(Operation, Operation.client_id == Client.id).filter(
            Operation.status == 'Completada',
            Operation.completed_at >= cutoff,
        ).group_by(
            Client.id, Client.nombres, Client.apellido_paterno, Client.razon_social
        ).all()

        # Detectar outliers (vol o max_op muy por encima del promedio)
        if not active:
            return {'ok': True, 'alerts': [], 'summary': 'Sin actividad en los últimos 30 días'}

        vols = [float(r.vol or 0) for r in active]
        avg_vol = sum(vols) / len(vols)
        threshold = avg_vol * 3  # 3x el promedio = outlier

        def _nombre(r):
            if r.razon_social:
                return r.razon_social
            parts = [r.nombres, r.apellido_paterno]
            return ' '.join(p for p in parts if p) or '—'

        outliers = [
            {
                'client_id':    r.id,
                'nombre':       _nombre(r),
                'ops_30d':      int(r.ops),
                'vol_usd_30d':  round(float(r.vol or 0), 2),
                'max_op_usd':   round(float(r.max_op or 0), 2),
                'razon':        'Volumen 3x por encima del promedio' if float(r.vol or 0) > threshold else 'Alta frecuencia',
            }
            for r in active
            if float(r.vol or 0) > threshold or int(r.ops) > 20
        ]

        return {
            'ok':       True,
            'total_activos': len(active),
            'avg_vol_usd': round(avg_vol, 2),
            'alertas':  outliers[:10],
            'summary':  f'{len(active)} clientes activos en 30 días. {len(outliers)} requieren revisión.',
        }

    except Exception as e:
        _log.error(f'[ComplianceAgent] batch alerts error: {e}', exc_info=True)
        return {'ok': False, 'error': str(e)}
