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
import { LinearGradient } from 'expo-linear-gradient';
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
} from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { BlurView } from 'expo-blur';
import * as Haptics from 'expo-haptics';
import { CommonActions } from '@react-navigation/native';
import axios from 'axios';
import socketService from '../services/socketService';
import { useAuth } from '../contexts/AuthContext';
import { Calculator } from '../components/Calculator';
import { API_CONFIG } from '../constants/config';
import { Operation } from '../types';

const { width: W } = Dimensions.get('window');
const GLASS_BG     = 'rgba(255,255,255,0.09)';
const GLASS_BORDER = 'rgba(255,255,255,0.17)';
const GREEN        = '#22c55e';

const STICKY_THRESHOLD = 90;   // px scroll antes de que aparece el sticky header
const TAB_BAR_H        = 72;   // altura del CustomTabBar (incluye safe area)

interface HomeScreenProps { navigation: any }

const capitalize = (s: string) =>
  s ? s.charAt(0).toUpperCase() + s.slice(1).toLowerCase() : s;

// ─── ActiveOpCard — reloj animado + arco giratorio ────────────────────────────
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
      {/* Animated glow border overlay */}
      <Reanimated.View style={[StyleSheet.absoluteFill, s.activeOpGlowBorder, { borderColor: accentColor }, glowStyle]} pointerEvents="none" />

      {/* Icon with spinning arc */}
      <View style={s.activeOpIconWrap}>
        <Reanimated.View style={[s.activeOpSpinArc, { borderTopColor: accentColor }, spinStyle]} />
        <Reanimated.View style={[s.activeOpIcon, { backgroundColor: `${accentColor}1A` }, iconStyle]}>
          <Ionicons name="time-outline" size={16} color={accentColor} />
        </Reanimated.View>
      </View>

      {/* Content */}
      <View style={s.activeOpContent}>
        <Text style={s.activeOpId}>{op.operation_id}</Text>
        <Text style={s.activeOpDetail}>
          {op.operation_type} · ${op.amount_usd.toFixed(2)} · S/ {op.amount_pen.toFixed(2)}
        </Text>
      </View>

      {/* Status pill + chevron */}
      <View style={s.activeOpRight}>
        <View style={[s.activeOpPill, { backgroundColor: `${accentColor}18`, borderColor: `${accentColor}33` }]}>
          <Text style={[s.activeOpPillText, { color: accentColor }]}>
            {isEnProceso ? 'En proceso' : 'Pendiente'}
          </Text>
        </View>
        <Ionicons name="chevron-forward" size={13} color="rgba(255,255,255,0.25)" style={{ marginTop: 2 }} />
      </View>
    </TouchableOpacity>
  );
};

