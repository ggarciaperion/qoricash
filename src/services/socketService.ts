import { io, Socket } from 'socket.io-client';
import * as Notifications from 'expo-notifications';
import { API_CONFIG } from '../constants/config';
import { EventEmitter } from '../utils/EventEmitter';

class SocketService {
  private socket: Socket | null = null;
  private clientDni: string | null = null;
  private pendingListeners: Map<string, Array<(data: any) => void>> = new Map();
  private eventEmitter: EventEmitter = new EventEmitter();

  // Configurar el manejador de notificaciones
  configure() {
    Notifications.setNotificationHandler({
      handleNotification: async () => ({
        shouldShowAlert: true,
        shouldPlaySound: false,
        shouldSetBadge: true,
      }),
    });
  }

  // Conectar al servidor Socket.IO
  connect(clientDni?: string) {
    if (this.socket?.connected) {
      console.log('✅ Socket ya está conectado');

      // Si se proporciona DNI y el socket ya está conectado, unirse al room
      if (clientDni && clientDni !== this.clientDni) {
        this.joinClientRoom(clientDni);
      }
      return;
    }

    if (clientDni) {
      this.clientDni = clientDni;
    }

    // Usar la URL base del servidor
    const socketUrl = API_CONFIG.BASE_URL;

    console.log('Conectando a Socket.IO:', socketUrl);

    this.socket = io(socketUrl, {
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionAttempts: 5,
    });

    this.socket.on('connect', () => {
      console.log('✅ [SOCKET] Socket.IO conectado exitosamente');
      console.log('[SOCKET] ID de socket:', this.socket?.id);

      // Join al room del cliente para recibir notificaciones específicas
      if (this.clientDni) {
        console.log(`📡 [SOCKET] Cliente DNI encontrado: ${this.clientDni}, uniéndose a room...`);
        this.socket?.emit('join_client_room', { dni: this.clientDni });
        console.log(`✅ [SOCKET] Evento 'join_client_room' emitido para client_${this.clientDni}`);
      } else {
        console.log('ℹ️ [SOCKET] No hay DNI de cliente, esperando autenticación...');
      }

      // Registrar listeners pendientes
      console.log('[SOCKET] Registrando listeners pendientes...');
      this.registerPendingListeners();
    });

    this.socket.on('disconnect', () => {
      console.log('❌ Socket.IO desconectado');
    });

    this.socket.on('connect_error', (error) => {
      console.error('Error de conexión Socket.IO:', error);
    });

    // Escuchar evento de operación actualizada
    this.socket.on('operacion_actualizada', (data) => {
      console.log('📡 Operación actualizada:', data);
      this.handleOperationUpdated(data);
    });

    // Escuchar evento de operación completada
    this.socket.on('operacion_completada', (data) => {
      console.log('📡 Operación completada:', data);
      this.handleOperationCompleted(data);
    });

    // Escuchar evento de nueva operación
    this.socket.on('nueva_operacion', (data) => {
      console.log('📡 Nueva operación:', data);
    });

    // Escuchar evento de tipos de cambio actualizados
    this.socket.on('tipos_cambio_actualizados', (data) => {
      console.log('📡 SocketService: Tipos de cambio actualizados recibidos:', data);
      // Mostrar notificación de tipos de cambio actualizados
      this.handleExchangeRatesUpdated(data);
    });

    // Escuchar evento de documentos aprobados
    this.socket.on('documents_approved', (data) => {
      console.log('🎉 [SOCKET] ¡EVENTO RECIBIDO EN SOCKET! documents_approved:', data);
      console.log('[SOCKET] Cliente DNI en evento:', data.client_dni);
      console.log('[SOCKET] Procesando notificación...');
      this.handleDocumentsApproved(data);
    });

    // Escuchar evento de operación expirada
    this.socket.on('operation_expired', (data) => {
      console.log('📡 Operación expirada:', data);
      this.handleOperationExpired(data);
    });
  }

