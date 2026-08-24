import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  Text,
  TouchableOpacity,
  RefreshControl,
  ImageBackground,
  Linking,
  ActivityIndicator,
} from 'react-native';
import Reanimated, {
  useSharedValue,
  useAnimatedStyle,
  withRepeat,
  withSequence,
  withTiming,
  Easing as REasing,
} from 'react-native-reanimated';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { MotiView } from 'moti';
import apiClient from '../api/client';

// ─── Types ────────────────────────────────────────────────────────────────────
interface MarketIndicator {
  key: string;
  label: string;
  value: number | null;
  chg: number | null;
  prefix: string;
  suffix: string;
}

interface MacroItem {
  key: string;
  label: string;
  value: number | null;
  prev_value: number | null;
  unit: string;
  direction: string;
  period: string;
  source: string;
}

interface NewsItem {
  title: string;
  source: string;
  time: string;
  impact_level: number;
  direction: string;
  summary: string;
  url: string;
}

interface Signal {
  type: string;
  confidence: number;
  title: string;
  summary: string;
}

interface MarketData {
  indicators: MarketIndicator[];
  macro: MacroItem[];
  news: NewsItem[];
  signal: Signal | null;
  last_update: string | null;
}

// ─── Constants ────────────────────────────────────────────────────────────────
const GLASS_BG     = 'rgba(255,255,255,0.08)';
const GLASS_BORDER = 'rgba(255,255,255,0.14)';
const GREEN        = '#22c55e';
const RED          = '#ef4444';
const AMBER        = '#f59e0b';
const TAB_BAR_H    = 72;

// ─── Helpers ──────────────────────────────────────────────────────────────────
const fmtValue = (v: number | null, prefix: string, suffix: string): string => {
  if (v === null || v === undefined) return '—';
  const abs = Math.abs(v);
  let formatted: string;
  if (abs >= 1000) {
    formatted = v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  } else if (abs >= 10) {
    formatted = v.toFixed(2);
  } else {
    formatted = v.toFixed(4);
  }
  return `${prefix}${formatted}${suffix}`;
};

const fmtChg = (chg: number | null): string => {
  if (chg === null || chg === undefined) return '';
  return `${chg >= 0 ? '+' : ''}${chg.toFixed(2)}%`;
};

const chgColor = (chg: number | null) => {
  if (chg === null || chg === undefined) return 'rgba(255,255,255,0.4)';
  return chg >= 0 ? GREEN : RED;
};

const INDICATOR_ICONS: Record<string, keyof typeof Ionicons.glyphMap> = {
  usdpen:       'swap-horizontal-outline',
  gold:         'trophy-outline',
  oil:          'flame-outline',
  sp500:        'bar-chart-outline',
  nasdaq:       'trending-up-outline',
  dxy:          'earth-outline',
  vix:          'warning-outline',
  copper:       'hardware-chip-outline',
  eurusd:       'cash-outline',
  treasury_10y: 'document-text-outline',
  btc:          'logo-bitcoin',
  usdjpy:       'swap-horizontal-outline',
};

const SIGNAL_CONFIG = {
  bullish:  { color: GREEN,  icon: 'trending-up'   as const, label: 'Alcista' },
  bearish:  { color: RED,    icon: 'trending-down'  as const, label: 'Bajista' },
  volatile: { color: AMBER,  icon: 'alert-circle'   as const, label: 'Volátil' },
  lateral:  { color: 'rgba(255,255,255,0.55)', icon: 'remove-outline' as const, label: 'Lateral' },
  neutral:  { color: 'rgba(255,255,255,0.55)', icon: 'remove-outline' as const, label: 'Neutral'  },
};

const DIRECTION_COLOR: Record<string, string> = {
  bullish: GREEN,
  bearish: RED,
  neutral: 'rgba(255,255,255,0.4)',
};

const IMPACT_COLOR = ['', 'rgba(255,255,255,0.25)', AMBER, RED];

