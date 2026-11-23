"""
wa_prospectos.py — Campañas WA a prospectos de la Fuente de Datos

Blueprint: /wa-prospectos/

Rutas:
  GET  /                          Panel principal
  GET  /api/elegibles             Prospectos elegibles (email previo + teléfono válido)
  GET  /api/plantillas            Plantillas activas desde config_whatsapp.json
  POST /api/enviar                Envío masivo a lista seleccionada
  GET  /api/campanas              Historial de campañas enviadas
  GET  /api/campanas/<campana>    Detalle de una campaña

Validación WA:
  Meta Cloud API no tiene endpoint de validación gratuito.
  La validación ocurre en el primer intento de envío:
    - 200 OK con messages[] → con_wa
    - Error 131026 / 131030  → sin_wa
    - Otro error             → error (reintentable)
"""
import json
import logging
import os
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
from flask import Blueprint, jsonify, render_template, request, current_app
from flask_login import login_required, current_user
from sqlalchemy import func, or_

from app.extensions import db
from app.models.prospecto import Prospecto, ActividadProspecto
from app.models.wa_campana_prospecto import WaCampanaProspecto
from app.models.wa_bot_session import WaBotSession
from app.utils.formatters import now_peru

log = logging.getLogger(__name__)

wa_prospectos_bp = Blueprint('wa_prospectos', __name__, url_prefix='/wa-prospectos')

# ── Config WhatsApp ───────────────────────────────────────────────────────────
_BASE_DIR = Path(__file__).parent.parent.parent  # raíz del proyecto
_CFG_PATH = _BASE_DIR / 'config_whatsapp.json'  # local dev; Render usa env vars

def _get_wa_config():
    """Carga config WA: env vars (producción) o config_whatsapp.json (dev local)."""
    token    = os.environ.get('WA_ACCESS_TOKEN', '')
    phone_id = os.environ.get('WA_PHONE_NUMBER_ID', '1197587863432080')
    if not token:
        # Dev local: leer desde config_whatsapp.json en la raíz del repo Prospeccion
        for cfg_path in [
            _CFG_PATH,
            Path(os.environ.get('WA_CONFIG_PATH', '')),
            Path.home() / 'Desktop' / 'Prospeccion' / 'config_whatsapp.json',
        ]:
            if cfg_path and cfg_path.exists():
                with open(cfg_path) as f:
                    cfg = json.load(f)
                token    = token    or cfg.get('access_token', '')
                phone_id = phone_id or cfg.get('phone_number_id', phone_id)
                break
    return token, phone_id

HEADER_IMAGE = 'https://app.qoricash.pe/static/banner_wa.png'

# Plantillas conocidas (se pueden extender desde config)
_PLANTILLAS_DEFAULT = [
    {
        'nombre':  'qoricash_precio_dia',
        'label':   'Precio del día (nuevo)',
        'idioma':  'es',
        'vars':    ['nombre', 'compra', 'venta'],
        'tiene_header_imagen': True,
    },
    {
        'nombre':  'qoricash_clientes_reactivacion',
        'label':   'Reactivación clientes',
        'idioma':  'es',
        'vars':    ['nombre', 'compra', 'venta'],
        'tiene_header_imagen': False,
    },
]

# Errores Meta que indican "número sin WhatsApp"
_ERRORES_SIN_WA = {131026, 131030}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _valid_mobile(val):
    """Retorna número 9 dígitos o None."""
    if not val:
        return None
    d = re.sub(r'\D', '', str(val))
    if d.startswith('51') and len(d) == 11:
        d = d[2:]
    if len(d) == 9 and d[0] == '9':
        return d
    return None

def _primer_numero(prospecto):
    """Extrae el primer número de celular válido de un Prospecto."""
    for campo in (prospecto.contacto_wa, prospecto.telefono,
                  prospecto.telefono_alt, prospecto.telefono_3, prospecto.telefono_4):
        n = _valid_mobile(campo)
        if n:
            return n
    return None

def _primer_nombre(full_name):
    if not full_name:
        return 'Estimado/a'
    words = full_name.strip().split()
    if not words:
        return 'Estimado/a'
    return words[0].capitalize()


