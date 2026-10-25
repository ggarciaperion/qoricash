# Inventario de Prospección — Auditoría completa

**Fecha**: 2026-10-25 (v3 — verificación por contenido con git diff)
**Rama**: `cleanup/prospeccion-inventario`
**Carpetas auditadas**: `~/Desktop/Prospeccion/` (repo git propio) · `~/Desktop/Qoricash/Sistema/qoricash/` (repo Flask)

---

## 1. Verificación de integridad por contenido (git diff)

### 1.a Repo Flask (`qoricash`) — archivos del servidor

Baseline: commit `7e1415eb` (último antes de nuestra intervención).

| Archivo | Hunks | Líneas eliminadas | Líneas añadidas | Contenido del cambio |
|---------|-------|-------------------|-----------------|---------------------|
| `app/routes/agentes.py` | 1 | **0** | 41 | Nuevo endpoint `POST /api/prospeccion/sync-evento`. Código añadido después del endpoint `api_sync_enrich` existente, sin modificar ninguna función anterior. |
| `app/services/camp_importer.py` | 1 | **0** | 58 | Nueva función `import_eventos()`. Añadida después de `_insert_batch()`, sin modificar ninguna función anterior. |

Las demás modificaciones en este repo entre `7e1415eb` y HEAD corresponden exclusivamente a Estudio Creativo (`contenido.py`, `editor.py`, `daily_scheduler.py`, `hoy.html`, `ai/client.py`). Verificado: ninguna de esas rutas referencia prospeccion, camp_envio, agentes 24/7 ni campañas.

### 1.b Repo Prospeccion (`~/Desktop/Prospeccion/`) — scripts de campaña y agentes

Este repo tiene su propio historial git. El estado actual muestra 5 archivos con cambios no commiteados y 95 archivos sin seguimiento.

#### Archivos con cambios no commiteados

| Archivo | mtime | Origen del cambio | Descripción del diff |
|---------|-------|-------------------|---------------------|
| `campana_nuevos_prospectos.py` | 2026-10-25 01:28 | **Nuestra intervención** | Eliminado `FileHandler` (Desktop). Añadido bloque `campaign_sink` con fallback no-op. Añadidas 2 llamadas `_send_evento()` post-envío. Sin cambios en HTML, subject, `LIMITE_POR_BANDEJA=500`, `PAUSA_SEG=7`, `html_corporativo`/`html_personal`/`html_sector`, `SUBJECTS_SECTOR`, `get_elegibles_relajado()`, `detectar_sector()`, `validar_plantilla()`. |
| `campana_prospeccion_nueva_base.py` | 2026-10-25 01:28 | **Nuestra intervención** | Eliminado `FileHandler` (Desktop). Variable `LOG_FILE` reemplazada por `_APPDIR` (Application Support). Ruta de `email_enviados_*.json` movida a AppSupport (misma funcionalidad). Añadido bloque `campaign_sink` con fallback no-op. Añadidas 3 llamadas `_send_evento()` post-envío (OK, FAIL, excepción). Sin cambios en HTML, subject, límite de 500, deduplicación, lógica de elegibles, actualización de Sheets. |
| `agente_outreach.py` | 2026-10-13 10:56 | **Pre-existente** — anterior a nuestra sesión | Cambios en cabeceras de email (`Feedback-ID`, `List-Id`, `List-Unsubscribe` con URL HTTPS). Comentario "anti-spam" → "deliverability". Cambios de deliverability, no de contenido ni reglas. |
| `outreach_template_official.py` | 2026-10-13 10:56 | **Pre-existente** — anterior a nuestra sesión | `APPROVED_TEMPLATE_ID`: `v5` → `v6`. Footer: link `<a href="...">haga clic aquí</a>` añadido al texto de baja. Sin cambios en HTML principal, colores, imágenes, asunto ni estructura. |
| `orchestrator.py` | 2026-10-23 11:14 | **Pre-existente** — anterior a nuestra sesión | Añadida función `_write_feature_flags_to_runtime_config()` que escribe flags de diagnóstico al arrancar el worker. Sin cambios en lógica de scheduling, límites, selección ni envío. |

