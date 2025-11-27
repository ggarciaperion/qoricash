# 🚀 Guía de Deployment a Producción - QoriCash Trading

## 📋 Tabla de Contenidos
1. [Preparación Previa](#preparación-previa)
2. [Configurar Cloudinary](#configurar-cloudinary)
3. [Configurar Gmail](#configurar-gmail)
4. [Deployment en Render](#deployment-en-render)
5. [Verificación Post-Deployment](#verificación-post-deployment)
6. [Troubleshooting](#troubleshooting)

---

## 🔧 Preparación Previa

### Requisitos
- [ ] Cuenta GitHub (código debe estar en repositorio)
- [ ] Cuenta Render.com (gratuita)
- [ ] Cuenta Cloudinary (gratuita)
- [ ] 2 cuentas Gmail (o usar 1 para ambos propósitos)

### Archivos Necesarios (✅ Ya creados)
- ✅ `render.yaml` - Configuración de Render
- ✅ `Procfile` - Comandos de inicio
- ✅ `runtime.txt` - Versión de Python
- ✅ `requirements.txt` - Dependencias
- ✅ `gunicorn_config.py` - Configuración del servidor
- ✅ `.env.production.template` - Template de variables

---

## ☁️ 1. Configurar Cloudinary (Almacenamiento de Archivos)

### Paso 1: Crear Cuenta
1. Ir a https://cloudinary.com/users/register_free
2. Registrarse con email
3. Verificar email

### Paso 2: Obtener Credenciales
1. Ir al Dashboard: https://console.cloudinary.com/
2. Copiar las siguientes credenciales:
   ```
   Cloud Name: your-cloud-name
   API Key: 123456789012345
   API Secret: AbCdEfGhIjKlMnOpQrStUvWxYz
   ```

### Paso 3: Crear Carpetas (Opcional)
En Settings > Upload > Upload presets, puedes crear presets para:
- `client_documents` - Documentos de clientes
- `operation_proofs` - Comprobantes de operaciones
- `validation_oc` - Validaciones OC

**Límites Plan Gratuito:**
- ✅ 25 GB almacenamiento
- ✅ 25 GB bandwidth/mes
- ✅ Suficiente para 10,000+ documentos

---

## 📧 2. Configurar Gmail (App Passwords)

### Email 1: Operaciones (Nuevas operaciones)
1. Ir a https://myaccount.google.com/apppasswords
2. Seleccionar "Correo" y "Windows Computer"
3. Generar contraseña (ej: `abcd efgh ijkl mnop`)
4. Guardar:
   ```
   MAIL_USERNAME=operaciones@tuempresa.com
   MAIL_PASSWORD=abcdefghijklmnop (sin espacios)
   MAIL_DEFAULT_SENDER=operaciones@tuempresa.com
   ```

### Email 2: Confirmaciones (Operaciones completadas)
1. Repetir proceso con segunda cuenta Gmail
2. Guardar:
   ```
   MAIL_CONFIRMATION_USERNAME=confirmaciones@tuempresa.com
   MAIL_CONFIRMATION_PASSWORD=pqrstuvwxyz12345
   MAIL_CONFIRMATION_SENDER=confirmaciones@tuempresa.com
   ```

**Nota:** Puedes usar la misma cuenta para ambos si lo prefieres.

---

## 🌐 3. Deployment en Render

### Opción A: Deployment Automático con Blueprint (Recomendado)

#### Paso 1: Conectar Repositorio
1. Ir a https://dashboard.render.com/
2. Clic en "New" > "Blueprint"
3. Conectar tu repositorio GitHub
4. Seleccionar el repositorio `Qoricashtrading`

#### Paso 2: Render detectará automáticamente `render.yaml`
- ✅ Creará base de datos PostgreSQL
- ✅ Creará web service
- ✅ Configurará variables de entorno básicas

#### Paso 3: Configurar Variables Secretas
En el Dashboard del Web Service, ir a "Environment" y agregar:

```bash
# CLOUDINARY
CLOUDINARY_CLOUD_NAME=tu-cloud-name
CLOUDINARY_API_KEY=123456789012345
CLOUDINARY_API_SECRET=AbCdEfGhIjKlMnOpQrStUvWxYz

# EMAIL PRINCIPAL
MAIL_USERNAME=operaciones@tuempresa.com
MAIL_PASSWORD=abcdefghijklmnop
MAIL_DEFAULT_SENDER=operaciones@tuempresa.com

# EMAIL CONFIRMACIÓN
MAIL_CONFIRMATION_USERNAME=confirmaciones@tuempresa.com
MAIL_CONFIRMATION_PASSWORD=pqrstuvwxyz12345
MAIL_CONFIRMATION_SENDER=confirmaciones@tuempresa.com
```

#### Paso 4: Deploy
1. Clic en "Manual Deploy" > "Deploy latest commit"
2. Esperar 5-10 minutos
3. Ver logs en tiempo real

### Opción B: Deployment Manual

#### Paso 1: Crear PostgreSQL Database
1. New > PostgreSQL
2. Name: `qoricash-db`
3. Database: `qoricash_trading_prod`
4. User: `qoricash_user`
5. Plan: **Starter ($7/mes)** o Free (limitado)
6. Create Database
7. Copiar "Internal Database URL"

#### Paso 2: Crear Web Service
1. New > Web Service
2. Conectar repositorio GitHub
3. Configurar:
   ```
   Name: qoricash-trading
   Region: Oregon (o el más cercano)
   Branch: main
   Runtime: Python 3
   Build Command: pip install -r requirements.txt && flask db upgrade
   Start Command: gunicorn -c gunicorn_config.py run:app
   Plan: Starter ($7/mes)
   ```

#### Paso 3: Variables de Entorno
Agregar TODAS las variables del template `.env.production.template`:

```bash
FLASK_ENV=production
SECRET_KEY=GENERAR_CLAVE_SEGURA_AQUI
DATABASE_URL=postgresql://user:pass@host/db  # Copiar de Internal URL
SESSION_COOKIE_SECURE=True
PERMANENT_SESSION_LIFETIME=43200

# ... resto de variables
```

#### Paso 4: Deploy
1. Clic en "Create Web Service"
2. Esperar el primer deploy (5-10 min)

---

## ✅ 4. Verificación Post-Deployment

### Paso 1: Verificar Health Check
```bash
curl https://tu-app.onrender.com/health
# Debe retornar: {"status":"healthy","service":"qoricash-trading"}
```

### Paso 2: Verificar Base de Datos
1. Ir a https://tu-app.onrender.com
2. Intentar iniciar sesión
3. Si no hay usuarios, crear uno desde la consola Render:

```bash
# En Render Shell
flask shell
from app.models.user import User
from app.extensions import db
user = User(username='admin', email='admin@qoricash.com', role='Master', status='Activo')
user.set_password('TuPasswordSeguro123!')
db.session.add(user)
db.session.commit()
exit()
```

### Paso 3: Verificar Cloudinary
1. Ir a Clientes > Nuevo Cliente
2. Subir un documento
3. Verificar que se suba correctamente
4. Ver en Cloudinary Console que aparece el archivo

### Paso 4: Verificar Emails
1. Crear una operación de prueba
2. Verificar que llegue email al cliente
3. Completar operación
4. Verificar que llegue email de confirmación

### Paso 5: Verificar WebSocket
1. Abrir 2 pestañas del navegador
2. Crear operación en una
3. Verificar que la otra se actualice en tiempo real

---

## 🔧 5. Configuraciones Adicionales

### Dominio Personalizado (Opcional)
1. En Render Dashboard > Settings > Custom Domain
2. Agregar: `app.tuempresa.com`
3. Configurar DNS en tu proveedor:
   ```
   Type: CNAME
   Name: app
   Value: tu-app.onrender.com
   ```
4. Esperar propagación DNS (5-60 min)
5. SSL se configura automáticamente

### Backup Automático de Base de Datos
1. En PostgreSQL Dashboard > Settings
2. Habilitar "Daily Backups" (plan Starter+)
3. Retención: 7 días

### Monitoring y Alertas
1. En Web Service > Settings > Health Check Path
2. Configurar: `/health`
3. En Settings > Notifications
4. Agregar email para alertas

---

## 🐛 6. Troubleshooting

### Error: "Application failed to start"
**Solución:**
1. Ver logs completos en Render Dashboard
2. Verificar que todas las variables estén configuradas
3. Verificar que `DATABASE_URL` esté correcta
4. Ejecutar manualmente: `flask db upgrade`

### Error: "Database connection failed"
**Solución:**
1. Verificar que la base de datos esté creada
2. Copiar "Internal Database URL" (no External)
3. Verificar formato: `postgresql://` (no `postgres://`)

### Error: "Import Error" o "Module not found"
**Solución:**
1. Verificar `requirements.txt` está completo
2. Ver logs de build
3. Reintentar deployment

### Emails no se envían
**Solución:**
1. Verificar App Passwords de Gmail
2. NO usar password normal de Gmail
3. Verificar que no tengan espacios
4. Revisar logs: buscar `[EMAIL]`

### Archivos no se suben
**Solución:**
1. Verificar credenciales de Cloudinary
2. Verificar que `CLOUDINARY_URL` esté correcto
3. Ver logs de FileService
4. Verificar cuota de Cloudinary

### WebSocket no funciona
**Solución:**
1. Verificar que `eventlet` esté instalado
2. Ver `gunicorn_config.py` tiene `worker_class = 'eventlet'`
3. Render soporta WebSocket en todos los planes

---

## 📊 7. Monitoreo de Producción

### Métricas Clave
- **Response Time:** < 2 segundos
- **Error Rate:** < 1%
- **Memory Usage:** < 450 MB (plan Starter = 512 MB)
- **CPU Usage:** < 80%

### Logs Importantes
```bash
# Ver logs en tiempo real
# Render Dashboard > Logs > Live

# Buscar errores
grep ERROR logs.txt

# Ver performance
grep "response time" logs.txt
```

### Escalamiento
Si necesitas más recursos:
1. Upgrade a plan "Standard" ($25/mes)
2. Aumenta workers en `gunicorn_config.py`
3. Considera Redis para sessions (multiple workers)

---

## 🎯 8. Checklist Final

### Pre-Launch
- [ ] Todas las variables de entorno configuradas
- [ ] Base de datos creada y migrada
- [ ] Usuario Master creado
- [ ] Cloudinary funcionando
- [ ] Emails funcionando (ambos)
- [ ] Health check respondiendo
- [ ] WebSocket funcionando

### Post-Launch
- [ ] Monitoring configurado
- [ ] Backups habilitados
- [ ] Dominio personalizado (opcional)
- [ ] SSL verificado (automático en Render)
- [ ] Alertas configuradas
- [ ] Documentación compartida con equipo

---

## 💰 9. Costos Estimados

### Plan Recomendado para Producción

**Render (Recomendado)**
- Web Service Starter: **$7/mes**
- PostgreSQL Starter: **$7/mes**
- **Total: $14/mes**

Incluye:
- ✅ 512 MB RAM
- ✅ 0.5 CPU
- ✅ SSL automático
- ✅ 100 GB bandwidth
- ✅ Backups diarios
- ✅ Auto-scaling
- ✅ 99.9% uptime

**Servicios Externos**
- Cloudinary Free: **$0/mes** (25 GB)
- Gmail: **$0/mes** (ilimitado)

**Total Mensual: ~$14 USD**

### Alternativa: Railway
- Hobby Plan: **$5/mes**
- PostgreSQL: **Incluido**
- Similar a Render pero menor uptime

---

## 🆘 Soporte

### Recursos
- **Render Docs:** https://render.com/docs
- **Flask Docs:** https://flask.palletsprojects.com
- **Cloudinary Docs:** https://cloudinary.com/documentation

### Comandos Útiles
```bash
# Conectar a shell de Render
# Dashboard > Shell

# Ver estado de migraciones
flask db current

# Ejecutar migración
flask db upgrade

# Crear usuario Master
flask shell
>>> from app.models.user import User
>>> from app.extensions import db
>>> user = User(username='admin', email='admin@empresa.com', role='Master', status='Activo')
>>> user.set_password('Password123!')
>>> db.session.add(user)
>>> db.session.commit()

# Ver logs en vivo
# Dashboard > Logs
```

---

## ✨ Conclusión

Siguiendo esta guía paso a paso, tendrás **QoriCash Trading** corriendo en producción de manera profesional, segura y escalable.

**Tiempo estimado:** 30-45 minutos
**Dificultad:** Media
**Costo mensual:** $14 USD

¡Éxito con el deployment! 🚀
