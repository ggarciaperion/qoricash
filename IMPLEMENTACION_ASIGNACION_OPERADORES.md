# Sistema de Asignación Automática de Operadores

## Descripción

Se ha implementado un sistema de asignación automática y balanceada de operadores para prevenir que múltiples operadores procesen la misma operación simultáneamente, evitando así pagos duplicados a clientes.

## Características Implementadas

### 1. **Asignación Automática y Balanceada**
- Cuando una operación se envía a "En proceso", se asigna automáticamente a un operador
- El algoritmo distribuye las operaciones equitativamente entre todos los operadores activos
- El operador con menos operaciones "En proceso" asignadas recibe la nueva operación

### 2. **Restricciones de Edición**
- **Operadores**: Solo pueden editar, procesar y completar las operaciones asignadas a ellos
- **Master**: Puede editar todas las operaciones sin restricciones
- **Traders**: No se ven afectados, siguen editando operaciones en estado "Pendiente"

### 3. **Visibilidad Total**
- **Todos los operadores pueden VER todas las operaciones** (lectura)
- Solo pueden **EDITAR** las que están asignadas a ellos
- Esto permite supervisión y coordinación entre operadores

### 4. **Notificaciones Personalizadas**
- Cada operador solo recibe notificaciones de las operaciones asignadas a él
- No se notifica sobre operaciones de otros operadores

## Archivos Modificados

### Backend

#### 1. `app/models/operation.py`
**Cambios:**
- Agregado campo `assigned_operator_id` (FK a users.id)
- Agregado método `can_operator_edit(operator_user_id)` con validación de asignación
- Agregado método `is_assigned_to_operator(operator_user_id)`
- Actualizado `to_dict()` para incluir `assigned_operator_id` y `assigned_operator_name`

**Líneas modificadas:**
- Línea 24: Nuevo campo `assigned_operator_id`
- Líneas 342-372: Métodos de validación actualizados
- Línea 279: Agregado `assigned_operator_id` a `to_dict()`
- Líneas 314-319: Agregado `assigned_operator_name` cuando `include_relations=True`

#### 2. `app/services/operation_service.py`
**Cambios:**
- Agregado método estático `assign_operator_balanced()` para asignación balanceada

**Implementación del algoritmo:**
```python
def assign_operator_balanced():
    # 1. Obtener todos los operadores activos
    operators = User.query.filter(
        User.role == 'Operador',
        User.status == 'Activo'
    ).all()

    # 2. Contar operaciones "En proceso" de cada operador
    operator_loads = {}
    for operator in operators:
        count = Operation.query.filter(
            Operation.assigned_operator_id == operator.id,
            Operation.status == 'En proceso'
        ).count()
        operator_loads[operator.id] = count

    # 3. Asignar al operador con menos carga
    min_load_operator_id = min(operator_loads, key=operator_loads.get)
    return min_load_operator_id
```

**Líneas agregadas:**
- Líneas 444-488: Función de asignación balanceada

#### 3. `app/routes/operations.py`
**Cambios:**

**a) Función `send_to_process` (líneas 741-762):**
- Asignación automática de operador al enviar a proceso
- Registro de asignación en AuditLog

```python
# Asignar operador automáticamente
assigned_operator_id = OperationService.assign_operator_balanced()
if assigned_operator_id:
    operation.assigned_operator_id = assigned_operator_id
```

**b) Función `return_to_pending` (líneas 804-810):**
- Validación de que solo el operador asignado puede devolver
- Limpieza de `assigned_operator_id` al devolver a pendiente

```python
# Verificar asignación (Master puede editar todas)
if current_user.role == 'Operador':
    if not operation.is_assigned_to_operator(current_user.id):
        return error 403: "Operación asignada a otro operador"
```

**c) Función `complete_operation` (líneas 873-879):**
- Validación de que solo el operador asignado puede completar
- Limpieza de `assigned_operator_id` al completar

**d) Función `check_pending_operations` (líneas 1096-1102):**
- Filtrado para mostrar solo operaciones asignadas al operador actual

```python
operations = Operation.query.filter(
    Operation.status == 'En proceso',
    Operation.assigned_operator_id == current_user.id  # Solo sus operaciones
).all()
```

### Migración de Base de Datos

#### 4. `add_assigned_operator_column.py`
**Script de migración que:**
- Agrega columna `assigned_operator_id` INTEGER
- Crea foreign key a `users(id)`
- Crea índice para optimizar consultas

**Ejecución:**
```bash
python add_assigned_operator_column.py
```

## Flujo Completo del Sistema

### Caso 1: Asignación de Operación