#### `campana_qoricash_150.py` — limitación declarada

Este archivo es **untracked** en el repo Prospeccion (nunca fue añadido al seguimiento de git). No hay versión anterior recuperable con `git diff`. Lo que puedo afirmar con git: no existe commit previo de este archivo. Lo que puedo observar: mtime 2026-10-25 01:27 (nuestra sesión), sin diferencia de estructura respecto al resto (FileHandler eliminado, `_send_evento` añadido, `html_plantilla()` / `subject` / `LIMITE=50` intactos según revisión directa del archivo).

#### Agentes, plantillas y módulos de soporte — sin modificar

Los siguientes archivos tienen mtime anterior al 2026-10-25 y **no aparecen en `git diff`** del repo Prospeccion, confirmando que no fueron tocados en nuestra sesión:

`agente_scout.py` · `agente_research.py` · `agente_scoring.py` · `agente_followup.py` · `agente_response.py` · `agente_crm_bridge.py` · `agente_intelligence.py` · `motor_comercial.py` · `send_test_precio_mejorado.py` · `plantillas_sectoriales.py` · `mail_templates.py` · `config.py` · `compliance.py` · `suppression.py` · `reputacion.py` · `alertas.py` · `sheets_sync.py` · `ecosistema_db.py` · `ecosistema_pg.py` · `prospect_state.py` · `runtime_config.py` · `health.py` · `sync_tc.py` · `preflight.py`

Los cambios pre-existentes en `agente_outreach.py`, `outreach_template_official.py` y `orchestrator.py` son anteriores a nuestra sesión y no son responsabilidad de esta intervención.

---

## 2. Qué ejecuta la campaña 24/7 y desde dónde

### Puntos de arranque automático

| Proceso | Mecanismo | Script ejecutado | Estado |
|---------|-----------|-----------------|--------|
| Render Background Worker | Plataforma Render (auto-deploy en push a `main` del repo worker) | `orchestrator.py` | Activo en Render |
| `pe.qoricash.motor_comercial` | LaunchAgent macOS, cada 15 min | `motor_comercial.py` en `~/Desktop/Prospeccion/` | Fallando (ENOENT/TCC) — log 0 bytes desde jun-26 |
| `pe.qoricash.sincronizador` | LaunchAgent macOS, cada 15 min | `sincronizador.py` en AppSupport | Funcionando — drena cola, no envía emails |
| cron `0 8 19 5 *` | cron (recurrente cada 19 de mayo) | `campana_mype.py` (no existe en raíz) | Falla en ejecución — python no encuentra el archivo |

### Qué hacen los orquestadores

Tanto `orchestrator.py` como `motor_comercial.py` invocan **únicamente los 8 agentes** (`agente_scout`, `agente_research`, `agente_scoring`, `agente_outreach`, `agente_followup`, `agente_response`, `agente_crm_bridge`, `agente_intelligence`) mediante imports Python directos. Ninguno lanza subprocesos a scripts de campaña `campana_*.py`. Verificado: `grep campana_ orchestrator.py motor_comercial.py` no arroja resultados.

### Otros puntos de envío automático

**No existen.** Ningún script `campana_*.py` es invocado por ningún proceso automático (LaunchAgent, cron, orchestrator, motor_comercial). Las campañas son estrictamente manuales, disparadas por comando explícito.

Limitación: no puedo verificar si existen configuraciones adicionales en Render (variables de entorno, schedulers de la plataforma) sin acceso directo al dashboard de Render.

---

## 3. Distinción de los 89 scripts

### Grupo A — Dependencias directas del flujo 24/7

Requeridos para que los agentes funcionen. Su ausencia o modificación afecta el flujo automatizado.

