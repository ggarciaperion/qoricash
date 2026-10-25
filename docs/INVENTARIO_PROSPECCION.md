# Inventario de Prospección — Auditoría completa

**Fecha**: 2026-10-25 (v2 — revisión post-aclaración)
**Rama**: `cleanup/prospeccion-inventario`
**Carpeta auditada**: `~/Desktop/Prospeccion/`

---

## 1. Verificación de cambios realizados en esta intervención

### 1.a Archivos del servidor Flask (en repo git)

Los siguientes archivos del servidor **sí fueron modificados** y están registrados en git:

| Archivo | Cambio | Afecta flujo 24/7 |
|---------|--------|-------------------|
| `app/services/camp_importer.py` | Se añadió `import_eventos()` — nueva función que recibe eventos JSON directos. No toca las funciones existentes de parseo de archivos ni el endpoint anterior. | No |
| `app/routes/agentes.py` | Se añadió el endpoint `POST /api/prospeccion/sync-evento`. Nuevas líneas al final del archivo, sin modificar rutas existentes. | No |
| `app/routes/contenido.py` | Cambios de Estudio Creativo únicamente (fuentes de noticias, auth de cron token). | No |
| `app/services/content/agents/editor.py` | Cambios de Estudio Creativo. | No |
| `app/services/content/daily_scheduler.py` | Cambios de Estudio Creativo. | No |

**Los agentes (`agente_*.py`, `orchestrator.py`, `motor_comercial.py`) y todos sus módulos de soporte no están en el repositorio git. Los cambios de servidor no los tocan.**

### 1.b Scripts de campaña en `~/Desktop/Prospeccion/` (fuera de git)

Tres scripts de campaña fueron modificados el 2026-10-25 (confirmado por fecha de modificación de archivo).
Ninguno es importado ni llamado por ningún agente 24/7 (verificado por grep en todos los agentes).

#### `campana_qoricash_150.py` — modificado 2026-10-25 01:27

**Qué cambió:**
- Se eliminó el `FileHandler` que escribía el log en `~/Desktop/...`. La configuración de logging quedó solo con `StreamHandler` (stdout).
- Se añadió al inicio (bloque try/except): `from campaign_sink import send_evento as _send_evento`. Si el import falla, `_send_evento` queda como no-op.
- Se añadieron dos llamadas `_send_evento({...})` después de cada envío exitoso y de cada fallo, solo para registro.

**Qué NO cambió:** `html_plantilla()`, `subject`, `LIMITE=50`, `PAUSA_S=10`, `BANDEJAS`, `es_elegible()`, `score_int()`, `actualizar_enviado()`, la lógica de rebotes, ni ninguna regla de selección o envío.

#### `campana_prospeccion_nueva_base.py` — modificado 2026-10-25 01:28

**Qué cambió:**
- Se eliminó el `FileHandler` al Desktop. Solo queda `StreamHandler`.
- La ruta de `email_enviados_*.json` (deduplicación 48h) se movió de `~/Desktop/Prospeccion/` a `~/Library/Application Support/qoricash/`. Funcionalidad idéntica, ubicación distinta.
- Se añadió bloque try/except con `campaign_sink`.
- Se añadieron llamadas `_send_evento()` después de cada envío (OK, FAIL, EXCEPCIÓN). No-op si import falla.

**Qué NO cambió:** toda la lógica de envío, templates (`html_corporativo` / `html_personal`), subjects, límite de 500 por bandeja, deduplicación, selección de elegibles, actualización de Sheets, manejo de errores de envío.

#### `campana_nuevos_prospectos.py` — modificado 2026-10-25 01:28

**Qué cambió:**
- Se eliminó el `FileHandler`. Solo queda `StreamHandler`.
- Se añadió bloque try/except con `campaign_sink`.
- Se añadieron llamadas `_send_evento()` después de "Enviado" y "Error". No-op si import falla.

**Qué NO cambió:** imports de `html_corporativo`, `html_personal`, `html_sector`, `SUBJECTS_SECTOR` desde `send_test_precio_mejorado.py` y `plantillas_sectoriales.py`, `validar_plantilla()`, `LIMITE_POR_BANDEJA=500`, `PAUSA_SEG=7`, `get_elegibles_relajado()`, `detectar_sector()`, toda la lógica de selección y envío.

#### `campaign_sink.py` — creado 2026-10-25 01:21

Archivo nuevo. Librería auxiliar importada por las tres campañas anteriores. No afecta a agentes.

### 1.c Módulos de plantillas y soporte — sin modificar

Verificado por fecha de modificación de archivo (todos anteriores al 2026-10-25):

