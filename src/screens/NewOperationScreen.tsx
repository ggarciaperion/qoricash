import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  Alert,
  TouchableOpacity,
  Modal,
  ImageBackground,
  TextInput,
  Text,
  Image,
  ActivityIndicator,
  Animated,
  Easing,
} from 'react-native';
import { BlurView } from 'expo-blur';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { MotiView } from 'moti';
import * as Haptics from 'expo-haptics';
import { createAudioPlayer } from 'expo-audio';
import { useAuth } from '../contexts/AuthContext';
import { Calculator } from '../components/Calculator';
import { operationsApi } from '../api/operations';
import { CreateOperationForm, BankAccount } from '../types';
import { formatCurrency, calculateAmount, formatExchangeRate } from '../utils/formatters';
import axios from 'axios';
import { API_CONFIG } from '../constants/config';
import { useBackground } from '../hooks/useBackground';

// ─── Design tokens ─────────────────────────────────────────────────────────────
const GREEN        = '#22c55e';
const GREEN_DIM    = 'rgba(34,197,94,0.10)';
const GREEN_BORDER = 'rgba(34,197,94,0.25)';
const GLASS_BG     = '#FFFFFF';
const GLASS_BORDER = 'rgba(0,0,0,0.08)';
const RED          = '#3b82f6';

// ─── Banks ─────────────────────────────────────────────────────────────────────
const BANKS_LIMA      = ['BCP', 'INTERBANK', 'PICHINCHA', 'BANBIF', 'BBVA', 'Scotiabank', 'Otros'];
const BANKS_PROVINCIA = ['BCP', 'INTERBANK'];

interface Props { navigation: any; route?: any }

// ─── Segmented control ─────────────────────────────────────────────────────────
const Seg: React.FC<{
  options: string[];
  value: string;
  onChange: (v: string) => void;
}> = ({ options, value, onChange }) => (
  <View style={s.seg}>
    {options.map(opt => (
      <TouchableOpacity
        key={opt}
        style={[s.segBtn, value === opt && s.segBtnActive]}
        onPress={() => { Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light); onChange(opt); }}
        activeOpacity={0.78}
      >
        <Text style={[s.segBtnTxt, value === opt && s.segBtnTxtActive]}>{opt}</Text>
      </TouchableOpacity>
    ))}
  </View>
);

// ─── Creating overlay ──────────────────────────────────────────────────────────
const DARK      = '#0D1117';
const DARK_GLOW = 'rgba(0,0,0,0.06)';
const ORBIT_R_A = 57;
const ORBIT_R_B = 42;
const DOT_A     = 4.5;
const DOT_B     = 3.5;
const SPIN_CTR  = 65;
const CONF_R    = 70;
const CONF_N    = 8;
const CONF_ANGLES = Array.from({ length: CONF_N }, (_, i) => (i * 360) / CONF_N);

const OvDot: React.FC<{ anim: Animated.Value }> = ({ anim }) => {
  const scale = anim.interpolate({ inputRange:[0,0.5,1], outputRange:[0.5,1.5,0.5] });
  const op    = anim.interpolate({ inputRange:[0,0.5,1], outputRange:[0.15,1,0.15] });
  const ty    = anim.interpolate({ inputRange:[0,0.5,1], outputRange:[0,-5,0] });
  return <Animated.View style={[ov.dot, { transform:[{scale},{translateY:ty}], opacity:op }]} />;
};

const OvArc: React.FC<{
  size:number; stroke:number;
  colorActive:string; colorDim:string;
  spin: Animated.AnimatedInterpolation<string>;
}> = ({ size, stroke, colorActive, colorDim, spin }) => (
  <Animated.View style={[{
    position:'absolute', width:size, height:size, borderRadius:size/2,
    borderWidth:stroke, borderColor:colorDim,
    borderTopColor:colorActive, borderRightColor:colorActive,
  }, { transform:[{rotate:spin}] }]} />
);

