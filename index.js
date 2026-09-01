// Polyfill window.location para Metro HMR en React Native (Expo Go)
if (typeof window !== 'undefined' && !window.location) {
  window.location = { protocol: 'http:' };
}

import { registerRootComponent } from 'expo';

import App from './App';

// registerRootComponent calls AppRegistry.registerComponent('main', () => App);
// It also ensures that whether you load the app in Expo Go or in a native build,
// the environment is set up appropriately
registerRootComponent(App);
