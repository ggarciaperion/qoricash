# Contrato de Integración T1 → T3 (Receptor Sync)

**Versión:** 1.0
**Fecha:** 2026-11-11
**Propietario panel (T3):** equipo Qoricash
**Propietario motor (T1):** motor Mac local

---

## 1. Resumen

El motor Mac (T1) sincroniza su estado hacia el panel Render (T3) vía HTTP.
El panel almacena en PostgreSQL y presenta métricas en tiempo real.
Comunicación: motor → panel (unidireccional). El panel nunca escribe de vuelta al motor.

---

## 2. URL base

| Entorno    | URL                                      |
|------------|------------------------------------------|
| Producción | `https://qoricash.onrender.com`          |
| Local T3   | `http://localhost:5099`                  |

---

## 3. Autenticación

Todos los endpoints (excepto `GET /api/sync/agents`) requieren:

```
Authorization: Bearer <SYNC_SECRET>
```

`SYNC_SECRET` es una cadena hexadecimal de 64 caracteres generada con:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

- En T3 (Render): variable de entorno `SYNC_SECRET`
- En T1 (motor Mac): exportar `SYNC_SECRET` antes de lanzar `motor_sync.py`

La comparación usa `hmac.compare_digest` — timing-safe.
Si `SYNC_SECRET` no está configurada en T3, **todos los requests retornan 401**.

---

## 4. Endpoints

### 4.1 `POST /api/sync/lote` — Estado completo de un lote

#### Headers
```
Content-Type: application/json
Authorization: Bearer <SYNC_SECRET>
```

#### Payload
```json
{
  "schema_version": "1.0",
  "emitido_en": "2026-11-10T23:30:00+00:00",
  "lote": {
    "lote_id":                  "2026-11-10-B",
    "fuente_sheet_id":          "1BxiMVs...",
    "fuente_tab":               "Hoja1",
    "fecha_creacion":           "2026-11-10T14:00:00+00:00",
    "creado_por":               "scheduler_lotes",
    "total_candidatos":         350,
    "total_elegibles":          300,
    "total_enviados":           0,
    "aceptados_pendientes":     0,
    "estado":                   "pendiente",
    "dry_run":                  true,
    "es_prueba":                false,
    "seleccion_completada_en":  "2026-11-10T14:05:00+00:00",
    "validacion_completada_en": "2026-11-10T14:20:00+00:00",
    "asignacion_completada_en": null,
    "supresion_json":           "{\"email\":5,\"dominio\":2}"
  },
  "items": [
    {
      "id":                   1001,
      "email":                "contacto@empresa.com",
      "ruc":                  "20123456789",
      "razon_social":         "Empresa SAC",
      "sector":               "Manufactura",
      "distrito":             "Miraflores",
      "bandeja":              "gerencia",
      "bandeja_asignada":     "gerencia",
      "estado_seleccion":     "elegible",
      "estado_envio":         "pendiente",
      "estado_validacion":    "valido",
      "fecha_envio":          null,
      "rebote_tipo":          null,
      "rebote_motivo":        null,
      "rebote_detectado_en":  null
    }
  ]
}
```

#### Campos requeridos
| Campo           | Tipo     | Descripción                              |
|-----------------|----------|------------------------------------------|
| `schema_version`| `"1.0"`  | Versión del contrato (literal)           |
| `emitido_en`    | ISO 8601 | Timestamp UTC del snapshot               |
| `lote.lote_id`  | string   | Identificador único del lote             |

#### Campos de item — semántica de rebotes
| Campo                 | Tipo              | Regla                                        |
|-----------------------|-------------------|----------------------------------------------|
| `estado_validacion`   | `valido\|invalido\|riesgo\|no_verificado\|sin_validar` | Estado del email validator |
| `rebote_tipo`         | `hard\|soft\|reputacion\|null` | Solo uno de los tres valores aceptados; cualquier otro → almacenado como `NULL` |
| `rebote_motivo`       | string \| null    | SMTP response code + descripción (ej. `"550 no such user"`) |
| `rebote_detectado_en` | ISO 8601 \| null  | Timestamp UTC cuando T1 detectó el rebote    |
| `fecha_envio`         | ISO 8601 \| null  | Timestamp UTC de aceptación por Gmail. Se **preserva** aunque `estado_envio` cambie a `rebotado` |

