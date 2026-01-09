import React, { useState, useEffect } from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Alert,
  Linking,
  ActivityIndicator,
} from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import {
  Text,
  Card,
  Divider,
  TextInput,
  Button,
  IconButton,
} from 'react-native-paper';
import AsyncStorage from '@react-native-async-storage/async-storage';
import axios from 'axios';
import { Operation } from '../types';
import { Colors } from '../constants/colors';
import { QORICASH_ACCOUNTS } from '../constants/config';
import { formatCurrency, formatDateTime } from '../utils/formatters';
import { operationsApi } from '../api/operations';
import { CustomModal } from '../components/CustomModal';
import { GlobalStyles } from '../styles/globalStyles';
import socketService from '../services/socketService';
import { logger } from '../utils/logger';

const LOCAL_OPERATIONS_CACHE_KEY = '@qoricash_local_operations_cache';
// Tiempo de expiración: 15 minutos
const OPERATION_TIMEOUT_MINUTES = 15;

interface TransferScreenProps {
  navigation: any;
  route: {
    params: {
      operation: Operation;
    };
  };
}

export const TransferScreen: React.FC<TransferScreenProps> = ({ navigation, route }) => {
  const { operation } = route.params;
  const [timeRemaining, setTimeRemaining] = useState('');
  const [isExpired, setIsExpired] = useState(false);
  const [uploadDialogVisible, setUploadDialogVisible] = useState(false);
  const [operationCode, setOperationCode] = useState('');
  const [selectedImages, setSelectedImages] = useState<string[]>([]);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    const timer = setInterval(() => {
      const createdDate = new Date(operation.created_at);
      const expirationDate = new Date(createdDate.getTime() + OPERATION_TIMEOUT_MINUTES * 60000);
      const now = new Date();
      const diffMs = expirationDate.getTime() - now.getTime();

      if (diffMs <= 0) {
        setTimeRemaining('0:00');

        // Marcar como expirada solo una vez
        if (!isExpired) {
          setIsExpired(true);
          clearInterval(timer);

          // Mostrar alerta y redirigir
          Alert.alert(
            '⏱️ Tiempo Expirado',
            `La operación ${operation.operation_id} ha sido cancelada porque se agotó el tiempo para subir el comprobante.\n\nPuedes crear una nueva operación desde el inicio.`,
            [
              {
                text: 'Entendido',
                onPress: async () => {
                  // Cancelar operación en backend inmediatamente
                  logger.info('TransferScreen', '⏱️ Timer expirado - Cancelando operación en backend');
                  try {
                    const response = await axios.post(
                      `${API_CONFIG.BASE_URL}/api/client/cancel-expired-operation/${operation.id}`,
                      {},
                      { timeout: 5000 }
                    );

                    if (response.data.success) {
                      logger.info('TransferScreen', '✅ Operación cancelada exitosamente en backend');
                    } else {
                      logger.warn('TransferScreen', `⚠️ Respuesta del backend: ${response.data.message}`);
                    }
                  } catch (error) {
                    logger.error('TransferScreen', '❌ Error cancelando operación en backend', error);
                  }

                  logger.info('TransferScreen', '🗑️ Limpiando caché local antes de redirigir');
                  try {
                    await AsyncStorage.removeItem(LOCAL_OPERATIONS_CACHE_KEY);
                    logger.info('TransferScreen', '✅ Caché limpiado exitosamente');
                  } catch (error) {
                    logger.error('TransferScreen', '❌ Error limpiando caché', error);
                  }
                  logger.info('TransferScreen', '🔄 Redirigiendo a HistoryTab por expiración local');
                  navigation.replace('Tabs', { screen: 'HistoryTab', params: { initialTab: 'completed' } });
                }
              }
            ],
            { cancelable: false }
          );
        }
        return;
      }

      const minutes = Math.floor(diffMs / 60000);
      const seconds = Math.floor((diffMs % 60000) / 1000);

      setTimeRemaining(`${minutes}:${seconds.toString().padStart(2, '0')}`);
    }, 1000);

    return () => clearInterval(timer);
  }, [operation.created_at, isExpired, navigation]);

  // Escuchar evento de operación expirada vía Socket.IO
  useEffect(() => {
    logger.info('TransferScreen', '🎬 Iniciando useEffect de operation_expired', {
      operation_id: operation.operation_id,
      operation_status: operation.status,
    });

    const handleOperationExpired = (data: any) => {
      logger.info('TransferScreen', '📡 Evento operation_expired recibido', data);

      if (data.operation_id === operation.operation_id) {
        logger.warn('TransferScreen', '⏱️ La operación actual ha expirado, mostrando alerta', {
          operation_id: operation.operation_id,
        });

        Alert.alert(
          '⏱️ Tiempo Expirado',
          `La operación ${data.operation_id} ha sido cancelada porque se agotó el tiempo para subir el comprobante.\n\nPuedes crear una nueva operación desde el inicio.`,
          [
            {
              text: 'Entendido',
              onPress: async () => {
                logger.info('TransferScreen', '🗑️ Limpiando caché local antes de redirigir');
                try {
                  await AsyncStorage.removeItem(LOCAL_OPERATIONS_CACHE_KEY);
                  logger.info('TransferScreen', '✅ Caché limpiado exitosamente');
                } catch (error) {
                  logger.error('TransferScreen', '❌ Error limpiando caché', error);
                }
                logger.info('TransferScreen', '🔄 Redirigiendo a HistoryTab');
                navigation.replace('Tabs', { screen: 'HistoryTab', params: { initialTab: 'completed' } });
              }
            }
          ],
          { cancelable: false }
        );
      } else {
        logger.debug('TransferScreen', '⏭️ Operación expirada no es la actual, ignorando', {
          received_operation_id: data.operation_id,
          current_operation_id: operation.operation_id,
        });
      }
    };

    // Verificar conexión Socket.IO
    const isConnected = socketService.isConnected();
    logger.info('TransferScreen', `📡 Estado Socket.IO: ${isConnected ? 'Conectado' : 'Desconectado'}`);

    if (!isConnected) {
      logger.warn('TransferScreen', '⚠️ Socket.IO no está conectado, los eventos pueden no llegar');
    }

    // Registrar listener
    logger.info('TransferScreen', '📝 Registrando listener para operation_expired');
    socketService.on('operation_expired', handleOperationExpired);

    // Cleanup al desmontar componente
    return () => {
      logger.info('TransferScreen', '🧹 Removiendo listener para operation_expired');
      socketService.off('operation_expired', handleOperationExpired);
    };
  }, [operation.operation_id, navigation]);

  const getQoriCashAccount = () => {
    // Determinar moneda según tipo de operación
    const currency = operation.operation_type === 'Compra' ? 'USD' : 'PEN';

    // Extraer banco de la cuenta del cliente
    const sourceBank = operation.source_bank_name?.toUpperCase() || '';

    // Mapeo de bancos
    const bankMapping: { [key: string]: keyof typeof QORICASH_ACCOUNTS.USD } = {
      'BCP': 'BCP',
      'BANCO DE CREDITO': 'BCP',
      'BANCO DE CREDITO DEL PERU': 'BCP',
      'INTERBANK': 'INTERBANK',
      'PICHINCHA': 'PICHINCHA',
      'BANCO PICHINCHA': 'PICHINCHA',
      'BANBIF': 'BANBIF',
      'BANCO BANBIF': 'BANBIF',
    };

    // Buscar si el banco del cliente está en nuestra lista de bancos preferidos
    let qoriBank: keyof typeof QORICASH_ACCOUNTS.USD | null = null;

    for (const [key, value] of Object.entries(bankMapping)) {
      if (sourceBank.includes(key)) {
        qoriBank = value;
        break;
      }
    }

    // Si el banco está en la lista, usar cuenta del mismo banco
    // Si no, usar CCI de Interbank
    const accounts = QORICASH_ACCOUNTS[currency as keyof typeof QORICASH_ACCOUNTS];

    if (qoriBank && accounts[qoriBank]) {
      return {
        ...accounts[qoriBank],
        use_cci: false,
      };
    } else {
      return {
        ...accounts.INTERBANK,
        use_cci: true,
      };
    }
  };

  const qoriAccount = getQoriCashAccount();

  const handlePickImage = async () => {
    if (selectedImages.length >= 4) {
      Alert.alert('Límite alcanzado', 'Solo puedes subir un máximo de 4 comprobantes');
      return;
    }

    const permissionResult = await ImagePicker.requestMediaLibraryPermissionsAsync();

    if (!permissionResult.granted) {
      Alert.alert('Permiso requerido', 'Necesitamos acceso a tu galería para seleccionar el comprobante');
      return;
    }

    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsEditing: true,
      quality: 0.8,
    });

    if (!result.canceled && result.assets[0]) {
      setSelectedImages([...selectedImages, result.assets[0].uri]);
    }
  };

  const handleRemoveImage = (index: number) => {
    setSelectedImages(selectedImages.filter((_, i) => i !== index));
  };

  const handleUploadProof = () => {
    // Validar que la operación no haya expirado
    if (isExpired) {
      Alert.alert(
        'Operación Expirada',
        'Esta operación ya no está disponible porque el tiempo ha expirado. Crea una nueva operación desde el inicio.',
        [{ text: 'Entendido', onPress: () => navigation.replace('Tabs', { screen: 'HistoryTab', params: { initialTab: 'completed' } }) }]
      );
      return;
    }

    setUploadDialogVisible(true);
  };

  const handleCloseUploadDialog = () => {
    setUploadDialogVisible(false);
    setOperationCode('');
    setSelectedImages([]);
  };

  const handleConfirmUpload = async () => {
    // Validar que la operación no haya expirado
    if (isExpired) {
      Alert.alert(
        'Operación Expirada',
        'Esta operación ya no está disponible porque el tiempo ha expirado. Crea una nueva operación desde el inicio.',
        [{ text: 'Entendido', onPress: () => navigation.replace('Tabs', { screen: 'HistoryTab', params: { initialTab: 'completed' } }) }]
      );
      return;
    }

    if (selectedImages.length === 0) {
      Alert.alert('Error', 'Debes seleccionar al menos un comprobante');
      return;
    }

    if (!operationCode.trim()) {
      Alert.alert('Error', 'Debes ingresar el código de operación');
      return;
    }

    try {
      setUploading(true);
      console.log('📤 Subiendo comprobante al servidor...');

      // Calcular el monto a transferir
      const amount = operation.operation_type === 'Compra'
        ? operation.amount_usd
        : operation.amount_pen;

      // Subir cada comprobante al servidor
      for (let i = 0; i < selectedImages.length; i++) {
        const imageUri = selectedImages[i];
        const formData = new FormData();

        formData.append('deposit_index', i.toString());
        formData.append('importe', amount.toString());
        formData.append('codigo_operacion', operationCode.trim());
        formData.append('file', {
          uri: imageUri,
          type: 'image/jpeg',
          name: `comprobante_${i}.jpg`,
        } as any);

        console.log(`📤 Subiendo comprobante ${i + 1}/${selectedImages.length}...`);
        await operationsApi.uploadDepositProof(operation.id, i, formData);
        console.log(`✅ Comprobante ${i + 1} subido exitosamente`);
      }

      console.log('✅ Todos los comprobantes subidos al servidor');

      setUploadDialogVisible(false);
      setSelectedImages([]);
      setOperationCode('');

      // Navegar a la pantalla "Recibe"
      navigation.replace('Receive', {
        operation: {
          ...operation,
          status: 'En proceso'
        }
      });
    } catch (error: any) {
      console.error('❌ Error al subir comprobantes:', error);
      Alert.alert('Error', error.message || 'No se pudo subir el comprobante al servidor');
    } finally {
      setUploading(false);
    }
  };

  const handleOpenWhatsApp = () => {
    const phoneNumber = '51926011920';
    const message = `Hola, quiero enviar mi comprobante para la operación ${operation.operation_id}`;
    const url = `https://wa.me/${phoneNumber}?text=${encodeURIComponent(message)}`;

    Linking.openURL(url).catch(() => {
      Alert.alert('Error', 'No se pudo abrir WhatsApp');
    });
  };

  return (
    <ScrollView style={styles.container}>
      {/* Timeline Stepper */}
      <View style={styles.timelineContainer}>
        <View style={styles.timelineStep}>
          <View style={[styles.timelineCircle, styles.timelineCircleCompleted]}>
            <IconButton icon="check" size={16} iconColor="#FFFFFF" />
          </View>
          <Text style={styles.timelineText}>Cotiza</Text>
        </View>

        <View style={[styles.timelineLine, styles.timelineLineCompleted]} />

        <View style={styles.timelineStep}>
          <View style={[styles.timelineCircle, styles.timelineCircleActive]}>
            <IconButton icon="bank-transfer" size={16} iconColor="#FFFFFF" />
          </View>
          <Text style={[styles.timelineText, styles.timelineTextActive]}>Transfiere</Text>
        </View>

        <View style={styles.timelineLine} />

        <View style={styles.timelineStep}>
          <View style={styles.timelineCircle}>
            <IconButton icon="check-circle-outline" size={16} iconColor="#999999" />
          </View>
          <Text style={styles.timelineText}>Recibe</Text>
        </View>
      </View>

      {/* Operation Summary Card */}
      <Card style={styles.summaryCard}>
        <Card.Content>
          <View style={styles.summaryHeader}>
            <View>
              <Text variant="labelSmall" style={styles.summaryLabel}>
                ID de Operación
              </Text>
              <Text variant="titleMedium" style={styles.summaryValue}>
                {operation.operation_id}
              </Text>
            </View>
            <View style={styles.timerContainer}>
              <IconButton icon="clock-outline" size={20} iconColor="#F44336" />
              <Text style={styles.timerText}>{timeRemaining}</Text>
            </View>
          </View>

          <Divider style={styles.summaryDivider} />

          <View style={styles.summaryRow}>
            <View style={styles.summaryItem}>
              <Text style={styles.summaryLabel}>Tipo de operación</Text>
              <Text style={styles.summaryValue}>{operation.operation_type}</Text>
            </View>
            <View style={styles.summaryItem}>
              <Text style={styles.summaryLabel}>Fecha y hora</Text>
              <Text style={styles.summaryValue}>{formatDateTime(operation.created_at)}</Text>
            </View>
          </View>

          <View style={styles.summaryRow}>
            <View style={styles.summaryBox}>
              <Text style={styles.summaryLabel}>Envías</Text>
              <Text style={styles.summaryAmount}>
                {operation.operation_type === 'Compra'
                  ? `$${operation.amount_usd.toFixed(2)}`
                  : `S/ ${operation.amount_pen.toFixed(2)}`
                }
              </Text>
            </View>
            <View style={styles.summaryBox}>
              <Text style={styles.summaryLabel}>Tipo de cambio</Text>
              <Text style={styles.summaryAmount}>{operation.exchange_rate.toFixed(3)}</Text>
            </View>
            <View style={styles.summaryBox}>
              <Text style={styles.summaryLabel}>Recibes</Text>
              <Text style={styles.summaryAmount}>
                {operation.operation_type === 'Compra'
                  ? `S/ ${operation.amount_pen.toFixed(2)}`
                  : `$${operation.amount_usd.toFixed(2)}`
                }
              </Text>
            </View>
          </View>
        </Card.Content>
      </Card>

      {/* Transfer Details Card */}
      <Card style={styles.transferCard}>
        <Card.Content>
          <Text variant="titleMedium" style={styles.transferTitle}>
            Transfiere a:
          </Text>

          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Titular:</Text>
            <Text style={styles.detailValue}>QoriCash SAC</Text>
          </View>

          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Banco:</Text>
            <Text style={styles.detailValue}>{qoriAccount.bank_name}</Text>
          </View>

          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Tipo de cuenta:</Text>
            <Text style={styles.detailValue}>{qoriAccount.account_type}</Text>
          </View>

          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>
              {qoriAccount.use_cci ? 'CCI:' : 'Número de cuenta:'}
            </Text>
            <View style={styles.accountNumberContainer}>
              <Text style={styles.accountNumber}>
                {qoriAccount.use_cci ? qoriAccount.cci : qoriAccount.account_number}
              </Text>
              <IconButton
                icon="content-copy"
                size={20}
                onPress={() => {
                  // Aquí iría lógica para copiar al portapapeles
                  Alert.alert('Copiado', 'Número de cuenta copiado al portapapeles');
                }}
              />
            </View>
          </View>

          {qoriAccount.use_cci && (
            <View style={styles.infoBox}>
              <IconButton icon="information-outline" size={20} iconColor="#2196F3" />
              <Text style={styles.infoText}>
                Para transferencias desde otros bancos, usa el CCI de Interbank
              </Text>
            </View>
          )}

          <View style={styles.importantNote}>
            <IconButton icon="information" size={20} iconColor="#2196F3" />
            <Text style={styles.importantNoteText}>
              Guarda el número de tu operación, lo usaremos en el siguiente paso
            </Text>
          </View>
        </Card.Content>
      </Card>

      {/* Upload Button */}
      <TouchableOpacity
        style={[styles.uploadButton, isExpired && styles.uploadButtonDisabled]}
        onPress={handleUploadProof}
        activeOpacity={0.8}
        disabled={isExpired}
      >
        <Text style={styles.uploadButtonText}>
          {isExpired ? 'OPERACIÓN EXPIRADA' : 'YA TRANSFERÍ'}
        </Text>
      </TouchableOpacity>

      {/* Upload Dialog */}
      <CustomModal
        visible={uploadDialogVisible}
        onDismiss={handleCloseUploadDialog}
        title="Agregar comprobante"
        actions={[
          {
            label: 'Cancelar',
            onPress: handleCloseUploadDialog,
            disabled: uploading,
          },
          {
            label: uploading ? 'Subiendo...' : 'Enviar',
            onPress: handleConfirmUpload,
            primary: true,
            disabled: uploading,
            loading: uploading,
          },
        ]}
      >
        <View>
            <Text style={styles.dialogText}>
              Sube tu comprobante de transferencia para que podamos procesar tu operación.
            </Text>

            {/* Lista de comprobantes seleccionados */}
            {selectedImages.map((imageUri, index) => (
              <View key={index} style={styles.imagePreviewContainer}>
                <View style={styles.imagePreviewInfo}>
                  <IconButton icon="file-image" size={20} iconColor="#82C16C" />
                  <Text style={styles.imagePreviewText}>Comprobante {index + 1}</Text>
                </View>
                <IconButton
                  icon="close-circle"
                  size={20}
                  iconColor="#F44336"
                  onPress={() => handleRemoveImage(index)}
                />
              </View>
            ))}

            {/* Botón para agregar comprobante */}
            {selectedImages.length < 4 && (
              <TouchableOpacity
                style={styles.addImageButton}
                activeOpacity={0.8}
                onPress={handlePickImage}
              >
                <IconButton icon="plus-circle" size={24} iconColor="#82C16C" />
                <Text style={styles.addImageButtonText}>
                  {selectedImages.length === 0 ? 'Seleccionar comprobante' : 'Agregar más comprobante'}
                </Text>
              </TouchableOpacity>
            )}

            {selectedImages.length === 4 && (
              <View style={styles.maxImagesNotice}>
                <IconButton icon="information" size={20} iconColor="#FF9800" />
                <Text style={styles.maxImagesNoticeText}>
                  Has alcanzado el máximo de 4 comprobantes
                </Text>
              </View>
            )}

            <TextInput
              label="Código de operación"
              mode="outlined"
              style={GlobalStyles.input}
              value={operationCode}
              onChangeText={setOperationCode}
              placeholder="Ingresa el código de tu transferencia"
            />

            <View style={styles.alternativeContact}>
              <Text style={styles.alternativeContactTitle}>
                También puedes enviar tu comprobante a:
              </Text>
              <View style={styles.contactRow}>
                <IconButton icon="email" size={20} iconColor="#666666" style={styles.contactIcon} />
                <Text style={styles.alternativeContactText}>
                  info@qoricash.pe
                </Text>
              </View>
              <TouchableOpacity onPress={handleOpenWhatsApp} activeOpacity={0.8} style={styles.contactRow}>
                <IconButton icon="phone" size={20} iconColor="#25D366" style={styles.contactIcon} />
                <Text style={styles.whatsappLink}>
                  +51 926 011 920
                </Text>
              </TouchableOpacity>
            </View>
        </View>
      </CustomModal>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },

  // Timeline Styles
  timelineContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 20,
    paddingHorizontal: 16,
    backgroundColor: Colors.surface,
    marginBottom: 16,
  },
  timelineStep: {
    alignItems: 'center',
  },
  timelineCircle: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#E0E0E0',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 8,
  },
  timelineCircleCompleted: {
    backgroundColor: '#82C16C',
  },
  timelineCircleActive: {
    backgroundColor: '#2196F3',
  },
  timelineLine: {
    flex: 1,
    height: 2,
    backgroundColor: '#E0E0E0',
    marginHorizontal: 8,
  },
  timelineLineCompleted: {
    backgroundColor: '#82C16C',
  },
  timelineText: {
    fontSize: 12,
    color: '#999999',
    fontWeight: '500',
  },
  timelineTextActive: {
    color: '#2196F3',
    fontWeight: '600',
  },

  // Summary Card Styles
  summaryCard: {
    marginHorizontal: 16,
    marginBottom: 16,
    backgroundColor: Colors.surface,
  },
  summaryHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  timerContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFEBEE',
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 16,
  },
  timerText: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#F44336',
  },
  summaryDivider: {
    marginVertical: 12,
  },
  summaryRow: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 8,
  },
  summaryItem: {
    flex: 1,
  },
  summaryBox: {
    flex: 1,
    backgroundColor: '#F5F5F5',
    padding: 12,
    borderRadius: 8,
  },
  summaryLabel: {
    fontSize: 11,
    color: '#666666',
    marginBottom: 4,
  },
  summaryValue: {
    fontSize: 13,
    fontWeight: '600',
    color: Colors.textDark,
  },
  summaryAmount: {
    fontSize: 16,
    fontWeight: 'bold',
    color: Colors.textDark,
  },
  importantNote: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#E3F2FD',
    padding: 12,
    borderRadius: 8,
    marginTop: 12,
  },
  importantNoteText: {
    flex: 1,
    fontSize: 13,
    color: '#1976D2',
    fontWeight: '500',
    marginLeft: 4,
  },

  // Transfer Card Styles
  transferCard: {
    marginHorizontal: 16,
    marginBottom: 16,
    backgroundColor: Colors.surface,
  },
  transferTitle: {
    fontWeight: 'bold',
    marginBottom: 16,
    color: Colors.textDark,
  },
  detailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
  },
  detailLabel: {
    fontSize: 13,
    color: '#666666',
    flex: 1,
  },
  detailValue: {
    fontSize: 14,
    fontWeight: '600',
    color: Colors.textDark,
    flex: 2,
    textAlign: 'right',
  },
  accountNumberContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 2,
    justifyContent: 'flex-end',
  },
  accountNumber: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#2196F3',
  },
  infoBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#E3F2FD',
    padding: 12,
    borderRadius: 8,
    marginTop: 12,
  },
  infoText: {
    flex: 1,
    fontSize: 12,
    color: '#1976D2',
    marginLeft: 8,
  },

  // Upload Button Styles
  uploadButton: {
    backgroundColor: '#82C16C',
    marginHorizontal: 16,
    marginBottom: 24,
    paddingVertical: 16,
    borderRadius: 12,
    alignItems: 'center',
    elevation: 4,
    shadowColor: '#82C16C',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
  },
  uploadButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: 'bold',
    letterSpacing: 1,
  },
  uploadButtonDisabled: {
    backgroundColor: '#BDBDBD',
    elevation: 0,
    shadowOpacity: 0,
  },

  // Dialog Styles
  dialog: {
    backgroundColor: Colors.surface,
  },
  dialogText: {
    marginBottom: 16,
    color: Colors.textDark,
  },
  imagePreviewContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#F0F8F0',
    padding: 8,
    borderRadius: 8,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: '#82C16C',
  },
  imagePreviewInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  imagePreviewText: {
    fontSize: 14,
    color: Colors.textDark,
    fontWeight: '600',
    marginLeft: 4,
  },
  addImageButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: '#82C16C',
    borderStyle: 'dashed',
    borderRadius: 12,
    padding: 12,
    marginBottom: 12,
  },
  addImageButtonText: {
    color: '#82C16C',
    fontWeight: '600',
    fontSize: 14,
    marginLeft: 4,
  },
  maxImagesNotice: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFF3E0',
    padding: 12,
    borderRadius: 8,
    marginBottom: 12,
  },
  maxImagesNoticeText: {
    flex: 1,
    fontSize: 12,
    color: '#F57C00',
    marginLeft: 4,
  },
  input: {
    marginBottom: 12,
  },
  alternativeContact: {
    backgroundColor: '#F5F5F5',
    padding: 16,
    borderRadius: 8,
    marginTop: 16,
  },
  alternativeContactTitle: {
    fontSize: 13,
    fontWeight: '600',
    color: Colors.textDark,
    marginBottom: 8,
  },
  contactRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 4,
  },
  contactIcon: {
    margin: 0,
    marginRight: -8,
  },
  alternativeContactText: {
    fontSize: 13,
    color: Colors.textDark,
  },
  whatsappLink: {
    fontSize: 13,
    color: '#25D366',
    fontWeight: '600',
    textDecorationLine: 'underline',
  },
});
