import React, { useState, useEffect } from 'react';
import { createStackNavigator } from '@react-navigation/stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { NavigationContainer } from '@react-navigation/native';
import { Icon } from 'react-native-paper';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { View, ImageBackground, StyleSheet } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { BlurView } from 'expo-blur';

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
      tabBar={(props) => <CustomTabBar {...props} />}
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
      {/* Fondo fijo — nunca transiciona, compartido por todas las pantallas auth */}
      <ImageBackground
        source={require('../../assets/cd.png')}
        style={StyleSheet.absoluteFill}
        resizeMode="cover"
      />

      {/* Stack con cards transparentes — el fondo es fijo, solo transiciona el contenido */}
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
        <Stack.Screen name="PublicCalculator" component={PublicCalculatorScreen} />
        <Stack.Screen name="Login" component={LoginScreen} />
        <Stack.Screen name="ClientTypeSelection" component={ClientTypeSelectionScreen} />
        <Stack.Screen name="Register" component={RegisterScreen} />
        <Stack.Screen name="RegisterWithGoogle" component={RegisterWithGoogleScreen} />
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
        options={{
          title: 'Cambiar Contraseña',
          headerTintColor: Colors.primary,
        }}
      />
      <Stack.Screen
        name="VerifyIdentity"
        component={VerifyIdentityScreen}
        options={{
          title: 'Validación de Identidad',
          headerTintColor: Colors.primary,
        }}
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

// Root Navigator
export const AppNavigator = () => {
  const { isAuthenticated, loading, client, logout } = useAuth();
  const { showLoginLoading, setShowLoginLoading, showLogoutLoading, setShowLogoutLoading } = useLoginLoading();
  const [requiresPasswordChange, setRequiresPasswordChange] = useState(false);

  useEffect(() => {
    checkPasswordChangeRequired();
  }, [isAuthenticated, client]);

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
      <NavigationContainer>
        {shouldShowAuthScreen ? (
          <AuthNavigator />
        ) : isAuthenticated ? (
          requiresPasswordChange ? (
            <Stack.Navigator screenOptions={{ headerShown: false }}>
              <Stack.Screen
                name="ChangePassword"
                component={ChangePasswordScreen}
                initialParams={{ isFirstLogin: true, dni: client?.dni }}
                options={{
                  headerShown: true,
                  title: 'Cambiar Contraseña',
                  headerTintColor: Colors.primary,
                  headerLeft: () => null, // Evitar que puedan regresar
                }}
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
    </View>
  );
};