def _enviar_wa_meta(numero_9d, nombre, compra, venta, plantilla_cfg):
    """
    Envía plantilla WA a +51{numero_9d}.
    Retorna (ok: bool, wa_id: str, error_code: int, error_msg: str)
    """
    token, phone_id = _get_wa_config()
    if not token or not phone_id:
        return False, '', -1, 'Config WA no disponible (token/phone_id)'

    destino = f'51{numero_9d}'
    components = []

    if plantilla_cfg.get('tiene_header_imagen'):
        components.append({
            'type': 'header',
            'parameters': [{'type': 'image', 'image': {'link': HEADER_IMAGE}}],
        })

    components.append({
        'type': 'body',
        'parameters': [
            {'type': 'text', 'parameter_name': 'nombre', 'text': nombre},
            {'type': 'text', 'parameter_name': 'compra', 'text': compra},
            {'type': 'text', 'parameter_name': 'venta',  'text': venta},
        ],
    })

    payload = {
        'messaging_product': 'whatsapp',
        'to': destino,
        'type': 'template',
        'template': {
            'name':     plantilla_cfg['nombre'],
            'language': {'code': plantilla_cfg['idioma']},
            'components': components,
        },
    }

    try:
        r = requests.post(
            f'https://graph.facebook.com/v19.0/{phone_id}/messages',
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
            json=payload,
            timeout=15,
        )
        resp = r.json()
        if r.ok and resp.get('messages'):
            wa_id = resp['messages'][0].get('id', '')
            return True, wa_id, 0, ''
        err   = resp.get('error', {})
        return False, '', err.get('code', 0), err.get('message', str(resp))[:300]
    except Exception as e:
        return False, '', -1, str(e)[:300]


# ── Rutas ─────────────────────────────────────────────────────────────────────

@wa_prospectos_bp.route('/')
@login_required
def index():
    if current_user.role not in ('Master', 'Presidente de Negocios'):
        return 'Acceso denegado', 403
    return render_template('wa_prospectos/index.html')


@wa_prospectos_bp.route('/api/plantillas')
@login_required
def api_plantillas():
    """Retorna plantillas disponibles."""
    return jsonify({'ok': True, 'plantillas': _PLANTILLAS_DEFAULT})


