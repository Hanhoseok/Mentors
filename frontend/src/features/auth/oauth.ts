export interface AuthCallbackParams {
  token: string | null;
  error: string | null;
  isNew: boolean;
}

export type GoogleMobilePlatform = 'android' | 'ios';

export interface GoogleAuthClientIdInput {
  platform: GoogleMobilePlatform;
  webClientId: string | null | undefined;
  iosClientId: string | null | undefined;
}

export interface GoogleNativeLoginPayloadInput {
  idToken: string;
  platform: GoogleMobilePlatform;
}

const AUTH_CALLBACK_PARAM_NAMES = ['token', 'error', 'is_new'] as const;

export function parseAuthCallbackParams(search: string): AuthCallbackParams {
  const normalizedSearch = search.startsWith('?') ? search.slice(1) : search;
  const params = new URLSearchParams(normalizedSearch);

  return {
    token: params.get('token'),
    error: params.get('error'),
    isNew: params.get('is_new') === '1',
  };
}

export function parseAuthCallbackUrl(url: string): AuthCallbackParams | null {
  try {
    const parsed = new URL(url);
    const isAuthCallback =
      parsed.host === 'auth' || parsed.pathname === '/auth' || parsed.pathname === '/--/auth';
    if (!isAuthCallback) {
      return null;
    }

    return parseAuthCallbackParams(parsed.search);
  } catch {
    return null;
  }
}

export function sanitizeAuthReturnTo(input: string): string {
  try {
    const url = new URL(input);
    for (const paramName of AUTH_CALLBACK_PARAM_NAMES) {
      url.searchParams.delete(paramName);
    }
    url.hash = '';
    return url.toString();
  } catch {
    return input;
  }
}

export function buildGoogleLoginStartUrl(apiBaseUrl: string, returnTo: string): string {
  const normalizedBaseUrl = apiBaseUrl.replace(/\/+$/, '');
  const url = new URL(`${normalizedBaseUrl}/auth/google/login`);
  url.searchParams.set('return_to', sanitizeAuthReturnTo(returnTo));
  return url.toString();
}

export function buildNativeAuthReturnTo(createUrl: (path: string) => string): string {
  return createUrl('auth');
}

export function buildGoogleNativeSigninConfig({
  platform,
  webClientId,
  iosClientId,
}: GoogleAuthClientIdInput): { webClientId: string; iosClientId?: string } | null {
  const normalizedWebClientId = webClientId?.trim();
  if (!normalizedWebClientId) {
    return null;
  }

  if (platform === 'ios') {
    const normalizedIosClientId = iosClientId?.trim();
    if (normalizedIosClientId) {
      return {
        webClientId: normalizedWebClientId,
        iosClientId: normalizedIosClientId,
      };
    }
  }

  return {
    webClientId: normalizedWebClientId,
  };
}

export function buildGoogleNativeLoginPayload({
  idToken,
  platform,
}: GoogleNativeLoginPayloadInput) {
  return {
    id_token: idToken,
    platform,
  };
}