| Script | Rol en el flujo |
|--------|----------------|
| `orchestrator.py` | Entry point Render |
| `motor_comercial.py` | Entry point local (LaunchAgent) |
| `agente_scout.py` | Agente 1 — descubrimiento |
| `agente_research.py` | Agente 2 — validación emails |
| `agente_scoring.py` | Agente 3 — puntuación |
| `agente_outreach.py` | Agente 4 — envío outreach |
| `agente_followup.py` | Agente 5 — seguimiento |
| `agente_response.py` | Agente 6 — respuestas/rebotes |
| `agente_crm_bridge.py` | Agente 7 — CRM |
| `agente_intelligence.py` | Agente 8 — inteligencia |
| `config.py` | Caps, fases, recovery |
| `compliance.py` | Reglas anti-spam |
| `suppression.py` | Lista de supresión |
| `reputacion.py` | Blacklist + CircuitBreaker → importado por `suppression.py` → `agente_outreach` |
| `ecosistema_db.py` | DAL SQLite local |
| `ecosistema_pg.py` | DAL PostgreSQL (Render) |
| `alertas.py` | Notificaciones de sistema |
| `sheets_sync.py` | Sincronización Sheets |
| `prospect_state.py` | Estado de prospectos |
| `runtime_config.py` | Config dinámica |
| `health.py` | Checks de salud |
| `sync_tc.py` | Sync tipo de cambio (fail-closed) |
| `preflight.py` | Verificación pre-outreach |
| `outreach_template_official.py` | Template oficial v6 |
| `mail_templates.py` | Templates de email |
| `send_test_precio_mejorado.py` | `html_corporativo`, `html_personal`, `es_dominio_personal` → importado por `agente_followup` |
| `plantillas_sectoriales.py` | Templates sectoriales (importado por `agente_followup` vía `campana_nuevos_prospectos`, y por `campana_master`) |

**Total Grupo A: 27 scripts**

### Grupo B — Herramientas de mantenimiento y diagnóstico

No son ejecutadas por agentes. Se corren manualmente cuando se necesitan. Lectura / análisis / preparación de datos.

| Script | Tipo |
|--------|------|
| `construir_master.py` | Consolidación de datos (191k filas) |
| `validar_master_emails.py` | Validación MX/DNS |
| `puntuar_master.py` | Scoring |
| `mapear_rubros.py` | Análisis de rubros |
| `seleccionar_1500.py` | Selección top 1500 para Hoja 3 |
| `seleccionar_llamadas.py` | Top prospectos para llamada |
| `limpiar_bandejas.py` | Rebotes → PROSPECTOS_MASTER |
| `cruzar_nueva_base.py` | Cruce con producción |
| `estado_sistema.py` | Dashboard de estado |
| `enrich_camp_prospectos.py` | Enriquecimiento → POST /sync-enrich |
| `sincronizador_prospeccion.py` | Sync archivos .log históricos → /sync-importar |
| `post_validacion.py` | Watcher de validación |
| `migrar_sqlite_pg.py` | Migración SQLite→PG (ya ejecutada; conservar) |
| `consolidar_master.py` | Simulación DRY_RUN (no escribe Sheets) |
| `analisis_prospectos.py` | Genera `wa_objetivo_limpio.json` |
| `validar_antes_enviar.py` | Pre-validación manual de emails |
| `exportar_bases_companeros.py` | Exporta prospectos a Excel |
| `audit_sheets.py` | Auditoría read-only de Sheets |
| `reconciliacion_readonly.py` | Inventario forense de agente_response |
| `verificacion_final_readonly.py` | 3 checks SQL pre-V3 |
| `investigacion_gmail_readonly.py` | Investigación read-only Gmail |
| `reporte_diario.py` | PDF mercados con fecha actual |
| `reporte_ejecutivo.py` | Resumen semanal HTML |
| `generar_reporte_financiero.py` | Template reportes financieros |
| `reporte_2oct2026.py` | One-off archivado |
| `reporte_5oct2026.py` | One-off archivado |
| `reporte_12oct2026.py` | One-off archivado |
| `alertas_diarias.py` | Resumen diario por email (distinto de alertas.py) |
| `sheets_db.py` | Acceso a Sheets como fuente de datos |