| Archivo | Última modificación |
|---------|---------------------|
| `send_test_precio_mejorado.py` | 2026-08-27 |
| `outreach_template_official.py` | 2026-10-13 |
| `plantillas_sectoriales.py` | 2026-08-27 |
| `mail_templates.py` | 2026-07-07 |
| `config.py` | 2026-10-09 |
| `compliance.py` | 2026-09-16 |
| `suppression.py` | 2026-09-16 |
| `alertas.py` | 2026-09-16 |
| `sheets_sync.py` | 2026-09-23 |
| `ecosistema_db.py` | 2026-10-06 |
| `ecosistema_pg.py` | 2026-10-06 |

### 1.d Agentes 24/7 — sin modificar

Verificado por fecha de modificación de archivo (todos anteriores al 2026-10-25):

| Archivo | Última modificación |
|---------|---------------------|
| `orchestrator.py` | 2026-10-23 |
| `agente_outreach.py` | 2026-10-13 |
| `motor_comercial.py` | 2026-10-09 |
| `agente_response.py` | 2026-10-06 |
| `agente_crm_bridge.py` | 2026-10-06 |
| `agente_intelligence.py` | 2026-09-29 |
| `agente_scoring.py` | 2026-09-23 |
| `agente_research.py` | 2026-09-23 |
| `agente_scout.py` | 2026-09-21 |
| `agente_followup.py` | 2026-09-16 |

**Conclusión**: los asuntos, HTML, colores, imágenes, firmas, plantillas, horarios, límites, selección de prospectos, exclusiones y reglas de seguimiento del flujo 24/7 no fueron tocados en ningún momento de esta intervención.

---

## 2. Procesos programados

| Proceso | Tipo | Estado | Detalle |
|---------|------|--------|---------|
| `pe.qoricash.sincronizador` | LaunchAgent (AppSupport) | Funcionando | Drena cola c/15 min. Ejecución real confirmada 2026-10-25 01:25. Sin FDA. |
| `pe.qoricash.motor_comercial` | LaunchAgent (Desktop) | Fallando | `can't open file … motor_comercial.py: [Errno 2]`. Log 0 bytes desde jun-26. `LastExitStatus=19978`. No reparar por ahora (podría iniciar envíos). |
| cron `0 8 19 5 *` | cron | Activo pero roto | Se ejecutará cada 19 de mayo a las 08:00 (no tiene año). El archivo `campana_mype.py` no existe en la raíz (solo en `_legacy/`), por lo que el comando python falla. La auto-eliminación (`crontab -l \| grep -v … \| crontab -`) solo se ejecutaría si python hubiera tenido éxito. No se ha eliminado. No ejecutar. |

---

## 3. LISTA 1 — Se conserva (con evidencia)

### Agentes 24/7 — dependencia directa del flujo

| Script | Función | Evidencia |
|--------|---------|-----------|
| `orchestrator.py` | Entry point Render Background Worker | Ejecutándose en Render actualmente |
| `motor_comercial.py` | Entry point LaunchAgent local | Programado vía plist (fallando por TCC — no reparar ahora) |
| `agente_scout.py` | Captación nuevos prospectos (06:00) | Importado por `orchestrator.py` y `motor_comercial.py` |
| `agente_research.py` | Enriquecimiento (c/4 h) | Idem |
| `agente_scoring.py` | Puntuación y priorización (23:00) | Idem |
| `agente_outreach.py` | Envío outreach (8 lotes 09:30–17:30) | Idem |
| `agente_followup.py` | Seguimiento (10:00) | Idem |
| `agente_response.py` | Respuestas entrantes (c/30 min) | Idem |
| `agente_crm_bridge.py` | Sincronización CRM (c/1 h) | Idem |
| `agente_intelligence.py` | Inteligencia comercial (20:00) | Idem |

### Módulos de soporte — dependencia directa de agentes (verificado por import)

| Script | Importado por (agentes) |
|--------|------------------------|
| `config.py` | Todos los agentes |
| `compliance.py` | `agente_outreach`, `agente_followup` |
| `suppression.py` | `agente_outreach` |
| `reputacion.py` | `suppression.py` + campañas manuales (`campana_nuevos_prospectos`, `campana_seguimiento_hoja4`, `campana_prospeccion_nueva_base`) |
| `ecosistema_db.py` | Agentes locales |
| `ecosistema_pg.py` | `orchestrator` y agentes Render |
| `alertas.py` | `agente_outreach`, `agente_followup`, `orchestrator`, `preflight`, `sync_tc` |
| `sheets_sync.py` | Varios agentes |
| `prospect_state.py` | Agentes |
| `runtime_config.py` | Agentes |
| `health.py` | `preflight`, `orchestrator` |
| `sync_tc.py` | `agente_outreach` (bloquea si TC no fresco) |
| `preflight.py` | `agente_outreach` |
| `outreach_template_official.py` | `agente_outreach` |
| `mail_templates.py` | Agentes |
| `send_test_precio_mejorado.py` | `agente_followup`, `campana_nuevos_prospectos` — exporta `html_corporativo`, `html_personal`, `es_dominio_personal` |
| `plantillas_sectoriales.py` | `campana_nuevos_prospectos`, `campana_master` |
| `sheets_db.py` | `campana_nuevos_prospectos`, `seleccionar_1500` |

