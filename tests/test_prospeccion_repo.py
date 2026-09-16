"""
test_prospeccion_repo.py — Tests de prospeccion_repo.py (Flask datasource PG)

Verifica:
1. Interfaz idéntica a prospeccion_connector (no rompe agentes.py)
2. Funciones retornan estructura correcta ante tablas vacías / pre-deploy
3. No expone secrets ni credenciales en outputs
4. get_prospeccion_kpis incluye campos nuevos: worker, bandejas, leads
5. get_worker_status distingue online/offline correctamente
6. get_agent_heartbeats enriquece con is_offline y age_seconds
7. Endpoints heartbeats y bandejas registrados en agentes_bp

Tests de integración con PG real: requieren DATABASE_URL y app en contexto Flask.
Tests unitarios: usan mocks de db.session y no requieren PG.

Ejecutar:
  cd /Users/gianpierre/Desktop/Qoricash/Sistema/qoricash
  python -m pytest tests/test_prospeccion_repo.py -v
"""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# ── Flask app fixture ─────────────────────────────────────────────────────────

@pytest.fixture(scope='module')
def app():
    """Crea la app Flask en modo test."""
    sys.path.insert(0, str(Path(__file__).parents[1]))
    os.environ.setdefault('FLASK_ENV', 'testing')
    os.environ.setdefault('SECRET_KEY', 'test-secret-key')
    os.environ.setdefault('DATABASE_URL', os.environ.get('DATABASE_URL', 'sqlite:///:memory:'))

    from app import create_app
    _app = create_app()
    _app.config['TESTING'] = True
    return _app


@pytest.fixture
def app_ctx(app):
    with app.app_context():
        yield


# ── Tests de estructura de módulo ─────────────────────────────────────────────

def test_repo_importable():
    """prospeccion_repo.py es importable sin conexión PG."""
    sys.path.insert(0, str(Path(__file__).parents[1]))
    from app.services import prospeccion_repo
    expected_funcs = [
        'get_master_stats', 'get_agent_runs', 'get_agent_heartbeats',
        'get_worker_status', 'get_runtime_config', 'get_tc_status',
        'get_bandeja_estado', 'get_outreach_stats_today',
        'get_alerts', 'get_lead_pipeline_stats', 'get_prospeccion_kpis',
    ]
    for fn in expected_funcs:
        assert hasattr(prospeccion_repo, fn), f"Función faltante: {fn}"


def test_interfaz_compatible_con_connector():
    """get_prospeccion_kpis() tiene los mismos campos clave que prospeccion_connector."""
    sys.path.insert(0, str(Path(__file__).parents[1]))
    from app.services import prospeccion_repo

    # Campos heredados del connector (no romper agentes.py ni mission_control.html)
    connector_fields = ['master', 'outreach_hoy', 'dry_run', 'tc', 'db_disponible']
    # Campos nuevos del repo
    new_fields = ['worker', 'bandejas', 'leads']

    # Mockear _rows y _row para no necesitar DB
    with patch('app.services.prospeccion_repo._rows', return_value=[]), \
         patch('app.services.prospeccion_repo._row',   return_value={}), \
         patch('app.services.prospeccion_repo._scalar', return_value=None):
        kpis = prospeccion_repo.get_prospeccion_kpis()

    for f in connector_fields + new_fields:
        assert f in kpis, f"Campo faltante en get_prospeccion_kpis: {f}"


def test_get_prospeccion_kpis_no_secrets():
    """get_prospeccion_kpis no expone tokens, passwords ni api_keys."""
    sys.path.insert(0, str(Path(__file__).parents[1]))
    from app.services import prospeccion_repo

    with patch('app.services.prospeccion_repo._rows', return_value=[]), \
         patch('app.services.prospeccion_repo._row',   return_value={}), \
         patch('app.services.prospeccion_repo._scalar', return_value=None):
        kpis = prospeccion_repo.get_prospeccion_kpis()

    kpis_str = str(kpis).lower()
    forbidden = ['token', 'secret', 'password', 'credential',
                 'refresh_token', 'client_secret', 'private_key']
    for word in forbidden:
        assert word not in kpis_str, f"Posible dato sensible en kpis: '{word}'"


def test_get_master_stats_disponible_false_on_empty():
    """get_master_stats retorna disponible=False si las tablas no existen."""
    sys.path.insert(0, str(Path(__file__).parents[1]))
    from app.services import prospeccion_repo

    with patch('app.services.prospeccion_repo._row', return_value={}):
        stats = prospeccion_repo.get_master_stats()

    assert stats.get('disponible') is False


