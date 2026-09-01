/**
 * RegisterScreen — replica fiel de aaaa.png
 */
import React, { useState, useRef } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, Platform,
  ScrollView, TextInput, KeyboardAvoidingView, Modal, ActivityIndicator,
  Animated, Easing, Image,
} from 'react-native';
import { BlurView } from 'expo-blur';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation, useRoute } from '@react-navigation/native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { authApi } from '../api/auth';
import { API_CONFIG } from '../constants/config';
import { Audio } from 'expo-av';

const DOC_MAX: Record<string, number> = { DNI: 8, CE: 9, RUC: 11 };

// ── Email validation ──────────────────────────────────────────────────────
const DISPOSABLE_DOMAINS = new Set([
  'yopmail.com','yopmail.fr','yopmail.pp.ua','mailinator.com','mailinator.net',
  'mailinator.org','guerrillamail.com','guerrillamail.net','guerrillamail.org',
  'guerrillamail.de','guerrillamail.biz','guerrillamail.info','guerrillamailblock.com',
  'grr.la','tempmail.com','temp-mail.org','tempmail.de','tempr.email','tempail.com',
  'tempalias.com','temporaryemail.net','temporaryinbox.com','temporaryforwarding.com',
  'throwam.com','throwaway.email','10minutemail.com','10minutemail.net','10minutemail.org',
  '20minutemail.com','30minutemail.com','mytrashmail.com',
  'trashmail.com','trashmail.me','trashmail.net','trashmail.at','trashmail.io',
  'trashmail.org','trashmail.de','trashmail.app','trashmail.gl','trashmail.ws',
  'trashmail.es','trashmail.fr','trashdevil.com','trashdevil.de','trashmailgenerator.com',
  'maildrop.cc','mailnull.com','mailnew.com','mailnesia.com','maileater.com',
  'mailexpire.com','mailme.ir','mailme24.com','mailmoat.com','mailslapping.com',
  'dispostable.com','discard.email','fakeinbox.com','sharklasers.com','spam4.me',
  'spamgourmet.com','spamgourmet.net','spamgourmet.org','spambox.us','spam.la',
  'spaml.de','spamfree24.org','spamfree24.de','spamgoes.in','spamstack.net',
  'spamwc.de','spamhereplease.com','spamcorptastic.com','spamoff.de',
  'mintemail.com','meltmail.com','mt2009.com','mt2014.com','rcpt.at',
  'sogetthis.com','getonemail.com','nowmymail.com','inboxclean.com',
  'filzmail.com','antichef.com','byom.de','rklips.com','pookmail.com',
  'lookugly.com','marud.com','tafmail.com','tinoza.org','tittbit.in',
  'owlpic.com','stuffmail.de','webemail.me','wolfsmail.tk','woomail.ovh',
  'zehnminuten.de','zehnminutenmail.de','zippymail.info','weg-werf-email.de',
  'wegwerfemail.com','wegwerfemail.de','xcpy.com','trbvm.com','tyldd.com',
  'venompen.com','uggsrock.com','gowikibooks.com','gowikicampus.com',
  'hailmail.net','klassmaster.com','jetable.fr.nf','jetable.net','jetable.org',
  'noclickemail.com','nobulk.com','nospamfor.us','nospammail.net',
  'oneoffemail.com','one-time.email','privy-mail.com','privy-mail.de',
  'selfdestructingmail.com','sendspamhere.com','shiftmail.com',
  'spamtroll.net','trillianpro.com','trungtamtuvan.com',
  'walala.org','walkmail.net','wilemail.com','xagloo.com','xcode.ro',
  'yoru-dea.com','you-spam.com','ypmail.webarnak.fr.eu.org',
]);

// Typos comunes en el TLD
const TYPO_TLDS: Record<string, string> = {
  con: 'com', cim: 'com', cpm: 'com', cmo: 'com', cob: 'com',
  ocm: 'com', como: 'com', coml: 'com', comm: 'com', comn: 'com',
  ney: 'net', nte: 'net', rog: 'org', ogr: 'org',
};

