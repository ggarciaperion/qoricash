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
  ImageBackground,
  ActivityIndicator,
  TextInput,
} from 'react-native';
import { Text } from 'react-native-paper';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { MotiView } from 'moti';
import * as ImagePicker from 'expo-image-picker';

import { operationsApi } from '../api/operations';
import { Operation } from '../types';
import { useAuth } from '../contexts/AuthContext';
import {
  formatCurrency,
  formatDateTime,
  formatExchangeRate,
  formatBankAccount,
} from '../utils/formatters';

// ─── Paleta ───────────────────────────────────────────────────────────────────
const GLASS_BG     = 'rgba(255,255,255,0.09)';
const GLASS_BORDER = 'rgba(255,255,255,0.15)';
const GREEN        = '#22c55e';
const RED          = '#ef4444';
const AMBER        = '#f59e0b';
const BLUE         = '#3b82f6';

// ─── Helpers de estado ────────────────────────────────────────────────────────
const STATUS_CFG: Record<string, { color: string; label: string }> = {
  completada:  { color: GREEN,  label: 'Completada'  },
  completado:  { color: GREEN,  label: 'Completada'  },
  pendiente:   { color: AMBER,  label: 'Pendiente'   },
  procesando:  { color: BLUE,   label: 'Procesando'  },
  en_proceso:  { color: BLUE,   label: 'En Proceso'  },
  cancelada:   { color: RED,    label: 'Cancelada'   },
  cancelado:   { color: RED,    label: 'Cancelada'   },
  expirado:    { color: RED,    label: 'Expirado'    },
};

const getStatusCfg = (status: string) =>
  STATUS_CFG[status.toLowerCase()] ?? { color: 'rgba(255,255,255,0.4)', label: status };

// ─── Types ────────────────────────────────────────────────────────────────────
interface DepositForm {
  imageUri: string;
  importe: string;
  codigoOperacion: string;
}
interface Props { route: any; navigation: any }

