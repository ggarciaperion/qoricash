import React, { useState, useRef, useEffect } from 'react';
import {
  View,
  StyleSheet,
  TouchableOpacity,
  Animated,
  Easing,
  StatusBar,
  Modal,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  ScrollView,
  Keyboard,
} from 'react-native';
import { TextInput, Text, IconButton } from 'react-native-paper';
import { LinearGradient } from 'expo-linear-gradient';
import { BlurView } from 'expo-blur';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useAuth } from '../contexts/AuthContext';
import { useLoginLoading } from '../contexts/LoginLoadingContext';
import { Colors } from '../constants/colors';
import { API_CONFIG } from '../constants/config';
import { GlobalStyles } from '../styles/globalStyles';

type DocumentType = 'DNI' | 'CE' | 'RUC';

const MAX_ATTEMPTS = 3;
const REMEMBER_KEY = '@qoricash:remember_doc';

// Opaque bg so react-native-paper can cut a clean gap in the floating label
const INPUT_BG = 'rgba(0,8,22,0.35)';

// Glass constants — matches PublicCalculatorScreen
const GLASS_BG     = 'rgba(255,255,255,0.08)';
const GLASS_BORDER = 'rgba(255,255,255,0.17)';

const detectDocType = (num: string): DocumentType | null => {
  if (num.length === 8)  return 'DNI';
  if (num.length === 9)  return 'CE';
  if (num.length === 11) return 'RUC';
  return null;
};

