import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  StyleSheet,
  FlatList,
  RefreshControl,
  TouchableOpacity,
  Alert,
  Modal,
  KeyboardAvoidingView,
  Platform,
  AppState,
  AppStateStatus,
  ImageBackground,
  TextInput,
  ActivityIndicator,
  Animated,
  Text,
  Dimensions,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { BlurView } from 'expo-blur';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import * as Haptics from 'expo-haptics';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useAuth } from '../contexts/AuthContext';
import { Operation } from '../types';
import axios from 'axios';
import { API_CONFIG } from '../constants/config';
import socketService from '../services/socketService';
import { formatCurrency, formatDateTime } from '../utils/formatters';
import { useNavigation, CommonActions } from '@react-navigation/native';
import { useBackground } from '../hooks/useBackground';

const { width: W } = Dimensions.get('window');

const GLASS_BG     = 'rgba(255,255,255,0.18)';
const GLASS_BORDER = 'rgba(255,255,255,0.15)';
const GREEN        = '#22c55e';
const OPERATION_TIMEOUT_MINUTES = 15;
const LOCAL_OPERATIONS_CACHE_KEY = '@qoricash_local_operations_cache';

// ─── Status config ────────────────────────────────────────────────────────────
const getStatusConfig = (status: string) => {
  switch (status) {
    case 'pendiente':
      return { color: '#fbbf24', icon: 'time-outline' as const,        label: 'Pendiente' };
    case 'en_proceso':
      return { color: '#60a5fa', icon: 'sync-outline' as const,        label: 'En Proceso' };
    case 'completado':
      return { color: '#22c55e', icon: 'checkmark-circle-outline' as const, label: 'Completada' };
    case 'cancelado':
      return { color: '#f87171', icon: 'close-circle-outline' as const, label: 'Cancelada' };
    case 'expirado':
      return { color: '#9ca3af', icon: 'alert-circle-outline' as const, label: 'Expirada' };
    default:
      return { color: '#9ca3af', icon: 'help-circle-outline' as const,  label: status };
  }
};

// ─── En-Proceso animations ────────────────────────────────────────────────────

/** Rotating sync icon — loops continuously */
const SpinningSync: React.FC<{ color: string; size: number }> = ({ color, size }) => {
  const rot = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    Animated.loop(
      Animated.timing(rot, { toValue: 1, duration: 1500, useNativeDriver: true })
    ).start();
  }, []);
  const rotate = rot.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '360deg'] });
  return (
    <Animated.View style={{ transform: [{ rotate }] }}>
      <Ionicons name="sync-outline" size={size} color={color} />
    </Animated.View>
  );
};

/** Badge that pulses its background & border glow */
const PulsingBadge: React.FC<{ color: string; children: React.ReactNode; baseStyle: any }> = ({ color, children, baseStyle }) => {
  const pulse = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: 900, useNativeDriver: false }),
        Animated.timing(pulse, { toValue: 0, duration: 900, useNativeDriver: false }),
      ])
    ).start();
  }, []);
  const bg     = pulse.interpolate({ inputRange: [0, 1], outputRange: [`${color}18`, `${color}35`] });
  const border = pulse.interpolate({ inputRange: [0, 1], outputRange: [`${color}40`, `${color}90`] });
  return (
    <Animated.View style={[baseStyle, { backgroundColor: bg, borderColor: border }]}>
      {children}
    </Animated.View>
  );
};

/** Traveling shimmer strip — signals activity at the card bottom */
const ShimmerBar: React.FC<{ color: string }> = ({ color }) => {
  const pos = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(pos, { toValue: 1, duration: 1700, useNativeDriver: true }),
        Animated.delay(300),
        Animated.timing(pos, { toValue: 0, duration: 0,    useNativeDriver: true }),
      ])
    ).start();
  }, []);
  const tx = pos.interpolate({ inputRange: [0, 1], outputRange: [-W, W * 1.2] });
  return (
    <View style={{ height: 3, overflow: 'hidden', backgroundColor: `${color}18` }}>
      <Animated.View
        style={{
          position: 'absolute', top: 0, bottom: 0,
          width: '38%',
          backgroundColor: `${color}70`,
          borderRadius: 2,
          transform: [{ translateX: tx }],
        }}
      />
    </View>
  );
};

