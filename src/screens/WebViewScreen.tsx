import React, { useState } from 'react';
import { View, StyleSheet, ActivityIndicator, TouchableOpacity, Text } from 'react-native';
import { WebView } from 'react-native-webview';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

const GREEN  = '#22c55e';
const BG     = '#080c14';

const INJECTED_CSS = `
(function() {
  var style = document.createElement('style');
  style.innerHTML = \`
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    *, *::before, *::after {
      box-sizing: border-box;
      -webkit-font-smoothing: antialiased;
    }

    html, body {
      background-color: #080c14 !important;
      color: rgba(255,255,255,0.82) !important;
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
      font-size: 15px !important;
      line-height: 1.7 !important;
      margin: 0 !important;
      padding: 0 !important;
    }

    body {
      padding: 24px 20px 48px !important;
      max-width: 100% !important;
    }

    h1, h2, h3, h4, h5, h6 {
      color: #ffffff !important;
      font-weight: 700 !important;
      line-height: 1.3 !important;
      margin-top: 28px !important;
      margin-bottom: 10px !important;
      letter-spacing: -0.2px !important;
    }

    h1 { font-size: 22px !important; font-weight: 800 !important; color: #22c55e !important; margin-top: 0 !important; }
    h2 { font-size: 17px !important; color: rgba(255,255,255,0.95) !important; }
    h3 { font-size: 15px !important; color: rgba(255,255,255,0.85) !important; }

    p {
      color: rgba(255,255,255,0.68) !important;
      margin-bottom: 14px !important;
      margin-top: 0 !important;
    }

    ul, ol {
      color: rgba(255,255,255,0.68) !important;
      padding-left: 20px !important;
      margin-bottom: 14px !important;
    }

    li {
      margin-bottom: 6px !important;
    }

    a {
      color: #22c55e !important;
      text-decoration: none !important;
    }

    strong, b {
      color: rgba(255,255,255,0.9) !important;
      font-weight: 600 !important;
    }

    em, i {
      color: rgba(255,255,255,0.6) !important;
    }

    hr {
      border: none !important;
      border-top: 1px solid rgba(255,255,255,0.1) !important;
      margin: 24px 0 !important;
    }

    table {
      width: 100% !important;
      border-collapse: collapse !important;
      margin-bottom: 16px !important;
    }

    th {
      background: rgba(34,197,94,0.1) !important;
      color: #22c55e !important;
      font-weight: 700 !important;
      padding: 10px 12px !important;
      text-align: left !important;
      border: 1px solid rgba(255,255,255,0.1) !important;
    }

    td {
      padding: 9px 12px !important;
      border: 1px solid rgba(255,255,255,0.08) !important;
      color: rgba(255,255,255,0.68) !important;
    }

    tr:nth-child(even) td {
      background: rgba(255,255,255,0.03) !important;
    }

    blockquote {
      border-left: 3px solid #22c55e !important;
      margin: 16px 0 !important;
      padding: 10px 16px !important;
      background: rgba(34,197,94,0.06) !important;
      border-radius: 0 8px 8px 0 !important;
      color: rgba(255,255,255,0.65) !important;
    }

    code, pre {
      background: rgba(255,255,255,0.06) !important;
      color: #22c55e !important;
      border-radius: 6px !important;
      font-size: 13px !important;
      padding: 2px 6px !important;
    }

    pre {
      padding: 14px !important;
      overflow-x: auto !important;
    }

    /* Ocultar headers/footers propios del backend si los hay */
    nav, footer, .navbar, .footer, header { display: none !important; }

    /* Secciones tipo card */
    section, article, .section, .card {
      background: rgba(255,255,255,0.05) !important;
      border: 1px solid rgba(255,255,255,0.1) !important;
      border-radius: 14px !important;
      padding: 16px !important;
      margin-bottom: 16px !important;
    }
  \`;
  document.head.appendChild(style);
})();
true;
`;

interface Props {
  route: { params: { url: string; title: string } };
  navigation: any;
}

export const WebViewScreen: React.FC<Props> = ({ route, navigation }) => {
  const { url, title } = route.params;
  const insets = useSafeAreaInsets();
  const [loading, setLoading] = useState(true);

  return (
    <View style={[s.root, { paddingTop: insets.top }]}>

      {/* Header */}
      <View style={s.header}>
        <TouchableOpacity style={s.backBtn} onPress={() => navigation.goBack()} activeOpacity={0.75}>
          <Ionicons name="chevron-back" size={22} color="#fff" />
        </TouchableOpacity>
        <Text style={s.titleText} numberOfLines={1}>{title}</Text>
        <View style={{ width: 40 }} />
      </View>

      {/* Divider */}
      <View style={s.divider} />

      {/* WebView */}
      <WebView
        source={{ uri: url }}
        style={s.web}
        injectedJavaScript={INJECTED_CSS}
        onLoadStart={() => setLoading(true)}
        onLoadEnd={() => setLoading(false)}
        javaScriptEnabled
        domStorageEnabled
      />

      {loading && (
        <View style={s.loadingOverlay}>
          <ActivityIndicator size="large" color={GREEN} />
          <Text style={s.loadingText}>Cargando...</Text>
        </View>
      )}

    </View>
  );
};

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: BG },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  backBtn: {
    width: 40, height: 40, borderRadius: 20,
    alignItems: 'center', justifyContent: 'center',
    backgroundColor: 'rgba(255,255,255,0.07)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.1)',
  },
  titleText: {
    flex: 1,
    textAlign: 'center',
    fontSize: 15,
    fontWeight: '700',
    color: '#fff',
    letterSpacing: 0.1,
  },
  divider: {
    height: StyleSheet.hairlineWidth,
    backgroundColor: 'rgba(255,255,255,0.1)',
  },
  web: { flex: 1, backgroundColor: BG },
  loadingOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: BG,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 12,
  },
  loadingText: {
    fontSize: 13,
    color: 'rgba(255,255,255,0.4)',
  },
});
