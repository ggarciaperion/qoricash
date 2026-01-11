# Implementación del Rol "Web" y Canal "web"

## Fecha de Implementación
11 de Enero de 2025

## Objetivo

Integrar la página web de QoriCash (qoricash-web) al ecosistema del sistema web (Qoricashtrading), replicando la misma lógica y funcionalidad del rol "App" para el aplicativo móvil, garantizando:

1. **Trazabilidad completa** de operaciones generadas desde la web
2. **Autenticación unificada** entre app móvil y página web
3. **Asignación correcta** de clientes y operaciones al trader que los registró
4. **Métricas y estadísticas** unificadas independiente del canal de origen

---

## Contexto del Sistema

### Ecosistema Actual

```
┌─────────────────────┐
│  Página Web         │ ──┐
│  (qoricash-web)     │   │
└─────────────────────┘   │
                          │
┌─────────────────────┐   ├──► ┌─────────────────────┐
│  Aplicativo Móvil   │ ──┤    │  Sistema Web Core   │
│  (QoriCashApp)      │   │    │  (Qoricashtrading)  │
└─────────────────────┘   │    └─────────────────────┘
                          │
┌─────────────────────┐   │
│  Operación Manual   │ ──┘
│  (Traders)          │
└─────────────────────┘
```

### Roles Existentes Antes de la Implementación

| Rol | Descripción | Canal |
|-----|-------------|-------|
| **Master** | Administrador principal del sistema | sistema |
| **Trader** | Gestor de clientes y operaciones | sistema |
| **Operador** | Procesa operaciones "En proceso" | sistema |
| **Middle Office** | Gestión de cumplimiento normativo (KYC/AML) | sistema |
| **Plataforma** | Canal web público (página anterior, desuso) | plataforma |
| **App** | Aplicativo móvil | app |

### Canales de Origen de Operaciones

| Canal | Descripción | Uso |
|-------|-------------|-----|
| **sistema** | Operaciones creadas manualmente por traders | Default |
| **plataforma** | Operaciones desde la página web anterior (legacy) | Obsoleto |
| **app** | Operaciones autónomas desde el aplicativo móvil | Activo |

---

## Cambios Implementados

### 1. Nuevo Rol: "Web"

Se agregó el rol **"Web"** al modelo de usuarios para identificar operaciones generadas desde la página web.

#### Modelo User (app/models/user.py)

**Antes:**
```python
role = db.Column(
    db.String(20),
    nullable=False,
    default='Trader'
)  # Master, Trader, Operador, Middle Office, Plataforma, App
```

**Después:**
```python
role = db.Column(
    db.String(20),
    nullable=False,
    default='Trader'
)  # Master, Trader, Operador, Middle Office, Plataforma, App, Web
```

**Constraint actualizado:**
```python
db.CheckConstraint(
    role.in_(['Master', 'Trader', 'Operador', 'Middle Office', 'Plataforma', 'App', 'Web']),
    name='check_user_role'
)
```

**Método agregado:**
```python
def is_web(self):
    """Verificar si es usuario de la Página Web"""
    return self.role == 'Web'
```

---

### 2. Nuevo Canal: "web"

Se agregó el canal **"web"** al modelo de operaciones para rastrear operaciones desde la página web.

#### Modelo Operation (app/models/operation.py)

**Antes:**
```python
origen = db.Column(
    db.String(20),
    nullable=False,
    default='sistema',
    index=True
)  # sistema, plataforma, app
```

**Después:**
```python
origen = db.Column(
    db.String(20),
    nullable=False,
    default='sistema',
    index=True
)  # sistema, plataforma, app, web
```

**Constraint actualizado:**
```python
db.CheckConstraint(
    origen.in_(['sistema', 'plataforma', 'app', 'web']),
    name='check_operation_origen'
)
```

---

### 3. Validaciones de Servicio Actualizadas

#### OperationService (app/services/operation_service.py)

**Línea 145-146 - Permisos para crear operaciones:**
```python
if not current_user or current_user.role not in ['Master', 'Trader', 'Plataforma', 'App', 'Web']:
    return False, 'No tienes permiso para crear operaciones', None
```