// ─── Screen ───────────────────────────────────────────────────────────────────
export const HistoryScreen: React.FC<{ route?: any }> = ({ route }) => {
  const bg = useBackground();
  const { client } = useAuth();
  const insets     = useSafeAreaInsets();
  const navigation = useNavigation<any>();

  const [operations,         setOperations]         = useState<Operation[]>([]);
  const [filteredOperations, setFilteredOperations] = useState<Operation[]>([]);
  const [loading,            setLoading]            = useState(false);
  const [refreshing,         setRefreshing]         = useState(false);
  const [activeTab,          setActiveTab]          = useState<'pending'|'completed'>(
    route?.params?.initialTab || 'pending'
  );
  const [currentTime,           setCurrentTime]           = useState(new Date());
  const [cancelDialogVisible,   setCancelDialogVisible]   = useState(false);
  const [cancelReason,          setCancelReason]          = useState('');
  const [operationToCancel,     setOperationToCancel]     = useState<Operation|null>(null);
  const [canceling,             setCanceling]             = useState(false);

  // Tab pill animation
  const pillX = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.spring(pillX, {
      toValue: activeTab === 'pending' ? 0 : 1,
      tension: 200, friction: 15, useNativeDriver: false,
    }).start();
  }, [activeTab]);

  // ── Data hooks (unchanged) ────────────────────────────────────────────────
  useEffect(() => { if (client) fetchHistory(); }, [client]);

  useEffect(() => {
    const unsubscribe = navigation.addListener('focus', () => {
      if (client) fetchHistory();
    });
    return unsubscribe;
  }, [navigation, client]);

  useEffect(() => {
    const interval = setInterval(() => { if (client) fetchHistory(); }, 30000);
    return () => clearInterval(interval);
  }, [client]);

  useEffect(() => {
    const handle = () => { if (client) fetchHistory(); };
    socketService.on('operacion_completada', handle);
    socketService.on('operacion_actualizada', handle);
    socketService.on('operacion_cancelada', handle);
    socketService.on('nueva_operacion', handle);
    socketService.on('operation_expired', handle);
    return () => {
      socketService.off('operacion_completada', handle);
      socketService.off('operacion_actualizada', handle);
      socketService.off('operacion_cancelada', handle);
      socketService.off('nueva_operacion', handle);
      socketService.off('operation_expired', handle);
    };
  }, [client]);

  useEffect(() => {
    const handle = () => { if (client) fetchHistory(); };
    socketService.subscribeToEvent('refresh_operations_list', handle);
    return () => socketService.unsubscribeFromEvent('refresh_operations_list', handle);
  }, [client]);

  useEffect(() => {
    const sub = AppState.addEventListener('change', (next: AppStateStatus) => {
      if (next === 'active' && client) fetchHistory();
    });
    return () => sub.remove();
  }, [client]);

  useEffect(() => {
    const interval = setInterval(() => setCurrentTime(new Date()), 3000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    let filtered = operations;
    if (activeTab === 'pending') {
      filtered = operations.filter(op => op.status === 'pendiente' || op.status === 'en_proceso');
    } else {
      filtered = operations.filter(op => op.status === 'completado' || op.status === 'cancelado' || op.status === 'expirado');
    }
    setFilteredOperations(filtered);
  }, [operations, activeTab, currentTime]);

  // ── API (unchanged) ───────────────────────────────────────────────────────
  const fetchHistory = async () => {
    if (!client) return;
    try {
      setLoading(true);
      const response = await axios.get<{ success: boolean; operations: Operation[] }>(
        `${API_CONFIG.BASE_URL}/api/client/my-operations/${client.dni}`
      );
      if (response.data.success) {
        try { await AsyncStorage.removeItem(LOCAL_OPERATIONS_CACHE_KEY); } catch (_) {}
        setOperations(response.data.operations);
      }
    } catch (e) {
      console.error('❌ Error cargando historial:', e);
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = async () => { setRefreshing(true); await fetchHistory(); setRefreshing(false); };

  const handleOperationPress = (op: Operation) => {
    try {
      if (op.status === 'pendiente') {
        navigation.dispatch(CommonActions.navigate({ name: 'Transfer', params: { operation: op } }));
      } else if (op.status === 'en_proceso') {
        navigation.dispatch(CommonActions.navigate({ name: 'Receive', params: { operation: op } }));
      } else {
        navigation.dispatch(CommonActions.navigate({ name: 'OperationDetail', params: { operationId: op.id } }));
      }
    } catch (e) { console.error('❌ Error navegando:', e); }
  };

  const handleCancelOperation = (op: Operation) => {
    setOperationToCancel(op); setCancelReason(''); setCancelDialogVisible(true);
  };

  const handleConfirmCancel = async () => {
    if (!cancelReason.trim()) { Alert.alert('Error', 'Debes proporcionar un motivo'); return; }
    if (!operationToCancel) return;
    try {
      setCanceling(true);
      await axios.post(`${API_CONFIG.BASE_URL}/api/client/cancel-operation/${operationToCancel.id}`, {
        cancellation_reason: cancelReason.trim(),
        client_dni: client?.dni || '',
      });
      try {
        const cacheStr = await AsyncStorage.getItem(LOCAL_OPERATIONS_CACHE_KEY);
        const cache = cacheStr ? JSON.parse(cacheStr) : {};
        cache[operationToCancel.id] = { ...operationToCancel, status: 'cancelado', cancellation_reason: cancelReason.trim() };
        await AsyncStorage.setItem(LOCAL_OPERATIONS_CACHE_KEY, JSON.stringify(cache));
      } catch (_) {}
      setCancelDialogVisible(false); setCancelReason(''); setOperationToCancel(null);
      await fetchHistory();
      Alert.alert('Éxito', 'La operación ha sido cancelada');
    } catch (e: any) {
      Alert.alert('Error', e.response?.data?.message || 'No se pudo cancelar la operación');
    } finally { setCanceling(false); }
  };

  const handleCloseCancelDialog = () => {
    setCancelDialogVisible(false); setCancelReason(''); setOperationToCancel(null);
  };

  const calculateTimeRemaining = (createdAt: string) => {
    const exp = new Date(new Date(createdAt).getTime() + OPERATION_TIMEOUT_MINUTES * 60000);
    const diff = exp.getTime() - currentTime.getTime();
    if (diff <= 0) return { expired: true, minutes: 0, seconds: 0 };
    return { expired: false, minutes: Math.floor(diff / 60000), seconds: Math.floor((diff % 60000) / 1000) };
  };

  // ── Operation Card ────────────────────────────────────────────────────────
  const OperationCard: React.FC<{ operation: Operation }> = ({ operation }) => {
    const sc     = getStatusConfig(operation.status);
    const time   = operation.status === 'pendiente' ? calculateTimeRemaining(operation.created_at) : null;

    return (
      <TouchableOpacity
        style={s.card}
        onPress={() => handleOperationPress(operation)}
        activeOpacity={0.82}
      >
        {/* Header */}
        <View style={s.cardTop}>
          <View style={s.cardLeft}>
            <Text style={s.cardId}>{operation.operation_id}</Text>
            <Text style={s.cardAmount}>
              {operation.operation_type === 'Compra'
                ? formatCurrency(operation.amount_usd, 'USD')
                : formatCurrency(operation.amount_pen, 'PEN')}
            </Text>
            <Text style={s.cardMeta}>
              {operation.operation_type} · T.C. {operation.exchange_rate.toFixed(3)}
            </Text>
            <Text style={s.cardDate}>{formatDateTime(operation.created_at)}</Text>
          </View>

          <View style={s.cardRight}>
            {operation.status === 'en_proceso' ? (
              <PulsingBadge
                color={sc.color}
                baseStyle={[s.statusBadge, { borderWidth: 1 }]}
              >
                <SpinningSync color={sc.color} size={12} />
                <Text style={[s.statusText, { color: sc.color }]}>{sc.label}</Text>
              </PulsingBadge>
            ) : (
              <View style={[s.statusBadge, { backgroundColor: `${sc.color}1a`, borderColor: `${sc.color}40` }]}>
                <Ionicons name={sc.icon} size={12} color={sc.color} />
                <Text style={[s.statusText, { color: sc.color }]}>{sc.label}</Text>
              </View>
            )}
            {time && !time.expired && (
              <View style={s.countdown}>
                <Ionicons name="timer-outline" size={10} color="#f87171" />
                <Text style={s.countdownText}>{time.minutes}:{time.seconds.toString().padStart(2,'0')}</Text>
              </View>
            )}
          </View>
        </View>

        {/* Cancel */}
        {operation.status === 'pendiente' && (
          <>
            <View style={s.cardLine} />
            <TouchableOpacity
              style={s.cancelRow}
              onPress={() => handleCancelOperation(operation)}
              activeOpacity={0.7}
            >
              <Ionicons name="close-circle-outline" size={14} color="#f87171" />
              <Text style={s.cancelText}>Cancelar operación</Text>
            </TouchableOpacity>
          </>
        )}

        {/* Detail */}
        <View style={s.cardLine} />
        <View style={s.detailRow}>
          <Ionicons name="eye-outline" size={14} color={GREEN} />
          <Text style={s.detailText}>Ver detalles</Text>
          <Ionicons name="chevron-forward" size={13} color={GREEN} style={{ marginLeft: 'auto' }} />
        </View>

        {/* Activity shimmer — only for en_proceso */}
        {operation.status === 'en_proceso' && <ShimmerBar color={sc.color} />}
      </TouchableOpacity>
    );
  };

  const pendingCount   = operations.filter(op => op.status === 'pendiente' || op.status === 'en_proceso').length;
  const completedCount = operations.filter(op => op.status === 'completado' || op.status === 'cancelado' || op.status === 'expirado').length;

  return (
    <View style={s.root}>
      <ImageBackground source={bg} style={StyleSheet.absoluteFill} resizeMode="cover" />
      <View style={[StyleSheet.absoluteFill, s.overlay]} pointerEvents="none" />

      {/* ── Tab switcher ── */}
      <View style={[s.tabWrap, { paddingTop: insets.top + 14 }]}>
        <View style={s.tabBar}>
          <TouchableOpacity
            style={[s.tabBtn, activeTab === 'pending' && s.tabBtnActive]}
            onPress={() => { Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light); setActiveTab('pending'); }}
            activeOpacity={0.82}
          >
            <Text style={[s.tabLabel, activeTab === 'pending' && s.tabLabelActive]}>
              En Curso {pendingCount > 0 ? `(${pendingCount})` : ''}
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[s.tabBtn, activeTab === 'completed' && s.tabBtnActive]}
            onPress={() => { Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light); setActiveTab('completed'); }}
            activeOpacity={0.82}
          >
            <Text style={[s.tabLabel, activeTab === 'completed' && s.tabLabelActive]}>
              Finalizadas {completedCount > 0 ? `(${completedCount})` : ''}
            </Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* ── Loading ── */}
      {loading && operations.length === 0 ? (
        <View style={s.center}>
          <ActivityIndicator size="large" color={GREEN} />
          <Text style={s.loadText}>Cargando historial...</Text>
        </View>
      ) : (
        <FlatList
          data={filteredOperations}
          keyExtractor={item => item.id.toString()}
          renderItem={({ item }) => <OperationCard operation={item} />}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="rgba(255,255,255,0.5)" />
          }
          contentContainerStyle={[
            filteredOperations.length === 0 ? s.emptyList : s.listContent,
            { paddingBottom: insets.bottom + 88 },
          ]}
          ListEmptyComponent={
            <View style={s.emptyWrap}>
              <Ionicons
                name={activeTab === 'pending' ? 'time-outline' : 'receipt-outline'}
                size={56}
                color="rgba(255,255,255,0.22)"
              />
              <Text style={s.emptyTitle}>
                {activeTab === 'pending' ? 'Sin operaciones en curso' : 'Sin historial'}
              </Text>
              <Text style={s.emptySubtitle}>
                {activeTab === 'pending'
                  ? 'Inicia una nueva operación desde el inicio'
                  : 'Aquí aparecerán tus operaciones completadas y canceladas'}
              </Text>
            </View>
          }
        />
      )}

      {/* ── Cancel Modal ── */}
      <Modal visible={cancelDialogVisible} transparent animationType="fade" onRequestClose={handleCloseCancelDialog}>
        <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
          <TouchableOpacity style={s.modalBackdrop} activeOpacity={1} onPress={handleCloseCancelDialog}>
            <TouchableOpacity activeOpacity={1} style={s.modalBox} onPress={e => e.stopPropagation()}>
              <BlurView intensity={88} tint="dark" style={StyleSheet.absoluteFill} />
              <View style={s.modalBorder} />

              <Ionicons name="alert-circle-outline" size={40} color="#f87171" style={{ marginBottom: 14 }} />
              <Text style={s.modalTitle}>Cancelar Operación</Text>
              <Text style={s.modalSub}>Indica el motivo de la cancelación</Text>

              <TextInput
                style={s.modalInput}
                placeholder="Escribe el motivo aquí..."
                placeholderTextColor="rgba(255,255,255,0.3)"
                value={cancelReason}
                onChangeText={setCancelReason}
                multiline
                numberOfLines={4}
                editable={!canceling}
              />

              <View style={s.modalActions}>
                <TouchableOpacity style={s.modalBtnSecondary} onPress={handleCloseCancelDialog} disabled={canceling}>
                  <Text style={s.modalBtnSecondaryText}>Volver</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[s.modalBtnDanger, (!cancelReason.trim() || canceling) && s.modalBtnDisabled]}
                  onPress={handleConfirmCancel}
                  disabled={canceling || !cancelReason.trim()}
                >
                  {canceling
                    ? <ActivityIndicator color="#fff" size="small" />
                    : <Text style={s.modalBtnDangerText}>Cancelar</Text>
                  }
                </TouchableOpacity>
              </View>
            </TouchableOpacity>
          </TouchableOpacity>
        </KeyboardAvoidingView>
      </Modal>
    </View>
  );
};

