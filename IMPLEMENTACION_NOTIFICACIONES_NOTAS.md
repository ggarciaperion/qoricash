# Implementación de Notificaciones de Notas para Operador

## Descripción
Se implementó un sistema de notificaciones estilo WhatsApp para indicar al rol **Operador** cuando una operación tiene notas sin leer. La notificación aparece como un badge rojo con el número "1" sobre el botón "Ver" o "Procesar", y desaparece automáticamente cuando el operador abre el modal.

## Cambios Implementados

### 1. Base de Datos
**Archivo modificado**: `operations` table
- Se agregó la columna `notes_read_by_json` (tipo TEXT, default `'[]'`)
- Almacena un array JSON con los IDs de usuarios que han leído las notas
- Todas las operaciones existentes fueron inicializadas con array vacío

### 2. Modelo de Datos
**Archivo**: `app/models/operation.py`

#### Campo agregado:
```python
notes_read_by_json = db.Column(db.Text, default='[]')
```

#### Propiedades agregadas:
```python
@property
def notes_read_by(self):
    """Obtener lista de IDs de usuarios que leyeron las notas"""
    try:
        return json.loads(self.notes_read_by_json or '[]')
    except:
        return []

@notes_read_by.setter
def notes_read_by(self, value):
    """Guardar lista de IDs de usuarios que leyeron las notas"""
    self.notes_read_by_json = json.dumps(value or [])
```

#### Métodos agregados:
```python
def mark_notes_as_read(self, user_id):
    """Marcar las notas como leídas por un usuario"""
    read_by = self.notes_read_by
    if user_id not in read_by:
        read_by.append(user_id)
        self.notes_read_by = read_by

def has_user_read_notes(self, user_id):
    """Verificar si un usuario ya leyó las notas"""
    return user_id in self.notes_read_by

def has_unread_notes(self, user_id):
    """Verificar si hay notas sin leer para un usuario"""
    return bool(self.notes and self.notes.strip()) and not self.has_user_read_notes(user_id)
```

#### to_dict() actualizado:
Se agregó `'notes_read_by': self.notes_read_by` al diccionario retornado.

### 3. Backend - API Endpoint
**Archivo**: `app/routes/operations.py`

Se agregó el endpoint:
```python
@operations_bp.route('/api/mark_notes_read/<int:operation_id>', methods=['POST'])
@login_required
@require_role('Operador', 'Master')
def mark_notes_read(operation_id):
    """
    API: Marcar notas como leídas por el usuario actual
    """
    operation = Operation.query.get(operation_id)
    if not operation:
        return jsonify({'success': False, 'message': 'Operación no encontrada'}), 404

    try:
        operation.mark_notes_as_read(current_user.id)
        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'Notas marcadas como leídas',
            'notes_read_by': operation.notes_read_by
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500
```

### 4. Frontend - Template
**Archivo**: `app/templates/operations/list.html`

#### Badges en tabla HTML (renderizado del servidor):
Para el rol Operador, se agregó el badge en los botones "Ver" y "Procesar":

```html
<button class="btn btn-outline-info position-relative" onclick="viewOperation({{ op.id }})"
        title="Ver (Solo lectura)" data-operation-id="{{ op.id }}">
    <i class="bi bi-eye"></i>
    {% if op.has_unread_notes(user.id) %}
    <span class="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger notes-badge"
          data-operation-id="{{ op.id }}">
        1
        <span class="visually-hidden">nota sin leer</span>
    </span>
    {% endif %}
</button>
```

#### Badges en filas dinámicas (JavaScript):
En la función `buildOperationRow()`, para el rol Operador:

```javascript
} else if (currentUserRole === 'Operador') {
    // Verificar si hay notas sin leer
    const hasUnreadNotes = op.notes && op.notes.trim() &&
                          op.notes_read_by && !op.notes_read_by.includes(currentUserId);
    const notificationBadge = hasUnreadNotes
        ? '<span class="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger notes-badge" data-operation-id="' + op.id + '">1<span class="visually-hidden">nota sin leer</span></span>'
        : '';

    if (op.status === 'Pendiente') {
        buttons = `<button class="btn btn-outline-info btn-sm position-relative"
                          onclick="viewOperation(${op.id})" title="Ver (Solo lectura)"
                          data-operation-id="${op.id}">
                      <i class="bi bi-eye"></i>
                      ${notificationBadge}
                   </button>`;
    } else if (op.status === 'En proceso') {
        buttons = `<button class="btn btn-outline-primary btn-sm position-relative"
                          onclick="editOperation(${op.id})" title="Procesar"
                          data-operation-id="${op.id}">
                      <i class="bi bi-pencil"></i>
                      ${notificationBadge}
                   </button>`;
    }
}
```

