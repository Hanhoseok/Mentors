import { apiClient } from '@/api/client';
import type { NativePushPlatform } from './logic';

export interface DeviceRegistrationResponse {
  id: number;
  platform: string;
}

export async function registerDevicePushToken(input: {
  pushToken: string;
  platform: NativePushPlatform;
}): Promise<DeviceRegistrationResponse> {
  const response = await apiClient.post<DeviceRegistrationResponse>('/me/devices', {
    fcm_token: input.pushToken,
    platform: input.platform,
  });
  return response.data;
}

export async function unregisterDevicePushToken(deviceId: number): Promise<void> {
  await apiClient.delete(`/me/devices/${deviceId}`);
}
