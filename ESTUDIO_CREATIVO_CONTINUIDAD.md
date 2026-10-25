# Estudio Creativo — Nota de Continuidad (25 Oct 2026)
## Estado: implementación local cerrada — pendiente revisión editorial y decisión de deploy

## Estado del servidor
- **Puerto**: 5002
- **Proceso**: `python3 -m gunicorn --worker-class eventlet -w 1 --bind 127.0.0.1:5002 --timeout 300 run:app`
- **Env**: `.env` (contiene ANTHROPIC_API_KEY)
- **DB**: SQLite `instance/qoricash_local.db`
- **Log**: `/tmp/qoricash_gunicorn.log`

### Por qué gunicorn (NO flask run)
`run.py` llama `eventlet.monkey_patch()`. Con `flask run`, el hub de eventlet no corre
→ los sockets patched bloquean indefinidamente. Con `gunicorn --worker-class eventlet`,
el hub sí corre → SDK de Anthropic + urllib funcionan correctamente.

### Cómo arrancar si el servidor no está activo
```bash
cd /Users/gianpierre/Desktop/Qoricash/Sistema/qoricash
set -a && source .env && set +a
python3 -m gunicorn --worker-class eventlet -w 1 --bind 127.0.0.1:5002 --timeout 300 run:app > /tmp/qoricash_gunicorn.log 2>&1 &
sleep 8
curl -s -o /dev/null -w "%{http_code}" http://localhost:5002/contenido/hoy
```

## Rutas del módulo
- `http://localhost:5002/contenido/hoy` — **Entrega de Hoy** (pantalla principal diaria)
- `http://localhost:5002/contenido/agentes` — panel de agentes + iniciar pipelines
- `http://localhost:5002/contenido/` — lista de propuestas
- `http://localhost:5002/contenido/pipeline/<id>` — detalle de pipeline
- `http://localhost:5002/contenido/propuesta/<id>` — detalle de propuesta
- `http://localhost:5002/contenido/calendario` — propuestas planificadas
- `http://localhost:5002/contenido/configuracion` — ficha de marca

## Sistema diario implementado (25 Oct 2026)

### Pipeline tipo "diario" (5 etapas)
```
investigador → editor → creativo → productor → revisor
```
1. **Investigador** (modo diario): 3 noticias categorizadas (nacional/internacional/mercados), últimas 48h → 7 días
2. **Editor** (modo diario): 3 posts LinkedIn 80-140 palabras, uno por noticia
3. **Creativo** (modo diario): 3 propuestas comerciales con audiencia rotativa por día del mes
4. **Productor** / Director Visual (modo diario): prompts Gemini/Flow para las 6 piezas, SIN Pillow
5. **Revisor** (modo diario): revisa 6 piezas, asigna `resource_status`, indica correcciones

### Modelos nuevos
- `EntregaDiaria` (tabla `entregas_diarias`): registro diario único, FK a ContentPipeline
- `ContentProposal` nuevos campos: `pipeline_id`, `delivery_type`, `noticia_category`, `resource_status`, `revisor_notas`, `correcciones`, `retry_count`

### Estados de resource_status
`prompt_listo` → `recurso_pendiente` / `recurso_cargado` → `pendiente_aprobacion` → `aprobado` → `planificado`

