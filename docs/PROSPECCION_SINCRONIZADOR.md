# Prospección — Sincronizador y Enriquecimiento

**Commits del módulo**
| Commit | Descripción |
|--------|-------------|
| `94ddce53` | feat: módulo de historial de campaña con enriquecimiento comercial |
| `4fcfb097` | fix: autenticación obligatoria sin bypass en endpoints de importación |
| `8299d417` | feat: versionar sincronizador y enriquecimiento de prospectos |
| `09872022` | fix: estado por destino, upsert PostgreSQL, enriquecimiento vía API |
| `7e1415eb` | docs: nota de continuidad inicial |
| ver git log | feat: cola en Application Support, sync-evento, sin FDA |

---

## Endpoints del servidor Flask (puerto 5002 local / Render en producción)

| Ruta | Método | Auth | Uso |
|------|--------|------|-----|
| `POST /agentes/api/prospeccion/sync-evento`   | POST | `X-Sync-Key` | **Vía principal (nueva)**: eventos directos desde campañas / cola |
| `POST /agentes/api/prospeccion/sync-importar` | POST | `X-Sync-Key` | Legado: archivos `.log` / `_resultado.json` vía multipart |
| `POST /agentes/api/prospeccion/sync-enrich`   | POST | `X-Sync-Key` | Upsert enriquecimiento desde Sheets |
| `GET  /agentes/prospeccion`                   | GET  | sesión + rol  | Panel web de revisión |

**Clave de autenticación**: `SYNC_API_KEY` en `.env` del servidor = `~/.config/qoricash/sync_key` en la Mac.

---

## Arquitectura de nuevos eventos (sin FDA)

```
Campaña (Mac, terminal)
    │ send_evento()  ←── campaign_sink.py
    │
    ├─ Flask disponible ──► POST /sync-evento ──► camp_envio (DB)
    │
    └─ Flask no disponible ──► ~/Library/Application Support/qoricash/queue/evt_*.json
                                          │
                              launchd (c/15 min, sin FDA)
                                          │
                              sincronizador.py (Application Support)
                                          │
                                POST /sync-evento ──► camp_envio (DB)
                                          │
                              Elimina evt_*.json confirmados
```

**Archivos históricos en `~/Desktop/Prospeccion/`** permanecen intactos hasta autorización expresa.
No se borran hasta confirmar transferencia completa.

---

## Infraestructura en Application Support (`~/Library/Application Support/qoricash/`)

| Archivo / Dir | Función |
|---------------|---------|
| `sincronizador.py` | Drainer de cola — launchd lo ejecuta c/15 min |
| `queue/evt_*.json` | Cola de reintentos (solo eventos sin confirmación) |
| `sincronizador.log` | Log rotado (500 KB × 3 archivos) |
| `launchd.log` | Salida cruda de launchd (errores no capturados) |
| `email_enviados_*.json` | Dedup 48h de campana_prospeccion_nueva_base |

**No requiere Full Disk Access** — Application Support es accesible sin TCC para launchd.

---

## Scripts en la Mac (`~/Desktop/Prospeccion/`)

### `campaign_sink.py` ← nuevo
Librería importada por las campañas. `send_evento(record)` intenta POST a `/sync-evento`;
si el servidor no está disponible, escribe a la cola en Application Support.

```python
from campaign_sink import send_evento
send_evento({
    'email': 'contacto@empresa.com',
    'empresa': 'Empresa S.A.',
    'bandeja': 'ggarcia@qoricash.pe',
    'proceso': 'campana_150',
    'enviado_at': '2026-10-25 09:30:00',
    'resultado_log': 'OK',
    'fuente_archivo': 'campana_150_2026-10-25.log',  # hash compatible con imports históricos
})
```

### `sincronizador.py` (en Application Support)
```bash
# Ver cola pendiente
python3 ~/Library/Application\ Support/qoricash/sincronizador.py --dry-run

# Apuntar a Render
python3 ~/Library/Application\ Support/qoricash/sincronizador.py \
  --url https://TU-APP.onrender.com/agentes/api/prospeccion/sync-evento
```

### LaunchAgent
**Plist**: `~/Library/LaunchAgents/pe.qoricash.sincronizador.plist`
**Intervalo**: 900 s (15 min) | **Sin FDA** | **Ejecución verificada**: 2026-10-25

```bash
# Log operativo
tail -f ~/Library/Application\ Support/qoricash/sincronizador.log

# Disparar manualmente
launchctl kickstart -k gui/$(id -u)/pe.qoricash.sincronizador

# Estado
launchctl list pe.qoricash.sincronizador
```

**Ejecución real confirmada (2026-10-25 01:25)**:
```
2026-10-25 01:25:02 INFO Sincronizador QoriCash — 1 eventos pendientes | http://localhost:5002/...
2026-10-25 01:25:02 INFO   lote 1-1: 1 confirmados y eliminados de la cola
2026-10-25 01:25:02 INFO Total confirmados: 1 | En cola: 0
LastExitStatus = 0
```

---

## Transferencia de históricos a Render (cuando se autorice deploy)

```bash
# 1. Agregar en Render env vars: SYNC_API_KEY=<misma clave que sync_key local>
# 2. Logs históricos (archivos .log / .json en Desktop — legado)
python3 ~/Desktop/Prospeccion/sincronizador_prospeccion.py \
  --reset \
  --url https://TU-APP.onrender.com/agentes/api/prospeccion/sync-importar

# 3. Nuevos eventos (cola en Application Support)
python3 ~/Library/Application\ Support/qoricash/sincronizador.py \
  --url https://TU-APP.onrender.com/agentes/api/prospeccion/sync-evento

# 4. Enriquecimiento desde Sheets
python3 ~/Desktop/Prospeccion/enrich_camp_prospectos.py \
  --url https://TU-APP.onrender.com/agentes/api/prospeccion/sync-enrich
```

**No conectar a Render hasta autorización.** Los históricos del Desktop se conservan hasta confirmar transferencia íntegra y autorización explícita de borrado.

---

## Panel web (revisión local)

URL: `http://127.0.0.1:5002/agentes/prospeccion`
Requiere sesión activa con rol `agente`, `admin` o `superadmin`.
