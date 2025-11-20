# 🎨 GUÍA DE CAMBIOS EN EL FRONTEND

**Fecha:** 2025-11-20
**Versión:** 2.1.0

---

## ✅ CAMBIOS IMPLEMENTADOS EN LA INTERFAZ

Se han actualizado los archivos del frontend para reflejar las nuevas funcionalidades y permisos del sistema.

---

## 📁 ARCHIVOS MODIFICADOS

### 1. **`app/templates/clients/list.html`**

#### **Cambio 1: Nueva columna "Usuario" (líneas 97-127)**
**VISIBLE PARA:** Solo Master y Operador

```html
{% if current_user.role in ['Master', 'Operador'] %}
<th>Usuario</th>
{% endif %}
```

**En el cuerpo de la tabla:**
```html
{% if current_user.role in ['Master', 'Operador'] %}
<td>
    {% if c.creator %}
        <span class="badge bg-secondary" title="{{ c.creator.role }}">
            <i class="bi bi-person"></i> {{ c.creator.username }}
        </span>
    {% else %}
        <span class="text-muted">N/A</span>
    {% endif %}
</td>
{% endif %}
```

**RESULTADO:**
- Master y Operador ven una columna adicional con el username del trader que registró al cliente
- El badge muestra un ícono de persona y el nombre de usuario
- Al pasar el mouse sobre el badge, se muestra el rol del usuario (tooltip)

---

#### **Cambio 2: Nueva columna "Fecha Registro" (líneas 100, 128-135)**
**VISIBLE PARA:** Todos los roles

```html
<th>Fecha Registro</th>

<!-- En el cuerpo -->
<td>
    {% if c.created_at %}
        <small>{{ c.created_at.strftime('%d/%m/%Y') }}</small><br>
        <small class="text-muted">{{ c.created_at.strftime('%H:%M') }}</small>
    {% else %}
        <span class="text-muted">-</span>
    {% endif %}
</td>
```

**RESULTADO:**
- Todos los usuarios ven la fecha de registro en formato DD/MM/YYYY
- Debajo aparece la hora en formato HH:MM en texto gris claro
- Si no hay fecha, muestra un guión "-"

---

#### **Cambio 3: Mensaje actualizado de validación de cuentas bancarias (líneas 365-391)**

**ANTES:**
```html
<div class="required-accounts-info">
    <i class="bi bi-info-circle"></i> <strong>Importante:</strong>
    Debes registrar al menos dos cuentas bancarias (una en Soles y otra en Dólares). Máximo 6 cuentas.
</div>

<div id="duplicateAccountsMessage" class="alert alert-danger" style="display: none;">
    <i class="bi bi-exclamation-triangle"></i>
    Tienes cuentas duplicadas (mismo banco y misma moneda). Por favor, elimina los duplicados.
</div>
```

**AHORA:**
```html
<div class="required-accounts-info">
    <i class="bi bi-info-circle"></i> <strong>Importante:</strong>
    Debes registrar al menos dos cuentas bancarias (una en Soles y otra en Dólares). Máximo 6 cuentas.
    <br><small class="text-muted">
        ✅ Puedes tener múltiples cuentas del mismo banco en la misma moneda,
        siempre que los números de cuenta sean diferentes.
    </small>
</div>

<div id="duplicateAccountsMessage" class="alert alert-danger" style="display: none;">
    <i class="bi bi-exclamation-triangle"></i>
    Tienes una cuenta duplicada exacta (mismo banco, tipo, número y moneda).
    Por favor, verifica los datos.
</div>
```

**RESULTADO:**
- El mensaje informativo ahora aclara que SÍ se pueden registrar múltiples cuentas del mismo banco
- El mensaje de error se actualiza para especificar "duplicado exacto"

---

### 2. **`app/static/js/clients.js`**

#### **Cambio 1: Función `validateDuplicateAccounts()` actualizada (líneas 241-291)**

**ANTES:**
```javascript
function validateDuplicateAccounts() {
    // Validaba solo banco + moneda
    if (accounts[i].bank === accounts[j].bank &&
        accounts[i].currency === accounts[j].currency) {
        // Rechazaba duplicado
    }
}
```

**AHORA:**
```javascript
function validateDuplicateAccounts() {
    // Valida banco + tipo + número + moneda (duplicado EXACTO)
    if (accounts[i].bank === accounts[j].bank &&
        accounts[i].accountType === accounts[j].accountType &&
        accounts[i].accountNumber === accounts[j].accountNumber &&
        accounts[i].currency === accounts[j].currency) {
        // Solo rechaza si TODA la info es idéntica
    }
}
```

**RESULTADO:**
- ✅ Permite: BCP Ahorro 123456 S/ + BCP Ahorro 789012 S/ (números diferentes)
- ✅ Permite: BCP Ahorro 123456 S/ + BCP Corriente 123456 S/ (tipo diferente)
- ❌ Rechaza: BCP Ahorro 123456 S/ + BCP Ahorro 123456 S/ (TODO idéntico)

---

