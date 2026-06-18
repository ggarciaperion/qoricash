"""
Centro de Inteligencia Comercial IA — /inteligencia
Blueprint principal del sistema de inteligencia automática de QoriCash.
"""
import os
import logging
from datetime import datetime, timedelta
from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from sqlalchemy import func, desc
from app.extensions import db
from app.utils.decorators import require_role
from app.utils.formatters import now_peru

logger = logging.getLogger(__name__)

inteligencia_bp = Blueprint("inteligencia", __name__, url_prefix="/inteligencia")

CRM_API_KEY = os.environ.get("CRM_API_KEY", "qoricash_crm_2026")

# ── Dashboard principal ────────────────────────────────────────────────────────

@inteligencia_bp.route("/")
@login_required
@require_role("Master", "Presidente de Negocios")
def dashboard():
    from app.models.inteligencia import EmailEvento, Oportunidad, EjecucionMotor

    hoy   = now_peru().date()
    ayer  = hoy - timedelta(days=1)
    sem   = hoy - timedelta(days=7)

    # ── Métricas de hoy ───────────────────────────────────────────────────────
    q_hoy = EmailEvento.query.filter(func.date(EmailEvento.procesado_en) == hoy)
    stats_hoy = {
        "correos":        q_hoy.count(),
        "rebotes":        q_hoy.filter(EmailEvento.tipo == "bounce").count(),
        "oportunidades":  Oportunidad.query.filter(func.date(Oportunidad.detectado_en) == hoy).count(),
        "actualizaciones": q_hoy.filter(EmailEvento.tipo.in_(["email_cambio", "auto_reply"])).count(),
        "no_contactar":   q_hoy.filter(EmailEvento.tipo == "no_contactar").count(),
        "ia_usada":       q_hoy.filter(EmailEvento.ia_usada == True).count(),
    }

    # ── Oportunidades recientes (últimos 7 días) ───────────────────────────────
    opps = (Oportunidad.query
            .filter(Oportunidad.detectado_en >= sem)
            .order_by(desc(Oportunidad.score), desc(Oportunidad.detectado_en))
            .limit(20).all())

    # ── Emails inválidos recientes ─────────────────────────────────────────────
    invalidos = (EmailEvento.query
                 .filter(EmailEvento.tipo == "bounce",
                         EmailEvento.procesado_en >= datetime.combine(sem, datetime.min.time()))
                 .order_by(desc(EmailEvento.procesado_en))
                 .limit(30).all())

    # ── Actividad IA ──────────────────────────────────────────────────────────
    ia_eventos = (EmailEvento.query
                  .filter(EmailEvento.ia_usada == True,
                          EmailEvento.procesado_en >= datetime.combine(sem, datetime.min.time()))
                  .order_by(desc(EmailEvento.procesado_en))
                  .limit(20).all())

    # ── Últimas ejecuciones de motores ────────────────────────────────────────
    ejecuciones = (EjecucionMotor.query
                   .order_by(desc(EjecucionMotor.inicio))
                   .limit(10).all())

    # ── Tokens IA acumulados (mes actual) ─────────────────────────────────────
    mes_inicio = hoy.replace(day=1)
    tokens_mes = db.session.query(
        func.coalesce(func.sum(EjecucionMotor.ia_tokens), 0),
        func.coalesce(func.sum(EjecucionMotor.ia_costo_usd), 0.0),
    ).filter(func.date(EjecucionMotor.inicio) >= mes_inicio).first()

    # ── Oportunidades por prioridad ────────────────────────────────────────────
    prioridades = {
        "alta":  Oportunidad.query.filter(Oportunidad.prioridad == "alta",
                                          Oportunidad.estado == "nuevo").count(),
        "media": Oportunidad.query.filter(Oportunidad.prioridad == "media",
                                          Oportunidad.estado == "nuevo").count(),
        "baja":  Oportunidad.query.filter(Oportunidad.prioridad == "baja",
                                          Oportunidad.estado == "nuevo").count(),
    }

    return render_template("inteligencia/dashboard.html",
        stats_hoy    = stats_hoy,
        opps         = opps,
        invalidos    = invalidos,
        ia_eventos   = ia_eventos,
        ejecuciones  = ejecuciones,
        tokens_mes   = int(tokens_mes[0]) if tokens_mes else 0,
        costo_mes    = round(float(tokens_mes[1]) if tokens_mes else 0, 4),
        prioridades  = prioridades,
    )


