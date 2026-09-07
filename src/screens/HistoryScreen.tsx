import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
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
import { CancelOperationModal } from '../components/CancelOperationModal';
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
      return { color: '#16a34a', icon: 'checkmark-circle-outline' as const, label: 'Completada' };
    case 'cancelado':
      return { color: '#dc2626', icon: 'close-circle-outline' as const, label: 'Cancelada' };
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
  const [loading,            setLoading]            = useState(false);
  const [refreshing,         setRefreshing]         = useState(false);
  const [activeTab,          setActiveTab]          = useState<'pending'|'completed'>(
    route?.params?.initialTab || 'pending'
  );

  useEffect(() => {
    if (route?.params?.initialTab) {
      const tab = route.params.initialTab as 'pending' | 'completed';
      setActiveTab(tab);
      slideAnim.setValue(tab === 'pending' ? 0 : tabWidth);
    }
  }, [route?.params?.initialTab]);
  const [currentTime,           setCurrentTime]           = useState(new Date());
  const [cancelDialogVisible,   setCancelDialogVisible]   = useState(false);
  const [cancelReason,          setCancelReason]          = useState('');
  const [operationToCancel,     setOperationToCancel]     = useState<Operation|null>(null);
  const [canceling,             setCanceling]             = useState(false);
  const [searchQuery,           setSearchQuery]           = useState('');
  const [dateFilter,            setDateFilter]            = useState<'all'|'7d'|'30d'|'90d'>('all');

  // Tab animations
  const [tabWidth, setTabWidth] = useState(0);
  const slideAnim = useRef(new Animated.Value(0)).current;
  const fadeAnim  = useRef(new Animated.Value(1)).current;

  const switchTab = useCallback((tab: 'pending' | 'completed') => {
    if (tab === activeTab) return;
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    // Slide pill
    Animated.spring(slideAnim, {
      toValue: tab === 'pending' ? 0 : tabWidth,
      useNativeDriver: true,
      tension: 320,
      friction: 22,
    }).start();
    // Fade content out → switch → fade in
    Animated.timing(fadeAnim, { toValue: 0.4, duration: 90, useNativeDriver: true }).start(() => {
      setActiveTab(tab);
      Animated.timing(fadeAnim, { toValue: 1, duration: 160, useNativeDriver: true }).start();
    });
  }, [activeTab, tabWidth, slideAnim, fadeAnim]);

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

  const filteredOperations = useMemo(() => {
    let filtered = operations;

    if (activeTab === 'pending') {
      return filtered.filter(op => op.status === 'pendiente' || op.status === 'en_proceso');
    }

    filtered = filtered.filter(op => op.status === 'completado' || op.status === 'cancelado' || op.status === 'expirado');

    if (dateFilter !== 'all') {
      const days = dateFilter === '7d' ? 7 : dateFilter === '30d' ? 30 : 90;
      const cutoff = new Date();
      cutoff.setDate(cutoff.getDate() - days);
      filtered = filtered.filter(op => new Date(op.created_at) >= cutoff);
    }

    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase();
      filtered = filtered.filter(op =>
        op.operation_id?.toLowerCase().includes(q) ||
        String(op.amount_usd).includes(q) ||
        String(op.amount_pen).includes(q) ||
        formatCurrency(op.amount_usd, 'USD').toLowerCase().includes(q) ||
        formatCurrency(op.amount_pen, 'PEN').toLowerCase().includes(q)
      );
    }

    return filtered;
  }, [operations, activeTab, searchQuery, dateFilter]);

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
    const sc      = getStatusConfig(operation.status);
    const time    = operation.status === 'pendiente' ? calculateTimeRemaining(operation.created_at) : null;
    const isDark  = operation.status === 'pendiente' || operation.status === 'en_proceso';

    return (
      <TouchableOpacity
        style={[s.card, isDark && { backgroundColor: '#0D1117', borderColor: '#0D1117' }]}
        onPress={() => handleOperationPress(operation)}
        activeOpacity={0.82}
      >
        {isDark ? (
          /* ── DARK CARD (pendiente / en_proceso) ── */
          <>
            <View style={{ padding: 22, gap: 18 }}>

              {/* Fila 1: ID + badge */}
              <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
                <Text style={{ fontSize: 11, fontWeight: '600', color: '#fff', letterSpacing: 0.6 }}>
                  {operation.operation_id}
                </Text>
                {operation.status === 'en_proceso' ? (
                  <PulsingBadge color={sc.color} baseStyle={[s.statusBadge, { borderWidth: 1 }]}>
                    <SpinningSync color={sc.color} size={12} />
                    <Text style={[s.statusText, { color: sc.color }]}>{sc.label}</Text>
                  </PulsingBadge>
                ) : (
                  <View style={[s.statusBadge, { backgroundColor: `${sc.color}1a`, borderColor: `${sc.color}40` }]}>
                    <Ionicons name={sc.icon} size={12} color={sc.color} />
                    <Text style={[s.statusText, { color: sc.color }]}>{sc.label}</Text>
                  </View>
                )}
              </View>

              {/* Fila 2: tipo de operación */}
              <Text style={{ fontSize: 11, fontWeight: '500', color: '#fff', textTransform: 'uppercase', letterSpacing: 1 }}>
                {operation.operation_type === 'Compra' ? '🇺🇸 Cambio de dólares a soles' : '🇵🇪 Cambio de soles a dólares'}
              </Text>

              {/* Fila 3: importes */}
              <View style={{ gap: 6 }}>
                <Text style={{ fontSize: 42, fontWeight: '900', color: '#fff', letterSpacing: -1.5 }} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.6}>
                  {operation.operation_type === 'Compra'
                    ? formatCurrency(operation.amount_usd, 'USD')
                    : formatCurrency(operation.amount_pen, 'PEN')}
                </Text>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                  <Ionicons name="arrow-forward" size={14} color={GREEN} />
                  <Text style={{ fontSize: 22, fontWeight: '700', color: GREEN }}>
                    {operation.operation_type === 'Compra'
                      ? formatCurrency(operation.amount_pen, 'PEN')
                      : formatCurrency(operation.amount_usd, 'USD')}
                  </Text>
                </View>
              </View>

              {/* Fila 4: TC + fecha + countdown */}
              <View style={{ flexDirection: 'row', alignItems: 'flex-end', justifyContent: 'space-between' }}>
                <View style={{ gap: 4 }}>
                  <Text style={{ fontSize: 12, color: '#fff', fontWeight: '500' }}>
                    T.C. {operation.exchange_rate.toFixed(4)}
                  </Text>
                  <Text style={{ fontSize: 11, color: '#fff' }}>
                    {formatDateTime(operation.created_at)}
                  </Text>
                </View>
                {time && !time.expired && (
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: 'rgba(248,113,113,0.15)', borderRadius: 12, paddingHorizontal: 12, paddingVertical: 7 }}>
                    <Ionicons name="timer-outline" size={15} color="#f87171" />
                    <Text style={{ fontSize: 18, fontWeight: '800', color: '#f87171' }}>
                      {time.minutes}:{time.seconds.toString().padStart(2, '0')}
                    </Text>
                  </View>
                )}
              </View>
            </View>

            {/* Acciones */}
            <View style={{ height: 1, backgroundColor: 'rgba(255,255,255,0.08)', marginHorizontal: 22 }} />
            {operation.status === 'pendiente' ? (
              <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                <TouchableOpacity
                  style={[s.cancelRow, { flex: 1, justifyContent: 'flex-start' }]}
                  onPress={() => handleCancelOperation(operation)}
                  activeOpacity={0.7}
                >
                  <Ionicons name="close-circle-outline" size={15} color="#f87171" />
                  <Text style={[s.cancelText, { fontSize: 13 }]}>Anular operación</Text>
                </TouchableOpacity>
                <View style={{ width: 1, height: 40, backgroundColor: 'rgba(255,255,255,0.15)' }} />
                <View style={[s.detailRow, { flex: 1, justifyContent: 'flex-end' }]}>
                  <Ionicons name="eye-outline" size={15} color={GREEN} />
                  <Text style={[s.detailText, { fontSize: 13 }]}>Ver detalles</Text>
                  <Ionicons name="chevron-forward" size={14} color={GREEN} />
                </View>
              </View>
            ) : (
              <View style={s.detailRow}>
                <Ionicons name="eye-outline" size={15} color={GREEN} />
                <Text style={[s.detailText, { fontSize: 13 }]}>Ver detalles</Text>
                <Ionicons name="chevron-forward" size={14} color={GREEN} style={{ marginLeft: 'auto' }} />
              </View>
            )}
            {operation.status === 'en_proceso' && <ShimmerBar color={sc.color} />}
          </>
        ) : (
          /* ── LIGHT CARD (completado / cancelado / expirado) ── */
          <>
            <View style={s.cardTop}>
              <View style={s.cardLeft}>
                <Text style={s.cardId}>{operation.operation_id}</Text>
                <Text style={s.cardAmount}>
                  {operation.operation_type === 'Compra'
                    ? formatCurrency(operation.amount_usd, 'USD')
                    : formatCurrency(operation.amount_pen, 'PEN')}
                </Text>
                <Text style={s.cardMeta}>
                  {operation.operation_type} · T.C. {operation.exchange_rate.toFixed(4)}
                </Text>
                <Text style={s.cardDate}>{formatDateTime(operation.created_at)}</Text>
              </View>
              <View style={s.cardRight}>
                <View style={[
                  s.statusBadge,
                  (operation.status === 'completado' || operation.status === 'cancelado')
                    ? { backgroundColor: sc.color, borderColor: sc.color }
                    : { backgroundColor: `${sc.color}1a`, borderColor: `${sc.color}40` },
                ]}>
                  <Ionicons
                    name={sc.icon}
                    size={12}
                    color={(operation.status === 'completado' || operation.status === 'cancelado') ? '#fff' : sc.color}
                  />
                  <Text style={[
                    s.statusText,
                    { color: (operation.status === 'completado' || operation.status === 'cancelado') ? '#fff' : sc.color },
                  ]}>{sc.label}</Text>
                </View>
              </View>
            </View>
            <View style={s.cardLine} />
            <View style={s.detailRow}>
              <Ionicons name="eye-outline" size={14} color={GREEN} />
              <Text style={s.detailText}>Ver detalles</Text>
              <Ionicons name="chevron-forward" size={13} color={GREEN} style={{ marginLeft: 'auto' }} />
            </View>
          </>
        )}
      </TouchableOpacity>
    );
  };

  const pendingCount   = operations.filter(op => op.status === 'pendiente' || op.status === 'en_proceso').length;
  const completedCount = operations.filter(op => op.status === 'completado' || op.status === 'cancelado' || op.status === 'expirado').length;

  return (
    <View style={s.root}>
      <View style={[StyleSheet.absoluteFill, { backgroundColor: '#F5F7FA' }]} pointerEvents="none" />

      {/* ── Tab switcher ── */}
      <View style={[s.tabWrap, { paddingTop: insets.top + 14 }]}>
        <View
          style={s.tabBar}
          onLayout={e => {
            const w = e.nativeEvent.layout.width / 2;
            setTabWidth(w);
            slideAnim.setValue(activeTab === 'pending' ? 0 : w);
          }}
        >
          {/* Sliding pill */}
          <Animated.View
            style={[s.tabPill, { width: tabWidth, transform: [{ translateX: slideAnim }] }]}
            pointerEvents="none"
          />

          <TouchableOpacity style={s.tabBtn} onPress={() => switchTab('pending')} activeOpacity={0.82}>
            <Text style={[s.tabLabel, activeTab === 'pending' && s.tabLabelActive]}>
              En Curso{pendingCount > 0 ? ` (${pendingCount})` : ''}
            </Text>
          </TouchableOpacity>

          <TouchableOpacity style={s.tabBtn} onPress={() => switchTab('completed')} activeOpacity={0.82}>
            <Text style={[s.tabLabel, activeTab === 'completed' && s.tabLabelActive]}>
              Finalizadas{completedCount > 0 ? ` (${completedCount})` : ''}
            </Text>
          </TouchableOpacity>
        </View>
      </View>

      <Animated.View style={{ flex: 1, opacity: fadeAnim }}>
      {/* ── Búsqueda + Filtros (solo Finalizadas) ── */}
      {activeTab === 'completed' && (
        <View style={s.searchWrap}>
          {/* Search input */}
          <View style={s.searchBox}>
            <Ionicons name="search-outline" size={16} color="#9CA3AF" />
            <TextInput
              style={s.searchInput}
              placeholder="Buscar por ID, importe, T.C., etc..."
              placeholderTextColor="#C4C9D4"
              value={searchQuery}
              onChangeText={setSearchQuery}
              returnKeyType="search"
              clearButtonMode="while-editing"
              autoCorrect={false}
              autoCapitalize="none"
            />
            {searchQuery.length > 0 && (
              <TouchableOpacity onPress={() => setSearchQuery('')} activeOpacity={0.7}>
                <Ionicons name="close-circle" size={16} color="#C4C9D4" />
              </TouchableOpacity>
            )}
          </View>

          {/* Date chips */}
          <View style={s.dateChips}>
            {(['all', '7d', '30d', '90d'] as const).map(f => (
              <TouchableOpacity
                key={f}
                style={[s.dateChip, dateFilter === f && s.dateChipActive]}
                onPress={() => setDateFilter(f)}
                activeOpacity={0.75}
              >
                <Text style={[s.dateChipText, dateFilter === f && s.dateChipTextActive]}>
                  {f === 'all' ? 'Todo' : f === '7d' ? '7 días' : f === '30d' ? '30 días' : '3 meses'}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      )}

      {/* ── Loading ── */}
      {loading && operations.length === 0 ? (
        <View style={s.center}>
          <ActivityIndicator size="large" color="#0D1117" />
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
                {activeTab === 'pending'
                  ? 'Sin operaciones en curso'
                  : (searchQuery || dateFilter !== 'all') ? 'Sin resultados' : 'Sin historial'}
              </Text>
              <Text style={s.emptySubtitle}>
                {activeTab === 'pending'
                  ? 'Inicia una nueva operación desde el inicio'
                  : (searchQuery || dateFilter !== 'all')
                    ? 'Prueba con otro término o amplía el rango de fechas'
                    : 'Aquí aparecerán tus operaciones completadas y canceladas'}
              </Text>
            </View>
          }
        />
      )}

      </Animated.View>

      {/* ── Cancel Modal ── */}
      <CancelOperationModal
        visible={cancelDialogVisible}
        onClose={handleCloseCancelDialog}
        operationId={operationToCancel?.id ?? 0}
        operationCode={operationToCancel?.operation_id ?? ''}
        clientDni={client?.dni ?? ''}
        onSuccess={() => {
          setCancelDialogVisible(false);
          setOperationToCancel(null);
          fetchHistory();
        }}
      />
    </View>
  );
};

// ─── Styles ───────────────────────────────────────────────────────────────────
const s = StyleSheet.create({
  root: { flex: 1 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: 12 },
  loadText: { color: '#6B7280', fontSize: 14 },

  // ── Search ──
  searchWrap: {
    paddingHorizontal: 20,
    paddingBottom: 12,
    gap: 10,
  },
  searchBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: 'rgba(0,0,0,0.07)',
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 10,
    gap: 10,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 4,
    elevation: 1,
  },
  searchInput: {
    flex: 1,
    fontSize: 14,
    color: '#0D1117',
    padding: 0,
  },
  dateChips: {
    flexDirection: 'row',
    gap: 8,
  },
  dateChip: {
    paddingHorizontal: 14,
    paddingVertical: 7,
    borderRadius: 20,
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: 'rgba(0,0,0,0.08)',
  },
  dateChipActive: {
    backgroundColor: '#0D1117',
    borderColor: '#0D1117',
  },
  dateChipText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#9CA3AF',
  },
  dateChipTextActive: {
    color: '#FFFFFF',
  },

  // ── Tabs ──
  tabWrap: {
    paddingHorizontal: 20,
    paddingBottom: 14,
  },
  tabBar: {
    flexDirection: 'row',
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: 'rgba(0,0,0,0.07)',
    borderRadius: 16,
    padding: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
    position: 'relative',
    overflow: 'hidden',
  },
  tabPill: {
    position: 'absolute',
    top: 4,
    bottom: 4,
    left: 4,
    backgroundColor: '#0D1117',
    borderRadius: 12,
  },
  tabBtn: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 12,
    alignItems: 'center',
    zIndex: 1,
  },
  tabLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: '#9CA3AF',
    letterSpacing: 0.1,
  },
  tabLabelActive: {
    color: '#FFFFFF',
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
    color: '#374151',
    textAlign: 'center',
  },
  emptySubtitle: {
    fontSize: 13,
    color: '#9CA3AF',
    textAlign: 'center',
    lineHeight: 20,
  },

  // ── Card ──
  card: {
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: 'rgba(0,0,0,0.06)',
    borderRadius: 20,
    marginBottom: 12,
    overflow: 'hidden',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 10,
    elevation: 3,
  },
  cardTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    padding: 16,
  },
  cardLeft: { flex: 1, paddingRight: 12 },
  cardId: { fontSize: 10.5, color: '#9CA3AF', fontWeight: '600', letterSpacing: 0.4, marginBottom: 4 },
  cardAmount: { fontSize: 20, fontWeight: '800', color: '#0D1117', letterSpacing: -0.3, marginBottom: 3 },
  cardMeta: { fontSize: 11.5, color: '#6B7280', marginBottom: 2 },
  cardDate: { fontSize: 10.5, color: '#9CA3AF', letterSpacing: 0.1 },
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

  cardLine: { height: StyleSheet.hairlineWidth, backgroundColor: 'rgba(0,0,0,0.06)', marginHorizontal: 16 },

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
    alignItems: 'stretch',
    backgroundColor: '#fff',
  },
  modalBorder: {
    position: 'absolute',
    top: 0, left: 0, right: 0, bottom: 0,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: 'rgba(0,0,0,0.08)',
  },
  modalTitle: { fontSize: 18, fontWeight: '800', color: '#0D1117', textAlign: 'center', marginBottom: 6 },
  modalSub: { fontSize: 13, color: '#6B7280', textAlign: 'center', marginBottom: 20 },
  modalInput: {
    width: '100%',
    backgroundColor: '#F9FAFB',
    borderWidth: 1,
    borderColor: 'rgba(0,0,0,0.08)',
    borderRadius: 14,
    padding: 14,
    color: '#0D1117',
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
    backgroundColor: '#F3F4F6',
    borderWidth: 1,
    borderColor: 'rgba(0,0,0,0.07)',
    alignItems: 'center',
  },
  modalBtnSecondaryText: { fontSize: 14, fontWeight: '600', color: '#374151' },
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