// ─── LiveDot — respiración + onda expansiva ───────────────────────────────────
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
  const insets = useSafeAreaInsets();
  const { client, refreshClient } = useAuth();
  const [refreshing, setRefreshing] = useState(false);
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

  // Teclado: auto-scroll para revelar calculadora cuando el teclado aparece
  const [keyboardHeight, setKeyboardHeight] = useState(0);
  useEffect(() => {
    const showEv = Platform.OS === 'ios' ? 'keyboardWillShow' : 'keyboardDidShow';
    const hideEv = Platform.OS === 'ios' ? 'keyboardWillHide' : 'keyboardDidHide';
    const showSub = Keyboard.addListener(showEv, e => {
      setKeyboardHeight(e.endCoordinates.height);
      scrollViewRef.current?.scrollTo({ y: ratesTopY.current, animated: true });
    });
    const hideSub = Keyboard.addListener(hideEv, () => {
      setKeyboardHeight(0);
      scrollViewRef.current?.scrollTo({ y: 0, animated: true });
    });
    return () => { showSub.remove(); hideSub.remove(); };
  }, []);

  // Socket: actualizar widget en tiempo real cuando cambia el estado de una operación
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

    return () => {
      socketService.off('operacion_completada',     removeOp);
      socketService.off('operacion_cancelada_admin', removeOp);
      socketService.off('operacion_en_proceso',     updateToInProcess);
    };
  }, [client?.dni]);

  const [showBlockModal,   setShowBlockModal]   = useState(false);
  const blockScale   = useSharedValue(0.86);
  const blockOpacity = useSharedValue(0);

  const [showMinAmountModal, setShowMinAmountModal] = useState(false);
  const minScale   = useSharedValue(0.86);
  const minOpacity = useSharedValue(0);

  useEffect(() => {
    if (showBlockModal) {
      blockScale.value   = 0.86;
      blockOpacity.value = 0;
      blockScale.value   = withSpring(1, { damping: 16, stiffness: 260 });
      blockOpacity.value = withTiming(1, { duration: 180 });
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

  // ── Referral code ──────────────────────────────────────────────────────────
  const REFERRAL_IMPROVEMENT = 0.002; // 20 pips (0.0001 cada uno)
  const [referralModalVisible, setReferralModalVisible] = useState(false);
  const [referralInput,        setReferralInput]        = useState('');
  const [referralValidating,   setReferralValidating]   = useState(false);
  const [referralApplied,      setReferralApplied]      = useState<string | null>(null); // código validado

  // ── Volume-based pip improvement (mirrors wa_bot.py) ──────────────────────
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
  const pipLabel = effectivePips > 0 ? `+${Math.round(effectivePips * 10000)} pips` : null;

  const improvedRates = referralApplied && calcRates
    ? { compra: calcRates.compra + REFERRAL_IMPROVEMENT, venta: calcRates.venta - REFERRAL_IMPROVEMENT }
    : null;

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

  // Scroll Y para sticky header
  const scrollViewRef = useRef<ScrollView>(null);
  const ratesTopY     = useRef(0);


  const onRefresh = async () => {
    setRefreshing(true);
    await Promise.all([refreshClient(), fetchActiveOps()]);
    setRefreshing(false);
  };

  const handleInitiateOperation = (
    operationType: 'Compra' | 'Venta',
    amountUSD: string,
    exchangeRate: number,
  ) => {
    // Validar monto mínimo en USD
    const inputVal  = parseFloat(amountUSD) || 0;
    const usdAmount = operationType === 'Compra' ? inputVal : inputVal / exchangeRate;
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
      Alert.alert(
        'Validación de Identidad Requerida',
        'Necesitamos validar tu DNI antes de iniciar una operación.\n\nPor favor, sube las fotos de tu DNI.',
        [{ text: 'Entendido' }],
      );
      return;
    }
    navigation.navigate('NewOperation', { operationType, amountUSD, exchangeRate });
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

  const minModalStyle = useAnimatedStyle(() => ({
    opacity:   minOpacity.value,
    transform: [{ scale: minScale.value }],
  }));

  const firstName = (() => {
    if (client.nombres)   return capitalize(client.nombres.split(' ')[0]);
    if (client.full_name) return capitalize(client.full_name.split(' ')[0]);
    return '';
  })();

  return (
    <View style={s.root}>

      {/* ── Fondo ── */}
      <ImageBackground
        source={require('../../assets/cd.png')}
        style={StyleSheet.absoluteFill}
        resizeMode="cover"
        pointerEvents="none"
      />
      <View style={[StyleSheet.absoluteFill, s.overlay]} pointerEvents="none" />

      {/* ── Encabezado fijo: saludo + logo ── */}
      <View style={[s.fixedGreeting, { paddingTop: insets.top + 16 }]}>
        <View style={s.headerRow}>
          <View>
            <Text style={s.greetingLabel}>Bienvenido,</Text>
            <Text style={s.greetingName}>{firstName}</Text>
          </View>
          <Image source={require('../../assets/logo.png')} style={s.logo} resizeMode="contain" />
        </View>
        <View style={s.fixedGreetingHairline} />
      </View>

      {/* ── Scroll ── */}
      <ScrollView
        ref={scrollViewRef}
        style={s.scroll}
        contentContainerStyle={[
          s.content,
          { paddingTop: 8, paddingBottom: insets.bottom + TAB_BAR_H + 16 + keyboardHeight },
        ]}
        scrollEnabled={true}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor="rgba(255,255,255,0.5)"
          />
        }
      >

        {/* ══ User info strip ══ */}
        <MotiView
          from={{ opacity: 0, translateY: 16, scale: 0.97 }}
          animate={{ opacity: 1, translateY: 0, scale: 1 }}
          transition={{ type: 'spring', delay: 80, damping: 20, stiffness: 180 }}
          style={s.userStrip}
        >
          <View style={s.stripItem}>
            <Text style={s.stripLabel}>Documento</Text>
            <Text style={s.stripValue}>{client.dni}</Text>
          </View>
          <View style={s.stripDivider} />
          <View style={s.stripItem}>
            <Text style={s.stripLabel}>Estado</Text>
            <View style={s.statusRow}>
              <Text style={s.statusText}>{capitalize(client.status)}</Text>
            </View>
          </View>
          <View style={s.stripDivider} />
          <View style={s.stripItem}>
            <Text style={s.stripLabel}>Tipo</Text>
            <Text style={s.stripValue}>
              {(client as any).client_type === 'juridico' ? 'Empresa' : 'Natural'}
            </Text>
          </View>
        </MotiView>

        {/* ══ Banners de verificación ══ */}
        {!client.has_complete_documents && (
          <MotiView
            from={{ opacity: 0, translateY: 12 }}
            animate={{ opacity: 1, translateY: 0 }}
            transition={{ type: 'spring', delay: 140, damping: 20, stiffness: 160 }}
          >
            {(!client.dni_front_url || !client.dni_back_url) && (
              <TouchableOpacity
                style={s.warningBanner}
                onPress={() => {
                  Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
                  navigation.navigate('VerifyIdentity');
                }}
                activeOpacity={0.82}
              >
                <View style={[s.bannerIcon, { backgroundColor: 'rgba(251,191,36,0.12)' }]}>
                  <Ionicons name="shield-outline" size={18} color="#fbbf24" />
                </View>
                <View style={s.bannerBody}>
                  <Text style={s.warningTitle}>Validación pendiente</Text>
                  <Text style={s.bannerSub}>Sube tu DNI para empezar a operar.</Text>
                </View>
                <View style={s.bannerChevron}>
                  <Ionicons name="chevron-forward" size={16} color="rgba(251,191,36,0.6)" />
                </View>
              </TouchableOpacity>
            )}

            {client.dni_front_url && client.dni_back_url && (
              <View style={s.infoBanner}>
                <View style={[s.bannerIcon, { backgroundColor: 'rgba(96,165,250,0.12)' }]}>
                  <Ionicons name="time-outline" size={18} color="#60a5fa" />
                </View>
                <View style={s.bannerBody}>
                  <Text style={s.infoTitle}>Validación en proceso</Text>
                  <Text style={s.bannerSub}>⏱ Aprox. 10 min — te notificaremos.</Text>
                </View>
              </View>
            )}
          </MotiView>
        )}

        {/* ══ Live indicator ══ */}
        <MotiView
          from={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ type: 'timing', delay: 200, duration: 420 }}
          style={s.liveRow}
          onLayout={e => { ratesTopY.current = e.nativeEvent.layout.y; }}
        >
          <LiveDot />
          <Text style={s.liveLabel}>Tipo de cambio en vivo</Text>
        </MotiView>

        {/* ══ Tarjetas de tipo de cambio (independientes) ══ */}
        <MotiView
          from={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ type: 'spring', delay: 210, damping: 22, stiffness: 160 }}
          style={s.ratesRow}
        >
          <TouchableOpacity
            onPress={() => setCalcOperationType('Compra')}
            activeOpacity={0.82}
            style={[s.rateTab, calcOperationType === 'Compra' && s.rateTabActiveCompra]}
          >
            <LinearGradient
              colors={calcOperationType === 'Compra'
                ? ['rgba(34,197,94,0.14)', 'rgba(10,40,22,0.55)']
                : ['rgba(255,255,255,0.07)', 'rgba(8,16,30,0.70)']}
              start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
              style={StyleSheet.absoluteFill}
            />
            <Text style={s.rateTabLabel}>Qoricash compra</Text>
            {displayRates ? (
              <View style={s.rateImprovedWrap}>
                <Text style={s.rateTabValueStrike}>S/ {calcRates?.compra.toFixed(4)}</Text>
                <Text style={[s.rateTabValue, s.rateImprovedValue]}>S/ {displayRates.compra.toFixed(4)}</Text>
              </View>
            ) : (
              <Text style={[s.rateTabValue, calcOperationType !== 'Compra' && s.rateTabValueDim]}>
                S/ {calcRates?.compra.toFixed(4) ?? '—'}
              </Text>
            )}
            <View style={s.rateTabPill}>
              {pipLabel && <Text style={s.ratePipBadge}>{pipLabel}</Text>}
              <Text style={s.rateTabPillText}>USD → PEN</Text>
            </View>
          </TouchableOpacity>

          <TouchableOpacity
            onPress={() => setCalcOperationType('Venta')}
            activeOpacity={0.82}
            style={[s.rateTab, calcOperationType === 'Venta' && s.rateTabActiveVenta]}
          >
            <LinearGradient
              colors={calcOperationType === 'Venta'
                ? ['rgba(59,130,246,0.14)', 'rgba(8,20,50,0.55)']
                : ['rgba(255,255,255,0.07)', 'rgba(8,16,30,0.70)']}
              start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
              style={StyleSheet.absoluteFill}
            />
            <Text style={s.rateTabLabel}>Qoricash vende</Text>
            {displayRates ? (
              <View style={s.rateImprovedWrap}>
                <Text style={s.rateTabValueStrike}>S/ {calcRates?.venta.toFixed(4)}</Text>
                <Text style={[s.rateTabValue, s.rateImprovedValue]}>S/ {displayRates.venta.toFixed(4)}</Text>
              </View>
            ) : (
              <Text style={[s.rateTabValue, calcOperationType !== 'Venta' && s.rateTabValueDim]}>
                S/ {calcRates?.venta.toFixed(4) ?? '—'}
              </Text>
            )}
            <View style={s.rateTabPill}>
              {pipLabel && <Text style={s.ratePipBadge}>{pipLabel}</Text>}
              <Text style={s.rateTabPillText}>PEN → USD</Text>
            </View>
          </TouchableOpacity>
        </MotiView>

        {/* ══ Calculadora ══ */}
        <MotiView
          from={{ opacity: 0, translateY: 20, scale: 0.96 }}
          animate={{ opacity: 1, translateY: 0, scale: 1 }}
          transition={{ type: 'spring', delay: 240, damping: 22, stiffness: 160 }}
          style={s.calcCard}
        >
          <Calculator
            onOperationReady={handleInitiateOperation}
            onAmountChange={(ready, operationType, amountUSD, rate) =>
              setPendingOp({ ready, operationType, amountUSD, rate })
            }
            onRatesChange={setCalcRates}
            onOperationTypeChange={setCalcOperationType}
            externalOperationType={calcOperationType}
            overrideRates={displayRates}
            hideTabs
          />

          {/* Badge de mejora por volumen */}
          {volumePips > 0 && (
            <View style={s.volumeBadge}>
              <Ionicons name="flash" size={11} color="#fbbf24" />
              <Text style={s.volumeBadgeText}>
                TC preferencial activo · +{Math.round(volumePips * 10000)} pips por monto especial
              </Text>
            </View>
          )}
        </MotiView>

        {/* ══ Botón iniciar operación (fuera de la card) ══ */}
        <MotiView
          from={{ opacity: 0, translateY: 10 }}
          animate={{ opacity: 1, translateY: 0 }}
          transition={{ type: 'spring', delay: 300, damping: 22, stiffness: 160 }}
          style={s.initiateWrap}
        >
          <TouchableOpacity
            style={[s.initiateBtn, !pendingOp.ready && s.initiateBtnDisabled]}
            onPress={() => {
              if (pendingOp.ready) {
                Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
                handleInitiateOperation(pendingOp.operationType, pendingOp.amountUSD, pendingOp.rate);
              }
            }}
            disabled={!pendingOp.ready}
            activeOpacity={0.82}
          >
            <Text style={[s.initiateBtnText, !pendingOp.ready && s.initiateBtnTextDisabled]}>
              INICIAR OPERACIÓN
            </Text>
            <Ionicons name="arrow-forward" size={16} color={pendingOp.ready ? '#fff' : 'rgba(255,255,255,0.3)'} />
          </TouchableOpacity>
        </MotiView>

        {/* ══ Código de referido ══ */}
        <MotiView
          from={{ opacity: 0, translateY: 8 }}
          animate={{ opacity: 1, translateY: 0 }}
          transition={{ type: 'spring', delay: 320, damping: 22, stiffness: 160 }}
        >
          <TouchableOpacity
            style={[s.referralRow, referralApplied && s.referralRowActive]}
            onPress={() => referralApplied ? null : setReferralModalVisible(true)}
            activeOpacity={referralApplied ? 1 : 0.78}
          >
            <Ionicons name="pricetag-outline" size={15} color={referralApplied ? GREEN : 'rgba(255,255,255,0.4)'} />
            <Text style={[s.referralRowText, referralApplied && { color: '#fff' }]}>
              {referralApplied ? `Cupón ${referralApplied} aplicado` : 'Tengo un cupón'}
            </Text>
            {referralApplied ? (
              <View style={s.referralBadge}>
                <Text style={s.referralBadgeText}>+20 pips</Text>
              </View>
            ) : null}
            {referralApplied && (
              <TouchableOpacity onPress={() => { setReferralApplied(null); setReferralInput(''); }} style={{ padding: 4 }}>
                <Ionicons name="close-circle" size={16} color="rgba(255,255,255,0.35)" />
              </TouchableOpacity>
            )}
          </TouchableOpacity>
        </MotiView>

        {/* ══ Operaciones activas ══ */}
        {activeOps.length > 0 && (
          <MotiView
            from={{ opacity: 0, translateY: 10 }}
            animate={{ opacity: 1, translateY: 0 }}
            transition={{ type: 'spring', delay: 360, damping: 22, stiffness: 160 }}
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
              const accentColor = isEnProceso ? GREEN : '#f59e0b';
              const bgColor     = isEnProceso ? 'rgba(34,197,94,0.07)' : 'rgba(245,158,11,0.07)';
              const borderColor = isEnProceso ? 'rgba(34,197,94,0.22)' : 'rgba(245,158,11,0.22)';

              return (
                <ActiveOpCard
                  key={op.id}
                  op={op}
                  isEnProceso={isEnProceso}
                  accentColor={accentColor}
                  bgColor={bgColor}
                  borderColor={borderColor}
                  onPress={() => {
                    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
                    const screen = isEnProceso ? 'Receive' : 'Transfer';
                    navigation.dispatch(CommonActions.navigate({ name: screen, params: { operation: op } }));
                  }}
                />
              );
            })}
          </MotiView>
        )}

      </ScrollView>

      {/* ── Modal: operación activa bloqueante ── */}
      <Modal
        visible={showBlockModal}
        transparent
        animationType="fade"
        statusBarTranslucent
        onRequestClose={() => setShowBlockModal(false)}
      >
        <BlurView intensity={55} tint="dark" style={s.blockModalBackdrop}>
          <Reanimated.View style={[s.blockModalCard, blockModalStyle]}>

            {/* Icono */}
            <View style={s.blockModalIconWrap}>
              <Ionicons name="time-outline" size={32} color="#f59e0b" />
            </View>

            {/* Texto */}
            <Text style={s.blockModalTitle}>Tienes una operación activa</Text>
            <Text style={s.blockModalBody}>
              Solo puedes tener una operación en curso a la vez. Completa o cancela tu operación actual antes de iniciar una nueva.
            </Text>

            {/* Botón primario: ir a la op activa */}
            <TouchableOpacity
              style={s.blockModalBtnPrimary}
              activeOpacity={0.82}
              onPress={() => {
                setShowBlockModal(false);
                const op = activeOps[0];
                const isEnProceso = op.status === 'en_proceso';
                const screen = isEnProceso ? 'Receive' : 'Transfer';
                navigation.dispatch(CommonActions.navigate({ name: screen, params: { operation: op } }));
              }}
            >
              <Ionicons name="arrow-forward-circle-outline" size={17} color="#fff" />
              <Text style={s.blockModalBtnPrimaryText}>Ver operación en curso</Text>
            </TouchableOpacity>

            {/* Botón secundario: cerrar */}
            <TouchableOpacity
              style={s.blockModalBtnSecondary}
              activeOpacity={0.7}
              onPress={() => setShowBlockModal(false)}
            >
              <Text style={s.blockModalBtnSecondaryText}>Entendido</Text>
            </TouchableOpacity>

          </Reanimated.View>
        </BlurView>
      </Modal>

      {/* ── Modal: monto mínimo ── */}
      <Modal
        visible={showMinAmountModal}
        transparent
        animationType="fade"
        statusBarTranslucent
        onRequestClose={() => setShowMinAmountModal(false)}
      >
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

            <TouchableOpacity
              style={s.minModalBtnClose}
              activeOpacity={0.7}
              onPress={() => setShowMinAmountModal(false)}
            >
              <Text style={s.blockModalBtnSecondaryText}>Entendido</Text>
            </TouchableOpacity>

          </Reanimated.View>
        </BlurView>
      </Modal>

      {/* ══ Modal: Código de referido ══════════════════════════════════════ */}
      <Modal
        visible={referralModalVisible}
        transparent
        animationType="fade"
        onRequestClose={closeReferralModal}
      >
        <KeyboardAvoidingView
          style={s.referralModalOverlay}
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        >
          <BlurView intensity={50} tint="dark" style={StyleSheet.absoluteFill} />
          <TouchableOpacity style={StyleSheet.absoluteFill} activeOpacity={1} onPress={closeReferralModal} />
          <View style={s.referralModalSheet}>
            {/* Header */}
            <View style={s.referralModalHeader}>
              <View style={s.referralModalIcon}>
                <Ionicons name="gift-outline" size={20} color={GREEN} />
              </View>
              <Text style={s.referralModalTitle}>Ingresa tu cupón aquí</Text>
              <TouchableOpacity onPress={closeReferralModal} style={s.referralModalClose}>
                <Ionicons name="close" size={20} color="rgba(255,255,255,0.5)" />
              </TouchableOpacity>
            </View>

            <Text style={s.referralModalSub}>
              Ingresa tu cupón, código de referido o código de campaña para desbloquear mejoras exclusivas en tu tipo de cambio.
            </Text>

            {/* Input */}
            <TextInput
              style={s.referralModalInput}
              value={referralInput}
              onChangeText={t => setReferralInput(t.toUpperCase())}
              placeholder="Ej: ABC123"
              placeholderTextColor="rgba(255,255,255,0.25)"
              autoCapitalize="characters"
              maxLength={8}
            />

            {/* Botón validar */}
            <TouchableOpacity
              style={[s.referralModalBtn, (!referralInput.trim() || referralValidating) && s.referralModalBtnDisabled]}
              onPress={handleValidateReferral}
              disabled={!referralInput.trim() || referralValidating}
              activeOpacity={0.85}
            >
              {referralValidating
                ? <Text style={s.referralModalBtnText}>Validando...</Text>
                : <Text style={s.referralModalBtnText}>Aplicar código</Text>
              }
            </TouchableOpacity>
          </View>
        </KeyboardAvoidingView>
      </Modal>

    </View>
  );
};

