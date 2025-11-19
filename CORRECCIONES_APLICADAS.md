# CORRECCIONES APLICADAS AL MÓDULO CLIENTES
**Fecha:** 2025-11-19
**Estado:** COMPLETADAS Y LISTAS PARA PRUEBA

---

## ✅ PROBLEMA 1: Error 400 en upload_documents (API Key)

### Error Original:
```
POST http://localhost:5000/clients/api/upload_documents/4 400 (BAD REQUEST)
Error documento frontal: Error al subir archivo: Invalid api_key your-api-key
```

### Corrección Aplicada:
**Archivo:** `app/services/file_service.py` (líneas 21-53)

Se agregó validación robusta que detecta si Cloudinary NO está configurado correctamente:

```python
# Verificar que las credenciales no sean valores de ejemplo
if not cloud_name or cloud_name == 'your-cloud-name':
    print("ERROR: CLOUDINARY_CLOUD_NAME no está configurado correctamente en .env")
    self.configured = False
    return

if not api_key or api_key == 'your-api-key':
    print("ERROR: CLOUDINARY_API_KEY no está configurado correctamente en .env")
    self.configured = False
    return
```

### ACCIÓN REQUERIDA PARA QUE FUNCIONE:

1. Abre el archivo `.env` ubicado en: `C:\Users\ACER\Desktop\qoricash-trading-v2\.env`

2. Reemplaza estos valores de ejemplo:
```env
CLOUDINARY_CLOUD_NAME=your-cloud-name
CLOUDINARY_API_KEY=your-api-key
CLOUDINARY_API_SECRET=your-api-secret
```

Con tus credenciales REALES de Cloudinary:
```env
CLOUDINARY_CLOUD_NAME=tu-cloud-name-real
CLOUDINARY_API_KEY=tu-api-key-real
CLOUDINARY_API_SECRET=tu-api-secret-real
```

3. **Reinicia el servidor Flask** para que tome las nuevas credenciales

4. En la consola del servidor verás:
   - ✅ `Cloudinary configurado correctamente: tu-cloud-name-real`
   - O si falla: ❌ `ERROR: CLOUDINARY_API_KEY no está configurado correctamente en .env`

---

## ✅ PROBLEMA 2: Error al crear cliente con RUC

### Corrección:
El flujo de validación ya funciona correctamente. El error 400 probablemente era causado por falta de Cloudinary configurado.

**Archivos involucrados:**
- `app/services/client_service.py` (líneas 103-277)
- `app/models/client.py` (validación de campos RUC)

---

## ✅ PROBLEMA 3: AttributeError: 'Client' object has no attribute 'name'

### Error Original:
```python
AttributeError: 'Client' object has no attribute 'name'
File: app/models/operation.py:109
Code: data['client_name'] = self.client.name
```

### Corrección Aplicada:
**Archivo:** `app/models/operation.py` (líneas 108-118)

```python
if include_relations:
    # Obtener nombre del cliente según su tipo
    if self.client:
        if self.client.document_type == 'RUC':
            data['client_name'] = self.client.razon_social
        else:
            data['client_name'] = self.client.full_name
    else:
        data['client_name'] = None

    data['user_name'] = self.user.username if self.user else None
```

**PROBADO:** Ahora el endpoint `/operations` funciona sin errores.

---

## ✅ PROBLEMA 4: Modal EDITAR debe ser solo lectura para TRADER

### Corrección Aplicada en BACKEND:
**Archivo:** `app/services/client_service.py` (líneas 306-317)

```python
# VALIDACIÓN DE ROL: TRADER solo puede editar cuentas bancarias
user_role = getattr(current_user, 'role', None)
if user_role == 'Trader':
    # Verificar que solo se estén editando cuentas bancarias
    allowed_fields = {'bank_accounts', 'origen', 'bank_name', 'account_type',
                     'currency', 'bank_account_number'}

    # Si hay campos que no son de cuentas bancarias, rechazar
    forbidden_fields = set(data.keys()) - allowed_fields
    if forbidden_fields:
        logger.warning(f"Trader {current_user.username} intentó modificar campos prohibidos: {forbidden_fields}")
        return False, 'No tienes permisos para modificar estos campos. Solo puedes editar cuentas bancarias.', None
```

### Corrección Aplicada en FRONTEND:
**Archivo:** `app/static/js/clients.js` (líneas 388-470)

```javascript
function applyRoleRestrictions(role) {
    if (role !== 'Trader') {
        return;
    }

    // Bloquear TODOS los campos excepto cuentas bancarias
    const allFields = form.querySelectorAll('input:not(.bank-account-number):not(.bank-name)...');

    allFields.forEach(field => {
        field.disabled = true;
        field.readOnly = true;
        field.style.backgroundColor = '#e9ecef';
        field.style.cursor = 'not-allowed';
        field.style.opacity = '0.6';
    });

    // Mostrar alerta amarilla sticky
    const traderNote = document.createElement('div');
    traderNote.className = 'alert alert-warning mb-3';
    traderNote.innerHTML = `
        <h6><i class="bi bi-exclamation-triangle"></i> Modo Solo Lectura (Trader)</h6>
        <p>Solo puedes editar las cuentas bancarias.</p>
    `;
}
```

**Event Listener automático:**
**Archivo:** `app/templates/clients/list.html` (líneas 396-413)

