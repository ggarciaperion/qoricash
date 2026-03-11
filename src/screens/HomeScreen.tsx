import React, { useState, useRef, useEffect } from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  RefreshControl,
  Image,
  Alert,
  SafeAreaView,
  Animated,
} from 'react-native';
import { Text, Icon, Button } from 'react-native-paper';
import { LinearGradient } from 'expo-linear-gradient';
import { useAuth } from '../contexts/AuthContext';
import { Colors } from '../constants/colors';
import { Calculator } from '../components/Calculator';
import { GlobalStyles } from '../styles/globalStyles';

interface HomeScreenProps {
  navigation: any;
}

// Capitalize first letter helper
const capitalize = (s: string) => s ? s.charAt(0).toUpperCase() + s.slice(1).toLowerCase() : s;

// ─── Pulsing live indicator dot ───────────────────────────────────────────────
const LiveDot = () => {
  const ringScale   = useRef(new Animated.Value(1)).current;
  const ringOpacity = useRef(new Animated.Value(0.75)).current;
  useEffect(() => {
    Animated.loop(
      Animated.sequence([
        Animated.parallel([
          Animated.timing(ringScale,   { toValue: 2.4, duration: 850, useNativeDriver: true }),
          Animated.timing(ringOpacity, { toValue: 0,   duration: 850, useNativeDriver: true }),
        ]),
        Animated.parallel([
          Animated.timing(ringScale,   { toValue: 1,    duration: 0, useNativeDriver: true }),
          Animated.timing(ringOpacity, { toValue: 0.75, duration: 0, useNativeDriver: true }),
        ]),
      ])
    ).start();
  }, []);
  return (
    <View style={{ width: 10, height: 10, justifyContent: 'center', alignItems: 'center' }}>
      <Animated.View style={{
        position: 'absolute',
        width: 10, height: 10, borderRadius: 5,
        backgroundColor: '#22c55e',
        opacity: ringOpacity,
        transform: [{ scale: ringScale }],
      }} />
      <View style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: '#22c55e' }} />
    </View>
  );
};

