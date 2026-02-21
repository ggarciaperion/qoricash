import apiClient from './client';
import { Operation, CreateOperationForm, ApiResponse } from '../types';

export const operationsApi = {
  /**
   * Create new operation
   */
  createOperation: async (
    clientDni: string,
    operationData: CreateOperationForm
  ): Promise<Operation> => {
    try {
      const payload = {
        client_dni: clientDni,
        operation_type: operationData.operation_type,
        amount_usd: parseFloat(operationData.amount_usd),
        exchange_rate: parseFloat(operationData.exchange_rate),
        source_account: operationData.source_account,
        destination_account: operationData.destination_account,
        notes: operationData.notes || '',
      };

      const response = await apiClient.post<{ success: boolean; operation: Operation }>(
        '/api/client/create-operation',
        payload
      );

      if (!response.success || !response.operation) {
        throw new Error('Error al crear operación');
      }

      return response.operation;
    } catch (error: any) {
      throw new Error(error.response?.data?.message || 'Error al crear operación');
    }
  },

  /**
   * Get operations list for a client by DNI
   */
  getOperations: async (clientDni: string, all: boolean = false): Promise<Operation[]> => {
    try {
      console.log('📡 [OPERATIONS API] Llamando a /api/client/my-operations/' + clientDni);
      const response = await apiClient.get<{ success: boolean; operations: Operation[] }>(
        `/api/client/my-operations/${clientDni}`
      );
      console.log('✅ [OPERATIONS API] Response:', response);
      console.log('✅ [OPERATIONS API] Operations count:', response.operations?.length || 0);

      return response.operations || [];
    } catch (error: any) {
      console.error('❌ [OPERATIONS API] Error:', error);
      console.error('❌ [OPERATIONS API] Error response:', error.response);
      console.error('❌ [OPERATIONS API] Error data:', error.response?.data);
      throw new Error(error.response?.data?.message || 'Error al obtener operaciones');
    }
  },

  /**
   * Get operation detail by ID
   */
  getOperationById: async (operationId: number): Promise<Operation> => {
    try {
      const response = await apiClient.get<{ success: boolean; operation: Operation }>(
        `/api/client/operation/${operationId}`
      );

      if (!response.success || !response.operation) {
        throw new Error('Operación no encontrada');
      }

      return response.operation;
    } catch (error: any) {
      throw new Error(error.response?.data?.message || 'Error al obtener operación');
    }
  },

  /**
   * Upload deposit proof (comprobante de abono)
   */
  uploadDepositProof: async (
    operationId: number,
    depositIndex: number,
    file: FormData
  ): Promise<void> => {
    try {
      // El deposit_index ya está incluido en el FormData desde OperationDetailScreen
      await apiClient.uploadFile(
        `/api/client/upload-deposit-proof/${operationId}`,
        file
      );
    } catch (error: any) {
      throw new Error(error.response?.data?.message || 'Error al subir comprobante');
    }
  },

  /**
   * Get today's operations
   */
  getTodayOperations: async (clientDni: string): Promise<Operation[]> => {
    try {
      const operations = await this.getOperations(clientDni, false);
      // Ya vienen filtradas por el backend
      return operations;
    } catch (error: any) {
      throw new Error(error.response?.data?.message || 'Error al obtener operaciones de hoy');
    }
  },

  /**
   * Get operation history (completed, cancelled, and expired operations)
   */
  getHistory: async (clientDni: string): Promise<Operation[]> => {
    try {
      const operations = await this.getOperations(clientDni, true);
      // Filtrar solo operaciones finalizadas (no pendientes ni en proceso)
      return operations.filter((op) =>
        op.status !== 'Pendiente' && op.status !== 'En proceso'
      );
    } catch (error: any) {
      throw new Error(error.response?.data?.message || 'Error al obtener historial');
    }
  },

  /**
   * Get pending operations
   */
  getPendingOperations: async (clientDni: string): Promise<Operation[]> => {
    try {
      const operations = await this.getOperations(clientDni, false);
      return operations.filter((op) => op.status === 'pendiente' || op.status === 'en_proceso');
    } catch (error: any) {
      throw new Error(error.response?.data?.message || 'Error al obtener operaciones pendientes');
    }
  },

  /**
   * Update operation status to "En proceso" (temporary local update)
   */
  updateOperationStatus: async (
    operationId: number,
    status: string,
    transferCode?: string
  ): Promise<void> => {
    try {
      // Intentar actualizar en el backend (si el endpoint existe)
      await apiClient.put(`/api/client/operation/${operationId}/status`, {
        status,
        transfer_code: transferCode,
      });
    } catch (error: any) {
      console.warn('⚠️ No se pudo actualizar en el backend, solo local:', error.message);
      // No lanzar error, continuar con actualización local
    }
  },
};
