# 🚀 GUÍA DE INSTALACIÓN - QORICASH TRADING V2

## 📦 LO QUE TENEMOS HASTA AHORA

✅ **Estructura base completa**
✅ **Configuración profesional**
✅ **Modelos de base de datos (ORM)**
✅ **Utilidades y decoradores**
✅ **Sistema listo para extender**

---

## 📋 PASO 1: CREAR EL PROYECTO LOCALMENTE

### 1.1 Crear carpeta del proyecto
```bash
mkdir qoricash-trading-v2
cd qoricash-trading-v2
```

### 1.2 Crear estructura de carpetas
```bash
# En Windows PowerShell:
New-Item -ItemType Directory -Force -Path app/models
New-Item -ItemType Directory -Force -Path app/services
New-Item -ItemType Directory -Force -Path app/routes
New-Item -ItemType Directory -Force -Path app/schemas
New-Item -ItemType Directory -Force -Path app/utils
New-Item -ItemType Directory -Force -Path app/templates/auth
New-Item -ItemType Directory -Force -Path app/templates/dashboard
New-Item -ItemType Directory -Force -Path app/templates/users
New-Item -ItemType Directory -Force -Path app/templates/clients
New-Item -ItemType Directory -Force -Path app/templates/operations
New-Item -ItemType Directory -Force -Path app/static/css
New-Item -ItemType Directory -Force -Path app/static/js
New-Item -ItemType Directory -Force -Path app/static/images
New-Item -ItemType Directory -Force -Path migrations/versions
New-Item -ItemType Directory -Force -Path tests
New-Item -ItemType Directory -Force -Path scripts

# En Linux/Mac:
mkdir -p app/{models,services,routes,schemas,utils}
mkdir -p app/templates/{auth,dashboard,users,clients,operations}
mkdir -p app/static/{css,js,images}
mkdir -p migrations/versions
mkdir -p tests
mkdir -p scripts
```

### 1.3 Copiar archivos generados
Copia todos los archivos que generé en `/mnt/user-data/outputs/new-system/` a tu proyecto local.

---

## 📋 PASO 2: INSTALAR DEPENDENCIAS

### 2.1 Crear entorno virtual
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 2.2 Instalar dependencias
```bash
pip install -r requirements.txt
```

---

## 📋 PASO 3: CONFIGURAR VARIABLES DE ENTORNO

### 3.1 Copiar .env.example a .env
```bash
cp .env.example .env
```

### 3.2 Editar .env con tus valores
```bash
# Generar SECRET_KEY
python -c "import secrets; print(secrets.token_hex(32))"

# Editar .env con tu editor favorito
# Llenar DATABASE_URL, CLOUDINARY_URL, etc.
```

---

## 📋 PASO 4: INICIALIZAR BASE DE DATOS

### 4.1 Crear base de datos en PostgreSQL
```sql
-- En tu PostgreSQL local o Render
CREATE DATABASE qoricash_v2;
```

### 4.2 Inicializar Alembic
```bash
flask db init
```

### 4.3 Crear primera migración
```bash
flask db migrate -m "Initial migration - User, Client, Operation, AuditLog"
```

### 4.4 Aplicar migración
```bash
flask db upgrade
```

---

## 📋 PASO 5: CREAR USUARIO ADMINISTRADOR

Crear archivo `scripts/create_admin.py`:

```python
from app import create_app, db
from app.models.user import User
from app.utils.formatters import now_peru

app = create_app()

with app.app_context():
    # Verificar si ya existe
    existing = User.query.filter_by(username='admin').first()
    if existing:
        print("❌ Usuario admin ya existe")
    else:
        # Crear usuario Master
        admin = User(
            username='admin',
            email='admin@qoricash.com',
            dni='12345678',
            role='Master',
            status='Activo',
            created_at=now_peru()
        )
        admin.set_password('admin123')  # Cambiar en producción
        
        db.session.add(admin)
        db.session.commit()
        
        print("✅ Usuario admin creado")
        print("   Username: admin")
        print("   Password: admin123")
        print("   ⚠️  CAMBIAR CONTRASEÑA EN PRODUCCIÓN")
```

Ejecutar:
```bash
python scripts/create_admin.py
```

---

## 📋 PASO 6: EJECUTAR EN DESARROLLO

```bash
python run.py
```

Abrir navegador en: http://localhost:5000

---

## 📋 PASO 7: VERIFICAR QUE FUNCIONA

1. ✅ El servidor arranca sin errores
2. ✅ La base de datos se conecta
3. ✅ Las tablas se crearon correctamente

---

## 🎯 PRÓXIMOS PASOS

En la siguiente entrega voy a crear:

1. **Servicios (Business Logic)**
   - AuthService (autenticación)
   - UserService (gestión de usuarios)
   - ClientService (gestión de clientes)
   - OperationService (gestión de operaciones)
   - FileService (carga de archivos con Cloudinary)
   - NotificationService (notificaciones en tiempo real)

2. **Rutas (Blueprints)**
   - auth.py (login, logout)
   - dashboard.py (dashboards)
   - users.py (CRUD de usuarios)
   - clients.py (CRUD de clientes)
   - operations.py (CRUD de operaciones)

3. **Templates HTML**
   - Base template
   - Login
   - Dashboards
   - Gestión de usuarios
   - Gestión de clientes
   - Gestión de operaciones

---

## ✅ CHECKLIST DE INSTALACIÓN

- [ ] Carpetas creadas
- [ ] Archivos copiados
- [ ] Entorno virtual creado y activado
- [ ] Dependencias instaladas
- [ ] Variables de entorno configuradas
- [ ] Base de datos creada
- [ ] Migraciones aplicadas
- [ ] Usuario admin creado
- [ ] Servidor ejecutándose

---

## 🆘 TROUBLESHOOTING

### Error: "No module named 'app'"
```bash
# Asegúrate de estar en la raíz del proyecto
cd qoricash-trading-v2
# Verifica que exista app/__init__.py
```

### Error: "DATABASE_URL not found"
```bash
# Verifica que .env existe y está configurado
cat .env  # Linux/Mac
type .env  # Windows
```

### Error: "Cannot connect to database"
```bash
# Verifica que PostgreSQL está corriendo
# Verifica que DATABASE_URL es correcto
```

---

## 📞 ¿ESTÁS LISTO?

Confirma cuando hayas completado estos pasos y continuaremos con:
1. Servicios de negocio
2. Rutas y controllers
3. Templates HTML
4. JavaScript para interactividad
5. Deploy a producción

**El sistema está 40% completo. Siguiente entrega: Servicios y Rutas (40% más).**
