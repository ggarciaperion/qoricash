import React, { useState, useRef, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Alert,
  Image,
  ImageBackground,
  TouchableOpacity,
  Linking,
  Animated,
  Easing,
  ActivityIndicator,
} from 'react-native';
import { BlurView } from 'expo-blur';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import * as DocumentPicker from 'expo-document-picker';
import { useNavigation } from '@react-navigation/native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import axios from 'axios';
import { API_CONFIG } from '../constants/config';
import { useAuth } from '../contexts/AuthContext';
import { useBackground } from '../hooks/useBackground';

// BG handled by useBackground hook

export const VerifyIdentityScreen = () => {
  const navigation = useNavigation();
  const insets = useSafeAreaInsets();
  const bg = useBackground();
  const { client, refreshClient } = useAuth();

  const [frontImage, setFrontImage]   = useState<string | null>(null);
  const [backImage, setBackImage]     = useState<string | null>(null);
  const [rucDocument, setRucDocument] = useState<{ uri: string; name: string; type: string } | null>(null);
  const [uploading, setUploading]     = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);
  const screenOpacity = useRef(new Animated.Value(1)).current;

  const isLegalEntity = client?.document_type === 'RUC';

  // ── Entrance animations ────────────────────────────────────────────────────
  const info1Anim = useRef(new Animated.Value(0)).current;
  const card1Anim = useRef(new Animated.Value(0)).current;
  const card2Anim = useRef(new Animated.Value(0)).current;
  const card3Anim = useRef(new Animated.Value(0)).current;
  const btnAnim   = useRef(new Animated.Value(0)).current;

  // ── Success modal animations ───────────────────────────────────────────────
  const overlayFade  = useRef(new Animated.Value(0)).current;
  const cardScale    = useRef(new Animated.Value(0.82)).current;
  const cardSlide    = useRef(new Animated.Value(48)).current;
  const circleScale  = useRef(new Animated.Value(0)).current;
  const checkScale   = useRef(new Animated.Value(0)).current;
  const checkOpacity = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.stagger(70, [info1Anim, card1Anim, card2Anim, card3Anim, btnAnim].map(a =>
      Animated.spring(a, { toValue: 1, tension: 200, friction: 18, useNativeDriver: true })
    )).start();
  }, []);

  const animStyle = (anim: Animated.Value) => ({
    opacity: anim,
    transform: [{
      translateY: anim.interpolate({ inputRange: [0, 1], outputRange: [28, 0] }),
    }],
  });

  // ── Pulse for upload zones ─────────────────────────────────────────────────
  const pulseFront = useRef(new Animated.Value(1)).current;
  const pulseBack  = useRef(new Animated.Value(1)).current;
  const pulseRuc   = useRef(new Animated.Value(1)).current;

  const startPulse = (anim: Animated.Value) => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(anim, { toValue: 1.03, duration: 900, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
        Animated.timing(anim, { toValue: 1,    duration: 900, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
      ])
    ).start();
  };

  useEffect(() => { startPulse(pulseFront); }, []);
  useEffect(() => { startPulse(pulseBack);  }, []);
  useEffect(() => { startPulse(pulseRuc);   }, []);

  // ── Success modal ──────────────────────────────────────────────────────────
  const showSuccessModal = () => {
    setShowSuccess(true);
    overlayFade.setValue(0);  cardScale.setValue(0.82);  cardSlide.setValue(48);
    circleScale.setValue(0);  checkScale.setValue(0);    checkOpacity.setValue(0);

    Animated.parallel([
      Animated.timing(overlayFade, { toValue: 1, duration: 260, useNativeDriver: true }),
      Animated.spring(cardScale,   { toValue: 1, tension: 180, friction: 16, useNativeDriver: true }),
      Animated.spring(cardSlide,   { toValue: 0, tension: 180, friction: 16, useNativeDriver: true }),
    ]).start(() => {
      Animated.spring(circleScale, { toValue: 1, tension: 200, friction: 10, useNativeDriver: true }).start(() => {
        Animated.parallel([
          Animated.spring(checkScale,   { toValue: 1, tension: 240, friction: 9, useNativeDriver: true }),
          Animated.timing(checkOpacity, { toValue: 1, duration: 120, useNativeDriver: true }),
        ]).start();
      });
    });
  };

  // ── Permissions ────────────────────────────────────────────────────────────
  const requestPermissions = async () => {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert('Permisos Requeridos', 'Necesitamos acceso a tu galería para subir las fotos.');
      return false;
    }
    return true;
  };

  const pickImage = async (side: 'front' | 'back') => {
    const ok = await requestPermissions();
    if (!ok) return;
    try {
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsEditing: true, aspect: [4, 3], quality: 0.8,
      });
      if (!result.canceled && result.assets[0]) {
        side === 'front' ? setFrontImage(result.assets[0].uri) : setBackImage(result.assets[0].uri);
      }
    } catch { Alert.alert('Error', 'No se pudo seleccionar la imagen'); }
  };

  const takePhoto = async (side: 'front' | 'back') => {
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert('Permisos Requeridos', 'Necesitamos acceso a tu cámara para tomar fotos.');
      return;
    }
    try {
      const result = await ImagePicker.launchCameraAsync({
        allowsEditing: true, aspect: [4, 3], quality: 0.8,
      });
      if (!result.canceled && result.assets[0]) {
        side === 'front' ? setFrontImage(result.assets[0].uri) : setBackImage(result.assets[0].uri);
      }
    } catch { Alert.alert('Error', 'No se pudo tomar la foto'); }
  };

  const showImageOptions = (side: 'front' | 'back') => {
    const docType = isLegalEntity ? 'DNI del Representante Legal' : 'DNI';
    Alert.alert(
      `${docType} — ${side === 'front' ? 'Anverso' : 'Reverso'}`,
      'Selecciona una opción',
      [
        { text: 'Tomar Foto',        onPress: () => takePhoto(side) },
        { text: 'Elegir de Galería', onPress: () => pickImage(side) },
        { text: 'Cancelar', style: 'cancel' },
      ]
    );
  };

  const pickRucFromGallery = async () => {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert('Permisos Requeridos', 'Necesitamos acceso a tu galería.');
      return;
    }
    try {
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsEditing: false, quality: 0.85,
      });
      if (!result.canceled && result.assets[0]) {
        const asset = result.assets[0];
        const name = asset.fileName || `ficha_ruc_${Date.now()}.jpg`;
        setRucDocument({ uri: asset.uri, name, type: asset.mimeType || 'image/jpeg' });
      }
    } catch { Alert.alert('Error', 'No se pudo seleccionar la imagen'); }
  };

  const pickRucFromFiles = async () => {
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: ['image/*', 'application/pdf'], copyToCacheDirectory: true,
      });
      if (!result.canceled && result.assets[0]) {
        const file = result.assets[0];
        setRucDocument({ uri: file.uri, name: file.name, type: file.mimeType || 'application/pdf' });
      }
    } catch { Alert.alert('Error', 'No se pudo seleccionar el documento'); }
  };

  const pickRucDocument = () => {
    Alert.alert(
      'Adjuntar Ficha RUC',
      'Selecciona el origen del documento',
      [
        { text: 'Fotos', onPress: pickRucFromGallery },
        { text: 'Archivos', onPress: pickRucFromFiles },
        { text: 'Cancelar', style: 'cancel' },
      ]
    );
  };

  // ── Submit ─────────────────────────────────────────────────────────────────
  const handleSubmit = async () => {
    if (!isLegalEntity && (!frontImage || !backImage)) {
      Alert.alert('Faltan Imágenes', 'Por favor adjunta ambas fotos de tu DNI (anverso y reverso)');
      return;
    }
    if (isLegalEntity && !rucDocument) {
      Alert.alert('Falta Ficha RUC', 'Por favor adjunta la Ficha RUC (imagen o PDF)');
      return;
    }
    try {
      setUploading(true);
      const formData = new FormData();
      formData.append('dni', client?.dni || '');
      if (frontImage)
        formData.append('dni_front', { uri: frontImage, type: 'image/jpeg', name: `dni_front_${client?.dni}.jpg` } as any);
      if (backImage)
        formData.append('dni_back', { uri: backImage, type: 'image/jpeg', name: `dni_back_${client?.dni}.jpg` } as any);
      if (isLegalEntity && rucDocument)
        formData.append('ruc_ficha', { uri: rucDocument.uri, type: rucDocument.type, name: rucDocument.name } as any);

      const response = await axios.post(
        `${API_CONFIG.BASE_URL}/api/client/upload-dni`,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );
      if (response.data.success) {
        showSuccessModal();
      } else {
        Alert.alert('Error', response.data.message || 'Error al subir documentos');
      }
    } catch (error: any) {
      Alert.alert('Error', error.response?.data?.message || 'Error al subir documentos');
    } finally {
      setUploading(false);
    }
  };

  const canSubmit = !uploading && (
    isLegalEntity
      ? !!rucDocument
      : !!frontImage && !!backImage
  );

  // ── Upload zone component ──────────────────────────────────────────────────
  const UploadZone = ({
    image, pulse, onPress, onClear, label, icon,
  }: {
    image: string | null;
    pulse: Animated.Value;
    onPress: () => void;
    onClear: () => void;
    label: string;
    icon: string;
  }) => (
    <View style={s.cardSection}>
      <View style={s.cardLabelRow}>
        <Ionicons name={icon as any} size={14} color="rgba(255,255,255,0.45)" />
        <Text style={s.cardLabel}>{label}</Text>
        {image && (
          <TouchableOpacity onPress={onClear} style={s.clearBtn} activeOpacity={0.7}>
            <Ionicons name="close-circle" size={18} color="rgba(239,68,68,0.8)" />
          </TouchableOpacity>
        )}
      </View>

      {image ? (
        <TouchableOpacity onPress={onPress} activeOpacity={0.88} style={s.previewWrap}>
          <Image source={{ uri: image }} style={s.previewImage} resizeMode="cover" />
          <View style={s.previewBadge}>
            <Ionicons name="checkmark-circle" size={16} color="#22c55e" />
            <Text style={s.previewBadgeText}>Imagen cargada</Text>
          </View>
        </TouchableOpacity>
      ) : (
        <Animated.View style={{ transform: [{ scale: pulse }] }}>
          <TouchableOpacity onPress={onPress} activeOpacity={0.8} style={s.uploadZone}>
            <View style={s.uploadIconWrap}>
              <Ionicons name="camera-outline" size={28} color="rgba(99,179,237,0.85)" />
            </View>
            <Text style={s.uploadZoneText}>Toca para agregar</Text>
            <Text style={s.uploadZoneSub}>Cámara o galería</Text>
          </TouchableOpacity>
        </Animated.View>
      )}
    </View>
  );

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <Animated.View style={[{ flex: 1 }, { opacity: screenOpacity }]}>
    <ImageBackground source={bg} style={s.root} resizeMode="cover">
      {/* ── Header fijo ──────────────────────────────────────────────────── */}
      <View style={[s.fixedHeader, { paddingTop: insets.top }]}>
        <TouchableOpacity
          style={s.backBtn}
          onPress={() => navigation.goBack()}
          activeOpacity={0.8}
        >
          <Ionicons name="chevron-back" size={22} color="#ffffff" />
        </TouchableOpacity>
        <Text style={s.headerTitle}>Validación de Identidad</Text>
        <View style={s.headerRight} />
      </View>

      <ScrollView
        contentContainerStyle={[s.scroll, { paddingBottom: insets.bottom + 40 }]}
        showsVerticalScrollIndicator={false}
      >

        {/* ── DNI Anverso y Reverso — solo para Persona Natural ─────────── */}
        {!isLegalEntity && (
          <>
            <Animated.View style={animStyle(card1Anim)}>
              <BlurView intensity={35} tint="dark" style={s.card}>
                <View style={s.cardHeader}>
                  <View style={s.cardIconWrap}>
                    <Ionicons name="card-outline" size={17} color="#63b3ed" />
                  </View>
                  <Text style={s.cardTitle}>DNI — Anverso</Text>
                </View>
                <UploadZone
                  image={frontImage}
                  pulse={pulseFront}
                  onPress={() => showImageOptions('front')}
                  onClear={() => setFrontImage(null)}
                  label="Parte frontal del documento"
                  icon="image-outline"
                />
              </BlurView>
            </Animated.View>

            <Animated.View style={animStyle(card2Anim)}>
              <BlurView intensity={35} tint="dark" style={s.card}>
                <View style={s.cardHeader}>
                  <View style={s.cardIconWrap}>
                    <Ionicons name="card-outline" size={17} color="#63b3ed" />
                  </View>
                  <Text style={s.cardTitle}>DNI — Reverso</Text>
                </View>
                <UploadZone
                  image={backImage}
                  pulse={pulseBack}
                  onPress={() => showImageOptions('back')}
                  onClear={() => setBackImage(null)}
                  label="Parte posterior del documento"
                  icon="image-outline"
                />
              </BlurView>
            </Animated.View>
          </>
        )}

        {/* ── Ficha RUC ─────────────────────────────────────────────────── */}
        {isLegalEntity && (
          <Animated.View style={animStyle(card3Anim)}>
            <BlurView intensity={35} tint="dark" style={s.card}>
              <View style={s.cardHeader}>
                <View style={s.cardIconWrap}>
                  <Ionicons name="document-text-outline" size={17} color="#63b3ed" />
                </View>
                <Text style={s.cardTitle}>Ficha RUC</Text>
              </View>

              <View style={s.cardSection}>
                <View style={s.cardLabelRow}>
                  <Ionicons name="attach-outline" size={14} color="rgba(255,255,255,0.45)" />
                  <Text style={s.cardLabel}>Imagen o PDF de la Ficha RUC</Text>
                  {rucDocument && (
                    <TouchableOpacity onPress={() => setRucDocument(null)} style={s.clearBtn} activeOpacity={0.7}>
                      <Ionicons name="close-circle" size={18} color="rgba(239,68,68,0.8)" />
                    </TouchableOpacity>
                  )}
                </View>

                {rucDocument ? (
                  <TouchableOpacity onPress={pickRucDocument} activeOpacity={0.88} style={s.previewWrap}>
                    {rucDocument.type.includes('pdf') ? (
                      <View style={s.pdfPreview}>
                        <Ionicons name="document-text" size={38} color="#ef4444" />
                        <Text style={s.pdfName} numberOfLines={2}>{rucDocument.name}</Text>
                      </View>
                    ) : (
                      <Image source={{ uri: rucDocument.uri }} style={s.previewImage} resizeMode="cover" />
                    )}
                    <View style={s.previewBadge}>
                      <Ionicons name="checkmark-circle" size={16} color="#22c55e" />
                      <Text style={s.previewBadgeText}>Documento cargado</Text>
                    </View>
                  </TouchableOpacity>
                ) : (
                  <Animated.View style={{ transform: [{ scale: pulseRuc }] }}>
                    <TouchableOpacity onPress={pickRucDocument} activeOpacity={0.8} style={s.uploadZone}>
                      <View style={s.uploadIconWrap}>
                        <Ionicons name="cloud-upload-outline" size={28} color="rgba(99,179,237,0.85)" />
                      </View>
                      <Text style={s.uploadZoneText}>Toca para adjuntar</Text>
                      <Text style={s.uploadZoneSub}>Imagen o PDF</Text>
                    </TouchableOpacity>
                  </Animated.View>
                )}
              </View>
            </BlurView>
          </Animated.View>
        )}

        {/* ── Submit button ─────────────────────────────────────────────── */}
        <Animated.View style={animStyle(btnAnim)}>
          <TouchableOpacity
            style={[s.submitBtn, !canSubmit && s.submitBtnDisabled]}
            onPress={handleSubmit}
            disabled={!canSubmit}
            activeOpacity={0.85}
          >
            {uploading ? (
              <ActivityIndicator size="small" color="#ffffff" />
            ) : (
              <>
                <Ionicons name="cloud-upload-outline" size={20} color="#ffffff" style={{ marginRight: 8 }} />
                <Text style={s.submitBtnText}>Enviar Documentos</Text>
              </>
            )}
          </TouchableOpacity>

          <TouchableOpacity
            style={s.waBtn}
            onPress={() => Linking.openURL('https://wa.me/51910624404?text=Hola,%20quiero%20enviar%20mis%20documentos%20para%20validar%20mi%20identidad')}
            activeOpacity={0.85}
          >
            <Ionicons name="logo-whatsapp" size={20} color="#ffffff" style={{ marginRight: 8 }} />
            <Text style={s.waBtnText}>Enviar documentos por WhatsApp</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={s.cancelBtn}
            onPress={() => navigation.goBack()}
            disabled={uploading}
            activeOpacity={0.7}
          >
            <Text style={s.cancelBtnText}>Cancelar</Text>
          </TouchableOpacity>
        </Animated.View>

      </ScrollView>

      {/* ── Modal de éxito ──────────────────────────────────────────────── */}
      {showSuccess && (
        <Animated.View style={[s.successOverlay, { opacity: overlayFade }]}>
          <BlurView intensity={50} tint="dark" style={StyleSheet.absoluteFill} />
          <Animated.View style={[s.successCard, { transform: [{ scale: cardScale }, { translateY: cardSlide }] }]}>
            <Animated.View style={[s.successCircle, { transform: [{ scale: circleScale }] }]}>
              <View style={s.successRing} />
              <Animated.View style={{ transform: [{ scale: checkScale }], opacity: checkOpacity }}>
                <Ionicons name="checkmark" size={42} color="#ffffff" />
              </Animated.View>
            </Animated.View>

            <Text style={s.successTitle}>¡Documentos Enviados!</Text>
            <Text style={s.successSubtitle}>
              {'Nuestro equipo revisará tu identidad\ny te notificará cuando esté verificada.\nGeneralmente toma menos de 10 minutos.'}
            </Text>

            <TouchableOpacity
              style={s.successBtn}
              onPress={async () => {
                try { await refreshClient(); } catch {}
                // Fade out suave antes de navegar
                Animated.timing(screenOpacity, {
                  toValue: 0,
                  duration: 420,
                  easing: Easing.out(Easing.quad),
                  useNativeDriver: true,
                }).start(() => {
                  setShowSuccess(false);
                  navigation.goBack();
                });
              }}
              activeOpacity={0.82}
            >
              <Text style={s.successBtnText}>Entendido</Text>
            </TouchableOpacity>
          </Animated.View>
        </Animated.View>
      )}

    </ImageBackground>
    </Animated.View>
  );
};

