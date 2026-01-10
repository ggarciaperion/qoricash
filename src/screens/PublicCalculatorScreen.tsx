import React, { useState } from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  Image,
  TouchableOpacity,
  RefreshControl,
} from 'react-native';
import { Text } from 'react-native-paper';
import { Colors } from '../constants/colors';
import { GlobalStyles } from '../styles/globalStyles';
import { Calculator } from '../components/Calculator';

interface PublicCalculatorScreenProps {
  navigation: any;
}

export const PublicCalculatorScreen: React.FC<PublicCalculatorScreenProps> = ({ navigation }) => {
  const [refreshing, setRefreshing] = useState(false);

  const onRefresh = async () => {
    setRefreshing(true);
    // La calculadora se actualiza internamente
    setTimeout(() => setRefreshing(false), 500);
  };

  const handleStartOperation = () => {
    navigation.navigate('Login');
  };

  const handleLogin = () => {
    navigation.navigate('Login');
  };

  return (
    <View style={[GlobalStyles.container, { backgroundColor: Colors.background }]}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        showsVerticalScrollIndicator={false}
      >
        {/* Header con Logo y Nombre */}
        <View style={styles.header}>
          <Image
            source={require('../../assets/logo-principal.png')}
            style={styles.headerLogo}
            resizeMode="contain"
          />
          <Text style={styles.brandName}>QoriCash</Text>
        </View>

        {/* Calculator Component */}
        <Calculator
          showHeader={true}
          showContinueButton={true}
          onOperationReady={handleStartOperation}
        />

        {/* Espaciador */}
        <View style={styles.spacer} />

        {/* Call to Action al final */}
        <TouchableOpacity
          style={styles.loginLink}
          onPress={handleLogin}
          activeOpacity={0.8}
        >
          <Text style={styles.loginLinkText}>¡Inicia sesión o regístrate!</Text>
        </TouchableOpacity>
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  scrollContent: {
    flexGrow: 1,
    justifyContent: 'center',
    padding: 24,
    paddingTop: 100, // Add top padding to prevent logo from being cut off
    paddingBottom: 40,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 32,
  },
  headerLogo: {
    width: 90,
    height: 90,
    marginRight: 16,
  },
  brandName: {
    fontSize: 42,
    fontWeight: '800',
    color: '#000000',
    letterSpacing: -1,
  },
  spacer: {
    flex: 1,
    minHeight: 40,
  },
  loginLink: {
    alignItems: 'center',
    paddingVertical: 16,
    marginHorizontal: 24,
  },
  loginLinkText: {
    fontSize: 16,
    fontWeight: '600',
    color: Colors.textDark,
    textAlign: 'center',
  },
});