**Línea 165-167 - Validación de ownership de clientes:**
```python
if current_user.role in ['Trader', 'Plataforma', 'App', 'Web']:
    if client.created_by != current_user.id:
        return False, 'Solo puedes crear operaciones para tus propios clientes', None
```

**Línea 189-190 - Validación de canal:**
```python
if origen not in ['sistema', 'plataforma', 'app', 'web']:
    origen = 'sistema'  # Default a 'sistema' si el valor es inválido
```

---

### 4. Migración de Base de Datos

Archivo: `migrations/versions/20250111_add_web_role_and_channel.py`

#### Acciones de la Migración

**Upgrade:**
1. ✅ Actualizar constraint `check_user_role` para incluir 'Web'
2. ✅ Actualizar constraint `check_operation_origen` para incluir 'web'
3. ✅ Crear o actualizar usuario del sistema:
   - Email: `web@qoricash.pe`
   - Username: `Página Web`
   - DNI: `99999997` (ficticio, usuario de sistema)
   - Rol: `Web`
   - Contraseña: `WebQoriCash2025!`

**Downgrade:**
1. Revertir usuario web a rol 'Plataforma'
2. Eliminar 'Web' del constraint de roles
3. Eliminar 'web' del constraint de origen

#### Ejecutar Migración

```bash
cd C:\Users\ACER\Desktop\Qoricashtrading
flask db upgrade
```

O usando Alembic directamente:
```bash
alembic upgrade head
```

---

## Autenticación Unificada

### Flujo de Autenticación (App y Web)

Los endpoints de autenticación son **unificados** entre el app móvil y la página web:

#### Endpoint: POST `/api/client/login`

**Request:**
```json
{
  "dni": "12345678",
  "password": "MiContraseña123!"
}
```

**Response (Exitoso):**
```json
{
  "success": true,
  "message": "Login exitoso",
  "client": {
    "id": 1,
    "dni": "12345678",
    "full_name": "Juan Pérez",
    "email": "juan@example.com",
    "phone": "987654321",
    "status": "Activo",
    ...
  },
  "requires_password_change": false
}
```

**Response (Error):**
```json
{
  "success": false,
  "message": "Contraseña incorrecta"
}
```

---

### Cambio de Contraseña

#### Endpoint: POST `/api/client/change-password`

**Request:**
```json
{
  "dni": "12345678",
  "current_password": "temporal123",
  "new_password": "MiNuevaContraseña123!"
}
```

**Validaciones:**
- Nueva contraseña mínimo 8 caracteres
- Si `requires_password_change=True`, no requiere contraseña actual

---

### Recuperación de Contraseña

#### Endpoint: POST `/api/client/forgot-password`

**Request:**
```json
{
  "dni": "12345678"
}
```

**Proceso:**
1. Genera contraseña temporal de 10 caracteres
2. Envía contraseña por email al cliente
3. Marca `requires_password_change = True`

---

## Asignación de Operaciones y Métricas

### Regla Fundamental

**Cuando un trader registra a un cliente desde el sistema web:**
- El cliente queda asignado al trader mediante el campo `created_by`
- **Todas las operaciones** generadas por ese cliente (desde web, app o sistema) **se contabilizan al trader original**

### Ejemplo de Flujo

```
1. Trader "Juan" registra al cliente "María" desde el sistema web
   → María.created_by = Juan.id

2. María recibe email con contraseña temporal

3. María ingresa a la página web y crea una operación
   → Operación.user_id = Usuario Web (rol: Web)
   → Operación.client_id = María.id
   → Operación.origen = 'web'

4. El sistema identifica que:
   → María.created_by = Juan.id
   → La operación suma a las métricas del Trader "Juan"
   → Juan puede ver esta operación en su dashboard
   → La comisión se asigna a Juan
```

### Dashboard y Estadísticas

Las estadísticas del trader incluyen **todas las operaciones de sus clientes**, independiente del canal:

```python
# En OperationService.get_dashboard_stats()
operations = Operation.query.join(Client).filter(
    Client.created_by == trader_id
).all()
```

---

## Tabla de Comparación: App vs Web