// ─── Component ────────────────────────────────────────────────────────────────
export const OperationDetailScreen: React.FC<Props> = ({ route, navigation }) => {
  const insets = useSafeAreaInsets();
  const { client } = useAuth();
  const { operationId } = route.params;

  const [operation, setOperation]   = useState<Operation | null>(null);
  const [loading, setLoading]       = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [uploading, setUploading]   = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [deposits, setDeposits]         = useState<DepositForm[]>([]);
  const [currentDeposit, setCurrentDeposit] = useState<DepositForm>({
    imageUri: '', importe: '', codigoOperacion: '',
  });
  const [errors, setErrors] = useState<any>({});

  // ── Logic helpers ───────────────────────────────────────────────────────────
  const isExpired = (createdAt: string) => {
    if (!createdAt) return false;
    return (Date.now() - new Date(createdAt).getTime()) / 1000 >= 30 * 60;
  };

  const getDisplayStatus = (op: Operation) => {
    if (op.status === 'pendiente' && isExpired(op.created_at || '')) return 'Expirado';
    return op.status || 'N/A';
  };

  const getSourceCurrency  = (op: Operation) => op.operation_type === 'Venta' ? 'S/' : '$';
  const getDestCurrency    = (op: Operation) => op.operation_type === 'Venta' ? '$' : 'S/';
  const getOperationTotal  = () => {
    if (!operation) return 0;
    return operation.operation_type === 'Venta'
      ? operation.amount_pen || 0
      : operation.amount_usd || 0;
  };
  const getTotalDeposits = () =>
    deposits.reduce((s, d) => s + parseFloat(d.importe || '0'), 0);

  // ── Data loading ────────────────────────────────────────────────────────────
  useEffect(() => { loadOperation(); }, [operationId]);

  const loadOperation = async () => {
    try {
      setLoading(true);
      setOperation(await operationsApi.getOperationById(operationId, client?.dni || ''));
    } catch (e: any) {
      Alert.alert('Error', e.message || 'Error al cargar operación');
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

  // ── Modal ───────────────────────────────────────────────────────────────────
  const openModal = () => {
    setModalVisible(true);
    setDeposits([]);
    setCurrentDeposit({ imageUri: '', importe: '', codigoOperacion: '' });
    setErrors({});
  };

  const handleSelectImage = async () => {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert('Permiso Denegado', 'Se necesita permiso para acceder a la galería');
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'], allowsEditing: true, aspect: [4, 3], quality: 0.8,
    });
    if (!result.canceled && result.assets[0]) {
      setCurrentDeposit(d => ({ ...d, imageUri: result.assets[0].uri }));
      setErrors((e: any) => ({ ...e, imageUri: '' }));
    }
  };

  const validateDeposit = () => {
    const e: any = {};
    if (!currentDeposit.imageUri) e.imageUri = 'Seleccione una imagen';
    if (!currentDeposit.importe || parseFloat(currentDeposit.importe) <= 0) e.importe = 'Ingrese un importe válido';
    if (!currentDeposit.codigoOperacion.trim()) e.codigoOperacion = 'Ingrese el código de operación';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleAddDeposit = () => {
    if (!validateDeposit()) return;
    setDeposits(ds => [...ds, currentDeposit]);
    setCurrentDeposit({ imageUri: '', importe: '', codigoOperacion: '' });
    setErrors({});
  };

  const handleSubmitDeposits = async () => {
    if (deposits.length === 0) { Alert.alert('Error', 'Debe agregar al menos un comprobante'); return; }
    const total = getTotalDeposits();
    const opTotal = getOperationTotal();
    const currency = operation?.operation_type === 'Venta' ? 'PEN' : 'USD';
    if (Math.abs(total - opTotal) > 0.01) {
      Alert.alert('Validación', `La suma (${formatCurrency(total, currency)}) debe coincidir con el monto (${formatCurrency(opTotal, currency)})`);
      return;
    }
    try {
      setUploading(true);
      for (let i = 0; i < deposits.length; i++) {
        const dep = deposits[i];
        const idx = (operation?.client_deposits?.length || 0) + i;
        const fd  = new FormData();
        fd.append('deposit_index', idx.toString());
        fd.append('importe', dep.importe);
        fd.append('codigo_operacion', dep.codigoOperacion);
        fd.append('client_dni', client?.dni || '');
        fd.append('file', { uri: dep.imageUri, type: 'image/jpeg', name: `comprobante_${idx}.jpg` } as any);
        await operationsApi.uploadDepositProof(operationId, idx, fd);
      }
      Alert.alert('Éxito', 'Comprobantes subidos exitosamente', [{
        text: 'OK', onPress: () => {
          setModalVisible(false);
          setDeposits([]);
          navigation.navigate('Tabs', { screen: 'HomeTab' });
        },
      }]);
    } catch (e: any) {
      Alert.alert('Error', e.message || 'Error al subir comprobantes');
    } finally {
      setUploading(false);
    }
  };

  const openPDF = (url: string) =>
    Linking.openURL(url).catch(() => Alert.alert('Error', 'No se pudo abrir el enlace'));

  // ── Loading / error states ──────────────────────────────────────────────────
  if (loading) {
    return (
      <View style={s.fullCenter}>
        <ImageBackground source={require('../../assets/cd.png')} style={StyleSheet.absoluteFill} resizeMode="cover" />
        <View style={[StyleSheet.absoluteFill, s.overlay]} />
        <ActivityIndicator size="large" color={GREEN} />
        <Text style={s.loadText}>Cargando operación...</Text>
      </View>
    );
  }

  if (!operation) {
    return (
      <View style={s.fullCenter}>
        <ImageBackground source={require('../../assets/cd.png')} style={StyleSheet.absoluteFill} resizeMode="cover" />
        <View style={[StyleSheet.absoluteFill, s.overlay]} />
        <Ionicons name="alert-circle-outline" size={40} color="rgba(255,255,255,0.3)" />
        <Text style={s.loadText}>Operación no encontrada</Text>
      </View>
    );
  }

  const displayStatus = getDisplayStatus(operation);
  const statusCfg     = getStatusCfg(displayStatus);
  const inputCurrency = operation.operation_type === 'Compra' ? 'USD' : 'PEN';
  const outputCurrency = operation.operation_type === 'Compra' ? 'PEN' : 'USD';

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <View style={s.root}>
      <ImageBackground
        source={require('../../assets/cd.png')}
        style={StyleSheet.absoluteFill}
        resizeMode="cover"
      />
      <View style={[StyleSheet.absoluteFill, s.overlay]} pointerEvents="none" />

      <ScrollView
        style={s.scroll}
        contentContainerStyle={[s.content, { paddingTop: insets.top + 12, paddingBottom: insets.bottom + 32 }]}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="rgba(255,255,255,0.5)" />
        }
      >
        {/* ── Header ── */}
        <View style={s.header}>
          <TouchableOpacity onPress={() => navigation.goBack()} style={s.backBtn} activeOpacity={0.75}>
            <Ionicons name="chevron-back" size={22} color="#fff" />
          </TouchableOpacity>
          <Text style={s.headerTitle}>Detalle de Operación</Text>
          <View style={s.headerSpacer} />
        </View>

        {/* ── ID + Fecha + Estado ── */}
        <MotiView
          from={{ opacity: 0, translateY: -12 }}
          animate={{ opacity: 1, translateY: 0 }}
          transition={{ type: 'spring', delay: 380, damping: 22, stiffness: 200 }}
          style={s.card}
        >
          <View style={s.idRow}>
            <View style={{ flex: 1 }}>
              <Text style={s.labelXs}>ID de Operación</Text>
              <Text style={s.operationId}>{operation.operation_id || 'N/A'}</Text>
              <Text style={s.dateText}>
                {operation.created_at ? formatDateTime(operation.created_at) : 'N/A'}
              </Text>
            </View>
            <View style={[s.statusBadge, { backgroundColor: statusCfg.color + '22', borderColor: statusCfg.color + '55' }]}>
              <View style={[s.statusDot, { backgroundColor: statusCfg.color }]} />
              <Text style={[s.statusText, { color: statusCfg.color }]}>{displayStatus}</Text>
            </View>
          </View>
        </MotiView>

        {/* ── Tipo + Montos ── */}
        <MotiView
          from={{ opacity: 0, translateY: 16, scale: 0.97 }}
          animate={{ opacity: 1, translateY: 0, scale: 1 }}
          transition={{ type: 'spring', delay: 440, damping: 22, stiffness: 180 }}
          style={s.card}
        >
          {/* Badge compra/venta */}
          <View style={s.typePillRow}>
            <View style={[s.typePill, operation.operation_type === 'Compra' ? s.typePillCompra : s.typePillVenta]}>
              <Ionicons
                name={operation.operation_type === 'Compra' ? 'arrow-down-circle' : 'arrow-up-circle'}
                size={14}
                color={operation.operation_type === 'Compra' ? GREEN : BLUE}
              />
              <Text style={[s.typeText, { color: operation.operation_type === 'Compra' ? GREEN : BLUE }]}>
                {operation.operation_type === 'Compra' ? 'Qoricash Compra' : 'Qoricash Vende'}
              </Text>
            </View>
          </View>

          {/* Enviando */}
          <View style={s.amountBlock}>
            <Text style={s.amountBlockLabel}>
              {operation.operation_type === 'Compra' ? 'Enviaste' : 'Pagaste'}
            </Text>
            <View style={s.amountBlockInner}>
              <Text style={s.amountValue}>
                {operation.operation_type === 'Compra'
                  ? formatCurrency(operation.amount_usd || 0, 'USD')
                  : formatCurrency(operation.amount_pen || 0, 'PEN')}
              </Text>
              <View style={s.currencyTag}>
                <Text style={s.currencyTagText}>{inputCurrency === 'USD' ? 'Dólares' : 'Soles'}</Text>
              </View>
            </View>
          </View>

          {/* Tipo de cambio */}
          <View style={s.tcRow}>
            <View style={s.tcDash} />
            <View style={s.tcPill}>
              <Ionicons name="swap-vertical" size={12} color={GREEN} />
              <Text style={s.tcLabel}>TC</Text>
              <Text style={s.tcValue}>{formatExchangeRate(operation.exchange_rate || 0)}</Text>
            </View>
            <View style={s.tcDash} />
          </View>

          {/* Recibiendo */}
          <View style={s.amountBlock}>
            <Text style={s.amountBlockLabel}>Recibiste</Text>
            <View style={s.amountBlockInner}>
              <Text style={[s.amountValue, { color: GREEN }]}>
                {operation.operation_type === 'Compra'
                  ? formatCurrency(operation.amount_pen || 0, 'PEN')
                  : formatCurrency(operation.amount_usd || 0, 'USD')}
              </Text>
              <View style={[s.currencyTag, { backgroundColor: GREEN + '20', borderColor: GREEN + '40' }]}>
                <Text style={[s.currencyTagText, { color: GREEN }]}>{outputCurrency === 'USD' ? 'Dólares' : 'Soles'}</Text>
              </View>
            </View>
          </View>
        </MotiView>

        {/* ── Cuentas Bancarias ── */}
        {(operation.source_account || operation.destination_account) && (
          <MotiView
            from={{ opacity: 0, translateY: 16 }}
            animate={{ opacity: 1, translateY: 0 }}
            transition={{ type: 'spring', delay: 500, damping: 22, stiffness: 180 }}
            style={s.card}
          >
            <Text style={s.sectionTitle}>Cuentas Bancarias</Text>

            {operation.source_account && (
              <View style={s.bankRow}>
                <View style={s.bankIconWrap}>
                  <Ionicons name="business-outline" size={18} color="rgba(255,255,255,0.6)" />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={s.bankLabel}>Cuenta Origen ({getSourceCurrency(operation)})</Text>
                  <Text style={s.bankName}>{operation.source_bank_name || ''}</Text>
                  <Text style={s.bankAccount}>{formatBankAccount(operation.source_account)}</Text>
                </View>
              </View>
            )}

            {operation.source_account && operation.destination_account && (
              <View style={s.bankDivider} />
            )}

            {operation.destination_account && (
              <View style={s.bankRow}>
                <View style={[s.bankIconWrap, { backgroundColor: GREEN + '18' }]}>
                  <Ionicons name="card-outline" size={18} color={GREEN} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={s.bankLabel}>Cuenta Destino ({getDestCurrency(operation)})</Text>
                  <Text style={s.bankName}>{operation.destination_bank_name || ''}</Text>
                  <Text style={s.bankAccount}>{formatBankAccount(operation.destination_account)}</Text>
                </View>
              </View>
            )}
          </MotiView>
        )}

        {/* ── Comprobantes del Cliente ── */}
        {operation.client_deposits && Array.isArray(operation.client_deposits) && operation.client_deposits.length > 0 && (
          <MotiView
            from={{ opacity: 0, translateY: 16 }}
            animate={{ opacity: 1, translateY: 0 }}
            transition={{ type: 'spring', delay: 560, damping: 22, stiffness: 180 }}
            style={s.card}
          >
            <Text style={s.sectionTitle}>Comprobantes del Cliente</Text>
            {operation.client_deposits.map((dep: any, i: number) => (
              <View key={i} style={[s.proofRow, i < operation.client_deposits!.length - 1 && s.proofRowBorder]}>
                <View style={s.proofIconWrap}>
                  <Ionicons name="document-text-outline" size={18} color="rgba(255,255,255,0.55)" />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={s.proofLabel}>Abono {i + 1}</Text>
                  <Text style={s.proofValue}>{formatCurrency(dep?.importe || 0, 'PEN')}</Text>
                  <Text style={s.proofCode}>Código: {dep?.codigo_operacion || 'N/A'}</Text>
                </View>
                {dep?.comprobante_url && (
                  <TouchableOpacity onPress={() => openPDF(dep.comprobante_url)} style={s.downloadBtn} activeOpacity={0.75}>
                    <Ionicons name="download-outline" size={18} color={GREEN} />
                  </TouchableOpacity>
                )}
              </View>
            ))}
          </MotiView>
        )}

        {/* ── Comprobantes del Operador ── */}
        {operation.operator_proofs && Array.isArray(operation.operator_proofs) && operation.operator_proofs.length > 0 && (
          <MotiView
            from={{ opacity: 0, translateY: 16 }}
            animate={{ opacity: 1, translateY: 0 }}
            transition={{ type: 'spring', delay: 620, damping: 22, stiffness: 180 }}
            style={s.card}
          >
            <Text style={s.sectionTitle}>Comprobantes del Operador</Text>
            {operation.operator_proofs.map((proof: any, i: number) => (
              <View key={i} style={[s.proofRow, i < operation.operator_proofs!.length - 1 && s.proofRowBorder]}>
                <View style={[s.proofIconWrap, { backgroundColor: GREEN + '18' }]}>
                  <Ionicons name="checkmark-circle-outline" size={18} color={GREEN} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={s.proofLabel}>Comprobante {i + 1}</Text>
                  <Text style={s.proofCode}>{proof?.comentario || 'Sin comentarios'}</Text>
                </View>
                {proof?.comprobante_url && (
                  <TouchableOpacity onPress={() => openPDF(proof.comprobante_url)} style={s.downloadBtn} activeOpacity={0.75}>
                    <Ionicons name="download-outline" size={18} color={GREEN} />
                  </TouchableOpacity>
                )}
              </View>
            ))}
            {operation.operator_comments && (
              <View style={s.commentsWrap}>
                <Text style={s.commentsLabel}>Comentarios del operador</Text>
                <Text style={s.commentsText}>{operation.operator_comments}</Text>
              </View>
            )}
          </MotiView>
        )}

        {/* ── Factura Electrónica ── */}
        {operation.invoices && Array.isArray(operation.invoices) && operation.invoices.length > 0 && (
          <MotiView
            from={{ opacity: 0, translateY: 16 }}
            animate={{ opacity: 1, translateY: 0 }}
            transition={{ type: 'spring', delay: 680, damping: 22, stiffness: 180 }}
            style={s.card}
          >
            <Text style={s.sectionTitle}>Factura Electrónica</Text>
            {operation.invoices.map((inv: any, i: number) => (
              <View key={i}>
                <View style={s.invoiceRow}>
                  <View style={s.proofIconWrap}>
                    <Ionicons name="receipt-outline" size={18} color="rgba(255,255,255,0.55)" />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={s.proofValue}>{inv?.invoice_number || 'N/A'}</Text>
                    <Text style={s.proofCode}>
                      {inv?.invoice_type || ''} · {formatCurrency(inv?.monto_total || 0, 'PEN')}
                    </Text>
                  </View>
                </View>
                {inv?.nubefact_enlace_pdf && (
                  <TouchableOpacity onPress={() => openPDF(inv.nubefact_enlace_pdf)} style={s.pdfBtn} activeOpacity={0.8}>
                    <Ionicons name="download-outline" size={15} color={GREEN} />
                    <Text style={s.pdfBtnText}>Descargar PDF</Text>
                  </TouchableOpacity>
                )}
              </View>
            ))}
          </MotiView>
        )}

        {/* ── Notas ── */}
        {operation.notes && (
          <MotiView
            from={{ opacity: 0, translateY: 16 }}
            animate={{ opacity: 1, translateY: 0 }}
            transition={{ type: 'spring', delay: 280, damping: 22, stiffness: 180 }}
            style={s.card}
          >
            <Text style={s.sectionTitle}>Notas</Text>
            <Text style={s.notesText}>{operation.notes}</Text>
          </MotiView>
        )}

        {/* ── Acción: Subir comprobante / Expirado ── */}
        {operation.status === 'pendiente' && (
          <MotiView
            from={{ opacity: 0, translateY: 10 }}
            animate={{ opacity: 1, translateY: 0 }}
            transition={{ type: 'spring', delay: 300, damping: 22, stiffness: 180 }}
            style={{ marginBottom: 12 }}
          >
            {isExpired(operation.created_at || '') ? (
              <View style={s.expiredBanner}>
                <Ionicons name="time-outline" size={20} color={RED} style={{ marginBottom: 6 }} />
                <Text style={s.expiredText}>
                  Esta operación ha expirado. No se pueden subir comprobantes después de 30 minutos.
                </Text>
              </View>
            ) : (
              <TouchableOpacity onPress={openModal} disabled={uploading} style={s.uploadBtn} activeOpacity={0.82}>
                <Ionicons name="cloud-upload-outline" size={18} color="#fff" />
                <Text style={s.uploadBtnText}>{uploading ? 'SUBIENDO...' : 'SUBIR COMPROBANTE'}</Text>
              </TouchableOpacity>
            )}
          </MotiView>
        )}

        {/* ── Volver ── */}
        <TouchableOpacity onPress={() => navigation.goBack()} style={s.backBtnBottom} activeOpacity={0.82}>
          <Text style={s.backBtnBottomText}>VOLVER</Text>
        </TouchableOpacity>
      </ScrollView>

      {/* ── Modal comprobantes ── */}
      <Modal
        visible={modalVisible}
        animationType="slide"
        transparent
        onRequestClose={() => setModalVisible(false)}
      >
        <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
          <View style={s.modalOverlay}>
            <View style={s.modalSheet}>
              {/* Modal header */}
              <View style={s.modalHeader}>
                <Text style={s.modalTitle}>Agregar Comprobantes</Text>
                <TouchableOpacity onPress={() => setModalVisible(false)} style={s.modalCloseBtn} activeOpacity={0.75}>
                  <Ionicons name="close" size={20} color="rgba(255,255,255,0.7)" />
                </TouchableOpacity>
              </View>

              <ScrollView
                style={{ maxHeight: '75%' }}
                contentContainerStyle={s.modalBody}
                keyboardShouldPersistTaps="handled"
                showsVerticalScrollIndicator={false}
              >
                {/* Info monto */}
                <View style={s.modalInfoCard}>
                  <Text style={s.modalInfoLabel}>Monto total de la operación</Text>
                  <Text style={s.modalInfoValue}>
                    {formatCurrency(getOperationTotal(), operation.operation_type === 'Venta' ? 'PEN' : 'USD')}
                  </Text>
                  {deposits.length > 0 && (
                    <>
                      <View style={s.modalDivider} />
                      <Text style={s.modalInfoLabel}>Total ingresado</Text>
                      <Text style={[s.modalInfoValue, {
                        color: Math.abs(getTotalDeposits() - getOperationTotal()) < 0.01 ? GREEN : AMBER,
                      }]}>
                        {formatCurrency(getTotalDeposits(), operation.operation_type === 'Venta' ? 'PEN' : 'USD')}
                      </Text>
                      <Text style={s.modalFaltante}>
                        Faltante: {formatCurrency(
                          getOperationTotal() - getTotalDeposits(),
                          operation.operation_type === 'Venta' ? 'PEN' : 'USD'
                        )}
                      </Text>
                    </>
                  )}
                </View>

                {/* Lista comprobantes agregados */}
                {deposits.length > 0 && (
                  <View style={{ marginBottom: 16 }}>
                    <Text style={s.modalSectionTitle}>Comprobantes ({deposits.length})</Text>
                    {deposits.map((dep, i) => (
                      <View key={i} style={s.modalDepositCard}>
                        <Image source={{ uri: dep.imageUri }} style={s.thumbnail} />
                        <View style={{ flex: 1, marginLeft: 12 }}>
                          <Text style={s.proofValue}>
                            {formatCurrency(parseFloat(dep.importe), operation.operation_type === 'Venta' ? 'PEN' : 'USD')}
                          </Text>
                          <Text style={s.proofCode}>Código: {dep.codigoOperacion}</Text>
                        </View>
                        <TouchableOpacity onPress={() => setDeposits(ds => ds.filter((_, j) => j !== i))} activeOpacity={0.75}>
                          <Ionicons name="trash-outline" size={20} color={RED} />
                        </TouchableOpacity>
                      </View>
                    ))}
                  </View>
                )}

                {/* Formulario */}
                <View style={s.modalDivider} />
                <Text style={s.modalSectionTitle}>
                  {deposits.length === 0 ? 'Agregar comprobante' : 'Agregar otro comprobante'}
                </Text>

                {/* Imagen */}
                <TouchableOpacity onPress={handleSelectImage} style={s.imagePickerBtn} activeOpacity={0.8}>
                  <Ionicons name="image-outline" size={18} color="rgba(255,255,255,0.6)" />
                  <Text style={s.imagePickerText}>
                    {currentDeposit.imageUri ? 'Cambiar imagen' : 'Seleccionar imagen'}
                  </Text>
                </TouchableOpacity>
                {currentDeposit.imageUri && (
                  <Image source={{ uri: currentDeposit.imageUri }} style={s.previewImage} />
                )}
                {errors.imageUri && <Text style={s.errorText}>{errors.imageUri}</Text>}

                {/* Importe */}
                <TextInput
                  placeholder={`Importe (${operation.operation_type === 'Venta' ? 'S/' : '$'})`}
                  placeholderTextColor="rgba(255,255,255,0.35)"
                  value={currentDeposit.importe}
                  onChangeText={t => { setCurrentDeposit(d => ({ ...d, importe: t })); setErrors((e: any) => ({ ...e, importe: '' })); }}
                  keyboardType="decimal-pad"
                  style={[s.modalInput, errors.importe && s.modalInputError]}
                />
                {errors.importe && <Text style={s.errorText}>{errors.importe}</Text>}

                {/* Código */}
                <TextInput
                  placeholder="Código de operación"
                  placeholderTextColor="rgba(255,255,255,0.35)"
                  value={currentDeposit.codigoOperacion}
                  onChangeText={t => { setCurrentDeposit(d => ({ ...d, codigoOperacion: t })); setErrors((e: any) => ({ ...e, codigoOperacion: '' })); }}
                  style={[s.modalInput, errors.codigoOperacion && s.modalInputError]}
                />
                {errors.codigoOperacion && <Text style={s.errorText}>{errors.codigoOperacion}</Text>}

                <TouchableOpacity onPress={handleAddDeposit} style={s.addBtn} activeOpacity={0.8}>
                  <Ionicons name="add-circle-outline" size={16} color="#fff" />
                  <Text style={s.addBtnText}>Agregar a la lista</Text>
                </TouchableOpacity>
              </ScrollView>

              {/* Modal actions */}
              <View style={s.modalActions}>
                <TouchableOpacity onPress={() => setModalVisible(false)} style={s.modalCancelBtn} activeOpacity={0.8}>
                  <Text style={s.modalCancelText}>Cancelar</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  onPress={handleSubmitDeposits}
                  disabled={uploading || deposits.length === 0}
                  style={[s.modalSubmitBtn, (uploading || deposits.length === 0) && s.modalSubmitBtnDisabled]}
                  activeOpacity={0.82}
                >
                  <Text style={[s.modalSubmitText, (uploading || deposits.length === 0) && { color: 'rgba(255,255,255,0.35)' }]}>
                    {uploading ? 'Enviando...' : 'Enviar Comprobantes'}
                  </Text>
                </TouchableOpacity>
              </View>
            </View>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </View>
  );
};

