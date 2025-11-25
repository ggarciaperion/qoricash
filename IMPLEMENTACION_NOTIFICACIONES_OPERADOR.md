# Sistema de Notificaciones para Operaciones Pendientes - Operador

## Descripción

Se ha implementado un sistema de notificaciones automáticas para alertar a los usuarios con rol **Operador** cuando hay operaciones en estado "En proceso" que requieren atención inmediata.

## Características Implementadas

### 1. **Notificaciones Automáticas**
- **Primera alerta**: Se muestra después de 10 minutos de que una operación esté en estado "En proceso"
- **Alertas recurrentes**: Se muestran cada 5 minutos después de la primera alerta (a los 15, 20, 25 minutos, etc.)
- **Solo para Operadores**: Las notificaciones solo se muestran a usuarios con rol "Operador"

### 2. **Modal Bloqueante**
- La notificación aparece como un modal (ventana emergente) que interrumpe cualquier acción que esté realizando el operador
- El modal tiene fondo estático (`backdrop: static`) para evitar que se cierre accidentalmente
- No se puede cerrar presionando ESC o haciendo clic fuera del modal
- Solo se puede cerrar con los botones "Ver Operaciones" o "Entendido"

### 3. **Verificación Automática en Todas las Páginas**
- El sistema verifica operaciones pendientes cada 1 minuto
- Funciona en todas las páginas del sistema, no solo en el menú de Operaciones
- La verificación es transparente y no interfiere con el trabajo del operador

### 4. **Información Detallada**
La notificación muestra:
- ID de la operación (ej: EXP-1001)
- Nombre del cliente
- Tipo de operación (Compra/Venta)
- Monto en USD
- Tiempo transcurrido en estado "En proceso" (en minutos)
- Badge rojo indicando el tiempo de espera

### 5. **Acciones Disponibles**
- **Ver Operaciones**: Redirige al operador a la página de operaciones para atenderlas inmediatamente
- **Entendido**: Cierra la notificación (se volverá a mostrar en la siguiente verificación si la operación sigue pendiente)

## Archivos Modificados

### Backend

#### 1. `app/models/operation.py`
**Cambios:**
- Agregado campo `in_process_since` (DateTime) para registrar cuándo una operación entra en estado "En proceso"
- Agregado método `get_time_in_process_minutes()` para calcular el tiempo transcurrido
- Actualizado `to_dict()` para incluir `in_process_since` y `time_in_process_minutes`

**Líneas modificadas:**
- Línea 86: Agregado campo `in_process_since`
- Líneas 343-354: Nuevo método `get_time_in_process_minutes()`
- Líneas 267-268: Actualizado `to_dict()`

#### 2. `app/routes/operations.py`
**Cambios:**
- Modificado `send_to_process()` para establecer `in_process_since` cuando se envía a proceso
- Modificado `return_to_pending()` para limpiar `in_process_since` cuando se devuelve
- Modificado `complete_operation()` para limpiar `in_process_since` cuando se completa
- Agregado nuevo endpoint `/api/check_pending_operations` (GET) para verificar operaciones pendientes

**Líneas modificadas:**
- Línea 743: Establecer `in_process_since` en `send_to_process()`
- Línea 797: Limpiar `in_process_since` en `return_to_pending()`
- Línea 869: Limpiar `in_process_since` en `complete_operation()`
- Líneas 1051-1100: Nuevo endpoint `check_pending_operations()`

**Endpoint `check_pending_operations()`:**
```python
GET /operations/api/check_pending_operations
Rol requerido: Operador
Retorna: JSON con lista de operaciones en proceso por 10+ minutos
```

### Frontend

#### 3. `app/templates/base.html`
**Cambios:**
- Agregado modal `pendingOperationsAlertModal` para mostrar alertas (solo visible para Operador)
- Modal con `data-bs-backdrop="static"` y `data-bs-keyboard="false"` para hacerlo bloqueante

**Líneas agregadas:**
- Líneas 181-208: Modal de notificaciones pendientes

#### 4. `app/static/js/common.js`
**Cambios:**
- Agregada función `initPendingOperationsMonitor()` para iniciar monitoreo
- Agregada función `checkPendingOperations()` para verificar operaciones cada minuto
- Agregada función `showPendingOperationsAlert()` para mostrar el modal
- Agregados event listeners para los botones del modal
- Llamada automática a `initPendingOperationsMonitor()` al cargar la página (solo para Operador)

**Líneas agregadas:**
- Líneas 491-494: Inicialización automática para Operador
- Líneas 497-613: Sistema completo de notificaciones

### Migración de Base de Datos

#### 5. `migrations/versions/add_in_process_since_field.py`
**Cambios:**
- Nueva migración para agregar el campo `in_process_since` a la tabla `operations`

