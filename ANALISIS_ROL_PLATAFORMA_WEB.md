# Análisis y Mejoras del Rol Plataforma (Canal WEB)

## 📋 Resumen Ejecutivo

El rol **Plataforma** fue creado para gestionar operaciones que provienen de la **página web pública** de QoriCash, permitiendo identificar y contabilizar estas operaciones en el sistema interno sin duplicar correos que ya envía la web.

### Estado Actual del Sistema

✅ **Funcionando Correctamente:**
- Rol "Plataforma" creado y configurado
- Campo `origen` en operaciones (`plataforma` vs `sistema`)
- API endpoints para registrar clientes y operaciones desde la web
- Lógica que previene duplicación de emails en operaciones creadas por Plataforma
- Permisos equivalentes a Trader (crear clientes, crear operaciones, ver solo sus propios registros)

⚠️ **Configuración Actual de Emails:**

| Evento | Web Pública | Sistema Interno (Rol Plataforma) | Estado |
|--------|-------------|----------------------------------|--------|
| **Cliente se registra** | ✅ Envía email | ❌ **BLOQUEADO** | ✅ Correcto |
| **Cliente es activado** | ❌ No envía | ❌ **BLOQUEADO** | ⚠️ **PROBLEMA** |
| **Operación creada** | ✅ Envía email | ❌ **BLOQUEADO** | ✅ Correcto |
| **Operación completada** | ❌ No envía | ❌ **BLOQUEADO** | ⚠️ **PROBLEMA** |

---

## 🔍 Problema Identificado

Actualmente, **TODOS** los emails del rol Plataforma están bloqueados en `app/services/email_service.py`:

```python
# Líneas 193-195
if operation.user and operation.user.role == 'Plataforma':
    logger.info(f'Email de completado omitido para operación {operation.operation_id} - creada por rol Plataforma')
    return True, 'Email omitido (rol Plataforma)'
```

### Lo que está mal:

1. **Cliente activado:** Cuando Plataforma activa un cliente, NO se envía email de bienvenida
2. **Operación completada:** Cuando Plataforma completa una operación, NO se envía email con factura/boleta

### Lo que debería suceder:

1. ✅ **Cliente registrado:** NO enviar (la web ya lo hizo)
2. ✅ **Cliente activado:** **SÍ ENVIAR** (la web no lo hace)
3. ✅ **Operación creada:** NO enviar (la web ya lo hizo)
4. ✅ **Operación completada:** **SÍ ENVIAR** con factura/boleta (la web no lo hace)

---

## 💡 Solución Propuesta

### Opción 1: Modificar Lógica de Emails (Recomendado) ⭐

Cambiar la lógica para que:
- **NO** envíe emails de registro/creación (la web ya los envió)
- **SÍ** envíe emails de activación/completado (la web no los envía)

#### Cambios en `app/services/email_service.py`:

**1. Email de Operación Completada (Línea ~193):**

```python
# ANTES:
if operation.user and operation.user.role == 'Plataforma':
    logger.info(f'Email de completado omitido para operación {operation.operation_id} - creada por rol Plataforma')
    return True, 'Email omitido (rol Plataforma)'

# DESPUÉS:
# Para rol Plataforma, SÍ enviar email de completado (incluye factura/boleta)
# La web NO envía este tipo de correos
# REMOVER ESTE BLOQUE COMPLETAMENTE
```

**2. Email de Cliente Activado (Línea ~1018):**

```python
# ANTES:
if trader and trader.role == 'Plataforma':
    logger.info(f'Email de cliente activado omitido para cliente {client.id} - registrado por rol Plataforma')
    return True, 'Email omitido (rol Plataforma)'

# DESPUÉS:
# Para rol Plataforma, SÍ enviar email de activación
# La web NO envía correos de activación
# REMOVER ESTE BLOQUE COMPLETAMENTE
```

**3. Mantener Bloqueados:**

- ✅ Email de nuevo cliente registrado (línea ~947)
- ✅ Email de nueva operación creada (línea ~138)
- ✅ Email de operación cancelada (línea ~1323)
- ✅ Email de monto modificado (línea ~1504)

---

## 🚀 Implementación de la Solución