| Característica | App Móvil | Página Web |
|----------------|-----------|------------|
| **Rol** | App | Web |
| **Canal** | app | web |
| **Autenticación** | DNI + Contraseña | DNI + Contraseña ✅ Unificada |
| **Registro de Cliente** | ❌ No disponible | ❌ No disponible (solo traders) |
| **Crear Operación** | ✅ Autónoma | ✅ Autónoma |
| **Asignación a Trader** | ✅ Al trader que registró | ✅ Al trader que registró |
| **Métricas** | ✅ Suma al trader | ✅ Suma al trader |
| **Endpoints** | `/api/client/*` | `/api/client/*` ✅ Compartidos |

---

## Archivos Modificados

| Archivo | Cambios |
|---------|---------|
| `app/models/user.py` | Agregado rol 'Web' + método `is_web()` |
| `app/models/operation.py` | Agregado canal 'web' |
| `app/services/operation_service.py` | Actualizado permisos y validaciones |
| `migrations/versions/20250111_add_web_role_and_channel.py` | Nueva migración |

---

## Endpoints Disponibles para la Página Web

### Autenticación de Clientes
- `POST /api/client/login` - Login de cliente
- `POST /api/client/change-password` - Cambiar contraseña
- `POST /api/client/forgot-password` - Recuperar contraseña
- `POST /api/client/logout` - Cerrar sesión

### Operaciones
- `POST /api/operations` - Crear operación
  - Parámetro `origen='web'` debe enviarse
- `GET /api/operations/client/<client_id>` - Operaciones del cliente
- `GET /api/operations/<id>` - Detalle de operación

### Tipos de Cambio
- `GET /api/exchange-rates/current` - Tipo de cambio actual (compra/venta)

### Clientes (Solo lectura para el cliente)
- `GET /api/clients/<id>` - Datos del cliente
- `GET /api/clients/<id>/stats` - Estadísticas del cliente

---

## Ejemplo de Implementación en qoricash-web

### 1. Servicio de Autenticación (TypeScript)

```typescript
// services/authService.ts
import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000';

export interface LoginRequest {
  dni: string;
  password: string;
}

export interface Client {
  id: number;
  dni: string;
  full_name: string;
  email: string;
  phone: string;
  status: string;
}

export interface LoginResponse {
  success: boolean;
  message: string;
  client?: Client;
  requires_password_change?: boolean;
}

export const authService = {
  login: async (credentials: LoginRequest): Promise<LoginResponse> => {
    const response = await axios.post(`${API_BASE_URL}/api/client/login`, credentials);
    return response.data;
  },

  changePassword: async (dni: string, currentPassword: string, newPassword: string) => {
    const response = await axios.post(`${API_BASE_URL}/api/client/change-password`, {
      dni,
      current_password: currentPassword,
      new_password: newPassword
    });
    return response.data;
  },

  forgotPassword: async (dni: string) => {
    const response = await axios.post(`${API_BASE_URL}/api/client/forgot-password`, {
      dni
    });
    return response.data;
  }
};
```

### 2. Servicio de Operaciones (TypeScript)

```typescript
// services/operationService.ts
import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000';

export interface CreateOperationRequest {
  client_id: number;
  operation_type: 'Compra' | 'Venta';
  amount_usd: number;
  exchange_rate: number;
  source_account?: string;
  destination_account?: string;
  notes?: string;
  origen: 'web';  // Siempre 'web' para operaciones desde la página
}

export const operationService = {
  createOperation: async (data: CreateOperationRequest, clientToken: string) => {
    const response = await axios.post(`${API_BASE_URL}/api/operations`, data, {
      headers: {
        'Authorization': `Bearer ${clientToken}`,
        'Content-Type': 'application/json'
      }
    });
    return response.data;
  },

  getClientOperations: async (clientId: number, clientToken: string) => {
    const response = await axios.get(`${API_BASE_URL}/api/operations/client/${clientId}`, {
      headers: {
        'Authorization': `Bearer ${clientToken}`
      }
    });
    return response.data;
  }
};
```

### 3. Hook de Autenticación (React)

