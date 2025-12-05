# Documentación Técnica del Sistema QoriCash Trading V2

## Propósito del Documento

Este documento describe la arquitectura, estructura y funcionamiento del sistema **QoriCash Trading V2**, desarrollado para la gestión de operaciones cambiarias en una casa de cambio online. El propósito es facilitar su revisión profesional, integración con Amazon Web Services (AWS) y conexión con sistemas externos.

---

## 1. Descripción General del Sistema

### 1.1 Objetivo del Sistema

QoriCash Trading V2 es una plataforma web interna para gestión de operaciones de cambio de divisas (compra/venta de dólares). Permite:

- Registro y gestión de clientes (KYC/AML)
- Creación y seguimiento de operaciones cambiarias
- Control de usuarios y perfiles de acceso (Master, Trader, Operador, Middle Office)
- Monitoreo de compliance y gestión de riesgos
- Notificaciones en tiempo real y correos electrónicos automatizados
- Dashboard con estadísticas operativas y financieras

### 1.2 Stack Tecnológico

| Componente | Tecnología | Versión |
|------------|------------|---------|
| **Backend** | Python / Flask | 3.0.0 |
| **Base de Datos** | PostgreSQL | Compatible con 12+ |
| **ORM** | SQLAlchemy + Flask-Migrate | 3.1.1 / 4.0.5 |
| **Autenticación** | Flask-Login + Werkzeug | 0.6.3 |
| **WebSocket** | Flask-SocketIO + Eventlet | 5.3.5 |
| **Almacenamiento de Archivos** | Cloudinary | 1.41.0 |
| **Correo Electrónico** | Flask-Mail + SMTP | 0.9.1 |
| **Servidor de Producción** | Gunicorn + Eventlet | 21.2.0 |
| **Frontend** | HTML5, CSS3, JavaScript (Vanilla) | - |
| **UI Framework** | Bootstrap 5 + DataTables | - |

### 1.3 Módulos Principales

El sistema está organizado en los siguientes módulos funcionales:

1. **Autenticación (`auth`)**: Login, logout, gestión de sesiones
2. **Dashboard (`dashboard`)**: Estadísticas, métricas, gráficos
3. **Usuarios (`users`)**: CRUD de usuarios, roles, permisos
4. **Clientes (`clients`)**: CRUD de clientes, documentación KYC
5. **Operaciones (`operations`)**: Creación, seguimiento y cierre de operaciones
6. **Posición (`position`)**: Control de saldos bancarios en USD/PEN
7. **Compliance (`compliance`)**: KYC/AML, perfiles de riesgo, alertas
8. **Accounting (`accounting`)**: Contabilización y conciliación (en desarrollo)

---

## 2. Arquitectura del Proyecto

### 2.1 Patrón de Arquitectura

El sistema utiliza el patrón **MVC (Model-View-Controller)** adaptado para Flask, con una separación clara de responsabilidades:

```
Rutas (Routes) → Servicios (Services) → Modelos (Models) → Base de Datos
                      ↓
                  Templates (Views)
```

**Flujo típico de una petición:**

1. Cliente HTTP → Ruta (Blueprint)
2. Ruta → Servicio (lógica de negocio)
3. Servicio → Modelo (ORM SQLAlchemy)
4. Modelo → PostgreSQL
5. Respuesta: JSON (API) o HTML renderizado (Jinja2)

### 2.2 Estructura de Carpetas