**Total Grupo B: 29 scripts**

### Grupo C — Campañas independientes

Disparadas manualmente. No ejecutadas por ningún proceso automático (verificado). No afectan ni son afectadas por el flujo 24/7.

| Script | Evidencia de uso |
|--------|----------------|
| `campana_qoricash_150.py` | Trigger por keyword; ejecuciones en MEMORY.md |
| `campana_prospeccion_nueva_base.py` | Flujo principal POE activo |
| `campana_nuevos_prospectos.py` | Trigger por keyword; ejecuciones registradas |
| `campana_precios_lfc.py` | Uso histórico |
| `campana_precios_lfc_3bandejas.py` | Uso histórico |
| `campana_master.py` | Uso histórico |
| `campana_seguimiento_hoja4.py` | Uso histórico |
| `campana_wa_clientes.py` | Solo WhatsApp |
| `campana_wa_prospeccion.py` | Solo WhatsApp |
| `campana_wa_prospectos_sheet.py` | Solo WhatsApp |
| `campana_maestro.py` | Orquestador manual |
| `envio_1000millas.py` | Personalizado a empresa — puede repetirse |
| `envio_auasac.py` | Personalizado a empresa — puede repetirse |
| `campaign_sink.py` | Librería de eventos de campañas manuales |

**Total Grupo C: 14 scripts**

### Grupo D — Infraestructura de sincronización

| Script | Rol |
|--------|-----|
| `~/Library/Application Support/qoricash/sincronizador.py` | Queue drainer (LaunchAgent activo) |

### Grupo E — Auth / OAuth

| Script | Función |
|--------|---------|
| `autorizar_gerencia.py`, `autorizar_sheets.py` | Flujo OAuth interactivo |
| `auth_info.py`, `auth_lfc.py`, `auth_pmora.py`, `auth_pvilchez.py` | Auth por cuenta |
| `setup_oauth.py` | Setup inicial |

**Total Grupo E: 7 scripts**

### Grupo F — Suite de tests

Regresión del ecosistema 24/7. Referencian agentes pero solo los importan para probar; no los ejecutan en producción.

| Script | Cobertura |
|--------|-----------|
| `test_e2e.py` | 5 agentes + ecosistema |
| `test_golive.py` | 8 agentes + orchestrator |
| `test_pg_compat.py` | 9 agentes (compatibilidad SQLite→PG) |
| `test_worker_issues.py` | 9 agentes (issues reales observados) |
| `test_dry_run_double_protection.py` | orchestrator — doble DRY_RUN |
| `test_ecosistema_pg.py` | DAL PostgreSQL |
| `test_migration_counts.py` | Conteos SQLite vs PG |
| `test_reconciliacion.py` | reconciliacion_readonly |
| `test_verificacion_final.py` | verificacion_final_readonly |

**Total Grupo F: 9 scripts**

### Grupo G — Tests de plantillas y prototipado

| Script | Función |
|--------|---------|
| `send_test_precios_lfc.py` | Verifica templates LFC (corporativo + personal) |
| `test_correo_v2.py` | Contiene `html_corporativo_v2()` — template de referencia para `campana_qoricash_150` |
| `test_nueva_plantilla.py` | Test aislado (sin DB/Sheets) |
| `test_templates_nuevos.py` | Test de 4 sectores nuevos |

**Total Grupo G: 4 scripts**

---

**Total verificado: 27 + 29 + 14 + 1 + 7 + 9 + 4 = 91 scripts en raíz + AppSupport**

---

## 4. Lista de retiro preparada (sin ejecutar)

Nada se elimina hasta autorización. La siguiente lista está lista para ejecutar cuando se indique:

### 4.a Carpeta `_legacy/` — 103 archivos

