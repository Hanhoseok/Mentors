import { isAxiosError } from 'axios';
import { apiClient } from '@/api/client';
import {
  DEV_LOCAL_TEST_ACCOUNT_EMAIL,
  DEV_LOCAL_TEST_ACCOUNT_PASSWORD,
  type LocalLoginRequest,
  type LocalSignupRequest,
} from './contracts';

export interface DevAccessTokenRequest {
  email?: string;
  nickname?: string;
  tier?: 'T1' | 'T2' | 'T3' | 'T4' | 'T5';
}

export interface DevAccessTokenUser {
  id: number;
  email: string;
  nickname: string;
  status: string;
}

export interface AuthTokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface GoogleMobileLoginRequest {
  id_token: string;
  platform: 'android' | 'ios';
}

export interface DevAccessTokenResponse extends AuthTokenResponse {
  created: boolean;
  user: DevAccessTokenUser;
  tier?: 'T1' | 'T2' | 'T3' | 'T4' | 'T5' | null;
}

export { DEV_LOCAL_TEST_ACCOUNT_EMAIL, DEV_LOCAL_TEST_ACCOUNT_PASSWORD };
export type { LocalLoginRequest, LocalSignupRequest };

export async function localSignup(payload: LocalSignupRequest): Promise<AuthTokenResponse> {
  const response = await apiClient.post<AuthTokenResponse>('/auth/local/signup', payload);
  return response.data;
}

export async function localLogin(payload: LocalLoginRequest): Promise<AuthTokenResponse> {
  const response = await apiClient.post<AuthTokenResponse>('/auth/local/login', payload);
  return response.data;
}

export async function mobileGoogleLogin(
  payload: GoogleMobileLoginRequest,
): Promise<AuthTokenResponse> {
  const response = await apiClient.post<AuthTokenResponse>('/auth/google/mobile', payload);
  return response.data;
}

export async function issueDevAccessToken(
  payload: DevAccessTokenRequest = {},
): Promise<DevAccessTokenResponse> {
  const response = await apiClient.post<DevAccessTokenResponse>('/auth/dev-token', payload);
  return response.data;
}

export async function getCurrentUser(): Promise<DevAccessTokenUser> {
  const response = await apiClient.get<DevAccessTokenUser>('/auth/me');
  return response.data;
}

export async function deleteCurrentUser(): Promise<void> {
  await apiClient.delete('/auth/me');
}

export function getAuthApiErrorMessage(error: unknown, fallback: string): string {
  if (isAxiosError<{ message?: string }>(error)) {
    return error.response?.data?.message ?? fallback;
  }

  return error instanceof Error ? error.message : fallback;
}
