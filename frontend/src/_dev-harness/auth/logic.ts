import {
  DEV_LOCAL_TEST_ACCOUNT_EMAIL,
  DEV_LOCAL_TEST_ACCOUNT_PASSWORD,
  type LocalLoginRequest,
  type LocalSignupRequest,
} from '../../features/auth/contracts';
export {
  buildGoogleNativeLoginPayload,
  buildGoogleNativeSigninConfig,
  buildGoogleLoginStartUrl,
  buildNativeAuthReturnTo,
  parseAuthCallbackParams,
  parseAuthCallbackUrl,
  sanitizeAuthReturnTo,
} from '../../features/auth/oauth';

export type AuthMode = 'login' | 'signup';

export interface AuthDraft {
  email: string;
  password: string;
  passwordConfirm: string;
}

export const EMPTY_AUTH_DRAFT: AuthDraft = {
  email: '',
  password: '',
  passwordConfirm: '',
};

export { DEV_LOCAL_TEST_ACCOUNT_EMAIL, DEV_LOCAL_TEST_ACCOUNT_PASSWORD };

export function normalizeEmailInput(value: string): string {
  return value.trim().toLowerCase();
}

export function validateAuthDraft(mode: AuthMode, draft: AuthDraft): string | null {
  const email = normalizeEmailInput(draft.email);
  const password = draft.password.trim();
  const passwordConfirm = draft.passwordConfirm.trim();

  if (!email || !password) {
    return '이메일과 비밀번호를 입력해 주세요.';
  }

  if (mode === 'signup') {
    if (password.length < 8) {
      return '비밀번호는 8자 이상으로 입력해 주세요.';
    }

    if (!passwordConfirm) {
      return '비밀번호 확인을 입력해 주세요.';
    }

    if (password !== passwordConfirm) {
      return '비밀번호 확인이 일치하지 않습니다.';
    }
  }

  return null;
}

export function buildLocalLoginPayload(
  draft: Pick<AuthDraft, 'email' | 'password'>,
): LocalLoginRequest {
  return {
    email: normalizeEmailInput(draft.email),
    password: draft.password,
  };
}

export function buildLocalSignupPayload(draft: AuthDraft): LocalSignupRequest {
  return {
    email: normalizeEmailInput(draft.email),
    password: draft.password,
    password_confirm: draft.passwordConfirm,
  };
}

export function buildTestAccountLoginPayload(): LocalLoginRequest {
  return {
    email: DEV_LOCAL_TEST_ACCOUNT_EMAIL,
    password: DEV_LOCAL_TEST_ACCOUNT_PASSWORD,
  };
}

