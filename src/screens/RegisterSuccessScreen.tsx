import React, { useRef, useEffect } from 'react';
import { View, StyleSheet, Animated, Image } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation, CommonActions } from '@react-navigation/native';
import { createAudioPlayer } from 'expo-audio';

const easeOut      = (t: number) => 1 - (1 - t) * (1 - t);
const easeOutCubic = (t: number) => 1 - Math.pow(1 - t, 3);

export const RegisterSuccessScreen = () => {
  const navigation = useNavigation();

  // Entrada de pantalla
  const screenFade  = useRef(new Animated.Value(0)).current;
  // Overlay negro para salida limpia (tapa la playa)
  const blackFade   = useRef(new Animated.Value(0)).current;

  // Logo
  const logoOpacity = useRef(new Animated.Value(0)).current;
  const logoY       = useRef(new Animated.Value(14)).current;

  // Spinner
  const spinOpacity = useRef(new Animated.Value(0)).current;
  const spinValue   = useRef(new Animated.Value(0)).current;
  const spinnerLoop = useRef<Animated.CompositeAnimation | null>(null);

  // Círculo del check
  const circleScale = useRef(new Animated.Value(0)).current;
  const circleOp    = useRef(new Animated.Value(0)).current;

  // Ripple
  const rippleScale = useRef(new Animated.Value(0.6)).current;
  const rippleOp    = useRef(new Animated.Value(0)).current;

  // Check
  const checkScale  = useRef(new Animated.Value(0.3)).current;
  const checkOp     = useRef(new Animated.Value(0)).current;

  // Textos
  const titleOp     = useRef(new Animated.Value(0)).current;
  const titleY      = useRef(new Animated.Value(14)).current;
  const subOp       = useRef(new Animated.Value(0)).current;
  const subY        = useRef(new Animated.Value(10)).current;

  useEffect(() => {
    // ① Pantalla hace fade in
    Animated.timing(screenFade, { toValue: 1, duration: 400, easing: easeOut, useNativeDriver: true }).start();

    // ② Logo entra suave
    setTimeout(() => {
      Animated.parallel([
        Animated.timing(logoOpacity, { toValue: 1, duration: 480, easing: easeOut, useNativeDriver: true }),
        Animated.timing(logoY,       { toValue: 0, duration: 480, easing: easeOut, useNativeDriver: true }),
      ]).start();
    }, 200);

    // ③ Spinner aparece y gira
    setTimeout(() => {
      Animated.timing(spinOpacity, { toValue: 1, duration: 300, useNativeDriver: true }).start();
      spinnerLoop.current = Animated.loop(
        Animated.timing(spinValue, { toValue: 1, duration: 850, easing: (t: number) => t, useNativeDriver: true })
      );
      spinnerLoop.current.start();
    }, 550);

    // ④ Spinner → check
    setTimeout(() => {
      spinnerLoop.current?.stop();
      Animated.timing(spinOpacity, { toValue: 0, duration: 280, easing: easeOut, useNativeDriver: true }).start(() => {
        try {
          const player = createAudioPlayer(require('../../assets/sounds/payment_success.mp3'));
          player.volume = 0.7;
          player.play();
        } catch {}

        Animated.parallel([
          Animated.spring(circleScale, { toValue: 1, tension: 130, friction: 12, useNativeDriver: true }),
          Animated.timing(circleOp,    { toValue: 1, duration: 200, useNativeDriver: true }),
        ]).start();

        setTimeout(() => {
          rippleOp.setValue(0.55);
          Animated.parallel([
            Animated.timing(rippleScale, { toValue: 2.0, duration: 680, easing: easeOutCubic, useNativeDriver: true }),
            Animated.timing(rippleOp,    { toValue: 0,   duration: 680, easing: easeOutCubic, useNativeDriver: true }),
          ]).start();
        }, 140);

        setTimeout(() => {
          Animated.parallel([
            Animated.spring(checkScale, { toValue: 1, tension: 180, friction: 9, useNativeDriver: true }),
            Animated.timing(checkOp,    { toValue: 1, duration: 200, useNativeDriver: true }),
          ]).start();
        }, 220);
      });
    }, 1900);

    // ⑤ Título
    setTimeout(() => {
      Animated.parallel([
        Animated.timing(titleOp, { toValue: 1, duration: 420, easing: easeOut, useNativeDriver: true }),
        Animated.timing(titleY,  { toValue: 0, duration: 420, easing: easeOut, useNativeDriver: true }),
      ]).start();
    }, 2500);

    // ⑥ Subtítulo
    setTimeout(() => {
      Animated.parallel([
        Animated.timing(subOp, { toValue: 1, duration: 400, easing: easeOut, useNativeDriver: true }),
        Animated.timing(subY,  { toValue: 0, duration: 400, easing: easeOut, useNativeDriver: true }),
      ]).start();
    }, 2780);

    // ⑦ Overlay negro tapa todo → navega a Login (sin ver la playa)
    setTimeout(() => {
      Animated.timing(blackFade, { toValue: 1, duration: 420, easing: easeOut, useNativeDriver: true }).start(() => {
        navigation.dispatch(
          CommonActions.reset({ index: 0, routes: [{ name: 'Login' }] })
        );
      });
    }, 4200);
  }, []);

  const spin = spinValue.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '360deg'] });

  return (
    <View style={s.container}>
      {/* Contenido principal */}
      <Animated.View style={[StyleSheet.absoluteFill, s.content, { opacity: screenFade }]}>

        <Animated.Image
          source={require('../../assets/qc.png')}
          style={[s.logo, { opacity: logoOpacity, transform: [{ translateY: logoY }] }]}
          resizeMode="contain"
        />

        <View style={s.iconZone}>
          <Animated.View style={[s.spinTrack, { opacity: spinOpacity }]} />
          <Animated.View style={[s.spinArc, { opacity: spinOpacity, transform: [{ rotate: spin }] }]} />
          <Animated.View style={[s.ripple, { opacity: rippleOp, transform: [{ scale: rippleScale }] }]} />
          <Animated.View style={[s.circle, { opacity: circleOp, transform: [{ scale: circleScale }] }]}>
            <Animated.View style={{ opacity: checkOp, transform: [{ scale: checkScale }] }}>
              <Ionicons name="checkmark" size={42} color="#fff" />
            </Animated.View>
          </Animated.View>
        </View>

        <Animated.Text style={[s.title, { opacity: titleOp, transform: [{ translateY: titleY }] }]}>
          ¡Cuenta creada!
        </Animated.Text>

        <Animated.Text style={[s.subtitle, { opacity: subOp, transform: [{ translateY: subY }] }]}>
          {'Tu cuenta ha sido registrada correctamente.\nBienvenido a Qoricash.'}
        </Animated.Text>

      </Animated.View>

      {/* Overlay negro para salida — tapa la playa durante la transición */}
      <Animated.View style={[StyleSheet.absoluteFill, s.blackOverlay, { opacity: blackFade }]} pointerEvents="none" />
    </View>
  );
};

