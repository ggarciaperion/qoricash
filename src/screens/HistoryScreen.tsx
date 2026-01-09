import React, { useState, useEffect } from 'react';
import { View, StyleSheet, FlatList, RefreshControl, TouchableOpacity, Alert, Modal, KeyboardAvoidingView, Platform, ScrollView, AppState, AppStateStatus } from 'react-native';
import {
  Text,
  ActivityIndicator,
  Card,
  Chip,
  Divider,
  IconButton,
  Icon,
  TextInput,
  Button,
} from 'react-native-paper';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useAuth } from '../contexts/AuthContext';
import { Operation } from '../types';
import axios from 'axios';
import { API_CONFIG } from '../constants/config';
import socketService from '../services/socketService';
import { Colors } from '../constants/colors';
import { formatDateTime } from '../utils/formatters';
import { useNavigation, CommonActions } from '@react-navigation/native';
import { GlobalStyles } from '../styles/globalStyles';
import { CustomModal } from '../components/CustomModal';
import { KeyboardAwareScrollView } from '../components/KeyboardAwareScrollView';

// TEMPORAL: Configurado a 1 minuto para pruebas (producción: 15)
const OPERATION_TIMEOUT_MINUTES = 1;
const LOCAL_OPERATIONS_CACHE_KEY = '@qoricash_local_operations_cache';

