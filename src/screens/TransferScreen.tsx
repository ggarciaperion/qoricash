import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Alert,
  Linking,
  ActivityIndicator,
  SafeAreaView,
  Image,
  StatusBar,
  Modal,
  KeyboardAvoidingView,
  Platform,
  Animated,
  Easing,
} from 'react-native';
import {
  Text,
  Card,
  Divider,
  TextInput,
  Button,
  IconButton,
} from 'react-native-paper';
import AsyncStorage from '@react-native-async-storage/async-storage';
import axios from 'axios';
import { Operation } from '../types';
import { Colors } from '../constants/colors';
import { QORICASH_ACCOUNTS } from '../constants/config';
import { formatCurrency, formatDateTime } from '../utils/formatters';
import apiClient from '../api/client';
import { GlobalStyles } from '../styles/globalStyles';
import socketService from '../services/socketService';
import { logger } from '../utils/logger';

const LOCAL_OPERATIONS_CACHE_KEY = '@qoricash_local_operations_cache';

const BANK_LOGOS: Record<string, any> = {
  'BCP': require('../../assets/banks/bcp.png'),
  'INTERBANK': require('../../assets/banks/interbank.png'),
  'BANBIF': require('../../assets/banks/banbif.png'),
  'BBVA': require('../../assets/banks/bbva.png'),
  'Scotiabank': require('../../assets/banks/scotiabank.png'),
  'SCOTIABANK': require('../../assets/banks/scotiabank.png'),
  'PICHINCHA': require('../../assets/banks/pichincha.png'),
};
// Tiempo de expiración: 15 minutos
const OPERATION_TIMEOUT_MINUTES = 15;

interface TransferScreenProps {
  navigation: any;
  route: {
    params: {
      operation: Operation;
    };
  };
}