def test_get_worker_status_offline_when_no_beat():
    """get_worker_status retorna online=False cuando no hay heartbeat en DB."""
    sys.path.insert(0, str(Path(__file__).parents[1]))
    from app.services import prospeccion_repo

    with patch('app.services.prospeccion_repo._row', return_value={}):
        status = prospeccion_repo.get_worker_status()

    assert status['online'] is False
    assert status['last_seen'] is None


def test_get_worker_status_online_fresh_beat():
    """get_worker_status retorna online=True si last_seen es reciente."""
    sys.path.insert(0, str(Path(__file__).parents[1]))
    from app.services import prospeccion_repo

    fresh = datetime.utcnow() - timedelta(minutes=1)
    beat  = {'last_seen': fresh, 'status': 'idle', 'hostname': 'render-01', 'pid': 1234}

    with patch('app.services.prospeccion_repo._row', return_value=beat):
        status = prospeccion_repo.get_worker_status()

    assert status['online'] is True
    assert status['status'] == 'idle'


def test_get_worker_status_offline_stale_beat():
    """get_worker_status retorna online=False si last_seen es antiguo."""
    sys.path.insert(0, str(Path(__file__).parents[1]))
    from app.services import prospeccion_repo

    stale = datetime.utcnow() - timedelta(minutes=10)
    beat  = {'last_seen': stale, 'status': 'idle', 'hostname': 'render-01', 'pid': 1234}

    with patch('app.services.prospeccion_repo._row', return_value=beat):
        status = prospeccion_repo.get_worker_status()

    assert status['online'] is False


def test_get_agent_heartbeats_enriches_is_offline():
    """get_agent_heartbeats agrega is_offline y age_seconds a cada beat."""
    sys.path.insert(0, str(Path(__file__).parents[1]))
    from app.services import prospeccion_repo

    fresh = datetime.utcnow() - timedelta(minutes=2)
    stale = datetime.utcnow() - timedelta(minutes=20)
    mock_beats = [
        {'agent': 'outreach',    'last_seen': fresh, 'status': 'idle',    'current_run_id': None, 'hostname': 'h1', 'updated_at': fresh},
        {'agent': 'scout',       'last_seen': stale, 'status': 'offline', 'current_run_id': None, 'hostname': 'h1', 'updated_at': stale},
        {'agent': 'no_heartbeat','last_seen': None,  'status': None,      'current_run_id': None, 'hostname': None, 'updated_at': None},
    ]

    with patch('app.services.prospeccion_repo._rows', return_value=mock_beats):
        beats = prospeccion_repo.get_agent_heartbeats()

    outreach = next(b for b in beats if b['agent'] == 'outreach')
    scout    = next(b for b in beats if b['agent'] == 'scout')
    no_hb    = next(b for b in beats if b['agent'] == 'no_heartbeat')

    assert outreach['is_offline'] is False
    assert isinstance(outreach['age_seconds'], int)
    assert scout['is_offline'] is True
    assert no_hb['is_offline'] is True
    assert no_hb['age_seconds'] is None


def test_get_tc_status_fresco():
    """get_tc_status marca fresco=True si tc_updated_at es reciente."""
    sys.path.insert(0, str(Path(__file__).parents[1]))
    from app.services import prospeccion_repo

    recent_ts = (datetime.now() - timedelta(minutes=30)).isoformat()
    config    = {'tc_compra': '3.750', 'tc_venta': '3.760', 'tc_updated_at': recent_ts}

    with patch('app.services.prospeccion_repo.get_runtime_config', return_value=config):
        tc = prospeccion_repo.get_tc_status()

    assert tc['fresco'] is True
    assert tc['compra'] == '3.750'


def test_get_tc_status_stale():
    """get_tc_status marca fresco=False si tc_updated_at tiene > 3 horas."""
    sys.path.insert(0, str(Path(__file__).parents[1]))
    from app.services import prospeccion_repo

    old_ts = (datetime.now() - timedelta(hours=5)).isoformat()
    config = {'tc_compra': '3.750', 'tc_venta': '3.760', 'tc_updated_at': old_ts}

    with patch('app.services.prospeccion_repo.get_runtime_config', return_value=config):
        tc = prospeccion_repo.get_tc_status()

    assert tc['fresco'] is False


