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
import { BlurView } from 'expo-blur';
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
import { shownCancelAlerts } from '../utils/cancelAlertDedup';
import { useAuth } from '../contexts/AuthContext';
import { useBackground } from '../hooks/useBackground';

const LOCAL_OPERATIONS_CACHE_KEY = '@qoricash_local_operations_cache';

const BANK_LOGOS: Record<string, any> = {
  'BCP':        require('../../assets/banks/bcp.png'),
  'INTERBANK':  require('../../assets/banks/ibk.png'),
  'BANBIF':     require('../../assets/banks/banbif.png'),
  'BBVA':       require('../../assets/banks/bbva.png'),
  'Scotiabank': require('../../assets/banks/scotiabank.png'),
  'SCOTIABANK': require('../../assets/banks/scotiabank.png'),
  'PICHINCHA':  require('../../assets/banks/pichincha.png'),
};

const OPERATION_TIMEOUT_MINUTES = 15;

const GREEN  = '#22c55e';
const GLASS  = '#FFFFFF';
const BORDER = 'rgba(0,0,0,0.08)';
const DIM    = '#6B7280';
const SHEET  = '#FFFFFF';

interface TransferScreenProps {
  navigation: any;
  route: {
    params: {
      operation: Operation;
    };
  };
}

export const TransferScreen: React.FC<TransferScreenProps> = ({ navigation, route }) => {
  const bg = useBackground();
  const { operation } = route.params;
  const insets = useSafeAreaInsets();
  const { client } = useAuth();
  const isLegalEntity = client?.document_type === 'RUC';

  const [timeRemaining, setTimeRemaining]   = useState('');
  const [isExpired, setIsExpired]           = useState(false);
  const [showTimerInfo, setShowTimerInfo]   = useState(false);
  const timerInfoSpin = useRef(new Animated.Value(0)).current;
  const timerInfoLoopRef = useRef<Animated.CompositeAnimation | null>(null);

  useEffect(() => {
    if (showTimerInfo) {
      timerInfoSpin.setValue(0);
      timerInfoLoopRef.current = Animated.loop(
        Animated.timing(timerInfoSpin, { toValue: 1, duration: 1800, useNativeDriver: true, easing: Easing.linear })
      );
      timerInfoLoopRef.current.start();
    } else {
      timerInfoLoopRef.current?.stop();
      timerInfoSpin.setValue(0);
    }
  }, [showTimerInfo]);

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
  const cancelSpin2       = useRef(new Animated.Value(0)).current;
  const cancelDotScale    = useRef(new Animated.Value(1)).current;
  const cancelCheckScale  = useRef(new Animated.Value(0)).current;
  const cancelCheckOpacity = useRef(new Animated.Value(0)).current;

  // ── Step arc spin animation ───────────────────────────────────────────────────
  const stepSpin = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    Animated.loop(
      Animated.timing(stepSpin, { toValue: 1, duration: 1600, useNativeDriver: true, easing: Easing.linear })
    ).start();
  }, []);

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
        const key = `expired_${data.operation_id}`;
        shownCancelAlerts.add(key);
        setTimeout(() => shownCancelAlerts.delete(key), 5000);
        Alert.alert(
          '⏱️ Operación Cancelada',
          `Tu operación ${data.operation_id} fue cancelada automáticamente por vencer el tiempo límite sin confirmación.\n\nPuedes crear una nueva operación desde el inicio.`,
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

    const handleCanceledByAdmin = (data: any) => {
      if (data.operation_id === operation.operation_id) {
        const key = `cancel_${data.operation_id}`;
        shownCancelAlerts.add(key);
        setTimeout(() => shownCancelAlerts.delete(key), 5000);
        Alert.alert(
          '❌ Operación Cancelada',
          `Tu operación ${data.operation_id} fue cancelada por el equipo Qoricash.\n\n` +
          `Motivo: ${data.reason || 'Sin motivo especificado'}\n\n` +
          `Si tienes alguna duda, contáctanos por WhatsApp.`,
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
    socketService.on('operacion_cancelada_admin', handleCanceledByAdmin);
    return () => {
      socketService.off('operation_expired', handleOperationExpired);
      socketService.off('operacion_cancelada_admin', handleCanceledByAdmin);
    };
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
    cancelSpin2.setValue(0);
    cancelDotScale.setValue(1);
    cancelCheckScale.setValue(0);
    cancelCheckOpacity.setValue(0);

    Animated.loop(
      Animated.timing(cancelSpinAnim, { toValue: 1, duration: 1100, easing: Easing.linear, useNativeDriver: true })
    ).start();
    Animated.loop(
      Animated.timing(cancelSpin2, { toValue: 1, duration: 1700, easing: Easing.linear, useNativeDriver: true })
    ).start();
    Animated.loop(
      Animated.sequence([
        Animated.timing(cancelDotScale, { toValue: 1.5, duration: 500, easing: Easing.out(Easing.ease), useNativeDriver: true }),
        Animated.timing(cancelDotScale, { toValue: 1,   duration: 500, easing: Easing.in(Easing.ease),  useNativeDriver: true }),
      ])
    ).start();

    try {
      await Promise.all([
        apiClient.post(`/api/client/cancel-operation/${operation.id}`, { cancellation_reason: cancelReason.trim(), client_dni: client?.dni || '' }),
        new Promise(resolve => setTimeout(resolve, 2500)),
      ]);

      await AsyncStorage.removeItem(LOCAL_OPERATIONS_CACHE_KEY);

      cancelSpinAnim.stopAnimation();
      cancelSpin2.stopAnimation();
      cancelDotScale.stopAnimation();
      setCancelAnimPhase('done');
      Animated.parallel([
        Animated.spring(cancelCheckScale, { toValue: 1, tension: 160, friction: 11, useNativeDriver: true }),
        Animated.timing(cancelCheckOpacity, { toValue: 1, duration: 220, useNativeDriver: true }),
      ]).start();

      setTimeout(() => {
        setCancelModalVisible(false);
        setCancelReason('');
        setCancelAnimPhase('idle');
        setCanceling(false);
        navigation.replace('Tabs', { screen: 'HistoryTab', params: { initialTab: 'completed' } });
      }, 1400);

    } catch (error: any) {
      cancelSpinAnim.stopAnimation();
      cancelSpin2.stopAnimation();
      cancelDotScale.stopAnimation();
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
      <View style={[StyleSheet.absoluteFill, { backgroundColor: '#F5F7FA' }]} pointerEvents="none" />

      {/* ── Header ── */}
      <View style={[s.header, { paddingTop: insets.top + 10 }]}>
        <TouchableOpacity onPress={() => navigation.replace('Tabs', { screen: 'HistoryTab' })} style={s.backBtn} activeOpacity={0.7}>
          <View style={s.backBtnInner}>
            <Ionicons name="chevron-back" size={20} color="#0D1117" />
          </View>
        </TouchableOpacity>
        <View style={s.headerCenter}>
          <View style={{ alignItems: 'center' }}>
            <Image
              source={require('../../assets/qc.png')}
              style={s.headerLogo}
              resizeMode="contain"
            />
            {isLegalEntity && (
              <Text style={s.corporateLabel}>corporate</Text>
            )}
          </View>
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
            {/* Paso 1 — completado: Cotiza */}
            <View style={s.step}>
              <View style={[s.stepDot, s.stepDotDone]}>
                <Ionicons name="receipt-outline" size={13} color="#fff" />
              </View>
              <Text style={[s.stepLabel, s.stepLabelDone]}>Cotiza</Text>
            </View>

            <View style={[s.stepLine, s.stepLineDone]} />

            {/* Paso 2 — activo: Transfiere */}
            <View style={s.step}>
              <View style={s.stepDotActiveWrap}>
                <View style={s.stepArcTrack} />
                <Animated.View style={[s.stepArcSpin, {
                  transform: [{ rotate: stepSpin.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '360deg'] }) }],
                }]} />
                <View style={[s.stepDot, s.stepDotActive]}>
                  <Ionicons name="swap-horizontal" size={13} color="#fff" />
                </View>
              </View>
              <Text style={[s.stepLabel, s.stepLabelActive]}>Transfiere</Text>
            </View>

            <View style={s.stepLine} />

            {/* Paso 3 — pendiente: Recibe */}
            <View style={s.step}>
              <View style={s.stepDot}>
                <Ionicons name="gift-outline" size={13} color={DIM} />
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
          style={[s.card, { backgroundColor: '#0D1117', borderColor: '#0D1117' }]}
        >
          {/* ID + timer */}
          <View style={s.cardTopRow}>
            <View>
              <Text style={[s.cardMeta, { color: 'rgba(255,255,255,0.45)' }]}>ID de Operación</Text>
              <Text style={[s.cardOpId, { color: '#fff', fontSize: 19 }]}>{operation.operation_id}</Text>
            </View>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
              <View style={[s.timerPill, isExpired && s.timerPillExpired]}>
                <Ionicons name="time-outline" size={13} color={isExpired ? '#ef4444' : '#fbbf24'} />
                <Text style={[s.timerText, isExpired && s.timerTextExpired]}>
                  {isExpired ? 'Expirado' : timeRemaining}
                </Text>
              </View>
              <TouchableOpacity onPress={() => setShowTimerInfo(true)} activeOpacity={0.7}
                style={{ width: 20, height: 20, borderRadius: 10, backgroundColor: 'rgba(255,255,255,0.12)', alignItems: 'center', justifyContent: 'center' }}>
                <Ionicons name="help" size={11} color="rgba(255,255,255,0.7)" />
              </TouchableOpacity>
            </View>
          </View>

          <View style={[s.hairline, { backgroundColor: 'rgba(255,255,255,0.1)' }]} />

          {/* Meta */}
          <View style={s.metaRow}>
            <View style={s.metaItem}>
              <Text style={[s.metaLabel, { color: 'rgba(255,255,255,0.45)' }]}>Tipo</Text>
              <Text style={[s.metaValue, { color: '#fff' }]}>
                {operation.operation_type === 'Compra' ? 'Qoricash Compra' : 'Qoricash Vende'}
              </Text>
            </View>
            <View style={s.metaItem}>
              <Text style={[s.metaLabel, { color: 'rgba(255,255,255,0.45)' }]}>Fecha</Text>
              <Text style={[s.metaValue, { color: '#fff' }]}>{formatDateTime(operation.created_at)}</Text>
            </View>
          </View>

          <View style={[s.hairline, { backgroundColor: 'rgba(255,255,255,0.1)' }]} />

          {/* Montos */}
          <View style={{ flexDirection: 'row', alignItems: 'center' }}>
            <View style={{ flex: 1, gap: 3 }}>
              <Text style={{ fontSize: 11, color: 'rgba(255,255,255,0.45)', fontWeight: '500', letterSpacing: 0.5, textTransform: 'uppercase' }}>
                {operation.operation_type === 'Compra' ? '🇺🇸 Envías' : '🇵🇪 Envías'}
              </Text>
              <Text style={{ fontSize: 28, fontWeight: '800', color: '#fff', letterSpacing: -0.5 }} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.5}>
                {operation.operation_type === 'Compra'
                  ? formatCurrency(operation.amount_usd, 'USD')
                  : formatCurrency(operation.amount_pen, 'PEN')}
              </Text>
            </View>

            <View style={{ alignItems: 'center', gap: 3, paddingHorizontal: 8 }}>
              <Ionicons name="swap-horizontal" size={14} color="rgba(255,255,255,0.35)" />
              <Text style={{ fontSize: 10, color: 'rgba(255,255,255,0.4)', fontWeight: '600' }}>{operation.exchange_rate.toFixed(4)}</Text>
            </View>

            <View style={{ flex: 1, gap: 3, alignItems: 'flex-end' }}>
              <Text style={{ fontSize: 11, color: 'rgba(255,255,255,0.45)', fontWeight: '500', letterSpacing: 0.5, textTransform: 'uppercase' }}>
                {operation.operation_type === 'Compra' ? '🇵🇪 Recibes' : '🇺🇸 Recibes'}
              </Text>
              <Text style={{ fontSize: 28, fontWeight: '800', color: GREEN, letterSpacing: -0.5 }} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.5}>
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
              <Ionicons name="business-outline" size={18} color="#FFFFFF" />
            </View>
            <View>
              <Text style={s.cardMeta}>Transfiere a</Text>
              <Text style={s.transferToName}>Qoricash SAC</Text>
              <Text style={s.transferToRuc}>RUC 20612229524</Text>
            </View>
          </View>

          <View style={s.hairline} />

          {/* Banco */}
          <View style={[s.detailRow, { overflow: 'hidden', height: 36, paddingVertical: 0, alignItems: 'center', marginRight: -18 }]}>
            <Text style={s.detailLabel}>Banco</Text>
            {BANK_LOGOS[qoriAccount.bank_name.toUpperCase()] ? (
              <Image
                source={BANK_LOGOS[qoriAccount.bank_name.toUpperCase()]}
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

          {!['BCP', 'INTERBANK', 'BANBIF'].includes((operation.source_bank_name || '').toUpperCase()) && (
            <View style={s.infoBanner}>
              <Ionicons name="information-circle-outline" size={15} color="#60a5fa" />
              <Text style={s.infoBannerText}>
                {operation.operation_type === 'Compra'
                  ? 'Si tienes tus dólares en un banco que no sea BCP, INTERBANK o BANBIF, envíalos a través de nuestro CCI INTERBANK, es inmediato. Guarda el número de tu operación bancaria, lo necesitarás en el siguiente paso.'
                  : 'Si tienes tus soles en un banco que no sea BCP, INTERBANK o BANBIF, envíalos a través de nuestro CCI INTERBANK, es inmediato. Guarda el número de tu operación bancaria, lo necesitarás en el siguiente paso.'
                }
              </Text>
            </View>
          )}

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

          <TouchableOpacity
            style={s.supportBtn}
            activeOpacity={0.7}
            onPress={() => {
              const msg = `Hola, necesito ayuda con mi operación ${operation.operation_id}`;
              Linking.openURL(`https://wa.me/51910624404?text=${encodeURIComponent(msg)}`);
            }}
          >
            <Ionicons name="logo-whatsapp" size={16} color="#25D366" />
            <Text style={s.supportBtnText}>Contactar con soporte</Text>
          </TouchableOpacity>
        </MotiView>

      </ScrollView>

      {/* ═══════════════════════════════════════════════════════════════════════
          MODAL — Código de transferencia
      ═══════════════════════════════════════════════════════════════════════ */}
      <Modal
        visible={transferCodeModalVisible}
        transparent
        animationType="fade"
        onRequestClose={() => {
          if (submitAnimPhase === 'idle') { setTransferCodeModalVisible(false); setTransferCode(''); }
        }}
      >
        <KeyboardAvoidingView
          style={s.modalOverlay}
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        >
          <View style={[StyleSheet.absoluteFill, { backgroundColor: 'rgba(0,0,0,0.65)' }]} />
          <View style={s.modalSheet}>
            {/* Header — fondo negro */}
            <View style={[s.modalHeader, { backgroundColor: '#0D1117' }]}>
              <View style={[s.modalIconWrap, { backgroundColor: 'rgba(255,255,255,0.12)', borderColor: 'rgba(255,255,255,0.15)' }]}>
                <Ionicons name="receipt-outline" size={18} color="#FFFFFF" />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={[s.modalTitle, { color: '#FFFFFF' }]}>Código de transferencia</Text>
                <Text style={[s.modalSub, { color: 'rgba(255,255,255,0.55)' }]}>Ingresa el número de tu voucher bancario</Text>
              </View>
              <TouchableOpacity
                onPress={() => { if (submitAnimPhase === 'idle') { setTransferCodeModalVisible(false); setTransferCode(''); } }}
                activeOpacity={0.7}
                style={[s.modalCloseBtn, { backgroundColor: 'rgba(255,255,255,0.12)' }]}
              >
                <Ionicons name="close" size={18} color="rgba(255,255,255,0.7)" />
              </TouchableOpacity>
            </View>

            {submitAnimPhase === 'idle' ? (
              <>
                <View style={s.modalBody}>
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
                    placeholderTextColor="rgba(0,0,0,0.3)"
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
          <BlurView intensity={55} tint="dark" style={StyleSheet.absoluteFill} />
          <View style={[StyleSheet.absoluteFill, { backgroundColor: 'rgba(0,0,0,0.35)' }]} />
          <View style={s.cancelSheet}>
            {cancelAnimPhase === 'idle' ? (
              <>
                {/* Header */}
                <View style={s.cancelIconBlock}>
                  <View style={s.cancelIconRing}>
                    <Ionicons name="close-circle" size={19} color="#fff" />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={s.cancelTitle}>Cancelar operación</Text>
                    <Text style={s.cancelSubtitle}>Esta acción no se puede deshacer</Text>
                  </View>
                  <TouchableOpacity
                    onPress={() => { if (!canceling) { setCancelModalVisible(false); setCancelReason(''); } }}
                    activeOpacity={0.7}
                    style={[s.modalCloseBtn, { backgroundColor: '#F3F4F6' }]}
                  >
                    <Ionicons name="close" size={18} color="#6B7280" />
                  </TouchableOpacity>
                </View>

                <View style={s.cancelBody}>
                  {/* Chip operación */}
                  <View style={s.cancelOpRow}>
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                      <Ionicons name="pricetag-outline" size={13} color="#9CA3AF" />
                      <Text style={[s.modalOpIdLabel, { color: '#6B7280' }]}>Operación</Text>
                    </View>
                    <View style={s.cancelOpChip}>
                      <Text style={s.cancelOpChipText}>{operation.operation_id}</Text>
                    </View>
                  </View>

                  {/* Input motivo */}
                  <Text style={[s.modalInputLabel, { color: '#374151' }]}>
                    Motivo de cancelación{'  '}<Text style={{ color: '#ef4444' }}>*</Text>
                  </Text>
                  <TextInput
                    style={[s.modalInput, s.modalInputMultiline,
                      { backgroundColor: '#F8FAFC', borderColor: 'rgba(0,0,0,0.10)', color: '#0D1117' },
                      cancelReason.trim() ? s.cancelInputActive : undefined,
                    ]}
                    value={cancelReason}
                    onChangeText={setCancelReason}
                    placeholder="Ej: Cambié de opinión, error en el monto..."
                    placeholderTextColor="#C4C9D4"
                    multiline
                    numberOfLines={3}
                  />
                  {!cancelReason.trim() && (
                    <Text style={s.fieldRequired}>Campo obligatorio para continuar</Text>
                  )}
                </View>

                {/* Botones */}
                <View style={s.cancelActions}>
                  <TouchableOpacity
                    style={[s.cancelBtnConfirm, !cancelReason.trim() && s.cancelBtnConfirmDisabled]}
                    onPress={handleCancelOperation}
                    disabled={!cancelReason.trim()}
                    activeOpacity={0.85}
                  >
                    <Ionicons name="close-circle-outline" size={18} color="#fff" />
                    <Text style={s.cancelBtnConfirmText}>Confirmar cancelación</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={s.cancelBtnBack}
                    onPress={() => { setCancelModalVisible(false); setCancelReason(''); }}
                    activeOpacity={0.8}
                  >
                    <Text style={s.cancelBtnBackText}>Volver sin cancelar</Text>
                  </TouchableOpacity>
                </View>
              </>
            ) : (
              <View style={s.animContainer}>
                {cancelAnimPhase === 'loading' ? (
                  <>
                    {/* Multi-ring premium loader */}
                    <View style={{ width: 80, height: 80, alignItems: 'center', justifyContent: 'center' }}>
                      {/* Outer static track */}
                      <View style={{
                        position: 'absolute',
                        width: 80, height: 80, borderRadius: 40,
                        borderWidth: 1, borderColor: 'rgba(239,68,68,0.12)',
                      }} />
                      {/* Main arc — clockwise */}
                      <Animated.View style={{
                        position: 'absolute',
                        width: 80, height: 80, borderRadius: 40,
                        borderWidth: 2,
                        borderTopColor: '#ef4444',
                        borderRightColor: '#ef4444',
                        borderBottomColor: 'rgba(239,68,68,0.25)',
                        borderLeftColor: 'transparent',
                        transform: [{ rotate: cancelSpinAnim.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '360deg'] }) }],
                      }} />
                      {/* Inner arc — counter-clockwise */}
                      <Animated.View style={{
                        position: 'absolute',
                        width: 56, height: 56, borderRadius: 28,
                        borderWidth: 1.5,
                        borderTopColor: 'transparent',
                        borderRightColor: 'transparent',
                        borderBottomColor: 'rgba(239,68,68,0.55)',
                        borderLeftColor: 'rgba(239,68,68,0.55)',
                        transform: [{ rotate: cancelSpin2.interpolate({ inputRange: [0, 1], outputRange: ['360deg', '0deg'] }) }],
                      }} />
                      {/* Center pulsing dot */}
                      <Animated.View style={{
                        width: 8, height: 8, borderRadius: 4,
                        backgroundColor: '#ef4444',
                        opacity: 0.7,
                        transform: [{ scale: cancelDotScale }],
                      }} />
                    </View>
                    <Text style={s.animText}>Anulando operación...</Text>
                    <Text style={s.animSub}>Esto tomará un momento</Text>
                  </>
                ) : (
                  <>
                    {/* Outlined check — no solid fill, lines only */}
                    <Animated.View style={{
                      transform: [{ scale: cancelCheckScale }],
                      opacity: cancelCheckOpacity,
                      shadowColor: '#ef4444',
                      shadowOffset: { width: 0, height: 0 },
                      shadowOpacity: 0.35,
                      shadowRadius: 18,
                    }}>
                      <Ionicons name="checkmark-circle-outline" size={76} color="#ef4444" />
                    </Animated.View>
                    <Text style={[s.animText, { color: '#ef4444' }]}>Operación anulada</Text>
                    <Text style={s.animSub}>Tu solicitud fue procesada</Text>
                  </>
                )}
              </View>
            )}
          </View>
        </KeyboardAvoidingView>
      </Modal>

      {/* ═══════════════════════════════════════════════════════════════════════
          MODAL — Info tiempo límite
      ═══════════════════════════════════════════════════════════════════════ */}
      <Modal
        visible={showTimerInfo}
        transparent
        animationType="fade"
        onRequestClose={() => setShowTimerInfo(false)}
      >
        <TouchableOpacity
          style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.55)', justifyContent: 'center', alignItems: 'center', padding: 32 }}
          activeOpacity={1}
          onPress={() => setShowTimerInfo(false)}
        >
          <View style={{ backgroundColor: '#fff', borderRadius: 20, padding: 24, width: '100%', shadowColor: '#000', shadowOffset: { width: 0, height: 8 }, shadowOpacity: 0.15, shadowRadius: 24, elevation: 12 }}>
            {/* Icono animado */}
            <View style={{ width: 56, height: 56, borderRadius: 28, backgroundColor: 'rgba(13,17,23,0.06)', borderWidth: 1, borderColor: 'rgba(13,17,23,0.1)', alignItems: 'center', justifyContent: 'center', marginBottom: 14, alignSelf: 'center' }}>
              <Animated.View style={{ transform: [{ rotate: timerInfoSpin.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '360deg'] }) }] }}>
                <Ionicons name="time-outline" size={28} color="#0D1117" />
              </Animated.View>
            </View>
            {/* Título */}
            <Text style={{ fontSize: 16, fontWeight: '800', color: '#0D1117', textAlign: 'center', marginBottom: 10 }}>
              Tiempo límite de transferencia
            </Text>
            {/* Cuerpo */}
            <Text style={{ fontSize: 13.5, color: '#4B5563', lineHeight: 21, textAlign: 'center', marginBottom: 20 }}>
              Tienes <Text style={{ fontWeight: '700', color: '#0D1117' }}>{OPERATION_TIMEOUT_MINUTES} minutos</Text> para realizar la transferencia bancaria e ingresar el número de operación.{'\n\n'}
              Si el tiempo se agota sin confirmación, la operación será <Text style={{ fontWeight: '700', color: '#ef4444' }}>cancelada automáticamente</Text> y deberás iniciar una nueva.
            </Text>
            {/* Botón */}
            <TouchableOpacity
              onPress={() => setShowTimerInfo(false)}
              activeOpacity={0.8}
              style={{ backgroundColor: '#0D1117', borderRadius: 12, paddingVertical: 13, alignItems: 'center' }}
            >
              <Text style={{ fontSize: 14, fontWeight: '700', color: '#fff' }}>Entendido</Text>
            </TouchableOpacity>
          </View>
        </TouchableOpacity>
      </Modal>
    </View>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