export const HistoryScreen: React.FC<{ route?: any }> = ({ route }) => {
  const { client } = useAuth();
  const navigation = useNavigation<any>();
  const [operations, setOperations] = useState<Operation[]>([]);
  const [filteredOperations, setFilteredOperations] = useState<Operation[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState<'pending' | 'completed'>(route?.params?.initialTab || 'pending');
  const [currentTime, setCurrentTime] = useState(new Date());
  const [cancelDialogVisible, setCancelDialogVisible] = useState(false);
  const [cancelReason, setCancelReason] = useState('');
  const [operationToCancel, setOperationToCancel] = useState<Operation | null>(null);
  const [canceling, setCanceling] = useState(false);

  // Cargar operaciones al montar
  useEffect(() => {
    if (client) {
      fetchHistory();
    }
  }, [client]);

  // Recargar cuando la pantalla se enfoca
  useEffect(() => {
    const unsubscribe = navigation.addListener('focus', () => {
      if (client) {
        console.log('🔄 Historial enfocado - Refrescando...');
        fetchHistory();
      }
    });

    return unsubscribe;
  }, [navigation, client]);

  // Actualizar operaciones cada 30 segundos
  useEffect(() => {
    const interval = setInterval(() => {
      if (client) {
        fetchHistory();
      }
    }, 30000);

    return () => clearInterval(interval);
  }, [client]);

  // Escuchar eventos de Socket.IO
  useEffect(() => {
    const handleUpdate = () => {
      console.log('🔔 Operación actualizada - Refrescando historial');
      if (client) {
        fetchHistory();
      }
    };

    socketService.on('operacion_completada', handleUpdate);
    socketService.on('operacion_actualizada', handleUpdate);
    socketService.on('operacion_cancelada', handleUpdate);
    socketService.on('nueva_operacion', handleUpdate);
    socketService.on('operation_expired', handleUpdate); // ← NUEVO

    return () => {
      socketService.off('operacion_completada', handleUpdate);
      socketService.off('operacion_actualizada', handleUpdate);
      socketService.off('operacion_cancelada', handleUpdate);
      socketService.off('nueva_operacion', handleUpdate);
      socketService.off('operation_expired', handleUpdate); // ← NUEVO
    };
  }, [client]);

  // Re-fetch al volver del background
  useEffect(() => {
    const subscription = AppState.addEventListener('change', (nextAppState: AppStateStatus) => {
      if (nextAppState === 'active' && client) {
        console.log('📱 App volvió al foreground - Refrescando historial');
        fetchHistory();
      }
    });

    return () => {
      subscription.remove();
    };
  }, [client]);

  // Actualizar contador cada 3 segundos (en lugar de cada segundo)
  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentTime(new Date());
    }, 3000);

    return () => clearInterval(interval);
  }, []);

  // Filtrar operaciones cuando cambia el tab activo
  useEffect(() => {
    let filtered = operations;

    // Filtrar por tab
    if (activeTab === 'pending') {
      filtered = operations.filter(
        (op) => op.status === 'Pendiente' || op.status === 'En proceso'
      );
    } else {
      filtered = operations.filter(
        (op) => op.status === 'Completada' || op.status === 'Cancelado' || op.status === 'Expirada'
      );
    }

    setFilteredOperations(filtered);
  }, [operations, activeTab, currentTime]);

  const fetchHistory = async () => {
    if (!client) return;

    try {
      setLoading(true);
      console.log('📋 Cargando historial para DNI:', client.dni);

      // Obtener todas las operaciones del cliente
      const response = await axios.get<{ success: boolean; operations: Operation[] }>(
        `${API_CONFIG.BASE_URL}/api/client/my-operations/${client.dni}`
      );

      if (response.data.success) {
        console.log('✅ Total operaciones:', response.data.operations.length);

        // Los datos del servidor SIEMPRE tienen prioridad
        const operations = response.data.operations;

        // Limpiar caché local después de sincronizar con el servidor
        // Esto evita que datos obsoletos locales sobrescriban datos frescos del servidor
        try {
          await AsyncStorage.removeItem(LOCAL_OPERATIONS_CACHE_KEY);
          console.log('🗑️ Caché local limpiado después de sincronizar con servidor');
        } catch (cacheError) {
          console.warn('⚠️ Error limpiando caché:', cacheError);
        }

        setOperations(operations);
      }
    } catch (error: any) {
      console.error('❌ Error cargando historial:', error);
      console.error('❌ Error response:', error.response?.data);
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchHistory();
    setRefreshing(false);
  };

  const handleOperationPress = (operation: Operation) => {
    console.log('📱 handleOperationPress llamado para:', operation.operation_id, 'Estado:', operation.status);

    try {
      // Si está pendiente (recién creada), ir a Transfer
      if (operation.status === 'Pendiente') {
        console.log('➡️ Navegando a Transfer');
        navigation.dispatch(
          CommonActions.navigate({
            name: 'Transfer',
            params: { operation },
          })
        );
      }
      // Si está en proceso (comprobante enviado), ir a Receive
      else if (operation.status === 'En proceso') {
        console.log('➡️ Navegando a Receive');
        navigation.dispatch(
          CommonActions.navigate({
            name: 'Receive',
            params: { operation },
          })
        );
      }
      // Si está completada o cancelada, ir a detalle
      else {
        console.log('➡️ Navegando a OperationDetail');
        navigation.dispatch(
          CommonActions.navigate({
            name: 'OperationDetail',
            params: { operationId: operation.id },
          })
        );
      }
    } catch (error) {
      console.error('❌ Error navegando:', error);
    }
  };

  const handleCancelOperation = (operation: Operation) => {
    setOperationToCancel(operation);
    setCancelReason('');
    setCancelDialogVisible(true);
  };

  const handleConfirmCancel = async () => {
    if (!cancelReason.trim()) {
      Alert.alert('Error', 'Debes proporcionar un motivo para cancelar la operación');
      return;
    }

    if (!operationToCancel) return;

    try {
      setCanceling(true);
      console.log('Cancelando operación:', operationToCancel.operation_id);

      await axios.post(`${API_CONFIG.BASE_URL}/api/client/cancel-operation/${operationToCancel.id}`, {
        cancellation_reason: cancelReason.trim(),
      });

      // Actualizar caché local
      try {
        const cacheStr = await AsyncStorage.getItem(LOCAL_OPERATIONS_CACHE_KEY);
        const cache = cacheStr ? JSON.parse(cacheStr) : {};
        cache[operationToCancel.id] = {
          ...operationToCancel,
          status: 'Cancelado',
          cancellation_reason: cancelReason.trim(),
        };
        await AsyncStorage.setItem(LOCAL_OPERATIONS_CACHE_KEY, JSON.stringify(cache));
      } catch (cacheError) {
        console.warn('⚠️ Error actualizando caché:', cacheError);
      }

      // Cerrar diálogo y refrescar
      setCancelDialogVisible(false);
      setCancelReason('');
      setOperationToCancel(null);
      await fetchHistory();

      Alert.alert('Éxito', 'La operación ha sido cancelada correctamente');
    } catch (error: any) {
      console.error('❌ Error cancelando operación:', error);
      Alert.alert('Error', error.response?.data?.message || 'No se pudo cancelar la operación');
    } finally {
      setCanceling(false);
    }
  };

  const handleCloseCancelDialog = () => {
    setCancelDialogVisible(false);
    setCancelReason('');
    setOperationToCancel(null);
  };

  const calculateTimeRemaining = (createdAt: string) => {
    const createdDate = new Date(createdAt);
    const expirationDate = new Date(createdDate.getTime() + OPERATION_TIMEOUT_MINUTES * 60000);
    const now = currentTime;
    const diffMs = expirationDate.getTime() - now.getTime();

    if (diffMs <= 0) {
      return { expired: true, minutes: 0, seconds: 0 };
    }

    const minutes = Math.floor(diffMs / 60000);
    const seconds = Math.floor((diffMs % 60000) / 1000);
    return { expired: false, minutes, seconds };
  };

  const getStatusConfig = (status: string) => {
    switch (status) {
      case 'Pendiente':
        return {
          color: '#FFC107',
          icon: 'clock-outline',
          text: 'Pendiente',
        };
      case 'En proceso':
        return {
          color: '#2196F3',
          icon: 'sync',
          text: 'En Proceso',
        };
      case 'Completada':
        return {
          color: '#82C16C',
          icon: 'check-circle',
          text: 'Completada',
        };
      case 'Cancelado':
        return {
          color: '#F44336',
          icon: 'close-circle',
          text: 'Cancelada',
        };
      case 'Expirada':
        return {
          color: '#9E9E9E',
          icon: 'clock-alert-outline',
          text: 'Expirada',
        };
      default:
        return {
          color: '#757575',
          icon: 'information',
          text: status,
        };
    }
  };

  const OperationCard: React.FC<{ operation: Operation; onPress: (op: Operation) => void }> = ({ operation, onPress }) => {
    const statusConfig = getStatusConfig(operation.status);
    const isPending = operation.status === 'Pendiente' || operation.status === 'En proceso';
    const timeRemaining = operation.status === 'Pendiente' ? calculateTimeRemaining(operation.created_at) : null;

    return (
      <Card style={styles.operationCard}>
        <Card.Content>
          <View style={styles.operationHeader}>
            <View style={styles.operationInfo}>
              <Text variant="labelSmall" style={styles.operationLabel}>
                {operation.operation_id}
              </Text>
              <Text variant="titleMedium" style={styles.operationAmount}>
                {operation.operation_type === 'Compra'
                  ? `$${operation.amount_usd.toFixed(2)}`
                  : `S/ ${operation.amount_pen.toFixed(2)}`}
              </Text>
              <Text variant="bodySmall" style={styles.operationType}>
                {operation.operation_type} • T.C. {operation.exchange_rate.toFixed(3)}
              </Text>
              <Text variant="bodySmall" style={styles.operationDate}>
                {formatDateTime(operation.created_at)}
              </Text>
            </View>

            <View style={styles.statusContainer}>
              <View style={styles.statusChipContainer}>
                <Chip
                  mode="flat"
                  style={[styles.statusChip, { backgroundColor: statusConfig.color }]}
                  textStyle={{ color: '#FFFFFF', fontWeight: 'bold', fontSize: 12 }}
                  icon={statusConfig.icon}
                >
                  {statusConfig.text}
                </Chip>
                {operation.status === 'Pendiente' && timeRemaining && !timeRemaining.expired && (
                  <View style={styles.countdownContainerChip}>
                    <Icon source="timer-sand" size={14} color="#F44336" />
                    <Text style={styles.countdownText}>
                      Expira en {timeRemaining.minutes}:{timeRemaining.seconds.toString().padStart(2, '0')}
                    </Text>
                  </View>
                )}
              </View>
            </View>
          </View>

          {operation.status === 'Pendiente' && (
            <>
              <Divider style={styles.divider} />
              <TouchableOpacity
                style={styles.cancelButton}
                onPress={() => handleCancelOperation(operation)}
                activeOpacity={0.7}
              >
                <Icon source="close-circle-outline" size={20} color="#F44336" />
                <Text style={styles.cancelButtonText}>Cancelar operación</Text>
              </TouchableOpacity>
            </>
          )}

          <Divider style={styles.divider} />
        </Card.Content>
        <TouchableOpacity
          onPress={() => {
            console.log('🔘 Botón presionado:', operation.operation_id, operation.status);
            onPress(operation);
          }}
          style={styles.detailButton}
          activeOpacity={0.7}
        >
          <View style={styles.detailButtonContent}>
            <Icon source="eye" size={20} color="#FFFFFF" />
            <Text style={styles.detailButtonText}>Ver detalles</Text>
          </View>
        </TouchableOpacity>
      </Card>
    );
  };

  if (loading && operations.length === 0) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color={Colors.primary} />
        <Text style={styles.loadingText}>Cargando historial...</Text>
      </View>
    );
  }

  const pendingCount = operations.filter(
    (op) => op.status === 'Pendiente' || op.status === 'En proceso'
  ).length;
  const completedCount = operations.filter(
    (op) => op.status === 'Completada' || op.status === 'Cancelado' || op.status === 'Expirada'
  ).length;

  return (
    <View style={styles.container}>
      {/* Custom Tabs */}
      <View style={styles.tabsContainer}>
        <View style={styles.customTabsContainer}>
          <TouchableOpacity
            style={[
              styles.customTab,
              styles.customTabLeft,
              activeTab === 'pending' && styles.customTabActive,
            ]}
            onPress={() => setActiveTab('pending')}
            activeOpacity={0.8}
          >
            <Text
              style={[
                styles.customTabText,
                activeTab === 'pending' && styles.customTabTextActive,
              ]}
            >
              En Curso ({pendingCount})
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[
              styles.customTab,
              styles.customTabRight,
              activeTab === 'completed' && styles.customTabActive,
            ]}
            onPress={() => setActiveTab('completed')}
            activeOpacity={0.8}
          >
            <Text
              style={[
                styles.customTabText,
                activeTab === 'completed' && styles.customTabTextActive,
              ]}
            >
              Finalizadas ({completedCount})
            </Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* List */}
      <FlatList
        data={filteredOperations}
        keyExtractor={(item) => item.id.toString()}
        renderItem={({ item }) => <OperationCard operation={item} onPress={handleOperationPress} />}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <IconButton
              icon={activeTab === 'pending' ? 'clock-outline' : 'history'}
              size={60}
              iconColor="#BDBDBD"
            />
            <Text variant="headlineSmall" style={styles.emptyTitle}>
              {activeTab === 'pending' ? 'Sin operaciones en curso' : 'Sin historial'}
            </Text>
            <Text variant="bodyLarge" style={styles.emptyText}>
              {activeTab === 'pending'
                ? 'Inicia una nueva operación desde el inicio'
                : 'Aquí aparecerán tus operaciones completadas y canceladas'}
            </Text>
          </View>
        }
        contentContainerStyle={
          filteredOperations.length === 0 ? styles.emptyList : styles.listContent
        }
      />

      {/* Cancel Operation Modal */}
      <Modal
        visible={cancelDialogVisible}
        transparent
        animationType="fade"
        onRequestClose={handleCloseCancelDialog}
      >
        <TouchableOpacity
          activeOpacity={1}
          style={styles.modalOverlay}
          onPress={handleCloseCancelDialog}
        >
          <KeyboardAvoidingView
            behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
            style={styles.modalKeyboardAvoid}
          >
            <TouchableOpacity activeOpacity={1} onPress={(e) => e.stopPropagation()}>
              <View style={styles.modalContainer}>
                {/* Header */}
                <View style={styles.modalHeader}>
                  <Icon source="alert-circle-outline" size={48} color="#F44336" />
                  <Text style={styles.modalTitle}>Cancelar Operación</Text>
                  <Text style={styles.modalSubtitle}>
                    Por favor, indica el motivo de la cancelación
                  </Text>
                </View>

                {/* Input */}
                <View style={styles.modalBody}>
                  <TextInput
                    mode="outlined"
                    label="Motivo de cancelación"
                    value={cancelReason}
                    onChangeText={setCancelReason}
                    multiline
                    numberOfLines={4}
                    placeholder="Escribe aquí el motivo..."
                    style={styles.cancelInput}
                    outlineColor={Colors.border}
                    activeOutlineColor={Colors.primary}
                    disabled={canceling}
                  />
                </View>

                {/* Actions - Siempre visibles */}
                <View style={styles.modalActions}>
                  <TouchableOpacity
                    style={styles.modalButtonSecondary}
                    onPress={handleCloseCancelDialog}
                    disabled={canceling}
                  >
                    <Text style={styles.modalButtonSecondaryText}>Volver</Text>
                  </TouchableOpacity>

                  <TouchableOpacity
                    style={[
                      styles.modalButtonPrimary,
                      (!cancelReason.trim() || canceling) && styles.modalButtonDisabled,
                    ]}
                    onPress={handleConfirmCancel}
                    disabled={canceling || !cancelReason.trim()}
                  >
                    {canceling ? (
                      <ActivityIndicator color="#fff" size="small" />
                    ) : (
                      <Text
                        style={[
                          styles.modalButtonPrimaryText,
                          (!cancelReason.trim() || canceling) && styles.modalButtonDisabledText,
                        ]}
                      >
                        Cancelar
                      </Text>
                    )}
                  </TouchableOpacity>
                </View>
              </View>
            </TouchableOpacity>
          </KeyboardAvoidingView>
        </TouchableOpacity>
      </Modal>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: Colors.background,
  },
  loadingText: {
    marginTop: 16,
    color: '#757575',
  },
  tabsContainer: {
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 16,
    backgroundColor: Colors.surface,
  },
  customTabsContainer: {
    flexDirection: 'row',
    borderRadius: 12,
    overflow: 'hidden',
    backgroundColor: '#F0F0F0',
    borderWidth: 2,
    borderColor: '#E0E0E0',
  },
  customTab: {
    flex: 1,
    paddingVertical: 14,
    paddingHorizontal: 16,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#F0F0F0',
  },
  customTabLeft: {
    borderTopLeftRadius: 10,
    borderBottomLeftRadius: 10,
  },
  customTabRight: {
    borderTopRightRadius: 10,
    borderBottomRightRadius: 10,
  },
  customTabActive: {
    backgroundColor: Colors.primary,
  },
  customTabText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#757575',
  },
  customTabTextActive: {
    color: '#FFFFFF',
  },
  listContent: {
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 16,
  },
  emptyList: {
    flexGrow: 1,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 32,
    marginTop: 60,
  },
  emptyTitle: {
    color: '#424242',
    marginBottom: 8,
    fontWeight: 'bold',
    marginTop: 16,
  },
  emptyText: {
    color: '#757575',
    textAlign: 'center',
  },
  operationCard: {
    marginBottom: 12,
    elevation: 2,
    backgroundColor: Colors.surface,
  },
  operationHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  operationInfo: {
    flex: 1,
  },
  operationLabel: {
    color: Colors.textLight,
    marginBottom: 4,
    fontSize: 12,
  },
  operationAmount: {
    fontWeight: 'bold',
    marginBottom: 4,
    color: Colors.textDark,
  },
  operationType: {
    color: Colors.textLight,
    marginBottom: 2,
  },
  operationDate: {
    color: Colors.textLight,
    fontSize: 11,
  },
  statusContainer: {
    alignItems: 'flex-end',
    flexDirection: 'row',
  },
  statusChipContainer: {
    alignItems: 'flex-end',
  },
  statusChip: {
    paddingHorizontal: 8,
  },
  actionHint: {
    marginLeft: -8,
  },
  divider: {
    marginVertical: 12,
    backgroundColor: Colors.divider,
  },
  actionInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#E3F2FD',
    padding: 8,
    borderRadius: 8,
    marginTop: 4,
  },
  actionInfoText: {
    flex: 1,
    fontSize: 12,
    color: '#1976D2',
    marginLeft: 4,
  },
  countdownContainerChip: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 4,
  },
  countdownText: {
    fontSize: 11,
    color: '#F44336',
    fontWeight: '600',
    marginLeft: 4,
  },
  detailButton: {
    backgroundColor: Colors.primary,
    paddingVertical: 14,
    paddingHorizontal: 16,
    margin: 16,
    marginTop: 0,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  detailButtonContent: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  detailButtonText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  cancelButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FFEBEE',
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 8,
    marginTop: 4,
    gap: 8,
  },
  cancelButtonText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#F44336',
  },
  // Modal styles
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  modalKeyboardAvoid: {
    width: '100%',
    alignItems: 'center',
  },
  modalContainer: {
    backgroundColor: '#fff',
    borderRadius: 20,
    width: '85%',
    maxWidth: 400,
    maxHeight: '80%',
    shadowColor: '#000',
    shadowOffset: {
      width: 0,
      height: 2,
    },
    shadowOpacity: 0.25,
    shadowRadius: 3.84,
    elevation: 5,
    paddingVertical: 24,
  },
  modalHeader: {
    alignItems: 'center',
    paddingHorizontal: 24,
    marginBottom: 20,
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: Colors.textDark,
    marginTop: 12,
    marginBottom: 8,
    textAlign: 'center',
  },
  modalSubtitle: {
    fontSize: 14,
    color: Colors.textLight,
    textAlign: 'center',
    lineHeight: 20,
  },
  modalBody: {
    paddingHorizontal: 24,
    marginBottom: 20,
    minHeight: 120,
  },
  cancelInput: {
    backgroundColor: '#fff',
    maxHeight: 150,
  },
  modalActions: {
    flexDirection: 'row',
    paddingHorizontal: 24,
    paddingTop: 8,
    gap: 12,
  },
  modalButtonSecondary: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 12,
    backgroundColor: '#F5F5F5',
    borderWidth: 1,
    borderColor: '#E0E0E0',
    alignItems: 'center',
    justifyContent: 'center',
  },
  modalButtonSecondaryText: {
    fontSize: 15,
    fontWeight: '600',
    color: '#424242',
  },
  modalButtonPrimary: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 12,
    backgroundColor: '#F44336',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#F44336',
    shadowOffset: {
      width: 0,
      height: 2,
    },
    shadowOpacity: 0.3,
    shadowRadius: 3,
    elevation: 4,
  },
  modalButtonPrimaryText: {
    fontSize: 15,
    fontWeight: '700',
    color: '#FFFFFF',
    letterSpacing: 0.3,
  },
  modalButtonDisabled: {
    backgroundColor: '#E0E0E0',
    opacity: 1,
    shadowOpacity: 0,
    elevation: 0,
  },
  modalButtonDisabledText: {
    color: '#9E9E9E',
  },
});
