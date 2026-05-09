"""
Modulo de Prospeccion — QoriCash Trading V2
Rutas para Master y Trader.
"""
import os, json, base64, threading
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from sqlalchemy import or_, func
from app.extensions import db, csrf
from app.models.prospecto import Prospecto, AsignacionProspecto, ActividadProspecto
from app.models.user import User
from app.utils.decorators import require_role
from app.utils.formatters import now_peru

# Credenciales OAuth2 compartidas — se leen de variables de entorno de Render
# GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET
_GMAIL_TOKEN_URI = "https://oauth2.googleapis.com/token"
_GMAIL_SCOPES    = ["https://mail.google.com/"]

# Mapeo email → variable de entorno que contiene SOLO el refresh_token (string simple)
_GMAIL_REFRESH_ENV = {
    "ggarcia@qoricash.pe":  "GMAIL_REFRESH_TOKEN_GGARCIA",
    "gerencia@qoricash.pe": "GMAIL_REFRESH_TOKEN_GERENCIA",
    "luacosta@qoricash.pe": "GMAIL_REFRESH_TOKEN_LUACOSTA",
}

# Mapeo email → nombre completo para el cuerpo del correo
_TRADER_NOMBRES = {
    "ggarcia@qoricash.pe":  "Gian Garcia",
    "gerencia@qoricash.pe": "Gian Garcia",
    "luacosta@qoricash.pe": "Luciana Acosta",
}

# Emails que usan cargo "Presidente de Negocios"
_EMAILS_PRESIDENTE = {"ggarcia@qoricash.pe", "gerencia@qoricash.pe"}

# Estado de campañas masivas activas: trader_id → dict
_campanas: dict = {}
_campanas_lock  = threading.Lock()


def _get_trader_info(sender_email: str, role: str = "Trader"):
    """Retorna (nombre_completo, cargo) para el remitente."""
    es_pres         = (role == "Master" or sender_email in _EMAILS_PRESIDENTE)
    nombre_completo = _TRADER_NOMBRES.get(sender_email, sender_email.split("@")[0])
    cargo           = "Presidente de Negocios" if es_pres else "Trader Fx"
    return nombre_completo, cargo


