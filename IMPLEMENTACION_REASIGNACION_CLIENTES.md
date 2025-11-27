# Implementación de Reasignación de Clientes

## Resumen

Se ha implementado completamente la funcionalidad de reasignación de clientes para el rol **Master/Admin**, permitiendo reasignar la cartera de clientes de un trader a otro, tanto de forma individual como masiva.

## Características Implementadas

### 1. Reasignación Individual
- Botón de reasignación en cada fila de la tabla de clientes (solo visible para Master)
- Modal intuitivo que muestra:
  - Nombre del cliente
  - Trader actual
  - Lista de traders activos disponibles con su cantidad de clientes
- Validaciones completas antes de reasignar

### 2. Reasignación Masiva (2 opciones)

#### Opción 1: Reasignar Clientes Seleccionados
- Checkboxes en cada fila para seleccionar clientes individualmente
- Checkbox "Seleccionar todos" en el encabezado
- Contador dinámico de clientes seleccionados
- Permite reasignar múltiples clientes seleccionados a un trader

#### Opción 2: Reasignar Todos los Clientes de un Trader
- Seleccionar trader origen (muestra cantidad de clientes que tiene)
- Seleccionar trader destino
- Reasigna automáticamente todos los clientes del trader origen al destino
- Ideal para cuando un trader renuncia o cambia de posición

## Archivos Modificados

### Backend

#### 1. `app/services/client_service.py`
**Métodos agregados:**
- `get_clients_by_trader(trader_id)`: Obtiene todos los clientes de un trader específico
- `reassign_client(current_user, client_id, new_trader_id)`: Reasigna un cliente individual
- `reassign_clients_bulk(current_user, client_ids, new_trader_id)`: Reasigna múltiples clientes

**Características:**
- Validación de permisos (solo Master puede reasignar)
- Validación de que el nuevo trader existe y está activo
- Registro de auditoría completo
- Emisión de eventos WebSocket para actualización en tiempo real

#### 2. `app/routes/clients.py`
**Rutas agregadas:**
- `GET /clients/api/traders/active`: Obtiene lista de traders activos
- `POST /clients/api/reassign/<client_id>`: Reasigna un cliente individual
- `POST /clients/api/reassign/bulk`: Reasigna múltiples clientes
- `GET /clients/api/trader/<trader_id>/clients`: Obtiene clientes de un trader

**Características:**
- Decorador `@require_role('Master')` en todas las rutas de reasignación
- Validaciones de entrada completas
- Manejo de errores robusto
- Integración con NotificationService

#### 3. `app/services/notification_service.py`
**Métodos agregados:**
- `notify_client_reassignment(client, reassigned_by_user, new_trader_id)`: Notifica reasignación individual
- `notify_bulk_client_reassignment(new_trader, reassigned_by_user, client_count)`: Notifica reasignación masiva
- `notify_new_client(client, created_by_user)`: Notifica nuevo cliente (ya existía, mejorado)

**Características:**
- Notificaciones en tiempo real vía WebSocket
- Notifica al nuevo trader que recibe clientes
- Notifica al trader anterior que pierde clientes
- Salas específicas por usuario (room=f'user_{user_id}')

### Frontend

#### 4. `app/templates/clients/list.html`
**Elementos agregados:**
- Botón "Reasignar Clientes" en el header (solo Master)
- Columna de checkboxes para selección múltiple (solo Master)
- Checkbox "Seleccionar todos" en el encabezado
- Botón de reasignación individual en acciones de cada cliente
- Modal `#reassignClientModal`: Reasignación individual
- Modal `#bulkReassignModal`: Reasignación masiva con 2 opciones

**Diseño:**
- UI intuitiva y responsive
- Información clara del estado actual
- Confirmaciones antes de acciones críticas

#### 5. `app/static/js/clients.js`
**Funciones agregadas:**
- `loadActiveTraders()`: Carga traders activos desde el servidor
- `showReassignModal(clientId)`: Muestra modal de reasignación individual
- `confirmReassignClient()`: Ejecuta reasignación individual
- `showBulkReassignModal()`: Muestra modal de reasignación masiva
- `updateBulkSelectedCount()`: Actualiza contador de seleccionados
- `confirmBulkReassignSelected()`: Reasigna clientes seleccionados
- `confirmBulkReassignFromTrader()`: Reasigna todos los clientes de un trader