#### 6. `apply_in_process_since_migration.py`
**Cambios:**
- Script Python para aplicar la migración manualmente
- Detecta automáticamente el tipo de base de datos (SQLite o PostgreSQL)
- Verifica si el campo ya existe antes de agregarlo

## Instrucciones de Instalación

### Paso 1: Aplicar Migración de Base de Datos

Ejecuta el script de migración:

```bash
cd C:\Users\ACER\Desktop\qoricash-trading-v2
python apply_in_process_since_migration.py
```

O usando Flask-Migrate:

```bash
set FLASK_APP=run.py
flask db upgrade
```

### Paso 2: Verificar la Migración

Verifica que el campo se haya agregado correctamente:

```python
python -c "from app import create_app; from app.extensions import db; app = create_app(); app.app_context().push(); inspector = db.inspect(db.engine); print('in_process_since' in [col['name'] for col in inspector.get_columns('operations')])"
```

Debería mostrar: `True`

### Paso 3: Reiniciar el Servidor

Reinicia el servidor Flask para que los cambios tomen efecto:

```bash
# Si usas run.py directamente
python run.py

# Si usas flask run
set FLASK_APP=run.py
flask run

# Si usas gunicorn (producción)
gunicorn -c gunicorn_config.py run:app
```

### Paso 4: Probar el Sistema

1. Inicia sesión con un usuario con rol **Operador**
2. Como Trader o Master, crea una operación y envíala a "En proceso"
3. El Operador debería recibir una notificación después de 10 minutos
4. Las notificaciones continuarán cada 5 minutos hasta que la operación sea atendida

## Lógica de Temporización

### Primera Notificación (10 minutos)
```
Operación enviada a "En proceso" → in_process_since = now()
Después de 10 minutos exactos → Modal aparece al Operador
```

### Notificaciones Recurrentes (cada 5 minutos)
```
10 minutos → Primera alerta
15 minutos → Segunda alerta
20 minutos → Tercera alerta
25 minutos → Cuarta alerta
... y así sucesivamente cada 5 minutos
```

### Cálculo Implementado
```javascript
const timeInProcess = operation.time_in_process_minutes;

// Lógica de alerta
const shouldAlert = (timeInProcess === 10) ||
                   (timeInProcess > 10 && (timeInProcess - 10) % 5 === 0);
```

## Casos de Uso

### Caso 1: Operación Nueva
1. Trader crea operación (Estado: "Pendiente")
2. Trader envía a proceso (Estado: "En proceso", `in_process_since` = ahora)
3. Después de 10 minutos: Modal aparece al Operador
4. Operador cierra modal con "Entendido"
5. 5 minutos después: Modal aparece nuevamente
6. Operador hace clic en "Ver Operaciones" y completa la operación
7. Las notificaciones se detienen

### Caso 2: Operación Devuelta
1. Operación está en "En proceso" por 12 minutos
2. Operador recibe alerta (primera a los 10 min)
3. Operador devuelve operación a "Pendiente" (para correcciones)
4. `in_process_since` se establece en `NULL`
5. Trader corrige y vuelve a enviar a proceso
6. `in_process_since` se establece en ahora (nuevo ciclo de 10 minutos)

### Caso 3: Múltiples Operaciones Pendientes
1. Hay 3 operaciones en proceso:
   - Op1: 12 minutos (alertada a los 10, próxima en 3 min)
   - Op2: 22 minutos (alertada a los 10, 15, 20, próxima en 3 min)
   - Op3: 8 minutos (aún no se alerta)
2. El modal mostrará Op1 y Op2 juntas cuando lleguen a 15 y 25 minutos respectivamente
3. Op3 se mostrará por primera vez a los 10 minutos

## Restricciones y Consideraciones

### Seguridad
- El endpoint `/api/check_pending_operations` está protegido con `@require_role('Operador')`
- Solo usuarios autenticados con rol "Operador" pueden acceder
- El decorador `@login_required` verifica la autenticación

### Rendimiento
- La verificación ocurre cada 1 minuto (60000 ms)
- Solo se consultan operaciones en estado "En proceso" con `in_process_since` no nulo
- La consulta es eficiente usando filtros indexados

### Experiencia de Usuario
- El modal es bloqueante para asegurar que el operador lo vea
- El sonido de notificación llama la atención del operador
- Los botones son claros: "Ver Operaciones" (acción inmediata) o "Entendido" (posponer)
- El modal funciona en todas las páginas del sistema, no solo en Operaciones

### Compatibilidad
- Funciona con Bootstrap 5.x
- Requiere jQuery 3.x
- Compatible con navegadores modernos (Chrome, Firefox, Edge, Safari)

## Troubleshooting

