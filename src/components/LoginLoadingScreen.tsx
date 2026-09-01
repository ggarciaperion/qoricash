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
import { Ionicons } from '@expo/vector-icons';
import { Audio } from 'expo-av';
import { useBackground } from '../hooks/useBackground';

const GREEN      = '#22c55e';
const GREEN_GLOW = 'rgba(34,197,94,0.18)';
const ORBIT_R_A  = 57;
const ORBIT_R_B  = 42;
const DOT_A      = 4.5;
const DOT_B      = 3.5;
const SPIN_CTR   = 65;   // spinWrap.width / 2  (130/2)
const CONF_R     = 70;
const CONF_N     = 8;
const CONF_ANGLES = Array.from({ length: CONF_N }, (_, i) => (i * 360) / CONF_N);

interface Props { visible: boolean; onComplete?: () => void }

// ── Dot indicador ─────────────────────────────────────────────────────────────
const Dot: React.FC<{ anim: Animated.Value }> = ({ anim }) => {
  const scale = anim.interpolate({ inputRange:[0,0.5,1], outputRange:[0.5,1.5,0.5] });
  const op    = anim.interpolate({ inputRange:[0,0.5,1], outputRange:[0.15,1,0.15] });
  const ty    = anim.interpolate({ inputRange:[0,0.5,1], outputRange:[0,-5,0] });
  return <Animated.View style={[st.dot, { transform:[{scale},{translateY:ty}], opacity:op }]} />;
};

// ── Arco giratorio ────────────────────────────────────────────────────────────
const Arc: React.FC<{
  size: number; stroke: number;
  colorActive: string; colorDim: string;
  spin: Animated.AnimatedInterpolation<string>;
}> = ({ size, stroke, colorActive, colorDim, spin }) => (
  <Animated.View style={[{
    position:'absolute', width:size, height:size, borderRadius:size/2,
    borderWidth:stroke, borderColor:colorDim,
    borderTopColor:colorActive, borderRightColor:colorActive,
  }, { transform:[{rotate:spin}] }]} />
);

