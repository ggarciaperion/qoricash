# Oficina Virtual — Coordinación T1 / T2 / T3

**Rama**: `feature/agentes-oficina-virtual`
**Commit base (último commiteado)**: `ddca82e9` feat(dashboard): Oficina Virtual v2

## Cambios pendientes (sin commit — en working tree)

| Archivo | Responsable | Cambio |
|---------|-------------|--------|
| `app/routes/agentes.py` | T1 | 403 estructurado (JSON/HTML), /dashboard sin queries ORM, ruta canónica, /inventario y /feature-flags |
| `app/services/mc_repo.py` | T1 | tc_updated_at fix Python 3.9, flag normalización a bool, is_demo, _is_demo_env |
| `app/services/agents/mail_agent.py` | T1 | SyntaxError en regex (literal newline) |
| `app/templates/agentes/dashboard.html` | T2 | secondaryAgents div, URL_INVENTARIO, is_demo check, ap-val--muted class, label "Con registro" |
| `run.py` | T1 | localhost auth bypass + session fix |
| `app/templates/agentes/403.html` | T1 | nuevo (sin commit) |
| `.env.mc_test` | T1 | nuevo (sin commit) |
| `OFICINA_VIRTUAL_COORDINATION.md` | T1 | nuevo (sin commit) |

**Terminal 3**: lo que está corriendo en localhost es el working tree, no el commit `ddca82e9`.
Los cambios sin commit arriba son parte de lo que se está probando.

---

## Servidor activo

**PID**: 16657
**URL**: http://127.0.0.1:5002
**Proceso**: `python3 -m flask run --port 5002 --no-reload --with-threads`
**ENV**: `.env.mc_test` → `DATABASE_URL=postgresql://localhost/qoricash_mc_test`

**Auth**: localhost auto-login como `mc_test` (Master) vía `request_loader` en `run.py`.
No se requiere login explícito desde 127.0.0.1.

---

## Cómo arrancar si el servidor no está activo

```bash
cd /Users/gianpierre/Desktop/Qoricash/Sistema/qoricash
set -a; source .env.mc_test; set +a
python3 -m flask run --port 5002 --no-reload --with-threads
```

**Auth desde navegador**: DNI `00000001` / contraseña `test123` (usuario `mc_test@test.local`, rol Master)
**Auth desde 127.0.0.1 automático**: requests desde localhost pasan como Master sin login explícito.

---

## Rutas de la Oficina Virtual

| Ruta | Descripción |
|------|-------------|
| `GET /agentes/dashboard` | Dashboard principal (sirve dashboard.html) |
| `GET /agentes/mission-control` | Alias (misma template) |
| `GET /agentes/mission_control` | → 301 → `/agentes/mission-control` |

---

## Contrato de API v2 (todos JSON, autenticado)

### `GET /agentes/api/v2/resumen`
Ejecutivo: TC, outreach_hoy, bandejas, sync, dry_run.

```json
{
  "query_at": "ISO8601",
  "env_note": "PostgreSQL (Render) | SQLite (local)",
  "cached": true,
  "tc": {
    "source": "runtime_config",
    "compra": "3.377",
    "venta": "3.381",
    "updated_at": "2026-10-21 15:03:08.22103-05",
    "fresco": false,
    "age_min": 2678
  },
  "outreach_hoy": {
    "source": "outreach_log",
    "enviados": 0,
    "fallidos": 0,
    "query_date": "2026-10-23"
  },
  "bandejas": [...],
  "sync": {...},
  "dry_run": false
}
```

**TC fresco**: `age_min < 180` (3 h). `fresco: null` = fecha no parseable.

### `GET /agentes/api/v2/agentes`
Estado de runs y heartbeats de los 8 agentes worker.

```json
{
  "agentes": [
    {
      "id": "outreach",
      "ultimo_run": {...},
      "heartbeat": {...},
      "cierre_registrado": true,
      "display_status": "ok|running|stale|sin_datos",
      "duration_s": 142
    }
  ]
}
```

