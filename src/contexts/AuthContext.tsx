import React, { createContext, useState, useContext, useEffect, ReactNode } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { authApi } from '../api/auth';
import apiClient from '../api/client';
import { User, Client, LoginCredentials } from '../types';
import { STORAGE_KEYS } from '../constants/config';
import socketService from '../services/socketService';
import { notificationService } from '../services/notificationService';

interface AuthContextData {
  user: User | null;
  client: Client | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: (credentials: LoginCredentials, dni: string) => Promise<void>;
  loginWithGoogle: (clientData: Client) => Promise<void>;
  logout: () => Promise<void>;
  refreshClient: () => Promise<void>;
}

const AuthContext = createContext<AuthContextData>({} as AuthContextData);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [client, setClient] = useState<Client | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    socketService.configure();
    socketService.connect();
    loadStoredData();

    return () => {
      socketService.disconnect();
    };
  }, []);

  // Cuando el usuario se autentica, unirse a room específico del cliente
  useEffect(() => {
    if (client && client.dni) {
      if (socketService.isConnected()) {
        socketService.joinClientRoom(client.dni);
      } else {
        socketService.connect(client.dni);
      }

      const handleDocumentsApproved = async (_data: any) => {
        try {
          await refreshClient();
        } catch (error) {
          console.error('[AUTH] Error refrescando cliente después de KYC:', error);
        }
      };

      socketService.on('documents_approved', handleDocumentsApproved);

      return () => {
        socketService.off('documents_approved', handleDocumentsApproved);
      };
    }
  }, [client]);

  const loadStoredData = async () => {
    try {
      const [storedUser, storedClient] = await Promise.all([
        AsyncStorage.getItem(STORAGE_KEYS.USER_DATA),
        AsyncStorage.getItem(STORAGE_KEYS.CLIENT_DATA),
      ]);

      if (storedClient && storedUser) {
        const cachedClient: Client = JSON.parse(storedClient);
        const cachedUser: User = JSON.parse(storedUser);

        // Validar sesión contra el backend con datos frescos
        try {
          const response = await apiClient.post(`/api/client/me`, { dni: cachedClient.dni });
          if (response.success && response.client) {
            setClient(response.client);
            setUser(cachedUser);
          } else {
            await AsyncStorage.multiRemove([STORAGE_KEYS.USER_DATA, STORAGE_KEYS.CLIENT_DATA]);
          }
        } catch {
          // Sin conexión: restaurar datos cacheados para permitir uso offline básico
          setClient(cachedClient);
          setUser(cachedUser);
        }
      }
    } catch (error) {
      console.error('[AUTH] Error restaurando sesión:', error);
      await AsyncStorage.multiRemove([STORAGE_KEYS.USER_DATA, STORAGE_KEYS.CLIENT_DATA]);
    } finally {
      setLoading(false);
    }
  };

  const login = async (credentials: LoginCredentials, dni: string) => {
    // NOTE: We intentionally do NOT call setLoading(true) here.
    // setLoading(true) causes AppNavigator to return null, which unmounts
    // NavigationContainer and resets the nav stack to PublicCalculatorScreen
    // on failure. The LoginLoadingScreen overlay handles the visual feedback.
    try {
      const loginResponse = await authApi.login({
        username: dni,
        password: credentials.password || '',
      });

      if (!loginResponse.success || !loginResponse.user || !loginResponse.client) {
        throw new Error(loginResponse.message || 'Error de autenticación');
      }

      const clientData = loginResponse.client;
      const requiresPasswordChange = loginResponse.requires_password_change || false;

      // Persistir sesión en AsyncStorage para auto-login en próxima apertura
      await AsyncStorage.multiSet([
        [STORAGE_KEYS.CLIENT_DATA, JSON.stringify(clientData)],
        [STORAGE_KEYS.USER_DATA, JSON.stringify(loginResponse.user)],
      ]);

      setUser(loginResponse.user);
      setClient(clientData);

      if (requiresPasswordChange) {
        await AsyncStorage.setItem(STORAGE_KEYS.REQUIRES_PASSWORD_CHANGE, 'true');
      }

      // Registrar token de push notifications
      try {
        await notificationService.registerForPushNotifications(dni);
      } catch (pushError) {
        console.error('[AUTH] Error registrando push token:', pushError);
      }
    } catch (error: any) {
      throw new Error(error.message || 'Error al iniciar sesión');
    }
  };

  const loginWithGoogle = async (clientData: Client) => {
    try {
      const googleUser: User = {
        id: clientData.id,
        username: clientData.dni,
        role: 'Cliente',
      };

      await AsyncStorage.multiSet([
        [STORAGE_KEYS.CLIENT_DATA, JSON.stringify(clientData)],
        [STORAGE_KEYS.USER_DATA, JSON.stringify(googleUser)],
      ]);

      setUser(googleUser);
      setClient(clientData);

      try {
        await notificationService.registerForPushNotifications(clientData.dni);
      } catch (pushError) {
        console.error('[AUTH] Error registrando push token (Google):', pushError);
      }
    } catch (error: any) {
      throw new Error(error.message || 'Error al iniciar sesión con Google');
    }
  };

  const logout = async () => {
    try {
      socketService.disconnect();
      await authApi.logout();
    } catch (error) {
      console.error('[AUTH] Error en logout:', error);
    } finally {
      socketService.disconnect();
      await AsyncStorage.multiRemove([
        STORAGE_KEYS.USER_DATA,
        STORAGE_KEYS.CLIENT_DATA,
        STORAGE_KEYS.AUTH_TOKEN,
        STORAGE_KEYS.REQUIRES_PASSWORD_CHANGE,
      ]);
      setUser(null);
      setClient(null);
    }
  };

  const refreshClient = async () => {
    try {
      if (!client) return;

      const response = await apiClient.post(`/api/client/me`, { dni: client.dni });

      if (response.success && response.client) {
        const updatedClient = response.client;
        await AsyncStorage.setItem(STORAGE_KEYS.CLIENT_DATA, JSON.stringify(updatedClient));
        setClient(updatedClient);
      }
    } catch (error) {
      console.error('[AUTH] Error refrescando cliente:', error);
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
        loginWithGoogle,
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
