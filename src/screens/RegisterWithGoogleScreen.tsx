/**
 * RegisterWithGoogleScreen
 * Completa el registro de un usuario que se autenticó con Google.
 * Google ya proveyó: nombre + email.
 * El usuario solo necesita ingresar: tipo doc, número doc, teléfono.
 */
import React, { useState } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, Platform,
  ScrollView, TextInput, KeyboardAvoidingView, Modal, Alert,
  ActivityIndicator,
} from 'react-native';
import { BlurView } from 'expo-blur';
import { Ionicons, FontAwesome } from '@expo/vector-icons';
import { useNavigation, useRoute } from '@react-navigation/native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { authApi } from '../api/auth';
import { useAuth } from '../contexts/AuthContext';

const DOC_MAX: Record<string, number> = { DNI: 8, CE: 9, RUC: 11 };

export const RegisterWithGoogleScreen: React.FC = () => {
  const navigation = useNavigation<any>();
  const route = useRoute();
  const insets = useSafeAreaInsets();
  const { loginWithGoogle } = useAuth();

  const params = (route.params as any) || {};
  const googleEmail: string = params.google_email || '';
  const googleName:  string = params.google_name  || '';

  // Derivar nombre / apellidos desde el nombre de Google
  const nameParts = googleName.trim().split(' ');
  const defaultNombres = nameParts[0] || '';
  const defaultApellido = nameParts.slice(1).join(' ') || '';

  const [tipoDoc, setTipoDoc]               = useState<'DNI' | 'CE' | 'RUC'>('DNI');
  const [showTipoPicker, setShowTipoPicker] = useState(false);
  const [numDoc, setNumDoc]                 = useState('');
  const [telefono, setTelefono]             = useState('');
  const [nombres, setNombres]               = useState(defaultNombres);
  const [apellidoPaterno, setApellidoPaterno] = useState(defaultApellido);
  const [razonSocial, setRazonSocial]       = useState('');
  const [personaContacto, setPersonaContacto] = useState(googleName);
  const [error, setError]                   = useState('');
  const [loading, setLoading]               = useState(false);
  const [acceptTerms, setAcceptTerms]       = useState(false);

  const tiposDocList: Array<'DNI' | 'CE' | 'RUC'> = ['DNI', 'CE', 'RUC'];
  const isNatural = tipoDoc !== 'RUC';

  const handleRegistrar = async () => {
    setError('');

    if (!numDoc || numDoc.length !== DOC_MAX[tipoDoc]) {
      setError(`Ingresa los ${DOC_MAX[tipoDoc]} dígitos del ${tipoDoc}`); return;
    }
    if (!telefono || telefono.length < 7) {
      setError('Ingresa un número de teléfono válido'); return;
    }
    if (isNatural && (!nombres.trim() || !apellidoPaterno.trim())) {
      setError('Ingresa tu nombre y apellido'); return;
    }
    if (!isNatural && !razonSocial.trim()) {
      setError('Ingresa la razón social de la empresa'); return;
    }
    if (!acceptTerms) {
      setError('Acepta los Términos y Condiciones'); return;
    }

    try {
      setLoading(true);

      // Generar contraseña aleatoria segura (el usuario siempre ingresará via Google)
      const randomPassword = Math.random().toString(36).slice(-8) + Math.random().toString(36).slice(-8).toUpperCase() + '!1';

      let registerData: any;

      if (isNatural) {
        registerData = {
          tipo_persona: 'Natural',
          tipo_documento: tipoDoc,
          dni: numDoc,
          nombres: nombres.trim().toUpperCase(),
          apellido_paterno: apellidoPaterno.trim().toUpperCase(),
          email: googleEmail,
          telefono: telefono.trim(),
          password: randomPassword,
          registration_via: 'google',
        };
      } else {
        registerData = {
          tipo_persona: 'Jurídica',
          tipo_documento: 'RUC',
          ruc: numDoc,
          dni: numDoc,
          razon_social: razonSocial.trim().toUpperCase(),
          persona_contacto: personaContacto.trim().toUpperCase(),
          email: googleEmail,
          telefono: telefono.trim(),
          password: randomPassword,
          registration_via: 'google',
        };
      }

      const response = await authApi.register(registerData);

      if (response.success) {
        Alert.alert(
          '¡Cuenta creada!',
          'Tu cuenta fue registrada con Google. Un asesor validará tu identidad pronto.',
          [{ text: 'Entendido', onPress: () => navigation.navigate('PublicCalculator') }]
        );
      }
    } catch (err: any) {
      setError(err.message || 'Error al registrar. Intenta de nuevo.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={s.root}>
      {/* Botón volver */}
      <TouchableOpacity
        style={[s.backBtn, { top: insets.top + 16 }]}
        onPress={() => navigation.goBack()}
        activeOpacity={0.8}
      >
        <Ionicons name="chevron-back" size={22} color="#ffffff" />
      </TouchableOpacity>

      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView
          contentContainerStyle={[s.scroll, { paddingTop: insets.top + 60 }]}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          {/* Título */}
          <View style={s.googleBadge}>
            <FontAwesome name="google" size={16} color="#fff" />
            <Text style={s.googleBadgeText}>Registrado con Google</Text>
          </View>

          <Text style={s.title}>
            {'Completa tu '}
            <Text style={s.titleGreen}>registro</Text>
          </Text>
          <Text style={s.subtitle}>Solo necesitamos unos datos más</Text>

          {/* Card */}
          <BlurView intensity={40} tint="dark" style={s.card}>

            {/* Email pre-llenado (solo lectura) */}
            <View style={[s.inputBox, s.inputReadOnly]}>
              <Text style={s.inputLabel}>Email (Google)</Text>
              <View style={s.readOnlyRow}>
                <Ionicons name="checkmark-circle" size={14} color="#22c55e" style={{ marginRight: 6 }} />
                <Text style={s.inputValueMuted}>{googleEmail}</Text>
              </View>
            </View>

            {/* Tipo de documento + Número */}
            <View style={s.fieldRow}>
              {/* Tipo */}
              <TouchableOpacity
                style={[s.inputBox, s.tipoBox]}
                onPress={() => setShowTipoPicker(true)}
                activeOpacity={0.8}
              >
                <Text style={s.inputLabel}>Tipo</Text>
                <View style={s.tipoInner}>
                  <Text style={s.inputValue}>{tipoDoc}</Text>
                  <Ionicons name={showTipoPicker ? 'chevron-up' : 'chevron-down'} size={14} color="rgba(255,255,255,0.5)" />
                </View>
              </TouchableOpacity>

              {/* Número de documento */}
              <View style={[s.inputBox, s.numBox]}>
                <Text style={s.inputLabel}>Número de documento</Text>
                <TextInput
                  style={s.inputValue}
                  value={numDoc}
                  onChangeText={t => setNumDoc(t.replace(/\D/g, '').slice(0, DOC_MAX[tipoDoc]))}
                  keyboardType="numeric"
                  maxLength={DOC_MAX[tipoDoc]}
                  placeholderTextColor="rgba(255,255,255,0.2)"
                  selectionColor="#22c55e"
                />
              </View>
            </View>

            {/* Tipo Picker Modal */}
            <Modal visible={showTipoPicker} transparent animationType="fade" onRequestClose={() => setShowTipoPicker(false)}>
              <TouchableOpacity style={s.modalOverlay} activeOpacity={1} onPress={() => setShowTipoPicker(false)}>
                <View style={s.tipoPickerModal}>
                  {tiposDocList.map(t => (
                    <TouchableOpacity
                      key={t}
                      style={[s.tipoOption, tipoDoc === t && s.tipoOptionSelected]}
                      onPress={() => { setTipoDoc(t); setNumDoc(''); setShowTipoPicker(false); }}
                    >
                      <Text style={[s.tipoOptionText, tipoDoc === t && s.tipoOptionActive]}>{t}</Text>
                      {tipoDoc === t && <Ionicons name="checkmark" size={14} color="#22c55e" />}
                    </TouchableOpacity>
                  ))}
                </View>
              </TouchableOpacity>
            </Modal>

            {/* Campos según tipo de persona */}
            {isNatural ? (
              <>
                <View style={s.inputBox}>
                  <Text style={s.inputLabel}>Nombres</Text>
                  <TextInput
                    style={s.inputValue}
                    value={nombres}
                    onChangeText={setNombres}
                    autoCapitalize="words"
                    placeholderTextColor="rgba(255,255,255,0.2)"
                    selectionColor="#22c55e"
                  />
                </View>
                <View style={s.inputBox}>
                  <Text style={s.inputLabel}>Apellido paterno</Text>
                  <TextInput
                    style={s.inputValue}
                    value={apellidoPaterno}
                    onChangeText={setApellidoPaterno}
                    autoCapitalize="words"
                    placeholderTextColor="rgba(255,255,255,0.2)"
                    selectionColor="#22c55e"
                  />
                </View>
              </>
            ) : (
              <>
                <View style={s.inputBox}>
                  <Text style={s.inputLabel}>Razón social</Text>
                  <TextInput
                    style={s.inputValue}
                    value={razonSocial}
                    onChangeText={setRazonSocial}
                    autoCapitalize="characters"
                    placeholderTextColor="rgba(255,255,255,0.2)"
                    selectionColor="#22c55e"
                  />
                </View>
                <View style={s.inputBox}>
                  <Text style={s.inputLabel}>Persona de contacto</Text>
                  <TextInput
                    style={s.inputValue}
                    value={personaContacto}
                    onChangeText={setPersonaContacto}
                    autoCapitalize="words"
                    placeholderTextColor="rgba(255,255,255,0.2)"
                    selectionColor="#22c55e"
                  />
                </View>
              </>
            )}

            {/* Teléfono */}
            <View style={s.inputBox}>
              <Text style={s.inputLabel}>Teléfono / Celular</Text>
              <TextInput
                style={s.inputValue}
                value={telefono}
                onChangeText={t => setTelefono(t.replace(/\D/g, '').slice(0, 15))}
                keyboardType="phone-pad"
                placeholderTextColor="rgba(255,255,255,0.2)"
                selectionColor="#22c55e"
              />
            </View>

            {/* Términos */}
            <TouchableOpacity style={s.checkRow} onPress={() => setAcceptTerms(v => !v)} activeOpacity={0.8}>
              <View style={[s.checkbox, acceptTerms && s.checkboxActive]}>
                {acceptTerms && <Ionicons name="checkmark" size={11} color="#fff" />}
              </View>
              <Text style={s.checkText}>
                {'Acepto los '}
                <Text style={s.greenLink}>Términos y Condiciones</Text>
                {' y la '}
                <Text style={s.greenLink}>Política de Privacidad</Text>
              </Text>
            </TouchableOpacity>

            {/* Error */}
            {!!error && <Text style={s.errorText}>{error}</Text>}

            {/* Separador */}
            <View style={s.separator} />

            {/* Botón registrar */}
            <TouchableOpacity style={s.continueBtn} onPress={handleRegistrar} activeOpacity={0.75} disabled={loading}>
              {loading
                ? <ActivityIndicator color="#0a1a2e" />
                : <Text style={s.continueBtnText}>Crear cuenta</Text>
              }
            </TouchableOpacity>
          </BlurView>

          <Text style={s.disclaimer}>
            Tu cuenta iniciará en proceso de verificación. Un asesor QoriCash la activará pronto.
          </Text>
        </ScrollView>
      </KeyboardAvoidingView>
    </View>
  );
};

export default RegisterWithGoogleScreen;

const s = StyleSheet.create({
  root:  { flex: 1, backgroundColor: 'transparent' },

  backBtn: {
    position: 'absolute',
    left: 20,
    zIndex: 10,
    padding: 4,
  },

  scroll: {
    flexGrow: 1,
    justifyContent: 'center',
    paddingHorizontal: 20,
    paddingBottom: 40,
  },

  googleBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'center',
    backgroundColor: 'rgba(255,255,255,0.15)',
    borderRadius: 20,
    paddingHorizontal: 14,
    paddingVertical: 6,
    gap: 8,
    marginBottom: 16,
  },
  googleBadgeText: {
    color: '#fff',
    fontSize: 13,
    fontWeight: '600',
  },

  title: {
    fontSize: 28,
    fontWeight: '800',
    color: '#ffffff',
    textAlign: 'center',
    marginBottom: 6,
  },
  titleGreen: { color: '#22c55e' },
  subtitle: {
    fontSize: 14,
    color: 'rgba(255,255,255,0.7)',
    textAlign: 'center',
    marginBottom: 20,
  },

  card: {
    borderRadius: 18,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.18)',
    paddingTop: 20,
  },

  fieldRow: {
    flexDirection: 'row',
    gap: 10,
    paddingHorizontal: 16,
    marginBottom: 12,
  },
  inputBox: {
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.25)',
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingTop: 8,
    paddingBottom: 10,
    marginBottom: 12,
    marginHorizontal: 16,
  },
  inputReadOnly: {
    borderColor: 'rgba(34,197,94,0.3)',
    backgroundColor: 'rgba(34,197,94,0.06)',
  },
  tipoBox: {
    flex: 0,
    width: 100,
    marginHorizontal: 0,
    marginBottom: 0,
  },
  numBox: {
    flex: 1,
    marginHorizontal: 0,
    marginBottom: 0,
  },
  inputLabel: {
    fontSize: 10,
    color: 'rgba(255,255,255,0.55)',
    fontWeight: '600',
    marginBottom: 4,
    letterSpacing: 0.2,
  },
  inputValue: {
    fontSize: 15,
    color: '#ffffff',
    fontWeight: '500',
    padding: 0,
  },
  inputValueMuted: {
    fontSize: 14,
    color: 'rgba(255,255,255,0.75)',
    fontWeight: '500',
  },
  readOnlyRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },

  tipoInner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.55)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  tipoPickerModal: {
    backgroundColor: '#1a2a3a',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.2)',
    overflow: 'hidden',
    minWidth: 160,
  },
  tipoOption: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 14,
    paddingHorizontal: 20,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255,255,255,0.08)',
  },
  tipoOptionSelected: { backgroundColor: 'rgba(34,197,94,0.1)' },
  tipoOptionText: {
    fontSize: 15,
    color: 'rgba(255,255,255,0.85)',
    fontWeight: '500',
  },
  tipoOptionActive: { color: '#22c55e', fontWeight: '700' },

  checkRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    paddingHorizontal: 16,
    marginBottom: 12,
    gap: 10,
  },
  checkbox: {
    width: 18,
    height: 18,
    borderRadius: 3,
    borderWidth: 1.5,
    borderColor: 'rgba(255,255,255,0.4)',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 1,
  },
  checkboxActive: { backgroundColor: '#22c55e', borderColor: '#22c55e' },
  checkText: {
    flex: 1,
    fontSize: 13,
    color: 'rgba(255,255,255,0.8)',
    lineHeight: 19,
  },
  greenLink: { color: '#22c55e', fontWeight: '600' },

  errorText: {
    fontSize: 12,
    color: '#f87171',
    textAlign: 'center',
    marginHorizontal: 16,
    marginBottom: 8,
  },

  separator: {
    height: 1,
    backgroundColor: 'rgba(255,255,255,0.12)',
    marginTop: 4,
  },
  continueBtn: {
    paddingVertical: 18,
    alignItems: 'center',
  },
  continueBtnText: {
    fontSize: 16,
    fontWeight: '700',
    color: '#0a1a2e',
    letterSpacing: 0.3,
  },

  disclaimer: {
    fontSize: 11,
    color: 'rgba(255,255,255,0.45)',
    textAlign: 'center',
    marginTop: 16,
    lineHeight: 16,
    paddingHorizontal: 8,
  },
});
