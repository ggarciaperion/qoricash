import React, { useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Animated,
  Easing,
  TouchableOpacity,
  Alert,
  Image,
  Linking,
  ImageBackground,
  Platform,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { MotiView } from 'moti';
import { Ionicons } from '@expo/vector-icons';
import { CommonActions } from '@react-navigation/native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Operation, BankAccount } from '../types';
import { formatCurrency, formatDateTime } from '../utils/formatters';
import { STORAGE_KEYS } from '../constants/config';
import socketService from '../services/socket';

const BANK_LOGOS: Record<string, any> = {
  'BCP':        require('../../assets/banks/bcp.png'),
  'INTERBANK':  require('../../assets/banks/interbank.png'),
  'BANBIF':     require('../../assets/banks/banbif.png'),
  'BBVA':       require('../../assets/banks/bbva.png'),
  'Scotiabank': require('../../assets/banks/scotiabank.png'),
  'SCOTIABANK': require('../../assets/banks/scotiabank.png'),
  'PICHINCHA':  require('../../assets/banks/pichincha.png'),
};

const GREEN  = '#22c55e';
const GLASS  = 'rgba(255,255,255,0.08)';
const BORDER = 'rgba(255,255,255,0.14)';
const DIM    = 'rgba(255,255,255,0.5)';

interface ReceiveScreenProps {
  navigation: any;
  route: {
    params: {
      operation: Operation;
    };
  };
}

export const ReceiveScreen: React.FC<ReceiveScreenProps> = ({ navigation, route }) => {
  const { operation }  = route.params;
  const insets         = useSafeAreaInsets();

  const rotateAnim     = useRef(new Animated.Value(0)).current;
  const clockOpacity   = useRef(new Animated.Value(1)).current;
  const checkScale     = useRef(new Animated.Value(0)).current;
  const checkOpacity   = useRef(new Animated.Value(0)).current;

  // ── Animación reloj ↔ check ───────────────────────────────────────────────
  useEffect(() => {
    navigation.setOptions({ headerLeft: () => null, gestureEnabled: false });

    const clockLoop = Animated.loop(
      Animated.timing(rotateAnim, { toValue: 1, duration: 800, easing: Easing.linear, useNativeDriver: true })
    );

    const runCycle = () => {
      rotateAnim.setValue(0);
      clockOpacity.setValue(1);
      checkScale.setValue(0);
      checkOpacity.setValue(0);
      clockLoop.start();

      setTimeout(() => {
        clockLoop.stop();
        Animated.timing(clockOpacity, { toValue: 0, duration: 250, useNativeDriver: true }).start(() => {
          Animated.parallel([
            Animated.spring(checkScale,    { toValue: 1, useNativeDriver: true }),
            Animated.timing(checkOpacity,  { toValue: 1, duration: 200, useNativeDriver: true }),
          ]).start(() => {
            setTimeout(() => {
              Animated.parallel([
                Animated.timing(checkOpacity, { toValue: 0, duration: 250, useNativeDriver: true }),
                Animated.timing(checkScale,   { toValue: 0, duration: 250, useNativeDriver: true }),
              ]).start(() => runCycle());
            }, 1200);
          });
        });
      }, 2400);
    };

    runCycle();
  }, [navigation]);

  // ── Socket.IO ─────────────────────────────────────────────────────────────
  useEffect(() => {
    socketService.connect();

    // Unirse al room del cliente para recibir notificaciones en tiempo real.
    // Se emite también en el evento 'connect' para cubrir reconexiones.
    let clientDni: string | null = null;

    const joinRoom = () => {
      if (clientDni) {
        socketService.emit('join_client_room', { dni: clientDni });
        console.log(`✅ [ReceiveScreen] join_client_room → DNI: ${clientDni}`);
      }
    };

    AsyncStorage.getItem(STORAGE_KEYS.CLIENT_DATA).then(raw => {
      if (!raw) return;
      try {
        const c = JSON.parse(raw);
        clientDni = c.dni || c.ruc || null;
        joinRoom();
      } catch {}
    });

    // También cuando el socket (re)conecte, volver a unirse al room
    socketService.on('connect', joinRoom);

    const redirectToHistory = () => {
      navigation.dispatch(
        CommonActions.reset({
          index: 0,
          routes: [{
            name: 'Tabs',
            state: {
              routes: [{ name: 'HomeTab' }, { name: 'HistoryTab' }, { name: 'ProfileTab' }],
              index: 1,
            },
          }],
        })
      );
    };

    const handleOperationUpdated = (data: any) => {
      if (data.id === operation.id || data.operation_id === operation.operation_id) {
        if (data.status === 'completado') {
          Alert.alert(
            '✅ Operación Completada',
            'Tu operación ha sido completada exitosamente. Tu pago ha sido procesado.',
            [{ text: 'Ver Historial', onPress: redirectToHistory }],
            { cancelable: false, onDismiss: redirectToHistory }
          );
        }
      }
    };

    const handleOperationCompleted = (data: any) => {
      if (data.operation_id === operation.operation_id) {
        Alert.alert(
          '✅ Operación Completada',
          `Tu operación ${data.operation_id} ha sido completada exitosamente. Tu pago ha sido procesado.`,
          [{ text: 'Ver Historial', onPress: redirectToHistory }],
          { cancelable: false, onDismiss: redirectToHistory }
        );
      }
    };

    const handleCanceledByAdmin = (data: any) => {
      if (data.operation_id === operation.operation_id) {
        Alert.alert(
          '❌ Operación Cancelada',
          `Tu operación ${data.operation_id} fue cancelada por el equipo Qoricash.\n\n` +
          `Motivo: ${data.reason || 'Sin motivo especificado'}\n\n` +
          `Si tienes alguna duda, contáctanos por WhatsApp.`,
          [{ text: 'Entendido', onPress: redirectToHistory }],
          { cancelable: false }
        );
      }
    };

    socketService.on('operacion_actualizada',   handleOperationUpdated);
    socketService.on('operacion_completada',    handleOperationCompleted);
    socketService.on('operacion_cancelada_admin', handleCanceledByAdmin);

    return () => {
      socketService.off('connect',                  joinRoom);
      socketService.off('operacion_actualizada',    handleOperationUpdated);
      socketService.off('operacion_completada',     handleOperationCompleted);
      socketService.off('operacion_cancelada_admin', handleCanceledByAdmin);
    };
  }, [operation.id, operation.operation_id, navigation]);

  const spin = rotateAnim.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '360deg'] });

  const handleAccept = () => {
    navigation.dispatch(
      CommonActions.reset({
        index: 0,
        routes: [{
          name: 'Tabs',
          state: {
            routes: [{ name: 'HomeTab' }, { name: 'HistoryTab' }, { name: 'ProfileTab' }],
            index: 1,
          },
        }],
      })
    );
  };

  // helpers
  const clientName = (() => {
    const full  = ((operation as any).client_name || '').trim();
    const parts = full.split(/\s+/);
    if (parts.length <= 2) return full || 'Por definir';
    return `${parts[0]} ${parts[Math.max(1, parts.length - 2)]}`;
  })();

  const accountInfo = (() => {
    const accounts: BankAccount[] = (operation as any).client_bank_accounts || [];
    const acc   = accounts.find((a: BankAccount) => a.account_number === operation.destination_account);
    const tipo  = acc?.account_type || 'Por definir';
    const moneda = acc?.currency
      ? (acc.currency === 'S/' ? 'Soles (S/)' : 'Dólares ($)')
      : (operation.operation_type === 'Compra' ? 'Soles (S/)' : 'Dólares ($)');
    return `${tipo} · ${moneda}`;
  })();

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <View style={s.root}>
      <ImageBackground
        source={require('../../assets/cd.png')}
        style={StyleSheet.absoluteFill}
        resizeMode="cover"
      />
      <View style={[StyleSheet.absoluteFill, s.overlay]} />

      {/* ── Header ── */}
      <View style={[s.header, { paddingTop: insets.top + 10 }]}>
        <View style={{ width: 40 }} />
        <View style={s.headerCenter}>
          <Image
            source={require('../../assets/vv.png')}
            style={s.headerLogo}
            resizeMode="contain"
          />
        </View>
        <View style={{ width: 40 }} />
      </View>

      <ScrollView
        style={s.scroll}
        contentContainerStyle={{ paddingBottom: insets.bottom + 90 }}
        showsVerticalScrollIndicator={false}
      >

        {/* ── Timeline Stepper ── */}
        <MotiView
          from={{ opacity: 0, translateY: -10 }}
          animate={{ opacity: 1, translateY: 0 }}
          transition={{ type: 'timing', duration: 400, delay: 0 }}
        >
          <View style={s.timeline}>
            {/* Paso 1 — completado */}
            <View style={s.step}>
              <View style={[s.stepDot, s.stepDotDone]}>
                <Ionicons name="checkmark" size={13} color="#fff" />
              </View>
              <Text style={[s.stepLabel, s.stepLabelDone]}>Cuentas</Text>
            </View>
            <View style={[s.stepLine, s.stepLineDone]} />

            {/* Paso 2 — completado */}
            <View style={s.step}>
              <View style={[s.stepDot, s.stepDotDone]}>
                <Ionicons name="checkmark" size={13} color="#fff" />
              </View>
              <Text style={[s.stepLabel, s.stepLabelDone]}>Transfiere</Text>
            </View>
            <View style={[s.stepLine, s.stepLineDone]} />

            {/* Paso 3 — activo */}
            <View style={s.step}>
              <View style={[s.stepDot, s.stepDotActive]}>
                <Ionicons name="gift-outline" size={13} color="#fff" />
              </View>
              <Text style={[s.stepLabel, s.stepLabelActive]}>Recibe</Text>
            </View>
          </View>
        </MotiView>

        {/* ── Estado de procesamiento ── */}
        <MotiView
          from={{ opacity: 0, translateY: 22 }}
          animate={{ opacity: 1, translateY: 0 }}
          transition={{ type: 'timing', duration: 400, delay: 80 }}
          style={s.card}
        >
          <View style={s.processingRow}>
            {/* Icono animado reloj ↔ check */}
            <View style={s.processingIconWrap}>
              <Animated.View style={[s.processingIconAbs, { opacity: clockOpacity, transform: [{ rotate: spin }] }]}>
                <Ionicons name="time-outline" size={28} color={GREEN} />
              </Animated.View>
              <Animated.View style={[s.processingIconAbs, { opacity: checkOpacity, transform: [{ scale: checkScale }] }]}>
                <Ionicons name="checkmark-circle" size={28} color={GREEN} />
              </Animated.View>
            </View>

            <View style={s.processingText}>
              <Text style={s.processingTitle}>Procesando tu operación</Text>
              <Text style={s.processingTime}>Tiempo promedio: 15 – 30 minutos</Text>
            </View>
          </View>

          {/* Barra de progreso sutil */}
          <View style={s.progressBar}>
            <MotiView
              from={{ width: '0%' }}
              animate={{ width: '65%' }}
              transition={{ type: 'timing', duration: 2000, delay: 300 }}
              style={s.progressFill}
            />
          </View>
        </MotiView>

        {/* ── Resumen de operación ── */}
        <MotiView
          from={{ opacity: 0, translateY: 22 }}
          animate={{ opacity: 1, translateY: 0 }}
          transition={{ type: 'timing', duration: 400, delay: 160 }}
          style={s.card}
        >
          {/* Cabecera */}
          <View style={s.cardHeaderRow}>
            <View style={s.cardIconWrap}>
              <Ionicons name="receipt-outline" size={17} color={GREEN} />
            </View>
            <Text style={s.cardTitle}>Detalles de la operación</Text>
          </View>

          <View style={s.hairline} />

          {/* ID / tipo / fecha */}
          <View style={s.detailRow}>
            <Text style={s.detailLabel}>ID de Operación</Text>
            <Text style={s.detailValue}>{operation.operation_id}</Text>
          </View>
          <View style={s.detailRow}>
            <Text style={s.detailLabel}>Tipo</Text>
            <Text style={s.detailValue}>
              Qoricash {operation.operation_type === 'Compra' ? 'compra' : 'venta'}
            </Text>
          </View>
          <View style={s.detailRow}>
            <Text style={s.detailLabel}>Fecha</Text>
            <Text style={s.detailValue}>{formatDateTime(operation.created_at)}</Text>
          </View>

          <View style={s.hairline} />

          {/* Montos */}
          <View style={s.amountsRow}>
            <View style={s.amountBlock}>
              <Text style={s.amountFlag}>
                {operation.operation_type === 'Compra' ? '🇺🇸' : '🇵🇪'}
              </Text>
              <Text style={s.amountLabel}>Enviaste</Text>
              <Text style={s.amountValue}>
                {operation.operation_type === 'Compra'
                  ? formatCurrency(operation.amount_usd, 'USD')
                  : formatCurrency(operation.amount_pen, 'PEN')}
              </Text>
            </View>

            <View style={s.tcPill}>
              <Ionicons name="swap-horizontal" size={11} color={DIM} />
              <Text style={s.tcPillText}>{operation.exchange_rate.toFixed(3)}</Text>
            </View>

            <View style={s.amountBlock}>
              <Text style={s.amountFlag}>
                {operation.operation_type === 'Compra' ? '🇵🇪' : '🇺🇸'}
              </Text>
              <Text style={s.amountLabel}>Recibirás</Text>
              <Text style={[s.amountValue, { color: GREEN }]}>
                {operation.operation_type === 'Compra'
                  ? formatCurrency(operation.amount_pen, 'PEN')
                  : formatCurrency(operation.amount_usd, 'USD')}
              </Text>
            </View>
          </View>
        </MotiView>

        {/* ── Cuenta de destino ── */}
        <MotiView
          from={{ opacity: 0, translateY: 22 }}
          animate={{ opacity: 1, translateY: 0 }}
          transition={{ type: 'timing', duration: 400, delay: 240 }}
          style={s.card}
        >
          <View style={s.cardHeaderRow}>
            <View style={s.cardIconWrap}>
              <Ionicons name="wallet-outline" size={17} color={GREEN} />
            </View>
            <Text style={s.cardTitle}>Cuenta de destino</Text>
          </View>

          <View style={s.hairline} />

          <View style={s.detailRow}>
            <Text style={s.detailLabel}>Titular</Text>
            <Text style={s.detailValue}>{clientName}</Text>
          </View>

          <View style={s.detailRowBank}>
            <Text style={s.detailLabel}>Banco</Text>
            {operation.destination_bank_name && BANK_LOGOS[operation.destination_bank_name] ? (
              <View style={s.bankLogoWrapper}>
                <Image
                  source={BANK_LOGOS[operation.destination_bank_name]}
                  style={s.bankLogo}
                  resizeMode="contain"
                />
              </View>
            ) : (
              <Text style={s.detailValue}>{operation.destination_bank_name || 'Por definir'}</Text>
            )}
          </View>

          <View style={s.detailRow}>
            <Text style={s.detailLabel}>Tipo / Moneda</Text>
            <Text style={s.detailValue}>{accountInfo}</Text>
          </View>

          <View style={[s.detailRow, { borderBottomWidth: 0 }]}>
            <Text style={s.detailLabel}>N° cuenta</Text>
            <Text style={s.detailValue}>{operation.destination_account || 'Por definir'}</Text>
          </View>
        </MotiView>

        {/* ── Botones ── */}
        <MotiView
          from={{ opacity: 0, translateY: 22 }}
          animate={{ opacity: 1, translateY: 0 }}
          transition={{ type: 'timing', duration: 400, delay: 320 }}
          style={s.actionsWrap}
        >
          <TouchableOpacity style={s.primaryBtn} onPress={handleAccept} activeOpacity={0.8}>
            <Ionicons name="checkmark-circle-outline" size={20} color="#fff" />
            <Text style={s.primaryBtnText}>VER MI HISTORIAL</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={s.supportBtn}
            activeOpacity={0.7}
            onPress={() => {
              const msg = `Hola, necesito ayuda con mi operación ${operation.operation_id}`;
              Linking.openURL(`https://wa.me/51910624404?text=${encodeURIComponent(msg)}`);
            }}
          >
            <Ionicons name="logo-whatsapp" size={16} color="#25D366" />
            <Text style={s.supportBtnText}>Contactar con soporte</Text>
          </TouchableOpacity>
        </MotiView>

      </ScrollView>
    </View>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
