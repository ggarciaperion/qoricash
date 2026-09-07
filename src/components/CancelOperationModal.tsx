import React, { useState, useRef } from 'react';
import {
  View, Text, StyleSheet, Modal, TextInput, TouchableOpacity,
  Animated, Easing, Platform, KeyboardAvoidingView,
} from 'react-native';
import { BlurView } from 'expo-blur';
import { Ionicons } from '@expo/vector-icons';
import apiClient from '../api/client';

const DIM = 'rgba(0,0,0,0.38)';

interface Props {
  visible: boolean;
  onClose: () => void;
  operationId: number;
  operationCode: string;
  clientDni: string;
  onSuccess: () => void;
}

export const CancelOperationModal: React.FC<Props> = ({
  visible, onClose, operationId, operationCode, clientDni, onSuccess,
}) => {
  const [cancelReason,   setCancelReason]   = useState('');
  const [animPhase, setAnimPhase] = useState<'idle' | 'loading' | 'done'>('idle');

  const spinAnim    = useRef(new Animated.Value(0)).current;
  const spin2       = useRef(new Animated.Value(0)).current;
  const dotScale    = useRef(new Animated.Value(1)).current;
  const checkScale  = useRef(new Animated.Value(0)).current;
  const checkOpacity = useRef(new Animated.Value(0)).current;

  const handleClose = () => {
    if (animPhase !== 'loading') {
      setCancelReason('');
      setAnimPhase('idle');
      onClose();
    }
  };

  const handleConfirm = async () => {
    if (!cancelReason.trim()) return;

    setAnimPhase('loading');
    spinAnim.setValue(0);
    spin2.setValue(0);
    dotScale.setValue(1);
    checkScale.setValue(0);
    checkOpacity.setValue(0);

    Animated.loop(
      Animated.timing(spinAnim, { toValue: 1, duration: 1100, easing: Easing.linear, useNativeDriver: true })
    ).start();
    Animated.loop(
      Animated.timing(spin2, { toValue: 1, duration: 1700, easing: Easing.linear, useNativeDriver: true })
    ).start();
    Animated.loop(
      Animated.sequence([
        Animated.timing(dotScale, { toValue: 1.5, duration: 500, easing: Easing.out(Easing.ease), useNativeDriver: true }),
        Animated.timing(dotScale, { toValue: 1,   duration: 500, easing: Easing.in(Easing.ease),  useNativeDriver: true }),
      ])
    ).start();

    try {
      await apiClient.post(`/api/client/cancel-operation/${operationId}`, {
        cancellation_reason: cancelReason.trim(),
        client_dni: clientDni,
      });

      spinAnim.stopAnimation();
      spin2.stopAnimation();
      dotScale.stopAnimation();
      setAnimPhase('done');

      Animated.parallel([
        Animated.spring(checkScale,   { toValue: 1, tension: 160, friction: 11, useNativeDriver: true }),
        Animated.timing(checkOpacity, { toValue: 1, duration: 220, useNativeDriver: true }),
      ]).start();

      setTimeout(() => {
        setCancelReason('');
        setAnimPhase('idle');
        onSuccess();
      }, 1800);

    } catch (error: any) {
      spinAnim.stopAnimation();
      spin2.stopAnimation();
      dotScale.stopAnimation();
      setAnimPhase('idle');
      const msg = error?.response?.data?.message || error?.message || 'No se pudo cancelar la operación';
      // Re-throw so caller can handle if needed
      throw new Error(msg);
    }
  };

  const handleConfirmSafe = () => {
    handleConfirm().catch(err => {
      const { Alert } = require('react-native');
      Alert.alert('Error', err.message);
    });
  };

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={handleClose}
    >
      <KeyboardAvoidingView
        style={s.overlay}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <BlurView intensity={55} tint="dark" style={StyleSheet.absoluteFill} />
        <View style={[StyleSheet.absoluteFill, { backgroundColor: 'rgba(0,0,0,0.35)' }]} />

        <View style={s.sheet}>
          {animPhase === 'idle' ? (
            <>
              {/* Header */}
              <View style={s.iconBlock}>
                <View style={s.iconRing}>
                  <Ionicons name="close-circle" size={19} color="#fff" />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={s.title}>Cancelar operación</Text>
                  <Text style={s.subtitle}>Esta acción no se puede deshacer</Text>
                </View>
                <TouchableOpacity onPress={handleClose} activeOpacity={0.7} style={s.closeBtn}>
                  <Ionicons name="close" size={18} color="#6B7280" />
                </TouchableOpacity>
              </View>

              {/* Body */}
              <View style={s.body}>
                <View style={s.opRow}>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                    <Ionicons name="pricetag-outline" size={13} color="#9CA3AF" />
                    <Text style={s.opLabel}>Operación</Text>
                  </View>
                  <View style={s.opChip}>
                    <Text style={s.opChipText}>{operationCode}</Text>
                  </View>
                </View>

                <Text style={s.inputLabel}>
                  Motivo de cancelación{'  '}<Text style={{ color: '#ef4444' }}>*</Text>
                </Text>
                <TextInput
                  style={[s.input, s.inputMultiline, cancelReason.trim() && s.inputActive]}
                  value={cancelReason}
                  onChangeText={setCancelReason}
                  placeholder="Ej: Cambié de opinión, error en el monto..."
                  placeholderTextColor="#C4C9D4"
                  multiline
                  numberOfLines={3}
                />
                {!cancelReason.trim() && (
                  <Text style={s.fieldRequired}>Campo obligatorio para continuar</Text>
                )}
              </View>

              {/* Buttons */}
              <View style={s.actions}>
                <TouchableOpacity
                  style={[s.btnConfirm, !cancelReason.trim() && s.btnConfirmDisabled]}
                  onPress={handleConfirmSafe}
                  disabled={!cancelReason.trim()}
                  activeOpacity={0.85}
                >
                  <Ionicons name="close-circle-outline" size={18} color="#fff" />
                  <Text style={s.btnConfirmText}>Confirmar cancelación</Text>
                </TouchableOpacity>
                <TouchableOpacity style={s.btnBack} onPress={handleClose} activeOpacity={0.8}>
                  <Text style={s.btnBackText}>Volver sin cancelar</Text>
                </TouchableOpacity>
              </View>
            </>
          ) : (
            <View style={s.animContainer}>
              {animPhase === 'loading' ? (
                <>
                  <View style={{ width: 80, height: 80, alignItems: 'center', justifyContent: 'center' }}>
                    <View style={{
                      position: 'absolute', width: 80, height: 80, borderRadius: 40,
                      borderWidth: 1, borderColor: 'rgba(239,68,68,0.12)',
                    }} />
                    <Animated.View style={{
                      position: 'absolute', width: 80, height: 80, borderRadius: 40,
                      borderWidth: 2,
                      borderTopColor: '#ef4444', borderRightColor: '#ef4444',
                      borderBottomColor: 'rgba(239,68,68,0.25)', borderLeftColor: 'transparent',
                      transform: [{ rotate: spinAnim.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '360deg'] }) }],
                    }} />
                    <Animated.View style={{
                      position: 'absolute', width: 56, height: 56, borderRadius: 28,
                      borderWidth: 1.5,
                      borderTopColor: 'transparent', borderRightColor: 'transparent',
                      borderBottomColor: 'rgba(239,68,68,0.55)', borderLeftColor: 'rgba(239,68,68,0.55)',
                      transform: [{ rotate: spin2.interpolate({ inputRange: [0, 1], outputRange: ['360deg', '0deg'] }) }],
                    }} />
                    <Animated.View style={{
                      width: 8, height: 8, borderRadius: 4,
                      backgroundColor: '#ef4444', opacity: 0.7,
                      transform: [{ scale: dotScale }],
                    }} />
                  </View>
                  <Text style={s.animText}>Anulando operación...</Text>
                  <Text style={s.animSub}>Esto tomará un momento</Text>
                </>
              ) : (
                <>
                  <Animated.View style={{
                    transform: [{ scale: checkScale }],
                    opacity: checkOpacity,
                    shadowColor: '#ef4444',
                    shadowOffset: { width: 0, height: 0 },
                    shadowOpacity: 0.35,
                    shadowRadius: 18,
                  }}>
                    <Ionicons name="checkmark-circle-outline" size={76} color="#ef4444" />
                  </Animated.View>
                  <Text style={[s.animText, { color: '#ef4444' }]}>Operación anulada</Text>
                  <Text style={s.animSub}>Tu solicitud fue procesada</Text>
                </>
              )}
            </View>
          )}
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
};