def _get_gmail_service(sender_email):
    """Construye y retorna el servicio Gmail API para el remitente."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    env_key       = _GMAIL_REFRESH_ENV.get(sender_email.lower())
    refresh_token = os.environ.get(env_key, "").strip() if env_key else ""
    if not refresh_token:
        raise ValueError(f"Refresh token no configurado para {sender_email} (var: {env_key})")

    client_id     = os.environ.get("GMAIL_CLIENT_ID", "")
    client_secret = os.environ.get("GMAIL_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise ValueError("GMAIL_CLIENT_ID o GMAIL_CLIENT_SECRET no configurados en Render")

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=_GMAIL_TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
        scopes=_GMAIL_SCOPES,
    )
    creds.refresh(Request())
    return build("gmail", "v1", credentials=creds)


def _get_firma_gmail(sender_email):
    """Obtiene la firma HTML real de la cuenta Gmail del remitente. Retorna '' si falla."""
    try:
        service = _get_gmail_service(sender_email)
        result  = service.users().settings().sendAs().list(userId="me").execute()
        for alias in result.get("sendAs", []):
            if alias.get("isDefault"):
                return alias.get("signature", "")
        sendas = result.get("sendAs", [])
        if sendas:
            return sendas[0].get("signature", "")
    except Exception:
        pass
    return ""


def _send_via_gmail_api(sender_email, to_email, subject, html_body):
    """Envía un correo usando Gmail API con OAuth2. El email queda en Enviados del remitente."""
    service = _get_gmail_service(sender_email)

    msg = MIMEMultipart("alternative")
    msg["To"]      = to_email
    msg["From"]    = sender_email
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()

prospeccion_bp = Blueprint("prospeccion", __name__, url_prefix="/prospeccion")

DIAS_VIGENCIA = 45  # días de vigencia de un prospecto asignado a un trader

GRUPOS_ORDEN = [
    "PIPELINE ACTIVO", "CLIENTES LFC", "PRIORITARIOS",
    "CALIFICADOS", "POR CONTACTAR", "UNIVERSO CONTACTADOS",
    "SOFT BOUNCE", "NO CONTACTAR",
]


def _base_query():
    """Retorna query filtrada segun rol: Master ve todo, Trader solo los suyos."""
    q = Prospecto.query
    if current_user.role == "Trader":
        q = (q.join(AsignacionProspecto,
                    AsignacionProspecto.prospecto_id == Prospecto.id)
               .filter(AsignacionProspecto.trader_id == current_user.id,
                       AsignacionProspecto.activo == True))
    return q


# ── Dashboard prospeccion ─────────────────────────────────────────────────────

@prospeccion_bp.route("/")
@login_required
@require_role("Master", "Trader")
def dashboard():
    q = _base_query()
    total        = q.filter(Prospecto.estado_comercial != "cliente").count()
    en_seguim    = q.filter(Prospecto.estado_comercial.in_(["seguimiento","P1","P2"])).count()
    en_negoc     = q.filter(Prospecto.estado_comercial.in_(["negociacion","P3"])).count()
    clientes     = q.filter(Prospecto.estado_comercial.in_(["cliente","P4"])).count()
    lfc          = q.filter(Prospecto.cliente_lfc == "Cliente LFC").count()

    # Top 5 rubros
    top_rubros = (db.session.query(Prospecto.rubro, func.count(Prospecto.id))
                  .filter(Prospecto.rubro.isnot(None))
                  .group_by(Prospecto.rubro)
                  .order_by(func.count(Prospecto.id).desc())
                  .limit(5).all())

    # Mis ultimas actividades
    actividades = (ActividadProspecto.query
                   .filter_by(user_id=current_user.id)
                   .order_by(ActividadProspecto.creado_en.desc())
                   .limit(8).all())

    # Solo Master: resumen por trader + prospectos vencidos
    traders_stats      = []
    traders_disponibles = []
    vencidos            = []

    if current_user.role == "Master":
        traders = User.query.filter(User.role == "Trader", User.status == "Activo").all()
        traders_disponibles = traders
        for t in traders:
            count = (AsignacionProspecto.query
                     .filter_by(trader_id=t.id, activo=True).count())
            traders_stats.append({"trader": t, "asignados": count})

        # Prospectos vencidos: asignados hace >DIAS_VIGENCIA días SIN actividad reciente
        fecha_corte = now_peru() - timedelta(days=DIAS_VIGENCIA)
        hoy = now_peru().date()
        rows = (db.session.query(Prospecto, AsignacionProspecto, User)
                .join(AsignacionProspecto, AsignacionProspecto.prospecto_id == Prospecto.id)
                .join(User, User.id == AsignacionProspecto.trader_id)
                .filter(
                    AsignacionProspecto.activo == True,
                    Prospecto.estado_comercial.notin_(["cliente", "P4"]),
                    Prospecto.actualizado_en < fecha_corte,
                    AsignacionProspecto.asignado_en < fecha_corte,
                )
                .order_by(Prospecto.actualizado_en.asc())
                .limit(150).all())

        for p, asig, trader in rows:
            base = asig.asignado_en.date()
            if p.actualizado_en and p.actualizado_en.date() > base:
                base = p.actualizado_en.date()
            vencidos.append({
                "p":       p,
                "trader":  trader,
                "dias_sin": (hoy - base).days,
            })

    return render_template(
        "prospeccion/dashboard.html",
        total=total, en_seguim=en_seguim, clientes=clientes,
        en_negoc=en_negoc, lfc=lfc,
        top_rubros=top_rubros,
        actividades=actividades,
        traders_stats=traders_stats,
        traders_disponibles=traders_disponibles,
        vencidos=vencidos,
        dias_vigencia=DIAS_VIGENCIA,
    )


# ── Lista de prospectos ───────────────────────────────────────────────────────

@prospeccion_bp.route("/lista")
@login_required
@require_role("Master", "Trader")
def lista():
    tab    = request.args.get("tab", "todos")       # todos | seguimiento | negociacion
    depto  = request.args.get("depto", "")
    q_str  = request.args.get("q", "")
    page   = request.args.get("page", 1, type=int)

    if tab == "clientes":
        query = _base_query().filter(Prospecto.estado_comercial.in_(["cliente", "P4"]))
    else:
        query = _base_query().filter(Prospecto.estado_comercial.notin_(["cliente", "P4"]))

    # Filtro por pestaña
    if tab == "seguimiento":
        query = query.filter(Prospecto.estado_comercial.in_(["seguimiento", "P1"]))
    elif tab == "negociacion":
        query = query.filter(Prospecto.estado_comercial.in_(["negociacion", "P2", "P3"]))

    if depto:
        query = query.filter(Prospecto.departamento.ilike(f"%{depto}%"))
    if q_str:
        like = f"%{q_str}%"
        query = query.filter(or_(
            Prospecto.razon_social.ilike(like),
            Prospecto.email.ilike(like),
            Prospecto.nombre_contacto.ilike(like),
            Prospecto.ruc.ilike(like),
        ))

    if tab == "seguimiento":
        order = Prospecto.actualizado_en.desc()
    else:
        order = Prospecto.score.desc()
    prospectos = query.order_by(order).paginate(page=page, per_page=50, error_out=False)
    deptos = [d[0] for d in db.session.query(Prospecto.departamento).distinct().order_by(Prospecto.departamento).all() if d[0]]

    # Conteos para las pestañas
    base = _base_query()
    cnt_todos       = base.filter(Prospecto.estado_comercial.notin_(["cliente","P4"])).count()
    cnt_seguimiento = base.filter(Prospecto.estado_comercial.in_(["seguimiento","P1"])).count()
    cnt_negociacion = base.filter(Prospecto.estado_comercial.in_(["negociacion","P2","P3"])).count()
    cnt_clientes    = base.filter(Prospecto.estado_comercial.in_(["cliente","P4"])).count()

    # Vigencia por prospecto (días restantes hasta vencimiento de asignación)
    hoy   = now_peru().date()
    pids  = [p.id for p in prospectos.items]
    asigs = (AsignacionProspecto.query
             .filter(AsignacionProspecto.prospecto_id.in_(pids),
                     AsignacionProspecto.activo == True)
             .all())
    asig_by_pid = {a.prospecto_id: a for a in asigs}

    vigencia_map = {}
    for p in prospectos.items:
        asig = asig_by_pid.get(p.id)
        if not asig:
            continue
        base_date = asig.asignado_en.date()
        if p.actualizado_en and p.actualizado_en.date() > base_date:
            base_date = p.actualizado_en.date()
        vigencia_map[p.id] = DIAS_VIGENCIA - (hoy - base_date).days

    return render_template(
        "prospeccion/lista.html",
        prospectos=prospectos,
        deptos=deptos,
        tab=tab,
        filtros={"depto": depto, "q": q_str, "tab": tab},
        cnt_todos=cnt_todos,
        cnt_seguimiento=cnt_seguimiento,
        cnt_negociacion=cnt_negociacion,
        cnt_clientes=cnt_clientes,
        vigencia_map=vigencia_map,
        dias_vigencia=DIAS_VIGENCIA,
    )


# ── Detalle de prospecto ──────────────────────────────────────────────────────

@prospeccion_bp.route("/<int:pid>")
@login_required
@require_role("Master", "Trader")
def detalle(pid):
    p = Prospecto.query.get_or_404(pid)
    _verificar_acceso(p)
    actividades = p.actividades.limit(30).all()

    traders_disponibles = []
    if current_user.role == "Master":
        traders_disponibles = User.query.filter_by(role="Trader", status="Activo").all()

    asignacion_actual  = p.asignaciones.filter_by(activo=True).first()
    historial_traders  = (p.asignaciones
                          .filter_by(activo=False)
                          .order_by(AsignacionProspecto.asignado_en.desc())
                          .all())

    # Vigencia para Trader
    vigencia_dias = None
    if current_user.role == "Trader" and asignacion_actual:
        hoy       = now_peru().date()
        base_date = asignacion_actual.asignado_en.date()
        if p.actualizado_en and p.actualizado_en.date() > base_date:
            base_date = p.actualizado_en.date()
        vigencia_dias = DIAS_VIGENCIA - (hoy - base_date).days

    return render_template(
        "prospeccion/detalle.html",
        p=p, actividades=actividades,
        traders_disponibles=traders_disponibles,
        asignacion_actual=asignacion_actual,
        historial_traders=historial_traders,
        vigencia_dias=vigencia_dias,
        dias_vigencia=DIAS_VIGENCIA,
    )


# ── Registrar actividad ───────────────────────────────────────────────────────

@prospeccion_bp.route("/<int:pid>/actividad", methods=["POST"])
@login_required
@require_role("Master", "Trader")
def agregar_actividad(pid):
    p = Prospecto.query.get_or_404(pid)
    _verificar_acceso(p)

    tipo        = request.form.get("tipo", "nota")
    descripcion = request.form.get("descripcion", "").strip()
    resultado   = request.form.get("resultado", "").strip()
    nuevo_est   = request.form.get("nuevo_estado", "").strip()
    fecha_prox  = request.form.get("fecha_proximo_contacto", "").strip()

    if not descripcion:
        flash("La descripcion es requerida.", "warning")
        return redirect(url_for("prospeccion.detalle", pid=pid))

    act = ActividadProspecto(
        prospecto_id=p.id,
        user_id=current_user.id,
        tipo=tipo,
        descripcion=descripcion,
        resultado=resultado or None,
        nuevo_estado=nuevo_est or None,
    )
    db.session.add(act)

    p.fecha_ultimo_contacto = now_peru().strftime("%Y-%m-%d %H:%M")
    if nuevo_est:
        p.estado_comercial = nuevo_est
    if fecha_prox:
        p.fecha_proximo_contacto = fecha_prox

    db.session.commit()
    flash("Actividad registrada correctamente.", "success")
    return redirect(url_for("prospeccion.detalle", pid=pid))


# ── Editar prospecto ──────────────────────────────────────────────────────────

@prospeccion_bp.route("/<int:pid>/editar", methods=["GET", "POST"])
@login_required
@require_role("Master")
def editar(pid):
    p = Prospecto.query.get_or_404(pid)
    _verificar_acceso(p)

    if request.method == "POST":
        campos = [
            "razon_social", "ruc", "tipo", "rubro", "departamento", "provincia",
            "nombre_contacto", "cargo", "email", "email_alt", "telefono",
            "cliente_lfc", "canal", "fuente", "remitente",
            "fecha_proximo_contacto", "estado_comercial", "nivel_interes",
            "grupo", "notas",
        ]
        for campo in campos:
            val = request.form.get(campo)
            if val is not None:
                setattr(p, campo, val.strip() or None)

        db.session.commit()
        flash("Registro actualizado.", "success")
        return redirect(url_for("prospeccion.detalle", pid=pid))

    return render_template("prospeccion/editar.html", p=p, grupos=GRUPOS_ORDEN)


# ── Asignar trader (solo Master) ──────────────────────────────────────────────

@prospeccion_bp.route("/<int:pid>/asignar", methods=["POST"])
@login_required
@require_role("Master")
def asignar(pid):
    p          = Prospecto.query.get_or_404(pid)
    trader_id  = request.form.get("trader_id", type=int)

    if not trader_id:
        # Quitar asignacion
        p.asignaciones.filter_by(activo=True).update({"activo": False})
        db.session.commit()
        flash("Asignacion eliminada.", "info")
        return redirect(url_for("prospeccion.detalle", pid=pid))

    trader = User.query.get_or_404(trader_id)

    # Desactivar asignacion anterior
    p.asignaciones.filter_by(activo=True).update({"activo": False})

    # Buscar si ya existe (inactiva)
    existente = AsignacionProspecto.query.filter_by(
        prospecto_id=pid, trader_id=trader_id
    ).first()
    if existente:
        existente.activo       = True
        existente.asignado_por = current_user.id
        existente.asignado_en  = now_peru()
    else:
        nueva = AsignacionProspecto(
            prospecto_id=pid,
            trader_id=trader_id,
            asignado_por=current_user.id,
        )
        db.session.add(nueva)

    db.session.commit()
    flash(f"Prospecto asignado a {trader.username}.", "success")
    return redirect(url_for("prospeccion.detalle", pid=pid))


# ── Asignacion masiva (solo Master) ──────────────────────────────────────────

@prospeccion_bp.route("/asignar-masivo", methods=["GET", "POST"])
@login_required
@require_role("Master")
def asignar_masivo():
    traders = User.query.filter_by(role="Trader", status="Activo").all()

    if request.method == "POST":
        trader_id  = request.form.get("trader_id", type=int)
        grupo      = request.form.get("grupo", "")
        cantidad   = request.form.get("cantidad", 50, type=int)

        if not trader_id or not grupo:
            flash("Selecciona trader y segmento.", "warning")
            return redirect(url_for("prospeccion.asignar_masivo"))

        # Prospectos sin asignacion activa del grupo seleccionado
        ya_asignados = db.session.query(AsignacionProspecto.prospecto_id).filter_by(activo=True)
        sin_asignar  = (Prospecto.query
                        .filter(Prospecto.grupo == grupo)
                        .filter(~Prospecto.id.in_(ya_asignados))
                        .filter(Prospecto.grupo != "NO CONTACTAR")
                        .order_by(Prospecto.score.desc())
                        .limit(cantidad).all())

        asignados = 0
        for prosp in sin_asignar:
            nueva = AsignacionProspecto(
                prospecto_id=prosp.id,
                trader_id=trader_id,
                asignado_por=current_user.id,
            )
            db.session.add(nueva)
            asignados += 1

        db.session.commit()
        flash(f"{asignados} prospectos asignados a {User.query.get(trader_id).username}.", "success")
        return redirect(url_for("prospeccion.asignar_masivo"))

    # Conteo por grupo sin asignar
    ya_asignados = db.session.query(AsignacionProspecto.prospecto_id).filter_by(activo=True)
    grupos_count = (db.session.query(Prospecto.grupo, func.count(Prospecto.id))
                    .filter(~Prospecto.id.in_(ya_asignados))
                    .filter(Prospecto.grupo != "NO CONTACTAR")
                    .group_by(Prospecto.grupo)
                    .order_by(func.count(Prospecto.id).desc()).all())

    return render_template("prospeccion/asignar_masivo.html",
                           traders=traders, grupos_count=grupos_count)


# ── Pipeline kanban ───────────────────────────────────────────────────────────

@prospeccion_bp.route("/pipeline")
@login_required
@require_role("Master", "Trader")
def pipeline():
    base = _base_query()
    columnas = {}
    config = [
        ("P1", "Presentacion enviada", "secondary"),
        ("P2", "Precio enviado",       "info"),
        ("P3", "En negociacion",       "warning"),
        ("P4", "Cliente cerrado",      "success"),
    ]
    for estado, label, color in config:
        items = base.filter(Prospecto.estado_comercial == estado).order_by(Prospecto.score.desc()).all()
        columnas[estado] = {"label": label, "color": color, "items": items}

    return render_template("prospeccion/pipeline.html", columnas=columnas)


@prospeccion_bp.route("/<int:pid>/mover", methods=["POST"])
@login_required
@require_role("Master", "Trader")
def mover_pipeline(pid):
    p = Prospecto.query.get_or_404(pid)
    _verificar_acceso(p)
    nuevo = request.form.get("estado")
    if nuevo in ("P1", "P2", "P3", "P4"):
        p.estado_comercial = nuevo
        db.session.commit()
    return redirect(request.referrer or url_for("prospeccion.pipeline"))


# ── No contactar ─────────────────────────────────────────────────────────────

@prospeccion_bp.route("/no-contactar")
@login_required
@require_role("Master")
def no_contactar():
    lista = (Prospecto.query
             .filter(Prospecto.grupo == "NO CONTACTAR")
             .order_by(Prospecto.razon_social).all())
    return render_template("prospeccion/no_contactar.html", lista=lista)


# ── API JSON (para charts del dashboard) ─────────────────────────────────────

@prospeccion_bp.route("/api/charts/grupos")
@login_required
@require_role("Master", "Trader")
def api_grupos():
    q = _base_query()
    rows = (db.session.query(Prospecto.grupo, func.count(Prospecto.id))
            .filter(Prospecto.id.in_(q.with_entities(Prospecto.id)))
            .group_by(Prospecto.grupo).all())
    colores = {
        "PIPELINE ACTIVO": "#8B5CF6", "CLIENTES LFC": "#22C55E",
        "PRIORITARIOS": "#B91C1C",    "CALIFICADOS": "#3B82F6",
        "POR CONTACTAR": "#0891B1",   "UNIVERSO CONTACTADOS": "#F59E0B",
        "SOFT BOUNCE": "#D97706",     "NO CONTACTAR": "#EF4444",
    }
    return jsonify([{"label": r[0] or "Sin grupo", "value": r[1],
                     "color": colores.get(r[0], "#94A3B8")} for r in rows])


@prospeccion_bp.route("/api/charts/rubros")
@login_required
@require_role("Master", "Trader")
def api_rubros():
    q = _base_query()
    rows = (db.session.query(Prospecto.rubro, func.count(Prospecto.id))
            .filter(Prospecto.id.in_(q.with_entities(Prospecto.id)))
            .filter(Prospecto.rubro.isnot(None))
            .group_by(Prospecto.rubro)
            .order_by(func.count(Prospecto.id).desc())
            .limit(10).all())
    return jsonify([{"rubro": r[0], "total": r[1]} for r in rows])


# ── Import masivo via HTTP (endpoint temporal para carga inicial) ─────────────

@prospeccion_bp.route("/api/sincronizar-enviados", methods=["POST"])
@csrf.exempt
def sincronizar_enviados():
    """Marca como 'seguimiento' todos los prospectos cuyo email aparece en la lista."""
    import os
    key = request.headers.get("X-Import-Key", "")
    if key != os.environ.get("PROSPECCION_IMPORT_KEY", "qc-import-prospectos-2026"):
        return jsonify({"error": "No autorizado"}), 401

    emails = request.get_json(force=True).get("emails", [])
    if not emails:
        return jsonify({"actualizados": 0, "no_encontrados": 0})

    emails_lower = [e.strip().lower() for e in emails if e and "@" in e]
    actualizados = 0
    no_encontrados = 0

    for email in emails_lower:
        p = Prospecto.query.filter(
            db.func.lower(Prospecto.email) == email,
            Prospecto.estado_comercial.notin_(["seguimiento","negociacion","cliente","P1","P2","P3","P4"])
        ).first()
        if p:
            p.estado_comercial = "seguimiento"
            actualizados += 1
        else:
            no_encontrados += 1

    db.session.commit()
    return jsonify({"actualizados": actualizados, "no_encontrados": no_encontrados})


@prospeccion_bp.route("/api/import-batch", methods=["POST"])
@csrf.exempt
def import_batch():
    """
    Endpoint temporal para cargar los 11K prospectos desde el Mac.
    Protegido por API key en header X-Import-Key.
    """
    import os
    key = request.headers.get("X-Import-Key", "")
    if key != os.environ.get("PROSPECCION_IMPORT_KEY", "qc-import-prospectos-2026"):
        return jsonify({"error": "No autorizado"}), 401

    data = request.get_json(force=True)
    action = data.get("action", "insert")

    if action == "truncate":
        Prospecto.query.delete()
        db.session.commit()
        return jsonify({"ok": True, "msg": "Tabla limpiada"})

    if action == "count":
        return jsonify({"total": Prospecto.query.count()})

    registros = data.get("registros", [])
    if not registros:
        return jsonify({"ok": True, "insertados": 0})

    objs = [Prospecto(**r) for r in registros]
    db.session.bulk_save_objects(objs)
    db.session.commit()
    return jsonify({"ok": True, "insertados": len(objs)})


@prospeccion_bp.route("/api/asignar-por-remitente", methods=["POST"])
@csrf.exempt
def asignar_por_remitente():
    """
    Asigna prospectos a usuarios segun el campo 'remitente'.
    Payload: {"remitente": "ggarcia", "email_usuario": "ggarcia@qoricash.pe"}
    O accion "preview" para ver cuantos se asignarian.
    """
    import os
    key = request.headers.get("X-Import-Key", "")
    if key != os.environ.get("PROSPECCION_IMPORT_KEY", "qc-import-prospectos-2026"):
        return jsonify({"error": "No autorizado"}), 401

    data          = request.get_json(force=True)
    remitente     = data.get("remitente", "").strip().lower()
    email_usuario = data.get("email_usuario", "").strip().lower()
    accion        = data.get("accion", "asignar")

    if not remitente or not email_usuario:
        return jsonify({"error": "remitente y email_usuario son requeridos"}), 400

    # Buscar usuario por email
    usuario = User.query.filter(
        db.func.lower(User.email) == email_usuario
    ).first()
    if not usuario:
        # Intentar por username
        usuario = User.query.filter(
            db.func.lower(User.username) == remitente
        ).first()
    if not usuario:
        usuarios_disponibles = [
            {"id": u.id, "username": u.username, "email": u.email, "role": u.role}
            for u in User.query.filter(User.role.in_(["Master", "Trader"])).all()
        ]
        return jsonify({
            "error": f"No se encontro usuario con email '{email_usuario}'",
            "usuarios_disponibles": usuarios_disponibles
        }), 404

    # Buscar prospectos con ese remitente
    prospectos = Prospecto.query.filter(
        db.func.lower(Prospecto.remitente) == remitente
    ).all()

    if accion == "preview":
        ya_asignados = sum(
            1 for p in prospectos
            if p.asignaciones.filter_by(trader_id=usuario.id, activo=True).first()
        )
        return jsonify({
            "remitente":      remitente,
            "usuario":        {"id": usuario.id, "username": usuario.username, "email": usuario.email, "role": usuario.role},
            "total_encontrados": len(prospectos),
            "ya_asignados":   ya_asignados,
            "por_asignar":    len(prospectos) - ya_asignados,
        })

    # Asignar
    asignados = 0
    ya_tenia  = 0
    ahora     = now_peru()

    for p in prospectos:
        existente = AsignacionProspecto.query.filter_by(
            prospecto_id=p.id, trader_id=usuario.id
        ).first()
        if existente:
            if not existente.activo:
                existente.activo      = True
                existente.asignado_en = ahora
                asignados += 1
            else:
                ya_tenia += 1
        else:
            nueva = AsignacionProspecto(
                prospecto_id=p.id,
                trader_id=usuario.id,
                activo=True,
                asignado_en=ahora,
            )
            db.session.add(nueva)
            asignados += 1

        if asignados % 500 == 0:
            db.session.flush()

    db.session.commit()
    return jsonify({
        "ok":        True,
        "remitente": remitente,
        "usuario":   {"id": usuario.id, "username": usuario.username, "role": usuario.role},
        "asignados": asignados,
        "ya_tenian": ya_tenia,
        "total":     len(prospectos),
    })


# ── Enviar correo a prospecto ─────────────────────────────────────────────────

LOGO_URL = "https://www.qoricash.pe/logofirma.png"

HEADER_HTML = f"""\
<table cellpadding="0" cellspacing="0" border="0" style="margin-bottom:24px;">
  <tr>
    <td style="width:4px;min-width:4px;background:#5CB85C;border-radius:2px;">&nbsp;</td>
    <td style="padding-left:14px;">
      <img src="{LOGO_URL}" alt="QoriCash" style="height:48px;width:auto;display:block;">
      <p style="margin:6px 0 0;font-size:11px;color:#64748B;letter-spacing:0.3px;">
        Regulada por la SBS &nbsp;&middot;&nbsp; Res. N.&ordm; 00313-2026
      </p>
    </td>
  </tr>
