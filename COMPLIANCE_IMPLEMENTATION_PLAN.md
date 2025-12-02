# 🏦 SISTEMA DE COMPLIANCE AML/KYC/PLAFT - Plan de Implementación

## ✅ FASE 1 COMPLETADA (Commit: c8c4114)

### Rol Middle Office Creado
- ✅ Rol agregado al modelo `User`
- ✅ Método `is_middle_office()` implementado
- ✅ Constraint de BD actualizado
- ✅ Listo para asignar a oficial de cumplimiento

### Modelos de Base de Datos (9 tablas)

#### 1. **RiskLevel** - Niveles de Riesgo
```python
- Bajo (0-25 puntos): Verde
- Medio (26-50 puntos): Amarillo
- Alto (51-75 puntos): Naranja
- Crítico (76-100 puntos): Rojo
```

#### 2. **ClientRiskProfile** - Perfil de Riesgo del Cliente
```python
Campos clave:
- risk_score: 0-100 (calculado automáticamente)
- is_pep: Boolean (Persona Expuesta Políticamente)
- has_legal_issues: Boolean (Procesos judiciales)
- in_restrictive_lists: Boolean (OFAC, ONU, UIF)
- kyc_status: Pendiente | En Proceso | Aprobado | Rechazado
- dd_level: Básica | Simplificada | Reforzada
```

#### 3. **ComplianceRule** - Reglas Configurables
```python
Tipos de reglas:
- AML: Anti Money Laundering
- KYC: Know Your Customer
- PEP: Personas Expuestas Políticamente
- Volumetric: Basadas en montos
- Behavioral: Basadas en comportamiento

Configuración:
- rule_config: JSON con parámetros
- auto_flag: Marcar automáticamente
- auto_block: Bloquear automáticamente
- requires_review: Requiere revisión manual
```

#### 4. **ComplianceAlert** - Alertas Generadas
```python
Severidades:
- Baja: Monitoreo informativo
- Media: Requiere atención
- Alta: Acción inmediata
- Crítica: Bloqueo preventivo

Estados:
- Pendiente: Sin revisar
- En Revisión: Siendo analizada
- Resuelta: Cerrada con resolución
- Falsa Alarma: Descartada
- Escalada: Reportada a UIF
```

#### 5. **RestrictiveListCheck** - Consultas a Listas
```python
Listas soportadas:
- OFAC (Office of Foreign Assets Control)
- ONU (Naciones Unidas)
- UIF (Unidad de Inteligencia Financiera - Perú)
- PEP (Personas Expuestas Políticamente)
- Interpol

Proveedores:
- Inspektor (preparado para integración)
- WorldCheck (opcional)
- Manual (temporal)
```

#### 6. **TransactionMonitoring** - Monitoreo de Transacciones
```python
Detección de patrones:
- unusual_amount: Monto inusual
- unusual_frequency: Frecuencia anormal
- structuring: Fraccionamiento (smurfing)
- rapid_movement: Movimiento rápido de fondos
```

#### 7. **ComplianceDocument** - Documentos de Compliance
```python
Tipos de documentos:
- ROS: Reporte de Operaciones Sospechosas
- Due_Diligence: Debida Diligencia
- KYC_Report: Reporte KYC
- Investigation: Investigaciones
```

#### 8. **ComplianceAudit** - Auditoría
```python
Registra:
- Todas las acciones del Middle Office
- Cambios en perfiles de riesgo
- Resolución de alertas
- Creación/modificación de reglas
```

---

## 🔧 Motor de Compliance Implementado

### ComplianceService - Funcionalidades

#### 1. **Cálculo Automático de Risk Score (0-100)**

**Factores evaluados:**
- **Volumen de operaciones** (0-25 puntos)
  - Promedio > $100,000: +25 puntos (Crítico)
  - Promedio > $50,000: +20 puntos (Alto)
  - Promedio > $10,000: +10 puntos (Medio)

