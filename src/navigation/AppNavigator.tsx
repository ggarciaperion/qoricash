import React, { useState, useEffect, useRef } from 'react';
import { createStackNavigator } from '@react-navigation/stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { NavigationContainer, CommonActions } from '@react-navigation/native';
import { Icon } from 'react-native-paper';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { View, StyleSheet, Modal, Text, TouchableOpacity, Animated, Easing, Linking, Alert } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { BlurView } from 'expo-blur';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import socketService from '../services/socketService';

import { useAuth } from '../contexts/AuthContext';
import { useLoginLoading } from '../contexts/LoginLoadingContext';
import { Colors } from '../constants/colors';
import { STORAGE_KEYS } from '../constants/config';
import { LoginLoadingScreen } from '../components/LoginLoadingScreen';
import { LogoutOverlay } from '../components/LogoutOverlay';
import { CustomTabBar } from '../components/CustomTabBar';

// Auth Screens
import { LoginScreen } from '../screens/LoginScreen';
import { PublicCalculatorScreen } from '../screens/PublicCalculatorScreen';
import { ClientTypeSelectionScreen } from '../screens/ClientTypeSelectionScreen';
import { RegisterScreen } from '../screens/RegisterScreen';
import { RegisterSuccessScreen } from '../screens/RegisterSuccessScreen';
import { RegisterWithGoogleScreen } from '../screens/RegisterWithGoogleScreen';
import { ChangePasswordScreen } from '../screens/ChangePasswordScreen';
import { VerifyIdentityScreen } from '../screens/VerifyIdentityScreen';

// Main Screens
import { HomeScreen } from '../screens/HomeScreen';
import { NewOperationScreen } from '../screens/NewOperationScreen';
import { TransferScreen } from '../screens/TransferScreen';
import { ReceiveScreen } from '../screens/ReceiveScreen';
import { OperationDetailScreen } from '../screens/OperationDetailScreen';
import { HistoryScreen } from '../screens/HistoryScreen';
import { MarketScreen } from '../screens/MarketScreen';
import { ProfileScreen } from '../screens/ProfileScreen';
import { LogsScreen } from '../screens/LogsScreen';
import { WebViewScreen } from '../screens/WebViewScreen';

const Stack = createStackNavigator();
const Tab = createBottomTabNavigator();

// Tab Navigator for authenticated users
const TabNavigator = () => {
  return (
    <Tab.Navigator
      tabBar={(props) => props.state.index === 0 ? null : <CustomTabBar {...props} />}
      screenOptions={{
        headerShown: false,
        sceneStyle: { backgroundColor: 'transparent' },
      }}
    >
      <Tab.Screen name="HomeTab"    component={HomeScreen}    options={{ title: 'Inicio' }} />
      <Tab.Screen name="HistoryTab" component={HistoryScreen} options={{ title: 'Historial' }} />
      <Tab.Screen name="MarketTab"  component={MarketScreen}  options={{ title: 'Mercado', headerShown: false }} />
      <Tab.Screen name="ProfileTab" component={ProfileScreen} options={{ title: 'Perfil' }} />
    </Tab.Navigator>
  );
};

