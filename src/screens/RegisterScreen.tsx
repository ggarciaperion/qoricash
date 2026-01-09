import React, { useState, useEffect } from 'react';
import {
  View,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  Alert,
  TouchableOpacity,
  FlatList,
  TextInput as RNTextInput,
  Linking,
} from 'react-native';
import { TextInput, Button, Text, HelperText, SegmentedButtons, IconButton, Checkbox } from 'react-native-paper';
import { useNavigation, useRoute, RouteProp } from '@react-navigation/native';
import axios from 'axios';
import { Colors } from '../constants/colors';
import { API_CONFIG } from '../constants/config';
import { getDepartamentos, getProvincias, getDistritos } from '../data/ubigeo';
import { CustomModal } from '../components/CustomModal';
import { KeyboardAwareScrollView } from '../components/KeyboardAwareScrollView';
import { GlobalStyles } from '../styles/globalStyles';

type RegisterRouteParams = {
  Register: {
    tipoPersona?: 'Natural' | 'Jurídica';
  };
};

type RegisterScreenRouteProp = RouteProp<RegisterRouteParams, 'Register'>;

export const RegisterScreen = () => {
  const navigation = useNavigation();
  const route = useRoute<RegisterScreenRouteProp>();

  // Personal data
  const [tipoPersona, setTipoPersona] = useState<'Natural' | 'Jurídica'>('Natural');
  const [tipoDocumento, setTipoDocumento] = useState<'DNI' | 'CE'>('DNI');
  const [dni, setDni] = useState('');
  const [ruc, setRuc] = useState('');
  const [email, setEmail] = useState('');
  const [nombres, setNombres] = useState('');
  const [apellidoPaterno, setApellidoPaterno] = useState('');
  const [apellidoMaterno, setApellidoMaterno] = useState('');
  const [razonSocial, setRazonSocial] = useState('');
  const [personaContacto, setPersonaContacto] = useState('');
  const [telefono, setTelefono] = useState('');
  const [direccion, setDireccion] = useState('');
  const [departamento, setDepartamento] = useState('');
  const [provincia, setProvincia] = useState('');
  const [distrito, setDistrito] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  // Ubigeo state
  const [departamentos, setDepartamentos] = useState<string[]>([]);
  const [provincias, setProvincias] = useState<string[]>([]);
  const [distritos, setDistritos] = useState<string[]>([]);
  const [departamentoMenuVisible, setDepartamentoMenuVisible] = useState(false);
  const [provinciaMenuVisible, setProvinciaMenuVisible] = useState(false);
  const [distritoMenuVisible, setDistritoMenuVisible] = useState(false);

  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // Checkboxes de aceptación
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [acceptPrivacy, setAcceptPrivacy] = useState(false);
  const [acceptPromotions, setAcceptPromotions] = useState(false);

  // Initialize tipoPersona from route params if provided
  useEffect(() => {
    if (route.params?.tipoPersona) {
      setTipoPersona(route.params.tipoPersona);
    }
  }, [route.params?.tipoPersona]);

  // Load departamentos on mount
  useEffect(() => {
    const deps = getDepartamentos();
    setDepartamentos(deps);
  }, []);

  // Update provincias when departamento changes
  useEffect(() => {
    if (departamento) {
      const provs = getProvincias(departamento);
      setProvincias(provs);
      setProvincia('');
      setDistrito('');
      setDistritos([]);
    } else {
      setProvincias([]);
      setProvincia('');
      setDistrito('');
      setDistritos([]);
    }
  }, [departamento]);

  // Update distritos when provincia changes
  useEffect(() => {
    if (departamento && provincia) {
      const dists = getDistritos(departamento, provincia);
      setDistritos(dists);
      setDistrito('');
    } else {
      setDistritos([]);
      setDistrito('');
    }
  }, [provincia, departamento]);

  const validateForm = () => {
    if (tipoPersona === 'Natural') {
      const longitudEsperada = tipoDocumento === 'DNI' ? 8 : 9;
      if (!dni || dni.length !== longitudEsperada) {
        setError(`${tipoDocumento} debe tener ${longitudEsperada} dígitos`);
        return false;
      }

      if (!nombres || !apellidoPaterno) {
        setError('Nombres y apellido paterno son obligatorios');
        return false;
      }
    } else {
      if (!ruc || ruc.length !== 11) {
        setError('RUC debe tener 11 dígitos');
        return false;
      }

      if (!razonSocial) {
        setError('Razón social es obligatoria');
        return false;
      }

      if (!personaContacto) {
        setError('Persona de contacto es obligatoria');
        return false;
      }
    }

    if (!email || !email.includes('@')) {
      setError('Email inválido');
      return false;
    }

    if (!telefono) {
      setError('Teléfono es obligatorio');
      return false;
    }

    if (!direccion) {
      setError('Dirección es obligatoria');
      return false;
    }

    if (!departamento) {
      setError('Departamento es obligatorio');
      return false;
    }

    if (!provincia) {
      setError('Provincia es obligatoria');
      return false;
    }

    if (!distrito) {
      setError('Distrito es obligatorio');
      return false;
    }

    if (!password || password.length < 8) {
      setError('La contraseña debe tener al menos 8 caracteres');
      return false;
    }

    if (password !== confirmPassword) {
      setError('Las contraseñas no coinciden');
      return false;
    }

    if (!acceptTerms) {
      setError('Debes aceptar los Términos y Condiciones');
      return false;
    }

    if (!acceptPrivacy) {
      setError('Debes aceptar la Política de Privacidad');
      return false;
    }

    return true;
  };

  const handleRegister = async () => {
    try {
      setError('');

      if (!validateForm()) {
        return;
      }

      setLoading(true);

      const payload: any = {
        tipo_persona: tipoPersona,
        email,
        telefono,
        direccion: direccion,
        departamento: departamento,
        provincia: provincia,
        distrito: distrito,
        password,
        accept_promotions: acceptPromotions,
      };

      if (tipoPersona === 'Natural') {
        payload.dni = dni;
        payload.tipo_documento = tipoDocumento;
        payload.nombres = nombres;
        payload.apellido_paterno = apellidoPaterno;
        payload.apellido_materno = apellidoMaterno;
      } else {
        payload.dni = ruc;
        payload.ruc = ruc;
        payload.razon_social = razonSocial;
        payload.persona_contacto = personaContacto;
      }

      console.log('========== PAYLOAD COMPLETO ==========');
      console.log(JSON.stringify(payload, null, 2));
      console.log('======================================');

      const response = await axios.post(
        `${API_CONFIG.BASE_URL}/api/client/register`,
        payload
      );

      if (response.data.success) {
        Alert.alert(
          '✅ Registro Exitoso',
          `Tu cuenta ha sido creada exitosamente.\n\n📧 Recibirás un email de confirmación.\n\nAhora puedes iniciar sesión con tu DNI${tipoPersona === 'Jurídica' ? '/RUC' : ''} y la contraseña que creaste.`,
          [
            {
              text: 'Iniciar Sesión',
              onPress: () => {
                // Navegar a Login y limpiar toda la pila de navegación
                navigation.reset({
                  index: 0,
                  routes: [{ name: 'Login' }],
                });
              },
            },
          ]
        );
      } else {
        setError(response.data.message || 'Error al registrarse');
      }
    } catch (err: any) {
      console.error('Error registering:', err);
      console.error('Response data:', err.response?.data);
      console.error('Response status:', err.response?.status);

      const errorMessage = err.response?.data?.message || err.message || 'Error al registrarse';

      setError(errorMessage);

      Alert.alert(
        '❌ Error en el Registro',
        errorMessage,
        [{ text: 'OK' }]
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      style={styles.container}
    >
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <View style={styles.formContainer}>
          <Text variant="headlineMedium" style={styles.title}>
            Crear Cuenta
          </Text>
          <Text variant="bodyMedium" style={styles.subtitle}>
            Completa tu información personal
          </Text>

          {/* Tipo de Persona - Hidden if selected from previous screen */}
          {!route.params?.tipoPersona && (
            <>
              <Text variant="labelLarge" style={styles.label}>
                Tipo de Persona
              </Text>
              <SegmentedButtons
                value={tipoPersona}
                onValueChange={(value) => setTipoPersona(value as 'Natural' | 'Jurídica')}
                buttons={[
                  {
                    value: 'Natural',
                    label: 'Natural',
                    icon: 'account',
                  },
                  {
                    value: 'Jurídica',
                    label: 'Jurídica',
                    icon: 'domain',
                  },
                ]}
                style={styles.segmentedButtons}
              />
            </>
          )}

          {/* Campos para Persona Natural */}
          {tipoPersona === 'Natural' ? (
            <>
              <Text style={styles.sectionLabel}>Tipo de Documento</Text>
              <SegmentedButtons
                value={tipoDocumento}
                onValueChange={(value) => {
                  setTipoDocumento(value as 'DNI' | 'CE');
                  setDni('');
                  setError('');
                }}
                buttons={[
                  {
                    value: 'DNI',
                    label: 'DNI (8 dígitos)',
                    icon: 'card-account-details',
                  },
                  {
                    value: 'CE',
                    label: 'CE (9 dígitos)',
                    icon: 'passport',
                  },
                ]}
                style={styles.segmentedButtons}
              />

              <TextInput
                label={`${tipoDocumento} *`}
                value={dni}
                onChangeText={(text) => {
                  setDni(text);
                  setError('');
                }}
                mode="outlined"
                keyboardType="numeric"
                maxLength={tipoDocumento === 'DNI' ? 8 : 9}
                placeholder={`Ingrese ${tipoDocumento === 'DNI' ? '8' : '9'} dígitos`}
                style={styles.input}
                left={<TextInput.Icon icon="card-account-details" />}
              />

              <TextInput
                label="Nombres *"
                value={nombres}
                onChangeText={(text) => {
                  setNombres(text);
                  setError('');
                }}
                mode="outlined"
                autoCapitalize="words"
                style={styles.input}
                left={<TextInput.Icon icon="account" />}
              />

              <TextInput
                label="Apellido Paterno *"
                value={apellidoPaterno}
                onChangeText={(text) => {
                  setApellidoPaterno(text);
                  setError('');
                }}
                mode="outlined"
                autoCapitalize="words"
                style={styles.input}
                left={<TextInput.Icon icon="account" />}
              />

              <TextInput
                label="Apellido Materno"
                value={apellidoMaterno}
                onChangeText={(text) => {
                  setApellidoMaterno(text);
                  setError('');
                }}
                mode="outlined"
                autoCapitalize="words"
                style={styles.input}
                left={<TextInput.Icon icon="account" />}
              />
            </>
          ) : (
            <>
              <TextInput
                label="RUC *"
                value={ruc}
                onChangeText={(text) => {
                  setRuc(text);
                  setError('');
                }}
                mode="outlined"
                keyboardType="numeric"
                maxLength={11}
                style={styles.input}
                left={<TextInput.Icon icon="card-account-details" />}
              />

              <TextInput
                label="Razón Social *"
                value={razonSocial}
                onChangeText={(text) => {
                  setRazonSocial(text);
                  setError('');
                }}
                mode="outlined"
                autoCapitalize="words"
                style={styles.input}
                left={<TextInput.Icon icon="domain" />}
              />

              <View style={styles.nativeInputContainer}>
                <Text variant="labelMedium" style={styles.nativeInputLabel}>
                  Persona de Contacto *
                </Text>
                <RNTextInput
                  value={personaContacto}
                  onChangeText={setPersonaContacto}
                  placeholder="Nombre completo de la persona de contacto"
                  autoCapitalize="words"
                  style={styles.nativeInput}
                />
              </View>
            </>
          )}

          {/* Campos comunes */}
          <TextInput
            label="Email *"
            value={email}
            onChangeText={(text) => {
              setEmail(text);
              setError('');
            }}
            mode="outlined"
            keyboardType="email-address"
            autoCapitalize="none"
            style={styles.input}
            left={<TextInput.Icon icon="email" />}
          />

          <TextInput
            label="Teléfono *"
            value={telefono}
            onChangeText={(text) => {
              setTelefono(text);
              setError('');
            }}
            mode="outlined"
            keyboardType="phone-pad"
            placeholder="+51987654321"
            style={styles.input}
            left={<TextInput.Icon icon="phone" />}
          />

          <TextInput
            label="Dirección *"
            value={direccion}
            onChangeText={(text) => {
              setDireccion(text);
              setError('');
            }}
            mode="outlined"
            multiline
            numberOfLines={3}
            placeholder="Ingrese su dirección completa"
            style={styles.input}
            left={<TextInput.Icon icon="map-marker" />}
          />

          {/* Departamento */}
          <Text variant="labelMedium" style={styles.fieldLabel}>
            Departamento *
          </Text>
          <TouchableOpacity onPress={() => setDepartamentoMenuVisible(true)}>
            <View style={styles.selector}>
              <Text style={styles.selectorText}>
                {departamento || 'Seleccionar departamento'}
              </Text>
              <IconButton icon="chevron-down" size={20} />
            </View>
          </TouchableOpacity>

          {/* Provincia */}
          <Text variant="labelMedium" style={styles.fieldLabel}>
            Provincia *
          </Text>
          <TouchableOpacity
            onPress={() => departamento ? setProvinciaMenuVisible(true) : null}
            disabled={!departamento}
          >
            <View style={[styles.selector, !departamento && styles.disabledSelector]}>
              <Text style={[styles.selectorText, !departamento && styles.disabledText]}>
                {provincia || (departamento ? 'Seleccionar provincia' : 'Seleccione departamento primero')}
              </Text>
              <IconButton icon="chevron-down" size={20} iconColor={!departamento ? '#ccc' : undefined} />
            </View>
          </TouchableOpacity>

          {/* Distrito */}
          <Text variant="labelMedium" style={styles.fieldLabel}>
            Distrito *
          </Text>
          <TouchableOpacity
            onPress={() => provincia ? setDistritoMenuVisible(true) : null}
            disabled={!provincia}
          >
            <View style={[styles.selector, !provincia && styles.disabledSelector]}>
              <Text style={[styles.selectorText, !provincia && styles.disabledText]}>
                {distrito || (provincia ? 'Seleccionar distrito' : 'Seleccione provincia primero')}
              </Text>
              <IconButton icon="chevron-down" size={20} iconColor={!provincia ? '#ccc' : undefined} />
            </View>
          </TouchableOpacity>

          <TextInput
            label="Contraseña *"
            value={password}
            onChangeText={(text) => {
              setPassword(text);
              setError('');
            }}
            mode="outlined"
            secureTextEntry={!showPassword}
            style={styles.input}
            left={<TextInput.Icon icon="lock" />}
            right={
              <TextInput.Icon
                icon={showPassword ? 'eye-off' : 'eye'}
                onPress={() => setShowPassword(!showPassword)}
              />
            }
          />

          <TextInput
            label="Confirmar Contraseña *"
            value={confirmPassword}
            onChangeText={(text) => {
              setConfirmPassword(text);
              setError('');
            }}
            mode="outlined"
            secureTextEntry={!showConfirmPassword}
            style={styles.input}
            left={<TextInput.Icon icon="lock-check" />}
            right={
              <TextInput.Icon
                icon={showConfirmPassword ? 'eye-off' : 'eye'}
                onPress={() => setShowConfirmPassword(!showConfirmPassword)}
              />
            }
          />

          {/* Checkboxes de aceptación */}
          <View style={styles.checkboxContainer}>
            <TouchableOpacity
              style={styles.checkboxRow}
              onPress={() => setAcceptTerms(!acceptTerms)}
              activeOpacity={0.7}
            >
              <Checkbox.Android
                status={acceptTerms ? 'checked' : 'unchecked'}
                color={Colors.primary}
              />
              <View style={styles.checkboxTextContainer}>
                <Text style={styles.checkboxText}>
                  Acepto los{' '}
                  <Text
                    style={styles.checkboxLink}
                    onPress={(e) => {
                      e.stopPropagation();
                      Linking.openURL(`${API_CONFIG.BASE_URL}/legal/terms`);
                    }}
                  >
                    Términos y Condiciones
                  </Text>
                  {' '}*
                </Text>
              </View>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.checkboxRow}
              onPress={() => setAcceptPrivacy(!acceptPrivacy)}
              activeOpacity={0.7}
            >
              <Checkbox.Android
                status={acceptPrivacy ? 'checked' : 'unchecked'}
                color={Colors.primary}
              />
              <View style={styles.checkboxTextContainer}>
                <Text style={styles.checkboxText}>
                  Acepto la{' '}
                  <Text
                    style={styles.checkboxLink}
                    onPress={(e) => {
                      e.stopPropagation();
                      Linking.openURL(`${API_CONFIG.BASE_URL}/legal/privacy`);
                    }}
                  >
                    Política de Privacidad
                  </Text>
                  {' '}y el tratamiento de mis datos personales *
                </Text>
              </View>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.checkboxRow}
              onPress={() => setAcceptPromotions(!acceptPromotions)}
              activeOpacity={0.7}
            >
              <Checkbox.Android
                status={acceptPromotions ? 'checked' : 'unchecked'}
                color={Colors.primary}
              />
              <View style={styles.checkboxTextContainer}>
                <Text style={styles.checkboxText}>
                  Deseo recibir promociones y ofertas por correo electrónico
                </Text>
              </View>
            </TouchableOpacity>
          </View>

          {error ? (
            <HelperText type="error" visible={!!error} style={styles.error}>
              {error}
            </HelperText>
          ) : null}

          <Button
            mode="contained"
            onPress={handleRegister}
            loading={loading}
            disabled={loading}
            style={styles.button}
            buttonColor={Colors.primary}
          >
            Crear Cuenta
          </Button>

          <Button
            mode="text"
            onPress={() => navigation.goBack()}
            style={styles.cancelButton}
          >
            Cancelar
          </Button>

          {/* Modal de selección de Departamento */}
          <CustomModal
            visible={departamentoMenuVisible}
            onDismiss={() => setDepartamentoMenuVisible(false)}
            title="Seleccionar Departamento"
          >
            <FlatList
              data={departamentos}
              keyExtractor={(item) => item}
              contentContainerStyle={styles.list}
              style={styles.listContainer}
              renderItem={({ item }) => (
                <TouchableOpacity
                  style={[
                    styles.option,
                    departamento === item && styles.optionSelected
                  ]}
                  onPress={() => {
                    setDepartamento(item);
                    setDepartamentoMenuVisible(false);
                  }}
                  activeOpacity={0.7}
                >
                  <View style={styles.optionContent}>
                    <View style={styles.iconContainer}>
                      <IconButton
                        icon="map-marker"
                        size={24}
                        iconColor={departamento === item ? Colors.primary : Colors.textLight}
                        style={styles.icon}
                      />
                    </View>
                    <Text style={[
                      styles.optionText,
                      departamento === item && styles.optionTextSelected
                    ]}>
                      {item}
                    </Text>
                  </View>
                  {departamento === item && (
                    <View style={styles.checkIconContainer}>
                      <IconButton
                        icon="check-circle"
                        size={24}
                        iconColor={Colors.primary}
                        style={{ margin: 0 }}
                      />
                    </View>
                  )}
                </TouchableOpacity>
              )}
            />
          </CustomModal>

          {/* Modal de selección de Provincia */}
          <CustomModal
            visible={provinciaMenuVisible}
            onDismiss={() => setProvinciaMenuVisible(false)}
            title="Seleccionar Provincia"
          >
            <FlatList
              data={provincias}
              keyExtractor={(item) => item}
              contentContainerStyle={styles.list}
              style={styles.listContainer}
              renderItem={({ item }) => (
                <TouchableOpacity
                  style={[
                    styles.option,
                    provincia === item && styles.optionSelected
                  ]}
                  onPress={() => {
                    setProvincia(item);
                    setProvinciaMenuVisible(false);
                  }}
                  activeOpacity={0.7}
                >
                  <View style={styles.optionContent}>
                    <View style={styles.iconContainer}>
                      <IconButton
                        icon="map-marker"
                        size={24}
                        iconColor={provincia === item ? Colors.primary : Colors.textLight}
                        style={styles.icon}
                      />
                    </View>
                    <Text style={[
                      styles.optionText,
                      provincia === item && styles.optionTextSelected
                    ]}>
                      {item}
                    </Text>
                  </View>
                  {provincia === item && (
                    <View style={styles.checkIconContainer}>
                      <IconButton
                        icon="check-circle"
                        size={24}
                        iconColor={Colors.primary}
                        style={{ margin: 0 }}
                      />
                    </View>
                  )}
                </TouchableOpacity>
              )}
            />
          </CustomModal>

          {/* Modal de selección de Distrito */}
          <CustomModal
            visible={distritoMenuVisible}
            onDismiss={() => setDistritoMenuVisible(false)}
            title="Seleccionar Distrito"
          >
            <FlatList
              data={distritos}
              keyExtractor={(item) => item}
              contentContainerStyle={styles.list}
              style={styles.listContainer}
              renderItem={({ item }) => (
                <TouchableOpacity
                  style={[
                    styles.option,
                    distrito === item && styles.optionSelected
                  ]}
                  onPress={() => {
                    setDistrito(item);
                    setDistritoMenuVisible(false);
                  }}
                  activeOpacity={0.7}
                >
                  <View style={styles.optionContent}>
                    <View style={styles.iconContainer}>
                      <IconButton
                        icon="map-marker"
                        size={24}
                        iconColor={distrito === item ? Colors.primary : Colors.textLight}
                        style={styles.icon}
                      />
                    </View>
                    <Text style={[
                      styles.optionText,
                      distrito === item && styles.optionTextSelected
                    ]}>
                      {item}
                    </Text>
                  </View>
                  {distrito === item && (
                    <View style={styles.checkIconContainer}>
                      <IconButton
                        icon="check-circle"
                        size={24}
                        iconColor={Colors.primary}
                        style={{ margin: 0 }}
                      />
                    </View>
                  )}
                </TouchableOpacity>
              )}
            />
          </CustomModal>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  scrollContent: {
    flexGrow: 1,
    padding: 24,
  },
  formContainer: {
    width: '100%',
  },
  title: {
    marginBottom: 8,
    marginTop: 40,
    fontWeight: '600',
    textAlign: 'center',
    color: Colors.textDark,
  },
  subtitle: {
    marginBottom: 24,
    textAlign: 'center',
    color: Colors.textLight,
  },
  label: {
    marginBottom: 8,
    marginTop: 8,
    color: Colors.textDark,
  },
  fieldLabel: {
    marginBottom: 8,
    marginTop: 12,
    color: Colors.textDark,
  },
  segmentedButtons: {
    marginBottom: 16,
  },
  input: {
    marginBottom: 16,
    backgroundColor: Colors.surface,
  },
  nativeInputContainer: {
    marginBottom: 16,
  },
  nativeInputLabel: {
    marginBottom: 8,
    color: Colors.textDark,
    fontSize: 12,
  },
  nativeInput: {
    borderWidth: 1,
    borderColor: '#ccc',
    borderRadius: 4,
    padding: 16,
    fontSize: 16,
    backgroundColor: Colors.surface,
    color: Colors.textDark,
  },
  error: {
    marginBottom: 8,
  },
  selector: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: '#ccc',
    borderRadius: 4,
    paddingLeft: 16,
    paddingRight: 4,
    marginBottom: 8,
    minHeight: 56,
  },
  selectorText: {
    fontSize: 16,
    color: Colors.textDark,
  },
  list: {
    paddingBottom: 20,
  },
  listContainer: {
    maxHeight: 400,
  },
  option: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 14,
    paddingHorizontal: 20,
    borderBottomWidth: 1,
    borderBottomColor: '#f3f4f6',
    backgroundColor: Colors.surface,
  },
  optionSelected: {
    backgroundColor: '#f0f9ff',
    borderLeftWidth: 4,
    borderLeftColor: Colors.primary,
  },
  optionContent: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  iconContainer: {
    marginRight: 12,
  },
  icon: {
    margin: 0,
  },
  optionText: {
    fontSize: 16,
    color: Colors.textDark,
    fontWeight: '500',
  },
  optionTextSelected: {
    color: Colors.primary,
    fontWeight: '600',
  },
  checkIconContainer: {
    marginLeft: 12,
  },
  button: {
    marginTop: 8,
    paddingVertical: 8,
  },
  cancelButton: {
    marginTop: 12,
  },
  disabledSelector: {
    backgroundColor: '#f5f5f5',
    opacity: 0.6,
  },
  disabledText: {
    color: '#999',
  },
  sectionLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: Colors.textDark,
    marginTop: 12,
    marginBottom: 8,
  },
  checkboxContainer: {
    marginTop: 16,
    marginBottom: 8,
  },
  checkboxRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  checkboxTextContainer: {
    flex: 1,
    justifyContent: 'center',
    marginLeft: 8,
  },
  checkboxText: {
    fontSize: 14,
    color: Colors.textDark,
    lineHeight: 20,
  },
  checkboxLink: {
    color: Colors.primary,
    textDecorationLine: 'underline',
    fontWeight: '600',
  },
});
