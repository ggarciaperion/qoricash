/**
 * RegisterScreen — replica fiel de aaaa.png
 */
import React, { useState } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, Platform,
  ScrollView, TextInput, KeyboardAvoidingView, Modal,
} from 'react-native';
import { BlurView } from 'expo-blur';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation, useRoute } from '@react-navigation/native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

const DOC_MAX: Record<string, number> = { DNI: 8, CE: 9, RUC: 11 };

export const RegisterScreen: React.FC = () => {
  const navigation = useNavigation<any>();
  const route = useRoute();
  const insets = useSafeAreaInsets();
  const params = (route.params as any) || {};
  const tipoPersona: 'Natural' | 'Jurídica' = params.tipoPersona || 'Natural';
  const isNatural = tipoPersona === 'Natural';

  const [paso, setPaso] = useState(1);

  // Paso 1
  const [tipoDoc, setTipoDoc]           = useState(isNatural ? 'DNI' : 'RUC');
  const [showTipoPicker, setShowTipoPicker] = useState(false);
  const [numDoc, setNumDoc]             = useState('');
  const [email, setEmail]               = useState('');
  const [password, setPassword]         = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [acceptTerms, setAcceptTerms]   = useState(false);
  const [notRobot, setNotRobot]         = useState(false);
  const [error, setError]               = useState('');

  const tiposDocList = isNatural ? ['DNI', 'CE'] : ['RUC'];

  const steps = [
    { num: 1, label: 'Identidad' },
    { num: 2, label: 'Contacto' },
    { num: 3, label: 'Verificación' },
  ];

  const handleContinuar = () => {
    setError('');
    if (!numDoc || numDoc.length !== DOC_MAX[tipoDoc]) {
      setError(`Ingresa los ${DOC_MAX[tipoDoc]} dígitos del ${tipoDoc}`); return;
    }
    if (!email || !/^[^@]+@[^@]+\.[^@]+$/.test(email)) {
      setError('Ingresa un correo electrónico válido'); return;
    }
    if (password.length < 8) {
      setError('La contraseña debe tener al menos 8 caracteres'); return;
    }
    if (!acceptTerms) {
      setError('Acepta los Términos y Condiciones'); return;
    }
    if (!notRobot) {
      setError('Confirma que no eres un robot'); return;
    }
    setPaso(2);
  };

  return (
    <View style={s.root}>
      {/* Botón volver — posición unificada con todas las pantallas auth */}
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
          <Text style={s.title}>
            {'Crear cuenta '}
            <Text style={s.titleGreen}>
              {isNatural ? 'Persona\nNatural' : 'Empresa'}
            </Text>
          </Text>
          <Text style={s.subtitle}>Únete a QoriCash en 3 simples pasos</Text>

          {/* Steps */}
          <View style={s.stepsRow}>
            {steps.map((step, idx) => (
              <React.Fragment key={step.num}>
                <View style={s.stepItem}>
                  <View style={[s.stepCircle, paso >= step.num && s.stepCircleActive]}>
                    <Text style={[s.stepNum, paso >= step.num && s.stepNumActive]}>
                      {step.num}
                    </Text>
                  </View>
                  <Text style={[s.stepLabel, paso === step.num && s.stepLabelActive]}>
                    {step.label}
                  </Text>
                </View>
                {idx < steps.length - 1 && (
                  <View style={[s.stepLine, paso > step.num && s.stepLineActive]} />
                )}
              </React.Fragment>
            ))}
          </View>

          {/* Card */}
          <BlurView intensity={40} tint="dark" style={s.card}>

            {/* Fila: Tipo + Número de documento */}
            <View style={s.fieldRow}>

              {/* Tipo */}
              <TouchableOpacity
                style={[s.inputBox, s.tipoBox, !isNatural && s.tipoBoxFixed]}
                onPress={() => isNatural && setShowTipoPicker(true)}
                activeOpacity={isNatural ? 0.8 : 1}
              >
                <Text style={s.inputLabel}>Tipo</Text>
                <View style={s.tipoInner}>
                  <Text style={s.inputValue}>{tipoDoc}</Text>
                  {isNatural && (
                    <Ionicons
                      name={showTipoPicker ? 'chevron-up' : 'chevron-down'}
                      size={14}
                      color="rgba(255,255,255,0.5)"
                    />
                  )}
                </View>
              </TouchableOpacity>

              {/* Tipo Picker Modal */}
              <Modal
                visible={showTipoPicker}
                transparent
                animationType="fade"
                onRequestClose={() => setShowTipoPicker(false)}
              >
                <TouchableOpacity
                  style={s.modalOverlay}
                  activeOpacity={1}
                  onPress={() => setShowTipoPicker(false)}
                >
                  <View style={s.tipoPickerModal}>
                    {tiposDocList.map(t => (
                      <TouchableOpacity
                        key={t}
                        style={[s.tipoOption, tipoDoc === t && s.tipoOptionSelected]}
                        onPress={() => { setTipoDoc(t); setNumDoc(''); setShowTipoPicker(false); }}
                      >
                        <Text style={[s.tipoOptionText, tipoDoc === t && s.tipoOptionActive]}>
                          {t}
                        </Text>
                        {tipoDoc === t && (
                          <Ionicons name="checkmark" size={14} color="#22c55e" />
                        )}
                      </TouchableOpacity>
                    ))}
                  </View>
                </TouchableOpacity>
              </Modal>

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

            {/* Correo electrónico */}
            <View style={s.inputBox}>
              <Text style={s.inputLabel}>Correo electrónico</Text>
              <TextInput
                style={s.inputValue}
                value={email}
                onChangeText={setEmail}
                keyboardType="email-address"
                autoCapitalize="none"
                placeholderTextColor="rgba(255,255,255,0.2)"
                selectionColor="#22c55e"
              />
            </View>

            {/* Contraseña */}
            <View style={s.inputBox}>
              <Text style={s.inputLabel}>Contraseña</Text>
              <View style={s.passwordRow}>
                <TextInput
                  style={[s.inputValue, { flex: 1 }]}
                  value={password}
                  onChangeText={setPassword}
                  secureTextEntry={!showPassword}
                  autoCapitalize="none"
                  placeholderTextColor="rgba(255,255,255,0.2)"
                  selectionColor="#22c55e"
                />
                <TouchableOpacity onPress={() => setShowPassword(v => !v)} style={s.eyeBtn}>
                  <Ionicons
                    name={showPassword ? 'eye-off-outline' : 'eye-outline'}
                    size={20}
                    color="rgba(255,255,255,0.5)"
                  />
                </TouchableOpacity>
              </View>
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

            {/* reCAPTCHA */}
            <TouchableOpacity style={s.captchaBox} onPress={() => setNotRobot(v => !v)} activeOpacity={0.8}>
              <View style={[s.checkbox, notRobot && s.checkboxActive]}>
                {notRobot && <Ionicons name="checkmark" size={11} color="#fff" />}
              </View>
              <Text style={s.captchaText}>No soy un robot</Text>
              <View style={s.captchaLogoWrap}>
                <Ionicons name="shield-checkmark" size={22} color="#22c55e" />
                <Text style={s.captchaLogoText}>reCAPTCHA</Text>
              </View>
            </TouchableOpacity>

            {/* Error */}
            {!!error && (
              <Text style={s.errorText}>{error}</Text>
            )}

            {/* Separador */}
            <View style={s.separator} />

            {/* Continuar */}
            <TouchableOpacity style={s.continueBtn} onPress={handleContinuar} activeOpacity={0.75}>
              <Text style={s.continueBtnText}>Continuar</Text>
            </TouchableOpacity>

          </BlurView>

        </ScrollView>
      </KeyboardAvoidingView>
    </View>
  );
};