// Auth Navigator
const AuthNavigator = () => {
  return (
    <View style={{ flex: 1 }}>
      <Stack.Navigator
        screenOptions={{
          headerShown: false,
          cardStyle: { backgroundColor: 'transparent' },
          cardOverlayEnabled: false,
          cardStyleInterpolator: ({ current, next, layouts }) => ({
            cardStyle: {
              // Entrada: slide desde derecha + fade in sutil
              opacity: current.progress.interpolate({
                inputRange:  [0, 0.4, 1],
                outputRange: [0, 0.7, 1],
                extrapolate: 'clamp',
              }),
              transform: [
                {
                  translateX: current.progress.interpolate({
                    inputRange:  [0, 1],
                    outputRange: [layouts.screen.width * 0.28, 0],
                    extrapolate: 'clamp',
                  }),
                },
                {
                  scale: current.progress.interpolate({
                    inputRange:  [0, 1],
                    outputRange: [0.96, 1],
                    extrapolate: 'clamp',
                  }),
                },
              ],
              // Salida: pantalla anterior se encoge y se desvanece
              ...(next && {
                opacity: next.progress.interpolate({
                  inputRange:  [0, 0.3],
                  outputRange: [1, 0],
                  extrapolate: 'clamp',
                }),
              }),
            },
          }),
          transitionSpec: {
            open:  { animation: 'spring', config: { stiffness: 380, damping: 38, mass: 1, overshootClamping: false } },
            close: { animation: 'spring', config: { stiffness: 380, damping: 38, mass: 1, overshootClamping: false } },
          },
        }}
      >
        <Stack.Screen name="PublicCalculator" component={PublicCalculatorScreen} options={{ cardStyle: { backgroundColor: '#F5F7FA' } }} />
        <Stack.Screen name="Login" component={LoginScreen} />
        <Stack.Screen name="ClientTypeSelection" component={ClientTypeSelectionScreen} />
        <Stack.Screen name="Register" component={RegisterScreen} />
        <Stack.Screen
          name="RegisterSuccess"
          component={RegisterSuccessScreen}
          options={{
            gestureEnabled: false,
            cardStyleInterpolator: ({ current }) => ({
              cardStyle: { opacity: current.progress },
            }),
            transitionSpec: {
              open:  { animation: 'timing', config: { duration: 380 } },
              close: { animation: 'timing', config: { duration: 300 } },
            },
          }}
        />
        <Stack.Screen name="RegisterWithGoogle" component={RegisterWithGoogleScreen} />
        <Stack.Screen name="WebView" component={WebViewScreen} />
      </Stack.Navigator>
    </View>
  );
};

// Main Navigator
const MainNavigator = () => {
  return (
    <Stack.Navigator
      screenOptions={{
        cardStyle: { backgroundColor: 'transparent' },
        cardOverlayEnabled: false,
      }}
    >
      <Stack.Screen
        name="Tabs"
        component={TabNavigator}
        options={{ headerShown: false }}
      />
      <Stack.Screen
        name="NewOperation"
        component={NewOperationScreen}
        options={{
          headerShown: false,
          cardStyleInterpolator: ({ current, next, layouts }) => ({
            cardStyle: {
              opacity: current.progress.interpolate({
                inputRange:  [0, 0.5, 1],
                outputRange: [0, 0.6, 1],
                extrapolate: 'clamp',
              }),
              transform: [
                {
                  translateY: current.progress.interpolate({
                    inputRange:  [0, 1],
                    outputRange: [layouts.screen.height * 0.06, 0],
                    extrapolate: 'clamp',
                  }),
                },
                {
                  scale: current.progress.interpolate({
                    inputRange:  [0, 1],
                    outputRange: [0.97, 1],
                    extrapolate: 'clamp',
                  }),
                },
              ],
              ...(next && {
                opacity: next.progress.interpolate({
                  inputRange:  [0, 0.3],
                  outputRange: [1, 0],
                  extrapolate: 'clamp',
                }),
              }),
            },
          }),
          transitionSpec: {
            open:  { animation: 'spring', config: { stiffness: 280, damping: 36, mass: 1, overshootClamping: false } },
            close: { animation: 'spring', config: { stiffness: 280, damping: 36, mass: 1, overshootClamping: false } },
          },
        }}
      />
      <Stack.Screen
        name="Transfer"
        component={TransferScreen}
        options={{
          headerShown: false,
        }}
      />
      <Stack.Screen
        name="Receive"
        component={ReceiveScreen}
        options={{
          headerShown: false,
        }}
      />
      <Stack.Screen
        name="OperationDetail"
        component={OperationDetailScreen}
        options={{
          headerShown: false,
          cardStyleInterpolator: ({ current, next, layouts }) => ({
            cardStyle: {
              opacity: current.progress.interpolate({
                inputRange:  [0, 0.5, 1],
                outputRange: [0, 0.6, 1],
                extrapolate: 'clamp',
              }),
              transform: [
                {
                  translateY: current.progress.interpolate({
                    inputRange:  [0, 1],
                    outputRange: [layouts.screen.height * 0.06, 0],
                    extrapolate: 'clamp',
                  }),
                },
                {
                  scale: current.progress.interpolate({
                    inputRange:  [0, 1],
                    outputRange: [0.97, 1],
                    extrapolate: 'clamp',
                  }),
                },
              ],
              ...(next && {
                opacity: next.progress.interpolate({
                  inputRange:  [0, 0.4],
                  outputRange: [1, 0],
                  extrapolate: 'clamp',
                }),
              }),
            },
            overlayStyle: {
              opacity: current.progress.interpolate({
                inputRange:  [0, 1],
                outputRange: [0, 0.38],
                extrapolate: 'clamp',
              }),
            },
          }),
          transitionSpec: {
            open:  { animation: 'spring', config: { stiffness: 280, damping: 36, mass: 1, overshootClamping: false } },
            close: { animation: 'spring', config: { stiffness: 280, damping: 36, mass: 1, overshootClamping: false } },
          },
        }}
      />
      <Stack.Screen
        name="ChangePassword"
        component={ChangePasswordScreen}
        options={{ headerShown: false }}
      />
      <Stack.Screen
        name="VerifyIdentity"
        component={VerifyIdentityScreen}
        options={{ headerShown: false }}
      />
      <Stack.Screen
        name="Logs"
        component={LogsScreen}
        options={{
          title: 'Logs del Sistema',
          headerTintColor: Colors.primary,
        }}
      />
      <Stack.Screen
        name="WebView"
        component={WebViewScreen}
        options={{ headerShown: false }}
      />
    </Stack.Navigator>
  );
};

