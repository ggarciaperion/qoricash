# Configurar Email en Render (Producción)

## Problema
El sistema NO envía emails en producción porque las credenciales de email NO están configuradas en Render.

En local funcionaba porque están en el archivo `.env`, pero este archivo NO se sube a GitHub (está en .gitignore).

---

## Solución: Agregar Variables de Entorno en Render

### Paso 1: Obtener credenciales de tu `.env` local

Abre tu archivo `.env` local y copia los valores de estas variables:

```
MAIL_SERVER=smtp.gmail.com (o tu servidor SMTP)
MAIL_PORT=587 (o 465)
MAIL_USE_TLS=True
MAIL_USE_SSL=False
MAIL_USERNAME=tu_correo@gmail.com
MAIL_PASSWORD=tu_contraseña_o_app_password
MAIL_DEFAULT_SENDER=tu_correo@gmail.com

# Para emails de confirmación (si usas otro correo)
MAIL_CONFIRMATION_USERNAME=correo_confirmacion@gmail.com
MAIL_CONFIRMATION_PASSWORD=contraseña_confirmacion
MAIL_CONFIRMATION_SENDER=correo_confirmacion@gmail.com
```

### Paso 2: Configurar en Render Dashboard

1. Ve a: https://dashboard.render.com
2. Selecciona tu web service
3. Ve a **"Environment"** (menú izquierda)
4. Click en **"Add Environment Variable"**
5. Agregar UNA POR UNA:

| Key | Value (ejemplo) |
|-----|-----------------|
| `MAIL_SERVER` | `smtp.gmail.com` |
| `MAIL_PORT` | `587` |
| `MAIL_USE_TLS` | `True` |
| `MAIL_USE_SSL` | `False` |
| `MAIL_USERNAME` | `tu_correo@gmail.com` |
| `MAIL_PASSWORD` | `tu_app_password_gmail` |
| `MAIL_DEFAULT_SENDER` | `tu_correo@gmail.com` |
| `MAIL_CONFIRMATION_USERNAME` | (mismo que MAIL_USERNAME o diferente) |
| `MAIL_CONFIRMATION_PASSWORD` | (contraseña del correo) |
| `MAIL_CONFIRMATION_SENDER` | (mismo que MAIL_DEFAULT_SENDER) |
| `MAIL_MAX_EMAILS` | `10` |
| `MAIL_ASCII_ATTACHMENTS` | `False` |

6. Click **"Save Changes"**
7. Esto causará un **REDEPLOY automático**

---

## Importante: Gmail App Password

Si usas Gmail, NO puedes usar tu contraseña normal. Debes crear un **App Password**:

### Crear App Password en Gmail:

1. Ve a: https://myaccount.google.com/security
2. Activa **"Verificación en 2 pasos"** (si no está activa)
3. Ve a: https://myaccount.google.com/apppasswords
4. Selecciona:
   - App: **Mail**
   - Device: **Other (custom name)** → Escribe "QoriCash Render"
5. Click **"Generate"**
6. Copia el password de 16 caracteres (sin espacios)
7. Usa ESTE password en `MAIL_PASSWORD` en Render

---

## Verificación

Después del redeploy:

1. Crea un cliente o operación que envíe email
2. Verifica que el email llegue
3. Si NO llega, revisa los logs de Render:
   - Busca errores de SMTP
   - Verifica que las credenciales sean correctas

---

## Troubleshooting

### Error: "Authentication failed"
- Verifica que `MAIL_USERNAME` y `MAIL_PASSWORD` sean correctos
- Si usas Gmail, usa App Password (no tu contraseña normal)

### Error: "Connection refused"
- Verifica `MAIL_SERVER` y `MAIL_PORT`
- Gmail: smtp.gmail.com:587 (TLS) o smtp.gmail.com:465 (SSL)

### Error: "TLS/SSL error"
- Si usas port 587: `MAIL_USE_TLS=True`, `MAIL_USE_SSL=False`
- Si usas port 465: `MAIL_USE_TLS=False`, `MAIL_USE_SSL=True`

---

## Alternativa: Usar SendGrid (Recomendado para producción)

En lugar de Gmail, puedes usar SendGrid (más confiable):

1. Crear cuenta gratis: https://signup.sendgrid.com/
2. Plan gratis: 100 emails/día
3. Configurar en Render:
   - `MAIL_SERVER=smtp.sendgrid.net`
   - `MAIL_PORT=587`
   - `MAIL_USE_TLS=True`
   - `MAIL_USERNAME=apikey`
   - `MAIL_PASSWORD=<tu_sendgrid_api_key>`