**`cierre_registrado: false`** = `finished_at IS NULL` = el agente arrancó pero no cerró.
**`display_status: "running"`** = started_at existe, finished_at null, < 2h ago.
**`display_status: "stale"`** = started_at existe, finished_at null, > 2h ago (colgado).

### `GET /agentes/api/v2/historial?agente=<id>&limit=20`
Historial de runs de un agente específico.

### `GET /agentes/api/v2/prospecto/<id>`
Detalle completo de un prospecto: estado, historial de outreach, follow-ups, log.

### `GET /agentes/api/v2/feature-flags`
Flags de configuración del worker.

```json
{
  "disponible": true,
  "flags": {
    "scout_enabled": true,
    "followup_enabled": true,
    "response_monitor_enabled": true,
    "crm_bridge_enabled": false,
    "dry_run": false,
    "go_live_batch_limit": "50",
    "worker_instance": "render-worker-demo:99999",
    "flags_recorded_at": "2026-10-23T16:34:32.083799+00:00"
  },
  "flags_stale": false,
  "flags_age_min": 6
}
```

**Tipos**: flags booleanos (`scout_enabled`, etc.) → `true | false | null`.
**`flags_stale: true`** = registrados hace > 24 h (instancia antigua o worker caído).
**`disponible: false`** = sin claves `feature.*` en runtime_config (worker no arrancó con esta versión).

### `GET /agentes/api/v2/inventario`
Catálogo estático de 18 agentes (8 worker + 2 support + 8 Flask) enriquecido con evidencia dinámica de agent_runs/heartbeat.

```json
{
  "agentes": [
    {
      "ecosistema": "worker",
      "id": "worker.scout",
      "nombre": "Scout",
      "ejecutado_alguna_vez": true,
      "disponible": true,
      "flag_valor": true,
      "ultimo_run_at": "2026-10-13T...",
      "horario_conf": "06:00 Lima diario",
      "dependencias_codigo": ["google_sheets_api", "sunat_api"]
    }
  ]
}
```

### Errores (APIs)

**403** (rol insuficiente):
```json
{"error": "acceso denegado", "code": 403, "detalle": "Se requiere rol: Master, Presidente de Negocios"}
```

**500** (error en repo):
```json
{"error": "internal", "detalle": "..."}
```

**403 HTML** (página): `agentes/403.html` con badges de roles requeridos.

---

## Escenarios de demo en qoricash_mc_test

| Agente | Estado |
|--------|--------|
| outreach | Último run cerrado OK (Oct 22) |
| response | En ejecución sin cierre (simula colgado) |
| scout | Corriendo desde Oct 13 (muy stale) |
| scoring | Cerrado OK |
| TC | Desactualizado (Oct 21, `fresco: false`) |
| Feature flags | Registrados hoy (frescos), crm_bridge=false |

---

## Base de datos demo

**Nombre**: `qoricash_mc_test` (PostgreSQL local)
**Env file**: `.env.mc_test`
**Conexión**: `postgresql://localhost/qoricash_mc_test`

Tablas worker presentes: `agent_runs`, `agent_heartbeat`, `runtime_config`,
`ec_prospectos`, `outreach_log`, `bandeja_estado`, `suppression`, `lead_pipeline`, etc.

---

## Convenciones de datos

- Timestamps: ISO 8601 con zona horaria. `null` si no disponible.
- `env_note: "PostgreSQL (Render)"` = DB con esquema completo (prod o demo).
  `env_note: "SQLite (local)"` = sin tablas worker, todos los agentes `disponible: false`.
- Campos `*_error` / `nota` = información de diagnóstico, no bloquean el render.
- `fresco: null` = no se pudo calcular la antigüedad del dato.
- Sin fallbacks silenciosos: si una tabla falla → campo con `error` explícito.

---

## Archivos clave

```
app/
  routes/agentes.py          # Rutas Flask — canonical: /agentes/mission-control
  services/mc_repo.py        # Repositorio v2 — todas las queries
  templates/agentes/
    dashboard.html           # Oficina Virtual v2 (Terminal 2)
    403.html                 # Página de acceso denegado
    dashboard_v1_backup.html # Respaldo
```
