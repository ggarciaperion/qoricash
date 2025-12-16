# 🔧 CONFIGURACIÓN DE NUBEFACT EN RENDER

Este documento explica cómo configurar las credenciales de NubeFact en Render para habilitar la facturación electrónica automática.

---

## 📋 CREDENCIALES DE NUBEFACT (Demo)

**URL API**: `https://api.nubefact.com/api/v1/931258a7-ab41-488d-aedf-b8a2a502a224`
**Token**: `c7328e0c40924368814da869b11326d7e1bceebc603c43309047102b397b6370`
**RUC**: `20615113698` (QORICASH SAC)

---

## 🚀 PASOS PARA CONFIGURAR EN RENDER

### 1. Acceder al Dashboard de Render

1. Ir a: **https://dashboard.render.com**
2. Iniciar sesión con tu cuenta
3. Seleccionar el proyecto **qoricash** (Web Service)

### 2. Configurar Variables de Entorno

1. En el panel lateral izquierdo, hacer clic en **"Environment"**
2. Buscar o agregar las siguientes variables:

#### Variables a Configurar:

```
NUBEFACT_API_URL=https://api.nubefact.com/api/v1/931258a7-ab41-488d-aedf-b8a2a502a224
```

```
NUBEFACT_TOKEN=c7328e0c40924368814da869b11326d7e1bceebc603c43309047102b397b6370
```

```
NUBEFACT_RUC=20615113698
```

```
NUBEFACT_ENABLED=True
```

**IMPORTANTE**:
- Si las variables ya existen, hacer clic en **"Edit"** y actualizar los valores
- Si no existen, hacer clic en **"Add Environment Variable"** y agregarlas una por una

### 3. Guardar Cambios

1. Hacer clic en **"Save Changes"** en la parte inferior
2. Render preguntará: **"This will trigger a new deploy. Continue?"**
3. Hacer clic en **"Save & Deploy"**

### 4. Esperar Deploy Automático

1. Render automáticamente:
   - Detectará los nuevos cambios en GitHub (ya fueron pushed)
   - Aplicará las variables de entorno
   - Ejecutará la migración de base de datos
   - Reiniciará el servicio

2. Monitorear el deploy en la pestaña **"Logs"**:
   - Verás el proceso de build
   - Instalación de dependencias
   - Aplicación de migraciones
   - Inicio del servidor

3. Esperar mensaje: **"Build successful"** y **"Live"**

---

## ✅ VERIFICAR QUE FUNCIONA

### Paso 1: Revisar Logs de Deploy

En la pestaña **"Logs"** de Render, buscar:

```
Successfully installed requests-2.31.0
Running migrations...
Applying migration 20251216_add_invoices_table... OK
Starting gunicorn...
```

### Paso 2: Crear Operación de Prueba

1. Ir al sistema: **https://qoricash.onrender.com** (o tu URL de Render)
2. Iniciar sesión como **Trader** u **Operador**
3. Crear una nueva operación con un cliente existente (o crear uno nuevo)
4. **Completar la operación**

### Paso 3: Verificar en Logs de Render

1. Ir a **"Logs"** en Render
2. Buscar mensajes como:

```
[INVOICE] Generando factura electrónica para operación EXP-1234
[INVOICE] Enviando comprobante a NubeFact...
[INVOICE] Respuesta NubeFact: Status 200
[INVOICE] Factura generada: F001-00000001
[EMAIL] Adjuntando factura F001-00000001
[EMAIL] Factura F001_00000001.pdf adjuntada exitosamente
[EMAIL] Email de operacion completada enviado exitosamente
```

### Paso 4: Verificar Email Recibido

1. Revisar el email del cliente
2. Verificar que contiene:
   - ✅ Sección "🧾 Factura Electrónica"
   - ✅ Archivo PDF adjunto (ejemplo: `F001_00000001.pdf`)
   - ✅ Comprobante de operación

### Paso 5: Verificar PDF de Factura

1. Abrir el PDF adjunto
2. Verificar datos:
   - ✅ RUC emisor: 20615113698
   - ✅ Razón social: QORICASH SAC
   - ✅ Datos del cliente
   - ✅ Descripción de operación
   - ✅ Montos correctos
   - ✅ "Exonerado de IGV"

---

## 🐛 TROUBLESHOOTING

### Error: "Token de NubeFact no configurado"

**Solución**:
- Verificar que `NUBEFACT_TOKEN` está configurado en Render
- Verificar que no tiene espacios al inicio o final
- Hacer un nuevo deploy

### Error: "Error al conectar con NubeFact"

**Solución**:
- Verificar que `NUBEFACT_API_URL` está correcta
- Verificar que Render tiene conexión a internet
- Revisar logs de NubeFact para más detalles

### No se genera factura

**Solución**:
- Verificar que `NUBEFACT_ENABLED=True`
- Verificar que la migración de BD se aplicó correctamente
- Revisar logs: `[INVOICE] Facturación electrónica deshabilitada`

### Email llega sin PDF adjunto

**Solución**:
- Revisar logs: buscar `[EMAIL] Error al adjuntar factura`
- Verificar que NubeFact generó el PDF correctamente
- El email se envía igual aunque falle el adjunto

---

## 📊 ESTRUCTURA DE URL NUBEFACT

La URL completa de tu API es:
```
https://api.nubefact.com/api/v1/931258a7-ab41-488d-aedf-b8a2a502a224
```

Donde:
- **Base**: `https://api.nubefact.com/api/v1/`
- **UUID**: `931258a7-ab41-488d-aedf-b8a2a502a224` (identificador único de tu cuenta)

El sistema automáticamente construye el endpoint completo:
```
https://api.nubefact.com/api/v1/931258a7-ab41-488d-aedf-b8a2a502a224/documento/generar
```

---

## 🔄 PASAR DE DEMO A PRODUCCIÓN

Cuando estés listo para producción:

1. **Mismo TOKEN y URL** - No cambian
2. **Reiniciar numeración**:
   - Las series (F001, B001) comienzan desde 00000001
   - Eliminar facturas de prueba de la BD
3. **Contratar plan** en NubeFact (si aún no lo hiciste)
4. **Verificar en SUNAT** que los comprobantes se envían correctamente

---

## 📞 SOPORTE

**Sistema Qoricash**:
- Desarrollador: Claude Code
- Documentación: Este archivo

**NubeFact**:
- Web: https://www.nubefact.com
- Email: soporte@nubefact.com
- Ayuda: https://ayuda.nubefact.com

---

## 📝 NOTAS IMPORTANTES

⚠️ **NUNCA** subir el archivo `.env` a GitHub
⚠️ Las credenciales solo deben estar en **Render Environment Variables**
⚠️ Estas son credenciales **DEMO** - los comprobantes son de prueba
✅ El sistema está configurado para **operaciones exoneradas de IGV**
✅ Series configuradas: **F001** (Facturas) y **B001** (Boletas)

---

**Fecha de creación**: 2025-12-16
**Versión**: 1.0