### Paso 1: Modificar `email_service.py`

```python
# app/services/email_service.py

@staticmethod
def send_operation_completed_email(operation):
    """
    Enviar email cuando se completa una operación.

    Para rol Plataforma: SÍ se envía este email porque incluye
    factura/boleta y la web NO envía estos correos.
    """
    try:
        # REMOVER EL BLOQUEO PARA PLATAFORMA EN ESTE MÉTODO
        # Las operaciones completadas SIEMPRE deben enviar email con factura/boleta

        from flask import current_app
        from flask_mail import Message

        logger.info(f'[EMAIL] Iniciando envio de email completado para operacion {operation.operation_id}')
        # ... resto del código sin cambios


@staticmethod
def send_client_activated_email(client, trader):
    """
    Enviar email cuando se activa un cliente.

    Para rol Plataforma: SÍ se envía este email porque la web
    NO envía correos de activación.
    """
    try:
        # REMOVER EL BLOQUEO PARA PLATAFORMA EN ESTE MÉTODO
        # Los emails de activación SIEMPRE deben enviarse

        from flask import current_app
        from flask_mail import Message

        # ... resto del código sin cambios


# MANTENER bloqueados estos métodos para rol Plataforma:

@staticmethod
def send_new_client_email(client, trader):
    """Email de nuevo cliente registrado - BLOQUEADO para Plataforma"""
    try:
        # MANTENER este bloqueo
        if trader and trader.role == 'Plataforma':
            logger.info(f'Email de nuevo cliente omitido para cliente {client.id} - registrado por rol Plataforma')
            return True, 'Email omitido (rol Plataforma)'
        # ...


@staticmethod
def send_new_operation_email(operation):
    """Email de nueva operación creada - BLOQUEADO para Plataforma"""
    try:
        # MANTENER este bloqueo
        if operation.user and operation.user.role == 'Plataforma':
            logger.info(f'Email omitido para operación {operation.operation_id} - creada por rol Plataforma')
            return True, 'Email omitido (rol Plataforma)'
        # ...
```

### Paso 2: Documentar el Comportamiento

Agregar comentarios claros en el código:

```python
"""
CONFIGURACIÓN DE EMAILS PARA ROL PLATAFORMA (Canal WEB):

El rol Plataforma se utiliza para registrar operaciones que vienen
desde la página web pública. La web envía sus propios correos de
bienvenida y confirmación inicial.

EMAILS BLOQUEADOS (la web ya los envió):
✅ Cliente registrado (send_new_client_email)
✅ Operación creada (send_new_operation_email)
✅ Operación cancelada (send_operation_cancelled_email)
✅ Monto modificado (send_amount_modified_email)

EMAILS HABILITADOS (la web NO los envía):
✅ Cliente activado (send_client_activated_email)
✅ Operación completada con factura/boleta (send_operation_completed_email)
"""
```

---

## 📧 Integración con Email info@qoricash.pe

### Problema Actual

Cuando hay nuevos registros o operaciones desde la web, llega un email a **info@qoricash.pe**, pero el rol Plataforma debe ingresar manualmente los datos al sistema.

### Solución 1: Webhook de la Página Web (Recomendado) ⭐

La página web puede enviar datos automáticamente al sistema mediante los endpoints API ya existentes:

#### Endpoints Disponibles:

```
POST /api/platform/register-client
POST /api/platform/register-operation
GET  /api/platform/get-client/<dni>
GET  /api/platform/health
```

#### Flujo Propuesto:

```
1. Cliente se registra en la WEB
   ↓
2. WEB envía email de bienvenida al cliente
   ↓
3. WEB envía datos al sistema vía API:
   POST /api/platform/register-client
   Headers: Authorization: Bearer <token-plataforma>
   Body: { dni, nombre, email, ... }
   ↓
4. Sistema crea cliente automáticamente
   (NO envía email porque ya lo hizo la web)
   ↓
5. Rol Plataforma activa el cliente
   ↓
6. Sistema SÍ envía email de activación
```

#### Autenticación:

**Opción A: Token de Sesión (Ya implementado)**
```python
# La web debe autenticarse con usuario Plataforma:
POST /login
Body: {
  "username": "plataforma",
  "password": "contraseña-segura"
}
Response: { "success": true, "user": { ... } }

# Luego usar la sesión para las peticiones
POST /api/platform/register-client
Cookie: session=xyz...
```

**Opción B: API Key (Más seguro para integraciones)**
```python
# Agregar autenticación por API Key
POST /api/platform/register-client
Headers:
  X-API-Key: clave-secreta-compartida-con-web
```

### Solución 2: Procesamiento Automático de Emails

Crear un servicio que lea el buzón **info@qoricash.pe** y procese automáticamente los correos de la web.

#### Arquitectura:

```
Email de WEB → info@qoricash.pe
    ↓
Script Python (ejecutado cada 5 min)
    ↓
Lee inbox IMAP
    ↓
Parsea datos del email
    ↓
Llama a API del sistema
POST /api/platform/register-client
POST /api/platform/register-operation
```

#### Implementación:

```python
# scripts/process_web_emails.py
import imaplib
import email
import re
from email.header import decode_header
import requests

IMAP_SERVER = "imap.gmail.com"
EMAIL = "info@qoricash.pe"
PASSWORD = "contraseña-app"
API_URL = "https://qoricash-sistema.render.com/api/platform"
API_KEY = "clave-secreta"

def connect_to_inbox():
    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(EMAIL, PASSWORD)
    mail.select("INBOX")
    return mail

def parse_client_registration_email(body):
    """
    Parsear email de registro de cliente desde la web
    Formato esperado:

    Nuevo cliente registrado:
    DNI: 12345678
    Nombre: Juan Pérez
    Email: juan@example.com
    Teléfono: 987654321
    """
    data = {}
    data['dni'] = re.search(r'DNI:\s*(\d+)', body).group(1) if re.search(r'DNI:\s*(\d+)', body) else None
    data['nombre'] = re.search(r'Nombre:\s*(.+)', body).group(1).strip() if re.search(r'Nombre:\s*(.+)', body) else None
    data['email'] = re.search(r'Email:\s*([\w\.-]+@[\w\.-]+)', body).group(1) if re.search(r'Email:\s*([\w\.-]+@[\w\.-]+)', body) else None
    data['phone'] = re.search(r'Teléfono:\s*(.+)', body).group(1).strip() if re.search(r'Teléfono:\s*(.+)', body) else None
    return data

def register_client_in_system(data):
    """Registrar cliente en el sistema vía API"""
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    response = requests.post(
        f"{API_URL}/register-client",
        json=data,
        headers=headers
    )
    return response.json()

def process_emails():
    mail = connect_to_inbox()

    # Buscar emails no leídos del remitente de la web
    status, messages = mail.search(None, '(UNSEEN FROM "web@qoricash.pe")')

    for num in messages[0].split():
        status, msg_data = mail.fetch(num, "(RFC822)")

        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])

                # Obtener el asunto
                subject = decode_header(msg["Subject"])[0][0]
                if isinstance(subject, bytes):
                    subject = subject.decode()

                # Obtener el cuerpo del email
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode()
                else:
                    body = msg.get_payload(decode=True).decode()

                # Procesar según el asunto
                if "Nuevo cliente registrado" in subject:
                    client_data = parse_client_registration_email(body)
                    result = register_client_in_system(client_data)
                    print(f"Cliente registrado: {result}")

                    # Marcar email como leído
                    mail.store(num, '+FLAGS', '\\Seen')

                elif "Nueva operación" in subject:
                    # Similar para operaciones
                    pass

    mail.close()
    mail.logout()

if __name__ == "__main__":
    process_emails()
```

#### Programar Ejecución Automática:

**Opción A: Cron Job (Linux/Mac)**
```bash
# Ejecutar cada 5 minutos
*/5 * * * * cd /path/to/qoricash && venv/bin/python scripts/process_web_emails.py
```

**Opción B: Task Scheduler (Windows)**
- Crear tarea programada que ejecute el script cada 5 minutos

