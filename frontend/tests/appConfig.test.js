const assert = require('node:assert/strict');

process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID =
  '1234567890-abcdefghijklmnopqrstuvwxyz.apps.googleusercontent.com';

const loadConfig = require('../app.config.js');

const config = loadConfig();
const plugins = Array.isArray(config.plugins) ? config.plugins : [];

const notificationPlugin = plugins.find(
  (plugin) => Array.isArray(plugin) && plugin[0] === 'expo-notifications',
);

assert.ok(notificationPlugin, 'expo-notifications plugin should be present in the final Expo config');
assert.deepEqual(
  notificationPlugin[1],
  {
    color: '#2D6A4F',
    defaultChannel: 'mentors-reminders',
  },
  'notification plugin config should pin the default channel and brand color before the next dev-client rebuild',
);

const googlePlugin = plugins.find(
  (plugin) => Array.isArray(plugin) && plugin[0] === '@react-native-google-signin/google-signin',
);

assert.ok(googlePlugin, 'the native Google Sign-In plugin should stay enabled alongside notifications');
assert.deepEqual(
  googlePlugin[1],
  {
    iosUrlScheme: 'com.googleusercontent.apps.1234567890-abcdefghijklmnopqrstuvwxyz',
  },
  'the Google Sign-In plugin should keep deriving the iOS URL scheme from the configured client id',
);

console.log('app config tests passed');
