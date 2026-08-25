import React, { useState, useEffect, useRef } from 'react';
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
import { useAuth } from '../contexts/AuthContext';
import { operationsApi } from '../api/operations';
import { CreateOperationForm, BankAccount } from '../types';
import { formatCurrency, calculateAmount, formatExchangeRate } from '../utils/formatters';
import axios from 'axios';
import { API_CONFIG } from '../constants/config';

// ─── Design tokens ─────────────────────────────────────────────────────────────
const GREEN        = '#22c55e';
const GREEN_DIM    = 'rgba(34,197,94,0.14)';
const GREEN_BORDER = 'rgba(34,197,94,0.3)';
const GLASS_BG     = 'rgba(255,255,255,0.08)';
const GLASS_BORDER = 'rgba(255,255,255,0.15)';
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

// ─── Creating overlay styles ───────────────────────────────────────────────────
const ov = StyleSheet.create({
  root:  { flex: 1, backgroundColor: '#000', justifyContent: 'center', alignItems: 'center' },
  layer: { ...StyleSheet.absoluteFillObject, justifyContent: 'center', alignItems: 'center' },

  // ── Loader
  orbitWrap: { width: 112, height: 112, justifyContent: 'center', alignItems: 'center' },
  outerRing: {              // lento, contrarrotante, muy sutil
    position: 'absolute',
    width: 112, height: 112, borderRadius: 56,
    borderWidth: 1,
    borderColor:        'rgba(255,255,255,0.07)',
    borderTopColor:     'rgba(255,255,255,0.28)',
    borderRightColor:   'rgba(255,255,255,0.12)',
  },
  trackRing: {              // pista estática para el arco interior
    position: 'absolute',
    width: 74, height: 74, borderRadius: 37,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.06)',
  },
  innerArc: {               // arco giratorio rápido
    position: 'absolute',
    width: 74, height: 74, borderRadius: 37,
    borderWidth: 1.5,
    borderColor:       'transparent',
    borderTopColor:    '#ffffff',
    borderRightColor:  'rgba(255,255,255,0.3)',
  },
  centerDot: {              // punto central que respira
    width: 5, height: 5, borderRadius: 2.5,
    backgroundColor: '#fff',
  },
  loadingLabel: {
    marginTop: 44,
    fontSize: 10,
    fontWeight: '300',
    color: 'rgba(255,255,255,0.3)',
    letterSpacing: 5,
    textTransform: 'uppercase',
  },

  // ── Check
  checkRing: {
    width: 76, height: 76, borderRadius: 38,
    borderWidth: 1.5,
    borderColor: '#ffffff',
    alignItems: 'center',
    justifyContent: 'center',
  },
  ripple: {                 // anillos expansivos (shockwave)
    position: 'absolute',
    width: 76, height: 76, borderRadius: 38,
    borderWidth: 1,
    borderColor: '#ffffff',
  },
  successLabel: {
    marginTop: 30,
    fontSize: 11,
    fontWeight: '300',
    color: '#ffffff',
    letterSpacing: 5,
    textTransform: 'uppercase',
  },
});

