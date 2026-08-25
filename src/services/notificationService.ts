/**
 * Servicio para enviar Push Notifications usando Expo Push Notifications
 *
 * Expo Push Notifications permite enviar notificaciones a dispositivos móviles
 * incluso cuando la app está cerrada o en segundo plano.
 */
import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import Constants from 'expo-constants';
import { Platform } from 'react-native';
import axios from 'axios';

// Configurar comportamiento de notificaciones
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: false,
    shouldSetBadge: true,
  }),
});

// URL del backend
const API_URL = 'https://qoricash-trading-v2.onrender.com';

export const notificationService = {
  /**
   * Registrar token de push notification
   */
  async registerForPushNotifications(dni: string): Promise<string | null> {
    try {
      // Verificar que sea dispositivo físico
      if (!Device.isDevice) {
        console.log('⚠️ Push notifications solo funcionan en dispositivos físicos');
        return null;
      }

      // Solicitar permisos
      const { status: existingStatus } = await Notifications.getPermissionsAsync();
      let finalStatus = existingStatus;

      if (existingStatus !== 'granted') {
        const { status } = await Notifications.requestPermissionsAsync();
        finalStatus = status;
      }

      if (finalStatus !== 'granted') {
        console.log('⚠️ Permisos de notificación denegados');
        return null;
      }

      // Obtener token de Expo
      // NOTA: Para producción, se necesita configurar projectId en app.json
      // Para desarrollo local con Expo Go, las push notifications están deshabilitadas
      let token: string;
      try {
        const projectId = Constants.expoConfig?.extra?.eas?.projectId;
        if (!projectId) {
          console.log('⚠️ ProjectId no configurado - Push notifications deshabilitadas en desarrollo');
          console.log('💡 Para habilitar push notifications, configura projectId en app.json');
          return null;
        }

        const tokenData = await Notifications.getExpoPushTokenAsync({
          projectId: projectId,
        });
        token = tokenData.data;
      } catch (tokenError: any) {
        console.log('⚠️ No se pudo obtener token de push (normal en desarrollo local)');
        console.log('💡 Las notificaciones push funcionarán cuando la app esté en producción');
        return null;
      }

      console.log('📲 Token de Expo obtenido:', token);

      // Enviar token al backend
      try {
        const response = await axios.post(
          `${API_URL}/api/client/register-push-token`,
          {
            dni: dni,
            push_token: token,
          }
        );

        if (response.data.success) {
          console.log('✅ Token registrado en backend exitosamente');
          return token;
        } else {
          console.error('❌ Error registrando token:', response.data.message);
          return null;
        }
      } catch (backendError) {
        console.error('❌ Error enviando token al backend:', backendError);
        return null;
      }
    } catch (error) {
      console.error('❌ Error en registerForPushNotifications:', error);
      return null;
    }
  },

  /**
   * Configurar listeners de notificaciones
   */
  setupNotificationListeners(
    onNotificationReceived?: (notification: Notifications.Notification) => void,
    onNotificationTapped?: (response: Notifications.NotificationResponse) => void
  ) {
    // Listener para notificaciones recibidas
    const receivedListener = Notifications.addNotificationReceivedListener(notification => {
      console.log('🔔 Notificación recibida:', notification);
      if (onNotificationReceived) {
        onNotificationReceived(notification);
      }
    });

    // Listener para cuando se toca la notificación
    const responseListener = Notifications.addNotificationResponseReceivedListener(response => {
      console.log('👆 Notificación tocada:', response);
      if (onNotificationTapped) {
        onNotificationTapped(response);
      }
    });

    // Retornar función de limpieza
    return () => {
      receivedListener.remove();
      responseListener.remove();
    };
  },

  /**
   * Configurar canal de notificaciones para Android
   */
  async setupAndroidNotificationChannel() {
    if (Platform.OS === 'android') {
      await Notifications.setNotificationChannelAsync('default', {
        name: 'QoriCash Notifications',
        importance: Notifications.AndroidImportance.MAX,
        vibrationPattern: [0, 250, 250, 250],
        lightColor: '#1976D2',
        sound: 'default',
      });
      console.log('✅ Canal de notificaciones Android configurado');
    }
  },

  /**
   * Mostrar notificación local (para testing)
   */
  async showLocalNotification(title: string, body: string, data?: any) {
    await Notifications.scheduleNotificationAsync({
      content: {
        title: title,
        body: body,
        data: data || {},
        sound: 'default',
      },
      trigger: null, // Mostrar inmediatamente
    });
  },
};
