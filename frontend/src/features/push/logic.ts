export type NativePushPlatform = 'ios' | 'android';

export function buildDeviceRegistrationPayload(input: {
  pushToken: string;
  platform: NativePushPlatform;
}): {
  fcm_token: string;
  platform: NativePushPlatform;
} {
  return {
    fcm_token: input.pushToken.trim(),
    platform: input.platform,
  };
}

export function resolveNotificationDeepLink(data: unknown): string | null {
  if (!data || typeof data !== 'object') {
    return null;
  }

  const deeplink = (data as Record<string, unknown>).deeplink;
  if (typeof deeplink !== 'string') {
    return null;
  }

  const normalized = deeplink.trim();
  return normalized || null;
}

export function shouldRegisterPushToken(input: {
  currentToken: string;
  lastRegisteredToken: string | null;
}): boolean {
  const normalized = input.currentToken.trim();
  return Boolean(normalized) && normalized !== input.lastRegisteredToken;
}