// ─── Estilos ──────────────────────────────────────────────────────────────────
const s = StyleSheet.create({
  root: {
    flex: 1,
  },
  overlay: {
    backgroundColor: 'transparent',
  },
  loadWrap: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#0a1a2e',
  },
  loadText: {
    color: 'rgba(255,255,255,0.6)',
    fontSize: 14,
  },
  scroll: { flex: 1 },
  content: {
    flexGrow: 1,
    paddingHorizontal: 20,
  },

  // ── Fixed greeting header ──
  fixedGreeting: {
    paddingHorizontal: 20,
    paddingBottom: 14,
    zIndex: 20,
  },
  fixedGreetingHairline: {
    marginTop: 14,
    height: StyleSheet.hairlineWidth,
    backgroundColor: 'rgba(255,255,255,0.10)',
  },

  // ── Header row ──
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  logo: {
    width: 110,
    height: 26,
  },
  greetingLabel: {
    fontSize: 13,
    color: 'rgba(255,255,255,0.5)',
    fontWeight: '400',
    marginBottom: 2,
    letterSpacing: 0.2,
  },
  greetingName: {
    fontSize: 32,
    fontWeight: '800',
    color: '#FFFFFF',
    letterSpacing: -0.6,
  },

  // ── User strip ──
  userStrip: {
    flexDirection: 'row',
    backgroundColor: GLASS_BG,
    borderWidth: 1,
    borderColor: GLASS_BORDER,
    borderRadius: 20,
    paddingVertical: 16,
    paddingHorizontal: 16,
    marginBottom: 18,
  },
  stripItem: {
    flex: 1,
    alignItems: 'center',
  },
  stripLabel: {
    fontSize: 9.5,
    color: 'rgba(255,255,255,0.38)',
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.7,
    marginBottom: 6,
  },
  stripValue: {
    fontSize: 13,
    color: 'rgba(255,255,255,0.82)',
    fontWeight: '600',
  },
  stripDivider: {
    width: StyleSheet.hairlineWidth * 2,
    backgroundColor: GLASS_BORDER,
    marginVertical: 2,
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
  },
  statusText: {
    fontSize: 13,
    color: GREEN,
    fontWeight: '700',
  },

  // ── Live dot ──
  dotWrap: {
    width: 11,
    height: 11,
    alignItems: 'center',
    justifyContent: 'center',
  },
  dotPulse: {
    position: 'absolute',
    width: 11,
    height: 11,
    borderRadius: 5.5,
    borderWidth: 1.5,
    borderColor: '#4ade80',
  },
  dotCore: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: '#4ade80',
  },

  // ── Banners ──
  warningBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(251,191,36,0.08)',
    borderWidth: 1,
    borderColor: 'rgba(251,191,36,0.22)',
    borderRadius: 16,
    padding: 14,
    marginBottom: 14,
    gap: 12,
  },
  infoBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(96,165,250,0.08)',
    borderWidth: 1,
    borderColor: 'rgba(96,165,250,0.22)',
    borderRadius: 16,
    padding: 14,
    marginBottom: 14,
    gap: 12,
  },
  bannerIcon: {
    width: 34,
    height: 34,
    borderRadius: 17,
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  bannerBody: { flex: 1 },
  bannerChevron: {
    width: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  warningTitle: {
    fontSize: 12.5,
    fontWeight: '700',
    color: '#fbbf24',
    marginBottom: 1,
  },
  infoTitle: {
    fontSize: 12.5,
    fontWeight: '700',
    color: '#60a5fa',
    marginBottom: 1,
  },
  bannerSub: {
    fontSize: 11,
    color: 'rgba(255,255,255,0.45)',
    lineHeight: 16,
  },

  // ── Live row ──
  liveRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 9,
    marginBottom: 12,
  },
  liveLabel: {
    fontSize: 11.5,
    color: 'rgba(255,255,255,0.68)',
    letterSpacing: 0.3,
    fontWeight: '500',
  },

  // ── Rate cards (independientes) ──
  ratesRow: {
    flexDirection: 'row',
    gap: 10,
    marginBottom: 14,
  },
  rateTab: {
    flex: 1,
    paddingVertical: 20,
    paddingHorizontal: 18,
    gap: 6,
    backgroundColor: 'transparent',
    borderWidth: 1,
    borderColor: GLASS_BORDER,
    borderRadius: 22,
    overflow: 'hidden',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.28,
    shadowRadius: 14,
    elevation: 8,
  },
  rateTabActive: {
    backgroundColor: 'rgba(34,197,94,0.13)',
    borderColor: GREEN,
  },
  rateTabActiveCompra: {
    borderColor: 'rgba(34,197,94,0.60)',
  },
  rateTabActiveVenta: {
    borderColor: 'rgba(59,130,246,0.60)',
  },
  rateTabLabel: {
    fontSize: 11,
    color: 'rgba(255,255,255,0.52)',
    letterSpacing: 1.4,
    textTransform: 'uppercase',
    fontWeight: '400',
  },
  rateTabValue: {
    fontSize: 26,
    fontWeight: '700',
    color: '#FFFFFF',
    letterSpacing: -0.5,
    lineHeight: 32,
  },
  rateTabValueDim: {
    opacity: 0.42,
  },
  rateTabPill: {
    alignSelf: 'flex-start',
    backgroundColor: 'rgba(255,255,255,0.10)',
    borderRadius: 20,
    paddingHorizontal: 8,
    paddingVertical: 3,
    marginTop: 2,
  },
  rateTabPillText: {
    fontSize: 9.5,
    color: 'rgba(255,255,255,0.55)',
    letterSpacing: 0.3,
  },
  // ── Calculator card ──
  calcCard: {
    paddingTop: 20,
  },

  // ── Initiate button (outside card) ──
  initiateWrap: {
    marginTop: 6,
  },
  initiateBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: GREEN,
    borderRadius: 18,
    paddingVertical: 17,
    gap: 10,
    shadowColor: GREEN,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.35,
    shadowRadius: 14,
    elevation: 8,
  },
  initiateBtnDisabled: {
    backgroundColor: 'rgba(255,255,255,0.10)',
    shadowOpacity: 0,
    elevation: 0,
  },
  initiateBtnText: {
    fontSize: 15,
    fontWeight: '800',
    color: '#fff',
    letterSpacing: 1.2,
  },
  initiateBtnTextDisabled: {
    color: 'rgba(255,255,255,0.30)',
  },

  // ── Active ops widget ──
  activeOpsWrap: {
    marginTop: 16,
    gap: 8,
  },
  activeOpsHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
    marginBottom: 4,
    paddingHorizontal: 2,
  },
  activeOpsDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: GREEN,
    opacity: 0.7,
  },
  activeOpsLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: 'rgba(255,255,255,0.38)',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
  },
  activeOpCard: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderRadius: 14,
    paddingVertical: 11,
    paddingHorizontal: 13,
    gap: 11,
    overflow: 'hidden',
  },
  activeOpGlowBorder: {
    borderRadius: 14,
    borderWidth: 1,
  },
  activeOpIconWrap: {
    width: 44,
    height: 44,
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  activeOpSpinArc: {
    position: 'absolute',
    width: 44,
    height: 44,
    borderRadius: 22,
    borderWidth: 1.5,
    borderTopColor: 'transparent',
    borderRightColor: 'transparent',
    borderBottomColor: 'transparent',
    borderLeftColor: 'transparent',
  },
  activeOpIcon: {
    width: 34,
    height: 34,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  activeOpContent: {
    flex: 1,
    gap: 3,
  },
  activeOpId: {
    fontSize: 13,
    fontWeight: '700',
    color: 'rgba(255,255,255,0.88)',
    letterSpacing: 0.2,
  },
  activeOpDetail: {
    fontSize: 11,
    color: 'rgba(255,255,255,0.4)',
    fontWeight: '400',
  },
  activeOpRight: {
    alignItems: 'flex-end',
    gap: 4,
    flexShrink: 0,
  },
  activeOpPill: {
    borderWidth: 1,
    borderRadius: 20,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  activeOpPillText: {
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 0.2,
  },

  // ── Block modal (operación activa) ──
  blockModalBackdrop: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 24,
  },
  blockModalCard: {
    width: '100%',
    backgroundColor: 'rgba(255,255,255,0.07)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.13)',
    borderRadius: 24,
    paddingVertical: 32,
    paddingHorizontal: 24,
    alignItems: 'center',
  },
  blockModalIconWrap: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: 'rgba(245,158,11,0.12)',
    borderWidth: 1,
    borderColor: 'rgba(245,158,11,0.25)',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 20,
  },
  blockModalTitle: {
    fontSize: 17,
    fontWeight: '700',
    color: '#fff',
    textAlign: 'center',
    letterSpacing: -0.2,
    marginBottom: 10,
  },
  blockModalBody: {
    fontSize: 13,
    color: 'rgba(255,255,255,0.52)',
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: 28,
  },
  blockModalBtnPrimary: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    width: '100%',
    backgroundColor: '#f59e0b',
    borderRadius: 14,
    paddingVertical: 14,
    marginBottom: 10,
    shadowColor: '#f59e0b',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.35,
    shadowRadius: 10,
    elevation: 6,
  },
  blockModalBtnPrimaryText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#fff',
    letterSpacing: 0.2,
  },
  blockModalBtnSecondary: {
    paddingVertical: 10,
    paddingHorizontal: 20,
  },
  blockModalBtnSecondaryText: {
    fontSize: 13,
    color: 'rgba(255,255,255,0.38)',
    fontWeight: '500',
  },
  minModalCard: {
    borderColor: 'rgba(245,158,11,0.22)',
  },
  minModalIconWrap: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: 'rgba(245,158,11,0.12)',
    borderWidth: 1,
    borderColor: 'rgba(245,158,11,0.25)',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 20,
  },
  minModalHighlight: {
    color: '#f59e0b',
    fontWeight: '700',
  },
  minModalBtnClose: {
    width: '100%',
    paddingVertical: 13,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.18)',
    alignItems: 'center',
  },

  // ── Referral ──────────────────────────────────────────────────────────────
  referralRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    marginHorizontal: 20,
    marginTop: 10,
    paddingVertical: 4,
  },
  referralRowActive: {},
  referralRowText: {
    fontSize: 13,
    color: 'rgba(255,255,255,0.5)',
    fontWeight: '500',
  },
  referralBadge: {
    backgroundColor: 'rgba(34,197,94,0.15)',
    borderWidth: 1,
    borderColor: 'rgba(34,197,94,0.3)',
    borderRadius: 8,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  referralBadgeText: {
    fontSize: 11,
    fontWeight: '700',
    color: GREEN,
  },
  rateImprovedWrap: {
    alignItems: 'flex-start',
    gap: 1,
  },
  rateTabValueStrike: {
    fontSize: 13,
    fontWeight: '500',
    color: 'rgba(255,255,255,0.3)',
    textDecorationLine: 'line-through',
  },
  rateImprovedValue: {
    color: GREEN,
  },
  ratePipBadge: {
    fontSize: 9,
    fontWeight: '700',
    color: GREEN,
    marginBottom: 2,
  },
  volumeBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    alignSelf: 'center',
    backgroundColor: 'rgba(251,191,36,0.10)',
    borderRadius: 20,
    paddingHorizontal: 12,
    paddingVertical: 5,
    marginTop: 10,
    borderWidth: 1,
    borderColor: 'rgba(251,191,36,0.22)',
  },
  volumeBadgeText: {
    fontSize: 11,
    color: '#fbbf24',
    fontWeight: '600',
  },

  // ── Referral modal ────────────────────────────────────────────────────────
  referralModalOverlay: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 20,
  },
  referralModalSheet: {
    width: '100%',
    backgroundColor: 'rgba(255,255,255,0.07)',
    borderRadius: 24,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: 'rgba(34,197,94,0.18)',
    padding: 24,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.4,
    shadowRadius: 28,
    elevation: 20,
  },
  referralModalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginBottom: 16,
  },
  referralModalIcon: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: 'rgba(34,197,94,0.12)',
    borderWidth: 1,
    borderColor: 'rgba(34,197,94,0.25)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  referralModalTitle: {
    flex: 1,
    fontSize: 17,
    fontWeight: '700',
    color: '#fff',
  },
  referralModalClose: {
    padding: 4,
  },
  referralModalSub: {
    fontSize: 13,
    color: 'rgba(255,255,255,0.5)',
    lineHeight: 20,
    marginBottom: 20,
  },
  referralModalInput: {
    backgroundColor: 'rgba(255,255,255,0.06)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.14)',
    borderRadius: 14,
    paddingHorizontal: 16,
    paddingVertical: 14,
    fontSize: 20,
    fontWeight: '700',
    color: '#fff',
    textAlign: 'center',
    letterSpacing: 4,
    marginBottom: 16,
  },
  referralModalBtn: {
    backgroundColor: GREEN,
    borderRadius: 14,
    paddingVertical: 15,
    alignItems: 'center',
    shadowColor: GREEN,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.4,
    shadowRadius: 12,
    elevation: 6,
  },
  referralModalBtnDisabled: {
    backgroundColor: 'rgba(34,197,94,0.2)',
    shadowOpacity: 0,
    elevation: 0,
  },
  referralModalBtnText: {
    fontSize: 15,
    fontWeight: '700',
    color: '#fff',
    letterSpacing: 0.3,
  },
});
