import React, { useEffect, useRef, useState } from 'react';
import {
  View,
  StyleSheet,
  Animated,
  Easing,
  Image,
  ImageBackground,
  Dimensions,
  Text,
} from 'react-native';
import { BlurView } from 'expo-blur';
import { Ionicons } from '@expo/vector-icons';

const { width } = Dimensions.get('window');
const GREEN      = '#22c55e';
const GREEN_GLOW = 'rgba(34,197,94,0.18)';

interface Props { visible: boolean; onComplete?: () => void }

// ── Dot animado ───────────────────────────────────────────────────────────────
const Dot: React.FC<{ anim: Animated.Value }> = ({ anim }) => {
  const scale = anim.interpolate({ inputRange: [0, 0.5, 1], outputRange: [0.5, 1.15, 0.5] });
  const op    = anim.interpolate({ inputRange: [0, 0.5, 1], outputRange: [0.22, 1, 0.22] });
  return <Animated.View style={[st.dot, { transform: [{ scale }], opacity: op }]} />;
};

// ── Anillo con arco luminoso ──────────────────────────────────────────────────
const Arc: React.FC<{
  size: number;
  stroke: number;
  colorActive: string;
  colorDim: string;
  spin: Animated.AnimatedInterpolation<string>;
  reverse?: boolean;
}> = ({ size, stroke, colorActive, colorDim, spin }) => (
  <Animated.View style={[{
    position: 'absolute',
    width: size, height: size,
    borderRadius: size / 2,
    borderWidth: stroke,
    borderColor: colorDim,
    borderTopColor: colorActive,
    borderRightColor: colorActive,
  }, { transform: [{ rotate: spin }] }]} />
);