### Módulos auxiliares nuevos

| Script | Evidencia |
|--------|-----------|
| `campaign_sink.py` | Importado por 3 campañas manuales; cola AppSupport verificada en producción |

### Suite de tests del ecosistema 24/7

Los siguientes scripts de test importan y validan el comportamiento de los agentes. Se conservan como regresión:

| Script | Cubre | Última modificación |
|--------|-------|---------------------|
| `test_e2e.py` | `agente_scout`, `agente_scoring`, `agente_response`, `agente_crm_bridge`, `agente_intelligence` | 2026-09-16 |
| `test_golive.py` | 8 agentes + `orchestrator` | 2026-09-21 |
| `test_pg_compat.py` | 9 agentes (compatibilidad SQLite→PG) | 2026-09-16 |
| `test_worker_issues.py` | 9 agentes (problemas reales observados en Render) | 2026-09-17 |
| `test_dry_run_double_protection.py` | `orchestrator` (doble protección DRY_RUN) | 2026-09-16 |
| `test_ecosistema_pg.py` | `ecosistema_pg.py` (DAL PostgreSQL) | 2026-09-16 |
| `test_migration_counts.py` | Conteos SQLite vs PostgreSQL | 2026-09-16 |
| `test_reconciliacion.py` | `reconciliacion_readonly.py` | 2026-09-17 |
| `test_verificacion_final.py` | `verificacion_final_readonly.py` | 2026-09-17 |

### Campañas manuales (clasificadas con evidencia)

| Script | Clasificación | Base |
|--------|--------------|------|
| `campana_qoricash_150.py` | Uso histórico confirmado — trigger por keyword | Mencionada en MEMORY.md, ejecuciones registradas |
| `campana_prospeccion_nueva_base.py` | Flujo principal activo — trigger por keyword | Script principal POE según MEMORY.md |
| `campana_nuevos_prospectos.py` | Uso histórico confirmado — trigger por keyword | Mencionada en MEMORY.md |
| `campana_precios_lfc.py` | Uso histórico confirmado | Tiene FileHandler — no adaptada aún |
| `campana_precios_lfc_3bandejas.py` | Uso histórico confirmado | Idem |
| `campana_master.py` | Uso histórico confirmado | Idem |
| `campana_seguimiento_hoja4.py` | Uso histórico confirmado — importa `reputacion` | Tiene FileHandler — no adaptada aún |
| `campana_wa_clientes.py` | Uso histórico — solo WhatsApp, no registra en `camp_envio` | No aplica send_evento |
| `campana_wa_prospeccion.py` | Idem | Idem |
| `campana_wa_prospectos_sheet.py` | Idem | Idem |
| `campana_maestro.py` | Orquestador — llama a otros scripts, no envía directamente | — |

### Gestión de datos / mantenimiento

| Script | Función | Base |
|--------|---------|------|
| `construir_master.py` | Consolida 4 fuentes → PROSPECTOS_MASTER | Flujo obligatorio post-actualización |
| `validar_master_emails.py` | Validación MX/DNS → col I | Parte del flujo obligatorio |
| `puntuar_master.py` | Score 0-10 + Prioridad → cols M, N | Parte del flujo obligatorio |
| `mapear_rubros.py` | Mapeo de rubros a 18 sectores | Usado por construir_master y análisis |
| `seleccionar_1500.py` | Selección top 1500 para Hoja 3 | Trigger por keyword |
| `seleccionar_llamadas.py` | Top prospectos para llamada | Manual |
| `limpiar_bandejas.py` | Escanea rebotes → actualiza PROSPECTOS_MASTER + Hoja4 + LFC | Trigger por keyword |
| `cruzar_nueva_base.py` | Elimina de nueva base registros ya en producción | Manual |
| `estado_sistema.py` | Dashboard: validación, scores, embudo, sectores | Manual |
| `enrich_camp_prospectos.py` | Enriquecimiento desde Sheets → POST /sync-enrich | Manual |
| `sincronizador_prospeccion.py` | Sync de archivos .log históricos → /sync-importar | Para transferencia a Render cuando se autorice |
| `post_validacion.py` | Watcher: lanza puntuar automáticamente tras validación | Manual |
| `migrar_sqlite_pg.py` | Migración SQLite → PostgreSQL | Ya ejecutada en go-live; conservar por reversión |
| `consolidar_master.py` | Simulación DRY_RUN de consolidación — no escribe Sheets | Herramienta de verificación previa |
| `analisis_prospectos.py` | Genera `wa_objetivo_limpio.json` para campañas WA | Herramienta para campañas WA |
| `validar_antes_enviar.py` | Pre-validación de emails elegibles antes de campañas | Herramienta manual (distinta de preflight.py que es para agentes) |
| `exportar_bases_companeros.py` | Exporta 600 prospectos a Excel (2 archivos × 300) | Herramienta manual |
| `audit_sheets.py` | Auditoría read-only de todas las pestañas del Sheet | Herramienta de diagnóstico |
| `reconciliacion_readonly.py` | Inventario forense de datos de agente_response | Herramienta diagnóstico; importada por test_reconciliacion.py |
| `verificacion_final_readonly.py` | 3 checks read-only SQL pre-V3 | Herramienta diagnóstico; importada por test_verificacion_final.py |
| `investigacion_gmail_readonly.py` | Investigación read-only de casos ambiguos de Gmail | Herramienta diagnóstico |

