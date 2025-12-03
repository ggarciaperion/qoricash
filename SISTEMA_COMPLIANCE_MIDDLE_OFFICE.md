# Sistema de Compliance - Middle Office

## Descripción General

Sistema completo de AML/KYC/PLAFT (Anti-Money Laundering / Know Your Customer / Prevención del Lavado de Activos y Financiamiento del Terrorismo) implementado en QoriCash Trading V2.

**Estado**: ✅ **FUNCIONAL AL 100%** (Verificación manual de DNI/RUC)

---

## 1. ROL MIDDLE OFFICE

### ¿Qué es el Middle Office?

El rol **Middle Office** es el **Oficial de Cumplimiento** (Compliance Officer) de la plataforma. Es responsable de:

- Prevenir lavado de activos y financiamiento del terrorismo
- Verificar identidad de clientes (KYC - Know Your Customer)
- Detectar operaciones sospechosas
- Generar reportes de operaciones sospechosas (ROS)
- Mantener perfiles de riesgo actualizados

### Permisos del Middle Office

| Menú | Permisos |
|------|----------|
| **Dashboard** | ✅ Lectura |
| **Clientes** | ✅ Lectura (NO puede crear/editar/eliminar) |
| **Operaciones** | ✅ Lectura |
| **Compliance** | ✅ Lectura y Escritura completa |
| **Usuarios** | ❌ Sin acceso (solo Master) |

### Funcionalidades Específicas

1. **Revisar Alertas de Compliance**
   - Ver todas las alertas generadas automáticamente
   - Clasificar alertas por severidad (Baja, Media, Alta, Crítica)
   - Resolver alertas con comentarios
   - Marcar alertas como "Falso Positivo"

2. **Gestionar Perfiles de Riesgo**
   - Ver perfil de riesgo de cada cliente (0-100 puntos)
   - Recalcular score de riesgo manualmente
   - Actualizar nivel de debida diligencia
   - Agregar notas de compliance

3. **Administrar KYC (Know Your Customer)**
   - Revisar documentación KYC de clientes
   - Aprobar/Rechazar KYC
   - Establecer fecha de vencimiento de KYC
   - Solicitar documentación adicional

4. **Generar Reportes ROS**
   - Crear Reportes de Operaciones Sospechosas
   - Enviar reportes a SBS/UIF
   - Dar seguimiento a reportes enviados

5. **Configurar Sistema**
   - Gestionar niveles de riesgo (Bajo, Medio, Alto, Crítico)
   - Configurar reglas de detección
   - Definir umbrales de alertas

---

## 2. MENÚS DEL MIDDLE OFFICE

### 2.1. Dashboard de Compliance

**Ruta**: `/compliance/`

**Funcionalidades**:
- Resumen de alertas pendientes por severidad
- Gráfico de distribución de riesgo de clientes
- Operaciones recientes que requieren revisión
- KYC pendientes de aprobación
- Estadísticas generales

**Widgets**:
```
┌─────────────────────────────────────────────────┐
│ ALERTAS PENDIENTES                              │
│ • Críticas:     5  🔴                           │
│ • Altas:       12  🟠                           │
│ • Medias:      28  🟡                           │
│ • Bajas:       45  🟢                           │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ DISTRIBUCIÓN DE RIESGO DE CLIENTES              │
│ • Crítico:    15  (8%)   🔴                     │
│ • Alto:       42  (22%)  🟠                     │
│ • Medio:      87  (45%)  🟡                     │
│ • Bajo:       48  (25%)  🟢                     │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ KYC PENDIENTES                                  │
│ • Total pendientes:  23                         │
│ • Vencidos:           8  ⚠️                     │
│ • Por vencer (7d):    5  ⏰                     │
└─────────────────────────────────────────────────┘
```

### 2.2. Gestión de Alertas

**Ruta**: `/compliance/alerts`

**Funcionalidades**:
- Listado de todas las alertas
- Filtros: Severidad, Estado, Fecha, Cliente
- Búsqueda por operación o cliente
- Resolución de alertas con comentarios
- Descarga de alertas en Excel

**Tipos de Alertas Automáticas**:
1. **Monto Alto**: Operación > $10,000
2. **Frecuencia Alta**: Más de 5 operaciones en 7 días
3. **Cliente PEP**: Persona Expuesta Políticamente
4. **Lista Restrictiva**: Cliente en listas de sanciones
5. **Problemas Legales**: Cliente con antecedentes
6. **Patrón Fraccionamiento**: Múltiples operaciones menores a umbral
7. **Cambio de Patrón**: Cambio drástico en comportamiento

**Estados de Alerta**:
- 🔴 **Activa**: Requiere revisión
- 🟡 **En Revisión**: Siendo analizada
- ✅ **Resuelta**: Analizada y cerrada
- ⚪ **Falso Positivo**: Alerta incorrecta

