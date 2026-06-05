const assert = require('node:assert/strict');

const { resolveEntryScreenState } = require('../../.tmp-navigation/_dev-harness/navigation/logic.js');
const { buildMainTabBarMetrics } = require('../../.tmp-navigation/navigation/logic.js');

assert.equal(
  resolveEntryScreenState({
    accessToken: null,
    hasCompletedOnboarding: false,
    isCheckingRemoteStatus: false,
  }),
  'login',
  'users without a token should land on the login screen first',
);

assert.equal(
  resolveEntryScreenState({
    accessToken: 'token',
    hasCompletedOnboarding: false,
    isCheckingRemoteStatus: true,
  }),
  'checking',
  'tokened users should briefly show the remote onboarding status check when needed',
);

assert.equal(
  resolveEntryScreenState({
    accessToken: 'token',
    hasCompletedOnboarding: false,
    isCheckingRemoteStatus: false,
  }),
  'onboarding',
  'authenticated users without onboarding completion should enter onboarding',
);

assert.equal(
  resolveEntryScreenState({
    accessToken: 'token',
    hasCompletedOnboarding: true,
    isCheckingRemoteStatus: false,
  }),
  'home',
  'completed users should land on home',
);

assert.deepEqual(
  buildMainTabBarMetrics({ bottomInset: 0, platform: 'android' }),
  { height: 70, paddingBottom: 12, paddingTop: 10 },
  'android tabs should keep a minimum gap above the system navigation bar',
);

assert.deepEqual(
  buildMainTabBarMetrics({ bottomInset: 24, platform: 'android' }),
  { height: 82, paddingBottom: 24, paddingTop: 10 },
  'android tabs should expand when the device reports a bottom inset',
);

assert.deepEqual(
  buildMainTabBarMetrics({ bottomInset: 34, platform: 'ios' }),
  { height: 94, paddingBottom: 34, paddingTop: 10 },
  'ios tabs should respect the home-indicator safe area',
);

console.log('navigation logic tests passed');
