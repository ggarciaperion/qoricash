# Guía de integración local T1 → T3

**Para:** equipo motor Mac (T1)
**Estado receptor:** listo en `localhost:5099` con DB `qoricash_sync_test`
**Fecha preparación:** 2026-11-11

---

## 1. Estado actual de la DB de pruebas

| Campo               | Valor                        |
|---------------------|------------------------------|
| DB                  | `qoricash_sync_test` (local) |
| Revisión Alembic    | `ec07_rebote_detectado_en`   |
| Lote operativo      | `2026-11-10-B` (es_prueba=0) |
| Seleccionados       | 300                          |
| Enviados            | 0                            |
| Rebotes almacenados | 0                            |
| `rebote_detectado_en` | columna TIMESTAMPTZ presente |

---

## 2. Iniciar el receptor local

Desde el directorio raíz del panel:

```bash
cd /Users/gianpierre/Desktop/Qoricash/Sistema/qoricash

# Cargar entorno de prueba local (SYNC_SECRET, DATABASE_URL, etc.)
# FLASK_CLI_ONLY=true suprime el scheduler de eventlet (no bloquea el server)
export $(grep -v '^#' .env.sync_test | xargs)

python3 run.py
```

El receptor escucha en `http://localhost:5099`.
Endpoints disponibles: `POST /api/sync/lote`, `POST /api/sync/agent`, `POST /api/sync/heartbeat`, `GET /api/sync/agents`.

### Variables necesarias en `.env.sync_test`

```
DATABASE_URL=postgresql://localhost/qoricash_sync_test
SYNC_SECRET=<SYNC_SECRET-de-.env.sync_test>
FLASK_CLI_ONLY=true
DEV_AUTO_LOGIN=false
SESSION_COOKIE_NAME=qori_sync_session
REMEMBER_COOKIE_NAME=qori_sync_remember
```

> **Nota:** `FLASK_CLI_ONLY=true` es obligatorio. Sin él, `eventlet.spawn()` bloquea el
> servidor Flask de desarrollo y los requests no responden.

---

## 3. Verificar conectividad (sin modificar datos)

```bash
export SYNC_SECRET="<SYNC_SECRET-de-.env.sync_test>"
BASE="http://localhost:5099"

# Ping
curl -s -X POST "$BASE/api/sync/heartbeat" \
  -H "Authorization: Bearer $SYNC_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"ts":"2026-11-11T00:00:00Z","origen":"motor_sync/1.0"}' | python3 -m json.tool
# Esperado: {"status":"ok","ts":"..."}

# Verificar agentes (sin auth)
curl -s "$BASE/api/sync/agents" | python3 -m json.tool
# Esperado: {"agents":[],"threshold_min":5}
```

---

## 4. Enviar heartbeat del scheduler

Configurar en `motor_sync.py` (o `scheduler_lotes.py`) para que llame cada 60 s:

```bash
curl -s -X POST "$BASE/api/sync/agent" \
  -H "Authorization: Bearer $SYNC_SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "agent":    "scheduler_lotes",
    "status":   "idle",
    "dry_run":  true,
    "hostname": "mac-local"
  }' | python3 -m json.tool
# Esperado: {"status":"ok","agent":"scheduler_lotes"}
```

Tras esto, `GET /api/sync/agents` mostrará el scheduler con `"online": true`.

---

## 5. Enviar snapshot del lote `2026-11-10-B`

Usar el snapshot que T1 ya tiene en SQLite. El receptor acepta el payload completo
definido en `CONTRATO_SYNC_T1.md`. Ejemplo mínimo de verificación de rebote:

