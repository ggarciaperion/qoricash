import apiClient from './client';
import { Client, ApiResponse } from '../types';

export const clientsApi = {
  /**
   * Get client by DNI
   */
  getClientByDni: async (dni: string): Promise<Client> => {
    try {
      const response = await apiClient.get<{ success: boolean; client: Client }>(
        `/api/platform/get-client/${dni}`
      );
      if (!response.success || !response.client) {
        throw new Error('Cliente no encontrado');
      }
      return response.client;
    } catch (error: any) {
      throw new Error(error.response?.data?.message || 'Error al obtener cliente');
    }
  },

  /**
   * Get client by ID
   */
  getClientById: async (clientId: number): Promise<Client> => {
    try {
      const response = await apiClient.get<{ success: boolean; client: Client }>(
        `/clients/api/${clientId}`
      );
      if (!response.success || !response.client) {
        throw new Error('Cliente no encontrado');
      }
      return response.client;
    } catch (error: any) {
      throw new Error(error.response?.data?.message || 'Error al obtener cliente');
    }
  },

  /**
   * Get client statistics
   */
  getClientStats: async (clientId: number): Promise<any> => {
    try {
      const response = await apiClient.get<ApiResponse>(`/clients/api/${clientId}/stats`);
      return response.data;
    } catch (error: any) {
      // If endpoint doesn't exist, return default stats
      return {
        total_operations: 0,
        total_usd_traded: 0,
        completed_operations: 0,
        pending_operations: 0,
      };
    }
  },

  /**
   * Register new client from app
   */
  registerClient: async (clientData: FormData): Promise<Client> => {
    try {
      const response = await apiClient.uploadFile<{ success: boolean; client: Client }>(
        '/api/platform/register-client',
        clientData
      );
      if (!response.success || !response.client) {
        throw new Error('Error al registrar cliente');
      }
      return response.client;
    } catch (error: any) {
      throw new Error(error.response?.data?.message || 'Error al registrar cliente');
    }
  },
};