export const TransferScreen: React.FC<TransferScreenProps> = ({ navigation, route }) => {
  const { operation } = route.params;
  const [timeRemaining, setTimeRemaining] = useState('');
  const [isExpired, setIsExpired] = useState(false);
  const [transferCodeModalVisible, setTransferCodeModalVisible] = useState(false);
  const [transferCode, setTransferCode] = useState('');
  const [submitAnimPhase, setSubmitAnimPhase] = useState<'idle' | 'loading' | 'done'>('idle');
  const submitSpinAnim = useRef(new Animated.Value(0)).current;
  const submitCheckScale = useRef(new Animated.Value(0)).current;
  const submitCheckOpacity = useRef(new Animated.Value(0)).current;
  const [cancelModalVisible, setCancelModalVisible] = useState(false);
  const [cancelReason, setCancelReason] = useState('');
  const [canceling, setCanceling] = useState(false);
  const [cancelAnimPhase, setCancelAnimPhase] = useState<'idle' | 'loading' | 'done'>('idle');
  const cancelSpinAnim = useRef(new Animated.Value(0)).current;
  const cancelCheckScale = useRef(new Animated.Value(0)).current;
  const cancelCheckOpacity = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const timer = setInterval(() => {
      const createdDate = new Date(operation.created_at);
      const expirationDate = new Date(createdDate.getTime() + OPERATION_TIMEOUT_MINUTES * 60000);
      const now = new Date();
      const diffMs = expirationDate.getTime() - now.getTime();

      if (diffMs <= 0) {
        setTimeRemaining('0:00');

        // Marcar como expirada solo una vez
        if (!isExpired) {
          setIsExpired(true);
          clearInterval(timer);

          // Mostrar alerta y redirigir
          Alert.alert(
            '⏱️ Tiempo Expirado',
            `La operación ${operation.operation_id} ha sido cancelada porque se agotó el tiempo para subir el comprobante.\n\nPuedes crear una nueva operación desde el inicio.`,
            [
              {
                text: 'Entendido',
                onPress: async () => {
                  // Cancelar operación en backend inmediatamente
                  logger.info('TransferScreen', '⏱️ Timer expirado - Cancelando operación en backend');
                  try {
                    const response = await axios.post(
                      `${API_CONFIG.BASE_URL}/api/client/cancel-expired-operation/${operation.id}`,
                      {},
                      { timeout: 5000 }
                    );

                    if (response.data.success) {
                      logger.info('TransferScreen', '✅ Operación cancelada exitosamente en backend');
                    } else {
                      logger.warn('TransferScreen', `⚠️ Respuesta del backend: ${response.data.message}`);
                    }
                  } catch (error) {
                    logger.error('TransferScreen', '❌ Error cancelando operación en backend', error);
                  }

                  logger.info('TransferScreen', '🗑️ Limpiando caché local antes de redirigir');
                  try {
                    await AsyncStorage.removeItem(LOCAL_OPERATIONS_CACHE_KEY);
                    logger.info('TransferScreen', '✅ Caché limpiado exitosamente');
                  } catch (error) {
                    logger.error('TransferScreen', '❌ Error limpiando caché', error);
                  }
                  logger.info('TransferScreen', '🔄 Redirigiendo a HistoryTab por expiración local');
                  navigation.replace('Tabs', { screen: 'HistoryTab', params: { initialTab: 'completed' } });
                }
              }
            ],
            { cancelable: false }
          );
        }
        return;
      }

      const minutes = Math.floor(diffMs / 60000);
      const seconds = Math.floor((diffMs % 60000) / 1000);

      setTimeRemaining(`${minutes}:${seconds.toString().padStart(2, '0')}`);
    }, 1000);

    return () => clearInterval(timer);
  }, [operation.created_at, isExpired, navigation]);

  // Escuchar evento de operación expirada vía Socket.IO
  useEffect(() => {
    logger.info('TransferScreen', '🎬 Iniciando useEffect de operation_expired', {
      operation_id: operation.operation_id,
      operation_status: operation.status,
    });

    const handleOperationExpired = (data: any) => {
      logger.info('TransferScreen', '📡 Evento operation_expired recibido', data);

      if (data.operation_id === operation.operation_id) {
        logger.warn('TransferScreen', '⏱️ La operación actual ha expirado, mostrando alerta', {
          operation_id: operation.operation_id,
        });

        Alert.alert(
          '⏱️ Tiempo Expirado',
          `La operación ${data.operation_id} ha sido cancelada porque se agotó el tiempo para subir el comprobante.\n\nPuedes crear una nueva operación desde el inicio.`,
          [
            {
              text: 'Entendido',
              onPress: async () => {
                logger.info('TransferScreen', '🗑️ Limpiando caché local antes de redirigir');
                try {
                  await AsyncStorage.removeItem(LOCAL_OPERATIONS_CACHE_KEY);
                  logger.info('TransferScreen', '✅ Caché limpiado exitosamente');
                } catch (error) {
                  logger.error('TransferScreen', '❌ Error limpiando caché', error);
                }
                logger.info('TransferScreen', '🔄 Redirigiendo a HistoryTab');
                navigation.replace('Tabs', { screen: 'HistoryTab', params: { initialTab: 'completed' } });
              }
            }
          ],
          { cancelable: false }
        );
      } else {
        logger.debug('TransferScreen', '⏭️ Operación expirada no es la actual, ignorando', {
          received_operation_id: data.operation_id,
          current_operation_id: operation.operation_id,
        });
      }
    };

    // Verificar conexión Socket.IO
    const isConnected = socketService.isConnected();
    logger.info('TransferScreen', `📡 Estado Socket.IO: ${isConnected ? 'Conectado' : 'Desconectado'}`);

    if (!isConnected) {
      logger.warn('TransferScreen', '⚠️ Socket.IO no está conectado, los eventos pueden no llegar');
    }

    // Registrar listener
    logger.info('TransferScreen', '📝 Registrando listener para operation_expired');
    socketService.on('operation_expired', handleOperationExpired);

    // Cleanup al desmontar componente
    return () => {
      logger.info('TransferScreen', '🧹 Removiendo listener para operation_expired');
      socketService.off('operation_expired', handleOperationExpired);
    };
  }, [operation.operation_id, navigation]);

  const getQoriCashAccount = () => {
    // Determinar moneda según tipo de operación
    const currency = operation.operation_type === 'Compra' ? 'USD' : 'PEN';

    // Extraer banco de la cuenta del cliente
    const sourceBank = operation.source_bank_name?.toUpperCase() || '';

    // Mapeo de bancos
    const bankMapping: { [key: string]: keyof typeof QORICASH_ACCOUNTS.USD } = {
      'BCP': 'BCP',
      'BANCO DE CREDITO': 'BCP',
      'BANCO DE CREDITO DEL PERU': 'BCP',
      'INTERBANK': 'INTERBANK',
      'PICHINCHA': 'PICHINCHA',
      'BANCO PICHINCHA': 'PICHINCHA',
      'BANBIF': 'BANBIF',
      'BANCO BANBIF': 'BANBIF',
    };

    // Buscar si el banco del cliente está en nuestra lista de bancos preferidos
    let qoriBank: keyof typeof QORICASH_ACCOUNTS.USD | null = null;

    for (const [key, value] of Object.entries(bankMapping)) {
      if (sourceBank.includes(key)) {
        qoriBank = value;
        break;
      }
    }

    // Si el banco está en la lista, usar cuenta del mismo banco
    // Si no, usar CCI de Interbank
    const accounts = QORICASH_ACCOUNTS[currency as keyof typeof QORICASH_ACCOUNTS];

    if (qoriBank && accounts[qoriBank]) {
      return {
        ...accounts[qoriBank],
        use_cci: false,
      };
    } else {
      return {
        ...accounts.INTERBANK,
        use_cci: true,
      };
    }
  };

  const qoriAccount = getQoriCashAccount();

  const handleYaTransferi = () => {
    if (isExpired) {
      Alert.alert(
        'Operación Expirada',
        'Esta operación ya no está disponible porque el tiempo ha expirado. Crea una nueva operación desde el inicio.',
        [{ text: 'Entendido', onPress: () => navigation.replace('Tabs', { screen: 'HistoryTab', params: { initialTab: 'completed' } }) }]
      );
      return;
    }
    setTransferCodeModalVisible(true);
  };

  const handleSubmitTransferCode = async () => {
    if (!transferCode.trim()) return;

    // Fase 1: spinner
    setSubmitAnimPhase('loading');
    submitSpinAnim.setValue(0);
    submitCheckScale.setValue(0);
    submitCheckOpacity.setValue(0);
    Animated.loop(
      Animated.timing(submitSpinAnim, {
        toValue: 1,
        duration: 800,
        easing: Easing.linear,
        useNativeDriver: true,
      })
    ).start();

    try {
      await Promise.all([
        apiClient.post(`/api/client/submit-transfer-code/${operation.id}`, {
          codigo_operacion: transferCode.trim(),
        }),
        new Promise(resolve => setTimeout(resolve, 1600)),
      ]);

      // Fase 2: check verde
      submitSpinAnim.stopAnimation();
      setSubmitAnimPhase('done');
      Animated.parallel([
        Animated.spring(submitCheckScale, { toValue: 1, useNativeDriver: true }),
        Animated.timing(submitCheckOpacity, { toValue: 1, duration: 200, useNativeDriver: true }),
      ]).start();

      setTimeout(() => {
        setTransferCodeModalVisible(false);
        setTransferCode('');
        setSubmitAnimPhase('idle');
        navigation.replace('Receive', { operation: { ...operation, status: 'en_proceso' } });
      }, 900);

    } catch (error: any) {
      submitSpinAnim.stopAnimation();
      setSubmitAnimPhase('idle');
      Alert.alert('Error', error?.response?.data?.message || error?.message || 'No se pudo registrar el código');
    }
  };

  const handleCancelOperation = async () => {
    if (!cancelReason.trim()) return;

    // Fase 1: spinner girando
    setCancelAnimPhase('loading');
    setCanceling(true);
    cancelSpinAnim.setValue(0);
    cancelCheckScale.setValue(0);
    cancelCheckOpacity.setValue(0);
    Animated.loop(
      Animated.timing(cancelSpinAnim, {
        toValue: 1,
        duration: 800,
        easing: Easing.linear,
        useNativeDriver: true,
      })
    ).start();

    try {
      const [response] = await Promise.all([
        apiClient.post(`/api/client/cancel-operation/${operation.id}`, {
          cancellation_reason: cancelReason.trim(),
        }),
        new Promise(resolve => setTimeout(resolve, 1500)),
      ]);

      await AsyncStorage.removeItem(LOCAL_OPERATIONS_CACHE_KEY);

      // Fase 2: check verde
      cancelSpinAnim.stopAnimation();
      setCancelAnimPhase('done');
      Animated.parallel([
        Animated.spring(cancelCheckScale, { toValue: 1, useNativeDriver: true }),
        Animated.timing(cancelCheckOpacity, { toValue: 1, duration: 200, useNativeDriver: true }),
      ]).start();

      setTimeout(() => {
        setCancelModalVisible(false);
        setCancelReason('');
        setCancelAnimPhase('idle');
        setCanceling(false);
        navigation.replace('Tabs', { screen: 'HistoryTab', params: { initialTab: 'completed' } });
      }, 800);

    } catch (error: any) {
      cancelSpinAnim.stopAnimation();
      setCancelAnimPhase('idle');
      setCanceling(false);
      Alert.alert('Error', error?.response?.data?.message || error?.message || 'No se pudo cancelar la operación');
    }
  };

  const handleOpenWhatsApp = () => {
    const phoneNumber = '51910624404';
    const message = `Hola, quiero enviar mi comprobante para la operación ${operation.operation_id}`;
    const url = `https://wa.me/${phoneNumber}?text=${encodeURIComponent(message)}`;

    Linking.openURL(url).catch(() => {
      Alert.alert('Error', 'No se pudo abrir WhatsApp');
    });
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar barStyle="light-content" backgroundColor="#22c55e" />

      {/* Header — idéntico al paso 1 */}
      <View style={styles.transferHeader}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.transferBackBtn} activeOpacity={0.7}>
          <Text style={styles.transferBackArrow}>‹</Text>
        </TouchableOpacity>
        <View style={styles.transferHeaderCenter}>
          <Image
            source={require('../../assets/logo-principal.png')}
            style={styles.transferHeaderLogo}
            resizeMode="contain"
            tintColor="#fff"
          />
          <Text style={styles.transferHeaderBrand}>Qoricash</Text>
        </View>
        <View style={styles.transferBackBtn} />
      </View>

      <ScrollView style={styles.container}>
      {/* Timeline Stepper */}
      <View style={styles.timelineContainer}>
        <View style={styles.timelineStep}>
          <View style={[styles.timelineCircle, styles.timelineCircleCompleted]}>
            <IconButton icon="check" size={16} iconColor="#FFFFFF" />
          </View>
          <Text style={styles.timelineText}>Cuentas</Text>
        </View>

        <View style={[styles.timelineLine, styles.timelineLineCompleted]} />

        <View style={styles.timelineStep}>
          <View style={[styles.timelineCircle, styles.timelineCircleActive]}>
            <IconButton icon="bank-transfer" size={16} iconColor="#FFFFFF" />
          </View>
          <Text style={[styles.timelineText, styles.timelineTextActive]}>Transfiere</Text>
        </View>

        <View style={styles.timelineLine} />

        <View style={styles.timelineStep}>
          <View style={styles.timelineCircle}>
            <IconButton icon="check-circle-outline" size={16} iconColor="#999999" />
          </View>
          <Text style={styles.timelineText}>Recibe</Text>
        </View>
      </View>

      {/* Operation Summary Card */}
      <Card style={styles.summaryCard}>
        <Card.Content>
          <View style={styles.summaryHeader}>
            <View>
              <Text variant="labelSmall" style={styles.summaryLabel}>
                ID de Operación
              </Text>
              <Text variant="titleMedium" style={styles.summaryValue}>
                {operation.operation_id}
              </Text>
            </View>
            <View style={styles.timerContainer}>
              <IconButton icon="clock-outline" size={20} iconColor="#F44336" />
              <Text style={styles.timerText}>{timeRemaining}</Text>
            </View>
          </View>

          <Divider style={styles.summaryDivider} />

          <View style={styles.summaryRow}>
            <View style={styles.summaryItem}>
              <Text style={styles.summaryLabel}>Tipo de operación</Text>
              <Text style={styles.summaryValue}>{operation.operation_type}</Text>
            </View>
            <View style={styles.summaryItem}>
              <Text style={styles.summaryLabel}>Fecha y hora</Text>
              <Text style={styles.summaryValue}>{formatDateTime(operation.created_at)}</Text>
            </View>
          </View>

          <View style={styles.summaryRow}>
            <View style={styles.summaryBox}>
              <Text style={styles.summaryLabel}>Envías</Text>
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
              <Text style={styles.summaryLabel}>Recibes</Text>
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

      {/* Transfer Details Card */}
      <Card style={styles.transferCard}>
        <Card.Content>
          <Text variant="titleMedium" style={styles.transferTitle}>
            Transfiere a:
          </Text>

          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Titular:</Text>
            <Text style={styles.detailValue}>Qoricash SAC</Text>
          </View>

          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Banco:</Text>
            {BANK_LOGOS[qoriAccount.bank_name] ? (
              <View style={styles.bankLogoDetailWrapper}>
                <Image
                  source={BANK_LOGOS[qoriAccount.bank_name]}
                  style={styles.bankLogoDetail}
                  resizeMode="contain"
                />
              </View>
            ) : (
              <Text style={styles.detailValue}>{qoriAccount.bank_name}</Text>
            )}
          </View>

          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Tipo de cuenta:</Text>
            <Text style={styles.detailValue}>{qoriAccount.account_type}</Text>
          </View>

          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>
              {qoriAccount.use_cci ? 'CCI:' : 'Número de cuenta:'}
            </Text>
            <View style={styles.accountNumberContainer}>
              <Text style={styles.accountNumber}>
                {qoriAccount.use_cci ? qoriAccount.cci : qoriAccount.account_number}
              </Text>
              <IconButton
                icon="content-copy"
                size={20}
                onPress={() => {
                  // Aquí iría lógica para copiar al portapapeles
                  Alert.alert('Copiado', 'Número de cuenta copiado al portapapeles');
                }}
              />
            </View>
          </View>

          {qoriAccount.use_cci && (
            <View style={styles.infoBox}>
              <IconButton icon="information-outline" size={20} iconColor="#2196F3" />
              <Text style={styles.infoText}>
                Para transferencias desde otros bancos, usa el CCI de Interbank
              </Text>
            </View>
          )}

          <View style={styles.importantNote}>
            <IconButton icon="information" size={20} iconColor="#2196F3" />
            <Text style={styles.importantNoteText}>
              Guarda el número de tu operación, lo usaremos en el siguiente paso
            </Text>
          </View>
        </Card.Content>
      </Card>

      {/* Upload Button */}
      <TouchableOpacity
        style={[styles.uploadButton, isExpired && styles.uploadButtonDisabled]}
        onPress={handleYaTransferi}
        activeOpacity={0.8}
        disabled={isExpired}
      >
        <Text style={styles.uploadButtonText}>
          {isExpired ? 'OPERACIÓN EXPIRADA' : 'YA TRANSFERÍ'}
        </Text>
      </TouchableOpacity>

      {/* Transfer Code Modal */}
      <Modal
        visible={transferCodeModalVisible}
        transparent
        animationType="slide"
        onRequestClose={() => { if (submitAnimPhase === 'idle') { setTransferCodeModalVisible(false); setTransferCode(''); } }}
      >
        <KeyboardAvoidingView
          style={styles.cancelModalOverlay}
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        >
          <View style={styles.cancelModalBox}>
            {/* Header verde */}
            <View style={[styles.cancelModalHeader, { backgroundColor: '#22c55e' }]}>
              <View style={styles.cancelModalIconCircle}>
                <IconButton icon="bank-transfer" size={26} iconColor="#fff" style={{ margin: 0 }} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.cancelModalTitle}>Código de transferencia</Text>
                <Text style={{ color: 'rgba(255,255,255,0.85)', fontSize: 12, marginTop: 2 }}>
                  Paso final para procesar tu operación
                </Text>
              </View>
            </View>

            {submitAnimPhase === 'idle' ? (
              <>
                <View style={styles.cancelModalBody}>
                  {/* Op ID */}
                  <View style={styles.cancelModalOpIdRow}>
                    <Text style={styles.cancelModalOpIdLabel}>Operación</Text>
                    <Text style={styles.cancelModalOpIdValue}>{operation.operation_id}</Text>
                  </View>

                  {/* Instrucción */}
                  <View style={styles.transferCodeInfo}>
                    <IconButton icon="information-outline" size={20} iconColor="#1d4ed8" style={{ margin: 0 }} />
                    <Text style={styles.transferCodeInfoText}>
                      Ingresa el número de operación que aparece en tu voucher o comprobante bancario. Este código es necesario para validar tu transferencia.
                    </Text>
                  </View>

                  <Text style={styles.cancelModalInputLabel}>
                    Número de operación <Text style={{ color: '#F44336' }}>*</Text>
                  </Text>
                  <TextInput
                    mode="outlined"
                    style={styles.cancelReasonInput}
                    value={transferCode}
                    onChangeText={setTransferCode}
                    placeholder="Ej: 00123456789"
                    keyboardType="default"
                    autoCapitalize="characters"
                    outlineColor={transferCode.trim() ? '#22c55e' : '#d1d5db'}
                    activeOutlineColor="#22c55e"
                  />
                  {!transferCode.trim() && (
                    <Text style={styles.cancelReasonRequired}>Campo obligatorio para continuar</Text>
                  )}
                </View>

                <View style={styles.cancelModalActions}>
                  <TouchableOpacity
                    style={styles.cancelModalBtnVolver}
                    onPress={() => { setTransferCodeModalVisible(false); setTransferCode(''); }}
                    activeOpacity={0.8}
                  >
                    <Text style={styles.cancelModalBtnVolverText}>Cancelar</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[styles.cancelModalBtnConfirm, { backgroundColor: '#22c55e' }, !transferCode.trim() && { backgroundColor: '#86efac' }]}
                    onPress={handleSubmitTransferCode}
                    disabled={!transferCode.trim()}
                    activeOpacity={0.8}
                  >
                    <Text style={styles.cancelModalBtnConfirmText}>ENVIAR</Text>
                  </TouchableOpacity>
                </View>
              </>
            ) : (
              <View style={styles.cancelAnimContainer}>
                {submitAnimPhase === 'loading' ? (
                  <>
                    <Animated.View style={{
                      transform: [{ rotate: submitSpinAnim.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '360deg'] }) }],
                      width: 64, height: 64, borderRadius: 32,
                      borderWidth: 5, borderColor: '#22c55e',
                      borderTopColor: 'transparent',
                    }} />
                    <Text style={styles.cancelAnimText}>Enviando código...</Text>
                    <Text style={{ fontSize: 12, color: '#9ca3af', textAlign: 'center' }}>
                      Notificando al operador
                    </Text>
                  </>
                ) : (
                  <>
                    <Animated.View style={{
                      transform: [{ scale: submitCheckScale }],
                      opacity: submitCheckOpacity,
                      width: 72, height: 72, borderRadius: 36,
                      backgroundColor: '#22c55e',
                      alignItems: 'center', justifyContent: 'center',
                    }}>
                      <IconButton icon="check" size={40} iconColor="#fff" style={{ margin: 0 }} />
                    </Animated.View>
                    <Text style={[styles.cancelAnimText, { color: '#22c55e' }]}>¡Código enviado!</Text>
                    <Text style={{ fontSize: 13, color: '#6b7280', textAlign: 'center' }}>
                      Un operador está procesando tu transferencia
                    </Text>
                  </>
                )}
              </View>
            )}
          </View>
        </KeyboardAvoidingView>
      </Modal>

      {/* Cancel Button */}
      <TouchableOpacity
        style={styles.cancelOperationButton}
        onPress={() => setCancelModalVisible(true)}
        activeOpacity={0.8}
      >
        <Text style={styles.cancelOperationButtonText}>CANCELAR OPERACIÓN</Text>
      </TouchableOpacity>

      {/* Cancel Modal */}
      <Modal
        visible={cancelModalVisible}
        transparent
        animationType="fade"
        onRequestClose={() => { if (!canceling) { setCancelModalVisible(false); setCancelReason(''); } }}
      >
        <KeyboardAvoidingView
          style={styles.cancelModalOverlay}
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        >
          <View style={styles.cancelModalBox}>
            {/* Header rojo */}
            <View style={styles.cancelModalHeader}>
              <View style={styles.cancelModalIconCircle}>
                <IconButton icon="alert" size={28} iconColor="#fff" style={{ margin: 0 }} />
              </View>
              <Text style={styles.cancelModalTitle}>Cancelar operación</Text>
            </View>

            {/* Body */}
            {cancelAnimPhase === 'idle' ? (
              <>
                <View style={styles.cancelModalBody}>
                  <View style={styles.cancelModalOpIdRow}>
                    <Text style={styles.cancelModalOpIdLabel}>Operación</Text>
                    <Text style={styles.cancelModalOpIdValue}>{operation.operation_id}</Text>
                  </View>

                  <Text style={styles.cancelModalWarning}>
                    Esta acción no se puede deshacer. Una vez cancelada, deberás crear una nueva operación si deseas continuar.
                  </Text>

                  <Text style={styles.cancelModalInputLabel}>
                    Motivo de cancelación <Text style={{ color: '#F44336' }}>*</Text>
                  </Text>
                  <TextInput
                    mode="outlined"
                    style={styles.cancelReasonInput}
                    value={cancelReason}
                    onChangeText={setCancelReason}
                    placeholder="Ej: Cambié de opinión, error en el monto..."
                    multiline
                    numberOfLines={4}
                    outlineColor={cancelReason.trim() ? '#d1d5db' : '#F44336'}
                    activeOutlineColor="#1d4ed8"
                  />
                  {!cancelReason.trim() && (
                    <Text style={styles.cancelReasonRequired}>Campo obligatorio para continuar</Text>
                  )}
                </View>

                <View style={styles.cancelModalActions}>
                  <TouchableOpacity
                    style={styles.cancelModalBtnVolver}
                    onPress={() => { setCancelModalVisible(false); setCancelReason(''); }}
                    activeOpacity={0.8}
                  >
                    <Text style={styles.cancelModalBtnVolverText}>Volver</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[styles.cancelModalBtnConfirm, !cancelReason.trim() && styles.cancelModalBtnDisabled]}
                    onPress={handleCancelOperation}
                    disabled={!cancelReason.trim()}
                    activeOpacity={0.8}
                  >
                    <Text style={styles.cancelModalBtnConfirmText}>Confirmar cancelación</Text>
                  </TouchableOpacity>
                </View>
              </>
            ) : (
              <View style={styles.cancelAnimContainer}>
                {cancelAnimPhase === 'loading' ? (
                  <>
                    <Animated.View style={{
                      transform: [{
                        rotate: cancelSpinAnim.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '360deg'] })
                      }],
                      width: 64, height: 64, borderRadius: 32,
                      borderWidth: 5, borderColor: '#F44336',
                      borderTopColor: 'transparent',
                    }} />
                    <Text style={styles.cancelAnimText}>Cancelando operación...</Text>
                  </>
                ) : (
                  <>
                    <Animated.View style={{
                      transform: [{ scale: cancelCheckScale }],
                      opacity: cancelCheckOpacity,
                      width: 64, height: 64, borderRadius: 32,
                      backgroundColor: '#22c55e',
                      alignItems: 'center', justifyContent: 'center',
                    }}>
                      <IconButton icon="check" size={36} iconColor="#fff" style={{ margin: 0 }} />
                    </Animated.View>
                    <Text style={[styles.cancelAnimText, { color: '#22c55e' }]}>Operación cancelada</Text>
                  </>
                )}
              </View>
            )}
          </View>
        </KeyboardAvoidingView>
      </Modal>

    </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    overflow: 'hidden',
  },

  // Timeline Styles
  timelineContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 10,
    paddingHorizontal: 16,
    backgroundColor: Colors.surface,
    marginBottom: 8,
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

  // Summary Card Styles
  summaryCard: {
    marginHorizontal: 16,
    marginBottom: 8,
    backgroundColor: '#22c55e',
  },
  summaryHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  timerContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFEBEE',
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 16,
  },
  timerText: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#F44336',
  },
  summaryDivider: {
    marginVertical: 6,
  },
  summaryRow: {
    flexDirection: 'row',
    gap: 6,
    marginTop: 4,
  },
  summaryItem: {
    flex: 1,
  },
  summaryBox: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.15)',
    padding: 8,
    borderRadius: 8,
  },
  summaryLabel: {
    fontSize: 11,
    color: 'rgba(255,255,255,0.75)',
    marginBottom: 4,
  },
  summaryValue: {
    fontSize: 13,
    fontWeight: '600',
    color: '#ffffff',
  },
  summaryAmount: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#ffffff',
  },
  importantNote: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#E3F2FD',
    padding: 8,
    borderRadius: 8,
    marginTop: 6,
  },
  importantNoteText: {
    flex: 1,
    fontSize: 13,
    color: '#1976D2',
    fontWeight: '500',
    marginLeft: 4,
  },

  // Transfer Card Styles
  transferCard: {
    marginHorizontal: 16,
    marginBottom: 8,
    backgroundColor: Colors.surface,
  },
  transferTitle: {
    fontWeight: 'bold',
    marginBottom: 16,
    color: Colors.textDark,
  },
  detailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 5,
  },
  detailLabel: {
    fontSize: 13,
    color: '#666666',
    flex: 1,
  },
  detailValue: {
    fontSize: 14,
    fontWeight: '600',
    color: Colors.textDark,
    flex: 2,
    textAlign: 'right',
  },
  bankLogoDetailWrapper: {
    flex: 2,
    alignItems: 'flex-end',
  },
  bankLogoDetail: {
    width: 80,
    height: 28,
  },
  accountNumberContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 2,
    justifyContent: 'flex-end',
  },
  accountNumber: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#2196F3',
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

  // Upload Button Styles
  uploadButton: {
    backgroundColor: '#22c55e',
    marginHorizontal: 16,
    marginBottom: 12,
    paddingVertical: 14,
    borderRadius: 12,
    alignItems: 'center',
    elevation: 4,
    shadowColor: '#22c55e',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
  },
  uploadButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: 'bold',
    letterSpacing: 1,
  },
  uploadButtonDisabled: {
    backgroundColor: '#BDBDBD',
    elevation: 0,
    shadowOpacity: 0,
  },
  cancelOperationButton: {
    marginHorizontal: 16,
    marginBottom: 16,
    paddingVertical: 13,
    borderRadius: 12,
    alignItems: 'center',
    borderWidth: 1.5,
    borderColor: '#F44336',
    backgroundColor: 'transparent',
  },
  cancelOperationButtonText: {
    color: '#F44336',
    fontSize: 14,
    fontWeight: '700',
    letterSpacing: 0.5,
  },

  // Cancel Modal
  cancelModalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.55)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  cancelModalBox: {
    width: '100%',
    maxWidth: 400,
    backgroundColor: '#fff',
    borderRadius: 20,
    overflow: 'hidden',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.25,
    shadowRadius: 24,
    elevation: 12,
  },
  cancelModalHeader: {
    backgroundColor: '#F44336',
    paddingVertical: 20,
    paddingHorizontal: 24,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  cancelModalIconCircle: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: 'rgba(255,255,255,0.2)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  cancelModalTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#fff',
  },
  cancelModalBody: {
    paddingHorizontal: 24,
    paddingTop: 20,
    paddingBottom: 8,
  },
  cancelModalOpIdRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#f8f9fa',
    borderRadius: 10,
    paddingVertical: 10,
    paddingHorizontal: 14,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#e9ecef',
  },
  cancelModalOpIdLabel: {
    fontSize: 13,
    color: '#6b7280',
    fontWeight: '500',
  },
  cancelModalOpIdValue: {
    fontSize: 14,
    fontWeight: '700',
    color: '#0D1B2A',
  },
  cancelModalWarning: {
    fontSize: 13,
    color: '#4b5563',
    lineHeight: 20,
    marginBottom: 20,
    backgroundColor: '#fff7ed',
    borderLeftWidth: 3,
    borderLeftColor: '#f97316',
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 6,
  },
  cancelModalInputLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: '#374151',
    marginBottom: 6,
  },
  transferCodeInfo: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: '#eff6ff',
    borderRadius: 8,
    paddingVertical: 10,
    paddingRight: 12,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#bfdbfe',
  },
  transferCodeInfoText: {
    flex: 1,
    fontSize: 13,
    color: '#1e40af',
    lineHeight: 18,
    paddingTop: 2,
  },
  cancelReasonInput: {
    backgroundColor: '#fff',
    fontSize: 14,
  },
  cancelReasonRequired: {
    fontSize: 12,
    color: '#F44336',
    marginTop: 4,
  },
  cancelModalActions: {
    flexDirection: 'row',
    gap: 12,
    paddingHorizontal: 24,
    paddingVertical: 20,
    borderTopWidth: 1,
    borderTopColor: '#f1f5f9',
  },
  cancelModalBtnVolver: {
    flex: 1,
    paddingVertical: 13,
    borderRadius: 12,
    alignItems: 'center',
    borderWidth: 1.5,
    borderColor: '#d1d5db',
    backgroundColor: '#fff',
  },
  cancelModalBtnVolverText: {
    fontSize: 15,
    fontWeight: '600',
    color: '#374151',
  },
  cancelModalBtnConfirm: {
    flex: 1,
    paddingVertical: 13,
    borderRadius: 12,
    alignItems: 'center',
    backgroundColor: '#F44336',
  },
  cancelModalBtnDisabled: {
    backgroundColor: '#fca5a5',
  },
  cancelModalBtnConfirmText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#fff',
  },
  cancelAnimContainer: {
    paddingVertical: 40,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 20,
  },
  cancelAnimText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#374151',
    textAlign: 'center',
  },

  // Dialog Styles
  dialog: {
    backgroundColor: Colors.surface,
  },
  dialogText: {
    marginBottom: 16,
    color: Colors.textDark,
  },
  imagePreviewContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#F0F8F0',
    padding: 8,
    borderRadius: 8,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: '#22c55e',
  },
  imagePreviewInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  imagePreviewText: {
    fontSize: 14,
    color: Colors.textDark,
    fontWeight: '600',
    marginLeft: 4,
  },
  addImageButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: '#22c55e',
    borderStyle: 'dashed',
    borderRadius: 12,
    padding: 12,
    marginBottom: 12,
  },
  addImageButtonText: {
    color: '#22c55e',
    fontWeight: '600',
    fontSize: 14,
    marginLeft: 4,
  },
  maxImagesNotice: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFF3E0',
    padding: 12,
    borderRadius: 8,
    marginBottom: 12,
  },
  maxImagesNoticeText: {
    flex: 1,
    fontSize: 12,
    color: '#F57C00',
    marginLeft: 4,
  },
  input: {
    marginBottom: 12,
  },
  alternativeContact: {
    backgroundColor: '#F5F5F5',
    padding: 16,
    borderRadius: 8,
    marginTop: 16,
  },
  alternativeContactTitle: {
    fontSize: 13,
    fontWeight: '600',
    color: Colors.textDark,
    marginBottom: 8,
  },
  contactRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 4,
  },
  contactIcon: {
    margin: 0,
    marginRight: -8,
  },
  alternativeContactText: {
    fontSize: 13,
    color: Colors.textDark,
  },
  whatsappLink: {
    fontSize: 13,
    color: '#25D366',
    fontWeight: '600',
    textDecorationLine: 'underline',
  },

  // ── Header ──
  safeArea: {
    flex: 1,
    backgroundColor: '#22c55e',
  },
  transferHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#22c55e',
    paddingVertical: 12,
    paddingHorizontal: 16,
  },
  transferBackBtn: {
    width: 40,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
  },
  transferBackArrow: {
    fontSize: 38,
    color: '#fff',
    lineHeight: 42,
    fontWeight: '300',
  },
  transferHeaderCenter: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  transferHeaderLogo: {
    width: 32,
    height: 32,
    marginRight: 8,
  },
  transferHeaderBrand: {
    fontSize: 26,
    fontFamily: 'Sansation-Bold',
    color: '#fff',
    letterSpacing: -0.5,
  },
});
