import { Linking, Platform } from 'react-native';
import {
  buildDeviceRegistrationPayload,
  resolveNotificationDeepLink,
  shouldRegisterPushToken,
  type NativePushPlatform,
} from './logic';
import { registerDevicePushToken, unregisterDevicePushToken } from './api';

type NotificationsModule = typeof import('expo-notifications');
type NotificationResponse = import('expo-notifications').NotificationResponse;
type EventSubscription = { remove: () => void };

let notificationsModulePromise: Promise<NotificationsModule | null> | null = null;
let responseSubscription: EventSubscription | null = null;
let pushTokenSubscription: EventSubscription | null = null;
let activeAccessToken: string | null = null;
let lastRegisteredToken: string | null = null;
let lastRegisteredDeviceId: number | null = null;
let bootstrapPromise: Promise<void> | null = null;

async function getNotificationsModuleAsync(): Promise<NotificationsModule | null> {
  if (Platform.OS === 'web') {
    return null;
  }

  if (!notificationsModulePromise) {
    notificationsModulePromise = import('expo-notifications');
  }

  return notificationsModulePromise;
}

function getNativePushPlatform(): NativePushPlatform | null {
  if (Platform.OS === 'ios' || Platform.OS === 'android') {
    return Platform.OS;
  }

  return null;
}

function removeSubscriptions(): void {
  responseSubscription?.remove();
  responseSubscription = null;
  pushTokenSubscription?.remove();
  pushTokenSubscription = null;
}

async function handleNotificationResponseAsync(response: NotificationResponse): Promise<void> {
  const deeplink = resolveNotificationDeepLink(response.notification.request.content.data);
  if (deeplink) {
    await Linking.openURL(deeplink);
  }
}

async function registerCurrentTokenAsync(
  currentToken: string,
  platform: NativePushPlatform,
): Promise<void> {
  if (!shouldRegisterPushToken({ currentToken, lastRegisteredToken })) {
    return;
  }

  const payload = buildDeviceRegistrationPayload({
    pushToken: currentToken,
    platform,
  });

  try {
    const response = await registerDevicePushToken({
      pushToken: payload.fcm_token,
      platform: payload.platform,
    });
    lastRegisteredToken = payload.fcm_token;
    lastRegisteredDeviceId = response.id;
  } catch (error) {
    console.warn('push token registration failed', error);
  }
}

async function attachRuntimeListenersAsync(Notifications: NotificationsModule): Promise<void> {
  if (!responseSubscription) {
    responseSubscription = Notifications.addNotificationResponseReceivedListener((response) => {
      void handleNotificationResponseAsync(response);
    });
  }

  if (!pushTokenSubscription) {
    pushTokenSubscription = Notifications.addPushTokenListener((token) => {
      const platform = getNativePushPlatform();
      if (!platform) {
        return;
      }

      void registerCurrentTokenAsync(String(token.data ?? ''), platform);
    });
  }
}

async function bootstrapNativePushAsync(): Promise<void> {
  const Notifications = await getNotificationsModuleAsync();
  const platform = getNativePushPlatform();

  if (!Notifications || !platform || !activeAccessToken) {
    return;
  }

  await attachRuntimeListenersAsync(Notifications);

  const permissions = await Notifications.getPermissionsAsync();
  if (permissions.status !== 'granted') {
    return;
  }

  try {
    const token = await Notifications.getDevicePushTokenAsync();
    await registerCurrentTokenAsync(String(token.data ?? ''), platform);
  } catch (error) {
    console.warn('native push bootstrap skipped', error);
  }

  const lastResponse = await Notifications.getLastNotificationResponseAsync();
  if (lastResponse) {
    await handleNotificationResponseAsync(lastResponse);
  }
}

export async function syncNativePushState(accessToken: string | null): Promise<void> {
  activeAccessToken = accessToken;

  if (!accessToken) {
    removeSubscriptions();
    lastRegisteredToken = null;
    lastRegisteredDeviceId = null;
    return;
  }

  if (!bootstrapPromise) {
    bootstrapPromise = bootstrapNativePushAsync().finally(() => {
      bootstrapPromise = null;
    });
  }

  await bootstrapPromise;
}

export async function unregisterNativePushState(): Promise<void> {
  removeSubscriptions();

  if (!activeAccessToken || lastRegisteredDeviceId == null) {
    return;
  }

  try {
    await unregisterDevicePushToken(lastRegisteredDeviceId);
  } catch (error) {
    console.warn('push token unregister failed', error);
  } finally {
    lastRegisteredDeviceId = null;
    lastRegisteredToken = null;
  }
}
