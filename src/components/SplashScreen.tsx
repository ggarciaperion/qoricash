import React, { useEffect } from 'react';
import { View, Image, StyleSheet, Dimensions } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import Reanimated, {
  useSharedValue,
  useAnimatedStyle,
  withTiming,
  withSequence,
  withSpring,
  Easing,
} from 'react-native-reanimated';

const { width: SCREEN_W } = Dimensions.get('window');

const LOGO_SIZE = 150;
const SHIM_W    = 60;
const TAIL_W    = 190;  // longitud de la cola de cometa
const TAIL_H    = 48;   // grosor de la cola

// ─── Timing (ms) ─────────────────────────────────────────────────────────────
//   0        ingreso: logo entra desde la derecha
//   620      rotación + destello
//   3100     salida: reversa exacta del ingreso
//   ~3860    onFinish
// ─────────────────────────────────────────────────────────────────────────────

interface Props { onFinish: () => void }

export const SplashScreen: React.FC<Props> = ({ onFinish }) => {

  // ── valores de animación ──────────────────────────────────────────────────
  const logoX   = useSharedValue(SCREEN_W + LOGO_SIZE); // off-screen derecha
  const logoY   = useSharedValue(24);
  const logoOp  = useSharedValue(0);
  const logoSc  = useSharedValue(0.82);
  const logoRot = useSharedValue(0);

  const glowOp  = useSharedValue(0);
  const glowSc  = useSharedValue(0.3);
  const ringOp  = useSharedValue(0);
  const ringSc  = useSharedValue(0.5);
  const shimX   = useSharedValue(-SHIM_W);

  // Cola de cometa — ingreso (derecha del logo) y salida (izquierda del logo)
  const tailEnterOp = useSharedValue(0);
  const tailExitOp  = useSharedValue(0);

  const rootOp  = useSharedValue(1);

  // ── estilos animados ──────────────────────────────────────────────────────
  const rootStyle = useAnimatedStyle(() => ({ opacity: rootOp.value }));

  const logoStyle = useAnimatedStyle(() => ({
    opacity: logoOp.value,
    transform: [
      { translateX: logoX.value },
      { translateY: logoY.value },
      { rotate: `${logoRot.value}deg` },
      { scale: logoSc.value },
    ],
  }));

  const glowStyle = useAnimatedStyle(() => ({
    opacity: glowOp.value,
    transform: [{ scale: glowSc.value }],
  }));

  const ringStyle = useAnimatedStyle(() => ({
    opacity: ringOp.value,
    transform: [{ scale: ringSc.value }],
  }));

  const shimStyle = useAnimatedStyle(() => ({
    transform: [{ translateX: shimX.value }],
  }));

  const tailEnterStyle = useAnimatedStyle(() => ({ opacity: tailEnterOp.value }));
  const tailExitStyle  = useAnimatedStyle(() => ({ opacity: tailExitOp.value }));

  // ── secuencia ─────────────────────────────────────────────────────────────
  useEffect(() => {
    const t: ReturnType<typeof setTimeout>[] = [];

    // ════════════════════════════════════════════════════════
    // INGRESO (0–620ms) — logo entra desde la derecha
    // ════════════════════════════════════════════════════════
    logoOp.value = withTiming(1, { duration: 300, easing: Easing.out(Easing.quad) });
    logoX.value  = withTiming(0, { duration: 620, easing: Easing.out(Easing.cubic) });
    logoY.value  = withSpring(0, { damping: 16, stiffness: 120 });
    logoSc.value = withSpring(1, { damping: 12, stiffness: 90 });

    // Cola de cometa — ingreso (aparece de inmediato, se desvanece al frenar)
    tailEnterOp.value = withTiming(0.72, { duration: 160, easing: Easing.out(Easing.quad) });
    t.push(setTimeout(() => {
      tailEnterOp.value = withTiming(0, { duration: 480, easing: Easing.out(Easing.cubic) });
    }, 160));

    // ════════════════════════════════════════════════════════
    // ROTACIÓN + DESTELLO (620–1 380ms)
    // ════════════════════════════════════════════════════════
    t.push(setTimeout(() => {
      logoRot.value = withTiming(360, { duration: 760, easing: Easing.inOut(Easing.cubic) });

      glowOp.value  = withTiming(0.55, { duration: 350, easing: Easing.out(Easing.quad) });
      glowSc.value  = withTiming(1.0,  { duration: 420, easing: Easing.out(Easing.cubic) });

      ringSc.value  = withTiming(2.6, { duration: 700, easing: Easing.out(Easing.cubic) });
      ringOp.value  = withSequence(
        withTiming(0.5, { duration: 80 }),
        withTiming(0,   { duration: 620, easing: Easing.out(Easing.quad) }),
      );

      shimX.value   = withTiming(LOGO_SIZE + SHIM_W, {
        duration: 500,
        easing: Easing.out(Easing.cubic),
      });
    }, 620));

    // ════════════════════════════════════════════════════════
    // GLOW PULSO SUAVE (1 420ms)
    // ════════════════════════════════════════════════════════
    t.push(setTimeout(() => {
      glowOp.value = withSequence(
        withTiming(0.28, { duration: 700, easing: Easing.inOut(Easing.quad) }),
        withTiming(0.16, { duration: 700, easing: Easing.inOut(Easing.quad) }),
      );
      glowSc.value = withTiming(1.1, { duration: 1200, easing: Easing.inOut(Easing.quad) });
    }, 1420));

    // ════════════════════════════════════════════════════════
    // SALIDA (3 100ms) — reversa exacta del ingreso
    // ════════════════════════════════════════════════════════
    t.push(setTimeout(() => {

      // Mismos valores de ingreso, pero en sentido inverso
      // Easing.in(cubic) = inversa de Easing.out(cubic)
      logoX.value  = withTiming(SCREEN_W + LOGO_SIZE, {
        duration: 620,
        easing: Easing.in(Easing.cubic),
      });
      logoY.value  = withTiming(24, { duration: 580, easing: Easing.in(Easing.quad) });
      logoSc.value = withTiming(0.82, { duration: 620, easing: Easing.in(Easing.cubic) });
      logoOp.value = withTiming(0, { duration: 540, easing: Easing.in(Easing.quad) });
      glowOp.value = withTiming(0, { duration: 380, easing: Easing.in(Easing.quad) });

      // Cola de cometa — salida (izquierda del logo, crece con aceleración)
      // Easing.in = logo empieza lento y acelera, cola crece gradualmente
      tailExitOp.value = withTiming(0.18, { duration: 300, easing: Easing.in(Easing.quad) });
    }, 3100));

    // Cola de salida alcanza su pico cuando el logo tiene máxima velocidad
    t.push(setTimeout(() => {
      tailExitOp.value = withTiming(0.75, { duration: 180, easing: Easing.out(Easing.quad) });
    }, 3100 + 380));

    t.push(setTimeout(() => {
      tailExitOp.value = withTiming(0, { duration: 200, easing: Easing.in(Easing.quad) });
    }, 3100 + 560));

    // Fondo se va a negro ligeramente después del logo (se ve la salida)
    t.push(setTimeout(() => {
      rootOp.value = withTiming(0, { duration: 380, easing: Easing.in(Easing.quad) });
    }, 3300));

    // Fin
    t.push(setTimeout(onFinish, 3780));

    return () => t.forEach(clearTimeout);
  }, []);

  return (
    <Reanimated.View style={[StyleSheet.absoluteFillObject, styles.root, rootStyle]}>
      <View style={styles.center}>

        {/* Anillo expansivo */}
        <Reanimated.View pointerEvents="none" style={[styles.ring, ringStyle]} />

        {/* Resplandor central */}
        <Reanimated.View pointerEvents="none" style={[styles.glow, glowStyle]} />

        {/*
          outerWrapper: aplica las transformaciones del logo.
          Las colas viven dentro y se posicionan absolutamente fuera de los
          límites del logoWrapper — overflow visible por defecto en RN.
        */}
        <Reanimated.View style={[styles.outerWrapper, logoStyle]}>

          {/* Cola de cometa — ingreso (se extiende hacia la derecha) */}
          <Reanimated.View
            pointerEvents="none"
            style={[styles.tailEnter, tailEnterStyle]}
          >
            <LinearGradient
              colors={['rgba(255,255,255,0.55)', 'rgba(255,255,255,0.18)', 'transparent']}
              start={{ x: 0, y: 0.5 }}
              end={{ x: 1, y: 0.5 }}
              style={StyleSheet.absoluteFillObject}
            />
          </Reanimated.View>

          {/* Cola de cometa — salida (se extiende hacia la izquierda) */}
          <Reanimated.View
            pointerEvents="none"
            style={[styles.tailExit, tailExitStyle]}
          >
            <LinearGradient
              colors={['transparent', 'rgba(255,255,255,0.18)', 'rgba(255,255,255,0.55)']}
              start={{ x: 0, y: 0.5 }}
              end={{ x: 1, y: 0.5 }}
              style={StyleSheet.absoluteFillObject}
            />
          </Reanimated.View>

          {/* Logo con shimmer */}
          <View style={styles.logoWrapper}>
            <Image
              source={require('../../assets/xx.png')}
              style={styles.logo}
              resizeMode="contain"
            />

            <View style={styles.shimClip} pointerEvents="none">
              <Reanimated.View style={[styles.shimStripe, shimStyle]}>
                <LinearGradient
                  colors={['transparent', 'rgba(255,255,255,0.45)', 'transparent']}
                  start={{ x: 0, y: 0.5 }}
                  end={{ x: 1, y: 0.5 }}
                  style={StyleSheet.absoluteFillObject}
                />
              </Reanimated.View>
            </View>
          </View>

        </Reanimated.View>
      </View>
    </Reanimated.View>
  );
};

