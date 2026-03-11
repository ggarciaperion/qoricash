import React, { useState, useRef, useEffect } from 'react';
import {
  View,
  StyleSheet,
  Image,
  TouchableOpacity,
  Animated,
  StatusBar,
  Modal,
  Alert,
} from 'react-native';
import { TextInput, Text, IconButton } from 'react-native-paper';
import { LinearGradient } from 'expo-linear-gradient';
import { useNavigation } from '@react-navigation/native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useAuth } from '../contexts/AuthContext';
import { useLoginLoading } from '../contexts/LoginLoadingContext';
import { Colors } from '../constants/colors';
import { API_CONFIG } from '../constants/config';
import { KeyboardAwareScrollView } from '../components/KeyboardAwareScrollView';
import { CustomModal } from '../components/CustomModal';
import { GlobalStyles } from '../styles/globalStyles';
import { ForexBackground } from '../components/ForexBackground';

type DocumentType = 'DNI' | 'CE' | 'RUC';

const MAX_ATTEMPTS = 3;

// Solid background color for inputs — must be opaque so react-native-paper
// can cut a clean gap in the outlined border where the floating label sits.
const INPUT_BG = '#0C1C2A';

// ─── Document picker options ─────────────────────────────────────────────────
const DOC_OPTIONS: { type: DocumentType; label: string; full: string; digits: number }[] = [
  { type: 'DNI', label: 'DNI', full: 'Documento Nacional de Identidad',  digits: 8  },
  { type: 'CE',  label: 'CE',  full: 'Carnet de Extranjería',             digits: 9  },
  { type: 'RUC', label: 'RUC', full: 'Registro Único de Contribuyentes',  digits: 11 },
];

// ─── Pulsing live dot (market pill) ──────────────────────────────────────────
const PulseDot = () => {
  const scale = useRef(new Animated.Value(1)).current;
  const op    = useRef(new Animated.Value(0.9)).current;
  useEffect(() => {
    Animated.loop(
      Animated.sequence([
        Animated.parallel([
          Animated.timing(scale, { toValue: 1.9, duration: 900, useNativeDriver: true }),
          Animated.timing(op,    { toValue: 0,   duration: 900, useNativeDriver: true }),
        ]),
        Animated.delay(600),
        Animated.parallel([
          Animated.timing(scale, { toValue: 1,   duration: 0, useNativeDriver: true }),
          Animated.timing(op,    { toValue: 0.9, duration: 0, useNativeDriver: true }),
        ]),
      ])
    ).start();
  }, []);
  return (
    <View style={{ width: 10, height: 10, justifyContent: 'center', alignItems: 'center' }}>
      <Animated.View style={{
        position: 'absolute',
        width: 10, height: 10, borderRadius: 5,
        backgroundColor: '#22c55e',
        opacity: op,
        transform: [{ scale }],
      }} />
      <View style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: '#22c55e' }} />
    </View>
  );
};