// ─── Main component ───────────────────────────────────────────────────────────
export const LoginScreen = () => {
  const navigation = useNavigation();
  const insets     = useSafeAreaInsets();
  const { login, loading } = useAuth();
  const { setShowLoginLoading } = useLoginLoading();

  const [documentType, setDocumentType] = useState<DocumentType | null>(null);
  const [dni,          setDni]          = useState('');
  const [password,     setPassword]     = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe,   setRememberMe]   = useState(false);

  // Attempt tracking
  const [failedAttempts, setFailedAttempts] = useState(0);
  const [showErrModal,   setShowErrModal]   = useState(false);
  const [errMsg,         setErrMsg]         = useState('');
  const [errIsAuth,      setErrIsAuth]      = useState(false);
  const isLocked = failedAttempts >= MAX_ATTEMPTS;

  // Forgot password modal
  const [showForgotModal, setShowForgotModal] = useState(false);
  const [resetDni,        setResetDni]        = useState('');
  const [resetEmail,      setResetEmail]      = useState('');
  const [resetLoading,    setResetLoading]    = useState(false);
  const [resetStep,       setResetStep]       = useState('');
  const [resetError,      setResetError]      = useState('');
  const [resetSending,    setResetSending]    = useState(false);
  const [resetSuccess,    setResetSuccess]    = useState(false);
  const forgotSlide       = useRef(new Animated.Value(52)).current;
  const resetBtnScale     = useRef(new Animated.Value(1)).current;
  const forgotFade        = useRef(new Animated.Value(0)).current;
  const forgotCardScale   = useRef(new Animated.Value(0.92)).current;
  const forgotCardOpacity = useRef(new Animated.Value(0)).current;

  const btnScale  = useRef(new Animated.Value(1)).current;
  const exitFade  = useRef(new Animated.Value(1)).current;
  const exitSlide = useRef(new Animated.Value(0)).current;

  // Field micro-animation values
  const dniY = useRef(new Animated.Value(0)).current;
  const pwY  = useRef(new Animated.Value(0)).current;

  const focusField = (y: Animated.Value, focused: boolean) => {
    Animated.spring(y, {
      toValue: focused ? -4 : 0,
      useNativeDriver: true,
      tension: 320,
      friction: 14,
    }).start();
  };

  // Load remembered document on mount
  useEffect(() => {
    AsyncStorage.getItem(REMEMBER_KEY).then(raw => {
      if (!raw) return;
      try {
        const saved = JSON.parse(raw) as { number: string };
        setDni(saved.number);
        setDocumentType(detectDocType(saved.number));
        setRememberMe(true);
      } catch {}
    });
  }, []);


  const handleGoBack = () => navigation.goBack();

  const punchBtn = () => {
    Animated.sequence([
      Animated.timing(btnScale, { toValue: 0.96, duration: 80,  useNativeDriver: true }),
      Animated.timing(btnScale, { toValue: 1,    duration: 120, useNativeDriver: true }),
    ]).start();
  };

  const showError = (msg: string, isAuthFail = false) => {
    setErrMsg(msg);
    setErrIsAuth(isAuthFail);
    setShowErrModal(true);
  };

  const handleDniChange = (text: string) => {
    const cleaned = text.replace(/\D/g, '').slice(0, 11);
    setDni(cleaned);
    setDocumentType(detectDocType(cleaned));
    if (rememberMe) {
      AsyncStorage.setItem(REMEMBER_KEY, JSON.stringify({ number: cleaned }));
    }
  };

  const handleRememberToggle = async (val: boolean) => {
    setRememberMe(val);
    if (val) {
      await AsyncStorage.setItem(REMEMBER_KEY, JSON.stringify({ number: dni }));
    } else {
      await AsyncStorage.removeItem(REMEMBER_KEY);
    }
  };

  const handleLogin = async () => {
    if (isLocked) {
      showError('Has superado el número máximo de intentos. Usa "¿Olvidaste tu contraseña?" para recuperar tu cuenta.');
      return;
    }
    if (!documentType) {
      showError('Ingresa un número de documento válido.\nDNI: 8 dígitos · CE: 9 dígitos · RUC: 11 dígitos');
      return;
    }
    try {
      punchBtn();
      Keyboard.dismiss();
      setShowLoginLoading(true);
      await login({ username: dni, password }, dni);
    } catch (err: any) {
      setShowLoginLoading(false);
      const next = failedAttempts + 1;
      setFailedAttempts(next);
      const remaining = MAX_ATTEMPTS - next;
      const msg = next >= MAX_ATTEMPTS
        ? 'Has superado el número máximo de intentos (3/3). Tu cuenta ha sido bloqueada temporalmente.\n\nUsa "¿Olvidaste tu contraseña?" para recuperar el acceso.'
        : `Los datos ingresados son incorrectos. Verifica tu documento y contraseña.\n\nTe ${remaining === 1 ? 'queda 1 intento' : `quedan ${remaining} intentos`} antes de que tu cuenta sea bloqueada por seguridad.`;
      showError(msg, true);
    }
  };

  const openForgotModal = () => {
    setShowForgotModal(true);
    setResetSuccess(false);
    forgotSlide.setValue(52);
    forgotFade.setValue(0);
    forgotCardScale.setValue(0.92);
    forgotCardOpacity.setValue(0);
    Animated.parallel([
      Animated.timing(forgotFade,        { toValue: 1, duration: 320, easing: Easing.out(Easing.quad), useNativeDriver: true }),
      Animated.spring(forgotSlide,       { toValue: 0, tension: 200, friction: 18, useNativeDriver: true }),
      Animated.spring(forgotCardScale,   { toValue: 1, tension: 200, friction: 18, useNativeDriver: true }),
      Animated.timing(forgotCardOpacity, { toValue: 1, duration: 240, easing: Easing.out(Easing.quad), useNativeDriver: true }),
    ]).start();
  };

  const closeForgotModal = () => {
    Animated.parallel([
      Animated.timing(forgotFade,        { toValue: 0, duration: 300, easing: Easing.in(Easing.quad), useNativeDriver: true }),
      Animated.timing(forgotCardOpacity, { toValue: 0, duration: 240, easing: Easing.in(Easing.quad), useNativeDriver: true }),
      Animated.timing(forgotCardScale,   { toValue: 0.94, duration: 280, easing: Easing.in(Easing.quad), useNativeDriver: true }),
      Animated.timing(forgotSlide,       { toValue: 20,   duration: 280, easing: Easing.in(Easing.quad), useNativeDriver: true }),
    ]).start(() => {
      setShowForgotModal(false);
      setResetDni(''); setResetEmail(''); setResetError(''); setResetSuccess(false); setResetSending(false);
    });
  };

  const handleForgotPassword = async () => {
    Keyboard.dismiss();
    setResetError('');

    // ── Validación local ────────────────────────────────────────────────────
    if (!resetDni || !resetEmail) {
      setResetError('Completa todos los campos'); return;
    }
    if (resetDni.length < 8) {
      setResetError('DNI / RUC inválido'); return;
    }
    if (!/^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$/.test(resetEmail.trim())) {
      setResetError('Ingresa un correo electrónico válido'); return;
    }

    // ── Animación del botón ─────────────────────────────────────────────────
    Animated.sequence([
      Animated.timing(resetBtnScale, { toValue: 0.96, duration: 80,  useNativeDriver: true }),
      Animated.timing(resetBtnScale, { toValue: 1,    duration: 130, useNativeDriver: true }),
    ]).start();

    setResetLoading(true);
    try {
      // ── Paso 1: Verificar que el documento existe ───────────────────────
      setResetStep('Verificando documento...');
      const verifyRes  = await fetch(`${API_CONFIG.BASE_URL}/api/client/verify/${resetDni}`);
      const verifyData = await verifyRes.json();

      if (!verifyData.success || !verifyData.exists) {
        setResetError('No encontramos ninguna cuenta con este número de documento.');
        return;
      }

      // ── Paso 2: Validar correo y enviar instrucciones ───────────────────
      setResetStep('Verificando correo...');
      const res  = await fetch(`${API_CONFIG.BASE_URL}/api/client/forgot-password`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ dni: resetDni, email: resetEmail.trim().toLowerCase() }),
      });
      const data = await res.json();

      if (data.success) {
        setFailedAttempts(0);
        setResetSending(true);
        setTimeout(() => {
          setResetSending(false);
          setResetSuccess(true);
        }, 1800);
      } else {
        setResetError(
          data.message ||
          'El correo ingresado no está asociado a este número de documento.'
        );
      }
    } catch {
      setResetError('Error de conexión. Intenta nuevamente.');
    } finally {
      setResetLoading(false);
      setResetStep('');
    }
  };

  return (
    <>
      <StatusBar barStyle="light-content" translucent backgroundColor="transparent" />

      <View style={styles.bg}>
        <ScrollView
          style={styles.scrollView}
          contentContainerStyle={[styles.scroll, { paddingTop: insets.top }]}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
          keyboardDismissMode="none"
        >
          <View style={{ width: '100%', flex: 1, justifyContent: 'center' }}>

            {/* ── Back button ── */}
            <TouchableOpacity style={[styles.backBtn, { top: insets.top + 16 }]} onPress={handleGoBack} activeOpacity={0.8}>
              <Ionicons name="chevron-back" size={22} color="#ffffff" />
            </TouchableOpacity>

            {/* ── Form ── */}
            <View style={styles.formContainer}>


              <Text style={styles.screenTitle}>Inicia <Text style={{ color: '#22c55e', fontWeight: '800' }}>sesión</Text></Text>
              <Text style={styles.formTitle}>Accede a tu cuenta Qoricash</Text>

              {/* Document number */}
              <Animated.View style={[styles.inputWrap, { transform: [{ translateY: dniY }] }]}>
                <TextInput
                  label={documentType ? `Número de ${documentType}` : 'Número de documento'}
                  value={dni}
                  onChangeText={handleDniChange}
                  onFocus={() => focusField(dniY, true)}
                  onBlur={() => focusField(dniY, false)}
                  mode="outlined"
                  keyboardType="numeric"
                  maxLength={11}
                  left={<TextInput.Icon icon="card-account-details-outline" iconColor="rgba(255,255,255,0.6)" />}
                  style={styles.input}
                  outlineStyle={styles.inputOutline}
                  outlineColor={GLASS_BORDER}
                  activeOutlineColor="rgba(255,255,255,0.9)"
                  textColor="#fff"
                  theme={{ colors: { onSurfaceVariant: 'rgba(255,255,255,0.5)', background: '#000000' } }}
                />
              </Animated.View>

              {/* Password */}
              <Animated.View style={[styles.inputWrap, { transform: [{ translateY: pwY }] }]}>
                <TextInput
                  label="Contraseña"
                  value={password}
                  onChangeText={t => setPassword(t)}
                  onFocus={() => focusField(pwY, true)}
                  onBlur={() => focusField(pwY, false)}
                  mode="outlined"
                  secureTextEntry={!showPassword}
                  left={<TextInput.Icon icon="lock-outline" iconColor="rgba(255,255,255,0.6)" />}
                  right={
                    <TextInput.Icon
                      icon={showPassword ? 'eye-off-outline' : 'eye-outline'}
                      iconColor="rgba(255,255,255,0.5)"
                      onPress={() => setShowPassword(v => !v)}
                    />
                  }
                  style={styles.input}
                  outlineStyle={styles.inputOutline}
                  outlineColor={GLASS_BORDER}
                  activeOutlineColor="rgba(255,255,255,0.9)"
                  textColor="#fff"
                  theme={{ colors: { onSurfaceVariant: 'rgba(255,255,255,0.5)', background: '#000000' } }}
                />
              </Animated.View>

              {/* Remember me */}
              <TouchableOpacity
                style={styles.rememberRow}
                onPress={() => handleRememberToggle(!rememberMe)}
                activeOpacity={0.7}
              >
                <View style={[styles.checkbox, rememberMe && styles.checkboxActive]}>
                  {rememberMe && (
                    <IconButton icon="check" size={12} iconColor="#0a1a2e" style={{ margin: 0 }} />
                  )}
                </View>
                <Text style={styles.rememberText}>Recuérdame</Text>
              </TouchableOpacity>

              {/* Login button */}
              <Animated.View style={[styles.btnWrap, { transform: [{ scale: btnScale }] }]}>
                <TouchableOpacity
                  style={[styles.btn, isLocked && styles.btnLocked]}
                  onPress={handleLogin}
                  disabled={loading}
                  activeOpacity={0.88}
                >
                  {loading ? (
                    <ActivityIndicator color={isLocked ? '#6B7280' : '#0a1a2e'} size={20} />
                  ) : (
                    <Text style={[styles.btnText, isLocked && styles.btnTextLocked]}>
                      {isLocked ? 'Cuenta Bloqueada' : 'Ingresar'}
                    </Text>
                  )}
                </TouchableOpacity>
              </Animated.View>

              {/* Forgot password */}
              <TouchableOpacity
                onPress={openForgotModal}
                style={styles.forgotBtn}
                disabled={loading}
                activeOpacity={0.7}
              >
                <Text style={styles.forgotText}>¿Olvidaste tu contraseña?</Text>
              </TouchableOpacity>

            </View>

            {/* ── Register button ── */}
            <View style={styles.registerSection}>
              <Text style={styles.registerPrompt}>¿Aún no eres cliente?</Text>
              <TouchableOpacity
                style={styles.registerBtn}
                onPress={() => navigation.navigate('ClientTypeSelection' as never)}
                disabled={loading}
                activeOpacity={0.8}
              >
                <Text style={styles.registerBtnText}>Crear cuenta gratis</Text>
              </TouchableOpacity>
            </View>
          </View>
        </ScrollView>
      </View>

      {/* ── Error / auth failure modal ─────────────────────────────────────── */}
      <Modal
        visible={showErrModal}
        transparent
        animationType="fade"
        onRequestClose={() => setShowErrModal(false)}
      >
        <View style={styles.errOverlay}>
          <BlurView intensity={80} tint="dark" style={[styles.errCard, isLocked && styles.errCardLocked]}>

            <View style={styles.errIconRow}>
              <Text style={styles.errEmoji}>{isLocked ? '🔒' : '⚠️'}</Text>
            </View>

            <Text style={styles.errTitle}>
              {isLocked ? 'Cuenta Bloqueada' : 'Error de Acceso'}
            </Text>

            {errIsAuth && !isLocked && failedAttempts > 0 && (
              <View style={styles.errAttemptBox}>
                <Text style={styles.errAttemptLabel}>
                  Intento {failedAttempts} de {MAX_ATTEMPTS}
                </Text>
                <View style={styles.errDotRow}>
                  {Array.from({ length: MAX_ATTEMPTS }, (_, i) => (
                    <View key={i} style={[styles.errDot, i < failedAttempts && styles.errDotFilled]} />
                  ))}
                </View>
              </View>
            )}

            <Text style={styles.errMsg}>{errMsg}</Text>

            <View style={styles.errActions}>
              {isLocked && (
                <TouchableOpacity
                  style={styles.errBtnPrimary}
                  onPress={() => { setShowErrModal(false); openForgotModal(); }}
                >
                  <Text style={styles.errBtnPrimaryTxt}>Recuperar contraseña</Text>
                </TouchableOpacity>
              )}
              <TouchableOpacity
                style={isLocked ? styles.errBtnSecondary : styles.errBtnPrimary}
                onPress={() => setShowErrModal(false)}
              >
                <Text style={isLocked ? styles.errBtnSecondaryTxt : styles.errBtnPrimaryTxt}>
                  {isLocked ? 'Cerrar' : 'Entendido'}
                </Text>
              </TouchableOpacity>
            </View>

          </BlurView>
        </View>
      </Modal>

      {/* ── Forgot password modal ──────────────────────────────────────────── */}
      <Modal visible={showForgotModal} transparent animationType="fade" onRequestClose={closeForgotModal}>
        <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
          <Animated.View style={[StyleSheet.absoluteFill, { opacity: forgotFade }]}>
            <BlurView intensity={50} tint="dark" style={StyleSheet.absoluteFill} />
          </Animated.View>
          <TouchableOpacity style={StyleSheet.absoluteFill} activeOpacity={1} onPress={closeForgotModal} />
          <View style={styles.forgotOverlay} pointerEvents="box-none">
            <Animated.View style={[styles.forgotCard, {
              opacity: forgotCardOpacity,
              transform: [{ translateY: forgotSlide }, { scale: forgotCardScale }],
            }]}>
              <View style={styles.forgotCardBorder} />

              {resetSending ? (
                <View style={{ alignItems: 'center', paddingVertical: 24, gap: 18 }}>
                  <View style={{
                    width: 64, height: 64, borderRadius: 32,
                    backgroundColor: 'rgba(34,197,94,0.12)',
                    borderWidth: 1, borderColor: 'rgba(34,197,94,0.25)',
                    alignItems: 'center', justifyContent: 'center',
                  }}>
                    <ActivityIndicator color="#22c55e" size={28} />
                  </View>
                  <Text style={{ color: '#22c55e', fontSize: 15, fontWeight: '700', letterSpacing: 0.2 }}>
                    Enviando instrucciones...
                  </Text>
                  <Text style={{ color: 'rgba(255,255,255,0.45)', fontSize: 12, textAlign: 'center' }}>
                    Estamos enviando tu contraseña temporal
                  </Text>
                </View>
              ) : resetSuccess ? (
                <>
                  <Text style={[styles.errEmoji, { textAlign: 'center' }]}>✅</Text>
                  <Text style={[styles.errTitle, { marginTop: 8 }]}>¡Correo enviado!</Text>
                  <Text style={[styles.errMsg, { width: '100%' }]}>
                    {'Enviamos una contraseña temporal a\n'}
                    <Text style={{ fontWeight: '700', color: '#22c55e' }}>{resetEmail}</Text>
                  </Text>
                  <TouchableOpacity style={[styles.errBtnPrimary, { width: '100%' }]} onPress={closeForgotModal} activeOpacity={0.85}>
                    <Text style={styles.errBtnPrimaryTxt}>Entendido</Text>
                  </TouchableOpacity>
                </>
              ) : (
                <>
                  <Text style={styles.forgotModalTitle}>Recuperar contraseña</Text>
                  <View style={styles.forgotModalDivider} />
                  <Text style={[styles.errMsg, { marginBottom: 16 }]}>Te enviaremos acceso temporal a tu correo</Text>

                  <View style={{ gap: 14, marginBottom: 12, width: '100%' }}>
                    <TextInput
                      label="Número de documento"
                      value={resetDni}
                      onChangeText={t => { setResetDni(t.replace(/\D/g, '').slice(0, 11)); setResetError(''); }}
                      mode="outlined"
                      keyboardType="numeric"
                      maxLength={11}
                      left={<TextInput.Icon icon="card-account-details-outline" iconColor="rgba(255,255,255,0.6)" />}
                      disabled={resetLoading}
                      style={styles.input}
                      outlineStyle={styles.inputOutline}
                      outlineColor={GLASS_BORDER}
                      activeOutlineColor="rgba(255,255,255,0.9)"
                      textColor="#fff"
                      theme={{ colors: { onSurfaceVariant: 'rgba(255,255,255,0.5)', background: '#000000' } }}
                    />
                    <TextInput
                      label="Correo electrónico"
                      value={resetEmail}
                      onChangeText={t => { setResetEmail(t); setResetError(''); }}
                      mode="outlined"
                      keyboardType="email-address"
                      autoCapitalize="none"
                      left={<TextInput.Icon icon="email-outline" iconColor="rgba(255,255,255,0.6)" />}
                      disabled={resetLoading}
                      style={styles.input}
                      outlineStyle={styles.inputOutline}
                      outlineColor={GLASS_BORDER}
                      activeOutlineColor="rgba(255,255,255,0.9)"
                      textColor="#fff"
                      theme={{ colors: { onSurfaceVariant: 'rgba(255,255,255,0.5)', background: '#000000' } }}
                    />
                  </View>

                  {!!resetError && (
                    <Text style={{ color: '#f87171', fontSize: 12, textAlign: 'center', marginBottom: 8, width: '100%' }}>{resetError}</Text>
                  )}

                  <View style={[styles.errActions, { width: '100%' }]}>
                    <Animated.View style={{ transform: [{ scale: resetBtnScale }] }}>
                      <TouchableOpacity
                        style={[styles.errBtnPrimary, resetLoading && styles.errBtnSending]}
                        onPress={handleForgotPassword}
                        disabled={resetLoading}
                        activeOpacity={0.85}
                      >
                        {resetLoading ? (
                          <View style={styles.errBtnLoadingRow}>
                            <ActivityIndicator color="#fff" size={16} />
                            <Text style={styles.errBtnStepTxt}>{resetStep}</Text>
                          </View>
                        ) : (
                          <Text style={styles.errBtnPrimaryTxt}>Enviar instrucciones</Text>
                        )}
                      </TouchableOpacity>
                    </Animated.View>
                    <TouchableOpacity style={styles.errBtnSecondary} onPress={closeForgotModal} activeOpacity={0.7}>
                      <Text style={styles.errBtnSecondaryTxt}>Cancelar</Text>
                    </TouchableOpacity>
                  </View>
                </>
              )}

            </Animated.View>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </>
  );
};

