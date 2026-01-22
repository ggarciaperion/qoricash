# Esquema de Base de Datos - QoriCash Trading V2

> Documentación completa del esquema de base de datos PostgreSQL
>
> **Última actualización**: 22 de enero de 2026

---

## Tabla de Contenidos

1. [Diagrama ERD Completo](#diagrama-erd-completo)
2. [Tablas Principales](#tablas-principales)
3. [Tablas de Compliance](#tablas-de-compliance)
4. [Relaciones y Foreign Keys](#relaciones-y-foreign-keys)
5. [Índices](#índices)
6. [Constraints](#constraints)

---

## Diagrama ERD Completo

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          CORE ENTITIES                                    │
└──────────────────────────────────────────────────────────────────────────┘

    ┌────────────────┐
    │     User       │
    ├────────────────┤
    │ id (PK)        │
    │ username       │◄──────────┐
    │ email          │           │
    │ password_hash  │           │ created_by
    │ dni            │           │
    │ role           │           │
    │ status         │           │
    │ created_at     │           │
    │ last_login     │           │
    └────────┬───────┘           │
             │                   │
             │ user_id           │
             │                   │
             ▼                   │
    ┌────────────────┐           │
    │    Client      │◄──────────┘
    ├────────────────┤
    │ id (PK)        │◄────────────────┐
    │ document_type  │                 │ referred_by
    │ dni (UNIQUE)   │                 │ (self-referential)
    │ email (UNIQUE) │                 │
    │ phone          │                 │
    │ password_hash  │                 │
    │ nombres        │─────────────────┘
    │ apellido_*     │
    │ razon_social   │
    │ dni_front_url  │ (Cloudinary)
    │ dni_back_url   │ (Cloudinary)
    │ bank_accounts  │ (JSON)
    │ referral_code  │ (6 chars unique)
    │ used_referral  │
    │ referred_by    │ (FK → clients.id)
    │ referral_pips  │
    │ status         │
    │ created_at     │
    │ created_by     │ (FK → users.id)
    └────────┬───────┘
             │
             │ client_id
             │
             ▼
    ┌─────────────────────────┐
    │      Operation          │
    ├─────────────────────────┤
    │ id (PK)                 │
    │ operation_id (UNIQUE)   │ ← "EXP-1001"
    │ client_id (FK)          │
    │ user_id (FK)            │ ← Trader que creó
    │ assigned_operator_id    │ ← Operador asignado
    │ operation_type          │ ← Compra/Venta
    │ origen                  │ ← sistema/app/web/plataforma
    │ amount_usd              │
    │ exchange_rate           │
    │ amount_pen              │
    │ source_account          │
    │ destination_account     │
    │ client_deposits_json    │ (JSON array)
    │ client_payments_json    │ (JSON array)
    │ operator_proofs_json    │ (JSON array, max 4)
    │ modification_logs_json  │ (JSON array)
    │ operator_comments       │
    │ status                  │ ← Pendiente/En proceso/...
    │ notes                   │
    │ notes_read_by_json      │ (JSON array de user IDs)
    │ created_at              │
    │ updated_at              │
    │ completed_at            │
    │ in_process_since        │
    └──────────┬──────────────┘
               │
               │ operation_id
               │
               ▼
    ┌─────────────────────────┐
    │       Invoice           │
    ├─────────────────────────┤
    │ id (PK)                 │
    │ operation_id (FK)       │
    │ client_id (FK)          │
    │ invoice_type            │ ← Factura/Boleta
    │ serie                   │ ← F001, B001
    │ numero                  │ ← 00000123
    │ invoice_number          │ ← F001-00000123
    │ emisor_ruc              │
    │ emisor_razon_social     │
    │ cliente_tipo_documento  │
    │ cliente_numero_doc      │
    │ cliente_denominacion    │
    │ monto_total             │
    │ moneda                  │ ← PEN/USD
    │ gravada                 │
    │ igv                     │
    │ status                  │ ← Pendiente/Aceptado/...
    │ nubefact_enlace_pdf     │ ← URL PDF
    │ nubefact_enlace_xml     │ ← URL XML
    │ nubefact_aceptada_sunat │
    │ created_at              │
    │ sent_at                 │
    │ accepted_at             │
    └─────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│                       REFERRALS & REWARDS                                 │
└──────────────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────┐
    │     RewardCode          │
    ├─────────────────────────┤
    │ id (PK)                 │
    │ code (UNIQUE)           │ ← 6 chars alfanuméricos
    │ client_id (FK)          │ ← Propietario
    │ pips_redeemed           │ ← 0.003 (30 pips)
    │ is_used                 │
    │ used_at                 │
    │ used_in_operation_id    │ (FK → operations.id)
    │ created_at              │
    └─────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│                      COMPLIANCE & AML/KYC                                 │
└──────────────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────┐
    │      RiskLevel          │
    ├─────────────────────────┤
    │ id (PK)                 │
    │ name (UNIQUE)           │ ← Bajo, Medio, Alto, Crítico
    │ description             │
    │ color                   │ ← green, yellow, orange, red
    │ score_min               │ ← 0
    │ score_max               │ ← 100
    │ created_at              │
    └───────────┬─────────────┘
                │
                │ risk_level_id
                ▼
    ┌─────────────────────────┐
    │  ClientRiskProfile      │
    ├─────────────────────────┤
    │ id (PK)                 │
    │ client_id (FK UNIQUE)   │ ← 1-1 con Client
    │ risk_level_id (FK)      │
    │ risk_score              │ ← 0-100
    │ is_pep                  │
    │ has_legal_issues        │
    │ in_restrictive_lists    │
    │ pep_type                │ ← Directo, Familiar, etc.
    │ pep_position            │
    │ pep_entity              │
    │ kyc_status              │ ← Pendiente/Aprobado/...
    │ kyc_verified_at         │
    │ kyc_verified_by (FK)    │ ← users.id
    │ dd_level                │ ← Básica/Reforzada
    │ scoring_details (JSON)  │
    │ created_at              │
    │ updated_at              │
    └─────────────────────────┘

    ┌─────────────────────────┐
    │   ComplianceRule        │
    ├─────────────────────────┤
    │ id (PK)                 │
    │ name                    │
    │ description             │
    │ rule_type               │ ← AML, KYC, PEP, Volumetric
    │ rule_config (JSON)      │
    │ is_active               │
    │ severity                │ ← Baja, Media, Alta, Crítica
    │ auto_flag               │
    │ auto_block              │
    │ requires_review         │
    │ created_at              │
    │ created_by (FK)         │
    └───────────┬─────────────┘
                │
                │ rule_id
                ▼
    ┌─────────────────────────┐
    │   ComplianceAlert       │
    ├─────────────────────────┤
    │ id (PK)                 │
    │ alert_type              │ ← AML, KYC, PEP, Suspicious
    │ severity                │
    │ client_id (FK)          │
    │ operation_id (FK)       │
    │ rule_id (FK)            │
    │ title                   │
    │ description             │
    │ details (JSON)          │
    │ status                  │ ← Pendiente/Resuelta/...
    │ reviewed_at             │
    │ reviewed_by (FK)        │ ← users.id
    │ review_notes            │
    │ resolution              │
    │ created_at              │
    │ updated_at              │
    └─────────────────────────┘

    ┌─────────────────────────┐
    │ RestrictiveListCheck    │
    ├─────────────────────────┤
    │ id (PK)                 │
    │ client_id (FK)          │
    │ list_type               │ ← OFAC, ONU, UIF, PEP
    │ provider                │ ← Inspektor, WorldCheck
    │ result                  │ ← Clean, Match, Potential
    │ match_score             │ ← 0-100
    │ details (JSON)          │
    │ is_manual               │
    │ pep_checked             │
    │ pep_result              │
    │ ofac_checked            │
    │ ofac_result             │
    │ onu_checked             │
    │ onu_result              │
    │ uif_checked             │
    │ uif_result              │
    │ interpol_checked        │
    │ interpol_result         │
    │ observations            │
    │ attachments             │ ← URLs Cloudinary
    │ checked_at              │
    │ checked_by (FK)         │
    └─────────────────────────┘

    ┌─────────────────────────┐
    │ TransactionMonitoring   │
    ├─────────────────────────┤
    │ id (PK)                 │
    │ operation_id (FK)       │
    │ client_id (FK)          │
    │ risk_score              │ ← 0-100
    │ flags (JSON)            │
    │ unusual_amount          │
    │ unusual_frequency       │
    │ structuring             │ ← Smurfing detection
    │ rapid_movement          │
    │ client_avg_amount       │
    │ deviation_percentage    │
    │ analyzed_at             │
    └─────────────────────────┘

    ┌─────────────────────────┐
    │  ComplianceDocument     │
    ├─────────────────────────┤
    │ id (PK)                 │
    │ document_type           │ ← ROS, Due_Diligence, KYC
    │ title                   │
    │ client_id (FK)          │
    │ operation_id (FK)       │
    │ alert_id (FK)           │
    │ file_url                │ ← Cloudinary
    │ file_name               │
    │ content                 │
    │ status                  │ ← Borrador/Enviado/...
    │ sent_to_uif             │
    │ sent_at                 │
    │ created_at              │
    │ created_by (FK)         │
    └─────────────────────────┘

    ┌─────────────────────────┐
    │   ComplianceAudit       │
    ├─────────────────────────┤
    │ id (PK)                 │
    │ user_id (FK)            │
    │ action_type             │ ← KYC_Review, Alert_Resolution
    │ entity_type             │ ← Client, Operation, Alert
    │ entity_id               │
    │ description             │
    │ changes (JSON)          │
    │ ip_address              │
    │ user_agent              │
    │ created_at              │
    └─────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│                       AUDITORÍA GENERAL                                   │
└──────────────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────┐
    │      AuditLog           │
    ├─────────────────────────┤
    │ id (PK)                 │
    │ user_id (FK)            │
    │ action                  │ ← CREATE_USER, UPDATE_OP, etc.
    │ entity                  │ ← User, Client, Operation
    │ entity_id               │
    │ details                 │
    │ notes                   │
    │ ip_address              │
    │ user_agent              │
    │ created_at              │
    └─────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│                     FINANZAS & CONTABILIDAD                               │
└──────────────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────┐
    │    ExchangeRate         │
    ├─────────────────────────┤
    │ id (PK)                 │
    │ buy_rate                │ ← Tipo de cambio compra
    │ sell_rate               │ ← Tipo de cambio venta
    │ updated_by (FK)         │
    │ updated_at              │
    └─────────────────────────┘

    ┌─────────────────────────┐
    │     BankBalance         │
    ├─────────────────────────┤
    │ id (PK)                 │
    │ bank_name               │
    │ balance_usd             │
    │ balance_pen             │
    │ initial_balance_usd     │
    │ initial_balance_pen     │
    │ updated_at              │
    │ updated_by (FK)         │
    └─────────────────────────┘

    ┌─────────────────────────┐
    │     TraderGoal          │
    ├─────────────────────────┤
    │ id (PK)                 │
    │ user_id (FK)            │ ← Trader
    │ month                   │
    │ year                    │
    │ goal_amount_pen         │
    │ created_by (FK)         │
    │ created_at              │
    └─────────────────────────┘

    ┌─────────────────────────┐
    │  TraderDailyProfit      │
    ├─────────────────────────┤
    │ id (PK)                 │
    │ user_id (FK)            │ ← Trader
    │ profit_date             │
    │ profit_amount_pen       │
    │ created_by (FK)         │
    │ created_at              │
    └─────────────────────────┘

    ┌─────────────────────────┐
    │   AccountingBatch       │
    ├─────────────────────────┤
    │ id (PK)                 │
    │ batch_code (UNIQUE)     │ ← NET-20260122-001
    │ description             │
    │ netting_date            │
    │ total_buys_usd          │
    │ total_buys_pen          │
    │ total_sells_usd         │
    │ total_sells_pen         │
    │ difference_usd          │
    │ total_profit_pen        │
    │ avg_buy_rate            │
    │ avg_sell_rate           │
    │ accounting_entry_json   │ ← Asientos contables
    │ status                  │ ← Abierto, Cerrado, Anulado
    │ created_at              │
    │ created_by (FK)         │
    └─────────────────────────┘

    ┌─────────────────────────┐
    │   AccountingMatch       │
    ├─────────────────────────┤
    │ id (PK)                 │
    │ batch_id (FK)           │
    │ buy_operation_id (FK)   │
    │ sell_operation_id (FK)  │
    │ matched_usd             │
    │ created_at              │
    └─────────────────────────┘
```

---

## Tablas Principales

### users
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(200) NOT NULL,
    dni VARCHAR(20) UNIQUE NOT NULL,
    role VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'Activo',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP,
    last_login TIMESTAMP,
    last_logout TIMESTAMP,

    CONSTRAINT check_user_role
        CHECK (role IN ('Master', 'Trader', 'Operador', 'Middle Office',
                        'Plataforma', 'App', 'Web')),
    CONSTRAINT check_user_status
        CHECK (status IN ('Activo', 'Inactivo'))
);
```

### clients
```sql
CREATE TABLE clients (
    id SERIAL PRIMARY KEY,
    document_type VARCHAR(10) NOT NULL,
    dni VARCHAR(20) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    phone VARCHAR(100),
    password_hash VARCHAR(200),
    requires_password_change BOOLEAN DEFAULT FALSE,

    -- Información personal (DNI/CE)
    apellido_paterno VARCHAR(100),
    apellido_materno VARCHAR(100),
    nombres VARCHAR(100),

    -- Información empresa (RUC)
    razon_social VARCHAR(200),
    persona_contacto VARCHAR(200),

    -- Documentos (Cloudinary URLs)
    dni_front_url VARCHAR(500),
    dni_back_url VARCHAR(500),
    dni_representante_front_url VARCHAR(500),
    dni_representante_back_url VARCHAR(500),
    ficha_ruc_url VARCHAR(500),
    validation_oc_url VARCHAR(500),

    -- Dirección
    direccion VARCHAR(300),
    distrito VARCHAR(100),
    provincia VARCHAR(100),
    departamento VARCHAR(100),

    -- Cuentas bancarias (JSON array)
    bank_accounts_json TEXT,

    -- Sistema de referidos
    referral_code VARCHAR(6) UNIQUE,
    used_referral_code VARCHAR(6),
    referred_by INTEGER REFERENCES clients(id),
    referral_pips_earned FLOAT DEFAULT 0.0,
    referral_pips_available FLOAT DEFAULT 0.0,
    referral_completed_uses INTEGER DEFAULT 0,
    referral_total_uses INTEGER DEFAULT 0,

    -- Estado
    status VARCHAR(20) NOT NULL DEFAULT 'Inactivo',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP,
    created_by INTEGER REFERENCES users(id),

    -- Índices
    CREATE INDEX idx_clients_dni ON clients(dni),
    CREATE INDEX idx_clients_email ON clients(email),
    CREATE INDEX idx_clients_referral_code ON clients(referral_code)
);
```

### operations
```sql
CREATE TABLE operations (
    id SERIAL PRIMARY KEY,
    operation_id VARCHAR(50) UNIQUE NOT NULL,

    -- Foreign Keys
    client_id INTEGER NOT NULL REFERENCES clients(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    assigned_operator_id INTEGER REFERENCES users(id),

    -- Tipo y origen
    operation_type VARCHAR(20) NOT NULL,
    origen VARCHAR(20) NOT NULL DEFAULT 'sistema',

    -- Montos
    amount_usd NUMERIC(15, 2) NOT NULL,
    exchange_rate NUMERIC(10, 4) NOT NULL,
    amount_pen NUMERIC(15, 2) NOT NULL,

    -- Cuentas
    source_account VARCHAR(100),
    destination_account VARCHAR(100),

    -- Comprobantes y pagos (JSON)
    client_deposits_json TEXT DEFAULT '[]',
    client_payments_json TEXT DEFAULT '[]',
    operator_proofs_json TEXT DEFAULT '[]',
    modification_logs_json TEXT DEFAULT '[]',
    operator_comments TEXT,

    -- Comprobantes legacy
    payment_proof_url VARCHAR(500),
    operator_proof_url VARCHAR(500),

    -- Estado
    status VARCHAR(20) NOT NULL DEFAULT 'Pendiente',
    notes TEXT,
    notes_read_by_json TEXT DEFAULT '[]',

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP,
    completed_at TIMESTAMP,
    in_process_since TIMESTAMP,

    -- Constraints
    CONSTRAINT check_operation_type
        CHECK (operation_type IN ('Compra', 'Venta')),
    CONSTRAINT check_operation_status
        CHECK (status IN ('Pendiente', 'En proceso', 'Completada',
                          'Cancelado', 'Expirada')),
    CONSTRAINT check_operation_origen
        CHECK (origen IN ('sistema', 'plataforma', 'app', 'web')),
    CONSTRAINT check_amount_usd_positive
        CHECK (amount_usd > 0),
    CONSTRAINT check_exchange_rate_positive
        CHECK (exchange_rate > 0),

    -- Índices
    CREATE INDEX idx_operations_operation_id ON operations(operation_id),
    CREATE INDEX idx_operations_client_id ON operations(client_id),
    CREATE INDEX idx_operations_user_id ON operations(user_id),
    CREATE INDEX idx_operations_assigned_operator ON operations(assigned_operator_id),
    CREATE INDEX idx_operations_status ON operations(status),
    CREATE INDEX idx_operations_origen ON operations(origen),
    CREATE INDEX idx_operations_created_at ON operations(created_at)
);
```

### invoices
```sql
CREATE TABLE invoices (
    id SERIAL PRIMARY KEY,

    -- Foreign Keys
    operation_id INTEGER NOT NULL REFERENCES operations(id),
    client_id INTEGER NOT NULL REFERENCES clients(id),

    -- Tipo de comprobante
    invoice_type VARCHAR(20) NOT NULL,
    serie VARCHAR(10),
    numero VARCHAR(20),
    invoice_number VARCHAR(50),

    -- Emisor (QoriCash SAC)
    emisor_ruc VARCHAR(11) NOT NULL,
    emisor_razon_social VARCHAR(200) NOT NULL,
    emisor_direccion VARCHAR(300),

    -- Cliente (receptor)
    cliente_tipo_documento VARCHAR(10),
    cliente_numero_documento VARCHAR(20) NOT NULL,
    cliente_denominacion VARCHAR(200) NOT NULL,
    cliente_direccion VARCHAR(300),
    cliente_email VARCHAR(120),

    -- Detalles
    descripcion TEXT,
    monto_total NUMERIC(15, 2) NOT NULL,
    moneda VARCHAR(10) DEFAULT 'PEN',
    gravada NUMERIC(15, 2) DEFAULT 0,
    exonerada NUMERIC(15, 2) DEFAULT 0,
    igv NUMERIC(15, 2) DEFAULT 0,

    -- Estado
    status VARCHAR(20) NOT NULL DEFAULT 'Pendiente',

    -- NubeFact
    nubefact_response TEXT,
    nubefact_enlace_pdf VARCHAR(500),
    nubefact_enlace_xml VARCHAR(500),
    nubefact_aceptada_por_sunat BOOLEAN DEFAULT FALSE,
    nubefact_sunat_description TEXT,
    nubefact_sunat_note TEXT,
    nubefact_codigo_hash VARCHAR(200),

    -- Errores
    error_message TEXT,

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP,
    sent_at TIMESTAMP,
    accepted_at TIMESTAMP,

    -- Índices
    CREATE INDEX idx_invoices_operation_id ON invoices(operation_id),
    CREATE INDEX idx_invoices_client_id ON invoices(client_id),
    CREATE INDEX idx_invoices_invoice_number ON invoices(invoice_number),
    CREATE INDEX idx_invoices_status ON invoices(status),
    CREATE INDEX idx_invoices_created_at ON invoices(created_at)
);
```

---

## Tablas de Compliance

### client_risk_profiles
```sql
CREATE TABLE client_risk_profiles (
    id SERIAL PRIMARY KEY,
    client_id INTEGER UNIQUE NOT NULL REFERENCES clients(id),
    risk_level_id INTEGER REFERENCES risk_levels(id),
    risk_score INTEGER DEFAULT 0,

    -- Flags de riesgo
    is_pep BOOLEAN DEFAULT FALSE,
    has_legal_issues BOOLEAN DEFAULT FALSE,
    in_restrictive_lists BOOLEAN DEFAULT FALSE,
    high_volume_operations BOOLEAN DEFAULT FALSE,

    -- Datos PEP
    pep_type VARCHAR(50),
    pep_position VARCHAR(200),
    pep_entity VARCHAR(200),
    pep_designation_date DATE,
    pep_end_date DATE,
    pep_notes TEXT,

    -- KYC
    kyc_status VARCHAR(50) DEFAULT 'Pendiente',
    kyc_verified_at TIMESTAMP,
    kyc_verified_by INTEGER REFERENCES users(id),
    kyc_notes TEXT,

    -- Due Diligence
    dd_level VARCHAR(50),
    dd_last_review TIMESTAMP,
    dd_next_review TIMESTAMP,

    -- Scoring
    scoring_details TEXT,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP
);
```

### compliance_alerts
```sql
CREATE TABLE compliance_alerts (
    id SERIAL PRIMARY KEY,

    -- Tipo de alerta
    alert_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,

    -- Entidad relacionada
    client_id INTEGER REFERENCES clients(id),
    operation_id INTEGER REFERENCES operations(id),
    rule_id INTEGER REFERENCES compliance_rules(id),

    -- Detalles
    title VARCHAR(200) NOT NULL,
    description TEXT,
    details TEXT,

    -- Estado
    status VARCHAR(50) DEFAULT 'Pendiente',
    reviewed_at TIMESTAMP,
    reviewed_by INTEGER REFERENCES users(id),
    review_notes TEXT,
    resolution VARCHAR(100),

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP
);
```

---

## Relaciones y Foreign Keys

### Relaciones Principales

```
User → Client (1:N)
  - users.id → clients.created_by

User → Operation (1:N) [Creador]
  - users.id → operations.user_id

User → Operation (1:N) [Operador Asignado]
  - users.id → operations.assigned_operator_id

Client → Client (1:N) [Referidos]
  - clients.id → clients.referred_by (self-referential)

Client → Operation (1:N)
  - clients.id → operations.client_id

Client → Invoice (1:N)
  - clients.id → invoices.client_id

Client → RewardCode (1:N)
  - clients.id → reward_codes.client_id

Client → ClientRiskProfile (1:1)
  - clients.id → client_risk_profiles.client_id (UNIQUE)

Operation → Invoice (1:N)
  - operations.id → invoices.operation_id

Operation → RewardCode (1:N)
  - operations.id → reward_codes.used_in_operation_id

Operation → ComplianceAlert (1:N)
  - operations.id → compliance_alerts.operation_id

Operation → TransactionMonitoring (1:1)
  - operations.id → transaction_monitoring.operation_id
```

---

## Índices

### Índices de Rendimiento

```sql
-- Búsquedas frecuentes
CREATE INDEX idx_clients_dni ON clients(dni);
CREATE INDEX idx_clients_email ON clients(email);
CREATE INDEX idx_clients_referral_code ON clients(referral_code);
CREATE INDEX idx_operations_operation_id ON operations(operation_id);
CREATE INDEX idx_operations_status ON operations(status);
CREATE INDEX idx_operations_created_at ON operations(created_at);

-- Foreign Keys (optimización de JOINs)
CREATE INDEX idx_operations_client_id ON operations(client_id);
CREATE INDEX idx_operations_user_id ON operations(user_id);
CREATE INDEX idx_operations_assigned_operator_id ON operations(assigned_operator_id);
CREATE INDEX idx_invoices_operation_id ON invoices(operation_id);
CREATE INDEX idx_invoices_client_id ON invoices(client_id);

-- Compliance
CREATE INDEX idx_client_risk_profiles_client_id ON client_risk_profiles(client_id);
CREATE INDEX idx_compliance_alerts_client_id ON compliance_alerts(client_id);
CREATE INDEX idx_compliance_alerts_operation_id ON compliance_alerts(operation_id);
CREATE INDEX idx_compliance_alerts_status ON compliance_alerts(status);
```

---

## Constraints

### Check Constraints

```sql
-- Users
ALTER TABLE users ADD CONSTRAINT check_user_role
    CHECK (role IN ('Master', 'Trader', 'Operador', 'Middle Office',
                    'Plataforma', 'App', 'Web'));

ALTER TABLE users ADD CONSTRAINT check_user_status
    CHECK (status IN ('Activo', 'Inactivo'));

-- Operations
ALTER TABLE operations ADD CONSTRAINT check_operation_type
    CHECK (operation_type IN ('Compra', 'Venta'));

ALTER TABLE operations ADD CONSTRAINT check_operation_status
    CHECK (status IN ('Pendiente', 'En proceso', 'Completada',
                      'Cancelado', 'Expirada'));

ALTER TABLE operations ADD CONSTRAINT check_operation_origen
    CHECK (origen IN ('sistema', 'plataforma', 'app', 'web'));

ALTER TABLE operations ADD CONSTRAINT check_amount_usd_positive
    CHECK (amount_usd > 0);

ALTER TABLE operations ADD CONSTRAINT check_exchange_rate_positive
    CHECK (exchange_rate > 0);
```

### Unique Constraints

```sql
-- Evitar duplicados
ALTER TABLE users ADD CONSTRAINT unique_username UNIQUE (username);
ALTER TABLE users ADD CONSTRAINT unique_email UNIQUE (email);
ALTER TABLE users ADD CONSTRAINT unique_dni UNIQUE (dni);

ALTER TABLE clients ADD CONSTRAINT unique_client_dni UNIQUE (dni);
ALTER TABLE clients ADD CONSTRAINT unique_client_email UNIQUE (email);
ALTER TABLE clients ADD CONSTRAINT unique_referral_code UNIQUE (referral_code);

ALTER TABLE operations ADD CONSTRAINT unique_operation_id UNIQUE (operation_id);

ALTER TABLE reward_codes ADD CONSTRAINT unique_reward_code UNIQUE (code);

ALTER TABLE client_risk_profiles ADD CONSTRAINT unique_client_profile
    UNIQUE (client_id);
```

---

## Tamaños Aproximados

**Estimación para 10,000 clientes y 50,000 operaciones**:

| Tabla | Registros | Tamaño Aprox. |
|-------|-----------|---------------|
| clients | 10,000 | ~15 MB |
| operations | 50,000 | ~80 MB |
| invoices | 50,000 | ~60 MB |
| reward_codes | 1,000 | ~1 MB |
| client_risk_profiles | 10,000 | ~10 MB |
| compliance_alerts | 2,000 | ~3 MB |
| transaction_monitoring | 50,000 | ~25 MB |
| audit_logs | 100,000 | ~40 MB |
| **TOTAL** | **~270,000** | **~234 MB** |

---

**Documento generado por**: Claude Code
**Fecha**: 22 de enero de 2026
**Versión**: 2.0
