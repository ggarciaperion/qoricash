import React from 'react';
import { View, StyleSheet, TouchableOpacity, Image } from 'react-native';
import { Text } from 'react-native-paper';
import { useNavigation } from '@react-navigation/native';
import { LinearGradient } from 'expo-linear-gradient';
import { Colors } from '../constants/colors';

export const ClientTypeSelectionScreen = () => {
  const navigation = useNavigation();

  const handleSelectPersonaNatural = () => {
    navigation.navigate('Register' as never, { tipoPersona: 'Natural' } as never);
  };

  const handleSelectPersonaJuridica = () => {
    navigation.navigate('Register' as never, { tipoPersona: 'Jurídica' } as never);
  };

  return (
    <View style={styles.container}>
      {/* Logo */}
      <View style={styles.logoContainer}>
        <Image
          source={require('../../assets/logo-principal.png')}
          style={styles.logo}
          resizeMode="contain"
        />
        <Text variant="headlineLarge" style={styles.brandName}>
          QoriCash
        </Text>
      </View>

      {/* Title */}
      <Text variant="headlineSmall" style={styles.title}>
        Elegir tipo de cliente
      </Text>
      <Text variant="bodyMedium" style={styles.subtitle}>
        Selecciona el tipo de cuenta que deseas crear
      </Text>

      {/* Options */}
      <View style={styles.optionsContainer}>
        {/* Persona Natural */}
        <TouchableOpacity
          onPress={handleSelectPersonaNatural}
          activeOpacity={0.8}
          style={styles.optionButton}
        >
          <LinearGradient
            colors={['#10B981', '#059669']}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 1 }}
            style={styles.optionGradient}
          >
            <View style={styles.iconContainer}>
              <Text style={styles.iconText}>👤</Text>
            </View>
            <Text variant="titleLarge" style={styles.optionTitle}>
              Persona Natural
            </Text>
            <Text variant="bodyMedium" style={styles.optionDescription}>
              Para personas individuales con DNI o Carnet de Extranjería
            </Text>
          </LinearGradient>
        </TouchableOpacity>

        {/* Persona Jurídica */}
        <TouchableOpacity
          onPress={handleSelectPersonaJuridica}
          activeOpacity={0.8}
          style={styles.optionButton}
        >
          <LinearGradient
            colors={['#3B82F6', '#2563EB']}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 1 }}
            style={styles.optionGradient}
          >
            <View style={styles.iconContainer}>
              <Text style={styles.iconText}>🏢</Text>
            </View>
            <Text variant="titleLarge" style={styles.optionTitle}>
              Persona Jurídica
            </Text>
            <Text variant="bodyMedium" style={styles.optionDescription}>
              Para empresas o negocios con RUC
            </Text>
          </LinearGradient>
        </TouchableOpacity>
      </View>

      {/* Back button */}
      <TouchableOpacity
        onPress={() => navigation.goBack()}
        style={styles.backButton}
      >
        <Text style={styles.backButtonText}>Volver al inicio</Text>
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
    padding: 24,
    paddingTop: 60,
    justifyContent: 'center',
  },
  logoContainer: {
    alignItems: 'center',
    marginBottom: 32,
  },
  logo: {
    width: 80,
    height: 80,
    marginBottom: 8,
  },
  brandName: {
    fontSize: 28,
    fontWeight: '800',
    color: '#000000',
    letterSpacing: -1,
  },
  title: {
    marginBottom: 8,
    fontWeight: '700',
    textAlign: 'center',
    color: Colors.textDark,
  },
  subtitle: {
    marginBottom: 32,
    textAlign: 'center',
    color: Colors.textLight,
  },
  optionsContainer: {
    gap: 16,
  },
  optionButton: {
    borderRadius: 16,
    overflow: 'hidden',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 12,
    elevation: 8,
  },
  optionGradient: {
    padding: 20,
    alignItems: 'center',
    minHeight: 160,
    justifyContent: 'center',
  },
  iconContainer: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: 'rgba(255, 255, 255, 0.2)',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 12,
  },
  iconText: {
    fontSize: 36,
  },
  optionTitle: {
    color: '#FFFFFF',
    fontWeight: '700',
    marginBottom: 6,
    textAlign: 'center',
  },
  optionDescription: {
    color: 'rgba(255, 255, 255, 0.9)',
    textAlign: 'center',
    paddingHorizontal: 12,
    fontSize: 13,
  },
  backButton: {
    marginTop: 24,
    padding: 12,
    alignItems: 'center',
  },
  backButtonText: {
    color: Colors.primary,
    fontSize: 15,
    fontWeight: '600',
  },
});
