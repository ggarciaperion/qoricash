import React from 'react';
import {
  Modal,
  View,
  TouchableOpacity,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  TouchableWithoutFeedback,
} from 'react-native';
import { Text, IconButton } from 'react-native-paper';
import { GlobalStyles } from '../styles/globalStyles';
import { Colors } from '../constants/colors';

interface CustomModalProps {
  visible: boolean;
  onDismiss: () => void;
  title: string;
  children: React.ReactNode;
  actions?: {
    label: string;
    onPress: () => void;
    primary?: boolean;
    disabled?: boolean;
    loading?: boolean;
  }[];
  dismissable?: boolean;
  maxHeight?: number | string;
}

export const CustomModal: React.FC<CustomModalProps> = ({
  visible,
  onDismiss,
  title,
  children,
  actions = [],
  dismissable = true,
  maxHeight = '85%',
}) => {
  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={dismissable ? onDismiss : undefined}
    >
      <TouchableWithoutFeedback onPress={dismissable ? onDismiss : undefined}>
        <View style={GlobalStyles.modalOverlay}>
          <TouchableWithoutFeedback>
            <KeyboardAvoidingView
              behavior={Platform.OS === 'ios' ? 'padding' : undefined}
              style={{ width: '100%', maxWidth: 400 }}
            >
              <View style={[GlobalStyles.modalContainer, { maxHeight }]}>
                {/* Header */}
                <View style={GlobalStyles.modalHeader}>
                  <Text style={GlobalStyles.modalTitle}>{title}</Text>
                  {dismissable && (
                    <IconButton
                      icon="close"
                      size={24}
                      onPress={onDismiss}
                      iconColor={Colors.textLight}
                    />
                  )}
                </View>

                {/* Content */}
                <View style={{ paddingVertical: 8 }}>
                  {children}
                </View>

                {/* Actions */}
                {actions.length > 0 && (
                  <View style={GlobalStyles.modalActions}>
                    {actions.map((action, index) => (
                      <TouchableOpacity
                        key={index}
                        style={[
                          GlobalStyles.modalButton,
                          action.primary
                            ? GlobalStyles.modalButtonPrimary
                            : GlobalStyles.modalButtonSecondary,
                          action.disabled && GlobalStyles.disabledButton,
                        ]}
                        onPress={action.onPress}
                        disabled={action.disabled || action.loading}
                        activeOpacity={0.7}
                      >
                        <Text
                          style={[
                            GlobalStyles.modalButtonText,
                            action.primary
                              ? GlobalStyles.modalButtonTextPrimary
                              : GlobalStyles.modalButtonTextSecondary,
                            action.disabled && GlobalStyles.disabledButtonText,
                          ]}
                        >
                          {action.loading ? 'Cargando...' : action.label}
                        </Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                )}
              </View>
            </KeyboardAvoidingView>
          </TouchableWithoutFeedback>
        </View>
      </TouchableWithoutFeedback>
    </Modal>
  );
};