def test_get_bandeja_estado_is_pausada():
    """get_bandeja_estado enriquece con is_pausada según pausada_hasta."""
    sys.path.insert(0, str(Path(__file__).parents[1]))
    from app.services import prospeccion_repo

    future = datetime.utcnow() + timedelta(hours=2)
    past   = datetime.utcnow() - timedelta(hours=1)

    mock_rows = [
        {'bandeja': 'ggarcia',  'enviados_hoy': 50, 'bounce_count_24h': 1,
         'total_24h': 51, 'pausada_hasta': future, 'ultimo_update': None},
        {'bandeja': 'gerencia', 'enviados_hoy': 30, 'bounce_count_24h': 0,
         'total_24h': 30, 'pausada_hasta': past,   'ultimo_update': None},
        {'bandeja': 'info',     'enviados_hoy': 10, 'bounce_count_24h': 0,
         'total_24h': 10, 'pausada_hasta': None,   'ultimo_update': None},
    ]

    with patch('app.services.prospeccion_repo._rows', return_value=mock_rows):
        bandejas = prospeccion_repo.get_bandeja_estado()

    ggarcia  = next(b for b in bandejas if b['bandeja'] == 'ggarcia')
    gerencia = next(b for b in bandejas if b['bandeja'] == 'gerencia')
    info     = next(b for b in bandejas if b['bandeja'] == 'info')

    assert ggarcia['is_pausada']  is True
    assert gerencia['is_pausada'] is False
    assert info['is_pausada']     is False


# ── Tests de endpoints registrados ───────────────────────────────────────────

def test_heartbeats_endpoint_registered():
    """agentes_bp expone GET /api/prospeccion/heartbeats."""
    from pathlib import Path as P
    code = (P(__file__).parents[1] / 'app' / 'routes' / 'agentes.py').read_text()
    assert '/api/prospeccion/heartbeats' in code
    assert 'get_agent_heartbeats' in code
    assert 'get_worker_status' in code


def test_bandejas_endpoint_registered():
    """agentes_bp expone GET /api/prospeccion/bandejas."""
    from pathlib import Path as P
    code = (P(__file__).parents[1] / 'app' / 'routes' / 'agentes.py').read_text()
    assert '/api/prospeccion/bandejas' in code
    assert 'get_bandeja_estado' in code


def test_agentes_uses_repo_not_connector():
    """agentes.py importa de prospeccion_repo, no de prospeccion_connector."""
    from pathlib import Path as P
    code = (P(__file__).parents[1] / 'app' / 'routes' / 'agentes.py').read_text()
    assert 'prospeccion_repo' in code, "agentes.py debe usar prospeccion_repo"
    # Si aún importa el connector viejo, es un error
    assert 'prospeccion_connector' not in code, \
        "agentes.py no debe importar prospeccion_connector (reemplazado por repo)"


def test_repo_uses_db_session():
    """prospeccion_repo.py usa db.session (no sqlite3 ni psycopg2 directo)."""
    from pathlib import Path as P
    code = (P(__file__).parents[1] / 'app' / 'services' / 'prospeccion_repo.py').read_text()
    assert 'db.session' in code
    assert 'db.text(' in code
    assert 'import sqlite3' not in code
    assert 'import psycopg2' not in code


def test_repo_graceful_on_missing_tables():
    """_rows/_row/_scalar retornan datos vacíos (no excepción) si db.session.execute falla."""
    sys.path.insert(0, str(Path(__file__).parents[1]))
    from app.services import prospeccion_repo

    # Las funciones _rows, _row, _scalar ya capturan excepciones internamente.
    # Verificar que retornan valor vacío cuando db.session.execute lanza una excepción.
    exc = Exception("relation does not exist")

    with patch('app.services.prospeccion_repo.db') as mock_db:
        mock_db.session.execute.side_effect = exc
        mock_db.text = lambda s: s

        rows   = prospeccion_repo._rows("SELECT 1")
        row    = prospeccion_repo._row("SELECT 1")
        scalar = prospeccion_repo._scalar("SELECT 1", default='fallback')

    assert rows   == [], f"_rows debe retornar [] en error, retornó: {rows}"
    assert row    == {}, f"_row debe retornar {{}} en error, retornó: {row}"
    assert scalar == 'fallback', f"_scalar debe retornar default en error, retornó: {scalar}"
