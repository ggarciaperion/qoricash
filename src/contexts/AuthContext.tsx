import React, { createContext, useState, useContext, useEffect, ReactNode } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { authApi } from '../api/auth';
import { clientsApi } from '../api/clients';
import apiClient from '../api/client';
import { User, Client, LoginCredentials } from '../types';
import { STORAGE_KEYS, API_CONFIG } from '../constants/config';
import socketService from '../services/socketService';
import { notificationService } from '../services/notificationService';

interface AuthContextData {
  user: User | null;
  client: Client | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: (credentials: LoginCredentials, dni: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshClient: () => Promise<void>;
}

const AuthContext = createContext<AuthContextData>({} as AuthContextData);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [client, setClient] = useState<Client | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Configurar servicio de notificaciones
    socketService.configure();

    // Conectar Socket.IO SIEMPRE (incluso sin autenticación) para tipos de cambio
    console.log('📡 Conectando Socket.IO (modo público para tipos de cambio)');
    socketService.connect();

    // NO cargar datos guardados - requiere login cada vez que se abre la app
    // loadStoredData();

    // Limpiar datos de sesión al iniciar la app
    clearStoredSession();

    // Limpiar al desmontar
    return () => {
      socketService.disconnect();
    };
  }, []);

  // Cuando el usuario se autentica, unirse a room específico del cliente
  useEffect(() => {
    if (client && client.dni) {
      console.log('🔔 [AUTH] Cliente autenticado, configurando Socket.IO para DNI:', client.dni);
      console.log('🔌 [AUTH] Socket conectado:', socketService.isConnected());

      // Reconectar con DNI del cliente para recibir notificaciones específicas
      if (socketService.isConnected()) {
        console.log('📡 [AUTH] Uniéndose al room del cliente...');
        socketService.joinClientRoom(client.dni);
      } else {
        console.warn('⚠️ [AUTH] Socket NO conectado, esperando conexión...');
        // Intentar conectar si no está conectado
        socketService.connect(client.dni);
      }

      // Escuchar evento de documentos aprobados para refrescar datos
      const handleDocumentsApproved = async (data: any) => {
        console.log('🎉 [AUTH] ¡EVENTO RECIBIDO! documents_approved:', data);
        console.log('🔄 [AUTH] Refrescando datos del cliente...');
        try {
          await refreshClient();
          console.log('✅ [AUTH] Datos del cliente actualizados después de aprobación KYC');
        } catch (error) {
          console.error('❌ [AUTH] Error refrescando cliente después de KYC:', error);
        }
      };

      console.log('👂 [AUTH] Registrando listener para evento documents_approved...');
      socketService.on('documents_approved', handleDocumentsApproved);
      console.log('✅ [AUTH] Listener registrado exitosamente');

      // Limpiar listener al desmontar
      return () => {
        console.log('🧹 [AUTH] Limpiando listener de documents_approved');
        socketService.off('documents_approved', handleDocumentsApproved);
      };
    }
  }, [client]);

  const clearStoredSession = async () => {
    try {
      // Limpiar todos los datos de sesión al abrir la app
      await AsyncStorage.multiRemove([
        STORAGE_KEYS.USER_DATA,
        STORAGE_KEYS.CLIENT_DATA,
        STORAGE_KEYS.AUTH_TOKEN,
        STORAGE_KEYS.REQUIRES_PASSWORD_CHANGE,
      ]);
      console.log('🧹 [AUTH] Sesión limpiada - requiere nuevo login');
    } catch (error) {
      console.error('❌ [AUTH] Error limpiando sesión:', error);
    } finally {
      setLoading(false);
    }
  };

  // Función anterior comentada - ya no se usa auto-login
  // const loadStoredData = async () => {
  //   try {
  //     const [storedUser, storedClient] = await Promise.all([
  //       AsyncStorage.getItem(STORAGE_KEYS.USER_DATA),
  //       AsyncStorage.getItem(STORAGE_KEYS.CLIENT_DATA),
  //     ]);
  //
  //     if (storedUser) {
  //       setUser(JSON.parse(storedUser));
  //     }
  //
  //     if (storedClient) {
  //       setClient(JSON.parse(storedClient));
  //     }
  //
  //     // Load session cookie
  //     await apiClient.loadSessionCookie();
  //   } catch (error) {
  //     console.error('Error loading stored data:', error);
  //   } finally {
  //     setLoading(false);
  //   }
  // };

  const login = async (credentials: LoginCredentials, dni: string) => {
    try {
      setLoading(true);

      console.log('🔐 [AUTH CONTEXT] Intentando login con DNI:', dni);

      // Login con DNI y contraseña
      const loginResponse = await authApi.login({
        username: dni,
        password: credentials.password || '',
      });

      console.log('✅ [AUTH CONTEXT] Login response:', loginResponse);

      if (!loginResponse.success || !loginResponse.user || !loginResponse.client) {
        console.error('❌ [AUTH CONTEXT] Login fallido:', loginResponse);
        throw new Error(loginResponse.message || 'Error de autenticación');
      }

      const clientData = loginResponse.client;
      const requiresPasswordChange = loginResponse.requires_password_change || false;

      console.log('✅ [AUTH CONTEXT] Cliente autenticado:', clientData.dni);
      console.log('🔐 [AUTH CONTEXT] Requiere cambio de contraseña:', requiresPasswordChange);

      // NO guardar datos en AsyncStorage - sesión temporal solo en memoria
      // La sesión se cierra automáticamente al cerrar la app
      console.log('💾 [AUTH CONTEXT] Sesión temporal - NO se persiste en AsyncStorage');

      console.log('✅ [AUTH CONTEXT] Login exitoso!');

      setUser(loginResponse.user);
      setClient(clientData);

      // Registrar token de push notifications
      try {
        console.log('📲 [AUTH CONTEXT] Registrando token de push notifications...');
        await notificationService.registerForPushNotifications(dni);
      } catch (pushError) {
        console.error('❌ [AUTH CONTEXT] Error registrando push token:', pushError);
        // No bloquear el login si falla el registro de push
      }
    } catch (error: any) {
      console.error('❌ [AUTH CONTEXT] Error en login:', error);
      throw new Error(error.message || 'Error al iniciar sesión');
    } finally {
      setLoading(false);
    }
  };

  const logout = async () => {
    try {
      setLoading(true);

      // Desconectar Socket.IO
      socketService.disconnect();

      await authApi.logout();
      await AsyncStorage.multiRemove([
        STORAGE_KEYS.USER_DATA,
        STORAGE_KEYS.CLIENT_DATA,
        STORAGE_KEYS.AUTH_TOKEN,
      ]);
      setUser(null);
      setClient(null);
    } catch (error) {
      console.error('Error during logout:', error);
      // Clear local data even if API call fails
      socketService.disconnect();
      await AsyncStorage.multiRemove([
        STORAGE_KEYS.USER_DATA,
        STORAGE_KEYS.CLIENT_DATA,
        STORAGE_KEYS.AUTH_TOKEN,
      ]);
      setUser(null);
      setClient(null);
    } finally {
      setLoading(false);
    }
  };

  const refreshClient = async () => {
    try {
      if (!client) return;

      // Usar el nuevo endpoint /me para refrescar datos del cliente
      const response = await apiClient.post(`/api/client/me`, {
        dni: client.dni,
      });

      if (response.success && response.client) {
        const updatedClient = response.client;
        // NO guardar en AsyncStorage - sesión temporal solo en memoria
        setClient(updatedClient);
      }
    } catch (error) {
      console.error('Error refreshing client:', error);
      throw new Error('Error al obtener cliente');
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        client,
        loading,
        isAuthenticated: !!user && !!client,
        login,
        logout,
        refreshClient,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};