export default RegisterScreen;

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: 'transparent' },

  scroll: {
    flexGrow: 1,
    justifyContent: 'center',
    paddingHorizontal: 20,
    paddingBottom: 40,
  },

  // Volver
  backBtn: {
    position: 'absolute',
    left: 20,
    zIndex: 10,
    padding: 4,
  },

  // Título
  title: {
    fontSize: 30,
    fontWeight: '800',
    color: '#ffffff',
    textAlign: 'center',
    marginBottom: 8,
    lineHeight: 36,
  },
  titleGreen: {
    color: '#22c55e',
  },
  subtitle: {
    fontSize: 14,
    color: 'rgba(255,255,255,0.8)',
    textAlign: 'center',
    marginBottom: 24,
  },

  // Steps
  stepsRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'center',
    marginBottom: 20,
    paddingHorizontal: 8,
  },
  stepItem: {
    alignItems: 'center',
  },
  stepCircle: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: 'rgba(255,255,255,0.2)',
    borderWidth: 1.5,
    borderColor: 'rgba(255,255,255,0.3)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepCircleActive: {
    backgroundColor: '#22c55e',
    borderColor: '#22c55e',
  },
  stepNum: {
    fontSize: 14,
    fontWeight: '700',
    color: 'rgba(255,255,255,0.5)',
  },
  stepNumActive: {
    color: '#ffffff',
  },
  stepLabel: {
    fontSize: 11,
    color: 'rgba(255,255,255,0.45)',
    fontWeight: '600',
    marginTop: 5,
  },
  stepLabelActive: {
    color: '#22c55e',
  },
  stepLine: {
    flex: 1,
    height: 1.5,
    backgroundColor: 'rgba(255,255,255,0.2)',
    marginTop: 17,
    marginHorizontal: 6,
  },
  stepLineActive: {
    backgroundColor: '#22c55e',
  },

  // Card
  card: {
    borderRadius: 18,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.18)',
    paddingTop: 20,
  },

  // Inputs
  fieldRow: {
    flexDirection: 'row',
    gap: 10,
    paddingHorizontal: 16,
    marginBottom: 20,
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
  tipoBox: {
    flex: 0,
    width: 100,
    marginHorizontal: 0,
    marginBottom: 0,
  },
  tipoBoxFixed: {
    opacity: 0.5,
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

  // Tipo dropdown
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
  tipoOptionSelected: {
    backgroundColor: 'rgba(34,197,94,0.1)',
  },
  tipoOptionText: {
    fontSize: 15,
    color: 'rgba(255,255,255,0.85)',
    fontWeight: '500',
  },
  tipoOptionActive: {
    color: '#22c55e',
    fontWeight: '700',
  },

  // Password
  passwordRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  eyeBtn: {
    padding: 4,
  },

  // Checkbox
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
  checkboxActive: {
    backgroundColor: '#22c55e',
    borderColor: '#22c55e',
  },
  checkText: {
    flex: 1,
    fontSize: 13,
    color: 'rgba(255,255,255,0.8)',
    lineHeight: 19,
  },
  greenLink: {
    color: '#22c55e',
    fontWeight: '600',
  },

  // reCAPTCHA
  captchaBox: {
    flexDirection: 'row',
    alignItems: 'center',
    marginHorizontal: 16,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.2)',
    borderRadius: 10,
    paddingVertical: 14,
    paddingHorizontal: 14,
    gap: 12,
  },
  captchaText: {
    flex: 1,
    fontSize: 14,
    color: 'rgba(255,255,255,0.85)',
    fontWeight: '500',
  },
  captchaLogoWrap: {
    alignItems: 'center',
  },
  captchaLogoText: {
    fontSize: 8,
    color: '#22c55e',
    fontWeight: '700',
    letterSpacing: 0.5,
    marginTop: 2,
  },

  // Error
  errorText: {
    fontSize: 12,
    color: '#f87171',
    textAlign: 'center',
    marginHorizontal: 16,
    marginBottom: 8,
  },

  // Separador + botón
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
    color: '#ffffff',
    letterSpacing: 0.3,
  },
});