```bash
# Snapshot con 1 item rebotado (para verificar rebote_detectado_en)
curl -s -X POST "$BASE/api/sync/lote" \
  -H "Authorization: Bearer $SYNC_SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "schema_version": "1.0",
    "emitido_en": "2026-11-11T10:00:00Z",
    "lote": {
      "lote_id":          "2026-11-10-B",
      "fuente_sheet_id":  "real-sheet-id",
      "fuente_tab":       "Hoja1",
      "fecha_creacion":   "2026-11-10T14:00:00Z",
      "creado_por":       "scheduler_lotes",
      "total_candidatos": 350,
      "total_elegibles":  300,
      "total_enviados":   0,
      "aceptados_pendientes": 0,
      "estado":           "pendiente",
      "dry_run":          true,
      "es_prueba":        false
    },
    "items": [
      {
        "id":                   1001,
        "email":                "contacto@empresa.com",
        "ruc":                  "20123456789",
        "razon_social":         "Empresa SAC",
        "sector":               "Manufactura",
        "bandeja":              "gerencia",
        "bandeja_asignada":     "gerencia",
        "estado_seleccion":     "elegible",
        "estado_envio":         "rebotado",
        "estado_validacion":    "invalido",
        "fecha_envio":          "2026-11-10T22:00:00Z",
        "rebote_tipo":          "hard",
        "rebote_motivo":        "550 no such user",
        "rebote_detectado_en":  "2026-11-11T09:00:00Z"
      }
    ]
  }' | python3 -m json.tool
# Esperado: {"items_procesados":1,"lote_id":"2026-11-10-B","status":"ok"}
```

### Verificar en la DB que se guardó

```bash
psql postgresql://localhost/qoricash_sync_test -c "
  SELECT email, estado_envio, rebote_tipo, rebote_motivo,
         rebote_detectado_en, fecha_envio
  FROM ec_lote_items li
  JOIN ec_lotes l ON l.id = li.lote_id
  WHERE l.lote_id = '2026-11-10-B'
    AND li.rebote_tipo IS NOT NULL
  LIMIT 5;
"
```

Esperado:
- `rebote_tipo = 'hard'`
- `rebote_motivo = '550 no such user'`
- `rebote_detectado_en = 2026-11-11 04:00:00-05:00` (UTC-5 Lima)
- `fecha_envio = 2026-11-10 17:00:00-05:00` (preservada, no borrada)

---

## 6. Verificar que las métricas del panel reflejan los cambios

Una vez enviado el snapshot, consultar:

```bash
# Auth: usar cookies de sesión del panel (login web) o token de sesión
# Acceder desde el navegador: http://localhost:5099/agentes
# O llamar directo al endpoint (requiere sesión):
# GET /api/prospeccion/pipeline-cards
```

El panel mostrará:
- Rebotes detectados hoy: 1 (si `rebote_detectado_en` es hoy Lima)
- Rebotes acumulados: 1
- Enviados hoy: 0 (dry_run=true)
- Pendientes del lote: 299 (1 rebotado, `fecha_envio` preservada pero no cuenta como enviado hoy por dry_run)

---

## 7. Verificar lote `2026-11-10-B` sin contaminar

El lote `2026-11-10-B` tiene `es_prueba=0` y `dry_run=true`. Los snapshots con
`"es_prueba": true` NO modifican este lote ni afectan métricas operativas.

Para limpiar los rebotes de prueba después de la integración:

```bash
psql postgresql://localhost/qoricash_sync_test -c "
  UPDATE ec_lote_items SET
    rebote_tipo = NULL,
    rebote_motivo = NULL,
    rebote_detectado_en = NULL,
    estado_envio = 'pendiente',
    fecha_envio = NULL
  WHERE lote_id = (SELECT id FROM ec_lotes WHERE lote_id = '2026-11-10-B')
    AND rebote_tipo IS NOT NULL;
"
```

---

## 8. SYNC_SECRET en producción

En Render, agregar la variable de entorno **antes** del deploy:
`SYNC_SECRET` → valor generado con `python3 -c "import secrets; print(secrets.token_hex(32))"`

El valor del `.env.sync_test` local es **solo para desarrollo local**.
No usar ese valor en producción.
