# Inventario de Prospección — Auditoría completa

**Fecha**: 2026-10-25
**Rama**: `cleanup/prospeccion-inventario`
**Carpeta auditada**: `~/Desktop/Prospeccion/`

---

## Procesos programados activos

| Proceso | Tipo | Estado | Notas |
|---------|------|--------|-------|
| `pe.qoricash.sincronizador` | LaunchAgent (AppSupport) | ✅ Funcionando | Drena cola c/15 min. Ejecución real confirmada 2026-10-25 |
| `pe.qoricash.motor_comercial` | LaunchAgent (Desktop) | ❌ Fallando | `can't open file … motor_comercial.py: [Errno 2]`. Log 0 bytes desde Jun 26. `LastExitStatus=19978` |
| cron `0 8 19 5 *` | cron (fecha pasada) | ❌ Estancado | Llama `campana_mype.py` (solo existe en `_legacy/`). Fecha de ejecución: 19 may 2026. Nunca se auto-eliminó porque el script python falló |

**Acción pendiente de autorización**: eliminar entrada de cron estancada.
**Acción pendiente**: reparar `motor_comercial` (mismo problema TCC que tenía sincronizador antes → mover script a AppSupport o corregir path en plist).

---

## LISTA 1 — Se conserva

### Agentes 24/7 (orquestados por `orchestrator.py` en Render / `motor_comercial.py` local)

| Script | Función |
|--------|---------|
| `orchestrator.py` | Entry point Render Background Worker |
| `motor_comercial.py` | Entry point LaunchAgent local (actualmente fallando) |
| `agente_scout.py` | Captación nuevos prospectos (06:00) |
| `agente_research.py` | Enriquecimiento de prospectos (c/4 h) |
| `agente_scoring.py` | Puntuación y priorización (23:00) |
| `agente_outreach.py` | Envío outreach (8 lotes 09:30–17:30) |
| `agente_followup.py` | Seguimiento de prospectos contactados (10:00) |
| `agente_response.py` | Procesamiento de respuestas entrantes (c/30 min) |
| `agente_crm_bridge.py` | Sincronización al CRM (c/1 h) |
| `agente_intelligence.py` | Análisis de inteligencia comercial (20:00) |

### Módulos de soporte críticos

| Script | Función | Importado por |
|--------|---------|---------------|
| `config.py` | Parámetros globales (caps, fases, recovery) | Todos los agentes |
| `compliance.py` | Reglas de cumplimiento anti-spam | `agente_outreach`, `agente_followup` |
| `suppression.py` | Lista de supresión de emails | `agente_outreach`, campañas |
| `ecosistema_db.py` | Capa de acceso a SQLite local | Agentes locales |
| `ecosistema_pg.py` | Capa de acceso a PostgreSQL (Render) | `orchestrator` y agentes Render |
| `alertas.py` | Notificaciones de sistema (Telegram/email) | `agente_outreach`, `agente_followup`, `orchestrator`, `preflight`, `sync_tc` |
| `sheets_sync.py` | Sincronización bidireccional con Sheets | Varios agentes |
| `sheets_db.py` | Acceso a Sheets como fuente de datos | `campana_nuevos_prospectos`, `seleccionar_1500` |
| `prospect_state.py` | Estado de prospectos en pipeline | Agentes |
| `runtime_config.py` | Config dinámica en tiempo de ejecución | Agentes |
| `health.py` | Checks de salud del sistema | `preflight`, `orchestrator` |
| `sync_tc.py` | Sincronización de tipo de cambio (08:50) | `agente_outreach` (preflight) |
| `preflight.py` | Verificación pre-outreach (DB/Gmail/TC/bandejas) | `agente_outreach` |
| `outreach_template_official.py` | Template oficial outreach v5 | `agente_outreach` |
| `mail_templates.py` | Colección de templates de email | Agentes |
| `plantillas_sectoriales.py` | Templates por sector (18 sectores) | `campana_nuevos_prospectos`, `campana_master` |
| `send_test_precio_mejorado.py` | **CRÍTICO** — exporta `html_corporativo`, `html_personal`, `es_dominio_personal` | `agente_followup`, `campana_nuevos_prospectos` |
| `campaign_sink.py` | Librería de eventos (POST directo + cola AppSupport) | `campana_qoricash_150`, `campana_prospeccion_nueva_base`, `campana_nuevos_prospectos` |

### Campañas activas (manuales / bajo demanda)

| Script | Trigger | Estado send_evento |
|--------|---------|-------------------|
| `campana_qoricash_150.py` | "prospecto [mes] X.XXX X.XXX" | ✅ Adaptado |
| `campana_prospeccion_nueva_base.py` | "Enviar prospección compra X venta Y" | ✅ Adaptado |
| `campana_nuevos_prospectos.py` | "Enviar correo a nuevos prospectos" | ✅ Adaptado |
| `campana_precios_lfc.py` | Manual | ⏳ Pendiente adaptar |
| `campana_precios_lfc_3bandejas.py` | Manual | ⏳ Pendiente adaptar |
| `campana_master.py` | Manual | ⏳ Pendiente adaptar |
| `campana_seguimiento_hoja4.py` | Manual | ⏳ Pendiente adaptar |
| `campana_wa_clientes.py` | Manual | ℹ️ Solo WhatsApp |
| `campana_wa_prospeccion.py` | Manual | ℹ️ Solo WhatsApp |
| `campana_wa_prospectos_sheet.py` | Manual | ℹ️ Solo WhatsApp |
| `campana_maestro.py` | Orquestador | ℹ️ No envía directamente |

