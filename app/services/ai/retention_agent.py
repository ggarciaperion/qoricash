"""
Agente de Cobranza y Retención de Clientes
-------------------------------------------
Identifica clientes en riesgo de abandono y genera:
  1. Segmentación por riesgo de churn (activo/dormido/perdido)
  2. Mensajes personalizados de reactivación
  3. Sugerencias de condiciones/ofertas especiales
  4. Priorización de cartera para el equipo comercial
"""
import logging
from app.services.ai.client import ask_json, ask, HAIKU, SONNET

_log = logging.getLogger(__name__)

# Umbrales de inactividad (días)
_DORMIDO_DIAS  = 30   # Sin operar en 30 días
_PERDIDO_DIAS  = 90   # Sin operar en 90 días


def _get_client_activity() -> list:
    from app.extensions import db
    from app.models.client import Client
    from app.models.operation import Operation
    from sqlalchemy import func
    from app.utils.formatters import now_peru
    from datetime import timedelta

    today = now_peru().date()

    stats = db.session.query(
        Client.id,
        Client.full_name,
        Client.razon_social,
        Client.email,
        Client.status,
        func.max(Operation.completed_at).label('ultima_op'),
        func.count(Operation.id).label('total_ops'),
        func.sum(Operation.amount_usd).label('vol_usd'),
        func.avg(Operation.amount_usd).label('avg_usd'),
    ).outerjoin(
        Operation,
        (Operation.client_id == Client.id) & (Operation.status == 'Completada')
    ).filter(
        Client.status == 'Activo',
    ).group_by(
        Client.id, Client.full_name, Client.razon_social, Client.email, Client.status
    ).all()

    result = []
    for r in stats:
        total_ops = int(r.total_ops or 0)
        vol_usd   = float(r.vol_usd or 0)
        avg_usd   = float(r.avg_usd or 0)

        if r.ultima_op:
            dias_inactivo = (today - r.ultima_op.date()).days
        else:
            dias_inactivo = 9999

        if dias_inactivo <= 14:
            segmento = 'activo'
        elif dias_inactivo <= _DORMIDO_DIAS:
            segmento = 'tibio'
        elif dias_inactivo <= _PERDIDO_DIAS:
            segmento = 'dormido'
        else:
            segmento = 'perdido'

        result.append({
            'id':             r.id,
            'nombre':         r.full_name or r.razon_social or '—',
            'email':          r.email or '—',
            'segmento':       segmento,
            'dias_inactivo':  dias_inactivo if dias_inactivo < 9999 else None,
            'total_ops':      total_ops,
            'vol_usd':        round(vol_usd, 2),
            'avg_usd':        round(avg_usd, 2),
            'ultima_op':      r.ultima_op.strftime('%Y-%m-%d') if r.ultima_op else None,
        })

    return result


