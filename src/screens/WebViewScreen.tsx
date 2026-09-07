import React, { useState } from 'react';
import { View, StyleSheet, ActivityIndicator, TouchableOpacity, Text } from 'react-native';
import { WebView } from 'react-native-webview';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

const BG     = '#FFFFFF';
const LOGO_B64 = 'data:image/jpeg;base64,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';

const INJECTED_CSS = `
(function() {
  // Deshabilitar estilos existentes
  try {
    document.querySelectorAll('link[rel="stylesheet"]').forEach(function(l) { l.disabled = true; });
    document.querySelectorAll('style:not(#qc-inject)').forEach(function(s) { s.disabled = true; });
  } catch(e) {}

  // Fondo blanco forzado
  document.documentElement.style.cssText = 'background:#fff!important';
  document.body.style.cssText = 'background:#fff!important;color:#374151!important;margin:0!important;padding:24px 20px 48px!important;max-width:100%!important;font-family:-apple-system,BlinkMacSystemFont,sans-serif!important;font-size:15px!important;line-height:1.7!important;';

  // Reemplazar logos
  function replaceLogo() {
    document.querySelectorAll('img').forEach(function(img) {
      var src = (img.getAttribute('src') || '').toLowerCase();
      var alt = (img.alt || '').toLowerCase();
      var cls = (img.className || '').toLowerCase();
      if (src.includes('logo') || alt.includes('logo') || alt.includes('qori') || cls.includes('logo')) {
        img.src = '${LOGO_B64}';
        img.style.cssText = 'max-width:140px!important;height:auto!important;display:block!important;margin:0 0 16px 0!important;border-radius:8px!important;';
      }
    });
  }
  setTimeout(replaceLogo, 200);
  setTimeout(replaceLogo, 800);

  var style = document.createElement('style');
  style.id = 'qc-inject';
  style.innerHTML = \`
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    *, *::before, *::after {
      box-sizing: border-box;
      -webkit-font-smoothing: antialiased;
    }

    html, body {
      background-color: #FFFFFF !important;
      color: #374151 !important;
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
      color: #0D1117 !important;
      font-weight: 700 !important;
      line-height: 1.3 !important;
      margin-top: 28px !important;
      margin-bottom: 10px !important;
      letter-spacing: -0.2px !important;
    }

    h1 { font-size: 22px !important; font-weight: 800 !important; color: #0D1117 !important; margin-top: 0 !important; }
    h2 { font-size: 17px !important; color: #0D1117 !important; }
    h3 { font-size: 15px !important; color: #1F2937 !important; }

    p {
      color: #4B5563 !important;
      margin-bottom: 14px !important;
      margin-top: 0 !important;
    }

    ul, ol {
      color: #4B5563 !important;
      padding-left: 20px !important;
      margin-bottom: 14px !important;
    }

    li {
      margin-bottom: 6px !important;
    }

    a {
      color: #0D1117 !important;
      text-decoration: underline !important;
    }

    strong, b {
      color: #0D1117 !important;
      font-weight: 600 !important;
    }

    em, i {
      color: #6B7280 !important;
    }

    hr {
      border: none !important;
      border-top: 1px solid rgba(0,0,0,0.1) !important;
      margin: 24px 0 !important;
    }

    table {
      width: 100% !important;
      border-collapse: collapse !important;
      margin-bottom: 16px !important;
    }

    th {
      background: #F3F4F6 !important;
      color: #0D1117 !important;
      font-weight: 700 !important;
      padding: 10px 12px !important;
      text-align: left !important;
      border: 1px solid rgba(0,0,0,0.1) !important;
    }

    td {
      padding: 9px 12px !important;
      border: 1px solid rgba(0,0,0,0.07) !important;
      color: #4B5563 !important;
    }

    tr:nth-child(even) td {
      background: #F9FAFB !important;
    }

    blockquote {
      border-left: 3px solid #0D1117 !important;
      margin: 16px 0 !important;
      padding: 10px 16px !important;
      background: #F3F4F6 !important;
      border-radius: 0 8px 8px 0 !important;
      color: #4B5563 !important;
    }

    code, pre {
      background: #F3F4F6 !important;
      color: #0D1117 !important;
      border-radius: 6px !important;
      font-size: 13px !important;
      padding: 2px 6px !important;
    }

    pre {
      padding: 14px !important;
      overflow-x: auto !important;
    }

    nav, footer, .navbar, .footer, header { display: none !important; }

    section, article, .section, .card {
      background: #F9FAFB !important;
      border: 1px solid rgba(0,0,0,0.07) !important;
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
          <Ionicons name="chevron-back" size={22} color="#FFFFFF" />
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
        injectedJavaScriptBeforeContentLoaded={INJECTED_CSS}
        onLoadStart={() => setLoading(true)}
        onLoadEnd={() => setLoading(false)}
        javaScriptEnabled
        domStorageEnabled
      />

      {loading && (
        <View style={s.loadingOverlay}>
          <ActivityIndicator size="large" color="#0D1117" />
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
    backgroundColor: '#0D1117',
  },
  titleText: {
    flex: 1,
    textAlign: 'center',
    fontSize: 15,
    fontWeight: '700',
    color: '#0D1117',
    letterSpacing: 0.1,
  },
  divider: {
    height: StyleSheet.hairlineWidth,
    backgroundColor: 'rgba(0,0,0,0.07)',
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
    color: '#9CA3AF',
  },
});