// ─── Styles ───────────────────────────────────────────────────────────────────
const s = StyleSheet.create({
  root: { flex: 1 },
  overlay: { backgroundColor: 'transparent' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: 12 },
  loadText: { color: 'rgba(255,255,255,0.5)', fontSize: 14 },

  // ── Tabs ──
  tabWrap: {
    paddingHorizontal: 20,
    paddingBottom: 14,
  },
  tabBar: {
    flexDirection: 'row',
    backgroundColor: GLASS_BG,
    borderWidth: 1,
    borderColor: GLASS_BORDER,
    borderRadius: 16,
    padding: 4,
    gap: 4,
  },
  tabBtn: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 12,
    alignItems: 'center',
  },
  tabBtnActive: {
    backgroundColor: 'rgba(34,197,94,0.15)',
    borderWidth: 1,
    borderColor: 'rgba(34,197,94,0.3)',
  },
  tabLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: 'rgba(255,255,255,0.38)',
    letterSpacing: 0.1,
  },
  tabLabelActive: {
    color: GREEN,
    fontWeight: '700',
  },

  // ── List ──
  listContent: {
    paddingHorizontal: 20,
    paddingTop: 4,
  },
  emptyList: {
    flexGrow: 1,
  },
  emptyWrap: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 12,
    paddingTop: 80,
    paddingHorizontal: 40,
  },
  emptyTitle: {
    fontSize: 17,
    fontWeight: '700',
    color: 'rgba(255,255,255,0.6)',
    textAlign: 'center',
  },
  emptySubtitle: {
    fontSize: 13,
    color: 'rgba(255,255,255,0.35)',
    textAlign: 'center',
    lineHeight: 20,
  },

  // ── Card ──
  card: {
    backgroundColor: 'rgba(255,255,255,0.15)',
    borderWidth: 1,
    borderColor: GLASS_BORDER,
    borderRadius: 20,
    marginBottom: 12,
    overflow: 'hidden',
  },
  cardTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    padding: 16,
  },
  cardLeft: { flex: 1, paddingRight: 12 },
  cardId: { fontSize: 10.5, color: 'rgba(255,255,255,0.38)', fontWeight: '600', letterSpacing: 0.4, marginBottom: 4 },
  cardAmount: { fontSize: 20, fontWeight: '800', color: '#fff', letterSpacing: -0.3, marginBottom: 3 },
  cardMeta: { fontSize: 11.5, color: 'rgba(255,255,255,0.5)', marginBottom: 2 },
  cardDate: { fontSize: 10.5, color: 'rgba(255,255,255,0.3)', letterSpacing: 0.1 },
  cardRight: { alignItems: 'flex-end', gap: 6 },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 20,
    borderWidth: 1,
  },
  statusText: { fontSize: 11, fontWeight: '700', letterSpacing: 0.1 },
  countdown: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
  },
  countdownText: { fontSize: 10, color: '#f87171', fontWeight: '700' },

  cardLine: { height: StyleSheet.hairlineWidth, backgroundColor: GLASS_BORDER, marginHorizontal: 16 },

  cancelRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 12,
    paddingHorizontal: 16,
  },
  cancelText: { fontSize: 12.5, fontWeight: '600', color: '#f87171' },

  detailRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
    paddingVertical: 12,
    paddingHorizontal: 16,
  },
  detailText: { fontSize: 13, fontWeight: '600', color: GREEN },

  // ── Modal ──
  modalBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.6)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 28,
  },
  modalBox: {
    width: '100%',
    borderRadius: 24,
    overflow: 'hidden',
    alignItems: 'center',
    paddingTop: 36,
    paddingBottom: 28,
    paddingHorizontal: 24,
  },
  modalBorder: {
    position: 'absolute',
    top: 0, left: 0, right: 0, bottom: 0,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: GLASS_BORDER,
  },
  modalTitle: { fontSize: 18, fontWeight: '800', color: '#fff', textAlign: 'center', marginBottom: 6 },
  modalSub: { fontSize: 13, color: 'rgba(255,255,255,0.45)', textAlign: 'center', marginBottom: 20 },
  modalInput: {
    width: '100%',
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderWidth: 1,
    borderColor: GLASS_BORDER,
    borderRadius: 14,
    padding: 14,
    color: '#fff',
    fontSize: 14,
    minHeight: 100,
    textAlignVertical: 'top',
    marginBottom: 20,
  },
  modalActions: { flexDirection: 'row', gap: 10, width: '100%' },
  modalBtnSecondary: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 14,
    backgroundColor: GLASS_BG,
    borderWidth: 1,
    borderColor: GLASS_BORDER,
    alignItems: 'center',
  },
  modalBtnSecondaryText: { fontSize: 14, fontWeight: '600', color: 'rgba(255,255,255,0.7)' },
  modalBtnDanger: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 14,
    backgroundColor: 'rgba(248,113,113,0.18)',
    borderWidth: 1,
    borderColor: 'rgba(248,113,113,0.35)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  modalBtnDangerText: { fontSize: 14, fontWeight: '700', color: '#f87171' },
  modalBtnDisabled: { opacity: 0.4 },
});
