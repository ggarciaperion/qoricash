import React, { useState, useEffect, useRef } from 'react';
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
  ActivityIndicator,
  Modal,
  Animated,
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

// ── Processing overlay ────────────────────────────────────────────────────
const PROCESSING_MESSAGES = [
  'Verificando tu información...',
  'Creando tu cuenta...',
  'Procesando datos...',
  'Configurando perfil...',
  'Casi listo...',
];

const RegistrationProcessingOverlay: React.FC<{ visible: boolean }> = ({ visible }) => {
  const [msgIndex, setMsgIndex] = useState(0);
  const fadeAnim = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    if (!visible) return;
    setMsgIndex(0);
    const interval = setInterval(() => {
      Animated.sequence([
        Animated.timing(fadeAnim, { toValue: 0, duration: 200, useNativeDriver: true }),
        Animated.timing(fadeAnim, { toValue: 1, duration: 300, useNativeDriver: true }),
      ]).start();
      setMsgIndex(i => (i + 1) % PROCESSING_MESSAGES.length);
    }, 1800);
    return () => clearInterval(interval);
  }, [visible]);

  return (
    <Modal visible={visible} transparent animationType="fade" statusBarTranslucent>
      <View style={processingStyles.overlay}>
        <View style={processingStyles.card}>
          <View style={processingStyles.spinnerWrap}>
            <ActivityIndicator size={48} color={Colors.primary} />
            <View style={processingStyles.spinnerRing} />
          </View>
          <Text style={processingStyles.title}>Procesando</Text>
          <Animated.Text style={[processingStyles.message, { opacity: fadeAnim }]}>
            {PROCESSING_MESSAGES[msgIndex]}
          </Animated.Text>
          <View style={processingStyles.dots}>
            {[0, 1, 2].map(i => (
              <View key={i} style={processingStyles.dot} />
            ))}
          </View>
        </View>
      </View>
    </Modal>
  );
};

const processingStyles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(13,27,42,0.85)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  card: {
    backgroundColor: Colors.surface,
    borderRadius: 24,
    padding: 40,
    alignItems: 'center',
    width: '100%',
    maxWidth: 320,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.25,
    shadowRadius: 20,
    elevation: 12,
  },
  spinnerWrap: {
    width: 80,
    height: 80,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 24,
  },
  spinnerRing: {
    position: 'absolute',
    width: 80,
    height: 80,
    borderRadius: 40,
    borderWidth: 2,
    borderColor: Colors.primaryLight,
    opacity: 0.3,
  },
  title: {
    fontSize: 20,
    fontWeight: '700',
    color: Colors.textDark,
    marginBottom: 8,
    letterSpacing: 0.3,
  },
  message: {
    fontSize: 14,
    color: Colors.textLight,
    textAlign: 'center',
    lineHeight: 20,
    minHeight: 20,
  },
  dots: {
    flexDirection: 'row',
    gap: 6,
    marginTop: 20,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: Colors.primary,
    opacity: 0.4,
  },
});