</table>"""

FIRMA_HTML = f"""\
<table cellpadding="0" cellspacing="0" border="0"
  style="max-width:500px;width:100%;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
         border:1px solid #e5e5e5;border-radius:8px;overflow:hidden;">
  <tr>
    <td style="width:80px;min-width:80px;background:linear-gradient(135deg,#f8faf8 0%,#ffffff 100%);
               padding:16px 12px;border-right:3px solid #5CB85C;text-align:center;vertical-align:middle;">
      <img src="{LOGO_URL}" alt="QoriCash" width="56" height="56" style="display:block;margin:0 auto;">
    </td>
    <td style="padding:14px 16px;vertical-align:middle;">
      <div style="font-size:16px;font-weight:700;color:#1a1a1a;line-height:1.2;margin-bottom:3px;">
        {{trader_nombre}}
      </div>
      <div style="font-size:10px;font-weight:600;color:#5CB85C;text-transform:uppercase;
                  letter-spacing:0.5px;margin-bottom:8px;">Trader QoriCash</div>
      <div style="width:40px;height:2px;background:linear-gradient(90deg,#5CB85C,transparent);
                  margin-bottom:10px;"></div>
      <table cellpadding="0" cellspacing="0" border="0" style="margin-bottom:3px;"><tr>
        <td style="padding-right:7px;vertical-align:middle;">
          <img src="https://img.icons8.com/material-rounded/48/5CB85C/phone.png"
               width="13" height="13" alt="" style="display:block;"></td>
        <td style="vertical-align:middle;font-size:12px;color:#2c2c2c;">
          <a href="https://wa.me/51926011920" style="color:#2c2c2c;text-decoration:none;">+51 926 011 920</a>
        </td>
      </tr></table>
      <table cellpadding="0" cellspacing="0" border="0" style="margin-bottom:3px;"><tr>
        <td style="padding-right:7px;vertical-align:middle;">
          <img src="https://img.icons8.com/material-rounded/48/5CB85C/marker.png"
               width="13" height="13" alt="" style="display:block;"></td>
        <td style="vertical-align:middle;font-size:12px;color:#2c2c2c;">
          <a href="https://www.google.com/maps/search/?api=1&query=Av.+Brasil+2790,+int.+504,+Pueblo+Libre,+Lima,+Peru"
             style="color:#2c2c2c;text-decoration:none;">Av. Brasil 2790, int. 504 - Pueblo Libre</a>
        </td>
      </tr></table>
      <table cellpadding="0" cellspacing="0" border="0" style="margin-bottom:12px;"><tr>
        <td style="padding-right:7px;vertical-align:middle;">
          <img src="https://img.icons8.com/material-rounded/48/5CB85C/globe.png"
               width="13" height="13" alt="" style="display:block;"></td>
        <td style="vertical-align:middle;font-size:12px;">
          <a href="https://www.qoricash.pe/" style="color:#5CB85C;text-decoration:none;font-weight:600;">
            www.qoricash.pe</a>
        </td>
      </tr></table>
      <a href="https://qoricash.pe/"
         style="display:inline-block;padding:7px 18px;background:linear-gradient(135deg,#5CB85C 0%,#4a9b4a 100%);
                color:#ffffff;text-decoration:none;border-radius:5px;font-size:11px;font-weight:700;
                letter-spacing:0.3px;">CAMBIAR AHORA</a>
    </td>
  </tr>