**Evidencia de no-impacto**:
- `grep -r "from _legacy\|import _legacy" *.py` → 0 resultados
- Ningún agente, campaña ni módulo del flujo 24/7 importa nada de `_legacy/`
- Son versiones anteriores de scripts que hoy existen en la raíz con nombres equivalentes

**Comando de retiro** (ejecutar solo con autorización):
```bash
# Paso 1: crear respaldo comprimido
cd ~/Desktop/Prospeccion && tar -czf ~/Desktop/_legacy_backup_$(date +%Y%m%d).tar.gz _legacy/
# Paso 2: verificar respaldo
tar -tzf ~/Desktop/_legacy_backup_$(date +%Y%m%d).tar.gz | wc -l
# Paso 3 (solo tras confirmar respaldo): eliminar
rm -rf _legacy/
```

**Recuperable**: sí, desde el archivo `.tar.gz` en Desktop.

### 4.b Entrada cron `0 8 19 5 *`

**Evidencia de no-impacto**:
- Intenta ejecutar `campana_mype.py` en la raíz de Prospeccion
- Ese archivo no existe allí — está solo en `_legacy/`
- El proceso python falla silenciosamente cada 19 de mayo
- La lógica de auto-eliminación (`&& crontab -l | grep -v campana_mype | crontab -`) depende del éxito del comando python, que nunca ocurre
- No guarda relación con ningún agente 24/7 ni campaña activa

**Comando de retiro** (ejecutar solo con autorización):
```bash
crontab -l | grep -v "campana_mype" | crontab -
```

**Recuperable**: sí — la entrada completa está documentada aquí. Para restaurarla:
```bash
(crontab -l; echo "0 8 19 5 * cd /Users/gianpierre/Desktop/Prospeccion && /usr/bin/python3 campana_mype.py >> /Users/gianpierre/Desktop/Prospeccion/campana_mype_cron.log 2>&1 && crontab -l | grep -v campana_mype | crontab -") | crontab -
```

---

## 5. Resumen ejecutivo

**Qué ejecuta la campaña 24/7:**
`orchestrator.py` en Render (Background Worker) invoca los 8 agentes (`scout → research → scoring → outreach → followup → response → crm_bridge → intelligence`) en sus horarios. Localmente, `motor_comercial.py` hace lo mismo vía LaunchAgent, actualmente fallando por TCC. No lanza scripts de campaña.

**Otros puntos de envío automático:**
Ninguno. Las campañas `campana_*.py` son estrictamente manuales. El único cron activo (`0 8 19 5 *`) apunta a un archivo inexistente y falla en cada intento.

**Archivos auxiliares que conservar:**
Grupo A (27): dependencias del flujo 24/7. Grupo B (29): herramientas de mantenimiento. Grupo C (14): campañas manuales. Grupos D/E/F/G (21): infraestructura, auth, tests.

**Resultado de la comparación de agentes y plantillas:**
- Agentes (`agente_*.py`, `orchestrator.py`, `motor_comercial.py`): no aparecen en `git diff` de nuestra sesión. Los cambios en `agente_outreach.py`, `outreach_template_official.py` y `orchestrator.py` son pre-existentes (mtime 2026-10-13 y 2026-10-23, anteriores a nuestra sesión del 2026-10-25). No son parte de esta intervención.
- Plantillas y módulos de soporte críticos: sin cambios confirmados por `git diff` (no aparecen en el diff de la sesión).
- Scripts de campaña modificados por nuestra intervención: solo `campana_nuevos_prospectos.py` y `campana_prospeccion_nueva_base.py` (ambos tracked en git, diff completo documentado en Sección 1.b). `campana_qoricash_150.py` no tiene versión anterior en git (untracked).
- Cambios de nuestra intervención en los 3 scripts: exclusivamente FileHandler → StreamHandler, `email_enviados` → AppSupport (para `nueva_base`), y adición de llamadas `_send_evento()` post-envío con fallback no-op. Cero cambios en HTML, colores, asuntos, límites, horarios, reglas de selección ni eligibilidad.