// ─── Componente principal ─────────────────────────────────────────────────────
export const LoginLoadingScreen: React.FC<Props> = ({ visible, onComplete }) => {
  const [shouldRender, setShouldRender] = useState(false);
  const [phase, setPhase]               = useState<'loading' | 'success'>('loading');

  // Entrada
  const overlayFade = useRef(new Animated.Value(0)).current;
  const cardScale   = useRef(new Animated.Value(0.86)).current;
  const cardFade    = useRef(new Animated.Value(0)).current;
  const logoFade    = useRef(new Animated.Value(0)).current;
  const logoY       = useRef(new Animated.Value(-20)).current;
  const textFade    = useRef(new Animated.Value(0)).current;

  // Spinners — 3 anillos con velocidades y sentidos distintos
  const spin1 = useRef(new Animated.Value(0)).current;
  const spin2 = useRef(new Animated.Value(0)).current;
  const spin3 = useRef(new Animated.Value(0)).current;

  // Glow pulsante
  const glowOp = useRef(new Animated.Value(0.3)).current;
  const glowSc = useRef(new Animated.Value(0.85)).current;

  // Dots
  const d0 = useRef(new Animated.Value(0)).current;
  const d1 = useRef(new Animated.Value(0)).current;
  const d2 = useRef(new Animated.Value(0)).current;

  // Éxito
  const ringsFade   = useRef(new Animated.Value(1)).current;
  const dotsFade    = useRef(new Animated.Value(1)).current;
  const checkScale  = useRef(new Animated.Value(0)).current;
  const checkFade   = useRef(new Animated.Value(0)).current;
  const checkGlow   = useRef(new Animated.Value(0)).current;
  const rippleScale = useRef(new Animated.Value(0.3)).current;
  const rippleFade  = useRef(new Animated.Value(0)).current;
  const successText = useRef(new Animated.Value(0)).current;

  // Salida
  const exitFade  = useRef(new Animated.Value(1)).current;
  const exitScale = useRef(new Animated.Value(1)).current;

  const loopsRef   = useRef<Animated.CompositeAnimation | null>(null);
  const timerRef   = useRef<ReturnType<typeof setTimeout> | null>(null);
  const runningRef = useRef(false);

  const resetAll = () => {
    overlayFade.setValue(0); cardScale.setValue(0.86); cardFade.setValue(0);
    logoFade.setValue(0); logoY.setValue(-20); textFade.setValue(0);
    spin1.setValue(0); spin2.setValue(0); spin3.setValue(0);
    glowOp.setValue(0.3); glowSc.setValue(0.85);
    d0.setValue(0); d1.setValue(0); d2.setValue(0);
    ringsFade.setValue(1); dotsFade.setValue(1);
    checkScale.setValue(0); checkFade.setValue(0); checkGlow.setValue(0);
    rippleScale.setValue(0.3); rippleFade.setValue(0); successText.setValue(0);
    exitFade.setValue(1); exitScale.setValue(1);
    setPhase('loading');
  };

  const startLoops = () => {
    const loop = (v: Animated.Value, dur: number, toVal = 1) =>
      Animated.loop(Animated.timing(v, { toValue: toVal, duration: dur, useNativeDriver: true, easing: Easing.linear }));

    const glowLoop = Animated.loop(Animated.sequence([
      Animated.parallel([
        Animated.timing(glowOp, { toValue: 0.95, duration: 900, useNativeDriver: true, easing: Easing.inOut(Easing.quad) }),
        Animated.timing(glowSc, { toValue: 1.15, duration: 900, useNativeDriver: true, easing: Easing.inOut(Easing.quad) }),
      ]),
      Animated.parallel([
        Animated.timing(glowOp, { toValue: 0.25, duration: 900, useNativeDriver: true, easing: Easing.inOut(Easing.quad) }),
        Animated.timing(glowSc, { toValue: 0.85, duration: 900, useNativeDriver: true, easing: Easing.inOut(Easing.quad) }),
      ]),
    ]));

    const dot = (a: Animated.Value, delay: number) =>
      Animated.loop(Animated.sequence([
        Animated.delay(delay),
        Animated.timing(a, { toValue: 1, duration: 420, useNativeDriver: true, easing: Easing.out(Easing.quad) }),
        Animated.timing(a, { toValue: 0, duration: 420, useNativeDriver: true, easing: Easing.in(Easing.quad) }),
        Animated.delay(840 - delay),
      ]));

    loopsRef.current = Animated.parallel([
      loop(spin1, 1100),
      loop(spin2, 1700),
      loop(spin3, 2300),
      glowLoop,
      dot(d0, 0), dot(d1, 200), dot(d2, 400),
    ]);
    loopsRef.current.start();
  };

  const stopLoops = () => { loopsRef.current?.stop(); loopsRef.current = null; };

  const playSuccess = (onDone: () => void) => {
    setPhase('success');
    Animated.parallel([
      // Rings + dots desaparecen
      Animated.timing(ringsFade, { toValue: 0, duration: 220, useNativeDriver: true }),
      Animated.timing(dotsFade,  { toValue: 0, duration: 180, useNativeDriver: true }),
      // Ripple expansivo
      Animated.sequence([
        Animated.timing(rippleFade,  { toValue: 0.7, duration: 100, useNativeDriver: true }),
        Animated.parallel([
          Animated.timing(rippleScale, { toValue: 3.2, duration: 600, useNativeDriver: true, easing: Easing.out(Easing.cubic) }),
          Animated.timing(rippleFade,  { toValue: 0,   duration: 600, useNativeDriver: true, easing: Easing.in(Easing.quad) }),
        ]),
      ]),
      // Checkmark con spring + glow
      Animated.sequence([
        Animated.delay(120),
        Animated.parallel([
          Animated.spring(checkScale, { toValue: 1, tension: 160, friction: 5, useNativeDriver: true }),
          Animated.timing(checkFade,  { toValue: 1, duration: 200, useNativeDriver: true }),
          Animated.timing(checkGlow,  { toValue: 1, duration: 400, useNativeDriver: true }),
        ]),
      ]),
      // Texto de éxito
      Animated.sequence([
        Animated.delay(280),
        Animated.timing(successText, { toValue: 1, duration: 320, useNativeDriver: true, easing: Easing.out(Easing.cubic) }),
      ]),
    ]).start(() => onDone());
  };

  useEffect(() => {
    if (!visible && runningRef.current) {
      loopsRef.current?.stop();
      if (timerRef.current) { clearTimeout(timerRef.current); timerRef.current = null; }
      runningRef.current = false;
      setShouldRender(false);
      resetAll();
      return;
    }
    if (!visible || runningRef.current) return;

    runningRef.current = true;
    resetAll();

    timerRef.current = setTimeout(() => {
      timerRef.current = null;
      if (!runningRef.current) return;
      setShouldRender(true);

      // ── ENTRADA (0–480ms) ────────────────────────────────────────────────────
      Animated.parallel([
        Animated.timing(overlayFade, { toValue: 1, duration: 380, useNativeDriver: true, easing: Easing.out(Easing.quad) }),
        Animated.spring(cardScale,   { toValue: 1, tension: 60, friction: 9, useNativeDriver: true }),
        Animated.timing(cardFade,    { toValue: 1, duration: 380, useNativeDriver: true }),
        Animated.timing(logoY,       { toValue: 0, duration: 520, useNativeDriver: true, easing: Easing.out(Easing.cubic) }),
        Animated.timing(logoFade,    { toValue: 1, duration: 520, useNativeDriver: true }),
        Animated.sequence([
          Animated.delay(280),
          Animated.timing(textFade, { toValue: 1, duration: 380, useNativeDriver: true, easing: Easing.out(Easing.quad) }),
        ]),
      ]).start(() => {
        if (!runningRef.current) return;
        startLoops();

        // ── ESPERA girando 2.4s ──────────────────────────────────────────────
        timerRef.current = setTimeout(() => {
          timerRef.current = null;
          if (!runningRef.current) return;
          stopLoops();

          // ── ÉXITO ────────────────────────────────────────────────────────────
          playSuccess(() => {
            if (!runningRef.current) return;

            // ── SALIDA (600ms de pausa después de éxito) ─────────────────────
            timerRef.current = setTimeout(() => {
              timerRef.current = null;
              Animated.parallel([
                Animated.timing(exitFade,  { toValue: 0, duration: 420, useNativeDriver: true, easing: Easing.in(Easing.cubic) }),
                Animated.timing(exitScale, { toValue: 0.93, duration: 420, useNativeDriver: true, easing: Easing.in(Easing.quad) }),
              ]).start(() => {
                runningRef.current = false;
                resetAll();
                onComplete?.();
                setShouldRender(false);
              });
            }, 620);
          });
        }, 2400);
      });
    }, 40);
  }, [visible]);

  if (!shouldRender) return null;

  const r1 = spin1.interpolate({ inputRange: [0,1], outputRange: ['0deg','360deg'] });
  const r2 = spin2.interpolate({ inputRange: [0,1], outputRange: ['360deg','0deg'] });
  const r3 = spin3.interpolate({ inputRange: [0,1], outputRange: ['0deg','360deg'] });

  return (
    <Animated.View
      style={[st.container, { opacity: exitFade, transform: [{ scale: exitScale }] }]}
      pointerEvents={visible ? 'auto' : 'none'}
    >
      <ImageBackground source={require('../../assets/cd.png')} style={StyleSheet.absoluteFill} resizeMode="cover" />
      <Animated.View style={[StyleSheet.absoluteFill, st.overlay, { opacity: overlayFade }]} />

      <Animated.View style={{ opacity: cardFade, transform: [{ scale: cardScale }], width: '100%', paddingHorizontal: 28 }}>
        <BlurView intensity={88} tint="dark" style={st.card}>

          {/* Logo */}
          <Animated.View style={{ opacity: logoFade, transform: [{ translateY: logoY }], marginBottom: 36 }}>
            <Image source={require('../../assets/logo.png')} style={st.logo} resizeMode="contain" />
          </Animated.View>

          {/* Spinner / Checkmark */}
          <View style={st.spinWrap}>

            {/* Glow central pulsante */}
            <Animated.View style={[st.glow, {
              opacity: glowOp,
              transform: [{ scale: glowSc }],
            }]} />

            {/* 3 arcos giratorios */}
            <Animated.View style={{ opacity: ringsFade, alignItems: 'center', justifyContent: 'center' }}>
              <Arc size={108} stroke={2.5}
                colorActive={GREEN}
                colorDim="rgba(34,197,94,0.1)"
                spin={r1}
              />
              <Arc size={82} stroke={2}
                colorActive="rgba(34,197,94,0.65)"
                colorDim="rgba(34,197,94,0.07)"
                spin={r2}
              />
              <Arc size={58} stroke={1.5}
                colorActive="rgba(34,197,94,0.4)"
                colorDim="transparent"
                spin={r3}
              />
            </Animated.View>

            {/* Ripple */}
            <Animated.View style={[st.ripple, {
              opacity: rippleFade,
              transform: [{ scale: rippleScale }],
            }]} />

            {/* Checkmark */}
            <Animated.View style={[st.checkWrap, {
              opacity: checkFade,
              transform: [{ scale: checkScale }],
            }]}>
              <Animated.View style={[st.checkGlowRing, { opacity: checkGlow }]} />
              <View style={st.checkCircle}>
                <Ionicons name="checkmark" size={36} color="#fff" />
              </View>
            </Animated.View>

          </View>

          {/* Textos superpuestos */}
          <View style={st.textBlock}>
            <Animated.View style={[StyleSheet.absoluteFill, {
              opacity: Animated.subtract(textFade, successText),
              alignItems: 'center',
              justifyContent: 'center',
            }]}>
              <Text style={st.title}>Validando <Text style={st.accent}>acceso</Text></Text>
              <Text style={st.sub}>Por favor espera un momento...</Text>
            </Animated.View>
            <Animated.View style={[StyleSheet.absoluteFill, {
              opacity: successText,
              alignItems: 'center',
              justifyContent: 'center',
              transform: [{ translateY: successText.interpolate({ inputRange:[0,1], outputRange:[10,0] }) }],
            }]}>
              <Text style={st.title}>¡Acceso <Text style={st.accent}>confirmado!</Text></Text>
              <Text style={st.sub}>Bienvenido a QoriCash</Text>
            </Animated.View>
          </View>

          {/* Dots */}
          <Animated.View style={[st.dotsRow, { opacity: dotsFade }]}>
            <Dot anim={d0} />
            <Dot anim={d1} />
            <Dot anim={d2} />
          </Animated.View>

        </BlurView>
      </Animated.View>
    </Animated.View>
  );
};

