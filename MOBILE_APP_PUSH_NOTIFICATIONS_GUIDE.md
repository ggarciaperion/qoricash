# Guía de Implementación: Push Notifications en App Móvil

## 📱 Objetivo
Implementar Expo Push Notifications en QoriCashApp para recibir notificaciones incluso cuando la app está cerrada o en segundo plano.

---

## ✅ Backend: COMPLETADO

El backend ya está 100% implementado con:
- ✅ Columna `push_notification_token` en tabla `clients`
- ✅ Servicio `PushNotificationService` en `app/services/push_notification_service.py`
- ✅ Endpoint `/api/client/register-push-token` para registrar tokens
- ✅ Integración automática en `operation_expiry_service.py`

---

## 🔧 Cambios Necesarios en Mobile App

### 1. Instalar Dependencias

```bash
cd QoriCashApp
npx expo install expo-notifications expo-device expo-constants
```

### 2. Configurar `app.json`

Agregar configuración de notificaciones:

```json
{
  "expo": {
    "name": "QoriCash",
    "plugins": [
      [
        "expo-notifications",
        {
          "icon": "./assets/notification-icon.png",
          "color": "#ffffff",
          "sounds": ["./assets/notification-sound.wav"]
        }
      ]
    ],
    "notification": {
      "icon": "./assets/notification-icon.png",
      "color": "#10b981",
      "androidMode": "default",
      "androidCollapsedTitle": "{{unread_count}} nuevas notificaciones"
    }
  }
}
```

### 3. Crear Servicio de Notificaciones

Crear archivo `src/services/notificationService.ts`:

```typescript
import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import Constants from 'expo-constants';
import { Platform } from 'react-native';
import axios from 'axios';

// Configurar comportamiento de notificaciones
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
  }),
});

export const notificationService = {
  /**
   * Registrar token de push notification
   */
  async registerForPushNotifications(dni: string): Promise<string | null> {
    try {
      // Verificar que sea dispositivo físico
      if (!Device.isDevice) {
        console.log('Push notifications solo funcionan en dispositivos físicos');
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
        console.log('Permisos de notificación denegados');
        return null;
      }

      // Obtener token de Expo
      const token = (await Notifications.getExpoPushTokenAsync({
        projectId: Constants.expoConfig?.extra?.eas?.projectId || 'your-project-id',
      })).data;

      console.log('📲 Token de Expo obtenido:', token);

      // Enviar token al backend
      const response = await axios.post(
        'https://qoricash-trading-v2.onrender.com/api/client/register-push-token',
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
    } catch (error) {
      console.error('❌ Error obteniendo token de push:', error);
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
      Notifications.removeNotificationSubscription(receivedListener);
      Notifications.removeNotificationSubscription(responseListener);
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
        lightColor: '#10b981',
        sound: 'default',
      });
    }
  },
};
```

### 4. Modificar `AuthContext.tsx`

Actualizar el contexto de autenticación para registrar el token al iniciar sesión:

```typescript
import { notificationService } from '../services/notificationService';

// En la función signIn, después de un login exitoso:
const signIn = async (dni: string, password: string) => {
  try {
    const response = await axios.post(`${API_URL}/api/client/login`, {
      dni,
      password,
    });

    if (response.data.success) {
      const userData = {
        dni: response.data.client.dni,
        fullName: response.data.client.full_name,
        email: response.data.client.email,
        // ... otros datos
      };

      // Guardar datos de usuario
      await AsyncStorage.setItem('user', JSON.stringify(userData));
      setUser(userData);

      // 🆕 REGISTRAR TOKEN DE PUSH NOTIFICATIONS
      try {
        await notificationService.registerForPushNotifications(dni);
      } catch (error) {
        console.error('Error registrando push token:', error);
        // No bloquear el login si falla el registro de push
      }

      return { success: true };
    } else {
      return { success: false, message: response.data.message };
    }
  } catch (error) {
    console.error('Error en login:', error);
    return { success: false, message: 'Error de conexión' };
  }
};
```

### 5. Modificar `App.tsx` o Componente Principal

Configurar listeners de notificaciones al iniciar la app:

```typescript
import { useEffect } from 'react';
import { notificationService } from './src/services/notificationService';

function App() {
  useEffect(() => {
    // Configurar canal de Android
    notificationService.setupAndroidNotificationChannel();

    // Configurar listeners
    const cleanup = notificationService.setupNotificationListeners(
      // Cuando se recibe notificación (app abierta)
      (notification) => {
        console.log('Notificación recibida:', notification);
        // Aquí puedes mostrar un modal o alerta personalizada
      },
      // Cuando se toca la notificación
      (response) => {
        const data = response.notification.request.content.data;
        console.log('Datos de notificación:', data);

        // Si es notificación de operación expirada, navegar a pantalla correspondiente
        if (data.type === 'operation_expired') {
          // navigation.navigate('OperationsScreen');
        }
      }
    );

    // Limpiar listeners al desmontar
    return cleanup;
  }, []);

  // ... resto del componente
}
```

---

## 🧪 Pruebas

### 1. Prueba en Dispositivo Físico

```bash
npx expo start
# Escanear QR con Expo Go en dispositivo físico
```

### 2. Verificar Registro de Token

1. Iniciar sesión en la app
2. Verificar en logs del backend que el token se registró:
   ```
   📲 Token de Expo registrado para cliente 12345678
   ```

3. Verificar en base de datos:
   ```sql
   SELECT dni, push_notification_token FROM clients WHERE dni = '12345678';
   ```

### 3. Probar Notificación de Operación Expirada

1. Crear operación sin subir comprobante
2. Esperar 1 minuto (tiempo de prueba actual)
3. Verificar que llegue push notification incluso con app cerrada

---

## 📋 Checklist de Implementación

- [ ] Instalar dependencias (`expo-notifications`, `expo-device`, `expo-constants`)
- [ ] Configurar `app.json` con plugins de notificaciones
- [ ] Crear `src/services/notificationService.ts`
- [ ] Modificar `AuthContext.tsx` para registrar token en login
- [ ] Configurar listeners en `App.tsx`
- [ ] Probar en dispositivo físico
- [ ] Verificar que token se guarde en BD
- [ ] Probar operación expirada con app cerrada
- [ ] Configurar ícono y sonido de notificación personalizados (opcional)

---

## 🔍 Troubleshooting

### Token no se registra

- Verificar que sea dispositivo físico (no emulador)
- Revisar permisos de notificación en configuración del dispositivo
- Verificar que el DNI sea correcto al llamar `registerForPushNotifications()`

### Notificaciones no llegan

- Verificar que el token esté en base de datos
- Revisar logs del backend para ver si se envió la notificación
- Verificar respuesta de Expo API en logs del backend
- Asegurarse de que la app esté en segundo plano (no cerrada completamente)

### Error "projectId is required"

- Configurar `projectId` en `app.json` o pasar explícitamente en `getExpoPushTokenAsync()`

---

## 📚 Referencias

- [Expo Notifications Docs](https://docs.expo.dev/versions/latest/sdk/notifications/)
- [Expo Push Notifications Guide](https://docs.expo.dev/push-notifications/overview/)
- [Testing Push Notifications](https://docs.expo.dev/push-notifications/sending-notifications/)

---

## 🎯 Estado Actual

**Backend**: ✅ 100% Completo
**Mobile App**: ⏳ Pendiente de implementación

Una vez implementado, el sistema notificará a los clientes vía:
1. 📧 **Email** - Siempre llega
2. 🔔 **Socket.IO** - Solo cuando app está abierta
3. 📲 **Push Notification** - Incluso con app cerrada
