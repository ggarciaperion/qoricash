import React, { useEffect, useRef } from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  Animated,
  Easing,
  TouchableOpacity,
  Alert,
  SafeAreaView,
  Image,
  Linking,
} from 'react-native';
import {
  Text,
  Card,
  Divider,
  IconButton,
} from 'react-native-paper';
import { CommonActions } from '@react-navigation/native';
import { Operation, BankAccount } from '../types';
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
  const clockOpacity = useRef(new Animated.Value(1)).current;
  const checkScale = useRef(new Animated.Value(0)).current;
  const checkOpacity = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    navigation.setOptions({ headerLeft: () => null, gestureEnabled: false });

    // Ciclo: reloj gira 2.4s → check aparece 1.2s → vuelve a reloj → ...
    const clockLoop = Animated.loop(
      Animated.timing(rotateAnim, { toValue: 1, duration: 800, easing: Easing.linear, useNativeDriver: true })
    );

    const runCycle = () => {
      rotateAnim.setValue(0);
      clockOpacity.setValue(1);
      checkScale.setValue(0);
      checkOpacity.setValue(0);
      clockLoop.start();

      setTimeout(() => {
        // Fade out reloj
        clockLoop.stop();
        Animated.timing(clockOpacity, { toValue: 0, duration: 250, useNativeDriver: true }).start(() => {
          // Aparece check con spring
          Animated.parallel([
            Animated.spring(checkScale, { toValue: 1, useNativeDriver: true }),
            Animated.timing(checkOpacity, { toValue: 1, duration: 200, useNativeDriver: true }),
          ]).start(() => {
            // Pausa con check visible, luego vuelve al reloj
            setTimeout(() => {
              Animated.parallel([
                Animated.timing(checkOpacity, { toValue: 0, duration: 250, useNativeDriver: true }),
                Animated.timing(checkScale, { toValue: 0, duration: 250, useNativeDriver: true }),
              ]).start(() => runCycle());
            }, 1200);
          });
        });
      }, 2400);
    };

    runCycle();
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
        if (data.status === 'completado') {
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
    <SafeAreaView style={{ flex: 1, paddingTop: 20 }}>
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
          <View style={styles.timeInfoRow}>
            <View style={{ width: 36, height: 36, alignItems: 'center', justifyContent: 'center' }}>
              <Animated.View style={{ position: 'absolute', opacity: clockOpacity, transform: [{ rotate: spin }] }}>
                <IconButton icon="clock-outline" size={26} iconColor="#22c55e" style={{ margin: 0 }} />
              </Animated.View>
              <Animated.View style={{ position: 'absolute', opacity: checkOpacity, transform: [{ scale: checkScale }] }}>
                <IconButton icon="check-circle" size={26} iconColor="#22c55e" style={{ margin: 0 }} />
              </Animated.View>
            </View>
            <View style={styles.timeInfoTextContainer}>
              <Text variant="titleMedium" style={styles.statusTitle}>
                Procesando tu operación
              </Text>
              <Text style={styles.timeInfoTitle}>Tiempo promedio: 15 - 30 minutos</Text>
            </View>
          </View>
        </Card.Content>
      </Card>

      {/* Operation Summary Card */}
      <Card style={styles.summaryCard}>
        <Card.Content>
          <View style={styles.summaryHeader}>
            <Image
              source={require('../../assets/logo-principal.png')}
              style={styles.summaryHeaderLogo}
              resizeMode="contain"
              tintColor="#fff"
            />
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
            <Text style={styles.detailValue}>
              Qoricash {operation.operation_type === 'Compra' ? 'compra' : 'venta'}
            </Text>
          </View>

          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Fecha:</Text>
            <Text style={styles.detailValue}>{formatDateTime(operation.created_at)}</Text>
          </View>

          <Divider style={styles.summaryDivider} />

          <View style={styles.summaryRow}>
            <View style={styles.summaryBox}>
              <Text style={styles.summaryLabel}>
                {operation.operation_type === 'Compra' ? '🇺🇸 ' : '🇵🇪 '}Enviaste
              </Text>
              <Text style={styles.summaryAmount}>
                {operation.operation_type === 'Compra'
                  ? formatCurrency(operation.amount_usd, 'USD')
                  : formatCurrency(operation.amount_pen, 'PEN')
                }
              </Text>
            </View>
            <View style={styles.summaryBox}>
              <Text style={styles.summaryLabel}>Tipo de cambio</Text>
              <Text style={styles.summaryAmount}>{operation.exchange_rate.toFixed(3)}</Text>
            </View>
            <View style={styles.summaryBox}>
              <Text style={styles.summaryLabel}>
                {operation.operation_type === 'Compra' ? '🇵🇪 ' : '🇺🇸 '}Recibirás
              </Text>
              <Text style={styles.summaryAmount}>
                {operation.operation_type === 'Compra'
                  ? formatCurrency(operation.amount_pen, 'PEN')
                  : formatCurrency(operation.amount_usd, 'USD')
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
            <Text style={styles.destLabel}>Titular:</Text>
            <Text style={styles.destValue}>
              {(() => {
                const full = ((operation as any).client_name || '').trim();
                const parts = full.split(/\s+/);
                if (parts.length <= 2) return full || 'Por definir';
                return `${parts[0]} ${parts[Math.max(1, parts.length - 2)]}`;
              })()}
            </Text>
          </View>

          <View style={styles.detailRow}>
            <Text style={styles.destLabel}>Banco:</Text>
            {operation.destination_bank_name && BANK_LOGOS[operation.destination_bank_name] ? (
              <View style={styles.destBankLogoWrapper}>
                <Image
                  source={BANK_LOGOS[operation.destination_bank_name]}
                  style={styles.destBankLogo}
                  resizeMode="contain"
                />
              </View>
            ) : (
              <Text style={styles.destValue}>{operation.destination_bank_name || 'Por definir'}</Text>
            )}
          </View>

          <View style={styles.detailRow}>
            <Text style={styles.destLabel}>Tipo / Moneda:</Text>
            <Text style={styles.destValue}>
              {(() => {
                const accounts: BankAccount[] = (operation as any).client_bank_accounts || [];
                const acc = accounts.find((a: BankAccount) => a.account_number === operation.destination_account);
                const tipo = acc?.account_type || 'Por definir';
                const moneda = acc?.currency
                  ? (acc.currency === 'S/' ? 'Soles (S/)' : 'Dólares ($)')
                  : (operation.operation_type === 'Compra' ? 'Soles (S/)' : 'Dólares ($)');
                return `${tipo} - ${moneda}`;
              })()}
            </Text>
          </View>

          <View style={styles.detailRow}>
            <Text style={styles.destLabel}>Número de cuenta:</Text>
            <Text style={styles.destValue}>{operation.destination_account || 'Por definir'}</Text>
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

      <TouchableOpacity
        style={styles.supportLink}
        activeOpacity={0.7}
        onPress={() => {
          const msg = `Hola, necesito ayuda con mi operación ${operation.operation_id}`;
          Linking.openURL(`https://wa.me/51910624404?text=${encodeURIComponent(msg)}`);
        }}
      >
        <Text style={styles.supportLinkText}>Contactar con soporte</Text>
      </TouchableOpacity>
    </ScrollView>
    </SafeAreaView>
  );
};

