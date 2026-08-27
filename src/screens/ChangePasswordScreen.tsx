import React, { useState, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  TextInput,
  Animated,
  Easing,
  ImageBackground,
  StatusBar,
  Platform,
  ScrollView,
  KeyboardAvoidingView,
  Keyboard,
} from 'react-native';
import { BlurView } from 'expo-blur';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';
import axios from 'axios';
import { API_CONFIG, STORAGE_KEYS } from '../constants/config';
import { useAuth } from '../contexts/AuthContext';
import { useNavigation } from '@react-navigation/native';

const BG    = require('../../assets/lo.png');
const GREEN = '#22c55e';

interface Props {
  route?: { params?: { isFirstLogin?: boolean; dni?: string } };
}

export const ChangePasswordScreen: React.FC<Props> = ({ route }) => {
  const navigation   = useNavigation();
  const insets       = useSafeAreaInsets();
  const { client, logout } = useAuth();
  const isFirstLogin = route?.params?.isFirstLogin ?? false;
  const clientDni    = route?.params?.dni || client?.dni || '';

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword,     setNewPassword]     = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showCurrent,     setShowCurrent]     = useState(false);
  const [showNew,         setShowNew]         = useState(false);
  const [showConfirm,     setShowConfirm]     = useState(false);
  const [error,           setError]           = useState('');
  const [loading,         setLoading]         = useState(false);
  const [showSuccess,     setShowSuccess]     = useState(false);

  // ── Animación de éxito ─────────────────────────────────────────────────────
  const overlayFade  = useRef(new Animated.Value(0)).current;
  const spinValue    = useRef(new Animated.Value(0)).current;
  const spinOpacity  = useRef(new Animated.Value(1)).current;
  const circleScale  = useRef(new Animated.Value(0)).current;
  const checkScale   = useRef(new Animated.Value(0)).current;
  const checkOpacity = useRef(new Animated.Value(0)).current;
  const titleOpacity = useRef(new Animated.Value(0)).current;
  const titleSlide   = useRef(new Animated.Value(16)).current;
  const spinnerLoop  = useRef<Animated.CompositeAnimation | null>(null);

  const showSuccessAnimation = () => {
    setShowSuccess(true);
    overlayFade.setValue(0);  spinValue.setValue(0);   spinOpacity.setValue(1);
    circleScale.setValue(0);  checkScale.setValue(0);  checkOpacity.setValue(0);
    titleOpacity.setValue(0); titleSlide.setValue(16);

    // ① Overlay negro entra
    Animated.timing(overlayFade, {
      toValue: 1, duration: 300, easing: Easing.out(Easing.quad), useNativeDriver: true,
    }).start(() => {

      // ② Spinner gira
      spinnerLoop.current = Animated.loop(
        Animated.timing(spinValue, { toValue: 1, duration: 820, easing: Easing.linear, useNativeDriver: true })
      );
      spinnerLoop.current.start();

      // ③ Tras 1.4s: spinner fade → check
      setTimeout(() => {
        spinnerLoop.current?.stop();
        Animated.timing(spinOpacity, { toValue: 0, duration: 220, useNativeDriver: true }).start(() => {

          // ④ Círculo verde
          Animated.spring(circleScale, { toValue: 1, tension: 220, friction: 9, useNativeDriver: true }).start(() => {

            // ⑤ Check con bounce
            Animated.parallel([
              Animated.spring(checkScale,   { toValue: 1, tension: 280, friction: 8, useNativeDriver: true }),
              Animated.timing(checkOpacity, { toValue: 1, duration: 140, useNativeDriver: true }),
            ]).start();

            // ⑥ Título sube
            setTimeout(() => {
              Animated.parallel([
                Animated.timing(titleOpacity, { toValue: 1, duration: 320, useNativeDriver: true }),
                Animated.spring(titleSlide,   { toValue: 0, tension: 280, friction: 22, useNativeDriver: true }),
              ]).start();

              // ⑦ Navegar tras mostrar el check 1.6s
              setTimeout(async () => {
                if (isFirstLogin) {
                  await logout();
                } else {
                  navigation.goBack();
                }
              }, 1600);
            }, 220);
          });
        });
      }, 1400);
    });
  };

  const validate = () => {
    if (!isFirstLogin && !currentPassword) {
      setError('Ingresa tu contraseña actual'); return false;
    }
    if (!newPassword) {
      setError('Ingresa una nueva contraseña'); return false;
    }
    if (newPassword.length < 8) {
      setError('La contraseña debe tener al menos 8 caracteres'); return false;
    }
    if (!isFirstLogin && newPassword === currentPassword) {
      setError('La nueva contraseña no puede ser igual a la contraseña actual'); return false;
    }
    if (newPassword !== confirmPassword) {
      setError('Las contraseñas no coinciden'); return false;
    }
    return true;
  };

  const handleSubmit = async () => {
    Keyboard.dismiss();
    setError('');
    if (!validate()) return;
    setLoading(true);
    try {
      const res = await axios.post(`${API_CONFIG.BASE_URL}/api/client/change-password`, {
        dni:              clientDni,
        current_password: currentPassword,
        new_password:     newPassword,
      });
      if (res.data.success) {
        await AsyncStorage.removeItem(STORAGE_KEYS.REQUIRES_PASSWORD_CHANGE);
        showSuccessAnimation();
      } else {
        setError(res.data.message || 'Error al cambiar contraseña');
      }
    } catch (err: any) {
      setError(err.response?.data?.message || err.message || 'Error al cambiar contraseña');
    } finally {
      setLoading(false);
    }
  };

  const spin = spinValue.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '360deg'] });

  return (
    <ImageBackground source={BG} style={s.root} resizeMode="cover">
      <StatusBar barStyle="light-content" translucent backgroundColor="transparent" />

      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView
          contentContainerStyle={[s.scroll, { paddingTop: insets.top + 24, paddingBottom: insets.bottom + 40 }]}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >

          {/* ── Back button (solo si no es primer login) ── */}
          {!isFirstLogin && (
            <TouchableOpacity
              style={[s.backBtn, { top: insets.top + 16 }]}
              onPress={() => navigation.goBack()}
              activeOpacity={0.8}
            >
              <Ionicons name="chevron-back" size={22} color="#ffffff" />
            </TouchableOpacity>
          )}

          {/* ── Header ── */}
          <View style={s.header}>
            <View style={s.lockIconWrap}>
              <Ionicons name="lock-closed" size={28} color={GREEN} />
            </View>
            <Text style={s.screenTitle}>
              {isFirstLogin ? 'Crear Nueva ' : 'Cambiar '}
              <Text style={{ color: GREEN }}>Contraseña</Text>
            </Text>
            <Text style={s.screenSubtitle}>
              {isFirstLogin
                ? 'Por seguridad, crea una contraseña\npersonal para tu cuenta.'
                : 'Ingresa tu contraseña actual y la nueva\nque deseas usar.'}
            </Text>
          </View>

          {/* ── Glass card ── */}
          <BlurView intensity={40} tint="dark" style={s.card}>

            {isFirstLogin && (
              <View style={s.infoBox}>
                <Ionicons name="shield-checkmark-outline" size={14} color={GREEN} />
                <Text style={s.infoText}>Tu contraseña debe tener al menos 8 caracteres</Text>
              </View>
            )}

            {!isFirstLogin && (
              <TouchableOpacity style={s.inputBox} activeOpacity={1}>
                <Text style={s.inputLabel}>Contraseña actual</Text>
                <View style={s.inputRow}>
                  <TextInput
                    style={[s.inputValue, { flex: 1 }]}
                    value={currentPassword}
                    onChangeText={t => { setCurrentPassword(t); setError(''); }}
                    secureTextEntry={!showCurrent}
                    autoCapitalize="none"
                    placeholderTextColor="rgba(255,255,255,0.2)"
                    selectionColor={GREEN}
                  />
                  <TouchableOpacity onPress={() => setShowCurrent(v => !v)} style={s.eyeBtn}>
                    <Ionicons name={showCurrent ? 'eye-off-outline' : 'eye-outline'} size={20} color="rgba(255,255,255,0.5)" />
                  </TouchableOpacity>
                </View>
              </TouchableOpacity>
            )}

            <TouchableOpacity style={s.inputBox} activeOpacity={1}>
              <Text style={s.inputLabel}>Nueva contraseña</Text>
              <View style={s.inputRow}>
                <TextInput
                  style={[s.inputValue, { flex: 1 }]}
                  value={newPassword}
                  onChangeText={t => { setNewPassword(t); setError(''); }}
                  secureTextEntry={!showNew}
                  autoCapitalize="none"
                  placeholderTextColor="rgba(255,255,255,0.2)"
                  selectionColor={GREEN}
                />
                <TouchableOpacity onPress={() => setShowNew(v => !v)} style={s.eyeBtn}>
                  <Ionicons name={showNew ? 'eye-off-outline' : 'eye-outline'} size={20} color="rgba(255,255,255,0.5)" />
                </TouchableOpacity>
              </View>
            </TouchableOpacity>

            <TouchableOpacity style={s.inputBox} activeOpacity={1}>
              <Text style={s.inputLabel}>Confirmar contraseña</Text>
              <View style={s.inputRow}>
                <TextInput
                  style={[s.inputValue, { flex: 1 }]}
                  value={confirmPassword}
                  onChangeText={t => { setConfirmPassword(t); setError(''); }}
                  secureTextEntry={!showConfirm}
                  autoCapitalize="none"
                  placeholderTextColor="rgba(255,255,255,0.2)"
                  selectionColor={GREEN}
                />
                <TouchableOpacity onPress={() => setShowConfirm(v => !v)} style={s.eyeBtn}>
                  <Ionicons name={showConfirm ? 'eye-off-outline' : 'eye-outline'} size={20} color="rgba(255,255,255,0.5)" />
                </TouchableOpacity>
              </View>
            </TouchableOpacity>

            {!!error && <Text style={s.errorText}>{error}</Text>}

            <View style={s.divider} />

            <TouchableOpacity
              style={[s.submitBtn, loading && { opacity: 0.6 }]}
              onPress={handleSubmit}
              disabled={loading}
              activeOpacity={0.8}
            >
              <Text style={s.submitBtnText}>
                {loading
                  ? 'Guardando...'
                  : isFirstLogin ? 'Crear Contraseña' : 'Cambiar Contraseña'}
              </Text>
            </TouchableOpacity>

            {!isFirstLogin && (
              <TouchableOpacity style={s.cancelBtn} onPress={() => navigation.goBack()} activeOpacity={0.7}>
                <Text style={s.cancelBtnText}>Cancelar</Text>
              </TouchableOpacity>
            )}

          </BlurView>

        </ScrollView>
      </KeyboardAvoidingView>

      {/* ── Overlay de éxito ────────────────────────────────────────────────── */}
      {showSuccess && (
        <Animated.View style={[s.successOverlay, { opacity: overlayFade }]}>

          <View style={s.successIconZone}>
            <Animated.View style={[s.spinTrack, { opacity: spinOpacity }]} />
            <Animated.View style={[s.spinArc,  { opacity: spinOpacity, transform: [{ rotate: spin }] }]} />
            <Animated.View style={[s.successCircle, { transform: [{ scale: circleScale }] }]}>
              <View style={s.successRing} />
              <Animated.View style={{ transform: [{ scale: checkScale }], opacity: checkOpacity }}>
                <Ionicons name="checkmark" size={44} color="#ffffff" />
              </Animated.View>
            </Animated.View>
          </View>

          <Animated.Text style={[s.successTitle, { opacity: titleOpacity, transform: [{ translateY: titleSlide }] }]}>
            {isFirstLogin ? '¡Contraseña creada!' : '¡Contraseña actualizada!'}
          </Animated.Text>

          <Animated.Text style={[s.successSubtitle, { opacity: titleOpacity }]}>
            {isFirstLogin ? 'Redirigiendo al inicio de sesión...' : 'Volviendo...'}
          </Animated.Text>

        </Animated.View>
      )}
    </ImageBackground>
  );
};