export default VerifyIdentityScreen;

const s = StyleSheet.create({
  root: {
    flex: 1,
  },
  // ── Fixed header
  fixedHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingBottom: 14,
    backgroundColor: 'transparent',
    zIndex: 20,
  },
  backBtn: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: 'rgba(255,255,255,0.08)',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.12)',
  },
  headerTitle: {
    flex: 1,
    textAlign: 'center',
    fontSize: 17,
    fontWeight: '700',
    color: '#ffffff',
    letterSpacing: 0.2,
  },
  headerRight: {
    width: 38,
  },

  // ── Scroll
  scroll: {
    paddingHorizontal: 20,
  },

  // ── Info card
  infoCard: {
    borderRadius: 16,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: 'rgba(251,191,36,0.18)',
    backgroundColor: 'rgba(251,191,36,0.04)',
    padding: 16,
    marginBottom: 14,
  },
  infoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
  },
  infoTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: '#fbbf24',
  },
  infoBody: {
    fontSize: 12.5,
    color: 'rgba(255,255,255,0.52)',
    lineHeight: 20,
    paddingLeft: 24,
  },

  // ── Cards
  card: {
    borderRadius: 18,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.08)',
    backgroundColor: 'rgba(255,255,255,0.15)',
    marginBottom: 14,
    padding: 18,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 14,
  },
  cardIconWrap: {
    width: 32,
    height: 32,
    borderRadius: 10,
    backgroundColor: 'rgba(99,179,237,0.1)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  cardTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#ffffff',
    flex: 1,
  },

  // ── Card section
  cardSection: { gap: 10 },
  cardLabelRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  cardLabel: {
    fontSize: 12,
    color: 'rgba(255,255,255,0.42)',
    flex: 1,
  },
  clearBtn: { padding: 2 },

  // ── Upload zone
  uploadZone: {
    borderWidth: 1.5,
    borderColor: 'rgba(99,179,237,0.22)',
    borderStyle: 'dashed',
    borderRadius: 14,
    paddingVertical: 26,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(99,179,237,0.03)',
    gap: 8,
  },
  uploadIconWrap: {
    width: 54,
    height: 54,
    borderRadius: 27,
    backgroundColor: 'rgba(99,179,237,0.1)',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 4,
  },
  uploadZoneText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#63b3ed',
  },
  uploadZoneSub: {
    fontSize: 12,
    color: 'rgba(255,255,255,0.32)',
  },

  // ── Preview
  previewWrap: {
    borderRadius: 14,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: 'rgba(34,197,94,0.3)',
  },
  previewImage: {
    width: '100%',
    height: 185,
  },
  previewBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 14,
    paddingVertical: 9,
    backgroundColor: 'rgba(34,197,94,0.08)',
    borderTopWidth: 1,
    borderTopColor: 'rgba(34,197,94,0.18)',
  },
  previewBadgeText: {
    fontSize: 12,
    color: '#22c55e',
    fontWeight: '600',
  },

  // ── PDF preview
  pdfPreview: {
    paddingVertical: 28,
    alignItems: 'center',
    gap: 10,
    backgroundColor: 'rgba(239,68,68,0.05)',
  },
  pdfName: {
    fontSize: 12,
    color: 'rgba(255,255,255,0.55)',
    textAlign: 'center',
    paddingHorizontal: 16,
  },

  // ── Submit button
  submitBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#22c55e',
    borderRadius: 16,
    paddingVertical: 17,
    borderWidth: 1,
    borderColor: 'rgba(34,197,94,0.3)',
    shadowColor: '#22c55e',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.45,
    shadowRadius: 14,
    elevation: 8,
  },
  submitBtnDisabled: {
    backgroundColor: '#1A3D58',
    borderColor: 'rgba(99,179,237,0.2)',
    shadowColor: '#1A3D58',
    opacity: 0.38,
    shadowOpacity: 0,
  },
  submitBtnText: {
    fontSize: 16,
    fontWeight: '700',
    color: '#ffffff',
    letterSpacing: 0.3,
  },
  waBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(37,211,102,0.07)',
    borderRadius: 16,
    paddingVertical: 17,
    marginTop: 10,
    borderWidth: 1,
    borderColor: 'rgba(37,211,102,0.25)',
  },
  waBtnText: {
    fontSize: 15,
    fontWeight: '700',
    color: '#25D366',
    letterSpacing: 0.2,
  },
  cancelBtn: {
    alignItems: 'center',
    paddingVertical: 16,
    marginTop: 4,
  },
  cancelBtnText: {
    fontSize: 14,
    color: 'rgba(255,255,255,0.38)',
    fontWeight: '500',
  },

  // ── Success modal
  successOverlay: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 28,
    zIndex: 100,
  },
  successCard: {
    width: '100%',
    backgroundColor: 'rgba(255,255,255,0.15)',
    borderRadius: 28,
    borderWidth: 1,
    borderColor: 'rgba(34,197,94,0.18)',
    paddingHorizontal: 28,
    paddingTop: 40,
    paddingBottom: 32,
    alignItems: 'center',
    shadowColor: '#22c55e',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.18,
    shadowRadius: 28,
    elevation: 20,
  },
  successCircle: {
    width: 96,
    height: 96,
    borderRadius: 48,
    backgroundColor: '#22c55e',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 28,
    shadowColor: '#22c55e',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.5,
    shadowRadius: 18,
    elevation: 12,
  },
  successRing: {
    position: 'absolute',
    width: 116,
    height: 116,
    borderRadius: 58,
    borderWidth: 2,
    borderColor: 'rgba(34,197,94,0.28)',
  },
  successTitle: {
    fontSize: 22,
    fontWeight: '800',
    color: '#ffffff',
    textAlign: 'center',
    marginBottom: 14,
    letterSpacing: 0.2,
  },
  successSubtitle: {
    fontSize: 14,
    color: 'rgba(255,255,255,0.6)',
    textAlign: 'center',
    lineHeight: 22,
    marginBottom: 32,
  },
  successBtn: {
    width: '100%',
    backgroundColor: '#22c55e',
    borderRadius: 14,
    paddingVertical: 16,
    alignItems: 'center',
    shadowColor: '#22c55e',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.35,
    shadowRadius: 10,
    elevation: 8,
  },
  successBtnText: {
    fontSize: 16,
    fontWeight: '800',
    color: '#ffffff',
    letterSpacing: 0.3,
  },
});
