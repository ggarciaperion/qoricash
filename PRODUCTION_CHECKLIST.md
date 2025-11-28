# ✅ CHECKLIST DE PRODUCCIÓN - QORICASH TRADING V2

## 📊 RESUMEN DE INFRAESTRUCTURA

**Volumen estimado:**
- 8 usuarios simultáneos
- 100 operaciones/día (3,000/mes)
- 700 clientes nuevos/mes
- ~3GB archivos/mes

**Stack actual (RECOMENDADO - NO MIGRAR):**
- ✅ Hosting: Render Web Service ($7/mes)
- ✅ Base de datos: Render PostgreSQL ($7/mes)
- ✅ Almacenamiento: Cloudinary Free → Plus cuando sea necesario
- ✅ Código: GitHub (privado)
- ✅ SSL: Automático con Render
- **Costo total: $14-$21/mes** (muy económico)

---

## 🚀 PASOS ANTES DE PRODUCCIÓN

### 1. INFRAESTRUCTURA Y HOSTING

- [ ] **Verificar plan de Render Web Service**
  - Ir a: https://dashboard.render.com
  - Confirmar que estás en plan **Starter ($7/mes)** mínimo
  - Si estás en Free tier, actualizar a Starter para evitar sleep

- [ ] **Verificar plan de PostgreSQL**
  - Confirmar plan **Starter ($7/mes)**
  - Verificar que backups automáticos estén activados
  - Anotar las credenciales de acceso

- [ ] **Configurar dominio personalizado**
  - ✅ Dominio agregado en Render: app.qoricash.pe
  - ✅ DNS configurado en punto.pe
  - [ ] Verificar SSL activo (https funcionando)
  - [ ] Probar acceso desde dispositivos externos

---

### 2. SEGURIDAD

- [ ] **Variables de entorno en producción**
  - [ ] Verificar que SECRET_KEY sea fuerte (no la del .env de desarrollo)
  - [ ] Confirmar DATABASE_URL apunta a producción
  - [ ] Verificar que FLASK_ENV=production
  - [ ] SESSION_COOKIE_SECURE=True (ya configurado)

- [ ] **Revisar permisos de usuario**
  - [ ] Probar login con cada rol (Master, Operador, Trader)
  - [ ] Verificar que Trader NO puede eliminar operaciones
  - [ ] Verificar que Operador puede gestionar clientes

- [ ] **Configurar rate limiting**
  - Ya está configurado en el código
  - [ ] Probar que funcione en producción

- [ ] **Auditoría de logs**
  - [ ] Verificar que logs se están generando en Render
  - [ ] Revisar logs de errores recientes

---

### 3. BACKUPS (CRÍTICO)

#### 3.1 Base de Datos

- [ ] **Backups automáticos de Render**
  - Verificar en dashboard que están activos
  - Frecuencia: Diaria (automática)
  - Retención: 7 días (plan Starter)

- [ ] **Backups manuales adicionales (OBLIGATORIO)**
  - [ ] Instalar PostgreSQL client en tu máquina local
    - Windows: https://www.postgresql.org/download/windows/
    - Necesitas `pg_dump` command

  - [ ] Probar backup manual:
    ```bash
    pg_dump postgresql://qoricash_v2_user:ZcytxqQkILNGwGOkzTpw7PFDWGSUCZpM@dpg-d4eevk3gk3sc73bmu3u0-a.oregon-postgres.render.com/qoricash_v2 > backup_manual.sql
    ```

  - [ ] Configurar backup automático semanal
    - Usar script: `scripts/backup_database.bat`
    - Configurar en Programador de Tareas de Windows
    - Ejecutar cada domingo a las 2:00 AM
    - Guardar backups en: `C:\Backups\QoriCash\Database\`

  - [ ] Configurar backup en la nube
    - Opción A: Google Drive (sync folder de backups)
    - Opción B: Dropbox
    - Opción C: OneDrive
    - Recomendación: Guardar últimos 30 días

#### 3.2 Código fuente

- [ ] **GitHub como repositorio principal**
  - ✅ Ya configurado
  - [ ] Verificar que el repositorio sea PRIVADO
  - [ ] Verificar que `.env` esté en `.gitignore`

- [ ] **Backup local del código**
  - [ ] Clonar repo en máquina local: `git clone https://github.com/ggarciaperion/qoricash.git`
  - [ ] Hacer `git pull` semanalmente
  - [ ] Guardar copia en disco externo mensualmente

#### 3.3 Archivos (Cloudinary)

- [ ] **Verificar plan de Cloudinary**
  - [ ] Ir a: https://cloudinary.com/console
  - [ ] Verificar uso actual de almacenamiento
  - [ ] Configurar alerta cuando llegues a 20GB (80% del free tier)

- [ ] **Backup de archivos (cuando sea necesario)**
  - Por ahora NO necesario (Cloudinary tiene redundancia)
  - Cuando llegues a 15GB, considerar exportar archivos

---

### 4. MONITOREO

- [ ] **Configurar alertas en Render**
  - [ ] Alertas de caída del servicio (email)
  - [ ] Alertas de uso de CPU/RAM excesivo
  - [ ] Alertas de errores 500

- [ ] **Monitoreo manual semanal**
  - [ ] Revisar logs en Render cada lunes
  - [ ] Verificar que backups se ejecutaron correctamente
  - [ ] Revisar uso de almacenamiento en Cloudinary

- [ ] **Herramientas de monitoreo (Opcional pero recomendado)**
  - [ ] Configurar UptimeRobot (gratis): https://uptimerobot.com
    - Monitorea que app.qoricash.pe esté online 24/7
    - Te avisa por email/SMS si se cae
  - [ ] Configurar Google Analytics (opcional para métricas)

---

### 5. PRUEBAS FINALES