```typescript
// hooks/useAuth.ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { authService, Client } from '@/services/authService';

interface AuthState {
  client: Client | null;
  isAuthenticated: boolean;
  requiresPasswordChange: boolean;
  login: (dni: string, password: string) => Promise<void>;
  logout: () => void;
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>;
}

export const useAuth = create<AuthState>()(
  persist(
    (set, get) => ({
      client: null,
      isAuthenticated: false,
      requiresPasswordChange: false,

      login: async (dni: string, password: string) => {
        const response = await authService.login({ dni, password });
        if (response.success && response.client) {
          set({
            client: response.client,
            isAuthenticated: true,
            requiresPasswordChange: response.requires_password_change || false
          });
        } else {
          throw new Error(response.message);
        }
      },

      logout: () => {
        set({
          client: null,
          isAuthenticated: false,
          requiresPasswordChange: false
        });
      },

      changePassword: async (currentPassword: string, newPassword: string) => {
        const client = get().client;
        if (!client) throw new Error('No hay cliente autenticado');

        const response = await authService.changePassword(
          client.dni,
          currentPassword,
          newPassword
        );

        if (response.success) {
          set({ requiresPasswordChange: false });
        } else {
          throw new Error(response.message);
        }
      }
    }),
    {
      name: 'qoricash-auth-storage'
    }
  )
);
```

---

## Validaciones y Reglas de Negocio

### 1. Creación de Operaciones desde Web

```python
# En OperationService.create_operation()
if current_user.role == 'Web':
    # El usuario Web puede crear operaciones para cualquier cliente activo
    # La operación se marca con origen='web'
    # El client.created_by determina a qué trader se asignan las métricas
```

### 2. Límites de Operación sin Documentos

```python
# En Client.can_create_operation()
if not self.has_complete_documents():
    total_usd = self.get_total_operations_usd()
    if total_usd + amount_usd > 1000:
        return False, "Has alcanzado el límite de $1,000. Completa tu documentación."
```

### 3. Estado del Cliente

Los clientes deben estar **Activos** para poder:
- Iniciar sesión en web/app
- Crear operaciones

---

## Métricas y Reportes

### Dashboard del Trader

**Incluye operaciones de sus clientes desde:**
- ✅ Sistema (creadas manualmente por el trader)
- ✅ App (creadas por el cliente desde móvil)
- ✅ Web (creadas por el cliente desde página web)

### Filtrado por Canal

```sql
-- Operaciones desde página web
SELECT * FROM operations WHERE origen = 'web';

-- Operaciones del trader "Juan" desde cualquier canal
SELECT o.*
FROM operations o
JOIN clients c ON o.client_id = c.id
WHERE c.created_by = (SELECT id FROM users WHERE username = 'Juan');
```

---

## Próximos Pasos

### En el Sistema Web (Qoricashtrading)

1. ✅ Ejecutar migración `20250111_add_web_role_and_channel.py`
2. ⏳ Verificar que el usuario web@qoricash.pe se creó correctamente
3. ⏳ Probar creación de operaciones con origen='web'

### En la Página Web (qoricash-web)

1. ⏳ Implementar servicios de autenticación (`authService.ts`)
2. ⏳ Implementar servicios de operaciones (`operationService.ts`)
3. ⏳ Crear formulario de login
4. ⏳ Crear formulario de cambio de contraseña
5. ⏳ Crear formulario de creación de operaciones (con origen='web')
6. ⏳ Implementar dashboard del cliente (ver sus operaciones)
7. ⏳ Configurar variables de entorno (NEXT_PUBLIC_API_URL)

---

## Comandos Útiles

### Verificar Usuario Web
```sql
SELECT * FROM users WHERE role = 'Web';
```

### Verificar Operaciones desde Web
```sql
SELECT
  o.operation_id,
  o.origen,
  c.full_name AS cliente,
  u.username AS creado_por,
  o.amount_usd,
  o.status,
  o.created_at
FROM operations o
JOIN clients c ON o.client_id = c.id
JOIN users u ON c.created_by = u.id
WHERE o.origen = 'web'
ORDER BY o.created_at DESC;
```

### Estadísticas por Canal
```sql
SELECT
  origen,
  COUNT(*) AS total_operaciones,
  SUM(amount_usd) AS total_usd
FROM operations
WHERE status = 'Completada'
GROUP BY origen;
```

---

## Contacto y Soporte

Para dudas sobre la implementación:
- **Sistema Web:** Qoricashtrading
- **Página Web:** qoricash-web
- **Aplicativo Móvil:** QoriCashApp

---

**Última actualización:** 11 de Enero de 2025