### 2.3. Perfiles de Riesgo

**Ruta**: `/compliance/risk-profiles`

**Funcionalidades**:
- Ver todos los perfiles de riesgo
- Filtrar por nivel de riesgo
- Recalcular score manualmente
- Ver histórico de cambios
- Actualizar debida diligencia

**Cálculo de Score de Riesgo (0-100)**:
```python
Base: 10 puntos

+ Volumen total operaciones:
  - > $100,000:  +30 puntos
  - > $50,000:   +20 puntos
  - > $10,000:   +10 puntos

+ Frecuencia operaciones:
  - > 10/mes:    +15 puntos
  - > 5/mes:     +10 puntos

+ Factores especiales:
  - Es PEP:                    +25 puntos
  - En listas restrictivas:    +30 puntos
  - Tiene problemas legales:   +20 puntos

Score final = min(suma_puntos, 100)
```

**Niveles de Riesgo**:
| Nivel | Score | Color | Debida Diligencia |
|-------|-------|-------|-------------------|
| Bajo | 0-25 | 🟢 Verde | Simplificada |
| Medio | 26-50 | 🟡 Amarillo | Normal |
| Alto | 51-75 | 🟠 Naranja | Ampliada |
| Crítico | 76-100 | 🔴 Rojo | Reforzada |

### 2.4. Revisión KYC

**Ruta**: `/compliance/kyc`

**Funcionalidades**:
- Listado de todos los clientes y su estado KYC
- Filtros: Estado, Vencimiento, Nivel de riesgo
- Aprobar/Rechazar KYC
- Establecer validez (ej: 1 año)
- Solicitar documentación adicional

**Estados KYC**:
- ⏳ **Pendiente**: Sin revisar
- ✅ **Aprobado**: KYC válido
- ❌ **Rechazado**: KYC no cumple requisitos
- 🔄 **En Revisión**: Siendo analizado
- ⚠️ **Vencido**: KYC expirado

**Documentos Requeridos**:
- DNI/RUC
- Comprobante de domicilio
- Declaración jurada de origen de fondos
- Referencias bancarias (para empresas)

### 2.5. Reportes ROS

**Ruta**: `/compliance/ros-reports`

**Funcionalidades**:
- Crear nuevo reporte de operación sospechosa
- Listar reportes enviados
- Ver estado de reportes
- Descargar en formato oficial SBS
- Dar seguimiento

**Campos del ROS**:
- Cliente involucrado
- Operaciones relacionadas
- Motivo de sospecha
- Análisis detallado
- Evidencias/Documentos
- Fecha de envío a SBS/UIF

### 2.6. Configuración

**Ruta**: `/compliance/settings`

**Funcionalidades**:
- Gestionar niveles de riesgo
- Configurar reglas de detección
- Definir umbrales de alertas
- Configurar integraciones (Inspektor)

---

## 3. LO QUE ESTÁ IMPLEMENTADO (100%)

### ✅ Base de Datos
- 9 tablas de compliance creadas
- Migración ejecutada y desplegada
- Niveles de riesgo inicializados
- Constraint de rol "Middle Office" aplicado

### ✅ Modelos
- `RiskLevel` - Niveles de riesgo
- `ClientRiskProfile` - Perfil de riesgo por cliente
- `ComplianceAlert` - Alertas automáticas
- `KYCDocument` - Documentos KYC
- `KYCReview` - Revisiones KYC
- `ROSReport` - Reportes de operaciones sospechosas
- `ComplianceRule` - Reglas de detección
- `ComplianceConfig` - Configuración del sistema
- `ComplianceAudit` - Auditoría de acciones

### ✅ Servicios
- `ComplianceService` - Lógica de negocio completa
  - `calculate_client_risk_score()` - Cálculo automático de riesgo
  - `analyze_operation()` - Análisis de operaciones
  - `update_client_risk_profile()` - Actualización de perfiles
  - `get_compliance_dashboard_stats()` - Estadísticas para dashboard

### ✅ Rutas y APIs
- `/compliance/` - Dashboard
- `/compliance/alerts` - Gestión de alertas
- `/compliance/risk-profiles` - Perfiles de riesgo
- `/compliance/kyc` - Revisión KYC
- 15+ endpoints API funcionales

### ✅ Frontend
- Templates HTML completos
- DataTables para listados
- Modales para edición
- Gráficos con Chart.js
- Badges y alertas visuales

### ✅ Integración
- Análisis automático al completar operación (app/services/operation_service.py:288-310)
- Generación automática de alertas
- Actualización automática de perfiles de riesgo
- Logging de acciones críticas