### APIs diarias
| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/contenido/hoy` | GET | Vista principal Entrega de Hoy |
| `/contenido/api/generar-diario` | POST | Disparo asíncrono (background thread) |
| `/contenido/api/generar-diario-sync` | POST | Disparo síncrono (para scheduler/cron) |
| `/contenido/api/propuesta/<id>/aprobar-diario` | POST | Aprueba pieza, resource_status=aprobado |
| `/contenido/api/propuesta/<id>/planificar-diario` | POST | Planifica pieza, resource_status=planificado |
| `/contenido/api/propuesta/<id>/cargar-recurso-diario` | POST | Sube imagen/video, resource_status=recurso_cargado |

## Scheduler — cómo se inicia y recupera

### Con el comando real de Gunicorn (local y Render)
```
python3 -m gunicorn --worker-class eventlet -w 1 --bind 127.0.0.1:5002 --timeout 300 run:app
```
- `preload_app=False` (default): el worker importa `run.py` → ejecuta `eventlet.spawn_after(2, start_all_schedulers)`.
- A los ~2 s del fork: `start_all_schedulers()` llama `daily_scheduler.spawn(app)` → lanza `run_scheduler_loop` en un greenlet del hub de eventlet.
- **No** hace falta `python run.py`; con gunicorn funciona exactamente igual.

Para desactivar: `export ESTUDIO_DIARIO_AUTO=false` antes de arrancar.

### Ventanas de generación
| Escenario | Comportamiento |
|-----------|---------------|
| Arranca 5:00–7:55 AM sin entrega → genera de inmediato (startup recovery normal) |
| Arranca 5:00–7:55 AM y entrega ya existe → marca `_fired_today`, no vuelve a lanzar |
| Loop normal 5:00–7:55 AM → lanza la entrega una vez (`_fired_today` evita repetición) |
| **Arranca después de 7:55 sin entrega** → genera una vez, `entrega.notas` += `[entrega atrasada]` |

### Control de duplicados (verificado)
- **DB**: `EntregaDiaria.fecha UNIQUE` — cualquier segundo worker o reinicio que intente crear la entrega falla silenciosamente (ya existe).
- **Memoria**: `_fired_today` flag en el greenlet — el loop no reintenta en el mismo día.
- Conclusión: seguro con `workers=1` (configuración de Render). Con `workers>1` la DB es la única garantía (race condition pequeña en el commit; aceptable).

### Render producción — Opción Cron Job ($1/mes, más robusto)
Crear Cron Job en Render:
```
curl -s -X POST https://<app>.onrender.com/contenido/api/generar-diario-sync \
  -H "Content-Type: application/json" \
  -H "X-Cron-Token: <ESTUDIO_CRON_TOKEN>" \
  -d '{}'
```
- Schedule: `0 10 * * *` (10:00 UTC = 5:00 AM Lima)
- Timeout: 600 s
- **ESTUDIO_CRON_TOKEN es obligatorio** en las variables de entorno de Render.

## Autenticación de endpoints

| Endpoint | Protección |
|----------|-----------|
| `/contenido/api/generar-diario` (async, manual) | Sesión + rol + CSRF — nunca expone el token cron |
| `/contenido/api/generar-diario-sync` (cron externo) | `X-Cron-Token` requerido; 503 si `ESTUDIO_CRON_TOKEN` no está configurado; 401 si token ausente o incorrecto |

## Commits de esta etapa
| Hash | Rama | Descripción |
|------|------|-------------|
| `92e93341` | master | feat: módulo Estudio Creativo completo (pipeline diario, 5 agentes, vistas, migraciones) |
| `2b74e6c1` | master | fix: auth obligatoria en cron, categorías sin forzado posicional, scheduler tardío |
| `2bb5818d` | cleanup/prospeccion-inventario | fix: app context en OS threads, subprocess para llamadas Claude (infra compartida) |
| `1c6b8d24` | cleanup/prospeccion-inventario | feat: nueva dirección visual fotográfica + propuestas WhatsApp y viajes |
| `f37cb165` | **feature/estudio-creativo** | cherry-pick de `1c6b8d24` — rama propia de Estudio Creativo |

## Coordinación de ramas
| Rama | Propósito | Estado |
|------|-----------|--------|
| **`deploy/estudio-creativo`** | Producción Render — solo Estudio Creativo | Pusheado, esperando activación en dashboard |
| **`feature/estudio-creativo`** | Desarrollo del módulo | Actualizado con scheduler 6:30 AM |
| `cleanup/prospeccion-inventario` | Rama Terminal 2 (Prospección) | Sin cambios de Prospección |
| `master` | Base — Prospección no desplegada aún | No modificado |

**Regla**: futuros cambios de Estudio Creativo van a `feature/estudio-creativo`; merges a `deploy/estudio-creativo` para producción.

## Deploy a Render — instrucciones pendientes

La rama `deploy/estudio-creativo` (HEAD: `b08810a6`) está en GitHub. Para activar el deploy:

**Opción A (recomendada):** En Render dashboard → servicio `qoricash` → Settings →
"Branch" → cambiar a `deploy/estudio-creativo` → Save → Click "Manual Deploy".

**Opción B:** Si el servicio usa Blueprint sync: Render dashboard → Blueprint →
"Sync" → seleccionar `deploy/estudio-creativo`.

**Variable secreta requerida:** Antes del deploy, en Render dashboard → Environment →
agregar `ESTUDIO_CRON_TOKEN` con un valor aleatorio (solo si se usará el endpoint cron externo).
Generarlo con: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`
Si solo se usa el scheduler interno, esta variable puede dejarse vacía o ausente.