```
Qoricashtrading/
│
├── app/                          # Código de la aplicación
│   ├── __init__.py              # Factory de la app Flask
│   ├── config.py                # Configuraciones (dev, prod)
│   ├── extensions.py            # Extensiones (db, mail, socketio, etc.)
│   │
│   ├── models/                  # Modelos de base de datos (ORM)
│   │   ├── user.py             # Usuarios del sistema
│   │   ├── client.py           # Clientes
│   │   ├── operation.py        # Operaciones cambiarias
│   │   ├── compliance.py       # Compliance (KYC, riesgo)
│   │   ├── audit_log.py        # Logs de auditoría
│   │   ├── bank_balance.py     # Saldos bancarios
│   │   └── ...
│   │
│   ├── routes/                  # Controladores (Blueprints)
│   │   ├── auth.py             # Autenticación
│   │   ├── dashboard.py        # Dashboard principal
│   │   ├── users.py            # Gestión de usuarios
│   │   ├── clients.py          # Gestión de clientes
│   │   ├── operations.py       # Gestión de operaciones
│   │   ├── compliance.py       # Middle Office / Compliance
│   │   └── ...
│   │
│   ├── services/                # Lógica de negocio
│   │   ├── auth_service.py
│   │   ├── client_service.py
│   │   ├── operation_service.py
│   │   ├── email_service.py
│   │   ├── compliance_service.py
│   │   ├── file_service.py     # Cloudinary uploads
│   │   └── ...
│   │
│   ├── templates/               # Vistas HTML (Jinja2)
│   │   ├── base.html           # Template base
│   │   ├── auth/               # Login, registro
│   │   ├── dashboard/          # Dashboard principal
│   │   ├── clients/            # Vistas de clientes
│   │   ├── operations/         # Vistas de operaciones
│   │   ├── compliance/         # Vistas KYC/Compliance
│   │   └── ...
│   │
│   ├── static/                  # Archivos estáticos (CSS, JS, imágenes)
│   │   ├── css/
│   │   ├── js/
│   │   └── img/
│   │
│   ├── utils/                   # Utilidades y helpers
│   │   ├── formatters.py       # Formateadores (fechas, moneda)
│   │   ├── validators.py       # Validadores
│   │   ├── decorators.py       # Decoradores personalizados
│   │   └── constants.py        # Constantes del sistema
│   │
│   └── socketio_events.py      # Eventos WebSocket (notificaciones)
│
├── migrations/                  # Migraciones de base de datos (Alembic)
│   └── versions/               # Versiones de migración
│
├── tests/                       # Tests unitarios y de integración
│
├── scripts/                     # Scripts auxiliares
│
├── run.py                       # Punto de entrada de la aplicación
├── gunicorn_config.py          # Configuración de Gunicorn
├── requirements.txt            # Dependencias Python
├── .env.example                # Ejemplo de variables de entorno
├── Procfile                    # Para despliegue en Render/Heroku
├── render.yaml                 # Configuración de Render
└── runtime.txt                 # Versión de Python (3.11.6)
```

### 2.3 Descripción de Componentes Clave

#### 2.3.1 **Rutas (Routes / Blueprints)**

Las rutas están organizadas por módulos funcionales utilizando Flask Blueprints. Cada blueprint agrupa endpoints relacionados.

**Ejemplo de estructura de blueprint:**

```python
# app/routes/clients.py
from flask import Blueprint, request, jsonify
from app.services.client_service import ClientService

clients_bp = Blueprint('clients', __name__)

@clients_bp.route('/api/list')
@login_required
def list_clients():
    clients = ClientService.get_all_clients()
    return jsonify({'success': True, 'data': clients})
```

**Blueprints registrados:**

- `/` → `auth_bp` (Login, logout)
- `/dashboard` → `dashboard_bp`
- `/users` → `users_bp`
- `/clients` → `clients_bp`
- `/operations` → `operations_bp`
- `/position` → `position_bp`
- `/compliance` → `compliance_bp`

#### 2.3.2 **Servicios (Services)**

Los servicios contienen la lógica de negocio y están separados de las rutas para facilitar:
- Reutilización de código
- Testing
- Mantenimiento

**Principio:** Las rutas delegan la lógica compleja a los servicios.

```python
# app/services/client_service.py
class ClientService:
    @staticmethod
    def create_client(data, current_user):
        # Validación de datos
        # Lógica de negocio
        # Interacción con modelos
        # Retorno de resultados
        pass
```

#### 2.3.3 **Modelos (Models)**

Los modelos definen la estructura de la base de datos usando SQLAlchemy ORM. Cada modelo representa una tabla.

**Características:**
- Relaciones entre tablas (ForeignKey, backref)
- Validaciones a nivel de modelo
- Métodos auxiliares (to_dict, etc.)
- Constraints de base de datos

#### 2.3.4 **Extensiones (Extensions)**

Archivo `app/extensions.py` centraliza las extensiones de Flask:

```python
db = SQLAlchemy()           # ORM
migrate = Migrate()         # Migraciones
login_manager = LoginManager()  # Autenticación
csrf = CSRFProtect()        # Protección CSRF
socketio = SocketIO()       # WebSocket
mail = Mail()               # Correo electrónico
limiter = Limiter()         # Rate limiting
```