@wa_prospectos_bp.route('/api/elegibles')
@login_required
def api_elegibles():
    """
    Retorna prospectos elegibles para campaña WA, ordenados por calidad de señal WA.

    Prioridad (wa_validado):
      1. 'bot_session'  — número con sesión activa en WaBotSession (confirmado WA por interacción real)
      2. 'con_wa'       — número que recibió template en campaña anterior sin error
      3. 'sin_historial'— número sin historial WA pero contactado por email (riesgo controlado)

    Excluidos:
      - 'sin_wa'        — números que ya fallaron con error 131026/131030 (no tiene WA)
      - no_contactar    — excluidos siempre
      - ya enviados en esta campaña (dedup)

    La API de Meta Cloud NO ofrece endpoint de validación de números.
    No se usa el envío como mecanismo de descubrimiento masivo.
    """
    campana     = request.args.get('campana', '').strip()
    solo_con_wa = request.args.get('solo_con_wa', 'false').lower() == 'true'
    limit       = min(int(request.args.get('limit', 500)), 2000)

    # ── 1. Números con sesión real en el bot (máxima confianza) ──────────────
    # WaBotSession.numero puede estar en formato '51XXXXXXXXX' o 'XXXXXXXXX'
    bot_rows = db.session.query(WaBotSession.numero).all()
    numeros_bot = set()
    for (n,) in bot_rows:
        d = re.sub(r'\D', '', str(n))
        if d.startswith('51') and len(d) == 11:
            d = d[2:]
        if len(d) == 9:
            numeros_bot.add(d)

    # ── 2. Números confirmados/rechazados por campañas anteriores ────────────
    campana_rows = db.session.query(
        WaCampanaProspecto.numero,
        WaCampanaProspecto.wa_validado,
    ).all()
    confirmados_wa = set()   # con_wa — enviado OK antes
    rechazados_wa  = set()   # sin_wa — error 131026/131030
    for (num, estado) in campana_rows:
        d = re.sub(r'\D', '', str(num))
        if d.startswith('51') and len(d) == 11:
            d = d[2:]
        if len(d) == 9:
            if estado == 'con_wa':
                confirmados_wa.add(d)
            elif estado == 'sin_wa':
                rechazados_wa.add(d)

    # ── 3. Números ya enviados en esta campaña (dedup) ───────────────────────
    enviados_campana = set()
    if campana:
        rows = db.session.query(WaCampanaProspecto.numero).filter(
            WaCampanaProspecto.campana == campana
        ).all()
        for (num,) in rows:
            d = re.sub(r'\D', '', str(num))
            if d.startswith('51') and len(d) == 11:
                d = d[2:]
            enviados_campana.add(d)

    # ── 4. Prospectos contactados (ya tienen relación con Qoricash) ──────────
    _ESTADOS_CONTACTADOS = (
        'contactado', 'interesado', 'negociando', 'cliente',
        'P1', 'P2', 'P3', 'P4', 'presentado', 'precio_enviado', 'seguimiento',
    )
    email_ids = (
        db.session.query(ActividadProspecto.prospecto_id)
        .filter(or_(
            ActividadProspecto.canal == 'email',
            ActividadProspecto.tipo  == 'email',
        ))
        .distinct()
        .subquery()
    )
    prospectos = (
        Prospecto.query
        .filter(
            or_(
                Prospecto.id.in_(email_ids),
                Prospecto.estado_comercial.in_(_ESTADOS_CONTACTADOS),
                Prospecto.tipo_ultimo_envio.isnot(None),
                Prospecto.fecha_ultimo_contacto.isnot(None),
            ),
            Prospecto.estado_comercial != 'no_contactar',
        )
        .order_by(Prospecto.fecha_ultimo_contacto.desc().nullslast())
        .all()
    )

    # ── 5. Construir lista priorizada ────────────────────────────────────────
    _PRIO = {'bot_session': 0, 'con_wa': 1, 'sin_historial': 2}

    candidatos = []
    seen_phones = set()

    for p in prospectos:
        numero = _primer_numero(p)
        if not numero or numero in seen_phones:
            continue
        if numero in enviados_campana:
            continue
        if numero in rechazados_wa:
            continue  # sabemos que no tiene WA — no desperdiciar cuota

        if numero in numeros_bot:
            wa_estado = 'bot_session'
        elif numero in confirmados_wa:
            wa_estado = 'con_wa'
        else:
            wa_estado = 'sin_historial'

        if solo_con_wa and wa_estado == 'sin_historial':
            continue

        seen_phones.add(numero)
        candidatos.append({
            'prospecto_id':   p.id,
            'numero':         f'+51{numero}',
            'numero_display': numero,
            'nombre':         p.nombre_contacto or '',
            'empresa':        p.razon_social or '',
            'rubro':          p.rubro or '',
            'provincia':      p.provincia or '',
            'estado_com':     p.estado_comercial or '',
            'ult_contacto':   str(p.fecha_ultimo_contacto) if p.fecha_ultimo_contacto else '',
            'wa_validado':    wa_estado,
            '_prio':          _PRIO.get(wa_estado, 9),
        })

    # Ordenar: bot_session → con_wa → sin_historial
    candidatos.sort(key=lambda x: x['_prio'])
    for c in candidatos:
        del c['_prio']

    resultado = candidatos[:limit]
    return jsonify({'ok': True, 'total': len(resultado), 'prospectos': resultado})