const s = StyleSheet.create({
  overlay: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 20,
  },
  sheet: {
    width: '100%',
    backgroundColor: '#FFFFFF',
    borderRadius: 24,
    overflow: 'hidden',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.18,
    shadowRadius: 24,
    elevation: 18,
  },
  iconBlock: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    paddingHorizontal: 18, paddingVertical: 14,
    borderBottomWidth: 1, borderBottomColor: 'rgba(0,0,0,0.07)',
  },
  iconRing: {
    width: 36, height: 36, borderRadius: 18,
    backgroundColor: '#dc2626',
    alignItems: 'center', justifyContent: 'center',
  },
  title: { fontSize: 15, fontWeight: '700', color: '#0D1117', marginBottom: 2 },
  subtitle: { fontSize: 11, color: DIM },
  closeBtn: {
    width: 32, height: 32, borderRadius: 16,
    backgroundColor: '#F3F4F6',
    alignItems: 'center', justifyContent: 'center',
  },
  body: { paddingHorizontal: 18, paddingTop: 16, paddingBottom: 6 },
  opRow: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    backgroundColor: '#F9FAFB', borderRadius: 10,
    borderWidth: 1, borderColor: 'rgba(0,0,0,0.07)',
    paddingHorizontal: 12, paddingVertical: 9, marginBottom: 12,
  },
  opLabel: { fontSize: 12, color: '#6B7280', fontWeight: '500' },
  opChip: {
    backgroundColor: '#dc2626', borderRadius: 6,
    paddingHorizontal: 8, paddingVertical: 3,
  },
  opChipText: { fontSize: 12, fontWeight: '700', color: '#FFFFFF', letterSpacing: 0.3 },
  inputLabel: { fontSize: 13, fontWeight: '600', color: '#0D1117', marginBottom: 10 },
  input: {
    backgroundColor: '#F8FAFC',
    borderWidth: 1.5, borderColor: 'rgba(0,0,0,0.10)',
    borderRadius: 14, color: '#0D1117', fontSize: 14,
    paddingHorizontal: 14, paddingVertical: 12,
  },
  inputMultiline: { minHeight: 90, textAlignVertical: 'top' },
  inputActive: {
    borderColor: 'rgba(239,68,68,0.5)',
    shadowColor: '#ef4444',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.15, shadowRadius: 6,
  },
  fieldRequired: { fontSize: 11, color: '#ef4444', marginTop: 5 },
  actions: {
    flexDirection: 'column', gap: 8,
    paddingHorizontal: 18, paddingTop: 14, paddingBottom: 20,
    borderTopWidth: 1, borderTopColor: 'rgba(0,0,0,0.06)',
  },
  btnConfirm: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    paddingVertical: 14, borderRadius: 14,
    backgroundColor: '#0D1117',
    shadowColor: '#000', shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.25, shadowRadius: 10, elevation: 4,
  },
  btnConfirmDisabled: {
    backgroundColor: 'rgba(0,0,0,0.08)',
    shadowOpacity: 0, elevation: 0,
  },
  btnConfirmText: { fontSize: 15, fontWeight: '700', color: '#fff', letterSpacing: 0.2 },
  btnBack: {
    paddingVertical: 12, borderRadius: 14, alignItems: 'center',
    borderWidth: 1, borderColor: 'rgba(0,0,0,0.12)',
  },
  btnBackText: { fontSize: 13, fontWeight: '600', color: '#374151' },
  animContainer: {
    paddingVertical: 48, alignItems: 'center', justifyContent: 'center', gap: 18,
  },
  animText: { fontSize: 17, fontWeight: '600', color: '#0D1117', textAlign: 'center' },
  animSub: { fontSize: 13, color: DIM, textAlign: 'center' },
});