// ─── Clasificación Nacional / Internacional ────────────────────────────────────
const FUENTES_NACIONALES = [
  'gestión', 'gestion', 'el comercio', 'elcomercio', 'rpp',
  'andina', 'semana económica', 'semanaeconomica', 'el peruano', 'elperuano',
  'la república', 'larepublica', 'peru21', 'expreso', 'correo', 'trome',
  'exitosa', 'ojo financiero', 'capital', 'bcrp', 'mef.gob', 'sbs.gob',
  'energiminas', 'minería perú', 'mineria peru', 'diario financiero perú',
  'rumbo minero', 'stakeholders', 'mercados & regiones',
];

type NewsOrigin = 'all' | 'nacional' | 'internacional';

const classifyNews = (source: string): 'nacional' | 'internacional' => {
  const lower = source.toLowerCase();
  return FUENTES_NACIONALES.some(k => lower.includes(k))
    ? 'nacional'
    : 'internacional';
};

// ─── Sub-components ───────────────────────────────────────────────────────────

const LivePulse: React.FC<{ color?: string }> = ({ color = GREEN }) => {
  const scale  = useSharedValue(1);
  const ringOp = useSharedValue(0);
  const ringSc = useSharedValue(1);

  useEffect(() => {
    scale.value = withRepeat(
      withSequence(
        withTiming(1.26, { duration: 750, easing: REasing.inOut(REasing.quad) }),
        withTiming(1,    { duration: 750, easing: REasing.inOut(REasing.quad) }),
      ), -1, false,
    );
    ringOp.value = withRepeat(
      withSequence(
        withTiming(0.55, { duration: 200,  easing: REasing.out(REasing.quad) }),
        withTiming(0,    { duration: 1100, easing: REasing.out(REasing.cubic) }),
        withTiming(0,    { duration: 200 }),
      ), -1, false,
    );
    ringSc.value = withRepeat(
      withSequence(
        withTiming(1,   { duration: 0 }),
        withTiming(2.8, { duration: 1300, easing: REasing.out(REasing.cubic) }),
        withTiming(1,   { duration: 0 }),
      ), -1, false,
    );
  }, []);

  const dotStyle  = useAnimatedStyle(() => ({ transform: [{ scale: scale.value }] }));
  const ringStyle = useAnimatedStyle(() => ({
    opacity:   ringOp.value,
    transform: [{ scale: ringSc.value }],
  }));

  return (
    <View style={s.livePulseWrap}>
      <Reanimated.View pointerEvents="none" style={[s.livePulseRing, { backgroundColor: color }, ringStyle]} />
      <Reanimated.View style={[s.livePulseDot, { backgroundColor: color }, dotStyle]} />
    </View>
  );
};

const SectionHeader: React.FC<{ title: string; subtitle?: string }> = ({ title, subtitle }) => (
  <View style={s.sectionHeader}>
    <Text style={s.sectionTitle}>{title}</Text>
    {subtitle ? <Text style={s.sectionSub}>{subtitle}</Text> : null}
  </View>
);

const IndicatorCard: React.FC<{ item: MarketIndicator; delay: number }> = ({ item, delay }) => {
  const icon = INDICATOR_ICONS[item.key] ?? 'analytics-outline';
  const color = chgColor(item.chg);
  return (
    <MotiView
      from={{ opacity: 0, scale: 0.94 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ type: 'spring', delay, damping: 20, stiffness: 180 }}
      style={s.indicatorCard}
    >
      <View style={s.indicatorTop}>
        <Ionicons name={icon} size={11} color="rgba(255,255,255,0.5)" />
        <Text style={s.indicatorLabel} numberOfLines={1}>{item.label}</Text>
      </View>
      <Text style={s.indicatorValue} numberOfLines={1}>
        {fmtValue(item.value, item.prefix, item.suffix)}
      </Text>
      {item.chg !== null && (
        <Text style={[s.indicatorChg, { color }]}>{fmtChg(item.chg)}</Text>
      )}
    </MotiView>
  );
};