const styles = StyleSheet.create({
  bg: {
    flex: 1,
  },
  scrollView: {
    flex: 1,
    backgroundColor: 'transparent',
  },
  scroll: {
    flexGrow: 1,
    paddingHorizontal: 20,
    paddingBottom: 40,
    justifyContent: 'center',
    alignItems: 'center',
  },

  // ── Títulos ───────────────────────────────────────────────────────────────
  screenTitle: {
    fontSize: 32,
    fontWeight: '800',
    color: '#ffffff',
    marginBottom: 6,
    letterSpacing: 0.2,
    textAlign: 'center',
  },
  formTitle: {
    fontSize: 15,
    fontWeight: '400',
    color: 'rgba(255,255,255,0.6)',
    marginBottom: 28,
    letterSpacing: 0.1,
    textAlign: 'center',
  },

  // ── Form container (sin fondo ni borde) ──────────────────────────────────
  backBtn: {
    position: 'absolute',
    left: 20,
    zIndex: 10,
    padding: 4,
  },
  formContainer: {
    paddingHorizontal: 4,
    marginBottom: 14,
  },
  // ── Inputs ────────────────────────────────────────────────────────────────
  inputWrap: {
    marginBottom: 14,
  },
  input: {
    backgroundColor: INPUT_BG,
  },
  inputOutline: {
    borderRadius: 14,
  },

  // ── Remember me ───────────────────────────────────────────────────────────
  rememberRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 18,
  },
  checkbox: {
    width: 20,
    height: 20,
    borderRadius: 6,
    borderWidth: 1.5,
    borderColor: GLASS_BORDER,
    backgroundColor: 'rgba(255,255,255,0.06)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  checkboxActive: {
    backgroundColor: '#fff',
    borderColor: '#fff',
  },
  rememberText: {
    fontSize: 13,
    color: 'rgba(255,255,255,0.65)',
    fontWeight: '500',
  },

  // ── Login button ──────────────────────────────────────────────────────────
  btnWrap: {
    borderRadius: 14,
    overflow: 'hidden',
    marginBottom: 14,
    shadowColor: '#fff',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 12,
    elevation: 8,
  },
  btn: {
    backgroundColor: '#ffffff',
    paddingVertical: 15,
    borderRadius: 14,
    alignItems: 'center',
  },
  btnLocked: {
    backgroundColor: 'rgba(255,255,255,0.12)',
  },
  btnText: {
    color: '#0a1a2e',
    fontSize: 16,
    fontWeight: '800',
    letterSpacing: 0.3,
  },
  btnTextLocked: {
    color: 'rgba(255,255,255,0.35)',
  },

  // ── Forgot ────────────────────────────────────────────────────────────────
  forgotBtn: {
    alignItems: 'center',
    paddingVertical: 4,
  },
  forgotText: {
    color: 'rgba(255,255,255,0.65)',
    fontSize: 13,
    fontWeight: '600',
  },

  registerSection: {
    width: '100%',
    marginTop: 60,
  },
  // ── Register button ───────────────────────────────────────────────────────
  registerPrompt: {
    color: 'rgba(255,255,255,0.45)',
    fontSize: 12,
    fontWeight: '400',
    textAlign: 'center',
    marginTop: 0,
    marginBottom: 8,
    letterSpacing: 0.3,
  },
  registerBtn: {
    backgroundColor: GLASS_BG,
    borderWidth: 1,
    borderColor: GLASS_BORDER,
    borderRadius: 14,
    paddingVertical: 14,
    alignItems: 'center',
    marginBottom: 28,
  },
  registerBtnText: {
    color: '#fff',
    fontSize: 15,
    fontWeight: '700',
    letterSpacing: 0.2,
    textAlign: 'center',
  },

  // ── Forgot password modal (glass style) ──────────────────────────────────
  forgotOverlay: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  forgotCard: {
    width: '100%',
    backgroundColor: 'rgba(255,255,255,0.15)',
    borderRadius: 28,
    overflow: 'hidden',
    paddingTop: 28,
    paddingBottom: 24,
    paddingHorizontal: 24,
    alignItems: 'center',
    shadowColor: '#22c55e',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.18,
    shadowRadius: 28,
    elevation: 20,
  },
  forgotCardBorder: {
    position: 'absolute',
    top: 0, left: 0, right: 0, bottom: 0,
    borderRadius: 28,
    borderWidth: 1,
    borderColor: 'rgba(34,197,94,0.18)',
  },
  forgotModalTitle: {
    fontSize: 17,
    fontWeight: '800',
    color: '#ffffff',
    marginBottom: 16,
    letterSpacing: 0.1,
    textAlign: 'center',
  },
  forgotModalDivider: {
    width: '100%',
    height: StyleSheet.hairlineWidth,
    backgroundColor: 'rgba(255,255,255,0.15)',
    marginBottom: 18,
  },

  // ── Error modal ───────────────────────────────────────────────────────────
  errOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.78)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  errCard: {
    borderRadius: 14,
    overflow: 'hidden',
    padding: 26,
    width: '100%',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.4)',
  },
  errCardLocked: {
    borderColor: GLASS_BORDER,
  },
  errIconRow: {
    alignItems: 'center',
    marginBottom: 14,
  },
  errEmoji: {
    fontSize: 44,
  },
  errTitle: {
    fontSize: 20,
    fontWeight: '800',
    color: '#ffffff',
    textAlign: 'center',
    marginBottom: 14,
  },
  errAttemptBox: {
    alignItems: 'center',
    marginBottom: 14,
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderRadius: 12,
    paddingVertical: 10,
    paddingHorizontal: 16,
  },
  errAttemptLabel: {
    fontSize: 12,
    color: '#B0BBC9',
    fontWeight: '600',
    marginBottom: 8,
    letterSpacing: 0.4,
  },
  errDotRow: {
    flexDirection: 'row',
    gap: 8,
  },
  errDot: {
    width: 30,
    height: 6,
    borderRadius: 3,
    backgroundColor: 'rgba(255,255,255,0.10)',
  },
  errDotFilled: {
    backgroundColor: '#f87171',
  },
  errMsg: {
    fontSize: 14,
    color: '#ffffff',
    textAlign: 'center',
    lineHeight: 22,
    marginBottom: 22,
  },
  errActions: {
    gap: 10,
  },
  errBtnPrimary: {
    backgroundColor: GLASS_BG,
    borderWidth: 1,
    borderColor: GLASS_BORDER,
    borderRadius: 14,
    paddingVertical: 14,
    alignItems: 'center',
  },
  errBtnSending: {
    backgroundColor: 'rgba(34,197,94,0.12)',
    borderColor: 'rgba(34,197,94,0.3)',
  },
  errBtnLoadingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  errBtnStepTxt: {
    color: 'rgba(255,255,255,0.75)',
    fontSize: 13,
    fontWeight: '500',
    letterSpacing: 0.2,
  },
  errBtnPrimaryTxt: {
    color: '#fff',
    fontSize: 15,
    fontWeight: '700',
    letterSpacing: 0.2,
    textAlign: 'center',
  },
  errBtnSecondary: {
    backgroundColor: GLASS_BG,
    borderWidth: 1,
    borderColor: GLASS_BORDER,
    borderRadius: 14,
    paddingVertical: 14,
    alignItems: 'center',
  },
  errBtnSecondaryTxt: {
    color: '#fff',
    fontSize: 15,
    fontWeight: '700',
    letterSpacing: 0.2,
    textAlign: 'center',
  },
});