# ── API — Stats para polling ───────────────────────────────────────────────────

@inteligencia_bp.route("/api/stats")
@login_required
@require_role("Master", "Presidente de Negocios")
def api_stats():
    from app.models.inteligencia import EmailEvento, Oportunidad, EjecucionMotor
    hoy = now_peru().date()
    q   = EmailEvento.query.filter(func.date(EmailEvento.procesado_en) == hoy)
    return jsonify({
        "correos":        q.count(),
        "rebotes":        q.filter(EmailEvento.tipo == "bounce").count(),
        "oportunidades":  Oportunidad.query.filter(
                              func.date(Oportunidad.detectado_en) == hoy).count(),
        "alta_prioridad": Oportunidad.query.filter(
                              Oportunidad.prioridad == "alta",
                              Oportunidad.estado == "nuevo").count(),
        "ultima_ejecucion": (EjecucionMotor.query
                             .order_by(desc(EjecucionMotor.inicio))
                             .with_entities(EjecucionMotor.inicio, EjecucionMotor.motor)
                             .first() or [None, None])[0],
    })


# ── API — Oportunidades ────────────────────────────────────────────────────────

@inteligencia_bp.route("/api/oportunidades")
@login_required
@require_role("Master", "Presidente de Negocios")
def api_oportunidades():
    from app.models.inteligencia import Oportunidad
    page     = request.args.get("page", 1, type=int)
    estado   = request.args.get("estado", "nuevo")
    prioridad = request.args.get("prioridad", "")
    q = Oportunidad.query
    if estado:
        q = q.filter(Oportunidad.estado == estado)
    if prioridad:
        q = q.filter(Oportunidad.prioridad == prioridad)
    opps = q.order_by(desc(Oportunidad.score), desc(Oportunidad.detectado_en)).paginate(
        page=page, per_page=20, error_out=False)
    return jsonify({
        "ok":    True,
        "total": opps.total,
        "items": [o.to_dict() for o in opps.items],
    })


@inteligencia_bp.route("/api/oportunidades/<int:oid>/estado", methods=["PATCH"])
@login_required
@require_role("Master", "Presidente de Negocios")
def api_opp_estado(oid):
    from app.models.inteligencia import Oportunidad
    opp = db.get_or_404(Oportunidad, oid)
    data = request.get_json(silent=True) or {}
    nuevo = data.get("estado", "").strip()
    if nuevo not in ("nuevo", "en_seguimiento", "convertido", "descartado"):
        return jsonify({"ok": False, "error": "estado inválido"}), 400
    opp.estado = nuevo
    db.session.commit()
    return jsonify({"ok": True, "estado": nuevo})


# ── API INTERNA — recibe datos de los motores locales ─────────────────────────

def _auth_motor():
    """Verifica API key del motor."""
    return request.headers.get("X-API-Key", "") == CRM_API_KEY