### Herramientas de reporte

| Script | Clasificación |
|--------|--------------|
| `reporte_diario.py` | Genera PDF de mercados con fecha actual — manual |
| `reporte_ejecutivo.py` | Resumen semanal HTML a ggarcia — manual |
| `generar_reporte_financiero.py` | Template para reportes financieros (originado jul-2026) |
| `reporte_2oct2026.py` | One-off archivado — no ejecutar |
| `reporte_5oct2026.py` | One-off archivado — no ejecutar |
| `reporte_12oct2026.py` | One-off archivado — no ejecutar |
| `alertas_diarias.py` | Resumen ejecutivo diario por email (distinto de alertas.py) — manual |

### Envíos personalizados one-off

| Script | Clasificación |
|--------|--------------|
| `envio_1000millas.py` | Envío personalizado a 1000 MILLAS S.A.C. — puede repetirse |
| `envio_auasac.py` | Envío personalizado a contactos AUASAC — puede repetirse |

### Scripts de test de plantillas y prototipado

| Script | Clasificación |
|--------|--------------|
| `send_test_precios_lfc.py` | Test de templates LFC (corporativo + personal) — herramienta de verificación |
| `test_correo_v2.py` | Contiene `html_corporativo_v2()` — template de referencia para `campana_qoricash_150` |
| `test_nueva_plantilla.py` | Test aislado (no toca DB/Sheets) — herramienta de verificación |
| `test_templates_nuevos.py` | Test de los 4 sectores nuevos (construccion, consultoria, hospedaje, agroindustria) |

### Autenticación / configuración OAuth

| Script | Función |
|--------|---------|
| `autorizar_gerencia.py`, `autorizar_sheets.py` | Flujo OAuth interactivo |
| `auth_info.py`, `auth_lfc.py`, `auth_pmora.py`, `auth_pvilchez.py` | Auth específica por cuenta |
| `setup_oauth.py` | Configuración inicial OAuth |

---

## 4. LISTA 2 — Se propone retirar (sin afectar flujo 24/7)

| Archivo / entrada | Motivo | Por qué no afecta al flujo 24/7 |
|-------------------|--------|----------------------------------|
| Carpeta `_legacy/` (103 scripts) | Versiones reemplazadas de campañas y utilidades, ya aisladas en subcarpeta. Ningún script activo los importa (verificado). | Ningún agente ni módulo de soporte importa nada de `_legacy/` |
| Entrada cron `0 8 19 5 *` | El archivo `campana_mype.py` no existe fuera de `_legacy/`. El comando python fallará cada 19 de mayo. La auto-eliminación nunca se activó porque depende del éxito de python. La entrada tiene efecto nulo pero ocupa el crontab y puede generar confusión. | `campana_mype.py` no tiene relación con ningún agente 24/7. Eliminarlo del crontab no afecta ningún proceso. |

**Nada se elimina hasta autorización explícita. Este inventario no ejecuta acciones.**

---

## 5. Resumen de conteos (v2)

| Categoría | Cantidad |
|-----------|----------|
| Agentes 24/7 | 10 |
| Módulos soporte críticos (dep. de agentes) | 18 |
| Módulos auxiliares nuevos | 1 |
| Suite de tests del ecosistema | 9 |
| Campañas manuales | 11 |
| Gestión de datos / mantenimiento | 20 |
| Herramientas de reporte | 7 |
| Envíos personalizados one-off | 2 |
| Tests de plantillas / prototipado | 4 |
| Auth / OAuth | 7 |
| **Total conservar (raíz)** | **89** |
| Legacy (subcarpeta `_legacy/`) | 103 |
| Cron roto | 1 entrada |
| **Total propuesto para retirar** | **103 archivos + 1 entrada** |
| Scripts pendientes de decidir | 0 (todos clasificados) |
