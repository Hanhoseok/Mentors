const assert = require('node:assert/strict');

const {
  DEV_LOCAL_TEST_ACCOUNT_EMAIL,
  DEV_LOCAL_TEST_ACCOUNT_PASSWORD,
  buildGoogleLoginStartUrl,
  buildLocalLoginPayload,
  buildLocalSignupPayload,
  normalizeEmailInput,
  parseAuthCallbackParams,
  validateAuthDraft,
} = require('../../.tmp-harness-auth/_dev-harness/auth/logic.js');

assert.equal(
  normalizeEmailInput('  USER@Example.COM  '),
  'user@example.com',
  'email inputs should be trimmed and normalized to lowercase',
);

assert.equal(
  validateAuthDraft('login', {
    email: '',
    password: '',
    passwordConfirm: '',
  }),
  '이메일과 비밀번호를 입력해 주세요.',
  'login mode should require both email and password',
);

assert.equal(
  validateAuthDraft('signup', {
    email: 'user@example.com',
    password: 'Mentors123!',
    passwordConfirm: 'Mismatch123!',
  }),
  '비밀번호 확인이 일치하지 않습니다.',
  'signup mode should reject mismatched password confirmation',
);

assert.equal(
  validateAuthDraft('signup', {
    email: 'user@example.com',
    password: 'short',
    passwordConfirm: 'short',
  }),
  '비밀번호는 8자 이상으로 입력해 주세요.',
  'signup mode should enforce the same minimum password rule as the backend',
);

assert.deepEqual(
  buildLocalLoginPayload({
    email: ' Demo@Mentors.dev ',
    password: 'Mentors123!',
  }),
  {
    email: 'demo@mentors.dev',
    password: 'Mentors123!',
  },
  'login payloads should normalize email before submission',
);

assert.deepEqual(
  buildLocalSignupPayload({
    email: ' Demo@Mentors.dev ',
    password: 'Mentors123!',
    passwordConfirm: 'Mentors123!',
  }),
  {
    email: 'demo@mentors.dev',
    password: 'Mentors123!',
    password_confirm: 'Mentors123!',
  },
  'signup payloads should match backend field names and normalize email',
);

assert.equal(
  buildGoogleLoginStartUrl('http://127.0.0.1:8000', 'http://127.0.0.1:3000/?token=old&error=stale'),
  'http://127.0.0.1:8000/auth/google/login?return_to=http%3A%2F%2F127.0.0.1%3A3000%2F',
  'google login redirect URLs should strip stale auth query params from the return target',
);

assert.deepEqual(
  parseAuthCallbackParams('?token=test-token&is_new=1'),
  {
    token: 'test-token',
    error: null,
    isNew: true,
  },
  'callback parsing should recover the issued token and new-user flag from the return URL',
);

assert.deepEqual(
  parseAuthCallbackParams(
    '?error=%EA%B5%AC%EA%B8%80+%EB%A1%9C%EA%B7%B8%EC%9D%B8+%EC%8B%A4%ED%8C%A8',
  ),
  {
    token: null,
    error: '구글 로그인 실패',
    isNew: false,
  },
  'callback parsing should surface backend auth errors for the login screen',
);

assert.equal(
  DEV_LOCAL_TEST_ACCOUNT_EMAIL,
  'local-test@mentors.dev',
  'frontend test-account login should stay aligned with the backend dev dummy account email',
);

assert.equal(
  DEV_LOCAL_TEST_ACCOUNT_PASSWORD,
  'Mentors123!',
  'frontend test-account login should stay aligned with the backend dev dummy account password',
);

console.log('auth logic tests passed');