---

## 3. Estructura de Base de Datos

### 3.1 Tablas Principales

#### **users** - Usuarios del Sistema
| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | INTEGER | PK |
| username | VARCHAR(100) | Nombre de usuario único |
| email | VARCHAR(120) | Email único |
| password_hash | VARCHAR(200) | Contraseña hasheada |
| dni | VARCHAR(8) | DNI único |
| role | VARCHAR(20) | Master, Trader, Operador, Middle Office |
| status | VARCHAR(20) | Activo, Inactivo |
| created_at | TIMESTAMP | Fecha de creación |
| last_login | TIMESTAMP | Último acceso |

#### **clients** - Clientes
| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | INTEGER | PK |
| document_type | VARCHAR(10) | DNI, CE, RUC |
| apellido_paterno | VARCHAR(100) | Para personas naturales |
| apellido_materno | VARCHAR(100) | Para personas naturales |
| nombres | VARCHAR(100) | Para personas naturales |
| razon_social | VARCHAR(200) | Para empresas (RUC) |
| dni | VARCHAR(20) | Número de documento (único) |
| email | VARCHAR(120) | Email único |
| phone | VARCHAR(100) | Teléfono(s) |
| dni_front_url | VARCHAR(500) | URL documento frontal |
| dni_back_url | VARCHAR(500) | URL documento reverso |
| bank_accounts_json | TEXT | Cuentas bancarias (JSON) |
| status | VARCHAR(20) | Activo, Inactivo |
| created_by | INTEGER | FK → users.id |
| created_at | TIMESTAMP | Fecha de registro |

#### **operations** - Operaciones Cambiarias
| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | INTEGER | PK |
| operation_id | VARCHAR(50) | EXP-1001, EXP-1002, etc. |
| client_id | INTEGER | FK → clients.id |
| user_id | INTEGER | FK → users.id (trader) |
| assigned_operator_id | INTEGER | FK → users.id (operador) |
| operation_type | VARCHAR(20) | Compra, Venta |
| amount_usd | NUMERIC(15,2) | Monto en USD |
| exchange_rate | NUMERIC(10,4) | Tipo de cambio |
| amount_pen | NUMERIC(15,2) | Monto en PEN |
| client_deposits_json | TEXT | Abonos del cliente (JSON) |
| operator_proofs_json | TEXT | Comprobantes del operador (JSON) |
| status | VARCHAR(20) | Pendiente, En proceso, Completada |
| notes | TEXT | Notas/comentarios |
| created_at | TIMESTAMP | Fecha de creación |
| completed_at | TIMESTAMP | Fecha de completado |

#### **client_risk_profiles** - Perfiles de Riesgo (Compliance)
| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | INTEGER | PK |
| client_id | INTEGER | FK → clients.id |
| risk_score | INTEGER | Puntaje de riesgo (0-100) |
| kyc_status | VARCHAR(20) | Pendiente, Aprobado, Rechazado |
| is_pep | BOOLEAN | Persona expuesta políticamente |
| in_restrictive_lists | BOOLEAN | En listas restrictivas |
| dd_level | VARCHAR(20) | Nivel de debida diligencia |
| kyc_verified_at | TIMESTAMP | Fecha de verificación |
| kyc_verified_by | INTEGER | FK → users.id |

#### **compliance_alerts** - Alertas de Compliance
| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | INTEGER | PK |
| alert_type | VARCHAR(50) | Tipo de alerta |
| severity | VARCHAR(20) | Baja, Media, Alta, Crítica |
| client_id | INTEGER | FK → clients.id |
| operation_id | INTEGER | FK → operations.id (opcional) |
| title | VARCHAR(200) | Título de la alerta |
| description | TEXT | Descripción detallada |
| status | VARCHAR(20) | Nueva, En revisión, Resuelta |
| created_at | TIMESTAMP | Fecha de generación |

#### **audit_logs** - Logs de Auditoría
| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | INTEGER | PK |
| user_id | INTEGER | FK → users.id |
| action | VARCHAR(100) | Acción realizada |
| entity_type | VARCHAR(50) | Tipo de entidad afectada |
| entity_id | INTEGER | ID de la entidad |
| changes | TEXT | JSON con cambios realizados |
| ip_address | VARCHAR(45) | IP del usuario |
| created_at | TIMESTAMP | Fecha del evento |