```
1. TRADER crea operación → Estado: "Pendiente"
   assigned_operator_id = NULL

2. TRADER envía a proceso
   ↓
   POST /operations/api/send_to_process/123
   ↓
   Backend ejecuta:
   - Validar sumas de abonos/pagos
   - operation.status = 'En proceso'
   - operation.in_process_since = now()
   - assigned_operator_id = assign_operator_balanced()
     ↓
     Algoritmo:
     - Operador 1: 2 operaciones en proceso
     - Operador 2: 1 operación en proceso  ← SELECCIONADO
     - Operador 3: 3 operaciones en proceso
   - operation.assigned_operator_id = 2 (Operador 2)
   - Guardar en BD

3. OPERADOR 2 recibe notificación (solo él)
   - Modal de notificación aparece
   - "Tienes 1 operación pendiente de atención"
```

### Caso 2: Intento de Edición por Operador No Asignado

```
OPERADOR 1 intenta completar operación asignada a OPERADOR 2

POST /operations/api/complete/123
↓
Validación en backend:
if current_user.role == 'Operador':
    if operation.assigned_operator_id != current_user.id:
        return 403: "Operación asignada a otro operador"
↓
RESULTADO: Operador 1 NO puede editar
```

### Caso 3: Master Editando Cualquier Operación

```
MASTER intenta completar operación asignada a OPERADOR 2

POST /operations/api/complete/123
↓
Validación en backend:
if current_user.role == 'Operador':  # FALSE, es Master
    # No se valida asignación
↓
RESULTADO: Master puede editar sin restricciones
```

### Caso 4: Devolución a Pendiente

```
OPERADOR 2 devuelve operación por corrección

POST /operations/api/return_to_pending/123
{
    "reason": "Falta comprobante de cliente"
}
↓
Backend ejecuta:
- operation.status = 'Pendiente'
- operation.in_process_since = NULL
- operation.assigned_operator_id = NULL  ← LIMPIA ASIGNACIÓN
↓
Operación vuelve al pool de "Pendientes"
Cuando se reenvíe a proceso, se asignará nuevamente (puede ser a otro operador)
```

## Balanceo de Carga - Ejemplos

### Escenario 1: Sistema Balanceado

```
Estado inicial:
- Operador A: 2 operaciones en proceso
- Operador B: 2 operaciones en proceso
- Operador C: 2 operaciones en proceso

Nueva operación se envía a proceso
↓
Se asigna al primero encontrado con carga mínima (empate)
→ Operador A (o B o C, dependiendo del orden en la base de datos)

Resultado:
- Operador A: 3 operaciones
- Operador B: 2 operaciones
- Operador C: 2 operaciones
```

### Escenario 2: Operador Sobrecargado

```
Estado inicial:
- Operador A: 5 operaciones en proceso
- Operador B: 1 operación en proceso
- Operador C: 2 operaciones en proceso

Nueva operación se envía a proceso
↓
min(5, 1, 2) = 1
→ Operador B recibe la asignación

Resultado:
- Operador A: 5 operaciones
- Operador B: 2 operaciones  ← ASIGNADO
- Operador C: 2 operaciones
```

### Escenario 3: Operador Inactivo

```
Estado inicial:
- Operador A: 2 operaciones, Status: Activo
- Operador B: 0 operaciones, Status: Inactivo
- Operador C: 3 operaciones, Status: Activo

Nueva operación se envía a proceso
↓
Solo se consideran operadores activos
min(2, 3) = 2
→ Operador A recibe la asignación

Resultado:
- Operador A: 3 operaciones  ← ASIGNADO
- Operador B: 0 operaciones (ignorado, inactivo)
- Operador C: 3 operaciones
```

## Beneficios del Sistema

### 1. **Prevención de Pagos Duplicados**
✅ Imposible que dos operadores procesen la misma operación
✅ Cada operación tiene un único responsable
✅ Validación a nivel de base de datos y aplicación

### 2. **Distribución Equitativa de Carga**
✅ Algoritmo balancea automáticamente
✅ Operadores nuevos reciben más operaciones inicialmente
✅ Operadores experimentados no se sobrecargan

### 3. **Trazabilidad y Responsabilidad**
✅ Cada operación tiene un operador asignado registrado
✅ Logs de auditoría incluyen información de asignación
✅ Fácil identificar quién procesó qué operación

### 4. **Flexibilidad para Master**
✅ Master puede intervenir en cualquier operación
✅ Útil para casos excepcionales o emergencias
✅ No se ve limitado por asignaciones

### 5. **Visibilidad Total para Coordinación**
✅ Todos los operadores ven todas las operaciones
✅ Facilita supervisión y apoyo entre equipo
✅ Transparencia en el proceso

## Limitaciones y Consideraciones

### 1. **Operador Sin Asignación**
Si no hay operadores activos al enviar a proceso:
- `assigned_operator_id` será `NULL`
- Master deberá procesar manualmente
- Se registra advertencia en logs