#### Respuestas
| HTTP | `status`     | Significado                                                   |
|------|--------------|---------------------------------------------------------------|
| 200  | `"ok"`       | Lote guardado. `items_procesados`: N items actualizados       |
| 200  | `"ok"`       | Idempotente: mismo `emitido_en` ya almacenado, `items_procesados=0` |
| 400  | —            | Payload inválido o campo faltante                             |
| 401  | —            | SYNC_SECRET incorrecto o ausente                              |
| 409  | `"rejected"` | Snapshot más antiguo que el último almacenado (last-write-wins) |
| 500  | —            | Error interno del panel (reintentar)                          |

#### Ejemplo respuesta 200
```json
{
  "status": "ok",
  "lote_id": "2026-11-10-B",
  "items_procesados": 300
}
```

---

### 4.2 `POST /api/sync/agent` — Heartbeat del scheduler

Enviar **cada 60 segundos**. El panel muestra "desconectado" si no recibe señal en 5 minutos.

#### Payload
```json
{
  "agent":    "scheduler_lotes",
  "status":   "idle",
  "dry_run":  true,
  "hostname": "MacBook-Pro-Gian"
}
```

| Campo      | Tipo    | Valores                              |
|------------|---------|--------------------------------------|
| `agent`    | string  | `"scheduler_lotes"` (acordado)       |
| `status`   | string  | `"idle"` \| `"running"` \| `"error"` |
| `dry_run`  | boolean | `true` si envíos deshabilitados      |
| `hostname` | string  | Opcional, para diagnóstico           |

#### Respuesta 200
```json
{"status": "ok", "agent": "scheduler_lotes"}
```

---

### 4.3 `POST /api/sync/heartbeat` — Ping de conectividad

Ping simple para verificar que la URL base responde antes de enviar un lote.

#### Payload
```json
{
  "ts":     "2026-11-10T23:30:00+00:00",
  "origen": "motor_sync/1.0"
}
```

#### Respuesta 200
```json
{"status": "ok", "ts": "2026-11-10T23:30:05+00:00"}
```

---

### 4.4 `GET /api/sync/agents` — Lista agentes (sin auth)

Usado por el panel frontend para mostrar el estado de conectividad de cada agente.
No requiere `Authorization`.

#### Respuesta 200
```json
{
  "agents": [
    {
      "agent":     "scheduler_lotes",
      "status":    "idle",
      "last_seen": "2026-11-10T23:30:00+00:00",
      "dry_run":   1,
      "online":    true,
      "edad_min":  1
    }
  ],
  "threshold_min": 5
}
```

---

## 5. Arranque del receptor — prueba local T1

### 5.1 Verificar que el panel está en línea

```bash
curl -s http://localhost:5099/api/sync/agents | python3 -m json.tool
```

Esperado: `{"agents": [], "threshold_min": 5}` (lista vacía si aún no hay heartbeats)

### 5.2 Verificar autenticación (heartbeat ping)

```bash
export SYNC_SECRET="<tu-secret-aqui>"
curl -s -X POST http://localhost:5099/api/sync/heartbeat \
  -H "Authorization: Bearer $SYNC_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"ts":"2026-11-11T00:00:00Z","origen":"motor_sync/1.0"}'
```

Esperado: `{"status":"ok","ts":"..."}`
Error 401: SYNC_SECRET no coincide o no configurado en T3.

### 5.3 Enviar heartbeat del scheduler

```bash
curl -s -X POST http://localhost:5099/api/sync/agent \
  -H "Authorization: Bearer $SYNC_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"agent":"scheduler_lotes","status":"idle","dry_run":true,"hostname":"mac-local"}'
```

Tras esto, el panel mostrará la píldora "scheduler" en verde.

### 5.4 Enviar snapshot de lote (prueba mínima)

