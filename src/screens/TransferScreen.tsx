import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Alert,
  Linking,
  Image,
  Modal,
  KeyboardAvoidingView,
  Platform,
  Animated,
  Easing,
  ImageBackground,
  TextInput,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { MotiView } from 'moti';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import axios from 'axios';
import { Operation } from '../types';
import { QORICASH_ACCOUNTS, API_CONFIG } from '../constants/config';
import { formatCurrency, formatDateTime } from '../utils/formatters';
import apiClient from '../api/client';
import socketService from '../services/socketService';
import { logger } from '../utils/logger';

const LOCAL_OPERATIONS_CACHE_KEY = '@qoricash_local_operations_cache';

const BANK_LOGOS: Record<string, any> = {
  'BCP':        require('../../assets/banks/bcp.png'),
  'INTERBANK':  require('../../assets/banks/interbank.png'),
  'BANBIF':     require('../../assets/banks/banbif.png'),
  'BBVA':       require('../../assets/banks/bbva.png'),
  'Scotiabank': require('../../assets/banks/scotiabank.png'),
  'SCOTIABANK': require('../../assets/banks/scotiabank.png'),
  'PICHINCHA':  require('../../assets/banks/pichincha.png'),
};

const OPERATION_TIMEOUT_MINUTES = 15;