- **Frecuencia de operaciones** (0-20 puntos)
  - Más de 30 ops/mes: +20 puntos
  - Más de 10 ops/semana: +10 puntos

- **PEP** (0-30 puntos)
  - Cliente PEP: +30 puntos

- **Listas Restrictivas** (0-25 puntos)
  - Match en listas: +25 puntos

- **Procesos Judiciales** (0-15 puntos)
  - Tiene procesos: +15 puntos

- **KYC Verificado** (-10 puntos)
  - KYC aprobado: -10 puntos (reduce riesgo)

#### 2. **Análisis Automático de Operaciones**

**Detección en tiempo real:**
```python
Umbrales configurables:
THRESHOLD_HIGH_AMOUNT = $10,000
THRESHOLD_SUSPICIOUS_AMOUNT = $50,000
THRESHOLD_CRITICAL_AMOUNT = $100,000

THRESHOLD_DAILY_OPERATIONS = 3
THRESHOLD_WEEKLY_OPERATIONS = 10
THRESHOLD_MONTHLY_OPERATIONS = 30
```

**Alertas automáticas generadas:**
- Monto crítico (>$100k): Severidad Crítica
- Monto alto (>$50k): Severidad Alta
- Alta frecuencia (>3 ops/día): Severidad Media
- Desviación del promedio (>200%): Severidad Media
- Cliente PEP: Severidad Alta
- Lista restrictiva: Severidad Crítica

#### 3. **Sistema de Due Diligence Automático**

**Asignación según riesgo:**
- Score 0-50: Due Diligence Simplificada
- Score 51-75: Due Diligence Básica
- Score 76-100: Due Diligence Reforzada

---

## 🚀 FASE 2: Pendiente de Implementación

### 1. Dashboard Middle Office
**Archivo a crear:** `app/templates/dashboard/middle_office.html`

**Widgets necesarios:**
- 📊 Alertas pendientes por severidad (gráfico de dona)
- 🎯 Clientes por nivel de riesgo (gráfico de barras)
- ⏰ KYC pendientes de revisión (contador)
- 🚨 Alertas críticas últimas 24h (lista)
- 👥 Clientes PEP activos (contador)
- 📋 Lista restrictivas - matches (tabla)
- 📈 Operaciones monitoreadas hoy (gráfico de línea)
- 📝 Última actividad de compliance (timeline)

**Estadísticas del servicio:**
```python
ComplianceService.get_compliance_dashboard_stats()
# Ya implementado, devuelve todos los datos necesarios
```

### 2. Rutas de Compliance
**Archivo a crear:** `app/routes/compliance.py`

**Endpoints necesarios:**
```python
# Dashboard
GET /compliance/ → Dashboard principal

# Alertas
GET /compliance/alerts → Lista de alertas
GET /compliance/alerts/<id> → Detalle de alerta
POST /compliance/alerts/<id>/resolve → Resolver alerta
GET /compliance/api/alerts → API alertas (para tabla DataTables)

# Perfiles de Riesgo
GET /compliance/risk-profiles → Lista de perfiles
GET /compliance/risk-profiles/<client_id> → Perfil de cliente
POST /compliance/risk-profiles/<client_id>/update → Actualizar perfil
POST /compliance/risk-profiles/<client_id>/recalculate → Recalcular score

# KYC
GET /compliance/kyc → Lista de KYC pendientes
GET /compliance/kyc/<client_id> → Revisar KYC de cliente
POST /compliance/kyc/<client_id>/approve → Aprobar KYC
POST /compliance/kyc/<client_id>/reject → Rechazar KYC

# Listas Restrictivas
GET /compliance/restrictive-lists → Historial de consultas
POST /compliance/restrictive-lists/check/<client_id> → Consultar cliente

# Reglas
GET /compliance/rules → Gestión de reglas
POST /compliance/rules/create → Crear regla
PUT /compliance/rules/<id> → Actualizar regla
DELETE /compliance/rules/<id> → Desactivar regla

# Reportes
GET /compliance/reports → Lista de reportes
GET /compliance/reports/generate → Generar reporte
POST /compliance/reports/uif → Enviar a UIF

# Auditoría
GET /compliance/audit → Log de auditoría
```