```bash
curl -s -X POST http://localhost:5099/api/sync/lote \
  -H "Authorization: Bearer $SYNC_SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "schema_version": "1.0",
    "emitido_en": "2026-11-11T00:00:00Z",
    "lote": {
      "lote_id": "PRUEBA-T1",
      "fuente_sheet_id": "test",
      "fuente_tab": "Hoja1",
      "fecha_creacion": "2026-11-11T00:00:00Z",
      "creado_por": "t1_test",
      "total_candidatos": 1,
      "total_elegibles": 1,
      "total_enviados": 0,
      "aceptados_pendientes": 0,
      "estado": "pendiente",
      "dry_run": true,
      "es_prueba": true
    },
    "items": [
      {
        "id": 1,
        "email": "test@example.com",
        "ruc": "20000000000",
        "razon_social": "Test SAC",
        "sector": "Test",
        "bandeja": "test",
        "bandeja_asignada": "test",
        "estado_seleccion": "elegible",
        "estado_envio": "pendiente",
        "estado_validacion": "valido",
        "fecha_envio": null,
        "rebote_tipo": null,
        "rebote_motivo": null,
        "rebote_detectado_en": null
      }
    ]
  }'
```

Esperado: `{"status":"ok","lote_id":"PRUEBA-T1","items_procesados":1}`

**Nota:** `es_prueba: true` excluye este lote de todas las métricas operativas del panel.

---

## 6. Reglas de consistencia

### Timestamps
- Todos los campos de timestamp aceptan ISO 8601 con offset UTC (`Z` o `+00:00`).
- El panel los convierte internamente a `TIMESTAMPTZ` PostgreSQL.
- El panel muestra fechas en zona `America/Lima` (UTC-5).

### last-write-wins
- El campo `emitido_en` del payload raíz determina qué snapshot prevalece.
- Si T3 ya almacenó un `emitido_en` más reciente, retorna HTTP 409.
- Si T3 ya almacenó el mismo `emitido_en`, retorna HTTP 200 idempotente.

### Rebotes — preservación de historial
- `fecha_envio` **nunca** se borra cuando `estado_envio` cambia a `rebotado`.
- El conteo "enviados hoy" usa `fecha_envio IS NOT NULL AND dry_run=FALSE`.
- El conteo "rebotes hoy" usa `rebote_detectado_en` (Lima date), no `fecha_envio`.
- `rebote_tipo` fuera de `{hard, soft, reputacion}` → almacenado como `NULL`.

### es_prueba
- `es_prueba: true` (o `1`) → lote excluido de: seleccionados, válidos, enviados hoy, rebotes.
- `dry_run: true` en un lote real (es_prueba=false) → item contado en "pendientes del lote" pero NO en "enviados hoy" (dry_run=FALSE requerido).

---

## 7. Schema mínimo de la DB (T3 recibe, no impone)

Tabla `ec_lote_items` — columnas relevantes para rebotes (Alembic ec07):

```sql
rebote_tipo         TEXT          -- CHECK: hard|soft|reputacion o NULL
rebote_motivo       TEXT          -- SMTP response o descripción
rebote_detectado_en TIMESTAMPTZ  -- UTC timestamp de detección
fecha_envio         TIMESTAMPTZ  -- Preservado aunque estado_envio='rebotado'
estado_validacion   TEXT          -- valido|invalido|riesgo|no_verificado|sin_validar
```

Migración aplicada: `ec07_rebote_detectado_en` (Alembic, idempotente).

---

## 8. Verificación post-deploy

```bash
# 1. Confirm endpoints responden
curl -s https://qoricash.onrender.com/api/sync/agents

# 2. Confirm ec07 en alembic_version
psql $DATABASE_URL -c "SELECT version_num FROM alembic_version;"
# Esperado: ec07_rebote_detectado_en

# 3. Confirm columna en DB de producción
psql $DATABASE_URL -c "
  SELECT column_name, data_type FROM information_schema.columns
  WHERE table_name='ec_lote_items' AND column_name='rebote_detectado_en';
"
# Esperado: rebote_detectado_en | timestamp with time zone
```
