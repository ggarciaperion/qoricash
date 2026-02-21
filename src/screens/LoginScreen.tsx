import React, { useState } from 'react';
import {
  View,
  StyleSheet,
  Image,
  TouchableOpacity,
  Alert,
} from 'react-native';
import { TextInput, Button, Text, HelperText, IconButton } from 'react-native-paper';
import { LinearGradient } from 'expo-linear-gradient';
import { useNavigation } from '@react-navigation/native';
import { useAuth } from '../contexts/AuthContext';
import { useLoginLoading } from '../contexts/LoginLoadingContext';
import { Colors } from '../constants/colors';
import { API_CONFIG } from '../constants/config';
import { KeyboardAwareScrollView } from '../components/KeyboardAwareScrollView';
import { CustomModal } from '../components/CustomModal';
import { GlobalStyles } from '../styles/globalStyles';

type DocumentType = 'DNI' | 'CE' | 'RUC';

export const LoginScreen = () => {
  const navigation = useNavigation();
  const { login, loading } = useAuth();
  const { setShowLoginLoading } = useLoginLoading();
  const [documentType, setDocumentType] = useState<DocumentType | null>(null);
  const [dni, setDni] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');

  // Forgot Password Modal State
  const [showForgotPasswordModal, setShowForgotPasswordModal] = useState(false);
  const [resetDni, setResetDni] = useState('');
  const [resetEmail, setResetEmail] = useState('');
  const [resetLoading, setResetLoading] = useState(false);
  const [resetError, setResetError] = useState('');

  const getDocumentMaxLength = (): number => {
    switch (documentType) {
      case 'DNI':
        return 8;
      case 'CE':
        return 9;
      case 'RUC':
        return 11;
      default:
        return 8;
    }
  };

  const handleLogin = async () => {
    try {
      setError('');

      if (!documentType) {
        setError('Por favor seleccione un tipo de documento');
        return;
      }

      if (!dni) {
        setError(`Por favor ingrese su ${documentType}`);
        return;
      }

      const maxLength = getDocumentMaxLength();
      if (dni.length !== maxLength) {
        setError(`${documentType} inválido (debe tener ${maxLength} caracteres)`);
        return;
      }

      // Mostrar pantalla de carga ANTES de hacer el login
      setShowLoginLoading(true);

      // Pequeño delay para que la animación inicie suavemente
      await new Promise(resolve => setTimeout(resolve, 200));

      // Enviar DNI y contraseña al backend
      // El backend validará si el cliente tiene contraseña configurada
      await login({ username: dni, password: password }, dni);

      // El login fue exitoso, la pantalla de carga completará su animación
      // y luego onComplete oculta la pantalla, permitiendo que el navigator
      // navegue al Home
    } catch (err: any) {
      // Si hay error, ocultar la pantalla de carga inmediatamente
      setShowLoginLoading(false);
      setError(err.message || 'Error al iniciar sesión');
    }
  };

  const handleForgotPassword = async () => {
    try {
      setResetError('');

      if (!resetDni || !resetEmail) {
        setResetError('Por favor complete todos los campos');
        return;
      }

      if (resetDni.length < 8) {
        setResetError('DNI/RUC inválido (mínimo 8 dígitos)');
        return;
      }

      if (!resetEmail.includes('@')) {
        setResetError('Email inválido');
        return;
      }

      setResetLoading(true);

      const response = await fetch(`${API_CONFIG.BASE_URL}/api/client/forgot-password`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          dni: resetDni,
          email: resetEmail.toLowerCase(),
        }),
      });

      const data = await response.json();

      setResetLoading(false);

      if (data.success) {
        setShowForgotPasswordModal(false);
        setResetDni('');
        setResetEmail('');
        Alert.alert(
          'Contraseña Enviada',
          'Se ha enviado una contraseña temporal a tu correo electrónico. Por favor revisa tu bandeja de entrada.',
          [{ text: 'OK' }]
        );
      } else {
        setResetError(data.message || 'Error al enviar la contraseña');
      }
    } catch (err: any) {
      setResetLoading(false);
      setResetError('Error de conexión. Intenta nuevamente.');
    }
  };

  return (
    <>
      <KeyboardAwareScrollView contentContainerStyle={styles.scrollContent}>
        {/* Logo */}
        <View style={styles.logoContainer}>
          <Image
            source={require('../../assets/logo-principal.png')}
            style={styles.logo}
            resizeMode="contain"
          />
          <Text variant="titleMedium" style={styles.subtitle}>
            Casa de Cambio Digital
          </Text>
        </View>

        {/* Info Banner para clientes registrados por traders */}
        <View style={styles.infoBanner}>
          <View style={styles.infoBannerIcon}>
            <IconButton icon="information" size={20} iconColor={Colors.info} style={{ margin: 0 }} />
          </View>
          <View style={styles.infoBannerContent}>
            <Text style={styles.infoBannerTitle}>¿Te registró un asesor?</Text>
            <Text style={styles.infoBannerText}>
              Usa el botón "¿Olvidaste tu contraseña?" para solicitar tu acceso.
            </Text>
          </View>
        </View>

        {/* Login Form */}
        <View style={styles.formContainer}>
          <Text variant="headlineSmall" style={styles.title}>
            Iniciar Sesión
          </Text>

          {/* Document Type Selector */}
          <Text variant="bodyMedium" style={styles.selectorLabel}>
            Selecciona tu tipo de documento
          </Text>

          <View style={styles.documentTypeContainer}>
            <TouchableOpacity
              style={[
                styles.documentTypeButton,
                documentType === 'DNI' && styles.documentTypeButtonActive,
              ]}
              onPress={() => {
                setDocumentType('DNI');
                setDni('');
                setError('');
              }}
            >
              <Text
                style={[
                  styles.documentTypeButtonText,
                  documentType === 'DNI' && styles.documentTypeButtonTextActive,
                ]}
              >
                DNI
              </Text>
              <Text
                style={[
                  styles.documentTypeButtonSubtext,
                  documentType === 'DNI' && styles.documentTypeButtonSubtextActive,
                ]}
              >
                8 dígitos
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[
                styles.documentTypeButton,
                documentType === 'CE' && styles.documentTypeButtonActive,
              ]}
              onPress={() => {
                setDocumentType('CE');
                setDni('');
                setError('');
              }}
            >
              <Text
                style={[
                  styles.documentTypeButtonText,
                  documentType === 'CE' && styles.documentTypeButtonTextActive,
                ]}
              >
                CE
              </Text>
              <Text
                style={[
                  styles.documentTypeButtonSubtext,
                  documentType === 'CE' && styles.documentTypeButtonSubtextActive,
                ]}
              >
                9 dígitos
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[
                styles.documentTypeButton,
                documentType === 'RUC' && styles.documentTypeButtonActive,
              ]}
              onPress={() => {
                setDocumentType('RUC');
                setDni('');
                setError('');
              }}
            >
              <Text
                style={[
                  styles.documentTypeButtonText,
                  documentType === 'RUC' && styles.documentTypeButtonTextActive,
                ]}
              >
                RUC
              </Text>
              <Text
                style={[
                  styles.documentTypeButtonSubtext,
                  documentType === 'RUC' && styles.documentTypeButtonSubtextActive,
                ]}
              >
                11 dígitos
              </Text>
            </TouchableOpacity>
          </View>

          <TextInput
            label={documentType ? `Número de ${documentType}` : 'Número de documento'}
            value={dni}
            onChangeText={(text) => {
              // Only allow numeric input and respect max length
              const numericText = text.replace(/[^0-9]/g, '');
              const maxLength = getDocumentMaxLength();
              if (numericText.length <= maxLength) {
                setDni(numericText);
              }
              setError('');
            }}
            mode="outlined"
            keyboardType="numeric"
            autoCapitalize="none"
            maxLength={getDocumentMaxLength()}
            style={GlobalStyles.input}
            left={<TextInput.Icon icon="card-account-details" />}
            placeholder={documentType ? `Ingrese ${getDocumentMaxLength()} dígitos` : 'Seleccione tipo de documento primero'}
            disabled={!documentType}
          />

          <TextInput
            label="Contraseña"
            value={password}
            onChangeText={(text) => {
              setPassword(text);
              setError('');
            }}
            mode="outlined"
            secureTextEntry={!showPassword}
            autoCapitalize="none"
            style={GlobalStyles.input}
            left={<TextInput.Icon icon="lock" />}
            right={
              <TextInput.Icon
                icon={showPassword ? 'eye-off' : 'eye'}
                onPress={() => setShowPassword(!showPassword)}
              />
            }
          />

          {error ? (
            <HelperText type="error" visible={!!error} style={styles.error}>
              {error}
            </HelperText>
          ) : null}

          <TouchableOpacity
            onPress={handleLogin}
            disabled={loading}
            activeOpacity={0.8}
            style={styles.loginButtonContainer}
          >
            <LinearGradient
              colors={[Colors.primary, Colors.primaryDark]}
              start={{ x: 0, y: 0 }}
              end={{ x: 1, y: 0 }}
              style={styles.loginButton}
            >
              <Text variant="titleMedium" style={styles.loginButtonText}>
                {loading ? 'Ingresando...' : 'Ingresar'}
              </Text>
            </LinearGradient>
          </TouchableOpacity>

          <Button
            mode="text"
            onPress={() => setShowForgotPasswordModal(true)}
            style={styles.forgotButton}
            disabled={loading}
            textColor={Colors.primary}
          >
            ¿Olvidaste tu contraseña?
          </Button>
        </View>

        {/* Footer */}
        <View style={styles.footer}>
          <Text variant="bodySmall" style={styles.footerText}>
            ¿No tienes cuenta?
          </Text>
          <Button
            mode="text"
            onPress={() => navigation.navigate('ClientTypeSelection' as never)}
            disabled={loading}
            textColor={Colors.primary}
          >
            Regístrate aquí
          </Button>
        </View>
      </KeyboardAwareScrollView>

      {/* Forgot Password Modal */}
      <CustomModal
        visible={showForgotPasswordModal}
        onDismiss={() => {
          setShowForgotPasswordModal(false);
          setResetDni('');
          setResetEmail('');
          setResetError('');
        }}
        title="Recuperar Contraseña"
        actions={[
          {
            label: 'Cancelar',
            onPress: () => {
              setShowForgotPasswordModal(false);
              setResetDni('');
              setResetEmail('');
              setResetError('');
            },
            disabled: resetLoading,
          },
          {
            label: 'Enviar Instrucciones',
            onPress: handleForgotPassword,
            primary: true,
            disabled: resetLoading,
            loading: resetLoading,
          },
        ]}
      >
        {/* Header Icon */}
        <View style={{ alignItems: 'center', marginBottom: 20 }}>
          <View
            style={{
              width: 80,
              height: 80,
              borderRadius: 40,
              backgroundColor: Colors.primaryLight,
              justifyContent: 'center',
              alignItems: 'center',
              marginBottom: 16,
            }}
          >
            <IconButton
              icon="lock-reset"
              size={40}
              iconColor={Colors.primary}
              style={{ margin: 0 }}
            />
          </View>
          <Text
            variant="bodyLarge"
            style={{
              textAlign: 'center',
              color: Colors.textDark,
              marginBottom: 8,
              fontWeight: '600',
            }}
          >
            ¿Olvidaste tu contraseña?
          </Text>
          <Text
            variant="bodyMedium"
            style={{
              textAlign: 'center',
              color: Colors.textLight,
              lineHeight: 22,
            }}
          >
            No te preocupes. Ingresa tus datos y te enviaremos las instrucciones para recuperar tu
            cuenta.
          </Text>
        </View>

        {/* Form Fields */}
        <View style={{ marginBottom: 8 }}>
          <TextInput
            label="DNI / CE / RUC"
            value={resetDni}
            onChangeText={(text) => {
              setResetDni(text);
              setResetError('');
            }}
            mode="outlined"
            keyboardType="numeric"
            autoCapitalize="none"
            style={GlobalStyles.input}
            left={<TextInput.Icon icon="card-account-details" />}
            disabled={resetLoading}
          />

          <TextInput
            label="Correo Electrónico"
            value={resetEmail}
            onChangeText={(text) => {
              setResetEmail(text);
              setResetError('');
            }}
            mode="outlined"
            keyboardType="email-address"
            autoCapitalize="none"
            style={GlobalStyles.input}
            left={<TextInput.Icon icon="email" />}
            disabled={resetLoading}
          />
        </View>

        {resetError ? (
          <HelperText type="error" visible={!!resetError} style={{ marginTop: 8 }}>
            {resetError}
          </HelperText>
        ) : null}

        {/* Info Box */}
        <View
          style={{
            backgroundColor: '#E7F3FF',
            padding: 12,
            borderRadius: 8,
            marginTop: 16,
            flexDirection: 'row',
            alignItems: 'flex-start',
          }}
        >
          <IconButton
            icon="information"
            size={20}
            iconColor="#2196F3"
            style={{ margin: 0, marginRight: 8 }}
          />
          <Text variant="bodySmall" style={{ flex: 1, color: '#1976D2', lineHeight: 18 }}>
            Recibirás un correo con una contraseña temporal. Podrás cambiarla después de iniciar
            sesión.
          </Text>
        </View>
      </CustomModal>
    </>
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
    paddingTop: 60, // Add top padding to prevent logo from being cut off
    paddingBottom: 40,
  },
  logoContainer: {
    alignItems: 'center',
    marginBottom: 40,
  },
  logo: {
    width: 180,
    height: 120,
    marginBottom: 12,
  },
  subtitle: {
    color: Colors.textLight,
    fontWeight: '500',
  },
  formContainer: {
    width: '100%',
  },
  title: {
    marginBottom: 20,
    fontWeight: '600',
    textAlign: 'center',
    color: Colors.textDark,
  },
  selectorLabel: {
    marginBottom: 12,
    color: Colors.textDark,
    fontWeight: '500',
  },
  documentTypeContainer: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 16,
  },
  documentTypeButton: {
    flex: 1,
    paddingVertical: 14,
    paddingHorizontal: 12,
    borderRadius: 12,
    borderWidth: 2,
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  documentTypeButtonActive: {
    borderColor: Colors.primary,
    backgroundColor: Colors.primary,
  },
  documentTypeButtonText: {
    fontSize: 16,
    fontWeight: '700',
    color: Colors.textDark,
    marginBottom: 2,
  },
  documentTypeButtonTextActive: {
    color: Colors.textOnPrimary,
  },
  documentTypeButtonSubtext: {
    fontSize: 11,
    color: Colors.textLight,
  },
  documentTypeButtonSubtextActive: {
    color: Colors.textOnPrimary,
    opacity: 0.9,
  },
  tempNotice: {
    backgroundColor: '#FFF3E0',
    padding: 12,
    borderRadius: 12,
    marginBottom: 24,
    borderLeftWidth: 4,
    borderLeftColor: Colors.warning,
  },
  tempNoticeText: {
    color: Colors.warningDark,
    textAlign: 'center',
  },
  input: {
    marginBottom: 16,
    backgroundColor: Colors.surface,
  },
  error: {
    marginBottom: 8,
  },
  loginButtonContainer: {
    marginTop: 8,
    marginBottom: 16,
    borderRadius: 12,
    overflow: 'hidden',
    shadowColor: Colors.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 8,
  },
  loginButton: {
    paddingVertical: 14,
    paddingHorizontal: 24,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 12,
  },
  loginButtonText: {
    color: Colors.textOnPrimary,
    fontWeight: '700',
    fontSize: 16,
  },
  forgotButton: {
    marginBottom: 24,
  },
  footer: {
    alignItems: 'center',
    marginTop: 32,
  },
  footerText: {
    color: Colors.textLight,
  },
  infoBanner: {
    backgroundColor: '#E7F3FF',
    borderLeftWidth: 4,
    borderLeftColor: Colors.info,
    borderRadius: 12,
    padding: 16,
    marginBottom: 24,
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  infoBannerIcon: {
    marginRight: 12,
    marginTop: 2,
  },
  infoBannerContent: {
    flex: 1,
  },
  infoBannerTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: Colors.textDark,
    marginBottom: 6,
  },
  infoBannerText: {
    fontSize: 13,
    color: '#1976D2',
    lineHeight: 20,
  },
});