const GREEN  = '#22c55e';
const GLASS  = 'rgba(255,255,255,0.08)';
const BORDER = 'rgba(255,255,255,0.14)';
const DIM    = 'rgba(255,255,255,0.5)';
const SHEET  = '#0b1929';

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
  const insets = useSafeAreaInsets();

  const [timeRemaining, setTimeRemaining]   = useState('');
  const [isExpired, setIsExpired]           = useState(false);

  const [transferCodeModalVisible, setTransferCodeModalVisible] = useState(false);
  const [transferCode, setTransferCode]     = useState('');
  const [submitAnimPhase, setSubmitAnimPhase] = useState<'idle' | 'loading' | 'done'>('idle');
  const submitSpinAnim    = useRef(new Animated.Value(0)).current;
  const submitCheckScale  = useRef(new Animated.Value(0)).current;
  const submitCheckOpacity = useRef(new Animated.Value(0)).current;

  const [cancelModalVisible, setCancelModalVisible] = useState(false);
  const [cancelReason, setCancelReason]     = useState('');
  const [canceling, setCanceling]           = useState(false);
  const [cancelAnimPhase, setCancelAnimPhase] = useState<'idle' | 'loading' | 'done'>('idle');
  const cancelSpinAnim    = useRef(new Animated.Value(0)).current;
  const cancelCheckScale  = useRef(new Animated.Value(0)).current;
  const cancelCheckOpacity = useRef(new Animated.Value(0)).current;

  // ── Timer countdown ──────────────────────────────────────────────────────────
  useEffect(() => {
    const timer = setInterval(() => {
      const createdDate    = new Date(operation.created_at);
      const expirationDate = new Date(createdDate.getTime() + OPERATION_TIMEOUT_MINUTES * 60000);
      const now            = new Date();
      const diffMs         = expirationDate.getTime() - now.getTime();

      if (diffMs <= 0) {
        setTimeRemaining('0:00');
        if (!isExpired) {
          setIsExpired(true);
          clearInterval(timer);
          Alert.alert(
            '⏱️ Tiempo Expirado',
            `La operación ${operation.operation_id} ha sido cancelada porque se agotó el tiempo para subir el comprobante.\n\nPuedes crear una nueva operación desde el inicio.`,
            [{
              text: 'Entendido',
              onPress: async () => {
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
                try {
                  await AsyncStorage.removeItem(LOCAL_OPERATIONS_CACHE_KEY);
                } catch (error) {
                  logger.error('TransferScreen', '❌ Error limpiando caché', error);
                }
                navigation.replace('Tabs', { screen: 'HistoryTab', params: { initialTab: 'completed' } });
              },
            }],
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

  // ── Socket.IO — operation_expired ─────────────────────────────────────────
  useEffect(() => {
    const handleOperationExpired = (data: any) => {
      if (data.operation_id === operation.operation_id) {
        Alert.alert(
          '⏱️ Tiempo Expirado',
          `La operación ${data.operation_id} ha sido cancelada porque se agotó el tiempo para subir el comprobante.\n\nPuedes crear una nueva operación desde el inicio.`,
          [{
            text: 'Entendido',
            onPress: async () => {
              try { await AsyncStorage.removeItem(LOCAL_OPERATIONS_CACHE_KEY); } catch {}
              navigation.replace('Tabs', { screen: 'HistoryTab', params: { initialTab: 'completed' } });
            },
          }],
          { cancelable: false }
        );
      }
    };

    socketService.on('operation_expired', handleOperationExpired);
    return () => socketService.off('operation_expired', handleOperationExpired);
  }, [operation.operation_id, navigation]);

  // ── Account helper ────────────────────────────────────────────────────────
  const getQoriCashAccount = () => {
    const currency   = operation.operation_type === 'Compra' ? 'USD' : 'PEN';
    const sourceBank = operation.source_bank_name?.toUpperCase() || '';

    const bankMapping: { [key: string]: keyof typeof QORICASH_ACCOUNTS.USD } = {
      'BCP':                          'BCP',
      'BANCO DE CREDITO':             'BCP',
      'BANCO DE CREDITO DEL PERU':    'BCP',
      'INTERBANK':                    'INTERBANK',
      'PICHINCHA':                    'PICHINCHA',
      'BANCO PICHINCHA':              'PICHINCHA',
      'BANBIF':                       'BANBIF',
      'BANCO BANBIF':                 'BANBIF',
    };

    let qoriBank: keyof typeof QORICASH_ACCOUNTS.USD | null = null;
    for (const [key, value] of Object.entries(bankMapping)) {
      if (sourceBank.includes(key)) { qoriBank = value; break; }
    }

    const accounts = QORICASH_ACCOUNTS[currency as keyof typeof QORICASH_ACCOUNTS];
    if (qoriBank && accounts[qoriBank]) {
      return { ...accounts[qoriBank], use_cci: false };
    }
    return { ...accounts.INTERBANK, use_cci: true };
  };

  const qoriAccount = getQoriCashAccount();

  // ── Handlers ──────────────────────────────────────────────────────────────
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

    setSubmitAnimPhase('loading');
    submitSpinAnim.setValue(0);
    submitCheckScale.setValue(0);
    submitCheckOpacity.setValue(0);

    Animated.loop(
      Animated.timing(submitSpinAnim, { toValue: 1, duration: 800, easing: Easing.linear, useNativeDriver: true })
    ).start();

    try {
      await Promise.all([
        apiClient.post(`/api/client/submit-transfer-code/${operation.id}`, { codigo_operacion: transferCode.trim() }),
        new Promise(resolve => setTimeout(resolve, 1600)),
      ]);

      submitSpinAnim.stopAnimation();
      setSubmitAnimPhase('done');
      Animated.parallel([
        Animated.spring(submitCheckScale,   { toValue: 1, useNativeDriver: true }),
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

    setCancelAnimPhase('loading');
    setCanceling(true);
    cancelSpinAnim.setValue(0);
    cancelCheckScale.setValue(0);
    cancelCheckOpacity.setValue(0);

    Animated.loop(
      Animated.timing(cancelSpinAnim, { toValue: 1, duration: 800, easing: Easing.linear, useNativeDriver: true })
    ).start();

    try {
      await Promise.all([
        apiClient.post(`/api/client/cancel-operation/${operation.id}`, { cancellation_reason: cancelReason.trim() }),
        new Promise(resolve => setTimeout(resolve, 1500)),
      ]);

      await AsyncStorage.removeItem(LOCAL_OPERATIONS_CACHE_KEY);

      cancelSpinAnim.stopAnimation();
      setCancelAnimPhase('done');
      Animated.parallel([
        Animated.spring(cancelCheckScale,   { toValue: 1, useNativeDriver: true }),
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
    const message     = `Hola, quiero enviar mi comprobante para la operación ${operation.operation_id}`;
    const url         = `https://wa.me/${phoneNumber}?text=${encodeURIComponent(message)}`;
    Linking.openURL(url).catch(() => Alert.alert('Error', 'No se pudo abrir WhatsApp'));
  };

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <View style={s.root}>
      <ImageBackground
        source={require('../../assets/cd.png')}
        style={StyleSheet.absoluteFill}
        resizeMode="cover"
      />
      <View style={[StyleSheet.absoluteFill, s.overlay]} />

      {/* ── Header ── */}
      <View style={[s.header, { paddingTop: insets.top + 10 }]}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={s.backBtn} activeOpacity={0.7}>
          <View style={s.backBtnInner}>
            <Ionicons name="chevron-back" size={20} color="#fff" />
          </View>
        </TouchableOpacity>
        <View style={s.headerCenter}>
          <Image
            source={require('../../assets/vv.png')}
            style={s.headerLogo}
            resizeMode="contain"
          />
        </View>
        <View style={{ width: 40 }} />
      </View>

      <ScrollView
        style={s.scroll}
        contentContainerStyle={{ paddingBottom: insets.bottom + 90 }}
        showsVerticalScrollIndicator={false}
      >

        {/* ── Timeline Stepper ── */}
        <MotiView
          from={{ opacity: 0, translateY: -10 }}
          animate={{ opacity: 1, translateY: 0 }}
          transition={{ type: 'timing', duration: 400, delay: 0 }}
        >
          <View style={s.timeline}>
            {/* Paso 1 — completado */}
            <View style={s.step}>
              <View style={[s.stepDot, s.stepDotDone]}>
                <Ionicons name="checkmark" size={13} color="#fff" />
              </View>
              <Text style={[s.stepLabel, s.stepLabelDone]}>Cuentas</Text>
            </View>

            <View style={[s.stepLine, s.stepLineDone]} />

            {/* Paso 2 — activo */}
            <View style={s.step}>
              <View style={[s.stepDot, s.stepDotActive]}>
                <Ionicons name="swap-horizontal" size={13} color="#fff" />
              </View>
              <Text style={[s.stepLabel, s.stepLabelActive]}>Transfiere</Text>
            </View>

            <View style={s.stepLine} />

            {/* Paso 3 — pendiente */}
            <View style={s.step}>
              <View style={s.stepDot}>
                <Ionicons name="checkmark-circle-outline" size={13} color={DIM} />
              </View>
              <Text style={s.stepLabel}>Recibe</Text>
            </View>
          </View>
        </MotiView>

        {/* ── Resumen de operación ── */}
        <MotiView
          from={{ opacity: 0, translateY: 22 }}
          animate={{ opacity: 1, translateY: 0 }}
          transition={{ type: 'timing', duration: 400, delay: 80 }}
          style={s.card}
        >
          {/* ID + timer */}
          <View style={s.cardTopRow}>
            <View>
              <Text style={s.cardMeta}>ID de Operación</Text>
              <Text style={s.cardOpId}>{operation.operation_id}</Text>
            </View>
            <View style={[s.timerPill, isExpired && s.timerPillExpired]}>
              <Ionicons name="time-outline" size={13} color={isExpired ? '#ef4444' : '#fbbf24'} />
              <Text style={[s.timerText, isExpired && s.timerTextExpired]}>
                {isExpired ? 'Expirado' : timeRemaining}
              </Text>
            </View>
          </View>

          <View style={s.hairline} />

          {/* Meta */}
          <View style={s.metaRow}>
            <View style={s.metaItem}>
              <Text style={s.metaLabel}>Tipo</Text>
              <Text style={s.metaValue}>{operation.operation_type}</Text>
            </View>
            <View style={s.metaItem}>
              <Text style={s.metaLabel}>Fecha</Text>
              <Text style={s.metaValue}>{formatDateTime(operation.created_at)}</Text>
            </View>
          </View>

          <View style={s.hairline} />

          {/* Montos */}
          <View style={s.amountsRow}>
            <View style={s.amountBlock}>
              <Text style={s.amountLabel}>Envías</Text>
              <Text style={s.amountValue}>
                {operation.operation_type === 'Compra'
                  ? formatCurrency(operation.amount_usd, 'USD')
                  : formatCurrency(operation.amount_pen, 'PEN')}
              </Text>
            </View>

            <View style={s.tcPill}>
              <Ionicons name="swap-horizontal" size={11} color={DIM} />
              <Text style={s.tcPillText}>{operation.exchange_rate.toFixed(3)}</Text>
            </View>

            <View style={s.amountBlock}>
              <Text style={s.amountLabel}>Recibes</Text>
              <Text style={[s.amountValue, { color: GREEN }]}>
                {operation.operation_type === 'Compra'
                  ? formatCurrency(operation.amount_pen, 'PEN')
                  : formatCurrency(operation.amount_usd, 'USD')}
              </Text>
            </View>
          </View>
        </MotiView>

        {/* ── Datos de transferencia ── */}
        <MotiView
          from={{ opacity: 0, translateY: 22 }}
          animate={{ opacity: 1, translateY: 0 }}
          transition={{ type: 'timing', duration: 400, delay: 160 }}
          style={s.card}
        >
          {/* Cabecera */}
          <View style={s.transferToHeader}>
            <View style={s.transferToIcon}>
              <Ionicons name="business-outline" size={18} color={GREEN} />
            </View>
            <View>
              <Text style={s.cardMeta}>Transferir a</Text>
              <Text style={s.transferToName}>Qoricash SAC</Text>
            </View>
          </View>

          <View style={s.hairline} />

          {/* Banco */}
          <View style={s.detailRow}>
            <Text style={s.detailLabel}>Banco</Text>
            {BANK_LOGOS[qoriAccount.bank_name] ? (
              <Image
                source={BANK_LOGOS[qoriAccount.bank_name]}
                style={s.bankLogo}
                resizeMode="contain"
              />
            ) : (
              <Text style={s.detailValue}>{qoriAccount.bank_name}</Text>
            )}
          </View>

          <View style={s.detailRow}>
            <Text style={s.detailLabel}>Tipo de cuenta</Text>
            <Text style={s.detailValue}>{qoriAccount.account_type}</Text>
          </View>

          <View style={s.detailRow}>
            <Text style={s.detailLabel}>{qoriAccount.use_cci ? 'CCI' : 'N° cuenta'}</Text>
            <View style={s.accountRow}>
              <Text style={s.accountNumber}>
                {qoriAccount.use_cci ? qoriAccount.cci : qoriAccount.account_number}
              </Text>
              <TouchableOpacity
                style={s.copyBtn}
                activeOpacity={0.7}
                onPress={() => Alert.alert('Copiado', 'Número de cuenta copiado al portapapeles')}
              >
                <Ionicons name="copy-outline" size={15} color={DIM} />
              </TouchableOpacity>
            </View>
          </View>

          {qoriAccount.use_cci && (
            <View style={s.infoBanner}>
              <Ionicons name="information-circle-outline" size={15} color="#60a5fa" />
              <Text style={s.infoBannerText}>
                Para transferencias desde otros bancos, usa el CCI de Interbank
              </Text>
            </View>
          )}

          <View style={s.noteBanner}>
            <Ionicons name="bookmark-outline" size={15} color="#fbbf24" />
            <Text style={s.noteBannerText}>
              Guarda el número de tu operación, lo necesitarás en el siguiente paso
            </Text>
          </View>
        </MotiView>

        {/* ── Botones de acción ── */}
        <MotiView
          from={{ opacity: 0, translateY: 22 }}
          animate={{ opacity: 1, translateY: 0 }}
          transition={{ type: 'timing', duration: 400, delay: 240 }}
          style={s.actionsWrap}
        >
          <TouchableOpacity
            style={[s.primaryBtn, isExpired && s.primaryBtnDisabled]}
            onPress={handleYaTransferi}
            activeOpacity={0.8}
            disabled={isExpired}
          >
            <Ionicons
              name={isExpired ? 'time-outline' : 'checkmark-circle-outline'}
              size={20}
              color="#fff"
            />
            <Text style={s.primaryBtnText}>
              {isExpired ? 'OPERACIÓN EXPIRADA' : 'YA TRANSFERÍ'}
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={s.dangerBtn}
            onPress={() => setCancelModalVisible(true)}
            activeOpacity={0.8}
          >
            <Text style={s.dangerBtnText}>CANCELAR OPERACIÓN</Text>
          </TouchableOpacity>
        </MotiView>

      </ScrollView>

      {/* ═══════════════════════════════════════════════════════════════════════
          MODAL — Código de transferencia
      ═══════════════════════════════════════════════════════════════════════ */}
      <Modal
        visible={transferCodeModalVisible}
        transparent
        animationType="slide"
        onRequestClose={() => {
          if (submitAnimPhase === 'idle') { setTransferCodeModalVisible(false); setTransferCode(''); }
        }}
      >
        <KeyboardAvoidingView
          style={s.modalOverlay}
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        >
          <View style={s.modalSheet}>
            {/* Accent strip */}
            <View style={s.modalAccentStrip} />
            <View style={s.modalHandle} />

            {/* Header */}
            <View style={s.modalHeader}>
              <View style={s.modalIconWrap}>
                <Ionicons name="receipt-outline" size={24} color={GREEN} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={s.modalTitle}>Código de transferencia</Text>
                <Text style={s.modalSub}>Ingresa el número de tu voucher bancario</Text>
              </View>
            </View>

            {submitAnimPhase === 'idle' ? (
              <>
                <View style={s.modalBody}>
                  {/* Operation ID chip */}
                  <View style={s.modalOpIdRow}>
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                      <Ionicons name="pricetag-outline" size={13} color={DIM} />
                      <Text style={s.modalOpIdLabel}>Operación</Text>
                    </View>
                    <View style={s.modalOpIdChip}>
                      <Text style={s.modalOpIdValue}>{operation.operation_id}</Text>
                    </View>
                  </View>

                  {/* Info banner — left-accent style */}
                  <View style={s.modalInfoBanner}>
                    <View style={s.modalInfoAccent} />
                    <Ionicons name="information-circle" size={16} color="#60a5fa" style={{ marginTop: 1 }} />
                    <Text style={s.modalInfoText}>
                      Ingresa el número de operación de tu voucher o comprobante bancario.
                    </Text>
                  </View>

                  {/* Input */}
                  <Text style={s.modalInputLabel}>
                    Número de operación{'  '}
                    <Text style={{ color: '#ef4444' }}>*</Text>
                  </Text>
                  <TextInput
                    style={[s.modalInput, transferCode.trim() ? s.modalInputActive : undefined]}
                    value={transferCode}
                    onChangeText={setTransferCode}
                    placeholder="Ej: 00123456789"
                    placeholderTextColor="rgba(255,255,255,0.3)"
                    keyboardType="default"
                    autoCapitalize="characters"
                  />
                  {!transferCode.trim() && (
                    <Text style={s.fieldRequired}>Campo obligatorio para continuar</Text>
                  )}
                </View>

                <View style={s.modalActions}>
                  <TouchableOpacity
                    style={[s.modalBtnGreen, !transferCode.trim() && s.modalBtnGreenDisabled]}
                    onPress={handleSubmitTransferCode}
                    disabled={!transferCode.trim()}
                    activeOpacity={0.85}
                  >
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                      <Ionicons name="checkmark-circle-outline" size={20} color="#fff" />
                      <Text style={s.modalBtnConfirmText}>ENVIAR CÓDIGO</Text>
                    </View>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={s.modalCancelLink}
                    onPress={() => { setTransferCodeModalVisible(false); setTransferCode(''); }}
                    activeOpacity={0.7}
                  >
                    <Text style={s.modalCancelLinkText}>Cancelar</Text>
                  </TouchableOpacity>
                </View>
              </>
            ) : (
              <View style={s.animContainer}>
                {submitAnimPhase === 'loading' ? (
                  <>
                    <Animated.View style={{
                      width: 64, height: 64, borderRadius: 32,
                      borderWidth: 4, borderColor: GREEN, borderTopColor: 'transparent',
                      transform: [{ rotate: submitSpinAnim.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '360deg'] }) }],
                    }} />
                    <Text style={s.animText}>Enviando código...</Text>
                    <Text style={s.animSub}>Notificando al operador</Text>
                  </>
                ) : (
                  <>
                    <Animated.View style={{
                      width: 72, height: 72, borderRadius: 36,
                      backgroundColor: GREEN, alignItems: 'center', justifyContent: 'center',
                      transform: [{ scale: submitCheckScale }],
                      opacity: submitCheckOpacity,
                    }}>
                      <Ionicons name="checkmark" size={38} color="#fff" />
                    </Animated.View>
                    <Text style={[s.animText, { color: GREEN }]}>¡Código enviado!</Text>
                    <Text style={s.animSub}>Un operador está procesando tu transferencia</Text>
                  </>
                )}
              </View>
            )}
          </View>
        </KeyboardAvoidingView>
      </Modal>

      {/* ═══════════════════════════════════════════════════════════════════════
          MODAL — Cancelar operación
      ═══════════════════════════════════════════════════════════════════════ */}
      <Modal
        visible={cancelModalVisible}
        transparent
        animationType="fade"
        onRequestClose={() => { if (!canceling) { setCancelModalVisible(false); setCancelReason(''); } }}
      >
        <KeyboardAvoidingView
          style={s.modalOverlay}
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        >
          <View style={s.modalSheet}>
            <View style={s.modalHandle} />

            <View style={s.modalHeader}>
              <View style={[s.modalIconWrap, s.modalIconWrapDanger]}>
                <Ionicons name="alert" size={22} color="#ef4444" />
              </View>
              <Text style={s.modalTitle}>Cancelar operación</Text>
            </View>

            {cancelAnimPhase === 'idle' ? (
              <>
                <View style={s.modalBody}>
                  <View style={s.modalOpIdRow}>
                    <Text style={s.modalOpIdLabel}>Operación</Text>
                    <Text style={s.modalOpIdValue}>{operation.operation_id}</Text>
                  </View>

                  <View style={s.warningBanner}>
                    <Text style={s.warningBannerText}>
                      Esta acción no se puede deshacer. Deberás crear una nueva operación si deseas continuar.
                    </Text>
                  </View>

                  <Text style={s.modalInputLabel}>
                    Motivo de cancelación{'  '}
                    <Text style={{ color: '#ef4444' }}>*</Text>
                  </Text>
                  <TextInput
                    style={[s.modalInput, s.modalInputMultiline, cancelReason.trim() ? s.modalInputActiveDanger : undefined]}
                    value={cancelReason}
                    onChangeText={setCancelReason}
                    placeholder="Ej: Cambié de opinión, error en el monto..."
                    placeholderTextColor="rgba(255,255,255,0.3)"
                    multiline
                    numberOfLines={3}
                  />
                  {!cancelReason.trim() && (
                    <Text style={s.fieldRequired}>Campo obligatorio para continuar</Text>
                  )}
                </View>

                <View style={s.modalActions}>
                  <TouchableOpacity
                    style={s.modalBtnGhost}
                    onPress={() => { setCancelModalVisible(false); setCancelReason(''); }}
                    activeOpacity={0.8}
                  >
                    <Text style={s.modalBtnGhostText}>Volver</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[s.modalBtnRed, !cancelReason.trim() && s.modalBtnRedDisabled]}
                    onPress={handleCancelOperation}
                    disabled={!cancelReason.trim()}
                    activeOpacity={0.8}
                  >
                    <Text style={s.modalBtnConfirmText}>Confirmar</Text>
                  </TouchableOpacity>
                </View>
              </>
            ) : (
              <View style={s.animContainer}>
                {cancelAnimPhase === 'loading' ? (
                  <>
                    <Animated.View style={{
                      width: 64, height: 64, borderRadius: 32,
                      borderWidth: 4, borderColor: '#ef4444', borderTopColor: 'transparent',
                      transform: [{ rotate: cancelSpinAnim.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '360deg'] }) }],
                    }} />
                    <Text style={s.animText}>Cancelando operación...</Text>
                  </>
                ) : (
                  <>
                    <Animated.View style={{
                      width: 72, height: 72, borderRadius: 36,
                      backgroundColor: GREEN, alignItems: 'center', justifyContent: 'center',
                      transform: [{ scale: cancelCheckScale }],
                      opacity: cancelCheckOpacity,
                    }}>
                      <Ionicons name="checkmark" size={38} color="#fff" />
                    </Animated.View>
                    <Text style={[s.animText, { color: GREEN }]}>Operación cancelada</Text>
                  </>
                )}
              </View>
            )}
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </View>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
const s = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: '#000',
  },
  overlay: {
    backgroundColor: 'transparent',
  },

  // ── Header ──────────────────────────────────────────────────────────────────
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingBottom: 14,
  },
  backBtn: {
    width: 40,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
  },
  backBtnInner: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: GLASS,
    borderWidth: 1,
    borderColor: BORDER,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerCenter: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerLogo: {
    width: 110,
    height: 22,
  },

  scroll: { flex: 1 },

  // ── Timeline ─────────────────────────────────────────────────────────────────
  timeline: {
    flexDirection: 'row',
    alignItems: 'center',
    marginHorizontal: 16,
    marginBottom: 16,
    backgroundColor: GLASS,
    borderWidth: 1,
    borderColor: BORDER,
    borderRadius: 20,
    paddingVertical: 14,
    paddingHorizontal: 20,
  },
  step: {
    alignItems: 'center',
    gap: 5,
  },
  stepDot: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderWidth: 1,
    borderColor: BORDER,
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepDotDone: {
    backgroundColor: GREEN,
    borderColor: GREEN,
  },
  stepDotActive: {
    backgroundColor: 'rgba(34,197,94,0.18)',
    borderColor: GREEN,
    borderWidth: 1.5,
  },
  stepLine: {
    flex: 1,
    height: 2,
    backgroundColor: 'rgba(255,255,255,0.1)',
    marginHorizontal: 8,
    marginBottom: 20,
  },
  stepLineDone: {
    backgroundColor: GREEN,
  },
  stepLabel: {
    fontSize: 10,
    color: DIM,
    fontWeight: '500',
  },
  stepLabelDone: {
    color: GREEN,
    fontWeight: '600',
  },
  stepLabelActive: {
    color: '#fff',
    fontWeight: '700',
  },

  // ── Cards ────────────────────────────────────────────────────────────────────
  card: {
    backgroundColor: GLASS,
    borderWidth: 1,
    borderColor: BORDER,
    borderRadius: 22,
    marginHorizontal: 16,
    marginBottom: 14,
    padding: 18,
  },
  hairline: {
    height: 1,
    backgroundColor: BORDER,
    marginVertical: 14,
  },

  // Resumen — cabecera
  cardTopRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  cardMeta: {
    fontSize: 10,
    color: DIM,
    fontWeight: '500',
    marginBottom: 3,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },
  cardOpId: {
    fontSize: 17,
    fontWeight: '700',
    color: '#fff',
    letterSpacing: 0.3,
  },
  timerPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    backgroundColor: 'rgba(251,191,36,0.1)',
    borderWidth: 1,
    borderColor: 'rgba(251,191,36,0.25)',
    borderRadius: 20,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  timerPillExpired: {
    backgroundColor: 'rgba(239,68,68,0.1)',
    borderColor: 'rgba(239,68,68,0.25)',
  },
  timerText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#fbbf24',
  },
  timerTextExpired: {
    color: '#ef4444',
  },

  // Resumen — meta
  metaRow: {
    flexDirection: 'row',
    gap: 16,
  },
  metaItem: { flex: 1 },
  metaLabel: {
    fontSize: 10,
    color: DIM,
    fontWeight: '500',
    marginBottom: 3,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  metaValue: {
    fontSize: 13,
    fontWeight: '600',
    color: '#fff',
  },

  // Resumen — montos
  amountsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  amountBlock: {
    flex: 1,
    backgroundColor: 'rgba(255,255,255,0.05)',
    borderRadius: 12,
    padding: 12,
    alignItems: 'center',
  },
  amountLabel: {
    fontSize: 10,
    color: DIM,
    fontWeight: '500',
    marginBottom: 5,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
  },
  amountValue: {
    fontSize: 14,
    fontWeight: '700',
    color: '#fff',
  },
  tcPill: {
    alignItems: 'center',
    gap: 3,
    paddingHorizontal: 6,
  },
  tcPillText: {
    fontSize: 10,
    color: DIM,
    fontWeight: '600',
  },

  // Detalles — cabecera
  transferToHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  transferToIcon: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: 'rgba(34,197,94,0.12)',
    borderWidth: 1,
    borderColor: 'rgba(34,197,94,0.25)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  transferToName: {
    fontSize: 16,
    fontWeight: '700',
    color: '#fff',
  },

  // Detalles — filas
  detailRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 9,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255,255,255,0.06)',
  },
  detailLabel: {
    fontSize: 13,
    color: DIM,
    flex: 1,
  },
  detailValue: {
    fontSize: 14,
    fontWeight: '600',
    color: '#fff',
    flex: 2,
    textAlign: 'right',
  },
  bankLogo: {
    width: 80,
    height: 28,
  },
  accountRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    flex: 2,
    justifyContent: 'flex-end',
  },
  accountNumber: {
    fontSize: 14,
    fontWeight: '700',
    color: GREEN,
    letterSpacing: 0.5,
  },
  copyBtn: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: GLASS,
    borderWidth: 1,
    borderColor: BORDER,
    alignItems: 'center',
    justifyContent: 'center',
  },

  infoBanner: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
    backgroundColor: 'rgba(96,165,250,0.08)',
    borderWidth: 1,
    borderColor: 'rgba(96,165,250,0.2)',
    borderRadius: 12,
    padding: 12,
    marginTop: 12,
  },
  infoBannerText: {
    flex: 1,
    fontSize: 12,
    color: '#93c5fd',
    lineHeight: 17,
  },
  noteBanner: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
    backgroundColor: 'rgba(251,191,36,0.08)',
    borderWidth: 1,
    borderColor: 'rgba(251,191,36,0.2)',
    borderRadius: 12,
    padding: 12,
    marginTop: 10,
  },
  noteBannerText: {
    flex: 1,
    fontSize: 12,
    color: '#fde68a',
    lineHeight: 17,
  },

  // ── Botones ──────────────────────────────────────────────────────────────────
  actionsWrap: {
    marginHorizontal: 16,
    gap: 10,
  },
  primaryBtn: {
    backgroundColor: GREEN,
    borderRadius: 16,
    paddingVertical: 16,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    shadowColor: GREEN,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.4,
    shadowRadius: 12,
    elevation: 6,
  },
  primaryBtnDisabled: {
    backgroundColor: 'rgba(255,255,255,0.15)',
    shadowOpacity: 0,
    elevation: 0,
  },
  primaryBtnText: {
    color: '#fff',
    fontSize: 15,
    fontWeight: '700',
    letterSpacing: 0.8,
  },
  dangerBtn: {
    borderRadius: 16,
    paddingVertical: 14,
    alignItems: 'center',
    borderWidth: 1.5,
    borderColor: 'rgba(239,68,68,0.45)',
    backgroundColor: 'rgba(239,68,68,0.07)',
  },
  dangerBtnText: {
    color: '#f87171',
    fontSize: 14,
    fontWeight: '700',
    letterSpacing: 0.5,
  },

  // ── Modales ──────────────────────────────────────────────────────────────────
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.85)',
    justifyContent: 'flex-end',
  },
  modalSheet: {
    backgroundColor: '#0c1f30',
    borderTopLeftRadius: 32,
    borderTopRightRadius: 32,
    overflow: 'hidden',
    paddingBottom: Platform.OS === 'ios' ? 38 : 24,
    borderTopWidth: 1,
    borderColor: 'rgba(34,197,94,0.2)',
    shadowColor: GREEN,
    shadowOffset: { width: 0, height: -4 },
    shadowOpacity: 0.12,
    shadowRadius: 20,
    elevation: 24,
  },
  modalAccentStrip: {
    height: 3,
    backgroundColor: GREEN,
    opacity: 0.7,
  },
  modalHandle: {
    width: 48,
    height: 4,
    borderRadius: 2,
    backgroundColor: 'rgba(255,255,255,0.15)',
    alignSelf: 'center',
    marginTop: 14,
    marginBottom: 6,
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
    paddingHorizontal: 24,
    paddingVertical: 18,
    borderBottomWidth: 1,
    borderBottomColor: BORDER,
  },
  modalIconWrap: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: 'rgba(34,197,94,0.14)',
    borderWidth: 1.5,
    borderColor: 'rgba(34,197,94,0.35)',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: GREEN,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.35,
    shadowRadius: 10,
    elevation: 6,
  },
  modalIconWrapDanger: {
    backgroundColor: 'rgba(239,68,68,0.12)',
    borderColor: 'rgba(239,68,68,0.25)',
  },
  modalTitle: {
    fontSize: 19,
    fontWeight: '700',
    color: '#fff',
    letterSpacing: 0.2,
  },
  modalSub: {
    fontSize: 12,
    color: DIM,
    marginTop: 3,
  },
  modalBody: {
    paddingHorizontal: 24,
    paddingTop: 22,
    paddingBottom: 8,
  },
  modalOpIdRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: 'rgba(255,255,255,0.05)',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: BORDER,
    paddingVertical: 12,
    paddingHorizontal: 16,
    marginBottom: 16,
  },
  modalOpIdChip: {
    backgroundColor: 'rgba(34,197,94,0.12)',
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderWidth: 1,
    borderColor: 'rgba(34,197,94,0.25)',
  },
  modalOpIdLabel: {
    fontSize: 12,
    color: DIM,
    fontWeight: '500',
  },
  modalOpIdValue: {
    fontSize: 13,
    fontWeight: '700',
    color: GREEN,
    letterSpacing: 0.5,
  },
  modalInfoBanner: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    backgroundColor: 'rgba(96,165,250,0.06)',
    borderWidth: 1,
    borderColor: 'rgba(96,165,250,0.15)',
    borderLeftWidth: 3,
    borderLeftColor: '#60a5fa',
    borderRadius: 10,
    padding: 12,
    marginBottom: 18,
  },
  modalInfoAccent: {
    display: 'none',
  },
  modalInfoText: {
    flex: 1,
    fontSize: 12,
    color: '#93c5fd',
    lineHeight: 18,
  },
  warningBanner: {
    backgroundColor: 'rgba(239,68,68,0.08)',
    borderWidth: 1,
    borderColor: 'rgba(239,68,68,0.2)',
    borderRadius: 10,
    padding: 12,
    marginBottom: 16,
  },
  warningBannerText: {
    fontSize: 13,
    color: '#fca5a5',
    lineHeight: 18,
  },
  modalInputLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: 'rgba(255,255,255,0.8)',
    marginBottom: 10,
  },
  modalInput: {
    backgroundColor: 'rgba(255,255,255,0.07)',
    borderWidth: 1.5,
    borderColor: BORDER,
    borderRadius: 14,
    color: '#fff',
    fontSize: 17,
    paddingHorizontal: 16,
    paddingVertical: 14,
    letterSpacing: 0.5,
  },
  modalInputMultiline: {
    minHeight: 90,
    textAlignVertical: 'top',
  },
  modalInputActive: {
    borderColor: GREEN,
    shadowColor: GREEN,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.4,
    shadowRadius: 8,
    elevation: 4,
  },
  modalInputActiveDanger: {
    borderColor: '#ef4444',
  },
  fieldRequired: {
    fontSize: 11,
    color: '#ef4444',
    marginTop: 5,
  },
  modalActions: {
    flexDirection: 'column',
    gap: 10,
    paddingHorizontal: 24,
    paddingTop: 20,
    borderTopWidth: 1,
    borderTopColor: BORDER,
  },
  modalBtnGhost: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 14,
    alignItems: 'center',
    borderWidth: 1.5,
    borderColor: BORDER,
    backgroundColor: GLASS,
  },
  modalBtnGhostText: {
    fontSize: 14,
    fontWeight: '600',
    color: 'rgba(255,255,255,0.65)',
  },
  modalCancelLink: {
    alignItems: 'center',
    paddingVertical: 10,
  },
  modalCancelLinkText: {
    fontSize: 14,
    fontWeight: '500',
    color: 'rgba(255,255,255,0.4)',
  },
  modalBtnGreen: {
    paddingVertical: 17,
    borderRadius: 16,
    alignItems: 'center',
    backgroundColor: GREEN,
    shadowColor: GREEN,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.45,
    shadowRadius: 14,
    elevation: 8,
  },
  modalBtnGreenDisabled: {
    backgroundColor: 'rgba(34,197,94,0.28)',
    shadowOpacity: 0,
    elevation: 0,
  },
  modalBtnRed: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 14,
    alignItems: 'center',
    backgroundColor: '#ef4444',
  },
  modalBtnRedDisabled: {
    backgroundColor: 'rgba(239,68,68,0.35)',
  },
  modalBtnConfirmText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#fff',
  },

  // Animaciones dentro de modal
  animContainer: {
    paddingVertical: 48,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 18,
  },
  animText: {
    fontSize: 17,
    fontWeight: '600',
    color: '#fff',
    textAlign: 'center',
  },
  animSub: {
    fontSize: 13,
    color: DIM,
    textAlign: 'center',
  },
});