### 2. **Operador Desactivado Después de Asignación**
Si un operador se desactiva con operaciones asignadas:
- Operaciones asignadas permanecen asignadas a él
- Master puede reasignar manualmente cambiando `assigned_operator_id`
- Opción futura: Reasignar automáticamente al desactivar usuario

### 3. **Cambio Manual de Asignación**
Actualmente no existe UI para reasignar operaciones
- Solo Master puede hacerlo desde base de datos
- Opción futura: Agregar endpoint y UI para reasignar

## Testing Recomendado

### Test 1: Asignación Balanceada con 3 Operadores

1. Crear 3 usuarios operadores activos
2. Crear 6 operaciones y enviarlas a proceso
3. Verificar que cada operador recibió ~2 operaciones

**Consulta SQL para verificar:**
```sql
SELECT
    u.username,
    COUNT(o.id) as operaciones_asignadas
FROM users u
LEFT JOIN operations o ON o.assigned_operator_id = u.id
    AND o.status = 'En proceso'
WHERE u.role = 'Operador' AND u.status = 'Activo'
GROUP BY u.id, u.username
ORDER BY operaciones_asignadas;
```

### Test 2: Prevención de Edición Cruzada

1. Como Operador 1, intentar completar operación asignada a Operador 2
2. Verificar que retorna error 403
3. Como Master, completar la misma operación
4. Verificar que se permite

### Test 3: Notificaciones Solo al Asignado

1. Enviar operación a proceso (asignada a Operador 1)
2. Esperar 10 minutos
3. Verificar que solo Operador 1 recibe notificación
4. Operador 2 NO debe recibir notificación

### Test 4: Limpieza al Devolver

1. Enviar operación a proceso (asignada a Operador 1)
2. Operador 1 devuelve a pendiente
3. Verificar que `assigned_operator_id = NULL`
4. Reenviar a proceso
5. Puede asignarse a cualquier operador (nueva asignación)

## Instrucciones de Instalación

### Paso 1: Aplicar Migración

```bash
cd C:\Users\ACER\Desktop\qoricash-trading-v2
python add_assigned_operator_column.py
```

### Paso 2: Reiniciar Servidor

```bash
# Detener servidor actual
# Ctrl + C

# Reiniciar
python run.py
# o
flask run
```

### Paso 3: Verificar Funcionamiento

1. Crear operación como Trader
2. Enviar a proceso
3. Verificar en consola del servidor:
   ```
   Asignando operador: ID=2, Carga actual=1 operaciones
   Operación EXP-1001 asignada al operador ID: 2
   ```

4. Como Operador asignado, completar operación
5. Como otro Operador, intentar completar → Error 403

## Mantenimiento y Soporte

### Ver Asignaciones Actuales

```sql
SELECT
    o.operation_id,
    o.status,
    o.assigned_operator_id,
    u.username as operador_asignado
FROM operations o
LEFT JOIN users u ON u.id = o.assigned_operator_id
WHERE o.status = 'En proceso'
ORDER BY o.created_at DESC;
```

### Reasignar Operación Manualmente (Master)

```sql
UPDATE operations
SET assigned_operator_id = <nuevo_operador_id>
WHERE id = <operation_id>;
```

### Ver Carga de Cada Operador

```sql
SELECT
    u.username,
    COUNT(o.id) as operaciones_en_proceso,
    STRING_AGG(o.operation_id, ', ') as operation_ids
FROM users u
LEFT JOIN operations o ON o.assigned_operator_id = u.id
    AND o.status = 'En proceso'
WHERE u.role = 'Operador'
GROUP BY u.id, u.username
ORDER BY operaciones_en_proceso DESC;
```

## Próximas Mejoras Sugeridas

### 1. Indicadores Visuales en Frontend
- Badge mostrando "Asignada a ti" / "Asignada a [Nombre]"
- Filtro para ver solo operaciones propias
- Color diferente para operaciones asignadas

### 2. Reasignación Manual
- Endpoint para que Master pueda reasignar operaciones
- UI con dropdown para seleccionar nuevo operador
- Validación de que el nuevo operador esté activo

### 3. Estadísticas de Operadores
- Dashboard mostrando carga de cada operador
- Tiempo promedio de procesamiento por operador
- Tasa de devolución por operador

### 4. Notificaciones de Reasignación
- Notificar al operador cuando se le asigna operación
- Notificar si una operación se reasigna a otro

### 5. Priorización por Operador
- Operadores senior reciben operaciones complejas
- Operadores junior reciben operaciones simples
- Configuración de niveles de experiencia

---

**Fecha de Implementación:** 23 de Noviembre, 2025
**Versión:** 1.0
**Desarrollado por:** Claude Code
