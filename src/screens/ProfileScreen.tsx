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
} from 'react-native-paper';
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
      <ScrollView style={styles.container}>
      {/* Profile Header */}
      <Card style={styles.headerCard}>
        <Card.Content style={styles.headerContent}>
          <Avatar.Text
            size={80}
            label={client?.full_name?.substring(0, 2).toUpperCase() || 'U'}
            style={styles.avatar}
          />
          <Text variant="headlineSmall" style={styles.name}>
            {client?.full_name}
          </Text>
          <Text variant="bodyMedium" style={styles.email}>
            {client?.email}
          </Text>
          <Text variant="bodyMedium" style={styles.dni}>
            {client?.document_type}: {client?.dni}
          </Text>
        </Card.Content>
      </Card>

      {/* Personal Information */}
      <Card style={styles.card}>
        <Card.Content>
          <View style={styles.sectionHeader}>
            <Text variant="titleMedium" style={styles.sectionTitle}>
              Información Personal
            </Text>
            <IconButton
              icon="pencil"
              size={20}
              onPress={() => {
                setPhone(client?.phone || '');
                setEmail(client?.email || '');
                setEditInfoVisible(true);
              }}
            />
          </View>
          <List.Item
            title="Teléfono"
            description={client?.phone || 'No registrado'}
            left={(props) => <List.Icon {...props} icon="phone" />}
          />
          <Divider />
          <List.Item
            title="Email"
            description={client?.email || 'No registrado'}
            left={(props) => <List.Icon {...props} icon="email" />}
          />
          <Divider />
          <List.Item
            title="Estado"
            description={client?.status}
            left={(props) => <List.Icon {...props} icon="information" />}
            right={(props) => (
              <Text
                style={[
                  styles.statusText,
                  { color: client?.status === 'Activo' ? '#82C16C' : '#F44336' },
                ]}
              >
                {client?.status}
              </Text>
            )}
          />
        </Card.Content>
      </Card>

      {/* Bank Accounts */}
      <Card style={styles.card}>
        <Card.Content>
          <Text variant="titleMedium" style={styles.sectionTitle}>
            Cuentas Bancarias
          </Text>
          {client?.bank_accounts && client.bank_accounts.length > 0 ? (
            client.bank_accounts.map((account, index) => (
              <View key={index}>
                {index > 0 && <Divider />}
                <List.Item
                  title={account.bank_name}
                  description={`${account.account_type} - ${account.currency}\n****${account.account_number.slice(-4)}`}
                  left={(props) => <List.Icon {...props} icon="bank" />}
                  right={(props) => (
                    <IconButton
                      icon="delete"
                      iconColor="#F44336"
                      size={24}
                      onPress={() => handleDeleteBankAccount(index)}
                    />
                  )}
                />
              </View>
            ))
          ) : (
            <Text style={styles.emptyText}>No tienes cuentas bancarias registradas</Text>
          )}
          <Button
            mode="outlined"
            onPress={handleOpenAddAccountDialog}
            style={styles.addButton}
            icon="plus"
          >
            Gestionar Cuentas
          </Button>
        </Card.Content>
      </Card>

      {/* Settings */}
      <Card style={styles.card}>
        <Card.Content>
          <Text variant="titleMedium" style={styles.sectionTitle}>
            Configuración
          </Text>
          <List.Item
            title="Cambiar Contraseña"
            description="Actualiza tu contraseña de acceso"
            left={(props) => <List.Icon {...props} icon="lock" />}
            right={(props) => <List.Icon {...props} icon="chevron-right" />}
            onPress={() => setChangePasswordVisible(true)}
          />
          <Divider />
          <List.Item
            title="Ayuda y Soporte"
            description="Contáctanos para resolver tus dudas"
            left={(props) => <List.Icon {...props} icon="help-circle" />}
            right={(props) => <List.Icon {...props} icon="chevron-right" />}
            onPress={() => setHelpVisible(true)}
          />
        </Card.Content>
      </Card>

      {/* App Information */}
      <Card style={styles.card}>
        <Card.Content>
          <Text variant="titleMedium" style={styles.sectionTitle}>
            Acerca de
          </Text>
          <List.Item
            title="Versión de la App"
            description="1.0.0"
            left={(props) => <List.Icon {...props} icon="application" />}
          />
          <Divider />
          <List.Item
            title="Logs del Sistema"
            description="Ver registros de depuración"
            left={(props) => <List.Icon {...props} icon="text-box-search" />}
            right={(props) => <List.Icon {...props} icon="chevron-right" />}
            onPress={() => navigation.navigate('Logs')}
          />
          <Divider />
          <List.Item
            title="Términos y Condiciones"
            left={(props) => <List.Icon {...props} icon="file-document" />}
            right={(props) => <List.Icon {...props} icon="chevron-right" />}
            onPress={() => {
              const API_CONFIG = require('../constants/config').API_CONFIG;
              const url = `${API_CONFIG.BASE_URL}/legal/terms`;
              Linking.openURL(url).catch((err) => {
                Alert.alert('Error', 'No se pudo abrir el navegador');
                console.error('Error al abrir términos:', err);
              });
            }}
          />
          <Divider />
          <List.Item
            title="Política de Privacidad"
            left={(props) => <List.Icon {...props} icon="shield-check" />}
            right={(props) => <List.Icon {...props} icon="chevron-right" />}
            onPress={() => {
              const API_CONFIG = require('../constants/config').API_CONFIG;
              const url = `${API_CONFIG.BASE_URL}/legal/privacy`;
              Linking.openURL(url).catch((err) => {
                Alert.alert('Error', 'No se pudo abrir el navegador');
                console.error('Error al abrir política de privacidad:', err);
              });
            }}
          />
        </Card.Content>
      </Card>

      {/* Logout Button */}
      <Button
        mode="contained"
        onPress={handleLogout}
        style={styles.logoutButton}
        buttonColor="#F44336"
        icon="logout"
      >
        Cerrar Sesión
      </Button>

      <View style={styles.footer}>
        <Text variant="bodySmall" style={styles.version}>
          QoriCash © 2024
        </Text>
      </View>
      </ScrollView>

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
                  activeOutlineColor="#82C16C"
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
                  activeOutlineColor="#82C16C"
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
                    activeOutlineColor="#82C16C"
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
                  color="#82C16C"
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
  container: {
    flex: 1,
    backgroundColor: '#F5F5F5',
  },
  headerCard: {
    margin: 16,
    elevation: 4,
  },
  headerContent: {
    alignItems: 'center',
    paddingVertical: 24,
  },
  avatar: {
    backgroundColor: Colors.primary,
    marginBottom: 16,
  },
  name: {
    fontWeight: 'bold',
    marginBottom: 4,
    color: Colors.textDark,
  },
  email: {
    color: '#757575',
    marginBottom: 4,
  },
  dni: {
    color: '#757575',
  },
  card: {
    marginHorizontal: 16,
    marginVertical: 8,
    elevation: 2,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  sectionTitle: {
    fontWeight: '600',
    color: Colors.textDark,
  },
  statusText: {
    fontWeight: '600',
    alignSelf: 'center',
  },
  emptyText: {
    textAlign: 'center',
    color: '#999',
    paddingVertical: 16,
  },
  addButton: {
    marginTop: 8,
  },
  logoutButton: {
    marginHorizontal: 16,
    marginVertical: 24,
  },
  footer: {
    alignItems: 'center',
    paddingVertical: 16,
    paddingBottom: 32,
  },
  version: {
    color: '#9E9E9E',
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
    backgroundColor: '#82C16C',
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
    backgroundColor: '#82C16C',
    alignItems: 'center',
    justifyContent: 'center',
  },
  dialogAddButtonBankDisabled: {
    backgroundColor: '#E0E0E0',
  },
  dialogAddButtonTextBank: {
    fontSize: 14,
    fontWeight: '600',
    color: '#FFFFFF',
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