#### **Cambio 2: Función `applyRoleRestrictions()` actualizada (líneas 401-465)**

**ANTES:**
```javascript
function applyRoleRestrictions(role) {
    if (role === 'Trader') {
        // Bloqueaba TODOS los campos excepto cuentas bancarias
        allFields.forEach(field => {
            if (!isBankField(field)) {
                field.disabled = true; // Bloquear
            }
        });
    }
}
```

**AHORA:**
```javascript
function applyRoleRestrictions(role) {
    if (role === 'Trader') {
        // Solo bloquea campos PROTEGIDOS
        const protectedFieldIds = [
            'documentType',  // Tipo de documento
            'dni',          // Número de documento
            'clientId'      // ID del cliente
        ];

        // Bloquear solo estos campos
        protectedFieldIds.forEach(fieldId => {
            const field = document.getElementById(fieldId);
            if (field) {
                field.disabled = true;
            }
        });
    }
}
```

**Nota informativa actualizada:**
```html
<div class="alert alert-info">
    <h6>Permisos de Edición (Trader)</h6>
    <p>
        ✅ Puedes editar: Nombres, email, teléfono, dirección, cuentas bancarias, documentos.
        🔒 Campos bloqueados: Tipo de documento y número de documento (no modificables).
    </p>
</div>
```

**RESULTADO:**
- Traders pueden editar casi todos los campos
- Solo están bloqueados: tipo de documento, número de documento
- La nota informativa es más amigable (color azul en vez de amarillo)

---

## 🎯 CÓMO SE VE EN LA INTERFAZ

### **Vista de Tabla de Clientes**

#### **Para MASTER y OPERADOR:**
```
┌────┬──────────┬──────────┬───────────────┬────────────┬───────────┬─────────────┬───────────────┬────────┬────────────┬──────────┐
│ ID │ Tipo Doc │ Document │ Nombre        │ Email      │ Teléfono  │ Usuario     │ Fecha Regist. │ Estado │ Operacione │ Acciones │
├────┼──────────┼──────────┼───────────────┼────────────┼───────────┼─────────────┼───────────────┼────────┼────────────┼──────────┤
│ 1  │ [DNI]    │ 12345678 │ JUAN PÉREZ    │ juan@...   │ 987654321 │ [👤 trader1] │ 20/11/2025   │ Activo │ [5]        │ [Botones]│
│    │          │          │               │            │           │             │ 14:30         │        │            │          │
└────┴──────────┴──────────┴───────────────┴────────────┴───────────┴─────────────┴───────────────┴────────┴────────────┴──────────┘
```

#### **Para TRADER:**
```
┌────┬──────────┬──────────┬───────────────┬────────────┬───────────┬───────────────┬────────┬────────────┬──────────┐
│ ID │ Tipo Doc │ Document │ Nombre        │ Email      │ Teléfono  │ Fecha Regist. │ Estado │ Operacione │ Acciones │
├────┼──────────┼──────────┼───────────────┼────────────┼───────────┼───────────────┼────────┼────────────┼──────────┤
│ 1  │ [DNI]    │ 12345678 │ JUAN PÉREZ    │ juan@...   │ 987654321 │ 20/11/2025   │ Activo │ [5]        │ [Botones]│
│    │          │          │               │            │           │ 14:30         │        │            │          │
└────┴──────────┴──────────┴───────────────┴────────────┴───────────┴───────────────┴────────┴────────────┴──────────┘
```

**NOTA:** Los Traders NO ven la columna "Usuario"

---

### **Vista de Modal de Edición**

#### **Para TRADER (al editar cliente):**

```
╔══════════════════════════════════════════════════════════════╗
║  ℹ️ Permisos de Edición (Trader)                            ║
║  ✅ Puedes editar: Nombres, email, teléfono, dirección,     ║
║     cuentas bancarias, documentos.                           ║
║  🔒 Campos bloqueados: Tipo de documento y número           ║
║     de documento (no modificables).                          ║
╚══════════════════════════════════════════════════════════════╝

Tipo de Documento: [DNI ▼] 🔒 (BLOQUEADO)
Número de Documento: [12345678] 🔒 (BLOQUEADO)

Apellido Paterno: [PÉREZ____________] ✅ (EDITABLE)
Apellido Materno: [GARCÍA___________] ✅ (EDITABLE)
Nombres: [JUAN__________________] ✅ (EDITABLE)

Email: [juan@email.com________] ✅ (EDITABLE)
Teléfono: [987654321___________] ✅ (EDITABLE)

Dirección: [Av. Lima 123_______] ✅ (EDITABLE)
...

Cuenta Bancaria 1: ✅ (EDITABLE)
Cuenta Bancaria 2: ✅ (EDITABLE)
```

---

## 📊 COMPARACIÓN: INTERFAZ ANTES vs AHORA