def analyze_retention() -> dict:
    """
    Analiza el portafolio de clientes activos y genera reporte de retención.
    """
    try:
        clients = _get_client_activity()
        if not clients:
            return {'ok': True, 'report': {'resumen': 'Sin clientes activos.'}, 'segments': {}}

        # Contar por segmento
        from collections import Counter
        seg_counts = Counter(c['segmento'] for c in clients)

        # Top clientes en riesgo (dormidos + perdidos con volumen alto)
        at_risk = sorted(
            [c for c in clients if c['segmento'] in ('dormido', 'perdido') and c['vol_usd'] > 0],
            key=lambda x: x['vol_usd'],
            reverse=True,
        )[:15]

        # Top clientes tibios (oportunidad de activación)
        tibios = sorted(
            [c for c in clients if c['segmento'] == 'tibio'],
            key=lambda x: x['vol_usd'],
            reverse=True,
        )[:10]

        risk_txt = '\n'.join(
            f"  {i+1}. {c['nombre']} | inactivo {c['dias_inactivo']}d | "
            f"vol=${c['vol_usd']:,.0f} | {c['total_ops']} ops | avg=${c['avg_usd']:,.0f}"
            for i, c in enumerate(at_risk)
        ) or '  (ninguno)'

        tibios_txt = '\n'.join(
            f"  {i+1}. {c['nombre']} | inactivo {c['dias_inactivo']}d | vol=${c['vol_usd']:,.0f}"
            for i, c in enumerate(tibios)
        ) or '  (ninguno)'

        total_vol_risk = sum(c['vol_usd'] for c in at_risk)

        prompt = f"""Eres el director comercial de QoriCash, casa de cambio B2B en Lima Perú.
Analiza el estado de retención del portafolio de clientes y genera un plan de acción.

RESUMEN PORTAFOLIO:
  Total clientes activos: {len(clients)}
  Activos (≤14d): {seg_counts.get('activo', 0)}
  Tibios (15-30d): {seg_counts.get('tibio', 0)}
  Dormidos (31-90d): {seg_counts.get('dormido', 0)}
  Perdidos (>90d): {seg_counts.get('perdido', 0)}
  Volumen en riesgo (dormidos+perdidos): ${total_vol_risk:,.0f} USD

TOP CLIENTES EN RIESGO (dormidos/perdidos con mayor volumen):
{risk_txt}

CLIENTES TIBIOS (oportunidad de reactivación):
{tibios_txt}

Genera un plan de retención con acciones concretas, priorizando por impacto económico.

Responde SOLO JSON:
{{
  "resumen_ejecutivo": "<2-3 oraciones del estado general>",
  "score_retencion": <0-100>,
  "prioridades": [
    {{
      "segmento": "dormido|perdido|tibio",
      "accion": "<acción específica>",
      "canal": "email|whatsapp|llamada",
      "oferta_sugerida": "<incentivo concreto ej: spread especial, operación sin comisión>",
      "urgencia": "alta|media|baja"
    }}
  ],
  "clientes_prioritarios": [
    {{"nombre": "<nombre>", "razon": "<por qué es prioritario>", "accion_inmediata": "<qué hacer>"}}
  ],
  "kpis_objetivo": {{
    "meta_reactivacion_30d": <número de clientes>,
    "vol_usd_recuperable": <estimado USD>
  }},
  "insight": "<observación clave del portafolio>"
}}"""

        result = ask_json(prompt, model=SONNET, max_tokens=1200)
        return {
            'ok':       True,
            'report':   result,
            'segments': dict(seg_counts),
            'total':    len(clients),
            'at_risk':  at_risk[:10],
        }

    except Exception as e:
        _log.error(f'[RetentionAgent] analyze_retention error: {e}', exc_info=True)
        return {'ok': False, 'error': str(e)}


def generate_reactivation_message(client_id: int) -> dict:
    """
    Genera mensaje de reactivación personalizado para un cliente específico.
    """
    try:
        from app.models.client import Client
        from app.models.operation import Operation
        from app.models.exchange_rate import ExchangeRate

        client = Client.query.get(client_id)
        if not client:
            return {'ok': False, 'error': 'Cliente no encontrado'}

        last_op = Operation.query.filter_by(
            client_id=client_id, status='Completada'
        ).order_by(Operation.completed_at.desc()).first()

        er = ExchangeRate.query.order_by(ExchangeRate.updated_at.desc()).first()
        compra = float(er.buy_rate)  if er else 3.70
        venta  = float(er.sell_rate) if er else 3.75

        from app.utils.formatters import now_peru
        dias = None
        if last_op and last_op.completed_at:
            dias = (now_peru().date() - last_op.completed_at.date()).days

        prompt = f"""Eres el director comercial de QoriCash, casa de cambio digital B2B en Lima.
Genera un mensaje de reactivación personalizado para este cliente que lleva tiempo sin operar.

CLIENTE:
  Nombre: {client.full_name or client.razon_social}
  Rubro: {getattr(client, 'rubro', 'empresa') or 'empresa'}
  Días sin operar: {f'{dias} días' if dias else 'nunca ha operado'}
  Última operación: {last_op.completed_at.strftime('%d/%m/%Y') if last_op and last_op.completed_at else 'N/A'}
  Tipo última op: {last_op.operation_type if last_op else 'N/A'}
  Monto última op: ${float(last_op.amount_usd or 0):,.0f} USD

TC HOY: Compramos {compra:.4f} | Vendemos {venta:.4f}

Responde SOLO JSON:
{{
  "canal": "email|whatsapp",
  "asunto": "<asunto del email si aplica>",
  "mensaje": "<mensaje personalizado de reactivación, menciona el tiempo, ofrece algo concreto, incluye el TC>",
  "oferta": "<incentivo específico para que vuelva a operar>",
  "urgencia_contacto": "hoy|esta_semana|este_mes"
}}"""

        result = ask_json(prompt, model=HAIKU, max_tokens=800)
        result['client_id']   = client_id
        result['client_name'] = client.full_name or client.razon_social
        result['dias_inactivo'] = dias
        return {'ok': True, 'message': result}

    except Exception as e:
        _log.error(f'[RetentionAgent] generate_reactivation error: {e}', exc_info=True)
        return {'ok': False, 'error': str(e)}
