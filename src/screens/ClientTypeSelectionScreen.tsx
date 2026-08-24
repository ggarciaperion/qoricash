import React from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

export const ClientTypeSelectionScreen = () => {
  const navigation = useNavigation<any>();
  const insets = useSafeAreaInsets();

  return (
    <View style={s.root}>
      {/* Body */}
      <View style={s.body}>

        {/* Title */}
        <TouchableOpacity style={[s.backBtn, { top: insets.top + 16 }]} onPress={() => navigation.goBack()} activeOpacity={0.8}>
          <Ionicons name="chevron-back" size={22} color="#ffffff" />
        </TouchableOpacity>

        <Text style={s.title}>
          <Text style={s.titleWhite}>Crear </Text>
          <Text style={s.titleGreen}>Cuenta</Text>
        </Text>

        {/* Subtitle */}
        <Text style={s.subtitle}>Únete a QoriCash en 3 simples pasos</Text>

        {/* Section label */}
        <Text style={s.sectionLabel}>Elige el tipo de cliente</Text>

        {/* Cards row */}
        <View style={s.row}>

          {/* Persona Natural */}
          <TouchableOpacity
            style={s.cardWrap}
            activeOpacity={0.8}
            onPress={() => navigation.navigate('Register', { tipoPersona: 'Natural' })}
          >
            <View style={s.card}>
              <View style={s.iconCircle}>
                <Ionicons name="person-outline" size={28} color="#22c55e" />
              </View>
              <Text style={s.cardTitle}>Persona Natural</Text>
              <Text style={s.cardDesc}>DNI · Carnet de{'\n'}Extranjería</Text>
            </View>
          </TouchableOpacity>

          {/* Empresa */}
          <TouchableOpacity
            style={s.cardWrap}
            activeOpacity={0.8}
            onPress={() => navigation.navigate('Register', { tipoPersona: 'Jurídica' })}
          >
            <View style={s.card}>
              <View style={s.iconCircle}>
                <Ionicons name="receipt-outline" size={28} color="#22c55e" />
              </View>
              <Text style={s.cardTitle}>Empresa</Text>
              <Text style={s.cardDesc}>{'Ficha RUC'}</Text>
            </View>
          </TouchableOpacity>

        </View>
      </View>

      {/* Bottom — ya tienes cuenta */}
      <View style={s.bottomRow}>
        <Text style={s.topText}>¿Ya tienes cuenta? </Text>
        <TouchableOpacity onPress={() => navigation.navigate('Login')} activeOpacity={0.8}>
          <Text style={s.topLink}>Inicia sesión</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
};

const s = StyleSheet.create({
  root: {
    flex: 1,
  },
  bottomRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Platform.OS === 'ios' ? 100 : 80,
  },
  topText: {
    color: 'rgba(255,255,255,0.85)',
    fontSize: 13,
    fontWeight: '500',
  },
  topLink: {
    color: '#22c55e',
    fontSize: 13,
    fontWeight: '700',
  },
  backBtn: {
    position: 'absolute',
    left: 20,
    zIndex: 10,
    padding: 4,
  },
  body: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 24,
    paddingTop: 80,
  },
  title: {
    fontSize: 38,
    fontWeight: '800',
    textAlign: 'center',
    marginBottom: 10,
  },
  titleWhite: {
    color: '#ffffff',
  },
  titleGreen: {
    color: '#22c55e',
  },
  subtitle: {
    fontSize: 15,
    color: 'rgba(255,255,255,0.85)',
    textAlign: 'center',
    marginBottom: 28,
    fontWeight: '400',
  },
  sectionLabel: {
    fontSize: 17,
    fontWeight: '700',
    color: '#ffffff',
    textAlign: 'center',
    marginBottom: 20,
  },
  row: {
    flexDirection: 'row',
    gap: 14,
    width: '100%',
  },
  cardWrap: {
    flex: 1,
    borderRadius: 18,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.45)',
  },
  card: {
    height: 170,
    paddingHorizontal: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  iconCircle: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: 'rgba(34,197,94,0.2)',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 14,
  },
  cardTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: '#ffffff',
    textAlign: 'center',
    marginBottom: 6,
  },
  cardDesc: {
    fontSize: 12,
    color: 'rgba(255,255,255,0.65)',
    textAlign: 'center',
    lineHeight: 17,
  },
});