const st = StyleSheet.create({
  container: {
    position: 'absolute',
    top: 0, left: 0, right: 0, bottom: 0,
    zIndex: 9999,
    justifyContent: 'center',
    alignItems: 'center',
  },
  overlay: {
    backgroundColor: 'rgba(0,0,0,0.52)',
  },
  card: {
    borderRadius: 30,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.13)',
    alignItems: 'center',
    paddingTop: 44,
    paddingBottom: 38,
    paddingHorizontal: 32,
  },
  logo: {
    width: 170,
    height: 40,
  },
  spinWrap: {
    width: 120,
    height: 120,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 32,
  },
  glow: {
    position: 'absolute',
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: GREEN_GLOW,
    shadowColor: GREEN,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 1,
    shadowRadius: 30,
  },
  ripple: {
    position: 'absolute',
    width: 88,
    height: 88,
    borderRadius: 44,
    borderWidth: 2,
    borderColor: GREEN,
  },
  checkWrap: {
    position: 'absolute',
    alignItems: 'center',
    justifyContent: 'center',
  },
  checkGlowRing: {
    position: 'absolute',
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: 'rgba(34,197,94,0.14)',
    shadowColor: GREEN,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 1,
    shadowRadius: 22,
  },
  checkCircle: {
    width: 66,
    height: 66,
    borderRadius: 33,
    backgroundColor: GREEN,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: GREEN,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.55,
    shadowRadius: 18,
    elevation: 12,
  },
  textBlock: {
    height: 52,
    width: '100%',
    position: 'relative',
    marginBottom: 6,
  },
  title: {
    fontSize: 19,
    fontWeight: '800',
    color: '#fff',
    textAlign: 'center',
    marginBottom: 5,
    letterSpacing: 0.1,
  },
  accent: {
    color: GREEN,
    fontWeight: '800',
  },
  sub: {
    fontSize: 12.5,
    color: 'rgba(255,255,255,0.45)',
    textAlign: 'center',
    letterSpacing: 0.2,
  },
  dotsRow: {
    flexDirection: 'row',
    gap: 8,
    alignItems: 'center',
    marginTop: 20,
  },
  dot: {
    width: 6.5,
    height: 6.5,
    borderRadius: 3.25,
    backgroundColor: GREEN,
  },
});
