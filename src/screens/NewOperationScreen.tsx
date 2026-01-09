import React, { useState, useEffect } from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  Alert,
  TouchableOpacity,
  SafeAreaView,
} from 'react-native';
import {
  TextInput,
  Button,
  Text,
  SegmentedButtons,
  Card,
  HelperText,
  Divider,
  RadioButton,
  Dialog,
  Portal,
  IconButton,
  Menu,
  Chip,
} from 'react-native-paper';
import { useAuth } from '../contexts/AuthContext';
import { operationsApi } from '../api/operations';
import { CreateOperationForm, BankAccount } from '../types';
import { formatCurrency, calculateAmount, formatExchangeRate } from '../utils/formatters';
import { Colors } from '../constants/colors';
import axios from 'axios';
import { API_CONFIG } from '../constants/config';
import { GlobalStyles } from '../styles/globalStyles';
import { CustomModal } from '../components/CustomModal';
import { KeyboardAwareScrollView } from '../components/KeyboardAwareScrollView';

interface NewOperationScreenProps {
  navigation: any;
  route?: any;
}

// Exchange rates will be fetched from API dynamically

// Available banks
const BANKS_LIMA = ['BCP', 'INTERBANK', 'PICHINCHA', 'BANBIF', 'BBVA', 'Scotiabank', 'Otros'];
const BANKS_PROVINCIA = ['BCP', 'INTERBANK'];