// ─── Componente principal ─────────────────────────────────────────────────────
export const LoginLoadingScreen: React.FC<Props> = ({ visible, onComplete }) => {
  const bg = useBackground();
  const [shouldRender, setShouldRender] = useState(false);
  const [phase, setPhase]               = useState<'loading'|'success'>('loading');

  const soundRef   = useRef<Audio.Sound | null>(null);
  const loopsRef   = useRef<Animated.CompositeAnimation | null>(null);
  const timersRef  = useRef<ReturnType<typeof setTimeout>[]>([]);
  const runningRef = useRef(false);

  // ── Entry ──────────────────────────────────────────────────────────────────
  const overlayFade  = useRef(new Animated.Value(0)).current;
  const cardScale    = useRef(new Animated.Value(0.86)).current;
  const cardFade     = useRef(new Animated.Value(0)).current;
  const cardY        = useRef(new Animated.Value(28)).current;
  const logoFade     = useRef(new Animated.Value(0)).current;
  const logoY        = useRef(new Animated.Value(-18)).current;
  const logoScale    = useRef(new Animated.Value(0.86)).current;
  const textFade     = useRef(new Animated.Value(0)).current;
  const subtextFade  = useRef(new Animated.Value(0)).current;

  // ── Loading loops ──────────────────────────────────────────────────────────
  const spin1     = useRef(new Animated.Value(0)).current;
  const spin2     = useRef(new Animated.Value(0)).current;
  const spin3     = useRef(new Animated.Value(0)).current;
  const orbitA    = useRef(new Animated.Value(0)).current;
  const orbitB    = useRef(new Animated.Value(0)).current;
  const orbitFade = useRef(new Animated.Value(1)).current;
  const glowOp    = useRef(new Animated.Value(0.3)).current;
  const glowSc    = useRef(new Animated.Value(0.85)).current;
  const logoFloat = useRef(new Animated.Value(0)).current;
  const d0 = useRef(new Animated.Value(0)).current;
  const d1 = useRef(new Animated.Value(0)).current;
  const d2 = useRef(new Animated.Value(0)).current;

  // ── Success ────────────────────────────────────────────────────────────────
  const ringsFade   = useRef(new Animated.Value(1)).current;
  const dotsFade    = useRef(new Animated.Value(1)).current;
  const checkScale  = useRef(new Animated.Value(0)).current;
  const checkFade   = useRef(new Animated.Value(0)).current;
  const checkGlow   = useRef(new Animated.Value(0)).current;
  const r1Scale = useRef(new Animated.Value(0.3)).current;
  const r1Fade  = useRef(new Animated.Value(0)).current;
  const r2Scale = useRef(new Animated.Value(0.3)).current;
  const r2Fade  = useRef(new Animated.Value(0)).current;
  const r3Scale = useRef(new Animated.Value(0.3)).current;
  const r3Fade  = useRef(new Animated.Value(0)).current;
  const successText = useRef(new Animated.Value(0)).current;

  // ── Confetti ───────────────────────────────────────────────────────────────
  const confX  = useRef(CONF_ANGLES.map(() => new Animated.Value(0))).current;
  const confY  = useRef(CONF_ANGLES.map(() => new Animated.Value(0))).current;
  const confOp = useRef(CONF_ANGLES.map(() => new Animated.Value(0))).current;

  // ── Exit ───────────────────────────────────────────────────────────────────
  const exitFade  = useRef(new Animated.Value(1)).current;
  const exitScale = useRef(new Animated.Value(1)).current;

  // ── Cleanup ────────────────────────────────────────────────────────────────
  useEffect(() => {
    return () => { soundRef.current?.unloadAsync(); };
  }, []);

  const clearTimers = () => {
    timersRef.current.forEach(t => clearTimeout(t));
    timersRef.current = [];
  };

  const addTimer = (fn: () => void, ms: number) => {
    const t = setTimeout(fn, ms);
    timersRef.current.push(t);
    return t;
  };

  const resetAll = () => {
    overlayFade.setValue(0); cardScale.setValue(0.86); cardFade.setValue(0);
    cardY.setValue(28); logoFade.setValue(0); logoY.setValue(-18);
    logoScale.setValue(0.86); textFade.setValue(0); subtextFade.setValue(0);
    spin1.setValue(0); spin2.setValue(0); spin3.setValue(0);
    orbitA.setValue(0); orbitB.setValue(0); orbitFade.setValue(1);
    glowOp.setValue(0.3); glowSc.setValue(0.85); logoFloat.setValue(0);
    d0.setValue(0); d1.setValue(0); d2.setValue(0);
    ringsFade.setValue(1); dotsFade.setValue(1);
    checkScale.setValue(0); checkFade.setValue(0); checkGlow.setValue(0);
    r1Scale.setValue(0.3); r1Fade.setValue(0);
    r2Scale.setValue(0.3); r2Fade.setValue(0);
    r3Scale.setValue(0.3); r3Fade.setValue(0);
    successText.setValue(0);
    confX.forEach(v => v.setValue(0));
    confY.forEach(v => v.setValue(0));
    confOp.forEach(v => v.setValue(0));
    exitFade.setValue(1); exitScale.setValue(1);
    setPhase('loading');
  };

  // ── Audio ──────────────────────────────────────────────────────────────────
  const preloadSound = async () => {
    try {
      await Audio.setAudioModeAsync({ playsInSilentModeIOS: true });
      const { sound } = await Audio.Sound.createAsync(
        require('../../assets/sounds/payment_success.mp3'),
        { volume: 0.58, shouldPlay: false }
      );
      soundRef.current = sound;
    } catch {}
  };

  const playSound = async () => {
    try {
      if (soundRef.current) {
        await soundRef.current.playAsync();
        soundRef.current.setOnPlaybackStatusUpdate(s => {
          if (s.isLoaded && s.didJustFinish) {
            soundRef.current?.unloadAsync();
            soundRef.current = null;
          }
        });
      }
    } catch {}
  };

  // ── Loops de carga ─────────────────────────────────────────────────────────
  const startLoops = () => {
    preloadSound();

    const loop = (v: Animated.Value, dur: number) =>
      Animated.loop(Animated.timing(v, { toValue:1, duration:dur, useNativeDriver:true, easing:Easing.linear }));

    const glowLoop = Animated.loop(Animated.sequence([
      Animated.parallel([
        Animated.timing(glowOp, { toValue:1, duration:860, useNativeDriver:true, easing:Easing.inOut(Easing.sin) }),
        Animated.timing(glowSc, { toValue:1.22, duration:860, useNativeDriver:true, easing:Easing.inOut(Easing.sin) }),
      ]),
      Animated.parallel([
        Animated.timing(glowOp, { toValue:0.18, duration:860, useNativeDriver:true, easing:Easing.inOut(Easing.sin) }),
        Animated.timing(glowSc, { toValue:0.80, duration:860, useNativeDriver:true, easing:Easing.inOut(Easing.sin) }),
      ]),
    ]));

    const floatLoop = Animated.loop(Animated.sequence([
      Animated.timing(logoFloat, { toValue:-5, duration:1300, useNativeDriver:true, easing:Easing.inOut(Easing.sin) }),
      Animated.timing(logoFloat, { toValue:5,  duration:1300, useNativeDriver:true, easing:Easing.inOut(Easing.sin) }),
    ]));

    const dot = (a: Animated.Value, delay: number) =>
      Animated.loop(Animated.sequence([
        Animated.delay(delay),
        Animated.timing(a, { toValue:1, duration:370, useNativeDriver:true, easing:Easing.out(Easing.quad) }),
        Animated.timing(a, { toValue:0, duration:370, useNativeDriver:true, easing:Easing.in(Easing.quad) }),
        Animated.delay(740 - delay),
      ]));

    loopsRef.current = Animated.parallel([
      loop(spin1, 1100),
      loop(spin2, 1750),
      loop(spin3, 2600),
      loop(orbitA, 2900),
      loop(orbitB, 4400),
      glowLoop, floatLoop,
      dot(d0, 0), dot(d1, 210), dot(d2, 420),
    ]);
    loopsRef.current.start();
  };

  const stopLoops = () => { loopsRef.current?.stop(); loopsRef.current = null; };

  // ── Ripple helper ──────────────────────────────────────────────────────────
  const makeRipple = (scale: Animated.Value, fade: Animated.Value, delay: number) =>
    Animated.sequence([
      Animated.delay(delay),
      Animated.parallel([
        Animated.timing(scale, { toValue:4.8, duration:780, useNativeDriver:true, easing:Easing.out(Easing.cubic) }),
        Animated.sequence([
          Animated.timing(fade, { toValue:0.9, duration:70,  useNativeDriver:true }),
          Animated.timing(fade, { toValue:0,   duration:710, useNativeDriver:true, easing:Easing.out(Easing.quad) }),
        ]),
      ]),
    ]);

  // ── Confetti burst ─────────────────────────────────────────────────────────
  const launchConfetti = () => {
    CONF_ANGLES.forEach((angle, i) => {
      const rad = (angle * Math.PI) / 180;
      Animated.sequence([
        Animated.delay(i * 14),
        Animated.parallel([
          Animated.timing(confX[i], { toValue: CONF_R * Math.cos(rad), duration:640, useNativeDriver:true, easing:Easing.out(Easing.cubic) }),
          Animated.timing(confY[i], { toValue: CONF_R * Math.sin(rad), duration:640, useNativeDriver:true, easing:Easing.out(Easing.cubic) }),
          Animated.sequence([
            Animated.timing(confOp[i], { toValue:1, duration:75, useNativeDriver:true }),
            Animated.timing(confOp[i], { toValue:0, duration:565, useNativeDriver:true, easing:Easing.in(Easing.cubic) }),
          ]),
        ]),
      ]).start();
    });
  };

  // ── Fase de éxito ──────────────────────────────────────────────────────────
  const playSuccess = (onDone: () => void) => {
    setPhase('success');
    playSound();
    launchConfetti();

    Animated.parallel([
      // Fade out elementos de carga
      Animated.timing(ringsFade, { toValue:0, duration:200, useNativeDriver:true }),
      Animated.timing(orbitFade, { toValue:0, duration:180, useNativeDriver:true }),
      Animated.timing(dotsFade,  { toValue:0, duration:160, useNativeDriver:true }),

      // Triple ripple
      makeRipple(r1Scale, r1Fade, 0),
      makeRipple(r2Scale, r2Fade, 140),
      makeRipple(r3Scale, r3Fade, 280),

      // Glow burst → settle
      Animated.sequence([
        Animated.parallel([
          Animated.timing(glowOp, { toValue:1.5, duration:150, useNativeDriver:true }),
          Animated.timing(glowSc, { toValue:1.8, duration:150, useNativeDriver:true }),
        ]),
        Animated.parallel([
          Animated.timing(glowOp, { toValue:0.65, duration:520, useNativeDriver:true }),
          Animated.timing(glowSc, { toValue:1.12, duration:520, useNativeDriver:true }),
        ]),
      ]),

      // Checkmark con spring (overshoot premium)
      Animated.sequence([
        Animated.delay(95),
        Animated.parallel([
          Animated.spring(checkScale, { toValue:1, tension:185, friction:5, useNativeDriver:true }),
          Animated.timing(checkFade,  { toValue:1, duration:180, useNativeDriver:true }),
          Animated.timing(checkGlow,  { toValue:1, duration:500, useNativeDriver:true }),
        ]),
      ]),

      // Texto de éxito
      Animated.sequence([
        Animated.delay(280),
        Animated.timing(successText, { toValue:1, duration:360, useNativeDriver:true, easing:Easing.out(Easing.cubic) }),
      ]),
    ]).start(() => onDone());
  };

  // ── Driver principal ───────────────────────────────────────────────────────
  useEffect(() => {
    if (!visible && runningRef.current) {
      loopsRef.current?.stop();
      clearTimers();
      runningRef.current = false;
      setShouldRender(false);
      resetAll();
      return;
    }
    if (!visible || runningRef.current) return;

    runningRef.current = true;
    resetAll();

    addTimer(() => {
      if (!runningRef.current) return;
      setShouldRender(true);

      // ── ENTRADA ──────────────────────────────────────────────────────────
      Animated.parallel([
        Animated.timing(overlayFade, { toValue:1, duration:360, useNativeDriver:true, easing:Easing.out(Easing.quad) }),
        Animated.spring(cardScale,   { toValue:1, tension:50, friction:9, useNativeDriver:true }),
        Animated.timing(cardFade,    { toValue:1, duration:320, useNativeDriver:true }),
        Animated.timing(cardY,       { toValue:0, duration:500, useNativeDriver:true, easing:Easing.out(Easing.cubic) }),
        // Logo: slide in desde arriba + slight back easing (overshoot leve)
        Animated.timing(logoY,     { toValue:0, duration:520, useNativeDriver:true, easing:Easing.out(Easing.back(1.5)) }),
        Animated.timing(logoFade,  { toValue:1, duration:480, useNativeDriver:true }),
        Animated.timing(logoScale, { toValue:1, duration:520, useNativeDriver:true, easing:Easing.out(Easing.back(1.3)) }),
        // Texto con stagger
        Animated.sequence([
          Animated.delay(230),
          Animated.timing(textFade, { toValue:1, duration:360, useNativeDriver:true, easing:Easing.out(Easing.quad) }),
        ]),
        Animated.sequence([
          Animated.delay(360),
          Animated.timing(subtextFade, { toValue:1, duration:340, useNativeDriver:true }),
        ]),
      ]).start(() => {
        if (!runningRef.current) return;
        startLoops();

        // ── ESPERA (2.5s girando) ─────────────────────────────────────────
        addTimer(() => {
          if (!runningRef.current) return;
          stopLoops();

          // ── ÉXITO ────────────────────────────────────────────────────────
          playSuccess(() => {
            if (!runningRef.current) return;

            // ── SALIDA ────────────────────────────────────────────────────
            addTimer(() => {
              Animated.parallel([
                Animated.timing(exitFade,  { toValue:0, duration:460, useNativeDriver:true, easing:Easing.in(Easing.cubic) }),
                Animated.timing(exitScale, { toValue:1.06, duration:460, useNativeDriver:true, easing:Easing.in(Easing.quad) }),
              ]).start(() => {
                runningRef.current = false;
                resetAll();
                onComplete?.();
                setShouldRender(false);
              });
            }, 680);
          });
        }, 2500);
      });
    }, 40);
  }, [visible]);

  if (!shouldRender) return null;

  const r1  = spin1.interpolate({ inputRange:[0,1], outputRange:['0deg','360deg'] });
  const r2  = spin2.interpolate({ inputRange:[0,1], outputRange:['360deg','0deg'] });
  const r3  = spin3.interpolate({ inputRange:[0,1], outputRange:['0deg','360deg'] });
  const rA  = orbitA.interpolate({ inputRange:[0,1], outputRange:['0deg','360deg'] });
  const rB  = orbitB.interpolate({ inputRange:[0,1], outputRange:['360deg','0deg'] });

  return (
    <Animated.View
      style={[st.container, { opacity:exitFade, transform:[{scale:exitScale}] }]}
      pointerEvents={visible ? 'auto' : 'none'}
    >
      <ImageBackground source={bg} style={StyleSheet.absoluteFill} resizeMode="cover" />
      <Animated.View style={[StyleSheet.absoluteFill, st.overlay, { opacity:overlayFade }]} />

      <Animated.View style={{ opacity:cardFade, transform:[{scale:cardScale},{translateY:cardY}], width:'100%', alignItems:'center' }}>

          {/* ── Logo flotante ── */}
          <Animated.View style={{
            opacity: logoFade,
            transform:[
              { translateY: Animated.add(logoY, logoFloat) },
              { scale: logoScale },
            ],
            marginBottom: 30,
          }}>
            <Image source={require('../../assets/logo.png')} style={st.logo} resizeMode="contain" />
          </Animated.View>

          {/* ── Área de spinner ── */}
          <View style={st.spinWrap}>

            {/* Glow central pulsante */}
            <Animated.View style={[st.glow, { opacity:glowOp, transform:[{scale:glowSc}] }]} />

            {/* Confetti (8 partículas) */}
            {CONF_ANGLES.map((_, i) => (
              <Animated.View key={`cf${i}`} style={[st.confettiDot, {
                opacity: confOp[i],
                transform:[{ translateX:confX[i] }, { translateY:confY[i] }],
              }]} />
            ))}

            {/* Triple ripple de éxito */}
            {([
              [r1Scale, r1Fade, GREEN],
              [r2Scale, r2Fade, 'rgba(34,197,94,0.62)'],
              [r3Scale, r3Fade, 'rgba(34,197,94,0.34)'],
            ] as [Animated.Value, Animated.Value, string][]).map(([scale, fade, color], i) => (
              <Animated.View key={`rp${i}`} style={[st.ripple, {
                opacity: fade, transform:[{scale}], borderColor:color,
              }]} />
            ))}

            {/* Órbita A: 3 puntos, CW, radio exterior */}
            <Animated.View style={[StyleSheet.absoluteFillObject, { opacity:orbitFade, transform:[{rotate:rA}] }]}>
              {[0, 120, 240].map((angle, i) => {
                const rad = (angle * Math.PI) / 180;
                return (
                  <View key={i} style={[st.orbitDotA, {
                    left: SPIN_CTR + ORBIT_R_A * Math.cos(rad) - DOT_A / 2,
                    top:  SPIN_CTR + ORBIT_R_A * Math.sin(rad) - DOT_A / 2,
                  }]} />
                );
              })}
            </Animated.View>

            {/* Órbita B: 3 puntos, CCW, radio interior */}
            <Animated.View style={[StyleSheet.absoluteFillObject, { opacity:orbitFade, transform:[{rotate:rB}] }]}>
              {[60, 180, 300].map((angle, i) => {
                const rad = (angle * Math.PI) / 180;
                return (
                  <View key={i} style={[st.orbitDotB, {
                    left: SPIN_CTR + ORBIT_R_B * Math.cos(rad) - DOT_B / 2,
                    top:  SPIN_CTR + ORBIT_R_B * Math.sin(rad) - DOT_B / 2,
                  }]} />
                );
              })}
            </Animated.View>

            {/* 3 arcos giratorios anidados */}
            <Animated.View style={{ opacity:ringsFade, alignItems:'center', justifyContent:'center' }}>
              <Arc size={114} stroke={2.5} colorActive={GREEN}                 colorDim="rgba(34,197,94,0.10)" spin={r1} />
              <Arc size={86}  stroke={2}   colorActive="rgba(34,197,94,0.62)" colorDim="rgba(34,197,94,0.07)" spin={r2} />
              <Arc size={60}  stroke={1.5} colorActive="rgba(34,197,94,0.36)" colorDim="transparent"          spin={r3} />
            </Animated.View>

            {/* Checkmark */}
            <Animated.View style={[st.checkWrap, { opacity:checkFade, transform:[{scale:checkScale}] }]}>
              <Animated.View style={[st.checkGlowRing, { opacity:checkGlow }]} />
              <View style={st.checkCircle}>
                <Ionicons name="checkmark" size={38} color="#fff" />
              </View>
            </Animated.View>

          </View>

          {/* ── Textos ── */}
          <View style={st.textBlock}>
            {/* Loading */}
            <Animated.View style={[StyleSheet.absoluteFill, {
              opacity: Animated.subtract(textFade, successText),
              alignItems:'center', justifyContent:'center',
            }]}>
              <Text style={st.title}>Verificando <Text style={st.accent}>acceso</Text></Text>
              <Animated.Text style={[st.sub, { opacity:subtextFade }]}>
                Un momento, por favor...
              </Animated.Text>
            </Animated.View>
            {/* Éxito */}
            <Animated.View style={[StyleSheet.absoluteFill, {
              opacity: successText,
              alignItems:'center', justifyContent:'center',
              transform:[{ translateY: successText.interpolate({ inputRange:[0,1], outputRange:[12,0] }) }],
            }]}>
              <Text style={st.title}>¡Acceso <Text style={st.accent}>confirmado!</Text></Text>
              <Text style={st.sub}>Bienvenido a QoriCash</Text>
            </Animated.View>
          </View>

          {/* ── Dots indicadores ── */}
          <Animated.View style={[st.dotsRow, { opacity:dotsFade }]}>
            <Dot anim={d0} />
            <Dot anim={d1} />
            <Dot anim={d2} />
          </Animated.View>

      </Animated.View>
    </Animated.View>
  );
};