// ─── Creating overlay ──────────────────────────────────────────────────────────
const CreatingOverlay: React.FC<{ visible: boolean; success: boolean }> = ({ visible, success }) => {
  // overlay
  const overlayOp   = useRef(new Animated.Value(0)).current;
  // loader
  const loaderOp    = useRef(new Animated.Value(0)).current;
  const outerRot    = useRef(new Animated.Value(0)).current;
  const innerRot    = useRef(new Animated.Value(0)).current;
  const dotPulse    = useRef(new Animated.Value(1)).current;
  // check
  const checkOp     = useRef(new Animated.Value(0)).current;
  const checkScale  = useRef(new Animated.Value(0.25)).current;
  const markOp      = useRef(new Animated.Value(0)).current;
  const markY       = useRef(new Animated.Value(6)).current;
  const textOp      = useRef(new Animated.Value(0)).current;
  const textY       = useRef(new Animated.Value(14)).current;
  // ripples
  const r1s = useRef(new Animated.Value(1)).current;
  const r1o = useRef(new Animated.Value(0)).current;
  const r2s = useRef(new Animated.Value(1)).current;
  const r2o = useRef(new Animated.Value(0)).current;
  const r3s = useRef(new Animated.Value(1)).current;
  const r3o = useRef(new Animated.Value(0)).current;

  const outerRef = useRef<Animated.CompositeAnimation>();
  const innerRef = useRef<Animated.CompositeAnimation>();
  const dotRef   = useRef<Animated.CompositeAnimation>();

  const reset = () => {
    outerRef.current?.stop();
    innerRef.current?.stop();
    dotRef.current?.stop();
    overlayOp.setValue(0);  loaderOp.setValue(0);
    outerRot.setValue(0);   innerRot.setValue(0);  dotPulse.setValue(1);
    checkOp.setValue(0);    checkScale.setValue(0.25);
    markOp.setValue(0);     markY.setValue(6);
    textOp.setValue(0);     textY.setValue(14);
    r1s.setValue(1); r1o.setValue(0);
    r2s.setValue(1); r2o.setValue(0);
    r3s.setValue(1); r3o.setValue(0);
  };

  useEffect(() => {
    if (!visible) { reset(); return; }

    // Fade in overlay + loader
    Animated.timing(overlayOp, { toValue: 1, duration: 320, useNativeDriver: true }).start();
    setTimeout(() => {
      Animated.timing(loaderOp, { toValue: 1, duration: 400, useNativeDriver: true }).start();
    }, 80);

    // Outer ring — lento, contrarrotante
    outerRef.current = Animated.loop(
      Animated.timing(outerRot, { toValue: -1, duration: 3800, easing: Easing.linear, useNativeDriver: true })
    );
    outerRef.current.start();

    // Inner arc — rápido
    innerRef.current = Animated.loop(
      Animated.timing(innerRot, { toValue: 1, duration: 820, easing: Easing.linear, useNativeDriver: true })
    );
    innerRef.current.start();

    // Dot pulse — respiración lenta
    dotRef.current = Animated.loop(
      Animated.sequence([
        Animated.timing(dotPulse, { toValue: 2.2, duration: 800, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
        Animated.timing(dotPulse, { toValue: 1,   duration: 800, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
      ])
    );
    dotRef.current.start();
  }, [visible]);

  useEffect(() => {
    if (!success || !visible) return;
    outerRef.current?.stop();
    innerRef.current?.stop();
    dotRef.current?.stop();

    // Loader desaparece
    Animated.timing(loaderOp, { toValue: 0, duration: 250, easing: Easing.out(Easing.ease), useNativeDriver: true }).start(() => {

      // Check ring entra con spring agresivo (overshoot visible)
      Animated.parallel([
        Animated.timing(checkOp,   { toValue: 1, duration: 200, useNativeDriver: true }),
        Animated.spring(checkScale, { toValue: 1, tension: 280, friction: 5, useNativeDriver: true }),
      ]).start(() => {

        // Shockwave: 3 ripples con stagger
        r1o.setValue(0.5); r2o.setValue(0.32); r3o.setValue(0.18);
        Animated.stagger(90, [
          Animated.parallel([
            Animated.timing(r1s, { toValue: 2.6, duration: 650, easing: Easing.out(Easing.ease), useNativeDriver: true }),
            Animated.timing(r1o, { toValue: 0,   duration: 650, useNativeDriver: true }),
          ]),
          Animated.parallel([
            Animated.timing(r2s, { toValue: 3.2, duration: 750, easing: Easing.out(Easing.ease), useNativeDriver: true }),
            Animated.timing(r2o, { toValue: 0,   duration: 750, useNativeDriver: true }),
          ]),
          Animated.parallel([
            Animated.timing(r3s, { toValue: 3.9, duration: 860, easing: Easing.out(Easing.ease), useNativeDriver: true }),
            Animated.timing(r3o, { toValue: 0,   duration: 860, useNativeDriver: true }),
          ]),
        ]).start();

        // Checkmark desliza desde abajo
        Animated.parallel([
          Animated.timing(markOp, { toValue: 1, duration: 230, useNativeDriver: true }),
          Animated.spring(markY,  { toValue: 0, tension: 200, friction: 8, useNativeDriver: true }),
        ]).start();

        // Texto sube con delay
        setTimeout(() => {
          Animated.parallel([
            Animated.timing(textOp, { toValue: 1, duration: 380, useNativeDriver: true }),
            Animated.timing(textY,  { toValue: 0, duration: 380, easing: Easing.out(Easing.ease), useNativeDriver: true }),
          ]).start();
        }, 160);
      });
    });
  }, [success]);

  const outerSpin = outerRot.interpolate({ inputRange: [-1, 0], outputRange: ['-360deg', '0deg'] });
  const innerSpin = innerRot.interpolate({ inputRange: [0, 1],  outputRange: ['0deg', '360deg'] });

  return (
    <Modal visible={visible} transparent animationType="none" onRequestClose={() => {}}>
      <Animated.View style={[ov.root, { opacity: overlayOp }]}>

        {/* ── Loader ── */}
        <Animated.View style={[ov.layer, { opacity: loaderOp }]}>
          <View style={ov.orbitWrap}>
            <Animated.View style={[ov.outerRing, { transform: [{ rotate: outerSpin }] }]} />
            <View style={ov.trackRing} />
            <Animated.View style={[ov.innerArc,  { transform: [{ rotate: innerSpin }] }]} />
            <Animated.View style={[ov.centerDot, { transform: [{ scale: dotPulse }] }]} />
          </View>
          <Text style={ov.loadingLabel}>Procesando</Text>
        </Animated.View>

        {/* ── Check ── */}
        <Animated.View style={[ov.layer, { opacity: checkOp }]}>
          {/* Ripples */}
          <Animated.View style={[ov.ripple, { opacity: r1o, transform: [{ scale: r1s }] }]} />
          <Animated.View style={[ov.ripple, { opacity: r2o, transform: [{ scale: r2s }] }]} />
          <Animated.View style={[ov.ripple, { opacity: r3o, transform: [{ scale: r3s }] }]} />
          {/* Círculo check */}
          <Animated.View style={[ov.checkRing, { transform: [{ scale: checkScale }] }]}>
            <Animated.View style={{ opacity: markOp, transform: [{ translateY: markY }] }}>
              <Ionicons name="checkmark" size={32} color="#fff" />
            </Animated.View>
          </Animated.View>
          {/* Texto */}
          <Animated.Text style={[ov.successLabel, { opacity: textOp, transform: [{ translateY: textY }] }]}>
            Operación creada
          </Animated.Text>
        </Animated.View>

      </Animated.View>
    </Modal>
  );
};

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
      {/* Backdrop */}
      <TouchableOpacity
        style={[StyleSheet.absoluteFill, { backgroundColor: 'rgba(0,0,0,0.65)' }]}
        activeOpacity={1}
        onPress={onClose}
      />
      {/* Contenido centrado — pointerEvents="box-none" deja pasar toques al backdrop excepto los de los hijos */}
      <View style={s.modalOuter} pointerEvents="box-none">
        <View style={s.modalBox}>
          <BlurView intensity={90} tint="dark" style={StyleSheet.absoluteFill} pointerEvents="none" />
          <View style={s.modalBorder} />
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
  const { client, refreshClient } = useAuth();
  const insets = useSafeAreaInsets();

  // ── Exchange rates ─────────────────────────────────────────────────────────
  const [realExchangeRates, setRealExchangeRates] = useState({ compra: 3.75, venta: 3.77 });

  const params              = route?.params || {};
  const initialOperationType = params.operationType || 'Compra';
  const initialAmount        = params.amountUSD     || '';
  const initialExchangeRate  = params.exchangeRate  || realExchangeRates.compra;

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

  const accountsPEN = client?.bank_accounts?.filter(a => a.currency === 'S/') || [];
  const accountsUSD = client?.bank_accounts?.filter(a => a.currency === '$')  || [];

  // ── Fetch rates ────────────────────────────────────────────────────────────
  useEffect(() => {
    (async () => {
      try {
        const res = await axios.get<{ success: boolean; rates: { compra: number; venta: number } }>(
          `${API_CONFIG.BASE_URL}/api/client/exchange-rates`
        );
        if (res.data.success) {
          setRealExchangeRates(res.data.rates);
          const rate = initialOperationType === 'Compra' ? res.data.rates.compra : res.data.rates.venta;
          setExchangeRate(rate.toString());
        }
      } catch {}
    })();
  }, []);

  useEffect(() => {
    const rate = operationType === 'Compra' ? realExchangeRates.compra : realExchangeRates.venta;
    setExchangeRate(rate.toString());
    setSourceAccount('');
    setDestinationAccount('');
  }, [operationType, realExchangeRates]);

  // ── Calculations ───────────────────────────────────────────────────────────
  const calculatePEN = () => {
    if (!amountUsd || !exchangeRate) return 0;
    const amt  = parseFloat(amountUsd);
    const rate = parseFloat(exchangeRate);
    return operationType === 'Compra'
      ? parseFloat((amt * rate).toFixed(2))
      : parseFloat((amt / rate).toFixed(2));
  };

  const inputCurrency  = operationType === 'Compra' ? 'USD' : 'PEN';
  const outputCurrency = operationType === 'Compra' ? 'PEN' : 'USD';
  const amountToSend    = parseFloat(amountUsd) || 0;
  const amountToReceive = calculatePEN();

  const renderAccountOption = (acc: BankAccount) =>
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

    // Check visible exactamente 900ms antes de navegar
    await delay(900);
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
      <ImageBackground source={require('../../assets/cd.png')} style={StyleSheet.absoluteFill} resizeMode="cover" />
      <View style={[StyleSheet.absoluteFill, s.overlay]} pointerEvents="none" />

      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        <ScrollView
          contentContainerStyle={[s.scroll, { paddingTop: insets.top + 16, paddingBottom: insets.bottom + 100 }]}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >

          {/* ── Header ── */}
          <MotiView
            from={{ opacity: 0, translateY: -8 }}
            animate={{ opacity: 1, translateY: 0 }}
            transition={{ type: 'spring', delay: 40, damping: 24, stiffness: 220 }}
          >
            <View style={s.pageHeader}>
              <TouchableOpacity style={s.backBtn} onPress={() => navigation.goBack()} activeOpacity={0.75}>
                <Ionicons name="chevron-back" size={20} color="#fff" />
              </TouchableOpacity>
              <Text style={s.pageTitle}>Nueva operación</Text>
              <View style={{ width: 38 }} />
            </View>
          </MotiView>


          {/* ── Stepper ── */}
          <MotiView
            from={{ opacity: 0, translateY: -6 }}
            animate={{ opacity: 1, translateY: 0 }}
            transition={{ type: 'spring', delay: 65, damping: 24, stiffness: 220 }}
          >
            <View style={s.stepperWrap}>
              {(['Cotiza', 'Transfiere', 'Recibe'] as const).map((label, i) => (
                <React.Fragment key={label}>
                  <View style={s.step}>
                    <View style={[s.stepDot, i === 0 && s.stepDotActive]}>
                      {i === 0
                        ? <Ionicons name="checkmark" size={12} color="#fff" />
                        : <Text style={s.stepNum}>{i + 1}</Text>
                      }
                    </View>
                    <Text style={[s.stepLabel, i === 0 && s.stepLabelActive]}>{label}</Text>
                  </View>
                  {i < 2 && <View style={s.stepLine} />}
                </React.Fragment>
              ))}
            </View>
          </MotiView>

          {/* ── Trading card (toggle + TC hero) ── */}
          <MotiView
            from={{ opacity: 0, translateY: 12 }}
            animate={{ opacity: 1, translateY: 0 }}
            transition={{ type: 'spring', delay: 90, damping: 22, stiffness: 200 }}
          >
            <View style={s.tradingCard}>
              <View style={[StyleSheet.absoluteFill, { borderRadius: 20, backgroundColor: 'rgba(255,255,255,0.055)' }]} />
              <View style={[StyleSheet.absoluteFill, {
                borderRadius: 20, borderWidth: 1,
                borderColor: operationType === 'Compra' ? 'rgba(34,197,94,0.28)' : 'rgba(59,130,246,0.25)',
              }]} />

              {/* ── BUY / SELL tabs ── */}
              <View style={s.bsWrap}>
                <TouchableOpacity
                  style={[s.bsBtn, operationType === 'Compra' && s.bsBtnBuy]}
                  onPress={() => { Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium); setOperationType('Compra'); }}
                  activeOpacity={0.78}
                >
                  {/* Radio indicator */}
                  <View style={[s.bsRadio, operationType === 'Compra' && { borderColor: GREEN, backgroundColor: 'rgba(34,197,94,0.15)' }]}>
                    {operationType === 'Compra' && <View style={[s.bsRadioDot, { backgroundColor: GREEN }]} />}
                  </View>
                  <Text style={[s.bsBtnLabel, { color: operationType === 'Compra' ? GREEN : 'rgba(255,255,255,0.35)' }]}>
                    Qoricash compra
                  </Text>
                </TouchableOpacity>
                <BsDividerAnim color={operationType === 'Compra' ? GREEN : RED} />
                <TouchableOpacity
                  style={[s.bsBtn, operationType === 'Venta' && s.bsBtnSell]}
                  onPress={() => { Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium); setOperationType('Venta'); }}
                  activeOpacity={0.78}
                >
                  {/* Radio indicator */}
                  <View style={[s.bsRadio, operationType === 'Venta' && { borderColor: RED, backgroundColor: 'rgba(59,130,246,0.15)' }]}>
                    {operationType === 'Venta' && <View style={[s.bsRadioDot, { backgroundColor: RED }]} />}
                  </View>
                  <Text style={[s.bsBtnLabel, { color: operationType === 'Venta' ? RED : 'rgba(255,255,255,0.35)' }]}>
                    Qoricash vende
                  </Text>
                </TouchableOpacity>
              </View>

              {/* ── Divider ── */}
              <View style={s.tradingCardDivider} />

              {/* ── T.C. hero ── */}
              <View style={s.tcHeroWrap}>
                <Text style={s.tcHeroLabel}>TIPO DE CAMBIO</Text>
                <Text style={[s.tcHeroValue, { color: operationType === 'Compra' ? GREEN : RED }]}>
                  {parseFloat(exchangeRate).toFixed(3)}
                </Text>
                <Text style={s.tcHeroCurr}>{operationType === 'Compra' ? 'USD por PEN' : 'PEN por USD'}</Text>
              </View>

              {/* ── BID / ASK reference ── */}
              <View style={s.tcRefRow}>
                <View style={s.tcRefPair}>
                  <LivePairBadge />
                  <Text style={s.tickerPairTxt}>USD/PEN</Text>
                </View>
                <View style={s.tcRefRates}>
                  <View style={s.tcRefItem}>
                    <Text style={s.tcRefLabel}>BID</Text>
                    <Text style={s.tcRefValue}>{realExchangeRates.compra.toFixed(3)}</Text>
                  </View>
                  <View style={s.tcRefSep} />
                  <View style={s.tcRefItem}>
                    <Text style={s.tcRefLabel}>ASK</Text>
                    <Text style={s.tcRefValue}>{realExchangeRates.venta.toFixed(3)}</Text>
                  </View>
                </View>
              </View>
            </View>
          </MotiView>

          {/* ── Order flow card ── */}
          <MotiView
            from={{ opacity: 0, translateY: 16, scale: 0.97 }}
            animate={{ opacity: 1, translateY: 0, scale: 1 }}
            transition={{ type: 'spring', delay: 210, damping: 22, stiffness: 180 }}
          >
            <View style={s.orderCard}>
              <View style={[StyleSheet.absoluteFill, { borderRadius: 20, backgroundColor: 'rgba(255,255,255,0.055)' }]} />
              <View style={[StyleSheet.absoluteFill, { borderRadius: 20, borderWidth: 1, borderColor: GLASS_BORDER }]} />

              {/* Envías */}
              <View style={s.orderRow}>
                <View style={s.orderCurrTag}>
                  <Text style={s.orderCurrTxt}>{inputCurrency}</Text>
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={s.orderRowLabel}>
                    {operationType === 'Compra' ? 'Usted envía dólares' : 'Usted envía soles'}
                  </Text>
                  <Text style={s.orderAmount}>
                    {formatCurrency(amountToSend, inputCurrency === 'USD' ? 'USD' : 'PEN')}
                  </Text>
                </View>
              </View>

              {/* Separador */}
              <View style={s.orderSepRow}>
                <View style={s.orderSepLine} />
                <View style={[s.orderSepIcon, { borderColor: operationType === 'Compra' ? 'rgba(34,197,94,0.3)' : 'rgba(59,130,246,0.3)' }]}>
                  <Ionicons name="swap-vertical" size={14} color={operationType === 'Compra' ? GREEN : RED} />
                </View>
                <View style={s.orderSepLine} />
              </View>

              {/* Recibes */}
              <View style={s.orderRow}>
                <View style={[s.orderCurrTag, {
                  borderColor: operationType === 'Compra' ? 'rgba(34,197,94,0.35)' : 'rgba(59,130,246,0.35)',
                  backgroundColor: operationType === 'Compra' ? 'rgba(34,197,94,0.1)' : 'rgba(59,130,246,0.1)',
                }]}>
                  <Text style={[s.orderCurrTxt, { color: operationType === 'Compra' ? GREEN : RED }]}>{outputCurrency}</Text>
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={s.orderRowLabel}>
                    {operationType === 'Compra' ? 'Usted recibe soles' : 'Usted recibe dólares'}
                  </Text>
                  <Text style={[s.orderAmount, { color: operationType === 'Compra' ? GREEN : RED }]}>
                    {formatCurrency(amountToReceive, outputCurrency === 'USD' ? 'USD' : 'PEN')}
                  </Text>
                </View>
              </View>
            </View>
          </MotiView>

          {/* ── Cuentas ── */}
          <MotiView
            from={{ opacity: 0, translateY: 16 }}
            animate={{ opacity: 1, translateY: 0 }}
            transition={{ type: 'spring', delay: 280, damping: 22, stiffness: 180 }}
          >
            <View style={s.accountsCard}>
              <View style={[StyleSheet.absoluteFill, { borderRadius: 20, backgroundColor: 'rgba(255,255,255,0.055)' }]} />
              <View style={[StyleSheet.absoluteFill, { borderRadius: 20, borderWidth: 1, borderColor: GLASS_BORDER }]} />

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
                  <Ionicons name="card-outline" size={14} color={getSourceText() ? 'rgba(255,255,255,0.55)' : 'rgba(255,255,255,0.2)'} />
                  {getSourceText()
                    ? <Text style={s.accountSelectorTxt} numberOfLines={1}>{getSourceText()}</Text>
                    : <Text style={s.accountSelectorPh}>Seleccionar cuenta...</Text>
                  }
                  <Ionicons name="chevron-down" size={13} color="rgba(255,255,255,0.25)" />
                </TouchableOpacity>
                <TouchableOpacity style={s.addMicroBtn} onPress={() => openAddAccount('source')} activeOpacity={0.75}>
                  <Ionicons name="add" size={14} color={GREEN} />
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
                  <Ionicons name="card-outline" size={14} color={getDestText() ? 'rgba(255,255,255,0.55)' : 'rgba(255,255,255,0.2)'} />
                  {getDestText()
                    ? <Text style={s.accountSelectorTxt} numberOfLines={1}>{getDestText()}</Text>
                    : <Text style={s.accountSelectorPh}>Seleccionar cuenta...</Text>
                  }
                  <Ionicons name="chevron-down" size={13} color="rgba(255,255,255,0.25)" />
                </TouchableOpacity>
                <TouchableOpacity style={s.addMicroBtn} onPress={() => openAddAccount('destination')} activeOpacity={0.75}>
                  <Ionicons name="add" size={14} color={GREEN} />
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
                { backgroundColor: operationType === 'Compra' ? GREEN : RED, shadowColor: operationType === 'Compra' ? GREEN : RED },
                (!termsAccepted || loading) && s.execBtnDim,
              ]}
              onPress={() => { Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium); handleSubmit(); }}
              disabled={loading || !termsAccepted}
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
          <Text style={s.inputLabel}>Origen</Text>
          <Seg options={['Lima','Provincia']} value={newAccountOrigen} onChange={v => { setNewAccountOrigen(v); setNewAccountBank(''); }} />

          {newAccountOrigen === 'Provincia' && (
            <View style={s.infoBox}>
              <Ionicons name="information-circle-outline" size={14} color="#fbbf24" />
              <Text style={s.infoBoxTxt}>Para provincia solo operamos con BCP e INTERBANK</Text>
            </View>
          )}

          <Text style={s.inputLabel}>Banco</Text>
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

          <View style={[s.infoBox, { marginTop: 16 }]}>
            <Ionicons name="wallet-outline" size={14} color={GREEN} />
            <Text style={[s.infoBoxTxt, { color: GREEN }]}>
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
          <TouchableOpacity style={[s.modalBtnSec, { width: '100%' }]} onPress={() => setSourceDialogVisible(false)}>
            <Text style={s.modalBtnSecTxt}>Cerrar</Text>
          </TouchableOpacity>
        }
      >
        <View style={s.modalBody}>
          {(operationType === 'Venta' ? accountsPEN : accountsUSD).length === 0 ? (
            <Text style={s.emptyTxt}>No tienes cuentas en {operationType === 'Venta' ? 'soles' : 'dólares'}. Agrega una primero.</Text>
          ) : (
            (operationType === 'Venta' ? accountsPEN : accountsUSD).map((acc, i) => (
              <TouchableOpacity
                key={i}
                style={[s.bankItem, sourceAccount === acc.account_number && s.bankItemActive]}
                onPress={() => { Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light); setSourceAccount(acc.account_number); setErrors({ ...errors, sourceAccount: '' }); setSourceDialogVisible(false); }}
                activeOpacity={0.75}
              >
                <Ionicons name="card-outline" size={16} color={sourceAccount === acc.account_number ? GREEN : 'rgba(255,255,255,0.45)'} />
                <Text style={[s.bankItemTxt, sourceAccount === acc.account_number && { color: GREEN }]} numberOfLines={1}>
                  {renderAccountOption(acc)}
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
          <TouchableOpacity style={[s.modalBtnSec, { width: '100%' }]} onPress={() => setDestDialogVisible(false)}>
            <Text style={s.modalBtnSecTxt}>Cerrar</Text>
          </TouchableOpacity>
        }
      >
        <View style={s.modalBody}>
          {(operationType === 'Venta' ? accountsUSD : accountsPEN).length === 0 ? (
            <Text style={s.emptyTxt}>No tienes cuentas en {operationType === 'Venta' ? 'dólares' : 'soles'}. Agrega una primero.</Text>
          ) : (
            (operationType === 'Venta' ? accountsUSD : accountsPEN).map((acc, i) => (
              <TouchableOpacity
                key={i}
                style={[s.bankItem, destinationAccount === acc.account_number && s.bankItemActive]}
                onPress={() => { Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light); setDestinationAccount(acc.account_number); setErrors({ ...errors, destinationAccount: '' }); setDestDialogVisible(false); }}
                activeOpacity={0.75}
              >
                <Ionicons name="card-outline" size={16} color={destinationAccount === acc.account_number ? GREEN : 'rgba(255,255,255,0.45)'} />
                <Text style={[s.bankItemTxt, destinationAccount === acc.account_number && { color: GREEN }]} numberOfLines={1}>
                  {renderAccountOption(acc)}
                </Text>
                {destinationAccount === acc.account_number && <Ionicons name="checkmark" size={16} color={GREEN} style={{ marginLeft: 'auto' }} />}
              </TouchableOpacity>
            ))
          )}
        </View>
      </GlassModal>

      {/* ══ Creating operation overlay ═════════════════════════════════════ */}
      <CreatingOverlay visible={creatingVisible} success={creatingSuccess} />

    </View>
  );
};