const s = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: '#000',
  },
  overlay: {
    backgroundColor: 'transparent',
  },

  // ── Header ──────────────────────────────────────────────────────────────────
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingBottom: 14,
  },
  headerCenter: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerLogo: {
    width: 110,
    height: 22,
  },

  scroll: { flex: 1 },

  // ── Timeline ─────────────────────────────────────────────────────────────────
  timeline: {
    flexDirection: 'row',
    alignItems: 'center',
    marginHorizontal: 16,
    marginBottom: 16,
    backgroundColor: GLASS,
    borderWidth: 1,
    borderColor: BORDER,
    borderRadius: 20,
    paddingVertical: 14,
    paddingHorizontal: 20,
  },
  step: {
    alignItems: 'center',
    gap: 5,
  },
  stepDot: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderWidth: 1,
    borderColor: BORDER,
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepDotDone: {
    backgroundColor: GREEN,
    borderColor: GREEN,
  },
  stepDotActive: {
    backgroundColor: 'rgba(34,197,94,0.18)',
    borderColor: GREEN,
    borderWidth: 1.5,
  },
  stepLine: {
    flex: 1,
    height: 2,
    backgroundColor: 'rgba(255,255,255,0.1)',
    marginHorizontal: 8,
    marginBottom: 20,
  },
  stepLineDone: {
    backgroundColor: GREEN,
  },
  stepLabel: {
    fontSize: 10,
    color: DIM,
    fontWeight: '500',
  },
  stepLabelDone: {
    color: GREEN,
    fontWeight: '600',
  },
  stepLabelActive: {
    color: '#fff',
    fontWeight: '700',
  },

  // ── Cards ────────────────────────────────────────────────────────────────────
  card: {
    backgroundColor: GLASS,
    borderWidth: 1,
    borderColor: BORDER,
    borderRadius: 22,
    marginHorizontal: 16,
    marginBottom: 14,
    padding: 18,
  },
  hairline: {
    height: 1,
    backgroundColor: BORDER,
    marginVertical: 14,
  },
  cardHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  cardIconWrap: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: 'rgba(34,197,94,0.12)',
    borderWidth: 1,
    borderColor: 'rgba(34,197,94,0.25)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  cardTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: '#fff',
  },

  // ── Procesamiento ────────────────────────────────────────────────────────────
  processingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
  },
  processingIconWrap: {
    width: 44,
    height: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  processingIconAbs: {
    position: 'absolute',
  },
  processingText: {
    flex: 1,
  },
  processingTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: '#fff',
    marginBottom: 3,
  },
  processingTime: {
    fontSize: 12,
    color: DIM,
  },
  progressBar: {
    height: 3,
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderRadius: 2,
    marginTop: 16,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    backgroundColor: GREEN,
    borderRadius: 2,
  },

  // ── Filas de detalle ──────────────────────────────────────────────────────────
  detailRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 9,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255,255,255,0.06)',
  },
  detailLabel: {
    fontSize: 13,
    color: DIM,
    flex: 1,
  },
  detailValue: {
    fontSize: 13,
    fontWeight: '600',
    color: '#fff',
    flex: 2,
    textAlign: 'right',
  },
  detailRowBank: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    height: 48,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255,255,255,0.06)',
  },
  bankLogoWrapper: {
    flex: 1,
    alignItems: 'flex-end',
    marginRight: -18,
  },
  bankLogo: {
    width: 130,
    height: 38,
    backgroundColor: 'transparent',
  },

  // ── Montos ──────────────────────────────────────────────────────────────────
  amountsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  amountBlock: {
    flex: 1,
    backgroundColor: 'rgba(255,255,255,0.05)',
    borderRadius: 12,
    padding: 12,
    alignItems: 'center',
    gap: 4,
  },
  amountFlag: {
    fontSize: 16,
  },
  amountLabel: {
    fontSize: 10,
    color: DIM,
    fontWeight: '500',
    textTransform: 'uppercase',
    letterSpacing: 0.4,
  },
  amountValue: {
    fontSize: 14,
    fontWeight: '700',
    color: '#fff',
  },
  tcPill: {
    alignItems: 'center',
    gap: 3,
    paddingHorizontal: 4,
  },
  tcPillText: {
    fontSize: 10,
    color: DIM,
    fontWeight: '600',
  },

  // ── Botones ──────────────────────────────────────────────────────────────────
  actionsWrap: {
    marginHorizontal: 16,
    gap: 10,
  },
  primaryBtn: {
    backgroundColor: GREEN,
    borderRadius: 16,
    paddingVertical: 16,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    shadowColor: GREEN,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.4,
    shadowRadius: 12,
    elevation: 6,
  },
  primaryBtnText: {
    color: '#fff',
    fontSize: 15,
    fontWeight: '700',
    letterSpacing: 0.8,
  },
  supportBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 7,
    paddingVertical: 14,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: 'rgba(37,211,102,0.3)',
    backgroundColor: 'rgba(37,211,102,0.06)',
  },
  supportBtnText: {
    fontSize: 14,
    color: '#25D366',
    fontWeight: '600',
  },
});
