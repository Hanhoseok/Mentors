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
  {
    height: 58,
    paddingBottom: 8,
    paddingTop: 8,
    marginBottom: 8,
    marginHorizontal: 14,
    borderRadius: 24,
  },
  'floating tabs should keep a stable card size even without a bottom inset',
);

assert.deepEqual(
  buildMainTabBarMetrics({ bottomInset: 24, platform: 'android' }),
  {
    height: 58,
    paddingBottom: 8,
    paddingTop: 8,
    marginBottom: 32,
    marginHorizontal: 14,
    borderRadius: 24,
  },
  'floating tabs should move upward by the reported bottom inset while keeping the same card size',
);

assert.deepEqual(
  buildMainTabBarMetrics({ bottomInset: 34, platform: 'ios' }),
  {
    height: 58,
    paddingBottom: 8,
    paddingTop: 8,
    marginBottom: 42,
    marginHorizontal: 14,
    borderRadius: 24,
  },
  'floating tabs should respect the home-indicator inset through bottom margin',
);

console.log('navigation logic tests passed');