// ─── Estilos ──────────────────────────────────────────────────────────────────
const s = StyleSheet.create({
  root:    { flex: 1 },
  overlay: { backgroundColor: 'transparent' },
  scroll:  { flex: 1 },
  content: { flexGrow: 1, paddingHorizontal: 18 },

  // Loading / error
  fullCenter: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 14 },
  loadText:   { color: 'rgba(255,255,255,0.5)', fontSize: 14 },

  // Header
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 20,
  },
  backBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: GLASS_BG,
    borderWidth: 1,
    borderColor: GLASS_BORDER,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  headerTitle: {
    flex: 1,
    fontSize: 20,
    fontWeight: '700',
    color: '#FFFFFF',
    letterSpacing: -0.3,
  },
  headerSpacer: { width: 36 },

  // Card base
  card: {
    backgroundColor: GLASS_BG,
    borderWidth: 1,
    borderColor: GLASS_BORDER,
    borderRadius: 22,
    padding: 18,
    marginBottom: 14,
  },

  // ID + status row
  idRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 12,
  },
  labelXs: {
    fontSize: 10,
    fontWeight: '600',
    color: 'rgba(255,255,255,0.38)',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    marginBottom: 4,
  },
  operationId: {
    fontSize: 24,
    fontWeight: '800',
    color: '#FFFFFF',
    letterSpacing: -0.5,
    marginBottom: 4,
  },
  dateText: {
    fontSize: 12,
    color: 'rgba(255,255,255,0.42)',
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    borderWidth: 1,
    borderRadius: 20,
    paddingHorizontal: 10,
    paddingVertical: 6,
    alignSelf: 'flex-start',
    marginTop: 4,
  },
  statusDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  statusText: {
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 0.2,
  },

  // Tipo + montos
  typePillRow: { alignItems: 'center', marginBottom: 18 },
  typePill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    borderWidth: 1,
    borderRadius: 20,
    paddingHorizontal: 14,
    paddingVertical: 7,
  },
  typePillCompra: {
    backgroundColor: GREEN + '15',
    borderColor: GREEN + '40',
  },
  typePillVenta: {
    backgroundColor: BLUE + '15',
    borderColor: BLUE + '40',
  },
  typeText: {
    fontSize: 13,
    fontWeight: '700',
    letterSpacing: 0.3,
  },

  amountBlock: { marginBottom: 8 },
  amountBlockLabel: {
    fontSize: 10,
    fontWeight: '600',
    color: 'rgba(255,255,255,0.38)',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    marginBottom: 6,
  },
  amountBlockInner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: 'rgba(255,255,255,0.06)',
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  amountValue: {
    fontSize: 22,
    fontWeight: '700',
    color: '#FFFFFF',
    letterSpacing: -0.3,
  },
  currencyTag: {
    backgroundColor: 'rgba(255,255,255,0.10)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.18)',
    borderRadius: 10,
    paddingHorizontal: 9,
    paddingVertical: 4,
  },
  currencyTagText: {
    fontSize: 11,
    fontWeight: '600',
    color: 'rgba(255,255,255,0.7)',
    letterSpacing: 0.2,
  },

  tcRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginVertical: 10,
    gap: 8,
  },
  tcDash: {
    flex: 1,
    height: StyleSheet.hairlineWidth * 2,
    backgroundColor: GLASS_BORDER,
  },
  tcPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    backgroundColor: GREEN + '15',
    borderWidth: 1,
    borderColor: GREEN + '35',
    borderRadius: 20,
    paddingHorizontal: 12,
    paddingVertical: 5,
  },
  tcLabel: {
    fontSize: 10,
    fontWeight: '600',
    color: 'rgba(255,255,255,0.5)',
    letterSpacing: 0.5,
  },
  tcValue: {
    fontSize: 13,
    fontWeight: '700',
    color: GREEN,
  },

  // Section title
  sectionTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: 'rgba(255,255,255,0.55)',
    letterSpacing: 0.8,
    textTransform: 'uppercase',
    marginBottom: 14,
  },

  // Cuentas bancarias
  bankRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 12,
    paddingVertical: 4,
  },
  bankIconWrap: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: 'rgba(255,255,255,0.08)',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  bankLabel: {
    fontSize: 10,
    fontWeight: '600',
    color: 'rgba(255,255,255,0.38)',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 2,
  },
  bankName: {
    fontSize: 14,
    fontWeight: '600',
    color: '#FFFFFF',
    marginBottom: 2,
  },
  bankAccount: {
    fontSize: 12,
    color: 'rgba(255,255,255,0.52)',
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
  },
  bankDivider: {
    height: StyleSheet.hairlineWidth,
    backgroundColor: GLASS_BORDER,
    marginVertical: 14,
  },

  // Proof rows
  proofRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingVertical: 10,
  },
  proofRowBorder: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: GLASS_BORDER,
  },
  proofIconWrap: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: 'rgba(255,255,255,0.08)',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  proofLabel: {
    fontSize: 10,
    fontWeight: '600',
    color: 'rgba(255,255,255,0.38)',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 2,
  },
  proofValue: {
    fontSize: 15,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  proofCode: {
    fontSize: 12,
    color: 'rgba(255,255,255,0.45)',
    marginTop: 2,
  },
  downloadBtn: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: GREEN + '18',
    borderWidth: 1,
    borderColor: GREEN + '35',
    alignItems: 'center',
    justifyContent: 'center',
  },

  // Operador comments
  commentsWrap: {
    marginTop: 12,
    backgroundColor: 'rgba(255,255,255,0.06)',
    borderRadius: 12,
    padding: 12,
  },
  commentsLabel: {
    fontSize: 10,
    fontWeight: '600',
    color: 'rgba(255,255,255,0.38)',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 6,
  },
  commentsText: {
    fontSize: 13,
    color: 'rgba(255,255,255,0.72)',
    lineHeight: 19,
  },

  // Invoice
  invoiceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginBottom: 10,
  },
  pdfBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    alignSelf: 'flex-start',
    borderWidth: 1,
    borderColor: GREEN + '40',
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 7,
    backgroundColor: GREEN + '12',
    marginTop: 4,
  },
  pdfBtnText: {
    fontSize: 13,
    fontWeight: '600',
    color: GREEN,
  },

  // Notes
  notesText: {
    fontSize: 14,
    color: 'rgba(255,255,255,0.72)',
    lineHeight: 21,
  },

  // Actions
  expiredBanner: {
    backgroundColor: RED + '15',
    borderWidth: 1,
    borderColor: RED + '35',
    borderRadius: 16,
    padding: 18,
    alignItems: 'center',
  },
  expiredText: {
    fontSize: 13,
    color: RED,
    textAlign: 'center',
    lineHeight: 20,
  },
  uploadBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    backgroundColor: GREEN,
    borderRadius: 18,
    paddingVertical: 17,
    shadowColor: GREEN,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.35,
    shadowRadius: 14,
    elevation: 8,
  },
  uploadBtnText: {
    fontSize: 15,
    fontWeight: '800',
    color: '#fff',
    letterSpacing: 1.2,
  },
  backBtnBottom: {
    borderWidth: 1,
    borderColor: GLASS_BORDER,
    borderRadius: 18,
    paddingVertical: 16,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: GLASS_BG,
    marginTop: 4,
  },
  backBtnBottomText: {
    fontSize: 14,
    fontWeight: '700',
    color: 'rgba(255,255,255,0.65)',
    letterSpacing: 1,
  },

  // ── Modal ──────────────────────────────────────────────────────────────────
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.72)',
    justifyContent: 'flex-end',
  },
  modalSheet: {
    backgroundColor: '#0f1f30',
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    borderTopWidth: 1,
    borderLeftWidth: 1,
    borderRightWidth: 1,
    borderColor: GLASS_BORDER,
    paddingBottom: Platform.OS === 'ios' ? 28 : 12,
    maxHeight: '92%',
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 22,
    paddingTop: 20,
    paddingBottom: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: GLASS_BORDER,
  },
  modalTitle: {
    fontSize: 17,
    fontWeight: '700',
    color: '#FFFFFF',
    letterSpacing: -0.2,
  },
  modalCloseBtn: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: 'rgba(255,255,255,0.08)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  modalBody: {
    paddingHorizontal: 22,
    paddingTop: 18,
    paddingBottom: 12,
  },
  modalInfoCard: {
    backgroundColor: 'rgba(255,255,255,0.07)',
    borderWidth: 1,
    borderColor: GLASS_BORDER,
    borderRadius: 16,
    padding: 16,
    marginBottom: 18,
  },
  modalInfoLabel: {
    fontSize: 11,
    color: 'rgba(255,255,255,0.45)',
    marginBottom: 4,
    fontWeight: '500',
  },
  modalInfoValue: {
    fontSize: 22,
    fontWeight: '800',
    color: '#FFFFFF',
    letterSpacing: -0.3,
  },
  modalFaltante: {
    fontSize: 12,
    color: 'rgba(255,255,255,0.4)',
    marginTop: 4,
  },
  modalDivider: {
    height: StyleSheet.hairlineWidth,
    backgroundColor: GLASS_BORDER,
    marginVertical: 14,
  },
  modalSectionTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: 'rgba(255,255,255,0.5)',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    marginBottom: 12,
  },
  modalDepositCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255,255,255,0.06)',
    borderRadius: 12,
    padding: 10,
    marginBottom: 8,
  },
  thumbnail: {
    width: 52,
    height: 52,
    borderRadius: 8,
  },
  previewImage: {
    width: '100%',
    height: 180,
    borderRadius: 12,
    marginBottom: 12,
  },
  imagePickerBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    borderWidth: 1,
    borderColor: GLASS_BORDER,
    borderRadius: 12,
    paddingVertical: 13,
    paddingHorizontal: 16,
    backgroundColor: 'rgba(255,255,255,0.06)',
    marginBottom: 10,
  },
  imagePickerText: {
    fontSize: 14,
    fontWeight: '500',
    color: 'rgba(255,255,255,0.62)',
  },
  modalInput: {
    backgroundColor: 'rgba(255,255,255,0.06)',
    borderWidth: 1,
    borderColor: GLASS_BORDER,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 14,
    color: '#FFFFFF',
    marginBottom: 8,
  },
  modalInputError: {
    borderColor: RED + '80',
  },
  errorText: {
    fontSize: 11,
    color: RED,
    marginBottom: 6,
    marginLeft: 4,
  },
  addBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: 'rgba(34,197,94,0.18)',
    borderWidth: 1,
    borderColor: GREEN + '50',
    borderRadius: 12,
    paddingVertical: 13,
    marginTop: 12,
  },
  addBtnText: {
    fontSize: 14,
    fontWeight: '600',
    color: GREEN,
  },
  modalActions: {
    flexDirection: 'row',
    gap: 12,
    paddingHorizontal: 22,
    paddingTop: 14,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: GLASS_BORDER,
  },
  modalCancelBtn: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 14,
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderWidth: 1,
    borderColor: GLASS_BORDER,
    alignItems: 'center',
  },
  modalCancelText: {
    fontSize: 14,
    fontWeight: '600',
    color: 'rgba(255,255,255,0.6)',
  },
  modalSubmitBtn: {
    flex: 2,
    paddingVertical: 14,
    borderRadius: 14,
    backgroundColor: GREEN,
    alignItems: 'center',
    shadowColor: GREEN,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 10,
    elevation: 6,
  },
  modalSubmitBtnDisabled: {
    backgroundColor: 'rgba(255,255,255,0.10)',
    shadowOpacity: 0,
    elevation: 0,
  },
  modalSubmitText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#FFFFFF',
    letterSpacing: 0.3,
  },
});
