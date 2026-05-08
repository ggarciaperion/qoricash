"""
Modulo de Prospeccion — QoriCash Trading V2
Rutas para Master y Trader.
"""
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import or_, func
from app.extensions import db, csrf
from app.models.prospecto import Prospecto, AsignacionProspecto, ActividadProspecto
from app.models.user import User
from app.utils.decorators import require_role
from app.utils.formatters import now_peru

prospeccion_bp = Blueprint("prospeccion", __name__, url_prefix="/prospeccion")

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
    total       = q.count()
    pipeline    = q.filter(Prospecto.estado_comercial.in_(["P1","P2","P3","P4"])).count()
    clientes    = q.filter(Prospecto.estado_comercial == "P4").count()
    en_negoc    = q.filter(Prospecto.estado_comercial == "P3").count()
    lfc         = q.filter(Prospecto.cliente_lfc == "Cliente LFC").count()

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

    # Solo Master: resumen por trader
    traders_stats = []
    if current_user.role == "Master":
        traders = User.query.filter(User.role == "Trader", User.status == "Activo").all()
        for t in traders:
            count = (AsignacionProspecto.query
                     .filter_by(trader_id=t.id, activo=True).count())
            traders_stats.append({"trader": t, "asignados": count})

    return render_template(
        "prospeccion/dashboard.html",
        total=total, pipeline=pipeline, clientes=clientes,
        en_negoc=en_negoc, lfc=lfc,
        top_rubros=top_rubros,
        actividades=actividades,
        traders_stats=traders_stats,
    )


# ── Lista de prospectos ───────────────────────────────────────────────────────

@prospeccion_bp.route("/lista")
@login_required
@require_role("Master", "Trader")
def lista():
    grupo  = request.args.get("grupo", "")
    rubro  = request.args.get("rubro", "")
    depto  = request.args.get("depto", "")
    q_str  = request.args.get("q", "")
    page   = request.args.get("page", 1, type=int)

    query = _base_query()

    if grupo:
        query = query.filter(Prospecto.grupo == grupo)
    if rubro:
        query = query.filter(Prospecto.rubro.ilike(f"%{rubro}%"))
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

    prospectos = query.order_by(Prospecto.score.desc()).paginate(page=page, per_page=50, error_out=False)

    rubros = [r[0] for r in db.session.query(Prospecto.rubro).distinct().order_by(Prospecto.rubro).all() if r[0]]
    deptos = [d[0] for d in db.session.query(Prospecto.departamento).distinct().order_by(Prospecto.departamento).all() if d[0]]

    return render_template(
        "prospeccion/lista.html",
        prospectos=prospectos,
        grupos=GRUPOS_ORDEN, rubros=rubros, deptos=deptos,
        filtros={"grupo": grupo, "rubro": rubro, "depto": depto, "q": q_str},
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

    asignacion_actual = p.asignaciones.filter_by(activo=True).first()

    return render_template(
        "prospeccion/detalle.html",
        p=p, actividades=actividades,
        traders_disponibles=traders_disponibles,
        asignacion_actual=asignacion_actual,
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
@require_role("Master", "Trader")
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

        score_val = request.form.get("score")
        if score_val:
            try:
                p.score = int(score_val)
            except ValueError:
                pass

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


# ── Helper ────────────────────────────────────────────────────────────────────

def _verificar_acceso(p):
    """Trader solo puede ver sus prospectos asignados."""
    if current_user.role == "Master":
        return
    asig = p.asignaciones.filter_by(trader_id=current_user.id, activo=True).first()
    if not asig:
        flash("No tienes acceso a este prospecto.", "danger")
        redirect(url_for("prospeccion.lista"))