**Commit que se desplegará:** `b08810a6` — render.yaml con branch + vars Estudio.

## Scheduler en producción (configurado en deploy/estudio-creativo)
| Evento | Hora Lima | Comportamiento |
|--------|-----------|---------------|
| Generación inicial | 6:30 AM | Pipeline completo: investigador → editor → creativo → productor → revisor |
| Fin de ventana | 7:25 AM | No se inician nuevas generaciones completas |
| Comprobación | 7:30 AM | Si la entrega no es `listo`, reintenta solo etapas fallidas (máx 1 vez) |
| Deadline visible | 8:00 AM | `/contenido/hoy` muestra `listo`, `parcial` (Entrega incompleta) o `error` |
| Recuperación | arranque | Si no hay entrega del día: genera de inmediato (si en ventana) o atrasada (si después) |

**Funcionamiento en Render (gunicorn + eventlet):**
- `gunicorn -c gunicorn_config.py run:app`
- `run.py` importado por cada worker → `eventlet.spawn_after(2, start_all_schedulers)`
- Scheduler corre en un greenlet propio dentro del worker
- No depende del usuario ni del panel — completamente autónomo
- Requiere `ESTUDIO_DIARIO_AUTO=true` (valor por defecto)

## Estado al cierre de la sesión de correcciones (25 Oct 2026)
- **Pipeline #36**: `parcial` — 5 etapas completadas, 2 noticias + 3 comerciales.
  - `mercados` faltó por DNS timeouts en feeds de Yahoo Finance/noticias ese momento.
  - Código correcto; `parcial` es estado esperado cuando una categoría no tiene feed disponible.
- Panel disponible en `http://localhost:5002/contenido/hoy` para revisión editorial.
- No se hizo push ni deploy.

## Fix técnico crítico aplicado en esta sesión

### Problema 1: `Working outside of application context` en scheduler
`try_generate_today` usaba `_tpool.execute(lambda: run_pipeline_auto(...))`. Los OS threads de tpool NO heredan el app context de Flask.
**Fix**: capturar `current_app._get_current_object()` antes de entrar al tpool y envolver `run_pipeline_auto` en `with _app.app_context()`. Aplicado también en `api_generar_diario_sync`.

### Problema 2: DNS/red falla al llamar Claude desde greenlet
`_call` caía a `_anthropic_urllib` que usa sockets monkey-patched por eventlet. Eventlet parchea `urllib` para usar tpool internamente → **deadlock** si ya estamos en un tpool OS thread.
**Fix**: usar `_anthropic_subprocess` como fallback. Lanza un proceso Python limpio (sin monkey-patch). `subprocess.communicate()` es cooperativo en greenlets gracias al parche de `os.read()` de eventlet.

### Regla permanente
En producción (gunicorn+eventlet): el SDK Anthropic SIEMPRE falla ("Trio primitives monkey-patched") → subprocess es el fallback definitivo. No usar `_anthropic_urllib` ni tpool anidado.

## Dirección visual actualizada (25 Oct 2026)

### Archivos modificados
| Archivo | Cambio |
|---------|--------|
| `app/services/content/agents/creativo.py` | Instrucciones de flow_prompt con estructura fotográfica obligatoria, prohibiciones explícitas, variedad entre piezas |
| `app/services/content/agents/productor.py` | `SYSTEM_DV` con nueva dirección fotográfica; `prompt_dv` actualizado |
| `app/services/content/agents/revisor.py` | `SYSTEM` con checklist visual; prompt `_run_diario` con 9 criterios visuales |