@wa_prospectos_bp.route('/api/enviar', methods=['POST'])
@login_required
def api_enviar():
    """
    Envía plantilla WA a lista seleccionada de prospectos.

    Body JSON:
    {
      "campana":    "Nov2026",
      "plantilla":  "qoricash_precio_dia",
      "compra":     "3.377",
      "venta":      "3.381",
      "prospectos": [
        {"prospecto_id": 1, "numero": "+51912345678", "nombre": "Carlos", "empresa": "Importex SAC"},
        ...
      ]
    }
    """
    if current_user.role not in ('Master', 'Presidente de Negocios'):
        return jsonify({'ok': False, 'error': 'Acceso denegado'}), 403

    data = request.get_json(silent=True) or {}

    campana   = (data.get('campana') or '').strip()
    plantilla_nombre = (data.get('plantilla') or '').strip()
    compra    = (data.get('compra') or '').strip()
    venta     = (data.get('venta') or '').strip()
    lista     = data.get('prospectos', [])
    pausa_seg = float(data.get('pausa_seg', 2))

    if not campana:
        return jsonify({'ok': False, 'error': 'campana requerida'}), 400
    if not plantilla_nombre:
        return jsonify({'ok': False, 'error': 'plantilla requerida'}), 400
    if not compra or not venta:
        return jsonify({'ok': False, 'error': 'compra y venta requeridos'}), 400
    if not lista:
        return jsonify({'ok': False, 'error': 'lista de prospectos vacía'}), 400

    # Buscar config de plantilla
    plantilla_cfg = next(
        (p for p in _PLANTILLAS_DEFAULT if p['nombre'] == plantilla_nombre),
        None
    )
    if not plantilla_cfg:
        # Usar defaults si es una plantilla nueva no listada
        plantilla_cfg = {
            'nombre': plantilla_nombre, 'idioma': 'es',
            'vars': ['nombre', 'compra', 'venta'], 'tiene_header_imagen': False,
        }

    ahora = now_peru()
    resultados = []
    ok_cnt = fallido_cnt = sin_wa_cnt = duplicado_cnt = 0

    for item in lista:
        pid     = item.get('prospecto_id')
        numero  = (item.get('numero') or '').strip()
        nombre  = (item.get('nombre') or 'Estimado/a').strip()
        empresa = (item.get('empresa') or '').strip()

        if not numero:
            continue

        # Normalizar nombre
        primer_n = _primer_nombre(nombre) if nombre else 'Estimado/a'

        # Verificar dedup por campana
        existente = WaCampanaProspecto.query.filter_by(
            numero=numero, campana=campana
        ).first()
        if existente:
            duplicado_cnt += 1
            resultados.append({
                'numero': numero, 'nombre': nombre, 'empresa': empresa,
                'estado': 'duplicado', 'error': f'Ya enviado a {numero} en campaña {campana}',
            })
            continue

        # Enviar
        exito, wa_id, err_code, err_msg = _enviar_wa_meta(
            numero.lstrip('+').lstrip('51'),
            primer_n, compra, venta, plantilla_cfg
        )

        # Determinar estado WA
        if exito:
            estado      = 'enviado'
            wa_validado = 'con_wa'
            ok_cnt += 1
        elif err_code in _ERRORES_SIN_WA:
            estado      = 'sin_wa'
            wa_validado = 'sin_wa'
            sin_wa_cnt += 1
        else:
            estado      = 'fallido'
            wa_validado = 'sin_validar'  # error técnico, no sabemos si tiene WA
            fallido_cnt += 1

        # Registrar en DB
        registro = WaCampanaProspecto(
            prospecto_id     = pid,
            numero           = numero,
            nombre           = nombre,
            empresa          = empresa,
            wa_validado      = wa_validado,
            fecha_validacion = ahora,
            campana          = campana,
            plantilla        = plantilla_nombre,
            compra           = compra,
            venta            = venta,
            wa_id            = wa_id or None,
            estado           = estado,
            error_msg        = err_msg or None,
            fecha_envio      = ahora if exito else None,
            enviado_por      = current_user.id,
            creado_en        = ahora,
            actualizado_en   = ahora,
        )
        db.session.add(registro)

        # Registrar en ActividadProspecto si hay prospecto_id
        if pid and exito:
            try:
                from app.models.prospecto import ActividadProspecto as AP
                actividad = AP(
                    prospecto_id = pid,
                    user_id      = current_user.id,
                    tipo         = 'whatsapp',
                    canal        = 'whatsapp',
                    descripcion  = f'[WA Campaña {campana}] Plantilla {plantilla_nombre} — TC Compra {compra} / Venta {venta}',
                    resultado    = 'enviado',
                    creado_en    = ahora,
                )
                db.session.add(actividad)
            except Exception as e:
                log.warning(f'[WA Prospectos] No se pudo registrar actividad para {pid}: {e}')

        resultados.append({
            'numero':  numero,
            'nombre':  nombre,
            'empresa': empresa,
            'estado':  estado,
            'wa_id':   wa_id or '',
            'error':   err_msg or '',
        })

        try:
            db.session.flush()
        except Exception as e:
            db.session.rollback()
            log.error(f'[WA Prospectos] Error flush para {numero}: {e}')

        if pausa_seg > 0 and len(lista) > 1:
            time.sleep(pausa_seg)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        log.error(f'[WA Prospectos] Error commit: {e}')
        return jsonify({'ok': False, 'error': f'Error guardando resultados: {e}'}), 500

    log.info(
        f'[WA Prospectos] Campaña {campana!r} — '
        f'OK:{ok_cnt} SinWA:{sin_wa_cnt} Fallidos:{fallido_cnt} Duplicados:{duplicado_cnt}'
    )

    return jsonify({
        'ok':         True,
        'campana':    campana,
        'resumen': {
            'total':      len(lista),
            'enviados':   ok_cnt,
            'sin_wa':     sin_wa_cnt,
            'fallidos':   fallido_cnt,
            'duplicados': duplicado_cnt,
        },
        'resultados': resultados,
    })


