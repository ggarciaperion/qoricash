import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  StyleSheet,
  Animated,
  RefreshControl,
  Image,
  ImageBackground,
  Alert,
  TouchableOpacity,
  Text,
  Dimensions,
} from 'react-native';
import { MotiView } from 'moti';
import { Ionicons } from '@expo/vector-icons';
import Reanimated, {
  useSharedValue,
  useAnimatedStyle,
  withRepeat,
  withSequence,
  withTiming,
  Easing as REasing,
} from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { BlurView } from 'expo-blur';
import * as Haptics from 'expo-haptics';
import axios from 'axios';
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

  const [pendingOp, setPendingOp] = useState<{
    ready: boolean;
    operationType: 'Compra' | 'Venta';
    amountUSD: string;
    rate: number;
  }>({ ready: false, operationType: 'Compra', amountUSD: '', rate: 0 });
  const [calcOperationType, setCalcOperationType] = useState<'Compra' | 'Venta'>('Compra');
  const [calcRates, setCalcRates] = useState<{ compra: number; venta: number } | null>(null);

  // Scroll Y para sticky header
  const scrollY = useRef(new Animated.Value(0)).current;

  // Sticky header opacity & translateY
  const stickyOp = scrollY.interpolate({
    inputRange:  [STICKY_THRESHOLD, STICKY_THRESHOLD + 32],
    outputRange: [0, 1],
    extrapolate: 'clamp',
  });
  const stickyTY = scrollY.interpolate({
    inputRange:  [STICKY_THRESHOLD, STICKY_THRESHOLD + 32],
    outputRange: [-12, 0],
    extrapolate: 'clamp',
  });

  // Parallax leve en el fondo
  const bgTY = scrollY.interpolate({
    inputRange:  [0, 300],
    outputRange: [0, -40],
    extrapolate: 'clamp',
  });

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

  const firstName = (() => {
    if (client.nombres)   return capitalize(client.nombres.split(' ')[0]);
    if (client.full_name) return capitalize(client.full_name.split(' ')[0]);
    return '';
  })();

  return (
    <View style={s.root}>

      {/* ── Fondo con parallax ── */}
      <Animated.View
        style={[StyleSheet.absoluteFill, { transform: [{ translateY: bgTY }] }]}
        pointerEvents="none"
      >
        <ImageBackground
          source={require('../../assets/cd.png')}
          style={[StyleSheet.absoluteFill, { top: -60, bottom: -60 }]}
          resizeMode="cover"
        />
      </Animated.View>
      <View style={[StyleSheet.absoluteFill, s.overlay]} pointerEvents="none" />

      {/* ── Sticky compact header ── */}
      <Animated.View
        style={[
          s.stickyHeader,
          { top: insets.top, opacity: stickyOp, transform: [{ translateY: stickyTY }] },
        ]}
        pointerEvents="none"
      >
        <BlurView intensity={70} tint="dark" style={StyleSheet.absoluteFill} />
        <View style={s.stickyHairline} />
        <Image source={require('../../assets/vv.png')} style={s.stickyLogo} resizeMode="contain" />
        <Text style={s.stickyName}>{firstName}</Text>
      </Animated.View>

      {/* ── Scroll ── */}
      <Animated.ScrollView
        style={s.scroll}
        contentContainerStyle={[
          s.content,
          { paddingTop: insets.top + 20, paddingBottom: insets.bottom + TAB_BAR_H + 16 },
        ]}
        showsVerticalScrollIndicator={false}
        scrollEventThrottle={16}
        onScroll={Animated.event([{ nativeEvent: { contentOffset: { y: scrollY } } }], {
          useNativeDriver: true,
        })}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor="rgba(255,255,255,0.5)"
          />
        }
      >

        {/* ══ Brand + Saludo ══ */}
        <MotiView
          from={{ opacity: 0, translateY: -20 }}
          animate={{ opacity: 1, translateY: 0 }}
          transition={{ type: 'spring', delay: 0, damping: 22, stiffness: 200 }}
          style={s.headerSection}
        >
          <View style={s.headerRow}>
            <View>
              <Text style={s.greetingLabel}>Bienvenido,</Text>
              <Text style={s.greetingName}>{firstName}</Text>
            </View>
            <Image source={require('../../assets/vv.png')} style={s.logo} resizeMode="contain" />
          </View>
        </MotiView>

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
            style={[s.rateTab, calcOperationType === 'Compra' && s.rateTabActive]}
          >
            <Text style={s.rateTabLabel}>Qoricash compra</Text>
            <Text style={[s.rateTabValue, calcOperationType !== 'Compra' && s.rateTabValueDim]}>
              S/ {calcRates?.compra.toFixed(3) ?? '—'}
            </Text>
            <View style={s.rateTabPill}>
              <Text style={s.rateTabPillText}>USD → PEN</Text>
            </View>
          </TouchableOpacity>

          <TouchableOpacity
            onPress={() => setCalcOperationType('Venta')}
            activeOpacity={0.82}
            style={[s.rateTab, calcOperationType === 'Venta' && s.rateTabActive]}
          >
            <Text style={s.rateTabLabel}>Qoricash vende</Text>
            <Text style={[s.rateTabValue, calcOperationType !== 'Venta' && s.rateTabValueDim]}>
              S/ {calcRates?.venta.toFixed(3) ?? '—'}
            </Text>
            <View style={s.rateTabPill}>
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
            hideTabs
          />
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
              const iconName    = isEnProceso ? 'swap-horizontal' : 'time-outline';

              return (
                <TouchableOpacity
                  key={op.id}
                  style={[s.activeOpCard, { backgroundColor: bgColor, borderColor }]}
                  onPress={() => {
                    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
                    navigation.navigate('History');
                  }}
                  activeOpacity={0.8}
                >
                  {/* Left icon */}
                  <View style={[s.activeOpIcon, { backgroundColor: `${accentColor}18` }]}>
                    <Ionicons name={iconName as any} size={16} color={accentColor} />
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
            })}
          </MotiView>
        )}

      </Animated.ScrollView>
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

  // ── Sticky header ──
  stickyHeader: {
    position: 'absolute',
    left: 0,
    right: 0,
    zIndex: 100,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 12,
    overflow: 'hidden',
  },
  stickyHairline: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    height: StyleSheet.hairlineWidth,
    backgroundColor: 'rgba(255,255,255,0.12)',
  },
  stickyLogo: {
    width: 110,
    height: 22,
  },
  stickyName: {
    fontSize: 15,
    fontWeight: '700',
    color: 'rgba(255,255,255,0.88)',
    letterSpacing: 0.1,
  },

  // ── Header section ──
  headerSection: {
    marginBottom: 20,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  logo: {
    width: 120,
    height: 24,
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
    backgroundColor: GLASS_BG,
    borderWidth: 1,
    borderColor: GLASS_BORDER,
    borderRadius: 22,
  },
  rateTabActive: {
    backgroundColor: 'rgba(34,197,94,0.13)',
    borderColor: GREEN,
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
    marginTop: 14,
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
  },
  activeOpIcon: {
    width: 34,
    height: 34,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
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
});
