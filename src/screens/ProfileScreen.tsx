import React, { useState, useEffect, useCallback } from 'react';
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
  ImageBackground,
  TextInput,
  ActivityIndicator,
  Text,
  SafeAreaView,
  Image,
  Share,
  Clipboard,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { BlurView } from 'expo-blur';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import * as Haptics from 'expo-haptics';
import { useAuth } from '../contexts/AuthContext';
import { useLoginLoading } from '../contexts/LoginLoadingContext';
import { useBackground } from '../hooks/useBackground';

// ─── Design tokens ────────────────────────────────────────────────────────────
const GLASS_BG     = 'rgba(255,255,255,0.18)';
const GLASS_BORDER = 'rgba(255,255,255,0.15)';
const GREEN        = '#22c55e';

interface ProfileScreenProps { navigation: any }

// ─── GlassModal — definido FUERA del componente para evitar remount en re-renders ─
const GlassModal: React.FC<{
  visible: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  footer: React.ReactNode;
}> = ({ visible, onClose, title, children, footer }) => (
  <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
    <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
      <View style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.62)', justifyContent: 'center', alignItems: 'center', padding: 24 }}>
        <TouchableOpacity style={StyleSheet.absoluteFill} activeOpacity={1} onPress={onClose} />
        <View style={{ width: '100%', maxHeight: '88%', borderRadius: 20, overflow: 'hidden', backgroundColor: '#FFFFFF', shadowColor: '#000', shadowOffset: { width: 0, height: 12 }, shadowOpacity: 0.18, shadowRadius: 28, elevation: 20 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', backgroundColor: '#0D1117', paddingHorizontal: 20, paddingVertical: 16 }}>
            <Text style={{ fontSize: 16, fontWeight: '800', color: '#FFFFFF', letterSpacing: 0.1 }}>{title}</Text>
            <TouchableOpacity onPress={onClose} style={{ width: 28, height: 28, borderRadius: 14, backgroundColor: 'rgba(255,255,255,0.10)', alignItems: 'center', justifyContent: 'center' }} activeOpacity={0.7}>
              <Ionicons name="close" size={17} color="rgba(255,255,255,0.7)" />
            </TouchableOpacity>
          </View>
          <ScrollView
            showsVerticalScrollIndicator={false}
            keyboardShouldPersistTaps="handled"
            contentContainerStyle={{ paddingHorizontal: 20, paddingTop: 16, paddingBottom: 20 }}
          >
            {children}
            {footer}
          </ScrollView>
        </View>
      </View>
    </KeyboardAvoidingView>
  </Modal>
);

const capitalize = (s: string) =>
  s ? s.charAt(0).toUpperCase() + s.slice(1).toLowerCase() : s;

// ─── Row de sección ───────────────────────────────────────────────────────────
const SectionRow: React.FC<{
  icon: string;
  title: string;
  subtitle?: string;
  onPress?: () => void;
  chevron?: boolean;
  danger?: boolean;
}> = ({ icon, title, subtitle, onPress, chevron = true, danger = false }) => (
  <TouchableOpacity
    style={s.row}
    onPress={onPress}
    activeOpacity={onPress ? 0.72 : 1}
    disabled={!onPress}
  >
    <View style={s.rowIcon}>
      <Ionicons name={icon as any} size={16} color={danger ? '#f87171' : '#6B7280'} />
    </View>
    <View style={s.rowTexts}>
      <Text style={[s.rowTitle, danger && { color: '#f87171' }]}>{title}</Text>
      {subtitle ? <Text style={s.rowSub}>{subtitle}</Text> : null}
    </View>
    {chevron && onPress && (
      <Ionicons name="chevron-forward" size={16} color="rgba(255,255,255,0.22)" />
    )}
  </TouchableOpacity>
);

// ─── Screen ───────────────────────────────────────────────────────────────────
export const ProfileScreen: React.FC<ProfileScreenProps> = ({ navigation }) => {
  const insets = useSafeAreaInsets();
  const bg = useBackground();
  const { client, user, refreshClient } = useAuth();
  const { setShowLogoutLoading } = useLoginLoading();

  // Referral stats
  const [referralStats, setReferralStats] = useState<{
    referral_code: string;
    total_referred_clients: number;
    total_pips_earned: number;
    pips_available: number;
  } | null>(null);

  const fetchReferralStats = useCallback(async () => {
    if (!client?.dni) return;
    try {
      const { API_CONFIG } = require('../constants/config');
      const res = await fetch(`${API_CONFIG.BASE_URL}/api/referrals/stats/${client.dni}`);
      const data = await res.json();
      if (data.success) setReferralStats(data);
    } catch {}
  }, [client?.dni]);

  useEffect(() => { fetchReferralStats(); }, [fetchReferralStats]);

  const handleCopyCode = () => {
    if (!referralStats?.referral_code) return;
    Clipboard.setString(referralStats.referral_code);
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    Alert.alert('¡Copiado!', `Código ${referralStats.referral_code} copiado al portapapeles`);
  };

  const handleShareCode = async () => {
    if (!referralStats?.referral_code) return;
    try {
      await Share.share({
        message: `¡Usa mi código de referido ${referralStats.referral_code} en Qoricash y obtén 20 pips de mejora en tu tipo de cambio! Descarga la app en www.qoricash.pe`,
      });
    } catch {}
  };

  // Modal states
  const [changePasswordVisible, setChangePasswordVisible] = useState(false);
  const [editInfoVisible,       setEditInfoVisible]       = useState(false);
  const [helpVisible,           setHelpVisible]           = useState(false);
  const [addAccountVisible,     setAddAccountVisible]     = useState(false);

  // Change password
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword,     setNewPassword]     = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showCurrentPwd,  setShowCurrentPwd]  = useState(false);
  const [showNewPwd,      setShowNewPwd]      = useState(false);
  const [showConfirmPwd,  setShowConfirmPwd]  = useState(false);

  // Edit info
  const [phone, setPhone] = useState(client?.phone || '');
  const [email, setEmail] = useState(client?.email || '');

  // Bank account
  const [newAccountOrigen,      setNewAccountOrigen]      = useState('Lima');
  const [newAccountBank,        setNewAccountBank]        = useState('');
  const [newAccountBankCustom,  setNewAccountBankCustom]  = useState('');
  const [newAccountType,        setNewAccountType]        = useState('Ahorro');
  const [newAccountCurrency,    setNewAccountCurrency]    = useState('S/');
  const [newAccountNumber,      setNewAccountNumber]      = useState('');
  const [newAccountCCI,         setNewAccountCCI]         = useState('');
  const [addingAccount,         setAddingAccount]         = useState(false);
  const [bankMenuVisible,       setBankMenuVisible]       = useState(false);
  const [editingAccounts,       setEditingAccounts]       = useState(false);

  // ── Handlers (logic unchanged) ─────────────────────────────────────────────
  const handleLogout = () => {
    Alert.alert('Cerrar Sesión', '¿Estás seguro que deseas cerrar sesión?', [
      { text: 'Cancelar', style: 'cancel' },
      { text: 'Cerrar Sesión', style: 'destructive', onPress: () => setShowLogoutLoading(true) },
    ]);
  };

  const handleChangePassword = async () => {
    if (!currentPassword || !newPassword || !confirmPassword) {
      Alert.alert('Error', 'Por favor completa todos los campos'); return;
    }
    if (newPassword.length < 8) {
      Alert.alert('Error', 'La nueva contraseña debe tener al menos 8 caracteres'); return;
    }
    if (newPassword !== confirmPassword) {
      Alert.alert('Error', 'Las contraseñas no coinciden'); return;
    }
    try {
      const { API_CONFIG } = require('../constants/config');
      const response = await fetch(`${API_CONFIG.BASE_URL}/api/client/change-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dni: client?.dni, current_password: currentPassword, new_password: newPassword }),
      });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.message || 'Error al cambiar contraseña');
      Alert.alert('Contraseña Actualizada', 'Tu contraseña ha sido cambiada exitosamente', [{
        text: 'Entendido', onPress: () => {
          setChangePasswordVisible(false);
          setCurrentPassword(''); setNewPassword(''); setConfirmPassword('');
        },
      }]);
    } catch (error: any) {
      Alert.alert('Error', error.message || 'No se pudo cambiar la contraseña');
    }
  };

  const handleEditInfo = async () => {
    if (!phone) { Alert.alert('Error', 'El teléfono es obligatorio'); return; }
    if (phone.length !== 9 || !/^9\d{8}$/.test(phone)) { Alert.alert('Error', 'El teléfono debe tener 9 dígitos y comenzar con 9'); return; }
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { Alert.alert('Error', 'Ingresa un email válido'); return; }
    Alert.alert('Información Actualizada', 'Tu información ha sido actualizada correctamente', [{
      text: 'Entendido', onPress: () => setEditInfoVisible(false),
    }]);
  };

  const openWhatsApp = () => {
    const msg = `Hola, soy ${client?.full_name} (DNI: ${client?.dni}). Necesito ayuda con mi cuenta de QoriCash.`;
    Linking.openURL(`https://wa.me/51910624404?text=${encodeURIComponent(msg)}`).catch(() =>
      Alert.alert('Error', 'No se pudo abrir WhatsApp')
    );
  };

  const openEmail = () => {
    const subject = `Soporte - ${client?.full_name}`;
    const body = `Hola,\n\nNecesito ayuda con mi cuenta.\n\nNombre: ${client?.full_name}\nDNI: ${client?.dni}\n\nConsulta:\n`;
    Linking.openURL(`mailto:info@qoricash.pe?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`).catch(() =>
      Alert.alert('Error', 'No se pudo abrir el correo')
    );
  };

  const BANKS_LIMA      = ['BCP', 'INTERBANK', 'PICHINCHA', 'BANBIF', 'BBVA', 'Scotiabank', 'Otros'];
  const BANKS_PROVINCIA = ['BCP', 'INTERBANK'];
  const getAvailableBanks = () => newAccountOrigen === 'Lima' ? BANKS_LIMA : BANKS_PROVINCIA;
  const needsCCI = () => !['BCP', 'INTERBANK', 'PICHINCHA', 'BANBIF'].includes(newAccountBank);

  const handleOpenAddAccountDialog = () => {
    setNewAccountOrigen('Lima'); setNewAccountBank(''); setNewAccountBankCustom('');
    setNewAccountType('Ahorro'); setNewAccountCurrency('S/'); setNewAccountNumber(''); setNewAccountCCI('');
    setAddAccountVisible(true);
  };

  const handleAddBankAccount = async () => {
    if (!client) return;
    if (!newAccountBank) { Alert.alert('Error', 'Seleccione un banco'); return; }
    if (newAccountBank === 'Otros' && !newAccountBankCustom.trim()) { Alert.alert('Error', 'Ingrese el nombre del banco'); return; }
    if (needsCCI() && (!newAccountCCI || newAccountCCI.length !== 20)) { Alert.alert('Error', 'Ingrese el CCI de 20 dígitos'); return; }
    if (!needsCCI() && !newAccountNumber) { Alert.alert('Error', 'Ingrese el número de cuenta'); return; }
    try {
      setAddingAccount(true);
      const { API_CONFIG } = require('../constants/config');
      const bankName = newAccountBank === 'Otros' ? newAccountBankCustom.trim() : newAccountBank;
      const response = await fetch(`${API_CONFIG.BASE_URL}/api/client/add-bank-account/${client.dni}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          origen: newAccountOrigen, bank_name: bankName,
          account_type: newAccountType, currency: newAccountCurrency,
          account_number: needsCCI() ? newAccountCCI : newAccountNumber,
          cci: needsCCI() ? newAccountCCI : undefined,
        }),
      });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.message || 'Error al agregar cuenta');
      if (refreshClient) await refreshClient();
      Alert.alert('Éxito', 'Cuenta bancaria agregada exitosamente');
      setAddAccountVisible(false);
    } catch (error: any) {
      Alert.alert('Error', error.message || 'Error al agregar cuenta bancaria');
    } finally { setAddingAccount(false); }
  };

  const handleDeleteBankAccount = async (accountIndex: number) => {
    if (!client) return;
    Alert.alert('Eliminar Cuenta', '¿Estás seguro?', [
      { text: 'Cancelar', style: 'cancel' },
      {
        text: 'Eliminar', style: 'destructive', onPress: async () => {
          try {
            const { API_CONFIG } = require('../constants/config');
            const response = await fetch(
              `${API_CONFIG.BASE_URL}/api/client/delete-bank-account/${client.dni}/${accountIndex}`,
              { method: 'DELETE', headers: { 'Content-Type': 'application/json' } }
            );
            const data = await response.json();
            if (!response.ok || !data.success) throw new Error(data.message || 'Error al eliminar cuenta');
            if (refreshClient) await refreshClient();
            Alert.alert('Éxito', 'Cuenta bancaria eliminada exitosamente');
          } catch (error: any) {
            Alert.alert('Error', error.message || 'Error al eliminar cuenta bancaria');
          }
        },
      },
    ]);
  };

  // ── Avatar initials ────────────────────────────────────────────────────────
  const initial = client?.nombres
    ? client.nombres.charAt(0).toUpperCase()
    : client?.full_name?.charAt(0).toUpperCase() || 'U';

  // ── Helpers for modals ─────────────────────────────────────────────────────
  // GlassModal se define a nivel de módulo para evitar remount en re-renders

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <View style={s.root}>
      <View style={[StyleSheet.absoluteFill, { backgroundColor: '#F5F7FA' }]} pointerEvents="none" />

      {/* ══ Header fijo (no scrollea) ════════════════════════════════════ */}
      <View style={[s.fixedHeader, { paddingTop: insets.top + 12 }]}>
        <Text style={s.headerLabel}>Mi perfil</Text>
        <View style={s.headerRow}>
          <Text style={s.headerName}>
            {[client?.nombres?.split(' ')[0], client?.apellido_paterno].filter(Boolean).join(' ') || client?.full_name}
          </Text>
          <Image source={require('../../assets/dt.png')} style={[s.headerLogo, { backgroundColor: 'transparent' }]} resizeMode="contain" />
        </View>
      </View>

      <ScrollView
        style={s.scroll}
        contentContainerStyle={[s.content, { paddingBottom: insets.bottom + 88 }]}
        showsVerticalScrollIndicator={false}
      >

        {/* ══ Info strip ═══════════════════════════════════════════════════ */}
        <View style={s.stripWrap}>
          <View style={s.strip}>
            <View style={s.stripItem}>
              <Text style={s.stripLabel}>Documento</Text>
              <Text style={s.stripValue}>{client?.dni}</Text>
            </View>
            <View style={s.stripDivider} />
            <View style={s.stripItem}>
              <Text style={s.stripLabel}>Estado</Text>
              <Text style={[s.stripValue, { color: GREEN }]}>{capitalize(client?.status || '')}</Text>
            </View>
            <View style={s.stripDivider} />
            <View style={s.stripItem}>
              <Text style={s.stripLabel}>Tipo</Text>
              <Text style={s.stripValue}>
                {(client as any)?.client_type === 'juridico' ? 'Empresa' : 'Natural'}
              </Text>
            </View>
          </View>
        </View>

        {/* ══ Código de Referido ══════════════════════════════════════════ */}
        {referralStats && (
          <View style={[s.card, s.referralCard]}>
            <View style={[s.cardHeader, { paddingTop: 12, paddingBottom: 8 }]}>
              <Ionicons name="gift-outline" size={15} color="#fff" />
              <Text style={[s.cardTitle, { color: '#fff' }]}>Programa de Referidos</Text>
            </View>

            {/* Código */}
            <View style={s.referralCodeRow}>
              <View style={s.referralCodeWrap}>
                <Text style={s.referralCodeLabel}>Tu código</Text>
                <Text style={s.referralCode}>{referralStats.referral_code}</Text>
              </View>
              <TouchableOpacity style={s.referralBtn} onPress={handleCopyCode} activeOpacity={0.75}>
                <Ionicons name="copy-outline" size={16} color="#fff" />
              </TouchableOpacity>
              <TouchableOpacity style={s.referralBtn} onPress={handleShareCode} activeOpacity={0.75}>
                <Ionicons name="share-social-outline" size={16} color="#fff" />
              </TouchableOpacity>
            </View>

            {/* Stats */}
            <View style={s.referralStatsRow}>
              <View style={s.referralStat}>
                <Text style={s.referralStatValue}>{referralStats.total_referred_clients}</Text>
                <Text style={s.referralStatLabel}>Referidos</Text>
              </View>
              <View style={s.referralStatDivider} />
              <View style={s.referralStat}>
                <Text style={s.referralStatValue}>{referralStats.total_pips_earned}</Text>
                <Text style={s.referralStatLabel}>Pips ganados</Text>
              </View>
              <View style={s.referralStatDivider} />
              <View style={s.referralStat}>
                <Text style={s.referralStatValue}>{referralStats.pips_available}</Text>
                <Text style={s.referralStatLabel}>Pips disponibles</Text>
              </View>
            </View>

            <Text style={s.referralHint}>
              Comparte tu código. Cuando tu referido complete su primera operación, ambos ganan 20 pips de mejora en el tipo de cambio.
            </Text>
          </View>
        )}

        {/* ══ Información Personal ════════════════════════════════════════ */}
        <View style={s.card}>
          <View style={s.cardHeader}>
            <Ionicons name="person-outline" size={15} color="#0D1117" />
            <Text style={s.cardTitle}>Información Personal</Text>
            <TouchableOpacity
              style={s.editBtn}
              onPress={() => { setPhone(client?.phone || ''); setEmail(client?.email || ''); setEditInfoVisible(true); }}
            >
              <Ionicons name="pencil-outline" size={14} color="#FFFFFF" />
            </TouchableOpacity>
          </View>
          <SectionRow icon="call-outline"  title="Teléfono" subtitle={client?.phone || 'No registrado'} onPress={undefined} chevron={false} />
          <View style={s.rowLine} />
          <SectionRow icon="mail-outline"  title="Email"    subtitle={client?.email || 'No registrado'} onPress={undefined} chevron={false} />
        </View>

        {/* ══ Configuración ════════════════════════════════════════════════ */}
        <View style={s.card}>
          <View style={s.cardHeader}>
            <Ionicons name="settings-outline" size={15} color="#0D1117" />
            <Text style={s.cardTitle}>Configuración</Text>
          </View>
          <SectionRow icon="lock-closed-outline" title="Cambiar Contraseña" subtitle="Actualiza tu contraseña de acceso" onPress={() => setChangePasswordVisible(true)} />
          <View style={s.rowLine} />
          <SectionRow icon="help-circle-outline" title="Ayuda y Soporte" subtitle="Contáctanos para resolver tus dudas" onPress={() => setHelpVisible(true)} />
        </View>

        {/* ══ Cuentas Bancarias ════════════════════════════════════════════ */}
        <View style={s.card}>
          <View style={s.cardHeader}>
            <Ionicons name="card-outline" size={15} color="#0D1117" />
            <Text style={s.cardTitle}>Cuentas Bancarias</Text>
            <TouchableOpacity style={s.editBtn} onPress={() => setEditingAccounts(e => !e)}>
              <Ionicons name={editingAccounts ? 'checkmark' : 'pencil-outline'} size={14} color="#FFFFFF" />
            </TouchableOpacity>
          </View>

          {client?.bank_accounts && client.bank_accounts.length > 0 ? (
            client.bank_accounts.map((account, i) => (
              <View key={i}>
                {i > 0 && <View style={s.rowLine} />}
                <View style={s.bankRow}>
                  <View style={s.bankIcon}>
                    <Ionicons name="business-outline" size={16} color="#6B7280" />
                  </View>
                  <View style={s.bankTexts}>
                    <Text style={s.bankName}>{account.bank_name}</Text>
                    <Text style={s.bankDetail}>
                      {account.account_type} · {account.currency} · ****{account.account_number.slice(-4)}
                    </Text>
                  </View>
                  {editingAccounts && (
                    <TouchableOpacity style={s.bankDelete} onPress={() => handleDeleteBankAccount(i)}>
                      <Ionicons name="trash-outline" size={16} color="#f87171" />
                    </TouchableOpacity>
                  )}
                </View>
              </View>
            ))
          ) : (
            <Text style={s.emptyText}>Sin cuentas registradas</Text>
          )}

          {editingAccounts && (
            <TouchableOpacity
              style={s.addBtn}
              onPress={() => {
                if ((client?.bank_accounts?.length ?? 0) >= 6) {
                  Alert.alert('Límite alcanzado', 'Has alcanzado el máximo de 6 cuentas bancarias permitidas.');
                } else {
                  handleOpenAddAccountDialog();
                }
              }}
              activeOpacity={0.78}
            >
              <Ionicons name="add-circle-outline" size={16} color="#FFFFFF" />
              <Text style={s.addBtnText}>Agregar cuenta</Text>
            </TouchableOpacity>
          )}
        </View>

        {/* ══ Acerca de ════════════════════════════════════════════════════ */}
        <View style={s.card}>
          <View style={s.cardHeader}>
            <Ionicons name="information-circle-outline" size={15} color="#0D1117" />
            <Text style={s.cardTitle}>Acerca de</Text>
          </View>
          <SectionRow icon="reader-outline"          title="Términos y Condiciones"   subtitle="Lee nuestros términos de uso"     onPress={() => { const { API_CONFIG } = require('../constants/config'); navigation.navigate('WebView', { url: `${API_CONFIG.BASE_URL}/legal/terms`, title: 'Términos y Condiciones' }); }} />
          <View style={s.rowLine} />
          <SectionRow icon="shield-checkmark-outline" title="Política de Privacidad"  subtitle="Conoce cómo protegemos tus datos" onPress={() => { const { API_CONFIG } = require('../constants/config'); navigation.navigate('WebView', { url: `${API_CONFIG.BASE_URL}/legal/privacy`, title: 'Política de Privacidad' }); }} />
        </View>

        {/* ══ Logout ═══════════════════════════════════════════════════════ */}
        <TouchableOpacity style={s.logoutBtn} onPress={handleLogout} activeOpacity={0.78}>
          <Ionicons name="log-out-outline" size={18} color="#f87171" />
          <Text style={s.logoutText}>Cerrar Sesión</Text>
        </TouchableOpacity>

        <Text style={s.footer}>Qoricash © 2025</Text>

      </ScrollView>

      {/* ══ Modal: Cambiar Contraseña ════════════════════════════════════ */}
      <GlassModal
        visible={changePasswordVisible}
        onClose={() => { setChangePasswordVisible(false); setCurrentPassword(''); setNewPassword(''); setConfirmPassword(''); }}
        title="Cambiar Contraseña"
        footer={
          <View style={s.modalActions}>
            <TouchableOpacity style={s.modalBtnSecondary} onPress={() => { setChangePasswordVisible(false); setCurrentPassword(''); setNewPassword(''); setConfirmPassword(''); }}>
              <Text style={s.modalBtnSecondaryText}>Cancelar</Text>
            </TouchableOpacity>
            <TouchableOpacity style={s.modalBtnPrimary} onPress={handleChangePassword}>
              <Text style={s.modalBtnPrimaryText}>Guardar</Text>
            </TouchableOpacity>
          </View>
        }
      >
        <View style={s.modalBody}>
          <Text style={s.inputLabel}>Contraseña actual</Text>
          <View style={s.inputRow}>
            <TextInput style={s.inputField} value={currentPassword} onChangeText={setCurrentPassword} secureTextEntry={!showCurrentPwd} placeholder="••••••••" placeholderTextColor="rgba(255,255,255,0.25)" />
            <TouchableOpacity onPress={() => setShowCurrentPwd(!showCurrentPwd)}>
              <Ionicons name={showCurrentPwd ? 'eye-off-outline' : 'eye-outline'} size={18} color="rgba(255,255,255,0.4)" />
            </TouchableOpacity>
          </View>

          <Text style={s.inputLabel}>Nueva contraseña</Text>
          <View style={s.inputRow}>
            <TextInput style={s.inputField} value={newPassword} onChangeText={setNewPassword} secureTextEntry={!showNewPwd} placeholder="Mínimo 8 caracteres" placeholderTextColor="rgba(255,255,255,0.25)" />
            <TouchableOpacity onPress={() => setShowNewPwd(!showNewPwd)}>
              <Ionicons name={showNewPwd ? 'eye-off-outline' : 'eye-outline'} size={18} color="rgba(255,255,255,0.4)" />
            </TouchableOpacity>
          </View>

          <Text style={s.inputLabel}>Confirmar contraseña</Text>
          <View style={s.inputRow}>
            <TextInput style={s.inputField} value={confirmPassword} onChangeText={setConfirmPassword} secureTextEntry={!showConfirmPwd} placeholder="Repite la nueva contraseña" placeholderTextColor="rgba(255,255,255,0.25)" />
            <TouchableOpacity onPress={() => setShowConfirmPwd(!showConfirmPwd)}>
              <Ionicons name={showConfirmPwd ? 'eye-off-outline' : 'eye-outline'} size={18} color="rgba(255,255,255,0.4)" />
            </TouchableOpacity>
          </View>
          <Text style={s.inputHint}>La contraseña debe tener al menos 8 caracteres</Text>
        </View>
      </GlassModal>

      {/* ══ Modal: Editar Información ════════════════════════════════════ */}
      <GlassModal
        visible={editInfoVisible}
        onClose={() => { setEditInfoVisible(false); setPhone(client?.phone || ''); setEmail(client?.email || ''); }}
        title="Editar Información"
        footer={
          <View style={s.modalActions}>
            <TouchableOpacity style={s.modalBtnSecondary} onPress={() => { setEditInfoVisible(false); }}>
              <Text style={s.modalBtnSecondaryText}>Cancelar</Text>
            </TouchableOpacity>
            <TouchableOpacity style={s.modalBtnPrimary} onPress={handleEditInfo}>
              <Text style={s.modalBtnPrimaryText}>Guardar</Text>
            </TouchableOpacity>
          </View>
        }
      >
        <View style={s.modalBody}>
          <Text style={s.inputLabel}>Teléfono</Text>
          <View style={s.inputRow}>
            <Ionicons name="call-outline" size={16} color="#9CA3AF" style={{ marginRight: 8 }} />
            <TextInput style={s.inputField} value={phone} onChangeText={setPhone} keyboardType="phone-pad" maxLength={9} placeholder="9XXXXXXXX" placeholderTextColor="#C4C9D4" />
          </View>

          <Text style={s.inputLabel}>Email</Text>
          <View style={s.inputRow}>
            <Ionicons name="mail-outline" size={16} color="#9CA3AF" style={{ marginRight: 8 }} />
            <TextInput style={s.inputField} value={email} onChangeText={setEmail} keyboardType="email-address" autoCapitalize="none" placeholder="correo@ejemplo.com" placeholderTextColor="#C4C9D4" />
          </View>
          <Text style={s.inputHint}>El teléfono debe tener 9 dígitos y comenzar con 9</Text>
        </View>
      </GlassModal>

      {/* ══ Modal: Ayuda y Soporte ════════════════════════════════════════ */}
      <GlassModal
        visible={helpVisible}
        onClose={() => setHelpVisible(false)}
        title="Ayuda y Soporte"
        footer={
          <TouchableOpacity style={[s.modalBtnPrimary, { width: '100%' }]} onPress={() => setHelpVisible(false)}>
            <Text style={s.modalBtnPrimaryText}>Cerrar</Text>
          </TouchableOpacity>
        }
      >
        <View style={s.modalBody}>
          <Text style={s.helpDesc}>Contáctanos a través de los siguientes canales:</Text>

          <TouchableOpacity style={s.contactRow} onPress={openWhatsApp} activeOpacity={0.78}>
            <View style={[s.contactIcon, { backgroundColor: 'rgba(37,211,102,0.15)', borderColor: 'rgba(37,211,102,0.3)' }]}>
              <Ionicons name="logo-whatsapp" size={20} color="#25D366" />
            </View>
            <View style={s.contactTexts}>
              <Text style={s.contactTitle}>WhatsApp</Text>
              <Text style={s.contactSub}>Chatea con nosotros</Text>
            </View>
            <Ionicons name="chevron-forward" size={16} color="rgba(255,255,255,0.22)" />
          </TouchableOpacity>

          <View style={s.rowLine} />

          <TouchableOpacity style={s.contactRow} onPress={openEmail} activeOpacity={0.78}>
            <View style={[s.contactIcon, { backgroundColor: 'rgba(96,165,250,0.15)', borderColor: 'rgba(96,165,250,0.3)' }]}>
              <Ionicons name="mail-outline" size={20} color="#60a5fa" />
            </View>
            <View style={s.contactTexts}>
              <Text style={s.contactTitle}>Email</Text>
              <Text style={s.contactSub}>info@qoricash.pe</Text>
            </View>
            <Ionicons name="chevron-forward" size={16} color="rgba(255,255,255,0.22)" />
          </TouchableOpacity>

          <View style={s.infoBox}>
            <Ionicons name="time-outline" size={14} color="rgba(255,255,255,0.35)" />
            <Text style={s.infoBoxText}>Horario: Lunes a Viernes 9:00 AM - 6:00 PM</Text>
          </View>
        </View>
      </GlassModal>

      {/* ══ Modal: Agregar Cuenta Bancaria ════════════════════════════════ */}
      <GlassModal
        visible={addAccountVisible}
        onClose={() => setAddAccountVisible(false)}
        title="Agregar Cuenta Bancaria"
        footer={
          <View style={s.modalActions}>
            <TouchableOpacity style={s.modalBtnSecondary} onPress={() => setAddAccountVisible(false)}>
              <Text style={s.modalBtnSecondaryText}>Cancelar</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[s.modalBtnPrimary, addingAccount && { opacity: 0.5 }]} onPress={handleAddBankAccount} disabled={addingAccount}>
              {addingAccount ? <ActivityIndicator color="#fff" size="small" /> : <Text style={s.modalBtnPrimaryText}>Agregar</Text>}
            </TouchableOpacity>
          </View>
        }
      >
        <View style={s.modalBody}>
          {/* Origen */}
          <Text style={s.inputLabel}>Origen</Text>
          <View style={{ flexDirection: 'row', gap: 20, marginBottom: 2, marginTop: 4 }}>
            {['Lima', 'Provincia'].map(o => (
              <TouchableOpacity
                key={o}
                style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}
                onPress={() => { setNewAccountOrigen(o); setNewAccountBank(''); }}
                activeOpacity={0.7}
              >
                <View style={{
                  width: 20, height: 20, borderRadius: 10,
                  borderWidth: 2,
                  borderColor: newAccountOrigen === o ? '#0D1117' : '#D1D5DB',
                  backgroundColor: newAccountOrigen === o ? '#0D1117' : 'transparent',
                  alignItems: 'center', justifyContent: 'center',
                }}>
                  {newAccountOrigen === o && (
                    <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: '#FFFFFF' }} />
                  )}
                </View>
                <Text style={{ fontSize: 14, fontWeight: '500', color: newAccountOrigen === o ? '#0D1117' : '#6B7280' }}>{o}</Text>
              </TouchableOpacity>
            ))}
          </View>

          {/* Banco */}
          <Text style={s.inputLabel}>Banco</Text>
          <TouchableOpacity style={s.inputRow} onPress={() => setBankMenuVisible(!bankMenuVisible)}>
            <TextInput style={s.inputField} value={newAccountBank || 'Seleccionar banco...'} editable={false} pointerEvents="none" placeholderTextColor="#C4C9D4" />
            <Ionicons name={bankMenuVisible ? 'chevron-up' : 'chevron-down'} size={16} color="#9CA3AF" />
          </TouchableOpacity>
          {bankMenuVisible && (
            <View style={s.bankMenu}>
              {getAvailableBanks().map(bank => (
                <TouchableOpacity key={bank} style={s.bankMenuItem} onPress={() => { setNewAccountBank(bank); setBankMenuVisible(false); }}>
                  <Text style={[s.bankMenuText, newAccountBank === bank && { color: "#0D1117" }]}>{bank}</Text>
                  {newAccountBank === bank && <Ionicons name="checkmark" size={14} color="#0D1117" />}
                </TouchableOpacity>
              ))}
            </View>
          )}

          {newAccountBank === 'Otros' && (
            <>
              <Text style={s.inputLabel}>Nombre del banco</Text>
              <View style={s.inputRow}>
                <TextInput style={s.inputField} value={newAccountBankCustom} onChangeText={setNewAccountBankCustom} placeholder="Nombre del banco" placeholderTextColor="#C4C9D4" />
              </View>
            </>
          )}

          {/* Tipo */}
          <Text style={s.inputLabel}>Tipo de cuenta</Text>
          <View style={{ flexDirection: 'row', gap: 20, marginBottom: 2, marginTop: 4 }}>
            {['Ahorro', 'Corriente'].map(t => (
              <TouchableOpacity
                key={t}
                style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}
                onPress={() => setNewAccountType(t)}
                activeOpacity={0.7}
              >
                <View style={{
                  width: 20, height: 20, borderRadius: 10,
                  borderWidth: 2,
                  borderColor: newAccountType === t ? '#0D1117' : '#D1D5DB',
                  backgroundColor: newAccountType === t ? '#0D1117' : 'transparent',
                  alignItems: 'center', justifyContent: 'center',
                }}>
                  {newAccountType === t && (
                    <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: '#FFFFFF' }} />
                  )}
                </View>
                <Text style={{ fontSize: 14, fontWeight: '500', color: newAccountType === t ? '#0D1117' : '#6B7280' }}>{t}</Text>
              </TouchableOpacity>
            ))}
          </View>

          {/* Moneda */}
          <Text style={s.inputLabel}>Moneda</Text>
          <View style={s.segmented}>
            {['S/', 'USD'].map(c => (
              <TouchableOpacity key={c} style={[s.segBtn, newAccountCurrency === c && s.segBtnActive]} onPress={() => setNewAccountCurrency(c)}>
                <Text style={[s.segBtnText, newAccountCurrency === c && s.segBtnTextActive]}>{c}</Text>
              </TouchableOpacity>
            ))}
          </View>

          {/* Número */}
          {needsCCI() ? (
            <>
              <Text style={s.inputLabel}>CCI (20 dígitos)</Text>
              <View style={s.inputRow}>
                <TextInput style={s.inputField} value={newAccountCCI} onChangeText={setNewAccountCCI} keyboardType="numeric" maxLength={20} placeholder="00000000000000000000" placeholderTextColor="#C4C9D4" />
              </View>
            </>
          ) : (
            <>
              <Text style={s.inputLabel}>Número de cuenta</Text>
              <View style={s.inputRow}>
                <TextInput style={s.inputField} value={newAccountNumber} onChangeText={setNewAccountNumber} keyboardType="numeric" placeholder="Número de cuenta" placeholderTextColor="#C4C9D4" />
              </View>
            </>
          )}
        </View>
      </GlassModal>

    </View>
  );
};

// ─── Styles ───────────────────────────────────────────────────────────────────
const GLASS_BG2    = 'rgba(255,255,255,0.18)';
const GLASS_BORDER2 = 'rgba(255,255,255,0.15)';
const GREEN2 = '#22c55e';

const s = StyleSheet.create({
  root:    { flex: 1 },
  scroll:  { flex: 1 },
  content: { paddingHorizontal: 20 },

  // ── Header fijo ──
  fixedHeader: {
    paddingHorizontal: 20,
    paddingBottom: 14,
    backgroundColor: '#F5F7FA',
  },
  headerLabel: { fontSize: 12, fontWeight: '400', color: '#9CA3AF', letterSpacing: 0.2, marginBottom: 5 },
  headerRow:   { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', width: '100%' },
  headerName:  { fontSize: 26, fontWeight: '800', color: '#0D1117', letterSpacing: -0.5 },
  headerLogo:  { width: 28, height: 28 },

  // ── Strip wrapper ──
  stripWrap: { marginBottom: 24 },

  // Info strip
  strip: {
    flexDirection: 'row',
    width: '100%',
    backgroundColor: '#0D1117',
    borderWidth: 1, borderColor: '#0D1117',
    borderRadius: 18,
    paddingVertical: 14, paddingHorizontal: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.15,
    shadowRadius: 8,
    elevation: 2,
  },
  stripItem:   { flex: 1, alignItems: 'center' },
  stripLabel:  { fontSize: 9.5, color: 'rgba(255,255,255,0.45)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: 0.6, marginBottom: 5 },
  stripValue:  { fontSize: 12.5, color: '#fff', fontWeight: '600' },
  stripDivider: { width: StyleSheet.hairlineWidth * 2, backgroundColor: 'rgba(255,255,255,0.15)', marginVertical: 2 },

  // ── Cards ──
  card: {
    backgroundColor: '#FFFFFF',
    borderWidth: 1, borderColor: 'rgba(0,0,0,0.06)',
    borderRadius: 20,
    marginBottom: 14,
    overflow: 'hidden',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 10,
    elevation: 3,
  },
  cardHeader: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    paddingHorizontal: 16, paddingTop: 16, paddingBottom: 12,
  },
  cardTitle: { flex: 1, fontSize: 14, fontWeight: '700', color: '#0D1117' },
  editBtn: {
    width: 30, height: 30, borderRadius: 15,
    backgroundColor: '#0D1117',
    borderWidth: 0,
    alignItems: 'center', justifyContent: 'center',
  },

  // ── Rows ──
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 16, paddingVertical: 14 },
  rowIcon: {
    width: 32, height: 32, borderRadius: 10,
    backgroundColor: '#F3F4F6',
    borderWidth: 1, borderColor: 'rgba(0,0,0,0.06)',
    alignItems: 'center', justifyContent: 'center',
    flexShrink: 0,
  },
  rowTexts: { flex: 1 },
  rowTitle:  { fontSize: 13.5, color: '#374151', fontWeight: '600', marginBottom: 2 },
  rowSub:    { fontSize: 11.5, color: '#9CA3AF', lineHeight: 16 },
  rowLine:   { height: StyleSheet.hairlineWidth, backgroundColor: 'rgba(0,0,0,0.06)', marginHorizontal: 16 },

  // Bank rows
  bankRow: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 16, paddingVertical: 14 },
  bankIcon: {
    width: 36, height: 36, borderRadius: 18,
    backgroundColor: '#F3F4F6', borderWidth: 1, borderColor: 'rgba(0,0,0,0.06)',
    alignItems: 'center', justifyContent: 'center',
  },
  bankTexts: { flex: 1 },
  bankName:   { fontSize: 13, fontWeight: '700', color: '#374151', marginBottom: 2 },
  bankDetail: { fontSize: 11, color: '#9CA3AF' },
  bankDelete: { padding: 6 },

  // Empty / add
  emptyText: { fontSize: 13, color: '#9CA3AF', textAlign: 'center', paddingVertical: 16, paddingHorizontal: 16 },
  addBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 7,
    margin: 12, paddingVertical: 12,
    backgroundColor: '#0D1117',
    borderRadius: 12, borderWidth: 0,
  },
  addBtnText: { fontSize: 13, fontWeight: '600', color: '#FFFFFF' },

  // ── Logout ──
  logoutBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 9,
    paddingVertical: 16,
    backgroundColor: 'rgba(248,113,113,0.08)',
    borderWidth: 1, borderColor: 'rgba(248,113,113,0.2)',
    borderRadius: 18,
    marginBottom: 18,
  },
  logoutText: { fontSize: 15, fontWeight: '700', color: '#f87171', letterSpacing: 0.2 },

  footer: { fontSize: 10.5, color: '#D1D5DB', textAlign: 'center', marginBottom: 8 },

  // ── Modal ──
  modalBackdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.62)', justifyContent: 'center', alignItems: 'center', padding: 24 },
  modalBox: {
    width: '100%', maxHeight: '88%',
    borderRadius: 20, overflow: 'hidden',
    backgroundColor: '#FFFFFF',
    shadowColor: '#000', shadowOffset: { width: 0, height: 12 }, shadowOpacity: 0.18, shadowRadius: 28, elevation: 20,
  },
  modalHeader: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    backgroundColor: '#0D1117', paddingHorizontal: 20, paddingVertical: 16,
  },
  modalTitle: { fontSize: 16, fontWeight: '800', color: '#FFFFFF', letterSpacing: 0.1 },
  modalCloseBtn: { width: 28, height: 28, borderRadius: 14, backgroundColor: 'rgba(255,255,255,0.10)', alignItems: 'center', justifyContent: 'center' },
  modalBodyWrap: { paddingHorizontal: 20, paddingTop: 16, paddingBottom: 20 },
  modalBorder: {},
  modalDivider: { width: '100%', height: StyleSheet.hairlineWidth, backgroundColor: 'rgba(0,0,0,0.07)', marginBottom: 18 },
  modalBody:   { width: '100%', gap: 4 },
  modalActions: { flexDirection: 'row', gap: 10, width: '100%', marginTop: 16 },
  modalBtnSecondary: {
    flex: 1, paddingVertical: 14, borderRadius: 14,
    backgroundColor: 'transparent', borderWidth: 1, borderColor: 'rgba(0,0,0,0.15)', alignItems: 'center',
  },
  modalBtnSecondaryText: { fontSize: 14, fontWeight: '600', color: '#374151' },
  modalBtnPrimary: {
    flex: 1, paddingVertical: 14, borderRadius: 14,
    backgroundColor: '#0D1117', alignItems: 'center', justifyContent: 'center',
  },
  modalBtnPrimaryText: { fontSize: 14, fontWeight: '700', color: '#FFFFFF' },

  // Form inputs
  inputLabel: { fontSize: 11, fontWeight: '600', color: '#6B7280', textTransform: 'uppercase', letterSpacing: 0.6, marginTop: 14, marginBottom: 6 },
  inputRow: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: '#F9FAFB', borderWidth: 1, borderColor: 'rgba(0,0,0,0.08)',
    borderRadius: 13, paddingHorizontal: 14, paddingVertical: 12,
  },
  inputField: { flex: 1, color: '#0D1117', fontSize: 14 },
  inputHint: { fontSize: 11, color: '#9CA3AF', marginTop: 8 },

  // Segmented
  segmented: { flexDirection: 'row', gap: 6, marginBottom: 2 },
  segBtn: {
    flex: 1, paddingVertical: 10, borderRadius: 12, alignItems: 'center',
    backgroundColor: '#F3F4F6', borderWidth: 1, borderColor: 'rgba(0,0,0,0.08)',
  },
  segBtnActive: { backgroundColor: '#0D1117', borderColor: '#0D1117' },
  segBtnText: { fontSize: 13, fontWeight: '600', color: '#6B7280' },
  segBtnTextActive: { color: '#fff', fontWeight: '700' },

  // Bank menu
  bankMenu: {
    backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: 'rgba(0,0,0,0.08)',
    borderRadius: 14, marginTop: 4, overflow: 'hidden',
    shadowColor: '#000', shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.08, shadowRadius: 12, elevation: 4,
  },
  bankMenuItem: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 16, paddingVertical: 12,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: 'rgba(0,0,0,0.06)',
  },
  bankMenuText: { fontSize: 14, color: '#374151', fontWeight: '500' },

  // Help modal
  helpDesc: { fontSize: 13, color: 'rgba(255,255,255,0.45)', marginBottom: 16 },
  contactRow: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 12 },
  contactIcon: { width: 42, height: 42, borderRadius: 21, borderWidth: 1, alignItems: 'center', justifyContent: 'center' },
  contactTexts: { flex: 1 },
  contactTitle: { fontSize: 14, fontWeight: '700', color: 'rgba(255,255,255,0.85)', marginBottom: 2 },
  contactSub:   { fontSize: 12, color: 'rgba(255,255,255,0.4)' },
  infoBox: { flexDirection: 'row', gap: 8, alignItems: 'center', marginTop: 16, padding: 12, backgroundColor: GLASS_BG2, borderRadius: 12, borderWidth: 1, borderColor: GLASS_BORDER2 },
  infoBoxText: { flex: 1, fontSize: 12, color: 'rgba(255,255,255,0.4)', lineHeight: 18 },

  // ── Referral card ──
  referralCard: {
    backgroundColor: '#1d4ed8',
    borderColor: '#2563eb',
  },
  referralCodeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 6,
    marginBottom: 10,
    paddingHorizontal: 14,
  },
  referralCodeWrap: {
    flex: 1,
    backgroundColor: 'rgba(255,255,255,0.1)',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.2)',
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  referralCodeLabel: {
    fontSize: 9,
    color: 'rgba(255,255,255,0.6)',
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 1,
  },
  referralCode: {
    fontSize: 18,
    fontWeight: '800',
    color: '#fff',
    letterSpacing: 3,
  },
  referralBtn: {
    width: 36,
    height: 36,
    borderRadius: 10,
    backgroundColor: 'rgba(255,255,255,0.12)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.2)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  referralStatsRow: {
    flexDirection: 'row',
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.15)',
    marginHorizontal: 14,
    marginBottom: 10,
  },
  referralStat: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: 8,
  },
  referralStatDivider: {
    width: 1,
    backgroundColor: 'rgba(255,255,255,0.2)',
    marginVertical: 8,
  },
  referralStatValue: {
    fontSize: 15,
    fontWeight: '700',
    color: '#fff',
    marginBottom: 2,
  },
  referralStatLabel: {
    fontSize: 9,
    color: 'rgba(255,255,255,0.6)',
    textTransform: 'uppercase',
    letterSpacing: 0.4,
  },
  referralHint: {
    fontSize: 11,
    color: 'rgba(255,255,255,0.65)',
    lineHeight: 15,
    textAlign: 'center',
    paddingHorizontal: 14,
    marginBottom: 14,
  },
});
