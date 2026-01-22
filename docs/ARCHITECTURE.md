# Arquitectura del Sistema - QoriCash Trading V2

> Documentación completa de la arquitectura del sistema de casa de cambio online
>
> **Última actualización**: 22 de enero de 2026

---

## Tabla de Contenidos

1. [Resumen Ejecutivo](#resumen-ejecutivo)
2. [Stack Tecnológico](#stack-tecnológico)
3. [Componentes del Sistema](#componentes-del-sistema)
4. [Arquitectura de Backend](#arquitectura-de-backend)
5. [Frontend Web](#frontend-web)
6. [Flujos Principales](#flujos-principales)
7. [Integraciones](#integraciones)
8. [Seguridad](#seguridad)
9. [Escalabilidad](#escalabilidad)

---

## Resumen Ejecutivo

QoriCash Trading V2 es una **plataforma integral de casa de cambio online** que permite a usuarios realizar operaciones de compra y venta de divisas (USD/PEN) a través de múltiples canales:

- **Página Web Pública** (qoricash.vercel.app)
- **App Móvil** (React Native/Expo)
- **Sistema Web Interno** (app.qoricash.pe) - Panel administrativo para Traders y Operadores

### Características Principales

- ✅ Registro y autenticación de clientes
- ✅ Operaciones de cambio de divisas (Compra/Venta)
- ✅ Sistema de referidos con recompensas (Pips)
- ✅ Facturación electrónica (NubeFact/SUNAT)
- ✅ Compliance AML/KYC/PLAFT integrado
- ✅ Notificaciones en tiempo real (Socket.IO)
- ✅ Múltiples cuentas bancarias por cliente
- ✅ Gestión de límites de operaciones
- ✅ Auditoría completa de todas las acciones
- ✅ Panel administrativo multi-rol

---

## Stack Tecnológico

### Backend
```
- Framework: Flask 3.x (Python)
- Base de Datos: PostgreSQL 14+
- ORM: SQLAlchemy 2.x
- Real-time: Socket.IO + Eventlet
- Migraciones: Alembic
- Autenticación: Flask-Login
- Validación: Marshmallow
- WSGI Server: Gunicorn (producción)
```

### Frontend Web
```
- Framework: Next.js 15.1.3 (App Router)
- UI Library: React 19
- Lenguaje: TypeScript 5
- Estilos: Tailwind CSS 3.4
- State Management: Zustand 5
- HTTP Client: Axios
- Formularios: React Hook Form + Zod
- Real-time: Socket.IO Client
```

### Infraestructura
```
- Hosting Backend: Render (PostgreSQL + Web Service)
- Hosting Frontend: Vercel
- File Storage: Cloudinary
- Email: SMTP (Gmail)
- Facturación: NubeFact API
- Compliance: Inspektor API
```

---

## Componentes del Sistema

```
┌─────────────────────────────────────────────────────────────────┐
│                         USUARIOS FINALES                         │
├─────────────────┬─────────────────┬──────────────────────────────┤
│   Página Web    │    App Móvil    │      Sistema Web Interno     │
│  (Next.js 15)   │ (React Native)  │    (Flask Templates)         │
└────────┬────────┴────────┬────────┴──────────────┬───────────────┘
         │                 │                       │
         └─────────────────┼───────────────────────┘
                           │
                           ▼
         ┌─────────────────────────────────────────────┐
         │         API BACKEND (Flask)                 │
         ├─────────────────────────────────────────────┤
         │  • REST API (/api/web, /api/platform)      │
         │  • WebSocket (Socket.IO)                    │
         │  • Autenticación (Flask-Login)              │
         │  • Rate Limiting                            │
         │  • CORS                                     │
         └────────────┬────────────────────────────────┘
                      │
         ┌────────────┴────────────────────────────┐
         │                                         │
         ▼                                         ▼
┌──────────────────┐                    ┌──────────────────┐
│   PostgreSQL     │                    │  Servicios de    │
│   (Database)     │                    │  Terceros        │
├──────────────────┤                    ├──────────────────┤
│ • Clientes       │                    │ • Cloudinary     │
│ • Operaciones    │                    │ • NubeFact       │
│ • Usuarios       │                    │ • Inspektor      │
│ • Facturas       │                    │ • SMTP/Email     │
│ • Compliance     │                    │                  │
└──────────────────┘                    └──────────────────┘
```

---

## Arquitectura de Backend

### Estructura de Directorios

```
Qoricashtrading/
├── app/
│   ├── __init__.py              # Factory de aplicación
│   ├── config.py                # Configuración multi-ambiente
│   ├── extensions.py            # Inicialización de extensiones
│   ├── socketio_events.py       # Eventos Socket.IO
│   │
│   ├── models/                  # Modelos SQLAlchemy (14 archivos)
│   │   ├── user.py              # Usuarios del sistema
│   │   ├── client.py            # Clientes
│   │   ├── operation.py         # Operaciones
│   │   ├── invoice.py           # Facturas
│   │   ├── compliance.py        # Compliance (8 modelos)
│   │   ├── reward_code.py       # Códigos de recompensa
│   │   ├── exchange_rate.py     # Tipos de cambio
│   │   ├── bank_balance.py      # Saldos bancarios
│   │   ├── trader_goal.py       # Metas de traders
│   │   ├── trader_daily_profit.py
│   │   ├── accounting_batch.py  # Lotes de neteo
│   │   ├── accounting_match.py  # Matching compra/venta
│   │   └── audit_log.py         # Auditoría
│   │
│   ├── routes/                  # Blueprints (14 módulos)
│   │   ├── auth.py              # Autenticación sistema
│   │   ├── client_auth.py       # Autenticación clientes
│   │   ├── dashboard.py         # Dashboard principal
│   │   ├── clients.py           # CRUD clientes
│   │   ├── operations.py        # CRUD operaciones
│   │   ├── web_api.py           # API página web
│   │   ├── platform_api.py      # API app móvil
│   │   ├── compliance.py        # Módulo compliance
│   │   ├── referrals.py         # Sistema de referidos
│   │   ├── accounting.py        # Contabilidad
│   │   ├── position.py          # Posiciones abiertas
│   │   ├── users.py             # Gestión de usuarios
│   │   ├── legal.py             # Términos, privacidad
│   │   └── platform.py          # Endpoints plataforma
│   │
│   ├── services/                # Lógica de negocio (16 servicios)
│   │   ├── auth_service.py
│   │   ├── client_service.py
│   │   ├── operation_service.py
│   │   ├── invoice_service.py   # NubeFact integration
│   │   ├── email_service.py     # Envío de correos
│   │   ├── file_service.py      # Cloudinary
│   │   ├── compliance_service.py
│   │   ├── referral_service.py
│   │   ├── accounting_service.py
│   │   ├── notification_service.py
│   │   ├── push_notification_service.py
│   │   ├── operation_expiry_service.py  # Auto-cancelación
│   │   ├── scheduler_service.py
│   │   └── inspektor_service.py
│   │
│   ├── schemas/                 # Validación Marshmallow
│   ├── utils/                   # Utilidades
│   ├── templates/               # Plantillas Jinja2
│   └── static/                  # Archivos estáticos
│
├── migrations/                  # Migraciones Alembic
├── scripts/                     # Scripts de mantenimiento
│   └── clean_database.py        # Limpieza de BD
├── docs/                        # Documentación
├── run.py                       # Entry point
├── requirements.txt
└── gunicorn_config.py
```

### Modelos de Base de Datos (Principales)

#### **Client** (Clientes)
```python
- Campos de identificación: dni, email, phone, document_type
- Información personal/empresa
- Documentos KYC (Cloudinary URLs)
- Cuentas bancarias (JSON array, múltiples)
- Sistema de referidos: referral_code, used_referral_code, referred_by
- Beneficios: referral_pips_earned, referral_pips_available
- Autenticación: password_hash, requires_password_change
```

#### **Operation** (Operaciones)
```python
- operation_id: EXP-1001, EXP-1002, etc.
- tipo: Compra/Venta
- origen: sistema, plataforma, app, web
- montos: amount_usd, exchange_rate, amount_pen
- estado: Pendiente, En proceso, Completada, Cancelado, Expirada
- comprobantes: client_deposits_json, client_payments_json, operator_proofs_json
- timestamps: created_at, in_process_since, completed_at
```

#### **Invoice** (Facturas Electrónicas)
```python
- Datos emisor (QoriCash SAC)
- Datos cliente
- NubeFact: nubefact_enlace_pdf, nubefact_enlace_xml
- SUNAT: nubefact_aceptada_por_sunat
- status: Pendiente, Enviado, Aceptado, Rechazado
```

#### **Compliance** (8 modelos)
```python
- RiskLevel: Niveles de riesgo (Bajo, Medio, Alto, Crítico)
- ClientRiskProfile: Perfil de riesgo + KYC status
- ComplianceRule: Reglas de detección
- ComplianceAlert: Alertas generadas
- RestrictiveListCheck: OFAC, ONU, UIF, PEP, Interpol
- TransactionMonitoring: Patrones sospechosos
- ComplianceDocument: Reportes UIF, Due Diligence
- ComplianceAudit: Auditoría de acciones
```

### Relaciones (Foreign Keys)

```
User (1) ──┬──> (N) Operation [user_id]
           └──> (N) Operation [assigned_operator_id]
           └──> (N) AuditLog

Client (1) ──┬──> (N) Operation
             ├──> (N) Invoice
             ├──> (N) RewardCode
             ├──> (1) ClientRiskProfile
             ├──> (N) ComplianceAlert
             ├──> (N) RestrictiveListCheck
             └──> (1) Client [referred_by - self-referential]

Operation (1) ──┬──> (N) Invoice
                ├──> (N) ComplianceAlert
                ├──> (1) TransactionMonitoring
                └──> (N) ComplianceDocument
```

---

## Frontend Web

### Estructura Next.js

```
qoricash-web/
├── app/                          # App Router (Next.js 15)
│   ├── page.tsx                  # Landing page
│   ├── login/page.tsx
│   ├── crear-cuenta/page.tsx
│   ├── dashboard/
│   │   ├── page.tsx              # Dashboard principal
│   │   ├── nueva-operacion/page.tsx
│   │   ├── agregar-cuenta/page.tsx
│   │   └── promociones/
│   ├── perfil/page.tsx
│   └── api/route.ts              # API routes
│
├── components/
│   ├── DashboardLayout.tsx
│   ├── AuthProvider.tsx
│   ├── Calculator.tsx
│   ├── ReferralBenefits.tsx
│   └── modals/
│
├── lib/
│   ├── api.ts                    # Axios instance
│   ├── types.ts                  # TypeScript interfaces
│   ├── api/
│   │   ├── auth.ts
│   │   ├── operations.ts
│   │   └── banks.ts
│   ├── services/
│   │   ├── authService.ts
│   │   ├── operationService.ts
│   │   └── socketService.ts
│   ├── store/
│   │   ├── useAuth.ts            # Zustand store
│   │   ├── exchangeStore.ts
│   │   └── referralStore.ts
│   └── hooks/
│       └── useSocket.ts
│
└── public/                       # Static assets
```

### State Management (Zustand)

```typescript
// Auth Store
interface AuthStore {
  client: Client | null
  isAuthenticated: boolean
  requiresPasswordChange: boolean
  login(dni: string, password: string): Promise<void>
  logout(): void
  changePassword(oldPassword: string, newPassword: string): Promise<void>
}

// Exchange Rate Store
interface ExchangeStore {
  buyRate: number
  sellRate: number
  updateRates(): Promise<void>
}

// Referral Store
interface ReferralStore {
  referralCode: string
  referralBenefits: ReferralBenefit[]
  redeemPips(): Promise<void>
}
```

---

## Flujos Principales

### 1. Registro de Cliente

```
┌──────────────┐
│ Cliente Web  │
│   o Móvil    │
└──────┬───────┘
       │
       │ POST /api/web/register
       │ {dni, email, nombres, password, ...}
       ▼
┌─────────────────────┐
│  Backend Validation │
├─────────────────────┤
│ • Validar DNI único │
│ • Validar email     │
│ • Hash password     │
│ • Generar referral  │
│   code (6 chars)    │
└──────┬──────────────┘
       │
       │ Guardar en DB
       ▼
┌─────────────────────┐
│   Client creado     │
│ Status: Inactivo    │
└──────┬──────────────┘
       │
       │ Enviar email
       │ de bienvenida
       ▼
┌─────────────────────┐
│ Email: "Bienvenido  │
│ a QoriCash"         │
└─────────────────────┘
```

### 2. Crear Operación

```
┌──────────────┐
│ Cliente      │
└──────┬───────┘
       │ Selecciona tipo (Compra/Venta)
       │ Ingresa monto USD
       │ Selecciona cuentas bancarias
       ▼
┌─────────────────────┐
│  Validaciones       │
├─────────────────────┤
│ • Verificar límites │
│   ($1000 sin docs)  │
│ • Validar cuentas   │
│ • Calcular monto PEN│
│   (usando exchange  │
│   rate)             │
└──────┬──────────────┘
       │
       │ POST /api/web/create-operation
       ▼
┌─────────────────────┐
│ Operation creada    │
│ Status: Pendiente   │
│ operation_id:       │
│   EXP-XXXX          │
└──────┬──────────────┘
       │
       ├─────────────────┬─────────────────┐
       │                 │                 │
       ▼                 ▼                 ▼
  Email Cliente    Notif Socket.IO   Email Traders
  + Push Notif     (real-time)       + Operadores
```

### 3. Completar Operación (Trader → Operador → Cliente)

```
PASO 1: TRADER (Estado: Pendiente)
┌─────────────────────┐
│ Trader edita        │
│ operación           │
├─────────────────────┤
│ • Sube comprobante  │
│   del cliente       │
│ • Ingresa código    │
│   de operación      │
│ • Selecciona cuenta │
│   de cargo          │
│ • Llena abonos      │
└──────┬──────────────┘
       │
       │ Cambia a "En proceso"
       │ Asigna a Operador
       ▼

PASO 2: OPERADOR (Estado: En proceso)
┌─────────────────────┐
│ Operador procesa    │
├─────────────────────┤
│ • Ve abonos cliente │
│ • Registra pagos    │
│   al cliente        │
│ • Sube comprobantes │
│   (máx 4)           │
│ • Agrega comentarios│
└──────┬──────────────┘
       │
       │ Click "Finalizar Operación"
       ▼
┌─────────────────────┐
│ Cambio a Completada │
├─────────────────────┤
│ • completed_at      │
│ • Generar factura   │
│   (NubeFact)        │
│ • Calcular pips     │
│   (referidos)       │
└──────┬──────────────┘
       │
       ├────────────┬────────────┐
       │            │            │
       ▼            ▼            ▼
  Email Cliente  Adjuntar    Actualizar
  + PDF factura  comprobante  beneficios
                              referidos
```

### 4. Sistema de Referidos

```
CLIENTE PADRINO (A)
┌─────────────────────┐
│ Tiene código:       │
│ ABC123              │
└─────────────────────┘
       │
       │ Comparte código
       ▼
NUEVO CLIENTE (B)
┌─────────────────────┐
│ Usa código: ABC123  │
│ al registrarse      │
└──────┬──────────────┘
       │
       │ Sistema guarda:
       │ B.used_referral_code = "ABC123"
       │ B.referred_by = A.id
       ▼
┌─────────────────────┐
│ Por cada operación  │
│ completada de B:    │
├─────────────────────┤
│ A gana 30 pips      │
│ (0.003)             │
└──────┬──────────────┘
       │
       │ A puede canjear 30 pips
       ▼
┌─────────────────────┐
│ Generar RewardCode  │
│ (6 chars único)     │
│ DEF456              │
└──────┬──────────────┘
       │
       │ Compartir con otros
       ▼
OTRO CLIENTE (C)
┌─────────────────────┐
│ Usa código: DEF456  │
│ en nueva operación  │
│ → Obtiene descuento │
└─────────────────────┘
```

---

## Integraciones

### Cloudinary (File Storage)

```python
# Carpetas organizadas por tipo
/dni/                    # Documentos de identidad
/operations/
  /payment_proofs/       # Comprobantes de clientes
  /operator_proofs/      # Comprobantes de operadores
/compliance/             # Documentos de compliance
```

**Uso en código**:
```python
from app.services.file_service import FileService

# Subir DNI frontal
url = FileService.upload_dni_front(file, client_id)

# Subir comprobante de operación
url = FileService.upload_payment_proof(file, operation_id)
```

### NubeFact (Facturación Electrónica)

**Flow**:
1. Operación completada
2. Sistema genera payload SUNAT:
   ```python
   {
     "operacion": "generar_comprobante",
     "tipo_de_comprobante": "01",  # Factura
     "serie": "F001",
     "numero": "00000123",
     "sunat_transaction": "1",
     "cliente_tipo_de_documento": "6",  # RUC
     "cliente_numero_de_documento": "20123456789",
     "cliente_denominacion": "EMPRESA SAC",
     "items": [{
       "unidad_de_medida": "ZZ",
       "codigo": "001",
       "descripcion": "Servicio de cambio de divisa",
       "cantidad": 1,
       "valor_unitario": 3500.00,
       "precio_unitario": 4130.00,
       "subtotal": 4130.00,
       "tipo_de_igv": "1",
       "igv": 630.00,
       "total": 4130.00
     }]
   }
   ```
3. POST a NubeFact API
4. NubeFact envía a SUNAT
5. Respuesta con PDF/XML URLs
6. Guardar en Invoice model
7. Adjuntar PDF a email cliente

### Inspektor (Compliance/Screening)

**Verificación automática** al registrar cliente:
- Listas OFAC (Office of Foreign Assets Control)
- Listas ONU (Consejo de Seguridad)
- UIF Perú (Unidad de Inteligencia Financiera)
- Listas PEP (Personas Expuestas Políticamente)
- Interpol

**Scoring de riesgo** basado en:
- Documentación completa
- Monto de operaciones
- Frecuencia de operaciones
- Resultados de listas restrictivas

---

## Seguridad

### Autenticación

**Sistema (Traders/Operadores)**:
- Flask-Login con sesiones server-side
- Password hashing: Werkzeug (PBKDF2)
- CSRF protection en formularios
- Session timeout: 10 minutos inactividad

**Clientes (Web/Móvil)**:
- Custom authentication (DNI + password)
- Password hashing: Werkzeug
- Token en localStorage (frontend)
- Axios interceptor para headers

### Autorización

**Decoradores por rol**:
```python
@login_required
@role_required('Master', 'Trader')
def create_operation():
    # Solo Master y Trader pueden crear operaciones
    pass
```

**Roles del sistema**:
- **Master**: Acceso total
- **Trader**: Crear/editar operaciones en estado Pendiente
- **Operador**: Procesar/finalizar operaciones en estado En proceso
- **Middle Office**: Revisión KYC/Compliance

### Rate Limiting

```python
# Login: 5 intentos por minuto
@limiter.limit("5 per minute")
def login():
    pass

# API general: 200/día, 50/hora
@limiter.limit("200 per day; 50 per hour")
def api_endpoint():
    pass
```

### CORS

```python
CORS(app, origins=[
    'http://localhost:3000',           # Dev web
    'https://qoricash.vercel.app',     # Prod web
    'http://localhost:8081',           # Dev móvil
    'https://app.qoricash.pe'          # Prod sistema
])
```

---

## Escalabilidad

### Database Optimization

**Connection Pooling** (Eventlet compatible):
```python
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_size': 5,
    'pool_recycle': 1800,        # 30 min
    'pool_pre_ping': True,       # Verificar antes de usar
    'max_overflow': 5,
    'pool_timeout': 30,
    'pool_reset_on_return': 'rollback'
}
```

### Async Operations

**Eventlet** para operaciones I/O bound:
- Envío de correos (async)
- Socket.IO real-time
- Consultas a APIs externas

```python
# run.py (CRÍTICO: monkey patch primero)
import eventlet
eventlet.monkey_patch()

# Luego importar resto de código
from app import create_app
```

### Caching

**Future improvements**:
- Redis para exchange rates
- Redis para session storage
- CDN para static assets (Cloudinary ya lo hace)

### Monitoring

**Logs estructurados**:
```python
logger.info(f"Operación {op.operation_id} creada por cliente {client.id}")
logger.warning(f"Límite de $1000 alcanzado para cliente {client.id}")
logger.error(f"Error en NubeFact: {error_message}")
```

**Métricas a monitorear**:
- Operaciones por día/hora
- Tiempo promedio en cada estado
- Tasas de conversión (registro → operación)
- Errores de NubeFact/Cloudinary
- Alertas de compliance

---

## Despliegue

### Desarrollo

```bash
# Backend
cd Qoricashtrading
python run.py
# → http://localhost:5000

# Frontend
cd qoricash-web
npm run dev
# → http://localhost:3000
```

### Producción

**Backend (Render)**:
```bash
gunicorn -c gunicorn_config.py run:app
# Worker class: eventlet
# Port: 5000
# Workers: 1 (eventlet maneja concurrencia)
```

**Frontend (Vercel)**:
```bash
npm run build
next start
# Auto-deploy en push a main
```

### Variables de Entorno Críticas

```bash
# Database
DATABASE_URL=postgresql://...

# Cloudinary
CLOUDINARY_CLOUD_NAME=xxx
CLOUDINARY_API_KEY=xxx
CLOUDINARY_API_SECRET=xxx

# NubeFact
NUBEFACT_TOKEN=xxx
NUBEFACT_API_URL=https://api.nubefact.com/api/v1
NUBEFACT_ENABLED=True

# Email
MAIL_SERVER=smtp.gmail.com
MAIL_USERNAME=xxx
MAIL_PASSWORD=xxx

# Security
SECRET_KEY=xxx
FLASK_ENV=production
```

---

## Próximos Pasos Recomendados

### Mejoras Técnicas

1. **Testing**:
   - Unit tests (pytest)
   - Integration tests
   - E2E tests (Playwright)

2. **CI/CD**:
   - GitHub Actions
   - Automated testing
   - Automated deployment

3. **Monitoring**:
   - Sentry (error tracking)
   - LogRocket (session replay)
   - Datadog (APM)

4. **Performance**:
   - Redis caching
   - Database query optimization
   - CDN para assets

### Mejoras de Negocio

1. **App Móvil Nativa**:
   - Publicar en App Store/Play Store
   - Push notifications (Firebase)
   - Biometric auth

2. **Dashboard Analytics**:
   - Reportes avanzados
   - Gráficos de tendencias
   - Exportación a Excel/PDF

3. **Automatización**:
   - Auto-assignment de operadores
   - Auto-approval para clientes de bajo riesgo
   - Reconciliación bancaria automática

---

**Documento generado por**: Claude Code
**Fecha**: 22 de enero de 2026
**Versión**: 2.0