import { shownCancelAlerts } from '../utils/cancelAlertDedup';

// Root Navigator
export const AppNavigator = () => {
  const { isAuthenticated, loading, client, logout } = useAuth();
  const { showLoginLoading, setShowLoginLoading, showLogoutLoading, setShowLogoutLoading } = useLoginLoading();
  const [requiresPasswordChange, setRequiresPasswordChange] = useState(false);

  // ── Notificación global: operación completada ──
  const navRef            = useRef<any>(null);
  const [completedOpId,     setCompletedOpId]     = useState<string | null>(null);
  const [completedOpDbId,   setCompletedOpDbId]   = useState<number | null>(null);
  const [showCompleteAlert, setShowCompleteAlert] = useState(false);
  const completeScale   = useRef(new Animated.Value(0.82)).current;
  const completeOpacity = useRef(new Animated.Value(0)).current;
  const iconPulse       = useRef(new Animated.Value(1)).current;
  const iconGlow        = useRef(new Animated.Value(0.12)).current;
  const ring1S          = useRef(new Animated.Value(1)).current;
  const ring1O          = useRef(new Animated.Value(0.55)).current;
  const ring2S          = useRef(new Animated.Value(1)).current;
  const ring2O          = useRef(new Animated.Value(0.40)).current;

  useEffect(() => {
    if (!isAuthenticated || !client?.dni) return;

    socketService.connect(client.dni);

    const handleOperationCompleted = (data: any) => {
      const opId = data?.operation_id || '';
      setCompletedOpId(opId || null);
      setCompletedOpDbId(data?.id ?? null);
      setShowCompleteAlert(true);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      // Reset values
      completeScale.setValue(0.82);
      completeOpacity.setValue(0);
      iconPulse.setValue(1);
      iconGlow.setValue(0.12);
      ring1S.setValue(1); ring1O.setValue(0.55);
      ring2S.setValue(1); ring2O.setValue(0.40);
      // Card entrance
      Animated.parallel([
        Animated.spring(completeScale,   { toValue: 1, tension: 210, friction: 17, useNativeDriver: true }),
        Animated.timing(completeOpacity, { toValue: 1, duration: 200, useNativeDriver: true }),
      ]).start(() => {
        // Icon pulse loop
        Animated.loop(
          Animated.sequence([
            Animated.timing(iconPulse, { toValue: 1.10, duration: 800, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
            Animated.timing(iconPulse, { toValue: 1,    duration: 800, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
          ])
        ).start();
        // Icon glow pulse loop
        Animated.loop(
          Animated.sequence([
            Animated.timing(iconGlow, { toValue: 0.28, duration: 800, easing: Easing.inOut(Easing.ease), useNativeDriver: false }),
            Animated.timing(iconGlow, { toValue: 0.12, duration: 800, easing: Easing.inOut(Easing.ease), useNativeDriver: false }),
          ])
        ).start();
        // Ring ripple helper
        const ripple = (s: Animated.Value, o: Animated.Value, delay: number) =>
          Animated.loop(
            Animated.sequence([
              Animated.delay(delay),
              Animated.parallel([
                Animated.timing(s, { toValue: 2.4, duration: 1400, easing: Easing.out(Easing.quad), useNativeDriver: true }),
                Animated.timing(o, { toValue: 0,   duration: 1400, easing: Easing.out(Easing.quad), useNativeDriver: true }),
              ]),
              Animated.parallel([
                Animated.timing(s, { toValue: 1,    duration: 0, useNativeDriver: true }),
                Animated.timing(o, { toValue: 0.55, duration: 0, useNativeDriver: true }),
              ]),
            ])
          );
        ripple(ring1S, ring1O, 0).start();
        ripple(ring2S, ring2O, 650).start();
      });
    };

    // ── Global: operación cancelada por admin ──────────────────────────────
    const handleGlobalAdminCancel = (data: any) => {
      const opId  = data?.operation_id || data?.id || '';
      const key   = `cancel_${opId}`;
      if (shownCancelAlerts.has(key)) return;   // ya manejado por la pantalla específica
      shownCancelAlerts.add(key);
      setTimeout(() => shownCancelAlerts.delete(key), 5000);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
      const reason = data?.reason || data?.cancellation_reason || null;
      Alert.alert(
        '❌ Operación Cancelada',
        `Tu operación ${opId} fue cancelada por el equipo Qoricash.` +
        (reason ? `\n\nMotivo: ${reason}` : '') +
        '\n\nSi tienes alguna duda, contáctanos por WhatsApp.',
        [{ text: 'Entendido' }],
        { cancelable: false }
      );
    };

    // ── Global: operación expirada por tiempo ──────────────────────────────
    const handleGlobalExpired = (data: any) => {
      const opId = data?.operation_id || '';
      const key  = `expired_${opId}`;
      if (shownCancelAlerts.has(key)) return;   // ya manejado por TransferScreen
      shownCancelAlerts.add(key);
      setTimeout(() => shownCancelAlerts.delete(key), 5000);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
      Alert.alert(
        '⏱️ Operación Cancelada',
        `Tu operación ${opId} fue cancelada automáticamente por vencer el tiempo límite sin confirmación.\n\nPuedes crear una nueva operación desde el inicio.`,
        [{ text: 'Entendido' }],
        { cancelable: false }
      );
    };

    socketService.on('operacion_completada', handleOperationCompleted);
    socketService.on('operacion_cancelada_admin', handleGlobalAdminCancel);
    socketService.on('operation_expired', handleGlobalExpired);

    return () => {
      socketService.off('operacion_completada', handleOperationCompleted);
      socketService.off('operacion_cancelada_admin', handleGlobalAdminCancel);
      socketService.off('operation_expired', handleGlobalExpired);
    };
  }, [isAuthenticated, client?.dni]);

  useEffect(() => {
    checkPasswordChangeRequired();
  }, [isAuthenticated, client]);

  const dismissCompleteAlert = () => {
    iconPulse.stopAnimation(); iconGlow.stopAnimation();
    ring1S.stopAnimation();    ring1O.stopAnimation();
    ring2S.stopAnimation();    ring2O.stopAnimation();
    iconPulse.setValue(1); iconGlow.setValue(0.12);
    ring1S.setValue(1); ring1O.setValue(0.55);
    ring2S.setValue(1); ring2O.setValue(0.40);
    setShowCompleteAlert(false);
  };

  const checkPasswordChangeRequired = async () => {
    try {
      const flag = await AsyncStorage.getItem(STORAGE_KEYS.REQUIRES_PASSWORD_CHANGE);
      setRequiresPasswordChange(flag === 'true');
    } catch (error) {
      console.error('Error checking password change:', error);
      setRequiresPasswordChange(false);
    }
  };

  if (loading) {
    return null; // You can add a splash screen here
  }

  // Bloquear navegación mientras la animación de login está activa
  // Esto permite que la animación complete antes de mostrar el MainNavigator
  const shouldShowAuthScreen = !isAuthenticated || showLoginLoading;

  return (
    <View style={{ flex: 1, backgroundColor: '#000000' }}>
      <NavigationContainer ref={navRef}>
        {shouldShowAuthScreen ? (
          <AuthNavigator />
        ) : isAuthenticated ? (
          requiresPasswordChange ? (
            <Stack.Navigator screenOptions={{ headerShown: false }}>
              <Stack.Screen
                name="ChangePassword"
                component={ChangePasswordScreen}
                initialParams={{ isFirstLogin: true, dni: client?.dni }}
                options={{ headerShown: false }}
              />
            </Stack.Navigator>
          ) : (
            <MainNavigator />
          )
        ) : (
          <AuthNavigator />
        )}
      </NavigationContainer>

      {/* Login Loading Screen - Global overlay */}
      <LoginLoadingScreen
        visible={showLoginLoading}
        onComplete={() => setShowLoginLoading(false)}
      />

      {/* Logout Overlay - Global overlay */}
      <LogoutOverlay
        visible={showLogoutLoading}
        onLogout={logout}
        onComplete={() => setShowLogoutLoading(false)}
      />

      {/* ── Alerta global: operación completada ── */}
      <Modal
        visible={showCompleteAlert}
        transparent
        animationType="fade"
        statusBarTranslucent
        onRequestClose={dismissCompleteAlert}
      >
        <BlurView intensity={60} tint="dark" style={navS.alertBackdrop}>
          <Animated.View style={[navS.successCard, { opacity: completeOpacity, transform: [{ scale: completeScale }] }]}>

            {/* Icono con anillos expansivos */}
            <View style={navS.successIconOuter}>
              <Animated.View style={[navS.successRing, { transform: [{ scale: ring2S }], opacity: ring2O }]} />
              <Animated.View style={[navS.successRing, { transform: [{ scale: ring1S }], opacity: ring1O }]} />
              <Animated.View style={[navS.successIconCircle, { transform: [{ scale: iconPulse }] }]}>
                <Ionicons name="checkmark" size={34} color="#22c55e" />
              </Animated.View>
            </View>

            <Text style={navS.successTitle}>¡Operación completada!</Text>
            {completedOpId ? (
              <Text style={navS.successBody}>
                Tu operación <Text style={navS.successOpId}>{completedOpId}</Text> fue procesada con éxito. Tu pago ha sido enviado.
              </Text>
            ) : (
              <Text style={navS.successBody}>
                Tu operación fue procesada con éxito. Tu pago ha sido enviado.
              </Text>
            )}

            {/* Botón ver operación */}
            <TouchableOpacity
              style={navS.successBtnPrimary}
              activeOpacity={0.82}
              onPress={() => {
                dismissCompleteAlert();
                setTimeout(() => {
                  if (completedOpDbId) {
                    navRef.current?.dispatch(
                      CommonActions.navigate({ name: 'OperationDetail', params: { operationId: completedOpDbId } })
                    );
                  } else {
                    navRef.current?.dispatch(
                      CommonActions.navigate({ name: 'HistoryTab' })
                    );
                  }
                }, 280);
              }}
            >
              <Ionicons name="receipt-outline" size={16} color="#22c55e" />
              <Text style={navS.successBtnPrimaryText}>Ver mi operación</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={navS.alertBtnClose}
              activeOpacity={0.7}
              onPress={dismissCompleteAlert}
            >
              <Text style={navS.alertBtnCloseText}>Entendido</Text>
            </TouchableOpacity>

          </Animated.View>
        </BlurView>
      </Modal>

    </View>
  );
};

const navS = StyleSheet.create({
  // ── Success modal ──
  successCard: {
    width: '100%',
    backgroundColor: 'rgba(255,255,255,0.15)',
    borderWidth: 1,
    borderColor: 'rgba(34,197,94,0.28)',
    borderRadius: 28,
    paddingVertical: 36,
    paddingHorizontal: 28,
    alignItems: 'center',
    shadowColor: '#22c55e',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.18,
    shadowRadius: 24,
    elevation: 16,
  },
  successIconOuter: {
    width: 80,
    height: 80,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 22,
  },
  successRing: {
    position: 'absolute',
    width: 72,
    height: 72,
    borderRadius: 36,
    borderWidth: 1.5,
    borderColor: 'rgba(34,197,94,0.50)',
    backgroundColor: 'transparent',
  },
  successIconCircle: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: 'rgba(34,197,94,0.13)',
    borderWidth: 1.5,
    borderColor: 'rgba(34,197,94,0.38)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  successTitle: {
    fontSize: 20,
    fontWeight: '800',
    color: '#fff',
    textAlign: 'center',
    letterSpacing: -0.3,
    marginBottom: 10,
  },
  successBody: {
    fontSize: 13.5,
    color: 'rgba(255,255,255,0.55)',
    textAlign: 'center',
    lineHeight: 21,
    marginBottom: 28,
  },
  successOpId: {
    color: '#22c55e',
    fontWeight: '700',
  },
  successBtnPrimary: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    width: '100%',
    backgroundColor: 'rgba(34,197,94,0.12)',
    borderWidth: 1,
    borderColor: 'rgba(34,197,94,0.30)',
    borderRadius: 14,
    paddingVertical: 15,
    marginBottom: 10,
  },
  successBtnPrimaryText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#22c55e',
    letterSpacing: 0.1,
  },
  // ── Cancel modal ──
  alertBackdrop: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 24,
  },
  alertCard: {
    width: '100%',
    backgroundColor: 'rgba(255,255,255,0.15)',
    borderWidth: 1,
    borderColor: 'rgba(239,68,68,0.25)',
    borderRadius: 24,
    paddingVertical: 32,
    paddingHorizontal: 24,
    alignItems: 'center',
  },
  alertIconWrap: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: 'rgba(239,68,68,0.10)',
    borderWidth: 1,
    borderColor: 'rgba(239,68,68,0.22)',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 20,
  },
  alertTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#fff',
    textAlign: 'center',
    letterSpacing: -0.2,
    marginBottom: 12,
  },
  alertBody: {
    fontSize: 13.5,
    color: 'rgba(255,255,255,0.55)',
    textAlign: 'center',
    lineHeight: 21,
    marginBottom: 14,
  },
  alertOpId: {
    color: 'rgba(255,255,255,0.82)',
    fontWeight: '700',
  },
  alertReasonBox: {
    width: '100%',
    backgroundColor: 'rgba(239,68,68,0.08)',
    borderWidth: 1,
    borderColor: 'rgba(239,68,68,0.18)',
    borderRadius: 12,
    paddingVertical: 12,
    paddingHorizontal: 14,
    marginBottom: 14,
  },
  alertReasonLabel: {
    fontSize: 9,
    fontWeight: '700',
    color: 'rgba(239,68,68,0.7)',
    letterSpacing: 1.5,
    textTransform: 'uppercase',
    marginBottom: 5,
  },
  alertReasonText: {
    fontSize: 13,
    color: 'rgba(255,255,255,0.75)',
    lineHeight: 19,
    fontWeight: '400',
  },
  alertBodySub: {
    fontSize: 12,
    color: 'rgba(255,255,255,0.35)',
    textAlign: 'center',
    marginBottom: 24,
  },
  alertBtnWa: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    width: '100%',
    backgroundColor: '#25D366',
    borderRadius: 14,
    paddingVertical: 14,
    marginBottom: 10,
    shadowColor: '#25D366',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.30,
    shadowRadius: 10,
    elevation: 5,
  },
  alertBtnWaText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#fff',
    letterSpacing: 0.1,
  },
  alertBtnClose: {
    paddingVertical: 10,
    paddingHorizontal: 24,
  },
  alertBtnCloseText: {
    fontSize: 13,
    color: 'rgba(255,255,255,0.35)',
    fontWeight: '500',
  },
});
