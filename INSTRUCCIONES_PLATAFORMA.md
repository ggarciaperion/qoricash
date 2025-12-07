# Instrucciones de Implementación - Rol Plataforma

## 📋 Descripción

Esta guía te ayudará a aplicar manualmente los cambios necesarios para integrar la página web pública con el sistema interno de QoriCash.

## 🚀 Scripts Disponibles

### 1. `verify_database.py` - Verificar Estado de la BD

**Propósito:** Diagnosticar el estado actual de la base de datos y detectar si faltan cambios.

**Uso en Render Shell:**
```bash
python verify_database.py
```

**Salida esperada:**
- Estado de tablas users y operations
- Presencia de columna 'origen'
- Constraints de validación
- Estadísticas de datos

---

### 2. `apply_plataforma_changes.py` - Aplicar Cambios

**Propósito:** Aplicar manualmente todos los cambios a la base de datos (si la migración automática falla).

**Uso en Render Shell:**
```bash
python apply_plataforma_changes.py
```

**Este script:**
1. ✅ Actualiza constraint de roles para incluir 'Plataforma'
2. ✅ Agrega columna 'origen' a tabla operations
3. ✅ Crea índice ix_operations_origen
4. ✅ Crea constraint check_operation_origen
5. ✅ Verifica que todos los cambios se aplicaron correctamente

---

### 3. `create_plataforma_user.py` - Crear Usuario Plataforma

**Propósito:** Crear un usuario con rol 'Plataforma' para que la web pública pueda autenticarse.

**Uso en Render Shell:**
```bash
python create_plataforma_user.py
```

**El script te pedirá:**
- Username (ej: `plataforma_web`)
- Email (ej: `plataforma@qoricash.com`)
- DNI (8 dígitos, ej: `00000001`)
- Contraseña (mínimo 8 caracteres)

**⚠️ IMPORTANTE:** Guarda las credenciales generadas de forma segura.

---

## 📝 Pasos para Resolver el Deploy Fallido

### Opción A: Ejecutar Scripts Manualmente en Render Shell

1. **Acceder a Render Shell:**
   - Ve a tu servicio en Render
   - Click en "Shell" en el menú lateral
   - Espera a que se conecte

2. **Verificar estado actual:**
   ```bash
   python verify_database.py
   ```

3. **Aplicar cambios si es necesario:**
   ```bash
   python apply_plataforma_changes.py
   ```

4. **Crear usuario Plataforma:**
   ```bash
   python create_plataforma_user.py
   ```

5. **Verificar nuevamente:**
   ```bash
   python verify_database.py
   ```

### Opción B: Eliminar la Migración y Usar Solo Scripts

Si las migraciones de Alembic están causando problemas, puedes:

1. Eliminar temporalmente el archivo de migración del repositorio
2. Hacer deploy sin la migración
3. Ejecutar `apply_plataforma_changes.py` manualmente en Shell
4. Restaurar el archivo de migración para futuros despliegues

---

## 🔍 Verificar que Todo Funciona

Después de aplicar los cambios, verifica:

### 1. Base de Datos
```bash
python verify_database.py
```

Debe mostrar:
- ✅ Constraint de roles incluye 'Plataforma'
- ✅ Columna 'origen' existe en operations
- ✅ Índice ix_operations_origen existe
- ✅ Constraint check_operation_origen existe

### 2. Usuario Plataforma Creado
```bash
python create_plataforma_user.py
```

### 3. Endpoints API Disponibles

Prueba que los endpoints estén accesibles:

```bash
# Health check (no requiere auth)
curl https://tu-app.onrender.com/api/platform/health

# Debería retornar:
# {"status":"ok","service":"QoriCash Platform API","version":"1.0.0"}
```

---

## 📚 Endpoints de la API Platform

Una vez todo configurado, la web pública puede usar:

### POST `/api/platform/register-client`
Registrar nuevo cliente desde la web.

### POST `/api/platform/register-operation`
Crear operación de compra/venta desde la web.

### GET `/api/platform/get-client/<dni>`
Consultar si un cliente existe.

### GET `/api/platform/health`
Verificar estado del servicio.

---

## 🆘 Solución de Problemas

### Error: "column 'origen' does not exist"
**Solución:**
```bash
python apply_plataforma_changes.py
```

### Error: "role 'Plataforma' violates check constraint"
**Solución:**
```bash
python apply_plataforma_changes.py
```

### Error: "User already exists"
**Solución:** Ya existe un usuario Plataforma. Usa ese o elimínalo primero.

### Error de migración de Alembic
**Solución:** Usa los scripts manuales en lugar de las migraciones automáticas.

---

## 📞 Resumen de Cambios Implementados

### Modelo User
- ✅ Nuevo rol: `'Plataforma'`
- ✅ Método: `is_plataforma()`
- ✅ Constraint actualizado

### Modelo Operation
- ✅ Nuevo campo: `origen` (plataforma/sistema)
- ✅ Índice en campo origen
- ✅ Constraint de validación
- ✅ Incluido en método `to_dict()`

### API Platform
- ✅ Blueprint registrado: `/api/platform/*`
- ✅ 4 endpoints disponibles
- ✅ Seguridad: Solo rol Plataforma o Master
- ✅ CSRF exempt para APIs externas

### Servicio de Operaciones
- ✅ Soporte para parámetro `origen`
- ✅ Validación de valores
- ✅ Rol Plataforma puede crear operaciones

---

## ✅ Checklist Final

Antes de integrar con la web pública:

- [ ] Scripts ejecutados exitosamente
- [ ] `verify_database.py` muestra todo en verde
- [ ] Usuario Plataforma creado y credenciales guardadas
- [ ] Health check endpoint responde correctamente
- [ ] Deploy de Render completado sin errores
- [ ] Paleta de colores verde/azul aplicada (commit anterior)

---

**Última actualización:** 2025-12-07
**Versión:** 1.0.0
