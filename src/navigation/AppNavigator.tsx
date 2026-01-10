import React, { useState, useEffect } from 'react';
import { createStackNavigator } from '@react-navigation/stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { NavigationContainer } from '@react-navigation/native';
import { Icon } from 'react-native-paper';
import AsyncStorage from '@react-native-async-storage/async-storage';

import { useAuth } from '../contexts/AuthContext';
import { Colors } from '../constants/colors';
import { STORAGE_KEYS } from '../constants/config';

// Auth Screens
import { LoginScreen } from '../screens/LoginScreen';
import { PublicCalculatorScreen } from '../screens/PublicCalculatorScreen';
import { ClientTypeSelectionScreen } from '../screens/ClientTypeSelectionScreen';
import { RegisterScreen } from '../screens/RegisterScreen';
import { ChangePasswordScreen } from '../screens/ChangePasswordScreen';
import { VerifyIdentityScreen } from '../screens/VerifyIdentityScreen';

// Main Screens
import { HomeScreen } from '../screens/HomeScreen';
import { NewOperationScreen } from '../screens/NewOperationScreen';
import { TransferScreen } from '../screens/TransferScreen';
import { ReceiveScreen } from '../screens/ReceiveScreen';
import { OperationDetailScreen } from '../screens/OperationDetailScreen';
import { HistoryScreen } from '../screens/HistoryScreen';
import { ProfileScreen } from '../screens/ProfileScreen';
import { LogsScreen } from '../screens/LogsScreen';

const Stack = createStackNavigator();
const Tab = createBottomTabNavigator();

// Tab Navigator for authenticated users
const TabNavigator = () => {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        tabBarIcon: ({ focused, color, size }) => {
          let iconName = 'home';

          if (route.name === 'HomeTab') {
            iconName = 'home';
          } else if (route.name === 'HistoryTab') {
            iconName = 'history';
          } else if (route.name === 'ProfileTab') {
            iconName = 'account';
          }

          return <Icon source={iconName} size={size} color={color} />;
        },
        tabBarActiveTintColor: Colors.success,
        tabBarInactiveTintColor: Colors.textMuted,
      })}
    >
      <Tab.Screen
        name="HomeTab"
        component={HomeScreen}
        options={{
          headerShown: false,
        }}
      />
      <Tab.Screen
        name="HistoryTab"
        component={HistoryScreen}
        options={{
          title: 'Historial',
          headerTitle: 'Historial de Operaciones',
        }}
      />
      <Tab.Screen
        name="ProfileTab"
        component={ProfileScreen}
        options={{
          title: 'Perfil',
          headerTitle: 'Mi Perfil',
        }}
      />
    </Tab.Navigator>
  );
};

// Auth Navigator
const AuthNavigator = () => {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="PublicCalculator" component={PublicCalculatorScreen} />
      <Stack.Screen name="Login" component={LoginScreen} />
      <Stack.Screen
        name="ClientTypeSelection"
        component={ClientTypeSelectionScreen}
        options={{
          headerShown: false,
        }}
      />
      <Stack.Screen
        name="Register"
        component={RegisterScreen}
        options={{
          headerShown: false,
        }}
      />
    </Stack.Navigator>
  );
};

// Main Navigator
const MainNavigator = () => {
  return (
    <Stack.Navigator>
      <Stack.Screen
        name="Tabs"
        component={TabNavigator}
        options={{ headerShown: false }}
      />
      <Stack.Screen
        name="NewOperation"
        component={NewOperationScreen}
        options={{
          headerShown: false,
        }}
      />
      <Stack.Screen
        name="Transfer"
        component={TransferScreen}
        options={{
          headerShown: false,
        }}
      />
      <Stack.Screen
        name="Receive"
        component={ReceiveScreen}
        options={{
          headerShown: false,
        }}
      />
      <Stack.Screen
        name="OperationDetail"
        component={OperationDetailScreen}
        options={{
          headerShown: false,
        }}
      />
      <Stack.Screen
        name="ChangePassword"
        component={ChangePasswordScreen}
        options={{
          title: 'Cambiar Contraseña',
          headerTintColor: Colors.primary,
        }}
      />
      <Stack.Screen
        name="VerifyIdentity"
        component={VerifyIdentityScreen}
        options={{
          title: 'Validación de Identidad',
          headerTintColor: Colors.primary,
        }}
      />
      <Stack.Screen
        name="Logs"
        component={LogsScreen}
        options={{
          title: 'Logs del Sistema',
          headerTintColor: Colors.primary,
        }}
      />
    </Stack.Navigator>
  );
};

// Root Navigator
export const AppNavigator = () => {
  const { isAuthenticated, loading, client } = useAuth();
  const [requiresPasswordChange, setRequiresPasswordChange] = useState(false);

  useEffect(() => {
    checkPasswordChangeRequired();
  }, [isAuthenticated, client]);

  const checkPasswordChangeRequired = async () => {
    try {
      const flag = await AsyncStorage.getItem(STORAGE_KEYS.REQUIRES_PASSWORD_CHANGE);
      setRequiresPasswordChange(flag === 'true');
    } catch (error) {
      console.error('Error checking password change:', error);
      setRequiresPasswordChange(false);
    }
  };

  if (loading) {
    return null; // You can add a splash screen here
  }

  return (
    <NavigationContainer>
      {isAuthenticated ? (
        requiresPasswordChange ? (
          <Stack.Navigator screenOptions={{ headerShown: false }}>
            <Stack.Screen
              name="ChangePassword"
              component={ChangePasswordScreen}
              initialParams={{ isFirstLogin: true, dni: client?.dni }}
              options={{
                headerShown: true,
                title: 'Cambiar Contraseña',
                headerTintColor: Colors.primary,
                headerLeft: () => null, // Evitar que puedan regresar
              }}
            />
          </Stack.Navigator>
        ) : (
          <MainNavigator />
        )
      ) : (
        <AuthNavigator />
      )}
    </NavigationContainer>
  );
};