export default RegisterSuccessScreen;

const s = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#FFFFFF',
  },
  content: {
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 36,
    backgroundColor: '#FFFFFF',
  },
  blackOverlay: {
    backgroundColor: '#000000',
  },
  logo: {
    width: 136,
    height: 42,
    marginBottom: 56,
  },
  iconZone: {
    width: 100,
    height: 100,
    marginBottom: 36,
    alignItems: 'center',
    justifyContent: 'center',
  },
  spinTrack: {
    position: 'absolute',
    width: 100,
    height: 100,
    borderRadius: 50,
    borderWidth: 2,
    borderColor: 'rgba(0,0,0,0.07)',
  },
  spinArc: {
    position: 'absolute',
    width: 100,
    height: 100,
    borderRadius: 50,
    borderWidth: 2,
    borderTopColor: '#0D1117',
    borderRightColor: 'rgba(0,0,0,0.15)',
    borderBottomColor: 'transparent',
    borderLeftColor: 'transparent',
  },
  ripple: {
    position: 'absolute',
    width: 84,
    height: 84,
    borderRadius: 42,
    borderWidth: 1.5,
    borderColor: '#16a34a',
  },
  circle: {
    position: 'absolute',
    width: 84,
    height: 84,
    borderRadius: 42,
    backgroundColor: '#16a34a',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#16a34a',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.28,
    shadowRadius: 16,
    elevation: 10,
  },
  title: {
    fontSize: 26,
    fontWeight: '800',
    color: '#0D1117',
    textAlign: 'center',
    marginBottom: 10,
    letterSpacing: 0.1,
  },
  subtitle: {
    fontSize: 14,
    color: '#6B7280',
    textAlign: 'center',
    lineHeight: 22,
    fontWeight: '400',
  },
});
