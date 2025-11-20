# 🔐 CREDENCIALES DE ACCESO - QORICASH TRADING V2

**Fecha de generación:** 2025-11-20

---

## 👤 USUARIO MASTER (ADMINISTRADOR)

### **Credenciales de Acceso:**

```
Username: admin
Password: admin123
Email: admin@qoricash.com
DNI: 12345678
Rol: Master
Estado: Activo
```

### **URL de Acceso:**
```
http://localhost:5000/login
```

---

## ⚠️ IMPORTANTE - SEGURIDAD

### **1. Cambiar contraseña inmediatamente:**
Una vez que hagas login, ve a tu perfil y cambia la contraseña por una segura.

**Pasos:**
1. Login con las credenciales de arriba
2. Ir a perfil de usuario (clic en tu nombre arriba a la derecha)
3. Seleccionar "Cambiar contraseña"
4. Ingresar contraseña actual: `admin123`
5. Ingresar nueva contraseña segura (mínimo 8 caracteres, al menos 1 número)

### **2. Recomendaciones de contraseña segura:**
- ✅ Mínimo 8 caracteres
- ✅ Incluir números
- ✅ Incluir mayúsculas y minúsculas
- ✅ Incluir caracteres especiales (!@#$%^&*)
- ❌ NO usar fechas de nacimiento
- ❌ NO usar palabras comunes
- ❌ NO compartir la contraseña

**Ejemplo de contraseña segura:**
```
QoriCash2025!
MasterAdmin#2024
Trading$ecure123
```

---

## 🚀 CÓMO INICIAR SESIÓN

### **Paso 1: Iniciar el servidor**
```bash
cd C:\Users\ACER\Desktop\qoricash-trading-v2
python run.py
```

### **Paso 2: Abrir navegador**
```
http://localhost:5000/login
```

### **Paso 3: Ingresar credenciales**
```
Username: admin
Password: admin123
```

### **Paso 4: Cambiar contraseña**
Una vez dentro, cambiar la contraseña inmediatamente.

---

## 👥 CREAR OTROS USUARIOS

Como usuario Master, puedes crear otros usuarios:

### **Crear Trader:**
1. Ir a "Usuarios" en el menú
2. Clic en "Nuevo Usuario"
3. Llenar datos:
   - Username: (único)
   - Email: (único)
   - DNI: (8 dígitos, único)
   - Contraseña: (temporal, el usuario debe cambiarla)
   - Rol: **Trader**
   - Estado: **Activo**
4. Guardar

### **Crear Operador:**
1. Mismos pasos que arriba
2. Rol: **Operador**

### **Permisos por rol:**

| Permiso | Master | Trader | Operador |
|---------|--------|--------|----------|
| Crear clientes | ✅ | ✅ | ❌ |
| Editar clientes | ✅ | ✅ (limitado) | ✅ |
| Activar/Desactivar clientes | ✅ | ❌ | ✅ |
| Ver columna "Usuario" | ✅ | ❌ | ✅ |
| Crear operaciones | ✅ | ✅ | ❌ |
| Procesar operaciones | ✅ | ✅ | ✅ |
| Gestionar usuarios | ✅ | ❌ | ❌ |
| Exportar datos | ✅ | ❌ | ❌ |
| Ver dashboard completo | ✅ | ✅ | ❌ |

---

## 🔄 RESETEAR CONTRASEÑA (SI LA OLVIDASTE NUEVAMENTE)

Si olvidas la contraseña del Master, ejecuta este comando:

```bash
cd C:\Users\ACER\Desktop\qoricash-trading-v2
python crear_usuario_master.py
```

El script te preguntará si deseas resetear la contraseña. Responde `s` para resetearla a `admin123`.

---

## 🛠️ SOLUCIÓN DE PROBLEMAS

### **Problema: No puedo hacer login**
**Solución:**
1. Verifica que el servidor esté corriendo (`python run.py`)
2. Verifica que la URL sea correcta: `http://localhost:5000/login`
3. Verifica username y password (case-sensitive)
4. Si el usuario está "Inactivo", ejecútalo el script de reseteo

### **Problema: Dice "Usuario o contraseña incorrectos"**
**Solución:**
1. Verifica que estás escribiendo: `admin` (todo minúscula)
2. Verifica que la contraseña sea: `admin123` (sin espacios)
3. Si aún falla, ejecuta el script de reseteo

### **Problema: El servidor no inicia**
**Solución:**
```bash
# Verificar que el entorno virtual está activado
cd C:\Users\ACER\Desktop\qoricash-trading-v2
venv\Scripts\activate

# Reinstalar dependencias si es necesario
pip install -r requirements-windows.txt

# Iniciar servidor
python run.py
```

---

## 📊 VERIFICAR USUARIOS EN LA BASE DE DATOS

Si necesitas ver qué usuarios existen, ejecuta:

```bash
cd C:\Users\ACER\Desktop\qoricash-trading-v2
python crear_usuario_master.py
```

Al final del script, verás un listado de todos los usuarios Master en el sistema.

---

## 🔒 AUDITORÍA

Todos los accesos al sistema se registran en la tabla `audit_log` con:
- Usuario que hizo login
- Fecha y hora
- IP desde donde se conectó
- Acciones realizadas

Como Master, puedes revisar esta auditoría desde el panel de administración.

---

## 📞 CONTACTO DE EMERGENCIA

Si tienes problemas graves con el acceso:
1. Ejecuta `python crear_usuario_master.py` para resetear
2. Revisa los logs en `app.log` (si existe)
3. Verifica la conexión a la base de datos PostgreSQL

---

## ✅ CHECKLIST INICIAL

Después del primer login como Master:

- [ ] Cambiar contraseña de `admin123` a una segura
- [ ] Crear usuario Trader de prueba
- [ ] Crear usuario Operador de prueba
- [ ] Probar crear un cliente de prueba
- [ ] Probar crear una operación de prueba
- [ ] Verificar que las columnas "Usuario" y "Fecha Registro" se ven correctamente
- [ ] Configurar variables de entorno de Cloudinary (para subir documentos)
- [ ] Revisar que la zona horaria esté en `America/Lima`

---

**¡Bienvenido a QoriCash Trading V2!** 🚀