@inteligencia_bp.route("/api/motor/evento", methods=["POST"])
def api_motor_evento():
    """Motor → Flask: registra un email procesado."""
    if not _auth_motor():
        return jsonify({"ok": False}), 401
    from app.models.inteligencia import EmailEvento
    data = request.get_json(silent=True) or {}
    try:
        ev = EmailEvento(
            cuenta         = data.get("cuenta", ""),
            mensaje_id     = data.get("mensaje_id"),
            remitente      = data.get("remitente", "")[:300],
            asunto         = data.get("asunto", "")[:500],
            tipo           = data.get("tipo", ""),
            confianza      = float(data.get("confianza", 1.0)),
            ia_usada       = bool(data.get("ia_usada", False)),
            ia_tokens      = int(data.get("ia_tokens", 0)),
            accion         = data.get("accion", "")[:300],
            email_afectado = data.get("email_afectado", "")[:200],
            email_nuevo    = data.get("email_nuevo", "")[:200],
            sheets_tab     = data.get("sheets_tab", ""),
            crm_updated    = bool(data.get("crm_updated", False)),
            sheets_updated = bool(data.get("sheets_updated", False)),
        )
        db.session.add(ev)
        db.session.commit()
        return jsonify({"ok": True, "id": ev.id})
    except Exception as e:
        db.session.rollback()
        logger.error(f"[Inteligencia] api_motor_evento error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@inteligencia_bp.route("/api/motor/oportunidad", methods=["POST"])
def api_motor_oportunidad():
    """Motor → Flask: registra una oportunidad detectada por IA."""
    if not _auth_motor():
        return jsonify({"ok": False}), 401
    from app.models.inteligencia import Oportunidad
    from app.models.notification import Notification
    from app.models.user import User
    data = request.get_json(silent=True) or {}
    try:
        opp = Oportunidad(
            empresa         = data.get("empresa", "")[:300],
            contacto        = data.get("contacto", "")[:200],
            cargo           = data.get("cargo", "")[:150],
            email           = data.get("email", "")[:200],
            telefono        = data.get("telefono", "")[:100],
            sector          = data.get("sector", "")[:100],
            prioridad       = data.get("prioridad", "baja"),
            score           = int(data.get("score", 0)),
            volumen_usd_est = int(data.get("volumen_usd_est", 0)),
            necesidad       = data.get("necesidad", ""),
            recomendacion   = data.get("recomendacion", ""),
            cuerpo_email    = data.get("cuerpo_email", "")[:2000],
            cuenta_origen   = data.get("cuenta_origen", ""),
            mensaje_id      = data.get("mensaje_id", ""),
        )
        db.session.add(opp)
        db.session.flush()

        # Notificación interna para Master / Presidente
        emoji   = "🔴" if opp.prioridad == "alta" else "🟡" if opp.prioridad == "media" else "⚪"
        titulo  = f"{emoji} Oportunidad {opp.prioridad.upper()}: {opp.empresa or opp.email}"
        mensaje = f"Score {opp.score}/100 · {opp.necesidad[:120] if opp.necesidad else ''}"
        Notification.create_for_roles(
            ["Master", "Presidente de Negocios"],
            title=titulo, message=mensaje,
            notif_type="danger" if opp.prioridad == "alta" else "warning",
            category="inteligencia",
            link="/inteligencia/",
        )
        db.session.commit()
        return jsonify({"ok": True, "id": opp.id, "prioridad": opp.prioridad})
    except Exception as e:
        db.session.rollback()
        logger.error(f"[Inteligencia] api_motor_oportunidad error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@inteligencia_bp.route("/api/motor/ejecucion", methods=["POST"])
def api_motor_ejecucion():
    """Motor → Flask: registra el resumen de una ejecución completa."""
    if not _auth_motor():
        return jsonify({"ok": False}), 401
    from app.models.inteligencia import EjecucionMotor
    data = request.get_json(silent=True) or {}
    try:
        inicio_str = data.get("inicio")
        fin_str    = data.get("fin")
        inicio = datetime.fromisoformat(inicio_str) if inicio_str else now_peru()
        fin    = datetime.fromisoformat(fin_str)    if fin_str    else now_peru()
        ej = EjecucionMotor(
            motor              = data.get("motor", "comercial"),
            inicio             = inicio,
            fin                = fin,
            duracion_seg       = (fin - inicio).total_seconds(),
            correos_analizados = int(data.get("correos_analizados", 0)),
            rebotes            = int(data.get("rebotes", 0)),
            oportunidades      = int(data.get("oportunidades", 0)),
            actualizaciones    = int(data.get("actualizaciones", 0)),
            no_contactar       = int(data.get("no_contactar", 0)),
            ia_tokens          = int(data.get("ia_tokens", 0)),
            ia_costo_usd       = float(data.get("ia_costo_usd", 0.0)),
            errores            = int(data.get("errores", 0)),
            estado             = data.get("estado", "ok"),
            resumen            = data.get("resumen", ""),
        )
        db.session.add(ej)
        db.session.commit()
        return jsonify({"ok": True, "id": ej.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500


# ── API — Historial de ejecuciones ────────────────────────────────────────────

@inteligencia_bp.route("/api/ejecuciones")
@login_required
@require_role("Master", "Presidente de Negocios")
def api_ejecuciones():
    from app.models.inteligencia import EjecucionMotor
    rows = (EjecucionMotor.query
            .order_by(desc(EjecucionMotor.inicio))
            .limit(50).all())
    return jsonify({"ok": True, "items": [r.to_dict() for r in rows]})