</table>"""

PIE = """\
<p style="font-size:10px;color:#94A3B8;margin-top:24px;border-top:1px solid #EEF2F7;padding-top:12px;">
  Si no desea recibir m&aacute;s comunicaciones de nuestra parte, responda este correo
  con el asunto <em>&ldquo;NO CONTACTAR&rdquo;</em> y lo retiraremos de inmediato.
</p>"""

BANCOS_HTML = """\
<table cellpadding="0" cellspacing="0" border="0" width="100%"
  style="margin:0 0 24px;border:1px solid #E2E8F0;border-radius:10px;overflow:hidden;">
  <tr>
    <td colspan="3" style="padding:8px 20px;background:#ECFDF5;border-bottom:1px solid #D1FAE5;">
      <p style="margin:0;font-size:9px;color:#047857;">
        Titular: <strong>QORICASH S.A.C.</strong> &nbsp;&bull;&nbsp; RUC: <strong>20615113698</strong>
      </p>
    </td>
  </tr>
  <tr>
    <td colspan="3" style="background:#ECFDF5;padding:8px 20px;border-bottom:1px solid #D1FAE5;">
      <p style="margin:0;font-size:9px;font-weight:700;color:#059669;text-transform:uppercase;letter-spacing:1px;">
        &#9889; Transferencia inmediata
      </p>
    </td>
  </tr>
  <tr style="border-bottom:1px solid #F1F5F9;">
    <td style="width:90px;padding:12px 8px 12px 20px;vertical-align:middle;">
      <span style="font-size:14px;font-weight:800;color:#F97316;">BCP</span>
    </td>
    <td style="padding:12px 12px;vertical-align:middle;border-left:1px solid #F1F5F9;">
      <p style="margin:0;font-size:9px;color:#94A3B8;text-transform:uppercase;letter-spacing:0.5px;">Soles (PEN)</p>
      <p style="margin:2px 0 0;font-size:12px;font-weight:700;color:#0D1B2A;letter-spacing:0.3px;">1937353150041</p>
    </td>
    <td style="padding:12px 20px 12px 12px;vertical-align:middle;border-left:1px solid #F1F5F9;">
      <p style="margin:0;font-size:9px;color:#94A3B8;text-transform:uppercase;letter-spacing:0.5px;">D&oacute;lares (USD)</p>
      <p style="margin:2px 0 0;font-size:12px;font-weight:700;color:#0D1B2A;letter-spacing:0.3px;">1917357790119</p>
    </td>
  </tr>
  <tr style="border-bottom:1px solid #F1F5F9;background:#FAFAFA;">
    <td style="width:90px;padding:12px 8px 12px 20px;vertical-align:middle;">
      <span style="font-size:14px;font-weight:800;color:#00A859;">Interbank</span>
    </td>
    <td style="padding:12px 12px;vertical-align:middle;border-left:1px solid #F1F5F9;">
      <p style="margin:0;font-size:9px;color:#94A3B8;text-transform:uppercase;letter-spacing:0.5px;">Soles (PEN)</p>
      <p style="margin:2px 0 0;font-size:12px;font-weight:700;color:#0D1B2A;letter-spacing:0.3px;">200-3007757571</p>
    </td>
    <td style="padding:12px 20px 12px 12px;vertical-align:middle;border-left:1px solid #F1F5F9;">
      <p style="margin:0;font-size:9px;color:#94A3B8;text-transform:uppercase;letter-spacing:0.5px;">D&oacute;lares (USD)</p>
      <p style="margin:2px 0 0;font-size:12px;font-weight:700;color:#0D1B2A;letter-spacing:0.3px;">200-3007757589</p>
    </td>
  </tr>
  <tr>
    <td style="width:90px;padding:12px 8px 12px 20px;vertical-align:middle;">
      <span style="font-size:14px;font-weight:800;color:#004B9D;">BanBif</span>
      <p style="margin:2px 0 0;font-size:9px;color:#94A3B8;">Solo Lima</p>
    </td>
    <td style="padding:12px 12px;vertical-align:middle;border-left:1px solid #F1F5F9;">
      <p style="margin:0;font-size:9px;color:#94A3B8;text-transform:uppercase;letter-spacing:0.5px;">Soles (PEN)</p>
      <p style="margin:2px 0 0;font-size:12px;font-weight:700;color:#0D1B2A;letter-spacing:0.3px;">007000845805</p>
    </td>
    <td style="padding:12px 20px 12px 12px;vertical-align:middle;border-left:1px solid #F1F5F9;">
      <p style="margin:0;font-size:9px;color:#94A3B8;text-transform:uppercase;letter-spacing:0.5px;">D&oacute;lares (USD)</p>
      <p style="margin:2px 0 0;font-size:12px;font-weight:700;color:#0D1B2A;letter-spacing:0.3px;">007000845813</p>
    </td>
  </tr>
  <tr>
    <td colspan="3" style="background:#F8FAFC;padding:8px 20px;border-top:1px solid #E2E8F0;border-bottom:1px solid #E2E8F0;">
      <p style="margin:0;font-size:9px;font-weight:700;color:#64748B;text-transform:uppercase;letter-spacing:1px;">
        &#8646; Transferencia interbancaria &mdash; CCI (desde cualquier banco)
        &nbsp;<span style="font-size:9px;color:#94A3B8;font-weight:400;text-transform:none;letter-spacing:0;">Solo Lima</span>
      </p>
    </td>
  </tr>
  <tr>
    <td colspan="3" style="padding:12px 20px;background:#F8FAFC;">
      <table cellpadding="0" cellspacing="0" border="0"><tr>
        <td style="padding-right:20px;vertical-align:middle;">
          <span style="font-size:14px;font-weight:800;color:#004A97;">BBVA</span>
        </td>
        <td style="padding-right:20px;vertical-align:middle;">
          <span style="font-size:14px;font-weight:800;color:#EC1C24;">Scotiabank</span>
        </td>
        <td style="padding-right:20px;vertical-align:middle;">
          <span style="font-size:14px;font-weight:800;color:#B8860B;">Pichincha</span>
        </td>
        <td style="vertical-align:middle;">
          <p style="margin:0;font-size:9px;color:#94A3B8;font-style:italic;">y cualquier otro banco del Per&uacute;</p>
        </td>
      </tr></table>
    </td>
  </tr>
