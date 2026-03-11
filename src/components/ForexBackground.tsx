import React, { useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Animated,
  Dimensions,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';

const { height: SCREEN_H } = Dimensions.get('window');
const TEAL = '#22c55e';

// ─── Star field (30 particles, deterministic) ───────────────────────────────
const STARS = [
  { top: '3%',  left: '7%',  size: 1.5, delay: 0    },
  { top: '8%',  left: '45%', size: 2.5, delay: 400  },
  { top: '5%',  left: '82%', size: 1,   delay: 800  },
  { top: '12%', left: '23%', size: 2,   delay: 200  },
  { top: '15%', left: '67%', size: 1.5, delay: 1200 },
  { top: '18%', left: '91%', size: 1,   delay: 600  },
  { top: '22%', left: '12%', size: 2,   delay: 1600 },
  { top: '25%', left: '55%', size: 1.5, delay: 300  },
  { top: '28%', left: '78%', size: 2,   delay: 900  },
  { top: '32%', left: '4%',  size: 1,   delay: 1400 },
  { top: '35%', left: '38%', size: 2.5, delay: 700  },
  { top: '38%', left: '93%', size: 1.5, delay: 100  },
  { top: '42%', left: '16%', size: 1,   delay: 1800 },
  { top: '45%', left: '72%', size: 2,   delay: 500  },
  { top: '50%', left: '49%', size: 1.5, delay: 1100 },
  { top: '55%', left: '28%', size: 1,   delay: 2000 },
  { top: '58%', left: '86%', size: 2,   delay: 300  },
  { top: '62%', left: '8%',  size: 1.5, delay: 1500 },
  { top: '65%', left: '62%', size: 2.5, delay: 800  },
  { top: '68%', left: '34%', size: 1,   delay: 1300 },
  { top: '72%', left: '76%', size: 2,   delay: 400  },
  { top: '75%', left: '18%', size: 1.5, delay: 1700 },
  { top: '78%', left: '51%', size: 1,   delay: 600  },
  { top: '82%', left: '88%', size: 2,   delay: 2200 },
  { top: '85%', left: '42%', size: 1.5, delay: 1000 },
  { top: '88%', left: '25%', size: 2,   delay: 200  },
  { top: '92%', left: '69%', size: 1,   delay: 1600 },
  { top: '95%', left: '6%',  size: 1.5, delay: 900  },
  { top: '10%', left: '33%', size: 1,   delay: 1100 },
  { top: '47%', left: '96%', size: 2,   delay: 700  },
];

// ─── Candlestick data ────────────────────────────────────────────────────────
const CANDLES = [
  { uw: 8,  b: 14, lw: 6,  bull: true  },
  { uw: 5,  b: 10, lw: 4,  bull: false },
  { uw: 12, b: 20, lw: 8,  bull: true  },
  { uw: 4,  b:  8, lw: 3,  bull: true  },
  { uw: 9,  b: 18, lw: 7,  bull: false },
  { uw: 6,  b: 12, lw: 5,  bull: true  },
  { uw: 14, b: 22, lw: 9,  bull: false },
  { uw: 5,  b: 10, lw: 4,  bull: true  },
  { uw: 11, b: 20, lw: 7,  bull: true  },
  { uw: 7,  b: 14, lw: 6,  bull: false },
  { uw: 16, b: 26, lw: 10, bull: true  },
  { uw: 6,  b: 12, lw: 5,  bull: false },
  { uw: 10, b: 18, lw: 7,  bull: true  },
  { uw: 4,  b:  8, lw: 3,  bull: true  },
  { uw: 13, b: 22, lw: 9,  bull: false },
];

// ─── Floating price tickers ──────────────────────────────────────────────────
const FLOAT_TICKERS = [
  { pair: 'USD/PEN', price: '3.725', change: '+0.02%', up: true,  left: '5%',  delay: 0    },
  { pair: 'EUR/USD', price: '1.082', change: '-0.15%', up: false, left: '54%', delay: 3500 },
  { pair: 'GBP/USD', price: '1.265', change: '+0.08%', up: true,  left: '26%', delay: 7000 },
  { pair: 'USD/BRL', price: '5.043', change: '-0.11%', up: false, left: '70%', delay: 1800 },
  { pair: 'JPY/USD', price: '0.0067',change: '+0.05%', up: true,  left: '40%', delay: 5200 },
];

// ─── Star ────────────────────────────────────────────────────────────────────
const Star = ({ s }: { s: typeof STARS[0] }) => {
  const op = useRef(new Animated.Value(0.05)).current;
  useEffect(() => {
    let alive = true;
    const pulse = () => {
      if (!alive) return;
      Animated.sequence([
        Animated.delay(s.delay),
        Animated.timing(op, { toValue: 0.8, duration: 1600 + (s.delay % 1000), useNativeDriver: true }),
        Animated.timing(op, { toValue: 0.05, duration: 1600 + (s.delay % 1000), useNativeDriver: true }),
      ]).start(({ finished }) => { if (finished && alive) pulse(); });
    };
    pulse();
    return () => { alive = false; };
  }, []);
  return (
    <Animated.View
      style={{
        position: 'absolute',
        top: s.top as any,
        left: s.left as any,
        width: s.size,
        height: s.size,
        borderRadius: s.size,
        backgroundColor: TEAL,
        opacity: op,
      }}
    />
  );
};

// ─── Scan line ───────────────────────────────────────────────────────────────
const ScanLine = () => {
  const ty = useRef(new Animated.Value(-2)).current;
  useEffect(() => {
    let alive = true;
    const sweep = () => {
      if (!alive) return;
      ty.setValue(-2);
      Animated.timing(ty, { toValue: SCREEN_H + 2, duration: 6000, useNativeDriver: true })
        .start(({ finished }) => { if (finished && alive) sweep(); });
    };
    const t = setTimeout(sweep, 1200);
    return () => { alive = false; clearTimeout(t); };
  }, []);
  return (
    <Animated.View
      pointerEvents="none"
      style={{
        position: 'absolute',
        left: 0,
        right: 0,
        height: 1.5,
        backgroundColor: 'rgba(0,222,168,0.09)',
        transform: [{ translateY: ty }],
      }}
    />
  );
};

// ─── Trading grid ─────────────────────────────────────────────────────────────
const TradingGrid = () => (
  <View style={StyleSheet.absoluteFillObject} pointerEvents="none">
    {[10, 24, 38, 52, 66, 80].map((p, i) => (
      <View key={`h${i}`} style={[styles.gridH, { top: `${p}%` as any }]} />
    ))}
    {[20, 40, 60, 80].map((p, i) => (
      <View key={`v${i}`} style={[styles.gridV, { left: `${p}%` as any }]} />
    ))}
  </View>
);

// ─── Candlestick row ──────────────────────────────────────────────────────────
const CandlestickRow = () => (
  <View style={styles.candleArea} pointerEvents="none">
    {CANDLES.map((c, i) => {
      const color = c.bull ? TEAL : '#fb7185';
      return (
        <View key={i} style={{ alignItems: 'center', justifyContent: 'flex-end', width: 12, height: 55 }}>
          <View style={{ position: 'absolute', bottom: c.lw + c.b, width: 1.5, height: c.uw, backgroundColor: color, borderRadius: 1 }} />
          <View style={{ position: 'absolute', bottom: c.lw,       width: 6,   height: c.b,  backgroundColor: color, borderRadius: 1 }} />
          <View style={{ position: 'absolute', bottom: 0,          width: 1.5, height: c.lw, backgroundColor: color, borderRadius: 1 }} />
        </View>
      );
    })}
  </View>
);

// ─── Floating price ticker ────────────────────────────────────────────────────
const FloatingTicker = ({ t }: { t: typeof FLOAT_TICKERS[0] }) => {
  const ty = useRef(new Animated.Value(0)).current;
  const op = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    let alive = true;
    const run = () => {
      if (!alive) return;
      ty.setValue(0);
      op.setValue(0);
      Animated.sequence([
        Animated.delay(t.delay % 10000),
        Animated.parallel([
          Animated.timing(ty, { toValue: -(SCREEN_H * 0.45), duration: 14000, useNativeDriver: true }),
          Animated.sequence([
            Animated.timing(op, { toValue: 0.38, duration: 2000, useNativeDriver: true }),
            Animated.delay(9000),
            Animated.timing(op, { toValue: 0, duration: 3000, useNativeDriver: true }),
          ]),
        ]),
      ]).start(({ finished }) => { if (finished && alive) run(); });
    };
    run();
    return () => { alive = false; };
  }, []);

  const col   = t.up ? '#22c55e' : '#f87171';
  const arrow = t.up ? '▲' : '▼';
  return (
    <Animated.View
      pointerEvents="none"
      style={{
        position: 'absolute',
        bottom: '18%',
        left: t.left as any,
        opacity: op,
        transform: [{ translateY: ty }],
      }}
    >
      <View style={{
        backgroundColor: 'rgba(11,22,32,0.80)',
        borderRadius: 8,
        paddingHorizontal: 9,
        paddingVertical: 5,
        borderWidth: 1,
        borderColor: col + '35',
      }}>
        <Text style={{ fontSize: 9, fontWeight: '700', color: '#64748b', letterSpacing: 0.4 }}>{t.pair}</Text>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 1 }}>
          <Text style={{ fontSize: 11, fontWeight: '800', color: '#CBD5E1' }}>{t.price}</Text>
          <Text style={{ fontSize: 9, fontWeight: '700', color: col }}>{arrow} {t.change}</Text>
        </View>
      </View>
    </Animated.View>
  );
};

