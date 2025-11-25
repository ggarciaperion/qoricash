# Configuración de Envío de Emails con Gmail

## 📧 Sistema de Notificaciones por Email Implementado

El sistema ahora envía automáticamente correos electrónicos en dos casos:

### 1. **Nueva Operación Creada**
- **Remitente:** Email del Trader que creó la operación (info@qoricash.pe)
- **Destinatario principal (TO):** Cliente
- **Copia (CC):** Trader que creó la operación
- **Copia oculta (BCC):** Master y todos los Operadores activos

### 2. **Operación Completada**
- **Remitente:** Email neutro de confirmación (confirmacion@qoricash.pe)
- **Destinatario principal (TO):** Cliente
- **Copia (CC):** Trader que creó la operación
- **Contenido adicional:** Adjunta el comprobante del operador (si fue subido)

---

## 🔧 Pasos para Configurar Gmail

### Paso 1: Habilitar "Contraseña de Aplicación" en Gmail

1. Ve a tu cuenta de Google: https://myaccount.google.com/
2. En el menú lateral, selecciona **"Seguridad"**
3. Busca la sección **"Verificación en dos pasos"**
   - Si no está habilitada, habilítala primero (es requisito obligatorio)
4. Una vez habilitada la verificación en dos pasos, busca **"Contraseñas de aplicaciones"**
5. Haz clic en **"Contraseñas de aplicaciones"**
6. Selecciona:
   - Aplicación: **"Correo"**
   - Dispositivo: **"Otro (nombre personalizado)"** → Escribe: "QoriCash Trading"
7. Haz clic en **"Generar"**
8. Google te mostrará una contraseña de 16 caracteres (ejemplo: `xxxx xxxx xxxx xxxx`)
9. **¡IMPORTANTE!** Copia esta contraseña, la necesitarás en el siguiente paso

### Paso 2: Configurar el archivo .env

Abre el archivo `.env` en la raíz del proyecto y actualiza estas líneas:

```env
# Email Configuration (Gmail)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USE_SSL=False
MAIL_USERNAME=tu-email@gmail.com                    # 👈 Cambia esto por tu email de Gmail
MAIL_PASSWORD=xxxx xxxx xxxx xxxx                   # 👈 Pega aquí la contraseña de aplicación generada
MAIL_DEFAULT_SENDER=tu-email@gmail.com              # 👈 Cambia esto por tu email de Gmail
MAIL_CONFIRMATION_SENDER=confirmacion@qoricash.pe   # Email neutro para operaciones completadas
MAIL_MAX_EMAILS=None
MAIL_ASCII_ATTACHMENTS=False
```

**Ejemplo real:**
```env
MAIL_USERNAME=qoricash.trading@gmail.com
MAIL_PASSWORD=abcd efgh ijkl mnop
MAIL_DEFAULT_SENDER=qoricash.trading@gmail.com
```

### Paso 3: Reiniciar el Servidor

Después de configurar el `.env`, reinicia el servidor Flask:

1. Detén el servidor actual (Ctrl+C)
2. Vuelve a iniciarlo:
   ```bash
   python run.py
   ```

---

## ✅ Probar el Sistema

### Prueba 1: Crear una Nueva Operación
1. Inicia sesión como **Trader** o **Master**
2. Ve al menú **"Operaciones"**
3. Haz clic en **"Nueva Operación"**
4. Completa el formulario y crea la operación
5. **Resultado esperado:**
   - El cliente recibirá un email con los detalles de la operación
   - El trader recibirá una copia (CC)
   - Master y operadores recibirán una copia oculta (BCC)

### Prueba 2: Completar una Operación
1. Inicia sesión como **Operador** o **Master**
2. Ve al menú **"Operaciones"**
3. Selecciona una operación en estado "En proceso"
4. Haz clic en **"Finalizar Operación"**
5. **Resultado esperado:**
   - El cliente recibirá un email confirmando que su operación está completada
   - El trader recibirá una copia (CC)

---

## 🎨 Plantillas de Email

Las plantillas de email están diseñadas con HTML responsivo y incluyen:
- ✅ Diseño profesional con colores de QoriCash
- ✅ Responsive (se adapta a móviles y tablets)
- ✅ Información completa de la operación
- ✅ Badges de color según el tipo de operación
- ✅ Formato claro y fácil de leer

---

## 🔍 Solución de Problemas

### Error: "SMTPAuthenticationError"
**Causa:** Email o contraseña incorrectos
**Solución:**
1. Verifica que hayas copiado bien la contraseña de aplicación (16 caracteres)
2. Asegúrate de usar tu email de Gmail completo (@gmail.com)

### Error: "Connection refused"
**Causa:** Puerto o servidor SMTP incorrecto
**Solución:**
1. Verifica que `MAIL_PORT=587` y `MAIL_SERVER=smtp.gmail.com`
2. Asegúrate de que `MAIL_USE_TLS=True`

### Los emails no llegan
**Posibles causas:**
1. Verifica la carpeta de **Spam** del destinatario
2. Asegúrate de que los clientes tengan email configurado en el sistema
3. Revisa los logs del servidor para ver errores

### Ver logs de errores
Los errores de envío de email se registran en los logs sin interrumpir la operación.
Busca en la consola del servidor líneas como:
```
ERROR: Error al enviar email para operación OP-XXXXX: ...
```

---

## 📝 Notas Importantes

1. **Las operaciones NO fallan si el email no se envía:** El sistema está diseñado para que un error en el envío de email no afecte la creación o completado de operaciones.

2. **Requisitos de los clientes:** Para que un cliente reciba emails, debe tener configurado su email en el sistema (campo `email` en el modelo Cliente).

3. **Límite de envíos:** Gmail tiene un límite de **500 emails por día** para cuentas gratuitas. Si necesitas enviar más, considera usar un servicio profesional como SendGrid.

4. **Seguridad:** NUNCA compartas tu contraseña de aplicación. Si crees que fue comprometida, revócala desde tu cuenta de Google y genera una nueva.

---

## 🚀 Archivos Modificados

Los siguientes archivos fueron modificados/creados para implementar el sistema de emails:

1. **Nuevos:**
   - `app/services/email_service.py` - Servicio de envío de emails
   - `CONFIGURAR_EMAIL.md` - Este archivo de documentación

2. **Modificados:**
   - `.env` - Agregadas configuraciones de email
   - `app/config.py` - Agregadas configuraciones de Flask-Mail
   - `app/extensions.py` - Agregada extensión Flask-Mail
   - `app/__init__.py` - Inicializado Flask-Mail
   - `app/services/operation_service.py` - Integrado envío de emails en creación y completado

---

## 📞 Soporte

Si tienes problemas con la configuración, verifica:
1. Que la verificación en dos pasos esté habilitada en Gmail
2. Que hayas generado la "Contraseña de aplicación" correctamente
3. Que el archivo `.env` tenga los valores correctos
4. Que hayas reiniciado el servidor después de configurar

¡El sistema de emails está listo para usar! 🎉