</table>"""

CUERPO_PRESENTACION = """\
<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;font-size:14px;color:#1E293B;line-height:1.7;max-width:620px;margin:0 auto;padding:24px;">
  {header}
  <p>Estimado(a) <strong>{nombre}</strong>,</p>
  <p style="text-align:justify;">{presentacion_remitente}</p>
  <p style="text-align:justify;">Trabajamos con empresas que realizan operaciones frecuentes de compra y venta de
    dolares, y que en muchos casos estan dejando dinero sobre la mesa al operar con el tipo de cambio que les ofrece
    su entidad financiera actual.</p>
  <p style="text-align:justify;">Porque cada centavo cuenta, le ofrecemos <strong>tasas que superan
    consistentemente al sistema bancario tradicional</strong>, con ejecucion inmediata y cero costos ocultos.
    Nuestro sistema tecnologico monitorea el mercado en tiempo real, lo que nos permite notificarle cuando es el
    momento ideal para operar.</p>
  <div style="background:#F7F9FC;border-left:4px solid #4CAF50;border-radius:4px;padding:16px 20px;margin:24px 0;">
    <p style="margin:0 0 6px;font-weight:bold;color:#0D1B2A;">Le propongo algo concreto:</p>
    <p style="margin:0;color:#4A5568;text-align:justify;">Una comparativa sin compromiso entre las tasas que recibe
      hoy de su proveedor actual y las que podemos ofrecerle en QoriCash, en tiempo real.</p>
  </div>
  <p style="text-align:justify;">Si desea conocer mas, puede ver nuestra presentacion institucional aqui:</p>
  <div style="margin:16px 0 24px;">
    <a href="https://qoricash.pe/presentacion.pdf"
       style="display:inline-block;padding:10px 24px;background:linear-gradient(135deg,#5CB85C 0%,#4a9b4a 100%);
              color:#ffffff;text-decoration:none;border-radius:6px;font-size:13px;font-weight:700;letter-spacing:0.3px;"
       target="_blank">Ver presentacion QoriCash</a>
  </div>
  <p style="text-align:justify;">Contamos con cuentas corrientes en soles y d&oacute;lares en los bancos
    m&aacute;s importantes del Per&uacute;:</p>
  {bancos}
  <p style="text-align:justify;">Quedamos atentos a su respuesta.</p>
  <br>{firma}{pie}