### 3.2 Relaciones Principales

```
users (1) ----< (N) operations
users (1) ----< (N) clients [created_by]
clients (1) ----< (N) operations
clients (1) ---- (1) client_risk_profiles
operations (N) ----> (1) users [assigned_operator_id]
clients (1) ----< (N) compliance_alerts
operations (1) ----< (N) compliance_alerts
```

### 3.3 Migraciones

El sistema utiliza **Flask-Migrate** (Alembic) para gestionar cambios en el esquema de base de datos.

**Comandos útiles:**
```bash
flask db migrate -m "Descripción del cambio"  # Crear migración
flask db upgrade                              # Aplicar migraciones
flask db downgrade                            # Revertir migración
```

Las migraciones están en: `migrations/versions/`

---

## 4. Configuración y Variables de Entorno

### 4.1 Archivo `.env`

El sistema requiere un archivo `.env` en la raíz del proyecto con las siguientes variables:

```bash
# Base de datos
DATABASE_URL=postgresql://usuario:password@host:5432/nombre_db

# Flask
SECRET_KEY=clave-secreta-muy-segura
FLASK_ENV=production  # o development

# Cloudinary (almacenamiento de archivos)
CLOUDINARY_CLOUD_NAME=tu-cloud-name
CLOUDINARY_API_KEY=tu-api-key
CLOUDINARY_API_SECRET=tu-api-secret

# Email SMTP (notificaciones)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=tu-email@dominio.com
MAIL_PASSWORD=tu-password-app

# Email de confirmación (operaciones completadas)
MAIL_CONFIRMATION_USERNAME=confirmaciones@dominio.com
MAIL_CONFIRMATION_PASSWORD=password
MAIL_CONFIRMATION_SENDER=confirmaciones@dominio.com

# Seguridad
RATELIMIT_ENABLED=True
LOG_LEVEL=INFO
```

### 4.2 Configuraciones por Entorno

El archivo `app/config.py` define tres configuraciones:

- **DevelopmentConfig**: Para desarrollo local
- **ProductionConfig**: Para producción (usa variables de entorno)
- **TestingConfig**: Para pruebas

---

## 5. Integración con Amazon Web Services (AWS)

### 5.1 Servicios AWS Recomendados

| Servicio AWS | Propósito | Configuración Necesaria |
|--------------|-----------|-------------------------|
| **EC2** o **Elastic Beanstalk** | Hosting del backend Flask | Instancia t3.medium o superior, Python 3.11+ |
| **RDS (PostgreSQL)** | Base de datos gestionada | PostgreSQL 14+, mínimo db.t3.micro |
| **S3** | Almacenamiento de archivos* | Bucket privado con políticas de acceso |
| **Secrets Manager** | Almacenamiento de credenciales | Guardar DATABASE_URL, API keys |
| **CloudWatch** | Logs y monitoreo | Configurar logs de la aplicación |
| **ALB (Application Load Balancer)** | Balanceo de carga | Si se requiere alta disponibilidad |
| **Route 53** | DNS y dominio | Configurar dominio personalizado |
| **IAM** | Control de acceso | Crear roles para EC2/EB con acceso a RDS, S3, Secrets Manager |

**Nota:** El sistema actualmente usa **Cloudinary** para archivos. Se puede migrar a **S3** si se requiere.

### 5.2 Arquitectura AWS Propuesta

```
Internet
    ↓
Route 53 (DNS: qoricash.com)
    ↓
Application Load Balancer (ALB)
    ↓
Elastic Beanstalk / EC2 (Flask App)
    ↓                    ↓
RDS PostgreSQL      S3 / Cloudinary
    ↓
CloudWatch Logs
```

### 5.3 Pasos para Migrar el Backend a AWS

#### Paso 1: Configurar RDS PostgreSQL

1. Crear instancia de RDS PostgreSQL (versión 14 o superior)
2. Configurar Security Group para permitir conexiones desde EC2/EB
3. Crear base de datos inicial:
   ```sql
   CREATE DATABASE qoricash_trading;
   ```
4. Obtener endpoint de conexión (ej: `db.xxxxx.us-east-1.rds.amazonaws.com`)

#### Paso 2: Configurar Secrets Manager