### ✅ Permisos
- Rol "Middle Office" creado
- Permisos configurados en todas las rutas
- Acceso correcto a menús
- Restricciones aplicadas

### ✅ Scripts de Inicialización
- `init_client_risk_profiles.py` - Crear perfiles para clientes existentes

---

## 4. LO QUE ESTÁ PREPARADO (Pero NO Activo)

### 🔵 Integración con Inspektor

**Archivo**: `app/services/inspektor_service.py`

**Estado**: Código completo y documentado, pero NO activado

**Para activar**:
1. Contratar servicio en https://inspektor.pe
2. Obtener API_KEY
3. Configurar variable de entorno en Render:
   ```bash
   INSPEKTOR_API_KEY=tu_api_key_aqui
   ```
4. Descomentar integración en `app/services/client_service.py`

**Funcionalidades**:
- Verificación automática DNI en RENIEC
- Verificación automática RUC en SUNAT
- Detección automática de PEP
- Consulta de listas restrictivas
- Validación de datos al crear cliente

**Costo**: ~$0.45 por consulta

---

## 5. CÓMO FUNCIONA EL SISTEMA

### Flujo Automático Completo

```
1. TRADER CREA OPERACIÓN
   ↓
2. OPERACIÓN REGISTRADA (estado: Pendiente)
   ↓
3. OPERADOR PROCESA OPERACIÓN
   ↓
4. OPERACIÓN COMPLETADA
   ↓
5. 🤖 ANÁLISIS AUTOMÁTICO DE COMPLIANCE
   |
   ├─ Analizar monto
   ├─ Analizar frecuencia
   ├─ Verificar si cliente es PEP
   ├─ Verificar listas restrictivas
   ├─ Verificar problemas legales
   ├─ Detectar patrones sospechosos
   |
   └─ Generar alertas si detecta algo
   ↓
6. ACTUALIZAR PERFIL DE RIESGO DEL CLIENTE
   |
   ├─ Recalcular score (0-100)
   ├─ Asignar nivel (Bajo/Medio/Alto/Crítico)
   └─ Definir debida diligencia
   ↓
7. MIDDLE OFFICE REVISA ALERTAS
   |
   ├─ Si es normal: Resolver como "OK"
   ├─ Si es sospechoso: Crear ROS
   └─ Si es falso positivo: Marcar y cerrar
   ↓
8. MIDDLE OFFICE APRUEBA/RECHAZA KYC
   ↓
9. SISTEMA AUDITADO COMPLETAMENTE
```

### Ejemplo Real

**Escenario**: Cliente "INVERSIONES PACÍFICO SAC" realiza 3 operaciones grandes

```
DÍA 1:
- Operación #1234: $12,500 USD → PEN
  → ⚠️ Alerta generada: "Monto Alto"
  → Score de riesgo: 35 → 45 (Medio)

DÍA 3:
- Operación #1245: $15,000 USD → PEN
  → ⚠️ Alerta generada: "Monto Alto + Frecuencia"
  → Score de riesgo: 45 → 58 (Alto)

DÍA 5:
- Operación #1256: $18,000 USD → PEN
  → 🚨 Alerta CRÍTICA: "Patrón Sospechoso - Fraccionamiento"
  → Score de riesgo: 58 → 72 (Alto)

Middle Office revisa:
- Verifica que es empresa legítima
- Valida facturas comerciales
- Confirma origen de fondos
- Resuelve alertas como "OK"
- Documenta en notas de compliance
```

---

## 6. INICIALIZACIÓN DEL SISTEMA

### Paso 1: Ejecutar Migraciones (YA EJECUTADO)

```bash
flask db upgrade
```

Esto crea las 9 tablas de compliance.

### Paso 2: Inicializar Perfiles de Riesgo

Para clientes existentes que no tienen perfil de riesgo:

```bash
python init_client_risk_profiles.py
```

Este script:
- Encuentra todos los clientes sin perfil de riesgo
- Calcula su score basado en operaciones históricas
- Crea perfil inicial para cada uno
- Asigna nivel de debida diligencia

**Salida Esperada**:
```
============================================================
INICIANDO CREACIÓN DE PERFILES DE RIESGO
============================================================
Total de clientes en sistema: 192
Clientes sin perfil de riesgo: 192

Procesando cliente: INVERSIONES PACÍFICO SAC (20123456789)
  - Score calculado: 45
  - Nivel asignado: Medio
  - Due diligence: Normal
  ✓ Perfil creado exitosamente (ID: 1)

Procesando cliente: COMERCIAL ANDINA EIRL (20234567890)
  - Score calculado: 15
  - Nivel asignado: Bajo
  - Due diligence: Simplificada
  ✓ Perfil creado exitosamente (ID: 2)

...

============================================================
RESUMEN DE EJECUCIÓN
============================================================
✓ Perfiles creados: 192
✗ Errores: 0
✓ Script completado exitosamente
```