const BANK_LOGOS: Record<string, any> = {
  'BCP': require('../../assets/banks/bcp.png'),
  'INTERBANK': require('../../assets/banks/interbank.png'),
  'BANBIF': require('../../assets/banks/banbif.png'),
  'BBVA': require('../../assets/banks/bbva.png'),
  'Scotiabank': require('../../assets/banks/scotiabank.png'),
  'SCOTIABANK': require('../../assets/banks/scotiabank.png'),
  'PICHINCHA': require('../../assets/banks/pichincha.png'),
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
    backgroundColor: '#22c55e',
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
    backgroundColor: '#22c55e',
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
    marginBottom: 8,
    backgroundColor: Colors.surface,
  },
  statusHeader: {
    alignItems: 'flex-start',
    paddingVertical: 0,
    paddingBottom: 0,
  },
  statusTitle: {
    fontWeight: 'bold',
    color: Colors.textDark,
    marginBottom: 2,
  },
  statusSubtitle: {
    fontSize: 14,
    color: '#666666',
    textAlign: 'center',
  },

  // Summary Card Styles
  summaryCard: {
    marginHorizontal: 16,
    marginBottom: 8,
    backgroundColor: '#22c55e',
  },
  summaryHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
    gap: 8,
  },
  summaryHeaderLogo: {
    width: 24,
    height: 24,
  },
  summaryHeaderText: {
    fontWeight: 'bold',
    color: '#ffffff',
  },
  summaryDivider: {
    marginVertical: 12,
    backgroundColor: 'rgba(255,255,255,0.3)',
  },
  detailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
  },
  detailLabel: {
    fontSize: 13,
    color: 'rgba(255,255,255,0.75)',
  },
  detailValue: {
    fontSize: 14,
    fontWeight: '600',
    color: '#ffffff',
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
    backgroundColor: 'rgba(0,0,0,0.15)',
    padding: 12,
    borderRadius: 8,
  },
  summaryLabel: {
    fontSize: 11,
    color: 'rgba(255,255,255,0.75)',
    marginBottom: 4,
  },
  summaryAmount: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#ffffff',
  },

  // Destination Card Styles
  destinationCard: {
    marginHorizontal: 16,
    marginBottom: 8,
    backgroundColor: Colors.surface,
  },
  destinationTitle: {
    fontWeight: 'bold',
    marginBottom: 8,
    color: Colors.textDark,
  },
  destLabel: {
    fontSize: 13,
    color: '#666666',
  },
  destValue: {
    fontSize: 14,
    fontWeight: '600',
    color: Colors.textDark,
    textAlign: 'right',
    flex: 1,
    marginLeft: 16,
  },
  destBankLogoWrapper: {
    flex: 1,
    flexDirection: 'row',
    justifyContent: 'flex-end',
    marginLeft: 16,
  },
  destBankLogo: {
    width: 80,
    height: 26,
    backgroundColor: 'transparent',
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
    color: '#22c55e',
  },

  // Accept Button Styles
  acceptButton: {
    backgroundColor: Colors.primary,
    marginHorizontal: 16,
    marginTop: 8,
    marginBottom: 12,
    paddingVertical: 14,
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
  supportLink: {
    alignItems: 'center',
    paddingBottom: 24,
    marginTop: 4,
  },
  supportLinkText: {
    fontSize: 14,
    color: '#25D366',
    fontWeight: '600',
    textDecorationLine: 'underline',
  },
});
