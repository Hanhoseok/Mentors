const appJson = require('./app.json');
const NOTIFICATION_PLUGIN = [
  'expo-notifications',
  {
    color: '#2D6A4F',
    defaultChannel: 'mentors-reminders',
  },
];

function buildGoogleIosUrlScheme(clientId) {
  const normalized = clientId?.trim();
  if (!normalized) {
    return null;
  }

  const suffix = normalized.replace(/\.apps\.googleusercontent\.com$/u, '');
  if (!suffix || suffix === normalized) {
    return null;
  }

  return `com.googleusercontent.apps.${suffix}`;
}

function withoutPlugin(plugins, pluginName) {
  return plugins.filter((plugin) => {
    if (Array.isArray(plugin)) {
      return plugin[0] !== pluginName;
    }
    return plugin !== pluginName;
  });
}

module.exports = () => {
  const baseConfig = appJson.expo;
  const iosUrlScheme = buildGoogleIosUrlScheme(process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID);
  const basePlugins = Array.isArray(baseConfig.plugins) ? baseConfig.plugins : [];
  const plugins = withoutPlugin(
    withoutPlugin(basePlugins, '@react-native-google-signin/google-signin'),
    'expo-notifications',
  );

  plugins.push(NOTIFICATION_PLUGIN);

  if (iosUrlScheme) {
    plugins.push([
      '@react-native-google-signin/google-signin',
      {
        iosUrlScheme,
      },
    ]);
  }

  return {
    ...baseConfig,
    plugins,
  };
};
