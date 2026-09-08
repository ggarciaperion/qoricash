import React, { useRef, useEffect, useState } from 'react';
import {
  View,
  TouchableOpacity,
  StyleSheet,
  Animated,
  Text,
} from 'react-native';
import { BlurView } from 'expo-blur';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import * as Haptics from 'expo-haptics';

const TAB_COUNT = 4;
const PILL_W    = 62;
const PILL_H    = 50;
const ACTIVE    = '#0D1117';
const DIM       = '#9CA3AF';

const TABS = [
  { key: 'HomeTab',    label: 'Inicio',    icon: 'home-outline'         as const, iconFocused: 'home'          as const },
  { key: 'HistoryTab', label: 'Historial', icon: 'time-outline'         as const, iconFocused: 'time'          as const },
  { key: 'MarketTab',  label: 'Mercado',   icon: 'trending-up-outline'  as const, iconFocused: 'trending-up'   as const },
  { key: 'ProfileTab', label: 'Perfil',    icon: 'person-outline'       as const, iconFocused: 'person'        as const },
];

interface Props { state: any; navigation: any }

export const CustomTabBar: React.FC<Props> = ({ state, navigation }) => {
  const insets = useSafeAreaInsets();
  const [barWidth, setBarWidth] = useState(0);
  const tabW = barWidth > 0 ? barWidth / TAB_COUNT : 0;

  // Pill slide — starts at 0, snaps to correct position once barWidth is known
  const pillX = useRef(new Animated.Value(0)).current;

  // Per-tab press scale
  const sc = [
    useRef(new Animated.Value(1)).current,
    useRef(new Animated.Value(1)).current,
    useRef(new Animated.Value(1)).current,
    useRef(new Animated.Value(1)).current,
  ];

  // Per-tab icon opacity (active = 1, inactive = 0.35)
  const ops = [
    useRef(new Animated.Value(state.index === 0 ? 1 : 0.65)).current,
    useRef(new Animated.Value(state.index === 1 ? 1 : 0.65)).current,
    useRef(new Animated.Value(state.index === 2 ? 1 : 0.65)).current,
    useRef(new Animated.Value(state.index === 3 ? 1 : 0.65)).current,
  ];

  // Snap pill instantly when barWidth resolves
  useEffect(() => {
    if (tabW > 0) {
      pillX.setValue(state.index * tabW + tabW / 2 - PILL_W / 2);
    }
  }, [tabW]);

  // Animate pill when tab changes
  useEffect(() => {
    if (tabW === 0) return;
    Animated.spring(pillX, {
      toValue: state.index * tabW + tabW / 2 - PILL_W / 2,
      tension: 220,
      friction: 15,
      useNativeDriver: true,
    }).start();

    // Fade icons
    ops.forEach((op, i) => {
      Animated.timing(op, {
        toValue: state.index === i ? 1 : 0.65,
        duration: 180,
        useNativeDriver: true,
      }).start();
    });
  }, [state.index, tabW]);

  const handlePress = (i: number) => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);

    // Bounce press
    Animated.sequence([
      Animated.timing(sc[i], { toValue: 0.80, duration: 70, useNativeDriver: true }),
      Animated.spring(sc[i], { toValue: 1, tension: 250, friction: 7, useNativeDriver: true }),
    ]).start();

    if (state.index !== i) {
      navigation.navigate(TABS[i].key);
    }
  };

  return (
    <View style={[styles.wrap, { paddingBottom: Math.max(insets.bottom, 6) }]}>

      {/* Fondo blanco con blur suave */}
      <BlurView intensity={80} tint="light" style={StyleSheet.absoluteFill} />
      <View style={[StyleSheet.absoluteFill, { backgroundColor: 'rgba(255,255,255,0.92)' }]} />

      {/* Hairline border top */}
      <View style={styles.hairline} />

      {/* Sliding pill */}
      <Animated.View style={[styles.pill, { transform: [{ translateX: pillX }] }]} />

      {/* Tabs */}
      <View style={styles.row} onLayout={(e) => setBarWidth(e.nativeEvent.layout.width)}>
        {TABS.map((tab, i) => {
          const focused   = state.index === i;
          const iconName  = focused ? tab.iconFocused : tab.icon;

          return (
            <TouchableOpacity
              key={tab.key}
              style={styles.tab}
              onPress={() => handlePress(i)}
              activeOpacity={1}
            >
              <Animated.View style={[styles.inner, { transform: [{ scale: sc[i] }] }]}>
                <Animated.View style={{ opacity: ops[i] }}>
                  <Ionicons
                    name={iconName}
                    size={22}
                    color={focused ? ACTIVE : '#6B7280'}
                  />
                </Animated.View>
                <Animated.Text
                  style={[styles.label, focused && styles.labelOn, { opacity: ops[i] }]}
                >
                  {tab.label}
                </Animated.Text>
              </Animated.View>
            </TouchableOpacity>
          );
        })}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  wrap: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    overflow: 'hidden',
  },
  hairline: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    height: StyleSheet.hairlineWidth * 2,
    backgroundColor: 'rgba(0,0,0,0.08)',
  },
  pill: {
    position: 'absolute',
    top: 6,
    width: PILL_W,
    height: PILL_H,
    borderRadius: PILL_H / 2,
    backgroundColor: 'rgba(13,17,23,0.08)',
    borderWidth: 1,
    borderColor: 'rgba(13,17,23,0.12)',
  },
  row: {
    flexDirection: 'row',
    paddingTop: 10,
  },
  tab: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: 4,
  },
  inner: {
    alignItems: 'center',
    gap: 3,
  },
  label: {
    fontSize: 10,
    fontWeight: '600',
    color: DIM,
    letterSpacing: 0.3,
  },
  labelOn: {
    color: ACTIVE,
    fontWeight: '700',
  },
});
