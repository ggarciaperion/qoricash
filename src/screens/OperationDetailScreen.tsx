import React, { useState, useEffect } from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  RefreshControl,
  Linking,
  Alert,
  Modal,
  Image,
  KeyboardAvoidingView,
  Platform,
  TouchableOpacity,
  SafeAreaView,
} from 'react-native';
import {
  Text,
  Card,
  Chip,
  Divider,
  Button,
  List,
  IconButton,
  ActivityIndicator,
  TextInput,
  HelperText,
} from 'react-native-paper';
import { operationsApi } from '../api/operations';
import { Operation } from '../types';
import {
  formatCurrency,
  formatDateTime,
  formatExchangeRate,
  formatBankAccount,
} from '../utils/formatters';
import { STATUS_COLORS, STATUS_ICONS } from '../constants/config';
import * as ImagePicker from 'expo-image-picker';
import { GlobalStyles } from '../styles/globalStyles';
import { CustomModal } from '../components/CustomModal';
import { KeyboardAwareScrollView } from '../components/KeyboardAwareScrollView';

interface DepositForm {
  imageUri: string;
  importe: string;
  codigoOperacion: string;
}

interface OperationDetailScreenProps {
  route: any;
  navigation: any;
}

export const OperationDetailScreen: React.FC<OperationDetailScreenProps> = ({
  route,
  navigation,
}) => {
  const { operationId } = route.params;
  const [operation, setOperation] = useState<Operation | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [uploading, setUploading] = useState(false);

  // Modal states
  const [modalVisible, setModalVisible] = useState(false);
  const [deposits, setDeposits] = useState<DepositForm[]>([]);
  const [currentDeposit, setCurrentDeposit] = useState<DepositForm>({
    imageUri: '',
    importe: '',
    codigoOperacion: '',
  });
  const [errors, setErrors] = useState<any>({});

  const isOperationExpired = (createdAt: string): boolean => {
    if (!createdAt) return false;
    const created = new Date(createdAt);
    const now = new Date();
    const elapsed = Math.floor((now.getTime() - created.getTime()) / 1000); // segundos
    const timeLimit = 30 * 60; // 30 minutos en segundos
    return elapsed >= timeLimit;
  };

  const getDisplayStatus = (op: Operation): string => {
    if (!op) return 'N/A';
    if (op.status === 'pendiente' && isOperationExpired(op.created_at || '')) {
      return 'Expirado';
    }
    return op.status || 'N/A';
  };

  const getSourceAccountCurrency = (op: Operation): string => {
    // Venta: QoriCash vende USD al cliente → Cliente paga S/, recibe $
    // Compra: QoriCash compra USD del cliente → Cliente paga $, recibe S/
    return op?.operation_type === 'Venta' ? 'S/' : '$';
  };

  const getDestinationAccountCurrency = (op: Operation): string => {
    return op?.operation_type === 'Venta' ? '$' : 'S/';
  };

  useEffect(() => {
    loadOperation();
  }, [operationId]);

  const loadOperation = async () => {
    try {
      setLoading(true);
      const data = await operationsApi.getOperationById(operationId);
      setOperation(data);
    } catch (error: any) {
      Alert.alert('Error', error.message || 'Error al cargar operación');
      navigation.goBack();
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await loadOperation();
    setRefreshing(false);
  };

  const handleOpenModal = () => {
    setModalVisible(true);
    setDeposits([]);
    setCurrentDeposit({
      imageUri: '',
      importe: '',
      codigoOperacion: '',
    });
    setErrors({});
  };

  const handleSelectImage = async () => {
    try {
      const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Permiso Denegado', 'Se necesita permiso para acceder a la galería');
        return;
      }

      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ['images'],
        allowsEditing: true,
        aspect: [4, 3],
        quality: 0.8,
      });

      if (!result.canceled && result.assets[0]) {
        setCurrentDeposit({ ...currentDeposit, imageUri: result.assets[0].uri });
        setErrors({ ...errors, imageUri: '' });
      }
    } catch (error: any) {
      Alert.alert('Error', error.message || 'Error al seleccionar imagen');
    }
  };

  const validateDeposit = (): boolean => {
    const newErrors: any = {};

    if (!currentDeposit.imageUri) {
      newErrors.imageUri = 'Seleccione una imagen';
    }

    if (!currentDeposit.importe || parseFloat(currentDeposit.importe) <= 0) {
      newErrors.importe = 'Ingrese un importe válido';
    }

    if (!currentDeposit.codigoOperacion.trim()) {
      newErrors.codigoOperacion = 'Ingrese el código de operación';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleAddDeposit = () => {
    if (!validateDeposit()) return;

    setDeposits([...deposits, currentDeposit]);
    setCurrentDeposit({
      imageUri: '',
      importe: '',
      codigoOperacion: '',
    });
    setErrors({});
  };

  const handleRemoveDeposit = (index: number) => {
    setDeposits(deposits.filter((_, i) => i !== index));
  };

  const getTotalDeposits = (): number => {
    return deposits.reduce((sum, dep) => sum + parseFloat(dep.importe || '0'), 0);
  };

  const getOperationTotal = (): number => {
    if (!operation) return 0;
    // Para "Compra": el cliente paga $ (amount_usd)
    // Para "Venta": el cliente paga S/ (amount_pen)
    return operation.operation_type === 'Venta'
      ? operation.amount_pen || 0
      : operation.amount_usd || 0;
  };

  const handleSubmitDeposits = async () => {
    if (deposits.length === 0) {
      Alert.alert('Error', 'Debe agregar al menos un comprobante');
      return;
    }

    const total = getTotalDeposits();
    const operationTotal = getOperationTotal();

    if (Math.abs(total - operationTotal) > 0.01) {
      Alert.alert(
        'Error de Validación',
        `La suma de los importes (${formatCurrency(total, operation?.operation_type === 'Venta' ? 'PEN' : 'USD')}) debe coincidir con el monto de la operación (${formatCurrency(operationTotal, operation?.operation_type === 'Venta' ? 'PEN' : 'USD')})`
      );
      return;
    }

    try {
      setUploading(true);

      for (let i = 0; i < deposits.length; i++) {
        const deposit = deposits[i];
        const depositIndex = (operation?.client_deposits?.length || 0) + i;

        console.log(`📤 [UPLOAD] Subiendo deposit ${i + 1}/${deposits.length}:`, {
          depositIndex,
          importe: deposit.importe,
          codigo: deposit.codigoOperacion,
          hasImage: !!deposit.imageUri,
        });

        const formData = new FormData();

        // Agregar primero los datos del formulario
        formData.append('deposit_index', depositIndex.toString());
        formData.append('importe', deposit.importe.toString());
        formData.append('codigo_operacion', deposit.codigoOperacion.toString());

        console.log(`📤 [UPLOAD] FormData construido:`, {
          deposit_index: depositIndex,
          importe: deposit.importe,
          codigo_operacion: deposit.codigoOperacion,
        });

        // Luego agregar el archivo
        formData.append('file', {
          uri: deposit.imageUri,
          type: 'image/jpeg',
          name: `comprobante_${depositIndex}.jpg`,
        } as any);

        console.log(`📤 [UPLOAD] Enviando a API...`);
        await operationsApi.uploadDepositProof(operationId, depositIndex, formData);
        console.log(`✅ [UPLOAD] Deposit ${i + 1} subido exitosamente`);
      }

      console.log(`✅ [UPLOAD] Todos los comprobantes subidos exitosamente`);

      Alert.alert('Éxito', 'Comprobantes subidos exitosamente', [
        {
          text: 'OK',
          onPress: () => {
            setModalVisible(false);
            setDeposits([]);
            // Redirigir al Home (HomeTab dentro de Tabs)
            navigation.navigate('Tabs', { screen: 'HomeTab' });
          },
        },
      ]);
    } catch (error: any) {
      Alert.alert('Error', error.message || 'Error al subir comprobantes');
    } finally {
      setUploading(false);
    }
  };

  const openPDF = (url: string) => {
    Linking.openURL(url).catch(() => {
      Alert.alert('Error', 'No se pudo abrir el enlace');
    });
  };

  const getStatusColor = (status: string) => {
    if (status === 'Expirado') {
      return '#D32F2F'; // Rojo para expirado
    }
    return STATUS_COLORS[status as keyof typeof STATUS_COLORS] || '#757575';
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#1976D2" />
      </View>
    );
  }

  if (!operation) {
    return (
      <View style={styles.errorContainer}>
        <Text>Operación no encontrada</Text>
      </View>
    );
  }

  const inputCurrency = operation?.operation_type === 'Compra' ? 'USD' : 'PEN';
  const outputCurrency = operation?.operation_type === 'Compra' ? 'PEN' : 'USD';

  return (
    <SafeAreaView style={{ flex: 1, paddingTop: 20 }}>
      <ScrollView
        style={styles.container}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      >
      {/* Unified Operation Details Card */}
      <Card style={styles.unifiedCard}>
        <Card.Content>
          {/* Operation ID and Status */}
          <View style={styles.unifiedHeader}>
            <View style={styles.headerLeft}>
              <Text variant="bodySmall" style={styles.idLabel}>
                ID de Operación
              </Text>
              <Text variant="titleLarge" style={styles.operationIdText}>
                {operation?.operation_id || 'N/A'}
              </Text>
              <Text variant="bodySmall" style={styles.dateText}>
                {operation?.created_at ? formatDateTime(operation.created_at) : 'N/A'}
              </Text>
            </View>
            <View style={styles.headerRight}>
              <View
                style={[
                  styles.statusBadge,
                  { backgroundColor: getStatusColor(getDisplayStatus(operation)) },
                ]}
              >
                <Text style={styles.statusBadgeText}>{getDisplayStatus(operation)}</Text>
              </View>
            </View>
          </View>

          <Divider style={styles.unifiedDivider} />

          {/* Operation Type */}
          <View style={styles.operationTypeRow}>
            <View style={styles.operationTypeBadge}>
              <Text style={styles.operationTypeText}>
                {operation?.operation_type || 'N/A'}
              </Text>
            </View>
          </View>

          {/* Unified Amounts Card */}
          <Card style={styles.amountsInnerCard}>
            <Card.Content style={styles.amountsInnerContent}>
              {/* Amount Sending */}
              <View style={styles.compactRow}>
                <View style={styles.compactBox}>
                  <Text style={styles.compactLabel}>
                    {operation?.operation_type === 'Compra' ? 'Enviando' : 'Pagando'}
                  </Text>
                  <Text style={styles.compactAmount}>
                    {operation?.operation_type === 'Compra'
                      ? formatCurrency(operation?.amount_usd || 0, 'USD')
                      : formatCurrency(operation?.amount_pen || 0, 'PEN')}
                  </Text>
                </View>
                <View style={styles.compactCurrencyBox}>
                  <Text style={styles.compactCurrencyText}>
                    {inputCurrency === 'USD' ? 'Dólares' : 'Soles'}
                  </Text>
                </View>
              </View>

              {/* Exchange Rate - Centered */}
              <View style={styles.centerExchangeRow}>
                <Text style={styles.centerExchangeLabel}>Tipo de cambio</Text>
                <Text style={styles.centerExchangeValue}>
                  {formatExchangeRate(operation?.exchange_rate || 0)}
                </Text>
              </View>

              {/* Amount Receiving */}
              <View style={styles.compactRow}>
                <View style={styles.compactBox}>
                  <Text style={styles.compactLabel}>Recibiendo</Text>
                  <Text style={styles.compactAmount}>
                    {operation?.operation_type === 'Compra'
                      ? formatCurrency(operation?.amount_pen || 0, 'PEN')
                      : formatCurrency(operation?.amount_usd || 0, 'USD')}
                  </Text>
                </View>
                <View style={styles.compactCurrencyBox}>
                  <Text style={styles.compactCurrencyText}>
                    {outputCurrency === 'USD' ? 'Dólares' : 'Soles'}
                  </Text>
                </View>
              </View>
            </Card.Content>
          </Card>
        </Card.Content>
      </Card>

      {/* Bank Accounts Card */}
      <Card style={GlobalStyles.card}>
        <Card.Content>
          <Text variant="titleMedium" style={styles.cardTitle}>
            Cuentas Bancarias
          </Text>
          {operation?.source_account && (
            <List.Item
              title={`Cuenta Origen (${getSourceAccountCurrency(operation)})`}
              description={`${operation?.source_bank_name || ''}\n${formatBankAccount(operation.source_account)}`}
              left={(props) => <List.Icon {...props} icon="bank" />}
            />
          )}
          {operation?.destination_account && (
            <List.Item
              title={`Cuenta Destino (${getDestinationAccountCurrency(operation)})`}
              description={`${operation?.destination_bank_name || ''}\n${formatBankAccount(operation.destination_account)}`}
              left={(props) => <List.Icon {...props} icon="bank-transfer" />}
            />
          )}
        </Card.Content>
      </Card>

      {/* Client Deposits */}
      {operation.client_deposits && Array.isArray(operation.client_deposits) && operation.client_deposits.length > 0 && (
        <Card style={GlobalStyles.card}>
          <Card.Content>
            <Text variant="titleMedium" style={styles.cardTitle}>
              Comprobantes del Cliente
            </Text>
            {operation.client_deposits.map((deposit, index) => (
              <List.Item
                key={index}
                title={`Abono ${index + 1}`}
                description={`${formatCurrency(deposit?.importe || 0, 'PEN')}\nCódigo: ${deposit?.codigo_operacion || 'N/A'}`}
                left={(props) => <List.Icon {...props} icon="file-document" />}
                right={(props) =>
                  deposit?.comprobante_url ? (
                    <IconButton
                      {...props}
                      icon="download"
                      onPress={() => openPDF(deposit.comprobante_url!)}
                    />
                  ) : null
                }
              />
            ))}
          </Card.Content>
        </Card>
      )}

      {/* Operator Proofs */}
      {operation.operator_proofs && Array.isArray(operation.operator_proofs) && operation.operator_proofs.length > 0 && (
        <Card style={GlobalStyles.card}>
          <Card.Content>
            <Text variant="titleMedium" style={styles.cardTitle}>
              Comprobantes del Operador
            </Text>
            {operation.operator_proofs.map((proof, index) => (
              <List.Item
                key={index}
                title={`Comprobante ${index + 1}`}
                description={proof?.comentario || 'Sin comentarios'}
                left={(props) => <List.Icon {...props} icon="check-circle" />}
                right={(props) =>
                  proof?.comprobante_url ? (
                    <IconButton
                      {...props}
                      icon="download"
                      onPress={() => openPDF(proof.comprobante_url)}
                    />
                  ) : null
                }
              />
            ))}
            {operation.operator_comments && (
              <>
                <Divider style={styles.divider} />
                <Text variant="bodyMedium" style={styles.commentsLabel}>
                  Comentarios:
                </Text>
                <Text variant="bodyMedium">{operation.operator_comments}</Text>
              </>
            )}
          </Card.Content>
        </Card>
      )}

      {/* Invoices */}
      {operation.invoices && Array.isArray(operation.invoices) && operation.invoices.length > 0 && (
        <Card style={GlobalStyles.card}>
          <Card.Content>
            <Text variant="titleMedium" style={styles.cardTitle}>
              Factura Electrónica
            </Text>
            {operation.invoices.map((invoice, index) => (
              <View key={index}>
                <List.Item
                  title={invoice?.invoice_number || 'N/A'}
                  description={`${invoice?.invoice_type || 'N/A'} - ${formatCurrency(invoice?.monto_total || 0, 'PEN')}`}
                  left={(props) => <List.Icon {...props} icon="file-pdf-box" />}
                />
                {invoice?.nubefact_enlace_pdf && (
                  <Button
                    mode="outlined"
                    icon="download"
                    onPress={() => openPDF(invoice.nubefact_enlace_pdf!)}
                    style={styles.downloadButton}
                  >
                    Descargar PDF
                  </Button>
                )}
              </View>
            ))}
          </Card.Content>
        </Card>
      )}

      {/* Notes */}
      {operation.notes && (
        <Card style={GlobalStyles.card}>
          <Card.Content>
            <Text variant="titleMedium" style={styles.cardTitle}>
              Notas
            </Text>
            <Text variant="bodyMedium">{operation.notes}</Text>
          </Card.Content>
        </Card>
      )}

      {/* Actions */}
      {operation?.status === 'pendiente' && (
        <View style={styles.actionsContainer}>
          {isOperationExpired(operation?.created_at || '') ? (
            <View style={styles.expiredNotice}>
              <Text variant="bodyMedium" style={styles.expiredText}>
                ⏱️ Esta operación ha expirado. No se pueden subir comprobantes después de 30 minutos.
              </Text>
            </View>
          ) : (
            <TouchableOpacity
              onPress={handleOpenModal}
              disabled={uploading}
              style={[styles.uploadButton, uploading && styles.uploadButtonDisabled]}
              activeOpacity={0.8}
            >
              <Text style={[styles.uploadButtonText, uploading && styles.uploadButtonTextDisabled]}>
                {uploading ? 'SUBIENDO...' : 'SUBIR COMPROBANTE'}
              </Text>
            </TouchableOpacity>
          )}
        </View>
      )}

      {/* Modal para agregar comprobantes */}
      <Modal
        visible={modalVisible}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setModalVisible(false)}
      >
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={styles.modalContainer}
        >
          <View style={styles.modalOverlay}>
            <View style={styles.modalContent}>
              <View style={styles.modalHeader}>
                <Text variant="headlineSmall" style={styles.modalTitle}>
                  Agregar Comprobantes
                </Text>
                <IconButton
                  icon="close"
                  size={24}
                  onPress={() => setModalVisible(false)}
                />
              </View>

              <ScrollView
                style={styles.scrollView}
                contentContainerStyle={styles.scrollContent}
                keyboardShouldPersistTaps="handled"
                showsVerticalScrollIndicator={true}
              >
                <View style={styles.dialogContent}>
                {/* Información de monto total */}
                <Card style={styles.infoCard}>
                  <Card.Content>
                    <Text variant="bodyMedium" style={styles.infoLabel}>
                      Monto Total de la Operación:
                    </Text>
                    <Text variant="titleLarge" style={styles.infoValue}>
                      {formatCurrency(
                        getOperationTotal(),
                        operation?.operation_type === 'Venta' ? 'PEN' : 'USD'
                      )}
                    </Text>
                    {deposits.length > 0 && (
                      <>
                        <Divider style={styles.divider} />
                        <Text variant="bodyMedium" style={styles.infoLabel}>
                          Total Ingresado:
                        </Text>
                        <Text
                          variant="titleMedium"
                          style={[
                            styles.infoValue,
                            {
                              color:
                                Math.abs(getTotalDeposits() - getOperationTotal()) < 0.01
                                  ? '#82C16C'
                                  : '#F57C00',
                            },
                          ]}
                        >
                          {formatCurrency(
                            getTotalDeposits(),
                            operation?.operation_type === 'Venta' ? 'PEN' : 'USD'
                          )}
                        </Text>
                        <Text variant="bodySmall" style={styles.infoLabel}>
                          Faltante:{' '}
                          {formatCurrency(
                            getOperationTotal() - getTotalDeposits(),
                            operation?.operation_type === 'Venta' ? 'PEN' : 'USD'
                          )}
                        </Text>
                      </>
                    )}
                  </Card.Content>
                </Card>

                {/* Lista de comprobantes agregados */}
                {deposits.length > 0 && (
                  <View style={styles.depositsList}>
                    <Text variant="titleMedium" style={styles.depositsTitle}>
                      Comprobantes Agregados ({deposits.length})
                    </Text>
                    {deposits.map((deposit, index) => (
                      <Card key={index} style={styles.depositCard}>
                        <Card.Content>
                          <View style={styles.depositRow}>
                            <Image source={{ uri: deposit.imageUri }} style={styles.thumbnail} />
                            <View style={styles.depositInfo}>
                              <Text variant="bodyMedium">
                                Importe:{' '}
                                {formatCurrency(
                                  parseFloat(deposit.importe),
                                  operation?.operation_type === 'Venta' ? 'PEN' : 'USD'
                                )}
                              </Text>
                              <Text variant="bodySmall">Código: {deposit.codigoOperacion}</Text>
                            </View>
                            <IconButton
                              icon="delete"
                              iconColor="#D32F2F"
                              size={20}
                              onPress={() => handleRemoveDeposit(index)}
                            />
                          </View>
                        </Card.Content>
                      </Card>
                    ))}
                  </View>
                )}

                {/* Formulario para nuevo comprobante */}
                <Divider style={styles.divider} />
                <Text variant="titleMedium" style={styles.sectionTitle}>
                  {deposits.length === 0 ? 'Agregar Comprobante' : 'Agregar Otro Comprobante'}
                </Text>

                {/* Seleccionar imagen */}
                <TouchableOpacity
                  onPress={handleSelectImage}
                  style={styles.selectImageButton}
                  activeOpacity={0.8}
                >
                  <Text style={styles.selectImageButtonText}>
                    {currentDeposit.imageUri ? 'Cambiar Imagen' : 'Seleccionar Imagen'}
                  </Text>
                </TouchableOpacity>
                {currentDeposit.imageUri && (
                  <Image source={{ uri: currentDeposit.imageUri }} style={styles.previewImage} />
                )}
                {errors.imageUri && (
                  <HelperText type="error" visible={!!errors.imageUri}>
                    {errors.imageUri}
                  </HelperText>
                )}

                {/* Importe */}
                <TextInput
                  label={`Importe (${operation?.operation_type === 'Venta' ? 'S/' : '$'})`}
                  value={currentDeposit.importe}
                  onChangeText={(text) => {
                    setCurrentDeposit({ ...currentDeposit, importe: text });
                    setErrors({ ...errors, importe: '' });
                  }}
                  keyboardType="decimal-pad"
                  mode="outlined"
                  style={styles.input}
                  error={!!errors.importe}
                />
                {errors.importe && (
                  <HelperText type="error" visible={!!errors.importe}>
                    {errors.importe}
                  </HelperText>
                )}

                {/* Código de operación */}
                <TextInput
                  label="Código de Operación"
                  value={currentDeposit.codigoOperacion}
                  onChangeText={(text) => {
                    setCurrentDeposit({ ...currentDeposit, codigoOperacion: text });
                    setErrors({ ...errors, codigoOperacion: '' });
                  }}
                  mode="outlined"
                  style={styles.input}
                  error={!!errors.codigoOperacion}
                />
                {errors.codigoOperacion && (
                  <HelperText type="error" visible={!!errors.codigoOperacion}>
                    {errors.codigoOperacion}
                  </HelperText>
                )}

                {/* Botón agregar a la lista */}
                <TouchableOpacity
                  onPress={handleAddDeposit}
                  style={styles.addToListButton}
                  activeOpacity={0.8}
                >
                  <Text style={styles.addToListButtonText}>Agregar a la Lista</Text>
                </TouchableOpacity>
              </View>
              </ScrollView>

              <View style={styles.modalActions}>
                <TouchableOpacity
                  onPress={() => setModalVisible(false)}
                  style={styles.modalCancelButton}
                  activeOpacity={0.8}
                >
                  <Text style={styles.modalCancelButtonText}>Cancelar</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  onPress={handleSubmitDeposits}
                  disabled={uploading || deposits.length === 0}
                  style={[
                    styles.modalSubmitButton,
                    (uploading || deposits.length === 0) && styles.modalSubmitButtonDisabled,
                  ]}
                  activeOpacity={0.8}
                >
                  <Text
                    style={[
                      styles.modalSubmitButtonText,
                      (uploading || deposits.length === 0) && styles.modalSubmitButtonTextDisabled,
                    ]}
                  >
                    {uploading ? 'Enviando...' : 'Enviar Comprobantes'}
                  </Text>
                </TouchableOpacity>
              </View>
            </View>
          </View>
        </KeyboardAvoidingView>
      </Modal>

      {/* Boton Aceptar */}
      <TouchableOpacity
        style={styles.acceptButton}
        onPress={() => navigation.goBack()}
        activeOpacity={0.8}
      >
        <Text style={styles.acceptButtonText}>ACEPTAR</Text>
      </TouchableOpacity>
    </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F5F5F5',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },

  // Unified Card Styles
  unifiedCard: {
    margin: 16,
    marginBottom: 12,
    elevation: 3,
    backgroundColor: '#FFFFFF',
  },
  unifiedHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  headerLeft: {
    flex: 1,
  },
  idLabel: {
    color: '#757575',
    fontSize: 12,
    marginBottom: 4,
  },
  operationIdText: {
    fontWeight: 'bold',
    color: '#0D1B2A',
    fontSize: 22,
    marginBottom: 4,
  },
  dateText: {
    color: '#757575',
    fontSize: 12,
  },
  headerRight: {
    marginLeft: 12,
  },
  statusBadge: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 16,
  },
  statusBadgeText: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: '600',
  },
  unifiedDivider: {
    marginVertical: 16,
    backgroundColor: '#E0E0E0',
  },
  operationTypeRow: {
    alignItems: 'center',
    marginBottom: 16,
  },
  operationTypeBadge: {
    backgroundColor: '#82C16C',
    paddingHorizontal: 24,
    paddingVertical: 10,
    borderRadius: 20,
  },
  operationTypeText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },

  // Unified Amounts Inner Card
  amountsInnerCard: {
    backgroundColor: '#F9F9F9',
    elevation: 0,
    marginTop: 0,
  },
  amountsInnerContent: {
    paddingVertical: 12,
    paddingHorizontal: 8,
  },
  compactRow: {
    flexDirection: 'row',
    marginBottom: 12,
  },
  compactBox: {
    flex: 1,
    backgroundColor: '#E8E8E8',
    borderRadius: 10,
    padding: 12,
    marginRight: 8,
  },
  compactLabel: {
    fontSize: 11,
    color: '#424242',
    marginBottom: 4,
  },
  compactAmount: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#0D1B2A',
  },
  compactCurrencyBox: {
    width: 80,
    backgroundColor: '#0D1B2A',
    borderRadius: 10,
    padding: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  compactCurrencyText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#FFFFFF',
    textAlign: 'center',
  },
  centerExchangeRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 12,
    marginBottom: 12,
    backgroundColor: '#FFFFFF',
    borderRadius: 8,
    gap: 8,
  },
  centerExchangeLabel: {
    fontSize: 13,
    color: '#424242',
    fontWeight: '500',
  },
  centerExchangeValue: {
    fontSize: 16,
    color: '#0D1B2A',
    fontWeight: 'bold',
  },
  card: {
    marginHorizontal: 16,
    marginVertical: 8,
    elevation: 2,
  },
  cardTitle: {
    fontWeight: '600',
    marginBottom: 12,
  },
  divider: {
    marginVertical: 12,
  },
  commentsLabel: {
    fontWeight: '600',
    marginBottom: 8,
  },
  downloadButton: {
    marginTop: 8,
    marginBottom: 8,
  },
  actionsContainer: {
    padding: 16,
  },
  uploadButton: {
    backgroundColor: '#82C16C',
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: 'center',
    justifyContent: 'center',
    elevation: 4,
    shadowColor: '#82C16C',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
  },
  uploadButtonDisabled: {
    backgroundColor: '#BDBDBD',
    shadowColor: '#BDBDBD',
  },
  uploadButtonText: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#FFFFFF',
    letterSpacing: 1,
  },
  uploadButtonTextDisabled: {
    color: '#757575',
  },
  expiredNotice: {
    backgroundColor: '#FFEBEE',
    padding: 16,
    borderRadius: 8,
    borderLeftWidth: 4,
    borderLeftColor: '#D32F2F',
  },
  expiredText: {
    color: '#C62828',
    textAlign: 'center',
  },
  // Modal styles
  modalContainer: {
    flex: 1,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: '#FFF',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    maxHeight: '90%',
    paddingBottom: Platform.OS === 'ios' ? 20 : 0,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingTop: 20,
    paddingBottom: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#E0E0E0',
  },
  modalTitle: {
    fontWeight: 'bold',
  },
  scrollView: {
    maxHeight: '70%',
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingBottom: 20,
  },
  dialogContent: {
    paddingVertical: 8,
  },
  modalActions: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 16,
    borderTopWidth: 1,
    borderTopColor: '#E0E0E0',
    gap: 12,
  },
  modalCancelButton: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 8,
    backgroundColor: '#F0F0F0',
    alignItems: 'center',
    justifyContent: 'center',
  },
  modalCancelButtonText: {
    fontSize: 15,
    fontWeight: '600',
    color: '#424242',
  },
  modalSubmitButton: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 8,
    backgroundColor: '#82C16C',
    alignItems: 'center',
    justifyContent: 'center',
  },
  modalSubmitButtonDisabled: {
    backgroundColor: '#BDBDBD',
  },
  modalSubmitButtonText: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  modalSubmitButtonTextDisabled: {
    color: '#757575',
  },
  infoCard: {
    backgroundColor: '#E3F2FD',
    marginBottom: 16,
  },
  infoLabel: {
    color: '#1976D2',
    marginBottom: 4,
  },
  infoValue: {
    color: '#1976D2',
    fontWeight: 'bold',
  },
  depositsList: {
    marginTop: 16,
  },
  depositsTitle: {
    fontWeight: '600',
    marginBottom: 8,
  },
  depositCard: {
    marginBottom: 8,
    elevation: 1,
  },
  depositRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  thumbnail: {
    width: 60,
    height: 60,
    borderRadius: 8,
    marginRight: 12,
  },
  depositInfo: {
    flex: 1,
  },
  sectionTitle: {
    fontWeight: '600',
    marginBottom: 12,
    marginTop: 8,
  },
  selectImageButton: {
    backgroundColor: '#F0F0F0',
    borderRadius: 8,
    paddingVertical: 14,
    marginBottom: 12,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: '#E0E0E0',
  },
  selectImageButtonText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#424242',
  },
  previewImage: {
    width: '100%',
    height: 200,
    borderRadius: 8,
    marginBottom: 12,
  },
  input: {
    marginBottom: 8,
  },
  addToListButton: {
    backgroundColor: '#82C16C',
    borderRadius: 8,
    paddingVertical: 14,
    marginTop: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  addToListButtonText: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  acceptButton: {
    backgroundColor: '#82C16C',
    borderRadius: 12,
    paddingVertical: 16,
    marginHorizontal: 16,
    marginTop: 20,
    marginBottom: 20,
    alignItems: 'center',
    justifyContent: 'center',
    elevation: 4,
    shadowColor: '#82C16C',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
  },
  acceptButtonText: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#FFFFFF',
    letterSpacing: 1,
  },
});