export const HomeScreen: React.FC<HomeScreenProps> = ({ navigation }) => {
  const { client, refreshClient } = useAuth();
  const [refreshing, setRefreshing] = useState(false);

  const onRefresh = async () => {
    setRefreshing(true);
    await refreshClient();
    setRefreshing(false);
  };

  const handleInitiateOperation = (
    operationType: 'Compra' | 'Venta',
    amountUSD: string,
    exchangeRate: number
  ) => {
    if (!client?.has_complete_documents) {
      Alert.alert(
        'Validación de Identidad Requerida',
        'Necesitamos validar tu DNI antes de iniciar una operación.\n\nPor favor, sube las fotos de tu DNI usando el botón "Validar Identidad".',
        [{ text: 'Entendido' }]
      );
      return;
    }
    navigation.navigate('NewOperation', { operationType, amountUSD, exchangeRate });
  };

  if (!client) {
    return (
      <View style={GlobalStyles.container}>
        <Text>Cargando...</Text>
      </View>
    );
  }

  // Use client.nombres (given names) for greeting — it contains first name(s) only.
  // Peruvian DBs often store full_name as "ApellidoPaterno ApellidoMaterno Nombres",
  // so split(' ')[0] on full_name returns the surname instead of the first name.
  const firstName = (() => {
    if (client.nombres) return capitalize(client.nombres.split(' ')[0]);
    if (client.full_name) return capitalize(client.full_name.split(' ')[0]);
    return '';
  })();

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView
        style={styles.scrollView}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={Colors.primary}
            colors={[Colors.primary]}
          />
        }
      >
        {/* ── Dark gradient header ── */}
        <LinearGradient
          colors={['#0D1B2A', '#111F2C', '#0f2236']}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
          style={styles.header}
        >
          {/* Subtle teal glow top-right */}
          <View style={styles.headerGlow} />

          <View style={styles.headerTop}>
            <View style={styles.headerGreetingBlock}>
              <Text style={styles.headerGreeting}>Bienvenido,</Text>
              <Text style={styles.headerName}>{firstName}</Text>
            </View>
            <Image
              source={require('../../assets/logo-principal.png')}
              style={styles.headerLogo}
              resizeMode="contain"
            />
          </View>

          {/* User info strip */}
          <View style={styles.userStrip}>
            <View style={styles.userStripItem}>
              <Text style={styles.userStripLabel}>Documento</Text>
              <Text style={styles.userStripValue}>{client.dni}</Text>
            </View>
            <View style={styles.userStripDivider} />
            <View style={styles.userStripItem}>
              <Text style={styles.userStripLabel}>Estado</Text>
              <View style={styles.statusBadge}>
                <View style={styles.statusDot} />
                <Text style={styles.statusBadgeText}>{capitalize(client.status)}</Text>
              </View>
            </View>
            <View style={styles.userStripDivider} />
            <View style={styles.userStripItem}>
              <Text style={styles.userStripLabel}>Tipo</Text>
              <Text style={styles.userStripValue}>
                {(client as any).client_type === 'juridico' ? 'Empresa' : 'Natural'}
              </Text>
            </View>
          </View>
        </LinearGradient>

        {/* ── Content ── */}
        <View style={styles.content}>

          {/* Verification banners */}
          {!client.has_complete_documents && (
            <>
              {/* Documents NOT submitted */}
              {(!client.dni_front_url || !client.dni_back_url) && (
                <View style={styles.verificationBanner}>
                  <View style={styles.bannerRow}>
                    <View style={styles.warningIconCircle}>
                      <Icon source="shield-alert" size={20} color={Colors.warning} />
                    </View>
                    <View style={styles.bannerTexts}>
                      <Text style={styles.bannerTitle}>Validación pendiente</Text>
                      <Text style={styles.bannerSubtitle}>
                        Sube tu DNI para empezar a operar.
                      </Text>
                    </View>
                  </View>
                  <Button
                    mode="contained"
                    icon="camera-plus"
                    onPress={() => navigation.navigate('VerifyIdentity')}
                    style={styles.verifyBtn}
                    buttonColor={Colors.warning}
                    textColor="#FFFFFF"
                    compact
                  >
                    Validar ahora
                  </Button>
                </View>
              )}

              {/* Documents submitted — under review */}
              {client.dni_front_url && client.dni_back_url && (
                <View style={styles.processingBanner}>
                  <View style={styles.bannerRow}>
                    <View style={styles.infoIconCircle}>
                      <Icon source="clock-outline" size={20} color={Colors.info} />
                    </View>
                    <View style={styles.bannerTexts}>
                      <Text style={styles.processingTitle}>Validación en proceso</Text>
                      <Text style={styles.bannerSubtitle}>
                        ⏱ Aprox. 10 minutos — te notificaremos.
                      </Text>
                    </View>
                  </View>
                </View>
              )}
            </>
          )}

          {/* ── Exchange rate calculator card ── */}
          <View style={styles.calculatorCard}>
            {/* Card header */}
            <View style={styles.calculatorCardHeader}>
              <View style={styles.calculatorCardHeaderLeft}>
                <View style={styles.calculatorIconBg}>
                  <Icon source="swap-horizontal" size={16} color={Colors.primary} />
                </View>
                <Text style={styles.calculatorCardTitle}>Tipo de Cambio</Text>
              </View>
              <View style={styles.liveChip}>
                <LiveDot />
                <Text style={styles.liveChipText}>EN VIVO</Text>
              </View>
            </View>

            <Calculator
              onOperationReady={handleInitiateOperation}
              showInitiateButton={true}
            />
          </View>

        </View>
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#0D1B2A',
  },
  scrollView: {
    flex: 1,
    backgroundColor: Colors.background,
  },

  // ── Header ──
  header: {
    paddingTop: 20,
    paddingBottom: 0,
    overflow: 'hidden',
  },
  headerGlow: {
    position: 'absolute',
    top: -60,
    right: -60,
    width: 200,
    height: 200,
    borderRadius: 100,
    backgroundColor: Colors.primary,
    opacity: 0.05,
  },
  headerTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    marginBottom: 20,
  },
  headerGreetingBlock: {
    flex: 1,
  },
  headerGreeting: {
    fontSize: 13,
    color: '#8A9BB5',
    fontWeight: '400',
    marginBottom: 2,
  },
  headerName: {
    fontSize: 26,
    fontWeight: '800',
    color: '#F1F5F9',
    letterSpacing: -0.5,
  },
  headerLogo: {
    width: 52,
    height: 52,
    opacity: 0.85,
  },

  // User strip
  userStrip: {
    flexDirection: 'row',
    borderTopWidth: 1,
    borderTopColor: 'rgba(255,255,255,0.07)',
    backgroundColor: 'rgba(255,255,255,0.04)',
    paddingVertical: 14,
    paddingHorizontal: 20,
  },
  userStripItem: {
    flex: 1,
    alignItems: 'center',
  },
  userStripLabel: {
    fontSize: 10,
    color: '#6B7E94',
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    marginBottom: 5,
  },
  userStripValue: {
    fontSize: 13,
    color: '#B0BBC9',
    fontWeight: '600',
  },
  userStripDivider: {
    width: 1,
    backgroundColor: 'rgba(255,255,255,0.07)',
    marginVertical: 2,
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
  },
  statusDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: Colors.success,
  },
  statusBadgeText: {
    fontSize: 13,
    color: Colors.success,
    fontWeight: '700',
  },

  // ── Content ──
  content: {
    padding: 16,
    paddingTop: 20,
  },

  // Verification banner — warning
  verificationBanner: {
    backgroundColor: '#FFFBEB',
    borderWidth: 1,
    borderColor: '#FDE68A',
    borderRadius: 16,
    padding: 16,
    marginBottom: 16,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
  },
  // Verification banner — processing
  processingBanner: {
    backgroundColor: '#EFF6FF',
    borderWidth: 1,
    borderColor: '#BFDBFE',
    borderRadius: 16,
    padding: 16,
    marginBottom: 16,
  },
  bannerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    flex: 1,
  },
  warningIconCircle: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: '#FEF3C7',
    justifyContent: 'center',
    alignItems: 'center',
    flexShrink: 0,
  },
  infoIconCircle: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: '#DBEAFE',
    justifyContent: 'center',
    alignItems: 'center',
    flexShrink: 0,
  },
  bannerTexts: {
    flex: 1,
  },
  bannerTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#92400E',
    marginBottom: 2,
  },
  processingTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#1E40AF',
    marginBottom: 2,
  },
  bannerSubtitle: {
    fontSize: 12,
    color: '#78716C',
    lineHeight: 17,
  },
  verifyBtn: {
    borderRadius: 10,
    flexShrink: 0,
  },

  // ── Calculator card ──
  calculatorCard: {
    backgroundColor: Colors.surface,
    borderRadius: 20,
    padding: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.08,
    shadowRadius: 16,
    elevation: 4,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  calculatorCardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 20,
    paddingBottom: 16,
    borderBottomWidth: 1,
    borderBottomColor: Colors.divider,
  },
  calculatorCardHeaderLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  calculatorIconBg: {
    width: 32,
    height: 32,
    borderRadius: 10,
    backgroundColor: `${Colors.primary}18`,
    justifyContent: 'center',
    alignItems: 'center',
  },
  calculatorCardTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: Colors.textDark,
  },
  liveChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    backgroundColor: 'rgba(34, 197, 94, 0.09)',
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: 'rgba(34, 197, 94, 0.2)',
  },
  // liveDot replaced by <LiveDot /> animated component above
  liveChipText: {
    fontSize: 10,
    fontWeight: '800',
    color: '#22c55e',
    letterSpacing: 0.8,
  },
});
