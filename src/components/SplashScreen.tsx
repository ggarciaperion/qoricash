import React, { useEffect, useRef } from 'react';
import {
  View,
  Image,
  Animated,
  StyleSheet,
  Dimensions,
  Text,
} from 'react-native';
import { Colors } from '../constants/colors';
import { ForexBackground } from './ForexBackground';

const { width, height } = Dimensions.get('window');

interface SplashScreenProps {
  onFinish: () => void;
}

const PRICE_STRIP = [
  { pair: 'USD/PEN', price: '3.725', up: true  },
  { pair: 'EUR/USD', price: '1.082', up: false },
  { pair: 'GBP/PEN', price: '4.713', up: true  },
];

export const SplashScreen: React.FC<SplashScreenProps> = ({ onFinish }) => {
  // ── animations
  const logoOpacity   = useRef(new Animated.Value(0)).current;
  const logoScale     = useRef(new Animated.Value(0.7)).current;
  const brandOpacity  = useRef(new Animated.Value(0)).current;
  const brandY        = useRef(new Animated.Value(16)).current;
  const tagOpacity    = useRef(new Animated.Value(0)).current;
  const tagY          = useRef(new Animated.Value(12)).current;
  const stripOpacity  = useRef(new Animated.Value(0)).current;
  const stripY        = useRef(new Animated.Value(20)).current;
  const screenOpacity = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    // ── staggered entrance
    Animated.sequence([
      // 1. Logo (0ms)
      Animated.parallel([
        Animated.timing(logoOpacity, { toValue: 1, duration: 550, useNativeDriver: true }),
        Animated.spring(logoScale,   { toValue: 1, tension: 50, friction: 7, useNativeDriver: true }),
      ]),

      // 2. Brand name (+350ms after logo starts fading in → overlap with parallel)
      Animated.delay(0),
    ]).start();

    // Brand enters 350ms after start
    setTimeout(() => {
      Animated.parallel([
        Animated.timing(brandOpacity, { toValue: 1, duration: 400, useNativeDriver: true }),
        Animated.timing(brandY,       { toValue: 0, duration: 400, useNativeDriver: true }),
      ]).start();
    }, 350);

    // Tagline enters 600ms after start
    setTimeout(() => {
      Animated.parallel([
        Animated.timing(tagOpacity, { toValue: 1, duration: 400, useNativeDriver: true }),
        Animated.timing(tagY,       { toValue: 0, duration: 400, useNativeDriver: true }),
      ]).start();
    }, 600);

    // Price strip enters 900ms after start
    setTimeout(() => {
      Animated.parallel([
        Animated.timing(stripOpacity, { toValue: 1, duration: 500, useNativeDriver: true }),
        Animated.timing(stripY,       { toValue: 0, duration: 500, useNativeDriver: true }),
      ]).start();
    }, 900);

    // ── exit at 3.2s
    const exitTimer = setTimeout(() => {
      Animated.timing(screenOpacity, {
        toValue: 0,
        duration: 450,
        useNativeDriver: true,
      }).start(() => onFinish());
    }, 3200);

    return () => clearTimeout(exitTimer);
  }, []);

  return (
    <Animated.View style={[styles.root, { opacity: screenOpacity }]}>
      <ForexBackground showTickers={false} />

      {/* ── Center content */}
      <View style={styles.center}>
        {/* Logo */}
        <Animated.View
          style={[
            styles.logoWrapper,
            { opacity: logoOpacity, transform: [{ scale: logoScale }] },
          ]}
        >
          <Image
            source={require('../../assets/logo-principal.png')}
            style={styles.logo}
            resizeMode="contain"
          />
        </Animated.View>

        {/* Brand name */}
        <Animated.View
          style={{ opacity: brandOpacity, transform: [{ translateY: brandY }] }}
        >
          <Text style={styles.brandName}>QoriCash</Text>
        </Animated.View>

        {/* Tagline */}
        <Animated.View
          style={{ opacity: tagOpacity, transform: [{ translateY: tagY }] }}
        >
          <Text style={styles.tagline}>Tu casa de cambio digital</Text>
        </Animated.View>
      </View>

      {/* ── Bottom price strip */}
      <Animated.View
        style={[
          styles.priceStrip,
          { opacity: stripOpacity, transform: [{ translateY: stripY }] },
        ]}
      >
        {PRICE_STRIP.map((item, i) => (
          <View key={i} style={styles.priceItem}>
            <Text style={styles.pricePair}>{item.pair}</Text>
            <Text style={[styles.priceValue, { color: item.up ? Colors.primary : '#f87171' }]}>
              {item.up ? '▲ ' : '▼ '}{item.price}
            </Text>
          </View>
        ))}
      </Animated.View>
    </Animated.View>
  );
};

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: '#0B1620',
  },
  center: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingBottom: 80,
  },
  logoWrapper: {
    width: width * 0.55,
    height: width * 0.38,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 20,
  },
  logo: {
    width: '100%',
    height: '100%',
  },
  brandName: {
    fontSize: 40,
    fontWeight: '800',
    color: '#F1F5F9',
    letterSpacing: 1.5,
    textAlign: 'center',
    marginBottom: 10,
  },
  tagline: {
    fontSize: 14,
    fontWeight: '500',
    color: '#64748B',
    letterSpacing: 1.0,
    textAlign: 'center',
    textTransform: 'uppercase',
  },

  // ── Price strip
  priceStrip: {
    position: 'absolute',
    bottom: 52,
    left: 24,
    right: 24,
    flexDirection: 'row',
    justifyContent: 'space-around',
    alignItems: 'center',
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.08)',
    borderRadius: 14,
    paddingVertical: 12,
    paddingHorizontal: 8,
  },
  priceItem: {
    alignItems: 'center',
    flex: 1,
  },
  pricePair: {
    fontSize: 10,
    fontWeight: '700',
    color: '#475569',
    letterSpacing: 0.8,
    textTransform: 'uppercase',
    marginBottom: 4,
  },
  priceValue: {
    fontSize: 14,
    fontWeight: '700',
    letterSpacing: 0.3,
  },
});