// ─── Styles ────────────────────────────────────────────────────────────────────
const s = StyleSheet.create({
  root:    { flex: 1 },
  overlay: { backgroundColor: 'transparent' },
  scroll:  { paddingHorizontal: 18 },

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
    backgroundColor: GREEN, borderColor: GREEN,
    shadowColor: GREEN, shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.5, shadowRadius: 8,
  },
  stepNum:        { fontSize: 11, fontWeight: '700', color: 'rgba(255,255,255,0.3)' },
  stepLabel:      { fontSize: 10, fontWeight: '600', color: 'rgba(255,255,255,0.28)', letterSpacing: 0.3 },
  stepLabelActive:{ color: GREEN, fontWeight: '700' },
  stepLine: {
    flex: 1, height: 1,
    backgroundColor: GLASS_BORDER,
    marginHorizontal: 6, marginBottom: 18,
  },

  // ── Page header ──
  pageHeader: {
    flexDirection: 'row', alignItems: 'center',
    justifyContent: 'space-between', marginBottom: 18,
  },
  backBtn: {
    width: 38, height: 38, borderRadius: 19,
    backgroundColor: GLASS_BG, borderWidth: 1, borderColor: GLASS_BORDER,
    alignItems: 'center', justifyContent: 'center',
  },
  pageTitle: { fontSize: 14, fontWeight: '700', color: '#fff', letterSpacing: 0.3 },

  // ── Trading card (toggle + TC hero) ──
  tradingCard: {
    borderRadius: 20, overflow: 'hidden',
    marginBottom: 10,
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
  bsBtnLabel: { fontSize: 13, fontWeight: '700', letterSpacing: 0.3 },
  bsRadio: {
    width: 18, height: 18, borderRadius: 9,
    borderWidth: 1.5, borderColor: 'rgba(255,255,255,0.2)',
    backgroundColor: 'rgba(255,255,255,0.04)',
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
  tcHeroWrap: {
    alignItems: 'center', paddingTop: 20, paddingBottom: 14,
  },
  tcHeroLabel: {
    fontSize: 9, fontWeight: '700', color: 'rgba(255,255,255,0.28)',
    letterSpacing: 2.5, textTransform: 'uppercase', marginBottom: 6,
  },
  tcHeroValue: {
    fontSize: 46, fontWeight: '800', letterSpacing: -1,
    lineHeight: 50,
  },
  tcHeroCurr: {
    fontSize: 10, fontWeight: '600', color: 'rgba(255,255,255,0.28)',
    letterSpacing: 1, marginTop: 6,
  },
  tcRefRow: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 18, paddingBottom: 16, paddingTop: 4,
  },
  tcRefPair:  { flexDirection: 'row', alignItems: 'center', gap: 5 },
  tcRefRates: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  tcRefItem:  { alignItems: 'center' },
  tcRefLabel: { fontSize: 8, fontWeight: '700', color: 'rgba(255,255,255,0.28)', letterSpacing: 1.5, marginBottom: 2 },
  tcRefValue: { fontSize: 13, fontWeight: '700', color: 'rgba(255,255,255,0.65)' },
  tcRefSep:   { width: 1, height: 20, backgroundColor: GLASS_BORDER },

  // ── Ticker remnants used inside trading card ──
  tickerDot:     { width: 5, height: 5, borderRadius: 2.5, backgroundColor: GREEN },
  tickerPairTxt: { fontSize: 9, fontWeight: '700', color: 'rgba(255,255,255,0.32)', letterSpacing: 1 },

  // ── Order card ──
  orderCard: {
    borderRadius: 20, overflow: 'hidden',
    padding: 20, marginBottom: 10,
  },
  orderRow:    { flexDirection: 'row', alignItems: 'center', gap: 14 },
  orderCurrTag: {
    width: 46, height: 46, borderRadius: 13,
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderWidth: 1, borderColor: GLASS_BORDER,
    alignItems: 'center', justifyContent: 'center',
  },
  orderCurrTxt:  { fontSize: 11, fontWeight: '800', color: 'rgba(255,255,255,0.55)', letterSpacing: 0.5 },
  orderRowLabel: { fontSize: 9, fontWeight: '700', color: 'rgba(255,255,255,0.28)', letterSpacing: 2, marginBottom: 4 },
  orderAmount:   { fontSize: 28, fontWeight: '800', color: '#fff', letterSpacing: -0.5 },
  orderSepRow:   { flexDirection: 'row', alignItems: 'center', marginVertical: 16 },
  orderSepLine:  { flex: 1, height: StyleSheet.hairlineWidth, backgroundColor: 'rgba(255,255,255,0.07)' },
  orderSepIcon:  {
    width: 32, height: 32, borderRadius: 16,
    backgroundColor: 'rgba(255,255,255,0.05)',
    borderWidth: 1,
    alignItems: 'center', justifyContent: 'center',
    marginHorizontal: 12,
  },

  // ── Accounts card ──
  accountsCard: {
    borderRadius: 20, overflow: 'hidden',
    paddingHorizontal: 18, paddingVertical: 16,
    marginBottom: 10,
  },
  accountBlock:     { flexDirection: 'row', alignItems: 'center', gap: 8 },
  accountMeta:      { width: 78 },
  accountRoleLabel: { fontSize: 9, fontWeight: '700', color: 'rgba(255,255,255,0.5)', letterSpacing: 0.3 },
  accountRoleSub:   { fontSize: 9, color: 'rgba(255,255,255,0.22)', marginTop: 2, fontWeight: '500' },
  accountSelector: {
    flex: 1, flexDirection: 'row', alignItems: 'center', gap: 7,
    backgroundColor: 'rgba(255,255,255,0.05)',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.09)',
    borderRadius: 12, paddingHorizontal: 11, paddingVertical: 10,
  },
  accountSelectorErr: { borderColor: 'rgba(248,113,113,0.45)' },
  accountSelectorTxt: { flex: 1, fontSize: 12, color: 'rgba(255,255,255,0.75)', fontWeight: '500' },
  accountSelectorPh:  { flex: 1, fontSize: 12, color: 'rgba(255,255,255,0.2)', fontStyle: 'italic' },
  addMicroBtn: {
    width: 30, height: 30, borderRadius: 10,
    backgroundColor: GREEN_DIM, borderWidth: 1, borderColor: GREEN_BORDER,
    alignItems: 'center', justifyContent: 'center',
  },
  accountDivider: { height: StyleSheet.hairlineWidth, backgroundColor: GLASS_BORDER, marginVertical: 14 },
  errorTxt:       { fontSize: 11, color: '#f87171', marginTop: 5 },

  // ── Declaration ──
  declarationRow: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 12,
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderWidth: 1, borderColor: GLASS_BORDER,
    borderRadius: 14, padding: 14, marginBottom: 12,
  },
  checkbox: {
    width: 20, height: 20, borderRadius: 10,
    borderWidth: 1.5, borderColor: GLASS_BORDER,
    backgroundColor: GLASS_BG, alignItems: 'center', justifyContent: 'center',
    flexShrink: 0, marginTop: 1,
  },
  checkboxOn:    { backgroundColor: GREEN, borderColor: GREEN },
  declarationTxt:{ flex: 1, fontSize: 12, color: 'rgba(255,255,255,0.42)', lineHeight: 18 },

  // ── Execute button ──
  execBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    borderRadius: 18, paddingVertical: 17,
    shadowOffset: { width: 0, height: 6 }, shadowOpacity: 0.45, shadowRadius: 16,
  },
  execBtnDim: { opacity: 0.32 },
  execTxt:    { fontSize: 15, fontWeight: '800', color: '#fff', letterSpacing: 1.4 },

  // ── Modals ──
  modalOuter: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  modalBox: {
    width: '100%', maxHeight: '85%', borderRadius: 28, overflow: 'hidden',
    alignItems: 'center', paddingTop: 28, paddingBottom: 24, paddingHorizontal: 24,
  },
  modalBorder:  { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, borderRadius: 28, borderWidth: 1, borderColor: GLASS_BORDER },
  modalTitle:   { fontSize: 17, fontWeight: '800', color: '#fff', marginBottom: 16, letterSpacing: 0.1 },
  modalDivider: { width: '100%', height: StyleSheet.hairlineWidth, backgroundColor: GLASS_BORDER, marginBottom: 18 },
  modalBody:    { width: '100%', gap: 2 },
  modalFooter:  { flexDirection: 'row', gap: 10, width: '100%', marginTop: 18 },
  modalBtnSec:  { flex: 1, paddingVertical: 14, borderRadius: 14, backgroundColor: GLASS_BG, borderWidth: 1, borderColor: GLASS_BORDER, alignItems: 'center' },
  modalBtnSecTxt: { fontSize: 14, fontWeight: '600', color: 'rgba(255,255,255,0.65)' },
  modalBtnPri:  { flex: 1, paddingVertical: 14, borderRadius: 14, backgroundColor: GREEN_DIM, borderWidth: 1, borderColor: GREEN_BORDER, alignItems: 'center', justifyContent: 'center' },
  modalBtnPriTxt: { fontSize: 14, fontWeight: '700', color: GREEN },

  // ── Form inputs ──
  inputLabel: { fontSize: 11, fontWeight: '600', color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase', letterSpacing: 0.6, marginTop: 14, marginBottom: 6 },
  inputRow: { flexDirection: 'row', alignItems: 'center', backgroundColor: GLASS_BG, borderWidth: 1, borderColor: GLASS_BORDER, borderRadius: 13, paddingHorizontal: 14, paddingVertical: 12 },
  inputField: { flex: 1, color: '#fff', fontSize: 14 },
  textInputStandalone: {
    backgroundColor: GLASS_BG, borderWidth: 1, borderColor: GLASS_BORDER,
    borderRadius: 13, paddingHorizontal: 14, paddingVertical: 13,
    color: '#fff', fontSize: 14, width: '100%',
  },

  // ── Inline dropdown ──
  inlineMenu: { backgroundColor: 'rgba(8,18,32,0.97)', borderWidth: 1, borderColor: GLASS_BORDER, borderRadius: 14, marginTop: 4, overflow: 'hidden' },
  inlineMenuItem: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 13, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: GLASS_BORDER },
  inlineMenuTxt: { fontSize: 14, color: 'rgba(255,255,255,0.75)', fontWeight: '500' },

  // ── Bank items ──
  bankItem: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 13, paddingHorizontal: 4, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: GLASS_BORDER },
  bankItemActive: { },
  bankItemTxt: { fontSize: 14, color: 'rgba(255,255,255,0.75)', fontWeight: '500', flex: 1 },

  // ── Info box ──
  infoBox:    { flexDirection: 'row', gap: 8, alignItems: 'center', padding: 12, backgroundColor: 'rgba(251,191,36,0.08)', borderRadius: 10, borderWidth: 1, borderColor: 'rgba(251,191,36,0.2)', marginTop: 10 },
  infoBoxTxt: { flex: 1, fontSize: 12, color: '#fbbf24', lineHeight: 17 },

  emptyTxt: { fontSize: 13, color: 'rgba(255,255,255,0.35)', textAlign: 'center', paddingVertical: 24 },

  // ── Segmented (used in modals) ──
  seg:           { flexDirection: 'row', gap: 6 },
  segBtn:        { flex: 1, paddingVertical: 11, borderRadius: 12, alignItems: 'center', backgroundColor: GLASS_BG, borderWidth: 1, borderColor: GLASS_BORDER },
  segBtnActive:  { backgroundColor: GREEN_DIM, borderColor: GREEN_BORDER },
  segBtnTxt:     { fontSize: 13, fontWeight: '600', color: 'rgba(255,255,255,0.38)' },
  segBtnTxtActive: { color: GREEN, fontWeight: '700' },
});