const s = StyleSheet.create({
  root: {
    flex: 1,
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
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: 'rgba(0,0,0,0.08)',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06,
    shadowRadius: 4,
    elevation: 2,
  },
  headerCenter: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerLogo: {
    width: 110,
    height: 26,
  },
  corporateLabel: {
    fontSize: 9,
    fontWeight: '500',
    color: '#9CA3AF',
    letterSpacing: 2.5,
    marginTop: 2,
    marginLeft: 18,
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
    backgroundColor: '#F3F4F6',
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
    backgroundColor: '#0D1117',
    borderColor: '#0D1117',
    borderWidth: 1.5,
  },
  stepDotActiveWrap: {
    width: 38,
    height: 38,
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepArcTrack: {
    position: 'absolute',
    width: 38,
    height: 38,
    borderRadius: 19,
    borderWidth: 1.5,
    borderColor: 'rgba(0,0,0,0.12)',
  },
  stepArcSpin: {
    position: 'absolute',
    width: 38,
    height: 38,
    borderRadius: 19,
    borderWidth: 1.5,
    borderTopColor: '#0D1117',
    borderRightColor: '#0D1117',
    borderBottomColor: '#0D1117',
    borderLeftColor: 'transparent',
  },
  stepLine: {
    flex: 1,
    height: 2,
    backgroundColor: 'rgba(0,0,0,0.08)',
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
    color: '#0D1117',
    fontWeight: '700',
  },

  // ── Cards ────────────────────────────────────────────────────────────────────
  card: {
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: 'rgba(0,0,0,0.06)',
    borderRadius: 22,
    marginHorizontal: 16,
    marginBottom: 14,
    padding: 18,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.08,
    shadowRadius: 16,
    elevation: 6,
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
    color: '#0D1117',
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
    color: '#0D1117',
  },

  // Resumen — montos
  amountsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  amountBlock: {
    flex: 1,
    backgroundColor: '#F3F4F6',
    borderRadius: 12,
    padding: 12,
    alignItems: 'center',
  },
  amountLabel: {
    fontSize: 9,
    color: DIM,
    fontWeight: '500',
    marginBottom: 5,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
  },
  amountValue: {
    fontSize: 22,
    fontWeight: '700',
    color: '#0D1117',
    letterSpacing: -0.3,
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
    backgroundColor: '#0D1117',
    borderWidth: 0,
    borderColor: 'transparent',
    alignItems: 'center',
    justifyContent: 'center',
  },
  transferToName: {
    fontSize: 16,
    fontWeight: '700',
    color: '#0D1117',
  },
  transferToRuc: {
    fontSize: 12,
    fontWeight: '400',
    color: 'rgba(0,0,0,0.45)',
    marginTop: 2,
  },

  // Detalles — filas
  detailRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 9,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(0,0,0,0.07)',
  },
  detailLabel: {
    fontSize: 13,
    color: DIM,
    flex: 1,
  },
  detailValue: {
    fontSize: 14,
    fontWeight: '600',
    color: '#0D1117',
    flex: 2,
    textAlign: 'right',
  },
  bankLogo: {
    width: 110,
    height: 38,
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
    color: '#2563eb',
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
    color: '#d97706',
    lineHeight: 17,
  },

  // ── Botones ──────────────────────────────────────────────────────────────────
  actionsWrap: {
    marginHorizontal: 16,
    gap: 10,
  },
  primaryBtn: {
    backgroundColor: '#0D1117',
    borderRadius: 16,
    paddingVertical: 16,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.12,
    shadowRadius: 4,
    elevation: 3,
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
    borderColor: 'rgba(0,0,0,0.20)',
    backgroundColor: 'transparent',
  },
  dangerBtnText: {
    color: '#dc2626',
    fontSize: 14,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  supportBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 7,
    paddingVertical: 14,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: 'rgba(0,0,0,0.20)',
    backgroundColor: 'transparent',
  },
  supportBtnText: {
    fontSize: 14,
    color: '#25D366',
    fontWeight: '600',
  },

  // ── Modales ──────────────────────────────────────────────────────────────────
  modalOverlay: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 20,
  },
  modalSheet: {
    width: '100%',
    backgroundColor: '#FFFFFF',
    borderRadius: 24,
    overflow: 'hidden',
    borderWidth: 0,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.18,
    shadowRadius: 28,
    elevation: 20,
  },
  modalCloseBtn: {
    width: 32, height: 32, borderRadius: 16,
    backgroundColor: '#F3F4F6',
    alignItems: 'center', justifyContent: 'center',
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingHorizontal: 18,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(0,0,0,0.07)',
  },
  modalIconWrap: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: 'rgba(34,197,94,0.12)',
    borderWidth: 1,
    borderColor: 'rgba(34,197,94,0.28)',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: GREEN,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.25,
    shadowRadius: 8,
    elevation: 4,
  },
  modalIconWrapDanger: {
    backgroundColor: 'rgba(239,68,68,0.12)',
    borderColor: 'rgba(239,68,68,0.25)',
  },
  modalTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#0D1117',
    letterSpacing: 0.1,
  },
  modalSub: {
    fontSize: 11,
    color: DIM,
    marginTop: 2,
  },
  modalBody: {
    paddingHorizontal: 18,
    paddingTop: 16,
    paddingBottom: 6,
  },
  modalOpIdRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#F9FAFB',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: 'rgba(0,0,0,0.07)',
    paddingVertical: 9,
    paddingHorizontal: 12,
    marginBottom: 12,
  },
  modalOpIdChip: {
    backgroundColor: '#16a34a',
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderWidth: 0,
  },
  modalOpIdLabel: {
    fontSize: 12,
    color: DIM,
    fontWeight: '500',
  },
  modalOpIdValue: {
    fontSize: 13,
    fontWeight: '700',
    color: '#FFFFFF',
    letterSpacing: 0.5,
  },
  modalInfoBanner: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
    backgroundColor: 'rgba(96,165,250,0.05)',
    borderWidth: 1,
    borderColor: 'rgba(96,165,250,0.12)',
    borderLeftWidth: 3,
    borderLeftColor: '#60a5fa',
    borderRadius: 8,
    padding: 10,
    marginBottom: 14,
  },
  modalInfoAccent: {
    display: 'none',
  },
  modalInfoText: {
    flex: 1,
    fontSize: 12,
    color: '#2563eb',
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
    color: '#FFFFFF',
    lineHeight: 18,
  },
  modalInputLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: '#0D1117',
    marginBottom: 10,
  },
  modalInput: {
    backgroundColor: '#F3F4F6',
    borderWidth: 1.5,
    borderColor: 'rgba(0,0,0,0.08)',
    borderRadius: 14,
    color: '#0D1117',
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
    borderColor: '#0D1117',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.08,
    shadowRadius: 4,
    elevation: 2,
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
    gap: 8,
    paddingHorizontal: 18,
    paddingTop: 14,
    paddingBottom: 6,
    borderTopWidth: 1,
    borderTopColor: 'rgba(0,0,0,0.07)',
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
    color: '#6B7280',
  },
  modalCancelLink: {
    alignItems: 'center',
    paddingVertical: 10,
  },
  modalCancelLinkText: {
    fontSize: 14,
    fontWeight: '500',
    color: 'rgba(0,0,0,0.4)',
  },
  modalBtnGreen: {
    paddingVertical: 14,
    borderRadius: 14,
    alignItems: 'center',
    backgroundColor: '#0D1117',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.12,
    shadowRadius: 4,
    elevation: 3,
  },
  modalBtnGreenDisabled: {
    backgroundColor: 'rgba(0,0,0,0.12)',
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

  // ── Cancel Modal ──────────────────────────────────────────────────────────────
  cancelSheet: {
    width: '100%',
    backgroundColor: '#FFFFFF',
    borderRadius: 24,
    overflow: 'hidden',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.18,
    shadowRadius: 24,
    elevation: 18,
  },
  cancelIconBlock: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingHorizontal: 18,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(0,0,0,0.07)',
  },
  cancelIconRing: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#dc2626',
    borderWidth: 1,
    borderColor: '#dc2626',
    alignItems: 'center',
    justifyContent: 'center',
  },
  cancelTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: '#0D1117',
    letterSpacing: 0.1,
    marginBottom: 2,
  },
  cancelSubtitle: {
    fontSize: 11,
    color: 'rgba(0,0,0,0.4)',
  },
  cancelBody: {
    paddingHorizontal: 18,
    paddingTop: 16,
    paddingBottom: 6,
  },
  cancelOpRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#F9FAFB',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: 'rgba(0,0,0,0.07)',
    paddingHorizontal: 12,
    paddingVertical: 9,
    marginBottom: 12,
  },
  cancelOpChip: {
    backgroundColor: '#dc2626',
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderWidth: 1,
    borderColor: '#dc2626',
  },
  cancelOpChipText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#FFFFFF',
    letterSpacing: 0.3,
  },
  cancelWarning: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
    backgroundColor: 'rgba(239,68,68,0.06)',
    borderWidth: 1,
    borderColor: 'rgba(239,68,68,0.18)',
    borderRadius: 10,
    padding: 10,
    marginBottom: 14,
  },
  cancelWarningText: {
    flex: 1,
    fontSize: 12,
    color: '#dc2626',
    lineHeight: 17,
  },
  cancelInputActive: {
    borderColor: 'rgba(239,68,68,0.5)',
    shadowColor: '#ef4444',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.15,
    shadowRadius: 6,
  },
  cancelActions: {
    flexDirection: 'column',
    gap: 8,
    paddingHorizontal: 18,
    paddingTop: 14,
    paddingBottom: 20,
    borderTopWidth: 1,
    borderTopColor: 'rgba(0,0,0,0.06)',
  },
  cancelBtnConfirm: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 14,
    borderRadius: 14,
    backgroundColor: '#0D1117',
    borderWidth: 1,
    borderColor: '#0D1117',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.25,
    shadowRadius: 10,
    elevation: 4,
  },
  cancelBtnConfirmDisabled: {
    backgroundColor: 'rgba(0,0,0,0.08)',
    borderColor: 'rgba(0,0,0,0.08)',
    shadowOpacity: 0,
    elevation: 0,
  },
  cancelBtnConfirmText: {
    fontSize: 15,
    fontWeight: '700',
    color: '#fff',
    letterSpacing: 0.2,
  },
  cancelBtnBack: {
    paddingVertical: 12,
    borderRadius: 14,
    alignItems: 'center',
    backgroundColor: 'transparent',
    borderWidth: 1,
    borderColor: 'rgba(0,0,0,0.12)',
  },
  cancelBtnBackText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#374151',
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
    color: '#0D1117',
    textAlign: 'center',
  },
  animSub: {
    fontSize: 13,
    color: DIM,
    textAlign: 'center',
  },
});