const CreatingOverlay: React.FC<{ visible: boolean; success: boolean }> = ({ visible, success }) => {
  const [shouldRender, setShouldRender] = useState(false);
  const [phase, setPhase] = useState<'loading'|'success'>('loading');

  const loopsRef = useRef<Animated.CompositeAnimation | null>(null);

  // Entry
  const overlayFade = useRef(new Animated.Value(0)).current;
  const cardFade    = useRef(new Animated.Value(0)).current;
  const cardY       = useRef(new Animated.Value(22)).current;
  const logoFade    = useRef(new Animated.Value(0)).current;
  const logoY       = useRef(new Animated.Value(-14)).current;
  const logoScale   = useRef(new Animated.Value(0.88)).current;
  const textFade    = useRef(new Animated.Value(0)).current;
  const subtextFade = useRef(new Animated.Value(0)).current;

  // Loops
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

  // Success
  const ringsFade  = useRef(new Animated.Value(1)).current;
  const dotsFade   = useRef(new Animated.Value(1)).current;
  const checkScale = useRef(new Animated.Value(0)).current;
  const checkFade  = useRef(new Animated.Value(0)).current;
  const checkGlow  = useRef(new Animated.Value(0)).current;
  const r1Scale = useRef(new Animated.Value(0.3)).current;
  const r1Fade  = useRef(new Animated.Value(0)).current;
  const r2Scale = useRef(new Animated.Value(0.3)).current;
  const r2Fade  = useRef(new Animated.Value(0)).current;
  const r3Scale = useRef(new Animated.Value(0.3)).current;
  const r3Fade  = useRef(new Animated.Value(0)).current;
  const successText = useRef(new Animated.Value(0)).current;

  // Confetti
  const confX  = useRef(CONF_ANGLES.map(() => new Animated.Value(0))).current;
  const confY  = useRef(CONF_ANGLES.map(() => new Animated.Value(0))).current;
  const confOp = useRef(CONF_ANGLES.map(() => new Animated.Value(0))).current;

  const resetAll = () => {
    overlayFade.setValue(0); cardFade.setValue(0); cardY.setValue(22);
    logoFade.setValue(0); logoY.setValue(-14); logoScale.setValue(0.88);
    textFade.setValue(0); subtextFade.setValue(0);
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
    setPhase('loading');
  };

  const startLoops = () => {
    const loop = (v: Animated.Value, dur: number) =>
      Animated.loop(Animated.timing(v, { toValue:1, duration:dur, useNativeDriver:true, easing:Easing.linear }));

    const glowLoop = Animated.loop(Animated.sequence([
      Animated.parallel([
        Animated.timing(glowOp, { toValue:1,    duration:860, useNativeDriver:true, easing:Easing.inOut(Easing.sin) }),
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
      loop(spin1, 1100), loop(spin2, 1750), loop(spin3, 2600),
      loop(orbitA, 2900), loop(orbitB, 4400),
      glowLoop, floatLoop,
      dot(d0, 0), dot(d1, 210), dot(d2, 420),
    ]);
    loopsRef.current.start();
  };

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

  const launchConfetti = () => {
    CONF_ANGLES.forEach((angle, i) => {
      const rad = (angle * Math.PI) / 180;
      Animated.sequence([
        Animated.delay(i * 14),
        Animated.parallel([
          Animated.timing(confX[i], { toValue: CONF_R * Math.cos(rad), duration:640, useNativeDriver:true, easing:Easing.out(Easing.cubic) }),
          Animated.timing(confY[i], { toValue: CONF_R * Math.sin(rad), duration:640, useNativeDriver:true, easing:Easing.out(Easing.cubic) }),
          Animated.sequence([
            Animated.timing(confOp[i], { toValue:1, duration:75,  useNativeDriver:true }),
            Animated.timing(confOp[i], { toValue:0, duration:565, useNativeDriver:true, easing:Easing.in(Easing.cubic) }),
          ]),
        ]),
      ]).start();
    });
  };

  // ── Visible change ─────────────────────────────────────────────────────────
  useEffect(() => {
    if (!visible) {
      loopsRef.current?.stop();
      setShouldRender(false);
      resetAll();
      return;
    }

    resetAll();
    setShouldRender(true);

    Animated.parallel([
      Animated.timing(overlayFade, { toValue:1, duration:340, useNativeDriver:true, easing:Easing.out(Easing.quad) }),
      Animated.timing(cardFade,    { toValue:1, duration:300, useNativeDriver:true }),
      Animated.timing(cardY,       { toValue:0, duration:480, useNativeDriver:true, easing:Easing.out(Easing.cubic) }),
      Animated.timing(logoY,       { toValue:0, duration:500, useNativeDriver:true, easing:Easing.out(Easing.back(1.4)) }),
      Animated.timing(logoFade,    { toValue:1, duration:460, useNativeDriver:true }),
      Animated.timing(logoScale,   { toValue:1, duration:500, useNativeDriver:true, easing:Easing.out(Easing.back(1.2)) }),
      Animated.sequence([
        Animated.delay(220),
        Animated.timing(textFade, { toValue:1, duration:340, useNativeDriver:true }),
      ]),
      Animated.sequence([
        Animated.delay(340),
        Animated.timing(subtextFade, { toValue:1, duration:320, useNativeDriver:true }),
      ]),
    ]).start(() => startLoops());
  }, [visible]);

  // ── Success change ─────────────────────────────────────────────────────────
  useEffect(() => {
    if (!success || !visible) return;
    loopsRef.current?.stop();
    setPhase('success');
    launchConfetti();

    Animated.parallel([
      Animated.timing(ringsFade, { toValue:0, duration:200, useNativeDriver:true }),
      Animated.timing(orbitFade, { toValue:0, duration:180, useNativeDriver:true }),
      Animated.timing(dotsFade,  { toValue:0, duration:160, useNativeDriver:true }),
      makeRipple(r1Scale, r1Fade, 0),
      makeRipple(r2Scale, r2Fade, 140),
      makeRipple(r3Scale, r3Fade, 280),
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
      Animated.sequence([
        Animated.delay(95),
        Animated.parallel([
          Animated.spring(checkScale, { toValue:1, tension:185, friction:5, useNativeDriver:true }),
          Animated.timing(checkFade,  { toValue:1, duration:180, useNativeDriver:true }),
          Animated.timing(checkGlow,  { toValue:1, duration:500, useNativeDriver:true }),
        ]),
      ]),
      Animated.sequence([
        Animated.delay(280),
        Animated.timing(successText, { toValue:1, duration:360, useNativeDriver:true, easing:Easing.out(Easing.cubic) }),
      ]),
    ]).start();
  }, [success]);

  if (!shouldRender) return null;

  const r1 = spin1.interpolate({ inputRange:[0,1], outputRange:['0deg','360deg'] });
  const r2 = spin2.interpolate({ inputRange:[0,1], outputRange:['360deg','0deg'] });
  const r3 = spin3.interpolate({ inputRange:[0,1], outputRange:['0deg','360deg'] });
  const rA = orbitA.interpolate({ inputRange:[0,1], outputRange:['0deg','360deg'] });
  const rB = orbitB.interpolate({ inputRange:[0,1], outputRange:['360deg','0deg'] });

  return (
    <Modal visible={visible} transparent animationType="none" onRequestClose={() => {}}>
      <Animated.View style={[ov.root, { opacity: overlayFade }]}>
        <Animated.View style={[StyleSheet.absoluteFill, { backgroundColor:'#FFFFFF', opacity: overlayFade }]} />

        <Animated.View style={{ opacity:cardFade, transform:[{translateY:cardY}], width:'100%', alignItems:'center' }}>

          {/* ── Logo + badge de operación ── */}
          <Animated.View style={{
            opacity: logoFade,
            transform:[{ translateY: Animated.add(logoY, logoFloat) }, { scale: logoScale }],
            marginBottom: 30,
            alignItems: 'center',
            gap: 10,
          }}>
            <Image source={require('../../assets/qc.png')} style={ov.logo} resizeMode="contain" />
            <View style={ov.opBadge}>
              <Ionicons name="swap-horizontal-outline" size={14} color={DARK} />
              <Text style={ov.opBadgeText}>Nueva operación</Text>
            </View>
          </Animated.View>

          {/* ── Spinner area ── */}
          <View style={ov.spinWrap}>
            <Animated.View style={[ov.glow, { opacity:glowOp, transform:[{scale:glowSc}] }]} />

            {/* Confetti */}
            {CONF_ANGLES.map((_, i) => (
              <Animated.View key={`cf${i}`} style={[ov.confettiDot, {
                opacity: confOp[i],
                transform:[{ translateX:confX[i] }, { translateY:confY[i] }],
              }]} />
            ))}

            {/* Triple ripple */}
            {([
              [r1Scale, r1Fade, DARK],
              [r2Scale, r2Fade, 'rgba(0,0,0,0.50)'],
              [r3Scale, r3Fade, 'rgba(0,0,0,0.28)'],
            ] as [Animated.Value, Animated.Value, string][]).map(([scale, fade, color], i) => (
              <Animated.View key={`rp${i}`} style={[ov.ripple, {
                opacity: fade, transform:[{scale}], borderColor:color,
              }]} />
            ))}

            {/* Órbita A */}
            <Animated.View style={[StyleSheet.absoluteFillObject, { opacity:orbitFade, transform:[{rotate:rA}] }]}>
              {[0, 120, 240].map((angle, i) => {
                const rad = (angle * Math.PI) / 180;
                return (
                  <View key={i} style={[ov.orbitDotA, {
                    left: SPIN_CTR + ORBIT_R_A * Math.cos(rad) - DOT_A / 2,
                    top:  SPIN_CTR + ORBIT_R_A * Math.sin(rad) - DOT_A / 2,
                  }]} />
                );
              })}
            </Animated.View>

            {/* Órbita B */}
            <Animated.View style={[StyleSheet.absoluteFillObject, { opacity:orbitFade, transform:[{rotate:rB}] }]}>
              {[60, 180, 300].map((angle, i) => {
                const rad = (angle * Math.PI) / 180;
                return (
                  <View key={i} style={[ov.orbitDotB, {
                    left: SPIN_CTR + ORBIT_R_B * Math.cos(rad) - DOT_B / 2,
                    top:  SPIN_CTR + ORBIT_R_B * Math.sin(rad) - DOT_B / 2,
                  }]} />
                );
              })}
            </Animated.View>

            {/* 3 arcos */}
            <Animated.View style={{ opacity:ringsFade, alignItems:'center', justifyContent:'center' }}>
              <OvArc size={114} stroke={2.5} colorActive={DARK}              colorDim="rgba(0,0,0,0.08)" spin={r1} />
              <OvArc size={86}  stroke={2}   colorActive="rgba(0,0,0,0.55)" colorDim="rgba(0,0,0,0.05)" spin={r2} />
              <OvArc size={60}  stroke={1.5} colorActive="rgba(0,0,0,0.30)" colorDim="transparent"      spin={r3} />
            </Animated.View>

            {/* Checkmark */}
            <Animated.View style={[ov.checkWrap, { opacity:checkFade, transform:[{scale:checkScale}] }]}>
              <Animated.View style={[ov.checkGlowRing, { opacity:checkGlow }]} />
              <View style={ov.checkCircle}>
                <Ionicons name="checkmark" size={38} color="#fff" />
              </View>
              <View style={ov.swapBadge}>
                <Ionicons name="swap-horizontal" size={11} color="#fff" />
              </View>
            </Animated.View>
          </View>

          {/* ── Textos ── */}
          <View style={ov.textBlock}>
            <Animated.View style={[StyleSheet.absoluteFill, {
              opacity: Animated.subtract(textFade, successText),
              alignItems:'center', justifyContent:'center',
            }]}>
              <Text style={ov.title}>Creando <Text style={ov.accent}>operación</Text></Text>
              <Animated.Text style={[ov.sub, { opacity: subtextFade }]}>
                Un momento, por favor...
              </Animated.Text>
            </Animated.View>
            <Animated.View style={[StyleSheet.absoluteFill, {
              opacity: successText,
              alignItems:'center', justifyContent:'center',
              transform:[{ translateY: successText.interpolate({ inputRange:[0,1], outputRange:[12,0] }) }],
            }]}>
              <Text style={ov.title}>¡Operación <Text style={ov.accent}>creada!</Text></Text>
              <Text style={ov.sub}>Redirigiendo al siguiente paso</Text>
            </Animated.View>
          </View>

          {/* ── Dots indicadores ── */}
          <Animated.View style={[ov.dotsRow, { opacity:dotsFade }]}>
            <OvDot anim={d0} />
            <OvDot anim={d1} />
            <OvDot anim={d2} />
          </Animated.View>

        </Animated.View>
      </Animated.View>
    </Modal>
  );
};

const ov = StyleSheet.create({
  root: {
    flex:1, justifyContent:'center', alignItems:'center',
  },
  logo: { width:130, height:33 },
  opBadge: {
    flexDirection:'row', alignItems:'center', gap:5,
    backgroundColor:'#F3F4F6',
    borderWidth:1, borderColor:'rgba(0,0,0,0.07)',
    borderRadius:100, paddingHorizontal:10, paddingVertical:5,
  },
  opBadgeText: {
    fontSize:11, fontWeight:'600', color:DARK, letterSpacing:0.1,
  },
  spinWrap: {
    width:130, height:130,
    alignItems:'center', justifyContent:'center',
    marginBottom:26,
  },
  glow: {
    position:'absolute', width:86, height:86, borderRadius:43,
    backgroundColor:DARK_GLOW,
    shadowColor:'#000', shadowOffset:{width:0,height:0},
    shadowOpacity:0.15, shadowRadius:24,
  },
  orbitDotA: {
    position:'absolute', width:DOT_A, height:DOT_A, borderRadius:DOT_A/2,
    backgroundColor:'rgba(0,0,0,0.55)',
    shadowColor:'#000', shadowOffset:{width:0,height:0},
    shadowOpacity:0.4, shadowRadius:3,
  },
  orbitDotB: {
    position:'absolute', width:DOT_B, height:DOT_B, borderRadius:DOT_B/2,
    backgroundColor:'rgba(0,0,0,0.30)',
  },
  ripple: {
    position:'absolute', width:90, height:90, borderRadius:45, borderWidth:1.5,
  },
  confettiDot: {
    position:'absolute', width:6, height:6, borderRadius:3,
    backgroundColor:DARK,
    shadowColor:'#000', shadowOffset:{width:0,height:0},
    shadowOpacity:0.3, shadowRadius:4,
    left: SPIN_CTR - 3, top: SPIN_CTR - 3,
  },
  checkWrap: {
    position:'absolute', alignItems:'center', justifyContent:'center',
  },
  checkGlowRing: {
    position:'absolute', width:90, height:90, borderRadius:45,
    backgroundColor:'rgba(0,0,0,0.06)',
    shadowColor:'#000', shadowOffset:{width:0,height:0},
    shadowOpacity:0.18, shadowRadius:22,
  },
  checkCircle: {
    width:68, height:68, borderRadius:34,
    backgroundColor:DARK,
    alignItems:'center', justifyContent:'center',
    shadowColor:'#000', shadowOffset:{width:0,height:8},
    shadowOpacity:0.22, shadowRadius:18, elevation:14,
  },
  swapBadge: {
    position:'absolute', top:-4, right:-4,
    width:20, height:20, borderRadius:10,
    backgroundColor:'#2563EB',
    alignItems:'center', justifyContent:'center',
    borderWidth:2, borderColor:'#FFFFFF',
  },
  textBlock: { height:54, width:'100%', position:'relative', marginBottom:4 },
  title: {
    fontSize:19, fontWeight:'800', color:DARK,
    textAlign:'center', marginBottom:5, letterSpacing:0.1,
  },
  accent: { color:DARK, fontWeight:'800' },
  sub: {
    fontSize:12.5, color:'#6B7280',
    textAlign:'center', letterSpacing:0.2,
  },
  dotsRow: { flexDirection:'row', gap:10, alignItems:'center', marginTop:16 },
  dot: { width:7, height:7, borderRadius:3.5, backgroundColor:DARK },
});

// ─── Glass modal wrapper ────────────────────────────────────────────────────────
const GlassModal: React.FC<{
  visible: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}> = ({ visible, onClose, title, children, footer }) => (
  <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
    <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
      {/* Backdrop oscuro sólido */}
      <View style={[StyleSheet.absoluteFill, { backgroundColor: 'rgba(0,0,0,0.65)' }]} />
      <TouchableOpacity style={StyleSheet.absoluteFill} activeOpacity={1} onPress={onClose} />
      {/* Card blanca centrada */}
      <View style={s.modalOuter} pointerEvents="box-none">
        <View style={s.modalBox}>
          <Text style={s.modalTitle}>{title}</Text>
          <View style={s.modalDivider} />
          <ScrollView style={{ width: '100%' }} showsVerticalScrollIndicator={false} keyboardShouldPersistTaps="handled">
            {children}
          </ScrollView>
          {footer}
        </View>
      </View>
    </KeyboardAvoidingView>
  </Modal>
);


// ─── LivePairBadge — latido con ondas expansivas ──────────────────────────────
const LivePairBadge: React.FC = () => {
  const ring1Scale = useRef(new Animated.Value(1)).current;
  const ring1Op    = useRef(new Animated.Value(0)).current;
  const ring2Scale = useRef(new Animated.Value(1)).current;
  const ring2Op    = useRef(new Animated.Value(0)).current;
  const dotScale   = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    const pulse = () =>
      Animated.sequence([
        Animated.timing(dotScale, { toValue: 1.35, duration: 180, easing: Easing.out(Easing.ease), useNativeDriver: true }),
        Animated.timing(dotScale, { toValue: 1,    duration: 300, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
      ]);

    const wave = (scale: Animated.Value, op: Animated.Value, delay: number) =>
      Animated.loop(
        Animated.sequence([
          Animated.delay(delay),
          Animated.parallel([
            Animated.timing(scale, { toValue: 3.2, duration: 1400, easing: Easing.out(Easing.ease), useNativeDriver: true }),
            Animated.timing(op,    { toValue: 0,   duration: 1400, useNativeDriver: true }),
          ]),
          Animated.parallel([
            Animated.timing(scale, { toValue: 1, duration: 0, useNativeDriver: true }),
            Animated.timing(op,    { toValue: 0.55, duration: 0, useNativeDriver: true }),
          ]),
        ])
      );

    // Heartbeat loop: pulse dot + launch waves every ~2s
    const heartbeat = Animated.loop(
      Animated.sequence([
        pulse(),
        Animated.delay(1520),
      ])
    );

    ring1Op.setValue(0.55);
    ring2Op.setValue(0.55);

    heartbeat.start();
    wave(ring1Scale, ring1Op, 0).start();
    wave(ring2Scale, ring2Op, 520).start();

    return () => { heartbeat.stop(); };
  }, []);

  return (
    <View style={lpb.wrap}>
      {/* Ondas expansivas */}
      <Animated.View style={[lpb.ring, { opacity: ring1Op, transform: [{ scale: ring1Scale }] }]} />
      <Animated.View style={[lpb.ring, { opacity: ring2Op, transform: [{ scale: ring2Scale }] }]} />
      {/* Punto central */}
      <Animated.View style={[lpb.dot, { transform: [{ scale: dotScale }] }]} />
    </View>
  );
};

const lpb = StyleSheet.create({
  wrap: { width: 10, height: 10, alignItems: 'center', justifyContent: 'center' },
  dot:  { width: 6, height: 6, borderRadius: 3, backgroundColor: '#22c55e', position: 'absolute' },
  ring: {
    position: 'absolute',
    width: 6, height: 6, borderRadius: 3,
    borderWidth: 1, borderColor: '#22c55e',
  },
});

// ─── BsDividerAnim — partícula minimalista monocromática según operación ────────
const BsDividerAnim: React.FC<{ color: string }> = ({ color }) => {
  const pos = useRef(new Animated.Value(0)).current;
  const op  = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.loop(
      Animated.sequence([
        Animated.parallel([
          Animated.timing(pos, { toValue: 1, duration: 1000, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
          Animated.sequence([
            Animated.timing(op, { toValue: 0,   duration: 0,   useNativeDriver: true }),
            Animated.timing(op, { toValue: 0.9, duration: 200, useNativeDriver: true }),
            Animated.timing(op, { toValue: 0.9, duration: 600, useNativeDriver: true }),
            Animated.timing(op, { toValue: 0,   duration: 200, useNativeDriver: true }),
          ]),
        ]),
        Animated.timing(pos, { toValue: 0, duration: 0, useNativeDriver: true }),
        Animated.delay(300),
      ])
    ).start();
  }, [color]);

  const translateY = pos.interpolate({ inputRange: [0, 1], outputRange: [-18, 18] });

  return (
    <View style={bsd.wrap}>
      <View style={bsd.line} />
      <Animated.View style={[bsd.dot, {
        backgroundColor: color,
        shadowColor: color,
        opacity: op,
        transform: [{ translateY }],
      }]} />
    </View>
  );
};

const bsd = StyleSheet.create({
  wrap: { width: 20, alignSelf: 'stretch', alignItems: 'center', justifyContent: 'center' },
  line: { position: 'absolute', width: 1, top: 0, bottom: 0, backgroundColor: 'rgba(255,255,255,0.08)' },
  dot:  {
    position: 'absolute',
    width: 4, height: 4, borderRadius: 2,
    shadowOffset: { width: 0, height: 0 }, shadowOpacity: 1, shadowRadius: 4,
  },
});

// ─── Screen ────────────────────────────────────────────────────────────────────
export const NewOperationScreen: React.FC<Props> = ({ navigation, route }) => {
  const bg = useBackground();
  const { client, refreshClient } = useAuth();
  const isLegalEntity = client?.document_type === 'RUC';
  const insets = useSafeAreaInsets();

  // ── Exchange rates ─────────────────────────────────────────────────────────
  const [realExchangeRates, setRealExchangeRates] = useState({ compra: 3.75, venta: 3.77 });

  const params               = route?.params || {};
  const initialOperationType = params.operationType    || 'Compra';
  const initialAmount        = params.amountUSD        || '';
  const initialExchangeRate  = params.exchangeRate     || realExchangeRates.compra;
  const initialBaseRate      = params.baseExchangeRate || null;
  // Tasas mejoradas completas pasadas desde HomeScreen (evita inconsistencias por fetch propio)
  const paramRatesCompra     = params.ratesCompra      || null;
  const paramRatesVenta      = params.ratesVenta       || null;
  // ── Pips dinámicos por volumen ─────────────────────────────────────────────
  const CORPORATE_BASE_PIPS = 0.0010;
  const REFERRAL_IMPROVEMENT = 0.002;

  const [liveAmountUSD, setLiveAmountUSD] = useState(parseFloat(initialAmount) || 0);

  const getVolumePips = (usd: number): number => {
    if (usd >= 15000) return isLegalEntity ? 0.0020 : 0.0015;
    if (usd >= 5000)  return 0.0010;
    return 0;
  };

  const corporatePips = isLegalEntity ? CORPORATE_BASE_PIPS : 0;
  const volumePips    = getVolumePips(liveAmountUSD);

  // Haptic al cruzar umbral de mejora (sin animación de escala para evitar conflicto con flip clock)
  const prevPipTier = useRef(volumePips);
  useEffect(() => {
    if (volumePips !== prevPipTier.current) {
      prevPipTier.current = volumePips;
      if (volumePips > 0) Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    }
  }, [volumePips]);

  // Memoizado para que Calculator solo reciba un nuevo objeto cuando los valores realmente cambian
  const memoOverrideRates = useMemo(() => {
    if (couponApplied && couponRates) return couponRates;
    const totalPips = corporatePips + Math.max(volumePips, 0);
    if (totalPips === 0) return null;
    return {
      compra: realExchangeRates.compra + totalPips,
      venta:  realExchangeRates.venta  - totalPips,
    };
  }, [couponApplied, couponRates, corporatePips, volumePips, realExchangeRates.compra, realExchangeRates.venta]);

  // Si hay mejora de precio, showImprovement = true
  const hasImprovement = initialBaseRate !== null &&
    Math.abs(initialExchangeRate - initialBaseRate) > 0.0005;

  const [operationType,      setOperationType]      = useState<'Compra'|'Venta'>(initialOperationType);
  const [amountUsd,          setAmountUsd]          = useState(initialAmount);
  const [exchangeRate,       setExchangeRate]       = useState(initialExchangeRate.toString());
  const [sourceAccount,      setSourceAccount]      = useState('');
  const [destinationAccount, setDestinationAccount] = useState('');
  const [termsAccepted,      setTermsAccepted]      = useState(false);
  const [loading,            setLoading]            = useState(false);
  const [creatingVisible,    setCreatingVisible]    = useState(false);
  const [creatingSuccess,    setCreatingSuccess]    = useState(false);
  const [errors,             setErrors]             = useState<any>({});

  // ── Add bank account modal ─────────────────────────────────────────────────
  const [addAccountVisible,      setAddAccountVisible]      = useState(false);
  const [addAccountType,         setAddAccountType]         = useState<'source'|'destination'>('source');
  const [newAccountOrigen,       setNewAccountOrigen]       = useState('Lima');
  const [newAccountBank,         setNewAccountBank]         = useState('');
  const [newAccountBankCustom,   setNewAccountBankCustom]   = useState('');
  const [newAccountAccType,      setNewAccountAccType]      = useState('Ahorro');
  const [newAccountNumber,       setNewAccountNumber]       = useState('');
  const [newAccountCCI,          setNewAccountCCI]          = useState('');
  const [addingAccount,          setAddingAccount]          = useState(false);
  const [bankMenuVisible,        setBankMenuVisible]        = useState(false);

  // ── Account selection modals ───────────────────────────────────────────────
  const [sourceDialogVisible, setSourceDialogVisible]      = useState(false);
  const [destDialogVisible,   setDestDialogVisible]        = useState(false);

  // ── Coupon ─────────────────────────────────────────────────────────────────
  const [clientPips,         setClientPips]         = useState(0);
  const [pipsLoading,        setPipsLoading]        = useState(false);
  const [generatedRewardCode,setGeneratedRewardCode] = useState<string | null>(null);
  const [couponCode,         setCouponCode]         = useState('');
  const [couponApplied,      setCouponApplied]      = useState<string | null>(null);
  const [couponRates,        setCouponRates]        = useState<{compra:number; venta:number} | null>(null);
  const [couponValidating,   setCouponValidating]   = useState(false);
  const [couponModalVisible, setCouponModalVisible] = useState(false);

  const toastAnim = useRef(new Animated.Value(0)).current;
  const stepSpin  = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    Animated.loop(
      Animated.timing(stepSpin, { toValue: 1, duration: 1600, useNativeDriver: true, easing: Easing.linear })
    ).start();
  }, []);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const showMinAmountToast = () => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
    Animated.spring(toastAnim, { toValue: 1, useNativeDriver: true, damping: 18, stiffness: 200 }).start();
    toastTimer.current = setTimeout(() => {
      Animated.timing(toastAnim, { toValue: 0, duration: 260, useNativeDriver: true, easing: Easing.in(Easing.ease) }).start();
    }, 3000);
  };

  const accountsPEN = client?.bank_accounts?.filter(a => a && a.account_number && a.currency === 'S/') || [];
  const accountsUSD = client?.bank_accounts?.filter(a => a && a.account_number && a.currency === '$')  || [];

  // ── Fetch rates + pips disponibles ─────────────────────────────────────────
  useEffect(() => {
    (async () => {
      try {
        const res = await axios.get<{ success: boolean; rates: { compra: number; venta: number } }>(
          `${API_CONFIG.BASE_URL}/api/client/exchange-rates`
        );
        if (res.data.success) {
          setRealExchangeRates(res.data.rates);
          // Solo actualizar la tasa si no vienen tasas mejoradas desde HomeScreen
          if (!paramRatesCompra && !paramRatesVenta && !params.exchangeRate) {
            const rate = initialOperationType === 'Compra' ? res.data.rates.compra : res.data.rates.venta;
            setExchangeRate(rate.toString());
          }
        }
      } catch {}
    })();
    // Cargar pips disponibles del cliente
    if (client?.dni) {
      fetch(`${API_CONFIG.BASE_URL}/api/referrals/stats/${client.dni}`)
        .then(r => r.json())
        .then(d => { if (d.success) setClientPips(d.pips_available || 0); })
        .catch(() => {});
    }
  }, []);

  useEffect(() => {
    // Usar tasas de HomeScreen si están disponibles (garantiza consistencia visual)
    // Si no, usar fetch propio
    const compra = paramRatesCompra ?? realExchangeRates.compra;
    const venta  = paramRatesVenta  ?? realExchangeRates.venta;
    const rate   = operationType === 'Compra' ? compra : venta;
    setExchangeRate(rate.toString());
    setSourceAccount('');
    setDestinationAccount('');
  }, [operationType, realExchangeRates]);

  // ── Calculations ───────────────────────────────────────────────────────────
  // amountUsd es SIEMPRE el monto en USD. El equivalente en soles es siempre amt * rate.
  const calculatePEN = () => {
    if (!amountUsd || !exchangeRate) return 0;
    const amt  = parseFloat(amountUsd);
    const rate = parseFloat(exchangeRate);
    return parseFloat((amt * rate).toFixed(2));
  };

  const inputCurrency  = operationType === 'Compra' ? 'USD' : 'PEN';
  const outputCurrency = operationType === 'Compra' ? 'PEN' : 'USD';
  // Compra: cliente envía USD, recibe PEN. Venta: cliente envía PEN, recibe USD.
  const amountToSend    = operationType === 'Compra' ? parseFloat(amountUsd) || 0 : calculatePEN();
  const amountToReceive = operationType === 'Compra' ? calculatePEN() : parseFloat(amountUsd) || 0;

  const renderAccountOption = (acc: BankAccount) =>
    `${acc.bank_name} (${acc.currency}) ****${acc.account_number.slice(-4)}`;

  const renderAccountOptionFull = (acc: BankAccount) =>
    `${acc.bank_name} · ${acc.account_type} (${acc.currency}) · ****${acc.account_number.slice(-4)}`;

  const getSourceText = () => {
    if (!sourceAccount) return null;
    const accs = operationType === 'Venta' ? accountsPEN : accountsUSD;
    const sel  = accs.find(a => a.account_number === sourceAccount);
    return sel ? renderAccountOption(sel) : null;
  };

  const getDestText = () => {
    if (!destinationAccount) return null;
    const accs = operationType === 'Venta' ? accountsUSD : accountsPEN;
    const sel  = accs.find(a => a.account_number === destinationAccount);
    return sel ? renderAccountOption(sel) : null;
  };

  // ── Validate ───────────────────────────────────────────────────────────────
  const validate = () => {
    const e: any = {};
    if (!amountUsd || parseFloat(amountUsd) <= 0) e.amountUsd = 'Ingrese un monto válido';
    else if (parseFloat(amountUsd) < 50) { showMinAmountToast(); return false; }
    if (!exchangeRate || parseFloat(exchangeRate) <= 0) e.exchangeRate = 'Ingrese un tipo de cambio válido';
    if (!sourceAccount)      e.sourceAccount      = 'Seleccione cuenta de origen';
    if (!destinationAccount) e.destinationAccount = 'Seleccione cuenta de destino';
    if (!termsAccepted)      e.termsAccepted      = 'Debe aceptar la declaración para continuar';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  // ── Submit ─────────────────────────────────────────────────────────────────
  const handleSubmit = async () => {
    if (!validate() || !client) return;

    if (!client.has_complete_documents) {
      const isNatural = client.document_type === 'DNI' || client.document_type === 'CE';
      const hasUploaded = isNatural
        ? (client.dni_front_url && client.dni_back_url)
        : (client.dni_representante_front_url && client.dni_representante_back_url);

      if (!hasUploaded) {
        Alert.alert(
          'Validación de Identidad Requerida',
          'Necesitamos validar tu DNI antes de iniciar una operación.\n\nPor favor, sube las fotos de tu DNI desde la pantalla de inicio.',
          [{ text: 'Entendido', onPress: () => navigation.navigate('HomeTab') }]
        );
      } else {
        Alert.alert(
          'Validación en Proceso',
          'Nuestro equipo está validando tus documentos.\n\n⏱️ Tiempo promedio: 10 minutos\n\nTe notificaremos cuando tu cuenta sea activada.',
          [{ text: 'Entendido', onPress: () => navigation.navigate('HomeTab') }]
        );
      }
      return;
    }

    setLoading(true);
    setCreatingVisible(true);
    setCreatingSuccess(false);

    const delay = (ms: number) => new Promise<void>(r => setTimeout(r, ms));

    // Toda la lógica de API encapsulada — nunca lanza, devuelve resultado o error
    const apiWork = async (): Promise<{ op?: any; activeId?: string; err?: string }> => {
      try {
        const res = await axios.get(`${API_CONFIG.BASE_URL}/api/client/my-operations/${client!.dni}`);
        if (res.data.success) {
          const active = res.data.operations.filter(
            (op: any) => op.status === 'pendiente' || op.status === 'en_proceso'
          );
          if (active.length > 0) return { activeId: active[0].operation_id };
        }
        const operationData: CreateOperationForm = {
          operation_type: operationType,
          amount_usd: amountUsd,
          exchange_rate: exchangeRate,
          source_account: sourceAccount,
          destination_account: destinationAccount,
          terms_accepted: termsAccepted,
          notes: '',
          ...(generatedRewardCode ? { coupon_code: generatedRewardCode } : {}),
        };
        const op = await operationsApi.createOperation(client!.dni, operationData);
        return { op };
      } catch (e: any) {
        return { err: e.message || 'Error al crear operación' };
      }
    };

    // Promise.all garantiza: logo visible MÍNIMO 1700ms sin importar qué tan rápida sea la API
    const [result] = await Promise.all([apiWork(), delay(1700)]);

    if (result.activeId) {
      setCreatingVisible(false);
      setLoading(false);
      Alert.alert('Operación en curso', `Ya tienes una operación activa (${result.activeId}). Completa o cancela tu operación actual antes de crear una nueva.`, [{ text: 'Entendido' }]);
      return;
    }
    if (result.err) {
      setCreatingVisible(false);
      setLoading(false);
      Alert.alert('Error', result.err);
      return;
    }

    // Logo fue visible exactamente ≥1700ms — ahora mostrar check
    setCreatingSuccess(true);

    // Check visible mínimo 1600ms antes de navegar
    await delay(1200);
    // Sonido de confirmación en el último instante de la animación
    try {
      const player = createAudioPlayer(require('../../assets/sounds/payment_success.mp3'));
      player.volume = 0.8;
      player.play();
    } catch {}
    await delay(400);
    navigation.replace('Transfer', { operation: result.op });
  };

  // ── Add bank account ───────────────────────────────────────────────────────
  const openAddAccount = (type: 'source'|'destination') => {
    if ((client?.bank_accounts?.length ?? 0) >= 6) {
      Alert.alert(
        'Límite alcanzado',
        'Ya tienes 6 cuentas bancarias registradas, que es el máximo permitido. Ve a tu Perfil para gestionar o eliminar cuentas.',
        [{ text: 'Entendido' }]
      );
      return;
    }
    setAddAccountType(type);
    setNewAccountOrigen('Lima'); setNewAccountBank(''); setNewAccountBankCustom('');
    setNewAccountAccType('Ahorro'); setNewAccountNumber(''); setNewAccountCCI('');
    setBankMenuVisible(false);
    setAddAccountVisible(true);
  };

  const closeAddAccount = () => {
    setBankMenuVisible(false);
    setAddAccountVisible(false);
  };

  // ── Validate coupon ────────────────────────────────────────────────────────
  const handleValidateCoupon = async () => {
    const code = couponCode.trim().toUpperCase();
    if (!code) return;
    setCouponValidating(true);
    try {
      const res = await fetch(`${API_CONFIG.BASE_URL}/api/referrals/validate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code, client_dni: client?.dni }),
      });
      const data = await res.json();
      if (data.is_valid) {
        const improvedCompra = realExchangeRates.compra + REFERRAL_IMPROVEMENT;
        const improvedVenta  = realExchangeRates.venta  - REFERRAL_IMPROVEMENT;
        setCouponApplied(code);
        setCouponRates({ compra: improvedCompra, venta: improvedVenta });
        const improved = operationType === 'Compra' ? improvedCompra : improvedVenta;
        setExchangeRate(improved.toFixed(4));
        setCouponModalVisible(false);
      } else {
        Alert.alert('Cupón inválido', data.message || 'El código no es válido');
      }
    } catch {
      Alert.alert('Error', 'No se pudo validar el cupón. Intenta nuevamente.');
    } finally {
      setCouponValidating(false);
    }
  };

  // ── Aplicar pips directamente ──────────────────────────────────────────────
  const handleUsePips = async () => {
    if (!client || pipsLoading || couponApplied) return;
    setPipsLoading(true);
    try {
      const res = await fetch(`${API_CONFIG.BASE_URL}/api/referrals/generate-reward-code`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ client_dni: client.dni }),
      });
      const data = await res.json();
      if (data.success && data.improvement && data.reward_code) {
        const pip = data.improvement as number;
        const improvedCompra = realExchangeRates.compra + pip;
        const improvedVenta  = realExchangeRates.venta  - pip;
        const pipsDisplay = Math.round(pip * 10000);
        setGeneratedRewardCode(data.reward_code.code);
        setCouponApplied(`★ ${pipsDisplay} pips`);
        setCouponRates({ compra: improvedCompra, venta: improvedVenta });
        const improved = operationType === 'Compra' ? improvedCompra : improvedVenta;
        setExchangeRate(improved.toFixed(4));
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      } else {
        Alert.alert('Sin pips', data.message || 'No se pudieron aplicar los pips');
      }
    } catch {
      Alert.alert('Error', 'No se pudo conectar. Intenta nuevamente.');
    } finally {
      setPipsLoading(false);
    }
  };

  const getAvailableBanks = () => newAccountOrigen === 'Lima' ? BANKS_LIMA : BANKS_PROVINCIA;
  const needsCCI = () => !['BCP','INTERBANK','PICHINCHA','BANBIF'].includes(newAccountBank);

  const handleAddBankAccount = async () => {
    if (!client) return;
    if (!newAccountBank) { Alert.alert('Error','Seleccione un banco'); return; }
    if (newAccountBank === 'Otros' && !newAccountBankCustom.trim()) { Alert.alert('Error','Ingrese el nombre del banco'); return; }
    if (needsCCI() && (!newAccountCCI || newAccountCCI.length !== 20)) { Alert.alert('Error','Ingrese el CCI de 20 dígitos'); return; }
    if (!needsCCI() && !newAccountNumber) { Alert.alert('Error','Ingrese el número de cuenta'); return; }
    try {
      setAddingAccount(true);
      const isUSD = (operationType === 'Compra' && addAccountType === 'source') ||
                    (operationType === 'Venta'  && addAccountType === 'destination');
      const currency    = isUSD ? '$' : 'S/';
      const bankName    = newAccountBank === 'Otros' ? newAccountBankCustom.trim() : newAccountBank;
      const response    = await fetch(`${API_CONFIG.BASE_URL}/api/client/add-bank-account/${client.dni}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          origen: newAccountOrigen, bank_name: bankName,
          account_type: newAccountAccType, currency,
          account_number: needsCCI() ? newAccountCCI : newAccountNumber,
          cci: needsCCI() ? newAccountCCI : undefined,
        }),
      });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.message || 'Error al agregar cuenta');
      if (refreshClient) await refreshClient();
      Alert.alert('Éxito','Cuenta bancaria agregada exitosamente');
      closeAddAccount();
    } catch (error: any) {
      Alert.alert('Error', error.message || 'Error al agregar cuenta bancaria');
    } finally { setAddingAccount(false); }
  };

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <View style={s.root}>
      <View style={[StyleSheet.absoluteFill, { backgroundColor: '#F5F7FA' }]} pointerEvents="none" />

      {/* ── Header fijo ── */}
      <View style={[s.pageHeader, { paddingTop: insets.top + 10 }]}>
        <TouchableOpacity style={s.backBtn} onPress={() => navigation.goBack()} activeOpacity={0.75}>
          <Ionicons name="chevron-back" size={20} color="#0D1117" />
        </TouchableOpacity>
        <View style={s.headerCenter}>
          <View style={{ alignItems: 'center' }}>
            <Image source={require('../../assets/qc.png')} style={s.headerLogo} resizeMode="contain" />
            {isLegalEntity && (
              <Text style={s.corporateLabel}>corporate</Text>
            )}
          </View>
        </View>
        <View style={{ width: 38 }} />
      </View>

      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        <ScrollView
          contentContainerStyle={[s.scroll, { paddingTop: 12, paddingBottom: insets.bottom + 100 }]}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >

          {/* ── Stepper ── */}
          <MotiView
            from={{ opacity: 0, translateY: -6 }}
            animate={{ opacity: 1, translateY: 0 }}
            transition={{ type: 'spring', delay: 65, damping: 24, stiffness: 220 }}
          >
            <View style={s.stepperWrap}>
              {/* Paso 1 — activo: Cotiza */}
              <View style={s.step}>
                <View style={s.stepDotActiveWrap}>
                  <View style={s.stepArcTrack} />
                  <Animated.View style={[s.stepArcSpin, {
                    transform: [{ rotate: stepSpin.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '360deg'] }) }],
                  }]} />
                  <View style={[s.stepDot, s.stepDotActive]}>
                    <Ionicons name="receipt-outline" size={12} color="#fff" />
                  </View>
                </View>
                <Text style={[s.stepLabel, s.stepLabelActive]}>Cotiza</Text>
              </View>
              <View style={s.stepLine} />
              {/* Paso 2 — pendiente: Transfiere */}
              <View style={s.step}>
                <View style={s.stepDot}>
                  <Ionicons name="swap-horizontal" size={12} color="#9CA3AF" />
                </View>
                <Text style={s.stepLabel}>Transfiere</Text>
              </View>
              <View style={s.stepLine} />
              {/* Paso 3 — pendiente: Recibe */}
              <View style={s.step}>
                <View style={s.stepDot}>
                  <Ionicons name="gift-outline" size={12} color="#9CA3AF" />
                </View>
                <Text style={s.stepLabel}>Recibe</Text>
              </View>
            </View>
          </MotiView>

          {/* ── Calculadora ── */}
          <MotiView
            from={{ opacity: 0, translateY: 12 }}
            animate={{ opacity: 1, translateY: 0 }}
            transition={{ type: 'spring', delay: 90, damping: 22, stiffness: 200 }}
          >
            <View style={s.calcCard}>
              <Calculator
                externalOperationType={operationType}
                onOperationTypeChange={(tipo) => {
                  setOperationType(tipo);
                  setSourceAccount('');
                  setDestinationAccount('');
                }}
                onAmountChange={(_isReady, tipo, amount, rate) => {
                  setAmountUsd(amount);
                  setExchangeRate(rate.toString());
                  setLiveAmountUSD(parseFloat(amount) || 0);
                  if (tipo !== operationType) {
                    setOperationType(tipo);
                    setSourceAccount('');
                    setDestinationAccount('');
                  }
                }}
                overrideRates={memoOverrideRates}
                showStrikeRate={corporatePips > 0 || volumePips > 0 || !!couponApplied}
              />
            </View>
          </MotiView>

          {/* ── Cupón ── */}
          <MotiView
            from={{ opacity: 0, translateY: 6 }}
            animate={{ opacity: 1, translateY: 0 }}
            transition={{ type: 'spring', delay: 160, damping: 22, stiffness: 200 }}
          >
            {couponApplied ? (
              <View style={s.couponAppliedRow}>
                <View style={s.couponAppliedBadge}>
                  <Ionicons name="pricetag" size={11} color="#16a34a" />
                  <Text style={s.couponAppliedTxt}>
                    {couponApplied?.startsWith('★')
                      ? `${couponApplied} aplicados`
                      : `Cupón ${couponApplied} · mejora aplicada`}
                  </Text>
                </View>
                <TouchableOpacity
                  onPress={() => {
                    setCouponApplied(null);
                    setCouponRates(null);
                    setCouponCode('');
                    setGeneratedRewardCode(null);
                    const baseRate = operationType === 'Compra' ? realExchangeRates.compra : realExchangeRates.venta;
                    setExchangeRate(baseRate.toString());
                  }}
                  activeOpacity={0.7}
                >
                  <Ionicons name="close-circle" size={16} color="#9CA3AF" />
                </TouchableOpacity>
              </View>
            ) : (
              <>
                <TouchableOpacity
                  style={s.couponBtn}
                  onPress={() => { Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light); setCouponModalVisible(true); }}
                  activeOpacity={0.75}
                >
                  <Ionicons name="pricetag-outline" size={13} color="#6B7280" />
                  <Text style={s.couponBtnTxt}>¿Tienes un cupón de descuento?</Text>
                  <Ionicons name="chevron-forward" size={12} color="rgba(0,0,0,0.25)" style={{ marginLeft: 'auto' }} />
                </TouchableOpacity>
                {clientPips > 0 && (
                  <View style={s.pipsRow}>
                    <TouchableOpacity
                      style={[s.pipsBtn, { flex: 1 }]}
                      onPress={handleUsePips}
                      disabled={pipsLoading}
                      activeOpacity={0.75}
                    >
                      <Ionicons name="star" size={13} color="#fff" />
                      <Text style={s.pipsBtnTxt}>
                        {Math.round(clientPips * 10000)} pips disponibles
                      </Text>
                      <View style={s.pipsBtnAction}>
                        {pipsLoading
                          ? <ActivityIndicator size="small" color="#fff" style={{ width: 36 }} />
                          : <Text style={s.pipsBtnActionTxt}>Aplicar</Text>
                        }
                      </View>
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={s.pipsInfoBtn}
                      onPress={() => Alert.alert(
                        '¿Qué son los pips?',
                        `Tienes ${Math.round(clientPips * 10000)} pips acumulados como premio por referir clientes a Qoricash.

Puedes canjearlos sin importar la cantidad que tengas. El máximo aplicable por operación es de 30 pips.

Si tienes más de 30, el excedente queda disponible para tu próxima operación.`,
                        [{ text: 'Entendido' }]
                      )}
                      activeOpacity={0.7}
                    >
                      <Ionicons name="help-circle-outline" size={20} color="#6B7280" />
                    </TouchableOpacity>
                  </View>
                )}
              </>
            )}
          </MotiView>

          {/* ── Cuentas ── */}
          <MotiView
            from={{ opacity: 0, translateY: 16 }}
            animate={{ opacity: 1, translateY: 0 }}
            transition={{ type: 'spring', delay: 280, damping: 22, stiffness: 180 }}
          >
            <Text style={s.sectionLabel}>Selecciona tus cuentas bancarias</Text>
            <View style={s.accountsCard}>

              {/* Cuenta cargo */}
              <View style={s.accountBlock}>
                <View style={s.accountMeta}>
                  <Text style={s.accountRoleLabel}>Cuenta de origen</Text>
                  <Text style={s.accountRoleSub}>{operationType === 'Venta' ? 'S/ Soles' : '$ Dólares'}</Text>
                </View>
                <TouchableOpacity
                  style={[s.accountSelector, errors.sourceAccount && s.accountSelectorErr]}
                  onPress={() => setSourceDialogVisible(true)}
                  activeOpacity={0.78}
                >
                  <Ionicons name="card-outline" size={14} color={getSourceText() ? 'rgba(0,0,0,0.55)' : 'rgba(0,0,0,0.25)'} />
                  {getSourceText()
                    ? <Text style={s.accountSelectorTxt} numberOfLines={1}>{getSourceText()}</Text>
                    : <Text style={s.accountSelectorPh}>Seleccionar cuenta...</Text>
                  }
                  <Ionicons name="chevron-down" size={13} color="rgba(0,0,0,0.30)" />
                </TouchableOpacity>
                <TouchableOpacity style={s.addMicroBtn} onPress={() => openAddAccount('source')} activeOpacity={0.75}>
                  <Ionicons name="add" size={14} color="#fff" />
                </TouchableOpacity>
              </View>
              {errors.sourceAccount && <Text style={s.errorTxt}>{errors.sourceAccount}</Text>}

              <View style={s.accountDivider} />

              {/* Cuenta abono */}
              <View style={s.accountBlock}>
                <View style={s.accountMeta}>
                  <Text style={s.accountRoleLabel}>Cuenta de destino</Text>
                  <Text style={s.accountRoleSub}>{operationType === 'Venta' ? '$ Dólares' : 'S/ Soles'}</Text>
                </View>
                <TouchableOpacity
                  style={[s.accountSelector, errors.destinationAccount && s.accountSelectorErr]}
                  onPress={() => setDestDialogVisible(true)}
                  activeOpacity={0.78}
                >
                  <Ionicons name="card-outline" size={14} color={getDestText() ? 'rgba(0,0,0,0.55)' : 'rgba(0,0,0,0.25)'} />
                  {getDestText()
                    ? <Text style={s.accountSelectorTxt} numberOfLines={1}>{getDestText()}</Text>
                    : <Text style={s.accountSelectorPh}>Seleccionar cuenta...</Text>
                  }
                  <Ionicons name="chevron-down" size={13} color="rgba(0,0,0,0.30)" />
                </TouchableOpacity>
                <TouchableOpacity style={s.addMicroBtn} onPress={() => openAddAccount('destination')} activeOpacity={0.75}>
                  <Ionicons name="add" size={14} color="#fff" />
                </TouchableOpacity>
              </View>
              {errors.destinationAccount && <Text style={s.errorTxt}>{errors.destinationAccount}</Text>}
            </View>
          </MotiView>

          {/* ── Declaración ── */}
          <MotiView
            from={{ opacity: 0, translateY: 14 }}
            animate={{ opacity: 1, translateY: 0 }}
            transition={{ type: 'spring', delay: 340, damping: 22, stiffness: 180 }}
          >
            <TouchableOpacity
              style={s.declarationRow}
              onPress={() => { Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light); setTermsAccepted(!termsAccepted); setErrors({ ...errors, termsAccepted: '' }); }}
              activeOpacity={0.82}
            >
              <View style={[s.checkbox, termsAccepted && s.checkboxOn]}>
                {termsAccepted && <Ionicons name="checkmark" size={12} color="#fff" />}
              </View>
              <Text style={s.declarationTxt}>
                Declaro que los fondos provienen de actividades lícitas y que soy titular de las cuentas bancarias registradas.
              </Text>
            </TouchableOpacity>
            {errors.termsAccepted && <Text style={[s.errorTxt, { marginTop: 6, marginLeft: 34 }]}>{errors.termsAccepted}</Text>}
          </MotiView>

          {/* ── Ejecutar orden ── */}
          <MotiView
            from={{ opacity: 0, translateY: 20, scale: 0.95 }}
            animate={{ opacity: 1, translateY: 0, scale: 1 }}
            transition={{ type: 'spring', delay: 400, damping: 20, stiffness: 180 }}
          >
            <TouchableOpacity
              style={[
                s.execBtn,
                !(amountUsd && sourceAccount && destinationAccount && termsAccepted) && s.execBtnDim,
              ]}
              onPress={() => { Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium); handleSubmit(); }}
              disabled={loading || !amountUsd || !sourceAccount || !destinationAccount || !termsAccepted}
              activeOpacity={0.82}
            >
              {loading
                ? <ActivityIndicator color="#fff" size="small" />
                : <Text style={s.execTxt}>CREAR OPERACIÓN</Text>
              }
            </TouchableOpacity>
          </MotiView>
        </ScrollView>
      </KeyboardAvoidingView>

      {/* ══ Modal: Agregar cuenta bancaria ════════════════════════════════════ */}
      <GlassModal
        visible={addAccountVisible}
        onClose={closeAddAccount}
        title="Agregar Cuenta Bancaria"
        footer={
          <View style={s.modalFooter}>
            <TouchableOpacity style={s.modalBtnSec} onPress={closeAddAccount}>
              <Text style={s.modalBtnSecTxt}>Cancelar</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[s.modalBtnPri, (addingAccount || !newAccountBank) && { opacity: 0.4 }]}
              onPress={handleAddBankAccount}
              disabled={addingAccount || !newAccountBank}
            >
              {addingAccount
                ? <ActivityIndicator color="#fff" size="small" />
                : <Text style={s.modalBtnPriTxt}>Agregar</Text>
              }
            </TouchableOpacity>
          </View>
        }
      >
        <View style={s.modalBody}>
          <Text style={s.inputLabel}>¿En qué plaza se aperturó su cuenta?</Text>
          <Seg options={['Lima','Provincia']} value={newAccountOrigen} onChange={v => { setNewAccountOrigen(v); setNewAccountBank(''); }} />

          {newAccountOrigen === 'Provincia' && (
            <View style={s.infoBox}>
              <Ionicons name="information-circle-outline" size={14} color="#fbbf24" />
              <Text style={s.infoBoxTxt}>Para provincia solo operamos con BCP e INTERBANK</Text>
            </View>
          )}

          <Text style={s.inputLabel}>Elige tu banco</Text>
          <TouchableOpacity style={s.inputRow} onPress={() => setBankMenuVisible(v => !v)} activeOpacity={0.78}>
            <Text style={[s.inputField, !newAccountBank && { color: 'rgba(255,255,255,0.25)' }]}>
              {newAccountBank || 'Seleccionar banco...'}
            </Text>
            <Ionicons name={bankMenuVisible ? 'chevron-up' : 'chevron-down'} size={16} color="rgba(255,255,255,0.4)" />
          </TouchableOpacity>
          {bankMenuVisible && (
            <View style={s.inlineMenu}>
              {getAvailableBanks().map(bank => (
                <TouchableOpacity
                  key={bank}
                  style={s.inlineMenuItem}
                  onPress={() => { Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light); setNewAccountBank(bank); setNewAccountBankCustom(''); setBankMenuVisible(false); }}
                  activeOpacity={0.75}
                >
                  <Text style={[s.inlineMenuTxt, newAccountBank === bank && { color: GREEN }]}>{bank}</Text>
                  {newAccountBank === bank && <Ionicons name="checkmark" size={14} color={GREEN} />}
                </TouchableOpacity>
              ))}
            </View>
          )}

          {newAccountBank === 'Otros' && (
            <>
              <Text style={s.inputLabel}>Nombre del banco</Text>
              <View style={s.inputRow}>
                <TextInput style={s.inputField} value={newAccountBankCustom} onChangeText={setNewAccountBankCustom} placeholder="Ej: Banco de la Nación" placeholderTextColor="rgba(255,255,255,0.25)" />
              </View>
            </>
          )}

          <Text style={s.inputLabel}>Tipo de cuenta</Text>
          <Seg options={['Ahorro','Corriente']} value={newAccountAccType} onChange={setNewAccountAccType} />

          {/* Account number label — hidden when no bank selected */}
          <Text style={[s.inputLabel, !newAccountBank && { display: 'none' }]}>
            {needsCCI() ? 'CCI (20 dígitos)' : 'Número de cuenta'}
          </Text>
          {/* Non-CCI banks: BCP, INTERBANK, PICHINCHA, BANBIF — always mounted, hidden via display:none */}
          <TextInput
            style={[s.textInputStandalone, (needsCCI() || !newAccountBank) && { display: 'none' }]}
            value={newAccountNumber}
            onChangeText={setNewAccountNumber}
            keyboardType="numeric"
            placeholder="Número de cuenta"
            placeholderTextColor="rgba(255,255,255,0.25)"
            autoCorrect={false}
            autoCapitalize="none"
          />
          {/* CCI banks: BBVA, Scotiabank, Otros — always mounted, hidden via display:none */}
          <TextInput
            style={[s.textInputStandalone, (!needsCCI() || !newAccountBank) && { display: 'none' }]}
            value={newAccountCCI}
            onChangeText={setNewAccountCCI}
            keyboardType="numeric"
            maxLength={20}
            placeholder="00000000000000000000"
            placeholderTextColor="rgba(255,255,255,0.25)"
            autoCorrect={false}
            autoCapitalize="none"
          />

          <View style={[s.infoBox, { marginTop: 16, backgroundColor: '#fff', borderColor: 'rgba(0,0,0,0.12)' }]}>
            <Ionicons name="wallet-outline" size={14} color="#0D1117" />
            <Text style={[s.infoBoxTxt, { color: '#0D1117' }]}>
              Moneda:{' '}
              {(operationType === 'Compra' && addAccountType === 'source') ||
               (operationType === 'Venta'  && addAccountType === 'destination')
                ? 'Dólares ($)'
                : 'Soles (S/)'}
            </Text>
          </View>
        </View>
      </GlassModal>


      {/* ══ Modal: Cuenta origen ═══════════════════════════════════════════════ */}
      <GlassModal
        visible={sourceDialogVisible}
        onClose={() => setSourceDialogVisible(false)}
        title={`Cuenta de cargo (${operationType === 'Venta' ? 'S/' : 'USD'})`}
        footer={
          <View style={s.modalFooter}>
            <TouchableOpacity style={[s.modalBtnSec, { flex: undefined, width: '100%' }]} onPress={() => setSourceDialogVisible(false)}>
              <Text style={s.modalBtnSecTxt}>Cerrar</Text>
            </TouchableOpacity>
          </View>
        }
      >
        <View style={s.modalBody}>
          {(operationType === 'Venta' ? accountsPEN : accountsUSD).length === 0 ? (
            <Text style={s.emptyTxt}>No tienes cuentas en {operationType === 'Venta' ? 'soles' : 'dólares'}. Agrega una primero.</Text>
          ) : (
            (operationType === 'Venta' ? accountsPEN : accountsUSD).map((acc, i, arr) => (
              <TouchableOpacity
                key={i}
                style={[s.bankItem, sourceAccount === acc.account_number && s.bankItemActive, i === arr.length - 1 && { borderBottomWidth: 0 }]}
                onPress={() => { Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light); setSourceAccount(acc.account_number); setErrors({ ...errors, sourceAccount: '' }); setSourceDialogVisible(false); }}
                activeOpacity={0.75}
              >
                <Ionicons name="card-outline" size={16} color={sourceAccount === acc.account_number ? GREEN : 'rgba(0,0,0,0.35)'} />
                <Text style={[s.bankItemTxt, sourceAccount === acc.account_number && { color: GREEN }]} numberOfLines={1}>
                  {renderAccountOptionFull(acc)}
                </Text>
                {sourceAccount === acc.account_number && <Ionicons name="checkmark" size={16} color={GREEN} style={{ marginLeft: 'auto' }} />}
              </TouchableOpacity>
            ))
          )}
        </View>
      </GlassModal>

      {/* ══ Modal: Cuenta destino ═══════════════════════════════════════════════ */}
      <GlassModal
        visible={destDialogVisible}
        onClose={() => setDestDialogVisible(false)}
        title={`Cuenta de destino (${operationType === 'Venta' ? 'USD' : 'S/'})`}
        footer={
          <View style={s.modalFooter}>
            <TouchableOpacity style={[s.modalBtnSec, { flex: undefined, width: '100%' }]} onPress={() => setDestDialogVisible(false)}>
              <Text style={s.modalBtnSecTxt}>Cerrar</Text>
            </TouchableOpacity>
          </View>
        }
      >
        <View style={s.modalBody}>
          {(operationType === 'Venta' ? accountsUSD : accountsPEN).length === 0 ? (
            <Text style={s.emptyTxt}>No tienes cuentas en {operationType === 'Venta' ? 'dólares' : 'soles'}. Agrega una primero.</Text>
          ) : (
            (operationType === 'Venta' ? accountsUSD : accountsPEN).map((acc, i, arr) => (
              <TouchableOpacity
                key={i}
                style={[s.bankItem, destinationAccount === acc.account_number && s.bankItemActive, i === arr.length - 1 && { borderBottomWidth: 0 }]}
                onPress={() => { Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light); setDestinationAccount(acc.account_number); setErrors({ ...errors, destinationAccount: '' }); setDestDialogVisible(false); }}
                activeOpacity={0.75}
              >
                <Ionicons name="card-outline" size={16} color={destinationAccount === acc.account_number ? GREEN : 'rgba(0,0,0,0.35)'} />
                <Text style={[s.bankItemTxt, destinationAccount === acc.account_number && { color: GREEN }]} numberOfLines={1}>
                  {renderAccountOptionFull(acc)}
                </Text>
                {destinationAccount === acc.account_number && <Ionicons name="checkmark" size={16} color={GREEN} style={{ marginLeft: 'auto' }} />}
              </TouchableOpacity>
            ))
          )}
        </View>
      </GlassModal>

      {/* ══ Modal: Cupón ═════════════════════════════════════════════════════ */}
      <Modal
        visible={couponModalVisible}
        transparent
        animationType="fade"
        onRequestClose={() => setCouponModalVisible(false)}
      >
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={{ flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24, backgroundColor: 'rgba(0,0,0,0.55)' }}
        >
          <TouchableOpacity style={StyleSheet.absoluteFill} activeOpacity={1} onPress={() => setCouponModalVisible(false)} />
          <View style={s.couponModal}>
            <View style={s.couponModalHeader}>
              <View style={s.couponModalIconWrap}>
                <Ionicons name="pricetag-outline" size={18} color="#FFFFFF" />
              </View>
              <Text style={s.couponModalTitle}>Ingresa tu cupón</Text>
              <TouchableOpacity onPress={() => setCouponModalVisible(false)} style={{ padding: 4 }}>
                <Ionicons name="close" size={20} color="rgba(255,255,255,0.6)" />
              </TouchableOpacity>
            </View>
            <View style={s.couponModalBody}>
              <Text style={s.couponModalSub}>
                Ingresa tu cupón o código de referido para desbloquear una mejora exclusiva en tu tipo de cambio.
              </Text>
              <TextInput
                style={s.couponModalInput}
                value={couponCode}
                onChangeText={t => setCouponCode(t.toUpperCase())}
                placeholder="Ej: ABC123"
                placeholderTextColor="#C4C9D4"
                autoCapitalize="characters"
                maxLength={8}
              />
              <TouchableOpacity
                style={[s.couponModalBtn, (!couponCode.trim() || couponValidating) && { opacity: 0.4 }]}
                onPress={handleValidateCoupon}
                disabled={!couponCode.trim() || couponValidating}
                activeOpacity={0.85}
              >
                <Text style={s.couponModalBtnTxt}>{couponValidating ? 'Validando...' : 'Aplicar código'}</Text>
              </TouchableOpacity>
            </View>
          </View>
        </KeyboardAvoidingView>
      </Modal>

      {/* ══ Creating operation overlay ═════════════════════════════════════ */}
      <CreatingOverlay visible={creatingVisible} success={creatingSuccess} />

      {/* ── Toast importe mínimo ── */}
      <Animated.View
        style={[s.minToast, {
          opacity: toastAnim,
          transform: [{ translateY: toastAnim.interpolate({ inputRange: [0, 1], outputRange: [16, 0] }) }],
        }]}
        pointerEvents="none"
      >
        <Ionicons name="information-circle" size={17} color="#FFFFFF" />
        <Text style={s.minToastTxt}>Para operar el importe mínimo es de $ 50.00</Text>
      </Animated.View>

    </View>
  );
};