const MacroRow: React.FC<{ item: MacroItem; delay: number }> = ({ item, delay }) => {
  const dirColor = DIRECTION_COLOR[item.direction] ?? 'rgba(255,255,255,0.4)';
  const arrow = item.direction === 'up' ? '↑' : item.direction === 'down' ? '↓' : '—';
  const val = item.value !== null ? `${item.value}${item.unit}` : '—';
  return (
    <MotiView
      from={{ opacity: 0, translateX: -12 }}
      animate={{ opacity: 1, translateX: 0 }}
      transition={{ type: 'timing', delay, duration: 320 }}
      style={s.macroRow}
    >
      <View style={s.macroLeft}>
        <Text style={s.macroLabel}>{item.label}</Text>
        {item.period ? <Text style={s.macroPeriod}>{item.period}</Text> : null}
      </View>
      <View style={s.macroRight}>
        <Text style={s.macroValue}>{val}</Text>
        <Text style={[s.macroArrow, { color: dirColor }]}>{arrow}</Text>
      </View>
    </MotiView>
  );
};

const NewsCard: React.FC<{ item: NewsItem; delay: number }> = ({ item, delay }) => {
  const impactColor = IMPACT_COLOR[Math.min(item.impact_level, 3)] ?? 'rgba(255,255,255,0.25)';
  const dirColor    = DIRECTION_COLOR[item.direction] ?? 'rgba(255,255,255,0.4)';

  const handlePress = () => {
    if (item.url) Linking.openURL(item.url).catch(() => {});
  };

  return (
    <MotiView
      from={{ opacity: 0, translateY: 10 }}
      animate={{ opacity: 1, translateY: 0 }}
      transition={{ type: 'timing', delay, duration: 320 }}
    >
      <TouchableOpacity
        style={s.newsCard}
        activeOpacity={item.url ? 0.75 : 1}
        onPress={item.url ? handlePress : undefined}
      >
        {/* Impact + direction bar */}
        <View style={[s.newsImpactBar, { backgroundColor: impactColor }]} />

        <View style={s.newsContent}>
          <View style={s.newsMetaRow}>
            <Text style={s.newsSource}>{item.source}</Text>
            {item.time ? <Text style={s.newsTime}>{item.time}</Text> : null}
            {item.direction !== 'neutral' && (
              <View style={[s.dirBadge, { borderColor: dirColor }]}>
                <Text style={[s.dirBadgeText, { color: dirColor }]}>
                  {item.direction === 'bullish' ? 'Alcista' : 'Bajista'}
                </Text>
              </View>
            )}
          </View>
          <Text style={s.newsTitle} numberOfLines={3}>{item.title}</Text>
          {item.summary ? (
            <Text style={s.newsSummary} numberOfLines={2}>{item.summary}</Text>
          ) : null}
        </View>

        {item.url ? (
          <Ionicons name="open-outline" size={14} color="rgba(255,255,255,0.25)" style={s.newsLink} />
        ) : null}
      </TouchableOpacity>
    </MotiView>
  );
};

