import { StyleSheet } from 'react-native';
import { Colors } from '../constants/colors';

/**
 * Estilos globales compartidos para toda la aplicación
 * Garantiza consistencia visual en todas las pantallas y componentes
 */

export const GlobalStyles = StyleSheet.create({
  // Contenedores principales
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },

  scrollContent: {
    flexGrow: 1,
    paddingHorizontal: 16,
    paddingBottom: 24,
  },

  // Cards y superficies
  card: {
    backgroundColor: Colors.surface,
    borderRadius: 16,
    padding: 16,
    marginVertical: 8,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 3,
  },

  cardTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: Colors.textDark,
    marginBottom: 12,
  },

  // Inputs
  input: {
    backgroundColor: Colors.surface,
    marginBottom: 16,
    borderRadius: 12,
  },

  inputOutlined: {
    backgroundColor: Colors.surface,
    marginBottom: 16,
  },

  // Botones
  primaryButton: {
    backgroundColor: Colors.primary,
    borderRadius: 12,
    paddingVertical: 14,
    paddingHorizontal: 24,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: Colors.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 6,
  },

  primaryButtonText: {
    color: Colors.textOnPrimary,
    fontSize: 16,
    fontWeight: '700',
    letterSpacing: 0.5,
  },

  secondaryButton: {
    backgroundColor: Colors.surface,
    borderRadius: 12,
    paddingVertical: 14,
    paddingHorizontal: 24,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: Colors.border,
  },

  secondaryButtonText: {
    color: Colors.textDark,
    fontSize: 16,
    fontWeight: '600',
  },

  outlineButton: {
    backgroundColor: 'transparent',
    borderRadius: 12,
    paddingVertical: 12,
    paddingHorizontal: 20,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: Colors.primary,
  },

  outlineButtonText: {
    color: Colors.primary,
    fontSize: 15,
    fontWeight: '600',
  },

  disabledButton: {
    backgroundColor: Colors.border,
    shadowColor: Colors.border,
  },

  disabledButtonText: {
    color: Colors.textMuted,
  },

  // Modales y Diálogos
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },

  modalContainer: {
    backgroundColor: Colors.surface,
    borderRadius: 20,
    padding: 24,
    width: '100%',
    maxWidth: 400,
    maxHeight: '85%',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.3,
    shadowRadius: 20,
    elevation: 10,
  },

  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 20,
    paddingBottom: 16,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
  },

  modalTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: Colors.textDark,
    flex: 1,
  },

  modalContent: {
    flexGrow: 1,
    flexShrink: 1,
  },

  modalActions: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 24,
    paddingTop: 20,
    borderTopWidth: 1,
    borderTopColor: Colors.border,
  },

  modalButton: {
    flex: 1,
    paddingVertical: 12,
    paddingHorizontal: 20,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },

  modalButtonPrimary: {
    backgroundColor: Colors.primary,
  },

  modalButtonSecondary: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
  },

  modalButtonText: {
    fontSize: 15,
    fontWeight: '600',
  },

  modalButtonTextPrimary: {
    color: Colors.textOnPrimary,
  },

  modalButtonTextSecondary: {
    color: Colors.textDark,
  },

  // Divisores
  divider: {
    height: 1,
    backgroundColor: Colors.divider,
    marginVertical: 16,
  },

  // Textos
  title: {
    fontSize: 24,
    fontWeight: '700',
    color: Colors.textDark,
    marginBottom: 8,
  },

  subtitle: {
    fontSize: 16,
    fontWeight: '500',
    color: Colors.textLight,
    marginBottom: 16,
  },

  bodyText: {
    fontSize: 14,
    color: Colors.textDark,
    lineHeight: 20,
  },

  caption: {
    fontSize: 12,
    color: Colors.textLight,
    lineHeight: 16,
  },

  // Badges y chips
  badge: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 12,
    alignSelf: 'flex-start',
  },

  badgeSuccess: {
    backgroundColor: '#E8F5E9',
  },

  badgeWarning: {
    backgroundColor: '#FFF3E0',
  },

  badgeError: {
    backgroundColor: '#FFEBEE',
  },

  badgeInfo: {
    backgroundColor: '#E3F2FD',
  },

  badgeText: {
    fontSize: 12,
    fontWeight: '600',
  },

  badgeTextSuccess: {
    color: '#2E7D32',
  },

  badgeTextWarning: {
    color: '#E65100',
  },

  badgeTextError: {
    color: '#C62828',
  },

  badgeTextInfo: {
    color: '#1565C0',
  },

  // Loading y estados vacíos
  centerContent: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },

  emptyStateText: {
    fontSize: 16,
    color: Colors.textLight,
    textAlign: 'center',
    marginTop: 16,
  },

  // Sombras predefinidas
  shadowLight: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 2,
  },

  shadowMedium: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 4,
  },

  shadowHeavy: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.15,
    shadowRadius: 16,
    elevation: 8,
  },

  // Espaciado
  marginTopSmall: {
    marginTop: 8,
  },

  marginTopMedium: {
    marginTop: 16,
  },

  marginTopLarge: {
    marginTop: 24,
  },

  marginBottomSmall: {
    marginBottom: 8,
  },

  marginBottomMedium: {
    marginBottom: 16,
  },

  marginBottomLarge: {
    marginBottom: 24,
  },

  paddingSmall: {
    padding: 8,
  },

  paddingMedium: {
    padding: 16,
  },

  paddingLarge: {
    padding: 24,
  },
});

/**
 * Configuración de KeyboardAvoidingView para todas las pantallas
 */
export const keyboardAvoidingViewProps = {
  behavior: 'padding' as const,
  keyboardVerticalOffset: 0,
};

/**
 * Props comunes para ScrollView con teclado
 */
export const scrollViewProps = {
  keyboardShouldPersistTaps: 'handled' as const,
  showsVerticalScrollIndicator: false,
};