**Características:**
- Manejo asíncrono con async/await
- Validaciones en cliente antes de enviar al servidor
- Actualización automática de la tabla tras reasignación exitosa
- Alertas informativas con SweetAlert o similar
- Event listeners para checkboxes dinámicos

## Flujo de Trabajo

### Reasignación Individual

1. Master hace clic en el botón de reasignación (icono flechas) de un cliente
2. Se abre modal mostrando:
   - Nombre del cliente
   - Trader actual
   - Lista de traders activos
3. Master selecciona el nuevo trader
4. Sistema valida:
   - Que el trader existe y está activo
   - Que Master tiene permisos
5. Se actualiza el campo `created_by` del cliente
6. Se registra en audit_log
7. Se envían notificaciones WebSocket:
   - Al nuevo trader: "Se te ha asignado el cliente X"
   - Al trader anterior: "El cliente X ha sido reasignado"
8. Se recarga la tabla automáticamente

### Reasignación Masiva - Opción 1 (Seleccionados)

1. Master selecciona clientes con checkboxes
2. Master hace clic en "Reasignar Clientes"
3. En el modal, sección "Opción 1":
   - Se muestra contador de clientes seleccionados
   - Master selecciona trader destino
4. Master hace clic en "Reasignar Seleccionados"
5. Sistema itera sobre cada cliente seleccionado
6. Para cada cliente se ejecuta el flujo de reasignación individual
7. Se muestra resultado consolidado (éxitos y fallos)
8. Se notifica al nuevo trader con cantidad total

### Reasignación Masiva - Opción 2 (Todos de un trader)

1. Master hace clic en "Reasignar Clientes"
2. En el modal, sección "Opción 2":
   - Master selecciona trader origen
   - Sistema muestra cantidad de clientes que tiene
   - Master selecciona trader destino
3. Master hace clic en "Reasignar Todos"
4. Sistema:
   - Obtiene todos los clientes del trader origen
   - Confirma con el usuario la cantidad
   - Ejecuta reasignación masiva
5. Se notifica resultado consolidado

## Validaciones Implementadas

### Backend
- ✅ Solo Master puede reasignar clientes
- ✅ El cliente debe existir
- ✅ El nuevo trader debe existir
- ✅ El nuevo trader debe tener rol "Trader"
- ✅ El nuevo trader debe estar activo
- ✅ Lista de clientes no puede estar vacía (bulk)
- ✅ Trader origen y destino no pueden ser el mismo

### Frontend
- ✅ Debe seleccionar al menos un cliente (seleccionados)
- ✅ Debe seleccionar un trader destino
- ✅ Debe seleccionar trader origen y destino (opción 2)
- ✅ Confirmación antes de reasignar
- ✅ Validación de respuesta del servidor

## Seguridad

- **Control de acceso**: Todas las rutas están protegidas con `@require_role('Master')`
- **Validación de permisos**: Se valida en backend que solo Master ejecute reasignaciones
- **Auditoría completa**: Cada reasignación se registra en `audit_log` con:
  - Usuario que ejecutó la acción
  - Acción: 'REASSIGN_CLIENT'
  - Cliente afectado
  - Detalles: trader origen y destino
- **Transacciones**: Uso de db.session con rollback en caso de error

## Eventos WebSocket

### Reasignación Individual
- **Evento**: `client_reassigned`
- **Datos**:
  ```javascript
  {
    client_id: 123,
    client: {...},
    old_trader_id: 5,
    new_trader_id: 7,
    reassigned_by: 'admin'
  }
  ```

### Notificación al Nuevo Trader
- **Evento**: `cliente_asignado`
- **Room**: `user_{trader_id}`
- **Datos**:
  ```javascript
  {
    client_id: 123,
    client_name: 'JUAN PÉREZ',
    client_dni: '12345678',
    old_trader_name: 'trader1',
    new_trader_name: 'trader2',
    reassigned_by: 'admin',
    message: 'Se te ha asignado el cliente JUAN PÉREZ'
  }
  ```

### Notificación al Trader Anterior
- **Evento**: `cliente_reasignado_removido`
- **Room**: `user_{trader_id}`
- **Datos**:
  ```javascript
  {
    client_id: 123,
    client_name: 'JUAN PÉREZ',
    message: 'El cliente JUAN PÉREZ ha sido reasignado a trader2'
  }
  ```

