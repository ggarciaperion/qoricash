# Prospección — Sincronizador y Enriquecimiento

**Commits del módulo**
| Commit | Descripción |
|--------|-------------|
| `94ddce53` | feat: módulo de historial de campaña con enriquecimiento comercial |
| `4fcfb097` | fix: autenticación obligatoria sin bypass en endpoints de importación |
| `8299d417` | feat: versionar sincronizador y enriquecimiento de prospectos |
| `09872022` | fix: estado por destino, upsert PostgreSQL, enriquecimiento vía API |

---

## Endpoints del servidor Flask (puerto 5002 local / Render en producción)

| Ruta | Método | Auth | Uso |
|------|--------|------|-----|
| `/agentes/api/prospeccion/sync-importar` | POST | `X-Sync-Key` | Importa `.log` / `_resultado.json` desde Mac vía multipart |
| `/agentes/api/prospeccion/sync-enrich`   | POST | `X-Sync-Key` | Upsert idempotente de registros enriquecidos desde Sheets |
| `/agentes/prospeccion`                   | GET  | sesión + rol  | Panel web de revisión |

**Clave de autenticación**: `SYNC_API_KEY` en `.env` del servidor = contenido de `~/.config/qoricash/sync_key` en la Mac.

---

## Scripts en la Mac (`~/Desktop/Prospeccion/`)

### `sincronizador_prospeccion.py`
Escanea `~/Desktop/Prospeccion/` en busca de archivos `.log` y `_resultado.json` nuevos o modificados y los envía a `sync-importar`.

```bash
# Modo normal (launchd lo llama cada 15 min)
python3 sincronizador_prospeccion.py

# Apuntar a Render
python3 sincronizador_prospeccion.py --url https://TU-APP.onrender.com/agentes/api/prospeccion/sync-importar

# Ver pendientes sin enviar
python3 sincronizador_prospeccion.py --dry-run

# Olvidar estado para un destino y re-enviar todo
python3 sincronizador_prospeccion.py --reset --url https://TU-APP.onrender.com/...
```

**Estado separado por destino** (`sincronizador_estado.json` formato v2):
```json
{ "version": 2, "destinos": {
    "http://localhost:5002/agentes/api/prospeccion/sync-importar": { "enviados": {...} },
    "https://TU-APP.onrender.com/agentes/api/prospeccion/sync-importar": { "enviados": {} }
}}
```
Archivos enviados a localhost **no** se omiten al enviar a Render.

### `enrich_camp_prospectos.py`
Lee PROSPECTOS_MASTER de Google Sheets y envía los registros enriquecidos a `sync-enrich`. Las credenciales OAuth de Sheets se quedan en la Mac.

```bash
# Enriquecer contra localhost
python3 enrich_camp_prospectos.py

# Enriquecer contra Render
python3 enrich_camp_prospectos.py --url https://TU-APP.onrender.com/agentes/api/prospeccion/sync-enrich

# Ver sin enviar
python3 enrich_camp_prospectos.py --dry-run
```

---

## LaunchAgent (automatización local)

**Plist instalado**: `~/Library/LaunchAgents/pe.qoricash.sincronizador.plist`  
**Intervalo**: cada 15 minutos  
**Script ejecutado**: `~/Desktop/Prospeccion/sincronizador_prospeccion.py`  
**Log**: `~/Desktop/Prospeccion/sincronizador.log`

```bash
# Activar
launchctl load ~/Library/LaunchAgents/pe.qoricash.sincronizador.plist

# Disparar manualmente
launchctl kickstart -k gui/$(id -u)/pe.qoricash.sincronizador

# Estado
launchctl list pe.qoricash.sincronizador

# Log en vivo
tail -f ~/Desktop/Prospeccion/sincronizador.log
```

### PENDIENTE — EPERM de macOS TCC

**Estado**: `launchd` no puede abrir `~/Desktop/Prospeccion/` — bloqueado por macOS TCC.  
**Binario a desbloquear**: `/Library/Developer/CommandLineTools/usr/bin/python3`

**Paso único en System Settings**:
> Ajustes del Sistema → Privacidad y seguridad → Acceso completo al disco  
> Clic en `+` → Cmd+Shift+G → pegar `/Library/Developer/CommandLineTools/usr/bin/python3` → Abrir

Una vez concedido, disparar manualmente y confirmar en el log:
```
[YYYY-MM-DD HH:MM:SS] Sincronizador QoriCash
  Archivos pendientes: N
  Endpoint: http://localhost:5002/...  [con clave]
  → archivo.log (X KB) [OK] N nuevos / M dup / 0 desc
```
**No dar por resuelto EPERM hasta ver esa salida real en el log.**

---

## Primer arranque en Render (logs históricos)

```bash
# 1. Agregar en Render → Environment → SYNC_API_KEY=<misma clave que sync_key local>
# 2. Sincronizar logs históricos (re-envío completo)
python3 sincronizador_prospeccion.py \
  --reset \
  --url https://TU-APP.onrender.com/agentes/api/prospeccion/sync-importar

# 3. Enriquecer prospectos
python3 enrich_camp_prospectos.py \
  --url https://TU-APP.onrender.com/agentes/api/prospeccion/sync-enrich
```

---

## Panel web (revisión local)

URL: `http://127.0.0.1:5002/agentes/prospeccion`  
Requiere sesión activa con rol `agente`, `admin` o `superadmin`.