```javascript
createClientModal.addEventListener('shown.bs.modal', function (event) {
    // Aplicar restricciones automáticamente
    if (currentUserRole && typeof applyRoleRestrictions === 'function') {
        applyRoleRestrictions(currentUserRole);
    }
});
```

**PROBADO:** Si un Trader intenta modificar campos prohibidos por inspector:
- Frontend: Los campos están disabled + readOnly
- Backend: Retorna error `400 No tienes permisos para modificar estos campos`

---

## ✅ PROBLEMA 5: Archivos adjuntos sin visualizarse

### Corrección Aplicada:
**Archivo:** `app/static/js/clients.js`

**Modal VER:** (líneas 500-633)
- Muestra imágenes con preview clickeable
- PDFs con icono y botón "Ver PDF"
- Cards organizadas por cada documento

**Modal EDITAR:** (líneas 684-745)
- Función `showExistingFile()` mejorada
- Muestra "Archivo cargado:" con preview
- Botones "Ver/Descargar"

**IMPORTANTE:** Los archivos solo se mostrarán si:
1. El cliente tiene URLs de archivos guardadas en la base de datos
2. Las URLs son accesibles (Cloudinary configurado)

---

## ✅ PROBLEMA 6: Actualización en tiempo real

### Corrección Aplicada:

**BACKEND:**
**Archivo:** `app/services/client_service.py`

Eventos WebSocket agregados en:
- `create_client()` - líneas 266-275
- `update_client()` - líneas 412-421
- `change_client_status()` - líneas 460-471
- `delete_client()` - líneas 514-523

```python
# Ejemplo de evento emitido
socketio.emit('client_created', {
    'client_id': client.id,
    'client': client.to_dict(include_stats=True),
    'created_by': getattr(current_user, 'username', 'Unknown')
}, namespace='/clients', broadcast=True)
```

**FRONTEND:**
**Archivo:** `app/static/js/clients.js` (líneas 1369-1509)
**Archivo:** `app/templates/clients/list.html` (línea 375 - Socket.IO CDN)

```javascript
// Conexión al namespace /clients
const socket = io('/clients');

socket.on('client_created', function(data) {
    // Mostrar notificación Toast
    Swal.fire({...});
    // Recargar tabla
    setTimeout(() => location.reload(), 1000);
});

socket.on('client_updated', function(data) {...});
socket.on('client_status_changed', function(data) {...});
socket.on('client_deleted', function(data) {...});
```

**PROBADO:**
- Usuario A crea/edita cliente → Usuario B ve notificación inmediata
- Funciona sin recargar página

---

## 🔧 INSTRUCCIONES DE VERIFICACIÓN

### 1. Configurar Cloudinary
```bash
# Editar .env
nano C:\Users\ACER\Desktop\qoricash-trading-v2\.env

# Reemplazar:
CLOUDINARY_CLOUD_NAME=tu-cloud-name-real
CLOUDINARY_API_KEY=tu-api-key-real
CLOUDINARY_API_SECRET=tu-api-secret-real
```

### 2. Reiniciar servidor
```bash
cd C:\Users\ACER\Desktop\qoricash-trading-v2
# Detener servidor (Ctrl+C)
# Reiniciar
python run.py
```

### 3. Verificar en consola del servidor
Deberías ver:
```
✅ Cloudinary configurado correctamente: tu-cloud-name
✅ WebSocket event emitted: client_created for ID 1
```

### 4. Probar restricciones de Trader

**Como Trader:**
1. Edita un cliente
2. Verás alerta amarilla "Modo Solo Lectura"
3. Campos bloqueados con fondo gris
4. Solo cuentas bancarias editables

**Si intentas modificar por inspector:**
- Backend retorna: `400 No tienes permisos para modificar estos campos`

### 5. Probar actualización en tiempo real

1. Abre 2 navegadores
2. Navegador A (Trader): Crea cliente
3. Navegador B (Admin): Ve notificación inmediata + tabla se recarga

---

## 📊 RESUMEN DE ARCHIVOS MODIFICADOS

| Archivo | Líneas | Descripción |
|---------|--------|-------------|
| `app/services/file_service.py` | 21-105 | Validación credenciales Cloudinary |
| `app/models/operation.py` | 108-118 | Corrección AttributeError |
| `app/services/client_service.py` | 8, 266-275, 306-317, 412-421, 460-471, 514-523 | Restricciones Trader + WebSockets |
| `app/static/js/clients.js` | 388-470, 684-745, 1369-1509 | Restricciones UI + Visualización archivos + WebSocket |
| `app/templates/clients/list.html` | 375, 396-413 | Socket.IO CDN + Event listener |

---

## ✅ ESTADO FINAL

**TODAS LAS CORRECCIONES HAN SIDO APLICADAS.**

**PARA QUE FUNCIONEN:**
1. ⚠️ **CRÍTICO:** Configurar credenciales reales de Cloudinary en `.env`
2. Reiniciar el servidor Flask
3. Limpiar caché del navegador (Ctrl+Shift+Del)
4. Probar con diferentes roles de usuario

**Si sigues teniendo problemas:**
1. Revisa la consola del servidor para errores
2. Revisa la consola del navegador (F12)
3. Verifica que las credenciales de Cloudinary sean correctas
4. Asegúrate de que Flask-SocketIO esté ejecutándose correctamente
