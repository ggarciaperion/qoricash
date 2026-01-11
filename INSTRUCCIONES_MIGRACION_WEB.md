# 📋 Instrucciones para Verificar Migración del Rol Web

## ⚡ Opción 1: Verificación Automática (RECOMENDADO)

### Paso 1: Conectarse al servidor de Render

Desde tu terminal local:

```bash
# Reemplaza con tu servicio de Render
render shell qoricash-trading-v2
```

O desde el dashboard de Render:
1. Ve a tu servicio `qoricash-trading-v2`
2. Click en "Shell" en la barra lateral
3. Espera a que cargue la terminal

### Paso 2: Ejecutar el script de verificación

```bash
cd ~/project/src
python verify_and_migrate_web_role.py
```

Este script te mostrará:
- ✅ Si el usuario Web fue creado
- ✅ Si los constraints están actualizados
- ✅ Si todo está funcionando correctamente

---

## 🔧 Opción 2: Ejecución Manual de Migración

Si el script indica que falta la migración:

```bash
cd ~/project/src
flask db upgrade
```

---

## 📊 Verificación de Resultados

El script mostrará algo como:

```
============================================================
VERIFICACIÓN DE MIGRACIÓN - ROL WEB Y CANAL WEB
============================================================

1️⃣  Verificando historial de migraciones...
   ✅ Versión actual: 20250111_add_web_role

2️⃣  Verificando usuario con rol 'Web'...
   ✅ Usuario encontrado:
      - ID: 8
      - Username: Página Web
      - Email: web@qoricash.pe
      - DNI: 99999997
      - Rol: Web
      - Estado: Activo

3️⃣  Verificando constraint de roles en tabla users...
   ✅ Constraint encontrado
   ✅ Rol 'Web' está incluido en el constraint

4️⃣  Verificando constraint de origen en tabla operations...
   ✅ Constraint encontrado
   ✅ Canal 'web' está incluido en el constraint

5️⃣  Probando validación de origen='web'...
   ✅ Validación de origen='web' funciona correctamente

============================================================
RESUMEN
============================================================
✅ Usuario Web: CREADO

💡 ACCIONES RECOMENDADAS:
   ✅ Todo está configurado correctamente
   ✅ La página web ya puede crear operaciones con origen='web'

============================================================
```

---

## ❌ Si Algo Falla

### Error: "No se encontró usuario con rol 'Web'"

**Solución:** El script lo creará automáticamente

### Error: "Rol 'Web' NO está en el constraint"

**Solución:**
```bash
flask db upgrade
```

### Error: "ModuleNotFoundError"

**Solución:**
```bash
source venv/bin/activate  # En Linux/Mac
# o
venv\Scripts\activate     # En Windows
```

---

## 🎯 ¿Qué Significa Éxito?

Si ves estos ✅:
- ✅ Usuario Web: CREADO
- ✅ Rol 'Web' está incluido en el constraint
- ✅ Canal 'web' está incluido en el constraint

**Entonces la página web YA PUEDE:**
- Autenticar clientes con DNI
- Crear operaciones con `origen='web'`
- Todas las operaciones se asignan al trader correcto
- Funciona igual que el app móvil

---

## 📞 Soporte

Si tienes dudas, proporciona el output completo del script:
```bash
python verify_and_migrate_web_role.py > verificacion.txt 2>&1
```

Y envía el archivo `verificacion.txt`

---

**Fecha:** 11 de Enero de 2025
**Archivo:** `verify_and_migrate_web_role.py`
