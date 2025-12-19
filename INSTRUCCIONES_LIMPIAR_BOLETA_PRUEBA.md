# Instrucciones para Eliminar Boleta de Prueba B001-1 en NubeFact

## 🎯 Objetivo

Eliminar la boleta de prueba **B001-1** que se generó durante las pruebas de integración para poder volver a usar la serie B001 con correlativo automático.

---

## 📋 Pasos para Anular/Eliminar la Boleta

### Opción 1: Anular el Comprobante (Recomendado)

1. **Ingresar a NubeFact**
   - Ir a: [www.nubefact.com](https://www.nubefact.com)
   - Iniciar sesión con las credenciales de QORICASH SAC

2. **Buscar el Comprobante**
   - Ir a: **Comprobantes → Ver comprobantes**
   - Buscar la boleta: **B001-1**
   - Filtrar por: Tipo de comprobante = "Boleta de Venta"

3. **Anular el Comprobante**
   - Hacer clic en la boleta B001-1
   - Buscar el botón **"Anular"** o **"Dar de baja"**
   - Confirmar la anulación
   - Esto generará una **Comunicación de Baja** ante SUNAT

### Opción 2: Contactar Soporte de NubeFact

Si no puedes anular el comprobante desde la interfaz web:

1. **Enviar email a soporte**
   - Email: soporte@nubefact.com
   - Asunto: "Solicitud de eliminación de comprobante de prueba"

2. **Contenido del email:**
   ```
   Estimado equipo de NubeFact,

   Solicito su apoyo para eliminar el siguiente comprobante de prueba
   generado durante la integración de su API:

   - RUC: 20610605571
   - Razón Social: QORICASH SAC
   - Tipo de comprobante: Boleta de Venta
   - Serie-Número: B001-1
   - Motivo: Comprobante de prueba generado durante integración de API

   Este comprobante está impidiendo que nuestro sistema genere
   correlativos automáticos correctamente.

   Agradezco su pronta atención.

   Saludos,
   [Tu nombre]
   ```

---

## 🔄 Alternativa: Autorizar Serie B002

Si prefieres no eliminar B001-1, puedes configurar la serie B002:

### Pasos para Autorizar B002:

1. **Ingresar a NubeFact**
   - Ir a: **Configuración → Series**

2. **Agregar Nueva Serie**
   - Tipo de comprobante: **Boleta de Venta**
   - Serie: **B002**
   - Número inicial: **1**
   - Guardar cambios

3. **Modificar el código (Ya NO es necesario)**
   - El código ya está configurado para usar B001
   - Si quieres usar B002, cambia la línea 254 en `invoice_service.py`:
   ```python
   serie = "F001" if invoice_type_code == "1" else "B002"
   ```

---

## ✅ Verificación

Después de anular B001-1 o configurar B002:

1. **Completar una nueva operación de boleta** (cliente con DNI o CE)
2. **Verificar en los logs** que se genera correctamente:
   ```
   [INVOICE] Serie: B001, Número correlativo: 1
   [INVOICE] ✅ Factura generada exitosamente: B001-1
   ```
3. **Verificar que llega el email** con PDF y XML adjuntos

---

## 📝 Notas Importantes

- **En modo DEMO**: Los comprobantes se generan pero `aceptada_por_sunat=False` (es normal)
- **En producción**: Los comprobantes serán aceptados por SUNAT automáticamente
- **No se requieren cambios en el código**: El sistema ya está configurado para usar B001

---

## 🔧 Estado Actual del Sistema

### ✅ Funcionando:
- Facturas (F001) para clientes con RUC
- Formato A4 para todos los comprobantes
- Adjuntar PDF y XML en emails
- Correlativo automático

### ⏳ Pendiente:
- Anular/eliminar boleta B001-1 de prueba
- Campo CDR (requiere ejecutar migración en BD)
- Subir logo en NubeFact web

---

## 📞 Soporte

**NubeFact:**
- Email: soporte@nubefact.com
- Web: www.nubefact.com/contacto
- Horario: Lunes a Viernes 9:00 AM - 6:00 PM

**Desarrollador:**
- Si tienes problemas, revisa los logs en Render
- Comando: Ver logs de la aplicación en el dashboard de Render

---

## 🚀 Próximos Pasos

1. ✅ **Serie revertida a B001** (completado)
2. ⏳ **Anular boleta B001-1** en NubeFact web o contactar soporte
3. ⏳ **Probar generación de nueva boleta** después de limpiar
4. ⏳ **Subir logo** en NubeFact (320x80px, <20KB)
5. ⏳ **Ejecutar migración CDR** cuando la BD lo permita
