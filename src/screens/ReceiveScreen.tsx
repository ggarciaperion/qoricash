import React, { useEffect, useRef } from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  Animated,
  Easing,
  TouchableOpacity,
  Alert,
} from 'react-native';
import {
  Text,
  Card,
  Divider,
  IconButton,
} from 'react-native-paper';
import { CommonActions } from '@react-navigation/native';
import { Operation } from '../types';
import { Colors } from '../constants/colors';
import { formatCurrency, formatDateTime } from '../utils/formatters';
import socketService from '../services/socket';
import { GlobalStyles } from '../styles/globalStyles';

interface ReceiveScreenProps {
  navigation: any;
  route: {
    params: {
      operation: Operation;
    };
  };
}

export const ReceiveScreen: React.FC<ReceiveScreenProps> = ({ navigation, route }) => {
  const { operation } = route.params;
  const rotateAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    // Ocultar el botón de atrás
    navigation.setOptions({
      headerLeft: () => null,
      gestureEnabled: false,
    });

    // Animación de rotación continua
    Animated.loop(
      Animated.timing(rotateAnim, {
        toValue: 1,
        duration: 2000,
        easing: Easing.linear,
        useNativeDriver: true,
      })
    ).start();
  }, [navigation]);

  // Escuchar actualizaciones de Socket.IO
  useEffect(() => {
    console.log('🔌 ReceiveScreen: Conectando Socket.IO para operación:', operation.operation_id);
    socketService.connect();

    const redirectToHistory = () => {
      console.log('✅ Redirigiendo al historial...');
      navigation.dispatch(
        CommonActions.reset({
          index: 0,
          routes: [
            {
              name: 'Tabs',
              state: {
                routes: [
                  { name: 'HomeTab' },
                  { name: 'HistoryTab' },
                  { name: 'ProfileTab' },
                ],
                index: 1, // HistoryTab
              },
            },
          ],
        })
      );
    };

    const handleOperationUpdated = (data: any) => {
      console.log('📡 [ReceiveScreen] operacion_actualizada recibido:', data);

      // Verificar si es nuestra operación
      if (data.id === operation.id || data.operation_id === operation.operation_id) {
        console.log(`✅ Actualización para operación ${operation.operation_id}: ${data.status}`);

        // Verificar si está completada (en femenino)
        if (data.status === 'Completada') {
          console.log('🎉 ¡Operación completada! Mostrando alerta...');
          Alert.alert(
            '✅ Operación Completada',
            'Tu operación ha sido completada exitosamente. Tu pago ha sido procesado.',
            [
              {
                text: 'Ver Historial',
                onPress: redirectToHistory,
              },
            ],
            {
              cancelable: false,
              onDismiss: redirectToHistory,
            }
          );
        }
      }
    };

    const handleOperationCompleted = (data: any) => {
      console.log('📡 [ReceiveScreen] operacion_completada recibido:', data);

      // Verificar si es nuestra operación
      if (data.operation_id === operation.operation_id) {
        console.log('🎉 ¡Operación completada via evento específico! Mostrando alerta...');
        Alert.alert(
          '✅ Operación Completada',
          `Tu operación ${data.operation_id} ha sido completada exitosamente. Tu pago ha sido procesado.`,
          [
            {
              text: 'Ver Historial',
              onPress: redirectToHistory,
            },
          ],
          {
            cancelable: false,
            onDismiss: redirectToHistory,
          }
        );
      }
    };

    // Escuchar ambos eventos
    socketService.on('operacion_actualizada', handleOperationUpdated);
    socketService.on('operacion_completada', handleOperationCompleted);

    return () => {
      console.log('🔌 ReceiveScreen: Desconectando Socket.IO...');
      socketService.off('operacion_actualizada', handleOperationUpdated);
      socketService.off('operacion_completada', handleOperationCompleted);
    };
  }, [operation.id, operation.operation_id, navigation]);

  const spin = rotateAnim.interpolate({
    inputRange: [0, 1],
    outputRange: ['0deg', '360deg'],
  });

  const handleAccept = () => {
    // Navegar al Historial (tab HistoryTab)
    navigation.dispatch(
      CommonActions.reset({
        index: 0,
        routes: [
          {
            name: 'Tabs',
            state: {
              routes: [
                { name: 'HomeTab' },
                { name: 'HistoryTab' },
                { name: 'ProfileTab' },
              ],
              index: 1, // HistoryTab
            },
          },
        ],
      })
    );
  };

  return (
    <ScrollView style={styles.container}>
      {/* Timeline Stepper */}
      <View style={styles.timelineContainer}>
        <View style={styles.timelineStep}>
          <View style={[styles.timelineCircle, styles.timelineCircleCompleted]}>
            <IconButton icon="check" size={16} iconColor="#FFFFFF" />
          </View>
          <Text style={styles.timelineText}>Cotiza</Text>
        </View>

        <View style={[styles.timelineLine, styles.timelineLineCompleted]} />

        <View style={styles.timelineStep}>
          <View style={[styles.timelineCircle, styles.timelineCircleCompleted]}>
            <IconButton icon="check" size={16} iconColor="#FFFFFF" />
          </View>
          <Text style={styles.timelineText}>Transfiere</Text>
        </View>

        <View style={[styles.timelineLine, styles.timelineLineCompleted]} />

        <View style={styles.timelineStep}>
          <View style={[styles.timelineCircle, styles.timelineCircleActive]}>
            <IconButton icon="check-circle-outline" size={16} iconColor="#FFFFFF" />
          </View>
          <Text style={[styles.timelineText, styles.timelineTextActive]}>Recibe</Text>
        </View>
      </View>

      {/* Processing Status Card */}
      <Card style={styles.statusCard}>
        <Card.Content>
          <View style={styles.statusHeader}>
            <Animated.View style={{ transform: [{ rotate: spin }] }}>
              <IconButton icon="clock-outline" size={60} iconColor="#2196F3" />
            </Animated.View>
            <Text variant="headlineSmall" style={styles.statusTitle}>
              Procesando tu operación
            </Text>
            <Text style={styles.statusSubtitle}>
              Nuestro equipo está verificando tu comprobante
            </Text>
          </View>
        </Card.Content>
      </Card>

      {/* Operation Summary Card */}
      <Card style={styles.summaryCard}>
        <Card.Content>
          <View style={styles.summaryHeader}>
            <Text variant="titleMedium" style={styles.summaryHeaderText}>
              Detalles de la operación
            </Text>
          </View>

          <Divider style={styles.summaryDivider} />

          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>ID de Operación:</Text>
            <Text style={styles.detailValue}>{operation.operation_id}</Text>
          </View>

          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Tipo:</Text>
            <Text style={styles.detailValue}>{operation.operation_type}</Text>
          </View>

          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Fecha:</Text>
            <Text style={styles.detailValue}>{formatDateTime(operation.created_at)}</Text>
          </View>

          <Divider style={styles.summaryDivider} />

          <View style={styles.summaryRow}>
            <View style={styles.summaryBox}>
              <Text style={styles.summaryLabel}>Enviaste</Text>
              <Text style={styles.summaryAmount}>
                {operation.operation_type === 'Compra'
                  ? `$${operation.amount_usd.toFixed(2)}`
                  : `S/ ${operation.amount_pen.toFixed(2)}`
                }
              </Text>
            </View>
            <View style={styles.summaryBox}>
              <Text style={styles.summaryLabel}>Tipo de cambio</Text>
              <Text style={styles.summaryAmount}>{operation.exchange_rate.toFixed(3)}</Text>
            </View>
            <View style={styles.summaryBox}>
              <Text style={styles.summaryLabel}>Recibirás</Text>
              <Text style={styles.summaryAmount}>
                {operation.operation_type === 'Compra'
                  ? `S/ ${operation.amount_pen.toFixed(2)}`
                  : `$${operation.amount_usd.toFixed(2)}`
                }
              </Text>
            </View>
          </View>
        </Card.Content>
      </Card>

      {/* Destination Account Card */}
      <Card style={styles.destinationCard}>
        <Card.Content>
          <Text variant="titleMedium" style={styles.destinationTitle}>
            Cuenta de destino
          </Text>

          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Banco:</Text>
            <Text style={styles.detailValue}>{operation.destination_bank_name || 'Por definir'}</Text>
          </View>

          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Número de cuenta:</Text>
            <Text style={styles.detailValue}>{operation.destination_account || 'Por definir'}</Text>
          </View>

          <View style={styles.infoBox}>
            <IconButton icon="information-outline" size={20} iconColor="#2196F3" />
            <Text style={styles.infoText}>
              Te notificaremos cuando tu operación sea completada
            </Text>
          </View>
        </Card.Content>
      </Card>

      {/* Status Information */}
      <Card style={styles.timeInfoCard}>
        <Card.Content>
          <View style={styles.timeInfoRow}>
            <IconButton icon="clock-check-outline" size={24} iconColor="#82C16C" />
            <View style={styles.timeInfoTextContainer}>
              <Text style={styles.timeInfoTitle}>Tiempo promedio de procesamiento</Text>
              <Text style={styles.timeInfoValue}>15 - 30 minutos</Text>
            </View>
          </View>
        </Card.Content>
      </Card>

      {/* Accept Button */}
      <TouchableOpacity
        style={styles.acceptButton}
        onPress={handleAccept}
        activeOpacity={0.8}
      >
        <Text style={styles.acceptButtonText}>ACEPTAR</Text>
      </TouchableOpacity>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },

  // Timeline Styles
  timelineContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 20,
    paddingHorizontal: 16,
    backgroundColor: Colors.surface,
    marginBottom: 16,
  },
  timelineStep: {
    alignItems: 'center',
  },
  timelineCircle: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#E0E0E0',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 8,
  },
  timelineCircleCompleted: {
    backgroundColor: '#82C16C',
  },
  timelineCircleActive: {
    backgroundColor: '#2196F3',
  },
  timelineLine: {
    flex: 1,
    height: 2,
    backgroundColor: '#E0E0E0',
    marginHorizontal: 8,
  },
  timelineLineCompleted: {
    backgroundColor: '#82C16C',
  },
  timelineText: {
    fontSize: 12,
    color: '#999999',
    fontWeight: '500',
  },
  timelineTextActive: {
    color: '#2196F3',
    fontWeight: '600',
  },

  // Status Card Styles
  statusCard: {
    marginHorizontal: 16,
    marginBottom: 16,
    backgroundColor: Colors.surface,
  },
  statusHeader: {
    alignItems: 'center',
    paddingVertical: 20,
  },
  statusTitle: {
    fontWeight: 'bold',
    color: Colors.textDark,
    marginTop: 8,
    marginBottom: 8,
    textAlign: 'center',
  },
  statusSubtitle: {
    fontSize: 14,
    color: '#666666',
    textAlign: 'center',
  },

  // Summary Card Styles
  summaryCard: {
    marginHorizontal: 16,
    marginBottom: 16,
    backgroundColor: Colors.surface,
  },
  summaryHeader: {
    marginBottom: 8,
  },
  summaryHeaderText: {
    fontWeight: 'bold',
    color: Colors.textDark,
  },
  summaryDivider: {
    marginVertical: 12,
  },
  detailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
  },
  detailLabel: {
    fontSize: 13,
    color: '#666666',
  },
  detailValue: {
    fontSize: 14,
    fontWeight: '600',
    color: Colors.textDark,
    textAlign: 'right',
    flex: 1,
    marginLeft: 16,
  },
  summaryRow: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 8,
  },
  summaryBox: {
    flex: 1,
    backgroundColor: '#F5F5F5',
    padding: 12,
    borderRadius: 8,
  },
  summaryLabel: {
    fontSize: 11,
    color: '#666666',
    marginBottom: 4,
  },
  summaryAmount: {
    fontSize: 16,
    fontWeight: 'bold',
    color: Colors.textDark,
  },

  // Destination Card Styles
  destinationCard: {
    marginHorizontal: 16,
    marginBottom: 16,
    backgroundColor: Colors.surface,
  },
  destinationTitle: {
    fontWeight: 'bold',
    marginBottom: 16,
    color: Colors.textDark,
  },
  infoBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#E3F2FD',
    padding: 12,
    borderRadius: 8,
    marginTop: 12,
  },
  infoText: {
    flex: 1,
    fontSize: 12,
    color: '#1976D2',
    marginLeft: 8,
  },

  // Time Info Card Styles
  timeInfoCard: {
    marginHorizontal: 16,
    marginBottom: 24,
    backgroundColor: Colors.surface,
  },
  timeInfoRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  timeInfoTextContainer: {
    flex: 1,
    marginLeft: 8,
  },
  timeInfoTitle: {
    fontSize: 13,
    color: '#666666',
    marginBottom: 4,
  },
  timeInfoValue: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#82C16C',
  },

  // Accept Button Styles
  acceptButton: {
    backgroundColor: Colors.primary,
    marginHorizontal: 16,
    marginVertical: 24,
    paddingVertical: 16,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
    elevation: 2,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
  },
  acceptButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: 'bold',
    letterSpacing: 1,
  },
});