// ─── Main Screen ──────────────────────────────────────────────────────────────
export const MarketScreen: React.FC = () => {
  const insets = useSafeAreaInsets();
  const [data, setData]           = useState<MarketData | null>(null);
  const [loading, setLoading]     = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError]         = useState('');
  const [newsFilter, setNewsFilter] = useState<NewsOrigin>('all');

  const fetchData = useCallback(async () => {
    try {
      setError('');
      const res = await apiClient.get('/api/client/market');
      if (res.success) {
        setData(res as MarketData);
      } else {
        setError('No se pudieron cargar los datos de mercado.');
      }
    } catch (err: any) {
      if (err?.response?.status) {
        setError(`Error del servidor (${err.response.status}). Intenta más tarde.`);
      } else {
        setError('Error de conexión. Verifica tu red.');
      }
    }
  }, []);

  useEffect(() => {
    fetchData().finally(() => setLoading(false));
  }, []);

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchData();
    setRefreshing(false);
  };

  const signal = data?.signal;
  const sigCfg = SIGNAL_CONFIG[signal?.type as keyof typeof SIGNAL_CONFIG] ?? SIGNAL_CONFIG.neutral;

  // ── Render ─────────────────────────────────────────────────────────────────
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
        contentContainerStyle={[
          s.content,
          { paddingTop: insets.top + 16, paddingBottom: insets.bottom + TAB_BAR_H + 16 },
        ]}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor="rgba(255,255,255,0.5)"
          />
        }
      >
        {/* ── Header ── */}
        <View style={s.pageHeader}>
          <Text style={s.pageTitle}>Mercado</Text>
          {data?.last_update ? (
            <Text style={s.pageSubtitle}>Actualizado {data.last_update} hrs</Text>
          ) : null}
        </View>

        {/* ── Loading ── */}
        {loading && (
          <View style={s.loadWrap}>
            <ActivityIndicator size="large" color={GREEN} />
            <Text style={s.loadText}>Cargando datos de mercado...</Text>
          </View>
        )}

        {/* ── Error ── */}
        {!loading && error ? (
          <View style={s.errorWrap}>
            <Ionicons name="cloud-offline-outline" size={36} color="rgba(255,255,255,0.3)" />
            <Text style={s.errorText}>{error}</Text>
            <TouchableOpacity style={s.retryBtn} onPress={onRefresh}>
              <Text style={s.retryText}>Reintentar</Text>
            </TouchableOpacity>
          </View>
        ) : null}

        {!loading && data && (
          <>
            {/* ── Signal card ── */}
            {signal && (
              <MotiView
                from={{ opacity: 0, translateY: -10 }}
                animate={{ opacity: 1, translateY: 0 }}
                transition={{ type: 'spring', delay: 0, damping: 22, stiffness: 200 }}
                style={[s.signalCard, { borderColor: `${sigCfg.color}40` }]}
              >
                <View style={[s.signalIcon, { backgroundColor: `${sigCfg.color}18` }]}>
                  <Ionicons name={sigCfg.icon} size={22} color={sigCfg.color} />
                </View>
                <View style={s.signalBody}>
                  <View style={s.signalTop}>
                    <Text style={[s.signalLabel, { color: sigCfg.color }]}>
                      Señal {sigCfg.label}
                    </Text>
                    <View style={[s.confBadge, { backgroundColor: `${sigCfg.color}18` }]}>
                      <Text style={[s.confText, { color: sigCfg.color }]}>
                        {signal.confidence}% confianza
                      </Text>
                    </View>
                  </View>
                  {signal.title ? (
                    <Text style={s.signalTitle}>{signal.title}</Text>
                  ) : null}
                </View>
                <LivePulse color={sigCfg.color} />
              </MotiView>
            )}

            {/* ── Market indicators ── */}
            {data.indicators.length > 0 && (
              <>
                <SectionHeader title="Indicadores de Mercado" subtitle="Precios en tiempo real" />
                <View style={s.indicatorsGrid}>
                  {data.indicators.map((item, i) => (
                    <IndicatorCard key={item.key} item={item} delay={i * 40} />
                  ))}
                </View>
              </>
            )}

            {/* ── Macro indicators ── */}
            {data.macro.length > 0 && (
              <>
                <SectionHeader title="Indicadores Macroeconómicos" subtitle="Datos fundamentales" />
                <View style={s.macroCard}>
                  {data.macro.map((item, i) => (
                    <React.Fragment key={item.key}>
                      <MacroRow item={item} delay={i * 50} />
                      {i < data.macro.length - 1 && <View style={s.macroDivider} />}
                    </React.Fragment>
                  ))}
                </View>
              </>
            )}

            {/* ── News ── */}
            {data.news.length > 0 && (() => {
              const filtered = newsFilter === 'all'
                ? data.news
                : data.news.filter(n => classifyNews(n.source) === newsFilter);
              return (
                <>
                  {/* Header + filtros */}
                  <View style={s.newsHeaderRow}>
                    <View>
                      <Text style={s.sectionTitle}>Noticias Financieras</Text>
                      <Text style={s.sectionSub}>Últimas 48 horas</Text>
                    </View>
                    <View style={s.newsFilters}>
                      {(['all', 'nacional', 'internacional'] as NewsOrigin[]).map(f => (
                        <TouchableOpacity
                          key={f}
                          onPress={() => setNewsFilter(f)}
                          style={[s.filterChip, newsFilter === f && s.filterChipActive]}
                          activeOpacity={0.75}
                        >
                          <Text style={[s.filterChipText, newsFilter === f && s.filterChipTextActive]}>
                            {f === 'all' ? 'Todo' : f === 'nacional' ? 'Nacional' : 'Internacional'}
                          </Text>
                        </TouchableOpacity>
                      ))}
                    </View>
                  </View>

                  {filtered.length > 0 ? (
                    <View style={s.newsList}>
                      {filtered.map((item, i) => (
                        <NewsCard key={`${item.title}-${i}`} item={item} delay={i * 30} />
                      ))}
                    </View>
                  ) : (
                    <View style={s.filterEmptyWrap}>
                      <Text style={s.filterEmptyText}>
                        No hay noticias {newsFilter === 'nacional' ? 'nacionales' : 'internacionales'} disponibles.
                      </Text>
                    </View>
                  )}
                </>
              );
            })()}

            {data.indicators.length === 0 && data.macro.length === 0 && data.news.length === 0 && (
              <View style={s.emptyWrap}>
                <Ionicons name="analytics-outline" size={40} color="rgba(255,255,255,0.2)" />
                <Text style={s.emptyText}>Los datos de mercado se actualizan cada 5 minutos.</Text>
              </View>
            )}
          </>
        )}
      </ScrollView>
    </View>
  );
};

