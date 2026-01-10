import apiClient from './client';
import { LoginCredentials, LoginResponse, User } from '../types';

export const authApi = {
  /**
   * Login with DNI and password
   */
  login: async (credentials: LoginCredentials): Promise<LoginResponse> => {
    try {
      console.log('📡 [CLIENT AUTH] Enviando login con DNI:', credentials.username);

      // Login con DNI y contraseña
      const response = await apiClient.post<LoginResponse>('/api/client/login', {
        dni: credentials.username,
        password: credentials.password || '',
      });

      console.log('📡 [CLIENT AUTH] Response:', response);

      if (!response.success || !response.client) {
        throw new Error(response.message || 'Error al iniciar sesión');
      }

      // Crear objeto User a partir del cliente
      const user: User = {
        id: response.client.id,
        username: response.client.dni,
        role: 'Cliente',
      };

      console.log('✅ [CLIENT AUTH] Login exitoso para cliente:', response.client.dni);

      return {
        success: true,
        message: response.message || 'Login exitoso',
        user,
        client: response.client,
        requires_password_change: response.requires_password_change,
      };
    } catch (error: any) {
      console.error('❌ [CLIENT AUTH] Error en login:', error);
      console.error('❌ [CLIENT AUTH] Error response:', error.response?.data);

      const errorMsg = error.response?.data?.message || error.message || 'Error al iniciar sesión';
      throw new Error(errorMsg);
    }
  },

  /**
   * Logout current user
   */
  logout: async (): Promise<void> => {
    try {
      // Intentar cerrar sesión en el servidor (opcional, puede fallar)
      await apiClient.get('/auth/logout').catch(() => {
        // Ignorar error del servidor - el logout local es suficiente
        console.log('Logout del servidor no disponible, solo limpiando sesión local');
      });
      await apiClient.clearSession();
    } catch (error: any) {
      // Limpiar sesión local incluso si hay error
      await apiClient.clearSession();
    }
  },

  /**
   * Change password
   */
  changePassword: async (oldPassword: string, newPassword: string): Promise<void> => {
    try {
      await apiClient.post('/auth/change_password', {
        old_password: oldPassword,
        new_password: newPassword,
      });
    } catch (error: any) {
      throw new Error(error.response?.data?.message || 'Error al cambiar contraseña');
    }
  },
};