1. Crear un secreto en AWS Secrets Manager con nombre `qoricash/production`
2. Almacenar en formato JSON:
   ```json
   {
     "DATABASE_URL": "postgresql://user:pass@rds-endpoint:5432/qoricash_trading",
     "SECRET_KEY": "clave-secreta",
     "CLOUDINARY_API_SECRET": "...",
     "MAIL_PASSWORD": "...",
     "MAIL_CONFIRMATION_PASSWORD": "..."
   }
   ```

#### Paso 3: Desplegar en Elastic Beanstalk o EC2

**Opción A: Elastic Beanstalk (Recomendado para simplicidad)**

1. Instalar EB CLI: `pip install awsebcli`
2. Inicializar aplicación:
   ```bash
   eb init -p python-3.11 qoricash-trading --region us-east-1
   ```
3. Crear entorno:
   ```bash
   eb create qoricash-prod --database
   ```
4. Configurar variables de entorno en EB (desde Secrets Manager):
   ```bash
   eb setenv DATABASE_URL=valor SECRET_KEY=valor
   ```
5. Desplegar:
   ```bash
   eb deploy
   ```

**Opción B: EC2 Manual**

1. Lanzar instancia EC2 (Amazon Linux 2023, t3.medium)
2. Instalar dependencias:
   ```bash
   sudo yum update -y
   sudo yum install python3.11 python3-pip git postgresql15 -y
   ```
3. Clonar repositorio:
   ```bash
   git clone https://github.com/ggarciaperion/qoricash.git
   cd qoricash
   ```