// ─── Styles ───────────────────────────────────────────────────────────────────
const s = StyleSheet.create({
  root: { flex: 1 },
  overlay: { backgroundColor: 'rgba(0,0,0,0.52)' },
  scroll: { flex: 1 },
  content: { flexGrow: 1, paddingHorizontal: 18 },

  // Header
  pageHeader: { marginBottom: 20 },
  pageTitle: {
    fontSize: 28,
    fontWeight: '800',
    color: '#FFFFFF',
    letterSpacing: -0.5,
  },
  pageSubtitle: {
    fontSize: 12,
    color: 'rgba(255,255,255,0.42)',
    marginTop: 4,
    letterSpacing: 0.2,
  },

  // Live pulse
  livePulseWrap: {
    width: 18,
    height: 18,
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  livePulseRing: {
    position: 'absolute',
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  livePulseDot: {
    width: 9,
    height: 9,
    borderRadius: 4.5,
  },

  // Loading / error
  loadWrap: {
    paddingVertical: 60,
    alignItems: 'center',
    gap: 16,
  },
  loadText: {
    fontSize: 13,
    color: 'rgba(255,255,255,0.5)',
  },
  errorWrap: {
    paddingVertical: 60,
    alignItems: 'center',
    gap: 14,
  },
  errorText: {
    fontSize: 13.5,
    color: 'rgba(255,255,255,0.5)',
    textAlign: 'center',
  },
  retryBtn: {
    backgroundColor: 'rgba(255,255,255,0.1)',
    borderRadius: 12,
    paddingHorizontal: 24,
    paddingVertical: 10,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.18)',
  },
  retryText: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: '600',
  },

  // Signal
  signalCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: GLASS_BG,
    borderWidth: 1,
    borderRadius: 18,
    padding: 16,
    marginBottom: 24,
    gap: 14,
  },
  signalIcon: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  signalBody: { flex: 1, gap: 4 },
  signalTop: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    flexWrap: 'wrap',
  },
  signalLabel: {
    fontSize: 14,
    fontWeight: '700',
    letterSpacing: 0.2,
  },
  confBadge: {
    borderRadius: 20,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  confText: {
    fontSize: 11,
    fontWeight: '600',
    letterSpacing: 0.2,
  },
  signalTitle: {
    fontSize: 12.5,
    color: 'rgba(255,255,255,0.62)',
    lineHeight: 18,
  },

  // Section header
  sectionHeader: {
    marginBottom: 12,
    gap: 2,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#FFFFFF',
    letterSpacing: -0.2,
  },
  sectionSub: {
    fontSize: 11,
    color: 'rgba(255,255,255,0.38)',
    letterSpacing: 0.3,
  },

  // Indicator grid
  indicatorsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 28,
  },
  indicatorCard: {
    width: '31%',
    backgroundColor: GLASS_BG,
    borderWidth: 1,
    borderColor: GLASS_BORDER,
    borderRadius: 14,
    padding: 10,
    gap: 3,
  },
  indicatorTop: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginBottom: 2,
  },
  indicatorLabel: {
    fontSize: 9,
    color: 'rgba(255,255,255,0.48)',
    letterSpacing: 0.3,
    textTransform: 'uppercase',
    flex: 1,
  },
  indicatorValue: {
    fontSize: 14,
    fontWeight: '700',
    color: '#FFFFFF',
    letterSpacing: -0.2,
  },
  indicatorChg: {
    fontSize: 11,
    fontWeight: '600',
    letterSpacing: 0.1,
  },

  // Macro
  macroCard: {
    backgroundColor: GLASS_BG,
    borderWidth: 1,
    borderColor: GLASS_BORDER,
    borderRadius: 18,
    marginBottom: 28,
    overflow: 'hidden',
  },
  macroRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 14,
    paddingHorizontal: 16,
  },
  macroLeft: { flex: 1, gap: 2 },
  macroLabel: {
    fontSize: 13.5,
    color: 'rgba(255,255,255,0.82)',
    fontWeight: '500',
  },
  macroPeriod: {
    fontSize: 10.5,
    color: 'rgba(255,255,255,0.35)',
    letterSpacing: 0.3,
  },
  macroRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  macroValue: {
    fontSize: 15,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  macroArrow: {
    fontSize: 16,
    fontWeight: '700',
    width: 16,
    textAlign: 'center',
  },
  macroDivider: {
    height: StyleSheet.hairlineWidth,
    backgroundColor: GLASS_BORDER,
    marginHorizontal: 16,
  },

  // News
  newsList: { gap: 10, marginBottom: 8 },
  newsCard: {
    flexDirection: 'row',
    backgroundColor: GLASS_BG,
    borderWidth: 1,
    borderColor: GLASS_BORDER,
    borderRadius: 16,
    overflow: 'hidden',
    alignItems: 'stretch',
  },
  newsImpactBar: {
    width: 4,
    flexShrink: 0,
  },
  newsContent: {
    flex: 1,
    padding: 14,
    gap: 6,
  },
  newsMetaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    flexWrap: 'wrap',
  },
  newsSource: {
    fontSize: 10.5,
    color: 'rgba(255,255,255,0.42)',
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  newsTime: {
    fontSize: 10.5,
    color: 'rgba(255,255,255,0.3)',
  },
  dirBadge: {
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  dirBadgeText: {
    fontSize: 9.5,
    fontWeight: '700',
    letterSpacing: 0.3,
  },
  newsTitle: {
    fontSize: 13.5,
    color: 'rgba(255,255,255,0.88)',
    fontWeight: '600',
    lineHeight: 19,
  },
  newsSummary: {
    fontSize: 11.5,
    color: 'rgba(255,255,255,0.42)',
    lineHeight: 17,
  },
  newsLink: {
    padding: 14,
    alignSelf: 'center',
    flexShrink: 0,
  },

  // Empty
  emptyWrap: {
    paddingVertical: 60,
    alignItems: 'center',
    gap: 14,
  },
  emptyText: {
    fontSize: 13,
    color: 'rgba(255,255,255,0.35)',
    textAlign: 'center',
    lineHeight: 20,
  },

  // News header + filtros
  newsHeaderRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    marginBottom: 12,
    gap: 10,
    flexWrap: 'wrap',
  },
  newsFilters: {
    flexDirection: 'row',
    gap: 6,
  },
  filterChip: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: GLASS_BORDER,
    backgroundColor: 'rgba(255,255,255,0.06)',
  },
  filterChipActive: {
    borderColor: GREEN,
    backgroundColor: 'rgba(34,197,94,0.14)',
  },
  filterChipText: {
    fontSize: 11,
    fontWeight: '600',
    color: 'rgba(255,255,255,0.45)',
    letterSpacing: 0.2,
  },
  filterChipTextActive: {
    color: GREEN,
  },
  filterEmptyWrap: {
    paddingVertical: 32,
    alignItems: 'center',
  },
  filterEmptyText: {
    fontSize: 13,
    color: 'rgba(255,255,255,0.35)',
    textAlign: 'center',
  },
});
