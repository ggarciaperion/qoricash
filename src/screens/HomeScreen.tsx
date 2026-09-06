import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  Animated,
  RefreshControl,
  Image,
  ImageBackground,
  Alert,
  Modal,
  TouchableOpacity,
  Text,
  TextInput,
  Dimensions,
  KeyboardAvoidingView,
  Keyboard,
  Platform,
} from 'react-native';
import { MotiView } from 'moti';
import { Ionicons } from '@expo/vector-icons';
import Reanimated, {
  useSharedValue,
  useAnimatedStyle,
  withRepeat,
  withSequence,
  withSpring,
  withTiming,
  interpolate,
  Easing as REasing,
  cancelAnimation,
  runOnJS,
} from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { BlurView } from 'expo-blur';
import * as Haptics from 'expo-haptics';
import { CommonActions } from '@react-navigation/native';
import axios from 'axios';
import socketService from '../services/socketService';
import { useAuth } from '../contexts/AuthContext';
import { useLoginLoading } from '../contexts/LoginLoadingContext';
import { Calculator } from '../components/Calculator';
import { API_CONFIG } from '../constants/config';
import { Operation } from '../types';
import { useBackground } from '../hooks/useBackground';

const { width: W } = Dimensions.get('window');

// Reloj animado para el banner "Validación en proceso"
const ClockIcon: React.FC = () => {
  const rot = useSharedValue(0);
  const sc  = useSharedValue(1);
  useEffect(() => {
    rot.value = withRepeat(
      withTiming(1, { duration: 6000, easing: REasing.linear }), -1, false,
    );
    sc.value = withRepeat(
      withSequence(
        withTiming(1.18, { duration: 1100, easing: REasing.inOut(REasing.quad) }),
        withTiming(1,    { duration: 1100, easing: REasing.inOut(REasing.quad) }),
      ), -1, false,
    );
  }, []);
  const style = useAnimatedStyle(() => ({
    transform: [
      { rotate: `${interpolate(rot.value, [0, 1], [0, 360])}deg` },
      { scale: sc.value },
    ],
  }));
  return (
    <Reanimated.View style={style}>
      <Ionicons name="time-outline" size={18} color="#FFFFFF" />
    </Reanimated.View>
  );
};

const GREEN        = '#22c55e';
const TAB_BAR_H   = 72;

interface HomeScreenProps { navigation: any }

const capitalize = (s: string) =>
  s ? s.charAt(0).toUpperCase() + s.slice(1).toLowerCase() : s;

// ─── ActiveOpCard ─────────────────────────────────────────────────────────────
interface ActiveOpCardProps {
  op: Operation;
  onPress: () => void;
  accentColor: string;
  bgColor: string;
  borderColor: string;
  isEnProceso: boolean;
}

const ActiveOpCard: React.FC<ActiveOpCardProps> = ({
  op, onPress, accentColor, bgColor, borderColor, isEnProceso,
}) => {
  const spin       = useSharedValue(0);
  const clockScale = useSharedValue(1);
  const cardBorder = useSharedValue(0.22);

  useEffect(() => {
    spin.value = withRepeat(
      withTiming(1, { duration: 2400, easing: REasing.linear }),
      -1, false,
    );
    clockScale.value = withRepeat(
      withSequence(
        withTiming(1.15, { duration: 850, easing: REasing.inOut(REasing.quad) }),
        withTiming(1,    { duration: 850, easing: REasing.inOut(REasing.quad) }),
      ), -1, false,
    );
    cardBorder.value = withRepeat(
      withSequence(
        withTiming(0.5,  { duration: 1100, easing: REasing.inOut(REasing.quad) }),
        withTiming(0.22, { duration: 1100, easing: REasing.inOut(REasing.quad) }),
      ), -1, false,
    );
  }, []);

  const spinStyle  = useAnimatedStyle(() => ({
    transform: [{ rotate: `${interpolate(spin.value, [0, 1], [0, 360])}deg` }],
  }));
  const iconStyle  = useAnimatedStyle(() => ({
    transform: [{ scale: clockScale.value }],
  }));
  const glowStyle  = useAnimatedStyle(() => ({
    opacity: cardBorder.value,
  }));

  return (
    <TouchableOpacity
      style={[s.activeOpCard, { backgroundColor: bgColor, borderColor }]}
      onPress={onPress}
      activeOpacity={0.8}
    >
      <Reanimated.View style={[StyleSheet.absoluteFill, s.activeOpGlowBorder, { borderColor: accentColor }, glowStyle]} pointerEvents="none" />
      <View style={s.activeOpIconWrap}>
        <Reanimated.View style={[s.activeOpSpinArc, { borderTopColor: accentColor }, spinStyle]} />
        <Reanimated.View style={[s.activeOpIcon, { backgroundColor: `${accentColor}1A` }, iconStyle]}>
          <Ionicons name="time-outline" size={16} color={accentColor} />
        </Reanimated.View>
      </View>
      <View style={s.activeOpContent}>
        <Text style={s.activeOpId}>{op.operation_id}</Text>
        <Text style={s.activeOpDetail}>
          {op.operation_type} · ${op.amount_usd.toFixed(2)} · S/ {op.amount_pen.toFixed(2)}
        </Text>
        <Text style={{ fontSize: 10.5, color: 'rgba(255,255,255,0.5)', marginTop: 2, fontWeight: '500' }}>
          T.C. {op.exchange_rate.toFixed(4)}
          {op.destination_bank_name ? `  ·  ${op.destination_bank_name} ****${(op.destination_account || '').slice(-4)}` : ''}
        </Text>
      </View>
      <View style={s.activeOpRight}>
        <View style={[s.activeOpPill, { backgroundColor: 'rgba(255,255,255,0.18)', borderColor: 'rgba(255,255,255,0.35)' }]}>
          <Text style={[s.activeOpPillText, { color: '#fff' }]}>
            {isEnProceso ? 'En proceso' : 'Pendiente'}
          </Text>
        </View>
        <Ionicons name="chevron-forward" size={13} color="rgba(255,255,255,0.4)" style={{ marginTop: 2 }} />
      </View>
    </TouchableOpacity>
  );
};

// ─── LiveDot ──────────────────────────────────────────────────────────────────
const LiveDot: React.FC = () => {
  const scale  = useSharedValue(1);
  const ringOp = useSharedValue(0);
  const ringSc = useSharedValue(1);

  useEffect(() => {
    scale.value = withRepeat(
      withSequence(
        withTiming(1.26, { duration: 750, easing: REasing.inOut(REasing.quad) }),
        withTiming(1,    { duration: 750, easing: REasing.inOut(REasing.quad) }),
      ), -1, false,
    );
    ringOp.value = withRepeat(
      withSequence(
        withTiming(0.55, { duration: 200, easing: REasing.out(REasing.quad) }),
        withTiming(0,    { duration: 1100, easing: REasing.out(REasing.cubic) }),
        withTiming(0,    { duration: 200 }),
      ), -1, false,
    );
    ringSc.value = withRepeat(
      withSequence(
        withTiming(1,   { duration: 0 }),
        withTiming(2.8, { duration: 1300, easing: REasing.out(REasing.cubic) }),
        withTiming(1,   { duration: 0 }),
      ), -1, false,
    );
  }, []);

  const dotStyle  = useAnimatedStyle(() => ({ transform: [{ scale: scale.value }] }));
  const ringStyle = useAnimatedStyle(() => ({
    opacity: ringOp.value,
    transform: [{ scale: ringSc.value }],
  }));

  return (
    <View style={s.dotWrap}>
      <Reanimated.View pointerEvents="none" style={[s.dotPulse, ringStyle]} />
      <Reanimated.View style={[s.dotCore, dotStyle]} />
    </View>
  );
};

