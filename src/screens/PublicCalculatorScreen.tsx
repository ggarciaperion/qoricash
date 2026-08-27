import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  Text,
  Image,
  Pressable,
  RefreshControl,
  Modal,
  TouchableWithoutFeedback,
  ActivityIndicator,
} from 'react-native';
import { MotiView } from 'moti';
import { Ionicons, FontAwesome } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import Reanimated, {
  useSharedValue,
  useAnimatedStyle,
  withTiming,
  withSpring,
  withSequence,
  withRepeat,
  Easing,
} from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import axios from 'axios';
import { API_CONFIG } from '../constants/config';
import socketService from '../services/socketService';
import * as WebBrowser from 'expo-web-browser';
import * as Google from 'expo-auth-session/providers/google';
import { authApi } from '../api/auth';
import { useAuth } from '../contexts/AuthContext';

WebBrowser.maybeCompleteAuthSession();

// ─── Google OAuth Client IDs ─────────────────────────────────────
// Obtén estos IDs en: https://console.cloud.google.com
// Proyecto → APIs & Services → Credentials → OAuth 2.0 Client IDs
// Para desarrollo con Expo Go se usa el Web Client ID en las 3 plataformas.
// Cuando hagas build de producción con EAS, crea client IDs separados para iOS y Android.
const GOOGLE_WEB_CLIENT_ID     = '222745937465-oe0ev6qqdhr5fnn7aund36hs6e52njma.apps.googleusercontent.com';
const GOOGLE_IOS_CLIENT_ID     = GOOGLE_WEB_CLIENT_ID;
const GOOGLE_ANDROID_CLIENT_ID = GOOGLE_WEB_CLIENT_ID;

// ─────────────────────────────────────────────────────────────────
// Tipos
// ─────────────────────────────────────────────────────────────────
interface Rates { compra: number; venta: number }
interface Props  { navigation: any }

// ─────────────────────────────────────────────────────────────────
// RateValue — número de tipo de cambio con flip animado al cambiar
// ─────────────────────────────────────────────────────────────────
interface RateValueProps { value: string; style?: any }

const RateValue: React.FC<RateValueProps> = ({ value, style }) => {
  const op = useSharedValue(1);
  const ty = useSharedValue(0);
  const animStyle = useAnimatedStyle(() => ({
    opacity: op.value,
    transform: [{ translateY: ty.value }],
  }));

  useEffect(() => {
    op.value = withTiming(0, { duration: 130, easing: Easing.in(Easing.quad) });
    ty.value = withTiming(-5, { duration: 130 });
    const t = setTimeout(() => {
      ty.value = 7;
      op.value = withTiming(1, { duration: 180, easing: Easing.out(Easing.quad) });
      ty.value = withSpring(0, { damping: 16, stiffness: 220 });
    }, 150);
    return () => clearTimeout(t);
  }, [value]);

  return <Reanimated.Text style={[style, animStyle]}>{value}</Reanimated.Text>;
};

// ─────────────────────────────────────────────────────────────────
// LiveDot — respiración orgánica + onda expansiva suave
// ─────────────────────────────────────────────────────────────────
const LiveDot: React.FC = () => {
  const scale  = useSharedValue(1);
  const ringOp = useSharedValue(0);
  const ringSc = useSharedValue(1);

  useEffect(() => {
    // Núcleo: respira suavemente — inOut para sensación completamente orgánica
    scale.value = withRepeat(
      withSequence(
        withTiming(1.26, { duration: 750, easing: Easing.inOut(Easing.quad) }),
        withTiming(1,    { duration: 750, easing: Easing.inOut(Easing.quad) }),
      ),
      -1,
      false,
    );

    // Onda: se expande lenta y graciosamente desde el núcleo
    ringOp.value = withRepeat(
      withSequence(
        withTiming(0.5,  { duration: 200, easing: Easing.out(Easing.quad) }),
        withTiming(0,    { duration: 1100, easing: Easing.out(Easing.cubic) }),
        withTiming(0,    { duration: 200 }),
      ),
      -1,
      false,
    );
    ringSc.value = withRepeat(
      withSequence(
        withTiming(1,   { duration: 0 }),
        withTiming(2.6, { duration: 1300, easing: Easing.out(Easing.cubic) }),
        withTiming(1,   { duration: 0 }),
      ),
      -1,
      false,
    );
  }, []);

  const dotStyle  = useAnimatedStyle(() => ({ transform: [{ scale: scale.value }] }));
  const ringStyle = useAnimatedStyle(() => ({
    opacity: ringOp.value,
    transform: [{ scale: ringSc.value }],
  }));

  return (
    <View style={styles.liveDotWrapper}>
      <Reanimated.View pointerEvents="none" style={[styles.livePulse, ringStyle]} />
      <Reanimated.View style={[styles.liveDotCore, dotStyle]} />
    </View>
  );
};

