import React, { useState } from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  Alert,
  Image,
  TouchableOpacity,
} from 'react-native';
import { Button, Text, Card, IconButton, ActivityIndicator } from 'react-native-paper';
import * as ImagePicker from 'expo-image-picker';
import * as DocumentPicker from 'expo-document-picker';
import { useNavigation } from '@react-navigation/native';
import axios from 'axios';
import { Colors } from '../constants/colors';
import { API_CONFIG } from '../constants/config';
import { useAuth } from '../contexts/AuthContext';
import { GlobalStyles } from '../styles/globalStyles';

export const VerifyIdentityScreen = () => {
  const navigation = useNavigation();
  const { client, refreshClient } = useAuth();

  const [frontImage, setFrontImage] = useState<string | null>(null);
  const [backImage, setBackImage] = useState<string | null>(null);
  const [rucDocument, setRucDocument] = useState<{ uri: string; name: string; type: string } | null>(null);
  const [uploading, setUploading] = useState(false);

  // Verificar si es persona jurídica
  const isLegalEntity = client?.document_type === 'RUC';

  const requestPermissions = async () => {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert(
        'Permisos Requeridos',
        'Necesitamos acceso a tu galería para subir las fotos de tu DNI.'
      );
      return false;
    }
    return true;
  };

  const pickImage = async (side: 'front' | 'back') => {
    const hasPermission = await requestPermissions();
    if (!hasPermission) return;

    try {
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsEditing: true,
        aspect: [4, 3],
        quality: 0.8,
      });

      if (!result.canceled && result.assets[0]) {
        if (side === 'front') {
          setFrontImage(result.assets[0].uri);
        } else {
          setBackImage(result.assets[0].uri);
        }
      }
    } catch (error) {
      console.error('Error picking image:', error);
      Alert.alert('Error', 'No se pudo seleccionar la imagen');
    }
  };

  const takePhoto = async (side: 'front' | 'back') => {
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert(
        'Permisos Requeridos',
        'Necesitamos acceso a tu cámara para tomar fotos de tu DNI.'
      );
      return;
    }

    try {
      const result = await ImagePicker.launchCameraAsync({
        allowsEditing: true,
        aspect: [4, 3],
        quality: 0.8,
      });

      if (!result.canceled && result.assets[0]) {
        if (side === 'front') {
          setFrontImage(result.assets[0].uri);
        } else {
          setBackImage(result.assets[0].uri);
        }
      }
    } catch (error) {
      console.error('Error taking photo:', error);
      Alert.alert('Error', 'No se pudo tomar la foto');
    }
  };

  const showImageOptions = (side: 'front' | 'back') => {
    const docType = isLegalEntity ? 'DNI del Representante Legal' : 'DNI';
    Alert.alert(
      `${docType} - ${side === 'front' ? 'Anverso' : 'Reverso'}`,
      'Selecciona una opción',
      [
        {
          text: 'Tomar Foto',
          onPress: () => takePhoto(side),
        },
        {
          text: 'Elegir de Galería',
          onPress: () => pickImage(side),
        },
        {
          text: 'Cancelar',
          style: 'cancel',
        },
      ]
    );
  };

  const pickRucDocument = async () => {
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: ['image/*', 'application/pdf'],
        copyToCacheDirectory: true,
      });

      if (!result.canceled && result.assets[0]) {
        const file = result.assets[0];
        setRucDocument({
          uri: file.uri,
          name: file.name,
          type: file.mimeType || 'application/pdf',
        });
      }
    } catch (error) {
      console.error('Error picking RUC document:', error);
      Alert.alert('Error', 'No se pudo seleccionar el documento');
    }
  };

  const handleSubmit = async () => {
    if (!frontImage || !backImage) {
      const docType = isLegalEntity ? 'DNI del representante legal' : 'DNI';
      Alert.alert(
        'Faltan Imágenes',
        `Por favor adjunta ambas fotos de tu ${docType} (anverso y reverso)`
      );
      return;
    }

    // Validar Ficha RUC para persona jurídica
    if (isLegalEntity && !rucDocument) {
      Alert.alert(
        'Falta Ficha RUC',
        'Por favor adjunta la Ficha RUC (imagen o PDF)'
      );
      return;
    }

    try {
      setUploading(true);

      const formData = new FormData();
      formData.append('dni', client?.dni || '');

      // Agregar imagen del anverso
      formData.append('dni_front', {
        uri: frontImage,
        type: 'image/jpeg',
        name: `dni_front_${client?.dni}.jpg`,
      } as any);

      // Agregar imagen del reverso
      formData.append('dni_back', {
        uri: backImage,
        type: 'image/jpeg',
        name: `dni_back_${client?.dni}.jpg`,
      } as any);

      // Agregar Ficha RUC si es persona jurídica
      if (isLegalEntity && rucDocument) {
        formData.append('ruc_ficha', {
          uri: rucDocument.uri,
          type: rucDocument.type,
          name: rucDocument.name,
        } as any);
      }

      const response = await axios.post(
        `${API_CONFIG.BASE_URL}/api/client/upload-dni`,
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        }
      );

      if (response.data.success) {
        Alert.alert(
          '✅ Documentos Enviados',
          'Tus documentos han sido enviados exitosamente. Nuestro equipo los revisará pronto.',
          [
            {
              text: 'OK',
              onPress: async () => {
                // Refrescar datos del cliente
                try {
                  await refreshClient();
                } catch (error) {
                  console.error('Error refreshing client:', error);
                }
                navigation.goBack();
              },
            },
          ]
        );
      } else {
        Alert.alert('Error', response.data.message || 'Error al subir documentos');
      }
    } catch (error: any) {
      console.error('Error uploading documents:', error);
      Alert.alert(
        'Error',
        error.response?.data?.message || 'Error al subir documentos'
      );
    } finally {
      setUploading(false);
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Text variant="headlineSmall" style={styles.title}>
          Validación de Identidad
        </Text>
        <Text variant="bodyMedium" style={styles.subtitle}>
          Para realizar tu primera operación, necesitamos validar tu identidad
        </Text>
      </View>

      <Card style={styles.infoCard}>
        <Card.Content>
          <Text variant="bodyMedium" style={styles.infoText}>
            {isLegalEntity
              ? '📸 Por favor, adjunta los siguientes documentos:'
              : '📸 Por favor, adjunta fotos claras de ambos lados de tu DNI'}
          </Text>
          <Text variant="bodySmall" style={styles.infoSubtext}>
            {isLegalEntity
              ? '• DNI del representante legal (anverso y reverso)\n• Ficha RUC (imagen o PDF)\n• Asegúrate de que toda la información sea legible\n• Las fotos deben estar bien iluminadas'
              : '• Asegúrate de que toda la información sea legible\n• La foto debe estar bien iluminada\n• No uses flash directo para evitar reflejos'}
          </Text>
        </Card.Content>
      </Card>

      {/* DNI Anverso */}
      <Card style={styles.imageCard}>
        <Card.Content>
          <View style={styles.cardHeader}>
            <Text variant="titleMedium" style={styles.cardTitle}>
              {isLegalEntity ? 'DNI Representante Legal - Anverso' : 'DNI - Anverso (Frente)'}
            </Text>
            {frontImage && (
              <IconButton
                icon="close-circle"
                size={24}
                onPress={() => setFrontImage(null)}
              />
            )}
          </View>

          {frontImage ? (
            <TouchableOpacity onPress={() => showImageOptions('front')}>
              <Image source={{ uri: frontImage }} style={styles.previewImage} />
            </TouchableOpacity>
          ) : (
            <TouchableOpacity
              style={styles.uploadButton}
              onPress={() => showImageOptions('front')}
            >
              <IconButton icon="camera-plus" size={48} iconColor={Colors.primary} />
              <Text variant="bodyMedium" style={styles.uploadText}>
                Toca para agregar foto del anverso
              </Text>
            </TouchableOpacity>
          )}
        </Card.Content>
      </Card>

      {/* DNI Reverso */}
      <Card style={styles.imageCard}>
        <Card.Content>
          <View style={styles.cardHeader}>
            <Text variant="titleMedium" style={styles.cardTitle}>
              {isLegalEntity ? 'DNI Representante Legal - Reverso' : 'DNI - Reverso (Atrás)'}
            </Text>
            {backImage && (
              <IconButton
                icon="close-circle"
                size={24}
                onPress={() => setBackImage(null)}
              />
            )}
          </View>

          {backImage ? (
            <TouchableOpacity onPress={() => showImageOptions('back')}>
              <Image source={{ uri: backImage }} style={styles.previewImage} />
            </TouchableOpacity>
          ) : (
            <TouchableOpacity
              style={styles.uploadButton}
              onPress={() => showImageOptions('back')}
            >
              <IconButton icon="camera-plus" size={48} iconColor={Colors.primary} />
              <Text variant="bodyMedium" style={styles.uploadText}>
                Toca para agregar foto del reverso
              </Text>
            </TouchableOpacity>
          )}
        </Card.Content>
      </Card>

      {/* Ficha RUC - Solo para Persona Jurídica */}
      {isLegalEntity && (
        <Card style={styles.imageCard}>
          <Card.Content>
            <View style={styles.cardHeader}>
              <Text variant="titleMedium" style={styles.cardTitle}>
                Ficha RUC
              </Text>
              {rucDocument && (
                <IconButton
                  icon="close-circle"
                  size={24}
                  onPress={() => setRucDocument(null)}
                />
              )}
            </View>

            {rucDocument ? (
              <TouchableOpacity onPress={pickRucDocument}>
                {rucDocument.type.includes('pdf') ? (
                  <View style={styles.documentPreview}>
                    <IconButton icon="file-pdf-box" size={64} iconColor={Colors.error} />
                    <Text variant="bodyMedium" style={styles.documentName}>
                      {rucDocument.name}
                    </Text>
                  </View>
                ) : (
                  <Image source={{ uri: rucDocument.uri }} style={styles.previewImage} />
                )}
              </TouchableOpacity>
            ) : (
              <TouchableOpacity
                style={styles.uploadButton}
                onPress={pickRucDocument}
              >
                <IconButton icon="file-upload" size={48} iconColor={Colors.primary} />
                <Text variant="bodyMedium" style={styles.uploadText}>
                  Toca para adjuntar Ficha RUC{'\n'}(Imagen o PDF)
                </Text>
              </TouchableOpacity>
            )}
          </Card.Content>
        </Card>
      )}

      <Button
        mode="contained"
        onPress={handleSubmit}
        disabled={
          !frontImage ||
          !backImage ||
          (isLegalEntity && !rucDocument) ||
          uploading
        }
        loading={uploading}
        style={styles.submitButton}
        buttonColor={Colors.primary}
      >
        {uploading ? 'Enviando...' : 'Enviar Documentos'}
      </Button>

      <Button
        mode="text"
        onPress={() => navigation.goBack()}
        disabled={uploading}
        style={styles.cancelButton}
      >
        Cancelar
      </Button>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  content: {
    padding: 16,
  },
  header: {
    marginBottom: 24,
  },
  title: {
    fontWeight: '600',
    color: Colors.textDark,
    marginBottom: 8,
  },
  subtitle: {
    color: Colors.textLight,
  },
  infoCard: {
    marginBottom: 24,
    backgroundColor: Colors.primaryLight,
    borderLeftWidth: 4,
    borderLeftColor: Colors.primary,
  },
  infoText: {
    color: Colors.primaryDark,
    marginBottom: 8,
    fontWeight: '600',
  },
  infoSubtext: {
    color: Colors.primaryDark,
    fontSize: 12,
  },
  imageCard: {
    marginBottom: 16,
    backgroundColor: Colors.surface,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  cardTitle: {
    fontWeight: '600',
    color: Colors.textDark,
  },
  uploadButton: {
    borderWidth: 2,
    borderColor: Colors.primary,
    borderStyle: 'dashed',
    borderRadius: 12,
    padding: 32,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.primaryLight,
  },
  uploadText: {
    color: Colors.primary,
    textAlign: 'center',
  },
  previewImage: {
    width: '100%',
    height: 200,
    borderRadius: 12,
    resizeMode: 'contain',
  },
  documentPreview: {
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
    backgroundColor: Colors.primaryLight,
    borderRadius: 12,
  },
  documentName: {
    color: Colors.primary,
    textAlign: 'center',
    marginTop: 8,
    fontWeight: '600',
  },
  submitButton: {
    marginTop: 24,
    paddingVertical: 8,
  },
  cancelButton: {
    marginTop: 12,
  },
});
