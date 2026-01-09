import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  StyleSheet,
  TouchableOpacity,
  TextInput as RNTextInput,
  Animated,
} from 'react-native';
import { Text, IconButton } from 'react-native-paper';
import axios from 'axios';
import { Colors } from '../constants/colors';
import { API_CONFIG } from '../constants/config';
import socketService from '../services/socketService';

interface CalculatorProps {
  onOperationReady?: (operationType: 'Compra' | 'Venta', amountUSD: string, exchangeRate: number) => void;
  showHeader?: boolean;
  showContinueButton?: boolean;
  showInitiateButton?: boolean;
  continueButtonText?: string;
}

interface ExchangeRates {
  compra: number;
  venta: number;
}

export const Calculator: React.FC<CalculatorProps> = ({
  onOperationReady,
  showHeader = false,
  showContinueButton = false,
  showInitiateButton = false,
  continueButtonText = 'CONTINUAR',
}) => {
  const [operationType, setOperationType] = useState<'Compra' | 'Venta'>('Compra');
  const [amountUSD, setAmountUSD] = useState('');
  const [amountPEN, setAmountPEN] = useState('');
  const [exchangeRates, setExchangeRates] = useState<ExchangeRates | null>(null);

  const rotateAnim = useRef(new Animated.Value(0)).current;

  const inputCurrency = operationType === 'Compra' ? 'USD' : 'PEN';
  const outputCurrency = operationType === 'Compra' ? 'PEN' : 'USD';

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

  useEffect(() => {
    calculateAmount();
  }, [amountUSD, operationType, exchangeRates]);

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
    if (!amountUSD || !exchangeRates) {
      setAmountPEN('');
      return;
    }

    const amount = parseFloat(amountUSD);
    if (isNaN(amount) || amount <= 0) {
      setAmountPEN('');
      return;
    }

    if (operationType === 'Compra') {
      const pen = (amount * exchangeRates.compra).toFixed(2);
      setAmountPEN(pen);
    } else {
      const usd = (amount / exchangeRates.venta).toFixed(2);
      setAmountPEN(usd);
    }
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

    setOperationType(operationType === 'Compra' ? 'Venta' : 'Compra');
  };

  const handleContinue = () => {
    if (onOperationReady && amountUSD && exchangeRates) {
      const rate = operationType === 'Compra' ? exchangeRates.compra : exchangeRates.venta;
      onOperationReady(operationType, amountUSD, rate);
    }
  };

  const currentRate = exchangeRates
    ? operationType === 'Compra'
      ? exchangeRates.compra
      : exchangeRates.venta
    : 0;

  const calculateSavings = () => {
    if (!amountPEN || !exchangeRates) return 0;
    const amount = parseFloat(amountPEN);
    return (amount * 0.03).toFixed(2);
  };

  const spin = rotateAnim.interpolate({
    inputRange: [0, 1],
    outputRange: ['0deg', '180deg'],
  });

  return (
    <View style={styles.container}>
      {showHeader && (
        <View style={styles.subtitleContainer}>
          <Text style={styles.subtitle}>Tipo de cambio hoy en Perú</Text>
          <IconButton icon="help-circle-outline" size={18} iconColor={Colors.textMuted} />
        </View>
      )}

      {/* Tabs de Compra/Venta */}
      <View style={styles.tabsContainer}>
        <TouchableOpacity
          style={[styles.tab, operationType === 'Compra' && styles.tabActive]}
          onPress={() => {
            setOperationType('Compra');
            setAmountUSD('');
            setAmountPEN('');
          }}
          activeOpacity={0.8}
        >
          <Text style={[styles.tabText, operationType === 'Compra' && styles.tabTextActive]}>
            Compra: {exchangeRates?.compra.toFixed(3) || '0.000'}
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tab, operationType === 'Venta' && styles.tabActive]}
          onPress={() => {
            setOperationType('Venta');
            setAmountUSD('');
            setAmountPEN('');
          }}
          activeOpacity={0.8}
        >
          <Text style={[styles.tabText, operationType === 'Venta' && styles.tabTextActive]}>
            Venta: {exchangeRates?.venta.toFixed(3) || '0.000'}
          </Text>
        </TouchableOpacity>
      </View>

      {/* Calculadora */}
      <View style={styles.calculatorContainer}>
        {/* Fila superior: Input y Moneda */}
        <View style={styles.calculatorRow}>
          <View style={styles.inputBox}>
            <Text style={styles.inputLabel}>¿Cuánto envías?</Text>
            <RNTextInput
              value={amountUSD}
              onChangeText={setAmountUSD}
              keyboardType="decimal-pad"
              placeholder="0"
              placeholderTextColor={Colors.textMuted}
              style={styles.inputAmount}
            />
          </View>
          <View style={styles.currencyBox}>
            <Text style={styles.currencyText}>
              {inputCurrency === 'USD' ? 'Dólares' : 'Soles'}
            </Text>
          </View>
        </View>

        {/* Botón de intercambio */}
        <TouchableOpacity onPress={handleSwapCurrency} activeOpacity={0.8} style={{ zIndex: 100 }}>
          <Animated.View style={[styles.swapButton, { transform: [{ rotate: spin }] }]}>
            <IconButton icon="swap-vertical" size={24} iconColor={Colors.textDark} />
          </Animated.View>
        </TouchableOpacity>

        {/* Fila inferior: Output y Moneda */}
        <View style={styles.calculatorRow}>
          <View style={styles.inputBox}>
            <Text style={styles.inputLabel}>Entonces recibes</Text>
            <Text style={styles.outputAmount}>
              {amountPEN || '0.00'}
            </Text>
          </View>
          <View style={styles.currencyBox}>
            <Text style={styles.currencyText}>
              {outputCurrency === 'USD' ? 'Dólares' : 'Soles'}
            </Text>
          </View>
        </View>

        {/* Información adicional */}
        {amountPEN && (
          <View style={styles.infoRow}>
            <Text style={styles.infoText}>
              Ahorro estimado: S/ {calculateSavings()}
            </Text>
            <Text style={styles.infoText}>
              Tipo de cambio: {currentRate.toFixed(3)}
            </Text>
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
    color: Colors.textDark,
  },
  tabsContainer: {
    flexDirection: 'row',
    marginBottom: 24,
    marginHorizontal: 8,
    borderRadius: 12,
    overflow: 'hidden',
  },
  tab: {
    flex: 1,
    paddingVertical: 16,
    paddingHorizontal: 12,
    backgroundColor: '#FFFFFF',
    alignItems: 'center',
    justifyContent: 'center',
  },
  tabActive: {
    backgroundColor: Colors.secondary,
  },
  tabText: {
    fontSize: 14,
    fontWeight: '600',
    color: Colors.textMuted,
  },
  tabTextActive: {
    color: '#FFFFFF',
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
    backgroundColor: '#E8E8E8',
    borderRadius: 14,
    padding: 16,
    marginRight: 10,
    zIndex: 1,
  },
  inputLabel: {
    fontSize: 13,
    color: Colors.textDark,
    marginBottom: 6,
  },
  inputAmount: {
    fontSize: 30,
    fontWeight: 'bold',
    color: Colors.textDark,
    padding: 0,
    margin: 0,
  },
  outputAmount: {
    fontSize: 30,
    fontWeight: 'bold',
    color: Colors.textDark,
  },
  currencyBox: {
    width: 95,
    backgroundColor: Colors.secondary,
    borderRadius: 14,
    padding: 16,
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1,
  },
  currencyText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#FFFFFF',
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
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 12,
    paddingHorizontal: 4,
  },
  infoText: {
    fontSize: 13,
    color: Colors.textDark,
    fontWeight: '500',
  },
  continueButton: {
    backgroundColor: '#82C16C',
    borderRadius: 12,
    paddingVertical: 16,
    marginTop: 20,
    marginHorizontal: 8,
    alignItems: 'center',
    justifyContent: 'center',
    elevation: 4,
    shadowColor: '#82C16C',
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
});