### Problema: No aparecen las notificaciones

**Verificar:**
1. ¿El usuario tiene rol "Operador"?
   ```javascript
   console.log(window.currentUserRole); // Debe ser 'Operador'
   ```

2. ¿Hay operaciones en proceso por más de 10 minutos?
   ```bash
   # Consulta SQL para verificar
   SELECT operation_id, status, in_process_since,
          ROUND((JULIANDAY('now') - JULIANDAY(in_process_since)) * 24 * 60) as minutes
   FROM operations
   WHERE status = 'En proceso' AND in_process_since IS NOT NULL;
   ```

3. ¿El campo `in_process_since` existe en la base de datos?
   ```python
   python apply_in_process_since_migration.py
   ```

4. ¿JavaScript se está cargando correctamente?
   ```javascript
   // En la consola del navegador
   console.log(typeof initPendingOperationsMonitor); // Debe ser 'function'
   ```

### Problema: El modal no es bloqueante

**Verificar:**
- El modal tiene los atributos correctos:
  ```javascript
  const alertModal = new bootstrap.Modal(document.getElementById('pendingOperationsAlertModal'), {
      backdrop: 'static',
      keyboard: false
  });
  ```

### Problema: Las notificaciones se muestran a roles incorrectos

**Verificar:**
- La condición en base.html:
  ```html
  {% if current_user.role == 'Operador' %}
  ```

- La inicialización en common.js:
  ```javascript
  if (window.currentUserRole === 'Operador') {
      initPendingOperationsMonitor();
  }
  ```

## Pruebas Recomendadas

### Prueba 1: Verificación de Tiempo
1. Crear una operación y enviarla a proceso
2. Esperar 10 minutos
3. Verificar que aparece el modal
4. Esperar 5 minutos más
5. Verificar que aparece nuevamente

### Prueba 2: Múltiples Operaciones
1. Crear 3 operaciones y enviarlas a proceso con 2 minutos de diferencia
2. Después de 10 minutos, verificar que se muestra la primera
3. Después de 12 minutos, verificar que se muestran ambas
4. Después de 14 minutos, verificar que se muestran las tres

### Prueba 3: Completar Operación
1. Crear operación y enviarla a proceso
2. Esperar 10 minutos (aparece alerta)
3. Completar la operación
4. Esperar 5 minutos más
5. Verificar que NO aparece nueva alerta

### Prueba 4: Devolver a Pendiente
1. Crear operación y enviarla a proceso
2. Esperar 12 minutos (aparece alerta)
3. Devolver a pendiente
4. Reenviar a proceso
5. Esperar 10 minutos (aparece nueva alerta desde cero)

## Mantenimiento Futuro

### Ajustar Tiempos de Notificación

Para cambiar los tiempos de notificación, edita el archivo `app/static/js/common.js`:

```javascript
// Cambiar intervalo de verificación (actualmente 1 minuto)
pendingOperationsCheckInterval = setInterval(function() {
    checkPendingOperations();
}, 60000); // Cambiar 60000 a otro valor en milisegundos

// Cambiar tiempos de alerta (actualmente 10 min inicial, 5 min recurrente)
const shouldAlert = (timeInProcess === 10) ||  // Cambiar 10 a otro valor
                   (timeInProcess > 10 && (timeInProcess - 10) % 5 === 0); // Cambiar 5 a otro valor
```

### Agregar Notificaciones a Otros Roles

Si se desea que otros roles también reciban notificaciones:

1. En `app/routes/operations.py`, cambiar el decorador:
   ```python
   @require_role('Operador', 'Master')  # Agregar roles adicionales
   ```

2. En `app/templates/base.html`, cambiar la condición:
   ```html
   {% if current_user.role in ['Operador', 'Master'] %}
   ```

3. En `app/static/js/common.js`, cambiar la inicialización:
   ```javascript
   if (['Operador', 'Master'].includes(window.currentUserRole)) {
       initPendingOperationsMonitor();
   }
   ```

## Resumen de Implementación

✅ **Backend:**
- Campo `in_process_since` agregado al modelo Operation
- Lógica de tiempo automática en transiciones de estado
- Endpoint API para verificar operaciones pendientes

✅ **Frontend:**
- Modal bloqueante para notificaciones
- Verificación automática cada 1 minuto
- Funciona en todas las páginas del sistema

✅ **Seguridad:**
- Restricción por rol (solo Operador)
- Autenticación requerida
- Validación en backend y frontend

✅ **Base de Datos:**
- Migración creada
- Script de aplicación disponible
- Compatible con SQLite y PostgreSQL

---

**Fecha de Implementación:** 23 de Noviembre, 2025
**Versión:** 1.0
**Desarrollado por:** Claude Code
