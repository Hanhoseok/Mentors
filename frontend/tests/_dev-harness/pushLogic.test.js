const assert = require('node:assert/strict');

const {
  buildDeviceRegistrationPayload,
  resolveNotificationDeepLink,
  shouldRegisterPushToken,
} = require('../../.tmp-push/features/push/logic.js');

assert.deepEqual(
  buildDeviceRegistrationPayload({
    pushToken: '  test-device-token  ',
    platform: 'android',
  }),
  {
    fcm_token: 'test-device-token',
    platform: 'android',
  },
  'device registration payloads should match backend field names and trim token whitespace',
);

assert.equal(
  resolveNotificationDeepLink({ deeplink: ' mentors://report/42 ' }),
  'mentors://report/42',
  'deeplink parsing should recover and normalize backend push payloads',
);

assert.equal(
  resolveNotificationDeepLink({ deeplink: '' }),
  null,
  'empty deeplinks should be ignored so notification taps do not trigger invalid navigation attempts',
);

assert.equal(
  resolveNotificationDeepLink(null),
  null,
  'non-object notification payloads should be treated as having no deeplink',
);

assert.equal(
  shouldRegisterPushToken({
    currentToken: 'fresh-token',
    lastRegisteredToken: null,
  }),
  true,
  'a newly acquired device token should be registered',
);

assert.equal(
  shouldRegisterPushToken({
    currentToken: 'same-token',
    lastRegisteredToken: 'same-token',
  }),
  false,
  'the scaffold should avoid redundant registration calls when the native token is unchanged',
);

console.log('push logic tests passed');
