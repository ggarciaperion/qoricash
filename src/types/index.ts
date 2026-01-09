// User Types
export interface User {
  id: number;
  username: string;
  email?: string;
  role: 'Master' | 'Trader' | 'Operador' | 'Middle Office' | 'Plataforma' | 'Cliente';
  status?: 'Activo' | 'Inactivo';
}

// Client Types
export interface BankAccount {
  origen: string;
  bank_name: string;
  account_type: string;
  currency: 'S/' | '$';
  account_number: string;
}

export interface Client {
  id: number;
  document_type: 'DNI' | 'CE' | 'RUC';
  dni: string;
  full_name: string;
  apellido_paterno?: string;
  apellido_materno?: string;
  nombres?: string;
  razon_social?: string;
  persona_contacto?: string;
  email: string;
  phone: string;
  direccion?: string;
  distrito?: string;
  provincia?: string;
  departamento?: string;
  status: 'Activo' | 'Inactivo';
  bank_accounts: BankAccount[];
  created_at: string;
  total_operations?: number;
  total_usd_traded?: number;
  has_complete_documents?: boolean;
  // Documentos para Persona Natural (DNI/CE)
  dni_front_url?: string;
  dni_back_url?: string;
  // Documentos para Persona Jurídica (RUC)
  dni_representante_front_url?: string;
  dni_representante_back_url?: string;
  ficha_ruc_url?: string;
}

// Operation Types
export interface ClientDeposit {
  importe: number;
  codigo_operacion: string;
  cuenta_cargo: string;
  comprobante_url?: string;
}

export interface ClientPayment {
  importe: number;
  cuenta_destino: string;
}

export interface OperatorProof {
  comprobante_url: string;
  comentario?: string;
}

export interface Invoice {
  id: number;
  invoice_number: string;
  invoice_type: 'Factura' | 'Boleta';
  monto_total: number;
  nubefact_enlace_pdf?: string;
  nubefact_enlace_xml?: string;
  created_at: string;
}

export interface Operation {
  id: number;
  operation_id: string;
  client_id: number;
  client_name: string;
  operation_type: 'Compra' | 'Venta';
  origen: 'sistema' | 'plataforma';
  amount_usd: number;
  exchange_rate: number;
  amount_pen: number;
  source_account?: string;
  destination_account?: string;
  source_bank_name?: string;
  destination_bank_name?: string;
  status: 'Pendiente' | 'En proceso' | 'Completada' | 'Cancelado';
  created_at: string;
  updated_at?: string;
  completed_at?: string;
  time_in_process_minutes?: number;
  client_deposits?: ClientDeposit[];
  client_payments?: ClientPayment[];
  operator_proofs?: OperatorProof[];
  invoices?: Invoice[];
  notes?: string;
  operator_comments?: string;
  assigned_operator_name?: string;
}

// Notification Types
export interface Notification {
  id: string;
  type: 'operation_created' | 'operation_updated' | 'operation_completed' | 'operation_cancelled' | 'documents_approved';
  title: string;
  message: string;
  operation_id?: string;
  read: boolean;
  created_at: string;
}

// API Response Types
export interface ApiResponse<T = any> {
  success: boolean;
  message?: string;
  data?: T;
  error?: string;
}

// Auth Types
export interface LoginCredentials {
  username: string;
  password: string;
}

export interface LoginResponse {
  success: boolean;
  user?: User;
  client?: Client;
  message?: string;
  requires_password_change?: boolean;
}

// Form Types
export interface CreateOperationForm {
  operation_type: 'Compra' | 'Venta';
  amount_usd: string;
  exchange_rate: string;
  source_account: string;
  destination_account: string;
  terms_accepted?: boolean;
  notes?: string;
}
