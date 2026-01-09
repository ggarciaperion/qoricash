import React, { useEffect, useState } from 'react';
import { StatusBar } from 'expo-status-bar';
import { Provider as PaperProvider, MD3LightTheme } from 'react-native-paper';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import * as Notifications from 'expo-notifications';
import { Platform, View, StyleSheet, Alert } from 'react-native';

import { AuthProvider } from './src/contexts/AuthContext';
import { AppNavigator } from './src/navigation/AppNavigator';
import { SplashScreen } from './src/components/SplashScreen';
import { Colors } from './src/constants/colors';
import { notificationService } from './src/services/notificationService';

// Custom Theme - QoriCash
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

  useEffect(() => {
    // Configurar canal de notificaciones para Android
    notificationService.setupAndroidNotificationChannel();

    // Configurar listeners de notificaciones
    const cleanup = notificationService.setupNotificationListeners(
      // Cuando se recibe notificación (app abierta)
      (notification) => {
        console.log('🔔 [APP] Notificación recibida:', notification);

        // Mostrar alerta si es operación expirada
        if (notification.request.content.data?.type === 'operation_expired') {
          Alert.alert(
            '⏱️ Operación Expirada',
            'Tu operación ha expirado por falta de comprobante. Puedes crear una nueva operación.',
            [{ text: 'Entendido', style: 'default' }]
          );
        }
      },
      // Cuando se toca la notificación
      (response) => {
        console.log('👆 [APP] Notificación tocada:', response);
        const data = response.notification.request.content.data;

        // Si es notificación de operación expirada, mostrar info adicional
        if (data?.type === 'operation_expired') {
          Alert.alert(
            '⏱️ Operación Expirada',
            'Tu operación fue cancelada automáticamente porque no se subió el comprobante a tiempo.',
            [{ text: 'Entendido', style: 'default' }]
          );
        }
      }
    );

    // Limpiar listeners al desmontar
    return cleanup;
  }, []);

  // Mostrar SplashScreen primero
  if (showSplash) {
    return <SplashScreen onFinish={() => setShowSplash(false)} />;
  }

  return (
    <SafeAreaProvider>
      <PaperProvider theme={theme}>
        <View style={styles.container}>
          <View style={styles.mobileContainer}>
            <AuthProvider>
              <AppNavigator />
              <StatusBar style="auto" />
            </AuthProvider>
          </View>
        </View>
      </PaperProvider>
    </SafeAreaProvider>
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