// ── Success modal ──────────────────────────────────────────────────────────
const RegistrationSuccessModal: React.FC<{
  visible: boolean;
  docLabel: string;
  onContinue: () => void;
}> = ({ visible, docLabel, onContinue }) => {
  const scaleAnim = useRef(new Animated.Value(0.6)).current;
  const opacityAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (visible) {
      Animated.parallel([
        Animated.spring(scaleAnim, { toValue: 1, tension: 60, friction: 7, useNativeDriver: true }),
        Animated.timing(opacityAnim, { toValue: 1, duration: 300, useNativeDriver: true }),
      ]).start();
    } else {
      scaleAnim.setValue(0.6);
      opacityAnim.setValue(0);
    }
  }, [visible]);

  return (
    <Modal visible={visible} transparent animationType="fade" statusBarTranslucent>
      <View style={successStyles.overlay}>
        <Animated.View style={[successStyles.card, { opacity: opacityAnim, transform: [{ scale: scaleAnim }] }]}>
          {/* Ícono */}
          <View style={successStyles.iconCircle}>
            <View style={successStyles.iconCircleInner}>
              <IconButton icon="check-bold" size={36} iconColor="#fff" style={{ margin: 0 }} />
            </View>
          </View>

          {/* Título */}
          <Text style={successStyles.title}>¡Cuenta creada!</Text>
          <Text style={successStyles.subtitle}>Tu registro fue exitoso</Text>

          {/* Separador */}
          <View style={successStyles.divider} />

          {/* Detalles */}
          <View style={successStyles.infoBox}>
            <IconButton icon="email-check-outline" size={18} iconColor={Colors.primary} style={{ margin: 0 }} />
            <Text style={successStyles.infoText}>
              Recibirás un correo de confirmación con los detalles de tu cuenta.
            </Text>
          </View>
          <View style={successStyles.infoBox}>
            <IconButton icon="shield-check-outline" size={18} iconColor={Colors.info} style={{ margin: 0 }} />
            <Text style={successStyles.infoText}>
              Tu cuenta será activada luego de la verificación de identidad.
            </Text>
          </View>

          {/* CTA */}
          <TouchableOpacity onPress={onContinue} activeOpacity={0.85} style={{ width: '100%', marginTop: 24 }}>
            <LinearGradient
              colors={[Colors.primary, Colors.primaryDark]}
              start={{ x: 0, y: 0 }}
              end={{ x: 1, y: 0 }}
              style={successStyles.ctaBtn}
            >
              <IconButton icon="login" size={20} iconColor="#fff" style={{ margin: 0 }} />
              <Text style={successStyles.ctaTxt}>Iniciar Sesión</Text>
            </LinearGradient>
          </TouchableOpacity>

          <Text style={successStyles.hint}>Usa tu {docLabel} y la contraseña que creaste</Text>
        </Animated.View>
      </View>
    </Modal>
  );
};

