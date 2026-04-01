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
import { TextInput, Text, IconButton } from 'react-native-paper';
import { useNavigation, useRoute, RouteProp } from '@react-navigation/native';
import { LinearGradient } from 'expo-linear-gradient';
import axios from 'axios';
import { Colors } from '../constants/colors';
import { API_CONFIG } from '../constants/config';
import { getDepartamentos, getProvincias, getDistritos } from '../data/ubigeo';
import { CustomModal } from '../components/CustomModal';
import { KeyboardAwareScrollView } from '../components/KeyboardAwareScrollView';

type RegisterRouteParams = {
  Register: {
    tipoPersona?: 'Natural' | 'Jurídica';
  };
};

type RegisterScreenRouteProp = RouteProp<RegisterRouteParams, 'Register'>;

// ── Section header helper ──────────────────────────────────────────────────
const SectionHeader = ({
  icon,
  label,
  color = Colors.primary,
}: {
  icon: string;
  label: string;
  color?: string;
}) => (
  <View style={[sectionHeaderStyles.wrap, { borderLeftColor: color }]}>
    <IconButton icon={icon} size={16} iconColor={color} style={sectionHeaderStyles.icon} />
    <Text style={[sectionHeaderStyles.text, { color }]}>{label.toUpperCase()}</Text>
  </View>
);

const sectionHeaderStyles = StyleSheet.create({
  wrap: {
    flexDirection: 'row',
    alignItems: 'center',
    borderLeftWidth: 3,
    paddingLeft: 8,
    marginTop: 24,
    marginBottom: 12,
  },
  icon: { margin: 0, marginRight: 2 },
  text: { fontSize: 11, fontWeight: '800', letterSpacing: 1 },
});

// ── Tipo-persona toggle ────────────────────────────────────────────────────
const TipoToggle = ({
  value,
  onChange,
}: {
  value: 'Natural' | 'Jurídica';
  onChange: (v: 'Natural' | 'Jurídica') => void;
}) => (
  <View style={toggleStyles.row}>
    {(['Natural', 'Jurídica'] as const).map((t) => {
      const active = value === t;
      return (
        <TouchableOpacity
          key={t}
          onPress={() => onChange(t)}
          activeOpacity={0.8}
          style={[toggleStyles.btn, active && toggleStyles.btnActive]}
        >
          <Text style={[toggleStyles.label, active && toggleStyles.labelActive]}>
            {t === 'Natural' ? '👤  Persona Natural' : '🏢  Persona Jurídica'}
          </Text>
        </TouchableOpacity>
      );
    })}
  </View>
);

const toggleStyles = StyleSheet.create({
  row: { flexDirection: 'row', gap: 10, marginBottom: 4 },
  btn: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 12,
    borderWidth: 1.5,
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
    alignItems: 'center',
  },
  btnActive: {
    borderColor: Colors.primary,
    backgroundColor: '#f0fdf4',
  },
  label: { fontSize: 13, fontWeight: '600', color: Colors.textLight },
  labelActive: { color: Colors.primaryDark },
});


// ── Location selector row ──────────────────────────────────────────────────
const LocationSelector = ({
  label,
  value,
  placeholder,
  disabled,
  onPress,
}: {
  label: string;
  value: string;
  placeholder: string;
  disabled?: boolean;
  onPress: () => void;
}) => (
  <TouchableOpacity
    onPress={disabled ? undefined : onPress}
    activeOpacity={disabled ? 1 : 0.7}
    style={[locStyles.wrap, disabled && locStyles.disabled]}
  >
    <IconButton icon="map-marker-outline" size={20} iconColor={disabled ? '#ccc' : Colors.primary} style={locStyles.icon} />
    <View style={locStyles.textWrap}>
      <Text style={locStyles.labelTxt}>{label}</Text>
      <Text style={[locStyles.valueTxt, !value && locStyles.placeholder, disabled && locStyles.placeholderDisabled]}>
        {value || placeholder}
      </Text>
    </View>
    <IconButton icon="chevron-right" size={20} iconColor={disabled ? '#ccc' : Colors.textLight} style={locStyles.chevron} />
  </TouchableOpacity>
);

