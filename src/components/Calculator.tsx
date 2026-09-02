import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  StyleSheet,
  TouchableOpacity,
  TextInput as RNTextInput,
  Animated,
  Alert,
  Keyboard,
  Platform,
} from 'react-native';
import { Text, IconButton } from 'react-native-paper';
import { Ionicons } from '@expo/vector-icons';
import Reanimated, {
  useSharedValue,
  useAnimatedStyle,
  withTiming,
  withSequence,
  withSpring,
  interpolateColor,
  interpolate,
  Easing,
} from 'react-native-reanimated';
import axios from 'axios';
import { Colors } from '../constants/colors';
import { API_CONFIG } from '../constants/config';
import { formatInputAmount } from '../utils/formatters';
import socketService from '../services/socketService';

interface CalculatorProps {
  onOperationReady?: (operationType: 'Compra' | 'Venta', amountUSD: string, exchangeRate: number) => void;
  onAmountChange?: (isReady: boolean, operationType: 'Compra' | 'Venta', amountUSD: string, rate: number) => void;
  onRatesChange?: (rates: { compra: number; venta: number }) => void;
  onOperationTypeChange?: (tipo: 'Compra' | 'Venta') => void;
  externalOperationType?: 'Compra' | 'Venta';
  hideTabs?: boolean;
  showHeader?: boolean;
  showContinueButton?: boolean;
  showInitiateButton?: boolean;
  continueButtonText?: string;
  lightMode?: boolean;
  overrideRates?: { compra: number; venta: number } | null;
  showStrikeRate?: boolean;
}

interface ExchangeRates {
  compra: number;
  venta: number;
}