### Nueva dirección — resumen
- Fotografía publicitaria o composición conceptual fotorrealista (NO ilustración corporativa).
- Un protagonista claro por pieza: persona en negocio, teléfono en uso, viajero, escena nocturna.
- Azul #196BFE como acento en un objeto o detalle, no tinte de toda la imagen.
- Logo como marca de agua, el usuario proporciona el archivo oficial.
- Tres piezas comerciales del día con escenarios y composiciones distintos.
- Texto en español en imagen solo si aporta valor; desarrollo en el copy del post.

### Propuestas de prueba — enlaces directos (25 Oct 2026)
| ID | Tema | URL | Estado |
|----|------|-----|--------|
| **45** | Operar por WhatsApp | `http://localhost:5002/contenido/propuesta/45` | `pendiente_aprobacion` |
| **32** | Tipo de cambio para negocios | `http://localhost:5002/contenido/propuesta/32` | `pendiente_aprobacion` (aprobación anterior invalidada) |
| **39** | Cambio de divisas para viajes | `http://localhost:5002/contenido/propuesta/39` | `pendiente_aprobacion` |

### Historial de propuestas comerciales (pipeline 28 — conservado)
| ID | Tema | Notas |
|----|------|-------|
| 31 | Spread cambiario: por qué varía el tipo de cambio | Prop original; flow_prompt actualizado a estilo fotográfico (cafetería Miraflores) |
| 32 | Tipo de cambio para negocios | Aprobación anterior invalidada; nuevo prompt: taller textil La Victoria/Gamarra |
| 33 | Comercio exterior — horario extendido | Texto corregido: distingue recepción de mensajes de ejecución operativa; NO es viajes |
| 39 | Cambio de divisas para viajes *(creado manualmente)* | Aeropuerto Jorge Chávez, viajero con mochila y pasaporte |
| 45 | Operar por WhatsApp *(creado manualmente)* | Dueño de ferretería/negocio revisando WhatsApp detrás del mostrador |

### Prop 33 — corrección y verificación de horario
**Problema original**: el texto podía insinuar operaciones disponibles a cualquier hora.
**Corrección**: distingue que WhatsApp recibe mensajes fuera de horario, pero las operaciones
se atienden "en la próxima ventana operativa disponible".
**Verificación de horario**: "lunes a sábado en horario extendido" está respaldado por el
beneficio verificado #3 de brand_configs: *"Operaciones disponibles de lunes a sábado en horario
extendido"*. El texto es correcto y no requiere reemplazarse por frases genéricas.

## Estado de la dirección visual (25 Oct 2026)
- **Probada por el usuario** en Gemini/Flow — resultado mejoró respecto a la versión anterior.
- **Dirección confirmada como base** para futuras propuestas, con variedad de escenas.
- **NO implica aprobación automática**: cada pieza sigue sujeta a aprobación individual antes de publicar.
- Muestras 45 (WhatsApp), 32 (Negocios) y 39 (Viajes) conservadas en `pendiente_aprobacion`.

## Próximos pasos
1. **Activar deploy en Render**: seguir instrucciones de la sección anterior.
2. **Verificar post-deploy**: `/contenido/hoy` con auth, textos y prompts accesibles, scheduler con próxima ejecución en hora Lima.
3. Aprobación individual de piezas (dirección visual aprobada, contenido pendiente por pieza).
4. Revisión editorial: textos de las 3 noticias del pipeline 28.
5. Primera entrega automática: mañana 26 Oct 2026 a las 6:30 AM Lima — registrar hora inicio, fin y estado para confirmar que terminó antes de las 8:00 AM.

## Para deploy a Render
1. `ESTUDIO_CRON_TOKEN` obligatorio si se usa el Cron Job (endpoint sync).
2. `ESTUDIO_DIARIO_AUTO` no debe estar en `false` si se usa el scheduler interno.
3. La migración `d1a2r3i4o5d6` usa `batch_alter_table` (compatible SQLite y PostgreSQL).
4. Hacer push del branch una vez aprobada la revisión editorial.