// ─── Screen ───────────────────────────────────────────────────────────────────
export const HomeScreen: React.FC<HomeScreenProps> = ({ navigation }) => {
  const bg = useBackground();
  const insets = useSafeAreaInsets();
  const { client, refreshClient } = useAuth();
  const { setShowLogoutLoading } = useLoginLoading();
  const isLegalEntity = client?.document_type === 'RUC';
  const [refreshing, setRefreshing] = useState(false);

  // ── Menú hamburguesa ──
  const [menuVisible, setMenuVisible] = useState(false);

  // ── Cambiar contraseña ──
  const [changePasswordVisible, setChangePasswordVisible] = useState(false);
  const [currentPassword,  setCurrentPassword]  = useState('');
  const [newPassword,      setNewPassword]      = useState('');
  const [confirmPassword,  setConfirmPassword]  = useState('');
  const [showCurrentPwd,   setShowCurrentPwd]   = useState(false);
  const [showNewPwd,       setShowNewPwd]       = useState(false);
  const [showConfirmPwd,   setShowConfirmPwd]   = useState(false);
  const [activeOps, setActiveOps] = useState<Operation[]>([]);

  const fetchActiveOps = async () => {
    if (!client?.dni) return;
    try {
      const res = await axios.get<{ success: boolean; operations: Operation[] }>(
        `${API_CONFIG.BASE_URL}/api/client/my-operations/${client.dni}`
      );
      if (res.data.success) {
        setActiveOps(
          res.data.operations.filter(
            op => op.status === 'pendiente' || op.status === 'en_proceso'
          )
        );
      }
    } catch {}
  };

  useEffect(() => { fetchActiveOps(); }, [client?.dni]);

  const [keyboardHeight, setKeyboardHeight] = useState(0);
  useEffect(() => {
    const showEv = Platform.OS === 'ios' ? 'keyboardWillShow' : 'keyboardDidShow';
    const hideEv = Platform.OS === 'ios' ? 'keyboardWillHide' : 'keyboardDidHide';
    const showSub = Keyboard.addListener(showEv, e => setKeyboardHeight(e.endCoordinates.height));
    const hideSub = Keyboard.addListener(hideEv, () => setKeyboardHeight(0));
    return () => { showSub.remove(); hideSub.remove(); };
  }, []);

  useEffect(() => {
    if (!client?.dni) return;
    socketService.joinClientRoom(client.dni);

    const removeOp = (data: any) => {
      const opId = data?.operation_id || data?.id;
      if (opId) setActiveOps(prev => prev.filter(o => o.operation_id !== opId && o.id !== opId));
    };
    const updateToInProcess = (data: any) => {
      const opId = data?.operation_id || data?.id;
      if (opId) setActiveOps(prev => prev.map(o =>
        (o.operation_id === opId || o.id === opId) ? { ...o, status: 'en_proceso' } : o
      ));
    };

    socketService.on('operacion_completada',     removeOp);
    socketService.on('operacion_cancelada_admin', removeOp);
    socketService.on('operacion_en_proceso',     updateToInProcess);

    const onDocumentsApproved = async () => {
      try { await refreshClient(); } catch {}
      setShowKycModal(true);
      kycScale.value   = 0.82;
      kycOpacity.value = 0;
      kycScale.value   = withSpring(1, { damping: 15, stiffness: 240 });
      kycOpacity.value = withTiming(1, { duration: 220 });
      kycCircle.value  = withSequence(
        withTiming(0, { duration: 0 }),
        withSpring(1, { damping: 10, stiffness: 220 }),
      );
    };
    socketService.on('documents_approved', onDocumentsApproved);

    return () => {
      socketService.off('operacion_completada',     removeOp);
      socketService.off('operacion_cancelada_admin', removeOp);
      socketService.off('operacion_en_proceso',     updateToInProcess);
      socketService.off('documents_approved',       onDocumentsApproved);
    };
  }, [client?.dni]);

  const [showKycModal, setShowKycModal] = useState(false);
  const kycScale   = useSharedValue(0.82);
  const kycOpacity = useSharedValue(0);
  const kycCircle  = useSharedValue(0);

  const kycOverlayStyle = useAnimatedStyle(() => ({ opacity: kycOpacity.value }));
  const kycCardStyle    = useAnimatedStyle(() => ({
    opacity: kycOpacity.value,
    transform: [{ scale: kycScale.value }],
  }));
  const kycCircleStyle  = useAnimatedStyle(() => ({
    transform: [{ scale: kycCircle.value }],
  }));

  const [showBlockModal,   setShowBlockModal]   = useState(false);
  const blockScale   = useSharedValue(0.86);
  const blockOpacity = useSharedValue(0);
  const clockSpin    = useSharedValue(0);

  const [showMinAmountModal, setShowMinAmountModal] = useState(false);
  const minScale   = useSharedValue(0.86);
  const minOpacity = useSharedValue(0);

  useEffect(() => {
    if (showBlockModal) {
      blockScale.value   = 0.86;
      blockOpacity.value = 0;
      blockScale.value   = withSpring(1, { damping: 16, stiffness: 260 });
      blockOpacity.value = withTiming(1, { duration: 180 });
      clockSpin.value    = 0;
      clockSpin.value    = withRepeat(withTiming(1, { duration: 2000, easing: REasing.linear }), -1, false);
    } else {
      cancelAnimation(clockSpin);
    }
  }, [showBlockModal]);

  const [pendingOp, setPendingOp] = useState<{
    ready: boolean;
    operationType: 'Compra' | 'Venta';
    amountUSD: string;
    rate: number;
  }>({ ready: false, operationType: 'Compra', amountUSD: '', rate: 0 });
  const [calcOperationType, setCalcOperationType] = useState<'Compra' | 'Venta'>('Compra');
  const [calcRates, setCalcRates] = useState<{ compra: number; venta: number } | null>(null);

  const EMPRESA_IMPROVEMENT = 0.0010;
  const EMPRESA_STRIKE_DIFF = 0.0030;

  const empresaRates = useMemo(
    () => calcRates && isLegalEntity
      ? { compra: calcRates.compra + EMPRESA_IMPROVEMENT, venta: calcRates.venta - EMPRESA_IMPROVEMENT }
      : null,
    [calcRates, isLegalEntity],
  );

  const REFERRAL_IMPROVEMENT = 0.002;
  const [referralModalVisible, setReferralModalVisible] = useState(false);
  const [referralInput,        setReferralInput]        = useState('');
  const [referralValidating,   setReferralValidating]   = useState(false);
  const [referralApplied,      setReferralApplied]      = useState<string | null>(null);

  const getVolumePips = (usdAmount: number): number => {
    if (usdAmount >= 10000) return 0.0020;
    if (usdAmount >= 5000)  return 0.0015;
    if (usdAmount >= 3000)  return 0.0010;
    return 0;
  };
  const pendingUSD = useMemo(() => {
    if (!pendingOp.ready || !pendingOp.amountUSD || !pendingOp.rate) return 0;
    const val = parseFloat(pendingOp.amountUSD) || 0;
    return pendingOp.operationType === 'Compra' ? val : (pendingOp.rate > 0 ? val / pendingOp.rate : 0);
  }, [pendingOp.ready, pendingOp.amountUSD, pendingOp.rate, pendingOp.operationType]);

  const volumePips    = useMemo(() => getVolumePips(pendingUSD), [pendingUSD]);
  const effectivePips = useMemo(
    () => Math.max(referralApplied ? REFERRAL_IMPROVEMENT : 0, volumePips),
    [referralApplied, volumePips],
  );
  const displayRates = useMemo(
    () => effectivePips > 0 && calcRates
      ? { compra: calcRates.compra + effectivePips, venta: calcRates.venta - effectivePips }
      : null,
    [effectivePips, calcRates],
  );

  const closeReferralModal = () => { setReferralModalVisible(false); setReferralInput(''); };

  const handleValidateReferral = async () => {
    const code = referralInput.trim().toUpperCase();
    if (!code) return;
    setReferralValidating(true);
    try {
      const res = await fetch(`${API_CONFIG.BASE_URL}/api/referrals/validate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code, client_dni: client?.dni }),
      });
      const data = await res.json();
      if (data.is_valid) {
        setReferralApplied(code);
        closeReferralModal();
      } else {
        Alert.alert('Código inválido', data.message || 'El código no es válido');
      }
    } catch {
      Alert.alert('Error', 'No se pudo validar el código. Intenta nuevamente.');
    } finally {
      setReferralValidating(false);
    }
  };

  const handleChangePassword = async () => {
    if (!currentPassword || !newPassword || !confirmPassword) {
      Alert.alert('Error', 'Por favor completa todos los campos'); return;
    }
    if (newPassword.length < 8) {
      Alert.alert('Error', 'La nueva contraseña debe tener al menos 8 caracteres'); return;
    }
    if (newPassword !== confirmPassword) {
      Alert.alert('Error', 'Las contraseñas no coinciden'); return;
    }
    try {
      const response = await fetch(`${API_CONFIG.BASE_URL}/api/client/change-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dni: client?.dni, current_password: currentPassword, new_password: newPassword }),
      });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.message || 'Error al cambiar contraseña');
      Alert.alert('Contraseña Actualizada', 'Tu contraseña ha sido cambiada exitosamente', [{
        text: 'Entendido', onPress: () => {
          setChangePasswordVisible(false);
          setCurrentPassword(''); setNewPassword(''); setConfirmPassword('');
        },
      }]);
    } catch (e: any) {
      Alert.alert('Error', e.message || 'No se pudo cambiar la contraseña');
    }
  };

  const scrollViewRef = useRef<ScrollView>(null);
  const ratesTopY     = useRef(0);

  const refreshSpin = useRef(new Animated.Value(0)).current;
  const refreshAnim = useRef<Animated.CompositeAnimation | null>(null);

  const onRefresh = async () => {
    setRefreshing(true);
    refreshSpin.setValue(0);
    refreshAnim.current = Animated.loop(
      Animated.timing(refreshSpin, { toValue: 1, duration: 700, useNativeDriver: true })
    );
    refreshAnim.current.start();
    await Promise.all([refreshClient(), fetchActiveOps()]);
    refreshAnim.current?.stop();
    setRefreshing(false);
  };

  const refreshRotate = refreshSpin.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '360deg'] });

  const handleInitiateOperation = (
    operationType: 'Compra' | 'Venta',
    amountUSD: string,
    exchangeRate: number,
  ) => {
    const inputVal  = parseFloat(amountUSD) || 0;
    const usdAmount = pendingUSD > 0
      ? pendingUSD
      : (operationType === 'Compra' ? inputVal : (exchangeRate > 0 ? inputVal / exchangeRate : 0));
    if (usdAmount < 50) {
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
      minScale.value   = 0.86;
      minOpacity.value = 0;
      minScale.value   = withSpring(1, { damping: 16, stiffness: 260 });
      minOpacity.value = withTiming(1, { duration: 180 });
      setShowMinAmountModal(true);
      return;
    }
    if (activeOps.length > 0) {
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
      setShowBlockModal(true);
      return;
    }
    if (!client?.has_complete_documents) {
      Alert.alert('Validación Requerida', 'Completa tu verificación de identidad primero.', [{ text: 'Entendido' }]);
      return;
    }
    const baseRate = calcRates
      ? (operationType === 'Compra' ? calcRates.compra : calcRates.venta)
      : null;
    navigation.navigate('NewOperation', {
      operationType,
      amountUSD: usdAmount.toString(),
      exchangeRate,
      baseExchangeRate: baseRate,
    });
  };

  const handleNuevaOperacion = () => {
    if (activeOps.length > 0) { Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning); setShowBlockModal(true); return; }
    if (!client?.has_complete_documents) {
      Alert.alert('Validación Requerida', 'Completa tu verificación de identidad primero.', [{ text: 'Entendido' }]); return;
    }
    const rate = (empresaRates ?? displayRates ?? calcRates)?.compra ?? 0;
    navigation.navigate('NewOperation', { operationType: 'Compra', amountUSD: '0', exchangeRate: rate, baseExchangeRate: calcRates?.compra ?? rate });
  };

  if (!client) {
    return (
      <View style={s.loadWrap}>
        <Text style={s.loadText}>Cargando...</Text>
      </View>
    );
  }

  const blockModalStyle = useAnimatedStyle(() => ({
    opacity:   blockOpacity.value,
    transform: [{ scale: blockScale.value }],
  }));

  const clockSpinStyle = useAnimatedStyle(() => ({
    transform: [{ rotate: `${interpolate(clockSpin.value, [0, 1], [0, 360])}deg` }],
  }));

  const minModalStyle = useAnimatedStyle(() => ({
    opacity:   minOpacity.value,
    transform: [{ scale: minScale.value }],
  }));

  const firstName = (() => {
    if (client.nombres)   return capitalize(client.nombres.split(' ')[0]);
    if (client.full_name) return capitalize(client.full_name.split(' ')[0]);
    return '';
  })();

  const displayedRates = empresaRates ?? displayRates ?? calcRates;

  // ── Grid tiles ──
  const gridTiles = [
    { icon: 'swap-horizontal-outline' as const, label: 'Nueva operación', onPress: handleNuevaOperacion },
    { icon: 'receipt-outline'         as const, label: 'Historial',       onPress: () => navigation.dispatch(CommonActions.navigate({ name: 'HistoryTab', params: { initialTab: 'completed' } })) },
    { icon: 'bar-chart-outline'       as const, label: 'Mercado',         onPress: () => navigation.dispatch(CommonActions.navigate({ name: 'MarketTab' })) },
    { icon: 'person-outline'          as const, label: 'Perfil',          onPress: () => navigation.dispatch(CommonActions.navigate({ name: 'ProfileTab' })) },
  ];

  // ── Quick actions ──
  const quickActions = [
    { icon: 'swap-horizontal-outline' as const, label: 'Operar',    onPress: handleNuevaOperacion },
    { icon: 'time-outline'            as const, label: 'Historial', onPress: () => navigation.dispatch(CommonActions.navigate({ name: 'HistoryTab', params: { initialTab: 'completed' } })) },
    { icon: 'trending-up-outline'     as const, label: 'Mercado',   onPress: () => navigation.dispatch(CommonActions.navigate({ name: 'MarketTab' })) },
  ];

  return (
    <View style={s.root}>

      {/* ── Fondo blanco ── */}
      <View style={[StyleSheet.absoluteFill, { backgroundColor: '#F5F7FA' }]} pointerEvents="none" />

      {/* ── Scroll ── */}
      <ScrollView
        ref={scrollViewRef}
        style={s.scroll}
        contentContainerStyle={[s.content, { paddingTop: insets.top + 16, paddingBottom: insets.bottom + 80 }]}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#0D1117" />
        }
      >
        <View style={s.centerWrap}>

        {/* ══ Saludo ══ */}
        <MotiView
          from={{ opacity: 0, translateY: 10 }}
          animate={{ opacity: 1, translateY: 0 }}
          transition={{ type: 'spring', delay: 60, damping: 22, stiffness: 180 }}
          style={s.greetingRow}
        >
          <TouchableOpacity
            style={s.menuBtn}
            onPress={() => { Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light); setMenuVisible(true); }}
            activeOpacity={0.75}
          >
            <Ionicons name="menu-outline" size={22} color="#0D1117" />
          </TouchableOpacity>
          <View style={{ flex: 1 }}>
            <Text style={s.greetingSub}>¡Hola,</Text>
            <Text style={s.greetingName}>{firstName}! 👋</Text>
          </View>
          <TouchableOpacity style={s.refreshBtn} onPress={onRefresh}>
            <Animated.View style={refreshing ? { transform: [{ rotate: refreshRotate }] } : undefined}>
              <Ionicons name="refresh-outline" size={20} color="#0D1117" />
            </Animated.View>
          </TouchableOpacity>
        </MotiView>

        {/* ══ Card negra — Tipo de Cambio ══ */}
        <MotiView
          from={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ type: 'spring', delay: 120, damping: 22, stiffness: 160 }}
          style={s.heroCard}
        >
          {/* Card top row */}
          <View style={s.heroCardTopRow}>
            <Text style={s.heroCardTitle}>Tipo de Cambio</Text>
            <View style={s.liveRow}>
              <LiveDot />
              <Text style={s.liveLabel}>En vivo</Text>
            </View>
          </View>

          {/* Rates */}
          <View style={s.heroRatesRow}>
            <View style={s.heroRateItem}>
              <Text style={s.heroRateLabel}>Compramos S/</Text>
              <Text style={s.heroRateValue} numberOfLines={1} adjustsFontSizeToFit>
                {displayedRates?.compra.toFixed(4) ?? '—'}
              </Text>
              <Text style={s.heroRateDir}>USD → PEN</Text>
            </View>
            <View style={s.heroRateDivider} />
            <View style={s.heroRateItem}>
              <Text style={s.heroRateLabel}>Vendemos S/</Text>
              <Text style={s.heroRateValue} numberOfLines={1} adjustsFontSizeToFit>
                {displayedRates?.venta.toFixed(4) ?? '—'}
              </Text>
              <Text style={s.heroRateDir}>PEN → USD</Text>
            </View>
          </View>

          {isLegalEntity && (
            <View style={s.corporateBadge}>
              <Ionicons name="business-outline" size={11} color="rgba(255,255,255,0.6)" />
              <Text style={s.corporateBadgeText}>Tarifa Corporativa</Text>
            </View>
          )}

        </MotiView>

        {/* ══ Banners de verificación ══ */}
        {!client.has_complete_documents && (
          <MotiView
            from={{ opacity: 0, translateY: 10 }}
            animate={{ opacity: 1, translateY: 0 }}
            transition={{ type: 'spring', delay: 260, damping: 20 }}
          >
            {(isLegalEntity ? !client.ficha_ruc_url : (!client.dni_front_url || !client.dni_back_url)) && (
              <TouchableOpacity
                style={s.bannerWarning}
                onPress={() => { Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium); navigation.navigate('VerifyIdentity'); }}
                activeOpacity={0.82}
              >
                <View style={[s.bannerIcon, { backgroundColor: 'rgba(255,255,255,0.18)' }]}>
                  <Ionicons name="shield-outline" size={18} color="#fff" />
                </View>
                <View style={s.bannerBody}>
                  <Text style={s.bannerTitleWarn}>Validación pendiente</Text>
                  <Text style={s.bannerSubWarn}>Necesitamos validar tu identidad para operar.</Text>
                </View>
                <Ionicons name="chevron-forward" size={16} color="rgba(255,255,255,0.6)" />
              </TouchableOpacity>
            )}
            {(isLegalEntity ? !!client.ficha_ruc_url : (client.dni_front_url && client.dni_back_url)) && (
              <View style={s.bannerInfo}>
                <View style={[s.bannerIcon, { backgroundColor: 'rgba(255,255,255,0.18)' }]}>
                  <ClockIcon />
                </View>
                <View style={s.bannerBody}>
                  <Text style={s.bannerTitleInfo}>Validación en proceso</Text>
                  <Text style={s.bannerSub}>⏱ Aprox. 10 min — te notificaremos.</Text>
                </View>
              </View>
            )}
          </MotiView>
        )}

        {/* ══ Grid 2×2 ══ */}
        <MotiView
          from={{ opacity: 0, translateY: 16 }}
          animate={{ opacity: 1, translateY: 0 }}
          transition={{ type: 'spring', delay: 300, damping: 22, stiffness: 160 }}
          style={s.gridWrap}
        >
          {gridTiles.map(({ icon, label, onPress }) => (
            <TouchableOpacity key={label} style={s.gridTile} onPress={onPress} activeOpacity={0.75}>
              <View style={s.gridIconWrap}>
                <Ionicons name={icon} size={26} color="#0D1117" />
              </View>
              <Text style={s.gridLabel}>{label}</Text>
            </TouchableOpacity>
          ))}
        </MotiView>

        {/* ══ Operaciones activas ══ */}
        {activeOps.length > 0 && (
          <MotiView
            from={{ opacity: 0, translateY: 10 }}
            animate={{ opacity: 1, translateY: 0 }}
            transition={{ type: 'spring', delay: 360, damping: 22 }}
            style={s.activeOpsWrap}
          >
            <View style={s.activeOpsHeader}>
              <View style={s.activeOpsDot} />
              <Text style={s.activeOpsLabel}>
                {activeOps.length === 1 ? 'Operación en curso' : `${activeOps.length} operaciones en curso`}
              </Text>
            </View>
            {activeOps.map(op => {
              const isEnProceso = op.status === 'en_proceso';
              return (
                <ActiveOpCard
                  key={op.id}
                  op={op}
                  isEnProceso={isEnProceso}
                  accentColor={isEnProceso ? '#60a5fa' : '#f59e0b'}
                  bgColor={isEnProceso ? '#1d4ed8' : '#1d4ed8'}
                  borderColor={isEnProceso ? '#3b82f6' : '#3b82f6'}
                  onPress={() => {
                    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
                    navigation.dispatch(CommonActions.navigate({ name: isEnProceso ? 'Receive' : 'Transfer', params: { operation: op } }));
                  }}
                />
              );
            })}
          </MotiView>
        )}

        {/* Calculator oculto — necesario para obtener tasas en tiempo real */}
        <View style={{ height: 0, overflow: 'hidden' }} pointerEvents="none">
          <Calculator
            onOperationReady={handleInitiateOperation}
            onAmountChange={(ready, operationType, amountUSD, rate) =>
              setPendingOp({ ready, operationType, amountUSD, rate })
            }
            onRatesChange={setCalcRates}
            onOperationTypeChange={setCalcOperationType}
            externalOperationType={calcOperationType}
            overrideRates={displayRates}
            showStrikeRate={!isLegalEntity}
            hideTabs
          />
        </View>

        </View>{/* /centerWrap */}
      </ScrollView>

      {/* ── Modal: operación activa bloqueante ── */}
      <Modal visible={showBlockModal} transparent animationType="fade" statusBarTranslucent onRequestClose={() => setShowBlockModal(false)}>
        <BlurView intensity={55} tint="dark" style={s.blockModalBackdrop}>
          <Reanimated.View style={[s.blockModalCard, blockModalStyle]}>
            <View style={s.blockModalIconWrap}>
              <Reanimated.View style={clockSpinStyle}>
                <Ionicons name="time-outline" size={32} color="#1d4ed8" />
              </Reanimated.View>
            </View>
            <Text style={s.blockModalTitle}>Tienes una operación activa</Text>
            <Text style={s.blockModalBody}>
              Solo puedes tener una operación en curso a la vez. Completa o cancela tu operación actual antes de iniciar una nueva.
            </Text>
            <TouchableOpacity style={s.blockModalBtnPrimary} activeOpacity={0.82}
              onPress={() => {
                setShowBlockModal(false);
                const op = activeOps[0];
                const isEnProceso = op.status === 'en_proceso';
                navigation.dispatch(CommonActions.navigate({ name: isEnProceso ? 'Receive' : 'Transfer', params: { operation: op } }));
              }}>
              <Ionicons name="arrow-forward-circle-outline" size={17} color="#fff" />
              <Text style={s.blockModalBtnPrimaryText}>Ver operación en curso</Text>
            </TouchableOpacity>
            <TouchableOpacity style={s.blockModalBtnSecondary} activeOpacity={0.7} onPress={() => setShowBlockModal(false)}>
              <Text style={s.blockModalBtnSecondaryText}>Entendido</Text>
            </TouchableOpacity>
          </Reanimated.View>
        </BlurView>
      </Modal>

      {/* ── Modal: monto mínimo ── */}
      <Modal visible={showMinAmountModal} transparent animationType="fade" statusBarTranslucent onRequestClose={() => setShowMinAmountModal(false)}>
        <BlurView intensity={55} tint="dark" style={s.blockModalBackdrop}>
          <Reanimated.View style={[s.blockModalCard, s.minModalCard, minModalStyle]}>
            <View style={s.minModalIconWrap}>
              <Ionicons name="alert-circle-outline" size={32} color="#f59e0b" />
            </View>
            <Text style={s.blockModalTitle}>Monto mínimo no alcanzado</Text>
            <Text style={s.blockModalBody}>
              El importe mínimo para realizar una operación es de{' '}
              <Text style={s.minModalHighlight}>$50 dólares</Text>.{'\n\n'}
              Ajusta el monto e intenta nuevamente.
            </Text>
            <TouchableOpacity style={s.minModalBtnClose} activeOpacity={0.7} onPress={() => setShowMinAmountModal(false)}>
              <Text style={s.blockModalBtnSecondaryText}>Entendido</Text>
            </TouchableOpacity>
          </Reanimated.View>
        </BlurView>
      </Modal>

      {/* ── Modal: Código de referido ── */}
      <Modal visible={referralModalVisible} transparent animationType="fade" onRequestClose={closeReferralModal}>
        <KeyboardAvoidingView style={s.referralModalOverlay} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
          <BlurView intensity={50} tint="dark" style={StyleSheet.absoluteFill} />
          <TouchableOpacity style={StyleSheet.absoluteFill} activeOpacity={1} onPress={closeReferralModal} />
          <View style={s.referralModalSheet}>
            <View style={s.referralModalHeader}>
              <View style={s.referralModalIcon}>
                <Ionicons name="gift-outline" size={20} color={GREEN} />
              </View>
              <Text style={s.referralModalTitle}>Ingresa tu cupón</Text>
              <TouchableOpacity onPress={closeReferralModal} style={s.referralModalClose}>
                <Ionicons name="close" size={20} color="rgba(255,255,255,0.5)" />
              </TouchableOpacity>
            </View>
            <Text style={s.referralModalSub}>
              Ingresa tu cupón o código de referido para desbloquear mejoras exclusivas en tu tipo de cambio.
            </Text>
            <TextInput
              style={s.referralModalInput}
              value={referralInput}
              onChangeText={t => setReferralInput(t.toUpperCase())}
              placeholder="Ej: ABC123"
              placeholderTextColor="rgba(255,255,255,0.25)"
              autoCapitalize="characters"
              maxLength={8}
            />
            <TouchableOpacity
              style={[s.referralModalBtn, (!referralInput.trim() || referralValidating) && s.referralModalBtnDisabled]}
              onPress={handleValidateReferral}
              disabled={!referralInput.trim() || referralValidating}
              activeOpacity={0.85}
            >
              <Text style={s.referralModalBtnText}>{referralValidating ? 'Validando...' : 'Aplicar código'}</Text>
            </TouchableOpacity>
          </View>
        </KeyboardAvoidingView>
      </Modal>

      {/* ── Modal: KYC aprobado ── */}
      <Modal visible={showKycModal} transparent animationType="none" statusBarTranslucent>
        <Reanimated.View style={[s.kycOverlay, kycOverlayStyle]}>
          <View style={[StyleSheet.absoluteFill, { backgroundColor: 'rgba(0,0,0,0.40)' }]} />
          <Reanimated.View style={[s.kycCard, kycCardStyle]}>

            {/* Ícono principal */}
            <Reanimated.View style={[s.kycCircle, kycCircleStyle]}>
              <View style={s.kycRing} />
              <Ionicons name="shield-checkmark" size={44} color="#ffffff" />
              {/* Badge checkmark */}
              <View style={s.kycCheckBadge}>
                <Ionicons name="checkmark" size={11} color="#fff" />
              </View>
            </Reanimated.View>

            <Text style={s.kycTitle}>¡Identidad Verificada!</Text>
            <Text style={s.kycSubtitle}>
              {'Tu cuenta ha sido activada exitosamente.\nYa puedes realizar operaciones\nde cambio de divisas con Qoricash.'}
            </Text>

            {/* Badges */}
            <View style={s.kycBadgesRow}>
              <View style={s.kycBadge}>
                <Ionicons name="checkmark-circle" size={14} color="#0D1117" />
                <Text style={s.kycBadgeText}>Cuenta Activa</Text>
              </View>
              <View style={s.kycBadge}>
                <Ionicons name="checkmark-circle" size={14} color="#0D1117" />
                <Text style={s.kycBadgeText}>KYC Aprobado</Text>
              </View>
            </View>

            {/* Divider */}
            <View style={s.kycDivider} />

            <TouchableOpacity
              style={s.kycBtn}
              onPress={() => {
                kycOpacity.value = withTiming(0, { duration: 380, easing: REasing.out(REasing.quad) });
                kycScale.value   = withTiming(0.92, { duration: 380, easing: REasing.out(REasing.quad) }, (finished) => {
                  if (finished) runOnJS(setShowKycModal)(false);
                });
              }}
              activeOpacity={0.85}
            >
              <Ionicons name="arrow-forward" size={16} color="#fff" />
              <Text style={s.kycBtnText}>Empezar a operar</Text>
            </TouchableOpacity>
          </Reanimated.View>
        </Reanimated.View>
      </Modal>

      {/* ── Logo pie de página ── */}
      <View style={[s.footerLogo, { paddingBottom: insets.bottom + 16 }]}>
        <Image source={require('../../assets/qc.png')} style={s.footerLogoImg} resizeMode="contain" />
      </View>

      {/* ══ Dropdown menú hamburguesa ════════════════════════════════════════ */}
      <Modal visible={menuVisible} transparent animationType="fade" onRequestClose={() => setMenuVisible(false)} statusBarTranslucent>
        <TouchableOpacity style={s.menuBackdrop} activeOpacity={1} onPress={() => setMenuVisible(false)}>
          <TouchableOpacity activeOpacity={1} style={[s.menuDropdown, { top: insets.top + 86, left: 16, right: 16 }]}>

            {/* Triángulo conector con el ícono */}
            <View style={s.menuArrow} />

            {/* Mi cuenta */}
            <TouchableOpacity style={s.menuItem} activeOpacity={0.7} onPress={() => {
              setMenuVisible(false);
              navigation.dispatch(CommonActions.navigate({ name: 'ProfileTab' }));
            }}>
              <View style={s.menuItemIcon}><Ionicons name="person-outline" size={19} color="#0D1117" /></View>
              <View style={{ flex: 1 }}>
                <Text style={s.menuItemTitle}>Mi cuenta</Text>
                <Text style={s.menuItemSub}>Ver y editar tu perfil</Text>
              </View>
              <Ionicons name="chevron-forward" size={16} color="rgba(0,0,0,0.22)" />
            </TouchableOpacity>

            <View style={s.menuDivider} />

            {/* Mis operaciones */}
            <TouchableOpacity style={s.menuItem} activeOpacity={0.7} onPress={() => {
              setMenuVisible(false);
              navigation.dispatch(CommonActions.navigate({ name: 'HistoryTab', params: { initialTab: 'completed' } }));
            }}>
              <View style={s.menuItemIcon}><Ionicons name="receipt-outline" size={19} color="#0D1117" /></View>
              <View style={{ flex: 1 }}>
                <Text style={s.menuItemTitle}>Mis operaciones</Text>
                <Text style={s.menuItemSub}>Historial finalizadas</Text>
              </View>
              <Ionicons name="chevron-forward" size={16} color="rgba(0,0,0,0.22)" />
            </TouchableOpacity>

            <View style={s.menuDivider} />

            {/* Cambiar contraseña */}
            <TouchableOpacity style={s.menuItem} activeOpacity={0.7} onPress={() => {
              setMenuVisible(false);
              setTimeout(() => setChangePasswordVisible(true), 300);
            }}>
              <View style={s.menuItemIcon}><Ionicons name="lock-closed-outline" size={19} color="#0D1117" /></View>
              <View style={{ flex: 1 }}>
                <Text style={s.menuItemTitle}>Cambiar contraseña</Text>
                <Text style={s.menuItemSub}>Actualiza tu acceso</Text>
              </View>
              <Ionicons name="chevron-forward" size={16} color="rgba(0,0,0,0.22)" />
            </TouchableOpacity>

            <View style={s.menuDivider} />

            {/* Cerrar sesión */}
            <TouchableOpacity style={s.menuItem} activeOpacity={0.7} onPress={() => {
              setMenuVisible(false);
              setTimeout(() => {
                Alert.alert('Cerrar Sesión', '¿Estás seguro que deseas cerrar sesión?', [
                  { text: 'Cancelar', style: 'cancel' },
                  { text: 'Cerrar Sesión', style: 'destructive', onPress: () => setShowLogoutLoading(true) },
                ]);
              }, 200);
            }}>
              <View style={[s.menuItemIcon, s.menuItemIconDanger]}><Ionicons name="log-out-outline" size={19} color="#f87171" /></View>
              <View style={{ flex: 1 }}>
                <Text style={[s.menuItemTitle, { color: '#f87171' }]}>Cerrar sesión</Text>
                <Text style={s.menuItemSub}>Salir de tu cuenta</Text>
              </View>
            </TouchableOpacity>

          </TouchableOpacity>
        </TouchableOpacity>
      </Modal>

      {/* ══ Modal: Cambiar Contraseña ════════════════════════════════════════ */}
      <Modal visible={changePasswordVisible} transparent animationType="fade" onRequestClose={() => setChangePasswordVisible(false)} statusBarTranslucent>
        <BlurView intensity={50} tint="dark" style={StyleSheet.absoluteFill} />
        <TouchableOpacity style={s.cpBackdrop} activeOpacity={1} onPress={() => setChangePasswordVisible(false)} />
        <View style={[s.cpSheet, { paddingBottom: insets.bottom + 16 }]}>
          <View style={s.menuHandle} />
          <Text style={s.cpTitle}>Cambiar Contraseña</Text>

          {/* Contraseña actual */}
          <Text style={s.cpLabel}>Contraseña actual</Text>
          <View style={s.cpInputRow}>
            <TextInput style={s.cpInput} value={currentPassword} onChangeText={setCurrentPassword} secureTextEntry={!showCurrentPwd} placeholder="••••••••" placeholderTextColor="rgba(255,255,255,0.25)" />
            <TouchableOpacity onPress={() => setShowCurrentPwd(!showCurrentPwd)}>
              <Ionicons name={showCurrentPwd ? 'eye-off-outline' : 'eye-outline'} size={18} color="rgba(255,255,255,0.4)" />
            </TouchableOpacity>
          </View>

          {/* Nueva contraseña */}
          <Text style={s.cpLabel}>Nueva contraseña</Text>
          <View style={s.cpInputRow}>
            <TextInput style={s.cpInput} value={newPassword} onChangeText={setNewPassword} secureTextEntry={!showNewPwd} placeholder="Mínimo 8 caracteres" placeholderTextColor="rgba(255,255,255,0.25)" />
            <TouchableOpacity onPress={() => setShowNewPwd(!showNewPwd)}>
              <Ionicons name={showNewPwd ? 'eye-off-outline' : 'eye-outline'} size={18} color="rgba(255,255,255,0.4)" />
            </TouchableOpacity>
          </View>

          {/* Confirmar contraseña */}
          <Text style={s.cpLabel}>Confirmar contraseña</Text>
          <View style={s.cpInputRow}>
            <TextInput style={s.cpInput} value={confirmPassword} onChangeText={setConfirmPassword} secureTextEntry={!showConfirmPwd} placeholder="Repite la nueva contraseña" placeholderTextColor="rgba(255,255,255,0.25)" />
            <TouchableOpacity onPress={() => setShowConfirmPwd(!showConfirmPwd)}>
              <Ionicons name={showConfirmPwd ? 'eye-off-outline' : 'eye-outline'} size={18} color="rgba(255,255,255,0.4)" />
            </TouchableOpacity>
          </View>

          <View style={s.cpActions}>
            <TouchableOpacity style={s.cpBtnCancel} onPress={() => setChangePasswordVisible(false)} activeOpacity={0.7}>
              <Text style={s.cpBtnCancelText}>Cancelar</Text>
            </TouchableOpacity>
            <TouchableOpacity style={s.cpBtnSave} onPress={handleChangePassword} activeOpacity={0.85}>
              <Text style={s.cpBtnSaveText}>Guardar</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

    </View>
  );
};

