import React, { useEffect, useState, useRef, useCallback } from 'react';
import { StatusBar } from 'react-native';
import { Provider as PaperProvider, MD3LightTheme } from 'react-native-paper';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { Platform, View, StyleSheet, Alert, Animated } from 'react-native';
import { Asset } from 'expo-asset';
import { useFonts } from 'expo-font';

// Montserrat
import {
  Montserrat_600SemiBold,
  Montserrat_700Bold,
  Montserrat_800ExtraBold,
} from '@expo-google-fonts/montserrat';

// Inter
import {
  Inter_400Regular,
  Inter_500Medium,
  Inter_600SemiBold,
  Inter_700Bold,
} from '@expo-google-fonts/inter';

// Poppins
import {
  Poppins_400Regular,
  Poppins_500Medium,
  Poppins_600SemiBold,
  Poppins_700Bold,
} from '@expo-google-fonts/poppins';

import { AuthProvider } from './src/contexts/AuthContext';
import { LoginLoadingProvider } from './src/contexts/LoginLoadingContext';
import { AppNavigator } from './src/navigation/AppNavigator';
import { SplashScreen } from './src/components/SplashScreen';
import { Colors } from './src/constants/colors';
import { notificationService } from './src/services/notificationService';

// Precarga de assets
Asset.loadAsync([
  require('./assets/ddd_bg.jpg'),
  require('./assets/logo.png'),
]).catch(() => {});

const theme = {
  ...MD3LightTheme,
  colors: {
    ...MD3LightTheme.colors,
    primary: Colors.primary,
    secondary: Colors.secondary,
    error: Colors.danger,
    success: Colors.success,
    background: Colors.background,
    surface: Colors.surface,
    onPrimary: Colors.textOnPrimary,
    onSecondary: Colors.textOnSecondary,
  },
};

export default function App() {
  const [showSplash, setShowSplash] = useState(true);
  const contentOp = useRef(new Animated.Value(0)).current;

  const handleSplashFinish = useCallback(() => {
    setShowSplash(false);
    Animated.timing(contentOp, {
      toValue: 1,
      duration: 480,
      delay: 60,
      useNativeDriver: true,
    }).start();
  }, [contentOp]);

  const [fontsLoaded] = useFonts({
    // Montserrat — wordmark institucional
    Montserrat_600SemiBold,
    Montserrat_700Bold,
    Montserrat_800ExtraBold,
    // Inter — UI principal (Stripe, Wise, Revolut)
    Inter_400Regular,
    Inter_500Medium,
    Inter_600SemiBold,
    Inter_700Bold,
    // Poppins — alternativa moderna redondeada
    Poppins_400Regular,
    Poppins_500Medium,
    Poppins_600SemiBold,
    Poppins_700Bold,
  });

  useEffect(() => {
    // Forzar barra de estado visible con iconos claros en todas las pantallas
    StatusBar.setBarStyle('light-content', true);
    if (Platform.OS === 'android') {
      StatusBar.setBackgroundColor('transparent', true);
      StatusBar.setTranslucent(true);
    }

    notificationService.setupAndroidNotificationChannel();

    const cleanup = notificationService.setupNotificationListeners(
      (notification) => {
        if (notification.request.content.data?.type === 'operation_expired') {
          Alert.alert(
            '⏱️ Operación Expirada',
            'Tu operación ha expirado por falta de comprobante. Puedes crear una nueva operación.',
            [{ text: 'Entendido', style: 'default' }]
          );
        }
      },
      (response) => {
        const data = response.notification.request.content.data;
        if (data?.type === 'operation_expired') {
          Alert.alert(
            '⏱️ Operación Expirada',
            'Tu operación fue cancelada automáticamente porque no se subió el comprobante a tiempo.',
            [{ text: 'Entendido', style: 'default' }]
          );
        }
      }
    );

    return cleanup;
  }, []);

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <PaperProvider theme={theme}>
          <View style={styles.container}>
            <Animated.View style={[styles.mobileContainer, { opacity: contentOp }]}>
              <AuthProvider>
                <LoginLoadingProvider>
                  <AppNavigator />
                  <StatusBar
                    barStyle="light-content"
                    backgroundColor="transparent"
                    translucent
                  />
                </LoginLoadingProvider>
              </AuthProvider>
            </Animated.View>
          </View>

          {showSplash && (
            <SplashScreen onFinish={handleSplashFinish} />
          )}
        </PaperProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#E0E0E0',
    alignItems: 'center',
  },
  mobileContainer: {
    flex: 1,
    width: '100%',
    maxWidth: Platform.OS === 'web' ? 430 : undefined,
    backgroundColor: '#FFF',
  },
});