  // Desconectar Socket.IO
  disconnect() {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
      this.clientDni = null;
      console.log('Socket.IO desconectado manualmente');
    }
  }

  // Unirse al room del cliente (útil cuando se autentica después de conectar)
  joinClientRoom(clientDni: string) {
    if (!this.socket?.connected) {
      console.error('❌ [SOCKET] Socket NO conectado, no se puede unir a room');
      console.log('[SOCKET] Intentando conectar socket primero...');
      this.connect(clientDni);
      return;
    }

    console.log(`📡 [SOCKET] Uniéndose al room del cliente: client_${clientDni}`);
    this.clientDni = clientDni;
    this.socket.emit('join_client_room', { dni: clientDni });
    console.log(`✅ [SOCKET] Evento 'join_client_room' emitido para DNI: ${clientDni}`);
  }

  // Manejar operación actualizada
  private async handleOperationUpdated(data: any) {
    await this.showNotification(
      'Operación Actualizada',
      `La operación ${data.operation_id} cambió a: ${data.status}`
    );
  }

  // Manejar operación completada
  private async handleOperationCompleted(data: any) {
    await this.showNotification(
      '✅ Operación Completada',
      `Tu operación ${data.operation_id} ha sido completada exitosamente. Tu pago ha sido procesado`
    );
  }

  // Manejar tipos de cambio actualizados
  private async handleExchangeRatesUpdated(data: any) {
    await this.showNotification(
      '💱 Tipos de Cambio Actualizados',
      `Compra: S/ ${data.compra.toFixed(3)} | Venta: S/ ${data.venta.toFixed(3)}`
    );
  }

  // Manejar documentos aprobados
  private async handleDocumentsApproved(data: any) {
    await this.showNotification(
      data.title || '✅ Cuenta Activada',
      data.message || 'Tus documentos han sido aprobados. ¡Ya puedes realizar operaciones!'
    );
  }

  // Manejar operación expirada
  private async handleOperationExpired(data: any) {
    console.log('⏱️ [SOCKET] Operación expirada detectada:', data.operation_id);

    await this.showNotification(
      '⏱️ Operación Expirada',
      `La operación ${data.operation_id} ha expirado por falta de transferencia. Puedes crear una nueva operación.`
    );

    // Emitir evento para que HistoryScreen refresque inmediatamente
    console.log('📡 [SOCKET] Emitiendo evento refresh_operations_list');
    this.eventEmitter.emit('refresh_operations_list', {
      reason: 'operation_expired',
      operation_id: data.operation_id
    });
  }

  // Mostrar notificación local
  private async showNotification(title: string, body: string) {
    try {
      await Notifications.scheduleNotificationAsync({
        content: {
          title,
          body,
          sound: true,
        },
        trigger: null, // Mostrar inmediatamente
      });
    } catch (error) {
      console.error('Error mostrando notificación:', error);
    }
  }

  // Registrar listeners pendientes cuando se conecte el socket
  private registerPendingListeners() {
    if (!this.socket) return;

    console.log(`📡 Registrando ${this.pendingListeners.size} listeners pendientes...`);
    this.pendingListeners.forEach((callbacks, event) => {
      callbacks.forEach(callback => {
        this.socket?.on(event, callback);
        console.log(`✅ Listener registrado para evento: ${event}`);
      });
    });
  }

  // Emitir evento personalizado (para actualizar UI)
  on(event: string, callback: (data: any) => void) {
    if (this.socket?.connected) {
      // Si ya está conectado, registrar inmediatamente
      this.socket.on(event, callback);
      console.log(`✅ Listener inmediato registrado para evento: ${event}`);
    } else {
      // Si no está conectado, agregar a pendientes
      if (!this.pendingListeners.has(event)) {
        this.pendingListeners.set(event, []);
      }
      this.pendingListeners.get(event)!.push(callback);
      console.log(`⏳ Listener pendiente agregado para evento: ${event}`);
    }
  }

  // Remover listener
  off(event: string, callback?: (data: any) => void) {
    // Remover del socket si está conectado
    if (this.socket) {
      this.socket.off(event, callback);
    }

    // Remover de pendientes si existe
    if (callback && this.pendingListeners.has(event)) {
      const callbacks = this.pendingListeners.get(event)!;
      const index = callbacks.indexOf(callback);
      if (index > -1) {
        callbacks.splice(index, 1);
        if (callbacks.length === 0) {
          this.pendingListeners.delete(event);
        }
      }
    }
  }

  // Obtener estado de conexión
  isConnected(): boolean {
    return this.socket?.connected || false;
  }

  // Suscribirse a eventos internos (para comunicación con componentes)
  subscribeToEvent(event: string, callback: (data: any) => void) {
    this.eventEmitter.on(event, callback);
    console.log(`✅ [SOCKET] Componente suscrito al evento: ${event}`);
  }

  // Desuscribirse de eventos internos
  unsubscribeFromEvent(event: string, callback: (data: any) => void) {
    this.eventEmitter.off(event, callback);
    console.log(`❌ [SOCKET] Componente desuscrito del evento: ${event}`);
  }
}

export default new SocketService();