const locStyles = StyleSheet.create({
  wrap: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: 12,
    marginBottom: 10,
    minHeight: 64,
    overflow: 'hidden',
  },
  disabled: { backgroundColor: '#f8f9fa', opacity: 0.6 },
  icon: { margin: 0, marginLeft: 4 },
  chevron: { margin: 0, marginRight: 4 },
  textWrap: { flex: 1 },
  labelTxt: { fontSize: 11, color: Colors.textLight, fontWeight: '600', marginBottom: 2 },
  valueTxt: { fontSize: 15, color: Colors.textDark, fontWeight: '500' },
  placeholder: { color: Colors.textMuted },
  placeholderDisabled: { color: '#ccc' },
});

// ── Main screen ────────────────────────────────────────────────────────────
export const RegisterScreen = () => {
  const navigation = useNavigation();
  const route = useRoute<RegisterScreenRouteProp>();

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

  const [departamentos, setDepartamentos] = useState<string[]>([]);
  const [provincias, setProvincias] = useState<string[]>([]);
  const [distritos, setDistritos] = useState<string[]>([]);
  const [departamentoMenuVisible, setDepartamentoMenuVisible] = useState(false);
  const [provinciaMenuVisible, setProvinciaMenuVisible] = useState(false);
  const [distritoMenuVisible, setDistritoMenuVisible] = useState(false);
  const [docTypeMenuVisible, setDocTypeMenuVisible] = useState(false);

  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const [acceptTerms, setAcceptTerms] = useState(false);
  const [acceptPrivacy, setAcceptPrivacy] = useState(false);
  const [acceptPromotions, setAcceptPromotions] = useState(false);

  useEffect(() => {
    if (route.params?.tipoPersona) setTipoPersona(route.params.tipoPersona);
  }, [route.params?.tipoPersona]);

  useEffect(() => {
    setDepartamentos(getDepartamentos());
  }, []);

  useEffect(() => {
    if (departamento) {
      setProvincias(getProvincias(departamento));
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

  useEffect(() => {
    if (departamento && provincia) {
      setDistritos(getDistritos(departamento, provincia));
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

    if (!email || !email.includes('@')) { setError('Email inválido'); return false; }
    if (!telefono) { setError('Teléfono es obligatorio'); return false; }
    if (!direccion) { setError('Dirección es obligatoria'); return false; }
    if (!departamento) { setError('Departamento es obligatorio'); return false; }
    if (!provincia) { setError('Provincia es obligatoria'); return false; }
    if (!distrito) { setError('Distrito es obligatorio'); return false; }
    if (!password || password.length < 8) { setError('La contraseña debe tener al menos 8 caracteres'); return false; }
    if (password !== confirmPassword) { setError('Las contraseñas no coinciden'); return false; }
    if (!acceptTerms) { setError('Debes aceptar los Términos y Condiciones'); return false; }
    if (!acceptPrivacy) { setError('Debes aceptar la Política de Privacidad'); return false; }
    return true;
  };

  const handleRegister = async () => {
    try {
      setError('');
      if (!validateForm()) return;
      setLoading(true);

      const payload: any = {
        tipo_persona: tipoPersona,
        email,
        telefono,
        direccion,
        departamento,
        provincia,
        distrito,
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

      const response = await axios.post(`${API_CONFIG.BASE_URL}/api/client/register`, payload);

      if (response.data.success) {
        Alert.alert(
          '✅ Registro Exitoso',
          `Tu cuenta ha sido creada.\n\n📧 Recibirás un email de confirmación.\n\nInicia sesión con tu ${tipoPersona === 'Jurídica' ? 'RUC' : 'DNI'} y la contraseña que creaste.`,
          [{ text: 'Iniciar Sesión', onPress: () => navigation.reset({ index: 0, routes: [{ name: 'Login' }] }) }]
        );
      } else {
        setError(response.data.message || 'Error al registrarse');
      }
    } catch (err: any) {
      const msg = err.response?.data?.message || err.message || 'Error al registrarse';
      setError(msg);
      Alert.alert('❌ Error en el Registro', msg, [{ text: 'OK' }]);
    } finally {
      setLoading(false);
    }
  };

  const inputTheme = {
    colors: {
      primary: Colors.primary,
      onSurfaceVariant: Colors.textLight,
      background: Colors.surface,
    },
    roundness: 12,
  };

  const styledInput = (extra?: object) => ({
    backgroundColor: Colors.surface,
    marginBottom: 10,
    ...extra,
  });

  const renderModalList = (
    data: string[],
    selected: string,
    onSelect: (v: string) => void,
    onDismiss: () => void
  ) => (
    <FlatList
      data={data}
      keyExtractor={(item) => item}
      style={{ maxHeight: 400 }}
      contentContainerStyle={{ paddingBottom: 20 }}
      renderItem={({ item }) => {
        const isSelected = item === selected;
        return (
          <TouchableOpacity
            style={[modalListStyles.item, isSelected && modalListStyles.itemSelected]}
            onPress={() => { onSelect(item); onDismiss(); }}
            activeOpacity={0.7}
          >
            <IconButton icon="map-marker" size={18} iconColor={isSelected ? Colors.primary : Colors.textLight} style={{ margin: 0 }} />
            <Text style={[modalListStyles.itemText, isSelected && modalListStyles.itemTextSelected]}>{item}</Text>
            {isSelected && <IconButton icon="check-circle" size={18} iconColor={Colors.primary} style={{ margin: 0 }} />}
          </TouchableOpacity>
        );
      }}
    />
  );

  return (
    <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        {/* ── Gradient Header (scrolls with content) ── */}
        <LinearGradient colors={['#0D1B2A', '#16a34a']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.header}>
          <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn} activeOpacity={0.7}>
            <IconButton icon="arrow-left" size={20} iconColor="#fff" style={{ margin: 0 }} />
          </TouchableOpacity>
          <View style={styles.headerContent}>
            <Text style={styles.headerBadgeText}>{tipoPersona === 'Natural' ? '👤' : '🏢'}</Text>
            <View>
              <Text style={styles.headerTitle}>Crear Cuenta</Text>
              <Text style={styles.headerSubtitle}>
                {tipoPersona === 'Natural' ? 'Persona Natural' : 'Persona Jurídica'}
              </Text>
            </View>
          </View>
        </LinearGradient>

        <View style={styles.formWrap}>
        {/* ── Tipo de Persona ── */}
        {!route.params?.tipoPersona && (
          <View style={styles.card}>
            <SectionHeader icon="account-switch" label="Tipo de cuenta" color="#6366f1" />
            <TipoToggle value={tipoPersona} onChange={setTipoPersona} />
          </View>
        )}

        {/* ── Datos de Identidad ── */}
        <View style={styles.card}>
          <SectionHeader icon="card-account-details-outline" label="Datos de identidad" color="#0891b2" />

          {tipoPersona === 'Natural' ? (
            <>
              <LocationSelector
                label="Elegir tipo de documento"
                value={tipoDocumento === 'DNI' ? '🪪  DNI — Documento Nacional de Identidad (8 dígitos)' : '📘  CE — Carnet de Extranjería (9 dígitos)'}
                placeholder="Seleccionar tipo de documento"
                onPress={() => setDocTypeMenuVisible(true)}
              />
              <TextInput
                label={`Número de ${tipoDocumento} *`}
                value={dni}
                onChangeText={(t) => { setDni(t); setError(''); }}
                mode="outlined"
                keyboardType="numeric"
                maxLength={tipoDocumento === 'DNI' ? 8 : 9}
                style={styledInput()}
                theme={inputTheme}
                left={<TextInput.Icon icon="identifier" />}
              />
              <TextInput
                label="Nombres *"
                value={nombres}
                onChangeText={(t) => { setNombres(t); setError(''); }}
                mode="outlined"
                autoCapitalize="words"
                style={styledInput()}
                theme={inputTheme}
                left={<TextInput.Icon icon="account-outline" />}
              />
              <View style={styles.row}>
                <TextInput
                  label="Ap. Paterno *"
                  value={apellidoPaterno}
                  onChangeText={(t) => { setApellidoPaterno(t); setError(''); }}
                  mode="outlined"
                  autoCapitalize="words"
                  style={[styledInput(), styles.flex1]}
                  theme={inputTheme}
                />
                <TextInput
                  label="Ap. Materno"
                  value={apellidoMaterno}
                  onChangeText={(t) => { setApellidoMaterno(t); setError(''); }}
                  mode="outlined"
                  autoCapitalize="words"
                  style={[styledInput(), styles.flex1]}
                  theme={inputTheme}
                />
              </View>
            </>
          ) : (
            <>
              <TextInput
                label="RUC *"
                value={ruc}
                onChangeText={(t) => { setRuc(t); setError(''); }}
                mode="outlined"
                keyboardType="numeric"
                maxLength={11}
                style={styledInput()}
                theme={inputTheme}
                left={<TextInput.Icon icon="barcode" />}
              />
              <TextInput
                label="Razón Social *"
                value={razonSocial}
                onChangeText={(t) => { setRazonSocial(t); setError(''); }}
                mode="outlined"
                autoCapitalize="words"
                style={styledInput()}
                theme={inputTheme}
                left={<TextInput.Icon icon="domain" />}
              />
              <TextInput
                label="Persona de Contacto *"
                value={personaContacto}
                onChangeText={(t) => { setPersonaContacto(t); setError(''); }}
                mode="outlined"
                autoCapitalize="words"
                style={styledInput()}
                theme={inputTheme}
                left={<TextInput.Icon icon="account-tie-outline" />}
              />
            </>
          )}
        </View>

        {/* ── Contacto ── */}
        <View style={styles.card}>
          <SectionHeader icon="phone-outline" label="Datos de contacto" color={Colors.primary} />
          <TextInput
            label="Email *"
            value={email}
            onChangeText={(t) => { setEmail(t); setError(''); }}
            mode="outlined"
            keyboardType="email-address"
            autoCapitalize="none"
            style={styledInput()}
            theme={inputTheme}
            left={<TextInput.Icon icon="email-outline" />}
          />
          <TextInput
            label="Teléfono *"
            value={telefono}
            onChangeText={(t) => { setTelefono(t); setError(''); }}
            mode="outlined"
            keyboardType="phone-pad"
            placeholder="+51 987 654 321"
            style={styledInput()}
            theme={inputTheme}
            left={<TextInput.Icon icon="phone-outline" />}
          />
        </View>

        {/* ── Ubicación ── */}
        <View style={styles.card}>
          <SectionHeader icon="map-marker-radius-outline" label="Ubicación" color="#f59e0b" />
          <TextInput
            label="Dirección completa *"
            value={direccion}
            onChangeText={(t) => { setDireccion(t); setError(''); }}
            mode="outlined"
            multiline
            numberOfLines={2}
            style={styledInput()}
            theme={inputTheme}
            left={<TextInput.Icon icon="home-outline" />}
          />
          <LocationSelector
            label="Departamento"
            value={departamento}
            placeholder="Seleccionar departamento"
            onPress={() => setDepartamentoMenuVisible(true)}
          />
          <LocationSelector
            label="Provincia"
            value={provincia}
            placeholder={departamento ? 'Seleccionar provincia' : 'Primero elige departamento'}
            disabled={!departamento}
            onPress={() => setProvinciaMenuVisible(true)}
          />
          <LocationSelector
            label="Distrito"
            value={distrito}
            placeholder={provincia ? 'Seleccionar distrito' : 'Primero elige provincia'}
            disabled={!provincia}
            onPress={() => setDistritoMenuVisible(true)}
          />
        </View>

        {/* ── Seguridad ── */}
        <View style={styles.card}>
          <SectionHeader icon="lock-outline" label="Seguridad" color="#7c3aed" />
          <TextInput
            label="Contraseña * (mín. 8 caracteres)"
            value={password}
            onChangeText={(t) => { setPassword(t); setError(''); }}
            mode="outlined"
            secureTextEntry={!showPassword}
            style={styledInput()}
            theme={inputTheme}
            left={<TextInput.Icon icon="lock-outline" />}
            right={<TextInput.Icon icon={showPassword ? 'eye-off-outline' : 'eye-outline'} onPress={() => setShowPassword(!showPassword)} />}
          />
          <TextInput
            label="Confirmar Contraseña *"
            value={confirmPassword}
            onChangeText={(t) => { setConfirmPassword(t); setError(''); }}
            mode="outlined"
            secureTextEntry={!showConfirmPassword}
            style={styledInput()}
            theme={inputTheme}
            left={<TextInput.Icon icon="lock-check-outline" />}
            right={<TextInput.Icon icon={showConfirmPassword ? 'eye-off-outline' : 'eye-outline'} onPress={() => setShowConfirmPassword(!showConfirmPassword)} />}
          />
        </View>

        {/* ── Aceptaciones ── */}
        <View style={[styles.card, styles.cardAccept]}>
          <SectionHeader icon="shield-check-outline" label="Términos y privacidad" color="#0891b2" />

          {[
            {
              checked: acceptTerms,
              onToggle: () => setAcceptTerms(!acceptTerms),
              text: (
                <Text style={checkStyles.txt}>
                  Acepto los{' '}
                  <Text style={checkStyles.link} onPress={(e) => { e.stopPropagation(); Linking.openURL(`${API_CONFIG.BASE_URL}/legal/terms`); }}>
                    Términos y Condiciones
                  </Text>
                  {' '}*
                </Text>
              ),
            },
            {
              checked: acceptPrivacy,
              onToggle: () => setAcceptPrivacy(!acceptPrivacy),
              text: (
                <Text style={checkStyles.txt}>
                  Acepto la{' '}
                  <Text style={checkStyles.link} onPress={(e) => { e.stopPropagation(); Linking.openURL(`${API_CONFIG.BASE_URL}/legal/privacy`); }}>
                    Política de Privacidad
                  </Text>
                  {' '}y el tratamiento de mis datos *
                </Text>
              ),
            },
            {
              checked: acceptPromotions,
              onToggle: () => setAcceptPromotions(!acceptPromotions),
              text: <Text style={checkStyles.txt}>Deseo recibir promociones y ofertas por correo</Text>,
              optional: true,
            },
          ].map(({ checked, onToggle, text, optional }, idx) => (
            <TouchableOpacity key={idx} onPress={onToggle} activeOpacity={0.7} style={checkStyles.row}>
              <View style={[checkStyles.box, checked && checkStyles.boxChecked]}>
                {checked && <IconButton icon="check" size={14} iconColor="#fff" style={{ margin: 0 }} />}
              </View>
              <View style={{ flex: 1 }}>{text}</View>
              {optional && (
                <View style={checkStyles.badge}>
                  <Text style={checkStyles.badgeTxt}>opcional</Text>
                </View>
              )}
            </TouchableOpacity>
          ))}
        </View>

        {/* ── Error ── */}
        {error ? (
          <View style={styles.errorWrap}>
            <IconButton icon="alert-circle-outline" size={18} iconColor={Colors.danger} style={{ margin: 0 }} />
            <Text style={styles.errorTxt}>{error}</Text>
          </View>
        ) : null}

        {/* ── Submit ── */}
        <TouchableOpacity
          onPress={handleRegister}
          disabled={loading}
          activeOpacity={0.85}
          style={{ borderRadius: 14, overflow: 'hidden', marginTop: 8 }}
        >
          <LinearGradient
            colors={loading ? ['#9ca3af', '#6b7280'] : [Colors.primary, Colors.primaryDark]}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 0 }}
            style={styles.submitGradient}
          >
            {loading ? (
              <Text style={styles.submitTxt}>Creando cuenta...</Text>
            ) : (
              <>
                <IconButton icon="account-plus-outline" size={20} iconColor="#fff" style={{ margin: 0 }} />
                <Text style={styles.submitTxt}>Crear Cuenta</Text>
              </>
            )}
          </LinearGradient>
        </TouchableOpacity>

        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.cancelBtn} activeOpacity={0.7}>
          <Text style={styles.cancelTxt}>Cancelar</Text>
        </TouchableOpacity>

        {/* ── Modals ── */}
        <CustomModal visible={docTypeMenuVisible} onDismiss={() => setDocTypeMenuVisible(false)} title="Elegir tipo de documento">
          <FlatList
            data={[
              { value: 'DNI' as const, label: '🪪  DNI', desc: 'Documento Nacional de Identidad', digits: '8 dígitos' },
              { value: 'CE' as const, label: '📘  CE', desc: 'Carnet de Extranjería', digits: '9 dígitos' },
            ]}
            keyExtractor={(item) => item.value}
            renderItem={({ item }) => {
              const isSelected = tipoDocumento === item.value;
              return (
                <TouchableOpacity
                  style={[modalListStyles.item, isSelected && modalListStyles.itemSelected]}
                  onPress={() => {
                    setTipoDocumento(item.value);
                    setDni('');
                    setError('');
                    setDocTypeMenuVisible(false);
                  }}
                  activeOpacity={0.7}
                >
                  <View style={{ flex: 1 }}>
                    <Text style={[modalListStyles.itemText, isSelected && modalListStyles.itemTextSelected]}>
                      {item.label}
                    </Text>
                    <Text style={{ fontSize: 12, color: Colors.textLight, marginTop: 2 }}>
                      {item.desc} — {item.digits}
                    </Text>
                  </View>
                  {isSelected && <IconButton icon="check-circle" size={20} iconColor={Colors.primary} style={{ margin: 0 }} />}
                </TouchableOpacity>
              );
            }}
          />
        </CustomModal>

        <CustomModal visible={departamentoMenuVisible} onDismiss={() => setDepartamentoMenuVisible(false)} title="Seleccionar Departamento">
          {renderModalList(departamentos, departamento, setDepartamento, () => setDepartamentoMenuVisible(false))}
        </CustomModal>

        <CustomModal visible={provinciaMenuVisible} onDismiss={() => setProvinciaMenuVisible(false)} title="Seleccionar Provincia">
          {renderModalList(provincias, provincia, setProvincia, () => setProvinciaMenuVisible(false))}
        </CustomModal>

        <CustomModal visible={distritoMenuVisible} onDismiss={() => setDistritoMenuVisible(false)} title="Seleccionar Distrito">
          {renderModalList(distritos, distrito, setDistrito, () => setDistritoMenuVisible(false))}
        </CustomModal>

        </View>{/* end formWrap */}
      </ScrollView>
    </KeyboardAvoidingView>
  );
};

// ── Checkbox styles ────────────────────────────────────────────────────────
const checkStyles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: Colors.divider,
  },
  box: {
    width: 22,
    height: 22,
    borderRadius: 6,
    borderWidth: 2,
    borderColor: Colors.border,
    backgroundColor: '#fff',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 2,
  },
  boxChecked: { backgroundColor: Colors.primary, borderColor: Colors.primary },
  txt: { fontSize: 13, color: Colors.text, lineHeight: 19, flex: 1 },
  link: { color: Colors.primary, fontWeight: '700', textDecorationLine: 'underline' },
  badge: {
    backgroundColor: '#f1f5f9',
    borderRadius: 8,
    paddingHorizontal: 8,
    paddingVertical: 2,
    alignSelf: 'center',
  },
  badgeTxt: { fontSize: 10, color: Colors.textLight, fontWeight: '600' },
});