</body></html>"""

CUERPO_PRECIO = """\
<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;font-size:14px;color:#1E293B;line-height:1.7;max-width:620px;margin:0 auto;padding:24px;">
  {header}
  <p>Estimado(a) <strong>{nombre}</strong>,</p>
  <p style="text-align:justify;">Le compartimos las tasas de tipo de cambio vigentes en este momento.
    Sabemos que cada centavo importa en sus operaciones, por eso actualizamos nuestros precios en tiempo real
    para que siempre opere con la mejor tasa:</p>
  {ticker}
  <p style="text-align:justify;">Contamos con cuentas corrientes en soles y d&oacute;lares en los bancos
    m&aacute;s importantes del Per&uacute;:</p>
  {bancos}
  <p style="text-align:justify;">Estamos listos para ejecutar su operaci&oacute;n de forma inmediata.
    Esc&iacute;banos por WhatsApp o responda este correo.</p>
  <div style="margin:16px 0 24px;">
    <a href="https://wa.me/51926011920"
       style="display:inline-block;padding:10px 24px;background:linear-gradient(135deg,#5CB85C 0%,#4a9b4a 100%);
              color:#ffffff;text-decoration:none;border-radius:6px;font-size:13px;font-weight:700;
              letter-spacing:0.3px;" target="_blank">Cotizar en linea</a>
  </div>
  <p style="text-align:justify;">Quedamos atentos a su respuesta.</p>
  <br>{firma}{pie}
</body></html>"""


def _build_ticker(compra, venta):
    hoy = datetime.now().strftime("%d/%m/%Y")
    return f"""\
<table cellpadding="0" cellspacing="0" border="0" width="100%"
  style="margin:24px 0;border:1px solid #E2E8F0;border-left:4px solid #5CB85C;
         border-radius:6px;background:#FFFFFF;">
  <tr>
    <td style="padding:20px 24px;">
      <p style="margin:0 0 16px;font-size:10px;font-weight:700;color:#64748B;
         text-transform:uppercase;letter-spacing:1.2px;">
        Tipo de cambio &nbsp;&middot;&nbsp; {hoy}
      </p>
      <table cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td style="padding-right:40px;vertical-align:top;">
            <p style="margin:0;font-size:10px;color:#94A3B8;font-weight:600;
               text-transform:uppercase;letter-spacing:0.8px;">Compramos</p>
            <p style="margin:4px 0 0;font-size:28px;font-weight:700;color:#1E293B;
               letter-spacing:-0.5px;line-height:1;">S/. {compra}</p>
          </td>
          <td style="width:1px;background:#E2E8F0;padding:0;">&nbsp;</td>
          <td style="padding-left:40px;vertical-align:top;">
            <p style="margin:0;font-size:10px;color:#94A3B8;font-weight:600;
               text-transform:uppercase;letter-spacing:0.8px;">Vendemos</p>
            <p style="margin:4px 0 0;font-size:28px;font-weight:700;color:#1E293B;
               letter-spacing:-0.5px;line-height:1;">S/. {venta}</p>
          </td>
        </tr>
      </table>
      <p style="margin:14px 0 0;font-size:11px;color:#64748B;border-top:1px solid #F1F5F9;
         padding-top:12px;">
        Tasa garantizada &nbsp;&middot;&nbsp; Sin comisiones ocultas &nbsp;&middot;&nbsp;
        Operaci&oacute;n en minutos
      </p>
      <p style="margin:8px 0 0;font-size:10px;color:#94A3B8;font-style:italic;">
        * Precios del momento, sujetos a variaci&oacute;n.
      </p>
    </td>
  </tr>