// ─── Styles ────────────────────────────────────────────────────────────────────
const s = StyleSheet.create({
  root:    { flex: 1 },
  minToast: {
    position: 'absolute', bottom: 100, alignSelf: 'center',
    flexDirection: 'row', alignItems: 'center', gap: 8,
    backgroundColor: '#0D1117', borderRadius: 14,
    paddingVertical: 12, paddingHorizontal: 18,
    shadowColor: '#000', shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.22, shadowRadius: 12, elevation: 10,
  },
  minToastTxt: { fontSize: 13, fontWeight: '600', color: '#FFFFFF' },
  scroll:  { paddingHorizontal: 18 },
  noScrollContent: { flex: 1, paddingHorizontal: 18, paddingTop: 8 },

  // ── Stepper ──
  stepperWrap: {
    flexDirection: 'row', alignItems: 'center',
    justifyContent: 'center', marginBottom: 16,
  },
  step:          { alignItems: 'center', gap: 5 },
  stepDot: {
    width: 28, height: 28, borderRadius: 14,
    backgroundColor: GLASS_BG, borderWidth: 1, borderColor: GLASS_BORDER,
    alignItems: 'center', justifyContent: 'center',
  },
  stepDotActive: {
    backgroundColor: '#0D1117', borderColor: '#0D1117',
  },
  stepDotActiveWrap: {
    width: 34, height: 34,
    alignItems: 'center', justifyContent: 'center',
  },
  stepArcTrack: {
    position: 'absolute', width: 34, height: 34, borderRadius: 17,
    borderWidth: 1.5, borderColor: 'rgba(0,0,0,0.12)',
  },
  stepArcSpin: {
    position: 'absolute', width: 34, height: 34, borderRadius: 17,
    borderWidth: 1.5,
    borderTopColor: '#0D1117', borderRightColor: '#0D1117',
    borderBottomColor: '#0D1117', borderLeftColor: 'transparent',
  },
  stepNum:        { fontSize: 11, fontWeight: '700', color: '#9CA3AF' },
  stepLabel:      { fontSize: 10, fontWeight: '600', color: '#9CA3AF', letterSpacing: 0.3 },
  stepLabelActive:{ color: '#0D1117', fontWeight: '700' },
  stepLine: {
    flex: 1, height: 1,
    backgroundColor: 'rgba(0,0,0,0.08)',
    marginHorizontal: 6, marginBottom: 18,
  },

  // ── Page header ──
  pageHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingBottom: 14,
  },
  backBtn: {
    width: 38, height: 38, borderRadius: 19,
    backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: 'rgba(0,0,0,0.08)',
    alignItems: 'center', justifyContent: 'center',
    shadowColor: '#000', shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06, shadowRadius: 4, elevation: 2,
  },
  pageTitle: { fontSize: 14, fontWeight: '700', color: '#0D1117', letterSpacing: 0.3 },
  headerCenter: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  headerLogo: { width: 105, height: 26 },
  corporateLabel: {
    fontSize: 9,
    fontWeight: '500',
    color: '#9CA3AF',
    letterSpacing: 2.5,
    marginTop: 2,
    marginLeft: 18,
  },

  // ── Calculator card wrapper ──
  calcCard: {
    marginBottom: 4,
  },
  calcError: {
    fontSize: 12,
    color: '#EF4444',
    marginTop: 6,
    marginHorizontal: 4,
  },

  // ── Trading card (toggle + TC hero) ──
  tradingCard: {
    backgroundColor: '#0D1117',
    borderRadius: 24, overflow: 'hidden',
    marginBottom: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.18,
    shadowRadius: 20,
    elevation: 10,
  },
  opTypeBadge: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 8, paddingVertical: 10, paddingHorizontal: 16,
  },
  opTypeSubLabel: {
    fontSize: 9, fontWeight: '500', color: 'rgba(255,255,255,0.4)',
    letterSpacing: 0.8, textTransform: 'uppercase', marginBottom: 2,
  },
  bsWrap: {
    flexDirection: 'row',
    alignItems: 'stretch',
  },
  bsBtn: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 8, paddingVertical: 16, paddingHorizontal: 12,
  },
  bsBtnBuy: {
    backgroundColor: 'rgba(34,197,94,0.12)',
  },
  bsBtnSell: {
    backgroundColor: 'rgba(59,130,246,0.1)',
  },
  bsBtnLabel: { fontSize: 13, fontWeight: '700', letterSpacing: 0.3, color: '#FFFFFF' },
  bsRadio: {
    width: 18, height: 18, borderRadius: 9,
    borderWidth: 1.5, borderColor: 'rgba(0,0,0,0.15)',
    backgroundColor: '#F3F4F6',
    alignItems: 'center', justifyContent: 'center',
  },
  bsRadioDot: {
    width: 8, height: 8, borderRadius: 4,
  },
  tradingCardDivider: {
    height: StyleSheet.hairlineWidth,
    backgroundColor: 'rgba(255,255,255,0.08)',
    marginHorizontal: 0,
  },
  tcRow: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 18, paddingVertical: 14,
  },
  tcRowLeft: {
    gap: 3,
  },
  tcRowRight: {
    alignItems: 'flex-end',
    gap: 2,
  },
  tcHeroLabel: {
    fontSize: 9, fontWeight: '700', color: 'rgba(255,255,255,0.4)',
    letterSpacing: 2.5, textTransform: 'uppercase',
  },
  tcHeroBaseValue: {
    fontSize: 14, fontWeight: '500', color: 'rgba(255,255,255,0.35)',
    letterSpacing: -0.2, textDecorationLine: 'line-through',
  },
  tcHeroValue: {
    fontSize: 34, fontWeight: '800', letterSpacing: -0.8, lineHeight: 38,
  },
  tcHeroPipBadge: {
    backgroundColor: 'rgba(34,197,94,0.15)',
    borderWidth: 1, borderColor: 'rgba(34,197,94,0.30)',
    borderRadius: 20, paddingHorizontal: 8, paddingVertical: 3,
  },
  tcHeroPipText: {
    fontSize: 9, fontWeight: '700', color: '#22c55e',
    letterSpacing: 1.5, textTransform: 'uppercase',
  },
  tcHeroCurr: {
    fontSize: 10, fontWeight: '600', color: 'rgba(255,255,255,0.4)',
    letterSpacing: 1,
  },
  tcRefRow: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 18, paddingBottom: 12, paddingTop: 2,
  },
  tcRefPair:  { flexDirection: 'row', alignItems: 'center', gap: 5 },
  tcRefRates: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  tcRefItem:  { alignItems: 'center' },
  tcRefLabel: { fontSize: 8, fontWeight: '700', color: 'rgba(255,255,255,0.4)', letterSpacing: 1.5, marginBottom: 2 },
  tcRefValue: { fontSize: 13, fontWeight: '700', color: 'rgba(255,255,255,0.85)' },
  tcRefSep:   { width: 1, height: 20, backgroundColor: 'rgba(255,255,255,0.12)' },

  // ── Ticker remnants used inside trading card ──
  tickerDot:     { width: 5, height: 5, borderRadius: 2.5, backgroundColor: GREEN },
  tickerPairTxt: { fontSize: 9, fontWeight: '700', color: 'rgba(255,255,255,0.4)', letterSpacing: 1 },

  // ── Order card ──
  orderCard: {
    backgroundColor: '#0D1117',
    borderRadius: 24, overflow: 'hidden',
    padding: 20, marginBottom: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.18,
    shadowRadius: 20,
    elevation: 10,
  },
  orderRow:    { flexDirection: 'row', alignItems: 'center', gap: 14 },
  orderCurrTag: {
    width: 46, height: 46, borderRadius: 13,
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.12)',
    alignItems: 'center', justifyContent: 'center',
  },
  orderCurrTxt:  { fontSize: 11, fontWeight: '800', color: 'rgba(255,255,255,0.6)', letterSpacing: 0.5 },
  orderRowLabel: { fontSize: 9, fontWeight: '700', color: 'rgba(255,255,255,0.4)', letterSpacing: 2, marginBottom: 4 },
  orderAmount:   { fontSize: 28, fontWeight: '800', color: '#FFFFFF', letterSpacing: -0.5 },
  orderSepRow:   { flexDirection: 'row', alignItems: 'center', marginVertical: 16 },
  orderSepLine:  { flex: 1, height: StyleSheet.hairlineWidth, backgroundColor: 'rgba(255,255,255,0.08)' },
  orderSepIcon:  {
    width: 32, height: 32, borderRadius: 16,
    backgroundColor: 'rgba(255,255,255,0.06)',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.12)',
    alignItems: 'center', justifyContent: 'center',
    marginHorizontal: 12,
  },

  sectionLabel: {
    fontSize: 13, fontWeight: '700', color: '#0D1117',
    letterSpacing: 0.1, marginBottom: 10, marginLeft: 2,
  },

  // ── Accounts card ──
  accountsCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 24, overflow: 'hidden',
    paddingHorizontal: 18, paddingVertical: 16,
    marginBottom: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.08,
    shadowRadius: 16,
    elevation: 6,
    borderWidth: 1,
    borderColor: 'rgba(0,0,0,0.06)',
  },
  accountBlock:     { flexDirection: 'row', alignItems: 'center', gap: 8 },
  accountMeta:      { width: 78 },
  accountRoleLabel: { fontSize: 9, fontWeight: '700', color: '#0D1117', letterSpacing: 0.3 },
  accountRoleSub:   { fontSize: 9, color: '#0D1117', marginTop: 2, fontWeight: '500' },
  accountSelector: {
    flex: 1, flexDirection: 'row', alignItems: 'center', gap: 7,
    backgroundColor: '#F3F4F6',
    borderWidth: 1, borderColor: 'rgba(0,0,0,0.07)',
    borderRadius: 12, paddingHorizontal: 11, paddingVertical: 10,
  },
  accountSelectorErr: { borderColor: 'rgba(239,68,68,0.45)' },
  accountSelectorTxt: { flex: 1, fontSize: 12, color: '#0D1117', fontWeight: '500' },
  accountSelectorPh:  { flex: 1, fontSize: 12, color: 'rgba(0,0,0,0.28)', fontStyle: 'italic' },
  addMicroBtn: {
    width: 30, height: 30, borderRadius: 10,
    backgroundColor: '#0D1117', borderWidth: 1, borderColor: '#0D1117',
    alignItems: 'center', justifyContent: 'center',
  },
  accountDivider: { height: StyleSheet.hairlineWidth, backgroundColor: 'rgba(0,0,0,0.08)', marginVertical: 14 },
  errorTxt:       { fontSize: 11, color: '#f87171', marginTop: 5 },

  // ── Declaration ──
  declarationRow: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 12,
    backgroundColor: '#F9FAFB',
    borderWidth: 1, borderColor: 'rgba(0,0,0,0.07)',
    borderRadius: 14, padding: 14, marginBottom: 12,
  },
  checkbox: {
    width: 20, height: 20, borderRadius: 10,
    borderWidth: 1.5, borderColor: 'rgba(0,0,0,0.15)',
    backgroundColor: '#F3F4F6', alignItems: 'center', justifyContent: 'center',
    flexShrink: 0, marginTop: 1,
  },
  checkboxOn:    { backgroundColor: GREEN, borderColor: GREEN },
  declarationTxt:{ flex: 1, fontSize: 12, color: '#6B7280', lineHeight: 18 },

  // ── Execute button ──
  execBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    borderRadius: 18, paddingVertical: 17,
    backgroundColor: '#0D1117',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 6 }, shadowOpacity: 0.22, shadowRadius: 16,
    elevation: 8,
  },
  execBtnDim: { opacity: 0.30 },
  execTxt:    { fontSize: 15, fontWeight: '800', color: '#fff', letterSpacing: 1.4 },

  // ── Modals ──
  modalOuter: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  modalBox: {
    width: '100%', maxHeight: '85%', borderRadius: 28, overflow: 'hidden',
    alignItems: 'center', paddingTop: 28, paddingBottom: 24, paddingHorizontal: 24,
    backgroundColor: '#FFFFFF',
    borderWidth: 1, borderColor: 'rgba(0,0,0,0.06)',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.25,
    shadowRadius: 28,
    elevation: 20,
  },
  modalTitle:   { fontSize: 17, fontWeight: '800', color: '#0D1117', marginBottom: 16, letterSpacing: 0.1 },
  modalDivider: { width: '100%', height: StyleSheet.hairlineWidth, backgroundColor: 'rgba(0,0,0,0.07)', marginBottom: 18 },
  modalBody:    { width: '100%', gap: 2 },
  modalFooter:  { flexDirection: 'row', gap: 10, width: '100%', marginTop: 18 },
  modalBtnSec:  { flex: 1, paddingVertical: 14, borderRadius: 14, backgroundColor: '#F3F4F6', borderWidth: 1, borderColor: 'rgba(0,0,0,0.07)', alignItems: 'center' },
  modalBtnSecTxt: { fontSize: 14, fontWeight: '600', color: '#374151' },
  modalBtnPri:  { flex: 1, paddingVertical: 14, borderRadius: 14, backgroundColor: '#0D1117', borderWidth: 1, borderColor: '#0D1117', alignItems: 'center', justifyContent: 'center' },
  modalBtnPriTxt: { fontSize: 14, fontWeight: '700', color: '#fff' },

  // ── Form inputs ──
  inputLabel: { fontSize: 11, fontWeight: '600', color: '#6B7280', textTransform: 'uppercase', letterSpacing: 0.6, marginTop: 14, marginBottom: 6 },
  inputRow: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#F9FAFB', borderWidth: 1, borderColor: 'rgba(0,0,0,0.08)', borderRadius: 13, paddingHorizontal: 14, paddingVertical: 12 },
  inputField: { flex: 1, color: '#0D1117', fontSize: 14 },
  textInputStandalone: {
    backgroundColor: '#F9FAFB', borderWidth: 1, borderColor: 'rgba(0,0,0,0.08)',
    borderRadius: 13, paddingHorizontal: 14, paddingVertical: 13,
    color: '#0D1117', fontSize: 14, width: '100%',
  },

  // ── Inline dropdown ──
  inlineMenu: { backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: 'rgba(0,0,0,0.08)', borderRadius: 14, marginTop: 4, overflow: 'hidden', shadowColor: '#000', shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.08, shadowRadius: 12, elevation: 4 },
  inlineMenuItem: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 13, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: 'rgba(0,0,0,0.07)' },
  inlineMenuTxt: { fontSize: 14, color: '#374151', fontWeight: '500' },

  // ── Bank items ──
  bankItem: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 13, paddingHorizontal: 4, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: 'rgba(0,0,0,0.07)' },
  bankItemActive: { },
  bankItemTxt: { fontSize: 14, color: '#374151', fontWeight: '500', flex: 1 },

  // ── Info box ──
  infoBox:    { flexDirection: 'row', gap: 8, alignItems: 'center', padding: 12, backgroundColor: 'rgba(251,191,36,0.08)', borderRadius: 10, borderWidth: 1, borderColor: 'rgba(251,191,36,0.2)', marginTop: 10 },
  infoBoxTxt: { flex: 1, fontSize: 12, color: '#fbbf24', lineHeight: 17 },

  emptyTxt: { fontSize: 13, color: '#9CA3AF', textAlign: 'center', paddingVertical: 24 },

  // ── Coupon ──
  couponBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 7,
    backgroundColor: '#FFFFFF',
    borderWidth: 1, borderColor: 'rgba(0,0,0,0.07)',
    borderRadius: 14, paddingHorizontal: 14, paddingVertical: 11,
    marginBottom: 10, marginTop: 2,
  },
  couponBtnTxt: { fontSize: 13, color: '#6B7280', fontWeight: '500' },
  couponAppliedRow: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 4, marginBottom: 10, marginTop: 2,
  },
  couponAppliedBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    backgroundColor: 'rgba(22,163,74,0.10)',
    borderWidth: 1, borderColor: 'rgba(22,163,74,0.25)',
    borderRadius: 20, paddingHorizontal: 10, paddingVertical: 5,
  },
  couponAppliedTxt: { fontSize: 12, fontWeight: '600', color: '#16a34a' },
  couponModal: {
    width: '100%', borderRadius: 20, overflow: 'hidden',
    backgroundColor: '#FFFFFF',
    shadowColor: '#000', shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.25, shadowRadius: 28, elevation: 20,
  },
  couponModalHeader: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    backgroundColor: '#0D1117', paddingHorizontal: 20, paddingVertical: 16,
  },
  couponModalIconWrap: {
    width: 34, height: 34, borderRadius: 17,
    backgroundColor: 'rgba(255,255,255,0.10)',
    alignItems: 'center', justifyContent: 'center',
  },
  couponModalTitle: { flex: 1, fontSize: 16, fontWeight: '800', color: '#FFFFFF' },
  couponModalBody: { paddingHorizontal: 20, paddingTop: 16, paddingBottom: 20 },
  couponModalSub: { fontSize: 13, color: '#6B7280', lineHeight: 20, marginBottom: 16 },
  couponModalInput: {
    backgroundColor: '#F9FAFB', borderWidth: 1, borderColor: 'rgba(0,0,0,0.10)',
    borderRadius: 14, paddingHorizontal: 16, paddingVertical: 14,
    fontSize: 20, fontWeight: '700', color: '#0D1117',
    textAlign: 'center', letterSpacing: 4, marginBottom: 14,
  },
  couponModalBtn: {
    backgroundColor: '#0D1117', borderRadius: 14, paddingVertical: 15,
    alignItems: 'center',
  },
  couponModalBtnTxt: { fontSize: 15, fontWeight: '700', color: '#fff', letterSpacing: 0.3 },

  // ── Pips ──
  pipsRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 10 },
  pipsInfoBtn: {
    width: 38, height: 38, borderRadius: 19,
    backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: 'rgba(0,0,0,0.08)',
    alignItems: 'center', justifyContent: 'center',
  },
  pipsBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 7,
    backgroundColor: '#16a34a',
    borderWidth: 0, borderRadius: 14, paddingHorizontal: 14, paddingVertical: 11,
  },
  pipsBtnTxt: { fontSize: 13, color: '#fff', fontWeight: '600', flex: 1 },
  pipsBtnAction: {
    backgroundColor: 'rgba(255,255,255,0.20)', borderRadius: 8,
    paddingHorizontal: 12, paddingVertical: 5,
    minWidth: 60, alignItems: 'center',
  },
  pipsBtnActionTxt: { fontSize: 12, fontWeight: '700', color: '#fff' },

  // ── Segmented (used in modals) ──
  seg:           { flexDirection: 'row', gap: 6 },
  segBtn:        { flex: 1, paddingVertical: 11, borderRadius: 12, alignItems: 'center', backgroundColor: '#F3F4F6', borderWidth: 1, borderColor: 'rgba(0,0,0,0.07)' },
  segBtnActive:  { backgroundColor: '#0D1117', borderColor: '#0D1117' },
  segBtnTxt:     { fontSize: 13, fontWeight: '600', color: '#9CA3AF' },
  segBtnTxtActive: { color: '#fff', fontWeight: '700' },
});
