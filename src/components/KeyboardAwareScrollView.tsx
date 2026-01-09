import React from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  ViewStyle,
} from 'react-native';
import { GlobalStyles, scrollViewProps } from '../styles/globalStyles';

interface KeyboardAwareScrollViewProps {
  children: React.ReactNode;
  contentContainerStyle?: ViewStyle;
  style?: ViewStyle;
  keyboardVerticalOffset?: number;
}

/**
 * Componente que evita que el teclado tape los inputs
 * Incluye KeyboardAvoidingView + ScrollView configurado correctamente
 */
export const KeyboardAwareScrollView: React.FC<KeyboardAwareScrollViewProps> = ({
  children,
  contentContainerStyle,
  style,
  keyboardVerticalOffset = Platform.OS === 'ios' ? 0 : 20,
}) => {
  return (
    <KeyboardAvoidingView
      style={[GlobalStyles.container, style]}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      keyboardVerticalOffset={keyboardVerticalOffset}
    >
      <ScrollView
        {...scrollViewProps}
        contentContainerStyle={[
          GlobalStyles.scrollContent,
          contentContainerStyle,
        ]}
        bounces={false}
      >
        {children}
      </ScrollView>
    </KeyboardAvoidingView>
  );
};
