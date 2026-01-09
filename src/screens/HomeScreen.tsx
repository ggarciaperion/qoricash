import React, { useState } from 'react';
import { View, StyleSheet, ScrollView, RefreshControl, Image, TouchableOpacity, Alert, SafeAreaView } from 'react-native';
import { Text, Card, Icon, Button } from 'react-native-paper';
import { useAuth } from '../contexts/AuthContext';
import { Colors } from '../constants/colors';
import { Calculator } from '../components/Calculator';
import { GlobalStyles } from '../styles/globalStyles';

interface HomeScreenProps {
  navigation: any;
}

export const HomeScreen: React.FC<HomeScreenProps> = ({ navigation }) => {
  const { client, refreshClient } = useAuth();
  const [refreshing, setRefreshing] = useState(false);

  const onRefresh = async () => {
    setRefreshing(true);
    await refreshClient();
    setRefreshing(false);
  };

  const handleInitiateOperation = (
    operationType: 'Compra' | 'Venta',
    amountUSD: string,
    exchangeRate: number
  ) => {
    // Verificar si el cliente tiene documentos completos
    if (!client?.has_complete_documents) {
      Alert.alert(
        'Validación de Identidad Requerida',
        'Necesitamos validar tu DNI antes de iniciar una operación.\n\nPor favor, sube las fotos de tu DNI usando el botón "Validar Identidad".',
        [{ text: 'Entendido' }]
      );
      return;
    }

    navigation.navigate('NewOperation', {
      operationType,
      amountUSD,
      exchangeRate,
    });
  };

  if (!client) {
    return (
      <View style={GlobalStyles.container}>
        <Text>Cargando...</Text>
      </View>
    );
  }

  return (
    <SafeAreaView style={{ flex: 1, paddingTop: 20 }}>
      <ScrollView
        style={GlobalStyles.container}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
    >
      {/* Header con Logo y Nombre de la Marca */}
      <View style={styles.header}>
        <Image
          source={require('../../assets/logo-principal.png')}
          style={styles.headerLogo}
          resizeMode="contain"
        />
        <Text style={GlobalStyles.title}>QoriCash</Text>
      </View>

      {/* Compact User Info */}
      <Card style={styles.userCard}>
        <Card.Content style={styles.userContent}>
          <View style={styles.userRow}>
            <View style={styles.userInfo}>
              <Text variant="titleMedium" style={styles.userName}>
                {client.full_name}
              </Text>
              <Text variant="bodySmall" style={styles.userDetail}>
                DNI: {client.dni} • {client.email}
              </Text>
            </View>
            <View style={styles.statusChip}>
              <Icon source="check-circle" size={16} color="#FFFFFF" />
              <Text style={styles.statusChipText}>{client.status}</Text>
            </View>
          </View>
        </Card.Content>
      </Card>

      {/* Banner de Validación de Identidad */}
      {!client.has_complete_documents && (
        <>
          {/* Documentos NO enviados - Validación Pendiente */}
          {(!client.dni_front_url || !client.dni_back_url) && (
            <Card style={styles.verificationBanner}>
              <Card.Content>
                <View style={styles.bannerHeader}>
                  <Icon source="alert-circle" size={24} color={Colors.warning} />
                  <Text variant="titleMedium" style={styles.bannerTitle}>
                    Validación Pendiente
                  </Text>
                </View>
                <Text variant="bodyMedium" style={styles.bannerText}>
                  Necesitamos validar tu información antes de tu primera operación.
                </Text>
                <Text variant="bodySmall" style={styles.bannerSubtext}>
                  Por favor, adjunta fotos de ambos lados de tu DNI para continuar.
                </Text>
                <Button
                  mode="contained"
                  icon="camera-plus"
                  onPress={() => navigation.navigate('VerifyIdentity')}
                  style={styles.verifyButton}
                  buttonColor={Colors.primary}
                >
                  Validar Identidad
                </Button>
              </Card.Content>
            </Card>
          )}

          {/* Documentos enviados - En Proceso de Revisión */}
          {client.dni_front_url && client.dni_back_url && (
            <Card style={styles.processingBanner}>
              <Card.Content>
                <View style={styles.bannerHeader}>
                  <Icon source="clock-outline" size={24} color={Colors.info} />
                  <Text variant="titleMedium" style={styles.processingTitle}>
                    Validación en Proceso
                  </Text>
                </View>
                <Text variant="bodyMedium" style={styles.processingText}>
                  Tus documentos están siendo revisados por nuestro equipo.
                </Text>
                <Text variant="bodySmall" style={styles.processingSubtext}>
                  ⏱️ Tiempo promedio de respuesta: 10 minutos
                </Text>
                <Text variant="bodySmall" style={styles.processingInfo}>
                  Te notificaremos cuando tu cuenta sea activada.
                </Text>
              </Card.Content>
            </Card>
          )}
        </>
      )}

      {/* Calculator Component */}
      <Card style={styles.calculatorCard}>
        <Card.Content>
          <Calculator
            onOperationReady={handleInitiateOperation}
            showInitiateButton={true}
          />
        </Card.Content>
      </Card>
    </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  // Usar GlobalStyles.container
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingTop: 20,
    paddingBottom: 16,
    backgroundColor: Colors.background,
  },
  headerLogo: {
    width: 70,
    height: 70,
    marginRight: 12,
  },
  // Usar GlobalStyles.title
  userCard: {
    margin: 16,
    marginTop: 8,
    marginBottom: 8,
    backgroundColor: Colors.surface,
  },
  userContent: {
    paddingVertical: 8,
  },
  userRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  userInfo: {
    flex: 1,
  },
  userName: {
    fontWeight: 'bold',
    marginBottom: 4,
    color: Colors.textDark,
  },
  userDetail: {
    color: Colors.textLight,
    fontSize: 12,
  },
  statusChip: {
    marginLeft: 8,
    height: 32,
    backgroundColor: '#82C16C',
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    borderRadius: 16,
    gap: 6,
  },
  statusChipText: {
    color: '#FFFFFF',
    fontWeight: '600',
    fontSize: 13,
  },
  verificationBanner: {
    marginHorizontal: 16,
    marginVertical: 8,
    backgroundColor: '#FFF3E0',
    borderLeftWidth: 4,
    borderLeftColor: Colors.warning,
  },
  bannerHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
    gap: 8,
  },
  bannerTitle: {
    fontWeight: '700',
    color: Colors.warningDark,
  },
  bannerText: {
    color: Colors.warningDark,
    marginBottom: 8,
    fontWeight: '600',
  },
  bannerSubtext: {
    color: Colors.warningDark,
    marginBottom: 16,
    opacity: 0.8,
  },
  verifyButton: {
    marginTop: 8,
  },
  processingBanner: {
    marginHorizontal: 16,
    marginVertical: 8,
    backgroundColor: '#E3F2FD',
    borderLeftWidth: 4,
    borderLeftColor: Colors.info,
  },
  processingTitle: {
    fontWeight: '700',
    color: Colors.infoDark,
  },
  processingText: {
    color: Colors.infoDark,
    marginBottom: 8,
    fontWeight: '600',
  },
  processingSubtext: {
    color: Colors.infoDark,
    marginBottom: 4,
    opacity: 0.9,
  },
  processingInfo: {
    color: Colors.infoDark,
    marginTop: 4,
    opacity: 0.8,
    fontStyle: 'italic',
  },
  calculatorCard: {
    marginHorizontal: 16,
    marginBottom: 24,
    backgroundColor: Colors.surface,
  },
});
