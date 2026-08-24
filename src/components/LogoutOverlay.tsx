import React, { useEffect, useRef, useState } from 'react';
import {
  View,
  StyleSheet,
  Animated,
  Easing,
  Image,
  ImageBackground,
  Text,
} from 'react-native';
import { BlurView } from 'expo-blur';

const GREEN      = '#22c55e';
const GREEN_GLOW = 'rgba(34,197,94,0.16)';

interface Props {
  visible: boolean;
  onLogout: () => Promise<void>;
  onComplete: () => void;
}

const Dot: React.FC<{ anim: Animated.Value }> = ({ anim }) => {
  const scale = anim.interpolate({ inputRange: [0, 0.5, 1], outputRange: [0.5, 1.15, 0.5] });
  const op    = anim.interpolate({ inputRange: [0, 0.5, 1], outputRange: [0.22, 1, 0.22] });
  return <Animated.View style={[s.dot, { transform: [{ scale }], opacity: op }]} />;
};

export const LogoutOverlay: React.FC<Props> = ({ visible, onLogout, onComplete }) => {
  const [shouldRender, setShouldRender] = useState(false);
  const runningRef = useRef(false);

  const overlayFade = useRef(new Animated.Value(0)).current;
  const cardFade    = useRef(new Animated.Value(0)).current;
  const cardScale   = useRef(new Animated.Value(0.88)).current;
  const logoFade    = useRef(new Animated.Value(0)).current;
  const logoY       = useRef(new Animated.Value(-16)).current;
  const textFade    = useRef(new Animated.Value(0)).current;
  const spin        = useRef(new Animated.Value(0)).current;
  const spin2       = useRef(new Animated.Value(0)).current;
  const glowOp      = useRef(new Animated.Value(0.3)).current;
  const glowSc      = useRef(new Animated.Value(0.85)).current;
  const d0          = useRef(new Animated.Value(0)).current;
  const d1          = useRef(new Animated.Value(0)).current;
  const d2          = useRef(new Animated.Value(0)).current;
  const exitFade    = useRef(new Animated.Value(1)).current;

  const loopRef   = useRef<Animated.CompositeAnimation | null>(null);
  const timersRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  const clear = () => {
    loopRef.current?.stop(); loopRef.current = null;
    timersRef.current.forEach(clearTimeout); timersRef.current = [];
  };

  const reset = () => {
    overlayFade.setValue(0); cardFade.setValue(0); cardScale.setValue(0.88);
    logoFade.setValue(0); logoY.setValue(-16); textFade.setValue(0);
    spin.setValue(0); spin2.setValue(0); glowOp.setValue(0.3); glowSc.setValue(0.85);
    d0.setValue(0); d1.setValue(0); d2.setValue(0);
    exitFade.setValue(1);
  };

  const startLoops = () => {
    const loop = (v: Animated.Value, dur: number, toVal = 1) =>
      Animated.loop(Animated.timing(v, { toValue: toVal, duration: dur, useNativeDriver: true, easing: Easing.linear }));

    const glowLoop = Animated.loop(Animated.sequence([
      Animated.parallel([
        Animated.timing(glowOp, { toValue: 0.9, duration: 850, useNativeDriver: true, easing: Easing.inOut(Easing.quad) }),
        Animated.timing(glowSc, { toValue: 1.18, duration: 850, useNativeDriver: true, easing: Easing.inOut(Easing.quad) }),
      ]),
      Animated.parallel([
        Animated.timing(glowOp, { toValue: 0.2, duration: 850, useNativeDriver: true, easing: Easing.inOut(Easing.quad) }),
        Animated.timing(glowSc, { toValue: 0.82, duration: 850, useNativeDriver: true, easing: Easing.inOut(Easing.quad) }),
      ]),
    ]));

    const dot = (a: Animated.Value, delay: number) =>
      Animated.loop(Animated.sequence([
        Animated.delay(delay),
        Animated.timing(a, { toValue: 1, duration: 400, useNativeDriver: true, easing: Easing.out(Easing.quad) }),
        Animated.timing(a, { toValue: 0, duration: 400, useNativeDriver: true, easing: Easing.in(Easing.quad) }),
        Animated.delay(800 - delay),
      ]));

    loopRef.current = Animated.parallel([
      loop(spin, 1300),
      loop(spin2, 2100),
      glowLoop,
      dot(d0, 0), dot(d1, 190), dot(d2, 380),
    ]);
    loopRef.current.start();
  };

  useEffect(() => {
    if (!visible) {
      if (runningRef.current) {
        clear();
        runningRef.current = false;
        setShouldRender(false);
        reset();
      }
      return;
    }
    if (runningRef.current) return;

    runningRef.current = true;
    reset();
    setShouldRender(true);

    // ── ENTRADA (0–480ms) ────────────────────────────────────────────────────
    Animated.parallel([
      Animated.timing(overlayFade, { toValue: 1, duration: 360, useNativeDriver: true, easing: Easing.out(Easing.quad) }),
      Animated.spring(cardScale,   { toValue: 1, tension: 60, friction: 9, useNativeDriver: true }),
      Animated.timing(cardFade,    { toValue: 1, duration: 360, useNativeDriver: true }),
      Animated.timing(logoY,       { toValue: 0, duration: 480, useNativeDriver: true, easing: Easing.out(Easing.cubic) }),
      Animated.timing(logoFade,    { toValue: 1, duration: 480, useNativeDriver: true }),
      Animated.sequence([
        Animated.delay(260),
        Animated.timing(textFade, { toValue: 1, duration: 340, useNativeDriver: true }),
      ]),
    ]).start(() => {
      if (!runningRef.current) return;
      startLoops();

      // ── Logout real detrás del overlay (380ms después de entrada) ──────────
      const t1 = setTimeout(async () => { await onLogout(); }, 380);
      timersRef.current.push(t1);

      // ── SALIDA (1400ms después de entrada) ────────────────────────────────
      const t2 = setTimeout(() => {
        if (!runningRef.current) return;
        clear();
        Animated.timing(exitFade, {
          toValue: 0, duration: 440, useNativeDriver: true, easing: Easing.in(Easing.cubic),
        }).start(() => {
          runningRef.current = false;
          reset();
          onComplete();
          setShouldRender(false);
        });
      }, 1400);
      timersRef.current.push(t2);
    });
  }, [visible]);

  if (!shouldRender) return null;

  const r1 = spin.interpolate({ inputRange: [0,1], outputRange: ['0deg','360deg'] });
  const r2 = spin2.interpolate({ inputRange: [0,1], outputRange: ['360deg','0deg'] });

  return (
    <Animated.View style={[s.container, { opacity: exitFade }]} pointerEvents="auto">

      <ImageBackground source={require('../../assets/cd.png')} style={StyleSheet.absoluteFill} resizeMode="cover" />
      <Animated.View style={[StyleSheet.absoluteFill, s.overlay, { opacity: overlayFade }]} />

      <Animated.View style={{ opacity: cardFade, transform: [{ scale: cardScale }], width: '100%', paddingHorizontal: 32 }}>
        <BlurView intensity={88} tint="dark" style={s.card}>

          {/* Logo */}
          <Animated.View style={{ opacity: logoFade, transform: [{ translateY: logoY }], marginBottom: 34 }}>
            <Image source={require('../../assets/vv.png')} style={s.logo} resizeMode="contain" />
          </Animated.View>

          {/* Spinner */}
          <View style={s.spinWrap}>

            {/* Glow central */}
            <Animated.View style={[s.glow, { opacity: glowOp, transform: [{ scale: glowSc }] }]} />

            {/* Anillo exterior */}
            <Animated.View style={[s.ringOuter, { transform: [{ rotate: r1 }] }]} />

            {/* Anillo interior (contra-rotación) */}
            <Animated.View style={[s.ringInner, { transform: [{ rotate: r2 }] }]} />

          </View>

          {/* Texto */}
          <Animated.View style={{ opacity: textFade, alignItems: 'center' }}>
            <Text style={s.title}>
              Cerrando <Text style={s.accent}>sesión</Text>
            </Text>
            <Text style={s.sub}>Hasta pronto...</Text>
          </Animated.View>

          {/* Dots */}
          <View style={s.dotsRow}>
            <Dot anim={d0} />
            <Dot anim={d1} />
            <Dot anim={d2} />
          </View>

        </BlurView>
      </Animated.View>
    </Animated.View>
  );
};

const s = StyleSheet.create({
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
    width: 160,
    height: 28,
  },
  spinWrap: {
    width: 96,
    height: 96,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 30,
  },
  glow: {
    position: 'absolute',
    width: 68,
    height: 68,
    borderRadius: 34,
    backgroundColor: GREEN_GLOW,
    shadowColor: GREEN,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 1,
    shadowRadius: 28,
  },
  ringOuter: {
    position: 'absolute',
    width: 76,
    height: 76,
    borderRadius: 38,
    borderWidth: 2.5,
    borderColor: 'rgba(34,197,94,0.1)',
    borderTopColor: GREEN,
    borderRightColor: GREEN,
  },
  ringInner: {
    position: 'absolute',
    width: 54,
    height: 54,
    borderRadius: 27,
    borderWidth: 2,
    borderColor: 'rgba(34,197,94,0.06)',
    borderTopColor: 'rgba(34,197,94,0.55)',
    borderLeftColor: 'rgba(34,197,94,0.55)',
  },
  title: {
    fontSize: 18,
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
    color: 'rgba(255,255,255,0.42)',
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