// ─── Estilos ──────────────────────────────────────────────────────────────────
const s = StyleSheet.create({
  root: { flex: 1 },

  loadWrap: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#F5F7FA' },
  loadText: { color: '#6B7280', fontSize: 14 },

  // ── Fixed header ──
  fixedHeader: {
    paddingHorizontal: 20,
    paddingBottom: 12,
    backgroundColor: '#F5F7FA',
    zIndex: 20,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'flex-end',
    height: 44,
  },
  logo: { width: 105, height: 26 },
  footerLogo: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    alignItems: 'center',
  },
  footerLogoImg: { width: 105, height: 26 },
  refreshBtn: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: '#FFFFFF',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 6,
    elevation: 2,
  },

  scroll: { flex: 1 },
  content: { flexGrow: 1, paddingHorizontal: 20 },
  centerWrap: { flex: 1, justifyContent: 'center' },

  // ── Greeting ──
  greetingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 14,
    marginBottom: 22,
  },
  menuBtn: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: '#FFFFFF',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: 'rgba(0,0,0,0.08)',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 6,
    elevation: 2,
  },
  greetingSub: { fontSize: 13, color: '#9CA3AF', fontWeight: '400' },
  greetingName: { fontSize: 22, fontWeight: '800', color: '#0D1117', letterSpacing: -0.4 },

  // ── Menú hamburguesa (dropdown) ──
  menuBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.22)',
  },
  menuDropdown: {
    position: 'absolute',
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    paddingVertical: 6,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.16,
    shadowRadius: 28,
    elevation: 20,
    borderWidth: 1,
    borderColor: 'rgba(0,0,0,0.07)',
    overflow: 'visible',
  },
  // Triángulo conector — cuadrado rotado 45° alineado al botón hamburguesa
  menuArrow: {
    position: 'absolute',
    top: -7,
    left: 19,
    width: 14,
    height: 14,
    backgroundColor: '#FFFFFF',
    borderTopWidth: 1,
    borderLeftWidth: 1,
    borderColor: 'rgba(0,0,0,0.07)',
    transform: [{ rotate: '45deg' }],
    borderTopLeftRadius: 3,
    zIndex: 1,
  },
  menuItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 13,
    paddingVertical: 15,
    paddingHorizontal: 16,
  },
  menuItemIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#F3F4F6',
    alignItems: 'center',
    justifyContent: 'center',
  },
  menuItemIconDanger: {
    backgroundColor: 'rgba(248,113,113,0.10)',
  },
  menuItemTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: '#0D1117',
    marginBottom: 2,
  },
  menuItemSub: {
    fontSize: 12,
    color: '#9CA3AF',
    fontWeight: '400',
  },
  menuDivider: {
    height: StyleSheet.hairlineWidth,
    backgroundColor: 'rgba(0,0,0,0.07)',
    marginHorizontal: 16,
  },

  // ── Cambiar contraseña ──
  cpBackdrop: {
    ...StyleSheet.absoluteFillObject,
  },
  cpSheet: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: '#0d1f2d',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    paddingHorizontal: 22,
    paddingTop: 12,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.10)',
  },
  cpTitle: {
    fontSize: 17,
    fontWeight: '700',
    color: '#FFFFFF',
    marginBottom: 20,
    textAlign: 'center',
  },
  cpLabel: {
    fontSize: 12,
    color: 'rgba(255,255,255,0.5)',
    fontWeight: '500',
    marginBottom: 6,
    letterSpacing: 0.3,
  },
  cpInputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255,255,255,0.06)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.12)',
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    marginBottom: 14,
    gap: 10,
  },
  cpInput: {
    flex: 1,
    fontSize: 14,
    color: '#FFFFFF',
    padding: 0,
  },
  cpActions: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 6,
    marginBottom: 4,
  },
  cpBtnCancel: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 14,
    backgroundColor: 'rgba(255,255,255,0.06)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.12)',
    alignItems: 'center',
  },
  cpBtnCancelText: {
    fontSize: 14,
    fontWeight: '600',
    color: 'rgba(255,255,255,0.6)',
  },
  cpBtnSave: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 14,
    backgroundColor: '#FFFFFF',
    alignItems: 'center',
  },
  cpBtnSaveText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#0D1117',
  },

  // ── Hero card (negra) ──
  heroCard: {
    backgroundColor: '#0D1117',
    borderRadius: 28,
    padding: 28,
    marginBottom: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 14 },
    shadowOpacity: 0.28,
    shadowRadius: 32,
    elevation: 20,
  },
  heroCardTopRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 24,
  },
  heroCardTitle: {
    fontSize: 13,
    fontWeight: '600',
    color: 'rgba(255,255,255,0.55)',
    letterSpacing: 0.3,
  },
  liveRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  liveLabel: { fontSize: 11, color: '#4ade80', fontWeight: '600' },

  heroRatesRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 16,
  },
  heroRateItem: { flex: 1, alignItems: 'center', overflow: 'hidden' },
  heroRateLabel: {
    fontSize: 12,
    color: 'rgba(255,255,255,0.5)',
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 6,
  },
  heroRateValue: {
    fontSize: 50,
    fontWeight: '800',
    color: '#FFFFFF',
    letterSpacing: -1,
    marginBottom: 4,
    width: '100%',
    textAlign: 'center',
  },
  heroRateDir: {
    fontSize: 11,
    color: 'rgba(255,255,255,0.35)',
    fontWeight: '500',
  },
  heroRateDivider: {
    width: 1,
    height: 56,
    backgroundColor: 'rgba(255,255,255,0.1)',
    marginHorizontal: 16,
  },
  corporateBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    alignSelf: 'flex-start',
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderRadius: 20,
    paddingHorizontal: 10,
    paddingVertical: 4,
    marginBottom: 16,
  },
  corporateBadgeText: {
    fontSize: 10,
    color: 'rgba(255,255,255,0.6)',
    fontWeight: '600',
    letterSpacing: 0.3,
  },
  newOpBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 14,
    paddingVertical: 14,
    marginTop: 20,
    gap: 8,
  },
  newOpBtnText: {
    fontSize: 15,
    fontWeight: '700',
    color: '#0D1117',
    letterSpacing: 0.2,
  },

  // ── Banners ──
  bannerWarning: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1D4ED8',
    borderWidth: 0,
    borderRadius: 16,
    padding: 14,
    marginBottom: 14,
    gap: 12,
  },
  bannerInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#2563EB',
    borderWidth: 1,
    borderColor: '#1D4ED8',
    borderRadius: 16,
    padding: 14,
    marginBottom: 14,
    gap: 12,
  },
  bannerIcon: { width: 34, height: 34, borderRadius: 17, alignItems: 'center', justifyContent: 'center', flexShrink: 0 },
  bannerBody: { flex: 1 },
  bannerTitleWarn: { fontSize: 12.5, fontWeight: '700', color: '#FFFFFF', marginBottom: 2 },
  bannerTitleInfo: { fontSize: 12.5, fontWeight: '700', color: '#FFFFFF', marginBottom: 2 },
  bannerSubWarn: { fontSize: 11.5, color: 'rgba(255,255,255,0.75)', lineHeight: 16 },
  bannerSub: { fontSize: 11.5, color: 'rgba(255,255,255,0.75)', lineHeight: 16 },

  // ── Grid 2×2 ──
  gridWrap: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 14,
    marginBottom: 22,
  },
  gridTile: {
    width: (W - 40 - 14) / 2,
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    paddingVertical: 22,
    paddingHorizontal: 20,
    alignItems: 'flex-start',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 2,
  },
  gridIconWrap: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: '#F3F4F6',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 14,
  },
  gridLabel: { fontSize: 14, fontWeight: '700', color: '#0D1117' },

  // ── Active operations ──
  activeOpsWrap: { marginBottom: 16 },
  activeOpsHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 10 },
  activeOpsDot: { width: 7, height: 7, borderRadius: 3.5, backgroundColor: GREEN },
  activeOpsLabel: { fontSize: 13, fontWeight: '700', color: '#0D1117' },

  activeOpCard: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: 16,
    borderWidth: 1,
    padding: 14,
    gap: 12,
    marginBottom: 10,
    backgroundColor: '#FFFFFF',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 6,
    elevation: 2,
  },
  activeOpGlowBorder: {
    borderRadius: 16,
    borderWidth: 1.5,
  },
  activeOpIconWrap: { width: 36, height: 36, alignItems: 'center', justifyContent: 'center' },
  activeOpSpinArc: {
    position: 'absolute',
    width: 36,
    height: 36,
    borderRadius: 18,
    borderWidth: 2,
    borderColor: 'transparent',
  },
  activeOpIcon: {
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  activeOpContent: { flex: 1 },
  activeOpId: { fontSize: 13, fontWeight: '700', color: '#fff', marginBottom: 2 },
  activeOpDetail: { fontSize: 11.5, color: 'rgba(255,255,255,0.65)' },
  activeOpRight: { alignItems: 'flex-end', gap: 4 },
  activeOpPill: {
    borderRadius: 20,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderWidth: 1,
  },
  activeOpPillText: { fontSize: 10.5, fontWeight: '700' },

  // ── Live dot ──
  dotWrap: { width: 10, height: 10, alignItems: 'center', justifyContent: 'center' },
  dotPulse: { position: 'absolute', width: 10, height: 10, borderRadius: 5, borderWidth: 1.5, borderColor: '#4ade80' },
  dotCore: { width: 6, height: 6, borderRadius: 3, backgroundColor: '#4ade80' },

  // ── Modales ──
  blockModalBackdrop: { flex: 1, justifyContent: 'center', alignItems: 'center', paddingHorizontal: 28 },
  blockModalCard: {
    width: '100%',
    backgroundColor: '#FFFFFF',
    borderRadius: 24,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.08)',
    padding: 28,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 20 },
    shadowOpacity: 0.5,
    shadowRadius: 40,
    elevation: 30,
  },
  minModalCard: {},
  blockModalIconWrap: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: 'rgba(29,78,216,0.1)',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 18,
    borderWidth: 1,
    borderColor: 'rgba(29,78,216,0.2)',
  },
  minModalIconWrap: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: 'rgba(245,158,11,0.12)',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 18,
    borderWidth: 1,
    borderColor: 'rgba(245,158,11,0.22)',
  },
  blockModalTitle: { fontSize: 18, fontWeight: '800', color: '#0D1117', textAlign: 'center', marginBottom: 10 },
  blockModalBody: { fontSize: 14, color: '#6B7280', textAlign: 'center', lineHeight: 22, marginBottom: 24 },
  blockModalBtnPrimary: {
    width: '100%',
    backgroundColor: '#0D1117',
    borderRadius: 14,
    paddingVertical: 15,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    marginBottom: 10,
  },
  blockModalBtnPrimaryText: { fontSize: 15, fontWeight: '700', color: '#fff' },
  blockModalBtnSecondary: {
    width: '100%',
    paddingVertical: 13,
    alignItems: 'center',
    borderRadius: 14,
    backgroundColor: 'transparent',
    borderWidth: 1.5,
    borderColor: '#0D1117',
  },
  blockModalBtnSecondaryText: { fontSize: 14, fontWeight: '600', color: '#0D1117' },
  minModalHighlight: { color: '#f59e0b', fontWeight: '700' },
  minModalBtnClose: {
    width: '100%',
    paddingVertical: 13,
    alignItems: 'center',
    borderRadius: 14,
    backgroundColor: 'rgba(255,255,255,0.06)',
  },

  // Referral modal
  referralModalOverlay: { flex: 1, justifyContent: 'flex-end' },
  referralModalSheet: {
    backgroundColor: '#1A1A2E',
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    borderWidth: 1,
    borderColor: 'rgba(34,197,94,0.18)',
    padding: 24,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: -12 },
    shadowOpacity: 0.4,
    shadowRadius: 28,
    elevation: 20,
  },
  referralModalHeader: { flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 16 },
  referralModalIcon: {
    width: 38, height: 38, borderRadius: 19,
    backgroundColor: 'rgba(34,197,94,0.12)',
    borderWidth: 1, borderColor: 'rgba(34,197,94,0.25)',
    alignItems: 'center', justifyContent: 'center',
  },
  referralModalTitle: { flex: 1, fontSize: 17, fontWeight: '700', color: '#fff' },
  referralModalClose: { padding: 4 },
  referralModalSub: { fontSize: 13, color: 'rgba(255,255,255,0.5)', lineHeight: 20, marginBottom: 20 },
  referralModalInput: {
    backgroundColor: 'rgba(255,255,255,0.06)',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.14)',
    borderRadius: 14,
    paddingHorizontal: 16, paddingVertical: 14,
    fontSize: 20, fontWeight: '700',
    color: '#fff', textAlign: 'center', letterSpacing: 4, marginBottom: 16,
  },
  referralModalBtn: {
    backgroundColor: GREEN,
    borderRadius: 14, paddingVertical: 15,
    alignItems: 'center',
    shadowColor: GREEN,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.4, shadowRadius: 12, elevation: 6,
  },
  referralModalBtnDisabled: { backgroundColor: 'rgba(34,197,94,0.2)', shadowOpacity: 0, elevation: 0 },
  referralModalBtnText: { fontSize: 15, fontWeight: '700', color: '#fff', letterSpacing: 0.3 },

  // KYC modal
  kycOverlay: { flex: 1, justifyContent: 'center', alignItems: 'center', paddingHorizontal: 28 },
  kycCard: {
    width: '100%',
    backgroundColor: '#FFFFFF',
    borderRadius: 28, borderWidth: 1, borderColor: 'rgba(0,0,0,0.07)',
    paddingHorizontal: 28, paddingTop: 44, paddingBottom: 32,
    alignItems: 'center',
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 12 }, shadowOpacity: 0.12, shadowRadius: 32, elevation: 20,
  },
  kycCircle: {
    width: 100, height: 100, borderRadius: 50,
    backgroundColor: '#0D1117',
    alignItems: 'center', justifyContent: 'center',
    marginBottom: 28,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 8 }, shadowOpacity: 0.22, shadowRadius: 18, elevation: 16,
  },
  kycRing: { position: 'absolute', width: 122, height: 122, borderRadius: 61, borderWidth: 1.5, borderColor: 'rgba(0,0,0,0.08)' },
  kycCheckBadge: {
    position: 'absolute', bottom: -2, right: -2,
    width: 22, height: 22, borderRadius: 11,
    backgroundColor: '#2563EB',
    alignItems: 'center', justifyContent: 'center',
    borderWidth: 2, borderColor: '#FFFFFF',
  },
  kycTitle: { fontSize: 22, fontWeight: '800', color: '#0D1117', textAlign: 'center', letterSpacing: 0.1, marginBottom: 10 },
  kycSubtitle: { fontSize: 14, color: '#6B7280', textAlign: 'center', lineHeight: 22, marginBottom: 22 },
  kycBadgesRow: { flexDirection: 'row', gap: 8, marginBottom: 22 },
  kycBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    backgroundColor: '#F3F4F6', borderRadius: 20,
    paddingHorizontal: 12, paddingVertical: 6,
    borderWidth: 1, borderColor: 'rgba(0,0,0,0.07)',
  },
  kycBadgeText: { fontSize: 12, color: '#0D1117', fontWeight: '600' },
  kycDivider: { width: '100%', height: 1, backgroundColor: 'rgba(0,0,0,0.06)', marginBottom: 22 },
  kycBtn: {
    width: '100%', backgroundColor: '#0D1117',
    borderRadius: 16, paddingVertical: 17,
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.18, shadowRadius: 10, elevation: 8,
  },
  kycBtnText: { fontSize: 16, fontWeight: '700', color: '#ffffff', letterSpacing: 0.2 },
});
