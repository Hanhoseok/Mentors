import { Platform } from 'react-native';
import type { ReminderPreferences } from '../store/settingsStore';
import { buildScheduledReminderRequests } from './logic';

const REMINDER_CHANNEL_ID = 'mentors-reminders';
const REMINDER_REQUEST_KEYS = new Set(['learning-reminder', 'daily-report']);

type NotificationsModule = typeof import('expo-notifications');

let notificationsModulePromise: Promise<NotificationsModule> | null = null;

async function getNotificationsModuleAsync(): Promise<NotificationsModule | null> {
  if (Platform.OS === 'web') {
    return null;
  }

  if (!notificationsModulePromise) {
    notificationsModulePromise = import('expo-notifications');
  }

  return notificationsModulePromise;
}

async function ensureReminderChannelAsync(): Promise<void> {
  if (Platform.OS !== 'android') {
    return;
  }

  const Notifications = await getNotificationsModuleAsync();
  if (!Notifications) {
    return;
  }

  await Notifications.setNotificationChannelAsync(REMINDER_CHANNEL_ID, {
    name: 'Mentors Reminders',
    importance: Notifications.AndroidImportance.DEFAULT,
    vibrationPattern: [0, 180, 120, 180],
    lightColor: '#2D6A4F',
  });
}

async function cancelManagedReminderNotificationsAsync(): Promise<void> {
  const Notifications = await getNotificationsModuleAsync();
  if (!Notifications) {
    return;
  }

  const scheduled = await Notifications.getAllScheduledNotificationsAsync();
  const managedRequests = scheduled.filter((request) => {
    const settingsKey = request.content.data?.settingsKey;
    return typeof settingsKey === 'string' && REMINDER_REQUEST_KEYS.has(settingsKey);
  });

  await Promise.all(
    managedRequests.map((request) =>
      Notifications.cancelScheduledNotificationAsync(request.identifier),
    ),
  );
}

export async function ensureReminderPermissionsAsync(): Promise<boolean> {
  const Notifications = await getNotificationsModuleAsync();
  if (!Notifications) {
    return true;
  }

  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldPlaySound: true,
      shouldSetBadge: false,
      shouldShowBanner: true,
      shouldShowList: true,
    }),
  });

  await ensureReminderChannelAsync();

  const existing = await Notifications.getPermissionsAsync();
  let finalStatus = existing.status;

  if (finalStatus !== 'granted') {
    const requested = await Notifications.requestPermissionsAsync();
    finalStatus = requested.status;
  }

  return finalStatus === 'granted';
}

export async function syncReminderNotifications(preferences: ReminderPreferences): Promise<void> {
  const Notifications = await getNotificationsModuleAsync();
  if (!Notifications) {
    return;
  }

  await ensureReminderChannelAsync();
  await cancelManagedReminderNotificationsAsync();

  const requests = buildScheduledReminderRequests(preferences);
  await Promise.all(
    requests.map((request) =>
      Notifications.scheduleNotificationAsync({
        content: {
          title: request.title,
          body: request.body,
          data: {
            settingsKey: request.key,
          },
        },
        trigger: {
          type: Notifications.SchedulableTriggerInputTypes.DAILY,
          hour: request.trigger.hour,
          minute: request.trigger.minute,
          channelId: REMINDER_CHANNEL_ID,
        },
      }),
    ),
  );
}