// ─────────────────────────────────────────────────────────────────
// Screen principal
// ─────────────────────────────────────────────────────────────────
export const PublicCalculatorScreen: React.FC<Props> = ({ navigation }) => {
  const insets = useSafeAreaInsets();
  const { loginWithGoogle } = useAuth();
  const [rates, setRates]           = useState<Rates | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [googleError, setGoogleError]     = useState('');

  // Google OAuth hook
  const [, response, promptGoogleAsync] = Google.useAuthRequest({
    iosClientId:     GOOGLE_IOS_CLIENT_ID,
    androidClientId: GOOGLE_ANDROID_CLIENT_ID,
    webClientId:     GOOGLE_WEB_CLIENT_ID,
  });

  // Manejar respuesta de Google
  useEffect(() => {
    if (response?.type === 'success') {
      const accessToken = response.authentication?.accessToken;
      if (accessToken) handleGoogleAuthResponse(accessToken);
    } else if (response?.type === 'error') {
      setGoogleError('No se pudo conectar con Google. Intenta de nuevo.');
      setGoogleLoading(false);
    } else if (response?.type === 'dismiss') {
      setGoogleLoading(false);
    }
  }, [response]);

  const handleGoogleAuthResponse = async (accessToken: string) => {
    try {
      setGoogleLoading(true);
      setGoogleError('');

      const result = await authApi.googleAuth(accessToken);

      if (result.action === 'login' && result.client) {
        // Cliente existente → iniciar sesión directamente
        await loginWithGoogle(result.client);
      } else if (result.action === 'register') {
        // Nuevo usuario → ir a completar registro con datos de Google pre-llenados
        navigation.navigate('RegisterWithGoogle', {
          google_email: result.google_email,
          google_name:  result.google_name,
        });
      }
    } catch (err: any) {
      setGoogleError(err.message || 'Error al autenticar con Google.');
    } finally {
      setGoogleLoading(false);
    }
  };

  const handleGooglePress = async () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setGoogleError('');
    setGoogleLoading(true);
    await promptGoogleAsync();
  };

  const fetchRates = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API_CONFIG.BASE_URL}/api/client/exchange-rates`);
      if (data.success) setRates(data.rates);
    } catch (_) {}
  }, []);

  useEffect(() => {
    fetchRates();
    const handler = (d: any) => setRates({ compra: d.compra, venta: d.venta });
    socketService.on('tipos_cambio_actualizados', handler);
    return () => socketService.off('tipos_cambio_actualizados', handler);
  }, []);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchRates();
    setRefreshing(false);
  }, [fetchRates]);

  const goLogin    = useCallback(() => navigation.navigate('Login'), [navigation]);
  const goRegister = useCallback(() => navigation.navigate('ClientTypeSelection'), [navigation]);

  // ── Popup de beneficios ──────────────────────────────────────
  const [popup, setPopup] = useState<{ title: string; body: string } | null>(null);

  const BENEFITS = [
    {
      icon: 'shield-checkmark-outline' as const,
      label: 'Seguro',
      title: 'Operaciones seguras',
      body: 'Utilizamos encriptación de nivel bancario y verificación de identidad para proteger cada transacción. Tu dinero y tus datos siempre están resguardados.',
    },
    {
      icon: 'flash-outline' as const,
      label: 'Inmediato',
      title: 'Cambio en minutos',
      body: 'Realizamos tu operación de cambio de forma rápida y eficiente. Sin esperas, sin burocracia. Tu dinero disponible en minutos.',
    },
    {
      icon: 'ribbon-outline' as const,
      label: 'Inscrito SBS',
      title: 'Regulado por la SBS',
      body: 'Registrados ante la SBS\nRes. N° 00313-2026\n\nOperamos bajo supervisión de la Superintendencia de Banca, Seguros y AFP del Perú.',
    },
  ] as const;

  const compra = rates ? `S/ ${rates.compra.toFixed(3)}` : '— —';
  const venta  = rates ? `S/ ${rates.venta.toFixed(3)}` : '— —';

  return (
    <View style={styles.bg}>

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={[
          styles.content,
          { paddingTop: insets.top + 16, paddingBottom: insets.bottom + 24 },
        ]}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor="rgba(255,255,255,0.5)"
          />
        }
      >

        {/* ══════════════════════════════════════════════
            BRAND — Qoricash + tagline
        ══════════════════════════════════════════════ */}
        <MotiView
          from={{ opacity: 0, translateY: -18 }}
          animate={{ opacity: 1, translateY: 0 }}
          transition={{ type: 'timing', duration: 540, easing: Easing.out(Easing.cubic) }}
          style={styles.brandSection}
        >
          {/* Logo absoluto — no empuja el contenido sin importar su tamaño */}
          <Image
            source={require('../../assets/logo.png')}
            style={styles.brandLogo}
            resizeMode="contain"
          />
          <Text style={styles.tagline}>
            CASA DE CAMBIO DIGITAL
          </Text>
        </MotiView>

        {/* ══════════════════════════════════════════════
            BENEFIT CARDS — Seguro · Inmediato · SBS
        ══════════════════════════════════════════════ */}
        <MotiView
          from={{ opacity: 0, translateY: 14 }}
          animate={{ opacity: 1, translateY: 0 }}
          transition={{ type: 'timing', duration: 460, delay: 100 }}
          style={styles.benefitsRow}
        >
          {BENEFITS.map((item, i) => (
            <Pressable
              key={i}
              style={({ pressed }) => [styles.benefitCard, pressed && { opacity: 0.72 }]}
              onPress={() => {
                Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
                setPopup({ title: item.title, body: item.body });
              }}
            >
              <View style={styles.benefitIconWrap}>
                <Ionicons name={item.icon} size={15} color="rgba(255,255,255,0.92)" />
              </View>
              <Text style={styles.benefitLabel}>{item.label}</Text>
            </Pressable>
          ))}
        </MotiView>

        {/* ══════════════════════════════════════════════
            LIVE INDICATOR
        ══════════════════════════════════════════════ */}
        <MotiView
          from={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ type: 'timing', duration: 380, delay: 180 }}
          style={styles.liveRow}
        >
          <LiveDot />
          <Text style={styles.liveLabel}>Tipo de cambio en vivo</Text>
        </MotiView>

        {/* ══════════════════════════════════════════════
            RATE CARDS — Compra / Venta
        ══════════════════════════════════════════════ */}
        <MotiView
          from={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ type: 'spring', delay: 140, damping: 18, stiffness: 130 }}
          style={styles.ratesRow}
        >
          {/* Card Compra */}
          <View style={styles.rateCard}>
            <Text style={styles.rateCardLabel}>Qoricash compra</Text>
            <RateValue value={compra} style={[styles.rateCardValue, { color: '#38bdf8' }]} />
            <View style={[styles.ratePill, {
              backgroundColor: 'transparent',
              borderWidth: 0,
            }]}>
              <Text style={[styles.ratePillText, { color: '#38bdf8' }]}>USD → PEN</Text>
            </View>
          </View>

          <View style={styles.ratesDivider} />

          {/* Card Venta */}
          <View style={styles.rateCard}>
            <Text style={styles.rateCardLabel}>Qoricash vende</Text>
            <RateValue value={venta} style={[styles.rateCardValue, { color: '#22c55e' }]} />
            <View style={[styles.ratePill, {
              backgroundColor: 'transparent',
              borderWidth: 0,
            }]}>
              <Text style={[styles.ratePillText, { color: '#22c55e' }]}>PEN → USD</Text>
            </View>
          </View>
        </MotiView>

        {/* ══════════════════════════════════════════════
            LOGIN
        ══════════════════════════════════════════════ */}
        <MotiView
          from={{ opacity: 0, translateY: 14 }}
          animate={{ opacity: 1, translateY: 0 }}
          transition={{ type: 'timing', duration: 400, delay: 220 }}
          style={styles.loginSection}
        >
          <Text style={styles.sectionMeta}>Para operar</Text>

          <Pressable
            onPress={() => {
              Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
              goLogin();
            }}
            style={({ pressed }) => [styles.loginBtn, pressed && styles.btnPressed]}
          >
            <Text style={styles.loginBtnText}>Ingresar</Text>
            <Ionicons name="arrow-forward" size={17} color="#0a1a2e" />
          </Pressable>
        </MotiView>

        {/* ══════════════════════════════════════════════
            REGISTER
        ══════════════════════════════════════════════ */}
        <MotiView
          from={{ opacity: 0, translateY: 14 }}
          animate={{ opacity: 1, translateY: 0 }}
          transition={{ type: 'timing', duration: 400, delay: 290 }}
          style={styles.registerSection}
        >
          <Text style={styles.registerPrompt}>Si no eres cliente, regístrate</Text>

          <Pressable
            onPress={() => {
              Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
              goRegister();
            }}
            style={({ pressed }) => [styles.glassBtn, pressed && styles.btnPressed]}
          >
            <Text style={styles.glassBtnText}>Registrar</Text>
          </Pressable>

          <Pressable
            onPress={handleGooglePress}
            disabled={googleLoading}
            style={({ pressed }) => [styles.glassBtn, styles.googleBtn, pressed && styles.btnPressed, googleLoading && styles.btnDisabled]}
          >
            {googleLoading
              ? <ActivityIndicator size="small" color="rgba(255,255,255,0.88)" />
              : <FontAwesome name="google" size={15} color="rgba(255,255,255,0.88)" />
            }
            <Text style={styles.glassBtnText}>
              {googleLoading ? 'Conectando...' : 'Continuar con Google'}
            </Text>
          </Pressable>

          {!!googleError && (
            <Text style={styles.googleErrorText}>{googleError}</Text>
          )}
        </MotiView>

        {/* ══════════════════════════════════════════════
            FOOTER
        ══════════════════════════════════════════════ */}
        <Text style={styles.footer}>Casa de cambio inscrita en la SBS</Text>

      </ScrollView>

      {/* ══════════════════════════════════════════════
          POPUP de beneficio
      ══════════════════════════════════════════════ */}
      <Modal
        visible={!!popup}
        transparent
        animationType="fade"
        statusBarTranslucent
        onRequestClose={() => setPopup(null)}
      >
        <TouchableWithoutFeedback onPress={() => setPopup(null)}>
          <View style={styles.popupBackdrop}>
            <TouchableWithoutFeedback>
              <View style={styles.popupCard}>
                <Text style={styles.popupTitle}>{popup?.title}</Text>
                <View style={styles.popupDivider} />
                <Text style={styles.popupBody}>{popup?.body}</Text>
                <Pressable
                  style={({ pressed }) => [styles.popupClose, pressed && { opacity: 0.7 }]}
                  onPress={() => setPopup(null)}
                >
                  <Text style={styles.popupCloseText}>Entendido</Text>
                </Pressable>
              </View>
            </TouchableWithoutFeedback>
          </View>
        </TouchableWithoutFeedback>
      </Modal>

    </View>
  );
};

// ─────────────────────────────────────────────────────────────────
// Estilos
// ─────────────────────────────────────────────────────────────────
const GLASS_BG     = 'rgba(255, 255, 255, 0.09)';
const GLASS_BORDER = 'rgba(255, 255, 255, 0.17)';

const styles = StyleSheet.create({
  bg: {
    flex: 1,
  },
  scroll: {
    flex: 1,
  },
  content: {
    flexGrow: 1,
    justifyContent: 'center',
    paddingHorizontal: 22,
  },

  // ── Brand ──────────────────────────────────────────────────────
  brandSection: {
    alignItems: 'center',
    marginBottom: 24,
  },
  brandLogo: {
    width: 180,
    height: 36,
    marginBottom: 10,
  },
  tagline: {
    fontFamily: 'Inter_400Regular',
    fontSize: 10.5,
    color: 'rgba(255,255,255,0.52)',
    letterSpacing: 2.8,
    textAlign: 'center',
  },

  // ── Benefit cards ──────────────────────────────────────────────
  benefitsRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 32,
    marginBottom: 22,
  },
  benefitCard: {
    alignItems: 'center',
    gap: 4,
  },
  benefitIconWrap: {
    width: 26,
    height: 26,
    borderRadius: 13,
    backgroundColor: 'rgba(255,255,255,0.08)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  benefitLabel: {
    fontFamily: 'Inter_500Medium',
    fontSize: 8.5,
    color: 'rgba(255,255,255,0.78)',
    textAlign: 'center',
    letterSpacing: 0.1,
    lineHeight: 12,
  },

  // ── Popup ───────────────────────────────────────────────────────
  popupBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.58)',
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 32,
  },
  popupCard: {
    width: '100%',
    backgroundColor: '#0d1f2d',
    borderRadius: 20,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.14)',
    padding: 24,
  },
  popupTitle: {
    fontFamily: 'Montserrat_700Bold',
    fontSize: 15,
    color: '#FFFFFF',
    letterSpacing: 0.2,
    marginBottom: 12,
  },
  popupDivider: {
    height: 1,
    backgroundColor: 'rgba(255,255,255,0.1)',
    marginBottom: 14,
  },
  popupBody: {
    fontFamily: 'Inter_400Regular',
    fontSize: 13.5,
    color: 'rgba(255,255,255,0.75)',
    lineHeight: 21,
    marginBottom: 22,
  },
  popupClose: {
    backgroundColor: 'rgba(255,255,255,0.1)',
    borderRadius: 12,
    paddingVertical: 12,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.18)',
  },
  popupCloseText: {
    fontFamily: 'Inter_600SemiBold',
    fontSize: 14,
    color: '#FFFFFF',
    letterSpacing: 0.2,
  },

  // ── Live indicator ─────────────────────────────────────────────
  liveRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 9,
    marginTop: 20,
    marginBottom: 14,
  },
  liveDotWrapper: {
    width: 12,
    height: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  livePulse: {
    position: 'absolute',
    width: 12,
    height: 12,
    borderRadius: 6,
    borderWidth: 1.5,
    borderColor: '#4ade80',
  },
  liveDotCore: {
    width: 7,
    height: 7,
    borderRadius: 3.5,
    backgroundColor: '#4ade80',
  },
  liveLabel: {
    fontFamily: 'Inter_500Medium',
    fontSize: 12,
    color: 'rgba(255,255,255,0.72)',
    letterSpacing: 0.2,
  },

  // ── Rate cards ─────────────────────────────────────────────────
  ratesRow: {
    flexDirection: 'row',
    backgroundColor: GLASS_BG,
    borderWidth: 1,
    borderColor: GLASS_BORDER,
    borderRadius: 22,
    marginBottom: 28,
    overflow: 'hidden',
  },
  rateCard: {
    flex: 1,
    paddingVertical: 22,
    paddingHorizontal: 18,
    gap: 6,
  },
  ratesDivider: {
    width: 1,
    backgroundColor: GLASS_BORDER,
    marginVertical: 18,
  },
  rateCardLabel: {
    fontFamily: 'Inter_400Regular',
    fontSize: 11,
    color: 'rgba(255,255,255,0.52)',
    letterSpacing: 1.4,
    textTransform: 'uppercase',
  },
  rateCardValue: {
    fontFamily: 'Montserrat_700Bold',
    fontSize: 32,
    color: '#FFFFFF',
    letterSpacing: -0.5,
    lineHeight: 38,
  },
  ratePill: {
    alignSelf: 'flex-start',
    backgroundColor: 'transparent',
    borderRadius: 20,
    paddingHorizontal: 8,
    paddingVertical: 3,
    marginTop: 8,
  },
  ratePillText: {
    fontFamily: 'Inter_400Regular',
    fontSize: 9.5,
    color: 'rgba(255,255,255,0.55)',
    letterSpacing: 0.3,
  },

  // ── Login section ──────────────────────────────────────────────
  loginSection: {
    gap: 12,
    marginBottom: 24,
  },
  sectionMeta: {
    fontFamily: 'Inter_400Regular',
    fontSize: 11.5,
    color: 'rgba(255,255,255,0.45)',
    letterSpacing: 0.3,
  },
  loginBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    paddingVertical: 17,
    gap: 9,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.22,
    shadowRadius: 14,
    elevation: 8,
  },
  loginBtnText: {
    fontFamily: 'Inter_700Bold',
    fontSize: 15.5,
    color: '#0a1a2e',
    letterSpacing: 0.2,
  },

  // ── Register section ───────────────────────────────────────────
  registerSection: {
    gap: 10,
    marginBottom: 28,
  },
  registerPrompt: {
    fontFamily: 'Inter_400Regular',
    fontSize: 11.5,
    color: 'rgba(255,255,255,0.45)',
    letterSpacing: 0.3,
    marginBottom: 2,
  },
  glassBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: GLASS_BG,
    borderWidth: 1,
    borderColor: GLASS_BORDER,
    borderRadius: 16,
    paddingVertical: 15,
    gap: 9,
  },
  googleBtn: {
    // mismo glass, solo añade gap con el ícono
  },
  btnDisabled: {
    opacity: 0.6,
  },
  googleErrorText: {
    fontSize: 12,
    color: '#f87171',
    textAlign: 'center',
    marginTop: 4,
  },
  glassBtnText: {
    fontFamily: 'Inter_500Medium',
    fontSize: 14.5,
    color: 'rgba(255,255,255,0.88)',
    letterSpacing: 0.1,
  },

  // ── Shared ─────────────────────────────────────────────────────
  btnPressed: {
    opacity: 0.78,
    transform: [{ scale: 0.975 }],
  },

  // ── Footer ─────────────────────────────────────────────────────
  footer: {
    fontFamily: 'Inter_400Regular',
    fontSize: 10,
    color: 'rgba(255,255,255,0.28)',
    textAlign: 'center',
    letterSpacing: 0.4,
  },
});