- [ ] **Pruebas funcionales**
  - [ ] Crear operación de prueba (Compra)
  - [ ] Crear operación de prueba (Venta)
  - [ ] Completar operación con comprobantes
  - [ ] Verificar que emails se envían correctamente
  - [ ] Descargar Excel de Posición
  - [ ] Descargar Excel de Historial
  - [ ] Probar búsqueda de clientes
  - [ ] Probar filtros en tablas

- [ ] **Pruebas de rendimiento**
  - [ ] Abrir 3-4 pestañas simultáneas con diferentes usuarios
  - [ ] Simular carga de 10 operaciones seguidas
  - [ ] Verificar que no haya lentitud

- [ ] **Pruebas de roles**
  - [ ] Login como Master → Probar todas las funciones
  - [ ] Login como Operador → Verificar permisos
  - [ ] Login como Trader → Verificar restricciones

- [ ] **Pruebas de emails**
  - [ ] Verificar email de nueva operación
  - [ ] Verificar email de operación completada
  - [ ] Verificar email de registro de cliente
  - [ ] Verificar que NO contenga información sensible

---

### 6. DOCUMENTACIÓN

- [ ] **Crear manual de usuario**
  - [ ] Cómo crear una operación
  - [ ] Cómo completar una operación
  - [ ] Cómo registrar clientes
  - [ ] Cómo descargar reportes
  - [ ] Cómo cambiar tipo de cambio

- [ ] **Documentar credenciales importantes**
  - [ ] Render login
  - [ ] Cloudinary login
  - [ ] GitHub repository
  - [ ] Credenciales de email
  - [ ] Guardar en lugar seguro (LastPass, 1Password, etc.)

- [ ] **Contactos de emergencia**
  - [ ] Soporte técnico (si tienes)
  - [ ] Procedimiento si se cae el sistema
  - [ ] Procedimiento de recuperación desde backup

---

### 7. CAPACITACIÓN DE USUARIOS

- [ ] **Crear usuarios de producción**
  - [ ] Crear 8 usuarios con emails reales
  - [ ] Asignar roles apropiados
  - [ ] Enviar credenciales de forma segura

- [ ] **Sesión de capacitación**
  - [ ] Mostrar cómo usar el sistema
  - [ ] Explicar flujo de operaciones
  - [ ] Resolver dudas
  - [ ] Practicar con datos de prueba

- [ ] **Guía rápida**
  - [ ] Crear documento PDF con pasos básicos
  - [ ] Incluir capturas de pantalla
  - [ ] Distribuir a todos los usuarios

---

### 8. PLAN DE CONTINGENCIA

- [ ] **¿Qué hacer si se cae Render?**
  1. Verificar status: https://status.render.com
  2. Revisar logs en dashboard
  3. Reiniciar servicio manualmente si es necesario
  4. Contactar soporte de Render

- [ ] **¿Qué hacer si se pierde la base de datos?**
  1. Ir a Render Dashboard → PostgreSQL → Backups
  2. Restaurar último backup automático
  3. Si no funciona, usar backup manual local
  4. Importar con: `psql DATABASE_URL < backup.sql`

- [ ] **¿Qué hacer si se excede límite de Cloudinary?**
  1. Actualizar a plan PLUS ($89/mes)
  2. O migrar a S3 (contactarme para ayuda)

---

## 📋 RESPUESTAS A TUS PREGUNTAS

### ¿Necesito migrar de Cloudinary?
**NO por ahora.** El plan Free (25GB) es suficiente por 6-8 meses. Cuando llegues a 20GB, evalúa:
- Opción A: Plan PLUS de Cloudinary ($89/mes)
- Opción B: Migrar a Amazon S3 (~$1/mes) - más técnico pero mucho más barato

### ¿Necesito migrar de Render?
**NO.** Render es perfecto para tu escala. Solo actualiza a plan Starter ($7/mes) para evitar que el servicio se "duerma".

### ¿Necesito migrar de PostgreSQL?
**NO.** El plan de PostgreSQL en Render ($7/mes) soporta tu volumen sin problemas por años.

### ¿Cómo guardo los archivos del código?
- **Principal**: GitHub (privado) ✅ Ya lo tienes
- **Backup local**: Tu máquina (hacer `git pull` semanal)
- **Backup externo**: Disco duro externo mensualmente (opcional)

### ¿Qué más necesito?
1. ✅ Backups automáticos de base de datos (CRÍTICO)
2. ✅ Monitoreo con UptimeRobot (gratis)
3. ✅ Documentación para usuarios
4. ✅ Plan de contingencia

---

## 💰 COSTOS MENSUALES ESTIMADOS

| Servicio | Plan | Costo |
|----------|------|-------|
| Render Web Service | Starter | $7 |
| Render PostgreSQL | Starter | $7 |
| Cloudinary | Free | $0 |
| Dominio punto.pe | - | ~$15/año |
| **TOTAL MENSUAL** | | **$14-$15** |

**Nota**: Cuando crezcas más allá de 25GB en Cloudinary, sumarían $89/mes o migramos a S3 por $1-2/mes.

---

## 🎯 PRÓXIMOS PASOS INMEDIATOS

1. [ ] Verificar que estás en plan Starter de Render ($7/mes)
2. [ ] Configurar backup semanal de base de datos
3. [ ] Configurar UptimeRobot para monitoreo
4. [ ] Crear usuarios de producción
5. [ ] Capacitar a tu equipo
6. [ ] ¡INICIAR OPERACIONES! 🚀

---

## 📞 SOPORTE

Si tienes dudas o problemas:
- Revisar este checklist
- Revisar logs en Render
- Contactar soporte técnico

**Sistema listo para producción con tu volumen actual. NO necesitas migraciones complejas.**
