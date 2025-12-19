# Instrucciones para Agregar Teléfono y Email en Comprobantes

## 🎯 Objetivo

Agregar el teléfono **+51 926 011 920** y el email **info@qoricash.pe** en el encabezado de los comprobantes electrónicos (facturas y boletas).

---

## 📋 Configuración desde NubeFact Web

### Paso 1: Acceder a la Configuración

1. Ingresar a [www.nubefact.com](https://www.nubefact.com)
2. Iniciar sesión con las credenciales de **QORICASH SAC**
3. Ir a: **Configuración → Configuración principal**

### Paso 2: Actualizar Datos del Emisor

1. Buscar la sección **"Datos del emisor"** o **"Datos de la empresa"**
2. Completar los siguientes campos:
   - **Teléfono:** +51 926 011 920
   - **Email de contacto:** info@qoricash.pe
   - **Dirección:** Av. Aviación 2405, San Borja, Lima, Lima *(ya configurado)*

3. Hacer clic en **"Guardar"** o **"Actualizar"**

### Paso 3: Verificar Configuración de Contactos

1. Ir a: **Configuración → Contactos de la empresa**
2. Agregar o verificar contactos por categoría:
   - **Administración:** info@qoricash.pe
   - **Finanzas:** (si aplica)
   - **Tecnología:** (si aplica)

---

## 🔍 Información Importante

### Sobre los Campos del Emisor:

- **Dirección:** Ya aparece en los comprobantes (configurada en variables de entorno)
- **RUC:** 20610605571 (ya configurado)
- **Razón Social:** QORICASH SAC (ya configurado)
- **Teléfono y Email:** Se configuran desde el panel web de NubeFact

### Datos de Contacto:

```
Teléfono: +51 926 011 920
Email: info@qoricash.pe
```

---

## ⚠️ Nota Técnica

**La API de NubeFact NO incluye parámetros** como `emisor_telefono` o `emisor_email` en el JSON de generación de comprobantes.

Estos datos se configuran **una sola vez** desde el panel web de NubeFact y se aplican **automáticamente** a todos los comprobantes generados (tanto desde la web como desde la API).

Una vez configurados, aparecerán en:
- ✅ Encabezado del PDF de facturas
- ✅ Encabezado del PDF de boletas
- ✅ Todos los comprobantes futuros

---

## ✅ Verificación

Después de configurar los datos en NubeFact:

1. **Generar un comprobante de prueba** (desde la web o completando una operación)
2. **Descargar el PDF** y verificar que aparezcan:
   - Logo de QoriCash (si ya fue subido)
   - QORICASH SAC
   - RUC: 20610605571
   - Dirección: Av. Aviación 2405, San Borja, Lima, Lima
   - **Teléfono: +51 926 011 920** ← *Nuevo*
   - **Email: info@qoricash.pe** ← *Nuevo*

---

## 🔧 Configuración Alternativa (Si No Aparece)

Si después de configurar en el panel web el teléfono y email NO aparecen en el PDF:

### Opción 1: Personalización Avanzada del PDF

1. Ir a: **Configuración → Personalizar PDF**
2. Buscar opciones para **"Datos adicionales del emisor"**
3. Activar campos de teléfono y email
4. Guardar cambios

### Opción 2: Contactar Soporte

Si no encuentras las opciones, contacta a soporte de NubeFact:

**Email:** soporte@nubefact.com

**Mensaje sugerido:**
```
Estimado equipo de NubeFact,

Necesito que aparezcan los siguientes datos de contacto en el
encabezado de mis comprobantes electrónicos (facturas y boletas):

- Teléfono: +51 926 011 920
- Email: info@qoricash.pe

RUC: 20610605571
Razón Social: QORICASH SAC

¿Cómo puedo configurar estos datos para que aparezcan en el PDF
de todos mis comprobantes?

Agradezco su pronta atención.
```

---

## 📝 Campos Actuales en el Sistema

El sistema QoriCash Trading actualmente envía los siguientes datos del emisor a NubeFact:

```python
# En app/services/invoice_service.py
emisor_ruc = "20610605571"
emisor_razon_social = "QORICASH SAC"
emisor_direccion = "Av. Aviación 2405, San Borja, Lima, Lima"
```

**NO hay parámetros** `emisor_telefono` o `emisor_email` porque estos se configuran desde el panel web de NubeFact.

---

## 🚀 Próximos Pasos

1. ✅ Ingresar a NubeFact web
2. ⏳ Configurar teléfono: +51 926 011 920
3. ⏳ Configurar email: info@qoricash.pe
4. ⏳ Generar comprobante de prueba
5. ⏳ Verificar que aparezcan en el PDF

---

## 📞 Soporte

**NubeFact:**
- Email: soporte@nubefact.com
- Web: www.nubefact.com/contacto
- Horario: Lunes a Viernes 9:00 AM - 6:00 PM

**Documentación:**
- Manual de Usuario: www.nubefact.com/manual-usuario-version-online
- Ayuda: ayuda.nubefact.com
