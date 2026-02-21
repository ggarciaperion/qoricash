import React, { useEffect, useRef, useState } from 'react';
import {
  View,
  StyleSheet,
  Animated,
  Easing,
  Image,
  Dimensions,
} from 'react-native';
import { Text } from 'react-native-paper';
import { Colors } from '../constants/colors';
import { LinearGradient } from 'expo-linear-gradient';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

const { width, height } = Dimensions.get('window');

interface LoginLoadingScreenProps {
  visible: boolean;
  onComplete?: () => void;
}

export const LoginLoadingScreen: React.FC<LoginLoadingScreenProps> = ({
  visible,
  onComplete,
}) => {
  // Estado interno para controlar el renderizado
  const [shouldRender, setShouldRender] = useState(false);

  // Animaciones
  const fadeAnim = useRef(new Animated.Value(0)).current;
  const scaleAnim = useRef(new Animated.Value(0.3)).current;
  const rotateAnim = useRef(new Animated.Value(0)).current;
  const checkmarkScale = useRef(new Animated.Value(0)).current;
  const checkmarkOpacity = useRef(new Animated.Value(0)).current;

  const animationInProgressRef = useRef(false);

  useEffect(() => {
    // Solo iniciar animación si visible es true y no hay animación en progreso
    if (visible && !animationInProgressRef.current) {
      // Marcar que la animación está en progreso
      animationInProgressRef.current = true;

      // Mostrar el componente
      setShouldRender(true);

      // Reset animations
      fadeAnim.setValue(0);
      scaleAnim.setValue(0.3);
      rotateAnim.setValue(0);
      checkmarkScale.setValue(0);
      checkmarkOpacity.setValue(0);

      // Secuencia de animaciones
      Animated.sequence([
        // 1. Fade in del fondo y logo (400ms)
        Animated.parallel([
          Animated.timing(fadeAnim, {
            toValue: 1,
            duration: 400,
            useNativeDriver: true,
            easing: Easing.out(Easing.ease),
          }),
          Animated.spring(scaleAnim, {
            toValue: 1,
            tension: 50,
            friction: 7,
            useNativeDriver: true,
          }),
        ]),

        // 2. Rotación del ícono de validación (2000ms - 2 rotaciones completas)
        // Rotación 1
        Animated.timing(rotateAnim, {
          toValue: 1,
          duration: 1000,
          useNativeDriver: true,
          easing: Easing.linear,
        }),
        // Reset para rotación 2
        Animated.timing(rotateAnim, {
          toValue: 0,
          duration: 0,
          useNativeDriver: true,
        }),
        // Rotación 2
        Animated.timing(rotateAnim, {
          toValue: 1,
          duration: 1000,
          useNativeDriver: true,
          easing: Easing.linear,
        }),

        // 3. Mostrar checkmark de éxito (300ms)
        Animated.parallel([
          Animated.spring(checkmarkScale, {
            toValue: 1,
            tension: 100,
            friction: 5,
            useNativeDriver: true,
          }),
          Animated.timing(checkmarkOpacity, {
            toValue: 1,
            duration: 300,
            useNativeDriver: true,
          }),
        ]),

        // 4. Pausa antes de completar (500ms)
        Animated.delay(500),
      ]).start(() => {
        // Fade out (300ms)
        Animated.timing(fadeAnim, {
          toValue: 0,
          duration: 300,
          useNativeDriver: true,
        }).start(() => {
          // Marcar que la animación terminó
          animationInProgressRef.current = false;

          // Ocultar el componente
          setShouldRender(false);

          // Llamar onComplete
          if (onComplete) {
            onComplete();
          }
        });
      });
    }
  }, [visible]);

  if (!shouldRender) return null;

  const spin = rotateAnim.interpolate({
    inputRange: [0, 1],
    outputRange: ['0deg', '360deg'],
  });

  return (
    <Animated.View
      style={[styles.container, { opacity: fadeAnim }]}
      pointerEvents={visible ? 'auto' : 'none'}
    >
      <LinearGradient
        colors={[Colors.secondary, Colors.secondaryLight]}
        style={styles.gradient}
      >
        <View style={styles.content}>
          {/* Logo */}
          <Animated.View
            style={[
              styles.logoContainer,
              {
                transform: [{ scale: scaleAnim }],
              },
            ]}
          >
            <Image
              source={require('../../assets/logo-principal.png')}
              style={styles.logo}
              resizeMode="contain"
            />
          </Animated.View>

          {/* Ícono de validación con rotación */}
          <Animated.View
            style={[
              styles.iconContainer,
              {
                transform: [{ rotate: spin }],
                opacity: checkmarkOpacity.interpolate({
                  inputRange: [0, 1],
                  outputRange: [1, 0],
                }),
              },
            ]}
          >
            <Icon name="shield-check" size={64} color={Colors.primary} />
          </Animated.View>

          {/* Checkmark de éxito */}
          <Animated.View
            style={[
              styles.checkmarkContainer,
              {
                opacity: checkmarkOpacity,
                transform: [{ scale: checkmarkScale }],
              },
            ]}
          >
            <View style={styles.checkmarkCircle}>
              <Icon name="check-bold" size={48} color={Colors.secondary} />
            </View>
          </Animated.View>

          {/* Texto */}
          <Animated.View style={{ opacity: fadeAnim }}>
            <Text style={styles.title}>Validando acceso</Text>
            <Text style={styles.subtitle}>Por favor espera un momento...</Text>
          </Animated.View>

          {/* Indicador de progreso con puntos animados */}
          <View style={styles.dotsContainer}>
            {[0, 1, 2].map((index) => (
              <Animated.View
                key={index}
                style={[
                  styles.dot,
                  {
                    opacity: fadeAnim,
                    transform: [
                      {
                        translateY: rotateAnim.interpolate({
                          inputRange: [0, 0.5, 1],
                          outputRange: [0, -10, 0],
                        }),
                      },
                    ],
                  },
                ]}
              />
            ))}
          </View>
        </View>
      </LinearGradient>
    </Animated.View>
  );
};

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    zIndex: 9999,
  },
  gradient: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  content: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  logoContainer: {
    marginBottom: 40,
    width: width * 0.5,
    height: width * 0.3,
    alignItems: 'center',
    justifyContent: 'center',
  },
  logo: {
    width: '100%',
    height: '100%',
  },
  iconContainer: {
    marginVertical: 30,
  },
  checkmarkContainer: {
    position: 'absolute',
    top: height * 0.35,
  },
  checkmarkCircle: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: Colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: Colors.primary,
    shadowOffset: {
      width: 0,
      height: 4,
    },
    shadowOpacity: 0.5,
    shadowRadius: 8,
    elevation: 8,
  },
  title: {
    fontSize: 24,
    fontWeight: '600',
    color: Colors.textOnSecondary,
    marginTop: 20,
    marginBottom: 8,
    textAlign: 'center',
  },
  subtitle: {
    fontSize: 16,
    color: Colors.textMuted,
    textAlign: 'center',
    marginBottom: 30,
  },
  dotsContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    marginTop: 20,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: Colors.primary,
  },
});
