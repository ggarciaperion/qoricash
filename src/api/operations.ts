import apiClient from './client';
import { Operation, CreateOperationForm } from '../types';

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
  getOperations: async (clientDni: string): Promise<Operation[]> => {
    try {
      const response = await apiClient.get<{ success: boolean; operations: Operation[] }>(
        `/api/client/my-operations/${clientDni}`
      );
      return response.operations || [];
    } catch (error: any) {
      throw new Error(error.response?.data?.message || 'Error al obtener operaciones');
    }
  },

  /**
   * Get operation detail by ID
   */
  getOperationById: async (operationId: number, clientDni: string): Promise<Operation> => {
    try {
      const response = await apiClient.get<{ success: boolean; operation: Operation }>(
        `/api/client/operation/${operationId}?client_dni=${encodeURIComponent(clientDni)}`
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
    return operationsApi.getOperations(clientDni);
  },

  /**
   * Get operation history (completed, cancelled, and expired operations)
   */
  getHistory: async (clientDni: string): Promise<Operation[]> => {
    const operations = await operationsApi.getOperations(clientDni);
    return operations.filter(
      (op) => op.status !== 'Pendiente' && op.status !== 'En proceso'
    );
  },

  /**
   * Get pending operations
   */
  getPendingOperations: async (clientDni: string): Promise<Operation[]> => {
    const operations = await operationsApi.getOperations(clientDni);
    return operations.filter(
      (op) => op.status === 'pendiente' || op.status === 'en_proceso'
    );
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