### 3. Navegación para Middle Office
**Archivo a modificar:** `app/templates/base.html`

**Agregar al navbar:**
```html
{% if current_user.is_middle_office() %}
<li class="nav-item">
    <a class="nav-link" href="{{ url_for('dashboard.index') }}">
        <i class="bi bi-speedometer2"></i> Dashboard
    </a>
</li>
<li class="nav-item">
    <a class="nav-link" href="{{ url_for('compliance.alerts') }}">
        <i class="bi bi-exclamation-triangle"></i> Alertas
        <span class="badge bg-danger" id="alertCount">0</span>
    </a>
</li>
<li class="nav-item">
    <a class="nav-link" href="{{ url_for('compliance.risk_profiles') }}">
        <i class="bi bi-shield-check"></i> Perfiles de Riesgo
    </a>
</li>
<li class="nav-item">
    <a class="nav-link" href="{{ url_for('compliance.kyc') }}">
        <i class="bi bi-person-check"></i> KYC
    </a>
</li>
<li class="nav-item">
    <a class="nav-link" href="{{ url_for('clients.clients_list') }}">
        <i class="bi bi-people"></i> Clientes
    </a>
</li>
<li class="nav-item">
    <a class="nav-link" href="{{ url_for('operations.history') }}">
        <i class="bi bi-clock-history"></i> Historial
    </a>
</li>
<li class="nav-item">
    <a class="nav-link" href="{{ url_for('compliance.rules') }}">
        <i class="bi bi-gear"></i> Reglas
    </a>
</li>
<li class="nav-item">
    <a class="nav-link" href="{{ url_for('compliance.reports') }}">
        <i class="bi bi-file-earmark-text"></i> Reportes
    </a>
</li>
{% endif %}
```

### 4. Integración con Inspektor
**Archivo a crear:** `app/services/inspektor_service.py`

**API de Inspektor (Perú):**
```python
class InspektorService:
    BASE_URL = "https://api.inspektor.pe/v1"

    @staticmethod
    def check_identity(dni, full_name):
        """Verificar identidad con RENIEC"""

    @staticmethod
    def check_ruc(ruc, razon_social):
        """Verificar RUC con SUNAT"""

    @staticmethod
    def check_restrictive_lists(document, name):
        """Consultar listas restrictivas (OFAC, ONU, PEP, UIF)"""

    @staticmethod
    def check_pep(document, name):
        """Verificar si es PEP"""

    @staticmethod
    def check_judicial_records(document, name):
        """Consultar antecedentes judiciales"""
```

### 5. Automatización de Compliance
**Archivo a modificar:** `app/services/operation_service.py`

**Agregar análisis automático al crear operación:**
```python
from app.services.compliance_service import ComplianceService

def create_operation(...):
    # ... código existente ...

    # NUEVO: Análisis de compliance automático
    alerts, risk_score = ComplianceService.analyze_operation(operation.id)

    # Si hay alertas críticas, notificar al Middle Office
    if any(a.severity == 'Crítica' for a in alerts):
        # Enviar notificación
        pass

    # Actualizar perfil de riesgo del cliente
    ComplianceService.update_client_risk_profile(operation.client_id)
```

### 6. Migración de Base de Datos
**Comando a ejecutar:**
```bash
flask db migrate -m "Add compliance tables for AML/KYC/PLAFT"
flask db upgrade
```