export default ChangePasswordScreen;

const s = StyleSheet.create({
  root: { flex: 1 },

  scroll: {
    flexGrow: 1,
    justifyContent: 'center',
    paddingHorizontal: 20,
  },

  // Back
  backBtn: {
    position: 'absolute',
    left: 20,
    zIndex: 10,
    padding: 4,
  },

  // Header
  header: {
    alignItems: 'center',
    marginBottom: 28,
    paddingHorizontal: 8,
  },
  lockIconWrap: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: 'rgba(34,197,94,0.12)',
    borderWidth: 1,
    borderColor: 'rgba(34,197,94,0.25)',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 18,
    shadowColor: GREEN,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.3,
    shadowRadius: 18,
    elevation: 8,
  },
  screenTitle: {
    fontSize: 28,
    fontWeight: '800',
    color: '#ffffff',
    textAlign: 'center',
    marginBottom: 10,
    letterSpacing: -0.3,
  },
  screenSubtitle: {
    fontSize: 14,
    color: 'rgba(255,255,255,0.55)',
    textAlign: 'center',
    lineHeight: 21,
  },

  // Card
  card: {
    borderRadius: 24,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.18)',
    paddingTop: 20,
  },

  // Info box
  infoBox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginHorizontal: 16,
    marginBottom: 16,
    backgroundColor: 'rgba(34,197,94,0.08)',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: 'rgba(34,197,94,0.2)',
    paddingVertical: 10,
    paddingHorizontal: 12,
  },
  infoText: {
    flex: 1,
    fontSize: 12.5,
    color: 'rgba(255,255,255,0.7)',
    lineHeight: 18,
  },

  // Inputs
  inputBox: {
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.25)',
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingTop: 8,
    paddingBottom: 10,
    marginBottom: 12,
    marginHorizontal: 16,
  },
  inputLabel: {
    fontSize: 10,
    color: 'rgba(255,255,255,0.55)',
    fontWeight: '600',
    marginBottom: 4,
    letterSpacing: 0.2,
  },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  inputValue: {
    fontSize: 15,
    color: '#ffffff',
    fontWeight: '500',
    padding: 0,
  },
  eyeBtn: {
    padding: 4,
  },

  // Error
  errorText: {
    fontSize: 12,
    color: '#f87171',
    textAlign: 'center',
    marginHorizontal: 16,
    marginBottom: 8,
  },

  // Divider + buttons
  divider: {
    height: 1,
    backgroundColor: 'rgba(255,255,255,0.12)',
    marginTop: 4,
  },
  submitBtn: {
    paddingVertical: 18,
    alignItems: 'center',
  },
  submitBtnText: {
    fontSize: 16,
    fontWeight: '700',
    color: '#ffffff',
    letterSpacing: 0.3,
  },
  cancelBtn: {
    alignItems: 'center',
    paddingVertical: 14,
    borderTopWidth: 1,
    borderTopColor: 'rgba(255,255,255,0.08)',
  },
  cancelBtnText: {
    fontSize: 14,
    color: 'rgba(255,255,255,0.38)',
    fontWeight: '500',
  },

  // ── Success overlay ──
  successOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: '#000000',
    justifyContent: 'center',
    alignItems: 'center',
    zIndex: 100,
    paddingHorizontal: 32,
  },
  successIconZone: {
    width: 92,
    height: 92,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 32,
  },
  spinTrack: {
    position: 'absolute',
    width: 92,
    height: 92,
    borderRadius: 46,
    borderWidth: 2.5,
    borderColor: 'rgba(255,255,255,0.08)',
  },
  spinArc: {
    position: 'absolute',
    width: 92,
    height: 92,
    borderRadius: 46,
    borderWidth: 2.5,
    borderTopColor: GREEN,
    borderRightColor: 'rgba(34,197,94,0.3)',
    borderBottomColor: 'transparent',
    borderLeftColor: 'transparent',
  },
  successCircle: {
    position: 'absolute',
    width: 82,
    height: 82,
    borderRadius: 41,
    backgroundColor: GREEN,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: GREEN,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.6,
    shadowRadius: 22,
    elevation: 12,
  },
  successRing: {
    position: 'absolute',
    width: 102,
    height: 102,
    borderRadius: 51,
    borderWidth: 1,
    borderColor: 'rgba(34,197,94,0.2)',
  },
  successTitle: {
    fontSize: 26,
    fontWeight: '800',
    color: '#ffffff',
    textAlign: 'center',
    letterSpacing: 0.1,
    marginBottom: 10,
  },
  successSubtitle: {
    fontSize: 13,
    color: 'rgba(255,255,255,0.38)',
    textAlign: 'center',
    letterSpacing: 0.3,
  },
});