// ── Modal list styles ──────────────────────────────────────────────────────
const modalListStyles = StyleSheet.create({
  item: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderBottomWidth: 1,
    borderBottomColor: Colors.divider,
    backgroundColor: Colors.surface,
    gap: 8,
  },
  itemSelected: {
    backgroundColor: '#f0fdf4',
    borderLeftWidth: 3,
    borderLeftColor: Colors.primary,
  },
  itemText: { flex: 1, fontSize: 15, color: Colors.textDark, fontWeight: '500' },
  itemTextSelected: { color: Colors.primaryDark, fontWeight: '700' },
});

// ── Main styles ────────────────────────────────────────────────────────────
const styles = StyleSheet.create({
  /* Compact horizontal header — scrolls with content */
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingTop: Platform.OS === 'ios' ? 52 : 32,
    paddingBottom: 14,
    paddingHorizontal: 16,
    gap: 12,
  },
  backBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: 'rgba(255,255,255,0.15)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerContent: { flexDirection: 'row', alignItems: 'center', gap: 10, flex: 1 },
  headerBadgeText: { fontSize: 26 },
  headerTitle: { fontSize: 18, fontWeight: '800', color: '#fff', letterSpacing: -0.3 },
  headerSubtitle: { fontSize: 12, color: 'rgba(255,255,255,0.72)', marginTop: 1, fontWeight: '500' },

  scroll: { backgroundColor: '#f1f5f9' },
  scrollContent: { paddingBottom: 40 },
  formWrap: { padding: 16 },

  card: {
    backgroundColor: Colors.surface,
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 2,
  },
  cardAccept: { paddingBottom: 4 },

  row: { flexDirection: 'row', gap: 10 },
  flex1: { flex: 1 },

  errorWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#fef2f2',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#fecaca',
    padding: 12,
    marginBottom: 12,
    gap: 6,
  },
  errorTxt: { flex: 1, color: Colors.danger, fontSize: 13, fontWeight: '500' },

  submitGradient: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 16,
    gap: 4,
  },
  submitTxt: { color: '#fff', fontSize: 16, fontWeight: '700' },

  cancelBtn: { alignItems: 'center', paddingVertical: 16 },
  cancelTxt: { color: Colors.textLight, fontSize: 14, fontWeight: '600' },
});