// ─── ForexBackground (exported) ───────────────────────────────────────────────
interface ForexBackgroundProps {
  /** Whether to show the floating price tickers. Default true. */
  showTickers?: boolean;
}

export const ForexBackground: React.FC<ForexBackgroundProps> = ({ showTickers = true }) => (
  <View style={StyleSheet.absoluteFillObject} pointerEvents="none">
    {/* Base gradient */}
    <LinearGradient
      colors={['#0B1620', '#0D1B2A', '#091420', '#0C1C2C']}
      locations={[0, 0.3, 0.7, 1]}
      start={{ x: 0.2, y: 0 }}
      end={{ x: 0.8, y: 1 }}
      style={StyleSheet.absoluteFillObject}
    />

    {/* Trading grid */}
    <TradingGrid />

    {/* Stars */}
    {STARS.map((s, i) => <Star key={i} s={s} />)}

    {/* Scan line */}
    <ScanLine />

    {/* Candlestick chart */}
    <CandlestickRow />

    {/* Floating tickers */}
    {showTickers && FLOAT_TICKERS.map((t, i) => <FloatingTicker key={i} t={t} />)}

    {/* Glow blobs */}
    <View style={styles.glowTR} />
    <View style={styles.glowBL} />
  </View>
);

const styles = StyleSheet.create({
  gridH: {
    position: 'absolute',
    left: 0,
    right: 0,
    height: 1,
    backgroundColor: 'rgba(0,222,168,0.05)',
  },
  gridV: {
    position: 'absolute',
    top: 0,
    bottom: 0,
    width: 1,
    backgroundColor: 'rgba(0,222,168,0.04)',
  },
  candleArea: {
    position: 'absolute',
    bottom: 28,
    left: 0,
    right: 0,
    flexDirection: 'row',
    justifyContent: 'space-evenly',
    paddingHorizontal: 10,
    opacity: 0.2,
    alignItems: 'flex-end',
  },
  glowTR: {
    position: 'absolute',
    top: -130,
    right: -130,
    width: 340,
    height: 340,
    borderRadius: 170,
    backgroundColor: '#22c55e',
    opacity: 0.04,
  },
  glowBL: {
    position: 'absolute',
    bottom: -100,
    left: -100,
    width: 260,
    height: 260,
    borderRadius: 130,
    backgroundColor: '#22c55e',
    opacity: 0.03,
  },
});