### Reasignación Masiva
- **Evento**: `clientes_asignados_masivo`
- **Room**: `user_{trader_id}`
- **Datos**:
  ```javascript
  {
    client_count: 10,
    new_trader_name: 'trader2',
    reassigned_by: 'admin',
    message: 'Se te han asignado 10 cliente(s) nuevos'
  }
  ```

## Ejemplos de Uso

### Caso 1: Trader renuncia
**Escenario**: El trader "juan_trader" (ID=5) renuncia y tiene 10 clientes

**Solución**:
1. Master accede a Gestión de Clientes
2. Hace clic en "Reasignar Clientes"
3. En "Opción 2":
   - Trader Origen: juan_trader (10 clientes)
   - Trader Destino: maria_trader
4. Confirma la reasignación
5. Los 10 clientes se reasignan a maria_trader
6. maria_trader recibe notificación en tiempo real

### Caso 2: Balancear cartera
**Escenario**: Un trader tiene demasiados clientes, redistribuir 5 a otro trader

**Solución**:
1. Master accede a Gestión de Clientes
2. Selecciona 5 clientes específicos con checkboxes
3. Hace clic en "Reasignar Clientes"
4. En "Opción 1":
   - Muestra "5 cliente(s) seleccionado(s)"
   - Selecciona trader destino
5. Confirma reasignación
6. Solo esos 5 clientes se reasignan

### Caso 3: Corregir asignación individual
**Escenario**: Un cliente fue asignado al trader incorrecto

**Solución**:
1. Master busca el cliente en la tabla
2. Hace clic en botón de reasignación (flechas)
3. Selecciona el trader correcto
4. Confirma
5. Cliente se reasigna inmediatamente

## Registro de Auditoría

Todas las reasignaciones quedan registradas en la tabla `audit_logs`:

```sql
INSERT INTO audit_logs (
    user_id,
    action,
    entity,
    entity_id,
    details,
    created_at
) VALUES (
    1, -- ID del Master
    'REASSIGN_CLIENT',
    'Client',
    123, -- ID del cliente
    'Cliente JUAN PÉREZ reasignado de trader1 a trader2',
    NOW()
);
```

## Notas Técnicas

### Relación Cliente-Trader
Los clientes están vinculados al trader mediante el campo `created_by` en la tabla `clients`:
- `created_by`: Foreign Key a `users.id`
- `creator`: Relationship con User

Al reasignar, se actualiza `created_by` al ID del nuevo trader.

### Compatibilidad
La implementación es compatible con:
- Sistema de operaciones existente
- Filtros por trader en dashboard
- Reportes y estadísticas por trader
- Sistema de permisos actual

### Rendimiento
- Carga de traders: Query optimizado con filtro por rol y estado
- Reasignación masiva: Procesa clientes secuencialmente con manejo de errores individual
- WebSocket: Eventos dirigidos a salas específicas (no broadcast innecesario)

## Testing Recomendado

1. **Permisos**: Verificar que solo Master puede acceder
2. **Validaciones**: Intentar reasignar con datos inválidos
3. **Trader inactivo**: Intentar asignar a trader desactivado
4. **Cliente inexistente**: Intentar reasignar cliente que no existe
5. **Reasignación masiva**: Probar con diferentes cantidades
6. **WebSocket**: Verificar que las notificaciones llegan correctamente
7. **Audit Log**: Verificar que se registran todas las acciones
8. **UI Responsive**: Probar en diferentes resoluciones

## Próximas Mejoras (Opcional)

- [ ] Historial de reasignaciones por cliente
- [ ] Filtro para ver clientes por trader en la tabla
- [ ] Confirmación con contraseña para reasignaciones masivas
- [ ] Exportar reporte de reasignaciones
- [ ] Dashboard con estadísticas de reasignaciones
- [ ] Notificaciones por email además de WebSocket
- [ ] Reasignación automática basada en carga de trabajo

## Soporte

Para cualquier duda sobre la implementación, revisar:
- Código fuente con comentarios detallados
- Logs del servidor para debugging
- Consola del navegador para errores de JavaScript
- Tabla audit_logs para rastrear acciones

---

**Fecha de implementación**: 2025-01-27
**Versión**: 1.0
**Estado**: ✅ Completado y funcional