// ─── Main component ───────────────────────────────────────────────────────────
export const LoginScreen = () => {
  const navigation  = useNavigation();
  const insets      = useSafeAreaInsets();
  const { login, loading } = useAuth();
  const { setShowLoginLoading } = useLoginLoading();

  const [documentType, setDocumentType] = useState<DocumentType | null>(null);
  const [dni,          setDni]          = useState('');
  const [password,     setPassword]     = useState('');
  const [showPassword, setShowPassword] = useState(false);

  // Attempt tracking
  const [failedAttempts, setFailedAttempts] = useState(0);
  const [showErrModal,   setShowErrModal]   = useState(false);
  const [errMsg,         setErrMsg]         = useState('');
  const [errIsAuth,      setErrIsAuth]      = useState(false);
  const isLocked = failedAttempts >= MAX_ATTEMPTS;

  // Document picker modal
  const [showDocPicker, setShowDocPicker] = useState(false);

  // Forgot password modal
  const [showForgotModal, setShowForgotModal] = useState(false);
  const [resetDni,        setResetDni]        = useState('');
  const [resetEmail,      setResetEmail]      = useState('');
  const [resetLoading,    setResetLoading]    = useState(false);
  const [resetError,      setResetError]      = useState('');

  // Entry animations
  const fadeAnim  = useRef(new Animated.Value(0)).current;
  const slideAnim = useRef(new Animated.Value(32)).current;
  const btnScale  = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    Animated.parallel([
      Animated.timing(fadeAnim,  { toValue: 1, duration: 700, useNativeDriver: true }),
      Animated.timing(slideAnim, { toValue: 0, duration: 700, useNativeDriver: true }),
    ]).start();
  }, []);

  const punchBtn = () => {
    Animated.sequence([
      Animated.timing(btnScale, { toValue: 0.96, duration: 80,  useNativeDriver: true }),
      Animated.timing(btnScale, { toValue: 1,    duration: 120, useNativeDriver: true }),
    ]).start();
  };

  const getDocMax = (): number => {
    switch (documentType) {
      case 'DNI': return 8;
      case 'CE':  return 9;
      case 'RUC': return 11;
      default:    return 8;
    }
  };

  const showError = (msg: string, isAuthFail = false) => {
    setErrMsg(msg);
    setErrIsAuth(isAuthFail);
    setShowErrModal(true);
  };

  const handleLogin = async () => {
    if (isLocked) {
      showError('Has superado el número máximo de intentos. Usa "¿Olvidaste tu contraseña?" para recuperar tu cuenta.');
      return;
    }
    if (!documentType) {
      showError('Selecciona un tipo de documento antes de continuar.');
      return;
    }
    if (!dni || dni.length !== getDocMax()) {
      showError(`El ${documentType} debe tener exactamente ${getDocMax()} dígitos.`);
      return;
    }
    try {
      punchBtn();
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

  const handleForgotPassword = async () => {
    try {
      setResetError('');
      if (!resetDni || !resetEmail) { setResetError('Completa todos los campos'); return; }
      if (resetDni.length < 8)      { setResetError('DNI / RUC inválido');         return; }
      if (!resetEmail.includes('@')) { setResetError('Email inválido');              return; }
      setResetLoading(true);
      const res  = await fetch(`${API_CONFIG.BASE_URL}/api/client/forgot-password`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ dni: resetDni, email: resetEmail.toLowerCase() }),
      });
      const data = await res.json();
      setResetLoading(false);
      if (data.success) {
        setShowForgotModal(false);
        setResetDni(''); setResetEmail('');
        setFailedAttempts(0);
        Alert.alert(
          'Contraseña Enviada',
          'Se envió una contraseña temporal a tu correo. Úsala para ingresar y luego cámbiala.',
          [{ text: 'OK' }]
        );
      } else {
        setResetError(data.message || 'Error al enviar la contraseña');
      }
    } catch {
      setResetLoading(false);
      setResetError('Error de conexión. Intenta nuevamente.');
    }
  };

  const selectedDoc = DOC_OPTIONS.find(o => o.type === documentType);

  return (
    <>
      {/* Translucent on Android; iOS ignores backgroundColor — both get light icons */}
      <StatusBar barStyle="light-content" translucent backgroundColor="transparent" />

      <View style={styles.root}>

        {/* ── Forex animated background ── */}
        <ForexBackground showTickers={true} />

        {/* ── Scrollable content — starts below status bar via dynamic paddingTop ── */}
        <KeyboardAwareScrollView
          style={styles.scrollView}
          contentContainerStyle={[styles.scroll, { paddingTop: insets.top + 16 }]}
        >

          {/* ── Unified card: logo + form ── */}
          <Animated.View style={[styles.card, { opacity: fadeAnim, transform: [{ translateY: slideAnim }] }]}>

            {/* Logo section */}
            <View style={styles.cardLogoSection}>
              <Image
                source={require('../../assets/logo-principal.png')}
                style={styles.logo}
                resizeMode="contain"
              />
              <Text style={styles.brandName}>QoriCash</Text>
              <Text style={styles.brandTag}>CASA DE CAMBIO DIGITAL</Text>
              <View style={styles.marketPill}>
                <PulseDot />
                <Text style={styles.marketText}>USD/PEN · En línea</Text>
              </View>
            </View>

            {/* Divider */}
            <View style={styles.cardDivider} />

            {/* Form section */}
            <View style={styles.cardForm}>

              <Text style={styles.cardTitle}>Iniciar Sesión</Text>
              <Text style={styles.cardSub}>Accede con tu documento de identidad</Text>

              {/* Document type dropdown */}
              <Text style={styles.fieldLabel}>Tipo de documento</Text>
              <TouchableOpacity
                style={[styles.docBtn, documentType && styles.docBtnSelected]}
                onPress={() => setShowDocPicker(true)}
                activeOpacity={0.8}
              >
                <View style={styles.docBtnLeft}>
                  <View style={[styles.docBtnIconWrap, documentType && styles.docBtnIconWrapActive]}>
                    <IconButton
                      icon="card-account-details-outline"
                      size={17}
                      iconColor={documentType ? Colors.primary : '#7B8FA8'}
                      style={{ margin: 0 }}
                    />
                  </View>
                  <View style={{ flex: 1 }}>
                    {documentType ? (
                      <>
                        <Text style={styles.docBtnValue}>{selectedDoc?.label}</Text>
                        <Text style={styles.docBtnHint}>{selectedDoc?.full} · {selectedDoc?.digits} dígitos</Text>
                      </>
                    ) : (
                      <Text style={styles.docBtnPlaceholder}>Seleccionar tipo de documento</Text>
                    )}
                  </View>
                </View>
                <IconButton icon="chevron-down" size={18} iconColor="#7B8FA8" style={{ margin: 0 }} />
              </TouchableOpacity>

              {/* Document number */}
              <TextInput
                label={documentType ? `Número de ${documentType}` : 'Número de documento'}
                value={dni}
                onChangeText={t => setDni(t.replace(/\D/g, '').slice(0, getDocMax()))}
                mode="outlined"
                keyboardType="numeric"
                disabled={!documentType}
                maxLength={getDocMax()}
                left={<TextInput.Icon icon="pound" iconColor={Colors.primary} />}
                style={styles.input}
                outlineStyle={styles.inputOutline}
                outlineColor="rgba(255,255,255,0.15)"
                activeOutlineColor={Colors.primary}
                textColor="#E2E8F0"
                theme={{ colors: { onSurfaceVariant: '#6B7280', background: INPUT_BG } }}
              />

              {/* Password */}
              <TextInput
                label="Contraseña"
                value={password}
                onChangeText={t => setPassword(t)}
                mode="outlined"
                secureTextEntry={!showPassword}
                left={<TextInput.Icon icon="lock-outline" iconColor={Colors.primary} />}
                right={
                  <TextInput.Icon
                    icon={showPassword ? 'eye-off-outline' : 'eye-outline'}
                    iconColor="#8A9BB5"
                    onPress={() => setShowPassword(v => !v)}
                  />
                }
                style={styles.input}
                outlineStyle={styles.inputOutline}
                outlineColor="rgba(255,255,255,0.15)"
                activeOutlineColor={Colors.primary}
                textColor="#E2E8F0"
                theme={{ colors: { onSurfaceVariant: '#6B7280', background: INPUT_BG } }}
              />

              {/* Login button */}
              <Animated.View style={[styles.btnWrap, { transform: [{ scale: btnScale }] }]}>
                <TouchableOpacity
                  onPress={handleLogin}
                  disabled={loading}
                  activeOpacity={0.9}
                >
                  <LinearGradient
                    colors={isLocked
                      ? ['#1e2d3d', '#1e2d3d']
                      : [Colors.primary, '#00c99a', Colors.primaryDark]}
                    start={{ x: 0, y: 0 }}
                    end={{ x: 1, y: 0 }}
                    style={styles.btn}
                  >
                    <Text style={[styles.btnText, isLocked && styles.btnTextLocked]}>
                      {loading ? 'Ingresando...' : isLocked ? '🔒  Cuenta Bloqueada' : 'Ingresar'}
                    </Text>
                  </LinearGradient>
                </TouchableOpacity>
              </Animated.View>

              {/* Forgot password */}
              <TouchableOpacity
                onPress={() => setShowForgotModal(true)}
                style={styles.forgotBtn}
                disabled={loading}
                activeOpacity={0.7}
              >
                <Text style={styles.forgotText}>¿Olvidaste tu contraseña?</Text>
              </TouchableOpacity>

              {/* Info hint */}
              <View style={styles.hint}>
                <IconButton icon="information-outline" size={14} iconColor={Colors.primary} style={{ margin: 0 }} />
                <Text style={styles.hintText}>
                  ¿Te registró un asesor? Usa "¿Olvidaste tu contraseña?" para obtener acceso.
                </Text>
              </View>

            </View>{/* end cardForm */}
          </Animated.View>

          {/* Footer */}
          <Animated.View style={[styles.footer, { opacity: fadeAnim }]}>
            <Text style={styles.footerTxt}>¿No tienes cuenta?</Text>
            <TouchableOpacity
              onPress={() => navigation.navigate('ClientTypeSelection' as never)}
              disabled={loading}
              activeOpacity={0.7}
            >
              <Text style={styles.footerLink}> Regístrate aquí</Text>
            </TouchableOpacity>
          </Animated.View>

        </KeyboardAwareScrollView>
      </View>

      {/* ── Document type picker modal ─────────────────────────────────────── */}
      <Modal
        visible={showDocPicker}
        transparent
        animationType="fade"
        onRequestClose={() => setShowDocPicker(false)}
      >
        <TouchableOpacity
          style={styles.pickerOverlay}
          activeOpacity={1}
          onPress={() => setShowDocPicker(false)}
        >
          <TouchableOpacity activeOpacity={1} style={styles.pickerCard}>

            <Text style={styles.pickerHeader}>Tipo de documento</Text>

            {DOC_OPTIONS.map(opt => (
              <TouchableOpacity
                key={opt.type}
                style={[styles.pickerRow, documentType === opt.type && styles.pickerRowActive]}
                onPress={() => { setDocumentType(opt.type); setDni(''); setShowDocPicker(false); }}
                activeOpacity={0.75}
              >
                <View style={[styles.pickerBadge, documentType === opt.type && styles.pickerBadgeActive]}>
                  <Text style={[styles.pickerBadgeLabel, documentType === opt.type && styles.pickerBadgeLabelActive]}>
                    {opt.label}
                  </Text>
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={[styles.pickerOptName, documentType === opt.type && styles.pickerOptNameActive]}>
                    {opt.full}
                  </Text>
                  <Text style={styles.pickerOptSub}>{opt.digits} dígitos</Text>
                </View>
                {documentType === opt.type && (
                  <IconButton icon="check-circle" size={20} iconColor={Colors.primary} style={{ margin: 0 }} />
                )}
              </TouchableOpacity>
            ))}

            <TouchableOpacity style={styles.pickerCancelRow} onPress={() => setShowDocPicker(false)}>
              <Text style={styles.pickerCancelText}>Cancelar</Text>
            </TouchableOpacity>

          </TouchableOpacity>
        </TouchableOpacity>
      </Modal>

      {/* ── Error / auth failure modal ─────────────────────────────────────── */}
      <Modal
        visible={showErrModal}
        transparent
        animationType="fade"
        onRequestClose={() => setShowErrModal(false)}
      >
        <View style={styles.errOverlay}>
          <View style={[styles.errCard, isLocked && styles.errCardLocked]}>

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
                  onPress={() => { setShowErrModal(false); setShowForgotModal(true); }}
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

          </View>
        </View>
      </Modal>

      {/* ── Forgot password modal ──────────────────────────────────────────── */}
      <CustomModal
        visible={showForgotModal}
        onDismiss={() => { setShowForgotModal(false); setResetDni(''); setResetEmail(''); setResetError(''); }}
        title="Recuperar Contraseña"
        actions={[
          {
            label: 'Cancelar',
            onPress: () => { setShowForgotModal(false); setResetDni(''); setResetEmail(''); setResetError(''); },
            disabled: resetLoading,
          },
          {
            label: 'Enviar Instrucciones',
            onPress: handleForgotPassword,
            primary: true,
            disabled: resetLoading,
            loading: resetLoading,
          },
        ]}
      >
        <View style={{ alignItems: 'center', marginBottom: 20 }}>
          <View style={{
            width: 80, height: 80, borderRadius: 40,
            backgroundColor: Colors.primaryLight + '20',
            justifyContent: 'center', alignItems: 'center', marginBottom: 16,
          }}>
            <IconButton icon="lock-reset" size={40} iconColor={Colors.primary} style={{ margin: 0 }} />
          </View>
          <Text variant="bodyLarge" style={{ textAlign: 'center', color: Colors.textDark, marginBottom: 8, fontWeight: '600' }}>
            ¿Olvidaste tu contraseña?
          </Text>
          <Text variant="bodyMedium" style={{ textAlign: 'center', color: Colors.textLight, lineHeight: 22 }}>
            No te preocupes. Ingresa tus datos y te enviaremos instrucciones para recuperar tu cuenta.
          </Text>
        </View>

        <View style={{ marginBottom: 8 }}>
          <TextInput
            label="DNI / CE / RUC"
            value={resetDni}
            onChangeText={t => { setResetDni(t); setResetError(''); }}
            mode="outlined"
            keyboardType="numeric"
            style={GlobalStyles.input}
            left={<TextInput.Icon icon="card-account-details" />}
            disabled={resetLoading}
          />
          <TextInput
            label="Correo Electrónico"
            value={resetEmail}
            onChangeText={t => { setResetEmail(t); setResetError(''); }}
            mode="outlined"
            keyboardType="email-address"
            autoCapitalize="none"
            style={GlobalStyles.input}
            left={<TextInput.Icon icon="email" />}
            disabled={resetLoading}
          />
        </View>

        {resetError ? (
          <Text style={{ color: Colors.danger, fontSize: 13, marginTop: 4, marginBottom: 8 }}>
            {resetError}
          </Text>
        ) : null}

        <View style={{ backgroundColor: '#E7F3FF', padding: 12, borderRadius: 8, marginTop: 8, flexDirection: 'row', alignItems: 'flex-start' }}>
          <IconButton icon="information" size={20} iconColor="#2196F3" style={{ margin: 0, marginRight: 8 }} />
          <Text variant="bodySmall" style={{ flex: 1, color: '#1976D2', lineHeight: 18 }}>
            Recibirás un correo con una contraseña temporal. Podrás cambiarla después de iniciar sesión.
          </Text>
        </View>
      </CustomModal>
    </>
  );
};

