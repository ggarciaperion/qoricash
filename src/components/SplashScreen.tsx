/**
 * QoriCash — Splash Screen "Draw-On"
 * Concepto: el anillo de la Q se dibuja sobre sí mismo (strokeDashoffset),
 * letras aparecen con pop elástico (scale overshoot), salida des-dibuja la Q.
 */
import React, { useEffect } from 'react';
import { View, StyleSheet, Dimensions } from 'react-native';
import Svg, { Circle, Line } from 'react-native-svg';
import Reanimated, {
  useSharedValue,
  useAnimatedStyle,
  useAnimatedProps,
  withTiming,
  withDelay,
  withSequence,
  withSpring,
  Easing,
  runOnJS,
} from 'react-native-reanimated';

const AnimatedCircle = Reanimated.createAnimatedComponent(Circle);
const AnimatedLine   = Reanimated.createAnimatedComponent(Line);

const { width: W, height: H } = Dimensions.get('window');

const FONT_SIZE = 50;
const Q_H       = FONT_SIZE * 1.45;
const LINE_W    = W * 0.72;
const STAGGER   = 40;

// Geometría SVG (viewBox "-10 -8 120 141")
const CIRC     = 2 * Math.PI * 38;                  // perímetro anillo ≈ 238.76
const TAIL_LEN = Math.hypot(80 - 51, 103 - 60);     // longitud cola  ≈ 51.87

const LETTERS = ['o', 'r', 'i', 'c', 'a', 's', 'h'];

// ── Q con draw-on animado ────────────────────────────────────────────────────
const AnimatedQ: React.FC<{
  ringProg: Reanimated.SharedValue<number>;
  tailProg: Reanimated.SharedValue<number>;
  size: number;
}> = ({ ringProg, tailProg, size }) => {

  const ringProps = useAnimatedProps(() => ({
    strokeDashoffset: CIRC * (1 - ringProg.value),
  }));

  const tailProps = useAnimatedProps(() => ({
    strokeDashoffset: TAIL_LEN * (1 - tailProg.value),
  }));

  return (
    <Svg width={size * 0.82} height={size} viewBox="-10 -8 120 141">
      <AnimatedCircle
        cx="50" cy="43" r="38"
        stroke="#FFF" strokeWidth="15" fill="none"
        strokeDasharray={CIRC}
        animatedProps={ringProps}
      />
      <AnimatedLine
        x1="51" y1="60" x2="80" y2="103"
        stroke="#FFF" strokeWidth="12" strokeLinecap="square"
        strokeDasharray={TAIL_LEN}
        animatedProps={tailProps}
      />
    </Svg>
  );
};

// ── Letra individual con pop spring ──────────────────────────────────────────
const AnimLetter: React.FC<{
  char: string;
  opOut: Reanimated.SharedValue<number>;
  scOut: Reanimated.SharedValue<number>;
}> = ({ char, opOut, scOut }) => {
  const style = useAnimatedStyle(() => ({
    opacity: opOut.value,
    transform: [{ scale: scOut.value }],
  }));
  return (
    <Reanimated.Text style={[styles.tailText, style]}>
      {char}
    </Reanimated.Text>
  );
};

interface Props { onFinish: () => void }