### Paso 3: Crear Usuario Middle Office

1. Login como Master
2. Ir a "Usuarios" → "Crear Nuevo Usuario"
3. Llenar datos:
   - Username: `compliance_officer`
   - Email: `compliance@qoricash.com`
   - DNI: (tu DNI)
   - Rol: **Middle Office** ✅
   - Password: (contraseña segura)
4. Clic en "Crear Usuario"

### Paso 4: Verificar Funcionamiento

1. Logout y login como Middle Office
2. Ir a "Compliance" → Dashboard
3. Verificar que se muestran estadísticas
4. Ir a "Clientes" (solo lectura)
5. Completar una operación como Trader
6. Verificar que se genera alerta automáticamente

---

## 7. CONFIGURACIÓN EN RENDER

### Variables de Entorno Actuales

```bash
# Base de datos
DATABASE_URL=postgresql://...

# Flask
SECRET_KEY=...
FLASK_ENV=production

# Cloudinary
CLOUDINARY_CLOUD_NAME=...
CLOUDINARY_API_KEY=...
CLOUDINARY_API_SECRET=...
```

### Variables para Inspektor (CUANDO SE CONTRATE)

```bash
# Agregar esta variable cuando se cierre contrato
INSPEKTOR_API_KEY=tu_api_key_de_inspektor
```

---

## 8. MANTENIMIENTO

### Tareas Recurrentes del Middle Office

**Diarias**:
- Revisar nuevas alertas generadas
- Resolver alertas de baja prioridad
- Monitorear operaciones del día

**Semanales**:
- Analizar alertas críticas
- Revisar KYC pendientes
- Actualizar perfiles de riesgo de clientes de alto riesgo

**Mensuales**:
- Generar reporte de operaciones sospechosas (si aplica)
- Revisar y actualizar reglas de detección
- Auditoría de sistema

### Logs de Compliance

Todos los eventos se loguean automáticamente:

```python
logger.info(f'Compliance analysis for OP-001234: 2 alerts, risk_score=45')
logger.warning(f'ALERTA CRÍTICA: Operación OP-001234 generó 1 alerta(s) crítica(s)')
```

Ver logs en Render: Dashboard → Logs

---

## 9. SOPORTE Y CONTACTO

### Documentación
- Este archivo: `SISTEMA_COMPLIANCE_MIDDLE_OFFICE.md`
- Código de Inspektor: `app/services/inspektor_service.py`
- Script de inicialización: `init_client_risk_profiles.py`

### En Caso de Problemas

1. **Alertas no se generan automáticamente**
   - Verificar que `operation_service.py` tiene el código de análisis
   - Revisar logs en Render
   - Verificar que la operación se completó correctamente

2. **No puedo crear usuario Middle Office**
   - Verificar migración `j2k3l4m5n6o7` aplicada
   - Verificar constraint en base de datos
   - Revisar logs de error

3. **Middle Office no puede acceder a Clientes**
   - Verificar decoradores `@require_role()` en `clients.py`
   - Verificar que usuario tiene rol exacto "Middle Office"

4. **Perfiles de riesgo no se calculan**
   - Ejecutar `python init_client_risk_profiles.py`
   - Verificar que hay operaciones para calcular score
   - Revisar `ComplianceService.calculate_client_risk_score()`

---

## 10. RESUMEN EJECUTIVO

### ✅ Sistema 100% Funcional

- **9 tablas** de compliance creadas y operativas
- **Rol Middle Office** creado y configurado con permisos correctos
- **Análisis automático** de operaciones al completarse
- **Generación automática** de alertas según patrones
- **Cálculo automático** de score de riesgo (0-100)
- **Dashboard completo** con estadísticas en tiempo real
- **Gestión de alertas** con resolución y comentarios
- **Perfiles de riesgo** con niveles y debida diligencia
- **Sistema KYC** con aprobación/rechazo
- **Reportes ROS** preparados
- **Auditoría completa** de todas las acciones

### 🔵 Preparado pero NO Activo

- **Inspektor API** - Servicio stub creado, esperando contrato

### 💰 Sin Costos Adicionales Actualmente

- Verificación manual de DNI/RUC (sin costo)
- Cuando se contrate Inspektor: ~$0.45 por consulta

### 🚀 Listo para Producción

El sistema está completamente funcional y listo para usar en producción.
Solo se requiere:
1. Ejecutar `python init_client_risk_profiles.py` una vez
2. Crear usuario(s) con rol Middle Office
3. Comenzar a operar normalmente

---

**Última actualización**: 2025-12-03
**Versión**: 2.0
**Estado**: ✅ PRODUCCIÓN