@wa_prospectos_bp.route('/api/campanas')
@login_required
def api_campanas():
    """Historial de campañas enviadas (agrupado por nombre de campaña)."""
    rows = db.session.query(
        WaCampanaProspecto.campana,
        WaCampanaProspecto.plantilla,
        func.count(WaCampanaProspecto.id).label('total'),
        func.sum(db.case((WaCampanaProspecto.estado == 'enviado',   1), else_=0)).label('enviados'),
        func.sum(db.case((WaCampanaProspecto.estado == 'entregado', 1), else_=0)).label('entregados'),
        func.sum(db.case((WaCampanaProspecto.estado == 'leido',     1), else_=0)).label('leidos'),
        func.sum(db.case((WaCampanaProspecto.estado == 'fallido',   1), else_=0)).label('fallidos'),
        func.sum(db.case((WaCampanaProspecto.estado == 'sin_wa',    1), else_=0)).label('sin_wa'),
        func.min(WaCampanaProspecto.fecha_envio).label('inicio'),
        func.max(WaCampanaProspecto.fecha_envio).label('fin'),
        WaCampanaProspecto.compra,
        WaCampanaProspecto.venta,
    ).group_by(
        WaCampanaProspecto.campana,
        WaCampanaProspecto.plantilla,
        WaCampanaProspecto.compra,
        WaCampanaProspecto.venta,
    ).order_by(func.max(WaCampanaProspecto.fecha_envio).desc()).all()

    campanas = []
    for r in rows:
        total = r.total or 0
        env   = (r.enviados or 0) + (r.entregados or 0) + (r.leidos or 0)
        campanas.append({
            'campana':    r.campana,
            'plantilla':  r.plantilla,
            'compra':     r.compra or '',
            'venta':      r.venta or '',
            'total':      total,
            'enviados':   env,
            'entregados': r.entregados or 0,
            'leidos':     r.leidos or 0,
            'fallidos':   r.fallidos or 0,
            'sin_wa':     r.sin_wa or 0,
            'tasa_entrega': round((r.entregados or 0) / env * 100, 1) if env > 0 else 0,
            'tasa_lectura': round((r.leidos or 0) / env * 100, 1) if env > 0 else 0,
            'inicio':     r.inicio.strftime('%d/%m/%Y %H:%M') if r.inicio else '',
            'fin':        r.fin.strftime('%d/%m/%Y %H:%M') if r.fin else '',
        })

    return jsonify({'ok': True, 'campanas': campanas})


@wa_prospectos_bp.route('/api/campanas/<campana_nombre>')
@login_required
def api_campana_detalle(campana_nombre):
    """Detalle de todos los envíos de una campaña específica."""
    page  = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 100))

    total = WaCampanaProspecto.query.filter_by(campana=campana_nombre).count()
    rows  = (WaCampanaProspecto.query
             .filter_by(campana=campana_nombre)
             .order_by(WaCampanaProspecto.fecha_envio.desc())
             .offset((page - 1) * limit)
             .limit(limit)
             .all())

    return jsonify({
        'ok':      True,
        'campana': campana_nombre,
        'total':   total,
        'page':    page,
        'items':   [r.to_dict() for r in rows],
    })