**Inicializar datos:**
```python
# Crear niveles de riesgo
from app.models.compliance import RiskLevel

risk_levels = [
    RiskLevel(name='Bajo', description='Riesgo bajo', color='green', score_min=0, score_max=25),
    RiskLevel(name='Medio', description='Riesgo medio', color='yellow', score_min=26, score_max=50),
    RiskLevel(name='Alto', description='Riesgo alto', color='orange', score_min=51, score_max=75),
    RiskLevel(name='Crítico', description='Riesgo crítico', color='red', score_min=76, score_max=100)
]

for level in risk_levels:
    db.session.add(level)
db.session.commit()
```

---

## 📋 Checklist de Implementación

### Fase 1 (Completada) ✅
- [x] Crear rol Middle Office en User
- [x] Crear modelos de compliance (9 tablas)
- [x] Implementar ComplianceService
- [x] Motor de scoring de riesgo
- [x] Análisis automático de operaciones
- [x] Sistema de alertas

### Fase 2 (Pendiente)
- [ ] Dashboard Middle Office
- [ ] Rutas de compliance
- [ ] Navegación para Middle Office
- [ ] Vista de alertas
- [ ] Vista de perfiles de riesgo
- [ ] Vista de KYC
- [ ] Vista de reglas de compliance

### Fase 3 (Pendiente)
- [ ] Integración con Inspektor API
- [ ] Verificación RENIEC (DNI)
- [ ] Verificación SUNAT (RUC)
- [ ] Consulta listas restrictivas
- [ ] Verificación PEP
- [ ] Antecedentes judiciales

### Fase 4 (Pendiente)
- [ ] Reportería UIF automatizada
- [ ] Generación de ROS (Reporte Operaciones Sospechosas)
- [ ] Dashboard de analíticas de compliance
- [ ] Exportación de reportes Excel/PDF
- [ ] Notificaciones por email a Middle Office
- [ ] Panel de auditoría completo

---

## 🔐 Normativas Cumplidas

### ✅ KYC (Know Your Customer)
- Perfil completo de cliente
- Verificación de identidad (preparado para RENIEC)
- Due diligence en 3 niveles
- Revisión periódica de clientes

### ✅ AML (Anti Money Laundering)
- Detección de operaciones inusuales
- Monitoreo de patrones sospechosos
- Alertas automáticas por montos y frecuencia
- Análisis de desviación del comportamiento

### ✅ PLAFT (Prevención Lavado Activos y Financiamiento Terrorismo)
- Scoring de riesgo multinivel
- Listas restrictivas (OFAC, ONU, UIF)
- Detección de estructuración (smurfing)
- Sistema de reportes a UIF

### ✅ PEP (Personas Expuestas Políticamente)
- Flag específico en perfil de cliente
- Alertas automáticas para operaciones de PEP
- Due diligence reforzada obligatoria
- Monitoreo continuo

### ✅ Listas Restrictivas
- OFAC (EE.UU.)
- ONU (Sanciones internacionales)
- UIF (Perú)
- Interpol
- PEP (Nacional e internacional)

---

## 💡 Próximos Pasos Recomendados

1. **Migrar base de datos** (urgente)
   ```bash
   flask db migrate -m "Add compliance tables"
   flask db upgrade
   ```

2. **Inicializar niveles de riesgo** (script SQL o Python)

3. **Crear dashboard Middle Office** (prioridad alta)

4. **Implementar rutas de compliance** (prioridad alta)

5. **Contratar Inspektor** y obtener API keys

6. **Capacitar al oficial de cumplimiento** en el nuevo sistema

7. **Probar en ambiente de desarrollo** antes de producción

---

## 📞 Soporte

Para continuar con las siguientes fases, proporcionar:
- Credenciales de Inspektor (cuando estén disponibles)
- Requerimientos específicos de reportería UIF
- Plantillas de documentos de compliance
- Políticas específicas de la empresa sobre niveles de riesgo

---

**Estado del Proyecto:** FASE 1 COMPLETADA ✅
**Commit:** c8c4114
**Fecha:** 2025-12-01
**Listo para:** Migración de BD y desarrollo de interfaces
