# Instrucciones para Configurar Logo en NubeFact

## 📋 Pasos para Subir el Logo de QoriCash

### 1. Preparar el Logo

**Requisitos del archivo:**
- **Dimensiones:** 320px x 80px (ancho x alto)
- **Peso máximo:** menos de 20 KB
- **Formato:** PNG o JPG (recomendado PNG con fondo transparente)

### 2. Acceder a la Configuración de NubeFact

1. Ingresar a [www.nubefact.com](https://www.nubefact.com)
2. Iniciar sesión con las credenciales de QORICASH SAC
3. Ir a: **Configuración → Configuración principal**

### 3. Subir el Logotipo

1. En la sección **"Logotipo"**, hacer clic en el botón **"Examinar"**
2. Seleccionar el archivo del logo preparado
3. El nombre del archivo aparecerá junto al botón "Examinar"
4. Hacer clic en **"Guardar"** o **"Actualizar"**

### 4. Configurar Formato de Boletas y Facturas

Para que las boletas tengan el mismo formato que las facturas (A4 en lugar de ticket):

1. En **Configuración → Configuración principal → Personalizar PDF**
2. Seleccionar **"A4"** para:
   - Facturas
   - Boletas
   - Notas asociadas
3. Guardar cambios

### 5. Habilitar Logo en Formato Ticket (si fuera necesario)

Si en algún momento necesitas formato ticket:
1. Ir a **Personalizar PDF**
2. Buscar la opción: **"¿Añadir logotipo en formato TICKET?"**
3. Seleccionar **"Sí"**

## ✅ Verificación

Una vez configurado:
- El logo aparecerá automáticamente en **todos los comprobantes generados por API**
- Tanto facturas como boletas mostrarán el logo
- El sistema ya está configurado para usar formato A4 para todos los comprobantes

## 📝 Notas Importantes

- Los cambios solo aplican a comprobantes generados **después** de guardar la configuración
- Los comprobantes anteriores mantendrán el formato con el que fueron generados
- El logo se incluye automáticamente, no requiere cambios en el código

## 🔧 Configuración Actual del Sistema

El sistema QoriCash Trading ya está configurado para:
- ✅ Formato A4 para boletas y facturas (campo `formato_de_pdf: "A4"`)
- ✅ Adjuntar PDF, XML y CDR (si disponible) en emails
- ✅ Generar comprobantes automáticamente al completar operaciones

## 📞 Soporte

Si tienes problemas para subir el logo:
- Email: soporte@nubefact.com
- Web: www.nubefact.com/contacto