export const SplashScreen: React.FC<Props> = ({ onFinish }) => {

  const rootOp = useSharedValue(1);

  // Q — draw-on + pulse al completar
  const ringProg = useSharedValue(0);
  const tailProg = useSharedValue(0);
  const qSc      = useSharedValue(1);

  // Letras — opacity + scale (pop elástico)
  const lOp = [
    useSharedValue(0), useSharedValue(0), useSharedValue(0), useSharedValue(0),
    useSharedValue(0), useSharedValue(0), useSharedValue(0),
  ];
  const lSc = [
    useSharedValue(0.55), useSharedValue(0.55), useSharedValue(0.55), useSharedValue(0.55),
    useSharedValue(0.55), useSharedValue(0.55), useSharedValue(0.55),
  ];

  // Línea + respiración conjunto
  const lineW  = useSharedValue(0);
  const lineOp = useSharedValue(0);
  const wordSc = useSharedValue(1);

  const rootStyle = useAnimatedStyle(() => ({ opacity: rootOp.value }));
  const qScStyle  = useAnimatedStyle(() => ({ transform: [{ scale: qSc.value }] }));
  const wordStyle = useAnimatedStyle(() => ({ transform: [{ scale: wordSc.value }] }));
  const lineStyle = useAnimatedStyle(() => ({ width: lineW.value, opacity: lineOp.value }));

  useEffect(() => {
    const E = Easing;

    // ── 1. Anillo se dibuja (0–740ms) ─────────────────────────────────────────
    ringProg.value = withTiming(1, { duration: 740, easing: E.inOut(E.cubic) });

    // ── 2. Cola se dibuja (320–700ms) ─────────────────────────────────────────
    tailProg.value = withDelay(320, withTiming(1, { duration: 400, easing: E.out(E.cubic) }));

    // ── 3. Pulse al completar la Q (720ms) ────────────────────────────────────
    qSc.value = withDelay(720, withSequence(
      withSpring(1.08, { damping: 4, stiffness: 340, mass: 0.5 }),
      withSpring(1.00, { damping: 12, stiffness: 180, mass: 0.9 }),
    ));

    // ── 4. Letras: pop elástico escalonado (780ms+) ───────────────────────────
    LETTERS.forEach((_, i) => {
      const d = 780 + i * STAGGER;
      lOp[i].value = withDelay(d, withTiming(1, { duration: 130, easing: E.out(E.cubic) }));
      lSc[i].value = withDelay(d, withSpring(1, { damping: 7, stiffness: 360, mass: 0.4 }));
    });

    // ── 5. Línea crece (1 280ms) ──────────────────────────────────────────────
    lineOp.value = withDelay(1280, withTiming(1, { duration: 100 }));
    lineW.value  = withDelay(1280, withTiming(LINE_W, { duration: 520, easing: E.out(E.cubic) }));

    // ── 6. Respiración suave (2 000–3 300ms) ─────────────────────────────────
    wordSc.value = withDelay(2000, withSequence(
      withTiming(1.013, { duration: 650, easing: E.inOut(E.sin) }),
      withTiming(1.000, { duration: 650, easing: E.inOut(E.sin) }),
    ));

    // ── 7. Salida (3 200ms+) ──────────────────────────────────────────────────
    // Línea se contrae
    lineW.value  = withDelay(3200, withTiming(0, { duration: 300, easing: E.in(E.cubic) }));
    lineOp.value = withDelay(3460, withTiming(0, { duration: 80 }));

    // Letras: scale→0.8 + fade, stagger suave
    LETTERS.forEach((_, i) => {
      const d = 3200 + i * 24;
      lSc[i].value = withDelay(d, withTiming(0.8, { duration: 240, easing: E.in(E.cubic) }));
      lOp[i].value = withDelay(d, withTiming(0,   { duration: 240, easing: E.in(E.cubic) }));
    });

    // Q se des-dibuja (cola primero, luego anillo retrocede)
    tailProg.value = withDelay(3310, withTiming(0, { duration: 200, easing: E.in(E.cubic) }));
    ringProg.value = withDelay(3360, withTiming(0, { duration: 400, easing: E.in(E.cubic) }));

    // Fondo se apaga
    rootOp.value = withDelay(3650, withTiming(0, { duration: 300, easing: E.in(E.quad) },
      (finished) => { if (finished) runOnJS(onFinish)(); }
    ));

  }, []);

  return (
    <Reanimated.View style={[styles.root, rootStyle]} pointerEvents="none">

      <Reanimated.View style={[styles.wordRow, wordStyle]}>

        {/* Q con draw-on + pulse */}
        <Reanimated.View style={qScStyle}>
          <AnimatedQ ringProg={ringProg} tailProg={tailProg} size={Q_H} />
        </Reanimated.View>

        {/* Letras con pop elástico */}
        <View style={styles.lettersRow}>
          {LETTERS.map((char, i) => (
            <AnimLetter key={i} char={char} opOut={lOp[i]} scOut={lSc[i]} />
          ))}
        </View>

      </Reanimated.View>

      {/* Línea decorativa */}
      <View style={styles.lineWrap}>
        <Reanimated.View style={[styles.line, lineStyle]} />
      </View>

    </Reanimated.View>
  );
};

const styles = StyleSheet.create({
  root: {
    position: 'absolute',
    top: 0, left: 0,
    width: W, height: H,
    backgroundColor: '#000000',
    justifyContent: 'center',
    alignItems: 'center',
    zIndex: 9999,
  },
  wordRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  lettersRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginLeft: 1,
    overflow: 'hidden',
  },
  tailText: {
    fontFamily: 'Sansation_Regular',
    fontSize: FONT_SIZE,
    color: '#FFFFFF',
    includeFontPadding: false,
    letterSpacing: 0.3,
  },
  lineWrap: {
    marginTop: 10,
    width: LINE_W,
    height: 1,
    overflow: 'hidden',
    alignSelf: 'center',
    alignItems: 'flex-start',
  },
  line: {
    height: 1,
    backgroundColor: 'rgba(255,255,255,0.45)',
  },
});