export const NewOperationScreen: React.FC<NewOperationScreenProps> = ({ navigation, route }) => {
  const { client, refreshClient } = useAuth();

  // State for real-time exchange rates
  const [realExchangeRates, setRealExchangeRates] = useState({ compra: 3.75, venta: 3.77 });

  // Get params from HomeScreen
  const params = route?.params || {};
  const initialOperationType = params.operationType || 'Compra';
  const initialAmount = params.amountUSD || '';
  const initialExchangeRate = params.exchangeRate || realExchangeRates.compra;

  const [operationType, setOperationType] = useState<'Compra' | 'Venta'>(initialOperationType);
  const [amountUsd, setAmountUsd] = useState(initialAmount);
  const [exchangeRate, setExchangeRate] = useState(initialExchangeRate.toString());
  const [sourceAccount, setSourceAccount] = useState('');
  const [destinationAccount, setDestinationAccount] = useState('');
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<any>({});

  // Add Bank Account Modal States
  const [addAccountDialogVisible, setAddAccountDialogVisible] = useState(false);
  const [addAccountType, setAddAccountType] = useState<'source' | 'destination'>('source');
  const [newAccountOrigen, setNewAccountOrigen] = useState('Lima');
  const [newAccountBank, setNewAccountBank] = useState('');
  const [newAccountBankCustomName, setNewAccountBankCustomName] = useState('');
  const [newAccountType, setNewAccountType] = useState('Ahorro');
  const [newAccountNumber, setNewAccountNumber] = useState('');
  const [newAccountCCI, setNewAccountCCI] = useState('');
  const [addingAccount, setAddingAccount] = useState(false);
  const [bankMenuVisible, setBankMenuVisible] = useState(false);

  // Account Selection Dialogs
  const [sourceAccountDialogVisible, setSourceAccountDialogVisible] = useState(false);
  const [destinationAccountDialogVisible, setDestinationAccountDialogVisible] = useState(false);

  const accountsPEN = client?.bank_accounts?.filter((acc) => acc.currency === 'S/') || [];
  const accountsUSD = client?.bank_accounts?.filter((acc) => acc.currency === '$') || [];

  // Fetch real exchange rates on component mount
  useEffect(() => {
    const fetchExchangeRates = async () => {
      try {
        const response = await axios.get<{ success: boolean; rates: { compra: number; venta: number } }>(
          `${API_CONFIG.BASE_URL}/api/client/exchange-rates`
        );
        if (response.data.success) {
          setRealExchangeRates(response.data.rates);
          console.log('📊 Tipos de cambio reales obtenidos:', response.data.rates);

          // Establecer el tipo de cambio inicial según el tipo de operación
          const rate = initialOperationType === 'Compra' ? response.data.rates.compra : response.data.rates.venta;
          setExchangeRate(rate.toString());
          console.log(`💱 Tipo de cambio inicial establecido: ${rate} para ${initialOperationType}`);
        }
      } catch (error) {
        console.error('Error fetching exchange rates:', error);
      }
    };
    fetchExchangeRates();
  }, []);

  // Update exchange rate when operation type changes DYNAMICALLY
  useEffect(() => {
    // Actualizar tipo de cambio según el tipo de operación seleccionado
    // Usar tipos de cambio reales (compra o venta) según corresponda
    const newRate = operationType === 'Compra' ? realExchangeRates.compra : realExchangeRates.venta;
    setExchangeRate(newRate.toString());
    console.log(`💱 Tipo de cambio actualizado a ${newRate} para ${operationType}`);

    // Reset accounts when operation type changes to avoid mismatched currencies
    setSourceAccount('');
    setDestinationAccount('');
  }, [operationType, realExchangeRates]);

  const calculatePEN = () => {
    if (!amountUsd || !exchangeRate) return 0;
    const amount = parseFloat(amountUsd);
    const rate = parseFloat(exchangeRate);

    // En Compra: USD -> PEN (multiplicar)
    // En Venta: PEN -> USD (dividir)
    if (operationType === 'Compra') {
      return parseFloat((amount * rate).toFixed(2));
    } else {
      return parseFloat((amount / rate).toFixed(2));
    }
  };

  const validate = () => {
    const newErrors: any = {};

    if (!amountUsd || parseFloat(amountUsd) <= 0) {
      newErrors.amountUsd = 'Ingrese un monto válido';
    }

    if (!exchangeRate || parseFloat(exchangeRate) <= 0) {
      newErrors.exchangeRate = 'Ingrese un tipo de cambio válido';
    }

    if (!sourceAccount) {
      newErrors.sourceAccount = 'Seleccione cuenta de origen';
    }

    if (!destinationAccount) {
      newErrors.destinationAccount = 'Seleccione cuenta de destino';
    }

    if (!termsAccepted) {
      newErrors.termsAccepted = 'Debe aceptar la declaración para continuar';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async () => {
    if (!validate() || !client) return;

    // Verificar si el cliente tiene documentos completos
    if (!client.has_complete_documents) {
      // DEBUG: Ver qué valores tiene el cliente
      console.log('🔍 DEBUG - Cliente:', {
        document_type: client.document_type,
        has_complete_documents: client.has_complete_documents,
        dni_front_url: client.dni_front_url,
        dni_back_url: client.dni_back_url,
        dni_representante_front_url: client.dni_representante_front_url,
        dni_representante_back_url: client.dni_representante_back_url,
      });

      // Diferenciar entre dos casos:
      // 1. Cliente NO ha subido documentos
      // 2. Cliente SÍ ha subido documentos pero están en proceso de validación

      // Verificar según el tipo de documento
      // Persona Natural (DNI/CE): dni_front_url y dni_back_url
      // Persona Jurídica (RUC): dni_representante_front_url y dni_representante_back_url
      const isPersonaNatural = client.document_type === 'DNI' || client.document_type === 'CE';
      const hasUploadedDocuments = isPersonaNatural
        ? (client.dni_front_url && client.dni_back_url)
        : (client.dni_representante_front_url && client.dni_representante_back_url);

      console.log('🔍 DEBUG - Validación:', {
        isPersonaNatural,
        hasUploadedDocuments,
      });

      if (!hasUploadedDocuments) {
        // Caso 1: No ha subido documentos
        Alert.alert(
          'Validación de Identidad Requerida',
          'Necesitamos validar tu DNI antes de iniciar una operación.\n\nPor favor, sube las fotos de tu DNI desde la pantalla de inicio.',
          [
            {
              text: 'Entendido',
              onPress: () => {
                // Regresar a la pantalla de inicio
                navigation.navigate('HomeTab');
              }
            }
          ]
        );
      } else {
        // Caso 2: Ya subió documentos pero están en validación
        Alert.alert(
          'Validación en Proceso',
          'Nuestro equipo está validando tus documentos.\n\n⏱️ Tiempo promedio de respuesta: 10 minutos\n\nTe notificaremos cuando tu cuenta sea activada y puedas realizar operaciones.',
          [
            {
              text: 'Entendido',
              onPress: () => {
                // Regresar a la pantalla de inicio
                navigation.navigate('HomeTab');
              }
            }
          ]
        );
      }
      return;
    }

    try {
      setLoading(true);

      // Verificar si hay operaciones activas (Pendiente o En proceso)
      console.log('🔍 Verificando operaciones activas para DNI:', client.dni);
      const response = await axios.get(
        `${API_CONFIG.BASE_URL}/api/client/my-operations/${client.dni}`
      );

      if (response.data.success) {
        const activeOperations = response.data.operations.filter(
          (op: any) => op.status === 'Pendiente' || op.status === 'En proceso'
        );

        if (activeOperations.length > 0) {
          console.log('⚠️ Operación activa encontrada:', activeOperations[0].operation_id);
          Alert.alert(
            'Operación en curso',
            `Ya tienes una operación activa (${activeOperations[0].operation_id}). Debes completar o cancelar tu operación actual antes de crear una nueva.`,
            [{ text: 'Entendido' }]
          );
          setLoading(false);
          return;
        }
      }

      console.log('✅ No hay operaciones activas, creando nueva operación...');

      const operationData: CreateOperationForm = {
        operation_type: operationType,
        amount_usd: amountUsd,
        exchange_rate: exchangeRate,
        source_account: sourceAccount,
        destination_account: destinationAccount,
        terms_accepted: termsAccepted,
        notes: '',
      };

      const newOperation = await operationsApi.createOperation(client.dni, operationData);

      // Navigate to Transfer screen
      navigation.replace('Transfer', { operation: newOperation });
    } catch (error: any) {
      console.error('❌ Error en handleSubmit:', error);
      Alert.alert('Error', error.message || 'Error al crear operación');
    } finally {
      setLoading(false);
    }
  };

  const resetForm = () => {
    setAmountUsd('');
    setSourceAccount('');
    setDestinationAccount('');
    setTermsAccepted(false);
    setErrors({});
  };

  const handleOpenAddAccountDialog = (type: 'source' | 'destination') => {
    setAddAccountType(type);
    setNewAccountOrigen('Lima');
    setNewAccountBank('');
    setNewAccountBankCustomName('');
    setNewAccountType('Ahorro');
    setNewAccountNumber('');
    setNewAccountCCI('');
    setAddAccountDialogVisible(true);
  };

  const handleAddBankAccount = async () => {
    if (!client) return;

    // Validaciones
    if (!newAccountBank) {
      Alert.alert('Error', 'Seleccione un banco');
      return;
    }

    // Si es "Otros", validar que haya ingresado el nombre del banco
    if (newAccountBank === 'Otros' && !newAccountBankCustomName.trim()) {
      Alert.alert('Error', 'Ingrese el nombre del banco');
      return;
    }

    const mainBanks = ['BCP', 'INTERBANK', 'PICHINCHA', 'BANBIF'];
    const needsCCIValue = !mainBanks.includes(newAccountBank);

    if (needsCCIValue && (!newAccountCCI || newAccountCCI.length !== 20)) {
      Alert.alert('Error', 'Para este banco debe ingresar el CCI de 20 dígitos');
      return;
    }

    if (!needsCCIValue && !newAccountNumber) {
      Alert.alert('Error', 'Ingrese el número de cuenta');
      return;
    }

    try {
      setAddingAccount(true);

      // Determinar la moneda según el tipo de cuenta que se está agregando
      const isSourceUSD = (operationType === 'Compra' && addAccountType === 'source') ||
                         (operationType === 'Venta' && addAccountType === 'destination');
      const currency = isSourceUSD ? '$' : 'S/';

      const API_CONFIG = require('../constants/config').API_CONFIG;

      // Determinar el nombre del banco a enviar
      const bankNameToSend = newAccountBank === 'Otros' ? newAccountBankCustomName.trim() : newAccountBank;

      const response = await fetch(
        `${API_CONFIG.BASE_URL}/api/client/add-bank-account/${client.dni}`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            origen: newAccountOrigen,
            bank_name: bankNameToSend,
            account_type: newAccountType,
            currency: currency,
            account_number: needsCCIValue ? newAccountCCI : newAccountNumber,
            cci: needsCCIValue ? newAccountCCI : undefined,
          }),
        }
      );

      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(data.message || 'Error al agregar cuenta');
      }

      // Refrescar datos del cliente
      if (refreshClient) {
        await refreshClient();
      }

      Alert.alert('Éxito', 'Cuenta bancaria agregada exitosamente');
      setAddAccountDialogVisible(false);
    } catch (error: any) {
      Alert.alert('Error', error.message || 'Error al agregar cuenta bancaria');
    } finally {
      setAddingAccount(false);
    }
  };

  const getAvailableBanks = () => {
    return newAccountOrigen === 'Lima' ? BANKS_LIMA : BANKS_PROVINCIA;
  };

  const needsCCI = () => {
    const mainBanks = ['BCP', 'INTERBANK', 'PICHINCHA', 'BANBIF'];
    return newAccountBank && !mainBanks.includes(newAccountBank);
  };

  const renderAccountOption = (account: BankAccount) => {
    return `${account.bank_name} - ${account.account_type} (${account.currency}) - ****${account.account_number.slice(-4)}`;
  };

  const getSelectedSourceAccountText = () => {
    if (!sourceAccount) return 'Seleccionar Cuenta';
    const accounts = operationType === 'Venta' ? accountsPEN : accountsUSD;
    const selected = accounts.find(acc => acc.account_number === sourceAccount);
    return selected ? renderAccountOption(selected) : 'Seleccionar Cuenta';
  };

  const getSelectedDestinationAccountText = () => {
    if (!destinationAccount) return 'Seleccionar Cuenta';
    const accounts = operationType === 'Venta' ? accountsUSD : accountsPEN;
    const selected = accounts.find(acc => acc.account_number === destinationAccount);
    return selected ? renderAccountOption(selected) : 'Seleccionar Cuenta';
  };

  const inputCurrency = operationType === 'Compra' ? 'USD' : 'PEN';
  const outputCurrency = operationType === 'Compra' ? 'PEN' : 'USD';
  const amountToSend = parseFloat(amountUsd) || 0;
  const amountToReceive = calculatePEN();

  return (
    <SafeAreaView style={{ flex: 1, paddingTop: 20 }}>
      <KeyboardAwareScrollView>
        <Card style={styles.card}>
          <Card.Content>
            {/* Timeline Stepper */}
            <View style={styles.timelineContainer}>
              <View style={styles.timelineStep}>
                <View style={[styles.timelineDot, styles.timelineDotActive]}>
                  <Text style={[styles.timelineDotText, styles.timelineDotTextActive]}>1</Text>
                </View>
                <Text style={[styles.timelineLabel, styles.timelineLabelActive]}>Cotiza</Text>
              </View>
              <View style={styles.timelineLine} />
              <View style={styles.timelineStep}>
                <View style={styles.timelineDot}>
                  <Text style={styles.timelineDotText}>2</Text>
                </View>
                <Text style={styles.timelineLabel}>Transfiere</Text>
              </View>
              <View style={styles.timelineLine} />
              <View style={styles.timelineStep}>
                <View style={styles.timelineDot}>
                  <Text style={styles.timelineDotText}>3</Text>
                </View>
                <Text style={styles.timelineLabel}>Recibe</Text>
              </View>
            </View>

            {/* Operation Type Selector */}
            <View style={styles.operationTypeSelector}>
              <TouchableOpacity
                style={[
                  styles.operationTypeButton,
                  styles.operationTypeButtonLeft,
                  operationType === 'Compra' && styles.operationTypeButtonActive,
                ]}
                onPress={() => setOperationType('Compra')}
                activeOpacity={0.8}
              >
                <Text style={[
                  styles.operationTypeButtonText,
                  operationType === 'Compra' && styles.operationTypeButtonTextActive,
                ]}>
                  Compra
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[
                  styles.operationTypeButton,
                  styles.operationTypeButtonRight,
                  operationType === 'Venta' && styles.operationTypeButtonActive,
                ]}
                onPress={() => setOperationType('Venta')}
                activeOpacity={0.8}
              >
                <Text style={[
                  styles.operationTypeButtonText,
                  operationType === 'Venta' && styles.operationTypeButtonTextActive,
                ]}>
                  Venta
                </Text>
              </TouchableOpacity>
            </View>

            {/* Operation Summary Card - Non Editable */}
            <Card style={styles.summaryCard}>
              <Card.Content>

                {/* Amount Sending */}
                <View style={styles.summaryRow}>
                  <View style={styles.summaryBox}>
                    <Text style={styles.summaryLabel}>¿Cuánto envías?</Text>
                    <Text style={styles.summaryAmount}>
                      {amountToSend.toFixed(2)}
                    </Text>
                  </View>
                  <View style={styles.summaryCurrencyBox}>
                    <Text style={styles.summaryCurrencyText}>
                      {inputCurrency === 'USD' ? 'Dólares' : 'Soles'}
                    </Text>
                  </View>
                </View>

                {/* Exchange Rate */}
                <View style={styles.exchangeRateRow}>
                  <Text style={styles.exchangeRateLabel}>Tipo de cambio</Text>
                  <Text style={styles.exchangeRateValue}>
                    {parseFloat(exchangeRate).toFixed(3)}
                  </Text>
                </View>

                {/* Amount Receiving */}
                <View style={styles.summaryRow}>
                  <View style={styles.summaryBox}>
                    <Text style={styles.summaryLabel}>Entonces recibes</Text>
                    <Text style={styles.summaryAmount}>
                      {amountToReceive.toFixed(2)}
                    </Text>
                  </View>
                  <View style={styles.summaryCurrencyBox}>
                    <Text style={styles.summaryCurrencyText}>
                      {outputCurrency === 'USD' ? 'Dólares' : 'Soles'}
                    </Text>
                  </View>
                </View>
              </Card.Content>
            </Card>

            <Divider style={styles.divider} />

            {/* Source Account */}
            <View style={styles.accountSection}>
              <View style={styles.accountHeader}>
                <Text variant="titleMedium" style={styles.accountTitle}>
                  Elige tu cuenta de cargo ({operationType === 'Venta' ? 'S/' : 'USD'})
                </Text>
                <TouchableOpacity
                  onPress={() => handleOpenAddAccountDialog('source')}
                  style={styles.addAccountButton}
                >
                  <Text style={styles.addAccountButtonText}>+ Agregar</Text>
                </TouchableOpacity>
              </View>
              <TouchableOpacity
                onPress={() => setSourceAccountDialogVisible(true)}
                style={styles.accountSelectButton}
                activeOpacity={0.8}
              >
                <Text style={[
                  styles.accountSelectButtonText,
                  !sourceAccount && styles.accountSelectButtonPlaceholder
                ]}>
                  {getSelectedSourceAccountText()}
                </Text>
                <IconButton icon="chevron-down" size={20} />
              </TouchableOpacity>
              {errors.sourceAccount && (
                <HelperText type="error" visible={!!errors.sourceAccount}>
                  {errors.sourceAccount}
                </HelperText>
              )}
            </View>

            <Divider style={styles.divider} />

            {/* Destination Account */}
            <View style={styles.accountSection}>
              <View style={styles.accountHeader}>
                <Text variant="titleMedium" style={styles.accountTitle}>
                  Elige tu cuenta de destino ({operationType === 'Venta' ? 'USD' : 'S/'})
                </Text>
                <TouchableOpacity
                  onPress={() => handleOpenAddAccountDialog('destination')}
                  style={styles.addAccountButton}
                >
                  <Text style={styles.addAccountButtonText}>+ Agregar</Text>
                </TouchableOpacity>
              </View>
              <TouchableOpacity
                onPress={() => setDestinationAccountDialogVisible(true)}
                style={styles.accountSelectButton}
                activeOpacity={0.8}
              >
                <Text style={[
                  styles.accountSelectButtonText,
                  !destinationAccount && styles.accountSelectButtonPlaceholder
                ]}>
                  {getSelectedDestinationAccountText()}
                </Text>
                <IconButton icon="chevron-down" size={20} />
              </TouchableOpacity>
              {errors.destinationAccount && (
                <HelperText type="error" visible={!!errors.destinationAccount}>
                  {errors.destinationAccount}
                </HelperText>
              )}
            </View>

            <Divider style={styles.divider} />

            {/* Terms and Conditions Checkbox */}
            <TouchableOpacity
              onPress={() => {
                setTermsAccepted(!termsAccepted);
                setErrors({ ...errors, termsAccepted: '' });
              }}
              activeOpacity={0.8}
              style={styles.checkboxContainer}
            >
              <View style={[
                styles.customCheckbox,
                termsAccepted && styles.customCheckboxChecked
              ]} />
              <Text style={styles.checkboxLabel}>
                Declaro como verdad que los fondos provienen producto de actividades lícitas y que soy el titular de las cuentas bancarias registradas
              </Text>
            </TouchableOpacity>
            {errors.termsAccepted && (
              <HelperText type="error" visible={!!errors.termsAccepted} style={styles.checkboxError}>
                {errors.termsAccepted}
              </HelperText>
            )}

            {/* Submit Button */}
            <TouchableOpacity
              onPress={handleSubmit}
              disabled={loading || !termsAccepted}
              activeOpacity={0.8}
              style={[
                styles.submitButton,
                (loading || !termsAccepted) && styles.submitButtonDisabled
              ]}
            >
              <Text style={[
                styles.submitButtonText,
                (loading || !termsAccepted) && styles.submitButtonTextDisabled
              ]}>
                {loading ? 'CREANDO OPERACIÓN...' : 'CREAR OPERACIÓN'}
              </Text>
            </TouchableOpacity>
          </Card.Content>
        </Card>
      </KeyboardAwareScrollView>

      {/* Add Bank Account Dialog */}
      <Portal>
        <Dialog
          visible={addAccountDialogVisible}
          onDismiss={() => setAddAccountDialogVisible(false)}
          style={styles.dialog}
        >
          <Dialog.Title style={styles.dialogTitle}>Agregar Cuenta Bancaria</Dialog.Title>
          <Dialog.ScrollArea>
            <ScrollView contentContainerStyle={styles.dialogContent}>
              {/* Origen */}
              <Text variant="titleSmall" style={styles.dialogLabel}>
                Origen
              </Text>
              <View style={styles.dialogSegmentedContainer}>
                <TouchableOpacity
                  style={[
                    styles.dialogSegmentedButton,
                    styles.dialogSegmentedButtonLeft,
                    newAccountOrigen === 'Lima' && styles.dialogSegmentedButtonActive,
                  ]}
                  onPress={() => setNewAccountOrigen('Lima')}
                  activeOpacity={0.8}
                >
                  <Text
                    style={[
                      styles.dialogSegmentedButtonText,
                      newAccountOrigen === 'Lima' && styles.dialogSegmentedButtonTextActive,
                    ]}
                  >
                    Lima
                  </Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[
                    styles.dialogSegmentedButton,
                    styles.dialogSegmentedButtonRight,
                    newAccountOrigen === 'Provincia' && styles.dialogSegmentedButtonActive,
                  ]}
                  onPress={() => setNewAccountOrigen('Provincia')}
                  activeOpacity={0.8}
                >
                  <Text
                    style={[
                      styles.dialogSegmentedButtonText,
                      newAccountOrigen === 'Provincia' && styles.dialogSegmentedButtonTextActive,
                    ]}
                  >
                    Provincia
                  </Text>
                </TouchableOpacity>
              </View>

              {/* Warning para Provincia */}
              {newAccountOrigen === 'Provincia' && (
                <Card style={styles.provinceWarningCard}>
                  <Card.Content style={styles.provinceWarningContent}>
                    <Text style={styles.provinceWarningText}>
                      Por el momento para cuentas de provincia solo operamos con BCP e INTERBANK
                    </Text>
                  </Card.Content>
                </Card>
              )}

              {/* Bank Selection */}
              <Text variant="titleSmall" style={styles.dialogLabel}>
                Banco
              </Text>
              <TouchableOpacity
                onPress={() => setBankMenuVisible(true)}
                style={styles.bankSelectButton}
                activeOpacity={0.8}
              >
                <Text style={styles.bankSelectButtonText}>
                  {newAccountBank || 'Seleccionar Banco'}
                </Text>
                <IconButton icon="chevron-down" size={20} />
              </TouchableOpacity>

              {/* Custom Bank Name (only when "Otros" is selected) */}
              {newAccountBank === 'Otros' && (
                <TextInput
                  label="Nombre del Banco"
                  value={newAccountBankCustomName}
                  onChangeText={setNewAccountBankCustomName}
                  mode="outlined"
                  placeholder="Ej: Banco de la Nación, Banco Ripley, etc."
                  style={styles.dialogInput}
                  outlineColor="#E0E0E0"
                  activeOutlineColor="#82C16C"
                />
              )}

              {/* Account Type */}
              <Text variant="titleSmall" style={styles.dialogLabel}>
                Tipo de Cuenta
              </Text>
              <View style={styles.dialogSegmentedContainer}>
                <TouchableOpacity
                  style={[
                    styles.dialogSegmentedButton,
                    styles.dialogSegmentedButtonLeft,
                    newAccountType === 'Ahorro' && styles.dialogSegmentedButtonActive,
                  ]}
                  onPress={() => setNewAccountType('Ahorro')}
                  activeOpacity={0.8}
                >
                  <Text
                    style={[
                      styles.dialogSegmentedButtonText,
                      newAccountType === 'Ahorro' && styles.dialogSegmentedButtonTextActive,
                    ]}
                  >
                    Ahorro
                  </Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[
                    styles.dialogSegmentedButton,
                    styles.dialogSegmentedButtonRight,
                    newAccountType === 'Corriente' && styles.dialogSegmentedButtonActive,
                  ]}
                  onPress={() => setNewAccountType('Corriente')}
                  activeOpacity={0.8}
                >
                  <Text
                    style={[
                      styles.dialogSegmentedButtonText,
                      newAccountType === 'Corriente' && styles.dialogSegmentedButtonTextActive,
                    ]}
                  >
                    Corriente
                  </Text>
                </TouchableOpacity>
              </View>

              {/* Account Number (only for main banks) */}
              {!needsCCI() && newAccountBank && (
                <TextInput
                  label="Número de Cuenta"
                  value={newAccountNumber}
                  onChangeText={setNewAccountNumber}
                  mode="outlined"
                  keyboardType="numeric"
                  style={styles.dialogInput}
                  outlineColor="#E0E0E0"
                  activeOutlineColor="#82C16C"
                />
              )}

              {/* CCI (only for non-main banks) */}
              {needsCCI() && (
                <>
                  <TextInput
                    label="CCI (20 dígitos)"
                    value={newAccountCCI}
                    onChangeText={setNewAccountCCI}
                    mode="outlined"
                    keyboardType="numeric"
                    maxLength={20}
                    style={styles.dialogInput}
                    outlineColor="#E0E0E0"
                    activeOutlineColor="#82C16C"
                  />
                  <HelperText type="info" visible={true} style={styles.helperText}>
                    Ingrese el CCI completo de 20 dígitos
                  </HelperText>
                </>
              )}

              {/* Currency Info */}
              <Card style={styles.currencyInfoCard}>
                <Card.Content style={styles.currencyInfoContent}>
                  <Text style={styles.currencyInfoLabel}>Moneda: </Text>
                  <Text style={styles.currencyInfoValue}>
                    {(operationType === 'Compra' && addAccountType === 'source') ||
                    (operationType === 'Venta' && addAccountType === 'destination')
                      ? 'Dólares ($)'
                      : 'Soles (S/)'}
                  </Text>
                </Card.Content>
              </Card>
            </ScrollView>
          </Dialog.ScrollArea>
          <Dialog.Actions style={styles.dialogActions}>
            <TouchableOpacity
              onPress={() => setAddAccountDialogVisible(false)}
              disabled={addingAccount}
              style={styles.dialogCancelButton}
              activeOpacity={0.8}
            >
              <Text style={styles.dialogCancelButtonText}>Cancelar</Text>
            </TouchableOpacity>
            <TouchableOpacity
              onPress={handleAddBankAccount}
              disabled={addingAccount || !newAccountBank}
              style={[
                styles.dialogAddButton,
                (addingAccount || !newAccountBank) && styles.dialogAddButtonDisabled,
              ]}
              activeOpacity={0.8}
            >
              <Text
                style={[
                  styles.dialogAddButtonText,
                  (addingAccount || !newAccountBank) && styles.dialogAddButtonTextDisabled,
                ]}
              >
                {addingAccount ? 'Agregando...' : 'Agregar Cuenta'}
              </Text>
            </TouchableOpacity>
          </Dialog.Actions>
        </Dialog>
      </Portal>

      {/* Bank Selection Dialog */}
      <Portal>
        <Dialog
          visible={bankMenuVisible}
          onDismiss={() => setBankMenuVisible(false)}
          style={styles.dialog}
        >
          <Dialog.Title style={styles.dialogTitle}>Seleccionar Banco</Dialog.Title>
          <Dialog.Content>
            <RadioButton.Group
              onValueChange={(value) => {
                setNewAccountBank(value);
                setNewAccountBankCustomName('');
                setBankMenuVisible(false);
              }}
              value={newAccountBank}
            >
              {getAvailableBanks().map((bank) => (
                <RadioButton.Item
                  key={bank}
                  label={bank}
                  value={bank}
                  style={styles.bankRadioItem}
                  labelStyle={styles.bankRadioLabel}
                  color="#82C16C"
                />
              ))}
            </RadioButton.Group>
          </Dialog.Content>
          <Dialog.Actions style={styles.dialogActions}>
            <TouchableOpacity
              onPress={() => setBankMenuVisible(false)}
              style={styles.dialogCancelButton}
              activeOpacity={0.8}
            >
              <Text style={styles.dialogCancelButtonText}>Cerrar</Text>
            </TouchableOpacity>
          </Dialog.Actions>
        </Dialog>
      </Portal>

      {/* Source Account Selection Dialog */}
      <Portal>
        <Dialog
          visible={sourceAccountDialogVisible}
          onDismiss={() => setSourceAccountDialogVisible(false)}
          style={styles.dialog}
        >
          <Dialog.Title style={styles.dialogTitle}>
            Elige tu cuenta de cargo ({operationType === 'Venta' ? 'S/' : 'USD'})
          </Dialog.Title>
          <Dialog.Content>
            <RadioButton.Group
              onValueChange={(value) => {
                setSourceAccount(value);
                setErrors({ ...errors, sourceAccount: '' });
                setSourceAccountDialogVisible(false);
              }}
              value={sourceAccount}
            >
              {(operationType === 'Venta' ? accountsPEN : accountsUSD).map((account, index) => (
                <RadioButton.Item
                  key={index}
                  label={renderAccountOption(account)}
                  value={account.account_number}
                  style={styles.bankRadioItem}
                  labelStyle={styles.bankRadioLabel}
                  color="#82C16C"
                />
              ))}
            </RadioButton.Group>
          </Dialog.Content>
          <Dialog.Actions style={styles.dialogActions}>
            <TouchableOpacity
              onPress={() => setSourceAccountDialogVisible(false)}
              style={styles.dialogCancelButton}
              activeOpacity={0.8}
            >
              <Text style={styles.dialogCancelButtonText}>Cerrar</Text>
            </TouchableOpacity>
          </Dialog.Actions>
        </Dialog>
      </Portal>

      {/* Destination Account Selection Dialog */}
      <Portal>
        <Dialog
          visible={destinationAccountDialogVisible}
          onDismiss={() => setDestinationAccountDialogVisible(false)}
          style={styles.dialog}
        >
          <Dialog.Title style={styles.dialogTitle}>
            Elige tu cuenta de destino ({operationType === 'Venta' ? 'USD' : 'S/'})
          </Dialog.Title>
          <Dialog.Content>
            <RadioButton.Group
              onValueChange={(value) => {
                setDestinationAccount(value);
                setErrors({ ...errors, destinationAccount: '' });
                setDestinationAccountDialogVisible(false);
              }}
              value={destinationAccount}
            >
              {(operationType === 'Venta' ? accountsUSD : accountsPEN).map((account, index) => (
                <RadioButton.Item
                  key={index}
                  label={renderAccountOption(account)}
                  value={account.account_number}
                  style={styles.bankRadioItem}
                  labelStyle={styles.bankRadioLabel}
                  color="#82C16C"
                />
              ))}
            </RadioButton.Group>
          </Dialog.Content>
          <Dialog.Actions style={styles.dialogActions}>
            <TouchableOpacity
              onPress={() => setDestinationAccountDialogVisible(false)}
              style={styles.dialogCancelButton}
              activeOpacity={0.8}
            >
              <Text style={styles.dialogCancelButtonText}>Cerrar</Text>
            </TouchableOpacity>
          </Dialog.Actions>
        </Dialog>
      </Portal>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  scrollContent: {
    padding: 16,
  },
  card: {
    elevation: 2,
    backgroundColor: Colors.surface,
  },

  // Timeline Stepper Styles
  timelineContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 20,
    paddingHorizontal: 16,
    marginBottom: 12,
  },
  timelineStep: {
    alignItems: 'center',
    flex: 1,
  },
  timelineDot: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#E0E0E0',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 8,
  },
  timelineDotActive: {
    backgroundColor: '#82C16C',
  },
  timelineDotText: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#757575',
  },
  timelineDotTextActive: {
    color: '#FFFFFF',
  },
  timelineLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: '#757575',
    textAlign: 'center',
  },
  timelineLabelActive: {
    color: '#82C16C',
    fontWeight: 'bold',
  },
  timelineLine: {
    height: 2,
    backgroundColor: '#E0E0E0',
    flex: 0.5,
    marginBottom: 24,
  },

  // Operation Type Selector Styles
  operationTypeSelector: {
    flexDirection: 'row',
    marginBottom: 16,
    marginHorizontal: 8,
    borderRadius: 12,
    overflow: 'hidden',
    backgroundColor: '#F0F0F0',
  },
  operationTypeButton: {
    flex: 1,
    paddingVertical: 14,
    paddingHorizontal: 16,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#F0F0F0',
  },
  operationTypeButtonLeft: {
    borderTopLeftRadius: 12,
    borderBottomLeftRadius: 12,
  },
  operationTypeButtonRight: {
    borderTopRightRadius: 12,
    borderBottomRightRadius: 12,
  },
  operationTypeButtonActive: {
    backgroundColor: '#82C16C',
  },
  operationTypeButtonText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#757575',
  },
  operationTypeButtonTextActive: {
    color: '#FFFFFF',
  },

  // Summary Card Styles (Non-editable)
  summaryCard: {
    backgroundColor: Colors.surface,
    elevation: 2,
    marginBottom: 8,
  },
  summaryRow: {
    flexDirection: 'row',
    marginBottom: 12,
  },
  summaryBox: {
    flex: 1,
    backgroundColor: '#E8E8E8',
    borderRadius: 12,
    padding: 12,
    marginRight: 8,
  },
  summaryLabel: {
    fontSize: 11,
    color: Colors.textDark,
    marginBottom: 4,
  },
  summaryAmount: {
    fontSize: 22,
    fontWeight: 'bold',
    color: Colors.textDark,
  },
  summaryCurrencyBox: {
    width: 80,
    backgroundColor: '#0D1B2A',
    borderRadius: 12,
    padding: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  summaryCurrencyText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#FFFFFF',
    textAlign: 'center',
  },
  exchangeRateRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 4,
    marginBottom: 12,
  },
  exchangeRateLabel: {
    fontSize: 11,
    color: Colors.textDark,
    fontWeight: '500',
  },
  exchangeRateValue: {
    fontSize: 11,
    color: Colors.textDark,
    fontWeight: 'bold',
  },

  // Account Section Styles
  accountSection: {
    marginBottom: 8,
  },
  accountHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  accountTitle: {
    fontWeight: '600',
    color: Colors.textDark,
  },
  addAccountButton: {
    backgroundColor: '#82C16C',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
  },
  addAccountButtonText: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: '600',
  },
  accountsCard: {
    backgroundColor: '#F9F9F9',
    elevation: 1,
  },
  accountRadioItem: {
    paddingVertical: 8,
    paddingHorizontal: 8,
  },
  accountRadioLabel: {
    fontSize: 13,
  },
  accountSelectButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#F0F0F0',
    borderRadius: 12,
    paddingLeft: 16,
    paddingRight: 4,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: '#E0E0E0',
    minHeight: 56,
  },
  accountSelectButtonText: {
    flex: 1,
    fontSize: 13,
    color: Colors.textDark,
    paddingVertical: 12,
  },
  accountSelectButtonPlaceholder: {
    color: '#999999',
  },

  divider: {
    marginVertical: 16,
    backgroundColor: Colors.divider,
  },

  // Checkbox Styles
  checkboxContainer: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginVertical: 16,
    paddingHorizontal: 8,
  },
  customCheckbox: {
    width: 20,
    height: 20,
    borderRadius: 10,
    borderWidth: 2,
    borderColor: '#D0D0D0',
    backgroundColor: '#FFFFFF',
    marginTop: 2,
  },
  customCheckboxChecked: {
    backgroundColor: '#82C16C',
    borderColor: '#82C16C',
  },
  checkboxLabel: {
    flex: 1,
    fontSize: 13,
    lineHeight: 20,
    color: Colors.textDark,
    marginLeft: 12,
    marginTop: 2,
  },
  checkboxError: {
    marginTop: -8,
    marginLeft: 8,
  },

  // Submit Button Styles
  submitButton: {
    backgroundColor: '#82C16C',
    borderRadius: 12,
    paddingVertical: 16,
    marginTop: 20,
    alignItems: 'center',
    justifyContent: 'center',
    elevation: 4,
    shadowColor: '#82C16C',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
  },
  submitButtonDisabled: {
    backgroundColor: Colors.border,
    shadowColor: Colors.border,
  },
  submitButtonText: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#FFFFFF',
    letterSpacing: 1,
  },
  submitButtonTextDisabled: {
    color: Colors.textMuted,
  },

  // Dialog Styles
  dialog: {
    maxHeight: '80%',
    backgroundColor: Colors.surface,
    borderRadius: 16,
  },
  dialogTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: Colors.textDark,
    textAlign: 'center',
  },
  dialogContent: {
    paddingHorizontal: 24,
    paddingBottom: 16,
  },
  dialogLabel: {
    marginTop: 16,
    marginBottom: 8,
    fontWeight: '600',
    color: Colors.textDark,
    fontSize: 14,
  },
  dialogInput: {
    marginTop: 8,
    marginBottom: 12,
    backgroundColor: Colors.surface,
  },

  // Custom Segmented Buttons for Dialog
  dialogSegmentedContainer: {
    flexDirection: 'row',
    marginBottom: 16,
    borderRadius: 12,
    overflow: 'hidden',
    backgroundColor: '#F0F0F0',
  },
  dialogSegmentedButton: {
    flex: 1,
    paddingVertical: 12,
    paddingHorizontal: 16,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#F0F0F0',
  },
  dialogSegmentedButtonLeft: {
    borderTopLeftRadius: 12,
    borderBottomLeftRadius: 12,
  },
  dialogSegmentedButtonRight: {
    borderTopRightRadius: 12,
    borderBottomRightRadius: 12,
  },
  dialogSegmentedButtonActive: {
    backgroundColor: '#82C16C',
  },
  dialogSegmentedButtonText: {
    fontSize: 14,
    fontWeight: '600',
    color: Colors.textMuted,
  },
  dialogSegmentedButtonTextActive: {
    color: '#FFFFFF',
  },

  // Province Warning
  provinceWarningCard: {
    backgroundColor: '#FFF3E0',
    marginBottom: 16,
    elevation: 0,
    borderWidth: 1,
    borderColor: '#FFB74D',
  },
  provinceWarningContent: {
    padding: 8,
  },
  provinceWarningText: {
    fontSize: 12,
    color: '#E65100',
    lineHeight: 18,
  },

  // Bank Selection Button
  bankSelectButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#F0F0F0',
    borderRadius: 12,
    paddingLeft: 16,
    paddingRight: 4,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#E0E0E0',
  },
  bankSelectButtonText: {
    fontSize: 14,
    color: Colors.textDark,
    paddingVertical: 12,
  },

  // Bank Radio Items
  bankRadioItem: {
    paddingVertical: 8,
    paddingHorizontal: 8,
  },
  bankRadioLabel: {
    fontSize: 14,
  },

  // Currency Info Card
  currencyInfoCard: {
    backgroundColor: '#E3F2FD',
    marginTop: 16,
    elevation: 0,
    borderWidth: 1,
    borderColor: '#90CAF9',
  },
  currencyInfoContent: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
  },
  currencyInfoLabel: {
    fontSize: 13,
    color: '#1976D2',
    fontWeight: '500',
  },
  currencyInfoValue: {
    fontSize: 13,
    color: '#1976D2',
    fontWeight: 'bold',
  },

  // Helper Text
  helperText: {
    marginTop: -8,
    marginBottom: 8,
  },

  // Dialog Actions
  dialogActions: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    gap: 12,
  },
  dialogCancelButton: {
    flex: 1,
    paddingVertical: 12,
    paddingHorizontal: 20,
    borderRadius: 8,
    backgroundColor: '#F0F0F0',
    alignItems: 'center',
    justifyContent: 'center',
  },
  dialogCancelButtonText: {
    fontSize: 14,
    fontWeight: '600',
    color: Colors.textDark,
  },
  dialogAddButton: {
    flex: 1,
    paddingVertical: 12,
    paddingHorizontal: 20,
    borderRadius: 8,
    backgroundColor: '#82C16C',
    alignItems: 'center',
    justifyContent: 'center',
  },
  dialogAddButtonDisabled: {
    backgroundColor: Colors.border,
  },
  dialogAddButtonText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  dialogAddButtonTextDisabled: {
    color: Colors.textMuted,
  },

  segmented: {
    marginBottom: 16,
  },
  radioItem: {
    paddingVertical: 4,
  },
});