const forgotStyles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.55)',
    justifyContent: 'flex-end',
  },
  sheet: {
    backgroundColor: '#fff',
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    maxHeight: '92%',
    overflow: 'hidden',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: -4 },
    shadowOpacity: 0.15,
    shadowRadius: 20,
    elevation: 24,
  },
  handle: {
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: '#E2E8F0',
    alignSelf: 'center',
    marginTop: 10,
    marginBottom: 4,
  },
  body: {
    paddingBottom: 36,
  },
  headerGrad: {
    paddingHorizontal: 24,
    paddingTop: 24,
    paddingBottom: 28,
    alignItems: 'center',
    gap: 8,
  },
  headerIcon: {
    width: 68,
    height: 68,
    borderRadius: 34,
    backgroundColor: 'rgba(255,255,255,0.18)',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 4,
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#fff',
    textAlign: 'center',
  },
  headerSub: {
    fontSize: 13,
    color: 'rgba(255,255,255,0.8)',
    textAlign: 'center',
  },
  inputs: {
    paddingHorizontal: 20,
    paddingTop: 20,
    gap: 4,
  },
  errorBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FEF2F2',
    borderRadius: 10,
    marginHorizontal: 20,
    marginTop: 8,
    paddingRight: 12,
    paddingVertical: 4,
    gap: 4,
  },
  errorTxt: {
    flex: 1,
    fontSize: 13,
    color: Colors.danger,
    lineHeight: 18,
  },
  infoBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F0FDF4',
    borderRadius: 10,
    marginHorizontal: 20,
    marginTop: 12,
    paddingRight: 12,
    paddingVertical: 4,
    gap: 4,
  },
  infoTxt: {
    flex: 1,
    fontSize: 13,
    color: '#166534',
    lineHeight: 18,
  },
  primaryBtn: {
    marginHorizontal: 20,
    marginTop: 20,
    borderRadius: 14,
    overflow: 'hidden',
  },
  primaryBtnGrad: {
    paddingVertical: 15,
    alignItems: 'center',
    justifyContent: 'center',
  },
  primaryBtnTxt: {
    fontSize: 16,
    fontWeight: '700',
    color: '#fff',
    letterSpacing: 0.3,
  },
  cancelLink: {
    alignItems: 'center',
    marginTop: 16,
    paddingVertical: 4,
  },
  cancelTxt: {
    fontSize: 14,
    color: Colors.textLight,
    textDecorationLine: 'underline',
  },
  successCircle: {
    width: 90,
    height: 90,
    borderRadius: 45,
    backgroundColor: Colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
    alignSelf: 'center',
    marginTop: 32,
    marginBottom: 20,
    shadowColor: Colors.primary,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.35,
    shadowRadius: 12,
    elevation: 8,
  },
  successTitle: {
    fontSize: 22,
    fontWeight: '800',
    color: Colors.textDark,
    textAlign: 'center',
    marginBottom: 8,
  },
  successSub: {
    fontSize: 14,
    color: Colors.textLight,
    textAlign: 'center',
    lineHeight: 22,
    paddingHorizontal: 28,
    marginBottom: 28,
  },
  successSteps: {
    marginHorizontal: 20,
    backgroundColor: '#F8FAFC',
    borderRadius: 16,
    paddingVertical: 8,
    paddingHorizontal: 8,
    marginBottom: 8,
    gap: 2,
  },
  stepRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingVertical: 4,
  },
  stepNumBox: {
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: Colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  stepNum: {
    fontSize: 11,
    fontWeight: '800',
    color: '#fff',
  },
  stepText: {
    flex: 1,
    fontSize: 13,
    color: Colors.textDark,
    lineHeight: 18,
  },
});