**Opción C: Render Cron Job (Si está en Render)**
```yaml
# render.yaml
services:
  - type: cron
    name: process-web-emails
    env: python
    schedule: "*/5 * * * *"  # Cada 5 minutos
    buildCommand: "pip install -r requirements.txt"
    startCommand: "python scripts/process_web_emails.py"
```

### Solución 3: Interfaz Manual Mejorada (Temporal)

Mientras se implementa la integración automática, mejorar la interfaz manual:

1. **Formulario rápido** para rol Plataforma que pre-rellene campos comunes
2. **Importación CSV/Excel** de clientes y operaciones en lote
3. **Copy-paste inteligente** que detecte formato del email

---

## 📊 Comparativa de Soluciones

| Solución | Complejidad | Tiempo Impl. | Automatización | Mantenimiento |
|----------|-------------|--------------|----------------|---------------|
| **Webhook WEB → API** | Media | 1-2 días | 100% | Bajo |
| **Procesar Emails** | Alta | 3-5 días | 95% | Medio |
| **Interfaz Mejorada** | Baja | 1 día | 0% (manual) | Bajo |

### Recomendación:

1. **Corto plazo:** Implementar cambios en emails (Paso 1)
2. **Mediano plazo:** Coordinar con desarrollador de la web para implementar webhooks
3. **Largo plazo:** Unificar web y sistema en una sola aplicación

---

## 🔧 Pasos de Implementación Inmediatos

### 1. Corregir Configuración de Emails (AHORA)

```bash
# Modificar app/services/email_service.py
# Remover bloqueos en:
# - send_operation_completed_email (línea ~193)
# - send_client_activated_email (línea ~1018)
```

### 2. Probar Flujo Completo

```
1. Rol Plataforma crea cliente (NO debe enviar email)
2. Rol Plataforma activa cliente (SÍ debe enviar email)
3. Rol Plataforma crea operación (NO debe enviar email)
4. Rol Plataforma completa operación (SÍ debe enviar email con factura)
```

### 3. Documentar Proceso

Crear guía para el rol Plataforma:
- Cuándo usar cada función
- Qué emails se envían automáticamente
- Cómo verificar que el cliente recibió los correos

---

## 📞 Siguiente Paso: Coordinación con Desarrollador Web

Para implementar integración automática vía webhooks:

1. **Compartir documentación de API:**
   - Endpoints disponibles: `/api/platform/*`
   - Formato de autenticación (sesión o API key)
   - Ejemplos de requests/responses

2. **Definir contrato de integración:**
   - ¿Qué datos envía la web?
   - ¿En qué momento (registro, operación, etc.)?
   - ¿Qué respuesta espera la web?

3. **Implementar en la web:**
   ```javascript
   // Ejemplo en la web pública
   async function onClientRegister(clientData) {
     // 1. Enviar email de bienvenida (web)
     await sendWelcomeEmail(clientData.email);

     // 2. Registrar en sistema interno (API)
     const response = await fetch('https://sistema.qoricash.pe/api/platform/register-client', {
       method: 'POST',
       headers: {
         'X-API-Key': 'clave-secreta',
         'Content-Type': 'application/json'
       },
       body: JSON.stringify(clientData)
     });

     if (response.ok) {
       console.log('Cliente registrado en sistema interno');
     }
   }
   ```

---

## ✅ Checklist de Implementación

### Fase 1: Corrección Inmediata (1 día)
- [ ] Remover bloqueo de email en `send_operation_completed_email`
- [ ] Remover bloqueo de email en `send_client_activated_email`
- [ ] Agregar comentarios explicativos en código
- [ ] Probar flujo completo con rol Plataforma
- [ ] Documentar comportamiento actual

### Fase 2: Mejora de Integración (1-2 semanas)
- [ ] Contactar desarrollador de la web
- [ ] Compartir documentación de API
- [ ] Definir formato de datos (JSON schema)
- [ ] Implementar webhooks en la web
- [ ] Probar integración end-to-end

### Fase 3: Automatización Completa (Opcional)
- [ ] Implementar script de procesamiento de emails
- [ ] Configurar cron job / task scheduler
- [ ] Monitorear logs y errores
- [ ] Ajustar parsing según formato real de emails

---

**¿Quieres que implemente la Fase 1 (corrección inmediata) ahora?**
