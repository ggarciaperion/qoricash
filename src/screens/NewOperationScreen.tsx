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

// ─── Creating overlay styles (must come before the components that use them) ───
// ─── Creating overlay styles ───────────────────────────────────────────────────
const ov = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.92)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  logo: { width: 180, height: 180 },
  checkCircle: {
    width: 92, height: 92, borderRadius: 46,
    backgroundColor: GREEN,
    alignItems: 'center', justifyContent: 'center',
    shadowColor: GREEN, shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.9, shadowRadius: 32,
  },
  labelTxt:   { marginTop: 44, fontSize: 16, fontWeight: '600', color: 'rgba(255,255,255,0.72)', letterSpacing: 0.3 },
  successTxt: { marginTop: 34, fontSize: 18, fontWeight: '700', color: GREEN, letterSpacing: 0.2 },
});

// ─── Creating overlay — usa Modal para renderizar SOBRE la transición de nav ──
const CreatingOverlay: React.FC<{ visible: boolean; success: boolean }> = ({ visible, success }) => {
  const logoPulse  = useRef(new Animated.Value(1)).current;
  const logoFloat  = useRef(new Animated.Value(0)).current;
  const checkScale = useRef(new Animated.Value(0)).current;
  const pulseLoop  = useRef<Animated.CompositeAnimation>();
  const floatLoop  = useRef<Animated.CompositeAnimation>();
  const startTimer = useRef<ReturnType<typeof setTimeout>>();
  const [phase, setPhase] = useState<'logo' | 'check'>('logo');

  const stopAll = () => {
    pulseLoop.current?.stop();
    floatLoop.current?.stop();
    clearTimeout(startTimer.current);
  };

  // Arrancar animación cuando el modal se abre
  useEffect(() => {
    if (!visible) {
      stopAll();
      logoPulse.setValue(1);
      logoFloat.setValue(0);
      checkScale.setValue(0);
      setPhase('logo');
      return;
    }

    // Esperar 250ms para que el modal haga fade in antes de pulsar
    startTimer.current = setTimeout(() => {
      pulseLoop.current = Animated.loop(
        Animated.sequence([
          Animated.timing(logoPulse, { toValue: 1.22, duration: 620, useNativeDriver: true }),
          Animated.timing(logoPulse, { toValue: 0.78, duration: 620, useNativeDriver: true }),
        ])
      );
      pulseLoop.current.start();

      floatLoop.current = Animated.loop(
        Animated.sequence([
          Animated.timing(logoFloat, { toValue: -18, duration: 620, useNativeDriver: true }),
          Animated.timing(logoFloat, { toValue:  18, duration: 620, useNativeDriver: true }),
        ])
      );
      floatLoop.current.start();
    }, 250);

    return stopAll;
  }, [visible]);

  // Transición a check
  useEffect(() => {
    if (!success || !visible) return;
    stopAll();
    logoPulse.setValue(1);
    logoFloat.setValue(0);
    setPhase('check');
    Animated.spring(checkScale, { toValue: 1, friction: 3, tension: 110, useNativeDriver: true }).start();
  }, [success]);

  // Modal renderiza ENCIMA de todo — incluidas transiciones de navegación
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={() => {}}>
      <View style={ov.root}>
        {phase === 'logo' ? (
          <Animated.View style={{ transform: [{ scale: logoPulse }, { translateY: logoFloat }] }}>
            <Image source={require('../../assets/ji.png')} style={ov.logo} resizeMode="contain" />
          </Animated.View>
        ) : (
          <Animated.View style={[ov.checkCircle, { transform: [{ scale: checkScale }] }]}>
            <Ionicons name="checkmark" size={44} color="#fff" />
          </Animated.View>
        )}
        <Text style={phase === 'check' ? ov.successTxt : ov.labelTxt}>
          {phase === 'check' ? '¡Operación creada!' : 'Creando tu operación…'}
        </Text>
      </View>
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

          {/* ── Header / back ── */}
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

          {/* ── Timeline stepper ── */}
          <MotiView
            from={{ opacity: 0, translateY: -10 }}
            animate={{ opacity: 1, translateY: 0 }}
            transition={{ type: 'spring', delay: 80, damping: 22, stiffness: 200 }}
          >
            <View style={s.stepperWrap}>
              {(['Cotiza','Transfiere','Recibe'] as const).map((label, i) => (
                <React.Fragment key={label}>
                  <View style={s.step}>
                    <View style={[s.stepDot, i === 0 && s.stepDotActive]}>
                      {i === 0
                        ? <Ionicons name="checkmark" size={14} color="#fff" />
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

          {/* ── Operation type (read-only) ── */}
          <MotiView
            from={{ opacity: 0, translateY: 16 }}
            animate={{ opacity: 1, translateY: 0 }}
            transition={{ type: 'spring', delay: 160, damping: 22, stiffness: 180 }}
          >
            <View style={[s.card, { backgroundColor: 'transparent', borderWidth: 0 }]}>
              <Text style={s.cardLabel}>Tipo de operación</Text>
              <View style={s.opTypeRow}>
                <View style={s.opTypeBadge}>
                  <Ionicons
                    name={operationType === 'Compra' ? 'arrow-down-circle' : 'arrow-up-circle'}
                    size={18}
                    color={GREEN}
                  />
                  <Text style={s.opTypeText}>
                    {operationType === 'Compra' ? 'Qoricash compra' : 'Qoricash vende'}
                  </Text>
                </View>
                <View style={s.opTcBadge}>
                  <Text style={s.opTcLabel}>T.C.</Text>
                  <Text style={s.opTcValue}>{parseFloat(exchangeRate).toFixed(3)}</Text>
                </View>
              </View>
              <Text style={s.cardHint}>
                {operationType === 'Compra'
                  ? 'Envías dólares · Recibes soles'
                  : 'Envías soles · Recibes dólares'}
              </Text>
            </View>
          </MotiView>

          {/* ── Summary ── */}
          <MotiView
            from={{ opacity: 0, translateY: 16, scale: 0.97 }}
            animate={{ opacity: 1, translateY: 0, scale: 1 }}
            transition={{ type: 'spring', delay: 230, damping: 22, stiffness: 180 }}
          >
            <View style={s.summaryCard}>
              {/* Capas efecto espejo */}
              <View style={[StyleSheet.absoluteFill, s.mirrorBase]} />
              <View style={[StyleSheet.absoluteFill, s.mirrorSheen]} />
              <View style={s.summaryBorder} />

              {/* Envías */}
              <View style={s.summaryRow}>
                <View style={{ flex: 1 }}>
                  <Text style={s.summaryRowLabel}>¿Cuánto envías?</Text>
                  <Text style={s.summaryAmount}>
                    {formatCurrency(amountToSend, inputCurrency === 'USD' ? 'USD' : 'PEN')}
                  </Text>
                </View>
                <View style={s.currencyTag}>
                  <Text style={s.currencyTagTxt}>{inputCurrency === 'USD' ? 'Dólares' : 'Soles'}</Text>
                </View>
              </View>

              {/* Recibes */}
              <View style={[s.summaryRow, { marginBottom: 0 }]}>
                <View style={{ flex: 1 }}>
                  <Text style={s.summaryRowLabel}>Entonces recibes</Text>
                  <Text style={[s.summaryAmount, { color: GREEN }]}>
                    {formatCurrency(amountToReceive, outputCurrency === 'USD' ? 'USD' : 'PEN')}
                  </Text>
                </View>
                <View style={[s.currencyTag, s.currencyTagGreen]}>
                  <Text style={[s.currencyTagTxt, { color: GREEN }]}>{outputCurrency === 'USD' ? 'Dólares' : 'Soles'}</Text>
                </View>
              </View>
            </View>
          </MotiView>

          {/* ── Cuenta origen ── */}
          <MotiView
            from={{ opacity: 0, translateY: 16 }}
            animate={{ opacity: 1, translateY: 0 }}
            transition={{ type: 'spring', delay: 300, damping: 22, stiffness: 180 }}
          >
            <View style={s.card}>
              <View style={s.accHeader}>
                <View style={{ flex: 1 }}>
                  <Text style={s.cardLabel}>Cuenta de cargo</Text>
                  <Text style={s.cardHint}>{operationType === 'Venta' ? 'Soles (S/)' : 'Dólares (USD)'}</Text>
                </View>
                <TouchableOpacity style={s.addAccBtn} onPress={() => openAddAccount('source')} activeOpacity={0.75}>
                  <Ionicons name="add" size={14} color={GREEN} />
                  <Text style={s.addAccTxt}>Agregar</Text>
                </TouchableOpacity>
              </View>
              <TouchableOpacity
                style={[s.accSelect, errors.sourceAccount && s.accSelectError]}
                onPress={() => setSourceDialogVisible(true)}
                activeOpacity={0.78}
              >
                <Ionicons name="business-outline" size={16} color={getSourceText() ? 'rgba(255,255,255,0.6)' : 'rgba(255,255,255,0.25)'} />
                <Text style={[s.accSelectTxt, !getSourceText() && s.accSelectPlaceholder]} numberOfLines={1}>
                  {getSourceText() || 'Seleccionar cuenta...'}
                </Text>
                <Ionicons name="chevron-down" size={16} color="rgba(255,255,255,0.3)" />
              </TouchableOpacity>
              {errors.sourceAccount && <Text style={s.errorTxt}>{errors.sourceAccount}</Text>}
            </View>
          </MotiView>

          {/* ── Cuenta destino ── */}
          <MotiView
            from={{ opacity: 0, translateY: 16 }}
            animate={{ opacity: 1, translateY: 0 }}
            transition={{ type: 'spring', delay: 360, damping: 22, stiffness: 180 }}
          >
            <View style={s.card}>
              <View style={s.accHeader}>
                <View style={{ flex: 1 }}>
                  <Text style={s.cardLabel}>Cuenta de destino</Text>
                  <Text style={s.cardHint}>{operationType === 'Venta' ? 'Dólares (USD)' : 'Soles (S/)'}</Text>
                </View>
                <TouchableOpacity style={s.addAccBtn} onPress={() => openAddAccount('destination')} activeOpacity={0.75}>
                  <Ionicons name="add" size={14} color={GREEN} />
                  <Text style={s.addAccTxt}>Agregar</Text>
                </TouchableOpacity>
              </View>
              <TouchableOpacity
                style={[s.accSelect, errors.destinationAccount && s.accSelectError]}
                onPress={() => setDestDialogVisible(true)}
                activeOpacity={0.78}
              >
                <Ionicons name="business-outline" size={16} color={getDestText() ? 'rgba(255,255,255,0.6)' : 'rgba(255,255,255,0.25)'} />
                <Text style={[s.accSelectTxt, !getDestText() && s.accSelectPlaceholder]} numberOfLines={1}>
                  {getDestText() || 'Seleccionar cuenta...'}
                </Text>
                <Ionicons name="chevron-down" size={16} color="rgba(255,255,255,0.3)" />
              </TouchableOpacity>
              {errors.destinationAccount && <Text style={s.errorTxt}>{errors.destinationAccount}</Text>}
            </View>
          </MotiView>

          {/* ── Declaración ── */}
          <MotiView
            from={{ opacity: 0, translateY: 16 }}
            animate={{ opacity: 1, translateY: 0 }}
            transition={{ type: 'spring', delay: 420, damping: 22, stiffness: 180 }}
          >
            <TouchableOpacity
              style={s.card}
              onPress={() => { Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light); setTermsAccepted(!termsAccepted); setErrors({ ...errors, termsAccepted: '' }); }}
              activeOpacity={0.82}
            >
              <View style={s.checkRow}>
                <View style={[s.checkbox, termsAccepted && s.checkboxOn]}>
                  {termsAccepted && <Ionicons name="checkmark" size={13} color="#fff" />}
                </View>
                <Text style={s.checkLabel}>
                  Declaro como verdad que los fondos provienen de actividades lícitas y que soy el titular de las cuentas bancarias registradas.
                </Text>
              </View>
              {errors.termsAccepted && <Text style={[s.errorTxt, { marginTop: 8 }]}>{errors.termsAccepted}</Text>}
            </TouchableOpacity>
          </MotiView>

          {/* ── Botón submit ── */}
          <MotiView
            from={{ opacity: 0, translateY: 20, scale: 0.95 }}
            animate={{ opacity: 1, translateY: 0, scale: 1 }}
            transition={{ type: 'spring', delay: 480, damping: 20, stiffness: 180 }}
          >
            <TouchableOpacity
              style={[s.submitBtn, (!termsAccepted || loading) && s.submitBtnDim]}
              onPress={() => { Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium); handleSubmit(); }}
              disabled={loading || !termsAccepted}
              activeOpacity={0.82}
            >
              {loading
                ? <ActivityIndicator color="#fff" size="small" />
                : <>
                    <Ionicons name="arrow-forward-circle" size={20} color="#fff" style={{ marginRight: 8 }} />
                    <Text style={s.submitTxt}>CREAR OPERACIÓN</Text>
                  </>
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
  scroll:  { paddingHorizontal: 20 },

  // ── Page header ──
  pageHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 22,
  },
  backBtn: {
    width: 38, height: 38, borderRadius: 19,
    backgroundColor: GLASS_BG,
    borderWidth: 1, borderColor: GLASS_BORDER,
    alignItems: 'center', justifyContent: 'center',
  },
  pageTitle: {
    fontSize: 15, fontWeight: '700', color: '#fff', letterSpacing: 0.1,
  },

  // ── Summary glass card ──
  summaryCard: {
    borderRadius: 20,
    overflow: 'hidden',
    padding: 18,
    marginBottom: 14,
  },
  mirrorBase: {
    backgroundColor: 'rgba(255,255,255,0.14)',
    borderRadius: 20,
  },
  mirrorSheen: {
    borderRadius: 20,
    backgroundColor: 'rgba(255,255,255,0.06)',
    borderTopWidth: 1.5,
    borderTopColor: 'rgba(255,255,255,0.55)',
    borderLeftWidth: 1,
    borderLeftColor: 'rgba(255,255,255,0.3)',
    borderRightWidth: 1,
    borderRightColor: 'rgba(255,255,255,0.08)',
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255,255,255,0.06)',
  },
  summaryBorder: {
    position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
    borderRadius: 20,
  },

  // ── Stepper ──
  stepperWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 24,
  },
  step: { alignItems: 'center', gap: 6 },
  stepDot: {
    width: 36, height: 36, borderRadius: 18,
    backgroundColor: GLASS_BG,
    borderWidth: 1, borderColor: GLASS_BORDER,
    alignItems: 'center', justifyContent: 'center',
  },
  stepDotActive: {
    backgroundColor: GREEN,
    borderColor: GREEN,
    shadowColor: GREEN,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.55,
    shadowRadius: 10,
  },
  stepNum:        { fontSize: 13, fontWeight: '700', color: 'rgba(255,255,255,0.35)' },
  stepLabel:      { fontSize: 11, fontWeight: '600', color: 'rgba(255,255,255,0.3)', letterSpacing: 0.3 },
  stepLabelActive:{ color: GREEN, fontWeight: '700' },
  stepLine: {
    flex: 1,
    height: 1,
    backgroundColor: GLASS_BORDER,
    marginHorizontal: 8,
    marginBottom: 20,
  },

  // ── Cards ──
  card: {
    backgroundColor: GLASS_BG,
    borderWidth: 1, borderColor: GLASS_BORDER,
    borderRadius: 20,
    padding: 18,
    marginBottom: 14,
  },
  cardLabel: { fontSize: 11, fontWeight: '700', color: 'rgba(255,255,255,0.45)', textTransform: 'uppercase', letterSpacing: 0.7, marginBottom: 12 },
  cardHint:  { fontSize: 11, color: 'rgba(255,255,255,0.3)', marginTop: 8 },

  // ── Op type read-only ──
  opTypeRow:   { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 },
  opTypeBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    backgroundColor: GREEN_DIM, borderWidth: 1, borderColor: GREEN_BORDER,
    borderRadius: 12, paddingHorizontal: 14, paddingVertical: 10, flex: 1, marginRight: 10,
  },
  opTypeText: { fontSize: 14, fontWeight: '700', color: GREEN },
  opTcBadge: {
    alignItems: 'center', justifyContent: 'center',
    backgroundColor: GLASS_BG, borderWidth: 1, borderColor: GLASS_BORDER,
    borderRadius: 12, paddingHorizontal: 14, paddingVertical: 10,
  },
  opTcLabel: { fontSize: 9, fontWeight: '700', color: 'rgba(255,255,255,0.38)', textTransform: 'uppercase', letterSpacing: 0.6, marginBottom: 2 },
  opTcValue: { fontSize: 15, fontWeight: '800', color: '#fff' },

  // ── Segmented ──
  seg:           { flexDirection: 'row', gap: 6 },
  segBtn:        { flex: 1, paddingVertical: 11, borderRadius: 12, alignItems: 'center', backgroundColor: GLASS_BG, borderWidth: 1, borderColor: GLASS_BORDER },
  segBtnActive:  { backgroundColor: GREEN_DIM, borderColor: GREEN_BORDER },
  segBtnTxt:     { fontSize: 13, fontWeight: '600', color: 'rgba(255,255,255,0.38)' },
  segBtnTxtActive: { color: GREEN, fontWeight: '700' },

  // ── Summary ──
  summaryRow:       { flexDirection: 'row', alignItems: 'center', marginBottom: 16 },
  summaryRowLabel:  { fontSize: 10.5, color: 'rgba(255,255,255,0.38)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 5 },
  summaryAmount:    { fontSize: 24, fontWeight: '800', color: '#fff', letterSpacing: -0.5 },
  currencyTag: {
    paddingHorizontal: 12, paddingVertical: 8, borderRadius: 12,
    backgroundColor: 'rgba(255,255,255,0.07)',
    borderWidth: 1, borderColor: GLASS_BORDER,
    alignItems: 'center', justifyContent: 'center', marginLeft: 12,
  },
  currencyTagGreen: { backgroundColor: GREEN_DIM, borderColor: GREEN_BORDER },
  currencyTagTxt:   { fontSize: 12, fontWeight: '600', color: 'rgba(255,255,255,0.55)' },
  tcRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 10, marginBottom: 16, borderTopWidth: StyleSheet.hairlineWidth, borderBottomWidth: StyleSheet.hairlineWidth, borderColor: GLASS_BORDER },
  tcDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: GREEN },
  tcLabel: { flex: 1, fontSize: 12, color: 'rgba(255,255,255,0.45)', fontWeight: '500' },
  tcValue: { fontSize: 13, fontWeight: '700', color: '#fff' },

  // ── Account ──
  accHeader:   { flexDirection: 'row', alignItems: 'center', marginBottom: 12 },
  addAccBtn:   { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 12, paddingVertical: 7, borderRadius: 10, backgroundColor: GREEN_DIM, borderWidth: 1, borderColor: GREEN_BORDER },
  addAccTxt:   { fontSize: 12, fontWeight: '600', color: GREEN },
  accSelect:   { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: 'rgba(255,255,255,0.05)', borderWidth: 1, borderColor: GLASS_BORDER, borderRadius: 13, paddingHorizontal: 14, paddingVertical: 13 },
  accSelectError: { borderColor: 'rgba(248,113,113,0.5)' },
  accSelectTxt:   { flex: 1, fontSize: 13, color: 'rgba(255,255,255,0.82)', fontWeight: '500' },
  accSelectPlaceholder: { color: 'rgba(255,255,255,0.25)' },
  errorTxt: { fontSize: 11, color: '#f87171', marginTop: 6, marginLeft: 2 },

  // ── Checkbox ──
  checkRow:  { flexDirection: 'row', alignItems: 'flex-start', gap: 12 },
  checkbox:  { width: 22, height: 22, borderRadius: 11, borderWidth: 1.5, borderColor: GLASS_BORDER, backgroundColor: GLASS_BG, alignItems: 'center', justifyContent: 'center', marginTop: 1, flexShrink: 0 },
  checkboxOn: { backgroundColor: GREEN, borderColor: GREEN },
  checkLabel: { flex: 1, fontSize: 12.5, color: 'rgba(255,255,255,0.55)', lineHeight: 19 },

  // ── Submit ──
  submitBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    backgroundColor: GREEN, borderRadius: 18,
    paddingVertical: 17,
    shadowColor: GREEN,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.45,
    shadowRadius: 16,
  },
  submitBtnDim: { backgroundColor: 'rgba(34,197,94,0.35)', shadowOpacity: 0 },
  submitTxt: { fontSize: 15, fontWeight: '800', color: '#fff', letterSpacing: 1.2 },

  // ── Modals ──
  modalBackdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.65)', justifyContent: 'center', alignItems: 'center', padding: 24 },
  modalOuter: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  modalBox: {
    width: '100%', maxHeight: '85%',
    borderRadius: 28, overflow: 'hidden',
    alignItems: 'center',
    paddingTop: 28, paddingBottom: 24, paddingHorizontal: 24,
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
    backgroundColor: GLASS_BG,
    borderWidth: 1,
    borderColor: GLASS_BORDER,
    borderRadius: 13,
    paddingHorizontal: 14,
    paddingVertical: 13,
    color: '#fff',
    fontSize: 14,
    width: '100%',
  },

  // ── Inline dropdown ──
  inlineMenu: {
    backgroundColor: 'rgba(8,18,32,0.97)',
    borderWidth: 1, borderColor: GLASS_BORDER,
    borderRadius: 14, marginTop: 4, overflow: 'hidden',
  },
  inlineMenuItem: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 16, paddingVertical: 13,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: GLASS_BORDER,
  },
  inlineMenuTxt: { fontSize: 14, color: 'rgba(255,255,255,0.75)', fontWeight: '500' },

  // ── Bank items ──
  bankItem: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 13, paddingHorizontal: 4, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: GLASS_BORDER },
  bankItemActive: { },
  bankItemTxt: { fontSize: 14, color: 'rgba(255,255,255,0.75)', fontWeight: '500', flex: 1 },

  // ── Info box ──
  infoBox:    { flexDirection: 'row', gap: 8, alignItems: 'center', padding: 12, backgroundColor: 'rgba(251,191,36,0.08)', borderRadius: 10, borderWidth: 1, borderColor: 'rgba(251,191,36,0.2)', marginTop: 10 },
  infoBoxTxt: { flex: 1, fontSize: 12, color: '#fbbf24', lineHeight: 17 },

  emptyTxt: { fontSize: 13, color: 'rgba(255,255,255,0.35)', textAlign: 'center', paddingVertical: 24 },
});

