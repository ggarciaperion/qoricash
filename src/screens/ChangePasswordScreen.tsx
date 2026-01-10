import React, { useState } from 'react';
import {
  View,
  StyleSheet,
  Alert,
} from 'react-native';
import { TextInput, Button, Text, HelperText } from 'react-native-paper';
import { useNavigation } from '@react-navigation/native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import axios from 'axios';
import { Colors } from '../constants/colors';
import { API_CONFIG, STORAGE_KEYS } from '../constants/config';
import { useAuth } from '../contexts/AuthContext';
import { KeyboardAwareScrollView } from '../components/KeyboardAwareScrollView';
import { GlobalStyles } from '../styles/globalStyles';

interface ChangePasswordScreenProps {
  route?: {
    params?: {
      isFirstLogin?: boolean;
      dni?: string;
    };
  };
}

export const ChangePasswordScreen: React.FC<ChangePasswordScreenProps> = ({ route }) => {
  const navigation = useNavigation();
  const { client, refreshClient, logout } = useAuth();
  const isFirstLogin = route?.params?.isFirstLogin || false;
  const clientDni = route?.params?.dni || client?.dni || '';

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const validatePassword = () => {
    if (!newPassword) {
      setError('Por favor ingrese una nueva contraseña');
      return false;
    }

    if (newPassword.length < 8) {
      setError('La contraseña debe tener al menos 8 caracteres');
      return false;
    }

    if (newPassword !== confirmPassword) {
      setError('Las contraseñas no coinciden');
      return false;
    }

    if (!isFirstLogin && !currentPassword) {
      setError('Por favor ingrese su contraseña actual');
      return false;
    }

    return true;
  };

  const handleChangePassword = async () => {
    try {
      setError('');

      if (!validatePassword()) {
        return;
      }

      setLoading(true);

      const response = await axios.post(
        `${API_CONFIG.BASE_URL}/api/client/change-password`,
        {
          dni: clientDni,
          current_password: currentPassword,
          new_password: newPassword,
        }
      );

      if (response.data.success) {
        // Remover flag de cambio requerido
        await AsyncStorage.removeItem(STORAGE_KEYS.REQUIRES_PASSWORD_CHANGE);

        Alert.alert(
          '✅ Contraseña Actualizada',
          isFirstLogin
            ? 'Tu contraseña ha sido creada exitosamente.\n\nAhora debes iniciar sesión con tu nueva contraseña.'
            : 'Contraseña actualizada exitosamente.\n\nPor seguridad, debes iniciar sesión nuevamente.',
          [
            {
              text: 'Iniciar Sesión',
              onPress: async () => {
                // Hacer logout completo para volver a la pantalla de login
                try {
                  await logout();
                } catch (error) {
                  console.error('Error en logout:', error);
                  // Forzar limpieza manual si el logout falla
                  await AsyncStorage.multiRemove([
                    STORAGE_KEYS.USER_DATA,
                    STORAGE_KEYS.CLIENT_DATA,
                    STORAGE_KEYS.AUTH_TOKEN,
                    STORAGE_KEYS.REQUIRES_PASSWORD_CHANGE,
                  ]);
                }
                // El AuthContext detectará que no hay sesión y mostrará LoginScreen automáticamente
              },
            },
          ]
        );
      } else {
        setError(response.data.message || 'Error al cambiar contraseña');
      }
    } catch (err: any) {
      console.error('Error changing password:', err);
      setError(
        err.response?.data?.message ||
          err.message ||
          'Error al cambiar contraseña'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAwareScrollView contentContainerStyle={styles.scrollContent}>
        <View style={styles.formContainer}>
          {isFirstLogin ? (
            <>
              <Text variant="headlineMedium" style={styles.title}>
                Crear Nueva Contraseña
              </Text>
              <Text variant="bodyMedium" style={styles.subtitle}>
                Por seguridad, debes crear una nueva contraseña personal para tu cuenta.
              </Text>
              <View style={styles.infoBox}>
                <Text variant="bodySmall" style={styles.infoText}>
                  🔐 Tu contraseña debe tener al menos 8 caracteres
                </Text>
              </View>
            </>
          ) : (
            <>
              <Text variant="headlineMedium" style={styles.title}>
                Cambiar Contraseña
              </Text>
              <Text variant="bodyMedium" style={styles.subtitle}>
                Ingresa tu contraseña actual y la nueva contraseña que deseas usar.
              </Text>
            </>
          )}

          {!isFirstLogin && (
            <TextInput
              label="Contraseña Actual"
              value={currentPassword}
              onChangeText={(text) => {
                setCurrentPassword(text);
                setError('');
              }}
              mode="outlined"
              secureTextEntry={!showCurrentPassword}
              autoCapitalize="none"
              style={GlobalStyles.input}
              left={<TextInput.Icon icon="lock" />}
              right={
                <TextInput.Icon
                  icon={showCurrentPassword ? 'eye-off' : 'eye'}
                  onPress={() => setShowCurrentPassword(!showCurrentPassword)}
                />
              }
            />
          )}

          <TextInput
            label="Nueva Contraseña"
            value={newPassword}
            onChangeText={(text) => {
              setNewPassword(text);
              setError('');
            }}
            mode="outlined"
            secureTextEntry={!showNewPassword}
            autoCapitalize="none"
            style={GlobalStyles.input}
            left={<TextInput.Icon icon="lock-plus" />}
            right={
              <TextInput.Icon
                icon={showNewPassword ? 'eye-off' : 'eye'}
                onPress={() => setShowNewPassword(!showNewPassword)}
              />
            }
          />

          <TextInput
            label="Confirmar Nueva Contraseña"
            value={confirmPassword}
            onChangeText={(text) => {
              setConfirmPassword(text);
              setError('');
            }}
            mode="outlined"
            secureTextEntry={!showConfirmPassword}
            autoCapitalize="none"
            style={GlobalStyles.input}
            left={<TextInput.Icon icon="lock-check" />}
            right={
              <TextInput.Icon
                icon={showConfirmPassword ? 'eye-off' : 'eye'}
                onPress={() => setShowConfirmPassword(!showConfirmPassword)}
              />
            }
          />

          {error ? (
            <HelperText type="error" visible={!!error} style={styles.error}>
              {error}
            </HelperText>
          ) : null}

          <Button
            mode="contained"
            onPress={handleChangePassword}
            loading={loading}
            disabled={loading}
            style={styles.button}
            buttonColor={Colors.primary}
          >
            {isFirstLogin ? 'Crear Contraseña' : 'Cambiar Contraseña'}
          </Button>

          {!isFirstLogin && (
            <Button
              mode="text"
              onPress={() => navigation.goBack()}
              disabled={loading}
              style={styles.cancelButton}
            >
              Cancelar
            </Button>
          )}
        </View>
    </KeyboardAwareScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  scrollContent: {
    flexGrow: 1,
    justifyContent: 'center',
    padding: 24,
  },
  formContainer: {
    width: '100%',
  },
  title: {
    marginBottom: 12,
    fontWeight: '600',
    textAlign: 'center',
    color: Colors.textDark,
  },
  subtitle: {
    marginBottom: 24,
    textAlign: 'center',
    color: Colors.textLight,
  },
  infoBox: {
    backgroundColor: Colors.primaryLight,
    padding: 16,
    borderRadius: 12,
    marginBottom: 24,
    borderLeftWidth: 4,
    borderLeftColor: Colors.primary,
  },
  infoText: {
    color: Colors.primaryDark,
    textAlign: 'center',
  },
  input: {
    marginBottom: 16,
    backgroundColor: Colors.surface,
  },
  error: {
    marginBottom: 8,
  },
  button: {
    marginTop: 8,
    paddingVertical: 8,
  },
  cancelButton: {
    marginTop: 12,
  },
});
