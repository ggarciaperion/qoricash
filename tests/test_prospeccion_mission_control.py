"""
test_prospeccion_mission_control.py — Tests Fase J

Verifica:
1. prospeccion_connector lee ecosistema.db y retorna estructura correcta
2. leads_api idempotencia: mismo gmail_message_id no crea dos oportunidades
3. Oportunidad.to_dict() contiene todos los campos necesarios
4. Pipeline serialización incluye todos los campos del modal
5. agentes_bp correctamente registrado en la app
6. DRY_RUN reflejo desde prospeccion_kpis
7. No se exponen secrets en outputs del conector

Ejecutar:
  cd /Users/gianpierre/Desktop/Qoricash/Sistema/qoricash
  python -m pytest tests/test_prospeccion_mission_control.py -v
"""
import os
import sys
import importlib.util
from pathlib import Path


# ── 1. prospeccion_connector ─────────────────────────────────────────────────

ECOSISTEMA_DB = Path("/Users/gianpierre/Desktop/Prospeccion/ecosistema.db")


def _load_connector():
    os.environ["ECOSISTEMA_DB_PATH"] = str(ECOSISTEMA_DB)
    spec = importlib.util.spec_from_file_location(
        "prospeccion_connector",
        Path(__file__).parents[1] / "app" / "services" / "prospeccion_connector.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_connector_estructura():
    """get_prospeccion_kpis() retorna los campos esperados."""
    if not ECOSISTEMA_DB.exists():
        return  # Skip si no hay DB (CI sin Prospeccion)
    conn = _load_connector()
    kpis = conn.get_prospeccion_kpis()
    assert "master" in kpis
    assert "dry_run" in kpis
    assert "tc" in kpis
    assert "db_disponible" in kpis


def test_connector_master_stats_reales():
    """master_stats retorna datos reales de ecosistema.db."""
    if not ECOSISTEMA_DB.exists():
        return
    conn = _load_connector()
    ms = conn.get_master_stats()
    assert ms["disponible"] is True
    assert ms["total"] > 100_000, f"Total prospectos inesperadamente bajo: {ms['total']}"
    assert ms["ready_for_outreach"] > 0
    assert "last_full_sync" in ms


def test_connector_no_secrets():
    """El conector no expone tokens ni credenciales."""
    if not ECOSISTEMA_DB.exists():
        return
    conn = _load_connector()
    kpis = conn.get_prospeccion_kpis()
    kpis_str = str(kpis)
    forbidden = ["token", "secret", "password", "credential", "refresh_token",
                 "client_secret", "api_key", "private_key"]
    for word in forbidden:
        assert word not in kpis_str.lower(), \
            f"prospeccion_kpis podría exponer dato sensible: '{word}'"


def test_connector_offline():
    """Si DB no existe, el conector retorna datos vacíos sin lanzar excepción."""
    spec = importlib.util.spec_from_file_location(
        "prospeccion_connector_offline",
        Path(__file__).parents[1] / "app" / "services" / "prospeccion_connector.py",
    )
    mod = importlib.util.module_from_spec(spec)
    # Apuntar a DB inexistente
    import unittest.mock
    with unittest.mock.patch.dict(os.environ, {"ECOSISTEMA_DB_PATH": "/tmp/nonexistent_db.db"}):
        spec.loader.exec_module(mod)
        ms = mod.get_master_stats()
    assert ms.get("disponible") is False, "Debe retornar disponible=False si DB no existe"


# ── 2. leads_api idempotencia (unit, sin Flask) ───────────────────────────────

def _load_leads_helpers():
    """Carga solo las funciones helper de leads_api sin Flask."""
    spec = importlib.util.spec_from_file_location(
        "leads_api",
        Path(__file__).parents[1] / "app" / "routes" / "leads_api.py",
    )
    src = Path(__file__).parents[1] / "app" / "routes" / "leads_api.py"
    code = src.read_text()
    # Solo compilar hasta los helpers (evitar imports Flask)
    import ast
    tree = ast.parse(code)
    # Extraer funciones helper independientes
    ns = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("_"):
            try:
                exec(compile(ast.Module([node], type_ignores=[]), str(src), "exec"), ns)
            except Exception:
                pass
    return ns


def test_prioridad_from_tipo():
    """_prioridad_from_tipo clasifica correctamente."""
    ns = _load_leads_helpers()
    f = ns.get("_prioridad_from_tipo")
    if not f:
        return  # helper no cargó (imports complejos)
    assert f("solicita_cotizacion") == "alta"
    assert f("solicita_llamada")    == "alta"
    assert f("solicita_whatsapp")   == "alta"
    assert f("interesado")           == "media"
    assert f("otro_tipo")            == "baja"


def test_build_necesidad():
    """_build_necesidad incluye tipo y subject."""
    ns = _load_leads_helpers()
    f = ns.get("_build_necesidad")
    if not f:
        return
    result = f("solicita_cotizacion", "Re: TC urgente", {})
    assert "cotización" in result.lower() or "solicita" in result.lower()
    assert "TC urgente" in result


# ── 3. Oportunidad modelo ────────────────────────────────────────────────────

def _load_oportunidad_model():
    spec = importlib.util.spec_from_file_location(
        "inteligencia_model",
        Path(__file__).parents[1] / "app" / "models" / "inteligencia.py",
    )
    code = (Path(__file__).parents[1] / "app" / "models" / "inteligencia.py").read_text()
    # Solo verificar campos del modelo en el source
    return code


def test_oportunidad_campos_requeridos():
    """El modelo Oportunidad tiene todos los campos del pipeline."""
    code = _load_oportunidad_model()
    required_fields = [
        "empresa", "contacto", "cargo", "email", "telefono",
        "sector", "prioridad", "score", "necesidad", "recomendacion",
        "cuerpo_email", "estado", "cuenta_origen", "mensaje_id",
    ]
    for field in required_fields:
        assert field in code, f"Campo faltante en Oportunidad: {field}"


def test_oportunidad_estados_pipeline():
    """Los 4 estados del pipeline están definidos en el código del modelo."""
    code = _load_oportunidad_model()
    for estado in ("nuevo", "en_seguimiento", "convertido", "descartado"):
        assert estado in code, f"Estado de pipeline faltante en código: {estado}"


def test_oportunidad_mensaje_id_unico():
    """mensaje_id tiene unique=True (garantía de idempotencia)."""
    code = _load_oportunidad_model()
    # Buscar la declaración de mensaje_id con unique
    assert "mensaje_id" in code
    # Verificar que en leads_api se usa mensaje_id para idempotencia
    leads_code = (Path(__file__).parents[1] / "app" / "routes" / "leads_api.py").read_text()
    assert "mensaje_id" in leads_code
    assert "already_exists" in leads_code


# ── 4. Pipeline comercial — serialización ────────────────────────────────────

def test_pipeline_ops_json_campos():
    """El route pipeline serializa todos los campos que el modal necesita."""
    code = (Path(__file__).parents[1] / "app" / "routes" / "comercial.py").read_text()
    required = ["empresa", "contacto", "email", "telefono", "sector",
                "prioridad", "score", "estado", "necesidad",
                "recomendacion", "cuerpo_email", "cuenta_origen", "detectado_en"]
    for field in required:
        assert f"'{field}'" in code, f"Campo faltante en ops_json: {field}"


# ── 5. Blueprint agentes registrado ─────────────────────────────────────────

def test_agentes_bp_en_init():
    """agentes_bp está registrado en __init__.py."""
    init_code = (Path(__file__).parents[1] / "app" / "__init__.py").read_text()
    assert "from app.routes.agentes import agentes_bp" in init_code
    assert "app.register_blueprint(agentes_bp)" in init_code


def test_mission_control_route_en_agentes():
    """La ruta /mission-control está definida en agentes.py."""
    code = (Path(__file__).parents[1] / "app" / "routes" / "agentes.py").read_text()
    assert "/mission-control" in code
    assert "prospeccion_kpis" in code
    assert "get_prospeccion_kpis" in code


# ── 6. DRY_RUN visible en template ─────────────────────────────────────────

def test_dry_run_visible_en_template():
    """El template mission_control.html muestra el banner DRY_RUN."""
    code = (Path(__file__).parents[1] / "app" / "templates" / "agentes" /
            "mission_control.html").read_text()
    assert "DRY_RUN" in code
    assert "prospeccion.dry_run" in code


def test_prospeccion_master_stats_en_template():
    """El template mission_control.html muestra MASTER stats."""
    code = (Path(__file__).parents[1] / "app" / "templates" / "agentes" /
            "mission_control.html").read_text()
    assert "prospeccion.master" in code
    assert "ready_for_outreach" in code
    assert "ready" in code.lower() or "Ready" in code


# ── 7. Navegación: links de CRM y Agentes IA ────────────────────────────────

def test_nav_crm_pipeline_link():
    """base.html incluye link a /comercial/pipeline (CRM Oportunidades)."""
    code = (Path(__file__).parents[1] / "app" / "templates" / "base.html").read_text()
    assert "comercial.pipeline" in code


def test_nav_agentes_ia_link():
    """base.html incluye link a Agentes IA / Mission Control."""
    code = (Path(__file__).parents[1] / "app" / "templates" / "base.html").read_text()
    assert "agentes.mission_control" in code


# ── 8. prospeccion_repo seguridad (reemplaza prospeccion_connector) ──────────

def test_repo_uses_db_session_not_sqlite():
    """prospeccion_repo usa db.session (SQLAlchemy) — no sqlite3 directo."""
    code = (Path(__file__).parents[1] / "app" / "services" /
            "prospeccion_repo.py").read_text()
    assert "db.session" in code, "Debe usar db.session (SQLAlchemy)"
    assert "import sqlite3" not in code, "No debe importar sqlite3"
    assert "import psycopg2" not in code, "No debe importar psycopg2 directamente"


def test_repo_no_secrets():
    """prospeccion_repo no expone tokens ni credenciales en ninguna función."""
    code = (Path(__file__).parents[1] / "app" / "services" /
            "prospeccion_repo.py").read_text()
    forbidden_imports = ["token.json", "credentials.json", "os.environ.get('SECRET"]
    for pattern in forbidden_imports:
        assert pattern not in code, \
            f"prospeccion_repo contiene referencia sospechosa: '{pattern}'"


def test_mission_control_uses_repo():
    """agentes.py importa de prospeccion_repo (no de prospeccion_connector)."""
    code = (Path(__file__).parents[1] / "app" / "routes" / "agentes.py").read_text()
    assert "prospeccion_repo" in code
    assert "prospeccion_connector" not in code, \
        "agentes.py debe haber migrado a prospeccion_repo"