4. Crear entorno virtual e instalar dependencias:
   ```bash
   python3.11 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
5. Configurar `.env` con credenciales de AWS Secrets Manager
6. Ejecutar migraciones:
   ```bash
   flask db upgrade
   ```
7. Configurar Gunicorn como servicio systemd:
   ```bash
   sudo nano /etc/systemd/system/qoricash.service
   ```
   Contenido:
   ```ini
   [Unit]
   Description=QoriCash Trading Application
   After=network.target

   [Service]
   User=ec2-user
   WorkingDirectory=/home/ec2-user/qoricash
   Environment="PATH=/home/ec2-user/qoricash/venv/bin"
   ExecStart=/home/ec2-user/qoricash/venv/bin/gunicorn -c gunicorn_config.py run:app

   [Install]
   WantedBy=multi-user.target
   ```
8. Iniciar servicio:
   ```bash
   sudo systemctl start qoricash
   sudo systemctl enable qoricash
   ```

#### Paso 4: Configurar ALB (Opcional pero recomendado)

1. Crear Application Load Balancer
2. Crear Target Group apuntando a la instancia EC2/EB
3. Configurar Health Check: `/health` (el sistema ya tiene este endpoint)
4. Configurar listeners HTTP (80) y HTTPS (443) con certificado SSL

#### Paso 5: Configurar CloudWatch Logs

1. Instalar agente de CloudWatch en EC2:
   ```bash
   sudo yum install amazon-cloudwatch-agent
   ```
2. Configurar para enviar logs de la aplicación

### 5.4 Consideraciones de Seguridad en AWS

- **Security Groups**: Restringir acceso a RDS solo desde EC2/EB
- **IAM Roles**: No usar credenciales hardcoded, usar IAM Roles
- **SSL/TLS**: Forzar HTTPS en ALB
- **Secrets Manager**: Rotar credenciales periódicamente
- **VPC**: Desplegar RDS en subnet privada

---

## 6. Integración con Sistema Externo

El sistema QoriCash puede integrarse con otro sistema de dos formas:

### 6.1 Opción Recomendada: API REST

Exponer endpoints RESTful para consultas y sincronización.

#### Endpoints Sugeridos para Integración

**Autenticación:**
- `POST /api/auth/token` - Obtener token JWT para autenticación

**Clientes:**
- `GET /api/clients` - Listar clientes
- `GET /api/clients/<id>` - Obtener cliente por ID
- `POST /api/clients` - Crear cliente
- `PUT /api/clients/<id>` - Actualizar cliente

**Operaciones:**
- `GET /api/operations` - Listar operaciones
- `GET /api/operations/<id>` - Obtener operación por ID
- `POST /api/operations` - Crear operación
- `PUT /api/operations/<id>` - Actualizar operación

**Consultas:**
- `GET /api/dashboard/stats` - Estadísticas del día
- `GET /api/position/balances` - Saldos bancarios

#### Implementación Sugerida

El sistema actual tiene endpoints existentes en `/api/*`. Para integración externa:

1. **Crear un módulo de API externa:**
   ```python
   # app/routes/external_api.py
   from flask import Blueprint, request, jsonify
   from functools import wraps

   external_api_bp = Blueprint('external_api', __name__)

   def require_api_key(f):
       @wraps(f)
       def decorated(*args, **kwargs):
           api_key = request.headers.get('X-API-Key')
           if api_key != os.getenv('EXTERNAL_API_KEY'):
               return jsonify({'error': 'Unauthorized'}), 401
           return f(*args, **kwargs)
       return decorated

   @external_api_bp.route('/external/clients', methods=['GET'])
   @require_api_key
   def get_clients():
       # Lógica para devolver clientes
       pass
   ```

2. **Autenticación por API Key:**
   - Generar API Key única para el sistema externo
   - Almacenar en Secrets Manager
   - Validar en cada petición

3. **Rate Limiting:**
   - Aplicar límites de peticiones por minuto
   - El sistema ya tiene Flask-Limiter configurado

#### Ejemplo de Consumo desde Sistema Externo

```python
import requests

API_URL = "https://qoricash.aws.com/external/clients"
API_KEY = "tu-api-key-secreta"

headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

response = requests.get(API_URL, headers=headers)
clients = response.json()
```

### 6.2 Opción Alternativa: Conexión Directa a Base de Datos

Si ambos sistemas comparten la misma base de datos PostgreSQL:

#### Ventajas:
- Sincronización en tiempo real
- Sin necesidad de APIs intermedias

#### Desventajas:
- Acoplamiento fuerte
- Riesgo de corrupción de datos
- Dificultad para aplicar lógica de negocio

#### Recomendaciones si se usa esta opción:

1. **Vistas de Base de Datos:**
   Crear vistas SQL específicas para el sistema externo:
   ```sql
   CREATE VIEW external_clients_view AS
   SELECT id, dni, email, status, created_at
   FROM clients
   WHERE status = 'Activo';
   ```

2. **Usuario de BD con Permisos Limitados:**
   ```sql
   CREATE USER external_system WITH PASSWORD 'password';
   GRANT SELECT ON external_clients_view TO external_system;
   GRANT SELECT, INSERT ON operations TO external_system;
   ```

3. **Triggers para Sincronización:**
   Si el sistema externo modifica datos, implementar triggers para mantener integridad.

4. **Esquema Separado (Opcional):**
   Crear un esquema específico para integración:
   ```sql
   CREATE SCHEMA external_api;
   CREATE TABLE external_api.sync_log (...);
   ```

---

## 7. Recomendaciones Técnicas Antes de Integrar

### 7.1 Estandarización de Endpoints

- [ ] Definir estándar de respuestas JSON:
  ```json
  {
    "success": true,
    "data": {...},
    "message": "Operación exitosa",
    "errors": []
  }
  ```

- [ ] Documentar todos los endpoints con Swagger/OpenAPI

- [ ] Versionado de API: `/api/v1/clients`, `/api/v2/clients`

### 7.2 Variables de Entorno

- [ ] Crear archivo `.env.example` completo con todas las variables requeridas
- [ ] Documentar cada variable de entorno
- [ ] Usar AWS Secrets Manager para producción

### 7.3 Logging y Monitoreo

- [ ] Implementar logs estructurados (formato JSON):
  ```python
  logger.info("Operation created", extra={
      "operation_id": op.operation_id,
      "client_id": op.client_id,
      "amount_usd": float(op.amount_usd)
  })
  ```

- [ ] Configurar envío de logs a CloudWatch
- [ ] Definir métricas clave para monitorear:
  - Tiempo de respuesta de endpoints
  - Tasa de errores
  - Operaciones creadas por hora

### 7.4 Seguridad

- [ ] Implementar autenticación JWT para APIs externas
- [ ] Configurar CORS apropiadamente
- [ ] Sanitizar todas las entradas de usuario
- [ ] Implementar protección contra SQL Injection (ORM SQLAlchemy ya lo hace)
- [ ] Habilitar HTTPS obligatorio en producción
- [ ] Configurar Content Security Policy (CSP)

### 7.5 Base de Datos

- [ ] Crear índices en columnas frecuentemente consultadas:
  ```sql
  CREATE INDEX idx_operations_client_id ON operations(client_id);
  CREATE INDEX idx_operations_status ON operations(status);
  CREATE INDEX idx_operations_created_at ON operations(created_at);
  ```

- [ ] Configurar backups automáticos en RDS
- [ ] Planificar estrategia de archivado de datos históricos

### 7.6 Testing

- [ ] Implementar tests de integración para endpoints críticos
- [ ] Crear suite de tests automatizados con pytest:
  ```bash
  pytest tests/
  ```

### 7.7 Documentación

- [ ] Documentar modelo de datos con diagramas ER
- [ ] Crear guía de despliegue paso a paso
- [ ] Documentar proceso de rollback en caso de fallo
- [ ] Crear runbook de operaciones (troubleshooting común)

### 7.8 Normalización de Datos

Antes de la integración, revisar y normalizar:

- [ ] **Clientes:** Verificar duplicados por DNI/email
- [ ] **Operaciones:** Asegurar integridad referencial
- [ ] **Campos JSON:** Validar estructura consistente en:
  - `bank_accounts_json`
  - `client_deposits_json`
  - `operator_proofs_json`

---

## 8. Checklist de Integración AWS

### Pre-Deploy
- [ ] Configurar cuenta AWS con permisos IAM necesarios
- [ ] Crear RDS PostgreSQL con backup automático
- [ ] Configurar Secrets Manager con credenciales
- [ ] Crear bucket S3 (si se migra desde Cloudinary)
- [ ] Configurar VPC con subnets públicas y privadas

### Deploy
- [ ] Desplegar backend en EC2 o Elastic Beanstalk
- [ ] Ejecutar migraciones: `flask db upgrade`
- [ ] Crear usuario Master inicial:
  ```bash
  python create_master_user.py
  ```
- [ ] Verificar endpoint de salud: `GET /health`
- [ ] Configurar ALB con certificado SSL
- [ ] Apuntar dominio en Route 53

### Post-Deploy
- [ ] Verificar logs en CloudWatch
- [ ] Ejecutar tests de smoke en producción
- [ ] Configurar alertas de CloudWatch para errores críticos
- [ ] Implementar monitoreo de performance (APM)
- [ ] Documentar URLs de producción y credenciales de acceso

### Integración con Sistema Externo
- [ ] Generar y compartir API Key
- [ ] Documentar endpoints disponibles
- [ ] Configurar rate limiting específico
- [ ] Establecer SLA de disponibilidad
- [ ] Crear canal de comunicación para issues técnicos

---

## 9. Información de Contacto y Soporte

### Repositorio
- **GitHub:** https://github.com/ggarciaperion/qoricash
- **Branch principal:** `master`
- **Commits recientes:** Incluyen optimizaciones de correos y compliance

### Despliegue Actual
- **Plataforma:** Render.com
- **URL:** Configurada en variables de entorno
- **Deploy automático:** Activado en push a master

### Credenciales y Accesos
Todas las credenciales deben obtenerse de:
- AWS Secrets Manager: `qoricash/production`
- Variables de entorno en servidor de producción

---

## 10. Cierre

El sistema **QoriCash Trading V2** ha sido diseñado con una arquitectura modular, escalable y mantenible. La separación clara entre rutas, servicios y modelos facilita la comprensión del flujo de datos y la implementación de nuevas funcionalidades.

La estructura actual está preparada para:
- Integración con servicios cloud (AWS)
- Conexión con sistemas externos mediante APIs REST
- Escalamiento horizontal y vertical
- Implementación de mejoras continuas

El código está documentado internamente y sigue las mejores prácticas de desarrollo con Flask y SQLAlchemy. Cualquier optimización, refactorización o mejora que considere necesaria será bienvenida y puede ser implementada sin afectar la funcionalidad existente.

---

**Nota Final:** Este documento es una guía técnica para facilitar la integración. Para detalles específicos de implementación, consultar el código fuente en el repositorio de GitHub. Para preguntas técnicas adicionales, el código está comentado y estructurado de forma clara para facilitar su comprensión.

---

**Fecha de Documento:** Diciembre 2024
**Versión del Sistema:** QoriCash Trading V2
**Python:** 3.11.6
**Flask:** 3.0.0
**PostgreSQL:** 12+