#### Función JavaScript para marcar como leído:
```javascript
function markNotesAsRead(operationId) {
    ajaxRequest(`/operations/api/mark_notes_read/${operationId}`, 'POST', null, function(response) {
        if (response.success) {
            // Ocultar badge de notificación para esta operación
            $(`.notes-badge[data-operation-id="${operationId}"]`).fadeOut(300, function() {
                $(this).remove();
            });
        }
    }, function(xhr, status, error) {
        // Error silencioso - no mostrar alerta al usuario
        console.error('Error al marcar notas como leídas:', error);
    });
}
```

#### Integración en funciones de modal:
Ambas funciones `viewOperation()` y `editOperation()` llaman a `markNotesAsRead()`:

```javascript
function viewOperation(operationId) {
    ajaxRequest(`/operations/api/${operationId}`, 'GET', null, function(response) {
        const op = response.operation;
        let html = buildViewHTML(op, true);
        $('#operationDetails').html(html);
        $('#viewOperationModal').modal('show');

        // Si es Operador y hay notas, marcarlas como leídas
        if (currentUserRole === 'Operador' && op.notes && op.notes.trim()) {
            markNotesAsRead(operationId);
        }
    });
}

function editOperation(operationId) {
    ajaxRequest(`/operations/api/${operationId}`, 'GET', null, function(response) {
        currentOperation = response.operation;
        clientBankAccounts = currentOperation.client_bank_accounts || [];
        loadEditModal();
        $('#editOperationModal').modal('show');

        // Si es Operador y hay notas, marcarlas como leídas
        if (currentUserRole === 'Operador' && currentOperation.notes && currentOperation.notes.trim()) {
            markNotesAsRead(operationId);
        }
    });
}
```

## Flujo de Funcionamiento

1. **Trader crea una operación con notas**
   - El campo `notes` se guarda normalmente
   - El campo `notes_read_by_json` se inicializa como `[]` (array vacío)

2. **Operador ve la lista de operaciones**
   - El template verifica con `op.has_unread_notes(user.id)` si hay notas sin leer
   - Si hay notas y el ID del operador NO está en `notes_read_by`, se muestra el badge rojo

3. **Operador hace clic en "Ver" o "Procesar"**
   - Se abre el modal correspondiente
   - Automáticamente se llama a `markNotesAsRead(operationId)`
   - El endpoint POST `/api/mark_notes_read/{id}` agrega el ID del usuario al array
   - El badge desaparece con animación fadeOut

4. **Actualización en tiempo real**
   - Si la tabla se recarga vía Socket.IO, `buildOperationRow()` verifica `notes_read_by`
   - El badge ya no aparece porque el ID del operador está en el array

## Ventajas de la Implementación

✅ **No intrusivo**: Solo visible para el rol Operador
✅ **Estilo WhatsApp**: Badge rojo con número en la esquina superior derecha
✅ **Automático**: Se marca como leído al abrir el modal, sin acción adicional
✅ **Persistente**: El estado se guarda en la base de datos
✅ **Multiusuario**: Cada operador tiene su propio estado de lectura
✅ **Actualización dinámica**: Compatible con el sistema de actualizaciones en tiempo real
✅ **Sin errores visuales**: Usa animación fadeOut suave para ocultar el badge

## Archivos Modificados

1. `app/models/operation.py` - Modelo y métodos de negocio
2. `app/routes/operations.py` - Endpoint API
3. `app/templates/operations/list.html` - Vista y JavaScript
4. Base de datos: Tabla `operations` - Nueva columna `notes_read_by_json`

## Cómo Probar

1. Con rol **Trader**:
   - Crear una operación nueva
   - En el campo "Notas", escribir cualquier texto (ej: "Revisar cuenta de origen")
   - Guardar la operación

2. Con rol **Operador**:
   - Ir al menú "Operaciones"
   - Verificar que aparece un badge rojo "1" en el botón "Ver" de esa operación
   - Hacer clic en "Ver"
   - Cerrar el modal
   - El badge debe haber desaparecido

3. Con otro **Operador** diferente:
   - Ver la misma operación
   - El badge debe aparecer nuevamente (es por usuario)

## Notas Técnicas

- El badge solo aparece si:
  1. El rol es Operador
  2. La operación tiene notas (`notes IS NOT NULL AND notes != ''`)
  3. El ID del usuario actual NO está en `notes_read_by_json`

- El badge se oculta automáticamente al:
  - Abrir el modal "Ver" (estado Pendiente)
  - Abrir el modal "Procesar" (estado En proceso)

- La columna `notes_read_by_json` se agregó directamente a la base de datos sin migración formal de Alembic debido a problemas con la cadena de revisiones.