const validateEmail = (raw: string): string | null => {
  const email = raw.trim().toLowerCase();
  if (!email) return 'Ingresa tu correo electrónico';

  // Formato básico: localpart@domain.tld
  if (!/^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$/.test(email))
    return 'Ingresa un correo electrónico válido';

  // Puntos consecutivos
  if (/\.{2,}/.test(email))
    return 'El correo no puede contener puntos consecutivos';

  // Detectar typo en TLD
  const tld = email.split('.').pop()!;
  if (TYPO_TLDS[tld])
    return `¿Quisiste escribir .${TYPO_TLDS[tld]}? Revisa tu correo`;

  // Dominio desechable
  const domain = email.split('@')[1];
  if (DISPOSABLE_DOMAINS.has(domain))
    return 'No se permiten correos temporales o desechables';

  return null;
};

export const RegisterScreen: React.FC = () => {
  const navigation = useNavigation<any>();
  const route = useRoute();
  const insets = useSafeAreaInsets();
  const params = (route.params as any) || {};
  const tipoPersona: 'Natural' | 'Jurídica' = params.tipoPersona || 'Natural';
  const isNatural = tipoPersona === 'Natural';

  const [paso, setPaso]               = useState(1);
  const [displayedPaso, setDisplayedPaso] = useState(1);
  const [loading, setLoading]         = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);

  // Animación de transición entre pasos
  const slideAnim = useRef(new Animated.Value(0)).current;
  const fadeAnim  = useRef(new Animated.Value(1)).current;

  // Animaciones del modal de éxito
  const overlayFade       = useRef(new Animated.Value(0)).current;
  const cardScale         = useRef(new Animated.Value(0.88)).current;
  const cardSlide         = useRef(new Animated.Value(56)).current;
  const spinValue         = useRef(new Animated.Value(0)).current;
  const spinOpacity       = useRef(new Animated.Value(1)).current;
  const processingOpacity = useRef(new Animated.Value(0)).current;
  const circleScale       = useRef(new Animated.Value(0)).current;
  const checkScale        = useRef(new Animated.Value(0)).current;
  const checkOpacity      = useRef(new Animated.Value(0)).current;
  const titleOpacity      = useRef(new Animated.Value(0)).current;
  const titleSlide        = useRef(new Animated.Value(16)).current;
  const subtitleOpacity   = useRef(new Animated.Value(0)).current;
  const btnOpacity        = useRef(new Animated.Value(0)).current;
  const btnSlide          = useRef(new Animated.Value(18)).current;
  const spinnerLoop       = useRef<Animated.CompositeAnimation | null>(null);

  const showSuccessModal = () => {
    setShowSuccess(true);
    // Reset
    overlayFade.setValue(0);       cardScale.setValue(0.88);
    cardSlide.setValue(56);        spinValue.setValue(0);
    spinOpacity.setValue(1);       processingOpacity.setValue(0);
    circleScale.setValue(0);       checkScale.setValue(0);
    checkOpacity.setValue(0);      titleOpacity.setValue(0);
    titleSlide.setValue(16);       subtitleOpacity.setValue(0);
    btnOpacity.setValue(0);        btnSlide.setValue(18);

    // ① Overlay + card entran
    Animated.parallel([
      Animated.timing(overlayFade, { toValue: 1, duration: 320, useNativeDriver: true }),
      Animated.spring(cardScale,   { toValue: 1, tension: 180, friction: 18, useNativeDriver: true }),
      Animated.spring(cardSlide,   { toValue: 0, tension: 180, friction: 18, useNativeDriver: true }),
    ]).start(() => {

      // ② "Procesando..." aparece
      Animated.timing(processingOpacity, { toValue: 1, duration: 260, useNativeDriver: true }).start();

      // ③ Spinner gira en loop
      spinnerLoop.current = Animated.loop(
        Animated.timing(spinValue, { toValue: 1, duration: 820, easing: Easing.linear, useNativeDriver: true })
      );
      spinnerLoop.current.start();

      // ④ Tras 1.5s, detener spinner y hacer transición al check
      setTimeout(() => {
        spinnerLoop.current?.stop();

        Animated.parallel([
          Animated.timing(spinOpacity,       { toValue: 0, duration: 220, useNativeDriver: true }),
          Animated.timing(processingOpacity, { toValue: 0, duration: 180, useNativeDriver: true }),
        ]).start(() => {

          // ⑤ Círculo verde hace pop
          Animated.spring(circleScale, {
            toValue: 1, tension: 220, friction: 9, useNativeDriver: true,
          }).start(() => {

            // ⑥ Check con bounce + sonido
            Audio.setAudioModeAsync({ playsInSilentModeIOS: true }).catch(() => {});
            Audio.Sound.createAsync(
              require('../../assets/sounds/payment_success.mp3'),
              { shouldPlay: true, volume: 0.75 }
            ).then(({ sound }) => {
              sound.setOnPlaybackStatusUpdate(st => { if (st.isLoaded && st.didJustFinish) sound.unloadAsync(); });
            }).catch(() => {});
            Animated.parallel([
              Animated.spring(checkScale,   { toValue: 1, tension: 280, friction: 8, useNativeDriver: true }),
              Animated.timing(checkOpacity, { toValue: 1, duration: 140, useNativeDriver: true }),
            ]).start();

            // ⑦ Título sube
            setTimeout(() => {
              Animated.parallel([
                Animated.timing(titleOpacity, { toValue: 1, duration: 320, useNativeDriver: true }),
                Animated.spring(titleSlide,   { toValue: 0, tension: 280, friction: 22, useNativeDriver: true }),
              ]).start();

              // ⑧ Subtítulo + botón
              setTimeout(() => {
                Animated.parallel([
                  Animated.timing(subtitleOpacity, { toValue: 1, duration: 340, useNativeDriver: true }),
                  Animated.timing(btnOpacity,      { toValue: 1, duration: 340, useNativeDriver: true }),
                  Animated.spring(btnSlide,        { toValue: 0, tension: 260, friction: 22, useNativeDriver: true }),
                ]).start();
              }, 130);
            }, 200);
          });
        });
      }, 1480);
    });
  };

  const goToPaso = (next: number) => {
    const dir = next > paso ? 1 : -1;
    setPaso(next); // actualiza indicadores de paso de inmediato
    Animated.parallel([
      Animated.timing(slideAnim, {
        toValue: -32 * dir,
        duration: 210,
        easing: Easing.out(Easing.quad),
        useNativeDriver: true,
      }),
      Animated.timing(fadeAnim, {
        toValue: 0,
        duration: 180,
        useNativeDriver: true,
      }),
    ]).start(() => {
      setDisplayedPaso(next);
      slideAnim.setValue(32 * dir);
      Animated.parallel([
        Animated.spring(slideAnim, {
          toValue: 0,
          tension: 260,
          friction: 22,
          useNativeDriver: true,
        }),
        Animated.timing(fadeAnim, {
          toValue: 1,
          duration: 230,
          useNativeDriver: true,
        }),
      ]).start();
    });
  };

  // Refs para focus — Paso 1
  const numDocRef   = useRef<TextInput>(null);
  const emailRef    = useRef<TextInput>(null);
  const passwordRef = useRef<TextInput>(null);

  // Refs para focus — Paso 2
  const nombresRef         = useRef<TextInput>(null);
  const apellidoPRef       = useRef<TextInput>(null);
  const apellidoMRef       = useRef<TextInput>(null);
  const telefonoRef        = useRef<TextInput>(null);
  const razonSocialRef     = useRef<TextInput>(null);
  const personaContactoRef = useRef<TextInput>(null);
  const relacionRef        = useRef<TextInput>(null);

  // Paso 1
  const [tipoDoc, setTipoDoc]               = useState(isNatural ? 'DNI' : 'RUC');
  const [showTipoPicker, setShowTipoPicker] = useState(false);
  const [numDoc, setNumDoc]                 = useState('');
  const [email, setEmail]                   = useState('');
  const [password, setPassword]             = useState('');
  const [showPassword, setShowPassword]     = useState(false);
  const [acceptTerms, setAcceptTerms]       = useState(false);
  const [notRobot, setNotRobot]             = useState(false);

  // Paso 2 — Persona Natural
  const [nombres, setNombres]               = useState('');
  const [apellidoP, setApellidoP]           = useState('');
  const [apellidoM, setApellidoM]           = useState('');
  const [telefono, setTelefono]             = useState('');

  // Paso 2 — Persona Jurídica
  const [razonSocial, setRazonSocial]           = useState('');
  const [personaContacto, setPersonaContacto]   = useState('');
  const [relacionEmpresa, setRelacionEmpresa]   = useState('');

  const [error, setError] = useState('');

  const tiposDocList = isNatural ? ['DNI', 'CE'] : ['RUC'];

  const steps = [
    { num: 1, label: 'Identidad' },
    { num: 2, label: 'Contacto' },
    { num: 3, label: 'Verificación' },
  ];

  // ── Validación reactiva por paso ─────────────────────────────────────────
  const emailLooksValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());

  const canContinuePaso1 =
    numDoc.length === DOC_MAX[tipoDoc] &&
    emailLooksValid &&
    password.length >= 8 &&
    acceptTerms &&
    notRobot;

  const canContinuePaso2 = isNatural
    ? !!nombres.trim() && !!apellidoP.trim() && telefono.length === 9
    : !!razonSocial.trim() && !!personaContacto.trim() && !!relacionEmpresa.trim() && telefono.length === 9;

  const canContinuePaso3 = true; // siempre activo — es solo confirmación

  const isReady =
    paso === 1 ? canContinuePaso1 :
    paso === 2 ? canContinuePaso2 :
    canContinuePaso3;

  const handleContinuar = async () => {
    setError('');
    if (!numDoc || numDoc.length !== DOC_MAX[tipoDoc]) {
      setError(`Ingresa los ${DOC_MAX[tipoDoc]} dígitos del ${tipoDoc}`); return;
    }
    const emailErr = validateEmail(email);
    if (emailErr) { setError(emailErr); return; }
    if (password.length < 8) {
      setError('La contraseña debe tener al menos 8 caracteres'); return;
    }
    if (!acceptTerms) {
      setError('Acepta los Términos y Condiciones'); return;
    }
    if (!notRobot) {
      setError('Confirma que no eres un robot'); return;
    }
    setError('');
    setLoading(true);

    try {
      // 1. Verificar si el documento ya está registrado
      const verifyRes = await fetch(`${API_CONFIG.BASE_URL}/api/client/verify/${numDoc}`);
      const verifyData = await verifyRes.json();
      if (verifyData.success && verifyData.exists) {
        setError(`Este ${tipoDoc} ya tiene una cuenta registrada. Por favor inicia sesión.`);
        return;
      }

      // 2. Pre-cargar datos desde RENIEC (DNI) o SUNAT (RUC)
      if (tipoDoc === 'DNI' || tipoDoc === 'RUC') {
        try {
          const endpoint = tipoDoc === 'DNI' ? 'dni-lookup' : 'ruc-lookup';
          const res = await fetch(`${API_CONFIG.BASE_URL}/api/web/${endpoint}?numero=${numDoc}`);
          const data = await res.json();
          if (data.success) {
            if (tipoDoc === 'DNI') {
              setNombres(data.nombres || '');
              setApellidoP(data.apellido_paterno || '');
              setApellidoM(data.apellido_materno || '');
            } else {
              setRazonSocial(data.razon_social || '');
            }
          }
        } catch (_) {
          // Fallo silencioso — el usuario completa los datos manualmente
        }
      }

      goToPaso(2);
    } catch (_) {
      // Si falla la verificación de red, permitir continuar sin bloquear
      goToPaso(2);
    } finally {
      setLoading(false);
    }
  };

  const handleContinuarPaso2 = () => {
    setError('');
    if (isNatural) {
      if (!nombres.trim()) { setError('Ingresa tu(s) nombre(s)'); return; }
      if (!apellidoP.trim()) { setError('Ingresa tu apellido paterno'); return; }
      if (!telefono || telefono.length < 9) { setError('Ingresa un teléfono válido de 9 dígitos'); return; }
    } else {
      if (!razonSocial.trim()) { setError('Ingresa la razón social'); return; }
      if (!personaContacto.trim()) { setError('Ingresa el nombre del contacto'); return; }
      if (!relacionEmpresa.trim()) { setError('Ingresa el cargo o relación con la empresa'); return; }
      if (!telefono || telefono.length < 9) { setError('Ingresa un teléfono válido de 9 dígitos'); return; }
    }
    setError('');
    goToPaso(3);
  };

  const handleSubmit = async () => {
    setError('');
    setLoading(true);
    try {
      const payload = isNatural
        ? {
            tipo_persona: 'Natural' as const,
            tipo_documento: tipoDoc as 'DNI' | 'CE',
            dni: numDoc,
            nombres: nombres.trim(),
            apellido_paterno: apellidoP.trim(),
            apellido_materno: apellidoM.trim() || undefined,
            email: email.trim().toLowerCase(),
            telefono: telefono.trim(),
            password,
          }
        : {
            tipo_persona: 'Jurídica' as const,
            tipo_documento: 'RUC' as const,
            dni: numDoc,
            razon_social: razonSocial.trim(),
            persona_contacto: personaContacto.trim(),
            relacion_empresa: relacionEmpresa.trim(),
            email: email.trim().toLowerCase(),
            telefono: telefono.trim(),
            password,
          };

      await authApi.register(payload);
      showSuccessModal();
    } catch (err: any) {
      setError(err.message || 'Error al crear la cuenta');
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={s.root}>
      {/* Botón volver — posición unificada con todas las pantallas auth */}
      <TouchableOpacity
        style={[s.backBtn, { top: insets.top + 16 }]}
        onPress={() => { setError(''); paso > 1 ? goToPaso(paso - 1) : navigation.goBack(); }}
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

          {/* Contenido animado — desliza entre pasos */}
          <Animated.View style={{ transform: [{ translateX: slideAnim }], opacity: fadeAnim }}>

          {/* ── PASO 1: Identidad ────────────────────────────────────── */}
          {displayedPaso === 1 && (<>

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
              <TouchableOpacity style={[s.inputBox, s.numBox]} onPress={() => numDocRef.current?.focus()} activeOpacity={1}>
                <Text style={s.inputLabel}>Número de documento</Text>
                <TextInput
                  ref={numDocRef}
                  style={s.inputValue}
                  value={numDoc}
                  onChangeText={t => setNumDoc(t.replace(/\D/g, '').slice(0, DOC_MAX[tipoDoc]))}
                  keyboardType="numeric"
                  maxLength={DOC_MAX[tipoDoc]}
                  placeholderTextColor="rgba(255,255,255,0.2)"
                  selectionColor="#22c55e"
                />
              </TouchableOpacity>
            </View>

            {/* Correo electrónico */}
            <TouchableOpacity style={s.inputBox} onPress={() => emailRef.current?.focus()} activeOpacity={1}>
              <Text style={s.inputLabel}>Correo electrónico</Text>
              <TextInput
                ref={emailRef}
                style={s.inputValue}
                value={email}
                onChangeText={setEmail}
                keyboardType="email-address"
                autoCapitalize="none"
                placeholderTextColor="rgba(255,255,255,0.2)"
                selectionColor="#22c55e"
              />
            </TouchableOpacity>

            {/* Contraseña */}
            <TouchableOpacity style={s.inputBox} onPress={() => passwordRef.current?.focus()} activeOpacity={1}>
              <Text style={s.inputLabel}>Contraseña</Text>
              <View style={s.passwordRow}>
                <TextInput
                  ref={passwordRef}
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
            </TouchableOpacity>

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

          </>)}

          {/* ── PASO 2: Contacto ─────────────────────────────────────── */}
          {displayedPaso === 2 && (<>

            {isNatural ? (<>
              {/* Nombres */}
              <TouchableOpacity style={s.inputBox} onPress={() => nombresRef.current?.focus()} activeOpacity={1}>
                <Text style={s.inputLabel}>Nombre(s)</Text>
                <TextInput
                  ref={nombresRef}
                  style={s.inputValue}
                  value={nombres}
                  onChangeText={setNombres}
                  autoCapitalize="words"
                  placeholderTextColor="rgba(255,255,255,0.2)"
                  selectionColor="#22c55e"
                />
              </TouchableOpacity>

              {/* Apellido Paterno */}
              <TouchableOpacity style={s.inputBox} onPress={() => apellidoPRef.current?.focus()} activeOpacity={1}>
                <Text style={s.inputLabel}>Apellido Paterno</Text>
                <TextInput
                  ref={apellidoPRef}
                  style={s.inputValue}
                  value={apellidoP}
                  onChangeText={setApellidoP}
                  autoCapitalize="words"
                  placeholderTextColor="rgba(255,255,255,0.2)"
                  selectionColor="#22c55e"
                />
              </TouchableOpacity>

              {/* Apellido Materno */}
              <TouchableOpacity style={s.inputBox} onPress={() => apellidoMRef.current?.focus()} activeOpacity={1}>
                <Text style={s.inputLabel}>Apellido Materno <Text style={s.optionalLabel}>(opcional)</Text></Text>
                <TextInput
                  ref={apellidoMRef}
                  style={s.inputValue}
                  value={apellidoM}
                  onChangeText={setApellidoM}
                  autoCapitalize="words"
                  placeholderTextColor="rgba(255,255,255,0.2)"
                  selectionColor="#22c55e"
                />
              </TouchableOpacity>
            </>) : (<>
              {/* Razón Social */}
              <TouchableOpacity style={s.inputBox} onPress={() => razonSocialRef.current?.focus()} activeOpacity={1}>
                <Text style={s.inputLabel}>Razón Social</Text>
                <TextInput
                  ref={razonSocialRef}
                  style={s.inputValue}
                  value={razonSocial}
                  onChangeText={setRazonSocial}
                  autoCapitalize="characters"
                  placeholderTextColor="rgba(255,255,255,0.2)"
                  selectionColor="#22c55e"
                />
              </TouchableOpacity>

              {/* Persona de Contacto */}
              <TouchableOpacity style={s.inputBox} onPress={() => personaContactoRef.current?.focus()} activeOpacity={1}>
                <Text style={s.inputLabel}>Persona de Contacto</Text>
                <TextInput
                  ref={personaContactoRef}
                  style={s.inputValue}
                  value={personaContacto}
                  onChangeText={setPersonaContacto}
                  autoCapitalize="words"
                  placeholderTextColor="rgba(255,255,255,0.2)"
                  selectionColor="#22c55e"
                />
              </TouchableOpacity>

              {/* Relación con la empresa */}
              <TouchableOpacity style={s.inputBox} onPress={() => relacionRef.current?.focus()} activeOpacity={1}>
                <Text style={s.inputLabel}>Cargo / Relación con la empresa</Text>
                <TextInput
                  ref={relacionRef}
                  style={s.inputValue}
                  value={relacionEmpresa}
                  onChangeText={setRelacionEmpresa}
                  autoCapitalize="words"
                  placeholderTextColor="rgba(255,255,255,0.2)"
                  selectionColor="#22c55e"
                />
              </TouchableOpacity>
            </>)}

            {/* Teléfono — común para ambos */}
            <TouchableOpacity style={s.inputBox} onPress={() => telefonoRef.current?.focus()} activeOpacity={1}>
              <Text style={s.inputLabel}>Teléfono</Text>
              <TextInput
                ref={telefonoRef}
                style={s.inputValue}
                value={telefono}
                onChangeText={t => setTelefono(t.replace(/\D/g, '').slice(0, 9))}
                keyboardType="phone-pad"
                maxLength={9}
                placeholderTextColor="rgba(255,255,255,0.2)"
                selectionColor="#22c55e"
              />
            </TouchableOpacity>

          </>)}

          {/* ── PASO 3: Verificación ─────────────────────────────────── */}
          {displayedPaso === 3 && (
            <View style={s.summaryBox}>
              <Text style={s.summaryTitle}>Resumen de tu cuenta</Text>

              <View style={s.summaryRow}>
                <Text style={s.summaryLabel}>Documento</Text>
                <Text style={s.summaryValue}>{tipoDoc} {numDoc}</Text>
              </View>
              <View style={s.summaryRow}>
                <Text style={s.summaryLabel}>Correo</Text>
                <Text style={s.summaryValue}>{email}</Text>
              </View>
              {isNatural ? (<>
                <View style={s.summaryRow}>
                  <Text style={s.summaryLabel}>Nombre</Text>
                  <Text style={s.summaryValue}>{nombres} {apellidoP} {apellidoM}</Text>
                </View>
              </>) : (<>
                <View style={s.summaryRow}>
                  <Text style={s.summaryLabel}>Razón Social</Text>
                  <Text style={s.summaryValue}>{razonSocial}</Text>
                </View>
                <View style={s.summaryRow}>
                  <Text style={s.summaryLabel}>Contacto</Text>
                  <Text style={s.summaryValue}>{personaContacto}</Text>
                </View>
              </>)}
              <View style={s.summaryRow}>
                <Text style={s.summaryLabel}>Teléfono</Text>
                <Text style={s.summaryValue}>{telefono}</Text>
              </View>
            </View>
          )}

          </Animated.View>

            {/* Error */}
            {!!error && (
              <Text style={s.errorText}>{error}</Text>
            )}

            {/* Separador */}
            <View style={s.separator} />

            {/* Botón principal */}
            <TouchableOpacity
              style={[s.continueBtn, isReady && s.continueBtnReady]}
              onPress={paso === 1 ? handleContinuar : paso === 2 ? handleContinuarPaso2 : handleSubmit}
              activeOpacity={0.75}
              disabled={loading}
            >
              {loading
                ? <ActivityIndicator color="#ffffff" size="small" />
                : <Text style={[s.continueBtnText, isReady && s.continueBtnTextReady]}>
                    {paso === 3 ? 'Crear Cuenta' : 'Continuar'}
                  </Text>
              }
            </TouchableOpacity>

          </BlurView>

        </ScrollView>
      </KeyboardAvoidingView>

      {/* ── Modal de éxito ─────────────────────────────────────────────── */}
      {showSuccess && (() => {
        const spin = spinValue.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '360deg'] });
        return (
          <Animated.View style={[s.successOverlay, { opacity: overlayFade }]}>

            {/* Logo + contenido centrados juntos */}
            <Animated.View style={[s.successContent, { transform: [{ scale: cardScale }, { translateY: cardSlide }] }]}>
              <Image
                source={require('../../assets/logo.png')}
                style={s.successLogo}
                resizeMode="contain"
              />

              {/* Zona del ícono */}
              <View style={s.successIconZone}>
                <Animated.View style={[s.spinTrack, { opacity: spinOpacity }]} />
                <Animated.View style={[s.spinArc, { opacity: spinOpacity, transform: [{ rotate: spin }] }]} />
                <Animated.View style={[s.successCircle, { transform: [{ scale: circleScale }] }]}>
                  <View style={s.successRing} />
                  <Animated.View style={{ transform: [{ scale: checkScale }], opacity: checkOpacity }}>
                    <Ionicons name="checkmark" size={44} color="#ffffff" />
                  </Animated.View>
                </Animated.View>
              </View>

              {/* "Creando tu cuenta..." */}
              <Animated.Text style={[s.processingText, { opacity: processingOpacity }]}>
                Creando tu cuenta...
              </Animated.Text>

              {/* Título */}
              <Animated.Text style={[s.successTitle, { opacity: titleOpacity, transform: [{ translateY: titleSlide }] }]}>
                ¡Cuenta creada!
              </Animated.Text>

              {/* Subtítulo */}
              <Animated.Text style={[s.successSubtitle, { opacity: subtitleOpacity }]}>
                {'Tu cuenta ha sido registrada correctamente.\nBienvenido a Qoricash.'}
              </Animated.Text>

              {/* Botón */}
              <Animated.View style={[s.successBtnWrap, { opacity: btnOpacity, transform: [{ translateY: btnSlide }] }]}>
                <TouchableOpacity
                  style={s.successBtn}
                  onPress={() => { setShowSuccess(false); navigation.navigate('Login' as never); }}
                  activeOpacity={0.8}
                >
                  <Text style={s.successBtnText}>Iniciar Sesión</Text>
                  <Ionicons name="arrow-forward" size={15} color="#ffffff" style={{ marginLeft: 8 }} />
                </TouchableOpacity>
              </Animated.View>

            </Animated.View>
          </Animated.View>
        );
      })()}
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

  // Paso 2 helper
  optionalLabel: {
    fontSize: 9,
    color: 'rgba(255,255,255,0.35)',
    fontWeight: '400',
  },

  // Paso 3 summary
  summaryBox: {
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 4,
  },
  summaryTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: 'rgba(255,255,255,0.55)',
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    marginBottom: 16,
  },
  summaryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 12,
    gap: 12,
  },
  summaryLabel: {
    fontSize: 12,
    color: 'rgba(255,255,255,0.45)',
    fontWeight: '600',
    flex: 0.45,
  },
  summaryValue: {
    fontSize: 13,
    color: '#ffffff',
    fontWeight: '500',
    flex: 0.55,
    textAlign: 'right',
  },

  // Modal de éxito — fondo negro puro, sin card
  successOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: '#000000',
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 32,
    zIndex: 100,
  },
  // Logo superior
  successLogo: {
    width: 140,
    height: 44,
    marginBottom: 48,
  },
  // Contenido central (sin card, sin borde, sin fondo)
  successContent: {
    width: '100%',
    alignItems: 'center',
  },
  // Zona del ícono (spinner → check)
  successIconZone: {
    width: 92,
    height: 92,
    marginBottom: 28,
    alignItems: 'center',
    justifyContent: 'center',
  },
  // Track tenue del spinner
  spinTrack: {
    position: 'absolute',
    width: 92,
    height: 92,
    borderRadius: 46,
    borderWidth: 2.5,
    borderColor: 'rgba(255,255,255,0.08)',
  },
  // Arco giratorio del spinner
  spinArc: {
    position: 'absolute',
    width: 92,
    height: 92,
    borderRadius: 46,
    borderWidth: 2.5,
    borderTopColor: '#22c55e',
    borderRightColor: 'rgba(34,197,94,0.3)',
    borderBottomColor: 'transparent',
    borderLeftColor: 'transparent',
  },
  // Círculo verde del check
  successCircle: {
    position: 'absolute',
    width: 82,
    height: 82,
    borderRadius: 41,
    backgroundColor: '#22c55e',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#22c55e',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.6,
    shadowRadius: 22,
    elevation: 12,
  },
  successRing: {
    position: 'absolute',
    width: 102,
    height: 102,
    borderRadius: 51,
    borderWidth: 1,
    borderColor: 'rgba(34,197,94,0.2)',
  },
  // Texto "Creando tu cuenta..."
  processingText: {
    fontSize: 14,
    color: 'rgba(255,255,255,0.4)',
    fontWeight: '400',
    letterSpacing: 0.4,
    marginBottom: 28,
    height: 22,
  },
  successTitle: {
    fontSize: 26,
    fontWeight: '800',
    color: '#ffffff',
    textAlign: 'center',
    marginBottom: 12,
    letterSpacing: 0.1,
  },
  successSubtitle: {
    fontSize: 14,
    color: 'rgba(255,255,255,0.45)',
    textAlign: 'center',
    lineHeight: 22,
    marginBottom: 48,
    fontWeight: '400',
  },
  successBtnWrap: {
    width: '100%',
  },
  successBtn: {
    width: '100%',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.2)',
    borderRadius: 14,
    paddingVertical: 16,
    backgroundColor: 'rgba(255,255,255,0.05)',
  },
  successBtnText: {
    fontSize: 15,
    fontWeight: '700',
    color: '#ffffff',
    letterSpacing: 0.3,
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
    borderRadius: 14,
    backgroundColor: 'rgba(255,255,255,0.08)',
  },
  continueBtnReady: {
    backgroundColor: '#22c55e',
    shadowColor: '#22c55e',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.35,
    shadowRadius: 10,
    elevation: 6,
  },
  continueBtnText: {
    fontSize: 16,
    fontWeight: '700',
    color: 'rgba(255,255,255,0.4)',
    letterSpacing: 0.3,
  },
  continueBtnTextReady: {
    color: '#ffffff',
  },
});