const st = StyleSheet.create({
  container: {
    position:'absolute', top:0, left:0, right:0, bottom:0,
    zIndex:9999, justifyContent:'center', alignItems:'center',
  },
  overlay: { backgroundColor:'rgba(0,0,0,0.62)' },
  logo: { width:175, height:42 },
  spinWrap: {
    width:130, height:130,
    alignItems:'center', justifyContent:'center',
    marginBottom:26,
  },
  glow: {
    position:'absolute', width:86, height:86, borderRadius:43,
    backgroundColor:GREEN_GLOW,
    shadowColor:GREEN, shadowOffset:{width:0,height:0},
    shadowOpacity:1, shadowRadius:36,
  },
  orbitDotA: {
    position:'absolute', width:DOT_A, height:DOT_A, borderRadius:DOT_A/2,
    backgroundColor:'rgba(34,197,94,0.62)',
    shadowColor:GREEN, shadowOffset:{width:0,height:0},
    shadowOpacity:0.9, shadowRadius:3,
  },
  orbitDotB: {
    position:'absolute', width:DOT_B, height:DOT_B, borderRadius:DOT_B/2,
    backgroundColor:'rgba(34,197,94,0.38)',
  },
  ripple: {
    position:'absolute', width:90, height:90, borderRadius:45, borderWidth:1.5,
  },
  confettiDot: {
    position:'absolute',
    width:6, height:6, borderRadius:3,
    backgroundColor:GREEN,
    shadowColor:GREEN, shadowOffset:{width:0,height:0},
    shadowOpacity:0.9, shadowRadius:5,
    left: SPIN_CTR - 3,
    top:  SPIN_CTR - 3,
  },
  checkWrap: {
    position:'absolute', alignItems:'center', justifyContent:'center',
  },
  checkGlowRing: {
    position:'absolute', width:90, height:90, borderRadius:45,
    backgroundColor:'rgba(34,197,94,0.11)',
    shadowColor:GREEN, shadowOffset:{width:0,height:0},
    shadowOpacity:1, shadowRadius:30,
  },
  checkCircle: {
    width:68, height:68, borderRadius:34,
    backgroundColor:GREEN,
    alignItems:'center', justifyContent:'center',
    shadowColor:GREEN, shadowOffset:{width:0,height:10},
    shadowOpacity:0.65, shadowRadius:22,
    elevation:14,
  },
  textBlock: { height:54, width:'100%', position:'relative', marginBottom:4 },
  title: {
    fontSize:19, fontWeight:'800', color:'#fff',
    textAlign:'center', marginBottom:5, letterSpacing:0.1,
  },
  accent: { color:GREEN, fontWeight:'800' },
  sub: {
    fontSize:12.5, color:'rgba(255,255,255,0.42)',
    textAlign:'center', letterSpacing:0.2,
  },
  dotsRow: { flexDirection:'row', gap:10, alignItems:'center', marginTop:16 },
  dot: { width:7, height:7, borderRadius:3.5, backgroundColor:GREEN },
});