### Gestión de datos / mantenimiento

| Script | Función |
|--------|---------|
| `construir_master.py` | Consolida 4 fuentes → PROSPECTOS_MASTER (191k filas) |
| `validar_master_emails.py` | Validación MX/DNS → col I |
| `puntuar_master.py` | Score 0-10 + Prioridad → cols M, N |
| `mapear_rubros.py` | Mapeo de rubros a 18 sectores |
| `seleccionar_1500.py` | Selección top 1500 para Hoja 3 |
| `seleccionar_llamadas.py` | Top prospectos para llamada (score≥5 + tel) |
| `limpiar_bandejas.py` | Escanea rebotes → actualiza PROSPECTOS_MASTER + Hoja4 + LFC |
| `cruzar_nueva_base.py` | Elimina de nueva base registros ya en producción |
| `estado_sistema.py` | Dashboard completo (validación, scores, embudo, sectores) |
| `enrich_camp_prospectos.py` | Enriquecimiento desde Sheets → POST `/sync-enrich` |
| `sincronizador_prospeccion.py` | Sync de archivos `.log`/`_resultado.json` históricos → `/sync-importar` |
| `post_validacion.py` | Watcher: lanza puntuar automáticamente tras validación |
| `migrar_sqlite_pg.py` | Migración SQLite → PostgreSQL (usada en go-live) |

### Autenticación / configuración OAuth

| Script | Función |
|--------|---------|
| `autorizar_gerencia.py`, `autorizar_sheets.py` | Flujo OAuth interactivo para bandejas |
| `auth_info.py`, `auth_lfc.py`, `auth_pmora.py`, `auth_pvilchez.py` | Auth específica por cuenta |
| `setup_oauth.py` | Configuración inicial OAuth |

---

## LISTA 2 — Se retira

| Archivo / Carpeta | Motivo |
|-------------------|--------|
| `_legacy/` (103 scripts) | Ya aislados en subcarpeta. Versiones anteriores de campañas y utilidades reemplazadas. Conservar hasta confirmar que no hay dependencias ocultas, luego eliminar carpeta completa |
| Entrada cron `0 8 19 5 * campana_mype.py` | Fecha pasada (19 may 2026), script solo existe en `_legacy/`, auto-eliminación nunca se ejecutó. Eliminación segura |

**No se elimina nada hasta autorización explícita.**

---

## LISTA 3 — Pendiente de confirmar

| Script | Situación | Pregunta |
|--------|-----------|----------|
| `consolidar_master.py` | Posible predecesor de `construir_master.py` | ¿Reemplazado? ¿Aún se usa? |
| `analisis_prospectos.py` | Sin imports conocidos desde agentes | ¿Análisis recurrente o one-off? |
| `envio_1000millas.py` | Campaña específica por nombre de empresa | ¿Completada? ¿Podría repetirse? |
| `envio_auasac.py` | Idem | ¿Completada? ¿Podría repetirse? |
| `audit_sheets.py` | Herramienta de diagnóstico readonly | ¿Se usa activamente o fue puntual? |
| `reconciliacion_readonly.py` | Idem | ¿Se usa activamente? |
| `verificacion_final_readonly.py` | Idem | ¿Se usa activamente? |
| `investigacion_gmail_readonly.py` | Idem | ¿Se usa activamente? |
| `reputacion.py` | Sin imports desde agentes actuales | ¿Integrado en algún agente o abandonado? |
| `alertas_diarias.py` | Existe junto a `alertas.py` | ¿Reemplazado por `alertas.py`? ¿Aún se corre manualmente? |
| `validar_antes_enviar.py` | Posible precursor de `preflight.py` | ¿Reemplazado? |
| `generar_reporte_financiero.py` | Sin imports desde agentes | ¿Manual? ¿Recurrente? |
| `reporte_diario.py` | Sin scheduler conocido | ¿Se corre manualmente? ¿Reemplazado por `estado_sistema.py`? |
| `reporte_ejecutivo.py` | Idem | ¿Se corre manualmente? |
| `reporte_2oct2026.py` | Nombre con fecha específica | ¿One-off archivable? |
| `reporte_5oct2026.py` | Idem | ¿One-off archivable? |
| `reporte_12oct2026.py` | Idem | ¿One-off archivable? |
| `exportar_bases_companeros.py` | Sin imports desde agentes | ¿One-off completado? |
| `send_test_precios_lfc.py` | Test de templates LFC | ¿Activo? ¿O reemplazado por `send_test_precio_mejorado.py`? |
| `test_correo_v2.py` | Contiene `html_corporativo_v2()` (template de `campana_qoricash_150`) | ¿Conservar como referencia de template? |
| `test_nueva_plantilla.py` | Test de plantilla | ¿One-off? |
| `test_*.py` (9 archivos restantes) | Suite de tests de integración | ¿Conservar como regresión? ¿O solo se corrieron una vez? |

---

## Resumen de conteos

| Categoría | Cantidad |
|-----------|----------|
| Agentes 24/7 | 10 |
| Módulos soporte críticos | 18 |
| Campañas activas | 11 |
| Gestión de datos / mantenimiento | 13 |
| Auth / OAuth | 7 |
| **Total conservar (raíz)** | **59** |
| Legacy (subcarpeta `_legacy/`) | 103 |
| Cron estancado | 1 entrada |
| **Total retirar** | **103 + 1** |
| Pendiente de confirmar | 21 |