const styles = StyleSheet.create({
  root: {
    backgroundColor: '#000000',
  },
  center: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },

  // Glow
  glow: {
    position: 'absolute',
    width: LOGO_SIZE * 2.2,
    height: LOGO_SIZE * 2.2,
    borderRadius: LOGO_SIZE * 1.1,
    backgroundColor: 'rgba(255,255,255,0.06)',
    shadowColor: '#FFFFFF',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 1,
    shadowRadius: 80,
  },

  // Anillo expansivo
  ring: {
    position: 'absolute',
    width: LOGO_SIZE * 1.4,
    height: LOGO_SIZE * 1.4,
    borderRadius: LOGO_SIZE * 0.7,
    borderWidth: 1.2,
    borderColor: 'rgba(255,255,255,0.55)',
  },

  // Contenedor principal (aplica las transformaciones del logo)
  outerWrapper: {
    width: LOGO_SIZE,
    height: LOGO_SIZE,
    alignItems: 'center',
    justifyContent: 'center',
  },

  // Cola de cometa — ingreso (derecha del logo, logo venía de la derecha)
  tailEnter: {
    position: 'absolute',
    left: LOGO_SIZE,                        // comienza en el borde derecho del logo
    top: (LOGO_SIZE - TAIL_H) / 2,
    width: TAIL_W,
    height: TAIL_H,
    borderRadius: TAIL_H / 2,
  },

  // Cola de cometa — salida (izquierda del logo, logo sale hacia la derecha)
  tailExit: {
    position: 'absolute',
    left: -TAIL_W,                          // comienza TAIL_W a la izquierda
    top: (LOGO_SIZE - TAIL_H) / 2,
    width: TAIL_W,
    height: TAIL_H,
    borderRadius: TAIL_H / 2,
  },

  // Logo con clip del shimmer
  logoWrapper: {
    width: LOGO_SIZE,
    height: LOGO_SIZE,
    overflow: 'hidden',
    alignItems: 'center',
    justifyContent: 'center',
  },
  logo: {
    width: '100%',
    height: '100%',
  },
  shimClip: {
    ...StyleSheet.absoluteFillObject,
    overflow: 'hidden',
  },
  shimStripe: {
    position: 'absolute',
    top: 0,
    bottom: 0,
    left: 0,
    width: SHIM_W,
  },
});