const styles = StyleSheet.create({
  // position:absolute fills the entire screen (y=0) including behind the iOS status bar,
  // preventing the white mobileContainer bleed-through that causes the "cut" effect.
  root: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: '#0B1620',
  },
  // Transparent so the ForexBackground gradient shows through
  scrollView: {
    flex: 1,
    backgroundColor: 'transparent',
  },
  scroll: {
    flexGrow: 1,
    paddingHorizontal: 20,
    // paddingTop is set dynamically via insets.top + 16
    paddingBottom: 36,
  },

  // ── Unified card ──────────────────────────────────────────────────────────
  card: {
    backgroundColor: 'rgba(11,22,32,0.92)',
    borderWidth: 1,
    borderColor: 'rgba(0,222,168,0.18)',
    borderRadius: 28,
    overflow: 'hidden',
    marginBottom: 20,
    shadowColor: '#22c55e',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.12,
    shadowRadius: 28,
    elevation: 10,
  },

  // ── Logo section ──────────────────────────────────────────────────────────
  cardLogoSection: {
    alignItems: 'center',
    paddingTop: 32,
    paddingBottom: 24,
    paddingHorizontal: 24,
    backgroundColor: 'rgba(0,222,168,0.04)',
  },
  logo: {
    width: 100,
    height: 66,
    marginBottom: 10,
  },
  brandName: {
    fontSize: 30,
    fontWeight: '800',
    color: '#F1F5F9',
    letterSpacing: 0.4,
    marginBottom: 2,
  },
  brandTag: {
    fontSize: 10,
    fontWeight: '700',
    color: Colors.primary,
    letterSpacing: 3,
    textTransform: 'uppercase',
    marginBottom: 16,
    opacity: 0.85,
  },
  marketPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: 'rgba(255,255,255,0.05)',
    borderWidth: 1,
    borderColor: 'rgba(0,222,168,0.20)',
    borderRadius: 20,
    paddingHorizontal: 14,
    paddingVertical: 7,
  },
  marketText: {
    fontSize: 12,
    color: '#B0BBC9',
    fontWeight: '600',
    letterSpacing: 0.4,
  },

  // ── Divider ───────────────────────────────────────────────────────────────
  cardDivider: {
    height: 1,
    backgroundColor: 'rgba(0,222,168,0.12)',
  },

  // ── Form section ──────────────────────────────────────────────────────────
  cardForm: {
    paddingHorizontal: 24,
    paddingTop: 22,
    paddingBottom: 24,
  },
  cardTitle: {
    fontSize: 20,
    fontWeight: '800',
    color: '#F1F5F9',
    textAlign: 'center',
    marginBottom: 4,
    letterSpacing: 0.2,
  },
  cardSub: {
    fontSize: 13,
    color: '#94A3B8',
    textAlign: 'center',
    marginBottom: 22,
  },

  // ── Field label ───────────────────────────────────────────────────────────
  fieldLabel: {
    fontSize: 11,
    color: '#7B8FA8',
    fontWeight: '700',
    letterSpacing: 1,
    textTransform: 'uppercase',
    marginBottom: 8,
  },

  // ── Document picker button ────────────────────────────────────────────────
  docBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: INPUT_BG,
    borderWidth: 1.5,
    borderColor: 'rgba(255,255,255,0.15)',
    borderRadius: 14,
    paddingVertical: 8,
    paddingLeft: 4,
    paddingRight: 0,
    marginBottom: 16,
    minHeight: 56,
  },
  docBtnSelected: {
    borderColor: 'rgba(0,222,168,0.40)',
    backgroundColor: '#0C1F2E',
  },
  docBtnLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  docBtnIconWrap: {
    width: 36,
    height: 36,
    borderRadius: 10,
    backgroundColor: 'rgba(255,255,255,0.05)',
    justifyContent: 'center',
    alignItems: 'center',
    marginLeft: 8,
    marginRight: 10,
  },
  docBtnIconWrapActive: {
    backgroundColor: 'rgba(0,222,168,0.12)',
  },
  docBtnValue: {
    fontSize: 15,
    fontWeight: '700',
    color: Colors.primary,
    marginBottom: 1,
  },
  docBtnHint: {
    fontSize: 11,
    color: '#7B8FA8',
  },
  docBtnPlaceholder: {
    fontSize: 14,
    color: '#8A9BB5',
  },

  // ── Inputs (opaque bg so the floating label gap renders correctly) ─────────
  input: {
    backgroundColor: INPUT_BG,
    marginBottom: 14,
  },
  inputOutline: {
    borderRadius: 14,
  },

  // ── Login button ──────────────────────────────────────────────────────────
  btnWrap: {
    borderRadius: 14,
    overflow: 'hidden',
    marginTop: 4,
    marginBottom: 14,
    shadowColor: Colors.primary,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.28,
    shadowRadius: 14,
    elevation: 10,
  },
  btn: {
    paddingVertical: 16,
    alignItems: 'center',
    borderRadius: 14,
  },
  btnText: {
    color: '#0B1620',
    fontSize: 16,
    fontWeight: '800',
    letterSpacing: 0.3,
  },
  btnTextLocked: {
    color: '#6B7280',
  },

  // ── Forgot / hint ─────────────────────────────────────────────────────────
  forgotBtn: {
    alignItems: 'center',
    paddingVertical: 6,
    marginBottom: 16,
  },
  forgotText: {
    color: Colors.primary,
    fontSize: 14,
    fontWeight: '600',
  },
  hint: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(0,222,168,0.05)',
    borderWidth: 1,
    borderColor: 'rgba(0,222,168,0.12)',
    borderRadius: 12,
    paddingVertical: 8,
    paddingHorizontal: 8,
  },
  hintText: {
    flex: 1,
    fontSize: 11.5,
    color: '#8A9BB5',
    lineHeight: 17,
  },

  // ── Footer ────────────────────────────────────────────────────────────────
  footer: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    paddingBottom: 8,
  },
  footerTxt: {
    fontSize: 14,
    color: '#94A3B8',
  },
  footerLink: {
    fontSize: 14,
    color: Colors.primary,
    fontWeight: '700',
  },

  // ── Document picker modal ─────────────────────────────────────────────────
  pickerOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.72)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  pickerCard: {
    backgroundColor: '#0F1E2B',
    borderRadius: 22,
    width: '100%',
    borderWidth: 1,
    borderColor: 'rgba(0,222,168,0.16)',
    shadowColor: '#22c55e',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.12,
    shadowRadius: 24,
    elevation: 12,
    overflow: 'hidden',
  },
  pickerHeader: {
    fontSize: 11,
    fontWeight: '800',
    color: '#7B8FA8',
    letterSpacing: 1.5,
    textTransform: 'uppercase',
    textAlign: 'center',
    paddingVertical: 16,
    paddingHorizontal: 20,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255,255,255,0.06)',
  },
  pickerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 14,
    paddingHorizontal: 16,
    gap: 14,
    borderRadius: 14,
    marginHorizontal: 6,
    marginTop: 4,
  },
  pickerRowActive: {
    backgroundColor: 'rgba(0,222,168,0.08)',
  },
  pickerBadge: {
    width: 46,
    height: 46,
    borderRadius: 13,
    backgroundColor: 'rgba(255,255,255,0.05)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.10)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  pickerBadgeActive: {
    backgroundColor: 'rgba(0,222,168,0.12)',
    borderColor: Colors.primary,
  },
  pickerBadgeLabel: {
    fontSize: 13,
    fontWeight: '800',
    color: '#8A9BB5',
  },
  pickerBadgeLabelActive: {
    color: Colors.primary,
  },
  pickerOptName: {
    fontSize: 14,
    fontWeight: '600',
    color: '#B0BBC9',
    marginBottom: 2,
  },
  pickerOptNameActive: {
    color: '#F1F5F9',
  },
  pickerOptSub: {
    fontSize: 11,
    color: '#7B8FA8',
  },
  pickerCancelRow: {
    alignItems: 'center',
    paddingVertical: 16,
    marginTop: 6,
    borderTopWidth: 1,
    borderTopColor: 'rgba(255,255,255,0.06)',
  },
  pickerCancelText: {
    fontSize: 15,
    color: '#8A9BB5',
    fontWeight: '600',
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
    backgroundColor: '#0F1E2B',
    borderRadius: 22,
    padding: 26,
    width: '100%',
    borderWidth: 1.5,
    borderColor: 'rgba(251,113,133,0.35)',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.45,
    shadowRadius: 24,
    elevation: 14,
  },
  errCardLocked: {
    borderColor: 'rgba(239,68,68,0.50)',
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
    color: '#F1F5F9',
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
    color: '#B0BBC9',
    textAlign: 'center',
    lineHeight: 22,
    marginBottom: 22,
  },
  errActions: {
    gap: 10,
  },
  errBtnPrimary: {
    backgroundColor: Colors.primary,
    borderRadius: 13,
    paddingVertical: 14,
    alignItems: 'center',
  },
  errBtnPrimaryTxt: {
    color: '#0B1620',
    fontSize: 15,
    fontWeight: '800',
  },
  errBtnSecondary: {
    backgroundColor: 'rgba(255,255,255,0.06)',
    borderRadius: 13,
    paddingVertical: 14,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.10)',
  },
  errBtnSecondaryTxt: {
    color: '#B0BBC9',
    fontSize: 15,
    fontWeight: '600',
  },
});