export const Calculator: React.FC<CalculatorProps> = ({
  onOperationReady,
  onAmountChange,
  onRatesChange,
  onOperationTypeChange,
  externalOperationType,
  hideTabs = false,
  showHeader = false,
  showContinueButton = false,
  showInitiateButton = false,
  continueButtonText = 'CONTINUAR',
  lightMode = false,
  overrideRates = null,
  showStrikeRate = false,
}) => {
  const [operationType, setOperationType] = useState<'Compra' | 'Venta'>('Compra');
  const activeOperationType = externalOperationType ?? operationType;
  const [amountUSD, setAmountUSD] = useState('');
  const [amountPEN, setAmountPEN] = useState('');
  const [exchangeRates, setExchangeRates] = useState<ExchangeRates | null>(null);

  const rotateAnim = useRef(new Animated.Value(0)).current;

  // Reanimated shared values
  const tabProgress = useSharedValue(0);   // 0 = Compra, 1 = Venta
  const swapScale   = useSharedValue(1);

  // Fondo animado de cada tarjeta (verde sólido cuando está activa)
  const animCompraTabStyle = useAnimatedStyle(() => ({
    backgroundColor: interpolateColor(
      tabProgress.value, [0, 1],
      ['rgba(34,197,94,0.22)', 'transparent'],
    ),
  }));
  const animVentaTabStyle = useAnimatedStyle(() => ({
    backgroundColor: interpolateColor(
      tabProgress.value, [0, 1],
      ['transparent', 'rgba(34,197,94,0.22)'],
    ),
  }));

  // Opacidad del valor: lleno cuando activo, atenuado cuando inactivo
  const animCompraValueStyle = useAnimatedStyle(() => ({
    opacity: interpolate(tabProgress.value, [0, 1], [1, 0.42]),
  }));
  const animVentaValueStyle = useAnimatedStyle(() => ({
    opacity: interpolate(tabProgress.value, [0, 1], [0.42, 1]),
  }));

  const animSwapStyle = useAnimatedStyle(() => ({
    transform: [{ scale: swapScale.value }],
  }));

  // TC efectivo: usa la mejora por volumen/cupón si está disponible
  const effectiveRates = overrideRates ?? exchangeRates;

  // Máximo 2 decimales en inputs de usuario
  const limitDecimals = (v: string): string => {
    const dot = v.indexOf('.');
    return dot === -1 ? v : v.slice(0, dot + 3);
  };

  // Formatear con separador de miles para mostrar en el input (no afecta el valor interno)
  const formatDisplay = (v: string): string => {
    if (!v) return v;
    const [intPart, decPart] = v.split('.');
    const formatted = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    return decPart !== undefined ? `${formatted}.${decPart}` : formatted;
  };

  const inputCurrency = activeOperationType === 'Compra' ? 'USD' : 'PEN';
  const outputCurrency = activeOperationType === 'Compra' ? 'PEN' : 'USD';

  useEffect(() => {
    fetchExchangeRates();

    // Escuchar cambios en tipos de cambio en tiempo real
    const handleExchangeRatesUpdate = (data: any) => {
      console.log('📱 Calculator: Tipos de cambio actualizados en tiempo real:', data);
      // Actualizar tipos de cambio directamente desde el evento
      setExchangeRates({
        compra: data.compra,
        venta: data.venta,
      });
    };

    socketService.on('tipos_cambio_actualizados', handleExchangeRatesUpdate);

    return () => {
      socketService.off('tipos_cambio_actualizados', handleExchangeRatesUpdate);
    };
  }, []);

  // Sincronizar animación de tab cuando el tipo viene de afuera
  useEffect(() => {
    if (externalOperationType !== undefined) {
      tabProgress.value = withTiming(externalOperationType === 'Venta' ? 1 : 0, {
        duration: 280,
        easing: Easing.out(Easing.cubic),
      });
    }
  }, [externalOperationType]);

  // Notificar al padre cuando cambian los rates
  useEffect(() => {
    if (exchangeRates) onRatesChange?.(exchangeRates);
  }, [exchangeRates]);

  useEffect(() => {
    calculateAmount();
  }, [activeOperationType, exchangeRates, overrideRates]);

  const fetchExchangeRates = async () => {
    try {
      const response = await axios.get<{ success: boolean; rates: ExchangeRates }>(
        `${API_CONFIG.BASE_URL}/api/client/exchange-rates`
      );
      if (response.data.success) {
        setExchangeRates(response.data.rates);
      }
    } catch (error) {
      console.error('Error fetching exchange rates:', error);
    }
  };

  const calculateAmount = () => {
    if (!amountUSD || !effectiveRates) {
      setAmountPEN('');
      onAmountChange?.(false, activeOperationType, '', 0);
      return;
    }

    const amount = parseFloat(amountUSD);
    if (isNaN(amount) || amount <= 0) {
      setAmountPEN('');
      onAmountChange?.(false, activeOperationType, '', 0);
      return;
    }

    if (activeOperationType === 'Compra') {
      const pen = (amount * effectiveRates.compra).toFixed(2);
      setAmountPEN(pen);
      onAmountChange?.(true, activeOperationType, amountUSD, effectiveRates.compra);
    } else {
      const usd = (amount / effectiveRates.venta).toFixed(2);
      setAmountPEN(usd);
      onAmountChange?.(true, activeOperationType, amountUSD, effectiveRates.venta);
    }
  };

  const handleInputChange = (text: string) => {
    const val = limitDecimals(text.replace(/,/g, ''));
    setAmountUSD(val);
    const amount = parseFloat(val);
    if (!effectiveRates || isNaN(amount) || amount <= 0) {
      setAmountPEN('');
      onAmountChange?.(false, activeOperationType, '', 0);
      return;
    }
    if (activeOperationType === 'Compra') {
      const out = (amount * effectiveRates.compra).toFixed(2);
      setAmountPEN(out);
      onAmountChange?.(true, activeOperationType, val, effectiveRates.compra);
    } else {
      const out = (amount / effectiveRates.venta).toFixed(2);
      setAmountPEN(out);
      onAmountChange?.(true, activeOperationType, val, effectiveRates.venta);
    }
  };

  const handleOutputChange = (text: string) => {
    const val = limitDecimals(text.replace(/,/g, ''));
    setAmountPEN(val);
    const amount = parseFloat(val);
    if (!effectiveRates || isNaN(amount) || amount <= 0) {
      setAmountUSD('');
      onAmountChange?.(false, activeOperationType, '', 0);
      return;
    }
    if (activeOperationType === 'Compra') {
      const inp = (amount / effectiveRates.compra).toFixed(2);
      setAmountUSD(inp);
      onAmountChange?.(true, activeOperationType, inp, effectiveRates.compra);
    } else {
      const inp = (amount * effectiveRates.venta).toFixed(2);
      setAmountUSD(inp);
      onAmountChange?.(true, activeOperationType, inp, effectiveRates.venta);
    }
  };

  const switchTab = (tipo: 'Compra' | 'Venta') => {
    setOperationType(tipo);
    onOperationTypeChange?.(tipo);
    tabProgress.value = withTiming(tipo === 'Venta' ? 1 : 0, {
      duration: 280,
      easing: Easing.out(Easing.cubic),
    });
  };

  const handleSwapCurrency = () => {
    Animated.sequence([
      Animated.timing(rotateAnim, {
        toValue: 1,
        duration: 300,
        useNativeDriver: true,
      }),
      Animated.timing(rotateAnim, {
        toValue: 0,
        duration: 0,
        useNativeDriver: true,
      }),
    ]).start();

    swapScale.value = withSequence(
      withSpring(0.8, { damping: 4, stiffness: 300 }),
      withSpring(1,   { damping: 6, stiffness: 200 }),
    );

    const next = activeOperationType === 'Compra' ? 'Venta' : 'Compra';
    switchTab(next);
  };

  const handleContinue = () => {
    if (onOperationReady && amountUSD && exchangeRates) {
      const rate = activeOperationType === 'Compra' ? exchangeRates.compra : exchangeRates.venta;
      onOperationReady(activeOperationType, amountUSD, rate);
    }
  };

  const currentRate = effectiveRates
    ? activeOperationType === 'Compra'
      ? effectiveRates.compra
      : effectiveRates.venta
    : 0;

  const calculateSavings = () => {
    if (!amountPEN || !exchangeRates) return 0;
    const amount = parseFloat(amountPEN);
    const rate = activeOperationType === 'Venta' ? 0.063 : 0.021;
    return (amount * rate).toFixed(2);
  };

  const spin = rotateAnim.interpolate({
    inputRange: [0, 1],
    outputRange: ['0deg', '180deg'],
  });

  return (
    <View style={styles.container}>
      {showHeader && (
        <View style={styles.subtitleContainer}>
          <Text style={[styles.subtitle, lightMode && styles.subtitleLight]}>Tipo de cambio hoy en Perú</Text>
          <IconButton
            icon="help-circle-outline"
            size={18}
            iconColor={Colors.textMuted}
            onPress={() =>
              Alert.alert(
                'Tipo de cambio en vivo',
                'El tipo de cambio mostrado es en tiempo real y está sujeto a variación según el mercado. El valor final de tu operación se confirmará al momento de iniciarla.',
                [{ text: 'Entendido', style: 'default' }]
              )
            }
          />
        </View>
      )}

      {/* Tarjetas de tipo de cambio — Compra / Venta (ocultas cuando hideTabs=true) */}
      {!hideTabs && <View style={[styles.tabsContainer, lightMode && styles.tabsContainerLight]}>
        {/* Card Compra */}
        <TouchableOpacity onPress={() => switchTab('Compra')} activeOpacity={0.82} style={styles.rateTab}>
          <Reanimated.View style={[StyleSheet.absoluteFill, animCompraTabStyle]} />
          <Text style={[styles.rateTabLabel, lightMode && styles.rateTabLabelLight]}>Qoricash compra</Text>
          <Reanimated.Text style={[styles.rateTabValue, lightMode && styles.rateTabValueLight, animCompraValueStyle]}>
            S/ {exchangeRates?.compra.toFixed(3) || '—'}
          </Reanimated.Text>
          <View style={styles.rateTabPill}>
            <Text style={styles.rateTabPillText}>USD → PEN</Text>
          </View>
        </TouchableOpacity>

        <View style={styles.rateTabDivider} />

        {/* Card Venta */}
        <TouchableOpacity onPress={() => switchTab('Venta')} activeOpacity={0.82} style={styles.rateTab}>
          <Reanimated.View style={[StyleSheet.absoluteFill, animVentaTabStyle]} />
          <Text style={[styles.rateTabLabel, lightMode && styles.rateTabLabelLight]}>Qoricash vende</Text>
          <Reanimated.Text style={[styles.rateTabValue, lightMode && styles.rateTabValueLight, animVentaValueStyle]}>
            S/ {exchangeRates?.venta.toFixed(3) || '—'}
          </Reanimated.Text>
          <View style={styles.rateTabPill}>
            <Text style={styles.rateTabPillText}>PEN → USD</Text>
          </View>
        </TouchableOpacity>
      </View>}

      {/* Calculadora */}
      <View style={styles.calculatorContainer}>
        {/* Fila superior: Input y Moneda */}
        <View style={styles.calculatorRow}>
          <View style={[styles.inputBox, lightMode && styles.inputBoxLight]}>
            <Text style={[styles.inputLabel, lightMode && styles.inputLabelLight]}>¿Cuánto envías?</Text>
            <RNTextInput
              value={formatDisplay(amountUSD)}
              onChangeText={handleInputChange}
              keyboardType="decimal-pad"
              placeholder="0"
              placeholderTextColor={Colors.textMuted}
              style={[styles.inputAmount, lightMode && styles.amountLight]}
              returnKeyType="done"
              onSubmitEditing={() => Keyboard.dismiss()}
            />
          </View>
          <View style={styles.currencyBox}>
            <Text style={styles.currencySymbol}>
              {inputCurrency === 'USD' ? '$' : 'S/'}
            </Text>
            <Text style={styles.currencyText}>
              {inputCurrency === 'USD' ? 'Dólares' : 'Soles'}
            </Text>
          </View>
        </View>

        {/* Botón de intercambio */}
        <TouchableOpacity onPress={handleSwapCurrency} activeOpacity={0.8} style={{ zIndex: 100 }}>
          <Reanimated.View style={[styles.swapButton, animSwapStyle]}>
            <Animated.View style={{ transform: [{ rotate: spin }] }}>
              <IconButton icon="swap-vertical" size={24} iconColor={Colors.textDark} />
            </Animated.View>
          </Reanimated.View>
        </TouchableOpacity>

        {/* Fila inferior: Output y Moneda */}
        <View style={styles.calculatorRow}>
          <View style={[styles.inputBox, lightMode && styles.inputBoxLight]}>
            <Text style={[styles.inputLabel, lightMode && styles.inputLabelLight]}>Entonces recibes</Text>
            <RNTextInput
              value={formatDisplay(amountPEN)}
              onChangeText={handleOutputChange}
              keyboardType="decimal-pad"
              placeholder="0.00"
              placeholderTextColor={Colors.textMuted}
              style={[styles.outputAmount, lightMode && styles.amountLight]}
              returnKeyType="done"
              onSubmitEditing={() => Keyboard.dismiss()}
            />
          </View>
          <View style={styles.currencyBox}>
            <Text style={styles.currencySymbol}>
              {outputCurrency === 'USD' ? '$' : 'S/'}
            </Text>
            <Text style={styles.currencyText}>
              {outputCurrency === 'USD' ? 'Dólares' : 'Soles'}
            </Text>
          </View>
        </View>

        {/* Tip mejora TC */}
        <Text style={styles.tcTip}>✦ Mejora tu tipo de cambio para importes mayores a $3,000</Text>

        {/* Información adicional */}
        {amountPEN && (
          <View style={styles.infoRow}>
            <Text style={[styles.infoText, lightMode && styles.infoTextLight]}>
              Ahorro estimado: S/ {formatInputAmount(String(calculateSavings()))}
            </Text>
            <View style={{ alignItems: 'flex-end' }}>
              {showStrikeRate && currentRate > 0 && (
                <Text style={styles.strikeRateText}>
                  {activeOperationType === 'Compra'
                    ? (currentRate - 0.003).toFixed(4)
                    : (currentRate + 0.003).toFixed(4)}
                </Text>
              )}
              <Text style={[styles.infoText, lightMode && styles.infoTextLight]}>
                TC: {currentRate.toFixed(4)}
              </Text>
            </View>
          </View>
        )}
      </View>


      {/* Botón Continuar o Iniciar Operación (opcional) */}
      {(showContinueButton || showInitiateButton) && (
        <TouchableOpacity
          style={[
            styles.continueButton,
            (!amountUSD || !amountPEN) && styles.continueButtonDisabled
          ]}
          onPress={handleContinue}
          activeOpacity={0.8}
          disabled={!amountUSD || !amountPEN}
        >
          <Text style={[
            styles.continueButtonText,
            showInitiateButton && styles.initiateButtonText,
            (!amountUSD || !amountPEN) && styles.continueButtonTextDisabled
          ]}>
            {showInitiateButton ? 'INICIAR OPERACIÓN' : continueButtonText}
          </Text>
        </TouchableOpacity>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    width: '100%',
  },
  subtitleContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 20,
  },
  subtitle: {
    fontSize: 15,
    color: '#FFFFFF',
  },
  tabsContainer: {
    flexDirection: 'row',
    backgroundColor: 'rgba(255,255,255,0.09)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.17)',
    borderRadius: 22,
    marginBottom: 24,
    overflow: 'hidden',
  },
  rateTab: {
    flex: 1,
    paddingVertical: 20,
    paddingHorizontal: 18,
    gap: 6,
    overflow: 'hidden',
  },
  rateTabLabel: {
    fontSize: 11,
    color: 'rgba(255,255,255,0.52)',
    letterSpacing: 1.4,
    textTransform: 'uppercase',
    fontWeight: '400',
  },
  rateTabLabelLight: {
    color: '#94a3b8',
  },
  rateTabValue: {
    fontSize: 26,
    fontWeight: '700',
    color: '#FFFFFF',
    letterSpacing: -0.5,
    lineHeight: 32,
  },
  rateTabValueLight: {
    color: '#0D1B2A',
  },
  rateTabPill: {
    alignSelf: 'flex-start',
    backgroundColor: 'rgba(255,255,255,0.25)',
    borderRadius: 20,
    paddingHorizontal: 8,
    paddingVertical: 3,
    marginTop: 2,
  },
  rateTabPillText: {
    fontSize: 9.5,
    color: 'rgba(255,255,255,0.55)',
    letterSpacing: 0.3,
  },
  rateTabDivider: {
    width: 1,
    backgroundColor: 'rgba(255,255,255,0.17)',
    marginVertical: 16,
  },
  calculatorContainer: {
    marginBottom: 20,
    marginHorizontal: 8,
  },
  calculatorRow: {
    flexDirection: 'row',
    marginBottom: 16,
    zIndex: 1,
  },
  inputBox: {
    flex: 1,
    backgroundColor: 'rgba(255,255,255,0.25)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.17)',
    borderRadius: 20,
    padding: 16,
    marginRight: 10,
    zIndex: 1,
  },
  inputLabel: {
    fontSize: 13,
    color: '#FFFFFF',
    marginBottom: 6,
  },
  inputAmount: {
    fontSize: 30,
    fontWeight: 'bold',
    color: '#FFFFFF',
    padding: 0,
    margin: 0,
  },
  outputAmount: {
    fontSize: 30,
    fontWeight: 'bold',
    color: '#FFFFFF',
  },
  currencyBox: {
    width: 95,
    backgroundColor: 'rgba(255,255,255,0.25)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.17)',
    borderRadius: 20,
    padding: 16,
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1,
  },
  currencySymbol: {
    fontSize: 22,
    fontWeight: '800',
    color: '#FFFFFF',
    textAlign: 'center',
    marginBottom: 2,
  },
  currencyText: {
    fontSize: 12,
    fontWeight: '600',
    color: 'rgba(255,255,255,0.85)',
    textAlign: 'center',
  },
  swapButton: {
    alignSelf: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 26,
    width: 52,
    height: 52,
    alignItems: 'center',
    justifyContent: 'center',
    marginVertical: -34,
    zIndex: 100,
    elevation: 10,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.25,
    shadowRadius: 8,
  },
  tcTip: {
    fontSize: 11,
    color: 'rgba(255,255,255,0.32)',
    textAlign: 'center',
    letterSpacing: 0.2,
    marginTop: 10,
    marginBottom: 2,
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 12,
    paddingHorizontal: 4,
  },
  infoText: {
    fontSize: 13,
    color: '#FFFFFF',
    fontWeight: '500',
  },
  strikeRateText: {
    fontSize: 11,
    color: 'rgba(255,255,255,0.38)',
    textDecorationLine: 'line-through',
    marginBottom: 1,
  },
  continueButton: {
    backgroundColor: Colors.primary,
    borderRadius: 12,
    paddingVertical: 16,
    marginTop: 20,
    marginHorizontal: 8,
    alignItems: 'center',
    justifyContent: 'center',
    elevation: 4,
    shadowColor: Colors.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
  },
  continueButtonDisabled: {
    backgroundColor: Colors.border,
    shadowColor: Colors.border,
  },
  continueButtonText: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#FFFFFF',
    letterSpacing: 1,
  },
  initiateButtonText: {
    color: '#FFFFFF',
  },
  continueButtonTextDisabled: {
    color: Colors.textMuted,
  },
  keyboardAccessory: {
    backgroundColor: '#CDD0D6',
    flexDirection: 'row',
    justifyContent: 'flex-end',
    alignItems: 'center',
    paddingHorizontal: 3,
    paddingVertical: 5,
    // Sin borde superior — el separador lo pone el OS y no se puede quitar,
    // pero eliminando padding extra se reduce el "gap" visual
  },
  keyboardKey: {
    backgroundColor: '#ADB5BD',   // color de teclas modificadoras iOS (shift/delete)
    borderRadius: 5,
    paddingHorizontal: 18,
    height: 42,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.32,
    shadowRadius: 0,
    elevation: 2,
  },
  keyboardKeyIcon: {
    fontSize: 19,
    color: '#000000',
    lineHeight: 22,
    fontWeight: '600',
  },

  /* ── Light mode overrides ── */
  subtitleLight: {
    color: '#64748b',
  },
  tabsContainerLight: {
    backgroundColor: '#F1F5F9',
    borderColor: '#E2E8F0',
  },
  inputBoxLight: {
    backgroundColor: '#F8FAFC',
    borderWidth: 1,
    borderColor: '#E2E8F0',
  },
  inputLabelLight: {
    color: '#64748b',
  },
  amountLight: {
    color: '#0D1B2A',
  },
  infoTextLight: {
    color: '#64748b',
  },
});