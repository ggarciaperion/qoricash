import React, { useEffect, useRef, useState } from 'react';
import {
  View,
  StyleSheet,
  Animated,
  Easing,
  Image,
  Text,
} from 'react-native';

const GREEN = '#22c55e';

interface Props {
  visible: boolean;
  onLogout: () => Promise<void>;
  onComplete: () => void;
}

const Dot: React.FC<{ anim: Animated.Value }> = ({ anim }) => {
  const scale = anim.interpolate({ inputRange: [0, 0.5, 1], outputRange: [0.4, 1.2, 0.4] });
  const op    = anim.interpolate({ inputRange: [0, 0.5, 1], outputRange: [0.18, 1, 0.18] });
  return <Animated.View style={[s.dot, { transform: [{ scale }], opacity: op }]} />;
};

export const LogoutOverlay: React.FC<Props> = ({ visible, onLogout, onComplete }) => {
  const [shouldRender, setShouldRender] = useState(false);
  const runningRef  = useRef(false);
  const exitingRef  = useRef(false);          // true mientras el fade-out está corriendo
  const loopRef     = useRef<Animated.CompositeAnimation | null>(null);
  const timersRef   = useRef<ReturnType<typeof setTimeout>[]>([]);

  // Valores de animación
  const masterFade  = useRef(new Animated.Value(0)).current;  // todo el overlay
  const contentFade = useRef(new Animated.Value(0)).current;
  const contentY    = useRef(new Animated.Value(24)).current;
  const spin        = useRef(new Animated.Value(0)).current;
  const spin2       = useRef(new Animated.Value(0)).current;
  const glowOp      = useRef(new Animated.Value(0.25)).current;
  const glowSc      = useRef(new Animated.Value(0.8)).current;
  const d0          = useRef(new Animated.Value(0)).current;
  const d1          = useRef(new Animated.Value(0)).current;
  const d2          = useRef(new Animated.Value(0)).current;

  const clearAll = () => {
    loopRef.current?.stop();
    loopRef.current = null;
    timersRef.current.forEach(clearTimeout);
    timersRef.current = [];
  };

  const resetValues = () => {
    masterFade.setValue(0);
    contentFade.setValue(0);
    contentY.setValue(24);
    spin.setValue(0);
    spin2.setValue(0);
    glowOp.setValue(0.25);
    glowSc.setValue(0.8);
    d0.setValue(0); d1.setValue(0); d2.setValue(0);
  };

  const startLoops = () => {
    const spinLoop = (v: Animated.Value, dur: number) =>
      Animated.loop(Animated.timing(v, { toValue: 1, duration: dur, easing: Easing.linear, useNativeDriver: true }));

    const glowLoop = Animated.loop(Animated.sequence([
      Animated.parallel([
        Animated.timing(glowOp, { toValue: 0.85, duration: 900, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
        Animated.timing(glowSc, { toValue: 1.22, duration: 900, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
      ]),
      Animated.parallel([
        Animated.timing(glowOp, { toValue: 0.18, duration: 900, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
        Animated.timing(glowSc, { toValue: 0.78, duration: 900, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
      ]),
    ]));

    const dot = (a: Animated.Value, delay: number) =>
      Animated.loop(Animated.sequence([
        Animated.delay(delay),
        Animated.timing(a, { toValue: 1, duration: 380, easing: Easing.out(Easing.quad), useNativeDriver: true }),
        Animated.timing(a, { toValue: 0, duration: 380, easing: Easing.in(Easing.quad),  useNativeDriver: true }),
        Animated.delay(Math.max(0, 760 - delay)),
      ]));

    loopRef.current = Animated.parallel([
      spinLoop(spin,  1200),
      spinLoop(spin2, 2000),
      glowLoop,
      dot(d0, 0), dot(d1, 200), dot(d2, 400),
    ]);
    loopRef.current.start();
  };

  useEffect(() => {
    // visible pasó a false desde afuera (no por nuestro propio onComplete)
    if (!visible) {
      if (runningRef.current && !exitingRef.current) {
        // Cierre forzado — fade suave y limpio
        exitingRef.current = true;
        clearAll();
        Animated.timing(masterFade, { toValue: 0, duration: 400, easing: Easing.in(Easing.quad), useNativeDriver: true })
          .start(() => { runningRef.current = false; exitingRef.current = false; setShouldRender(false); resetValues(); });
      }
      return;
    }
    if (runningRef.current) return;

    // ── Iniciar animación de logout ──────────────────────────────────────────
    runningRef.current = true;
    exitingRef.current = false;
    resetValues();
    setShouldRender(true);

    // ① Overlay negro entra completamente (280ms)
    Animated.timing(masterFade, {
      toValue: 1, duration: 280, easing: Easing.out(Easing.quad), useNativeDriver: true,
    }).start(() => {
      if (!runningRef.current) return;

      // ② Contenido sube suavemente una vez que el negro está listo
      Animated.parallel([
        Animated.timing(contentFade, { toValue: 1, duration: 360, easing: Easing.out(Easing.quad), useNativeDriver: true }),
        Animated.spring(contentY,   { toValue: 0, tension: 160, friction: 18, useNativeDriver: true }),
      ]).start(() => {
        if (!runningRef.current) return;
        startLoops();
      });

      // ③ Logout real mientras el overlay negro tapa todo (seguro, sin flash)
      const t1 = setTimeout(async () => {
        if (!runningRef.current) return;
        await onLogout();
      }, 200);
      timersRef.current.push(t1);

      // ④ Fade-out del contenido (a negro) → luego fade-out del overlay
      const t2 = setTimeout(() => {
        if (!runningRef.current) return;
        exitingRef.current = true;
        clearAll();

        // Primero desaparece el contenido (queda negro puro)
        Animated.timing(contentFade, {
          toValue: 0, duration: 420, easing: Easing.in(Easing.quad), useNativeDriver: true,
        }).start(() => {
          if (!runningRef.current) return;

          // Luego el negro hace fade out suave a la nueva pantalla
          Animated.timing(masterFade, {
            toValue: 0, duration: 520, easing: Easing.inOut(Easing.quad), useNativeDriver: true,
          }).start(() => {
            runningRef.current  = false;
            exitingRef.current  = false;
            // NO llamar reset() aquí — evita el flash de valores reseteados
            onComplete();
            setShouldRender(false);
          });
        });
      }, 2200);
      timersRef.current.push(t2);
    });
  }, [visible]);

  if (!shouldRender) return null;

  const r1 = spin.interpolate({ inputRange: [0, 1], outputRange: ['0deg',  '360deg'] });
  const r2 = spin2.interpolate({ inputRange: [0, 1], outputRange: ['360deg', '0deg'] });

  return (
    // masterFade controla TODO — negro puro de fondo
    <Animated.View style={[s.container, { opacity: masterFade }]} pointerEvents="auto">

      {/* Contenido centrado */}
      <Animated.View style={[s.content, { opacity: contentFade, transform: [{ translateY: contentY }] }]}>

        {/* Logo */}
        <Image source={require('../../assets/logo.png')} style={s.logo} resizeMode="contain" />

        {/* Spinner */}
        <View style={s.spinWrap}>
          <Animated.View style={[s.glow, { opacity: glowOp, transform: [{ scale: glowSc }] }]} />
          <Animated.View style={[s.ringOuter, { transform: [{ rotate: r1 }] }]} />
          <Animated.View style={[s.ringInner, { transform: [{ rotate: r2 }] }]} />
        </View>

        {/* Texto */}
        <Text style={s.title}>
          Cerrando <Text style={s.accent}>sesión</Text>
        </Text>
        <Text style={s.sub}>Hasta pronto...</Text>

        {/* Dots */}
        <View style={s.dotsRow}>
          <Dot anim={d0} />
          <Dot anim={d1} />
          <Dot anim={d2} />
        </View>

      </Animated.View>
    </Animated.View>
  );
};

const s = StyleSheet.create({
  container: {
    position: 'absolute',
    top: 0, left: 0, right: 0, bottom: 0,
    zIndex: 9999,
    backgroundColor: '#000000',   // negro puro — elimina cualquier flash
    justifyContent: 'center',
    alignItems: 'center',
  },
  content: {
    alignItems: 'center',
    paddingHorizontal: 40,
  },
  logo: {
    width: 148,
    height: 34,
    marginBottom: 48,
  },
  spinWrap: {
    width: 88,
    height: 88,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 32,
  },
  glow: {
    position: 'absolute',
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: 'rgba(34,197,94,0.14)',
    shadowColor: GREEN,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 1,
    shadowRadius: 26,
    elevation: 0,
  },
  ringOuter: {
    position: 'absolute',
    width: 72,
    height: 72,
    borderRadius: 36,
    borderWidth: 2.5,
    borderColor: 'rgba(34,197,94,0.08)',
    borderTopColor: GREEN,
    borderRightColor: GREEN,
  },
  ringInner: {
    position: 'absolute',
    width: 50,
    height: 50,
    borderRadius: 25,
    borderWidth: 2,
    borderColor: 'rgba(34,197,94,0.05)',
    borderTopColor: 'rgba(34,197,94,0.5)',
    borderLeftColor: 'rgba(34,197,94,0.5)',
  },
  title: {
    fontSize: 17,
    fontWeight: '700',
    color: '#ffffff',
    textAlign: 'center',
    marginBottom: 5,
    letterSpacing: 0.1,
  },
  accent: {
    color: GREEN,
    fontWeight: '800',
  },
  sub: {
    fontSize: 12,
    color: 'rgba(255,255,255,0.35)',
    textAlign: 'center',
    letterSpacing: 0.3,
  },
  dotsRow: {
    flexDirection: 'row',
    gap: 9,
    alignItems: 'center',
    marginTop: 22,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: GREEN,
  },
});
