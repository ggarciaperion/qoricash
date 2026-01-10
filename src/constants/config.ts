// API Configuration
export const API_CONFIG = {
  // Cambiar esta URL por la URL de tu servidor en producción
  BASE_URL: 'https://app.qoricash.pe', // ✅ URL correcta del servidor activo
  // BASE_URL: 'https://qoricash-v2.onrender.com', // Base de datos de Render (pruebas)
  // BASE_URL: 'http://192.168.100.3:5000', // Servidor local

  TIMEOUT: 30000,

  // Usuario de plataforma para autenticación
  // NOTA: El backend usa autenticación basada en sesiones (Flask-Login)
  // El login se hace con form data a /login (retorna HTML con redirect)
  // La sesión se mantiene con cookies en las llamadas posteriores a /api/platform/*
  PLATFORM_USERNAME: 'plataforma',
  PLATFORM_PASSWORD: 'plataforma123', // ⚠️ CAMBIAR por el password real de tu usuario plataforma
};

// App Configuration
export const APP_CONFIG = {
  APP_NAME: 'QoriCash',
  VERSION: '1.0.0',
  CURRENCY_SYMBOLS: {
    PEN: 'S/',
    USD: '$',
  },
};

// SocketIO Configuration
export const SOCKET_CONFIG = {
  RECONNECTION: true,
  RECONNECTION_ATTEMPTS: 5,
  RECONNECTION_DELAY: 1000,
};

// Storage Keys
export const STORAGE_KEYS = {
  USER_DATA: '@qoricash_user_data',
  CLIENT_DATA: '@qoricash_client_data',
  AUTH_TOKEN: '@qoricash_auth_token',
  BIOMETRIC_ENABLED: '@qoricash_biometric_enabled',
  REQUIRES_PASSWORD_CHANGE: '@qoricash_requires_password_change',
};

// Operation Status Colors
export const STATUS_COLORS = {
  Pendiente: '#FFC107',
  'En proceso': '#2196F3',
  Completada: '#82C16C',
  Cancelado: '#F44336',
};

// Operation Status Icons
export const STATUS_ICONS = {
  Pendiente: 'clock-outline',
  'En proceso': 'sync',
  Completada: 'check-circle',
  Cancelado: 'close-circle',
};

// QoriCash Bank Accounts (CUENTAS DE EJEMPLO PARA PRUEBAS)
export const QORICASH_ACCOUNTS = {
  USD: {
    BCP: {
      bank_name: 'BCP',
      account_number: '193-2458769-1-25',
      account_type: 'Cuenta Corriente USD',
      cci: '00219300245876912501',
    },
    INTERBANK: {
      bank_name: 'Interbank',
      account_number: '200-3001458796',
      account_type: 'Cuenta Corriente USD',
      cci: '00320013001458796015',
    },
    PICHINCHA: {
      bank_name: 'Pichincha',
      account_number: '30025896547',
      account_type: 'Cuenta Corriente USD',
      cci: '10103000025896547012',
    },
    BANBIF: {
      bank_name: 'BanBif',
      account_number: '7002587493621',
      account_type: 'Cuenta Corriente USD',
      cci: '03870012587493621058',
    },
  },
  PEN: {
    BCP: {
      bank_name: 'BCP',
      account_number: '193-2458769-0-84',
      account_type: 'Cuenta Corriente S/',
      cci: '00219300245876908425',
    },
    INTERBANK: {
      bank_name: 'Interbank',
      account_number: '200-3001458795',
      account_type: 'Cuenta Corriente S/',
      cci: '00320013001458795013',
    },
    PICHINCHA: {
      bank_name: 'Pichincha',
      account_number: '30025896548',
      account_type: 'Cuenta Corriente S/',
      cci: '10103000025896548010',
    },
    BANBIF: {
      bank_name: 'BanBif',
      account_number: '7002587493620',
      account_type: 'Cuenta Corriente S/',
      cci: '03870012587493620056',
    },
  },
};
