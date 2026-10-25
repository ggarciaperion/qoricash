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
| Hash | Descripción |
|------|-------------|
| `92e93341` | feat: módulo Estudio Creativo completo (pipeline diario, 5 agentes, vistas, migraciones) |
| `2b74e6c1` | fix: auth obligatoria en cron, categorías sin forzado posicional, scheduler tardío |

## Estado al cierre de la etapa local
- Panel disponible en `http://localhost:5002/contenido/hoy` para revisión editorial.
- Pipeline #28 en DB: 2 noticias mercados + 1 internacional, sin nacional — artefacto de la prueba inicial (bug ya corregido en código).
- El próximo pipeline diario generará exactamente 1 noticia por categoría con su fuente real.
- No se hizo push ni deploy.

## Próximos pasos (pendientes de decisión)
1. Revisión editorial: textos, fuentes, prompts y presentación del paquete diario.
2. Ajustes puntuales según revisión.
3. Decisión de deploy: scheduler interno en Render **o** Cron Job ($1/mes).
4. Variables de entorno a configurar antes del deploy:
   - `ESTUDIO_CRON_TOKEN` (obligatoria si se usa el endpoint cron)
   - `ESTUDIO_DIARIO_AUTO=false` solo si se quiere desactivar el scheduler interno

## Para deploy a Render
1. `ESTUDIO_CRON_TOKEN` obligatorio si se usa el Cron Job (endpoint sync).
2. `ESTUDIO_DIARIO_AUTO` no debe estar en `false` si se usa el scheduler interno.
3. La migración `d1a2r3i4o5d6` usa `batch_alter_table` (compatible SQLite y PostgreSQL).
4. Hacer push del branch una vez aprobada la revisión editorial.
