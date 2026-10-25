# Estudio Creativo — Nota de Continuidad (25 Oct 2026)

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

## Scheduler

### Local (gunicorn+eventlet)
Configurado en `run.py` como greenlet + tpool. Se inicia automáticamente en `eventlet.spawn_after(2, ...)` cuando el worker arranca. Lanza el pipeline a las **5:00-5:05 AM Lima** si no existe EntregaDiaria para hoy.

Para desactivar: `export ESTUDIO_DIARIO_AUTO=false` antes de arrancar.

### Render producción — qué activar
**Opción 1 (scheduler interno — cero costo adicional):**
El scheduler ya está en `run.py`. Al hacer deploy, correrá automáticamente en el web worker.
Simplemente asegurarse de que `ESTUDIO_DIARIO_AUTO` NO esté seteado como `false` en Render.

**Opción 2 (Render Cron Job — más robusto, $1/mes):**
Crear un Cron Job en Render con:
- Comando: `curl -X POST https://<tu-app>.onrender.com/contenido/api/generar-diario-sync -H "Content-Type: application/json" -d '{}'`
- Horario: `0 10 * * *` (10:00 UTC = 5:00 AM Lima)
- Timeout: 600s

## Entrega demostrada localmente (pipeline #28)
| Pieza | Tipo | Categoría | Tema | Palabras | Prompt |
|-------|------|-----------|------|----------|--------|
| #28 | noticia | mercados | USD/PEN cierra en 3.4455 | 90 | OK 686c |
| #29 | noticia | mercados | Bitcoin 80,800 USD antes de Fed | 103 | OK 723c |
| #30 | noticia | internacional | Midterms EE.UU. incertidumbre Wall Street | 97 | OK 732c |
| #31 | comercial | — | Cambia dólares desde donde estés | 75 | OK 697c |
| #32 | comercial | — | Tipo de cambio pensado para negocios | ~90 | OK 738c |
| #33 | comercial | — | El comercio exterior no para a las 6 pm | ~85 | OK 766c |

## Cambios en esta sesión (sin commit)
| Archivo | Cambio |
|---------|--------|
| `app/models/content_proposal.py` | +pipeline_id, delivery_type, noticia_category, resource_status, revisor_notas, correcciones, retry_count + properties |
| `app/models/content_pipeline.py` | +EntregaDiaria model |
| `app/services/content/pipeline_coordinator.py` | +tipo 'diario' en PIPELINE_SEQUENCES; editor mode 'investigador' |
| `app/services/content/agents/investigador.py` | +_run_diario (3 noticias categorizadas, 48h/7d window) |
| `app/services/content/agents/editor.py` | +_run_diario (3 posts LinkedIn 80-140 palabras) |
| `app/services/content/agents/creativo.py` | +_run_diario (3 propuestas com. + visual prompts, audiencia rotativa) |
| `app/services/content/agents/productor.py` | +_run_diario (Director Visual: 6 prompts Gemini/Flow, sin Pillow) |
| `app/services/content/agents/revisor.py` | +_run_diario (revisa 6 piezas, correcciones, resource_status) |
| `app/routes/contenido.py` | +/hoy, +/api/generar-diario, +/api/generar-diario-sync, +aprobar/planificar/cargar-recurso-diario |
| `app/templates/contenido/hoy.html` | nueva vista principal Entrega de Hoy |
| `app/templates/contenido/agentes.html` | +tab "Entrega de Hoy" |
| `run.py` | +start_daily_content_scheduler (greenlet, 5 AM Lima, tpool) |
| `migrations/versions/d1a2r3i4o5d6_daily_delivery.py` | migración (aplicada manualmente a SQLite) |

## Para deploy a Render
1. Commit todos los archivos untracked del módulo (ver lista arriba + archivos originales c1o2n3t4e5n6)
2. La migración `d1a2r3i4o5d6` usa `batch_alter_table` (compatible SQLite y PostgreSQL)
3. El scheduler interno se activa solo al arrancar el worker
4. Verificar que `ESTUDIO_DIARIO_AUTO` no esté bloqueado en variables de entorno de Render