| Elemento | ANTES | AHORA |
|----------|-------|-------|
| **Columna "Banco"** | Visible para todos | ❌ ELIMINADA |
| **Columna "Usuario"** | ❌ No existía | ✅ Visible para Master/Operador |
| **Columna "Fecha Registro"** | ❌ No visible en tabla | ✅ Visible para todos |
| **Mensaje de cuentas múltiples** | ❌ No mencionaba la posibilidad | ✅ Aclara que SÍ se puede |
| **Validación frontend duplicados** | Rechazaba banco+moneda | ✅ Solo rechaza duplicados exactos |
| **Campos editables por Trader** | Solo cuentas bancarias | ✅ Casi todos (excepto doc type y DNI) |
| **Nota para Trader** | ⚠️ Amarilla: "Solo lectura" | ℹ️ Azul: "Permisos ampliados" |

---

## 🧪 PRUEBAS RECOMENDADAS

### **1. Probar como MASTER:**
1. Ir a `/clients`
2. Verificar que aparece la columna "Usuario"
3. Verificar que aparece la columna "Fecha Registro"
4. Editar un cliente → Verificar que todos los campos son editables

### **2. Probar como OPERADOR:**
1. Ir a `/clients`
2. Verificar que aparece la columna "Usuario"
3. Verificar que aparece la columna "Fecha Registro"
4. Editar un cliente → Verificar que todos los campos son editables

### **3. Probar como TRADER:**
1. Ir a `/clients`
2. Verificar que NO aparece la columna "Usuario"
3. Verificar que SÍ aparece la columna "Fecha Registro"
4. Crear cliente nuevo con 3 cuentas BCP en soles (números diferentes)
   - ✅ Debe permitir guardarlo
5. Intentar crear cliente con 2 cuentas BCP Ahorro 123456 S/ (duplicado exacto)
   - ❌ Debe mostrar error: "cuenta duplicada exacta"
6. Editar un cliente existente:
   - Verificar nota azul: "✅ Puedes editar..."
   - Cambiar email, teléfono, dirección → ✅ Debe permitir
   - Intentar cambiar tipo de documento → 🔒 Debe estar bloqueado
   - Intentar cambiar número de documento → 🔒 Debe estar bloqueado
   - Agregar/modificar cuentas bancarias → ✅ Debe permitir

---

## 🔧 SOLUCIÓN DE PROBLEMAS

### **Problema: No veo la columna "Usuario"**
**Causa:** Estás logueado como Trader
**Solución:** La columna solo es visible para Master y Operador (es correcto)

### **Problema: Los cambios no se reflejan en el navegador**
**Causa:** Caché del navegador
**Solución:**
1. Presiona `Ctrl + Shift + R` (Windows/Linux)
2. Presiona `Cmd + Shift + R` (Mac)
3. O borra el caché del navegador

### **Problema: Como Trader puedo editar tipo de documento**
**Causa:** La función `applyRoleRestrictions()` no se está ejecutando
**Solución:**
1. Abre la consola del navegador (F12)
2. Verifica si hay errores de JavaScript
3. Asegúrate de que `currentUserRole` está definido
4. Verifica que el modal se abre correctamente

### **Problema: Validación de duplicados no funciona**
**Causa:** Campos de tipo de cuenta o número no tienen ID correcto
**Solución:**
1. Abre la consola (F12)
2. Ejecuta: `console.log(document.querySelectorAll('[id^="accountType"]'))`
3. Verifica que los IDs sean: `accountType1`, `accountType2`, etc.
4. Si no, revisa la función `addBankAccount()` en `clients.js`

---

## 📱 RESPONSIVE DESIGN

Los cambios son compatibles con dispositivos móviles:
- En pantallas pequeñas, la tabla tiene scroll horizontal
- Las columnas adicionales no rompen el diseño
- Bootstrap 5 maneja automáticamente el responsive

---

## 🎨 PERSONALIZACIÓN ADICIONAL

Si deseas personalizar los estilos:

**Color del badge de usuario:**
```css
/* Cambiar color de azul a verde */
.badge.bg-secondary {
    background-color: #28a745 !important;
}
```

**Formato de fecha diferente:**
```python
# En list.html, línea 130
{{ c.created_at.strftime('%d-%m-%Y') }}  # Guiones en vez de barras
{{ c.created_at.strftime('%d de %B %Y') }}  # "20 de Noviembre 2025"
```

---

## ✅ VERIFICACIÓN FINAL

**Checklist de implementación:**
- [✅] Columna "Usuario" visible solo para Master/Operador
- [✅] Columna "Fecha Registro" visible para todos
- [✅] Mensaje de validación actualizado en formulario
- [✅] Validación JavaScript permite múltiples cuentas mismo banco
- [✅] Traders pueden editar más campos (no solo cuentas)
- [✅] Campos protegidos bloqueados para Traders
- [✅] Nota informativa actualizada (azul, amigable)
- [✅] Exportación CSV incluye columna "Usuario Registro"

---

## 📞 SOPORTE

Si encuentras algún problema:
1. Revisa la consola del navegador (F12) → Tab "Console"
2. Verifica que los archivos se hayan actualizado correctamente
3. Borra caché y recarga (Ctrl+Shift+R)
4. Revisa los logs del servidor Python para errores backend

---

**¡Cambios implementados exitosamente!** 🚀
