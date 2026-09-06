import React, { useState, useRef, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Alert,
  Image,
  TouchableOpacity,
  Linking,
  Animated,
  Easing,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import * as DocumentPicker from 'expo-document-picker';
import { useNavigation } from '@react-navigation/native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import axios from 'axios';
import { API_CONFIG } from '../constants/config';
import { useAuth } from '../contexts/AuthContext';
import { DocsLoadingOverlay } from '../components/DocsLoadingOverlay';

export const VerifyIdentityScreen = () => {
  const navigation = useNavigation();
  const insets = useSafeAreaInsets();
  const { client, refreshClient } = useAuth();

  const [frontImage, setFrontImage]   = useState<string | null>(null);
  const [backImage, setBackImage]     = useState<string | null>(null);
  const [rucDocument, setRucDocument] = useState<{ uri: string; name: string; type: string } | null>(null);
  const [showDocsLoading, setShowDocsLoading] = useState(false);

  const isLegalEntity = client?.document_type === 'RUC';

  // ── Entrance animations ────────────────────────────────────────────────────
  const card1Anim = useRef(new Animated.Value(0)).current;
  const card2Anim = useRef(new Animated.Value(0)).current;
  const card3Anim = useRef(new Animated.Value(0)).current;
  const btnAnim   = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.stagger(70, [card1Anim, card2Anim, card3Anim, btnAnim].map(a =>
      Animated.spring(a, { toValue: 1, tension: 200, friction: 18, useNativeDriver: true })
    )).start();
  }, []);

  const animStyle = (anim: Animated.Value) => ({
    opacity: anim,
    transform: [{
      translateY: anim.interpolate({ inputRange: [0, 1], outputRange: [22, 0] }),
    }],
  });

  // ── Pulse del dot de estado ───────────────────────────────────────────────
  const dotScale   = useRef(new Animated.Value(1)).current;
  const dotOpacity = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    Animated.loop(
      Animated.sequence([
        Animated.parallel([
          Animated.timing(dotScale,   { toValue: 1.7,  duration: 700, easing: Easing.out(Easing.ease),    useNativeDriver: true }),
          Animated.timing(dotOpacity, { toValue: 0,    duration: 700, easing: Easing.out(Easing.ease),    useNativeDriver: true }),
        ]),
        Animated.parallel([
          Animated.timing(dotScale,   { toValue: 1,    duration: 0,   useNativeDriver: true }),
          Animated.timing(dotOpacity, { toValue: 1,    duration: 0,   useNativeDriver: true }),
        ]),
        Animated.delay(400),
      ])
    ).start();
  }, []);

  // ── Pulse for upload zones ─────────────────────────────────────────────────
  const pulseFront = useRef(new Animated.Value(1)).current;
  const pulseBack  = useRef(new Animated.Value(1)).current;
  const pulseRuc   = useRef(new Animated.Value(1)).current;

  const startPulse = (anim: Animated.Value) => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(anim, { toValue: 1.02, duration: 950, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
        Animated.timing(anim, { toValue: 1,    duration: 950, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
      ])
    ).start();
  };

  useEffect(() => { startPulse(pulseFront); }, []);
  useEffect(() => { startPulse(pulseBack);  }, []);
  useEffect(() => { startPulse(pulseRuc);   }, []);

  // ── Animation complete → navigate home ────────────────────────────────────
  const handleAnimationComplete = async () => {
    setShowDocsLoading(false);
    try { await refreshClient(); } catch {}
    navigation.goBack();
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

    // Inicia animación de inmediato y llama la API en paralelo
    setShowDocsLoading(true);

    try {
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
      if (!response.data.success) {
        setShowDocsLoading(false);
        Alert.alert('Error', response.data.message || 'Error al subir documentos');
      }
      // Si success: la animación sigue su curso y onComplete navega al home
    } catch (error: any) {
      setShowDocsLoading(false);
      Alert.alert('Error', error.response?.data?.message || 'Error al subir documentos');
    }
  };

  const canSubmit = !showDocsLoading && (
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
        <Ionicons name={icon as any} size={14} color="#9CA3AF" />
        <Text style={s.cardLabel}>{label}</Text>
        {image && (
          <TouchableOpacity onPress={onClear} style={s.clearBtn} activeOpacity={0.7}>
            <Ionicons name="close-circle" size={18} color="#EF4444" />
          </TouchableOpacity>
        )}
      </View>

      {image ? (
        <TouchableOpacity onPress={onPress} activeOpacity={0.88} style={s.previewWrap}>
          <Image source={{ uri: image }} style={s.previewImage} resizeMode="cover" />
          <View style={s.previewBadge}>
            <Ionicons name="checkmark-circle" size={15} color="#FFFFFF" />
            <Text style={s.previewBadgeText}>Imagen cargada</Text>
          </View>
        </TouchableOpacity>
      ) : (
        <Animated.View style={{ transform: [{ scale: pulse }] }}>
          <TouchableOpacity onPress={onPress} activeOpacity={0.8} style={s.uploadZone}>
            <View style={s.uploadIconWrap}>
              <Ionicons name="camera-outline" size={26} color="#0D1117" />
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
    <View style={s.root}>

      {/* ── Header ──────────────────────────────────────────────────────── */}
      <View style={[s.fixedHeader, { paddingTop: insets.top + 8 }]}>
        <TouchableOpacity
          style={s.backBtn}
          onPress={() => navigation.goBack()}
          activeOpacity={0.8}
        >
          <Ionicons name="chevron-back" size={22} color="#0D1117" />
        </TouchableOpacity>
        <Text style={s.headerTitle}>Validación de Identidad</Text>
        <View style={s.headerRight} />
      </View>

      <ScrollView
        contentContainerStyle={[s.scroll, { paddingBottom: insets.bottom + 40 }]}
        showsVerticalScrollIndicator={false}
      >
        {/* ── Badge de estado ─────────────────────────────────────────── */}
        <Animated.View style={[s.statusBadge, animStyle(card1Anim)]}>
          <View style={s.statusDotWrap}>
            {/* Aro que se expande y desvanece */}
            <Animated.View style={[s.statusDotRing, { transform: [{ scale: dotScale }], opacity: dotOpacity }]} />
            {/* Punto sólido central */}
            <View style={s.statusDot} />
          </View>
          <Text style={s.statusText}>Pendiente de verificación</Text>
        </Animated.View>

        {/* ── DNI Anverso ─────────────────────────────────────────────── */}
        {!isLegalEntity && (
          <>
            <Animated.View style={animStyle(card1Anim)}>
              <View style={s.card}>
                <View style={s.cardHeader}>
                  <View style={s.cardIconWrap}>
                    <Ionicons name="card-outline" size={17} color="#0D1117" />
                  </View>
                  <View>
                    <Text style={s.cardTitle}>DNI — Anverso</Text>
                    <Text style={s.cardSubtitle}>Parte frontal del documento</Text>
                  </View>
                </View>
                <View style={s.divider} />
                <UploadZone
                  image={frontImage}
                  pulse={pulseFront}
                  onPress={() => showImageOptions('front')}
                  onClear={() => setFrontImage(null)}
                  label="Foto nítida y legible"
                  icon="image-outline"
                />
              </View>
            </Animated.View>

            {/* ── DNI Reverso ─────────────────────────────────────────── */}
            <Animated.View style={animStyle(card2Anim)}>
              <View style={s.card}>
                <View style={s.cardHeader}>
                  <View style={s.cardIconWrap}>
                    <Ionicons name="card-outline" size={17} color="#0D1117" />
                  </View>
                  <View>
                    <Text style={s.cardTitle}>DNI — Reverso</Text>
                    <Text style={s.cardSubtitle}>Parte posterior del documento</Text>
                  </View>
                </View>
                <View style={s.divider} />
                <UploadZone
                  image={backImage}
                  pulse={pulseBack}
                  onPress={() => showImageOptions('back')}
                  onClear={() => setBackImage(null)}
                  label="Foto nítida y legible"
                  icon="image-outline"
                />
              </View>
            </Animated.View>
          </>
        )}

        {/* ── Ficha RUC ─────────────────────────────────────────────────── */}
        {isLegalEntity && (
          <Animated.View style={animStyle(card3Anim)}>
            <View style={s.card}>
              <View style={s.cardHeader}>
                <View style={s.cardIconWrap}>
                  <Ionicons name="document-text-outline" size={17} color="#0D1117" />
                </View>
                <View>
                  <Text style={s.cardTitle}>Ficha RUC</Text>
                  <Text style={s.cardSubtitle}>Descárgala desde SUNAT</Text>
                </View>
              </View>
              <View style={s.divider} />

              <View style={s.cardSection}>
                <View style={s.cardLabelRow}>
                  <Ionicons name="attach-outline" size={14} color="#9CA3AF" />
                  <Text style={s.cardLabel}>Imagen o PDF de la Ficha RUC</Text>
                  {rucDocument && (
                    <TouchableOpacity onPress={() => setRucDocument(null)} style={s.clearBtn} activeOpacity={0.7}>
                      <Ionicons name="close-circle" size={18} color="#EF4444" />
                    </TouchableOpacity>
                  )}
                </View>

                {rucDocument ? (
                  <TouchableOpacity onPress={pickRucDocument} activeOpacity={0.88} style={s.previewWrap}>
                    {rucDocument.type.includes('pdf') ? (
                      <View style={s.pdfPreview}>
                        <View style={s.pdfIconWrap}>
                          <Ionicons name="document-text" size={32} color="#EF4444" />
                        </View>
                        <Text style={s.pdfName} numberOfLines={2}>{rucDocument.name}</Text>
                      </View>
                    ) : (
                      <Image source={{ uri: rucDocument.uri }} style={s.previewImage} resizeMode="cover" />
                    )}
                    <View style={s.previewBadge}>
                      <Ionicons name="checkmark-circle" size={15} color="#FFFFFF" />
                      <Text style={s.previewBadgeText}>Documento cargado</Text>
                    </View>
                  </TouchableOpacity>
                ) : (
                  <Animated.View style={{ transform: [{ scale: pulseRuc }] }}>
                    <TouchableOpacity onPress={pickRucDocument} activeOpacity={0.8} style={s.uploadZone}>
                      <View style={s.uploadIconWrap}>
                        <Ionicons name="cloud-upload-outline" size={26} color="#0D1117" />
                      </View>
                      <Text style={s.uploadZoneText}>Toca para adjuntar</Text>
                      <Text style={s.uploadZoneSub}>Imagen o PDF</Text>
                    </TouchableOpacity>
                  </Animated.View>
                )}
              </View>
            </View>
          </Animated.View>
        )}

        {/* ── Botones ──────────────────────────────────────────────────── */}
        <Animated.View style={animStyle(btnAnim)}>
          <TouchableOpacity
            style={[s.submitBtn, !canSubmit && s.submitBtnDisabled]}
            onPress={handleSubmit}
            disabled={!canSubmit}
            activeOpacity={0.85}
          >
            <Ionicons name="cloud-upload-outline" size={19} color="#ffffff" style={{ marginRight: 8 }} />
            <Text style={s.submitBtnText}>Enviar Documentos</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={s.waBtn}
            onPress={() => Linking.openURL('https://wa.me/51910624404?text=Hola,%20quiero%20enviar%20mis%20documentos%20para%20validar%20mi%20identidad')}
            activeOpacity={0.85}
          >
            <Ionicons name="logo-whatsapp" size={18} color="#16A34A" style={{ marginRight: 8 }} />
            <Text style={s.waBtnText}>Enviar por WhatsApp</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={s.cancelBtn}
            onPress={() => navigation.goBack()}
            disabled={showDocsLoading}
            activeOpacity={0.7}
          >
            <Text style={s.cancelBtnText}>Cancelar</Text>
          </TouchableOpacity>
        </Animated.View>

      </ScrollView>

      {/* ── Animación de envío (igual que login/logout) ──────────────── */}
      <DocsLoadingOverlay
        visible={showDocsLoading}
        onComplete={handleAnimationComplete}
      />

    </View>
  );
};

export default VerifyIdentityScreen;

const s = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: '#F5F7FA',
  },

  // ── Header
  fixedHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingBottom: 14,
    backgroundColor: '#F5F7FA',
    zIndex: 20,
  },
  backBtn: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: '#FFFFFF',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: 'rgba(0,0,0,0.08)',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 6,
    elevation: 2,
  },
  headerTitle: {
    flex: 1,
    textAlign: 'center',
    fontSize: 17,
    fontWeight: '700',
    color: '#0D1117',
    letterSpacing: 0.1,
  },
  headerRight: { width: 38 },

  // ── Scroll
  scroll: {
    paddingHorizontal: 20,
    paddingTop: 4,
  },

  // ── Status badge
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: 8,
    backgroundColor: '#2563EB',
    borderRadius: 100,
    paddingHorizontal: 14,
    paddingVertical: 8,
    marginBottom: 18,
  },
  statusDotWrap: {
    width: 10,
    height: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  statusDotRing: {
    position: 'absolute',
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: 'rgba(255,255,255,0.5)',
  },
  statusDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
    backgroundColor: '#FFFFFF',
  },
  statusText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#FFFFFF',
    letterSpacing: 0.2,
  },

  // ── Cards
  card: {
    backgroundColor: '#FFFFFF',
    borderRadius: 18,
    borderWidth: 1,
    borderColor: 'rgba(0,0,0,0.07)',
    marginBottom: 14,
    padding: 18,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginBottom: 14,
  },
  cardIconWrap: {
    width: 36,
    height: 36,
    borderRadius: 12,
    backgroundColor: '#F3F4F6',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: 'rgba(0,0,0,0.06)',
  },
  cardTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: '#0D1117',
    marginBottom: 2,
  },
  cardSubtitle: {
    fontSize: 12,
    color: '#9CA3AF',
    fontWeight: '400',
  },
  divider: {
    height: StyleSheet.hairlineWidth,
    backgroundColor: 'rgba(0,0,0,0.07)',
    marginBottom: 14,
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
    color: '#9CA3AF',
    flex: 1,
  },
  clearBtn: { padding: 2 },

  // ── Upload zone
  uploadZone: {
    borderWidth: 1.5,
    borderColor: 'rgba(0,0,0,0.10)',
    borderStyle: 'dashed',
    borderRadius: 14,
    paddingVertical: 28,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#F9FAFB',
    gap: 8,
  },
  uploadIconWrap: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: '#F3F4F6',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: 'rgba(0,0,0,0.07)',
    marginBottom: 4,
  },
  uploadZoneText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#0D1117',
  },
  uploadZoneSub: {
    fontSize: 12,
    color: '#9CA3AF',
  },

  // ── Preview
  previewWrap: {
    borderRadius: 12,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: 'rgba(0,0,0,0.08)',
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
    paddingVertical: 10,
    backgroundColor: '#0D1117',
  },
  previewBadgeText: {
    fontSize: 12,
    color: '#FFFFFF',
    fontWeight: '600',
  },

  // ── PDF preview
  pdfPreview: {
    paddingVertical: 24,
    alignItems: 'center',
    gap: 10,
    backgroundColor: '#FFF5F5',
  },
  pdfIconWrap: {
    width: 56,
    height: 56,
    borderRadius: 14,
    backgroundColor: '#FEE2E2',
    alignItems: 'center',
    justifyContent: 'center',
  },
  pdfName: {
    fontSize: 12,
    color: '#6B7280',
    textAlign: 'center',
    paddingHorizontal: 16,
  },

  // ── Submit button
  submitBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#0D1117',
    borderRadius: 16,
    paddingVertical: 17,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.18,
    shadowRadius: 14,
    elevation: 8,
  },
  submitBtnDisabled: {
    backgroundColor: '#E5E7EB',
    shadowOpacity: 0,
    elevation: 0,
  },
  submitBtnText: {
    fontSize: 16,
    fontWeight: '700',
    color: '#ffffff',
    letterSpacing: 0.2,
  },
  waBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    paddingVertical: 16,
    marginTop: 10,
    borderWidth: 1,
    borderColor: '#BBF7D0',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 6,
    elevation: 1,
  },
  waBtnText: {
    fontSize: 15,
    fontWeight: '600',
    color: '#16A34A',
    letterSpacing: 0.1,
  },
  cancelBtn: {
    alignItems: 'center',
    paddingVertical: 18,
  },
  cancelBtnText: {
    fontSize: 14,
    color: '#9CA3AF',
    fontWeight: '500',
  },

});
