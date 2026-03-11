import React, { useState } from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  Alert,
  Modal,
  TouchableOpacity,
  Linking,
  KeyboardAvoidingView,
  Platform,
  SafeAreaView,
} from 'react-native';
import {
  List,
  Divider,
  Avatar,
  Text,
  Card,
  Button,
  TextInput,
  IconButton,
  Portal,
  Dialog,
  RadioButton,
  HelperText,
  Icon,
} from 'react-native-paper';
import { LinearGradient } from 'expo-linear-gradient';
import { useAuth } from '../contexts/AuthContext';
import { Colors } from '../constants/colors';
import { GlobalStyles } from '../styles/globalStyles';

interface ProfileScreenProps {
  navigation: any;
}

export const ProfileScreen: React.FC<ProfileScreenProps> = ({ navigation }) => {
  const { client, user, logout, refreshClient } = useAuth();

  // Estados para modales
  const [changePasswordVisible, setChangePasswordVisible] = useState(false);
  const [editInfoVisible, setEditInfoVisible] = useState(false);
  const [helpVisible, setHelpVisible] = useState(false);
  const [addAccountVisible, setAddAccountVisible] = useState(false);

  // Estados para formularios
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [phone, setPhone] = useState(client?.phone || '');
  const [email, setEmail] = useState(client?.email || '');

  // Estados de seguridad de contraseña
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  // Estados para agregar cuenta bancaria
  const [newAccountOrigen, setNewAccountOrigen] = useState('Lima');
  const [newAccountBank, setNewAccountBank] = useState('');
  const [newAccountBankCustomName, setNewAccountBankCustomName] = useState('');
  const [newAccountType, setNewAccountType] = useState('Ahorro');
  const [newAccountCurrency, setNewAccountCurrency] = useState('S/');
  const [newAccountNumber, setNewAccountNumber] = useState('');
  const [newAccountCCI, setNewAccountCCI] = useState('');
  const [addingAccount, setAddingAccount] = useState(false);
  const [bankMenuVisible, setBankMenuVisible] = useState(false);

  const handleLogout = () => {
    Alert.alert('Cerrar Sesión', '¿Estás seguro que deseas cerrar sesión?', [
      { text: 'Cancelar', style: 'cancel' },
      {
        text: 'Cerrar Sesión',
        style: 'destructive',
        onPress: async () => {
          await logout();
        },
      },
    ]);
  };

  const handleChangePassword = async () => {
    // Validaciones
    if (!currentPassword || !newPassword || !confirmPassword) {
      Alert.alert('Error', 'Por favor completa todos los campos');
      return;
    }

    if (newPassword.length < 8) {
      Alert.alert('Error', 'La nueva contraseña debe tener al menos 8 caracteres');
      return;
    }

    if (newPassword !== confirmPassword) {
      Alert.alert('Error', 'Las contraseñas no coinciden');
      return;
    }

    try {
      const API_CONFIG = require('../constants/config').API_CONFIG;
      const response = await fetch(`${API_CONFIG.BASE_URL}/api/client/change-password`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          dni: client?.dni,
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });

      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(data.message || 'Error al cambiar contraseña');
      }

      Alert.alert(
        '✅ Contraseña Actualizada',
        'Tu contraseña ha sido cambiada exitosamente',
        [
          {
            text: 'Entendido',
            onPress: () => {
              setChangePasswordVisible(false);
              setCurrentPassword('');
              setNewPassword('');
              setConfirmPassword('');
            },
          },
        ]
      );
    } catch (error: any) {
      Alert.alert('Error', error.message || 'No se pudo cambiar la contraseña');
      console.error('Error al cambiar contraseña:', error);
    }
  };

  const handleEditInfo = async () => {
    // Validaciones
    if (!phone) {
      Alert.alert('Error', 'El teléfono es obligatorio');
      return;
    }

    if (phone.length !== 9 || !/^9\d{8}$/.test(phone)) {
      Alert.alert('Error', 'El teléfono debe tener 9 dígitos y comenzar con 9');
      return;
    }

    if (!email) {
      Alert.alert('Error', 'El email es obligatorio');
      return;
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      Alert.alert('Error', 'Ingresa un email válido');
      return;
    }

    try {
      // TODO: Implementar API call real cuando esté disponible en backend
      // const response = await apiClient.put(`/api/client/update-info/${client?.dni}`, {
      //   phone,
      //   email,
      // });

      // Mostrar mensaje de éxito
      Alert.alert(
        '✅ Información Actualizada',
        'Tu información personal ha sido actualizada correctamente',
        [
          {
            text: 'Entendido',
            onPress: () => {
              setEditInfoVisible(false);
              // TODO: Actualizar el contexto cuando la API esté lista
              // updateClient({ ...client, phone, email });
            },
          },
        ]
      );
    } catch (error) {
      Alert.alert('Error', 'No se pudo actualizar la información. Intenta nuevamente.');
      console.error('Error al actualizar información:', error);
    }
  };

  const openWhatsApp = () => {
    const phoneNumber = '51926011920'; // Mismo número para enviar comprobantes
    const message = `Hola, soy ${client?.full_name} (DNI: ${client?.dni}). Necesito ayuda con mi cuenta de QoriCash.`;
    const url = `https://wa.me/${phoneNumber}?text=${encodeURIComponent(message)}`;

    Linking.openURL(url).catch((err) => {
      Alert.alert('Error', 'No se pudo abrir WhatsApp');
      console.error('Error al abrir WhatsApp:', err);
    });
  };

  const openEmail = () => {
    const email = 'info@qoricash.pe';
    const subject = `Soporte - ${client?.full_name}`;
    const body = `Hola,\n\nNecesito ayuda con mi cuenta.\n\nDatos:\nNombre: ${client?.full_name}\nDNI: ${client?.dni}\nEmail: ${client?.email}\n\nConsulta:\n`;
    const url = `mailto:${email}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;

    Linking.openURL(url).catch((err) => {
      Alert.alert('Error', 'No se pudo abrir el cliente de correo');
      console.error('Error al abrir email:', err);
    });
  };

  // Funciones para agregar cuenta bancaria
  const BANKS_LIMA = ['BCP', 'INTERBANK', 'PICHINCHA', 'BANBIF', 'BBVA', 'Scotiabank', 'Otros'];
  const BANKS_PROVINCIA = ['BCP', 'INTERBANK'];

  const getAvailableBanks = () => {
    return newAccountOrigen === 'Lima' ? BANKS_LIMA : BANKS_PROVINCIA;
  };

  const needsCCI = () => {
    const mainBanks = ['BCP', 'INTERBANK', 'PICHINCHA', 'BANBIF'];
    return newAccountBank && !mainBanks.includes(newAccountBank);
  };

  const handleOpenAddAccountDialog = () => {
    setNewAccountOrigen('Lima');
    setNewAccountBank('');
    setNewAccountBankCustomName('');
    setNewAccountType('Ahorro');
    setNewAccountCurrency('S/');
    setNewAccountNumber('');
    setNewAccountCCI('');
    setAddAccountVisible(true);
  };

  const handleAddBankAccount = async () => {
    if (!client) return;

    // Validaciones
    if (!newAccountBank) {
      Alert.alert('Error', 'Seleccione un banco');
      return;
    }

    if (newAccountBank === 'Otros' && !newAccountBankCustomName.trim()) {
      Alert.alert('Error', 'Ingrese el nombre del banco');
      return;
    }

    const mainBanks = ['BCP', 'INTERBANK', 'PICHINCHA', 'BANBIF'];
    const needsCCIValue = !mainBanks.includes(newAccountBank);

    if (needsCCIValue && (!newAccountCCI || newAccountCCI.length !== 20)) {
      Alert.alert('Error', 'Para este banco debe ingresar el CCI de 20 dígitos');
      return;
    }

    if (!needsCCIValue && !newAccountNumber) {
      Alert.alert('Error', 'Ingrese el número de cuenta');
      return;
    }

    try {
      setAddingAccount(true);

      const API_CONFIG = require('../constants/config').API_CONFIG;
      const bankNameToSend = newAccountBank === 'Otros' ? newAccountBankCustomName.trim() : newAccountBank;

      const response = await fetch(
        `${API_CONFIG.BASE_URL}/api/client/add-bank-account/${client.dni}`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            origen: newAccountOrigen,
            bank_name: bankNameToSend,
            account_type: newAccountType,
            currency: newAccountCurrency,
            account_number: needsCCIValue ? newAccountCCI : newAccountNumber,
            cci: needsCCIValue ? newAccountCCI : undefined,
          }),
        }
      );

      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(data.message || 'Error al agregar cuenta');
      }

      // Refrescar datos del cliente para mostrar la nueva cuenta
      if (refreshClient) {
        await refreshClient();
      }

      Alert.alert('Éxito', 'Cuenta bancaria agregada exitosamente');
      setAddAccountVisible(false);
    } catch (error: any) {
      Alert.alert('Error', error.message || 'Error al agregar cuenta bancaria');
    } finally {
      setAddingAccount(false);
    }
  };

  const handleDeleteBankAccount = async (accountIndex: number) => {
    if (!client) return;

    Alert.alert(
      'Eliminar Cuenta Bancaria',
      '¿Estás seguro que deseas eliminar esta cuenta bancaria?',
      [
        {
          text: 'Cancelar',
          style: 'cancel',
        },
        {
          text: 'Eliminar',
          style: 'destructive',
          onPress: async () => {
            try {
              const API_CONFIG = require('../constants/config').API_CONFIG;
              const url = `${API_CONFIG.BASE_URL}/api/client/delete-bank-account/${client.dni}/${accountIndex}`;

              const response = await fetch(url, {
                method: 'DELETE',
                headers: {
                  'Content-Type': 'application/json',
                },
              });

              const data = await response.json();

              if (!response.ok || !data.success) {
                throw new Error(data.message || 'Error al eliminar cuenta');
              }

              // Refrescar datos del cliente
              if (refreshClient) {
                await refreshClient();
              }

              Alert.alert('Éxito', 'Cuenta bancaria eliminada exitosamente');
            } catch (error: any) {
              console.error('Error al eliminar cuenta bancaria:', error);
              Alert.alert('Error', error.message || 'Error al eliminar cuenta bancaria');
            }
          },
        },
      ]
    );
  };

  return (
    <>
      <SafeAreaView style={styles.safeArea}>
        <ScrollView style={styles.scrollView} showsVerticalScrollIndicator={false}>

          {/* ── Dark gradient header ── */}
          <LinearGradient
            colors={['#0D1B2A', '#111F2C', '#0f2236']}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 1 }}
            style={styles.header}
          >
            <View style={styles.headerGlow} />

            {/* Avatar initials */}
            <View style={styles.avatarCircle}>
              <Text style={styles.avatarInitials}>
                {client?.nombres
                  ? client.nombres.charAt(0).toUpperCase()
                  : client?.full_name?.charAt(0).toUpperCase() || 'U'}
              </Text>
            </View>

            <Text style={styles.headerName}>{client?.full_name}</Text>
            <Text style={styles.headerEmail}>{client?.email}</Text>

            {/* Status badge */}
            <View style={styles.statusBadge}>
              <View style={styles.statusDot} />
              <Text style={styles.statusBadgeText}>{client?.status}</Text>
            </View>

            {/* Info strip */}
            <View style={styles.infoStrip}>
              <View style={styles.infoStripItem}>
                <Text style={styles.infoStripLabel}>Documento</Text>
                <Text style={styles.infoStripValue}>{client?.dni}</Text>
              </View>
              <View style={styles.infoStripDivider} />
              <View style={styles.infoStripItem}>
                <Text style={styles.infoStripLabel}>Tipo</Text>
                <Text style={styles.infoStripValue}>
                  {(client as any)?.client_type === 'juridico' ? 'Empresa' : 'Natural'}
                </Text>
              </View>
              <View style={styles.infoStripDivider} />
              <View style={styles.infoStripItem}>
                <Text style={styles.infoStripLabel}>Teléfono</Text>
                <Text style={styles.infoStripValue}>{client?.phone || '—'}</Text>
              </View>
            </View>
          </LinearGradient>

          <View style={styles.content}>

            {/* ── Personal Info ── */}
            <View style={styles.sectionCard}>
              <View style={styles.sectionCardHeader}>
                <View style={styles.sectionIconBg}>
                  <Icon source="account-outline" size={16} color={Colors.primary} />
                </View>
                <Text style={styles.sectionCardTitle}>Información Personal</Text>
                <TouchableOpacity
                  style={styles.editBtn}
                  onPress={() => {
                    setPhone(client?.phone || '');
                    setEmail(client?.email || '');
                    setEditInfoVisible(true);
                  }}
                >
                  <Icon source="pencil-outline" size={16} color={Colors.primary} />
                </TouchableOpacity>
              </View>

              <View style={styles.infoRow}>
                <View style={styles.infoRowIconBg}>
                  <Icon source="phone-outline" size={14} color="#64748B" />
                </View>
                <View style={styles.infoRowTexts}>
                  <Text style={styles.infoRowLabel}>Teléfono</Text>
                  <Text style={styles.infoRowValue}>{client?.phone || 'No registrado'}</Text>
                </View>
              </View>

              <View style={styles.infoRowDivider} />

              <View style={styles.infoRow}>
                <View style={styles.infoRowIconBg}>
                  <Icon source="email-outline" size={14} color="#64748B" />
                </View>
                <View style={styles.infoRowTexts}>
                  <Text style={styles.infoRowLabel}>Email</Text>
                  <Text style={styles.infoRowValue}>{client?.email || 'No registrado'}</Text>
                </View>
              </View>
            </View>

            {/* ── Bank Accounts ── */}
            <View style={styles.sectionCard}>
              <View style={styles.sectionCardHeader}>
                <View style={styles.sectionIconBg}>
                  <Icon source="bank-outline" size={16} color={Colors.primary} />
                </View>
                <Text style={styles.sectionCardTitle}>Cuentas Bancarias</Text>
              </View>

              {client?.bank_accounts && client.bank_accounts.length > 0 ? (
                client.bank_accounts.map((account, index) => (
                  <View key={index}>
                    {index > 0 && <View style={styles.infoRowDivider} />}
                    <View style={styles.bankRow}>
                      <View style={styles.bankRowIconBg}>
                        <Icon source="bank" size={16} color={Colors.primary} />
                      </View>
                      <View style={styles.bankRowTexts}>
                        <Text style={styles.bankRowName}>{account.bank_name}</Text>
                        <Text style={styles.bankRowDetail}>
                          {account.account_type} · {account.currency} · ****{account.account_number.slice(-4)}
                        </Text>
                      </View>
                      <TouchableOpacity
                        style={styles.bankDeleteBtn}
                        onPress={() => handleDeleteBankAccount(index)}
                      >
                        <Icon source="trash-can-outline" size={18} color="#ef4444" />
                      </TouchableOpacity>
                    </View>
                  </View>
                ))
              ) : (
                <Text style={styles.emptyText}>Sin cuentas registradas</Text>
              )}

              <TouchableOpacity style={styles.addAccountBtn} onPress={handleOpenAddAccountDialog}>
                <Icon source="plus-circle-outline" size={18} color={Colors.primary} />
                <Text style={styles.addAccountBtnText}>Gestionar Cuentas</Text>
              </TouchableOpacity>
            </View>

            {/* ── Settings ── */}
            <View style={styles.sectionCard}>
              <View style={styles.sectionCardHeader}>
                <View style={styles.sectionIconBg}>
                  <Icon source="cog-outline" size={16} color={Colors.primary} />
                </View>
                <Text style={styles.sectionCardTitle}>Configuración</Text>
              </View>

              <TouchableOpacity style={styles.settingsRow} onPress={() => setChangePasswordVisible(true)}>
                <View style={styles.settingsRowIconBg}>
                  <Icon source="lock-outline" size={14} color="#64748B" />
                </View>
                <View style={styles.settingsRowTexts}>
                  <Text style={styles.settingsRowTitle}>Cambiar Contraseña</Text>
                  <Text style={styles.settingsRowSubtitle}>Actualiza tu contraseña de acceso</Text>
                </View>
                <Icon source="chevron-right" size={20} color="#94A3B8" />
              </TouchableOpacity>

              <View style={styles.infoRowDivider} />

              <TouchableOpacity style={styles.settingsRow} onPress={() => setHelpVisible(true)}>
                <View style={styles.settingsRowIconBg}>
                  <Icon source="help-circle-outline" size={14} color="#64748B" />
                </View>
                <View style={styles.settingsRowTexts}>
                  <Text style={styles.settingsRowTitle}>Ayuda y Soporte</Text>
                  <Text style={styles.settingsRowSubtitle}>Contáctanos para resolver tus dudas</Text>
                </View>
                <Icon source="chevron-right" size={20} color="#94A3B8" />
              </TouchableOpacity>
            </View>

            {/* ── About ── */}
            <View style={styles.sectionCard}>
              <View style={styles.sectionCardHeader}>
                <View style={styles.sectionIconBg}>
                  <Icon source="information-outline" size={16} color={Colors.primary} />
                </View>
                <Text style={styles.sectionCardTitle}>Acerca de</Text>
              </View>

              <View style={styles.settingsRow}>
                <View style={styles.settingsRowIconBg}>
                  <Icon source="application" size={14} color="#64748B" />
                </View>
                <View style={styles.settingsRowTexts}>
                  <Text style={styles.settingsRowTitle}>Versión de la App</Text>
                  <Text style={styles.settingsRowSubtitle}>1.0.0</Text>
                </View>
              </View>

              <View style={styles.infoRowDivider} />

              <TouchableOpacity style={styles.settingsRow} onPress={() => navigation.navigate('Logs')}>
                <View style={styles.settingsRowIconBg}>
                  <Icon source="text-box-search-outline" size={14} color="#64748B" />
                </View>
                <View style={styles.settingsRowTexts}>
                  <Text style={styles.settingsRowTitle}>Logs del Sistema</Text>
                  <Text style={styles.settingsRowSubtitle}>Ver registros de depuración</Text>
                </View>
                <Icon source="chevron-right" size={20} color="#94A3B8" />
              </TouchableOpacity>

              <View style={styles.infoRowDivider} />

              <TouchableOpacity
                style={styles.settingsRow}
                onPress={() => {
                  const API_CONFIG = require('../constants/config').API_CONFIG;
                  Linking.openURL(`${API_CONFIG.BASE_URL}/legal/terms`).catch(() =>
                    Alert.alert('Error', 'No se pudo abrir el navegador')
                  );
                }}
              >
                <View style={styles.settingsRowIconBg}>
                  <Icon source="file-document-outline" size={14} color="#64748B" />
                </View>
                <View style={styles.settingsRowTexts}>
                  <Text style={styles.settingsRowTitle}>Términos y Condiciones</Text>
                </View>
                <Icon source="chevron-right" size={20} color="#94A3B8" />
              </TouchableOpacity>

              <View style={styles.infoRowDivider} />

              <TouchableOpacity
                style={styles.settingsRow}
                onPress={() => {
                  const API_CONFIG = require('../constants/config').API_CONFIG;
                  Linking.openURL(`${API_CONFIG.BASE_URL}/legal/privacy`).catch(() =>
                    Alert.alert('Error', 'No se pudo abrir el navegador')
                  );
                }}
              >
                <View style={styles.settingsRowIconBg}>
                  <Icon source="shield-check-outline" size={14} color="#64748B" />
                </View>
                <View style={styles.settingsRowTexts}>
                  <Text style={styles.settingsRowTitle}>Política de Privacidad</Text>
                </View>
                <Icon source="chevron-right" size={20} color="#94A3B8" />
              </TouchableOpacity>
            </View>

            {/* ── Logout ── */}
            <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
              <Icon source="logout" size={20} color="#FFFFFF" />
              <Text style={styles.logoutBtnText}>Cerrar Sesión</Text>
            </TouchableOpacity>

            <View style={styles.footer}>
              <Text style={styles.footerText}>QoriCash © 2025</Text>
            </View>

          </View>
        </ScrollView>
      </SafeAreaView>

      {/* Modal: Cambiar Contraseña */}
      <Modal
        visible={changePasswordVisible}
        transparent
        animationType="fade"
        onRequestClose={() => {
          setChangePasswordVisible(false);
          setCurrentPassword('');
          setNewPassword('');
          setConfirmPassword('');
        }}
      >
        <View style={styles.modalOverlay}>
          <KeyboardAvoidingView
            behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
            style={styles.keyboardAvoid}
          >
            <View style={styles.modalContainer}>
              <View style={styles.modalHeader}>
                <Text style={styles.modalTitle}>Cambiar Contraseña</Text>
              </View>

              <ScrollView style={styles.modalBody} showsVerticalScrollIndicator={false}>
                <TextInput
                  label="Contraseña Actual"
                  value={currentPassword}
                  onChangeText={setCurrentPassword}
                  secureTextEntry={!showCurrentPassword}
                  mode="outlined"
                  style={GlobalStyles.input}
                  right={
                    <TextInput.Icon
                      icon={showCurrentPassword ? 'eye-off' : 'eye'}
                      onPress={() => setShowCurrentPassword(!showCurrentPassword)}
                    />
                  }
                />
                <TextInput
                  label="Nueva Contraseña"
                  value={newPassword}
                  onChangeText={setNewPassword}
                  secureTextEntry={!showNewPassword}
                  mode="outlined"
                  style={GlobalStyles.input}
                  right={
                    <TextInput.Icon
                      icon={showNewPassword ? 'eye-off' : 'eye'}
                      onPress={() => setShowNewPassword(!showNewPassword)}
                    />
                  }
                />
                <TextInput
                  label="Confirmar Nueva Contraseña"
                  value={confirmPassword}
                  onChangeText={setConfirmPassword}
                  secureTextEntry={!showConfirmPassword}
                  mode="outlined"
                  style={GlobalStyles.input}
                  right={
                    <TextInput.Icon
                      icon={showConfirmPassword ? 'eye-off' : 'eye'}
                      onPress={() => setShowConfirmPassword(!showConfirmPassword)}
                    />
                  }
                />
                <Text style={styles.helpText}>
                  La contraseña debe tener al menos 8 caracteres
                </Text>
              </ScrollView>

              <View style={styles.modalActions}>
                <Button
                  mode="outlined"
                  onPress={() => {
                    setChangePasswordVisible(false);
                    setCurrentPassword('');
                    setNewPassword('');
                    setConfirmPassword('');
                  }}
                  style={styles.modalButton}
                >
                  Cancelar
                </Button>
                <Button
                  mode="contained"
                  onPress={handleChangePassword}
                  style={styles.modalButton}
                >
                  Guardar
                </Button>
              </View>
            </View>
          </KeyboardAvoidingView>
        </View>
      </Modal>

      {/* Modal: Editar Información */}
      <Modal
        visible={editInfoVisible}
        transparent
        animationType="fade"
        onRequestClose={() => {
          setEditInfoVisible(false);
          setPhone(client?.phone || '');
          setEmail(client?.email || '');
        }}
      >
        <View style={styles.modalOverlay}>
          <KeyboardAvoidingView
            behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
            style={styles.keyboardAvoid}
          >
            <View style={styles.modalContainerCompact}>
              <View style={styles.modalHeaderCompact}>
                <Text style={styles.modalTitle}>Editar Información</Text>
              </View>

              <View style={styles.modalBodyCompact}>
                <TextInput
                  label="Teléfono"
                  value={phone}
                  onChangeText={setPhone}
                  keyboardType="phone-pad"
                  mode="outlined"
                  style={styles.inputCompact}
                  maxLength={9}
                  left={<TextInput.Icon icon="phone" />}
                />
                <TextInput
                  label="Email"
                  value={email}
                  onChangeText={setEmail}
                  keyboardType="email-address"
                  mode="outlined"
                  style={styles.inputCompact}
                  autoCapitalize="none"
                  left={<TextInput.Icon icon="email" />}
                />
                <Text style={styles.helpTextCompact}>
                  El teléfono debe tener 9 dígitos y comenzar con 9
                </Text>
              </View>

              <View style={styles.modalActionsCompact}>
                <Button
                  mode="outlined"
                  onPress={() => {
                    setEditInfoVisible(false);
                    setPhone(client?.phone || '');
                    setEmail(client?.email || '');
                  }}
                  style={styles.modalButton}
                >
                  Cancelar
                </Button>
                <Button
                  mode="contained"
                  onPress={handleEditInfo}
                  style={styles.modalButton}
                >
                  Guardar
                </Button>
              </View>
            </View>
          </KeyboardAvoidingView>
        </View>
      </Modal>

      {/* Modal: Ayuda y Soporte */}
      <Portal>
        <Dialog
          visible={helpVisible}
          onDismiss={() => setHelpVisible(false)}
          style={styles.dialog}
        >
          <Dialog.Title>Ayuda y Soporte</Dialog.Title>
          <Dialog.Content>
            <Text style={styles.helpTitle}>¿Necesitas ayuda?</Text>
            <Text style={styles.helpDescription}>
              Contáctanos a través de los siguientes canales:
            </Text>

            <TouchableOpacity style={styles.contactOption} onPress={openWhatsApp}>
              <List.Icon icon="whatsapp" color="#25D366" />
              <View style={styles.contactText}>
                <Text style={styles.contactTitle}>WhatsApp</Text>
                <Text style={styles.contactDescription}>Chatea con nosotros</Text>
              </View>
              <List.Icon icon="chevron-right" />
            </TouchableOpacity>

            <Divider style={styles.divider} />

            <TouchableOpacity style={styles.contactOption} onPress={openEmail}>
              <List.Icon icon="email" color="#1976D2" />
              <View style={styles.contactText}>
                <Text style={styles.contactTitle}>Email</Text>
                <Text style={styles.contactDescription}>info@qoricash.pe</Text>
              </View>
              <List.Icon icon="chevron-right" />
            </TouchableOpacity>

            <Divider style={styles.divider} />

            <View style={styles.infoBox}>
              <List.Icon icon="clock" color="#757575" />
              <Text style={styles.infoText}>
                Horario de atención: Lunes a Viernes 9:00 AM - 6:00 PM
              </Text>
            </View>
          </Dialog.Content>
          <Dialog.Actions>
            <Button onPress={() => setHelpVisible(false)}>Cerrar</Button>
          </Dialog.Actions>
        </Dialog>
      </Portal>

      {/* Modal: Agregar Cuenta Bancaria */}
      <Portal>
        <Dialog
          visible={addAccountVisible}
          onDismiss={() => setAddAccountVisible(false)}
          style={styles.dialogLarge}
        >
          <Dialog.Title style={styles.dialogTitle}>Agregar Cuenta Bancaria</Dialog.Title>
          <Dialog.ScrollArea>
            <ScrollView contentContainerStyle={styles.dialogContentLarge} showsVerticalScrollIndicator={false}>
              {/* Origen */}
              <Text variant="titleSmall" style={styles.dialogLabelBank}>
                Origen
              </Text>
              <View style={styles.currencySelector}>
                <TouchableOpacity
                  style={[
                    styles.currencySelectorButton,
                    styles.currencySelectorButtonLeft,
                    newAccountOrigen === 'Lima' && styles.currencySelectorButtonActive,
                  ]}
                  onPress={() => setNewAccountOrigen('Lima')}
                  activeOpacity={0.8}
                >
                  <Text
                    style={[
                      styles.currencySelectorButtonText,
                      newAccountOrigen === 'Lima' && styles.currencySelectorButtonTextActive,
                    ]}
                  >
                    Lima
                  </Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[
                    styles.currencySelectorButton,
                    styles.currencySelectorButtonRight,
                    newAccountOrigen === 'Provincia' && styles.currencySelectorButtonActive,
                  ]}
                  onPress={() => setNewAccountOrigen('Provincia')}
                  activeOpacity={0.8}
                >
                  <Text
                    style={[
                      styles.currencySelectorButtonText,
                      newAccountOrigen === 'Provincia' && styles.currencySelectorButtonTextActive,
                    ]}
                  >
                    Provincia
                  </Text>
                </TouchableOpacity>
              </View>

              {/* Warning para Provincia */}
              {newAccountOrigen === 'Provincia' && (
                <Card style={styles.provinceWarningCard}>
                  <Card.Content style={styles.provinceWarningContent}>
                    <Text style={styles.provinceWarningText}>
                      Por el momento para cuentas de provincia solo operamos con BCP e INTERBANK
                    </Text>
                  </Card.Content>
                </Card>
              )}

              {/* Banco */}
              <Text variant="titleSmall" style={styles.dialogLabelBank}>
                Banco
              </Text>
              <TouchableOpacity
                onPress={() => setBankMenuVisible(true)}
                style={styles.bankSelectButton}
                activeOpacity={0.8}
              >
                <Text style={styles.bankSelectButtonText}>
                  {newAccountBank || 'Seleccionar Banco'}
                </Text>
                <IconButton icon="chevron-down" size={20} />
              </TouchableOpacity>

              {/* Nombre del banco personalizado */}
              {newAccountBank === 'Otros' && (
                <TextInput
                  label="Nombre del Banco"
                  value={newAccountBankCustomName}
                  onChangeText={setNewAccountBankCustomName}
                  mode="outlined"
                  placeholder="Ej: Banco de la Nación, Banco Ripley, etc."
                  style={styles.inputBank}
                  outlineColor="#E0E0E0"
                  activeOutlineColor="#22c55e"
                />
              )}

              {/* Tipo de Cuenta */}
              <Text variant="titleSmall" style={styles.dialogLabelBank}>
                Tipo de Cuenta
              </Text>
              <View style={styles.currencySelector}>
                <TouchableOpacity
                  style={[
                    styles.currencySelectorButton,
                    styles.currencySelectorButtonLeft,
                    newAccountType === 'Ahorro' && styles.currencySelectorButtonActive,
                  ]}
                  onPress={() => setNewAccountType('Ahorro')}
                  activeOpacity={0.8}
                >
                  <Text
                    style={[
                      styles.currencySelectorButtonText,
                      newAccountType === 'Ahorro' && styles.currencySelectorButtonTextActive,
                    ]}
                  >
                    Ahorro
                  </Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[
                    styles.currencySelectorButton,
                    styles.currencySelectorButtonRight,
                    newAccountType === 'Corriente' && styles.currencySelectorButtonActive,
                  ]}
                  onPress={() => setNewAccountType('Corriente')}
                  activeOpacity={0.8}
                >
                  <Text
                    style={[
                      styles.currencySelectorButtonText,
                      newAccountType === 'Corriente' && styles.currencySelectorButtonTextActive,
                    ]}
                  >
                    Corriente
                  </Text>
                </TouchableOpacity>
              </View>

              {/* Moneda */}
              <Text variant="titleSmall" style={styles.dialogLabelBank}>
                Moneda
              </Text>
              <View style={styles.currencySelector}>
                <TouchableOpacity
                  style={[
                    styles.currencySelectorButton,
                    styles.currencySelectorButtonLeft,
                    newAccountCurrency === 'S/' && styles.currencySelectorButtonActive,
                  ]}
                  onPress={() => setNewAccountCurrency('S/')}
                  activeOpacity={0.8}
                >
                  <Text
                    style={[
                      styles.currencySelectorButtonText,
                      newAccountCurrency === 'S/' && styles.currencySelectorButtonTextActive,
                    ]}
                  >
                    Soles (S/)
                  </Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[
                    styles.currencySelectorButton,
                    styles.currencySelectorButtonRight,
                    newAccountCurrency === '$' && styles.currencySelectorButtonActive,
                  ]}
                  onPress={() => setNewAccountCurrency('$')}
                  activeOpacity={0.8}
                >
                  <Text
                    style={[
                      styles.currencySelectorButtonText,
                      newAccountCurrency === '$' && styles.currencySelectorButtonTextActive,
                    ]}
                  >
                    Dólares ($)
                  </Text>
                </TouchableOpacity>
              </View>

              {/* Número de Cuenta (solo para bancos principales) */}
              {!needsCCI() && newAccountBank && (
                <TextInput
                  label="Número de Cuenta"
                  value={newAccountNumber}
                  onChangeText={setNewAccountNumber}
                  mode="outlined"
                  keyboardType="numeric"
                  style={styles.inputBank}
                  outlineColor="#E0E0E0"
                  activeOutlineColor="#22c55e"
                />
              )}

              {/* CCI (solo para bancos no principales) */}
              {needsCCI() && (
                <>
                  <TextInput
                    label="CCI (20 dígitos)"
                    value={newAccountCCI}
                    onChangeText={setNewAccountCCI}
                    mode="outlined"
                    keyboardType="numeric"
                    maxLength={20}
                    style={styles.inputBank}
                    outlineColor="#E0E0E0"
                    activeOutlineColor="#22c55e"
                  />
                  <HelperText type="info" visible={true} style={styles.helperTextBank}>
                    Ingrese el CCI completo de 20 dígitos
                  </HelperText>
                </>
              )}
            </ScrollView>
          </Dialog.ScrollArea>
          <Dialog.Actions style={styles.dialogActionsBank}>
            <TouchableOpacity
              onPress={() => setAddAccountVisible(false)}
              disabled={addingAccount}
              style={styles.dialogCancelButtonBank}
              activeOpacity={0.8}
            >
              <Text style={styles.dialogCancelButtonTextBank}>Cancelar</Text>
            </TouchableOpacity>
            <TouchableOpacity
              onPress={handleAddBankAccount}
              disabled={addingAccount || !newAccountBank}
              style={[
                styles.dialogAddButtonBank,
                (addingAccount || !newAccountBank) && styles.dialogAddButtonBankDisabled,
              ]}
              activeOpacity={0.8}
            >
              <Text
                style={[
                  styles.dialogAddButtonTextBank,
                  (addingAccount || !newAccountBank) && styles.dialogAddButtonTextBankDisabled,
                ]}
              >
                {addingAccount ? 'Agregando...' : 'Agregar Cuenta'}
              </Text>
            </TouchableOpacity>
          </Dialog.Actions>
        </Dialog>
      </Portal>

      {/* Modal: Seleccionar Banco */}
      <Portal>
        <Dialog
          visible={bankMenuVisible}
          onDismiss={() => setBankMenuVisible(false)}
          style={styles.dialog}
        >
          <Dialog.Title style={styles.dialogTitle}>Seleccionar Banco</Dialog.Title>
          <Dialog.Content>
            <RadioButton.Group
              onValueChange={(value) => {
                setNewAccountBank(value);
                setNewAccountBankCustomName('');
                setBankMenuVisible(false);
              }}
              value={newAccountBank}
            >
              {getAvailableBanks().map((bank) => (
                <RadioButton.Item
                  key={bank}
                  label={bank}
                  value={bank}
                  style={styles.bankRadioItem}
                  labelStyle={styles.bankRadioLabel}
                  color="#22c55e"
                />
              ))}
            </RadioButton.Group>
          </Dialog.Content>
          <Dialog.Actions style={styles.dialogActionsBank}>
            <TouchableOpacity
              onPress={() => setBankMenuVisible(false)}
              style={styles.dialogCancelButtonBank}
              activeOpacity={0.8}
            >
              <Text style={styles.dialogCancelButtonTextBank}>Cerrar</Text>
            </TouchableOpacity>
          </Dialog.Actions>
        </Dialog>
      </Portal>
    </>
  );
};

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#0D1B2A',
  },
  scrollView: {
    flex: 1,
    backgroundColor: Colors.background,
  },

  // ── Header ──
  header: {
    paddingTop: 24,
    paddingBottom: 0,
    alignItems: 'center',
    overflow: 'hidden',
  },
  headerGlow: {
    position: 'absolute',
    top: -60,
    right: -60,
    width: 200,
    height: 200,
    borderRadius: 100,
    backgroundColor: Colors.primary,
    opacity: 0.05,
  },
  avatarCircle: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: `${Colors.primary}20`,
    borderWidth: 2,
    borderColor: `${Colors.primary}60`,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 14,
  },
  avatarInitials: {
    fontSize: 32,
    fontWeight: '800',
    color: Colors.primary,
  },
  headerName: {
    fontSize: 22,
    fontWeight: '800',
    color: '#F1F5F9',
    letterSpacing: -0.3,
    textAlign: 'center',
    marginBottom: 4,
    paddingHorizontal: 20,
  },
  headerEmail: {
    fontSize: 13,
    color: '#6B7E94',
    marginBottom: 14,
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    backgroundColor: `${Colors.primary}15`,
    borderWidth: 1,
    borderColor: `${Colors.primary}40`,
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: 20,
    marginBottom: 20,
  },
  statusDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: Colors.primary,
  },
  statusBadgeText: {
    fontSize: 12,
    color: Colors.primary,
    fontWeight: '700',
  },
  infoStrip: {
    flexDirection: 'row',
    width: '100%',
    borderTopWidth: 1,
    borderTopColor: 'rgba(255,255,255,0.07)',
    backgroundColor: 'rgba(255,255,255,0.04)',
    paddingVertical: 14,
    paddingHorizontal: 20,
  },
  infoStripItem: {
    flex: 1,
    alignItems: 'center',
  },
  infoStripLabel: {
    fontSize: 10,
    color: '#6B7E94',
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    marginBottom: 5,
  },
  infoStripValue: {
    fontSize: 13,
    color: '#B0BBC9',
    fontWeight: '600',
  },
  infoStripDivider: {
    width: 1,
    backgroundColor: 'rgba(255,255,255,0.07)',
    marginVertical: 2,
  },

  // ── Content ──
  content: {
    padding: 16,
    paddingTop: 20,
  },

  // Section cards
  sectionCard: {
    backgroundColor: Colors.surface,
    borderRadius: 20,
    padding: 20,
    marginBottom: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.06,
    shadowRadius: 12,
    elevation: 3,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  sectionCardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 16,
    paddingBottom: 14,
    borderBottomWidth: 1,
    borderBottomColor: Colors.divider,
  },
  sectionIconBg: {
    width: 32,
    height: 32,
    borderRadius: 10,
    backgroundColor: `${Colors.primary}18`,
    justifyContent: 'center',
    alignItems: 'center',
  },
  sectionCardTitle: {
    flex: 1,
    fontSize: 15,
    fontWeight: '700',
    color: Colors.textDark,
  },
  editBtn: {
    width: 32,
    height: 32,
    borderRadius: 10,
    backgroundColor: `${Colors.primary}12`,
    justifyContent: 'center',
    alignItems: 'center',
  },

  // Info rows
  infoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingVertical: 4,
  },
  infoRowIconBg: {
    width: 32,
    height: 32,
    borderRadius: 8,
    backgroundColor: '#F1F5F9',
    justifyContent: 'center',
    alignItems: 'center',
    flexShrink: 0,
  },
  infoRowTexts: {
    flex: 1,
  },
  infoRowLabel: {
    fontSize: 11,
    color: '#94A3B8',
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    marginBottom: 2,
  },
  infoRowValue: {
    fontSize: 14,
    color: Colors.textDark,
    fontWeight: '600',
  },
  infoRowDivider: {
    height: 1,
    backgroundColor: Colors.divider,
    marginVertical: 10,
  },

  // Bank rows
  bankRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingVertical: 4,
  },
  bankRowIconBg: {
    width: 38,
    height: 38,
    borderRadius: 10,
    backgroundColor: `${Colors.primary}12`,
    justifyContent: 'center',
    alignItems: 'center',
    flexShrink: 0,
  },
  bankRowTexts: {
    flex: 1,
  },
  bankRowName: {
    fontSize: 14,
    fontWeight: '700',
    color: Colors.textDark,
    marginBottom: 2,
  },
  bankRowDetail: {
    fontSize: 12,
    color: '#94A3B8',
  },
  bankDeleteBtn: {
    width: 36,
    height: 36,
    borderRadius: 10,
    backgroundColor: '#FEF2F2',
    justifyContent: 'center',
    alignItems: 'center',
  },
  emptyText: {
    textAlign: 'center',
    color: '#94A3B8',
    fontSize: 13,
    paddingVertical: 8,
  },
  addAccountBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    marginTop: 12,
    paddingVertical: 10,
    borderRadius: 12,
    borderWidth: 1.5,
    borderStyle: 'dashed',
    borderColor: `${Colors.primary}50`,
    backgroundColor: `${Colors.primary}08`,
  },
  addAccountBtnText: {
    fontSize: 13,
    fontWeight: '700',
    color: Colors.primary,
  },

  // Settings rows
  settingsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingVertical: 4,
  },
  settingsRowIconBg: {
    width: 32,
    height: 32,
    borderRadius: 8,
    backgroundColor: '#F1F5F9',
    justifyContent: 'center',
    alignItems: 'center',
    flexShrink: 0,
  },
  settingsRowTexts: {
    flex: 1,
  },
  settingsRowTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: Colors.textDark,
    marginBottom: 1,
  },
  settingsRowSubtitle: {
    fontSize: 12,
    color: '#94A3B8',
  },

  // Logout
  logoutBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: '#ef4444',
    borderRadius: 16,
    paddingVertical: 16,
    marginTop: 4,
    marginBottom: 12,
    shadowColor: '#ef4444',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
    elevation: 4,
  },
  logoutBtnText: {
    fontSize: 15,
    fontWeight: '800',
    color: '#FFFFFF',
    letterSpacing: 0.3,
  },

  // Footer
  footer: {
    alignItems: 'center',
    paddingVertical: 8,
    paddingBottom: 32,
  },
  footerText: {
    color: '#94A3B8',
    fontSize: 12,
  },
  // Modal styles
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'flex-start',
    alignItems: 'center',
    paddingTop: 80,
  },
  keyboardAvoid: {
    width: '100%',
    alignItems: 'center',
  },
  modalContainer: {
    width: '92%',
    maxWidth: 500,
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    marginHorizontal: 20,
    maxHeight: '85%',
    elevation: 5,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 3.84,
  },
  modalHeader: {
    padding: 20,
    borderBottomWidth: 1,
    borderBottomColor: '#E0E0E0',
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: Colors.textDark,
  },
  modalBody: {
    padding: 20,
    maxHeight: 500,
  },
  modalBodyNoScroll: {
    padding: 20,
  },
  modalActions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    padding: 16,
    gap: 8,
    borderTopWidth: 1,
    borderTopColor: '#E0E0E0',
  },
  modalButton: {
    minWidth: 100,
  },
  // Compact modal styles (for Edit Info modal)
  modalContainerCompact: {
    width: '92%',
    maxWidth: 500,
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    marginHorizontal: 20,
    elevation: 5,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 3.84,
  },
  modalHeaderCompact: {
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#E0E0E0',
  },
  modalBodyCompact: {
    padding: 16,
  },
  modalActionsCompact: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    padding: 12,
    gap: 8,
    borderTopWidth: 1,
    borderTopColor: '#E0E0E0',
  },
  inputCompact: {
    marginBottom: 10,
    backgroundColor: '#FFFFFF',
  },
  helpTextCompact: {
    fontSize: 11,
    color: '#757575',
    fontStyle: 'italic',
    marginTop: -6,
    marginBottom: 4,
  },
  // Dialog styles (for Help modal)
  dialog: {
    maxHeight: '80%',
    borderRadius: 16,
  },
  dialogScrollArea: {
    maxHeight: 400,
    paddingHorizontal: 0,
  },
  dialogContent: {
    paddingHorizontal: 24,
    paddingVertical: 8,
  },
  input: {
    marginBottom: 12,
    backgroundColor: '#FFFFFF',
  },
  helpText: {
    fontSize: 12,
    color: '#757575',
    fontStyle: 'italic',
    marginTop: -8,
    marginBottom: 8,
  },
  helpTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: Colors.textDark,
    marginBottom: 8,
  },
  helpDescription: {
    fontSize: 14,
    color: '#757575',
    marginBottom: 16,
  },
  contactOption: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
  },
  contactText: {
    flex: 1,
    marginLeft: 8,
  },
  contactTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: Colors.textDark,
  },
  contactDescription: {
    fontSize: 13,
    color: '#757575',
  },
  divider: {
    marginVertical: 8,
  },
  infoBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F5F5F5',
    padding: 12,
    borderRadius: 8,
    marginTop: 16,
  },
  infoText: {
    flex: 1,
    fontSize: 12,
    color: '#757575',
    marginLeft: 8,
  },
  // Bank Account Dialog Styles
  dialogLarge: {
    maxHeight: '85%',
    borderRadius: 16,
  },
  dialogContentLarge: {
    paddingHorizontal: 24,
    paddingVertical: 16,
  },
  dialogLabelBank: {
    marginTop: 12,
    marginBottom: 8,
    fontWeight: '600',
    color: Colors.textDark,
    fontSize: 14,
  },
  currencySelector: {
    flexDirection: 'row',
    marginBottom: 16,
    borderRadius: 12,
    overflow: 'hidden',
    backgroundColor: '#F0F0F0',
  },
  currencySelectorButton: {
    flex: 1,
    paddingVertical: 12,
    paddingHorizontal: 16,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#F0F0F0',
  },
  currencySelectorButtonLeft: {
    borderTopLeftRadius: 12,
    borderBottomLeftRadius: 12,
  },
  currencySelectorButtonRight: {
    borderTopRightRadius: 12,
    borderBottomRightRadius: 12,
  },
  currencySelectorButtonActive: {
    backgroundColor: Colors.primary,
  },
  currencySelectorButtonText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#757575',
  },
  currencySelectorButtonTextActive: {
    color: '#FFFFFF',
  },
  provinceWarningCard: {
    backgroundColor: '#FFF3E0',
    marginBottom: 16,
    elevation: 0,
    borderWidth: 1,
    borderColor: '#FFB74D',
  },
  provinceWarningContent: {
    padding: 8,
  },
  provinceWarningText: {
    fontSize: 12,
    color: '#E65100',
    lineHeight: 18,
  },
  bankSelectButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#F0F0F0',
    borderRadius: 12,
    paddingLeft: 16,
    paddingRight: 4,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#E0E0E0',
  },
  bankSelectButtonText: {
    fontSize: 14,
    color: Colors.textDark,
    paddingVertical: 12,
  },
  inputBank: {
    marginTop: 8,
    marginBottom: 12,
    backgroundColor: '#FFFFFF',
  },
  helperTextBank: {
    marginTop: -8,
    marginBottom: 8,
  },
  dialogActionsBank: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    gap: 12,
  },
  dialogCancelButtonBank: {
    flex: 1,
    paddingVertical: 12,
    paddingHorizontal: 20,
    borderRadius: 8,
    backgroundColor: '#F0F0F0',
    alignItems: 'center',
    justifyContent: 'center',
  },
  dialogCancelButtonTextBank: {
    fontSize: 14,
    fontWeight: '600',
    color: Colors.textDark,
  },
  dialogAddButtonBank: {
    flex: 1,
    paddingVertical: 12,
    paddingHorizontal: 20,
    borderRadius: 8,
    backgroundColor: Colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  dialogAddButtonBankDisabled: {
    backgroundColor: '#E0E0E0',
  },
  dialogAddButtonTextBank: {
    fontSize: 14,
    fontWeight: '600',
    color: '#0D1B2A',
  },
  dialogAddButtonTextBankDisabled: {
    color: '#999999',
  },
  bankRadioItem: {
    paddingVertical: 8,
    paddingHorizontal: 8,
  },
  bankRadioLabel: {
    fontSize: 14,
  },
});