const successStyles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(13,27,42,0.75)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  card: {
    backgroundColor: Colors.surface,
    borderRadius: 28,
    padding: 32,
    alignItems: 'center',
    width: '100%',
    maxWidth: 340,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.2,
    shadowRadius: 24,
    elevation: 14,
  },
  iconCircle: {
    width: 96,
    height: 96,
    borderRadius: 48,
    backgroundColor: `${Colors.primary}18`,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 20,
  },
  iconCircleInner: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: Colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: Colors.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.4,
    shadowRadius: 12,
    elevation: 6,
  },
  title: {
    fontSize: 24,
    fontWeight: '800',
    color: Colors.textDark,
    textAlign: 'center',
    letterSpacing: 0.2,
  },
  subtitle: {
    fontSize: 14,
    color: Colors.textLight,
    marginTop: 4,
    marginBottom: 20,
    textAlign: 'center',
  },
  divider: {
    width: '100%',
    height: 1,
    backgroundColor: Colors.border,
    marginBottom: 20,
  },
  infoBox: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    width: '100%',
    marginBottom: 8,
  },
  infoText: {
    flex: 1,
    fontSize: 13,
    color: Colors.text,
    lineHeight: 18,
    paddingTop: 10,
  },
  ctaBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 14,
    paddingVertical: 14,
    paddingHorizontal: 24,
    gap: 4,
  },
  ctaTxt: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '700',
    letterSpacing: 0.3,
  },
  hint: {
    fontSize: 12,
    color: Colors.textMuted,
    marginTop: 12,
    textAlign: 'center',
  },
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
  const [showProcessing, setShowProcessing] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);

  // ── Estado lookup RENIEC / SUNAT ─────────────────────────────────────────
  const [lookupLoading, setLookupLoading] = useState(false);
  const [lookupMsg, setLookupMsg] = useState<{ type: 'success' | 'error' | 'warning'; text: string } | null>(null);
  const [lookupLocked, setLookupLocked] = useState(false);

  const [acceptTerms, setAcceptTerms] = useState(false);
  const [acceptPrivacy, setAcceptPrivacy] = useState(false);
  const [acceptPromotions, setAcceptPromotions] = useState(false);

  useEffect(() => {
    if (route.params?.tipoPersona) setTipoPersona(route.params.tipoPersona);
  }, [route.params?.tipoPersona]);

  useEffect(() => {
    setDepartamentos(getDepartamentos());
  }, []);

  const skipUbigeoReset = useRef(false);

  useEffect(() => {
    if (skipUbigeoReset.current) return;
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
    if (skipUbigeoReset.current) return;
    if (departamento && provincia) {
      setDistritos(getDistritos(departamento, provincia));
      setDistrito('');
    } else {
      setDistritos([]);
      setDistrito('');
    }
  }, [provincia, departamento]);

  // ── Consulta RENIEC / SUNAT ───────────────────────────────────────────────
  const handleLookup = async () => {
    setLookupMsg(null);
    setLookupLocked(false);

    const isRuc = tipoPersona === 'Jurídica';
    const docNum = isRuc ? ruc.trim() : dni.trim();
    const expectedLen = isRuc ? 11 : (tipoDocumento === 'DNI' ? 8 : 9);

    if (docNum.length !== expectedLen) {
      setLookupMsg({ type: 'warning', text: `Ingresa los ${expectedLen} dígitos antes de buscar.` });
      return;
    }

    if (!isRuc && tipoDocumento === 'CE') {
      setLookupMsg({ type: 'warning', text: 'La búsqueda automática solo está disponible para DNI.' });
      return;
    }

    setLookupLoading(true);
    try {
      const endpoint = isRuc
        ? `${API_CONFIG.BASE_URL}/api/web/ruc-lookup?numero=${encodeURIComponent(docNum)}`
        : `${API_CONFIG.BASE_URL}/api/web/dni-lookup?numero=${encodeURIComponent(docNum)}`;

      const res  = await axios.get(endpoint);
      const data = res.data;

      if (!data.success) {
        setLookupMsg({ type: 'error', text: data.message || 'No se encontró el documento.' });
        return;
      }

      if (isRuc) {
        setRazonSocial(data.razon_social || '');
        if (data.direccion) setDireccion(data.direccion);
        if (data.departamento || data.provincia || data.distrito) {
          skipUbigeoReset.current = true;
          if (data.departamento) {
            setProvincias(getProvincias(data.departamento));
            setDepartamento(data.departamento);
          }
          if (data.provincia) {
            setDistritos(getDistritos(data.departamento, data.provincia));
            setProvincia(data.provincia);
          }
          if (data.distrito) setDistrito(data.distrito);
          setTimeout(() => { skipUbigeoReset.current = false; }, 0);
        }

        const estado = data.estado || '';
        const esActivo = estado.includes('ACTIVO');
        setLookupMsg({
          type: esActivo ? 'success' : 'warning',
          text: `${data.razon_social}${estado ? ` — ${estado}` : ''}${data.condicion ? ` · ${data.condicion}` : ''}`,
        });
      } else {
        setNombres(data.nombres || '');
        setApellidoPaterno(data.apellido_paterno || '');
        setApellidoMaterno(data.apellido_materno || '');
        setLookupMsg({
          type: 'success',
          text: `${data.apellido_paterno} ${data.apellido_materno}, ${data.nombres}`,
        });
      }
      setLookupLocked(true);
    } catch (err: any) {
      const msg = err.response?.data?.message || 'No se pudo conectar con el servicio.';
      setLookupMsg({ type: 'error', text: msg });
    } finally {
      setLookupLoading(false);
    }
  };

  // Resetear lookup cuando cambia el número de documento
  const handleDniChange = (text: string) => {
    setDni(text);
    setError('');
    if (lookupLocked) { setLookupLocked(false); setLookupMsg(null); }
  };

  const handleRucChange = (text: string) => {
    setRuc(text);
    setError('');
    if (lookupLocked) { setLookupLocked(false); setLookupMsg(null); }
  };

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

      // Fase 1: mostrar overlay de procesamiento y deshabilitar botón
      setLoading(true);
      setShowProcessing(true);

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

      // Fase 2: ocultar procesamiento y mostrar resultado
      setShowProcessing(false);

      if (response.data.success) {
        setShowSuccess(true);
      } else {
        setError(response.data.message || 'Error al registrarse');
      }
    } catch (err: any) {
      setShowProcessing(false);
      const msg = err.response?.data?.message || err.message || 'Error al registrarse. Intenta nuevamente.';
      setError(msg);
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

  const UbigeoPickerContent = ({
    data,
    selected,
    onSelect,
    onDismiss,
  }: {
    data: string[];
    selected: string;
    onSelect: (v: string) => void;
    onDismiss: () => void;
  }) => {
    const [query, setQuery] = useState('');
    const filtered = query.trim()
      ? data.filter(item => item.toLowerCase().includes(query.toLowerCase()))
      : data;

    return (
      <View style={{ flex: 1 }}>
        {/* Buscador */}
        <View style={modalListStyles.searchBox}>
          <IconButton icon="magnify" size={18} iconColor={Colors.textLight} style={{ margin: 0 }} />
          <RNTextInput
            placeholder="Buscar..."
            placeholderTextColor={Colors.textLight}
            value={query}
            onChangeText={setQuery}
            style={modalListStyles.searchInput}
            autoCorrect={false}
            autoCapitalize="characters"
          />
          {query.length > 0 && (
            <IconButton icon="close-circle" size={16} iconColor={Colors.textLight} style={{ margin: 0 }} onPress={() => setQuery('')} />
          )}
        </View>

        {filtered.length === 0 ? (
          <View style={modalListStyles.emptyBox}>
            <Text style={modalListStyles.emptyText}>Sin resultados</Text>
          </View>
        ) : (
          <FlatList
            data={filtered}
            keyExtractor={(item) => item}
            style={{ flex: 1 }}
            keyboardShouldPersistTaps="handled"
            renderItem={({ item }) => {
              const isSelected = item === selected;
              return (
                <TouchableOpacity
                  style={[modalListStyles.item, isSelected && modalListStyles.itemSelected]}
                  onPress={() => { onSelect(item); onDismiss(); }}
                  activeOpacity={0.7}
                >
                  <IconButton icon="map-marker-outline" size={16} iconColor={isSelected ? Colors.primary : Colors.textLight} style={{ margin: 0 }} />
                  <Text style={[modalListStyles.itemText, isSelected && modalListStyles.itemTextSelected]}>{item}</Text>
                  {isSelected && <IconButton icon="check-circle" size={16} iconColor={Colors.primary} style={{ margin: 0 }} />}
                </TouchableOpacity>
              );
            }}
          />
        )}
      </View>
    );
  };

  const renderModalList = (
    data: string[],
    selected: string,
    onSelect: (v: string) => void,
    onDismiss: () => void
  ) => (
    <UbigeoPickerContent data={data} selected={selected} onSelect={onSelect} onDismiss={onDismiss} />
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
                onPress={() => { setDocTypeMenuVisible(true); setLookupLocked(false); setLookupMsg(null); }}
              />

              {/* Campo DNI + botón búsqueda RENIEC */}
              <View style={lookupStyles.row}>
                <TextInput
                  label={`Número de ${tipoDocumento} *`}
                  value={dni}
                  onChangeText={handleDniChange}
                  mode="outlined"
                  keyboardType="numeric"
                  maxLength={tipoDocumento === 'DNI' ? 8 : 9}
                  style={[styledInput(), { flex: 1, marginBottom: 0 },
                    lookupLocked && { backgroundColor: '#f0fdf4' }]}
                  theme={lookupLocked
                    ? { ...inputTheme, colors: { ...inputTheme.colors, primary: '#16a34a', onSurfaceVariant: '#16a34a' } }
                    : inputTheme}
                  left={<TextInput.Icon icon="identifier" />}
                  editable={!lookupLocked}
                />
                {tipoDocumento === 'DNI' && (
                  <TouchableOpacity
                    onPress={handleLookup}
                    disabled={lookupLoading}
                    style={[lookupStyles.btn, lookupLoading && lookupStyles.btnDisabled]}
                    activeOpacity={0.8}
                  >
                    {lookupLoading
                      ? <ActivityIndicator size={18} color="#fff" />
                      : <IconButton icon="magnify" size={18} iconColor="#fff" style={{ margin: 0 }} />
                    }
                  </TouchableOpacity>
                )}
              </View>

              {/* Feedback lookup */}
              {lookupMsg && (
                <View style={[lookupStyles.feedback,
                  lookupMsg.type === 'success' && lookupStyles.fbSuccess,
                  lookupMsg.type === 'warning' && lookupStyles.fbWarning,
                  lookupMsg.type === 'error'   && lookupStyles.fbError,
                ]}>
                  <IconButton
                    icon={lookupMsg.type === 'success' ? 'check-circle' : 'alert-circle'}
                    size={16}
                    iconColor={lookupMsg.type === 'success' ? '#16a34a' : lookupMsg.type === 'warning' ? '#d97706' : Colors.danger}
                    style={{ margin: 0 }}
                  />
                  <Text style={[lookupStyles.fbTxt,
                    lookupMsg.type === 'success' && { color: '#15803d' },
                    lookupMsg.type === 'warning' && { color: '#92400e' },
                    lookupMsg.type === 'error'   && { color: Colors.danger },
                  ]}>{lookupMsg.text}</Text>
                </View>
              )}

              <TextInput
                label="Nombres *"
                value={nombres}
                onChangeText={(t) => { setNombres(t); setError(''); }}
                mode="outlined"
                autoCapitalize="words"
                editable={!lookupLocked}
                style={[styledInput(), lookupLocked && { backgroundColor: '#f0fdf4' }]}
                theme={lookupLocked
                  ? { ...inputTheme, colors: { ...inputTheme.colors, primary: '#16a34a', onSurfaceVariant: '#16a34a' } }
                  : inputTheme}
                left={<TextInput.Icon icon="account-outline" />}
                right={lookupLocked ? <TextInput.Icon icon="lock" iconColor="#16a34a" /> : undefined}
              />
              <View style={styles.row}>
                <TextInput
                  label="Ap. Paterno *"
                  value={apellidoPaterno}
                  onChangeText={(t) => { setApellidoPaterno(t); setError(''); }}
                  mode="outlined"
                  autoCapitalize="words"
                  editable={!lookupLocked}
                  style={[styledInput(), styles.flex1, lookupLocked && { backgroundColor: '#f0fdf4' }]}
                  theme={lookupLocked
                    ? { ...inputTheme, colors: { ...inputTheme.colors, primary: '#16a34a', onSurfaceVariant: '#16a34a' } }
                    : inputTheme}
                />
                <TextInput
                  label="Ap. Materno"
                  value={apellidoMaterno}
                  onChangeText={(t) => { setApellidoMaterno(t); setError(''); }}
                  mode="outlined"
                  autoCapitalize="words"
                  editable={!lookupLocked}
                  style={[styledInput(), styles.flex1, lookupLocked && { backgroundColor: '#f0fdf4' }]}
                  theme={lookupLocked
                    ? { ...inputTheme, colors: { ...inputTheme.colors, primary: '#16a34a', onSurfaceVariant: '#16a34a' } }
                    : inputTheme}
                />
              </View>
            </>
          ) : (
            <>
              {/* Campo RUC + botón búsqueda SUNAT */}
              <View style={lookupStyles.row}>
                <TextInput
                  label="RUC *"
                  value={ruc}
                  onChangeText={handleRucChange}
                  mode="outlined"
                  keyboardType="numeric"
                  maxLength={11}
                  style={[styledInput(), { flex: 1, marginBottom: 0 }]}
                  theme={inputTheme}
                  left={<TextInput.Icon icon="barcode" />}
                />
                <TouchableOpacity
                  onPress={handleLookup}
                  disabled={lookupLoading}
                  style={[lookupStyles.btn, lookupLoading && lookupStyles.btnDisabled]}
                  activeOpacity={0.8}
                >
                  {lookupLoading
                    ? <ActivityIndicator size={18} color="#fff" />
                    : <IconButton icon="magnify" size={18} iconColor="#fff" style={{ margin: 0 }} />
                  }
                  <Text style={lookupStyles.btnTxt}>SUNAT</Text>
                </TouchableOpacity>
              </View>

              {/* Feedback lookup */}
              {lookupMsg && (
                <View style={[lookupStyles.feedback,
                  lookupMsg.type === 'success' && lookupStyles.fbSuccess,
                  lookupMsg.type === 'warning' && lookupStyles.fbWarning,
                  lookupMsg.type === 'error'   && lookupStyles.fbError,
                ]}>
                  <IconButton
                    icon={lookupMsg.type === 'success' ? 'check-circle' : 'alert-circle'}
                    size={16}
                    iconColor={lookupMsg.type === 'success' ? '#16a34a' : lookupMsg.type === 'warning' ? '#d97706' : Colors.danger}
                    style={{ margin: 0 }}
                  />
                  <Text style={[lookupStyles.fbTxt,
                    lookupMsg.type === 'success' && { color: '#15803d' },
                    lookupMsg.type === 'warning' && { color: '#92400e' },
                    lookupMsg.type === 'error'   && { color: Colors.danger },
                  ]}>{lookupMsg.text}</Text>
                </View>
              )}

              <TextInput
                label="Razón Social *"
                value={razonSocial}
                onChangeText={(t) => { setRazonSocial(t); setError(''); }}
                mode="outlined"
                autoCapitalize="words"
                editable={!lookupLocked}
                style={[styledInput(), lookupLocked && { backgroundColor: '#f0fdf4' }]}
                theme={lookupLocked
                  ? { ...inputTheme, colors: { ...inputTheme.colors, primary: '#16a34a', onSurfaceVariant: '#16a34a' } }
                  : inputTheme}
                left={<TextInput.Icon icon="domain" />}
                right={lookupLocked ? <TextInput.Icon icon="lock" iconColor="#16a34a" /> : undefined}
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
              <>
                <ActivityIndicator size={18} color="#fff" style={{ marginRight: 8 }} />
                <Text style={styles.submitTxt}>Procesando...</Text>
              </>
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

      {/* ── Processing overlay (se muestra encima de todo) ── */}
      <RegistrationProcessingOverlay visible={showProcessing} />

      {/* ── Success modal ── */}
      <RegistrationSuccessModal
        visible={showSuccess}
        docLabel={tipoPersona === 'Jurídica' ? 'RUC' : tipoDocumento}
        onContinue={() => {
          setShowSuccess(false);
          navigation.reset({ index: 0, routes: [{ name: 'Login' }] });
        }}
      />

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
  searchBox: {
    flexDirection: 'row',
    alignItems: 'center',
    marginHorizontal: 0,
    marginBottom: 8,
    backgroundColor: '#f4f4f5',
    borderRadius: 10,
    paddingHorizontal: 4,
  },
  searchInput: {
    flex: 1,
    fontSize: 14,
    color: Colors.textDark,
    paddingVertical: 8,
  },
  emptyBox: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 32,
  },
  emptyText: {
    color: Colors.textLight,
    fontSize: 14,
  },
  item: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderBottomWidth: 1,
    borderBottomColor: Colors.divider,
    backgroundColor: Colors.surface,
    gap: 4,
  },
  itemSelected: {
    backgroundColor: '#f0fdf4',
    borderLeftWidth: 3,
    borderLeftColor: Colors.primary,
  },
  itemText: { flex: 1, fontSize: 14, color: Colors.textDark, fontWeight: '500' },
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

// ── Lookup styles ──────────────────────────────────────────────────────────
const lookupStyles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 10,
  },
  btn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.primary,
    borderRadius: 12,
    paddingHorizontal: 10,
    paddingVertical: 8,
    gap: 2,
    alignSelf: 'center',
    marginTop: 4,
  },
  btnDisabled: { opacity: 0.6 },
  btnTxt: { color: '#fff', fontSize: 11, fontWeight: '800', letterSpacing: 0.5 },
  feedback: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    borderRadius: 10,
    borderWidth: 1,
    paddingHorizontal: 10,
    paddingVertical: 8,
    marginBottom: 10,
    gap: 6,
  },
  fbSuccess: { backgroundColor: '#f0fdf4', borderColor: '#86efac' },
  fbWarning: { backgroundColor: '#fffbeb', borderColor: '#fcd34d' },
  fbError:   { backgroundColor: '#fef2f2', borderColor: '#fecaca' },
  fbTxt: { flex: 1, fontSize: 12, lineHeight: 17 },
});