</table>"""


def _construir_email(p, tipo, compra, venta, sender_email, nombre_completo, cargo, firma_pre=None):
    """Construye el HTML y asunto. Sin dependencia en current_user (usable en hilos)."""
    nombre_saludo = (p.nombre_contacto or p.razon_social or "estimado cliente").split()[0].capitalize()

    presentacion_remitente = (
        f"Mi nombre es <strong>{nombre_completo}</strong>, {cargo} de "
        "<strong>QoriCash SAC</strong>, fintech de cambio de divisas 100% digital, "
        "regulada por la Superintendencia de Banca, Seguros y AFP del Peru."
    )

    # firma_pre: firma ya obtenida (evita llamada extra a Gmail API en campañas masivas)
    firma_gmail = firma_pre if firma_pre is not None else _get_firma_gmail(sender_email)
    if firma_gmail:
        firma = f'<div style="margin-top:16px">{firma_gmail}</div>'
    else:
        firma = FIRMA_HTML.replace("{trader_nombre}", nombre_completo)

    if tipo == "precio":
        ticker = _build_ticker(compra, venta)
        html   = CUERPO_PRECIO.format(
            header=HEADER_HTML, nombre=nombre_saludo,
            ticker=ticker, bancos=BANCOS_HTML, firma=firma, pie=PIE,
        )
        return html, "QoriCash - Tipo de cambio del dia", "negociacion"
    else:
        html = CUERPO_PRESENTACION.format(
            header=HEADER_HTML, nombre=nombre_saludo,
            presentacion_remitente=presentacion_remitente,
            bancos=BANCOS_HTML, firma=firma, pie=PIE,
        )
        return html, "QoriCash - El mejor tipo de cambio para empresas", "seguimiento"


@prospeccion_bp.route("/<int:pid>/preview-email", methods=["POST"])
@login_required
@require_role("Master", "Trader")
def preview_email(pid):
    """Genera el borrador HTML sin enviarlo."""
    p = Prospecto.query.get_or_404(pid)
    _verificar_acceso(p)

    if not p.email:
        return jsonify({"ok": False, "error": "El prospecto no tiene email registrado."}), 400

    data   = request.get_json(force=True)
    tipo   = data.get("tipo", "presentacion")
    compra = data.get("compra", "")
    venta  = data.get("venta", "")

    if tipo == "precio" and (not compra or not venta):
        return jsonify({"ok": False, "error": "Debes indicar COMPRA y VENTA."}), 400

    sender_email            = (getattr(current_user, "email", "") or "").lower()
    nombre_completo, cargo  = _get_trader_info(sender_email, current_user.role)
    html, asunto, _         = _construir_email(p, tipo, compra, venta, sender_email, nombre_completo, cargo)
    return jsonify({"ok": True, "html": html, "asunto": asunto, "para": p.email})


@prospeccion_bp.route("/<int:pid>/enviar-email", methods=["POST"])
@login_required
@require_role("Master", "Trader")
def enviar_email(pid):
    p = Prospecto.query.get_or_404(pid)
    _verificar_acceso(p)

    if not p.email:
        return jsonify({"ok": False, "error": "El prospecto no tiene email registrado."}), 400

    data         = request.get_json(force=True)
    tipo         = data.get("tipo", "presentacion")
    compra       = data.get("compra", "")
    venta        = data.get("venta", "")
    html_editado = data.get("html_editado", "").strip()

    if tipo == "precio" and (not compra or not venta):
        return jsonify({"ok": False, "error": "Debes indicar COMPRA y VENTA."}), 400

    sender_email            = (getattr(current_user, "email", "") or "").lower()
    nombre_completo, cargo  = _get_trader_info(sender_email, current_user.role)

    if not sender_email:
        return jsonify({"ok": False, "error": "Tu usuario no tiene email configurado."}), 400

    if html_editado:
        html   = html_editado
        asunto = data.get("asunto", "QoriCash")
    else:
        html, asunto, _ = _construir_email(p, tipo, compra, venta, sender_email, nombre_completo, cargo)

    try:
        _send_via_gmail_api(sender_email, p.email, asunto, html)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500

    nuevo_estado = "negociacion" if tipo == "precio" else "seguimiento"
    act = ActividadProspecto(
        prospecto_id=p.id,
        user_id=current_user.id,
        tipo="email",
        descripcion=f"Correo de {tipo} enviado.",
        resultado="Enviado",
        nuevo_estado=nuevo_estado,
    )
    db.session.add(act)
    p.estado_comercial      = nuevo_estado
    p.tipo_ultimo_envio     = tipo
    p.fecha_ultimo_contacto = now_peru().strftime("%Y-%m-%d %H:%M")
    db.session.commit()

    tipo_label = "presentacion" if tipo == "presentacion" else "precio del dia"
    return jsonify({"ok": True, "msg": f"Correo de {tipo_label} enviado a {p.email}."})


# ── Cambiar estado (seguimiento → negociacion) ────────────────────────────────

@prospeccion_bp.route("/<int:pid>/cambiar-estado", methods=["POST"])
@login_required
@require_role("Master", "Trader")
def cambiar_estado(pid):
    p = Prospecto.query.get_or_404(pid)
    _verificar_acceso(p)

    nuevo = request.get_json(force=True).get("estado", "")
    if nuevo not in ("seguimiento", "negociacion"):
        return jsonify({"ok": False, "error": "Estado invalido."}), 400

    act = ActividadProspecto(
        prospecto_id=p.id,
        user_id=current_user.id,
        tipo="estado",
        descripcion=f"Estado cambiado a {nuevo}.",
        nuevo_estado=nuevo,
    )
    db.session.add(act)
    p.estado_comercial = nuevo
    db.session.commit()
    return jsonify({"ok": True})


# ── Registrar como cliente ────────────────────────────────────────────────────

@prospeccion_bp.route("/<int:pid>/registrar-cliente", methods=["POST"])
@login_required
@require_role("Master", "Trader")
def registrar_cliente(pid):
    from app.models.client import Client
    from werkzeug.security import generate_password_hash
    import secrets

    p = Prospecto.query.get_or_404(pid)
    _verificar_acceso(p)

    # 1. Buscar cliente existente por RUC o email
    cliente = None
    if p.ruc:
        cliente = Client.query.filter_by(dni=p.ruc).first()
    if not cliente and p.email:
        cliente = Client.query.filter_by(email=p.email).first()

    if cliente:
        # Ya existe — solo marcar prospecto como convertido
        p.estado_comercial = "cliente"
        act = ActividadProspecto(
            prospecto_id=p.id, user_id=current_user.id,
            tipo="estado",
            descripcion=f"Cruzado con cliente existente ID {cliente.id} ({cliente.email}).",
            nuevo_estado="cliente",
        )
        db.session.add(act)
        db.session.commit()
        return jsonify({"ok": True, "accion": "vinculado",
                        "msg": f"Vinculado con cliente existente: {cliente.email}"})

    # 2. No existe — crear cliente basico con los datos del prospecto
    if not p.email:
        return jsonify({"ok": False,
                        "error": "El prospecto no tiene email. Agrega uno antes de registrarlo como cliente."}), 400

    temp_pass = secrets.token_urlsafe(10)
    nuevo_cliente = Client(
        document_type = "RUC" if p.ruc else "DNI",
        dni           = p.ruc or p.email,
        razon_social  = p.razon_social,
        persona_contacto = p.nombre_contacto,
        email         = p.email,
        phone         = p.telefono,
        departamento  = p.departamento,
        provincia     = p.provincia,
        password_hash = generate_password_hash(temp_pass),
    )
    db.session.add(nuevo_cliente)

    p.estado_comercial = "cliente"
    act = ActividadProspecto(
        prospecto_id=p.id, user_id=current_user.id,
        tipo="estado",
        descripcion=f"Registrado como nuevo cliente ({p.email}).",
        nuevo_estado="cliente",
    )
    db.session.add(act)

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        return jsonify({"ok": False, "error": f"Error al crear cliente: {exc}"}), 500

    return jsonify({"ok": True, "accion": "creado",
                    "msg": f"Cliente creado exitosamente: {p.email}"})


# ── Campaña masiva ────────────────────────────────────────────────────────────

def _campana_worker(app, trader_id, prospecto_ids, tipo, sender_email,
                    nombre_completo, cargo, firma_pre):
    """Hilo que envía emails con pausa configurable entre cada uno."""
    pausa = 7  # segundos entre envíos

    with app.app_context():
        stop_event = _campanas[trader_id]["stop"]

        for pid in prospecto_ids:
            if stop_event.is_set():
                break
            try:
                with _campanas_lock:
                    if trader_id not in _campanas or stop_event.is_set():
                        break
                    compra = _campanas[trader_id]["compra"]
                    venta  = _campanas[trader_id]["venta"]

                p = Prospecto.query.get(pid)
                if not p or not p.email:
                    with _campanas_lock:
                        if trader_id in _campanas:
                            _campanas[trader_id]["errores"] += 1
                    continue

                html, asunto, nuevo_estado = _construir_email(
                    p, tipo, compra, venta,
                    sender_email, nombre_completo, cargo, firma_pre=firma_pre,
                )
                _send_via_gmail_api(sender_email, p.email, asunto, html)

                p.estado_comercial      = nuevo_estado
                p.tipo_ultimo_envio     = tipo
                p.fecha_ultimo_contacto = now_peru().strftime("%Y-%m-%d %H:%M")

                act = ActividadProspecto(
                    prospecto_id=p.id,
                    user_id=trader_id,
                    tipo="email",
                    descripcion=f"Campaña masiva: correo de {tipo} enviado.",
                    resultado="Enviado",
                    nuevo_estado=nuevo_estado,
                )
                db.session.add(act)
                db.session.commit()

                with _campanas_lock:
                    if trader_id in _campanas:
                        _campanas[trader_id]["enviados"] += 1

            except Exception:
                db.session.rollback()
                with _campanas_lock:
                    if trader_id in _campanas:
                        _campanas[trader_id]["errores"] += 1

            # Pausa interruptible
            stop_event.wait(timeout=pausa)

        with _campanas_lock:
            if trader_id in _campanas:
                if stop_event.is_set():
                    _campanas[trader_id]["estado"] = "detenida"
                else:
                    _campanas[trader_id]["estado"] = "completada"


@prospeccion_bp.route("/campana/iniciar", methods=["POST"])
@login_required
@require_role("Master", "Trader")
def campana_iniciar():
    data   = request.get_json(force=True)
    ids    = [int(i) for i in data.get("ids", []) if str(i).isdigit()]
    tipo   = data.get("tipo", "presentacion")
    compra = data.get("compra", "").strip()
    venta  = data.get("venta", "").strip()

    if not ids:
        return jsonify({"ok": False, "error": "No se seleccionaron prospectos."}), 400
    if tipo == "precio" and (not compra or not venta):
        return jsonify({"ok": False, "error": "Debes indicar COMPRA y VENTA."}), 400

    trader_id = current_user.id
    with _campanas_lock:
        camp = _campanas.get(trader_id)
        if camp and camp["estado"] == "activa":
            return jsonify({"ok": False,
                            "error": "Ya hay una campaña activa. Detén la actual primero."}), 400

    sender_email            = (getattr(current_user, "email", "") or "").lower()
    nombre_completo, cargo  = _get_trader_info(sender_email, current_user.role)
    firma_pre               = _get_firma_gmail(sender_email)

    stop_event = threading.Event()
    with _campanas_lock:
        _campanas[trader_id] = {
            "estado":   "activa",
            "tipo":     tipo,
            "compra":   compra,
            "venta":    venta,
            "total":    len(ids),
            "enviados": 0,
            "errores":  0,
            "stop":     stop_event,
        }

    app = current_app._get_current_object()
    t = threading.Thread(
        target=_campana_worker,
        args=(app, trader_id, ids, tipo, sender_email, nombre_completo, cargo, firma_pre),
        daemon=True,
    )
    t.start()
    return jsonify({"ok": True, "total": len(ids)})


@prospeccion_bp.route("/campana/estado")
@login_required
@require_role("Master", "Trader")
def campana_estado():
    trader_id = current_user.id
    with _campanas_lock:
        camp = _campanas.get(trader_id)
        if not camp:
            return jsonify({"activa": False})
        resp = {
            "activa":   camp["estado"] == "activa",
            "estado":   camp["estado"],
            "tipo":     camp["tipo"],
            "total":    camp["total"],
            "enviados": camp["enviados"],
            "errores":  camp["errores"],
            "compra":   camp.get("compra", ""),
            "venta":    camp.get("venta", ""),
        }
        # Limpiar estado final para que no persista entre recargas
        if camp["estado"] in ("completada", "detenida"):
            del _campanas[trader_id]
        return jsonify(resp)


@prospeccion_bp.route("/campana/detener", methods=["POST"])
@login_required
@require_role("Master", "Trader")
def campana_detener():
    trader_id = current_user.id
    with _campanas_lock:
        camp = _campanas.get(trader_id)
        if not camp or camp["estado"] != "activa":
            return jsonify({"ok": False, "error": "No hay campaña activa."}), 400
        camp["stop"].set()
    return jsonify({"ok": True})


@prospeccion_bp.route("/reasignar-vencidos", methods=["POST"])
@login_required
@require_role("Master")
def reasignar_vencidos():
    data            = request.get_json(force=True)
    ids             = [int(i) for i in data.get("ids", []) if str(i).isdigit()]
    nuevo_trader_id = int(data.get("trader_id", 0))

    if not ids or not nuevo_trader_id:
        return jsonify({"ok": False, "error": "Faltan parámetros."}), 400

    nuevo_trader = User.query.get(nuevo_trader_id)
    if not nuevo_trader:
        return jsonify({"ok": False, "error": "Trader no encontrado."}), 404

    ahora       = now_peru()
    reasignados = 0

    for pid in ids:
        p = Prospecto.query.get(pid)
        if not p:
            continue

        # Desactivar asignación actual
        p.asignaciones.filter_by(activo=True).update({"activo": False})

        # Crear o reactivar asignación al nuevo trader
        existente = AsignacionProspecto.query.filter_by(
            prospecto_id=pid, trader_id=nuevo_trader_id
        ).first()
        if existente:
            existente.activo       = True
            existente.asignado_en  = ahora
            existente.asignado_por = current_user.id
        else:
            db.session.add(AsignacionProspecto(
                prospecto_id=pid,
                trader_id=nuevo_trader_id,
                asignado_por=current_user.id,
                asignado_en=ahora,
            ))

        # Registrar actividad
        db.session.add(ActividadProspecto(
            prospecto_id=pid,
            user_id=current_user.id,
            tipo="nota",
            descripcion=(f"Reasignado a {nuevo_trader.username} "
                         f"por vencimiento de vigencia ({DIAS_VIGENCIA} días sin actividad)."),
        ))
        reasignados += 1

    db.session.commit()
    return jsonify({"ok": True, "reasignados": reasignados})


@prospeccion_bp.route("/campana/actualizar-precios", methods=["POST"])
@login_required
@require_role("Master", "Trader")
def campana_actualizar_precios():
    data   = request.get_json(force=True)
    compra = data.get("compra", "").strip()
    venta  = data.get("venta", "").strip()
    if not compra or not venta:
        return jsonify({"ok": False, "error": "Debes indicar COMPRA y VENTA."}), 400

    trader_id = current_user.id
    with _campanas_lock:
        camp = _campanas.get(trader_id)
        if not camp or camp["estado"] != "activa":
            return jsonify({"ok": False, "error": "No hay campaña activa."}), 400
        camp["compra"] = compra
        camp["venta"]  = venta
    return jsonify({"ok": True})


# ── Helper ────────────────────────────────────────────────────────────────────

def _verificar_acceso(p):
    """Trader solo puede ver sus prospectos asignados."""
    if current_user.role == "Master":
        return
    asig = p.asignaciones.filter_by(trader_id=current_user.id, activo=True).first()
    if not asig:
        flash("No tienes acceso a este prospecto.", "danger")
        redirect(url_for("prospeccion.lista"))
